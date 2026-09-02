import unittest

from core.auth_challenge import (
    AuthAttemptResult,
    AuthStatus,
    auth_result_for_registration,
    normalize_auth_result,
)
from core.registration.state_machine import PageState, classify_page


class AuthChallengeContractTests(unittest.TestCase):
    def test_result_projection_contains_only_safe_compatibility_fields(self):
        result = AuthAttemptResult(
            status=AuthStatus.AUTHENTICATED,
            auth_method="email_otp",
            challenge_chain=("email_otp", "totp"),
            remote_identity="existing",
        )

        self.assertEqual(
            {
                "status": "authenticated",
                "code": "",
                "auth_method": "email_otp",
                "challenge_chain": ["email_otp", "totp"],
                "remote_identity": "existing",
                "retryable": False,
                "roxy_fallback_allowed": True,
                "next_action": "continue",
            },
            result.as_dict(),
        )

    def test_normalization_drops_secrets_and_provider_payloads(self):
        result = normalize_auth_result(
            {
                "status": "authenticated",
                "auth_method": "protocol",
                "challenge_chain": ["password"],
                "remote_identity": "existing",
                "retryable": False,
                "roxy_fallback_allowed": True,
                "next_action": "continue",
                "detail": {"access_token": "secret"},
                "access_token": "secret",
                "password": "secret",
                "totp_secret": "secret",
                "callback_url": "http://localhost:1455/auth/callback?code=secret",
            }
        )

        self.assertEqual("authenticated", result.status)
        self.assertEqual(["password"], list(result.challenge_chain))
        self.assertNotIn("access_token", result.as_dict())
        self.assertNotIn("password", result.as_dict())
        self.assertNotIn("totp_secret", result.as_dict())
        self.assertNotIn("callback_url", result.as_dict())
        self.assertNotIn("detail", result.as_dict())

    def test_registration_projection_uses_same_safe_contract(self):
        result = auth_result_for_registration(
            {"success": True},
            auth_method="roxy",
            remote_identity="new_candidate",
            challenge_chain=("email_otp", "totp"),
        )

        self.assertEqual(
            {
                "status": "authenticated",
                "code": "",
                "auth_method": "roxy",
                "challenge_chain": ["email_otp", "totp"],
                "remote_identity": "new_candidate",
                "retryable": False,
                "roxy_fallback_allowed": True,
                "next_action": "continue",
            },
            result.as_dict(),
        )

    def test_protocol_error_codes_keep_safe_retry_and_fallback_policy(self):
        rejected = normalize_auth_result({"error": "password_rejected"})
        unknown = normalize_auth_result({"error": "password_result_unknown"})
        unsupported = normalize_auth_result({"error": "unsupported"})

        self.assertEqual("password_rejected", rejected.code)
        self.assertFalse(rejected.retryable)
        self.assertFalse(rejected.roxy_fallback_allowed)
        self.assertEqual("password_result_unknown", unknown.code)
        self.assertFalse(unknown.roxy_fallback_allowed)
        self.assertEqual("unsupported", unsupported.code)
        self.assertTrue(unsupported.roxy_fallback_allowed)
        self.assertEqual("roxy_fallback", unsupported.next_action)


class TotpPageClassificationTests(unittest.TestCase):
    def test_authenticator_form_wins_over_generic_one_time_code_marker(self):
        state = {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Enter the code from your authenticator app",
            "inputs": [
                {"type": "text", "name": "totp", "autocomplete": "one-time-code"},
            ],
        }

        self.assertEqual(PageState.MFA_TOTP, classify_page(state))

    def test_email_verification_remains_email_otp_even_with_one_time_code_input(self):
        state = {
            "url": "https://auth.openai.com/email-verification",
            "text": "Enter the verification code sent to your email",
            "inputs": [
                {"type": "text", "name": "code", "autocomplete": "one-time-code"},
            ],
        }

        self.assertEqual(PageState.OTP_EMAIL, classify_page(state))


if __name__ == "__main__":
    unittest.main()
