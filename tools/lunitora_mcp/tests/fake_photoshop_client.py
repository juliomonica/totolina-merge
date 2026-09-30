"""Test-only peer. Uses a disposable token supplied by tests, never the real pairing file."""
from __future__ import annotations

import asyncio
import socket
from copy import deepcopy

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from core.config import ENDPOINT
from modules.photoshop.protocol import BRIDGE_VERSION, MAX_PAYLOAD_BYTES, PROTOCOL_VERSION, decode, encode

PING = {"photoshop_version": "27.10.0", "host_version": "27.10.0",
        "uxp_version": "test-runtime", "plugin_version": BRIDGE_VERSION}
NO_DOCUMENT = {"has_document": False, "document": None}
ACTIVE_DOCUMENT = {
    "has_document": True,
    "document": {
        "id": 42, "name": "Totolina – 猫 🐾.psd", "width_px": 2048, "height_px": 1024, "saved": False,
        "top_level_layer_count": 2, "recursive_layer_count": 5,
        "layers": [
            {"id": 1, "name": "表情", "kind": "group", "children": [
                {"id": 2, "name": "Eyes", "kind": "pixel", "children": []},
                {"id": 3, "name": "Eyes", "kind": "group", "children": [
                    {"id": 4, "name": "瞳 🐱", "kind": "pixel", "children": []}
                ]}
            ]},
            {"id": 5, "name": "Body", "kind": "pixel", "children": []}
        ],
        "artboard_count": 1, "artboards": [{"id": 1, "name": "表情"}],
    },
}


class FakePhotoshopClient:
    def __init__(self, token: str, *, document: dict | None = None,
                 delay: float = 0, ignore: bool = False, mutate=None):
        self.token = token
        self.document = deepcopy(document if document is not None else NO_DOCUMENT)
        self.delay = delay
        self.ignore = ignore
        self.mutate = mutate
        self.requests = []
        self.socket = None
        self.reader = None

    async def __aenter__(self):
        # Match the IPv4-only listener without delaying short tests on an IPv6 refusal.
        self.socket = await connect(ENDPOINT, family=socket.AF_INET, proxy=None, max_size=MAX_PAYLOAD_BYTES,
                                    compression=None, close_timeout=1)
        await self.socket.send(encode({"type": "auth", "protocol_version": PROTOCOL_VERSION,
                                       "token": self.token}))
        response = decode(await asyncio.wait_for(self.socket.recv(), 2))
        if not response.get("ok"):
            await self.socket.close()
            raise RuntimeError("Fake peer authentication failed.")
        self.reader = asyncio.create_task(self._read())
        return self

    async def _read(self):
        try:
            async for raw in self.socket:
                request = decode(raw)
                self.requests.append(request)
                if self.ignore:
                    continue
                delay = self.delay
                if delay:
                    await asyncio.sleep(delay)
                result = PING if request["operation"] == "photoshop_ping" else self.document
                response = {
                    "type": "response", "protocol_version": PROTOCOL_VERSION,
                    "id": request["id"], "operation": request["operation"],
                    "ok": True, "result": deepcopy(result), "error": None,
                }
                if self.mutate:
                    self.mutate(response)
                await self.socket.send(encode(response))
        except ConnectionClosed:
            pass

    async def __aexit__(self, *_):
        if self.socket:
            await self.socket.close()
        if self.reader:
            self.reader.cancel()
            try:
                await self.reader
            except asyncio.CancelledError:
                pass
