"""Phase 6 T5 web receipts against the product editor and fake persistence."""
from contextlib import contextmanager
import unittest
from unittest.mock import patch

import config
from config import runtime, schema, env_loader
from tests.runtime import test_runtime_config_publication as reload_tests
from webui import config_editor as editor


class WebReceiptTests(unittest.TestCase):
    setUp = reload_tests.ActualReloadTests.setUp
    tearDown = reload_tests.ActualReloadTests.tearDown
    def test_save_receipt_db_revision_is_separate_from_local_and_worker(self):
        old=schema.non_sensitive_snapshot()
        data={'TASK_CENTER_RETENTION_DAYS':'7'}
        class Repository:
            def current_revision(self,*,conn):
                self.connection=conn
                return 81
        repository=Repository()
        connection=object()
        @contextmanager
        def transaction(): yield connection
        def write(updates):
            data.update(updates)
            runtime._project(data,read_file=False)
            return list(updates)
        with (patch.object(runtime,'database_enabled',return_value=True),
              patch.object(runtime,'persistence_transaction',transaction),
              patch.object(runtime,'write_persisted_values',side_effect=write),
              patch.object(runtime,'load_values',side_effect=lambda **kwargs:dict(data)),
              patch.object(runtime,'_repository',return_value=repository),
              patch.object(env_loader,'env_file_lock',transaction)):
            result=editor.update_config({'TASK_CENTER_RETENTION_DAYS':27})
        self.assertIs(repository.connection,connection)
        self.assertEqual(result['persisted_db_revision'],81)
        self.assertEqual(result['local_snapshot_revision'],old.revision+1)
        self.assertEqual(result['worker_application'],{'state':'unknown','applied_db_revision':None})
        self.assertTrue(result['web_reloaded'])
        self.assertEqual(config._APPLIED_DB_REVISION,81)

    def test_commit_failure_does_not_publish_snapshot_or_db_applied_marker(self):
        old=schema.non_sensitive_snapshot()
        data={'TASK_CENTER_RETENTION_DAYS':'7'}
        class Repository:
            def current_revision(self,*,conn): return 82
        @contextmanager
        def transaction():
            yield object()
            raise RuntimeError('synthetic_commit_failure')
        @contextmanager
        def file_lock(): yield
        def write(updates):
            data.update(updates)
            runtime._project(data,read_file=False)
            return list(updates)
        with (patch.object(runtime,'database_enabled',return_value=True),
              patch.object(runtime,'persistence_transaction',transaction),
              patch.object(runtime,'write_persisted_values',side_effect=write),
              patch.object(runtime,'load_values',side_effect=lambda **kwargs:dict(data)),
              patch.object(runtime,'_repository',return_value=Repository()),
              patch.object(env_loader,'env_file_lock',file_lock)):
            with self.assertRaisesRegex(RuntimeError,'synthetic_commit_failure'):
                editor.update_config({'TASK_CENTER_RETENTION_DAYS':28})
        self.assertIs(schema.non_sensitive_snapshot(),old)
        self.assertIsNone(config._APPLIED_DB_REVISION)

if __name__=='__main__': unittest.main()
