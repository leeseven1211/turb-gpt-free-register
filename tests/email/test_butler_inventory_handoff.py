"""人工导入持久交接，不允许远端另发邮箱或以短租约冒充归属。"""
import unittest
from unittest.mock import patch


class ButlerInventoryHandoffTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'connector': 'forward_butler', 'credential_ref': 'TEST_KEY',
                        'inbox_locator': {'api_base': 'https://butler.example/v1',
                                          'mailbox_email': 'final@example.test'}}
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == '/me':
            return {'code': 200, 'id': 'stable-client',
                    'policy': {'consumer': 'turb', 'service': 'openai'},
                    'capabilities': ['mailboxes.acquisition.v1', 'inbound.recipient_evidence.v1']}
        return {'code': 200, 'mailbox': {
            'email': 'parent+tag@icloud.com', 'provider': 'icloud_hme',
            'mailbox_email': 'final@example.test', 'identity_type': 'plus_alias',
            'identity_id': 'fixed-identity', 'parent_email': 'parent@icloud.com',
            'recipient_mode': 'forwarded_exact_v1', 'strict_family': True,
            'lease_id': 'fixed-lease',
        }}

    def invoke(self, request=None):
        from core.email.email_butler import inventory_handoff as handoff
        with patch.object(handoff, '_consumer_instance', return_value='local-instance'), \
             patch('core.email.derivation._profile_credentials', return_value={
                 'api_base': 'https://butler.example/v1', 'api_key': 'test-key',
                 'mailbox_email': 'final@example.test'}), \
             patch('core.email.email_butler.client._request', side_effect=request or self.request):
            return handoff.handoff_for_import('parent+tag@icloud.com', self.profile)

    def test_exact_manual_handoff_has_stable_persistent_owner(self):
        first = self.invoke()
        second = self.invoke()
        self.assertEqual(first, second)
        self.assertEqual(first['identity_id'], 'fixed-identity')
        writes = [call for call in self.calls if call[1] == '/mailboxes' and call[2]['json'].get('acquisition_id')]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0][2]['json'], writes[1][2]['json'])
        body = writes[0][2]['json']
        self.assertEqual(body['requested_email'], 'parent+tag@icloud.com')
        self.assertEqual(body['owner_kind'], 'local_inventory')
        self.assertEqual(body['owner_id'], 'local-instance')
        self.assertNotIn('lease_id', first)
        self.assertNotIn('api_key', str(first))

    def test_different_identity_is_rejected_before_local_import(self):
        def wrong(method, path, **kwargs):
            result = self.request(method, path, **kwargs)
            if path == '/mailboxes':
                result['mailbox']['email'] = 'other@icloud.com'
            return result
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke(wrong)

    def test_missing_capability_never_mutates_remote_stock(self):
        def unsupported(method, path, **kwargs):
            result = self.request(method, path, **kwargs)
            if path == '/me':
                result['capabilities'] = []
            return result
        with self.assertRaisesRegex(ValueError, 'handoff_contract_unsupported'):
            self.invoke(unsupported)
        self.assertEqual([call[1] for call in self.calls], ['/me'])

    def test_timeout_replay_uses_original_acquisition(self):
        def timeout(method, path, **kwargs):
            result = self.request(method, path, **kwargs)
            if path == '/mailboxes' and kwargs['json'].get('acquisition_id'):
                raise TimeoutError('simulated')
            return result
        with self.assertRaisesRegex(ValueError, 'handoff_unconfirmed'):
            self.invoke(timeout)
        self.invoke()
        writes = [call for call in self.calls if call[1] == '/mailboxes' and call[2]['json'].get('acquisition_id')]
        self.assertEqual(writes[0][2]['json'], writes[1][2]['json'])

