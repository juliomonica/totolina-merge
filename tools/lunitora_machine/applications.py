"""Deterministic discovery; interactive selection belongs only to setup."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from .configuration import KINDS, SETUP_COMMAND, save_config
from .policy import LauncherError


def resolve_application(kind, configured, platform, *, interactive=False, prompt=input):
    label = "UXP Developer Tool (UDT)" if kind == "udt" else kind
    if configured:
        try:
            validated = platform.validate_application(kind, configured["path"])
            return validated, "already correct" if configured == validated else "metadata update available"
        except (LauncherError, OSError, ValueError):
            pass
    try:
        candidates = platform.discover(kind, configured)
    except (LauncherError, OSError, ValueError):
        if not interactive:
            raise LauncherError(f"Cannot safely discover {label}; rerun {SETUP_COMMAND}.") from None
        candidates = []
    unique = {app["path"]: app for app in candidates}
    candidates = [unique[key] for key in sorted(unique)]
    if len(candidates) == 1:
        return candidates[0], "repaired/updated" if configured else "discovered"
    state = "requires user selection" if candidates else "missing"
    if not interactive:
        return None, state
    if candidates:
        for index, app in enumerate(candidates, 1):
            print(f"  {index}. {app['path']} ({app.get('version') or 'version unknown'})")
    try:
        answer = prompt(f"{label}: {state}. Select a number or installed application path; Enter skips: ").strip()
    except (EOFError, OSError):
        return None, state
    if not answer:
        return None, state
    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1], "selected"
    path = answer.strip('"')
    try:
        return platform.validate_application(kind, path), "selected"
    except (LauncherError, OSError, ValueError):
        raise LauncherError(f"Selected {label} location is invalid; rerun {SETUP_COMMAND}.") from None


def resolve_config(config, platform, *, interactive=False, prompt=input, required=KINDS, tolerant=False):
    updated = deepcopy(config)
    states = {}
    for kind in required:
        try:
            app, state = resolve_application(kind, config["applications"][kind], platform,
                                             interactive=interactive, prompt=prompt)
        except (LauncherError, OSError, ValueError):
            if not tolerant:
                raise
            app, state = None, "requires user selection/inspection unavailable"
        updated["applications"][kind] = app
        states[kind] = state
    return updated, states


def required_for_mode(mode):
    required = ["desktop"]
    if mode.startswith("art"):
        required.append("photoshop")
    if mode == "art-dev":
        required.append("udt")
    if mode.startswith("godot"):
        required.append("godot")
    return required


def runtime_applications(root: Path, config, platform, mode, *, check=False):
    required = required_for_mode(mode)
    updated, states = resolve_config(config, platform, required=required)
    missing = [kind for kind in required if updated["applications"][kind] is None]
    if missing:
        raise LauncherError("Application configuration is missing/ambiguous: " + ", ".join(missing)
                            + "; rerun " + SETUP_COMMAND + ".")
    if updated != config and not check:
        save_config(root, updated, expected=config)
    return updated["applications"]
