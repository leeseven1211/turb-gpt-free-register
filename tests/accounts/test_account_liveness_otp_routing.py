# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from config import email as email_config
from core.accounts.liveness.protocol import legacy as account_liveness
from core.email import provider as email_provider


class AccountLivenessOtpRoutingTests(unittest.TestCase):
    def test_registered_source_uses_email_service_when_enabled(self):
        with (
            patch.object(email_config, "USE_EMAIL_SERVICE", True),
            patch.object(email_provider, "resolve_email_source", return_value="icloud_hide") as resolve_source,
            patch("core.email.icloud_hide.client.fetch_latest_otp", return_value="123456") as fetch_otp,
            patch("core.email.manual_otp.wait_for_manual_otp") as manual_otp,
            patch.object(account_liveness, "validate_email_otp", return_value={"ok": True}) as validate_otp,
        ):
            result = account_liveness._validate_with_retry(
                object(), "account@example.com", 100.0, max_otp_attempts=1
            )

        self.assertEqual(result, {"ok": True})
        resolve_source.assert_called_once_with("account@example.com")
        fetch_otp.assert_called_once()
        manual_otp.assert_not_called()
        validate_otp.assert_called_once()

    def test_global_manual_mode_stays_manual_without_explicit_source(self):
        with (
            patch.object(email_config, "USE_EMAIL_SERVICE", False),
            patch("core.email.manual_otp.wait_for_manual_otp", return_value="123456") as manual_otp,
            patch("core.email.icloud_hide.client.fetch_latest_otp") as fetch_otp,
            patch.object(account_liveness, "validate_email_otp", return_value={"ok": True}),
        ):
            result = account_liveness._validate_with_retry(
                object(), "account@example.com", 100.0, max_otp_attempts=1
            )

        self.assertEqual(result, {"ok": True})
        manual_otp.assert_called_once()
        fetch_otp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
