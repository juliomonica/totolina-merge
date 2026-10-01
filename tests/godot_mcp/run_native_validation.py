#!/usr/bin/env python3
"""Validate the read-only addon in an isolated Godot project, using only stdlib.

Keep the printed temporary artifact directory for startup/test logs. The runner
copies only the addon and native fixture; it never copies production scenes,
local credentials, project settings, user saves, or editor configuration.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

EXPECTED_CHECKS = 56
ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ERROR_PATTERN = re.compile(
    r"(?:\bSCRIPT ERROR:|\bERROR:|Assertion failed|AssertionError|"
    r"FATAL|SIGSEGV|SIGABRT|Segmentation fault|CrashHandler)",
    re.IGNORECASE,
)
SUMMARY_PATTERN = re.compile(r"^GODOT_MCP_INSPECTION_CHECKS=(\d+) FAILURES=(\d+)$", re.MULTILINE)
ADDON_FILES = (
    "plugin.cfg", "plugin.gd", "plugin.gd.uid", "bridge_client.gd",
    "bridge_client.gd.uid", "inspection.gd", "inspection.gd.uid",
)
FIXTURE_FILES = ("inspection_validation.gd", "inspection_validation.gd.uid")


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
        print("PASS isolated Godot MCP native validation", flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
