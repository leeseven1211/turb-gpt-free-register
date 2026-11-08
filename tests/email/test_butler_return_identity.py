"""删除外围退号须使用原远端交接编号及固定连接。"""
import unittest
from unittest.mock import patch

from core.email.email_butler import client
from core.email.email_butler import lease_bindings, v2


class ButlerReturnIdentityTests(unittest.TestCase):
    def test_return_uses_original_acquisition_and_fixed_connection(self):
        account = client.EmailButlerAccount(email='alias@icloud.com', mailbox_id='',
            acquisition_id='remote-import-one', api_base='https://fixed.example.test/v1', api_key='test-key')
        binding = {'lease_id': 'lse_original', 'client_id': 'original-client', 'credential_ref': 'ORIGINAL_KEY'}
        released = {'id': 'lse_original', 'email': account.email, 'service': 'openai',
                    'client_id': 'original-client', 'status': 'released'}
        with patch.object(client, '_return_account_context', return_value=(account, account.acquisition_id)), patch.object(
                lease_bindings, 'resolve', return_value=binding) as resolve, patch.object(
                v2, 'release', return_value=released) as request, patch.object(lease_bindings, 'save'):
            self.assertTrue(client.return_account(account.email)['ok'])
        self.assertEqual(resolve.call_args.args, (account.email,))
        self.assertEqual(resolve.call_args.kwargs['acquisition_id'], 'remote-import-one')
        self.assertTrue(resolve.call_args.kwargs['for_release'])
        self.assertEqual(request.call_args.args, ('lse_original',))
        self.assertEqual(request.call_args.kwargs['api_base'], account.api_base)
        self.assertEqual(request.call_args.kwargs['api_key'], account.api_key)

    def test_explicit_lease_never_looks_up_or_renews_identity(self):
        binding = {'lease_id': 'original-lease', 'client_id': 'original-client', 'credential_ref': 'ORIGINAL_KEY'}
        released = {'id': 'original-lease', 'email': 'alias@icloud.com', 'service': 'openai',
                    'client_id': 'original-client', 'status': 'released'}
        with patch.object(client, '_return_account_context', side_effect=AssertionError('不应查找替代身份')), patch.object(
                lease_bindings, 'resolve', return_value=binding) as resolve, patch.object(
                v2, 'release', return_value=released) as request, patch.object(lease_bindings, 'save'), patch.object(
                v2, 'renew', side_effect=AssertionError('退租不得续租')):
            self.assertTrue(client.return_account('alias@icloud.com', lease_id='original-lease',
                api_base='https://fixed.example.test/v1', api_key='fixture-key', client_id='original-client')['ok'])
        self.assertEqual(resolve.call_args.kwargs['lease_id'], 'original-lease')
        self.assertEqual(resolve.call_args.kwargs['client_id'], 'original-client')
        self.assertEqual(request.call_args.args, ('original-lease',))

    def test_missing_fixed_context_is_a_failure_without_remote_request(self):
        with patch.object(client, '_return_account_context', side_effect=client.EmailButlerClientError(
                'fixed_route_unavailable')), patch.object(client, '_request') as request:
            result = client.return_account('alias@icloud.com')
        self.assertFalse(result['ok'])
        request.assert_not_called()

    def test_tombstone_keeps_remote_handoff_instead_of_local_acquisition(self):
        from core.storage.email import local_imports
        from core.storage import records
        from core.email import derivation

        row = {'status': 'tombstone', 'local_inbox_profile_id': 7, 'provider': 'icloud_hme',
               'local_acquisition_id': 'local-registration-task', 'butler_handoff': {'acquisition_id': 'remote-import'}}
        profile = {'state': 'active', 'connector': 'forward_butler', 'credential_ref': 'ORIGINAL_KEY'}
        with patch.object(local_imports, 'get_butler_email', return_value=row), patch.object(
                records, 'get_row', return_value=profile), patch.object(derivation, '_profile_credentials', return_value={
                    'api_base': 'https://fixed.example.test/v1', 'api_key': 'test-key'}):
            context, acquisition = client._return_account_context('alias@icloud.com')
        self.assertEqual(acquisition, 'remote-import')
        self.assertEqual(context.acquisition_id, 'remote-import')
