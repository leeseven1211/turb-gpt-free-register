"""任务中心特殊取消和受管取消复用同一集合事实入口。"""
import uuid
from unittest.mock import patch

from psycopg import Cursor

from core.codex import operation_service as codex
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import bulk_submission, store
from tests.support_pg import PostgresTestCase


class TaskCenterCancelCollectionTests(PostgresTestCase):
    def setUp(self):
        records.init()
        store.reset_ready()
        store.init()
        from core import account_task_store
        self.schema_patch = patch.object(account_task_store, '_SCHEMA', self.schema)
        self.schema_patch.start()
        self.addCleanup(self.schema_patch.stop)
        with patch.object(account_task_store, '_READY_KEY', ''):
            account_task_store.init()
        codex.register_actions()

    def tasks(self, count, prefix='cancel'):
        accounts = []
        for number in range(count):
            accounts.append(records.insert_row(records.ACCOUNTS, {
                'email': f'{prefix}{number}@example.test',
                'codex_credential_state': 'valid', 'codex_status': 'success'}))
        with store._connect() as conn:
            replies = bulk_submission.create_specs([
                {'task_type': 'codex_retry', 'account_id': account_id,
                 'email': f'{prefix}{number}@example.test', 'source_id': uuid.uuid4().hex}
                for number, account_id in enumerate(accounts)], conn=conn)
        return store.get_action_tasks_many([row['task_id'] for row in replies])

    def cancel(self, tasks):
        from core.operations.task_center_cancel import accept_cancellations
        queries = []
        original = Cursor.execute
        def measured(cursor, query, *args, **kwargs):
            queries.append(str(query))
            return original(cursor, query, *args, **kwargs)
        with patch.object(Cursor, 'execute', measured), patch.object(task_gateway, 'notify_dispatch'):
            result = accept_cancellations(tasks)
        return result, queries

    def test_twenty_custom_codex_cancels_use_constant_queries_and_preserve_valid_assets(self):
        first, one = self.cancel(self.tasks(1, 'one'))
        many, twenty = self.cancel(self.tasks(20, 'twenty'))
        self.assertEqual(len(twenty), len(one))
        self.assertLessEqual(len(twenty), 20)
        self.assertTrue(all(status == 200 and payload['state'] == 'cancelled'
                            for payload, status in [*first.values(), *many.values()]))
        self.assertTrue(all(row['codex_status'] == 'success' and row['codex_credential_state'] == 'valid'
                            and row['codex_execution_status'] == 'empty'
                            and row['codex_last_run_status'] == 'cancelled'
                            and row['codex_active_run_id'] is None
                            for row in records.list_rows(records.ACCOUNTS)))

    def test_status_changed_after_snapshot_is_skipped_and_running_task_is_not_selected(self):
        tasks = self.tasks(3)
        task_ids = list(tasks)
        run_ids = [tasks[task_id]['last_run_id'] for task_id in task_ids]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='running' WHERE id=%s", (run_ids[0],))
        tasks[task_ids[1]]['status'] = 'running'
        result, _ = self.cancel(tasks)
        self.assertEqual(result[task_ids[0]][1], 409)
        self.assertNotIn(task_ids[1], result)
        self.assertEqual(result[task_ids[2]][0]['state'], 'cancelled')
        self.assertEqual(store.get_run(run_ids[0])['status'], 'running')
        self.assertEqual(store.get_run(run_ids[1])['status'], 'queued')

    def test_known_custom_cancel_does_not_call_single_runtime_or_account_updates(self):
        tasks = self.tasks(4)
        with patch('core.codex.operation_service.request_cancel', side_effect=AssertionError('single cancel')), \
             patch('core.db.update_account_codex_operation_state', side_effect=AssertionError('single account projection')):
            result, _ = self.cancel(tasks)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(payload['ok'] for payload, _ in result.values()))

    def test_cancel_projection_preserves_single_email_lookup_scope_and_real_log_path(self):
        tasks = self.tasks(1, 'Case')
        task = next(iter(tasks.values()))
        sibling = records.insert_row(records.ACCOUNTS, {
            'email': task['email_snapshot'].swapcase(), 'codex_execution_status': 'running',
            'codex_active_run_id': 999, 'codex_last_run_status': 'success'})
        before = records.get_row(records.ACCOUNTS, sibling)
        with patch('core.operations.task_center_cancel.run_log.append') as append:
            result, _ = self.cancel(tasks)
        self.assertEqual(result[task['id']][1], 200)
        self.assertEqual(records.get_row(records.ACCOUNTS, sibling), before)
        append.assert_called_once()
        self.assertEqual(append.call_args.args[0], store.get_run(task['last_run_id'])['log_file'])
