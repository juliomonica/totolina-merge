"""Read-only Windows process admission; raw command lines never leave the probe."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import ntpath
import os
from pathlib import Path

from .policy import same_path


ROLES = {"core.godot_server": "Godot MCP server", "core.server": "Photoshop MCP server"}
PROBE_MARKER = "--lunitora-environment-probe"


def _entrypoint(argv):
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) for arg in argv):
        return None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in ("-B", "-I", "-E", "-s", "-S", "-u", "-O", "-OO", "-q"):
            index += 1
        elif arg in ("-X", "-W") and index + 1 < len(argv):
            index += 2
        elif arg in ("-m", "-c") and index + 1 < len(argv):
            return arg, argv[index + 1]
        elif not arg.startswith("-"):
            return "script", arg
        else:
            return None
    return None


def classify_processes(root, rows, *, current_pid, probe_pid, base_executable,
                       expected_created=None):
    """Admit only live venv users, retaining uncertainty instead of guessing roles."""
    interpreters = [str(Path(root) / "tools/lunitora_mcp/.venv/Scripts" / name)
                    for name in ("python.exe", "pythonw.exe")]
    setup = str(Path(root) / "tools/lunitora_setup.py")
    live = {row["pid"]: row for row in rows if row.get("alive", True)}
    expected_created = expected_created or {}
    exempt, ambiguous = set(), {}

    def venv(path):
        return isinstance(path, str) and any(same_path(path, image) for image in interpreters)

    def uncertain(pid, reason):
        ambiguous[pid] = {"pid": pid, "reason": reason}

    def birth(row):
        return type(row.get("created")) is int and row["created"] > 0

    for pid in (current_pid, probe_pid):
        child = live.get(pid)
        if child is None:
            continue
        if (not child.get("identity_ok", True) or not birth(child)
                or (pid in expected_created and child.get("created") != expected_created[pid])):
            uncertain(pid, "process provenance changed")
            continue
        exempt.add(pid)
        seen = {pid}
        while child.get("parent_pid") in live:
            parent = live[child["parent_pid"]]
            if parent["pid"] in seen:
                uncertain(parent["pid"], "process ancestry ambiguous")
                break
            seen.add(parent["pid"])
            entry = _entrypoint(parent.get("argv"))
            setup_parent = entry is not None and entry[0] == "script" and same_path(entry[1], setup)
            forwarded = (venv(parent.get("executable")) and isinstance(parent.get("argv"), list)
                         and isinstance(child.get("argv"), list) and parent["argv"][1:] == child["argv"][1:])
            if not (setup_parent or forwarded):
                break
            if (not parent.get("identity_ok", True) or not birth(parent)
                    or not birth(child) or parent["created"] > child["created"]):
                uncertain(parent["pid"], "process ancestry provenance changed")
                break
            exempt.add(parent["pid"])
            child = parent

    blockers = []
    for pid, row in sorted(live.items()):
        if pid in exempt:
            continue
        image, argv = row.get("executable"), row.get("argv")
        if not row.get("identity_ok", True):
            uncertain(pid, "process identity unavailable or changed")
            continue
        entry = _entrypoint(argv)
        role = ROLES.get(entry[1]) if entry is not None and entry[0] == "-m" else None
        using = venv(image) or (isinstance(argv, list) and bool(argv) and venv(argv[0]))
        if not using and same_path(image or "", base_executable):
            parent = live.get(row.get("parent_pid"))
            if parent is not None and venv(parent.get("executable")):
                if (not parent.get("identity_ok", True) or not birth(row)
                        or not birth(parent) or parent["created"] > row["created"]
                        or not isinstance(argv, list) or not isinstance(parent.get("argv"), list)
                        or parent["argv"][1:] != argv[1:]):
                    uncertain(pid, "venv redirector provenance changed")
                    continue
                using = True
            elif (parent is not None and parent.get("identity_ok", True) and birth(parent) and birth(row)
                  and parent["created"] <= row["created"] and isinstance(argv, list) and argv
                  and isinstance(parent.get("argv"), list) and parent["argv"]
                  and ntpath.basename(parent.get("executable", "")).lower() in ("python.exe", "pythonw.exe")
                  and ntpath.basename(ntpath.dirname(parent["executable"])).lower() == "scripts"
                  and ntpath.basename(ntpath.dirname(ntpath.dirname(parent["executable"]))).lower() == ".venv"
                  and not same_path(parent["executable"], base_executable)
                  and (same_path(argv[0], parent["executable"]) or same_path(argv[0], base_executable))
                  and same_path(parent["argv"][0], parent["executable"])
                  and argv[1:] == parent["argv"][1:]):
                continue
            elif argv is None or role:
                uncertain(pid, "Python environment provenance unavailable")
                continue
        if using:
            if not birth(row):
                uncertain(pid, "process provenance changed")
            elif not isinstance(image, str) or not ntpath.isabs(image):
                uncertain(pid, "process executable unavailable")
            else:
                blockers.append({"role": role or "Repository Python process", "pid": pid,
                                 "executable": image, "created": row["created"]})
    return {"state": "ambiguous" if ambiguous else ("in_use" if blockers else "free"),
            "blockers": blockers, "ambiguities": [ambiguous[key] for key in sorted(ambiguous)]}


class _Entry(ctypes.Structure):
    _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                ("heap", ctypes.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
                ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD), ("name", w.WCHAR * 260)]


class _Unicode(ctypes.Structure):
    _fields_ = [("length", w.USHORT), ("maximum", w.USHORT), ("buffer", ctypes.c_void_p)]


class _Native:
    def __init__(self):
        if os.name != "nt":
            raise ValueError("Windows process inspection required")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        self.nt = ctypes.WinDLL("ntdll", use_last_error=True, winmode=0x800)
        self.shell = ctypes.WinDLL("shell32", use_last_error=True, winmode=0x800)
        def bind(dll, name, args, result):
            method = getattr(dll, name)
            method.argtypes, method.restype = args, result
        p = ctypes.c_void_p
        bind(self.kernel, "CreateToolhelp32Snapshot", [w.DWORD, w.DWORD], w.HANDLE)
        bind(self.kernel, "Process32FirstW", [w.HANDLE, ctypes.POINTER(_Entry)], w.BOOL)
        bind(self.kernel, "Process32NextW", [w.HANDLE, ctypes.POINTER(_Entry)], w.BOOL)
        bind(self.kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
        bind(self.kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        bind(self.kernel, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
        bind(self.kernel, "GetProcessTimes", [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4, w.BOOL)
        bind(self.kernel, "GetSystemTimeAsFileTime", [ctypes.POINTER(w.FILETIME)], None)
        bind(self.kernel, "QueryFullProcessImageNameW", [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)], w.BOOL)
        bind(self.kernel, "LocalFree", [p], p)
        bind(self.nt, "NtQueryInformationProcess", [w.HANDLE, w.ULONG, p, w.ULONG, ctypes.POINTER(w.ULONG)], w.LONG)
        bind(self.shell, "CommandLineToArgvW", [w.LPCWSTR, ctypes.POINTER(ctypes.c_int)], ctypes.POINTER(w.LPWSTR))

    def created(self, handle):
        values = [w.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise ValueError()
        return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime

    def argv(self, handle):
        size = w.ULONG()
        self.nt.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))
        if not ctypes.sizeof(_Unicode) <= size.value <= 131072:
            return None
        data = ctypes.create_string_buffer(size.value)
        if self.nt.NtQueryInformationProcess(handle, 60, data, len(data), ctypes.byref(size)) != 0:
            return None
        text = _Unicode.from_buffer(data)
        start, end = ctypes.addressof(data), ctypes.addressof(data) + len(data)
        if (text.length % 2 or not text.buffer or text.buffer < start or text.buffer + text.length > end
                or text.length > text.maximum):
            return None
        count = ctypes.c_int()
        parsed = self.shell.CommandLineToArgvW(ctypes.wstring_at(text.buffer, text.length // 2), ctypes.byref(count))
        if not parsed:
            return None
        try:
            return [str(parsed[index]) for index in range(count.value)] if 0 < count.value <= 8192 else None
        finally:
            self.kernel.LocalFree(parsed)


def current_creation_time():
    native = _Native()
    return native.created(w.HANDLE(-1))


def inspect_windows(root, *, current_pid, current_created, base_executable=None):
    """Pin each candidate while validating birth time, image, argv and liveness."""
    native = _Native()
    own_pid = os.getpid()
    expected = {current_pid: current_created, own_pid: native.created(w.HANDLE(-1))}
    stamp = w.FILETIME()
    native.kernel.GetSystemTimeAsFileTime(ctypes.byref(stamp))
    snapshot_time = (stamp.dwHighDateTime << 32) | stamp.dwLowDateTime
    snapshot = native.kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot in (None, ctypes.c_void_p(-1).value):
        raise ValueError()
    rows = []
    try:
        item = _Entry()
        item.size = ctypes.sizeof(item)
        present = native.kernel.Process32FirstW(snapshot, ctypes.byref(item))
        if not present:
            raise ValueError()
        count = 0
        while present:
            count += 1
            if count > 65536:
                raise ValueError()
            if item.name.lower().startswith("python"):
                row = {"pid": int(item.pid), "parent_pid": int(item.parent), "alive": True}
                handle = native.kernel.OpenProcess(0x1000 | 0x100000, False, item.pid)
                if not handle:
                    row.update(alive=ctypes.get_last_error() != 87, identity_ok=False)
                else:
                    try:
                        row["created"] = native.created(handle)
                        length = w.DWORD(32768)
                        image = ctypes.create_unicode_buffer(length.value)
                        if not native.kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
                            raise ValueError()
                        row["executable"] = image.value
                        row["argv"] = native.argv(handle)
                        status = native.kernel.WaitForSingleObject(handle, 0)
                        row["alive"] = status != 0
                        row["identity_ok"] = status in (0, 258) and row["created"] <= snapshot_time
                    except Exception:
                        row["identity_ok"] = False
                    finally:
                        native.kernel.CloseHandle(handle)
                rows.append(row)
            present = native.kernel.Process32NextW(snapshot, ctypes.byref(item))
        if ctypes.get_last_error() != 18:
            raise ValueError()
    finally:
        native.kernel.CloseHandle(snapshot)
    import sys
    return classify_processes(root, rows, current_pid=current_pid, probe_pid=own_pid,
                              base_executable=base_executable or sys._base_executable, expected_created=expected)
