"""Render a native public-writer saved fixture against independent CPU skinning."""
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
import tempfile

import numpy as np
from PIL import Image, ImageDraw


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_body_alignment(repository: Path) -> dict:
    """Check the fixed neck/collar contours in BodyStation-local pixel units."""
    spec = json.loads((repository / "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json").read_text())
    nodes = {node["path"]: node for node in spec["nodes"]}
    pivot = nodes["BodyStation/HeadPivot"]
    head = nodes["BodyStation/HeadPivot/Head"]
    torso = nodes["BodyStation/Torso"]
    if (pivot["position_px"] != [0, 306] or pivot["scale"] != [.8, .8]
            or head["pivot_px"] != [627, 1145] or torso["pivot_px"] != [561, 0]
            or nodes["BodyStation"]["scale"] != [.375, .375]):
        raise RuntimeError("Approved BodyStation alignment transforms changed")
    animation = spec["animation"]
    track = animation["paths"].index("BodyStation/HeadPivot:position:y")
    keys = animation["values"][track]
    rest_y = pivot["position_px"][1]
    relative_bob = [value - rest_y for value in keys]
    if (keys != [306, 300, 294, 300, 306] or keys[0] != rest_y or keys[-1] != rest_y
            or relative_bob != [0, -6, -12, -6, 0]):
        raise RuntimeError("Head rest endpoints or relative bob changed")
    assets = {asset["id"]: asset for asset in spec["textures"]}
    alpha_threshold = 128
    band = (-210.0, 210.0)
    with Image.open(repository / assets["head_full"]["path"].removeprefix("res://")) as image:
        head_mask = np.asarray(image.getchannel("A")) >= alpha_threshold
    with Image.open(repository / assets["torso"]["path"].removeprefix("res://")) as image:
        torso_mask = np.asarray(image.getchannel("A")) >= alpha_threshold
    head_columns = head_mask.any(axis=0)
    torso_columns = torso_mask.any(axis=0)
    # Pixel edges, not centers: a head pixel maps to an 0.8-wide local interval.
    head_bottom = head_mask.shape[0] - np.argmax(head_mask[::-1], axis=0)
    torso_top = np.argmax(torso_mask, axis=0)
    overlaps = []
    covered_width = 0.0
    for source_x in np.flatnonzero(head_columns):
        left = max(band[0], .8 * (int(source_x) - head["pivot_px"][0]))
        right = min(band[1], .8 * (int(source_x) + 1 - head["pivot_px"][0]))
        if right <= left:
            continue
        for torso_x in range(max(0, math.floor(left + torso["pivot_px"][0])),
                             min(torso_mask.shape[1], math.ceil(right + torso["pivot_px"][0]))):
            start = max(left, torso_x - torso["pivot_px"][0])
            end = min(right, torso_x + 1 - torso["pivot_px"][0])
            if end - start <= 1e-8:
                continue
            if not torso_columns[torso_x]:
                raise RuntimeError("Collar contour has no opaque attachment in the reviewed band")
            bottom = rest_y + .8 * (int(head_bottom[source_x]) - head["pivot_px"][1])
            overlaps.append(bottom - int(torso_top[torso_x]))
            covered_width += end - start
    if not overlaps or abs(covered_width - (band[1] - band[0])) > 1e-8:
        raise RuntimeError("Head/collar contour does not cover the complete reviewed attachment band")
    rest_overlap = min(overlaps)
    highest_bob_overlap = rest_overlap + min(relative_bob)
    if rest_overlap < 16.0 or highest_bob_overlap < 4.0:
        raise RuntimeError("Lateral cheek/collar gap or insufficient overlap at rest/highest bob")
    return {"alpha_threshold": alpha_threshold, "attachment_band_local_px": list(band),
            "minimum_rest_overlap_local_px": rest_overlap,
            "minimum_highest_bob_overlap_local_px": highest_bob_overlap,
            "rest_y": rest_y, "head_y_keys": keys, "relative_bob": relative_bob}


def verify_scarf_spec(repository: Path) -> dict:
    """Use only the pinned fixture specification, never a tuning artifact."""
    spec_path = repository / "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
    spec = json.loads(spec_path.read_text())
    nodes = {node["path"]: node for node in spec["nodes"]}
    scarf = nodes["BodyStation/ScarfForeground"]
    if (len(nodes) != 19 or scarf["class"] != "Sprite2D"
            or scarf["position_px"] != [0, 0] or scarf["rotation_rad"] != 0
            or scarf["scale"] != [1, 1] or scarf["z_index"] != 1
            or scarf["texture"] != "scarf_foreground" or scarf["pivot_px"] != [139, -238]
            or "uv_px" in scarf or "vertices_px" in scarf):
        raise RuntimeError("Approved static ScarfForeground contract changed")
    assets = {asset["id"]: asset for asset in spec["textures"]}
    asset = assets[scarf["texture"]]
    source = repository / asset["path"].removeprefix("res://")
    if (asset["size_px"] != [288, 147] or asset["import_settings"]["process/fix_alpha_border"] is not False
            or digest(source) != asset["source_sha256"]
            or digest(Path(str(source) + ".import")) != asset["import_sha256"]):
        raise RuntimeError("Pinned extracted scarf source/import contract changed")
    with Image.open(source) as image:
        if image.size != (288, 147):
            raise RuntimeError("Extracted scarf dimensions changed")
    if any("ScarfForeground" in path for path in spec["animation"]["paths"]):
        raise RuntimeError("Static ScarfForeground acquired an animation track")
    return {"spec_sha256": digest(spec_path), "generated_node_count": len(nodes),
            "sprite_offset_px": [-139, 238], "sprite_size_px": asset["size_px"],
            "separate_texture_id": scarf["texture"], "source_import_hashes_match": True,
            "z_index": scarf["z_index"], "no_animation_track": True}


def verify_scarf_captures(evidence: Path, report: dict) -> dict:
    """Protect the face/jaw and quantify the bounded opacity duplicate."""
    if (report["generated_node_count"] != 19 or not report["scarf_separate_texture"]
            or not report["scarf_exact_sprite_spec"] or not report["scarf_not_animated"]):
        raise RuntimeError("Native ScarfForeground fixture verification failed")
    captures = []
    for item in report["scarf_captures"]:
        name, y = item["presentation"], item["head_y"]
        off = np.asarray(Image.open(evidence / f"scarf_{name}_y{y}_off.png").convert("RGBA"), dtype=np.int16)
        on = np.asarray(Image.open(evidence / f"scarf_{name}_y{y}_on.png").convert("RGBA"), dtype=np.int16)
        delta = np.abs(on - off)
        delta[(on[:, :, 3] == 0) & (off[:, :, 3] == 0), :3] = 0
        scale = item["render_scale"]
        origin_x, origin_y = item["origin"]
        protected_end = math.floor(origin_y + scale * item["protected_above_body_y"])
        if np.any(delta[:protected_end]):
            raise RuntimeError(f"Scarf obscured protected face/jaw/whiskers: {name}, Y={y}")
        changed = np.any(delta, axis=2)
        if not np.any(changed):
            raise RuntimeError("Scarf did not change the intended lower-neck attachment")
        changed_y, changed_x = np.nonzero(changed)
        # Source rows 1158..1164 contain the baked central bottom-neck outline.
        # The foreground should replace this ink with the red scarf face at all
        # three approved rest/intermediate/highest-bob positions.
        # Pixel centers are x/y + 0.5. At normal scale this source band is
        # only 1.8 rendered pixels high; whole-pixel-edge rounding can falsely
        # produce an empty crop at Y=294 despite two covered pixel centers.
        left = math.ceil(origin_x - 12 * scale - .5)
        right = math.floor(origin_x + 12 * scale - .5) + 1
        top = math.ceil(origin_y + scale * (y + .8 * (1158 - 1145)) - .5)
        bottom = math.floor(origin_y + scale * (y + .8 * (1164 - 1145)) - .5) + 1
        patch = on[top:bottom, left:right]
        red = ((patch[:, :, 0] > 1.5 * patch[:, :, 1])
               & (patch[:, :, 0] > 1.5 * patch[:, :, 2]) & (patch[:, :, 3] >= 250))
        if not red.size or not np.all(red):
            raise RuntimeError(f"Heavy neck-bottom outline remains exposed: {name}, Y={y}")
        captures.append({**item, "protected_pixels_identical": True, "neck_bottom_outline_hidden": True,
                         "changed_pixels": int(changed.sum()),
                         "changed_bounds_px": [int(changed_x.min()), int(changed_y.min()),
                                               int(changed_x.max()) + 1, int(changed_y.max()) + 1]})
    if len(captures) != 6 or {item["head_y"] for item in captures} != {306, 300, 294}:
        raise RuntimeError("Missing rest/intermediate/highest-bob scarf captures")
    opacity = []
    for name in ("normal", "closeup"):
        off = np.asarray(Image.open(evidence / f"scarf_{name}_torso_off.png").convert("RGBA"), dtype=np.int16)
        on = np.asarray(Image.open(evidence / f"scarf_{name}_torso_on.png").convert("RGBA"), dtype=np.int16)
        delta = np.abs(on - off)
        delta[(on[:, :, 3] == 0) & (off[:, :, 3] == 0), :3] = 0
        # Extracted nearly opaque torso pixels (source alpha 253/254) gain a
        # small amount of opacity. This is measured separately from intentional
        # neck occlusion; no production texture is changed or alpha clamped.
        if delta.max() > 4:
            raise RuntimeError(f"Unexpected scarf duplicate opacity artifact: {name}, max={delta.max()}")
        opacity.append({"presentation": name, "max_rgba_difference_255": int(delta.max()),
                        "max_rgb_difference_255": int(delta[:, :, :3].max()),
                        "max_alpha_difference_255": int(delta[:, :, 3].max()),
                        "mean_rgba_difference_255": float(delta.mean())})
    return {"capture_count": 16, "head_positions": [306, 300, 294], "captures": captures,
            "isolated_torso_opacity": opacity}


def component_sizes(mask: np.ndarray) -> list[int]:
    """Measure rendered opaque connectivity, without using rig geometry."""
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
            for next_row, next_column in ((row - 1, column), (row + 1, column),
                                         (row, column - 1), (row, column + 1)):
                if (0 <= next_row < height and 0 <= next_column < width
                        and mask[next_row, next_column] and not visited[next_row, next_column]):
                    visited[next_row, next_column] = True
                    queue.append((next_row, next_column))
        sizes.append(count)
    return sorted(sizes, reverse=True)


def verify_arm_captures(evidence: Path, report: dict) -> dict:
    """Detect a detached forearm or transparent joint in the actual writer rig."""
    if not report["arm_two_piece_hierarchy"] or report["arm_effective_rest_elbow_px"] != [-77, 136]:
        raise RuntimeError("Native two-piece arm hierarchy/scale verification failed")
    captures = []
    expected_names = {f"arm_{presentation}_{sample}_{index:02d}"
                      for presentation in ("normal", "closeup")
                      for sample in ("elbow", "demo") for index in range(5)}
    expected_names.update(f"arm_{presentation}_demo_{index:02d}"
                          for presentation in ("390x844", "405x720", "540x960") for index in range(3))
    if {item["name"] for item in report["arm_captures"]} != expected_names:
        raise RuntimeError("Missing rest/intermediate/maximum or native demo arm captures")
    for item in report["arm_captures"]:
        image = np.asarray(Image.open(evidence / (item["name"] + ".png")).convert("RGBA"))
        mask = image[:, :, 3] >= 128
        sizes = component_sizes(mask)
        if not sizes or sizes[0] < 10_000 or sizes[0] / int(mask.sum()) < .995:
            raise RuntimeError(f"Blank or detached two-piece arm: {item['name']}")
        y, x = np.ogrid[:mask.shape[0], :mask.shape[1]]
        center_x, center_y = item["joint_px"]
        disk = ((x + .5 - center_x) ** 2 + (y + .5 - center_y) ** 2
                <= item["joint_radius_px"] ** 2)
        if not disk.any() or not mask[disk].all():
            raise RuntimeError(f"Transparent hole at the elbow attachment: {item['name']}")
        captures.append({**item, "opaque_joint_pixels": int(disk.sum()),
                         "largest_opaque_component_fraction": sizes[0] / int(mask.sum()),
                         "major_opaque_components": sum(size > 16 for size in sizes)})
    for presentation in ("normal", "closeup"):
        rest = np.asarray(Image.open(evidence / f"arm_{presentation}_elbow_00.png"))
        for sample in ("demo_00", "demo_04"):
            returned = np.asarray(Image.open(evidence / f"arm_{presentation}_{sample}.png"))
            if not np.array_equal(rest, returned):
                raise RuntimeError(f"Arm did not return to identical rest pixels: {presentation}, {sample}")
    # Assemble the native crops without changing source artwork. Grey grounds
    # make light sleeve edges and alpha holes inspectable at normal/closeup size.
    sheet = Image.new("RGB", (2100, 870), "#d9dfe4")
    draw = ImageDraw.Draw(sheet)
    for column in range(5):
        for row, presentation in enumerate(("normal", "closeup")):
            crop = Image.open(evidence / f"arm_{presentation}_elbow_{column:02d}.png").convert("RGBA")
            left, top = column * 420, 30 if row == 0 else 530
            sheet.paste(crop, (left, top), crop)
            draw.text((left + 12, top - 22), f"Two pieces | elbow +{column * 5} deg | {presentation}", fill="#202831")
    sheet.save(evidence / "arm-two-piece-comparison.png")
    mobile = Image.new("RGB", (810, 1590), "#d9dfe4")
    draw = ImageDraw.Draw(mobile)
    for row, presentation in enumerate(("390x844", "405x720", "540x960")):
        for column in range(3):
            crop = Image.open(evidence / f"arm_{presentation}_demo_{column:02d}.png").convert("RGBA")
            crop.thumbnail((260, 500))
            left, top = column * 270, row * 530
            mobile.paste(crop, (left + (270 - crop.width) // 2, top + 30), crop)
            draw.text((left + 10, top + 8), f"{presentation} | native t={column * .5:g}s", fill="#202831")
    mobile.save(evidence / "arm-mobile-key-poses.png")
    return {"capture_count": len(captures), "elbow_delta_degrees": [0, 5, 10, 15, 20],
            "native_demo_times": [0, .5, 1, 1.5, 2], "alpha_threshold": 128,
            "return_to_rest_pixel_identical": True, "captures": captures,
            "mobile_viewports": [[390, 844], [405, 720], [540, 960]],
            "contact_sheet": "arm-two-piece-comparison.png", "mobile_contact_sheet": "arm-mobile-key-poses.png"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True)
    parser.add_argument("--authored-scene", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    assets = repository / "addons/lunitora_godot/test_assets/rig_test_cat"
    source_hashes = {path: digest(path) for path in assets.rglob("*") if path.is_file()}
    body_alignment = verify_body_alignment(repository)
    scarf_spec = verify_scarf_spec(repository)
    scene_hash = digest(args.authored_scene)
    project = Path(tempfile.mkdtemp(prefix="lunitora-v05-public-gpu-"))
    shutil.copytree(assets, project / assets.relative_to(repository))
    shutil.copy2(args.authored_scene, project / "authored.tscn")
    shutil.copy2(Path(__file__).with_name("deformation_gpu_validation.gd"), project / "oracle.gd")
    spec_path = repository / "addons/lunitora_godot/specs/rig_test_cat_deformation_v1.json"
    shutil.copy2(spec_path, project / "fixture_spec.json")
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Public v0.5 deformation oracle"\n'
        '[rendering]\nrenderer/rendering_method="mobile"\nrendering_device/driver.windows="d3d12"\n', encoding="utf-8")
    env = dict(os.environ)
    env["APPDATA"] = str(project / "userdata")
    env["LOCALAPPDATA"] = str(project / "cache")
    for label, command in (
        ("import", [args.godot, "--headless", "--path", str(project), "--editor", "--import", "--quit"]),
        ("graphical", [args.godot, "--path", str(project), "--position", "-10000,-10000", "--script", "res://oracle.gd"]),
    ):
        completed = subprocess.run(command, env=env, capture_output=True, timeout=args.timeout)
        output = completed.stdout + completed.stderr
        (project / (label + ".log")).write_bytes(output)
        if completed.returncode or any(token in output for token in (b"SCRIPT ERROR", b"ERROR:", b"WARNING:")):
            raise RuntimeError(f"{label} native run failed: {project}\n{output.decode(errors='replace')}")
    evidence = project / "gpu_evidence"
    report = json.loads((evidence / "result.json").read_text())
    scarf_captures = verify_scarf_captures(evidence, report)
    arm_captures = verify_arm_captures(evidence, report)
    if (report["renderer"], report["driver"]) != ("mobile", "d3d12"):
        raise RuntimeError("GPU proof used an unexpected renderer")
    comparisons = []
    for prefix, count in (("amplitude", 21), ("animation", 65)):
        for index in range(count):
            gpu = np.asarray(Image.open(evidence / f"{prefix}_gpu_{index:02d}.png").convert("RGBA"), dtype=np.int16)
            cpu = np.asarray(Image.open(evidence / f"{prefix}_cpu_{index:02d}.png").convert("RGBA"), dtype=np.int16)
            delta = np.abs(gpu - cpu)
            # Transparent RGB is immaterial to visible output.
            delta[(gpu[:, :, 3] == 0) & (cpu[:, :, 3] == 0), :3] = 0
            if delta.max() > 8 or delta.mean() > .01:
                raise RuntimeError(f"GPU/CPU oracle mismatch {prefix} {index}: {delta.max()}, {delta.mean()}")
            comparisons.append({"fixture": prefix, "index": index,
                                "max_difference_255": int(delta.max()), "mean_difference_255": float(delta.mean())})
    rest = np.asarray(Image.open(evidence / "rest.png"))
    reattached = np.asarray(Image.open(evidence / "reattached.png"))
    detached = np.asarray(Image.open(evidence / "detached.png"))
    if not np.array_equal(rest, reattached) or np.any(detached[:, :, 3]):
        raise RuntimeError("Detached render state did not clear/restore exactly")
    if not (.6 < report["min_area_ratio"] <= 1 <= report["max_area_ratio"] < 1.4
            and .7 < report["min_edge_ratio"] <= 1 <= report["max_edge_ratio"] < 1.4
            and report["rest_error_px"] == 0):
        raise RuntimeError("Approved deformation geometry envelope was exceeded")
    if (source_hashes != {path: digest(path) for path in source_hashes}
            or digest(args.authored_scene) != scene_hash or digest(spec_path) != scarf_spec["spec_sha256"]):
        raise RuntimeError("Public fixture inputs changed during rendering")
    # CPU oracle is calculated separately from AnimationPlayer's interpolation.
    # Native wrapped-angle values and articulated transforms are checked at all 65 times.
    max_angle_error = 0.0
    max_head_error = 0.0
    max_arm_origin_error = 0.0
    max_arm_basis_error = 0.0
    for sample in report["animation_samples"]:
        for actual, degrees in zip(sample["rotations"], (2, 4, 6, 6)):
            expected = np.deg2rad(degrees * sample["amplitude"])
            error = abs((actual - expected + np.pi) % (2 * np.pi) - np.pi)
            max_angle_error = max(max_angle_error, error)
        time = sample["time"]
        segment = min(int(time / .5), 3)
        u = (time - segment * .5) / .5
        q = 2 * u * u if u < .5 else 1 - 2 * (1 - u) ** 2
        shoulder = np.deg2rad([0, 12, 6, 3, 0])
        elbow = .87026 + np.deg2rad([0, 10, 20, 10, 0])
        for key, values in (("shoulder", shoulder), ("elbow", elbow)):
            expected = values[segment] + q * (values[segment + 1] - values[segment])
            error = abs((sample[key] - expected + np.pi) % (2 * np.pi) - np.pi)
            max_angle_error = max(max_angle_error, error)
        expected_shoulder = shoulder[segment] + q * (shoulder[segment + 1] - shoulder[segment])
        expected_elbow = elbow[segment] + q * (elbow[segment + 1] - elbow[segment])
        # Independent native-global oracle: authored scene placement (30,30),
        # station placement (900,160), inherited .5*.4 scale, and scaled elbow
        # position. This checks actual Node2D global bases, not declared locals.
        cosine, sine = math.cos(expected_shoulder), math.sin(expected_shoulder)
        expected_origin = np.asarray([930 - 77 * cosine - 136 * sine,
                                      190 - 77 * sine + 136 * cosine])
        for key, angle in (("arm_elbow_global", expected_shoulder + expected_elbow),
                           ("arm_lower_global", expected_shoulder + expected_elbow - .87026)):
            actual = sample[key]
            expected_x = .2 * np.asarray([math.cos(angle), math.sin(angle)])
            expected_y = .2 * np.asarray([-math.sin(angle), math.cos(angle)])
            max_arm_origin_error = max(max_arm_origin_error, float(np.max(np.abs(actual["origin"] - expected_origin))))
            max_arm_basis_error = max(max_arm_basis_error,
                                      float(np.max(np.abs(actual["x"] - expected_x))),
                                      float(np.max(np.abs(actual["y"] - expected_y))))
        head = [306, 300, 294, 300, 306]
        expected = head[segment] + q * (head[segment + 1] - head[segment])
        max_head_error = max(max_head_error, abs(sample["head_y"] - expected))
    if max_angle_error > 1e-6 or max_head_error != 0:
        raise RuntimeError("Native -2 easing differs from the approved CPU interpolation oracle")
    if max_arm_origin_error > 1e-4 or max_arm_basis_error > 1e-6:
        raise RuntimeError(f"Native inherited arm transform differs from CPU articulation: "
                           f"origin={max_arm_origin_error}, basis={max_arm_basis_error}")
    report.update({"authored_scene_sha256": scene_hash, "source_import_files_preserved": len(source_hashes),
                   "gpu_cpu_comparisons": comparisons, "detached_render_cleared": True,
                   "reattached_rest_pixel_identical": True, "max_wrapped_angle_error_rad": max_angle_error,
                   "max_head_y_error_px": max_head_error, "body_alignment": body_alignment,
                   "scarf_spec": scarf_spec, "scarf_graphical": scarf_captures,
                   "arm_graphical": arm_captures, "arm_global_transform_samples": len(report["animation_samples"]),
                   "max_arm_global_origin_error_px": max_arm_origin_error,
                   "max_arm_global_basis_error": max_arm_basis_error})
    frames = [Image.open(evidence / f"combined_{index:02d}.png").convert("RGBA") for index in range(65)]
    frames[0].save(evidence / "combined-demo.gif", save_all=True, append_images=frames[1:], duration=31, loop=0, disposal=2)
    (project / "verified-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifacts": str(project), "gpu_cpu_samples": len(comparisons),
                      "max_difference_255": max(item["max_difference_255"] for item in comparisons),
                      "max_mean_difference_255": max(item["mean_difference_255"] for item in comparisons),
                      "cpu_geometry_poses": report["cpu_poses"], "min_area_ratio": report["min_area_ratio"],
                      "max_area_ratio": report["max_area_ratio"], "min_edge_ratio": report["min_edge_ratio"],
                      "max_edge_ratio": report["max_edge_ratio"], "max_wrapped_angle_error_rad": max_angle_error,
                      "max_head_y_error_px": max_head_error, "body_alignment": body_alignment,
                      "scarf_spec": scarf_spec, "scarf_graphical": scarf_captures,
                      "arm_graphical": arm_captures, "arm_global_transform_samples": len(report["animation_samples"]),
                      "max_arm_global_origin_error_px": max_arm_origin_error,
                      "max_arm_global_basis_error": max_arm_basis_error}, indent=2))


if __name__ == "__main__":
    main()
