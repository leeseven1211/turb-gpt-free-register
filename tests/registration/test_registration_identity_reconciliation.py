import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from core.auth.challenge import RemoteExistingAccountError, auth_result_for_operation, classify_registration_identity, safe_to_start_new_registration
from core.registration import service as registration_service
from core.auth.protocol.openai_auth import AccountUnusableError
from core.registration import roxy as roxy_registration
from core.auth.state_machine import StageBudget
from core.codex.roxy import oauth as roxy_codex_oauth


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

    def test_pre_auth_transport_unknown_remains_reconciliation_fence(self):
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
            self.assertFalse(
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

    def test_pre_auth_tls_unknown_remains_reconciliation_fence(self):
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
            self.assertFalse(
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





class RegistrationServiceRetryBoundaryTests(unittest.TestCase):
    def test_resume_get_failure_requires_positive_current_route_facts(self):
        job = {"job_type": "registration_resume", "email": "held@example.test"}
        result = {
            "success": False, "email": job["email"], "account_id": 42,
            "request_unknown": True, "checkpoint": "account_request_started",
            "proxy_transport_failure": True, "current_lease_route_verified": True,
            "resume_login_get_transport_failure": True,
            "resume_proxy_rotation_ready": True, "resume_proxy_rotation_profile_id": "held-profile",
            "error": "net::ERR_TUNNEL_CONNECTION_FAILED",
        }
        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(registration_service._should_retry_registration_resume_with_new_proxy(
                result, job, 0, existing_password="saved-password",
            ))
            for field in ("proxy_transport_failure", "current_lease_route_verified",
                          "resume_login_get_transport_failure", "resume_proxy_rotation_ready"):
                for value in (False, None, "true"):
                    with self.subTest(field=field, value=value):
                        self.assertFalse(registration_service._should_retry_registration_resume_with_new_proxy(
                            {**result, field: value}, job, 0, existing_password="saved-password",
                        ))
            for changed_job, password, retry_count in (
                ({**job, "job_type": "registration"}, "saved-password", 0),
                ({**job, "email": "other@example.test"}, "saved-password", 0),
                (job, "", 0), (job, "saved-password", 2),
            ):
                with self.subTest(job=changed_job, password_present=bool(password), retry_count=retry_count):
                    self.assertFalse(registration_service._should_retry_registration_resume_with_new_proxy(
                        result, changed_job, retry_count, existing_password=password,
                    ))

    def test_transport_fault_is_independent_from_unknown_account_fence(self):
        result = {"request_unknown": True, "account_id": 42,
                  "proxy_transport_failure": True, "current_lease_route_verified": True}
        self.assertTrue(registration_service._confirmed_registration_proxy_transport_failure(result))
        for changed in (
            {"current_lease_route_verified": False},
            {"proxy_transport_failure": False},
            {"proxy_transport_failure": "true"},
        ):
            with self.subTest(changed=changed):
                self.assertFalse(registration_service._confirmed_registration_proxy_transport_failure(
                    {**result, **changed},
                ))
        for error in ("HTTP 400", "HTTP 403", "ERR_TUNNEL_CONNECTION_FAILED",
                      "StageTimeout", "找不到邮箱输入框/邮箱入口"):
            with self.subTest(error=error):
                self.assertFalse(registration_service._confirmed_registration_proxy_transport_failure({"error": error}))

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

    def test_registration_stage_timeout_does_not_rotate_before_remote_identity_is_known(self):
        proxy = MagicMock(provider="1024proxy")
        result = {
            "success": False,
            "remote_identity": "unknown",
            "request_unknown": False,
            "error": "registration_failed: StageTimeout: Roxy registration stage timeout exhausted",
        }

        with patch.object(registration_service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(registration_service._should_retry_registration_with_new_proxy(result, proxy, 0))

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
