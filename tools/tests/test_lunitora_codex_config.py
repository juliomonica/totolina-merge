"""Disposable project MCP configuration/ownership safety coverage."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from lunitora_machine import codex_config as subject
from lunitora_machine import structural_toml
from lunitora_machine.configuration import ConfigurationError


def fixture_toml(data):
    return "\n".join(structural_toml._render_entry(name, entry, "\n")
                     for name, entry in data.get("mcp_servers", {}).items())


class CodexConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lunitora codex config ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "checkout with spaces"
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.user_config = Path(self.temporary.name) / "user codex" / "config.toml"
        self.calls = []
        self.tracked = set()
        self.not_ignored = set()

    def runner(self, command):
        self.calls.append(command)
        self.assertEqual(command[:3], ["git", "-C", str(self.root)])
        self.assertNotIn("--global", command)
        path = command[-1]
        if command[3] == "ls-files":
            code = 0 if path in self.tracked else 1
        elif command[3] == "check-ignore":
            code = 1 if path in self.not_ignored else 0
        else:
            self.fail("Git mutation attempted: " + repr(command))
        return SimpleNamespace(returncode=code, stdout="", stderr="")

    def provision(self, capabilities=("godot", "photoshop"), *, check=False, platform="windows"):
        return subject.provision_codex(self.root, platform, capabilities, check=check,
                                       runner=self.runner, user_config=self.user_config)

    def project(self):
        return subject.project_config_path(self.root)

    def write_project(self, text):
        self.project().parent.mkdir(exist_ok=True)
        self.project().write_text(text, encoding="utf-8")

    def write_user(self, text):
        self.user_config.parent.mkdir(exist_ok=True)
        self.user_config.write_text(text, encoding="utf-8")

    def entry_text(self, capability="godot", *, changes=None):
        name = subject.PROFILES[capability][0]
        entry = subject.desired_entry(self.root, "windows", capability)
        entry.update(changes or {})
        return fixture_toml({"mcp_servers": {name: entry}})

    def snapshot(self):
        return {str(path.relative_to(Path(self.temporary.name))): path.read_bytes()
                for path in Path(self.temporary.name).rglob("*") if path.is_file()}

    def test_fresh_config_uses_direct_python_and_reviewed_allowlists(self):
        import tomllib
        result = self.provision()
        self.assertEqual({item["state"] for item in result.values()}, {"created"})
        self.assertTrue(all(item["ready"] for item in result.values()))
        config = tomllib.loads(self.project().read_text("utf-8"))
        self.assertEqual(set(config), {"mcp_servers"})
        self.assertEqual(set(config["mcp_servers"]), {"lunitora_godot", "lunitora_photoshop"})
        for key, (name, _, _, _) in subject.PROFILES.items():
            self.assertEqual(config["mcp_servers"][name], subject.desired_entry(self.root, "windows", key))
        self.assertEqual(len(config["mcp_servers"]["lunitora_godot"]["enabled_tools"]), 9)
        self.assertEqual(len(config["mcp_servers"]["lunitora_photoshop"]["enabled_tools"]), 3)
        self.assertNotIn("lunitora_launcher", self.project().read_text("utf-8"))

    def test_idempotent_rerun_is_byte_identical_and_no_atomic_writes(self):
        self.provision()
        before = self.snapshot()
        with patch.object(subject, "_atomic", side_effect=AssertionError("unnecessary write")):
            result = self.provision()
        self.assertTrue(all(item["ready"] for item in result.values()))
        self.assertEqual({item["state"] for item in result.values()}, {"already correct"})
        self.assertEqual(self.snapshot(), before)

    def test_owned_entry_with_user_date_edit_blocks_only_that_capability(self):
        self.provision(("godot",))
        self.write_project(self.project().read_text("utf-8") + "custom_date = 2026-10-02\n")
        import tomllib
        edited = tomllib.loads(self.project().read_text("utf-8"))["mcp_servers"]["lunitora_godot"]
        outcome = self.provision()
        self.assertEqual(outcome["godot"]["state"], "conflict")
        self.assertTrue(outcome["photoshop"]["ready"])
        self.assertEqual(tomllib.loads(self.project().read_text("utf-8"))["mcp_servers"]["lunitora_godot"], edited)

    def test_unicode_case_expansion_cannot_admit_another_transport(self):
        self.assertFalse(subject._same_path("C:\\Config\\\u0130\\python.exe", "C:\\Config\\i\u0307\\python.exe", "windows"))

    def test_atomic_project_temporary_files_are_ignored(self):
        import subprocess
        source = Path(__file__).absolute().parents[2]
        path = ".codex/.lunitora-codex-0123456789abcdef0123456789abcdef.tmp"
        inspected = subprocess.run(["git", "-C", str(source), "check-ignore", "--no-index", "--", path],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(inspected.returncode, 0)

    def test_unrelated_toml_comments_approval_restrictions_and_user_choices_survive(self):
        import tomllib
        original = ("# Keep the user comment\nmodel = 'custom'\n"
                    "approval_policy = 'on-request' # choice\n"
                    "sandbox_mode = 'read-only'\n\n"
                    "[mcp_servers.custom]\ncommand = 'custom command'\n"
                    "enabled_tools = ['read']\ndisabled_tools = ['write']\n"
                    "[mcp_servers.custom.tools.read]\napproval_mode = 'prompt'\n")
        self.write_project(original)
        self.provision(("godot",))
        output = self.project().read_text("utf-8")
        self.assertTrue(output.startswith(original))
        parsed = tomllib.loads(output)
        self.assertEqual(parsed["approval_policy"], "on-request")
        self.assertEqual(parsed["sandbox_mode"], "read-only")
        self.assertEqual(parsed["mcp_servers"]["custom"]["tools"]["read"]["approval_mode"], "prompt")
        self.assertNotIn("trust_level", output)
        self.assertNotIn("projects", parsed)

    def test_compatible_custom_project_is_not_adopted_or_modified(self):
        text = self.entry_text(changes={"enabled_tools": ["godot_ping"], "enabled": True,
                                       "tool_timeout_sec": 6, "env_vars": ["LOCAL_CHOICE"],
                                       "tools": {"godot_ping": {"approval_mode": "prompt"}}})
        self.write_project(text)
        result = self.provision(("godot",))
        self.assertEqual(result["godot"]["state"], "compatible custom")
        self.assertEqual(self.project().read_text("utf-8"), text)
        self.assertFalse(subject.ownership_path(self.root).exists())

    def test_compatible_global_is_preserved_without_project_override(self):
        text = "# user only\n" + self.entry_text(changes={"enabled_tools": ["godot_ping"],
                                                       "default_tools_approval_mode": "prompt"})
        self.write_user(text)
        before = self.snapshot()
        result = self.provision(("godot",))
        self.assertEqual(result["godot"]["state"], "compatible inherited")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.project().exists())

    def test_custom_conflict_fails_only_affected_capability(self):
        import tomllib
        self.write_project(self.entry_text(changes={"command": "custom-wrapper.exe"}))
        result = self.provision()
        self.assertFalse(result["godot"]["ready"])
        self.assertEqual(result["godot"]["state"], "conflict")
        self.assertTrue(result["photoshop"]["ready"])
        config = tomllib.loads(self.project().read_text("utf-8"))
        self.assertEqual(config["mcp_servers"]["lunitora_godot"]["command"], "custom-wrapper.exe")
        ownership = json.loads(subject.ownership_path(self.root).read_text("utf-8"))
        self.assertNotIn("lunitora_godot", ownership["entries"])

    def test_conflicting_global_prevents_same_name_override_but_no_global_change(self):
        self.write_user(self.entry_text(changes={"args": ["-m", "custom.server"]}))
        before = self.snapshot()
        result = self.provision(("godot",))
        self.assertEqual(result["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)

    def test_missing_allowlist_and_unreviewed_tool_are_conflicts(self):
        for policy in (None, ["unreviewed_write_tool"]):
            with self.subTest(policy=policy):
                entry = subject.desired_entry(self.root, "windows", "godot")
                if policy is None:
                    del entry["enabled_tools"]
                else:
                    entry["enabled_tools"] = policy
                self.write_project(fixture_toml({"mcp_servers": {"lunitora_godot": entry}}))
                before = self.snapshot()
                self.assertFalse(self.provision(("godot",))["godot"]["ready"])
                self.assertEqual(self.snapshot(), before)

    def test_enabled_false_empty_allowlist_and_fully_denied_are_preserved(self):
        for change in ({"enabled": False}, {"enabled_tools": []},
                       {"disabled_tools": list(subject.GODOT_TOOLS)}):
            with self.subTest(change=change):
                self.write_project(self.entry_text(changes=change))
                before = self.snapshot()
                result = self.provision(("godot",))
                self.assertEqual(result["godot"]["state"], "user restricted")
                self.assertFalse(result["godot"]["ready"])
                self.assertEqual(self.snapshot(), before)

    def test_conflicting_global_narrower_policy_is_not_broadened(self):
        self.provision(("godot",))
        self.write_user(self.entry_text(changes={"enabled_tools": ["godot_ping"]}))
        before = self.snapshot()
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)

    def test_global_tool_approval_and_deny_choices_are_not_overridden(self):
        self.provision(("godot",))
        for change in ({"disabled_tools": ["godot_create_rig_lab"]},
                       {"tools": {"godot_ping": {"approval_mode": "prompt"}}},
                       {"default_tools_approval_mode": "prompt"}, {"enabled": False}):
            with self.subTest(change=change):
                self.write_user(self.entry_text(changes=change))
                before = self.snapshot()
                self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
                self.assertEqual(self.snapshot(), before)

    def test_check_fresh_zero_writes_without_tomlkit(self):
        before = self.snapshot()
        with patch.object(subject, "_toml", side_effect=AssertionError("doctor must be stdlib")), \
                patch.object(subject, "config_lock", side_effect=AssertionError("doctor lock write")):
            result = self.provision(check=True)
        self.assertEqual({item["state"] for item in result.values()}, {"creation available"})
        self.assertFalse(any(item["ready"] for item in result.values()))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / "tools/.lunitora").exists())

    def test_check_existing_does_not_mutate_or_create_locks(self):
        self.write_project("# Comment preserved\n" + self.entry_text())
        before = self.snapshot()
        with patch.object(subject, "_atomic", side_effect=AssertionError("doctor write")):
            result = self.provision(("godot",), check=True)
        self.assertTrue(result["godot"]["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_owned_transport_repair_only_updates_paths_with_policy_preserved(self):
        self.provision(("godot",))
        document = tomllib.loads(self.project().read_text("utf-8"))
        entry = document["mcp_servers"]["lunitora_godot"]
        entry["command"] = "C:\\Old Checkout\\tools\\lunitora_mcp\\.venv\\Scripts\\python.exe"
        entry["cwd"] = "C:\\Old Checkout\\tools\\lunitora_mcp"
        self.project().write_text(fixture_toml(document), encoding="utf-8")
        path = subject.ownership_path(self.root)
        manifest = json.loads(path.read_text("utf-8"))
        manifest["entries"]["lunitora_godot"]["sha256"] = subject._fingerprint(entry)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        before = self.snapshot()
        planned = self.provision(("godot",), check=True)
        self.assertEqual(planned["godot"]["state"], "repair available")
        self.assertEqual(self.snapshot(), before)
        result = self.provision(("godot",))
        self.assertEqual(result["godot"]["state"], "repaired/updated")
        repaired = tomllib.loads(self.project().read_text("utf-8"))["mcp_servers"]["lunitora_godot"]
        self.assertEqual(repaired, subject.desired_entry(self.root, "windows", "godot"))

    def test_owned_entry_user_edit_or_removal_is_preserved(self):
        self.provision(("godot",))
        document = tomllib.loads(self.project().read_text("utf-8"))
        document["mcp_servers"]["lunitora_godot"]["tool_timeout_sec"] = 4
        self.project().write_text(fixture_toml(document), encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)
        del document["mcp_servers"]["lunitora_godot"]
        self.project().write_text(fixture_toml(document), encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)

    def test_invalid_toml_never_exposes_source_contents(self):
        marker = "SYNTHETIC_SECRET_DO_NOT_OUTPUT"
        self.write_project("bad = '" + marker + "\n")
        before = self.snapshot()
        result = self.provision()
        self.assertEqual({item["state"] for item in result.values()}, {"conflict"})
        self.assertNotIn(marker, repr(result))
        self.assertEqual(self.snapshot(), before)

    def test_existing_global_environment_secret_is_not_copied_to_repo_or_result(self):
        marker = "SYNTHETIC_SECRET_DO_NOT_COPY"
        self.write_user(self.entry_text(changes={"env": {"TOKEN": marker}}))
        result = self.provision()
        self.assertTrue(result["godot"]["ready"])
        self.assertNotIn(marker, repr(result))
        for path in self.root.rglob("*"):
            if path.is_file():
                self.assertNotIn(marker.encode(), path.read_bytes())

    def test_malformed_ownership_record_fails_closed(self):
        self.provision(("godot",))
        path = subject.ownership_path(self.root)
        path.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.provision()["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)

    def test_tracked_and_nonignored_local_paths_are_rejected(self):
        for paths in (self.tracked, self.not_ignored):
            for path in (".codex/config.toml", "tools/.lunitora/codex-owned.json", "tools/.lunitora/codex.lock"):
                with self.subTest(path=path, tracked=paths is self.tracked):
                    paths.add(path)
                    before = self.snapshot()
                    self.assertEqual(self.provision()["godot"]["state"], "conflict")
                    self.assertEqual(self.snapshot(), before)
                    paths.clear()

    def test_nonregular_and_hardlinked_configuration_rejected(self):
        self.project().mkdir(parents=True)
        self.assertFalse(self.provision()["godot"]["ready"])
        self.project().rmdir()
        original = Path(self.temporary.name) / "hardlink original"
        original.write_text("# original\n", encoding="utf-8")
        os.link(original, self.project())
        before = self.snapshot()
        self.assertFalse(self.provision()["godot"]["ready"])
        self.assertEqual(self.snapshot(), before)

    def test_redirected_storage_is_rejected_before_read_or_write(self):
        with patch.object(subject, "reject_redirects", side_effect=ConfigurationError("Redirected storage rejected")), \
                patch.object(subject, "_read", side_effect=AssertionError("redirected read")):
            self.assertEqual(self.provision()["godot"]["state"], "conflict")

    def test_concurrent_change_is_detected_before_config_replace(self):
        original_lock = subject.config_lock
        @contextmanager
        def mutate(root, name):
            with original_lock(root, name):
                self.write_project("# external edit\n")
                yield
        with patch.object(subject, "config_lock", mutate), \
                patch.object(subject, "_atomic", side_effect=AssertionError("concurrent overwrite")):
            result = self.provision()
        self.assertEqual(result["godot"]["state"], "conflict")
        self.assertEqual(self.project().read_text("utf-8"), "# external edit\n")

    def test_ownership_failure_rolls_back_new_project_config(self):
        original = subject._atomic
        def partial(path, payload):
            if path == subject.ownership_path(self.root):
                raise OSError("fixture manifest failure")
            return original(path, payload)
        with patch.object(subject, "_atomic", partial):
            first = self.provision(("godot",))
        self.assertEqual(first["godot"]["state"], "conflict")
        self.assertIn("restored", first["godot"]["reason"])
        self.assertFalse(self.project().exists())
        self.assertFalse(subject.ownership_path(self.root).exists())
        second = self.provision(("godot",))
        self.assertEqual(second["godot"]["state"], "created")

    def test_ownership_failure_restores_existing_project_exact_bytes(self):
        original_text = "# Exact original\napproval_policy = 'on-request'\n"
        self.write_project(original_text)
        original = subject._atomic
        def partial(path, payload):
            if path == subject.ownership_path(self.root):
                raise OSError("fixture manifest failure")
            return original(path, payload)
        with patch.object(subject, "_atomic", partial):
            result = self.provision(("godot",))
        self.assertIn("restored", result["godot"]["reason"])
        self.assertEqual(self.project().read_text("utf-8"), original_text)

    def test_ownership_failure_never_rolls_back_concurrent_user_edit(self):
        original = subject._atomic
        def partial(path, payload):
            if path == subject.ownership_path(self.root):
                self.write_project("# concurrent edit\n")
                raise OSError("fixture manifest failure")
            return original(path, payload)
        with patch.object(subject, "_atomic", partial):
            result = self.provision(("godot",))
        self.assertIn("partially prepared", result["godot"]["reason"])
        self.assertEqual(self.project().read_text("utf-8"), "# concurrent edit\n")

    def test_windows_case_separator_equivalence_does_not_rewrite_custom_path(self):
        desired = subject.desired_entry(self.root, "windows", "godot")
        text = self.entry_text(changes={"command": desired["command"].upper().replace("\\", "/"),
                                       "cwd": desired["cwd"].upper().replace("\\", "/")})
        self.write_project(text)
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "compatible custom")
        self.assertEqual(self.project().read_text("utf-8"), text)

    def test_macos_transport_configuration_does_not_claim_live_validation(self):
        import tomllib
        result = self.provision(("godot",), platform="macos")
        self.assertTrue(result["godot"]["ready"])
        self.assertIn("live acceptance", result["godot"]["reason"])
        entry = tomllib.loads(self.project().read_text("utf-8"))["mcp_servers"]["lunitora_godot"]
        self.assertTrue(entry["command"].endswith(".venv\\bin\\python") or entry["command"].endswith(".venv/bin/python"))
        self.assertNotIn("trust", entry)

    def test_no_capabilities_no_reads_or_writes(self):
        with patch.object(subject, "_read", side_effect=AssertionError("unnecessary read")):
            self.assertEqual(self.provision(()), {})

    def test_relative_or_same_global_location_is_rejected(self):
        for location in (Path("relative/config.toml"), self.project()):
            result = subject.provision_codex(self.root, "windows", ("godot",), runner=self.runner,
                                            user_config=location)
            self.assertEqual(result["godot"]["state"], "conflict")

    def test_mcp_servers_non_table_is_preserved_without_secret_diagnostics(self):
        self.write_project('mcp_servers = "SYNTHETIC_PRIVATE_VALUE"\n')
        result = self.provision()
        self.assertNotIn("SYNTHETIC_PRIVATE_VALUE", repr(result))
        self.assertFalse(any(item["ready"] for item in result.values()))

    def test_named_profile_override_fails_only_affected_capability(self):
        text = self.entry_text().replace("[mcp_servers.lunitora_godot]", "[profiles.custom.mcp_servers.lunitora_godot]")
        self.write_user(text)
        before = self.user_config.read_bytes()
        result = self.provision()
        self.assertEqual(result["godot"]["state"], "conflict")
        self.assertTrue(result["photoshop"]["ready"])
        self.assertEqual(self.user_config.read_bytes(), before)

    def test_unsupported_transport_fields_and_invalid_timeouts_fail_closed(self):
        for changes in ({"url": "https://example.invalid"}, {"auth": "oauth"},
                        {"http_headers": {"Authorization": "SYNTHETIC_DO_NOT_OUTPUT"}},
                        {"startup_timeout_sec": 0}, {"tool_timeout_sec": True},
                        {"tool_timeout_sec": float("inf")}):
            with self.subTest(changes=changes):
                self.write_project(self.entry_text(changes=changes))
                before = self.snapshot()
                result = self.provision(("godot",))
                self.assertEqual(result["godot"]["state"], "conflict")
                self.assertNotIn("SYNTHETIC_DO_NOT_OUTPUT", repr(result))
                self.assertEqual(self.snapshot(), before)

    def test_remote_placement_sources_and_http_only_policy_are_not_local_ready(self):
        for changes in ({"experimental_environment": "remote"},
                        {"env_vars": [{"name": "LOCAL_VAR", "source": "remote"}]},
                        {"env_http_headers": {"Authorization": "LOCAL_VARIABLE"}},
                        {"http_headers_helper": "custom helper"}, {"oauth_resource": "custom-resource"}):
            with self.subTest(changes=changes):
                self.write_project(self.entry_text(changes=changes))
                before = self.snapshot()
                self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
                self.assertEqual(self.snapshot(), before)

    def test_compatible_local_source_environment_choices_stay_unmodified(self):
        text = self.entry_text(changes={"experimental_environment": "local",
                                       "env_vars": ["ONE", {"name": "TWO", "source": "local"}]})
        self.write_user(text)
        before = self.snapshot()
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "compatible inherited")
        self.assertEqual(self.snapshot(), before)

    def test_invalid_known_tool_policy_is_preserved_but_not_reported_ready(self):
        for changes in ({"default_tools_approval_mode": "unknown-mode"}, {"required": "yes"},
                        {"default_tools_approval_mode": ["prompt"]}, {"default_tools_approval_mode": {"mode": "prompt"}},
                        {"tools": ["godot_ping"]}, {"tools": {"godot_ping": {"approval_mode": "unknown-mode"}}},
                        {"tools": {"godot_ping": {"approval_mode": ["prompt"]}}},
                        {"tools": {"godot_ping": {"approval_mode": {"mode": "prompt"}}}},
                        {"tools": {"godot_ping": {"output_token_limit": True}}},
                        {"env": {"LOCAL_VAR": 1}}, {"env_vars": [{"source": "local"}]}):
            with self.subTest(changes=changes):
                self.write_project(self.entry_text(changes=changes))
                before = self.snapshot()
                self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
                self.assertEqual(self.snapshot(), before)

    def test_malformed_owned_non_table_is_preserved_not_adopted(self):
        self.provision(("godot",))
        self.write_project("[mcp_servers]\nlunitora_godot = 1\n")
        path = subject.ownership_path(self.root)
        manifest = json.loads(path.read_text("utf-8"))
        manifest["entries"]["lunitora_godot"]["sha256"] = subject._fingerprint(1)
        path.write_text(json.dumps(manifest), encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.provision(("godot",))["godot"]["state"], "conflict")
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
