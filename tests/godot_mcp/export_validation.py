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
ADDON_SCRIPT_CONTROLS = ("plugin.gd", "bridge_client.gd", "inspection.gd", "rig_lab.gd", "animation_writer.gd")
ADDON_SCENE_CONTROLS = ("labs/totolina_rig_lab.tscn",)
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


def addon_source_snapshot(repository: Path, project: Path) -> dict[str, str]:
    """Check the exact current helper/seed source before any disposable override."""
    result: dict[str, str] = {}
    for source in sorted((repository / ADDON).rglob("*")):
        if not source.is_file() or source.suffix not in {".gd", ".uid", ".cfg", ".tscn"}:
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
            for resource in (*ADDON_SCRIPT_CONTROLS, *ADDON_SCENE_CONTROLS):
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
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    engine = shutil.which(args.godot)
    if engine is None:
        parser.error("Godot not found; pass --godot /absolute/path/to/Godot")
    repository = Path(__file__).resolve().parents[2]
    addon = repository / ADDON
    if not all((addon / filename).is_file() for filename in ("plugin.cfg", *ADDON_SCRIPT_CONTROLS, *ADDON_SCENE_CONTROLS)):
        parser.error("The v0.3 addon helpers and actual rig-lab fixture must exist before package validation")
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
    authored_lab = copy_authored_lab(args.authored_lab_scene, project) if args.authored_lab_scene else None
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
        compiled_count = compare_packages(excluded, control)
        report["presets"][name] = {"excluded": excluded_result, "control": control_result, "compiled_remap_targets_absent": compiled_count}
        print(f"PASS {name}: excluded {excluded_result['addon_entries']} addon entries; control {control_result['addon_entries']}; {compiled_count} remapped compiled resources absent", flush=True)
    preset_path.write_bytes(source_bytes)
    for relative, digest in source_snapshot.items():
        if hashlib.sha256((repository / relative).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Repository addon sources changed during export validation")
        if relative != ADDON + ADDON_SCENE_CONTROLS[0] or authored_lab is None:
            if hashlib.sha256((project / relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError("Disposable addon source snapshot changed during export validation")
    if authored_lab and hashlib.sha256((project / ADDON / ADDON_SCENE_CONTROLS[0]).read_bytes()).hexdigest() != authored_lab["sha256"]:
        raise RuntimeError("Disposable authored lab scene changed during export validation")
    (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EXPORT EXCLUSION: 2 native mobile preset packages and 2 positive-control packages passed; 0 skipped.", flush=True)


if __name__ == "__main__":
    main()
