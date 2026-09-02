import unittest
from unittest.mock import MagicMock, patch

from core import roxy_codex_oauth
from core.registration import roxy as roxy_registration


class RoxyEmailOtpChallengeTests(unittest.TestCase):
    def _totp_state(self):
        return {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Enter the code from your authenticator app",
            "inputs": [
                {"type": "text", "name": "totp", "autocomplete": "one-time-code"},
            ],
            "errors": [],
        }

    def test_codex_email_otp_wait_identifies_totp_before_accepting_non_email_url(self):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/log-in/password"
        state = self._totp_state()

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_read_email_otp_validate_dead_code", return_value=""),
            patch.object(roxy_codex_oauth, "_is_callback_url", return_value=False),
            patch.object(roxy_codex_oauth, "_has_strict_add_phone_form", return_value=False),
            patch.object(roxy_codex_oauth, "_is_phone_code_page", return_value=False),
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=True),
            patch.object(roxy_codex_oauth.time, "sleep"),
        ):
            result = roxy_codex_oauth._wait_after_email_otp_submit(driver, timeout=1)

        self.assertEqual("totp_required", result)

    def test_registration_email_otp_wait_identifies_totp_before_accepting_non_email_url(self):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/log-in/password"
        state = self._totp_state()

        with (
            patch.object(roxy_registration, "_email_otp_page_state", return_value=state),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
        ):
            result = roxy_registration._wait_after_email_otp_submit(driver, timeout=1)

        self.assertEqual("totp_required", result)

    def test_codex_resolves_totp_after_email_otp_without_resending_email(self):
        driver = MagicMock()
        resolver = MagicMock(side_effect=["email_otp", "advanced"])

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "report_stage"),
            patch.object(roxy_codex_oauth, "human_delay"),
            patch.object(roxy_codex_oauth, "_maybe_accept"),
            patch.object(roxy_codex_oauth, "_select_existing_account_if_present", return_value=False),
            patch.object(roxy_codex_oauth, "_account_login_credentials", return_value=("", "totp-secret")),
            patch.object(roxy_codex_oauth, "_type_email_address"),
            patch.object(roxy_codex_oauth, "_submit_email_step"),
            patch.object(roxy_codex_oauth, "complete_openai_login_challenge", resolver),
            patch.object(roxy_codex_oauth, "_wait_for_fresh_email_otp", return_value="123456"),
            patch.object(roxy_codex_oauth, "_wait_for_otp_input"),
            patch.object(roxy_codex_oauth, "_clear_otp_inputs"),
            patch.object(roxy_codex_oauth, "_type_otp"),
            patch.object(roxy_codex_oauth, "_install_email_otp_validate_hook"),
            patch.object(roxy_codex_oauth, "_click_if_present", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_after_email_otp_submit", return_value="totp_required"),
        ):
            result = roxy_codex_oauth._fill_email_and_otp(
                driver,
                "account@example.com",
                MagicMock(),
                "https://auth.openai.com/oauth/authorize",
            )

        self.assertIsNone(result)
        self.assertEqual(2, resolver.call_count)
        self.assertEqual("totp-secret", resolver.call_args_list[1].args[3])
        self.assertEqual("account@example.com", resolver.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
