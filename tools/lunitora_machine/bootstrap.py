"""Apply repository-owned setup; doctor uses the same plan without mutations."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from .applications import resolve_config
from .configuration import (ConfigurationError, configure_aliases, load_setup_config,
                            local_path, save_config, validate_repository)
from .environment import ensure_environment, format_usage
from .integration import configure_integration, integration_success
from .host_runtime import validated_host
from .policy import LauncherError
from .prerequisites import inspect_prerequisites
from .readiness import summarize


def platform_name() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    raise ConfigurationError("Windows and macOS are the supported setup platforms; Linux is outside this milestone.")


def get_platform(name):
    if name == "windows":
        from .platforms.windows import WindowsPlatform
        return WindowsPlatform()
    from .platforms.macos import MacPlatform
    return MacPlatform()


def catalog(root: Path):
    data = json.loads((root / "tools/lunitora_requirements.json").read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["applications"]}


def print_summary(name, core, apps, *, emit=print, details=None, integration=None,
                  local_ready=None, environment_ready=None, applications_inspected=True,
                  environment_present=False):
    emit("Capability readiness (configuration only; not live acceptance):")
    for capability, status in summarize(name, core, apps, details, integration=integration,
                                        local_ready=local_ready, environment_ready=environment_ready,
                                        applications_inspected=applications_inspected,
                                        environment_present=environment_present).items():
        if isinstance(status, dict):
            emit(f"  {capability}: {status['state']} - {status['reason']}")
            for field in ("local_configuration", "python_environment", "mcp_configuration", "authentication", "photoshop_installed", "udt_installed", "developer_mode_plugin_loading", "protected_bridge_credential", "photoshop_panel_paired", "live_connection", "next_first_time_step"):
                if field in status:
                    emit(f"    {field.replace('_', ' ')}: {status[field]}")
        else:
            emit(f"  {capability}: {status}")


def bootstrap(root: Path, platform, *, check=False, interactive=True, prompt=input,
              emit=print, runner=None, secret_prompt=None, replace_photoshop=False,
              deferred=False, environment_state=None, host_python=None):
    if check and replace_photoshop:
        raise ConfigurationError("--check cannot be combined with --pair-photoshop; check never requests or replaces a token.")
    kwargs = {} if runner is None else {"runner": runner}
    inspect_only = check or deferred
    validate_repository(root, **kwargs)
    environment = environment_state if environment_state is not None else ensure_environment(
        root, platform.name, check=inspect_only, host_python=host_python,
        interactive=interactive and not inspect_only, prompt=prompt, emit=emit, **kwargs)
    deferred = deferred or environment.get("deferred", False)
    inspect_only = check or deferred
    if environment_state is None and environment.get("usage"):
        for line in format_usage(environment["usage"]):
            emit(line)
    emit("Python environment: " + environment["state"] + " - " + environment["reason"])
    if deferred:
        emit("Deferred setup continues with read-only readiness inspection; no configuration or credential changes will be attempted.")
    original, config_state = load_setup_config(root, platform.name, check=inspect_only,
                                             interactive=interactive and not inspect_only, prompt=prompt, emit=emit)
    from .art_guidance import UDT_DESCRIPTION
    emit(UDT_DESCRIPTION)
    updated, states = resolve_config(original, platform,
                                     interactive=interactive and not inspect_only, prompt=prompt, tolerant=True)
    requirements = catalog(root)
    for kind, state in states.items():
        if inspect_only and state == "repaired/updated":
            state = "repair available"
        app = updated["applications"][kind]
        requirement = requirements[kind]
        workflows = ", ".join(requirement.get("required_for", []))
        classification = "required for " + workflows if workflows else "optional for " + ", ".join(requirement.get("optional_for", []))
        version = app.get("version", "unknown") if app else "not detected"
        action = "none" if app else requirement.get("action", "Install/configure the application and rerun setup.")
        emit(f"{requirement.get('name', kind)} | {classification} | {state} | version {version} | {action} | other capabilities continue")
        if kind == "udt":
            from .art_guidance import UDT_DESCRIPTION
            emit(UDT_DESCRIPTION + " Adobe provides it through Creative Cloud; UDT/Developer Mode currently require administrator/elevated privileges. Core/Game continue without it.")
    if inspect_only:
        emit("Local configuration: " + config_state + ("; repair available" if updated != original else ""))
    else:
        # Unverified cached paths aid the next rediscovery, but never imply readiness.
        persisted = deepcopy(updated)
        for kind, app in updated["applications"].items():
            if app is None and original["applications"][kind] is not None:
                persisted["applications"][kind] = original["applications"][kind]
        changed = save_config(root, persisted, expected=original if local_path(root).exists() else None)
        emit("Local configuration: " + ("repaired/updated" if changed else "already correct"))
        for directory in (root / "source_art/_inbox", root / "source_art/_staging"):
            from .configuration import reject_redirects
            reject_redirects(directory)
            directory.mkdir(parents=True, exist_ok=True)
    integration = configure_integration(root, platform.name, updated["applications"],
                                        check=inspect_only, emit=emit, runner=runner,
                                        interactive=interactive and not inspect_only, secret_prompt=secret_prompt,
                                        replace_photoshop=replace_photoshop and not deferred)
    alias_states = configure_aliases(root, platform.name, check=inspect_only, host_python=host_python, **kwargs)
    emit("Repository-local aliases: " + ("already correct" if all(state == "already correct" for state in alias_states.values()) else ("updates available" if inspect_only else "repaired/updated")))
    pairing_available = not replace_photoshop or updated["applications"].get("photoshop") is not None
    if not pairing_available:
        emit("Photoshop bridge pairing: unavailable on this machine because Photoshop is not installed/configured. Core/Game are unaffected; no token was requested or changed.")
    elif deferred and replace_photoshop:
        emit("Photoshop bridge pairing is deferred; no token was requested or changed. Rerun python tools/lunitora_setup.py --pair-photoshop after the environment can be updated safely.")
    details = inspect_prerequisites(root, platform.name)
    source = json.loads((root / "tools/lunitora_requirements.json").read_text(encoding="utf-8"))
    for requirement in source["prerequisites"]:
        key = requirement["id"]
        if key not in details:
            continue
        status = details[key]
        purpose = "required for " + ", ".join(requirement["required_for"]) if requirement["required_for"] else "optional for " + ", ".join(requirement["optional_for"])
        action = requirement["action"] if not status["ready"] else "none for detection; live configuration remains unverified"
        emit(f"{requirement.get('name', key)} | {purpose} | {status['state']} | version {status['version']} | {action} | other capabilities continue")
    aliases_ready = all(state == "already correct" for state in alias_states.values()) or not inspect_only
    config_ready = local_path(root).is_file() if inspect_only else True
    core = environment["ready"] and aliases_ready and config_ready
    print_summary(platform.name, core, updated["applications"], emit=emit, details=details, integration=integration,
                  local_ready=aliases_ready and config_ready, environment_ready=environment["ready"],
                  environment_present=bool(environment.get("python")))
    if platform.name == "windows":
        from .authentication import PHOTOSHOP_STORAGE, CAPABILITIES
        from .art_guidance import emit_first_time
        emit_first_time(root, root / PHOTOSHOP_STORAGE / CAPABILITIES["photoshop"], emit)
    return 0 if not deferred and core and pairing_available and integration_success(integration, check=inspect_only) else 1


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Repository-local Lunitora machine setup. External applications are never installed.")
    parser.add_argument("--check", action="store_true", help="Read-only doctor; no installation, repair or application startup.")
    parser.add_argument("--pair-photoshop", action="store_true", help="Reuse a valid protected token or privately create/import a first-time token.")
    parser.add_argument("--repair-photoshop-auth", action="store_true", help="Consent-gated ownership/DACL repair; preserves the existing valid Photoshop token.")
    parser.add_argument("--migrate-photoshop-auth", action="store_true", help="Consent-gated byte-preserving migration into dedicated protected Windows storage.")
    parser.add_argument("--_host-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.migrate_photoshop_auth and (args.check or args.pair_photoshop or args.repair_photoshop_auth):
        parser.error("--migrate-photoshop-auth must be used alone.")
    if args.repair_photoshop_auth and (args.check or args.pair_photoshop):
        parser.error("--repair-photoshop-auth cannot be combined with --check or --pair-photoshop.")
    if args.check and args.pair_photoshop:
        parser.error("--check cannot be combined with --pair-photoshop; check never requests or replaces a token.")
    root = Path(__file__).absolute().parents[2]
    name = None
    apps = {}
    try:
        name = platform_name()
        validate_repository(root)
        host = validated_host(root, name)
        if (os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(host)
                or sys.prefix != sys.base_prefix):
            if args._host_worker:
                raise ConfigurationError("Setup worker must use the validated standalone host Python.")
            import subprocess
            command = [host, "-I", "-S", "-B", str(root / "tools/lunitora_setup.py"), "--_host-worker"]
            if args.check:
                command.append("--check")
            if args.pair_photoshop:
                command.append("--pair-photoshop")
            if args.repair_photoshop_auth:
                command.append("--repair-photoshop-auth")
            if args.migrate_photoshop_auth:
                command.append("--migrate-photoshop-auth")
            return subprocess.run(command, check=False).returncode
        if args.migrate_photoshop_auth:
            from .photoshop_migration import migrate
            return migrate(root, name)
        if args.repair_photoshop_auth:
            from .photoshop_recovery import repair
            return repair(root, name)
        state = ensure_environment(root, name, check=args.check, host_python=host,
                                   interactive=not args.check, emit=print)
        deferred = state.get("deferred", False)
        if state.get("usage"):
            for line in format_usage(state["usage"]):
                print(line, flush=True)
        platform = get_platform(name)
        return bootstrap(root, platform, check=args.check, interactive=not args.check,
                         replace_photoshop=args.pair_photoshop, deferred=deferred,
                         environment_state=state, host_python=host)
    except (ConfigurationError, LauncherError, OSError, ValueError) as error:
        print("Setup: " + str(error), file=sys.stderr)
        if name:
            print_summary(name, False, apps, applications_inspected=False)
        return 1
