# -*- coding: utf-8 -*-
"""派生收件的 IMAP 召回、路由隔离与不同协议候选过滤。"""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from core import forward_imap_client as forward
from core import outlook_client as outlook
from core import qqmail_client as qq
from core.email_recipients import candidate_match
from tests.test_email_recipients import PARENT, CHILD_A, CHILD_B, hme_message


def raw_message(uid, target, *, code="123456", received="20-Oct-2026 01:00:00 +0000"):
    msg = hme_message(target)
    msg["From"] = "OpenAI <noreply@openai.com>"
    msg["Subject"] = f"Your ChatGPT code is {code}"
    msg["Message-ID"] = f"<{uid}@example.test>"
    msg.set_content(f"Your code is {code}")
    return (f'7 (UID {uid} INTERNALDATE "{received}" BODY[] {{1}}'.encode(), msg.as_bytes())


class Mail:
    def __init__(self, rows):
        self.rows = rows
        self.searches = []
        self.fetches = []

    def noop(self):
        return "OK", []

    def response(self, name):
        return name, [b"120"]

    def uid(self, command, *args):
        if command == "search":
            self.searches.append(args[-1])
            return "OK", [b" ".join(str(uid).encode() for uid in self.rows)]
        self.fetches.append(args)
        return "OK", [self.rows[int(uid)] for uid in args[0].split(b",")]


class DerivedForwardIMAPTests(unittest.TestCase):
    def test_one_parent_two_children_are_indexed_once_and_do_not_mix(self):
        mail = Mail({1: raw_message(1, PARENT), 2: raw_message(2, CHILD_A), 3: raw_message(3, CHILD_B)})
        indexed = forward._messages_for_recipients(mail, {PARENT, CHILD_A, CHILD_B}, 0)
        self.assertEqual({target: [row[2] for row in rows] for target, rows in indexed.items()}, {
            PARENT: ["1"], CHILD_A: ["2"], CHILD_B: ["3"],
        })
        self.assertEqual(len(mail.fetches), 1)
        self.assertEqual(len(mail.searches), 7)
        self.assertTrue(any("HEADER Received" in query for query in mail.searches))
        self.assertTrue(all('SINCE "01-Jan-1970"' in query for query in mail.searches))

    def test_latest_otp_skips_sibling_and_old_child_and_observes_uid(self):
        mail = Mail({
            1: raw_message(1, CHILD_A, code="111111", received="20-Oct-2026 00:59:40 +0000"),
            2: raw_message(2, CHILD_A, code="222222"),
            3: raw_message(3, CHILD_B, code="333333"),
        })
        after = datetime(2026, 10, 20, 0, 59, 55, tzinfo=timezone.utc).timestamp()
        with patch("core.email_auth_guard.observe_candidate") as observe:
            result = forward._latest_forwarded_otp(mail, CHILD_A, after)
        self.assertEqual(result, "222222")
        self.assertEqual(observe.call_count, 1)
        self.assertTrue(observe.call_args.args[0].endswith(":120:2"))
        cursor = observe.call_args.kwargs["cursor"]
        self.assertEqual(cursor["uid"], "2")
        self.assertEqual(cursor["uidvalidity"], "120")
        self.assertNotIn("code", str(observe.call_args))
        self.assertNotIn("222222", str(observe.call_args))

    def test_received_search_uses_existing_limit(self):
        mail = Mail({uid: raw_message(uid, CHILD_A) for uid in range(1, 8)})
        rows = forward._messages_for_recipient(mail, CHILD_A, 0, limit=2)
        self.assertEqual([row[2] for row in rows], ["7", "6"])
        self.assertEqual(mail.fetches[0][0], b"7,6")

    def test_profile_is_nested_restored_and_does_not_mutate_global_configuration(self):
        with patch.object(forward._email_cfg, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "global-password"), patch.object(forward._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "global@example.test"):
            original = forward._settings()
            with forward.use_inbox_profile({"server": "imap.one.test", "port": 1993, "email": "one@example.test", "password": "abcd efgh"}):
                self.assertEqual(forward._settings(), ("imap.one.test", 1993, "one@example.test", "abcdefgh"))
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    with forward.use_inbox_profile({"email": "two@example.test", "password": "two-password"}):
                        self.assertEqual(forward._settings()[2], "two@example.test")
                        raise RuntimeError("stop")
                self.assertEqual(forward._settings()[2], "one@example.test")
            self.assertEqual(forward._settings(), original)

    def test_profile_context_is_separate_for_concurrent_threads(self):
        barrier = threading.Barrier(2)

        def read(identity):
            with forward.use_inbox_profile({"email": identity, "password": "secret"}):
                barrier.wait(timeout=3)
                return forward._settings()[2]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(read, identity) for identity in ("one@example.test", "two@example.test")]
            self.assertEqual([future.result() for future in futures], ["one@example.test", "two@example.test"])

    def test_incomplete_profile_never_borrows_current_global_password(self):
        with forward.use_inbox_profile({"email": "old@example.test", "credential_ref": "ENV_OLD_PASSWORD"}):
            with self.assertRaises(forward.ForwardIMAPError):
                forward._settings()

    def test_butler_child_cannot_silently_switch_to_direct_imap(self):
        with patch.multiple(forward._email_cfg, ICLOUD_HME_INBOX_MODE="forward_butler", ICLOUD_HME_FORWARD_IMAP_EMAIL=""), patch.object(forward, "_fetch_latest_otp_local") as local:
            with self.assertRaisesRegex(forward.ForwardIMAPError, "mailbox_mismatch"):
                forward.fetch_latest_otp(CHILD_A, after_ts=0)
        local.assert_not_called()

    def test_explicit_profile_connector_uses_pinned_imap(self):
        with patch.object(forward._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"), patch.object(forward, "_fetch_latest_otp_local", return_value="123456") as local:
            with forward.use_inbox_profile({"connector": "forward_imap", "email": "old@example.test", "password": "secret"}):
                result = forward.fetch_latest_otp(CHILD_A, after_ts=0)
        self.assertEqual(result, "123456")
        self.assertEqual(local.call_args.args[0], CHILD_A)

    def test_strict_profile_blocks_ambiguous_displayed_parent(self):
        item = qq._msg_to_dict(hme_message(None))
        self.assertTrue(forward._matches_recipient(PARENT, item))
        with forward.use_inbox_profile({"strict_family": True}):
            self.assertFalse(forward._matches_recipient(PARENT, item))


class OutlookDerivedRecipientTests(unittest.TestCase):
    def test_graph_query_and_normalization_preserve_recipient_evidence(self):
        response = Mock(status_code=200, text="")
        response.json.return_value = {"value": [{
            "id": "message-a", "toRecipients": [{"emailAddress": {"address": CHILD_A}}],
            "ccRecipients": [], "internetMessageHeaders": [{"name": "X-Original-To", "value": CHILD_A}],
        }]}
        http = Mock()
        http.get.return_value = response
        item = outlook._fetch_graph_messages(http, "test-token")[0]
        query = http.get.call_args.kwargs["params"]["$select"]
        self.assertTrue(all(field in query for field in ("toRecipients", "ccRecipients", "internetMessageHeaders")))
        self.assertTrue(candidate_match(CHILD_A, item))
        self.assertFalse(candidate_match(PARENT, item))

    def test_rest_normalization_preserves_capitalized_recipients(self):
        response = Mock(status_code=200, text="")
        response.json.return_value = {"value": [{"Id": "message-a", "ToRecipients": [{"EmailAddress": {"Address": CHILD_A}}]}]}
        http = Mock()
        http.get.return_value = response
        item = outlook._fetch_outlook_rest_messages(http, "test-token")[0]
        self.assertTrue(candidate_match(CHILD_A, item))
        self.assertFalse(candidate_match(CHILD_B, item))

    def test_all_protocol_candidates_are_exact_filtered_before_selection(self):
        account = outlook.OutlookAccount(PARENT, "password", "client", "refresh")
        def message(address, second, code):
            return {"id": f"message-{code}", "from": "OpenAI <noreply@openai.com>", "to": address,
                    "subject": f"Your ChatGPT code is {code}", "receivedDateTime": f"2026-10-20T01:00:{second:02d}Z"}
        graph = [message(CHILD_B, 3, "333333"), message("", 2, "444444"), message(CHILD_A, 1, "111111")]
        imap = [message(CHILD_B, 4, "555555"), message(CHILD_A, 0, "222222")]
        with patch.object(outlook, "get_account_context", return_value=account), patch.object(outlook, "_http_session"), patch.object(outlook, "_fetch_via", side_effect=[graph, imap]), patch("core.email_auth_guard.observe_candidate") as observe:
            result = outlook.fetch_latest_otp(CHILD_A, after_ts=0, max_wait=5, settle_seconds=0)
        self.assertEqual(result, "111111")
        self.assertEqual(observe.call_args.args[0], "graph:message-111111")
        self.assertNotIn("111111", str(observe.call_args.kwargs))

    def test_explicit_parent_credentials_can_target_child(self):
        account = outlook.OutlookAccount(PARENT, "password", "client", "refresh")
        with patch.object(outlook, "fetch_latest_otp", return_value="123456") as fetch:
            self.assertEqual(outlook.fetch_otp_with_account(account, target_email=CHILD_A), "123456")
        self.assertEqual(fetch.call_args.args[0], CHILD_A)
        self.assertIs(outlook._CONTEXT_CACHE[CHILD_A], account)

    def test_qq_imap_parser_keeps_original_recipients_for_same_matcher(self):
        item = qq._msg_to_dict(hme_message())
        self.assertTrue(candidate_match(CHILD_A, item))
        self.assertFalse(candidate_match(CHILD_B, item))
        self.assertFalse(candidate_match(PARENT, item))


class ForwardDeactivationProfileRoutingTests(unittest.TestCase):
    def profile(self, identifier, mailbox, *, strict=False):
        return {"id": identifier, "inbox_key": f"inbox-{identifier}", "revision": 1,
                "connector": "forward_imap", "server": "imap.history.test", "port": 993,
                "email": mailbox, "password": "test-password", "strict_family": strict}

    def test_same_profile_mother_and_children_share_connection_with_separate_rules(self):
        def row(uid, original):
            msg = hme_message(original)
            msg["From"] = "OpenAI <noreply@openai.com>"
            msg["Subject"] = "OpenAI account deactivated"
            msg.set_content("Your OpenAI account has been deactivated.")
            return (f'7 (UID {uid} BODY[] {{1}}'.encode(), msg.as_bytes())

        mail = Mail({1: row(1, None), 2: row(2, PARENT), 3: row(3, CHILD_A), 4: row(4, CHILD_B)})
        mailbox = "historical@example.test"
        profiles = {PARENT: self.profile(1, mailbox, strict=True), CHILD_A: self.profile(1, mailbox), CHILD_B: self.profile(1, mailbox)}
        with patch("core.email_derivation.inbox_profiles_for_addresses", return_value=profiles) as lookup, patch.object(
            forward, "_connect", return_value=mail
        ) as connect:
            results = forward.scan_openai_deactivation_bulk([PARENT, CHILD_A, CHILD_B, CHILD_A])
        self.assertEqual(connect.call_count, 1)
        self.assertEqual(lookup.call_count, 1)
        self.assertEqual(lookup.call_args.args[0], sorted([PARENT, CHILD_A, CHILD_B]))
        self.assertEqual({target: result["message_id"] for target, result in results.items()}, {PARENT: "2", CHILD_A: "3", CHILD_B: "4"})
        self.assertEqual(len(mail.fetches), 1)
        self.assertEqual(len(mail.searches), 7)

    def test_distinct_profiles_and_legacy_group_read_their_own_inboxes(self):
        seen = []
        other = "another+tag123@icloud.com"
        legacy = "legacy@icloud.com"
        profiles = {CHILD_A: self.profile(1, "first@example.test"), CHILD_B: self.profile(1, "first@example.test"), other: self.profile(2, "second@example.test")}

        def connect():
            seen.append(forward._settings()[2])
            return Mock()

        def messages(_mail, targets, _since):
            return {target: [] for target in targets}

        with patch("core.email_derivation.inbox_profiles_for_addresses", return_value=profiles) as lookup, patch.multiple(
            forward._email_cfg, ICLOUD_HME_FORWARD_IMAP_SERVER="imap.current.test", ICLOUD_HME_FORWARD_IMAP_PORT=993,
            ICLOUD_HME_FORWARD_IMAP_EMAIL="global@example.test", ICLOUD_HME_FORWARD_IMAP_PASSWORD="global-password",
        ), patch.object(forward, "_connect", side_effect=connect), patch.object(forward, "_messages_for_recipients", side_effect=messages):
            results = forward.scan_openai_deactivation_bulk([CHILD_A, CHILD_B, other, legacy])
        self.assertCountEqual(seen, ["first@example.test", "second@example.test", "global@example.test"])
        self.assertEqual(set(results), {CHILD_A, CHILD_B, other, legacy})
        self.assertEqual(lookup.call_count, 1)

    def test_missing_historical_profile_never_falls_back_to_global(self):
        with patch("core.email_derivation.inbox_profiles_for_addresses", side_effect=RuntimeError("原收件配置缺失")), patch.object(forward, "_connect") as connect:
            with self.assertRaisesRegex(RuntimeError, "原收件配置缺失"):
                forward.scan_openai_deactivation_bulk([CHILD_A])
        connect.assert_not_called()

    def test_unsupported_connector_never_falls_back_to_global(self):
        with patch("core.email_derivation.inbox_profiles_for_addresses", return_value={CHILD_A: {"connector": "outlook"}}), patch.object(forward, "_connect") as connect:
            with self.assertRaisesRegex(forward.ForwardIMAPError, "不能改读"):
                forward.scan_openai_deactivation_bulk([CHILD_A])
        connect.assert_not_called()

    def test_single_scan_uses_same_bulk_profile_resolution(self):
        with patch.object(forward, "scan_openai_deactivation_bulk", return_value={CHILD_A: {"detected": False}}) as bulk:
            self.assertEqual(forward.scan_openai_deactivation(CHILD_A.upper(), lookback_days=30), {"detected": False})
        bulk.assert_called_once_with([CHILD_A], lookback_days=30)

    def test_empty_scan_does_not_query_profiles_or_connect(self):
        with patch("core.email_derivation.inbox_profiles_for_addresses") as lookup, patch.object(forward, "_connect") as connect:
            self.assertEqual(forward.scan_openai_deactivation_bulk(["", " "]), {})
        lookup.assert_not_called()
        connect.assert_not_called()


class ForwardProviderSPFRecallTests(unittest.TestCase):
    def test_encoded_target_recall_fetches_once_and_applies_provider_exact_match(self):
        msg = hme_message(None)
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom=bounces+1234567-a1b2-{CHILD_A.replace('@', '=')}@em7877.tm.openai.com"
        msg["Return-Path"] = "owner@gmail.com"
        msg["Return-Path"] = f"bounces+1234567-a1b2-{CHILD_A.replace('@', '=')}-forwarded@icloud.com"
        msg["From"] = "OpenAI <noreply@openai.com>"
        msg["Subject"] = "Your ChatGPT code is 123456"
        msg.set_content("Your code is 123456")
        # 原始认证头保留 addr-spec；默认生成器会把长属性改写为 RFC 2047 编码词。
        raw = (b"7 (UID 42 BODY[] {1}", msg.as_bytes(policy=msg.policy.clone(max_line_length=0)))

        class ProviderMail(Mail):
            def uid(self, command, *args):
                if command == "search":
                    self.searches.append(args[-1])
                    encoded = CHILD_A.replace("@", "=")
                    hit = f'HEADER Return-Path "{encoded}"' in args[-1] or f'HEADER Authentication-Results "{encoded}"' in args[-1]
                    return "OK", [b"42" if hit else b""]
                return super().uid(command, *args)

        mail = ProviderMail({42: raw})
        self.assertEqual(forward._latest_forwarded_otp(mail, CHILD_A, 0), "123456")
        self.assertEqual(len(mail.searches), 7)
        self.assertEqual(len(mail.fetches), 1)
        for query in mail.searches[-2:]:
            self.assertIn(CHILD_A.replace("@", "="), query)
            self.assertIn('SINCE "', query)
            self.assertNotIn(CHILD_A, query)

    def test_server_substring_recall_never_assigns_similar_sibling(self):
        msg = hme_message(None)
        sibling = CHILD_A.replace("+a1b2c3", "+a1b2c3x")
        msg["Authentication-Results"] = f"spf.icloud.com; spf=pass smtp.mailfrom=bounces+1234567-a1b2-{sibling.replace('@', '=')}@em7877.tm.openai.com"
        msg["From"] = "OpenAI <noreply@openai.com>"
        msg["Subject"] = "Your code is 123456"
        msg.set_content("Your code is 123456")
        mail = Mail({42: (b"7 (UID 42 BODY[] {1}", msg.as_bytes(policy=msg.policy.clone(max_line_length=0)))})
        self.assertIsNone(forward._latest_forwarded_otp(mail, CHILD_A, 0))
