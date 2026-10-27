"""Explicit imported expiry never releases or replaces the original identity."""
import unittest
from unittest.mock import patch

from core import record_store
from core.storage import local_email_imports
from tests.support_pg import PostgresTestCase
from webui.routes.email_pool import _parse_email_pool_import


class EmailResourceLifetimeParsingTests(unittest.TestCase):
    def test_optional_third_field_is_canonical_utc_expiry(self):
        result = _parse_email_pool_import(
            'future@example.test----https://code.example.test/secret----2099-01-01T08:00:00+08:00', 'generic_api')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['extra_fields'], 0)
        self.assertEqual(result['records'][0].get('expires_at'), '2099-01-01T00:00:00Z')
        self.assertEqual(result['records'][0].get('expires_at_epoch'), 4070908800.0)

    def test_invalid_timezone_and_expired_rows_are_rejected_without_echoing_url(self):
        for value in ['2099-01-01T00:00:00', 'nonsense', '2000-01-01T00:00:00Z']:
            with self.subTest(value=value):
                result = _parse_email_pool_import(
                    'fixture@example.test----https://code.example.test/secret----' + value, 'generic_api')
                self.assertEqual(result['records'], [])
                self.assertEqual(len(result['errors']), 1)
                self.assertNotIn('/secret', str(result['errors']))

    def test_batch_expiry_only_fills_unspecified_rows(self):
        result = _parse_email_pool_import(
            'one@example.test----https://code.example.test/one\n'
            'two@example.test----https://code.example.test/two----2099-02-01T00:00:00Z',
            'generic_api', expires_at='2099-01-01T00:00:00Z')
        self.assertEqual([r['expires_at'] for r in result['records']],
                         ['2099-01-01T00:00:00Z', '2099-02-01T00:00:00Z'])

    def test_legacy_two_field_import_does_not_invent_expiry(self):
        result = _parse_email_pool_import('old@example.test----https://code.example.test/old', 'generic_api')
        self.assertEqual(result['records'], [{'email': 'old@example.test', 'code_url': 'https://code.example.test/old'}])


class HistoricalRemailRestoreTests(unittest.TestCase):
    def test_prepared_and_rejected_intents_cannot_purchase_during_restore(self):
        from core import email_provider
        for status in ['prepared', 'rejected']:
            with self.subTest(status=status), \
                    patch('core.local_email_inventory.find_local_email', return_value=None), \
                    patch('core.email_derivation.restore_address', return_value=None), \
                    patch('core.storage.remail_orders.get_intent', return_value={
                        'status': status, 'owner_kind': 'registration_root', 'owner_id': '1',
                        'acquisition_id': 'original', 'private_json': {}, 'order_no': '',
                    }), \
                    patch('core.remail_order_coordinator.RemailOrderCoordinator.acquire',
                          side_effect=AssertionError('恢复不能调用购买方法')):
                with self.assertRaisesRegex(RuntimeError, 'remail_original_order_unavailable'):
                    email_provider.restore_email_context('old@example.test', source='remail', acquisition_id='original')


class EmailResourceLifetimeStoreTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        record_store.init()

    def test_import_retains_expiry_and_rejects_already_expired_resources(self):
        self.assertEqual(local_email_imports.import_resources([{
            'email': 'future@example.test', 'code_url': 'https://fixture.example.test/code',
            'expires_at': '2099-01-01T08:00:00+08:00',
        }], source='generic_api'), (1, 0))
        row = record_store.get_row_by(record_store.GENERIC_API_POOL, 'email', 'future@example.test')
        self.assertEqual(row.get('expires_at'), '2099-01-01T00:00:00Z')
        self.assertEqual(row.get('expires_at_epoch'), 4070908800.0)
        with self.assertRaisesRegex(ValueError, 'email_resource_expired'):
            local_email_imports.import_resources([{
                'email': 'expired@example.test', 'code_url': 'https://fixture.example.test/code',
                'expires_at': '2000-01-01T00:00:00Z',
            }], source='generic_api')
        self.assertIsNone(record_store.get_row_by(record_store.GENERIC_API_POOL, 'email', 'expired@example.test'))

    def test_summary_and_new_claim_exclude_expired_receipt(self):
        from core import local_email_inventory as inventory
        record_store.insert_row(record_store.GENERIC_API_POOL, {
            'email': 'expired@example.test', 'code_url': 'https://fixture.example.test/code', 'status': 'available',
            'expires_at': '2000-01-01T00:00:00Z', 'expires_at_epoch': 946684800.0,
        })
        self.assertEqual(inventory.summary('generic_api')['available'], 0)
        self.assertIsNone(inventory.claim('generic_api', owner_kind='test', owner_id='expired', acquisition_id='expired'))

    def test_summary_excludes_invalid_or_inconsistent_expiry_metadata(self):
        from core import local_email_inventory as inventory
        for number, expiry in enumerate(['not-a-date', '2000-01-01T00:00:00Z']):
            record_store.insert_row(record_store.GENERIC_API_POOL, {
                'email': f'invalid-{number}@example.test', 'code_url': 'https://fixture.example.test/code',
                'status': 'available', 'expires_at': expiry, 'expires_at_epoch': 4070908800.0,
            })
        self.assertEqual(inventory.summary('generic_api')['available'], 0)

    def test_same_intent_and_restore_reject_expiry_but_keep_claim_and_occupancy(self):
        from core import local_email_inventory as inventory, email_provider
        local_email_imports.import_resources([{
            'email': 'held@example.test', 'code_url': 'https://fixture.example.test/code',
            'expires_at': '2099-01-01T00:00:00Z',
        }], source='generic_api')
        original = inventory.claim('generic_api', owner_kind='test', owner_id='held', acquisition_id='held')
        record_store.patch_row(record_store.GENERIC_API_POOL, original['id'],
            {'expires_at': '2000-01-01T00:00:00Z', 'expires_at_epoch': 946684800.0})
        for action in [
            lambda: inventory.claim('generic_api', owner_kind='test', owner_id='held', acquisition_id='held'),
            lambda: email_provider.restore_email_context('held@example.test', source='generic_api'),
        ]:
            with self.assertRaisesRegex(RuntimeError, 'email_resource_expired'):
                action()
        self.assertEqual(record_store.get_row(record_store.GENERIC_API_POOL, original['id'])['status'], 'used')
        self.assertEqual(record_store.count_rows(record_store.LOCAL_EMAIL_CLAIMS), 1)

    def test_cached_generic_context_keeps_original_expiry(self):
        from core import generic_api_mail_client as client
        local_email_imports.import_resources([{
            'email': 'cached@example.test', 'code_url': 'https://fixture.example.test/code',
            'expires_at': '2099-01-01T00:00:00Z',
        }], source='generic_api')
        with patch.dict(client._CONTEXT_CACHE, {}, clear=True):
            account = client.get_account_context('cached@example.test')
            self.assertEqual(getattr(account, 'expires_at', None), '2099-01-01T00:00:00Z')
            with patch('time.time', return_value=4070908801.0):
                with self.assertRaisesRegex(RuntimeError, 'email_resource_expired'):
                    client.get_account_context('cached@example.test')

    def test_copy_material_preserves_expiry_but_old_rows_stay_two_fields(self):
        from core import db
        for address, expiry in [('future@example.test', '2099-01-01T00:00:00Z'), ('legacy@example.test', None)]:
            local_email_imports.import_resources([{
                'email': address, 'code_url': 'https://fixture.example.test/code', 'expires_at': expiry,
            }], source='generic_api')
            expected = address + '----https://fixture.example.test/code' + ('----' + expiry if expiry else '')
            self.assertEqual(db.email_pool_secret('generic_api', address, 'copy_line'), expected)
