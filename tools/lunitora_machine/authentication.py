"""Provision reviewed local credentials without exposing secrets."""
from __future__ import annotations

from contextlib import ExitStack
import importlib
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sys
import warnings

from .configuration import reject_redirects, run

CAPABILITIES = {"godot": "godot-auth.json", "photoshop": "pairing-token.txt"}
STORAGE = Path("tools/lunitora_mcp/.local")


class AuthenticationError(ValueError):
    """Deliberately omit operating-system/credential contents from diagnostics."""


class PairingInputError(AuthenticationError):
    def __init__(self):
        super().__init__("Secret input was cancelled, invalid or unavailable; no credential changed. Rerun setup in an interactive terminal.")


def _status(ready, state, reason):
    return {"ready": ready, "state": state, "reason": reason}


def _reviewed_modules():
    toolkit = Path(__file__).absolute().parents[1] / "lunitora_mcp"
    sys.path.insert(0, str(toolkit))
    try:
        config = importlib.import_module("modules.godot.config")
        photoshop = importlib.import_module("core.config")
        for module in (config, photoshop):
            if not Path(module.__file__).absolute().is_relative_to(toolkit):
                raise AuthenticationError()
        from . import native_credentials as security
        return config, security, photoshop
    finally:
        sys.path.pop(0)


def _guard_storage(root: Path, filename: str, runner) -> None:
    root = Path(os.path.abspath(root))
    local = root / STORAGE
    reject_redirects(local / filename)
    # Reject tracked material even if an ignore rule would otherwise match it.
    tracked = runner(["git", "-C", str(root), "ls-files", "-z", "--", STORAGE.as_posix()])
    if tracked.returncode or tracked.stdout:
        raise AuthenticationError()
    ignored = runner(["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--",
                      (STORAGE / filename).as_posix()])
    if ignored.returncode:
        raise AuthenticationError()


def _missing(error) -> bool:
    return isinstance(error, FileNotFoundError) or getattr(error, "winerror", None) in (2, 3)


def _pin_ancestors(root: Path, stack: ExitStack, security) -> Path:
    root = Path(os.path.abspath(root))
    current = Path(root.anchor)
    security.pin(stack, current, directory=True)
    for part in root.parts[1:]:
        current /= part
        security.pin(stack, current, directory=True)
    for part in ("tools", "lunitora_mcp"):
        current /= part
        security.pin(stack, current, directory=True)
    return current / ".local"


def _read_protected(root: Path, filename: str, security) -> bytes | None:
    """Read through read-only pinned handles; missing storage stays missing."""
    with ExitStack() as stack:
        local = _pin_ancestors(root, stack, security)
        try:
            directory = security.pin(stack, local, directory=True)
        except Exception as error:
            if _missing(error):
                return None
            raise
        security.validate_acl(directory)
        try:
            handle = security.pin(stack, local / filename, directory=False)
        except Exception as error:
            if _missing(error):
                return None
            raise
        security.validate_acl(handle)
        if filename == CAPABILITIES["photoshop"]:
            _, _, file, _, _ = security._apis()
            file.SetFilePointer(handle, 0, 0)
            return file.ReadFile(handle, 4097)[1]
        return security.read_storage(handle)


def _unique_fields(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise AuthenticationError()
        data[key] = value
    return data


def _validate_godot(payload: bytes, root: Path, config) -> None:
    path, identity = config.project_identity(root)
    data = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_fields)
    if (not isinstance(data, dict)
            or set(data) != {"schema_version", "project_path", "project_id", "secret"}
            or type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["project_path"] != path or data["project_id"] != identity
            or not isinstance(data["secret"], str)
            or re.fullmatch(r"[0-9a-f]{64}", data["secret"]) is None):
        raise AuthenticationError()


def _validate_photoshop(payload: bytes, photoshop) -> None:
    if len(payload) > 130 or not photoshop.valid_token(payload.decode("ascii").strip()):
        raise AuthenticationError()


def pairing_instructions(root: Path, emit=print) -> None:
    emit("Photoshop is required to run Art. UXP Developer Tool (UDT) is Adobe's utility for loading, developing and debugging the Lunitora UXP Photoshop plugin.")
    emit("UDT is required for developer plugin loading and git art-dev; an installed packaged plugin does not need UDT for daily use.")
    emit("Normally this is one-time pairing per machine. The bridge token is this machine's pairing/authentication credential, not an Adobe password.")
    emit("1. In Adobe Creative Cloud Desktop, All apps, install UXP Developer Tools. In Photoshop, Edit > Preferences > Plugins > Enable Developer Mode, then restart Photoshop after protecting unsaved work. Enable UDT's first-run Developer Mode prompt yourself.")
    emit("2. In UDT choose Add Plugin, select " + str(root / "tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json") + ", then Load.")
    emit("3. In Photoshop open Plugins > Lunitora Photoshop Bridge. The panel only accepts a token; it does not generate or reveal one.")
    emit("4. Enter an existing token privately below, or press Enter to generate this machine's token. Setup stores it only in the ignored protected credential file.")
    emit("5. Privately open " + str(root / STORAGE / CAPABILITIES["photoshop"]) + " after setup, copy it into the panel's Pairing token password field, then close the file without changes.")
    emit("6. Trust/reload the project in Codex explicitly so its MCP server starts; choose Connect / Reconnect. Confirm Connected and Pairing saved securely on this computer. Never paste the token into Codex config, logs or chat.")


def read_pairing_token(secret_prompt=None) -> str | None:
    """Reject getpass's echoing fallback and redact all input failures."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            value = (secret_prompt or getpass.getpass)(
                "Photoshop bridge token (hidden; Enter generates a new machine token): ")
        if not isinstance(value, str):
            raise AuthenticationError()
        value = value.strip()
        if not value:
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{64}", value) is None:
            raise AuthenticationError()
        return value
    except (Exception, KeyboardInterrupt):
        raise PairingInputError() from None


def _replace_pairing(root, security, photoshop, token, expected) -> bool:
    _, con, file, _, nt = security._apis()
    with ExitStack() as stack:
        local = _pin_ancestors(root, stack, security)
        security.validate_acl(security.pin(stack, local, directory=True))
        handle = file.CreateFile(str(local / CAPABILITIES["photoshop"]),
                                 con.GENERIC_READ | con.GENERIC_WRITE | nt.READ_CONTROL,
                                 0, None, con.OPEN_EXISTING, 0x00200000, None)
        stack.callback(handle.Close)
        info = file.GetFileInformationByHandle(handle)
        if info[0] & (0x400 | 0x10) or info[7] != 1 or info[5] or info[6] > 4096:
            raise AuthenticationError()
        security.validate_acl(handle)
        file.SetFilePointer(handle, 0, 0)
        _, current = file.ReadFile(handle, 4097)
        if current != expected:
            raise AuthenticationError()
        if token is not None and current.decode("ascii", errors="replace").strip() == token:
            return False
        payload = ((token or secrets.token_urlsafe(48)) + "\n").encode("ascii")
        _validate_photoshop(payload, photoshop)
        if payload == current:
            return False
        try:
            file.SetFilePointer(handle, 0, 0)
            security.write_storage(handle, payload)
            file.SetEndOfFile(handle)
            file.FlushFileBuffers(handle)
        except Exception:
            try:
                file.SetFilePointer(handle, 0, 0)
                if current:
                    security.write_storage(handle, current)
                file.SetEndOfFile(handle)
                file.FlushFileBuffers(handle)
            except Exception:
                pass
            raise AuthenticationError() from None
        return True


def _store_pairing(root: Path, security, photoshop, *, token=None, expected=None) -> bool:
    """The existing token format, protected before any token bytes are written."""
    if expected is not None:
        return _replace_pairing(root, security, photoshop, token, expected)
    _, _, file, _, _ = security._apis()
    with ExitStack() as stack:
        local = _pin_ancestors(root, stack, security)
        try:
            file.CreateDirectory(str(local), security.protected_attributes(directory=True))
        except Exception as error:
            if getattr(error, "winerror", None) != 183:
                raise AuthenticationError() from None
        security.validate_acl(security.pin(stack, local, directory=True))
        path = local / CAPABILITIES["photoshop"]
        try:
            handle = security.pin(stack, path, directory=False, create=True)
            created = True
        except Exception as error:
            if getattr(error, "winerror", None) not in (80, 183):
                raise AuthenticationError() from None
            handle = security.pin(stack, path, directory=False)
            created = False
        security.validate_acl(handle)
        if created:
            payload = ((token or secrets.token_urlsafe(48)) + "\n").encode("ascii")
            _validate_photoshop(payload, photoshop)
            security.write_storage(handle, payload)
            handle.Close()
            handle = security.pin(stack, path, directory=False)
        stored = security.read_storage(handle)
        _validate_photoshop(stored, photoshop)
        if not created and token is not None and stored.decode("ascii").strip() != token:
            raise AuthenticationError()
        return created


def _create_pairing(root: Path, security, photoshop) -> bool:
    return _store_pairing(root, security, photoshop)


def _create_godot(root: Path, security, config) -> bool:
    stack, handle, created = security.open_storage(root)
    with stack:
        if created:
            path, identity = config.project_identity(root)
            payload = (json.dumps({"schema_version": 1, "project_path": path,
                                  "project_id": identity, "secret": secrets.token_hex(32)},
                                 sort_keys=True) + "\n").encode("utf-8")
            _validate_godot(payload, root, config)
            security.write_storage(handle, payload)
        _validate_godot(security.read_storage(handle), root, config)
    return created


def provision_authentication(root: Path, platform_name: str, capabilities, *, check=False,
                             runner=run, interactive=False, secret_prompt=None, emit=print,
                             replace_photoshop=False) -> dict[str, dict]:
    """Return non-secret statuses only; failures remain local to each capability."""
    requested = tuple(dict.fromkeys(capabilities))
    if any(name not in CAPABILITIES for name in requested):
        raise ValueError("Only reviewed Godot and Photoshop local authentication is supported.")
    if platform_name == "macos":
        return {name: _status(False, "REQUIRES MAC",
                             "Authentication storage and live pairing require Mac validation; no credentials changed.")
                for name in requested}
    if platform_name != "windows" or os.name != "nt":
        return {name: _status(False, "unsupported", "Protected local authentication requires Windows.")
                for name in requested}
    if not requested:
        return {}
    try:
        config, security, photoshop = _reviewed_modules()
    except Exception:
        return {name: _status(False, "blocked", "Reviewed authentication dependencies are unavailable; rerun setup.")
                for name in requested}
    statuses = {}
    for name in requested:
        try:
            filename = CAPABILITIES[name]
            _guard_storage(root, filename, runner)
            payload = _read_protected(root, filename, security)
            if name == "photoshop":
                valid = False
                if payload is not None:
                    try:
                        _validate_photoshop(payload, photoshop)
                        valid = True
                    except Exception:
                        pass
                if valid and (not replace_photoshop or check):
                    statuses[name] = _status(True, "already correct", "Protected machine-local token is valid and preserved; live bridge acceptance remains unverified.")
                    continue
                if check:
                    statuses[name] = _status(False, "creation available" if payload is None else "pairing required", "Run python tools/lunitora_setup.py for private one-time machine pairing; no prompt or credential change occurred. See docs/MACHINE_SETUP.md, Photoshop Pairing.")
                    continue
                if interactive:
                    pairing_instructions(root, emit)
                    if payload is not None:
                        emit("This will replace the current protected token only after hidden input. Cancel to preserve it; reconnect the Photoshop panel and refresh MCP after replacement.")
                    token = read_pairing_token(secret_prompt)
                    _guard_storage(root, filename, runner)
                    changed = _store_pairing(root, security, photoshop, token=token, expected=payload)
                elif payload is None and not replace_photoshop:
                    changed = _create_pairing(root, security, photoshop)
                else:
                    raise PairingInputError()
                statuses[name] = _status(True, "paired locally" if changed else "already correct", "Protected token is stored. Pair the Photoshop panel privately; live bridge acceptance remains unverified.")
                continue
            if payload is not None:
                if name == "godot":
                    _validate_godot(payload, root, config)
                else:
                    _validate_photoshop(payload, photoshop)
                statuses[name] = _status(True, "already correct",
                                         "Protected machine-local credential is valid and preserved; live authentication unverified.")
            elif check:
                statuses[name] = _status(False, "creation available",
                                         "Setup can create a protected machine-local credential; no credential was created.")
            else:
                if name == "godot":
                    created = _create_godot(root, security, config)
                else:
                    created = _create_pairing(root, security, photoshop)
                statuses[name] = _status(True, "created" if created else "already correct",
                                         "Protected machine-local credential is ready; live authentication unverified.")
        except PairingInputError:
            statuses[name] = _status(False, "pairing required", str(PairingInputError()))
        except Exception:
            statuses[name] = _status(False, "blocked",
                                     "Authentication storage is unsafe, tracked, malformed or unavailable; review existing storage. Setup will not repair ACLs or rotate credentials.")
    return statuses
