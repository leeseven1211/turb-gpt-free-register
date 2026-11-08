"""v2 业务适配保留原身份、时间窗与验证码事件，不执行真实网络或等待。"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.email.email_butler import client, lease_bindings, v2

ADDRESS = 'parent+original@example.test'
BASE = 'https://butler.example/v2'
KEY = 'fixture-private-api-key'
ANCHOR = 1794096000.0


def matched(**changes):
    return {'lease_id': 'lse_original', 'service': 'openai', 'status': 'matched',
            'verification_code': '123456', 'code_id': 'code_original_delivery',
            'received_at': datetime.fromtimestamp(ANCHOR + 5, timezone.utc).isoformat(), **changes}


def pending(state='pending'):
    return {'lease_id': 'lse_original', 'service': 'openai', 'status': state,
            'verification_code': None, 'code_id': None, 'received_at': None}


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ButlerV2ClientTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.account = client.EmailButlerAccount(email=ADDRESS, mailbox_id='', provider='icloud_hme',
            api_base=BASE, api_key=KEY, acquisition_id='acquisition-original',
            credential_ref='credential-original', client_id='client-original')
        self.binding = {'lease_id': 'lse_original', 'client_id': 'client-original', 'api_base': BASE,
                        'credential_ref': 'credential-original', 'service': 'openai', 'address_norm': ADDRESS}
        self.clock = Clock()
        self.stack.enter_context(patch.dict(client._CONTEXT_CACHE, {}, clear=True))
        self.resolve = self.stack.enter_context(patch.object(lease_bindings, 'resolve', return_value=self.binding))
        self.code = self.stack.enter_context(patch.object(v2, 'code', return_value=matched()))
        self.observe = self.stack.enter_context(patch('core.auth.email_guard.observe_candidate'))
        self.session = self.stack.enter_context(patch('core.auth.email_guard.current_session', return_value=None))
        self.stack.enter_context(patch.object(client.time, 'monotonic', side_effect=self.clock.monotonic))
        self.stack.enter_context(patch.object(client, 'bounded_sleep', side_effect=self.clock.sleep))
        self.old = self.stack.enter_context(patch.object(client, '_request', side_effect=AssertionError('不能调用退役接口')))

    def fetch(self, **kwargs):
        return client._fetch_v2_otp(self.account, after_ts=kwargs.pop('after_ts', ANCHOR),
                                   max_wait=kwargs.pop('max_wait', 46), **kwargs)

    def test_matched_records_v2_event_and_exact_recipient_evidence_without_secrets(self):
        self.assertEqual(self.fetch(), '123456')
        self.resolve.assert_called_once_with(ADDRESS, api_base=BASE, api_key=KEY,
            credential_ref='credential-original', acquisition_id='acquisition-original',
            lease_id='', client_id='client-original')
        args, kwargs = self.observe.call_args
        self.assertTrue(args[0].startswith('butler-v2:'))
        self.assertTrue(args[0].endswith(':code_original_delivery'))
        self.assertEqual(kwargs['evidence']['contract'], 'butler.v2.lease')
        self.assertEqual(kwargs['evidence']['recipient'], ADDRESS)
        self.assertEqual(kwargs['evidence']['service'], 'openai')
        self.assertEqual(kwargs['cursor']['butler_v2_lease_id'], 'lse_original')
        self.assertEqual(kwargs['cursor']['butler_v2_after_code_id'], 'code_original_delivery')
        self.assertNotIn('recipient_evidence', kwargs['evidence'])
        self.assertNotIn(KEY, repr(kwargs))
        self.assertNotIn('123456', repr(kwargs))
        self.assertNotIn(KEY, repr(self.account))
        self.old.assert_not_called()

    def test_all_providers_use_the_same_pinned_lease_code_api(self):
        for provider in ('icloud_hme', 'outlook_graph', 'cloudflare', 'mailcom'):
            self.account.provider = provider
            client._CONTEXT_CACHE[ADDRESS] = self.account
            with self.subTest(provider=provider):
                self.assertEqual(client.fetch_latest_otp(ADDRESS, after_ts=ANCHOR, max_wait=5), '123456')
        self.assertEqual(self.code.call_count, 4)
        self.assertTrue(all(call.args == ('lse_original',) for call in self.code.call_args_list))

    def test_twenty_second_chunks_share_total_budget_and_exact_since(self):
        def no_mail(_lease_id, **kwargs):
            self.clock.now += kwargs['wait_seconds']
            return pending()
        self.code.side_effect = no_mail
        with self.assertRaises(client.EmailButlerClientError) as caught:
            self.fetch(max_wait=46, poll_interval=1)
        self.assertEqual(caught.exception.error_code, 'inbound_code_timeout')
        self.assertEqual([call.kwargs['wait_seconds'] for call in self.code.call_args_list], [20, 20, 4])
        self.assertEqual(self.clock.now, 46)
        expected = datetime.fromtimestamp(ANCHOR, timezone.utc).isoformat().replace('+00:00', 'Z')
        self.assertTrue(all(call.kwargs['since'] == expected for call in self.code.call_args_list))
        self.observe.assert_not_called()

    def test_fractional_and_epoch_since_are_not_shifted_back_or_replaced(self):
        for anchor in (0.0, ANCHOR + .75):
            self.code.return_value = matched(received_at=datetime.fromtimestamp(anchor + 1, timezone.utc).isoformat())
            with self.subTest(anchor=anchor):
                self.assertEqual(self.fetch(after_ts=anchor), '123456')
                self.assertEqual(self.code.call_args.kwargs['since'],
                    datetime.fromtimestamp(anchor, timezone.utc).isoformat().replace('+00:00', 'Z'))

    def test_ambiguous_never_selects_a_code_or_falls_back_to_local_mailbox(self):
        def ambiguous(_lease_id, **kwargs):
            self.clock.now += kwargs['wait_seconds']
            return pending('ambiguous')
        self.code.side_effect = ambiguous
        local = Mock(return_value='999999')
        with self.assertRaises(client.EmailButlerClientError) as caught:
            client.fetch_inbound_otp(ADDRESS, after_ts=ANCHOR, max_wait=5, api_base=BASE, api_key=KEY,
                                     acquisition_id='acquisition-original', local_probe=local)
        self.assertEqual(caught.exception.error_code, 'inbound_code_ambiguous')
        self.observe.assert_not_called()
        local.assert_not_called()

    def test_nonretryable_rejections_fail_immediately_with_original_classification(self):
        for code, status in (('invalid_api_key', 401), ('permission_denied', 403), ('lease_expired', 410),
                             ('recipient_ambiguous', 409)):
            self.code.reset_mock()
            self.code.side_effect = v2.ButlerV2Error(code, status_code=status, request_id='req_original')
            with self.subTest(code=code), self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch()
            self.assertEqual(caught.exception.error_code, code)
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(caught.exception.request_id, 'req_original')
            self.code.assert_called_once()
            self.assertEqual(self.clock.now, 0)

    def test_retryable_provider_failure_continues_original_lease_until_match(self):
        self.code.side_effect = [v2.ButlerV2Error('provider_unavailable', status_code=502, retryable=True), matched()]
        self.assertEqual(self.fetch(poll_interval=1), '123456')
        self.assertEqual(self.code.call_count, 2)
        self.assertEqual(self.resolve.call_count, 1)
        self.assertTrue(all(call.args == ('lse_original',) for call in self.code.call_args_list))
        self.assertEqual(self.clock.now, 1)

    def test_retryable_failure_and_empty_mail_keep_different_final_causes(self):
        for failure, expected in ((pending(), 'inbound_code_timeout'),
                                  (v2.ButlerV2Error('butler_transport_timeout', retryable=True), 'butler_transport_timeout')):
            self.clock.now = 0
            def result(_lease_id, **kwargs):
                self.clock.now += kwargs['wait_seconds']
                if isinstance(failure, Exception):
                    raise failure
                return failure
            self.code.side_effect = result
            with self.subTest(expected=expected), self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(max_wait=2)
            self.assertEqual(caught.exception.error_code, expected)

    def test_bad_format_wrong_service_wrong_lease_and_prechallenge_mail_are_rejected(self):
        variants = [({'verification_code': 'ABC123'}, 'otp_format_invalid'),
                    ({'service': 'grok'}, 'lease_identity_mismatch'),
                    ({'lease_id': 'lse_replacement'}, 'lease_identity_mismatch'),
                    ({'received_at': datetime.fromtimestamp(ANCHOR - .1, timezone.utc).isoformat()}, 'otp_before_challenge')]
        for changes, expected in variants:
            self.code.return_value = matched(**changes)
            with self.subTest(expected=expected), self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch()
            self.assertEqual(caught.exception.error_code, expected)
        self.observe.assert_not_called()

    def test_resume_cursor_applies_only_to_the_same_lease(self):
        for lease_id, expected in (('lse_original', 'code_previous_delivery'), ('lse_other', None)):
            self.session.return_value = SimpleNamespace(row={'cursor': {
                'butler_v2_lease_id': lease_id, 'butler_v2_after_code_id': 'code_previous_delivery'}})
            with self.subTest(lease_id=lease_id):
                self.assertEqual(self.fetch(), '123456')
                self.assertEqual(self.code.call_args.kwargs['after_code_id'], expected)

    def test_mapping_failure_happens_before_code_or_legacy_http(self):
        self.resolve.side_effect = v2.ButlerV2Error('lease_client_mismatch', status_code=403)
        with self.assertRaises(client.EmailButlerClientError) as caught:
            self.fetch()
        self.assertEqual(caught.exception.error_code, 'lease_client_mismatch')
        self.code.assert_not_called()
        self.old.assert_not_called()

    def test_success_keeps_remote_reading_rights_and_unknown_does_not_report_failure(self):
        with patch('core.email.inventory.record_outcome', return_value=True) as outcome, patch.object(v2, 'release') as release:
            client.release_account(ADDRESS, status='success', note='注册成功')
            outcome.assert_called_once_with(ADDRESS, source='email_butler', status='success', note='注册成功')
            release.assert_not_called()
            outcome.reset_mock()
            client.release_account(ADDRESS, status='request_unknown')
            outcome.assert_not_called()

    def test_explicit_return_releases_only_resolved_original_id_and_saves_receipt(self):
        result = {'id': 'lse_original', 'email': ADDRESS, 'service': 'openai', 'client_id': 'client-original',
                  'status': 'released', 'service_tag_removed': True, 'already_inactive': False}
        with patch.object(v2, 'release', return_value=result) as release, patch.object(lease_bindings, 'save') as save:
            response = client.return_account(ADDRESS, api_base=BASE, api_key=KEY,
                                             acquisition_id='acquisition-original', lease_id='lse_original')
        self.assertTrue(response['ok'])
        self.resolve.assert_called_once_with(ADDRESS, api_base=BASE, api_key=KEY,
            acquisition_id='acquisition-original', lease_id='lse_original', credential_ref='',
            client_id='', for_release=True)
        release.assert_called_once_with('lse_original', api_base=BASE, api_key=KEY, reason='Turb 显式删除未使用邮箱')
        self.assertEqual(save.call_args.kwargs['client_id'], 'client-original')
        self.assertNotIn(KEY, repr(response))

    def test_return_from_fixed_context_checks_original_handoff_client(self):
        self.account.lease_id = 'lse_original'
        self.resolve.side_effect = v2.ButlerV2Error('lease_client_mismatch', status_code=403)
        with (patch.object(client, '_return_account_context', return_value=(self.account, 'acquisition-original')),
              patch.object(v2, 'release') as release):
            response = client.return_account(ADDRESS)
        self.assertFalse(response['ok'])
        self.assertEqual(self.resolve.call_args.kwargs['client_id'], 'client-original')
        self.assertEqual(self.resolve.call_args.kwargs['credential_ref'], 'credential-original')
        release.assert_not_called()

    def test_unverified_old_return_cannot_release_later_lease(self):
        self.resolve.side_effect = v2.ButlerV2Error('lease_original_mapping_required')
        with patch.object(v2, 'release') as release:
            response = client.return_account(ADDRESS, api_base=BASE, api_key=KEY, acquisition_id='old-acquisition')
        self.assertFalse(response['ok'])
        self.assertEqual(response['error_code'], 'lease_original_mapping_required')
        release.assert_not_called()

    def test_restore_local_provider_keeps_fixed_route_and_original_handoff(self):
        from core.storage import records
        from core.email import derivation
        profile = {'id': 7, 'state': 'active', 'connector': 'forward_butler', 'credential_ref': 'credential-original'}
        row = {'email': ADDRESS, 'local_inbox_profile_id': 7, 'provider': 'outlook_graph',
               'local_acquisition_id': 'local-task-only', 'butler_handoff': {
                   'lease_id': 'lse_original', 'acquisition_id': 'acquisition-original', 'client_id': 'client-original'}}
        with patch.object(records, 'get_row', return_value=profile), patch.object(derivation, '_profile_credentials',
                return_value={'api_base': BASE, 'api_key': KEY, 'mailbox_email': ''}):
            account = client.restore_local_account(row)
        self.assertEqual((account.provider, account.client_id, account.lease_id, account.acquisition_id),
                         ('outlook_graph', 'client-original', 'lse_original', 'acquisition-original'))
        self.assertEqual(account.credential_ref, 'credential-original')
        self.resolve.assert_not_called()
        self.code.assert_not_called()
