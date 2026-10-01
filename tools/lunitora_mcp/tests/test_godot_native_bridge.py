"""Actual Godot WebSocketPeer/Crypto against Python, in disposable project copies.

These tests exercise the native client transport, not a live Codex editor session.
The copied client's URL points at an ephemeral test listener. Disposable editor
subclasses supply delayed/dropped responses and post-action verification faults;
production framing, authentication, scene dispatch and writer remain native.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from modules.godot.bridge import GodotBridge
from modules.godot.config import Config, PROJECT_ROOT, ensure_credential
from modules.godot.protocol import BridgeError, WRITE_OPERATION

GODOT_EXECUTABLE = Path(os.environ.get("GODOT_TEST_EXE",
    "D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64.exe"))
SCRIPT = '''extends SceneTree
const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")
const Inspection = preload("res://addons/lunitora_godot/inspection.gd")
var bridge: RefCounted
var inspection: RefCounted
func _initialize() -> void:
    inspection = Inspection.new()
    bridge = BridgeClient.new()
    bridge.start(_dispatch)
func _process(_delta: float) -> bool:
    bridge.poll()
    return false
func _finalize() -> void:
    bridge.stop()
func _dispatch(operation: String, _params: Dictionary) -> Dictionary:
    match operation:
        "godot_ping":
            return inspection.ping("native-transport-validation")
        "godot_get_editor_state":
            var selected: Array[Node] = []
            return inspection.editor_state(null, selected, PackedStringArray(), "native-transport-validation")
        "godot_inspect_scene":
            return inspection.inspect_scene(null, PackedStringArray(), "native-transport-validation")
    return inspection.failure("UNSUPPORTED_OPERATION", "Unsupported operation.")
'''
EDITOR_CONTROL = '''@tool
extends "res://addons/lunitora_godot/plugin.gd"
# All delay/drop controls exist only in this disposable test subclass.
const DELAY_FIRST_WRITE_MS = {delay}
const DROP_FIRST_WRITE_REPLY = {drop}
const WITHHOLD_FIRST_WRITE_REPLY = {withhold}
const FAULT_AFTER_ACTION = {fault}
var first_write := true
class ReplyControl extends "res://addons/lunitora_godot/bridge_client.gd":
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
    if WITHHOLD_FIRST_WRITE_REPLY:
        _bridge.stop()
        _bridge = ReplyControl.new()
        _bridge.start(_dispatch)
    if FAULT_AFTER_ACTION:
        _writer = FaultWriter.new(_session_id)
func _dispatch(operation: String, params: Dictionary, request_id := "",
        expected_session_id := "", command_origin := false) -> Dictionary:
    var controlled := operation == "godot_create_rig_lab" and first_write
    if controlled:
        first_write = false
        if DELAY_FIRST_WRITE_MS:
            OS.delay_msec(DELAY_FIRST_WRITE_MS)
    var result: Dictionary = super._dispatch(operation, params, request_id, expected_session_id, command_origin)
    if controlled and DROP_FIRST_WRITE_REPLY and result.ok:
        _bridge._peer.close()
    return result
'''
LAB_PATH = "addons/lunitora_godot/labs/totolina_rig_lab.tscn"


class GodotNativeBridgeTests(unittest.IsolatedAsyncioTestCase):
    editor_mode = False
    editor_control = EDITOR_CONTROL

    def control_values(self):
        """Fixed fixture controls; subclasses may substitute their own template."""
        delay = 250 if self._testMethodName.endswith("delayed_dispatch") else 0
        return {"delay": delay,
                "drop": "true" if self._testMethodName.endswith("lost_reply") else "false",
                "withhold": "true" if delay else "false",
                "fault": "true" if self._testMethodName.endswith("fault_latch") else "false"}

    async def asyncSetUp(self):
        self.assertTrue(GODOT_EXECUTABLE.is_file(), "Godot 4.7.2 test executable is required.")
        self.directory = tempfile.TemporaryDirectory(prefix="lunitora-godot-native-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / "tools/lunitora_mcp").mkdir(parents=True)
        self.credential = ensure_credential(self.project)
        self.addCleanup(self.credential.close)
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=0)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.port = self.bridge.port
        self.addAsyncCleanup(self.bridge.stop)
        addon = self.project / "addons/lunitora_godot"
        addon.mkdir(parents=True)
        source = PROJECT_ROOT / "addons/lunitora_godot"
        shutil.copy2(source / "inspection.gd", addon / "inspection.gd")
        shutil.copy2(source / "inspection.gd.uid", addon / "inspection.gd.uid")
        if self.editor_mode:
            for filename in ("plugin.gd", "rig_lab.gd"):
                shutil.copy2(source / filename, addon / filename)
                shutil.copy2(source / (filename + ".uid"), addon / (filename + ".uid"))
            (addon / "native_editor_transport.gd").write_text(
                self.editor_control.format(**self.control_values()), encoding="utf-8")
            (addon / "native_editor_transport.gd.uid").write_text("uid://dlghwo7gnmklj\n", encoding="utf-8")
            (addon / "plugin.cfg").write_text('[plugin]\nname="Native writer transport fixture"\n'
                'description="Disposable native test only"\nauthor="tests"\nversion="0.2.0"\n'
                'script="native_editor_transport.gd"\n', encoding="utf-8")
            lab = self.project / LAB_PATH
            lab.parent.mkdir(parents=True)
            lab.write_text('[gd_scene format=3]\n\n[node name="TotolinaRigLab" type="Node2D"]\n',
                           encoding="utf-8")
            self.lab_hash = lab.read_bytes()
        client = (source / "bridge_client.gd").read_text(encoding="utf-8")
        self.assertEqual(client.count('"ws://127.0.0.1:43128"'), 1)
        client = client.replace('"ws://127.0.0.1:43128"', f'"ws://127.0.0.1:{self.port}"')
        (addon / "bridge_client.gd").write_text(client, encoding="utf-8")
        shutil.copy2(source / "bridge_client.gd.uid", addon / "bridge_client.gd.uid")
        enabled = ('[editor_plugins]\nenabled=PackedStringArray("res://addons/lunitora_godot/plugin.cfg")\n'
                   if self.editor_mode else '')
        (self.project / "project.godot").write_text('config_version=5\n\n[application]\nconfig/name="Native bridge validation"\n'
            + enabled + '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
        if not self.editor_mode:
            (self.project / "native_bridge.gd").write_text(SCRIPT, encoding="utf-8")
            (self.project / "native_bridge.gd.uid").write_text("uid://dlghwo7gnmklj\n", encoding="utf-8")
        environment = dict(os.environ)
        for variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            isolated = self.project / ("isolated_" + variable.lower())
            isolated.mkdir()
            environment[variable] = str(isolated)
        process_temp = self.project / "isolated_process_temp"
        process_temp.mkdir()
        for variable in ("TEMP", "TMP", "TMPDIR"):
            environment[variable] = str(process_temp)
        mode = ["--editor", f"res://{LAB_PATH}"] if self.editor_mode else ["--script", "res://native_bridge.gd"]
        self.process = await asyncio.create_subprocess_exec(str(GODOT_EXECUTABLE), "--headless",
            "--path", str(self.project), *mode, "--max-fps", "60", env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addAsyncCleanup(self.finish_child)
        await self.wait_connected()

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
        self.assertNotIn(b"SCRIPT ERROR", output)
        self.assertNotIn(b"Parse Error", output)
        self.assertNotIn(b"ERROR:", output,
                         "Remaining temporary save files: " +
                         repr([str(path.relative_to(self.project)) for path in self.project.rglob("*.tmp")]))

    async def wait_connected(self):
        async with asyncio.timeout(10):
            while self.bridge._connection is None:
                if self.process.returncode is not None:
                    self.fail("Native client exited before mutual authentication.")
                await asyncio.sleep(0.02)
            if self.editor_mode:
                while True:
                    data, _ = await self.bridge.request("godot_get_editor_state", {})
                    if data["scene"]["path"] == f"res://{LAB_PATH}":
                        break
                    await asyncio.sleep(0.02)

    async def test_native_mutual_auth_and_eight_concurrent_read_only_requests(self):
        operations = ["godot_ping", "godot_get_editor_state", "godot_inspect_scene"]
        results = await asyncio.gather(*(self.bridge.request(operations[index % 3], {}) for index in range(8)))
        self.assertEqual(len(results), 8)
        for index, (data, timing) in enumerate(results):
            if not self.editor_mode:
                self.assertEqual(data["editor_session_id"], "native-transport-validation")
            self.assertGreaterEqual(timing, 0)
            if index % 3 == 0:
                self.assertRegex(data["godot_version"], r"^4\.7\.2(?:[.-]|$)")
                self.assertEqual(data["project_path"], self.credential.project_path)
            if index % 3 == 2:
                self.assertEqual(len(data["nodes"]), 1 if self.editor_mode else 0)
        self.assertEqual(self.bridge._pending, {})

    async def test_native_reconnects_after_codex_owned_listener_restart(self):
        original = self.bridge._connection
        await self.bridge.request("godot_ping", {})
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()
        self.assertIsNot(self.bridge._connection, original)
        data, _ = await self.bridge.request("godot_ping", {})
        self.assertTrue(data["read_only"])


class GodotNativeWriterBridgeTests(GodotNativeBridgeTests):
    """Real editor/plugin/writer across native WebSocket and Python owner lifetimes."""
    editor_mode = True

    async def expect_error(self, code, awaitable):
        with self.assertRaises(BridgeError) as raised:
            await awaitable
        self.assertEqual(raised.exception.code, code)

    async def restart_owner(self):
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()

    async def test_native_editor_write_is_single_undo_action_and_never_autosaves(self):
        result, _ = await self.bridge.request(WRITE_OPERATION, {})
        self.assertEqual(result["created_node_count"], 7)
        self.assertEqual(result["undo_actions_added"], 1)
        self.assertEqual(result["save_state"], "saved_dirty")
        self.assertFalse(result["auto_saved"])
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(len(inspected["nodes"]), 8)
        self.assertEqual(inspected["scene"]["save_state"], "saved_dirty")
        await self.expect_error("LAB_ALREADY_CREATED", self.bridge.request(WRITE_OPERATION, {}))
        self.assertEqual((self.project / LAB_PATH).read_bytes(), self.lab_hash)

    async def test_native_editor_replay_ledger_survives_python_owner_restart(self):
        write_id = "a" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["b" * 32, write_id]):
            result, _ = await self.bridge.request(WRITE_OPERATION, {})
        session = result["editor_session_id"]
        await self.restart_owner()
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["c" * 32, write_id]):
            await self.expect_error("WRITE_REPLAY_REJECTED", self.bridge.request(WRITE_OPERATION, {}))
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(inspected["editor_session_id"], session)
        self.assertEqual(len(inspected["nodes"]), 8)
        self.assertEqual((self.project / LAB_PATH).read_bytes(), self.lab_hash)

    async def test_native_timeout_settles_only_after_ordered_delayed_dispatch(self):
        self.bridge.config = Config(request_timeout_seconds=0.05)
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        await self.expect_error("WRITE_BUSY", self.bridge.request(WRITE_OPERATION, {}))
        self.bridge.config = Config(request_timeout_seconds=5)
        # This request uses the same native FIFO command stream. It cannot reply
        # until the delayed original write has finished synchronous execution.
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(len(inspected["nodes"]), 8)
        self.assertIsNone(self.bridge._unresolved_write)
        await self.expect_error("LAB_ALREADY_CREATED", self.bridge.request(WRITE_OPERATION, {}))
        self.assertEqual((self.project / LAB_PATH).read_bytes(), self.lab_hash)

    async def test_native_transport_reconnect_settles_lost_reply(self):
        write_id = "d" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["e" * 32, write_id]):
            await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        await self.expect_error("WRITE_BUSY", self.bridge.request(WRITE_OPERATION, {}))
        await self.wait_connected()
        self.assertIsNone(self.bridge._unresolved_write)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["f" * 32, write_id]):
            await self.expect_error("WRITE_REPLAY_REJECTED", self.bridge.request(WRITE_OPERATION, {}))
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(len(inspected["nodes"]), 8)
        self.assertEqual((self.project / LAB_PATH).read_bytes(), self.lab_hash)

    async def test_native_reconnect_and_python_restart_preserve_fault_latch(self):
        state, _ = await self.bridge.request("godot_get_editor_state", {})
        session = state["editor_session_id"]
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        self.assertIsNone(self.bridge._unresolved_write)
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(len(inspected["nodes"]), 8)
        original = self.bridge._connection
        await original.close()
        async with asyncio.timeout(10):
            while self.bridge._connection is original:
                await asyncio.sleep(0.02)
        await self.wait_connected()
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        await self.restart_owner()
        await self.expect_error("WRITE_OUTCOME_UNKNOWN", self.bridge.request(WRITE_OPERATION, {}))
        inspected, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(inspected["editor_session_id"], session)
        self.assertEqual(len(inspected["nodes"]), 8)
        self.assertEqual((self.project / LAB_PATH).read_bytes(), self.lab_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
