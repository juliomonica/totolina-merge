"""Phase 4 orchestration/readiness without live configuration or applications."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import bootstrap, environment, integration
from lunitora_machine.readiness import summarize
from test_lunitora_setup import Fixture, result


def status(ready=True, state="already correct"):
    return {"ready": ready, "state": state, "reason": "non-secret fixture status"}


class IntegrationTests(Fixture):
    def configure(self, applications, configurations, authentications, **kwargs):
        emitted = []
        with patch.object(integration, "provision_codex", return_value=configurations) as config, \
             patch.object(integration, "provision_authentication", return_value=authentications) as auth:
            data = integration.configure_integration(self.root, "windows", applications, emit=emitted.append, **kwargs)
        return data, emitted, config, auth

    def test_missing_art_only_requests_game_integration(self):
        apps = {"godot": self.app("godot"), "photoshop": None}
        data, _, config, auth = self.configure(apps, {"godot": status()}, {"godot": status()})
        self.assertEqual(config.call_args.args[2], ("godot",))
        self.assertEqual(auth.call_args.args[2], ("godot",))
        self.assertTrue(integration.integration_success(data))

    def test_conflict_blocks_only_that_capability_and_its_credentials(self):
        apps = {key: self.app(key) for key in ("godot", "photoshop")}
        configurations = {"godot": status(False, "conflict"), "photoshop": status()}
        data, _, _, auth = self.configure(apps, configurations, {"photoshop": status()})
        self.assertEqual(auth.call_args.args[2], ("photoshop",))
        self.assertEqual(data["godot"]["authentication"]["state"], "not provisioned")
        self.assertTrue(data["photoshop"]["authentication"]["ready"])
        self.assertFalse(integration.integration_success(data))

    def test_user_disabled_server_never_provisions_authentication(self):
        data, _, _, auth = self.configure({"godot": self.app("godot")}, {"godot": status(False, "user restricted")}, {})
        self.assertEqual(auth.call_args.args[2], ())
        self.assertTrue(integration.integration_success(data))

    def test_check_reports_both_proposed_actions_without_writes(self):
        before = self.snapshot()
        data, emitted, config, auth = self.configure(
            {"godot": self.app("godot")}, {"godot": status(False, "creation available")},
            {"godot": status(False, "creation available")}, check=True)
        self.assertTrue(config.call_args.kwargs["check"])
        self.assertTrue(auth.call_args.kwargs["check"])
        self.assertTrue(any("creation available" in line for line in emitted))
        self.assertFalse(integration.integration_success(data, check=True))
        self.assertEqual(before, self.snapshot())

    def test_mac_auth_boundary_is_not_claimed_ready(self):
        data, _, _, _ = self.configure({"godot": self.app("godot")}, {"godot": status()}, {"godot": status(False, "REQUIRES MAC")})
        states = summarize("macos", True, {"godot": self.app("godot"), "desktop": self.app("desktop")}, integration=data)
        self.assertEqual(states["Core"]["authentication"], "REQUIRES MAC")
        self.assertEqual(states["Game"]["state"], "PARTIAL")
        self.assertEqual(states["Game"]["live_connection"], "NOT CHECKED")
        self.assertTrue(integration.integration_success(data))

    def test_ready_local_config_auth_is_not_live_acceptance(self):
        apps = {key: self.app(key) for key in ("godot", "desktop")}
        data, _, _, _ = self.configure(apps, {"godot": status()}, {"godot": status()})
        states = summarize("windows", True, apps, integration=data)
        self.assertEqual(states["Core"]["local_configuration"], "READY")
        self.assertEqual(states["Core"]["mcp_configuration"], "READY")
        self.assertEqual(states["Core"]["authentication"], "READY")
        self.assertEqual(states["Game"]["state"], "CONFIGURED")
        self.assertEqual(states["Game"]["live_connection"], "NOT CHECKED")
        self.assertEqual(states["Art"]["state"], "MISSING")

    def test_blocked_auth_does_not_make_local_core_missing(self):
        apps = {key: self.app(key) for key in ("godot", "desktop")}
        data, _, _, _ = self.configure(apps, {"godot": status()}, {"godot": status(False, "blocked")})
        states = summarize("windows", True, apps, integration=data)
        self.assertEqual(states["Core"]["state"], "READY")
        self.assertEqual(states["Core"]["authentication"], "PARTIAL / ACTION REQUIRED")
        self.assertEqual(states["Game"]["state"], "PARTIAL")
        self.assertFalse(integration.integration_success(data))

    def test_pending_dependency_does_not_misreport_valid_local_configuration(self):
        apps = {key: self.app(key) for key in ("godot", "desktop")}
        data, _, _, _ = self.configure(apps, {"godot": status()}, {"godot": status()})
        states = summarize("windows", False, apps, integration=data, local_ready=True, environment_ready=False)
        self.assertEqual(states["Core"]["state"], "PARTIAL")
        self.assertEqual(states["Core"]["local_configuration"], "READY")
        self.assertEqual(states["Core"]["python_environment"], "UPDATE / REPAIR REQUIRED")
        self.assertEqual(states["Game"]["mcp_configuration"], "already correct")

    def test_no_apps_does_not_provision_unrelated_credentials(self):
        data, _, config, auth = self.configure({}, {}, {})
        self.assertEqual(config.call_args.args[2], ())
        self.assertEqual(auth.call_args.args[2], ())
        states = summarize("windows", True, {}, integration=data)
        self.assertEqual(states["Core"]["mcp_configuration"], "NOT REQUESTED")
        self.assertTrue(integration.integration_success(data))

    def test_bootstrap_auth_failure_reports_partial_game_not_art_failure(self):
        self.platform.matches["godot"] = [self.app("godot")]
        self.platform.matches["desktop"] = [self.app("desktop")]
        emitted = []
        with patch.object(bootstrap, "ensure_environment", return_value=self.healthy()), \
             patch.object(integration, "provision_codex", return_value={"godot": status()}), \
             patch.object(integration, "provision_authentication", return_value={"godot": status(False, "blocked")}):
            code = bootstrap.bootstrap(self.root, self.platform, interactive=False, runner=self.runner, emit=emitted.append)
        self.assertEqual(code, 1)
        self.assertTrue(any("Core: READY" in line for line in emitted))
        self.assertTrue(any("Game: PARTIAL" in line for line in emitted))
        self.assertTrue(any("Art: MISSING" in line for line in emitted))

    def test_bootstrap_check_with_new_dependency_pending_is_readonly(self):
        self.platform.matches["godot"] = [self.app("godot")]
        pending = {"ready": False, "inspection_ready": True, "state": "dependency update available", "reason": "TOML package pending"}
        before = self.snapshot()
        with patch.object(bootstrap, "ensure_environment", return_value=pending), \
             patch.object(integration, "provision_codex", return_value={"godot": status(False, "creation available")}), \
             patch.object(integration, "provision_authentication", return_value={"godot": status(False, "creation available")}):
            code = bootstrap.bootstrap(self.root, self.platform, check=True, runner=self.runner, emit=lambda _: None)
        self.assertEqual(code, 1)
        self.assertEqual(before, self.snapshot())

    def test_readonly_handoff_uses_validated_host_without_venv_or_toml_dependency(self):
        pending = {"ready": False, "inspection_ready": True, "state": "dependency update available", "reason": "TOML package pending", "python": "C:\\Test Python\\python.exe"}
        host = "C:\\Standalone Python\\Python312\\python.exe"
        with patch.object(bootstrap, "__file__", str(self.root / "tools/lunitora_machine/bootstrap.py")), \
             patch.object(bootstrap, "validate_repository"), patch.object(bootstrap, "platform_name", return_value="windows"), \
             patch.object(bootstrap, "validated_host", return_value=host), \
             patch.object(bootstrap, "ensure_environment", return_value=pending) as environment_setup, \
             patch("subprocess.run", return_value=SimpleNamespace(returncode=1)) as spawn, patch("builtins.print"):
            self.assertEqual(bootstrap.main(["--check"]), 1)
        command = spawn.call_args.args[0]
        self.assertEqual(command[0], host)
        self.assertIn("--check", command)
        self.assertIn("--_host-worker", command)
        self.assertIn("-S", command)
        self.assertNotIn(".venv", " ".join(command))
        environment_setup.assert_not_called()

    def test_incomplete_environment_still_allows_readonly_host_readiness_inspection(self):
        pending = {"ready": False, "inspection_ready": True, "state": "update deferred",
                   "reason": "managed MCP update deferred", "deferred": True}
        with patch.object(bootstrap, "validate_repository"), patch.object(bootstrap, "platform_name", return_value="windows"), \
             patch.object(bootstrap, "validated_host", return_value=bootstrap.sys.executable), \
             patch.object(bootstrap.sys, "prefix", bootstrap.sys.base_prefix), \
             patch.object(bootstrap, "ensure_environment", return_value=pending), \
             patch.object(bootstrap, "get_platform", return_value=self.platform), \
             patch.object(bootstrap, "bootstrap", return_value=1) as inspect, \
             patch("subprocess.run") as spawn, patch("builtins.print"):
            self.assertEqual(bootstrap.main([]), 1)
        spawn.assert_not_called()
        self.assertTrue(inspect.call_args.kwargs["deferred"])
        self.assertEqual(inspect.call_args.kwargs["environment_state"], pending)

    def test_corrupt_mcp_import_blocks_payload_readiness_but_allows_host_doctor(self):
        executable = environment.python_path(self.root, "windows")
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture")
        (executable.parents[1] / "pyvenv.cfg").write_text("include-system-site-packages = false\n", encoding="utf-8")
        metadata = {"version": [3, 12, 10], "bits": 64, "prefix": str(executable.parents[1]), "base_prefix": "C:\\Python312",
                    "packages": {"mcp": "2.2.0", "pywin32": "312"}}
        import json
        def runner(command):
            if command[-1] == environment.PROBE:
                return result(json.dumps(metadata))
            return result(returncode=1 if isinstance(command[-1], str) and command[-1].startswith("import mcp") else 0)
        state = environment.inspect_environment(self.root, "windows", runner)
        self.assertFalse(state["ready"])
        self.assertTrue(state["inspection_ready"])
