"""Windows handle-locked inbox/staging paths; no arbitrary Photoshop paths."""
from contextlib import contextmanager, ExitStack
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import stat

from .protocol import BridgeError

RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.I)


def relative_parts(value: str, area: str) -> tuple[str, ...]:
    if not isinstance(value, str) or len(value) > 512:
        raise BridgeError("INVALID_PATH")
    parts = tuple(value.split("/"))
    if (len(parts) < 3 or parts[:2] != ("source_art", area)
            or any(not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}", p)
                   or p in {".", ".."} or p.endswith(".") or RESERVED.match(p) for p in parts)
            or not parts[-1].lower().endswith(".png")):
        raise BridgeError("INVALID_PATH")
    return parts


@contextmanager
def locked_handle(path: Path, *, directory: bool):
    """OPEN_REPARSE_POINT + deny write/delete sharing closes the validation race."""
    if os.name != "nt":
        raise BridgeError("UNSUPPORTED_PLATFORM")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                  wintypes.LPVOID, wintypes.DWORD]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    # GENERIC_READ participates in share checks; metadata-only access does not
    # reliably prevent directory renames on Windows.
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x02200000, None)
    if handle == wintypes.HANDLE(-1).value:
        if ctypes.get_last_error() in {2, 3}:
            raise BridgeError("SOURCE_NOT_FOUND" if not directory else "INVALID_PATH")
        raise BridgeError("PATH_UNSAFE")
    try:
        attrs = (wintypes.DWORD * 2)()
        if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(attrs), ctypes.sizeof(attrs)):
            raise BridgeError("PATH_UNSAFE")
        if attrs[0] & 0x400 or bool(attrs[0] & 0x10) != directory:
            raise BridgeError("PATH_UNSAFE")
        yield handle
    finally:
        kernel.CloseHandle(handle)


@contextmanager
def locked_parent(repo: Path, parts: tuple[str, ...], *, create: bool = False):
    """Hold every parent until publication; reject junctions as well as symlinks."""
    with ExitStack() as stack:
        current = repo
        stack.enter_context(locked_handle(current, directory=True))
        for part in parts[:-1]:
            current = current / part
            if create:
                try:
                    current.mkdir()
                except FileExistsError:
                    pass
            stack.enter_context(locked_handle(current, directory=True))
        yield current / parts[-1]


def read_source(path: Path, limit: int) -> bytes:
    with locked_handle(path, directory=False):
        # The pinned no-write/no-delete handle prevents replacement while opening.
        with path.open("rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BridgeError("PATH_UNSAFE")
            data = stream.read(limit + 1)
    if len(data) > limit:
        raise BridgeError("IMAGE_TOO_LARGE")
    return data


def require_absent(path: Path) -> None:
    # lexists also rejects broken symlinks and directories.
    if os.path.lexists(path):
        raise BridgeError("DESTINATION_EXISTS")


def publish_candidate(path: Path, data: bytes) -> None:
    """CREATE_NEW + share=0: existing names fail; partial bytes are never readable.

    The caller holds the parent locks. On failure mark the still-exclusive handle
    for deletion before closing it, so no partial candidate is made available.
    """
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                 wintypes.LPVOID, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0xC0010000, 0, None, 1, 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        if ctypes.get_last_error() in {80, 183}:
            raise BridgeError("DESTINATION_EXISTS")
        raise BridgeError("STAGING_WRITE_FAILED")
    descriptor = None
    stream = None
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | os.O_RDWR)
        stream = os.fdopen(descriptor, "w+b", buffering=0)
        with stream:
            try:
                if stream.write(data) != len(data):
                    raise OSError("Incomplete candidate write.")
                stream.flush()
                os.fsync(stream.fileno())
                stream.seek(0)
                if stream.read(len(data) + 1) != data:
                    raise OSError("Candidate readback mismatch.")
            except BaseException:
                delete = ctypes.c_ubyte(1)
                if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(delete), 1):
                    raise BridgeError("STAGING_WRITE_FAILED") from None
                raise
    finally:
        if stream is None:
            delete = ctypes.c_ubyte(1)
            kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(delete), 1)
            if descriptor is None:
                kernel.CloseHandle(handle)
            else:
                os.close(descriptor)
