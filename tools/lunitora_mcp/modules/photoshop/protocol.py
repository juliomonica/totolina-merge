"""Version 1 wire protocol and safe, structured results."""
from __future__ import annotations

import json
import math
import base64
import binascii
from typing import NotRequired, TypedDict

from .png_validation import MAX_IMAGE_BYTES

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.1.0"
MAX_INSPECTION_BYTES = 262_144
MAX_IMAGE_BASE64_BYTES = 4 * ((MAX_IMAGE_BYTES + 2) // 3)
# One PNG per message, plus bounded JSON metadata (including escaped request IDs).
MAX_PAYLOAD_BYTES = MAX_IMAGE_BASE64_BYTES + 1024
MAX_LAYERS = 2000
MAX_DEPTH = 64
PROCESS_OPERATION = "photoshop_process_image"
OPERATIONS = frozenset({"photoshop_ping", "photoshop_get_active_document", PROCESS_OPERATION})
ERROR_MESSAGES = {
    "UNPAIRED": "Run local setup and pair the Photoshop panel.",
    "PORT_IN_USE": "Cannot bind 127.0.0.1:43127. Stop the other listener; no alternate interface or port is used.",
    "DISCONNECTED": "Photoshop is disconnected. Load the UXP panel and select Connect / Reconnect.",
    "TIMEOUT": "Photoshop did not reply before the request deadline.",
    "BUSY": "The bridge has reached its bounded in-flight request limit.",
    "AUTH_FAILED": "Pairing failed. Use the toolkit's local pairing token.",
    "INVALID_MESSAGE": "The peer sent an invalid bridge message.",
    "PAYLOAD_TOO_LARGE": "The bridge message exceeds the size limit.",
    "UNSUPPORTED_OPERATION": "Only the registered Photoshop operations are permitted.",
    "PHOTOSHOP_READ_FAILED": "Photoshop could not read the current document. Retry when the host is available.",
    "HOST_DETECTION_FAILED": "Could not detect valid Adobe host metadata from UXP. Reload the Photoshop plugin and retry.",
    "DOCUMENT_TOO_LARGE": "The document exceeds the layer, depth, or response-size limit; no partial result was returned.",
    "UNSUPPORTED_HOST": "This plugin requires Photoshop 27.10 or newer.",
    "INVALID_PATH": "Use a PNG repository-relative path inside the required inbox or staging directory.",
    "PATH_UNSAFE": "The path is linked, redirected, shared for writing, or otherwise unsafe.",
    "UNSUPPORTED_PLATFORM": "Phase 2A path protection currently requires native Windows.",
    "SOURCE_NOT_FOUND": "The selected inbox image does not exist.",
    "DESTINATION_EXISTS": "The staging destination already exists; choose a new filename.",
    "INVALID_DIMENSIONS": "Canvas width and height must be integers from 1 through 2048.",
    "CANVAS_TOO_SMALL": "The requested canvas would crop the image; use its original size or a larger canvas.",
    "IMAGE_TOO_LARGE": "Phase 2A input and output PNGs must each fit within 24 MiB.",
    "INVALID_IMAGE": "Phase 2A requires a complete non-interlaced 8-bit RGBA PNG.",
    "BACKGROUND_REMOVAL_UNAVAILABLE": "Reliable offline background removal is not enabled in Phase 2A.",
    "PHOTOSHOP_PROCESSING_FAILED": "Photoshop could not process the temporary image; no candidate was published.",
    "OUTPUT_VALIDATION_FAILED": "The exported PNG failed independent dimensions, alpha, or padding validation.",
    "STAGING_WRITE_FAILED": "The candidate could not be published safely in staging.",
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


class ProcessingValidation(TypedDict):
    format: str
    bit_depth: int
    color_type: str
    has_transparency: bool
    dimensions_verified: bool
    source_alpha_preserved: bool
    padding_verified: bool
    source_unchanged: bool
    bytes_written: int
    sha256: str
    human_approval_required: bool


class ProcessingData(TypedDict):
    source_relative_path: str
    staging_relative_path: str
    width_px: int
    height_px: int
    background_removal_requested: bool
    background_removal_completed: bool
    validation: ProcessingValidation


class ProcessingResult(Envelope):
    result: ProcessingData | None


def image_bytes(value: object) -> bytes:
    if not isinstance(value, str) or not 0 < len(value) <= MAX_IMAGE_BASE64_BYTES:
        raise BridgeError("INVALID_MESSAGE")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise BridgeError("INVALID_MESSAGE") from None
    if not 0 < len(data) <= MAX_IMAGE_BYTES or base64.b64encode(data).decode("ascii") != value:
        raise BridgeError("INVALID_MESSAGE")
    return data


def validate_processing_parameters(data: dict) -> None:
    if (not isinstance(data, dict)
            or set(data) != {"image_base64", "width_px", "height_px", "remove_background"}):
        raise BridgeError("INVALID_MESSAGE")
    for key in ("width_px", "height_px"):
        if type(data[key]) is not int or not 1 <= data[key] <= 2048:
            raise BridgeError("INVALID_DIMENSIONS")
    if type(data["remove_background"]) is not bool:
        raise BridgeError("INVALID_MESSAGE")
    image_bytes(data["image_base64"])


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
    limit = MAX_PAYLOAD_BYTES if message.get("operation") == PROCESS_OPERATION else MAX_INSPECTION_BYTES
    if len(raw.encode("utf-8")) > limit:
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
    if message.get("operation") != PROCESS_OPERATION and len(raw.encode("utf-8")) > MAX_INSPECTION_BYTES:
        raise BridgeError("PAYLOAD_TOO_LARGE")
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

    if operation == PROCESS_OPERATION:
        require(set(data) == {"png_base64", "width_px", "height_px",
                              "background_removal_requested", "background_removal_completed"})
        image_bytes(data["png_base64"])
        for field in ("width_px", "height_px"):
            require(type(data[field]) is int and 1 <= data[field] <= 2048)
        # Phase 2A fails explicitly for removal instead of guessing an action descriptor.
        require(data["background_removal_requested"] is False)
        require(data["background_removal_completed"] is False)
        return
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
