"""Real stdio purity and SDK discovery/input/output contracts with disposable auth."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
import socket
import subprocess
import sys
import unittest

from jsonschema import Draft202012Validator, ValidationError
from mcp import Client

from core.godot_server import create_server
from modules.godot.config import Config, HOST, ROOT
from modules.godot.protocol import (BridgeError, MAX_PAYLOAD_BYTES, OPERATIONS, READ_OPERATIONS,
                                   WRITE_OPERATION, WRITE_OPERATIONS, ANIMATION_WRITE_OPERATION, encode, envelope, validate_result)
from modules.godot.tools import MAX_TOOL_RESULT_BYTES, MCP_ENVELOPE_RESERVE_BYTES, tool_result
from tests.fake_godot_client import FakeGodotClient, LAB_SCENE, ROOT_NODE, SAVED_SCENE, disposable_credential, ping


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def large_inspection(repeat: int, character: str = "x") -> dict:
    nodes = [dict(ROOT_NODE, child_count=40)]
    nodes.extend(dict(ROOT_NODE, path=f"Child{index}_" + character * repeat, parent_path=".") for index in range(40))
    return {"editor_session_id": "large-response-test", "scene": deepcopy(SAVED_SCENE), "nodes": nodes}


def expected_unbounded_body(payload: dict) -> dict:
    # Independent wire representation, including both compatibility views, rather
    # than calling the production size limiter to derive a boundary fixture.
    return {"content": [{"type": "text", "text": encode(payload)}],
            "structuredContent": payload, "isError": not payload["ok"], "resultType": "complete"}


def encoded_size(value: dict) -> int:
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))


def last_fitting_repeat(character: str) -> int:
    lower, upper = 0, 4000
    while lower < upper:
        candidate = (lower + upper + 1) // 2
        payload = envelope(large_inspection(candidate, character), elapsed_ms=0.0)
        if encoded_size(expected_unbounded_body(payload)) <= MAX_TOOL_RESULT_BYTES:
            lower = candidate
        else:
            upper = candidate - 1
    return lower


class GodotMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_seven_tools_with_closed_empty_inputs_and_annotations(self):
        async with Client(create_server(Config(), disposable_credential(), port=0)) as client:
            listing = (await client.list_tools()).tools
            self.assertEqual({tool.name for tool in listing}, OPERATIONS)
            for tool in listing:
                self.assertEqual(tool.input_schema["properties"], {})
                self.assertFalse(tool.input_schema["additionalProperties"])
                self.assertEqual(tool.input_schema["maxProperties"], 0)
                self.assertEqual(tool.annotations.read_only_hint, tool.name in READ_OPERATIONS)
                self.assertFalse(tool.annotations.destructive_hint)
                self.assertEqual(tool.annotations.idempotent_hint, tool.name in READ_OPERATIONS)
                self.assertFalse(tool.annotations.open_world_hint)
                self.assertFalse(tool.output_schema["additionalProperties"])
                Draft202012Validator.check_schema(tool.output_schema)

    async def test_output_schema_enforces_success_failure_and_recursive_closed_fields(self):
        credential = disposable_credential()
        server = create_server(Config(), credential, port=0)
        listing = await server.list_tools()
        schema = next(tool.output_schema for tool in listing if tool.name == "godot_ping")
        validator = Draft202012Validator(schema)
        data = envelope(ping(credential), elapsed_ms=0.1)
        validator.validate(data)
        validator.validate(envelope(error=BridgeError("DISCONNECTED")))
        for location, field, value in (("root", "connected", False), ("root", "result", None),
                                       ("root", "round_trip_ms", None), ("root", "extra", True),
                                       ("result", "tracks", [])):
            with self.subTest(location=location, field=field):
                changed = deepcopy(data)
                (changed if location == "root" else changed["result"])[field] = value
                with self.assertRaises(ValidationError):
                    validator.validate(changed)

    async def test_public_direct_calls_reject_extra_nonobjects_and_unknown_operations(self):
        server = create_server(Config(), disposable_credential(), port=0)
        for argument in (None, {"unexpected": 1}, [], "", False):
            response = await server.call_tool("godot_ping", argument)
            self.assertEqual(response.structured_content["error"]["code"], "INVALID_REQUEST")
        response = await server.call_tool("godot_save_scene", {})
        self.assertEqual(response.structured_content["error"]["code"], "UNSUPPORTED_OPERATION")

    async def test_inprocess_client_with_fake_authenticated_editor(self):
        credential, port = disposable_credential(), free_port()
        async with Client(create_server(Config(), credential, port=port)) as client:
            async with FakeGodotClient(credential, port, scene=LAB_SCENE, nodes=[ROOT_NODE]):
                for operation in (*READ_OPERATIONS, WRITE_OPERATION, ANIMATION_WRITE_OPERATION):
                    response = await client.call_tool(operation, {})
                    self.assertFalse(response.is_error)
                    self.assertTrue(response.structured_content["connected"])

    async def test_unavailable_and_conflicting_listeners_do_not_disable_discovery(self):
        async with Client(create_server(Config(), None, port=0)) as client:
            self.assertEqual(len((await client.list_tools()).tools), 7)
            response = await client.call_tool("godot_ping", {})
            self.assertEqual(response.structured_content["error"]["code"], "LOCAL_AUTH_UNSAFE")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, 0))
            occupied.listen(1)
            server = create_server(Config(), disposable_credential(), port=occupied.getsockname()[1])
            async with Client(server) as client:
                self.assertEqual(len((await client.list_tools()).tools), 7)
                response = await client.call_tool("godot_ping", {})
                self.assertEqual(response.structured_content["error"]["code"], "PORT_IN_USE")

    async def test_tool_response_bounds_both_metadata_views_and_escaped_encoding(self):
        for character in ("x", '"', "\n", "猫"):
            with self.subTest(character=repr(character)):
                repeat = last_fitting_repeat(character)
                for extra, expected_ok in ((0, True), (1, False)):
                    payload = envelope(large_inspection(repeat + extra, character), elapsed_ms=0.0)
                    validate_result("godot_inspect_scene", payload["result"])
                    self.assertLess(len(encode(payload).encode("utf-8")), MAX_PAYLOAD_BYTES)
                    response = tool_result(payload)
                    self.assertEqual(response.structured_content["ok"], expected_ok)
                    self.assertLessEqual(len(response.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")),
                                         MAX_TOOL_RESULT_BYTES)
                    if not expected_ok:
                        self.assertEqual(response.structured_content["error"]["code"], "RESPONSE_TOO_LARGE")
                        self.assertIsNone(response.structured_content["result"])
                        self.assertTrue(response.structured_content["connected"])


class GodotStdioTests(unittest.IsolatedAsyncioTestCase):
    async def child(self, *, unsafe=False, fixture=None):
        # Invoke production main with only disposable in-memory auth and ephemeral
        # listener injection. No secret is passed in argv/env or read from disk.
        bootstrap = (
            "from core import godot_server as entry; "
            "from modules.godot.config import Credential; "
            "import secrets; "
            "credential = Credential('c:/test/disposable', secrets.token_hex(32), secrets.token_bytes(32)); "
            "entry.ensure_credential = lambda: credential; "
            "factory = entry.create_server; "
            "entry.create_server = lambda config, credential, startup_error=None: "
            "factory(config, credential, startup_error=startup_error, port=0); "
        )
        if unsafe:
            bootstrap += "entry.ensure_credential = lambda: (_ for _ in ()).throw(entry.ConfigurationError()); "
        if fixture is not None:
            repeat, character = fixture
            bootstrap += "from tests.test_godot_stdio import large_inspection; "
            method = "async def fixture_request(self, operation, params=None):\n    return large_inspection(%r, %r), 0.0\n" % (repeat, character)
            bootstrap += "exec(%r); entry.GodotBridge.request = fixture_request; " % method
        bootstrap += "raise SystemExit(entry.main())"
        process = await asyncio.create_subprocess_exec(sys.executable, "-B", "-c", bootstrap, cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    limit=MAX_PAYLOAD_BYTES + 4096)
        self.addAsyncCleanup(self.finish, process)
        return process

    async def finish(self, process):
        if process.returncode is None:
            process.stdin.close()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def exchange(self, process, request_id, method, params):
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        process.stdin.write((json.dumps(message) + "\n").encode())
        await process.stdin.drain()
        raw = await asyncio.wait_for(process.stdout.readline(), 10)
        self.last_response_bytes = len(raw)
        reply = json.loads(raw)
        self.assertEqual(reply.get("jsonrpc"), "2.0")
        self.assertEqual(reply.get("id"), request_id)
        return reply

    async def initialize(self, process):
        reply = await self.exchange(process, 1, "initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {},
            "clientInfo": {"name": "godot-stdio-test", "version": "0.1.0"}})
        self.assertIn("result", reply)
        process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        await process.stdin.drain()

    async def assert_clean_shutdown(self, process):
        process.stdin.close()
        await asyncio.wait_for(process.wait(), 5)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(await process.stdout.read(), b"")
        self.assertNotIn(b"Traceback", await process.stderr.read())

    async def test_real_stdio_only_jsonrpc_and_disconnected_error(self):
        process = await self.child()
        await self.initialize(process)
        listing = await self.exchange(process, 2, "tools/list", {})
        self.assertEqual({tool["name"] for tool in listing["result"]["tools"]}, OPERATIONS)
        response = await self.exchange(process, 3, "tools/call", {"name": "godot_ping", "arguments": {}})
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "DISCONNECTED")
        await self.assert_clean_shutdown(process)

    async def test_raw_stdio_extra_null_missing_and_nonobjects_rejected_before_sdk(self):
        process = await self.child()
        await self.initialize(process)
        params_cases = [{"name": operation, "arguments": arguments}
                        for operation in ("godot_ping", *WRITE_OPERATIONS)
                        for arguments in ({"unexpected": True}, None, [], False, "")]
        params_cases.extend({"name": operation} for operation in ("godot_ping", *WRITE_OPERATIONS))
        for request_id, params in enumerate(params_cases, 2):
            with self.subTest(request_id=request_id):
                response = await self.exchange(process, request_id, "tools/call", params)
                self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "INVALID_REQUEST")
        response = await self.exchange(process, 20, "tools/call", {"name": "godot_save_scene", "arguments": {}})
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "UNSUPPORTED_OPERATION")
        await self.assert_clean_shutdown(process)

    async def test_unsafe_local_auth_keeps_real_stdio_tool_discovery(self):
        process = await self.child(unsafe=True)
        await self.initialize(process)
        listing = await self.exchange(process, 2, "tools/list", {})
        self.assertEqual(len(listing["result"]["tools"]), 7)
        response = await self.exchange(process, 3, "tools/call", {"name": "godot_ping", "arguments": {}})
        self.assertEqual(response["result"]["structuredContent"]["error"]["code"], "LOCAL_AUTH_UNSAFE")
        await self.assert_clean_shutdown(process)

    async def assert_stdio_size_boundary(self, character):
        repeat = last_fitting_repeat(character)
        for extra, expected_ok in ((0, True), (1, False)):
            fixture = large_inspection(repeat + extra, character)
            validate_result("godot_inspect_scene", fixture)
            payload = envelope(fixture, elapsed_ms=0.0)
            self.assertLess(len(encode(payload).encode("utf-8")), MAX_PAYLOAD_BYTES)
            unbounded_size = encoded_size(expected_unbounded_body(payload))
            self.assertEqual(unbounded_size <= MAX_TOOL_RESULT_BYTES, expected_ok)
            if expected_ok:
                self.assertGreater(unbounded_size, MAX_TOOL_RESULT_BYTES - 1024)
            process = await self.child(fixture=(repeat + extra, character))
            await self.initialize(process)
            listing = await self.exchange(process, 2, "tools/list", {})
            schema = next(tool["outputSchema"] for tool in listing["result"]["tools"]
                          if tool["name"] == "godot_inspect_scene")
            response = await self.exchange(process, 3, "tools/call", {"name": "godot_inspect_scene", "arguments": {}})
            self.assertLessEqual(self.last_response_bytes, MAX_PAYLOAD_BYTES)
            data = response["result"]["structuredContent"]
            Draft202012Validator(schema).validate(data)
            self.assertEqual(data["ok"], expected_ok)
            self.assertEqual(json.loads(response["result"]["content"][0]["text"]), data)
            if expected_ok:
                self.assertEqual(data["result"], fixture)
                self.assertLessEqual(self.last_response_bytes,
                                     MAX_PAYLOAD_BYTES - MCP_ENVELOPE_RESERVE_BYTES + 128)
            else:
                self.assertEqual(data["error"]["code"], "RESPONSE_TOO_LARGE")
                self.assertIsNone(data["result"])
                self.assertLess(self.last_response_bytes, 2048)
            await self.assert_clean_shutdown(process)

    async def test_real_stdio_plain_metadata_at_encoded_response_boundary(self):
        await self.assert_stdio_size_boundary("x")

    async def test_real_stdio_escaped_metadata_at_encoded_response_boundary(self):
        await self.assert_stdio_size_boundary('"')


if __name__ == "__main__":
    unittest.main(verbosity=2)
