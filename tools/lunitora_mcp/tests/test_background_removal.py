"""v0.5 deterministic segmentation fixtures; no Photoshop AI or cloud calls."""
import asyncio
import base64
import json
import secrets
import socket
import unittest
from unittest.mock import patch
import zlib

from mcp import Client
from mcp.server import MCPServer
from websockets.asyncio.client import connect

from core.config import Config, ENDPOINT
from modules.photoshop import bridge as bridge_module, processing
from modules.photoshop.bridge import PhotoshopBridge
from modules.photoshop.png_validation import PNGError, read_png, removal_evidence
from modules.photoshop.protocol import (BridgeError, PROCESS_OPERATION, MAX_IMAGE_BASE64_BYTES,
                                       decode, encode, envelope, peer_failure, validate_result)
from modules.photoshop.tools import register_tools
from tests import test_phase2 as fixtures
from tests.fake_photoshop_client import FakePhotoshopClient

png = fixtures.png


def removal_reply(before, after, width=4, height=4, *, fitted_alpha=None, fitted_size=None):
    source = read_png(before)
    aw, ah = fitted_size or (source.width, source.height)
    artwork = after if fitted_alpha is None else fitted_alpha
    dx, dy = (width - aw) // 2, (height - ah) // 2
    alpha = [0] * (width * height)
    for y in range(ah):
        alpha[(y + dy) * width + dx:(y + dy) * width + dx + aw] = artwork[y * aw:(y + 1) * aw]
    return {"png_base64": base64.b64encode(png(width, height, alpha=alpha)).decode("ascii"),
            "width_px": width, "height_px": height,
            "background_removal_requested": True, "background_removal_completed": True,
            "removal_evidence": removal_evidence(source.pixels[3::4], bytes(after)),
            "resampled_alpha_crc32": zlib.crc32(bytes(artwork))}


class RemovalAlphaTests(unittest.TestCase):
    def test_rgb_threshold_below_at_above(self):
        before = bytes([255] * 2000)  # exactly two pixels required
        for removed in (1, 2, 3):
            after = bytes([0] * removed + [255] * (2000 - removed))
            with self.subTest(removed=removed):
                if removed < 2:
                    with self.assertRaisesRegex(PNGError, "BACKGROUND_REMOVAL_NO_OP"):
                        removal_evidence(before, after)
                else:
                    self.assertEqual(removal_evidence(before, after)["removed_pixels"], removed)

    def test_threshold_rounds_up_and_never_zero(self):
        for total, removed, success in ((2001, 2, False), (2001, 3, True), (2, 0, False), (2, 1, True)):
            before, after = bytes([255] * total), bytes([0] * removed + [255] * (total - removed))
            if success:
                removal_evidence(before, after)
            else:
                with self.assertRaisesRegex(PNGError, "BACKGROUND_REMOVAL_NO_OP"):
                    removal_evidence(before, after)

    def test_alpha_drop_and_final_alpha_boundaries(self):
        for initial, final, success in ((23, 8, False), (24, 8, True), (25, 9, False), (16, 0, True)):
            with self.subTest(initial=initial, final=final):
                if success:
                    removal_evidence(bytes([initial, 255]), bytes([final, 255]))
                else:
                    with self.assertRaisesRegex(PNGError, "BACKGROUND_REMOVAL_NO_OP"):
                        removal_evidence(bytes([initial, 255]), bytes([final, 255]))

    def test_rgba_existing_transparency_never_counts(self):
        before = bytes([0] * 1000 + [255] * 1000)
        with self.assertRaisesRegex(PNGError, "BACKGROUND_REMOVAL_NO_OP"):
            removal_evidence(before, before)
        after = before[:1000] + bytes([0]) + before[1001:]
        proof = removal_evidence(before, after)
        self.assertEqual((proof["visible_pixels"], proof["removed_pixels"]), (1000, 1))

    def test_empty_and_near_empty_subject_rejected(self):
        for foreground in (0, 1):
            with self.assertRaisesRegex(PNGError, "BACKGROUND_REMOVAL_EMPTY_SUBJECT"):
                removal_evidence(bytes([255] * 2000), bytes([255] * foreground + [0] * (2000 - foreground)))
        removal_evidence(bytes([255] * 2000), bytes([16, 16] + [0] * 1998))

    def test_increased_alpha_and_incomparable_bounds_rejected(self):
        for before, after in ((bytes([0, 255]), bytes([255, 0])), (bytes([255]), bytes([0, 255]))):
            with self.assertRaises(PNGError):
                removal_evidence(before, after)

    def test_safe_reason_enum_does_not_echo_peer_details(self):
        for reason in ("BACKGROUND_REMOVAL_NO_OP", "private path/token", {"secret": "private"}):
            report = envelope(error=peer_failure({"code": "OUTPUT_VALIDATION_FAILED", "reason": reason,
                                                  "message": "private", "diagnostics": {"secret": "private"}}))
            self.assertNotIn("private", json.dumps(report))
            self.assertEqual(report["error"]["diagnostics"]["failed_condition"],
                reason if reason == "BACKGROUND_REMOVAL_NO_OP" else "NATIVE_OUTPUT_VALIDATION_FAILED")

    def test_wire_rejects_unbounded_or_caller_controlled_evidence(self):
        reply = removal_reply(png(color_type=2), [0, 255, 255, 255])
        validate_result(PROCESS_OPERATION, reply)
        for proof in (None, {}, {**reply["removal_evidence"], "_target": []},
                      {**reply["removal_evidence"], "removed_pixels": True},
                      {**reply["removal_evidence"], "foreground_pixels": 2048**2 + 1}):
            with self.assertRaises(BridgeError):
                validate_result(PROCESS_OPERATION, {**reply, "removal_evidence": proof})

    def test_maximum_png_and_removal_metadata_fit_unchanged_wire_limit(self):
        reply = removal_reply(png(color_type=2), [0, 255, 255, 255])
        reply["png_base64"] = "A" * MAX_IMAGE_BASE64_BYTES
        reply["removal_evidence"] = {key: 4294967295 for key in reply["removal_evidence"]}
        raw = encode({"type": "response", "protocol_version": 1, "id": "\0" * 64,
                      "operation": PROCESS_OPERATION, "ok": True, "result": reply, "error": None})
        self.assertLessEqual(len(raw) - MAX_IMAGE_BASE64_BYTES, 1024)


class RemovalProcessingTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixtures.ProcessingTests.setUp
    run_image = fixtures.ProcessingTests.run_image

    def prepare(self, *, rgba=False):
        source = png(alpha=[0, 255, 255, 255]) if rgba else png(color_type=2)
        self.source.write_bytes(source)
        after = [0, 0, 255, 255] if rgba else [0, 255, 255, 255]
        reply = removal_reply(source, after)
        self.bridge.request.return_value = (reply, 1)
        return source, reply

    async def rejected(self, reply, reason=None, **kwargs):
        self.bridge.request.return_value = (reply, 1)
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(remove_background=True, **kwargs)
        self.assertEqual(caught.exception.code, "OUTPUT_VALIDATION_FAILED")
        if reason:
            self.assertEqual(caught.exception.diagnostics["failed_condition"], reason)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.processor._busy)

    async def test_rgb_preserve_size_success_and_source_unchanged(self):
        source, wire = self.prepare()
        reply, _ = await self.run_image(remove_background=True)
        self.assertTrue(reply["background_removal_completed"])
        self.assertTrue(reply["background_removal_requested"])
        self.assertFalse(reply["validation"]["source_alpha_preserved"])
        self.assertEqual(reply["validation"]["alpha_validation"], "background_removal_native_crc32")
        self.assertTrue(reply["validation"]["human_approval_required"])
        self.assertEqual(self.output.read_bytes(), base64.b64decode(wire["png_base64"]))
        self.assertEqual(self.source.read_bytes(), source)
        self.assertTrue(self.bridge.request.call_args.args[1]["remove_background"])

    async def test_rgba_additional_removal_succeeds(self):
        source, _ = self.prepare(rgba=True)
        reply, _ = await self.run_image(remove_background=True)
        self.assertTrue(reply["background_removal_completed"])
        self.assertEqual(self.source.read_bytes(), source)

    async def test_rgba_unchanged_alpha_with_fabricated_success_rejected(self):
        source, reply = self.prepare(rgba=True)
        alpha = [0] * 16
        alpha[5:7], alpha[9:11] = [0, 255], [255, 255]
        reply["png_base64"] = base64.b64encode(png(4, 4, alpha=alpha)).decode()
        reply["resampled_alpha_crc32"] = zlib.crc32(read_png(source).pixels[3::4])
        await self.rejected(reply, "BACKGROUND_REMOVAL_NO_OP")

    async def test_mismatched_evidence_never_publishes(self):
        _, good = self.prepare()
        for field in good["removal_evidence"]:
            reply = {**good, "removal_evidence": {**good["removal_evidence"], field: good["removal_evidence"][field] ^ 1}}
            await self.rejected(reply)

    async def test_empty_subject_rejected_despite_claimed_success(self):
        _, reply = self.prepare()
        reply["png_base64"] = base64.b64encode(png(4, 4, alpha=[0] * 16)).decode()
        reply["resampled_alpha_crc32"] = zlib.crc32(bytes(4))
        await self.rejected(reply, "BACKGROUND_REMOVAL_EMPTY_SUBJECT")

    async def test_padding_only_transparency_is_not_removal(self):
        _, reply = self.prepare()
        alpha = [0] * 16
        alpha[5:7] = alpha[9:11] = [255, 255]
        reply["png_base64"] = base64.b64encode(png(4, 4, alpha=alpha)).decode()
        reply["resampled_alpha_crc32"] = zlib.crc32(bytes([255] * 4))
        await self.rejected(reply, "BACKGROUND_REMOVAL_NO_OP")

    async def test_wrong_dimensions_rgb_export_and_opaque_padding_rejected(self):
        _, good = self.prepare()
        for image in (png(5, 4), png(4, 4, color_type=2), png(4, 4, alpha=[255] * 16)):
            await self.rejected({**good, "png_base64": base64.b64encode(image).decode()})

    async def test_fit_removal_bicubic_and_nearest_validate_native_artwork(self):
        source = png(4, 4, color_type=2)
        self.source.write_bytes(source)
        after, scaled = [0] * 8 + [255] * 8, [0, 0, 255, 255]
        for resample in ("bicubic", "nearest"):
            reply = removal_reply(source, after, 3, 2, fitted_alpha=scaled, fitted_size=(2, 2))
            self.bridge.request.return_value = (reply, 1)
            result, _ = await self.run_image(remove_background=True, mode="fit", resample=resample, width=3, height=2)
            self.assertEqual((result["artwork_width_px"], result["artwork_height_px"]), (2, 2))
            self.assertEqual(self.source.read_bytes(), source)
            self.assertEqual(self.bridge.request.call_args.args[1]["resample"], resample)
            self.output.unlink()
            await self.rejected({**reply, "resampled_alpha_crc32": reply["resampled_alpha_crc32"] ^ 1},
                                "NATIVE_ALPHA_CHECKSUM_MISMATCH", width=3, height=2, mode="fit", resample=resample)

    async def test_fit_rejects_lost_subject_or_opaque_artwork_even_with_padding(self):
        source = png(4, 4, color_type=2)
        self.source.write_bytes(source)
        for scaled, reason in (([0] * 4, "BACKGROUND_REMOVAL_EMPTY_SUBJECT"),
                               ([255] * 4, "BACKGROUND_REMOVAL_OUTPUT_OPAQUE")):
            reply = removal_reply(source, [0] * 8 + [255] * 8, 3, 2, fitted_alpha=scaled, fitted_size=(2, 2))
            await self.rejected(reply, reason, width=3, height=2, mode="fit")

    async def test_source_change_prevents_publication_after_valid_removal(self):
        source, reply = self.prepare()
        with patch.object(processing, "read_source", side_effect=[source, b"changed", b"changed"]):
            await self.rejected(reply, "SOURCE_CHANGED")

    async def test_false_request_rejects_unsolicited_removal(self):
        self.prepare()
        with self.assertRaises(BridgeError) as caught:
            await self.run_image()
        self.assertEqual(caught.exception.code, "OUTPUT_VALIDATION_FAILED")
        self.assertFalse(self.output.exists())

    async def test_destination_exists_does_not_invoke_photoshop(self):
        self.prepare()
        self.output.write_bytes(b"owner")
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(remove_background=True)
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"owner")
        self.bridge.request.assert_not_called()

    async def test_destination_created_during_removal_is_never_overwritten(self):
        source, reply = self.prepare()
        async def respond(*args):
            self.output.write_bytes(b"racing owner")
            return reply, 1
        self.bridge.request.side_effect = respond
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(remove_background=True)
        self.assertEqual(caught.exception.code, "DESTINATION_EXISTS")
        self.assertEqual(self.output.read_bytes(), b"racing owner")
        self.assertEqual(self.source.read_bytes(), source)

    async def test_real_authenticated_bridge_success_and_error_classifications(self):
        source, result = self.prepare()
        token = secrets.token_urlsafe(48)
        actual = PhotoshopBridge(Config(), token)
        await actual.start()
        self.addAsyncCleanup(actual.stop)
        self.assertIsNone(actual.startup_error)
        self.processor = processing.ImageProcessor(actual)
        for code in ("BACKGROUND_REMOVAL_UNAVAILABLE", "PHOTOSHOP_PROCESSING_FAILED", "PHOTOSHOP_CANCELLED",
                     "OUTPUT_VALIDATION_FAILED", None):
            def respond(response):
                if code:
                    response.update(ok=False, result=None, error={"code": code, "message": "private",
                                    "reason": "BACKGROUND_REMOVAL_NO_OP"})
                else:
                    response["result"] = result
            async with FakePhotoshopClient(token, mutate=respond):
                if code:
                    with self.assertRaises(BridgeError) as caught:
                        await self.run_image(remove_background=True)
                    self.assertEqual(caught.exception.code, code)
                    self.assertNotIn("private", str(envelope(error=caught.exception)))
                    if code == "OUTPUT_VALIDATION_FAILED":
                        self.assertEqual(caught.exception.diagnostics["failed_condition"], "BACKGROUND_REMOVAL_NO_OP")
                    self.assertFalse(self.output.exists())
                else:
                    reply, _ = await self.run_image(remove_background=True)
                    self.assertTrue(reply["background_removal_completed"])
                    self.output.unlink()
            self.assertEqual(self.source.read_bytes(), source)
        await actual.stop()
        with self.assertRaises(BridgeError) as caught:
            await self.run_image(remove_background=True)
        self.assertEqual(caught.exception.code, "DISCONNECTED")
        self.assertFalse(self.output.exists())

    async def test_timeout_then_late_reply_cannot_publish_or_satisfy_next_request(self):
        _, result = self.prepare()
        token = secrets.token_urlsafe(48)
        actual = PhotoshopBridge(Config(), token)
        await actual.start()
        self.addAsyncCleanup(actual.stop)
        self.assertIsNone(actual.startup_error)
        self.processor = processing.ImageProcessor(actual)
        async with connect(ENDPOINT, family=socket.AF_INET, proxy=None, compression=None) as peer:
            await peer.send(encode({"type": "auth", "protocol_version": 1, "token": token}))
            self.assertTrue(decode(await peer.recv())["ok"])
            original_timeout, deadlines = asyncio.timeout, []
            def short_timeout(seconds):
                deadlines.append(seconds)
                return original_timeout(0.05)
            with patch.object(bridge_module.asyncio, "timeout", short_timeout):
                task = asyncio.create_task(self.run_image(remove_background=True))
                first = decode(await peer.recv())
                with self.assertRaises(BridgeError) as caught:
                    await task
            self.assertEqual(caught.exception.code, "TIMEOUT")
            self.assertEqual(deadlines, [30.0])
            self.assertFalse(self.output.exists())
            task = asyncio.create_task(self.run_image(remove_background=True))
            second = decode(await peer.recv())
            self.assertNotEqual(first["id"], second["id"])
            await peer.send(encode({"type": "response", "protocol_version": 1, "id": first["id"],
                                   "operation": PROCESS_OPERATION, "ok": True, "result": result, "error": None}))
            # A WebSocket ping/pong orders delivery behind the late response.
            await (await peer.ping())
            self.assertFalse(task.done())
            self.assertFalse(self.output.exists())
            await peer.close()
            with self.assertRaises(BridgeError) as disconnected:
                await task
            self.assertEqual(disconnected.exception.code, "DISCONNECTED")
            self.assertFalse(self.output.exists())

    async def test_mcp_schema_stays_narrow_and_defaults_to_false(self):
        self.prepare()
        server = MCPServer("removal-test")
        register_tools(server, self.bridge)
        async with Client(server) as client:
            listing = await client.list_tools()
            self.assertEqual(len(listing.tools), 3)
            tool = next(t for t in listing.tools if t.name == PROCESS_OPERATION)
            fields = tool.input_schema["properties"]
            self.assertEqual(set(fields), {"source_relative_path", "staging_relative_path", "width_px",
                                           "height_px", "remove_background", "mode", "resample"})
            self.assertIs(fields["remove_background"]["default"], False)
            reply = await client.call_tool(PROCESS_OPERATION, {"source_relative_path": self.source_name,
                "staging_relative_path": self.output_name, "width_px": 4, "height_px": 4, "remove_background": True})
            self.assertFalse(reply.is_error, reply.structured_content)
            self.assertTrue(reply.structured_content["result"]["background_removal_completed"])
