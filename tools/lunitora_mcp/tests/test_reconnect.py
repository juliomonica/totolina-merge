"""Connection grace over real authenticated sockets on a test-only ephemeral port."""
import asyncio
import base64
import secrets
from time import perf_counter
import unittest
from unittest.mock import patch

from websockets.asyncio.client import connect

from core.config import Config
from modules.photoshop.bridge import PhotoshopBridge
from modules.photoshop.protocol import BridgeError, decode, encode
from tests.test_phase2 import png, result


class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token = secrets.token_urlsafe(48)
        self.bridge = PhotoshopBridge(Config(request_timeout_seconds=0.15), self.token)
        # Only this test instance: production endpoint/config remain fixed.
        with patch("modules.photoshop.bridge.PORT", 0):
            await self.bridge.start()
        self.assertIsNone(self.bridge.startup_error)
        port = self.bridge._server.sockets[0].getsockname()[1]
        self.endpoint = f"ws://127.0.0.1:{port}"

    async def asyncTearDown(self):
        await self.bridge.stop()

    async def pair(self, peer, token=None):
        await peer.send(encode({"type": "auth", "protocol_version": 1, "token": token or self.token}))
        return decode(await peer.recv())

    async def test_process_call_waits_for_authentication_without_ping(self):
        parameters = {"image_base64": base64.b64encode(png()).decode(),
                      "width_px": 4, "height_px": 4, "remove_background": False}
        pending = asyncio.create_task(self.bridge.request("photoshop_process_image", parameters))
        await asyncio.sleep(0.025)
        self.assertFalse(pending.done())
        async with connect(self.endpoint, proxy=None) as peer:
            self.assertTrue((await self.pair(peer))["ok"])
            request = decode(await peer.recv())
            self.assertEqual(request["operation"], "photoshop_process_image")
            await peer.send(encode({"type": "response", "protocol_version": 1,
                                   "id": request["id"], "operation": request["operation"],
                                   "ok": True, "result": result(), "error": None}))
            response, elapsed = await pending
            self.assertEqual(response["width_px"], 4)
            self.assertGreaterEqual(elapsed, 20)

    async def test_ping_remains_immediate(self):
        started = perf_counter()
        with self.assertRaises(BridgeError) as caught:
            await self.bridge.request("photoshop_ping")
        self.assertEqual(caught.exception.code, "DISCONNECTED")
        self.assertLess(perf_counter() - started, 0.1)

    async def test_no_peer_has_bounded_disconnected_result(self):
        with patch("modules.photoshop.bridge.CONNECTION_GRACE_SECONDS", 0.05):
            with self.assertRaises(BridgeError) as caught:
                await self.bridge.request("photoshop_get_active_document")
        self.assertEqual(caught.exception.code, "DISCONNECTED")
        self.assertFalse(self.bridge._pending)

    async def test_unauthenticated_peer_cannot_release_waiter(self):
        pending = asyncio.create_task(self.bridge.request("photoshop_get_active_document"))
        async with connect(self.endpoint, proxy=None) as peer:
            self.assertFalse((await self.pair(peer, secrets.token_urlsafe(48)))["ok"])
        with self.assertRaises(BridgeError) as caught:
            await pending
        self.assertEqual(caught.exception.code, "DISCONNECTED")

    async def test_wait_and_response_share_original_request_deadline(self):
        started = perf_counter()
        pending = asyncio.create_task(self.bridge.request("photoshop_get_active_document"))
        await asyncio.sleep(0.075)
        async with connect(self.endpoint, proxy=None) as peer:
            await self.pair(peer)
            await peer.recv()  # Deliberately do not reply.
            with self.assertRaises(BridgeError) as caught:
                await pending
        self.assertEqual(caught.exception.code, "TIMEOUT")
        self.assertLess(perf_counter() - started, 0.22)
        self.assertFalse(self.bridge._pending)

    async def test_shutdown_wakes_waiter(self):
        pending = asyncio.create_task(self.bridge.request("photoshop_get_active_document"))
        await asyncio.sleep(0)
        await self.bridge.stop()
        with self.assertRaises(BridgeError) as caught:
            await pending
        self.assertEqual(caught.exception.code, "DISCONNECTED")

    async def test_cancellation_leaves_no_request_to_replay(self):
        pending = asyncio.create_task(self.bridge.request("photoshop_get_active_document"))
        await asyncio.sleep(0)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertFalse(self.bridge._pending)
        async with connect(self.endpoint, proxy=None) as peer:
            await self.pair(peer)
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(peer.recv(), 0.03)

    async def test_startup_errors_do_not_wait(self):
        self.bridge.startup_error = BridgeError("PORT_IN_USE")
        started = perf_counter()
        with self.assertRaises(BridgeError) as caught:
            await self.bridge.request("photoshop_get_active_document")
        self.assertEqual(caught.exception.code, "PORT_IN_USE")
        self.assertLess(perf_counter() - started, 0.1)
