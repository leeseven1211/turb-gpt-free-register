"""Historical HME scans and OTPs retain full recipient and challenge evidence."""
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from core import deactivation_mail_service as scans
from core import email_butler_client as butler, forward_imap_client as imap


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
    def inbound(self, payload, *, after_ts=100):
        with patch.object(butler, "_require_recipient_capability"), patch.object(
            butler, "_request", return_value=payload
        ) as request:
            value = butler.fetch_inbound_otp(
                CHILD, after_ts=after_ts, max_wait=1, require_recipient_evidence=True,
                strict_family=True, mailbox_email=MAILBOX, api_base="https://pinned.test/v1", api_key="pinned",
            )
        return value, request.call_args.kwargs

    def test_strict_explicit_challenge_does_not_include_previous_30_seconds(self):
        payload = {**receipt(CHILD), "verification_code": "123456"}
        value, request = self.inbound(payload)
        self.assertEqual(value, "123456")
        self.assertEqual(request["json"]["since"], datetime.fromtimestamp(100, timezone.utc).isoformat().replace("+00:00", "Z"))

    def test_strict_validated_candidate_keeps_stable_message_and_recipient_evidence(self):
        payload = {**receipt(CHILD), "verification_code": "123456", "body": "must not reach ledger"}
        with patch("core.email_auth_guard.observe_candidate") as observe:
            self.inbound(payload)
        observe.assert_called_once()
        self.assertIn("pg:123", observe.call_args.args[0])
        self.assertEqual(observe.call_args.kwargs["evidence"], payload["recipient_evidence"])
        self.assertNotIn("body", observe.call_args.kwargs["cursor"])

    def test_invalid_receipt_never_records_candidate(self):
        payload = {**receipt(PARENT), "verification_code": "123456"}
        with patch("core.email_auth_guard.observe_candidate") as observe:
            with self.assertRaisesRegex(butler.EmailButlerClientError, "recipient_mismatch"):
                self.inbound(payload)
        observe.assert_not_called()

    def test_non_strict_challenge_retains_compatibility_window(self):
        with patch.object(butler, "_request", return_value={"code": 200, "verification_code": "123456"}) as request:
            butler.fetch_inbound_otp(PARENT, after_ts=100, max_wait=1)
        self.assertEqual(request.call_args.kwargs["json"]["since"], datetime.fromtimestamp(70, timezone.utc).isoformat().replace("+00:00", "Z"))

    def test_strict_scan_preserves_pinned_connection_and_full_address_proof(self):
        with patch.object(butler, "_request", return_value=receipt(CHILD)) as request:
            result = butler.scan_openai_deactivation(
                CHILD, api_base="https://pinned.test/v1", api_key="pinned",
                mailbox_email=MAILBOX, strict_family=True,
            )
        self.assertTrue(result["detected"])
        self.assertEqual(request.call_args.kwargs["api_base"], "https://pinned.test/v1")
        self.assertEqual(request.call_args.kwargs["api_key"], "pinned")
        self.assertEqual(request.call_args.kwargs["json"]["email"], CHILD)
        self.assertTrue(request.call_args.kwargs["json"]["strict_family"])

    def test_strict_negative_scan_requires_matching_recipient_receipt(self):
        with patch.object(butler, "_request", return_value=receipt(PARENT, detected=False)):
            with self.assertRaisesRegex(butler.EmailButlerClientError, "recipient_mismatch"):
                butler.scan_openai_deactivation(CHILD, mailbox_email=MAILBOX, strict_family=True)

    def test_bulk_scan_does_not_turn_failed_item_into_negative_success(self):
        failed = {"ok": False, "error_code": "signal_history_incomplete", "error": "history incomplete"}
        with patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: failed}}) as request:
            result = butler.scan_openai_deactivation_bulk(
                [PARENT, CHILD], api_base="https://pinned.test/v1", api_key="pinned",
                mailbox_email=MAILBOX, strict_family=True,
            )
        self.assertTrue(result[PARENT]["detected"])
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[CHILD]["error_code"], "signal_history_incomplete")
        self.assertEqual(set(request.call_args.kwargs["json"]["emails"]), {PARENT, CHILD})
        request.assert_called_once()

    def test_bulk_scan_shares_one_mailbox_scan_for_5000_targets(self):
        targets = [f"alias{i}@icloud.com" for i in range(5001)]

        def respond(method, path, **kwargs):
            return {"code": 200, "results": {target: receipt(target, detected=False) for target in kwargs["json"]["emails"]}}

        with patch.object(butler, "_request", side_effect=respond) as request:
            result = butler.scan_openai_deactivation_bulk(targets, mailbox_email=MAILBOX)
        self.assertEqual(len(result), 5001)
        self.assertEqual([len(call.kwargs["json"]["emails"]) for call in request.call_args_list], [5000, 1])
        self.assertGreaterEqual(request.call_args.kwargs["timeout"], 55)

    def test_bulk_mismatched_receipt_fails_only_that_full_recipient(self):
        with patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: receipt(PARENT)}}):
            result = butler.scan_openai_deactivation_bulk([PARENT, CHILD], mailbox_email=MAILBOX)
        self.assertTrue(result[PARENT]["ok"])
        self.assertFalse(result[CHILD]["ok"])
        self.assertEqual(result[CHILD]["error_code"], "recipient_mismatch")

    def test_bulk_malformed_item_fails_only_that_full_recipient(self):
        for invalid in ("broken", {"code": "invalid", "signal": {"detected": False}}):
            with self.subTest(invalid=invalid), patch.object(butler, "_request", return_value={
                "code": 200, "results": {PARENT: receipt(PARENT), CHILD: invalid}
            }):
                result = butler.scan_openai_deactivation_bulk([PARENT, CHILD], mailbox_email=MAILBOX)
                self.assertTrue(result[PARENT]["ok"])
                self.assertFalse(result[CHILD]["ok"])


class HistoricalScanRouteTests(unittest.TestCase):
    def test_pinned_and_global_butler_targets_share_one_remote_batch_without_imap(self):
        profile = {"connector": "forward_butler", "api_base": "https://pinned.test/v1", "api_key": "pinned", "mailbox_email": MAILBOX}
        with patch("core.email_butler_bridge.inbox_profiles_for_addresses", return_value={CHILD: profile}), patch.object(
            imap._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"
        ), patch.object(imap._email_cfg, "EMAIL_BUTLER_API_BASE", "https://pinned.test/v1"), patch.object(
            imap._email_cfg, "EMAIL_BUTLER_API_KEY", "pinned"
        ), patch.object(imap._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", MAILBOX), patch.object(
            imap, "_connect", side_effect=AssertionError("Butler scans must not open IMAP")
        ), patch.object(butler, "_request", return_value={"code": 200, "results": {PARENT: receipt(PARENT), CHILD: receipt(CHILD)}}) as request:
            result = imap.scan_openai_deactivation_bulk([PARENT, CHILD])
        self.assertTrue(result[PARENT]["detected"])
        self.assertTrue(result[CHILD]["detected"])
        request.assert_called_once()
        self.assertEqual(set(request.call_args.kwargs["json"]["emails"]), {PARENT, CHILD})

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
