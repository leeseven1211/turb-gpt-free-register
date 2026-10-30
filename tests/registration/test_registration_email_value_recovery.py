"""邮箱键入无异常但实际值为空时，只在未派发的准备阶段恢复输入。"""
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.auth.browser import email_otp
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import StageBudget, StageTimeout


EMAIL = "unit@example.test"


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


@contextmanager
def _unfilled_email_flow(*, stable=True, pending=None, before_type=None, setter_delay=0):
    clock = _Clock()
    driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
    value = [""]

    def type_email(*_args, **_kwargs):
        if before_type is not None:
            before_type(clock)
        if pending is not None:
            driver._browser_submission_receipt = BrowserSubmissionReceipt(
                kind="resume_login", stage="submit_email", phase="ui_dispatched", endpoint_kind=pending,
            )
        return "email"

    def stabilize(*_args):
        clock.sleep(setter_delay)
        value[0] = EMAIL if stable else ""
        return {"ok": True, "value": value[0]}

    with ExitStack() as stack:
        stack.enter_context(patch.object(email_otp, "time", clock))
        stack.enter_context(patch.object(
            email_otp.StageBudget, "start",
            side_effect=lambda timeout: StageBudget(clock.now + timeout, clock=clock.time),
        ))
        stack.enter_context(patch.object(email_otp, "_type_email_address", side_effect=type_email))
        stack.enter_context(patch.object(email_otp, "_email_input_value_state", side_effect=lambda _driver: {
            "url": driver.current_url, "inputs": [{"type": "email", "value": value[0]}],
        }))
        stack.enter_context(patch.object(email_otp, "human_delay"))
        setter = stack.enter_context(patch.object(email_otp, "_stabilize_email_input_before_submit", side_effect=stabilize))
        submit = stack.enter_context(patch.object(email_otp, "_submit_email_step"))
        stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
        fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
        yield driver, clock, setter, submit, fallback


class EmailValueRecoveryTests(unittest.TestCase):
    def test_empty_value_after_successful_typing_uses_native_setter_before_first_submit(self):
        with _unfilled_email_flow() as (driver, _clock, setter, submit, fallback):
            result = email_otp._submit_email_and_wait_next(driver, EMAIL)
        self.assertEqual(result, "otp")
        setter.assert_called_once_with(driver, EMAIL)
        submit.assert_called_once_with(driver, EMAIL)
        fallback.assert_not_called()

    def test_value_that_is_still_empty_never_dispatches_or_calls_nextauth(self):
        with _unfilled_email_flow(stable=False) as (driver, _clock, setter, submit, fallback):
            with self.assertRaisesRegex(RuntimeError, "邮箱提交后未进入"):
                email_otp._submit_email_and_wait_next(driver, EMAIL)
        self.assertEqual(setter.call_count, 3)
        submit.assert_not_called()
        fallback.assert_not_called()

    def test_expired_preparation_budget_never_runs_setter_or_submit(self):
        with _unfilled_email_flow(before_type=lambda clock: clock.sleep(1)) as (driver, _clock, setter, submit, fallback):
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(driver, EMAIL, total_timeout=1)
        setter.assert_not_called()
        submit.assert_not_called()
        fallback.assert_not_called()

    def test_setter_cannot_submit_after_consuming_remaining_preparation_budget(self):
        with _unfilled_email_flow(setter_delay=1) as (driver, _clock, setter, submit, fallback):
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(driver, EMAIL, total_timeout=1)
        setter.assert_called_once_with(driver, EMAIL)
        submit.assert_not_called()
        fallback.assert_not_called()

    def test_pending_email_receipt_prevents_value_repair(self):
        for endpoint in ("email_submit", "nextauth_signin"):
            with self.subTest(endpoint=endpoint), _unfilled_email_flow(pending=endpoint) as (
                driver, _clock, setter, submit, fallback,
            ):
                with self.assertRaises(email_otp._EmailSubmissionUnknown):
                    email_otp._submit_email_and_wait_next(driver, EMAIL)
                setter.assert_not_called()
                submit.assert_not_called()
                fallback.assert_not_called()

    def test_previous_password_receipt_does_not_block_unsubmitted_email_input(self):
        with _unfilled_email_flow(pending="password_submit") as (driver, _clock, setter, submit, fallback):
            self.assertEqual(email_otp._submit_email_and_wait_next(driver, EMAIL), "otp")
        setter.assert_called_once_with(driver, EMAIL)
        submit.assert_called_once_with(driver, EMAIL)
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
