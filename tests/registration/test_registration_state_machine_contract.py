import unittest
from unittest.mock import patch

from core.auth.state_machine import FlowStateError, PageState, RegistrationStateMachine, StageBudget, StageTimeout, can_resend_otp, classify_page, run_with_budget


class RegistrationStateMachineContractTests(unittest.TestCase):
    def test_sleep_crossing_poll_deadline_between_clock_reads_never_uses_negative_delay(self):
        ticks = iter((0.0, 0.0, 0.099, 0.099, 0.101))
        budget = StageBudget(10, clock=lambda: next(ticks, 0.101))
        delays = []

        def sleeper(seconds):
            self.assertGreaterEqual(seconds, 0)
            delays.append(seconds)

        budget.sleep(0.1, sleeper=sleeper)
        self.assertEqual(delays, [])

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

    def test_session_ended_text_overrides_stale_verification_route_in_supported_languages(self):
        for text in ("Your session has ended", "Your session has expired", "会话已结束", "会话已过期",
                     "セッションが終了しました", "セッションの有効期限が切れました"):
            with self.subTest(text=text):
                self.assertEqual(classify_page({
                    "url": "https://auth.openai.com/email-verification", "text": text,
                    "inputs": [{"type": "text", "autocomplete": "one-time-code"}],
                }), PageState.LOGGED_OUT)



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

    def test_session_json_document_reader_avoids_homepage_shell(self):
        from core.auth.browser.session_auth import _read_chatgpt_session_document

        class Driver:
            def execute_script(self, _script):
                return '{"accessToken":"opaque-token","user":{}}'

        self.assertEqual(
            _read_chatgpt_session_document(Driver()),
            {"accessToken": "opaque-token", "user": {}},
        )

    def test_session_warning_banner_is_classified_before_long_timeout(self):
        from core.auth.browser import session_auth

        class Driver:
            def execute_async_script(self, _script):
                return {
                    "ok": True,
                    "status": 200,
                    "data": {"WARNING_BANNER": "unauthenticated"},
                }

        with self.assertRaisesRegex(RuntimeError, "chatgpt_session_unavailable"):
            session_auth._read_chatgpt_session_once(Driver())

    def test_session_document_warning_banner_is_not_treated_as_pending_token(self):
        from core.auth.browser import session_auth

        class Driver:
            current_url = "https://chatgpt.com/api/auth/session"

            def execute_script(self, _script):
                return '{"WARNING_BANNER":"unauthenticated"}'

        with self.assertRaisesRegex(RuntimeError, "chatgpt_session_unavailable"):
            session_auth._read_chatgpt_session_document(Driver())

    def test_session_fetch_short_circuits_repeated_warning_banner(self):
        from core.auth.browser import session_auth

        class Driver:
            current_url = "https://chatgpt.com/api/auth/session"

            def execute_script(self, _script):
                return '{"WARNING_BANNER":"unauthenticated"}'

            def execute_async_script(self, _script):
                return {
                    "ok": True,
                    "status": 200,
                    "data": {"WARNING_BANNER": "unauthenticated"},
                }

        with patch.object(session_auth.time, "sleep", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "chatgpt_session_unavailable"):
                session_auth._fetch_chatgpt_session(Driver(), timeout=120)

    def test_registration_snapshot_does_not_eagerly_read_codex_config(self):
        try:
            from core.registration import roxy
        except ModuleNotFoundError as exc:
            self.skipTest(f"optional registration dependency unavailable: {exc}")

        class ExplodingCodexConfig:
            def __getattr__(self, name):
                raise AssertionError(f"live Codex config was read: {name}")

        stop_before_browser = RuntimeError("stop before browser")
        with (
            patch.object(roxy, "_codex_cfg", ExplodingCodexConfig()),
            patch.object(roxy, "RoxyBrowserClient", return_value=object()),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", side_effect=stop_before_browser),
            patch("core.registration.service.report_job_progress"),
        ):
            with self.assertRaisesRegex(RuntimeError, "stop before browser"):
                roxy.run_roxy_registration(
                    "test@example.com",
                    "Test User",
                    birthday="1990-01-01",
                    proxy="http://pool.example:8080",
                    registration_options={"codex_enabled": False},
                )

        self.assertNotIn("_codex_cfg", roxy.run_roxy_registration.__code__.co_varnames)

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
