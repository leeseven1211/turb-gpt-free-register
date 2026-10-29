# -*- coding: utf-8 -*-
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import roxy_registration
from core.registration import email_otp
from core.registration.state_machine import StageTimeout


class _FakeDriver:
    def __init__(self):
        self.current_url = "https://chatgpt.com/auth/login"
        self.refresh_count = 0

    def refresh(self):
        self.refresh_count += 1

    def execute_script(self, *_args):
        return False


class RoxyEmailRecoveryTests(unittest.TestCase):
    @contextmanager
    def _missing_email_entry(self, driver, *, advanced_state=None, fallback=None, now=None):
        now = now if now is not None else [0.0]
        outer_budget = email_otp.StageBudget.start(10, clock=lambda: now[0])
        state = {"url": driver.current_url, "title": "ChatGPT", "inputs": [], "actions": []}
        error = RuntimeError("找不到邮箱输入框/邮箱入口（未使用文字识别），state={...}")
        with (
            patch.object(email_otp.StageBudget, "start", return_value=outer_budget),
            patch.object(email_otp, "_type_email_address", side_effect=error) as type_email,
            patch.object(email_otp, "_email_submit_advanced_state", return_value=advanced_state),
            patch.object(email_otp, "_email_entry_state", return_value=state),
            patch.object(email_otp, "_email_input_value_state") as input_state,
            patch.object(email_otp, "_submit_email_step") as submit,
            patch.object(email_otp, "_email_ui_submission_state", return_value=None) as ui_state,
            patch.object(email_otp, "_submit_email_via_browser_nextauth", return_value=(
                fallback if fallback is not None else {"ok": True, "stage": "redirect_dispatched"}
            )) as nextauth,
            patch.object(email_otp, "_wait_email_submit_next_state", return_value="login_password") as wait_next,
            patch.object(email_otp, "human_delay"),
        ):
            yield {
                "type_email": type_email, "input_state": input_state, "submit": submit,
                "ui_state": ui_state, "nextauth": nextauth, "wait_next": wait_next,
                "outer_budget": outer_budget, "state": state, "error": error,
            }

    def test_missing_initial_email_entry_uses_nextauth_with_remaining_budget(self):
        for actions in ([], [{"tag": "A", "attrs": "https://openai.com/policies/terms-of-use"}]):
            with self.subTest(actions=actions):
                driver = _FakeDriver()
                now = [0.0]
                with self._missing_email_entry(driver, now=now) as calls:
                    calls["state"]["actions"] = actions

                    def missing_after_preparation(*_args, **_kwargs):
                        now[0] = 7.0
                        raise calls["error"]

                    def dispatch_nextauth(current_driver, _email):
                        budget = current_driver._registration_stage_budget
                        self.assertEqual(budget.deadline, calls["outer_budget"].deadline)
                        self.assertEqual(budget.remaining(), 3.0)
                        return {"ok": True, "stage": "redirect_dispatched"}

                    calls["type_email"].side_effect = missing_after_preparation
                    calls["nextauth"].side_effect = dispatch_nextauth
                    result = email_otp._submit_email_and_wait_next(
                        driver, "test@example.com", total_timeout=10, allow_login_password=True,
                    )

                self.assertEqual(result, "login_password")
                calls["nextauth"].assert_called_once_with(driver, "test@example.com")
                calls["wait_next"].assert_called_once_with(
                    driver, "test@example.com", timeout=3.0, wait_through_transient=True,
                )
                calls["submit"].assert_not_called()
                calls["input_state"].assert_not_called()

    def test_missing_initial_email_entry_accepts_late_authentication_state(self):
        for advanced_state in ("otp", "login_password", "logged_in"):
            with self.subTest(advanced_state=advanced_state):
                driver = _FakeDriver()
                with self._missing_email_entry(driver, advanced_state=advanced_state) as calls:
                    result = email_otp._submit_email_and_wait_next(
                        driver, "test@example.com", allow_login_password=True,
                    )
                self.assertEqual(result, advanced_state)
                calls["nextauth"].assert_not_called()
                calls["submit"].assert_not_called()

    def test_missing_initial_email_entry_preserves_dispatched_submission_barrier(self):
        phases = ("dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown")
        cases = [(phase, None) for phase in phases] + [(None, phase) for phase in ("queued", "dispatched", "unknown")]
        for receipt_phase, ui_phase in cases:
            with self.subTest(receipt_phase=receipt_phase, ui_phase=ui_phase):
                driver = _FakeDriver()
                if receipt_phase is not None:
                    driver._browser_submission_receipt = email_otp.BrowserSubmissionReceipt(
                        kind="resume_login", stage="email", phase=receipt_phase,
                    )
                with self._missing_email_entry(driver) as calls:
                    calls["ui_state"].return_value = ui_phase
                    with self.assertRaises(email_otp._EmailSubmissionUnknown):
                        email_otp._submit_email_and_wait_next(driver, "test@example.com")
                calls["nextauth"].assert_not_called()
                calls["submit"].assert_not_called()

    def test_missing_initial_email_entry_rejects_other_origins_and_oauth_routes(self):
        for url in (
            "https://accounts.google.com/", "https://auth.openai.com/authorize",
            "https://chatgpt.com/consent", "https://chatgpt.com.evil.test/auth/login",
            "http://chatgpt.com/auth/login", "https://chatgpt.com:8443/auth/login",
            "https://user@chatgpt.com/auth/login",
        ):
            with self.subTest(url=url):
                driver = _FakeDriver()
                driver.current_url = url
                with self._missing_email_entry(driver) as calls:
                    with self.assertRaisesRegex(RuntimeError, "找不到邮箱输入框/邮箱入口"):
                        email_otp._submit_email_and_wait_next(driver, "test@example.com")
                calls["nextauth"].assert_not_called()
                calls["submit"].assert_not_called()

    def test_missing_initial_email_entry_does_not_replace_visible_challenge(self):
        driver = _FakeDriver()
        with self._missing_email_entry(driver) as calls:
            calls["state"]["inputs"] = [{"name": "totp", "type": "text"}]
            with self.assertRaisesRegex(RuntimeError, "找不到邮箱输入框/邮箱入口"):
                email_otp._submit_email_and_wait_next(driver, "test@example.com")
        calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_uses_remaining_attempt_and_budget(self):
        driver = _FakeDriver()
        now = [0.0]
        submitted = Mock()
        with self._missing_email_entry(driver, now=now) as calls:
            calls["state"]["inputs"] = [{"type": "email", "name": "email"}]
            calls["input_state"].return_value = {"inputs": [{"value": "test@example.com"}]}

            def type_after_mount(*_args, **kwargs):
                if calls["type_email"].call_count == 1:
                    now[0] = 7.0
                    raise calls["error"]
                self.assertEqual(kwargs["timeout"], 3.0)
                self.assertEqual(driver._registration_stage_budget.remaining(), 3.0)
                return "email"

            calls["type_email"].side_effect = type_after_mount
            with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                result = email_otp._submit_email_and_wait_next(
                    driver, "test@example.com", total_timeout=10, allow_login_password=True,
                    recover_late_email_entry=True, on_submitted=submitted,
                )

        self.assertEqual(result, "login_password")
        self.assertEqual(calls["type_email"].call_count, 2)
        calls["submit"].assert_called_once_with(driver, "test@example.com")
        submitted.assert_called_once_with()
        calls["nextauth"].assert_not_called()

    def test_shared_email_entry_keeps_default_late_input_behavior(self):
        driver = _FakeDriver()
        with self._missing_email_entry(driver) as calls:
            calls["state"]["inputs"] = [{"type": "email", "name": "email"}]
            with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                with self.assertRaises(RuntimeError) as raised:
                    email_otp._submit_email_and_wait_next(driver, "test@example.com")
        self.assertIs(raised.exception, calls["error"])
        calls["type_email"].assert_called_once()
        calls["submit"].assert_not_called()
        calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_preserves_unknown_submission_barrier(self):
        for receipt_phase, ui_phase in (
            ("dispatch_intent", None), ("ui_queued", None), ("ui_dispatched", None),
            ("request_observed", None), ("response_observed", None), ("unknown", None),
            (None, "queued"), (None, "dispatched"), (None, "unknown"),
        ):
            with self.subTest(receipt_phase=receipt_phase, ui_phase=ui_phase):
                driver = _FakeDriver()
                if receipt_phase is not None:
                    driver._browser_submission_receipt = email_otp.BrowserSubmissionReceipt(
                        kind="registration", stage="email", endpoint_kind="email_submit", phase=receipt_phase,
                    )
                with self._missing_email_entry(driver) as calls:
                    calls["state"]["inputs"] = [{"type": "email", "name": "email"}]
                    calls["ui_state"].return_value = ui_phase
                    with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                        with self.assertRaises(email_otp._EmailSubmissionUnknown):
                            email_otp._submit_email_and_wait_next(
                                driver, "test@example.com", recover_late_email_entry=True,
                            )
                calls["type_email"].assert_called_once()
                calls["submit"].assert_not_called()
                calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_does_not_extend_attempts(self):
        driver = _FakeDriver()
        with self._missing_email_entry(driver) as calls:
            calls["state"]["inputs"] = [{"type": "email", "name": "email"}]
            with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                with self.assertRaises(RuntimeError) as raised:
                    email_otp._submit_email_and_wait_next(
                        driver, "test@example.com", attempts=1, recover_late_email_entry=True,
                    )
        self.assertIs(raised.exception, calls["error"])
        calls["type_email"].assert_called_once()
        calls["submit"].assert_not_called()
        calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_does_not_replace_other_challenges(self):
        driver = _FakeDriver()
        with self._missing_email_entry(driver) as calls:
            calls["state"]["inputs"] = [{"name": "totp", "type": "text"}]
            with patch.object(email_otp, "_find_visible_email_input_js", return_value=None):
                with self.assertRaises(RuntimeError) as raised:
                    email_otp._submit_email_and_wait_next(
                        driver, "test@example.com", recover_late_email_entry=True,
                    )
        self.assertIs(raised.exception, calls["error"])
        calls["type_email"].assert_called_once()
        calls["submit"].assert_not_called()
        calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_preserves_coexisting_challenge(self):
        for challenge in ({"name": "authenticator", "type": "text"}, {"name": "password", "type": "password"}):
            with self.subTest(challenge=challenge):
                driver = _FakeDriver()
                with self._missing_email_entry(driver) as calls:
                    calls["state"]["inputs"] = [{"type": "email", "name": "email"}, challenge]
                    calls["input_state"].return_value = {"inputs": [{"value": "test@example.com"}]}
                    calls["type_email"].side_effect = [calls["error"], "email"]
                    with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                        with self.assertRaises(RuntimeError) as raised:
                            email_otp._submit_email_and_wait_next(
                                driver, "test@example.com", allow_login_password=True,
                                recover_late_email_entry=True,
                            )
                self.assertIs(raised.exception, calls["error"])
                calls["type_email"].assert_called_once()
                calls["submit"].assert_not_called()
                calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_allows_hidden_and_non_text_controls(self):
        for email_input in (
            {"type": "email"}, {"type": "text", "name": "email"},
            {"type": "text", "name": "username"}, {"type": "text", "id": "email-input"},
            {"type": "text", "autocomplete": "email"},
        ):
            with self.subTest(email_input=email_input):
                driver = _FakeDriver()
                with self._missing_email_entry(driver) as calls:
                    calls["state"]["inputs"] = [email_input,
                        {"type": "hidden", "name": "csrfToken"},
                        {"type": "password", "name": "password", "visible": False},
                        {"type": "submit"}, {"type": "button"}, {"type": "reset"},
                    ]
                    calls["input_state"].return_value = {"inputs": [{"value": "test@example.com"}]}
                    calls["type_email"].side_effect = [calls["error"], "email"]
                    with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                        result = email_otp._submit_email_and_wait_next(
                            driver, "test@example.com", allow_login_password=True,
                            recover_late_email_entry=True,
                        )
                self.assertEqual(result, "login_password")
                self.assertEqual(calls["type_email"].call_count, 2)
                calls["submit"].assert_called_once_with(driver, "test@example.com")
                calls["nextauth"].assert_not_called()

    def test_local_roxy_late_email_entry_does_not_restart_expired_budget(self):
        driver = _FakeDriver()
        now = [0.0]
        with self._missing_email_entry(driver, now=now) as calls:
            def missing_after_deadline(*_args, **_kwargs):
                now[0] = 11.0
                raise calls["error"]

            calls["type_email"].side_effect = missing_after_deadline
            calls["state"]["inputs"] = [{"type": "email", "name": "email"}]
            with patch.object(email_otp, "_find_visible_email_input_js", return_value=object()):
                with self.assertRaises(StageTimeout):
                    email_otp._submit_email_and_wait_next(
                        driver, "test@example.com", total_timeout=10, recover_late_email_entry=True,
                    )
        calls["submit"].assert_not_called()
        calls["nextauth"].assert_not_called()

    def test_only_local_roxy_registration_enables_late_email_entry_recovery(self):
        from tests.test_registration_resume_session import ResumeSessionFlowTests

        harness = ResumeSessionFlowTests()
        for local_roxy in (True, False):
            with self.subTest(local_roxy=local_roxy), harness.run_context(action="registration") as (_, mocks):
                mocks["navigate"].side_effect = None
                submit_email = Mock(side_effect=RuntimeError("单测在邮箱入口结束"))
                helpers = None if local_roxy else SimpleNamespace(
                    driver_name="roxy_oss", submit_email_and_wait_next=submit_email,
                    complete_profile_page=Mock(),
                )
                if local_roxy:
                    submit_email = mocks["_submit_email_and_wait_next"]
                    submit_email.side_effect = RuntimeError("单测在邮箱入口结束")
                result = harness.run_registration(existing_password=None, _browser_helpers=helpers)
            self.assertFalse(result["success"])
            submit_email.assert_called_once()
            if local_roxy:
                self.assertIs(submit_email.call_args.kwargs["recover_late_email_entry"], True)
            else:
                self.assertNotIn("recover_late_email_entry", submit_email.call_args.kwargs)

    def test_missing_initial_email_entry_does_not_restart_expired_budget(self):
        driver = _FakeDriver()
        now = [0.0]
        with self._missing_email_entry(driver, now=now) as calls:
            def missing_after_deadline(*_args, **_kwargs):
                now[0] = 11.0
                raise calls["error"]

            calls["type_email"].side_effect = missing_after_deadline
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(driver, "test@example.com", total_timeout=10)
        calls["nextauth"].assert_not_called()
        calls["submit"].assert_not_called()

    def test_missing_initial_email_entry_only_attempts_nextauth_once(self):
        driver = _FakeDriver()
        fallback = {"ok": False, "not_dispatched": True, "reason": "csrf_unavailable"}
        with self._missing_email_entry(driver, fallback=fallback) as calls:
            calls["submit"].side_effect = email_otp._EmailFrontendNotReady("页面仍未挂载")
            with self.assertRaisesRegex(RuntimeError, "邮箱提交后未进入密码页/验证码页"):
                email_otp._submit_email_and_wait_next(driver, "test@example.com")
        calls["nextauth"].assert_called_once_with(driver, "test@example.com")
        calls["type_email"].assert_called_once()

    def test_password_relogin_does_not_reuse_completed_email_budget(self):
        driver = _FakeDriver()
        completed_budgets = []
        now = [0.0]
        outer_budget = email_otp.StageBudget.start(180, clock=lambda: now[0])

        def confirm_password_page(current_driver, *_args, **_kwargs):
            completed_budgets.append(current_driver._registration_stage_budget)
            return "login_password"

        with (
            patch.object(email_otp.StageBudget, "start", return_value=outer_budget),
            patch.object(email_otp, "_type_email_address", return_value="email"),
            patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(email_otp, "human_delay"),
            patch.object(email_otp, "_submit_email_step"),
            patch.object(email_otp, "_wait_email_submit_next_state", side_effect=confirm_password_page),
        ):
            self.assertEqual(email_otp._submit_email_and_wait_next(
                driver, "test@example.com", allow_login_password=True,
            ), "login_password")

        # 重置密码耗时后再次登录，不能读到上一次邮箱流程已过期的预算。
        now[0] = 181.0
        self.assertTrue(completed_budgets[0].expired())
        with (
            patch.object(email_otp, "_wait_email_frontend_ready"),
            patch.object(email_otp, "_stabilize_email_input_before_submit", return_value={"ok": True}),
            patch.object(email_otp, "_submit_email_form_stable", return_value={"ok": True}) as submit,
            patch.object(email_otp, "_assert_not_external_idp"),
            patch.object(email_otp.time, "sleep"),
        ):
            email_otp._submit_email_step(driver, "test@example.com")
        submit.assert_called_once_with(driver, "test@example.com")
        self.assertFalse(hasattr(driver, "_registration_stage_budget"))
        self.assertFalse(hasattr(driver, "_registration_before_email_dispatch"))

    def test_email_scope_restores_caller_values_or_removes_temporary_values(self):
        attributes = (
            "_registration_resume_login", "_registration_email_progress",
            "_registration_stage_budget", "_registration_before_email_dispatch",
        )
        for existing_scope in (False, True):
            for error in (None, RuntimeError("登录失败"), StageTimeout("阶段超时")):
                with self.subTest(existing_scope=existing_scope, error=type(error).__name__):
                    driver = _FakeDriver()
                    previous = dict(zip(attributes, (
                        False, None, email_otp.StageBudget.start(90), Mock(),
                    ))) if existing_scope else {}
                    for name, value in previous.items():
                        setattr(driver, name, value)
                    with (
                        patch.object(email_otp, "_type_email_address", return_value="email"),
                        patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
                        patch.object(email_otp, "human_delay"),
                        patch.object(email_otp, "_submit_email_step", side_effect=error),
                        patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"),
                    ):
                        if error is None:
                            self.assertEqual(email_otp._submit_email_and_wait_next(driver, "test@example.com"), "otp")
                        else:
                            with self.assertRaises(type(error)):
                                email_otp._submit_email_and_wait_next(driver, "test@example.com")
                    for name in attributes:
                        self.assertEqual(hasattr(driver, name), existing_scope, name)
                        if existing_scope:
                            self.assertIs(getattr(driver, name), previous[name], name)

    def test_email_unknown_dispatch_restores_scope_after_timeout_conversion(self):
        driver = _FakeDriver()
        previous_budget = email_otp.StageBudget.start(90)
        previous_hook = Mock()
        driver._registration_stage_budget = previous_budget
        driver._registration_before_email_dispatch = previous_hook

        def submit_then_timeout(current_driver, _email):
            current_driver._email_submission_receipt = {"id": "test-submission"}
            raise StageTimeout("阶段超时")

        with (
            patch.object(email_otp, "_type_email_address", return_value="email"),
            patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(email_otp, "human_delay"),
            patch.object(email_otp, "_submit_email_step", side_effect=submit_then_timeout),
            patch.object(email_otp, "_log_email_submission_timeout"),
        ):
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                email_otp._submit_email_and_wait_next(driver, "test@example.com")
        self.assertIs(driver._registration_stage_budget, previous_budget)
        self.assertIs(driver._registration_before_email_dispatch, previous_hook)
        self.assertIsNone(driver._email_submission_receipt)
        previous_hook.assert_not_called()

    def test_nested_email_flow_restores_active_outer_budget_and_dispatch_hook(self):
        for inner_failure in (False, True):
            with self.subTest(inner_failure=inner_failure):
                driver = _FakeDriver()
                active_email = [None]

                def type_email(_driver, email, **_kwargs):
                    active_email[0] = email
                    return "email"

                def submit(current_driver, email):
                    if email == "inner@example.com":
                        if inner_failure:
                            raise RuntimeError("内层登录失败")
                        return
                    outer_scope = {
                        name: getattr(current_driver, name) for name in (
                            "_registration_resume_login", "_registration_email_progress",
                            "_registration_stage_budget", "_registration_before_email_dispatch",
                        )
                    }
                    try:
                        email_otp._submit_email_and_wait_next(current_driver, "inner@example.com")
                    except RuntimeError:
                        if not inner_failure:
                            raise
                    for name, value in outer_scope.items():
                        self.assertIs(getattr(current_driver, name), value, name)
                    # 内层结束后外层仍能切换自己的提交预算。
                    current_driver._registration_before_email_dispatch()

                with (
                    patch.object(email_otp, "_type_email_address", side_effect=type_email),
                    patch.object(email_otp, "_email_input_value_state", side_effect=lambda _driver: {"inputs": [{"value": active_email[0]}]}),
                    patch.object(email_otp, "human_delay"),
                    patch.object(email_otp, "_submit_email_step", side_effect=submit),
                    patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"),
                ):
                    self.assertEqual(email_otp._submit_email_and_wait_next(
                        driver, "outer@example.com", allow_login_password=True,
                    ), "otp")
                self.assertFalse(hasattr(driver, "_registration_stage_budget"))
                self.assertFalse(hasattr(driver, "_registration_before_email_dispatch"))

    def test_email_submission_keeps_original_outer_deadline_during_call(self):
        driver = _FakeDriver()
        now = [0.0]
        outer_budget = email_otp.StageBudget.start(10, clock=lambda: now[0])

        def submit(current_driver, _email):
            preparation = current_driver._registration_stage_budget
            now[0] = 9.0
            submission = current_driver._registration_before_email_dispatch()
            self.assertIsNot(submission, preparation)
            self.assertEqual(submission.deadline, outer_budget.deadline)
            now[0] = 10.0
            submission.require("邮箱首次提交")

        with (
            patch.object(email_otp.StageBudget, "start", return_value=outer_budget),
            patch.object(email_otp, "_type_email_address", return_value="email"),
            patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(email_otp, "human_delay"),
            patch.object(email_otp, "_submit_email_step", side_effect=submit),
            patch.object(email_otp, "_wait_email_submit_next_state") as wait_next,
        ):
            with self.assertRaises(StageTimeout):
                email_otp._submit_email_and_wait_next(driver, "test@example.com", total_timeout=10)
        wait_next.assert_not_called()
        self.assertFalse(hasattr(driver, "_registration_stage_budget"))

    def test_zero_email_input_budget_does_not_restore_default_timeout(self):
        driver = _FakeDriver()
        with patch.object(roxy_registration, "_find_visible_email_input_js") as find_input:
            with self.assertRaises(StageTimeout):
                roxy_registration._type_email_address(driver, "test@example.com", timeout=0)
        find_input.assert_not_called()

    def test_email_success_waits_for_next_page_instead_of_queue_return(self):
        driver = _FakeDriver()
        confirmed = Mock()
        progress = Mock()

        def wait_next(*_args, **_kwargs):
            confirmed.assert_not_called()
            return "otp"

        with (
            patch.object(roxy_registration, "_type_email_address", return_value="email"),
            patch.object(roxy_registration, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(roxy_registration, "human_delay"),
            patch.object(roxy_registration, "_submit_email_step"),
            patch.object(roxy_registration, "_wait_email_submit_next_state", side_effect=wait_next),
        ):
            result = roxy_registration._submit_email_and_wait_next(
                driver, "test@example.com", on_submitted=confirmed, on_progress=progress,
            )
        self.assertEqual(result, "otp")
        confirmed.assert_called_once_with()
        self.assertEqual([call.args[0] for call in progress.call_args_list], ["waiting_input", "filled", "pending"])

    def test_unknown_email_dispatch_never_reports_success(self):
        driver = _FakeDriver()
        confirmed = Mock()
        with (
            patch.object(roxy_registration, "_type_email_address", return_value="email"),
            patch.object(roxy_registration, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(roxy_registration, "human_delay"),
            patch.object(roxy_registration, "_submit_email_step"),
            patch.object(roxy_registration, "_wait_email_submit_next_state", side_effect=email_otp._EmailSubmissionUnknown("request_unknown")),
        ):
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                roxy_registration._submit_email_and_wait_next(driver, "test@example.com", on_submitted=confirmed)
        confirmed.assert_not_called()

    def test_existing_next_page_closes_email_step_as_skipped(self):
        confirmed = Mock()
        progress = Mock()
        with (
            patch.object(roxy_registration, "_type_email_address", return_value="otp"),
            patch.object(roxy_registration, "_submit_email_step") as submit,
        ):
            result = roxy_registration._submit_email_and_wait_next(
                _FakeDriver(), "test@example.com", on_submitted=confirmed, on_progress=progress,
            )
        self.assertEqual(result, "otp")
        self.assertEqual(progress.call_args.args[0], "skipped")
        confirmed.assert_not_called()
        submit.assert_not_called()

    def test_nextauth_navigation_dispatch_alone_never_reports_email_success(self):
        confirmed = Mock()
        with (
            patch.object(roxy_registration, "_type_email_address", return_value="email"),
            patch.object(roxy_registration, "_email_input_value_state", return_value={"inputs": [{"value": "test@example.com"}]}),
            patch.object(roxy_registration, "human_delay"),
            patch.object(roxy_registration, "_submit_email_step", side_effect=email_otp._EmailFrontendNotReady("未派发")),
            patch.object(roxy_registration, "_submit_email_via_browser_nextauth", return_value={"ok": True, "stage": "redirect_dispatched"}) as fallback,
            patch.object(roxy_registration, "_wait_email_submit_next_state", side_effect=email_otp._EmailSubmissionUnknown("request_unknown")),
        ):
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                roxy_registration._submit_email_and_wait_next(_FakeDriver(), "test@example.com", on_submitted=confirmed)
        confirmed.assert_not_called()
        fallback.assert_called_once()

    def test_otp_unknown_landing_is_not_accepted(self):
        for url in ("https://auth.openai.com/", "https://chatgpt.com/auth/error"):
            now = [0.0]

            def sleep(seconds):
                now[0] += seconds

            with (
                self.subTest(url=url),
                patch.object(roxy_registration, "_email_otp_page_state", return_value={"url": url, "inputs": []}),
                patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
                patch.object(roxy_registration, "_has_access_token", return_value=False),
                patch.object(roxy_registration.time, "monotonic", side_effect=lambda: now[0]),
                patch.object(roxy_registration.time, "sleep", side_effect=sleep),
            ):
                self.assertEqual(roxy_registration._wait_after_email_otp_submit(_FakeDriver(), timeout=1), "stuck")

    def test_otp_profile_landing_is_accepted(self):
        with (
            patch.object(roxy_registration, "_email_otp_page_state", return_value={"url": "https://auth.openai.com/about-you", "inputs": []}),
            patch.object(roxy_registration.time, "sleep"),
        ):
            self.assertEqual(roxy_registration._wait_after_email_otp_submit(_FakeDriver(), timeout=1), "accepted")

    def test_chatgpt_login_shell_is_not_oauth_consent(self):
        driver = _FakeDriver()
        driver.current_url = "https://chatgpt.com/auth/login?email=masked%40icloud.com"
        with patch.object(driver, "execute_script") as execute_script:
            self.assertFalse(roxy_registration._is_oauth_consent_like(driver))
        execute_script.assert_not_called()

    def test_resend_result_records_the_actual_click_time(self):
        button = Mock()
        button.text = "Resend"
        button.get_attribute.return_value = ""

        class Driver(_FakeDriver):
            def execute_script(self, *_args):
                return button

        fake_time = Mock()
        fake_time.monotonic.side_effect = [10.0, 10.0]
        fake_time.time.return_value = 1234.5
        fake_time.sleep.return_value = None
        with patch.object(
            roxy_registration,
            "_human_click",
        ), patch.object(
            roxy_registration,
            "_email_otp_page_state",
            return_value={"buttons": [{"text": "Resend", "disabled": True}]},
        ), patch.object(
            roxy_registration,
            "_is_email_verification_page",
            return_value=True,
        ), patch.object(
            roxy_registration,
            "_browser_actions_enabled",
            return_value=False,
        ), patch.object(roxy_registration, "time", fake_time):
            result = roxy_registration._click_resend_email_otp(Driver(), timeout=20)

        self.assertEqual(result["requested_after_ts"], 1234.5)

    def test_submitted_otp_tracker_rejects_the_same_code_twice(self):
        tracker_factory = getattr(roxy_registration, "_OtpAttemptTracker", None)
        self.assertIsNotNone(tracker_factory)
        if tracker_factory is None:
            return

        tracker = tracker_factory()
        self.assertTrue(tracker.accept("123456"))
        self.assertFalse(tracker.accept("123456"))
        self.assertTrue(tracker.accept("654321"))

    def test_otp_wait_failure_does_not_treat_dom_click_as_send_confirmation(self):
        code, detail = roxy_registration._classify_otp_wait_failure(
            TimeoutError("等待验证码超时"),
            last_ui_ack="unconfirmed",
        )

        self.assertEqual(code, "otp_request_unconfirmed")
        self.assertIn("不能断言", detail)

    def test_otp_wait_failure_distinguishes_delivery_and_mailbox_failures(self):
        delivery = roxy_registration._classify_otp_wait_failure(
            TimeoutError("等待验证码超时"),
            last_ui_ack="confirmed",
        )
        mailbox = roxy_registration._classify_otp_wait_failure(
            RuntimeError("Email Butler PG 读取失败"),
            last_ui_ack="confirmed",
        )

        self.assertEqual(delivery[0], "otp_delivery_missing")
        self.assertEqual(mailbox[0], "otp_mailbox_unavailable")

    def test_email_transition_gets_fresh_budget_after_slow_submit_dispatch(self):
        driver = _FakeDriver()

        class Budget:
            def __init__(self, remaining):
                self.value = remaining

            def remaining(self):
                return self.value

            def expired(self):
                return self.value <= 0

            def require(self, _action="stage"):
                if self.value <= 0:
                    raise AssertionError("stale pre-submit budget was reused")
                return self.value

        pre_submit = Budget(60)
        transition = Budget(60)

        def slow_submit(_driver, _email):
            pre_submit.value = 0

        email_state = {
            "url": "https://chatgpt.com/auth/login",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(
            roxy_registration.StageBudget,
            "start",
            side_effect=[pre_submit, transition],
        ) as start_budget, patch.object(
            roxy_registration, "_type_email_address"
        ), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step", side_effect=slow_submit
        ), patch.object(
            roxy_registration, "_wait_email_submit_next_state", return_value="otp"
        ) as wait_next:
            result = roxy_registration._submit_email_and_wait_next(
                driver,
                "test@example.com",
                total_timeout=60,
            )

        self.assertEqual(result, "otp")
        self.assertEqual(start_budget.call_count, 2)
        wait_next.assert_called_once_with(
            driver,
            "test@example.com",
            timeout=20,
            blank_shell_grace=3,
        )

    def test_type_otp_waits_for_delayed_input(self):
        field = Mock()
        field.is_displayed.return_value = True
        field.is_enabled.return_value = True

        class DelayedOtpDriver(_FakeDriver):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def find_elements(self, *_args):
                self.calls += 1
                return [field] if self.calls == 6 else []

        driver = DelayedOtpDriver()
        preparation_order = []
        preparation = Mock(side_effect=lambda _fields: preparation_order.append("prepared"))
        with patch.object(
            roxy_registration.time, "monotonic", return_value=100.0
        ), patch.object(roxy_registration.time, "sleep"), patch.object(
            roxy_registration, "_human_type_text", side_effect=lambda *_args, **_kwargs: preparation_order.append("typed")
        ) as type_text:
            roxy_registration._type_otp(driver, "123456", timeout=2, before_input=preparation)

        preparation.assert_called_once_with([field])
        self.assertEqual(preparation_order, ["prepared", "typed"])
        type_text.assert_called_once_with(driver, field, "123456", clear=True)

    def test_type_otp_recovers_from_email_otp_send_api_route(self):
        field = Mock()
        field.is_displayed.return_value = True
        field.is_enabled.return_value = True

        class ApiRouteDriver(_FakeDriver):
            def __init__(self):
                super().__init__()
                self.current_url = "https://auth.openai.com/api/accounts/email-otp/send"
                self.back_count = 0

            def back(self):
                self.back_count += 1
                self.current_url = "https://auth.openai.com/email-verification"

            def find_elements(self, *_args):
                return [field]

        driver = ApiRouteDriver()
        with patch.object(roxy_registration.time, "monotonic", return_value=100.0), patch.object(
            roxy_registration.time, "sleep"
        ), patch.object(roxy_registration, "_human_type_text") as type_text:
            roxy_registration._type_otp(driver, "123456", timeout=20)

        self.assertEqual(driver.back_count, 1)
        type_text.assert_called_once_with(driver, field, "123456", clear=True)

    def test_blank_auth_shell_uses_logged_dom_state_as_fallback(self):
        driver = _FakeDriver()
        state = {
            "url": "https://chatgpt.com/auth/login",
            "title": "Get started | ChatGPT",
            "inputs": [],
            "actions": [
                {"attrs": "/?slm=1", "tag": "A", "type": ""},
                {"attrs": "dismiss-welcome #", "tag": "A", "type": ""},
            ],
        }

        self.assertTrue(roxy_registration._is_blank_chatgpt_auth_shell(driver, state))

    def test_blank_auth_shell_without_actions_is_detected_by_start_title(self):
        driver = _FakeDriver()
        state = {
            "url": "https://chatgpt.com/auth/login",
            "title": "開始する | ChatGPT",
            "inputs": [],
            "actions": [],
        }

        self.assertTrue(roxy_registration._is_blank_chatgpt_auth_shell(driver, state))

    def test_blank_auth_shell_detects_localized_start_title(self):
        driver = _FakeDriver()
        state = {
            "url": "https://chatgpt.com/auth/login",
            "title": "Bắt đầu | ChatGPT",
            "inputs": [],
            "actions": [],
        }

        self.assertTrue(roxy_registration._is_blank_chatgpt_auth_shell(driver, state))

    def test_submit_wait_returns_blank_shell_without_waiting_for_timeout(self):
        driver = _FakeDriver()
        with patch.object(roxy_registration, "_has_access_token", return_value=False), patch.object(
            roxy_registration, "_is_login_password_page", return_value=False
        ), patch.object(roxy_registration, "_is_email_verification_page", return_value=False), patch.object(
            roxy_registration, "_is_signup_password_page", return_value=False
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(roxy_registration, "_is_blank_chatgpt_auth_shell", return_value=True):
            result = roxy_registration._wait_email_submit_next_state(driver, "test@example.com", timeout=20)

        self.assertEqual(result, "blank_shell")

    def test_submit_wait_gives_transient_blank_shell_a_bounded_hydration_grace(self):
        driver = _FakeDriver()
        fake_time = Mock()
        fake_time.time.side_effect = [100.0, 100.0, 101.0, 102.0]
        fake_time.sleep.return_value = None
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            side_effect=[None, None, "otp"],
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=True,
        ), patch.object(roxy_registration, "time", fake_time):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                blank_shell_grace=3,
            )

        self.assertEqual(result, "otp")

    def test_submit_wait_stops_grace_and_falls_back_for_persistent_blank_shell(self):
        driver = _FakeDriver()
        fake_time = Mock()
        fake_time.time.side_effect = [100.0, 100.0, 101.0, 103.1]
        fake_time.sleep.return_value = None
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value=None,
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=True,
        ), patch.object(roxy_registration, "time", fake_time):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                blank_shell_grace=3,
            )

        self.assertEqual(result, "blank_shell")

    def test_submit_wait_ignores_transient_shell_until_otp_arrives(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            side_effect=[None, "otp"],
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value={"url": driver.current_url, "inputs": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=True,
        ), patch.object(roxy_registration.time, "sleep"):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                wait_through_transient=True,
            )

        self.assertEqual(result, "otp")

    def test_submit_settle_does_not_resubmit_cleared_email_form(self):
        driver = _FakeDriver()
        fake_time = Mock()
        fake_time.time.side_effect = [100.0, 100.0, 103.0, 104.0, 106.0, 107.0]
        cleared_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": ""}],
        }
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            side_effect=[None, None, "otp"],
        ), patch.object(
            roxy_registration,
            "_email_input_value_state",
            return_value=cleared_state,
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            return_value=False,
        ), patch.object(
            roxy_registration,
            "_recover_email_submit_if_stuck",
        ) as recover, patch.object(roxy_registration, "time", fake_time):
            result = roxy_registration._wait_email_submit_next_state(
                driver,
                "test@example.com",
                timeout=20,
                wait_through_transient=True,
            )

        self.assertEqual(result, "otp")
        recover.assert_not_called()

    def test_stuck_email_page_uses_nextauth_fallback(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["email_page", "otp"],
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "redirected"},
        ) as nextauth:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        nextauth.assert_called_once_with(driver, "test@example.com")

    def test_first_blank_shell_switches_to_nextauth_without_reload(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["blank_shell", "otp"],
        ), patch.object(
            roxy_registration,
            "_log_blank_auth_shell_diagnostics",
        ), patch.object(roxy_registration, "_reload_blank_chatgpt_auth_shell") as reload_shell, patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "redirected"},
        ) as nextauth:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        reload_shell.assert_not_called()
        nextauth.assert_called_once_with(driver, "test@example.com")

    def test_nextauth_fallback_accepts_otp_that_arrived_during_race(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login",
            "inputs": [{"value": "test@example.com"}],
        }
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            return_value="blank_shell",
        ) as wait_next, patch.object(
            roxy_registration,
            "_log_blank_auth_shell_diagnostics",
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": True, "stage": "already_advanced", "state": "otp"},
        ):
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        wait_next.assert_called_once_with(
            driver,
            "test@example.com",
            timeout=20,
            blank_shell_grace=3,
        )

    def test_retry_stops_when_page_reaches_otp_before_email_refill(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="otp",
        ) as type_email, patch.object(
            roxy_registration,
            "_submit_email_step",
        ) as submit_email:
            result = roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

        self.assertEqual(result, "otp")
        type_email.assert_called_once_with(
            driver,
            "test@example.com",
            timeout=20,
            stop_on_advanced=True,
        )
        submit_email.assert_not_called()

    def test_new_registration_rejects_existing_login_password_page(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/log-in/password"
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="login_password",
        ):
            with self.assertRaisesRegex(RuntimeError, "已注册/不可用邮箱"):
                roxy_registration._submit_email_and_wait_next(driver, "test@example.com")

    def test_pending_account_resume_accepts_login_password_page(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/log-in/password"
        with patch.object(
            roxy_registration,
            "_type_email_address",
            return_value="login_password",
        ):
            result = roxy_registration._submit_email_and_wait_next(
                driver,
                "test@example.com",
                allow_login_password=True,
            )

        self.assertEqual(result, "login_password")

    def test_nextauth_skips_navigation_when_page_already_reached_otp(self):
        driver = _FakeDriver()
        driver.current_url = "https://auth.openai.com/email-verification"
        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value="otp",
        ):
            result = roxy_registration._submit_email_via_browser_nextauth(
                driver,
                "test@example.com",
            )

        self.assertEqual(result["state"], "otp")
        self.assertEqual(result["stage"], "already_advanced")
        self.assertTrue(result["ok"])

    def test_nextauth_does_not_treat_chatgpt_login_as_final_landing(self):
        driver = _FakeDriver()
        driver.set_script_timeout = lambda _timeout: None
        responses = iter((
            {"ok": True, "stage": "csrf_ready", "csrf_token": "test-token"},
            {"ok": True, "url": "https://chatgpt.com/api/auth/signin?csrf=true"},
        ))
        driver.execute_async_script = lambda *_args: next(responses)

        def _land_back_on_login(current_driver, *_args, **_kwargs):
            current_driver.current_url = "https://chatgpt.com/auth/login?callbackUrl=https%3A%2F%2Fchatgpt.com%2F"

        with patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value=None,
        ), patch.object(
            roxy_registration,
            "_safe_get",
            side_effect=_land_back_on_login,
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration,
            "_page_warmup",
        ):
            result = roxy_registration._submit_email_via_browser_nextauth(
                driver,
                "test@example.com",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "redirect_not_landed")
        self.assertEqual(result["url"], "https://chatgpt.com/auth/login")
        self.assertEqual(result["target_url"], "https://chatgpt.com/api/auth/signin")

    def test_submit_callback_runs_once_when_ui_is_retried(self):
        driver = _FakeDriver()
        email_state = {
            "url": "https://chatgpt.com/auth/login?email=test%40example.com",
            "inputs": [{"value": "test@example.com"}],
        }
        submitted = []
        with patch.object(roxy_registration, "_type_email_address"), patch.object(
            roxy_registration, "_email_input_value_state", return_value=email_state
        ), patch.object(roxy_registration, "human_delay"), patch.object(
            roxy_registration, "_submit_email_step"
        ), patch.object(
            roxy_registration,
            "_wait_email_submit_next_state",
            side_effect=["email_page", "otp"],
        ), patch.object(
            roxy_registration,
            "_submit_email_via_browser_nextauth",
            return_value={"ok": False, "stage": "signin"},
        ):
            result = roxy_registration._submit_email_and_wait_next(
                driver,
                "test@example.com",
                on_submitted=lambda: submitted.append(True),
            )

        self.assertEqual(result, "otp")
        self.assertEqual(submitted, [True])

    def test_missing_email_form_reloads_blank_auth_shell_once(self):
        driver = _FakeDriver()
        email_input = object()

        with patch.object(
            roxy_registration,
            "_find_visible_email_input_js",
            side_effect=[None, email_input],
        ), patch.object(
            roxy_registration,
            "_email_entry_state",
            return_value={"url": driver.current_url, "inputs": [], "actions": []},
        ), patch.object(
            roxy_registration,
            "_is_blank_chatgpt_auth_shell",
            side_effect=[True, True, False],
        ), patch.object(
            roxy_registration,
            "_email_submit_advanced_state",
            return_value=None,
        ), patch.object(
            roxy_registration,
            "_click_email_entry_option",
            return_value=False,
        ), patch.object(
            roxy_registration,
            "_page_warmup",
        ) as page_warmup, patch.object(
            roxy_registration,
            "human_delay",
        ), patch.object(
            roxy_registration,
            "_human_type_text",
        ) as type_text:
            roxy_registration._type_email_address(driver, "test@example.com", timeout=2)

        self.assertEqual(driver.refresh_count, 1)
        page_warmup.assert_called_once_with(driver, reason="reload_blank_auth_shell")
        type_text.assert_called_once_with(driver, email_input, "test@example.com", clear=True)

    def test_otp_submit_timeout_is_stuck_not_accepted(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration, "_is_email_verification_page", return_value=True
        ), patch.object(
            roxy_registration,
            "_email_otp_page_state",
            return_value={"inputs": [], "errors": []},
        ):
            outcome = roxy_registration._wait_after_email_otp_submit(driver, timeout=0)

        self.assertEqual(outcome, "stuck")

    def test_otp_submit_timeout_with_error_is_invalid(self):
        driver = _FakeDriver()
        with patch.object(
            roxy_registration, "_is_email_verification_page", return_value=True
        ), patch.object(
            roxy_registration,
            "_email_otp_page_state",
            return_value={"inputs": [{"ariaInvalid": "true"}], "errors": []},
        ):
            outcome = roxy_registration._wait_after_email_otp_submit(driver, timeout=0)

        self.assertEqual(outcome, "invalid")


if __name__ == "__main__":
    unittest.main()
