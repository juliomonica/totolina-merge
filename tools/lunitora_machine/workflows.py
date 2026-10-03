"""Seven operator workflows; MCP processes remain owned by Desktop."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import time

from .logs import new_godot_output_logs
from .policy import (LauncherError, Process, godot_editor_command, owned_descendants,
                     process_identity, proven_bridge_processes, same_path)

MODES = frozenset({"art", "art-refresh", "art-dev", "dev", "dev-refresh", "godot", "godot-refresh"})


def _snapshot(platform) -> list[Process]:
    processes = list(platform.processes())
    ids = [item.pid for item in processes if item.pid > 0]
    if len(ids) != len(set(ids)):
        raise LauncherError("Process inspection is ambiguous; nothing was terminated.")
    return processes


def _application_processes(processes: list[Process], path: str | None) -> list[Process]:
    return [item for item in processes if item.pid > 0 and same_path(item.executable, path)]


def _fresh(platform, snapshot: Process) -> Process | None:
    fresh = [item for item in _snapshot(platform) if item.pid == snapshot.pid]
    if not fresh:
        return None
    if not process_identity(snapshot, fresh[0]):
        raise LauncherError("Process identity changed or is unavailable; refusing termination.")
    return fresh[0]


def _stop(platform, snapshot: Process) -> None:
    if _fresh(platform, snapshot) is not None:
        platform.stop_verified(snapshot)


def wait_for_exit(platform, snapshots: list[Process], seconds: float) -> list[Process]:
    if not snapshots:
        return []
    deadline = time.monotonic() + seconds
    while True:
        current = _snapshot(platform)
        remaining = [item for item in snapshots if any(process_identity(item, live) for live in current)]
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(0.25)


def close_desktop(platform, path: str, keep_open_path: str | None, emit) -> list[Process]:
    all_processes = _snapshot(platform)
    desktops = _application_processes(all_processes, path)
    if not desktops:
        return []
    owned = owned_descendants(all_processes, desktops)
    if any(item.pid == os.getpid() for item in owned):
        raise LauncherError("Run refresh from an external shell after Desktop work finishes; it cannot close its own parent session.")
    protected = _application_processes(all_processes, keep_open_path)
    protected += owned_descendants(all_processes, protected)
    protected_ids = {item.pid for item in protected}
    owned = [item for item in owned if item.pid not in protected_ids]
    emit("Closing ChatGPT/Codex Desktop (active Desktop work will stop)...")
    for item in desktops:
        if _fresh(platform, item) is not None:
            platform.request_close(item)
    for item in wait_for_exit(platform, desktops, 8):
        _stop(platform, item)
    if _application_processes(_snapshot(platform), path):
        raise LauncherError("Desktop is still running; close it completely before a fresh external-shell attempt.")
    return wait_for_exit(platform, owned, 10)


def assert_port_free(platform, port: int) -> None:
    if platform.port_owners(port):
        raise LauncherError(f"Port {port} is still occupied.")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
            probe.listen(1)
    except OSError:
        raise LauncherError(f"Port {port} could not be proven free.") from None


def clear_stale_bridge_port(platform, root: Path, desktop_owned: list[Process], port: int,
                           module: str, emit) -> None:
    if (port, module) not in ((43127, "core.server"), (43128, "core.godot_server")):
        raise LauncherError("Unsupported bridge port/module pair; nothing was inspected or terminated.")
    deadline = time.monotonic() + 10
    while platform.port_owners(port) and time.monotonic() < deadline:
        time.sleep(0.25)
    for pid in platform.port_owners(port):
        all_processes = _snapshot(platform)
        owners = [item for item in all_processes if item.pid == pid]
        if len(owners) != 1:
            raise LauncherError(f"Port {port} owner PID {pid} cannot be inspected; nothing was terminated.")
        owner = owners[0]
        emit(f"Port {port} owner PID {pid} requires exact repository process proof.")
        proof = proven_bridge_processes(owner, all_processes, root, module)
        if not proof:
            raise LauncherError("Unknown port owner; nothing was terminated. Close its owning application yourself.")
        anchor = proof[-1]
        was_owned = any(process_identity(item, owner) for item in desktop_owned)
        parent_alive = any(item.pid == anchor.parent_pid for item in all_processes)
        if not was_owned and parent_alive:
            raise LauncherError("Exact bridge belongs to another live process; it is not proven stale. Nothing was terminated.")
        for item in proof:
            _stop(platform, item)
    assert_port_free(platform, port)
    emit(f"Port {port} is free.")


def ensure_application(platform, application: dict, root: Path, label: str, emit) -> None:
    if _application_processes(_snapshot(platform), application["path"]):
        emit(f"{label} is already running.")
        return
    platform.spawn_application(application, root)
    emit(f"{label} launch requested.")


def ensure_godot_editor(platform, application: dict, root: Path, emit) -> None:
    if any(godot_editor_command(item, application["path"], root) for item in _snapshot(platform)):
        emit("Godot editor is already running for this checkout.")
        return
    logs = new_godot_output_logs(root)
    try:
        with logs.stdout.open("xb") as stdout, logs.stderr.open("xb") as stderr:
            subprocess.Popen([application["path"], "--editor", "--path", str(root)], cwd=root,
                             stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                             shell=False, close_fds=True, **platform.detached_flags())
    except (OSError, ValueError):
        raise LauncherError("Godot launch failed; no automatic retry was made.") from None
    emit("Godot editor launch requested for this checkout.")
    emit(f"Godot stdout: {logs.stdout}")
    emit(f"Godot stderr: {logs.stderr}")


def run_workflow(mode: str, apps: dict, root: Path, platform, emit=print) -> None:
    if platform.name != "windows":
        raise LauncherError("REQUIRES MAC validation: native workflows are currently Windows-only.")
    if mode not in MODES:
        raise LauncherError("Unknown operator workflow; nothing was launched.")
    art = mode in ("art", "art-refresh", "art-dev")
    godot = mode in ("godot", "godot-refresh")
    required = ["desktop"] + (["photoshop"] if art else []) + (["udt"] if mode == "art-dev" else []) + (["godot"] if godot else [])
    for kind in required:
        if not isinstance(apps.get(kind), dict) or not apps[kind].get("path"):
            raise LauncherError(f"{kind} is not configured; run machine setup with an explicit override.")
    if mode.endswith("-refresh"):
        keep_open_path = (apps.get("godot") or {}).get("path") if mode == "godot-refresh" else None
        if keep_open_path:
            emit("Keeping configured Godot editors open to protect unsaved work.")
        leftovers = close_desktop(platform, apps["desktop"]["path"], keep_open_path, emit)
        if mode == "godot-refresh":
            clear_stale_bridge_port(platform, root, leftovers, 43128, "core.godot_server", emit)
        elif mode == "art-refresh":
            clear_stale_bridge_port(platform, root, leftovers, 43127, "core.server", emit)
        leftovers = wait_for_exit(platform, leftovers, 2)
        if leftovers:
            emit("Desktop-owned processes are still exiting: " + ", ".join(f"PID {item.pid}" for item in leftovers))
            raise LauncherError("Recovery stopped before reopening Desktop; no unrelated process was terminated.")
    if art:
        ensure_application(platform, apps["photoshop"], root, "Photoshop", emit)
    if mode == "art-dev":
        emit("DEVELOPER ONLY: UXP Developer Tool (UDT) is Adobe's utility for loading, developing and debugging the Lunitora UXP Photoshop plugin.")
        ensure_application(platform, apps["udt"], root, "UXP Developer Tool (UDT)", emit)
    ensure_application(platform, apps["desktop"], root, "ChatGPT/Codex Desktop", emit)
    if mode == "godot":
        ensure_godot_editor(platform, apps["godot"], root, emit)
    emit(f"OK: {mode} startup complete for {root}. Configured stdio MCP servers remain Desktop-owned.")
    if godot:
        emit("lunitora_godot stays Codex-owned; the open Godot editor reconnects automatically.")
    if art:
        emit("After one-time plugin installation and pairing, request the approved inbox-to-staging image operation.")
