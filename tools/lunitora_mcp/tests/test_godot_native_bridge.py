"""Actual Godot WebSocketPeer/Crypto against Python, in disposable project copies.

These tests exercise the native client transport, not a live Codex editor session.
Only the copied client's URL is substituted with an ephemeral test listener.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from modules.godot.bridge import GodotBridge
from modules.godot.config import Config, PROJECT_ROOT, ensure_credential

GODOT_EXECUTABLE = Path(os.environ.get("GODOT_TEST_EXE",
    "D:/Development/Tools/Godot/4.7.2/Godot_v4.7.2-stable_win64.exe"))
SCRIPT = '''extends SceneTree
const BridgeClient = preload("res://addons/lunitora_godot/bridge_client.gd")
const Inspection = preload("res://addons/lunitora_godot/inspection.gd")
var bridge: RefCounted
var inspection: RefCounted
func _initialize() -> void:
    inspection = Inspection.new()
    bridge = BridgeClient.new()
    bridge.start(_dispatch)
func _process(_delta: float) -> bool:
    bridge.poll()
    return false
func _finalize() -> void:
    bridge.stop()
func _dispatch(operation: String, _params: Dictionary) -> Dictionary:
    match operation:
        "godot_ping":
            return inspection.ping("native-transport-validation")
        "godot_get_editor_state":
            var selected: Array[Node] = []
            return inspection.editor_state(null, selected, PackedStringArray(), "native-transport-validation")
        "godot_inspect_scene":
            return inspection.inspect_scene(null, PackedStringArray(), "native-transport-validation")
    return inspection.failure("UNSUPPORTED_OPERATION", "Unsupported operation.")
'''


class GodotNativeBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertTrue(GODOT_EXECUTABLE.is_file(), "Godot 4.7.2 test executable is required.")
        self.directory = tempfile.TemporaryDirectory(prefix="lunitora-godot-native-")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / "tools/lunitora_mcp").mkdir(parents=True)
        self.credential = ensure_credential(self.project)
        self.addCleanup(self.credential.close)
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=0)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.port = self.bridge.port
        self.addAsyncCleanup(self.bridge.stop)
        addon = self.project / "addons/lunitora_godot"
        addon.mkdir(parents=True)
        source = PROJECT_ROOT / "addons/lunitora_godot"
        shutil.copy2(source / "inspection.gd", addon / "inspection.gd")
        client = (source / "bridge_client.gd").read_text(encoding="utf-8")
        self.assertEqual(client.count('"ws://127.0.0.1:43128"'), 1)
        client = client.replace('"ws://127.0.0.1:43128"', f'"ws://127.0.0.1:{self.port}"')
        (addon / "bridge_client.gd").write_text(client, encoding="utf-8")
        (self.project / "project.godot").write_text('[application]\nconfig/name="Native bridge validation"\n'
            '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
        (self.project / "native_bridge.gd").write_text(SCRIPT, encoding="utf-8")
        self.process = await asyncio.create_subprocess_exec(str(GODOT_EXECUTABLE), "--headless",
            "--path", str(self.project), "--script", "res://native_bridge.gd", "--max-fps", "60",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addAsyncCleanup(self.finish_child)
        await self.wait_connected()

    async def finish_child(self):
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        stdout, stderr = await self.process.communicate()
        output = stdout + stderr
        self.assertNotIn(self.credential.secret.hex().encode(), output)
        self.assertNotIn(b"SCRIPT ERROR", output)
        self.assertNotIn(b"Parse Error", output)

    async def wait_connected(self):
        async with asyncio.timeout(10):
            while self.bridge._connection is None:
                if self.process.returncode is not None:
                    self.fail("Native client exited before mutual authentication.")
                await asyncio.sleep(0.02)

    async def test_native_mutual_auth_and_eight_concurrent_read_only_requests(self):
        operations = ["godot_ping", "godot_get_editor_state", "godot_inspect_scene"]
        results = await asyncio.gather(*(self.bridge.request(operations[index % 3], {}) for index in range(8)))
        self.assertEqual(len(results), 8)
        for index, (data, timing) in enumerate(results):
            self.assertEqual(data["editor_session_id"], "native-transport-validation")
            self.assertGreaterEqual(timing, 0)
            if index % 3 == 0:
                self.assertRegex(data["godot_version"], r"^4\.7\.2(?:[.-]|$)")
                self.assertEqual(data["project_path"], self.credential.project_path)
            if index % 3 == 2:
                self.assertEqual(data["nodes"], [])
        self.assertEqual(self.bridge._pending, {})

    async def test_native_reconnects_after_codex_owned_listener_restart(self):
        original = self.bridge._connection
        await self.bridge.request("godot_ping", {})
        await self.bridge.stop()
        self.bridge = GodotBridge(Config(request_timeout_seconds=5), self.credential, port=self.port)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.addAsyncCleanup(self.bridge.stop)
        await self.wait_connected()
        self.assertIsNot(self.bridge._connection, original)
        data, _ = await self.bridge.request("godot_ping", {})
        self.assertTrue(data["read_only"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
