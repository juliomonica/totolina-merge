"""Closed v1 wire contracts: metadata reads and four fixed undoable lab writes."""
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
BRIDGE_VERSION = "0.4.0"
MAX_PAYLOAD_BYTES = 256 * 1024
MAX_STRING_BYTES = 4096
MAX_NODES = 2000
MAX_DEPTH = 64
MAX_SELECTED = 128
MAX_PLAYER_ANIMATIONS = 128
MAX_ANIMATIONS = 512
WRITE_OPERATION = "godot_create_rig_lab"
ANIMATION_WRITE_OPERATION = "godot_create_rig_lab_animation"
TOLINA_RIG_WRITE_OPERATION = "godot_create_tolina_rig_lab"
TOLINA_BLINK_WRITE_OPERATION = "godot_create_tolina_lab_blink"
WRITE_OPERATIONS = frozenset({WRITE_OPERATION, ANIMATION_WRITE_OPERATION,
                              TOLINA_RIG_WRITE_OPERATION, TOLINA_BLINK_WRITE_OPERATION})
READ_OPERATIONS = frozenset({"godot_ping", "godot_get_editor_state", "godot_inspect_scene"})
OPERATIONS = READ_OPERATIONS | WRITE_OPERATIONS
LAB_SCENE_PATH = "res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"
LAB_ROOT_NAME = "TotolinaRigLab"
RIG_ROOT_NAME = "TotolinaRigV2"
UNDO_ACTION_NAME = "Lunitora: Create Totolina Rig Lab Scaffold"
ANIMATION_PLAYER_PATH = "TotolinaRigV2/AnimationPlayer"
ANIMATION_UNDO_ACTION_NAME = "Lunitora: Create Rig Lab Animation"
TOLINA_LAB_SCENE_PATH = "res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"
TOLINA_LAB_ROOT_NAME = "TolinaCharacterRigLab"
TOLINA_RIG_ROOT_NAME = "TolinaRig"
TOLINA_RIG_UNDO_ACTION_NAME = "Lunitora: Create Tolina Character Rig"
TOLINA_ANIMATION_PLAYER_PATH = "TolinaRig/AnimationPlayer"
TOLINA_BLINK_UNDO_ACTION_NAME = "Lunitora: Create Tolina Lab Blink"
WRITE_ERRORS = frozenset({"LAB_SCENE_REQUIRED", "LAB_ROOT_MISMATCH", "LAB_ALREADY_CREATED",
                          "RIG_LAB_BUILD_FAILED", "WRITE_REPLAY_REJECTED", "SESSION_WRITE_LIMIT",
                          "WRITE_OUTCOME_UNKNOWN", "WRITE_BUSY", "INVALID_REQUEST", "INVALID_MESSAGE"})
ANIMATION_WRITE_ERRORS = (WRITE_ERRORS - {"LAB_ALREADY_CREATED", "RIG_LAB_BUILD_FAILED"}) | {
    "LAB_RIG_REQUIRED", "LAB_RIG_MISMATCH", "LAB_ANIMATION_ALREADY_CREATED", "LAB_ANIMATION_CONFLICT",
    "LAB_ANIMATION_EDITOR_BUSY", "LAB_ANIMATION_EDITOR_SETTLING", "RIG_LAB_ANIMATION_BUILD_FAILED",
}
TOLINA_RIG_WRITE_ERRORS = (WRITE_ERRORS - {"RIG_LAB_BUILD_FAILED"}) | {
    "TOLINA_SPEC_INVALID", "TOLINA_ASSET_INVALID", "TOLINA_RIG_BUILD_FAILED",
}
TOLINA_BLINK_WRITE_ERRORS = (ANIMATION_WRITE_ERRORS - {"RIG_LAB_ANIMATION_BUILD_FAILED"}) | {
    "TOLINA_SPEC_INVALID", "TOLINA_ASSET_INVALID", "TOLINA_BLINK_BUILD_FAILED",
}
WRITE_ERRORS_BY_OPERATION = {
    WRITE_OPERATION: WRITE_ERRORS, ANIMATION_WRITE_OPERATION: ANIMATION_WRITE_ERRORS,
    TOLINA_RIG_WRITE_OPERATION: TOLINA_RIG_WRITE_ERRORS,
    TOLINA_BLINK_WRITE_OPERATION: TOLINA_BLINK_WRITE_ERRORS,
}
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
    "UNSUPPORTED_OPERATION": "Only registered Godot operations are permitted; no generic editing API exists.",
    "SCENE_TOO_LARGE": "The scene exceeds bounded inspection limits; no partial result was returned.",
    "RESPONSE_TOO_LARGE": "The encoded bridge response exceeds the size limit.",
    "INSPECTION_FAILED": "Godot could not inspect current editor metadata.",
    "LAB_SCENE_REQUIRED": "Open the saved Totolina rig lab scene before creating its scaffold.",
    "LAB_ROOT_MISMATCH": "The rig lab root must be the exact native, script-free local Node2D.",
    "LAB_ALREADY_CREATED": "The reserved TotolinaRigV2 subtree already exists; nothing was replaced.",
    "RIG_LAB_BUILD_FAILED": "Detached rig lab preparation failed before starting an undo action.",
    "WRITE_REPLAY_REJECTED": "This write request ID was already seen; this does not identify its original outcome.",
    "SESSION_WRITE_LIMIT": "This editor session has reached its bounded write request limit.",
    "WRITE_OUTCOME_UNKNOWN": "The write outcome is unknown. Do not retry automatically; obtain a fresh editor read and review the lab.",
    "WRITE_BUSY": "A write is active or awaiting temporal settlement. Obtain a fresh editor read before another write.",
    "LAB_RIG_REQUIRED": "Create the dedicated rig lab scaffold before creating its animation.",
    "LAB_RIG_MISMATCH": "The lab requires the exact native v0.2 scaffold and deterministic rest pose.",
    "LAB_ANIMATION_ALREADY_CREATED": "The fixed bend_tip animation or its global library already exists.",
    "LAB_ANIMATION_CONFLICT": "The lab AnimationPlayer has incompatible animation or playback state.",
    "LAB_ANIMATION_EDITOR_BUSY": "The AnimationPlayer editor or an unclassified observer is attached. Follow the documented recovery procedure.",
    "LAB_ANIMATION_EDITOR_SETTLING": "Detached editor observations have not reached a genuine later process pass. Do not retry automatically.",
    "RIG_LAB_ANIMATION_BUILD_FAILED": "Detached animation preparation failed before starting an undo action.",
    "TOLINA_SPEC_INVALID": "The reviewed Tolina specification failed its pinned digest or closed validation. Nothing was repaired.",
    "TOLINA_ASSET_INVALID": "An approved external Tolina texture or import failed identity, hash, type or dimension validation. Nothing was repaired.",
    "TOLINA_RIG_BUILD_FAILED": "Detached Tolina rig preparation failed before starting an undo action.",
    "TOLINA_BLINK_BUILD_FAILED": "Detached Tolina blink preparation failed before starting an undo action.",
}
# Shared rejection codes retain the legacy writer's exact diagnostic text. Only
# the fixed v0.4 operations select these truthful Tolina-specific descriptions.
TOLINA_ERROR_MESSAGES = {
    "LAB_SCENE_REQUIRED": "Open the saved Tolina character rig lab scene before using this fixed writer.",
    "LAB_ROOT_MISMATCH": "The Tolina lab root must be the exact native, script-free local Node2D.",
    "LAB_ALREADY_CREATED": "The reserved TolinaRig subtree already exists; nothing was replaced.",
    "LAB_RIG_REQUIRED": "Create the dedicated Tolina character rig before creating its blink.",
    "LAB_RIG_MISMATCH": "The Tolina lab requires the exact reviewed native v0.4 rig and deterministic rest state.",
    "LAB_ANIMATION_ALREADY_CREATED": "The fixed blink animation or its global library already exists.",
}
ErrorCode = Literal[
    "DISCONNECTED", "TIMEOUT", "BUSY", "PORT_IN_USE", "EDITOR_BUSY", "AUTH_FAILED",
    "LOCAL_AUTH_UNSAFE", "PROJECT_MISMATCH", "UNSUPPORTED_HOST", "INVALID_REQUEST",
    "INVALID_MESSAGE", "UNSUPPORTED_OPERATION", "SCENE_TOO_LARGE", "RESPONSE_TOO_LARGE",
    "INSPECTION_FAILED",
    "LAB_SCENE_REQUIRED", "LAB_ROOT_MISMATCH", "LAB_ALREADY_CREATED", "RIG_LAB_BUILD_FAILED",
    "WRITE_REPLAY_REJECTED", "SESSION_WRITE_LIMIT", "WRITE_OUTCOME_UNKNOWN", "WRITE_BUSY",
    "LAB_RIG_REQUIRED", "LAB_RIG_MISMATCH", "LAB_ANIMATION_ALREADY_CREATED", "LAB_ANIMATION_CONFLICT",
    "LAB_ANIMATION_EDITOR_BUSY", "LAB_ANIMATION_EDITOR_SETTLING", "RIG_LAB_ANIMATION_BUILD_FAILED",
    "TOLINA_SPEC_INVALID", "TOLINA_ASSET_INVALID", "TOLINA_RIG_BUILD_FAILED", "TOLINA_BLINK_BUILD_FAILED",
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
    plugin_version: Literal["0.4.0"]
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
    bridge_version: Literal["0.4.0"]
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


@with_config(extra="forbid")
class RigLabData(TypedDict):
    editor_session_id: NonEmptyString
    project_path: NonEmptyString
    scene_path: Literal["res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"]
    root_name: Literal["TotolinaRigLab"]
    created_root: Literal["TotolinaRigV2"]
    created_node_count: Annotated[int, Field(strict=True, ge=7, le=7)]
    undo_action_name: Literal["Lunitora: Create Totolina Rig Lab Scaffold"]
    undo_actions_added: Annotated[int, Field(strict=True, ge=1, le=1)]
    save_state: Literal["saved_dirty"]
    auto_saved: Literal[False]
    read_only: Literal[False]


@with_config(extra="forbid")
class RigLabResult(Envelope):
    result: RigLabData | None


@with_config(extra="forbid")
class RigLabAnimationData(TypedDict):
    editor_session_id: NonEmptyString
    project_path: NonEmptyString
    scene_path: Literal["res://addons/lunitora_godot/labs/totolina_rig_lab.tscn"]
    root_name: Literal["TotolinaRigLab"]
    animation_player_path: Literal["TotolinaRigV2/AnimationPlayer"]
    library_name: Literal[""]
    animation_name: Literal["bend_tip"]
    animation_key: Literal["bend_tip"]
    length_seconds: Annotated[float, Field(strict=True, ge=1.0, le=1.0, allow_inf_nan=False)]
    track_count: Annotated[int, Field(strict=True, ge=1, le=1)]
    key_count: Annotated[int, Field(strict=True, ge=3, le=3)]
    undo_action_name: Literal["Lunitora: Create Rig Lab Animation"]
    undo_actions_added: Annotated[int, Field(strict=True, ge=1, le=1)]
    save_state: Literal["saved_dirty"]
    auto_saved: Literal[False]
    read_only: Literal[False]


@with_config(extra="forbid")
class RigLabAnimationResult(Envelope):
    result: RigLabAnimationData | None


@with_config(extra="forbid")
class TolinaRigLabData(TypedDict):
    editor_session_id: NonEmptyString
    project_path: NonEmptyString
    scene_path: Literal["res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"]
    root_name: Literal["TolinaCharacterRigLab"]
    created_root: Literal["TolinaRig"]
    created_node_count: Annotated[int, Field(strict=True, ge=21, le=21)]
    undo_action_name: Literal["Lunitora: Create Tolina Character Rig"]
    undo_actions_added: Annotated[int, Field(strict=True, ge=1, le=1)]
    save_state: Literal["saved_dirty"]
    auto_saved: Literal[False]
    read_only: Literal[False]


@with_config(extra="forbid")
class TolinaRigLabResult(Envelope):
    result: TolinaRigLabData | None


@with_config(extra="forbid")
class TolinaLabBlinkData(TypedDict):
    editor_session_id: NonEmptyString
    project_path: NonEmptyString
    scene_path: Literal["res://addons/lunitora_godot/labs/tolina_character_rig_lab.tscn"]
    root_name: Literal["TolinaCharacterRigLab"]
    animation_player_path: Literal["TolinaRig/AnimationPlayer"]
    library_name: Literal[""]
    animation_name: Literal["blink"]
    animation_key: Literal["blink"]
    length_seconds: Annotated[float, Field(strict=True, ge=0.24, le=0.24, allow_inf_nan=False)]
    track_count: Annotated[int, Field(strict=True, ge=3, le=3)]
    key_count: Annotated[int, Field(strict=True, ge=18, le=18)]
    undo_action_name: Literal["Lunitora: Create Tolina Lab Blink"]
    undo_actions_added: Annotated[int, Field(strict=True, ge=1, le=1)]
    save_state: Literal["saved_dirty"]
    auto_saved: Literal[False]
    read_only: Literal[False]


@with_config(extra="forbid")
class TolinaLabBlinkResult(Envelope):
    result: TolinaLabBlinkData | None


def error_info(code: str, *, operation: str | None = None) -> ErrorInfo:
    messages = TOLINA_ERROR_MESSAGES if operation in {TOLINA_RIG_WRITE_OPERATION, TOLINA_BLINK_WRITE_OPERATION} else {}
    return {"code": code, "message": messages.get(code, ERROR_MESSAGES[code])}


def envelope(result: dict | None = None, *, elapsed_ms: float | None = None,
             error: BridgeError | None = None, operation: str | None = None) -> dict:
    if error is None and (result is None or elapsed_ms is None or not math.isfinite(elapsed_ms) or elapsed_ms < 0):
        raise ValueError("Successful result requires bounded timing and metadata.")
    return {"ok": error is None, "connected": error is None or error.connected,
            "protocol_version": PROTOCOL_VERSION, "bridge_version": BRIDGE_VERSION,
            "round_trip_ms": elapsed_ms, "result": result if error is None else None,
            "error": error_info(error.code, operation=operation) if error else None}


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
    elif operation in {WRITE_OPERATION, TOLINA_RIG_WRITE_OPERATION}:
        _fields(data, {"editor_session_id", "project_path", "scene_path", "root_name", "created_root",
                       "created_node_count", "undo_action_name", "undo_actions_added", "save_state",
                       "auto_saved", "read_only"})
        require(_string(data["editor_session_id"]) and _string(data["project_path"]))
        if operation == TOLINA_RIG_WRITE_OPERATION:
            scene_path, root_name = TOLINA_LAB_SCENE_PATH, TOLINA_LAB_ROOT_NAME
            created_root, action_name, node_count = TOLINA_RIG_ROOT_NAME, TOLINA_RIG_UNDO_ACTION_NAME, 21
        else:
            scene_path, root_name = LAB_SCENE_PATH, LAB_ROOT_NAME
            created_root, action_name, node_count = RIG_ROOT_NAME, UNDO_ACTION_NAME, 7
        require(data["scene_path"] == scene_path and data["root_name"] == root_name
                and data["created_root"] == created_root and data["undo_action_name"] == action_name)
        require(type(data["created_node_count"]) is int and data["created_node_count"] == node_count
                and type(data["undo_actions_added"]) is int and data["undo_actions_added"] == 1)
        require(data["save_state"] == "saved_dirty" and data["auto_saved"] is False and data["read_only"] is False)
    elif operation in {ANIMATION_WRITE_OPERATION, TOLINA_BLINK_WRITE_OPERATION}:
        _fields(data, {"editor_session_id", "project_path", "scene_path", "root_name",
                       "animation_player_path", "library_name", "animation_name", "animation_key",
                       "length_seconds", "track_count", "key_count", "undo_action_name",
                       "undo_actions_added", "save_state", "auto_saved", "read_only"})
        require(_string(data["editor_session_id"]) and _string(data["project_path"]))
        if operation == TOLINA_BLINK_WRITE_OPERATION:
            scene_path, root_name = TOLINA_LAB_SCENE_PATH, TOLINA_LAB_ROOT_NAME
            player_path, animation_name = TOLINA_ANIMATION_PLAYER_PATH, "blink"
            action_name, length, track_count, key_count = TOLINA_BLINK_UNDO_ACTION_NAME, 0.24, 3, 18
        else:
            scene_path, root_name = LAB_SCENE_PATH, LAB_ROOT_NAME
            player_path, animation_name = ANIMATION_PLAYER_PATH, "bend_tip"
            action_name, length, track_count, key_count = ANIMATION_UNDO_ACTION_NAME, 1.0, 1, 3
        require(data["scene_path"] == scene_path and data["root_name"] == root_name
                and data["animation_player_path"] == player_path and data["library_name"] == ""
                and data["animation_name"] == animation_name and data["animation_key"] == animation_name
                and data["undo_action_name"] == action_name)
        require(type(data["length_seconds"]) in {int, float} and data["length_seconds"] == length
                and type(data["track_count"]) is int and data["track_count"] == track_count
                and type(data["key_count"]) is int and data["key_count"] == key_count
                and type(data["undo_actions_added"]) is int and data["undo_actions_added"] == 1)
        require(data["save_state"] == "saved_dirty" and data["auto_saved"] is False and data["read_only"] is False)
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
    fields = {"type", "protocol_version", "id", "operation", "ok", "result", "error"}
    if type(message.get("operation")) is str and message["operation"] in WRITE_OPERATIONS:
        fields.add("editor_session_id")
    _fields(message, fields)
    require(type(message["protocol_version"]) is int and message["protocol_version"] == PROTOCOL_VERSION
            and message["type"] == "response" and is_hex(message["id"], 32)
            and type(message["operation"]) is str and type(message["ok"]) is bool)
    require(message["operation"] in OPERATIONS, "UNSUPPORTED_OPERATION")
    if message["operation"] in WRITE_OPERATIONS:
        require(_string(message["editor_session_id"]))
    if message["ok"]:
        require(message["error"] is None)
        validate_result(message["operation"], message["result"])
        if message["operation"] in WRITE_OPERATIONS:
            require(message["result"]["editor_session_id"] == message["editor_session_id"])
    else:
        require(message["result"] is None)
        _fields(message["error"], {"code", "message"})
        require(type(message["error"]["code"]) is str and message["error"]["code"] in ERROR_MESSAGES
                and _string(message["error"]["message"], empty=True))
        if message["operation"] in WRITE_OPERATIONS:
            require(message["error"]["code"] in WRITE_ERRORS_BY_OPERATION[message["operation"]])
