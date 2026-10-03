"""Versioned non-secret local configuration and local-only Git aliases."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import uuid

MODES = ("art", "art-refresh", "art-dev", "dev", "dev-refresh", "godot", "godot-refresh")
KINDS = ("desktop", "photoshop", "udt", "godot")
SETUP_COMMAND = "python tools/lunitora_setup.py"


class ConfigurationError(ValueError):
    pass


def run(command, *, cwd=None):
    return subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)


def validate_repository(root: Path, runner=run) -> None:
    try:
        result = runner(["git", "-C", str(root), "rev-parse", "--show-toplevel"])
    except FileNotFoundError:
        raise ConfigurationError("Git is missing. Install Git for Windows/Git Bash, then rerun " + SETUP_COMMAND + ".") from None
    if result.returncode or os.path.normcase(os.path.abspath(result.stdout.strip())) != os.path.normcase(str(root.absolute())):
        raise ConfigurationError("Run setup from the expected Totolina Merge Git checkout.")
    try:
        project = (root / "project.godot").read_text(encoding="utf-8")
        bridge = json.loads((root / "tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ConfigurationError("Expected Totolina Merge project and bridge manifest are missing.") from None
    if not re.search(r'^config/name="Totolina Merge"\r?$', project, re.MULTILINE) or bridge.get("id") != "com.lunitora.photoshop.bridge":
        raise ConfigurationError("This is not the expected Totolina Merge project and bridge.")


def local_path(root: Path) -> Path:
    return root / "tools/.lunitora/config.json"


def reject_redirects(path: Path) -> None:
    """Check existing ancestors before following or creating machine-local paths."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ConfigurationError("Machine-local storage must not contain symlinks or reparse points.")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError("Duplicate local configuration field.")
        result[key] = value
    return result


def empty_config(root: Path, platform: str) -> dict:
    return {"schema_version": 1, "repository_root": str(root.absolute()),
            "platform": platform, "applications": dict.fromkeys(KINDS)}


def load_config(root: Path, platform: str, *, migrate=True) -> tuple[dict, str]:
    path = local_path(root)
    reject_redirects(path)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_object)
        except (OSError, ValueError):
            raise ConfigurationError("Invalid machine-local configuration; rerun " + SETUP_COMMAND + ".") from None
        validate_config(data, root, platform)
        return data, "already correct"
    data = empty_config(root, platform)
    old = root / "tools/operator_launcher/config.local.json"
    if migrate and old.exists():
        reject_redirects(old)
        try:
            legacy = json.loads(old.read_text(encoding="utf-8-sig"), object_pairs_hook=_object)
            if os.path.normcase(os.path.abspath(legacy["repositoryRoot"])) != os.path.normcase(str(root.absolute())):
                raise ValueError()
            for kind in KINDS:
                value = legacy.get(kind + "Exe")
                if value:
                    if not isinstance(value, str):
                        raise ValueError()
                    data["applications"][kind] = {"path": value}
        except (KeyError, TypeError, OSError, ValueError):
            raise ConfigurationError("Legacy local configuration cannot be migrated safely; rerun " + SETUP_COMMAND + ".") from None
        return data, "migration available"
    return data, "missing"


def validate_config(data: dict, root: Path, platform: str) -> None:
    if (not isinstance(data, dict) or set(data) != {"schema_version", "repository_root", "platform", "applications"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["repository_root"] != str(root.absolute()) or data["platform"] != platform
            or not isinstance(data["applications"], dict) or set(data["applications"]) != set(KINDS)):
        raise ConfigurationError("Local configuration schema/checkout/platform mismatch; rerun " + SETUP_COMMAND + ".")
    for kind, app in data["applications"].items():
        if app is not None and (not isinstance(app, dict) or set(app) - {"kind", "path", "version", "identity", "aumid"}
                                or not isinstance(app.get("path"), str)
                                or ("kind" in app and app["kind"] != kind)
                                or any(value is not None and not isinstance(value, str) for value in app.values())):
            raise ConfigurationError("Local application metadata is invalid; rerun " + SETUP_COMMAND + ".")


def load_setup_config(root: Path, platform: str, *, check=False, interactive=True,
                      prompt=input, emit=print) -> tuple[dict, str]:
    try:
        return load_config(root, platform)
    except ConfigurationError:
        if check or not interactive:
            raise
        path = local_path(root)
        reject_redirects(path)
        before = path.read_bytes() if path.is_file() else None
        if path.exists() and before is None:
            raise ConfigurationError("Local configuration is not a regular file; no automatic recovery is safe.") from None
        emit("Local configuration is invalid. Setup can preserve it and rebuild validated application selections.")
        try:
            approved = prompt("Preserve invalid configuration and rebuild? [y/N]: ").strip().lower() in ("y", "yes")
        except (EOFError, OSError):
            approved = False
        if not approved:
            raise ConfigurationError("Local configuration was preserved; rerun " + SETUP_COMMAND + " to approve rebuilding it.") from None
        if before is not None:
            with config_lock(root):
                reject_redirects(path)
                if not path.is_file() or path.read_bytes() != before:
                    raise ConfigurationError("Configuration changed during recovery; rerun " + SETUP_COMMAND + ".")
                backup = path.with_name("config-invalid-" + uuid.uuid4().hex + ".json")
                os.replace(path, backup)
            emit("Original configuration preserved in ignored local storage: " + backup.name)
        # Invalid legacy configuration remains untouched; never copy unverified fields.
        return empty_config(root, platform), "rebuild approved"


@contextmanager
def config_lock(root: Path, name="setup.lock"):
    directory = local_path(root).parent
    reject_redirects(directory)
    directory.mkdir(exist_ok=True)
    lock = directory / name
    reject_redirects(lock)
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"0")
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise ConfigurationError("Another setup/repair is active; rerun " + SETUP_COMMAND + " after it finishes.") from None
        yield
    finally:
        if acquired:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def save_config(root: Path, data: dict, expected: dict | None = None) -> bool:
    validate_config(data, root, data["platform"])
    path = local_path(root)
    payload = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with config_lock(root):
        reject_redirects(path)
        if path.exists():
            before = path.read_bytes()
            if expected is not None and json.loads(before) != expected:
                raise ConfigurationError("Configuration changed during repair; rerun " + SETUP_COMMAND + ".")
            if before == payload:
                return False
        temporary = path.with_name("config-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return True


def alias_values(platform: str, host_python=None) -> dict[str, str]:
    executable = str(host_python or getattr(sys, "_base_executable", sys.executable))
    if not os.path.isabs(executable) or any(ord(char) < 32 for char in executable):
        raise ConfigurationError("Git aliases require an absolute validated host Python path.")
    if platform == "windows":
        executable = executable.replace("\\", "/")
    return {mode: f'!{shlex.quote(executable)} -B "./tools/lunitora_launcher.py" {mode}' for mode in MODES}


def configure_aliases(root: Path, platform: str, *, check=False, runner=run, host_python=None) -> dict[str, str]:
    states = {}
    for mode, wanted in alias_values(platform, host_python).items():
        result = runner(["git", "-C", str(root), "config", "--local", "--get-all", "alias." + mode])
        if result.returncode not in (0, 1):
            raise ConfigurationError("Cannot inspect repository-local Git aliases.")
        if result.stdout.splitlines() == [wanted]:
            states[mode] = "already correct"
        elif check:
            states[mode] = "missing" if result.returncode == 1 else "update available"
        else:
            result = runner(["git", "-C", str(root), "config", "--local", "--replace-all", "alias." + mode, wanted])
            if result.returncode:
                raise ConfigurationError("Could not install repository-local alias " + mode + ".")
            states[mode] = "repaired/updated"
    return states
