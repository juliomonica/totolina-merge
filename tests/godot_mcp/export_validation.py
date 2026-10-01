#!/usr/bin/env python3
"""Verify real Godot Android/iOS data packages exclude the editor addon.

Runs the native --export-pack path twice per existing mobile preset in an
isolated resource fixture (or --full-project runtime copy): with the repository's exact preset bytes, then with
only that preset's addon exclusion removed as a positive control. No templates,
signing, SDK, device, or executable export is requested. The addon source is
copied, but editor plugins stay disabled and no real credential is copied.
"""
from __future__ import annotations

import argparse
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
ERROR_PATTERN = re.compile(r"(?im)(?:^\s*(?:SCRIPT ERROR:|ERROR:)|FATAL|CrashHandler)")
RESOURCE = '[gd_resource type="Resource" format=3]\n\n[resource]\n'


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


def verify_zip(path: Path, *, excluded: bool, full_project: bool = False) -> dict[str, int | bool]:
    with zipfile.ZipFile(path) as package:
        entries = package.namelist()
        if len(entries) != len(set(entries)):
            raise RuntimeError("Duplicate package entries")
        normalized = [entry.removeprefix("res://").lstrip("/") for entry in entries]
        if not any(entry.startswith("keep.tres") for entry in normalized):
            raise RuntimeError("Positive runtime-resource control is absent")
        if full_project and not any(entry in ("scenes/menu/main_menu.tscn", "scenes/menu/main_menu.tscn.remap") for entry in normalized):
            raise RuntimeError("Production main scene is absent from the package")
        addon_entries = [entry for entry in normalized if entry.startswith(ADDON)]
        if any("/.local/" in f"/{entry}" or entry.endswith("godot-auth.json") for entry in normalized):
            raise RuntimeError("Local credential fixture leaked into a package")
        if excluded and addon_entries:
            raise RuntimeError("Addon resources or remaps remain in the excluded package")
        if not excluded:
            if not any(entry.startswith(ADDON + "export_probe.tres") for entry in addon_entries):
                raise RuntimeError("Positive addon-resource control is absent")
            if not any(entry.startswith(ADDON + "nested/export_probe.tres") for entry in addon_entries):
                raise RuntimeError("Nested positive addon-resource control is absent")
            for script in ("plugin.gd", "bridge_client.gd", "inspection.gd"):
                if not any(entry in (ADDON + script, ADDON + script + ".remap") or
                           entry == ADDON + script[:-3] + ".gdc" for entry in addon_entries):
                    raise RuntimeError(f"Positive addon-script control is absent: {script}")
        # An exported .remap may lead to bytecode under .godot/exported rather
        # than the source folder. The excluded package must have no artifact
        # targeted by any addon remap in its positive-control package; checked
        # by compare_packages below.
        return {"entries": len(entries), "addon_entries": len(addon_entries), "excluded": excluded}


def compare_packages(excluded_path: Path, control_path: Path) -> int:
    targets: set[str] = set()
    with zipfile.ZipFile(control_path) as control:
        for entry in control.namelist():
            normalized = entry.removeprefix("res://").lstrip("/")
            if normalized.startswith(ADDON) and normalized.endswith(".remap"):
                remap = control.read(entry).decode("utf-8", errors="strict")
                for match in re.finditer(r'(?m)^path="res://([^"]+)"$', remap):
                    targets.add(match.group(1))
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
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    engine = shutil.which(args.godot)
    if engine is None:
        parser.error("Godot not found; pass --godot /absolute/path/to/Godot")
    repository = Path(__file__).resolve().parents[2]
    addon = repository / ADDON
    if not all((addon / filename).is_file() for filename in ("plugin.cfg", "plugin.gd", "bridge_client.gd", "inspection.gd")):
        parser.error("The v0.1 addon must exist before package validation")
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
    report: dict[str, object] = {"godot_executable": str(Path(engine).resolve()), "fixture": "isolated working-tree runtime project" if args.full_project else "isolated native exporter", "presets": {}}
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
        compiled_count = compare_packages(excluded, control)
        report["presets"][name] = {"excluded": excluded_result, "control": control_result, "compiled_remap_targets_absent": compiled_count}
        print(f"PASS {name}: excluded {excluded_result['addon_entries']} addon entries; control {control_result['addon_entries']}; {compiled_count} remapped compiled resources absent", flush=True)
    preset_path.write_bytes(source_bytes)
    (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("EXPORT EXCLUSION: 2 native mobile preset packages and 2 positive-control packages passed; 0 skipped.", flush=True)


if __name__ == "__main__":
    main()
