"""Windows adapter contracts plus read-only native probes; no apps started/stopped."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import builtins
import ntpath
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lunitora_machine.policy import LauncherError, Process
from lunitora_machine.platforms import windows


class WindowsContracts(unittest.TestCase):
    def setUp(self):
        self.platform = windows.WindowsPlatform()
        self.native = Mock()
        self.native.metadata.return_value = {"ProductName": "Codex", "ProductVersion": "1.2.3"}
        self.native.publisher.return_value = "OpenAI OpCo, LLC"
        self.api_patch = patch.object(windows, "_api", return_value=self.native)
        self.api_patch.start()
        self.addCleanup(self.api_patch.stop)
        self.path_patch = patch.object(windows, "_absolute_executable", side_effect=lambda path: path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def test_wmi_creation_uses_integer_filetime_microseconds(self):
        self.assertEqual(windows._wmi_created("16010101000000.000001+000"), 1)
        self.assertEqual(windows._wmi_created("20260101000000.123456+000"),
                         windows._wmi_created("20251231160000.123456-480"))
        self.assertIsNone(windows._wmi_created(None))
        self.assertIsNone(windows._wmi_created("2026**********.******+000"))
        self.assertIsNone(windows._wmi_created("20260231000000.000000+000"))

    def test_raw_com_process_and_app_enumeration_never_import_generated_clients(self):
        class Dispatch:
            def __init__(self, properties=None, methods=None, items=None):
                self.properties, self.methods, self.values = properties or {}, methods or {}, items or []
            def get(self, name):
                return self.properties[name]
            def call(self, name, *arguments):
                return self.methods[name](*arguments)
            def items(self, limit=65536):
                if len(self.values) > limit:
                    raise LauncherError("Native COM enumeration exceeds its safety bound.")
                return iter(self.values)

        item = Dispatch({"Name": "Codex"}, {"ExtendedProperty": lambda name: "Registered.Desktop_publisher!DesktopUI"})
        folder = Dispatch(methods={"Items": lambda: Dispatch({"Count": 1}, items=[item])})
        shell = Dispatch(methods={"NameSpace": lambda name: folder})
        row = Dispatch({"ProcessId": 100, "ParentProcessId": 1, "CreationDate": "20260101000000.123456+000",
                        "ExecutablePath": r"C:\Apps\Codex.exe", "CommandLine": None, "Name": "Codex.exe"})
        service = Dispatch(methods={"ExecQuery": lambda query: Dispatch(items=[row])})
        original_import = builtins.__import__
        def guard(name, *args, **kwargs):
            if name.startswith(("win32com", "pythoncom", "win32api")):
                raise AssertionError("Third-party COM clients/cache must not be imported.")
            return original_import(name, *args, **kwargs)
        with patch.object(windows, "_RawDispatch", side_effect=lambda value: value), \
                patch.object(windows, "_shell_dispatch", return_value=shell), \
                patch.object(windows, "_wmi_dispatch", return_value=service), \
                patch.object(builtins, "__import__", side_effect=guard):
            apps = self.platform._apps_folder()
            processes = self.platform.processes()
        self.assertEqual(apps, [{"aumid": "Registered.Desktop_publisher!DesktopUI", "name": "Codex"}])
        self.assertEqual(processes[0].pid, 100)
        self.assertIsNone(processes[0].command_line)

    def test_raw_com_enumeration_is_bounded(self):
        dispatch = object.__new__(windows._RawDispatch)
        with self.assertRaisesRegex(LauncherError, "safety bound"):
            list(dispatch.items(limit=65537))

    def test_process_inspection_failure_never_returns_empty_snapshots(self):
        with patch.object(windows, "_wmi_dispatch", side_effect=OSError("Denied")):
            with self.assertRaisesRegex(LauncherError, "no empty-list fallback"):
                self.platform.processes()

    def test_signature_validation_is_cache_only_without_network_retrieval(self):
        native = object.__new__(windows._WindowsAPI)
        native.trust = Mock()
        def verify(window, action, data_pointer):
            data = ctypes.cast(data_pointer, ctypes.POINTER(windows._WINTRUST_DATA)).contents
            self.assertEqual(data.flags, 0x1000)
            self.assertEqual(data.ui, 2)
            return -1
        native.trust.WinVerifyTrust.side_effect = verify
        with self.assertRaisesRegex(LauncherError, "valid OpenAI"):
            native.publisher(r"C:\Apps\Codex.exe")

    def test_godot_official_metadata_and_legacy_kind(self):
        self.native.metadata.return_value = {"ProductName": "Godot Engine", "ProductVersion": "4.7.2.stable.official.abc123"}
        app = self.platform.validate_application("godotExe", r"C:\Tools\Godot_v4.7.2-stable_win64.exe")
        self.assertEqual(app["kind"], "godot")
        self.assertEqual(app["version"], "4.7.2.stable.official.abc123")
        self.native.metadata.return_value["ProductVersion"] = "4.7.2.stable.custom.abc123"
        with self.assertRaises(LauncherError):
            self.platform.validate_application("godot", r"C:\Tools\Godot.exe")

    def test_photoshop_minimum_and_newer_versions_are_numerically_validated(self):
        for product, version in (("Adobe Photoshop", "27.10.0"), ("Photoshop", "27.11.1"),
                                 ("Adobe Photoshop 2026", "28.0.0")):
            with self.subTest(product=product, version=version):
                self.native.metadata.return_value = {"ProductName": product, "ProductVersion": version}
                app = self.platform.validate_application("photoshop", r"C:\Adobe\Photoshop.exe")
                self.assertEqual(app["version"], version)

    def test_old_or_unparseable_photoshop_version_is_rejected(self):
        for version in ("27.9.9", "26.99.0", "current"):
            with self.subTest(version=version):
                self.native.metadata.return_value = {"ProductName": "Adobe Photoshop", "ProductVersion": version}
                with self.assertRaisesRegex(LauncherError, "27.10"):
                    self.platform.validate_application("photoshop", r"C:\Adobe\Photoshop.exe")

    def test_photoshop_filename_without_product_identity_is_rejected(self):
        self.native.metadata.return_value = {"ProductName": "Another Editor", "ProductVersion": "28.0.0"}
        with self.assertRaisesRegex(LauncherError, "Photoshop application"):
            self.platform.validate_application("photoshop", r"C:\Adobe\Photoshop.exe")

    def test_udt_requires_uxp_developer_product_identity(self):
        self.native.metadata.return_value = {"ProductName": "Adobe UXP Developer Tools", "ProductVersion": "2.2.1"}
        app = self.platform.validate_application("udt", r"C:\Adobe\Adobe UXP Developer Tools.exe")
        self.assertEqual(app["identity"], "Adobe UXP Developer Tools")
        self.native.metadata.return_value["ProductName"] = "Adobe Other Tools"
        with self.assertRaisesRegex(LauncherError, "UXP Developer Tool product"):
            self.platform.validate_application("udt", r"C:\Adobe\Adobe UXP Developer Tools.exe")

    def test_wrong_filename_or_product_cannot_masquerade_as_desktop(self):
        with self.assertRaises(LauncherError):
            self.platform.validate_application("desktop", r"C:\Tools\codex-command-runner.exe")
        self.native.metadata.return_value["ProductName"] = "Codex CLI"
        with self.assertRaises(LauncherError):
            self.platform.validate_application("desktop", r"C:\Tools\Codex.exe")
        self.native.publisher.assert_not_called()

    def test_desktop_requires_verified_openai_leaf_signer(self):
        self.native.publisher.return_value = "Not OpenAI OpCo, LLC"
        with self.assertRaisesRegex(LauncherError, "OpenAI publisher"):
            self.platform.validate_application("desktop", r"C:\Apps\Codex.exe")

    def test_registered_desktop_uses_discovered_exact_application_identity(self):
        package = {"family": "Registered.Desktop_publisher", "path": r"C:\RegisteredDesktop"}
        self.platform._registered_packages = Mock(return_value=[package])
        self.platform._manifest_applications = Mock(return_value=[
            {"path": r"C:\RegisteredDesktop\app\Codex.exe", "id": "DesktopUI"},
            {"path": r"C:\RegisteredDesktop\app\resources\codex-command-runner.exe", "id": "Runner"},
        ])
        app = self.platform.validate_application("desktop", r"C:\RegisteredDesktop\app\Codex.exe")
        self.assertEqual(app["aumid"], "Registered.Desktop_publisher!DesktopUI")

    def test_ambiguous_registration_and_manifest_are_rejected(self):
        package = {"family": "Registered.Desktop_publisher", "path": r"C:\RegisteredDesktop"}
        self.platform._registered_packages = Mock(return_value=[package, package])
        with self.assertRaisesRegex(LauncherError, "ambiguous"):
            self.platform.validate_application("desktop", r"C:\RegisteredDesktop\Codex.exe")
        self.platform._registered_packages.return_value = [package]
        self.platform._manifest_applications = Mock(return_value=[
            {"path": r"C:\RegisteredDesktop\Codex.exe", "id": "A"},
            {"path": r"C:\RegisteredDesktop\Codex.exe", "id": "B"},
        ])
        with self.assertRaisesRegex(LauncherError, "exactly one"):
            self.platform.validate_application("desktop", r"C:\RegisteredDesktop\Codex.exe")

    def test_package_inspection_failure_never_becomes_unpackaged_fallback(self):
        self.platform._registered_packages = Mock(side_effect=LauncherError("Registration denied"))
        with self.assertRaisesRegex(LauncherError, "Registration denied"):
            self.platform.validate_application("desktop", r"C:\Apps\Codex.exe")

    def test_unregistered_windowsapps_binary_is_rejected(self):
        self.platform._registered_packages = Mock(return_value=[])
        with self.assertRaisesRegex(LauncherError, "Unregistered WindowsApps"):
            self.platform.validate_application("desktop", r"C:\Program Files\WindowsApps\Desktop\Codex.exe")

    def test_package_activation_failure_is_one_attempt_without_binary_fallback(self):
        app = {"kind": "desktop", "path": r"C:\RegisteredDesktop\Codex.exe",
               "aumid": "Registered.Desktop_publisher!DesktopUI"}
        self.platform.validate_application = Mock(return_value=app)
        with patch.object(windows.subprocess, "Popen", side_effect=OSError("Denied")) as start:
            with self.assertRaisesRegex(LauncherError, "no retry"):
                self.platform.spawn_application(app, Path(r"C:\Project With Spaces"))
        self.assertEqual(start.call_count, 1)
        self.assertEqual(start.call_args.args[0][1], "shell:AppsFolder\\Registered.Desktop_publisher!DesktopUI")
        self.assertNotIn("cwd", start.call_args.kwargs)

    def test_changed_activation_identity_stops_before_start(self):
        app = {"kind": "desktop", "path": r"C:\RegisteredDesktop\Codex.exe", "aumid": "Family!Old"}
        self.platform.validate_application = Mock(return_value={**app, "aumid": "Family!New"})
        with patch.object(windows.subprocess, "Popen") as start:
            with self.assertRaisesRegex(LauncherError, "changed"):
                self.platform.spawn_application(app, Path(r"C:\Project"))
        start.assert_not_called()

    def test_discovery_registry_failure_is_fatal_without_fallback(self):
        self.platform._registry_candidates = Mock(side_effect=LauncherError("Registry denied"))
        self.platform.validate_application = Mock()
        with patch.object(windows.shutil, "which", return_value=None):
            with self.assertRaisesRegex(LauncherError, "Registry denied"):
                self.platform.discover("godot")
        self.platform.validate_application.assert_not_called()

    def test_saved_godot_parent_discovers_all_candidates_without_newest_pick(self):
        old = Path(r"C:\Saved Godot\Godot_old.exe")
        paths = [Path(r"C:\Saved Godot\Godot_one.exe"), Path(r"C:\Saved Godot\Godot_two.exe")]
        self.platform._registry_candidates = Mock(return_value=[])
        def validate(kind, path):
            if path not in {str(value) for value in paths}:
                raise LauncherError("Missing")
            return {"kind": kind, "path": path, "version": "4.7.2", "identity": "Godot"}
        self.platform.validate_application = Mock(side_effect=validate)
        with patch.object(windows.shutil, "which", return_value=None), \
                patch.object(Path, "is_dir", return_value=True), \
                patch.object(Path, "glob", return_value=iter(paths)):
            result = self.platform.discover("godot", {"path": str(old)})
        self.assertEqual({app["path"] for app in result}, {str(path) for path in paths})

    def test_fresh_identity_mismatch_is_rejected_before_native_handle(self):
        process = Process(100, 1, 123, r"C:\Apps\Codex.exe", None, "Codex.exe")
        self.platform.processes = Mock(return_value=[Process(100, 1, 124, process.executable, None, process.name)])
        with self.assertRaisesRegex(LauncherError, "changed"):
            self.platform.stop_verified(process)
        self.native.kernel.OpenProcess.assert_not_called()
        self.native.kernel.TerminateProcess.assert_not_called()

    def test_disappearance_is_benign_without_native_mutation(self):
        process = Process(100, 1, 123, r"C:\Apps\Codex.exe", None, "Codex.exe")
        self.platform.processes = Mock(return_value=[])
        self.platform.request_close(process)
        self.platform.stop_verified(process)
        self.native.kernel.OpenProcess.assert_not_called()

    def test_missing_creation_or_executable_is_never_proof(self):
        for created, executable in ((None, r"C:\Apps\Codex.exe"), (0, r"C:\Apps\Codex.exe"), (123, None)):
            with self.assertRaisesRegex(LauncherError, "incomplete"):
                self.platform.stop_verified(Process(100, 1, created, executable, None, "Codex.exe"))
        self.native.kernel.TerminateProcess.assert_not_called()

    def test_held_handle_identity_mismatch_closes_without_termination(self):
        process = Process(100, 1, 123, r"C:\Apps\Codex.exe", None, "Codex.exe")
        self.platform.processes = Mock(return_value=[process])
        self.native.kernel.OpenProcess.return_value = 99
        self.native.process_identity.return_value = (124, process.executable)
        with self.assertRaisesRegex(LauncherError, "Held process identity"):
            self.platform.stop_verified(process)
        self.native.kernel.CloseHandle.assert_called_once_with(99)
        self.native.kernel.TerminateProcess.assert_not_called()

    def test_verified_termination_uses_held_handle_and_waits(self):
        process = Process(100, 1, 123, r"C:\Apps\Codex.exe", None, "Codex.exe")
        self.platform.processes = Mock(return_value=[process])
        self.native.kernel.OpenProcess.return_value = 99
        self.native.process_identity.return_value = (123, process.executable)
        self.native.kernel.WaitForSingleObject.side_effect = [258, 0]
        self.native.kernel.TerminateProcess.return_value = True
        self.platform.stop_verified(process)
        self.native.kernel.TerminateProcess.assert_called_once_with(99, 1)
        self.native.kernel.WaitForSingleObject.assert_any_call(99, 5000)
        self.native.kernel.CloseHandle.assert_called_once_with(99)

    def test_unknown_held_handle_wait_status_cannot_terminate(self):
        process = Process(100, 1, 123, r"C:\Apps\Codex.exe", None, "Codex.exe")
        self.platform.processes = Mock(return_value=[process])
        self.native.kernel.OpenProcess.return_value = 99
        self.native.process_identity.return_value = (123, process.executable)
        self.native.kernel.WaitForSingleObject.return_value = 0xFFFFFFFF
        with self.assertRaisesRegex(LauncherError, "state could not"):
            self.platform.stop_verified(process)
        self.native.kernel.TerminateProcess.assert_not_called()
        self.native.kernel.CloseHandle.assert_called_once_with(99)

    def test_port_bounds_are_checked_before_native_query(self):
        for port in (0, -1, 65536, "43128"):
            with self.assertRaisesRegex(LauncherError, "Invalid TCP port"):
                self.platform.port_owners(port)
        self.native.port_owners.assert_not_called()

    def test_tcp_owner_table_preserves_network_port_and_ipv4_ipv6(self):
        native = object.__new__(windows._WindowsAPI)
        native.ip = Mock()
        def query(data, length_pointer, ordered, family, table, reserved):
            row_type = windows._TCP4_ROW if family == 2 else windows._TCP6_ROW
            length = ctypes.cast(length_pointer, ctypes.POINTER(wintypes.DWORD))
            length.contents.value = 4 + ctypes.sizeof(row_type)
            self.assertEqual(table, 3)
            if data is None:
                return 122
            ctypes.cast(data, ctypes.POINTER(wintypes.DWORD)).contents.value = 1
            row = row_type.from_buffer(data, 4)
            row.state, row.port, row.pid = 2, socket.htons(43128), family
            return 0
        native.ip.GetExtendedTcpTable.side_effect = query
        self.assertEqual(native.port_owners(43128), [2, 23])
        self.assertEqual(native.port_owners(43127), [])


@unittest.skipUnless(os.name == "nt", "Requires Windows native APIs")
class WindowsReadOnlyNative(unittest.TestCase):
    def test_current_python_product_metadata_is_readable(self):
        metadata = windows._api().metadata(sys.executable)
        self.assertTrue(metadata["ProductName"])
        self.assertTrue(metadata["ProductVersion"])

    def test_own_wmi_and_held_process_creation_and_executable_match(self):
        platform = windows.WindowsPlatform()
        own = [process for process in platform.processes() if process.pid == os.getpid()]
        self.assertEqual(len(own), 1)
        self.assertIsNotNone(own[0].command_line)
        native = windows._api()
        handle = native.kernel.OpenProcess(0x1000, False, os.getpid())
        self.assertTrue(handle)
        try:
            created, executable = native.process_identity(handle)
            self.assertEqual(own[0].created, created)
            self.assertTrue(windows._same_path(own[0].executable, executable))
            self.assertTrue(any(windows._same_path(executable, path) for path in
                                (sys.executable, getattr(sys, "_base_executable", sys.executable))))
        finally:
            native.kernel.CloseHandle(handle)

    def test_tcp_owner_queries_are_read_only_and_return_valid_pids(self):
        for port in (43127, 43128):
            owners = windows.WindowsPlatform().port_owners(port)
            self.assertEqual(owners, sorted(set(owners)))
            self.assertTrue(all(isinstance(pid, int) and pid > 0 for pid in owners))


if __name__ == "__main__":
    unittest.main()
