"""Version 1 wire protocol and safe, structured results."""
from __future__ import annotations

import json
import math
from typing import NotRequired, TypedDict

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"
MAX_PAYLOAD_BYTES = 262_144
MAX_LAYERS = 2000
MAX_DEPTH = 64
OPERATIONS = frozenset({"photoshop_ping", "photoshop_get_active_document"})
ERROR_MESSAGES = {
    "UNPAIRED": "Run local setup and pair the Photoshop panel.",
    "PORT_IN_USE": "Cannot bind 127.0.0.1:43127. Stop the other listener; no alternate interface or port is used.",
    "DISCONNECTED": "Photoshop is disconnected. Load the UXP panel and select Connect / Reconnect.",
    "TIMEOUT": "Photoshop did not reply before the request deadline.",
    "BUSY": "The bridge has reached its bounded in-flight request limit.",
    "AUTH_FAILED": "Pairing failed. Use the toolkit's local pairing token.",
    "INVALID_MESSAGE": "The peer sent an invalid bridge message.",
    "PAYLOAD_TOO_LARGE": "The bridge message exceeds the size limit.",
    "UNSUPPORTED_OPERATION": "Only photoshop_ping and photoshop_get_active_document are permitted.",
    "PHOTOSHOP_READ_FAILED": "Photoshop could not read the current document. Retry when the host is available.",
    "HOST_DETECTION_FAILED": "Could not detect valid Adobe host metadata from UXP. Reload the Photoshop plugin and retry.",
    "DOCUMENT_TOO_LARGE": "The document exceeds the layer, depth, or response-size limit; no partial result was returned.",
    "UNSUPPORTED_HOST": "This plugin requires Photoshop 27.10 or newer.",
}


class BridgeError(Exception):
    def __init__(self, code: str, *, connected: bool = False):
        self.code = code if code in ERROR_MESSAGES else "INVALID_MESSAGE"
        self.connected = connected
        super().__init__(ERROR_MESSAGES[self.code])


class ErrorInfo(TypedDict):
    code: str
    message: str


class PingData(TypedDict):
    host_name: NotRequired[str]
    photoshop_version: str
    host_version: str | None
    uxp_version: str | None
    plugin_version: str


class LayerInfo(TypedDict):
    id: int
    name: str
    kind: str
    children: list[LayerInfo]


class ArtboardInfo(TypedDict):
    id: int
    name: str


class DocumentInfo(TypedDict):
    id: int
    name: str
    width_px: float
    height_px: float
    saved: bool | None
    top_level_layer_count: int
    recursive_layer_count: int
    layers: list[LayerInfo]
    artboard_count: int
    artboards: list[ArtboardInfo]


class DocumentData(TypedDict):
    has_document: bool
    document: DocumentInfo | None


class Envelope(TypedDict):
    ok: bool
    connected: bool
    protocol_version: int
    bridge_version: str
    round_trip_ms: float | None
    error: ErrorInfo | None


class PingResult(Envelope):
    result: PingData | None


class DocumentResult(Envelope):
    result: DocumentData | None


def error_info(code: str) -> ErrorInfo:
    return {"code": code, "message": ERROR_MESSAGES[code]}


def envelope(result: dict | None = None, *, elapsed_ms: float | None = None,
             error: BridgeError | None = None) -> dict:
    return {
        "ok": error is None,
        "connected": error is None or error.connected,
        "protocol_version": PROTOCOL_VERSION,
        "bridge_version": BRIDGE_VERSION,
        "round_trip_ms": elapsed_ms,
        "result": result if error is None else None,
        "error": error_info(error.code) if error else None,
    }


def encode(message: dict) -> str:
    raw = json.dumps(message, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise BridgeError("PAYLOAD_TOO_LARGE")
    return raw


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def decode(raw: str | bytes) -> dict:
    if not isinstance(raw, str):
        raise BridgeError("INVALID_MESSAGE")
    if len(raw.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise BridgeError("PAYLOAD_TOO_LARGE")
    try:
        message = json.loads(raw, object_pairs_hook=_unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, RecursionError):
        raise BridgeError("INVALID_MESSAGE") from None
    if (not isinstance(message, dict)
            or type(message.get("protocol_version")) is not int
            or message["protocol_version"] != PROTOCOL_VERSION):
        raise BridgeError("INVALID_MESSAGE")
    return message


def validate_response(message: dict) -> None:
    if set(message) != {"type", "protocol_version", "id", "operation", "ok", "result", "error"}:
        raise BridgeError("INVALID_MESSAGE")
    if (message["type"] != "response" or not isinstance(message["id"], str)
            or not 1 <= len(message["id"]) <= 64 or type(message["ok"]) is not bool):
        raise BridgeError("INVALID_MESSAGE")
    if not isinstance(message["operation"], str):
        raise BridgeError("INVALID_MESSAGE")
    if message["operation"] not in OPERATIONS:
        raise BridgeError("UNSUPPORTED_OPERATION")
    if message["ok"]:
        if not isinstance(message["result"], dict) or message["error"] is not None:
            raise BridgeError("INVALID_MESSAGE")
        validate_result(message["operation"], message["result"])
    elif (message["result"] is not None or not isinstance(message["error"], dict)
          or not isinstance(message["error"].get("code"), str)
          or message["error"]["code"] not in ERROR_MESSAGES):
        raise BridgeError("INVALID_MESSAGE")


def validate_result(operation: str, data: dict) -> None:
    """Reject malformed/stale peer data before reporting a successful tool call."""
    def require(condition: bool) -> None:
        if not condition:
            raise BridgeError("INVALID_MESSAGE")

    def identity(value: dict) -> None:
        require(type(value.get("id")) is int and isinstance(value.get("name"), str))

    if operation == "photoshop_ping":
        required = {"photoshop_version", "host_version", "uxp_version", "plugin_version"}
        require(set(data) in (required, required | {"host_name"}))
        if "host_name" in data:
            require(isinstance(data["host_name"], str) and 0 < len(data["host_name"]) < 100
                    and bool(data["host_name"].strip()))
        for field in ("photoshop_version", "plugin_version"):
            require(isinstance(data[field], str) and 0 < len(data[field]) < 100)
        for field in ("host_version", "uxp_version"):
            require(data[field] is None or isinstance(data[field], str) and len(data[field]) < 100)
        return
    require(set(data) == {"has_document", "document"} and type(data["has_document"]) is bool)
    if not data["has_document"]:
        require(data["document"] is None)
        return
    doc = data["document"]
    require(isinstance(doc, dict))
    require(set(doc) == {"id", "name", "width_px", "height_px", "saved", "layers",
                         "top_level_layer_count", "recursive_layer_count", "artboards", "artboard_count"})
    identity(doc)
    for field in ("width_px", "height_px"):
        require(type(doc[field]) in (int, float) and math.isfinite(doc[field]) and doc[field] > 0)
    require(doc["saved"] is None or type(doc["saved"]) is bool)
    require(isinstance(doc["layers"], list) and isinstance(doc["artboards"], list))
    for field in ("top_level_layer_count", "recursive_layer_count", "artboard_count"):
        require(type(doc[field]) is int and 0 <= doc[field] <= MAX_LAYERS)
    require(doc["top_level_layer_count"] == len(doc["layers"]))
    require(doc["artboard_count"] == len(doc["artboards"]))
    seen = set()
    stack = [(layer, 1) for layer in doc["layers"]]
    while stack:
        layer, depth = stack.pop()
        require(isinstance(layer, dict))
        require(set(layer) == {"id", "name", "kind", "children"})
        identity(layer)
        require(layer["id"] not in seen and depth <= MAX_DEPTH and len(seen) < MAX_LAYERS)
        seen.add(layer["id"])
        require(isinstance(layer["kind"], str) and isinstance(layer["children"], list))
        stack.extend((child, depth + 1) for child in layer["children"])
    require(doc["recursive_layer_count"] == len(seen))
    artboard_ids = set()
    for artboard in doc["artboards"]:
        require(isinstance(artboard, dict) and set(artboard) == {"id", "name"})
        identity(artboard)
        require(artboard["id"] in seen and artboard["id"] not in artboard_ids)
        artboard_ids.add(artboard["id"])
