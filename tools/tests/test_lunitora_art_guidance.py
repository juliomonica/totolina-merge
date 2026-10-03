"""First-time Art reports remain local, honest and free of credential inspection."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).absolute().parents[1]))
from lunitora_machine.art_guidance import emit_first_time, MANIFEST
from lunitora_machine.readiness import summarize
from lunitora_machine.bootstrap import print_summary

class ArtGuidanceTests(unittest.TestCase):
    def test_order_manifest_panel_and_adobe_requirements(self):
        root = Path(__file__).absolute().parents[2]
        lines=[]
        # Guidance must not inspect even the existence of a live credential.
        with patch.object(Path, 'exists', side_effect=AssertionError('filesystem lookup')):
            emit_first_time(root, root / 'tools/lunitora_mcp/.local/photoshop-auth/pairing-token.txt', lines.append)
        text='\n'.join(lines)
        markers=['1. Install/open Adobe Creative Cloud','2. Install supported Adobe Photoshop','3. In Creative Cloud','4. Launch UDT','5. Launch Photoshop','6. With Photoshop running','7. In Photoshop open Plugins','8. From the repository root','9. The protected Lunitora','10. Privately open','11. Manually enter the SAME','12. Choose Connect','13. After active Codex','14. From Codex','15. Confirm Art readiness']
        positions=[text.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        manifest=json.loads((root/MANIFEST).read_text())
        html=(root/MANIFEST.parent/'index.html').read_text()
        self.assertIn(str(root/MANIFEST),text)
        self.assertIn(manifest['host']['minVersion'],text)
        self.assertIn(manifest['entrypoints'][0]['label']['default'],text)
        self.assertIn('type="password"',html)
        self.assertIn('Pairing token',html)
        self.assertIn('administrator privileges',text)
        self.assertIn('--migrate-photoshop-auth',text)
        self.assertIn('--repair-photoshop-auth',text)
        self.assertIn('--pair-photoshop',text)
        self.assertIn('Never paste the credential',text)
    def test_installed_apps_do_not_prove_manual_or_live_states(self):
        apps={name:{'path':'fixture'} for name in ('photoshop','udt','desktop')}
        integration={'photoshop':{'configuration':{'ready':True,'state':'already correct'},'authentication':{'ready':True,'state':'already correct'}}}
        report=summarize('windows',True,apps,integration=integration)['Art']
        self.assertEqual(report['photoshop_installed'],'DETECTED')
        self.assertEqual(report['udt_installed'],'DETECTED')
        self.assertEqual(report['protected_bridge_credential'],'already correct')
        for key in ('developer_mode_plugin_loading','photoshop_panel_paired','live_connection'):
            self.assertTrue(report[key].startswith('NOT CHECKED'))
        self.assertNotEqual(report['state'],'READY')
        self.assertIn('steps 4-7',report['next_first_time_step'])
    def test_missing_photoshop_identifies_first_install_step_without_blocking_core(self):
        report=summarize('windows',True,{'godot':{'path':'fixture'},'desktop':{'path':'fixture'}})
        self.assertEqual(report['Core']['state'],'READY')
        self.assertEqual(report['Game']['state'],'CONFIGURED')
        self.assertIn('Steps 1-2',report['Art']['next_first_time_step'])
        self.assertIn('Creative Cloud',report['Art']['next_first_time_step'])
    def test_missing_udt_identifies_development_step(self):
        report=summarize('windows',True,{'photoshop':{'path':'fixture'}})['Art']
        self.assertIn('Step 3',report['next_first_time_step'])
        self.assertIn('packaged-plugin',report['next_first_time_step'])
    def test_missing_credential_exposes_sanitized_action(self):
        apps={name:{'path':'fixture'} for name in ('photoshop','udt')}
        integration={'photoshop':{'configuration':{'ready':True,'state':'already correct'},'authentication':{'ready':False,'state':'migration required','reason':'Run --migrate-photoshop-auth'}}}
        report=summarize('windows',True,apps,integration=integration)['Art']
        self.assertEqual(report['protected_bridge_credential'],'migration required')
        self.assertIn('--migrate-photoshop-auth',report['next_first_time_step'])
    def test_uninspected_apps_not_assumed_missing(self):
        report=summarize('windows',False,{},applications_inspected=False)['Art']
        self.assertEqual(report['photoshop_installed'],'NOT CHECKED')
        self.assertEqual(report['udt_installed'],'NOT CHECKED')
        self.assertIn('inspection unavailable',report['next_first_time_step'])
    def test_printed_doctor_fields_are_independent_and_do_not_read_or_prompt(self):
        lines=[]
        with patch('builtins.input',side_effect=AssertionError('prompt')),patch.object(Path,'open',side_effect=AssertionError('read')):
            print_summary('windows',True,{},emit=lines.append)
        text='\n'.join(lines)
        for label in ('photoshop installed','udt installed','developer mode plugin loading','protected bridge credential','photoshop panel paired','live connection','next first time step'):
            self.assertIn(label+':',text)
