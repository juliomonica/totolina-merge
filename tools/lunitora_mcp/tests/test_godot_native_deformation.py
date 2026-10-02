"""v0.5 registered public tools through real authenticated native editors.

All projects and native saves are disposable. Test controls never become MCP
tools and never edit the real checkout's labs or credentials.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import unittest
from unittest.mock import patch

from modules.godot.bridge import GodotBridge
from modules.godot.config import PROJECT_ROOT, ensure_credential
from modules.godot.tools import GodotMCPServer, register_tools
from tests import test_godot_native_bridge as native
from tests import test_godot_native_animation as animation
from tests import test_godot_native_character as character

RIG = "godot_create_rig_test_cat_deformation_lab"
DEMO = "godot_create_rig_test_cat_deformation_demo"
ALL_WRITES = ("godot_create_rig_lab", "godot_create_rig_lab_animation",
              "godot_create_tolina_rig_lab", "godot_create_tolina_lab_blink", RIG, DEMO)
LAB = "addons/lunitora_godot/labs/rig_test_cat_deformation_lab.tscn"
ASSETS = "addons/lunitora_godot/test_assets/rig_test_cat"
SPEC = "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
SCARF = f"res://{ASSETS}/body/rig_test_cat_scarf_foreground.png"
SCARF_SHA256 = "b76534ce925d736de66ad5d74ee163780968a3c63a3a5c8af02e7dd993aff4d3"
SCARF_IMPORT_SHA256 = "cb6b770b4ef34f80bb7a0a23e89977e4383c9104d9266c98ded3963a4afc485d"
CONTROL = '''@tool
extends "res://addons/lunitora_godot/plugin.gd"
const Driver = preload("res://tests/godot_mcp/deformation_lab_validation.gd")
const SCENARIO := "{scenario}"
var first := true
class WithheldReply extends "res://addons/lunitora_godot/bridge_client.gd":
    var withheld := false
    func _send(message: Dictionary) -> bool:
        if message.get("operation") == "godot_create_rig_test_cat_deformation_demo" and not withheld:
            withheld = true
            return true
        return super._send(message)
class RigFault extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_deformation_after_action(_root: Node, _rig: Node, _before: Dictionary,
            _manager: EditorUndoRedoManager) -> bool:
        return false
class DemoFault extends "res://addons/lunitora_godot/rig_lab.gd":
    func _verify_deformation_demo_after_action(_root: Node, _rig: Node, _player: AnimationPlayer,
            _library: AnimationLibrary, _before: Dictionary, _manager: EditorUndoRedoManager) -> bool:
        return false
class RigBuildFailure extends "res://addons/lunitora_godot/rig_lab.gd":
    func _prepare_deformation_rig(_spec: Dictionary, _textures: Dictionary) -> Node2D:
        return null
class DemoBuildFailure extends "res://addons/lunitora_godot/rig_lab.gd":
    func _prepare_deformation_library() -> AnimationLibrary:
        return AnimationLibrary.new()
func _enter_tree() -> void:
    super._enter_tree()
    if SCENARIO == "ordered_timeout":
        _bridge.stop()
        _bridge = WithheldReply.new()
        _bridge.start(_dispatch)
    if SCENARIO == "rig_fault":
        _writer = RigFault.new(_session_id)
    if SCENARIO == "demo_fault":
        _writer = DemoFault.new(_session_id)
    if SCENARIO == "rig_build_failure":
        _writer = RigBuildFailure.new(_session_id)
    if SCENARIO == "demo_build_failure":
        _writer = DemoBuildFailure.new(_session_id)
    if get_tree().root.get_node_or_null("NativeDeformationDriver") == null:
        var driver := Driver.new()
        driver.name = "NativeDeformationDriver"
        get_tree().root.add_child.call_deferred(driver)
func _poll_editor_commands() -> void:
    var driver := get_tree().root.get_node_or_null("NativeDeformationDriver")
    if driver != null:
        driver._normal_process_tick()
    super._poll_editor_commands()
func _dispatch(operation: String, params: Dictionary, request_id := "",
        expected_session_id := "", command_origin := false) -> Dictionary:
    var controlled := operation == "godot_create_rig_test_cat_deformation_demo" and first
    if controlled:
        first = false
        if SCENARIO == "ordered_timeout":
            OS.delay_msec(600)
        if SCENARIO == "draw_settlement":
            get_tree().root.get_node("NativeDeformationDriver")._queue_draw_disconnect_select_root()
    var result: Dictionary = super._dispatch(operation, params, request_id, expected_session_id, command_origin)
    if controlled and SCENARIO == "lost_reply" and result.ok:
        _bridge._peer.close()
    return result
'''


class GodotNativeDeformationTests(native.GodotNativeBridgeTests):
    editor_mode = True
    bootstrap_import = True
    lab_path = LAB
    lab_root_name = "RigTestCatDeformationLab"
    editor_control = CONTROL
    test_native_mutual_auth_and_eight_concurrent_read_only_requests = None
    test_native_reconnects_after_codex_owned_listener_restart = None
    public = animation.GodotNativeAnimationTests.public
    evidence = animation.GodotNativeAnimationTests.evidence
    frames = animation.GodotNativeAnimationTests.frames
    restart_owner = animation.GodotNativeAnimationTests.restart_owner
    command = character.GodotNativeCharacterTests.command

    def control_values(self):
        fixtures = self.project / "tests/godot_mcp"
        fixtures.mkdir(parents=True)
        for name in ("animation_lab_validation.gd", "deformation_lab_validation.gd", "weighted_mesh_validation.gd"):
            for suffix in ("", ".uid"):
                shutil.copy2(PROJECT_ROOT / "tests/godot_mcp" / (name + suffix), fixtures / (name + suffix))
        addon = self.project / "addons/lunitora_godot"
        shutil.copytree(PROJECT_ROOT / "addons/lunitora_godot/specs", addon / "specs")
        shutil.copytree(PROJECT_ROOT / ASSETS, self.project / ASSETS)
        for name in ("weighted_mesh_2d.gd", "deformation_rig.gd"):
            for suffix in ("", ".uid"):
                shutil.copy2(PROJECT_ROOT / "addons/lunitora_godot" / (name + suffix), addon / (name + suffix))
        self.asset_before = self.asset_hashes()
        return {"scenario": self._testMethodName.removeprefix("test_native_deformation_")}

    def asset_hashes(self):
        return {str(p.relative_to(self.project)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.project / ASSETS).rglob("*") if p.is_file()}

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.server = GodotMCPServer("Native v0.5 public acceptance")
        register_tools(self.server, self.bridge)
        self._command_counter = 0
        ready = await self.frames()
        self.initial_session = ready["session"]
        self.baseline = (self.project / LAB).read_bytes()
        self.fixture_spec = json.loads((self.project / SPEC).read_text(encoding="utf-8"))
        self.assertEqual(len(self.fixture_spec["textures"]), 24)
        self.assertEqual(self.asset_hashes(), self.asset_before)
        ping = await self.public("godot_ping")
        self.assertEqual(ping["bridge_version"], "0.5.0")
        self.assertEqual(ping["result"]["plugin_version"], "0.5.0")
        self.assertEqual(ping["protocol_version"], 1)

    async def graphical_ready(self):
        await self.evidence(lambda value: value["display"] == "Windows"
                            and value["scene"] == f"res://{LAB}" and value["frame"] >= 12)

    async def bootstrap_ready(self):
        await self.evidence(lambda value: value["scene"] == f"res://{LAB}" and value["frame"] >= 16)

    async def finish_child(self):
        communication = asyncio.create_task(self.process.communicate())
        if self.process.returncode is None:
            if hasattr(self, "_command_counter"):
                pending = self.project / ".godot/animation_control.pending"
                pending.write_text(json.dumps({"command": "quit", "id": "cleanup", "frames": 0}), encoding="utf-8")
                pending.replace(self.project / ".godot/animation_control.json")
            try:
                await asyncio.wait_for(asyncio.shield(communication), 5)
            except TimeoutError:
                self.process.terminate()
        stdout, stderr = await asyncio.wait_for(communication, 10)
        directory = PROJECT_ROOT / "tools/lunitora_mcp/.local/native-deformation-logs"
        directory.mkdir(parents=True, exist_ok=True)
        label = type(self).__name__ + "-" + self._testMethodName
        (directory / (label + ".log")).write_bytes(stdout + stderr)
        files = list((self.project / ".godot").glob("animation_evidence_*.json"))
        if files:
            shutil.copy2(max(files, key=lambda p: p.stat().st_mtime_ns), directory / (label + ".json"))
        if (self.project / LAB).exists():
            shutil.copy2(self.project / LAB, directory / (label + ".tscn"))
        for token in (b"SCRIPT ERROR", b"Parse Error", b"ERROR:", b"WARNING:", self.credential.secret.hex().encode()):
            self.assertNotIn(token, stdout + stderr)

    def assert_rig(self, value, *, extra_nodes=0):
        self.assertTrue(value["rig"]["exact"], value["rig"])
        self.assertEqual((value["rig"]["count"], value["rig"]["vertices"], value["rig"]["triangles"], value["rig"]["bones"]),
                         (19, 561, 1024, 4))
        self.assertEqual(len(value["snapshot"]), 20 + extra_nodes)
        self.assertTrue(value["textures_unchanged"])
        self.assertEqual(value["texture_changed"], 0)
        self.assertEqual(self.asset_hashes(), self.asset_before)
        for path, node in value["snapshot"].items():
            self.assertFalse(node["script"], path)
            if path != ".":
                self.assertEqual(node["owner"], value["root"], path)
        for row in self.fixture_spec["nodes"]:
            path = "RigTestCatRig" + ("/" + row["path"] if row["path"] != "." else "")
            self.assertEqual(value["snapshot"][path]["class"], row["class"], path)
        self.assert_scarf(value)
        self.assert_arm(value)

    def assert_arm(self, value):
        arm = value["rig"]["arm"]
        self.assertEqual(arm["station"], {"position": [900, 160], "rotation": 0, "scale": [.5, .5], "z": 0})
        self.assertEqual(arm["shoulder"], {"position": [0, 0], "rotation": 0, "scale": [1, 1], "z": 0})
        self.assertEqual(arm["upper_children"], ["Elbow"])
        self.assertEqual(arm["elbow_children"], ["LowerArmPaw"])
        scale = struct.unpack("f", struct.pack("f", .4))[0]
        upper_scale = [struct.unpack("f", struct.pack("f", part))[0] for part in arm["upper"]["scale"]]
        self.assertEqual(upper_scale, [scale, scale])
        self.assertEqual((arm["upper"]["position"], arm["upper"]["rotation"], arm["upper"]["z"], arm["upper"]["offset"]),
                         ([0, 0], 0, 0, [-810, -320]))
        self.assertEqual(arm["elbow"] | {"rotation": 0},
                         {"position": [-385, 680], "rotation": 0, "scale": [1, 1], "z": 0})
        self.assertAlmostEqual(arm["elbow"]["rotation"], .8702600002288818, delta=1e-14)
        self.assertEqual((arm["lower"]["position"], arm["lower"]["scale"], arm["lower"]["z"], arm["lower"]["offset"]),
                         ([0, 0], [1, 1], -1, [-860, -240]))
        self.assertAlmostEqual(arm["lower"]["rotation"], -.8702600002288818, delta=1e-14)
        for name, filename in (("upper", "rig_test_cat_arm_upper_l.png"), ("lower", "rig_test_cat_arm_lower_paw_l.png")):
            piece = arm[name]
            self.assertEqual(piece["texture_path"], f"res://{ASSETS}/arms/{filename}")
            self.assertEqual(piece["texture_size"], [1254, 1254])
            self.assertNotEqual(piece["texture_id"], 0)
            self.assertEqual(piece["filter"], 2)
            self.assertTrue(piece["z_relative"])
            self.assertFalse(piece["centered"])
            self.assertFalse(piece["flip_h"])
            self.assertFalse(piece["flip_v"])

    def assert_scarf(self, value):
        scarf = value["rig"]["scarf"]
        row = next(row for row in self.fixture_spec["nodes"] if row["path"] == "BodyStation/ScarfForeground")
        texture = next(texture for texture in self.fixture_spec["textures"] if texture["id"] == row["texture"])
        self.assertEqual((row["class"], row["pivot_px"], texture["path"], texture["size_px"]),
                         ("Sprite2D", [139, -238], SCARF, [288, 147]))
        self.assertEqual((texture["source_sha256"], texture["import_sha256"]), (SCARF_SHA256, SCARF_IMPORT_SHA256))
        self.assertTrue(scarf["exists"])
        self.assertEqual(scarf["class"], "Sprite2D")
        self.assertFalse(scarf["script"])
        self.assertEqual(scarf["owner"], value["root"])
        self.assertNotEqual(scarf["texture_id"], scarf["torso_texture_id"])
        self.assertNotEqual(scarf["texture_id"], 0)
        self.assertEqual(scarf["texture_id"], scarf["cached_texture_id"])
        self.assertEqual(scarf["texture_path"], SCARF)
        self.assertEqual(scarf["texture_size"], [288, 147])
        self.assertEqual(scarf["texture_class"], "CompressedTexture2D")
        self.assertFalse(scarf["texture_script"])
        self.assertFalse(scarf["texture_local"])
        self.assertEqual((scarf["source_sha256"], scarf["import_sha256"]), (SCARF_SHA256, SCARF_IMPORT_SHA256))
        self.assertEqual(scarf["import_error"], 0)
        self.assertEqual(scarf["import_uid"], "uid://c0lea83sdtwng")
        self.assertEqual(scarf["import_path"],
                         "res://.godot/imported/rig_test_cat_scarf_foreground.png-b03e8467b8468f475ecddaa41365b43b.ctex")
        self.assertFalse(scarf["fix_alpha_border"])
        self.assertEqual(scarf["offset"], [-139, 238])
        self.assertFalse(scarf["centered"])
        self.assertFalse(scarf["flip_h"])
        self.assertFalse(scarf["flip_v"])
        self.assertEqual((scarf["hframes"], scarf["vframes"], scarf["frame"]), (1, 1, 0))
        self.assertFalse(scarf["region_enabled"])
        self.assertEqual(scarf["region_rect"], [0, 0, 0, 0])
        self.assertEqual((scarf["position"], scarf["rotation"], scarf["scale"], scarf["z"]),
                         ([0, 0], 0, [1, 1], 1))
        self.assertEqual(scarf["filter"], 2)  # CanvasItem.TEXTURE_FILTER_LINEAR.
        self.assertTrue(scarf["z_relative"])
        self.assertEqual(scarf["body_children"], ["Torso", "HeadPivot", "ScarfForeground"])
        self.assertEqual(scarf["body"], {"position": [1450, 300], "rotation": 0, "scale": [.375, .375], "z": 0})
        self.assertEqual(scarf["torso"], {"position": [0, 0], "rotation": 0, "scale": [1, 1], "z": 0})
        scale = struct.unpack("f", struct.pack("f", .8))[0]
        serialized_scale = [struct.unpack("f", struct.pack("f", value))[0]
                            for value in scarf["head_pivot"]["scale"]]
        self.assertEqual(serialized_scale, [scale, scale])
        self.assertEqual(scarf["head_pivot"] | {"scale": serialized_scale},
                         {"position": [0, 306], "rotation": 0, "scale": [scale, scale], "z": 0})
        self.assertEqual(scarf["head"], {"position": [0, 0], "rotation": 0, "scale": [1, 1], "z": 0})
        self.assertEqual(scarf["head_offset"], [-627, -1145])
        self.assertEqual(scarf["torso_offset"], [-561, 0])

    def assert_demo(self, value, *, extra_nodes=0):
        self.assert_rig(value, extra_nodes=extra_nodes)
        recipe = value["recipe"]
        self.assertTrue(recipe["exact"])
        self.assertEqual(recipe["libraries"], [""])
        self.assertEqual(recipe["animations"], ["deformation_demo"])
        self.assertEqual((recipe["length"], recipe["step"], recipe["loop"]), (2.0, .125, 0))
        self.assertEqual(recipe["markers"], [])
        self.assertFalse(recipe["reset"])
        for key in ("assigned", "current", "autoplay"):
            self.assertEqual(recipe[key], "")
        self.assertEqual(recipe["queue"], [])
        self.assertFalse(recipe["playing"])
        self.assertEqual(recipe["rest"][:5], [0, 0, 0, 0, 0])
        self.assertAlmostEqual(recipe["rest"][5], .8702600002288818, delta=1e-14)
        self.assertEqual(recipe["rest"][6], 306)
        self.assertEqual(len(recipe["tracks"]), 7)
        self.assertEqual(sum(len(t["keys"]) for t in recipe["tracks"]), 35)
        head_track = recipe["tracks"][6]
        self.assertEqual(head_track["path"], "BodyStation/HeadPivot:position:y")
        head_values = [key[1] for key in head_track["keys"]]
        self.assertEqual((head_values[0], head_values[-1]), (recipe["rest"][6], recipe["rest"][6]))
        self.assertEqual([value - recipe["rest"][6] for value in head_values], [0, -6, -12, -6, 0])
        for index, track in enumerate(recipe["tracks"]):
            self.assertNotIn("ScarfForeground", track["path"])
            self.assertNotIn("LowerArmPaw", track["path"])
            self.assertEqual((track["type"], track["update"]), (0, 0))
            self.assertTrue(track["enabled"])
            self.assertFalse(track["imported"])
            self.assertFalse(track["loop_wrap"])
            self.assertEqual([key[0] for key in track["keys"]], [0, .5, 1, 1.5, 2])
            self.assertEqual([key[2] for key in track["keys"]], [-2] * 5)
            self.assertEqual(track["keys"][0][1], track["keys"][-1][1])

    async def make_rig(self, *, extra_nodes=0):
        session = (await self.evidence())["session"]
        result = (await self.public(RIG))["result"]
        self.assertEqual(result["created_node_count"], 19)
        self.assertEqual(result["undo_action_name"], "Lunitora: Create Rig Test Cat Deformation Rig")
        self.assertEqual(result["undo_actions_added"], 1)
        self.assertFalse(result["auto_saved"])
        value = await self.frames(12)
        self.assert_rig(value, extra_nodes=extra_nodes)
        self.assertEqual(value["recipe"]["animations"], [])
        self.assertTrue(value["dirty"])
        self.assertEqual(value["session"], session)
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)
        return value

    async def test_native_deformation_combined_cycle(self):
        empty = await self.evidence()
        self.assertEqual(empty["cache_initial"], [])
        created = await self.make_rig()
        await self.command("watch")
        await self.command("retain_rig")
        response = (await self.public(DEMO))["result"]
        self.assertEqual(response["undo_action_name"], "Lunitora: Create Rig Test Cat Deformation Demo")
        self.assertEqual((response["track_count"], response["key_count"]), (7, 35))
        demo = await self.frames(12)
        self.assert_demo(demo)
        await self.command("retain")
        undone = await self.command("undo")
        self.assert_rig(undone)
        self.assertEqual(undone["rig"]["arm"], created["rig"]["arm"])
        self.assertEqual(undone["snapshot"], created["snapshot"])
        self.assertEqual(undone["recipe"]["libraries"], [])
        self.assertTrue(undone["dirty"])
        empty_again = await self.command("undo")
        self.assertEqual(empty_again["snapshot"], empty["snapshot"])
        self.assertFalse(empty_again["dirty"])
        self.assertEqual(empty_again["retained_rig"], created["snapshot"]["RigTestCatRig"]["id"])
        self.assertEqual(empty_again["retained_scarf"], created["rig"]["scarf"]["id"])
        rig_redone = await self.command("redo")
        self.assert_rig(rig_redone)
        self.assertEqual(rig_redone["snapshot"], created["snapshot"])
        self.assertEqual(rig_redone["rig"]["scarf"], created["rig"]["scarf"])
        self.assertEqual(rig_redone["rig"]["arm"], created["rig"]["arm"])
        redone = await self.command("redo")
        self.assert_demo(redone)
        for key in ("library_id", "animation_id"):
            self.assertEqual(redone["recipe"][key], demo["recipe"][key])
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)

    async def test_native_deformation_persistence_reload_disposal(self):
        await self.command("warm")
        await self.make_rig()
        await self.public(DEMO)
        original = await self.frames()
        await self.command("retain_rig")
        await self.command("retain")
        saved = await self.command("save")
        self.assert_demo(saved)
        self.assertFalse(saved["dirty"])
        scene = (self.project / LAB).read_text()
        self.assertEqual(scene.count('[ext_resource type="Texture2D"'), 6)
        self.assertNotIn(".json", scene)
        self.assertNotIn('[sub_resource type="CompressedTexture2D"', scene)
        blocks = dict(re.findall(r'\[node name="(Torso|ScarfForeground)"[^\n]*\]\n(.*?)(?=\n\[|\Z)', scene, re.S))
        self.assertEqual(set(blocks), {"Torso", "ScarfForeground"})
        texture_ids = [re.search(r'^texture = ExtResource\("([^"]+)"\)$', blocks[name], re.M).group(1)
                       for name in ("Torso", "ScarfForeground")]
        external = {}
        for header in re.findall(r'^\[ext_resource ([^\n]+)\]$', scene, re.M):
            fields = dict(re.findall(r'(type|path|id)="([^"]+)"', header))
            self.assertEqual(fields["type"], "Texture2D")
            external[fields["path"]] = fields["id"]
        self.assertNotEqual(texture_ids[0], texture_ids[1])
        self.assertEqual(texture_ids[0], external[f"res://{ASSETS}/body/rig_test_cat_torso.png"])
        self.assertEqual(texture_ids[1], external[SCARF])
        self.assertRegex(scene, r'\[node name="ScarfForeground" type="Sprite2D" parent="RigTestCatRig/BodyStation"[^\n]*\]')
        self.assertIn("offset = Vector2(-139, 238)", blocks["ScarfForeground"])
        self.assertIn("centered = false", blocks["ScarfForeground"])
        self.assertIn("texture_filter = 2", blocks["ScarfForeground"])
        for property_name in ("polygon", "uv", "antialiased", "skeleton", "bones"):
            self.assertNotRegex(blocks["ScarfForeground"], rf"(?m)^{property_name}\s*=")
        self.assertIn("z_index = 1", blocks["ScarfForeground"])
        await self.command("undo")
        await self.command("reload")
        restored = await self.command("redo")
        self.assert_demo(restored)
        self.assertFalse(restored["dirty"])
        self.assertEqual(restored["recipe"]["animation_id"], original["recipe"]["animation_id"])
        await self.command("root")
        await self.command("hide")
        closed = await self.command("close")
        for key in ("root", "retained_rig", "retained_scarf", "retained_library", "retained_animation"):
            self.assertEqual(closed[key], 0)
        reopened = await self.command("open")
        self.assert_demo(reopened)
        self.assertFalse(reopened["dirty"])
        self.assertEqual(reopened["file_hash"], saved["file_hash"])

    async def test_native_deformation_dirty_rejections_fresh_branch(self):
        dirty = await self.command("dirty")
        created = await self.make_rig()
        await self.command("retain_rig")
        undone = await self.command("undo")
        self.assertEqual(undone["snapshot"], dirty["snapshot"])
        self.assertTrue(undone["dirty"])
        changed = await self.command("wrong_root")
        await self.public(RIG, error="LAB_ROOT_MISMATCH")
        self.assertEqual((await self.frames())["history"], changed["history"])
        await self.command("restore_root")
        fresh = await self.make_rig()
        self.assertNotEqual(fresh["snapshot"]["RigTestCatRig"]["id"], created["snapshot"]["RigTestCatRig"]["id"])
        self.assertEqual(fresh["retained_rig"], 0)
        await self.public(DEMO)
        await self.command("retain")
        await self.command("undo")
        changed = await self.command("modified_mesh")
        await self.public(DEMO, error="LAB_RIG_MISMATCH")
        self.assertEqual((await self.frames())["history"], changed["history"])
        await self.command("restore_mesh")
        changed = await self.command("modified_scarf")
        await self.public(DEMO, error="LAB_RIG_MISMATCH")
        after = await self.frames()
        for key in ("snapshot", "history", "dirty", "file_hash"):
            self.assertEqual(after[key], changed[key])
        await self.command("restore_scarf")
        for change, restore in (("modified_scarf_texture", "restore_scarf_texture"),
                                ("modified_scarf_offset", "restore_scarf_offset"),
                                ("modified_scarf_region", "restore_scarf_region")):
            changed = await self.command(change)
            self.assertFalse(changed["rig"]["exact"])
            await self.public(DEMO, error="LAB_RIG_MISMATCH")
            after = await self.frames()
            for key in ("snapshot", "history", "dirty", "file_hash"):
                self.assertEqual(after[key], changed[key], change)
            self.assertEqual(after["rig"]["scarf"], changed["rig"]["scarf"])
            self.assert_scarf(await self.command(restore))
        for change, restore in (("modified_lower_rotation", "restore_lower_rotation"), ("posed_elbow", "restore_elbow")):
            changed = await self.command(change)
            self.assertFalse(changed["rig"]["exact"])
            await self.public(DEMO, error="LAB_RIG_MISMATCH")
            after = await self.frames()
            for key in ("snapshot", "history", "dirty", "file_hash"):
                self.assertEqual(after[key], changed[key], change)
            self.assertEqual(after["rig"]["arm"], changed["rig"]["arm"])
            restored = await self.command(restore)
            self.assert_arm(restored)
        await self.public(DEMO)
        redone = await self.frames()
        self.assert_demo(redone)
        self.assertEqual((redone["retained_library"], redone["retained_animation"]), (0, 0))

    async def test_native_deformation_preaction_observers(self):
        before = await self.evidence()
        await self.public(DEMO, error="LAB_RIG_REQUIRED")
        for change, restore, error in (("wrong_root", "restore_root", "LAB_ROOT_MISMATCH"),
                                      ("wrong_scene", "restore_scene", "LAB_SCENE_REQUIRED")):
            changed = await self.command(change)
            for operation in (RIG, DEMO):
                await self.public(operation, error=error)
            self.assertEqual((await self.frames())["history"], changed["history"])
            await self.command(restore)
        self.assertEqual((await self.frames())["snapshot"], before["snapshot"])
        await self.make_rig()
        await self.public(RIG, error="LAB_ALREADY_CREATED")
        for change, restore, error in (("skeletal_observer", "remove_skeletal_observer", "LAB_SKELETON_EDITOR_BUSY"),
                                      ("other_polygon_observer", "remove_other_polygon_observer", "LAB_SKELETON_EDITOR_BUSY"),
                                      ("observer", "remove_observer", "LAB_ANIMATION_EDITOR_BUSY"),
                                      ("speed", "restore_speed", "LAB_ANIMATION_CONFLICT")):
            changed = await self.command(change)
            if change == "other_polygon_observer":
                expected_receiver = changed["snapshot"]["OtherPolygon"]["id"]
                self.assertTrue(any(row["id"] == expected_receiver and row["class"] == "Polygon2D"
                                    and row["method"] == "Polygon2D::_skeleton_bone_setup_changed"
                                    and row["flags"] == 0 for row in changed["rig"]["observers"]))
            await self.public(DEMO, error=error)
            after = await self.frames()
            for field in ("history", "snapshot", "dirty"):
                self.assertEqual(after[field], changed[field])
            await self.command(restore)
        await self.public(DEMO)
        await self.public(DEMO, error="LAB_ANIMATION_ALREADY_CREATED")

    async def test_native_deformation_draw_observers_preserve_redo(self):
        await self.make_rig()
        await self.command("save")
        await self.public(DEMO)
        demo = await self.frames(12)
        original = await self.command("undo", frames=12)
        self.assertTrue(original["history"][3])
        self.assertFalse(original["dirty"])
        for command, remove, connections, flags in (
                ("draw_observer", "remove_draw_observer", "draw_connections", 0),
                ("deferred_draw_observer", "remove_draw_observer", "draw_connections", 1),
                ("scarf_draw_observer", "remove_scarf_draw_observer", "scarf_draw_connections", 0),
                ("deferred_scarf_draw_observer", "remove_scarf_draw_observer", "scarf_draw_connections", 1)):
            attached = await self.command(command, frames=12)
            self.assertTrue(any(row["method"] == "_draw_observer" and row["flags"] == flags
                                for row in attached[connections]))
            await self.public(DEMO, error="LAB_SKELETON_EDITOR_BUSY")
            after = await self.frames(12)
            for field in ("snapshot", "history", "dirty", "file_hash"):
                self.assertEqual(after[field], attached[field])
            self.assertEqual(after["snapshot"], original["snapshot"])
            self.assertEqual(after["recipe"]["libraries"], [])
            await self.command(remove, frames=12)
        restored = await self.command("redo", frames=12)
        self.assert_demo(restored)
        for key in ("library_id", "animation_id"):
            self.assertEqual(restored["recipe"][key], demo["recipe"][key])

    async def test_native_deformation_weighted_primitive(self):
        before = await self.frames()
        checked = await self.command("weighted_validation")
        self.assertEqual(checked["helper_results"], {"checks": 153, "failures": [], "scarf_spec_valid": True,
                         "scarf_registration": [{"property": name, "rejected": True}
                                                for name in ("texture", "pivot_px", "z_index", "position_px", "rotation_rad", "scale")]})
        for key in ("snapshot", "history", "dirty"):
            self.assertEqual(checked[key], before[key])
        await self.make_rig()

    async def test_native_deformation_unrelated_and_commit_reentry(self):
        before = await self.command("unrelated")
        await self.command("reentry")
        await self.make_rig(extra_nodes=1)
        await self.command("remove_reentry")
        after = await self.frames()
        self.assertEqual(after["snapshot"]["Unrelated"], before["snapshot"]["Unrelated"])
        self.assertEqual(len(after["reentrant_results"]), 6)
        self.assertTrue(all(row["error"]["code"] == "WRITE_BUSY" for row in after["reentrant_results"]))
        await self.public(DEMO)
        self.assert_demo(await self.frames(), extra_nodes=1)

    async def test_native_deformation_rig_build_failure(self):
        dirty = await self.command("dirty")
        await self.command("undo")
        before = await self.frames()
        await self.public(RIG, error="DEFORMATION_RIG_BUILD_FAILED")
        after = await self.frames()
        for key in ("snapshot", "history", "dirty"):
            self.assertEqual(after[key], before[key])
        self.assertFalse(after["faulted"])
        redone = await self.command("redo")
        self.assertEqual(redone["snapshot"], dirty["snapshot"])

    async def test_native_deformation_demo_build_failure(self):
        await self.make_rig()
        dirty = await self.command("dirty")
        await self.command("undo")
        before = await self.frames()
        await self.public(DEMO, error="DEFORMATION_DEMO_BUILD_FAILED")
        after = await self.frames()
        for key in ("snapshot", "history", "dirty"):
            self.assertEqual(after[key], before[key])
        self.assertFalse(after["faulted"])
        self.assert_rig(after)
        self.assertEqual((await self.command("redo"))["snapshot"], dirty["snapshot"])

    async def test_native_deformation_asset_spec_pin_rejections(self):
        before = await self.frames()
        manifest = self.project / "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
        texture = self.project / ASSETS / "tail/rig_test_cat_tail.png"
        scarf = self.project / SCARF.removeprefix("res://")
        for path, error in ((manifest, "DEFORMATION_SPEC_INVALID"),
                            (texture, "DEFORMATION_ASSET_INVALID"),
                            (texture.with_suffix(".png.import"), "DEFORMATION_ASSET_INVALID"),
                            (scarf, "DEFORMATION_ASSET_INVALID"),
                            (scarf.with_suffix(".png.import"), "DEFORMATION_ASSET_INVALID")):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b"\n")
                await self.public(RIG, error=error)
                after = await self.frames()
                for key in ("snapshot", "history", "dirty"):
                    self.assertEqual(after[key], before[key])
                self.assertFalse(after["faulted"])
            finally:
                path.write_bytes(original)
        await self.make_rig()

    async def test_native_deformation_ordered_timeout(self):
        await self.make_rig()
        # Leave enough budget for the mandatory fresh read of the larger rig;
        # only the deliberately delayed mutation must time out.
        self.bridge.config = native.Config(request_timeout_seconds=.25)
        await self.public(DEMO, error="WRITE_OUTCOME_UNKNOWN")
        for operation in ALL_WRITES:
            await self.public(operation, error="WRITE_BUSY")
        self.bridge.config = native.Config(request_timeout_seconds=5)
        inspected = await self.public("godot_inspect_scene")
        self.assertEqual(len(inspected["result"]["nodes"]), 20)
        self.assertIsNone(self.bridge._unresolved_write)
        self.assert_demo(await self.frames())

    async def test_native_deformation_lost_reply(self):
        await self.make_rig()
        write_id = "a" * 32
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["b" * 32, write_id]):
            await self.public(DEMO, error="WRITE_OUTCOME_UNKNOWN")
        await self.wait_connected()
        await self.restart_owner()
        for index, operation in enumerate(ALL_WRITES):
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0xd000 + index:032x}", write_id]):
                await self.public(operation, error="WRITE_REPLAY_REJECTED")
            await self.public("godot_get_editor_state")
        self.assert_demo(await self.frames())

    async def test_native_deformation_mixed_capacity_rollover(self):
        changed = await self.command("wrong_root")
        first = f"{0x9000:032x}"
        for index in range(128):
            operation = ALL_WRITES[index % 6]
            error = "LAB_ROOT_MISMATCH" if operation in (RIG, DEMO) else "LAB_SCENE_REQUIRED"
            with patch("modules.godot.bridge.secrets.token_hex", side_effect=[f"{0xa000+index:032x}", f"{0x9000+index:032x}"]):
                await self.public(operation, error=error)
            if index == 63:
                await self.bridge._connection.close()
                await self.wait_connected()
        await self.restart_owner()
        for operation in ALL_WRITES:
            await self.public(operation, error="SESSION_WRITE_LIMIT")
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["d" * 32, first]):
            await self.public(DEMO, error="WRITE_REPLAY_REJECTED")
        full = await self.command("restore_root")
        self.assertEqual(full["ledger"], 128)
        self.assertEqual(full["history"], changed["history"])
        rolled = await self.command("reload")
        self.assertNotEqual(rolled["session"], changed["session"])
        self.assertEqual(rolled["ledger"], 0)
        with patch("modules.godot.bridge.secrets.token_hex", side_effect=["e" * 32, first]):
            await self.public(RIG)
        self.assert_rig(await self.frames())

    async def assert_fault(self, operation):
        await self.public(operation, error="WRITE_OUTCOME_UNKNOWN")
        evidence = await self.frames()
        self.assertTrue(evidence["faulted"])
        self.assertFalse(evidence["active"])
        for _ in range(2):
            for writer in ALL_WRITES:
                await self.public(writer, error="WRITE_OUTCOME_UNKNOWN")
            await self.restart_owner()
        self.assertEqual((self.project / LAB).read_bytes(), self.baseline)
        await self.public("godot_get_editor_state")
        await self.public("godot_inspect_scene")

    async def test_native_deformation_rig_fault(self):
        await self.assert_fault(RIG)
        self.assert_rig(await self.frames())

    async def test_native_deformation_demo_fault(self):
        await self.make_rig()
        await self.assert_fault(DEMO)
        self.assert_demo(await self.frames())


class GodotGraphicalDeformationTests(GodotNativeDeformationTests):
    graphical_editor = True
    rendering_method = "mobile"
    rendering_driver_windows = "d3d12"
    test_native_deformation_ordered_timeout = None
    test_native_deformation_lost_reply = None
    test_native_deformation_mixed_capacity_rollover = None
    test_native_deformation_rig_fault = None
    test_native_deformation_demo_fault = None
    test_native_deformation_asset_spec_pin_rejections = None
    test_native_deformation_rig_build_failure = None
    test_native_deformation_demo_build_failure = None
    test_native_deformation_weighted_primitive = None

    async def test_native_deformation_native_polygon_editor_admission(self):
        await self.assert_polygon_editor_admission("select_mesh", "draw_connections")

    async def test_native_deformation_native_scarf_sprite_editor_admission(self):
        await self.make_rig()
        await self.command("save")
        await self.command("select_scarf", frames=12)
        selected = await self.evidence(lambda row: row["inspected"] == row["rig"]["scarf"]["id"]
                                      and row["selected"] == [row["rig"]["scarf"]["id"]])
        self.assert_rig(selected)
        self.assertEqual(selected["scarf_draw_connections"], [])
        self.assertFalse(selected["dirty"])
        await self.public(DEMO)
        created = await self.frames(12)
        self.assert_demo(created)
        self.assertTrue(created["dirty"])
        self.assertEqual(created["file_hash"], selected["file_hash"])
        undone = await self.command("undo", frames=12)
        self.assertEqual(undone["snapshot"], selected["snapshot"])
        self.assertEqual(undone["recipe"]["libraries"], [])
        self.assertFalse(undone["dirty"])
        restored = await self.command("redo", frames=12)
        self.assert_demo(restored)
        self.assertEqual(restored["recipe"]["animation_id"], created["recipe"]["animation_id"])

    async def assert_polygon_editor_admission(self, command, connections):
        await self.make_rig()
        await self.command("save")
        selected = await self.command(command, frames=12)
        selected = await self.evidence(lambda row: row["inspected"] in row["selected"]
                                      and any(connection["class"] == "Polygon2DEditor"
                                              for connection in row[connections]))
        self.assert_rig(selected)
        await self.public(DEMO, error="LAB_SKELETON_EDITOR_BUSY")
        rejected = await self.frames(12)
        for key in ("snapshot", "history", "dirty", "file_hash"):
            self.assertEqual(rejected[key], selected[key])
        detached = await self.command("root", frames=12)
        self.assertEqual(detached[connections], [])
        await self.public(DEMO)
        created = await self.frames(12)
        self.assert_demo(created)
        undone = await self.command("undo", frames=12)
        self.assertEqual(undone["snapshot"], detached["snapshot"])
        self.assertEqual(undone["recipe"]["libraries"], [])
        restored = await self.command("redo", frames=12)
        self.assert_demo(restored)
        self.assertEqual(restored["recipe"]["animation_id"], created["recipe"]["animation_id"])

    async def test_native_deformation_draw_settlement(self):
        await self.make_rig()
        before = await self.command("select_tip", frames=12)
        await self.public(DEMO, error="LAB_ANIMATION_EDITOR_SETTLING")
        drained = await self.frames(12)
        self.assertEqual(drained["draw_connections"], [])
        self.assertGreater(drained["draw_observer_calls"], 0)
        self.assertEqual(drained["recipe"]["rest"][3], 0.125)
        for key in ("history", "dirty", "file_hash"):
            self.assertEqual(drained[key], before[key])
        self.assertEqual(drained["recipe"]["libraries"], [])
        await self.public(DEMO, error="LAB_RIG_MISMATCH")
        restored = await self.command("restore_tip_test_only", frames=12)
        self.assert_rig(restored)
        await self.public(DEMO)
        created = await self.frames(12)
        self.assert_demo(created)
        undone = await self.command("undo", frames=12)
        self.assertEqual(undone["snapshot"], restored["snapshot"])
        redone = await self.command("redo", frames=12)
        self.assert_demo(redone)
        self.assertEqual(redone["recipe"]["animation_id"], created["recipe"]["animation_id"])

    async def test_native_deformation_selection_queued_history_disposal(self):
        created = await self.make_rig()
        await self.command("retain_rig")
        for command in ("select_mesh", "select_scarf", "select_skeleton", "select_root_bone", "select_mid1", "select_mid2", "select_tip"):
            selected = await self.command(command, frames=12)
            selected = await self.evidence(lambda row: row["inspected"] in row["selected"])
            self.assertEqual(selected["snapshot"], created["snapshot"])
            self.assert_rig(selected)
        await self.command("root")
        queued = await self.command("queued_undo_redo", frames=12)
        self.assertEqual(queued["snapshot"], created["snapshot"])
        await self.command("queue")
        undone = await self.command("undo", frames=12)
        self.assertEqual(len(undone["snapshot"]), 1)
        self.assertFalse(undone["dirty"])
        await self.command("reload")
        self.assertEqual((await self.frames())["retained_rig"], created["snapshot"]["RigTestCatRig"]["id"])
        self.assertEqual((await self.frames())["retained_scarf"], created["rig"]["scarf"]["id"])
        await self.public(RIG)
        fresh = await self.frames(12)
        self.assert_rig(fresh)
        self.assertEqual(fresh["retained_rig"], 0)
        self.assertEqual(fresh["retained_scarf"], 0)
        await self.command("retain_rig")
        await self.command("undo")
        cleared = await self.command("clear_history", frames=12)
        self.assertEqual(cleared["retained_rig"], 0)
        self.assertEqual(cleared["retained_scarf"], 0)
        self.assertEqual(len(cleared["snapshot"]), 1)

    async def test_native_deformation_animation_editor_admission(self):
        await self.make_rig()
        await self.command("save")
        attached = await self.command("attach")
        self.assertTrue(any(row["class"] == "AnimationPlayerEditor" for row in attached["connections"]))
        await self.public(DEMO, error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("pin")
        await self.command("root")
        await self.public(DEMO, error="LAB_ANIMATION_EDITOR_BUSY")
        await self.command("unpin")
        await self.command("hide")
        await self.command("close")
        opened = await self.command("open")
        self.assertEqual(opened["connections"], [])
        await self.public(DEMO)
        original = await self.frames(12)
        self.assert_demo(original)
        await self.command("undo")
        restored = await self.command("redo", frames=12)
        self.assert_demo(restored)
        self.assertEqual(restored["recipe"]["animation_id"], original["recipe"]["animation_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
