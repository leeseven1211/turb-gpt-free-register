from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event, current_thread
import tempfile
import unittest
from unittest.mock import patch

from core import admin_repository, db, record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app
from webui.routes.email_pool import _parse_email_pool_import


class LocalEmailImportParsingTests(unittest.TestCase):
    def test_butler_text_import_keeps_full_hme_identity_and_rejects_other_routes(self):
        parsed = _parse_email_pool_import(
            'Parent@icloud.com\nparent+tag@icloud.com\nuser@outlook.com\na@@icloud.com\n',
            'email_butler',
        )
        self.assertEqual(parsed['records'], [{'email': 'parent@icloud.com'}, {'email': 'parent+tag@icloud.com'}])
        self.assertEqual(len(parsed['errors']), 2)


class LocalEmailImportsTests(PostgresTestCase):
    def setUp(self):
        record_store.reset_ready()
        record_store.init()
        self.client = create_app(auth_code='test-auth').test_client()
        self.headers = {'X-Auth-Code': 'test-auth'}
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_patch = patch('config.env_loader._ENV_PATH', Path(self.directory.name) / '.env')
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.config_patch = patch.multiple('config.email', EMAIL_BUTLER_API_BASE='https://butler.example.test/v1',
            EMAIL_BUTLER_API_KEY='test-fixed-key', ICLOUD_HME_FORWARD_IMAP_EMAIL='forward@example.test')
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.handoff_patch = patch('core.butler_inventory_handoff.handoff_for_import',
            side_effect=lambda email, profile, **kwargs: {
                'version': 1, 'state': 'issued', 'owner_kind': 'local_inventory',
                'owner_id': 'test-instance', 'acquisition_id': 'test-handoff:' + email,
                'identity_id': 'identity:' + email,
                'parent_email': email.partition('@')[0].split('+', 1)[0] + '@icloud.com',
            })
        self.handoff_patch.start()
        self.addCleanup(self.handoff_patch.stop)

    def post(self, endpoint, body):
        return self.client.post(endpoint, json=body, headers=self.headers)

    def test_unconfirmed_butler_handoff_cannot_become_available_local_stock(self):
        with patch('core.butler_inventory_handoff.handoff_for_import',
                   side_effect=ValueError('handoff_unconfirmed: 请重试同一地址')):
            response = self.post('/api/outlook/import', {'source': 'email_butler', 'text': 'new@icloud.com'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 0)

    def test_import_pins_connection_lists_safely_and_duplicate_does_not_change_route(self):
        response = self.post('/api/outlook/import', {'source': 'email_butler', 'text': 'new+tag@icloud.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['inserted'], 1)
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', 'new+tag@icloud.com')
        from core.storage.email_address_allocations import get_inbox_profile
        original_profile = get_inbox_profile(row['inbox_profile_id'])
        self.assertEqual(row['status'], 'available')
        self.assertEqual(row['provider'], 'icloud_hme')
        self.assertEqual(original_profile['connector'], 'forward_butler')
        self.assertEqual(original_profile['inbox_locator'], {'api_base': 'https://butler.example.test/v1', 'mailbox_email': 'forward@example.test'})
        self.assertNotIn('test-fixed-key', str(row))
        from core import local_email_inventory
        local_email_inventory.claim('email_butler', owner_kind='test', owner_id='list-redaction',
                                    acquisition_id='list-redaction')
        record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], {'status': 'request_unknown'})
        with patch('config.email.EMAIL_BUTLER_API_KEY', 'different-key'):
            repeated = self.post('/api/outlook/import', {'source': 'email_butler', 'text': row['email']})
        self.assertEqual(repeated.get_json()['inserted'], 0)
        self.assertEqual(record_store.get_row(record_store.EMAIL_BUTLER_POOL, row['id'])['status'], 'request_unknown')
        self.assertEqual(record_store.get_row(record_store.EMAIL_BUTLER_POOL, row['id'])['inbox_profile_id'], row['inbox_profile_id'])
        listing = self.client.get('/api/outlook?source=email_butler&paged=1', headers=self.headers)
        self.assertEqual(listing.status_code, 200)
        item = listing.get_json()['items'][0]
        self.assertEqual(item['source'], 'email_butler')
        for name in ('credential_ref', 'inbox_profile_id', 'inbox_locator', 'api_base', 'api_key',
                     'local_inbox_profile_id', 'local_acquisition_id', 'local_owner_kind', 'local_owner_id', 'butler_handoff'):
            self.assertNotIn(name, item)

    def test_cross_source_used_registered_and_unknown_are_skipped_by_all_importers(self):
        record_store.insert_row(record_store.OUTLOOK_POOL, {'email': 'used@icloud.com', 'status': 'used'})
        record_store.insert_row(record_store.GENERIC_API_POOL, {'email': 'unknown@icloud.com', 'status': 'request_unknown'})
        record_store.insert_row(record_store.ACCOUNTS, {'email': 'registered@icloud.com', 'email_source': 'generic_api'})
        text = 'used@icloud.com\nunknown@icloud.com\nregistered@icloud.com\nfresh@icloud.com'
        preview = self.post('/api/outlook/import-preview', {'source': 'email_butler', 'text': text}).get_json()
        self.assertEqual(preview['existing'], 3)
        self.assertEqual(preview['new'], 1)
        imported = self.post('/api/outlook/import', {'source': 'email_butler', 'text': text}).get_json()
        self.assertEqual((imported['inserted'], imported['skipped']), (1, 3))
        self.assertEqual(db.import_outlook_accounts([{'email': 'unknown@icloud.com', 'password': 'p', 'client_id': 'c', 'refresh_token': 'r'}]), (0, 1))
        self.assertEqual(db.import_generic_api_emails([{'email': 'used@icloud.com', 'code_url': 'https://code.example.test'}]), (0, 1))
        self.assertEqual(db.import_generic_api_emails([{'email': 'registered@icloud.com', 'code_url': 'https://code.example.test'}]), (0, 1))

    def test_missing_fixed_forward_connection_fails_without_importing(self):
        with patch('config.email.ICLOUD_HME_FORWARD_IMAP_EMAIL', ''):
            response = self.post('/api/outlook/import', {'source': 'email_butler', 'text': 'new@icloud.com'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(record_store.count_rows(record_store.EMAIL_BUTLER_POOL), 0)

    def test_butler_unknown_cannot_be_reset_to_available_or_deleted_for_reimport(self):
        self.assertEqual(self.post('/api/outlook/import', {'source': 'email_butler', 'text': 'kept@icloud.com'}).status_code, 200)
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', 'kept@icloud.com')
        record_store.patch_row(record_store.EMAIL_BUTLER_POOL, row['id'], {'status': 'request_unknown'})
        changed = self.post('/api/outlook/status', {'source': 'email_butler', 'email': row['email'], 'status': 'available'})
        self.assertEqual(changed.status_code, 409)
        deleted = self.post('/api/outlook/delete', {'source': 'email_butler', 'email': row['email']})
        self.assertFalse(deleted.get_json()['deleted'])
        self.assertEqual(record_store.get_row(record_store.EMAIL_BUTLER_POOL, row['id'])['status'], 'request_unknown')
        self.assertEqual(self.post('/api/outlook/status', {'source': 'email_butler', 'email': row['email'], 'status': 'failed'}).status_code, 200)
        bypass = self.post('/api/outlook/status', {'source': 'email_butler', 'email': row['email'], 'status': 'available'})
        self.assertEqual(bypass.status_code, 409)

    def test_legacy_used_resource_is_retained_by_status_and_bulk_delete_routes(self):
        record_store.insert_row(record_store.GENERIC_API_POOL, {'email': 'legacy@example.test', 'status': 'used'})
        changed = self.post('/api/outlook/status', {'source': 'generic_api', 'email': 'legacy@example.test', 'status': 'available'})
        self.assertEqual(changed.status_code, 409)
        deleted = self.post('/api/outlook/delete-bulk', {'items': [{'source': 'generic_api', 'email': 'legacy@example.test'}]}).get_json()
        self.assertEqual(deleted['deleted_count'], 0)
        self.assertEqual(record_store.get_row_by(record_store.GENERIC_API_POOL, 'email', 'legacy@example.test')['status'], 'used')

    def test_parallel_imports_cannot_create_two_local_resources_for_one_address(self):
        first_locked, second_attempted, second_locked = Event(), Event(), Event()
        first_keys, seen_threads = {}, set()
        original_lock = record_store.advisory_xact_lock

        def coordinated_lock(conn, key):
            thread = current_thread().name
            if not key.startswith('registered-account:') or thread in seen_threads:
                return original_lock(conn, key)
            seen_threads.add(thread)
            if thread.startswith('import-outlook'):
                first_keys['outlook'] = key
                original_lock(conn, key)
                first_locked.set()
                if not second_attempted.wait(5):
                    raise AssertionError('second importer did not request its first address')
                if first_keys['generic'] != key and not second_locked.wait(5):
                    raise AssertionError('second importer did not lock its different first address')
                return
            first_keys['generic'] = key
            if not first_locked.wait(5):
                raise AssertionError('first importer did not lock its first address')
            second_attempted.set()
            original_lock(conn, key)
            second_locked.set()

        outlook = [{'email': email, 'password': 'p', 'client_id': 'c', 'refresh_token': 'r'}
                   for email in ('one@example.test', 'two@example.test')]
        generic = [{'email': email, 'code_url': 'https://code.example.test'}
                   for email in ('two@example.test', 'one@example.test')]
        with patch.object(record_store, 'advisory_xact_lock', side_effect=coordinated_lock), ThreadPoolExecutor(
                1, thread_name_prefix='import-outlook') as outlook_pool, ThreadPoolExecutor(
                1, thread_name_prefix='import-generic') as generic_pool:
            first = outlook_pool.submit(db.import_outlook_accounts, outlook)
            second = generic_pool.submit(db.import_generic_api_emails, generic)
            results = [first.result(), second.result()]
        self.assertEqual(sorted(results), [(0, 2), (2, 0)])
        self.assertEqual(record_store.count_rows(record_store.OUTLOOK_POOL) + record_store.count_rows(record_store.GENERIC_API_POOL), 2)

    def test_claimed_butler_admin_mutation_and_outcome_do_not_deadlock(self):
        from core import local_email_inventory as inventory
        from core.storage import local_email_imports

        for operation in ('status', 'delete'):
            with self.subTest(operation=operation):
                address = f'locking-{operation}@icloud.com'
                local_email_imports.import_resources([{'email': address}], source='email_butler')
                inventory.claim('email_butler', owner_kind='test', owner_id=operation,
                                acquisition_id='locking:' + operation)
                admin_has_row, outcome_needs_row = Event(), Event()
                original_lock, original_get = record_store.advisory_xact_lock, record_store.get_row

                def coordinated_lock(conn, key):
                    if current_thread().name.startswith('inventory-admin') and key == 'registered-account:' + address:
                        # The admin already owns the pool row. Let the outcome
                        # reach that row before either operation proceeds.
                        admin_has_row.set()
                        if not outcome_needs_row.wait(5):
                            raise AssertionError('outcome did not reach the pool row')
                    return original_lock(conn, key)

                def coordinated_get(table, row_id, **kwargs):
                    if (current_thread().name.startswith('inventory-outcome')
                            and table == record_store.EMAIL_BUTLER_POOL and kwargs.get('for_update')):
                        outcome_needs_row.set()
                    return original_get(table, row_id, **kwargs)

                mutation = (lambda: local_email_imports.set_butler_status(address, status='failed')) if operation == 'status' else (
                    lambda: local_email_imports.delete_butler_email(address))
                with patch.object(record_store, 'advisory_xact_lock', side_effect=coordinated_lock), patch.object(
                        record_store, 'get_row', side_effect=coordinated_get), ThreadPoolExecutor(
                        1, thread_name_prefix='inventory-admin') as admin_pool, ThreadPoolExecutor(
                        1, thread_name_prefix='inventory-outcome') as outcome_pool:
                    admin = admin_pool.submit(mutation)
                    self.assertTrue(admin_has_row.wait(5))
                    outcome = outcome_pool.submit(inventory.record_outcome, address, source='email_butler', status='used')
                    self.assertEqual(admin.result(timeout=10), operation == 'status')
                    self.assertTrue(outcome.result(timeout=10))
                row = local_email_imports.get_butler_email(address)
                self.assertEqual(row['status'], 'used')
                self.assertTrue(inventory.has_claim(address))
