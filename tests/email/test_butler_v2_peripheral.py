"""在隔离 PostgreSQL 验证 v2 本地事实、历史意图恢复和退租边界。"""
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import patch

from core import db
from core.email.email_butler import client, service_facts, usage_reports
from core.storage import records as store
from core.storage.email import local_imports
from tests.support_pg import PostgresTestCase


class V2ServiceFactTests(PostgresTestCase):
    def setUp(self):
        store.init()
        consumer = patch('core.email.email_butler.inventory_handoff._consumer_instance', return_value='fixture-v2')
        consumer.start()
        self.addCleanup(consumer.stop)

    def events(self):
        return store.list_rows(store.EMAIL_SERVICE_SYNC, order_by='id')

    def old_import(self, *, state='pending', status='pending_sync', as_registered=False):
        pool_id = store.insert_row(store.GENERIC_API_POOL, {
            'email': 'old@example.test', 'code_url': 'https://codes.example.test',
            'status': status, 'service_tags': ['other'],
        })
        event_id = store.insert_row(store.EMAIL_SERVICE_SYNC, {
            'event_key': 'old-import', 'kind': 'import', 'address_norm': 'old@example.test',
            'source': 'generic_api', 'pool_id': pool_id, 'state': state, 'attempts': 2,
            'api_base': 'https://retired.example.test/v1', 'credential_ref': 'MISSING_OLD_SECRET',
            'payload': {'evidence_id': 'original-evidence'}, 'as_registered': as_registered,
            'final_status': 'available', 'next_attempt_at': datetime.now(timezone.utc) + timedelta(days=1),
        })
        return pool_id, event_id

    def test_direct_import_is_available_with_local_evidence_without_butler_credentials(self):
        with patch.object(client, '_request') as retired_http:
            result = local_imports.import_resources([
                {'email': 'direct@example.test', 'code_url': 'https://codes.example.test', 'service_tags': ['other']}],
                source='generic_api')
        self.assertEqual(result, (1, 0))
        retired_http.assert_not_called()
        row = store.get_row_by(store.GENERIC_API_POOL, 'email', 'direct@example.test')
        self.assertEqual((row['status'], row['service_sync_state']), ('available', 'local_only'))
        self.assertEqual(row['service_tags'], ['openai', 'other'])
        self.assertEqual(row['service_fact_scope'], 'local')
        event = self.events()[0]
        self.assertEqual(event['state'], 'local_only')
        self.assertIsNone(event.get('delivered_at'))
        self.assertEqual(service_facts.pending_count('generic_api', [row['email']]), 0)
        self.assertFalse(service_facts.dispatch_once())

    def test_registered_import_completes_in_same_local_transaction(self):
        self.assertEqual(db.import_registered_email_accounts([
            {'email': 'registered@example.test', 'code_url': 'https://codes.example.test',
             'access_token': 'fixture-token', 'user_name': '测试账号'}], 'generic_api'), (1, 0))
        account = store.get_row_by(store.ACCOUNTS, 'email', 'registered@example.test')
        self.assertIsNotNone(account)
        self.assertEqual(account['user_name'], '测试账号')
        self.assertEqual(store.get_row_by(store.GENERIC_API_POOL, 'email', account['email'])['status'], 'used')
        self.assertEqual(self.events()[0]['state'], 'local_only')

    def test_import_and_local_evidence_rollback_together(self):
        with self.assertRaisesRegex(RuntimeError, '回滚'):
            with store.transaction() as conn:
                local_imports.import_resources([
                    {'email': 'rollback@example.test', 'code_url': 'https://codes.example.test'}],
                    source='generic_api', _conn=conn)
                raise RuntimeError('回滚')
        self.assertEqual(self.events(), [])
        self.assertEqual(store.count_rows(store.GENERIC_API_POOL), 0)

    def test_old_blocked_import_is_published_without_reading_old_secret(self):
        pool_id, event_id = self.old_import(state='blocked')
        original = store.get_row(store.EMAIL_SERVICE_SYNC, event_id)['payload']
        with patch.object(client, '_request') as retired_http, patch(
                'config.runtime.read_persisted_values', side_effect=AssertionError('本地归档不得读取远端凭据')):
            self.assertTrue(service_facts.dispatch_once())
        retired_http.assert_not_called()
        event = store.get_row(store.EMAIL_SERVICE_SYNC, event_id)
        row = store.get_row(store.GENERIC_API_POOL, pool_id)
        self.assertEqual(event['state'], 'local_only')
        self.assertEqual(event['payload'], original)
        self.assertIsNone(event.get('delivered_at'))
        self.assertEqual(row['status'], 'available')
        self.assertEqual(row['service_fact_scope'], 'local')

    def test_old_registered_import_is_published_as_account(self):
        pool_id, _ = self.old_import(as_registered=True)
        self.assertTrue(service_facts.dispatch_once())
        self.assertIsNotNone(store.get_row_by(store.ACCOUNTS, 'email', 'old@example.test'))
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['status'], 'used')

    def test_local_completion_never_revives_deleted_or_unknown_inventory(self):
        for index, state in enumerate(('tombstone', 'request_unknown', 'reserved')):
            with self.subTest(state=state):
                address = f'keep{index}@example.test'
                pool_id = store.insert_row(store.GENERIC_API_POOL, {'email': address, 'status': state})
                store.insert_row(store.EMAIL_SERVICE_SYNC, {
                    'event_key': address, 'kind': 'import', 'address_norm': address, 'source': 'generic_api',
                    'pool_id': pool_id, 'state': 'pending', 'attempts': 0, 'payload': {'evidence_id': address},
                    'final_status': 'available',
                })
                self.assertTrue(service_facts.dispatch_once())
                self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['status'], state)

    def test_expired_sender_recovers_without_stale_completion_publishing(self):
        pool_id, event_id = self.old_import()
        first = service_facts._claim_next()
        store.patch_row(store.EMAIL_SERVICE_SYNC, event_id, {'lease_until': datetime.now(timezone.utc) - timedelta(seconds=1)})
        second = service_facts._claim_next()
        self.assertNotEqual(first['lease_owner'], second['lease_owner'])
        service_facts._finish(first, local_only=True)
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['status'], 'pending_sync')
        service_facts._finish(second, local_only=True, error='service_facts_unsupported')
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['status'], 'available')

    def return_event(self):
        profile_id = store.insert_row(store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'return-v2', 'revision': 1, 'connector': 'forward_butler', 'state': 'active',
            'credential_ref': 'V2_RETURN_KEY', 'inbox_locator': {'api_base': 'https://fixed.example.test/v2'},
        })
        pool_id = store.insert_row(store.EMAIL_BUTLER_POOL, {
            'email': 'return@example.test', 'status': 'available', 'inbox_profile_id': profile_id,
            'butler_handoff': {'version': 2, 'lease_id': 'lse_original', 'client_id': 'original-client'},
        })
        with store.transaction() as conn:
            event = service_facts.enqueue_return('email_butler', store.get_row(store.EMAIL_BUTLER_POOL, pool_id), conn=conn)
            store.patch_row(store.EMAIL_BUTLER_POOL, pool_id, {'status': 'tombstone'}, conn=conn)
            return event

    def test_v2_return_uses_original_lease_without_legacy_acquisition(self):
        event = self.return_event()
        self.assertEqual(event['state'], 'pending')
        with patch.dict(os.environ, {'V2_RETURN_KEY': 'fixture-key'}), patch(
                'config.runtime.read_persisted_values', return_value={}), patch.object(
                client, 'return_account', return_value={'email': event['address_norm'], 'service': 'openai',
                                                       'released': True}) as release, patch.object(client, '_request') as retired_http:
            self.assertTrue(service_facts.dispatch_once())
        retired_http.assert_not_called()
        self.assertEqual(release.call_args.kwargs['lease_id'], 'lse_original')
        self.assertEqual(release.call_args.kwargs['client_id'], 'original-client')
        self.assertEqual(release.call_args.kwargs['api_base'], 'https://fixed.example.test/v2')
        self.assertEqual(self.events()[0]['state'], 'delivered')

    def test_uncertain_return_preserves_original_payload_for_retry(self):
        event = self.return_event()
        with patch.dict(os.environ, {'V2_RETURN_KEY': 'fixture-key'}), patch(
                'config.runtime.read_persisted_values', return_value={}), patch.object(
                client, 'return_account', side_effect=client.EmailButlerClientError('超时', error_code='request_timeout')):
            service_facts.dispatch_once()
        current = self.events()[0]
        self.assertEqual(current['state'], 'pending')
        self.assertEqual(current['payload'], event['payload'])
        self.assertEqual(current['error_code'], 'request_timeout')

    def test_return_result_error_keeps_remote_code_and_unknown_state(self):
        event = self.return_event()
        result = {'ok': False, 'error_code': 'request_timeout', 'status_code': None,
                  'retryable': True, 'request_unknown': True}
        with patch.dict(os.environ, {'V2_RETURN_KEY': 'fixture-key'}), patch(
                'config.runtime.read_persisted_values', return_value={}), patch.object(
                client, 'return_account', return_value=result):
            service_facts.dispatch_once()
        current = self.events()[0]
        self.assertEqual(current['state'], 'pending')
        self.assertEqual(current['error_code'], 'request_timeout')
        self.assertEqual(current['payload'], event['payload'])

    def test_return_result_permission_rejection_is_blocked_with_original_code(self):
        self.return_event()
        result = {'ok': False, 'error_code': 'permission_denied', 'status_code': 403,
                  'retryable': False, 'request_unknown': False}
        with patch.dict(os.environ, {'V2_RETURN_KEY': 'fixture-key'}), patch(
                'config.runtime.read_persisted_values', return_value={}), patch.object(
                client, 'return_account', return_value=result):
            service_facts.dispatch_once()
        self.assertEqual((self.events()[0]['state'], self.events()[0]['error_code']),
                         ('blocked', 'permission_denied'))
        self.assertEqual(self.events()[0]['error_status_code'], 403)


class V2UsageEvidenceTests(PostgresTestCase):
    def setUp(self):
        store.init()
        self.profile_id = store.insert_row(store.EMAIL_INBOX_PROFILES, {
            'inbox_key': 'usage-v2', 'revision': 1, 'connector': 'forward_butler', 'state': 'active',
            'credential_ref': 'UNAVAILABLE_ORIGINAL_KEY',
            'inbox_locator': {'api_base': 'https://fixed.example.test/v1'},
        })
        self.row = {'email': 'usage@example.test', 'provider': 'outlook_graph',
                    'inbox_profile_id': self.profile_id,
                    'butler_handoff': {'version': 2, 'acquisition_id': 'original-intent', 'lease_id': 'lse_original'}}

    def enqueue(self, status='used'):
        return usage_reports.enqueue(self.row['email'], status=status, source='email_butler', row=self.row)

    def test_usage_is_local_only_without_releasing_or_reporting(self):
        with patch.object(client, '_request') as retired_http, patch.object(client, 'return_account') as release:
            first = self.enqueue()
            second = self.enqueue()
            self.assertFalse(usage_reports.dispatch_once())
        retired_http.assert_not_called()
        release.assert_not_called()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['state'], 'local_only')
        self.assertIsNone(first.get('delivered_at'))
        self.assertTrue(usage_reports.has_success(self.row['email']))

    def test_success_is_final_and_supersedes_local_failure(self):
        self.enqueue('failed')
        self.enqueue()
        self.assertIsNone(self.enqueue('failed'))
        rows = store.list_rows(store.EMAIL_USAGE_REPORTS, order_by='id')
        self.assertEqual([(row['result'], row['state']) for row in rows],
                         [('provider_error', 'superseded'), ('ok', 'local_only')])

    def test_old_blocked_report_retains_evidence_without_network_or_credentials(self):
        event = self.enqueue()
        store.patch_row(store.EMAIL_USAGE_REPORTS, event['id'], {'state': 'blocked', 'last_error': 'http_410'})
        with patch.object(client, '_request') as retired_http, patch(
                'config.runtime.read_persisted_values', side_effect=AssertionError('归档不应解密凭据')):
            self.assertTrue(usage_reports.dispatch_once())
        retired_http.assert_not_called()
        current = store.get_row(store.EMAIL_USAGE_REPORTS, event['id'])
        self.assertEqual(current['state'], 'local_only')
        self.assertEqual(current['payload'], event['payload'])
        self.assertEqual(current['delivery_reason'], 'usage_report_unsupported')
        self.assertIsNone(current.get('delivered_at'))

    def test_usage_and_local_business_transaction_rollback_together(self):
        with self.assertRaisesRegex(RuntimeError, '回滚'):
            with store.transaction() as conn, conn.cursor() as cur:
                usage_reports.enqueue(self.row['email'], status='used', source='email_butler', row=self.row, cursor=cur)
                raise RuntimeError('回滚')
        self.assertEqual(store.count_rows(store.EMAIL_USAGE_REPORTS), 0)

    def test_historical_sending_recovery_keeps_fence(self):
        event = self.enqueue()
        store.patch_row(store.EMAIL_USAGE_REPORTS, event['id'], {'state': 'pending'})
        first = usage_reports._claim_next()
        store.patch_row(store.EMAIL_USAGE_REPORTS, event['id'], {'lease_until': datetime.now(timezone.utc) - timedelta(seconds=1)})
        second = usage_reports._claim_next()
        usage_reports._finish(first, local_only=True)
        self.assertEqual(store.get_row(store.EMAIL_USAGE_REPORTS, event['id'])['state'], 'sending')
        usage_reports._finish(second, local_only=True)
        self.assertEqual(store.get_row(store.EMAIL_USAGE_REPORTS, event['id'])['state'], 'local_only')
