"""Exactly two parameter-free MCP tools, both read-only."""
from typing import Annotated
import json

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .bridge import PhotoshopBridge
from .protocol import BridgeError, DocumentResult, PingResult, envelope


async def call_bridge(bridge: PhotoshopBridge, operation: str) -> CallToolResult:
    try:
        data, elapsed_ms = await bridge.request(operation)
        payload = envelope(data, elapsed_ms=elapsed_ms)
    except BridgeError as error:
        payload = envelope(error=error)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structured_content=payload,
        is_error=not payload["ok"],
    )


def register_tools(server: MCPServer, bridge: PhotoshopBridge) -> None:
    annotations = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                  idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=annotations)
    async def photoshop_ping() -> Annotated[CallToolResult, PingResult]:
        """Request a fresh reply from Photoshop; report versions and measured round-trip time."""
        return await call_bridge(bridge, "photoshop_ping")

    @server.tool(annotations=annotations)
    async def photoshop_get_active_document() -> Annotated[CallToolResult, DocumentResult]:
        """Read active-document metadata, ordered layer tree/counts and artboards; never edit or save."""
        return await call_bridge(bridge, "photoshop_get_active_document")
