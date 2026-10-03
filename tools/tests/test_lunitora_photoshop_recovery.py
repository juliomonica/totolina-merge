"""Recovery acceptance uses disposable credentials only."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
from lunitora_machine import authentication as auth, photoshop_recovery as recovery, bootstrap

TOKEN = b'q' * 64 + b'\r\n'


def git(command):
    return SimpleNamespace(returncode=0, stdout='', stderr='')


@unittest.skipUnless(os.name == 'nt', 'Windows security contract')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / auth.STORAGE
        self.local.mkdir(parents=True)
        self.path = self.local / 'pairing-token.txt'
        self.path.write_bytes(TOKEN)
        _, self.security, self.photoshop = auth._reviewed_modules()
        self.output = []

    def snapshot(self, path, directory=False):
        with ExitStack() as stack:
            return self.security.protection_snapshot(self.security.pin(stack, path, directory=directory))

    def repair(self, prompt=lambda _: 'y'):
        return recovery.repair(self.root, 'windows', runner=git, prompt=prompt, emit=self.output.append)

    def test_repair_preserves_bytes_and_unrelated_children_acl(self):
        child = self.local / 'artifact.txt'
        child.write_bytes(b'unrelated')
        nested = self.local / 'nested'
        nested.mkdir()
        nested_child = nested / 'artifact.txt'
        nested_child.write_bytes(b'nested artifact')
        with ExitStack() as stack:
            for p in (child, nested_child, nested):
                self.security.apply_protection(self.security.repair_handle(stack, p, directory=p.is_dir()), directory=p.is_dir())
        before = [(p.read_bytes() if p.is_file() else None, self.snapshot(p, p.is_dir()))
                  for p in (child, nested, nested_child)]
        self.assertEqual(self.repair(), 0)
        self.assertEqual(self.path.read_bytes(), TOKEN)
        after = [(p.read_bytes() if p.is_file() else None, self.snapshot(p, p.is_dir()))
                 for p in (child, nested, nested_child)]
        self.assertEqual(before, after)
        with ExitStack() as stack:
            for p in (self.local, self.path):
                self.security.validate_acl(self.security.pin(stack, p, directory=p.is_dir()))
        self.assertNotIn(TOKEN.decode().strip(), '\n'.join(self.output))

    def test_unprotected_unrelated_child_stops_before_mutation(self):
        child = self.local / 'artifact.txt'
        child.write_bytes(b'unrelated')
        before = self.snapshot(self.local, True), self.snapshot(self.path), self.snapshot(child)
        prompt = Mock()
        self.assertEqual(self.repair(prompt), 1)
        prompt.assert_not_called()
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path), self.snapshot(child)))
        self.assertIn('unrelated children', '\n'.join(self.output))

    def test_cancel_zero_changes(self):
        before = self.snapshot(self.local, True), self.snapshot(self.path), self.path.read_bytes()
        self.assertEqual(self.repair(lambda _: 'n'), 1)
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path), self.path.read_bytes()))

    def test_concurrent_token_change_fails_before_acl_mutation(self):
        before = self.snapshot(self.local, True), self.snapshot(self.path)
        def consent(_):
            self.path.write_bytes(b'z' * 64 + b'\n')
            return 'y'
        self.assertEqual(self.repair(consent), 1)
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path)))

    def test_concurrent_acl_change_fails_closed(self):
        def consent(_):
            with ExitStack() as stack:
                h = self.security.repair_handle(stack, self.path, directory=False)
                self.security.apply_protection(h, directory=False)
            return 'y'
        before = self.snapshot(self.local, True)
        self.assertEqual(self.repair(consent), 1)
        self.assertEqual(before, self.snapshot(self.local, True))

    def test_child_added_during_consent_stops_without_repair(self):
        before = self.snapshot(self.local, True), self.snapshot(self.path)
        def consent(_):
            (self.local / 'concurrent.txt').write_bytes(b'artifact')
            return 'y'
        self.assertEqual(self.repair(consent), 1)
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path)))

    def test_git_state_changes_during_consent_blocks_mutation(self):
        before = self.snapshot(self.local, True), self.snapshot(self.path)
        tracked = False
        def runner(command):
            return SimpleNamespace(returncode=0, stdout='tracked' if tracked and 'ls-files' in command else '', stderr='')
        def consent(_):
            nonlocal tracked
            tracked = True
            return 'y'
        self.assertEqual(recovery.repair(self.root, 'windows', runner=runner, prompt=consent, emit=self.output.append), 1)
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path)))

    def test_hardlink_ambiguous_path_rejected_without_consent(self):
        os.link(self.path, self.root / 'alias')
        prompt = Mock(side_effect=AssertionError('consent must not occur'))
        self.assertEqual(self.repair(prompt), 1)
        prompt.assert_not_called()

    def test_active_reader_blocks_mutation(self):
        before = self.snapshot(self.local, True)
        with ExitStack() as stack:
            self.security.pin(stack, self.path, directory=False)
            self.assertEqual(self.repair(), 1)
        self.assertEqual(before, self.snapshot(self.local, True))

    def test_unknown_owner_provenance_rejected(self):
        with patch.object(self.security, 'reviewed_owner', return_value=False):
            prompt = Mock()
            self.assertEqual(self.repair(prompt), 1)
            prompt.assert_not_called()

    def test_redirect_guard_rejects_before_consent_or_mutation(self):
        prompt = Mock()
        with patch.object(auth, '_guard_storage', side_effect=auth.AuthenticationError()), \
                patch.object(self.security, 'apply_protection') as mutation:
            self.assertEqual(self.repair(prompt), 1)
        prompt.assert_not_called()
        mutation.assert_not_called()

    def test_malformed_token_is_not_repaired_or_replaced(self):
        self.path.write_bytes(b'malformed')
        before = self.snapshot(self.local, True), self.snapshot(self.path)
        prompt = Mock()
        self.assertEqual(self.repair(prompt), 1)
        prompt.assert_not_called()
        self.assertEqual(self.path.read_bytes(), b'malformed')
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path)))

    def test_normal_check_and_pair_offer_repair_without_writes(self):
        before = self.snapshot(self.local, True), self.snapshot(self.path), self.path.read_bytes()
        for kwargs in ({}, {'check': True}, {'replace_photoshop': True, 'interactive': True}):
            with patch.object(self.security, 'apply_protection', side_effect=AssertionError('write')), \
                    patch.object(auth, '_store_pairing', side_effect=AssertionError('token write')):
                result = auth.provision_authentication(self.root, 'windows', ('photoshop',), runner=git, **kwargs)
            self.assertEqual(result['photoshop']['state'], 'migration required')
            self.assertIn('--migrate-photoshop-auth', result['photoshop']['reason'])
        self.assertEqual(before, (self.snapshot(self.local, True), self.snapshot(self.path), self.path.read_bytes()))

    def test_errors_and_output_never_contain_token(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), \
                patch.object(self.security, 'apply_protection', side_effect=ValueError(TOKEN.decode())):
            self.assertEqual(self.repair(), 1)
        self.assertNotIn(TOKEN.decode().strip(), stdout.getvalue() + stderr.getvalue() + '\n'.join(self.output))

    def test_repeated_repair_and_pair_reuse_protected_token(self):
        self.assertEqual(self.repair(), 0)
        prompt = Mock(side_effect=AssertionError('prompt'))
        self.assertEqual(self.repair(prompt), 0)
        result = auth.provision_authentication(self.root, 'windows', ('photoshop',), runner=git,
                                               replace_photoshop=True, interactive=True, secret_prompt=prompt)
        self.assertTrue(result['photoshop']['ready'])
        self.assertEqual(self.path.read_bytes(), TOKEN)


class CliTests(unittest.TestCase):
    def test_check_repair_rejected_before_any_setup(self):
        with patch.object(bootstrap, 'validate_repository') as validate, patch('sys.stderr'), self.assertRaises(SystemExit):
            bootstrap.main(['--check', '--repair-photoshop-auth'])
        validate.assert_not_called()

    def test_repair_worker_flag_forwarded(self):
        with patch.object(bootstrap, 'validate_repository'), \
                patch.object(bootstrap, 'platform_name', return_value='windows'), \
                patch.object(bootstrap, 'validated_host', return_value='C:/synthetic/python.exe'), \
                patch('subprocess.run', return_value=SimpleNamespace(returncode=0)) as worker:
            self.assertEqual(bootstrap.main(['--repair-photoshop-auth']), 0)
        self.assertIn('--repair-photoshop-auth', worker.call_args.args[0])

    def test_repair_bypasses_environment_and_configuration_updates(self):
        with patch.object(bootstrap, 'validate_repository'), \
                patch.object(bootstrap, 'platform_name', return_value='windows'), \
                patch.object(bootstrap, 'validated_host', return_value=sys.executable), \
                patch.object(bootstrap.sys, 'prefix', sys.base_prefix), \
                patch.object(bootstrap, 'ensure_environment') as environment, \
                patch.object(bootstrap, 'bootstrap') as setup, \
                patch.object(recovery, 'repair', return_value=0) as repair:
            self.assertEqual(bootstrap.main(['--repair-photoshop-auth']), 0)
        repair.assert_called_once()
        environment.assert_not_called()
        setup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
