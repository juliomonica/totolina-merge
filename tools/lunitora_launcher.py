"""Git-fronted daily workflows. Repair never becomes an interactive wizard."""
import sys

sys.dont_write_bytecode = True

from pathlib import Path

sys.path.insert(0, str(Path(__file__).absolute().parent))

from lunitora_machine.applications import runtime_applications
from lunitora_machine.bootstrap import get_platform, platform_name
from lunitora_machine.configuration import ConfigurationError, MODES, load_config, validate_repository
from lunitora_machine.environment import inspect_environment
from lunitora_machine.host_runtime import require_current_host
from lunitora_machine.policy import LauncherError
from lunitora_machine.workflows import run_workflow


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Lunitora repository-local operator launcher.")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--check", "-Check", action="store_true", help="Validate this workflow without repair, launch or shutdown.")
    args = parser.parse_args(argv)
    root = Path(__file__).absolute().parents[1]
    try:
        validate_repository(root)
        require_current_host()
        name = platform_name()
        if name == "macos":
            raise LauncherError("REQUIRES MAC: live activation, ownership and refresh have not been validated.")
        try:
            environment = inspect_environment(root, name)
        except (ConfigurationError, OSError, ValueError):
            raise LauncherError("Repository MCP environment is unsafe or unhealthy; rerun python tools/lunitora_setup.py. No application was launched.") from None
        if not environment["ready"]:
            raise LauncherError("Repository environment needs repair; rerun python tools/lunitora_setup.py.")
        config, _ = load_config(root, name, migrate=False)
        platform = get_platform(name)
        applications = runtime_applications(root, config, platform, args.mode, check=args.check)
        if args.check:
            print("OK: workflow prerequisites validated; no repair, launch or shutdown occurred.")
        else:
            run_workflow(args.mode, applications, root, platform)
        return 0
    except (ConfigurationError, LauncherError, OSError, ValueError) as error:
        print("Launcher: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
