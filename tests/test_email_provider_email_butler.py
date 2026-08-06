# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import email as email_config
from core import email_provider


class EmailButlerProviderTests(unittest.TestCase):
    def test_parse_sources_keeps_email_butler(self):
        self.assertEqual(
            email_provider.parse_email_sources("email_butler,cloudflare"),
            ["email_butler", "cloudflare"],
        )

    @patch("core.email_butler_client.pick_account")
    def test_acquire_uses_email_butler(self, pick_account):
        pick_account.return_value.email = "fresh@example.com"
        with patch("core.email_provider.parse_email_sources", return_value=["email_butler"]):
            self.assertEqual(email_provider.acquire_email(), "fresh@example.com")

    @patch("core.email_butler_client.get_account_context", return_value=object())
    def test_resolve_recognizes_email_butler_context(self, get_context):
        self.assertEqual(email_provider.resolve_email_source("fresh@example.com"), "email_butler")

    @patch("core.email_butler_client.fetch_latest_otp", return_value="654321")
    @patch("core.email_provider.resolve_email_source", return_value="email_butler")
    def test_wait_routes_to_email_butler(self, resolve, fetch):
        with patch.object(email_config, "USE_EMAIL_SERVICE", True):
            self.assertEqual(email_provider.wait_for_otp("fresh@example.com", after_ts=123), "654321")
        fetch.assert_called_once_with("fresh@example.com", after_ts=123)

    @patch("core.email_butler_client.release_account")
    @patch("core.email_provider.resolve_email_source", return_value="email_butler")
    def test_release_routes_to_email_butler(self, resolve, release):
        self.assertEqual(email_provider.release_email("fresh@example.com", status="failed"), "email_butler")
        release.assert_called_once_with("fresh@example.com", status="failed", note=None)


if __name__ == "__main__":
    unittest.main()
