"""Fixed animation contracts and cross-operation admission on the shared bridge."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError
from pydantic import TypeAdapter

from core.godot_server import create_server
from modules.godot.bridge import GodotBridge, UnresolvedWrite
from modules.godot.config import Config
from modules.godot.protocol import (
    ANIMATION_WRITE_OPERATION, ANIMATION_WRITE_ERRORS, BridgeError, OPERATIONS,
    READ_OPERATIONS, RigLabAnimationResult, WRITE_OPERATION, WRITE_OPERATIONS,
    encode, envelope, error_info, validate_response, validate_result,
)
from modules.godot.tools import call_bridge, tool_result
from tests.fake_godot_client import (
    FakeGodotClient, LAB_SCENE, ROOT_NODE, disposable_credential, result_for,
    rig_lab_animation_result, rig_lab_result,
)


def terminal(request, credential, *, operation=None, code=None):
    operation = operation or request["operation"]
    data = (rig_lab_animation_result(credential) if operation == ANIMATION_WRITE_OPERATION
            else rig_lab_result(credential))
    data["editor_session_id"] = request["editor_session_id"]
    return {"type": "response", "protocol_version": 1, "id": request["id"],
            "operation": operation, "editor_session_id": request["editor_session_id"],
            "ok": code is None, "result": data if code is None else None,
            "error": error_info(code) if code is not None else None}


class AnimationContractTests(unittest.TestCase):
    def setUp(self):
        self.credential = disposable_credential()
        self.data = rig_lab_animation_result(self.credential)

    def test_exact_sixteen_field_result_and_closed_schema(self):
        self.assertEqual(len(self.data), 16)
        validate_result(ANIMATION_WRITE_OPERATION, self.data)
        TypeAdapter(RigLabAnimationResult).validate_python(envelope(self.data, elapsed_ms=0.1))
        for field, value in (
            ("scene_path", "res://production.tscn"), ("root_name", "Other"),
            ("animation_player_path", "Other/AnimationPlayer"), ("library_name", "other"),
            ("animation_name", "RESET"), ("animation_key", "other/bend_tip"),
            ("length_seconds", True), ("length_seconds", 2.0), ("length_seconds", float("nan")),
            ("track_count", True), ("track_count", 2), ("key_count", 4),
            ("undo_actions_added", True), ("undo_actions_added", 2),
            ("undo_action_name", "Other"), ("save_state", "saved_clean"),
            ("auto_saved", True), ("read_only", True), ("arbitrary_tracks", []),
        ):
            with self.subTest(field=field, value=value):
                changed = dict(self.data, **{field: value})
                with self.assertRaises(BridgeError):
                    validate_result(ANIMATION_WRITE_OPERATION, changed)
                with self.assertRaises(ValueError):
                    TypeAdapter(RigLabAnimationResult).validate_python(envelope(changed, elapsed_ms=0.1))

    def test_operation_specific_failure_contracts_are_closed(self):
        request = {"operation": ANIMATION_WRITE_OPERATION, "id": "a" * 32,
                   "editor_session_id": "disposable-editor-session"}
        for code in ANIMATION_WRITE_ERRORS:
            validate_response(terminal(request, self.credential, code=code))
        for operation, code in ((ANIMATION_WRITE_OPERATION, "RIG_LAB_BUILD_FAILED"),
                                (ANIMATION_WRITE_OPERATION, "LAB_ALREADY_CREATED"),
                                (WRITE_OPERATION, "LAB_ANIMATION_EDITOR_BUSY"),
                                (WRITE_OPERATION, "RIG_LAB_ANIMATION_BUILD_FAILED"),
                                (ANIMATION_WRITE_OPERATION, "INSPECTION_FAILED")):
            with self.subTest(operation=operation, code=code), self.assertRaises(BridgeError):
                validate_response(terminal(request, self.credential, operation=operation, code=code))

    def test_writer_session_is_required_and_matches_result(self):
        request = {"operation": ANIMATION_WRITE_OPERATION, "id": "a" * 32,
                   "editor_session_id": "disposable-editor-session"}
        for code in (None, "LAB_ANIMATION_EDITOR_BUSY", "WRITE_OUTCOME_UNKNOWN"):
            value = terminal(request, self.credential, code=code)
            validate_response(value)
            del value["editor_session_id"]
            with self.assertRaises(BridgeError):
                validate_response(value)
        value = terminal(request, self.credential)
        value["result"]["editor_session_id"] = "another-session"
        with self.assertRaises(BridgeError):
            validate_response(value)

    def test_malformed_operation_types_are_sanitized(self):
        request = {"operation": ANIMATION_WRITE_OPERATION, "id": "a" * 32,
                   "editor_session_id": "disposable-editor-session"}
        for operation in ([], {}, None, False):
            value = terminal(request, self.credential)
            value["operation"] = operation
            with self.assertRaises(BridgeError):
                validate_response(value)

    def test_unresolved_record_remains_compatible_and_operation_aware(self):
        legacy = UnresolvedWrite("a" * 32, None, "session")
        animation = UnresolvedWrite("b" * 32, None, "session", operation=ANIMATION_WRITE_OPERATION)
        self.assertEqual(legacy.operation, WRITE_OPERATION)
        self.assertEqual(animation.operation, ANIMATION_WRITE_OPERATION)


class AnimationTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = disposable_credential()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.15), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)

    async def peer(self, **kwargs):
        kwargs.setdefault("has_rig", True)
        peer = await FakeGodotClient(self.credential, self.bridge.port, scene=LAB_SCENE,
                                     nodes=[ROOT_NODE], **kwargs).__aenter__()
        self.addAsyncCleanup(peer.__aexit__, None, None, None)
        return peer

    async def failure(self, code, operation=ANIMATION_WRITE_OPERATION, action=None):
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

    async def test_animation_never_implicitly_creates_missing_rig(self):
        peer = await self.peer(has_rig=False)
        await self.failure("LAB_RIG_REQUIRED")
        self.assertFalse(peer.created)
        self.assertEqual(peer.applied_writes, 0)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_both_writers_use_fresh_session_correlated_barriers(self):
        peer = await self.peer(has_rig=False)
        await self.bridge.request(WRITE_OPERATION, {})
        data, _ = await self.bridge.request(ANIMATION_WRITE_OPERATION, {})
        self.assertEqual(data, rig_lab_animation_result(self.credential))
        self.assertEqual([request["operation"] for request in peer.requests],
                         ["godot_get_editor_state", WRITE_OPERATION,
                          "godot_get_editor_state", ANIMATION_WRITE_OPERATION])
        for request in peer.requests:
            fields = {"type", "protocol_version", "id", "operation", "params"}
            if request["operation"] in WRITE_OPERATIONS:
                fields.add("editor_session_id")
                self.assertEqual(request["editor_session_id"], peer.session_id)
            self.assertEqual(set(request), fields)
        self.assertEqual(peer.applied_writes, 2)

    async def test_animation_safe_rejections_never_retry_or_leave_tombstone(self):
        peer = await self.peer()
        for code in ("LAB_RIG_MISMATCH", "LAB_ANIMATION_CONFLICT", "LAB_ANIMATION_EDITOR_BUSY",
                     "LAB_ANIMATION_EDITOR_SETTLING", "RIG_LAB_ANIMATION_BUILD_FAILED"):
            peer.animation_error = code
            before = len(peer.requests)
            await self.failure(code)
            self.assertEqual(len(peer.requests) - before, 2)
            self.assertEqual(peer.applied_writes, 0)
            self.assertFalse(peer.animation_created)
            self.assertIsNone(self.bridge._unresolved_write)
        peer.animation_error = None
        await self.bridge.request(ANIMATION_WRITE_OPERATION, {})
        await self.failure("LAB_ANIMATION_ALREADY_CREATED")
        self.assertEqual(peer.applied_writes, 1)

    async def test_active_preflight_blocks_either_writer_without_queueing(self):
        peer = await self.peer(ignore=True)
        for operation in WRITE_OPERATIONS:
            first = asyncio.create_task(self.bridge.request(operation, {}))
            await self.received(peer, len(peer.requests) + 1)
            for second in WRITE_OPERATIONS:
                await self.failure("WRITE_BUSY", second)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            self.assertFalse(self.bridge._write_active)
            self.assertIsNone(self.bridge._unresolved_write)

    async def test_lost_animation_reply_blocks_both_until_explicit_ordered_read(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(self.bridge._unresolved_write.operation, ANIMATION_WRITE_OPERATION)
        before = len(peer.requests)
        for operation in WRITE_OPERATIONS:
            await self.failure("WRITE_BUSY", operation)
        self.assertEqual(len(peer.requests), before)
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        peer.ignore_write_reply = False
        await self.failure("LAB_ANIMATION_ALREADY_CREATED")
        self.assertEqual(peer.applied_writes, 1)

    async def test_delayed_animation_settlement_waits_for_native_fifo_model(self):
        peer = await self.peer(write_delay=0.22, ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        state, _ = await self.bridge.request("godot_get_editor_state", {})
        self.assertTrue(state["scene"]["dirty_changes"])
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_wrong_operation_pending_and_late_replies_never_settle(self):
        peer = await self.peer(ignore_write_reply=True)
        action = asyncio.create_task(self.bridge.request(ANIMATION_WRITE_OPERATION, {}))
        await self.received(peer, 2)
        request = peer.requests[-1]
        await peer.socket.send(encode(terminal(request, self.credential, operation=WRITE_OPERATION)))
        await self.failure("WRITE_OUTCOME_UNKNOWN", action=action)
        await peer.socket.send(encode(terminal(request, self.credential, operation=WRITE_OPERATION,
                                              code="LAB_ALREADY_CREATED")))
        await asyncio.sleep(0.01)
        self.assertIsNotNone(self.bridge._unresolved_write)
        self.assertEqual(self.bridge._unresolved_write.operation, ANIMATION_WRITE_OPERATION)
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        await peer.socket.send(encode(terminal(request, self.credential)))
        async with asyncio.timeout(1):
            while self.bridge._unresolved_write is not None:
                await asyncio.sleep(0.005)
        self.assertEqual(peer.applied_writes, 1)

    async def test_animation_reply_cannot_settle_rig_tombstone(self):
        peer = await self.peer(has_rig=False, ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN", WRITE_OPERATION)
        await peer.socket.send(encode(terminal(peer.requests[-1], self.credential,
                                              operation=ANIMATION_WRITE_OPERATION)))
        await asyncio.sleep(0.01)
        self.assertEqual(self.bridge._unresolved_write.operation, WRITE_OPERATION)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_cross_operation_replay_uses_one_editor_ledger(self):
        peer = await self.peer()
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, "b" * 32,
                                                                        "c" * 32, "b" * 32]):
            await self.bridge.request(ANIMATION_WRITE_OPERATION, {})
            await self.failure("WRITE_REPLAY_REJECTED", WRITE_OPERATION)
        self.assertEqual(len(peer.write_ids), 1)
        self.assertEqual(peer.applied_writes, 1)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY")
        await self.bridge.request("godot_ping", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_mixed_rejections_share_exactly_one_128_id_capacity(self):
        peer = await self.peer(animation_error="LAB_ANIMATION_EDITOR_BUSY")
        for index in range(128):
            operation = WRITE_OPERATION if index % 2 else ANIMATION_WRITE_OPERATION
            code = "LAB_ALREADY_CREATED" if operation == WRITE_OPERATION else "LAB_ANIMATION_EDITOR_BUSY"
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0x1000 + index:032x}",
                                                                            f"{0x2000 + index:032x}"]):
                await self.failure(code, operation)
        self.assertEqual(len(peer.write_ids), 128)
        for operation in WRITE_OPERATIONS:
            await self.failure("SESSION_WRITE_LIMIT", operation)
        self.assertEqual(len(peer.write_ids), 128)
        self.assertEqual(peer.applied_writes, 0)

    async def test_editor_fault_latch_blocks_both_after_fresh_reads(self):
        peer = await self.peer()
        peer.write_faulted = True
        for operation in WRITE_OPERATIONS:
            await self.failure("WRITE_OUTCOME_UNKNOWN", operation)
            await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(peer.applied_writes, 0)

    async def test_python_restart_keeps_shared_ledger_and_fresh_barrier(self):
        peer = await self.peer()
        write_id = "b" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["a" * 32, write_id]):
            await self.bridge.request(ANIMATION_WRITE_OPERATION, {})
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.15), self.credential, port=0)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)
        peer.port = self.bridge.port
        previous = len(peer.requests)
        await peer.__aenter__()
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["c" * 32, write_id]):
            await self.failure("WRITE_REPLAY_REJECTED", WRITE_OPERATION)
        self.assertEqual([request["operation"] for request in peer.requests[previous:]],
                         ["godot_get_editor_state", WRITE_OPERATION])
        self.assertEqual(peer.applied_writes, 1)

    async def test_new_session_cannot_settle_old_animation_outcome(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await peer.socket.close()
        await self.dropped()
        await self.peer(session_id="new-editor-session")
        state, _ = await self.bridge.request("godot_get_editor_state", {})
        self.assertEqual(state["editor_session_id"], "new-editor-session")
        self.assertIsNotNone(self.bridge._unresolved_write)
        for operation in WRITE_OPERATIONS:
            await self.failure("WRITE_BUSY", operation)

    async def test_animation_response_serialization_retains_operation_aware_fence(self):
        peer = await self.peer()
        def fail_success(payload):
            if payload["ok"]:
                raise BridgeError("RESPONSE_TOO_LARGE")
            return tool_result(payload)
        with patch("modules.godot.tools.tool_result", fail_success):
            response = await call_bridge(self.bridge, ANIMATION_WRITE_OPERATION)
        self.assertEqual(response.structured_content["error"]["code"], "WRITE_OUTCOME_UNKNOWN")
        self.assertEqual(self.bridge._unresolved_write.operation, ANIMATION_WRITE_OPERATION)
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)

    async def test_mismatched_session_after_animation_dispatch_is_unknown(self):
        def mutate(value):
            if value["operation"] == ANIMATION_WRITE_OPERATION:
                value["editor_session_id"] = "other-editor"
        peer = await self.peer(mutate=mutate)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNotNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)

    async def test_wrong_project_animation_result_is_unknown(self):
        def mutate(value):
            if value["operation"] == ANIMATION_WRITE_OPERATION:
                value["result"]["project_path"] = "d:/different-project"
        peer = await self.peer(mutate=mutate)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNotNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)

    async def test_v02_preflight_never_dispatches_either_writer(self):
        def mutate(value):
            if value["operation"] == "godot_get_editor_state":
                value["result"]["plugin_version"] = "0.2.0"
        for operation in WRITE_OPERATIONS:
            peer = await self.peer(mutate=mutate)
            await self.failure("INVALID_MESSAGE", operation)
            await peer.socket.wait_closed()
            await self.dropped()
            self.assertEqual([request["operation"] for request in peer.requests], ["godot_get_editor_state"])
            self.assertEqual(peer.applied_writes, 0)
            self.assertIsNone(self.bridge._unresolved_write)

    async def test_animation_cancellation_after_send_preserves_cross_writer_fence(self):
        peer = await self.peer(ignore_write_reply=True)
        action = asyncio.create_task(self.bridge.request(ANIMATION_WRITE_OPERATION, {}))
        await self.received(peer, 2)
        action.cancel()
        await self.failure("WRITE_OUTCOME_UNKNOWN", action=action)
        for operation in WRITE_OPERATIONS:
            await self.failure("WRITE_BUSY", operation)
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)

    async def test_incomplete_animation_send_retires_socket_until_replacement_read(self):
        peer = await self.peer()
        connection = self.bridge._connection
        original_send = connection.send
        async def interrupted(message):
            if '"operation":"godot_create_rig_lab_animation"' in message:
                await asyncio.Event().wait()
            await original_send(message)
        with patch.object(connection, "send", interrupted):
            await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNone(self.bridge._connection)
        self.assertEqual(self.bridge._unresolved_write.operation, ANIMATION_WRITE_OPERATION)
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        await peer.socket.wait_closed()
        replacement = await self.peer()
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)
        await self.bridge.request(ANIMATION_WRITE_OPERATION, {})
        self.assertEqual(replacement.applied_writes, 1)

    async def test_old_animation_reply_on_replacement_socket_never_settles(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        original_request = peer.requests[-1]
        await peer.socket.close()
        await self.dropped()
        replacement = await self.peer()
        await replacement.socket.send(encode(terminal(original_request, self.credential)))
        await asyncio.sleep(0.01)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_read_before_animation_send_cannot_settle_unknown_animation(self):
        peer = await self.peer(ignore=True)
        action = asyncio.create_task(self.bridge.request(ANIMATION_WRITE_OPERATION, {}))
        await self.received(peer, 1)
        self.bridge.config = Config(request_timeout_seconds=0.6)
        earlier = asyncio.create_task(self.bridge.request("godot_get_editor_state", {}))
        await self.received(peer, 2)
        self.bridge.config = Config(request_timeout_seconds=0.1)
        async def send_read(request):
            data = result_for(request["operation"], self.credential, LAB_SCENE, [ROOT_NODE], [])
            await peer.socket.send(encode({"type": "response", "protocol_version": 1,
                "id": request["id"], "operation": request["operation"], "ok": True,
                "result": data, "error": None}))
        await send_read(peer.requests[0])
        await self.received(peer, 3)
        await self.failure("WRITE_OUTCOME_UNKNOWN", action=action)
        await send_read(peer.requests[1])
        await earlier
        self.assertIsNotNone(self.bridge._unresolved_write)
        later = asyncio.create_task(self.bridge.request("godot_get_editor_state", {}))
        await self.received(peer, 4)
        await send_read(peer.requests[3])
        await later
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_late_animation_replay_rejection_cannot_establish_original_outcome(self):
        peer = await self.peer(ignore_write_reply=True)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        await peer.socket.send(encode(terminal(peer.requests[-1], self.credential,
                                              code="WRITE_REPLAY_REJECTED")))
        await asyncio.sleep(0.01)
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.failure("WRITE_BUSY", WRITE_OPERATION)
        await self.bridge.request("godot_get_editor_state", {})
        self.assertIsNone(self.bridge._unresolved_write)

    async def test_wrong_operation_error_code_after_animation_dispatch_is_unknown(self):
        def mutate(value):
            if value["operation"] == ANIMATION_WRITE_OPERATION:
                value.update(ok=False, result=None, error=error_info("RIG_LAB_BUILD_FAILED"))
        peer = await self.peer(mutate=mutate)
        await self.failure("WRITE_OUTCOME_UNKNOWN")
        self.assertIsNotNone(self.bridge._unresolved_write)
        self.assertEqual(peer.applied_writes, 1)


class AnimationMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_seven_tools_keep_read_schemas_and_closed_animation_contract(self):
        server = create_server(Config(), disposable_credential(), port=0)
        listing = await server.list_tools()
        self.assertEqual({tool.name for tool in listing}, OPERATIONS)
        self.assertEqual(len(listing), 7)
        for tool in listing:
            self.assertEqual(tool.annotations.read_only_hint, tool.name in READ_OPERATIONS)
            self.assertEqual(tool.annotations.idempotent_hint, tool.name in READ_OPERATIONS)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertFalse(tool.annotations.open_world_hint)
            self.assertFalse(tool.input_schema["additionalProperties"])
            self.assertEqual(tool.input_schema["properties"], {})
        tool = next(tool for tool in listing if tool.name == ANIMATION_WRITE_OPERATION)
        validator = Draft202012Validator(tool.output_schema)
        value = envelope(rig_lab_animation_result(disposable_credential()), elapsed_ms=0.1)
        validator.validate(value)
        for field, data in (("library_name", "other"), ("key_count", 4), ("arbitrary_path", "Other")):
            changed = deepcopy(value)
            changed["result"][field] = data
            with self.assertRaises(ValidationError):
                validator.validate(changed)

    async def test_animation_input_never_coerces_user_paths_or_properties(self):
        server = create_server(Config(), disposable_credential(), port=0)
        for data in (None, [], False, {"path": "Other:position"}, {"keys": []}, {"animation_name": "other"}):
            value = await server.call_tool(ANIMATION_WRITE_OPERATION, data)
            self.assertEqual(value.structured_content["error"]["code"], "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main(verbosity=2)
