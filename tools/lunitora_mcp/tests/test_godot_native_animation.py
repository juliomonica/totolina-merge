"""Public registered animation writer against real disposable native editors.

All Create calls traverse the actual MCP tool registration, Python owner and
authenticated native WebSocket command pump. The fixture driver performs only
test controls/native menu shortcuts and explicit disposable-project saves.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from modules.godot.bridge import GodotBridge
from modules.godot.config import Config, PROJECT_ROOT
from modules.godot.protocol import ANIMATION_WRITE_OPERATION, WRITE_OPERATION
from modules.godot.tools import GodotMCPServer, register_tools
from tests import test_godot_native_bridge as native

CONTROL = '''@tool
extends "res://addons/lunitora_godot/plugin.gd"
const Driver = preload("res://tests/godot_mcp/animation_lab_validation.gd")
const SCENARIO := "{scenario}"
var first_animation := true
class WithheldReply extends "res://addons/lunitora_godot/bridge_client.gd":
    var withheld := false
    func _send(message: Dictionary) -> bool:
        if message.get("operation") == "godot_create_rig_lab_animation" and not withheld:
            withheld = true
            return true
        return super._send(message)
class FaultWriter extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_animation_after_action(_scene: Node, _rig: Node, _player: AnimationPlayer,
            _tip: Bone2D, _library: AnimationLibrary, _before: Dictionary,
            _manager: EditorUndoRedoManager) -> bool:
        return false
func _enter_tree() -> void:
    super._enter_tree()
    if SCENARIO == "ordered_timeout":
        _bridge.stop()
        _bridge = WithheldReply.new()
        _bridge.start(_dispatch)
    if SCENARIO == "shared_fault_latch":
        _writer = FaultWriter.new(_session_id)
    if get_tree().root.get_node_or_null("NativeAnimationDriver") == null:
        var driver := Driver.new()
        driver.name = "NativeAnimationDriver"
        get_tree().root.add_child.call_deferred(driver)
func _poll_editor_commands() -> void:
    var driver := get_tree().root.get_node_or_null("NativeAnimationDriver")
    if driver != null:
        driver._normal_process_tick()
    super._poll_editor_commands()
func _dispatch(operation: String, params: Dictionary, request_id := "",
        expected_session_id := "", command_origin := false) -> Dictionary:
    var driver := get_tree().root.get_node_or_null("NativeAnimationDriver")
    if operation == "godot_create_rig_lab_animation" and driver != null and driver._retarget_next_write:
        driver._retarget_next_write = false
        driver._command("retarget")
        driver._command("same_pass")
    var controlled := operation == "godot_create_rig_lab_animation" and first_animation
    if controlled:
        first_animation = false
        if SCENARIO == "ordered_timeout":
            OS.delay_msec(350)
    var result: Dictionary = super._dispatch(operation, params, request_id, expected_session_id, command_origin)
    if controlled and SCENARIO == "lost_reply" and result.ok:
        _bridge._peer.close()
    return result
'''


class GodotNativeAnimationTests(native.GodotNativeBridgeTests):
    editor_mode = True
    editor_control = CONTROL
    test_native_mutual_auth_and_eight_concurrent_read_only_requests = None
    test_native_reconnects_after_codex_owned_listener_restart = None

    def control_values(self):
        fixtures = self.project / "tests/godot_mcp"
        fixtures.mkdir(parents=True)
        for name in ("animation_lab_validation.gd", "animation_lab_validation.gd.uid"):
            shutil.copy2(PROJECT_ROOT / "tests/godot_mcp" / name, fixtures / name)
        return {"scenario": self._testMethodName.removeprefix("test_native_animation_")}

    async def graphical_ready(self):
        await self.evidence(lambda value: value["display"] == "Windows"
            and value["scene"] == f"res://{native.LAB_PATH}" and value["frame"] >= 8)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.server = GodotMCPServer("Native public writer validation")
        register_tools(self.server, self.bridge)
        self._command_counter = 0
        self.assertRegex((await self.public("godot_ping"))["result"]["godot_version"], r"^4\.7\.2(?:[.-]|$)")
        rig = await self.public(WRITE_OPERATION)
        self.assertEqual(rig["result"]["created_node_count"], 7)
        state = await self.command("save")
        self.assertFalse(state["dirty"])
        self.assertEqual(state["connections"], [])
        self.rig_bytes = (self.project / native.LAB_PATH).read_bytes()
        self.rig_snapshot = state["snapshot"]
        self.initial_session = state["session"]
        self.copy_manifest = {name: hashlib.sha256((self.project / "addons/lunitora_godot" / name).read_bytes()).hexdigest()
            for name in ("plugin.gd", "rig_lab.gd", "animation_writer.gd", "inspection.gd")}

    async def public(self, operation=ANIMATION_WRITE_OPERATION, *, error=None):
        response = await self.server.call_tool(operation, {})
        payload = response.structured_content
        if error is None:
            self.assertTrue(payload["ok"], payload)
            self.assertFalse(response.is_error)
        else:
            self.assertFalse(payload["ok"])
            self.assertTrue(response.is_error)
            self.assertEqual(payload["error"]["code"], error)
        return payload

    async def evidence(self, predicate=lambda value: True):
        async with asyncio.timeout(15):
            while True:
                try:
                    files = list((self.project / ".godot").glob("animation_evidence_*.json"))
                    latest = max(files, key=lambda path: path.stat().st_mtime_ns) if files else None
                    data = json.loads(latest.read_text(encoding="utf-8")) if latest else None
                except (FileNotFoundError, PermissionError, json.JSONDecodeError):
                    # Godot publishes successive evidence files. On Windows a
                    # path can appear before its short-lived write handle closes
                    # or disappear during the fixture's bounded report pruning.
                    # Wait for a complete readable report; never retry MCP writes.
                    data = None
                if data is not None and predicate(data):
                    return data
                await asyncio.sleep(0.01)

    async def command(self, command, *, frames=8):
        self._command_counter += 1
        command_id = f"{command}-{self._command_counter}"
        pending = self.project / ".godot/animation_control.pending"
        pending.write_text(
            json.dumps({"command": command, "id": command_id, "frames": frames}), encoding="utf-8")
        pending.replace(self.project / ".godot/animation_control.json")
        value = await self.evidence(lambda item: item["ack"] == command_id)
        self.assertTrue(value["ok"], command)
        return value

    async def frames(self, count=8):
        before = await self.evidence()
        return await self.evidence(lambda value: value["frame"] >= before["frame"] + count)

    def assert_recipe(self, value, expected_nodes=8):
        recipe = value["recipe"]
        self.assertEqual(recipe["libraries"], [""])
        self.assertEqual(recipe["animations"], ["bend_tip"])
        self.assertEqual(recipe["length"], 1.0)
        self.assertEqual(recipe["step"], 0.125)
        self.assertEqual(recipe["loop_mode"], 0)
        self.assertEqual(recipe["markers"], [])
        self.assertFalse(recipe["reset"])
        self.assertEqual(len(recipe["tracks"]), 1)
        track = recipe["tracks"][0]
        self.assertEqual(track["type"], 0)
        self.assertEqual(track["path"], "Skeleton2D/Root/Tip:rotation")
        self.assertEqual(track["interpolation"], 3)
        self.assertEqual(track["update"], 0)
        self.assertTrue(track["enabled"])
        self.assertFalse(track["imported"])
        self.assertFalse(track["loop_wrap"])
        self.assertEqual(len(track["keys"]), 3)
        for key, time, expected_value in zip(track["keys"], (0, 0.5, 1), (0, 0.3490658503988659, 0)):
            self.assertEqual(key["time"], time)
            self.assertEqual(key["value_type"], 3)
            self.assertEqual(key["transition"], 1)
            # Godot JSON evidence prints rounded decimal floats. The native
            # recipe controller and production gate verify exact double values.
            self.assertAlmostEqual(key["value"], expected_value, delta=1e-15)
        for sample in track["samples"]:
            self.assertAlmostEqual(sample, 0.17453292519943295, delta=0.000001)
        self.assertTrue(recipe["root_resolves"])
        self.assertEqual(recipe["root_node"], "..")
        self.assertEqual(recipe["autoplay"], "")
        self.assertEqual(recipe["assigned"], "")
        self.assertEqual(recipe["current"], "")
        self.assertFalse(recipe["playing"])
        self.assertEqual(recipe["queue"], [])
        self.assertEqual(recipe["tip_rotation"], 0)
        self.assertEqual(recipe["tip_transform"], recipe["tip_rest"])
        self.assertEqual(len(value["snapshot"]), expected_nodes)
        for path, node in value["snapshot"].items():
            self.assertFalse(node["script"], path)
            if path != ".":
                self.assertEqual(node["owner"], value["root"], path)

    async def restart_owner(self):
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()
        self.server = GodotMCPServer("Native public writer restarted owner")
        register_tools(self.server, self.bridge)

    async def test_native_animation_controlled_cycle(self):
        before = await self.evidence()
        result = (await self.public())["result"]
        self.assertEqual(result["undo_actions_added"], 1)
        self.assertEqual(result["undo_action_name"], "Lunitora: Create Rig Lab Animation")
        self.assertFalse(result["auto_saved"])
        created = await self.frames()
        self.assert_recipe(created)
        self.assertTrue(created["dirty"])
        self.assertEqual(created["session"], before["session"])
        self.assertEqual(created["history"][2], before["history"][2] + 1)
        await self.command("retain")
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], before["snapshot"])
        self.assertFalse(undone["dirty"])
        self.assertEqual(undone["retained_library"], created["recipe"]["library_id"])
        self.assertEqual(undone["retained_animation"], created["recipe"]["animation_id"])
        redone = await self.command("redo")
        self.assert_recipe(redone)
        self.assertEqual(redone["recipe"]["library_id"], created["recipe"]["library_id"])
        self.assertEqual(redone["recipe"]["animation_id"], created["recipe"]["animation_id"])
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)
        await self.public(error="LAB_ANIMATION_ALREADY_CREATED")
        saved = await self.command("save")
        self.assertFalse(saved["dirty"])
        await self.command("undo")
        self.assertTrue((await self.evidence())["dirty"])
        await self.command("redo")
        self.assertFalse((await self.evidence())["dirty"])
        await self.command("hide")
        closed = await self.command("close")
        self.assertEqual(closed["root"], 0)
        self.assertEqual(closed["retained_library"], 0)
        reopened = await self.command("open")
        self.assert_recipe(reopened)
        self.assertFalse(reopened["dirty"])
        self.assertEqual(reopened["file_hash"], saved["file_hash"])

    async def test_native_animation_rejections_preserve_redo(self):
        await self.public()
        await self.command("retain")
        baseline = await self.command("undo")
        variants = [("wrong_root", "restore_root", "LAB_ROOT_MISMATCH"),
                    ("modified_tip", "restore_tip", "LAB_RIG_MISMATCH"),
                    ("wrong_path", "restore_path", "LAB_RIG_MISMATCH"),
                    ("speed", "restore_speed", "LAB_ANIMATION_CONFLICT"),
                    ("empty_library", "remove_library", "LAB_ANIMATION_CONFLICT"),
                    ("observer", "remove_observer", "LAB_ANIMATION_EDITOR_BUSY")]
        for change, restore, code in variants:
            with self.subTest(change=change):
                changed = await self.command(change)
                await self.public(error=code)
                after = await self.frames()
                self.assertEqual(after["history"], changed["history"])
                self.assertEqual(after["dirty"], changed["dirty"])
                self.assertEqual(after["snapshot"], changed["snapshot"])
                await self.command(restore)
        after = await self.evidence()
        self.assertEqual(after["history"], baseline["history"])
        self.assertTrue(after["history"][3])
        await self.public()
        fresh = await self.frames()
        self.assert_recipe(fresh)
        self.assertFalse(fresh["history"][3])
        self.assertEqual(fresh["retained_library"], 0)
        self.assertEqual(fresh["retained_animation"], 0)

    async def test_native_animation_ordered_timeout(self):
        self.bridge.config = Config(request_timeout_seconds=0.05)
        await self.public(error="WRITE_OUTCOME_UNKNOWN")
        await self.public(WRITE_OPERATION, error="WRITE_BUSY")
        self.assertEqual(self.bridge._unresolved_write.operation, ANIMATION_WRITE_OPERATION)
        self.bridge.config = Config(request_timeout_seconds=5)
        inspected = await self.public("godot_inspect_scene")
        self.assertEqual(len(inspected["result"]["nodes"]), 8)
        self.assertIsNone(self.bridge._unresolved_write)
        self.assert_recipe(await self.frames())
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)

    async def test_native_animation_lost_reply(self):
        request_id = "a" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["b" * 32, request_id]):
            await self.public(error="WRITE_OUTCOME_UNKNOWN")
        await self.wait_connected()
        self.assertIsNone(self.bridge._unresolved_write)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["c" * 32, request_id]):
            await self.public(error="WRITE_REPLAY_REJECTED")
        self.assert_recipe(await self.frames())
        await self.restart_owner()
        self.assertEqual((await self.public("godot_ping"))["result"]["editor_session_id"], self.initial_session)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["d" * 32, request_id]):
            await self.public(error="WRITE_REPLAY_REJECTED")

    async def test_native_animation_shared_fault_latch(self):
        await self.public(error="WRITE_OUTCOME_UNKNOWN")
        self.assert_recipe(await self.frames())
        await self.public(WRITE_OPERATION, error="WRITE_OUTCOME_UNKNOWN")
        original = self.bridge._connection
        await original.close()
        await self.wait_connected()
        await self.public(error="WRITE_OUTCOME_UNKNOWN")
        await self.restart_owner()
        await self.public(WRITE_OPERATION, error="WRITE_OUTCOME_UNKNOWN")
        value = await self.evidence()
        self.assertTrue(value["faulted"])
        self.assertFalse(value["active"])
        self.assertEqual(value["session"], self.initial_session)
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)

    async def test_native_animation_mixed_ledger_capacity_and_session_rollover(self):
        baseline = await self.command("wrong_root")
        oldest = f"{0x2000:032x}"
        # The prerequisite rig Create consumed one entry. Both operations share
        # the remaining127 entries; reconnect and Python owner restart retain it.
        for index in range(127):
            operation = ANIMATION_WRITE_OPERATION if index % 2 else WRITE_OPERATION
            with patch("modules.godot.bridge.secrets.token_hex",
                       side_effect=[f"{0x3000 + index:032x}", f"{0x2000 + index:032x}"]):
                await self.public(operation, error="LAB_ROOT_MISMATCH")
            if index == 63:
                await self.bridge._connection.close()
                await self.wait_connected()
        await self.restart_owner()
        await self.public(error="SESSION_WRITE_LIMIT")
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["d" * 32, oldest]):
            await self.public(ANIMATION_WRITE_OPERATION, error="WRITE_REPLAY_REJECTED")
        await self.public("godot_get_editor_state")
        full = await self.command("restore_root")
        self.assertEqual(full["ledger"], 128)
        self.assertEqual(full["history"], baseline["history"])
        self.assertEqual(full["session"], baseline["session"])
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)
        await self.public(WRITE_OPERATION, error="SESSION_WRITE_LIMIT")
        rolled = await self.command("reload")
        await self.wait_connected()
        self.assertNotEqual(rolled["session"], baseline["session"])
        self.assertEqual(rolled["ledger"], 0)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["e" * 32, oldest]):
            await self.public()
        self.assert_recipe(await self.frames())

    async def finish_child(self):
        # Drain pipes while asking the fixture to quit. Waiting for exit before
        # draining a failed editor's error output can deadlock its pipe handles.
        communication = asyncio.create_task(self.process.communicate())
        if self.process.returncode is None:
            if hasattr(self, "_command_counter"):
                pending = self.project / ".godot/animation_control.pending"
                pending.write_text(
                    json.dumps({"command": "quit", "id": "cleanup", "frames": 0}), encoding="utf-8")
                pending.replace(self.project / ".godot/animation_control.json")
            try:
                await asyncio.wait_for(asyncio.shield(communication), 5)
            except TimeoutError:
                self.process.terminate()
        stdout, stderr = await asyncio.wait_for(communication, 10)
        output = stdout + stderr
        self.assertNotIn(self.credential.secret.hex().encode(), output)
        directory = PROJECT_ROOT / "tools/lunitora_mcp/.local/native-animation-logs"
        directory.mkdir(parents=True, exist_ok=True)
        label = type(self).__name__ + "-" + self._testMethodName
        (directory / (label + ".log")).write_bytes(output)
        (directory / (label + ".remaining-tmp.json")).write_text(json.dumps(
            [str(path.relative_to(self.project)) for path in self.project.rglob("*.tmp")], indent=2), encoding="utf-8")
        files = list((self.project / ".godot").glob("animation_evidence_*.json"))
        if files:
            latest = max(files, key=lambda path: path.stat().st_mtime_ns)
            (directory / (label + ".evidence.json")).write_bytes(latest.read_bytes())
        if hasattr(self, "copy_manifest"):
            (directory / (label + ".manifest.json")).write_text(json.dumps(self.copy_manifest, indent=2), encoding="utf-8")
        if self._testMethodName.endswith("controlled_cycle"):
            shutil.copy2(self.project / native.LAB_PATH, directory / (label + ".tscn"))
        self.assertNotIn(b"SCRIPT ERROR", output)
        self.assertNotIn(b"Parse Error", output)
        self.assertNotIn(b"ERROR:", output)


class GodotGraphicalAnimationTests(GodotNativeAnimationTests):
    """Identical public transport cycle with real Windows editor frames."""
    graphical_editor = True
    test_native_animation_rejections_preserve_redo = None
    test_native_animation_ordered_timeout = None
    test_native_animation_lost_reply = None
    test_native_animation_shared_fault_latch = None
    test_native_animation_mixed_ledger_capacity_and_session_rollover = None

    async def test_native_animation_attach_between_undo_redo(self):
        value = await self.evidence()
        self.assertEqual(value["display"], "Windows")
        await self.public()
        await self.frames()
        await self.command("undo")
        attached = await self.command("attach")
        self.assertTrue(any(row["class"] == "AnimationPlayerEditor" for row in attached["connections"]))
        redone = await self.command("redo")
        self.assertEqual(redone["recipe"]["animations"], ["bend_tip"])
        self.assertEqual(redone["recipe"]["assigned"], "bend_tip")
        self.assertFalse(redone["recipe"]["playing"])
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)

    async def test_native_animation_graphical_admission_and_queued_settlement(self):
        self.assertEqual((await self.evidence())["display"], "Windows")
        attached = await self.command("attach")
        self.assertTrue(any(row["class"] == "AnimationPlayerEditor" and row["custom"] for row in attached["connections"]))
        await self.public(error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("pin")
        await self.command("root")
        await self.public(error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("unpin")
        await self.public(error="LAB_ANIMATION_EDITOR_BUSY")
        hidden = await self.command("hide")
        self.assertNotEqual(hidden["connections"], [])
        await self.command("close")
        opened = await self.command("open")
        self.assertEqual(opened["connections"], [])
        await self.command("retarget_on_write")
        before = await self.evidence()
        await self.public(error="LAB_ANIMATION_EDITOR_SETTLING")
        drained = await self.frames()
        self.assertEqual(drained["connections"], [])
        self.assertEqual(drained["sentinels"][-1]["other_assigned"], "bend_tip")
        self.assertEqual(drained["recipe"]["assigned"], "")
        self.assertEqual(drained["recipe"]["tip_rotation"], 0)
        self.assertEqual(drained["history"], before["history"])
        self.assertFalse(drained["dirty"])
        self.assertEqual(len(drained["observations"]), 3)
        for reply in drained["observations"]:
            self.assertEqual(reply["error"]["code"], "LAB_ANIMATION_EDITOR_SETTLING")
        self.assertGreater(drained["frame"], drained["quiet_frame"])
        await self.public()
        created = await self.frames()
        self.assert_recipe(created, expected_nodes=10)
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], drained["snapshot"])
        redone = await self.command("redo")
        self.assert_recipe(redone, expected_nodes=10)
        self.assertEqual((self.project / native.LAB_PATH).read_bytes(), self.rig_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
