"""Stdlib host access to the reviewed Windows protected credential contract."""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
from ctypes import wintypes as w
from functools import lru_cache
import os
from pathlib import Path
from types import SimpleNamespace


class StorageError(ValueError):
    def __init__(self):
        super().__init__("Local authentication storage is unsafe or unavailable.")


class _StorageOSError(OSError):
    def __init__(self, code):
        super().__init__("Local authentication storage is unavailable.")
        self.winerror = code


class _SecurityDescriptor(ctypes.Structure):
    _fields_ = [("revision", w.BYTE), ("reserved", w.BYTE), ("control", w.WORD),
                ("owner", ctypes.c_void_p), ("group", ctypes.c_void_p),
                ("sacl", ctypes.c_void_p), ("dacl", ctypes.c_void_p)]


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", w.BOOL)]


class _ACL(ctypes.Structure):
    _fields_ = [("revision", w.BYTE), ("reserved", w.BYTE), ("size", w.WORD),
                ("count", w.WORD), ("reserved2", w.WORD)]


class _ACE(ctypes.Structure):
    _fields_ = [("type", w.BYTE), ("flags", w.BYTE), ("size", w.WORD), ("mask", w.DWORD)]


class _FileInfo(ctypes.Structure):
    _fields_ = [("attributes", w.DWORD), ("created", w.FILETIME), ("accessed", w.FILETIME),
                ("written", w.FILETIME), ("volume", w.DWORD), ("size_high", w.DWORD),
                ("size_low", w.DWORD), ("links", w.DWORD),
                ("index_high", w.DWORD), ("index_low", w.DWORD)]


class _Handle:
    def __init__(self, value, native):
        self.value, self.native = value, native

    def Close(self):
        if self.value is not None:
            value, self.value = self.value, None
            if not self.native.kernel.CloseHandle(value):
                raise StorageError()


def _handle(value):
    result = value.value if isinstance(value, _Handle) else value
    if not result:
        raise StorageError()
    return result


def _filetime(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


class _Native:
    def __init__(self):
        if os.name != "nt":
            raise StorageError()
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True, winmode=0x800)
        p, pp = ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        def bind(dll, name, args, result):
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        bind(self.kernel, "GetCurrentProcess", [], w.HANDLE)
        bind(self.kernel, "CloseHandle", [w.HANDLE], w.BOOL)
        bind(self.kernel, "LocalFree", [p], p)
        bind(self.kernel, "CreateFileW", [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(_SecurityAttributes),
                                           w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
        bind(self.kernel, "CreateDirectoryW", [w.LPCWSTR, ctypes.POINTER(_SecurityAttributes)], w.BOOL)
        bind(self.kernel, "GetFileInformationByHandle", [w.HANDLE, ctypes.POINTER(_FileInfo)], w.BOOL)
        bind(self.kernel, "SetFilePointerEx", [w.HANDLE, ctypes.c_longlong,
                                               ctypes.POINTER(ctypes.c_longlong), w.DWORD], w.BOOL)
        bind(self.kernel, "ReadFile", [w.HANDLE, p, w.DWORD, ctypes.POINTER(w.DWORD), p], w.BOOL)
        bind(self.kernel, "WriteFile", [w.HANDLE, p, w.DWORD, ctypes.POINTER(w.DWORD), p], w.BOOL)
        bind(self.kernel, "FlushFileBuffers", [w.HANDLE], w.BOOL)
        bind(self.kernel, "SetEndOfFile", [w.HANDLE], w.BOOL)
        bind(self.security, "OpenProcessToken", [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL)
        bind(self.security, "GetTokenInformation", [w.HANDLE, ctypes.c_int, p, w.DWORD,
                                                     ctypes.POINTER(w.DWORD)], w.BOOL)
        bind(self.security, "CreateWellKnownSid", [ctypes.c_int, p, p, ctypes.POINTER(w.DWORD)], w.BOOL)
        bind(self.security, "IsValidSid", [p], w.BOOL)
        bind(self.security, "GetLengthSid", [p], w.DWORD)
        bind(self.security, "InitializeAcl", [p, w.DWORD, w.DWORD], w.BOOL)
        bind(self.security, "AddAccessAllowedAceEx", [p, w.DWORD, w.DWORD, w.DWORD, p], w.BOOL)
        bind(self.security, "InitializeSecurityDescriptor", [p, w.DWORD], w.BOOL)
        bind(self.security, "SetSecurityDescriptorOwner", [p, p, w.BOOL], w.BOOL)
        bind(self.security, "SetSecurityDescriptorDacl", [p, w.BOOL, p, w.BOOL], w.BOOL)
        bind(self.security, "SetSecurityDescriptorControl", [p, w.WORD, w.WORD], w.BOOL)
        bind(self.security, "GetSecurityInfo", [w.HANDLE, ctypes.c_int, w.DWORD, pp, pp, pp, pp, pp], w.DWORD)
        bind(self.security, "GetSecurityDescriptorControl", [p, ctypes.POINTER(w.WORD),
                                                             ctypes.POINTER(w.DWORD)], w.BOOL)
        bind(self.security, "GetAce", [p, w.DWORD, pp], w.BOOL)
        bind(self.security, "SetKernelObjectSecurity", [w.HANDLE, w.DWORD, p], w.BOOL)

    def sid(self, pointer):
        if not pointer or not self.security.IsValidSid(pointer):
            raise StorageError()
        size = self.security.GetLengthSid(pointer)
        if not 8 <= size <= 68:
            raise StorageError()
        return ctypes.string_at(pointer, size)

    def identity(self):
        token = w.HANDLE()
        if not self.security.OpenProcessToken(self.kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise StorageError()
        try:
            size = w.DWORD()
            self.security.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
            if not ctypes.sizeof(ctypes.c_void_p) <= size.value <= 65536:
                raise StorageError()
            data = ctypes.create_string_buffer(size.value)
            if not self.security.GetTokenInformation(token, 1, data, len(data), ctypes.byref(size)):
                raise StorageError()
            pointer = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p)).contents.value
            start, end = ctypes.addressof(data), ctypes.addressof(data) + len(data)
            if not pointer or not start <= pointer <= end - 8:
                raise StorageError()
            user = self.sid(pointer)
            if pointer + len(user) > end:
                raise StorageError()
        finally:
            self.kernel.CloseHandle(token)
        size = w.DWORD(68)
        data = ctypes.create_string_buffer(size.value)
        if not self.security.CreateWellKnownSid(22, None, data, ctypes.byref(size)):
            raise StorageError()
        return user, self.sid(ctypes.addressof(data))


@lru_cache(maxsize=1)
def _native():
    return _Native()


class _File:
    def CreateFile(self, path, access, share, attributes, creation, flags, template):
        if "\x00" in path:
            raise StorageError()
        native = _native()
        security = None if attributes is None else ctypes.byref(attributes)
        value = native.kernel.CreateFileW(path, access, share, security, creation, flags, template)
        if value in (None, ctypes.c_void_p(-1).value):
            raise _StorageOSError(ctypes.get_last_error())
        return _Handle(value, native)

    def CreateDirectory(self, path, attributes):
        if "\x00" in path:
            raise StorageError()
        security = None if attributes is None else ctypes.byref(attributes)
        if not _native().kernel.CreateDirectoryW(path, security):
            raise _StorageOSError(ctypes.get_last_error())

    def GetFileInformationByHandle(self, handle):
        info = _FileInfo()
        if not _native().kernel.GetFileInformationByHandle(_handle(handle), ctypes.byref(info)):
            raise StorageError()
        return (info.attributes, _filetime(info.created), _filetime(info.accessed), _filetime(info.written),
                info.volume, info.size_high, info.size_low, info.links, info.index_high, info.index_low)

    def SetFilePointer(self, handle, distance, method):
        position = ctypes.c_longlong()
        if not _native().kernel.SetFilePointerEx(_handle(handle), distance, ctypes.byref(position), method):
            raise StorageError()
        return position.value

    def ReadFile(self, handle, size):
        if type(size) is not int or not 0 < size <= 4097:
            raise StorageError()
        data, count = ctypes.create_string_buffer(size), w.DWORD()
        if not _native().kernel.ReadFile(_handle(handle), data, size, ctypes.byref(count), None):
            raise StorageError()
        if count.value > size:
            raise StorageError()
        return 0, data.raw[:count.value]

    def WriteFile(self, handle, payload):
        if not isinstance(payload, bytes) or not 0 < len(payload) <= 4096:
            raise StorageError()
        data, count = ctypes.create_string_buffer(payload), w.DWORD()
        if not _native().kernel.WriteFile(_handle(handle), data, len(payload), ctypes.byref(count), None):
            raise StorageError()
        return 0, count.value

    def FlushFileBuffers(self, handle):
        if not _native().kernel.FlushFileBuffers(_handle(handle)):
            raise StorageError()

    def SetEndOfFile(self, handle):
        if not _native().kernel.SetEndOfFile(_handle(handle)):
            raise StorageError()


_CON = SimpleNamespace(GENERIC_READ=0x80000000, GENERIC_WRITE=0x40000000,
                       FILE_SHARE_READ=1, CREATE_NEW=1, OPEN_EXISTING=3, TOKEN_QUERY=8)
_NT = SimpleNamespace(READ_CONTROL=0x20000, FILE_ALL_ACCESS=0x1F01FF)
_FILE = _File()


def _apis():
    return _native(), _CON, _FILE, None, _NT


def protected_attributes(*, directory):
    native = _native()
    user, system = [ctypes.create_string_buffer(value) for value in native.identity()]
    size = ctypes.sizeof(_ACL) + sum(8 + len(value) - 1 for value in (user, system))
    acl = ctypes.create_string_buffer(size)
    descriptor = _SecurityDescriptor()
    operations = [native.security.InitializeAcl(acl, size, 2)]
    for sid in (user, system):
        operations.append(native.security.AddAccessAllowedAceEx(acl, 2, 3 if directory else 0,
                                                                 _NT.FILE_ALL_ACCESS, sid))
    operations.extend([
        native.security.InitializeSecurityDescriptor(ctypes.byref(descriptor), 1),
        native.security.SetSecurityDescriptorOwner(ctypes.byref(descriptor), user, False),
        native.security.SetSecurityDescriptorDacl(ctypes.byref(descriptor), True, acl, False),
        native.security.SetSecurityDescriptorControl(ctypes.byref(descriptor), 0x1000, 0x1000),
    ])
    if not all(operations):
        raise StorageError()
    attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), ctypes.addressof(descriptor), False)
    attributes._keepalive = descriptor, acl, user, system
    return attributes


def validate_acl(handle):
    native = _native()
    user, system = native.identity()
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    status = native.security.GetSecurityInfo(_handle(handle), 1, 1 | 4,
                                             ctypes.byref(owner), None, ctypes.byref(dacl), None,
                                             ctypes.byref(descriptor))
    if status or not descriptor.value:
        raise StorageError()
    try:
        control, revision = w.WORD(), w.DWORD()
        if (not native.security.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision))
                or not control.value & 0x1000 or native.sid(owner.value) != user or not dacl.value):
            raise StorageError()
        header = ctypes.cast(dacl, ctypes.POINTER(_ACL)).contents
        if header.count != 2 or header.size < ctypes.sizeof(_ACL):
            raise StorageError()
        start, end, seen = dacl.value, dacl.value + header.size, set()
        for index in range(header.count):
            pointer = ctypes.c_void_p()
            if (not native.security.GetAce(dacl, index, ctypes.byref(pointer))
                    or not pointer.value or not start <= pointer.value <= end - 16):
                raise StorageError()
            ace = ctypes.cast(pointer, ctypes.POINTER(_ACE)).contents
            if (ace.type != 0 or ace.flags & 0x10 or ace.mask != _NT.FILE_ALL_ACCESS
                    or ace.size < 16 or pointer.value + ace.size > end):
                raise StorageError()
            sid = native.sid(pointer.value + 8)
            if pointer.value + 8 + len(sid) > pointer.value + ace.size or sid not in (user, system) or sid in seen:
                raise StorageError()
            seen.add(sid)
        if seen != {user, system}:
            raise StorageError()
    finally:
        native.kernel.LocalFree(descriptor)


def protection_snapshot(handle):
    """Immutable, non-secret provenance and ACL evidence from a pinned object."""
    native = _native()
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    if native.security.GetSecurityInfo(_handle(handle), 1, 5, ctypes.byref(owner), None,
                                       ctypes.byref(dacl), None, ctypes.byref(descriptor)):
        raise StorageError()
    try:
        control, revision = w.WORD(), w.DWORD()
        if not native.security.GetSecurityDescriptorControl(descriptor, ctypes.byref(control), ctypes.byref(revision)):
            raise StorageError()
        entries = []
        if not dacl.value:
            raise StorageError()
        header = ctypes.cast(dacl, ctypes.POINTER(_ACL)).contents
        for index in range(header.count):
            pointer = ctypes.c_void_p()
            if not native.security.GetAce(dacl, index, ctypes.byref(pointer)):
                raise StorageError()
            ace = ctypes.cast(pointer, ctypes.POINTER(_ACE)).contents
            entries.append(ctypes.string_at(pointer, ace.size))
        return native.sid(owner.value), control.value, tuple(entries)
    finally:
        native.kernel.LocalFree(descriptor)


def reviewed_owner(snapshot):
    native = _native()
    user, system = native.identity()
    size = w.DWORD(68)
    data = ctypes.create_string_buffer(size.value)
    if not native.security.CreateWellKnownSid(26, None, data, ctypes.byref(size)):
        raise StorageError()
    return snapshot[0] in (user, system, native.sid(ctypes.addressof(data)))


def repair_handle(stack, path, *, directory):
    """Exclusive mutation handle; never enables privileges or follows redirects."""
    handle = _FILE.CreateFile(str(path), _CON.GENERIC_READ | _NT.READ_CONTROL | 0xC0000,
                              0, None, _CON.OPEN_EXISTING,
                              0x00200000 | (0x02000000 if directory else 0), None)
    stack.callback(handle.Close)
    info = _FILE.GetFileInformationByHandle(handle)
    if (info[0] & 0x400 or bool(info[0] & 0x10) != directory
            or (not directory and (info[7] != 1 or info[5] or info[6] > 4096))):
        raise StorageError()
    return handle


def pin_child_security(stack, path, *, directory):
    """Pin unrelated artifacts for security inspection, without credential size limits."""
    handle = _FILE.CreateFile(str(path), _NT.READ_CONTROL, 0, None, _CON.OPEN_EXISTING,
                              0x00200000 | (0x02000000 if directory else 0), None)
    stack.callback(handle.Close)
    info = _FILE.GetFileInformationByHandle(handle)
    if info[0] & 0x400 or bool(info[0] & 0x10) != directory:
        raise StorageError()
    return handle


def apply_protection(handle, *, directory):
    """Apply reviewed security. Caller must guard directory inheritance effects."""
    # Non-inheritable ACEs satisfy validate_acl. The caller must first prove
    # unrelated children have protected DACLs, because Windows can propagate
    # removal of inherited ACEs even when these new ACEs are non-inheritable.
    attributes = protected_attributes(directory=False)
    if not _native().security.SetKernelObjectSecurity(
            _handle(handle), 1 | 4 | 0x80000000, attributes.descriptor):
        raise StorageError()
    validate_acl(handle)


def pin(stack: ExitStack, path: Path, *, directory, create=False):
    access = _CON.GENERIC_READ | _NT.READ_CONTROL | (_CON.GENERIC_WRITE if create else 0)
    handle = _FILE.CreateFile(str(path), access, _CON.FILE_SHARE_READ,
                              protected_attributes(directory=False) if create else None,
                              _CON.CREATE_NEW if create else _CON.OPEN_EXISTING,
                              0x00200000 | (0x02000000 if directory else 0), None)
    stack.callback(handle.Close)
    info = _FILE.GetFileInformationByHandle(handle)
    if (info[0] & 0x400 or bool(info[0] & 0x10) != directory
            or (not directory and (info[7] != 1 or info[5] or info[6] > 4096))):
        raise StorageError()
    return handle


def open_storage(project_root):
    stack = ExitStack()
    try:
        root = Path(os.path.abspath(project_root))
        current = Path(root.anchor)
        pin(stack, current, directory=True)
        for part in root.parts[1:]:
            current /= part
            pin(stack, current, directory=True)
        for part in ("tools", "lunitora_mcp"):
            current /= part
            pin(stack, current, directory=True)
        current /= ".local"
        try:
            _FILE.CreateDirectory(str(current), protected_attributes(directory=True))
        except Exception as error:
            if getattr(error, "winerror", None) != 183:
                raise StorageError() from None
        validate_acl(pin(stack, current, directory=True))
        try:
            handle = pin(stack, current / "godot-auth.json", directory=False, create=True)
            created = True
        except Exception as error:
            if getattr(error, "winerror", None) not in (80, 183):
                raise StorageError() from None
            handle, created = pin(stack, current / "godot-auth.json", directory=False), False
        validate_acl(handle)
        return stack, handle, created
    except BaseException:
        stack.close()
        raise StorageError() from None


def write_storage(handle, payload):
    _, count = _FILE.WriteFile(handle, payload)
    if count != len(payload):
        raise StorageError()
    _FILE.FlushFileBuffers(handle)


def read_storage(handle):
    _FILE.SetFilePointer(handle, 0, 0)
    _, payload = _FILE.ReadFile(handle, 4097)
    if not 0 < len(payload) <= 4096:
        raise StorageError()
    return payload
