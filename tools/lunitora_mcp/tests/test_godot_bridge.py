"""Disposable mutual-auth peers exercise transport, bounded work and reconnects."""
from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import secrets
import socket
import unittest

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidMessage, InvalidStatus

from modules.godot.bridge import GodotBridge, MAX_PENDING
from modules.godot.config import Config, Credential, HOST
from modules.godot.protocol import (BridgeError, MAX_PAYLOAD_BYTES, decode, encode, proof)
from tests.fake_godot_client import (FakeGodotClient, NO_SCENE, ROOT_NODE, SAVED_SCENE,
                                     disposable_credential, ping, result_for)


class GodotBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.credential = disposable_credential()
        self.bridge = GodotBridge(Config(request_timeout_seconds=0.2, authentication_timeout_seconds=0.2),
                                  self.credential, port=0)
        await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        self.addAsyncCleanup(self.bridge.stop)

    async def peer(self, **kwargs):
        peer = await FakeGodotClient(self.credential, self.bridge.port, **kwargs).__aenter__()
        self.addAsyncCleanup(peer.__aexit__, None, None, None)
        return peer

    async def raw(self, **kwargs):
        peer = await connect(f"ws://{HOST}:{self.bridge.port}", proxy=None, compression=None,
                             close_timeout=1, **kwargs)
        self.addAsyncCleanup(peer.close)
        return peer

    async def hello(self, peer, *, nonce=None, project_id=None):
        nonce = nonce or secrets.token_hex(32)
        await peer.send(encode({"type": "hello", "protocol_version": 1,
                                "project_id": project_id or self.credential.project_id, "client_nonce": nonce}))
        return nonce, decode(await asyncio.wait_for(peer.recv(), 1))

    async def rejection(self, peer, expected):
        rejection = decode(await asyncio.wait_for(peer.recv(), 1))
        self.assertEqual(rejection["type"], "rejected")
        self.assertEqual(rejection["error"]["code"], expected)
        await asyncio.wait_for(peer.wait_closed(), 1)

    def response(self, request, result=None):
        return {"type": "response", "protocol_version": 1, "id": request["id"],
                "operation": request["operation"], "ok": True,
                "result": result if result is not None else ping(self.credential), "error": None}

    async def wait_requests(self, peer, count):
        async with asyncio.timeout(1):
            while len(peer.requests) < count:
                peer.request_received.clear()
                await peer.request_received.wait()

    async def test_disconnected_is_immediate_bounded_error(self):
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "DISCONNECTED")

    async def test_mutual_authentication_and_all_three_fresh_reads(self):
        peer = await self.peer(scene=SAVED_SCENE, nodes=[ROOT_NODE])
        for operation in ("godot_ping", "godot_get_editor_state", "godot_inspect_scene"):
            data, timing = await self.bridge.request(operation, {})
            self.assertEqual(data, result_for(operation, self.credential, SAVED_SCENE, [ROOT_NODE], []))
            self.assertGreaterEqual(timing, 0)
        self.assertEqual(len({request["id"] for request in peer.requests}), 3)
        self.assertTrue(all(set(request) == {"type", "protocol_version", "id", "operation", "params"}
                            and request["params"] == {} for request in peer.requests))

    async def test_no_scene_inspection(self):
        await self.peer()
        data, _ = await self.bridge.request("godot_inspect_scene", {})
        self.assertEqual(data["scene"], NO_SCENE)
        self.assertEqual(data["nodes"], [])

    async def test_wrong_client_proof_never_authenticates(self):
        peer = await self.raw()
        nonce, challenge = await self.hello(peer)
        await peer.send(encode({"type": "authenticate", "protocol_version": 1, "proof": "0" * 64}))
        await self.rejection(peer, "AUTH_FAILED")
        self.assertIsNone(self.bridge._connection)

    async def test_client_refuses_wrong_server_proof(self):
        wrong = Credential(self.credential.project_path, self.credential.project_id, secrets.token_bytes(32))
        with self.assertRaises(RuntimeError):
            await FakeGodotClient(wrong, self.bridge.port).__aenter__()
        self.assertIsNone(self.bridge._connection)

    async def test_role_reflection_proof_rejected(self):
        peer = await self.raw()
        _, challenge = await self.hello(peer)
        await peer.send(encode({"type": "authenticate", "protocol_version": 1, "proof": challenge["proof"]}))
        await self.rejection(peer, "AUTH_FAILED")

    async def test_project_mismatch_rejected_before_authentication(self):
        peer = await self.raw()
        _, rejection = await self.hello(peer, project_id=secrets.token_hex(32))
        self.assertEqual(rejection["error"]["code"], "PROJECT_MISMATCH")
        await peer.wait_closed()

    async def test_reused_client_nonce_rejected(self):
        peer = await self.raw()
        nonce, _ = await self.hello(peer)
        await peer.close()
        second = await self.raw()
        _, rejection = await self.hello(second, nonce=nonce)
        self.assertEqual(rejection["error"]["code"], "AUTH_FAILED")

    async def test_old_client_proof_rejected_by_fresh_challenge(self):
        first = await self.raw()
        nonce, challenge = await self.hello(first)
        old_proof = proof(self.credential.secret, self.credential.project_id, nonce, challenge["server_nonce"], "client")
        await first.close()
        second = await self.raw()
        _, fresh = await self.hello(second)
        self.assertNotEqual(challenge["server_nonce"], fresh["server_nonce"])
        await second.send(encode({"type": "authenticate", "protocol_version": 1, "proof": old_proof}))
        await self.rejection(second, "AUTH_FAILED")

    async def test_authentication_timeout(self):
        peer = await self.raw()
        await self.rejection(peer, "AUTH_FAILED")

    async def test_browser_origin_rejected(self):
        with self.assertRaises(InvalidStatus):
            await self.raw(origin="http://localhost")

    async def test_second_authenticated_editor_cannot_replace(self):
        original = await self.peer()
        with self.assertRaises(RuntimeError):
            await FakeGodotClient(self.credential, self.bridge.port).__aenter__()
        await self.bridge.request("godot_ping", {})
        self.assertEqual(len(original.requests), 1)

    async def test_connection_limit_is_bounded(self):
        peers = [await self.raw() for _ in range(4)]
        with self.assertRaises((InvalidMessage, OSError)):
            await self.raw()
        for peer in peers:
            await peer.close()

    async def test_partial_tcp_handshakes_cannot_bypass_connection_limit(self):
        writers = []
        try:
            for _ in range(4):
                _, writer = await asyncio.open_connection(HOST, self.bridge.port)
                writers.append(writer)
                writer.write(b"GET / HTTP/1.1\r\n")
                await writer.drain()
            self.assertEqual(len(self.bridge._transports), 4)
            self.assertEqual(len(self.bridge._connections), 0)
            reader, fifth = await asyncio.open_connection(HOST, self.bridge.port)
            writers.append(fifth)
            try:
                self.assertEqual(await asyncio.wait_for(reader.read(1), 1), b"")
            except ConnectionResetError:
                pass
            self.assertEqual(len(self.bridge._transports), 4)
        finally:
            for writer in writers:
                writer.close()
            await asyncio.gather(*(writer.wait_closed() for writer in writers), return_exceptions=True)

    async def test_malformed_authentication_binary_duplicate_and_extra(self):
        for raw in (b"binary", '{"protocol_version":1,"protocol_version":1}',
                    encode({"type": "hello", "protocol_version": 1, "project_id": self.credential.project_id,
                            "client_nonce": secrets.token_hex(32), "extra": True})):
            peer = await self.raw()
            await peer.send(raw)
            await self.rejection(peer, "INVALID_MESSAGE")

    async def test_timeout_and_stale_reply_never_satisfy_next_request(self):
        peer = await self.peer(ignore=True)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "TIMEOUT")
        task = asyncio.create_task(self.bridge.request("godot_ping", {}))
        await self.wait_requests(peer, 2)
        await peer.socket.send(encode(self.response(peer.requests[0])))
        await asyncio.sleep(0.02)
        self.assertFalse(task.done())
        await peer.socket.send(encode(self.response(peer.requests[1])))
        data, _ = await task
        self.assertEqual(data, ping(self.credential))
        self.assertEqual(self.bridge._pending, {})

    async def test_disconnect_fails_pending_and_reconnect_accepts_fresh_editor(self):
        peer = await self.peer(ignore=True)
        task = asyncio.create_task(self.bridge.request("godot_ping", {}))
        await self.wait_requests(peer, 1)
        await peer.socket.close()
        with self.assertRaises(BridgeError) as error:
            await task
        self.assertEqual(error.exception.code, "DISCONNECTED")
        await self.peer()
        await self.bridge.request("godot_ping", {})
        self.assertEqual(self.bridge._pending, {})

    async def test_pending_limit_and_cancel_cleanup(self):
        peer = await self.peer(ignore=True)
        tasks = [asyncio.create_task(self.bridge.request("godot_ping", {})) for _ in range(MAX_PENDING)]
        await self.wait_requests(peer, MAX_PENDING)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "BUSY")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(self.bridge._pending, {})

    async def test_malformed_response_disconnects_with_sanitized_error(self):
        def mutate(response):
            response["result"]["arbitrary_script_property"] = "forbidden"
        await self.peer(mutate=mutate)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "INVALID_MESSAGE")

    async def test_response_project_mismatch_rejected(self):
        def mutate(response):
            response["result"]["project_path"] = "c:/different/project"
        await self.peer(mutate=mutate)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "PROJECT_MISMATCH")

    async def test_editor_session_cannot_change_on_existing_socket(self):
        peer = await self.peer()
        await self.bridge.request("godot_ping", {})
        peer.mutate = lambda response: response["result"].update(editor_session_id="unexpected-session")
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "INVALID_MESSAGE")

    async def test_wrong_operation_cannot_satisfy_request(self):
        def mutate(response):
            response["operation"] = "godot_inspect_scene"
            response["result"] = result_for("godot_inspect_scene", self.credential, NO_SCENE, [], [])
        await self.peer(mutate=mutate)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "INVALID_MESSAGE")

    async def test_oversized_frame_disconnects_without_partial_metadata(self):
        peer = await self.peer(ignore=True)
        task = asyncio.create_task(self.bridge.request("godot_ping", {}))
        await self.wait_requests(peer, 1)
        await peer.socket.send("a" * (MAX_PAYLOAD_BYTES + 1))
        with self.assertRaises(BridgeError) as error:
            await task
        self.assertEqual(error.exception.code, "DISCONNECTED")

    async def test_peer_error_text_is_never_echoed(self):
        marker = "sensitive-peer-details-never-return"
        def mutate(response):
            response.update(ok=False, result=None, error={"code": "INSPECTION_FAILED", "message": marker})
        await self.peer(mutate=mutate)
        with self.assertRaises(BridgeError) as error:
            await self.bridge.request("godot_ping", {})
        self.assertEqual(error.exception.code, "INSPECTION_FAILED")
        self.assertNotIn(marker, str(error.exception))

    async def test_no_stdout_stderr_auth_material(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            peer = await self.peer()
            await self.bridge.request("godot_ping", {})
            await peer.socket.close()
        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(output, "")
        self.assertNotIn(self.credential.secret.hex(), output)

    async def test_invalid_input_and_unregistered_mutations_rejected(self):
        for params in ({"play": True}, [], "", False):
            with self.assertRaises(BridgeError) as error:
                await self.bridge.request("godot_ping", params)
            self.assertEqual(error.exception.code, "INVALID_REQUEST")
        for operation in ("godot_save_scene", "godot_set_selection", "godot_play_animation", "godot_create_node"):
            with self.assertRaises(BridgeError) as error:
                await self.bridge.request(operation, {})
            self.assertEqual(error.exception.code, "UNSUPPORTED_OPERATION")

    async def test_occupied_port_and_absent_credential_remain_available_errors(self):
        absent = GodotBridge(Config(), None, port=0)
        await absent.start()
        self.assertEqual(absent.startup_error.code, "LOCAL_AUTH_UNSAFE")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind((HOST, 0))
            occupied.listen(1)
            conflict = GodotBridge(Config(), self.credential, port=occupied.getsockname()[1])
            await conflict.start()
            self.assertEqual(conflict.startup_error.code, "PORT_IN_USE")
            await conflict.stop()
            self.assertEqual(occupied.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN), 1)

    async def test_shutdown_closes_connections_and_pending_work(self):
        peer = await self.peer(ignore=True)
        task = asyncio.create_task(self.bridge.request("godot_ping", {}))
        await self.wait_requests(peer, 1)
        await self.bridge.stop()
        with self.assertRaises(BridgeError) as error:
            await task
        self.assertEqual(error.exception.code, "DISCONNECTED")
        await peer.socket.wait_closed()


if __name__ == "__main__":
    unittest.main(verbosity=2)
