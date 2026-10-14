"""邮箱验证码页只读识别、单次刷新及原提交围栏的回归测试。"""
from copy import deepcopy
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from selenium.common.exceptions import TimeoutException

from core.registration import email_otp, roxy
from core.registration.browser_submission import BrowserSubmissionReceipt
from core.registration.state_machine import StageBudget
from core.cloakbrowser_driver import CloakSeleniumDriver


_OTP_URL = "https://auth.openai.com/email-verification"


def _blank_state():
    return {"url": _OTP_URL, "title": "OpenAI", "text": "", "inputs": [], "buttons": [], "errors": []}


def _form_state():
    return {
        "url": _OTP_URL, "title": "OpenAI", "text": "Enter the verification code",
        "inputs": [{"type": "text", "name": "code", "autocomplete": "one-time-code"}],
        "buttons": [{"text": "Continue", "type": "submit", "disabled": False}], "errors": [],
    }


def _route_error_state():
    # 使用现场出现的结构：错误在正文，errors 数组为空。
    return {
        "url": _OTP_URL, "title": "OpenAI", "inputs": [], "errors": [],
        "text": "Route Error (400 Invalid content type: text/html; charset=UTF-8)",
        "buttons": [{"text": "Try again", "disabled": False}],
    }


class _FakeClock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.001, float(seconds))


class _FakeDriver:
    def __init__(self, state, *, refreshed_state=None, refresh_error=None):
        self.state = deepcopy(state)
        self.current_url = self.state["url"]
        self.refreshed_state = deepcopy(refreshed_state) if refreshed_state is not None else None
        self.refresh_error = refresh_error
        self.refresh_count = 0

    def execute_script(self, *_args):
        return deepcopy(self.state)

    def refresh(self):
        self.refresh_count += 1
        if self.refresh_error is not None:
            raise self.refresh_error
        if self.refreshed_state is not None:
            self.state = deepcopy(self.refreshed_state)
            self.current_url = self.state["url"]


class EmailOtpPageRecoveryTests(unittest.TestCase):
    def test_cloak_driver_refresh_is_bounded_and_restores_its_navigation_timeout(self):
        page = Mock()
        page.url = _OTP_URL
        driver = CloakSeleniumDriver(Mock(), None, page)
        driver.set_page_load_timeout(30)
        with patch.object(email_otp, "_email_otp_page_state", return_value=_route_error_state()):
            self.assertTrue(self._recover(driver, state=_route_error_state(), budget=self._budget(7.5)))
        page.reload.assert_called_once()
        self.assertGreater(page.reload.call_args.kwargs["timeout"], 0)
        self.assertLessEqual(page.reload.call_args.kwargs["timeout"], 7500)
        self.assertEqual(driver._page_load_timeout_ms, 30000)

    def setUp(self):
        self.clock = _FakeClock()
        self.time_patch = patch.object(email_otp, "time", self.clock)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.stop_patch = patch.object(email_otp, "_check_manual_stop")
        self.stop_patch.start()
        self.addCleanup(self.stop_patch.stop)
        self.token_patch = patch.object(email_otp, "_has_access_token", return_value=False)
        self.token_patch.start()
        self.addCleanup(self.token_patch.stop)

    def _helper(self, name):
        helper = getattr(email_otp, name, None)
        self.assertTrue(callable(helper), f"缺少邮箱验证码页恢复 helper: {name}")
        return helper

    def _reason(self, state):
        return self._helper("_email_otp_page_recovery_reason")(state)

    def _recover(self, driver, state=None, *, budget=None):
        return self._helper("_recover_email_otp_page_if_needed")(driver, state=state, budget=budget)

    def _wait_ready(self, driver, timeout=15, *, budget=None):
        return self._helper("_wait_email_otp_page_ready")(driver, timeout=timeout, budget=budget)

    def _budget(self, seconds):
        return StageBudget.start(seconds, clock=self.clock.monotonic)

    def _wait_after_submit(self, driver, timeout=4, *, budget=None):
        return email_otp._wait_after_email_otp_submit(driver, timeout=timeout, budget=budget)

    def test_normal_otp_form_is_ready_without_refresh(self):
        driver = _FakeDriver(_form_state())
        self.assertEqual(self._reason(driver.state), "")
        self.assertFalse(self._recover(driver, state=driver.state, budget=self._budget(15)))
        self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "ready")
        self.assertEqual(driver.refresh_count, 0)

    def test_blank_shell_must_persist_three_seconds_before_one_refresh(self):
        driver = _FakeDriver(_blank_state(), refreshed_state=_form_state())
        budget = self._budget(15)
        self.assertIsInstance(self._reason(driver.state), str)
        self.assertTrue(self._reason(driver.state))
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.clock.now += 2.9
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 0)
        self.clock.now += 0.2
        self.assertTrue(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 1)
        self.assertFalse(self._recover(driver, state=_route_error_state(), budget=budget))
        self.assertEqual(driver.refresh_count, 1)
        self.assertEqual(self._wait_ready(driver, budget=budget), "ready")

    def test_wait_ready_recovers_persistent_blank_shell_with_original_budget(self):
        driver = _FakeDriver(_blank_state(), refreshed_state=_form_state())
        budget = self._budget(8)
        deadline = budget.deadline
        self.assertEqual(self._wait_ready(driver, timeout=15, budget=budget), "ready")
        self.assertEqual(driver.refresh_count, 1)
        self.assertGreaterEqual(self.clock.now, 103.0)
        self.assertEqual(budget.deadline, deadline)
        self.assertLessEqual(self.clock.now, deadline)

    def test_actual_route_error_snapshot_refreshes_without_blank_grace(self):
        driver = _FakeDriver(_route_error_state(), refreshed_state=_form_state())
        self.assertTrue(self._reason(driver.state))
        self.assertTrue(self._recover(driver, state=driver.state, budget=self._budget(15)))
        self.assertEqual(driver.refresh_count, 1)
        self.assertLess(self.clock.now, 103.0)
        self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "ready")

    def test_refresh_keeps_the_original_submitted_or_unknown_receipt_unchanged(self):
        for phase in ("request_observed", "unknown"):
            with self.subTest(phase=phase):
                driver = _FakeDriver(_route_error_state(), refreshed_state=_form_state())
                receipt = BrowserSubmissionReceipt(
                    kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase=phase,
                    result="unknown", submission_id="test-original-otp-submission", started_at=90.0,
                )
                driver._browser_submission_receipt = receipt
                before = vars(receipt).copy()
                with patch.object(email_otp, "record_browser_submission_fact") as record:
                    self.assertTrue(self._recover(driver, state=driver.state, budget=self._budget(15)))
                    self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "ready")
                self.assertIs(driver._browser_submission_receipt, receipt)
                self.assertEqual(vars(receipt), before)
                record.assert_not_called()
                self.assertEqual(driver.refresh_count, 1)

    def test_submitted_route_error_recovers_form_but_keeps_original_result_unknown(self):
        state = _route_error_state()
        state["errors"] = [state["text"]]
        driver = _FakeDriver(state, refreshed_state=_form_state())
        receipt = BrowserSubmissionReceipt(
            kind="otp", stage="email_otp", endpoint_kind="otp_submit", phase="unknown",
            result="unknown", submission_id="test-original-otp-submission", started_at=90.0,
        )
        driver._browser_submission_receipt = receipt
        before = vars(receipt).copy()
        with ExitStack() as stack:
            submit = stack.enter_context(patch.object(roxy, "_submit_email_otp_current_form"))
            retype = stack.enter_context(patch.object(email_otp, "_type_otp"))
            resend = stack.enter_context(patch.object(email_otp, "_click_resend_email_otp"))
            record = stack.enter_context(patch.object(email_otp, "record_browser_submission_fact"))
            self.assertEqual(self._wait_after_submit(driver, budget=self._budget(15)), "stuck")
        self.assertEqual(driver.refresh_count, 1)
        self.assertIs(driver._browser_submission_receipt, receipt)
        self.assertEqual(vars(receipt), before)
        submit.assert_not_called()
        retype.assert_not_called()
        resend.assert_not_called()
        record.assert_not_called()

    def test_submitted_route_error_stays_stuck_after_unchanged_page_or_failed_refresh(self):
        state = _route_error_state()
        state["errors"] = [state["text"]]
        for refresh_error in (None, RuntimeError("测试刷新失败")):
            with self.subTest(refresh_error=type(refresh_error).__name__):
                driver = _FakeDriver(state, refresh_error=refresh_error)
                self.assertEqual(self._wait_after_submit(driver, budget=self._budget(15)), "stuck")
                self.assertEqual(driver.refresh_count, 1)

    def test_refresh_temporarily_caps_page_load_to_local_confirmation_budget_and_restores_it(self):
        for refresh_error in (None, RuntimeError("测试刷新失败")):
            with self.subTest(refresh_error=type(refresh_error).__name__):
                driver = _FakeDriver(_route_error_state(), refresh_error=refresh_error)
                driver.timeouts = SimpleNamespace(page_load=90.0)
                timeout_changes = []

                def set_timeout(seconds):
                    timeout_changes.append((seconds, self.clock.now))
                    driver.timeouts.page_load = seconds

                driver.set_page_load_timeout = Mock(side_effect=set_timeout)
                # 外层仍有 15 秒，提交确认仅有 4 秒；刷新必须受局部截止时间限制。
                local_deadline = self.clock.now + 4.0
                self.assertEqual(self._wait_after_submit(driver, timeout=4, budget=self._budget(15)), "stuck")
                self.assertEqual(driver.refresh_count, 1)
                self.assertEqual(driver.set_page_load_timeout.call_count, 2)
                temporary_timeout, changed_at = timeout_changes[0]
                self.assertGreaterEqual(temporary_timeout, 1.0)
                self.assertLessEqual(temporary_timeout, local_deadline - changed_at)
                self.assertEqual(timeout_changes[-1][0], 90.0)
                self.assertEqual(driver.timeouts.page_load, 90.0)

    def test_refresh_timeout_stops_page_loading_before_restoring_original_timeout(self):
        driver = _FakeDriver(_route_error_state(), refresh_error=TimeoutException("测试刷新加载超时"))
        driver.timeouts = SimpleNamespace(page_load=90.0)
        events = []
        original_execute_script = driver.execute_script

        def execute_script(script, *args):
            events.append(("script", script))
            return original_execute_script(script, *args)

        def set_timeout(seconds):
            events.append(("timeout", seconds))
            driver.timeouts.page_load = seconds

        driver.execute_script = Mock(side_effect=execute_script)
        driver.set_page_load_timeout = Mock(side_effect=set_timeout)
        budget = self._budget(15)
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        stop_indices = [index for index, event in enumerate(events) if event == ("script", "window.stop();")]
        restore_indices = [index for index, event in enumerate(events) if event == ("timeout", 90.0)]
        self.assertEqual(len(stop_indices), 1)
        self.assertEqual(len(restore_indices), 1)
        self.assertLess(stop_indices[0], restore_indices[0])
        self.assertEqual(driver.timeouts.page_load, 90.0)
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 1)
        stop_calls = [call for call in driver.execute_script.call_args_list if call.args == ("window.stop();",)]
        self.assertEqual(len(stop_calls), 1)

    def test_route_error_snapshot_that_has_become_blank_starts_a_new_blank_grace(self):
        driver = _FakeDriver(_blank_state(), refreshed_state=_form_state())
        budget = self._budget(15)
        # 原快照是错误页，刷新前的新快照只是瞬态空白，不得套用错误页的立即刷新分支。
        self.assertFalse(self._recover(driver, state=_route_error_state(), budget=budget))
        self.assertEqual(driver.refresh_count, 0)
        self.clock.now += 0.5
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver._email_otp_blank_seen_at, self.clock.now)
        self.clock.now += 2.9
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 0)
        self.clock.now += 0.2
        self.assertTrue(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 1)

    def test_malformed_email_verification_url_returns_stuck_without_raising(self):
        state = _blank_state()
        state["url"] = "https://[broken/email-verification"
        driver = _FakeDriver(state)
        self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "stuck")
        self.assertEqual(driver.refresh_count, 0)

    def test_blank_page_with_visible_challenge_is_never_refreshed(self):
        state = _blank_state()
        state["challengePresent"] = True
        driver = _FakeDriver(state, refreshed_state=_form_state())
        self.assertEqual(self._reason(state), "")
        self.assertFalse(self._recover(driver, state=state, budget=self._budget(15)))
        self.clock.now += 4.0
        self.assertFalse(self._recover(driver, state=state, budget=self._budget(15)))
        self.assertEqual(self._wait_ready(driver, timeout=4, budget=self._budget(15)), "stuck")
        self.assertEqual(driver.refresh_count, 0)

    def test_transient_blank_that_mounts_before_grace_does_not_refresh_and_resets_seen_at(self):
        driver = _FakeDriver(_blank_state())
        mounts_at = self.clock.now + 2.0

        def current_state(*_args):
            return _blank_state() if self.clock.now < mounts_at else _form_state()

        with patch.object(driver, "execute_script", side_effect=current_state):
            self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "ready")
        self.assertEqual(driver.refresh_count, 0)
        self.assertIsNone(getattr(driver, "_email_otp_blank_seen_at", None))
        # 后续再次出现空壳，必须重新计算 3 秒，不能沿用前一段瞬态空白的时间。
        new_blank_seen_at = self.clock.now
        self.assertFalse(self._recover(driver, state=driver.state, budget=self._budget(15)))
        self.assertEqual(driver._email_otp_blank_seen_at, new_blank_seen_at)
        self.clock.now += 2.9
        self.assertFalse(self._recover(driver, state=driver.state, budget=self._budget(15)))
        self.assertEqual(driver.refresh_count, 0)

    def test_failed_refresh_uses_the_only_refresh_allowance(self):
        driver = _FakeDriver(_route_error_state(), refresh_error=RuntimeError("测试刷新失败"))
        budget = self._budget(15)
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.clock.now += 4.0
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 1)

    def test_expired_budget_does_not_refresh_even_for_route_error(self):
        driver = _FakeDriver(_route_error_state(), refreshed_state=_form_state())
        budget = self._budget(0)
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(self._wait_ready(driver, timeout=15, budget=budget), "stuck")
        self.assertEqual(driver.refresh_count, 0)

    def test_nearly_expired_budget_does_not_start_route_error_refresh(self):
        driver = _FakeDriver(_route_error_state(), refreshed_state=_form_state())
        budget = self._budget(0.2)
        deadline = budget.deadline
        self.assertFalse(self._recover(driver, state=driver.state, budget=budget))
        self.assertEqual(driver.refresh_count, 0)
        self.assertEqual(budget.deadline, deadline)

    def test_short_timeout_ends_before_blank_shell_is_eligible_for_refresh(self):
        driver = _FakeDriver(_blank_state(), refreshed_state=_form_state())
        budget = self._budget(2)
        deadline = budget.deadline
        self.assertEqual(self._wait_ready(driver, timeout=15, budget=budget), "stuck")
        self.assertEqual(driver.refresh_count, 0)
        self.assertEqual(budget.deadline, deadline)
        self.assertLessEqual(self.clock.now, deadline)

    def test_profile_landing_is_accepted_without_refresh(self):
        state = {"url": "https://auth.openai.com/about-you", "inputs": [], "text": "Tell us about you"}
        driver = _FakeDriver(state)
        self.assertEqual(self._reason(state), "")
        self.assertFalse(self._recover(driver, state=state, budget=self._budget(15)))
        self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "accepted")
        self.assertEqual(driver.refresh_count, 0)

    def test_route_error_refresh_that_advances_to_profile_is_accepted(self):
        profile = {"url": "https://auth.openai.com/about-you", "inputs": [], "text": "Tell us about you"}
        driver = _FakeDriver(_route_error_state(), refreshed_state=profile)
        self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), "accepted")
        self.assertEqual(driver.refresh_count, 1)

    def test_explicit_verified_landing_and_totp_are_not_refreshed(self):
        states = (
            ({"url": _OTP_URL, "emailVerified": True, "inputs": [], "text": "Email verified"}, "email_verified"),
            ({"url": "https://auth.openai.com/log-in/password", "text": "Enter the code from your authenticator app",
              "inputs": [{"type": "text", "name": "totp", "autocomplete": "one-time-code"}]}, "totp_required"),
        )
        for state, expected in states:
            with self.subTest(expected=expected):
                driver = _FakeDriver(state)
                self.assertEqual(self._reason(state), "")
                self.assertEqual(self._wait_ready(driver, budget=self._budget(15)), expected)
                self.assertEqual(driver.refresh_count, 0)

    def test_invalid_code_disabled_account_and_external_host_are_not_recoverable(self):
        invalid = _form_state()
        invalid["errors"] = ["Invalid verification code"]
        invalid["inputs"][0]["ariaInvalid"] = "true"
        invalid_without_form = _blank_state()
        invalid_without_form.update(text="Invalid verification code", errors=["Invalid verification code"])
        disabled = _blank_state()
        disabled.update(text="Your account has been deactivated", errors=["account_deactivated"])
        other_error = _route_error_state()
        other_error["text"] = "Route Error (500 Internal Server Error)"
        external = _route_error_state()
        external["url"] = "https://example.test/email-verification"
        deceptive_host = _route_error_state()
        deceptive_host["url"] = "https://auth.openai.com.example.test/email-verification"
        for state in (invalid, invalid_without_form, disabled, other_error, external, deceptive_host):
            with self.subTest(text=state.get("text"), url=state["url"]):
                driver = _FakeDriver(state)
                self.assertEqual(self._reason(state), "")
                self.assertFalse(self._recover(driver, state=state, budget=self._budget(15)))
                self.clock.now += 4.0
                self.assertFalse(self._recover(driver, state=state, budget=self._budget(15)))
                self.assertEqual(driver.refresh_count, 0)

    def test_route_changed_after_snapshot_does_not_refresh_new_page(self):
        driver = _FakeDriver(_route_error_state())
        driver.current_url = "https://auth.openai.com/about-you"
        self.assertFalse(self._recover(driver, state=driver.state, budget=self._budget(15)))
        self.assertEqual(driver.refresh_count, 0)


if __name__ == "__main__":
    unittest.main()
