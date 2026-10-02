"""Closed fixed-write contracts and temporal fences using disposable peers."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError
from pydantic import TypeAdapter

from core.godot_server import create_server
from modules.godot.bridge import GodotBridge
from modules.godot.config import Config
from modules.godot.protocol import (BRIDGE_VERSION, BridgeError, RigLabResult, WRITE_OPERATION,
                                   encode, envelope, error_info, validate_response, validate_result)
from modules.godot.tools import call_bridge, tool_result
from tests.fake_godot_client import (FakeGodotClient, LAB_SCENE, ROOT_NODE, disposable_credential,
                                     result_for, rig_lab_result)


def writer_response(request, credential, *, code=None):
    return {"type": "response", "protocol_version": 1, "id": request["id"],
            "operation": WRITE_OPERATION, "editor_session_id": request["editor_session_id"],
            "ok": code is None, "result": rig_lab_result(credential) if code is None else None,
            "error": error_info(code) if code is not None else None}


class RigLabSchemaTests(unittest.TestCase):
    def setUp(self):
        self.credential = disposable_credential()
        self.data = rig_lab_result(self.credential)

    def test_fixed_seven_node_result_and_closed_schema(self):
        validate_result(WRITE_OPERATION, self.data)
        TypeAdapter(RigLabResult).validate_python(envelope(self.data, elapsed_ms=0.1))
        self.assertEqual(BRIDGE_VERSION, "0.4.0")
        for field, value in (("created_node_count", 8), ("created_node_count", True),
                             ("undo_actions_added", 0), ("auto_saved", True), ("read_only", True),
                             ("scene_path", "res://scenes/presentation/totolina_operator.tscn"),
                             ("root_name", "Other"), ("created_root", "Other"), ("save_state", "saved_clean"),
                             ("undo_action_name", "Other"), ("arbitrary_resource", {})):
            with self.subTest(field=field, value=value):
                data = dict(self.data, **{field: value})
                with self.assertRaises(BridgeError):
                    validate_result(WRITE_OPERATION, data)

    def test_writer_reply_requires_correlated_session_for_success_and_failure(self):
        request = {"id": "a" * 32, "editor_session_id": self.data["editor_session_id"]}
        for code in (None, "LAB_SCENE_REQUIRED", "WRITE_REPLAY_REJECTED", "SESSION_WRITE_LIMIT"):
            response = writer_response(request, self.credential, code=code)
            validate_response(response)
            del response["editor_session_id"]
            with self.assertRaises(BridgeError):
                validate_response(response)
        response = writer_response(request, self.credential)
        response["editor_session_id"] = "another-session"
        with self.assertRaises(BridgeError):
            validate_response(response)

    def test_read_reply_shape_is_unchanged_and_rejects_writer_only_metadata(self):
        response = {"type": "response", "protocol_version": 1, "id": "b" * 32,
                    "operation": "godot_get_editor_state", "ok": True,
                    "result": result_for("godot_get_editor_state", self.credential, LAB_SCENE, [], []), "error": None}
        validate_response(response)
        response["editor_session_id"] = "disposable-editor-session"
        with self.assertRaises(BridgeError):
            validate_response(response)

    def test_unapproved_writer_failure_cannot_appear_as_safe_rejection(self):
        response = writer_response({"id": "a" * 32, "editor_session_id": "disposable-editor-session"},
                                   self.credential, code="INSPECTION_FAILED")
        with self.assertRaises(BridgeError):
            validate_response(response)


class RigLabTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = disposable_credential()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.15), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)

    async def peer(self, **kwargs):
        peer = await FakeGodotClient(self.credential, self.bridge.port, scene=LAB_SCENE,
                                     nodes=[ROOT_NODE], **kwargs).__aenter__()
        self.addAsyncCleanup(peer.__aexit__, None, None, None)
        return peer

    async def wait_requests(self, peer, count):
        async with asyncio.timeout(2):
            while len(peer.requests) < count:
                peer.request_received.clear()
                await peer.request_received.wait()

    async def failure(self, code, action=None):
        with self.assertRaises(BridgeError) as error:
            await (action if action is not None else self.bridge.request(WRITE_OPERATION, {}))
        self.assertEqual(error.exception.code, code)

    async def send_read(self, peer, request):
        await peer.socket.send(encode({"type": "response", "protocol_version": 1, "id": request["id"],
                                      "operation": request["operation"], "ok": True,
                                      "result": result_for(request["operation"], self.credential, LAB_SCENE, [ROOT_NODE], []),
                                      "error": None}))

    async def test_every_writer_has_fresh_ordered_barrier_and_session_bound_wire(self):
        peer = await self.peer()
        data, _ = await self.bridge.request(WRITE_OPERATION, {})
        self.assertEqual(data, rig_lab_result(self.credential))
        await self.failure("LAB_ALREADY_CREATED")
        self.assertEqual([request["operation"] for request in peer.requests],
                         ["godot_get_editor_state", WRITE_OPERATION] * 2)
        for request in peer.requests:
            fields = {"type", "protocol_version", "id", "operation", "params"}
            if request["operation"] == WRITE_OPERATION:
                fields.add("editor_session_id")
                self.assertEqual(request["editor_session_id"], peer.session_id)
            self.assertEqual(set(request), fields)
        self.assertEqual(peer.applied_writes, 1)

    async def test_write_busy_is_not_queued_while_preflight_active(self):
        peer = await self.peer(ignore=True)
        first = asyncio.create_task(self.bridge.request(WRITE_OPERATION, {}))
        await self.wait_requests(peer, 1)
        await self.failure("WRITE_BUSY")
        self.assertEqual(len(peer.requests), 1)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        self.assertFalse(self.bridge._write_active)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_lost_reply_blocks_write_until_explicit_read_then_keeps_original_unknown(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        self.assertEqual(len(peer.requests), 2)
        data, _ = await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(data["scene"]["save_state"], "saved_dirty")
        self.assertIsNone(self.bridge._unresolved_write)
        peer.ignore_write_reply = False
        await self.failure("LAB_ALREADY_CREATED")
        self.assertEqual(peer.applied_writes, 1)

    async def test_ordered_read_waits_for_delayed_old_dispatch_before_rearming(self):
        peer = await self.peer(write_delay=0.22)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await self.failure("WRITE_BUSY")
        data, _ = await self.bridge.request("godot_get_editor_state", {})
        self.assertTrue(data["scene"]["dirty_changes"])
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_earlier_read_reply_does_not_settle_later_unknown_write(self):
        peer = await self.peer(ignore=True)
        writer = asyncio.create_task(self.bridge.request(WRITE_OPERATION, {}))
        await self.wait_requests(peer, 1)
        self.bridge.config = Config(request_timeout_seconds=0.6)
        earlier = asyncio.create_task(self.bridge.request("godot_get_editor_state", {}))
        await self.wait_requests(peer, 2)
        self.bridge.config = Config(request_timeout_seconds=0.1)
        await self.send_read(peer, peer.requests[0])
        await self.wait_requests(peer, 3)
        await self.failure("WRITE_OUTCOME_UNKNOWN", writer)
        self.assertIsNotNone(self.bridge._unresolved_write)
        # A valid reply from a read sent BEFORE the writer is not its barrier.
        await self.send_read(peer, peer.requests[1])
        await earlier
        self.assertIsNotNone(self.bridge._unresolved_write)
        later = asyncio.create_task(self.bridge.request("godot_get_editor_state", {}))
        await self.wait_requests(peer, 4)
        await self.send_read(peer, peer.requests[3])
        await later
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_cancellation_after_send_reports_unknown_and_keeps_gate(self):
        peer = await self.peer(ignore_write_reply=True)
        writer = asyncio.create_task(self.bridge.request(WRITE_OPERATION, {}))
        await self.wait_requests(peer, 2)
        writer.cancel()
        await self.failure("WRITE_OUTCOME_UNKNOWN", writer)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_incomplete_send_retires_transport_before_replacement_read(self):
        peer = await self.peer()
        connection = self.bridge._connection
        original_send = connection.send

        async def interrupted_send(message):
            if '"operation":"godot_create_rig_lab"' in message:
                await asyncio.Event().wait()
            await original_send(message)

        with patch.object(connection, "send", interrupted_send):
            await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNone(self.bridge._connection)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await peer.socket.wait_closed()
        replacement = await self.peer()
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        await self.bridge.request(WRITE_OPERATION, {})
        self.assertEqual(replacement.applied_writes, 1)

    async def test_write_reply_session_missing_or_changed_is_unknown_not_safe_failure(self):
        for mode in ("missing", "changed"):
            def mutate(response):
                if response["operation"] == WRITE_OPERATION:
                    if mode == "missing":
                        del response["editor_session_id"]
                    else:
                        response["editor_session_id"] = "different-session"
            peer = await self.peer(mutate=mutate)
            await self.failure("WRITE_OUTCOME_UNKNOWN")
            self.assertEqual(peer.applied_writes, 1)
            self.assertIsNotNone(self.bridge._unresolved_write)
            await peer.socket.wait_closed()
            if mode == "missing":
                replacement = await self.peer()
                await self.bridge.request("godot_get_editor_state", {})
                await replacement.__aexit__()

    async def test_wrong_project_postcommit_result_is_unknown(self):
        def mutate(response):
            if response["operation"] == WRITE_OPERATION:
                response["result"]["project_path"] = "c:/another/project"
        peer = await self.peer(mutate=mutate)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNotNone(self.bridge._unresolved_write)

    async def test_postsend_nonwriter_failure_code_is_unknown(self):
        def mutate(response):
            if response["operation"] == WRITE_OPERATION:
                response.update(ok=False, result=None, error=error_info("INSPECTION_FAILED"))
        await self.peer(mutate=mutate)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNotNone(self.bridge._unresolved_write)

    async def test_incompatible_preflight_never_sends_write(self):
        def mutate(response):
            response["result"]["plugin_version"] = "0.1.0"
        peer = await self.peer(mutate=mutate)
        await self.failure("INVALID_MESSAGE")
        self.assertEqual([request["operation"] for request in peer.requests], ["godot_get_editor_state"])
        self.assertEqual(peer.applied_writes, 0)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_late_replay_rejection_keeps_tombstone_until_ordered_read(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await peer.socket.send(encode(writer_response(peer.requests[1], self.credential,
                                                       code="WRITE_REPLAY_REJECTED")))
        await asyncio.sleep(0.01)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)

    async def test_genuine_late_success_reply_settles_original_write(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await peer.socket.send(encode(writer_response(peer.requests[1], self.credential)))
        async with asyncio.timeout(1):
            while self.bridge._unresolved_write is not None:
                await asyncio.sleep(0.005)
        self.assertEqual(peer.applied_writes, 1)

    async def test_old_writer_id_on_replacement_connection_cannot_settle(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        old_request = peer.requests[1]
        await peer.socket.close()
        replacement = await self.peer()
        await replacement.socket.send(encode(writer_response(old_request, self.credential)))
        await asyncio.sleep(0.01)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_different_editor_session_cannot_prove_old_peer_replacement(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await peer.socket.close()
        await self.peer(session_id="different-editor-instance")
        data, _ = await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(data["editor_session_id"], "different-editor-instance")
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")

    async def test_mcp_response_failure_reinstates_admission_fence_until_read(self):
        peer = await self.peer()
        def serialization_fault(payload):
            if payload["ok"]:
                raise BridgeError("RESPONSE_TOO_LARGE")
            return tool_result(payload)
        with patch("modules.godot.tools.tool_result", serialization_fault):
            result = await call_bridge(self.bridge, WRITE_OPERATION)
        self.assertEqual(result.structured_content["error"]["code"], "WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_fresh_python_writer_barrier_after_restart_keeps_editor_ledger(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        ids = set(peer.write_ids)
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.15), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)
        peer.port = self.bridge.port
        peer.ignore_write_reply = False
        previous = len(peer.requests)
        await peer.__aenter__()
        await self.failure("LAB_ALREADY_CREATED")
        self.assertEqual([request["operation"] for request in peer.requests[previous:]],
                         ["godot_get_editor_state", WRITE_OPERATION])
        self.assertTrue(ids <= peer.write_ids)
        self.assertEqual(peer.applied_writes, 1)

    async def test_editor_replay_and_capacity_errors_never_apply_again(self):
        peer = await self.peer()
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, "b" * 32,
                                                                        "c" * 32, "b" * 32]):
            await self.bridge.request(WRITE_OPERATION, {})
            await self.failure("WRITE_REPLAY_REJECTED")
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        peer.created = False  # Simulate an explicit user Undo; old ID stays seen.
        peer.write_ids.update(f"{index:032x}" for index in range(127))
        await self.failure("SESSION_WRITE_LIMIT")
        self.assertEqual(peer.applied_writes, 1)

    async def test_editor_fault_latch_survives_python_transport_recovery(self):
        peer = await self.peer()
        peer.write_faulted = True
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await self.bridge.request("godot_get_editor_state", {})
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(peer.applied_writes, 0)


class RigLabMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_writer_output_schema_rejects_unapproved_counts_and_paths(self):
        credential = disposable_credential()
        server = create_server(Config(), credential, port=0)
        listing = await server.list_tools()
        tool = next(tool for tool in listing if tool.name == WRITE_OPERATION)
        self.assertFalse(tool.annotations.read_only_hint)
        self.assertFalse(tool.annotations.idempotent_hint)
        self.assertFalse(tool.annotations.destructive_hint)
        self.assertFalse(tool.annotations.open_world_hint)
        validator = Draft202012Validator(tool.output_schema)
        payload = envelope(rig_lab_result(credential), elapsed_ms=0.1)
        validator.validate(payload)
        validator.validate(envelope(error=BridgeError("WRITE_OUTCOME_UNKNOWN")))
        for field, value in (("created_node_count", 8), ("auto_saved", True), ("node_properties", {})):
            data = deepcopy(payload)
            data["result"][field] = value
            with self.assertRaises(ValidationError):
                validator.validate(data)

    async def test_writer_input_is_empty_before_sdk_coercion(self):
        server = create_server(Config(), disposable_credential(), port=0)
        for value in (None, [], False, {"scene_path": "res://other.tscn"}, {"script": "anything"}):
            result = await server.call_tool(WRITE_OPERATION, value)
            self.assertEqual(result.structured_content["error"]["code"], "INVALID_REQUEST")

    async def test_postdispatch_serialization_failure_is_sanitized_unknown(self):
        credential = disposable_credential()
        class Bridge:
            async def request(self, operation, params):
                return rig_lab_result(credential), 0.1
            def retain_unknown_write(self):
                pass
        def serialization_fault(payload):
            if payload["ok"]:
                raise BridgeError("RESPONSE_TOO_LARGE")
            return tool_result(payload)
        with patch("modules.godot.tools.tool_result", serialization_fault):
            result = await call_bridge(Bridge(), WRITE_OPERATION)
        self.assertEqual(result.structured_content["error"]["code"], "WRITE_OUTCOME_UNKNOWN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
