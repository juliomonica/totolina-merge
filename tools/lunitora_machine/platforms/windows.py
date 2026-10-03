"""Windows-native launcher operations; no PowerShell or shell-command fallback."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import ntpath
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import xml.etree.ElementTree as ET

from lunitora_machine.policy import (
    LauncherError, Process, absolute_local_path, process_identity, same_path as _same_path,
)
from .windows_com import RawDispatch as _RawDispatch, shell_dispatch as _shell_dispatch, wmi_dispatch as _wmi_dispatch


_KINDS = {
    "desktopExe": "desktop", "photoshopExe": "photoshop",
    "udtExe": "udt", "godotExe": "godot",
}
_NAMES = {
    "desktop": ("ChatGPT.exe", "Codex.exe"),
    "photoshop": ("Photoshop.exe",),
    "udt": ("Adobe UXP Developer Tools.exe", "UXP Developer Tool.exe"),
    "godot": ("Godot.exe", "godot.exe"),
}
_FILETIME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)
_AUMID = re.compile(r"^[A-Za-z0-9._-]+![A-Za-z0-9._-]+$")
_OPENAI = re.compile(r"^OpenAI(?: OpCo)?(?:,? (?:LLC|Inc\.?))?$")
_GODOT_NAME = re.compile(r"^Godot(?:_[A-Za-z0-9._-]+)?\.exe$", re.IGNORECASE)
_GODOT_VERSION = re.compile(r"^4\.7\.2\.stable\.official(?:\.[A-Za-z0-9]+)?$")


def _kind(value: str) -> str:
    value = _KINDS.get(value, value)
    if value not in _NAMES:
        raise LauncherError("Unknown application kind.")
    return value


def _contained(path: str, directory: str) -> bool:
    if not absolute_local_path(path) or not absolute_local_path(directory):
        return False
    path = ntpath.normpath(path)
    directory = ntpath.normpath(directory).rstrip("\\/")
    return len(path) > len(directory) and path[len(directory)] == "\\" and _same_path(path[:len(directory)], directory)


def _absolute_executable(path: str) -> str:
    if not absolute_local_path(path):
        raise LauncherError("Application requires an absolute local executable path.")
    full = os.path.abspath(path)
    if ntpath.splitext(full)[1].lower() != ".exe" or not Path(full).is_file():
        raise LauncherError("Application executable is missing or is not an .exe file.")
    return full


def _wmi_created(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d{14})\.(\d{6})([+-])(\d{3})", str(value))
    if not match:
        return None
    offset = int(match[4]) * (1 if match[3] == "+" else -1)
    try:
        stamp = datetime.strptime(match[1], "%Y%m%d%H%M%S").replace(
            microsecond=int(match[2]), tzinfo=timezone(timedelta(minutes=offset))
        )
    except ValueError:
        return None
    delta = stamp.astimezone(timezone.utc) - _FILETIME_EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _process_running(native, handle) -> bool:
    status = native.kernel.WaitForSingleObject(handle, 0)
    if status == 0:
        return False
    if status == 258:
        return True
    raise LauncherError("Held process state could not be inspected; refusing mutation.")


class _GUID(ctypes.Structure):
    _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD),
                ("data3", wintypes.WORD), ("data4", ctypes.c_ubyte * 8)]


class _WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("path", wintypes.LPCWSTR),
                ("file", wintypes.HANDLE), ("subject", ctypes.c_void_p)]


class _WINTRUST_DATA(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD), ("policy", ctypes.c_void_p),
        ("sip", ctypes.c_void_p), ("ui", wintypes.DWORD),
        ("revocation", wintypes.DWORD), ("choice", wintypes.DWORD),
        ("file_info", ctypes.POINTER(_WINTRUST_FILE_INFO)),
        ("state_action", wintypes.DWORD), ("state", wintypes.HANDLE),
        ("url", wintypes.LPCWSTR), ("flags", wintypes.DWORD),
        ("ui_context", wintypes.DWORD), ("signature", ctypes.c_void_p),
    ]


class _PROVIDER_CERT_PREFIX(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("certificate", ctypes.c_void_p)]


class _TCP4_ROW(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in
                ("state", "local", "port", "remote", "remote_port", "pid")]


class _TCP6_ROW(ctypes.Structure):
    _fields_ = [("local", ctypes.c_ubyte * 16), ("scope", wintypes.DWORD),
                ("port", wintypes.DWORD), ("remote", ctypes.c_ubyte * 16),
                ("remote_scope", wintypes.DWORD), ("remote_port", wintypes.DWORD),
                ("state", wintypes.DWORD), ("pid", wintypes.DWORD)]


class _WindowsAPI:
    def __init__(self) -> None:
        if os.name != "nt":
            raise LauncherError("Windows operations require Windows.")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        self.version = ctypes.WinDLL("version", use_last_error=True, winmode=0x800)
        self.trust = ctypes.WinDLL("wintrust", use_last_error=True, winmode=0x800)
        self.crypto = ctypes.WinDLL("crypt32", use_last_error=True, winmode=0x800)
        self.ip = ctypes.WinDLL("iphlpapi", use_last_error=True, winmode=0x800)
        self.user = ctypes.WinDLL("user32", use_last_error=True, winmode=0x800)
        self._bind()

    def _bind(self) -> None:
        def bind(dll, name, args, result):
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        pointer = ctypes.c_void_p
        dword_pointer = ctypes.POINTER(wintypes.DWORD)
        bind(self.version, "GetFileVersionInfoSizeW", [wintypes.LPCWSTR, dword_pointer], wintypes.DWORD)
        bind(self.version, "GetFileVersionInfoW", [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, pointer], wintypes.BOOL)
        bind(self.version, "VerQueryValueW", [pointer, wintypes.LPCWSTR, ctypes.POINTER(pointer), ctypes.POINTER(wintypes.UINT)], wintypes.BOOL)
        bind(self.trust, "WinVerifyTrust", [wintypes.HWND, ctypes.POINTER(_GUID), ctypes.POINTER(_WINTRUST_DATA)], wintypes.LONG)
        bind(self.trust, "WTHelperProvDataFromStateData", [wintypes.HANDLE], pointer)
        bind(self.trust, "WTHelperGetProvSignerFromChain", [pointer, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], pointer)
        bind(self.trust, "WTHelperGetProvCertFromChain", [pointer, wintypes.DWORD], pointer)
        bind(self.crypto, "CertGetNameStringW", [pointer, wintypes.DWORD, wintypes.DWORD, pointer, wintypes.LPWSTR, wintypes.DWORD], wintypes.DWORD)
        bind(self.kernel, "GetPackagesByPackageFamily", [wintypes.LPCWSTR, dword_pointer, ctypes.POINTER(wintypes.LPWSTR), dword_pointer, wintypes.LPWSTR], wintypes.LONG)
        bind(self.kernel, "GetPackagePathByFullName", [wintypes.LPCWSTR, dword_pointer, wintypes.LPWSTR], wintypes.LONG)
        bind(self.kernel, "OpenProcess", [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
        bind(self.kernel, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
        bind(self.kernel, "GetProcessTimes", [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL)
        bind(self.kernel, "QueryFullProcessImageNameW", [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, dword_pointer], wintypes.BOOL)
        bind(self.kernel, "TerminateProcess", [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL)
        bind(self.kernel, "WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD)
        bind(self.ip, "GetExtendedTcpTable", [pointer, dword_pointer, wintypes.BOOL, wintypes.ULONG, ctypes.c_int, wintypes.ULONG], wintypes.DWORD)
        bind(self.user, "GetWindowThreadProcessId", [wintypes.HWND, dword_pointer], wintypes.DWORD)
        bind(self.user, "IsWindowVisible", [wintypes.HWND], wintypes.BOOL)
        bind(self.user, "GetWindow", [wintypes.HWND, wintypes.UINT], wintypes.HWND)
        bind(self.user, "PostMessageW", [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM], wintypes.BOOL)
        self.enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        bind(self.user, "EnumWindows", [self.enum_callback, wintypes.LPARAM], wintypes.BOOL)

    def metadata(self, path: str) -> dict[str, str]:
        ignored = wintypes.DWORD()
        size = self.version.GetFileVersionInfoSizeW(path, ctypes.byref(ignored))
        if not size:
            raise LauncherError("Application has no readable Windows product metadata.")
        data = ctypes.create_string_buffer(size)
        if not self.version.GetFileVersionInfoW(path, 0, size, data):
            raise LauncherError("Could not read Windows product metadata.")
        translations = ctypes.c_void_p()
        length = wintypes.UINT()
        if not self.version.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(translations), ctypes.byref(length)):
            raise LauncherError("Application has no version-resource translation.")
        if length.value < 4 or length.value % 4:
            raise LauncherError("Application version-resource translation is invalid.")
        pairs = ctypes.cast(translations, ctypes.POINTER(wintypes.WORD))
        result = {}
        for field in ("ProductName", "ProductVersion"):
            values = set()
            for index in range(length.value // 4):
                query = f"\\StringFileInfo\\{pairs[index * 2]:04x}{pairs[index * 2 + 1]:04x}\\{field}"
                value = ctypes.c_void_p()
                value_length = wintypes.UINT()
                if self.version.VerQueryValueW(data, query, ctypes.byref(value), ctypes.byref(value_length)) and value_length.value:
                    values.add(ctypes.wstring_at(value.value, value_length.value).rstrip("\0"))
            if len(values) != 1:
                raise LauncherError("Application product metadata is missing or ambiguous.")
            result[field] = values.pop()
        return result

    def publisher(self, path: str) -> str:
        action = _GUID(0x00AAC56B, 0xCD44, 0x11D0, (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0, 0xC0, 0x4F, 0xC2, 0x95, 0xEE))
        file_info = _WINTRUST_FILE_INFO(ctypes.sizeof(_WINTRUST_FILE_INFO), path, None, None)
        data = _WINTRUST_DATA()
        data.size, data.ui, data.choice, data.state_action = ctypes.sizeof(data), 2, 1, 1
        data.flags = 0x1000  # WTD_CACHE_ONLY_URL_RETRIEVAL: checks must not fetch certificates.
        data.file_info = ctypes.pointer(file_info)
        try:
            if self.trust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data)) != 0:
                raise LauncherError("Desktop requires a valid OpenAI Authenticode signature.")
            provider = self.trust.WTHelperProvDataFromStateData(data.state)
            signer = self.trust.WTHelperGetProvSignerFromChain(provider, 0, False, 0) if provider else None
            certificate = self.trust.WTHelperGetProvCertFromChain(signer, 0) if signer else None
            if not certificate:
                raise LauncherError("Desktop signer identity is unavailable.")
            context = ctypes.cast(certificate, ctypes.POINTER(_PROVIDER_CERT_PREFIX)).contents.certificate
            size = self.crypto.CertGetNameStringW(context, 4, 0, None, None, 0)
            if size < 2 or size > 32768:
                raise LauncherError("Desktop signer identity is unavailable.")
            name = ctypes.create_unicode_buffer(size)
            if self.crypto.CertGetNameStringW(context, 4, 0, None, name, size) != size:
                raise LauncherError("Desktop signer identity could not be read.")
            return name.value
        finally:
            if data.state:
                data.state_action = 2
                self.trust.WinVerifyTrust(None, ctypes.byref(action), ctypes.byref(data))

    def packages(self, family: str) -> list[str]:
        count, length = wintypes.DWORD(), wintypes.DWORD()
        status = self.kernel.GetPackagesByPackageFamily(family, ctypes.byref(count), None, ctypes.byref(length), None)
        if status == 0 and not count.value:
            return []
        if status != 122 or not 0 < count.value <= 4096 or not 0 < length.value <= 1_048_576:
            raise LauncherError("Current-user package registration could not be inspected.")
        names = (wintypes.LPWSTR * count.value)()
        buffer = ctypes.create_unicode_buffer(length.value)
        status = self.kernel.GetPackagesByPackageFamily(family, ctypes.byref(count), names, ctypes.byref(length), buffer)
        if status != 0:
            raise LauncherError("Current-user package registration changed during inspection.")
        return [str(name) for name in names[:count.value] if name]

    def package_path(self, full_name: str) -> str:
        length = wintypes.DWORD()
        status = self.kernel.GetPackagePathByFullName(full_name, ctypes.byref(length), None)
        if status != 122 or not 1 < length.value <= 32768:
            raise LauncherError("Registered package installation path is unavailable.")
        buffer = ctypes.create_unicode_buffer(length.value)
        if self.kernel.GetPackagePathByFullName(full_name, ctypes.byref(length), buffer) != 0:
            raise LauncherError("Registered package installation path changed during inspection.")
        return buffer.value

    def process_identity(self, handle) -> tuple[int, str]:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            raise LauncherError("Process creation time could not be proven.")
        created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) // 10
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not self.kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            raise LauncherError("Process executable identity could not be proven.")
        return created, path.value

    def port_owners(self, port: int) -> list[int]:
        owners = set()
        for family, row_type in ((2, _TCP4_ROW), (23, _TCP6_ROW)):
            length = wintypes.DWORD()
            status = self.ip.GetExtendedTcpTable(None, ctypes.byref(length), False, family, 3, 0)
            if status not in (0, 122):
                raise LauncherError("TCP listener ownership could not be inspected.")
            for _ in range(3):
                if not 4 <= length.value <= 67_108_864:
                    raise LauncherError("TCP listener table has invalid bounds.")
                data = ctypes.create_string_buffer(length.value)
                status = self.ip.GetExtendedTcpTable(data, ctypes.byref(length), False, family, 3, 0)
                if status == 122:
                    continue
                if status != 0:
                    raise LauncherError("TCP listener ownership could not be inspected.")
                count = ctypes.cast(data, ctypes.POINTER(wintypes.DWORD)).contents.value
                if 4 + count * ctypes.sizeof(row_type) > ctypes.sizeof(data):
                    raise LauncherError("TCP listener table is truncated.")
                for index in range(count):
                    row = row_type.from_buffer(data, 4 + index * ctypes.sizeof(row_type))
                    if row.state == 2 and socket.ntohs(row.port & 0xFFFF) == port:
                        owners.add(int(row.pid))
                break
            else:
                raise LauncherError("TCP listener table changed repeatedly during inspection.")
        return sorted(owners)


@lru_cache(maxsize=1)
def _api() -> _WindowsAPI:
    return _WindowsAPI()


class WindowsPlatform:
    name = "windows"

    def _apps_folder(self) -> list[dict[str, str]]:
        try:
            folder_raw = _shell_dispatch().call("NameSpace", "shell:AppsFolder")
            if folder_raw is None:
                raise LauncherError("Current-user AppsFolder is unavailable.")
            folder = _RawDispatch(folder_raw)
            items = _RawDispatch(folder.call("Items"))
            if not 0 <= int(items.get("Count")) <= 4096:
                raise LauncherError("AppsFolder enumeration exceeds its safety bound.")
            return [{"aumid": str(item.call("ExtendedProperty", "System.AppUserModel.ID") or ""),
                     "name": str(item.get("Name") or "")} for item in items.items(limit=4096)]
        except LauncherError:
            raise
        except Exception as error:
            raise LauncherError("Current-user application registration inspection failed.") from error

    def _registered_packages(self, entries: list[dict] | None = None) -> list[dict]:
        entries = self._apps_folder() if entries is None else entries
        families = sorted({entry["aumid"].split("!", 1)[0] for entry in entries if _AUMID.fullmatch(entry["aumid"])})
        packages = []
        for family in families:
            for full_name in _api().packages(family):
                packages.append({"family": family, "full_name": full_name,
                                 "path": _api().package_path(full_name)})
        return packages

    def _manifest_applications(self, package: dict) -> list[dict[str, str]]:
        try:
            root = ET.parse(Path(package["path"]) / "AppxManifest.xml").getroot()
        except (OSError, ET.ParseError) as error:
            raise LauncherError("Registered Desktop manifest could not be inspected.") from error
        applications = []
        for element in root.findall("./{*}Applications/{*}Application"):
            relative = element.get("Executable", "")
            if not relative or ntpath.isabs(relative):
                continue
            executable = ntpath.abspath(ntpath.join(package["path"], relative))
            if not _contained(executable, package["path"]):
                raise LauncherError("Package executable escapes its registered installation.")
            applications.append({"path": executable, "id": element.get("Id", "")})
        return applications

    def _desktop_target(self, path: str) -> dict:
        publisher = _api().publisher(path)
        if not _OPENAI.fullmatch(publisher):
            raise LauncherError("Desktop requires a valid OpenAI publisher signature.")
        packages = [package for package in self._registered_packages() if _contained(path, package["path"])]
        if len(packages) > 1:
            raise LauncherError("Desktop package registration is ambiguous.")
        if packages:
            package = packages[0]
            applications = [app for app in self._manifest_applications(package) if _same_path(app["path"], path)]
            if len(applications) != 1:
                raise LauncherError("Desktop must match exactly one registered application.")
            aumid = package["family"] + "!" + applications[0]["id"]
            if not _AUMID.fullmatch(aumid):
                raise LauncherError("Desktop application identity is invalid.")
            return {"aumid": aumid, "identity": publisher}
        if "\\windowsapps\\" in ntpath.normcase(path):
            raise LauncherError("Unregistered WindowsApps Desktop is not an unpackaged application.")
        for ancestor in Path(path).parents:
            if (ancestor / "AppxManifest.xml").is_file():
                raise LauncherError("Desktop has a loose package manifest but no registration.")
        return {"identity": publisher}

    def validate_application(self, kind: str, path: str) -> dict:
        kind = _kind(kind)
        path = _absolute_executable(path)
        name = ntpath.basename(path)
        if kind == "godot":
            if not _GODOT_NAME.fullmatch(name):
                raise LauncherError("Executable filename is not Godot.")
        elif name.casefold() not in {value.casefold() for value in _NAMES[kind]}:
            raise LauncherError("Executable filename does not match the requested application.")
        metadata = _api().metadata(path)
        result = {"kind": kind, "path": path, "version": metadata["ProductVersion"],
                  "identity": metadata["ProductName"]}
        if kind == "godot":
            if metadata["ProductName"] != "Godot Engine" or not _GODOT_VERSION.fullmatch(metadata["ProductVersion"]):
                raise LauncherError("Godot must be the official 4.7.2 stable editor.")
        elif kind == "desktop":
            if metadata["ProductName"] not in ("Codex", "ChatGPT"):
                raise LauncherError("Executable is not the ChatGPT/Codex desktop product.")
            result.update(self._desktop_target(path))
        elif kind == "photoshop":
            if not re.fullmatch(r"(?:Adobe )?Photoshop(?:\s+.*)?", metadata["ProductName"], re.IGNORECASE):
                raise LauncherError("Executable is not the Photoshop application product.")
            if metadata["ProductVersion"]:
                version = re.match(r"^(\d+)\.(\d+)(?:\D|$)", metadata["ProductVersion"])
                if not version or (int(version[1]), int(version[2])) < (27, 10):
                    raise LauncherError("Photoshop requires version 27.10 or newer.")
        elif kind == "udt":
            product = re.sub(r"[\s_-]+", "", metadata["ProductName"]).casefold()
            if "uxpdeveloper" not in product:
                raise LauncherError("Executable is not the UXP Developer Tool product.")
        return result

    def _registry_candidates(self, kind: str) -> list[str]:
        import winreg
        candidates = []
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                access = winreg.KEY_READ | view
                for name in _NAMES[kind]:
                    key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + name
                    try:
                        with winreg.OpenKey(hive, key_path, 0, access) as key:
                            value, _ = winreg.QueryValueEx(key, "")
                            if isinstance(value, str):
                                candidates.append(os.path.expandvars(value.strip().strip('"')))
                    except FileNotFoundError:
                        pass
                    except OSError as error:
                        raise LauncherError("Application registry discovery failed.") from error
                key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
                try:
                    with winreg.OpenKey(hive, key_path, 0, access) as root:
                        count = winreg.QueryInfoKey(root)[0]
                        if count > 16384:
                            raise LauncherError("Installed-application registry exceeds its safety bound.")
                        for index in range(count):
                            with winreg.OpenKey(root, winreg.EnumKey(root, index)) as key:
                                try:
                                    display = str(winreg.QueryValueEx(key, "DisplayName")[0]).casefold()
                                    location = winreg.QueryValueEx(key, "InstallLocation")[0]
                                except FileNotFoundError:
                                    continue
                                expected = {"desktop": ("codex", "chatgpt"), "photoshop": ("adobe photoshop",),
                                            "udt": ("uxp developer",), "godot": ("godot",)}[kind]
                                if isinstance(location, str) and any(value in display for value in expected):
                                    candidates.extend(ntpath.join(os.path.expandvars(location), name) for name in _NAMES[kind])
                except FileNotFoundError:
                    pass
                except OSError as error:
                    raise LauncherError("Installed-application registry discovery failed.") from error
        return candidates

    def discover(self, kind: str, configured: dict | None = None) -> list[dict]:
        kind = _kind(kind)
        candidates = []
        configured = configured or {}
        saved = configured.get("path", configured.get(kind, configured.get(kind + "Exe")))
        if isinstance(saved, dict):
            saved = saved.get("path")
        if isinstance(saved, str):
            candidates.append(saved)
        for name in _NAMES[kind]:
            found = shutil.which(name)
            if found:
                candidates.append(found)
        candidates.extend(self._registry_candidates(kind))
        if kind == "desktop":
            entries = self._apps_folder()
            families = {entry["aumid"].split("!", 1)[0] for entry in entries
                        if _AUMID.fullmatch(entry["aumid"]) and
                        (entry["name"].casefold() in ("codex", "chatgpt") or entry["aumid"].startswith("OpenAI."))}
            for package in self._registered_packages(entries):
                if package["family"] in families:
                    candidates.extend(app["path"] for app in self._manifest_applications(package)
                                      if ntpath.basename(app["path"]).casefold() in {name.casefold() for name in _NAMES[kind]})
        elif kind in ("photoshop", "udt"):
            for variable in ("ProgramFiles", "ProgramFiles(x86)"):
                directory = os.environ.get(variable)
                if not directory:
                    continue
                adobe = Path(directory) / "Adobe"
                try:
                    folders = list(adobe.iterdir()) if adobe.is_dir() else []
                except OSError as error:
                    raise LauncherError("Adobe installation discovery failed.") from error
                if len(folders) > 4096:
                    raise LauncherError("Adobe installation directory exceeds its safety bound.")
                prefix = "adobe photoshop " if kind == "photoshop" else "adobe uxp developer"
                for folder in folders:
                    if folder.name.casefold().startswith(prefix) and folder.is_dir():
                        candidates.extend(str(folder / name) for name in _NAMES[kind])
        elif kind == "godot" and absolute_local_path(saved):
            directory = Path(saved).parent
            try:
                nearby = list(directory.glob("Godot*.exe")) if directory.is_dir() else []
            except OSError as error:
                raise LauncherError("Saved Godot installation directory could not be inspected.") from error
            if len(nearby) > 4096:
                raise LauncherError("Godot installation directory exceeds its safety bound.")
            candidates.extend(str(path) for path in nearby)
        valid = []
        for path in candidates:
            try:
                app = self.validate_application(kind, path)
            except LauncherError:
                continue
            if not any(_same_path(app["path"], existing["path"]) for existing in valid):
                valid.append(app)
        return sorted(valid, key=lambda app: app["path"])

    def processes(self) -> list[Process]:
        try:
            records = _RawDispatch(_wmi_dispatch().call(
                "ExecQuery", "SELECT ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine, Name FROM Win32_Process"
            ))
            return [Process(pid=int(row.get("ProcessId")), parent_pid=int(row.get("ParentProcessId")),
                            created=_wmi_created(row.get("CreationDate")), executable=row.get("ExecutablePath") or None,
                            command_line=row.get("CommandLine") or None, name=str(row.get("Name") or ""))
                    for row in records.items()]
        except Exception as error:
            raise LauncherError("Windows process inspection failed; no empty-list fallback is permitted.") from error

    def port_owners(self, port: int) -> list[int]:
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise LauncherError("Invalid TCP port.")
        return _api().port_owners(port)

    def _verified_handle(self, process: Process, terminate: bool = False):
        if type(process.pid) is not int or process.pid <= 0 or type(process.created) is not int or process.created <= 0 or not process.executable:
            raise LauncherError("Process identity is incomplete; refusing mutation.")
        records = [row for row in self.processes() if row.pid == process.pid]
        if not records:
            return None
        if len(records) != 1 or not process_identity(records[0], process):
            raise LauncherError("Process identity changed; refusing mutation.")
        native = _api()
        handle = native.kernel.OpenProcess(0x1000 | 0x100000 | (1 if terminate else 0), False, process.pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return None
            raise LauncherError("Process handle could not be obtained; refusing mutation.")
        try:
            created, executable = native.process_identity(handle)
            if created != process.created or not _same_path(executable, process.executable):
                raise LauncherError("Held process identity changed; refusing mutation.")
            return handle
        except BaseException:
            native.kernel.CloseHandle(handle)
            raise

    def request_close(self, process: Process) -> None:
        handle = self._verified_handle(process)
        if handle is None:
            return
        native = _api()
        try:
            if not _process_running(native, handle):
                return
            selected = []
            @native.enum_callback
            def callback(window, _):
                pid = wintypes.DWORD()
                native.user.GetWindowThreadProcessId(window, ctypes.byref(pid))
                if pid.value == process.pid and native.user.IsWindowVisible(window) and not native.user.GetWindow(window, 4):
                    selected.append(window)
                    return False
                return True
            ctypes.set_last_error(0)
            result = native.user.EnumWindows(callback, 0)
            if not result and not selected and ctypes.get_last_error():
                raise LauncherError("Desktop window inspection failed.")
            if selected:
                pid = wintypes.DWORD()
                native.user.GetWindowThreadProcessId(selected[0], ctypes.byref(pid))
                if pid.value == process.pid and _process_running(native, handle):
                    if not native.user.PostMessageW(selected[0], 0x10, 0, 0) and ctypes.get_last_error() != 1400:
                        raise LauncherError("Verified Desktop close request failed.")
        finally:
            native.kernel.CloseHandle(handle)

    def stop_verified(self, process: Process) -> None:
        handle = self._verified_handle(process, terminate=True)
        if handle is None:
            return
        native = _api()
        try:
            if not _process_running(native, handle):
                return
            if not native.kernel.TerminateProcess(handle, 1):
                if not _process_running(native, handle):
                    return
                raise LauncherError("Verified process termination failed.")
            if native.kernel.WaitForSingleObject(handle, 5000) != 0:
                raise LauncherError("Verified process did not exit.")
        finally:
            native.kernel.CloseHandle(handle)

    def detached_flags(self) -> dict:
        return {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}

    def spawn_application(self, app: dict, cwd: Path) -> None:
        kind = _kind(app.get("kind", "desktop" if app.get("aumid") else ""))
        if kind == "godot":
            raise LauncherError("Godot launch belongs to the checkout-aware workflow.")
        current = self.validate_application(kind, app["path"])
        if current.get("aumid") != app.get("aumid"):
            raise LauncherError("Desktop activation identity changed before launch.")
        flags = self.detached_flags()
        flags["close_fds"] = True
        try:
            if current.get("aumid"):
                subprocess.Popen([str(Path(os.environ["WINDIR"]) / "explorer.exe"),
                                  "shell:AppsFolder\\" + current["aumid"]],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, **flags)
            else:
                subprocess.Popen([current["path"]], cwd=cwd, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        except OSError as error:
            raise LauncherError("Application launch failed; no retry or fallback was attempted.") from error
