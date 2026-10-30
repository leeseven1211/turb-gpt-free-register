# -*- coding: utf-8 -*-
"""Butler 严格收件契约及固定连接器的回归测试。"""
import os
import unittest
from unittest.mock import Mock, patch

from core.email.email_butler import client as client
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

    def fetch(self, **kwargs):
        return client.fetch_inbound_otp(CHILD, after_ts=100, max_wait=1,
            require_recipient_evidence=True, mailbox_email=MAILBOX, **kwargs)

    def test_strict_request_and_receipt_use_full_child_and_pinned_endpoint(self):
        calls = []

        def request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else receipt()

        with patch.object(client, "_request", side_effect=request):
            self.assertEqual(self.fetch(api_base=BASE + "/pinned", api_key="pinned-key"), "654321")
        inbound = next(call for call in calls if call[1] == "/inbound/code")
        self.assertEqual(inbound[2]["json"], {
            "email": CHILD, "since": "1970-01-01T00:01:10Z", "timeout_seconds": 1,
            "recipient_mode": "forwarded_exact_v1", "strict_family": False, "mailbox_email": MAILBOX,
        })
        self.assertEqual(inbound[2]["api_base"], BASE + "/pinned")
        self.assertEqual(inbound[2]["api_key"], "pinned-key")

    def test_missing_capability_blocks_before_inbound_request(self):
        with patch.object(client, "_request", return_value={"code": 200, "capabilities": ["inbound.code"]}) as request:
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_contract_unsupported"):
                self.fetch(api_base=BASE + "/old")
        self.assertEqual([call.args[1] for call in request.call_args_list], ["/me"])

    def test_old_service_without_me_endpoint_is_contract_unsupported(self):
        with patch.object(client, "_request", side_effect=client.EmailButlerClientError(
                "Email Butler 请求失败 (/me): HTTP 404; 路由不存在")):
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_contract_unsupported"):
                self.fetch(api_base=BASE + "/without-me")

    def test_capability_cache_isolated_by_endpoint_and_key_identity(self):
        calls = []

        def request(_method, path, **kwargs):
            if path == "/me":
                calls.append((kwargs["api_base"], kwargs["api_key"]))
                supported = kwargs["api_key"] == "capable-key"
                return {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"] if supported else []}
            return receipt()

        with patch.object(client, "_request", side_effect=request):
            for _ in range(2):
                self.assertEqual(self.fetch(api_base=BASE + "/cache", api_key="capable-key"), "654321")
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_contract_unsupported"):
                self.fetch(api_base=BASE + "/cache", api_key="old-key")
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_contract_unsupported"):
                self.fetch(api_base=BASE + "/other", api_key="old-key")
        self.assertEqual(calls, [(BASE + "/cache", "capable-key"), (BASE + "/cache", "old-key"), (BASE + "/other", "old-key")])

    def test_missing_or_incorrect_receipt_never_accepts_code(self):
        cases = [
            ({"code": 200, "verification_code": "654321"}, "recipient_contract_unsupported"),
            ({**receipt(), "recipient_match": {"email": PARENT, "strict_family": False, "mailbox_email": MAILBOX}}, "recipient_mismatch"),
            ({**receipt(), "recipient_match": {"email": CHILD, "strict_family": False, "mailbox_email": "other@example.test"}}, "mailbox_mismatch"),
            ({**receipt(), "recipient_match": {"email": CHILD, "strict_family": True, "mailbox_email": MAILBOX}}, "recipient_mismatch"),
            ({**receipt(), "recipient_evidence": {}}, "recipient_evidence_missing"),
            ({**receipt(), "recipient_evidence": {"original_recipients": [PARENT]}}, "recipient_mismatch"),
            ({**receipt(), "recipient_evidence": {"original_recipients": [CHILD, "alias+other@icloud.com"]}}, "recipient_ambiguous"),
        ]
        for payload, error in cases:
            with self.subTest(error=error, payload=payload), patch.object(client, "_request", side_effect=lambda _m, path, **_kw:
                    {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else payload):
                with self.assertRaisesRegex(client.EmailButlerClientError, error):
                    self.fetch(api_base=BASE + "/receipts")

    def test_strict_parent_requires_original_parent_and_no_local_probe(self):
        local = Mock(return_value="111111")
        payload = receipt(PARENT, strict=True)
        with patch.object(client, "_request", side_effect=lambda _m, path, **_kw:
                {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else payload):
            self.assertEqual(client.fetch_inbound_otp(PARENT, max_wait=1, strict_family=True,
                mailbox_email=MAILBOX, local_probe=local, api_base=BASE + "/parent"), "654321")
        local.assert_not_called()

    def test_strict_parent_with_only_displayed_parent_is_ambiguous(self):
        payload = {**receipt(PARENT, strict=True), "recipient_evidence": {
            "original_recipients": [], "displayed_recipients": [PARENT], "hme_recipients": [PARENT]}}
        with patch.object(client, "_request", side_effect=lambda _m, path, **_kw:
                {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else payload):
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_ambiguous"):
                client.fetch_inbound_otp(PARENT, max_wait=1, strict_family=True,
                    mailbox_email=MAILBOX, api_base=BASE + "/ambiguous-parent")

    def test_strict_timeout_preserves_remote_classification_without_imap_probe(self):
        local = Mock(return_value="111111")
        payload = {"code": 200, "error_code": "recipient_evidence_missing", "message": "邮件缺少完整收件证据"}
        clock = iter([0, 0, 0, 2, 2])
        with patch.object(client.time, "monotonic", side_effect=lambda: next(clock, 2)), patch.object(
                client, "_request", side_effect=lambda _m, path, **_kw:
                {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else payload):
            with self.assertRaisesRegex(client.EmailButlerClientError, "recipient_evidence_missing"):
                self.fetch(local_probe=local, api_base=BASE + "/timeout")
        local.assert_not_called()

    def test_strict_request_requires_final_mailbox(self):
        with patch.object(client, "_request") as request:
            with self.assertRaisesRegex(client.EmailButlerClientError, "mailbox_mismatch"):
                client.fetch_inbound_otp(CHILD, max_wait=1, require_recipient_evidence=True)
        request.assert_not_called()

    def test_complete_displayed_child_with_hme_parent_is_valid_real_evidence(self):
        payload = {**receipt(), "recipient_evidence": {
            "original_recipients": [], "displayed_recipients": [CHILD], "hme_recipients": [PARENT],
            "forwarding_destinations": [MAILBOX], "received_for": [], "conflicting_original_families": [],
            "sources": [],
        }}
        with patch.object(client, "_request", side_effect=lambda _m, path, **_kw:
                {"code": 200, "capabilities": ["inbound.recipient_evidence.v1"]} if path == "/me" else payload):
            self.assertEqual(self.fetch(api_base=BASE + "/displayed-child"), "654321")


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
