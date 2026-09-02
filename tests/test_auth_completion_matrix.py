import unittest
from unittest.mock import MagicMock, patch

from core.account_completion_service import completion_plan
from core import protocol_v2_liveness
from core import live_check_service
from core import codex_retry_service
from core import roxy_liveness
from core.auth_challenge import auth_result_for_operation


class AuthCompletionMatrixTests(unittest.TestCase):
    def test_account_completion_plan_covers_all_saved_credential_combinations(self):
        settings = {
            "password_enabled": True,
            "plan_check_enabled": False,
            "twofa_enabled": True,
            "codex_enabled": False,
            "refresh_at_enabled": False,
        }
        expected = {
            (False, False): ["password", "twofa"],
            (True, False): ["twofa"],
            (False, True): ["password"],
            (True, True): [],
        }
        for (has_password, has_totp), missing in expected.items():
            account = {
                "access_token": "saved-token",
                "totp_secret": "totp-secret" if has_totp else "",
                "extra_json": '{"account_password":"saved-password"}' if has_password else "{}",
            }
            self.assertEqual(missing, completion_plan(account, settings)["missing_steps"])

    def test_protocol_v2_success_exposes_the_complete_challenge_chain(self):
        session_info = {"accessToken": "token", "user": {}, "account": {}}
        session = type("Session", (), {"proxy": ""})()

        with patch.object(
            protocol_v2_liveness,
            "_refresh_with_password",
            return_value={
                "ok": True,
                "status": "live",
                "auth_method": "password_email_otp_mfa",
                "access_token": "token",
            },
        ):
            result = protocol_v2_liveness.refresh_access_token("account@example.com", proxy="")

        self.assertEqual(
            ["password", "email_otp", "totp"],
            result["auth"]["challenge_chain"],
        )
        self.assertEqual("existing", result["auth"]["remote_identity"])

    def test_protocol_v2_rejected_password_exposes_non_fallback_auth_result(self):
        error = protocol_v2_liveness.ProtocolV2AuthError(
            "password_rejected",
            roxy_fallback_allowed=False,
        )
        with patch.object(protocol_v2_liveness, "_refresh_with_password", side_effect=error):
            result = protocol_v2_liveness.refresh_access_token("account@example.com", proxy="")

        self.assertEqual("password_rejected", result["auth"]["status"])
        self.assertFalse(result["auth"]["roxy_fallback_allowed"])
        self.assertEqual("stop", result["auth"]["next_action"])

    def test_account_operation_result_projection_is_safe_for_success_and_failure(self):
        success = auth_result_for_operation(
            {"ok": True, "status": "success", "auth_method": "roxy"},
            auth_method="roxy",
        )
        failure = auth_result_for_operation(
            {"ok": False, "status": "failed", "message": "secret must not leak"},
            auth_method="roxy",
        )

        self.assertEqual("authenticated", success.status)
        self.assertEqual("request_unknown", failure.status)
        self.assertNotIn("message", failure.as_dict())

    def test_browser_error_text_with_explicit_password_code_keeps_stop_policy(self):
        result = auth_result_for_operation(
            {"ok": False, "error": "Roxy PasswordRejectedError: password_rejected"},
            auth_method="roxy",
        )

        self.assertEqual("password_rejected", result.code)
        self.assertFalse(result.roxy_fallback_allowed)
        self.assertEqual("stop", result.next_action)

    def test_live_check_service_attaches_the_same_auth_projection(self):
        result = live_check_service._attach_auth_projection(
            {"ok": False, "error": "password_result_unknown", "roxy_fallback_allowed": False},
            auth_method="legacy_email_otp",
        )

        self.assertEqual("password_result_unknown", result["auth"]["status"])
        self.assertFalse(result["auth"]["roxy_fallback_allowed"])

    def test_account_completion_worker_attaches_the_same_auth_projection(self):
        result = codex_retry_service._attach_auth_projection(
            {"ok": True, "status": "success", "twofa_driver": "protocol"},
            auth_method="protocol_direct",
        )

        self.assertEqual("authenticated", result["auth"]["status"])
        self.assertEqual("protocol_direct", result["auth"]["auth_method"])

    def test_roxy_refresh_resolves_totp_after_email_otp_without_resending_email(self):
        resolver = MagicMock(return_value="advanced")
        with (
            patch.object(roxy_liveness, "wait_for_otp", return_value="123456"),
            patch.object(roxy_liveness, "_clear_otp_inputs"),
            patch.object(roxy_liveness, "_type_otp"),
            patch.object(roxy_liveness, "_click_continue"),
            patch.object(roxy_liveness, "_wait_after_email_otp_submit", return_value="totp_required"),
            patch.object(roxy_liveness, "_click_resend_email_otp") as resend,
            patch("core.roxy_codex_oauth.complete_openai_login_challenge", resolver),
        ):
            roxy_liveness._complete_otp(
                MagicMock(),
                "account@example.com",
                100.0,
                totp_secret="totp-secret",
            )

        resolver.assert_called_once()
        resend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
