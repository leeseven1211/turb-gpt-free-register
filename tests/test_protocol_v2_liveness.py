# -*- coding: utf-8 -*-
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class _Response:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class _Session:
    def __init__(self, proxy="http://proxy.example:8080"):
        self.proxy = proxy
        self.posts = []
        self.session = MagicMock()

    def get_auth_headers(self, referer=""):
        return {"referer": referer, "openai-sentinel-token": "stale"}

    def post(self, url, headers, data, allow_redirects=False):
        self.posts.append((url, headers, json.loads(data), allow_redirects))
        return _Response(200, {"continue_url": "https://auth.openai.com/authorize/continue?code=x"})


class _OtpResponse:
    def __init__(self, *, status_code=200, url="https://auth.openai.com/email-verification", headers=None, history=None):
        self.status_code = status_code
        self.url = url
        self.headers = headers or {"content-type": "application/json"}
        self.history = history or []
        self.text = "{}"


class _OtpSession:
    def __init__(self, response):
        self.response = response

    def get_auth_navigate_headers(self, referer=""):
        return {"referer": referer}

    def get(self, *args, **kwargs):
        return self.response


class ProtocolV2LivenessTests(unittest.TestCase):
    def test_credentials_reader_never_uses_email_provider_password(self):
        from core import account_credentials

        with patch(
            "core.db.get_account_by_email",
            return_value={
                "password": "mail-provider-password",
                "account_password": "openai-password",
                "totp_secret": "totp-secret",
            },
        ):
            self.assertEqual(
                ("openai-password", "totp-secret"),
                account_credentials.get_account_login_credentials("account@example.com"),
            )

    def test_password_verify_posts_sentinel_and_never_logs_or_returns_password(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        with (
            patch.object(v2, "request_sentinel_token", return_value={"token": "challenge"}),
            patch.object(v2, "build_sentinel_header", return_value=("sentinel", "so")),
        ):
            result = v2._password_verify(session, "CorrectPassword!123")

        self.assertEqual("https://auth.openai.com/api/accounts/password/verify", session.posts[0][0])
        self.assertEqual("sentinel", session.posts[0][1]["openai-sentinel-token"])
        self.assertEqual("so", session.posts[0][1]["openai-sentinel-so-token"])
        self.assertEqual({"password": "CorrectPassword!123"}, session.posts[0][2])
        self.assertEqual("https://auth.openai.com/authorize/continue?code=x", result["continue_url"])

    def test_password_http_401_invalid_password_is_classified_as_rejected(self):
        from core import protocol_v2_liveness as v2

        class RejectedSession(_Session):
            def post(self, url, headers, data, allow_redirects=False):
                return _Response(401, {"error": {"code": "invalid_password"}}, text='{"error":{"code":"invalid_password"}}')

        with (
            patch.object(v2, "request_sentinel_token", return_value={"token": "challenge"}),
            patch.object(v2, "build_sentinel_header", return_value=("sentinel", None)),
        ):
            with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                v2._password_verify(RejectedSession(), "wrong")

        self.assertEqual("password_rejected", caught.exception.code)
        self.assertFalse(caught.exception.roxy_fallback_allowed)

    def test_password_http_401_real_login_failure_code_is_classified_as_rejected(self):
        from core import protocol_v2_liveness as v2

        class RejectedSession(_Session):
            def post(self, url, headers, data, allow_redirects=False):
                return _Response(
                    401,
                    {
                        "error": {
                            "message": "Login failed. Please try again or seek help at https://help.openai.com/",
                            "type": "invalid_request_error",
                            "param": None,
                            "code": "invalid_username_or_password",
                        }
                    },
                    text='{"error":{"code":"invalid_username_or_password"}}',
                )

        with (
            patch.object(v2, "request_sentinel_token", return_value={"token": "challenge"}),
            patch.object(v2, "build_sentinel_header", return_value=("sentinel", None)),
        ):
            with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                v2._password_verify(RejectedSession(), "wrong")

        self.assertEqual("password_rejected", caught.exception.code)
        self.assertFalse(caught.exception.roxy_fallback_allowed)

    def test_password_rejection_is_classified_without_roxy_or_email_fallback_by_default(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        rejected = v2.ProtocolV2AuthError("password_rejected", roxy_fallback_allowed=False)
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", side_effect=rejected),
            patch.object(v2, "_start_email_session") as start_email,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_rejected", result["error"])
        self.assertEqual("rejected", result["password_auth_status"])
        self.assertFalse(result["roxy_fallback_allowed"])
        start_email.assert_not_called()

    def test_password_direct_callback_returns_authenticated_session(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", return_value={"continue_url": "https://auth.openai.com/authorize/continue?code=x"}),
            patch.object(v2, "_follow_and_fetch", return_value={"accessToken": "fresh", "account": {"planType": "free"}}),
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("password", result["auth_method"])
        self.assertEqual("authenticated_session", result["validation_method"])
        self.assertEqual("http://proxy.example:8080", result["proxy_used"])
        session.session.close.assert_called_once()

    def test_missing_password_uses_existing_email_refresh_path_without_password_post(self):
        from core import protocol_v2_liveness as v2

        legacy = {
            "ok": True,
            "status": "live",
            "access_token": "fresh",
            "validation_method": "email_otp",
        }
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("", "")),
            patch.object(v2, "check_account_liveness", return_value=legacy) as check,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="http://proxy.example:8080")

        self.assertTrue(result["ok"])
        self.assertEqual("legacy_email_otp", result["auth_method"])
        self.assertEqual("protocol_v2", result["live_check_driver"])
        check.assert_called_once_with(
            "account@example.com",
            proxy="http://proxy.example:8080",
            clear_log=False,
            proxy_supplier=None,
        )

    def test_password_email_challenge_uses_email_state_machine_then_returns_token(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        password_result = {
            "page": {"type": "email_verification"},
            "continue_url": "https://auth.openai.com/email-verification",
        }
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", return_value=password_result),
            patch.object(v2, "_complete_email_otp", return_value=({"accessToken": "fresh"}, "password_email_otp")) as complete_email,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("password_email_otp", result["auth_method"])
        complete_email.assert_called_once_with(
            session,
            "account@example.com",
            unittest.mock.ANY,
            auth_method="password_email_otp",
        )

    def test_password_email_challenge_can_continue_to_totp(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        password_result = {
            "page": {"type": "email_verification"},
            "continue_url": "https://auth.openai.com/email-verification",
        }
        email_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "https://auth.openai.com/mfa-challenge/factor-1",
        }
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "totp-secret")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", return_value=password_result),
            patch.object(v2, "_complete_email_otp", return_value=(email_result, "password_email_otp")),
            patch.object(v2, "_complete_mfa", return_value=({"accessToken": "fresh"}, "password_email_otp_mfa")) as complete_mfa,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("password_email_otp_mfa", result["auth_method"])
        complete_mfa.assert_called_once_with(
            session,
            email_result,
            "https://auth.openai.com/mfa-challenge/factor-1",
            "totp-secret",
        )

    def test_password_page_without_continue_url_stops_without_clicking_or_following(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", return_value={"page": {"type": "unknown"}}),
            patch.object(v2, "_follow_and_fetch") as follow,
            patch.object(v2, "_start_email_session") as start_email,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("auth_page_unknown", result["error"])
        follow.assert_not_called()
        start_email.assert_not_called()

    def test_mfa_path_requires_remote_challenge_and_saved_totp(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        password_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "https://auth.openai.com/mfa-challenge/factor-1",
        }
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "JBSWY3DPEHPK3PXP")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", return_value=password_result),
            patch.object(v2, "_mfa_issue_challenge", return_value={"ok": True}) as issue,
            patch.object(v2, "_totp_code", return_value="123456"),
            patch.object(v2, "_mfa_verify", return_value={"continue_url": "https://auth.openai.com/authorize/continue?code=x"}) as verify,
            patch.object(v2, "_follow_and_fetch", return_value={"accessToken": "fresh", "account": {"planType": "free"}}),
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("password_mfa_totp", result["auth_method"])
        issue.assert_called_once_with(session, "factor-1")
        verify.assert_called_once_with(session, "factor-1", "123456")

    def test_password_rejection_can_use_one_fresh_email_session_when_explicitly_enabled(self):
        from config import account as account_config
        from core import protocol_v2_liveness as v2

        original = _Session()
        fallback = _Session()
        rejected = v2.ProtocolV2AuthError("password_rejected", roxy_fallback_allowed=False)
        with (
            patch.object(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", True),
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(original, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", side_effect=rejected),
            patch.object(v2, "_start_email_session", return_value=(fallback, 123.0)),
            patch.object(v2, "_complete_email_otp", return_value=({"accessToken": "fresh"}, "password_fallback_email_otp")),
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertTrue(result["ok"])
        self.assertEqual("password_fallback_email_otp", result["auth_method"])
        self.assertEqual("rejected", result["password_auth_status"])
        self.assertTrue(result["fallback_used"])
        self.assertFalse(result["roxy_fallback_allowed"] if "roxy_fallback_allowed" in result else False)
        original.session.close.assert_called_once()
        fallback.session.close.assert_called_once()

    def test_password_fallback_does_not_send_from_password_page(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        with (
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
        ):
            with self.assertRaises(v2.ProtocolV2AuthError) as caught:
                v2._start_email_session("account@example.com", proxy="")

        self.assertEqual("passwordless_fallback_unavailable", caught.exception.code)
        session.session.close.assert_called_once()

    def test_password_fallback_preserves_unavailable_reason_without_waiting_for_otp(self):
        from config import account as account_config
        from core import protocol_v2_liveness as v2

        original = _Session()
        rejected = v2.ProtocolV2AuthError("password_rejected", roxy_fallback_allowed=False)
        unavailable = v2.ProtocolV2AuthError("passwordless_fallback_unavailable", category="auth", roxy_fallback_allowed=False)
        with (
            patch.object(account_config, "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK", True),
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(original, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", side_effect=rejected),
            patch.object(v2, "_start_email_session", side_effect=unavailable),
            patch.object(v2, "_complete_email_otp") as complete_email,
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("passwordless_fallback_unavailable", result["error"])
        self.assertEqual("rejected", result["password_auth_status"])
        self.assertFalse(result["roxy_fallback_allowed"])
        complete_email.assert_not_called()
        original.session.close.assert_called_once()

    def test_password_fallback_accepts_authorize_email_challenge_without_resend(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        with (
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/email-verification"),
        ):
            result = v2._start_email_session("account@example.com", proxy="")

        self.assertIs(session, result[0])
        self.assertGreater(result[1], 0)
        session.session.close.assert_not_called()

    def test_email_otp_send_rejects_redirect_to_error_even_when_final_status_is_200(self):
        from core import openai_auth

        response = _OtpResponse(
            url="https://auth.openai.com/error",
            headers={"content-type": "text/html; charset=utf-8"},
            history=[
                SimpleNamespace(
                    status_code=302,
                    url="https://auth.openai.com/api/accounts/email-otp/send",
                    headers={"location": "https://auth.openai.com/error"},
                )
            ],
        )
        with self.assertRaisesRegex(RuntimeError, "email_otp_send_rejected"):
            openai_auth.send_email_otp(_OtpSession(response))

    def test_email_otp_send_accepts_explicit_json_success(self):
        from core import openai_auth

        response = _OtpResponse(
            headers={"content-type": "application/json"},
        )
        self.assertIsNone(openai_auth.send_email_otp(_OtpSession(response)))

    def test_password_result_unknown_never_becomes_password_rejected(self):
        from core import protocol_v2_liveness as v2

        session = _Session()
        unknown = v2.ProtocolV2AuthError("password_result_unknown", category="network", retryable=True)
        with (
            patch.object(v2, "get_account_login_credentials", return_value=("saved-password", "")),
            patch.object(v2, "_network_preflight_with_retry", return_value=(session, "authorize")),
            patch.object(v2, "follow_authorize", return_value="https://auth.openai.com/log-in/password"),
            patch.object(v2, "_password_verify", side_effect=unknown),
        ):
            result = v2.refresh_access_token("account@example.com", proxy="")

        self.assertFalse(result["ok"])
        self.assertEqual("password_result_unknown", result["error"])
        self.assertNotIn("password_auth_status", result)
        self.assertFalse(result["roxy_fallback_allowed"])

    def test_refresh_driver_is_gated_and_legacy_is_default(self):
        from config import account as account_config
        from core import live_check_service

        with patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", False):
            self.assertEqual("legacy", live_check_service._resolve_refresh_driver("protocol_v2"))
        with patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", True):
            self.assertEqual("protocol_v2", live_check_service._resolve_refresh_driver("protocol_v2"))
        self.assertEqual("legacy", live_check_service._resolve_refresh_driver("legacy"))

    def test_refresh_enqueue_freezes_protocol_v2_driver_for_worker(self):
        from config import account as account_config
        from core import live_check_service

        with (
            patch.object(account_config, "ACCOUNT_TOKEN_REFRESH_DRIVER", "protocol_v2"),
            patch.object(account_config, "ACCOUNT_AUTH_V2_ENABLED", True),
            patch.object(
                live_check_service.db,
                "get_account",
                return_value={
                    "id": 7,
                    "email": "account@example.com",
                    "access_token": "existing-token",
                },
            ),
            patch.object(live_check_service.db, "account_is_deactivated", return_value=False),
            patch.object(live_check_service.db, "claim_account_live_check", return_value=True),
            patch.object(live_check_service.account_task_store, "create_task", return_value=101),
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service._EXECUTOR, "submit") as submit,
        ):
            result = live_check_service.enqueue_account_live_check(
                account_id=7,
                email="account@example.com",
                trigger="token_refresh_manual",
                proxy="",
                force_refresh=True,
            )

        self.assertTrue(result["accepted"])
        self.assertEqual("protocol_v2", result["token_refresh_driver"])
        self.assertEqual("protocol_v2", submit.call_args.kwargs["refresh_driver"])
        live_check_service._QUEUE_SLOTS.release()


if __name__ == "__main__":
    unittest.main()
