import unittest
from unittest.mock import patch

from core.registration.state_machine import (
    FlowStateError,
    PageState,
    RegistrationStateMachine,
    StageBudget,
    StageTimeout,
    can_resend_otp,
    classify_page,
    run_with_budget,
)


class RegistrationStateMachineContractTests(unittest.TestCase):
    def test_roxy_page_states_are_explicit_and_password_intent_is_not_guessed(self):
        self.assertEqual(
            classify_page({
                "url": "https://auth.openai.com/create-account/password",
                "inputs": [{"type": "password", "autocomplete": "new-password", "visible": True}],
                "forms": [{"action": "/api/accounts/create_account"}],
            }),
            PageState.PASSWORD_CREATE,
        )
        self.assertEqual(
            classify_page({
                "url": "https://auth.openai.com/email-verification",
                "inputs": [{"type": "password", "autocomplete": "current-password", "visible": True}],
                "forms": [{"action": "/api/accounts/login"}],
                "text": "Sign in with your password",
            }),
            PageState.PASSWORD_LOGIN,
        )
        self.assertEqual(
            classify_page({
                "url": "https://auth.openai.com/create-account/password",
                "inputs": [{"type": "password", "visible": True}],
                "forms": [{"action": "/api/accounts/login"}],
            }),
            PageState.PASSWORD_LOGIN,
        )
        self.assertEqual(
            classify_page({
                "url": "https://auth.openai.com/email-verification",
                "inputs": [{"type": "text", "autocomplete": "one-time-code", "visible": True}],
            }),
            PageState.OTP_EMAIL,
        )

    def test_state_machine_rejects_reverse_or_ambiguous_transition(self):
        machine = RegistrationStateMachine()
        machine.transition(PageState.AUTH_TRANSIENT)
        machine.transition(PageState.OTP_EMAIL)
        machine.transition(PageState.EMAIL_VERIFIED)
        machine.transition(PageState.AUTHENTICATED)
        with self.assertRaises(FlowStateError):
            machine.transition(PageState.EMAIL_FORM)

    def test_one_stage_budget_is_shared_by_primary_assist_and_fallback(self):
        now = [100.0]
        budget = StageBudget.start(5, clock=lambda: now[0])
        calls = []

        def primary(stage):
            calls.append(("primary", round(stage.remaining(), 1)))
            now[0] = 103.0
            raise RuntimeError("protocol unavailable")

        def assist(stage):
            calls.append(("assist", round(stage.remaining(), 1)))
            now[0] = 104.0
            raise RuntimeError("assist unavailable")

        def fallback(stage):
            calls.append(("fallback", round(stage.remaining(), 1)))
            self.assertLessEqual(stage.remaining(), 1.0)
            return "roxy"

        self.assertEqual(run_with_budget(budget, primary, protocol_assist=assist, roxy_fallback=fallback), "roxy")
        self.assertEqual([item[0] for item in calls], ["primary", "assist", "fallback"])

    def test_budget_exhaustion_is_terminal_and_does_not_start_fallback(self):
        now = [100.0]
        budget = StageBudget.start(1, clock=lambda: now[0])
        calls = []

        def primary(stage):
            calls.append("primary")
            now[0] = 101.1
            raise RuntimeError("slow")

        def fallback(stage):
            calls.append("fallback")
            return "invalid"

        with self.assertRaises(StageTimeout):
            run_with_budget(budget, primary, roxy_fallback=fallback)
        self.assertEqual(calls, ["primary"])

    def test_verified_email_never_enters_resend_branch(self):
        self.assertTrue(can_resend_otp(PageState.OTP_EMAIL))
        self.assertFalse(can_resend_otp(PageState.EMAIL_VERIFIED))
        self.assertFalse(can_resend_otp(PageState.OTP_ACCEPTED, email_verified=True))
        self.assertEqual(
            classify_page({
                "url": "https://auth.openai.com/email-verification",
                "text": "Email verified successfully",
                "inputs": [{"autocomplete": "one-time-code", "visible": True}],
            }),
            PageState.EMAIL_VERIFIED,
        )

    def test_known_callback_error_and_logout_are_terminal_page_states(self):
        self.assertEqual(
            classify_page({"url": "https://chatgpt.com/auth/error?error=OAuthCallback"}),
            PageState.AUTH_ERROR,
        )
        self.assertEqual(
            classify_page({"url": "https://chatgpt.com/session-ended", "text": "Please log in"}),
            PageState.LOGGED_OUT,
        )

    def test_protocol_callback_error_stops_without_retrying_session(self):
        try:
            from core.registration import protocol
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional registration dependency unavailable: {exc}")

        session = object()
        with patch.object(
            protocol,
            "follow_oauth_callback",
            return_value="https://chatgpt.com/auth/error?error=OAuthCallback",
        ) as callback, patch.object(protocol, "fetch_session") as fetch, patch.object(protocol.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "AUTH_ERROR"):
                protocol._finalize_registration_session(
                    session,
                    "https://auth.openai.com/authorize/continue?state=opaque",
                    "test@example.com",
                    total_timeout=30,
                )

        callback.assert_called_once()
        fetch.assert_not_called()
        sleep.assert_not_called()

    def test_protocol_retry_consumes_one_shared_budget(self):
        try:
            from core.registration import protocol
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional registration dependency unavailable: {exc}")

        now = [100.0]
        budget = StageBudget.start(3, clock=lambda: now[0])
        session = object()

        def transient(*_args, **_kwargs):
            now[0] += 2.0
            raise RuntimeError("temporary connection reset")

        with patch.object(protocol, "follow_oauth_callback", side_effect=transient) as callback, patch.object(
            protocol.time, "sleep", side_effect=lambda seconds: now.__setitem__(0, now[0] + seconds)
        ) as sleep:
            with self.assertRaises(StageTimeout):
                protocol._finalize_registration_session(
                    session,
                    "https://auth.openai.com/authorize/continue?state=opaque",
                    "test@example.com",
                    budget=budget,
                )

        self.assertEqual(callback.call_count, 1)
        self.assertEqual(sleep.call_count, 1)

    def test_roxy_session_wait_stops_on_known_callback_error(self):
        try:
            from core.registration import roxy
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional registration dependency unavailable: {exc}")

        class Driver:
            current_url = "https://chatgpt.com/auth/error?error=OAuthCallback"

            def execute_script(self, _script):
                return ""

        with patch.object(roxy, "_read_chatgpt_session_once") as read_session:
            with self.assertRaisesRegex(RuntimeError, "AUTH_ERROR"):
                roxy._fetch_chatgpt_session(Driver(), timeout=30)
        read_session.assert_not_called()

    def test_roxy_otp_wait_exposes_email_verified_terminal(self):
        try:
            from core.registration import roxy
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional registration dependency unavailable: {exc}")

        driver = object()
        with patch.object(roxy, "_is_email_verification_page", return_value=True), patch.object(
            roxy,
            "_email_otp_page_state",
            return_value={"emailVerified": True, "inputs": [], "errors": []},
        ), patch.object(roxy.time, "monotonic", side_effect=[0.0, 0.0, 0.0]), patch.object(roxy.time, "sleep"):
            self.assertEqual(roxy._wait_after_email_otp_submit(driver, timeout=5), "email_verified")


if __name__ == "__main__":
    unittest.main()
