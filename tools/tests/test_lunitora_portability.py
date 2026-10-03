"""Requirements, metadata-only mobile checks and explicit Mac boundaries."""
import io
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

from lunitora_machine.platforms.macos import MacPlatform
from lunitora_machine.policy import LauncherError
from lunitora_machine.prerequisites import inspect_prerequisites
from lunitora_machine.readiness import summarize

SOURCE = Path(__file__).absolute().parents[2]


class CatalogTests(unittest.TestCase):
    def test_external_apps_never_auto_install(self):
        data = json.loads((SOURCE / "tools/lunitora_requirements.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        for app in data["applications"]:
            self.assertEqual(app["policy"], "manual_install")
            for key in ("purpose", "platforms", "required_for", "optional_for", "version_policy", "action"):
                self.assertIn(key, app)
        python = next(item for item in data["prerequisites"] if item["id"] == "python")
        self.assertEqual(python["policy"], "manual_install")

    def test_catalog_source_references_exist(self):
        data = json.loads((SOURCE / "tools/lunitora_requirements.json").read_text(encoding="utf-8"))
        for item in (*data["applications"], *data["prerequisites"]):
            source = item.get("source", "")
            if source and not source.startswith("https://"):
                self.assertTrue((SOURCE / source).is_file(), source)

    def test_five_capabilities_optional_missing_not_core_failure(self):
        states = summarize("windows", True, {})
        self.assertEqual(list(states), ["Core", "Game", "Android", "iOS", "Art"])
        self.assertEqual(states["Core"]["state"], "READY")
        self.assertEqual(states["iOS"]["state"], "REQUIRES MAC")
        self.assertEqual(states["Game"]["state"], "MISSING")

    def test_android_metadata_is_not_device_proof(self):
        states = summarize("windows", True, {"godot": {"path": "fixture"}},
                           dict.fromkeys(("jdk", "android_sdk", "export_templates_android"), True))
        self.assertEqual(states["Android"]["state"], "CONFIGURED")
        self.assertIn("not tested", states["Android"]["reason"])


class MacTests(unittest.TestCase):
    def validate(self, kind, data):
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "stat") as stat, patch.object(Path, "open", return_value=io.BytesIO(plistlib.dumps(data))):
            stat.return_value.st_size = 100
            return MacPlatform().validate_application(kind, str(SOURCE / "Fixture.app"))

    def test_bundle_metadata_only(self):
        app = self.validate("godot", {"CFBundleIdentifier": "org.godotengine.godot", "CFBundleShortVersionString": "4.7.2"})
        self.assertEqual(app["kind"], "godot")
        self.assertEqual(app["version"], "4.7.2")

    def test_wrong_version_or_identity_rejected(self):
        for data in ({"CFBundleIdentifier": "org.godotengine.godot", "CFBundleShortVersionString": "4.8.0"}, {"CFBundleIdentifier": "other", "CFBundleShortVersionString": "4.7.2"}):
            with self.assertRaises(LauncherError):
                self.validate("godot", data)

    def test_photoshop_minimum_and_udt_identity(self):
        with self.assertRaises(LauncherError):
            self.validate("photoshop", {"CFBundleIdentifier": "com.adobe.Photoshop", "CFBundleShortVersionString": "27.9.0"})
        with self.assertRaises(LauncherError):
            self.validate("udt", {"CFBundleIdentifier": "com.adobe.Photoshop", "CFBundleShortVersionString": "27.10.0"})

    def test_every_native_control_refuses(self):
        platform = MacPlatform()
        for method, args in ((platform.processes, ()), (platform.port_owners, (43128,)), (platform.request_close, (None,)), (platform.stop_verified, (None,)), (platform.spawn_application, ({}, SOURCE))):
            with self.assertRaisesRegex(LauncherError, "REQUIRES MAC"):
                method(*args)

    def test_mac_readiness_does_not_claim_native_acceptance(self):
        states = summarize("macos", True, {"godot": {"path": "bundle"}, "photoshop": {"path": "bundle"}})
        self.assertIn("REQUIRES MAC", states["Game"]["reason"])
        self.assertIn("REQUIRES MAC", states["Art"]["reason"])


class PrerequisiteTests(unittest.TestCase):
    def test_inaccessible_templates_do_not_disable_core_game(self):
        original = Path.is_file
        def inspect(path):
            if path.name in ("android_debug.apk", "android_release.apk"):
                raise PermissionError("fixture access denied")
            return original(path)
        with patch.object(Path, "is_file", inspect):
            details = inspect_prerequisites(SOURCE, "windows", environ={"APPDATA": str(SOURCE)})
        self.assertIn("unavailable", details["export_templates_android"]["state"])
        states = summarize("windows", True, {"godot": {"path": "fixture"}, "desktop": {"path": "fixture"}}, details)
        self.assertEqual(states["Core"]["state"], "READY")
        self.assertEqual(states["Game"]["state"], "CONFIGURED")
        self.assertEqual(states["Android"]["state"], "NOT CONFIGURED")

    def test_non_dictionary_xcode_metadata_does_not_fail_inspection(self):
        original = Path.open
        def open_metadata(path, *args, **kwargs):
            if str(path).replace("\\", "/").endswith("Xcode.app/Contents/Info.plist"):
                return io.BytesIO(plistlib.dumps(["invalid metadata"]))
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", open_metadata):
            details = inspect_prerequisites(SOURCE, "macos", environ={})
        self.assertEqual(details["xcode"]["state"], "REQUIRES MAC")

    def test_ios_template_filename_metadata_remains_requires_mac(self):
        with tempfile.TemporaryDirectory(prefix="lunitora ios metadata ") as temp:
            home = Path(temp)
            templates = home / "Library/Application Support/Godot/export_templates/4.7.2.stable"
            templates.mkdir(parents=True)
            (templates / "ios.zip").write_bytes(b"metadata fixture, never exported")
            with patch.object(Path, "home", return_value=home):
                status = inspect_prerequisites(SOURCE, "macos", environ={})["export_templates_ios"]
            self.assertTrue(status["ready"])
            self.assertIn("REQUIRES MAC", status["state"])

    def test_missing_mobile_tools_readonly_and_nonblocking(self):
        with patch("shutil.which", return_value=None):
            states = inspect_prerequisites(SOURCE, "windows", environ={})
        self.assertFalse(states["jdk"]["ready"])
        self.assertFalse(states["android_sdk"]["ready"])
        self.assertEqual(states["xcode"]["state"], "REQUIRES MAC")

    def test_jdk_sdk_templates_from_disposable_metadata(self):
        with tempfile.TemporaryDirectory(prefix="lunitora SDK space ") as temp:
            root = Path(temp)
            jdk = root / "jdk17"
            (jdk / "bin").mkdir(parents=True)
            (jdk / "release").write_text('JAVA_VERSION="17.0.12"\n', encoding="ascii")
            for name in ("java.exe", "javac.exe"):
                (jdk / "bin" / name).write_bytes(b"metadata fixture, never executed")
            sdk = root / "sdk"
            for folder in ("platform-tools", "build-tools/35.0.1", "platforms/android-35", "cmdline-tools/latest"):
                (sdk / folder).mkdir(parents=True)
            (sdk / "platform-tools/adb.exe").write_bytes(b"fixture")
            (sdk / "platform-tools/source.properties").write_text("Pkg.Revision = 35.0.2\n", encoding="ascii")
            templates = root / "data/Godot/export_templates/4.7.2.stable"
            templates.mkdir(parents=True)
            for name in ("android_debug.apk", "android_release.apk"):
                (templates / name).write_bytes(b"fixture")
            before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
            states = inspect_prerequisites(SOURCE, "windows", environ={"JAVA_HOME": str(jdk), "ANDROID_HOME": str(sdk), "APPDATA": str(root / "data")})
            self.assertTrue(all(states[key]["ready"] for key in ("jdk", "android_sdk", "export_templates_android")))
            self.assertEqual(before, {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
