"""Bounded recovery tests use simulated identities or disposable MCP fixtures."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import environment_recovery as recovery
from lunitora_machine.environment_usage import classify_processes


class FakeRecovery:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.pinned, self.verified, self.stopped, self.closed = [], [], [], []
        self.pin_failure = None
        self.verify_failure = None
        self.stop_failure = None
        self.wait_failure = None

    def snapshot(self):
        return deepcopy(self.rows)

    def pin(self, row):
        if row["pid"] == self.pin_failure:
            raise ValueError("SECRET-PIN-DETAIL")
        self.pinned.append(row["pid"])
        return dict(row)

    def verify(self, target):
        self.verified.append(target["pid"])
        if target["pid"] == self.verify_failure:
            raise ValueError("SECRET-IDENTITY-DETAIL")
        return True

    def stop(self, target):
        if target["pid"] == self.stop_failure:
            raise ValueError("SECRET-STOP-DETAIL")
        self.stopped.append(target["pid"])
        return target["pid"] != self.wait_failure

    def close(self, target):
        self.closed.append(target["pid"])


class EnvironmentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(r"C:\Work Trees\Totolina Merge")
        self.venv = str(self.root / "tools/lunitora_mcp/.venv/Scripts/python.exe")
        self.base = r"C:\Python312\python.exe"
        self.parent = self.row(700, self.venv, created=100)
        self.child = self.row(701, self.base, parent=700, created=200)
        self.rows = [self.parent, self.child]
        self.usage = self.report(self.rows)

    def row(self, pid, executable, *, created=100, parent=1, module="core.godot_server"):
        return {"pid": pid, "parent_pid": parent, "created": created,
                "executable": executable, "argv": [executable, "-B", "-m", module],
                "alive": True, "identity_ok": True}

    def report(self, rows):
        return {"state": "in_use", "blockers": [
            {"role": "Godot MCP server" if row["argv"][3] == "core.godot_server" else "Photoshop MCP server",
             "pid": row["pid"], "created": row["created"], "executable": row["executable"]}
            for row in rows], "ambiguities": []}

    def recover(self, *, rows=None, usage=None, answer="y", interactive=True, backend=None):
        backend = backend or FakeRecovery(self.rows if rows is None else rows)
        self.output, self.prompts = [], []
        def prompt(question):
            self.prompts.append(question)
            return answer
        result = recovery.recover_mcp_blockers(
            self.root, self.usage if usage is None else usage, interactive=interactive,
            prompt=prompt, emit=self.output.append, backend=backend, base_executable=self.base)
        return result, backend

    def assertSafeRefusal(self, result, backend):
        self.assertFalse(result["recovered"])
        self.assertEqual(result["state"], "ambiguous")
        self.assertEqual(backend.stopped, [])

    def test_exact_mcp_base_child_and_redirector_are_stopped_once_child_first(self):
        result, backend = self.recover()
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [701, 700])
        self.assertEqual(backend.pinned, [701, 700])
        self.assertEqual(backend.closed, [701, 700])
        self.assertEqual(len(self.prompts), 1)

    def test_direct_venv_mcp_without_redirected_child_is_admitted(self):
        result, backend = self.recover(rows=[self.parent], usage=self.report([self.parent]))
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [700])

    def test_photoshop_mcp_has_exact_role_and_unchanged_command_contract(self):
        row = self.row(702, self.venv, module="core.server")
        result, backend = self.recover(rows=[row], usage=self.report([row]))
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [702])
        self.assertIn("Photoshop MCP server | PID 702", "\n".join(self.output))

    def test_base_child_argv_zero_can_name_exact_venv_redirector(self):
        self.child["argv"][0] = self.venv
        result, backend = self.recover()
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [701, 700])

    def test_explicit_yes_is_accepted_case_insensitively(self):
        self.assertTrue(self.recover(answer=" YES ")[0]["recovered"])

    def test_declined_recovery_preserves_all_processes(self):
        result, backend = self.recover(answer="n")
        self.assertFalse(result["recovered"])
        self.assertEqual(result["state"], "deferred")
        self.assertEqual(backend.stopped, [])
        self.assertEqual(backend.closed, backend.pinned)

    def test_blank_response_does_not_implicitly_approve_termination(self):
        self.assertFalse(self.recover(answer="")[0]["recovered"])

    def test_noninteractive_setup_performs_no_snapshot_pin_or_prompt(self):
        backend = FakeRecovery(self.rows)
        backend.snapshot = lambda: self.fail("noninteractive recovery took a snapshot")
        result, backend = self.recover(interactive=False, backend=backend)
        self.assertEqual(result["state"], "deferred")
        self.assertEqual(backend.pinned, [])
        self.assertEqual(self.prompts, [])

    def test_ambiguous_usage_is_not_terminated_or_prompted(self):
        usage = deepcopy(self.usage)
        usage.update(state="ambiguous", ambiguities=[{"reason": "process provenance changed"}])
        result, backend = self.recover(usage=usage)
        self.assertSafeRefusal(result, backend)
        self.assertEqual(self.prompts, [])

    def test_generic_repo_python_blocker_is_never_terminated(self):
        usage = deepcopy(self.usage)
        usage["blockers"][0]["role"] = "Repository Python process"
        self.assertSafeRefusal(*self.recover(usage=usage))

    def test_unrelated_base_python_is_not_recovered(self):
        unrelated = self.row(703, self.base)
        unrelated["argv"] = [self.base, "-B", "other_script.py"]
        result, backend = self.recover(rows=[*self.rows, unrelated])
        self.assertTrue(result["recovered"])
        self.assertNotIn(703, backend.stopped)

    def test_other_checkout_mcp_redirector_and_base_child_are_not_recovered(self):
        other = r"C:\Other Checkout\tools\lunitora_mcp\.venv\Scripts\python.exe"
        parent = self.row(710, other, created=50)
        child = self.row(711, self.base, parent=710, created=60)
        result, backend = self.recover(rows=[*self.rows, parent, child])
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [701, 700])

    def test_godot_editor_and_desktop_are_never_recovery_targets(self):
        editor = self.row(712, r"C:\Godot\Godot.exe")
        editor["argv"] = [editor["executable"], "--editor", "--path", str(self.root)]
        desktop = self.row(713, r"C:\Desktop\Codex.exe")
        desktop["argv"] = [desktop["executable"]]
        result, backend = self.recover(rows=[*self.rows, editor, desktop])
        self.assertTrue(result["recovered"])
        self.assertEqual(backend.stopped, [701, 700])

    def test_reported_role_must_match_exact_native_module(self):
        usage = deepcopy(self.usage)
        usage["blockers"][0]["role"] = "Photoshop MCP server"
        self.assertSafeRefusal(*self.recover(usage=usage))

    def test_pythonw_is_not_implicitly_admitted_as_reviewed_mcp_command(self):
        executable = self.venv.replace("python.exe", "pythonw.exe")
        row = self.row(714, executable)
        self.assertSafeRefusal(*self.recover(rows=[row], usage=self.report([row])))

    def test_same_module_with_extra_arguments_is_not_recovered_or_disclosed(self):
        self.parent["argv"].extend(["--token", "SECRET-ARGUMENT"])
        result, backend = self.recover()
        self.assertSafeRefusal(result, backend)
        self.assertNotIn("SECRET-ARGUMENT", "\n".join(self.output) + str(result))

    def test_same_module_without_exact_B_switch_is_not_recovered(self):
        self.parent["argv"].remove("-B")
        self.assertSafeRefusal(*self.recover())

    def test_unreadable_argv_is_never_recovered(self):
        self.parent["argv"] = None
        self.assertSafeRefusal(*self.recover())

    def test_orphan_base_mcp_without_live_venv_parent_is_not_recovered(self):
        self.assertSafeRefusal(*self.recover(rows=[self.child], usage=self.report([self.child])))

    def test_base_mcp_has_no_implicit_admission_from_venv_argv_zero(self):
        self.child["argv"][0] = self.venv
        self.assertSafeRefusal(*self.recover(rows=[self.child], usage=self.report([self.child])))

    def test_pid_reuse_since_usage_admission_is_refused(self):
        self.child["created"] += 1
        self.assertSafeRefusal(*self.recover())

    def test_reused_parent_cannot_prove_base_child_checkout(self):
        self.parent["created"] = 300
        self.assertSafeRefusal(*self.recover(usage=self.report(self.rows)))

    def test_changed_executable_since_usage_admission_is_refused(self):
        self.parent["executable"] = r"C:\Unrelated Python\python.exe"
        self.assertSafeRefusal(*self.recover())

    def test_missing_creation_time_disables_recovery(self):
        usage = deepcopy(self.usage)
        usage["blockers"][0].pop("created")
        self.assertSafeRefusal(*self.recover(usage=usage))

    def test_unverifiable_identity_disables_recovery(self):
        self.parent["identity_ok"] = False
        self.assertSafeRefusal(*self.recover())

    def test_new_repository_python_blocker_cancels_entire_recovery(self):
        additional = self.row(704, self.venv)
        additional["argv"] = [self.venv, "-B", "user_work.py"]
        self.assertSafeRefusal(*self.recover(rows=[*self.rows, additional]))

    def test_new_mcp_blocker_not_in_admission_is_not_silently_added(self):
        self.assertSafeRefusal(*self.recover(rows=[*self.rows, self.row(705, self.venv)]))

    def test_exited_or_missing_admitted_pid_requires_fresh_inspection_not_termination(self):
        self.parent["alive"] = False
        self.child["alive"] = False
        self.assertSafeRefusal(*self.recover())

    def test_duplicate_expected_pid_is_refused(self):
        usage = deepcopy(self.usage)
        usage["blockers"].append(deepcopy(usage["blockers"][0]))
        self.assertSafeRefusal(*self.recover(usage=usage))

    def test_setup_current_pid_cannot_be_admitted_for_recovery(self):
        row = self.row(os.getpid(), self.venv)
        self.assertSafeRefusal(*self.recover(rows=[row], usage=self.report([row])))

    def test_child_and_parent_modules_must_match(self):
        self.child["argv"][3] = "core.server"
        self.assertSafeRefusal(*self.recover(usage=self.report(self.rows)))

    def test_partial_pin_failure_cancels_before_prompt_or_any_termination(self):
        backend = FakeRecovery(self.rows)
        backend.pin_failure = 700
        result, backend = self.recover(backend=backend)
        self.assertSafeRefusal(result, backend)
        self.assertEqual(backend.closed, [701])
        self.assertEqual(self.prompts, [])

    def test_changed_held_identity_after_consent_cancels_before_first_termination(self):
        backend = FakeRecovery(self.rows)
        backend.verify_failure = 700
        self.assertSafeRefusal(*self.recover(backend=backend))

    def test_termination_failure_does_not_retry_or_continue_to_redirector(self):
        backend = FakeRecovery(self.rows)
        backend.stop_failure = 701
        result, backend = self.recover(backend=backend)
        self.assertSafeRefusal(result, backend)
        self.assertEqual(backend.closed, backend.pinned)

    def test_unproven_exit_does_not_allow_update_or_stop_more_processes(self):
        backend = FakeRecovery(self.rows)
        backend.wait_failure = 701
        result, backend = self.recover(backend=backend)
        self.assertFalse(result["recovered"])
        self.assertEqual(result["state"], "ambiguous")
        self.assertEqual(backend.stopped, [701])
        self.assertEqual(backend.closed, backend.pinned)

    def test_diagnostics_name_roles_and_pids_but_no_argv_or_exceptions(self):
        result, backend = self.recover()
        output = "\n".join(self.output) + str(result)
        self.assertIn("Godot MCP server | PID 700", output)
        self.assertIn("Godot MCP server | PID 701", output)
        self.assertNotIn("core.godot_server", output)
        self.assertNotIn("SECRET", output)
        self.assertIn("Godot Editor and Desktop will not be closed", output)

    def test_case_insensitive_paths_with_spaces_match_exact_checkout(self):
        for row in self.rows:
            row["executable"] = row["executable"].upper()
            row["argv"][0] = row["argv"][0].upper()
        self.assertTrue(self.recover()[0]["recovered"])


@unittest.skipUnless(os.name == "nt", "Windows-native disposable recovery")
class NativeEnvironmentRecoveryTests(unittest.TestCase):
    def fixture(self, answer):
        with tempfile.TemporaryDirectory(prefix="lunitora recovery path spaces ") as directory:
            root = Path(directory)
            venv.EnvBuilder(with_pip=False).create(root / "tools/lunitora_mcp/.venv")
            core = root / "tools/lunitora_mcp/core"
            core.mkdir()
            (core / "__init__.py").write_bytes(b"")
            (core / "godot_server.py").write_text(
                "import time\nprint('READY', flush=True)\ntime.sleep(30)\n", encoding="ascii")
            executable = root / "tools/lunitora_mcp/.venv/Scripts/python.exe"
            child = subprocess.Popen(
                [str(executable), "-B", "-m", "core.godot_server"], cwd=core.parent,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                self.assertEqual(child.stdout.readline().strip(), "READY")
                backend = recovery._RecoveryNative()
                rows = backend.snapshot()
                base = recovery._base_python(root)
                usage = classify_processes(root, rows, current_pid=os.getpid(), probe_pid=os.getpid(),
                                           base_executable=base)
                births = {row["pid"]: row["created"] for row in rows if "created" in row}
                for blocker in usage["blockers"]:
                    blocker["created"] = births[blocker["pid"]]
                self.assertEqual(usage["state"], "in_use")
                self.assertIn(child.pid, {item["pid"] for item in usage["blockers"]})
                output = []
                result = recovery.recover_mcp_blockers(root, usage, interactive=True,
                                                       prompt=lambda _: answer, emit=output.append,
                                                       backend=backend, base_executable=base)
                if answer == "y":
                    self.assertTrue(result["recovered"], result)
                    child.communicate(timeout=10)
                    after = classify_processes(root, backend.snapshot(), current_pid=os.getpid(),
                                               probe_pid=os.getpid(), base_executable=base)
                    self.assertEqual(after["state"], "free", after)
                else:
                    self.assertFalse(result["recovered"])
                    self.assertIsNone(child.poll())
            finally:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=10)

    def test_native_accepted_exact_fixture_exit_is_proven_before_return(self):
        self.fixture("y")

    def test_native_declined_exact_fixture_remains_running(self):
        self.fixture("n")


if __name__ == "__main__":
    unittest.main()
