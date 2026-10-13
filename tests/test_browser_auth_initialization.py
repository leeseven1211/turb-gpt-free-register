"""登录表单接管、会话探测和认证首屏等待的竞态回归。"""
import json
import shutil
import subprocess
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.registration import email_otp, password_auth, session_auth
from core import roxy_codex_oauth
from core.registration.auth_context import AuthExecutionContext, execution_context
from core.registration.state_machine import StageBudget, StageTimeout


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


def _run_js(source):
    result = subprocess.run([shutil.which("node"), "-e", source], text=True, capture_output=True, timeout=10, check=True)
    return json.loads(result.stdout)


class BrowserAuthInitializationTests(unittest.TestCase):
    def test_stage_timeout_after_dispatch_preserves_unknown_outcome(self):
        driver = SimpleNamespace()
        def expires(*_args):
            driver._email_submission_receipt = {"id": "sent"}
            raise StageTimeout("阶段预算耗尽")
        with patch.object(email_otp, "_submit_email_and_wait_next_impl", side_effect=expires):
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                email_otp._submit_email_and_wait_next(driver, "unit@example.test")
        self.assertIsNone(driver._email_submission_receipt)

    def test_confirmed_next_step_releases_receipt_but_unknown_does_not(self):
        for state in (None, "login_password", "otp", "password", "logged_in"):
            with self.subTest(state=state), ExitStack() as stack:
                driver = SimpleNamespace(_email_submission_receipt={"id": "old"})
                for name, expected in (("_is_login_password_page", "login_password"), ("_is_email_verification_page", "otp"), ("_is_signup_password_page", "password"), ("_has_access_token", "logged_in")):
                    stack.enter_context(patch.object(email_otp, name, return_value=state == expected))
                self.assertEqual(email_otp._email_submit_advanced_state(driver), state)
                self.assertEqual(driver._email_submission_receipt, {"id": "old"} if state is None else None)

    def test_codex_confirmed_otp_clears_previous_submit_before_next_flow(self):
        driver = SimpleNamespace(_email_submission_receipt={"id": "old"}, execute_script=Mock(return_value=None))
        state = {"url": "https://auth.openai.com/email-verification", "inputs": [{"name": "code"}]}
        with ExitStack() as stack:
            stack.enter_context(patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state))
            for name in ("_is_totp_login_page", "_is_login_password_page", "_is_browser_error_page_state", "_is_terminal_auth_error_page", "_is_empty_auth_challenge_state"):
                stack.enter_context(patch.object(roxy_codex_oauth, name, return_value=False))
            stack.enter_context(patch.object(roxy_codex_oauth, "_is_email_verification_page", return_value=True))
            self.assertEqual(roxy_codex_oauth._complete_login_challenge_after_email(driver, "unit@example.test", "", ""), "email_otp")
        self.assertIsNone(email_otp._email_ui_submission_state(driver))

    def test_codex_pending_email_waits_without_fallback_even_after_navigation(self):
        clock = _Clock()
        driver = SimpleNamespace(_email_submission_receipt={"id": "old"}, execute_script=Mock(return_value=None))
        state = {"url": "https://chatgpt.com/auth/login?email=masked", "inputs": []}
        with ExitStack() as stack:
            stack.enter_context(patch.object(roxy_codex_oauth, "time", clock))
            stack.enter_context(patch.object(roxy_codex_oauth, "_login_challenge_state", return_value=state))
            for name in ("_is_browser_error_page_state", "_is_terminal_auth_error_page"):
                stack.enter_context(patch.object(roxy_codex_oauth, name, return_value=False))
            fallback = stack.enter_context(patch.object(roxy_codex_oauth, "_submit_email_via_browser_nextauth"))
            with self.assertRaises(email_otp._EmailSubmissionUnknown):
                roxy_codex_oauth._complete_login_challenge_after_email(driver, "unit@example.test", "", "", timeout=5)
        fallback.assert_not_called()
        self.assertEqual(clock.now, 5)

    def test_session_probe_never_fetches_from_foreign_or_lookalike_origin(self):
        for url in ("https://auth.openai.com/email-verification", "https://chatgpt.com.evil.test/", "http://chatgpt.com/", "https://chatgpt.com:444/"):
            with self.subTest(url=url):
                driver = Mock(current_url=url)
                self.assertFalse(session_auth._has_access_token(driver))
                driver.execute_async_script.assert_not_called()

    def test_session_probe_uses_remaining_shared_budget(self):
        driver = Mock(current_url="https://chatgpt.com/")
        driver.execute_async_script.return_value = True
        budget = StageBudget(0.125, clock=lambda: 0.0)
        self.assertTrue(session_auth._has_access_token(driver, budget=budget))
        self.assertEqual(driver.execute_async_script.call_args.args[1], 125)
        with self.assertRaises(StageTimeout):
            session_auth._has_access_token(driver, budget=StageBudget(0, clock=lambda: 0.0))

    def test_dom_next_state_does_not_wait_for_session(self):
        with patch.object(email_otp, "_is_login_password_page", return_value=False), patch.object(
            email_otp, "_is_email_verification_page", return_value=True
        ), patch.object(email_otp, "_has_access_token") as probe:
            self.assertEqual(email_otp._email_submit_advanced_state(object()), "otp")
        probe.assert_not_called()

    def test_frontend_wait_is_bounded_and_never_clicks_unready_form(self):
        clock = _Clock()
        driver = SimpleNamespace(execute_script=Mock(return_value=False))
        with patch.object(email_otp, "time", clock):
            with self.assertRaisesRegex(RuntimeError, "email_frontend_not_ready"):
                email_otp._wait_email_frontend_ready(driver, timeout=0.5)
        self.assertEqual(clock.now, 0.5)
        self.assertEqual(driver.execute_script.call_count, 2)

    def test_frontend_wait_accepts_late_handler_binding(self):
        clock = _Clock()
        driver = SimpleNamespace(execute_script=Mock(side_effect=[False, False, True]))
        with patch.object(email_otp, "time", clock):
            email_otp._wait_email_frontend_ready(driver, timeout=1)
        self.assertEqual(clock.now, 0.5)

    def test_frontend_timeout_does_not_fall_back_to_native_submit(self):
        driver = SimpleNamespace()
        with patch.object(email_otp, "_wait_email_frontend_ready", side_effect=RuntimeError("email_frontend_not_ready")), patch.object(
            email_otp, "_submit_email_form_stable"
        ) as stable, patch.object(email_otp, "_submit_nearest_form_for_active_input") as fallback:
            with self.assertRaisesRegex(RuntimeError, "email_frontend_not_ready"):
                email_otp._submit_email_step(driver, "unit@example.test")
        stable.assert_not_called()
        fallback.assert_not_called()

    def _run_email_flow(self, ready):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=ready))
        budgets = []

        def start_budget(timeout):
            budget = StageBudget(clock.now + timeout, clock=clock.time)
            budgets.append(budget)
            return budget

        with ExitStack() as stack:
            stack.enter_context(patch.object(email_otp, "time", clock))
            stack.enter_context(patch.object(email_otp.StageBudget, "start", side_effect=start_budget))
            stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="email"))
            stack.enter_context(patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "unit@example.test"}]}))
            stack.enter_context(patch.object(email_otp, "human_delay"))
            stack.enter_context(patch.object(email_otp, "_browser_actions_enabled", return_value=False))
            stack.enter_context(patch.object(email_otp, "_stabilize_email_input_before_submit", return_value={"ok": True}))
            stable = stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", return_value={"ok": True}))
            native = stack.enter_context(patch.object(email_otp, "_submit_nearest_form_for_active_input"))
            fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth", return_value={"ok": True, "state": "otp"}))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            result = email_otp._submit_email_and_wait_next(driver, "unit@example.test")
        return result, stable, native, fallback, budgets, clock

    def test_unhydrated_form_uses_one_fallback_without_native_submit_or_new_budget(self):
        result, stable, native, fallback, budgets, clock = self._run_email_flow(False)
        self.assertEqual(result, "otp")
        self.assertEqual(len(budgets), 1)
        # 前端准备预算耗尽后，兜底必须切换到同一外层截止内剩余的提交预算。
        self.assertEqual(budgets[0].remaining(), 60)
        stable.assert_not_called()
        native.assert_not_called()
        self.assertEqual(fallback.call_count, 1)

    def test_hydrated_form_does_not_use_nextauth_fallback(self):
        result, stable, native, fallback, _, _ = self._run_email_flow(True)
        self.assertEqual(result, "otp")
        self.assertEqual(stable.call_count, 1)
        native.assert_not_called()
        fallback.assert_not_called()

    def test_ui_dispatch_switches_to_one_submission_budget_before_click(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", execute_script=Mock(return_value=True))
        seen = []
        with ExitStack() as stack:
            stack.enter_context(patch.object(email_otp, "time", clock))
            stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="email"))
            stack.enter_context(patch.object(email_otp, "_email_input_value_state", return_value={"inputs": [{"value": "unit@example.test"}]}))
            stack.enter_context(patch.object(email_otp, "human_delay"))
            stack.enter_context(patch.object(email_otp, "_browser_actions_enabled", return_value=False))
            stack.enter_context(patch.object(email_otp, "_stabilize_email_input_before_submit", return_value={"ok": True}))
            stack.enter_context(patch.object(email_otp, "_submit_email_form_stable", return_value={"ok": True}))
            stack.enter_context(patch.object(email_otp, "_wait_email_submit_next_state", return_value="otp"))
            result = email_otp._submit_email_and_wait_next(driver, "unit@example.test")

        self.assertEqual(result, "otp")
        # _submit_email_step 使用真实实现；提交前钩子会在进入
        # _submit_email_form_stable 前观察共享提交预算。
        self.assertIsInstance(driver._registration_stage_budget, StageBudget)
        self.assertLessEqual(driver._registration_stage_budget.remaining(), 60)

    def test_total_timeout_smaller_than_soft_outer_limit_is_preserved(self):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login")
        budgets = []

        def start_budget(timeout):
            budgets.append(timeout)
            return StageBudget(clock.now + timeout, clock=clock.time)

        with patch.object(email_otp, "time", clock), patch.object(email_otp.StageBudget, "start", side_effect=start_budget), patch.object(
            email_otp, "_type_email_address", return_value="otp"
        ):
            self.assertEqual(email_otp._submit_email_and_wait_next(driver, "unit@example.test", total_timeout=2), "otp")
        self.assertEqual(budgets, [2.0])

    def test_slow_signin_keeps_one_click_and_never_uses_fallback(self):
        for arrived in (True, False):
            with self.subTest(arrived=arrived):
                clock = _Clock()
                driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login?email=masked",
                                         execute_script=Mock(return_value={"id": "test", "phase": "dispatched"}))
                budget = StageBudget(12, clock=clock.time)

                def submit(*_args):
                    driver._email_submission_receipt = {"id": "test"}

                with ExitStack() as stack:
                    stack.enter_context(patch.object(email_otp, "time", clock))
                    start = stack.enter_context(patch.object(email_otp.StageBudget, "start", return_value=budget))
                    stack.enter_context(patch.object(email_otp, "_type_email_address", return_value="email"))
                    stack.enter_context(patch.object(email_otp, "human_delay"))
                    submitted = stack.enter_context(patch.object(email_otp, "_submit_email_step", side_effect=submit))
                    stack.enter_context(patch.object(email_otp, "_email_input_value_state", side_effect=lambda _: {
                        "url": driver.current_url, "inputs": [{"value": "unit@example.test" if clock.now == 0 else ""}]}))
                    stack.enter_context(patch.object(email_otp, "_email_submit_advanced_state", side_effect=lambda *_a, **_kw: "otp" if arrived and clock.now >= 9 else None))
                    stack.enter_context(patch.object(email_otp, "_is_blank_chatgpt_auth_shell", return_value=False))
                    recover = stack.enter_context(patch.object(email_otp, "_recover_email_submit_if_stuck"))
                    fallback = stack.enter_context(patch.object(email_otp, "_submit_email_via_browser_nextauth"))
                    if arrived:
                        self.assertEqual(email_otp._submit_email_and_wait_next(driver, "unit@example.test", total_timeout=12), "otp")
                    else:
                        with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                            email_otp._submit_email_and_wait_next(driver, "unit@example.test", total_timeout=12)
                self.assertEqual(submitted.call_count, 1)
                self.assertEqual(start.call_count, 1)
                recover.assert_not_called()
                fallback.assert_not_called()
                self.assertIsNone(getattr(driver, "_email_submission_receipt", None))

    def test_lost_document_receipt_remains_unknown_until_budget_expires(self):
        clock = _Clock()
        driver = SimpleNamespace(execute_script=Mock(return_value=None), _email_submission_receipt={"id": "old-document"})
        with patch.object(email_otp, "time", clock), patch.object(email_otp, "_email_submit_advanced_state", return_value=None), patch.object(
            email_otp, "_recover_email_submit_if_stuck"
        ) as recover:
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                email_otp._wait_email_submit_next_state(driver, "unit@example.test", timeout=0.1, budget=StageBudget(1, clock=clock.time))
        self.assertEqual(clock.now, 1)
        recover.assert_not_called()

    def test_cancelled_queued_click_is_safe_for_existing_fallback(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"id": "test", "phase": "cancelled"}),
                                 _email_submission_receipt={"id": "test"})
        with patch.object(email_otp, "_email_submit_advanced_state", return_value=None):
            self.assertEqual(email_otp._wait_email_submit_next_state(driver, "unit@example.test", timeout=1), "email_frontend_not_ready")
        self.assertIsNone(driver._email_submission_receipt)

    def test_pending_click_blocks_direct_fallback_and_legacy_recovery(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"id": "test", "phase": "queued"}),
                                 _email_submission_receipt={"id": "test"}, execute_async_script=Mock())
        with patch.object(email_otp, "_email_submit_advanced_state", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                email_otp._submit_email_via_browser_nextauth(driver, "unit@example.test")
        self.assertEqual(email_otp._recover_email_submit_if_stuck(driver, "unit@example.test")["reason"], "email_submission_pending")
        driver.execute_async_script.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_native_get_recovery_requires_original_document_navigation(self):
        driver = SimpleNamespace(execute_script=Mock(return_value=False))
        self.assertEqual(email_otp._recover_email_submit_if_stuck(driver, "unit@example.test")["reason"], "native_get_not_confirmed")
        script = driver.execute_script.call_args.args[0]
        source = """
        let original='https://chatgpt.com/auth/login';
        const window={}; const performance={getEntriesByType:()=>[{name:original,type:'navigate'}]};
        const probe=()=>{SCRIPT};
        const spa=probe(); original+='?email=masked'; const native=probe();
        window.__turbEmailSubmission={phase:'dispatched'};
        console.log(JSON.stringify([spa,native,probe()]));
        """.replace("SCRIPT", script)
        self.assertEqual(_run_js(source), [False, True, False])

    def test_safe_submit_without_target_does_not_blindly_submit_first_form(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={"ok": True}))
        with patch.object(email_otp, "_is_oauth_consent_like", return_value=False):
            self.assertFalse(email_otp._submit_nearest_form_for_active_input(driver))
        self.assertEqual(driver.execute_script.call_count, 1)

    def test_nextauth_fetch_and_navigation_share_remaining_budget(self):
        driver = SimpleNamespace(
            current_url="https://chatgpt.com/auth/login",
            _registration_stage_budget=StageBudget(0.3, clock=lambda: 0.0),
            timeouts=SimpleNamespace(script=8), set_script_timeout=Mock(), execute_script=Mock(),
            execute_async_script=Mock(return_value={"ok": True, "url": "https://auth.openai.com/authorize"}),
        )
        with patch.object(email_otp, "_email_submit_advanced_state", return_value=None), patch.object(
            email_otp, "_safe_get"
        ) as navigation:
            result = email_otp._submit_email_via_browser_nextauth(driver, "unit@example.test")
        self.assertEqual(result["stage"], "redirect_dispatched")
        self.assertEqual(driver.execute_async_script.call_args.args[-1], 250)
        self.assertEqual(driver.set_script_timeout.call_args_list[0].args, (0.3,))
        self.assertEqual(driver.set_script_timeout.call_args_list[-1].args, (8,))
        navigation.assert_not_called()

    def test_nextauth_exhausted_budget_does_not_send_request(self):
        driver = SimpleNamespace(_registration_stage_budget=StageBudget(0, clock=lambda: 0.0), execute_async_script=Mock())
        with self.assertRaises(StageTimeout):
            email_otp._submit_email_via_browser_nextauth(driver, "unit@example.test")
        driver.execute_async_script.assert_not_called()

    def test_next_state_session_probe_obeys_fallback_budget(self):
        budget = StageBudget(0.3, clock=lambda: 0.0)
        with patch.object(email_otp, "_is_login_password_page", return_value=False), patch.object(
            email_otp, "_is_email_verification_page", return_value=False
        ), patch.object(email_otp, "_is_signup_password_page", return_value=False), patch.object(
            email_otp, "_has_access_token", return_value=False
        ) as probe:
            self.assertIsNone(email_otp._email_submit_advanced_state(object(), budget=budget))
        self.assertIs(probe.call_args.kwargs["budget"], budget)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_nextauth_timeout_aborts_pending_csrf_without_sending_signin(self):
        driver = SimpleNamespace(current_url="https://chatgpt.com/auth/login", set_script_timeout=Mock(),
                                 execute_async_script=Mock(return_value={"ok": False}))
        with patch.object(email_otp, "_email_submit_advanced_state", return_value=None):
            email_otp._submit_email_via_browser_nextauth(driver, "unit@example.test")
        script = driver.execute_async_script.call_args.args[0]
        source = """
        let requests=0, aborted=false;
        const location={origin:'https://chatgpt.com'};
        const fetch=(_u,o)=>{requests++;o.signal.addEventListener('abort',()=>aborted=true);return new Promise(()=>{});};
        (function(){SCRIPT})('unit@example.test','fake-device','fake-log',5,result=>{
          console.log(JSON.stringify({requests,aborted,ok:result.ok,reason:result.reason}));
        });
        """.replace("SCRIPT", script)
        self.assertEqual(_run_js(source), {"requests": 1, "aborted": True, "ok": False, "reason": "nextauth_budget_exhausted"})

    def _password_wait(self, *, ready_after=None, budget_seconds=None, pending=True):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://auth.openai.com/email-verification", refresh=Mock())
        clicked = []

        def snapshot(_script):
            if ready_after is not None and clock.now >= ready_after:
                return {"ok": True, "target": object()}
            return {"ok": False, "reason": "missing_create_account_password_target",
                    "input_count": 0, "button_count": 0, "body_text_length": 0,
                    "initialization": {"pending": int(pending), "early": True, "ready": "complete",
                                       "recent_activity": False, "hydration_started": True, "hydration_ended": False}}

        driver.execute_script = snapshot
        budget = StageBudget(budget_seconds, clock=clock.time) if budget_seconds else None
        with execution_context(AuthExecutionContext(budget=budget)), patch.object(password_auth, "time", clock), patch.object(
            password_auth, "_is_signup_password_page", side_effect=lambda _: bool(clicked)
        ), patch.object(password_auth, "_human_click", side_effect=lambda *a, **kw: clicked.append(True)), patch.object(
            password_auth, "_has_access_token", return_value=False
        ):
            result = password_auth._click_signup_password_from_otp_if_present(driver, timeout=2)
        return result, driver, clock

    def test_initialization_can_finish_after_original_15_second_window(self):
        result, driver, clock = self._password_wait(ready_after=25)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(clock.now, 25)
        driver.refresh.assert_not_called()

    def test_pending_initial_send_is_never_refreshed_and_wait_is_bounded(self):
        result, driver, clock = self._password_wait()
        self.assertFalse(result["ok"])
        self.assertLessEqual(clock.now, 45.5)
        driver.refresh.assert_not_called()

    def test_initialization_extension_respects_parent_budget(self):
        result, driver, clock = self._password_wait(budget_seconds=3)
        self.assertFalse(result["ok"])
        self.assertLessEqual(clock.now, 3.5)
        driver.refresh.assert_not_called()

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_ssr_form_does_not_pass_until_submit_handler_exists(self):
        source = "const location={hostname:'chatgpt.com',pathname:'/auth/login'};" + email_otp._EMAIL_FRONTEND_READY_JS + """
        const input={}, form={}, submit={};
        const before=emailFrontendReady(input,form,submit);
        input.__reactProps$test={onChange(){}};
        const inputOnly=emailFrontendReady(input,form,submit);
        form.__reactProps$test={onSubmit(){}};
        console.log(JSON.stringify([before,inputOnly,emailFrontendReady(input,form,submit)]));
        """
        self.assertEqual(_run_js(source), [False, False, True])

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_stable_submit_checks_hydration_again_before_its_single_click(self):
        driver = Mock()
        driver.execute_script.return_value = {}
        email_otp._submit_email_form_stable(driver, "unit@example.test")
        script = driver.execute_script.call_args.args[0]
        source = r"""
        let queued=[], clicks=0, keyEvents=0;
        const location={hostname:'chatgpt.com',pathname:'/auth/login'};
        const window={}; const getComputedStyle=()=>({visibility:'visible',display:'block'});
        const setTimeout=callback=>queued.push(callback);
        class Event {constructor(type){this.type=type;}}
        const InputEvent=Event, FocusEvent=Event;
        class HTMLInputElement {set value(v){this._value=v;} get value(){return this._value;}}
        const input=new HTMLInputElement();
        Object.assign(input,{offsetWidth:1,isConnected:true,getAttribute:()=>'',scrollIntoView(){},focus(){},blur(){},
          closest:()=>form,dispatchEvent(e){if(e.type.startsWith('key'))keyEvents++;}});
        const submit={offsetWidth:1,isConnected:true,getAttribute:k=>k==='type'?'submit':'',querySelectorAll:()=>[],
          querySelector:()=>null,scrollIntoView(){},click(){clicks++;}};
        const form={isConnected:true,getAttribute:()=>'',querySelectorAll:()=>[submit]};
        submit.form=form;
        const document={querySelectorAll:()=>[input]};
        const execute=function(){SCRIPT};
        const ssr=execute('unit@example.test');
        form.__reactProps$test={onSubmit(){}};
        const hydrated=execute('unit@example.test');
        delete form.__reactProps$test; queued.shift()();
        const afterUnmount=clicks;
        form.__reactProps$test={onSubmit(){}};
        execute('unit@example.test'); submit.isConnected=false; queued.shift()();
        const afterDetached=clicks;
        submit.isConnected=true;
        execute('unit@example.test'); submit.form={}; queued.shift()();
        const afterWrongForm=clicks;
        submit.form=form;
        execute('unit@example.test'); queued.shift()();
        console.log(JSON.stringify({ssr:ssr.ok,hydrated:hydrated.ok,afterUnmount,afterDetached,afterWrongForm,clicks,keyEvents}));
        """.replace("SCRIPT", script)
        self.assertEqual(_run_js(source), {"ssr": False, "hydrated": True, "afterUnmount": 0, "afterDetached": 0, "afterWrongForm": 0, "clicks": 1, "keyEvents": 0})

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_session_abort_completes_once_even_when_fetch_never_settles(self):
        driver = Mock(current_url="https://chatgpt.com/")
        session_auth._has_access_token(driver)
        script = driver.execute_async_script.call_args.args[0]
        # Selenium 参数位于脚本 arguments，外层词法环境提供浏览器对象。
        source = "let aborted=false,calls=0; const location={origin:'https://chatgpt.com'}; const fetch=(_u,o)=>{o.signal.addEventListener('abort',()=>aborted=true);return new Promise(()=>{});}; (function(){" + script + "})(5,value=>{calls++;setTimeout(()=>console.log(JSON.stringify({aborted,calls,value})),5);});"
        self.assertEqual(_run_js(source), {"aborted": True, "calls": 1, "value": False})

    @unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际页面脚本语义测试")
    def test_observer_preserves_fetch_and_waits_until_response_body_finishes(self):
        source = """
        (async()=>{
        let now=100, entries=[], resolveFetch;
        const promise=new Promise(resolve=>resolveFetch=resolve), response={status:200};
        const location={hostname:'auth.openai.com',origin:'https://auth.openai.com',href:'https://auth.openai.com/email-verification'};
        const document={readyState:'loading'};
        const performance={now:()=>now,getEntriesByType:t=>t==='resource'?entries:[]};
        const window={fetch:()=>promise};
        """ + password_auth._AUTH_INITIALIZATION_OBSERVER_JS + """
        const returned=window.fetch('/api/accounts/passwordless/send-otp',{method:'POST'});
        resolveFetch(response); await promise;
        const snapshot=()=>{ """ + password_auth._AUTH_INITIALIZATION_SNAPSHOT_JS + """ return authInitialization; };
        const before=snapshot().pending;
        entries=[{name:'https://auth.openai.com/api/accounts/passwordless/send-otp',startTime:101,responseEnd:200,responseStatus:200}];
        console.log(JSON.stringify({samePromise:returned===promise,sameResponse:(await returned)===response,before,after:snapshot().pending}));
        })();
        """
        self.assertEqual(_run_js(source), {"samePromise": True, "sameResponse": True, "before": 1, "after": 0})
