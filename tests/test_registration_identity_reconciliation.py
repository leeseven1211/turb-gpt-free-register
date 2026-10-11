import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from core.auth_challenge import (
    RemoteExistingAccountError,
    auth_result_for_operation,
    classify_registration_identity,
    safe_to_start_new_registration,
)
from core import registration_service
from core.openai_auth import AccountUnusableError
from core.registration import roxy as roxy_registration
from core.registration import protocol as protocol_registration
from core import roxy_codex_oauth


class RegistrationIdentityContractTests(unittest.TestCase):
    def test_login_password_is_classified_as_remote_existing(self):
        self.assertEqual("existing", classify_registration_identity("login_password"))
        self.assertEqual("existing", classify_registration_identity("logged_in"))
        self.assertEqual("existing", classify_registration_identity("external_url"))

    def test_profile_and_password_steps_are_new_registration_candidates(self):
        self.assertEqual("new_candidate", classify_registration_identity("password"))
        self.assertEqual("new_candidate", classify_registration_identity("otp"))
        self.assertEqual("new_candidate", classify_registration_identity("profile"))

    def test_unknown_state_is_not_safe_for_new_registration(self):
        result = {
            "remote_identity": "unknown",
            "request_unknown": True,
        }

        self.assertEqual("unknown", classify_registration_identity("unknown"))
        self.assertFalse(safe_to_start_new_registration(result))

    def test_existing_identity_is_not_safe_for_new_registration(self):
        result = {
            "remote_identity": "existing",
            "manual_reconcile": True,
        }

        self.assertFalse(safe_to_start_new_registration(result))

    def test_registration_auth_projection_keeps_the_non_sensitive_challenge_chain(self):
        projection = auth_result_for_operation(
            {
                "ok": True,
                "auth_method": "roxy",
                "challenge_chain": ["email_otp", "totp"],
            },
            auth_method="roxy",
            remote_identity="existing",
        )

        self.assertEqual(["email_otp", "totp"], projection.as_dict()["challenge_chain"])

    def test_registration_result_status_reports_unconfirmed_as_failed(self):
        self.assertEqual(
            "failed",
            registration_service.registration_result_status({"manual_reconcile": True}),
        )
        self.assertEqual(
            "failed",
            registration_service.registration_result_status({"request_unknown": True}),
        )

    def test_pre_auth_transport_unknown_is_retryable_failure_not_manual_confirmation(self):
        result = {
            "success": False,
            "remote_identity": "unknown",
            "remote_identity_state": "not_started",
            "remote_account_state": "not_started",
            "request_unknown": True,
            "error": "request_unknown: RuntimeError: 邮箱提交/认证跳转超过总预算 60 秒，最后状态={'url': 'chrome-error://chromewebdata/'}",
        }
        proxy = MagicMock(provider="1024proxy")

        self.assertEqual("failed", registration_service.registration_result_status(result))
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(
                registration_service._should_retry_registration_with_new_proxy(result, proxy, 0)
            )

    def test_post_submit_unknown_remains_a_reconciliation_fence(self):
        result = {
            "success": False,
            "remote_identity": "unknown",
            "request_unknown": True,
            "error": "request_unknown: _PasswordTransitionTimeout: 密码提交后页面结果待确认",
        }
        proxy = MagicMock(provider="1024proxy")

        self.assertEqual("failed", registration_service.registration_result_status(result))
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(
                registration_service._should_retry_registration_with_new_proxy(result, proxy, 0)
            )

    def test_password_submit_unknown_with_browser_error_remains_a_reconciliation_fence(self):
        result = {
            "success": False,
            "remote_identity": "unknown",
            "request_unknown": True,
            "error": "request_unknown: _PasswordTransitionTimeout: 密码提交后认证跳转超时，chrome-error://chromewebdata/",
        }
        proxy = MagicMock(provider="1024proxy")

        self.assertEqual("failed", registration_service.registration_result_status(result))
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(
                registration_service._should_retry_registration_with_new_proxy(result, proxy, 0)
            )

    def test_confirmed_checkpoint_never_uses_pre_auth_transport_retry(self):
        result = {
            "success": False,
            "remote_identity": "unknown",
            "remote_identity_state": "confirmed",
            "remote_account_state": "confirmed",
            "checkpoint": "account_confirmed",
            "request_unknown": True,
            "error": "request_unknown: ERR_SSL_PROTOCOL_ERROR",
        }
        proxy = MagicMock(provider="1024proxy")

        self.assertEqual("failed", registration_service.registration_result_status(result))
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(
                registration_service._should_retry_registration_with_new_proxy(result, proxy, 0)
            )

    def test_pre_auth_tls_error_is_retryable_failure_not_manual_confirmation(self):
        result = {
            "success": False,
            "remote_identity": "unknown",
            "remote_identity_state": "not_started",
            "remote_account_state": "not_started",
            "request_unknown": True,
            "error": "request_unknown: RuntimeError: ERR_SSL_PROTOCOL_ERROR",
        }
        proxy = MagicMock(provider="1024proxy")

        self.assertEqual("failed", registration_service.registration_result_status(result))
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(
                registration_service._should_retry_registration_with_new_proxy(result, proxy, 0)
            )

    def test_roxy_login_password_page_raises_explicit_existing_identity_error(self):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/log-in/password"

        with patch.object(roxy_registration, "_type_email_address", return_value="login_password"):
            with self.assertRaises(RemoteExistingAccountError):
                roxy_registration._submit_email_and_wait_next(driver, "account@example.com", attempts=1)

    def test_roxy_unknown_post_email_state_is_request_unknown(self):
        self.assertTrue(
            roxy_registration._is_registration_request_unknown(
                "邮箱提交后未识别到密码、OTP 或登录态分支"
            )
        )

    def test_protocol_login_password_continuation_is_remote_existing(self):
        self.assertEqual(
            "existing",
            protocol_registration._classify_registration_continuation(
                "login_password",
                "https://auth.openai.com/log-in/password",
            ),
        )

    def test_protocol_new_candidate_finalizes_oauth_after_create_account(self):
        session = MagicMock()
        session.proxy = ""
        session.device_id = "device-id"
        session.sentinel_sid = None
        session.browser_profile = None

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol_registration, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol_registration, "network_preflight"))
            stack.enter_context(patch.object(protocol_registration, "get_providers"))
            stack.enter_context(patch.object(protocol_registration, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol_registration, "signin_openai", return_value="authorize"))
            stack.enter_context(
                patch.object(
                    protocol_registration,
                    "follow_authorize",
                    return_value="https://auth.openai.com/email-verification",
                )
            )
            stack.enter_context(
                patch.object(
                    protocol_registration,
                    "validate_email_otp",
                    return_value={
                        "page": {"type": "about_you"},
                        "continue_url": "https://auth.openai.com/about-you",
                    },
                )
            )
            stack.enter_context(patch.object(protocol_registration, "navigate_about_you"))
            stack.enter_context(
                patch.object(protocol_registration, "request_sentinel_token", return_value={"token": "opaque"})
            )
            stack.enter_context(
                patch.object(protocol_registration, "build_sentinel_header", return_value=("sentinel", None))
            )
            create_account = stack.enter_context(
                patch.object(
                    protocol_registration,
                    "create_account",
                    return_value={"continue_url": "https://auth.openai.com/authorize/continue?state=opaque"},
                )
            )
            finalize = stack.enter_context(
                patch.object(
                    protocol_registration,
                    "_finalize_registration_session",
                    return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
                )
            )
            persist_core = stack.enter_context(
                patch("core.registration_service.persist_registration_core", return_value=7)
            )
            wait_for_otp = stack.enter_context(
                patch.object(protocol_registration, "wait_for_otp", return_value="123456")
            )
            run_codex_oauth = stack.enter_context(
                patch(
                    "core.codex_oauth.run_codex_oauth",
                    return_value={"status": "skipped", "ok": True, "message": "测试跳过"},
                )
            )
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(
                patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True})
            )
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(protocol_registration, "human_delay"))
            stack.enter_context(patch.object(protocol_registration._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(
                patch.multiple(
                    protocol_registration._protocol_cfg,
                    CHATGPT_ANON_BOOTSTRAP_ENABLED=False,
                    CHATGPT_AUTH_BOOTSTRAP_ENABLED=False,
                    create=True,
                )
            )
            result = protocol_registration.run_protocol_registration(
                "new@example.com",
                "New User",
                "2000-01-01",
                email_source="icloud_hide",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": True,
                    "plan_check_enabled": False,
                },
            )
            oauth_otp_provider = run_codex_oauth.call_args.kwargs["otp_provider"]
            oauth_otp_provider("new@example.com", after_ts=123.0)

        self.assertTrue(persist_core.called, result)
        self.assertTrue(result["success"], result)
        self.assertEqual("new_candidate", result["remote_identity"])
        self.assertEqual(
            {"accessToken": "fresh-token", "user": {}, "account": {}},
            persist_core.call_args.kwargs["chatgpt_session"],
        )
        create_account.assert_called_once()
        self.assertEqual(wait_for_otp.call_args.kwargs["email_source"], "icloud_hide")
        self.assertEqual(persist_core.call_args.kwargs["email_source"], "icloud_hide")
        self.assertEqual(wait_for_otp.call_count, 2)
        finalize.assert_called_once_with(
            session,
            "https://auth.openai.com/authorize/continue?state=opaque",
            "new@example.com",
        )

    def test_protocol_marks_confirmed_unusable_account_failed_without_disabling(self):
        session = MagicMock()
        session.proxy = ""

        with (
            patch.object(protocol_registration, "BrowserSession", return_value=session),
            patch.object(
                protocol_registration,
                "network_preflight",
                side_effect=AccountUnusableError(
                    "账号已废弃（account_deleted）",
                    error_code="account_deleted",
                ),
            ),
            patch("core.email_provider.release_email", return_value="icloud_hide") as release_email,
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.registration_service.report_job_progress"),
        ):
            result = protocol_registration.run_protocol_registration(
                "dead@example.com",
                "Dead User",
                "2000-01-01",
                registration_options={"codex_enabled": False, "plan_check_enabled": False},
                email_source="icloud_hide",
            )

        self.assertFalse(result["success"])
        self.assertEqual(release_email.call_args.kwargs["status"], "failed")
        self.assertNotEqual(release_email.call_args.kwargs["status"], "disabled")
        self.assertEqual(release_email.call_args.kwargs["source"], "icloud_hide")
        retain_email.assert_not_called()


class RegistrationServiceRetryBoundaryTests(unittest.TestCase):
    def test_transient_pre_auth_unknown_identity_can_rotate_proxy(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "request_unknown": False,
            "error": "RuntimeError: ERR_TUNNEL_CONNECTION_FAILED",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_transient_proxy_retry_is_blocked_for_existing_remote_identity(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "existing",
            "manual_reconcile": True,
            "error": "err_connection_reset",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_registration_stage_timeout_can_rotate_before_remote_identity_is_known(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "request_unknown": False,
            "error": "registration_failed: StageTimeout: Roxy registration stage timeout exhausted",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_auth_route_rejection_before_account_creation_can_rotate_proxy(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "remote_identity_state": "not_started",
            "request_unknown": False,
            "manual_reconcile": False,
            "error_code": "auth_route_rejected",
            "retry_as_new_route": True,
            "error": "HTTP 403",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_auth_route_rejection_cannot_bypass_confirmed_checkpoint(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "remote_identity_state": "confirmed",
            "remote_account_state": "confirmed",
            "checkpoint": "account_confirmed",
            "error_code": "auth_route_rejected",
            "retry_as_new_route": True,
            "error": "Auth authorize 路由被拒绝: HTTP 403",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_explicit_account_deleted_cannot_bypass_route_retry_guard(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "error_code": "account_deleted",
            "retry_as_new_route": True,
            "error": "账号已删除",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_new_candidate_identity_cannot_start_duplicate_registration(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "new_candidate",
            "request_unknown": False,
            "error": "ERR_CONNECTION_RESET",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

    def test_explicit_profile_rejection_never_starts_a_second_account(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "account_id": 1540,
            "registration_pending": True,
            "access_token": "",
            "retry_as_new_registration": True,
            "error_code": "account_create_rejected",
            "error": "account_create_rejected: 远端资料页明确拒绝创建账号",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))


class RegistrationLoginErrorPageTests(unittest.TestCase):
    def test_auth_error_page_is_not_treated_as_advanced_login(self):
        state = {
            "url": "https://chatgpt.com/auth/error?error=undefined",
            "inputs": [],
            "errors": [],
            "text": "",
        }

        self.assertFalse(roxy_codex_oauth._is_login_advanced(None, state))

    def test_auth_error_page_raises_terminal_login_error(self):
        state = {
            "url": "https://chatgpt.com/auth/error?error=undefined",
            "inputs": [],
            "errors": [],
            "text": "",
        }
        driver = MagicMock()

        with patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state):
            with self.assertRaisesRegex(RuntimeError, "auth/error"):
                roxy_codex_oauth._complete_login_challenge_after_email(
                    driver, "account@example.com", "saved-password", "", timeout=5,
                )


if __name__ == "__main__":
    unittest.main()
