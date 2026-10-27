"""Registration supply is the imported local inventory, independent of Butler stock."""
from unittest.mock import patch

from config import email as cfg
from core import record_store
from core.email_supply import email_supply_summary
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class EmailSupplyTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        self.app = create_app(auth_code='test-auth')
        self.client = self.app.test_client()
        self.client.environ_base['HTTP_X_AUTH_CODE'] = 'test-auth'
        self.settings = patch.multiple(cfg, EMAIL_SOURCE='email_butler', USE_EMAIL_SERVICE=True,
                                       ICLOUD_HME_BUTLER_BRIDGE_ENABLED=True)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.environment = patch.dict(__import__('os').environ, {'SUPPLY_FIXTURE_KEY': 'fixture-only'})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        from core.storage.email_address_allocations import create_inbox_profile
        self.profile = create_inbox_profile(inbox_key='supply-fixture', connector='forward_butler',
            credential_ref='SUPPLY_FIXTURE_KEY', inbox_locator={
                'api_base': 'https://butler.test/v1', 'mailbox_email': 'final@example.test'})

    def seed(self, email, **changes):
        return record_store.insert_row(record_store.ICLOUD_HIDE_POOL,
            {'email': email, 'status': 'available', 'remote_active': True,
             'derivation_policy': {'inbox_profile_id': self.profile['id']}, **changes})

    def test_local_hme_is_counted_even_when_old_config_only_mentions_butler(self):
        self.seed('unused@icloud.com')
        self.seed('used@icloud.com', status='used')
        with patch('core.email_butler_client._request', side_effect=AssertionError('inventory must stay local')):
            result = email_supply_summary()
        self.assertEqual(result['scope'], 'local_pool')
        self.assertEqual(result['status'], 'known')
        self.assertEqual((result['total'], result['available'], result['used']), (2, 1, 1))

    def test_summary_uses_local_count_in_legacy_and_new_fields(self):
        self.seed('unused@icloud.com')
        with patch('core.email_butler_client._request', side_effect=AssertionError('no remote inventory read')):
            result = self.client.get('/api/summary').get_json()
        self.assertEqual(result['outlook_available'], 1)
        self.assertEqual(result['email_supply']['available'], 1)

    def test_unhealthy_available_rows_do_not_inflate_capacity(self):
        self.seed('healthy@icloud.com')
        self.seed('inactive@icloud.com', remote_active=False)
        self.seed('invalid@icloud.com', email_invalid=True)
        self.seed('registered@icloud.com', registered_account_id=123)
        result = email_supply_summary()
        self.assertEqual(result['available'], 1)

    def test_new_registration_source_options_only_offer_local_pools(self):
        self.seed('unused@icloud.com')
        with patch('core.email_butler_client._request', side_effect=AssertionError('no remote inventory read')):
            result = self.client.get('/api/email-sources').get_json()
        self.assertEqual({row['value'] for row in result['sources']},
                         {'outlook', 'generic_api', 'cloudflare_domain', 'icloud_hide', 'email_butler'})
        hme = next(row for row in result['sources'] if row['value'] == 'icloud_hide')
        self.assertTrue(hme['enabled'])

    def test_legacy_remote_source_cannot_submit_new_registration(self):
        with patch.object(cfg, 'EMAIL_SOURCE', 'gptmail'), patch('core.registration_service.submit_registration') as submit:
            response = self.client.post('/api/jobs', json={'count': 1, 'email_source': 'gptmail'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('本地', response.get_json()['error'])
        submit.assert_not_called()

    def test_hme_submit_never_syncs_or_creates_and_reports_local_shortage(self):
        self.seed('unused@icloud.com')
        with patch('core.icloud_hme_client.sync_aliases', side_effect=AssertionError('submit cannot sync')), patch('core.registration_service.submit_registration', return_value=[]) as submit:
            response = self.client.post('/api/jobs', json={'count': 2, 'email_source': 'icloud_hide'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('1', response.get_json()['warning'])
        self.assertIn('导入', response.get_json()['warning'])
        submit.assert_called_once()
