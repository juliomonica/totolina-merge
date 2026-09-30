"""Bounded, independent validation of the PNG subset used by Phase 2A.

No image editing: decode pixels only to verify dimensions, alpha and padding.
"""
from dataclasses import dataclass
import struct
import zlib

MAX_IMAGE_BYTES = 24 * 1024 * 1024
MAX_DIMENSION = 2048
SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PNGError(ValueError):
    pass


@dataclass(frozen=True)
class PNG:
    width: int
    height: int
    pixels: bytes

    @property
    def has_transparency(self) -> bool:
        return any(alpha < 255 for alpha in self.pixels[3::4])


def read_png(data: bytes) -> PNG:
    """Require one complete, non-interlaced, 8-bit RGBA PNG; reject APNG."""
    if not 0 < len(data) <= MAX_IMAGE_BYTES or not data.startswith(SIGNATURE):
        raise PNGError("Invalid PNG or encoded size limit.")
    offset, header, compressed, ended, idat_ended = 8, None, bytearray(), False, False
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data) or not all(65 <= b <= 90 or 97 <= b <= 122 for b in kind):
            raise PNGError("Invalid PNG chunk.")
        content = data[offset + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + content) != crc or kind in {b"acTL", b"fcTL", b"fdAT", b"tRNS"}:
            raise PNGError("Invalid checksum or unsupported PNG.")
        if header is None and kind != b"IHDR":
            raise PNGError("Missing initial IHDR.")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise PNGError("Invalid IHDR.")
            header = struct.unpack(">IIBBBBB", content)
            width, height, depth, color, compression, filtering, interlace = header
            if (not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION
                    or (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0)):
                raise PNGError("Only bounded non-interlaced RGBA8 PNG is supported.")
        elif kind == b"IDAT":
            if idat_ended:
                raise PNGError("Non-consecutive IDAT.")
            compressed.extend(content)
        elif kind == b"IEND":
            if length or not compressed or end != len(data):
                raise PNGError("Invalid IEND.")
            ended = True
            break
        elif kind == b"PLTE":
            if compressed or not length or length % 3 or length > 768:
                raise PNGError("Invalid palette.")
        elif kind[0] & 32 == 0:
            raise PNGError("Unknown critical chunk.")
        if compressed and kind != b"IDAT":
            idat_ended = True
        offset = end
    if not ended or header is None:
        raise PNGError("Truncated PNG.")
    width, height = header[:2]
    stride = width * 4
    expected = (stride + 1) * height
    try:
        inflater = zlib.decompressobj()
        raw = inflater.decompress(bytes(compressed), expected + 1)
    except zlib.error:
        raise PNGError("Invalid compressed pixels.") from None
    if (len(raw) != expected or not inflater.eof or inflater.unused_data
            or inflater.unconsumed_tail):
        raise PNGError("Invalid or oversized pixel stream.")
    pixels, previous = bytearray(), bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + stride + 1])
        if method > 4:
            raise PNGError("Invalid row filter.")
        if method:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                above = previous[x]
                upper_left = previous[x - 4] if x >= 4 else 0
                if method == 1:
                    prediction = left
                elif method == 2:
                    prediction = above
                elif method == 3:
                    prediction = (left + above) // 2
                else:
                    p = left + above - upper_left
                    a, b, c = abs(p - left), abs(p - above), abs(p - upper_left)
                    prediction = left if a <= b and a <= c else above if b <= c else upper_left
                row[x] = (row[x] + prediction) & 255
        pixels.extend(row)
        previous = row
    return PNG(width, height, bytes(pixels))


def verify_canvas(source: PNG, output: PNG, width: int, height: int) -> None:
    """Verify original alpha is unchanged and all added padding is transparent."""
    if (output.width, output.height) != (width, height) or not output.has_transparency:
        raise PNGError("Wrong output dimensions or no transparent pixels.")
    dx, dy = (width - source.width) // 2, (height - source.height) // 2
    if dx < 0 or dy < 0:
        raise PNGError("Canvas would crop the source.")
    for y in range(height):
        alpha = output.pixels[(y * width) * 4 + 3:((y + 1) * width) * 4:4]
        if dy <= y < dy + source.height:
            source_start = (y - dy) * source.width * 4
            expected = source.pixels[source_start + 3:source_start + source.width * 4:4]
            if alpha[dx:dx + source.width] != expected:
                raise PNGError("Source transparency changed.")
            if any(alpha[:dx]) or any(alpha[dx + source.width:]):
                raise PNGError("Opaque horizontal padding.")
        elif any(alpha):
            raise PNGError("Opaque vertical padding.")
