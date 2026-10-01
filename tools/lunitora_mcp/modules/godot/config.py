"""Fixed Godot endpoint and automatic, project-bound local authentication."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets

from .security import StorageError, open_storage, pin, read_storage, write_storage

ROOT = Path(__file__).absolute().parents[2]
PROJECT_ROOT = ROOT.parents[1]
HOST = "127.0.0.1"
PORT = 43128
AUTH_PATH = ROOT / ".local" / "godot-auth.json"


class ConfigurationError(ValueError):
    def __init__(self):
        super().__init__("Local Godot configuration is unsafe or unavailable.")


@dataclass(frozen=True)
class Config:
    request_timeout_seconds: float = 5.0
    authentication_timeout_seconds: float = 5.0

    def __post_init__(self):
        for value in (self.request_timeout_seconds, self.authentication_timeout_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0.05 <= value <= 30:
                raise ConfigurationError()


@dataclass
class Credential:
    project_path: str
    project_id: str
    secret: bytes = field(repr=False)
    _pins: ExitStack | None = field(default=None, repr=False, compare=False)

    def close(self):
        if self._pins is not None:
            self._pins.close()
            self._pins = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def project_identity(project_root: Path) -> tuple[str, str]:
    path = os.path.abspath(project_root).replace("\\", "/").rstrip("/")
    if os.name == "nt":
        path = path.lower()
    if not path or len(path.encode("utf-8")) > 4096:
        raise ConfigurationError()
    return path, hashlib.sha256(path.encode("utf-8")).hexdigest()


def _unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ConfigurationError()
        result[name] = value
    return result


def ensure_credential(project_root: Path = PROJECT_ROOT) -> Credential:
    pins = None
    try:
        path, identity = project_identity(project_root)
        pins, handle, created = open_storage(project_root)
        if created:
            data = {"schema_version": 1, "project_path": path, "project_id": identity,
                    "secret": secrets.token_bytes(32).hex()}
            write_storage(handle, (json.dumps(data, separators=(",", ":")) + "\n").encode("utf-8"))
            # Retire creation's write access before retaining read-only pins.
            handle.Close()
            handle = pin(pins, Path(project_root) / "tools/lunitora_mcp/.local/godot-auth.json", directory=False)
        data = json.loads(read_storage(handle).decode("utf-8"), object_pairs_hook=_unique_fields)
        if (not isinstance(data, dict)
                or set(data) != {"schema_version", "project_path", "project_id", "secret"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1
                or data["project_path"] != path or data["project_id"] != identity
                or not isinstance(data["secret"], str)
                or re.fullmatch(r"[0-9a-f]{64}", data["secret"]) is None):
            raise ConfigurationError()
        return Credential(path, identity, bytes.fromhex(data["secret"]), pins)
    except Exception:
        if pins is not None:
            pins.close()
        raise ConfigurationError() from None
