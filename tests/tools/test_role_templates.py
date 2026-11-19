from pathlib import Path
import plistlib
import unittest
ROOT=Path(__file__).resolve().parents[2]
class TemplateTests(unittest.TestCase):
    def test_launchd_templates_are_independent_foreground_roles_with_finite_stop(self):
        values=[plistlib.loads((ROOT/f'deploy/launchd/local.turb.{role}.plist.example').read_bytes()) for role in ('web','worker')]
        self.assertNotEqual(values[0]['Label'],values[1]['Label'])
        for role,value in zip(('web','worker'),values):
            self.assertEqual(value['ExitTimeOut'],60);self.assertEqual(value['EnvironmentVariables']['TURB_RUNTIME_MODE'],role);self.assertEqual(value['EnvironmentVariables']['TURB_RUNTIME_MANAGER'],'launchd');self.assertTrue(all(isinstance(item,str) for item in value['EnvironmentVariables'].values()));self.assertNotIn('sh',value['ProgramArguments']);self.assertEqual(value['Umask'],0o077)
            arguments=value['ProgramArguments']
            self.assertEqual(arguments[arguments.index('--shutdown-timeout')+1],'55')
    def test_systemd_split_templates_have_no_stop_propagation_and_combined_is_separate(self):
        for role in ('web','worker'):
            source=(ROOT/f'deploy/systemd/turb-{role}@.service').read_text();self.assertIn('Type=exec',source);self.assertIn('TimeoutStopSec=90',source);self.assertIn(f'Environment=TURB_RUNTIME_MODE={role}',source);self.assertIn('Environment=TURB_RUNTIME_MANAGER=systemd',source)
            for key in ('BindsTo=','PartOf=','Requires=','nohup','--preload'):self.assertNotIn(key,source)
        self.assertNotIn('--server waitress',(ROOT/'deploy/systemd/turb-gpt-free-register.service').read_text())
if __name__=='__main__':unittest.main()
