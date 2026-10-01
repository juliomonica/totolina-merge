#!/usr/bin/env python3
"""Validate metadata and the rig writer in an isolated native Godot editor.

Keep the printed temporary artifact directory for startup/test logs. The runner
copies only the addon and native fixture; it never copies production scenes,
local credentials, project settings, user saves, or editor configuration.
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
import sys
import tempfile

EXPECTED_CHECKS = 56
MINIMUM_RIG_EDITOR_CHECKS = 200
MINIMUM_ANIMATION_EDITOR_CHECKS = 200
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ERROR_PATTERN = re.compile(
    r"(?:\bSCRIPT ERROR:|\bERROR:|Assertion failed|AssertionError|"
    r"FATAL|SIGSEGV|SIGABRT|Segmentation fault|CrashHandler)",
    re.IGNORECASE,
)
SUMMARY_PATTERN = re.compile(r"^GODOT_MCP_INSPECTION_CHECKS=(\d+) FAILURES=(\d+)$", re.MULTILINE)
RIG_SUMMARY_PATTERN = re.compile(r"^GODOT_MCP_RIG_EDITOR_CHECKS=(\d+) FAILURES=(\d+)$", re.MULTILINE)
ANIMATION_SUMMARY_PATTERN = re.compile(r"^GODOT_MCP_ANIMATION_EDITOR_CHECKS=(\d+) FAILURES=(\d+)$", re.MULTILINE)
ADDON_FILES = (
    "plugin.cfg", "plugin.gd", "plugin.gd.uid", "bridge_client.gd",
    "bridge_client.gd.uid", "inspection.gd", "inspection.gd.uid", "rig_lab.gd", "rig_lab.gd.uid",
    "animation_writer.gd", "animation_writer.gd.uid",
)
FIXTURE_FILES = ("inspection_validation.gd", "inspection_validation.gd.uid",
                 "rig_lab_validation.gd", "rig_lab_validation.gd.uid",
                 "animation_lab_validation.gd", "animation_lab_validation.gd.uid")
LAB_PATH = "addons/lunitora_godot/labs/totolina_rig_lab.tscn"


def production_snapshot(repository: Path) -> dict[str, str]:
    """Audit source scenes/resources plus any real lab; never copy them to tests."""
    files = {repository / "project.godot", repository / "export_presets.cfg",
             repository / LAB_PATH}
    for directory in ("scenes", "resources", "assets", "scripts"):
        location = repository / directory
        if location.is_dir():
            files.update(path for path in location.rglob("*") if path.is_file())
    return {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files) if path.is_file()}


def checked_run(command: list[str], *, environment: dict[str, str], capture_path: Path,
                engine_log: Path, timeout: int) -> str:
    with capture_path.open("w", encoding="utf-8") as capture:
        try:
            process = subprocess.run(
                command, env=environment, stdout=capture, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Godot timed out; see {capture_path}") from None
    output = ANSI_PATTERN.sub("", capture_path.read_text(encoding="utf-8", errors="replace"))
    native_log = ANSI_PATTERN.sub(
        "", engine_log.read_text(encoding="utf-8", errors="replace") if engine_log.exists() else ""
    )
    if process.returncode != 0 or ERROR_PATTERN.search(output) or ERROR_PATTERN.search(native_log):
        print(output[-16000:], file=sys.stderr)
        raise RuntimeError(f"Godot validation failed (exit {process.returncode}); see {capture_path}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path, help="Explicit path to the Godot 4.7.2 executable")
    parser.add_argument("--timeout", type=int, default=60, help="Maximum seconds per isolated Godot process")
    args = parser.parse_args()
    engine = args.godot.absolute()
    if not engine.is_file():
        parser.error("Godot executable does not exist; pass --godot with its explicit path")
    if not 1 <= args.timeout <= 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    repository = Path(__file__).resolve().parents[2]
    before_snapshot = production_snapshot(repository)
    artifacts = Path(tempfile.mkdtemp(prefix="lunitora-godot-native-")).resolve()
    project = artifacts / "project"
    addon = project / "addons" / "lunitora_godot"
    fixtures = project / "tests" / "godot_mcp"
    addon.mkdir(parents=True)
    fixtures.mkdir(parents=True)
    print(f"ARTIFACTS: {artifacts}", flush=True)
    try:
        for filename in ADDON_FILES:
            shutil.copy2(repository / "addons" / "lunitora_godot" / filename, addon / filename)
        for filename in FIXTURE_FILES:
            shutil.copy2(repository / "tests" / "godot_mcp" / filename, fixtures / filename)
        manifest = {filename: hashlib.sha256((addon / filename).read_bytes()).hexdigest() for filename in ADDON_FILES}
        (artifacts / "addon-source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        lab = project / LAB_PATH
        lab.parent.mkdir(parents=True)
        lab.write_text('[gd_scene format=3]\n\n'
                       '[node name="TotolinaRigLab" type="Node2D"]\n\n'
                       '[node name="Unrelated" type="Node2D" parent="."]\n'
                       'position = Vector2(7, 9)\n', encoding="utf-8")
        (project / "project.godot").write_text(
            'config_version=5\n\n[application]\n'
            'config/name="Lunitora MCP isolated native validation"\n'
            'config/use_custom_user_dir=true\n'
            'config/custom_user_dir_name="lunitora-native-validation"\n\n'
            '[editor_plugins]\n'
            'enabled=PackedStringArray("res://addons/lunitora_godot/plugin.cfg")\n\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
            encoding="utf-8",
        )
        environment = dict(os.environ)
        for variable, directory in (("APPDATA", "appdata"), ("LOCALAPPDATA", "localappdata"),
                                    ("XDG_DATA_HOME", "xdg_data"), ("XDG_CONFIG_HOME", "xdg_config"),
                                    ("XDG_CACHE_HOME", "xdg_cache")):
            isolated_path = artifacts / directory
            isolated_path.mkdir()
            environment[variable] = str(isolated_path)
        # Godot's exporter/editor can use fixed names in OS.get_temp_path().
        # Isolate this too so independent native runs cannot collide there.
        process_temp = artifacts / "process_temp"
        process_temp.mkdir()
        for variable in ("TEMP", "TMP", "TMPDIR"):
            environment[variable] = str(process_temp)
        base = [str(engine), "--headless", "--path", str(project)]
        startup_log = artifacts / "startup-engine.log"
        checked_run(
            base + ["--log-file", str(startup_log), "--editor", "--import", "--quit"],
            environment=environment, capture_path=artifacts / "startup.log",
            engine_log=startup_log, timeout=args.timeout,
        )
        print("PASS editor startup/import/GDScript parsing", flush=True)
        fixture_log = artifacts / "inspection-engine.log"
        output = checked_run(
            base + ["--log-file", str(fixture_log), "--script", "tests/godot_mcp/inspection_validation.gd"],
            environment=environment, capture_path=artifacts / "inspection.log",
            engine_log=fixture_log, timeout=args.timeout,
        )
        summaries = SUMMARY_PATTERN.findall(output)
        if summaries != [(str(EXPECTED_CHECKS), "0")]:
            raise RuntimeError(f"Expected exactly {EXPECTED_CHECKS} native checks and zero failures; see {fixture_log}")
        print(f"GODOT_MCP_INSPECTION_CHECKS={EXPECTED_CHECKS} FAILURES=0", flush=True)
        # The acceptance controller is a second, test-only EditorPlugin. It is
        # enabled only after the separate import and original inspection gates.
        # Production plugin disable/reload tests cannot interrupt this controller.
        controller = project / "addons" / "rig_lab_validation"
        controller.mkdir()
        (controller / "plugin.cfg").write_text(
            '[plugin]\nname="Isolated rig editor acceptance"\n'
            'description="Test-only native editor controller"\nauthor="Lunitora tests"\n'
            'version="1"\nscript="../../tests/godot_mcp/rig_lab_validation.gd"\n', encoding="utf-8")
        project_settings = project / "project.godot"
        text = project_settings.read_text(encoding="utf-8")
        text = text.replace('enabled=PackedStringArray("res://addons/lunitora_godot/plugin.cfg")',
                            'enabled=PackedStringArray("res://addons/lunitora_godot/plugin.cfg", '
                            '"res://addons/rig_lab_validation/plugin.cfg")')
        project_settings.write_text(text, encoding="utf-8")
        editor_log = artifacts / "rig-editor-engine.log"
        output = checked_run(
            base + ["--log-file", str(editor_log), "--editor", f"res://{LAB_PATH}"],
            environment=environment, capture_path=artifacts / "rig-editor.log",
            engine_log=editor_log, timeout=args.timeout,
        )
        rig_summaries = RIG_SUMMARY_PATTERN.findall(output)
        if len(rig_summaries) != 1 or rig_summaries[0][1] != "0" or int(rig_summaries[0][0]) < MINIMUM_RIG_EDITOR_CHECKS:
            raise RuntimeError(f"Expected at least {MINIMUM_RIG_EDITOR_CHECKS} native editor rig checks and zero failures; see {editor_log}")
        print(f"GODOT_MCP_RIG_EDITOR_CHECKS={rig_summaries[0][0]} FAILURES=0", flush=True)
        rig_checks = int(rig_summaries[0][0])
        # Each gate uses a fresh native editor. Files are prepared only after
        # the preceding process exits, never while a scene is open in an editor.
        marker = fixtures / "root_marker.gd"
        marker.write_text("@tool\nextends Node2D\n", encoding="utf-8")
        gate_variants = (
            ("production-path", "scenes/production_like.tscn", "ProductionLike", "Node2D", False,
             "LAB_SCENE_REQUIRED"),
            ("root-name", LAB_PATH, "WrongLabRoot", "Node2D", False, "LAB_ROOT_MISMATCH"),
            ("root-class", LAB_PATH, "TotolinaRigLab", "Node", False, "LAB_ROOT_MISMATCH"),
            ("root-script", LAB_PATH, "TotolinaRigLab", "Node2D", True, "LAB_ROOT_MISMATCH"),
        )
        for label, scene_path, name, node_class, scripted, code in gate_variants:
            scene_file = project / scene_path
            scene_file.parent.mkdir(parents=True, exist_ok=True)
            resource = ('[ext_resource type="Script" path="res://tests/godot_mcp/root_marker.gd" id="1"]\n\n'
                        if scripted else "")
            scene_file.write_text('[gd_scene format=3]\n\n' + resource +
                                  f'[node name="{name}" type="{node_class}"]\n' +
                                  ('script = ExtResource("1")\n' if scripted else "") +
                                  '\n[node name="Unrelated" type="Node2D" parent="."]\n'
                                  'position = Vector2(7, 9)\n', encoding="utf-8")
            gate_log = artifacts / f"gate-{label}-engine.log"
            gate_output = checked_run(
                base + ["--log-file", str(gate_log), "--editor", f"res://{scene_path}",
                        "--", "rig-gate", code],
                environment=environment, capture_path=artifacts / f"gate-{label}.log",
                engine_log=gate_log, timeout=args.timeout,
            )
            gate_summaries = RIG_SUMMARY_PATTERN.findall(gate_output)
            if gate_summaries != [("14", "0")]:
                raise RuntimeError(f"Native editor gate acceptance failed; see {gate_log}")
            rig_checks += int(gate_summaries[0][0])
            print(f"PASS native editor {label} rejection: {gate_summaries[0][0]} checks", flush=True)
        print(f"GODOT_MCP_RIG_EDITOR_TOTAL_CHECKS={rig_checks} FAILURES=0", flush=True)
        # This hook exists only in the disposable copy. Acceptance callbacks run
        # inside the production plugin's actual normal-process admission scope.
        lab.write_text('[gd_scene format=3]\n\n[node name="TotolinaRigLab" type="Node2D"]\n', encoding="utf-8")
        (addon / "native_animation_plugin.gd").write_text(
            '@tool\nextends "res://addons/lunitora_godot/plugin.gd"\n'
            'func _poll_editor_commands() -> void:\n'
            '    for controller in get_tree().root.find_children("*", "EditorPlugin", true, false):\n'
            '        var script: Script = controller.get_script()\n'
            '        if script != null and script.resource_path == "res://tests/godot_mcp/animation_lab_validation.gd":\n'
            '            controller._normal_process_tick()\n'
            '    super._poll_editor_commands()\n', encoding="utf-8")
        (addon / "plugin.cfg").write_text('[plugin]\nname="Isolated animation writer"\n'
            'description="Disposable test hook"\nauthor="Lunitora tests"\nversion="0.3.0"\n'
            'script="native_animation_plugin.gd"\n', encoding="utf-8")
        animation_controller = project / "addons" / "animation_lab_validation"
        animation_controller.mkdir()
        (animation_controller / "plugin.cfg").write_text('[plugin]\nname="Isolated animation editor acceptance"\n'
            'description="Test-only native editor controller"\nauthor="Lunitora tests"\nversion="1"\n'
            'script="../../tests/godot_mcp/animation_lab_validation.gd"\n', encoding="utf-8")
        settings = project_settings.read_text(encoding="utf-8").replace(
            '"res://addons/rig_lab_validation/plugin.cfg"', '"res://addons/animation_lab_validation/plugin.cfg"')
        project_settings.write_text(settings, encoding="utf-8")
        animation_log = artifacts / "animation-editor-engine.log"
        animation_output = checked_run(
            [str(engine), "--path", str(project), "--log-file", str(animation_log),
             "--editor", f"res://{LAB_PATH}", "--", "animation-native"],
            environment=environment, capture_path=artifacts / "animation-editor.log",
            engine_log=animation_log, timeout=args.timeout,
        )
        animation_summaries = ANIMATION_SUMMARY_PATTERN.findall(animation_output)
        if (len(animation_summaries) != 1 or animation_summaries[0][1] != "0"
                or int(animation_summaries[0][0]) < MINIMUM_ANIMATION_EDITOR_CHECKS):
            raise RuntimeError(f"Expected at least {MINIMUM_ANIMATION_EDITOR_CHECKS} native animation checks and zero failures; see {animation_log}")
        print(f"GODOT_MCP_ANIMATION_EDITOR_CHECKS={animation_summaries[0][0]} FAILURES=0", flush=True)
        print(f"SAVED_ANIMATION_EXPORT_CONTROL: {lab}", flush=True)
        if production_snapshot(repository) != before_snapshot:
            raise RuntimeError("Production scenes/resources or the real lab changed during isolated validation")
        print(f"PASS {len(before_snapshot)} production/lab file hashes unchanged", flush=True)
        print("PASS isolated Godot MCP native validation", flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
