"""邮箱换绑受理一次集合持久化，执行与远端响应边界保持领域原样。"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import logging
import unittest
from unittest.mock import patch

from flask import Flask

from core.accounts.email_change import service
from core.storage import records
from core.storage.operations import common, store as operations
from tests.email.test_email_collection_reads import CursorCounter
from tests.support_pg import PostgresTestCase


class EmailChangeBulkSubmissionTests(PostgresTestCase):
    def setUp(self):
        records.init()
        operations.reset_ready()
        operations.init()
        self.ready = patch('core.runtime.capabilities.require_email_source', return_value=(True, ''))
        self.ready.start()
        self.addCleanup(self.ready.stop)

    def row(self, index, **extra):
        return records.insert_row(records.ACCOUNTS, {'email': f'change{index}@example.test',
            'created_at': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
            'access_token': 'fixture-at', **extra})

    def test_bulk_creates_specs_collectively_with_one_snapshot_and_stable_ordinals(self):
        ids = [self.row(number) for number in range(15)]
        queries = []
        original = common._connect
        @contextmanager
        def counted():
            with original() as conn:
                yield CursorCounter(conn, queries)
        snapshot = service._config_snapshot()
        with patch.object(service, 'submit_email_change', side_effect=AssertionError('不循环单条提交')), \
             patch.object(common, '_connect', side_effect=counted), \
             patch.object(service, 'register_operation_handlers', side_effect=AssertionError('Web 不注册执行 handler')), \
             patch.object(service, '_config_snapshot', return_value=snapshot) as capture, \
             patch.object(service.task_gateway, 'notify_dispatch') as notify:
            result = service.submit_email_change_bulk(ids + [ids[0]], source='outlook', idempotency_key='bulk-change')
        self.assertEqual((result['started_count'], result['skipped_count']), (15, 0))
        self.assertLessEqual(len(queries), 18, '\n'.join(queries))
        self.assertEqual(capture.call_count, 1)
        self.assertEqual(notify.call_count, 1)
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT t.account_id,i.ordinal,r.data FROM {operations._table("operation_tasks")} t '
                f'JOIN {operations._table("operation_batch_items")} i ON i.task_id=t.id '
                f'JOIN {operations._table("operation_runs")} r ON r.id=i.run_id '
                'WHERE i.batch_id=%s ORDER BY ordinal', (result['batch_id'],))
            rows = list(cur.fetchall())
        self.assertEqual([(row['account_id'], row['ordinal']) for row in rows], list(zip(ids, range(1,16))))
        self.assertTrue(all(row['data']['email_source'] == 'outlook' for row in rows))
        self.assertNotIn('fixture-at', str(result))

    def test_mixed_qualification_and_replay_do_not_create_orphan_batches(self):
        good = self.row('good')
        missing_token = self.row('token', access_token='')
        unknown = self.row('unknown', email_change_status='request_unknown')
        busy = self.row('busy')
        operations.create_runtime_task(task_type='live_check', account_id=busy, email='changebusy@example.test')
        ids = [good, missing_token, unknown, busy, 99999]
        with patch.object(service.task_gateway, 'notify_dispatch'):
            first = service.submit_email_change_bulk(ids, source='outlook', idempotency_key='mixed')
            second = service.submit_email_change_bulk(ids, source='outlook', idempotency_key='mixed')
        self.assertEqual((first['started_count'], first['skipped_count']), (1, 4))
        self.assertEqual(first['batch_id'], second['batch_id'])
        self.assertEqual(first['started'][0]['run_id'], second['started'][0]['run_id'])
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM {operations._table("operation_batches")} WHERE batch_type=%s', ('email_change',))
            self.assertEqual(cur.fetchone()['n'], 1)

    def test_specs_failure_rolls_back_batch_and_all_tasks(self):
        ids = [self.row(number) for number in range(3)]
        from core.storage.operations import bulk_submission
        original = bulk_submission.create_specs
        def fail(specs, *, conn):
            original(specs, conn=conn)
            raise RuntimeError('块提交前故障')
        with patch.object(bulk_submission, 'create_specs', side_effect=fail), self.assertRaisesRegex(RuntimeError, '块提交前故障'):
            service.submit_email_change_bulk(ids, source='outlook')
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM {operations._table("operation_tasks")} WHERE task_type=%s', ('email_change',))
            self.assertEqual(cur.fetchone()['n'], 0)
            cur.execute(f'SELECT count(*) AS n FROM {operations._table("operation_batches")} WHERE batch_type=%s', ('email_change',))
            self.assertEqual(cur.fetchone()['n'], 0)

    def test_same_request_rejects_changed_targets_or_source_and_preserves_first_snapshot(self):
        first_id, second_id = self.row('first'), self.row('second')
        with patch.object(service.task_gateway, 'notify_dispatch'):
            first = service.submit_email_change_bulk([first_id], source='outlook', idempotency_key='fixed')
            with self.assertRaisesRegex(ValueError, 'idempotency_key_conflict'):
                service.submit_email_change_bulk([second_id], source='outlook', idempotency_key='fixed')
            with patch.object(service, '_config_snapshot', side_effect=AssertionError('重放不重捕获配置')):
                replay = service.submit_email_change_bulk([first_id], source='outlook', idempotency_key='fixed')
        self.assertEqual(replay, first)

    def test_concurrent_identical_requests_commit_one_original_batch(self):
        from concurrent.futures import ThreadPoolExecutor
        ids = [self.row(number) for number in range(4)]
        with patch.object(service.task_gateway, 'notify_dispatch'), ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: service.submit_email_change_bulk(ids,
                source='outlook', idempotency_key='parallel-fixed'), range(2)))
        self.assertEqual(results[0], results[1])
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT count(*) AS n FROM {operations._table("operation_batches")} WHERE batch_type=%s', ('email_change',))
            self.assertEqual(cur.fetchone()['n'], 1)


class EmailChangeBulkRouteTests(unittest.TestCase):
    def setUp(self):
        from webui import runtime
        from webui.routes.accounts import create_accounts_blueprint

        self.app = Flask("email-change-bulk-routes")
        self.app.register_blueprint(create_accounts_blueprint(
            runtime.WebUIContext(self.app, logging.getLogger("email-change-bulk-routes")),
        ))

    def test_header_request_key_reaches_collection_submission(self):
        with patch.object(service, 'submit_email_change_bulk', return_value={
            'accepted': True, 'batch_id': 1, 'started': [{'account_id': 7}],
        }) as submit:
            response = self.app.test_client().post('/api/accounts/email-change-bulk',
                json={'account_ids': [7], 'source': 'outlook'},
                headers={'X-Account-Request-Key': '0123456789abcdef0123456789abcdef'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(submit.call_args.kwargs['idempotency_key'], '0123456789abcdef0123456789abcdef')

    def test_request_key_conflict_is_http_409(self):
        with patch.object(service, 'submit_email_change_bulk',
                side_effect=ValueError('idempotency_key_conflict')):
            response = self.app.test_client().post('/api/accounts/email-change-bulk',
                json={'account_ids': [7], 'source': 'outlook'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['error'], 'idempotency_key_conflict')

    def test_special_bulk_receipts_keep_large_identifiers_exact(self):
        from core.accounts.deactivation import mail_scan

        large = 2**53 + 1
        with patch.object(service, 'submit_email_change_bulk', return_value={
            'accepted': True, 'batch_id': large,
            'started': [{'account_id': large, 'task_id': large + 1, 'run_id': large + 2}],
        }):
            response = self.app.test_client().post('/api/accounts/email-change-bulk',
                json={'account_ids': [str(large)], 'source': 'outlook'})
        self.assertEqual(response.status_code, 202)
        receipt = response.get_json()
        self.assertEqual(receipt['batch_id'], str(large))
        self.assertEqual(receipt['started'][0]['run_id'], str(large + 2))
        with patch("core.runtime.capabilities.require_feature", return_value=(True, "")), \
             patch.object(mail_scan, 'enqueue_bulk', return_value={
                 'batch_id': large,
                 'started': [{'id': large, 'task_id': large + 1, 'run_id': large + 2}],
             }), patch.object(mail_scan, 'queue_settings', return_value={}):
            response = self.app.test_client().post('/api/accounts/check-deactivation-mail-bulk',
                json={'account_ids': [str(large)]})
        self.assertEqual(response.status_code, 202)
        receipt = response.get_json()
        self.assertEqual(receipt['batch_id'], str(large))
        self.assertEqual(receipt['started'][0]['id'], str(large))
        self.assertEqual(receipt['started'][0]['run_id'], str(large + 2))
