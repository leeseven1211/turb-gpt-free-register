import unittest
from unittest.mock import MagicMock, patch

from core.auth_challenge import (
    RemoteExistingAccountError,
    auth_result_for_operation,
    classify_registration_identity,
    safe_to_start_new_registration,
)
from core import registration_service
from core.registration import roxy as roxy_registration
from core.registration import protocol as protocol_registration


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

    def test_registration_result_status_preserves_reconciliation_states(self):
        self.assertEqual(
            "manual_reconcile",
            registration_service.registration_result_status({"manual_reconcile": True}),
        )
        self.assertEqual(
            "request_unknown",
            registration_service.registration_result_status({"request_unknown": True}),
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

        with (
            patch.object(protocol_registration, "BrowserSession", return_value=session),
            patch.object(protocol_registration, "network_preflight"),
            patch.object(protocol_registration, "get_providers"),
            patch.object(protocol_registration, "get_csrf_token", return_value="csrf"),
            patch.object(protocol_registration, "signin_openai", return_value="authorize"),
            patch.object(protocol_registration, "follow_authorize", return_value="https://auth.openai.com/email-verification"),
            patch.object(
                protocol_registration,
                "validate_email_otp",
                return_value={
                    "page": {"type": "about_you"},
                    "continue_url": "https://auth.openai.com/about-you",
                },
            ),
            patch.object(protocol_registration, "navigate_about_you"),
            patch.object(protocol_registration, "request_sentinel_token", return_value={"token": "opaque"}),
            patch.object(protocol_registration, "build_sentinel_header", return_value=("sentinel", None)),
            patch.object(
                protocol_registration,
                "create_account",
                return_value={"continue_url": "https://auth.openai.com/authorize/continue?state=opaque"},
            ) as create_account,
            patch.object(
                protocol_registration,
                "_finalize_registration_session",
                return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
            ) as finalize,
            patch("core.registration_service.persist_registration_core", return_value=7) as persist_core,
            patch("core.email_provider.resolve_email_source", return_value="generic_api"),
            patch("core.db.update_account_codex_status"),
            patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}),
            patch("core.registration_service.report_job_progress"),
            patch.object(protocol_registration, "human_delay"),
            patch.object(protocol_registration._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False, create=True),
            patch.object(protocol_registration._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", False, create=True),
        ):
            result = protocol_registration.run_protocol_registration(
                "new@example.com",
                "New User",
                "2000-01-01",
                otp_code="123456",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
            )

        self.assertTrue(persist_core.called, result)
        self.assertTrue(result["success"], result)
        self.assertEqual("new_candidate", result["remote_identity"])
        create_account.assert_called_once()
        finalize.assert_called_once_with(
            session,
            "https://auth.openai.com/authorize/continue?state=opaque",
            "new@example.com",
        )


class RegistrationServiceRetryBoundaryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
