"""Fixed loopback policy and toolkit-local setup. Never log token contents."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tomllib
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 43127
# Client hostname matches the UXP allowlist; the listener still binds to HOST.
ENDPOINT = f"ws://localhost:{PORT}"
TOKEN_PATH = ROOT / ".local" / "pairing-token.txt"


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    request_timeout_seconds: float = 5.0
    authentication_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        for value in (self.request_timeout_seconds, self.authentication_timeout_seconds):
            if type(value) not in (int, float) or not 0.05 <= value <= 30.0:
                raise ConfigurationError("Timeouts must be finite numbers between 0.05 and 30 seconds.")


def load_config(path: Path | None = None) -> Config:
    if path is None:
        return Config()
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if set(data) - {"request_timeout_seconds", "authentication_timeout_seconds"}:
        raise ConfigurationError("Only timeout settings may be configured; endpoint and token path are fixed.")
    return Config(**data)


def valid_token(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{64}", value) is not None


def load_token() -> str | None:
    # A present dedicated token takes precedence; never fall back on corruption.
    protected = ROOT / ".local" / "photoshop-auth" / "pairing-token.txt"
    path = protected if protected.exists() or protected.is_symlink() else TOKEN_PATH
    if path == protected and os.name == "nt":
        import sys
        sys.path.insert(0, str(ROOT.parent))
        try:
            from lunitora_machine import authentication as auth
            from lunitora_machine import native_credentials as security
            payload = auth._read_protected(ROOT.parents[1], "pairing-token.txt", security)
            if payload is None:
                raise ConfigurationError("Protected pairing storage is unavailable.")
            auth._validate_photoshop(payload, __import__(__name__, fromlist=["valid_token"]))
            return payload.decode("ascii").strip()
        except Exception:
            raise ConfigurationError("Protected pairing storage is unsafe or unavailable.") from None
        finally:
            sys.path.pop(0)
    return _load_token_path(path)


def _load_token_path(path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink() or path.parent.is_symlink() or path.resolve().parent not in (ROOT / ".local", ROOT / ".local" / "photoshop-auth") or (ROOT / ".local").resolve() != ROOT / ".local":
        raise ConfigurationError("The pairing file must be inside the toolkit's real .local directory.")
    with path.open("r", encoding="ascii") as stream:
        value = stream.read(130).strip()
    if not valid_token(value):
        raise ConfigurationError("Invalid local pairing file. Restore a valid local token before starting.")
    return value


def setup_token() -> Path:
    """Delegate to the reviewed setup writer; never create insecure runtime tokens."""
    import sys
    sys.path.insert(0, str(ROOT.parent))
    try:
        from lunitora_machine import authentication as auth
        result = auth.provision_authentication(ROOT.parents[1],
            "windows" if os.name == "nt" else "macos", ("photoshop",))
        if not result["photoshop"]["ready"]:
            raise ConfigurationError("Run python tools/lunitora_setup.py; protected pairing is unavailable.")
        return ROOT.parents[1] / auth.storage_for(ROOT.parents[1], "pairing-token.txt") / "pairing-token.txt"
    finally:
        sys.path.pop(0)
