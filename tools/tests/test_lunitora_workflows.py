"""Dependency-free policy/workflow checks; all application mutations are fake."""
from __future__ import annotations

from dataclasses import replace
import ntpath
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lunitora_machine import policy, workflows
from lunitora_machine.policy import LauncherError, Process

ROOT = Path(r"D:\Game Projects\Totolina Merge")
APPS = {kind: {"kind": kind, "path": path} for kind, path in {
    "desktop": r"C:\Apps\Codex.exe", "photoshop": r"C:\Apps\Photoshop.exe",
    "udt": r"C:\Apps\Adobe UXP Developer Tools.exe", "godot": r"C:\Tools\Godot.exe"}.items()}
VENV = ntpath.join(str(ROOT), "tools", "lunitora_mcp", ".venv", "Scripts", "python.exe")


def process(pid, parent=0, path=None, command="", created=100):
    path = path or APPS["desktop"]["path"]
    return Process(pid, parent, created, path, command, ntpath.basename(path))


def bridge(pid=20, parent=10, module="core.godot_server", path=VENV):
    return process(pid, parent, path, f'"{path}" -B -m {module}', 200)


class FakePlatform:
    name = "windows"

    def __init__(self, processes=()):
        self.items = list(processes)
        self.events = []
        self.owners = {43127: [], 43128: []}
        self.close_exits = True
        self.stop_exits = True

    def processes(self):
        return list(self.items)

    def port_owners(self, port):
        self.events.append(("port", port))
        return list(self.owners[port])

    def request_close(self, item):
        self.events.append(("close", item.pid))
        if self.close_exits:
            self.items.remove(item)

    def stop_verified(self, item):
        self.events.append(("stop", item.pid))
        if self.stop_exits:
            self.items.remove(item)
            for owners in self.owners.values():
                if item.pid in owners:
                    owners.remove(item.pid)

    def spawn_application(self, application, cwd):
        self.events.append(("spawn", application["kind"], cwd))

    def detached_flags(self):
        return {"creationflags": 123}


class PolicyTests(unittest.TestCase):
    def test_absolute_local_paths_and_windows_identity(self):
        self.assertTrue(policy.same_path(r"D:\A\..\Game", "d:/game/"))
        for path in (None, "", "relative.exe", r"D:relative.exe", r"\rooted.exe", r"\\host\share\app.exe"):
            with self.subTest(path=path):
                self.assertFalse(policy.absolute_local_path(path))
                self.assertFalse(policy.same_path(path, path))

    def test_unicode_case_expansion_cannot_alias_another_windows_path(self):
        self.assertFalse(policy.same_path("C:\\stra\u00dfe\\app.exe", "C:\\strasse\\app.exe"))
        self.assertFalse(policy.same_path("C:\\app.exe\x00", "C:\\app.exe"))

    def test_process_identity_requires_pid_time_and_path(self):
        item = process(10)
        self.assertTrue(policy.process_identity(item, item))
        for changed in (replace(item, pid=11), replace(item, created=101), replace(item, created=None),
                        replace(item, executable=None), replace(item, executable=r"C:\Other\Codex.exe")):
            self.assertFalse(policy.process_identity(item, changed))

    def test_descendants_need_live_parent_creation_order(self):
        parent = process(10)
        child = process(20, 10, created=200)
        grandchild = process(30, 20, created=300)
        invalid = [process(40, 10, created=99), process(50, 20, created=None), process(60, 999)]
        self.assertEqual(policy.owned_descendants([grandchild, *invalid, child], [parent]), [child, grandchild])

    def test_conservative_command_parser(self):
        self.assertEqual(policy.windows_arguments('"C:\\App Path\\app.exe" -e "D:\\Game Projects"'),
                         [r"C:\App Path\app.exe", "-e", r"D:\Game Projects"])
        for line in (None, "", 'a"b"', '"mixed"suffix', '"unterminated', '"C:\\end\\"', "app\n-e"):
            self.assertEqual(policy.windows_arguments(line), [], repr(line))

    def test_exact_editor_command_and_spaces(self):
        item = process(20, path=APPS["godot"]["path"],
                       command=f'"{APPS["godot"]["path"]}" --editor --path "{ROOT}"')
        self.assertTrue(policy.godot_editor_command(item, APPS["godot"]["path"], ROOT))
        self.assertFalse(policy.godot_editor_command(item, r"C:\Other\Godot.exe", ROOT))
        self.assertFalse(policy.godot_editor_command(item, APPS["godot"]["path"], Path(r"D:\Other")))

    def test_project_file_and_short_editor_flags(self):
        project = ntpath.join(str(ROOT), "project.godot")
        for args in (f'"{project}"', f'-e "{project}"', f'"{project}" --editor', f'--path "{ROOT}" -e'):
            item = process(20, path=APPS["godot"]["path"], command=f'"{APPS["godot"]["path"]}" {args}')
            self.assertTrue(policy.godot_editor_command(item, item.executable, ROOT), args)

    def test_ambiguous_godot_commands_are_not_editor_proof(self):
        executable = APPS["godot"]["path"]
        for args in ("", "--project-manager", f'--path "{ROOT}"', f'-e -e --path "{ROOT}"',
                     f'-e --path "{ROOT}" --path "D:\\Other"', f'-e --path "{ROOT}" --project-manager',
                     '-e --path .', '-e --path "D:relative"', '-e --path "\\rooted"',
                     '-e --path "\\\\host\\share"', '--EDITOR --path "D:\\Game"'):
            item = process(20, path=executable, command=f'"{executable}" {args}')
            self.assertFalse(policy.godot_editor_command(item, executable, ROOT), args)
        for argv0 in ("Godot.exe", r"C:Godot.exe", r"\Godot.exe"):
            item = process(20, path=executable, command=f'"{argv0}" -e --path "{ROOT}"')
            self.assertFalse(policy.godot_editor_command(item, executable, ROOT))

    def test_bridge_command_accepts_only_exact_module_and_flags(self):
        for module in ("core.server", "core.godot_server"):
            self.assertTrue(policy.server_command(bridge(module=module), VENV, module))
            for args in (f'-m {module}', f'-B -m {module} --setup', f'-B -m {module}.extra',
                         f'-B -c {module}', f'"-B" -m {module}', f'-B -m "{module}"'):
                item = bridge(module=module)
                self.assertFalse(policy.server_command(replace(item, command_line=f'"{VENV}" {args}'), VENV, module))
        self.assertFalse(policy.server_command(bridge(), VENV, "core.server"))
        self.assertFalse(policy.server_command(bridge(), VENV, "arbitrary.module"))
        self.assertFalse(policy.server_command(replace(bridge(), executable=r"C:\Other\python.exe"), VENV, "core.godot_server"))

    def test_direct_venv_bridge_needs_no_redirector_config(self):
        self.assertEqual(policy.proven_bridge_processes(bridge(), [], ROOT, "core.godot_server"), [bridge()])

    def test_redirector_child_needs_exact_parent_base_and_creation_time(self):
        parent = bridge(20, 10)
        base = r"C:\Python312\python.exe"
        child = replace(bridge(30, 20, path=base), created=300)
        with patch.object(Path, "read_text", return_value=f"home = C:\\Python312\nexecutable = {base}\n"):
            self.assertEqual(policy.proven_bridge_processes(child, [parent], ROOT, "core.godot_server"), [child, parent])
            for parents in ([], [parent, parent], [replace(parent, created=301)], [replace(parent, created=None)],
                            [replace(parent, command_line=parent.command_line + " --extra")]):
                self.assertEqual(policy.proven_bridge_processes(child, parents, ROOT, "core.godot_server"), [])
        with patch.object(Path, "read_text", return_value=f"executable = {base}\nexecutable = {base}\n"):
            self.assertEqual(policy.proven_bridge_processes(child, [parent], ROOT, "core.godot_server"), [])
        with patch.object(Path, "read_text", side_effect=OSError):
            self.assertEqual(policy.proven_bridge_processes(child, [parent], ROOT, "core.godot_server"), [])


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.godot = self.enterContext(patch.object(workflows, "ensure_godot_editor"))
        self.port_free = self.enterContext(patch.object(workflows, "assert_port_free"))
        # Deadline advancement is deterministic and never sleeps in these fakes.
        self.enterContext(patch.object(workflows.time, "sleep"))
        self.enterContext(patch.object(workflows.time, "monotonic", side_effect=range(0, 10000, 20)))

    def run_mode(self, mode, platform=None, apps=APPS):
        platform = platform or FakePlatform()
        workflows.run_workflow(mode, apps, ROOT, platform, self.messages.append)
        return platform

    def test_exact_seven_workflow_effects(self):
        expected = {"art": ["photoshop", "desktop"], "art-refresh": ["photoshop", "desktop"],
                    "art-dev": ["photoshop", "udt", "desktop"], "dev": ["desktop"],
                    "dev-refresh": ["desktop"], "godot": ["desktop"], "godot-refresh": ["desktop"]}
        for mode, kinds in expected.items():
            with self.subTest(mode=mode):
                self.godot.reset_mock()
                platform = self.run_mode(mode)
                self.assertEqual([event[1] for event in platform.events if event[0] == "spawn"], kinds)
                self.assertTrue(all(event[2] == ROOT for event in platform.events if event[0] == "spawn"))
                self.assertEqual(self.godot.call_count, int(mode == "godot"))
                ports = {event[1] for event in platform.events if event[0] == "port"}
                self.assertEqual(ports, {43127} if mode == "art-refresh" else {43128} if mode == "godot-refresh" else set())

    def test_unknown_and_unvalidated_mac_workflows_have_no_actions(self):
        platform = FakePlatform()
        with self.assertRaises(LauncherError):
            self.run_mode("unknown", platform)
        platform.name = "macos"
        with self.assertRaisesRegex(LauncherError, "REQUIRES MAC"):
            self.run_mode("godot", platform)
        self.assertEqual(platform.events, [])

    def test_missing_required_application_has_no_actions(self):
        for mode, kind in (("dev", "desktop"), ("art", "photoshop"), ("art-dev", "udt"), ("godot-refresh", "godot")):
            platform = FakePlatform()
            with self.assertRaisesRegex(LauncherError, kind):
                self.run_mode(mode, platform, {key: value for key, value in APPS.items() if key != kind})
            self.assertEqual(platform.events, [])

    def test_existing_applications_are_reused_by_exact_path(self):
        platform = FakePlatform([process(1, path=APPS["desktop"]["path"]), process(2, path=APPS["photoshop"]["path"])])
        self.run_mode("art", platform)
        self.assertEqual(platform.events, [])
        self.assertTrue(any("already running" in message for message in self.messages))

    def test_app_spawn_failure_has_no_fallback_or_retry(self):
        platform = FakePlatform()
        platform.spawn_application = Mock(side_effect=LauncherError("activation failed"))
        with self.assertRaisesRegex(LauncherError, "activation failed"):
            self.run_mode("dev", platform)
        platform.spawn_application.assert_called_once_with(APPS["desktop"], ROOT)

    def test_refresh_closes_desktop_before_reopening(self):
        platform = self.run_mode("dev-refresh", FakePlatform([process(10)]))
        self.assertEqual(platform.events, [("close", 10), ("spawn", "desktop", ROOT)])

    def test_refresh_self_parent_guard_precedes_godot_protection(self):
        desktop = process(10)
        godot = process(os.getpid(), 10, APPS["godot"]["path"], created=200)
        platform = FakePlatform([desktop, godot])
        with self.assertRaisesRegex(LauncherError, "own parent session"):
            self.run_mode("godot-refresh", platform)
        self.assertEqual(platform.events, [])

    def test_godot_refresh_preserves_all_configured_editors_and_descendants(self):
        desktop = process(10)
        godot = process(20, 10, APPS["godot"]["path"], "--another-project", 200)
        child = process(30, 20, r"C:\Apps\Worker.exe", created=300)
        another = process(40, 10, APPS["godot"]["path"], "--project-manager", 200)
        platform = self.run_mode("godot-refresh", FakePlatform([desktop, godot, child, another]))
        self.assertEqual(platform.items, [godot, child, another])
        self.assertFalse(any(event[0] == "stop" for event in platform.events))

    def test_other_refreshes_retain_original_lingering_descendant_boundary(self):
        platform = FakePlatform([process(10), process(20, 10, APPS["godot"]["path"], created=200)])
        with self.assertRaisesRegex(LauncherError, "Recovery stopped"):
            self.run_mode("dev-refresh", platform)
        self.assertFalse(any(event[0] in ("stop", "spawn") for event in platform.events))

    def test_non_exiting_desktop_is_stopped_only_after_fresh_identity(self):
        platform = FakePlatform([process(10)])
        platform.close_exits = False
        self.run_mode("dev-refresh", platform)
        self.assertEqual(platform.events[:2], [("close", 10), ("stop", 10)])

    def test_desktop_that_survives_verified_stop_blocks_reopen(self):
        platform = FakePlatform([process(10)])
        platform.close_exits = platform.stop_exits = False
        with self.assertRaisesRegex(LauncherError, "Desktop is still running"):
            self.run_mode("dev-refresh", platform)
        self.assertFalse(any(event[0] == "spawn" for event in platform.events))

    def test_changed_pid_identity_cannot_reach_native_stop(self):
        item = process(10)
        platform = FakePlatform([replace(item, created=101)])
        with self.assertRaisesRegex(LauncherError, "identity"):
            workflows._stop(platform, item)
        self.assertEqual(platform.events, [])

    def test_disappeared_process_is_benign(self):
        platform = FakePlatform()
        workflows._stop(platform, process(10))
        self.assertEqual(platform.events, [])

    def test_ambiguous_snapshot_blocks_mutations(self):
        platform = FakePlatform([process(10), process(10)])
        with self.assertRaisesRegex(LauncherError, "ambiguous"):
            self.run_mode("dev-refresh", platform)
        self.assertEqual(platform.events, [])

    def test_process_inspection_failure_is_not_an_empty_snapshot(self):
        platform = FakePlatform()
        platform.processes = Mock(side_effect=LauncherError("inspection failed"))
        with self.assertRaisesRegex(LauncherError, "inspection failed"):
            self.run_mode("dev", platform)
        self.assertEqual(platform.events, [])

    def test_unknown_bridge_owner_is_never_killed_or_echoed(self):
        platform = FakePlatform([process(20, path=r"C:\Other\python.exe", command="private-secret")])
        platform.owners[43128] = [20]
        with self.assertRaisesRegex(LauncherError, "Unknown port owner"):
            self.run_mode("godot-refresh", platform)
        self.assertFalse(any(event[0] in ("stop", "spawn") for event in platform.events))
        self.assertNotIn("private-secret", "\n".join(self.messages))

    def test_external_live_bridge_parent_blocks_stop(self):
        platform = FakePlatform([bridge(parent=99), process(99, path=r"C:\Other\client.exe")])
        platform.owners[43128] = [20]
        with self.assertRaisesRegex(LauncherError, "another live process"):
            self.run_mode("godot-refresh", platform)
        self.assertFalse(any(event[0] == "stop" for event in platform.events))

    def test_proven_orphan_bridge_is_stopped_then_port_verified(self):
        platform = FakePlatform([bridge(parent=99)])
        platform.owners[43128] = [20]
        self.run_mode("godot-refresh", platform)
        self.assertIn(("stop", 20), platform.events)
        self.port_free.assert_called_once_with(platform, 43128)

    def test_desktop_owned_bridge_can_stop_during_parent_exit(self):
        item = bridge()
        platform = FakePlatform([item, process(10)])
        platform.owners[43128] = [20]
        workflows.clear_stale_bridge_port(platform, ROOT, [item], 43128, "core.godot_server", self.messages.append)
        self.assertIn(("stop", 20), platform.events)

    def test_port_without_inspectable_owner_blocks_recovery(self):
        platform = FakePlatform()
        platform.owners[43128] = [999]
        with self.assertRaisesRegex(LauncherError, "cannot be inspected"):
            self.run_mode("godot-refresh", platform)
        self.assertFalse(any(event[0] in ("stop", "spawn") for event in platform.events))

    def test_unsupported_port_module_never_inspects_or_stops(self):
        for pair in ((43127, "core.godot_server"), (43128, "core.server"), (999, "core.server")):
            platform = FakePlatform()
            with self.assertRaisesRegex(LauncherError, "Unsupported"):
                workflows.clear_stale_bridge_port(platform, ROOT, [], *pair, self.messages.append)
            self.assertEqual(platform.events, [])


class PortProbeTests(unittest.TestCase):
    def test_occupied_port_is_not_probed_or_reassigned(self):
        platform = FakePlatform()
        platform.owners[43128] = [20]
        with patch.object(workflows.socket, "socket") as factory:
            with self.assertRaisesRegex(LauncherError, "still occupied"):
                workflows.assert_port_free(platform, 43128)
        factory.assert_not_called()

    def test_free_port_uses_exact_loopback_exclusive_probe_and_closes(self):
        platform = FakePlatform()
        with patch.object(workflows.socket, "socket") as factory:
            workflows.assert_port_free(platform, 43128)
        probe = factory.return_value.__enter__.return_value
        probe.bind.assert_called_once_with(("127.0.0.1", 43128))
        probe.listen.assert_called_once_with(1)
        if hasattr(workflows.socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt.assert_called_once_with(workflows.socket.SOL_SOCKET, workflows.socket.SO_EXCLUSIVEADDRUSE, 1)
        factory.return_value.__exit__.assert_called_once()

    def test_bind_failure_is_fail_closed_without_fallback_port(self):
        platform = FakePlatform()
        with patch.object(workflows.socket, "socket") as factory:
            probe = factory.return_value.__enter__.return_value
            probe.bind.side_effect = OSError("private socket detail")
            with self.assertRaisesRegex(LauncherError, "could not be proven free"):
                workflows.assert_port_free(platform, 43128)
        probe.bind.assert_called_once_with(("127.0.0.1", 43128))
        probe.listen.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
