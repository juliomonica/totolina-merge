"""Bounded RGB/RGBA PNG decoding, RGBA encoding and independent alpha validation."""
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
    color_type: int = 6

    @property
    def has_transparency(self) -> bool:
        return any(alpha < 255 for alpha in self.pixels[3::4])


def read_png(data: bytes) -> PNG:
    """Decode RGB/RGBA8 to RGBA pixels; reject interlacing, APNG and tRNS."""
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
                    or color not in (2, 6)
                    or (depth, compression, filtering, interlace) != (8, 0, 0, 0)):
                raise PNGError("Only bounded non-interlaced RGB/RGBA8 PNG is supported.")
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
    channels = 3 if header[3] == 2 else 4
    stride = width * channels
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
                left = row[x - channels] if x >= channels else 0
                above = previous[x]
                upper_left = previous[x - channels] if x >= channels else 0
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
        if channels == 3:
            for x in range(0, stride, 3):
                pixels.extend(row[x:x + 3])
                pixels.append(255)
        else:
            pixels.extend(row)
        previous = row
    return PNG(width, height, bytes(pixels), header[3])


def fitted_size(source_width: int, source_height: int, width: int, height: int,
                mode: str = "preserve_size") -> tuple[int, int]:
    """One proportional scale <= 1, rounded half-up to whole pixels (minimum one)."""
    if mode not in ("preserve_size", "fit"):
        raise PNGError("Invalid processing mode.")
    if source_width <= width and source_height <= height:
        return source_width, source_height
    if mode == "preserve_size":
        raise PNGError("Canvas would crop the source.")
    if width * source_height <= height * source_width:
        return width, max(1, (2 * source_height * width + source_width) // (2 * source_width))
    return max(1, (2 * source_width * height + source_height) // (2 * source_height)), height


def rgba_png(data: bytes) -> bytes:
    """Make an opaque RGB host export RGBA without changing pixels or profiles.

    Photoshop can optimize an opaque export to RGB. Re-encode only that case;
    Preserve ancillary chunks, extending sBIT to describe the new alpha channel.
    """
    image = read_png(data)
    if image.color_type == 6:
        return data
    def chunk(kind, content):
        return (struct.pack(">I", len(content)) + kind + content
                + struct.pack(">I", zlib.crc32(kind + content)))
    stride = image.width * 4
    raw = b"".join(b"\0" + image.pixels[y * stride:(y + 1) * stride] for y in range(image.height))
    encoded = bytearray(SIGNATURE)
    offset, wrote_pixels = 8, False
    while offset < len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if kind == b"IHDR":
            encoded.extend(chunk(kind, struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)))
        elif kind == b"sBIT":
            significant_bits = data[offset + 8:end - 4]
            if len(significant_bits) != 3 or any(not 1 <= bits <= 8 for bits in significant_bits):
                raise PNGError("Invalid RGB significant bits.")
            encoded.extend(chunk(kind, significant_bits + b"\x08"))
        elif kind == b"IDAT":
            if not wrote_pixels:
                encoded.extend(chunk(kind, zlib.compress(raw)))
                wrote_pixels = True
        else:
            encoded.extend(data[offset:end])
        offset = end
    if len(encoded) > MAX_IMAGE_BYTES:
        raise PNGError("RGBA export exceeds the encoded size limit.")
    return bytes(encoded)


def verify_canvas(source: PNG, output: PNG, width: int, height: int,
                  mode: str = "preserve_size", resample: str = "bicubic",
                  resampled_alpha_crc32: int | None = None) -> str:
    """Check padding and exact source/nearest alpha, or native bicubic alpha integrity.

    Bicubic RGB/RGBA alpha is checked against Photoshop's pre-padding pixel checksum,
    not an independently recreated interpolation kernel. CRC is an integrity check,
    not authentication; the existing authenticated bridge remains the trust boundary.
    """
    if resample not in ("bicubic", "nearest"):
        raise PNGError("Invalid resample method.")
    if (output.width, output.height) != (width, height) or output.color_type != 6:
        raise PNGError("Wrong output dimensions or missing RGBA channels.")
    artwork_width, artwork_height = fitted_size(source.width, source.height, width, height, mode)
    dx, dy = (width - artwork_width) // 2, (height - artwork_height) // 2
    if dx < 0 or dy < 0:
        raise PNGError("Canvas would crop the source.")
    resized = (artwork_width, artwork_height) != (source.width, source.height)
    native_alpha = resized and resample == "bicubic"
    if native_alpha and (type(resampled_alpha_crc32) is not int
                         or not 0 <= resampled_alpha_crc32 <= 0xffffffff):
        raise PNGError("Missing native resampled alpha checksum.")
    checksum = 0
    for y in range(height):
        alpha = output.pixels[(y * width) * 4 + 3:((y + 1) * width) * 4:4]
        if dy <= y < dy + artwork_height:
            artwork_alpha = alpha[dx:dx + artwork_width]
            if native_alpha:
                checksum = zlib.crc32(artwork_alpha, checksum)
            else:
                source_y = (2 * (y - dy) + 1) * source.height // (2 * artwork_height)
                source_start = source_y * source.width * 4
                expected = bytes(source.pixels[source_start +
                    ((2 * x + 1) * source.width // (2 * artwork_width)) * 4 + 3]
                    for x in range(artwork_width))
                if artwork_alpha != expected:
                    raise PNGError("Source transparency changed.")
            if any(alpha[:dx]) or any(alpha[dx + artwork_width:]):
                raise PNGError("Opaque horizontal padding.")
        elif any(alpha):
            raise PNGError("Opaque vertical padding.")
    if native_alpha and checksum != resampled_alpha_crc32:
        raise PNGError("Native resampled transparency changed during padding/export.")
    return "photoshop_bicubic_crc32" if native_alpha else "nearest_exact" if resized and resample == "nearest" else "source_exact"
