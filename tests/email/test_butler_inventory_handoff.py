"""人工导入持久交接，不允许远端另发邮箱或以短租约冒充归属。"""
import unittest
from copy import deepcopy
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


class ButlerInventoryBatchHandoffTests(unittest.TestCase):
    def setUp(self):
        self.profile = {'state': 'active', 'connector': 'forward_butler'}
        self.connection = {'api_base': 'https://butler.example/v1', 'api_key': 'test-key',
                           'mailbox_email': 'final@example.test'}
        self.items = [self.item('first'), self.item('second')]
        self.calls = []

    def item(self, tag):
        return {'id': tag, 'address_norm': f'parent+{tag}@icloud.com',
                'acquisition_id': f'fixed-{tag}',
                'ownership': {'owner_kind': 'local_inventory', 'owner_id': 'local-instance',
                              'acquisition_id': f'fixed-{tag}'},
                'candidate': {'email': f'parent+{tag}@icloud.com', 'provider': 'icloud_hme',
                    'mailbox_email': 'final@example.test', 'identity_type': 'plus_alias',
                    'identity_id': f'identity-{tag}', 'parent_email': 'parent@icloud.com',
                    'recipient_mode': 'forwarded_exact_v1', 'strict_family': True}}

    def result(self, item):
        return {'requested_email': item['address_norm'], 'acquisition_id': item['acquisition_id'],
                'code': 200, 'mailbox': {**item['candidate'], **item['ownership'],
                                         'lease_id': 'fixed-lease'}}

    def invoke(self, results=None, *, error=None, items=None, provided_connection=False,
               response_payload=...):
        from core.email.email_butler import inventory_handoff as handoff

        def request(method, path, **kwargs):
            self.calls.append((method, path, kwargs))
            if error:
                raise error
            if response_payload is not ...:
                return response_payload
            return {'code': 200, 'results': results if results is not None
                    else [self.result(item) for item in self.items]}

        with patch('core.email.derivation._profile_credentials', return_value=self.connection) as credentials, \
             patch('core.email.email_butler.client._request', side_effect=request):
            output = handoff.handoff_selected_batch(
                self.items if items is None else items, self.profile, client_id='stable-client',
                **({'connection': self.connection} if provided_connection else {}))
            self.credential_calls = credentials.call_count
            return output

    def test_reordered_results_match_frozen_acquisition_and_address(self):
        output = self.invoke([self.result(self.items[1]), self.result(self.items[0])])
        self.assertEqual(output['fixed-first']['receipt'], {
            'owner_kind': 'local_inventory', 'owner_id': 'local-instance',
            'acquisition_id': 'fixed-first', 'client_id': 'stable-client',
            'identity_id': 'identity-first', 'parent_email': 'parent@icloud.com',
            'state': 'issued', 'version': 1})
        self.assertEqual(output['fixed-second']['receipt']['identity_id'], 'identity-second')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][:2], ('POST', '/mailboxes/import-batch'))
        self.assertEqual(self.calls[0][2]['json']['items'][0], {
            'requested_email': 'parent+first@icloud.com', 'provider': 'icloud_hme',
            'owner_kind': 'local_inventory', 'owner_id': 'local-instance',
            'acquisition_id': 'fixed-first'})
        self.assertEqual(self.credential_calls, 1)

    def test_item_rejection_does_not_discard_another_confirmed_handoff(self):
        rejected = {'requested_email': 'parent+second@icloud.com',
                    'acquisition_id': 'fixed-second', 'code': 409,
                    'error_code': 'acquisition_owner_conflict'}
        output = self.invoke([self.result(self.items[0]), rejected])
        self.assertIn('receipt', output['fixed-first'])
        self.assertEqual(output['fixed-second']['outcome'], 'failed')
        self.assertEqual(output['fixed-second']['error_code'], 'acquisition_owner_conflict')
        self.assertEqual(output['fixed-second']['status_code'], 409)

    def test_missing_result_only_leaves_its_original_acquisition_unknown(self):
        output = self.invoke([self.result(self.items[0])])
        self.assertIn('receipt', output['fixed-first'])
        self.assertEqual(output['fixed-second']['outcome'], 'unknown')
        self.assertEqual(output['fixed-second']['error_code'], 'handoff_response_invalid')

    def test_duplicate_response_cannot_confirm_duplicated_acquisition(self):
        first = self.result(self.items[0])
        output = self.invoke([first, deepcopy(first), self.result(self.items[1])])
        self.assertNotIn('receipt', output['fixed-first'])
        self.assertEqual(output['fixed-first']['error_code'], 'handoff_response_invalid')
        self.assertIn('receipt', output['fixed-second'])

    def test_unknown_response_identity_invalidates_envelope(self):
        output = self.invoke([self.result(self.items[0]), self.result(self.item('unexpected'))])
        self.assertTrue(all(result.get('error_code') == 'handoff_response_invalid'
                            for result in output.values()))

    def test_incomplete_response_identity_invalidates_envelope(self):
        output = self.invoke([self.result(self.items[0]), {'code': 200}])
        self.assertTrue(all(result.get('error_code') == 'handoff_response_invalid'
                            for result in output.values()))

    def test_swapped_addresses_never_confirm_either_acquisition(self):
        first, second = [self.result(item) for item in self.items]
        first['requested_email'], second['requested_email'] = second['requested_email'], first['requested_email']
        output = self.invoke([first, second])
        self.assertTrue(all('receipt' not in result for result in output.values()))
        self.assertTrue(all(result['outcome'] == 'unknown' for result in output.values()))

    def test_changed_complete_mailbox_or_ownership_cannot_be_imported(self):
        changes = ({'identity_id': 'replacement'}, {'owner_id': 'other-owner'},
                   {'acquisition_id': 'other-acquisition'}, {'lease_id': ''},
                   {'strict_family': False}, {'mailbox_email': 'other@example.test'})
        for change in changes:
            with self.subTest(change=change):
                first = self.result(self.items[0])
                first['mailbox'].update(change)
                output = self.invoke([first, self.result(self.items[1])])
                self.assertEqual(output['fixed-first']['error_code'], 'handoff_identity_mismatch')
                self.assertEqual(output['fixed-first']['outcome'], 'unknown')
                self.assertIn('receipt', output['fixed-second'])

    def test_malformed_item_status_does_not_confirm_mailbox(self):
        for code in (None, True, '200', [], 201, 302):
            with self.subTest(code=code):
                first = self.result(self.items[0])
                first['code'] = code
                output = self.invoke([first, self.result(self.items[1])])
                self.assertEqual(output['fixed-first']['error_code'], 'handoff_response_invalid')
                self.assertIn('receipt', output['fixed-second'])

    def test_malformed_envelope_leaves_every_original_acquisition_unknown(self):
        for payload in (None, [], {'code': 200}, {'code': '200', 'results': []},
                        {'code': 200, 'results': {}}, {'code': 500, 'results': []}):
            with self.subTest(payload=payload):
                output = self.invoke(response_payload=payload)
                self.assertEqual(set(output), {'fixed-first', 'fixed-second'})
                self.assertTrue(all(result['outcome'] == 'unknown' and
                    result['error_code'] == 'handoff_response_invalid' for result in output.values()))

    def test_non_string_lease_never_confirms_handoff(self):
        for lease in (True, 123, [], {}):
            with self.subTest(lease=lease):
                first = self.result(self.items[0])
                first['mailbox']['lease_id'] = lease
                output = self.invoke([first, self.result(self.items[1])])
                self.assertEqual(output['fixed-first']['error_code'], 'handoff_identity_mismatch')

    def test_timeout_retries_only_the_original_batch_acquisitions(self):
        output = self.invoke(error=TimeoutError('simulated'))
        self.assertTrue(all(result['outcome'] == 'unknown' for result in output.values()))
        self.assertTrue(all(result['error_code'] == 'handoff_timeout' for result in output.values()))
        self.invoke()
        self.assertEqual(self.calls[0][2]['json'], self.calls[1][2]['json'])

    def test_transient_http_item_failures_remain_unknown(self):
        for code in (408, 425, 429, 500, 503):
            with self.subTest(code=code):
                first = self.result(self.items[0])
                first.update(code=code, error_code='remote_temporarily_unavailable')
                output = self.invoke([first, self.result(self.items[1])])
                self.assertEqual(output['fixed-first']['outcome'], 'unknown')
                self.assertEqual(output['fixed-first']['status_code'], code)

    def test_http_rejection_and_transient_failure_keep_classification(self):
        from core.email.email_butler.client import EmailButlerClientError
        for code, outcome in ((401, 'failed'), (429, 'unknown'), (503, 'unknown')):
            with self.subTest(code=code):
                output = self.invoke(error=EmailButlerClientError(
                    'message-must-not-be-copied', status_code=code, error_code='remote_error'))
                self.assertTrue(all(result['outcome'] == outcome for result in output.values()))
                self.assertTrue(all(result['status_code'] == code for result in output.values()))
                self.assertNotIn('message-must-not-be-copied', str(output))

    def test_provided_connection_never_reloads_fixed_credentials(self):
        output = self.invoke(provided_connection=True)
        self.assertIn('receipt', output['fixed-first'])
        self.assertEqual(self.credential_calls, 0)

    def test_oversize_or_duplicate_input_never_submits_partial_batch(self):
        for items in ([self.item(str(index)) for index in range(26)],
                      [self.items[0], deepcopy(self.items[0])]):
            with self.subTest(count=len(items)):
                with self.assertRaisesRegex(ValueError, 'handoff_'):
                    self.invoke(items=items)
        self.assertEqual(self.calls, [])

    def test_25_frozen_items_use_one_http_request(self):
        items = [self.item(str(index)) for index in range(25)]
        output = self.invoke([self.result(item) for item in reversed(items)], items=items)
        self.assertEqual(len(output), 25)
        self.assertTrue(all('receipt' in result for result in output.values()))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0][2]['json']['items']), 25)

    def test_changed_local_acquisition_or_address_never_mutates_remote(self):
        for key, value in (('acquisition_id', 'replacement'), ('address_norm', 'other@icloud.com')):
            with self.subTest(key=key):
                item = deepcopy(self.items[0])
                item[key] = value
                with self.assertRaisesRegex(ValueError, 'handoff_identity_mismatch'):
                    self.invoke(items=[item])
        self.assertEqual(self.calls, [])

    def test_single_handoff_can_reuse_connection_without_changing_receipt(self):
        from core.email.email_butler import inventory_handoff as handoff
        with patch('core.email.derivation._profile_credentials') as credentials, \
             patch('core.email.email_butler.client._request', return_value=self.result(self.items[0])):
            receipt = handoff.handoff_selected(self.items[0]['candidate'], self.profile,
                ownership=self.items[0]['ownership'], client_id='stable-client', connection=self.connection)
        self.assertEqual(receipt['identity_id'], 'identity-first')
        credentials.assert_not_called()

