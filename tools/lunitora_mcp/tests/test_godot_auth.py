"""Disposable Windows storage tests. Real workstation credentials are never read."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from modules.godot.config import Config, ConfigurationError, ensure_credential, project_identity
from modules.godot.security import StorageError, pin, protected_attributes, validate_acl


class ConfigurationTests(unittest.TestCase):
    def test_timeouts_are_finite_bounded_numbers(self):
        for value in (False, "5", None, 0, 31, float("nan"), float("inf")):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ConfigurationError):
                Config(request_timeout_seconds=value)
        Config(request_timeout_seconds=0.05, authentication_timeout_seconds=30)

    def test_project_identity_is_canonical_and_path_bound(self):
        first, identity = project_identity(Path.cwd())
        self.assertEqual(identity, hashlib.sha256(first.encode()).hexdigest())
        self.assertNotEqual(identity, project_identity(Path.cwd() / "another-project")[1])
        if os.name == "nt":
            self.assertEqual(first, first.lower())
            self.assertNotIn("\\", first)


@unittest.skipUnless(os.name == "nt", "Native Windows ACL and reparse protection")
class CredentialStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lunitora-godot-auth-test-")
        self.root = Path(self.directory.name)
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.path = self.root / "tools/lunitora_mcp/.local/godot-auth.json"

    def tearDown(self):
        self.directory.cleanup()

    def test_automatic_secret_is_256_bit_and_hidden_from_repr(self):
        with ensure_credential(self.root) as credential:
            self.assertEqual(len(credential.secret), 32)
            self.assertTrue(credential.secret.hex() not in repr(credential))
            self.assertTrue(self.path.is_file())

    def test_existing_credential_is_preserved_and_concurrent_readers_work(self):
        with ensure_credential(self.root) as first:
            before = self.path.read_bytes()
            with ensure_credential(self.root) as second:
                self.assertTrue(first.secret == second.secret)
                self.assertTrue(before == self.path.read_bytes())
        with ensure_credential(self.root) as third:
            self.assertTrue(before == self.path.read_bytes())

    def test_file_and_directory_have_protected_user_system_acls(self):
        with ensure_credential(self.root), ExitStack() as stack:
            validate_acl(pin(stack, self.path, directory=False))
            validate_acl(pin(stack, self.path.parent, directory=True))

    def test_pinned_file_denies_mutation(self):
        with ensure_credential(self.root):
            with self.assertRaises(OSError):
                self.path.write_bytes(b"untrusted")
            with self.assertRaises(OSError):
                self.path.rename(self.path.with_suffix(".moved"))

    def test_malformed_credential_is_not_repaired_or_rotated(self):
        with ensure_credential(self.root):
            pass
        self.path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            ensure_credential(self.root)
        self.assertEqual(self.path.read_text(), "{}")

    def test_wrong_project_binding_is_rejected(self):
        with ensure_credential(self.root):
            pass
        data = json.loads(self.path.read_text())
        data["project_id"] = "0" * 64
        self.path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            ensure_credential(self.root)

    def test_oversized_and_duplicate_field_storage_is_rejected(self):
        with ensure_credential(self.root):
            pass
        for content in ("x" * 4097, '{"schema_version":1,"schema_version":1}'):
            self.path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                ensure_credential(self.root)

    def test_permissive_existing_local_directory_is_not_changed(self):
        self.path.parent.mkdir()
        import win32security
        before = win32security.GetFileSecurity(str(self.path.parent), win32security.DACL_SECURITY_INFORMATION)
        with self.assertRaises(ConfigurationError):
            ensure_credential(self.root)
        after = win32security.GetFileSecurity(str(self.path.parent), win32security.DACL_SECURITY_INFORMATION)
        self.assertEqual(bytes(before), bytes(after))
        self.assertFalse(self.path.exists())

    def test_broadened_file_acl_is_rejected_without_repair(self):
        with ensure_credential(self.root):
            pass
        import win32security
        import ntsecuritycon
        descriptor = win32security.GetFileSecurity(str(self.path), win32security.DACL_SECURITY_INFORMATION)
        acl = descriptor.GetSecurityDescriptorDacl()
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_GENERIC_READ,
                               win32security.CreateWellKnownSid(win32security.WinWorldSid, None))
        win32security.SetNamedSecurityInfo(str(self.path), win32security.SE_FILE_OBJECT,
                                         win32security.DACL_SECURITY_INFORMATION, None, None, acl, None)
        with self.assertRaises(ConfigurationError):
            ensure_credential(self.root)

    def test_hard_linked_credential_is_rejected(self):
        with ensure_credential(self.root):
            pass
        os.link(self.path, self.root / "alias.json")
        with self.assertRaises(ConfigurationError):
            ensure_credential(self.root)

    def test_junction_ancestor_is_rejected_without_reading_target(self):
        target = self.root / "target"
        target.mkdir()
        sentinel = target / "sentinel"
        sentinel.write_text("preserve")
        junction = self.root / "tools/lunitora_mcp/.local"
        subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(target)],
                       check=True, capture_output=True)
        try:
            with self.assertRaises(ConfigurationError):
                ensure_credential(self.root)
            self.assertEqual(sentinel.read_text(), "preserve")
            self.assertFalse((target / "godot-auth.json").exists())
        finally:
            os.rmdir(junction)


if __name__ == "__main__":
    unittest.main()
