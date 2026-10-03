"""Host-driven venv lifecycle admission; no real dependencies or apps changed."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import environment, environment_recovery, environment_usage


class HostEnvironmentLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lunitora host environment spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.host = r"C:\Host Python Space\Python312\python.exe"
        self.python = environment.python_path(self.root, "windows")
        self.calls = []
        self.installed = False
        self.free = {"state": "free", "blockers": [], "ambiguities": []}
        self.usage = {"state": "in_use", "blockers": [{"role": "Godot MCP server", "pid": 812,
                       "created": 100, "executable": str(self.python)}], "ambiguities": []}
        self.lock = self.root / "tools/lunitora_mcp/requirements.lock"
        self.lock.write_text("mcp==2.2.0\n", encoding="ascii")

    def prepare(self):
        self.python.parent.mkdir(parents=True, exist_ok=True)
        self.python.write_bytes(b"DISPOSABLE-NONEXECUTABLE-FIXTURE")
        (self.python.parents[1] / "pyvenv.cfg").write_text(
            "include-system-site-packages = false\nexecutable = " + self.host + "\n", encoding="utf-8")

    def inspect(self, *args, **kwargs):
        if not self.python.parents[1].exists():
            return {"ready": False, "state": "missing", "reason": "repository Python environment missing"}
        return {"ready": self.installed, "state": "already correct" if self.installed else "dependency update available",
                "reason": "pinned packages verified" if self.installed else "pinned packages need repair",
                "data": {"base_executable": self.host}, "base_executable": self.host,
                "python": str(self.python)}

    def runner(self, command, **kwargs):
        self.calls.append(command)
        if "venv" in command:
            self.prepare()
        if "install" in command:
            self.installed = True
        payload = {"version": [3, 12, 10], "bits": 64, "prefix": r"C:\Host Python Space\Python312",
                   "base_prefix": r"C:\Host Python Space\Python312", "executable": self.host,
                   "base_executable": self.host, "packages": {}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    def run_setup(self, *, usage=None, recovery=None, check=False, interactive=False):
        emitted, prompts = [], []
        def prompt(question):
            prompts.append(question)
            return "y"
        with patch.object(environment, "inspect_environment", side_effect=self.inspect), \
                patch.object(environment, "inspect_environment_use", side_effect=usage or [self.free]) as inspect_use, \
                patch.object(environment_recovery, "recover_mcp_blockers", return_value=recovery or {
                    "recovered": False, "state": "deferred", "reason": "recovery declined"}) as recover:
            result = environment.ensure_environment(
                self.root, "windows", runner=self.runner, host_python=self.host,
                check=check, interactive=interactive, prompt=prompt, emit=emitted.append)
        return result, inspect_use, recover, emitted

    def test_completely_absent_venv_is_created_using_host_then_pinned_once(self):
        result, usage, recover, emitted = self.run_setup()
        self.assertTrue(result["ready"])
        self.assertEqual(result["state"], "created")
        creation = [command for command in self.calls if "venv" in command]
        installs = [command for command in self.calls if "install" in command]
        self.assertEqual(len(creation), 1)
        self.assertEqual(creation[0][0], self.host)
        self.assertEqual(creation[0][-1], str(self.python.parents[1]))
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0][0], str(self.python))
        self.assertEqual(installs[0][-1], str(self.lock))
        recover.assert_not_called()

    def test_healthy_environment_is_reused_without_use_probe_or_install(self):
        self.prepare()
        self.installed = True
        result, usage, recover, emitted = self.run_setup()
        self.assertTrue(result["ready"])
        self.assertEqual(self.calls, [])
        usage.assert_not_called()
        recover.assert_not_called()

    def test_created_environment_rerun_is_idempotent(self):
        first, _, _, _ = self.run_setup()
        self.assertTrue(first["ready"])
        before = len(self.calls)
        second, usage, recover, _ = self.run_setup()
        self.assertTrue(second["ready"])
        self.assertEqual(len(self.calls), before)
        usage.assert_not_called()
        recover.assert_not_called()

    def test_unhealthy_unused_environment_is_repaired_without_recreation(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup()
        self.assertEqual(result["state"], "repaired/updated")
        self.assertFalse(any("venv" in command for command in self.calls))
        self.assertEqual(sum("install" in command for command in self.calls), 1)
        usage.assert_called_once()
        recover.assert_not_called()

    def test_accepted_recovery_requires_second_free_proof_before_pip(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(
            usage=[self.usage, self.free], recovery={"recovered": True, "state": "exited",
                                                   "reason": "verified process exit proven"}, interactive=True)
        self.assertEqual(result["state"], "repaired/updated")
        self.assertEqual(usage.call_count, 2)
        recover.assert_called_once()
        self.assertEqual(sum("install" in command for command in self.calls), 1)

    def test_new_blocker_after_recovery_prevents_dependency_mutation(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(
            usage=[self.usage, self.usage], recovery={"recovered": True, "state": "exited",
                                                    "reason": "verified process exit proven"}, interactive=True)
        self.assertFalse(result["ready"])
        self.assertTrue(result["deferred"])
        self.assertEqual(usage.call_count, 2)
        self.assertEqual(self.calls, [])
        recover.assert_called_once()

    def test_ambiguous_second_proof_prevents_dependency_mutation(self):
        self.prepare()
        uncertain = {"state": "ambiguous", "blockers": [],
                     "ambiguities": [{"reason": "process provenance changed"}]}
        result, usage, recover, emitted = self.run_setup(
            usage=[self.usage, uncertain], recovery={"recovered": True, "state": "exited",
                                                    "reason": "verified process exit proven"}, interactive=True)
        self.assertTrue(result["deferred"])
        self.assertEqual(result["usage"]["state"], "ambiguous")
        self.assertEqual(self.calls, [])
        recover.assert_called_once()

    def test_declined_recovery_never_runs_pip(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(usage=[self.usage], interactive=True)
        self.assertTrue(result["deferred"])
        self.assertEqual(self.calls, [])
        recover.assert_called_once()

    def test_ambiguous_recovery_drops_stale_identities_and_never_runs_pip(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(
            usage=[self.usage], interactive=True,
            recovery={"recovered": False, "state": "ambiguous",
                      "reason": "environment-use state ambiguous; no update is safe"})
        self.assertTrue(result["deferred"])
        self.assertEqual(result["usage"]["state"], "ambiguous")
        self.assertEqual(result["usage"]["blockers"], [])
        self.assertEqual(self.calls, [])
        recover.assert_called_once()

    def test_ambiguous_initial_use_never_invokes_recovery(self):
        self.prepare()
        uncertain = {"state": "ambiguous", "blockers": [],
                     "ambiguities": [{"reason": "process identity unavailable or changed"}]}
        result, usage, recover, emitted = self.run_setup(usage=[uncertain], interactive=True)
        self.assertTrue(result["deferred"])
        self.assertEqual(self.calls, [])
        recover.assert_not_called()

    def test_noninteractive_active_environment_never_invokes_recovery(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(usage=[self.usage])
        self.assertTrue(result["deferred"])
        self.assertEqual(self.calls, [])
        recover.assert_not_called()

    def test_check_on_missing_environment_has_zero_writes_or_recovery(self):
        before = {str(path.relative_to(self.root)): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        result, usage, recover, emitted = self.run_setup(check=True, interactive=True)
        self.assertFalse(result["ready"])
        self.assertEqual(self.calls, [])
        usage.assert_not_called()
        recover.assert_not_called()
        self.assertEqual(before, {str(path.relative_to(self.root)): path.read_bytes()
                                 for path in self.root.rglob("*") if path.is_file()})

    def test_check_on_unhealthy_environment_never_requests_recovery(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup(check=True, interactive=True)
        self.assertFalse(result["ready"])
        self.assertEqual(self.calls, [])
        usage.assert_not_called()
        recover.assert_not_called()

    def test_failed_install_has_one_attempt_only_after_free_proof(self):
        self.prepare()
        calls = []
        def failed(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=1, stdout="", stderr="SECRET-PIP-DETAIL")
        with patch.object(environment, "inspect_environment", side_effect=self.inspect), \
                patch.object(environment, "inspect_environment_use", return_value=self.free):
            with self.assertRaisesRegex(environment.ConfigurationError, "Pinned dependency installation failed"):
                environment.ensure_environment(self.root, "windows", runner=failed, host_python=self.host)
        self.assertEqual(sum("install" in command for command in calls), 1)

    def test_inactive_repair_probe_receives_host_and_exact_base(self):
        self.prepare()
        result, usage, recover, emitted = self.run_setup()
        self.assertTrue(result["ready"])
        self.assertEqual(usage.call_args.kwargs["host_python"], self.host)
        self.assertEqual(usage.call_args.kwargs["base_executable"], self.host)

    def test_broken_interpreter_is_repairable_only_with_valid_base_metadata(self):
        self.prepare()
        cfg = self.python.parents[1] / "pyvenv.cfg"
        cfg.write_text("include-system-site-packages = false\nversion = 3.12.10\nexecutable = " + self.host + "\n", encoding="utf-8")
        metadata = {"prefix": "C:\\Host Python Space", "base_prefix": "C:\\Host Python Space"}
        with patch.object(environment, "probe", side_effect=lambda executable, runner: metadata if executable == self.host else None):
            state = environment.inspect_environment(self.root, "windows", runner=self.runner)
        self.assertFalse(state["ready"])
        self.assertTrue(state["rebuild"])
        self.assertEqual(state["base_executable"], self.host)
        self.assertEqual(self.calls, [])

    def test_broken_interpreter_without_compatible_base_is_not_overwritten(self):
        self.prepare()
        before = self.python.read_bytes()
        with patch.object(environment, "probe", return_value=None):
            with self.assertRaises(environment.ConfigurationError):
                environment.ensure_environment(self.root, "windows", host_python=self.host, runner=self.runner)
        self.assertEqual(self.python.read_bytes(), before)
        self.assertEqual(self.calls, [])

    def test_verified_broken_interpreter_rebuild_occurs_once_after_free_proof(self):
        self.prepare()
        broken = dict(self.inspect(), rebuild=True)
        healthy = dict(broken, ready=True, rebuild=False)
        with patch.object(environment, "inspect_environment", side_effect=[broken, broken, healthy]), \
                patch.object(environment, "inspect_environment_use", return_value=self.free) as usage:
            state = environment.ensure_environment(self.root, "windows", host_python=self.host, runner=self.runner)
        self.assertEqual(state["state"], "repaired/updated")
        usage.assert_called_once()
        self.assertEqual(sum("venv" in command for command in self.calls), 1)
        self.assertEqual(sum("install" in command for command in self.calls), 1)
        self.assertEqual(self.calls[0][0], self.host)

    def test_active_broken_interpreter_is_not_rebuilt_or_installed(self):
        self.prepare()
        broken = dict(self.inspect(), rebuild=True)
        with patch.object(environment, "inspect_environment", return_value=broken), \
                patch.object(environment, "inspect_environment_use", return_value=self.usage):
            state = environment.ensure_environment(self.root, "windows", host_python=self.host, runner=self.runner)
        self.assertTrue(state["deferred"])
        self.assertEqual(self.calls, [])


class HostEnvironmentUseProbeTests(unittest.TestCase):
    def test_broken_or_absent_venv_use_probe_executes_only_validated_host_python(self):
        root = Path(r"C:\Missing Venv\Checkout With Spaces")
        host = r"C:\Host Python Space\Python312\python.exe"
        target_base = r"C:\MCP Python Base\python.exe"
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "state": "free", "blockers": [], "ambiguities": []}), stderr="")
        with patch.object(environment_usage, "current_creation_time", return_value=100):
            result = environment.inspect_environment_use(root, "windows", runner=runner,
                                                         host_python=host, base_executable=target_base)
        self.assertEqual(result["state"], "free")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], host)
        self.assertEqual(calls[0][1:5], ["-I", "-S", "-B", "-c"])
        self.assertNotIn(str(environment.python_path(root, "windows")), calls[0])
        self.assertIn(repr(target_base), calls[0][5])
        self.assertIn(repr(str(root.absolute())), calls[0][5])

    def test_failed_host_probe_reports_ambiguity_without_echoing_streams(self):
        sentinel = "HOST-PROBE-SECRET-NOT-FOR-OUTPUT"
        with patch.object(environment_usage, "current_creation_time", return_value=100):
            result = environment.inspect_environment_use(
                Path(r"C:\Missing Venv"), "windows", host_python=r"C:\Python312\python.exe",
                runner=lambda _: SimpleNamespace(returncode=1, stdout=sentinel, stderr=sentinel))
        self.assertEqual(result["state"], "ambiguous")
        self.assertEqual(result["blockers"], [])
        self.assertNotIn(sentinel, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
