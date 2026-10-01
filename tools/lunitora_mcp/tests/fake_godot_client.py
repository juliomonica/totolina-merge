"""Test-only metadata peer using disposable credentials and ephemeral listeners."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import hmac
import secrets
import socket

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from modules.godot.config import Credential, HOST
from modules.godot.protocol import (BRIDGE_VERSION, MAX_PAYLOAD_BYTES, PROTOCOL_VERSION,
                                   decode, encode, is_hex, proof)

NO_SCENE = {"exists": False, "path": None, "root_name": None, "has_saved_path": False,
            "save_state": "no_scene", "dirty_changes": None, "dirty_reason": "no_scene"}
SAVED_SCENE = {"exists": True, "path": "res://tests/fixture.tscn", "root_name": "Root",
               "has_saved_path": True, "save_state": "saved_clean", "dirty_changes": False,
               "dirty_reason": None}
UNNAMED_SCENE = {"exists": True, "path": None, "root_name": "Root", "has_saved_path": False,
                 "save_state": "new_unsaved", "dirty_changes": None, "dirty_reason": "unnamed_scene"}
ROOT_NODE = {"path": ".", "parent_path": None, "type": "Node2D", "child_count": 0,
             "kind": None, "animations": None}


def disposable_credential() -> Credential:
    return Credential("c:/test/godot-project", secrets.token_hex(32), secrets.token_bytes(32))


def ping(credential: Credential) -> dict:
    return {"godot_version": "4.7.2.stable.official.ed1daf0bf", "project_path": credential.project_path,
            "project_name": "Totolina – 猫 🐾", "plugin_version": BRIDGE_VERSION,
            "editor_session_id": "disposable-editor-session", "read_only": True}


def result_for(operation: str, credential: Credential, scene: dict, nodes: list, selection: list) -> dict:
    if operation == "godot_ping":
        return ping(credential)
    if operation == "godot_get_editor_state":
        return {**ping(credential), "scene": deepcopy(scene), "selected_nodes": {
            "total_count": len(selection), "nodes": deepcopy(selection[:128]), "truncated": len(selection) > 128}}
    return {"editor_session_id": "disposable-editor-session", "scene": deepcopy(scene), "nodes": deepcopy(nodes)}


class FakeGodotClient:
    def __init__(self, credential: Credential, port: int, *, scene: dict | None = None,
                 nodes: list | None = None, selection: list | None = None,
                 delay: float = 0, ignore: bool = False, mutate=None):
        self.credential = credential
        self.port = port
        self.scene = deepcopy(scene if scene is not None else NO_SCENE)
        self.nodes = deepcopy(nodes if nodes is not None else [])
        self.selection = deepcopy(selection if selection is not None else [])
        self.delay, self.ignore, self.mutate = delay, ignore, mutate
        self.requests = []
        self.socket = self.reader = None
        self.client_nonce = None
        self.challenge = None
        self.request_received = asyncio.Event()

    async def __aenter__(self):
        self.socket = await connect(f"ws://{HOST}:{self.port}", family=socket.AF_INET, proxy=None,
                                    max_size=MAX_PAYLOAD_BYTES, compression=None, close_timeout=1)
        self.client_nonce = secrets.token_hex(32)
        await self.socket.send(encode({"type": "hello", "protocol_version": PROTOCOL_VERSION,
                                       "project_id": self.credential.project_id, "client_nonce": self.client_nonce}))
        challenge = decode(await asyncio.wait_for(self.socket.recv(), 2))
        self.challenge = challenge
        if (set(challenge) != {"type", "protocol_version", "server_nonce", "proof"}
                or challenge["type"] != "challenge" or not is_hex(challenge["server_nonce"], 64)
                or not is_hex(challenge["proof"], 64)
                or not hmac.compare_digest(challenge["proof"], proof(
                    self.credential.secret, self.credential.project_id, self.client_nonce,
                    challenge["server_nonce"], "server"))):
            await self.socket.close()
            raise RuntimeError("Fake peer refused unauthenticated server.")
        await self.socket.send(encode({"type": "authenticate", "protocol_version": PROTOCOL_VERSION,
                                       "proof": proof(self.credential.secret, self.credential.project_id,
                                                      self.client_nonce, challenge["server_nonce"], "client")}))
        ready = decode(await asyncio.wait_for(self.socket.recv(), 2))
        if ready != {"type": "ready", "protocol_version": PROTOCOL_VERSION}:
            await self.socket.close()
            raise RuntimeError("Fake peer authentication was rejected.")
        self.reader = asyncio.create_task(self._read())
        return self

    async def _read(self):
        try:
            async for raw in self.socket:
                request = decode(raw)
                self.requests.append(request)
                self.request_received.set()
                if self.ignore:
                    continue
                if self.delay:
                    await asyncio.sleep(self.delay)
                response = {"type": "response", "protocol_version": PROTOCOL_VERSION,
                            "id": request["id"], "operation": request["operation"], "ok": True,
                            "result": result_for(request["operation"], self.credential,
                                                 self.scene, self.nodes, self.selection), "error": None}
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
