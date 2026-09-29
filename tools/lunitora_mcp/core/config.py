"""Fixed loopback policy and toolkit-local setup. Never log token contents."""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
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
    if not TOKEN_PATH.exists():
        return None
    if TOKEN_PATH.resolve().parent != (ROOT / ".local"):
        raise ConfigurationError("The pairing file must be inside the toolkit's real .local directory.")
    with TOKEN_PATH.open("r", encoding="ascii") as stream:
        value = stream.read(130).strip()
    if not valid_token(value):
        raise ConfigurationError("Invalid local pairing file. Restore a valid local token before starting.")
    return value


def setup_token() -> Path:
    """Create once; preserve an existing token. No token is returned or printed."""
    TOKEN_PATH.parent.mkdir(exist_ok=True)
    if TOKEN_PATH.parent.resolve() != ROOT / ".local":
        raise ConfigurationError("The .local directory must not redirect outside the toolkit.")
    try:
        descriptor = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        load_token()
    else:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as stream:
            stream.write(secrets.token_urlsafe(48) + "\n")
    return TOKEN_PATH
