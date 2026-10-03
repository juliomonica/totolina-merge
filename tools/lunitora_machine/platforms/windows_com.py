"""Bounded Windows COM automation using only ctypes, without generated clients."""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import os
import threading
import uuid

from ..policy import LauncherError


class _GUID(ctypes.Structure):
    _fields_ = [("data1", w.DWORD), ("data2", w.WORD), ("data3", w.WORD),
                ("data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


_NULL = _GUID()
_DISPATCH = _GUID.parse("00020400-0000-0000-C000-000000000046")
_ENUM = _GUID.parse("00020404-0000-0000-C000-000000000046")


class _Record(ctypes.Structure):
    _fields_ = [("record", ctypes.c_void_p), ("info", ctypes.c_void_p)]


class _Value(ctypes.Union):
    _fields_ = [("integer", ctypes.c_longlong), ("unsigned", ctypes.c_ulonglong),
                ("long", w.LONG), ("short", ctypes.c_short), ("byte", ctypes.c_byte),
                ("double", ctypes.c_double), ("single", ctypes.c_float),
                ("pointer", ctypes.c_void_p), ("record", _Record)]


class _Variant(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("kind", w.WORD), ("reserved1", w.WORD), ("reserved2", w.WORD),
                ("reserved3", w.WORD), ("value", _Value)]


class _Arguments(ctypes.Structure):
    _fields_ = [("values", ctypes.POINTER(_Variant)), ("names", ctypes.POINTER(w.LONG)),
                ("count", w.UINT), ("named_count", w.UINT)]


class _Exception(ctypes.Structure):
    _fields_ = [("code", w.WORD), ("reserved", w.WORD), ("source", ctypes.c_void_p),
                ("description", ctypes.c_void_p), ("help", ctypes.c_void_p),
                ("context", w.DWORD), ("reserved_pointer", ctypes.c_void_p),
                ("deferred", ctypes.c_void_p), ("status", w.LONG)]


def _check(status):
    if status < 0:
        raise LauncherError("Windows COM inspection failed; refusing an unsafe fallback.")


class _Apartment:
    def __init__(self, api):
        self.api = api
        self.thread = threading.get_ident()
        result = api.ole.CoInitializeEx(None, 2)
        if result not in (0, 1, -2147417850):  # Existing different apartment is usable.
            _check(result)
        self.owned = result in (0, 1)

    def __del__(self):
        if getattr(self, "owned", False) and self.thread == threading.get_ident():
            self.api.ole.CoUninitialize()


class _Automation:
    def __init__(self):
        if os.name != "nt":
            raise LauncherError("Windows COM inspection requires Windows.")
        self.ole = ctypes.WinDLL("ole32", use_last_error=True, winmode=0x800)
        self.auto = ctypes.WinDLL("oleaut32", use_last_error=True, winmode=0x800)
        self.local = threading.local()
        p = ctypes.c_void_p
        def bind(dll, name, args, result):
            method = getattr(dll, name)
            method.argtypes, method.restype = args, result
        bind(self.ole, "CoInitializeEx", [p, w.DWORD], w.LONG)
        bind(self.ole, "CoUninitialize", [], None)
        bind(self.ole, "CLSIDFromProgID", [w.LPCWSTR, ctypes.POINTER(_GUID)], w.LONG)
        bind(self.ole, "CoCreateInstance", [ctypes.POINTER(_GUID), p, w.DWORD,
                                           ctypes.POINTER(_GUID), ctypes.POINTER(p)], w.LONG)
        bind(self.ole, "CoGetObject", [w.LPCWSTR, p, ctypes.POINTER(_GUID), ctypes.POINTER(p)], w.LONG)
        bind(self.auto, "SysAllocStringLen", [w.LPCWSTR, w.UINT], p)
        bind(self.auto, "SysStringLen", [p], w.UINT)
        bind(self.auto, "SysFreeString", [p], None)
        bind(self.auto, "VariantClear", [ctypes.POINTER(_Variant)], w.LONG)

    def apartment(self):
        if not hasattr(self.local, "apartment"):
            self.local.apartment = _Apartment(self)
        return self.local.apartment

    def create(self, name, *, moniker=False):
        apartment = self.apartment()
        pointer = ctypes.c_void_p()
        if moniker:
            status = self.ole.CoGetObject(name, None, ctypes.byref(_DISPATCH), ctypes.byref(pointer))
        else:
            clsid = _GUID()
            _check(self.ole.CLSIDFromProgID(name, ctypes.byref(clsid)))
            status = self.ole.CoCreateInstance(ctypes.byref(clsid), None, 21,
                                               ctypes.byref(_DISPATCH), ctypes.byref(pointer))
        _check(status)
        if not pointer.value:
            raise LauncherError("Windows COM returned no inspection interface.")
        return RawDispatch(pointer.value, api=self, apartment=apartment)

    def argument(self, value):
        item = _Variant()
        if value is None:
            return item
        if isinstance(value, str):
            if len(value) > 1_048_576 or "\x00" in value:
                raise LauncherError("COM string exceeds its safety bounds.")
            units = len(value.encode("utf-16-le", errors="surrogatepass")) // 2
            item.kind, item.pointer = 8, self.auto.SysAllocStringLen(value, units)
            if not item.pointer:
                raise LauncherError("Windows COM string allocation failed.")
        elif type(value) is bool:
            item.kind, item.short = 11, -1 if value else 0
        elif type(value) is int and -(2 ** 31) <= value < 2 ** 31:
            item.kind, item.long = 3, value
        else:
            raise LauncherError("Unsupported COM inspection argument.")
        return item

    def value(self, item, apartment):
        kind = item.kind
        if kind in (0, 1):
            return None
        if kind == 8:
            if not item.pointer:
                return ""
            size = self.auto.SysStringLen(item.pointer)
            if size > 1_048_576:
                raise LauncherError("COM string exceeds its safety bounds.")
            return ctypes.wstring_at(item.pointer, size)
        if kind == 11:
            return item.short != 0
        if kind in (2, 3, 16, 17, 18, 19, 20, 21, 22, 23):
            types = {2: ctypes.c_short, 3: w.LONG, 16: ctypes.c_byte, 17: ctypes.c_ubyte,
                     18: w.WORD, 19: w.DWORD, 20: ctypes.c_longlong,
                     21: ctypes.c_ulonglong, 22: ctypes.c_int, 23: ctypes.c_uint}
            return ctypes.cast(ctypes.byref(item.value), ctypes.POINTER(types[kind])).contents.value
        if kind in (4, 5):
            return item.single if kind == 4 else item.double
        if kind in (9, 13) and item.pointer:
            result = (RawDispatch if kind == 9 else _Unknown)(item.pointer, api=self, apartment=apartment)
            result._method(1, w.ULONG)()  # The returned VARIANT retains its own reference.
            return result
        raise LauncherError("Unsupported COM inspection value; refusing to guess.")


_AUTOMATION = None


def _automation():
    global _AUTOMATION
    if _AUTOMATION is None:
        _AUTOMATION = _Automation()
    return _AUTOMATION


class _Unknown:
    def __init__(self, pointer, *, api=None, apartment=None):
        self.api = _automation() if api is None else api
        self.apartment = self.api.apartment() if apartment is None else apartment
        if isinstance(pointer, _Unknown):
            if not pointer.pointer:
                raise LauncherError("Windows COM interface is unavailable.")
            self.pointer = pointer.pointer
            self._method(1, w.ULONG)()
        else:
            self.pointer = int(pointer or 0)
        if not self.pointer:
            raise LauncherError("Windows COM interface is unavailable.")

    def _method(self, index, result, *args):
        if not self.pointer:
            raise LauncherError("Windows COM interface is closed.")
        table = ctypes.cast(self.pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        function = ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *args)(table[index])
        return lambda *values: function(self.pointer, *values)

    def query(self, interface, cls):
        pointer = ctypes.c_void_p()
        _check(self._method(0, w.LONG, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
            ctypes.byref(interface), ctypes.byref(pointer)))
        return cls(pointer.value, api=self.api, apartment=self.apartment)

    def close(self):
        if getattr(self, "pointer", None):
            self._method(2, w.ULONG)()
            self.pointer = None

    def __del__(self):
        self.close()


class RawDispatch(_Unknown):
    def _invoke(self, identifier, flags, arguments=()):
        if len(arguments) > 64:
            raise LauncherError("COM arguments exceed their safety bound.")
        values = (_Variant * len(arguments))()
        result, exception, argument_error = _Variant(), _Exception(), w.UINT()
        try:
            for index, value in enumerate(reversed(arguments)):
                values[index] = self.api.argument(value)
            parameters = _Arguments(values, None, len(values), 0)
            status = self._method(6, w.LONG, w.LONG, ctypes.POINTER(_GUID), w.DWORD, w.WORD,
                                  ctypes.POINTER(_Arguments), ctypes.POINTER(_Variant),
                                  ctypes.POINTER(_Exception), ctypes.POINTER(w.UINT))(
                identifier, ctypes.byref(_NULL), 0, flags, ctypes.byref(parameters),
                ctypes.byref(result), ctypes.byref(exception), ctypes.byref(argument_error))
            _check(status)
            return self.api.value(result, self.apartment)
        finally:
            self.api.auto.VariantClear(ctypes.byref(result))
            for value in values:
                self.api.auto.VariantClear(ctypes.byref(value))
            for value in (exception.source, exception.description, exception.help):
                if value:
                    self.api.auto.SysFreeString(value)

    def _identifier(self, name):
        if not isinstance(name, str) or not name or "\x00" in name or len(name) > 1024:
            raise LauncherError("Invalid COM inspection property.")
        names, identifier = (w.LPWSTR * 1)(name), w.LONG()
        _check(self._method(5, w.LONG, ctypes.POINTER(_GUID), ctypes.POINTER(w.LPWSTR),
                            w.UINT, w.DWORD, ctypes.POINTER(w.LONG))(
            ctypes.byref(_NULL), names, 1, 0, ctypes.byref(identifier)))
        return identifier.value

    def get(self, name):
        return self._invoke(self._identifier(name), 2)

    def call(self, name, *arguments):
        return self._invoke(self._identifier(name), 1, arguments)

    def items(self, limit=65536):
        if type(limit) is not int or not 0 <= limit <= 65536:
            raise LauncherError("COM enumeration exceeds its safety bound.")
        unknown = self._invoke(-4, 3)
        if not isinstance(unknown, _Unknown):
            raise LauncherError("Windows COM enumeration interface is unavailable.")
        enumerator = unknown.query(_ENUM, _Unknown)
        try:
            for index in range(limit + 1):
                value, fetched = _Variant(), w.ULONG()
                try:
                    status = enumerator._method(3, w.LONG, w.ULONG, ctypes.POINTER(_Variant),
                                                ctypes.POINTER(w.ULONG))(1, ctypes.byref(value), ctypes.byref(fetched))
                    _check(status)
                    if status == 1 and fetched.value == 0:
                        return
                    if status != 0 or fetched.value != 1 or index == limit:
                        raise LauncherError("Native COM enumeration exceeds its safety bound.")
                    item = self.api.value(value, self.apartment)
                    if not isinstance(item, _Unknown):
                        raise LauncherError("Windows COM enumeration yielded no object.")
                    yield item.query(_DISPATCH, RawDispatch)
                finally:
                    self.api.auto.VariantClear(ctypes.byref(value))
        finally:
            enumerator.close()
            unknown.close()


def shell_dispatch():
    return _automation().create("Shell.Application")


def wmi_dispatch():
    return _automation().create(
        "winmgmts:{impersonationLevel=impersonate}!\\\\.\\root\\cimv2", moniker=True
    )
