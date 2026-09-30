"""One bounded inbox PNG -> Photoshop temporary copy -> reviewed staging candidate."""
import asyncio
import base64
import hashlib

from core.config import ROOT
from .path_security import (locked_parent, locked_handle, read_source, relative_parts,
                            require_absent, publish_candidate)
from .png_validation import (MAX_DIMENSION, MAX_IMAGE_BYTES, PNGError, read_png, verify_canvas,
                             fitted_size, rgba_png, verify_removal_canvas)
from .protocol import BridgeError, PROCESS_OPERATION, image_bytes
from .validation_diagnostics import CONDITIONS, canvas_diagnostics

REPO_ROOT = ROOT.parents[1]


class ImageProcessor:
    def __init__(self, bridge):
        self.bridge = bridge
        self._busy = False

    async def process(self, source_relative_path: str, staging_relative_path: str,
                      width_px: int, height_px: int, remove_background: bool = False,
                      mode: str = "preserve_size", resample: str = "bicubic"):
        for dimension in (width_px, height_px):
            if type(dimension) is not int or not 1 <= dimension <= MAX_DIMENSION:
                raise BridgeError("INVALID_DIMENSIONS")
        if type(remove_background) is not bool:
            raise BridgeError("INVALID_MESSAGE")
        if type(mode) is not str or mode not in ("preserve_size", "fit"):
            raise BridgeError("INVALID_MODE")
        if type(resample) is not str or resample not in ("bicubic", "nearest"):
            raise BridgeError("INVALID_RESAMPLE")
        source_parts = relative_parts(source_relative_path, "_inbox")
        output_parts = relative_parts(staging_relative_path, "_staging")
        if self._busy:
            raise BridgeError("BUSY")
        self._busy = True
        try:
            return await self._process(source_parts, output_parts, width_px, height_px, remove_background, mode, resample)
        except BridgeError:
            raise
        except OSError:
            raise BridgeError("STAGING_WRITE_FAILED") from None
        finally:
            self._busy = False

    async def _process(self, source_parts, output_parts, width, height, remove_background, mode, resample):
        # Parent handles stay pinned across awaits; no source path reaches Photoshop.
        with locked_parent(REPO_ROOT, source_parts) as source:
            with locked_handle(source, directory=False):
                data = read_source(source, MAX_IMAGE_BYTES)
                try:
                    original = read_png(data)
                except PNGError:
                    raise BridgeError("INVALID_IMAGE") from None
                if mode == "preserve_size" and (width < original.width or height < original.height):
                    raise BridgeError("CANVAS_TOO_SMALL")
                artwork_width, artwork_height = fitted_size(original.width, original.height, width, height, mode)
                with locked_parent(REPO_ROOT, output_parts, create=True) as destination:
                    require_absent(destination)
                    parameters = {
                        "image_base64": base64.b64encode(data).decode("ascii"),
                        "width_px": width, "height_px": height, "remove_background": remove_background,
                    }
                    # Omission retains the exact Phase 2A request for older plugins.
                    if mode != "preserve_size":
                        parameters["mode"] = mode
                        # Explicit even for the default: older nearest-only plugins must fail closed.
                        parameters["resample"] = resample
                    reply, elapsed = await self.bridge.request(PROCESS_OPERATION, parameters)
                    candidate = None
                    exported_color_type = None
                    try:
                        output = image_bytes(reply["png_base64"])
                        candidate = read_png(output)
                        exported_color_type = candidate.color_type
                        if candidate.color_type == 2 and not remove_background:
                            output = rgba_png(output)
                            candidate = read_png(output)
                        if (reply.get("background_removal_requested") is not remove_background
                                or reply.get("background_removal_completed") is not remove_background
                                or (not remove_background and "removal_evidence" in reply)):
                            raise PNGError("BACKGROUND_REMOVAL_EVIDENCE_MISMATCH")
                        if remove_background:
                            alpha_validation = verify_removal_canvas(original, candidate, width, height, mode,
                                resample, reply.get("removal_evidence"), reply.get("resampled_alpha_crc32"))
                        else:
                            alpha_validation = verify_canvas(original, candidate, width, height, mode, resample,
                                                             reply.get("resampled_alpha_crc32"))
                        if (reply["width_px"], reply["height_px"]) != (width, height):
                            raise PNGError("Mismatched peer dimensions.")
                        if read_source(source, MAX_IMAGE_BYTES) != data:
                            raise PNGError("Source changed during processing.")
                    except (PNGError, KeyError, TypeError) as error:
                        diagnostics = canvas_diagnostics(original, candidate, width, height, mode, resample,
                                                         reply.get("resampled_alpha_crc32"), removal=remove_background)
                        diagnostics["failed_condition"] = CONDITIONS.get(str(error), "PNG_DECODE_OR_REPLY_INVALID")
                        diagnostics["exported_color_type"] = {2: "RGB", 6: "RGBA"}.get(exported_color_type)
                        # Check independently even if alpha/padding failed first. Keep path locks held.
                        try:
                            diagnostics["source_unchanged_validation_failed"] = read_source(source, MAX_IMAGE_BYTES) != data
                        except (BridgeError, OSError):
                            pass  # Unavailable is null, never a false success.
                        raise BridgeError("OUTPUT_VALIDATION_FAILED", connected=True,
                                          diagnostics=diagnostics) from None
                    # No awaited work after this cancellation checkpoint and publication.
                    await asyncio.sleep(0)
                    require_absent(destination)
                    publish_candidate(destination, output)
                    return {
                        "source_relative_path": "/".join(source_parts),
                        "staging_relative_path": "/".join(output_parts),
                        "width_px": width, "height_px": height,
                        "mode": mode, "resample": resample,
                        "source_color_type": "RGB" if original.color_type == 2 else "RGBA",
                        "artwork_width_px": artwork_width, "artwork_height_px": artwork_height,
                        "offset_x_px": (width - artwork_width) // 2,
                        "offset_y_px": (height - artwork_height) // 2,
                        "background_removal_requested": remove_background,
                        "background_removal_completed": remove_background,
                        "validation": {
                            "format": "PNG", "bit_depth": 8, "color_type": "RGBA",
                            "has_transparency": candidate.has_transparency,
                            "dimensions_verified": True, "source_alpha_preserved": not remove_background,
                            "alpha_validation": alpha_validation,
                            "padding_verified": True, "source_unchanged": True,
                            "bytes_written": len(output),
                            "sha256": hashlib.sha256(output).hexdigest(),
                            "human_approval_required": True,
                        },
                    }, elapsed
