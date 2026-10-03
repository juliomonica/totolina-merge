"""Host-runtime isolation proofs; all executable fixtures are disposable."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lunitora_machine import bootstrap, configuration, environment, host_runtime

SOURCE = Path(__file__).absolute().parents[2]


def host_python():
    """Use the prerequisite interpreter, not a test runner's venv redirector."""
    return str(Path(getattr(sys, "_base_executable", sys.executable)).absolute())


class DisposableCheckout(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lunitora host checkout space ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        tools = self.root / "tools"
        tools.mkdir()
        shutil.copytree(SOURCE / "tools/lunitora_machine", tools / "lunitora_machine",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for filename in ("lunitora_launcher.py", "lunitora_setup.py", "lunitora_requirements.json"):
            shutil.copyfile(SOURCE / "tools" / filename, tools / filename)
        toolkit = tools / "lunitora_mcp"
        manifest = toolkit / "bridges/photoshop_uxp/manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"id":"com.lunitora.photoshop.bridge"}\n', encoding="ascii")
        shutil.copyfile(SOURCE / "tools/lunitora_mcp/requirements.lock", toolkit / "requirements.lock")
        (self.root / "project.godot").write_text('config/name="Totolina Merge"\n', encoding="ascii")
        (self.root / ".gitignore").write_text("/tools/.lunitora/\n/tools/lunitora_mcp/.venv/\n", encoding="ascii")
        subprocess.run(["git", "init", "-q", str(self.root)], capture_output=True, check=True)

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.rglob("*") if path.is_file()}

    def execute_launcher(self, mode):
        return subprocess.run([host_python(), "-I", "-S", "-B",
                               str(self.root / "tools/lunitora_launcher.py"), mode],
                              cwd=self.root, capture_output=True, text=True, timeout=30, check=False)


@unittest.skipUnless(os.name == "nt", "Windows launcher acceptance")
class HostLauncherIsolation(DisposableCheckout):
    def test_actual_entrypoint_runs_all_seven_modes_without_mcp_venv(self):
        before = self.snapshot()
        for mode in configuration.MODES:
            with self.subTest(mode=mode):
                response = self.execute_launcher(mode)
                self.assertEqual(response.returncode, 1)
                self.assertIn("python tools/lunitora_setup.py", response.stderr)
                self.assertNotIn("ModuleNotFoundError", response.stderr)
                self.assertNotIn("Traceback", response.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "tools/lunitora_mcp/.venv").exists())

    def test_actual_entrypoint_runs_all_seven_modes_with_broken_mcp_interpreter(self):
        executable = environment.python_path(self.root, "windows")
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"deliberately nonexecutable managed payload")
        (executable.parents[1] / "pyvenv.cfg").write_text(
            "include-system-site-packages = false\nversion = 3.12.10\n", encoding="ascii")
        before = self.snapshot()
        for mode in configuration.MODES:
            with self.subTest(mode=mode):
                response = self.execute_launcher(mode)
                self.assertEqual(response.returncode, 1)
                self.assertIn("python tools/lunitora_setup.py", response.stderr)
                self.assertNotIn("ModuleNotFoundError", response.stderr)
                self.assertNotIn("Traceback", response.stderr)
        self.assertEqual(before, self.snapshot())


class LauncherAdmission(unittest.TestCase):
    def setUp(self):
        self.launcher = importlib.import_module("lunitora_launcher")

    def test_unhealthy_managed_environment_never_launches_desktop(self):
        with patch.object(self.launcher, "validate_repository"), \
                patch.object(self.launcher, "require_current_host"), \
                patch.object(self.launcher, "platform_name", return_value="windows"), \
                patch.object(self.launcher, "inspect_environment", return_value={
                    "ready": False, "state": "dependency update available", "reason": "pinned dependency repair required"}), \
                patch.object(self.launcher, "runtime_applications") as applications, \
                patch.object(self.launcher, "run_workflow") as workflow:
            for mode in configuration.MODES:
                with self.subTest(mode=mode), redirect_stderr(io.StringIO()) as output:
                    self.assertEqual(self.launcher.main([mode]), 1)
                    self.assertIn("python tools/lunitora_setup.py", output.getvalue())
            applications.assert_not_called()
            workflow.assert_not_called()

    def test_launcher_healthy_payload_preserves_every_workflow_mode(self):
        applications = {"desktop": {"path": "host-owned Desktop"}}
        with patch.object(self.launcher, "validate_repository"), \
                patch.object(self.launcher, "require_current_host"), \
                patch.object(self.launcher, "platform_name", return_value="windows"), \
                patch.object(self.launcher, "inspect_environment", return_value={"ready": True}), \
                patch.object(self.launcher, "load_config", return_value=({}, "already correct")), \
                patch.object(self.launcher, "get_platform", return_value="windows adapter"), \
                patch.object(self.launcher, "runtime_applications", return_value=applications), \
                patch.object(self.launcher, "run_workflow") as workflow:
            for mode in configuration.MODES:
                with self.subTest(mode=mode):
                    self.assertEqual(self.launcher.main([mode]), 0)
                    self.assertEqual(workflow.call_args.args[0], mode)
                    self.assertIs(workflow.call_args.args[1], applications)

    def test_daily_check_never_launches_when_payload_is_healthy(self):
        with patch.object(self.launcher, "validate_repository"), \
                patch.object(self.launcher, "require_current_host"), \
                patch.object(self.launcher, "platform_name", return_value="windows"), \
                patch.object(self.launcher, "inspect_environment", return_value={"ready": True}), \
                patch.object(self.launcher, "load_config", return_value=({}, "already correct")), \
                patch.object(self.launcher, "get_platform"), \
                patch.object(self.launcher, "runtime_applications"), \
                patch.object(self.launcher, "run_workflow") as workflow, redirect_stdout(io.StringIO()):
            for mode in configuration.MODES:
                self.assertEqual(self.launcher.main([mode, "--check"]), 0)
            workflow.assert_not_called()


class HostImportIsolation(DisposableCheckout):
    def test_setup_and_launcher_import_in_isolated_host_without_payload_packages(self):
        source = """import importlib.abc,importlib,sys
blocked={'mcp','websockets','tomlkit','pythoncom','pywintypes','win32api','win32com','win32file','win32security'}
class RejectPayload(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in blocked:
            raise RuntimeError('managed payload package entered host runtime')
sys.meta_path.insert(0,RejectPayload())
sys.path.insert(0,sys.argv[1])
for name in ('lunitora_setup','lunitora_launcher','lunitora_machine.applications','lunitora_machine.configuration','lunitora_machine.environment','lunitora_machine.platforms.windows','lunitora_machine.platforms.macos','lunitora_machine.workflows'):
    importlib.import_module(name)
print('host imports are independent')
"""
        response = subprocess.run([host_python(), "-I", "-B", "-c", source, str(self.root / "tools")],
                                  capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(response.stdout.strip(), "host imports are independent")


class HostAliases(DisposableCheckout):
    def test_all_seven_aliases_target_host_not_managed_payload(self):
        for platform, executable in (("windows", "C:/Host Python 3.12/python.exe"),
                                     ("macos", "/Library/Host Python 3.12/bin/python3.12")):
            values = configuration.alias_values(platform, host_python=executable)
            self.assertEqual(tuple(values), configuration.MODES)
            for mode, value in values.items():
                with self.subTest(platform=platform, mode=mode):
                    self.assertIn(executable, value)
                    self.assertIn("tools/lunitora_launcher.py", value)
                    self.assertTrue(value.endswith(" " + mode))
                    self.assertNotIn(".venv", value)
                    self.assertNotIn("powershell", value.lower())

    def test_actual_seven_aliases_work_from_nested_checkout_with_spaces_without_venv(self):
        executable = host_python()
        stub = "import json,os,sys; print(json.dumps({'cwd':os.getcwd(),'mode':sys.argv[1],'runtime':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix}))\n"
        (self.root / "tools/lunitora_launcher.py").write_text(stub, encoding="ascii")
        configuration.configure_aliases(self.root, "windows", host_python=executable)
        nested = self.root / "nested directory with spaces"
        nested.mkdir()
        for mode in configuration.MODES:
            with self.subTest(mode=mode):
                response = subprocess.run(["git", "-C", str(nested), mode], capture_output=True,
                                          text=True, timeout=30, check=False)
                self.assertEqual(response.returncode, 0, response.stderr)
                outcome = json.loads(response.stdout)
                self.assertEqual(outcome["mode"], mode)
                self.assertEqual(os.path.normcase(outcome["cwd"]), os.path.normcase(str(self.root)))
                self.assertEqual(os.path.normcase(outcome["runtime"]), os.path.normcase(executable))
                self.assertEqual(outcome["prefix"], outcome["base_prefix"])
        self.assertFalse((self.root / "tools/lunitora_mcp/.venv").exists())

    def test_alias_install_rerun_does_not_change_local_or_global_configuration(self):
        global_config = self.root / "unrelated global config"
        global_config.write_text("[user]\n  name = Preserved\n", encoding="ascii")
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config), "GIT_CONFIG_NOSYSTEM": "1"}):
            configuration.configure_aliases(self.root, "windows", host_python=host_python())
            before = self.snapshot()
            states = configuration.configure_aliases(self.root, "windows", host_python=host_python())
            self.assertEqual(set(states.values()), {"already correct"})
            self.assertEqual(before, self.snapshot())

    def test_alias_check_with_missing_payload_has_zero_writes(self):
        before = self.snapshot()
        states = configuration.configure_aliases(self.root, "windows", host_python=host_python(), check=True)
        self.assertEqual(set(states.values()), {"missing"})
        self.assertEqual(before, self.snapshot())


class HostRuntimePolicy(unittest.TestCase):
    def test_current_standalone_supported_python_is_admitted(self):
        with patch.object(host_runtime.sys, "version_info", (3, 12, 10)), \
                patch.object(host_runtime.sys, "maxsize", 2**63 - 1), \
                patch.object(host_runtime.sys, "prefix", "standalone"), \
                patch.object(host_runtime.sys, "base_prefix", "standalone"):
            self.assertTrue(Path(host_runtime.require_current_host()).is_absolute())

    def test_launcher_rejects_virtualenv_runtime_even_when_mcp_healthy(self):
        with patch.object(host_runtime.sys, "prefix", "managed MCP environment"), \
                patch.object(host_runtime.sys, "base_prefix", "standalone"), \
                self.assertRaisesRegex(configuration.ConfigurationError, "repair local aliases"):
            host_runtime.require_current_host()

    def test_launcher_rejects_wrong_host_version_and_architecture(self):
        for version, bits in (((3, 14, 0), 2**63 - 1), ((3, 12, 10), 2**31 - 1)):
            with self.subTest(version=version, bits=bits), \
                    patch.object(host_runtime.sys, "version_info", version), \
                    patch.object(host_runtime.sys, "maxsize", bits), \
                    self.assertRaisesRegex(configuration.ConfigurationError, "Python 3.12 x64"):
                host_runtime.require_current_host()

    def test_validated_alias_host_is_standalone_and_outside_payload(self):
        root = SOURCE
        data = {"prefix": "standalone", "base_prefix": "standalone", "executable": host_python()}
        with patch.object(host_runtime, "find_python", return_value=host_python()) as selection, \
                patch.object(host_runtime, "probe", return_value=data):
            self.assertEqual(host_runtime.validated_host(root, "windows"), host_python())
            selection.assert_called_once()

    def test_validated_host_rejects_managed_payload_path_and_nonstandalone_prefix(self):
        for executable, prefix, base in ((str(environment.python_path(SOURCE, "windows")), "same", "same"),
                                         (host_python(), "venv", "standalone")):
            with self.subTest(executable=executable, prefix=prefix), \
                    patch.object(host_runtime, "find_python", return_value=executable), \
                    patch.object(host_runtime, "probe", return_value={"prefix": prefix, "base_prefix": base,
                                                                     "executable": executable}), \
                    self.assertRaisesRegex(configuration.ConfigurationError, "operator runtime|standalone"):
                host_runtime.validated_host(SOURCE, "windows")


class HostEnvironmentLifecycle(DisposableCheckout):
    def response(self, stdout="", returncode=0):
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    def create_payload(self):
        executable = environment.python_path(self.root, "windows")
        response = subprocess.run([host_python(), "-I", "-B", "-m", "venv", "--without-pip",
                                   str(executable.parents[1])], capture_output=True, text=True, check=False)
        self.assertEqual(response.returncode, 0, response.stderr)
        return executable

    def data(self, packages):
        executable = environment.python_path(self.root, "windows")
        return {"version": [3, 12, 10], "bits": 64, "prefix": str(executable.parents[1]),
                "base_prefix": str(Path(host_python()).parent), "executable": str(executable),
                "base_executable": host_python(), "packages": packages}

    def test_first_creation_uses_host_then_healthy_rerun_reuses_payload(self):
        calls, installed = [], False
        def runner(command):
            nonlocal installed
            calls.append(command)
            if "venv" in command:
                self.assertEqual(command[0], host_python())
                self.create_payload()
            if "install" in command:
                self.assertEqual(command[0], str(environment.python_path(self.root, "windows")))
                installed = True
            if command[-1] == environment.PROBE:
                return self.response(json.dumps(self.data(environment.pins(self.root, "windows") if installed else {})))
            return self.response()
        with patch.object(environment, "find_python", return_value=host_python()):
            initial = environment.ensure_environment(self.root, "windows", runner=runner)
            self.assertEqual(initial["state"], "created")
            self.assertTrue(initial["ready"])
            before = self.snapshot()
            repeated = environment.ensure_environment(self.root, "windows", runner=runner)
            self.assertEqual(repeated["state"], "already correct")
            self.assertEqual(before, self.snapshot())
        self.assertEqual(sum("venv" in command for command in calls), 1)
        self.assertEqual(sum("install" in command for command in calls), 1)

    def test_inactive_unhealthy_payload_repairs_once_without_recreation(self):
        self.create_payload()
        calls, installed = [], False
        def runner(command):
            nonlocal installed
            calls.append(command)
            if "venv" in command:
                self.fail("Existing payload must not be recreated for dependency repair")
            if "install" in command:
                installed = True
            if command[-1] == environment.PROBE:
                return self.response(json.dumps(self.data(environment.pins(self.root, "windows") if installed else {})))
            return self.response()
        with patch.object(environment, "inspect_environment_use", return_value={"state": "free", "blockers": [], "ambiguities": []}):
            updated = environment.ensure_environment(self.root, "windows", runner=runner)
        self.assertTrue(updated["ready"])
        self.assertEqual(updated["state"], "repaired/updated")
        self.assertEqual(sum("install" in command for command in calls), 1)

    def test_setup_entrypoint_without_compatible_host_exits_without_mutation(self):
        caller = str(self.root / "Python314/python.exe")
        launcher = str(self.root / "py.exe")
        python32 = str(self.root / "Python312-32/python.exe")
        virtualenv = str(self.root / "other-venv/Scripts/python.exe")
        candidates = {
            caller: {"version": [3, 14, 0], "bits": 64, "prefix": "host", "base_prefix": "host"},
            python32: {"version": [3, 12, 10], "bits": 32, "prefix": "host", "base_prefix": "host"},
            virtualenv: {"version": [3, 12, 10], "bits": 64, "prefix": "venv", "base_prefix": "host"},
        }
        calls = []
        def read_only_process(command, **kwargs):
            calls.append(command)
            if command == ["git", "-C", str(self.root), "rev-parse", "--show-toplevel"]:
                return self.response(str(self.root))
            if command == [launcher, "-3.12", "-I", "-B", "-c", "import sys; print(sys.executable)"]:
                return self.response(python32)
            if command[0] in candidates and command[1:] == ["-I", "-B", "-c", environment.PROBE]:
                return self.response(json.dumps(candidates[command[0]]))
            self.fail("Host-selection failure attempted a non-read-only command: " + repr(command))

        before = self.snapshot()
        directories = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.is_dir())
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(bootstrap, "__file__", str(self.root / "tools/lunitora_machine/bootstrap.py")), \
                patch.object(bootstrap, "platform_name", return_value="windows"), \
                patch.object(environment.sys, "executable", caller), \
                patch.object(environment.sys, "_base_executable", caller), \
                patch.object(environment.shutil, "which", side_effect={
                    "py": launcher, "python3.12": virtualenv, "python": caller}.get), \
                patch.dict(os.environ, {"LOCALAPPDATA": ""}), \
                patch.object(subprocess, "run", side_effect=read_only_process), \
                patch.object(bootstrap, "ensure_environment") as payload_setup, \
                patch.object(bootstrap, "configure_aliases") as alias_setup, \
                patch.object(bootstrap, "bootstrap") as provisioning, \
                patch.object(sys, "argv", ["lunitora_setup.py"]), \
                patch.object(sys, "path", list(sys.path)), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(self.root / "tools/lunitora_setup.py"), run_name="__main__")
            self.assertEqual(exit_result.exception.code, 1)
            payload_setup.assert_not_called()
            alias_setup.assert_not_called()
            provisioning.assert_not_called()

        output = stdout.getvalue() + stderr.getvalue()
        self.assertIn("Install Python 3.12 x64 alongside your current Python", stderr.getvalue())
        self.assertIn("then rerun python tools/lunitora_setup.py", stderr.getvalue())
        self.assertIn("Python is never downloaded by setup", stderr.getvalue())
        self.assertNotIn("Traceback", output)
        self.assertEqual({command[0] for command in calls if command[-1] == environment.PROBE}, set(candidates))
        self.assertEqual(before, self.snapshot())  # Includes repository Git configuration/aliases.
        self.assertEqual(directories, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.is_dir()))
        self.assertFalse((self.root / "tools/lunitora_mcp/.venv").exists())
        self.assertFalse(configuration.local_path(self.root).exists())

    def test_actual_fresh_doctor_executes_isolated_host_and_never_creates_payload(self):
        before = self.snapshot()
        response = subprocess.run([host_python(), "-I", "-S", "-B", str(self.root / "tools/lunitora_setup.py"), "--check"],
                                  cwd=self.root, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(response.returncode, 1)
        self.assertNotIn("ModuleNotFoundError", response.stderr)
        self.assertNotIn("Traceback", response.stderr)
        self.assertIn("Capability readiness", response.stdout)
        self.assertIn("Python environment: missing", response.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "tools/lunitora_mcp/.venv").exists())

    def test_actual_venv_caller_hands_off_doctor_to_host_not_payload(self):
        executable = self.create_payload()
        before = self.snapshot()
        response = subprocess.run([str(executable), "-B", str(self.root / "tools/lunitora_setup.py"), "--check"],
                                  cwd=self.root, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(response.returncode, 1)
        self.assertNotIn("ModuleNotFoundError", response.stderr)
        self.assertNotIn("Traceback", response.stderr)
        self.assertNotIn("Setup worker must", response.stderr)
        self.assertIn("Capability readiness", response.stdout)
        self.assertEqual(before, self.snapshot())

    def test_actual_python314_caller_hands_off_doctor_to_supported_host(self):
        caller = shutil.which("python")
        if not caller:
            self.skipTest("No separate machine Python entrypoint available")
        probe = subprocess.run([caller, "-I", "-B", "-c", "import json,sys; print(json.dumps(list(sys.version_info[:2])))"],
                               capture_output=True, text=True, timeout=30, check=False)
        if probe.returncode or json.loads(probe.stdout) != [3, 14]:
            self.skipTest("Optional Python 3.14 caller is not installed")
        before = self.snapshot()
        response = subprocess.run([caller, "-I", "-S", "-B", str(self.root / "tools/lunitora_setup.py"), "--check"],
                                  cwd=self.root, capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(response.returncode, 1)
        self.assertNotIn("ModuleNotFoundError", response.stderr)
        self.assertNotIn("Traceback", response.stderr)
        self.assertNotIn("Setup worker must", response.stderr)
        self.assertIn("Capability readiness", response.stdout)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
