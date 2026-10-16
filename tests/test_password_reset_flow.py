import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import roxy_codex_oauth
from core.registration import email_otp


class PasswordResetFlowTests(unittest.TestCase):
    def _relogin_context(self, driver):
        stack = ExitStack()
        for name in ('_clear_confirmed_email_submission', '_safe_get', 'human_delay', '_maybe_accept', 'report_stage'):
            stack.enter_context(patch.object(roxy_codex_oauth, name))
        stack.enter_context(patch.object(roxy_codex_oauth, '_login_challenge_state', return_value={'url': driver.current_url}))
        for name in ('_is_login_advanced', '_is_login_password_page', '_is_email_verification_page'):
            stack.enter_context(patch.object(roxy_codex_oauth, name, return_value=False))
        return stack

    def test_reset_relogin_confirms_email_transition_before_using_new_password(self):
        driver = SimpleNamespace(current_url='https://chatgpt.com/auth/login')
        provider = Mock()
        events = []
        with self._relogin_context(driver) as stack:
            flow = stack.enter_context(patch.object(email_otp, '_submit_email_and_wait_next', return_value='login_password'))
            typed = stack.enter_context(patch.object(roxy_codex_oauth, '_type_email_address'))
            submit = stack.enter_context(patch.object(roxy_codex_oauth, '_submit_email_step'))
            resolve = stack.enter_context(patch.object(roxy_codex_oauth, '_complete_login_challenge_after_email', return_value='advanced'))
            roxy_codex_oauth._relogin_after_password_reset(
                driver, 'account@example.com', 'Generated!123', 'saved-totp', provider,
                stage_reporter=lambda **event: events.append(event),
            )
            flow.call_args.kwargs['on_progress']('waiting_frontend', '等待表单接管')

        flow.assert_called_once()
        self.assertEqual(flow.call_args.args, (driver, 'account@example.com'))
        self.assertTrue(flow.call_args.kwargs['allow_login_password'])
        self.assertTrue(any(event['detail'].get('email_phase') == 'waiting_frontend' for event in events))
        typed.assert_not_called()
        submit.assert_not_called()
        self.assertEqual(resolve.call_args.args, (driver, 'account@example.com', 'Generated!123', 'saved-totp'))
        self.assertIs(resolve.call_args.kwargs['otp_provider'], provider)
        self.assertFalse(resolve.call_args.kwargs['allow_password_reset'])

    def test_reset_relogin_preserves_email_failure_without_repeating_reset(self):
        driver = SimpleNamespace(current_url='https://chatgpt.com/auth/login')
        error = email_otp._EmailFrontendNotReady('email_frontend_not_ready')
        with self._relogin_context(driver) as stack:
            stack.enter_context(patch.object(email_otp, '_submit_email_and_wait_next', side_effect=error))
            resolve = stack.enter_context(patch.object(roxy_codex_oauth, '_complete_login_challenge_after_email'))
            reset = stack.enter_context(patch.object(roxy_codex_oauth, '_reset_password_via_email'))
            with self.assertRaises(email_otp._EmailFrontendNotReady):
                roxy_codex_oauth._relogin_after_password_reset(
                    driver, 'account@example.com', 'Generated!123', '', Mock(),
                )

        resolve.assert_not_called()
        reset.assert_not_called()

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
            patch.object(roxy_codex_oauth, "human_delay"),
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
