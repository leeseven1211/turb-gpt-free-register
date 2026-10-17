import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import roxy_codex_oauth
from core import roxy_liveness
from core.auth_challenge import MfaSecretMissingError, PasswordRejectedError
from core.registration.browser_submission import BrowserSubmissionReceipt
from core.registration import roxy as roxy_registration
from core.registration.auth_context import AuthExecutionContext, current_execution_context, execution_context
from core.registration.password_auth import _PasswordTransitionTimeout
from core.registration.state_machine import StageBudget, StageTimeout


class RoxyEmailOtpChallengeTests(unittest.TestCase):
    def _resolve_offered_password(self, *, password="saved-password", offered=True, navigation_works=True,
                                 password_already_submitted=False):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/email-verification"
        target = "https://auth.openai.com/log-in/password"
        driver.get.side_effect = lambda url: setattr(driver, "current_url", url) if navigation_works else None
        clock = [100.0]

        def state(_driver):
            return {"url": driver.current_url, "inputs": [{"name": "code"}], "errors": [], "buttons": []}

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=state),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
            patch.object(roxy_codex_oauth, "_is_login_password_page", side_effect=lambda _d: driver.current_url == target),
            patch.object(roxy_codex_oauth, "_is_email_verification_page", side_effect=lambda _d: driver.current_url.endswith("email-verification")),
            patch.object(roxy_codex_oauth, "_is_login_advanced", side_effect=lambda *_a: driver.current_url == "https://chatgpt.com/"),
            patch("core.registration.password_auth._resume_login_password_url", return_value=target if offered else None),
            patch.object(roxy_codex_oauth, "_submit_saved_login_password", side_effect=lambda *_a: setattr(driver, "current_url", "https://chatgpt.com/")) as submit,
            patch.object(roxy_codex_oauth, "time", SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0]+s))),
            patch.object(roxy_codex_oauth, "human_delay"),
        ):
            result = roxy_codex_oauth.complete_openai_login_challenge(
                driver, "unit@example.test", password, "", timeout=30,
                **({"password_already_submitted": True} if password_already_submitted else {}),
            )
        return result, driver, submit

    def test_saved_password_uses_offered_login_entry_before_waiting_for_email(self):
        result, driver, submit = self._resolve_offered_password()
        self.assertEqual(result, "advanced")
        driver.get.assert_called_once_with("https://auth.openai.com/log-in/password")
        submit.assert_called_once()

    def test_missing_password_or_unoffered_entry_keeps_email_otp_flow(self):
        for kwargs in ({"password": ""}, {"offered": False}):
            with self.subTest(kwargs=kwargs):
                result, driver, submit = self._resolve_offered_password(**kwargs)
                self.assertEqual(result, "email_otp")
                driver.get.assert_not_called()
                submit.assert_not_called()

    def test_offered_password_navigation_does_not_loop_when_page_stays_on_otp(self):
        result, driver, submit = self._resolve_offered_password(navigation_works=False)
        self.assertEqual(result, "email_otp")
        driver.get.assert_called_once()
        submit.assert_not_called()

    def test_registration_password_already_submitted_continues_otp_without_password_replay(self):
        result, driver, submit = self._resolve_offered_password(password_already_submitted=True)
        self.assertEqual(result, "email_otp")
        driver.get.assert_not_called()
        submit.assert_not_called()

    def test_offered_password_navigation_uses_remaining_parent_budget_and_restores_timeout(self):
        driver = MagicMock()
        driver.timeouts.page_load = 30
        now = [100.0]
        budget = StageBudget.start(2, clock=lambda: now[0])
        with execution_context(AuthExecutionContext(budget=budget)), \
             patch.object(roxy_codex_oauth.time, "time", side_effect=lambda: now[0]), \
             patch("core.registration.password_auth._resume_login_password_url", return_value="https://auth.openai.com/log-in/password"):
            self.assertTrue(roxy_codex_oauth._open_offered_saved_password(driver, 130))
        self.assertEqual([c.args[0] for c in driver.set_page_load_timeout.call_args_list], [2, 30])

    def test_post_refresh_totp_delay_cannot_outlive_original_budget(self):
        now = [100.0]
        budget = StageBudget.start(1, clock=lambda: now[0])

        def advance(seconds):
            now[0] += seconds

        def form_delay(_kind, *, budget=None):
            if budget is None:
                advance(5)
            else:
                budget.sleep(5, sleeper=advance)

        state = {"url": "https://auth.openai.com/mfa-challenge/test-factor", "inputs": [{"name": "totp"}], "text": "Authenticator"}
        fake_time = SimpleNamespace(time=lambda: now[0], sleep=advance)
        with execution_context(AuthExecutionContext(budget=budget)), patch.object(
            roxy_codex_oauth, "time", fake_time,
        ), patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state), patch.object(
            roxy_codex_oauth, "_submit_saved_login_totp",
        ) as submit, patch.object(roxy_codex_oauth, "human_delay", side_effect=form_delay):
            with self.assertRaises(StageTimeout):
                roxy_codex_oauth.complete_openai_login_challenge(MagicMock(), "account@example.test", "password", "secret")
        self.assertEqual(submit.call_count, 1)
        self.assertLessEqual(now[0], budget.deadline)

    def test_post_refresh_totp_inherits_the_original_stage_budget(self):
        budget = StageBudget.start(3)

        def resolve(*_args, **kwargs):
            context = current_execution_context()
            self.assertIsNotNone(context.budget)
            self.assertLessEqual(context.budget.deadline, budget.deadline)
            self.assertLessEqual(kwargs["timeout"], 3)
            return "advanced"

        with patch.object(roxy_codex_oauth, "complete_openai_login_challenge", side_effect=resolve):
            self.assertEqual(roxy_registration._complete_registration_totp_after_email_otp(
                MagicMock(), "account@example.test", "test-password", "test-totp-secret", budget=budget,
            ), "advanced")

    def test_login_resolver_checks_parent_budget_before_reading_or_submitting(self):
        now = [100.0]
        budget = StageBudget.start(1, clock=lambda: now[0])
        with execution_context(AuthExecutionContext(budget=budget)), patch.object(
            roxy_codex_oauth, "_login_challenge_state", return_value={"url": "https://auth.openai.com/about-you"},
        ) as snapshot, patch.object(roxy_codex_oauth, "_is_login_advanced", return_value=True):
            now[0] = 102.0
            with self.assertRaises(StageTimeout):
                roxy_codex_oauth.complete_openai_login_challenge(MagicMock(), "account@example.test", "password", "secret")
        snapshot.assert_not_called()

    def test_callback_log_path_drops_code_state_and_dynamic_challenge(self):
        self.assertEqual(
            "/auth/callback",
            roxy_codex_oauth._auth_path_for_log(
                "http://localhost:1455/auth/callback?code=private-code&state=private-state"
            ),
        )
        self.assertEqual(
            "/mfa-challenge/*",
            roxy_codex_oauth._auth_path_for_log(
                "https://auth.openai.com/mfa-challenge/private-factor?state=private-state"
            ),
        )
        self.assertEqual("-", roxy_codex_oauth._auth_path_for_log("https://other.example/private-code"))
        self.assertEqual("-", roxy_codex_oauth._auth_path_for_log("http://localhost:bad/auth/callback?code=private-code"))

    def test_performance_callback_log_does_not_include_code_or_state(self):
        callback = "http://localhost:1455/auth/callback?code=private-code&state=private-state"
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/sign-in-with-chatgpt/codex/consent"
        driver.execute_script.return_value = [callback]
        with patch.object(roxy_codex_oauth.logger, "info") as log_info:
            self.assertEqual(callback, roxy_codex_oauth._extract_callback_url_from_page(driver))
        logged = repr(log_info.call_args_list)
        self.assertNotIn("private-code", logged)
        self.assertNotIn("private-state", logged)

    def test_login_challenge_state_detects_structured_deactivation_error(self):
        state = {
            "url": "https://auth.openai.com/mfa-challenge/example",
            "errors": [
                "error_code: account_deactivated request_id: redacted",
            ],
        }

        self.assertEqual(
            "account_deactivated",
            roxy_codex_oauth._detect_account_unusable_login_state(state),
        )
        self.assertEqual(
            "",
            roxy_codex_oauth._detect_account_unusable_login_state({
                "url": "https://chatgpt.com/auth/login",
                "errors": ["error_code: account_deactivated"],
            }),
        )
        self.assertEqual(
            "",
            roxy_codex_oauth._detect_account_unusable_login_state({
                "url": "https://auth.openai.com/mfa-challenge/example",
                "errors": ["Your account has been deactivated"],
            }),
        )

    def test_login_challenge_raises_typed_error_before_generic_state_failure(self):
        state = {
            "url": "https://auth.openai.com/mfa-challenge/example",
            "inputs": [],
            "errors": ["error_code: account_deactivated request_id: redacted"],
        }
        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state),
        ):
            with self.assertRaises(roxy_codex_oauth.AccountUnusableError) as caught:
                roxy_codex_oauth._complete_login_challenge_after_email(
                    MagicMock(), "account@example.com", "password", "totp", timeout=5,
                )

        self.assertEqual("account_deactivated", caught.exception.error_code)

    def _totp_state(self):
        return {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Enter the code from your authenticator app",
            "inputs": [
                {"type": "text", "name": "totp", "autocomplete": "one-time-code"},
            ],
            "errors": [],
        }

    def test_codex_email_otp_wait_identifies_totp_before_accepting_non_email_url(self):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/log-in/password"
        state = self._totp_state()

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_read_email_otp_validate_dead_code", return_value=""),
            patch.object(roxy_codex_oauth, "_is_callback_url", return_value=False),
            patch.object(roxy_codex_oauth, "_has_strict_add_phone_form", return_value=False),
            patch.object(roxy_codex_oauth, "_is_phone_code_page", return_value=False),
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=True),
            patch.object(roxy_codex_oauth.time, "sleep"),
        ):
            result = roxy_codex_oauth._wait_after_email_otp_submit(driver, timeout=1)

        self.assertEqual("totp_required", result)

    def test_registration_email_otp_wait_identifies_totp_before_accepting_non_email_url(self):
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/log-in/password"
        state = self._totp_state()

        with (
            patch.object(roxy_registration, "_email_otp_page_state", return_value=state),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
        ):
            result = roxy_registration._wait_after_email_otp_submit(driver, timeout=1)

        self.assertEqual("totp_required", result)

    def test_codex_resolves_totp_after_email_otp_without_resending_email(self):
        driver = MagicMock()
        resolver = MagicMock(side_effect=["email_otp", "advanced"])

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "report_stage"),
            patch.object(roxy_codex_oauth, "human_delay"),
            patch.object(roxy_codex_oauth, "_maybe_accept"),
            patch.object(roxy_codex_oauth, "_select_existing_account_if_present", return_value=False),
            patch.object(roxy_codex_oauth, "_account_login_credentials", return_value=("", "totp-secret")),
            patch.object(roxy_codex_oauth, "_type_email_address"),
            patch.object(roxy_codex_oauth, "_submit_email_step"),
            patch.object(roxy_codex_oauth, "complete_openai_login_challenge", resolver),
            patch.object(roxy_codex_oauth, "_wait_for_fresh_email_otp", return_value="123456"),
            patch.object(roxy_codex_oauth, "_wait_for_otp_input"),
            patch.object(roxy_codex_oauth, "_clear_otp_inputs"),
            patch.object(roxy_codex_oauth, "_type_otp"),
            patch.object(roxy_codex_oauth, "_install_email_otp_validate_hook"),
            patch.object(roxy_codex_oauth, "_click_if_present", return_value=True),
            patch.object(roxy_codex_oauth, "_wait_after_email_otp_submit", return_value="totp_required"),
        ):
            result = roxy_codex_oauth._fill_email_and_otp(
                driver,
                "account@example.com",
                MagicMock(),
                "https://auth.openai.com/oauth/authorize",
            )

        self.assertIsNone(result)
        self.assertEqual(2, resolver.call_count)
        self.assertEqual("totp-secret", resolver.call_args_list[1].args[3])
        self.assertEqual("account@example.com", resolver.call_args_list[1].args[1])

    def test_registration_resolves_totp_after_email_otp_with_saved_credentials(self):
        driver = MagicMock()
        resolver = MagicMock(return_value="advanced")

        with patch.object(roxy_codex_oauth, "complete_openai_login_challenge", resolver):
            result = roxy_registration._complete_registration_totp_after_email_otp(
                driver,
                "account@example.com",
                "saved-password",
                "totp-secret",
            )

        self.assertEqual("advanced", result)
        resolver.assert_called_once_with(
            driver,
            "account@example.com",
            "saved-password",
            "totp-secret",
            timeout=45,
        )

    def test_registration_stops_after_email_otp_when_totp_credentials_are_missing(self):
        with self.assertRaisesRegex(RuntimeError, "缺少可用密码或 TOTP"):
            roxy_registration._complete_registration_totp_after_email_otp(
                MagicMock(),
                "account@example.com",
                "saved-password",
                "",
            )

    def test_explicit_password_error_is_not_treated_as_a_transient_page_error(self):
        state = {
            "text": "Incorrect password",
            "errors": ["The password is incorrect"],
            "inputs": [{"type": "password", "ariaInvalid": "true"}],
        }

        self.assertTrue(roxy_codex_oauth._is_explicit_password_rejection_state(state))

    def test_email_or_password_error_is_classified_as_explicit_rejection(self):
        self.assertTrue(
            roxy_codex_oauth._is_explicit_password_rejection_state(
                {"text": "Invalid email or password", "errors": []}
            )
        )

    def test_rejected_saved_password_can_enter_authorized_email_reset_flow(self):
        driver = MagicMock()
        password_page = {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Enter your password",
            "inputs": [{"type": "password", "name": "password"}],
            "errors": [],
        }
        rejected_page = {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Incorrect email address or password",
            "inputs": [{"type": "password", "name": "password", "ariaInvalid": "true"}],
            "errors": ["Incorrect email address or password"],
        }

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=[password_page, rejected_page]),
            patch.object(roxy_codex_oauth, "_is_browser_error_page_state", return_value=False),
            patch.object(roxy_codex_oauth, "_is_terminal_auth_error_page", return_value=False),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=True),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
            patch.object(roxy_codex_oauth, "_submit_saved_login_password"),
            patch.object(roxy_codex_oauth, "_reset_password_via_email", return_value=True) as reset_password,
            patch.object(roxy_codex_oauth, "human_delay"),
        ):
            result = roxy_codex_oauth._complete_login_challenge_after_email(
                driver,
                "account@example.com",
                "stale-password",
                "totp-secret",
                timeout=5,
                otp_provider=MagicMock(),
                allow_password_reset=True,
                on_password_reset_submitted=MagicMock(),
            )

        self.assertEqual("advanced", result)
        reset_password.assert_called_once()
        self.assertEqual("account@example.com", reset_password.call_args.args[1])

    def test_shared_password_rejection_respects_reset_authorization(self):
        password_page = {
            "url": "https://auth.openai.com/log-in/password",
            "text": "Enter your password",
            "inputs": [{"type": "password", "name": "password"}],
            "errors": [],
        }
        for allow_reset in (False, True):
            with self.subTest(allow_reset=allow_reset):
                driver = MagicMock()
                rejected = PasswordRejectedError("远端明确拒绝保存密码")
                submitted_checkpoint = MagicMock()
                confirmed_checkpoint = MagicMock()
                with (
                    patch.object(roxy_codex_oauth, "check_cancelled"),
                    patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=password_page),
                    patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=True),
                    patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
                    patch.object(roxy_codex_oauth, "_fill_password_page_if_present", side_effect=rejected) as shared,
                    patch.object(roxy_codex_oauth, "_reset_password_via_email", return_value=True) as reset,
                ):
                    kwargs = {
                        "otp_provider": MagicMock(), "allow_password_reset": allow_reset,
                        "on_password_reset_submitted": submitted_checkpoint,
                        "on_password_confirmed": confirmed_checkpoint,
                    }
                    if allow_reset:
                        self.assertEqual("advanced", roxy_codex_oauth._complete_login_challenge_after_email(
                            driver, "account@example.com", "saved-password", "saved-totp", **kwargs,
                        ))
                    else:
                        with self.assertRaises(PasswordRejectedError) as caught:
                            roxy_codex_oauth._complete_login_challenge_after_email(
                                driver, "account@example.com", "saved-password", "saved-totp", **kwargs,
                            )
                        self.assertIs(caught.exception, rejected)
                    shared.assert_called_once()
                    if allow_reset:
                        reset.assert_called_once()
                        self.assertIs(reset.call_args.kwargs["on_password_submitted"], submitted_checkpoint)
                        self.assertIs(reset.call_args.kwargs["on_password_confirmed"], confirmed_checkpoint)
                        self.assertEqual(reset.call_args.kwargs["totp_secret"], "saved-totp")
                    else:
                        reset.assert_not_called()
                    driver.refresh.assert_not_called()

    def test_missing_totp_is_a_typed_non_fallback_failure(self):
        with self.assertRaises(MfaSecretMissingError) as caught:
            roxy_codex_oauth._submit_saved_login_totp(
                MagicMock(),
                "account@example.com",
                "",
            )

        self.assertEqual("mfa_secret_missing", caught.exception.code)

    def test_browser_error_page_fails_login_challenge_without_waiting_for_timeout(self):
        state = {
            "url": "chrome-error://chromewebdata/",
            "inputs": [],
            "errors": ["无法访问此网站"],
        }

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state),
            patch.object(roxy_codex_oauth.time, "time", side_effect=[0.0, 1.0]),
            patch.object(roxy_codex_oauth.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "浏览器导航失败"):
                roxy_codex_oauth._complete_login_challenge_after_email(
                    MagicMock(),
                    "account@example.com",
                    "",
                    "",
                    timeout=45,
                )

    def test_empty_mfa_state_after_totp_gets_one_bounded_refresh(self):
        driver = MagicMock()
        driver.step = "totp"
        refreshes = []

        def refresh():
            refreshes.append(driver.step)
            driver.step = "advanced"

        driver.refresh.side_effect = refresh
        clock = [100.0]

        def state(_driver):
            if driver.step == "totp":
                return {
                    "url": "https://auth.openai.com/mfa-challenge/redacted",
                    "inputs": [{"type": "text", "autocomplete": "one-time-code"}],
                    "errors": [],
                }
            if driver.step == "empty_mfa":
                return {
                    "url": "https://auth.openai.com/mfa-challenge/redacted",
                    "inputs": [],
                    "errors": [],
                }
            return {"url": "https://chatgpt.com/", "inputs": [], "errors": []}

        def submit_totp(_driver, _email, _secret):
            driver.step = "empty_mfa"

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=state),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=False),
            patch.object(roxy_codex_oauth, "_is_email_verification_page", return_value=False),
            patch.object(
                roxy_codex_oauth,
                "_is_totp_login_page",
                side_effect=lambda _driver, _state=None: driver.step == "totp",
            ),
            patch.object(
                roxy_codex_oauth,
                "_is_login_advanced",
                side_effect=lambda _driver, _state=None: driver.step == "advanced",
            ),
            patch.object(roxy_codex_oauth, "_submit_saved_login_totp", side_effect=submit_totp),
            patch.object(roxy_codex_oauth.time, "time", side_effect=lambda: clock[0]),
            patch.object(
                roxy_codex_oauth.time,
                "sleep",
                side_effect=lambda seconds: clock.__setitem__(0, clock[0] + max(0.5, seconds)),
            ),
            patch.object(roxy_codex_oauth, "human_delay"),
        ):
            result = roxy_codex_oauth._complete_login_challenge_after_email(
                driver, "account@example.com", "", "totp-secret", timeout=10
            )

        self.assertEqual("advanced", result)
        self.assertEqual(["empty_mfa"], refreshes)

    def test_initial_empty_mfa_state_gets_one_bounded_refresh_before_totp(self):
        driver = MagicMock()
        driver.step = "empty_mfa"
        refreshes = []

        def refresh():
            refreshes.append(driver.step)
            driver.step = "totp"

        driver.refresh.side_effect = refresh
        clock = [100.0]

        def state(_driver):
            if driver.step == "empty_mfa":
                return {
                    "url": "https://auth.openai.com/mfa-challenge/redacted",
                    "inputs": [],
                    "errors": [],
                }
            if driver.step == "totp":
                return {
                    "url": "https://auth.openai.com/mfa-challenge/redacted",
                    "inputs": [{"type": "text", "autocomplete": "one-time-code"}],
                    "errors": [],
                }
            return {"url": "https://chatgpt.com/", "inputs": [], "errors": []}

        def submit_totp(_driver, _email, _secret):
            driver.step = "advanced"

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=state),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=False),
            patch.object(roxy_codex_oauth, "_is_email_verification_page", return_value=False),
            patch.object(
                roxy_codex_oauth,
                "_is_totp_login_page",
                side_effect=lambda _driver, _state=None: driver.step == "totp",
            ),
            patch.object(
                roxy_codex_oauth,
                "_is_login_advanced",
                side_effect=lambda _driver, _state=None: driver.step == "advanced",
            ),
            patch.object(roxy_codex_oauth, "_submit_saved_login_totp", side_effect=submit_totp) as submit,
            patch.object(roxy_codex_oauth.time, "time", side_effect=lambda: clock[0]),
            patch.object(
                roxy_codex_oauth.time,
                "sleep",
                side_effect=lambda seconds: clock.__setitem__(0, clock[0] + max(0.5, seconds)),
            ),
            patch.object(roxy_codex_oauth, "human_delay"),
        ):
            result = roxy_codex_oauth._complete_login_challenge_after_email(
                driver, "account@example.com", "", "totp-secret", timeout=10
            )

        self.assertEqual("advanced", result)
        self.assertEqual(["empty_mfa"], refreshes)
        submit.assert_called_once_with(driver, "account@example.com", "totp-secret")

    def test_shared_password_timeout_refreshes_and_retries_saved_password_once(self):
        driver = MagicMock()
        driver.step = "password"
        password_state = {
            "url": "https://auth.openai.com/log-in/password",
            "inputs": [{"type": "password", "autocomplete": "current-password"}],
            "errors": [],
        }
        advanced_state = {"url": "https://chatgpt.com/", "inputs": [], "errors": []}
        first_receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
        first_receipt.transition("unknown", result="unknown")
        second_receipt = BrowserSubmissionReceipt(kind="resume_login", stage="login_password")
        driver._browser_submission_receipt = first_receipt
        submit_count = [0]

        def submit_password(*_args, **_kwargs):
            submit_count[0] += 1
            if submit_count[0] == 1:
                raise _PasswordTransitionTimeout("request_unknown: 密码提交结果未知")
            driver.step = "advanced"
            second_receipt.transition("confirmed", result="success")
            driver._browser_submission_receipt = second_receipt

        def state(_driver):
            return password_state if driver.step == "password" else advanced_state

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=state),
            patch.object(
                roxy_codex_oauth, "_is_login_password_page",
                side_effect=lambda _driver: driver.step == "password",
            ),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
            patch.object(
                roxy_codex_oauth, "_is_login_advanced",
                side_effect=lambda _driver, _state=None: driver.step == "advanced",
            ),
            patch.object(
                roxy_codex_oauth, "_fill_password_page_if_present", side_effect=submit_password,
            ) as shared,
            patch.object(roxy_codex_oauth, "_refresh_auth_challenge_after_submit") as refresh,
            patch.object(roxy_codex_oauth, "_reset_password_via_email") as reset,
            patch.object(roxy_codex_oauth, "human_delay"),
        ):
            result = roxy_codex_oauth._complete_login_challenge_after_email(
                driver, "account@example.com", "saved-password", "", timeout=30,
                allow_password_reset=True, otp_provider=MagicMock(),
            )

        self.assertEqual("advanced", result)
        self.assertEqual(2, submit_count[0])
        shared.assert_called()
        self.assertEqual(2, shared.call_count)
        refresh.assert_called_once_with(driver, "登录密码")
        reset.assert_not_called()
        self.assertEqual("confirmed", first_receipt.phase)

    def test_shared_password_timeout_does_not_retry_twice(self):
        driver = MagicMock()
        password_state = {
            "url": "https://auth.openai.com/log-in/password",
            "inputs": [{"type": "password", "autocomplete": "current-password"}],
            "errors": [],
        }
        error = _PasswordTransitionTimeout("request_unknown: 密码提交结果未知")

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=password_state),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=True),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
            patch.object(roxy_codex_oauth, "_fill_password_page_if_present", side_effect=error) as shared,
            patch.object(roxy_codex_oauth, "_refresh_auth_challenge_after_submit") as refresh,
            patch.object(roxy_codex_oauth, "_reset_password_via_email") as reset,
        ):
            with self.assertRaises(_PasswordTransitionTimeout) as caught:
                roxy_codex_oauth._complete_login_challenge_after_email(
                    driver, "account@example.com", "saved-password", "", timeout=30,
                    allow_password_reset=True, otp_provider=MagicMock(),
                )

        self.assertIs(caught.exception, error)
        self.assertEqual(2, shared.call_count)
        refresh.assert_called_once_with(driver, "登录密码")
        reset.assert_not_called()

    def test_shared_password_timeout_honors_explicit_rejection_after_refresh(self):
        driver = MagicMock()
        driver._browser_submission_receipt = BrowserSubmissionReceipt(
            kind="resume_login", stage="login_password",
        )
        driver._browser_submission_receipt.transition("unknown", result="unknown")
        password_state = {
            "url": "https://auth.openai.com/log-in/password",
            "inputs": [{"type": "password", "autocomplete": "current-password"}],
            "errors": [],
        }
        rejected_state = {
            **password_state,
            "errors": ["Incorrect password"],
        }
        error = _PasswordTransitionTimeout("request_unknown: 密码提交结果未知")
        states = iter((password_state, password_state, rejected_state))

        with (
            patch.object(roxy_codex_oauth, "check_cancelled"),
            patch.object(roxy_codex_oauth, "_login_challenge_state", side_effect=lambda _driver: next(states)),
            patch.object(roxy_codex_oauth, "_is_login_password_page", return_value=True),
            patch.object(roxy_codex_oauth, "_is_totp_login_page", return_value=False),
            patch.object(roxy_codex_oauth, "_fill_password_page_if_present", side_effect=error) as shared,
            patch.object(roxy_codex_oauth, "_refresh_auth_challenge_after_submit") as refresh,
            patch.object(roxy_codex_oauth, "_reset_password_via_email", return_value=True) as reset,
        ):
            result = roxy_codex_oauth._complete_login_challenge_after_email(
                driver, "account@example.com", "saved-password", "", timeout=30,
                allow_password_reset=True, otp_provider=MagicMock(),
            )

        self.assertEqual("advanced", result)
        shared.assert_called_once()
        refresh.assert_called_once_with(driver, "登录密码")
        reset.assert_called_once()
        self.assertEqual("rejected", driver._browser_submission_receipt.phase)

    def test_liveness_email_shell_can_use_nextauth_fallback_before_typing(self):
        driver = MagicMock()
        with (
            patch.object(roxy_liveness, "_page_account_unusable_code", return_value=""),
            patch.object(
                roxy_liveness,
                "_type_email_address",
                side_effect=RuntimeError("找不到邮箱输入框/邮箱入口，state={...}"),
            ),
            patch.object(
                roxy_liveness,
                "_submit_email_via_browser_nextauth",
                return_value={"ok": True, "stage": "auth_landed", "state": "login_password"},
            ) as nextauth,
            patch.object(roxy_liveness, "_has_access_token", return_value=False),
            patch.object(roxy_liveness, "_is_login_password_page", return_value=True),
            patch(
                "core.roxy_codex_oauth.complete_openai_login_challenge",
                return_value="advanced",
            ) as complete,
        ):
            result = roxy_liveness._enter_existing_account_otp(
                driver,
                "account@example.com",
                password="saved-password",
                totp_secret="totp-secret",
            )

        self.assertEqual("logged_in", result)
        nextauth.assert_called_once_with(driver, "account@example.com")
        complete.assert_called_once_with(
            driver,
            "account@example.com",
            "saved-password",
            "totp-secret",
            timeout=45,
        )


if __name__ == "__main__":
    unittest.main()
