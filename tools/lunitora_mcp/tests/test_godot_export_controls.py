"""Bounds/allowlists for retained native export controls; packs are proven natively."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

EXPORT_SCRIPT = Path(__file__).resolve().parents[3] / "tests/godot_mcp/export_validation.py"
_spec = importlib.util.spec_from_file_location("godot_export_controls", EXPORT_SCRIPT)
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)
REPOSITORY = Path(__file__).resolve().parents[3]


def authored_scene():
    textures = sorted({"res://" + export.TOLINA_TEXTURE_PREFIX + value[0]
                       for value in export.TOLINA_TEXTURE_NODES.values()})
    text = '[gd_scene load_steps=18 format=3 uid="uid://native_export_control"]\n\n'
    for index, path in enumerate(textures):
        text += f'[ext_resource type="Texture2D" path="{path}" id="{index}"]\n'
    text += '[sub_resource type="Animation" id="Animation_blink"]\nresource_name = "blink"\n'
    text += '[sub_resource type="AnimationLibrary" id="Library_blink"]\n_data = {"blink": SubResource("Animation_blink")}\n'
    text += '[node name="TolinaCharacterRigLab" type="Node2D" unique_id=42]\n'
    text += '[node name="TolinaRig" type="Node2D" parent="."]\n'
    text += '[node name="Visual" type="Node2D" parent="TolinaRig"]\n'
    text += '[node name="Arms" type="Node2D" parent="TolinaRig/Visual"]\n'
    text += '[node name="Eyes" type="Node2D" parent="TolinaRig/Visual"]\n'
    for piece in export.TOLINA_TEXTURE_NODES:
        parent, name = piece.rsplit("/", 1) if "/" in piece else ("", piece)
        parent = "TolinaRig/Visual" + ("/" + parent if parent else "")
        text += f'[node name="{name}" type="Sprite2D" parent="{parent}"]\n'
    text += '[node name="AnimationPlayer" type="AnimationPlayer" parent="TolinaRig"]\n'
    return text


def authored_deformation_scene():
    """Structural allowlist fixture; native package tests prove full semantics."""
    text = '[gd_scene load_steps=9 format=3 uid="uid://deformation_control"]\n\n'
    textures = sorted({"res://" + export.DEFORMATION_TEXTURE_PREFIX + row[0]
                       for row in export.DEFORMATION_TEXTURE_NODES.values()})
    for index, path in enumerate(textures):
        text += f'[ext_resource type="Texture2D" path="{path}" id="{index}"]\n'
    text += '[sub_resource type="Animation" id="Animation_demo"]\nresource_name = "deformation_demo"\n'
    text += '[sub_resource type="AnimationLibrary" id="Library_demo"]\n_data = {"deformation_demo": SubResource("Animation_demo")}\n'
    for path, native_class in export.DEFORMATION_NODE_CLASSES.items():
        if path == "RigTestCatDeformationLab":
            text += f'[node name="{path}" type="{native_class}" unique_id=42]\n'
        else:
            parent, name = path.rsplit("/", 1) if "/" in path else (".", path)
            text += f'[node name="{name}" type="{native_class}" parent="{parent}"]\n'
            if path in {"RigTestCatRig/BodyStation/Torso", "RigTestCatRig/BodyStation/ScarfForeground"}:
                texture_path = "res://" + export.DEFORMATION_TEXTURE_PREFIX + export.DEFORMATION_TEXTURE_NODES[path.removeprefix("RigTestCatRig/")][0]
                text += f'texture = ExtResource("{textures.index(texture_path)}")\n'
    return text


class ExportControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lunitora-export-control-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        (self.project / export.ADDON / "labs").mkdir(parents=True)
        self.source = self.root / "native-saved.tscn"

    def admit(self, text):
        self.source.write_text(text, encoding="utf-8")
        return export.copy_authored_tolina_lab(self.source, self.project)

    def test_deformation_export_retains_24_assets_with_exported_scarf_and_four_full_canvas_arm_inputs(self):
        fixture = json.loads((REPOSITORY / export.ADDON / export.DEFORMATION_SPEC_CONTROL).read_text(encoding="utf-8"))
        textures = {row["id"]: row for row in fixture["textures"]}
        self.assertEqual(len(textures), 24)
        for name in ("arm_upper_l", "arm_upper_r", "arm_lower_paw_l", "arm_lower_paw_r"):
            self.assertEqual(textures[name]["size_px"], [1254, 1254], name)
        self.assertIn("head_full", textures)
        self.assertIn("cape", textures)
        scarf = textures["scarf_foreground"]
        self.assertEqual(scarf["size_px"], [288, 147])
        self.assertEqual(scarf["path"], "res://" + export.DEFORMATION_TEXTURE_PREFIX + "body/rig_test_cat_scarf_foreground.png")
        self.assertEqual(scarf["source_sha256"], "b76534ce925d736de66ad5d74ee163780968a3c63a3a5c8af02e7dd993aff4d3")
        self.assertEqual(scarf["import_sha256"], "cb6b770b4ef34f80bb7a0a23e89977e4383c9104d9266c98ded3963a4afc485d")
        self.assertFalse({"head_main", "neck_under_scarf", "arm_elbow_sleeve_overlap_l",
                          "arm_elbow_sleeve_overlap_r"} & textures.keys())
        for path in ("ArmStation/Shoulder/UpperArm", "ArmStation/Shoulder/UpperArm/Elbow/LowerArmPaw"):
            self.assertEqual(export.DEFORMATION_TEXTURE_NODES[path][1], [1254, 1254])

    def test_normal_scene_and_node_uid_metadata_is_accepted_without_rewriting(self):
        record = self.admit(authored_scene())
        self.assertEqual(record["node_count"], 22)
        self.assertEqual(record["external_texture_count"], 15)
        self.assertEqual(record["inline_resource_count"], 2)
        self.assertTrue(record["no_json_runtime_dependency"])
        destination = self.project / export.ADDON / export.ADDON_SCENE_CONTROLS[1]
        self.assertEqual(destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(record["sha256"], hashlib.sha256(destination.read_bytes()).hexdigest())

    def test_unapproved_external_inputs_and_duplicate_references_reject(self):
        source = authored_scene()
        path = "res://" + export.TOLINA_TEXTURE_PREFIX + "body/cat_totolina_body.png"
        for altered in (source.replace(path, "res://production/unapproved.png"),
                        source.replace('type="Texture2D"', 'type="Texture"', 1),
                        source.replace(path, "res://" + export.TOLINA_TEXTURE_PREFIX + "ears/cat_totolina_ear_left.png"),
                        source + '[ext_resource type="Texture2D" path="res://other.png" id="other"]\n'):
            with self.subTest(altered=altered[:80]), self.assertRaises(RuntimeError):
                self.admit(altered)

    def test_wrong_structure_scripts_json_or_extra_resources_reject(self):
        source = authored_scene()
        for altered in (source.replace('name="TolinaCharacterRigLab"', 'name="Production"'),
                        source.replace('name="EarLeft" type="Sprite2D"', 'name="EarLeft" type="Node2D"'),
                        source + '[node name="Extra" type="Node" parent="TolinaRig"]\n',
                        source + 'script = ExtResource("other")\n',
                        source + 'metadata/spec = "res://addons/lunitora_godot/specs/other.json"\n',
                        source + '[sub_resource type="Resource" id="Other"]\n'):
            with self.subTest(altered=altered[-80:]), self.assertRaises(RuntimeError):
                self.admit(altered)

    def test_old_synthetic_inline_control_does_not_accept_external_texture_fixture(self):
        self.source.write_text(authored_scene(), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            export.copy_authored_lab(self.source, self.project)

    def test_native_deformation_identity_metadata_and_exact_external_inputs_are_accepted(self):
        self.source.write_text(authored_deformation_scene(), encoding="utf-8")
        record = export.copy_authored_deformation_lab(self.source, self.project)
        self.assertEqual(record["node_count"], 20)
        self.assertTrue(record["distinct_scarf_texture_reference"])
        self.assertEqual(record["external_texture_count"], 6)
        self.assertEqual(record["inline_resource_count"], 2)
        self.assertTrue(record["no_json_runtime_dependency"])
        self.assertEqual(record["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        destination = self.project / export.ADDON / export.ADDON_SCENE_CONTROLS[2]
        self.assertEqual(destination.read_bytes(), self.source.read_bytes())

    def test_authored_deformation_rejects_unapproved_nodes_resources_and_runtime_json(self):
        text = authored_deformation_scene()
        path = "res://" + export.DEFORMATION_TEXTURE_PREFIX + "tail/rig_test_cat_tail.png"
        for altered in (text.replace('name="RigTestCatDeformationLab"', 'name="Production"'),
                        text.replace('name="TailMesh" type="Polygon2D"', 'name="TailMesh" type="Sprite2D"'),
                        text.replace('name="ScarfForeground" type="Sprite2D"', 'name="ScarfForeground" type="Polygon2D"'),
                        text + '[node name="Extra" type="Node2D" parent="RigTestCatRig"]\n',
                        text + '[node name="TailStation" type="Node2D" parent="RigTestCatRig"]\n',
                        text.replace(path, "res://assets/production/unapproved.png"),
                        text.replace('type="Texture2D"', 'type="Texture"', 1),
                        text + '[sub_resource type="Resource" id="Unexpected"]\n',
                        text + 'script = ExtResource("Unexpected")\n',
                        text + 'metadata/spec = "res://addons/lunitora_godot/specs/runtime.json"\n'):
            self.source.write_text(altered, encoding="utf-8")
            with self.subTest(altered=altered[-100:]), self.assertRaises(RuntimeError):
                export.copy_authored_deformation_lab(self.source, self.project)

    def test_authored_deformation_scarf_requires_its_distinct_external_texture_reference(self):
        text = authored_deformation_scene()
        header = '[node name="ScarfForeground" type="Sprite2D" parent="RigTestCatRig/BodyStation"]\n'
        before, scarf = text.split(header, 1)
        reference, after = scarf.split("\n", 1)
        torso_header = '[node name="Torso" type="Sprite2D" parent="RigTestCatRig/BodyStation"]\n'
        torso_reference = text.split(torso_header, 1)[1].split("\n", 1)[0]
        swapped = before.replace(torso_header + torso_reference, torso_header + reference) + header + torso_reference + "\n" + after
        for altered in (before + header + after,
                        before + header + 'texture = ExtResource("unknown")\n' + after,
                        before + header + torso_reference + "\n" + after,
                        before + header + reference + "\n" + reference + "\n" + after,
                        before + header + 'texture = SubResource("private_texture")\n' + after,
                        swapped):
            self.source.write_text(altered, encoding="utf-8")
            with self.subTest(altered=altered[-100:]), self.assertRaises(RuntimeError):
                export.copy_authored_deformation_lab(self.source, self.project)

    def test_authored_deformation_artifact_size_is_bounded(self):
        for content in (b"", b"#" * (1024 * 1024 + 1)):
            self.source.write_bytes(content)
            with self.subTest(size=len(content)), self.assertRaises(RuntimeError):
                export.copy_authored_deformation_lab(self.source, self.project)

    def texture_pack(self, filename, *, change_payload=None, omit_payload=None, change_import=None):
        destination = self.root / filename
        paths = {export.TOLINA_TEXTURE_PREFIX + value[0] for value in export.TOLINA_TEXTURE_NODES.values()}
        with zipfile.ZipFile(destination, "w") as package:
            for index, path in enumerate(sorted(paths)):
                target = f".godot/imported/texture-{index}.ctex"
                imported = f'[remap]\npath="res://{target}"\n'.encode()
                if change_import == index:
                    imported += b"# altered\n"
                package.writestr(path + ".import", imported)
                if omit_payload != index:
                    package.writestr(target, b"altered" if change_payload == index else f"native-payload-{index}".encode())
        return destination

    def test_production_texture_payload_comparison_requires_all_fifteen_identical(self):
        excluded = self.texture_pack("excluded.zip")
        control = self.texture_pack("control.zip")
        digests = export.compare_tolina_texture_payloads(excluded, control)
        self.assertEqual(len(digests), 15)
        for variation in ({"change_payload": 2}, {"omit_payload": 2}, {"change_import": 2}):
            changed = self.texture_pack("changed.zip", **variation)
            with self.subTest(variation=variation), self.assertRaises(RuntimeError):
                export.compare_tolina_texture_payloads(excluded, changed)

    def test_diagnostic_pack_removes_only_json_and_any_json_remap_target(self):
        control = self.root / "control.zip"
        diagnostic = self.root / "diagnostic.zip"
        with zipfile.ZipFile(control, "w") as package:
            for index, relative in enumerate(export.ADDON_SPEC_CONTROLS):
                manifest = export.ADDON + relative
                target = f".godot/exported/reviewed-manifest-{index}.res"
                package.writestr(manifest, b'{"tooling_only":true}')
                package.writestr(manifest + ".remap", f'path="res://{target}"\n')
                package.writestr(target, b"manifest payload")
            package.writestr("assets/production.ctex", b"texture payload")
            package.writestr(export.ADDON + "labs/control.scn", b"native scene payload")
        export.without_editor_json(control, diagnostic)
        with zipfile.ZipFile(diagnostic) as package:
            self.assertEqual(set(package.namelist()), {"assets/production.ctex", export.ADDON + "labs/control.scn"})
            self.assertEqual(package.read("assets/production.ctex"), b"texture payload")

    def positive_addon_pack(self, filename, *, omit_import=None, omit_payload=None):
        """Exercise source/remap and imported-resource controls independently."""
        spec = json.loads((REPOSITORY / export.ADDON / export.DEFORMATION_SPEC_CONTROL).read_text(encoding="utf-8"))
        textures = spec["textures"]
        self.assertEqual(len(textures), 24)
        destination = self.root / filename
        controls = (*export.ADDON_SCRIPT_CONTROLS, *export.ADDON_SCENE_CONTROLS, *export.ADDON_SPEC_CONTROLS)
        with zipfile.ZipFile(destination, "w") as package:
            package.writestr("keep.tres", b"runtime control")
            package.writestr(export.ADDON + "export_probe.tres", b"addon control")
            package.writestr(export.ADDON + "nested/export_probe.tres", b"nested addon control")
            for index, relative in enumerate(controls):
                target = f".godot/exported/addon-control-{index}.res"
                package.writestr(export.ADDON + relative + ".remap", f'path="res://{target}"\n')
                package.writestr(target, b"native addon payload")
            for index, texture in enumerate(textures):
                source = texture["path"].removeprefix("res://")
                self.assertTrue(source.startswith(export.DEFORMATION_TEXTURE_PREFIX))
                target = f".godot/imported/deformation-texture-{index}.ctex"
                if omit_import != index:
                    package.writestr(source + ".import", f'[remap]\npath="res://{target}"\n')
                if omit_payload != index:
                    package.writestr(target, b"native texture payload")
        return destination, textures

    def test_all_three_scenes_both_specs_new_scripts_and_24_texture_controls_are_required(self):
        control, textures = self.positive_addon_pack("all-addon-controls.zip")
        verified = export.verify_zip(control, excluded=False)
        controls = verified["actual_addon_resource_controls"]
        for relative in (*export.ADDON_SCRIPT_CONTROLS, *export.ADDON_SCENE_CONTROLS, *export.ADDON_SPEC_CONTROLS):
            self.assertIn(relative, controls)
        for texture in textures:
            relative = texture["path"].removeprefix("res://" + export.ADDON)
            self.assertIn(relative, controls)
        self.assertEqual(len(controls), 37)
        for variation in ({"omit_import": 3}, {"omit_payload": 3}):
            malformed, _ = self.positive_addon_pack("missing-texture-control.zip", **variation)
            with self.subTest(variation=variation), self.assertRaises(RuntimeError):
                export.verify_zip(malformed, excluded=False)

    def test_exclusion_checks_import_targets_outside_the_addon_directory(self):
        control, _ = self.positive_addon_pack("addon-import-targets.zip")
        excluded = self.root / "excluded.zip"
        with zipfile.ZipFile(excluded, "w") as package:
            package.writestr("keep.tres", b"runtime control")
        export.verify_zip(excluded, excluded=True)
        self.assertEqual(export.compare_packages(excluded, control), 37)
        with zipfile.ZipFile(excluded, "a") as package:
            package.writestr(".godot/imported/deformation-texture-3.ctex", b"leaked texture")
        # The compiled payload has no addon prefix. Correlation to the positive
        # import control must still catch it rather than trusting prefix checks.
        with self.assertRaises(RuntimeError):
            export.compare_packages(excluded, control)


if __name__ == "__main__":
    unittest.main(verbosity=2)
