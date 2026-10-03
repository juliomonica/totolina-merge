"""Bounded macOS bundle metadata support; native control remains unvalidated."""
from __future__ import annotations

import plistlib
import re
from pathlib import Path
from xml.parsers.expat import ExpatError

from lunitora_machine.policy import LauncherError


class MacPlatform:
    name = "macos"

    def validate_application(self, kind: str, path: str) -> dict:
        if kind not in {"desktop", "godot", "photoshop", "udt"}:
            raise LauncherError("Unknown application kind.")
        bundle = Path(path).expanduser()
        if not bundle.is_absolute() or bundle.suffix.lower() != ".app":
            raise LauncherError("Select an absolute macOS .app bundle path.")
        bundle = bundle.resolve()
        metadata = bundle / "Contents" / "Info.plist"
        try:
            if not metadata.is_file() or metadata.stat().st_size > 1024 * 1024:
                raise ValueError("Missing or oversized bundle metadata")
            with metadata.open("rb") as stream:
                info = plistlib.load(stream)
            if not isinstance(info, dict):
                raise ValueError("Invalid bundle metadata object")
            identity = info.get("CFBundleIdentifier")
            version = info.get("CFBundleShortVersionString") or info.get("CFBundleVersion")
            if not isinstance(identity, str) or not identity:
                raise ValueError("Missing bundle identity")
            if not isinstance(version, str) or not version:
                raise ValueError("Missing bundle version")
        except (OSError, ValueError, TypeError, ExpatError, plistlib.InvalidFileException) as error:
            raise LauncherError("Application bundle metadata is missing or invalid.") from error
        label = " ".join(value for value in (
            bundle.stem, identity, info.get("CFBundleName"), info.get("CFBundleDisplayName"))
            if isinstance(value, str)).casefold()
        if kind == "godot" and (
            identity != "org.godotengine.godot"
            or not re.fullmatch(r"4\.7\.2(?:[.-]stable[.-]official(?:[.-][A-Za-z0-9]+)?)?", version)
        ):
            raise LauncherError("Select the project-compatible Godot 4.7.2 application bundle.")
        if kind == "photoshop":
            match = re.match(r"^(\d+)\.(\d+)(?:\.|$)", version)
            if not identity.lower().startswith("com.adobe.photoshop") or not match or (
                int(match[1]), int(match[2])) < (27, 10):
                raise LauncherError("Photoshop 27.10 or newer is required.")
        if kind == "desktop" and (not identity.lower().startswith("com.openai.")
                                  or not any(name in label for name in ("codex", "chatgpt", "com.openai.chat"))):
            raise LauncherError("Select the OpenAI desktop application bundle.")
        if kind == "udt" and (not identity.lower().startswith("com.adobe.") or "uxp" not in label
                              or not any(name in label for name in ("developer", "devtools"))):
            raise LauncherError("Select the Adobe UXP Developer Tool application bundle.")
        return {"kind": kind, "path": str(bundle), "version": version, "identity": identity}

    def discover(self, kind: str, configured: dict | None = None) -> list[dict]:
        candidates: list[Path] = []
        current = configured
        if isinstance(current, dict) and current.get("path"):
            candidates.append(Path(current["path"]))
        for directory in (Path("/Applications"), Path.home() / "Applications"):
            try:
                entries = sorted(directory.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.suffix.lower() == ".app":
                    candidates.append(entry)
                elif entry.is_dir() and not entry.is_symlink() and entry.name.startswith("Adobe "):
                    try:
                        candidates.extend(sorted(entry.glob("*.app")))
                    except OSError:
                        continue
        result: list[dict] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                app = self.validate_application(kind, str(candidate))
            except LauncherError:
                continue
            if app["path"] not in seen:
                seen.add(app["path"])
                result.append(app)
        return result

    def processes(self) -> list:
        raise LauncherError("REQUIRES MAC: native process inspection has not been validated.")

    def port_owners(self, port: int) -> list[int]:
        raise LauncherError("REQUIRES MAC: native port ownership inspection has not been validated.")

    def request_close(self, process) -> None:
        raise LauncherError("REQUIRES MAC: desktop close/ownership behavior has not been validated.")

    def stop_verified(self, process) -> None:
        raise LauncherError("REQUIRES MAC: verified process termination has not been validated.")

    def spawn_application(self, app: dict, cwd: Path):
        raise LauncherError("REQUIRES MAC: native application activation has not been validated.")

    def detached_flags(self) -> dict:
        # This is the future POSIX child flag, not an accepted native launcher.
        return {"start_new_session": True}
