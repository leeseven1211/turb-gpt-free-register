"""验证 AT 回调接线、挑战事实与共享登录入口的隔离。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.liveness.protocol import callback, v2
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost


EMAIL = "callback@example.test"
CALLBACK_URL = "https://chatgpt.com/api/auth/callback/openai?code=fixture"


class AtCallbackIntegrationTests(unittest.TestCase):
    def scenario(self, *, email_login=False):
        stack = ExitStack()
        self.addCleanup(stack.close)
        session = SimpleNamespace(session=SimpleNamespace(close=Mock()), proxy="fixture-route")
        stack.enter_context(patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "fixture-secret")))
        stack.enter_context(patch.object(v2, "account_email_is_invalid", return_value=False))
        stack.enter_context(patch.object(v2, "_network_preflight_with_retry", return_value=(session, "fixture-authorize")))
        landing = "https://auth.openai.com/email-verification" if email_login else "https://auth.openai.com/log-in/password"
        stack.enter_context(patch.object(v2, "follow_authorize", return_value=landing))
        stack.enter_context(patch.object(v2, "_open_offered_password_login", return_value=landing))
        stack.enter_context(patch.object(v2, "send_email_otp"))
        mfa = {"page": {"type": "mfa_challenge"}, "continue_url": "https://auth.openai.com/mfa-challenge/fixture-factor"}
        password = stack.enter_context(patch.object(v2, "_password_verify", return_value=mfa))
        otp = stack.enter_context(patch.object(v2, "_validate_with_retry", return_value=mfa))
        stack.enter_context(patch.object(v2, "_mfa_issue_challenge"))
        mfa_verify = stack.enter_context(patch.object(v2, "_mfa_verify", return_value={"continue_url": CALLBACK_URL}))
        stack.enter_context(patch.object(v2, "_totp_code", return_value="fixture-code"))
        stack.enter_context(patch.object(v2, "build_safe_fingerprint_summary", return_value={}))
        recovery = stack.enter_context(patch.object(callback, "complete_callback"))
        return session, recovery, password, otp, mfa_verify

    def test_callback_failure_keeps_email_and_mfa_success_facts(self):
        session, recovery, password, otp, mfa = self.scenario(email_login=True)
        recovery.side_effect = callback.CallbackRecoveryError("oauth_callback_failed", category="network", diagnostics={
            "operation": "oauth_callback", "failure_kind": "transport_error", "curl_error_code": 18,
        })
        result = v2.refresh_access_token(EMAIL, callback_recovery=True)
        self.assertEqual("oauth_callback_failed", result["error"])
        self.assertEqual(["email_otp", "totp"], result["challenge_chain"])
        self.assertEqual("success", result["email_otp_status"])
        self.assertEqual("success", result["mfa_status"])
        self.assertEqual(18, result["auth_diagnostics"]["curl_error_code"])
        self.assertFalse(result["roxy_fallback_allowed"])
        password.assert_not_called()
        otp.assert_called_once()
        mfa.assert_called_once()
        session.session.close.assert_called_once()
        self.assertIsNone(v2._AT_CALLBACK_CONTEXT.get())

    def test_password_receipt_survives_later_session_failure(self):
        _, recovery, password, otp, mfa = self.scenario()
        recovery.side_effect = callback.CallbackRecoveryError("session_fetch_failed", category="network", diagnostics={
            "operation": "session_fetch", "failure_kind": "http_error", "http_status": 503,
        })
        result = v2.refresh_access_token(EMAIL, callback_recovery=True)
        self.assertEqual("verified", result["password_auth_status"])
        self.assertEqual("success", result["mfa_status"])
        self.assertEqual(["password", "totp"], result["challenge_chain"])
        password.assert_called_once()
        otp.assert_not_called()
        mfa.assert_called_once()

    def test_email_fallback_keeps_callback_network_reason_and_completed_challenges(self):
        session, recovery, password, _, _ = self.scenario()
        password.side_effect = v2.ProtocolV2AuthError("password_rejected")
        recovery.side_effect = callback.CallbackRecoveryError("oauth_callback_failed", category="network", diagnostics={
            "operation": "oauth_callback", "failure_kind": "transport_error", "curl_error_code": 18,
        })
        with patch.object(v2, "_start_email_session", return_value=(session, 0)):
            result = v2.refresh_access_token(EMAIL, callback_recovery=True, allow_password_email_fallback=True)
        self.assertEqual("password_rejected_email_fallback_failed", result["error"])
        self.assertEqual("oauth_callback", result["auth_diagnostics"]["cause_operation"])
        self.assertEqual(18, result["auth_diagnostics"]["curl_error_code"])
        self.assertEqual("success", result["email_otp_status"])
        self.assertEqual("success", result["mfa_status"])

    def test_shared_login_default_does_not_enable_recovery(self):
        _, recovery, _, _, _ = self.scenario()
        info = {"accessToken": "fixture-at", "user": {"email": EMAIL}}
        with patch.object(v2, "follow_oauth_callback") as old_callback, patch.object(v2, "fetch_session", return_value=info):
            result = v2.refresh_access_token(EMAIL)
        self.assertTrue(result["ok"])
        recovery.assert_not_called()
        old_callback.assert_called_once()
        self.assertNotIn("challenge_chain", result)

    def test_cancellation_and_lease_loss_escape_wrapped_otp_helpers(self):
        for error in (OperationCancelled("取消"), OperationLeaseLost("租约失效")):
            with self.subTest(error=type(error).__name__):
                _, recovery, _, _, _ = self.scenario(email_login=True)
                recovery.side_effect = error
                with self.assertRaises(type(error)):
                    v2.refresh_access_token(EMAIL, callback_recovery=True)
                recovery.assert_called_once()
                self.assertIsNone(v2._AT_CALLBACK_CONTEXT.get())

    def test_passwordless_refresh_injects_callback_without_changing_legacy_default(self):
        session, recovery, _, _, _ = self.scenario()
        info = {"accessToken": "fixture-at", "user": {"email": EMAIL}}
        recovery.return_value = info

        def legacy(email, **kwargs):
            received = kwargs["callback_handler"](session, CALLBACK_URL, referer="https://auth.openai.com/email-verification")
            return {"ok": True, "session": received}

        with patch.object(v2, "get_account_login_credentials", return_value=("", "")), patch.object(v2, "check_account_liveness", side_effect=legacy):
            result = v2.refresh_access_token(EMAIL, callback_recovery=True)
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["email_otp_status"])
        recovery.assert_called_once()
