"""Deferred repairs inspect readiness without mutating machine configuration."""
from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import bootstrap, configuration, integration
from lunitora_machine.readiness import summarize
from test_lunitora_setup import Fixture


def status():
    return {"ready": True, "state": "already correct", "reason": "verified fixture"}


class DeferredReadinessTests(Fixture):
    def prepare_configured_game(self):
        data = configuration.empty_config(self.root, "windows")
        for kind in ("godot", "desktop"):
            app = self.app(kind)
            data["applications"][kind] = app
            self.platform.valid[app["path"]] = app
        configuration.save_config(self.root, data)
        configuration.configure_aliases(self.root, "windows", runner=self.runner)
        return data

    def pending(self, *, safe=True):
        return {"ready": False, "state": "update deferred", "reason": "environment mutation deferred",
                "inspection_ready": safe, "deferred": True, "python": "C:\\Test Python\\python.exe"}

    def auth_context(self):
        return patch.object(integration, "provision_authentication", return_value={"godot": status()})

    def test_normal_deferred_repair_is_readonly_and_reports_partial_existing_game(self):
        self.prepare_configured_game()
        before = self.snapshot()
        self.calls.clear()
        output = []
        with patch.object(bootstrap, "ensure_environment", return_value=self.pending()), \
                patch.object(integration, "provision_codex", return_value={"godot": status()}) as codex, \
                self.auth_context() as auth, patch.object(bootstrap, "save_config") as save:
            result = bootstrap.bootstrap(self.root, self.platform, runner=self.runner, emit=output.append,
                                         prompt=lambda _: self.fail("Deferred setup prompted"),
                                         secret_prompt=lambda _: self.fail("Deferred setup requested a secret"))
        self.assertEqual(result, 1)
        self.assertTrue(codex.call_args.kwargs["check"])
        self.assertTrue(auth.call_args.kwargs["check"])
        self.assertFalse(auth.call_args.kwargs["interactive"])
        save.assert_not_called()
        self.assertEqual(before, self.snapshot())
        text = "\n".join(output)
        self.assertIn("Core: PARTIAL", text)
        self.assertIn("Game: PARTIAL", text)
        self.assertIn("local configuration: READY", text)
        self.assertNotIn("Godot is not configured", text)
        self.assertNotIn("Core: MISSING", text)
        self.assertFalse(any("--replace-all" in command for command in self.calls))

    def test_deferred_and_check_use_identical_capability_classification(self):
        self.prepare_configured_game()
        state = self.pending()
        outputs = []
        with patch.object(integration, "provision_codex", return_value={"godot": status()}), self.auth_context():
            for options in ({"deferred": True}, {"check": True}):
                output = []
                bootstrap.bootstrap(self.root, self.platform, runner=self.runner, emit=output.append,
                                    environment_state=state, **options)
                outputs.append(output[output.index("Capability readiness (configuration only; not live acceptance):"):])
        self.assertEqual(outputs[0], outputs[1])

    def test_proven_deferred_state_is_inspected_in_host_without_venv_worker(self):
        state = self.pending()
        with patch.object(bootstrap, "__file__", str(self.root / "tools/lunitora_machine/bootstrap.py")), \
                patch.object(bootstrap, "validate_repository"), \
                patch.object(bootstrap, "platform_name", return_value="windows"), \
                patch.object(bootstrap, "validated_host", return_value=bootstrap.sys.executable), \
                patch.object(bootstrap, "ensure_environment", return_value=state), \
                patch.object(bootstrap.sys, "prefix", bootstrap.sys.base_prefix), \
                patch.object(bootstrap, "get_platform", return_value=self.platform), \
                patch.object(bootstrap, "bootstrap", return_value=1) as inspect, \
                patch("subprocess.run") as worker, patch("builtins.print"):
            self.assertEqual(bootstrap.main([]), 1)
        worker.assert_not_called()
        self.assertTrue(inspect.call_args.kwargs["deferred"])
        self.assertEqual(inspect.call_args.kwargs["environment_state"], state)
        self.assertEqual(inspect.call_args.kwargs["host_python"], bootstrap.sys.executable)

    def test_host_worker_never_forwards_into_managed_venv(self):
        self.prepare_configured_game()
        host = "C:\\Standalone Python\\python.exe"
        with patch.object(bootstrap, "__file__", str(self.root / "tools/lunitora_machine/bootstrap.py")), \
                patch.object(bootstrap, "validate_repository"), \
                patch.object(bootstrap, "platform_name", return_value="windows"), \
                patch.object(bootstrap, "validated_host", return_value=host), \
                patch.object(bootstrap, "ensure_environment", return_value=self.pending()) as environment, \
                patch.object(bootstrap.sys, "executable", host), \
                patch.object(bootstrap.sys, "prefix", "C:\\Standalone Python"), \
                patch.object(bootstrap.sys, "base_prefix", "C:\\Standalone Python"), \
                patch.object(bootstrap, "get_platform", return_value=self.platform), \
                patch.object(bootstrap, "bootstrap", return_value=1) as inspect, \
                patch("subprocess.run") as worker, patch("builtins.print"):
            self.assertEqual(bootstrap.main(["--_host-worker"]), 1)
        worker.assert_not_called()
        self.assertFalse(environment.call_args.kwargs["check"])
        self.assertEqual(environment.call_args.kwargs["host_python"], host)
        self.assertTrue(inspect.call_args.kwargs["deferred"])
        self.assertEqual(inspect.call_args.kwargs["environment_state"], self.pending())

    def test_deferred_pairing_never_passes_replacement_to_authentication(self):
        self.prepare_configured_game()
        output = []
        with patch.object(integration, "provision_codex", return_value={"godot": status()}), self.auth_context() as auth:
            result = bootstrap.bootstrap(self.root, self.platform, runner=self.runner, emit=output.append,
                                         environment_state=self.pending(), deferred=True, replace_photoshop=True,
                                         secret_prompt=lambda _: self.fail("Deferred pairing prompted"))
        self.assertEqual(result, 1)
        self.assertFalse(auth.call_args.kwargs["replace_photoshop"])
        self.assertTrue(auth.call_args.kwargs["check"])
        self.assertTrue(any("Core/Game are unaffected" in line for line in output))

    def test_uninspectable_mcp_environment_does_not_hide_host_application_readiness(self):
        self.prepare_configured_game()
        state = self.pending(safe=False)
        output = []
        with patch.object(integration, "provision_codex", return_value={"godot": status()}), self.auth_context():
            self.assertEqual(bootstrap.bootstrap(self.root, self.platform, runner=self.runner,
                                                environment_state=state, deferred=True,
                                                emit=output.append), 1)
        text = "\n".join(output)
        self.assertIn("Core: PARTIAL", text)
        self.assertIn("Game: PARTIAL", text)
        self.assertIn("local configuration: READY", text)
        self.assertNotIn("Godot is not configured", text)

    def test_unknown_application_inspection_never_implies_missing_installations(self):
        states = summarize("windows", False, {}, applications_inspected=False,
                           environment_ready=False, environment_present=True)
        self.assertEqual(states["Core"]["state"], "PARTIAL")
        self.assertEqual(states["Game"]["state"], "NOT CHECKED")
        self.assertEqual(states["Art"]["state"], "NOT CHECKED")

    def test_photoshop_pairing_on_non_art_machine_preserves_ready_core_game(self):
        self.prepare_configured_game()
        output = []
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()), \
                patch.object(integration, "provision_codex", return_value={"godot": status()}), self.auth_context() as auth:
            result = bootstrap.bootstrap(self.root, self.platform, runner=self.runner, emit=output.append,
                                         interactive=False, replace_photoshop=True,
                                         secret_prompt=lambda _: self.fail("Missing Photoshop requested token"))
        self.assertEqual(result, 1)
        self.assertEqual(auth.call_args.args[2], ("godot",))
        text = "\n".join(output)
        self.assertIn("pairing: unavailable on this machine", text)
        self.assertIn("Core/Game are unaffected", text)
        self.assertIn("Core: READY", text)
        self.assertIn("Game: CONFIGURED", text)
        self.assertNotIn("Game: MISSING", text)

    def test_obsolete_managed_worker_flag_is_rejected_without_environment_access(self):
        with patch.object(bootstrap, "ensure_environment") as environment, patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            bootstrap.main(["--_inspect-deferred"])
        self.assertEqual(raised.exception.code, 2)
        environment.assert_not_called()
