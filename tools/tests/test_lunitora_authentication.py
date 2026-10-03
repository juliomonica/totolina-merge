"""Provisioning contracts and disposable native storage; no workstation secrets."""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import authentication as auth
from lunitora_machine import native_credentials as storage


def safe_git(command, **kwargs):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def godot_payload(config, root):
    path, identity = config.project_identity(root)
    return json.dumps({"schema_version": 1, "project_path": path,
                       "project_id": identity, "secret": "a" * 64}).encode()


def acl_snapshot(path):
    native = storage._native()
    length = native.security.GetSecurityDescriptorLength
    length.argtypes, length.restype = [ctypes.c_void_p], w.DWORD
    with ExitStack() as stack:
        handle = storage.pin(stack, path, directory=path.is_dir())
        descriptor = ctypes.c_void_p()
        status = native.security.GetSecurityInfo(storage._handle(handle), 1, 1 | 4,
                                                 None, None, None, None, ctypes.byref(descriptor))
        if status or not descriptor.value:
            raise AssertionError("Disposable security descriptor unavailable")
        try:
            size = length(descriptor)
            if not 20 <= size <= 65536:
                raise AssertionError("Disposable security descriptor bounds invalid")
            return ctypes.string_at(descriptor, size)
        finally:
            native.kernel.LocalFree(descriptor)


def broaden_disposable_acl(path):
    native = storage._native()
    user, system = [ctypes.create_string_buffer(value) for value in native.identity()]
    world, size = ctypes.create_string_buffer(68), w.DWORD(68)
    if not native.security.CreateWellKnownSid(1, None, world, ctypes.byref(size)):
        raise AssertionError("Disposable World SID unavailable")
    acl = ctypes.create_string_buffer(8 + len(user) - 1 + len(system) - 1 + size.value + 24)
    if not native.security.InitializeAcl(acl, len(acl), 2):
        raise AssertionError("Disposable ACL unavailable")
    for sid in (user, system):
        if not native.security.AddAccessAllowedAceEx(acl, 2, 0, storage._NT.FILE_ALL_ACCESS, sid):
            raise AssertionError("Disposable ACL creation failed")
    if not native.security.AddAccessAllowedAceEx(acl, 2, 0, 0x120089, world):
        raise AssertionError("Disposable ACL broadening failed")
    setter = native.security.SetNamedSecurityInfoW
    setter.argtypes, setter.restype = [w.LPWSTR, ctypes.c_int, w.DWORD] + [ctypes.c_void_p] * 4, w.DWORD
    if setter(str(path), 1, 4, None, None, acl, None):
        raise AssertionError("Disposable ACL installation failed")


class AuthenticationContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd() / "disposable project with spaces"
        self.config, self.security, self.photoshop = auth._reviewed_modules()
        self.guard = patch.object(auth, "_guard_storage")
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def provision(self, names=("godot",), **kwargs):
        return auth.provision_authentication(self.root, "windows", names, runner=safe_git, **kwargs)

    def test_mac_authentication_is_unvalidated_and_does_not_inspect_credentials(self):
        with patch.object(auth, "_reviewed_modules") as modules, patch.object(auth, "_read_protected") as reader:
            result = auth.provision_authentication(self.root, "macos", ("godot", "photoshop"))
        self.assertEqual({item["state"] for item in result.values()}, {"REQUIRES MAC"})
        self.assertFalse(any(item["ready"] for item in result.values()))
        modules.assert_not_called()
        reader.assert_not_called()

    def test_empty_capabilities_do_not_load_authentication(self):
        with patch.object(auth, "_reviewed_modules") as modules:
            self.assertEqual(self.provision(()), {})
        modules.assert_not_called()

    def test_unreviewed_authentication_is_rejected(self):
        for capability in ("apple-signing", "store-password", "codex-login", "certificate"):
            with self.subTest(capability=capability), self.assertRaises(ValueError):
                self.provision((capability,))

    def test_check_missing_only_proposes_creation(self):
        with patch.object(auth, "_read_protected", return_value=None), \
                patch.object(self.config, "ensure_credential") as ensure, \
                patch.object(auth, "_create_pairing") as pairing:
            result = self.provision(("godot", "photoshop"), check=True)
        self.assertEqual({item["state"] for item in result.values()}, {"creation available"})
        ensure.assert_not_called()
        pairing.assert_not_called()

    def test_existing_valid_godot_is_preserved_without_creation(self):
        payload = godot_payload(self.config, self.root)
        with patch.object(auth, "_read_protected", return_value=payload), \
                patch.object(self.config, "ensure_credential") as ensure:
            result = self.provision()
        ensure.assert_not_called()
        self.assertTrue(result["godot"]["ready"])
        self.assertEqual(result["godot"]["state"], "already correct")
        self.assertNotIn("a" * 64, repr(result))

    def test_existing_valid_photoshop_is_preserved_without_creation(self):
        with patch.object(auth, "_read_protected", return_value=b"b" * 64 + b"\n"), \
                patch.object(auth, "_create_pairing") as pairing:
            result = self.provision(("photoshop",))
        pairing.assert_not_called()
        self.assertTrue(result["photoshop"]["ready"])
        self.assertNotIn("b" * 64, repr(result))

    def test_valid_existing_credential_check_never_calls_writer(self):
        with patch.object(auth, "_read_protected", return_value=godot_payload(self.config, self.root)), \
                patch.object(self.config, "ensure_credential") as ensure:
            result = self.provision(check=True)
        ensure.assert_not_called()
        self.assertTrue(result["godot"]["ready"])

    def test_normal_godot_creation_uses_reviewed_writer_once(self):
        with patch.object(auth, "_read_protected", return_value=None), \
                patch.object(auth, "_create_godot", return_value=True) as ensure:
            result = self.provision()
        ensure.assert_called_once_with(self.root, self.security, self.config)
        self.assertEqual(result["godot"]["state"], "created")

    def test_photoshop_creation_preserves_concurrent_existing_token(self):
        with patch.object(auth, "_read_protected", return_value=None), \
                patch.object(auth, "_create_pairing", return_value=False) as pairing:
            result = self.provision(("photoshop",))
        pairing.assert_called_once()
        self.assertEqual(result["photoshop"]["state"], "already correct")

    def test_duplicate_json_and_wrong_binding_fail_without_rotation(self):
        payload = json.loads(godot_payload(self.config, self.root))
        wrong_identity = dict(payload, project_id="0" * 64)
        wrong_path = dict(payload, project_path="unrelated")
        wrong_version = dict(payload, schema_version=True)
        wrong_secret = dict(payload, secret="c" * 63)
        for content in (b'{"schema_version":1,"schema_version":1}',
                        *(json.dumps(item).encode() for item in (wrong_identity, wrong_path, wrong_version, wrong_secret))):
            with self.subTest(content_length=len(content)), \
                    patch.object(auth, "_read_protected", return_value=content), \
                    patch.object(self.config, "ensure_credential") as ensure:
                self.assertFalse(self.provision()["godot"]["ready"])
                ensure.assert_not_called()

    def test_invalid_pairing_token_is_not_repaired(self):
        for content in (b"malformed", b"x" * 131, b"\xff" * 64):
            with self.subTest(content_length=len(content)), \
                    patch.object(auth, "_read_protected", return_value=content), \
                    patch.object(auth, "_create_pairing") as pairing:
                result = self.provision(("photoshop",))
                self.assertFalse(result["photoshop"]["ready"])
                pairing.assert_not_called()

    def test_failure_messages_never_echo_exception_contents(self):
        secret = "test-exception-content-not-a-real-secret"
        with patch.object(auth, "_read_protected", side_effect=ValueError(secret)):
            result = self.provision()
        self.assertNotIn(secret, repr(result))
        self.assertEqual(result["godot"]["state"], "blocked")

    def test_missing_dependencies_do_not_echo_contents(self):
        with patch.object(auth, "_reviewed_modules", side_effect=ValueError("sensitive diagnostic")):
            result = self.provision()
        self.assertNotIn("sensitive diagnostic", repr(result))
        self.assertFalse(result["godot"]["ready"])

    def test_failure_is_capability_local(self):
        with patch.object(auth, "_read_protected", side_effect=[ValueError("unsafe"), b"b" * 64]):
            result = self.provision(("godot", "photoshop"))
        self.assertFalse(result["godot"]["ready"])
        self.assertTrue(result["photoshop"]["ready"])

    def test_missing_art_does_not_touch_pairing_storage(self):
        with patch.object(auth, "_read_protected", return_value=godot_payload(self.config, self.root)) as reader:
            self.provision(("godot",))
        self.assertEqual(reader.call_args.args[1], "godot-auth.json")
        self.assertEqual(reader.call_count, 1)


class IgnoredStorageContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd()

    def test_guard_uses_only_read_only_git_commands_and_checks_ignored_storage(self):
        runner = Mock(side_effect=safe_git)
        auth._guard_storage(self.root, "godot-auth.json", runner)
        commands = [item.args[0] for item in runner.call_args_list]
        self.assertEqual([item[3] for item in commands], ["ls-files", "check-ignore"])
        self.assertEqual(commands[0][-1], "tools/lunitora_mcp/.local")
        self.assertEqual(commands[1][-1], "tools/lunitora_mcp/.local/godot-auth.json")
        self.assertIn("--no-index", commands[1])
        self.assertFalse(any("--global" in command or "config" in command for command in commands))

    def test_tracked_storage_fails_even_if_ignored(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="tracked\0"))
        with self.assertRaises(auth.AuthenticationError):
            auth._guard_storage(self.root, "godot-auth.json", runner)
        self.assertEqual(runner.call_count, 1)

    def test_unignored_storage_is_rejected(self):
        runner = Mock(side_effect=[SimpleNamespace(returncode=0, stdout=""),
                                   SimpleNamespace(returncode=1, stdout="")])
        with self.assertRaises(auth.AuthenticationError):
            auth._guard_storage(self.root, "pairing-token.txt", runner)

    def test_git_inspection_failure_is_rejected(self):
        runner = Mock(return_value=SimpleNamespace(returncode=128, stdout=""))
        with self.assertRaises(auth.AuthenticationError):
            auth._guard_storage(self.root, "godot-auth.json", runner)

    def test_redirects_are_rejected_before_any_git_or_credential_access(self):
        runner = Mock()
        with patch.object(auth, "reject_redirects", side_effect=ValueError("unsafe redirect")), \
                self.assertRaises(ValueError):
            auth._guard_storage(self.root, "godot-auth.json", runner)
        runner.assert_not_called()


@unittest.skipUnless(os.name == "nt", "Native protected Windows storage requires Windows")
class WindowsProtectedStorage(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lunitora phase4 auth spaces ")
        self.root = Path(self.directory.name)
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.config, self.security, self.photoshop = auth._reviewed_modules()
        self.local = self.root / auth.STORAGE
        self.godot = self.local / "godot-auth.json"
        self.pairing = self.local / "pairing-token.txt"

    def tearDown(self):
        self.directory.cleanup()

    def provision(self, names=("godot",), **kwargs):
        return auth.provision_authentication(self.root, "windows", names, runner=safe_git, **kwargs)

    def snapshot(self):
        return {str(path.relative_to(self.root)): (path.stat().st_mtime_ns,
                                                  path.read_bytes() if path.is_file() else None)
                for path in self.root.rglob("*")}

    def test_missing_check_performs_zero_writes_or_directory_creation(self):
        before = self.snapshot()
        with patch.object(self.security, "open_storage", side_effect=AssertionError("writer called")):
            result = self.provision(("godot", "photoshop"), check=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.local.exists())
        self.assertEqual({item["state"] for item in result.values()}, {"creation available"})

    def test_create_godot_credential_and_preserve_bytes_and_timestamp_on_rerun(self):
        first = self.provision()
        self.assertEqual(first["godot"]["state"], "created")
        before = self.snapshot()
        secret = json.loads(self.godot.read_bytes())["secret"]
        second = self.provision()
        self.assertEqual(second["godot"]["state"], "already correct")
        self.assertEqual(self.snapshot(), before)
        self.assertNotIn(secret, repr(first) + repr(second))

    def test_created_files_and_directory_have_reviewed_protected_dacl(self):
        result = self.provision(("godot", "photoshop"))
        self.assertTrue(all(item["ready"] for item in result.values()), result)
        with ExitStack() as stack:
            for path in (self.local, self.godot, self.pairing):
                self.security.validate_acl(self.security.pin(stack, path, directory=path == self.local))

    def test_created_photoshop_token_matches_existing_runtime_format_and_is_preserved(self):
        first = self.provision(("photoshop",))
        self.assertTrue(first["photoshop"]["ready"], first)
        token = self.pairing.read_text(encoding="ascii").strip()
        self.assertTrue(self.photoshop.valid_token(token))
        self.assertEqual(len(token), 64)
        self.assertNotIn(token, repr(first))
        before = self.snapshot()
        self.assertTrue(self.provision(("photoshop",))["photoshop"]["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_existing_credential_check_performs_zero_writes(self):
        self.provision(("godot", "photoshop"))
        before = self.snapshot()
        with patch.object(self.security, "open_storage", side_effect=AssertionError("writer called")), \
                patch.object(self.config, "ensure_credential", side_effect=AssertionError("writer called")), \
                patch.object(auth, "_create_pairing", side_effect=AssertionError("writer called")):
            result = self.provision(("godot", "photoshop"), check=True)
        self.assertTrue(all(item["ready"] for item in result.values()))
        self.assertEqual(self.snapshot(), before)

    def test_live_read_pins_allow_read_only_validation_without_rotation(self):
        self.provision()
        with ExitStack() as stack:
            handle = self.security.pin(stack, self.godot, directory=False)
            self.security.validate_acl(handle)
            before = self.godot.read_bytes()
            result = self.provision()
            self.assertTrue(result["godot"]["ready"])
            self.assertEqual(self.godot.read_bytes(), before)

    def test_missing_file_inside_protected_directory_remains_missing_during_check(self):
        self.provision()
        before = self.snapshot()
        result = self.provision(("photoshop",), check=True)
        self.assertEqual(result["photoshop"]["state"], "creation available")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.pairing.exists())

    def test_permissive_existing_local_directory_is_not_repaired(self):
        self.local.mkdir()
        before = acl_snapshot(self.local)
        for check in (True, False):
            result = self.provision(("godot", "photoshop"), check=check)
            self.assertFalse(any(item["ready"] for item in result.values()))
        after = acl_snapshot(self.local)
        self.assertEqual(before, after)
        self.assertFalse(self.godot.exists())
        self.assertFalse(self.pairing.exists())

    def test_valid_legacy_photoshop_token_in_unsafe_storage_is_preserved(self):
        self.local.mkdir()
        self.pairing.write_bytes(b"p" * 64 + b"\n")
        before = self.snapshot()
        descriptor = acl_snapshot(self.local)
        for check in (True, False):
            result = self.provision(("photoshop",), check=check)
            self.assertFalse(result["photoshop"]["ready"])
            self.assertEqual(set(result), {"photoshop"})
        self.assertEqual(self.snapshot(), before)
        after = acl_snapshot(self.local)
        self.assertEqual(descriptor, after)

    def test_broadened_file_dacl_is_not_repaired(self):
        self.provision()
        broaden_disposable_acl(self.godot)
        before = acl_snapshot(self.godot)
        payload = self.godot.read_bytes()
        for check in (True, False):
            self.assertFalse(self.provision(check=check)["godot"]["ready"])
        after = acl_snapshot(self.godot)
        self.assertEqual(before, after)
        self.assertEqual(payload, self.godot.read_bytes())

    def test_malformed_credentials_are_preserved_not_rotated(self):
        self.provision(("godot", "photoshop"))
        self.godot.write_bytes(b"{}")
        self.pairing.write_bytes(b"malformed")
        before = self.snapshot()
        for check in (True, False):
            result = self.provision(("godot", "photoshop"), check=check)
            self.assertFalse(any(item["ready"] for item in result.values()))
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_project_fields_are_rejected_read_only(self):
        self.provision()
        self.godot.write_bytes(b'{"schema_version":1,"schema_version":1}')
        before = self.snapshot()
        self.assertFalse(self.provision(check=True)["godot"]["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_hard_linked_file_is_rejected_without_modification(self):
        self.provision()
        os.link(self.godot, self.root / "alias.json")
        before = self.snapshot()
        self.assertFalse(self.provision()["godot"]["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_junction_storage_is_rejected_without_touching_target(self):
        target = self.root / "target"
        target.mkdir()
        sentinel = target / "sentinel"
        sentinel.write_bytes(b"preserve")
        subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(self.local), str(target)],
                       check=True, capture_output=True)
        try:
            for check in (True, False):
                self.assertFalse(self.provision(check=check)["godot"]["ready"])
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            self.assertFalse((target / "godot-auth.json").exists())
        finally:
            os.rmdir(self.local)

    def test_tracked_or_unignored_storage_fails_before_secret_creation(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="tracked\0"))
        result = auth.provision_authentication(self.root, "windows", ("godot",), runner=runner)
        self.assertFalse(result["godot"]["ready"])
        self.assertFalse(self.local.exists())


if __name__ == "__main__":
    unittest.main()
