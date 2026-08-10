# -*- coding: utf-8 -*-
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from core import forward_imap_client as client


class ForwardIMAPTests(unittest.TestCase):
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
