"""Three metadata reads and two fixed lab writes; exact empty public inputs."""
from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .bridge import GodotBridge
from .protocol import (BridgeError, EditorStateResult, MAX_PAYLOAD_BYTES, OPERATIONS, PingResult,
                       RigLabResult, RigLabAnimationResult, SceneInspectionResult, WRITE_OPERATION,
                       ANIMATION_WRITE_OPERATION, WRITE_OPERATIONS, encode, envelope, validate_result)

EMPTY_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False, "maxProperties": 0}
# The text block and structured content both contain the metadata for MCP client
# compatibility. Bound their fully encoded combined body, including JSON string
# escaping, and leave room for Codex's outer JSON-RPC response and line delimiter.
MCP_ENVELOPE_RESERVE_BYTES = 1024
MAX_TOOL_RESULT_BYTES = MAX_PAYLOAD_BYTES - MCP_ENVELOPE_RESERVE_BYTES


def tool_result(payload: dict) -> CallToolResult:
    def construct(value):
        return CallToolResult(content=[TextContent(type="text", text=encode(value))],
                              structured_content=value, is_error=not value["ok"])

    try:
        result = construct(payload)
        # Use the SDK model's JSON serializer and aliases, as stdio does. Measuring
        # the WebSocket payload alone misses duplicated data and escaped quotes.
        if len(result.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")) <= MAX_TOOL_RESULT_BYTES:
            return result
    except BridgeError as error:
        if error.code != "RESPONSE_TOO_LARGE":
            raise
    # Return only the fixed failure contract; never retain a partial scene or peer
    # text. This fallback is small even when the source metadata filled its frame.
    return construct(envelope(error=BridgeError("RESPONSE_TOO_LARGE", connected=payload["connected"])))


def failure(code: str) -> CallToolResult:
    return tool_result(envelope(error=BridgeError(code)))


class GodotMCPServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        # Public direct calls must follow the same contract as stdio requests.
        if type(name) is not str or name not in OPERATIONS:
            return failure("UNSUPPORTED_OPERATION")
        if type(arguments) is not dict or arguments != {}:
            return failure("INVALID_REQUEST")
        return await super().call_tool(name, arguments, context)

    async def list_tools(self):
        listing = await super().list_tools()
        for tool in listing:
            tool.input_schema = dict(EMPTY_SCHEMA)
            # The TypedDict contracts forbid unknown fields recursively. Add the
            # success/failure relationship explicitly to the published schema.
            tool.output_schema = dict(tool.output_schema)
            tool.output_schema["allOf"] = [{
                "if": {"properties": {"ok": {"const": True}}},
                "then": {"properties": {"connected": {"const": True}, "error": {"type": "null"},
                                        "result": {"type": "object"}, "round_trip_ms": {"type": "number"}}},
                "else": {"properties": {"result": {"type": "null"}, "error": {"type": "object"}}},
            }]
        return listing


async def exact_empty_arguments(ctx, call_next):
    # SDK 2.2 accepts/coerces null or extra zero-argument fields by default.
    # Inspect the raw request before that behavior can discard caller input.
    if ctx.method == "tools/call":
        params = ctx.params
        if type(params) is not dict or type(params.get("name")) is not str or params["name"] not in OPERATIONS:
            return failure("UNSUPPORTED_OPERATION")
        if type(params.get("arguments")) is not dict or params["arguments"] != {}:
            return failure("INVALID_REQUEST")
    return await call_next(ctx)


async def call_bridge(bridge: GodotBridge, operation: str) -> CallToolResult:
    dispatched = False
    try:
        data, elapsed_ms = await bridge.request(operation, {})
        dispatched = True
        if operation in WRITE_OPERATIONS:
            validate_result(operation, data)
        result = tool_result(envelope(data, elapsed_ms=elapsed_ms))
        if operation in WRITE_OPERATIONS and not result.structured_content["ok"]:
            bridge.retain_unknown_write()
            return tool_result(envelope(error=BridgeError("WRITE_OUTCOME_UNKNOWN", connected=True)))
        return result
    except BridgeError as error:
        if dispatched and operation in WRITE_OPERATIONS:
            bridge.retain_unknown_write()
            error = BridgeError("WRITE_OUTCOME_UNKNOWN", connected=True)
        return tool_result(envelope(error=error))
    except Exception:
        if operation not in WRITE_OPERATIONS:
            raise
        if dispatched:
            bridge.retain_unknown_write()
        # Never claim failed/no mutation after a successful dispatch whose MCP
        # serialization or validation failed. Do not echo arbitrary exceptions.
        return tool_result(envelope(error=BridgeError("WRITE_OUTCOME_UNKNOWN", connected=True)))


def register_tools(server: GodotMCPServer, bridge: GodotBridge) -> None:
    server.middleware.append(exact_empty_arguments)
    annotations = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                  idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=annotations)
    async def godot_ping() -> Annotated[CallToolResult, PingResult]:
        """Read a fresh authenticated editor reply, versions and project identity."""
        return await call_bridge(bridge, "godot_ping")

    @server.tool(annotations=annotations)
    async def godot_get_editor_state() -> Annotated[CallToolResult, EditorStateResult]:
        """Read current scene/save state and selected-node metadata without changing the editor."""
        return await call_bridge(bridge, "godot_get_editor_state")

    @server.tool(annotations=annotations)
    async def godot_inspect_scene() -> Annotated[CallToolResult, SceneInspectionResult]:
        """Read bounded current-scene node metadata and animation names; no tracks, images or script data."""
        return await call_bridge(bridge, "godot_inspect_scene")

    write_annotations = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                        idempotent_hint=False, open_world_hint=False)

    @server.tool(annotations=write_annotations)
    async def godot_create_rig_lab() -> Annotated[CallToolResult, RigLabResult]:
        """Create exactly seven fixed lab scaffold nodes in one undo action, only in the approved open lab. Never saves, plays, replaces or edits production scenes. Unknown outcomes require a fresh read and review; never retry automatically."""
        return await call_bridge(bridge, WRITE_OPERATION)

    @server.tool(annotations=write_annotations)
    async def godot_create_rig_lab_animation() -> Annotated[CallToolResult, RigLabAnimationResult]:
        """Add the fixed bend_tip animation in one undo action to the exact existing lab rig with a detached, settled animation editor. Never creates a rig, saves, selects, plays or writes production scenes. Unknown outcomes require a fresh read and review; never retry automatically."""
        return await call_bridge(bridge, ANIMATION_WRITE_OPERATION)
