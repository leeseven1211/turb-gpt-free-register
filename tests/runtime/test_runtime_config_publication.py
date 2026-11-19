"""Phase 6 T5 publication regressions against the real config package."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

import config
from config import runtime, schema, env_loader
from core.storage import postgres


class ActualReloadTests(unittest.TestCase):
    def setUp(self):
        self.env_before = dict(os.environ)
        self.state = config.capture_reload_state()
        config._APPLIED_DB_REVISION = None
        no_db = patch.object(postgres, 'connect', side_effect=AssertionError('real DB forbidden'))
        no_db.start()
        self.addCleanup(no_db.stop)
        self.repository = patch.object(runtime, '_repository', side_effect=AssertionError('no DB access permitted'))
        self.repository.start()
        self.addCleanup(self.repository.stop)

    def tearDown(self):
        config.restore_reload_state(self.state)
        os.environ.clear()
        os.environ.update(self.env_before)

    def test_exact_values_published_without_reading_bootstrap_file_or_database(self):
        os.environ.update(DATABASE_URL='fixture-never-connected', PYTHON_DOTENV_DISABLED='0', TURB_INSTANCE_ID='boot')
        old = schema.non_sensitive_snapshot()
        with patch.object(env_loader, 'read_env_file', side_effect=AssertionError('physical file forbidden')):
            applied = config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'17'}, 23)
        current = schema.non_sensitive_snapshot()
        self.assertEqual(current['TASK_CENTER_RETENTION_DAYS'], 17)
        self.assertEqual(old['TASK_CENTER_RETENTION_DAYS'], self.state['snapshot']['TASK_CENTER_RETENTION_DAYS'])
        self.assertIsNot(old, current)
        self.assertEqual(applied, (23, old.revision + 1))
        self.assertEqual(os.environ['TURB_INSTANCE_ID'], 'boot')
        self.assertEqual(config.TASK_CENTER_RETENTION_DAYS, 17)

    def test_strict_invalid_keeps_exact_snapshot_modules_env_and_runtime_cache(self):
        old = schema.non_sensitive_snapshot()
        cache = runtime.capture_state()
        with self.assertRaises(schema.ConfigValidationError):
            config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'broken-secret'}, 31)
        self.assertIs(schema.non_sensitive_snapshot(), old)
        self.assertEqual(runtime.capture_state(), cache)
        self.assertEqual(dict(os.environ), self.env_before)

    def test_module_failure_rolls_back_actual_module_namespaces_and_snapshot(self):
        old = schema.non_sensitive_snapshot()
        before = config.TASK_CENTER_RETENTION_DAYS
        original = config._importlib.reload
        def reload(module):
            result = original(module)
            if module.__name__ == 'config.operations':
                raise RuntimeError('reload_failure')
            return result
        with patch.object(config._importlib, 'reload', side_effect=reload):
            with self.assertRaisesRegex(RuntimeError, 'reload_failure'):
                config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'18'}, 34)
        self.assertIs(schema.non_sensitive_snapshot(), old)
        self.assertEqual(config.TASK_CENTER_RETENTION_DAYS, before)
        self.assertEqual(sys.modules['config.operations'].TASK_CENTER_RETENTION_DAYS, before)
        self.assertEqual(dict(os.environ), self.env_before)

    def test_before_publish_failure_never_exposes_candidate(self):
        old = schema.non_sensitive_snapshot()
        def guard():
            self.assertIs(schema.non_sensitive_snapshot(), old)
            raise TimeoutError('config_timeout')
        with patch.object(schema, 'publish_config_snapshot', wraps=schema.publish_config_snapshot) as publish:
            with self.assertRaises(TimeoutError):
                config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'19'}, 35, before_publish=guard)
            publish.assert_not_called()
        self.assertIs(schema.non_sensitive_snapshot(), old)
        self.assertEqual(dict(os.environ), self.env_before)

    def test_publisher_failure_restores_runtime_projection_and_module_values(self):
        old = schema.non_sensitive_snapshot()
        with patch.object(schema, 'publish_config_snapshot', side_effect=RuntimeError('publication_failed')):
            with self.assertRaisesRegex(RuntimeError, 'publication_failed'):
                config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'20'}, 36)
        self.assertIs(schema.non_sensitive_snapshot(), old)
        self.assertEqual(dict(os.environ), self.env_before)
        self.assertEqual(config.TASK_CENTER_RETENTION_DAYS, old['TASK_CENTER_RETENTION_DAYS'])

    def test_fence_checks_after_snapshot_construction_before_reference_swap(self):
        old = schema.non_sensitive_snapshot()
        expired = [False]
        original = schema.ConfigSnapshot
        class DelayedSnapshot(original):
            def __init__(self, values, sources, revision):
                super().__init__(values, sources, revision)
                if revision > old.revision:
                    expired[0] = True
        candidate = schema.build_non_sensitive_snapshot({'TASK_CENTER_RETENTION_DAYS':'33'})
        def guard():
            if expired[0]:
                raise TimeoutError('late_snapshot_construction')
        with patch.object(schema, 'ConfigSnapshot', DelayedSnapshot):
            # Construct a compatible candidate before the publication-only delay.
            prepared = DelayedSnapshot(candidate.values, candidate.sources, 0)
            with self.assertRaises(TimeoutError):
                schema.publish_config_snapshot(prepared, before_publish=guard)
        self.assertIs(schema.non_sensitive_snapshot(), old)

    def test_bootstrap_in_database_is_rejected_and_process_identity_unchanged(self):
        os.environ['TURB_INSTANCE_ID'] = 'stable'
        for key in ('TURB_RUNTIME_MODE','TURB_INSTANCE_ID','TURB_RUNTIME_DIR','DATABASE_URL'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'bootstrap'):
                config.apply_runtime_snapshot({key:'tampered'}, 2)
        self.assertEqual(os.environ['TURB_INSTANCE_ID'], 'stable')

    def test_old_observer_read_cannot_overwrite_newer_web_publication(self):
        with config.deferred_publication() as holder:
            holder['candidate'] = schema.build_non_sensitive_snapshot({'TASK_CENTER_RETENTION_DAYS':'23'}, strict=True)
            holder['db_revision'] = 51
        current = schema.non_sensitive_snapshot()
        result = config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'22'}, 50)
        self.assertEqual(result, (51, current.revision))
        self.assertIs(schema.non_sensitive_snapshot(), current)
        self.assertEqual(current['TASK_CENTER_RETENTION_DAYS'], 23)

    def test_nested_publication_refused_so_success_cannot_precede_outer_commit(self):
        with config.deferred_publication(), self.assertRaisesRegex(RuntimeError, 'nested'):
            config.apply_runtime_snapshot({'TASK_CENTER_RETENTION_DAYS':'24'}, 60)


if __name__ == '__main__':
    unittest.main()
