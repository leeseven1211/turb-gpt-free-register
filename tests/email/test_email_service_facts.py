"""永久服务事实同步在隔离 PostgreSQL 中验证，不触及生产邮箱或真实接口。"""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event, current_thread
from unittest.mock import patch

import requests

from core import db
from core.email import inventory
from core.email.email_butler import client, service_facts as sync
from core.storage import records as store
from core.storage.email import local_imports
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class EmailServiceFactsTests(PostgresTestCase):
    def setUp(self):
        store.init()
        self.fixture_key = 'SERVICE_FACT_TEST_KEY'
        for mocked in (
            patch.dict(os.environ, {self.fixture_key: 'fixture-secret'}),
            patch.object(sync, '_new_route', return_value={'api_base': 'https://original.test/v1', 'credential_ref': self.fixture_key}),
            patch('core.email.email_butler.inventory_handoff._consumer_instance', return_value='fixture-instance'),
            patch('config.runtime.read_persisted_values', return_value={}),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)

    def stage(self, address='one+alias@example.test', **extra):
        self.assertEqual(local_imports.import_resources([
            {'email': address, 'code_url': 'https://private.test/fixture', **extra}], source='generic_api'), (1, 0))
        return store.get_row_by(store.GENERIC_API_POOL, 'email', address)

    def events(self):
        return store.list_rows(store.EMAIL_SERVICE_SYNC, order_by='id')

    def receipt(self, *args, **kwargs):
        item = kwargs['json']['items'][0]
        return {'code': 200, 'results': [{'code': 200, 'address': item['address'],
            'evidence_id': item['evidence_id'], 'service': 'openai', 'ever_imported': True, 'permanent': True}]}

    def deliver(self):
        with patch.object(client, '_request', side_effect=self.receipt) as request:
            self.assertTrue(sync.dispatch_once())
        return request

    def test_new_import_is_pending_until_central_ack_and_does_not_report_success(self):
        row = self.stage(service_tags=['anthropic'])
        self.assertEqual(row['status'], 'pending_sync')
        self.assertEqual(row['service_tags'], ['anthropic', 'openai'])
        self.assertEqual(inventory.summary('generic_api')['available'], 0)
        self.assertIsNone(inventory.claim('generic_api'))
        self.assertFalse(db.release_generic_api_email(row['email'], status='available'))
        request = self.deliver()
        self.assertEqual(request.call_args.args, ('POST', '/service-facts/batch'))
        self.assertNotIn('code_url', str(request.call_args.kwargs['json']))
        self.assertNotIn('fixture-secret', str(self.events()))
        self.assertEqual(store.count_rows(store.EMAIL_USAGE_REPORTS), 0)
        ready = store.get_row(store.GENERIC_API_POOL, row['id'])
        self.assertEqual((ready['status'], ready['service_fact_permanent']), ('available', True))
        self.assertEqual(inventory.summary('generic_api')['available'], 1)
        first = inventory.claim('generic_api', owner_kind='test', owner_id='owner', acquisition_id='same-intent')
        second = inventory.claim('generic_api', owner_kind='test', owner_id='owner', acquisition_id='same-intent')
        self.assertEqual(first['email'], second['email'])

    def test_timeout_replays_same_evidence_and_original_route(self):
        self.stage()
        error = client.EmailButlerClientError('私有响应不写入事件')
        error.__cause__ = requests.Timeout('private-url')
        with patch.object(client, '_request', side_effect=error):
            sync.dispatch_once()
        event = self.events()[0]
        self.assertEqual((event['state'], event['error_code']), ('pending', 'service_fact_timeout'))
        self.assertNotIn('private-url', str(event))
        sync.retry('generic_api', event['address_norm'], 'import')
        request = self.deliver()
        self.assertEqual(request.call_args.kwargs['api_base'], 'https://original.test/v1')
        self.assertEqual(request.call_args.kwargs['json']['items'][0], event['payload'])

    def test_invalid_permanent_receipt_cannot_publish_inventory(self):
        row = self.stage()
        invalid = self.receipt(json={'items': [self.events()[0]['payload']]})
        invalid['results'][0]['permanent'] = False
        with patch.object(client, '_request', return_value=invalid):
            sync.dispatch_once()
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, row['id'])['status'], 'pending_sync')
        self.assertEqual(self.events()[0]['error_code'], 'service_fact_receipt_invalid')

    def test_foreign_address_receipt_does_not_publish(self):
        self.stage()
        invalid = self.receipt(json={'items': [self.events()[0]['payload']]})
        invalid['results'][0]['address'] = 'other@example.test'
        with patch.object(client, '_request', return_value=invalid):
            sync.dispatch_once()
        self.assertEqual(self.events()[0]['error_code'], 'service_fact_receipt_mismatch')
        self.assertEqual(inventory.summary('generic_api')['available'], 0)

    def test_policy_rejection_is_visible_and_manual_retry_keeps_evidence(self):
        self.stage()
        rejected = self.receipt(json={'items': [self.events()[0]['payload']]})
        rejected['results'][0].update(code=403, error_code='service_policy_mismatch', retryable=False)
        with patch.object(client, '_request', return_value=rejected):
            sync.dispatch_once()
        event = self.events()[0]
        self.assertEqual(event['state'], 'blocked')
        self.assertEqual(sync.summary()['blocked'], 1)
        self.assertTrue(sync.retry('generic_api', event['address_norm'], 'import'))
        self.assertEqual(self.events()[0]['payload'], event['payload'])
        self.deliver()

    def test_missing_configuration_is_durable_then_binds_once(self):
        with patch.object(sync, '_new_route', return_value={'api_base': '', 'credential_ref': '', 'error_code': 'service_fact_configuration_missing'}):
            row = self.stage()
        self.assertEqual(row['service_sync_state'], 'blocked')
        self.assertFalse(sync.dispatch_once())
        self.assertTrue(sync.retry('generic_api', row['email'], 'import'))
        self.deliver()

    def test_transaction_rollback_has_no_pool_or_event(self):
        with self.assertRaisesRegex(RuntimeError, '事务回滚'):
            with store.transaction() as conn:
                local_imports.import_resources([{'email': 'rollback@example.test', 'code_url': 'https://fixture.test'}],
                                              source='generic_api', _conn=conn)
                raise RuntimeError('事务回滚')
        self.assertEqual(self.events(), [])
        self.assertEqual(store.count_rows(store.GENERIC_API_POOL), 0)

    def test_registered_material_waits_for_ack_and_reuses_existing_pool(self):
        address = 'existing@example.test'
        pool_id = store.insert_row(store.GENERIC_API_POOL, {'email': address, 'status': 'used',
            'email_invalid': True, 'email_invalid_reason': '母邮箱不可用', 'email_invalid_source': 'manual'})
        self.assertEqual(db.import_registered_email_accounts([{'email': address, 'code_url': 'https://fixed.test'}], 'generic_api'), (1, 0))
        self.assertIsNone(store.get_row_by(store.ACCOUNTS, 'email', address))
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['status'], 'pending_sync')
        self.deliver()
        account = store.get_row_by(store.ACCOUNTS, 'email', address)
        self.assertIs(account['email_invalid'], True)
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, pool_id)['registered_account_id'], account['id'])
        self.assertEqual(store.count_rows(store.GENERIC_API_POOL), 1)
        self.assertEqual(store.count_rows(store.EMAIL_USAGE_REPORTS), 0)

    def test_new_registered_material_is_not_exposed_as_unregistered_stock(self):
        address = 'registered@example.test'
        self.assertEqual(db.import_registered_email_accounts([{'email': address, 'password': 'p', 'client_id': 'c',
            'refresh_token': 'r', 'access_token': 'a', 'user_id': 'fixture-user', 'user_name': '测试账号',
            'plan_type': 'plus', 'expires_at': '2000-01-01T00:00:00Z', 'device_id': 'fixture-device',
            'proxy_used': 'http://fixture:secret@synthetic.test:80',
            'codex_status': 'pending', 'codex_error': 'fixture-error'}], 'outlook'), (1, 0))
        self.assertIsNone(store.get_row_by(store.ACCOUNTS, 'email', address))
        from core.storage import admin_repository
        listing = admin_repository.list_email_pool(admin_repository.PageRequest(page=1, page_size=50, filters={'source': 'outlook'}))
        self.assertNotIn('fixture:secret', str(listing))
        self.deliver()
        self.assertEqual(store.get_row_by(store.OUTLOOK_POOL, 'email', address)['status'], 'used')
        self.assertEqual(store.get_row_by(store.ACCOUNTS, 'email', address)['access_token'], 'a')
        account = store.get_row_by(store.ACCOUNTS, 'email', address)
        self.assertEqual((account['user_id'], account['user_name'], account['plan_type']),
                         ('fixture-user', '测试账号', 'plus'))
        self.assertEqual((account['expires_at'], account['device_id'], account['codex_error']),
                         ('2000-01-01T00:00:00Z', 'fixture-device', 'fixture-error'))
        self.assertEqual(inventory.summary('outlook')['available'], 0)

    def test_expired_sender_is_recovered_and_old_completion_is_fenced(self):
        row = self.stage()
        old = sync._claim_next()
        self.assertIsNone(sync._claim_next())
        store.patch_row(store.EMAIL_SERVICE_SYNC, old['id'], {'lease_until': datetime.now(timezone.utc) - timedelta(seconds=1)})
        current = sync._claim_next()
        self.assertNotEqual(old['lease_owner'], current['lease_owner'])
        sync._finish(old, delivered=True)
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, row['id'])['status'], 'pending_sync')
        sync._finish(current, delivered=True)
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, row['id'])['status'], 'available')

    def test_deleted_pending_import_still_syncs_without_resurrecting_address(self):
        row = self.stage()
        self.assertTrue(db.delete_generic_api_email(row['email']))
        self.deliver()
        self.assertIsNone(store.get_row(store.GENERIC_API_POOL, row['id']))
        self.assertEqual(local_imports.import_resources([{'email': row['email'], 'code_url': 'https://fixture.test'}], source='generic_api'), (0, 1))
        self.assertEqual(self.events()[0]['state'], 'delivered')

    def butler_row(self):
        profile_id = store.insert_row(store.EMAIL_INBOX_PROFILES, {'inbox_key': 'return-profile', 'revision': 1,
            'connector': 'forward_butler', 'state': 'active', 'credential_ref': self.fixture_key,
            'inbox_locator': {'api_base': 'https://return-original.test/v1', 'mailbox_email': 'final@example.test'}})
        pool_id = store.insert_row(store.EMAIL_BUTLER_POOL, {'email': 'return+alias@icloud.com', 'status': 'available',
            'inbox_profile_id': profile_id, 'butler_handoff': {'acquisition_id': 'original-acquisition'},
            'service_tags': ['openai', 'anthropic'], 'service_fact_permanent': True})
        return store.get_row(store.EMAIL_BUTLER_POOL, pool_id)

    def test_delete_outbox_preserves_original_acquisition_and_legacy_receipt_tags(self):
        row = self.butler_row()
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        event = self.events()[0]
        self.assertEqual(event['payload'], {'email': row['email'], 'service': 'openai', 'acquisition_id': 'original-acquisition'})
        with patch.object(client, '_request', return_value={'code': 200, 'email': row['email'], 'released': True,
                                                         'removed': True, 'service_tags': []}) as request:
            sync.dispatch_once()
        self.assertEqual(request.call_args.kwargs['api_base'], 'https://return-original.test/v1')
        self.assertEqual(self.events()[0]['state'], 'delivered')
        deleted = store.get_row(store.EMAIL_BUTLER_POOL, row['id'])
        self.assertEqual(deleted['status'], 'tombstone')
        self.assertIn('openai', deleted['service_tags'])

    def test_return_failure_is_visible_and_can_retry_after_deletion(self):
        row = self.butler_row()
        local_imports.delete_butler_email(row['email'])
        with patch.object(client, '_request', side_effect=client.EmailButlerClientError('fixture', status_code=409, error_code='acquisition_service_mismatch')):
            sync.dispatch_once()
        self.assertEqual(sync.sync_status('email_butler', row['email'])['state'], 'blocked')
        self.assertTrue(sync.retry('email_butler', row['email'], 'return'))
        self.assertEqual(self.events()[0]['payload']['acquisition_id'], 'original-acquisition')

    def test_missing_original_return_route_never_uses_current_default(self):
        pool_id = store.insert_row(store.EMAIL_BUTLER_POOL, {'email': 'no-route@icloud.com', 'status': 'available'})
        self.assertTrue(local_imports.delete_butler_email('no-route@icloud.com'))
        self.assertEqual(self.events()[0]['state'], 'blocked')
        self.assertFalse(sync.dispatch_once())
        self.assertTrue(sync.retry('email_butler', 'no-route@icloud.com', 'return'))
        with patch.object(client, '_request') as request:
            sync.dispatch_once()
        request.assert_not_called()
        self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, pool_id)['status'], 'tombstone')

    def test_api_rejects_manual_pending_status_bypass_and_omits_route(self):
        row = self.stage()
        web = create_app(auth_code='fixture-auth').test_client()
        headers = {'X-Auth-Code': 'fixture-auth'}
        response = web.post('/api/outlook/status', json={'email': row['email'], 'source': 'generic_api', 'status': 'available'}, headers=headers)
        self.assertEqual(response.status_code, 409)
        payload = web.get('/api/email-service-sync', headers=headers).get_json()
        self.assertEqual(payload['summary']['pending'], 1)
        for secret in ('credential_ref', 'api_base', 'fixture-secret', 'payload'):
            self.assertNotIn(secret, str(payload))
        self.assertEqual(web.post('/api/email-service-sync/retry', json={'source': 'generic_api', 'email': row['email'], 'kind': 'import'}, headers=headers).status_code, 202)

    def test_inbound_read_uses_original_remote_handoff_and_fixed_connection(self):
        row = self.butler_row()
        store.patch_row(store.EMAIL_BUTLER_POOL, row['id'], {
            'provider': 'icloud_hme', 'recipient_mode': 'forwarded_exact_v1', 'strict_family': True,
            'local_acquisition_id': 'unrelated-local-task'})
        account = client.restore_local_account(row['email'])
        self.assertEqual(account.acquisition_id, 'original-acquisition')
        with patch.object(client, 'fetch_inbound_otp', return_value='123456') as fetch:
            client.fetch_latest_otp(row['email'], after_ts=100, max_wait=1)
        self.assertEqual(fetch.call_args.kwargs['acquisition_id'], 'original-acquisition')
        self.assertEqual(fetch.call_args.kwargs['api_base'], 'https://return-original.test/v1')

    def test_inbound_transport_carries_acquisition_without_new_claim(self):
        with patch.object(client, '_request', return_value={'code': 200, 'verification_code': '123456'}) as request:
            self.assertEqual(client.fetch_inbound_otp('exact@icloud.com', after_ts=100,
                max_wait=1, acquisition_id='original-remote'), '123456')
        self.assertEqual(request.call_args.args, ('POST', '/inbound/code'))
        self.assertEqual(request.call_args.kwargs['json']['acquisition_id'], 'original-remote')
        self.assertEqual(request.call_args.kwargs['json']['service'], 'openai')

    def test_parent_acquisition_is_never_sent_for_a_child_address(self):
        profile = {'butler_identity': {'email': 'parent@icloud.com', 'acquisition_id': 'parent-only'}}
        self.assertEqual(client.original_handoff_acquisition('parent+child@icloud.com', profile=profile), '')
        self.assertEqual(client.original_handoff_acquisition('parent@icloud.com', profile=profile), 'parent-only')

    def test_return_completion_and_repeated_delete_keep_consistent_lock_order(self):
        row = self.butler_row()
        local_imports.delete_butler_email(row['email'])
        event = sync._claim_next()
        admin_locked, sender_needs_pool = Event(), Event()
        original_get_by, original_get = store.get_row_by, store.get_row

        def admin_get(table, *args, **kwargs):
            result = original_get_by(table, *args, **kwargs)
            if current_thread().name.startswith('return-admin') and table == store.EMAIL_BUTLER_POOL:
                admin_locked.set()
                self.assertTrue(sender_needs_pool.wait(5))
            return result

        def sender_get(table, *args, **kwargs):
            if current_thread().name.startswith('return-finish') and table == store.EMAIL_BUTLER_POOL:
                sender_needs_pool.set()
            return original_get(table, *args, **kwargs)

        with patch.object(store, 'get_row_by', side_effect=admin_get), patch.object(store, 'get_row', side_effect=sender_get), \
             ThreadPoolExecutor(1, thread_name_prefix='return-admin') as admins, \
             ThreadPoolExecutor(1, thread_name_prefix='return-finish') as senders:
            deletion = admins.submit(local_imports.delete_butler_email, row['email'])
            self.assertTrue(admin_locked.wait(5))
            finished = senders.submit(sync._finish, event, delivered=True)
            self.assertFalse(deletion.result(timeout=10))
            finished.result(timeout=10)
        self.assertEqual(self.events()[0]['state'], 'delivered')
