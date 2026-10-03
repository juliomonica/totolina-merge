"""Configuration capability summary, never a live application or device proof."""
from __future__ import annotations

from collections.abc import Mapping


def _configured(apps: dict, kind: str) -> bool:
    app = apps.get(kind)
    return bool(app and (not isinstance(app, Mapping) or app.get("path")))


def _ready(details: dict, prerequisite: str) -> bool:
    value = details.get(prerequisite)
    return value is True or (isinstance(value, Mapping) and value.get("ready") is True)


def _entry(state: str, reason: str) -> dict:
    return {"state": state, "reason": reason}


def summarize(platform: str, core_ready: bool, apps: dict, details: dict | None = None,
              *, integration: dict | None = None, local_ready: bool | None = None,
              environment_ready: bool | None = None, applications_inspected: bool = True,
              environment_present: bool = False) -> dict:
    details = details or {}
    game = _configured(apps, "godot")
    art = _configured(apps, "photoshop")
    desktop = _configured(apps, "desktop")
    android = game and all(_ready(details, key) for key in (
        "jdk", "android_sdk", "export_templates_android"))
    ios = game and all(_ready(details, key) for key in ("xcode", "export_templates_ios"))
    result = {
        "Core": _entry(
            "READY" if core_ready else "MISSING",
            "Core configuration and Python environment ready; live MCP configuration/authentication not checked."
            if core_ready else "Core setup is incomplete; inspect Python environment, configuration and alias diagnostics.",
        ),
        "Game": _entry(
            ("CONFIGURED" if desktop else "PARTIAL") if game else "MISSING",
            "Godot configured; editor launch, MCP connectivity and gameplay were not tested." + (" Desktop is missing; daily Game aliases are unavailable." if not desktop else "")
            if game else "Godot is not configured; this does not prevent Core use.",
        ),
        "Android": _entry(
            "CONFIGURED" if android else "NOT CONFIGURED",
            "Build prerequisites configured; executable export/signing and device behavior not tested."
            if android
            else "Android build prerequisites are not all checked/configured; Core/Game remain available.",
        ),
        "iOS": _entry("REQUIRES MAC", "Executable export requires macOS/Xcode; resource packs are not device proof."),
        "Art": _entry(
            ("CONFIGURED" if desktop else "PARTIAL") if art else "MISSING",
            "Photoshop configured; plugin installation/pairing and live processing not checked. UXP Developer Tool (UDT) is required for developer loading/art-dev, not daily packaged-plugin use." + (" Desktop is missing; daily Art aliases are unavailable." if not desktop else "")
            if art else "Photoshop is not configured; Core/Game do not require Art tooling.",
        ),
    }
    if not applications_inspected:
        for capability in ("Game", "Art"):
            result[capability] = _entry("NOT CHECKED", "Application/configuration inspection was unavailable; no missing installation is assumed.")
    if environment_ready is not None and not core_ready:
        if local_ready or environment_present:
            result["Core"] = _entry("PARTIAL", "Existing local setup requires environment/configuration/alias preparation or repair; uninspected capabilities are not assumed missing.")
        result["Core"]["python_environment"] = "READY" if environment_ready else "UPDATE / REPAIR REQUIRED"
    if platform == "macos":
        result["iOS"] = _entry(
            "CONFIGURED" if ios else "REQUIRES MAC",
            "Xcode/templates configured; signing, provisioning, build and devices remain manual/unvalidated."
            if ios
            else "Mac Xcode/templates are not validated; signing/provisioning and devices remain manual.",
        )
        for capability in ("Game", "Art"):
            if result[capability]["state"] in ("CONFIGURED", "PARTIAL"):
                result[capability]["reason"] += " macOS native launcher/MCP control REQUIRES MAC validation."
    if integration is not None:
        local_ready = core_ready if local_ready is None else local_ready
        if local_ready and not core_ready:
            result["Core"] = _entry("PARTIAL", "Local configuration/aliases are ready; Python environment preparation or health repair remains.")
        result["Core"]["reason"] = ("Local environment/configuration ready; MCP and authentication readiness are reported separately."
                                    if core_ready else result["Core"]["reason"])
        local_state = "READY" if local_ready else "UPDATE / REPAIR REQUIRED" if environment_present else "MISSING"
        result["Core"]["local_configuration"] = local_state
        if environment_ready is not None:
            result["Core"]["python_environment"] = "READY" if environment_ready else "UPDATE / REPAIR REQUIRED"
        for field in ("configuration", "authentication"):
            statuses = [entry[field] for entry in integration.values()]
            value = ("NOT REQUESTED" if not statuses else "READY" if all(entry["ready"] for entry in statuses)
                     else "REQUIRES MAC" if all(entry["ready"] or entry["state"] == "REQUIRES MAC" for entry in statuses)
                     else "PARTIAL / ACTION REQUIRED")
            result["Core"]["mcp_configuration" if field == "configuration" else field] = value
        result["Core"]["live_connection"] = "NOT CHECKED"
        for capability, key in (("Game", "godot"), ("Art", "photoshop")):
            if key not in integration:
                continue
            entry = integration[key]
            result[capability]["local_configuration"] = local_state
            result[capability]["mcp_configuration"] = entry["configuration"]["state"]
            result[capability]["authentication"] = entry["authentication"]["state"]
            result[capability]["live_connection"] = "NOT CHECKED"
            if not core_ready or not entry["configuration"]["ready"] or not entry["authentication"]["ready"]:
                result[capability]["state"] = "PARTIAL"
                result[capability]["reason"] += " Remaining local preparation or platform validation is listed below."
    art_status = result["Art"]
    inspected = applications_inspected
    art_status["photoshop_installed"] = ("DETECTED" if art else "NOT DETECTED / NOT CONFIGURED") if inspected else "NOT CHECKED"
    art_status["udt_installed"] = ("DETECTED" if _configured(apps, "udt") else "NOT DETECTED / NOT CONFIGURED") if inspected else "NOT CHECKED"
    art_status["developer_mode_plugin_loading"] = "NOT CHECKED - manually verify UDT Developer Mode and Load, or installed packaged plugin"
    art_status["protected_bridge_credential"] = (integration or {}).get("photoshop", {}).get("authentication", {}).get("state", "NOT CHECKED")
    art_status["photoshop_panel_paired"] = "NOT CHECKED - manually enter the same token once in Pairing token and Connect / Reconnect"
    art_status["live_connection"] = "NOT CHECKED - from Codex run one read-only photoshop_ping({})"
    if not inspected:
        action = "Application inspection unavailable; rerun --check before assuming any installation is missing."
    elif not art:
        action = "Steps 1-2: open/sign in to Creative Cloud and install/configure supported Photoshop for Art; Lunitora does not install it. Core/Game continue."
    elif not _configured(apps, "udt"):
        action = "Step 3 (development loading): install UXP Developer Tools through Creative Cloud. UDT loads/develops/debugs/packages UXP plugins; Core/Game and daily packaged-plugin use continue."
    elif art_status["protected_bridge_credential"] not in ("already correct", "created", "paired locally"):
        entry = (integration or {}).get("photoshop", {}).get("authentication", {})
        action = "Steps 4-7 require manual verification; step 8 local credential: " + entry.get("reason", "run setup for protected credential inspection.")
    else:
        action = "Verify steps 4-7 manually (Developer Mode/plugin loading); then steps 11-15 (panel pairing, git art-refresh and read-only photoshop_ping). Local credential is configured; manual/live states remain unverified."
    if platform == "macos":
        action = "REQUIRES MAC: native credential protection and live Art validation remain separate; the Windows first-time checklist does not establish Mac readiness."
    art_status["next_first_time_step"] = action
    return result
