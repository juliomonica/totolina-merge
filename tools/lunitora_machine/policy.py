"""Pure, fail-closed Windows process and command-line admission rules."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import ntpath
import os
from pathlib import Path
import re


class LauncherError(RuntimeError):
    """An operator-safe diagnostic; never include arbitrary process arguments."""


@dataclass(frozen=True)
class Process:
    pid: int
    parent_pid: int
    created: int | None
    executable: str | None
    command_line: str | None
    name: str


def absolute_local_path(value: object) -> bool:
    return isinstance(value, str) and "\x00" not in value and re.match(r"^[A-Za-z]:[\\/]", value) is not None


def same_path(left: object, right: object) -> bool:
    if not absolute_local_path(left) or not absolute_local_path(right):
        return False
    try:
        left = ntpath.normpath(left).rstrip("\\/")
        right = ntpath.normpath(right).rstrip("\\/")
        if os.name == "nt":
            compare = ctypes.WinDLL("kernel32", use_last_error=True).CompareStringOrdinal
            compare.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_bool]
            compare.restype = ctypes.c_int
            return compare(left, -1, right, -1, True) == 2
        # Do not use Unicode casefold: expanding one character can alias another
        # Windows path. Non-Windows policy tests conservatively fold ASCII only.
        lower = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
        return left.translate(lower) == right.translate(lower)
    except (TypeError, ValueError):
        return False


def process_identity(left: Process, right: Process) -> bool:
    return (type(left.pid) is int and type(right.pid) is int and left.pid > 0 and left.pid == right.pid
            and type(left.created) is int and type(right.created) is int and left.created > 0 and left.created == right.created
            and same_path(left.executable, right.executable))


def owned_descendants(processes: list[Process], parents: list[Process]) -> list[Process]:
    owned = {item.pid: item for item in parents if item.pid > 0}
    initial = set(owned)
    while True:
        added = False
        for item in processes:
            parent = owned.get(item.parent_pid)
            if (item.pid > 0 and item.pid not in owned and parent is not None
                    and type(parent.created) is int and type(item.created) is int
                    and 0 < parent.created <= item.created):
                owned[item.pid] = item
                added = True
        if not added:
            return [item for pid, item in owned.items() if pid not in initial]


def windows_arguments(command_line: object) -> list[str]:
    """Accept only whole quoted arguments or bare words, never mixed quoting."""
    if not isinstance(command_line, str) or not command_line or "\r" in command_line or "\n" in command_line:
        return []
    remaining = command_line.strip()
    arguments = []
    while remaining:
        match = re.match(r'^(?:"([^"\r\n]*)"|([^\s"]+))(?=\s|$)', remaining)
        if match is None:
            return []
        quoted, bare = match.groups()
        if quoted is not None and quoted.endswith("\\"):
            return []
        arguments.append(quoted if quoted is not None else bare)
        remaining = remaining[match.end():].lstrip()
    return arguments


def godot_editor_command(process: Process, executable: str, root: str | Path) -> bool:
    if not same_path(process.executable, executable):
        return False
    argv = windows_arguments(process.command_line)
    if len(argv) < 2 or not same_path(argv[0], executable):
        return False
    editor = False
    project_file = False
    project = None
    index = 1
    while index < len(argv):
        argument = argv[index]
        if argument in ("--editor", "-e"):
            if editor:
                return False
            editor = True
        elif argument == "--path":
            if project is not None or index + 1 >= len(argv):
                return False
            index += 1
            if not absolute_local_path(argv[index]):
                return False
            project = argv[index]
        else:
            if (project is not None or not absolute_local_path(argument)
                    or ntpath.basename(argument) != "project.godot"):
                return False
            project = ntpath.dirname(argument)
            project_file = True
        index += 1
    return (editor or project_file) and same_path(project, str(root))


def server_command(process: Process, executable: str, module: str = "core.server") -> bool:
    if module not in ("core.server", "core.godot_server") or not same_path(process.executable, executable):
        return False
    if not windows_arguments(process.command_line):
        return False
    prefix = re.escape(executable)
    return re.fullmatch(r'(?i:"' + prefix + '"|' + prefix + r')\s+-B\s+-m\s+'
                        + re.escape(module) + r'\s*', process.command_line) is not None


def proven_bridge_processes(owner: Process, processes: list[Process], root: Path,
                            module: str = "core.server") -> list[Process]:
    venv = ntpath.join(str(root), "tools", "lunitora_mcp", ".venv", "Scripts", "python.exe")
    if server_command(owner, venv, module):
        return [owner]
    parents = [item for item in processes if item.pid == owner.parent_pid]
    if (len(parents) != 1 or not server_command(parents[0], venv, module)
            or type(owner.created) is not int or type(parents[0].created) is not int
            or not 0 < parents[0].created <= owner.created):
        return []
    try:
        lines = (root / "tools/lunitora_mcp/.venv/pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []
    base = [line[13:].strip() for line in lines if re.match(r"^executable = (.+)$", line)]
    if len(base) == 1 and server_command(owner, base[0], module):
        return [owner, parents[0]]
    return []
