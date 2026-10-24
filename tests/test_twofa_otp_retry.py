"""2FA 邮箱验证码临时拒绝的恢复边界。"""
import json
import traceback
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import account_export as flow


def response(status, payload=None, *, headers=None, text=None, url=""):
    return SimpleNamespace(
        status_code=status, headers=headers or {},
        text=json.dumps(payload or {}) if text is None else text,
        json=lambda: payload or {},
        url=url, history=[],
    )


class TwofaOtpRetryTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.object(flow, "_reauth_retry_settings", return_value=(3, 3.0))
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.session = Mock()
        self.session.get_auth_headers.return_value = {}

    def test_temporary_refusal_reuses_original_session_and_code(self):
        self.session.post.side_effect = [
            response(403), response(429, headers={"Retry-After": "8"}),
            response(200, {"continue_url": "https://example.test/callback"}),
        ]
        with patch.object(flow.time, "sleep") as sleep, patch.object(flow, "_clear_twofa_session_circuit") as clear:
            result = flow._validate_reauth_otp_with_retry(self.session, "012345")
        self.assertEqual(result, "https://example.test/callback")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [3.0, 8])
        self.assertEqual(clear.call_count, 2)
        self.assertEqual(self.session.post.call_count, 3)
        for call in self.session.post.call_args_list:
            self.assertEqual(json.loads(call.kwargs["data"]), {"code": "012345"})

    def test_business_errors_and_challenges_do_not_retry(self):
        cases = [
            response(403, {"error": {"code": "invalid_otp"}}),
            response(429, {"error": {"message": "request rejected"}}),
            response(403, headers={"cf-mitigated": "challenge"}),
            response(403, text="<html>challenge-platform</html>"),
            response(401), response(500),
        ]
        for rejected in cases:
            with self.subTest(status=rejected.status_code, payload=rejected.json()):
                self.session.post.reset_mock()
                self.session.post.side_effect = None
                self.session.post.return_value = rejected
                with patch.object(flow.time, "sleep") as sleep, self.assertRaises(flow.TwofaProtocolHTTPError):
                    flow._validate_reauth_otp_with_retry(self.session, "012345")
                self.session.post.assert_called_once()
                sleep.assert_not_called()

    def test_long_or_unparseable_cooldown_does_not_retry_early(self):
        for value in ("121", "999999", "Wed, 21 Oct 2026 07:28:00 GMT", "-1", "１２"):
            with self.subTest(value=value):
                self.session.post.reset_mock()
                self.session.post.return_value = response(429, headers={"Retry-After": value})
                with patch.object(flow.time, "sleep") as sleep, self.assertRaises(flow.TwofaProtocolHTTPError):
                    flow._validate_reauth_otp_with_retry(self.session, "012345")
                self.session.post.assert_called_once()
                sleep.assert_not_called()

    def test_retry_limit_is_bounded_and_diagnostics_hide_response_contents(self):
        self.session.post.return_value = response(403, {"message": "OTP=012345 user@example.test"})
        with patch.object(flow.time, "sleep"), self.assertLogs(flow.logger, "WARNING") as logs:
            with self.assertRaises(flow.TwofaProtocolHTTPError) as raised:
                flow._validate_reauth_otp_with_retry(self.session, "012345")
        self.assertEqual(self.session.post.call_count, 3)
        rendered = "\n".join(logs.output) + str(raised.exception)
        self.assertNotIn("012345", rendered)
        self.assertNotIn("user@example.test", rendered)

    def test_unknown_transport_result_is_not_replayed_or_exposed(self):
        self.session.post.side_effect = TimeoutError("unknown OTP=012345 user@example.test")
        with patch.object(flow.time, "sleep") as sleep, self.assertRaises(flow.TwofaProtocolTransportError) as raised:
            flow._validate_reauth_otp_with_retry(self.session, "012345")
        self.session.post.assert_called_once()
        sleep.assert_not_called()
        self.assertNotIn("012345", str(raised.exception))
        self.assertNotIn("user@example.test", str(raised.exception))


class TwofaReauthDispatchTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.session = Mock()
        self.session.get_auth_navigate_headers.return_value = {}
        self.landing = "https://auth.openai.com/email-verification"
        self.send_response = response(200, url=self.landing)
        self.now = 100.0

        def navigate(url, **_kwargs):
            if url == "https://auth.openai.com/authorize":
                self.events.append("navigate")
                self.now = 200.0
                return response(200, url=self.landing)
            self.assertEqual(url, "https://auth.openai.com/api/accounts/email-otp/send")
            self.events.append("send")
            self.now = 201.0
            if isinstance(self.send_response, Exception):
                raise self.send_response
            return self.send_response

        def wait(_email, *, after_ts):
            self.events.append(("wait", after_ts))
            return "012345"

        self.session.get.side_effect = navigate
        patches = [
            patch.object(flow, "human_delay"),
            patch.object(flow.time, "time", side_effect=lambda: self.now),
            patch.object(flow, "_trigger_reauth_with_retry", return_value="https://auth.openai.com/authorize"),
            patch.object(flow, "_warm_auth_document_for_reauth"),
            patch.object(flow, "_validate_reauth_otp_with_retry", return_value="https://chatgpt.com/callback"),
            patch.object(flow, "_exchange_new_token_with_retry", return_value="fresh-token"),
            patch.object(flow, "_enroll_totp", return_value=("test-secret", "test-session")),
            patch.object(flow, "_activate_totp", return_value=True),
            patch("config.email.USE_EMAIL_SERVICE", True),
            patch("core.email_provider.wait_for_otp", side_effect=wait),
        ]
        self.mocks = [p.start() for p in patches]
        for item in patches:
            self.addCleanup(item.stop)
        self.wait_for_otp = self.mocks[-1]
        self.validate = self.mocks[4]

    def test_verified_landing_sends_before_waiting_with_new_mail_anchor(self):
        result = flow.setup_2fa(self.session, "user@example.test")

        self.assertEqual(result, "test-secret")
        self.assertEqual(self.events, ["navigate", "send", ("wait", 200.0)])
        self.validate.assert_called_once_with(self.session, "012345")

    def test_other_landing_does_not_send_or_wait_and_keeps_safe_reason(self):
        for landing in (
            "https://auth.openai.com/log-in/password?email=user@example.test&state=private-state",
            "https://auth.openai.com/error?code=private-code",
            "https://example.test/email-verification",
            "http://auth.openai.com/email-verification",
            "https://auth.openai.com:444/email-verification",
        ):
            with self.subTest(landing=landing):
                self.landing = landing
                self.events.clear()
                with self.assertRaises(flow.TwofaProtocolStepError) as raised:
                    flow.setup_2fa(self.session, "user@example.test")
                self.assertIn("unexpected_auth_page", str(raised.exception))
                self.assertNotIn("user@example.test", str(raised.exception))
                self.assertNotIn("private-", str(raised.exception))
                self.assertEqual(self.events, ["navigate"])
        self.wait_for_otp.assert_not_called()
        self.validate.assert_not_called()

    def test_send_rejection_does_not_wait_for_mail(self):
        self.send_response = response(200, url="https://auth.openai.com/error")

        with self.assertRaises(flow.TwofaProtocolStepError) as raised:
            flow.setup_2fa(self.session, "user@example.test")

        self.assertEqual(raised.exception.operation, "reauth_otp_send")
        self.assertEqual(self.events, ["navigate", "send"])
        self.wait_for_otp.assert_not_called()
        self.validate.assert_not_called()

    def test_unknown_send_result_is_not_replayed_or_exposed(self):
        self.send_response = TimeoutError("user@example.test OTP=012345 private-state")

        with self.assertRaises(flow.TwofaProtocolStepError) as raised:
            flow.setup_2fa(self.session, "user@example.test")

        self.assertEqual(self.events, ["navigate", "send"])
        self.wait_for_otp.assert_not_called()
        self.validate.assert_not_called()
        rendered = "".join(traceback.format_exception(raised.exception))
        for private in ("user@example.test", "012345", "private-state"):
            self.assertNotIn(private, rendered)

    def test_supplied_code_is_not_invalidated_by_resending(self):
        result = flow.setup_2fa(self.session, "user@example.test", otp_code="123456")

        self.assertEqual(result, "test-secret")
        self.assertEqual(self.events, ["navigate"])
        self.wait_for_otp.assert_not_called()
        self.validate.assert_called_once_with(self.session, "123456")

    def test_manual_entry_also_waits_for_successful_dispatch(self):
        with patch("config.email.USE_EMAIL_SERVICE", False), patch("builtins.input", return_value="123456"):
            result = flow.setup_2fa(self.session, "user@example.test")

        self.assertEqual(result, "test-secret")
        self.assertEqual(self.events, ["navigate", "send"])
        self.wait_for_otp.assert_not_called()
        self.validate.assert_called_once_with(self.session, "123456")
