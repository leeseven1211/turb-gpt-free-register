# -*- coding: utf-8 -*-
"""公共入口使用 v2，并保留诊断分类、固定身份和未知请求保护。"""
from contextlib import ExitStack
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from core.email.email_butler import client, lease_bindings, v2


class EmailButlerClientTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(client._CONTEXT_CACHE, {}, clear=True))
        self.stack.enter_context(patch.multiple(client._email_cfg,
            EMAIL_BUTLER_API_BASE='https://butler.example/v2', EMAIL_BUTLER_API_KEY='fixture-key'))
        self.binding = {'lease_id': 'lse_original', 'client_id': 'client-original',
                        'credential_ref': 'fixed-reference', 'api_base': 'https://butler.example/v2'}
        self.resolve = self.stack.enter_context(patch.object(lease_bindings, 'resolve', return_value=self.binding))
        self.stack.enter_context(patch('core.auth.email_guard.current_session', return_value=None))
        self.stack.enter_context(patch('core.auth.email_guard.observe_candidate'))
        self.clock = 0.0
        self.stack.enter_context(patch.object(client.time, 'monotonic', side_effect=lambda: self.clock))
        self.stack.enter_context(patch.object(client, 'bounded_sleep', side_effect=self.sleep))

    def sleep(self, seconds):
        self.clock += seconds

    def matched(self):
        return {'lease_id': 'lse_original', 'service': 'openai', 'status': 'matched',
                'verification_code': '654321', 'code_id': 'code_delivery',
                'received_at': datetime.fromtimestamp(105, timezone.utc).isoformat()}

    def fetch(self, **kwargs):
        return client.fetch_inbound_otp('alias@icloud.com', after_ts=100.0, **kwargs)

    def test_scan_returns_explicit_unsupported_without_inventing_signal_fields(self):
        with patch.object(v2.requests, 'request') as request:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                client.scan_openai_deactivation('a@example.com')
        self.assertEqual(caught.exception.error_code, 'signal_scan_unsupported')
        request.assert_not_called()

    def test_scan_bulk_preserves_each_address_failure_without_repeating_retired_requests(self):
        with patch.object(v2.requests, 'request') as request:
            results = client.scan_openai_deactivation_bulk(['a@example.test', 'b@example.test'], mailbox_email='final@example.test')
        self.assertEqual(set(results), {'a@example.test', 'b@example.test'})
        self.assertTrue(all(not value['ok'] and value['error_code'] == 'signal_scan_unsupported' for value in results.values()))
        request.assert_not_called()

    def test_connection_reports_real_v2_permissions_without_requiring_retired_signal_capability(self):
        who = {'client_id': 'client-original', 'allowed_services': ['openai'],
               'permissions': ['codes.read'], 'limits': {'wait_seconds': 20}}
        with patch.object(v2, 'me', return_value=who):
            result = client.test_connection()
        self.assertTrue(result['ok'])
        self.assertFalse(result['ready'])
        self.assertEqual(result['api_version'], 2)
        self.assertIn('leases.read', result['missing_permissions'])
        self.assertNotIn('signals.scan', result['missing_permissions'])

    def test_restore_context_restores_exact_existing_identity_without_claim(self):
        original = client.EmailButlerAccount(email='restore@example.com', mailbox_id='',
            lease_id='lse_original', api_base='https://fixed.example/v2', api_key='fixture-key')
        with patch.object(client, 'restore_local_account', return_value=original) as restore, patch.object(v2, 'create_lease') as create:
            account = client.restore_account_context('restore@example.com')
        self.assertIs(account, original)
        restore.assert_called_once_with('restore@example.com')
        create.assert_not_called()

    def test_fetch_inbound_otp_uses_original_v2_lease_and_exact_challenge_time(self):
        with patch.object(v2, 'code', return_value=self.matched()) as request:
            otp = self.fetch(max_wait=15, poll_interval=1, settle_seconds=0)
        self.assertEqual(otp, '654321')
        self.assertEqual(request.call_args.args, ('lse_original',))
        self.assertEqual(request.call_args.kwargs['since'], '1970-01-01T00:01:40Z')
        self.assertEqual(request.call_args.kwargs['wait_seconds'], 15)
        self.assertEqual(client.get_account_context('alias@icloud.com').lease_id, 'lse_original')

    def test_inbound_wait_continues_after_transient_connection_error_on_same_lease(self):
        with patch.object(v2, 'code', side_effect=[v2.ButlerV2Error('butler_transport_connection', retryable=True), self.matched()]) as request:
            self.assertEqual(self.fetch(max_wait=15), '654321')
        self.assertEqual(request.call_count, 2)
        self.assertEqual({call.args[0] for call in request.call_args_list}, {'lse_original'})
        self.assertEqual(self.resolve.call_count, 1)

    def test_inbound_wait_continues_after_gateway_524_with_bounded_chunks(self):
        with patch.object(v2, 'code', side_effect=[v2.ButlerV2Error('butler_http_524', status_code=524, retryable=True), self.matched()]) as request:
            self.assertEqual(self.fetch(max_wait=160), '654321')
        self.assertEqual(request.call_count, 2)
        self.assertTrue(all(call.kwargs['wait_seconds'] <= 20 for call in request.call_args_list))

    def test_inbound_wait_does_not_retry_auth_error(self):
        with patch.object(v2, 'code', side_effect=v2.ButlerV2Error('invalid_api_key', status_code=401)) as request:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(max_wait=160)
        self.assertEqual(caught.exception.error_code, 'invalid_api_key')
        request.assert_called_once()

    def test_inbound_wait_does_not_bypass_v2_authorization_with_local_probe(self):
        probe = Mock(return_value='135790')
        def pending(_lease_id, **kwargs):
            self.clock += kwargs['wait_seconds']
            return {'lease_id': 'lse_original', 'service': 'openai', 'status': 'pending'}
        with patch.object(v2, 'code', side_effect=pending):
            with self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(max_wait=2, local_probe=probe)
        self.assertEqual(caught.exception.error_code, 'inbound_code_timeout')
        probe.assert_not_called()

    def test_inbound_wait_preserves_no_mail_and_api_failure_as_different_diagnostics(self):
        cases = [(None, 'inbound_code_timeout'),
                 (v2.ButlerV2Error('butler_transport_timeout', retryable=True), 'butler_transport_timeout'),
                 (v2.ButlerV2Error('provider_unavailable', status_code=502, retryable=True), 'provider_unavailable')]
        for outcome, expected in cases:
            self.clock = 0
            def result(_lease_id, **kwargs):
                self.clock += kwargs['wait_seconds']
                if outcome:
                    raise outcome
                return {'lease_id': 'lse_original', 'service': 'openai', 'status': 'pending'}
            with self.subTest(expected=expected), patch.object(v2, 'code', side_effect=result):
                with self.assertRaises(client.EmailButlerClientError) as caught:
                    self.fetch(max_wait=1)
            self.assertEqual(caught.exception.error_code, expected)
            self.assertFalse(caught.exception.definite_rejection)
            self.assertNotIsInstance(caught.exception, TimeoutError)

    def test_recipient_receipt_errors_keep_the_actual_local_validation_cause(self):
        from core.registration.failure_diagnostics import RegistrationFailureDiagnostics
        from core.operations.errors import registration_diagnostic_cause_code
        match = {'email': 'alias+one@icloud.com', 'strict_family': False, 'mailbox_email': 'inbox@example.test'}
        payload = {'recipient_mode': 'forwarded_exact_v1', 'recipient_match': match}
        cases = [({}, 'recipient_contract_unsupported'),
                 ({**payload, 'recipient_match': {**match, 'email': 'other@icloud.com'}}, 'recipient_mismatch'),
                 ({**payload, 'recipient_match': {**match, 'mailbox_email': 'other@example.test'}}, 'mailbox_mismatch'),
                 (payload, 'recipient_evidence_missing')]
        for receipt, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(client.EmailButlerClientError) as caught:
                client._validate_recipient_receipt(receipt, 'alias+one@icloud.com', False, 'inbox@example.test')
            diagnostics = RegistrationFailureDiagnostics()
            diagnostics.progress('email_otp', 'running')
            self.assertEqual(registration_diagnostic_cause_code(diagnostics.failure(caught.exception)), expected)

    def test_retired_non_idempotent_request_is_blocked_without_http_or_reallocation(self):
        with patch.object(v2.requests, 'request') as request:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                client._request('POST', '/mailboxes', json={'purpose': 'registration'},
                                api_base='http://example.test/v1', api_key='secret')
        self.assertEqual(caught.exception.error_code, 'api_version_retired')
        request.assert_not_called()

    def test_non_idempotent_v2_failure_preserves_original_intent_without_retry(self):
        with patch.object(v2.requests, 'request', side_effect=v2.requests.ConnectionError('private endpoint')) as request:
            with self.assertRaises(v2.ButlerV2Error) as caught:
                v2.create_lease(api_base='https://butler.example/v2', api_key='fixture-key',
                                external_ref='original-intent', idempotency_key='original-key')
        request.assert_called_once()
        self.assertTrue(caught.exception.request_unknown)
        self.assertNotIn('private endpoint', str(caught.exception))
