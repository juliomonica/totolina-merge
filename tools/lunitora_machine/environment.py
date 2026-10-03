"""Stdlib-only Python environment planning and pinned dependency bootstrap."""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import shutil
import sys

from .configuration import ConfigurationError, config_lock, reject_redirects, run

PROBE = """import importlib.metadata as m,json,platform,sys
print(json.dumps({'version':list(sys.version_info[:3]),'prefix':sys.prefix,'base_prefix':sys.base_prefix,'executable':sys.executable,'base_executable':getattr(sys,'_base_executable',sys.executable),'bits':64 if sys.maxsize>2**32 else 32,'packages':{d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()}}))"""


def python_path(root: Path, platform: str) -> Path:
    return root / "tools/lunitora_mcp/.venv" / ("Scripts/python.exe" if platform == "windows" else "bin/python")


def pins(root: Path, platform: str) -> dict[str, str]:
    result = {}
    for line in (root / "tools/lunitora_mcp/requirements.lock").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_-]+)==([A-Za-z0-9.+_-]+)(?:\s*;\s*sys_platform\s*==\s*['\"]win32['\"])?", line)
        if not match:
            raise ConfigurationError("Dependency lock must contain exact pins and supported platform markers only.")
        if ";" in line and platform != "windows":
            continue
        name, version = match.groups()
        name = name.lower().replace("_", "-")
        if name in result:
            raise ConfigurationError("Duplicate dependency pin.")
        result[name] = version
    if not result:
        raise ConfigurationError("Dependency lock is empty.")
    return result


def probe(executable, runner=run):
    try:
        result = runner([str(executable), "-I", "-B", "-c", PROBE])
        if result.returncode:
            return None
        data = json.loads(result.stdout)
        if data["version"][:2] != [3, 12] or data["bits"] != 64:
            return None
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def inspect_environment(root: Path, platform: str, runner=run) -> dict:
    executable = python_path(root, platform)
    directory = executable.parents[1]
    reject_redirects(directory)
    if not directory.exists():
        return {"ready": False, "state": "missing", "reason": "repository Python environment missing"}
    cfg = directory / "pyvenv.cfg"
    reject_redirects(cfg)
    if not cfg.is_file():
        raise ConfigurationError("Existing environment has no valid pyvenv.cfg; refusing replacement.")
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string("[venv]\n" + cfg.read_text(encoding="utf-8"))
        if parser["venv"].get("include-system-site-packages", "true").lower() != "false":
            raise ValueError()
    except (ValueError, configparser.Error):
        raise ConfigurationError("Existing repository environment configuration is unsafe; refusing replacement.") from None
    data = probe(executable, runner)
    if not data:
        base = parser["venv"].get("executable")
        base_data = probe(base, runner) if base and os.path.isabs(base) else None
        if (parser["venv"].get("version", "").split(".")[:2] != ["3", "12"]
                or not base_data or base_data["prefix"] != base_data["base_prefix"]):
            raise ConfigurationError("Repository environment needs compatible Python 3.12 x64; no valid environment was overwritten.")
        return {"ready": False, "state": "environment repair available", "python": str(executable),
                "reason": "managed MCP interpreter is unhealthy; host Python can inspect and repair it",
                "base_executable": str(base), "rebuild": True}
    if os.path.normcase(os.path.abspath(data["prefix"])) != os.path.normcase(str(directory.absolute())):
        raise ConfigurationError("Repository environment needs compatible Python 3.12 x64; no valid environment was overwritten.")
    wanted = pins(root, platform)
    missing = [name for name, version in wanted.items() if data["packages"].get(name) != version]
    health = runner([str(executable), "-I", "-B", "-m", "pip", "check"])
    imports_ok = False
    if not missing and health.returncode == 0:
        imports = "import mcp,websockets" + (",pythoncom,win32api" if platform == "windows" else "")
        imports_ok = runner([str(executable), "-I", "-B", "-c", imports]).returncode == 0
    ready = not missing and health.returncode == 0 and imports_ok
    return {"ready": ready,
            "state": "already correct" if ready else "dependency update available",
            "reason": "pinned dependencies and imports verified" if ready else "pinned packages, imports or dependency health need repair",
            "python": str(executable), "data": data, "inspection_ready": True,
            "base_executable": data.get("base_executable")}


def find_python(root: Path, platform: str, runner=run) -> str:
    candidates = [sys.executable, getattr(sys, "_base_executable", sys.executable)]
    cfg = root / "tools/lunitora_mcp/.venv/pyvenv.cfg"
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if line.startswith("executable = "):
                candidates.append(line.split(" = ", 1)[1].strip())
    if platform == "windows":
        launcher = shutil.which("py")
        if launcher:
            result = runner([launcher, "-3.12", "-I", "-B", "-c", "import sys; print(sys.executable)"])
            if result.returncode == 0:
                candidates.append(result.stdout.strip())
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(str(Path(local) / "Programs/Python/Python312/python.exe"))
    candidates.extend(filter(None, (shutil.which("python3.12"), shutil.which("python"))))
    for candidate in dict.fromkeys(candidates):
        data = probe(candidate, runner)
        if data and data["prefix"] == data["base_prefix"]:
            return str(candidate)
    raise ConfigurationError("Install Python 3.12 x64 alongside your current Python, then rerun python tools/lunitora_setup.py. Python is never downloaded by setup.")


def inspect_environment_use(root: Path, platform: str, runner=run, *, host_python=None, base_executable=None) -> dict:
    """Return admitted identities only, never arbitrary argv or probe diagnostics."""
    ambiguous = {"state": "ambiguous", "blockers": [],
                 "ambiguities": [{"reason": "environment-use inspection unavailable"}]}
    if platform != "windows":
        return {**ambiguous, "ambiguities": [{"reason": "macOS environment-use inspection REQUIRES MAC"}]}
    try:
        from .environment_usage import PROBE_MARKER, current_creation_time
        source = _USAGE_SOURCE.replace("ROOT_REPR", repr(str(root.absolute())))
        source = source.replace("CURRENT_PID", str(os.getpid()))
        source = source.replace("CURRENT_CREATED", str(current_creation_time()))
        source = source.replace("BASE_REPR", repr(base_executable))
        result = runner([str(host_python or getattr(sys, "_base_executable", sys.executable)), "-I", "-S", "-B", "-c", source,
                         PROBE_MARKER])
        if result.returncode:
            return ambiguous
        report = json.loads(result.stdout)
        if (not isinstance(report, dict) or set(report) != {"state", "blockers", "ambiguities"}
                or report["state"] not in ("free", "in_use", "ambiguous")
                or not isinstance(report["blockers"], list) or not isinstance(report["ambiguities"], list)):
            return ambiguous
        for item in report["blockers"]:
            if (set(item) != {"role", "pid", "executable", "created"}
                    or item["role"] not in ("Godot MCP server", "Photoshop MCP server", "Repository Python process")
                    or type(item["pid"]) is not int or item["pid"] <= 0
                    or type(item["created"]) is not int or item["created"] <= 0
                    or not isinstance(item["executable"], str) or not os.path.isabs(item["executable"])
                    or any(ord(char) < 32 for char in item["executable"])):
                return ambiguous
        allowed = {"process provenance changed", "process ancestry ambiguous", "process ancestry provenance changed",
                   "process identity unavailable or changed", "venv redirector provenance changed",
                   "Python environment provenance unavailable", "process executable unavailable"}
        for item in report["ambiguities"]:
            if (not isinstance(item, dict) or set(item) - {"pid", "reason"}
                    or item.get("reason") not in allowed
                    or ("pid" in item and (type(item["pid"]) is not int or item["pid"] <= 0))):
                return ambiguous
        if ((report["state"] == "free" and (report["blockers"] or report["ambiguities"]))
                or (report["state"] == "in_use" and (not report["blockers"] or report["ambiguities"]))
                or (report["state"] == "ambiguous" and not report["ambiguities"])):
            return ambiguous
        return report
    except (OSError, ValueError, KeyError, TypeError):
        return ambiguous


def environment_in_use(root: Path, platform: str, runner=run) -> bool:
    return inspect_environment_use(root, platform, runner)["state"] != "free"


def format_usage(report) -> list[str]:
    lines = ["Repository Python environment is currently in use." if report["state"] == "in_use"
             else "environment-use state ambiguous; dependency update deferred."]
    for item in report["blockers"]:
        lines.extend(["Blocking process:", "  role: " + item["role"], f"  pid: {item['pid']}",
                      "  executable: " + item["executable"]])
    for item in report["ambiguities"]:
        lines.append("Inspection uncertainty: " + item["reason"] + (f" (pid: {item['pid']})" if "pid" in item else ""))
    if report["state"] == "in_use":
        action = ("  Close Codex Desktop, then rerun:" if all(item["role"] != "Repository Python process" for item in report["blockers"])
                  else "  Finish the owning repository Python workflow; close Codex Desktop if using MCP. Then rerun:")
        lines.extend(["Action:", action, "  python tools/lunitora_setup.py"])
    else:
        lines.extend(["Uncertain processes were not labelled as Desktop/MCP; no environment changes were made.",
                      "Rerun python tools/lunitora_setup.py --check for read-only readiness diagnostics."])
    return lines


_USAGE_SOURCE = '''import json,sys
sys.path.insert(0, ROOT_REPR + '/tools')
from lunitora_machine.environment_usage import inspect_windows
try:
    report=inspect_windows(ROOT_REPR,current_pid=CURRENT_PID,current_created=CURRENT_CREATED,base_executable=BASE_REPR)
except Exception:
    report={'state':'ambiguous','blockers':[],'ambiguities':[{'reason':'environment-use inspection unavailable'}]}
print(json.dumps(report))'''


def ensure_environment(root: Path, platform: str, *, check=False, runner=run,
                       host_python=None, interactive=False, prompt=input, emit=print) -> dict:
    state = inspect_environment(root, platform, runner)
    if check or state["ready"]:
        return state
    with config_lock(root, "environment.lock"):
        state = inspect_environment(root, platform, runner)
        if state["ready"]:
            return state
        return _install_environment(root, platform, runner, state=state, host_python=host_python,
                                    interactive=interactive, prompt=prompt, emit=emit)


def _install_environment(root: Path, platform: str, runner, *, state=None,
                         host_python=None, interactive=False, prompt=input, emit=print) -> dict:
    executable = python_path(root, platform)
    directory = executable.parents[1]
    created = not directory.exists()
    if created:
        python = host_python or find_python(root, platform, runner)
        result = runner([python, "-I", "-B", "-m", "venv", str(directory)])
        if result.returncode:
            raise ConfigurationError("Repository Python environment creation failed; no system Python was changed.")
    else:
        inspection = {} if host_python is None and not (state or {}).get("base_executable") else {
            "host_python": host_python, "base_executable": (state or {}).get("base_executable")}
        usage = inspect_environment_use(root, platform, runner, **inspection)
        if usage["state"] == "in_use" and interactive:
            from .environment_recovery import recover_mcp_blockers
            recovery = recover_mcp_blockers(root, usage, interactive=True, prompt=prompt,
                                            emit=emit, base_executable=(state or {}).get("base_executable"))
            if recovery["recovered"]:
                usage = inspect_environment_use(root, platform, runner, **inspection)
                if usage["state"] != "free":
                    emit("Environment is not proven free after bounded recovery; update remains deferred.")
            else:
                emit("MCP recovery: " + recovery["reason"])
                if recovery["state"] == "ambiguous":
                    usage = {"state": "ambiguous", "blockers": [],
                             "ambiguities": [{"reason": "process provenance changed"}]}
        if usage["state"] != "free":
            state = state or inspect_environment(root, platform, runner)
            return {**state, "ready": False, "state": "update deferred", "deferred": True,
                    "reason": "environment-use state ambiguous" if usage["state"] == "ambiguous" else "repository Python environment is currently in use",
                    "usage": usage}
        if (state or {}).get("rebuild"):
            python = host_python or find_python(root, platform, runner)
            result = runner([python, "-I", "-B", "-m", "venv", str(directory)])
            if result.returncode:
                raise ConfigurationError("Managed MCP interpreter repair failed; no system Python was changed.")
    result = runner([str(executable), "-I", "-B", "-m", "pip", "install", "--disable-pip-version-check", "-r",
                     str(root / "tools/lunitora_mcp/requirements.lock")])
    if result.returncode:
        raise ConfigurationError("Pinned dependency installation failed. Check network/package access and rerun setup; external applications were not installed.")
    state = inspect_environment(root, platform, runner)
    if not state["ready"]:
        raise ConfigurationError("Repository environment self-test failed after dependency installation.")
    state["state"] = "created" if created else "repaired/updated"
    return state
