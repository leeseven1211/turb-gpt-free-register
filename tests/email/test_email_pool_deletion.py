"""本地删除与远端退租分别核验，保留真实成功及结果不明的历史证据。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from threading import Event
import uuid
from unittest.mock import patch

from core import db
from core.email import inventory
from core.email.email_butler import service_facts as sync
from core.storage import admin_repository, records as store, registration
from core.storage.email import local_imports
from tests.support_pg import PostgresTestCase


class EmailPoolDeletionTests(PostgresTestCase):
    def setUp(self):
        store.init()
        registration.reset_ready()
        registration.init()

    def row(self, address='failed+tag@icloud.test', **data):
        profile = store.insert_row(store.EMAIL_INBOX_PROFILES, {
            'inbox_key': uuid.uuid4().hex, 'revision': 1, 'connector': 'forward_butler', 'state': 'active',
            'credential_ref': 'DELETE_TEST_KEY', 'inbox_locator': {'api_base': 'https://fixture.test/v2'}})
        row_id = store.insert_row(store.EMAIL_BUTLER_POOL, {
            'email': address, 'status': 'used', 'used_at': '2026-11-01T00:00:00', 'provider': 'icloud_hme',
            'inbox_profile_id': profile, 'butler_handoff': {'lease_id': 'lse_original', 'client_id': 'original-client',
            'acquisition_id': 'original-import', 'version': 2, 'state': 'issued', 'service': 'openai',
            'email': address, 'expires_at': None}, **data})
        return store.get_row(store.EMAIL_BUTLER_POOL, row_id)

    def attempt(self, address, **fields):
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f'''INSERT INTO {registration._table('registration_attempts')}
                (attempt_uuid,email,email_snapshot,checkpoint,remote_account_state,local_account_state)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id''',
                (uuid.uuid4().hex, address, address, fields.get('checkpoint', 'otp_started'),
                 fields.get('remote_account_state', 'request_unknown'), fields.get('local_account_state', 'none')))
            return cur.fetchone()['id']

    def usage_report(self, address, *, state='delivered', result='ok'):
        return store.insert_row(store.EMAIL_USAGE_REPORTS, {
            'event_key': address, 'operation_id': address, 'address_norm': address,
            'source': 'email_butler', 'result': result, 'state': state,
            'payload': {'status': result, 'message': '历史邮箱使用记录'},
        })

    def persisted_event(self, attempt):
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f'''INSERT INTO {registration._table('registration_events')}
                (event_uuid,attempt_id,checkpoint,event_type) VALUES(%s,%s,'core_persisted','core_persisted')''',
                (uuid.uuid4().hex, attempt))

    def test_claimed_password_placeholder_and_mailbox_refresh_token_do_not_protect(self):
        for status in ('used', 'failed', 'request_unknown', 'reserved', 'running'):
            with self.subTest(status=status):
                address = status + '@example.test'
                row = self.row(address, status=status)
                account_id = store.insert_row(store.ACCOUNTS, {'email': address, 'password': 'fixture',
                    'refresh_token': 'outlook-mailbox-refresh-token', 'email_source': 'outlook'})
                store.patch_row(store.EMAIL_BUTLER_POOL, row['id'], {'registered_account_id': account_id})
                self.attempt(address)
                self.assertTrue(local_imports.delete_butler_email(address))
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'tombstone')
                self.assertIsNotNone(store.get_row(store.ACCOUNTS, account_id))

    def test_explicit_success_evidence_protects_even_if_current_status_failed(self):
        for evidence in ('token', 'imported', 'local_token', 'local_persisted', 'historical_event'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address, status='failed')
                if evidence == 'token':
                    store.insert_row(store.ACCOUNTS, {'email': address, 'access_token': 'fixture-at'})
                elif evidence == 'imported':
                    store.insert_row(store.ACCOUNTS, {'email': address,
                        'extra_json': json.dumps({'imported_registered': True})})
                elif evidence in {'local_token', 'local_persisted'}:
                    self.attempt(address, checkpoint='failed', local_account_state=(
                        'token_obtained' if evidence == 'local_token' else 'persisted'))
                else:
                    attempt = self.attempt(address, checkpoint='failed')
                    self.persisted_event(attempt)
                self.assertFalse(local_imports.delete_butler_email(address))
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'failed')

    def test_usage_or_remote_only_history_allows_local_delete_without_releasing_lease(self):
        for evidence in ('usage_delivered', 'usage_local_only', 'remote_confirmed', 'account_confirmed'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address)
                report = None
                if evidence.startswith('usage_'):
                    report_id = self.usage_report(address, state=evidence.removeprefix('usage_'))
                    report = store.get_row(store.EMAIL_USAGE_REPORTS, report_id)
                elif evidence == 'remote_confirmed':
                    self.attempt(address, checkpoint='failed', remote_account_state='confirmed')
                else:
                    self.attempt(address, checkpoint='account_confirmed', remote_account_state='not_started')
                with patch('core.email.email_butler.client.return_account') as release:
                    self.assertTrue(local_imports.delete_butler_email(address))
                    self.assertFalse(sync.dispatch_once())
                release.assert_not_called()
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'tombstone')
                status = sync.sync_status('email_butler', address)
                self.assertEqual((status['state'], status['error_code']),
                    ('local_only', 'registration_result_unverified'))
                self.assertTrue(status['lease_retained'])
                if report is not None:
                    self.assertEqual(store.get_row(store.EMAIL_USAGE_REPORTS, report['id']), report)

    def test_used_unknown_and_placeholder_history_never_releases_lease(self):
        for evidence in ('used_without_history', 'request_unknown', 'candidate_account', 'failed_attempt'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address, status='request_unknown' if evidence == 'request_unknown' else 'used')
                if evidence == 'candidate_account':
                    account_id = store.insert_row(store.ACCOUNTS, {'email': address, 'password': 'fixture'})
                    store.patch_row(store.EMAIL_BUTLER_POOL, row['id'], {'registered_account_id': account_id})
                elif evidence == 'failed_attempt':
                    self.attempt(address, checkpoint='failed', remote_account_state='not_started')
                with patch('core.email.email_butler.client.return_account') as release:
                    self.assertTrue(local_imports.delete_butler_email(address))
                    self.assertFalse(sync.dispatch_once())
                release.assert_not_called()
                self.assertEqual(sync.sync_status('email_butler', address)['error_code'],
                    'registration_result_unverified')

    def test_restored_available_stock_with_history_does_not_release_lease(self):
        """人为恢复 available 并清空 used_at，不能抹掉其他表中的使用历史。"""
        for evidence in ('usage_ok', 'usage_provider_error', 'candidate_account', 'job',
                         'attempt', 'otp_request', 'local_claim', 'batch_claim',
                         'legacy_claim_intent', 'legacy_claim_intent_empty_address', 'duplicate'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address, status='available', used_at=None)
                if evidence.startswith('usage_'):
                    self.usage_report(address, result=evidence.removeprefix('usage_'))
                elif evidence == 'candidate_account':
                    store.insert_row(store.ACCOUNTS, {'email': address, 'password': 'fixture'})
                elif evidence == 'job':
                    store.insert_row(store.JOBS, {'email': address, 'status': 'failed'})
                elif evidence == 'attempt':
                    self.attempt(address, checkpoint='failed', remote_account_state='not_started')
                elif evidence == 'otp_request':
                    store.insert_row(store.EMAIL_OTP_REQUESTS, {
                        'address_key': address, 'owner_kind': 'test', 'owner_id': address,
                        'challenge_id': 'historical-challenge', 'send_generation': 1,
                        'requested_at': '2026-11-01T00:00:00', 'send_state': 'sent',
                        'state': 'expired', 'submission_state': 'result_unknown',
                        'execution_token': 'fixture-execution', 'fence': 1,
                        'lease_expires_at': '2026-11-01T00:01:00',
                    })
                elif evidence == 'local_claim':
                    store.insert_row(store.LOCAL_EMAIL_CLAIMS, {
                        'acquisition_id': address, 'owner_kind': 'test', 'owner_id': address,
                        'source': 'email_butler', 'pool_id': row['id'],
                        'address_norm': address, 'status': 'failed',
                    })
                elif evidence == 'batch_claim':
                    store.insert_row(store.REGISTRATION_BATCH_EMAIL_CLAIMS, {
                        'claim_key': address, 'batch_id': 'historical-batch', 'email': address,
                        'email_source': 'email_butler', 'claimed_at': '2026-11-01T00:00:00',
                    })
                elif evidence.startswith('legacy_claim_intent'):
                    store.insert_row(store.EMAIL_BUTLER_CLAIM_INTENTS, {
                        'acquisition_id': address, 'owner_kind': 'test', 'owner_id': address,
                        'status': 'claimed', 'address_norm': (
                            '' if evidence.endswith('_empty_address') else address),
                        'api_base': 'https://fixture.test/v2', 'credential_ref': 'DELETE_TEST_KEY',
                        'mailbox': {'email': address},
                    })
                else:
                    store.insert_row(store.GENERIC_API_POOL, {
                        'email': address, 'status': 'available', 'used_at': None,
                    })
                with patch('core.email.email_butler.client.return_account') as release:
                    self.assertTrue(local_imports.delete_butler_email(address))
                    self.assertFalse(sync.dispatch_once())
                release.assert_not_called()
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'tombstone')
                status = sync.sync_status('email_butler', address)
                self.assertEqual((status['state'], status['error_code']),
                    ('local_only', 'registration_result_unverified'))
                self.assertTrue(status['lease_retained'])

    def test_deleted_account_still_protects_its_persisted_registration_history(self):
        row = self.row()
        account_id = store.insert_row(store.ACCOUNTS, {'email': row['email'], 'access_token': 'fixture-at'})
        attempt = self.attempt(row['email'], checkpoint='failed')
        self.persisted_event(attempt)
        self.assertTrue(db.delete_account(acc_id=account_id))
        self.assertIsNone(store.get_row(store.ACCOUNTS, account_id))
        self.assertFalse(local_imports.delete_butler_email(row['email']))
        self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'used')

    def test_other_source_direct_delete_cannot_bypass_confirmed_success(self):
        row_id = store.insert_row(store.GENERIC_API_POOL, {'email': 'success@example.test', 'status': 'failed'})
        store.insert_row(store.ACCOUNTS, {'email': 'success@example.test', 'access_token': 'fixture'})
        self.assertFalse(db.delete_generic_api_email('success@example.test'))
        self.assertIsNotNone(store.get_row(store.GENERIC_API_POOL, row_id))

    def test_successful_rebound_original_is_protected_without_blocking_sibling(self):
        original = self.row('original+one@icloud.test')
        sibling = self.row('original+two@icloud.test')
        store.insert_row(store.ACCOUNTS, {'email': 'new@example.test', 'access_token': '',
            'original_email_line': original['email'] + '----fixture',
            'extra_json': json.dumps({'imported_registered': True})})
        self.assertFalse(local_imports.delete_butler_email(original['email']))
        self.assertTrue(local_imports.delete_butler_email(sibling['email']))

    def test_successful_rebound_and_historical_checkpoint_survive_cleared_tokens(self):
        for evidence in ('email_change_status', 'registration_checkpoint'):
            row = self.row(evidence + '@example.test')
            data = {'email': evidence + '-new@example.test', 'access_token': '',
                'original_email_line': row['email'] + '----fixture'}
            if evidence == 'email_change_status':
                data['email_change_status'] = 'success'
            else:
                data['extra_json'] = json.dumps({'registration_checkpoint': 'registered'})
            store.insert_row(store.ACCOUNTS, data)
            self.assertFalse(local_imports.delete_butler_email(row['email']))

    def test_deleted_ordinary_source_retains_marker_for_old_attempt(self):
        address = 'ordinary@example.test'
        row_id = store.insert_row(store.GENERIC_API_POOL, {'email': address, 'status': 'used'})
        attempt = self.attempt(address)
        self.assertTrue(db.delete_generic_api_email(address))
        self.assertEqual(store.get_row(store.GENERIC_API_POOL, row_id)['status'], 'tombstone')
        self.assertEqual(db.generic_api_email_pool_summary()['total'], 0)
        with self.assertRaisesRegex(ValueError, 'local_email_deleted'):
            registration.start_run(attempt)

    def test_deleted_stock_disappears_from_rows_facets_and_counts(self):
        row = self.row()
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        for filters in ({}, {'source': 'all'}, {'source': 'email_butler'}, {'status': 'tombstone'}):
            result = admin_repository.list_email_pool(admin_repository.PageRequest(filters=filters))
            self.assertEqual(result['total'], 0)
            self.assertEqual(result['items'], [])
            self.assertFalse(result['facets'].get('status'))
        self.assertEqual(inventory.summary('email_butler')['total'], 0)
        with self.assertRaisesRegex(ValueError, 'local_email_deleted'):
            local_imports.set_butler_status(row['email'], status='available')

    def test_deleted_claim_cannot_resume_and_late_outcome_does_not_revive_row(self):
        row = self.row(status='available', used_at=None)
        inventory.claim('email_butler', acquisition_id='original-task', owner_kind='test', owner_id='original-task')
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        with self.assertRaisesRegex(inventory.LocalEmailInventoryError, 'local_email_identity_unavailable'):
            inventory.claim('email_butler', acquisition_id='original-task', owner_kind='test', owner_id='original-task')
        inventory.record_outcome(row['email'], source='email_butler', status='used')
        self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'tombstone')
        with patch('core.email.email_butler.client.return_account') as release:
            self.assertFalse(sync.dispatch_once())
        release.assert_not_called()
        self.assertEqual(sync.sync_status('email_butler', row['email'])['error_code'],
            'registration_result_unverified')

    def test_active_cli_run_defers_then_retains_lease_after_failure(self):
        row = self.row()
        attempt = self.attempt(row['email'], checkpoint='created', remote_account_state='not_started')
        run = registration.start_run(attempt, initial_status='running')
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        with patch('core.email.email_butler.client.return_account') as release:
            self.assertTrue(sync.dispatch_once())
        release.assert_not_called()
        self.assertEqual(sync.sync_status('email_butler', row['email'])['error_code'], 'registration_active')
        with self.assertRaisesRegex(ValueError, 'local_email_deleted'):
            registration.start_run(attempt)
        registration.finish_run(run['id'], status='failed')
        event = store.get_row_by(store.EMAIL_SERVICE_SYNC, 'event_key', f"return:email_butler:{row['id']}")
        store.patch_row(store.EMAIL_SERVICE_SYNC, event['id'], {'next_attempt_at': datetime.now(timezone.utc)-timedelta(seconds=1)})
        with patch('core.email.email_butler.client.return_account') as release:
            self.assertTrue(sync.dispatch_once())
        release.assert_not_called()
        status = sync.sync_status('email_butler', row['email'])
        self.assertEqual((status['state'], status['error_code']),
            ('local_only', 'registration_result_unverified'))
        self.assertTrue(status['lease_retained'])

    def test_never_claimed_available_stock_returns_only_its_original_lease(self):
        row = self.row(status='available', used_at=None)
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        self.assertEqual(sync.sync_status('email_butler', row['email'])['state'], 'pending')
        with patch.dict(os.environ, {'DELETE_TEST_KEY': 'fixture'}), patch('config.runtime.read_persisted_values', return_value={}), patch(
                'core.email.email_butler.client.return_account', return_value={
                    'email': row['email'], 'service': 'openai', 'released': True}) as release:
            self.assertTrue(sync.dispatch_once())
        self.assertEqual(release.call_args.kwargs['lease_id'], 'lse_original')
        self.assertEqual(release.call_args.kwargs['acquisition_id'], 'original-import')
        self.assertEqual(release.call_args.kwargs['client_id'], 'original-client')
        self.assertEqual(sync.sync_status('email_butler', row['email'])['state'], 'delivered')

    def test_old_pending_return_without_unused_inventory_evidence_retains_lease(self):
        row = self.row(status='available', used_at=None)
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        event = store.get_row_by(store.EMAIL_SERVICE_SYNC,
            'event_key', f"return:email_butler:{row['id']}")
        self.assertEqual(event['state'], 'pending')
        store.patch_row(store.EMAIL_SERVICE_SYNC, event['id'], {'return_evidence': None})
        with patch('core.email.email_butler.client.return_account') as release:
            self.assertTrue(sync.dispatch_once())
        release.assert_not_called()
        retained = store.get_row(store.EMAIL_SERVICE_SYNC, event['id'])
        self.assertEqual(retained['payload'], event['payload'])
        self.assertEqual((retained['state'], retained['error_code']),
            ('local_only', 'registration_result_unverified'))
        self.assertTrue(sync.sync_status('email_butler', row['email'])['lease_retained'])

    def test_pending_return_rechecks_late_usage_unknown_attempt_and_true_success(self):
        for evidence in ('usage', 'unknown_attempt', 'token'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address, status='available', used_at=None)
                self.assertTrue(local_imports.delete_butler_email(address))
                self.assertEqual(sync.sync_status('email_butler', address)['state'], 'pending')
                if evidence == 'usage':
                    self.usage_report(address)
                elif evidence == 'unknown_attempt':
                    self.attempt(address)
                else:
                    store.insert_row(store.ACCOUNTS, {'email': address, 'access_token': 'late-fixture-at'})
                with patch('core.email.email_butler.client.return_account') as release:
                    self.assertTrue(sync.dispatch_once())
                release.assert_not_called()
                status = sync.sync_status('email_butler', address)
                self.assertEqual(status['state'], 'local_only')
                self.assertEqual(status['error_code'],
                    'registration_confirmed' if evidence == 'token' else 'registration_result_unverified')
                self.assertTrue(status['lease_retained'])
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'tombstone')

    def test_sibling_usage_report_does_not_block_never_claimed_full_address(self):
        used = self.row('same-parent+used@icloud.test')
        untouched = self.row('same-parent+untouched@icloud.test', status='available', used_at=None)
        self.usage_report(used['email'])
        self.assertTrue(local_imports.delete_butler_email(used['email']))
        self.assertTrue(local_imports.delete_butler_email(untouched['email']))
        with patch.dict(os.environ, {'DELETE_TEST_KEY': 'fixture'}), patch(
                'config.runtime.read_persisted_values', return_value={}), patch(
                'core.email.email_butler.client.return_account', return_value={
                    'email': untouched['email'], 'service': 'openai', 'released': True}) as release:
            self.assertTrue(sync.dispatch_once())
        release.assert_called_once()
        self.assertEqual(release.call_args.args[0], untouched['email'])
        self.assertEqual(sync.sync_status('email_butler', used['email'])['error_code'],
            'registration_result_unverified')
        self.assertEqual(sync.sync_status('email_butler', untouched['email'])['state'], 'delivered')

    def test_delete_rechecks_success_committed_while_waiting_for_address_lock(self):
        row = self.row()
        success_ready, commit_success, delete_waiting = Event(), Event(), Event()
        original_lock = store.advisory_xact_lock

        def save_success():
            with store.transaction() as conn:
                original_lock(conn, 'registered-account:' + row['email'])
                store.insert_row(store.ACCOUNTS,
                    {'email': row['email'], 'access_token': 'concurrent-fixture-at'}, conn=conn)
                success_ready.set()
                self.assertTrue(commit_success.wait(5))

        def observed_lock(conn, key):
            if key == 'registered-account:' + row['email']:
                delete_waiting.set()
            return original_lock(conn, key)

        with ThreadPoolExecutor(2) as workers:
            success = workers.submit(save_success)
            try:
                self.assertTrue(success_ready.wait(5))
                with patch.object(store, 'advisory_xact_lock', side_effect=observed_lock):
                    deletion = workers.submit(local_imports.delete_butler_email, row['email'])
                    self.assertTrue(delete_waiting.wait(5))
                    commit_success.set()
                    success.result(timeout=10)
                    self.assertFalse(deletion.result(timeout=10))
            finally:
                commit_success.set()
        self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'used')
        self.assertIsNone(store.get_row_by(store.EMAIL_SERVICE_SYNC,
            'event_key', f"return:email_butler:{row['id']}"))
