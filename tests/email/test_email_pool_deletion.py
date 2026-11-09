"""Delete failed/unknown stock without deleting confirmed registration evidence."""
from datetime import datetime, timedelta, timezone
import json
import os
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
        for evidence in ('token', 'imported', 'remote_confirmed', 'usage', 'historical_event'):
            with self.subTest(evidence=evidence):
                address = evidence + '@example.test'
                row = self.row(address, status='failed')
                if evidence == 'token':
                    store.insert_row(store.ACCOUNTS, {'email': address, 'access_token': 'fixture-at'})
                elif evidence == 'imported':
                    store.insert_row(store.ACCOUNTS, {'email': address,
                        'extra_json': json.dumps({'imported_registered': True})})
                elif evidence == 'remote_confirmed':
                    self.attempt(address, checkpoint='failed', remote_account_state='confirmed')
                elif evidence == 'usage':
                    store.insert_row(store.EMAIL_USAGE_REPORTS, {'event_key': address, 'operation_id': address,
                        'address_norm': address, 'source': 'email_butler', 'result': 'ok', 'state': 'local_only'})
                else:
                    attempt = self.attempt(address, checkpoint='failed')
                    with store.transaction() as conn, conn.cursor() as cur:
                        cur.execute(f'''INSERT INTO {registration._table('registration_events')}
                            (event_uuid,attempt_id,checkpoint,event_type) VALUES(%s,%s,'core_persisted','core_persisted')''',
                            (uuid.uuid4().hex, attempt))
                self.assertFalse(local_imports.delete_butler_email(address))
                self.assertEqual(store.get_row(store.EMAIL_BUTLER_POOL, row['id'])['status'], 'failed')

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
            self.assertTrue(sync.dispatch_once())
        release.assert_not_called()
        self.assertEqual(sync.sync_status('email_butler', row['email'])['error_code'], 'registration_confirmed')

    def test_active_cli_run_defers_release_then_returns_only_original_lease(self):
        row = self.row()
        attempt = self.attempt(row['email'])
        run = registration.start_run(attempt, initial_status='running')
        self.assertTrue(local_imports.delete_butler_email(row['email']))
        with patch('core.email.email_butler.client.return_account') as release:
            self.assertTrue(sync.dispatch_once())
        release.assert_not_called()
        self.assertEqual(sync.sync_status('email_butler', row['email'])['error_code'], 'registration_active')
        with self.assertRaisesRegex(ValueError, 'local_email_deleted'):
            registration.start_run(attempt)
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {registration._table('registration_runs')} SET status='failed' WHERE id=%s", (run['id'],))
        event = store.get_row_by(store.EMAIL_SERVICE_SYNC, 'event_key', f"return:email_butler:{row['id']}")
        store.patch_row(store.EMAIL_SERVICE_SYNC, event['id'], {'next_attempt_at': datetime.now(timezone.utc)-timedelta(seconds=1)})
        with patch.dict(os.environ, {'DELETE_TEST_KEY': 'fixture'}), patch('config.runtime.read_persisted_values', return_value={}), patch(
                'core.email.email_butler.client.return_account', return_value={
                    'email': row['email'], 'service': 'openai', 'released': True}) as release:
            self.assertTrue(sync.dispatch_once())
        self.assertEqual(release.call_args.kwargs['lease_id'], 'lse_original')
        self.assertEqual(release.call_args.kwargs['acquisition_id'], 'original-import')
        self.assertEqual(release.call_args.kwargs['client_id'], 'original-client')
        self.assertEqual(sync.sync_status('email_butler', row['email'])['state'], 'delivered')
