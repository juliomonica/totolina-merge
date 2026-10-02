"""Bounds/allowlists for retained native export controls; packs are proven natively."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

EXPORT_SCRIPT = Path(__file__).resolve().parents[3] / "tests/godot_mcp/export_validation.py"
_spec = importlib.util.spec_from_file_location("godot_export_controls", EXPORT_SCRIPT)
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)


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
        manifest = export.ADDON + export.ADDON_SPEC_CONTROL
        target = ".godot/exported/reviewed-manifest.res"
        with zipfile.ZipFile(control, "w") as package:
            package.writestr(manifest, b'{"tooling_only":true}')
            package.writestr(manifest + ".remap", f'path="res://{target}"\n')
            package.writestr(target, b"manifest payload")
            package.writestr("assets/production.ctex", b"texture payload")
            package.writestr(export.ADDON + "labs/control.scn", b"native scene payload")
        export.without_editor_json(control, diagnostic)
        with zipfile.ZipFile(diagnostic) as package:
            self.assertEqual(set(package.namelist()), {"assets/production.ctex", export.ADDON + "labs/control.scn"})
            self.assertEqual(package.read("assets/production.ctex"), b"texture payload")


if __name__ == "__main__":
    unittest.main(verbosity=2)
