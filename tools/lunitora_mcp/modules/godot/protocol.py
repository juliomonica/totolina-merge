"""Closed v1 wire and result contracts. No editor mutations exist in this protocol."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
from typing import Annotated, Literal

from pydantic import Field, with_config
from typing_extensions import TypedDict

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_STRING_BYTES = 4096
MAX_NODES = 2000
MAX_DEPTH = 64
MAX_SELECTED = 128
MAX_PLAYER_ANIMATIONS = 128
MAX_ANIMATIONS = 512
OPERATIONS = frozenset({"godot_ping", "godot_get_editor_state", "godot_inspect_scene"})
ERROR_MESSAGES = {
    "DISCONNECTED": "Godot editor is disconnected. Open this project with the editor plugin enabled.",
    "TIMEOUT": "Godot did not reply before the request deadline.",
    "BUSY": "The bridge has reached its connection or in-flight request limit.",
    "PORT_IN_USE": "Cannot bind 127.0.0.1:43128. Stop the other listener; no alternate port is used.",
    "EDITOR_BUSY": "Godot editor inspection is temporarily unavailable.",
    "AUTH_FAILED": "Mutual local authentication failed. Check the project's protected credential.",
    "LOCAL_AUTH_UNSAFE": "Local credential storage is unavailable or unsafe. See GODOT_README.md.",
    "PROJECT_MISMATCH": "The editor or credential belongs to a different project.",
    "UNSUPPORTED_HOST": "This editor plugin requires Godot 4.7.",
    "INVALID_REQUEST": "Each Godot tool accepts exactly an empty object.",
    "INVALID_MESSAGE": "The peer sent an invalid bridge message.",
    "UNSUPPORTED_OPERATION": "Only the three registered read-only Godot operations are permitted.",
    "SCENE_TOO_LARGE": "The scene exceeds bounded inspection limits; no partial result was returned.",
    "RESPONSE_TOO_LARGE": "The encoded bridge response exceeds the size limit.",
    "INSPECTION_FAILED": "Godot could not inspect current editor metadata.",
}
ErrorCode = Literal[
    "DISCONNECTED", "TIMEOUT", "BUSY", "PORT_IN_USE", "EDITOR_BUSY", "AUTH_FAILED",
    "LOCAL_AUTH_UNSAFE", "PROJECT_MISMATCH", "UNSUPPORTED_HOST", "INVALID_REQUEST",
    "INVALID_MESSAGE", "UNSUPPORTED_OPERATION", "SCENE_TOO_LARGE", "RESPONSE_TOO_LARGE",
    "INSPECTION_FAILED",
]
BoundedString = Annotated[str, Field(max_length=MAX_STRING_BYTES)]
NonEmptyString = Annotated[str, Field(min_length=1, max_length=MAX_STRING_BYTES)]
Count = Annotated[int, Field(strict=True, ge=0)]


class BridgeError(Exception):
    def __init__(self, code: str, *, connected: bool = False):
        self.code = code if code in ERROR_MESSAGES else "INVALID_MESSAGE"
        self.connected = connected
        super().__init__(ERROR_MESSAGES[self.code])


@with_config(extra="forbid")
class ErrorInfo(TypedDict):
    code: ErrorCode
    message: BoundedString


@with_config(extra="forbid")
class PingData(TypedDict):
    godot_version: NonEmptyString
    project_path: NonEmptyString
    project_name: BoundedString
    plugin_version: Literal["0.1.0"]
    editor_session_id: NonEmptyString
    read_only: Literal[True]


@with_config(extra="forbid")
class SceneInfo(TypedDict):
    exists: bool
    path: NonEmptyString | None
    root_name: NonEmptyString | None
    has_saved_path: bool
    save_state: Literal["no_scene", "new_unsaved", "saved_clean", "saved_dirty"]
    dirty_changes: bool | None
    dirty_reason: Literal["no_scene", "unnamed_scene"] | None


@with_config(extra="forbid")
class SelectedNode(TypedDict):
    path: NonEmptyString
    type: NonEmptyString


@with_config(extra="forbid")
class SelectionInfo(TypedDict):
    total_count: Count
    nodes: Annotated[list[SelectedNode], Field(max_length=MAX_SELECTED)]
    truncated: bool


@with_config(extra="forbid")
class EditorStateData(PingData):
    scene: SceneInfo
    selected_nodes: SelectionInfo


@with_config(extra="forbid")
class AnimationInfo(TypedDict):
    count: Count
    names: Annotated[list[NonEmptyString], Field(max_length=MAX_PLAYER_ANIMATIONS)] | None
    omitted_reason: Literal["limit"] | None


@with_config(extra="forbid")
class NodeInfo(TypedDict):
    path: NonEmptyString
    parent_path: NonEmptyString | None
    type: NonEmptyString
    child_count: Annotated[int, Field(strict=True, ge=0, le=MAX_NODES - 1)]
    kind: Literal["skeleton2d", "bone2d", "polygon2d", "animation_player"] | None
    animations: AnimationInfo | None


@with_config(extra="forbid")
class SceneInspectionData(TypedDict):
    editor_session_id: NonEmptyString
    scene: SceneInfo
    nodes: Annotated[list[NodeInfo], Field(max_length=MAX_NODES)]


@with_config(extra="forbid")
class Envelope(TypedDict):
    ok: bool
    connected: bool
    protocol_version: Literal[1]
    bridge_version: Literal["0.1.0"]
    round_trip_ms: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None
    error: ErrorInfo | None


@with_config(extra="forbid")
class PingResult(Envelope):
    result: PingData | None


@with_config(extra="forbid")
class EditorStateResult(Envelope):
    result: EditorStateData | None


@with_config(extra="forbid")
class SceneInspectionResult(Envelope):
    result: SceneInspectionData | None


def error_info(code: str) -> ErrorInfo:
    return {"code": code, "message": ERROR_MESSAGES[code]}


def envelope(result: dict | None = None, *, elapsed_ms: float | None = None,
             error: BridgeError | None = None) -> dict:
    if error is None and (result is None or elapsed_ms is None or not math.isfinite(elapsed_ms) or elapsed_ms < 0):
        raise ValueError("Successful result requires bounded timing and metadata.")
    return {"ok": error is None, "connected": error is None or error.connected,
            "protocol_version": PROTOCOL_VERSION, "bridge_version": BRIDGE_VERSION,
            "round_trip_ms": elapsed_ms, "result": result if error is None else None,
            "error": error_info(error.code) if error else None}


def require(condition: bool, code: str = "INVALID_MESSAGE") -> None:
    if not condition:
        raise BridgeError(code)


def is_hex(value: object, size: int) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % size, value) is not None


def proof(secret: bytes, project_id: str, client_nonce: str, server_nonce: str, role: str) -> str:
    require(role in {"server", "client"} and len(secret) == 32)
    require(all(is_hex(value, 64) for value in (project_id, client_nonce, server_nonce)))
    transcript = f"lunitora-godot\n1\n{project_id}\n{client_nonce}\n{server_nonce}\n{role}\n".encode("ascii")
    return hmac.new(secret, transcript, hashlib.sha256).hexdigest()


def encode(message: dict) -> str:
    try:
        raw = json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        require(len(raw.encode("utf-8")) <= MAX_PAYLOAD_BYTES, "RESPONSE_TOO_LARGE")
        return raw
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BridgeError("INVALID_MESSAGE") from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def decode(raw: str | bytes) -> dict:
    require(type(raw) is str)
    try:
        require(len(raw.encode("utf-8")) <= MAX_PAYLOAD_BYTES, "RESPONSE_TOO_LARGE")
        message = json.loads(raw, object_pairs_hook=_unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise BridgeError("INVALID_MESSAGE") from None
    require(type(message) is dict and type(message.get("protocol_version")) is int
            and message["protocol_version"] == PROTOCOL_VERSION)
    return message


def validate_hello(message: dict) -> None:
    _fields(message, {"type", "protocol_version", "project_id", "client_nonce"})
    require(type(message["protocol_version"]) is int and message["protocol_version"] == PROTOCOL_VERSION
            and message["type"] == "hello" and is_hex(message["project_id"], 64)
            and is_hex(message["client_nonce"], 64))


def validate_authenticate(message: dict) -> None:
    _fields(message, {"type", "protocol_version", "proof"})
    require(type(message["protocol_version"]) is int and message["protocol_version"] == PROTOCOL_VERSION
            and message["type"] == "authenticate" and is_hex(message["proof"], 64))


def _string(value: object, *, empty: bool = False) -> bool:
    if type(value) is not str:
        return False
    try:
        return (empty or bool(value)) and len(value.encode("utf-8")) <= MAX_STRING_BYTES
    except UnicodeError:
        return False


def _fields(value: object, fields: set[str]) -> None:
    require(type(value) is dict and set(value) == fields)


def _count(value: object) -> bool:
    return type(value) is int and value >= 0


def _path(value: object) -> bool:
    return _string(value) and (value == "." or not value.startswith(("/", ":"))
                              and ":" not in value and "\\" not in value
                              and all(part not in {"", ".", ".."} for part in value.split("/")))


def validate_scene(scene: dict) -> None:
    _fields(scene, {"exists", "path", "root_name", "has_saved_path", "save_state", "dirty_changes", "dirty_reason"})
    require(type(scene["exists"]) is bool and type(scene["has_saved_path"]) is bool)
    if not scene["exists"]:
        require(scene == {"exists": False, "path": None, "root_name": None, "has_saved_path": False,
                          "save_state": "no_scene", "dirty_changes": None, "dirty_reason": "no_scene"})
        return
    require(_string(scene["root_name"]))
    if scene["has_saved_path"]:
        require(_string(scene["path"]) and scene["path"].startswith("res://"))
        require(type(scene["dirty_changes"]) is bool and scene["dirty_reason"] is None)
        require(scene["save_state"] == ("saved_dirty" if scene["dirty_changes"] else "saved_clean"))
    else:
        require(scene["path"] is None and scene["save_state"] == "new_unsaved"
                and scene["dirty_changes"] is None and scene["dirty_reason"] == "unnamed_scene")


def _ping(data: dict) -> None:
    for field in ("godot_version", "project_path", "editor_session_id"):
        require(_string(data[field]))
    require(_string(data["project_name"], empty=True) and data["plugin_version"] == BRIDGE_VERSION
            and data["read_only"] is True)
    require(data["godot_version"].startswith("4.7."), "UNSUPPORTED_HOST")


def validate_result(operation: str, data: dict) -> None:
    require(operation in OPERATIONS, "UNSUPPORTED_OPERATION")
    ping_fields = {"godot_version", "project_path", "project_name", "plugin_version", "editor_session_id", "read_only"}
    if operation == "godot_ping":
        _fields(data, ping_fields)
        _ping(data)
    elif operation == "godot_get_editor_state":
        _fields(data, ping_fields | {"scene", "selected_nodes"})
        _ping(data)
        validate_scene(data["scene"])
        selection = data["selected_nodes"]
        _fields(selection, {"total_count", "nodes", "truncated"})
        require(_count(selection["total_count"]) and type(selection["nodes"]) is list
                and len(selection["nodes"]) <= MAX_SELECTED and type(selection["truncated"]) is bool)
        require(len(selection["nodes"]) == min(selection["total_count"], MAX_SELECTED)
                and selection["truncated"] == (selection["total_count"] > MAX_SELECTED))
        require(data["scene"]["exists"] or selection["total_count"] == 0)
        seen = set()
        for node in selection["nodes"]:
            _fields(node, {"path", "type"})
            require(_path(node["path"]) and _string(node["type"]) and node["path"] not in seen)
            seen.add(node["path"])
    else:
        _fields(data, {"editor_session_id", "scene", "nodes"})
        require(_string(data["editor_session_id"]))
        validate_scene(data["scene"])
        require(type(data["nodes"]) is list and len(data["nodes"]) <= MAX_NODES)
        if not data["scene"]["exists"]:
            require(data["nodes"] == [])
            return
        require(bool(data["nodes"]))
        known: dict[str, dict] = {}
        children: dict[str, int] = {}
        animation_total = 0
        kind_types = {"Skeleton2D": "skeleton2d", "Bone2D": "bone2d", "Polygon2D": "polygon2d",
                      "AnimationPlayer": "animation_player"}
        for node in data["nodes"]:
            _fields(node, {"path", "parent_path", "type", "child_count", "kind", "animations"})
            path = node["path"]
            require(_path(path) and path not in known and _string(node["type"])
                    and _count(node["child_count"]) and node["child_count"] < MAX_NODES)
            require(node["kind"] == kind_types.get(node["type"]))
            depth = 0 if path == "." else len(path.split("/"))
            require(depth <= MAX_DEPTH)
            parent = None if path == "." else path.rsplit("/", 1)[0] if "/" in path else "."
            require(node["parent_path"] == parent and (parent is None and not known or parent in known))
            known[path] = node
            children[path] = 0
            if parent is not None:
                children[parent] += 1
            if node["kind"] != "animation_player":
                require(node["animations"] is None)
                continue
            animations = node["animations"]
            _fields(animations, {"count", "names", "omitted_reason"})
            require(_count(animations["count"]))
            if animations["names"] is None:
                require(animations["omitted_reason"] == "limit"
                        and (animations["count"] > MAX_PLAYER_ANIMATIONS
                             or animation_total + animations["count"] > MAX_ANIMATIONS))
            else:
                names = animations["names"]
                require(type(names) is list and len(names) == animations["count"] <= MAX_PLAYER_ANIMATIONS
                        and animations["omitted_reason"] is None and all(_string(name) for name in names)
                        and len(set(names)) == len(names))
                animation_total += len(names)
                require(animation_total <= MAX_ANIMATIONS)
        require(all(node["child_count"] == children[path] for path, node in known.items()))


def validate_response(message: dict) -> None:
    _fields(message, {"type", "protocol_version", "id", "operation", "ok", "result", "error"})
    require(type(message["protocol_version"]) is int and message["protocol_version"] == PROTOCOL_VERSION
            and message["type"] == "response" and is_hex(message["id"], 32)
            and type(message["operation"]) is str and type(message["ok"]) is bool)
    require(message["operation"] in OPERATIONS, "UNSUPPORTED_OPERATION")
    if message["ok"]:
        require(message["error"] is None)
        validate_result(message["operation"], message["result"])
    else:
        require(message["result"] is None)
        _fields(message["error"], {"code", "message"})
        require(type(message["error"]["code"]) is str and message["error"]["code"] in ERROR_MESSAGES
                and _string(message["error"]["message"], empty=True))
