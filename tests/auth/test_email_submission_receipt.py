"""邮箱点击回执的取消边界、脱敏诊断与会话探测节流。"""

import json
import shutil
import subprocess
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.auth.browser import email_otp
from core.auth.state_machine import StageBudget


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


_PAGE_JS = r"""
let queued=[], cleared=[], clicks=0;
const location={hostname:'chatgpt.com',pathname:'/auth/login'};
const window={}; const getComputedStyle=()=>({visibility:'visible',display:'block'});
const setTimeout=callback=>{queued.push(callback); return queued.length;};
const clearTimeout=ident=>cleared.push(ident);
class Event {constructor(type){this.type=type;}}
const InputEvent=Event, FocusEvent=Event;
class HTMLInputElement {set value(v){this._value=v;} get value(){return this._value;}}
const input=new HTMLInputElement();
Object.assign(input,{offsetWidth:1,isConnected:true,validity:{valid:true},getAttribute:()=>'',
  matches:()=>false,scrollIntoView(){},focus(){},blur(){},closest:()=>form,dispatchEvent(){}});
const submit={offsetWidth:1,isConnected:true,getAttribute:k=>k==='type'?'submit':'',
  matches:()=>false,querySelectorAll:()=>[],querySelector:()=>null,scrollIntoView(){},click(){clicks++;}};
const form={isConnected:true,getAttribute:()=>'',querySelectorAll:()=>[submit],
  matches:()=>false,__reactProps$test:{onSubmit(){}}};
submit.form=form;
const document={querySelectorAll:()=>[input]};
"""


class EmailSubmissionReceiptTests(unittest.TestCase):
    def _submit_script(self):
        driver = SimpleNamespace(execute_script=Mock(return_value={}))
        email_otp._submit_email_form_stable(driver, "unit@example.test")
        return driver.execute_script.call_args.args[0]

    def _run_js(self, body):
        if not shutil.which("node"):
            self.skipTest("需要 Node 执行页面脚本语义测试")
        result = subprocess.run([shutil.which("node"), "-e", _PAGE_JS + body],
                                text=True, capture_output=True, check=True, timeout=10)
        return json.loads(result.stdout)

    def test_queued_cancel_stops_timer_and_late_callback_but_not_dispatched_click(self):
        driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"},
                                 execute_script=Mock(return_value=False))
        email_otp._cancel_queued_email_submission(driver)
        cancel = driver.execute_script.call_args.args[0]
        result = self._run_js("const execute=function(){" + self._submit_script() + "};"
                             + "const cancel=function(){" + cancel + "};" + """
        execute('unit@example.test','receipt');
        const wrongStopped=cancel('other-receipt');
        const stopped=cancel('receipt');
        queued.shift()();
        const afterCancel=clicks;
        execute('unit@example.test','sent'); queued.shift()();
        const sentStopped=cancel('sent');
        console.log(JSON.stringify({wrongStopped,stopped,afterCancel,sentStopped,clicks,cleared:cleared.length}));
        """)
        self.assertEqual(result, {"wrongStopped": False, "stopped": True, "afterCancel": 0, "sentStopped": False,
                                  "clicks": 1, "cleared": 1})

    def test_callback_rechecks_input_validity_and_button_state_before_click(self):
        changes = (
            "input.value='changed@example.test';",
            "input.validity.valid=false;",
            "form.matches=()=>true;",
            "input.readOnly=true;",
            "input.matches=()=>true;",
            "submit.matches=()=>true;",
            "submit.getAttribute=k=>k==='aria-disabled'?'true':k==='type'?'submit':'';",
            "window.__turbEmailSubmission.phase='cancelled';",
            "window.__turbEmailSubmission={id:'replacement',phase:'queued'};",
        )
        for change in changes:
            with self.subTest(change=change):
                result = self._run_js("const execute=function(){" + self._submit_script() + "};"
                                     + "execute('unit@example.test','receipt');" + change
                                     + "queued.shift()(); console.log(JSON.stringify({clicks}));")
                self.assertEqual(result, {"clicks": 0})

    def test_stale_queued_click_can_recover_before_full_budget(self):
        clock = _Clock()
        driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"},
                                 execute_script=Mock(return_value={"id": "receipt", "phase": "queued"}))
        with patch.object(email_otp, "time", clock), patch.object(
            email_otp, "_email_submit_advanced_state", return_value=None
        ), patch.object(email_otp, "_cancel_queued_email_submission", return_value=True) as cancel:
            result = email_otp._wait_email_submit_next_state(
                driver, "unit@example.test", timeout=20, budget=StageBudget(60, clock=clock.time),
            )
        self.assertEqual(result, "email_frontend_not_ready")
        self.assertLess(clock.now, 5)
        cancel.assert_called_once()

    def test_cancel_failure_keeps_submission_barrier_until_shared_budget_expires(self):
        for result in (False, RuntimeError("执行上下文已替换")):
            with self.subTest(result=type(result).__name__):
                clock = _Clock()
                driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"})

                def execute(script, *_args):
                    if "clearTimeout(receipt.timer)" in script:
                        if isinstance(result, Exception):
                            raise result
                        return result
                    return {"id": "receipt", "phase": "queued"}

                driver.execute_script = Mock(side_effect=execute)
                with patch.object(email_otp, "time", clock), patch.object(
                    email_otp, "_email_submit_advanced_state", return_value=None
                ), patch.object(email_otp, "_recover_email_submit_if_stuck") as recover:
                    with self.assertRaises(email_otp._EmailSubmissionUnknown):
                        email_otp._wait_email_submit_next_state(
                            driver, "unit@example.test", timeout=1, budget=StageBudget(4, clock=clock.time),
                        )
                self.assertEqual(clock.now, 4)
                self.assertEqual(driver._email_submission_receipt, {"id": "receipt"})
                recover.assert_not_called()

    def test_dispatched_or_missing_receipt_never_enters_queue_cancel(self):
        for browser_receipt in ({"id": "receipt", "phase": "dispatched"}, None):
            with self.subTest(browser_receipt=browser_receipt):
                clock = _Clock()
                driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"},
                                         execute_script=Mock(return_value=browser_receipt))
                with patch.object(email_otp, "time", clock), patch.object(
                    email_otp, "_email_submit_advanced_state", return_value=None
                ), patch.object(email_otp, "_cancel_queued_email_submission") as cancel, patch.object(
                    email_otp, "_recover_email_submit_if_stuck"
                ) as recover:
                    with self.assertRaises(email_otp._EmailSubmissionUnknown):
                        email_otp._wait_email_submit_next_state(
                            driver, "unit@example.test", timeout=1, budget=StageBudget(4, clock=clock.time),
                        )
                cancel.assert_not_called()
                recover.assert_not_called()
                self.assertEqual(clock.now, 4)

    def test_timeout_keeps_only_safe_receipt_diagnostics_after_cleanup(self):
        clock = _Clock()
        secret = "private@example.test"
        driver = SimpleNamespace(execute_script=Mock(return_value={
            "id": "receipt", "phase": "dispatched", "elapsed_ms": 1000,
            "input_connected": True, "input_valid": True, "submit_enabled": True,
            "email": secret, "url": "https://chatgpt.com/auth/login?email=" + secret,
        }))

        def wait(*_args):
            driver._email_submission_receipt = {"id": "receipt"}
            return email_otp._wait_email_submit_next_state(
                driver, secret, timeout=1, budget=StageBudget(1, clock=clock.time),
            )

        with patch.object(email_otp, "time", clock), patch.object(
            email_otp, "_email_submit_advanced_state", return_value=None
        ), patch.object(email_otp, "_submit_email_and_wait_next_impl", side_effect=wait):
            with self.assertLogs(email_otp.logger, level="WARNING") as logs:
                with self.assertRaises(email_otp._EmailSubmissionUnknown):
                    email_otp._submit_email_and_wait_next(driver, secret)
        snapshot = driver._email_submission_diagnostics
        self.assertEqual(snapshot["phase"], "dispatched")
        self.assertIs(snapshot["same_document"], True)
        self.assertIs(snapshot["input_valid"], True)
        self.assertNotIn(secret, json.dumps(snapshot) + str(logs.output))
        self.assertNotIn("url", snapshot)
        self.assertIsNone(driver._email_submission_receipt)

    def test_lost_document_diagnostics_retain_only_previous_confirmed_phase(self):
        driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"}, execute_script=Mock(side_effect=[
            {"id": "receipt", "phase": "dispatched", "elapsed_ms": float("nan"),
             "input_matches": "private@example.test", "reason": "private@example.test"},
            None,
        ]))
        self.assertEqual(email_otp._email_ui_submission_state(driver), "dispatched")
        self.assertEqual(driver._email_submission_diagnostics, {"phase": "dispatched", "same_document": True})
        self.assertEqual(email_otp._email_ui_submission_state(driver), "unknown")
        self.assertEqual(driver._email_submission_diagnostics, {
            "phase": "unknown", "same_document": False, "last_confirmed_phase": "dispatched",
        })

    def test_email_page_session_probe_is_throttled_but_dom_transition_is_immediate(self):
        clock = _Clock()
        driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"})
        with ExitStack() as stack:
            stack.enter_context(patch.object(email_otp, "time", clock))
            stack.enter_context(patch.object(email_otp, "_is_login_password_page", return_value=False))
            otp = stack.enter_context(patch.object(email_otp, "_is_email_verification_page", return_value=False))
            stack.enter_context(patch.object(email_otp, "_is_signup_password_page", return_value=False))
            stack.enter_context(patch.object(email_otp, "_is_email_login_page_still_present", return_value=True))
            session = stack.enter_context(patch.object(email_otp, "_has_access_token", return_value=False))
            for _ in range(5):
                self.assertIsNone(email_otp._email_submit_advanced_state(driver))
                clock.sleep(0.4)
            self.assertEqual(session.call_count, 1)
            otp.return_value = True
            self.assertEqual(email_otp._email_submit_advanced_state(driver), "otp")
            self.assertEqual(session.call_count, 1)

    def test_session_probe_resumes_immediately_when_email_form_disappears(self):
        driver = SimpleNamespace(_email_submission_receipt={"id": "receipt"})
        with ExitStack() as stack:
            for name in ("_is_login_password_page", "_is_email_verification_page", "_is_signup_password_page"):
                stack.enter_context(patch.object(email_otp, name, return_value=False))
            email_page = stack.enter_context(patch.object(email_otp, "_is_email_login_page_still_present", return_value=True))
            session = stack.enter_context(patch.object(email_otp, "_has_access_token", return_value=False))
            self.assertIsNone(email_otp._email_submit_advanced_state(driver))
            email_page.return_value = False
            session.return_value = True
            self.assertEqual(email_otp._email_submit_advanced_state(driver), "logged_in")


if __name__ == "__main__":
    unittest.main()
