# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import patch

from core import forward_imap_client as client


class ForwardIMAPTests(unittest.TestCase):
    def test_messages_use_imap_internaldate_as_received_time(self):
        msg = EmailMessage()
        msg["From"] = "OpenAI <noreply@openai.com>"
        msg["To"] = "alias@icloud.com"
        msg["Date"] = "Fri, 28 Aug 2026 03:10:00 +0000"
        msg["Subject"] = "Your ChatGPT code is 123456"
        msg.set_content("Your code is 123456")

        class Mail:
            def search(self, *_args):
                return "OK", [b"42"]

            def fetch(self, *_args):
                return "OK", [(b'42 (INTERNALDATE "28-Aug-2026 03:22:57 +0000" RFC822 {1}', msg.as_bytes())]

        rows = client._messages_for_recipient(Mail(), "alias@icloud.com", 0)

        self.assertEqual(len(rows), 1)
        item = rows[0][0]
        self.assertEqual(item["date"], "2026-08-28T03:10:00Z")
        self.assertEqual(item["receivedDateTime"], "2026-08-28T03:22:57Z")
        self.assertEqual(
            client._message_timestamp(item),
            datetime(2026, 8, 28, 3, 22, 57, tzinfo=timezone.utc).timestamp(),
        )

    def test_recipient_headers_include_hme_forwarding_headers(self):
        msg = EmailMessage()
        msg["To"] = "owner@gmail.com"
        msg["X-Original-To"] = "alias@icloud.com"
        self.assertIn("alias@icloud.com", client._recipient_headers(msg))

    def test_settings_strip_spaces_from_google_app_password(self):
        with (
            patch.object(client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_SERVER", "imap.gmail.com"),
            patch.object(client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_PORT", 993),
            patch.object(client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "owner@gmail.com"),
            patch.object(client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "abcd efgh ijkl mnop"),
        ):
            self.assertEqual(client._settings(), ("imap.gmail.com", 993, "owner@gmail.com", "abcdefghijklmnop"))

    def test_settings_require_application_password(self):
        with patch.object(client._email_cfg, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", ""):
            with self.assertRaises(client.ForwardIMAPError):
                client._settings()

    @patch("core.email_butler_client.test_connection")
    def test_connection_uses_email_butler_pg_cache(self, test_butler):
        test_butler.return_value = {
            "consumer": "turb",
            "capabilities": ["inbound.code"],
        }
        result = client.test_connection()
        self.assertEqual(result["method"], "email_butler_pg")
        self.assertEqual(result["status"], "ok")

    @patch("core.email_butler_client.fetch_inbound_otp", return_value="123456")
    def test_fetch_latest_otp_delegates_to_pg_cache_when_imap_unavailable(self, fetch):
        with (
            patch.object(client._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"),
            patch.object(client, "_connect", side_effect=client.ForwardIMAPError("offline")),
        ):
            result = client.fetch_latest_otp(
                "alias@icloud.com",
                after_ts=123.0,
                max_wait=10,
                poll_interval=2,
                settle_seconds=0,
            )
        self.assertEqual(result, "123456")
        fetch.assert_called_once_with(
            "alias@icloud.com",
            after_ts=123.0,
            max_wait=10,
            poll_interval=2,
            settle_seconds=0,
            local_probe=None,
        )

    @patch("core.email_butler_client.fetch_inbound_otp")
    def test_fetch_latest_otp_passes_direct_imap_probe(self, fetch):
        class Mail:
            def noop(self):
                return "OK", []

            def logout(self):
                return None

        message = {
            "from": "ChatGPT <noreply@openai.com>",
            "subject": "Your ChatGPT code is 654321",
            "date": "2026-08-17T04:41:25Z",
        }

        def use_probe(_email, **kwargs):
            return kwargs["local_probe"]()

        fetch.side_effect = use_probe
        with (
            patch.object(client._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_butler"),
            patch.object(client, "_connect", return_value=Mail()),
            patch.object(
                client,
                "_messages_for_recipient",
                return_value=[(message, "alias@icloud.com", "1479")],
            ),
        ):
            result = client.fetch_latest_otp(
                "alias@icloud.com",
                after_ts=0,
                max_wait=10,
            )

        self.assertEqual(result, "654321")
        self.assertIsNotNone(fetch.call_args.kwargs["local_probe"])

    def test_forward_imap_mode_reads_local_mailbox_without_butler(self):
        class Mail:
            def logout(self):
                return None

        with (
            patch.object(client._email_cfg, "ICLOUD_HME_INBOX_MODE", "forward_imap"),
            patch.object(client, "_connect", return_value=Mail()),
            patch.object(client, "_latest_forwarded_otp", return_value="246810"),
            patch("core.email_butler_client.fetch_inbound_otp") as fetch,
        ):
            result = client.fetch_latest_otp(
                "alias@icloud.com",
                after_ts=123.0,
                max_wait=10,
                poll_interval=2,
            )

        self.assertEqual(result, "246810")
        fetch.assert_not_called()

    def test_deactivation_scan_matches_forwarded_alias_without_returning_body(self):
        class Mail:
            def logout(self):
                return None

        target = "hidden@icloud.com"
        message = {
            "from": "OpenAI <noreply@openai.com>",
            "subject": "OpenAI account deactivated",
            "text": "Your OpenAI account has been deactivated.",
            "date": "2026-08-09T10:00:00Z",
        }
        with (
            patch.object(client, "_connect", return_value=Mail()),
            patch.object(
                client,
                "_messages_for_recipient",
                return_value=[(message, f"owner@gmail.com {target}", "42")],
            ),
        ):
            result = client.scan_openai_deactivation(target)

        self.assertTrue(result["detected"])
        self.assertEqual(result["message_id"], "42")
        self.assertNotIn("text", result)

    def test_deactivation_scan_rejects_message_for_another_alias(self):
        class Mail:
            def logout(self):
                return None

        message = {
            "from": "noreply@openai.com",
            "subject": "OpenAI account deactivated",
            "text": "Your OpenAI account has been deactivated.",
        }
        with (
            patch.object(client, "_connect", return_value=Mail()),
            patch.object(
                client,
                "_messages_for_recipient",
                return_value=[(message, "another@icloud.com", "43")],
            ),
        ):
            result = client.scan_openai_deactivation("hidden@icloud.com")

        self.assertFalse(result["detected"])


if __name__ == "__main__":
    unittest.main()
