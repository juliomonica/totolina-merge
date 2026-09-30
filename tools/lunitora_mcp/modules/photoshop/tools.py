"""Two compatible read-only tools and one explicit staging-candidate operation."""
from typing import Annotated
import json

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import StrictBool, StrictInt

from .bridge import PhotoshopBridge
from .protocol import BridgeError, DocumentResult, PingResult, ProcessingResult, envelope
from .processing import ImageProcessor


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

    processor = ImageProcessor(bridge)

    @server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                            idempotent_hint=False, open_world_hint=False))
    async def photoshop_process_image(
        source_relative_path: str, staging_relative_path: str,
        width_px: StrictInt, height_px: StrictInt, remove_background: StrictBool = False,
    ) -> Annotated[CallToolResult, ProcessingResult]:
        """Create one transparent PNG candidate for human review, never a production asset.

        Select repository-relative source_art/_inbox/*.png and a new
        source_art/_staging/*.png destination. Phase 2A accepts non-interlaced RGBA8
        PNGs up to 24 MiB and canvases 1..2048 px. Preserve scale/padding: canvas
        must be at least the source size. Background removal is currently unavailable.
        """
        try:
            data, elapsed = await processor.process(
                source_relative_path, staging_relative_path, width_px, height_px, remove_background)
            payload = envelope(data, elapsed_ms=elapsed)
        except BridgeError as error:
            payload = envelope(error=error)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
            structured_content=payload, is_error=not payload["ok"],
        )
