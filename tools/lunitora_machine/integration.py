"""Coordinate MCP configuration and authentication without starting servers."""
from __future__ import annotations

from .authentication import provision_authentication
from .codex_config import provision_codex


def configure_integration(root, platform_name, applications, *, check=False,
                          emit=print, runner=None, interactive=False, secret_prompt=None,
                          replace_photoshop=False):
    capabilities = tuple(key for key in ("godot", "photoshop") if applications.get(key))
    kwargs = {} if runner is None else {"runner": runner}
    configured = provision_codex(root, platform_name, capabilities, check=check, **kwargs)
    eligible = tuple(key for key in capabilities if configured[key]["ready"]
                     or configured[key]["state"] in ("creation available", "repair available"))
    authenticated = provision_authentication(root, platform_name, eligible, check=check,
                                             interactive=interactive and not check,
                                             secret_prompt=secret_prompt, emit=emit,
                                             replace_photoshop=replace_photoshop, **kwargs)
    result = {}
    for key in capabilities:
        auth = authenticated.get(key, {
            "ready": False, "state": "not provisioned",
            "reason": "MCP configuration is conflicting or user-restricted; no authentication changes were attempted.",
        })
        result[key] = {"configuration": configured[key], "authentication": auth,
                       "live_connection": {"ready": False, "state": "NOT CHECKED",
                                           "reason": "Live MCP connection acceptance is separate; setup does not launch applications."}}
        emit(f"{key} MCP configuration: {configured[key]['state']} - {configured[key]['reason']}")
        if key == "photoshop":
            emit(f"Photoshop bridge authentication: {'OK' if auth['ready'] else auth['state']} - {auth['reason']}")
        else:
            emit(f"{key} authentication: {auth['state']} - {auth['reason']}")
    emit("Codex project trust and live MCP acceptance remain explicit user actions; no servers were started.")
    return result


def integration_success(result, *, check=False):
    for entry in result.values():
        configuration, authentication = entry["configuration"], entry["authentication"]
        if configuration["state"] == "user restricted":
            continue
        if not configuration["ready"]:
            return False
        if not authentication["ready"] and authentication["state"] != "REQUIRES MAC":
            return False
    return True
