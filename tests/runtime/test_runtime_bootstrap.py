from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from core.runtime.bootstrap import RuntimeBootstrap

class BootstrapTests(unittest.TestCase):
    def make(self,env):
        def git_result(command, **_kwargs):
            if '--show-toplevel' in command:
                return SimpleNamespace(stdout='/project')
            return SimpleNamespace(stdout='a'*40)
        with patch('core.runtime.bootstrap.subprocess.run',side_effect=git_result):
            return RuntimeBootstrap.from_environment(project_root=Path('/project'),environment=env)
    def test_old_combined_keeps_legacy_paths(self):
        value=self.make({});self.assertEqual(value.mode,'combined');self.assertTrue(value.legacy_paths)
    def test_split_requires_explicit_absolute_stable_path(self):
        for env in ({'TURB_RUNTIME_MODE':'worker'},{'TURB_RUNTIME_MODE':'web','TURB_RUNTIME_DIR':'relative'}):
            with self.assertRaises(ValueError):self.make(env)
    def test_split_log_root_is_set_before_domain_import_and_preserves_explicit(self):
        value=self.make({'TURB_RUNTIME_MODE':'worker','TURB_RUNTIME_DIR':'/stable'})
        env={};value.prepare_log_environment(env);self.assertEqual(env['TASK_RUN_LOG_ROOT'],'/stable/logs')
        env={'TASK_RUN_LOG_ROOT':'/existing'};value.prepare_log_environment(env);self.assertEqual(env['TASK_RUN_LOG_ROOT'],'/existing')
    def test_invalid_role_and_instance_fail_before_side_effects(self):
        for env in ({'TURB_RUNTIME_MODE':'typo'},{'TURB_INSTANCE_ID':'a/b'}):
            with self.assertRaises(ValueError):self.make(env)

    def test_git_root_must_be_nonempty_and_absolute(self):
        root = Path.cwd()
        for output in ('', '.', root.name):
            with self.subTest(output=output):
                with patch('core.runtime.bootstrap.subprocess.run',
                           return_value=SimpleNamespace(stdout=output)) as run:
                    with self.assertRaisesRegex(ValueError, 'runtime_release_unavailable'):
                        RuntimeBootstrap.from_environment(project_root=root, environment={})
                self.assertEqual(run.call_count, 1)
