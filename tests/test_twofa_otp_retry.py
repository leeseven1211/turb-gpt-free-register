"""2FA 邮箱验证码临时拒绝的恢复边界。"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import account_export as flow


def response(status, payload=None, *, headers=None, text=None):
    return SimpleNamespace(
        status_code=status, headers=headers or {},
        text=json.dumps(payload or {}) if text is None else text,
        json=lambda: payload or {},
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
