"""Explicit, bounded recovery of exact checkout-owned Windows MCP processes."""
from __future__ import annotations

import configparser
import ctypes
from ctypes import wintypes as w
from dataclasses import dataclass
import os
from pathlib import Path
import time

from .configuration import reject_redirects
from .environment_usage import ROLES, _Entry, _Native, classify_processes
from .policy import same_path


@dataclass(frozen=True)
class _Held:
    handle: object
    row: dict


def _base_python(root):
    path = Path(root) / "tools/lunitora_mcp/.venv/pyvenv.cfg"
    reject_redirects(path)
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string("[venv]\n" + path.read_text(encoding="utf-8"))
    base = parser["venv"].get("executable")
    if not same_path(base, base):
        raise ValueError()
    return base


def _exact_module(row, executable):
    argv = row.get("argv")
    if (not isinstance(argv, list) or len(argv) != 4 or not same_path(argv[0], executable)
            or argv[1:3] != ["-B", "-m"] or argv[3] not in ROLES):
        return None
    return argv[3]


def admitted_recovery(root, usage, rows, base_executable):
    """Return only exact identities; uncertainty never expands recovery scope."""
    if (usage.get("state") != "in_use" or usage.get("ambiguities")
            or not isinstance(usage.get("blockers"), list) or not usage["blockers"]):
        raise ValueError()
    observed = classify_processes(root, rows, current_pid=os.getpid(), probe_pid=os.getpid(),
                                  base_executable=base_executable)
    if observed["state"] != "in_use" or observed["ambiguities"]:
        raise ValueError()
    expected = {}
    for blocker in usage["blockers"]:
        if (not isinstance(blocker, dict) or blocker.get("role") not in ROLES.values()
                or type(blocker.get("pid")) is not int or blocker["pid"] <= 0
                or blocker["pid"] == os.getpid() or blocker["pid"] in expected
                or type(blocker.get("created")) is not int or blocker["created"] <= 0
                or not same_path(blocker.get("executable"), blocker.get("executable"))):
            raise ValueError()
        expected[blocker["pid"]] = blocker
    if set(expected) != {item["pid"] for item in observed["blockers"]}:
        raise ValueError()
    live = {row["pid"]: row for row in rows if row.get("alive", True)}
    if len(live) != sum(bool(row.get("alive", True)) for row in rows):
        raise ValueError()
    venv = str(Path(root) / "tools/lunitora_mcp/.venv/Scripts/python.exe")
    targets = []
    for pid, blocker in expected.items():
        row = live.get(pid)
        if (row is None or not row.get("identity_ok", True)
                or row.get("created") != blocker["created"]
                or not same_path(row.get("executable"), blocker["executable"])):
            raise ValueError()
        if same_path(row["executable"], venv):
            module = _exact_module(row, venv)
            order = 1
        elif same_path(row["executable"], base_executable):
            parent = live.get(row.get("parent_pid"))
            if (parent is None or parent["pid"] not in expected
                    or not same_path(parent.get("executable"), venv)
                    or type(parent.get("created")) is not int
                    or not 0 < parent["created"] <= row["created"]):
                raise ValueError()
            parent_module = _exact_module(parent, venv)
            module = _exact_module(row, base_executable) or _exact_module(row, venv)
            if not parent_module or parent_module != module:
                raise ValueError()
            order = 0
        else:
            raise ValueError()
        if not module or ROLES[module] != blocker["role"]:
            raise ValueError()
        targets.append((order, dict(row)))
    return [row for _, row in sorted(targets, key=lambda item: (item[0], item[1]["pid"]))]


class _RecoveryNative:
    def __init__(self):
        self.native = _Native()
        self.deadline = None
        method = self.native.kernel.TerminateProcess
        method.argtypes, method.restype = [w.HANDLE, w.UINT], w.BOOL

    def _row(self, handle, row):
        native = self.native
        result = {"pid": row["pid"], "parent_pid": row["parent_pid"]}
        result["created"] = native.created(handle)
        length = w.DWORD(32768)
        image = ctypes.create_unicode_buffer(length.value)
        if not native.kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)):
            raise ValueError()
        result["executable"] = image.value
        result["argv"] = native.argv(handle)
        status = native.kernel.WaitForSingleObject(handle, 0)
        if status not in (0, 258):
            raise ValueError()
        result.update(alive=status == 258, identity_ok=True)
        return result

    def snapshot(self):
        native = self.native
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
                            row = self._row(handle, row)
                            row["identity_ok"] = row["created"] <= snapshot_time
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
        return rows

    def pin(self, row):
        native = self.native
        handle = native.kernel.OpenProcess(0x1000 | 0x100000 | 1, False, row["pid"])
        if not handle:
            raise ValueError()
        held = _Held(handle, row)
        try:
            self.verify(held)
        except Exception:
            native.kernel.CloseHandle(handle)
            raise
        return held

    def verify(self, held):
        if self.native.kernel.WaitForSingleObject(held.handle, 0) == 0:
            return False
        current = self._row(held.handle, held.row)
        if (not current["alive"] or current["created"] != held.row["created"]
                or not same_path(current["executable"], held.row["executable"])
                or current["argv"] != held.row["argv"]):
            raise ValueError()
        return True

    def stop(self, held):
        if not self.verify(held):
            return True
        if self.deadline is None:
            self.deadline = time.monotonic() + 5
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            return False
        if not self.native.kernel.TerminateProcess(held.handle, 1):
            if self.native.kernel.WaitForSingleObject(held.handle, 0) == 0:
                return True
            raise ValueError()
        return self.native.kernel.WaitForSingleObject(held.handle, max(1, int(remaining * 1000))) == 0

    def close(self, held):
        self.native.kernel.CloseHandle(held.handle)


def recover_mcp_blockers(root, usage, *, interactive, prompt=input, emit=print,
                         backend=None, base_executable=None):
    """One explicit attempt; the caller must re-inspect use before any venv write."""
    result = {"recovered": False, "state": "deferred", "reason": "verified recovery not approved"}
    if not interactive:
        result["reason"] = "interactive confirmation required; rerun python tools/lunitora_setup.py"
        return result
    if os.name != "nt" and backend is None:
        return {**result, "state": "ambiguous", "reason": "Windows recovery unavailable; REQUIRES MAC"}
    held = []
    try:
        backend = backend or _RecoveryNative()
        base_executable = base_executable or _base_python(root)
        targets = admitted_recovery(root, usage, backend.snapshot(), base_executable)
        # All exact identities are pinned before consent or the first termination.
        for row in targets:
            held.append(backend.pin(row))
        emit("Repository MCP environment needs an update.")
        emit("Verified Lunitora processes still using it:")
        for row in targets:
            emit(f"  {ROLES[row['argv'][3]]} | PID {row['pid']}")
        emit("Only these verified MCP processes will stop; Godot Editor and Desktop will not be closed.")
        try:
            answer = prompt("Stop these verified Lunitora MCP processes and continue? [y/N]: ")
        except (EOFError, OSError, KeyboardInterrupt):
            return result
        if not isinstance(answer, str) or answer.strip().lower() not in ("y", "yes"):
            return result
        for target in held:
            backend.verify(target)
        for target in held:
            if not backend.stop(target):
                return {**result, "state": "ambiguous", "reason": "verified process exit could not be proven; no dependency update is safe"}
        emit("Verified MCP processes exited. Environment use will be checked again before repair.")
        return {"recovered": True, "state": "exited", "reason": "verified MCP process exit proven"}
    except Exception:
        return {**result, "state": "ambiguous", "reason": "environment-use state ambiguous; no further recovery or dependency update is safe"}
    finally:
        if backend is not None:
            for target in held:
                backend.close(target)
