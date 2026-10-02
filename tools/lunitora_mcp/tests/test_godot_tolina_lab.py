"""Closed v0.4 contracts and all-four-writer settlement/correlation regressions.

Native fixtures separately prove editor/resource behavior. This authenticated
FIFO test peer proves the Python transport never retries or invents settlement.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError
from mcp import Client
from pydantic import TypeAdapter

from core.godot_server import create_server
from modules.godot.bridge import GodotBridge
from modules.godot.config import Config, HOST
from modules.godot.protocol import (
    ANIMATION_WRITE_OPERATION, BRIDGE_VERSION, BridgeError, OPERATIONS,
    READ_OPERATIONS, TOLINA_BLINK_WRITE_OPERATION, TOLINA_RIG_WRITE_OPERATION,
    TolinaLabBlinkResult, TolinaRigLabResult, WRITE_ERRORS_BY_OPERATION,
    WRITE_OPERATION, WRITE_OPERATIONS, encode, envelope, error_info,
    validate_response, validate_result,
)
from modules.godot.tools import call_bridge, tool_result
from tests.fake_godot_client import (
    FakeGodotClient, LAB_SCENE, ROOT_NODE, TOLINA_LAB_SCENE, disposable_credential,
    result_for, tolina_lab_blink_result, tolina_rig_lab_result,
)

NEW_OPERATIONS = (TOLINA_RIG_WRITE_OPERATION, TOLINA_BLINK_WRITE_OPERATION)
ALL_WRITES = (WRITE_OPERATION, ANIMATION_WRITE_OPERATION, *NEW_OPERATIONS)


def terminal(request, credential, *, operation=None, code=None):
    operation = operation or request["operation"]
    data = result_for(operation, credential, TOLINA_LAB_SCENE, [ROOT_NODE], [])
    data["editor_session_id"] = request["editor_session_id"]
    return {"type": "response", "protocol_version": 1, "id": request["id"],
            "operation": operation, "editor_session_id": request["editor_session_id"],
            "ok": code is None, "result": data if code is None else None,
            "error": error_info(code) if code is not None else None}


class TolinaContractTests(unittest.TestCase):
    def setUp(self):
        self.credential = disposable_credential()

    def test_four_fixed_writes_protocol_one_version_four(self):
        self.assertEqual(WRITE_OPERATIONS, frozenset(ALL_WRITES))
        self.assertEqual(len(OPERATIONS), 7)
        self.assertEqual(BRIDGE_VERSION, "0.4.0")
        self.assertEqual(envelope(tolina_rig_lab_result(self.credential), elapsed_ms=0)["protocol_version"], 1)

    def test_rig_exact_closed_eleven_field_contract(self):
        data = tolina_rig_lab_result(self.credential)
        self.assertEqual(len(data), 11)
        validate_result(TOLINA_RIG_WRITE_OPERATION, data)
        adapter = TypeAdapter(TolinaRigLabResult)
        adapter.validate_python(envelope(data, elapsed_ms=0.1))
        for field, value in (("scene_path", LAB_SCENE["path"]), ("root_name", "TotolinaRigLab"),
                             ("created_root", "TotolinaRigV2"), ("created_node_count", 7),
                             ("created_node_count", True), ("undo_actions_added", 2),
                             ("undo_actions_added", True), ("undo_action_name", "Other"),
                             ("save_state", "saved_clean"), ("auto_saved", True),
                             ("read_only", True), ("textures", [])):
            with self.subTest(field=field, value=value):
                changed = dict(data, **{field: value})
                with self.assertRaises(BridgeError):
                    validate_result(TOLINA_RIG_WRITE_OPERATION, changed)
                with self.assertRaises(ValueError):
                    adapter.validate_python(envelope(changed, elapsed_ms=0.1))

    def test_blink_exact_closed_sixteen_field_contract(self):
        data = tolina_lab_blink_result(self.credential)
        self.assertEqual(len(data), 16)
        validate_result(TOLINA_BLINK_WRITE_OPERATION, data)
        adapter = TypeAdapter(TolinaLabBlinkResult)
        adapter.validate_python(envelope(data, elapsed_ms=0.1))
        for field, value in (("scene_path", LAB_SCENE["path"]), ("root_name", "TotolinaRigLab"),
                             ("animation_player_path", "TotolinaRigV2/AnimationPlayer"),
                             ("library_name", "other"), ("animation_name", "bend_tip"),
                             ("animation_key", "other/blink"), ("length_seconds", 0.25),
                             ("length_seconds", True), ("length_seconds", float("nan")),
                             ("track_count", 1), ("track_count", True), ("key_count", 3),
                             ("undo_actions_added", 2), ("undo_actions_added", True),
                             ("undo_action_name", "Other"), ("save_state", "saved_clean"),
                             ("auto_saved", True), ("read_only", True), ("tracks", [])):
            with self.subTest(field=field, value=value):
                changed = dict(data, **{field: value})
                with self.assertRaises(BridgeError):
                    validate_result(TOLINA_BLINK_WRITE_OPERATION, changed)
                with self.assertRaises(ValueError):
                    adapter.validate_python(envelope(changed, elapsed_ms=0.1))

    def test_every_operation_has_closed_correlated_error_set(self):
        request = {"id": "a" * 32, "editor_session_id": "disposable-editor-session"}
        for operation in NEW_OPERATIONS:
            request["operation"] = operation
            for code in WRITE_ERRORS_BY_OPERATION[operation]:
                value = terminal(request, self.credential, code=code)
                validate_response(value)
                del value["editor_session_id"]
                with self.assertRaises(BridgeError):
                    validate_response(value)
            value = terminal(request, self.credential)
            validate_response(value)
            value["result"]["editor_session_id"] = "other-session"
            with self.assertRaises(BridgeError):
                validate_response(value)
        for operation, code in ((TOLINA_RIG_WRITE_OPERATION, "TOLINA_BLINK_BUILD_FAILED"),
                                (TOLINA_BLINK_WRITE_OPERATION, "TOLINA_RIG_BUILD_FAILED"),
                                (WRITE_OPERATION, "TOLINA_SPEC_INVALID"),
                                (ANIMATION_WRITE_OPERATION, "TOLINA_ASSET_INVALID"),
                                (TOLINA_RIG_WRITE_OPERATION, "INSPECTION_FAILED")):
            request["operation"] = operation
            with self.subTest(operation=operation, code=code), self.assertRaises(BridgeError):
                validate_response(terminal(request, self.credential, code=code))

    def test_shared_error_codes_keep_legacy_text_and_use_exact_new_fixture_names(self):
        self.assertIn("TotolinaRigV2", error_info("LAB_ALREADY_CREATED")["message"])
        self.assertIn("bend_tip", error_info("LAB_ANIMATION_ALREADY_CREATED", operation=ANIMATION_WRITE_OPERATION)["message"])
        self.assertIn("TolinaRig subtree", error_info("LAB_ALREADY_CREATED", operation=TOLINA_RIG_WRITE_OPERATION)["message"])
        self.assertIn("blink animation", error_info("LAB_ANIMATION_ALREADY_CREATED", operation=TOLINA_BLINK_WRITE_OPERATION)["message"])
        self.assertEqual(error_info("WRITE_OUTCOME_UNKNOWN", operation=TOLINA_RIG_WRITE_OPERATION),
                         error_info("WRITE_OUTCOME_UNKNOWN"))


class TolinaTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = disposable_credential()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.12), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)

    async def peer(self, **kwargs):
        scene = kwargs.pop("scene", TOLINA_LAB_SCENE)
        peer = await FakeGodotClient(self.credential, self.bridge.port, scene=scene,
                                     nodes=[ROOT_NODE], **kwargs).__aenter__()
        self.addAsyncCleanup(peer.__aexit__, None, None, None)
        return peer

    async def failure(self, operation, code, action=None):
        with self.assertRaises(BridgeError) as raised:
            await (action if action is not None else self.bridge.request(operation, {}))
        self.assertEqual(raised.exception.code, code)

    async def received(self, peer, count):
        async with asyncio.timeout(2):
            while len(peer.requests) < count:
                peer.request_received.clear()
                await peer.request_received.wait()

    async def dropped(self):
        async with asyncio.timeout(2):
            while self.bridge._connection is not None:
                await asyncio.sleep(0.005)

    async def block_all(self, code="WRITE_BUSY"):
        for operation in ALL_WRITES:
            await self.failure(operation, code)

    async def test_new_rig_then_blink_fresh_barriers_no_retry(self):
        peer = await self.peer()
        for operation in NEW_OPERATIONS:
            result, _ = await self.bridge.request(operation, {})
            validate_result(operation, result)
        self.assertEqual(peer.applied_writes, 2)
        self.assertEqual([request["operation"] for request in peer.requests],
                         ["godot_get_editor_state", TOLINA_RIG_WRITE_OPERATION,
                          "godot_get_editor_state", TOLINA_BLINK_WRITE_OPERATION])
        for request in peer.requests:
            if request["operation"] in WRITE_OPERATIONS:
                self.assertEqual(request["editor_session_id"], peer.session_id)
                self.assertEqual(request["params"], {})

    async def test_blink_missing_rig_rejection_never_creates_rig(self):
        peer = await self.peer()
        await self.failure(TOLINA_BLINK_WRITE_OPERATION, "LAB_RIG_REQUIRED")
        self.assertFalse(peer.tolina_created)
        self.assertFalse(peer.blink_created)
        self.assertEqual(peer.applied_writes, 0)
        self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(len(peer.requests), 2)

    async def test_cross_lab_and_production_requests_reject_before_peer_mutation(self):
        peer = await self.peer(scene=LAB_SCENE, has_rig=True)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "LAB_SCENE_REQUIRED")
        peer.scene = deepcopy(TOLINA_LAB_SCENE)
        for operation in (WRITE_OPERATION, ANIMATION_WRITE_OPERATION):
            await self.failure(operation, "LAB_SCENE_REQUIRED")
        peer.scene["path"] = "res://scenes/presentation/totolina_operator.tscn"
        for operation in ALL_WRITES:
            await self.failure(operation, "LAB_SCENE_REQUIRED")
        self.assertEqual(peer.applied_writes, 0)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_safe_errors_settle_once_without_retry(self):
        peer = await self.peer()
        for operation in NEW_OPERATIONS:
            peer.tolina_created = operation == TOLINA_BLINK_WRITE_OPERATION
            codes = ("TOLINA_SPEC_INVALID", "TOLINA_ASSET_INVALID",
                     "TOLINA_RIG_BUILD_FAILED" if operation == TOLINA_RIG_WRITE_OPERATION else "TOLINA_BLINK_BUILD_FAILED")
            if operation == TOLINA_BLINK_WRITE_OPERATION:
                codes += ("LAB_RIG_MISMATCH", "LAB_ANIMATION_EDITOR_BUSY", "LAB_ANIMATION_EDITOR_SETTLING",
                          "LAB_ANIMATION_CONFLICT")
            for code in codes:
                peer.tolina_rig_error = code if operation == TOLINA_RIG_WRITE_OPERATION else None
                peer.blink_error = code if operation == TOLINA_BLINK_WRITE_OPERATION else None
                before = len(peer.requests)
                await self.failure(operation, code)
                self.assertEqual(len(peer.requests) - before, 2)
                self.assertEqual(peer.applied_writes, 0)
                self.assertIsNone(self.bridge._unresolved_write)

    async def test_duplicate_creation_reports_no_second_mutation(self):
        peer = await self.peer()
        for operation, code in ((TOLINA_RIG_WRITE_OPERATION, "LAB_ALREADY_CREATED"),
                                (TOLINA_BLINK_WRITE_OPERATION, "LAB_ANIMATION_ALREADY_CREATED")):
            await self.bridge.request(operation, {})
            count = peer.applied_writes
            await self.failure(operation, code)
            self.assertEqual(peer.applied_writes, count)

    async def test_public_errors_name_only_the_requested_fixture(self):
        await self.peer(has_tolina_rig=True)
        result = await call_bridge(self.bridge, TOLINA_RIG_WRITE_OPERATION)
        self.assertEqual(result.structured_content["error"]["code"], "LAB_ALREADY_CREATED")
        self.assertIn("TolinaRig subtree", result.structured_content["error"]["message"])
        self.assertNotIn("TotolinaRigV2", result.structured_content["error"]["message"])

    async def test_shared_busy_guard_all_four_during_each_new_preflight(self):
        peer = await self.peer(ignore=True)
        for operation in NEW_OPERATIONS:
            count = len(peer.requests)
            action = asyncio.create_task(self.bridge.request(operation, {}))
            await self.received(peer, count + 1)
            await self.block_all()
            self.assertEqual(len(peer.requests), count + 1)
            action.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await action
            self.assertIsNone(self.bridge._unresolved_write)

    async def test_lost_response_each_new_operation_blocks_all_until_ordered_read(self):
        peer = await self.peer(ignore_write_reply=True)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            count = len(peer.requests)
            await self.block_all()
            self.assertEqual(len(peer.requests), count)
            await self.bridge.request("godot_get_editor_state", {})
            self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 2)

    async def test_delayed_write_fifo_read_waits_until_applied(self):
        peer = await self.peer(ignore_write_reply=True, write_delay=0.17)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            await self.block_all()
            state, _ = await self.bridge.request("godot_get_editor_state", {})
            self.assertEqual(state["scene"]["save_state"], "saved_dirty")
            self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 2)

    async def test_every_other_operation_reply_cannot_settle_new_write(self):
        peer = await self.peer(ignore_write_reply=True)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            request = peer.requests[-1]
            for other in set(ALL_WRITES) - {operation}:
                await peer.socket.send(encode(terminal(request, self.credential, operation=other)))
            await asyncio.sleep(0.01)
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            await self.block_all()
            await peer.socket.send(encode(terminal(request, self.credential)))
            async with asyncio.timeout(1):
                while self.bridge._unresolved_write is not None:
                    await asyncio.sleep(0.005)
        self.assertEqual(peer.applied_writes, 2)

    async def test_new_write_replay_rejection_never_settles_original(self):
        peer = await self.peer(ignore_write_reply=True)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            await peer.socket.send(encode(terminal(peer.requests[-1], self.credential,
                                                  code="WRITE_REPLAY_REJECTED")))
            await asyncio.sleep(0.01)
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            await self.block_all()
            await self.bridge.request("godot_ping", {})
            self.assertIsNone(self.bridge._unresolved_write)

    async def test_all_four_operations_share_replay_id_ledger(self):
        peer = await self.peer()
        write_id = "b" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, write_id]):
            await self.bridge.request(TOLINA_RIG_WRITE_OPERATION, {})
        for index, operation in enumerate(ALL_WRITES):
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0x100 + index:032x}", write_id]):
                await self.failure(operation, "WRITE_REPLAY_REJECTED")
            self.assertIsNotNone(self.bridge._unresolved_write)
            await self.bridge.request("godot_ping", {})
        self.assertEqual(len(peer.write_ids), 1)
        self.assertEqual(peer.applied_writes, 1)

    async def test_mixed_four_operation_capacity_is_one_128_entry_limit(self):
        peer = await self.peer(has_tolina_rig=True, blink_error="LAB_ANIMATION_EDITOR_BUSY")
        for index in range(128):
            operation = ALL_WRITES[index % 4]
            code = ("LAB_SCENE_REQUIRED" if operation in {WRITE_OPERATION, ANIMATION_WRITE_OPERATION}
                    else "LAB_ALREADY_CREATED" if operation == TOLINA_RIG_WRITE_OPERATION
                    else "LAB_ANIMATION_EDITOR_BUSY")
            await self.failure(operation, code)
        self.assertEqual(len(peer.write_ids), 128)
        await self.block_all("SESSION_WRITE_LIMIT")
        self.assertEqual(len(peer.write_ids), 128)
        self.assertEqual(peer.applied_writes, 0)

    async def test_fault_in_each_new_operation_keeps_editor_latch_for_all_after_reads(self):
        peer = await self.peer()
        for operation in NEW_OPERATIONS:
            peer.write_faulted = True
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            await self.bridge.request("godot_get_editor_state", {})
            await self.block_all("WRITE_OUTCOME_UNKNOWN")
            self.assertEqual(peer.applied_writes, 0)
        self.assertEqual(len(peer.write_ids), 0)

    async def test_reconnect_retains_new_write_ledger_and_requires_fresh_read(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure(TOLINA_RIG_WRITE_OPERATION, "WRITE_OUTCOME_UNKNOWN")
        await peer.socket.close()
        await self.dropped()
        await peer.__aenter__()
        await self.block_all()
        await self.bridge.request("godot_get_editor_state", {})
        peer.ignore_write_reply = False
        await self.failure(TOLINA_RIG_WRITE_OPERATION, "LAB_ALREADY_CREATED")
        await self.bridge.request(TOLINA_BLINK_WRITE_OPERATION, {})
        self.assertEqual(peer.applied_writes, 2)

    async def test_python_restart_preserves_new_request_id_across_all_operations(self):
        peer = await self.peer()
        write_id = "b" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, write_id]):
            await self.bridge.request(TOLINA_RIG_WRITE_OPERATION, {})
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.12), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)
        peer.port = self.bridge.port
        await peer.__aenter__()
        for index, operation in enumerate(ALL_WRITES):
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0x200 + index:032x}", write_id]):
                await self.failure(operation, "WRITE_REPLAY_REJECTED")
            await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(len(peer.write_ids), 1)
        self.assertEqual(peer.applied_writes, 1)

    async def test_rollover_cannot_settle_old_new_writer_unknown(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure(TOLINA_RIG_WRITE_OPERATION, "WRITE_OUTCOME_UNKNOWN")
        await peer.socket.close()
        await self.dropped()
        replacement = await self.peer(session_id="new-editor-session")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.block_all()
        self.assertEqual(replacement.applied_writes, 0)

    async def test_new_write_on_new_editor_session_has_fresh_ledger(self):
        peer = await self.peer()
        write_id = "b" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, write_id]):
            await self.bridge.request(TOLINA_RIG_WRITE_OPERATION, {})
        await peer.socket.close()
        await self.dropped()
        replacement = await self.peer(session_id="new-editor-session")
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["c" * 32, write_id]):
            value, _ = await self.bridge.request(TOLINA_RIG_WRITE_OPERATION, {})
        self.assertEqual(value["editor_session_id"], "new-editor-session")
        self.assertEqual(replacement.write_ids, {write_id})
        self.assertEqual(replacement.applied_writes, 1)

    async def test_cancellation_after_each_new_dispatch_is_unknown_without_retry(self):
        peer = await self.peer(ignore_write_reply=True)
        for operation in NEW_OPERATIONS:
            count = len(peer.requests)
            action = asyncio.create_task(self.bridge.request(operation, {}))
            await self.received(peer, count + 2)
            action.cancel()
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN", action)
            self.assertEqual(len(peer.requests), count + 2)
            await self.block_all()
            await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(peer.applied_writes, 2)

    async def test_incomplete_new_write_send_retires_socket_until_replacement_read(self):
        for operation in NEW_OPERATIONS:
            peer = await self.peer(has_tolina_rig=operation == TOLINA_BLINK_WRITE_OPERATION)
            connection = self.bridge._connection
            original_send = connection.send
            async def interrupted(message):
                if f'"operation":"{operation}"' in message:
                    await asyncio.Event().wait()
                await original_send(message)
            with patch.object(connection, "send", interrupted):
                await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            self.assertIsNone(self.bridge._connection)
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            await self.block_all()
            await peer.socket.wait_closed()
            await peer.__aenter__()
            await self.bridge.request("godot_get_editor_state", {})
            self.assertIsNone(self.bridge._unresolved_write)
            self.assertEqual(peer.applied_writes, 0)
            await peer.socket.close()
            await self.dropped()

    async def test_old_new_writer_reply_from_replacement_socket_cannot_settle(self):
        peer = await self.peer(ignore_write_reply=True)
        for operation in NEW_OPERATIONS:
            await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
            request = peer.requests[-1]
            await peer.socket.close()
            await self.dropped()
            await peer.__aenter__()
            await peer.socket.send(encode(terminal(request, self.credential)))
            await asyncio.sleep(0.01)
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            await self.block_all()
            await self.bridge.request("godot_get_editor_state", {})
            self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 2)

    async def test_serialization_failure_after_each_new_dispatch_is_unknown(self):
        peer = await self.peer()
        def fail_success(payload):
            if payload["ok"]:
                raise BridgeError("RESPONSE_TOO_LARGE")
            return tool_result(payload)
        for operation in NEW_OPERATIONS:
            with patch("modules.godot.tools.tool_result", fail_success):
                response = await call_bridge(self.bridge, operation)
            self.assertEqual(response.structured_content["error"]["code"], "WRITE_OUTCOME_UNKNOWN")
            self.assertEqual(self.bridge._unresolved_write.operation, operation)
            await self.block_all()
            await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(peer.applied_writes, 2)

    async def test_wrong_session_project_or_error_contract_after_new_dispatch_is_unknown(self):
        for operation in NEW_OPERATIONS:
            for kind in ("session", "project", "error"):
                def mutate(value):
                    if value["operation"] != operation:
                        return
                    if kind == "session":
                        value["editor_session_id"] = "other-editor"
                    elif kind == "project":
                        value["result"]["project_path"] = "d:/different-project"
                    else:
                        value.update(ok=False, result=None, error=error_info("RIG_LAB_BUILD_FAILED"))
                peer = await self.peer(has_tolina_rig=operation == TOLINA_BLINK_WRITE_OPERATION,
                                       mutate=mutate)
                await self.failure(operation, "WRITE_OUTCOME_UNKNOWN")
                self.assertIsNotNone(self.bridge._unresolved_write)
                self.assertEqual(peer.applied_writes, 1)
                await peer.socket.wait_closed()
                await self.dropped()
                replacement = await self.peer()
                await self.bridge.request("godot_get_editor_state", {})
                self.assertIsNone(self.bridge._unresolved_write)
                await replacement.socket.close()
                await self.dropped()

    async def test_stale_v03_read_never_dispatches_any_writer(self):
        def mutate(value):
            if value["operation"] == "godot_get_editor_state":
                value["result"]["plugin_version"] = "0.3.0"
        for operation in ALL_WRITES:
            peer = await self.peer(mutate=mutate)
            await self.failure(operation, "INVALID_MESSAGE")
            await peer.socket.wait_closed()
            await self.dropped()
            self.assertEqual([request["operation"] for request in peer.requests], ["godot_get_editor_state"])
            self.assertEqual(peer.applied_writes, 0)


class TolinaMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_new_public_schemas_are_closed_and_fixed(self):
        credential = disposable_credential()
        server = create_server(Config(), credential, port=0)
        listing = await server.list_tools()
        self.assertEqual({tool.name for tool in listing}, OPERATIONS)
        for operation in NEW_OPERATIONS:
            tool = next(tool for tool in listing if tool.name == operation)
            self.assertEqual(tool.input_schema, {"type": "object", "properties": {},
                                               "additionalProperties": False, "maxProperties": 0})
            self.assertFalse(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.idempotent_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            validator = Draft202012Validator(tool.output_schema)
            value = envelope(result_for(operation, credential, TOLINA_LAB_SCENE, [], []), elapsed_ms=0.1)
            validator.validate(value)
            for field, content in (("extra", {}), ("scene_path", "res://production.tscn"),
                                   ("auto_saved", True), ("undo_actions_added", 2)):
                changed = deepcopy(value)
                changed["result"][field] = content
                with self.assertRaises(ValidationError):
                    validator.validate(changed)

    async def test_new_public_inputs_never_accept_manifest_path_or_geometry(self):
        server = create_server(Config(), disposable_credential(), port=0)
        for operation in NEW_OPERATIONS:
            for data in (None, [], False, {"spec": "other.json"}, {"path": "Other:modulate:a"},
                         {"keys": []}, {"texture": "other.png"}, {"animation_name": "other"}):
                response = await server.call_tool(operation, data)
                self.assertEqual(response.structured_content["error"]["code"], "INVALID_REQUEST")

    async def test_sdk_calls_real_new_tool_functions_with_disposable_auth(self):
        credential = disposable_credential()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((HOST, 0))
            port = probe.getsockname()[1]
        server = create_server(Config(), credential, port=port)
        async with Client(server) as client:
            async with FakeGodotClient(credential, port, scene=TOLINA_LAB_SCENE,
                                       nodes=[ROOT_NODE]) as peer:
                for operation in (*READ_OPERATIONS, *NEW_OPERATIONS):
                    response = await client.call_tool(operation, {})
                    self.assertFalse(response.is_error)
                    validate_result(operation, response.structured_content["result"])
                self.assertEqual(peer.applied_writes, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
