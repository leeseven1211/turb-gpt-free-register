import ast
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import browser_use_registration
from core import roxy_registration
from core.registration import password_auth
from core.registration.browser_submission import BrowserSubmissionReceipt, unresolved_submission_ids


def _password_target_script():
    """执行生产中实际使用的选择脚本，避免仅对脚本文字做断言。"""
    module = ast.parse(Path(password_auth.__file__).read_text(encoding="utf-8"))
    return next(
        node.value for node in ast.walk(module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and "missing_password_input" in node.value and "password_targets" in node.value
    )


def _password_target_result(**fixture):
    source = r"""
    const fixture = FIXTURE;
    const window = {};
    const timers = [];
    const setTimeout = fn => timers.push(fn);
    let clicks = 0;
    const location = {hostname:'auth.openai.com'};
    const getComputedStyle = el => ({visibility:'visible', display:el.hidden ? 'none' : 'block'});
    const form = {id:'password-form', isConnected:true, getAttribute:key=>key === 'id' ? 'password-form' : ''};
    const otherForm = {};
    const listeners = new Set();
    form.addEventListener = (name, callback) => { if (name === 'submit') listeners.add(callback); };
    form.removeEventListener = (name, callback) => { if (name === 'submit') listeners.delete(callback); };
    let submitEvents = 0;
    form.checkValidity = () => fixture.formValid !== false;
    if (fixture.hydrated !== false) form.__reactProps$test = {onSubmit(){}};
    const buttons = (fixture.buttons || [{id:'continue', type:'submit', text:'Continue'}]).map((item, index) => ({
      ...item, tagName:'BUTTON', disabled:!!item.disabled, isConnected:true,
      offsetWidth:100, offsetHeight:30, type:item.type || 'submit', textContent:item.text || '',
      form:item.otherForm ? otherForm : form,
      matches:()=>!!(fixture.fieldsetDisabled || item.fieldsetDisabled),
      click(){
        clicks += 1;
        if (fixture.suppressSubmit) return;
        if (fixture.foreignSubmitFirst) {
          for (const listener of [...listeners]) listener({target:otherForm, submitter:this, defaultPrevented:false});
        }
        const event = {target:form, submitter:fixture.mismatchedSubmitter ? {} : this, defaultPrevented:false};
        submitEvents += 1;
        for (const listener of [...listeners]) listener(event);
        // 模拟祖先 React 委托处理器晚于 form 捕获监听器阻止默认提交。
        if (fixture.preventDefault) event.defaultPrevented = true;
      },
      getAttribute:key=>({type:item.type || '', name:item.name || '', value:item.value || '',
        'aria-disabled':item.ariaDisabled ? 'true' : ''}[key] || ''),
      getBoundingClientRect:()=>({left:0,right:100,top:60 + index*40,bottom:90 + index*40}),
      getClientRects:()=>[{}], scrollIntoView(){}, closest:()=>form,
    }));
    form.querySelectorAll = () => buttons;
    const input = {id:'password', tagName:'INPUT', type:'password', disabled:false, readOnly:false,
      offsetWidth:100, offsetHeight:40, isConnected:true,
      value:fixture.inputValue === undefined ? 'ValidPass123!' : fixture.inputValue,
      form:fixture.hasForm === false ? null : form,
      matches:()=>!!fixture.fieldsetDisabled, validity:{valid:fixture.inputValid !== false},
      closest:()=>fixture.hasForm === false ? null : form, getAttribute:()=>'',
      getClientRects:()=>[{}], getBoundingClientRect:()=>({left:0,right:100,top:0,bottom:40})};
    const document = {querySelectorAll:selector=>selector.includes('password') ? [input] : buttons};
    const execute = function(){SCRIPT};
    const result = execute(fixture.mode || 'submit', 'ValidPass123!', fixture.replaced ? {} : input, 'test-submission');
    if (fixture.valueAfterQueue !== undefined) input.value = fixture.valueAfterQueue;
    if (fixture.superseded) window.__turbPasswordSubmissionReceipt = {};
    for (const callback of timers) callback();
    if (fixture.stopObserving) window.__turbPasswordSubmissionReceipt?.stop_observing?.();
    console.log(JSON.stringify({ok:result.ok, reason:result.reason, clicks,
      phase:window.__turbPasswordSubmissionReceipt?.phase || null,
      receipt:window.__turbPasswordSubmissionReceipt || null, listeners:listeners.size, submitEvents,
      input:result.input?.id || null, button:result.button?.id || null}));
    """.replace("FIXTURE", json.dumps(fixture)).replace("SCRIPT", _password_target_script())
    result = subprocess.run(
        [shutil.which("node"), "-e", source], check=True, capture_output=True, text=True, timeout=10,
    )
    return json.loads(result.stdout)


@unittest.skipUnless(shutil.which("node"), "需要 Node 执行实际密码表单脚本")
class PasswordFormTargetTests(unittest.TestCase):
    def test_intent_password_submit_is_preferred_to_back(self):
        result = _password_target_result(buttons=[
            {"id": "continue", "type": "submit", "name": "intent", "value": "password_signup", "text": "Continue"},
            {"id": "back", "type": "button", "text": "Back"},
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["button"], "continue")

    def test_disabled_empty_form_allows_filling_before_submit_selection(self):
        result = _password_target_result(
            mode="input", inputValue="", buttons=[{"id": "continue", "type": "submit", "disabled": True}],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["input"], "password")

    def test_password_form_requires_frontend_submit_handler(self):
        self.assertFalse(_password_target_result(hydrated=False)["ok"])

    def test_input_without_form_does_not_use_page_wide_buttons(self):
        self.assertFalse(_password_target_result(hasForm=False)["ok"])

    def test_submit_button_must_belong_to_password_form(self):
        result = _password_target_result(buttons=[
            {"id": "foreign", "type": "submit", "text": "Continue", "otherForm": True},
            {"id": "continue", "type": "submit", "text": "Continue"},
        ])
        self.assertTrue(result["ok"])
        self.assertEqual(result["button"], "continue")

    def test_alternative_buttons_are_never_used_as_password_submit(self):
        for button in (
            {"type": "submit", "name": "intent", "value": "passwordless_signup_send_otp", "text": "Continue"},
            {"type": "submit", "text": "Back"},
            {"type": "button", "text": "Try another way"},
            {"type": "button", "text": "Show password"},
        ):
            with self.subTest(button=button):
                self.assertFalse(_password_target_result(buttons=[button])["ok"])

    def test_submit_rechecks_the_filled_input_after_replacement(self):
        self.assertFalse(_password_target_result(replaced=True)["ok"])

    def test_submit_rechecks_value_after_frontend_reset(self):
        self.assertFalse(_password_target_result(inputValue="")["ok"])


    def test_external_connection_buttons_are_not_password_submits(self):
        for name, value in (("connection", "google-oauth2"), ("provider", "apple"), ("intent", "google_oauth")):
            with self.subTest(name=name, value=value):
                self.assertFalse(_password_target_result(buttons=[
                    {"type": "submit", "name": name, "value": value, "text": "Continue"},
                ])["ok"])

    def test_disabled_fieldset_and_invalid_form_are_not_submitted(self):
        for fixture in ({"fieldsetDisabled": True}, {"inputValid": False}, {"formValid": False}):
            with self.subTest(fixture=fixture):
                self.assertFalse(_password_target_result(**fixture)["ok"])

    def test_password_submit_is_queued_once(self):
        result = _password_target_result(mode="queue")
        self.assertTrue(result["ok"])
        self.assertEqual(result["clicks"], 1)
        self.assertEqual(result["phase"], "dispatched")
        self.assertEqual(result["receipt"], {
            "phase": "dispatched", "submission_id": "test-submission", "click_called": True,
            "submit_event_observed": True, "submit_default_prevented": False, "submitter_matches": True,
        })
        self.assertEqual(result["listeners"], 0)

    def test_click_without_submit_does_not_claim_form_submission_or_retry(self):
        result = _password_target_result(mode="queue", suppressSubmit=True, stopObserving=True)
        self.assertEqual(result["clicks"], 1)
        self.assertTrue(result["receipt"]["click_called"])
        self.assertFalse(result["receipt"]["submit_event_observed"])
        self.assertIsNone(result["receipt"]["submit_default_prevented"])
        self.assertIsNone(result["receipt"]["submitter_matches"])
        self.assertEqual(result["listeners"], 0)

    def test_delegated_prevent_default_is_read_after_event_propagation(self):
        result = _password_target_result(mode="queue", preventDefault=True)
        self.assertEqual(result["clicks"], 1)
        self.assertTrue(result["receipt"]["submit_event_observed"])
        self.assertTrue(result["receipt"]["submit_default_prevented"])

    def test_only_original_form_submission_is_observed_and_submitter_is_checked(self):
        result = _password_target_result(mode="queue", foreignSubmitFirst=True, mismatchedSubmitter=True)
        self.assertEqual(result["clicks"], 1)
        self.assertTrue(result["receipt"]["submit_event_observed"])
        self.assertFalse(result["receipt"]["submitter_matches"])
        self.assertEqual(result["listeners"], 0)

    def test_queued_submit_cancels_if_input_changes_before_click(self):
        result = _password_target_result(mode="queue", valueAfterQueue="")
        self.assertTrue(result["ok"])
        self.assertEqual(result["clicks"], 0)
        self.assertEqual(result["phase"], "cancelled")
        self.assertFalse(result["receipt"]["click_called"])
        self.assertFalse(result["receipt"]["submit_event_observed"])
        self.assertEqual(result["listeners"], 0)

    def test_superseded_receipt_never_clicks(self):
        result = _password_target_result(mode="queue", superseded=True)
        self.assertEqual(result["clicks"], 0)
        self.assertEqual(result["listeners"], 0)


class PasswordSubmissionEvidenceTests(unittest.TestCase):
    def test_snapshot_keeps_only_whitelisted_metadata_and_existing_request_fact(self):
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create", endpoint_kind="password_submit")
        receipt.phase = "request_observed"
        driver = SimpleNamespace(execute_script=Mock(return_value={
            "phase": "dispatched", "click_called": True, "submit_event_observed": True,
            "submit_default_prevented": True, "submitter_matches": True,
            "password": "private-test-value", "email": "private@example.test",
        }))
        snapshot = password_auth._password_submission_snapshot(driver, receipt, stop_observing=True)
        self.assertTrue(snapshot["request_observed"])
        self.assertTrue(snapshot["receipt_present"])
        self.assertNotIn("password", snapshot)
        self.assertNotIn("email", snapshot)
        self.assertEqual(driver.execute_script.call_args.args[1:], (receipt.submission_id, True))

    def test_missing_or_unreadable_original_receipt_leaves_evidence_unknown(self):
        receipt = BrowserSubmissionReceipt(kind="password", stage="password_create")
        for raw in (None, {}, {"phase": {"secret": "private-test-value"}, "click_called": "private-test-value"}):
            with self.subTest(raw=raw):
                driver = SimpleNamespace(execute_script=Mock(return_value=raw))
                snapshot = password_auth._password_submission_snapshot(driver, receipt)
                self.assertFalse(snapshot["receipt_present"])
                self.assertIsNone(snapshot["click_called"])
                self.assertIsNone(snapshot["request_observed"])
                self.assertNotIn("private-test-value", password_auth._password_submission_summary(snapshot))
        driver.execute_script.side_effect = RuntimeError("private-test-value")
        self.assertFalse(password_auth._password_submission_snapshot(driver, receipt)["receipt_present"])


class _RoxyDriver:
    def __init__(self):
        self.state = "otp"

    @property
    def current_url(self):
        if self.state == "otp":
            return "https://auth.openai.com/email-verification"
        return "https://auth.openai.com/create-account/password"

    def execute_script(self, _script, *_args):
        if _args and _args[0] == "queue":
            return {"ok": True, "reason": "password_submit_queued"}
        return {"ok": True, "input": object(), "button": object()}


class _RefreshableOtpDriver(_RoxyDriver):
    def __init__(self):
        super().__init__()
        self.refresh_count = 0
        self.scan_count = 0

    def refresh(self):
        self.refresh_count += 1

    def execute_script(self, _script):
        self.scan_count += 1
        if self.refresh_count:
            return {
                "ok": True,
                "reason": "create_account_password_target",
                "target": object(),
            }
        return {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [{"text": "Resend email", "href": "", "name": "intent", "value": "resend", "aria": ""}],
        }


class _BrowserUsePage:
    def __init__(self):
        self.state = "email_verification"


class _SteppingClock:
    def __init__(self, step=0.6):
        self.value = -step
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


class RegistrationFailureClassificationTests(unittest.TestCase):
    def test_pre_account_shell_failures_are_disposable_but_checkpointed_failures_are_not(self):
        disposable_errors = (
            "Roxy registration stage timeout exhausted",
            "email OTP input budget exhausted",
            "page_not_hydrated: blank shell",
        )
        for error in disposable_errors:
            with self.subTest(error=error):
                self.assertTrue(
                    roxy_registration._is_disposable_pre_account_failure(
                        error,
                        create_acknowledged=False,
                        account_id=None,
                    )
                )

        self.assertTrue(
            roxy_registration._is_disposable_pre_account_failure(
                '找不到邮箱输入框/邮箱入口，state={"actions": [], "inputs": [], '
                '"title": "開始する | ChatGPT", "url": "https://chatgpt.com/auth/login"}',
                create_acknowledged=False,
                account_id=None,
            )
        )

        self.assertFalse(
            roxy_registration._is_disposable_pre_account_failure(
                "Roxy registration stage timeout exhausted",
                create_acknowledged=True,
                account_id=None,
            )
        )
        self.assertFalse(
            roxy_registration._is_disposable_pre_account_failure(
                "Roxy registration stage timeout exhausted",
                create_acknowledged=False,
                account_id=501,
            )
        )

    def test_password_entry_failures_preserve_profile_for_same_attempt_recovery(self):
        for error in (
            "password_entry_page_not_hydrated",
            "password_entry_not_offered",
            "password_entry_recovery_exhausted",
        ):
            with self.subTest(error=error):
                self.assertFalse(
                    roxy_registration._is_disposable_pre_account_failure(
                        error,
                        create_acknowledged=False,
                        account_id=None,
                    )
                )


class RegistrationPasswordFlowTests(unittest.TestCase):
    def test_password_timeout_reports_submit_evidence_without_repeating_click(self):
        driver = _RoxyDriver()
        driver.state = "password"
        queues = []
        phases = []

        def execute(_script, *args):
            if args and args[0] == "queue":
                queues.append(args[3])
                return {"ok": True, "reason": "password_submit_queued"}
            if args and args[0] == "input":
                return {"ok": True, "input": object()}
            return {"phase": "dispatched", "click_called": True, "submit_event_observed": True,
                    "submit_default_prevented": True, "submitter_matches": True}

        with (
            patch.object(driver, "execute_script", side_effect=execute),
            patch.object(password_auth, "_registration_auth_mode", return_value="password"),
            patch.object(password_auth, "_is_email_verification_page", return_value=False),
            patch.object(password_auth, "_has_access_token", return_value=False),
            patch.object(password_auth, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(password_auth, "_is_signup_password_page", return_value=True),
            patch.object(password_auth, "_is_login_password_page", return_value=False),
            patch.object(password_auth, "_registration_password", return_value="ValidPass123!"),
            patch.object(password_auth, "_password_transition_timeout_seconds", return_value=3),
            patch.object(password_auth, "_human_type_text"),
            patch.object(password_auth, "human_delay"),
            patch.object(password_auth, "_check_manual_stop"),
            patch.object(password_auth, "record_browser_submission_fact", side_effect=lambda _driver, phase, **_kw: phases.append(phase)),
            patch.object(password_auth, "time", SimpleNamespace(time=_SteppingClock(step=1), sleep=lambda _seconds: None)),
        ):
            with self.assertRaisesRegex(RuntimeError, "request_unknown") as caught:
                password_auth._fill_password_page_if_present(driver, "new@example.test", timeout=10)
        self.assertEqual(len(queues), 1)
        self.assertIn("click_called=true", str(caught.exception))
        self.assertIn("submit_default_prevented=true", str(caught.exception))
        self.assertIn("request_observed=unknown", str(caught.exception))
        self.assertNotIn("ValidPass123!", str(caught.exception))
        self.assertNotIn("new@example.test", str(caught.exception))
        self.assertIn("unknown", phases)
        self.assertNotIn("not_dispatched", phases)
        self.assertNotIn("confirmed", phases)

    def test_password_requires_positive_landing_and_never_confirms_blank_or_error(self):
        for landing in ("https://auth.openai.com/", "https://chatgpt.com/auth/error", "https://auth.openai.com/about-you"):
            driver = _RoxyDriver()
            driver.state = "password"
            phases = []
            clock = _SteppingClock(step=1)
            snapshots = [{"url": driver.current_url}, {"url": landing, "inputs": []}]
            with (
                self.subTest(landing=landing),
                patch.object(password_auth, "_registration_auth_mode", return_value="password"),
                patch.object(password_auth, "_is_email_verification_page", return_value=False),
                patch.object(password_auth, "_has_access_token", return_value=False),
                patch.object(password_auth, "_password_page_state", side_effect=lambda _driver: snapshots.pop(0) if len(snapshots) > 1 else snapshots[0]),
                patch.object(password_auth, "_is_signup_password_page", side_effect=[True, False]),
                patch.object(password_auth, "_is_login_password_page", return_value=False),
                patch.object(password_auth, "_registration_password", return_value="ValidPass123!"),
                patch.object(password_auth, "_password_transition_timeout_seconds", return_value=3),
                patch.object(password_auth, "_human_type_text"),
                patch.object(password_auth, "human_delay"),
                patch.object(password_auth, "_check_manual_stop"),
                patch.object(password_auth, "record_browser_submission_fact", side_effect=lambda _driver, phase, **_kwargs: phases.append(phase)),
                patch.object(password_auth, "time", SimpleNamespace(time=clock, sleep=lambda _seconds: None)),
            ):
                if landing.endswith("about-you"):
                    self.assertEqual(password_auth._fill_password_page_if_present(driver, "new@example.test", timeout=10), "ValidPass123!")
                    self.assertIn("confirmed", phases)
                else:
                    with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                        password_auth._fill_password_page_if_present(driver, "new@example.test", timeout=10)
                    self.assertNotIn("confirmed", phases)

    def test_unresolved_submission_fence_survives_new_run_fact_projection(self):
        facts = [
            {"submission_id": "old", "phase": "dispatch_intent"},
            {"submission_id": "old", "phase": "unknown"},
            {"submission_id": "closed", "phase": "dispatch_intent"},
            {"submission_id": "closed", "phase": "confirmed"},
        ]
        self.assertEqual(unresolved_submission_ids(facts), {"old"})
        self.assertEqual(
            unresolved_submission_ids([
                {"submission_id": "confirmed", "phase": "confirmed"},
                {"submission_id": "confirmed", "phase": "request_observed"},
            ]),
            set(),
        )

    def test_real_password_driver_path_persists_prepared_before_dispatch(self):
        """走共享密码 driver 实现，验证持久化回调先于异步提交围栏。"""
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        events = []

        def submit_password(_script, *args):
            if args and args[0] == "queue":
                events.append("browser_queue")
                driver.state = "otp"
                return {"ok": True, "reason": "password_submit_queued"}
            return {"ok": True, "input": object(), "button": object()}

        with (
            patch.object(password_auth, "_registration_auth_mode", return_value="password"),
            patch.object(password_auth, "_is_email_verification_page", side_effect=lambda _driver: driver.state == "otp"),
            patch.object(password_auth, "_has_access_token", return_value=False),
            patch.object(password_auth, "_password_page_state", return_value={}),
            patch.object(password_auth, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(password_auth, "_is_login_password_page", return_value=False),
            patch.object(password_auth, "_registration_password", return_value=password),
            patch.object(password_auth, "_human_type_text"),
            patch.object(password_auth, "human_delay"),
            patch.object(password_auth, "_check_manual_stop"),
            patch.object(password_auth, "record_browser_submission_fact", side_effect=lambda _driver, phase, **_kwargs: events.append(phase)),
            patch.object(driver, "execute_script", side_effect=submit_password),
            patch.object(password_auth, "time", SimpleNamespace(time=lambda: 1, sleep=lambda _seconds: None)),
        ):
            result = password_auth._fill_password_page_if_present(
                driver,
                "new@example.com",
                timeout=2,
                on_password_prepared=lambda value: events.append(("prepared_checkpoint", value)),
                on_password_submitted=lambda value: events.append(("started_checkpoint", value)),
            )

        self.assertEqual(result, password)
        self.assertLess(events.index(("prepared_checkpoint", password)), events.index("browser_queue"))
        self.assertLess(events.index("prepared"), events.index("dispatch_intent"))
        self.assertIn(("started_checkpoint", password), events)
        self.assertEqual(events.count("browser_queue"), 1)

    def test_roxy_empty_otp_shell_does_not_force_password_route(self):
        driver = _RoxyDriver()
        driver.refresh_count = 0

        def refresh():
            driver.refresh_count += 1

        def empty_shell(_script):
            return {
                "ok": False,
                "reason": "missing_create_account_password_target",
                "candidates": [],
                "input_count": 0,
                "button_count": 0,
                "body_text_length": 0,
            }

        driver.refresh = refresh
        driver.execute_script = empty_shell
        with (
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=_SteppingClock(), sleep=Mock()),
            ),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "password_entry_recovery_exhausted")
        self.assertEqual(result["refresh_count"], 1)
        self.assertEqual(result["direct_navigation_count"], 0)
        self.assertEqual(driver.refresh_count, 1)

    def test_roxy_mounted_otp_page_never_forces_direct_password_route(self):
        driver = _RoxyDriver()
        driver.refresh_count = 0
        driver.refresh = lambda: setattr(driver, "refresh_count", driver.refresh_count + 1)
        driver.execute_script = lambda _script: {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [{
                "tag": "BUTTON",
                "text": "Resend email",
                "href": "",
                "name": "intent",
                "value": "resend",
                "aria": "",
            }],
            "input_count": 1,
            "button_count": 1,
            "body_text_length": 80,
        }
        with (
            patch.object(roxy_registration, "_safe_get") as direct_navigation,
            patch.object(roxy_registration, "_is_signup_password_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=_SteppingClock(), sleep=Mock()),
            ),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "password_entry_not_offered")
        self.assertEqual(result["refresh_count"], 1)
        self.assertEqual(result["direct_navigation_count"], 0)
        direct_navigation.assert_not_called()

    def test_password_mode_rejects_mounted_otp_page_without_password_option(self):
        driver = _RoxyDriver()
        with (
            patch.object(
                roxy_registration,
                "_click_signup_password_from_otp_if_present",
                return_value={
                    "ok": False,
                    "reason": "password_entry_not_offered",
                    "page_state": "mounted",
                    "url_path": "/email-verification",
                    "input_count": 1,
                    "button_count": 6,
                },
            ),
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=True),
            patch.object(roxy_registration, "time", SimpleNamespace(time=lambda: 1, sleep=Mock())),
        ):
            with self.assertRaisesRegex(RuntimeError, "password_entry_not_offered"):
                roxy_registration._fill_password_page_if_present(driver, "masked@example.test", timeout=2)

    def test_roxy_empty_otp_shell_exhausts_without_direct_navigation(self):
        driver = _RoxyDriver()
        driver.refresh_count = 0
        driver.refresh = lambda: setattr(driver, "refresh_count", driver.refresh_count + 1)
        driver.execute_script = lambda _script: {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [],
            "input_count": 0,
            "button_count": 0,
            "body_text_length": 0,
        }
        with (
            patch.object(roxy_registration, "_safe_get") as direct_navigation,
            patch.object(roxy_registration, "_is_signup_password_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=_SteppingClock(), sleep=Mock()),
            ),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "password_entry_recovery_exhausted")
        self.assertEqual(result["refresh_count"], 1)
        self.assertEqual(result["direct_navigation_count"], 0)
        direct_navigation.assert_not_called()

    def test_roxy_waits_for_delayed_create_password_target(self):
        driver = _RoxyDriver()
        target = object()
        calls = 0

        def delayed_target(_script):
            nonlocal calls
            calls += 1
            if calls < 3:
                return {"ok": False, "reason": "missing_create_account_password_target"}
            return {"ok": True, "reason": "create_account_password_target", "target": target}

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        driver.execute_script = delayed_target
        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")
        self.assertEqual(calls, 3)

    def test_roxy_password_target_supports_japanese_text_only_link(self):
        driver = _RoxyDriver()
        target = object()

        def text_only_target(script):
            self.assertIn("パスワードで続行", script)
            self.assertIn("conflictingLoginPath", script)
            return {
                "ok": True,
                "reason": "create_account_password_target",
                "target": target,
                "href": "",
                "text": "パスワードで続行",
            }

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        driver.execute_script = text_only_target
        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")

    def test_roxy_missing_password_target_preserves_candidate_diagnostics(self):
        driver = _RoxyDriver()
        candidate = {
            "tag": "A",
            "text": "Resend email",
            "href": "",
            "name": "",
            "value": "",
            "aria": "",
        }
        driver.execute_script = lambda _script: {
            "ok": False,
            "reason": "missing_create_account_password_target",
            "candidates": [candidate],
        }
        with (
            patch.object(roxy_registration, "_is_signup_password_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration.time, "sleep"),
            patch.object(roxy_registration.time, "time", side_effect=[0, 0, 2]),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "password_entry_not_offered")
        self.assertEqual(result["candidates"], [candidate])

    def test_roxy_password_target_refreshes_once_before_classifying_otp_only_flow(self):
        driver = _RefreshableOtpDriver()
        target = object()
        driver.execute_script = lambda _script: (
            {"ok": True, "reason": "create_account_password_target", "target": target}
            if driver.refresh_count
            else {"ok": False, "reason": "missing_create_account_password_target", "candidates": [
                {"text": "Resend email", "href": "", "name": "intent", "value": "resend", "aria": ""}
            ]}
        )

        def click_target(_driver, element, label=""):
            self.assertIs(element, target)
            self.assertEqual(label, "signup_use_password")
            driver.state = "password"

        with (
            patch.object(roxy_registration, "_human_click", side_effect=click_target),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 10] + [0] * 30), sleep=Mock()),
            ),
        ):
            result = roxy_registration._click_signup_password_from_otp_if_present(driver, timeout=2)

        self.assertTrue(result["ok"])
        self.assertEqual(result["reason"], "entered_create_account_password")
        self.assertEqual(driver.refresh_count, 1)

    def test_roxy_password_submit_does_not_advance_while_password_page_is_stuck(self):
        driver = _RoxyDriver()
        password = "ValidPass123!"
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_password_transition_timeout_seconds", return_value=20),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "human_delay"),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 0, 31]), sleep=Mock()),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "尚未确认下一步"):
                roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=2)

    def test_roxy_password_submit_uses_independent_transition_budget(self):
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=[False, True]),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_password_transition_timeout_seconds", return_value=60),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "_check_manual_stop"),
            patch.object(roxy_registration, "human_delay"),
            patch.object(
                roxy_registration,
                "time",
                SimpleNamespace(time=Mock(side_effect=[0, 0, 0, 30]), sleep=Mock()),
            ),
        ):
            result = roxy_registration._fill_password_page_if_present(
                driver,
                "new@example.com",
                timeout=2,
            )

        self.assertEqual(result, password)

    def test_roxy_password_submit_stops_early_on_explicit_remote_create_error(self):
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(
                roxy_registration,
                "_password_page_state",
                side_effect=[
                    {"url": driver.current_url, "text": "password form"},
                    {"url": driver.current_url, "text": "アカウントを作成できませんでした。もう一度お試しください"},
                ],
            ),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "human_delay"),
        ):
            with self.assertRaisesRegex(RuntimeError, "request_unknown.*页面报告账号创建失败"):
                roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=2)

    def test_roxy_password_is_checkpointed_immediately_after_submit_is_queued(self):
        driver = _RoxyDriver()
        driver.state = "password"
        password = "ValidPass123!"
        order = []

        def submit_password(_script, *args):
            if args and args[0] == "queue":
                order.append("queued")
                driver.state = "otp"
                return {"ok": True, "reason": "password_submit_queued"}
            return {"ok": True, "input": object(), "button": object()}

        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=lambda _driver: driver.state == "otp"),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(driver, "execute_script", side_effect=submit_password),
            patch.object(roxy_registration, "human_delay"),
        ):
            result = roxy_registration._fill_password_page_if_present(
                driver,
                "new@example.com",
                timeout=2,
                on_password_submitted=lambda value: order.append(("checkpoint", value)),
            )

        self.assertEqual(result, password)
        self.assertEqual(order, ["queued", ("checkpoint", password)])

    def test_roxy_password_submit_bridge_error_preserves_password_without_retry(self):
        driver = _RoxyDriver()
        password = "ValidPass123!"
        submissions = []
        saved = []

        def execute(_script, *args):
            if args and args[0] == "queue":
                submissions.append("possibly_dispatched")
                raise RuntimeError("bridge disconnected")
            return {"ok": True, "input": object(), "button": object()}

        with (
            patch.object(driver, "execute_script", side_effect=execute),
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=[False, True]),
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={}),
            patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(roxy_registration, "_human_click"),
            patch.object(roxy_registration, "human_delay"),
        ):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                roxy_registration._fill_password_page_if_present(
                    driver, "new@example.test", timeout=2, on_password_submitted=saved.append,
                )

        self.assertEqual(submissions, ["possibly_dispatched"])
        self.assertEqual(saved, [password])

    def test_roxy_password_mode_switches_from_otp_before_filling_password(self):
        driver = _RoxyDriver()
        password = "ValidPass123!"

        def switch_to_password(_driver, timeout=15):
            driver.state = "password"
            return {"ok": True, "reason": "entered_create_account_password"}

        def submit_password(_script, *args):
            if args and args[0] == "queue":
                driver.state = "otp"
                return {"ok": True, "reason": "password_submit_queued"}
            return {"ok": True, "input": object(), "button": object()}

        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
            patch.object(roxy_registration, "_is_email_verification_page", side_effect=lambda _driver: driver.state == "otp"),
            patch.object(roxy_registration, "_click_signup_password_from_otp_if_present", side_effect=switch_to_password) as switch,
            patch.object(roxy_registration, "_has_access_token", return_value=False),
            patch.object(roxy_registration, "_password_page_state", return_value={"url": driver.current_url}),
            patch.object(roxy_registration, "_is_signup_password_page", side_effect=lambda _driver: driver.state == "password"),
            patch.object(roxy_registration, "_is_login_password_page", return_value=False),
            patch.object(roxy_registration, "_registration_password", return_value=password),
            patch.object(roxy_registration, "_human_type_text"),
            patch.object(driver, "execute_script", side_effect=submit_password),
            patch.object(roxy_registration, "human_delay"),
        ):
            result = roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=2)

        self.assertEqual(result, password)
        switch.assert_called_once()

    def test_ambiguous_queue_response_preserves_password_without_resubmitting(self):
        for response in (None, {}, [], True, {"ok": True}, {"ok": 1, "reason": "password_submit_queued"},
                         {"ok": False, "reason": "unknown"}):
            with self.subTest(response=response):
                driver = _RoxyDriver()
                submissions = []
                saved = []

                def execute(_script, *args):
                    if args and args[0] == "queue":
                        submissions.append("possibly_dispatched")
                        if len(submissions) > 1:
                            raise RuntimeError("unexpected repeated queue")
                        return response
                    return {"ok": True, "input": object()}

                with (
                    patch.object(driver, "execute_script", side_effect=execute),
                    patch.object(roxy_registration, "_registration_auth_mode", return_value="password"),
                    patch.object(roxy_registration, "_is_email_verification_page", return_value=False),
                    patch.object(roxy_registration, "_has_access_token", return_value=False),
                    patch.object(roxy_registration, "_password_page_state", return_value={}),
                    patch.object(roxy_registration, "_is_signup_password_page", return_value=True),
                    patch.object(roxy_registration, "_is_login_password_page", return_value=False),
                    patch.object(roxy_registration, "_registration_password", return_value="ValidPass123!"),
                    patch.object(roxy_registration, "_human_type_text"),
                    patch.object(roxy_registration, "human_delay"),
                    patch.object(roxy_registration, "_password_transition_timeout_seconds", return_value=0),
                ):
                    with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                        roxy_registration._fill_password_page_if_present(
                            driver, "new@example.test", timeout=2, on_password_submitted=saved.append,
                        )
                self.assertEqual(submissions, ["possibly_dispatched"])
                self.assertEqual(saved, ["ValidPass123!"])

    def test_repeated_explicit_pre_dispatch_queue_failures_close_as_not_dispatched(self):
        driver = _RoxyDriver()
        phases = []
        ticks = iter((0, 0, 2, 3))

        def execute(_script, *args):
            if args and args[0] == "queue":
                return {"ok": False, "reason": "missing_password_submit"}
            return {"ok": True, "input": object()}

        with (
            patch.object(driver, "execute_script", side_effect=execute),
            patch.object(password_auth, "_registration_auth_mode", return_value="password"),
            patch.object(password_auth, "_is_email_verification_page", return_value=False),
            patch.object(password_auth, "_has_access_token", return_value=False),
            patch.object(password_auth, "_password_page_state", return_value={}),
            patch.object(password_auth, "_is_signup_password_page", return_value=True),
            patch.object(password_auth, "_is_login_password_page", return_value=False),
            patch.object(password_auth, "_registration_password", return_value="ValidPass123!"),
            patch.object(password_auth, "_human_type_text"),
            patch.object(password_auth, "human_delay"),
            patch.object(password_auth, "record_browser_submission_fact", side_effect=lambda _driver, phase, **_kwargs: phases.append(phase)),
            patch.object(password_auth, "time", SimpleNamespace(time=lambda: next(ticks), sleep=lambda _seconds: None)),
        ):
            with self.assertRaisesRegex(RuntimeError, "password_form_not_ready"):
                password_auth._fill_password_page_if_present(driver, "new@example.test", timeout=1)

        self.assertIn("not_dispatched", phases)
        self.assertNotIn("unknown", phases)

    def test_roxy_otp_mode_keeps_passwordless_registration(self):
        driver = _RoxyDriver()
        with (
            patch.object(roxy_registration, "_registration_auth_mode", return_value="otp"),
            patch.object(roxy_registration, "_is_email_verification_page", return_value=True),
            patch.object(roxy_registration, "_click_signup_password_from_otp_if_present") as switch,
        ):
            result = roxy_registration._fill_password_page_if_present(driver, "new@example.com", timeout=1)

        self.assertIsNone(result)
        switch.assert_not_called()

    def test_browser_use_password_mode_switches_from_otp_before_filling_password(self):
        page = _BrowserUsePage()
        password = "ValidPass123!"

        def state(_page):
            return {"state": page.state, "url": "https://auth.openai.com/" + page.state}

        def switch_to_password(_page, timeout=15):
            page.state = "password"
            return True

        def click_submit(_page, _selectors, timeout_ms=1500):
            page.state = "email_verification"
            return True

        with (
            patch.object(browser_use_registration, "_registration_auth_mode", return_value="password"),
            patch.object(browser_use_registration, "_browser_use_heartbeat", return_value=page),
            patch.object(browser_use_registration, "_quick_auth_state", side_effect=state),
            patch.object(browser_use_registration, "_click_signup_password_from_otp_if_present", side_effect=switch_to_password) as switch,
            patch.object(browser_use_registration, "_registration_password", return_value=password),
            patch.object(browser_use_registration, "_fill_first", return_value=True),
            patch.object(browser_use_registration, "_click_first", side_effect=click_submit),
            patch.object(browser_use_registration, "_bu_delay"),
        ):
            result = browser_use_registration._fill_password_if_present(
                page,
                "new@example.com",
                timeout=2,
                context=None,
            )

        self.assertEqual(result, password)
        switch.assert_called_once()

    def test_browser_use_password_mode_rejects_otp_page_without_password_entry(self):
        page = _BrowserUsePage()
        with (
            patch.object(browser_use_registration, "_registration_auth_mode", return_value="password"),
            patch.object(browser_use_registration, "_browser_use_heartbeat", return_value=page),
            patch.object(
                browser_use_registration,
                "_quick_auth_state",
                return_value={"state": "email_verification", "url": "https://auth.openai.com/email-verification", "hasOtp": True},
            ),
            patch.object(browser_use_registration, "_click_signup_password_from_otp_if_present", return_value=False) as switch,
        ):
            with self.assertRaisesRegex(RuntimeError, "无法切换到创建密码页"):
                browser_use_registration._fill_password_if_present(
                    page,
                    "new@example.com",
                    timeout=2,
                    context=None,
                )
        switch.assert_called_once()

    def test_browser_use_password_submit_stops_on_explicit_remote_create_error(self):
        page = _BrowserUsePage()
        states = iter(
            (
                {"state": "password", "url": "https://auth.openai.com/create-account/password", "remoteCreateError": False},
                {"state": "password", "url": "https://auth.openai.com/create-account/password", "remoteCreateError": True},
            )
        )
        with (
            patch.object(browser_use_registration, "_registration_auth_mode", return_value="password"),
            patch.object(browser_use_registration, "_browser_use_heartbeat", return_value=page),
            patch.object(browser_use_registration, "_quick_auth_state", side_effect=lambda _page: next(states)),
            patch.object(browser_use_registration, "_registration_password", return_value="ValidPass123!"),
            patch.object(browser_use_registration, "_fill_first", return_value=True),
            patch.object(browser_use_registration, "_click_first", return_value=True),
            patch.object(browser_use_registration, "_bu_delay"),
        ):
            with self.assertRaisesRegex(RuntimeError, "request_unknown.*页面报告账号创建失败"):
                browser_use_registration._fill_password_if_present(
                    page,
                    "new@example.com",
                    timeout=2,
                    context=None,
                )


if __name__ == "__main__":
    unittest.main()
