"""Failure evidence remains bounded and does not relax existing acceptance rules."""
import json
import unittest
from unittest.mock import patch
import zlib

from mcp import Client
from mcp.server import MCPServer

from modules.photoshop.png_validation import PNGError, read_png, verify_canvas
from modules.photoshop.protocol import BridgeError, envelope, validate_result, PROCESS_OPERATION
from modules.photoshop.validation_diagnostics import canvas_diagnostics
from modules.photoshop import processing
from modules.photoshop.tools import register_tools
from tests import test_phase2 as fixtures

png, padded, result = fixtures.png, fixtures.padded, fixtures.result


class DiagnosticTests(unittest.TestCase):
    def test_rgb_edge_alpha_is_distinguished_from_opaque_padding(self):
        source = read_png(png(4, 8, color_type=2))
        alpha = [0, 240, 255, 0, 0, 255, 255, 0, 0, 255, 255, 0, 0, 255, 240, 0]
        output = read_png(png(4, 4, alpha=alpha))
        with self.assertRaisesRegex(PNGError, "Missing native resampled alpha checksum"):
            verify_canvas(source, output, 4, 4, "fit")
        report = canvas_diagnostics(source, output, 4, 4, "fit", "bicubic", None)
        self.assertTrue(report["alpha_validation_failed"])
        self.assertFalse(report["padding_validation_failed"])
        self.assertEqual(report["alpha_validation"], "photoshop_bicubic_crc32")
        self.assertIsNone(report["artwork_alpha_mismatch_count"])
        self.assertIsNone(report["expected_artwork_alpha_crc32"])
        self.assertEqual(report["artwork_partial_alpha_pixel_count"], 2)
        self.assertEqual(report["artwork_partial_alpha_edge_pixel_count"], 2)
        self.assertIsNone(report["first_artwork_alpha_mismatch"])
        self.assertEqual(report["expected_artwork"], report["actual_nontransparent_bounds"])
        self.assertEqual(report["actual_nontransparent_bounds"],
                         {"width_px": 2, "height_px": 4, "offset_x_px": 1, "offset_y_px": 0})

    def test_opaque_canvas_does_not_misreport_artwork_alpha_failure(self):
        source, output = read_png(png(4, 8, color_type=2)), read_png(png(4, 4, alpha=[255] * 16))
        report = canvas_diagnostics(source, output, 4, 4, "fit", "bicubic", zlib.crc32(bytes([255] * 8)))
        self.assertFalse(report["alpha_validation_failed"])
        self.assertTrue(report["padding_validation_failed"])
        self.assertFalse(report["has_transparency"])
        self.assertEqual(report["padding_nonzero_alpha_pixel_count"], 8)

    def test_native_checksum_and_padding_failures_are_reported_independently(self):
        output = read_png(png(4, 4, alpha=[0, 64, 128, 0] * 4))
        checksum = zlib.crc32(bytes([64, 128] * 4))
        for color_type in (2, 6):
            source = read_png(png(4, 8, color_type=color_type))
            for supplied, failed in ((checksum, False), (checksum ^ 1, True), (None, True)):
                report = canvas_diagnostics(source, output, 4, 4, "fit", "bicubic", supplied)
                self.assertEqual(report["alpha_validation_failed"], failed)
                self.assertEqual(report["expected_artwork_alpha_crc32"], supplied)
                self.assertEqual(report["actual_artwork_alpha_crc32"], checksum)
                self.assertFalse(report["padding_validation_failed"])

    def test_wrong_dimensions_rgb_and_unavailable_checks_are_explicit(self):
        source, output = read_png(png()), read_png(png(5, 3, color_type=2))
        report = canvas_diagnostics(source, output, 4, 4, "preserve_size", "bicubic", None)
        self.assertTrue(report["dimensions_validation_failed"])
        self.assertEqual(report["actual_output"], {"width_px": 5, "height_px": 3})
        self.assertFalse(report["output_is_rgba"])
        self.assertIsNone(report["alpha_validation_failed"])
        self.assertIsNone(report["source_unchanged_validation_failed"])
        report = canvas_diagnostics(source, None, 4, 4, "fit", "bicubic", None)
        self.assertIsNone(report["actual_output"])
        self.assertIsNone(report["padding_validation_failed"])

    def test_transparent_borders_are_not_reported_as_artwork_dimensions(self):
        report = canvas_diagnostics(read_png(png()), read_png(padded()), 4, 4, "fit", "bicubic", None)
        self.assertFalse(report["alpha_validation_failed"])
        empty = read_png(png(alpha=[0] * 4))
        report = canvas_diagnostics(empty, empty, 2, 2, "fit", "bicubic", None)
        self.assertIsNone(report["actual_nontransparent_bounds"])
        self.assertIsNone(report["actual_opaque_bounds"])

    def test_retired_native_diagnostics_and_other_extra_fields_are_rejected(self):
        for change in ({"native_diagnostics": {}}, {"token": "private"}):
            with self.assertRaises(BridgeError):
                validate_result(PROCESS_OPERATION, {**result(), **change})


class ProcessingDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    # Reuse the locked native-Windows temporary repository fixture, not its test methods.
    setUp = fixtures.ProcessingTests.setUp
    run_image = fixtures.ProcessingTests.run_image

    async def test_mcp_rgb_partial_alpha_success_requires_native_checksum(self):
        original = png(4, 8, color_type=2)
        self.source.write_bytes(original)
        alpha = [0, 240, 255, 0] * 4
        output = png(4, 4, alpha=alpha)
        checksum = zlib.crc32(bytes([240, 255] * 4))
        server = MCPServer("rgb-bicubic-test")
        register_tools(server, self.bridge)
        async with Client(server) as client:
            for index, proof in enumerate(({}, {"resampled_alpha_crc32": checksum ^ 1},
                                           {"resampled_alpha_crc32": checksum})):
                self.bridge.request.return_value = ({**result(output), **proof}, 1)
                destination = f"source_art/_staging/bicubic-{index}.png"
                reply = await client.call_tool(PROCESS_OPERATION, {
                    "source_relative_path": self.source_name, "staging_relative_path": destination,
                    "width_px": 4, "height_px": 4, "mode": "fit"})
                self.assertEqual(reply.is_error, index < 2)
                self.assertEqual((self.repo / destination).exists(), index == 2)
                if index == 2:
                    validation = reply.structured_content["result"]["validation"]
                    self.assertEqual(validation["alpha_validation"], "photoshop_bicubic_crc32")
                    self.assertTrue(validation["dimensions_verified"])
                    self.assertTrue(validation["padding_verified"])
                    self.assertTrue(validation["source_unchanged"])
                    self.assertEqual((self.repo / destination).read_bytes(), output)
                self.assertEqual(self.source.read_bytes(), original)

    async def test_safe_failure_envelope_preserves_all_independent_checks(self):
        self.source.write_bytes(png(4, 8, color_type=2))
        alpha = [0, 240, 255, 0] * 4
        checksum = zlib.crc32(bytes([240, 255] * 4))
        self.bridge.request.return_value = ({**result(png(4, 4, alpha=alpha)), "resampled_alpha_crc32": checksum ^ 1}, 1)
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(mode="fit")
        payload = envelope(error=caught.exception)
        report = payload["error"]["diagnostics"]
        self.assertEqual(report["failed_condition"], "NATIVE_ALPHA_CHECKSUM_MISMATCH")
        self.assertTrue(report["alpha_validation_failed"])
        self.assertFalse(report["padding_validation_failed"])
        self.assertFalse(report["source_unchanged_validation_failed"])
        self.assertEqual(report["expected_artwork_alpha_crc32"], checksum ^ 1)
        self.assertEqual(report["actual_artwork_alpha_crc32"], checksum)
        self.assertFalse(self.output.exists())
        self.assertIsNone(payload["result"])
        for forbidden in ("base64", "image_base64", "raw_pixels", "token", "private"):
            self.assertNotIn(forbidden, json.dumps(payload))

    async def test_all_checks_reported_even_when_alpha_fails_first(self):
        self.bridge.request.return_value = (result(png(4, 4, alpha=[255] * 16)), 1)
        with self.assertRaises(BridgeError) as caught:
            await self.run_image()
        report = caught.exception.diagnostics
        self.assertTrue(report["alpha_validation_failed"])
        self.assertTrue(report["padding_validation_failed"])
        self.assertFalse(report["source_unchanged_validation_failed"])

    async def test_changed_source_is_reported_without_logging_contents(self):
        with patch.object(processing, "read_source", side_effect=[png(), b"private changed bytes", b"private changed bytes"]):
            with self.assertRaises(BridgeError) as caught:
                await self.run_image()
        self.assertEqual(caught.exception.diagnostics["failed_condition"], "SOURCE_CHANGED")
        self.assertTrue(caught.exception.diagnostics["source_unchanged_validation_failed"])
        self.assertNotIn("private", json.dumps(envelope(error=caught.exception)))
        self.assertFalse(self.output.exists())

    async def test_unknown_exception_text_is_never_reported(self):
        with patch.object(processing, "verify_canvas", side_effect=PNGError("private image/token data")):
            with self.assertRaises(BridgeError) as caught:
                await self.run_image()
        self.assertEqual(caught.exception.diagnostics["failed_condition"], "PNG_DECODE_OR_REPLY_INVALID")
        self.assertNotIn("private", json.dumps(envelope(error=caught.exception)))

    async def test_mcp_serializes_failure_diagnostics_without_image_payload(self):
        self.bridge.request.return_value = (result(png(4, 4, alpha=[255] * 16)), 1)
        server = MCPServer("diagnostic-test")
        register_tools(server, self.bridge)
        async with Client(server) as client:
            reply = await client.call_tool(PROCESS_OPERATION, {
                "source_relative_path": self.source_name, "staging_relative_path": self.output_name,
                "width_px": 4, "height_px": 4})
        self.assertTrue(reply.is_error)
        report = reply.structured_content["error"]["diagnostics"]
        self.assertEqual(report["failed_condition"], "VERTICAL_PADDING_NOT_TRANSPARENT")
        self.assertTrue(report["padding_validation_failed"])
        self.assertFalse(self.output.exists())
        self.assertNotIn("base64", json.dumps(reply.structured_content))
