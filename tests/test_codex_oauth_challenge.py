# -*- coding: utf-8 -*-
"""Codex Protocol 登录挑战的本地响应模拟测试。"""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import codex_oauth


class CodexOAuthChallengeTests(unittest.TestCase):
    def _submit_with_response(self, payload, *, status_code=200):
        response = SimpleNamespace(status_code=status_code, json=lambda: payload)
        with patch.object(codex_oauth, "request_sentinel_token", return_value={}), patch.object(
            codex_oauth, "build_sentinel_header", return_value=("sentinel", None)
        ), patch.object(codex_oauth, "_post_json", return_value=response), patch.object(
            codex_oauth.time, "time", return_value=100.0
        ), patch.object(codex_oauth, "navigate_email_otp_send") as send:
            step = codex_oauth._submit_email(object(), "account@example.test")
        return step, send

    def test_direct_email_verification_waits_without_extra_send(self):
        result, send = self._submit_with_response({
            "page": {"type": "email_verification"},
            "continue_url": "/email-verification",
        })
        self.assertEqual(result, ("verify", "/email-verification", 100.0))
        send.assert_not_called()

    def test_email_send_follows_only_confirmed_auth_route(self):
        result, send = self._submit_with_response({
            "page": {"type": "email_otp_send"},
            "continue_url": "/api/accounts/email-otp/send",
        })
        self.assertEqual(result, ("verify", "", 100.0))
        send.assert_called_once_with(
            unittest.mock.ANY,
            continue_url="/api/accounts/email-otp/send",
            referer="https://auth.openai.com/log-in",
        )

    def test_password_challenge_does_not_wait_or_send_email(self):
        result, send = self._submit_with_response({
            "page": {"type": "login_password"},
            "continue_url": "/log-in/password",
        })
        self.assertEqual(result, ("password", "/log-in/password", 100.0))
        send.assert_not_called()

    def test_workspace_select_is_reserved_for_existing_post_flow(self):
        result, send = self._submit_with_response({
            "continue_url": "/api/accounts/workspace/select",
        })
        self.assertEqual(result, ("continue", "", 100.0))
        send.assert_not_called()

    def test_callback_log_keeps_path_without_authorization_code(self):
        path = codex_oauth._url_path_for_log(
            "http://localhost:1455/auth/callback?code=private-code&state=private-state"
        )
        self.assertEqual(path, "/auth/callback")

    def test_callback_error_does_not_echo_query(self):
        location = "http://localhost:1455/auth/callback?state=private-state&trace=private-value"
        with self.assertRaises(RuntimeError) as raised:
            codex_oauth._extract_code(location, "private-state")
        self.assertNotIn("private-state", str(raised.exception))
        self.assertNotIn("private-value", str(raised.exception))

    def test_sub2_callback_summary_excludes_unknown_payload(self):
        summary = codex_oauth._summarize_sub2_response({
            "message": "private-secret", "credential": "private-token", "success": True,
        })
        self.assertEqual(summary, "success=true")

    def test_cpa_callback_failure_keeps_retry_category_without_remote_body(self):
        response = SimpleNamespace(
            status_code=409,
            json=lambda: {"message": "timeout waiting for oauth callback private-token"},
            text="private-token",
        )
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"), patch.object(
            codex_oauth, "_cpa_management_key", return_value="private-key"
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._cpa_request_json("POST", "/v0/management/oauth-callback", {})
        message = str(raised.exception)
        self.assertNotIn("private-token", message)
        self.assertIn("category=oauth_callback_timeout", message)
        self.assertTrue(codex_oauth._is_cpa_callback_reauth_error(raised.exception))

    def test_sub2_failure_does_not_echo_remote_response(self):
        response = SimpleNamespace(
            status_code=502,
            json=lambda: {"detail": "private-token"},
            text="private-token",
        )
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_sub2_codex_base", return_value="https://sub2.example.test"), patch.object(
            codex_oauth, "_sub2_codex_headers", return_value={}
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._sub2_codex_request_json("POST", "/callback", {})
        self.assertNotIn("private-token", str(raised.exception))
        self.assertIn("status=502", str(raised.exception))

    def test_cpa_auth_file_download_failure_does_not_echo_remote_response(self):
        response = SimpleNamespace(status_code=502, text="private-token")
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"), patch.object(
            codex_oauth, "_cpa_management_key", return_value="private-key"
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._cpa_request_raw("GET", "/v0/management/auth-files/download")
        self.assertNotIn("private-token", str(raised.exception))
        self.assertIn("status=502", str(raised.exception))

    def test_unknown_or_untrusted_step_does_not_send_email(self):
        for payload in (
            {},
            {"page": {"type": "email_otp_send"}},
            {"continue_url": "https://untrusted.example/api/accounts/email-otp/send"},
            {"continue_url": "https://auth.openai.com:bad/email-verification"},
            {"page": {"type": "login_password"}, "continue_url": "/api/accounts/email-otp/send"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(RuntimeError) as raised:
                    self._submit_with_response(payload)
                self.assertNotIn("untrusted.example", str(raised.exception))

    def test_saved_password_can_continue_without_email_otp(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        with patch("core.account_credentials.get_account_login_credentials", return_value=("private-password", "")), patch(
            "core.protocol_v2_liveness._password_verify",
            return_value={"continue_url": "/api/accounts/continue"},
        ) as verify:
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password?state=opaque"
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        verify.assert_called_once_with(session, "private-password")
        self.assertEqual(
            session.get.call_args.args[0],
            "https://auth.openai.com/log-in/password?state=opaque",
        )

    def test_saved_password_mfa_uses_existing_totp_protocol(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        password_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "/mfa-challenge/factor-1",
        }
        with patch("core.account_credentials.get_account_login_credentials", return_value=("private-password", "private-secret")), patch(
            "core.protocol_v2_liveness._password_verify", return_value=password_result,
        ), patch("core.protocol_v2_liveness._mfa_issue_challenge") as issue, patch(
            "core.protocol_v2_liveness._totp_code", return_value="123456"
        ), patch("core.protocol_v2_liveness._mfa_verify", return_value={
            "continue_url": "/api/accounts/continue"
        }) as verify, patch.object(codex_oauth, "report_stage"), patch.object(
            codex_oauth, "check_cancelled"
        ):
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password"
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        issue.assert_called_once_with(session, "factor-1")
        verify.assert_called_once_with(session, "factor-1", "123456")

    def test_new_registration_credentials_need_no_database_read(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        password_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "/mfa-challenge/factor-1",
        }
        with patch("core.account_credentials.get_account_login_credentials") as saved, patch(
            "core.protocol_v2_liveness._password_verify", return_value=password_result
        ) as password_verify, patch(
            "core.protocol_v2_liveness._mfa_issue_challenge"
        ), patch("core.protocol_v2_liveness._totp_code", return_value="123456") as totp_code, patch(
            "core.protocol_v2_liveness._mfa_verify", return_value={
                "continue_url": "/api/accounts/continue"
            }
        ), patch.object(codex_oauth, "report_stage"), patch.object(codex_oauth, "check_cancelled"):
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password",
                login_password="Password!123", login_totp_secret="private-secret",
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        password_verify.assert_called_once_with(session, "Password!123")
        totp_code.assert_called_once_with("private-secret")
        saved.assert_not_called()

    def test_password_result_unknown_is_not_classified_as_failed(self):
        from core.protocol_v2_liveness import ProtocolV2AuthError

        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        with patch(
            "core.protocol_v2_liveness._password_verify",
            side_effect=ProtocolV2AuthError("password_result_unknown"),
        ):
            with self.assertRaises(codex_oauth.CodexAuthResultUnknown):
                codex_oauth._verify_saved_login_password(
                    session, "account@example.test", "/log-in/password",
                    login_password="Password!123",
                )

    def test_email_otp_rejection_does_not_echo_code_or_response(self):
        response = SimpleNamespace(
            status_code=400,
            text="private response 123456",
            json=lambda: {"error": {"code": "invalid_code"}},
        )
        with patch.object(codex_oauth, "request_sentinel_token", return_value={}), patch.object(
            codex_oauth, "build_sentinel_header", return_value=("sentinel", None)
        ), patch.object(codex_oauth, "_post_json", return_value=response):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._submit_email_otp(object(), "123456")
        self.assertNotIn("123456", str(raised.exception))
        self.assertNotIn("private response", str(raised.exception))

    def test_password_continue_skips_otp_and_phone_waiters(self):
        otp_provider = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_oauth, "BrowserSession"))
            stack.enter_context(patch.object(codex_oauth, "check_cancelled"))
            stack.enter_context(patch.object(codex_oauth, "report_stage"))
            stack.enter_context(patch.object(codex_oauth, "human_delay"))
            stack.enter_context(patch.object(codex_oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(codex_oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(codex_oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(codex_oauth, "network_preflight"))
            stack.enter_context(patch.object(codex_oauth, "_bootstrap_authorize"))
            stack.enter_context(patch.object(
                codex_oauth, "_submit_email", return_value=("password", "/log-in/password", 100.0)
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_verify_saved_login_password",
                return_value=("continue", "/api/accounts/continue", 101.0),
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_follow_login_continue", side_effect=RuntimeError("授权后续模拟停止")
            ))
            submit_otp = stack.enter_context(patch.object(codex_oauth, "_submit_email_otp"))
            phone = stack.enter_context(patch.object(codex_oauth, "_do_phone_verification"))
            result = codex_oauth.run_codex_oauth(
                "account@example.test",
                otp_provider=otp_provider,
                proxy="",
                force=True,
                driver_override="protocol",
            )
        self.assertEqual(result["status"], "failed")
        self.assertIn("授权后续模拟停止", result["message"])
        otp_provider.assert_not_called()
        submit_otp.assert_not_called()
        phone.assert_not_called()

    def test_password_post_unknown_requires_reconciliation(self):
        otp_provider = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_oauth, "BrowserSession"))
            stack.enter_context(patch.object(codex_oauth, "check_cancelled"))
            stack.enter_context(patch.object(codex_oauth, "report_stage"))
            stack.enter_context(patch.object(codex_oauth, "human_delay"))
            stack.enter_context(patch.object(codex_oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(codex_oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(codex_oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(codex_oauth, "network_preflight"))
            stack.enter_context(patch.object(codex_oauth, "_bootstrap_authorize"))
            stack.enter_context(patch.object(
                codex_oauth, "_submit_email", return_value=("password", "/log-in/password", 100.0)
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_verify_saved_login_password",
                side_effect=codex_oauth.CodexAuthResultUnknown("结果未知"),
            ))
            submit_otp = stack.enter_context(patch.object(codex_oauth, "_submit_email_otp"))
            phone = stack.enter_context(patch.object(codex_oauth, "_do_phone_verification"))
            result = codex_oauth.run_codex_oauth(
                "account@example.test", otp_provider=otp_provider,
                proxy="", force=True, driver_override="protocol",
            )
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["outcome"], "request_unknown")
        self.assertTrue(result["reconcile_required"])
        otp_provider.assert_not_called()
        submit_otp.assert_not_called()
        phone.assert_not_called()


if __name__ == "__main__":
    unittest.main()
