"""Protected disposable credential storage contracts, without MCP dependencies."""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lunitora_machine import native_credentials as storage


class NativeCredentialContracts(unittest.TestCase):
    def test_errors_do_not_expose_paths_or_payloads(self):
        self.assertEqual(str(storage.StorageError()), "Local authentication storage is unsafe or unavailable.")
        error = storage._StorageOSError(32)
        self.assertEqual(error.winerror, 32)
        self.assertEqual(str(error), "Local authentication storage is unavailable.")

    def test_close_is_idempotent(self):
        native = Mock()
        handle = storage._Handle(44, native)
        handle.Close()
        handle.Close()
        native.kernel.CloseHandle.assert_called_once_with(44)

    def test_closed_handle_cannot_be_reused(self):
        with self.assertRaises(storage.StorageError):
            storage._handle(storage._Handle(None, Mock()))

    def test_pin_preserves_share_and_reparse_contract(self):
        handle, stack = Mock(), Mock()
        info = [0, 0, 0, 0, 0, 0, 4, 1, 0, 0]
        with patch.object(storage._FILE, "CreateFile", return_value=handle) as create, \
                patch.object(storage._FILE, "GetFileInformationByHandle", return_value=info):
            self.assertIs(storage.pin(stack, Path("proof.txt"), directory=False), handle)
        arguments = create.call_args.args
        self.assertEqual(arguments[1], storage._CON.GENERIC_READ | storage._NT.READ_CONTROL)
        self.assertEqual(arguments[2], storage._CON.FILE_SHARE_READ)
        self.assertIsNone(arguments[3])
        self.assertEqual(arguments[4:6], (storage._CON.OPEN_EXISTING, 0x00200000))
        stack.callback.assert_called_once_with(handle.Close)

    def test_pin_rejects_links_wrong_type_and_large_payloads(self):
        for attributes, size_high, size, links in ((0x400, 0, 1, 1), (0x10, 0, 1, 1),
                                                   (0, 0, 1, 2), (0, 1, 0, 1), (0, 0, 4097, 1)):
            with self.subTest(attributes=attributes, size=size, links=links):
                info = [attributes, 0, 0, 0, 0, size_high, size, links, 0, 0]
                with patch.object(storage._FILE, "CreateFile", return_value=Mock()), \
                        patch.object(storage._FILE, "GetFileInformationByHandle", return_value=info):
                    with self.assertRaises(storage.StorageError):
                        storage.pin(Mock(), Path("proof.txt"), directory=False)

    def test_write_bounds_reject_before_native_call(self):
        with patch.object(storage, "_native") as native:
            for payload in (b"", b"x" * 4097, "not bytes"):
                with self.assertRaises(storage.StorageError):
                    storage._FILE.WriteFile(1, payload)
        native.assert_not_called()

    def test_read_bounds_reject_before_native_call(self):
        with patch.object(storage, "_native") as native:
            for size in (0, -1, 4098, True):
                with self.assertRaises(storage.StorageError):
                    storage._FILE.ReadFile(1, size)
        native.assert_not_called()

    def test_partial_write_is_rejected(self):
        with patch.object(storage._FILE, "WriteFile", return_value=(0, 2)), \
                patch.object(storage._FILE, "FlushFileBuffers") as flush:
            with self.assertRaises(storage.StorageError):
                storage.write_storage(1, b"proof")
        flush.assert_not_called()

    def test_empty_and_oversized_read_is_rejected(self):
        with patch.object(storage._FILE, "SetFilePointer"):
            for payload in (b"", b"x" * 4097):
                with patch.object(storage._FILE, "ReadFile", return_value=(0, payload)):
                    with self.assertRaises(storage.StorageError):
                        storage.read_storage(1)


@unittest.skipUnless(os.name == "nt", "Requires Windows protected storage")
class NativeCredentialDisposable(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lunitora-native-storage-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Project With Spaces"
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.file = self.root / "tools/lunitora_mcp/.local/godot-auth.json"
        self.payload = b'{"disposable_proof":true}\n'

    def create(self):
        stack, handle, created = storage.open_storage(self.root)
        with stack:
            self.assertTrue(created)
            storage.write_storage(handle, self.payload)

    def test_protected_creation_and_unchanged_read_only_reopen(self):
        self.create()
        before = self.file.stat().st_mtime_ns
        stack, handle, created = storage.open_storage(self.root)
        with stack:
            self.assertFalse(created)
            storage.validate_acl(handle)
            self.assertEqual(storage.read_storage(handle), self.payload)
        self.assertEqual(self.file.stat().st_mtime_ns, before)

    def test_pinned_storage_denies_other_write_handles(self):
        self.create()
        with ExitStack() as stack:
            handle = storage.pin(stack, self.file, directory=False)
            storage.validate_acl(handle)
            with self.assertRaises(storage._StorageOSError) as error:
                storage._FILE.CreateFile(str(self.file), storage._CON.GENERIC_WRITE, 1, None, 3, 0x00200000, None)
            self.assertEqual(error.exception.winerror, 32)
            self.assertEqual(storage.read_storage(handle), self.payload)

    def test_empty_protected_file_is_invalid(self):
        stack, handle, created = storage.open_storage(self.root)
        with stack:
            self.assertTrue(created)
            with self.assertRaises(storage.StorageError):
                storage.read_storage(handle)

    def test_unprotected_local_directory_is_rejected_without_acl_repair(self):
        local = self.file.parent
        local.mkdir()
        before = local.stat().st_mtime_ns
        with self.assertRaises(storage.StorageError):
            storage.open_storage(self.root)
        self.assertEqual(local.stat().st_mtime_ns, before)
        self.assertFalse(self.file.exists())

    def test_unprotected_existing_file_is_rejected_without_replacement(self):
        storage._FILE.CreateDirectory(str(self.file.parent), storage.protected_attributes(directory=True))
        self.file.write_bytes(self.payload)
        before = self.file.stat().st_mtime_ns
        with self.assertRaises(storage.StorageError):
            storage.open_storage(self.root)
        self.assertEqual(self.file.read_bytes(), self.payload)
        self.assertEqual(self.file.stat().st_mtime_ns, before)

    def test_hardlink_is_rejected(self):
        self.create()
        alias = self.file.parent / "alias-proof.json"
        os.link(self.file, alias)
        with self.assertRaises(storage.StorageError):
            storage.open_storage(self.root)
        self.assertEqual(self.file.read_bytes(), self.payload)

    def test_exact_protected_owner_two_ace_contract(self):
        attributes = storage.protected_attributes(directory=True)
        descriptor, acl, user, system = attributes._keepalive
        native = storage._native()
        current, local_system = native.identity()
        self.assertEqual(user.raw[:-1], current)
        self.assertEqual(system.raw[:-1], local_system)
        self.assertTrue(descriptor.control & 0x1000)
        header = storage._ACL.from_buffer(acl)
        self.assertEqual(header.count, 2)
        for index in range(2):
            pointer = ctypes.c_void_p()
            self.assertTrue(native.security.GetAce(acl, index, ctypes.byref(pointer)))
            ace = ctypes.cast(pointer, ctypes.POINTER(storage._ACE)).contents
            self.assertEqual((ace.type, ace.flags, ace.mask), (0, 3, storage._NT.FILE_ALL_ACCESS))

    def test_extra_ace_is_rejected(self):
        attributes = storage.protected_attributes(directory=False)
        descriptor, acl, user, system = attributes._keepalive
        native = storage._native()
        world = ctypes.create_string_buffer(68)
        size = ctypes.wintypes.DWORD(len(world))
        self.assertTrue(native.security.CreateWellKnownSid(1, None, world, ctypes.byref(size)))
        large_acl = ctypes.create_string_buffer(len(acl) + size.value + 8)
        self.assertTrue(native.security.InitializeAcl(large_acl, len(large_acl), 2))
        for sid in (user, system):
            self.assertTrue(native.security.AddAccessAllowedAceEx(large_acl, 2, 0, storage._NT.FILE_ALL_ACCESS, sid))
        self.assertTrue(native.security.AddAccessAllowedAceEx(large_acl, 2, 0, storage._NT.READ_CONTROL, world))
        self.assertTrue(native.security.SetSecurityDescriptorDacl(ctypes.byref(descriptor), True, large_acl, False))
        attributes._keepalive = descriptor, large_acl, user, system, world
        with ExitStack() as stack:
            handle = storage._FILE.CreateFile(str(self.file.parent.parent / "extra-ace.txt"),
                                              storage._CON.GENERIC_READ, 1, attributes, 1, 0x00200000, None)
            stack.callback(handle.Close)
            with self.assertRaises(storage.StorageError):
                storage.validate_acl(handle)

    def test_storage_roundtrip_without_site_packages_or_pywin32(self):
        tools = str(Path(__file__).resolve().parents[1])
        script = (
            "import builtins, pathlib, sys; sys.path.insert(0, " + repr(tools) + ")\n"
            "original = builtins.__import__\n"
            "def guard(name, *args, **kwargs):\n"
            "    if name.split('.')[0] in ('win32api','win32con','win32file','win32security','ntsecuritycon','pythoncom','mcp','websockets','tomlkit'):\n"
            "        raise AssertionError('Host credential storage imported an MCP dependency')\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = guard\n"
            "from lunitora_machine import native_credentials as storage\n"
            "root = pathlib.Path(" + repr(str(self.root)) + ")\n"
            "stack, handle, created = storage.open_storage(root)\n"
            "with stack:\n"
            "    assert created\n"
            "    storage.write_storage(handle, b'disposable protected storage proof')\n"
            "stack, handle, created = storage.open_storage(root)\n"
            "with stack:\n"
            "    assert not created\n"
            "    assert storage.read_storage(handle) == b'disposable protected storage proof'\n"
            "print('stdlib-only protected storage: OK')\n"
        )
        result = subprocess.run([getattr(sys, "_base_executable", sys.executable), "-I", "-S", "-B", "-c", script],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "stdlib-only protected storage: OK")

    def test_reviewed_mcp_storage_and_host_storage_are_interoperable(self):
        toolkit = Path(__file__).resolve().parents[1] / "lunitora_mcp"
        interpreter = toolkit / ".venv/Scripts/python.exe"
        if not interpreter.is_file():
            self.skipTest("Reviewed MCP dependency environment is unavailable for separate interoperability proof")
        self.create()
        runtime_root = self.root.parent / "Reviewed Runtime Fixture"
        (runtime_root / "tools/lunitora_mcp").mkdir(parents=True)
        script = (
            "import pathlib, sys; sys.path.insert(0, " + repr(str(toolkit)) + ")\n"
            "try: import win32security\n"
            "except ImportError: sys.exit(77)\n"
            "from modules.godot import security\n"
            "stack, handle, created = security.open_storage(pathlib.Path(" + repr(str(self.root)) + "))\n"
            "with stack:\n"
            "    assert not created\n"
            "    assert security.read_storage(handle) == b'{\"disposable_proof\":true}\\n'\n"
            "stack, handle, created = security.open_storage(pathlib.Path(" + repr(str(runtime_root)) + "))\n"
            "with stack:\n"
            "    assert created\n"
            "    security.write_storage(handle, b'reviewed runtime disposable proof')\n"
            "print('reviewed runtime storage interoperability: OK')\n"
        )
        result = subprocess.run([str(interpreter), "-I", "-B", "-c", script],
                                capture_output=True, text=True, timeout=30)
        if result.returncode == 77:
            self.skipTest("Reviewed MCP pywin32 is unavailable for separate interoperability proof")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "reviewed runtime storage interoperability: OK")
        stack, handle, created = storage.open_storage(runtime_root)
        with stack:
            self.assertFalse(created)
            self.assertEqual(storage.read_storage(handle), b"reviewed runtime disposable proof")


if __name__ == "__main__":
    unittest.main()
