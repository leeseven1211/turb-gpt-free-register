"""旧完整地址交接入口只恢复 v2 原租约，不调用随机分配和退役 API。"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from core.email.email_butler import inventory_handoff as handoff, v2


class ButlerInventoryHandoffTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'id': 1, 'state': 'active', 'connector': 'forward_butler', 'credential_ref': 'TEST_KEY',
            'inbox_locator': {'api_base': 'https://butler.example/v1', 'mailbox_email': 'final@example.test'}}
        self.connection = {'api_base': 'https://butler.example/v1', 'api_key': 'fixture-secret'}
        self.calls = []
        self.bindings = {}
        self.items = []
        for index in range(2):
            email = f'parent+tag{index}@icloud.com'
            acquisition = 'original-acquisition-' + str(index)
            self.bindings[email] = {'email': email, 'provider': 'icloud_hme', 'client_id': 'stable-client',
                'lease_id': 'lse_original_' + str(index), 'service': 'openai', 'status': 'active',
                'expires_at': None, 'acquisition_id': acquisition}
            self.items.append({'acquisition_id': acquisition, 'address_norm': email,
                'candidate': {'email': email, 'provider': 'icloud_hme'},
                'ownership': {'owner_kind': 'local_inventory', 'owner_id': 'local-instance',
                    'acquisition_id': acquisition}})
        for target in [
            patch('core.email.derivation._profile_credentials', return_value=self.connection),
            patch('core.email.email_butler.lease_bindings.resolve', side_effect=self.resolve),
            patch.object(v2, 'create_lease', side_effect=AssertionError('禁止随机分配')),
            patch('core.email.email_butler.client._request', side_effect=AssertionError('禁止旧接口')),
        ]:
            target.start()
            self.addCleanup(target.stop)

    def resolve(self, email, **kwargs):
        self.calls.append((email, kwargs))
        result = self.bindings[email]
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)

    def invoke(self):
        return handoff.handoff_for_import(self.items[0]['address_norm'], self.profile)

    def batch(self, items=None, **kwargs):
        return handoff.handoff_selected_batch(self.items if items is None else items,
            self.profile, client_id='stable-client', **kwargs)

    def test_pasted_address_recovers_the_same_long_term_lease(self):
        first, second = self.invoke(), self.invoke()
        self.assertEqual(first, second)
        self.assertEqual(first['version'], 2)
        self.assertEqual(first['lease_id'], 'lse_original_0')
        self.assertEqual(first['email'], self.items[0]['address_norm'])
        self.assertNotIn('api_key', first)
        v2.create_lease.assert_not_called()

    def test_different_complete_address_is_rejected(self):
        self.bindings[self.items[0]['address_norm']]['email'] = 'different@icloud.com'
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke()

    def test_missing_read_permission_is_classified_without_allocating(self):
        self.bindings[self.items[0]['address_norm']] = v2.ButlerV2Error('permission_denied', status_code=403)
        with self.assertRaises(v2.ButlerV2Error) as error:
            self.invoke()
        self.assertEqual(error.exception.error_code, 'permission_denied')
        v2.create_lease.assert_not_called()

    def test_timeout_recovery_always_keeps_original_address(self):
        email = self.items[0]['address_norm']
        original = self.bindings[email]
        self.bindings[email] = v2.ButlerV2Error('butler_transport_timeout', retryable=True)
        with self.assertRaises(v2.ButlerV2Error):
            self.invoke()
        self.bindings[email] = original
        self.invoke()
        self.assertEqual([call[0] for call in self.calls], [email, email])

    def test_batch_results_are_keyed_by_original_acquisition(self):
        result = self.batch()
        self.assertEqual(set(result), {item['acquisition_id'] for item in self.items})
        for item in self.items:
            self.assertEqual(result[item['acquisition_id']]['receipt']['email'], item['address_norm'])

    def test_one_rejected_item_does_not_discard_another_confirmed_lease(self):
        self.bindings[self.items[0]['address_norm']] = v2.ButlerV2Error('lease_released', status_code=410)
        result = self.batch()
        self.assertEqual(result[self.items[0]['acquisition_id']]['outcome'], 'unknown')
        self.assertIn('receipt', result[self.items[1]['acquisition_id']])

    def test_missing_mapping_preserves_original_intent(self):
        self.bindings[self.items[0]['address_norm']] = v2.ButlerV2Error('lease_restore_required')
        result = self.batch()
        self.assertEqual(result[self.items[0]['acquisition_id']]['error_code'], 'lease_restore_required')
        self.assertEqual(self.items[0]['acquisition_id'], 'original-acquisition-0')

    def test_duplicate_acquisition_is_rejected_before_any_lookup(self):
        changed = deepcopy(self.items)
        changed[1]['acquisition_id'] = changed[0]['acquisition_id']
        changed[1]['ownership']['acquisition_id'] = changed[0]['acquisition_id']
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.batch(changed)
        self.assertEqual(self.calls, [])

    def test_duplicate_address_is_rejected_before_any_lookup(self):
        changed = deepcopy(self.items)
        changed[1]['address_norm'] = changed[0]['address_norm']
        changed[1]['candidate']['email'] = changed[0]['address_norm']
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.batch(changed)
        self.assertEqual(self.calls, [])

    def test_missing_candidate_is_rejected_before_any_lookup(self):
        changed = deepcopy(self.items)
        changed[0]['candidate'] = None
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.batch(changed)
        self.assertEqual(self.calls, [])

    def test_swapped_local_addresses_cannot_confirm_wrong_identity(self):
        changed = deepcopy(self.items)
        changed[0]['address_norm'], changed[1]['address_norm'] = changed[1]['address_norm'], changed[0]['address_norm']
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.batch(changed)
        self.assertEqual(self.calls, [])

    def test_wrong_provider_cannot_publish_original_lease(self):
        self.bindings[self.items[0]['address_norm']]['provider'] = 'mailcom'
        result = self.batch()
        self.assertEqual(result[self.items[0]['acquisition_id']]['error_code'], 'handoff_identity_mismatch')

    def test_wrong_client_cannot_publish_original_lease(self):
        self.bindings[self.items[0]['address_norm']]['client_id'] = 'other-client'
        result = self.batch()
        self.assertEqual(result[self.items[0]['acquisition_id']]['error_code'], 'handoff_identity_mismatch')

    def test_wrong_service_cannot_publish_original_lease(self):
        self.bindings[self.items[0]['address_norm']]['service'] = 'grok'
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke()

    def test_empty_lease_id_cannot_confirm_handoff(self):
        self.bindings[self.items[0]['address_norm']]['lease_id'] = ''
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke()

    def test_expired_lease_cannot_be_replaced_with_random_address(self):
        self.bindings[self.items[0]['address_norm']]['status'] = 'expired'
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke()
        v2.create_lease.assert_not_called()

    def test_short_lease_cannot_be_published_as_long_term_stock(self):
        self.bindings[self.items[0]['address_norm']]['expires_at'] = '2026-12-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
            self.invoke()

    def test_unknown_transient_http_status_keeps_error_classification(self):
        for status, code in [(403, 'permission_denied'), (429, 'rate_limited'), (503, 'provider_unavailable')]:
            with self.subTest(status=status):
                self.bindings[self.items[0]['address_norm']] = v2.ButlerV2Error(code, status_code=status)
                item = self.batch()[self.items[0]['acquisition_id']]
                self.assertEqual((item['error_code'], item['status_code'], item['outcome']), (code, status, 'unknown'))

    def test_supplied_connection_never_reloads_fixed_credentials(self):
        with patch('core.email.derivation._profile_credentials', side_effect=AssertionError('禁止重载')):
            self.batch(connection=self.connection)
        self.assertTrue(all(call[1]['api_key'] == 'fixture-secret' for call in self.calls))

    def test_oversized_batch_is_rejected_before_partial_lookup(self):
        with self.assertRaisesRegex(ValueError, 'handoff_batch_too_large'):
            self.batch(self.items * 51)
        self.assertEqual(self.calls, [])

    def test_empty_batch_never_calls_remote(self):
        self.assertEqual(self.batch([]), {})
        self.assertEqual(self.calls, [])

    def test_frozen_acquisition_is_forwarded_to_resolver(self):
        receipt = handoff.handoff_selected(self.items[0]['candidate'], self.profile,
            ownership=self.items[0]['ownership'], client_id='stable-client')
        self.assertEqual(self.calls[0][1]['acquisition_id'], self.items[0]['acquisition_id'])
        self.assertEqual(receipt['owner_id'], 'local-instance')
        self.assertEqual(receipt['acquisition_id'], self.items[0]['acquisition_id'])

    def test_inactive_profile_cannot_switch_to_global_connection(self):
        self.profile['state'] = 'disabled'
        with self.assertRaisesRegex(ValueError, 'fixed_route_unavailable'):
            self.invoke()
        self.assertEqual(self.calls, [])
