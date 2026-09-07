import unittest
from unittest.mock import Mock, patch

from core import roxy_codex_oauth


class PasswordResetFlowTests(unittest.TestCase):
    def test_missing_forgot_link_does_not_start_reset(self):
        driver = Mock()
        with patch.object(roxy_codex_oauth, "_forgot_password_target", return_value=None), patch.object(
            roxy_codex_oauth, "_human_click"
        ) as click:
            result = roxy_codex_oauth._reset_password_via_email(
                driver,
                "account@example.com",
                Mock(),
            )

        self.assertFalse(result)
        click.assert_not_called()

    def test_reset_flow_uses_fresh_otp_and_checkpoints_submitted_password(self):
        driver = Mock()
        target = object()
        continue_target = object()
        otp_provider = Mock()
        checkpoint = Mock()
        with (
            patch.object(roxy_codex_oauth, "_forgot_password_target", return_value=target),
            patch.object(roxy_codex_oauth, "_human_click") as click,
            patch.object(roxy_codex_oauth, "_wait_for_reset_route", return_value=True),
            patch.object(roxy_codex_oauth, "_reset_continue_target", return_value=continue_target),
            patch.object(roxy_codex_oauth, "_wait_for_reset_otp_page", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_for_fresh_email_otp", return_value="123456") as wait_code,
            patch.object(roxy_codex_oauth, "_wait_for_otp_input"),
            patch.object(roxy_codex_oauth, "_clear_otp_inputs"),
            patch.object(roxy_codex_oauth, "_type_otp"),
            patch.object(roxy_codex_oauth, "_click_if_present", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_for_reset_password_form", return_value="accepted"),
            patch.object(roxy_codex_oauth, "_submit_reset_password_and_wait") as submit,
            patch.object(roxy_codex_oauth, "_relogin_after_password_reset") as relogin,
            patch("core.registration.selenium_auth.registration_password", return_value="Generated!123"),
        ):
            self.assertTrue(
                roxy_codex_oauth._reset_password_via_email(
                    driver,
                    "account@example.com",
                    otp_provider,
                    on_password_submitted=checkpoint,
                )
            )

        self.assertEqual(click.call_count, 2)
        submit.assert_called_once_with(
            driver,
            "account@example.com",
            "Generated!123",
            on_password_submitted=checkpoint,
        )
        relogin.assert_called_once()
        self.assertEqual(wait_code.call_args.args[:2], (otp_provider, "account@example.com"))
        self.assertEqual(wait_code.call_args.kwargs["used_codes"], {"123456"})


if __name__ == "__main__":
    unittest.main()
