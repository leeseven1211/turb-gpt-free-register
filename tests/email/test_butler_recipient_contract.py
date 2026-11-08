# -*- coding: utf-8 -*-
"""Butler 严格收件契约及固定连接器的回归测试。"""
import os
import unittest
from unittest.mock import Mock, patch

from core.email.email_butler import client as client, lease_bindings, v2
from core.email import derivation as derivation
from core.email import forward_imap as forward
from core.email.icloud_hide import client as hme


CHILD = "alias+child@icloud.com"
PARENT = "alias@icloud.com"
MAILBOX = "final@example.test"
BASE = "https://butler.example.test/v1"


def receipt(target=CHILD, strict=False, mailbox=MAILBOX):
    return {
        "code": 200, "verification_code": "654321", "recipient_mode": "forwarded_exact_v1",
        "recipient_match": {"email": target, "strict_family": strict, "mailbox_email": mailbox},
        "recipient_evidence": {"original_recipients": [target]},
    }


class ButlerRecipientContractTests(unittest.TestCase):
    def setUp(self):
        self.config = patch.multiple(client._email_cfg, EMAIL_BUTLER_API_BASE=BASE, EMAIL_BUTLER_API_KEY="test-key")
        self.config.start()
        self.addCleanup(self.config.stop)
        self.cache = patch.dict(client._CONTEXT_CACHE, {}, clear=True)
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.binding = {'lease_id': 'lse_original', 'client_id': 'fixture-client',
                        'api_base': BASE.replace('/v1', '/v2'), 'credential_ref': 'fixture-reference'}
        self.result = {'lease_id': 'lse_original', 'service': 'openai', 'status': 'matched',
                       'verification_code': '654321', 'code_id': 'code_delivery',
                       'received_at': '1970-01-01T00:01:45Z'}

    def fetch(self, **kwargs):
        return client.fetch_inbound_otp(CHILD, after_ts=100, max_wait=1,
            require_recipient_evidence=True, mailbox_email=MAILBOX, **kwargs)

    def test_v2_request_preserves_full_child_pinned_endpoint_and_challenge_time(self):
        fixed = 'https://pinned.example.test/v2'
        with patch.object(lease_bindings, 'resolve', return_value={**self.binding, 'api_base': fixed}) as resolve, patch.object(
                v2, 'code', return_value=self.result) as request:
            self.assertEqual(self.fetch(api_base=fixed, api_key='pinned-key'), '654321')
        self.assertEqual(resolve.call_args.args, (CHILD,))
        self.assertEqual(resolve.call_args.kwargs['api_base'], fixed)
        self.assertEqual(resolve.call_args.kwargs['api_key'], 'pinned-key')
        self.assertEqual(request.call_args.args, ('lse_original',))
        self.assertEqual(request.call_args.kwargs['since'], '1970-01-01T00:01:40Z')
        self.assertEqual(request.call_args.kwargs['api_base'], fixed)
        self.assertEqual(request.call_args.kwargs['api_key'], 'pinned-key')

    def test_missing_v2_authorization_blocks_before_code_request(self):
        with patch.object(lease_bindings, 'resolve', side_effect=v2.ButlerV2Error(
                'permission_denied', status_code=403)), patch.object(v2, 'code') as request:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(api_base=BASE)
        self.assertEqual(caught.exception.error_code, 'permission_denied')
        request.assert_not_called()

    def test_service_without_v2_does_not_fall_back_to_retired_endpoint(self):
        with patch.object(lease_bindings, 'resolve', side_effect=v2.ButlerV2Error(
                'butler_http_404', status_code=404)), patch.object(client, '_request') as retired:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(api_base=BASE)
        self.assertEqual(caught.exception.error_code, 'butler_http_404')
        retired.assert_not_called()

    def test_authorization_context_isolated_by_endpoint_and_key(self):
        calls = []
        def resolve(_email, **kwargs):
            calls.append((kwargs['api_base'], kwargs['api_key']))
            if kwargs['api_key'] != 'capable-key':
                raise v2.ButlerV2Error('invalid_api_key', status_code=401)
            return self.binding
        with patch.object(lease_bindings, 'resolve', side_effect=resolve), patch.object(v2, 'code', return_value=self.result):
            for _ in range(2):
                self.assertEqual(self.fetch(api_base=BASE, api_key='capable-key'), '654321')
            for base in (BASE, 'https://other.example.test/v2'):
                with self.assertRaises(client.EmailButlerClientError) as caught:
                    self.fetch(api_base=base, api_key='old-key')
                self.assertEqual(caught.exception.error_code, 'invalid_api_key')
        self.assertEqual(calls, [(BASE, 'capable-key'), (BASE, 'capable-key'),
                                 (BASE, 'old-key'), ('https://other.example.test/v2', 'old-key')])

    def test_historical_receipt_validator_keeps_full_recipient_and_evidence_guards(self):
        cases = [
            ({'code': 200, 'verification_code': '654321'}, 'recipient_contract_unsupported'),
            ({**receipt(), 'recipient_match': {'email': PARENT, 'strict_family': False, 'mailbox_email': MAILBOX}}, 'recipient_mismatch'),
            ({**receipt(), 'recipient_match': {'email': CHILD, 'strict_family': False, 'mailbox_email': 'other@example.test'}}, 'mailbox_mismatch'),
            ({**receipt(), 'recipient_match': {'email': CHILD, 'strict_family': True, 'mailbox_email': MAILBOX}}, 'recipient_mismatch'),
            ({**receipt(), 'recipient_evidence': {}}, 'recipient_evidence_missing'),
            ({**receipt(), 'recipient_evidence': {'original_recipients': [PARENT]}}, 'recipient_mismatch'),
            ({**receipt(), 'recipient_evidence': {'original_recipients': [CHILD, 'alias+other@icloud.com']}}, 'recipient_ambiguous'),
        ]
        for payload, error in cases:
            with self.subTest(error=error), self.assertRaises(client.EmailButlerClientError) as caught:
                client._validate_recipient_receipt(payload, CHILD, False, MAILBOX)
            self.assertEqual(caught.exception.error_code, error)

    def test_strict_parent_uses_original_lease_and_never_probes_imap(self):
        local = Mock(return_value='111111')
        with patch.object(lease_bindings, 'resolve', return_value=self.binding) as resolve, patch.object(
                v2, 'code', return_value=self.result):
            self.assertEqual(client.fetch_inbound_otp(PARENT, after_ts=100, max_wait=1, strict_family=True,
                mailbox_email=MAILBOX, local_probe=local, api_base=BASE), '654321')
        self.assertEqual(resolve.call_args.args, (PARENT,))
        local.assert_not_called()

    def test_historical_strict_parent_with_only_displayed_parent_is_ambiguous(self):
        payload = {**receipt(PARENT, strict=True), 'recipient_evidence': {
            'original_recipients': [], 'displayed_recipients': [PARENT], 'hme_recipients': [PARENT]}}
        with self.assertRaises(client.EmailButlerClientError) as caught:
            client._validate_recipient_receipt(payload, PARENT, True, MAILBOX)
        self.assertEqual(caught.exception.error_code, 'recipient_ambiguous')

    def test_server_recipient_rejection_preserves_classification_without_imap_probe(self):
        local = Mock(return_value='111111')
        with patch.object(lease_bindings, 'resolve', return_value=self.binding), patch.object(
                v2, 'code', side_effect=v2.ButlerV2Error('recipient_evidence_missing', status_code=409)):
            with self.assertRaises(client.EmailButlerClientError) as caught:
                self.fetch(local_probe=local, api_base=BASE)
        self.assertEqual(caught.exception.error_code, 'recipient_evidence_missing')
        local.assert_not_called()

    def test_missing_original_lease_blocks_before_code_without_claiming_replacement(self):
        with patch.object(lease_bindings, 'resolve', side_effect=v2.ButlerV2Error('lease_restore_required')), patch.object(
                v2, 'code') as code, patch.object(v2, 'create_lease') as create:
            with self.assertRaises(client.EmailButlerClientError) as caught:
                client.fetch_inbound_otp(CHILD, after_ts=100, max_wait=1, require_recipient_evidence=True)
        self.assertEqual(caught.exception.error_code, 'lease_restore_required')
        code.assert_not_called()
        create.assert_not_called()

    def test_complete_historical_displayed_child_with_hme_parent_remains_valid_evidence(self):
        payload = {**receipt(), 'recipient_evidence': {
            'original_recipients': [], 'displayed_recipients': [CHILD], 'hme_recipients': [PARENT],
            'forwarding_destinations': [MAILBOX], 'received_for': [], 'conflicting_original_families': [],
            'sources': [],
        }}
        client._validate_recipient_receipt(payload, CHILD, False, MAILBOX)


class ButlerForwardRoutingTests(unittest.TestCase):
    def test_child_and_strict_parent_use_butler_without_opening_imap(self):
        for target, strict in [(CHILD, False), (PARENT, True)]:
            with self.subTest(target=target), forward.use_inbox_profile({
                    "connector": "forward_butler", "api_base": BASE, "api_key": "pinned-key",
                    "mailbox_email": MAILBOX, "strict_family": strict}), patch.object(
                    forward, "_connect", side_effect=AssertionError("严格路径不能连接 IMAP")), patch(
                    "core.email.email_butler.client.fetch_inbound_otp", return_value="654321") as fetch:
                self.assertEqual(forward.fetch_latest_otp(target, after_ts=100), "654321")
                self.assertTrue(fetch.call_args.kwargs["require_recipient_evidence"])
                self.assertEqual(fetch.call_args.kwargs["strict_family"], strict)
                self.assertEqual(fetch.call_args.kwargs["mailbox_email"], MAILBOX)
                self.assertEqual(fetch.call_args.kwargs["api_key"], "pinned-key")
                self.assertNotIn("local_probe", fetch.call_args.kwargs)

    def test_butler_alias_relay_remains_usable(self):
        rows, stats = hme._prepare_imap_aliases(
            [{"email": PARENT, "forwardToEmail": "relay@gmail.com", "active": True}],
            inbox_mode="forward_butler", forward_imap_email=MAILBOX)
        self.assertTrue(rows[0]["active"])
        self.assertEqual(stats["forward_incompatible"], 0)

    def test_pinned_butler_profile_is_usable_without_global_imap_credentials(self):
        profile = {"state": "active", "connector": "forward_butler", "credential_ref": "TEST_BUTLER_KEY",
            "inbox_locator": {"api_base": BASE, "mailbox_email": MAILBOX}, "id": 1, "inbox_key": "butler:fixed", "revision": 1}
        with patch.dict(os.environ, {"TEST_BUTLER_KEY": "old-key"}):
            self.assertTrue(derivation._inventory_profile_usable(profile, "icloud_hide"))
            credentials = derivation._profile_credentials(profile)
        self.assertEqual(credentials["api_key"], "old-key")
        self.assertNotIn("password", credentials)


if __name__ == "__main__":
    unittest.main()
