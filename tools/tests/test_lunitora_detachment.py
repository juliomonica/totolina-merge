"""Mocked log contracts and one isolated native child; no real apps or MCP."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from lunitora_machine import logs, workflows
from lunitora_machine.policy import LauncherError, Process, same_path

ROOT = Path(r"D:\Game Projects\Totolina Merge")
APPS = {"godot": {"kind": "godot", "path": r"C:\Tools\Godot.exe"}}


def process(pid, path, command):
    return Process(pid, 0, 100, path, command, "Godot.exe")


class FakePlatform:
    def __init__(self, processes=()):
        self.items = list(processes)

    def processes(self):
        return list(self.items)

    def detached_flags(self):
        return {"creationflags": 123}


class LogTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(tempfile.TemporaryDirectory(prefix="lunitora log tests "))
        self.temp = Path(self.directory)
        self.root = self.temp / "project"
        self.root.mkdir()
        self.enterContext(patch.object(logs.tempfile, "gettempdir", return_value=self.directory))

    def test_log_pair_is_external_unique_and_registered(self):
        first = logs.new_godot_output_logs(self.root)
        second = logs.new_godot_output_logs(self.root)
        self.assertNotEqual(first, second)
        self.assertEqual(first.stdout.parent, self.temp / "lunitora-godot-launcher")
        match = re.fullmatch(r"godot-([a-f0-9]{32})\.stdout\.log", first.stdout.name)
        self.assertIsNotNone(match)
        self.assertEqual(first.stderr.name, f"godot-{match[1]}.stderr.log")
        self.assertFalse(first.stdout.parent.is_relative_to(self.root))

    def test_cleanup_only_removes_matching_plain_old_files(self):
        folder = self.temp / "lunitora-godot-launcher"
        folder.mkdir()
        stale = folder / ("godot-" + "a" * 32 + ".stdout.log")
        fresh = folder / ("godot-" + "b" * 32 + ".stderr.log")
        unrelated = folder / "keep.stdout.log"
        subdirectory = folder / ("godot-" + "c" * 32 + ".stdout.log")
        for path in (stale, fresh, unrelated):
            path.write_text("fixture", encoding="ascii")
        subdirectory.mkdir()
        sentinel = subdirectory / "keep.txt"
        sentinel.write_text("fixture", encoding="ascii")
        old = time.time() - 8 * 24 * 60 * 60
        for path in (stale, unrelated, subdirectory):
            os.utime(path, (old, old))
        logs.new_godot_output_logs(self.root)
        self.assertFalse(stale.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(sentinel.read_text(), "fixture")

    def test_hardlinked_old_log_is_not_removed(self):
        folder = self.temp / "lunitora-godot-launcher"
        folder.mkdir()
        linked = folder / ("godot-" + "a" * 32 + ".stdout.log")
        linked.write_text("fixture", encoding="ascii")
        os.link(linked, self.temp / "alias.txt")
        old = time.time() - 8 * 24 * 60 * 60
        os.utime(linked, (old, old))
        logs.new_godot_output_logs(self.root)
        self.assertTrue(linked.exists())

    def test_cleanup_failure_is_best_effort(self):
        folder = self.temp / "lunitora-godot-launcher"
        folder.mkdir()
        stale = folder / ("godot-" + "a" * 32 + ".stdout.log")
        stale.touch()
        old = time.time() - 8 * 24 * 60 * 60
        os.utime(stale, (old, old))
        with patch.object(Path, "unlink", side_effect=PermissionError):
            pair = logs.new_godot_output_logs(self.root)
        self.assertTrue(stale.exists())
        self.assertNotEqual(pair.stdout, stale)

    def test_directory_reparse_is_rejected(self):
        with patch.object(logs, "_reparse", return_value=True):
            with self.assertRaisesRegex(LauncherError, "reparse"):
                logs.new_godot_output_logs(self.root)

    def test_repository_local_temp_is_rejected(self):
        with patch.object(logs.tempfile, "gettempdir", return_value=str(self.root)):
            with self.assertRaisesRegex(LauncherError, "outside the repository"):
                logs.new_godot_output_logs(self.root)

    def test_log_directory_failure_is_fatal_before_launch(self):
        with patch.object(Path, "mkdir", side_effect=PermissionError):
            with self.assertRaisesRegex(LauncherError, "storage is unavailable"):
                logs.new_godot_output_logs(self.root)


class GodotLaunchTests(unittest.TestCase):
    def test_correct_editor_reuse_allocates_no_logs_or_process(self):
        item = process(20, path=APPS["godot"]["path"],
                       command=f'"{APPS["godot"]["path"]}" --editor --path "{ROOT}"')
        with patch.object(workflows, "new_godot_output_logs") as output, patch.object(workflows.subprocess, "Popen") as popen:
            workflows.ensure_godot_editor(FakePlatform([item]), APPS["godot"], ROOT, lambda _: None)
        output.assert_not_called()
        popen.assert_not_called()

    def test_godot_launch_contract_and_separate_closed_parent_handles(self):
        with tempfile.TemporaryDirectory(prefix="lunitora spawn tests ") as temp:
            pair = logs.OutputLogs(Path(temp) / "out.log", Path(temp) / "err.log")
            messages = []
            with patch.object(workflows, "new_godot_output_logs", return_value=pair), patch.object(workflows.subprocess, "Popen") as popen:
                workflows.ensure_godot_editor(FakePlatform(), APPS["godot"], ROOT, messages.append)
            popen.assert_called_once()
            args, kwargs = popen.call_args
            self.assertEqual(args, ([APPS["godot"]["path"], "--editor", "--path", str(ROOT)],))
            self.assertEqual(kwargs["cwd"], ROOT)
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertFalse(kwargs["shell"])
            self.assertTrue(kwargs["close_fds"])
            self.assertEqual(kwargs["creationflags"], 123)
            self.assertNotIn("startupinfo", kwargs)
            self.assertNotEqual(kwargs["stdout"].name, kwargs["stderr"].name)
            self.assertTrue(kwargs["stdout"].closed and kwargs["stderr"].closed)
            self.assertTrue(any(str(pair.stdout) in message for message in messages))
            self.assertTrue(any(str(pair.stderr) in message for message in messages))

    def test_another_project_does_not_suppress_launch(self):
        item = process(20, path=APPS["godot"]["path"], command=f'"{APPS["godot"]["path"]}" -e --path "D:\\Other"')
        with tempfile.TemporaryDirectory() as temp:
            pair = logs.OutputLogs(Path(temp) / "out", Path(temp) / "err")
            with patch.object(workflows, "new_godot_output_logs", return_value=pair), patch.object(workflows.subprocess, "Popen") as popen:
                workflows.ensure_godot_editor(FakePlatform([item]), APPS["godot"], ROOT, lambda _: None)
            popen.assert_called_once()

    def test_log_failure_never_attempts_process_creation(self):
        with patch.object(workflows, "new_godot_output_logs", side_effect=LauncherError("storage")), patch.object(workflows.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(LauncherError, "storage"):
                workflows.ensure_godot_editor(FakePlatform(), APPS["godot"], ROOT, lambda _: None)
        popen.assert_not_called()

    def test_spawn_failure_is_single_attempt_and_closes_handles(self):
        with tempfile.TemporaryDirectory() as temp:
            pair = logs.OutputLogs(Path(temp) / "out", Path(temp) / "err")
            with patch.object(workflows, "new_godot_output_logs", return_value=pair), patch.object(workflows.subprocess, "Popen", side_effect=OSError("private detail")) as popen:
                with self.assertRaisesRegex(LauncherError, "no automatic retry"):
                    workflows.ensure_godot_editor(FakePlatform(), APPS["godot"], ROOT, lambda _: None)
            popen.assert_called_once()
            self.assertTrue(popen.call_args.kwargs["stdout"].closed)
            self.assertTrue(popen.call_args.kwargs["stderr"].closed)


IDENTITY_SOURCE = r'''
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetCurrentProcess.restype = wintypes.HANDLE
kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
kernel.GetProcessTimes.restype = wintypes.BOOL
kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
def identity(handle):
    times = [wintypes.FILETIME() for _ in range(4)]
    assert kernel.GetProcessTimes(handle, *[ctypes.byref(value) for value in times])
    image = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(len(image))
    assert kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size))
    return ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) // 10, image.value
def publish(path, value):
    pending = path.with_name(path.name + '.pending')
    pending.write_text(value, encoding='utf-8')
    pending.replace(path)
'''

NATIVE_SOURCE = r'''
import ctypes, json, os, sys, time, traceback
from ctypes import wintypes
from pathlib import Path
''' + IDENTITY_SOURCE + r'''
assert len(sys.argv) == 4 and sys.argv[1:3] == ['--editor', '--path']
root = Path(sys.argv[3]).resolve()
nonce = (root / 'nonce.txt').read_text(encoding='ascii')
def wait(name):
    path = root / name
    deadline = time.monotonic() + 30
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise TimeoutError('Fixture handshake timed out: ' + name)
        time.sleep(0.025)
    assert path.read_text(encoding='ascii') == nonce
try:
    created, image = identity(kernel.GetCurrentProcess())
    publish(root / 'child.json', json.dumps({'pid': os.getpid(), 'created': created,
                                            'nonce': nonce, 'image': image}))
    wait('release.txt')
    os.write(1, ('fixture-stdout-' + nonce + '\n').encode('ascii'))
    os.write(2, ('fixture-stderr-' + nonce + '\n').encode('ascii'))
    (root / 'cwd.txt').write_text(os.getcwd(), encoding='utf-8')
    publish(root / 'ready.txt', nonce)
    wait('finish.txt')
except BaseException:
    (root / 'failure.txt').write_text(traceback.format_exc(), encoding='utf-8')
    raise
'''


def wait_file(path: Path, seconds=10):
    deadline = time.monotonic() + seconds
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Fixture handshake timed out: {path.name}")
        time.sleep(0.025)


@unittest.skipUnless(os.name == "nt", "Disposable Windows native-child proof")
class NativeDetachmentTests(unittest.TestCase):
    def test_delayed_native_output_survives_one_shot_launcher_exit(self):
        nonce = uuid.uuid4().hex
        temp_base = Path(tempfile.gettempdir()).resolve()
        root = Path(tempfile.mkdtemp(prefix=f"lunitora native output {nonce} ")).resolve()
        project = root / "project"
        project.mkdir()
        executable = Path(sys._base_executable).resolve()
        handle = None
        launcher = None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        identity = None

        def prove_handle(result, metadata, expected):
            self.assertEqual(metadata["nonce"], nonce)
            self.assertIs(type(metadata["pid"]), int)
            self.assertGreater(metadata["pid"], 0)
            self.assertIs(type(metadata["created"]), int)
            times = [wintypes.FILETIME() for _ in range(4)]
            self.assertTrue(kernel.GetProcessTimes(result, *[ctypes.byref(value) for value in times]))
            created = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) // 10
            self.assertEqual(created, metadata["created"])
            image = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(image))
            self.assertTrue(kernel.QueryFullProcessImageNameW(result, 0, image, ctypes.byref(size)))
            self.assertTrue(same_path(image.value, str(expected)))

        def prove_process(metadata, expected):
            result = kernel.OpenProcess(0x1000 | 0x100000 | 1, False, metadata["pid"])
            self.assertTrue(result, "Fixture process handle unavailable")
            try:
                prove_handle(result, metadata, expected)
            except BaseException:
                kernel.CloseHandle(result)
                raise
            return result

        try:
            self.assertTrue(root.is_relative_to(temp_base) and root != temp_base)
            (project / "nonce.txt").write_text(nonce, encoding="ascii")
            source = root / "fixture_child.py"
            source.write_text(NATIVE_SOURCE, encoding="ascii")
            env = dict(os.environ, TEMP=str(root), TMP=str(root), TMPDIR=str(root))
            tools = Path(__file__).resolve().parents[1]
            fixture_launcher = root / "fixture_launcher.py"
            fixture_launcher.write_text(
                "import ctypes, json, os, sys\nfrom ctypes import wintypes\nfrom pathlib import Path\n"
                + IDENTITY_SOURCE +
                "print('FIXTURE_LAUNCHER_STARTED', flush=True)\n"
                "created, image = identity(kernel.GetCurrentProcess())\n"
                f"data = {{'pid': os.getpid(), 'created': created, 'nonce': {nonce!r}, 'image': image}}\n"
                f"publish(Path({str(project / 'launcher.json')!r}), json.dumps(data))\n"
                f"sys.path.insert(0, {str(tools)!r})\n"
                "from lunitora_machine import workflows\n"
                "from lunitora_machine.platforms.windows import WindowsPlatform\n"
                "class FixturePlatform(WindowsPlatform):\n"
                "    def processes(self): return []\n"
                "actual_spawn = workflows.subprocess.Popen\nchildren = []\n"
                "def fixture_spawn(argv, **kwargs):\n"
                f"    assert argv == [{str(executable)!r}, '--editor', '--path', {str(project)!r}]\n"
                "    assert not children, 'Only one native launch attempt is permitted'\n"
                f"    child = actual_spawn([argv[0], '-I', '-B', {str(source)!r}, *argv[1:]], **kwargs)\n"
                "    children.append(child)\n"
                "    created, image = identity(child._handle)\n"
                f"    data = {{'pid': child.pid, 'created': created, 'nonce': {nonce!r}, 'image': image}}\n"
                f"    publish(Path({str(project / 'spawned.json')!r}), json.dumps(data))\n"
                "    return child\n"
                "workflows.subprocess.Popen = fixture_spawn\n"
                f"workflows.ensure_godot_editor(FixturePlatform(), {{'path': {str(executable)!r}}}, Path({str(project)!r}), print)\n"
                "print('FIXTURE_LAUNCHER_FINISHED', flush=True)\n", encoding="utf-8")
            stdout_path = root / "launcher.stdout.capture"
            stderr_path = root / "launcher.stderr.capture"
            with stdout_path.open("xb") as stdout_file, stderr_path.open("xb") as stderr_file:
                launcher = subprocess.Popen([str(executable), "-I", "-B", str(fixture_launcher)], cwd=root, env=env,
                                            stdin=subprocess.DEVNULL, stdout=stdout_file, stderr=stderr_file,
                                            creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
                wait_file(project / "launcher.json")
                launcher_identity = json.loads((project / "launcher.json").read_text(encoding="utf-8"))
                self.assertEqual(launcher_identity["pid"], launcher.pid)
                prove_handle(launcher._handle, launcher_identity, executable)
                # Process exit is independent of capture-handle EOF.
                try:
                    launcher.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.fail("Invoking launcher did not exit before release. Fixture stdout: "
                              + stdout_path.read_bytes().decode(errors="replace") + "; fixture stderr: "
                              + stderr_path.read_bytes().decode(errors="replace"))
            stdout = stdout_path.read_bytes()
            stderr = stderr_path.read_bytes()
            self.assertEqual(launcher.returncode, 0, stderr.decode(errors="replace"))
            self.assertIn(b"FIXTURE_LAUNCHER_FINISHED", stdout)
            self.assertFalse((project / "release.txt").exists())
            self.assertFalse((project / "ready.txt").exists())
            spawned = json.loads((project / "spawned.json").read_text(encoding="utf-8"))
            self.assertTrue(same_path(spawned["image"], str(executable)))
            self.assertEqual(kernel.WaitForSingleObject(launcher._handle, 0), 0, "Invoking Python launcher is still alive")
            handle = prove_process(spawned, executable)
            self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0x102, "Child exited before launcher return")
            wait_file(project / "child.json")
            identity = json.loads((project / "child.json").read_text(encoding="utf-8"))
            self.assertEqual(identity["pid"], spawned["pid"])
            self.assertEqual(identity["created"], spawned["created"])
            self.assertEqual(identity["nonce"], nonce)
            self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0x102, "Child exited before explicit release")
            output = next(Path(line.split(": ", 1)[1]) for line in stdout.decode().splitlines() if line.startswith("Godot stdout: "))
            error = next(Path(line.split(": ", 1)[1]) for line in stdout.decode().splitlines() if line.startswith("Godot stderr: "))
            self.assertEqual(output.parent, root / "lunitora-godot-launcher")
            self.assertEqual(error.parent, output.parent)
            self.assertEqual(output.stat().st_size, 0)
            self.assertEqual(error.stat().st_size, 0)
            (project / "release.txt").write_text(nonce, encoding="ascii")
            wait_file(project / "ready.txt")
            self.assertEqual((project / "ready.txt").read_text(), nonce)
            self.assertTrue(same_path((project / "cwd.txt").read_text(), str(project)))
            self.assertGreater(output.stat().st_size, 0)
            self.assertGreater(error.stat().st_size, 0)
            self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0x102, "Child did not wait for finish")
            (project / "finish.txt").write_text(nonce, encoding="ascii")
            self.assertEqual(kernel.WaitForSingleObject(handle, 10000), 0)
            exit_code = wintypes.DWORD()
            self.assertTrue(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
            self.assertEqual(exit_code.value, 0)
            self.assertEqual(output.read_text().strip(), f"fixture-stdout-{nonce}")
            self.assertEqual(error.read_text().strip(), f"fixture-stderr-{nonce}")
            for captured in (stdout, stderr):
                self.assertNotIn(f"fixture-stdout-{nonce}".encode(), captured)
                self.assertNotIn(f"fixture-stderr-{nonce}".encode(), captured)
            # Re-read after delayed writes: the capture files must not grow with
            # child output after the launcher has returned.
            self.assertEqual(stdout_path.read_bytes(), stdout)
            self.assertEqual(stderr_path.read_bytes(), stderr)
        finally:
            try:
                for sentinel in ("release.txt", "finish.txt"):
                    if not (project / sentinel).exists():
                        (project / sentinel).write_text(nonce, encoding="ascii")
                metadata = next((path for path in (project / "spawned.json", project / "child.json") if path.is_file()), None)
                if handle is None and metadata is not None:
                    identity = json.loads(metadata.read_text(encoding="utf-8"))
                    handle = prove_process(identity, executable)
                if handle is not None and kernel.WaitForSingleObject(handle, 2000) == 0x102:
                    # The held handle has already proven exact fixture path/time/nonce.
                    self.assertTrue(kernel.TerminateProcess(handle, 9))
                    self.assertEqual(kernel.WaitForSingleObject(handle, 5000), 0)
            finally:
                if handle is not None:
                    kernel.CloseHandle(handle)
                try:
                    if launcher is not None and launcher.poll() is None:
                        # Popen retains the exact handle for our directly launched
                        # base Python, with no venv redirector process in between.
                        launcher.kill()
                        launcher.wait(timeout=5)
                finally:
                    resolved = root.resolve()
                    self.assertEqual(resolved, root)
                    self.assertTrue(resolved.is_relative_to(temp_base) and resolved != temp_base)
                    self.assertTrue(root.name.startswith(f"lunitora native output {nonce} "))
                    self.assertFalse(root.is_symlink())
                    shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
