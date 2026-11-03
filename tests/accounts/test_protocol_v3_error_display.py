"""v3 新的认证分支在任务列表保留具体原因。"""
import unittest

from core.accounts.liveness.service import (
    _refresh_result_is_unknown,
    _safe_refresh_auth_diagnostics,
    _safe_refresh_cause_code,
)
from core.operations.errors import classify_task_error


class ProtocolV3ErrorDisplayTests(unittest.TestCase):
    def test_new_causes_keep_classified_task_display(self):
        for code in (
            "identity_mismatch", "identity_unconfirmed", "account_reference_mismatch",
            "workspace_ambiguous", "workspace_missing", "account_profile_required",
            "untrusted_auth_url", "auth_challenge_loop", "cached_session_network_failed",
            "cached_session_http_failed", "cached_session_invalid_response",
            "auth_redirect_invalid", "auth_redirect_limit", "auth_navigation_failed",
            "session_fetch_failed", "session_invalid_response", "protocol_v3_unknown_error",
            "email_otp_validate_failed", "email_otp_validate_invalid_response",
            "workspace_select_failed", "workspace_select_invalid_response",
            "access_token_expired", "auth_context_ambiguous",
        ):
            with self.subTest(code=code):
                self.assertEqual(code, _safe_refresh_cause_code({"error_code": code}))
                result = classify_task_error(code, task_type="token_refresh", error_code=code,
                                             result_summary={"cause_code": code})
                self.assertNotEqual("unknown.unclassified", result["code"])
                self.assertTrue(result.get("display_code"))

    def test_challenge_diagnostics_retain_safe_operation(self):
        for operation in ("email_otp_validate", "workspace_select"):
            with self.subTest(operation=operation):
                self.assertEqual(
                    {"operation": operation},
                    _safe_refresh_auth_diagnostics({"operation": operation, "secret": "never-save"}),
                )

    def test_v3_unknown_auth_result_requires_reconciliation(self):
        self.assertTrue(_refresh_result_is_unknown({"error_code": "protocol_v3_unknown_error"}))


if __name__ == "__main__":
    unittest.main()
