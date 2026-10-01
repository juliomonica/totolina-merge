"""Temporal write admission against real Godot editors in disposable projects.

Fixture-only subclasses delay replies, stage packets and reload their plugin.
The production command pump, authentication and writer run unmodified.
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from modules.godot.bridge import GodotBridge, UnresolvedWrite
from modules.godot.config import Config, PROJECT_ROOT
from modules.godot.protocol import BridgeError, WRITE_OPERATION, encode
from tests import test_godot_native_bridge as native


DRIVER = '''@tool
extends Node
var ack := ""
var old_session := ""
var retired_writer := false
var stopped_dispatch := false
var reloading := false
func _plugin() -> EditorPlugin:
    for candidate in get_tree().root.find_children("*", "EditorPlugin", true, false):
        var script: Script = candidate.get_script()
        if script != null and script.resource_path == "res://addons/lunitora_godot/native_editor_transport.gd":
            return candidate
    return null
func _process(_delta: float) -> void:
    if reloading or not FileAccess.file_exists("res://native_safety_control.json"):
        return
    var command: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://native_safety_control.json"))
    if not command is Dictionary:
        return
    DirAccess.remove_absolute(ProjectSettings.globalize_path("res://native_safety_control.json"))
    var plugin := _plugin()
    if plugin == null:
        return
    if command.command == "reload":
        reloading = true
        old_session = plugin._session_id
        var writer: RefCounted = plugin._writer
        var bridge: RefCounted = plugin._bridge
        EditorInterface.set_plugin_enabled("lunitora_godot", false)
        retired_writer = writer._retired
        stopped_dispatch = not bridge._dispatch.is_valid()
        await get_tree().process_frame
        EditorInterface.set_plugin_enabled("lunitora_godot", true)
        await get_tree().process_frame
        reloading = false
    else:
        plugin._fixture_command(command.command)
    ack = command.id
'''

CONTROL = '''@tool
extends "res://addons/lunitora_godot/plugin.gd"
const SafetyDriver = preload("res://addons/lunitora_godot/safety_driver.gd")
const SCENARIO := "{scenario}"
var paused := false
var first_write := true
var write_entered := false
var write_finished := false
var read_calls := 0
var reads_while_active := 0
var recursive_checks: Array[Dictionary] = []
var stop_queued_packets := -1
var evidence_sequence := 0
var previous_evidence := ""
class WithheldReply extends "res://addons/lunitora_godot/bridge_client.gd":
    var withheld := false
    func _send(message: Dictionary) -> bool:
        if message.get("operation") == "godot_create_rig_lab" and not withheld:
            withheld = true
            return true
        return super._send(message)
class FaultWriter extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_after_action(_root: Node, _rig: Node, _before: Dictionary,
            _manager: EditorUndoRedoManager) -> bool:
        return false
func _enter_tree() -> void:
    super._enter_tree()
    if SCENARIO == "ordered_barrier":
        _bridge.stop()
        _bridge = WithheldReply.new()
        _bridge.start(_dispatch)
    if SCENARIO == "fault_latch":
        _writer = FaultWriter.new(_session_id)
    if get_tree().root.get_node_or_null("NativeSafetyDriver") == null:
        var driver := SafetyDriver.new()
        driver.name = "NativeSafetyDriver"
        get_tree().root.add_child.call_deferred(driver)
func _fixture_command(command: String) -> void:
    match command:
        "pause": paused = true
        "resume": paused = false
        "wrong_root": EditorInterface.get_edited_scene_root().name = "WrongRoot"
        "restore_root": EditorInterface.get_edited_scene_root().name = "TotolinaRigLab"
        "probe_stop":
            for _index in range(4):
                _bridge.poll()
func _process(delta: float) -> void:
    if paused:
        if _bridge._peer != null:
            _bridge._peer.poll()
    else:
        super._process(delta)
    _evidence()
func _dispatch(operation: String, params: Dictionary, request_id := "",
        expected_session_id := "", command_origin := false) -> Dictionary:
    if operation != "godot_create_rig_lab":
        read_calls += 1
        if _writer._active:
            reads_while_active += 1
    var controlled := operation == "godot_create_rig_lab" and first_write
    if controlled:
        first_write = false
        write_entered = true
        _evidence()
        if SCENARIO in ["ordered_barrier", "recursive_poll", "reentrant_stop"]:
            OS.delay_msec(350)
        if SCENARIO == "recursive_poll":
            EditorInterface.get_edited_scene_root().child_entered_tree.connect(_nested_poll)
    var result: Dictionary = super._dispatch(operation, params, request_id, expected_session_id, command_origin)
    if controlled:
        write_finished = true
        if SCENARIO == "recursive_poll":
            EditorInterface.get_edited_scene_root().child_entered_tree.disconnect(_nested_poll)
        if SCENARIO == "reentrant_stop" and result.ok:
            _bridge._peer.poll()
            stop_queued_packets = _bridge._peer.get_available_packet_count()
            _bridge.stop()
        _evidence()
    return result
func _nested_poll(_node: Node) -> void:
    # Poll only the socket so the later read is positively queued, then try the
    # production recursive command pump from the native child-entered signal.
    _bridge._peer.poll()
    var before: int = _bridge._peer.get_available_packet_count()
    var before_reads := read_calls
    var active: bool = _writer._active
    _bridge.poll()
    recursive_checks.append({{"active": active, "before": before,
        "after": _bridge._peer.get_available_packet_count(),
        "reads_before": before_reads, "reads_after": read_calls}})
func _evidence() -> void:
    if _writer == null or _bridge == null:
        return
    var driver := get_tree().root.get_node_or_null("NativeSafetyDriver")
    var data := {{"session": _session_id, "writer": _writer.get_instance_id(),
        "ledger": _writer._write_ids.size(), "ids": _writer._write_ids.keys(),
        "active": _writer._active, "faulted": _writer._faulted,
        "paused": paused, "write_entered": write_entered, "write_finished": write_finished,
        "read_calls": read_calls, "reads_while_active": reads_while_active,
        "recursive": recursive_checks, "peer": 0, "packets": 0, "peer_state": -1,
        "stage": _bridge._stage, "dispatch_valid": _bridge._dispatch.is_valid(), "rig_nodes": 0,
        "stop_queued_packets": stop_queued_packets, "history_count": -1, "history_version": -1,
        "ack": "", "old_session": "", "retired_writer": false, "stopped_dispatch": false}}
    if _bridge._peer != null:
        data.peer = _bridge._peer.get_instance_id()
        data.packets = _bridge._peer.get_available_packet_count()
        data.peer_state = _bridge._peer.get_ready_state()
    if driver != null:
        data.ack = driver.ack
        data.old_session = driver.old_session
        data.retired_writer = driver.retired_writer
        data.stopped_dispatch = driver.stopped_dispatch
    var root := EditorInterface.get_edited_scene_root()
    if root != null:
        var manager := get_undo_redo()
        var history_id := manager.get_object_history_id(root)
        var history := manager.get_history_undo_redo(history_id)
        if history != null:
            data.history_count = history.get_history_count()
            data.history_version = history.get_version()
        if root.has_node("TotolinaRigV2"):
            var rig := root.get_node("TotolinaRigV2")
            data.rig_nodes = 1 + rig.find_children("*", "", true, false).size()
    var encoded := JSON.stringify(data)
    if encoded == previous_evidence:
        return
    previous_evidence = encoded
    evidence_sequence += 1
    # Immutable evidence files avoid Windows safe-save rename conflicts with a
    # simultaneous Python reader. The editor ignores this .godot directory.
    var path := "res://.godot/native_safety_%s_%08d.json" % [_session_id, evidence_sequence]
    var file := FileAccess.open(path, FileAccess.WRITE)
    file.store_string(encoded)
    file.close()
'''


class GodotNativeSafetyTests(native.GodotNativeBridgeTests):
    editor_mode = True
    editor_control = CONTROL
    # The inherited read/restart tests already run in their owning module.
    test_native_mutual_auth_and_eight_concurrent_read_only_requests = None
    test_native_reconnects_after_codex_owned_listener_restart = None

    def control_values(self):
        (self.project / "addons/lunitora_godot/safety_driver.gd").write_text(DRIVER, encoding="utf-8")
        return {"scenario": self._testMethodName.removeprefix("test_native_")}

    async def evidence(self, predicate=lambda value: True):
        async with asyncio.timeout(10):
            while True:
                try:
                    files = list((self.project / ".godot").glob("native_safety_*.json"))
                    latest = max(files, key=lambda path: path.stat().st_mtime_ns) if files else None
                    data = json.loads(latest.read_text(encoding="utf-8")) if latest else None
                except (FileNotFoundError, json.JSONDecodeError):
                    data = None
                if data is not None and predicate(data):
                    return data
                await asyncio.sleep(0.01)

    async def command(self, command):
        command_id = f"{command}-{id(self)}"
        (self.project / "native_safety_control.json").write_text(
            json.dumps({"command": command, "id": command_id}), encoding="utf-8")
        return await self.evidence(lambda value: value["ack"] == command_id)

    async def expect_error(self, code, awaitable):
        with self.assertRaises(BridgeError) as raised:
            await awaitable
        self.assertEqual(raised.exception.code, code)

    async def reconnect(self):
        connection = self.bridge._connection
        await connection.close()
        await self.wait_connected()
        self.assertIsNot(self.bridge._connection, connection)

    async def restart_owner(self):
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()

    async def fixed_id_write(self, request_id, error=None):
        self._fixture_read_id = getattr(self, "_fixture_read_id", 0) + 1
        read_id = f"{0x100000 + self._fixture_read_id:032x}"
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=[read_id, request_id]):
            operation = self.bridge.request(WRITE_OPERATION, {})
            if error is None:
                return await operation
            await self.expect_error(error, operation)

    async def assert_node_count(self, count):
        data, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(len(data["nodes"]), count)
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.lab_hash)
        return data

    async def finish_child(self):
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        stdout, stderr = await self.process.communicate()
        output = stdout + stderr
        self.assertNotIn(self.credential.secret.hex().encode(), output)
        log_dir = PROJECT_ROOT / "tools/lunitora_mcp/.local/native-safety-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{self._testMethodName}.log").write_bytes(output)
        evidence_files = list((self.project / ".godot").glob("native_safety_*.json"))
        if evidence_files:
            latest = max(evidence_files, key=lambda path: path.stat().st_mtime_ns)
            (log_dir / f"{self._testMethodName}.evidence.json").write_bytes(latest.read_bytes())
        self.assertNotIn(b"SCRIPT ERROR", output)
        self.assertNotIn(b"Parse Error", output)
        self.assertNotIn(b"ERROR:", output)

    async def test_native_ordered_barrier(self):
        connection = self.bridge._connection
        self.bridge.config = Config(request_timeout_seconds=0.1)
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        await self.expect_error("WRITE_BUSY", self.bridge.request(WRITE_OPERATION, {}))
        self.assertIsNotNone(self.bridge._unresolved_write)
        before = await self.evidence(lambda value: value["write_entered"])
        self.assertFalse(before["write_finished"])
        self.bridge.config = Config(request_timeout_seconds=5)
        await self.assert_node_count(8)
        self.assertIsNone(self.bridge._unresolved_write)
        self.assertIs(self.bridge._connection, connection)
        after = await self.evidence(lambda value: value["write_finished"])
        self.assertEqual(after["ledger"], 1)
        self.assertEqual(after["reads_while_active"], 0)
        await self.expect_error("LAB_ALREADY_CREATED", self.bridge.request(WRITE_OPERATION, {}))

    async def test_native_unread_old_peer(self):
        state = await self.command("pause")
        connection = self.bridge._connection
        request_id = "a" * 32
        await connection.send(encode({"type": "request", "protocol_version": 1,
            "id": request_id, "operation": WRITE_OPERATION, "params": {},
            "editor_session_id": state["session"]}))
        queued = await self.evidence(lambda value: value["packets"] >= 1)
        self.assertEqual(queued["ledger"], 0)
        self.assertFalse(queued["write_entered"])
        await connection.close()
        await self.evidence(lambda value: value["peer_state"] in (2, 3))
        await self.command("resume")
        await self.wait_connected()
        await self.assert_node_count(1)
        replaced = await self.evidence(lambda value: value["peer"] not in (0, queued["peer"]))
        self.assertEqual(replaced["session"], queued["session"])
        self.assertEqual(replaced["ledger"], 0)
        self.assertNotIn(request_id, replaced["ids"])
        await self.fixed_id_write(request_id)
        await self.assert_node_count(8)
        self.assertEqual((await self.evidence(lambda value: value["ledger"] == 1))["ledger"], 1)

    async def test_native_fault_latch(self):
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        state = await self.evidence(lambda value: value["faulted"])
        self.assertFalse(state["active"])
        await self.assert_node_count(8)
        await self.reconnect()
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        await self.restart_owner()
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        after = await self.evidence(lambda value: value["ledger"] == 3)
        self.assertEqual(after["session"], state["session"])
        self.assertEqual(after["writer"], state["writer"])
        self.assertTrue(after["faulted"])
        self.assertFalse(after["active"])
        self.assertEqual(after["history_count"], state["history_count"])
        self.assertEqual(after["history_version"], state["history_version"])
        await self.assert_node_count(8)

    async def test_native_capacity_ledger(self):
        state = await self.command("wrong_root")
        for index in range(128):
            await self.fixed_id_write(f"{0x1000 + index:032x}", "LAB_ROOT_MISMATCH")
            if index == 63:
                await self.reconnect()
                retained = await self.evidence(lambda value: value["ledger"] == 64)
                self.assertEqual(retained["writer"], state["writer"])
        await self.restart_owner()
        await self.expect_error("SESSION_WRITE_LIMIT", self.bridge.request(WRITE_OPERATION, {}))
        await self.fixed_id_write(f"{0x1000:032x}", "WRITE_REPLAY_REJECTED")
        self.assertIsNotNone(self.bridge._unresolved_write)
        await self.expect_error("WRITE_BUSY", self.bridge.request(WRITE_OPERATION, {}))
        await self.assert_node_count(1)
        self.assertIsNone(self.bridge._unresolved_write)
        after = await self.command("restore_root")
        self.assertEqual(after["ledger"], 128)
        self.assertEqual(after["writer"], state["writer"])
        self.assertEqual(after["session"], state["session"])
        await self.expect_error("SESSION_WRITE_LIMIT", self.bridge.request(WRITE_OPERATION, {}))
        await self.assert_node_count(1)

    async def test_native_stale_wire_session(self):
        before = await self.command("wrong_root")
        request_id = "b" * 32
        await self.fixed_id_write(request_id, "LAB_ROOT_MISMATCH")
        await self.command("restore_root")
        after = await self.command("reload")
        await self.wait_connected()
        self.assertNotEqual(after["session"], before["session"])
        self.assertTrue(after["retired_writer"])
        self.assertTrue(after["stopped_dispatch"])
        self.assertEqual(after["ledger"], 0)
        # Deliberately bypass Python preflight to submit the old wire session;
        # the native writer must reject before admission/action creation.
        record = UnresolvedWrite(request_id, self.bridge._connection, before["session"])
        self.bridge._unresolved_write = record
        await self.expect_error("INVALID_MESSAGE", self.bridge._exchange(
            WRITE_OPERATION, connection=record.connection, writer=record))
        await self.assert_node_count(1)
        state = await self.evidence(lambda value: value["ledger"] == 0)
        self.assertNotIn(request_id, state["ids"])
        await self.bridge.request(WRITE_OPERATION, {})
        await self.assert_node_count(8)

    async def test_native_recursive_poll(self):
        writer = asyncio.create_task(self.bridge.request(WRITE_OPERATION, {}))
        self.addAsyncCleanup(self._finish_task, writer)
        await self.evidence(lambda value: value["write_entered"])
        read = asyncio.create_task(self.bridge.request("godot_get_editor_state", {}))
        self.addAsyncCleanup(self._finish_task, read)
        await writer
        data, _ = await read
        self.assertTrue(data["scene"]["dirty_changes"])
        evidence = await self.evidence(lambda value: bool(value["recursive"]))
        self.assertEqual(evidence["reads_while_active"], 0)
        self.assertTrue(any(value["before"] >= 1 for value in evidence["recursive"]))
        for value in evidence["recursive"]:
            self.assertTrue(value["active"])
            self.assertEqual(value["after"], value["before"])
            self.assertEqual(value["reads_after"], value["reads_before"])
        await self.assert_node_count(8)

    async def test_native_reentrant_stop(self):
        writer = asyncio.create_task(self.bridge.request(WRITE_OPERATION, {}))
        self.addAsyncCleanup(self._finish_task, writer)
        entered = await self.evidence(lambda value: value["write_entered"])
        queued_id = "c" * 32
        await self.bridge._connection.send(encode({"type": "request", "protocol_version": 1,
            "id": queued_id, "operation": WRITE_OPERATION, "params": {},
            "editor_session_id": entered["session"]}))
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", writer)
        stopped = await self.evidence(lambda value: value["write_finished"])
        self.assertEqual(stopped["stage"], 0)
        self.assertFalse(stopped["dispatch_valid"])
        self.assertEqual(stopped["peer"], 0)
        self.assertEqual(stopped["ledger"], 1)
        self.assertEqual(stopped["rig_nodes"], 7)
        self.assertGreaterEqual(stopped["stop_queued_packets"], 1)
        self.assertNotIn(queued_id, stopped["ids"])
        after = await self.command("probe_stop")
        self.assertEqual(after["stage"], 0)
        self.assertFalse(after["dispatch_valid"])
        self.assertEqual(after["peer"], 0)
        self.assertEqual(after["ledger"], 1)
        self.assertEqual(after["rig_nodes"], 7)
        self.assertIsNone(self.bridge._connection)
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.lab_hash)

    async def _finish_task(self, task):
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, BridgeError):
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
