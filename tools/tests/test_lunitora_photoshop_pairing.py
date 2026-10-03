"""Private pairing contracts using synthetic tokens and disposable storage only."""
from __future__ import annotations

from contextlib import ExitStack
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import warnings

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))

from lunitora_machine import authentication as auth
from lunitora_machine import applications, bootstrap, integration


TOKEN = "a" * 64
NEW_TOKEN = "b" * 64


def safe_git(command, **kwargs):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


class SecretPromptContracts(unittest.TestCase):
    def test_supplied_valid_token_is_returned_without_diagnostics(self):
        prompt = Mock(return_value=TOKEN)
        with patch("builtins.print") as printed:
            token = auth.read_pairing_token(prompt)
        self.assertTrue(token == TOKEN)
        prompt.assert_called_once()
        printed.assert_not_called()
        self.assertNotIn(TOKEN, repr(prompt.call_args))

    def test_blank_private_input_requests_generation(self):
        self.assertIsNone(auth.read_pairing_token(lambda _: ""))

    def test_surrounding_copy_whitespace_is_not_part_of_token(self):
        token = auth.read_pairing_token(lambda _: " \t" + TOKEN + "\r\n")
        self.assertTrue(token == TOKEN)

    def test_invalid_input_is_rejected_without_echo(self):
        for value in ("short", "x" * 63, "x" * 65, "!" * 64, "\u00e9" * 64):
            with self.subTest(length=len(value)), self.assertRaises(auth.AuthenticationError) as raised:
                auth.read_pairing_token(lambda _: value)
            self.assertNotIn(value, str(raised.exception))

    def test_prompt_exceptions_are_redacted(self):
        for failure in (EOFError(TOKEN), OSError(TOKEN), KeyboardInterrupt(TOKEN)):
            with self.subTest(kind=type(failure).__name__), self.assertRaises(auth.AuthenticationError) as raised:
                auth.read_pairing_token(Mock(side_effect=failure))
            self.assertNotIn(TOKEN, str(raised.exception))

    def test_non_text_private_input_is_rejected(self):
        for value in (None, TOKEN.encode(), 123, {"token": TOKEN}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(auth.AuthenticationError) as raised:
                auth.read_pairing_token(lambda _: value)
            self.assertNotIn(TOKEN, str(raised.exception))

    def test_getpass_warning_aborts_before_echoing_fallback(self):
        def unsafe_prompt(_):
            warnings.warn("no private console", getpass.GetPassWarning)
            self.fail("An echoing fallback must not consume the token")
        with patch.object(getpass, "getpass", side_effect=unsafe_prompt), \
                self.assertRaises(auth.AuthenticationError):
            auth.read_pairing_token()

    def test_default_prompt_uses_getpass_not_input(self):
        with patch.object(getpass, "getpass", return_value=TOKEN) as private, \
                patch("builtins.input", side_effect=AssertionError("echoing input called")):
            token = auth.read_pairing_token()
        self.assertTrue(token == TOKEN)
        private.assert_called_once()


@unittest.skipUnless(os.name == "nt", "Protected credential provisioning requires Windows")
class PairingProvisioningContracts(unittest.TestCase):
    def setUp(self):
        self.root = Path.cwd() / "disposable pairing project with spaces"
        self.config, self.security, self.photoshop = auth._reviewed_modules()
        guard = patch.object(auth, "_guard_storage")
        guard.start()
        self.addCleanup(guard.stop)

    def provision(self, **kwargs):
        return auth.provision_authentication(self.root, "windows", ("photoshop",), runner=safe_git, **kwargs)

    def test_valid_stored_token_never_prompts_or_writes(self):
        prompt = Mock(side_effect=AssertionError("prompt called"))
        with patch.object(auth, "_read_protected", return_value=(TOKEN + "\n").encode()), \
                patch.object(auth, "_store_pairing") as store:
            result = self.provision(interactive=True, secret_prompt=prompt)
        self.assertTrue(result["photoshop"]["ready"])
        prompt.assert_not_called()
        store.assert_not_called()
        self.assertNotIn(TOKEN, repr(result))

    def test_missing_token_interactive_uses_private_input(self):
        prompt = Mock(return_value=TOKEN)
        output = []
        with patch.object(auth, "_read_protected", return_value=None), \
                patch.object(auth, "_store_pairing", return_value=True) as store:
            result = self.provision(interactive=True, secret_prompt=prompt, emit=output.append)
        self.assertTrue(result["photoshop"]["ready"])
        prompt.assert_called_once()
        self.assertTrue(store.call_args.kwargs["token"] == TOKEN)
        self.assertNotIn(TOKEN, repr(result) + "\n".join(output))

    def test_malformed_protected_token_can_be_repaired_with_private_input(self):
        existing = b"malformed"
        with patch.object(auth, "_read_protected", return_value=existing), \
                patch.object(auth, "_store_pairing", return_value=True) as store:
            result = self.provision(interactive=True, secret_prompt=lambda _: NEW_TOKEN, emit=lambda _: None)
        self.assertTrue(result["photoshop"]["ready"])
        self.assertTrue(store.call_args.kwargs["expected"] == existing)

    def test_explicit_pairing_reuses_valid_protected_token(self):
        existing = (TOKEN + "\n").encode()
        prompt = Mock(return_value=NEW_TOKEN)
        with patch.object(auth, "_read_protected", return_value=existing), \
                patch.object(auth, "_store_pairing", return_value=True) as store:
            result = self.provision(interactive=True, secret_prompt=prompt,
                                    replace_photoshop=True, emit=lambda _: None)
        self.assertTrue(result["photoshop"]["ready"])
        store.assert_not_called()
        prompt.assert_not_called()
        self.assertNotIn(TOKEN, repr(result))
        self.assertNotIn(NEW_TOKEN, repr(result))

    def test_invalid_interactive_entry_never_reaches_storage_writer(self):
        with patch.object(auth, "_read_protected", return_value=None), \
                patch.object(auth, "_store_pairing") as store:
            result = self.provision(interactive=True, secret_prompt=lambda _: "invalid", emit=lambda _: None)
        self.assertFalse(result["photoshop"]["ready"])
        store.assert_not_called()

    def test_storage_becoming_tracked_during_prompt_blocks_writer(self):
        with patch.object(auth, "_guard_storage", side_effect=[None, auth.AuthenticationError()]), \
                patch.object(auth, "_read_protected", return_value=None), \
                patch.object(auth, "_store_pairing") as store:
            result = self.provision(interactive=True, secret_prompt=lambda _: TOKEN, emit=lambda _: None)
        self.assertFalse(result["photoshop"]["ready"])
        self.assertNotIn(TOKEN, repr(result))
        store.assert_not_called()

    def test_check_never_prompts_or_writes_even_when_replacement_requested(self):
        prompt = Mock(side_effect=AssertionError("prompt called"))
        for payload in (None, b"malformed", (TOKEN + "\n").encode()):
            with self.subTest(existing=payload is not None), \
                    patch.object(auth, "_read_protected", return_value=payload), \
                    patch.object(auth, "_store_pairing") as store:
                result = self.provision(check=True, interactive=True, secret_prompt=prompt,
                                        replace_photoshop=True, emit=lambda _: None)
            self.assertNotIn(TOKEN, repr(result))
            store.assert_not_called()
        prompt.assert_not_called()

    def test_unsafe_storage_blocks_before_private_prompt(self):
        prompt = Mock(side_effect=AssertionError("prompt called"))
        with patch.object(auth, "_read_protected", side_effect=ValueError(TOKEN)), \
                patch.object(auth, "_store_pairing") as store:
            result = self.provision(interactive=True, secret_prompt=prompt,
                                    replace_photoshop=True, emit=lambda _: None)
        self.assertFalse(result["photoshop"]["ready"])
        prompt.assert_not_called()
        store.assert_not_called()
        self.assertNotIn(TOKEN, repr(result))

    def test_storage_authentication_error_contents_are_redacted(self):
        output = []
        with patch.object(auth, "_read_protected", side_effect=auth.AuthenticationError(TOKEN)):
            result = self.provision(interactive=True, emit=output.append)
        self.assertFalse(result["photoshop"]["ready"])
        self.assertNotIn(TOKEN, repr(result) + "\n".join(output))

    def test_noninteractive_pairing_reuses_valid_token_without_prompt_or_write(self):
        with patch.object(auth, "_read_protected", return_value=(TOKEN + "\n").encode()), \
                patch.object(auth, "_store_pairing") as store:
            result = self.provision(replace_photoshop=True, emit=lambda _: None)
        self.assertTrue(result["photoshop"]["ready"])
        store.assert_not_called()

    def test_mac_pairing_does_not_request_secret_or_touch_storage(self):
        prompt = Mock(side_effect=AssertionError("prompt called"))
        with patch.object(auth, "_read_protected") as read, patch.object(auth, "_store_pairing") as store:
            result = auth.provision_authentication(self.root, "macos", ("photoshop",),
                                                  interactive=True, secret_prompt=prompt,
                                                  replace_photoshop=True)
        self.assertEqual(result["photoshop"]["state"], "REQUIRES MAC")
        prompt.assert_not_called()
        read.assert_not_called()
        store.assert_not_called()

    def test_missing_art_does_not_invoke_pairing_prompt(self):
        prompt = Mock(side_effect=AssertionError("prompt called"))
        with patch.object(auth, "_read_protected") as read, patch.object(auth, "_store_pairing") as store:
            self.assertEqual(auth.provision_authentication(self.root, "windows", (),
                                                          interactive=True, secret_prompt=prompt), {})
        prompt.assert_not_called()
        read.assert_not_called()
        store.assert_not_called()


class SetupPairingControls(unittest.TestCase):
    def test_udt_selection_prompt_uses_full_application_name(self):
        platform = Mock()
        platform.discover.return_value = []
        prompt = Mock(return_value="")
        app, state = applications.resolve_application("udt", None, platform,
                                                     interactive=True, prompt=prompt)
        self.assertIsNone(app)
        self.assertEqual(state, "missing")
        prompt.assert_called_once()
        self.assertTrue(prompt.call_args.args[0].startswith("UXP Developer Tool (UDT):"))

    def test_pairing_instructions_match_existing_manifest_panel_and_token_direction(self):
        root = Path(__file__).absolute().parents[2]
        manifest_path = root / "tools/lunitora_mcp/bridges/photoshop_uxp/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = []
        auth.pairing_instructions(root, output.append)
        text = "\n".join(output)
        self.assertIn("UXP Developer Tool (UDT)", output[0])
        self.assertIn("loading, developing, debugging and packaging", output[0])
        self.assertIn("one-time pairing per machine", text)
        self.assertIn("Edit > Preferences > Plugins > Enable Developer Mode", text)
        self.assertIn("enable Developer Mode when prompted", text)
        self.assertIn(str(manifest_path), text)
        self.assertIn("Add Plugin", text)
        self.assertIn("Plugins > " + manifest["entrypoints"][0]["label"]["default"], text)
        self.assertIn("panel only accepts a token; it does not generate or reveal one", text)
        self.assertIn("enter an existing token privately", text)
        self.assertIn("press Enter to generate this machine's token", text)
        self.assertIn(str(root / auth.PHOTOSHOP_STORAGE / "pairing-token.txt"), text)
        self.assertIn("password input, currently labelled Pairing token", text)
        self.assertIn("Connect / Reconnect", text)
        self.assertIn("Pairing saved securely on this computer", text)

    def test_check_and_reset_rejected_before_environment_or_worker(self):
        with patch.object(bootstrap, "ensure_environment") as environment, \
                patch.object(bootstrap, "validate_repository") as repository, \
                patch("subprocess.run") as worker, patch("sys.stderr"), \
                self.assertRaises(SystemExit) as raised:
            bootstrap.main(["--check", "--pair-photoshop"])
        self.assertEqual(raised.exception.code, 2)
        environment.assert_not_called()
        repository.assert_not_called()
        worker.assert_not_called()

    def test_explicit_reset_flag_reaches_verified_host_worker(self):
        host = "C:\\Test Python\\python.exe"
        with patch.object(bootstrap, "validate_repository"), \
                patch.object(bootstrap, "platform_name", return_value="windows"), \
                patch.object(bootstrap, "validated_host", return_value=host), \
                patch.object(bootstrap.sys, "prefix", "C:\\System Python"), \
                patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as worker:
            self.assertEqual(bootstrap.main(["--pair-photoshop"]), 0)
        command = worker.call_args.args[0]
        self.assertIn("--pair-photoshop", command)
        self.assertIn("--_host-worker", command)
        self.assertEqual(command[0], host)
        self.assertNotIn(".venv", command[0])

    def test_configured_photoshop_reports_authentication_ok_not_live_acceptance(self):
        ready = {"ready": True, "state": "already correct", "reason": "protected local configuration"}
        output = []
        with patch.object(integration, "provision_codex", return_value={"photoshop": ready}), \
                patch.object(integration, "provision_authentication", return_value={"photoshop": ready}):
            result = integration.configure_integration(Path.cwd(), "windows", {"photoshop": {"path": "fixture"}},
                                                       interactive=True, emit=output.append)
        self.assertTrue(any(line.startswith("Photoshop bridge authentication: OK") for line in output))
        self.assertFalse(result["photoshop"]["live_connection"]["ready"])
        self.assertEqual(result["photoshop"]["live_connection"]["state"], "NOT CHECKED")

    def test_integration_check_disables_interactive_pairing(self):
        ready = {"ready": True, "state": "already correct", "reason": "protected local configuration"}
        with patch.object(integration, "provision_codex", return_value={"photoshop": ready}), \
                patch.object(integration, "provision_authentication", return_value={"photoshop": ready}) as authentication:
            integration.configure_integration(Path.cwd(), "windows", {"photoshop": {"path": "fixture"}},
                                              check=True, interactive=True, emit=lambda _: None)
        self.assertTrue(authentication.call_args.kwargs["check"])
        self.assertFalse(authentication.call_args.kwargs["interactive"])


@unittest.skipUnless(os.name == "nt", "Native protected storage requires Windows")
class PairingProtectedReplacement(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lunitora pairing security spaces ")
        self.root = Path(self.directory.name)
        (self.root / "tools/lunitora_mcp").mkdir(parents=True)
        self.config, self.security, self.photoshop = auth._reviewed_modules()
        self.local = self.root / auth.STORAGE
        self.path = self.root / auth.PHOTOSHOP_STORAGE / "pairing-token.txt"

    def tearDown(self):
        self.directory.cleanup()

    def store(self, **kwargs):
        return auth._store_pairing(self.root, self.security, self.photoshop, **kwargs)

    def test_supplied_token_is_protected_and_matches_runtime_format(self):
        self.assertTrue(self.store(token=TOKEN))
        self.assertTrue(self.path.read_bytes() == (TOKEN + "\n").encode())
        with ExitStack() as stack:
            self.security.validate_acl(self.security.pin(stack, self.local, directory=True))
            self.security.validate_acl(self.security.pin(stack, self.path, directory=False))

    def test_explicit_replacement_uses_expected_bytes_and_keeps_protected_acl(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes()
        self.assertTrue(self.store(token=NEW_TOKEN, expected=before))
        self.assertTrue(self.path.read_bytes() == (NEW_TOKEN + "\n").encode())
        with ExitStack() as stack:
            self.security.validate_acl(self.security.pin(stack, self.path, directory=False))

    def test_same_supplied_token_preserves_bytes_and_timestamp(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        self.assertFalse(self.store(token=TOKEN, expected=before[0]))
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)

    def test_stale_expected_bytes_fail_without_replacing_current_token(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        with self.assertRaises(Exception):
            self.store(token=NEW_TOKEN, expected=b"outdated")
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)

    def test_create_only_cannot_overwrite_different_concurrent_token(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        with self.assertRaises(Exception):
            self.store(token=NEW_TOKEN)
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)

    def test_create_only_generation_preserves_existing_valid_token(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        self.assertFalse(self.store())
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)

    def test_malformed_short_token_can_be_replaced_and_truncated(self):
        self.store(token=TOKEN)
        self.path.write_bytes(b"malformed" * 9)
        self.assertTrue(self.store(token=NEW_TOKEN, expected=self.path.read_bytes()))
        self.assertEqual(self.path.stat().st_size, 65)
        self.assertTrue(self.path.read_bytes() == (NEW_TOKEN + "\n").encode())

    def test_empty_protected_token_can_be_repaired_with_hidden_input(self):
        self.store(token=TOKEN)
        self.path.write_bytes(b"")
        result = auth.provision_authentication(self.root, "windows", ("photoshop",),
                                               runner=safe_git, interactive=True,
                                               secret_prompt=lambda _: NEW_TOKEN, emit=lambda _: None)
        self.assertTrue(result["photoshop"]["ready"])
        self.assertTrue(self.path.read_bytes() == (NEW_TOKEN + "\n").encode())

    def test_empty_protected_token_check_does_not_prompt_or_repair(self):
        self.store(token=TOKEN)
        self.path.write_bytes(b"")
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        prompt = Mock(side_effect=AssertionError("prompt called"))
        result = auth.provision_authentication(self.root, "windows", ("photoshop",),
                                               runner=safe_git, check=True, interactive=True,
                                               secret_prompt=prompt, emit=lambda _: None)
        self.assertFalse(result["photoshop"]["ready"])
        self.assertEqual(result["photoshop"]["state"], "pairing required")
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)
        prompt.assert_not_called()

    def test_failed_replacement_restores_previous_protected_token(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes()
        write = self.security.write_storage
        attempts = 0
        def fail_once(handle, payload):
            nonlocal attempts
            attempts += 1
            write(handle, payload)
            if attempts == 1:
                raise OSError("synthetic failure")
        with patch.object(self.security, "write_storage", side_effect=fail_once), \
                self.assertRaises(auth.AuthenticationError):
            self.store(token=NEW_TOKEN, expected=before)
        self.assertEqual(attempts, 2)
        self.assertTrue(self.path.read_bytes() == before)

    def test_active_read_only_pin_prevents_replacement(self):
        self.store(token=TOKEN)
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        with ExitStack() as stack:
            self.security.pin(stack, self.path, directory=False)
            with self.assertRaises(Exception):
                self.store(token=NEW_TOKEN, expected=before[0])
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)

    def test_hardlinked_pairing_token_cannot_be_replaced(self):
        self.store(token=TOKEN)
        os.link(self.path, self.root / "not-a-credential-copy.txt")
        before = self.path.read_bytes(), self.path.stat().st_mtime_ns
        with self.assertRaises(Exception):
            self.store(token=NEW_TOKEN, expected=before[0])
        self.assertTrue((self.path.read_bytes(), self.path.stat().st_mtime_ns) == before)


if __name__ == "__main__":
    unittest.main()
