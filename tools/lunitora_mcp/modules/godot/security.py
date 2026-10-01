"""Windows-only credential storage. Never expose credentials in diagnostics.

Every ancestor and the credential remain pinned without write/delete sharing
until the MCP process closes the Credential. Protected DACLs are applied at
creation, before any secret bytes are written.
"""
from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path


class StorageError(ValueError):
    def __init__(self):
        super().__init__("Local Godot authentication storage is unsafe or unavailable.")


def _apis():
    if os.name != "nt":
        raise StorageError()
    import win32api
    import win32con
    import win32file
    import win32security
    import ntsecuritycon
    return win32api, win32con, win32file, win32security, ntsecuritycon


def _identity():
    api, con, _, security, _ = _apis()
    token = security.OpenProcessToken(api.GetCurrentProcess(), con.TOKEN_QUERY)
    try:
        user = security.GetTokenInformation(token, security.TokenUser)[0]
    finally:
        token.Close()
    return user, security.CreateWellKnownSid(security.WinLocalSystemSid, None)


def protected_attributes(*, directory: bool):
    _, _, _, security, nt = _apis()
    user, system = _identity()
    acl = security.ACL()
    flags = 3 if directory else 0  # OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
    for sid in (user, system):
        acl.AddAccessAllowedAceEx(security.ACL_REVISION, flags, nt.FILE_ALL_ACCESS, sid)
    descriptor = security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(user, False)
    descriptor.SetSecurityDescriptorDacl(True, acl, False)
    descriptor.SetSecurityDescriptorControl(0x1000, 0x1000)  # SE_DACL_PROTECTED
    attributes = security.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def validate_acl(handle) -> None:
    _, _, _, security, nt = _apis()
    user, system = _identity()
    descriptor = security.GetSecurityInfo(
        handle, security.SE_FILE_OBJECT,
        security.OWNER_SECURITY_INFORMATION | security.DACL_SECURITY_INFORMATION)
    control, _ = descriptor.GetSecurityDescriptorControl()
    if not control & 0x1000 or descriptor.GetSecurityDescriptorOwner() != user:
        raise StorageError()
    acl = descriptor.GetSecurityDescriptorDacl()
    if acl is None or acl.GetAceCount() != 2:
        raise StorageError()
    seen = set()
    for index in range(acl.GetAceCount()):
        header, mask, sid = acl.GetAce(index)
        identity = security.ConvertSidToStringSid(sid)
        if (header[0] != 0 or header[1] & 0x10 or mask != nt.FILE_ALL_ACCESS
                or sid not in (user, system) or identity in seen):
            raise StorageError()
        seen.add(identity)
    if seen != {security.ConvertSidToStringSid(user), security.ConvertSidToStringSid(system)}:
        raise StorageError()


def pin(stack: ExitStack, path: Path, *, directory: bool, create: bool = False):
    _, con, file, _, nt = _apis()
    access = con.GENERIC_READ | nt.READ_CONTROL
    if create:
        access |= con.GENERIC_WRITE
    handle = file.CreateFile(
        str(path), access, con.FILE_SHARE_READ,
        protected_attributes(directory=False) if create else None,
        con.CREATE_NEW if create else con.OPEN_EXISTING,
        0x00200000 | (0x02000000 if directory else 0), None)
    stack.callback(handle.Close)
    info = file.GetFileInformationByHandle(handle)
    if info[0] & 0x400 or bool(info[0] & 0x10) != directory:
        raise StorageError()
    if not directory and (info[7] != 1 or info[5] or info[6] > 4096):
        raise StorageError()
    return handle


def open_storage(project_root: Path) -> tuple[ExitStack, object, bool]:
    """Return pinned file/parents; reject links before resolving paths.

    Existing local directories must already have the protected DACL. We never
    repair an untrusted directory or change Photoshop's existing local storage.
    """
    _, _, file, _, _ = _apis()
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
            file.CreateDirectory(str(current), protected_attributes(directory=True))
        except Exception as error:
            if getattr(error, "winerror", None) != 183:
                raise StorageError() from None
        local_handle = pin(stack, current, directory=True)
        validate_acl(local_handle)
        path = current / "godot-auth.json"
        try:
            handle = pin(stack, path, directory=False, create=True)
            created = True
        except Exception as error:
            if getattr(error, "winerror", None) not in (80, 183):
                raise StorageError() from None
            handle = pin(stack, path, directory=False)
            created = False
        validate_acl(handle)
        return stack, handle, created
    except BaseException:
        stack.close()
        raise StorageError() from None


def write_storage(handle, payload: bytes) -> None:
    _, _, file, _, _ = _apis()
    if not 0 < len(payload) <= 4096:
        raise StorageError()
    _, count = file.WriteFile(handle, payload)
    if count != len(payload):
        raise StorageError()
    file.FlushFileBuffers(handle)


def read_storage(handle) -> bytes:
    _, _, file, _, _ = _apis()
    file.SetFilePointer(handle, 0, 0)
    _, data = file.ReadFile(handle, 4097)
    if not 0 < len(data) <= 4096:
        raise StorageError()
    return data
