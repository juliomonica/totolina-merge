"""Host-Python COM contracts and read-only Windows proofs without site packages."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lunitora_machine.policy import LauncherError
from lunitora_machine.platforms import windows_com as com


class _Dispatch(com.RawDispatch):
    def __init__(self, invoke):
        self.api, self.apartment, self.pointer = Mock(), object(), 1
        self.invoke = invoke

    def _method(self, index, result, *arguments):
        if index != 6:
            raise AssertionError("Unexpected interface method")
        return self.invoke

    def close(self):
        self.pointer = None


class HostCOMContracts(unittest.TestCase):
    def test_variant_has_native_windows_automation_layout(self):
        if os.name == "nt":
            self.assertEqual(ctypes.sizeof(com._Variant), 24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 16)
            self.assertEqual(com._Variant.value.offset, 8)

    def test_guid_preserves_windows_byte_order(self):
        self.assertEqual(bytes(com._DISPATCH).hex(), "0004020000000000c000000000000046")

    def test_hresult_error_is_redacted(self):
        with self.assertRaisesRegex(LauncherError, "Windows COM inspection failed") as raised:
            com._check(-2147024891)
        self.assertNotIn("2147024891", str(raised.exception))

    def test_success_hresult_is_accepted(self):
        for status in (0, 1):
            com._check(status)

    def test_invalid_property_rejected_without_native_call(self):
        dispatch = object.__new__(com.RawDispatch)
        for name in (None, "", "bad\x00name", "x" * 1025):
            with self.assertRaisesRegex(LauncherError, "Invalid COM inspection property"):
                dispatch._identifier(name)

    def test_closed_interface_is_not_dereferenced(self):
        dispatch = object.__new__(com.RawDispatch)
        dispatch.pointer = None
        with self.assertRaisesRegex(LauncherError, "closed"):
            dispatch._method(1, w.ULONG)

    def test_invalid_enumeration_bounds_fail_before_invoke(self):
        dispatch = object.__new__(com.RawDispatch)
        for limit in (-1, 65537, True, "1"):
            with self.assertRaisesRegex(LauncherError, "safety bound"):
                list(dispatch.items(limit))

    def test_invoke_reverses_arguments_and_preserves_flags(self):
        def invoke(identifier, iid, locale, flags, parameters, result, exception, argument_error):
            args = ctypes.cast(parameters, ctypes.POINTER(com._Arguments)).contents
            self.assertEqual((identifier, locale, flags, args.count, args.named_count), (44, 0, 1, 2, 0))
            self.assertEqual([args.values[i].long for i in range(2)], [2, 1])
            return 0
        dispatch = _Dispatch(invoke)
        dispatch.api.argument.side_effect = lambda value: com._Variant(kind=3, value=com._Value(long=value))
        dispatch.api.value.return_value = "result"
        self.assertEqual(dispatch._invoke(44, 1, (1, 2)), "result")
        self.assertEqual(dispatch.api.auto.VariantClear.call_count, 3)

    def test_invoke_failure_clears_all_variants_and_redacts(self):
        dispatch = _Dispatch(lambda *args: -2147024891)
        dispatch.api.argument.side_effect = lambda value: com._Variant(kind=3, value=com._Value(long=value))
        with self.assertRaisesRegex(LauncherError, "COM inspection failed"):
            dispatch._invoke(44, 1, (1, 2))
        self.assertEqual(dispatch.api.auto.VariantClear.call_count, 3)
        dispatch.api.value.assert_not_called()

    def test_argument_failure_clears_previous_allocations(self):
        dispatch = _Dispatch(Mock())
        dispatch.api.argument.side_effect = [com._Variant(kind=8), LauncherError("Unsupported")]
        with self.assertRaisesRegex(LauncherError, "Unsupported"):
            dispatch._invoke(44, 1, (1, 2))
        self.assertEqual(dispatch.api.auto.VariantClear.call_count, 3)
        dispatch.invoke.assert_not_called()

    def test_invoke_exception_descriptions_are_freed_not_emitted(self):
        def invoke(identifier, iid, locale, flags, parameters, result, exception, argument_error):
            fields = ctypes.cast(exception, ctypes.POINTER(com._Exception)).contents
            fields.source, fields.description, fields.help = 17, 18, 19
            return -2147352567
        dispatch = _Dispatch(invoke)
        with self.assertRaisesRegex(LauncherError, "COM inspection failed"):
            dispatch._invoke(44, 1)
        self.assertEqual([call.args[0] for call in dispatch.api.auto.SysFreeString.call_args_list], [17, 18, 19])

    def test_excess_arguments_fail_before_allocation(self):
        dispatch = _Dispatch(Mock())
        with self.assertRaisesRegex(LauncherError, "safety bound"):
            dispatch._invoke(44, 1, tuple(range(65)))
        dispatch.api.argument.assert_not_called()
        dispatch.invoke.assert_not_called()

    def test_missing_enumerator_fails_closed(self):
        dispatch = _Dispatch(Mock())
        dispatch._invoke = Mock(return_value=None)
        with self.assertRaisesRegex(LauncherError, "enumeration interface"):
            list(dispatch.items())

    def test_overlong_string_not_dereferenced(self):
        api = object.__new__(com._Automation)
        api.auto = Mock()
        api.auto.SysStringLen.return_value = 1_048_577
        with self.assertRaisesRegex(LauncherError, "safety bounds"):
            api.value(com._Variant(kind=8, value=com._Value(pointer=1)), object())

    def test_unsupported_variant_fails_closed(self):
        api = object.__new__(com._Automation)
        for kind in (7, 10, 12, 0x2008, 0x4008):
            with self.assertRaisesRegex(LauncherError, "Unsupported COM inspection value"):
                api.value(com._Variant(kind=kind), object())

    def test_scalar_variants_do_not_require_third_party_conversion(self):
        api = object.__new__(com._Automation)
        for kind, field, value in ((2, "short", -4), (3, "long", -42), (16, "byte", -3),
                                    (20, "integer", -(2 ** 40)), (21, "unsigned", 2 ** 40)):
            with self.subTest(kind=kind):
                item = com._Variant(kind=kind)
                setattr(item, field, value)
                self.assertEqual(api.value(item, object()), value)
        self.assertIsNone(api.value(com._Variant(kind=1), object()))
        self.assertTrue(api.value(com._Variant(kind=11, value=com._Value(short=-1)), object()))

    def test_argument_types_and_bounds_are_fail_closed(self):
        api = object.__new__(com._Automation)
        api.auto = Mock()
        for value in (1.0, object(), 2 ** 31, -(2 ** 31) - 1, "bad\x00value", "a" * 1_048_577):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(LauncherError):
                    api.argument(value)
        api.auto.SysAllocStringLen.assert_not_called()

    def test_string_allocation_uses_utf16_code_units(self):
        api = object.__new__(com._Automation)
        api.auto = Mock()
        api.auto.SysAllocStringLen.return_value = 1
        text = "app-" + chr(0x1F4BB)
        api.argument(text)
        api.auto.SysAllocStringLen.assert_called_once_with(text, 6)

    def test_string_allocation_failure_does_not_return_null_bstr(self):
        api = object.__new__(com._Automation)
        api.auto = Mock()
        api.auto.SysAllocStringLen.return_value = None
        with self.assertRaisesRegex(LauncherError, "allocation failed"):
            api.argument("safe")


@unittest.skipUnless(os.name == "nt", "Requires Windows native APIs")
class HostWindowsReadOnlyNative(unittest.TestCase):
    def test_native_bstr_preserves_spaces_and_astral_unicode(self):
        api = com._automation()
        text = "C:\\Program Files\\" + chr(0x1F4BB) + "\\Codex.exe"
        value = api.argument(text)
        try:
            self.assertEqual(api.value(value, api.apartment()), text)
        finally:
            api.auto.VariantClear(ctypes.byref(value))

    def test_read_only_apps_and_process_proof_without_site_or_venv_packages(self):
        tools = str(Path(__file__).resolve().parents[1])
        script = (
            "import builtins, os, sys; sys.path.insert(0, " + repr(tools) + ")\n"
            "original = builtins.__import__\n"
            "def guard(name, *args, **kwargs):\n"
            "    if name.split('.')[0] in ('pythoncom','win32com','win32api','mcp','websockets','tomlkit'):\n"
            "        raise AssertionError('Host runtime imported an MCP dependency')\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = guard\n"
            "from lunitora_machine.platforms.windows import WindowsPlatform, _api, _same_path\n"
            "platform = WindowsPlatform()\n"
            "own = [item for item in platform.processes() if item.pid == os.getpid()]\n"
            "assert len(own) == 1 and own[0].command_line and own[0].created\n"
            "native = _api(); handle = native.kernel.OpenProcess(0x1000, False, os.getpid())\n"
            "assert handle\n"
            "try:\n"
            "    created, image = native.process_identity(handle)\n"
            "    assert created == own[0].created and _same_path(image, own[0].executable)\n"
            "finally: native.kernel.CloseHandle(handle)\n"
            "apps = platform._apps_folder()\n"
            "assert apps and all(set(app) == {'aumid','name'} for app in apps)\n"
            "print('stdlib-only read-only Windows adapter: OK')\n"
        )
        result = subprocess.run([getattr(sys, "_base_executable", sys.executable), "-I", "-S", "-B", "-c", script],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "stdlib-only read-only Windows adapter: OK")


if __name__ == "__main__":
    unittest.main()
