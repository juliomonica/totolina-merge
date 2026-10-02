#!/usr/bin/env python3
"""Verify real Godot Android/iOS data packages exclude the editor addon.

Runs the native --export-pack path twice per existing mobile preset in an
isolated resource fixture (or --full-project runtime copy): with the repository's exact preset bytes, then with
only that preset's addon exclusion removed as a positive control. No templates,
signing, SDK, device, or executable export is requested. No real credential is
copied. An optional retained native-writer scene is substituted only in the
disposable copy, then loaded from both positive-control packages natively.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


ADDON = "addons/lunitora_godot/"
EXCLUSION = ADDON + "*"
ADDON_SCRIPT_CONTROLS = ("plugin.gd", "bridge_client.gd", "inspection.gd", "rig_lab.gd", "animation_writer.gd", "character_rig.gd")
ADDON_SCENE_CONTROLS = ("labs/totolina_rig_lab.tscn", "labs/tolina_character_rig_lab.tscn")
ADDON_SPEC_CONTROL = "specs/tolina_character_rig_v1.json"
TOLINA_TEXTURE_NODES = {
    "EarLeft": ("ears/cat_totolina_ear_left.png", [192, 192]),
    "EarRight": ("ears/cat_totolina_ear_right.png", [192, 192]),
    "Body": ("body/cat_totolina_body.png", [768, 1024]),
    "Arms/Idle": ("arms/cat_totolina_arm_idle.png", [384, 384]),
    "Arms/Press01": ("arms/cat_totolina_arm_press_01.png", [384, 384]),
    "Arms/Press02": ("arms/cat_totolina_arm_press_02.png", [384, 384]),
    "Arms/Press03": ("arms/cat_totolina_arm_press_03.png", [384, 384]),
    "ShoulderOverlap": ("body/cat_totolina_body.png", [768, 1024]),
    "Eyes/Rest": ("eyes/cat_totolina_eyes_blink_01.png", [328, 128]),
    "Eyes/Half": ("eyes/cat_totolina_eyes_blink_02.png", [328, 128]),
    "Eyes/Closed": ("eyes/cat_totolina_eyes_blink_03.png", [328, 128]),
    "Eyes/Excited": ("eyes/cat_totolina_eyes_excited.png", [328, 128]),
    "Eyes/Surprised": ("eyes/cat_totolina_eyes_surprised.png", [328, 128]),
    "MouthIdle": ("mouths/cat_totolina_mouth_idle.png", [128, 128]),
    "MouthExcited": ("mouths/cat_totolina_mouth_excited.png", [128, 128]),
    "MouthSurprised": ("mouths/cat_totolina_mouth_surprised.png", [128, 128]),
}
TOLINA_TEXTURE_PREFIX = "assets/characters/totolina/"
ERROR_PATTERN = re.compile(r"(?im)(?:^\s*(?:SCRIPT ERROR:|ERROR:)|FATAL|CrashHandler)")
RESOURCE = '[gd_resource type="Resource" format=3]\n\n[resource]\n'
PACKAGE_ANIMATION_VALIDATION = r'''extends SceneTree

const LAB_PATH := "res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"
var _checks := 0
var _failures := 0

func _check(condition: bool, label: String) -> void:
    _checks += 1
    if not condition:
        _failures += 1
        print("FAIL exported animation: " + label)

func _initialize() -> void:
    _run.call_deferred()

func _run() -> void:
    var args := OS.get_cmdline_user_args()
    if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0]):
        _check(false, "native positive-control resource pack loads")
        _finish()
        return
    _check(true, "native positive-control resource pack loads")
    var packed := load(LAB_PATH) as PackedScene
    _check(packed != null, "compiled lab is a loadable PackedScene")
    if packed == null:
        _finish()
        return
    var scene := packed.instantiate()
    root.add_child(scene)
    await process_frame
    await process_frame
    _check(scene.name == "TotolinaRigLab" and scene.get_class() == "Node2D", "lab root")
    var manifest := {
        ".": "Node2D", "TotolinaRigV2": "Node2D", "TotolinaRigV2/Meshes": "Node2D",
        "TotolinaRigV2/Meshes/TestMesh": "Polygon2D", "TotolinaRigV2/Skeleton2D": "Skeleton2D",
        "TotolinaRigV2/Skeleton2D/Root": "Bone2D", "TotolinaRigV2/Skeleton2D/Root/Tip": "Bone2D",
        "TotolinaRigV2/AnimationPlayer": "AnimationPlayer",
    }
    var pending: Array[Node] = [scene]
    var count := 0
    while not pending.is_empty():
        var node: Node = pending.pop_back()
        var path := String(scene.get_path_to(node))
        _check(manifest.has(path) and node.get_class() == manifest.get(path), "exact node " + path)
        _check(node.get_script() == null, "native script-free node " + path)
        if node != scene:
            _check(node.owner == scene, "persisted ownership " + path)
        if node is Node2D and path != "TotolinaRigV2/Skeleton2D/Root/Tip":
            _check(node.transform == Transform2D.IDENTITY, "unchanged rest transform " + path)
        count += 1
        for child in node.get_children(true):
            pending.append(child)
    _check(count == 8, "root plus exactly seven generated nodes")
    var mesh := scene.get_node("TotolinaRigV2/Meshes/TestMesh") as Polygon2D
    _check(mesh.color == Color(0.25, 0.5, 1, 1), "exact color")
    _check(mesh.polygon == PackedVector2Array([Vector2(0, -12), Vector2(64, -12), Vector2(128, -12),
        Vector2(128, 12), Vector2(64, 12), Vector2(0, 12)]), "exact vertices")
    _check(mesh.polygons == [PackedInt32Array([0, 1, 5]), PackedInt32Array([1, 4, 5]),
        PackedInt32Array([1, 2, 4]), PackedInt32Array([2, 3, 4])], "exact triangles")
    _check(mesh.texture == null and mesh.vertex_colors.is_empty(), "synthetic untextured mesh")
    _check(mesh.skeleton == NodePath("../../Skeleton2D") and mesh.get_bone_count() == 2, "skeleton binding")
    _check(mesh.get_bone_path(0) == NodePath("Root") and mesh.get_bone_path(1) == NodePath("Root/Tip"), "bone paths")
    _check(mesh.get_bone_weights(0) == PackedFloat32Array([1, 0.5, 0, 0, 0.5, 1]) and
        mesh.get_bone_weights(1) == PackedFloat32Array([0, 0.5, 1, 1, 0.5, 0]), "exact weights")
    var player := scene.get_node("TotolinaRigV2/AnimationPlayer") as AnimationPlayer
    _check(player.root_node == NodePath("..") and player.get_node(player.root_node) == scene.get_node("TotolinaRigV2"), "player root path")
    _check(player.get_animation_library_list().size() == 1 and player.has_animation_library(&""), "exactly one global library")
    _check(player.get_animation_list().size() == 1 and player.has_animation(&"bend_tip") and not player.has_animation(&"RESET"), "exactly bend_tip and no RESET")
    _check(player.autoplay == &"" and player.assigned_animation == &"" and player.current_animation == &"" and
        player.get_queue().is_empty() and not player.is_playing(), "no autoplay assignment playback or queue")
    var library := player.get_animation_library(&"")
    _check(library.get_class() == "AnimationLibrary" and library.get_script() == null, "native script-free library")
    _check(library.get_animation_list_size() == 1 and library.has_animation(&"bend_tip"), "inline library content")
    var animation := library.get_animation(&"bend_tip")
    _check(animation.get_class() == "Animation" and animation.get_script() == null, "native script-free animation")
    _check(animation == player.get_animation(&"bend_tip"), "library/player animation identity")
    _check(animation.length == 1.0 and animation.loop_mode == Animation.LOOP_NONE and
        animation.step == 0.125 and not animation.capture_included, "exact length loop step and capture flag")
    _check(animation.get_marker_names().is_empty(), "no markers")
    _check(animation.get_track_count() == 1 and animation.track_get_type(0) == Animation.TYPE_VALUE, "one value track")
    _check(animation.track_get_path(0) == NodePath("Skeleton2D/Root/Tip:rotation"), "exact property track")
    _check(animation.track_get_interpolation_type(0) == Animation.INTERPOLATION_LINEAR_ANGLE and
        animation.value_track_get_update_mode(0) == Animation.UPDATE_CONTINUOUS, "interpolation and update mode")
    _check(animation.track_is_enabled(0) and not animation.track_is_imported(0) and
        not animation.track_get_interpolation_loop_wrap(0), "track flags")
    _check(animation.track_get_key_count(0) == 3, "exactly three keys")
    var times := [0.0, 0.5, 1.0]
    var values := [0.0, 0.3490658503988659, 0.0]
    for index in range(3):
        _check(animation.track_get_key_time(0, index) == times[index], "key time " + str(index))
        var value: Variant = animation.track_get_key_value(0, index)
        _check(typeof(value) == TYPE_FLOAT and value == values[index], "typed float key value " + str(index))
        _check(animation.track_get_key_transition(0, index) == 1.0, "key transition " + str(index))
    for time in [0.25, 0.75]:
        _check(absf(float(animation.value_track_interpolate(0, time)) - 0.17453292519943295) <= 0.000001,
            "detached +10 degree interpolation at " + str(time))
    for path in ["TotolinaRigV2/Skeleton2D/Root", "TotolinaRigV2/Skeleton2D/Root/Tip"]:
        var bone := scene.get_node(path) as Bone2D
        var pose := Transform2D.IDENTITY if path.ends_with("/Root") else Transform2D(0.0, Vector2(64, 0))
        _check(bone.rest == pose and bone.transform == pose, "unchanged bone rest/current pose " + path)
        _check(bone.get_length() == 64.0 and bone.get_bone_angle() == 0.0 and
            not bone.get_autocalculate_length_and_angle(), "exact bone length and angle " + path)
    scene.queue_free()
    _finish()

func _finish() -> void:
    print("GODOT_MCP_EXPORTED_ANIMATION_CHECKS=%d FAILURES=%d" % [_checks, _failures])
    quit(0 if _failures == 0 else 1)
'''

PACKAGE_TOLINA_VALIDATION = r'''extends SceneTree

const LAB_PATH := "res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"
const TEXTURES := __TEXTURES__
var _checks := 0
var _failures := 0

func _check(condition: bool, label: String) -> void:
    _checks += 1
    if not condition:
        _failures += 1
        print("FAIL exported Tolina: " + label)

func _initialize() -> void:
    _run.call_deferred()

func _run() -> void:
    var args := OS.get_cmdline_user_args()
    _check(args.size() == 2, "pack and lab-presence arguments")
    if args.size() != 2:
        _finish()
        return
    _check(ProjectSettings.load_resource_pack(args[0]), "native resource pack mounts")
    var include_lab := args[1] == "lab"
    var loaded := {}
    for piece in TEXTURES:
        var info: Array = TEXTURES[piece]
        var path := "res://assets/characters/totolina/" + String(info[0])
        var texture := ResourceLoader.load(path, "Texture2D", ResourceLoader.CACHE_MODE_REUSE) as Texture2D
        _check(texture != null, "production external texture loadable " + piece)
        if texture == null:
            continue
        _check(texture.get_class() == "CompressedTexture2D" and texture.get_script() == null,
            "native imported production texture " + piece)
        _check(texture.resource_path == path and texture.get_size() == Vector2(info[1][0], info[1][1]),
            "external PNG identity and dimensions " + piece)
        loaded[path] = texture
    _check(loaded.size() == 15, "all 15 unique production inputs loadable")
    var production := load("res://scenes/presentation/totolina_operator.tscn") as PackedScene
    _check(production != null, "production operator remains packaged and loadable")
    if production != null:
        var node := production.instantiate()
        _check(node.get_node("Visual/cat_totolina_body").texture == loaded.get(
            "res://assets/characters/totolina/body/cat_totolina_body.png"), "production cached body identity")
        node.free()
    if not include_lab:
        _check(not ResourceLoader.exists(LAB_PATH), "Tolina lab absent from normal package")
        _check(not ResourceLoader.exists("res://addons/lunitora_godot/specs/tolina_character_rig_v1.json"),
            "editor-only manifest absent from normal package")
        _finish()
        return
    var packed := load(LAB_PATH) as PackedScene
    _check(packed != null, "compiled Tolina lab loadable without tooling JSON")
    if packed == null:
        _finish()
        return
    var scene := packed.instantiate()
    root.add_child(scene)
    await process_frame
    await process_frame
    _check(scene.name == "TolinaCharacterRigLab" and scene.get_class() == "Node2D", "native lab root")
    var manifest := {
        ".": "Node2D", "TolinaRig": "Node2D", "TolinaRig/Visual": "Node2D",
        "TolinaRig/Visual/Arms": "Node2D", "TolinaRig/Visual/Eyes": "Node2D",
        "TolinaRig/AnimationPlayer": "AnimationPlayer",
    }
    for piece in TEXTURES:
        manifest["TolinaRig/Visual/" + piece] = "Sprite2D"
    var pending: Array[Node] = [scene]
    var count := 0
    while not pending.is_empty():
        var node: Node = pending.pop_back()
        var path := String(scene.get_path_to(node))
        _check(manifest.has(path) and node.get_class() == manifest.get(path), "exact native class " + path)
        _check(node.get_script() == null, "script-free " + path)
        if node != scene:
            _check(node.owner == scene, "persisted scene ownership " + path)
        count += 1
        for child in node.get_children(true):
            pending.append(child)
    _check(count == 22, "root plus exactly 21 generated nodes")
    for piece in TEXTURES:
        var sprite := scene.get_node("TolinaRig/Visual/" + piece) as Sprite2D
        var info: Array = TEXTURES[piece]
        var path := "res://assets/characters/totolina/" + String(info[0])
        _check(sprite.texture == loaded.get(path), "shared cached external texture " + piece)
        _check(sprite.visible and sprite.self_modulate == Color.WHITE and sprite.modulate.r == 1.0 and
            sprite.modulate.g == 1.0 and sprite.modulate.b == 1.0, "visible white RGB and self modulation " + piece)
        _check(sprite.texture_filter == CanvasItem.TEXTURE_FILTER_LINEAR and not sprite.centered,
            "linear filter and reviewed pivot form " + piece)
    var body := scene.get_node("TolinaRig/Visual/Body") as Sprite2D
    var overlap := scene.get_node("TolinaRig/Visual/ShoulderOverlap") as Sprite2D
    _check(body.texture == overlap.texture, "Body/ShoulderOverlap share one external body")
    _check(overlap.region_enabled and overlap.region_rect == Rect2(530, 325, 170, 95), "exact overlap region")
    var player := scene.get_node("TolinaRig/AnimationPlayer") as AnimationPlayer
    _check(player.root_node == NodePath("..") and player.get_node(player.root_node) == scene.get_node("TolinaRig"),
        "player root resolves to TolinaRig")
    _check(player.get_animation_library_list().size() == 1 and player.has_animation_library(&""), "one global library")
    _check(player.get_animation_list() == PackedStringArray(["blink"]) and not player.has_animation(&"RESET"),
        "one blink and no RESET")
    _check(player.autoplay == &"" and player.assigned_animation == &"" and player.current_animation == &"" and
        not player.is_playing() and player.get_queue().is_empty(), "unassigned stopped empty autoplay and queue")
    var library := player.get_animation_library(&"")
    _check(library.get_class() == "AnimationLibrary" and library.get_script() == null and
        library.get_animation_list_size() == 1, "one native inline library")
    var animation := player.get_animation(&"blink")
    _check(animation != null and animation.get_class() == "Animation" and animation.get_script() == null,
        "native inline animation")
    _check(animation == library.get_animation(&"blink"), "library/player exact animation identity")
    _check(animation.length == 0.24 and animation.step == 0.125 and animation.loop_mode == Animation.LOOP_NONE and
        not animation.capture_included and animation.get_marker_names().is_empty(), "length step loop capture markers")
    _check(animation.get_track_count() == 3, "exactly three tracks")
    var names := ["Rest", "Half", "Closed"]
    var times := PackedFloat32Array([0.0, 0.05, 0.095, 0.14, 0.19, 0.24])
    var values := [[1.0, 0.0, 0.0, 0.0, 0.0, 1.0], [0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]]
    for track in range(3):
        _check(animation.track_get_type(track) == Animation.TYPE_VALUE and animation.track_is_enabled(track) and
            not animation.track_is_imported(track) and not animation.track_get_interpolation_loop_wrap(track),
            "type and track flags " + names[track])
        _check(animation.track_get_path(track) == NodePath("Visual/Eyes/" + names[track] + ":modulate:a") and
            animation.track_get_interpolation_type(track) == Animation.INTERPOLATION_LINEAR and
            animation.value_track_get_update_mode(track) == Animation.UPDATE_CONTINUOUS, "path interpolation update " + names[track])
        _check(animation.track_get_key_count(track) == 6, "six keys " + names[track])
        for key in range(6):
            var value: Variant = animation.track_get_key_value(track, key)
            _check(animation.track_get_key_time(track, key) == times[key], "canonical float32 time")
            _check(typeof(value) == TYPE_FLOAT and value == values[track][key] and value >= 0.0 and value <= 1.0,
                "exact bounded float alpha")
            _check(animation.track_get_key_transition(track, key) == 1.0, "unit transition")
        var sprite := scene.get_node("TolinaRig/Visual/Eyes/" + names[track]) as Sprite2D
        _check(sprite.modulate.a == values[track][0], "persisted initial rest alpha " + names[track])
    scene.free()
    _finish()

func _finish() -> void:
    print("GODOT_MCP_EXPORTED_TOLINA_CHECKS=%d FAILURES=%d" % [_checks, _failures])
    quit(0 if _failures == 0 else 1)
'''


def addon_source_snapshot(repository: Path, project: Path) -> dict[str, str]:
    """Check the exact current helper/seed source before any disposable override."""
    result: dict[str, str] = {}
    for source in sorted((repository / ADDON).rglob("*")):
        if not source.is_file() or source.suffix not in {".gd", ".uid", ".cfg", ".tscn", ".json"}:
            continue
        relative = source.relative_to(repository)
        data = source.read_bytes()
        if (project / relative).read_bytes() != data:
            raise RuntimeError(f"Addon source snapshot differs: {relative.as_posix()}")
        result[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    return result


def copy_authored_lab(source: Path, project: Path) -> dict[str, object]:
    """Use a retained actual native-writer Save/Reopen artifact, never the real lab."""
    data = source.read_bytes()
    if not 1 <= len(data) <= 1024 * 1024:
        raise RuntimeError("Authored lab artifact exceeds the bounded fixture size")
    text = data.decode("utf-8", errors="strict")
    if "[ext_resource " in text or re.search(r"(?m)^script\s*=", text):
        raise RuntimeError("The authored lab control must be native and entirely inline")
    nodes = re.findall(r"(?m)^\[node\s+([^\r\n]+)\]$", text)
    manifest = {}
    for entry in nodes:
        fields = dict(re.findall(r'(name|type|parent)="([^"]*)"', entry))
        if not {"name", "type"}.issubset(fields):
            raise RuntimeError("Malformed authored lab node header")
        path = fields["name"] if "parent" not in fields else (
            fields["name"] if fields["parent"] == "." else fields["parent"] + "/" + fields["name"])
        if path in manifest:
            raise RuntimeError("Duplicate authored lab node path")
        manifest[path] = fields["type"]
    expected = {
        "TotolinaRigLab": "Node2D", "TotolinaRigV2": "Node2D",
        "TotolinaRigV2/Meshes": "Node2D", "TotolinaRigV2/Meshes/TestMesh": "Polygon2D",
        "TotolinaRigV2/Skeleton2D": "Skeleton2D", "TotolinaRigV2/Skeleton2D/Root": "Bone2D",
        "TotolinaRigV2/Skeleton2D/Root/Tip": "Bone2D", "TotolinaRigV2/AnimationPlayer": "AnimationPlayer",
    }
    if manifest != expected:
        raise RuntimeError("Authored export control must contain the root and exactly seven rig nodes")
    resources = re.findall(r'(?m)^\[sub_resource type="([^"]+)"', text)
    if sorted(resources) != ["Animation", "AnimationLibrary"] or "bend_tip" not in text:
        raise RuntimeError("Authored export control lacks its inline animation/library")
    destination = project / ADDON / ADDON_SCENE_CONTROLS[0]
    destination.write_bytes(data)
    return {"source": str(source.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "node_count": len(nodes), "inline_resource_count": len(resources)}


def copy_authored_tolina_lab(source: Path, project: Path) -> dict[str, object]:
    """Admit only an actual native saved 21-node rig with its fixed inline blink."""
    data = source.read_bytes()
    if not 1 <= len(data) <= 1024 * 1024:
        raise RuntimeError("Authored Tolina artifact exceeds the bounded fixture size")
    text = data.decode("utf-8", errors="strict").replace("\r\n", "\n")
    if re.search(r"(?m)^script\s*=", text) or ".json" in text:
        raise RuntimeError("Tolina package control must be native and have no JSON runtime dependency")
    nodes = re.findall(r"(?m)^\[node\s+([^\r\n]+)\]$", text)
    manifest = {}
    for entry in nodes:
        fields = dict(re.findall(r'(name|type|parent)="([^"]*)"', entry))
        if not {"name", "type"}.issubset(fields):
            raise RuntimeError("Malformed authored Tolina node header")
        path = fields["name"] if "parent" not in fields else (
            fields["name"] if fields["parent"] == "." else fields["parent"] + "/" + fields["name"])
        if path in manifest:
            raise RuntimeError("Duplicate authored Tolina node path")
        manifest[path] = fields["type"]
    expected = {"TolinaCharacterRigLab": "Node2D", "TolinaRig": "Node2D",
                "TolinaRig/Visual": "Node2D", "TolinaRig/Visual/Arms": "Node2D",
                "TolinaRig/Visual/Eyes": "Node2D", "TolinaRig/AnimationPlayer": "AnimationPlayer"}
    expected.update({"TolinaRig/Visual/" + piece: "Sprite2D" for piece in TOLINA_TEXTURE_NODES})
    if manifest != expected:
        raise RuntimeError("Tolina package control must contain root plus the exact 21-node rig")
    external = re.findall(r"(?m)^\[ext_resource\s+([^\r\n]+)\]$", text)
    paths = []
    for entry in external:
        fields = dict(re.findall(r'(type|path|id)="([^"]*)"', entry))
        if fields.get("type") != "Texture2D" or not fields.get("id"):
            raise RuntimeError("Tolina control may reference only approved external Texture2D PNGs")
        paths.append(fields.get("path"))
    expected_paths = {"res://" + TOLINA_TEXTURE_PREFIX + value[0] for value in TOLINA_TEXTURE_NODES.values()}
    if len(paths) != 15 or len(set(paths)) != 15 or set(paths) != expected_paths:
        raise RuntimeError("Tolina control must reference exactly the 15 approved external PNG paths")
    resources = re.findall(r'(?m)^\[sub_resource type="([^"]+)"', text)
    if sorted(resources) != ["Animation", "AnimationLibrary"] or '"blink"' not in text:
        raise RuntimeError("Tolina control must contain only its inline blink animation/library")
    destination = project / ADDON / ADDON_SCENE_CONTROLS[1]
    destination.write_bytes(data)
    return {"source": str(source.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "node_count": len(nodes), "inline_resource_count": len(resources),
            "external_texture_count": len(paths), "no_json_runtime_dependency": True}


def production_source_snapshot(repository: Path) -> dict[str, str]:
    """Hash production inputs without inspecting private machine/signing content."""
    sources = [repository / "project.godot", repository / "export_presets.cfg"]
    for directory in ("assets", "scenes", "scripts", "config", "localization"):
        sources.extend(path for path in (repository / directory).rglob("*") if path.is_file())
    return {path.relative_to(repository).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(sources)}


def preset_sections(source: str) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for match in re.finditer(r"(?ms)^\[preset\.(\d+)\]\r?\n(.*?)(?=^\[|\Z)", source):
        body = match.group(2)
        name = re.search(r'^name="([^"]+)"$', body, re.M)
        platform = re.search(r'^platform="([^"]+)"$', body, re.M)
        if name and platform and platform.group(1) in ("Android", "iOS"):
            if name.group(1) in result:
                raise RuntimeError("Duplicate mobile preset name")
            result[name.group(1)] = (match.group(0), body)
    if set(result) != {"Android", "iOS"}:
        raise RuntimeError("Expected the existing Android and iOS presets")
    return result


def without_addon_exclusion(source: str, section: str, body: str) -> str:
    match = re.search(r'^exclude_filter="([^"]*)"$', body, re.M)
    if not match:
        raise RuntimeError("Missing export exclusion")
    patterns = [item.strip() for item in match.group(1).split(",") if item.strip()]
    if EXCLUSION not in patterns:
        raise RuntimeError("Mobile preset lacks the required addon exclusion")
    remaining = [item for item in patterns if item != EXCLUSION]
    changed_body = body[:match.start()] + f'exclude_filter="{",".join(remaining)}"' + body[match.end():]
    changed_section = section[:len(section) - len(body)] + changed_body
    return source.replace(section, changed_section, 1)


def run_engine(command: list[str], log: Path, env: dict[str, str], timeout: int) -> None:
    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, env=env)
        try:
            result = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError(f"Godot export timed out; inspect {log}") from None
    output = log.read_text(encoding="utf-8", errors="replace")
    if result != 0 or ERROR_PATTERN.search(output):
        # Do not echo exporter diagnostics: production preset bytes may contain
        # workstation signing fields. Retained local logs are for inspection.
        raise RuntimeError(f"Godot export failed (exit {result}); inspect {log}")


def verify_authored_package(engine: str, package: Path, artifacts: Path,
                            env: dict[str, str], timeout: int, name: str) -> int:
    """Load the actual exported scene/resources natively, outside the export source project."""
    project = artifacts / "native-package-check"
    project.mkdir(exist_ok=True)
    (project / "project.godot").write_text(
        'config_version=5\n\n[application]\nconfig/name="Godot authored-package validation"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
    (project / "verify.gd").write_text(PACKAGE_ANIMATION_VALIDATION, encoding="utf-8")
    log = artifacts / f"{name}-control-native-validation.log"
    run_engine([engine, "--headless", "--path", str(project), "--script", "res://verify.gd", "--", str(package)],
               log, env, timeout)
    summaries = re.findall(r"(?m)^GODOT_MCP_EXPORTED_ANIMATION_CHECKS=(\d+) FAILURES=(\d+)$",
                           log.read_text(encoding="utf-8", errors="replace"))
    if len(summaries) != 1 or int(summaries[0][0]) < 50 or summaries[0][1] != "0":
        raise RuntimeError(f"Exported animation semantic validation failed; inspect {log}")
    return int(summaries[0][0])


def verify_tolina_package(engine: str, package: Path, artifacts: Path,
                         env: dict[str, str], timeout: int, name: str, *, include_lab: bool) -> int:
    """Load production textures and the inline blink with no manifest/helper use."""
    project = artifacts / "native-tolina-package-check"
    project.mkdir(exist_ok=True)
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Tolina native package validation"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
    mapping = json.dumps(TOLINA_TEXTURE_NODES, separators=(",", ":"))
    (project / "verify.gd").write_text(PACKAGE_TOLINA_VALIDATION.replace("__TEXTURES__", mapping), encoding="utf-8")
    log = artifacts / f"{name}-tolina-native-validation.log"
    run_engine([engine, "--headless", "--path", str(project), "--script", "res://verify.gd", "--",
                str(package), "lab" if include_lab else "excluded"], log, env, timeout)
    summaries = re.findall(r"(?m)^GODOT_MCP_EXPORTED_TOLINA_CHECKS=(\d+) FAILURES=(\d+)$",
                           log.read_text(encoding="utf-8", errors="replace"))
    minimum = 200 if include_lab else 50
    if len(summaries) != 1 or int(summaries[0][0]) < minimum or summaries[0][1] != "0":
        raise RuntimeError(f"Exported Tolina native validation failed; inspect {log}")
    return int(summaries[0][0])


def without_editor_json(control: Path, destination: Path) -> None:
    """Diagnostic control removes tooling JSON and its possible compiled target."""
    removed = {ADDON + ADDON_SPEC_CONTROL, ADDON + ADDON_SPEC_CONTROL + ".remap"}
    with zipfile.ZipFile(control) as source:
        normalized = {entry.removeprefix("res://").lstrip("/"): entry for entry in source.namelist()}
        remap = normalized.get(ADDON + ADDON_SPEC_CONTROL + ".remap")
        if remap:
            removed.update(re.findall(r'(?m)^path="res://([^"]+)"$', source.read(remap).decode("utf-8")))
        with zipfile.ZipFile(destination, "w") as target:
            for entry in source.infolist():
                if entry.filename.removeprefix("res://").lstrip("/") not in removed:
                    target.writestr(entry, source.read(entry.filename))


def compare_tolina_texture_payloads(excluded_path: Path, control_path: Path) -> dict[str, str]:
    """Require unchanged import bytes and CTEX payloads in both mobile packages."""
    paths = {TOLINA_TEXTURE_PREFIX + value[0] for value in TOLINA_TEXTURE_NODES.values()}
    result = {}
    with zipfile.ZipFile(excluded_path) as excluded, zipfile.ZipFile(control_path) as control:
        excluded_names = {entry.removeprefix("res://").lstrip("/"): entry for entry in excluded.namelist()}
        control_names = {entry.removeprefix("res://").lstrip("/"): entry for entry in control.namelist()}
        for path in sorted(paths):
            imported = path + ".import"
            if imported not in excluded_names or imported not in control_names:
                raise RuntimeError("Production texture import is missing from mobile package: " + path)
            original = excluded.read(excluded_names[imported])
            positive = control.read(control_names[imported])
            if original != positive:
                raise RuntimeError("Production texture import differs across mobile package controls: " + path)
            targets = re.findall(r'(?m)^path="res://([^"]+)"$', positive.decode("utf-8"))
            if len(targets) != 1 or targets[0] not in excluded_names or targets[0] not in control_names:
                raise RuntimeError("Production texture compiled payload is missing: " + path)
            original_payload = excluded.read(excluded_names[targets[0]])
            control_payload = control.read(control_names[targets[0]])
            if original_payload != control_payload:
                raise RuntimeError("Production texture payload changed across mobile package controls: " + path)
            result[path] = hashlib.sha256(control_payload).hexdigest()
    return result


def verify_resource_control(package: zipfile.ZipFile, normalized_entries: dict[str, str], relative: str) -> str:
    """Require a real source resource or its exported artifact, following remaps."""
    source = ADDON + relative
    if source in normalized_entries:
        return source
    remap = source + ".remap"
    if remap in normalized_entries:
        data = package.read(normalized_entries[remap]).decode("utf-8", errors="strict")
        targets = re.findall(r'(?m)^path="res://([^"]+)"$', data)
        if len(targets) != 1 or targets[0] not in normalized_entries:
            raise RuntimeError(f"Positive addon remap has no unique packaged target: {relative}")
        return targets[0]
    compiled = str(Path(source).with_suffix(".gdc" if source.endswith(".gd") else ".scn")).replace("\\", "/")
    if compiled in normalized_entries:
        return compiled
    raise RuntimeError(f"Positive actual addon-resource control is absent: {relative}")


def verify_zip(path: Path, *, excluded: bool, full_project: bool = False) -> dict[str, object]:
    with zipfile.ZipFile(path) as package:
        entries = package.namelist()
        if len(entries) != len(set(entries)):
            raise RuntimeError("Duplicate package entries")
        normalized_entries = {entry.removeprefix("res://").lstrip("/"): entry for entry in entries}
        if len(normalized_entries) != len(entries):
            raise RuntimeError("Duplicate normalized package entries")
        normalized = list(normalized_entries)
        if not any(entry.startswith("keep.tres") for entry in normalized):
            raise RuntimeError("Positive runtime-resource control is absent")
        if full_project and not any(entry in ("scenes/menu/main_menu.tscn", "scenes/menu/main_menu.tscn.remap") for entry in normalized):
            raise RuntimeError("Production main scene is absent from the package")
        addon_entries = [entry for entry in normalized if entry.startswith(ADDON)]
        if any("/.local/" in f"/{entry}" or entry.endswith("godot-auth.json") for entry in normalized):
            raise RuntimeError("Local credential fixture leaked into a package")
        if excluded and addon_entries:
            raise RuntimeError("Addon resources or remaps remain in the excluded package")
        actual_controls: dict[str, str] = {}
        if not excluded:
            if not any(entry.startswith(ADDON + "export_probe.tres") for entry in addon_entries):
                raise RuntimeError("Positive addon-resource control is absent")
            if not any(entry.startswith(ADDON + "nested/export_probe.tres") for entry in addon_entries):
                raise RuntimeError("Nested positive addon-resource control is absent")
            for resource in (*ADDON_SCRIPT_CONTROLS, *ADDON_SCENE_CONTROLS, ADDON_SPEC_CONTROL):
                actual_controls[resource] = verify_resource_control(package, normalized_entries, resource)
        # An exported .remap may lead to bytecode under .godot/exported rather
        # than the source folder. The excluded package must have no artifact
        # targeted by any addon remap in its positive-control package; checked
        # by compare_packages below.
        return {"entries": len(entries), "addon_entries": len(addon_entries), "excluded": excluded,
                "actual_addon_resource_controls": actual_controls}


def compare_packages(excluded_path: Path, control_path: Path) -> int:
    targets: set[str] = set()
    with zipfile.ZipFile(control_path) as control:
        control_names = {entry.removeprefix("res://").lstrip("/") for entry in control.namelist()}
        for entry in control.namelist():
            normalized = entry.removeprefix("res://").lstrip("/")
            if normalized.startswith(ADDON) and normalized.endswith(".remap"):
                remap = control.read(entry).decode("utf-8", errors="strict")
                for match in re.finditer(r'(?m)^path="res://([^"]+)"$', remap):
                    targets.add(match.group(1))
        if not targets.issubset(control_names):
            raise RuntimeError("Positive addon remap target is absent from its control package")
    with zipfile.ZipFile(excluded_path) as excluded:
        names = {entry.removeprefix("res://").lstrip("/") for entry in excluded.namelist()}
        if targets & names:
            raise RuntimeError("Compiled addon resource remains outside the addon folder")
    return len(targets)


def copy_runtime_snapshot(repository: Path, project: Path, *, full_project: bool) -> None:
    roots = ("addons", "assets", "config", "localization", "scenes", "scripts", "tests") if full_project else ("addons",)
    filenames = ("project.godot", "icon.svg", "icon.svg.import") if full_project else ()
    process = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *roots, *filenames],
        cwd=repository, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for name in process.stdout.decode("utf-8", errors="strict").split("\0"):
        if not name:
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Unsafe resource snapshot path")
        if any(part in {".local", ".godot", ".venv", "__pycache__"} for part in relative.parts):
            continue
        source_path = repository / relative
        if not source_path.is_file():
            continue
        # A snapshot must never follow a link to credentials outside its safe
        # resource roots. The Git inventory also excludes ignored local files.
        for component in (source_path, *source_path.parents):
            if component == repository.parent:
                break
            if component.is_symlink() or (os.name == "nt" and component.is_junction()):
                raise RuntimeError("Redirected resource snapshot path")
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--full-project", action="store_true", help="Copy current production runtime resources before exporting, without local credentials or caches")
    parser.add_argument("--authored-lab-scene", type=Path,
                        help="Retained native/public-writer saved rig+animation artifact for disposable inline export controls")
    parser.add_argument("--authored-tolina-scene", type=Path,
                        help="Retained native-writer saved 21-node Tolina rig+blink with approved external PNG references")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    engine = shutil.which(args.godot)
    if engine is None:
        parser.error("Godot not found; pass --godot /absolute/path/to/Godot")
    repository = Path(__file__).resolve().parents[2]
    addon = repository / ADDON
    if not all((addon / filename).is_file() for filename in ("plugin.cfg", *ADDON_SCRIPT_CONTROLS,
                                                            *ADDON_SCENE_CONTROLS, ADDON_SPEC_CONTROL)):
        parser.error("The v0.4 addon helpers, reviewed specification and actual lab baselines must exist")
    if args.authored_tolina_scene and not args.full_project:
        parser.error("The external production-texture control requires --full-project")
    if args.artifacts_dir:
        artifacts = args.artifacts_dir.resolve()
        if artifacts.is_relative_to(repository) and not artifacts.is_relative_to(repository / ".godot"):
            parser.error("In-project artifacts must be inside ignored .godot")
        artifacts.mkdir(parents=True, exist_ok=False)
    else:
        artifacts = Path(tempfile.mkdtemp(prefix="lunitora-godot-export-")).resolve()
    project = artifacts / "project"
    project.mkdir()
    # Tracked plus new nonignored runtime resources only. Never copy tooling,
    # source artwork, credentials, caches, signing stores, or user saves.
    copy_runtime_snapshot(repository, project, full_project=args.full_project)
    source_snapshot = addon_source_snapshot(repository, project)
    production_snapshot = production_source_snapshot(repository)
    authored_lab = copy_authored_lab(args.authored_lab_scene, project) if args.authored_lab_scene else None
    authored_tolina = copy_authored_tolina_lab(args.authored_tolina_scene, project) if args.authored_tolina_scene else None
    if not args.full_project:
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Godot MCP export validation"\n'
            'run/main_scene="res://main.tscn"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8")
        (project / "main.tscn").write_text('[gd_scene format=3]\n\n[node name="ExportValidation" type="Node"]\n', encoding="utf-8")
    (project / "keep.tres").write_text(RESOURCE, encoding="utf-8")
    (project / ADDON / "export_probe.tres").write_text(RESOURCE, encoding="utf-8")
    (project / ADDON / "nested").mkdir()
    (project / ADDON / "nested/export_probe.tres").write_text(RESOURCE, encoding="utf-8")
    local = project / "tools/lunitora_mcp/.local"
    local.mkdir(parents=True)
    (local / "export_auth_probe.tres").write_text(RESOURCE, encoding="utf-8")
    (local / "godot-auth.json").write_text('{"fixture":true}\n', encoding="utf-8")
    shutil.copy2(repository / "tools/.gdignore", project / "tools/.gdignore")
    # Copy exact presets without displaying them or altering signing/platform
    # options. Only the control's selected exclude_filter changes.
    source_bytes = (repository / "export_presets.cfg").read_bytes()
    source = source_bytes.decode("utf-8").replace("\r\n", "\n")
    presets = preset_sections(source)
    preset_path = project / "export_presets.cfg"
    preset_path.write_bytes(source_bytes)
    env = dict(os.environ)
    # Godot's exporter uses a fixed tmpproject.binary under the OS temp root.
    # Keep it private to this run so parallel editor/export fixtures cannot
    # collide or inherit another test process's temporary-file permissions.
    native_temp = artifacts / "native-temp"
    native_temp.mkdir()
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = str(native_temp)
    if os.name == "nt":
        env["APPDATA"] = str(artifacts / "userdata")
        env["LOCALAPPDATA"] = str(artifacts / "cache")
    base = [engine, "--headless", "--path", str(project)]
    print(f"ARTIFACTS: {artifacts}", flush=True)
    settings = project / "project.godot"
    original_settings = settings.read_bytes()
    if args.full_project:
        # As in the existing Kitchen runner, CSV import must create translations
        # before the editor can eagerly load them. Restore actual settings for
        # every export below; only the disposable initial import uses this.
        settings.write_bytes(re.sub(rb"(?m)^locale/translations=[^\r\n]*",
                                    b"locale/translations=PackedStringArray()", original_settings))
    try:
        run_engine(base + ["--editor", "--import", "--quit"], artifacts / "import.log", env, args.timeout)
    finally:
        settings.write_bytes(original_settings)
    report: dict[str, object] = {"godot_executable": str(Path(engine).resolve()),
                               "native_temp_directory": str(native_temp),
                               "fixture": "isolated working-tree runtime project" if args.full_project else "isolated native exporter",
                               "addon_source_sha256": source_snapshot,
                               "authored_lab_control": authored_lab,
                               "authored_tolina_control": authored_tolina,
                               "production_source_files_preserved": len(production_snapshot),
                               "executable_ios_export_device_behavior": "NOT VALIDATED / REQUIRES MAC/iOS",
                               "presets": {}}
    for name, (section, body) in presets.items():
        without = without_addon_exclusion(source, section, body)
        preset_path.write_bytes(source_bytes)
        excluded = artifacts / f"{name}-excluded.zip"
        run_engine(base + ["--export-pack", name, str(excluded)], artifacts / f"{name}-excluded.log", env, args.timeout)
        excluded_result = verify_zip(excluded, excluded=True, full_project=args.full_project)
        preset_path.write_text(without, encoding="utf-8", newline="\n")
        control = artifacts / f"{name}-control.zip"
        run_engine(base + ["--export-pack", name, str(control)], artifacts / f"{name}-control.log", env, args.timeout)
        control_result = verify_zip(control, excluded=False, full_project=args.full_project)
        if authored_lab:
            control_result["authored_animation_native_checks"] = verify_authored_package(
                engine, control, artifacts, env, args.timeout, name)
        if args.full_project:
            excluded_result["production_tolina_native_checks"] = verify_tolina_package(
                engine, excluded, artifacts, env, args.timeout, name + "-excluded", include_lab=False)
            control_result["production_texture_payload_sha256"] = compare_tolina_texture_payloads(excluded, control)
        if authored_tolina:
            control_result["authored_tolina_native_checks"] = verify_tolina_package(
                engine, control, artifacts, env, args.timeout, name + "-control", include_lab=True)
            diagnostic = artifacts / f"{name}-control-without-editor-json.zip"
            without_editor_json(control, diagnostic)
            control_result["tolina_without_json_native_checks"] = verify_tolina_package(
                engine, diagnostic, artifacts, env, args.timeout, name + "-without-json", include_lab=True)
            control_result["tolina_has_no_json_runtime_dependency"] = True
        compiled_count = compare_packages(excluded, control)
        report["presets"][name] = {"excluded": excluded_result, "control": control_result, "compiled_remap_targets_absent": compiled_count}
        print(f"PASS {name}: excluded {excluded_result['addon_entries']} addon entries; control {control_result['addon_entries']}; {compiled_count} remapped compiled resources absent", flush=True)
    preset_path.write_bytes(source_bytes)
    for relative, digest in source_snapshot.items():
        if hashlib.sha256((repository / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Repository addon sources changed during export validation")
        overridden = ((relative == ADDON + ADDON_SCENE_CONTROLS[0] and authored_lab is not None) or
                      (relative == ADDON + ADDON_SCENE_CONTROLS[1] and authored_tolina is not None))
        if not overridden:
            if hashlib.sha256((project / relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Disposable addon source snapshot changed during export validation")
    if authored_lab and hashlib.sha256((project / ADDON / ADDON_SCENE_CONTROLS[0]).read_bytes()).hexdigest() != authored_lab["sha256"]:
        raise RuntimeError("Disposable authored lab scene changed during export validation")
    if authored_tolina and hashlib.sha256((project / ADDON / ADDON_SCENE_CONTROLS[1]).read_bytes()).hexdigest() != authored_tolina["sha256"]:
        raise RuntimeError("Disposable authored Tolina scene changed during export validation")
    for relative, digest in production_snapshot.items():
        if hashlib.sha256((repository / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Repository production input changed during export validation: " + relative)
    (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EXPORT EXCLUSION: 2 native mobile preset packages and 2 positive-control packages passed; 0 skipped.", flush=True)


if __name__ == "__main__":
    main()
