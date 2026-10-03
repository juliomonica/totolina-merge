"""The operator runtime is standalone Python, never the managed MCP payload."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from .configuration import ConfigurationError, run
from .environment import find_python, probe


def validated_host(root: Path, platform: str, *, runner=run) -> str:
    executable = find_python(root, platform, runner)
    data = probe(executable, runner)
    if (not data or data["prefix"] != data["base_prefix"]
            or not os.path.isabs(data.get("executable", executable))):
        raise ConfigurationError("A standalone Python 3.12 x64 host is required; rerun python tools/lunitora_setup.py.")
    path = str(Path(data.get("executable", executable)).absolute())
    if Path(path).is_relative_to(root / "tools/lunitora_mcp/.venv"):
        raise ConfigurationError("The MCP environment cannot be the operator runtime; rerun python tools/lunitora_setup.py.")
    return path


def require_current_host() -> str:
    if (sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32
            or sys.prefix != sys.base_prefix):
        raise ConfigurationError("Launcher requires standalone Python 3.12 x64; rerun python tools/lunitora_setup.py to repair local aliases.")
    return str(Path(sys.executable).absolute())
