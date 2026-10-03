"""Migration acceptance with disposable Windows credentials, never live storage."""
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import sys
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
from lunitora_machine import authentication as auth, photoshop_migration as migration, bootstrap
TOKEN = b'q' * 64 + b'\r\n'
def git(command): return SimpleNamespace(returncode=0, stdout='', stderr='')

@unittest.skipUnless(os.name == 'nt', 'Windows owner/DACL contract')
class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / auth.STORAGE
        self.local.mkdir(parents=True)
        self.source = self.local / 'pairing-token.txt'
        self.source.write_bytes(TOKEN)
        self.target = self.root / auth.PHOTOSHOP_STORAGE / 'pairing-token.txt'
        _, self.security, self.photoshop = auth._reviewed_modules()
        self.output = []
    def snapshot(self, p):
        with ExitStack() as stack:
            return (p.read_bytes() if p.is_file() else None,
                    self.security.protection_snapshot(self.security.pin(stack,p,directory=p.is_dir())))
    def migrate(self, prompt=lambda _: 'y', runner=git):
        return migration.migrate(self.root,'windows',prompt=prompt,runner=runner,emit=self.output.append)
    def test_offered_and_byte_identical_with_reviewed_acl(self):
        self.assertTrue(migration.migration_available(self.root,self.security,self.photoshop,git))
        before = self.snapshot(self.source), self.snapshot(self.local)
        self.assertEqual(self.migrate(),0)
        self.assertEqual(self.target.read_bytes(),TOKEN)
        self.assertEqual(before,(self.snapshot(self.source),self.snapshot(self.local)))
        with ExitStack() as stack:
            for p in (self.target,self.target.parent):
                self.security.validate_acl(self.security.pin(stack,p,directory=p.is_dir()))
        self.assertIn('legacy credential remains; cleanup available after live pairing acceptance',self.output)
    def test_unrelated_children_bytes_and_acls_unchanged(self):
        nested=self.local/'nested';nested.mkdir();child=nested/'artifact';child.write_bytes(b'art')
        other=self.local/'artifact';other.write_bytes(b'unrelated')
        before=[self.snapshot(p) for p in (nested,child,other,self.source,self.local)]
        self.assertEqual(self.migrate(),0)
        self.assertEqual(before,[self.snapshot(p) for p in (nested,child,other,self.source,self.local)])
    def test_cancel_zero_changes(self):
        before=self.snapshot(self.source),self.snapshot(self.local)
        self.assertEqual(self.migrate(lambda _: 'n'),1)
        self.assertFalse(self.target.parent.exists())
        self.assertEqual(before,(self.snapshot(self.source),self.snapshot(self.local)))
    def test_idempotent_no_prompt(self):
        self.assertEqual(self.migrate(),0)
        before=self.snapshot(self.target)
        prompt=Mock(side_effect=AssertionError())
        self.assertEqual(self.migrate(prompt),0);prompt.assert_not_called()
        self.assertEqual(before,self.snapshot(self.target))
    def test_conflicting_destination_fail_closed(self):
        self.assertEqual(self.migrate(),0)
        self.target.write_bytes(b'z'*64+b'\n')
        prompt=Mock();self.assertEqual(self.migrate(prompt),1);prompt.assert_not_called()
        self.assertEqual(self.target.read_bytes(),b'z'*64+b'\n')
    def test_malformed_source_no_prompt(self):
        self.source.write_bytes(b'malformed');prompt=Mock()
        self.assertEqual(self.migrate(prompt),1);prompt.assert_not_called()
        self.assertFalse(self.target.parent.exists())
    def test_tracked_source_or_destination(self):
        for storage in (auth.STORAGE,auth.PHOTOSHOP_STORAGE):
            def tracked(command):
                return SimpleNamespace(returncode=0,stdout='tracked' if 'ls-files' in command and command[-1]==storage.as_posix() else '',stderr='')
            prompt=Mock();self.assertEqual(self.migrate(prompt,tracked),1);prompt.assert_not_called()
            self.assertFalse(self.target.parent.exists())
    def test_nonignored_destination_rejected(self):
        def runner(command):
            return SimpleNamespace(returncode=1 if 'check-ignore' in command and 'photoshop-auth' in command[-1] else 0, stdout='', stderr='')
        prompt = Mock()
        self.assertEqual(self.migrate(prompt, runner), 1)
        prompt.assert_not_called()
        self.assertFalse(self.target.parent.exists())
    def test_unsafe_destination_acl_rejected_without_repair(self):
        self.target.parent.mkdir()
        self.target.write_bytes(TOKEN)
        before = self.snapshot(self.target), self.snapshot(self.target.parent)
        prompt = Mock()
        self.assertEqual(self.migrate(prompt), 1)
        prompt.assert_not_called()
        self.assertEqual(before, (self.snapshot(self.target), self.snapshot(self.target.parent)))
    def test_source_acl_changes_during_consent(self):
        def consent(_):
            with ExitStack() as stack:
                self.security.apply_protection(self.security.repair_handle(stack, self.source, directory=False), directory=False)
            return 'y'
        self.assertEqual(self.migrate(consent), 1)
        self.assertFalse(self.target.parent.exists())
    def test_written_bytes_must_equal_source_exactly(self):
        original = self.security.write_storage
        with patch.object(self.security, 'write_storage', side_effect=lambda h, p: original(h, b'z' * 64 + b'\n')):
            self.assertEqual(self.migrate(), 1)
        self.assertEqual(self.source.read_bytes(), TOKEN)
    def test_redirect_rejected(self):
        with patch.object(auth,'reject_redirects',side_effect=auth.AuthenticationError()):
            prompt=Mock();self.assertEqual(self.migrate(prompt),1);prompt.assert_not_called()
    def test_reparse_destination_rejected(self):
        other = self.root / 'redirect-target'
        other.mkdir()
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.target.parent), str(other)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        prompt = Mock()
        self.assertEqual(self.migrate(prompt), 1)
        prompt.assert_not_called()
        self.assertFalse(list(other.iterdir()))
    def test_runtime_prefers_new_protected_token(self):
        self.assertEqual(self.migrate(), 0)
        self.source.write_bytes(b'malformed')
        with patch.object(self.photoshop, 'ROOT', self.root / 'tools/lunitora_mcp'), \
                patch.object(self.photoshop, 'TOKEN_PATH', self.source):
            self.assertEqual(self.photoshop.load_token(), TOKEN.decode().strip())
    def test_runtime_corrupt_destination_never_falls_back(self):
        self.assertEqual(self.migrate(), 0)
        self.target.write_bytes(b'malformed')
        with patch.object(self.photoshop, 'ROOT', self.root / 'tools/lunitora_mcp'), \
                patch.object(self.photoshop, 'TOKEN_PATH', self.source):
            with self.assertRaises(self.photoshop.ConfigurationError):
                self.photoshop.load_token()
    def test_concurrent_git_change_during_consent(self):
        changed = False
        def runner(command):
            return SimpleNamespace(returncode=0, stdout='tracked' if changed and 'ls-files' in command else '', stderr='')
        def consent(_):
            nonlocal changed
            changed = True
            return 'y'
        self.assertEqual(self.migrate(consent, runner), 1)
        self.assertFalse(self.target.parent.exists())
    def test_hardlinked_destination_rejected(self):
        self.assertEqual(self.migrate(),0);os.link(self.target,self.root/'alias')
        prompt=Mock();self.assertEqual(self.migrate(prompt),1);prompt.assert_not_called()
    def test_directory_with_unrelated_artifact_rejected(self):
        self.assertEqual(self.migrate(),0);(self.target.parent/'unrelated').write_bytes(b'art')
        prompt=Mock();self.assertEqual(self.migrate(prompt),1);prompt.assert_not_called()
    def test_source_change_during_consent(self):
        def consent(_): self.source.write_bytes(b'z'*64);return 'y'
        self.assertEqual(self.migrate(consent),1);self.assertFalse(self.target.parent.exists())
    def test_destination_change_during_consent(self):
        def consent(_):
            self.target.parent.mkdir();self.target.write_bytes(TOKEN);return 'y'
        self.assertEqual(self.migrate(consent),1)
        self.assertEqual(self.target.read_bytes(),TOKEN)
    def test_source_identity_replacement_same_bytes(self):
        def consent(_): self.source.unlink();self.source.write_bytes(TOKEN);return 'y'
        self.assertEqual(self.migrate(consent),1);self.assertFalse(self.target.parent.exists())
    def test_source_pinned_against_writes_during_copy(self):
        original=self.security.write_storage
        def write(handle,payload):
            with self.assertRaises(OSError): self.source.write_bytes(b'z'*64)
            return original(handle,payload)
        with patch.object(self.security,'write_storage',side_effect=write):self.assertEqual(self.migrate(),0)
    def test_reopened_identity_change_rejected(self):
        original=self.security.pin;count=0
        def pin(stack,path,**kwargs):
            nonlocal count
            if path==self.target:
                count+=1
                if count==2:
                    path.unlink();path.write_bytes(TOKEN)
            return original(stack,path,**kwargs)
        with patch.object(self.security,'pin',side_effect=pin):self.assertEqual(self.migrate(),1)
    def test_secrets_absent_even_on_failure(self):
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err),patch.object(self.security,'write_storage',side_effect=ValueError(TOKEN.decode())):
            self.assertEqual(self.migrate(),1)
        self.assertNotIn(TOKEN.decode().strip(),out.getvalue()+err.getvalue()+'\n'.join(self.output))
    def test_setup_check_and_pair_prefer_destination(self):
        self.assertEqual(self.migrate(),0);self.source.write_bytes(b'malformed')
        for kwargs in ({},{'check':True},{'interactive':True,'replace_photoshop':True}):
            prompt=Mock(side_effect=AssertionError())
            result=auth.provision_authentication(self.root,'windows',('photoshop',),runner=git,secret_prompt=prompt,**kwargs)
            self.assertTrue(result['photoshop']['ready']);prompt.assert_not_called()
        self.assertEqual(self.target.read_bytes(),TOKEN)
    def test_fresh_pairing_uses_dedicated_storage(self):
        self.source.unlink()
        result=auth.provision_authentication(self.root,'windows',('photoshop',),runner=git,interactive=True,secret_prompt=lambda _: 'z'*64,emit=self.output.append)
        self.assertTrue(result['photoshop']['ready']);self.assertTrue(self.target.exists());self.assertFalse(self.source.exists())
    def test_protected_legacy_unchanged(self):
        with ExitStack() as stack:
            for p in (self.source,self.local):
                self.security.apply_protection(self.security.repair_handle(stack,p,directory=p.is_dir()),directory=p.is_dir())
        before=self.snapshot(self.source),self.snapshot(self.local)
        result=auth.provision_authentication(self.root,'windows',('photoshop',),runner=git)
        self.assertTrue(result['photoshop']['ready']);self.assertFalse(self.target.parent.exists())
        self.assertEqual(before,(self.snapshot(self.source),self.snapshot(self.local)))

class Contracts(unittest.TestCase):
    def test_mac_separate_no_dependencies_or_mutation(self):
        output=[]
        with patch.object(auth,'_reviewed_modules') as modules:
            self.assertEqual(migration.migrate(Path('.'),'macos',emit=output.append),1)
        modules.assert_not_called();self.assertIn('REQUIRES MAC',''.join(output))
    def test_worker_flag_forwarded(self):
        with patch.object(bootstrap, 'validate_repository'), \
                patch.object(bootstrap, 'platform_name', return_value='windows'), \
                patch.object(bootstrap, 'validated_host', return_value='C:/synthetic/python.exe'), \
                patch('subprocess.run', return_value=SimpleNamespace(returncode=0)) as worker:
            self.assertEqual(bootstrap.main(['--migrate-photoshop-auth']), 0)
        self.assertIn('--migrate-photoshop-auth', worker.call_args.args[0])
    def test_migration_bypasses_setup_mutations(self):
        with patch.object(bootstrap, 'validate_repository'), \
                patch.object(bootstrap, 'platform_name', return_value='windows'), \
                patch.object(bootstrap, 'validated_host', return_value=sys.executable), \
                patch.object(bootstrap.sys, 'prefix', sys.base_prefix), \
                patch.object(bootstrap, 'ensure_environment') as environment, \
                patch.object(bootstrap, 'bootstrap') as setup, \
                patch.object(migration, 'migrate', return_value=0) as migrate:
            self.assertEqual(bootstrap.main(['--migrate-photoshop-auth']), 0)
        migrate.assert_called_once()
        environment.assert_not_called()
        setup.assert_not_called()
    def test_check_combination_rejected(self):
        with patch.object(bootstrap,'validate_repository') as validate,patch('sys.stderr'),self.assertRaises(SystemExit):
            bootstrap.main(['--check','--migrate-photoshop-auth'])
        validate.assert_not_called()
