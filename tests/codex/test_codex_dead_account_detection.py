# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from core.codex import oauth as codex_oauth
from core.auth.protocol.openai_auth import AccountUnusableError, detect_account_unusable_response_body
from core.codex.legacy.browser_use.oauth import _wait_after_email_submit


class CodexDeadAccountDetectionTests(unittest.TestCase):
    def test_detect_account_unusable_response_body_uses_error_code(self):
        self.assertEqual(
            detect_account_unusable_response_body('{"error":{"code":"account_deactivated"}}'),
            "account_deactivated",
        )
        self.assertEqual(
            detect_account_unusable_response_body('{"error":{"code":"account_deleted"}}'),
            "account_deleted",
        )
        self.assertEqual(detect_account_unusable_response_body('Your account has been deactivated.'), "")

    def test_browser_use_email_submit_returns_deactivated_from_response_tracker(self):
        class Body:
            def inner_text(self, timeout=1000):
                return "Your account has been deactivated."

        class Page:
            url = "https://auth.openai.com/email-verification"
            def locator(self, selector):
                return Body()

        tracker = {"code": "account_deactivated"}
        self.assertEqual(_wait_after_email_submit(Page(), timeout=1, dead_tracker=tracker), "deactivated:account_deactivated")
        self.assertNotEqual(_wait_after_email_submit(Page(), timeout=1, dead_tracker={}), "deactivated:account_deactivated")

    def test_structured_unusable_exception_marks_oauth_result_explicitly(self):
        with patch.object(codex_oauth, "BrowserSession"), patch.object(
            codex_oauth,
            "check_cancelled",
            side_effect=AccountUnusableError("账号已废", error_code="account_deactivated"),
        ):
            result = codex_oauth.run_codex_oauth(
                "dead@example.com",
                proxy="",
                force=True,
                driver_override="protocol",
            )

        self.assertEqual(result["status"], "deactivated")
        self.assertTrue(result["email_permanently_unusable"])
        self.assertEqual(result["account_unusable_error_code"], "account_deactivated")


if __name__ == "__main__":
    unittest.main()
