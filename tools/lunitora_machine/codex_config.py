"""Project-scoped MCP provisioning without changing trust or user policy."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import uuid

from .configuration import ConfigurationError, config_lock, reject_redirects, run
from .policy import same_path

GODOT_TOOLS = (
    "godot_ping", "godot_get_editor_state", "godot_inspect_scene",
    "godot_create_rig_lab", "godot_create_rig_lab_animation",
    "godot_create_tolina_rig_lab", "godot_create_tolina_lab_blink",
    "godot_create_rig_test_cat_deformation_lab", "godot_create_rig_test_cat_deformation_demo",
)
PHOTOSHOP_TOOLS = ("photoshop_ping", "photoshop_get_active_document", "photoshop_process_image")
PROFILES = {
    "godot": ("lunitora_godot", "core.godot_server", 10, GODOT_TOOLS),
    "photoshop": ("lunitora_photoshop", "core.server", 35, PHOTOSHOP_TOOLS),
}
_MAX_BYTES = 2 * 1024 * 1024


def project_config_path(root):
    return root / ".codex/config.toml"


def ownership_path(root):
    return root / "tools/.lunitora/codex-owned.json"


def _user_config_path():
    base = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    if not base.is_absolute():
        raise ConfigurationError("CODEX_HOME must be an absolute local directory; MCP configuration was preserved.")
    return base / "config.toml"


def _plain(path):
    reject_redirects(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ConfigurationError("MCP configuration storage must be a regular, non-hardlinked file.")
    if info.st_size > _MAX_BYTES:
        raise ConfigurationError("MCP configuration exceeds the safe setup size limit.")


def _read(path):
    _plain(path)
    return path.read_bytes() if path.exists() else None


def _admit_local(root, path, runner):
    _plain(path)
    relative = path.relative_to(root).as_posix()
    tracked = runner(["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative])
    if tracked.returncode == 0:
        raise ConfigurationError("MCP machine-local storage is tracked by Git; no setup write is permitted.")
    if tracked.returncode != 1:
        raise ConfigurationError("Cannot verify MCP machine-local Git tracking status.")
    ignored = runner(["git", "-C", str(root), "check-ignore", "--", relative])
    if ignored.returncode != 0:
        raise ConfigurationError("MCP machine-local storage must be ignored by Git before setup can use it.")


def _toml():
    from . import structural_toml
    return structural_toml


def _document(payload, *, check=False):
    if check:
        import tomllib
        parser, empty = tomllib.loads, dict
    else:
        library = _toml()
        parser, empty = library.parse, library.document
    if payload is None:
        return empty()
    try:
        return parser(payload.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        # Parser errors may contain a source line with credentials.
        raise ConfigurationError("Invalid Codex TOML; setup preserved it without displaying its contents.") from None


def _unwrapped(value):
    return value.unwrap() if hasattr(value, "unwrap") else value


def _fingerprint(entry):
    try:
        encoded = json.dumps(_unwrapped(entry), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise ConfigurationError("MCP entry cannot be safely recorded as setup-owned.") from None
    return hashlib.sha256(encoded).hexdigest()


def _manifest(payload, root, platform):
    empty = {"schema_version": 1, "repository_root": str(root.absolute()),
             "platform": platform, "entries": {}}
    if payload is None:
        return empty
    try:
        def unique(pairs):
            output = {}
            for key, value in pairs:
                if key in output:
                    raise ValueError()
                output[key] = value
            return output
        result = json.loads(payload, object_pairs_hook=unique)
        if (not isinstance(result, dict) or set(result) != set(empty)
                or type(result["schema_version"]) is not int or result["schema_version"] != 1
                or result["repository_root"] != empty["repository_root"]
                or result["platform"] != platform or not isinstance(result["entries"], dict)):
            raise ValueError()
        names = {item[0] for item in PROFILES.values()}
        for name, record in result["entries"].items():
            if (name not in names or not isinstance(record, dict) or set(record) != {"sha256"}
                    or not isinstance(record["sha256"], str) or len(record["sha256"]) != 64
                    or any(char not in "0123456789abcdef" for char in record["sha256"])):
                raise ValueError()
        return result
    except (UnicodeError, ValueError, TypeError):
        raise ConfigurationError("Invalid MCP ownership record; setup will not adopt or overwrite existing entries.") from None


def desired_entry(root, platform, capability):
    _, module, timeout, tools = PROFILES[capability]
    executable = ".venv/Scripts/python.exe" if platform == "windows" else ".venv/bin/python"
    toolkit = root / "tools/lunitora_mcp"
    return {"command": str(toolkit / executable), "args": ["-B", "-m", module],
            "cwd": str(toolkit), "startup_timeout_sec": 15, "tool_timeout_sec": timeout,
            "enabled_tools": list(tools)}


def _same_path(first, second, platform):
    if not isinstance(first, str) or not isinstance(second, str):
        return False
    if platform == "windows":
        return same_path(first, second)
    return first == second


def _compatible(entry, desired, platform):
    if not isinstance(entry, Mapping) or set(entry) & {
            "url", "http_headers", "headers", "bearer_token_env_var", "auth", "env_http_headers",
            "http_headers_helper", "oauth_resource", "oauth", "scopes"}:
        return False
    data = _unwrapped(entry)
    if (not _same_path(data.get("command"), desired["command"], platform)
            or data.get("args") != desired["args"]
            or not _same_path(data.get("cwd"), desired["cwd"], platform)):
        return False
    allowed = data.get("enabled_tools")
    if (not isinstance(allowed, list) or any(not isinstance(tool, str) for tool in allowed)
            or len(set(allowed)) != len(allowed) or not set(allowed) <= set(desired["enabled_tools"])):
        return False
    for key in ("enabled", "required"):
        if key in data and type(data[key]) is not bool:
            return False
    approval_modes = {"auto", "prompt", "writes", "approve"}
    if "default_tools_approval_mode" in data:
        mode = data["default_tools_approval_mode"]
        if not isinstance(mode, str) or mode not in approval_modes:
            return False
    tool_policy = data.get("tools", {})
    if not isinstance(tool_policy, dict):
        return False
    for name, policy in tool_policy.items():
        if not isinstance(name, str) or not isinstance(policy, dict):
            return False
        if "approval_mode" in policy:
            mode = policy["approval_mode"]
            if not isinstance(mode, str) or mode not in approval_modes:
                return False
        if "output_token_limit" in policy and (type(policy["output_token_limit"]) is not int or policy["output_token_limit"] <= 0):
            return False
    for key in ("startup_timeout_sec", "startup_timeout_ms", "tool_timeout_sec"):
        if key in data and (type(data[key]) not in (int, float) or data[key] <= 0
                            or (type(data[key]) is float and not math.isfinite(data[key]))):
            return False
    if data.get("experimental_environment", "local") != "local":
        return False
    environment = data.get("env", {})
    if not isinstance(environment, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                                              for key, value in environment.items()):
        return False
    sources = data.get("env_vars", [])
    if not isinstance(sources, list):
        return False
    for source in sources:
        if isinstance(source, str):
            continue
        if (not isinstance(source, dict) or set(source) - {"name", "source"}
                or not isinstance(source.get("name"), str) or source.get("source", "local") != "local"):
            return False
    denied = data.get("disabled_tools", [])
    return isinstance(denied, list) and all(isinstance(tool, str) for tool in denied)


def _restricted(entry):
    data = _unwrapped(entry)
    return data.get("enabled") is False or not set(data["enabled_tools"]) - set(data.get("disabled_tools", []))


def _no_broader(project, inherited):
    first, second = _unwrapped(project), _unwrapped(inherited)
    if second.get("enabled") is False and first.get("enabled") is not False:
        return False
    if not set(first["enabled_tools"]) <= set(second["enabled_tools"]):
        return False
    if not set(second.get("disabled_tools", [])) <= set(first.get("disabled_tools", [])):
        return False
    for key in ("default_tools_approval_mode", "tools", "env", "env_vars"):
        if key in second and first.get(key) != second[key]:
            return False
    return True


def _servers(document):
    servers = document.get("mcp_servers", {})
    if not isinstance(servers, Mapping):
        raise ConfigurationError("Codex mcp_servers is not a table; configuration was preserved.")
    return servers


def _profile_overrides(document, names):
    profiles = document.get("profiles", {})
    if not isinstance(profiles, Mapping):
        raise ConfigurationError("Codex profiles are not a table; configuration was preserved.")
    conflicts = set()
    for profile in profiles.values():
        if not isinstance(profile, Mapping):
            raise ConfigurationError("Codex profile is not a table; configuration was preserved.")
        conflicts.update(set(_servers(profile)) & names)
    return conflicts


def _status(ready, state, reason):
    return {"ready": ready, "state": state, "reason": reason}


def _atomic(path, payload):
    temporary = path.with_name(".lunitora-codex-" + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace_pair(project, owned, payload, manifest_payload, originals):
    _atomic(project, payload)
    try:
        _atomic(owned, manifest_payload)
    except OSError:
        # Roll back only bytes we still own, never concurrent user edits.
        try:
            if _read(project) != payload or _read(owned) != originals[owned]:
                raise ConfigurationError("MCP ownership write failed after configuration changed; rerun setup for safe inspection.")
            if originals[project] is None:
                project.unlink()
            else:
                _atomic(project, originals[project])
        except (OSError, ConfigurationError):
            raise ConfigurationError("MCP ownership write failed; configuration may be partially prepared and is not adopted. Rerun setup for safe inspection.") from None
        raise ConfigurationError("MCP ownership write failed; the project configuration was restored to its exact previous bytes.") from None


def provision_codex(root: Path, platform_name: str, capabilities, *, check=False,
                    runner=run, user_config=None):
    """Only new entries are adopted; compatible custom entries stay unowned."""
    root = root.absolute()
    selected = tuple(dict.fromkeys(capabilities))
    if platform_name not in ("windows", "macos") or any(key not in PROFILES for key in selected):
        raise ConfigurationError("Unsupported MCP setup platform/capability.")
    if not selected:
        return {}
    results = {}
    changed = set()
    project = project_config_path(root)
    owned = ownership_path(root)
    try:
        inherited = Path(user_config) if user_config is not None else _user_config_path()
        if not inherited.is_absolute() or inherited == project:
            raise ConfigurationError("User and project Codex configuration paths must be separate absolute files.")
        for path in (project, owned, owned.with_name("codex.lock")):
            _admit_local(root, path, runner)
        originals = {path: _read(path) for path in (project, owned, inherited)}
        document = _document(originals[project], check=check)
        global_document = _document(originals[inherited], check=check)
        manifest = _manifest(originals[owned], root, platform_name)
        updated_manifest = deepcopy(manifest)
        project_servers, global_servers = _servers(document), _servers(global_document)
        names = {PROFILES[key][0] for key in selected}
        profile_overrides = _profile_overrides(document, names) | _profile_overrides(global_document, names)
        for capability in selected:
            name = PROFILES[capability][0]
            desired = desired_entry(root, platform_name, capability)
            existing, global_entry = project_servers.get(name), global_servers.get(name)
            record = manifest["entries"].get(name)
            if name in profile_overrides:
                results[capability] = _status(False, "conflict", "A named Codex profile overrides this MCP entry; setup preserved it for user review.")
                continue
            if global_entry is not None and not _compatible(global_entry, desired, platform_name):
                results[capability] = _status(False, "conflict", "User-level MCP entry has custom transport/tool policy; no override was created.")
                continue
            if record is not None:
                try:
                    unchanged = isinstance(existing, Mapping) and _fingerprint(existing) == record["sha256"]
                except ConfigurationError:
                    unchanged = False
                if not unchanged:
                    results[capability] = _status(False, "conflict", "Setup-owned MCP entry was edited or removed; user choices were preserved.")
                    continue
                candidate = deepcopy(existing)
                candidate["command"], candidate["cwd"] = desired["command"], desired["cwd"]
                if not _compatible(candidate, desired, platform_name):
                    results[capability] = _status(False, "conflict", "Setup-owned MCP policy does not match the reviewed contract.")
                    continue
                if global_entry is not None and not _no_broader(candidate, global_entry):
                    results[capability] = _status(False, "conflict", "Project MCP entry would override a narrower user-level restriction; no change was made.")
                    continue
                if _unwrapped(candidate) != _unwrapped(existing):
                    project_servers[name] = candidate
                    updated_manifest["entries"][name] = {"sha256": _fingerprint(candidate)}
                    changed.add(capability)
                    results[capability] = _status(not check, "repair available" if check else "repaired/updated", "Only setup-owned direct-Python transport paths are updated; policy is unchanged.")
                else:
                    results[capability] = _status(not _restricted(existing), "already correct" if not _restricted(existing) else "user restricted", "Setup-owned configuration is preserved; live connection acceptance is separate.")
            elif existing is not None:
                if not _compatible(existing, desired, platform_name):
                    results[capability] = _status(False, "conflict", "Project MCP entry has custom transport/tool policy; setup did not overwrite it.")
                elif global_entry is not None and not _no_broader(existing, global_entry):
                    results[capability] = _status(False, "conflict", "Project and user-level MCP restrictions differ; both entries were preserved.")
                else:
                    results[capability] = _status(not _restricted(existing), "compatible custom" if not _restricted(existing) else "user restricted", "Existing project entry is retained byte-for-byte and is not adopted by setup.")
            elif global_entry is not None:
                results[capability] = _status(not _restricted(global_entry), "compatible inherited" if not _restricted(global_entry) else "user restricted", "Existing user-level entry is retained; no project override or global write is made.")
            else:
                if "mcp_servers" not in document:
                    document["mcp_servers"] = {} if check else _toml().table()
                    project_servers = document["mcp_servers"]
                project_servers[name] = deepcopy(desired) if check else _toml().item(desired)
                updated_manifest["entries"][name] = {"sha256": _fingerprint(desired)}
                changed.add(capability)
                results[capability] = _status(not check, "creation available" if check else "created", "Project-scoped direct-Python MCP entry; trust and live acceptance still require the user.")
        if changed and not check:
            try:
                payload = _toml().dumps(document).encode("utf-8")
            except ValueError:
                raise ConfigurationError("Codex TOML layout cannot be safely updated; existing configuration was preserved for user review.") from None
            manifest_payload = (json.dumps(updated_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with config_lock(root, "codex.lock"):
                for path in (project, owned, owned.with_name("codex.lock")):
                    _admit_local(root, path, runner)
                if any(_read(path) != before for path, before in originals.items()):
                    raise ConfigurationError("Codex configuration changed during setup; no planned changes were applied.")
                reject_redirects(project.parent)
                project.parent.mkdir(exist_ok=True)
                _replace_pair(project, owned, payload, manifest_payload, originals)
        return results
    except (ConfigurationError, OSError) as error:
        # OSError filenames and external TOML lines must not leak into diagnostics.
        reason = str(error) if isinstance(error, ConfigurationError) else "MCP storage could not be safely accessed; existing files were preserved."
        return {key: _status(False, "conflict", reason) for key in selected}
