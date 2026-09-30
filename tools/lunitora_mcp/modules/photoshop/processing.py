"""One bounded inbox PNG -> Photoshop temporary copy -> reviewed staging candidate."""
import asyncio
import base64
import hashlib

from core.config import ROOT
from .path_security import (locked_parent, locked_handle, read_source, relative_parts,
                            require_absent, publish_candidate)
from .png_validation import MAX_DIMENSION, MAX_IMAGE_BYTES, PNGError, read_png, verify_canvas
from .protocol import BridgeError, PROCESS_OPERATION, image_bytes

REPO_ROOT = ROOT.parents[1]


class ImageProcessor:
    def __init__(self, bridge):
        self.bridge = bridge
        self._busy = False

    async def process(self, source_relative_path: str, staging_relative_path: str,
                      width_px: int, height_px: int, remove_background: bool = False):
        for dimension in (width_px, height_px):
            if type(dimension) is not int or not 1 <= dimension <= MAX_DIMENSION:
                raise BridgeError("INVALID_DIMENSIONS")
        if type(remove_background) is not bool:
            raise BridgeError("INVALID_MESSAGE")
        source_parts = relative_parts(source_relative_path, "_inbox")
        output_parts = relative_parts(staging_relative_path, "_staging")
        if self._busy:
            raise BridgeError("BUSY")
        self._busy = True
        try:
            return await self._process(source_parts, output_parts, width_px, height_px, remove_background)
        except BridgeError:
            raise
        except OSError:
            raise BridgeError("STAGING_WRITE_FAILED") from None
        finally:
            self._busy = False

    async def _process(self, source_parts, output_parts, width, height, remove_background):
        # Parent handles stay pinned across awaits; no source path reaches Photoshop.
        with locked_parent(REPO_ROOT, source_parts) as source:
            with locked_handle(source, directory=False):
                data = read_source(source, MAX_IMAGE_BYTES)
                try:
                    original = read_png(data)
                except PNGError:
                    raise BridgeError("INVALID_IMAGE") from None
                if width < original.width or height < original.height:
                    raise BridgeError("CANVAS_TOO_SMALL")
                with locked_parent(REPO_ROOT, output_parts, create=True) as destination:
                    require_absent(destination)
                    if remove_background:
                        raise BridgeError("BACKGROUND_REMOVAL_UNAVAILABLE")
                    reply, elapsed = await self.bridge.request(PROCESS_OPERATION, {
                        "image_base64": base64.b64encode(data).decode("ascii"),
                        "width_px": width, "height_px": height, "remove_background": False,
                    })
                    try:
                        output = image_bytes(reply["png_base64"])
                        candidate = read_png(output)
                        verify_canvas(original, candidate, width, height)
                        if (reply["width_px"], reply["height_px"]) != (width, height):
                            raise PNGError("Mismatched peer dimensions.")
                        if read_source(source, MAX_IMAGE_BYTES) != data:
                            raise PNGError("Source changed during processing.")
                    except (PNGError, KeyError, TypeError):
                        raise BridgeError("OUTPUT_VALIDATION_FAILED", connected=True) from None
                    # No awaited work after this cancellation checkpoint and publication.
                    await asyncio.sleep(0)
                    require_absent(destination)
                    publish_candidate(destination, output)
                    return {
                        "source_relative_path": "/".join(source_parts),
                        "staging_relative_path": "/".join(output_parts),
                        "width_px": width, "height_px": height,
                        "background_removal_requested": False,
                        "background_removal_completed": False,
                        "validation": {
                            "format": "PNG", "bit_depth": 8, "color_type": "RGBA",
                            "has_transparency": candidate.has_transparency,
                            "dimensions_verified": True, "source_alpha_preserved": True,
                            "padding_verified": True, "source_unchanged": True,
                            "bytes_written": len(output),
                            "sha256": hashlib.sha256(output).hexdigest(),
                            "human_approval_required": True,
                        },
                    }, elapsed
