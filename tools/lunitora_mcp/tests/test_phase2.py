"""Phase 2A safety/PNG tests plus the real MCP and authenticated loopback transport."""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import zlib

from mcp import Client
from websockets.asyncio.client import connect

from core.config import Config, ENDPOINT, ROOT
from core.server import create_server
from modules.photoshop import path_security, processing
from modules.photoshop.path_security import locked_parent, relative_parts
from modules.photoshop.png_validation import (MAX_IMAGE_BYTES, PNG, PNGError, read_png, verify_canvas,
                                             fitted_size, rgba_png)
from modules.photoshop.processing import ImageProcessor
from modules.photoshop.protocol import (BridgeError, MAX_IMAGE_BASE64_BYTES, MAX_INSPECTION_BYTES,
                                       MAX_PAYLOAD_BYTES, PROCESS_OPERATION, decode, encode,
                                       image_bytes, validate_processing_parameters, validate_result)
from tests.fake_photoshop_client import FakePhotoshopClient


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(width=2, height=2, *, alpha=None, filter_type=0, color_type=6):
    channels = 3 if color_type == 2 else 4
    pixels = [bytes((40, 80, 120, alpha[i] if alpha is not None else [0, 128, 255, 255][i % 4]))[:channels]
              for i in range(width * height)]
    previous = bytes(width * channels)
    rows = []
    for y in range(height):
        row = b"".join(pixels[y * width:(y + 1) * width])
        encoded = bytearray()
        for x, value in enumerate(row):
            a, b, c = row[x - channels] if x >= channels else 0, previous[x], previous[x - channels] if x >= channels else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            paeth = a if pa <= pb and pa <= pc else b if pb <= pc else c
            prediction = [0, a, b, (a + b) // 2, paeth][filter_type]
            encoded.append((value - prediction) & 255)
        rows.append(bytes([filter_type]) + encoded)
        previous = row
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def padded(width=4, height=4):
    alpha = [0] * (width * height)
    dx, dy = (width - 2) // 2, (height - 2) // 2
    for y in range(2):
        alpha[(dy + y) * width + dx:(dy + y) * width + dx + 2] = [0, 128, 255, 255][y * 2:y * 2 + 2]
    return png(width, height, alpha=alpha)


def result(data=None, width=4, height=4):
    return {"png_base64": base64.b64encode(data or padded(width, height)).decode("ascii"),
            "width_px": width, "height_px": height,
            "background_removal_requested": False, "background_removal_completed": False}


def sized_png(size, data=None):
    """Generate a valid PNG with a large ancillary chunk; no committed binary fixture."""
    data = png() if data is None else data
    text = b"size\0" + b"x" * (size - len(data) - 12 - 5)
    return data[:-12] + chunk(b"tEXt", text) + data[-12:]


class PNGTests(unittest.TestCase):
    def test_all_five_png_filters_decode_identically(self):
        expected = read_png(png()).pixels
        for method in range(5):
            self.assertEqual(read_png(png(filter_type=method)).pixels, expected)

    def test_bad_crc_truncation_extra_data_and_pixel_bomb_rejected(self):
        data = png()
        bomb = (data[:33] + chunk(b"IDAT", zlib.compress(b"\0" * 1000000)) + chunk(b"IEND", b""))
        for candidate in (data[:-1], data + b"junk", data[:45] + b"X" + data[46:], bomb):
            with self.subTest(length=len(candidate)), self.assertRaises(PNGError):
                read_png(candidate)

    def test_apng_interlaced_indexed_and_oversized_input_rejected(self):
        for data in (png()[:33] + chunk(b"acTL", b"\0" * 8) + png()[33:],
                     b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 1)),
                     b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 3, 0, 0, 0)),
                     png() + b"x" * MAX_IMAGE_BYTES):
            with self.assertRaises(PNGError):
                read_png(data)

    def test_alpha_and_padding_preserved_in_odd_canvas(self):
        verify_canvas(read_png(png()), read_png(padded(3, 5)), 3, 5)

    def test_rgb_all_filters_decode_to_opaque_rgba_pixels(self):
        expected = bytes((40, 80, 120, 255)) * 15
        for method in range(5):
            image = read_png(png(3, 5, color_type=2, filter_type=method))
            self.assertEqual(image.color_type, 2)
            self.assertEqual(image.pixels, expected)
            self.assertFalse(image.has_transparency)

    def test_rgb_conversion_preserves_pixels_profiles_and_text(self):
        metadata = chunk(b"iCCP", b"test\0\0" + zlib.compress(b"profile fixture")) + chunk(b"tEXt", b"note\0keep")
        original = png(3, 5, color_type=2)
        original = original[:33] + metadata + chunk(b"sBIT", b"\x06\x07\x08") + original[33:]
        converted = rgba_png(original)
        self.assertEqual(read_png(converted).color_type, 6)
        self.assertEqual(read_png(converted).pixels, read_png(original).pixels)
        self.assertIn(metadata, converted)
        self.assertIn(chunk(b"sBIT", b"\x06\x07\x08\x08"), converted)
        self.assertEqual(rgba_png(converted), converted)
        for invalid in (b"\0\x08\x08", b"\x09\x08\x08", b"\x08" * 4):
            rgb = png(color_type=2)
            with self.assertRaises(PNGError):
                rgba_png(rgb[:33] + chunk(b"sBIT", invalid) + rgb[33:])

    def test_rgb_transparent_color_key_and_unsupported_depth_rejected(self):
        rgb = png(color_type=2)
        cases = [rgb[:33] + chunk(b"tRNS", b"\0" * 6) + rgb[33:]]
        for depth, color in ((16, 2), (16, 6), (8, 0), (8, 3), (8, 4)):
            cases.append(rgb[:8] + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, depth, color, 0, 0, 0)) + rgb[33:])
        for candidate in cases:
            with self.assertRaises(PNGError):
                read_png(candidate)

    def test_fit_portrait_and_landscape_dimensions(self):
        self.assertEqual(fitted_size(4, 8, 4, 4, "fit"), (2, 4))
        self.assertEqual(fitted_size(8, 4, 4, 4, "fit"), (4, 2))
        self.assertEqual(fitted_size(941, 1672, 512, 512, "fit"), (288, 512))

    def test_fit_same_size_smaller_source_and_one_pixel_dimension(self):
        for mode in ("preserve_size", "fit"):
            self.assertEqual(fitted_size(4, 4, 4, 4, mode), (4, 4))
            self.assertEqual(fitted_size(2, 3, 9, 9, mode), (2, 3))
        self.assertEqual(fitted_size(1, 2048, 1, 1, "fit"), (1, 1))
        self.assertEqual(fitted_size(7, 3, 4, 4, "fit"), (4, 2))

    def test_fit_preserves_hand_calculated_partial_alpha_and_odd_padding(self):
        source = read_png(png(4, 8, alpha=list(range(32))))
        # 4x8 -> 2x4: sample columns 1,3 and rows 1,3,5,7.
        alpha = [0, 5, 7, 0, 0, 0, 13, 15, 0, 0,
                 0, 21, 23, 0, 0, 0, 29, 31, 0, 0]
        verify_canvas(source, read_png(png(5, 4, alpha=alpha)), 5, 4, "fit", "nearest")
        for position in (0, 1, 19):
            wrong = alpha.copy()
            wrong[position] += 1
            with self.assertRaises(PNGError):
                verify_canvas(source, read_png(png(5, 4, alpha=wrong)), 5, 4, "fit", "nearest")

    def test_fit_rejects_stretched_or_shifted_alpha(self):
        source = read_png(png(8, 4, alpha=list(range(32))))
        good = [0] * 4 + [9, 11, 13, 15, 25, 27, 29, 31] + [0] * 4
        verify_canvas(source, read_png(png(4, 4, alpha=good)), 4, 4, "fit", "nearest")
        for alpha in ([9, 11, 13, 15] * 4, good[4:] + [0] * 4):
            with self.assertRaises(PNGError):
                verify_canvas(source, read_png(png(4, 4, alpha=alpha)), 4, 4, "fit", "nearest")

    def test_bicubic_alpha_uses_native_checksum_and_still_checks_padding(self):
        source = read_png(png(4, 8, alpha=list(range(32))))
        # Simulated native response, deliberately unlike nearest samples.
        artwork = [3, 6, 11, 14, 19, 22, 27, 30]
        alpha = [0, 3, 6, 0, 0, 0, 11, 14, 0, 0,
                 0, 19, 22, 0, 0, 0, 27, 30, 0, 0]
        checksum = zlib.crc32(bytes(artwork))
        output = read_png(png(5, 4, alpha=alpha))
        self.assertEqual(verify_canvas(source, output, 5, 4, "fit", "bicubic", checksum),
                         "photoshop_bicubic_crc32")
        for bad in (None, True, -1, 2**32, "123", checksum ^ 1):
            with self.subTest(checksum=bad), self.assertRaises(PNGError):
                verify_canvas(source, output, 5, 4, "fit", "bicubic", bad)
        for position in (0, 1, 19):
            wrong = alpha.copy()
            wrong[position] += 1
            with self.assertRaises(PNGError):
                verify_canvas(source, read_png(png(5, 4, alpha=wrong)), 5, 4, "fit", "bicubic", checksum)
        with self.assertRaises(PNGError):
            verify_canvas(source, output, 5, 4, "fit", "nearest", checksum)

    def test_bicubic_no_resize_still_requires_exact_source_alpha(self):
        for mode in ("preserve_size", "fit"):
            self.assertEqual(verify_canvas(read_png(png()), read_png(padded()), 4, 4, mode), "source_exact")
            with self.assertRaises(PNGError):
                verify_canvas(read_png(png()), read_png(png(4, 4)), 4, 4, mode, "bicubic", 0)

    def test_rgb_unscaled_and_nearest_still_require_exact_opacity(self):
        for sw, sh, mode, resample, expected in (
                (2, 4, "preserve_size", "bicubic", "source_exact"),
                (2, 4, "preserve_size", "nearest", "source_exact"),
                (2, 4, "fit", "bicubic", "source_exact"),
                (4, 8, "fit", "nearest", "nearest_exact")):
            with self.subTest(mode=mode, resample=resample):
                source = read_png(png(sw, sh, color_type=2))
                alpha = [0, 255, 255, 0] * 4
                self.assertEqual(verify_canvas(source, read_png(png(4, 4, alpha=alpha)),
                                              4, 4, mode, resample), expected)
                alpha[1] = 220
                checksum = zlib.crc32(bytes([220] + [255] * 7))
                with self.assertRaisesRegex(PNGError, "Source transparency changed"):
                    verify_canvas(source, read_png(png(4, 4, alpha=alpha)),
                                  4, 4, mode, resample, checksum)

    def test_resample_wire_validation_accepts_legacy_and_rejects_invalid_values(self):
        request = {"image_base64": base64.b64encode(png()).decode("ascii"),
                   "width_px": 4, "height_px": 4, "remove_background": False}
        for extra in ({}, {"mode": "fit"}, {"mode": "preserve_size"}):
            validate_processing_parameters({**request, **extra})
            for resample in ("bicubic", "nearest"):
                validate_processing_parameters({**request, **extra, "resample": resample})
        for resample in (None, True, 1, "", "BICUBIC", "bilinear", [], {}):
            with self.assertRaises(BridgeError) as caught:
                validate_processing_parameters({**request, "resample": resample})
            self.assertEqual(caught.exception.code, "INVALID_RESAMPLE")
        with self.assertRaises(BridgeError):
            validate_processing_parameters({**request, "resample": "bicubic", "script": "forbidden"})

    def test_native_alpha_checksum_response_is_optional_and_bounded(self):
        validate_result(PROCESS_OPERATION, result())
        for checksum in (0, 2**32 - 1):
            validate_result(PROCESS_OPERATION, {**result(), "resampled_alpha_crc32": checksum})
        for checksum in (None, True, -1, 2**32, "123", [], {}):
            with self.assertRaises(BridgeError):
                validate_result(PROCESS_OPERATION, {**result(), "resampled_alpha_crc32": checksum})

    def test_exact_opaque_rgb_still_requires_rgba_output(self):
        source = read_png(png(color_type=2))
        with self.assertRaises(PNGError):
            verify_canvas(source, source, 2, 2)
        output = read_png(rgba_png(png(color_type=2)))
        verify_canvas(source, output, 2, 2)
        self.assertFalse(output.has_transparency)

    def test_rgba_conversion_cannot_bypass_encoded_limit(self):
        original = sized_png(500, png(color_type=2))
        self.assertGreater(len(rgba_png(original)), len(original))
        with patch("modules.photoshop.png_validation.MAX_IMAGE_BYTES", len(original)):
            with self.assertRaises(PNGError):
                rgba_png(original)

    def test_processing_modes_preserve_legacy_wire_and_reject_invalid_values(self):
        request = {"image_base64": base64.b64encode(png()).decode("ascii"),
                   "width_px": 4, "height_px": 4, "remove_background": False}
        validate_processing_parameters(request)
        for mode in ("preserve_size", "fit"):
            validate_processing_parameters({**request, "mode": mode})
        for mode in ("", "FIT", "crop", None, False, 1, [], {}):
            with self.assertRaises(BridgeError) as caught:
                validate_processing_parameters({**request, "mode": mode})
            self.assertEqual(caught.exception.code, "INVALID_MODE")

    def test_alpha_loss_opaque_padding_and_wrong_dimensions_rejected(self):
        for data in (png(4, 4, alpha=[255] * 16), png(4, 4), padded(5, 5)):
            with self.assertRaises(PNGError):
                verify_canvas(read_png(png()), read_png(data), 4, 4)

    def test_base64_and_processing_response_are_bounded(self):
        validate_result("photoshop_process_image", result())
        for data in ("", "bad!", "A" * (MAX_IMAGE_BASE64_BYTES + 4), "Zh==", "Zm9="):
            with self.assertRaises(BridgeError):
                image_bytes(data)
        for change in ({"background_removal_completed": True}, {"width_px": True}, {"extra": "field"}):
            with self.assertRaises(BridgeError):
                validate_result("photoshop_process_image", {**result(), **change})

    def test_png_byte_boundaries(self):
        self.assertEqual(MAX_IMAGE_BYTES, 25_165_824)
        for size in (MAX_IMAGE_BYTES - 1, MAX_IMAGE_BYTES, MAX_IMAGE_BYTES + 1):
            with self.subTest(size=size):
                data = sized_png(size)
                self.assertEqual(len(data), size)
                if size <= MAX_IMAGE_BYTES:
                    self.assertEqual(read_png(data), read_png(png()))
                else:
                    with self.assertRaises(PNGError):
                        read_png(data)

    def test_base64_request_and_response_byte_boundaries(self):
        for size in (MAX_IMAGE_BYTES - 1, MAX_IMAGE_BYTES, MAX_IMAGE_BYTES + 1):
            with self.subTest(size=size):
                data = b"x" * size
                response = result(data)
                value = response["png_base64"]
                request = {"image_base64": value, "width_px": 4, "height_px": 4, "remove_background": False}
                if size <= MAX_IMAGE_BYTES:
                    self.assertEqual(image_bytes(value), data)
                    validate_processing_parameters(request)
                    validate_result(PROCESS_OPERATION, response)
                else:
                    for check in (lambda: image_bytes(value), lambda: validate_processing_parameters(request),
                                  lambda: validate_result(PROCESS_OPERATION, response)):
                        with self.assertRaises(BridgeError) as caught:
                            check()
                        self.assertEqual(caught.exception.code, "INVALID_MESSAGE")

    def test_protocol_utf8_byte_boundaries_and_legacy_inspection_bound(self):
        for operation, limit in ((PROCESS_OPERATION, MAX_PAYLOAD_BYTES), ("photoshop_ping", MAX_INSPECTION_BYTES)):
            message = {"protocol_version": 1, "operation": operation, "padding": "猫🐱"}
            overhead = len(encode(message).encode("utf-8"))
            for size in (limit - 1, limit, limit + 1):
                with self.subTest(operation=operation, size=size):
                    message["padding"] = "猫🐱" + "x" * (size - overhead)
                    raw = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
                    self.assertEqual(len(raw.encode("utf-8")), size)
                    if size <= limit:
                        self.assertEqual(encode(message), raw)
                        self.assertEqual(decode(raw), message)
                    else:
                        for check in (lambda: encode(message), lambda: decode(raw)):
                            with self.assertRaises(BridgeError) as caught:
                                check()
                            self.assertEqual(caught.exception.code, "PAYLOAD_TOO_LARGE")

    def test_maximum_image_fits_request_and_response_with_escaped_id(self):
        self.assertEqual(MAX_IMAGE_BASE64_BYTES, 33_554_432)
        self.assertEqual(MAX_PAYLOAD_BYTES, 33_555_456)
        # Each control character takes six JSON bytes; IDs permit up to 64 characters.
        common = {"protocol_version": 1, "id": "\0" * 64, "operation": PROCESS_OPERATION}
        image = base64.b64encode(b"x" * MAX_IMAGE_BYTES).decode("ascii")
        request = {**common, "type": "request", "parameters": {
            "image_base64": image, "width_px": 2048, "height_px": 2048, "remove_background": False,
            "mode": "preserve_size", "resample": "bicubic"}}
        response = {**common, "type": "response", "ok": True, "error": None, "result": {
            "png_base64": image, "width_px": 2048, "height_px": 2048,
            "background_removal_requested": False, "background_removal_completed": False,
            "resampled_alpha_crc32": 2**32 - 1}}
        for message in (request, response):
            size = len(encode(message).encode("utf-8"))
            self.assertLessEqual(size - len(image), 1024)
            self.assertEqual(decode(encode(message)), message)


class RGBBicubicRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Synthetic native alpha with the live portrait's geometry, extrema and
        # 1,196 partial edge pixels; no claim to reproduce Photoshop's kernel.
        cls.source = PNG(941, 1672, bytes((40, 80, 120, 255)) * (941 * 1672), 2)
        artwork = bytes([220]) * 216 + (bytes([220]) + bytes([255]) * 214 + bytes([220])) * 382 + bytes([220]) * 216
        cls.checksum = zlib.crc32(artwork)
        pixels = bytearray(bytes((40, 80, 120, 0)) * (384 * 384))
        for y in range(384):
            start = (y * 384 + 84) * 4 + 3
            pixels[start:start + 216 * 4:4] = artwork[y * 216:(y + 1) * 216]
        cls.output = PNG(384, 384, bytes(pixels))

    def test_live_portrait_partial_edges_pass_with_native_checksum(self):
        self.assertEqual(fitted_size(941, 1672, 384, 384, "fit"), (216, 384))
        self.assertEqual(sum(0 < a < 255 for a in self.output.pixels[3::4]), 1196)
        self.assertEqual(verify_canvas(self.source, self.output, 384, 384, "fit",
                                      resampled_alpha_crc32=self.checksum), "photoshop_bicubic_crc32")

    def test_changed_exported_edge_alpha_fails_native_checksum(self):
        pixels = bytearray(self.output.pixels)
        pixels[84 * 4 + 3] = 221
        with self.assertRaisesRegex(PNGError, "Native resampled transparency changed"):
            verify_canvas(self.source, PNG(384, 384, bytes(pixels)), 384, 384,
                          "fit", "bicubic", self.checksum)

    def test_missing_invalid_or_mismatched_native_checksum_fails(self):
        for checksum in (None, True, -1, 2**32, "123", self.checksum ^ 1):
            with self.subTest(checksum=checksum), self.assertRaises(PNGError):
                verify_canvas(self.source, self.output, 384, 384, "fit", "bicubic", checksum)

    def test_nonzero_alpha_outside_expected_rectangle_fails_even_with_matching_checksum(self):
        for x, y in ((83, 0), (300, 383)):
            pixels = bytearray(self.output.pixels)
            pixels[(y * 384 + x) * 4 + 3] = 1
            with self.subTest(x=x, y=y), self.assertRaisesRegex(PNGError, "Opaque horizontal padding"):
                verify_canvas(self.source, PNG(384, 384, bytes(pixels)), 384, 384,
                              "fit", "bicubic", self.checksum)

    def test_wrong_dimensions_and_shifted_artwork_fail(self):
        with self.assertRaisesRegex(PNGError, "Wrong output dimensions"):
            verify_canvas(self.source, self.output, 385, 384, "fit", "bicubic", self.checksum)
        shifted = b"".join(b"\0" * 4 + self.output.pixels[y * 384 * 4:((y + 1) * 384 - 1) * 4]
                           for y in range(384))
        with self.assertRaisesRegex(PNGError, "Opaque horizontal padding"):
            verify_canvas(self.source, PNG(384, 384, shifted), 384, 384, "fit", "bicubic", self.checksum)


class ProcessingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        (ROOT / ".local").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="phase2-", dir=ROOT / ".local")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        (self.repo / "source_art/_inbox").mkdir(parents=True)
        (self.repo / "source_art/_staging").mkdir()
        self.source_name = "source_art/_inbox/source.png"
        self.output_name = "source_art/_staging/candidate.png"
        self.source = self.repo / self.source_name
        self.output = self.repo / self.output_name
        self.source.write_bytes(png())
        self.root_patch = patch.object(processing, "REPO_ROOT", self.repo)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.bridge = AsyncMock()
        self.bridge.request.return_value = (result(), 12.5)
        self.processor = ImageProcessor(self.bridge)

    async def run_image(self, **kwargs):
        return await self.processor.process(
            kwargs.get("source", self.source_name), kwargs.get("output", self.output_name),
            kwargs.get("width", 4), kwargs.get("height", 4), kwargs.get("remove_background", False),
            kwargs.get("mode", "preserve_size"), kwargs.get("resample", "bicubic"))

    async def assert_error(self, code, **kwargs):
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(**kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.source.read_bytes(), png())
        self.assertEqual(list(self.output.parent.glob(".lunitora-*")), [])

    async def test_valid_inbox_to_staging_and_structured_success(self):
        reply, elapsed = await self.run_image()
        self.assertEqual(self.output.read_bytes(), padded())
        self.assertEqual(self.source.read_bytes(), png())
        self.assertEqual(reply["source_relative_path"], self.source_name)
        self.assertEqual(reply["staging_relative_path"], self.output_name)
        self.assertEqual((reply["width_px"], reply["height_px"]), (4, 4))
        self.assertEqual(elapsed, 12.5)
        self.assertFalse(reply["background_removal_requested"])
        self.assertFalse(reply["background_removal_completed"])
        self.assertTrue(reply["validation"]["human_approval_required"])
        self.assertTrue(reply["validation"]["source_alpha_preserved"])
        self.assertEqual(reply["validation"]["sha256"], hashlib.sha256(padded()).hexdigest())
        operation, parameters = self.bridge.request.call_args.args
        self.assertEqual(operation, "photoshop_process_image")
        self.assertEqual(set(parameters), {"image_base64", "width_px", "height_px", "remove_background"})
        self.assertEqual(image_bytes(parameters["image_base64"]), png())

    async def test_nested_staging_directories_created_safely(self):
        await self.run_image(output="source_art/_staging/new/nested/candidate.png")
        self.assertEqual((self.repo / "source_art/_staging/new/nested/candidate.png").read_bytes(), padded())

    async def test_rgb_input_produces_rgba_with_transparent_padding(self):
        self.source.write_bytes(png(color_type=2))
        original = self.source.read_bytes()
        alpha = [0, 0, 0, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 0, 0, 0]
        self.bridge.request.return_value = (result(png(4, 4, alpha=alpha)), 1)
        data, _ = await self.run_image()
        self.assertEqual(data["source_color_type"], "RGB")
        self.assertEqual(data["mode"], "preserve_size")
        self.assertTrue(data["validation"]["has_transparency"])
        self.assertEqual(read_png(self.output.read_bytes()).color_type, 6)
        self.assertEqual(self.source.read_bytes(), original)

    async def test_exact_rgb_export_is_encoded_rgba_without_erasing_pixels(self):
        original = png(color_type=2)
        self.source.write_bytes(original)
        self.bridge.request.return_value = (result(original, 2, 2), 1)
        data, _ = await self.run_image(width=2, height=2, mode="fit")
        candidate = read_png(self.output.read_bytes())
        self.assertEqual(candidate.color_type, 6)
        self.assertEqual(candidate.pixels, read_png(original).pixels)
        self.assertFalse(data["validation"]["has_transparency"])
        self.assertEqual((data["artwork_width_px"], data["artwork_height_px"]), (2, 2))
        self.assertEqual((data["offset_x_px"], data["offset_y_px"]), (0, 0))
        self.assertEqual(self.source.read_bytes(), original)

    async def test_rgba_portrait_fit_preserves_sampled_alpha_and_source(self):
        original = png(4, 8, alpha=list(range(32)))
        self.source.write_bytes(original)
        alpha = [0, 5, 7, 0, 0, 0, 13, 15, 0, 0,
                 0, 21, 23, 0, 0, 0, 29, 31, 0, 0]
        self.bridge.request.return_value = (result(png(5, 4, alpha=alpha), 5, 4), 1)
        data, _ = await self.run_image(width=5, height=4, mode="fit", resample="nearest")
        self.assertEqual((data["artwork_width_px"], data["artwork_height_px"]), (2, 4))
        self.assertEqual((data["offset_x_px"], data["offset_y_px"]), (1, 0))
        self.assertEqual(data["source_color_type"], "RGBA")
        self.assertTrue(data["validation"]["source_alpha_preserved"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.bridge.request.call_args.args[1]["mode"], "fit")
        self.assertEqual(self.bridge.request.call_args.args[1]["resample"], "nearest")
        self.assertEqual(data["resample"], "nearest")
        self.assertEqual(data["validation"]["alpha_validation"], "nearest_exact")

    async def test_default_and_explicit_bicubic_preserve_native_alpha_through_publication(self):
        artwork = [6, 8, 10, 12, 22, 24, 26, 28]
        output = png(4, 4, alpha=[0] * 4 + artwork + [0] * 4)
        self.bridge.request.return_value = ({**result(output), "resampled_alpha_crc32": zlib.crc32(bytes(artwork))}, 1)
        for color_type in (2, 6):
            original = png(8, 4, alpha=list(range(32)), color_type=color_type)
            self.source.write_bytes(original)
            for index, extra in enumerate(({}, {"resample": "bicubic"})):
                data, _ = await self.run_image(mode="fit", output=f"source_art/_staging/bicubic-{color_type}-{index}.png", **extra)
                self.assertEqual(self.bridge.request.call_args.args[1]["resample"], "bicubic")
                self.assertEqual(data["resample"], "bicubic")
                self.assertEqual(data["validation"]["alpha_validation"], "photoshop_bicubic_crc32")
                self.assertTrue(data["validation"]["source_alpha_preserved"])
                self.assertEqual((self.repo / data["staging_relative_path"]).read_bytes(), output)
                self.assertEqual(self.source.read_bytes(), original)

    async def test_bicubic_missing_checksum_or_matted_export_cannot_publish(self):
        for color_type in (2, 6):
            self.source.write_bytes(png(8, 4, color_type=color_type))
            for output, proof in ((png(4, 4), {}),
                                  (png(4, 4, alpha=[0] * 4 + [255] * 8 + [0] * 4),
                                   {"resampled_alpha_crc32": zlib.crc32(bytes([0, 128, 255, 255] * 2))})):
                self.bridge.request.return_value = ({**result(output), **proof}, 1)
                with self.assertRaises(BridgeError) as caught:
                    await self.run_image(mode="fit")
                self.assertEqual(caught.exception.code, "OUTPUT_VALIDATION_FAILED")
                self.assertFalse(self.output.exists())

    async def test_invalid_resample_never_contacts_host_or_publishes(self):
        for resample in (None, True, 1, "", "BICUBIC", "bilinear", [], {}):
            await self.assert_error("INVALID_RESAMPLE", mode="fit", resample=resample)
        self.bridge.request.assert_not_called()

    async def test_preserve_size_resample_choices_keep_legacy_wire(self):
        for index, resample in enumerate(("bicubic", "nearest")):
            data, _ = await self.run_image(resample=resample, output=f"source_art/_staging/legacy-{index}.png")
            self.assertEqual(set(self.bridge.request.call_args.args[1]),
                             {"image_base64", "width_px", "height_px", "remove_background"})
            self.assertEqual(data["validation"]["alpha_validation"], "source_exact")

    async def test_fit_smaller_rgba_keeps_existing_padding_without_upscale(self):
        self.bridge.request.return_value = (result(padded(3, 5), 3, 5), 1)
        data, _ = await self.run_image(width=3, height=5, mode="fit")
        self.assertEqual((data["artwork_width_px"], data["artwork_height_px"]), (2, 2))
        self.assertEqual((data["offset_x_px"], data["offset_y_px"]), (0, 1))
        self.assertEqual(self.output.read_bytes(), padded(3, 5))

    async def test_fit_exact_rgba_does_not_resample_alpha(self):
        self.bridge.request.return_value = (result(png(), 2, 2), 1)
        data, _ = await self.run_image(width=2, height=2, mode="fit")
        self.assertEqual(self.output.read_bytes(), png())
        self.assertEqual((data["artwork_width_px"], data["artwork_height_px"]), (2, 2))

    async def test_fit_cannot_publish_opaque_padding_or_lost_alpha(self):
        for color_type in (2, 6):
            original = png(8, 4, color_type=color_type)
            self.source.write_bytes(original)
            self.bridge.request.return_value = (result(png(4, 4, color_type=2)), 1)
            with self.assertRaises(BridgeError) as caught:
                await self.run_image(mode="fit")
            self.assertEqual(caught.exception.code, "OUTPUT_VALIDATION_FAILED")
            self.assertFalse(self.output.exists())
            self.assertEqual(self.source.read_bytes(), original)

    async def test_invalid_modes_never_contact_host_or_publish(self):
        for mode in (None, True, 1, "", "FIT", "crop", [], {}):
            await self.assert_error("INVALID_MODE", mode=mode)
        self.bridge.request.assert_not_called()

    async def test_fit_keeps_path_and_no_overwrite_preflight(self):
        await self.assert_error("INVALID_PATH", mode="fit", output="assets/fit.png")
        await self.assert_error("INVALID_PATH", mode="fit", source="source_art/_inbox/../source.png")
        self.output.write_bytes(b"existing owner")
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(mode="fit")
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"existing owner")
        self.bridge.request.assert_not_called()

    async def test_fit_propagates_background_removal_unavailable(self):
        self.bridge.request.side_effect = BridgeError("BACKGROUND_REMOVAL_UNAVAILABLE", connected=True)
        await self.assert_error("BACKGROUND_REMOVAL_UNAVAILABLE", mode="fit", remove_background=True)
        self.bridge.request.assert_awaited_once()

    async def test_mcp_mode_schema_and_invalid_mode_validation(self):
        token = secrets.token_urlsafe(48)
        async with Client(create_server(Config(), token)) as client:
            listing = await client.list_tools()
            tool = next(tool for tool in listing.tools if tool.name == PROCESS_OPERATION)
            self.assertEqual(tool.input_schema["properties"]["mode"]["enum"], ["preserve_size", "fit"])
            self.assertEqual(tool.input_schema["properties"]["mode"]["default"], "preserve_size")
            self.assertNotIn("mode", tool.input_schema["required"])
            self.assertEqual(tool.input_schema["properties"]["resample"]["enum"], ["bicubic", "nearest"])
            self.assertEqual(tool.input_schema["properties"]["resample"]["default"], "bicubic")
            self.assertNotIn("resample", tool.input_schema["required"])
            async with FakePhotoshopClient(token) as peer:
                for mode in ("crop", None, True, 1, []):
                    reply = await client.call_tool(PROCESS_OPERATION, {
                        "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                        "width_px": 4, "height_px": 4, "mode": mode})
                    self.assertTrue(reply.is_error)
                for resample in (None, True, 1, "", "BICUBIC", "bilinear", [], {}):
                    reply = await client.call_tool(PROCESS_OPERATION, {
                        "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                        "width_px": 4, "height_px": 4, "mode": "fit", "resample": resample})
                    self.assertTrue(reply.is_error)
                self.assertEqual(peer.requests, [])
                self.assertFalse(self.output.exists())

    async def test_real_mcp_rgb_landscape_fit_and_additive_result(self):
        original = png(8, 4, color_type=2)
        self.source.write_bytes(original)
        output = png(4, 4, alpha=[0] * 4 + [255] * 8 + [0] * 4)
        token = secrets.token_urlsafe(48)
        def respond(response):
            response["result"] = {**result(output), "resampled_alpha_crc32": zlib.crc32(bytes([255] * 8))}
        async with Client(create_server(Config(), token)) as client:
            async with FakePhotoshopClient(token, mutate=respond) as peer:
                reply = await client.call_tool(PROCESS_OPERATION, {
                    "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                    "width_px": 4, "height_px": 4, "mode": "fit"})
                self.assertFalse(reply.is_error, reply.structured_content)
                data = reply.structured_content["result"]
                self.assertEqual((data["artwork_width_px"], data["artwork_height_px"]), (4, 2))
                self.assertEqual((data["offset_x_px"], data["offset_y_px"]), (0, 1))
                self.assertEqual(data["mode"], "fit")
                self.assertEqual(data["source_color_type"], "RGB")
                self.assertTrue(data["validation"]["human_approval_required"])
                self.assertEqual(peer.requests[0]["parameters"]["mode"], "fit")
                self.assertEqual(self.output.read_bytes(), output)
                self.assertEqual(self.source.read_bytes(), original)

    async def test_mcp_resample_default_and_explicit_choices_round_trip(self):
        self.source.write_bytes(png(8, 4, color_type=2))
        output = png(4, 4, alpha=[0] * 4 + [255] * 8 + [0] * 4)
        token = secrets.token_urlsafe(48)
        def respond(response):
            response["result"] = {**result(output), "resampled_alpha_crc32": zlib.crc32(bytes([255] * 8))}
        async with Client(create_server(Config(), token)) as client:
            async with FakePhotoshopClient(token, mutate=respond) as peer:
                for index, extra in enumerate(({}, {"resample": "bicubic"}, {"resample": "nearest"})):
                    reply = await client.call_tool(PROCESS_OPERATION, {
                        "source_relative_path": self.source_name,
                        "staging_relative_path": f"source_art/_staging/mcp-{index}.png",
                        "width_px": 4, "height_px": 4, "mode": "fit", **extra})
                    self.assertFalse(reply.is_error, reply.structured_content)
                    expected = extra.get("resample", "bicubic")
                    self.assertEqual(reply.structured_content["result"]["resample"], expected)
                    self.assertEqual(peer.requests[-1]["parameters"]["resample"], expected)

    async def test_traversal_and_windows_path_tricks_rejected(self):
        for path in ("source_art/_inbox/../outside.png", "source_art/_inbox/./source.png",
                     "source_art/_inbox//source.png", r"source_art\_inbox\source.png",
                     "source_art/_inbox/%2e%2e/source.png", "source_art/_inbox/source.png:stream",
                     "source_art/_inbox/NUL.png", "source_art/_inbox/foo./source.png"):
            with self.subTest(path=path):
                await self.assert_error("INVALID_PATH", source=path)
        self.bridge.request.assert_not_called()

    async def test_absolute_drive_unc_and_device_paths_rejected(self):
        for path in ("/tmp/source.png", r"C:\temp\source.png", "C:/temp/source.png",
                     r"\\server\share\source.png", r"\\?\C:\temp\source.png", "C:source.png"):
            with self.subTest(path=path):
                await self.assert_error("INVALID_PATH", source=path)
                await self.assert_error("INVALID_PATH", output=path)

    async def test_production_and_cross_area_paths_rejected(self):
        for path in ("assets/candidate.png", "source_art/characters/candidate.png", self.output_name):
            await self.assert_error("INVALID_PATH", source=path)
        for path in ("assets/candidate.png", self.source_name, "source_art/_staging/../../assets/test.png"):
            await self.assert_error("INVALID_PATH", output=path)

    async def test_destination_exists_fails_without_contacting_photoshop(self):
        self.output.write_bytes(b"keep me")
        with self.assertRaises(BridgeError) as caught:
            await self.run_image()
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"keep me")
        self.bridge.request.assert_not_called()

    async def test_destination_created_during_processing_is_not_overwritten(self):
        async def raced(*args):
            self.output.write_bytes(b"other owner")
            return result(), 1
        self.bridge.request.side_effect = raced
        with self.assertRaises(BridgeError) as caught:
            await self.run_image()
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"other owner")

    async def test_create_new_prevents_race_after_final_existence_check(self):
        publish = processing.publish_candidate
        def raced(path, data):
            path.write_bytes(b"race winner")
            publish(path, data)
        with patch.object(processing, "publish_candidate", side_effect=raced):
            with self.assertRaises(BridgeError) as caught:
                await self.run_image()
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"race winner")

    async def test_source_cannot_be_written_or_deleted_while_photoshop_runs(self):
        async def attempt_mutation(*args):
            with self.assertRaises(OSError):
                self.source.write_bytes(b"changed")
            with self.assertRaises(OSError):
                self.source.unlink()
            return result(), 1
        self.bridge.request.side_effect = attempt_mutation
        await self.run_image()
        self.assertEqual(self.source.read_bytes(), png())

    async def test_concurrent_processing_returns_busy_and_releases_after_success(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def hold(*args):
            started.set()
            await release.wait()
            return result(), 1
        self.bridge.request.side_effect = hold
        first = asyncio.create_task(self.run_image())
        try:
            await started.wait()
            await self.assert_error("BUSY")
        finally:
            release.set()
            await first
        self.assertFalse(self.processor._busy)

    async def test_file_stream_initialization_failure_removes_exclusive_candidate(self):
        with patch.object(path_security.os, "fdopen", side_effect=OSError("private detail")):
            await self.assert_error("STAGING_WRITE_FAILED")

    async def test_invalid_canvas_dimensions(self):
        for dimension in (0, -1, 2049, True, 2.5, "4", None):
            await self.assert_error("INVALID_DIMENSIONS", width=dimension)
            await self.assert_error("INVALID_DIMENSIONS", height=dimension)

    async def test_smaller_canvas_never_crops_or_scales(self):
        await self.assert_error("CANVAS_TOO_SMALL", width=1)
        self.bridge.request.assert_not_called()

    async def test_disconnected_failure_leaves_no_output(self):
        self.bridge.request.side_effect = BridgeError("DISCONNECTED")
        await self.assert_error("DISCONNECTED")

    async def test_photoshop_failure_leaves_no_output(self):
        self.bridge.request.side_effect = BridgeError("PHOTOSHOP_PROCESSING_FAILED", connected=True)
        await self.assert_error("PHOTOSHOP_PROCESSING_FAILED")

    async def test_timeout_leaves_no_output(self):
        self.bridge.request.side_effect = BridgeError("TIMEOUT")
        await self.assert_error("TIMEOUT")

    async def test_cancellation_leaves_no_output_and_releases_busy(self):
        self.bridge.request.side_effect = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.run_image()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.processor._busy)

    async def test_background_removal_fails_explicitly_without_side_effects(self):
        self.bridge.request.side_effect = BridgeError("BACKGROUND_REMOVAL_UNAVAILABLE", connected=True)
        await self.assert_error("BACKGROUND_REMOVAL_UNAVAILABLE", remove_background=True)
        self.bridge.request.assert_awaited_once()

    async def test_invalid_export_never_published(self):
        self.bridge.request.return_value = (result(png(4, 4, alpha=[255] * 16)), 1)
        await self.assert_error("OUTPUT_VALIDATION_FAILED")

    async def test_source_missing_and_invalid_png_fail_before_bridge(self):
        missing = "source_art/_inbox/missing.png"
        await self.assert_error("SOURCE_NOT_FOUND", source=missing)
        self.source.write_bytes(b"not a PNG")
        with self.assertRaises(BridgeError) as caught:
            await self.run_image()
        self.assertEqual(caught.exception.code, "INVALID_IMAGE")
        self.bridge.request.assert_not_called()

    async def test_source_hardlink_to_other_tree_is_rejected(self):
        other = self.repo / "production.png"
        os.link(self.source, other)
        await self.assert_error("PATH_UNSAFE")
        self.bridge.request.assert_not_called()

    async def test_junction_escape_is_rejected_for_both_roots(self):
        outside = self.repo / "outside"
        outside.mkdir()
        (outside / "source.png").write_bytes(png())
        for area in ("_inbox", "_staging"):
            link = self.repo / "source_art" / area / "escape"
            subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                kwargs = {"source": "source_art/_inbox/escape/source.png"} if area == "_inbox" else {
                    "output": "source_art/_staging/escape/candidate.png"}
                await self.assert_error("PATH_UNSAFE", **kwargs)
                self.assertFalse((outside / "candidate.png").exists())
            finally:
                os.rmdir(link)  # remove this known junction only, never recurse into target

    async def test_locked_parent_cannot_be_renamed_during_processing(self):
        with locked_parent(self.repo, relative_parts(self.output_name, "_staging")):
            with self.assertRaises(OSError):
                self.output.parent.rename(self.repo / "moved")

    async def test_publish_failure_cleans_temporary_candidate(self):
        with patch.object(path_security.os, "fsync", side_effect=OSError("private detail")):
            await self.assert_error("STAGING_WRITE_FAILED")

    async def test_real_mcp_authenticated_bridge_structured_success(self):
        token = secrets.token_urlsafe(48)
        def respond(response):
            if response["operation"] == "photoshop_process_image":
                response["result"] = result()
        async with Client(create_server(Config(), token)) as client:
            async with FakePhotoshopClient(token, mutate=respond) as peer:
                reply = await client.call_tool("photoshop_process_image", {
                    "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                    "width_px": 4, "height_px": 4})
                self.assertFalse(reply.is_error)
                self.assertTrue(reply.structured_content["connected"])
                self.assertEqual(reply.structured_content["result"]["staging_relative_path"], self.output_name)
                self.assertEqual(peer.requests[0]["operation"], "photoshop_process_image")
                self.assertNotIn("source_relative_path", peer.requests[0]["parameters"])

    async def test_real_mcp_disconnected_and_failure_contracts(self):
        token = secrets.token_urlsafe(48)
        args = {"source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                "width_px": 4, "height_px": 4}
        async with Client(create_server(Config(), token)) as client:
            reply = await client.call_tool("photoshop_process_image", args)
            self.assertTrue(reply.is_error)
            self.assertEqual(reply.structured_content["error"]["code"], "DISCONNECTED")
            def reject(response):
                response.update(ok=False, result=None, error={
                    "code": "PHOTOSHOP_PROCESSING_FAILED", "message": "private exception text"})
            async with FakePhotoshopClient(token, mutate=reject):
                reply = await client.call_tool("photoshop_process_image", args)
                self.assertTrue(reply.is_error)
                self.assertTrue(reply.structured_content["connected"])
                self.assertEqual(reply.structured_content["error"]["code"], "PHOTOSHOP_PROCESSING_FAILED")
                self.assertNotIn("private", str(reply.structured_content))
        self.assertFalse(self.output.exists())

    async def test_real_mcp_file_boundaries_in_both_directions(self):
        token = secrets.token_urlsafe(48)
        for size in (MAX_IMAGE_BYTES - 1, MAX_IMAGE_BYTES):
            with self.subTest(size=size):
                source = sized_png(size)
                output = sized_png(size, padded())
                self.source.write_bytes(source)
                def respond(response):
                    response["result"] = result(output)
                async with Client(create_server(Config(), token)) as client:
                    async with FakePhotoshopClient(token, mutate=respond) as peer:
                        reply = await client.call_tool(PROCESS_OPERATION, {
                            "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                            "width_px": 4, "height_px": 4})
                        self.assertFalse(reply.is_error, reply.structured_content)
                        self.assertEqual(reply.structured_content["result"]["validation"]["bytes_written"], size)
                        self.assertEqual(image_bytes(peer.requests[0]["parameters"]["image_base64"]), source)
                        self.assertEqual(self.output.read_bytes(), output)
                        self.assertEqual(self.source.read_bytes(), source)
                self.output.unlink()

    async def test_oversized_source_does_not_contact_or_disconnect_authenticated_peer(self):
        self.source.write_bytes(sized_png(MAX_IMAGE_BYTES + 1))
        token = secrets.token_urlsafe(48)
        async with Client(create_server(Config(), token)) as client:
            async with FakePhotoshopClient(token) as peer:
                reply = await client.call_tool(PROCESS_OPERATION, {
                    "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                    "width_px": 4, "height_px": 4})
                payload = reply.structured_content
                self.assertTrue(reply.is_error)
                self.assertEqual(payload["error"]["code"], "IMAGE_TOO_LARGE")
                self.assertFalse(payload["connected"])  # No fresh reply for this operation; not global state.
                self.assertIsNone(payload["round_trip_ms"])
                self.assertEqual(peer.requests, [])
                self.assertFalse(self.output.exists())
                ping = await client.call_tool("photoshop_ping", {})
                self.assertTrue(ping.structured_content["connected"])
                self.assertTrue(ping.structured_content["ok"])

    async def test_oversized_output_never_published(self):
        self.bridge.request.return_value = (result(sized_png(MAX_IMAGE_BYTES + 1, padded())), 1)
        await self.assert_error("INVALID_MESSAGE")

    async def test_authenticated_websocket_message_boundaries(self):
        token = secrets.token_urlsafe(48)
        args = {"source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                "width_px": 4, "height_px": 4}
        async with Client(create_server(Config(), token)) as client:
            for size in (MAX_PAYLOAD_BYTES - 1, MAX_PAYLOAD_BYTES, MAX_PAYLOAD_BYTES + 1):
                with self.subTest(size=size):
                    async with connect(ENDPOINT, family=socket.AF_INET, proxy=None,
                                       max_size=MAX_PAYLOAD_BYTES, compression=None) as peer:
                        await peer.send(encode({"type": "auth", "protocol_version": 1, "token": token}))
                        self.assertTrue(decode(await peer.recv())["ok"])
                        task = asyncio.create_task(client.call_tool(PROCESS_OPERATION, args))
                        request = decode(await asyncio.wait_for(peer.recv(), 5))
                        raw = encode({"type": "response", "protocol_version": 1, "id": request["id"],
                                      "operation": PROCESS_OPERATION, "ok": True, "result": result(), "error": None})
                        raw += " " * (size - len(raw.encode("utf-8")))
                        await peer.send(raw)
                        reply = await asyncio.wait_for(task, 10)
                        if size <= MAX_PAYLOAD_BYTES:
                            self.assertFalse(reply.is_error, reply.structured_content)
                            self.assertEqual(self.output.read_bytes(), padded())
                            self.output.unlink()
                        else:
                            await asyncio.wait_for(peer.wait_closed(), 5)
                            self.assertEqual(peer.close_code, 1009)
                            self.assertTrue(reply.is_error)
                            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
