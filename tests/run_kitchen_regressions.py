#!/usr/bin/env python3
"""Run native Godot integration tests in a disposable copy, failing on engine errors.

Python standard library only. No live saves, editor cache, config or Git state is
modified. Keep the temporary directory (printed at start) for logs/screenshots.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ERROR_PATTERN = re.compile(
    r"(?:SCRIPT ERROR:|(?:^|\n)\s*ERROR:|Assertion failed|AssertionError|"
    r"FATAL|SIGSEGV|SIGABRT|Segmentation fault|CrashHandler|"
    r"Invalid (?:access|call)|previously freed|Failed loading resource)",
    re.IGNORECASE,
)


def checked_run(command, log_path, timeout=600, expected_marker=None):
    """Godot may print a script error and still exit 0: inspect output too."""
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError(f"Timed out: {log_path}")
    output = log_path.read_text(encoding="utf-8", errors="replace")
    errors = ERROR_PATTERN.search(output)
    if return_code != 0 or errors or (expected_marker and expected_marker not in output):
        print(output[-16000:])
        raise RuntimeError(f"Regression failed (exit {return_code}): {log_path}")
    print(f"PASS {log_path.name}", flush=True)
    for line in output.splitlines():
        if "checks," in line:
            print(line, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("GODOT_BIN", "godot"))
    parser.add_argument("--suite", choices=["all", "integration", "sponge", "touch", "spawn", "collection", "debug-spawn", "animation-lab", "merge-flavor", "machine", "controls", "creation-result"], default="all")
    parser.add_argument("--graphical", action="store_true", help="Also run actual portrait merge captures")
    parser.add_argument("--timeout", type=int, default=600, help="Maximum seconds per Godot process")
    parser.add_argument("--artifacts-dir", type=Path, help="Create a new artifact directory at this path")
    args = parser.parse_args()
    engine = shutil.which(args.godot)
    if not engine:
        parser.error("Godot not found; pass --godot /absolute/path/to/Godot")
    repository = Path(__file__).resolve().parents[1]
    if args.artifacts_dir:
        artifacts = args.artifacts_dir.resolve()
        if artifacts.is_relative_to(repository) and not artifacts.is_relative_to(repository / ".godot"):
            parser.error("In-project artifacts must be under .godot to avoid copying the output into itself")
        artifacts.mkdir(parents=True, exist_ok=False)
    else:
        artifacts = Path(tempfile.mkdtemp(prefix="totolinas-mystery-journey-regressions-")).resolve()
    project = artifacts / "project"
    print(f"ARTIFACTS: {artifacts}", flush=True)
    shutil.copytree(repository, project, ignore=shutil.ignore_patterns(".git", ".godot", "__pycache__"))
    user_data_name = (artifacts / "user_data").as_posix()
    if os.name == "nt":
        # Godot appends the custom name to APPDATA on Windows. These environment
        # changes affect only this runner process and its children.
        os.environ["APPDATA"] = str(artifacts)
        os.environ["LOCALAPPDATA"] = str(artifacts / "cache")
        user_data_name = "user_data"
    # This file exists only in the test copy. It cannot reset the user's saves.
    override = (
        '[application]\nconfig/use_custom_user_dir=true\n'
        f'config/custom_user_dir_name="{user_data_name}"\n')
    (project / "override.cfg").write_text(override, encoding="utf-8")
    # The editor does not use override.cfg. Suppress eager translation loading
    # in the disposable project's settings until CSV import creates them.
    settings_path = project / "project.godot"
    original_settings = settings_path.read_bytes()
    settings_path.write_bytes(re.sub(
        rb"(?m)^locale/translations=[^\r\n]*", b"locale/translations=PackedStringArray()",
        original_settings))
    base = [engine, "--headless", "--path", str(project)]
    try:
        checked_run(base + ["--editor", "--import", "--quit"], artifacts / "import.log", args.timeout)
    finally:
        settings_path.write_bytes(original_settings)
    suites = [("merge_integration_validation", "MERGE INTEGRATION:", [])]
    if args.suite == "touch":
        suites = [("touch_input_validation", "TOUCH INPUT:", [])]
    if args.suite == "spawn":
        suites = [("spawn_stage_validation", "SPAWN STAGES:", [])]
    if args.suite == "collection":
        suites = [("collection_lifecycle_validation", "COLLECTION LIFECYCLE:", [])]
    if args.suite == "creation-result":
        suites = [("creation_result_validation", "CREATION RESULT FLOW:", [])]
    if args.suite == "debug-spawn":
        suites = [("debug_spawn_validation", "DEBUG SPAWN:", [])]
    if args.suite == "animation-lab":
        suites = [("merge_effect_lab_validation", "MERGE EFFECT LAB:", [])]
    if args.suite == "merge-flavor":
        suites = [("merge_flavor_validation", "MERGE FLAVOR:", [])]
    if args.suite == "machine":
        suites = [("machine_gameplay_validation", "MACHINE GAMEPLAY:", []),
                  ("machine_interaction_lab_validation", "MACHINE INTERACTION LAB:", [])]
    if args.suite == "controls":
        suites = [("kitchen_controls_validation", "KITCHEN CONTROLS:", [])]
    if args.suite == "sponge":
        suites[0][2].append("--sponge-only")
    if args.suite == "all":
        suites += [
            ("creation_result_validation", "CREATION RESULT FLOW:", []),
            ("merge_effect_lab_validation", "MERGE EFFECT LAB:", []),
            ("merge_flavor_validation", "MERGE FLAVOR:", []),
            ("debug_spawn_validation", "DEBUG SPAWN:", []),
            ("spawn_stage_validation", "SPAWN STAGES:", []),
            ("touch_input_validation", "TOUCH INPUT:", []),
            ("kitchen_recipe_validation", "LOCKED KITCHEN RECIPES:", []),
            ("collection_lifecycle_validation", "COLLECTION LIFECYCLE:", []),
            ("world_sizing_validation", "WORLD SIZING:", []),
            ("machine_gameplay_validation", "MACHINE GAMEPLAY:", []),
            ("machine_interaction_lab_validation", "MACHINE INTERACTION LAB:", []),
            ("kitchen_controls_validation", "KITCHEN CONTROLS:", []),
        ]
    for name, marker, flags in suites:
        checked_run(base + ["--script", f"res://tests/{name}.gd", "--",
                    f"--test-output-dir={artifacts}"] + flags,
                    artifacts / f"{name}.log", args.timeout, marker)
    if args.graphical:
        if args.suite in ("all", "creation-result"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/creation_result_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_creation_result.log", args.timeout, "CREATION RESULT FLOW:")
        if args.suite == "creation-result":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "controls"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/kitchen_controls_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_kitchen_controls.log", args.timeout, "KITCHEN CONTROLS:")
        if args.suite == "controls":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "machine"):
            for name, marker in [("machine_gameplay_validation", "MACHINE GAMEPLAY:"),
                                 ("machine_interaction_lab_validation", "MACHINE INTERACTION LAB:")]:
                checked_run([engine, "--path", str(project), "--script", f"res://tests/{name}.gd", "--",
                             f"--test-output-dir={artifacts}", f"--lab-output={artifacts / 'machine-lab'}"],
                            artifacts / f"graphical_{name}.log", args.timeout, marker)
        if args.suite == "machine":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "merge-flavor"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/merge_flavor_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_merge_flavor.log", args.timeout, "MERGE FLAVOR:")
        if args.suite == "merge-flavor":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "animation-lab"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/merge_effect_lab_validation.gd", "--",
                         f"--lab-output={artifacts / 'lab'}"],
                        artifacts / "graphical_animation_lab.log", args.timeout, "MERGE EFFECT LAB:")
        if args.suite == "animation-lab":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "debug-spawn"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/debug_spawn_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_debug_spawn.log", args.timeout, "DEBUG SPAWN:")
        if args.suite == "debug-spawn":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite == "collection":
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/collection_lifecycle_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_collection.log", args.timeout, "COLLECTION LIFECYCLE:")
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        if args.suite in ("all", "spawn"):
            checked_run([engine, "--path", str(project), "--script",
                         "res://tests/spawn_stage_validation.gd", "--",
                         f"--test-output-dir={artifacts}"],
                        artifacts / "graphical_spawn_stages.log", args.timeout, "SPAWN STAGES:")
        if args.suite == "spawn":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        checked_run([engine, "--path", str(project), "--script",
                     "res://tests/touch_input_validation.gd", "--",
                     f"--test-output-dir={artifacts}"],
                    artifacts / "graphical_touch_input.log", args.timeout, "TOUCH INPUT:")
        if args.suite == "touch":
            print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)
            return
        checked_run([engine, "--path", str(project), "--script",
                     "res://tests/merge_integration_validation.gd", "--",
                     f"--test-output-dir={artifacts}", "--portraits"],
                    artifacts / "graphical_merges.log", args.timeout, "MERGE INTEGRATION:")
        for name, marker in [
            ("collection_lifecycle_validation", "COLLECTION LIFECYCLE:"),
            ("world_sizing_validation", "WORLD SIZING:"),
        ]:
            checked_run([engine, "--path", str(project), "--script",
                         f"res://tests/{name}.gd", "--", f"--test-output-dir={artifacts}"],
                        artifacts / f"graphical_{name}.log", args.timeout, marker)
    print(f"ALL REQUESTED REGRESSIONS PASSED. Logs/captures: {artifacts}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
