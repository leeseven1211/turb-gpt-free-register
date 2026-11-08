"""Historical HME scans and OTPs retain full recipient and challenge evidence."""
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from core.accounts.deactivation import mail_scan as scans
from core.email.email_butler import client as butler, v2, lease_bindings
from core.email import forward_imap as imap


PARENT = "alias@icloud.com"
CHILD = "alias+child@icloud.com"
MAILBOX = "final@example.test"


def receipt(address, *, detected=True):
    return {
        "code": 200, "ok": True, "checked_at": "2026-10-27T00:00:00Z",
        "recipient_mode": "forwarded_exact_v1",
        "recipient_match": {"email": address, "mailbox_email": MAILBOX, "strict_family": True},
        "recipient_evidence": {"original_recipients": [address]},
        "message_id": "pg:123", "signal": {"detected": detected, "message_id": "pg:123"},
    }


class StrictButlerReceiptTests(unittest.TestCase):
    def inbound(self, payload, *, after_ts=100, address=CHILD):
        binding = {'lease_id': 'lse_original', 'client_id': 'client-fixture',
                   'email': address, 'service': 'openai', 'api_base': 'https://pinned.test/v2'}
        result = {'lease_id': 'lse_original', 'service': 'openai', 'status': 'matched',
                  'verification_code': '123456', 'code_id': 'code_original',
                  'received_at': '1970-01-01T00:01:41Z', **payload}
        with patch.object(lease_bindings, 'resolve', return_value=binding), patch.object(
            v2, 'code', return_value=result
        ) as request, patch.dict(butler._CONTEXT_CACHE, {}, clear=True):
            value = butler.fetch_inbound_otp(address, after_ts=after_ts, max_wait=1,
                require_recipient_evidence=True, strict_family=True, api_base='https://pinned.test/v2', api_key='fixture')
        return value, request.call_args.kwargs

    def test_strict_explicit_challenge_does_not_include_previous_30_seconds(self):
        value, request = self.inbound({})
        self.assertEqual(value, '123456')
        self.assertEqual(request['since'], datetime.fromtimestamp(100, timezone.utc).isoformat().replace('+00:00', 'Z'))

    def test_strict_validated_candidate_keeps_stable_message_and_recipient_evidence(self):
        with patch('core.auth.email_guard.observe_candidate') as observe:
            self.inbound({'body': '不会写入候选账本'})
        observe.assert_called_once()
        self.assertTrue(observe.call_args.args[0].endswith(':code_original'))
        self.assertEqual(observe.call_args.kwargs['evidence']['recipient'], CHILD)
        self.assertEqual(observe.call_args.kwargs['evidence']['contract'], 'butler.v2.lease')
        self.assertNotIn('body', str(observe.call_args))
        self.assertNotIn('123456', str(observe.call_args))

    def test_invalid_receipt_never_records_candidate(self):
        for changes in ({'lease_id': 'lse_other'}, {'service': 'grok'},
                        {'verification_code': 'ABC123'}, {'received_at': '1970-01-01T00:01:39Z'}):
            with self.subTest(changes=changes), patch('core.auth.email_guard.observe_candidate') as observe:
                with self.assertRaises(butler.EmailButlerClientError):
                    self.inbound(changes)
                observe.assert_not_called()

    def test_parent_challenge_keeps_same_explicit_time_boundary(self):
        _, request = self.inbound({}, address=PARENT)
        self.assertEqual(request['since'], datetime.fromtimestamp(100, timezone.utc).isoformat().replace('+00:00', 'Z'))

    def test_strict_scan_reports_v2_unsupported_without_reading_another_connection(self):
        with patch.object(butler, "_request", return_value=receipt(CHILD)) as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'signal_scan_unsupported'):
                butler.scan_openai_deactivation(
                    CHILD, api_base="https://pinned.test/v1", api_key="pinned",
                    mailbox_email=MAILBOX, strict_family=True,
                )
        request.assert_not_called()

    def test_unsupported_scan_never_returns_negative_detection(self):
        with patch.object(butler, "_request", return_value=receipt(PARENT, detected=False)) as request:
            with self.assertRaisesRegex(butler.EmailButlerClientError, 'signal_scan_unsupported'):
                butler.scan_openai_deactivation(CHILD, mailbox_email=MAILBOX, strict_family=True)
        request.assert_not_called()

    def test_bulk_scan_does_not_turn_failed_item_into_negative_success(self):
        failed = {"ok": False, "error_code": "signal_history_incomplete", "error": "history incomplete"}
        with patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: failed}}) as request:
            result = butler.scan_openai_deactivation_bulk(
                [PARENT, CHILD], api_base="https://pinned.test/v1", api_key="pinned",
                mailbox_email=MAILBOX, strict_family=True,
            )
        self.assertFalse(result[PARENT]["ok"])
        self.assertNotIn('detected', result[PARENT])
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[CHILD]["error_code"], "signal_scan_unsupported")
        request.assert_not_called()

    def test_bulk_scan_marks_all_5001_targets_unsupported_without_remote_calls(self):
        targets = [f"alias{i}@icloud.com" for i in range(5001)]

        def respond(method, path, **kwargs):
            return {"code": 200, "results": {target: receipt(target, detected=False) for target in kwargs["json"]["emails"]}}

        with patch.object(butler, "_request", side_effect=respond) as request:
            result = butler.scan_openai_deactivation_bulk(targets, mailbox_email=MAILBOX)
        self.assertEqual(len(result), 5001)
        self.assertTrue(all(item.get('error_code') == 'signal_scan_unsupported' for item in result.values()))
        self.assertTrue(all('detected' not in item for item in result.values()))
        request.assert_not_called()

    def test_retired_bulk_receipts_cannot_override_v2_unsupported(self):
        with patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: receipt(PARENT)}}) as request:
            result = butler.scan_openai_deactivation_bulk([PARENT, CHILD], mailbox_email=MAILBOX)
        self.assertFalse(result[PARENT]["ok"])
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[CHILD]["error_code"], "signal_scan_unsupported")
        request.assert_not_called()

    def test_bulk_malformed_item_fails_only_that_full_recipient(self):
        for invalid in ("broken", {"code": "invalid", "signal": {"detected": False}}):
            with self.subTest(invalid=invalid), patch.object(butler, "_request", return_value={
                "code": 200, "results": {PARENT: receipt(PARENT), CHILD: invalid}
            }) as request:
                result = butler.scan_openai_deactivation_bulk([PARENT, CHILD], mailbox_email=MAILBOX)
                self.assertFalse(result[PARENT]["ok"])
                self.assertFalse(result[CHILD]["ok"])
                self.assertEqual(result[PARENT]['error_code'], 'signal_scan_unsupported')
                self.assertEqual(result[CHILD]['error_code'], 'signal_scan_unsupported')
                request.assert_not_called()


class HistoricalScanRouteTests(unittest.TestCase):
    def test_pinned_parent_butler_survives_global_imap_with_bridge_disabled(self):
        profile = {"connector": "forward_butler", "api_base": "https://pinned.test/v1", "api_key": "pinned", "mailbox_email": MAILBOX}
        with patch("core.email.derivation.inbox_profiles_for_addresses", return_value={}), patch(
            "core.email.email_butler.bridge.inbox_profiles_for_addresses", return_value={PARENT: profile}
        ), patch("core.email.email_butler.bridge.enabled", return_value=False), patch.object(
            imap._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_imap"
        ), patch.object(imap, "_connect", side_effect=AssertionError("固定 Butler 母地址不能改扫全局 IMAP")), patch.object(
            butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT)}}
        ) as request:
            result = imap.scan_openai_deactivation_bulk([PARENT])[PARENT]
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_code'], 'signal_scan_unsupported')
        request.assert_not_called()

    def test_unavailable_parent_profile_fails_only_that_target_without_global_fallback(self):
        from core.email import derivation as email_derivation
        from core.email.email_butler import bridge as email_butler_bridge
        from core.storage import records as record_store

        profile = {"id": 1, "state": "active", "connector": "forward_butler", "credential_ref": "MISSING_TEST_KEY"}
        good = {"connector": "forward_butler", "api_base": "https://pinned.test/v1", "api_key": "pinned", "mailbox_email": MAILBOX}
        with patch.object(record_store, "list_rows", side_effect=lambda table, **kwargs:
                [{"email": PARENT, "derivation_policy": {"inbox_profile_id": 1}}]
                if table == record_store.ICLOUD_HIDE_POOL else []), patch.object(
            email_derivation.store, "get_inbox_profile", return_value=profile
        ), patch.object(email_derivation, "_profile_credentials", side_effect=RuntimeError("原配置密钥缺失")), patch.object(
            email_derivation, "inbox_profiles_for_addresses", return_value={}
        ):
            profiles = email_butler_bridge.inbox_profiles_for_addresses([PARENT])
        with patch.object(email_butler_bridge, "inbox_profiles_for_addresses", return_value={PARENT: profiles[PARENT], CHILD: good}), patch.object(
            imap._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"
        ), patch.object(imap, "_connect", side_effect=AssertionError("错误固定配置不能fallback全局")), patch.object(
            butler, "_request", return_value={"code": 200, "results": {CHILD: receipt(CHILD)}}
        ):
            result = imap.scan_openai_deactivation_bulk([PARENT, CHILD])
        self.assertFalse(result[PARENT]["ok"])
        self.assertEqual(result[PARENT]["error_code"], "email_derivation_profile_unavailable")
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[CHILD]['error_code'], 'signal_scan_unsupported')

    def test_unavailable_child_profile_is_returned_without_losing_other_parent_route(self):
        from core.email import derivation as email_derivation
        from core.email.email_butler import bridge as email_butler_bridge
        from core.storage import records as record_store

        def rows(table, **kwargs):
            if table == record_store.EMAIL_ADDRESS_ALLOCATIONS:
                return [{"address_norm": CHILD, "parent_address": PARENT, "inbox_profile_id": 1}]
            return [{"email": "other@icloud.com", "derivation_policy": {"inbox_profile_id": 2}}]

        def profile(profile_id):
            return {"id": profile_id, "state": "disabled" if profile_id == 1 else "active", "connector": "forward_butler"}

        with patch.object(record_store, "list_rows", side_effect=rows), patch.object(
            email_derivation.store, "get_inbox_profile", side_effect=profile
        ), patch.object(email_derivation, "_profile_credentials", return_value={"connector": "forward_butler", "api_key": "valid"}):
            profiles = email_butler_bridge.inbox_profiles_for_addresses([CHILD, "other@icloud.com"])
        self.assertEqual(profiles[CHILD]["error_code"], "email_derivation_profile_unavailable")
        self.assertEqual(profiles["other@icloud.com"]["api_key"], "valid")

    def test_pinned_and_global_butler_targets_are_unsupported_without_imap_fallback(self):
        profile = {"connector": "forward_butler", "api_base": "https://pinned.test/v1", "api_key": "pinned", "mailbox_email": MAILBOX}
        with patch("core.email.email_butler.bridge.inbox_profiles_for_addresses", return_value={CHILD: profile}), patch.object(
            imap._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"
        ), patch.object(imap._email_cfg, "EMAIL_BUTLER_API_BASE", "https://pinned.test/v1"), patch.object(
            imap._email_cfg, "EMAIL_BUTLER_API_KEY", "pinned"
        ), patch.object(imap._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", MAILBOX), patch.object(
            imap, "_connect", side_effect=AssertionError("Butler scans must not open IMAP")
        ), patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: receipt(CHILD)}}) as request:
            result = imap.scan_openai_deactivation_bulk([PARENT, CHILD])
        self.assertFalse(result[PARENT]["ok"])
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[PARENT]['error_code'], 'signal_scan_unsupported')
        self.assertEqual(result[CHILD]['error_code'], 'signal_scan_unsupported')
        request.assert_not_called()

    def test_single_account_scan_does_not_report_ok_false_as_success(self):
        account = {"id": 7, "email": CHILD, "email_source": "icloud_hide"}
        reporter = Mock()
        with patch.object(scans, "_ReporterAdapter", return_value=reporter), patch.object(
            scans.db, "get_account", return_value=account
        ), patch.object(scans.db, "update_account_deactivation_mail") as update, patch.object(
            scans, "scan_hme_deactivation_bulk", return_value={CHILD: {"ok": False, "error": "signal_history_incomplete"}}
        ):
            scans._scan(7, "manual")
        self.assertEqual(reporter.finish.call_args.kwargs["status"], "failed")
        self.assertFalse(any(call.args[1].get("status") == "success" for call in update.call_args_list))


if __name__ == "__main__":
    unittest.main()
