"""Bounded, metadata-only external-tool checks; no installers or SDK services."""
from __future__ import annotations

import os
from pathlib import Path
import plistlib
import re
import shutil


def _entry(ready=False, state="missing", version=None):
    return {"ready": ready, "state": state, "version": version or "unknown"}


def _template_status(directory, names):
    try:
        ready = bool(directory and all((directory / name).is_file() for name in names))
    except OSError:
        return _entry(state="template inspection unavailable")
    return _entry(ready, "matching template files detected" if ready else "missing matching templates",
                  "4.7.2.stable" if ready else None)


def _jdk_candidates(environ):
    result = []
    if environ.get("JAVA_HOME"):
        result.append(Path(environ["JAVA_HOME"]))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if environ.get(variable):
            for vendor in ("Java", "Eclipse Adoptium", "Microsoft"):
                parent = Path(environ[variable]) / vendor
                try:
                    result.extend(path for path in parent.glob("jdk*") if path.is_dir())
                except OSError:
                    pass
    return result


def inspect_prerequisites(root: Path, platform: str, *, environ=None) -> dict:
    environ = os.environ if environ is None else environ
    result = {"node": _entry(bool(shutil.which("node")), "detected; version not checked" if shutil.which("node") else "missing"),
              "git_lfs": _entry(state="optional; no current LFS tracking")}
    jdk = []
    for directory in _jdk_candidates(environ):
        try:
            release = (directory / "release").read_text(encoding="utf-8")
            version = re.search(r'^JAVA_VERSION="([^"]+)"$', release, re.MULTILINE)
            executable = directory / "bin" / ("java.exe" if platform == "windows" else "java")
            compiler = executable.with_name("javac.exe" if platform == "windows" else "javac")
            if version and executable.is_file() and compiler.is_file():
                jdk.append(version[1])
        except (OSError, UnicodeError):
            pass
    compatible = [value for value in jdk if value.split(".", 1)[0] == "17"]
    result["jdk"] = _entry(bool(compatible), "detected JDK 17; Godot path/license not checked" if compatible else "missing compatible JDK 17", compatible[0] if compatible else None)
    sdk_paths = [Path(environ[key]) for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT") if environ.get(key)]
    if platform == "windows" and environ.get("LOCALAPPDATA"):
        sdk_paths.append(Path(environ["LOCALAPPDATA"]) / "Android/Sdk")
    elif platform == "macos":
        sdk_paths.append(Path.home() / "Library/Android/sdk")
    sdk_ok = []
    sdk_version = None
    sdk_unavailable = False
    for directory in sdk_paths:
        adb = directory / "platform-tools" / ("adb.exe" if platform == "windows" else "adb")
        try:
            properties = (directory / "platform-tools/source.properties").read_text(encoding="utf-8")
            revision = re.search(r"^Pkg.Revision\s*=\s*(\d+)([^\r\n]*)$", properties, re.MULTILINE)
        except (OSError, UnicodeError):
            revision = None
        try:
            if (revision and int(revision[1]) >= 35 and adb.is_file() and (directory / "build-tools/35.0.1").is_dir()
                    and (directory / "platforms/android-35").is_dir()
                    and (directory / "cmdline-tools").is_dir()):
                sdk_ok.append(directory)
                sdk_version = revision[1] + revision[2].strip()
        except OSError:
            sdk_unavailable = True
    sdk_state = "required SDK files detected; licenses/Godot paths/device not checked" if sdk_ok else ("SDK inspection unavailable" if sdk_unavailable else "missing required SDK files")
    result["android_sdk"] = _entry(bool(sdk_ok), sdk_state, sdk_version)
    if platform == "windows":
        data = Path(environ["APPDATA"]) / "Godot" if environ.get("APPDATA") else None
    else:
        data = Path.home() / "Library/Application Support/Godot"
    templates = data / "export_templates/4.7.2.stable" if data else None
    result["export_templates_android"] = _template_status(templates, ("android_debug.apk", "android_release.apk"))
    if platform == "macos":
        xcode = Path("/Applications/Xcode.app/Contents/Info.plist")
        try:
            with xcode.open("rb") as stream:
                metadata = plistlib.load(stream)
            if not isinstance(metadata, dict):
                raise ValueError("Invalid Xcode bundle metadata")
            result["xcode"] = _entry(True, "bundle detected; REQUIRES MAC live validation", metadata.get("CFBundleShortVersionString"))
        except (OSError, ValueError, TypeError):
            result["xcode"] = _entry(state="REQUIRES MAC")
        result["export_templates_ios"] = _template_status(templates, ("ios.zip",))
        result["export_templates_ios"]["state"] += "; REQUIRES MAC"
    else:
        result["xcode"] = _entry(state="REQUIRES MAC")
        result["export_templates_ios"] = _entry(state="REQUIRES MAC")
    return result
