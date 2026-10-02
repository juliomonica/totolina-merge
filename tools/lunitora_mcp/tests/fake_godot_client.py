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
from modules.godot.protocol import (ANIMATION_PLAYER_PATH, ANIMATION_UNDO_ACTION_NAME,
                                   ANIMATION_WRITE_OPERATION, BRIDGE_VERSION, LAB_ROOT_NAME, LAB_SCENE_PATH, MAX_PAYLOAD_BYTES,
                                   PROTOCOL_VERSION, RIG_ROOT_NAME, UNDO_ACTION_NAME, WRITE_OPERATION,
                                   TOLINA_LAB_ROOT_NAME, TOLINA_LAB_SCENE_PATH, TOLINA_RIG_ROOT_NAME,
                                   TOLINA_RIG_UNDO_ACTION_NAME, TOLINA_ANIMATION_PLAYER_PATH,
                                   TOLINA_BLINK_UNDO_ACTION_NAME, TOLINA_RIG_WRITE_OPERATION,
                                   TOLINA_BLINK_WRITE_OPERATION,
                                   DEFORMATION_LAB_SCENE_PATH, DEFORMATION_LAB_ROOT_NAME,
                                   DEFORMATION_RIG_ROOT_NAME, DEFORMATION_RIG_UNDO_ACTION_NAME,
                                   DEFORMATION_ANIMATION_PLAYER_PATH, DEFORMATION_DEMO_UNDO_ACTION_NAME,
                                   DEFORMATION_RIG_WRITE_OPERATION, DEFORMATION_DEMO_WRITE_OPERATION,
                                   WRITE_OPERATIONS, decode, encode, error_info, is_hex, proof)

NO_SCENE = {"exists": False, "path": None, "root_name": None, "has_saved_path": False,
            "save_state": "no_scene", "dirty_changes": None, "dirty_reason": "no_scene"}
SAVED_SCENE = {"exists": True, "path": "res://tests/fixture.tscn", "root_name": "Root",
               "has_saved_path": True, "save_state": "saved_clean", "dirty_changes": False,
               "dirty_reason": None}
UNNAMED_SCENE = {"exists": True, "path": None, "root_name": "Root", "has_saved_path": False,
                 "save_state": "new_unsaved", "dirty_changes": None, "dirty_reason": "unnamed_scene"}
ROOT_NODE = {"path": ".", "parent_path": None, "type": "Node2D", "child_count": 0,
             "kind": None, "animations": None}
LAB_SCENE = dict(SAVED_SCENE, path=LAB_SCENE_PATH, root_name=LAB_ROOT_NAME)
TOLINA_LAB_SCENE = dict(SAVED_SCENE, path=TOLINA_LAB_SCENE_PATH, root_name=TOLINA_LAB_ROOT_NAME)
DEFORMATION_LAB_SCENE = dict(SAVED_SCENE, path=DEFORMATION_LAB_SCENE_PATH, root_name=DEFORMATION_LAB_ROOT_NAME)


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
    if operation == WRITE_OPERATION:
        return rig_lab_result(credential)
    if operation == ANIMATION_WRITE_OPERATION:
        return rig_lab_animation_result(credential)
    if operation == TOLINA_RIG_WRITE_OPERATION:
        return tolina_rig_lab_result(credential)
    if operation == TOLINA_BLINK_WRITE_OPERATION:
        return tolina_lab_blink_result(credential)
    if operation == DEFORMATION_RIG_WRITE_OPERATION:
        return deformation_rig_lab_result(credential)
    if operation == DEFORMATION_DEMO_WRITE_OPERATION:
        return deformation_demo_result(credential)
    return {"editor_session_id": "disposable-editor-session", "scene": deepcopy(scene), "nodes": deepcopy(nodes)}


def rig_lab_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {"editor_session_id": session_id, "project_path": credential.project_path,
            "scene_path": LAB_SCENE_PATH, "root_name": LAB_ROOT_NAME, "created_root": RIG_ROOT_NAME,
            "created_node_count": 7, "undo_action_name": UNDO_ACTION_NAME, "undo_actions_added": 1,
            "save_state": "saved_dirty", "auto_saved": False, "read_only": False}


def rig_lab_animation_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {"editor_session_id": session_id, "project_path": credential.project_path,
            "scene_path": LAB_SCENE_PATH, "root_name": LAB_ROOT_NAME,
            "animation_player_path": ANIMATION_PLAYER_PATH, "library_name": "",
            "animation_name": "bend_tip", "animation_key": "bend_tip", "length_seconds": 1.0,
            "track_count": 1, "key_count": 3, "undo_action_name": ANIMATION_UNDO_ACTION_NAME,
            "undo_actions_added": 1, "save_state": "saved_dirty", "auto_saved": False, "read_only": False}


def tolina_rig_lab_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {**rig_lab_result(credential, session_id), "scene_path": TOLINA_LAB_SCENE_PATH,
            "root_name": TOLINA_LAB_ROOT_NAME, "created_root": TOLINA_RIG_ROOT_NAME,
            "created_node_count": 21, "undo_action_name": TOLINA_RIG_UNDO_ACTION_NAME}


def tolina_lab_blink_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {**rig_lab_animation_result(credential, session_id), "scene_path": TOLINA_LAB_SCENE_PATH,
            "root_name": TOLINA_LAB_ROOT_NAME, "animation_player_path": TOLINA_ANIMATION_PLAYER_PATH,
            "animation_name": "blink", "animation_key": "blink", "length_seconds": 0.24,
            "track_count": 3, "key_count": 18, "undo_action_name": TOLINA_BLINK_UNDO_ACTION_NAME}


def deformation_rig_lab_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {**rig_lab_result(credential, session_id), "scene_path": DEFORMATION_LAB_SCENE_PATH,
            "root_name": DEFORMATION_LAB_ROOT_NAME, "created_root": DEFORMATION_RIG_ROOT_NAME,
            "created_node_count": 19, "undo_action_name": DEFORMATION_RIG_UNDO_ACTION_NAME}


def deformation_demo_result(credential: Credential, session_id="disposable-editor-session") -> dict:
    return {**rig_lab_animation_result(credential, session_id), "scene_path": DEFORMATION_LAB_SCENE_PATH,
            "root_name": DEFORMATION_LAB_ROOT_NAME, "animation_player_path": DEFORMATION_ANIMATION_PLAYER_PATH,
            "animation_name": "deformation_demo", "animation_key": "deformation_demo", "length_seconds": 2.0,
            "track_count": 7, "key_count": 35, "undo_action_name": DEFORMATION_DEMO_UNDO_ACTION_NAME}


class FakeGodotClient:
    def __init__(self, credential: Credential, port: int, *, scene: dict | None = None,
                 nodes: list | None = None, selection: list | None = None,
                 delay: float = 0, ignore: bool = False, mutate=None,
                 write_delay: float = 0, ignore_write_reply: bool = False, session_id="disposable-editor-session",
                 has_rig: bool = False, animation_error: str | None = None,
                 has_tolina_rig: bool = False, tolina_rig_error: str | None = None,
                 blink_error: str | None = None, has_deformation_rig: bool = False,
                 deformation_rig_error: str | None = None, deformation_demo_error: str | None = None):
        self.credential = credential
        self.port = port
        self.scene = deepcopy(scene if scene is not None else NO_SCENE)
        self.nodes = deepcopy(nodes if nodes is not None else [])
        self.selection = deepcopy(selection if selection is not None else [])
        self.delay, self.ignore, self.mutate = delay, ignore, mutate
        self.write_delay, self.ignore_write_reply = write_delay, ignore_write_reply
        self.session_id = session_id
        self.write_ids = set()
        self.created = has_rig
        self.animation_created = False
        self.animation_error = animation_error
        self.tolina_created = has_tolina_rig
        self.blink_created = False
        self.tolina_rig_error = tolina_rig_error
        self.blink_error = blink_error
        self.deformation_created = has_deformation_rig
        self.deformation_demo_created = False
        self.deformation_rig_error = deformation_rig_error
        self.deformation_demo_error = deformation_demo_error
        self.write_faulted = False
        self.applied_writes = 0
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
        socket = self.socket
        try:
            async for raw in socket:
                request = decode(raw)
                self.requests.append(request)
                self.request_received.set()
                if self.ignore:
                    continue
                delay = self.write_delay if request["operation"] in WRITE_OPERATIONS else self.delay
                if delay:
                    await asyncio.sleep(delay)
                # A replacement peer cannot consume buffered packets from the
                # retired socket; mirror the editor's synchronous retirement.
                if socket is not self.socket or socket.close_code is not None:
                    break
                response = {"type": "response", "protocol_version": PROTOCOL_VERSION,
                            "id": request["id"], "operation": request["operation"], "ok": True,
                            "result": result_for(request["operation"], self.credential,
                                                 self.scene, self.nodes, self.selection), "error": None}
                response["result"]["editor_session_id"] = self.session_id
                if request["operation"] in WRITE_OPERATIONS:
                    response["editor_session_id"] = self.session_id
                    code = None
                    if request.get("editor_session_id") != self.session_id:
                        code = "INVALID_MESSAGE"
                    elif self.write_faulted:
                        code = "WRITE_OUTCOME_UNKNOWN"
                    elif request["id"] in self.write_ids:
                        code = "WRITE_REPLAY_REJECTED"
                    elif len(self.write_ids) >= 128:
                        code = "SESSION_WRITE_LIMIT"
                    else:
                        self.write_ids.add(request["id"])
                        operation = request["operation"]
                        tolina = operation in {TOLINA_RIG_WRITE_OPERATION, TOLINA_BLINK_WRITE_OPERATION}
                        deformation = operation in {DEFORMATION_RIG_WRITE_OPERATION, DEFORMATION_DEMO_WRITE_OPERATION}
                        expected_path = DEFORMATION_LAB_SCENE_PATH if deformation else TOLINA_LAB_SCENE_PATH if tolina else LAB_SCENE_PATH
                        expected_root = DEFORMATION_LAB_ROOT_NAME if deformation else TOLINA_LAB_ROOT_NAME if tolina else LAB_ROOT_NAME
                        if self.scene["path"] != expected_path:
                            code = "LAB_SCENE_REQUIRED"
                        elif self.scene["root_name"] != expected_root:
                            code = "LAB_ROOT_MISMATCH"
                        elif request["operation"] == WRITE_OPERATION and self.created:
                            code = "LAB_ALREADY_CREATED"
                        elif request["operation"] == ANIMATION_WRITE_OPERATION and not self.created:
                            code = "LAB_RIG_REQUIRED"
                        elif request["operation"] == ANIMATION_WRITE_OPERATION and self.animation_created:
                            code = "LAB_ANIMATION_ALREADY_CREATED"
                        elif request["operation"] == ANIMATION_WRITE_OPERATION and self.animation_error:
                            code = self.animation_error
                        elif operation == TOLINA_RIG_WRITE_OPERATION and self.tolina_created:
                            code = "LAB_ALREADY_CREATED"
                        elif operation == TOLINA_RIG_WRITE_OPERATION and self.tolina_rig_error:
                            code = self.tolina_rig_error
                        elif operation == TOLINA_BLINK_WRITE_OPERATION and not self.tolina_created:
                            code = "LAB_RIG_REQUIRED"
                        elif operation == TOLINA_BLINK_WRITE_OPERATION and self.blink_created:
                            code = "LAB_ANIMATION_ALREADY_CREATED"
                        elif operation == TOLINA_BLINK_WRITE_OPERATION and self.blink_error:
                            code = self.blink_error
                        elif operation == DEFORMATION_RIG_WRITE_OPERATION and self.deformation_created:
                            code = "LAB_ALREADY_CREATED"
                        elif operation == DEFORMATION_RIG_WRITE_OPERATION and self.deformation_rig_error:
                            code = self.deformation_rig_error
                        elif operation == DEFORMATION_DEMO_WRITE_OPERATION and not self.deformation_created:
                            code = "LAB_RIG_REQUIRED"
                        elif operation == DEFORMATION_DEMO_WRITE_OPERATION and self.deformation_demo_created:
                            code = "LAB_ANIMATION_ALREADY_CREATED"
                        elif operation == DEFORMATION_DEMO_WRITE_OPERATION and self.deformation_demo_error:
                            code = self.deformation_demo_error
                        else:
                            if request["operation"] == WRITE_OPERATION:
                                self.created = True
                            elif operation == TOLINA_RIG_WRITE_OPERATION:
                                self.tolina_created = True
                            elif operation == DEFORMATION_RIG_WRITE_OPERATION:
                                self.deformation_created = True
                            else:
                                if deformation:
                                    self.deformation_demo_created = True
                                elif tolina:
                                    self.blink_created = True
                                else:
                                    self.animation_created = True
                                for node in self.nodes:
                                    if node["type"] == "AnimationPlayer":
                                        node["animations"] = {"count": 1, "names": ["deformation_demo" if deformation else "blink" if tolina else "bend_tip"], "omitted_reason": None}
                            self.applied_writes += 1
                            self.scene.update(save_state="saved_dirty", dirty_changes=True)
                    if code is not None:
                        response.update(ok=False, result=None, error=error_info(code))
                    if self.ignore_write_reply:
                        continue
                if self.mutate:
                    self.mutate(response)
                await socket.send(encode(response))
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
