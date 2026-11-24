"""停用邮件本地集合写入与共享 HME 受理的真实 PostgreSQL 契约。"""
from unittest.mock import Mock, patch

from core.accounts.deactivation import mail_scan
from core.storage import records as store
from core.storage.operations import common, schema
from tests.email.test_email_collection_reads import CursorCounter
from tests.support_pg import PostgresTestCase


class DeactivationMailCollectionTests(PostgresTestCase):
    def test_collection_projection_preserves_history_restoration_and_codex_facts(self):
        from core.storage.accounts import deactivation_mail
        self.seed(store.ACCOUNTS, [
            {'id': 1, 'email': 'dead@example.test'},
            {'id': 2, 'email': 'restored@example.test', 'account_status': 'active',
             'account_restored_at': '2026-11-20T00:00:00Z',
             'account_deactivation_history': [{'deactivation_mail': {'message_id': 'old-id'}}]},
            {'id': 3, 'email': 'unsupported@example.test', 'deactivation_mail_checked_at': 'old-check'},
        ])
        store.insert_row(store.CODEX_CREDENTIALS, {'email': 'DEAD@example.test', 'filename': 'dead.json'})
        queries = []
        with store.transaction() as conn:
            updated = deactivation_mail.update_many({
                1: {'status': 'success', 'detected': True, 'subject': 'Deactivated'},
                2: {'status': 'success', 'detected': True, 'message_id': 'old-id'},
                3: {'status': 'unsupported', 'error': 'unsupported', 'preserve_checked_at': True},
            }, conn=CursorCounter(conn, queries))
        self.assertEqual(set(updated), {1, 2, 3})
        self.assertLessEqual(len(queries), 4)
        deactivation_mail.update_many({1: {'status': 'success', 'detected': False}})
        dead = store.get_row(store.ACCOUNTS, 1)
        self.assertTrue(dead['deactivation_mail_detected'])
        self.assertEqual(dead['deactivation_mail_subject'], 'Deactivated')
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f'SELECT deactivated FROM {store._qualified(store.ACCOUNTS)} WHERE id=1')
            self.assertTrue(cur.fetchone()['deactivated'])
        self.assertEqual(store.get_row(store.ACCOUNTS, 2)['account_status'], 'active')
        self.assertFalse(store.get_row(store.ACCOUNTS, 2).get('deactivation_mail_detected'))
        self.assertEqual(store.get_row(store.ACCOUNTS, 3)['deactivation_mail_checked_at'], 'old-check')
        credential = store.get_row_by(store.CODEX_CREDENTIALS, 'filename', 'dead.json')
        self.assertEqual(credential['oauth_status'], 'deactivated')
        self.assertTrue(credential['oauth_reauth_required'])

    def test_enqueue_uses_collection_specs_and_global_hme_anchor(self):
        self.seed(store.ACCOUNTS, [
            {'id': 1, 'email': 'anchor@icloud.test', 'email_source': 'icloud_hide'},
            {'id': 2, 'email': 'alias@icloud.test', 'email_source': 'icloud_hide'},
            {'id': 3, 'email': 'cloud@example.test', 'email_source': 'cloudflare'},
            {'id': 4, 'email': 'unsupported@example.test', 'email_source': 'email_butler'},
        ])
        with patch.object(mail_scan.db, 'get_account', side_effect=AssertionError('per-account read')), \
             patch.object(mail_scan.db, 'update_account_deactivation_mail', side_effect=AssertionError('per-account update')), \
             patch.object(mail_scan.account_task_store, 'notify_dispatch'):
            accepted = mail_scan.enqueue_bulk([2, 3, 4], account_request_key='collection-request')
            replay = mail_scan.enqueue_bulk([2, 3, 4], account_request_key='collection-request')
            busy = mail_scan.enqueue_bulk([1], account_request_key='another-request')
        self.assertEqual(len(accepted['started']), 2)
        self.assertEqual(len(accepted['skipped']), 1)
        self.assertTrue(all(item['reused'] for item in replay['started']))
        self.assertEqual([item['run_id'] for item in accepted['started']], [item['run_id'] for item in replay['started']])
        self.assertEqual(len(busy['busy']), 1)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT account_id,data FROM {common._table('operation_runs')} ORDER BY id")
            runs = cur.fetchall()
        hme = next(row for row in runs if row['data'].get('bulk'))
        self.assertEqual(hme['account_id'], 1)
        self.assertEqual(hme['data']['account_batches'], [[{'account_id': 2, 'email': 'alias@icloud.test'}]])
        self.assertEqual(store.get_row(store.ACCOUNTS, 4)['deactivation_mail_scan_status'], 'unsupported')

    def test_hme_projection_uses_collections_and_remote_only_once(self):
        self.seed(store.ACCOUNTS, [{'id': i, 'email': f'{i}@icloud.test', 'email_source': 'icloud_hide'} for i in range(1, 5)])
        context = Mock()
        context.is_cancel_requested.return_value = False
        with patch.object(mail_scan.db, 'update_account_deactivation_mail', side_effect=AssertionError('per-account update')), \
             patch.object(mail_scan, 'scan_hme_deactivation_bulk', return_value={
                 '1@icloud.test': {'ok': True, 'detected': True},
                 '2@icloud.test': {'ok': True, 'detected': False},
                 '3@icloud.test': {'ok': False, 'error_code': 'signal_scan_unsupported'},
             }) as remote:
            mail_scan._scan_hme_group(context, [{'account_id': i, 'email': f'{i}@icloud.test'} for i in range(1, 5)], 'manual_bulk')
        remote.assert_called_once()
        self.assertEqual(context.finish.call_args.kwargs['result_summary']['failed_count'], 1)
        self.assertEqual([store.get_row(store.ACCOUNTS, i)['deactivation_mail_scan_status'] for i in range(1, 5)],
                         ['success', 'success', 'unsupported', 'failed'])

    def test_cloudflare_acceptance_does_not_lock_the_unrelated_hme_anchor(self):
        self.seed(store.ACCOUNTS, [
            {'id': 1, 'email': 'anchor@icloud.test', 'email_source': 'icloud_hide'},
            {'id': 2, 'email': 'cloud@example.test', 'email_source': 'cloudflare'},
        ])
        load = mail_scan.mail_store.load_many
        locked_ids = []
        def load_selected(account_ids, *, conn):
            locked_ids.append(list(account_ids))
            return load(account_ids, conn=conn)
        with patch.object(mail_scan.mail_store, 'load_many', side_effect=load_selected), \
             patch.object(mail_scan.account_task_store, 'notify_dispatch'):
            accepted = mail_scan.enqueue_bulk([2])
        self.assertEqual(1, len(accepted['started']))
        self.assertEqual([[2]], locked_ids)

    def test_hme_relocks_with_global_anchor_without_rolling_back_the_callers_transaction(self):
        self.seed(store.ACCOUNTS, [
            {'id': 1, 'email': 'anchor@icloud.test', 'email_source': 'icloud_hide'},
            {'id': 2, 'email': 'alias@icloud.test', 'email_source': 'icloud_hide'},
            {'id': 3, 'email': 'sentinel@example.test'},
        ])
        schema.init_operation_schema()
        load = mail_scan.mail_store.load_many
        locked_ids = []
        def load_selected(account_ids, *, conn):
            locked_ids.append(list(account_ids))
            return load(account_ids, conn=conn)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._qualified(store.ACCOUNTS)} SET data=data || %s::jsonb WHERE id=3",
                        ('{"caller_write": true}',))
            token = common._SETTLEMENT_CONNECTION.set(conn)
            try:
                with patch.object(mail_scan.mail_store, 'load_many', side_effect=load_selected), \
                     patch.object(mail_scan.account_task_store, 'notify_dispatch'):
                    accepted = mail_scan.enqueue_bulk([2])
            finally:
                common._SETTLEMENT_CONNECTION.reset(token)
        self.assertEqual([[2], [1, 2]], locked_ids)
        self.assertEqual(1, len(accepted['started']))
        self.assertTrue(store.get_row(store.ACCOUNTS, 3)['caller_write'])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT account_id FROM {common._table('operation_runs')}")
            self.assertEqual(1, cur.fetchone()['account_id'])

    def test_recovery_collection_does_not_overwrite_newer_queued_projection(self):
        self.seed(store.ACCOUNTS, [
            {'id': 1, 'email': 'old@icloud.test', 'deactivation_mail_scan_status': 'running',
             'deactivation_mail_scan_started_at': '2026-11-20T00:00:00Z', 'deactivation_mail_checked_at': 'prior'},
            {'id': 2, 'email': 'new@icloud.test', 'deactivation_mail_scan_status': 'queued',
             'deactivation_mail_scan_queued_at': '2026-11-23T00:00:00Z'},
        ])
        run = {'id': 88, 'completed_at': '2026-11-22T00:00:00Z', 'trigger': 'scheduled',
               'data': {'bulk': True, 'account_batches': [[{'account_id': 1, 'email': 'old@icloud.test'},
                                                            {'account_id': 2, 'email': 'new@icloud.test'}]]}}
        with patch.object(mail_scan.operation_runtime_store, 'list_interrupted_runtime_runs', return_value=[run]), \
             patch.object(mail_scan.operation_runtime_store, 'mark_runtime_run_projection_reconciled'), \
             patch.object(mail_scan.db, 'get_account', side_effect=AssertionError('per-account recovery read')), \
             patch.object(mail_scan.db, 'update_account_deactivation_mail', side_effect=AssertionError('per-account recovery write')):
            self.assertEqual(mail_scan.reconcile_interrupted_scans(), 1)
        self.assertEqual(store.get_row(store.ACCOUNTS, 1)['deactivation_mail_scan_status'], 'failed')
        self.assertEqual(store.get_row(store.ACCOUNTS, 1)['deactivation_mail_checked_at'], 'prior')
        self.assertEqual(store.get_row(store.ACCOUNTS, 2)['deactivation_mail_scan_status'], 'queued')

    def test_cloudflare_acceptance_sql_budget_is_independent_of_account_count(self):
        from contextlib import contextmanager
        self.seed(store.ACCOUNTS, [{'id': i, 'email': f'budget{i}@example.test', 'email_source': 'cloudflare'} for i in range(1, 82)])
        store.init()
        schema.init_operation_schema()
        connect = common._connect
        def accept(ids):
            queries = []
            @contextmanager
            def counted():
                with connect() as conn:
                    yield CursorCounter(conn, queries)
            with patch.object(common, '_connect', counted), patch.object(mail_scan.account_task_store, 'notify_dispatch'):
                result = mail_scan.enqueue_bulk(ids)
            self.assertEqual(len(result['started']), len(ids))
            return len(queries)
        one = accept([1])
        eighty = accept(list(range(2, 82)))
        self.assertEqual(eighty, one)
        self.assertLessEqual(eighty, 15)

    def test_large_acceptance_bounds_sql_payloads_and_notifies_only_after_commit(self):
        self.seed(store.ACCOUNTS, [
            {'id': i, 'email': f'chunk{i}@example.test', 'email_source': 'cloudflare'}
            for i in range(1, 502)
        ])
        create_specs = mail_scan.bulk_submission.create_specs
        sizes = []
        def create_block(specifications, *, conn):
            sizes.append(len(specifications))
            return create_specs(specifications, conn=conn)
        with patch.object(mail_scan.bulk_submission, 'create_specs', side_effect=create_block), \
             patch.object(mail_scan, 'register_operation_handlers', side_effect=AssertionError('Web executor registration')), \
             patch.object(mail_scan.account_task_store, 'notify_dispatch') as notify:
            accepted = mail_scan.enqueue_bulk(list(range(1, 502)))
        self.assertEqual([500, 1], sizes)
        self.assertEqual(501, len(accepted['started']))
        notify.assert_called_once()
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_runs')} WHERE task_id IS NOT NULL")
            self.assertEqual(501, cur.fetchone()['n'])
        self.assertEqual(store.get_row(store.ACCOUNTS, 501)['deactivation_mail_scan_status'], 'queued')
