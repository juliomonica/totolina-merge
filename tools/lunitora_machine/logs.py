"""Bounded, external Godot output logs with no recursive cleanup."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid

from .policy import LauncherError


@dataclass(frozen=True)
class OutputLogs:
    stdout: Path
    stderr: Path


def _reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def new_godot_output_logs(root: Path) -> OutputLogs:
    directory = Path(os.path.abspath(tempfile.gettempdir())) / "lunitora-godot-launcher"
    try:
        if directory.resolve().is_relative_to(root.resolve()):
            raise LauncherError("Godot output logs must stay outside the repository.")
        directory.mkdir(exist_ok=True)
        info = directory.lstat()
        if _reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise LauncherError("Godot output log directory must be a plain directory, not a reparse point.")
    except OSError:
        raise LauncherError("Godot output log storage is unavailable; nothing was launched.") from None
    try:
        cutoff = time.time() - 7 * 24 * 60 * 60
        for path in directory.iterdir():
            if not re.fullmatch(r"godot-[a-f0-9]{32}\.(stdout|stderr)\.log", path.name):
                continue
            try:
                info = path.lstat()
                if (not _reparse(info) and stat.S_ISREG(info.st_mode)
                        and info.st_nlink == 1 and info.st_mtime < cutoff):
                    path.unlink()
            except OSError:
                pass
    except OSError:
        pass
    identity = uuid.uuid4().hex
    return OutputLogs(directory / f"godot-{identity}.stdout.log", directory / f"godot-{identity}.stderr.log")
