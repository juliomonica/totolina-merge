"""Render and validate the fixed assembled-cat lab in an isolated native project.

The authored scene, accepted artwork and v0.5 fixture are read-only inputs.
Evidence, import caches, native save/reopen output and userdata stay under --output.
Use --quick only while iterating: it cannot establish the realtime20-loop proof.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def components(mask: np.ndarray) -> list[int]:
    """Four-connected opaque components; independent of the declared rig."""
    visited = np.zeros(mask.shape, dtype=bool)
    height, width = mask.shape
    sizes = []
    for y, x in zip(*np.nonzero(mask)):
        if visited[y, x]:
            continue
        visited[y, x] = True
        queue = deque([(int(y), int(x))])
        count = 0
        while queue:
            row, column = queue.popleft()
            count += 1
            for nr, nc in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
                if 0 <= nr < height and 0 <= nc < width and mask[nr, nc] and not visited[nr, nc]:
                    visited[nr, nc] = True
                    queue.append((nr, nc))
        sizes.append(count)
    return sorted(sizes, reverse=True)


def pixels(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.int16)


def difference(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    delta = np.abs(first - second)
    delta[(first[:, :, 3] == 0) & (second[:, :, 3] == 0), :3] = 0
    return delta


def verify_images(evidence: Path, report: dict) -> dict:
    phones = [item for item in report["captures"] if item["kind"] == "phone"]
    expected_phases = {"rest", "quarter", "breath_extreme", "three_quarter", "end", "boundary_before", "boundary_after"}
    if len(phones) != 21 or {item["phase"] for item in phones} != expected_phases:
        raise RuntimeError("Missing required phone/key/extreme/boundary captures")
    connectivity = []
    boundaries = []
    for size in ((390, 844), (405, 720), (540, 960)):
        current = [item for item in phones if item["viewport"] == list(size)]
        if len(current) != 7:
            raise RuntimeError(f"Missing required phone captures: {size}")
        feet = current[0]["feet_canvas_transforms"]
        for item in current:
            if item["feet_canvas_transforms"] != feet:
                raise RuntimeError(f"Feet slide in native canvas transforms: {item['name']}")
            image = pixels(evidence / (item["name"] + ".png"))
            if image.shape[:2] != (size[1], size[0]):
                raise RuntimeError("Phone screenshot has incorrect native dimensions")
            mask = image[:, :, 3] >= 128
            sizes = components(mask)
            fraction = sizes[0] / int(mask.sum()) if sizes else 0.0
            if not sizes or sizes[0] < 10_000 or fraction < .995:
                raise RuntimeError(f"Blank/disconnected assembled character: {item['name']}; {sizes[:8]}")
            if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
                raise RuntimeError(f"Character clipped by phone viewport: {item['name']}")
            connectivity.append({"name": item["name"], "largest_component_fraction": fraction,
                                 "opaque_pixels": int(mask.sum()), "components_over16_pixels": sum(count > 16 for count in sizes)})
        prefix = f"{size[0]}x{size[1]}"
        rest = pixels(evidence / (prefix + "_rest.png"))
        end = pixels(evidence / (prefix + "_end.png"))
        if not np.array_equal(rest, end):
            raise RuntimeError(f"Loop endpoints render differently: {prefix}")
        before = pixels(evidence / (prefix + "_boundary_before.png"))
        after = pixels(evidence / (prefix + "_boundary_after.png"))
        delta = difference(before, after)
        changed = np.any(delta, axis=2)
        # Smooth ease-in/out can move antialiased edge pixels fractionally.
        # A one-level AA change can touch many edge pixels without a visual
        # pop. Bound substantial changes (>4/255) independently, retaining
        # strict maximum and whole-image mean limits and reporting both masks.
        substantial = np.any(delta > 4, axis=2)
        if delta.max() > 32 or delta.mean() > .02 or substantial.mean() > .002:
            raise RuntimeError(f"Visible loop-boundary discontinuity: {prefix}; max={delta.max()}, mean={delta.mean()}, substantial_fraction={substantial.mean()}")
        boundaries.append({"viewport": list(size), "endpoints_pixel_identical": True,
                           "before_after_max_difference255": int(delta.max()),
                           "before_after_mean_difference255": float(delta.mean()),
                           "before_after_changed_pixel_fraction": float(changed.mean()),
                           "before_after_difference_over4_pixel_fraction": float(substantial.mean())})
    joints = []
    closeups = [item for item in report["captures"] if item["kind"] == "closeup"]
    if len(closeups) != 35 or {item["part"] for item in closeups} != {
            "shoulder_l", "elbow_l", "shoulder_r", "elbow_r", "neck", "feet", "tail_attachment"}:
        raise RuntimeError("Missing fixed attachment closeups")
    neck = []
    for item in closeups:
        if item["part"] == "neck":
            image = pixels(evidence / (item["name"] + ".png"))
            # Accepted head source rows1158..1164 contain its heavy bottom-neck
            # outline. Native closeups center on HeadPivot at1.4 body-px scale.
            left = math.ceil(320 - 12 * 1.4 - .5)
            right = math.floor(320 + 12 * 1.4 - .5) + 1
            top = math.ceil(240 + 1.4 * .8 * (1158 - 1145) - .5)
            bottom = math.floor(240 + 1.4 * .8 * (1164 - 1145) - .5) + 1
            patch = image[top:bottom, left:right]
            red = ((patch[:, :, 0] > 1.5 * patch[:, :, 1])
                   & (patch[:, :, 0] > 1.5 * patch[:, :, 2]) & (patch[:, :, 3] >= 250))
            if not red.size or not red.all():
                raise RuntimeError(f"Scarf exposes accepted bottom-neck attachment: {item['name']}")
            neck.append({"name": item["name"], "neck_bottom_outline_hidden": True, "covered_pixels": int(red.sum())})
        if not item["part"].startswith(("shoulder", "elbow")):
            continue
        image = pixels(evidence / (item["name"] + ".png"))
        mask = image[:, :, 3] >= 128
        rows, columns = np.ogrid[:mask.shape[0], :mask.shape[1]]
        x, y = item["joint_px"]
        disk = (columns + .5 - x) ** 2 + (rows + .5 - y) ** 2 <= item["joint_radius_px"] ** 2
        if not disk.any() or not mask[disk].all():
            raise RuntimeError(f"Transparent gap at measured attachment: {item['name']}")
        joints.append({"name": item["name"], "opaque_attachment_disk_pixels": int(disk.sum())})
    comparisons = []
    for index in range(report["gpu_cpu_samples"]):
        gpu = pixels(evidence / f"tail_gpu_{index:02d}.png")
        cpu = pixels(evidence / f"tail_cpu_{index:02d}.png")
        delta = difference(gpu, cpu)
        if delta.max() > 8 or delta.mean() > .01:
            raise RuntimeError(f"Native tail GPU/CPU skinning mismatch: {index}; {delta.max()}, {delta.mean()}")
        comparisons.append({"index": index, "max_difference255": int(delta.max()), "mean_difference255": float(delta.mean())})
    return {"phone_connectivity": connectivity, "attachment_disks": joints, "scarf_neck_coverage": neck, "loop_boundaries": boundaries,
            "tail_gpu_cpu_comparisons": comparisons, "feet_canvas_transforms_static": True,
            "subjective_art_quality": "REQUIRES USER REVIEW"}


def contact_sheets(evidence: Path) -> list[str]:
    phases = ("rest", "quarter", "breath_extreme", "three_quarter", "end", "boundary_before", "boundary_after")
    sheet = Image.new("RGB", (7 * 290, 3 * 610), "#d9dfe4")
    draw = ImageDraw.Draw(sheet)
    for row, size in enumerate(((390, 844), (405, 720), (540, 960))):
        for column, phase in enumerate(phases):
            image = Image.open(evidence / f"{size[0]}x{size[1]}_{phase}.png").convert("RGBA")
            image.thumbnail((274, 572))
            left, top = column * 290 + (290 - image.width) // 2, row * 610 + 30
            sheet.paste(image, (left, top), image)
            draw.text((column * 290 + 8, row * 610 + 8), f"{size[0]}x{size[1]} | {phase}", fill="#202831")
    sheet.save(evidence / "phone-key-poses.png")
    parts = ("shoulder_l", "elbow_l", "shoulder_r", "elbow_r", "neck", "feet", "tail_attachment")
    attachment = Image.new("RGB", (5 * 400, 7 * 330), "#d9dfe4")
    draw = ImageDraw.Draw(attachment)
    for row, part in enumerate(parts):
        for column, time in enumerate((0, 1.5, 3, 4.5, 6)):
            image = Image.open(evidence / f"closeup_{part}_{column:02d}.png").convert("RGBA")
            image.thumbnail((400, 300))
            left, top = column * 400, row * 330 + 30
            attachment.paste(image, (left, top), image)
            draw.text((left + 8, row * 330 + 8), f"{part} | t={time:g}s", fill="#202831")
    attachment.save(evidence / "attachment-key-poses.png")
    frames = []
    for index in range(60):
        image = Image.open(evidence / f"motion_{index:02d}.png").convert("RGBA")
        background = Image.new("RGB", image.size, "#d9dfe4")
        background.paste(image, (0, 0), image)
        frames.append(background)
    frames[0].save(evidence / "assembled-idle.gif", save_all=True, append_images=frames[1:], duration=100, loop=0, disposal=2)
    return ["phone-key-poses.png", "attachment-key-poses.png", "assembled-idle.gif"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true", help="Manual advance iteration; excludes realtime proof")
    parser.add_argument("--timeout", type=int, default=360)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    assets = repository / "addons/lunitora_godot/test_assets/rig_test_cat"
    scene = repository / "addons/lunitora_godot/labs/rig_test_cat_assembled_idle_lab.tscn"
    spec = repository / "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
    tracked_inputs = [scene, spec, *[path for path in assets.rglob("*") if path.is_file()]]
    hashes = {path: digest(path) for path in tracked_inputs}
    project = args.output.resolve()
    if project.exists() and any(project.iterdir()):
        raise RuntimeError("--output must be absent or empty; existing evidence is never overwritten")
    project.mkdir(parents=True, exist_ok=True)
    shutil.copytree(assets, project / assets.relative_to(repository))
    scene_destination = project / scene.relative_to(repository)
    scene_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(scene, scene_destination)
    shutil.copy2(spec, project / "fixture_spec.json")
    shutil.copy2(Path(__file__).with_name("assembled_idle_validation.gd"), project / "oracle.gd")
    bounds = {}
    for path in assets.rglob("*.png"):
        with Image.open(path) as image:
            alpha = np.asarray(image.convert("RGBA"))[:, :, 3] >= 16
            rows, columns = np.nonzero(alpha)
            if not rows.size:
                raise RuntimeError(f"Blank accepted texture: {path.name}")
            bounds["res://" + path.relative_to(repository).as_posix()] = [int(columns.min()), int(rows.min()), int(columns.max()) + 1, int(rows.max()) + 1]
    (project / "alpha_bounds.json").write_text(json.dumps(bounds), encoding="utf-8")
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Assembled idle isolated validation"\n'
        '[display]\nwindow/size/viewport_width=405\nwindow/size/viewport_height=720\n'
        '[rendering]\nrenderer/rendering_method="mobile"\nrendering_device/driver.windows="d3d12"\n', encoding="utf-8")
    env = dict(os.environ)
    env["APPDATA"] = str(project / "userdata")
    env["LOCALAPPDATA"] = str(project / "cache")
    commands = [
        ("import", [args.godot, "--headless", "--path", str(project), "--editor", "--import", "--quit"]),
        ("graphical", [args.godot, "--path", str(project), "--position", "-10000,-10000", "--script", "res://oracle.gd", "--", *(["--quick"] if args.quick else [])]),
    ]
    for label, command in commands:
        try:
            completed = subprocess.run(command, env=env, capture_output=True, timeout=args.timeout)
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b"") + (error.stderr or b"")
            (project / (label + ".log")).write_bytes(output)
            raise RuntimeError(f"{label} timed out; diagnostics: {project / (label + '.log')}") from error
        output = completed.stdout + completed.stderr
        (project / (label + ".log")).write_bytes(output)
        if completed.returncode or any(token in output for token in (b"SCRIPT ERROR", b"ERROR:", b"WARNING:")):
            lines = output.decode(errors="replace").splitlines()
            preview = "\n".join(lines[:35])
            raise RuntimeError(f"{label} native validation failed; full diagnostics: {project / (label + '.log')}\n{preview}")
    evidence = project / "evidence"
    report = json.loads((evidence / "native-report.json").read_text())
    if (report["renderer"], report["driver"]) != ("mobile", "d3d12"):
        raise RuntimeError("Unexpected graphical renderer/driver")
    graphical = verify_images(evidence, report)
    sheets = contact_sheets(evidence)
    if any(digest(path) != expected for path, expected in hashes.items()):
        raise RuntimeError("Authored source/accepted fixture changed during isolated validation")
    report.update({"graphical": graphical, "review_artifacts": sheets,
                   "readonly_source_hashes_preserved": len(hashes), "authored_scene_sha256": hashes[scene],
                   "fixture_spec_sha256": hashes[spec], "realtime20_loop_proof": not args.quick})
    (project / "verified-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifacts": str(project), "node_count": report["node_count"], "idle_tracks": len(report["tracks"]),
                      "idle_keys": report["idle_key_count"], "reset_keys": report["reset_key_count"],
                      "native_assertions": report["native_assertions"], "geometry_samples": report["geometry_samples"],
                      "gpu_cpu_samples": report["gpu_cpu_samples"], "continuous_playback": report["continuous_playback"],
                      "replay_cycles": report["replay_cycles"],
                      "capture_count": len(report["captures"]) + 2 * report["gpu_cpu_samples"] + 1,
                      "min_triangle_area_ratio": report["min_triangle_area_ratio"],
                      "max_triangle_area_ratio": report["max_triangle_area_ratio"],
                      "max_native_value_error": report["max_native_value_error"], "review_artifacts": sheets,
                      "status": "VERIFIED" if not args.quick else "ITERATION ONLY: realtime proof NOT EXECUTED"}, indent=2))


if __name__ == "__main__":
    main()
