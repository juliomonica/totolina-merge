"""Disposable bootstrap/configuration tests; never change workstation settings."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lunitora_machine import applications, bootstrap, configuration as config, environment
from lunitora_machine.policy import LauncherError
from lunitora_machine.readiness import summarize

SOURCE = Path(__file__).absolute().parents[2]


def result(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


class Platform:
    name = "windows"

    def __init__(self):
        self.matches = {kind: [] for kind in config.KINDS}
        self.valid = {}
        self.fail = set()
        self.discoveries = []

    def validate_application(self, kind, path):
        if path not in self.valid:
            raise LauncherError("not valid")
        return self.valid[path]

    def discover(self, kind, configured=None):
        self.discoveries.append((kind, configured))
        if kind in self.fail:
            raise LauncherError("inspection unavailable")
        return self.matches[kind]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lunitora setup space ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "tools/lunitora_mcp/bridges/photoshop_uxp").mkdir(parents=True)
        (self.root / "project.godot").write_text('config/name="Totolina Merge"\n', encoding="utf-8")
        (self.root / "tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json").write_text('{"id":"com.lunitora.photoshop.bridge"}', encoding="utf-8")
        shutil.copyfile(SOURCE / "tools/lunitora_requirements.json", self.root / "tools/lunitora_requirements.json")
        (self.root / "tools/lunitora_mcp/requirements.lock").write_text('mcp==2.2.0\npywin32==312 ; sys_platform == "win32"\n', encoding="utf-8")
        self.platform = Platform()
        self.aliases = {}
        self.calls = []

    def runner(self, command, **kwargs):
        self.calls.append(command)
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return result(str(self.root))
        if "--get-all" in command:
            value = self.aliases.get(command[-1])
            return result(value + "\n" if value else "", 0 if value else 1)
        if "--replace-all" in command:
            self.aliases[command[-2]] = command[-1]
            return result()
        if "ls-files" in command:
            return result(returncode=1 if "--error-unmatch" in command else 0)
        if "check-ignore" in command:
            return result()
        raise AssertionError(command)

    def healthy(self):
        return {"ready": True, "state": "already correct", "reason": "pinned dependencies verified"}

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.rglob("*") if path.is_file()}

    def app(self, kind, path=None):
        return {"kind": kind, "path": path or "C:\\Apps\\" + kind + ".exe", "version": "1", "identity": kind}


class ConfigurationTests(Fixture):
    def test_empty_schema(self):
        data, state = config.load_config(self.root, "windows")
        self.assertEqual(state, "missing")
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(set(data["applications"]), set(config.KINDS))
        self.assertTrue(all(value is None for value in data["applications"].values()))

    def test_save_rerun_is_noop(self):
        data = config.empty_config(self.root, "windows")
        self.assertTrue(config.save_config(self.root, data))
        before = self.snapshot()
        self.assertFalse(config.save_config(self.root, data))
        self.assertEqual(before, self.snapshot())

    def test_schema_forbids_secrets_and_wrong_kind(self):
        data = config.empty_config(self.root, "windows")
        data["password"] = "never stored"
        with self.assertRaises(config.ConfigurationError):
            config.save_config(self.root, data)
        del data["password"]
        data["applications"]["desktop"] = self.app("godot")
        with self.assertRaises(config.ConfigurationError):
            config.save_config(self.root, data)

    def test_duplicate_json_rejected(self):
        config.local_path(self.root).parent.mkdir()
        config.local_path(self.root).write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        with self.assertRaises(config.ConfigurationError):
            config.load_config(self.root, "windows")

    def test_explicit_setup_recovers_bad_json_and_schema_preserving_bytes(self):
        for payload in (b"{bad json", b'{"schema_version":999}'):
            with self.subTest(payload=payload):
                path = config.local_path(self.root)
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(payload)
                before_backups = set(path.parent.glob("config-invalid-*.json"))
                data, state = config.load_setup_config(self.root, "windows", prompt=lambda _: "yes", emit=lambda _: None)
                self.assertEqual(state, "rebuild approved")
                self.assertEqual(data, config.empty_config(self.root, "windows"))
                self.assertFalse(path.exists())
                new_backups = set(path.parent.glob("config-invalid-*.json")) - before_backups
                self.assertEqual(len(new_backups), 1)
                self.assertEqual(new_backups.pop().read_bytes(), payload)
                config.save_config(self.root, data)
                self.assertEqual(config.load_config(self.root, "windows")[0], data)

    def test_moved_checkout_recovery_does_not_trust_old_paths(self):
        data = config.empty_config(self.root, "windows")
        data["repository_root"] = str(self.root / "old checkout")
        data["applications"]["desktop"] = self.app("desktop")
        path = config.local_path(self.root)
        path.parent.mkdir()
        path.write_text(json.dumps(data), encoding="utf-8")
        recovered, _ = config.load_setup_config(self.root, "windows", prompt=lambda _: "y", emit=lambda _: None)
        self.assertTrue(all(app is None for app in recovered["applications"].values()))

    def test_invalid_config_check_and_declined_rebuild_are_readonly(self):
        path = config.local_path(self.root)
        path.parent.mkdir()
        path.write_bytes(b"invalid")
        before = self.snapshot()
        with self.assertRaises(config.ConfigurationError):
            config.load_setup_config(self.root, "windows", check=True,
                                     prompt=lambda _: self.fail("Check prompted"))
        with self.assertRaises(config.ConfigurationError):
            config.load_setup_config(self.root, "windows", prompt=lambda _: "", emit=lambda _: None)
        self.assertEqual(before, self.snapshot())

    def test_recovery_race_never_quarantines_new_configuration(self):
        path = config.local_path(self.root)
        path.parent.mkdir()
        path.write_bytes(b"invalid")
        def approve(_):
            path.write_bytes(b"different")
            return "yes"
        with self.assertRaisesRegex(config.ConfigurationError, "changed during recovery"):
            config.load_setup_config(self.root, "windows", prompt=approve, emit=lambda _: None)
        self.assertEqual(path.read_bytes(), b"different")
        self.assertFalse(list(path.parent.glob("config-invalid-*.json")))

    def test_invalid_legacy_rebuild_leaves_legacy_untouched(self):
        old = self.root / "tools/operator_launcher/config.local.json"
        old.parent.mkdir()
        old.write_bytes(b"invalid legacy")
        data, _ = config.load_setup_config(self.root, "windows", prompt=lambda _: "yes", emit=lambda _: None)
        config.save_config(self.root, data)
        self.assertEqual(old.read_bytes(), b"invalid legacy")

    def test_legacy_migration_is_readonly_and_preserves_old(self):
        old = self.root / "tools/operator_launcher/config.local.json"
        old.parent.mkdir()
        old.write_text(json.dumps({"repositoryRoot": str(self.root), "desktopExe": "C:\\Apps\\Codex.exe", "photoshopExe": None, "udtExe": None}), encoding="utf-8-sig")
        before = self.snapshot()
        data, state = config.load_config(self.root, "windows")
        self.assertEqual(state, "migration available")
        self.assertEqual(data["applications"]["desktop"]["path"], "C:\\Apps\\Codex.exe")
        self.assertEqual(before, self.snapshot())

    def test_concurrent_config_update_not_overwritten(self):
        old = config.empty_config(self.root, "windows")
        config.save_config(self.root, old)
        other = deepcopy(old)
        other["applications"]["desktop"] = self.app("desktop")
        config.save_config(self.root, other)
        with self.assertRaises(config.ConfigurationError):
            config.save_config(self.root, old, expected=old)
        self.assertEqual(config.load_config(self.root, "windows")[0], other)

    def test_lock_failure_does_not_replace(self):
        path = config.local_path(self.root)
        with config.config_lock(self.root):
            with self.assertRaises(config.ConfigurationError):
                config.save_config(self.root, config.empty_config(self.root, "windows"))
        self.assertFalse(path.exists())

    def test_all_aliases_are_python_local_and_quoted(self):
        states = config.configure_aliases(self.root, "windows", runner=self.runner)
        self.assertEqual(len(states), 7)
        for command in self.calls:
            self.assertNotIn("--global", command)
        for mode, value in config.alias_values("windows").items():
            self.assertEqual(self.aliases["alias." + mode], value)
            self.assertNotIn("powershell", value)
            self.assertNotIn(".venv", value)
            self.assertIn("lunitora_launcher.py", value)
        self.calls.clear()
        config.configure_aliases(self.root, "windows", runner=self.runner)
        self.assertFalse(any("--replace-all" in command for command in self.calls))

    def test_alias_check_has_no_writes(self):
        states = config.configure_aliases(self.root, "windows", check=True, runner=self.runner)
        self.assertTrue(all(state == "missing" for state in states.values()))
        self.assertFalse(any("--replace-all" in command for command in self.calls))

    def test_actual_git_aliases_leave_global_unchanged_and_local_files_ignored(self):
        global_config = self.root / "global fixture"
        global_config.write_text('[user]\n\tname = Untouched\n', encoding="utf-8")
        before = global_config.read_bytes()
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1"}):
            subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
            (self.root / ".gitignore").write_text('/tools/.lunitora/\n/tools/lunitora_mcp/.venv/\n', encoding="utf-8")
            config.configure_aliases(self.root, "windows")
            config.save_config(self.root, config.empty_config(self.root, "windows"))
            checked = subprocess.run(["git", "-C", str(self.root), "check-ignore", "tools/.lunitora/config.json"], capture_output=True, text=True, check=True)
            self.assertIn("config.json", checked.stdout)
        self.assertEqual(before, global_config.read_bytes())

    def test_actual_alias_executes_python_from_nested_checkout_with_spaces(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        base = environment.find_python(SOURCE, "windows")
        (self.root / "tools/lunitora_launcher.py").write_text('import json,os,sys; print(json.dumps({"cwd":os.getcwd(),"mode":sys.argv[1]}))\n', encoding="ascii")
        config.configure_aliases(self.root, "windows", host_python=base)
        nested = self.root / "nested directory"
        nested.mkdir()
        response = subprocess.run(["git", "-C", str(nested), "dev"], capture_output=True, text=True, check=True)
        data = json.loads(response.stdout)
        self.assertEqual(os.path.normcase(data["cwd"]), os.path.normcase(str(self.root)))
        self.assertEqual(data["mode"], "dev")

    def test_stale_lock_file_is_not_permanent_setup_blocker(self):
        path = config.local_path(self.root)
        path.parent.mkdir()
        (path.parent / "setup.lock").write_bytes(b"0")
        self.assertTrue(config.save_config(self.root, config.empty_config(self.root, "windows")))

    def test_repository_identity_and_missing_git(self):
        config.validate_repository(self.root, self.runner)
        (self.root / "project.godot").write_text('config/name="Other"', encoding="utf-8")
        with self.assertRaises(config.ConfigurationError):
            config.validate_repository(self.root, self.runner)
        with self.assertRaisesRegex(config.ConfigurationError, "Git is missing"):
            config.validate_repository(self.root, lambda *args: (_ for _ in ()).throw(FileNotFoundError()))


class DiscoveryTests(Fixture):
    def test_valid_selection_wins_over_multiple_discovered_apps(self):
        app = self.app("desktop")
        self.platform.valid[app["path"]] = app
        self.platform.matches["desktop"] = [app, self.app("desktop", "C:\\Other\\Codex.exe")]
        self.assertEqual(applications.resolve_application("desktop", app, self.platform)[0], app)
        self.assertFalse(self.platform.discoveries)

    def test_stale_path_single_match_repairs(self):
        app = self.app("desktop")
        self.platform.matches["desktop"] = [app]
        fixed, state = applications.resolve_application("desktop", {"path": "C:\\Old\\Codex.exe"}, self.platform)
        self.assertEqual(fixed, app)
        self.assertEqual(state, "repaired/updated")

    def test_ambiguity_never_silently_chooses(self):
        self.platform.matches["desktop"] = [self.app("desktop"), self.app("desktop", "C:\\Other\\Codex.exe")]
        app, state = applications.resolve_application("desktop", None, self.platform)
        self.assertIsNone(app)
        self.assertEqual(state, "requires user selection")

    def test_setup_selection_and_explicit_path_validation(self):
        app = self.app("desktop")
        self.platform.matches["desktop"] = [app, self.app("desktop", "C:\\Other\\Codex.exe")]
        self.assertEqual(applications.resolve_application("desktop", None, self.platform, interactive=True, prompt=lambda _: "2")[0]["path"], "C:\\Other\\Codex.exe")
        self.platform.matches["desktop"] = []
        self.platform.valid[app["path"]] = app
        self.assertEqual(applications.resolve_application("desktop", None, self.platform, interactive=True, prompt=lambda _: app["path"])[0], app)

    def test_runtime_ambiguity_never_prompts_or_writes(self):
        data = config.empty_config(self.root, "windows")
        self.platform.matches["desktop"] = [self.app("desktop"), self.app("desktop", "C:\\Other\\Codex.exe")]
        before = self.snapshot()
        with patch("builtins.input", side_effect=AssertionError("runtime prompt")):
            with self.assertRaisesRegex(LauncherError, "python tools/lunitora_setup.py"):
                applications.runtime_applications(self.root, data, self.platform, "dev")
        self.assertEqual(before, self.snapshot())

    def test_runtime_repairs_only_required_capability(self):
        data = config.empty_config(self.root, "windows")
        data["applications"]["desktop"] = {"path": "C:\\Old\\Codex.exe"}
        config.save_config(self.root, data)
        self.platform.matches["desktop"] = [self.app("desktop")]
        got = applications.runtime_applications(self.root, data, self.platform, "dev")
        self.assertEqual(got["desktop"], self.app("desktop"))
        self.assertEqual([kind for kind, _ in self.platform.discoveries], ["desktop"])

    def test_daily_check_does_not_persist_deterministic_repairs(self):
        data = config.empty_config(self.root, "windows")
        data["applications"]["desktop"] = {"path": "C:\\Old\\Codex.exe"}
        config.save_config(self.root, data)
        self.platform.matches["desktop"] = [self.app("desktop")]
        before = self.snapshot()
        applications.runtime_applications(self.root, data, self.platform, "dev", check=True)
        self.assertEqual(before, self.snapshot())

    def test_nonterminal_setup_selection_eof_skips_optional_app(self):
        def eof(_):
            raise EOFError()
        app, state = applications.resolve_application("photoshop", None, self.platform, interactive=True, prompt=eof)
        self.assertIsNone(app)
        self.assertEqual(state, "missing")

    def test_optional_inspection_failure_isolated(self):
        self.platform.fail.add("photoshop")
        updated, states = applications.resolve_config(config.empty_config(self.root, "windows"), self.platform, tolerant=True)
        self.assertIsNone(updated["applications"]["photoshop"])
        self.assertIn("inspection unavailable", states["photoshop"])


class BootstrapTests(Fixture):
    def test_first_setup_and_idempotent_rerun(self):
        emitted = []
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()):
            self.assertEqual(bootstrap.bootstrap(self.root, self.platform, interactive=False, runner=self.runner, emit=emitted.append), 0)
            before = self.snapshot()
            self.assertEqual(bootstrap.bootstrap(self.root, self.platform, interactive=False, runner=self.runner, emit=emitted.append), 0)
        self.assertEqual(before, self.snapshot())
        self.assertTrue((self.root / "source_art/_inbox").is_dir())
        self.assertTrue((self.root / "source_art/_staging").is_dir())
        self.assertTrue(any("Core:" in line for line in emitted))
        self.assertTrue(any("iOS: REQUIRES MAC" in line for line in emitted))

    def test_check_entire_fixture_unchanged_even_when_repairs_available(self):
        data = config.empty_config(self.root, "windows")
        data["applications"]["godot"] = {"path": "C:\\Old\\Godot.exe"}
        config.save_config(self.root, data)
        self.platform.matches["godot"] = [self.app("godot")]
        before = self.snapshot()
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()) as env:
            bootstrap.bootstrap(self.root, self.platform, check=True, prompt=lambda _: self.fail("doctor prompt"), runner=self.runner, emit=lambda _: None)
        self.assertTrue(env.call_args.kwargs["check"])
        self.assertFalse(env.call_args.kwargs["interactive"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse(any("--replace-all" in command for command in self.calls))

    def test_missing_optional_tools_dont_fail_core(self):
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()):
            self.assertEqual(bootstrap.bootstrap(self.root, self.platform, interactive=False, runner=self.runner, emit=lambda _: None), 0)
        states = summarize("windows", True, {})
        self.assertEqual(states["Core"]["state"], "READY")
        self.assertNotEqual(states["Game"]["state"], "READY")

    def test_unavailable_inspection_preserves_cache_but_not_readiness(self):
        data = config.empty_config(self.root, "windows")
        app = self.app("desktop")
        data["applications"]["desktop"] = app
        config.save_config(self.root, data)
        self.platform.fail.add("desktop")
        emitted = []
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()):
            self.assertEqual(bootstrap.bootstrap(self.root, self.platform, interactive=False, runner=self.runner, emit=emitted.append), 0)
        self.assertEqual(config.load_config(self.root, "windows")[0]["applications"]["desktop"], app)
        self.assertTrue(any("inspection unavailable" in line for line in emitted))

    def test_missing_environment_check_does_not_create(self):
        before = self.snapshot()
        state = environment.ensure_environment(self.root, "windows", check=True, runner=self.runner)
        self.assertFalse(state["ready"])
        self.assertEqual(before, self.snapshot())


class EnvironmentTests(Fixture):
    def prepare_env(self):
        executable = environment.python_path(self.root, "windows")
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture")
        (executable.parents[1] / "pyvenv.cfg").write_text('include-system-site-packages = false\nversion = 3.12.10\n', encoding="utf-8")
        return executable

    def probe_data(self):
        prefix = str(environment.python_path(self.root, "windows").parents[1])
        return {"version": [3, 12, 10], "bits": 64, "prefix": prefix, "base_prefix": "C:\\Python312", "packages": {"mcp": "2.2.0", "pywin32": "312"}}

    def test_pins_platform_qualified_without_version_changes(self):
        self.assertEqual(environment.pins(self.root, "windows"), {"mcp": "2.2.0", "pywin32": "312"})
        self.assertEqual(environment.pins(self.root, "macos"), {"mcp": "2.2.0"})

    def test_invalid_or_duplicate_lock_fails(self):
        path = self.root / "tools/lunitora_mcp/requirements.lock"
        for text in ("mcp>=2\n", "mcp==2\nmcp==2\n", ""):
            path.write_text(text, encoding="ascii")
            with self.assertRaises(config.ConfigurationError):
                environment.pins(self.root, "windows")

    def test_valid_environment_not_recreated_or_installed(self):
        self.prepare_env()
        calls = []
        def runner(command):
            calls.append(command)
            return result(json.dumps(self.probe_data())) if "-c" in command else result()
        state = environment.ensure_environment(self.root, "windows", runner=runner)
        self.assertTrue(state["ready"])
        self.assertFalse(any("install" in command or "venv" in command for command in calls))
        self.assertTrue(all("-B" in command for command in calls))

    def test_wrong_python_or_system_site_environment_not_overwritten(self):
        self.prepare_env()
        before = self.snapshot()
        bad = self.probe_data()
        bad["version"] = [3, 14, 0]
        with self.assertRaises(config.ConfigurationError):
            environment.ensure_environment(self.root, "windows", runner=lambda _: result(json.dumps(bad)))
        self.assertEqual(before, self.snapshot())

    def test_creation_install_and_health_are_repo_only(self):
        calls = []
        def runner(command):
            calls.append(command)
            if "venv" in command:
                self.prepare_env()
            if "-c" in command:
                return result(json.dumps(self.probe_data()))
            return result()
        with patch.object(environment, "find_python", return_value="C:\\Python312\\python.exe"):
            state = environment.ensure_environment(self.root, "windows", runner=runner)
        self.assertEqual(state["state"], "created")
        installs = [command for command in calls if "install" in command]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0][0], str(environment.python_path(self.root, "windows")))
        self.assertEqual(installs[0][-1], str(self.root / "tools/lunitora_mcp/requirements.lock"))
        self.assertNotIn("--upgrade", installs[0])

    def test_in_use_update_is_deferred(self):
        self.prepare_env()
        usage = {"state": "in_use", "blockers": [{"role": "Godot MCP server", "pid": 123,
                  "executable": str(environment.python_path(self.root, "windows"))}], "ambiguities": []}
        with patch.object(environment, "inspect_environment", return_value={"ready": False}), \
                patch.object(environment, "inspect_environment_use", return_value=usage):
            state = environment.ensure_environment(self.root, "windows", runner=lambda _: self.fail("installation attempted"))
        self.assertTrue(state["deferred"])
        self.assertEqual(state["usage"], usage)
        self.assertFalse(state["ready"])

    def test_failed_install_one_attempt(self):
        self.prepare_env()
        calls = []
        with patch.object(environment, "inspect_environment", return_value={"ready": False}), \
                patch.object(environment, "inspect_environment_use", return_value={"state": "free", "blockers": [], "ambiguities": []}):
            def runner(command):
                calls.append(command)
                return result(returncode=1)
            with self.assertRaises(config.ConfigurationError):
                environment.ensure_environment(self.root, "windows", runner=runner)
        self.assertEqual(len(calls), 1)

    def test_missing_config_venv_never_replaced(self):
        directory = environment.python_path(self.root, "windows").parents[1]
        directory.mkdir(parents=True)
        with self.assertRaisesRegex(config.ConfigurationError, "refusing replacement"):
            environment.ensure_environment(self.root, "windows", runner=lambda _: self.fail("unexpected process"))

    def test_real_readonly_existing_environment_probe(self):
        if not environment.python_path(SOURCE, "windows").is_file():
            self.skipTest("Repository Windows environment unavailable")
        state = environment.inspect_environment(SOURCE, "windows")
        wanted = environment.pins(SOURCE, "windows")
        self.assertEqual(state["ready"], all(state["data"]["packages"].get(key) == value for key, value in wanted.items()))
        self.assertTrue(state["inspection_ready"])
        self.assertEqual(len(wanted), 30)

    def test_corrupt_import_probe_not_ready(self):
        self.prepare_env()
        def runner(command):
            if command[-1] == environment.PROBE:
                return result(json.dumps(self.probe_data()))
            if "-c" in command:
                return result(returncode=1)
            return result()
        self.assertFalse(environment.inspect_environment(self.root, "windows", runner)["ready"])

    def test_real_stdlib_usage_probe_is_readonly(self):
        if os.name != "nt":
            self.skipTest("Windows-only usage probe")
        self.assertIs(type(environment.environment_in_use(SOURCE, "windows")), bool)


if __name__ == "__main__":
    unittest.main()
