"""Pure process-admission fixtures; never launch or control installed applications."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import venv

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import environment, environment_usage


class EnvironmentUsageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(r"C:\Work Trees\Totolina Merge")
        self.venv = str(self.root / "tools/lunitora_mcp/.venv/Scripts/python.exe")
        self.base = r"C:\Python312\python.exe"
        self.setup = str(self.root / "tools/lunitora_setup.py")
        self.current_pid = 500
        self.probe_pid = 501
        self.current = self.row(self.current_pid, self.base, created=100,
                                argv=[self.base, "-B", self.setup])
        self.probe = self.row(self.probe_pid, self.venv, parent=self.current_pid,
                              created=200, argv=[self.venv, "-I", "-B", "-c",
                                                 "pass", "--lunitora-environment-probe"])

    def row(self, pid, executable=None, *, parent=1, created=300, argv=None,
            alive=True, identity_ok=True):
        executable = executable or self.base
        return {"pid": pid, "parent_pid": parent, "created": created,
                "executable": executable, "argv": argv,
                "alive": alive, "identity_ok": identity_ok}

    def classify(self, rows=(), *, expected_created=None, include_context=True):
        context = [self.current, self.probe] if include_context else []
        return environment_usage.classify_processes(
            self.root, deepcopy([*context, *rows]), current_pid=self.current_pid,
            probe_pid=self.probe_pid, base_executable=self.base,
            expected_created=expected_created or {self.current_pid: 100, self.probe_pid: 200})

    def assertFree(self, state):
        self.assertEqual(state["state"], "free")
        self.assertEqual(state["blockers"], [])
        self.assertEqual(state["ambiguities"], [])

    def assertBlocked(self, state, pid, role=None):
        self.assertEqual(state["state"], "in_use")
        blockers = {blocker["pid"]: blocker for blocker in state["blockers"]}
        self.assertIn(pid, blockers)
        self.assertEqual(set(blockers[pid]), {"pid", "role", "executable", "created"})
        if role:
            self.assertEqual(blockers[pid]["role"], role)

    def assertAmbiguous(self, state):
        self.assertEqual(state["state"], "ambiguous")
        self.assertTrue(state["ambiguities"])

    def test_no_desktop_godot_or_mcp_environment_is_free(self):
        self.assertFree(self.classify())

    def test_setup_itself_using_venv_is_not_a_blocker(self):
        self.current["executable"] = self.venv
        self.current["argv"][0] = self.venv
        self.assertFree(self.classify())

    def test_probe_itself_using_venv_is_not_a_blocker(self):
        self.assertFree(self.classify())

    def test_probe_redirector_with_same_forwarded_arguments_is_exempt(self):
        parent = self.row(550, self.venv, parent=self.current_pid, created=150,
                         argv=list(self.probe["argv"]))
        self.probe["parent_pid"] = 550
        self.probe["executable"] = self.base
        self.probe["argv"][0] = self.base
        self.assertFree(self.classify([parent]))

    def test_probe_redirector_with_different_arguments_is_not_exempt(self):
        parent = self.row(551, self.venv, parent=self.current_pid, created=150,
                         argv=[self.venv, "-B", "unknown.py"])
        self.probe["parent_pid"] = 551
        self.probe["executable"] = self.base
        self.probe["argv"][0] = self.base
        self.assertBlocked(self.classify([parent]), 551)

    def test_probe_marker_on_an_unrelated_process_does_not_exempt_it(self):
        process = self.row(552, self.venv, argv=[self.venv, "-I", "-B", "-c",
                                               "pass", "--lunitora-environment-probe"])
        self.assertBlocked(self.classify([process]), 552)

    def test_direct_venv_godot_mcp_is_blocker_with_accurate_role(self):
        process = self.row(600, self.venv, argv=[self.venv, "-B", "-m", "core.godot_server"])
        self.assertBlocked(self.classify([process]), 600, "Godot MCP server")

    def test_direct_venv_photoshop_mcp_is_blocker_with_accurate_role(self):
        process = self.row(601, self.venv, argv=[self.venv, "-B", "-m", "core.server"])
        self.assertBlocked(self.classify([process]), 601, "Photoshop MCP server")

    def test_unknown_live_venv_python_is_still_blocker(self):
        process = self.row(602, self.venv, argv=[self.venv, "-B", "custom_tool.py"])
        self.assertBlocked(self.classify([process]), 602)

    def test_unreadable_venv_arguments_do_not_weaken_detection(self):
        self.assertBlocked(self.classify([self.row(603, self.venv)]), 603)

    def test_multiple_mcp_blockers_are_all_reported(self):
        processes = [self.row(600, self.venv, argv=[self.venv, "-B", "-m", "core.godot_server"]),
                     self.row(601, self.venv, argv=[self.venv, "-B", "-m", "core.server"])]
        state = self.classify(processes)
        self.assertEqual(state["state"], "in_use")
        self.assertEqual({item["pid"] for item in state["blockers"]}, {600, 601})

    def test_exited_mcp_snapshot_is_not_an_active_blocker(self):
        process = self.row(604, self.venv, alive=False,
                           argv=[self.venv, "-B", "-m", "core.godot_server"])
        self.assertFree(self.classify([process]))

    def test_stale_pid_without_live_process_is_not_active(self):
        self.assertFree(self.classify([self.row(605, self.venv, alive=False, identity_ok=False)]))

    def test_unrelated_base_python_is_ignored(self):
        process = self.row(606, self.base, argv=[self.base, "-B", "other_project.py"])
        self.assertFree(self.classify([process]))

    def test_unrelated_other_python_is_ignored(self):
        executable = r"D:\Other Python\python.exe"
        process = self.row(607, executable, argv=[executable, "-B", "other_project.py"])
        self.assertFree(self.classify([process]))

    def test_repository_path_in_unrelated_arguments_is_not_venv_use(self):
        process = self.row(608, self.base,
                           argv=[self.base, "-B", "backup.py", "--directory", str(self.root)])
        self.assertFree(self.classify([process]))

    def test_venv_path_as_data_argument_is_not_venv_use(self):
        process = self.row(609, self.base,
                           argv=[self.base, "-B", "hash_file.py", "--input", self.venv])
        self.assertFree(self.classify([process]))

    def test_other_checkout_venv_is_not_this_environment(self):
        executable = r"C:\Other Checkout\tools\lunitora_mcp\.venv\Scripts\python.exe"
        process = self.row(610, executable, argv=[executable, "-B", "-m", "core.godot_server"])
        self.assertFree(self.classify([process]))

    def test_proven_other_checkout_redirected_mcp_is_ignored(self):
        executable = r"C:\Other Checkout\tools\lunitora_mcp\.venv\Scripts\python.exe"
        parent = self.row(559, executable, created=300,
                         argv=[executable, "-B", "-m", "core.godot_server"])
        child = self.row(560, self.base, parent=559, created=400,
                        argv=[executable, "-B", "-m", "core.godot_server"])
        self.assertFree(self.classify([parent, child]))

    def test_other_checkout_redirector_child_can_name_base_interpreter(self):
        executable = r"C:\Other Checkout\tools\lunitora_mcp\.venv\Scripts\python.exe"
        parent = self.row(559, executable, created=300,
                         argv=[executable, "-B", "-m", "core.godot_server"])
        child = self.row(560, self.base, parent=559, created=400,
                        argv=[self.base, "-B", "-m", "core.godot_server"])
        self.assertFree(self.classify([parent, child]))

    def test_reused_other_checkout_parent_does_not_prove_mcp_environment(self):
        executable = r"C:\Other Checkout\tools\lunitora_mcp\.venv\Scripts\python.exe"
        parent = self.row(561, executable, created=500,
                         argv=[executable, "-B", "-m", "core.godot_server"])
        child = self.row(562, self.base, parent=561, created=400,
                        argv=[executable, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([parent, child]))

    def test_neighbor_venv_prefix_is_not_this_environment(self):
        executable = self.venv.replace(".venv", ".venv-other")
        process = self.row(611, executable, argv=[executable, "-B", "tool.py"])
        self.assertFree(self.classify([process]))

    def test_pythonw_in_repository_venv_remains_a_blocker(self):
        executable = self.venv.replace("python.exe", "pythonw.exe")
        process = self.row(553, executable, argv=[executable, "-B", "tool.py"])
        self.assertBlocked(self.classify([process]), 553)

    def test_non_python_executable_under_venv_is_not_python_use(self):
        executable = self.venv.replace("python.exe", "some_application.exe")
        process = self.row(554, executable, argv=[executable])
        self.assertFree(self.classify([process]))

    def test_base_interpreter_with_venv_argv_zero_is_blocked(self):
        process = self.row(612, self.base, argv=[self.venv, "-B", "-m", "core.godot_server"])
        self.assertBlocked(self.classify([process]), 612, "Godot MCP server")

    def test_live_venv_parent_proves_redirected_base_mcp_child(self):
        parent = self.row(613, self.venv, created=300,
                         argv=[self.venv, "-B", "-m", "core.godot_server"])
        child = self.row(614, self.base, parent=613, created=400,
                        argv=[self.base, "-B", "-m", "core.godot_server"])
        state = self.classify([parent, child])
        self.assertBlocked(state, 613, "Godot MCP server")
        self.assertBlocked(state, 614, "Godot MCP server")

    def test_orphan_base_mcp_without_venv_provenance_is_explicitly_ambiguous(self):
        process = self.row(615, self.base, argv=[self.base, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([process]))

    def test_exited_venv_parent_does_not_prove_live_base_mcp_child(self):
        parent = self.row(616, self.venv, created=300, alive=False,
                         argv=[self.venv, "-B", "-m", "core.godot_server"])
        child = self.row(617, self.base, parent=616, created=400,
                        argv=[self.base, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([parent, child]))

    def test_exited_descendant_with_unrelated_live_python_is_ignored(self):
        exited = self.row(618, self.venv, alive=False,
                          argv=[self.venv, "-B", "-m", "core.godot_server"])
        unrelated = self.row(619, self.base, argv=[self.base, "-B", "other.py"])
        self.assertFree(self.classify([exited, unrelated]))

    def test_mismatched_live_venv_process_identity_is_ambiguous(self):
        process = self.row(620, self.venv, identity_ok=False,
                           argv=[self.venv, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([process]))

    def test_reused_parent_pid_cannot_prove_mcp_provenance(self):
        parent = self.row(621, self.venv, created=500,
                         argv=[self.venv, "-B", "-m", "core.godot_server"])
        child = self.row(622, self.base, parent=621, created=400,
                        argv=[self.base, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([parent, child]))

    def test_missing_creation_time_on_relevant_process_is_ambiguous(self):
        process = self.row(623, self.venv, created=None,
                           argv=[self.venv, "-B", "-m", "core.godot_server"])
        self.assertAmbiguous(self.classify([process]))

    def test_current_pid_reuse_is_never_exempted(self):
        self.current["created"] = 101
        self.assertAmbiguous(self.classify())

    def test_probe_pid_reuse_is_never_exempted(self):
        self.probe["created"] = 201
        self.assertAmbiguous(self.classify())

    def test_verified_setup_parent_is_exempt_from_venv_usage(self):
        parent = self.row(624, self.venv, created=50, argv=[self.venv, "-B", self.setup])
        self.current["parent_pid"] = 624
        self.assertFree(self.classify([parent]))

    def test_setup_parent_created_after_child_is_not_exempted(self):
        parent = self.row(625, self.venv, created=150, argv=[self.venv, "-B", self.setup])
        self.current["parent_pid"] = 625
        self.assertAmbiguous(self.classify([parent]))

    def test_unrelated_venv_python_parent_is_not_exempted(self):
        parent = self.row(626, self.venv, created=50, argv=[self.venv, "-B", "user_script.py"])
        self.current["parent_pid"] = 626
        self.assertBlocked(self.classify([parent]), 626)

    def test_setup_path_as_data_does_not_exempt_venv_parent(self):
        parent = self.row(555, self.venv, created=50,
                         argv=[self.venv, "-B", "hash_file.py", self.setup])
        self.current["parent_pid"] = 555
        self.assertBlocked(self.classify([parent]), 555)

    def test_setup_path_in_inline_code_does_not_exempt_venv_parent(self):
        parent = self.row(556, self.venv, created=50,
                         argv=[self.venv, "-B", "-c", "print('setup')", self.setup])
        self.current["parent_pid"] = 556
        self.assertBlocked(self.classify([parent]), 556)

    def test_wrong_repository_setup_parent_is_not_exempted(self):
        parent = self.row(557, self.venv, created=50,
                         argv=[self.venv, "-B", r"C:\Other Checkout\tools\lunitora_setup.py"])
        self.current["parent_pid"] = 557
        self.assertBlocked(self.classify([parent]), 557)

    def test_unverified_setup_ancestor_is_explicitly_ambiguous(self):
        parent = self.row(558, self.venv, created=50, identity_ok=False,
                         argv=[self.venv, "-B", self.setup])
        self.current["parent_pid"] = 558
        self.assertAmbiguous(self.classify([parent]))

    def test_other_setup_process_is_not_blanket_exempted(self):
        process = self.row(627, self.venv, argv=[self.venv, "-B", self.setup])
        self.assertBlocked(self.classify([process]), 627)

    def test_inherited_handle_parent_alone_is_not_a_blocker(self):
        parent = self.row(628, self.base, created=50, argv=[self.base, "-B", "shell_wrapper.py"])
        self.current["parent_pid"] = 628
        self.assertFree(self.classify([parent]))

    def test_readonly_classification_does_not_change_raw_rows(self):
        rows = [self.current, self.probe, self.row(629, self.venv)]
        original = deepcopy(rows)
        environment_usage.classify_processes(self.root, rows, current_pid=self.current_pid,
                                              probe_pid=self.probe_pid, base_executable=self.base,
                                              expected_created={self.current_pid: 100, self.probe_pid: 200})
        self.assertEqual(rows, original)

    def test_diagnostics_do_not_include_arbitrary_command_arguments(self):
        sentinel = "SECRET-ARGUMENT-NOT-FOR-OUTPUT"
        process = self.row(630, self.venv,
                           argv=[self.venv, "-B", "-m", "core.godot_server", "--token", sentinel])
        state = self.classify([process])
        self.assertBlocked(state, 630)
        self.assertNotIn(sentinel, json.dumps(state))
        self.assertNotIn("--token", json.dumps(state))

    def test_paths_with_spaces_and_case_preserve_executable_diagnostics(self):
        executable = self.venv.upper()
        process = self.row(631, executable, argv=[executable, "-B", "-m", "core.godot_server"])
        state = self.classify([process])
        self.assertBlocked(state, 631, "Godot MCP server")
        self.assertEqual(state["blockers"][0]["executable"], executable)


class EnvironmentUsageDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(r"C:\Work Trees\Totolina Merge")
        self.executable = str(self.root / "tools/lunitora_mcp/.venv/Scripts/python.exe")

    def probe(self, payload, *, code=0, stderr=""):
        with patch.object(environment_usage, "current_creation_time", return_value=100):
            return environment.inspect_environment_use(
                self.root, "windows", runner=lambda _: SimpleNamespace(
                    returncode=code, stdout=payload, stderr=stderr))

    def test_valid_report_prints_exact_roles_pids_and_executables(self):
        report = {"state": "in_use", "blockers": [
            {"role": "Godot MCP server", "pid": 12345, "executable": self.executable, "created": 100},
            {"role": "Photoshop MCP server", "pid": 12346, "executable": self.executable, "created": 200}],
            "ambiguities": []}
        verified = self.probe(json.dumps(report))
        self.assertEqual(verified, report)
        output = "\n".join(environment.format_usage(verified))
        self.assertIn("Repository Python environment is currently in use.", output)
        self.assertIn("role: Godot MCP server", output)
        self.assertIn("role: Photoshop MCP server", output)
        self.assertIn("pid: 12345", output)
        self.assertIn("pid: 12346", output)
        self.assertIn("executable: " + self.executable, output)
        self.assertIn("python tools/lunitora_setup.py", output)

    def test_extra_arbitrary_arguments_in_probe_report_are_rejected_without_echo(self):
        sentinel = "PROBE-SECRET-ARGUMENT-NOT-FOR-OUTPUT"
        report = {"state": "in_use", "blockers": [
            {"role": "Godot MCP server", "pid": 12345, "executable": self.executable,
             "argv": ["--token", sentinel]}], "ambiguities": []}
        verified = self.probe(json.dumps(report))
        self.assertEqual(verified["state"], "ambiguous")
        output = "\n".join(environment.format_usage(verified))
        self.assertIn("environment-use state ambiguous", output)
        self.assertNotIn(sentinel, output)
        self.assertNotIn("--token", output)

    def test_failed_probe_never_echoes_stdout_or_stderr(self):
        sentinel = "PROBE-FAILURE-SECRET-NOT-FOR-OUTPUT"
        verified = self.probe(sentinel, code=1, stderr=sentinel)
        self.assertEqual(verified["state"], "ambiguous")
        output = "\n".join(environment.format_usage(verified))
        self.assertIn("environment-use state ambiguous", output)
        self.assertNotIn(sentinel, output)
        self.assertNotIn("Close Codex Desktop", output)
        self.assertNotIn("Repository Python environment is currently in use.", output)

    def test_malformed_probe_reports_uncertainty_without_assuming_desktop_open(self):
        verified = self.probe("not valid JSON")
        self.assertEqual(verified["state"], "ambiguous")
        output = "\n".join(environment.format_usage(verified))
        self.assertIn("environment-use state ambiguous", output)
        self.assertIn("Uncertain processes were not labelled as Desktop/MCP", output)
        self.assertNotIn("Close Codex Desktop", output)
        self.assertEqual(verified["blockers"], [])


@unittest.skipUnless(os.name == "nt", "Windows-native process inspection")
class NativeEnvironmentUsageTests(unittest.TestCase):
    def assertSanitized(self, report):
        self.assertEqual(set(report), {"state", "blockers", "ambiguities"})
        self.assertIn(report["state"], {"free", "in_use", "ambiguous"})
        for blocker in report["blockers"]:
            self.assertEqual(set(blocker), {"role", "pid", "executable", "created"})
            self.assertGreater(blocker["pid"], 0)
        for ambiguity in report["ambiguities"]:
            self.assertLessEqual(set(ambiguity), {"pid", "reason"})
        self.assertNotIn("argv", json.dumps(report))

    def inspect(self, root):
        return environment_usage.inspect_windows(
            root, current_pid=os.getpid(),
            current_created=environment_usage.current_creation_time())

    def test_native_current_process_and_redirector_are_not_blockers(self):
        root = Path(__file__).absolute().parents[2]
        report = self.inspect(root)
        self.assertSanitized(report)
        self.assertNotIn(os.getpid(), {item["pid"] for item in report["blockers"]})
        self.assertNotIn(os.getppid(), {item["pid"] for item in report["blockers"]})

    def test_native_disposable_venv_child_blocks_then_disappears_after_exit(self):
        with tempfile.TemporaryDirectory(prefix="lunitora environment use space ") as directory:
            root = Path(directory)
            fixture_env = root / "tools/lunitora_mcp/.venv"
            venv.EnvBuilder(with_pip=False).create(fixture_env)
            executable = fixture_env / "Scripts/python.exe"
            self.assertEqual(self.inspect(root)["state"], "free")
            child = subprocess.Popen(
                [str(executable), "-I", "-B", "-c",
                 "import time; print('READY', flush=True); time.sleep(30)"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                self.assertEqual(child.stdout.readline().strip(), "READY")
                report = self.inspect(root)
                self.assertSanitized(report)
                self.assertIn(child.pid, {item["pid"] for item in report["blockers"]})
                child.terminate()
                child.communicate(timeout=10)
                after = self.inspect(root)
                self.assertSanitized(after)
                self.assertEqual(after["state"], "free")
                self.assertNotIn(child.pid, {item["pid"] for item in after["blockers"]})
            finally:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)

    def test_native_disposable_godot_mcp_module_is_admitted_by_role(self):
        with tempfile.TemporaryDirectory(prefix="lunitora mcp environment use space ") as directory:
            root = Path(directory)
            fixture_env = root / "tools/lunitora_mcp/.venv"
            venv.EnvBuilder(with_pip=False).create(fixture_env)
            core = root / "tools/lunitora_mcp/core"
            core.mkdir()
            (core / "__init__.py").write_bytes(b"")
            (core / "godot_server.py").write_text(
                "import time\nprint('READY', flush=True)\ntime.sleep(30)\n", encoding="ascii")
            executable = fixture_env / "Scripts/python.exe"
            child = subprocess.Popen(
                [str(executable), "-B", "-m", "core.godot_server"], cwd=core.parent,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                self.assertEqual(child.stdout.readline().strip(), "READY")
                report = self.inspect(root)
                self.assertSanitized(report)
                blockers = {item["pid"]: item for item in report["blockers"]}
                self.assertIn(child.pid, blockers)
                self.assertEqual(blockers[child.pid]["role"], "Godot MCP server")
            finally:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
