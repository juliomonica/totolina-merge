"""Tooling-only tests. No Photoshop, Godot or real pairing token is required."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import secrets
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic
import unittest
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from websockets.asyncio.client import connect

from core import config as config_module
from core.config import Config, ConfigurationError, ENDPOINT, HOST, PORT, ROOT, load_config
from core.server import create_server, live_test
from modules.photoshop.bridge import PhotoshopBridge
from modules.photoshop.png_validation import read_png
from modules.photoshop.protocol import (BRIDGE_VERSION, BridgeError, MAX_PAYLOAD_BYTES, PROTOCOL_VERSION,
                                       decode, encode, envelope, validate_result, validate_response)
from tests.fake_photoshop_client import ACTIVE_DOCUMENT, FakePhotoshopClient, NO_DOCUMENT, PING


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / ".local").mkdir(exist_ok=True)

    def test_wire_rejects_binary_bad_version_duplicate_fields_and_oversize(self):
        for raw in (b"binary", "[]", '{"protocol_version":2}',
                    '{"protocol_version":1,"protocol_version":1}',
                    '{"protocol_version":NaN}', "x" * (MAX_PAYLOAD_BYTES + 1)):
            with self.subTest(raw_type=type(raw).__name__, length=len(raw)):
                with self.assertRaises(BridgeError):
                    decode(raw)

    def test_invalid_response_types_are_safe_errors(self):
        for operation in ([], {}, None, 3):
            with self.subTest(operation=operation):
                with self.assertRaises(BridgeError):
                    validate_response({"type": "response", "protocol_version": 1, "id": "abc",
                                       "operation": operation, "ok": True, "result": {}, "error": None})

    def test_ping_accepts_host_name_and_preserves_existing_version_fields(self):
        data = {**PING, "host_name": "photoshop"}
        validate_result("photoshop_ping", data)
        validate_response({"type": "response", "protocol_version": PROTOCOL_VERSION, "id": "ping",
                           "operation": "photoshop_ping", "ok": True, "result": data, "error": None})
        result = envelope(data)
        self.assertEqual(result["result"], {**PING, "host_name": "photoshop"})
        self.assertEqual(result["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(result["bridge_version"], BRIDGE_VERSION)

    def test_ping_accepts_omitted_host_name_for_older_plugins(self):
        data = deepcopy(PING)
        self.assertNotIn("host_name", data)
        validate_result("photoshop_ping", data)
        self.assertEqual(envelope(data)["result"], PING)

    def test_optional_host_name_does_not_relax_other_ping_validation(self):
        invalid_names = [None, False, 27, [], {}, "", "   ", "x" * 100]
        for name in invalid_names:
            with self.subTest(host_name=name):
                with self.assertRaises(BridgeError) as caught:
                    validate_result("photoshop_ping", {**PING, "host_name": name})
                self.assertEqual(caught.exception.code, "INVALID_MESSAGE")
        for field in PING:
            data = {**PING, "host_name": "photoshop"}
            del data[field]
            with self.subTest(missing_field=field), self.assertRaises(BridgeError):
                validate_result("photoshop_ping", data)
        with self.assertRaises(BridgeError):
            validate_result("photoshop_ping", {**PING, "host_name": "photoshop", "unexpected": "value"})

    def test_host_detection_failed_is_a_structured_error(self):
        code = "HOST_DETECTION_FAILED"
        for operation in ("photoshop_ping", "photoshop_get_active_document"):
            with self.subTest(operation=operation):
                validate_response({"type": "response", "protocol_version": PROTOCOL_VERSION, "id": "failure",
                                   "operation": operation, "ok": False, "result": None,
                                   "error": {"code": code, "message": "untrusted peer detail"}})
        result = envelope(error=BridgeError(code, connected=True))
        self.assertFalse(result["ok"])
        self.assertTrue(result["connected"])
        self.assertIsNone(result["result"])
        self.assertEqual(result["error"]["code"], code)
        self.assertIn("Adobe host metadata", result["error"]["message"])
        self.assertNotIn("untrusted", result["error"]["message"])

    def test_document_read_failure_stays_distinct_from_host_detection(self):
        code = "PHOTOSHOP_READ_FAILED"
        validate_response({"type": "response", "protocol_version": PROTOCOL_VERSION, "id": "failure",
                           "operation": "photoshop_get_active_document", "ok": False, "result": None,
                           "error": {"code": code, "message": "untrusted document detail"}})
        result = envelope(error=BridgeError(code, connected=True))
        self.assertEqual(result["error"]["code"], code)
        self.assertIn("current document", result["error"]["message"])
        self.assertNotEqual(result["error"], envelope(error=BridgeError("HOST_DETECTION_FAILED"))["error"])

    def test_inconsistent_counts_and_duplicate_ids_are_rejected(self):
        for mutate in (lambda d: d.update(recursive_layer_count=500),
                       lambda d: d["layers"][1].update(id=1),
                       lambda d: d.update(width_px=float("nan")),
                       lambda d: d.update(artboards=[{"id": 500, "name": "missing"}])):
            data = deepcopy(ACTIVE_DOCUMENT)
            mutate(data["document"])
            with self.assertRaises(BridgeError):
                validate_result("photoshop_get_active_document", data)

    def test_config_rejects_lan_host_and_unbounded_timeouts(self):
        for value in (0, -1, 31, float("nan"), float("inf"), True):
            with self.assertRaises(ConfigurationError):
                Config(request_timeout_seconds=value)
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as directory:
            path = Path(directory) / "config.toml"
            path.write_text('host = "0.0.0.0"\n', encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_config(path)

    def test_setup_creates_once_and_does_not_expose_or_replace_token(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as directory:
            root = Path(directory)
            path = root / ".local" / "pairing-token.txt"
            with patch.object(config_module, "ROOT", root), patch.object(config_module, "TOKEN_PATH", path):
                self.assertIsNone(config_module.load_token())
                self.assertEqual(config_module.setup_token(), path)
                token = config_module.load_token()
                self.assertTrue(config_module.valid_token(token))
                config_module.setup_token()
                self.assertEqual(config_module.load_token(), token)

    def test_manifest_permission_and_version_contract(self):
        manifest = json.loads((ROOT / "bridges/photoshop_uxp/manifest.json").read_text())
        self.assertEqual(manifest["manifestVersion"], 5)
        self.assertEqual(manifest["host"], {"app": "PS", "minVersion": "27.10.0", "data": {"apiVersion": 2, "loadEvent": "startup"}})
        self.assertEqual(manifest["id"], "com.lunitora.photoshop.bridge")
        self.assertEqual(manifest["requiredPermissions"], {"network": {"domains": ["ws://localhost/"]}})
        self.assertEqual(ENDPOINT, "ws://localhost:43127")

    def test_manifest_declares_plugin_packaging_icons(self):
        manifest = json.loads((ROOT / "bridges/photoshop_uxp/manifest.json").read_text())
        self.assertEqual(manifest.get("icons"), [{
            "width": 24, "height": 24, "path": "icons/lunitora-plugin.png",
            "scale": [1, 2], "theme": ["all"], "species": ["pluginList"],
        }])

    def test_manifest_declares_panel_presentation_icons(self):
        manifest = json.loads((ROOT / "bridges/photoshop_uxp/manifest.json").read_text())
        panels = [entry for entry in manifest["entrypoints"] if entry["type"] == "panel"]
        self.assertEqual([panel["id"] for panel in panels], ["lunitora-photoshop"])
        self.assertEqual(panels[0].get("icons"), [{
            "width": 23, "height": 23, "path": "icons/lunitora-panel.png",
            "scale": [1, 2], "theme": ["all"], "species": ["generic"],
        }])

    def test_package_contains_valid_pngs_for_every_declared_icon_density(self):
        plugin_root = ROOT / "bridges/photoshop_uxp"
        manifest = json.loads((plugin_root / "manifest.json").read_text())
        icons = manifest["icons"] + [icon for entry in manifest["entrypoints"]
                                    if entry["type"] == "panel" for icon in entry["icons"]]
        declared_files = set()
        for icon in icons:
            logical_path = Path(icon["path"])
            self.assertEqual(logical_path.parent.as_posix(), "icons")
            self.assertEqual(logical_path.suffix, ".png")
            self.assertNotIn("@", logical_path.name)
            for scale in icon["scale"]:
                asset = logical_path.with_name(f"{logical_path.stem}@{scale}x.png")
                declared_files.add(asset.name)
                with self.subTest(asset=asset.as_posix()):
                    data = (plugin_root / asset).read_bytes()
                    self.assertLessEqual(len(data), 1024 * 1024)
                    image = read_png(data)  # Full decode, CRC, RGBA8 and non-interlacing checks.
                    self.assertEqual((image.width, image.height),
                                     (icon["width"] * scale, icon["height"] * scale))
                    self.assertEqual(image.color_type, 6)
                    self.assertTrue(image.has_transparency)
                    self.assertIn(255, image.pixels[3::4], "Icon must contain visible artwork")
        self.assertEqual({asset.name for asset in (plugin_root / "icons").iterdir()}, declared_files)


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token = secrets.token_urlsafe(48)
        self.bridge = PhotoshopBridge(Config(request_timeout_seconds=0.2,
                                             authentication_timeout_seconds=0.2), self.token)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error, "Fixed test port is occupied; no process will be stopped.")

    async def asyncTearDown(self):
        await self.bridge.stop()

    async def assert_code(self, operation, code):
        with self.assertRaises(BridgeError) as caught:
            await self.bridge.request(operation)
        self.assertEqual(caught.exception.code, code)

    async def test_binds_only_ipv4_loopback(self):
        self.assertEqual((HOST, PORT), ("127.0.0.1", 43127))
        self.assertTrue(self.bridge._server.sockets)
        for server_socket in self.bridge._server.sockets:
            self.assertEqual(server_socket.getsockname(), ("127.0.0.1", 43127))
            self.assertEqual(server_socket.family, socket.AF_INET)

    async def test_ping_requires_two_fresh_responses(self):
        async with FakePhotoshopClient(self.token) as peer:
            first, elapsed = await self.bridge.request("photoshop_ping")
            second, _ = await self.bridge.request("photoshop_ping")
            self.assertEqual(first, PING)
            self.assertEqual(second, PING)
            self.assertGreaterEqual(elapsed, 0)
            self.assertEqual(len(peer.requests), 2)
            self.assertNotEqual(peer.requests[0]["id"], peer.requests[1]["id"])

    async def test_disconnected(self):
        await self.assert_code("photoshop_ping", "DISCONNECTED")

    async def test_timeout_and_pending_cleanup(self):
        async with FakePhotoshopClient(self.token, ignore=True):
            await self.assert_code("photoshop_ping", "TIMEOUT")
            self.assertEqual(self.bridge._pending, {})

    async def test_late_response_cannot_satisfy_a_new_request(self):
        async with FakePhotoshopClient(self.token, delay=0.25) as peer:
            await self.assert_code("photoshop_ping", "TIMEOUT")
            peer.delay = 0
            result, _ = await self.bridge.request("photoshop_ping")
            self.assertEqual(result, PING)
            self.assertEqual(len(peer.requests), 2)

    async def test_invalid_token_cannot_replace_authenticated_peer(self):
        async with FakePhotoshopClient(self.token) as peer:
            async with connect(ENDPOINT, family=socket.AF_INET, proxy=None) as intruder:
                await intruder.send(encode({"type": "auth", "protocol_version": 1,
                                            "token": secrets.token_urlsafe(48)}))
                message = decode(await intruder.recv())
                self.assertFalse(message["ok"])
                self.assertEqual(message["error"]["code"], "AUTH_FAILED")
                await intruder.wait_closed()
            result, _ = await self.bridge.request("photoshop_ping")
            self.assertEqual(result, PING)
            self.assertEqual(len(peer.requests), 1)

    async def test_no_auth_times_out(self):
        async with connect(ENDPOINT, family=socket.AF_INET, proxy=None) as peer:
            message = decode(await asyncio.wait_for(peer.recv(), 1))
            self.assertEqual(message["error"]["code"], "AUTH_FAILED")
            await peer.wait_closed()
        await self.assert_code("photoshop_ping", "DISCONNECTED")

    async def test_request_before_auth_is_rejected(self):
        async with connect(ENDPOINT, family=socket.AF_INET, proxy=None) as peer:
            await peer.send(encode({"type": "request", "protocol_version": 1,
                                    "id": "x", "operation": "photoshop_ping"}))
            self.assertEqual(decode(await peer.recv())["error"]["code"], "AUTH_FAILED")

    async def test_unsupported_operation_is_never_sent(self):
        async with FakePhotoshopClient(self.token) as peer:
            await self.assert_code("photoshop_export_png", "UNSUPPORTED_OPERATION")
            self.assertEqual(peer.requests, [])

    async def test_no_document(self):
        async with FakePhotoshopClient(self.token):
            data, _ = await self.bridge.request("photoshop_get_active_document")
            self.assertEqual(data, NO_DOCUMENT)

    async def test_document_nested_groups_duplicate_names_unicode_and_artboards(self):
        async with FakePhotoshopClient(self.token, document=ACTIVE_DOCUMENT):
            data, _ = await self.bridge.request("photoshop_get_active_document")
            self.assertEqual(data, ACTIVE_DOCUMENT)
            doc = data["document"]
            self.assertEqual([x["id"] for x in doc["layers"]], [1, 5])
            self.assertEqual([x["name"] for x in doc["layers"][0]["children"]], ["Eyes", "Eyes"])
            self.assertEqual(doc["recursive_layer_count"], 5)

    async def test_response_operation_mismatch_is_rejected(self):
        async with FakePhotoshopClient(self.token, mutate=lambda r: r.update(
                operation="photoshop_get_active_document", result=NO_DOCUMENT)):
            await self.assert_code("photoshop_ping", "INVALID_MESSAGE")

    async def test_malformed_response_fails_safely(self):
        async with FakePhotoshopClient(self.token, mutate=lambda r: r.update(operation=[])):
            await self.assert_code("photoshop_ping", "INVALID_MESSAGE")

    async def test_reconnect_replaces_previous_peer_without_duplicate_handlers(self):
        async with FakePhotoshopClient(self.token) as first:
            await self.bridge.request("photoshop_ping")
            async with FakePhotoshopClient(self.token) as second:
                await first.socket.wait_closed()
                await self.bridge.request("photoshop_ping")
                await self.bridge.request("photoshop_ping")
                self.assertEqual(len(first.requests), 1)
                self.assertEqual(len(second.requests), 2)
                self.assertEqual(self.bridge._pending, {})

    async def test_disconnect_during_request(self):
        async with FakePhotoshopClient(self.token, ignore=True) as peer:
            task = asyncio.create_task(self.bridge.request("photoshop_ping"))
            while not peer.requests:
                await asyncio.sleep(0.005)
            await peer.socket.close()
            with self.assertRaises(BridgeError) as caught:
                await task
            self.assertEqual(caught.exception.code, "DISCONNECTED")

    async def test_oversized_frame_closes_connection(self):
        async with FakePhotoshopClient(self.token) as peer:
            await peer.socket.send("x" * (MAX_PAYLOAD_BYTES + 1))
            await asyncio.wait_for(peer.socket.wait_closed(), 2)
            self.assertEqual(peer.socket.close_code, 1009)

    async def test_pending_requests_are_bounded(self):
        async with FakePhotoshopClient(self.token, ignore=True):
            tasks = [asyncio.create_task(self.bridge.request("photoshop_ping")) for _ in range(17)]
            replies = await asyncio.gather(*tasks, return_exceptions=True)
            codes = [reply.code for reply in replies if isinstance(reply, BridgeError)]
            self.assertEqual(codes.count("BUSY"), 1)
            self.assertEqual(codes.count("TIMEOUT"), 16)


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_ping_output_schema_and_results_allow_optional_host_name(self):
        token = secrets.token_urlsafe(48)
        async with Client(create_server(Config(), token)) as client:
            listing = await client.list_tools()
            schema = next(tool.output_schema for tool in listing.tools if tool.name == "photoshop_ping")
            ping_schema = schema["$defs"]["PingData"]
            self.assertEqual(ping_schema["properties"]["host_name"]["type"], "string")
            self.assertNotIn("host_name", ping_schema["required"])
            self.assertEqual(set(ping_schema["required"]), set(PING))
            for include_name in (False, True):
                def add_name(response):
                    if include_name:
                        response["result"]["host_name"] = "photoshop"
                with self.subTest(include_name=include_name):
                    async with FakePhotoshopClient(token, mutate=add_name):
                        reply = await client.call_tool("photoshop_ping", {})
                        self.assertFalse(reply.is_error)
                        payload = reply.structured_content
                        expected = {**PING, "host_name": "photoshop"} if include_name else PING
                        self.assertEqual(payload["result"], expected)
                        self.assertEqual(payload["protocol_version"], PROTOCOL_VERSION)
                        self.assertEqual(payload["bridge_version"], BRIDGE_VERSION)

    async def test_mcp_preserves_host_detection_and_document_read_error_codes(self):
        token = secrets.token_urlsafe(48)
        async with Client(create_server(Config(), token)) as client:
            for operation, code in (("photoshop_ping", "HOST_DETECTION_FAILED"),
                                    ("photoshop_get_active_document", "HOST_DETECTION_FAILED"),
                                    ("photoshop_get_active_document", "PHOTOSHOP_READ_FAILED")):
                def reject(response):
                    response.update(ok=False, result=None,
                                    error={"code": code, "message": "private peer detail"})
                with self.subTest(operation=operation, code=code):
                    async with FakePhotoshopClient(token, mutate=reject):
                        reply = await client.call_tool(operation, {})
                        self.assertTrue(reply.is_error)
                        self.assertTrue(reply.structured_content["connected"])
                        self.assertEqual(reply.structured_content["error"]["code"], code)
                        self.assertNotIn("private peer detail", json.dumps(reply.structured_content))

    async def test_initialize_compatible_readonly_schemas_and_disconnected_result(self):
        async with Client(create_server(Config(), secrets.token_urlsafe(48))) as client:
            listing = await client.list_tools()
            self.assertEqual({tool.name for tool in listing.tools},
                             {"photoshop_ping", "photoshop_get_active_document", "photoshop_process_image"})
            for tool in listing.tools:
                if tool.name == "photoshop_process_image":
                    self.assertFalse(tool.annotations.read_only_hint)
                    self.assertFalse(tool.annotations.idempotent_hint)
                    continue
                self.assertEqual(tool.input_schema["properties"], {})
                self.assertTrue(tool.annotations.read_only_hint)
                self.assertFalse(tool.annotations.destructive_hint)
                self.assertIsNotNone(tool.output_schema)
            reply = await client.call_tool("photoshop_ping", {})
            self.assertTrue(reply.is_error)
            self.assertFalse(reply.structured_content["connected"])
            self.assertEqual(reply.structured_content["error"]["code"], "DISCONNECTED")

    async def test_tools_with_fake_host(self):
        token = secrets.token_urlsafe(48)
        async with Client(create_server(Config(), token)) as client:
            async with FakePhotoshopClient(token, document=ACTIVE_DOCUMENT):
                ping = await client.call_tool("photoshop_ping", {})
                self.assertFalse(ping.is_error)
                self.assertEqual(ping.structured_content["result"], PING)
                doc = await client.call_tool("photoshop_get_active_document", {})
                self.assertFalse(doc.is_error)
                self.assertEqual(doc.structured_content["result"], ACTIVE_DOCUMENT)

    async def test_unpaired_server_still_lists_tools(self):
        async with Client(create_server(Config(), None)) as client:
            self.assertEqual(len((await client.list_tools()).tools), 3)
            reply = await client.call_tool("photoshop_ping", {})
            self.assertEqual(reply.structured_content["error"]["code"], "UNPAIRED")

    async def test_occupied_port_does_not_break_mcp_discovery(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, PORT))
            occupied.listen(1)
            async with Client(create_server(Config(), secrets.token_urlsafe(48))) as client:
                self.assertEqual(len((await client.list_tools()).tools), 3)
                reply = await client.call_tool("photoshop_ping", {})
                self.assertTrue(reply.is_error)
                self.assertEqual(reply.structured_content["error"]["code"], "PORT_IN_USE")

    async def test_real_stdio_legacy_initialize_and_stdout_purity(self):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-B", "-m", "core.server", cwd=ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        async def exchange(message):
            process.stdin.write((json.dumps(message) + "\n").encode())
            await process.stdin.drain()
            line = await asyncio.wait_for(process.stdout.readline(), 10)
            result = json.loads(line)  # Any diagnostic on stdout makes this fail.
            self.assertEqual(result.get("jsonrpc"), "2.0")
            self.assertEqual(result.get("id"), message["id"])
            return result
        try:
            initialized = await exchange({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                           "clientInfo": {"name": "phase1-test", "version": "0.1.0"}}})
            self.assertIn("result", initialized)
            process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            listing = await exchange({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            self.assertEqual({tool["name"] for tool in listing["result"]["tools"]},
                             {"photoshop_ping", "photoshop_get_active_document", "photoshop_process_image"})
            response = await exchange({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                       "params": {"name": "photoshop_ping", "arguments": {}}})
            self.assertTrue(response["result"]["isError"])
            self.assertIn(response["result"]["structuredContent"]["error"]["code"],
                          {"UNPAIRED", "DISCONNECTED"})
            process.stdin.close()
            await asyncio.wait_for(process.wait(), 5)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(await process.stdout.read(), b"")
            self.assertNotIn(b"Traceback", await process.stderr.read())
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()






class BridgeDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, diagnostics):
        output, stdout = io.StringIO(), io.StringIO()
        token, invalid = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        bridge = PhotoshopBridge(Config(), token, diagnostics=diagnostics)
        with redirect_stderr(output), redirect_stdout(stdout):
            await bridge.start()
            self.assertIsNone(bridge.startup_error)
            try:
                async with FakePhotoshopClient(token) as peer:
                    await bridge.request("photoshop_ping")
                    async with connect(ENDPOINT, family=socket.AF_INET, proxy=None) as intruder:
                        await intruder.send(encode({"type": "auth", "protocol_version": 1, "token": invalid}))
                        self.assertEqual(decode(await intruder.recv())["error"]["code"], "AUTH_FAILED")
                        await intruder.wait_closed()
                    # Peer-controlled close reasons and unsupported operations are never echoed.
                    await peer.socket.close(1000, invalid)
                    with self.assertRaises(BridgeError):
                        await bridge.request(token)
            finally:
                await bridge.stop()
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn(token, output.getvalue())
        self.assertNotIn(invalid, output.getvalue())
        self.assertNotIn('"token"', output.getvalue())
        return output.getvalue()

    async def test_live_diagnostics_report_lifecycle_without_credentials(self):
        output = await self.exercise(True)
        for event in ("Bridge listening on 127.0.0.1:43127", "Incoming WebSocket connection accepted",
                      "Authentication message received", "Authentication accepted",
                      "Authentication rejected: code=AUTH_FAILED", "WebSocket connection closed",
                      "MCP protocol request received: operation=photoshop_ping"):
            self.assertIn(event, output)

    async def test_normal_bridge_does_not_emit_live_diagnostics(self):
        self.assertEqual(await self.exercise(False), "")


class LiveTestTests(unittest.IsolatedAsyncioTestCase):
    """Exercise the driver against a real stdio child and fake authenticated UXP."""

    def setUp(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="live-test-", dir=ROOT / ".local")
        self.assertTrue(Path(self.directory.name).resolve().is_relative_to((ROOT / ".local").resolve()))
        self.addCleanup(self.directory.cleanup)
        token_path = Path(self.directory.name) / ".local" / "pairing-token.txt"
        token_path.parent.mkdir()
        self.token = secrets.token_urlsafe(48)
        token_path.write_text(self.token, encoding="ascii")
        self.output = io.StringIO()
        self.stdout = io.StringIO()
        self.first_disconnected = asyncio.Event()
        self.calls = []
        self.tasks = []
        self.parameters_patch = patch("core.server.StdioServerParameters", side_effect=self.child_parameters)
        self.parameters_factory = self.parameters_patch.start()
        self.addCleanup(self.parameters_patch.stop)
        self.client_patch = patch("core.server.Client", side_effect=self.observed_client)
        self.client_factory = self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def child_parameters(self, **kwargs):
        self.assertEqual(kwargs["command"], sys.executable)
        self.assertEqual(kwargs["args"], ["-B", "-m", "core.server"])
        self.assertEqual(kwargs["cwd"], str(ROOT))
        self.assertEqual(kwargs["env"], {"LUNITORA_LIVE_TEST_DIAGNOSTICS": "1"})
        # Run the production entry point with disposable local credentials only.
        bootstrap = (
            "import sys; from pathlib import Path; from core import config; "
            "config.ROOT = Path(sys.argv[1]); "
            "config.TOKEN_PATH = config.ROOT / '.local' / 'pairing-token.txt'; "
            "from core.server import main; sys.argv = ['core.server']; "
            "raise SystemExit(main())"
        )
        return StdioServerParameters(command=sys.executable,
                                     args=["-B", "-c", bootstrap, self.directory.name], cwd=str(ROOT),
                                     env=kwargs["env"])

    def observed_client(self, *args, **kwargs):
        client = Client(*args, **kwargs)
        original_call = client.call_tool

        async def observe(name, arguments):
            reply = await original_call(name, arguments)
            self.calls.append((name, reply.structured_content))
            if reply.is_error and reply.structured_content["error"]["code"] == "DISCONNECTED":
                self.first_disconnected.set()
            return reply

        client.call_tool = observe
        return client

    async def asyncTearDown(self):
        for task in self.tasks:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    def start_driver(self, wait_seconds):
        async def run():
            with redirect_stderr(self.output), redirect_stdout(self.stdout):
                return await live_test(None, wait_seconds)
        task = asyncio.create_task(run())
        self.tasks.append(task)
        return task

    async def pair_after_waiting(self, task, *, delay=0.65, **kwargs):
        await asyncio.wait_for(self.first_disconnected.wait(), 5)
        await asyncio.sleep(delay)
        self.assertFalse(task.done(), "Driver exited while waiting for Photoshop.")
        peer = await FakePhotoshopClient(self.token, **kwargs).__aenter__()
        self.addAsyncCleanup(peer.__aexit__, None, None, None)
        return peer

    def assert_bridge_stopped(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((HOST, PORT))

    async def test_initially_disconnected_then_connects_before_deadline(self):
        task = self.start_driver(5)
        peer = await self.pair_after_waiting(task, document=ACTIVE_DOCUMENT)
        self.assertEqual(await asyncio.wait_for(task, 5), 0)
        self.assertGreaterEqual(sum(data["error"] is not None for _, data in self.calls), 2)
        self.assertIn("Waiting for Photoshop", self.output.getvalue())
        self.assertIn(ACTIVE_DOCUMENT["document"]["name"], self.output.getvalue())
        child_output = self.output.getvalue()
        for event in ("Bridge listening on 127.0.0.1:43127", "Incoming WebSocket connection accepted",
                      "Authentication message received", "Authentication accepted", "WebSocket connection closed",
                      "MCP protocol request received: operation=photoshop_get_active_document"):
            self.assertIn(event, child_output)
        self.assertNotIn(self.token, child_output + self.output.getvalue())
        self.assertIn('"photoshop_ping"', self.output.getvalue())
        self.assertIn('"photoshop_get_active_document"', self.output.getvalue())
        await asyncio.wait_for(peer.socket.wait_closed(), 1)
        self.assert_bridge_stopped()

    async def test_disconnected_wait_expires_with_timeout(self):
        started = monotonic()
        task = self.start_driver(1)
        self.assertEqual(await asyncio.wait_for(task, 5), 1)
        self.assertGreaterEqual(monotonic() - started, 1)
        self.assertGreaterEqual(len(self.calls), 2)
        self.assertTrue(all(name == "photoshop_ping" for name, _ in self.calls))
        self.assertIn("Timed out", self.output.getvalue())
        self.assertIn('"code": "TIMEOUT"', self.output.getvalue())
        self.assertNotIn('"code": "DISCONNECTED"', self.output.getvalue())
        self.assert_bridge_stopped()

    async def test_success_has_one_handler_and_cleans_up_between_runs(self):
        request_ids = []
        for _ in range(2):
            self.first_disconnected.clear()
            task = self.start_driver(5)
            peer = await self.pair_after_waiting(task)
            self.assertEqual(await asyncio.wait_for(task, 5), 0)
            await asyncio.wait_for(peer.socket.wait_closed(), 1)
            self.assertEqual([r["operation"] for r in peer.requests],
                             ["photoshop_ping", "photoshop_get_active_document"])
            request_ids.extend(r["id"] for r in peer.requests)
            self.assert_bridge_stopped()
        self.assertEqual(len(set(request_ids)), 4)
        self.assertEqual(self.client_factory.call_count, 2)
        self.assertEqual(self.parameters_factory.call_count, 2)

    async def test_wait_deadline_also_bounds_an_unresponsive_ping(self):
        task = self.start_driver(1)
        peer = await self.pair_after_waiting(task, delay=0.1, ignore=True)
        self.assertEqual(await asyncio.wait_for(task, 3), 1)
        self.assertEqual([r["operation"] for r in peer.requests], ["photoshop_ping"])
        self.assertIn("Timed out", self.output.getvalue())
        await asyncio.wait_for(peer.socket.wait_closed(), 1)
        self.assert_bridge_stopped()

    async def test_authentication_and_protocol_errors_fail_without_retry(self):
        for code in ("AUTH_FAILED", "INVALID_MESSAGE"):
            with self.subTest(code=code):
                self.first_disconnected.clear()
                def reject(response):
                    response.update(ok=False, result=None, error={"code": code, "message": "Test failure"})
                task = self.start_driver(10)
                peer = await self.pair_after_waiting(task, delay=0.1, mutate=reject)
                self.assertEqual(await asyncio.wait_for(task, 2), 1)
                self.assertEqual([r["operation"] for r in peer.requests], ["photoshop_ping"])
                self.assertIn('"code": "' + code + '"', self.output.getvalue())
                self.assertNotIn("Timed out", self.output.getvalue())
                self.assert_bridge_stopped()



    async def test_startup_failure_reports_exit_paths_and_sanitized_stderr(self):
        script = (
            "import sys; from pathlib import Path; "
            "value = Path(sys.argv[1]).read_text(); "
            "print('RuntimeError: simulated child startup failure', file=sys.stderr); "
            "print('password=private-startup-value ' + value, file=sys.stderr); "
            "raise SystemExit(23)"
        )
        self.parameters_factory.side_effect = lambda **_: StdioServerParameters(
            command=sys.executable, args=["-B", "-c", script,
                str(Path(self.directory.name) / ".local" / "pairing-token.txt")], cwd=str(ROOT))
        self.assertEqual(await asyncio.wait_for(self.start_driver(5), 5), 1)
        output = self.output.getvalue()
        for expected in ("failed during initialization", "Child executable: " + sys.executable,
                         "Child cwd: " + str(ROOT), "Child exit code: 23",
                         "Port 127.0.0.1:43127 already occupied before spawn: no",
                         "Child stderr (sanitized", "simulated child startup failure"):
            self.assertIn(expected, output)
        self.assertNotIn(self.token, output)
        self.assertNotIn("private-startup-value", output)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.calls, [])
        self.assert_bridge_stopped()

    async def test_occupied_port_does_not_close_mcp_during_initialization(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, PORT))
            occupied.listen(1)
            self.assertEqual(await asyncio.wait_for(self.start_driver(5), 5), 1)
            child = self.client_factory.call_args.args[0]
            self.assertEqual(child.port_was_occupied, "yes")
            self.assertEqual(child.process.returncode, 0)
            self.assertFalse(child.forced_stop)
            self.assertIn('"code": "PORT_IN_USE"', self.output.getvalue())
            self.assertNotIn("failed during initialization", self.output.getvalue())
            self.assertEqual(occupied.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN), 1)
            self.assertEqual(self.stdout.getvalue(), "")

    async def test_startup_failure_reports_preexisting_occupied_port(self):
        self.parameters_factory.side_effect = lambda **_: StdioServerParameters(
            command=sys.executable, args=["-B", "-c", "raise SystemExit(19)"], cwd=str(ROOT))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, PORT))
            occupied.listen(1)
            self.assertEqual(await asyncio.wait_for(self.start_driver(5), 5), 1)
            self.assertIn("Child exit code: 19", self.output.getvalue())
            self.assertIn("already occupied before spawn: yes", self.output.getvalue())

    async def test_missing_executable_reports_unavailable_exit_without_traceback(self):
        missing = str(ROOT / ".local" / "missing-python.exe")
        self.parameters_factory.side_effect = lambda **_: StdioServerParameters(
            command=missing, cwd=str(ROOT))
        self.assertEqual(await asyncio.wait_for(self.start_driver(5), 5), 1)
        self.assertIn("Child executable: " + missing, self.output.getvalue())
        self.assertIn("Child exit code: unavailable", self.output.getvalue())
        self.assertNotIn("Traceback", self.output.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

    async def test_invalid_child_stdout_is_reported_without_echoing_raw_data(self):
        script = ("import sys; from pathlib import Path; print(Path(sys.argv[1]).read_text()); "
                  "raise SystemExit(17)")
        self.parameters_factory.side_effect = lambda **_: StdioServerParameters(
            command=sys.executable, args=["-B", "-c", script,
                str(Path(self.directory.name) / ".local" / "pairing-token.txt")], cwd=str(ROOT))
        self.assertEqual(await asyncio.wait_for(self.start_driver(5), 5), 1)
        self.assertIn("Non-MCP stdout observed: yes", self.output.getvalue())
        self.assertNotIn(self.token, self.output.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

if __name__ == "__main__":
    (ROOT / ".local").mkdir(exist_ok=True)
    unittest.main(verbosity=2)
