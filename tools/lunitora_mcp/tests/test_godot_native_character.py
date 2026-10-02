"""v0.4 public tools and native editor history in disposable checkout fixtures."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import unittest
from unittest.mock import patch

from modules.godot.bridge import GodotBridge
from modules.godot.config import PROJECT_ROOT, ensure_credential
from modules.godot.tools import GodotMCPServer, register_tools
from tests import test_godot_native_bridge as native
from tests import test_godot_native_animation as animation

RIG = "godot_create_tolina_rig_lab"
BLINK = "godot_create_tolina_lab_blink"
ALL_WRITES = ("godot_create_rig_lab", "godot_create_rig_lab_animation", RIG, BLINK,
              "godot_create_rig_test_cat_deformation_lab", "godot_create_rig_test_cat_deformation_demo")
LAB = "addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"
CONTROL = '''@tool
extends "res://addons/lunitora_godot/plugin.gd"
const Driver = preload("res://tests/godot_mcp/character_lab_validation.gd")
const SCENARIO := "{scenario}"
var first := true
class WithheldReply extends "res://addons/lunitora_godot/bridge_client.gd":
    var withheld := false
    func _send(message: Dictionary) -> bool:
        if message.get("operation") == "godot_create_tolina_lab_blink" and not withheld:
            withheld = true
            return true
        return super._send(message)
class RigFault extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_tolina_after_action(_root: Node, _rig: Node, _before: Dictionary,
            _manager: EditorUndoRedoManager) -> bool:
        return false
class BlinkFault extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_tolina_blink_after_action(_root: Node, _rig: Node, _player: AnimationPlayer,
            _library: AnimationLibrary, _before: Dictionary, _manager: EditorUndoRedoManager) -> bool:
        return false
func _enter_tree() -> void:
    super._enter_tree()
    if SCENARIO == "ordered_timeout":
        _bridge.stop()
        _bridge = WithheldReply.new()
        _bridge.start(_dispatch)
    if SCENARIO == "rig_shared_fault":
        _writer = RigFault.new(_session_id)
    if SCENARIO == "blink_shared_fault":
        _writer = BlinkFault.new(_session_id)
    if get_tree().root.get_node_or_null("NativeCharacterDriver") == null:
        var driver := Driver.new()
        driver.name = "NativeCharacterDriver"
        get_tree().root.add_child.call_deferred(driver)
func _poll_editor_commands() -> void:
    var driver := get_tree().root.get_node_or_null("NativeCharacterDriver")
    if driver != null:
        driver._normal_process_tick()
    super._poll_editor_commands()
func _dispatch(operation: String, params: Dictionary, request_id := "",
        expected_session_id := "", command_origin := false) -> Dictionary:
    var driver := get_tree().root.get_node_or_null("NativeCharacterDriver")
    if operation == "godot_create_tolina_lab_blink" and driver != null and driver._retarget_next_write:
        driver._retarget_next_write = false
        driver._command("retarget")
        driver._command("same_pass")
    var controlled := operation == "godot_create_tolina_lab_blink" and first
    if controlled:
        first = false
        if SCENARIO == "ordered_timeout":
            OS.delay_msec(350)
    var result: Dictionary = super._dispatch(operation, params, request_id, expected_session_id, command_origin)
    if controlled and SCENARIO == "lost_reply" and result.ok:
        _bridge._peer.close()
    return result
'''


class GodotNativeCharacterTests(native.GodotNativeBridgeTests):
    editor_mode = True
    bootstrap_import = True
    lab_path = LAB
    lab_root_name = "TolinaCharacterRigLab"
    editor_control = CONTROL
    test_native_mutual_auth_and_eight_concurrent_read_only_requests = None
    test_native_reconnects_after_codex_owned_listener_restart = None
    public = animation.GodotNativeAnimationTests.public
    evidence = animation.GodotNativeAnimationTests.evidence
    frames = animation.GodotNativeAnimationTests.frames
    restart_owner = animation.GodotNativeAnimationTests.restart_owner

    async def command(self, command, *, frames=8):
        if command != "reload":
            return await animation.GodotNativeAnimationTests.command(self, command, frames=frames)
        # Enabling/disabling an editor plugin persists this disposable project's
        # settings. No MCP owner may retain protected Windows file pins during
        # that explicit editor lifecycle control; reacquire after it settles.
        identity = (self.credential.project_path, self.credential.project_id)
        secret = self.credential.secret
        await self.bridge.stop()
        self.credential.close()
        value = await animation.GodotNativeAnimationTests.command(self, command, frames=frames)
        # Godot 4.7.2 ProjectSettingsEditor queues a 1.5-second native save timer
        # when addons change. Observe that real timer drain before repinning.
        self.assertTrue(value["project_settings_timer_found"])
        value = await self.evidence(lambda item: item["frame"] > value["frame"]
                                    and not item["project_settings_save_pending"])
        self.credential = ensure_credential(self.project)
        self.assertEqual((self.credential.project_path, self.credential.project_id), identity)
        self.assertTrue(self.credential.secret == secret)
        self.addCleanup(self.credential.close)
        self.bridge = GodotBridge(native.Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()
        self.server = GodotMCPServer("Native v0.4 lifecycle restarted owner")
        register_tools(self.server, self.bridge)
        return value

    async def finish_child(self):
        # All public requests have finished. Release Windows ancestor pins before
        # this disposable editor persists its own project state during shutdown.
        await self.bridge.stop()
        self.credential.close()
        await animation.GodotNativeAnimationTests.finish_child(self)
        directory = PROJECT_ROOT / "tools/lunitora_mcp/.local/native-character-logs"
        directory.mkdir(parents=True, exist_ok=True)
        label = type(self).__name__ + "-" + self._testMethodName
        if (self.project / LAB).is_file():
            shutil.copy2(self.project / LAB, directory / (label + ".tscn"))
        (directory / (label + ".production-manifest.json")).write_text(
            json.dumps(self.production_hashes(), indent=2), encoding="utf-8")

    def control_values(self):
        fixtures = self.project / "tests/godot_mcp"
        fixtures.mkdir(parents=True)
        for name in ("animation_lab_validation.gd", "character_lab_validation.gd"):
            shutil.copy2(PROJECT_ROOT / "tests/godot_mcp" / name, fixtures / name)
            shutil.copy2(PROJECT_ROOT / "tests/godot_mcp" / (name + ".uid"), fixtures / (name + ".uid"))
        addon = self.project / "addons/lunitora_godot"
        shutil.copytree(PROJECT_ROOT / "addons/lunitora_godot/specs", addon / "specs")
        shutil.copytree(PROJECT_ROOT / "assets/characters/totolina", self.project / "assets/characters/totolina",
                        ignore=shutil.ignore_patterns("*.tmp"))
        for name in ("scenes/presentation/totolina_operator.tscn",
                     "scripts/presentation/totolina_operator_presentation.gd",
                     "scripts/presentation/totolina_operator_presentation.gd.uid"):
            destination = self.project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / name, destination)
        self.production_before = self.production_hashes()
        return {"scenario": self._testMethodName.removeprefix("test_native_character_")}

    def production_hashes(self):
        files = list((self.project / "assets").rglob("*"))
        files += list((self.project / "scenes").rglob("*")) + list((self.project / "scripts").rglob("*"))
        return {str(path.relative_to(self.project)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in files if path.is_file()}

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.server = GodotMCPServer("Native v0.4 public acceptance")
        register_tools(self.server, self.bridge)
        self._command_counter = 0
        ready = await self.frames()
        self.initial_session = ready["session"]
        self.baseline = (self.project / LAB).read_bytes()
        self.assertEqual(self.production_hashes(), self.production_before)
        ping = await self.public("godot_ping")
        self.assertEqual(ping["bridge_version"], "0.5.0")
        self.assertEqual(ping["result"]["plugin_version"], "0.5.0")

    async def graphical_ready(self):
        await self.evidence(lambda value: value["display"] == "Windows"
            and value["scene"] == f"res://{LAB}" and value["frame"] >= 8)

    async def bootstrap_ready(self):
        await self.evidence(lambda value: value["scene"] == f"res://{LAB}" and value["frame"] >= 16)

    def assert_rig(self, value, *, extra_nodes=0):
        self.assertEqual(value["rig"]["count"], 21)
        self.assertEqual(value["rig"]["sprites"], 16)
        self.assertEqual(value["rig"]["problems"], [])
        self.assertEqual(value["rig"]["composition"], {"compared": 19, "failures": []})
        self.assertEqual(len(value["snapshot"]), 22 + extra_nodes)
        self.assertTrue(value["textures_unchanged"])
        self.assertEqual(value["texture_changed"], 0)
        self.assertTrue(value["production_unchanged"])
        for path, node in value["snapshot"].items():
            self.assertFalse(node["script"], path)
            if path != ".":
                self.assertEqual(node["owner"], value["root"], path)
        self.assertEqual(self.production_hashes(), self.production_before)

    def assert_blink(self, value, *, extra_nodes=0):
        self.assert_rig(value, extra_nodes=extra_nodes)
        recipe = value["recipe"]
        self.assertTrue(recipe["exact"])
        self.assertEqual(recipe["libraries"], [""])
        self.assertEqual(recipe["animations"], ["blink"])
        self.assertEqual(recipe["length"], 0.24)
        self.assertEqual(recipe["step"], 0.125)
        self.assertEqual(recipe["loop"], 0)
        self.assertEqual(recipe["markers"], [])
        self.assertFalse(recipe["reset"])
        self.assertEqual(recipe["rest"], [1, 0, 0])
        self.assertEqual(recipe["assigned"], "")
        self.assertEqual(recipe["current"], "")
        self.assertEqual(recipe["autoplay"], "")
        self.assertEqual(recipe["queue"], [])
        self.assertFalse(recipe["playing"])
        self.assertEqual(len(recipe["tracks"]), 3)
        for index, variant in enumerate(("Rest", "Half", "Closed")):
            track = recipe["tracks"][index]
            self.assertEqual(track["path"], f"Visual/Eyes/{variant}:modulate:a")
            self.assertEqual((track["type"], track["interpolation"], track["update"]), (0, 1, 0))
            self.assertTrue(track["enabled"])
            self.assertFalse(track["imported"])
            self.assertFalse(track["loop_wrap"])
            for key, time, alpha in zip(track["keys"], (0, 0.05, 0.095, 0.14, 0.19, 0.24),
                                       ((1, 0, 0, 0, 0, 1), (0, 1, 0, 0, 1, 0), (0, 0, 1, 1, 0, 0))[index]):
                expected_time = struct.unpack("f", struct.pack("f", time))[0]
                self.assertAlmostEqual(key[0], expected_time, delta=1e-15)
                self.assertEqual(key[1:], [alpha, 1])

    async def make_rig(self, *, extra_nodes=0):
        before = await self.evidence()
        result = (await self.public(RIG))["result"]
        self.assertEqual(result["created_node_count"], 21)
        self.assertEqual(result["undo_action_name"], "Lunitora: Create Tolina Character Rig")
        self.assertEqual(result["undo_actions_added"], 1)
        self.assertFalse(result["auto_saved"])
        value = await self.frames()
        self.assert_rig(value, extra_nodes=extra_nodes)
        self.assertEqual(value["recipe"]["animations"], [])
        self.assertTrue(value["dirty"])
        self.assertEqual(value["session"], before["session"])
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)
        return value

    async def test_native_character_combined_cycle(self):
        empty = await self.evidence()
        self.assertEqual(empty["cache_initial"], [])
        created = await self.make_rig()
        await self.command("watch")
        await self.command("retain_rig")
        response = (await self.public(BLINK))["result"]
        self.assertEqual(response["undo_action_name"], "Lunitora: Create Tolina Lab Blink")
        self.assertEqual((response["track_count"], response["key_count"]), (3, 18))
        blink = await self.frames()
        self.assert_blink(blink)
        await self.command("retain")
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], created["snapshot"])
        self.assertEqual(undone["recipe"]["libraries"], [])
        self.assertTrue(undone["dirty"])
        empty_again = await self.command("undo")
        self.assertEqual(empty_again["snapshot"], empty["snapshot"])
        self.assertFalse(empty_again["dirty"])
        self.assertEqual(empty_again["retained_rig"], created["snapshot"]["TolinaRig"]["id"])
        restored = await self.command("redo")
        self.assertEqual(restored["snapshot"], created["snapshot"])
        redone = await self.command("redo")
        self.assert_blink(redone)
        self.assertEqual(redone["recipe"]["library_id"], blink["recipe"]["library_id"])
        self.assertEqual(redone["recipe"]["animation_id"], blink["recipe"]["animation_id"])
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)

    async def test_native_character_rig_cold_and_warm_cycles(self):
        empty = await self.evidence()
        self.assertEqual(empty["cache_initial"], [])
        created = await self.make_rig()
        await self.command("watch")
        watched = await self.command("assignment_signals")
        self.assertEqual(watched["sprite_assignment_signals"], 16)
        self.assertEqual(watched["texture_changed"], 0)
        await self.command("retain_rig")
        self.assertFalse((await self.command("undo"))["dirty"])
        self.assert_rig(await self.command("redo"))
        await self.command("undo")
        await self.command("production")
        warm = await self.make_rig()
        self.assertEqual(warm["retained_rig"], 0)
        self.assertNotEqual(warm["snapshot"]["TolinaRig"]["id"], created["snapshot"]["TolinaRig"]["id"])
        saved = await self.command("save")
        self.assertFalse(saved["dirty"])
        persisted = (self.project / LAB).read_text(encoding="utf-8")
        self.assertEqual(persisted.count('[ext_resource type="Texture2D"'), 15)
        self.assertNotIn("character_rig_v1.json", persisted)
        self.assertNotIn('[sub_resource type="CompressedTexture2D"', persisted)
        self.assertTrue((await self.command("undo"))["dirty"])
        self.assertFalse((await self.command("redo"))["dirty"])
        await self.command("retain_rig")
        await self.command("reload")
        await self.wait_connected()
        self.assert_rig(await self.frames())
        await self.command("hide")
        self.assertEqual((await self.command("close"))["retained_rig"], 0)
        reopened = await self.command("open")
        self.assert_rig(reopened)
        self.assertFalse(reopened["dirty"])
        self.assertEqual(reopened["recipe"]["animations"], [])
        self.assertEqual(reopened["recipe"]["libraries"], [])
        self.assertEqual(reopened["recipe"]["autoplay"], "")
        self.assertEqual(reopened["file_hash"], saved["file_hash"])

    async def test_native_character_spec_asset_rejections(self):
        result = await self.command("spec_cases")
        self.assertEqual(len(result["spec_results"]), 22)
        self.assertTrue(all(result["spec_results"].values()), result["spec_results"])
        spec = self.project / "addons/lunitora_godot/specs/tolina_character_rig_v1.json"
        body = self.project / "assets/characters/totolina/body/cat_totolina_body.png"
        imported = body.with_name(body.name + ".import")
        mapped_path = re.search(r'^path="res://([^"]+)"$', imported.read_text(encoding="utf-8"), re.MULTILINE)
        self.assertIsNotNone(mapped_path)
        compressed = self.project / mapped_path.group(1)
        cases = ((spec, "changed", "TOLINA_SPEC_INVALID"), (spec, "missing", "TOLINA_SPEC_INVALID"),
                 (body, "changed", "TOLINA_ASSET_INVALID"), (body, "missing", "TOLINA_ASSET_INVALID"),
                 (imported, "changed", "TOLINA_ASSET_INVALID"), (imported, "missing", "TOLINA_ASSET_INVALID"),
                 (compressed, "missing", "TOLINA_ASSET_INVALID"))
        for path, change, error in cases:
            with self.subTest(path=path.name, change=change):
                baseline = await self.evidence()
                original = path.read_bytes()
                backup = path.with_name(path.name + ".test-disabled")
                try:
                    if change == "missing":
                        path.replace(backup)
                    else:
                        path.write_bytes(original + b"\n")
                    for operation in (RIG, BLINK):
                        await self.public(operation, error=error)
                finally:
                    if change == "missing":
                        backup.replace(path)
                    else:
                        path.write_bytes(original)
                preserved = await self.frames(2)
                self.assertEqual(preserved["history"], baseline["history"])
                self.assertEqual(preserved["snapshot"], baseline["snapshot"])
                self.assertEqual(preserved["dirty"], baseline["dirty"])
                self.assertEqual((self.project / LAB).read_bytes(), self.baseline)
        self.assertEqual(self.production_hashes(), self.production_before)
        changed = await self.command("script_root")
        await self.public(RIG, error="LAB_ROOT_MISMATCH")
        self.assertEqual((await self.frames())["history"], changed["history"])
        await self.command("restore_root_script")
        await self.make_rig()

    async def test_native_character_native_commit_reentry(self):
        await self.command("reentry_on")
        await self.make_rig()
        state = await self.command("reentry_off")
        self.assertEqual(len(state["committing_results"]), 4)
        for response in state["committing_results"]:
            self.assertEqual(response["error"]["code"], "WRITE_BUSY")
        self.assertEqual(state["history"][2], 1)
        self.assert_rig(state)

    async def test_native_character_numeric_engine_boundary(self):
        characterization = (await self.command("numeric"))["numeric"]
        self.assertGreater(characterization["half_first"], 1)
        self.assertLess(characterization["closed_first"], 0)
        self.assertLess(characterization["half_second"], 0)
        self.assertGreater(characterization["closed_second"], 1)
        self.assertLess(characterization["color_alpha"], 0)
        self.assertTrue(characterization["exact_key_alphas"])
        self.assertTrue(characterization["sum_partition"])
        self.assertEqual(characterization["helper_verification"], "")
        await self.make_rig()
        await self.public(BLINK)
        self.assert_blink(await self.frames())

    async def test_native_character_unrelated_nodes_preserved(self):
        baseline = await self.command("unrelated")
        await self.command("dirty")
        before = await self.frames()
        created = await self.make_rig(extra_nodes=1)
        self.assertEqual(created["snapshot"]["Unrelated"], baseline["snapshot"]["Unrelated"])
        await self.public(BLINK)
        self.assert_blink(await self.frames(), extra_nodes=1)
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], created["snapshot"])
        twice = await self.command("undo")
        self.assertEqual(twice["snapshot"], before["snapshot"])
        self.assertTrue(twice["dirty"])
        await self.command("redo")
        self.assert_blink(await self.command("redo"), extra_nodes=1)

    async def test_native_character_wrong_native_root_class(self):
        original = (self.project / LAB).read_bytes()
        self.assertEqual((await self.command("close"))["root"], 0)
        # The disposable scene is genuinely closed before editing its fixture.
        (self.project / LAB).write_bytes(original.replace(b'type="Node2D"', b'type="Sprite2D"'))
        opened = await self.command("open")
        self.assertEqual(opened["snapshot"]["."]["class"], "Sprite2D")
        for operation in (RIG, BLINK):
            await self.public(operation, error="LAB_ROOT_MISMATCH")
        rejected = await self.frames()
        self.assertEqual(rejected["snapshot"], opened["snapshot"])
        self.assertEqual(rejected["history"], opened["history"])
        self.assertFalse(rejected["dirty"])
        self.assertEqual((await self.command("close"))["root"], 0)
        (self.project / LAB).write_bytes(original)
        await self.command("open")
        await self.make_rig()

    async def test_native_character_wrong_cached_resource_identity(self):
        for command, expected_class in (("fake_type", "ImageTexture"),
                                        ("fake_load_path_dimensions", "CompressedTexture2D")):
            changed = await self.command(command)
            self.assertEqual(changed["cache_fault"]["class"], expected_class)
            self.assertTrue(changed["cache_fault"]["cached"])
            for operation in (RIG, BLINK):
                await self.public(operation, error="TOLINA_ASSET_INVALID")
            rejected = await self.frames()
            self.assertEqual(rejected["snapshot"], changed["snapshot"])
            self.assertEqual(rejected["history"], changed["history"])
            self.assertFalse(rejected["dirty"])
            await self.command("clear_fake")
        self.assertEqual(self.production_hashes(), self.production_before)
        await self.make_rig()

    async def test_native_character_warm_cache_production_and_persistence(self):
        await self.command("production")
        value = await self.make_rig()
        self.assertEqual(value["texture_count"], 15)
        await self.public(BLINK)
        original = await self.frames()
        self.assert_blink(original)
        await self.command("retain")
        saved = await self.command("save")
        self.assertFalse(saved["dirty"])
        self.assert_blink(saved)
        persisted = (self.project / LAB).read_text(encoding="utf-8")
        self.assertEqual(persisted.count('[ext_resource type="Texture2D"'), 15)
        self.assertNotIn("character_rig_v1.json", persisted)
        self.assertNotIn('[sub_resource type="CompressedTexture2D"', persisted)
        self.assertIn('[sub_resource type="AnimationLibrary"', persisted)
        await self.command("undo")
        self.assertTrue((await self.evidence())["dirty"])
        await self.command("reload")
        await self.wait_connected()
        redone = await self.command("redo")
        self.assertFalse(redone["dirty"])
        self.assert_blink(redone)
        self.assertEqual(redone["recipe"]["animation_id"], original["recipe"]["animation_id"])
        await self.command("hide")
        closed = await self.command("close")
        self.assertEqual(closed["root"], 0)
        self.assertEqual(closed["retained_library"], 0)
        reopened = await self.command("open")
        self.assert_blink(reopened)
        self.assertFalse(reopened["dirty"])
        self.assertEqual(reopened["file_hash"], saved["file_hash"])

    async def test_native_character_redo_disposal_dirty_baseline(self):
        dirty = await self.command("dirty")
        created = await self.make_rig()
        await self.command("retain_rig")
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], dirty["snapshot"])
        self.assertTrue(undone["dirty"])
        changed = await self.command("wrong_root")
        await self.public(RIG, error="LAB_ROOT_MISMATCH")
        rejected = await self.frames()
        self.assertEqual(rejected["history"], changed["history"])
        self.assertEqual(rejected["snapshot"], changed["snapshot"])
        await self.command("restore_root")
        fresh = await self.make_rig()
        self.assertNotEqual(fresh["snapshot"]["TolinaRig"]["id"], created["snapshot"]["TolinaRig"]["id"])
        self.assertEqual(fresh["retained_rig"], 0)
        await self.public(BLINK)
        await self.command("retain")
        await self.command("undo")
        changed = await self.command("modified_sprite")
        await self.public(BLINK, error="LAB_RIG_MISMATCH")
        self.assertEqual((await self.frames())["history"], changed["history"])
        await self.command("restore_sprite")
        await self.public(BLINK)
        fresh_blink = await self.frames()
        self.assert_blink(fresh_blink)
        self.assertEqual(fresh_blink["retained_library"], 0)
        self.assertEqual(fresh_blink["retained_animation"], 0)
        self.assertTrue(fresh_blink["dirty"])

    async def test_native_character_preaction_gates(self):
        before = await self.evidence()
        await self.public(BLINK, error="LAB_RIG_REQUIRED")
        for change, restore, error in (("wrong_root", "restore_root", "LAB_ROOT_MISMATCH"),
                                       ("wrong_scene", "restore_scene", "LAB_SCENE_REQUIRED")):
            changed = await self.command(change)
            for operation in (RIG, BLINK):
                await self.public(operation, error=error)
            self.assertEqual((await self.frames())["history"], changed["history"])
            await self.command(restore)
        self.assertEqual((await self.frames())["snapshot"], before["snapshot"])
        await self.make_rig()
        await self.public(RIG, error="LAB_ALREADY_CREATED")
        for change, restore, error in (("wrong_path", "restore_path", "LAB_RIG_MISMATCH"),
                                       ("speed", "restore_speed", "LAB_ANIMATION_CONFLICT"),
                                       ("empty_library", "remove_library", "LAB_ANIMATION_CONFLICT"),
                                       ("observer", "remove_observer", "LAB_ANIMATION_EDITOR_BUSY")):
            changed = await self.command(change)
            await self.public(BLINK, error=error)
            after = await self.frames()
            self.assertEqual(after["history"], changed["history"])
            self.assertEqual(after["snapshot"], changed["snapshot"])
            self.assertEqual(after["dirty"], changed["dirty"])
            await self.command(restore)
        await self.public(BLINK)
        await self.public(BLINK, error="LAB_ANIMATION_ALREADY_CREATED")

    async def test_native_character_ordered_timeout(self):
        await self.make_rig()
        self.bridge.config = native.Config(request_timeout_seconds=0.05)
        await self.public(BLINK, error="WRITE_OUTCOME_UNKNOWN")
        for operation in ALL_WRITES:
            await self.public(operation, error="WRITE_BUSY")
        self.bridge.config = native.Config(request_timeout_seconds=5)
        inspected = await self.public("godot_inspect_scene")
        self.assertEqual(len(inspected["result"]["nodes"]), 22)
        self.assertIsNone(self.bridge._unresolved_write)
        self.assert_blink(await self.frames())

    async def test_native_character_lost_reply(self):
        await self.make_rig()
        write_id = "a" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["b" * 32, write_id]):
            await self.public(BLINK, error="WRITE_OUTCOME_UNKNOWN")
        await self.wait_connected()
        self.assertIsNone(self.bridge._unresolved_write)
        for operation, read_id in ((RIG, "c" * 32), (BLINK, "d" * 32)):
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[read_id, write_id]):
                await self.public(operation, error="WRITE_REPLAY_REJECTED")
            # Replay rejection deliberately cannot settle an earlier admission.
            # A separately requested ordered read is required before any fresh
            # request, even when this test intentionally reuses a rejected ID.
            self.assertIsNotNone(self.bridge._unresolved_write)
            await self.public("godot_get_editor_state")
            self.assertIsNone(self.bridge._unresolved_write)
        await self.restart_owner()
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["e" * 32, write_id]):
            await self.public(BLINK, error="WRITE_REPLAY_REJECTED")
        self.assert_blink(await self.frames())

    async def test_native_character_mixed_capacity_rollover(self):
        baseline = await self.command("wrong_root")
        oldest = f"{0x9000:032x}"
        for index in range(128):
            operation = ALL_WRITES[index % len(ALL_WRITES)]
            error = "LAB_ROOT_MISMATCH" if operation in (RIG, BLINK) else "LAB_SCENE_REQUIRED"
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0xa000 + index:032x}", f"{0x9000 + index:032x}"]):
                await self.public(operation, error=error)
            if index == 63:
                await self.bridge._connection.close()
                await self.wait_connected()
        await self.restart_owner()
        for operation in ALL_WRITES:
            await self.public(operation, error="SESSION_WRITE_LIMIT")
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["d" * 32, oldest]):
            await self.public(BLINK, error="WRITE_REPLAY_REJECTED")
        full = await self.command("restore_root")
        self.assertEqual(full["ledger"], 128)
        self.assertEqual(full["history"], baseline["history"])
        rolled = await self.command("reload")
        await self.wait_connected()
        self.assertNotEqual(rolled["session"], baseline["session"])
        self.assertEqual(rolled["ledger"], 0)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["e" * 32, oldest]):
            await self.public(RIG)
        self.assert_rig(await self.frames())

    async def assert_shared_fault(self, operation):
        await self.public(operation, error="WRITE_OUTCOME_UNKNOWN")
        value = await self.frames()
        self.assertTrue(value["faulted"])
        self.assertFalse(value["active"])
        self.assert_rig(value)
        for writer in ALL_WRITES:
            await self.public(writer, error="WRITE_OUTCOME_UNKNOWN")
        await self.bridge._connection.close()
        await self.wait_connected()
        for writer in ALL_WRITES:
            await self.public(writer, error="WRITE_OUTCOME_UNKNOWN")
        await self.restart_owner()
        for writer in ALL_WRITES:
            await self.public(writer, error="WRITE_OUTCOME_UNKNOWN")
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)
        await self.public("godot_get_editor_state")
        await self.public("godot_inspect_scene")

    async def test_native_character_rig_shared_fault(self):
        await self.assert_shared_fault(RIG)

    async def test_native_character_blink_shared_fault(self):
        await self.make_rig()
        await self.assert_shared_fault(BLINK)
        self.assert_blink(await self.frames())


class GodotGraphicalCharacterTests(GodotNativeCharacterTests):
    """Actual Windows AnimationPlayer editor/native observer controls."""
    graphical_editor = True
    test_native_character_preaction_gates = None
    test_native_character_ordered_timeout = None
    test_native_character_lost_reply = None
    test_native_character_mixed_capacity_rollover = None
    test_native_character_redo_disposal_dirty_baseline = None
    test_native_character_rig_shared_fault = None
    test_native_character_blink_shared_fault = None

    async def test_native_character_graphical_admission_and_settlement(self):
        await self.make_rig()
        await self.command("save")
        attached = await self.command("attach")
        self.assertTrue(any(row["class"] == "AnimationPlayerEditor" and row["flags"] == 1 for row in attached["connections"]))
        await self.public(BLINK, error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("pin")
        await self.command("root")
        await self.public(BLINK, error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("unpin")
        await self.public(BLINK, error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("hide")
        await self.command("close")
        detached = await self.command("open")
        self.assertEqual(detached["connections"], [])
        await self.command("retarget_on_write")
        before = await self.evidence()
        await self.public(BLINK, error="LAB_ANIMATION_EDITOR_SETTLING")
        drained = await self.frames()
        self.assertEqual(drained["connections"], [])
        self.assertEqual(drained["sentinels"][-1]["other_assigned"], "blink")
        self.assertEqual(drained["recipe"]["assigned"], "")
        self.assertEqual(drained["history"], before["history"])
        for response in drained["observations"]:
            self.assertEqual(response["error"]["code"], "LAB_ANIMATION_EDITOR_SETTLING")
        await self.public(BLINK)
        self.assert_blink(await self.frames(), extra_nodes=1)
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], drained["snapshot"])
        self.assert_blink(await self.command("redo"), extra_nodes=1)

    async def test_native_character_attach_between_undo_redo(self):
        await self.make_rig()
        await self.public(BLINK)
        await self.command("undo")
        attached = await self.command("attach")
        self.assertTrue(any(row["class"] == "AnimationPlayerEditor" for row in attached["connections"]))
        redone = await self.command("redo")
        self.assertEqual(redone["recipe"]["animations"], ["blink"])
        self.assertEqual(redone["recipe"]["assigned"], "blink")
        self.assertFalse(redone["recipe"]["playing"])
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
