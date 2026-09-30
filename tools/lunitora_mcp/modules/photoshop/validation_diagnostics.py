"""Failure-only, bounded scalar diagnostics; never include image data or peer text."""
import zlib

from .png_validation import PNG, fitted_size


# Only locally authored validator messages can become public reason codes.
CONDITIONS = {
    "Wrong output dimensions or missing RGBA channels.": "OUTPUT_DIMENSIONS_OR_RGBA",
    "Canvas would crop the source.": "CANVAS_CROPS_SOURCE",
    "Missing native resampled alpha checksum.": "NATIVE_ALPHA_CHECKSUM_MISSING",
    "Source transparency changed.": "ARTWORK_ALPHA_MISMATCH",
    "Opaque horizontal padding.": "HORIZONTAL_PADDING_NOT_TRANSPARENT",
    "Opaque vertical padding.": "VERTICAL_PADDING_NOT_TRANSPARENT",
    "Native resampled transparency changed during padding/export.": "NATIVE_ALPHA_CHECKSUM_MISMATCH",
    "Mismatched peer dimensions.": "PEER_DIMENSIONS_MISMATCH",
    "Source changed during processing.": "SOURCE_CHANGED",
}


def rectangle(left, top, right, bottom):
    return {"width_px": right - left, "height_px": bottom - top,
            "offset_x_px": left, "offset_y_px": top}


def canvas_diagnostics(source: PNG, output: PNG | None, width: int, height: int,
                       mode: str, resample: str, native_checksum: int | None) -> dict:
    """Measure every check without changing verify_canvas's acceptance or first failure.

    Observed bounds describe nonzero/opaque alpha, not inferred artwork placement:
    transparent source borders can make these smaller than the artwork rectangle.
    Unknown/unavailable checks are null, never reported as passing.
    """
    aw, ah = fitted_size(source.width, source.height, width, height, mode)
    dx, dy = (width - aw) // 2, (height - ah) // 2
    resized = (aw, ah) != (source.width, source.height)
    native_alpha = resized and resample == "bicubic"
    report = {
        "source": {"width_px": source.width, "height_px": source.height,
                   "color_type": "RGB" if source.color_type == 2 else "RGBA"},
        "mode": mode, "resample": resample,
        "expected_output": {"width_px": width, "height_px": height},
        "actual_output": None,
        "expected_artwork": rectangle(dx, dy, dx + aw, dy + ah),
        "actual_nontransparent_bounds": None, "actual_opaque_bounds": None,
        "output_is_rgba": None, "has_transparency": None,
        "dimensions_validation_failed": None,
        "padding_validation_failed": None, "alpha_validation_failed": None,
        "source_unchanged_validation_failed": None,
        "alpha_validation": "photoshop_bicubic_crc32" if native_alpha else
            "nearest_exact" if resized and resample == "nearest" else "source_exact",
        "artwork_alpha_min": None, "artwork_alpha_max": None,
        "artwork_partial_alpha_pixel_count": None,
        "artwork_partial_alpha_edge_pixel_count": None,
        "artwork_alpha_mismatch_count": None, "first_artwork_alpha_mismatch": None,
        "padding_nonzero_alpha_pixel_count": None, "first_padding_nonzero_alpha": None,
    }
    if output is None:
        return report
    report.update(actual_output={"width_px": output.width, "height_px": output.height},
                  output_is_rgba=output.color_type == 6, has_transparency=output.has_transparency,
                  dimensions_validation_failed=(output.width, output.height) != (width, height))
    # Scan bounded decoded pixels; expose aggregate counts/bounds and at most two samples.
    visible, opaque = [output.width, output.height, -1, -1], [output.width, output.height, -1, -1]
    padding_count = mismatches = partial = edge_partial = 0
    alpha_min, alpha_max, checksum = 255, 0, 0
    same_size = (output.width, output.height) == (width, height)
    for y in range(output.height):
        row = output.pixels[y * output.width * 4 + 3:(y + 1) * output.width * 4:4]
        for x, alpha in enumerate(row):
            for bounds, present in ((visible, alpha > 0), (opaque, alpha == 255)):
                if present:
                    bounds[0], bounds[1] = min(bounds[0], x), min(bounds[1], y)
                    bounds[2], bounds[3] = max(bounds[2], x), max(bounds[3], y)
            inside = dx <= x < dx + aw and dy <= y < dy + ah
            if not inside:
                if alpha:
                    padding_count += 1
                    if report["first_padding_nonzero_alpha"] is None:
                        report["first_padding_nonzero_alpha"] = {"x_px": x, "y_px": y, "alpha": alpha}
                continue
            alpha_min, alpha_max = min(alpha_min, alpha), max(alpha_max, alpha)
            partial += 0 < alpha < 255
            edge_partial += 0 < alpha < 255 and (x in (dx, dx + aw - 1) or y in (dy, dy + ah - 1))
            if same_size and not native_alpha:
                sx = (2 * (x - dx) + 1) * source.width // (2 * aw)
                sy = (2 * (y - dy) + 1) * source.height // (2 * ah)
                expected = source.pixels[(sy * source.width + sx) * 4 + 3]
                if alpha != expected:
                    mismatches += 1
                    if report["first_artwork_alpha_mismatch"] is None:
                        report["first_artwork_alpha_mismatch"] = {
                            "x_px": x, "y_px": y, "expected_alpha": expected, "actual_alpha": alpha}
        if same_size and dy <= y < dy + ah:
            checksum = zlib.crc32(row[dx:dx + aw], checksum)
    for name, bounds in (("actual_nontransparent_bounds", visible), ("actual_opaque_bounds", opaque)):
        if bounds[2] >= 0:
            report[name] = rectangle(bounds[0], bounds[1], bounds[2] + 1, bounds[3] + 1)
    if same_size:
        report.update(padding_validation_failed=padding_count > 0,
                      padding_nonzero_alpha_pixel_count=padding_count,
                      artwork_alpha_min=alpha_min, artwork_alpha_max=alpha_max,
                      artwork_partial_alpha_pixel_count=partial,
                      artwork_partial_alpha_edge_pixel_count=edge_partial,
                      actual_artwork_alpha_crc32=checksum)
        if native_alpha:
            valid_checksum = type(native_checksum) is int and 0 <= native_checksum <= 0xffffffff
            report.update(alpha_validation_failed=not valid_checksum or checksum != native_checksum,
                          expected_artwork_alpha_crc32=native_checksum if valid_checksum else None,
                          actual_artwork_alpha_crc32=checksum)
        else:
            report.update(alpha_validation_failed=mismatches > 0, artwork_alpha_mismatch_count=mismatches)
    return report
