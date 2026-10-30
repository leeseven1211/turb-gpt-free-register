"""慢加载登录表单的等待、首次提交和取消回归。"""
import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.auth.browser import email_otp
from core.auth.browser.auth_context import AuthExecutionContext, execution_context
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import CancellationRequested, StageBudget, StageTimeout


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


@contextmanager
def _email_flow(clock, driver):
    """替换网络和 DOM 边界，保留实际等待、提交步骤和阶段预算。"""
    with ExitStack() as stack:
        stack.enter_context(patch.object(email_otp, "time", clock))
        stack.enter_context(patch.object(
            email_otp.StageBudget, "start",
            side_effect=lambda timeout: StageBudget(clock.now + timeout, clock=clock.time),
        ))
        stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="email"))
        stack.enter_context(patch.object(email_otp, "_email_input_value_state", return_value={
            "inputs": [{"value": "unit@example.test"}],
        }))
        stack.enter_context(patch.object(email_otp, "human_delay"))
        stack.enter_context(patch.object(email_otp, "_browser_actions_enabled", return_value=False))
        stack.enter_context(patch.object(email_otp, "_stabilize_email_input_before_submit", return_value={"ok": True}))
        stack.enter_context(patch.object(email_otp, "_assert_not_external_idp"))
        stack.enter_context(patch.object(email_otp, "_email_submit_advanced_state", return_value=None))
        stack.enter_context(patch.object(email_otp, "_is_blank_chatgpt_auth_shell", return_value=False))
        yield stack


class EmailFrontendLoadingTests(unittest.TestCase):
    def test_login_with_native_redirect_waits_within_existing_preparation_budget_before_single_submit(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login_with?callback_path=/")
        real_type_email = email_otp._type_email_address
        email_input = object()

        def visible_email_input(_driver):
            if clock.now >= 51:
                driver.current_url = "https://auth.openai.com/log-in"
                return email_input
            return None

        with _email_flow(clock, driver) as stack:
            typed = stack.enter_context(patch.object(email_otp, "_type_email_address", side_effect=real_type_email))
            stack.enter_context(patch.object(email_otp, "_find_visible_email_input_js", side_effect=visible_email_input))
            stack.enter_context(patch.object(email_otp, "_human_type_text"))
            stack.enter_context(patch.object(email_otp, "_email_entry_state", return_value={"inputs": [], "actions": []}))
            stack.enter_context(patch.object(email_otp, "_click_email_entry_option", return_value=False))
            refresh = stack.enter_context(patch.object(email_otp, "_reload_blank_chatgpt_auth_shell"))
            submit = stack.enter_context(patch.object(email_otp, "_submit_email_step"))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            self.assertEqual(email_otp._submit_email_and_wait_next(
                driver, "unit@example.test", attempts=1, allow_login_password=True,
            ), "otp")
        typed.assert_called_once()
        self.assertEqual(typed.call_args.kwargs["timeout"], email_otp.EMAIL_PREPARATION_TIMEOUT)
        self.assertGreaterEqual(clock.now, 51)
        self.assertLess(clock.now, 52)
        submit.assert_called_once()
        fallback.assert_not_called()
        refresh.assert_not_called()

    def test_login_with_wait_does_not_extend_outer_budget_or_send_fallback(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login_with?callback_path=/")

        def wait_until_deadline(_driver, _email, *, timeout, stop_on_advanced):
            clock.sleep(timeout)
            raise RuntimeError("找不到邮箱输入框/邮箱入口（原生登录跳转仍在进行）")

        with _email_flow(clock, driver) as stack:
            stack.enter_context(patch.object(email_otp, "_type_email_address", side_effect=wait_until_deadline))
            submit = stack.enter_context(patch.object(email_otp, "_submit_email_step"))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(
                    driver, "unit@example.test", attempts=1, allow_login_password=True, total_timeout=30,
                )
        self.assertEqual(clock.now, 30)
        submit.assert_not_called()
        fallback.assert_not_called()

    def test_native_redirect_wait_is_not_enabled_for_ordinary_or_untrusted_entries(self):
        for entry, allow_login in (
            ("https://chatgpt.com/auth/login", True),
            ("https://chatgpt.com/auth/login_with?callback_path=/", False),
            ("https://user@chatgpt.com/auth/login_with?callback_path=/", True),
            ("https://chatgpt.com:8443/auth/login_with?callback_path=/", True),
            ("https://chatgpt.com.evil.test/auth/login_with?callback_path=/", True),
            ("https://chatgpt.com/auth/login_with_other?callback_path=/", True),
        ):
            with self.subTest(entry=entry, allow_login=allow_login):
                clock = _Clock()
                driver = SimpleNamespace(current_url=entry)
                with _email_flow(clock, driver) as stack:
                    typed = stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="otp"))
                    self.assertEqual(email_otp._submit_email_and_wait_next(
                        driver, "unit@example.test", attempts=1, allow_login_password=allow_login,
                    ), "otp")
                self.assertEqual(typed.call_args.kwargs["timeout"], 20)

    def test_slow_frontend_keeps_full_submission_budget_after_extended_wait(self):
        clock = _Clock()
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/auth/login",
            execute_script=Mock(side_effect=lambda *_args: clock.now >= 179),
        )
        submission_window = []

        def submit_form(current_driver, _email):
            submission_window.append(current_driver._registration_stage_budget.remaining())
            return {"ok": True}

        with _email_flow(clock, driver) as stack:
            stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=None))
            stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", side_effect=submit_form))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            stack.enter_context(patch.object(
                email_otp, "_submit_email_via_browser_nextauth",
                return_value={"ok": False, "not_dispatched": True},
            ))
            result = email_otp._submit_email_and_wait_next(driver, "unit@example.test", attempts=1)

        self.assertEqual(result, "otp")
        self.assertEqual(len(submission_window), 1)
        self.assertGreaterEqual(submission_window[0], 59.5)

    def test_undispatched_nextauth_fallback_gets_fresh_budget_within_outer_deadline(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
        submit_calls = []
        fallback_deadlines = []

        def submit_step(current_driver, _email):
            submit_calls.append(clock.now)
            current_driver._registration_before_email_dispatch()
            clock.sleep(61)

        def nextauth_fallback(current_driver, _email):
            fallback_deadlines.append(current_driver._registration_stage_budget.deadline)
            return {"ok": True, "state": "otp"}

        with _email_flow(clock, driver) as stack:
            stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=submit_step))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="email_page"))
            stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value=None))
            fallback = stack.enter_context(patch.object(
                email_otp, "_submit_email_via_browser_nextauth", side_effect=nextauth_fallback,
            ))
            result = email_otp._submit_email_and_wait_next(driver, "unit@example.test", attempts=1)

        self.assertEqual(result, "otp")
        self.assertEqual(submit_calls, [0.0])
        self.assertEqual(fallback_deadlines, [121.0])
        fallback.assert_called_once_with(driver, "unit@example.test")

    def test_default_wait_uses_current_preparation_budget_for_slow_handler(self):
        clock = _Clock()
        driver = SimpleNamespace(
            execute_script=Mock(side_effect=lambda *_args: clock.now >= 92),
            _registration_stage_budget=StageBudget(120, clock=clock.time),
        )
        with patch.object(email_otp, "time", clock):
            email_otp._wait_email_frontend_ready(driver)
        self.assertEqual(clock.now, 92)

    def test_unready_form_stops_at_current_preparation_deadline(self):
        clock = _Clock()
        driver = SimpleNamespace(
            execute_script=Mock(return_value=False),
            _registration_stage_budget=StageBudget(120, clock=clock.time),
        )
        with patch.object(email_otp, "time", clock):
            with self.assertRaises(email_otp._EmailFrontendNotReady):
                email_otp._wait_email_frontend_ready(driver)
        self.assertEqual(clock.now, 120)
        self.assertEqual(driver._registration_stage_budget.deadline, 120)

    def test_without_stage_budget_wait_keeps_legacy_hard_limit(self):
        clock = _Clock()
        driver = SimpleNamespace(execute_script=Mock(return_value=False))
        with patch.object(email_otp, "time", clock):
            with self.assertRaises(email_otp._EmailFrontendNotReady):
                email_otp._wait_email_frontend_ready(driver)
        self.assertEqual(clock.now, 30)

    def test_explicit_timeout_cannot_extend_or_replace_shared_deadline(self):
        for remaining, timeout, expected in ((120, 0.5, 0.5), (0.5, 120, 0.5)):
            with self.subTest(remaining=remaining, timeout=timeout):
                clock = _Clock()
                driver = SimpleNamespace(
                    execute_script=Mock(return_value=False),
                    _registration_stage_budget=StageBudget(remaining, clock=clock.time),
                )
                with patch.object(email_otp, "time", clock):
                    with self.assertRaises(email_otp._EmailFrontendNotReady):
                        email_otp._wait_email_frontend_ready(driver, timeout=timeout)
                self.assertEqual(clock.now, expected)
                self.assertEqual(driver._registration_stage_budget.deadline, remaining)

    def test_slow_frontend_reports_progress_then_executes_first_click_once(self):
        clock = _Clock()
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/auth/login",
            execute_script=Mock(side_effect=lambda *_args: clock.now >= 92),
        )
        progress = []
        clicked_at = []

        def submit(*_args):
            clicked_at.append(clock.now)
            self.assertLessEqual(driver._registration_stage_budget.remaining(), 60)
            return {"ok": True}

        with _email_flow(clock, driver) as stack:
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", side_effect=submit))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", return_value={
                "ok": False, "stage": "csrf", "error_type": "csrf_http",
            }))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            self.assertEqual(email_otp._submit_email_and_wait_next(
                driver, "unit@example.test", on_progress=lambda phase, detail: progress.append((clock.now, phase, detail)),
            ), "otp")
        stable.assert_called_once_with(driver, "unit@example.test")
        fallback.assert_not_called()
        self.assertGreaterEqual(clicked_at[0], 92)
        self.assertLess(clock.now, 120)
        waiting = [when for when, phase, _detail in progress if phase == "waiting_frontend"]
        self.assertGreaterEqual(len(waiting), 9)
        self.assertTrue(all(9.5 <= newer - older <= 10.5 for older, newer in zip(waiting, waiting[1:])))
        self.assertIn("frontend_ready", [phase for _when, phase, _detail in progress])
        self.assertFalse(hasattr(driver, "_registration_email_progress"))

    def test_readonly_csrf_failure_can_wait_then_execute_first_ui_click(self):
        clock = _Clock()
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/auth/login",
            execute_script=Mock(side_effect=lambda *_args: clock.now >= 40),
        )
        original_submit = email_otp._submit_email_step
        submit_attempts = []
        submit_budgets = []

        def submit_step(*args):
            submit_attempts.append(clock.now)
            submit_budgets.append(driver._registration_stage_budget)
            if len(submit_attempts) == 1:
                # 表单接管竞态发生在真正点击之前，没有 UI 提交回执。
                clock.sleep(10)
                raise email_otp._EmailFrontendNotReady("email_frontend_not_ready")
            return original_submit(*args)

        def csrf_failure(*_args):
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="email", stage="nextauth", endpoint_kind="nextauth_signin", http_method="POST",
            )
            clock.sleep(25)
            return {"ok": False, "stage": "csrf", "status": 503, "error_type": "csrf_http", "not_dispatched": True}

        with _email_flow(clock, driver) as stack:
            step = stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=submit_step))
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", return_value={"ok": True}))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", side_effect=csrf_failure))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            self.assertEqual(email_otp._submit_email_and_wait_next(driver, "unit@example.test"), "otp")
        self.assertEqual(step.call_count, 2)
        stable.assert_called_once_with(driver, "unit@example.test")
        fallback.assert_called_once_with(driver, "unit@example.test")
        self.assertGreaterEqual(clock.now, 40)
        self.assertLess(clock.now, 70)
        self.assertEqual(submit_budgets[-1].deadline, 70)
        self.assertFalse(hasattr(driver, "_registration_stage_budget"))

    def test_dispatched_ui_is_observed_without_reclick_or_nextauth(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=True))

        def submit(*_args):
            driver._email_submission_receipt = {"id": "same-submit"}
            return {"ok": True}

        with _email_flow(clock, driver) as stack:
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", side_effect=submit))
            stack.enter_context(patch.object(email_otp, "_email_ui_submission_state", return_value="dispatched"))
            stack.enter_context(patch.object(
                email_otp, "_email_submit_advanced_state",
                side_effect=lambda *_args, **_kwargs: "otp" if clock.now >= 45 else None,
            ))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
            recovery = stack.enter_context(patch.object(email_otp, "_recover_email_submit_if_stuck"))
            self.assertEqual(email_otp._submit_email_and_wait_next(driver, "unit@example.test"), "otp")
        stable.assert_called_once_with(driver, "unit@example.test")
        fallback.assert_not_called()
        recovery.assert_not_called()
        self.assertGreaterEqual(clock.now, 45)
        self.assertLess(clock.now, 46)

    def test_csrf_no_dispatch_marker_never_overrides_pending_ui_or_auth_request(self):
        pending_states = [(phase, None) for phase in ("queued", "dispatched", "unknown")]
        pending_states.extend((None, phase) for phase in (
            "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown",
        ))
        for ui_phase, receipt_phase in pending_states:
            with self.subTest(ui_phase=ui_phase, receipt_phase=receipt_phase):
                clock = _Clock()
                driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=True))

                def csrf_failure(*_args):
                    driver._test_ui_phase = ui_phase
                    if receipt_phase is not None:
                        driver._browser_submission_receipt = BrowserSubmissionReceipt(
                            kind="email", stage="nextauth", phase=receipt_phase,
                        )
                    return {"ok": False, "stage": "csrf", "not_dispatched": True}

                with _email_flow(clock, driver) as stack:
                    step = stack.enter_context(patch.object(
                        email_otp, "_submit_email_step", side_effect=email_otp._EmailFrontendNotReady("email_frontend_not_ready"),
                    ))
                    stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable"))
                    stack.enter_context(patch.object(
                        email_otp, "_email_ui_submission_state", side_effect=lambda _: getattr(driver, "_test_ui_phase", None),
                    ))
                    fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", side_effect=csrf_failure))
                    with self.assertRaises(RuntimeError):
                        email_otp._submit_email_and_wait_next(driver, "unit@example.test")
                step.assert_called_once_with(driver, "unit@example.test")
                stable.assert_not_called()
                fallback.assert_called_once_with(driver, "unit@example.test")

    def test_fallback_failure_without_explicit_no_dispatch_cannot_retry_ui(self):
        for fallback_result in (
            {"ok": False, "stage": "signin", "status": 503},
            {"ok": False, "stage": "csrf", "status": 503},
            {"ok": False, "stage": "csrf", "not_dispatched": False},
        ):
            with self.subTest(fallback_result=fallback_result):
                clock = _Clock()
                driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=True))
                with _email_flow(clock, driver) as stack:
                    step = stack.enter_context(patch.object(
                        email_otp, "_submit_email_step", side_effect=email_otp._EmailFrontendNotReady("email_frontend_not_ready"),
                    ))
                    stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable"))
                    fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", return_value=fallback_result))
                    with self.assertRaises(RuntimeError):
                        email_otp._submit_email_and_wait_next(driver, "unit@example.test")
                step.assert_called_once_with(driver, "unit@example.test")
                stable.assert_not_called()
                fallback.assert_called_once_with(driver, "unit@example.test")

    def test_failed_csrf_and_unready_frontend_respect_smaller_outer_budget(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=False))
        original_submit = email_otp._submit_email_step
        submit_attempts = []
        submit_budgets = []

        def submit_step(*args):
            submit_attempts.append(clock.now)
            submit_budgets.append(driver._registration_stage_budget)
            if len(submit_attempts) == 1:
                clock.sleep(10)
                raise email_otp._EmailFrontendNotReady("email_frontend_not_ready")
            return original_submit(*args)

        def csrf_failure(*_args):
            clock.sleep(25)
            return {"ok": False, "stage": "csrf", "status": 503, "error_type": "csrf_http", "not_dispatched": True}

        with _email_flow(clock, driver) as stack:
            stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=submit_step))
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable"))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", side_effect=csrf_failure))
            with self.assertRaises(RuntimeError):
                email_otp._submit_email_and_wait_next(driver, "unit@example.test", total_timeout=55)
        self.assertEqual(clock.now, 55)
        stable.assert_not_called()
        fallback.assert_called_once_with(driver, "unit@example.test")
        self.assertEqual(submit_budgets[-1].deadline, 55)
        self.assertFalse(hasattr(driver, "_registration_stage_budget"))

    def test_frontend_ready_just_before_deadline_does_not_dispatch_after_pause(self):
        clock = _Clock()
        ready_at = []

        def frontend_probe(*_args):
            if clock.now < 69.75:
                return False
            # 本次 DOM 探测结束时仅剩 0.1 秒，提交前停顿会耗尽预算。
            clock.now = 69.9
            ready_at.append(clock.now)
            return True

        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(side_effect=frontend_probe))
        original_submit = email_otp._submit_email_step
        submit_attempts = []
        submit_budgets = []

        def submit_step(*args):
            submit_attempts.append(clock.now)
            submit_budgets.append(driver._registration_stage_budget)
            if len(submit_attempts) == 1:
                clock.sleep(10)
                raise email_otp._EmailFrontendNotReady("email_frontend_not_ready")
            return original_submit(*args)

        def csrf_failure(*_args):
            driver._browser_submission_receipt = BrowserSubmissionReceipt(kind="email", stage="nextauth")
            clock.sleep(25)
            return {"ok": False, "stage": "csrf", "not_dispatched": True}

        with _email_flow(clock, driver) as stack:
            step = stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=submit_step))
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", return_value={"ok": True}))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", side_effect=csrf_failure))
            observed = stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(driver, "unit@example.test")
        self.assertEqual(step.call_count, 2)
        self.assertEqual(ready_at, [69.9])
        self.assertAlmostEqual(clock.now, 70.3)
        self.assertEqual(submit_budgets[-1].deadline, 70)
        self.assertFalse(hasattr(driver, "_registration_stage_budget"))
        stable.assert_not_called()
        observed.assert_not_called()
        fallback.assert_called_once_with(driver, "unit@example.test")
        self.assertIsNone(driver._email_submission_receipt)

    def test_cancellation_interrupts_slow_frontend_and_restores_progress_callback(self):
        clock = _Clock()
        original_progress = Mock()
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=False),
            _registration_email_progress=original_progress,
        )
        context = AuthExecutionContext(cancellation=lambda: clock.now >= 2)
        with _email_flow(clock, driver) as stack:
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable"))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
            with execution_context(context):
                with self.assertRaises(CancellationRequested):
                    email_otp._submit_email_and_wait_next(driver, "unit@example.test", on_progress=Mock())
        self.assertEqual(clock.now, 2)
        stable.assert_not_called()
        fallback.assert_not_called()
        self.assertIs(driver._registration_email_progress, original_progress)
        original_progress.assert_not_called()
