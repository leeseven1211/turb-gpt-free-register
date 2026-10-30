"""注册会话身份与浏览器保留现场的证据边界。"""
import unittest
import ast
import inspect
import json
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.registration import roxy
from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import StageBudget
from core.codex.roxy.oauth import _install_email_otp_validate_hook
from core.browser.roxy.client import RoxyBrowserClient, RoxyOpenResult


class RegistrationBrowserEvidenceTests(unittest.TestCase):
    def test_otp_preparation_uses_current_budget_instead_of_expired_email_budget(self):
        driver = SimpleNamespace(
            _registration_stage_budget=StageBudget.start(0), execute_script=Mock(return_value=True),
        )
        with patch("core.codex.roxy.oauth._install_email_otp_validate_hook") as install:
            roxy._prepare_email_otp_current_form(driver, [object()], budget=StageBudget.start(10))
        install.assert_called_once_with(driver, capture_responses=False)
        driver.execute_script.assert_called_once()

    def test_observed_otp_request_prevents_manual_click(self):
        receipt = BrowserSubmissionReceipt(kind="otp", stage="email_otp", endpoint_kind="otp_submit")
        receipt.phase = "request_observed"
        driver = SimpleNamespace(_browser_submission_receipt=receipt, execute_script=Mock())
        self.assertEqual(roxy._submit_email_otp_current_form(driver), {"clicked": False, "reason": "request_observed"})
        driver.execute_script.assert_not_called()

    def test_unprepared_otp_form_is_closed_as_not_dispatched(self):
        driver = SimpleNamespace(execute_script=Mock(return_value=False))
        with patch("core.codex.roxy.oauth._install_email_otp_validate_hook"), patch.object(
            roxy, "record_browser_submission_fact"
        ) as record:
            with self.assertRaisesRegex(RuntimeError, "otp_form_not_ready"):
                roxy._prepare_email_otp_current_form(driver, [object()])
        record.assert_called_once_with(driver, "not_dispatched", result="cancelled")

    def _run_current_otp_form_script(self, scenario):
        """执行生产脚本，模拟同一表单的事件结束与请求派发。"""
        source = r"""
        (async () => {
          const prepare = new Function(PREPARE);
          const submit = new Function(SUBMIT);
          const scenario = SCENARIO;
          let listener = null, clicks = 0;
          const form = {
            isConnected: true, method: 'post', action: 'https://auth.openai.com/email-verification',
            getAttribute: name => name === 'method' ? 'post' : name === 'action' ? '/email-verification' : null,
            querySelectorAll: () => [button], checkValidity: () => true,
          };
          const dispatchSubmit = canceled => {
            const event = {target: form, submitter: button, defaultPrevented: false,
              cancelable: true, isTrusted: true,
              preventDefault() { this.defaultPrevented = true; }};
            listener?.(event);
            if (canceled) event.preventDefault();
          };
          const button = {
            tagName: 'BUTTON', type: 'submit', name: 'intent', value: 'validate', form,
            disabled: false, isConnected: true,
            getClientRects: () => [1], matches: () => button.disabled,
            getAttribute: name => name === 'type' ? 'submit' : name === 'aria-disabled' ? null : '',
            click() { clicks++; dispatchSubmit(true); },
            scrollIntoView() {},
            getBoundingClientRect: () => ({left:10, top:20, width:100, height:40}),
            contains: el => el === button,
          };
          const input = {
            isConnected: true, form, readOnly: false, value: 'test-only-code',
            getClientRects: () => [1], matches: () => false,
          };
          global.location = {pathname: '/email-verification', href: form.action};
          global.window = {
            __codexEmailOtpValidateRequestCounterInstalled: true,
            __codexEmailOtpValidateRequestCount: 0,
            fetch: async () => ({status: 200}),
          };
          global.XMLHttpRequest = function() {};
          XMLHttpRequest.prototype.open = function() {};
          XMLHttpRequest.prototype.send = function() {};
          XMLHttpRequest.prototype.addEventListener = function() {};
          window.XMLHttpRequest = XMLHttpRequest;
          global.document = {
            elementFromPoint: () => button,
            addEventListener: (_name, callback) => { listener = callback; },
            removeEventListener: (_name, callback) => { if (listener === callback) listener = null; },
          };
          if (prepare([input]) !== true) throw Error('生产验证码准备脚本未绑定表单');
          if (['canceled', 'request', 'form-get', 'form-resend'].includes(scenario))
            dispatchSubmit(true);
          if (scenario === 'native') dispatchSubmit(false);
          if (scenario === 'native-then-canceled') {
            dispatchSubmit(false);
            await new Promise(resolve => setTimeout(resolve, 0));
            dispatchSubmit(true);
          }
          if (scenario === 'request') window.__codexEmailOtpValidateRequestCount++;
          if (scenario === 'form-post' || scenario === 'form-get' || scenario === 'form-resend') {
            const init = {method: scenario === 'form-get' ? 'GET' : 'POST'};
            if (init.method === 'POST') init.body = new URLSearchParams({
              intent: scenario === 'form-resend' ? 'resend' : 'validate', code: 'test-only-code',
            });
            await window.fetch(form.action, init);
          }
          if (scenario === 'form-xhr') {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', form.action);
            xhr.send(new URLSearchParams({intent: 'validate', code: 'test-only-code'}));
          }
          if (scenario === 'external-url') {
            await window.fetch(new URL('https://telemetry.example.test/collect'), {
              method: 'POST', body: new URLSearchParams({intent: 'validate'}),
            });
          }
          if (scenario === 'replaced') form.isConnected = false;
          if (scenario === 'disabled') button.disabled = true;
          // 捕获期之后页面才能取消事件，等待生产监听器读取最终状态。
          await new Promise(resolve => setTimeout(resolve, 0));
          const first = submit(scenario === 'trusted');
          await new Promise(resolve => setTimeout(resolve, 0));
          const second = submit();
          console.log(JSON.stringify({first, second, clicks}));
        })().catch(error => { console.error(error); process.exitCode = 1; });
        """.replace("PREPARE", json.dumps(roxy._OTP_PREPARE_CURRENT_FORM_SCRIPT)).replace(
            "SUBMIT", json.dumps(roxy._OTP_SUBMIT_CURRENT_FORM_SCRIPT)
        ).replace("SCENARIO", json.dumps(scenario))
        result = subprocess.run(
            [shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(result.stdout)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码首次点击")
    def test_canceled_submit_without_request_does_not_skip_first_click(self):
        result = self._run_current_otp_form_script("canceled")
        self.assertTrue(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 1)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码首次点击")
    def test_ready_current_form_is_clicked_once(self):
        result = self._run_current_otp_form_script("ready")
        self.assertTrue(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 1)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证真实点击预留")
    def test_trusted_current_form_reserves_only_one_external_click(self):
        result = self._run_current_otp_form_script("trusted")
        self.assertTrue(result["first"]["clicked"])
        self.assertEqual(result["first"]["trusted_click"], {"x": 60, "y": 40})
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 0)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码请求去重")
    def test_automatic_validate_request_is_not_clicked_again(self):
        result = self._run_current_otp_form_script("request")
        self.assertFalse(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 0)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证同路径验证码请求")
    def test_same_form_fetch_validate_post_is_not_clicked_again(self):
        result = self._run_current_otp_form_script("form-post")
        self.assertFalse(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 0)
        self.assertNotIn("test-only-code", json.dumps(result))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证同路径验证码请求")
    def test_same_form_xhr_validate_post_is_not_clicked_again(self):
        result = self._run_current_otp_form_script("form-xhr")
        self.assertFalse(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 0)
        self.assertNotIn("test-only-code", json.dumps(result))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证同路径请求分类")
    def test_same_form_get_does_not_skip_validate_click(self):
        result = self._run_current_otp_form_script("form-get")
        self.assertTrue(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 1)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证同路径请求分类")
    def test_explicit_resend_post_does_not_skip_validate_click(self):
        result = self._run_current_otp_form_script("form-resend")
        self.assertTrue(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 1)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码原生提交")
    def test_uncanceled_native_post_is_not_clicked_again(self):
        result = self._run_current_otp_form_script("native")
        self.assertFalse(result["first"]["clicked"])
        self.assertFalse(result["second"]["clicked"])
        self.assertEqual(result["clicks"], 0)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码原生提交")
    def test_later_canceled_event_cannot_clear_pending_native_post(self):
        result = self._run_current_otp_form_script("native-then-canceled")
        self.assertFalse(result["first"]["clicked"])
        self.assertEqual(result["clicks"], 0)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码请求来源")
    def test_external_url_object_post_does_not_block_first_click(self):
        result = self._run_current_otp_form_script("external-url")
        self.assertTrue(result["first"]["clicked"])
        self.assertEqual(result["clicks"], 1)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码表单状态")
    def test_replaced_or_disabled_form_is_not_clicked(self):
        for scenario in ("replaced", "disabled"):
            with self.subTest(scenario=scenario):
                result = self._run_current_otp_form_script(scenario)
                self.assertFalse(result["first"]["clicked"])
                self.assertFalse(result["second"]["clicked"])
                self.assertEqual(result["clicks"], 0)

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码诊断脱敏")
    def test_submit_diagnostics_only_contain_booleans_and_counts(self):
        result = self._run_current_otp_form_script("canceled")
        diagnostics = result["first"].get("diagnostics")
        self.assertIsInstance(diagnostics, dict)
        self.assertTrue(diagnostics)
        self.assertTrue(all(type(value) in (bool, int) for value in diagnostics.values()))
        self.assertNotIn("test-only-code", json.dumps(result))

    @unittest.skipUnless(shutil.which("node"), "需要 Node 验证验证码请求观察器")
    def test_direct_fetch_and_xhr_are_observed_before_response_without_rehooking(self):
        tree = ast.parse(inspect.getsource(_install_email_otp_validate_hook))
        script = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                      and isinstance(node.value, str) and "__codexEmailOtpValidateHooked" in node.value)
        source = r"""
        const script = SCRIPT;
        let fetches = 0, sends = 0, bodyReads = 0;
        global.window = {fetch(){fetches++;return Promise.resolve({status:200,
          clone(){bodyReads++;return {text:async()=> 'private-response'};}});}};
        global.XMLHttpRequest = function(){};
        XMLHttpRequest.prototype.open = function(){};
        XMLHttpRequest.prototype.send = function(){sends++;this.callback?.();};
        XMLHttpRequest.prototype.addEventListener = function(_name,callback){this.callback=callback;};
        Object.defineProperty(XMLHttpRequest.prototype,'responseText',{get(){bodyReads++;return 'private-response';}});
        new Function(script)(false);
        const hookedFetch = window.fetch, hookedSend = XMLHttpRequest.prototype.send;
        new Function(script)(false);
        window.fetch('/api/accounts/email-otp/validate', {method:'POST'});
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/accounts/email-otp/validate'); xhr.send();
        window.fetch('/api/accounts/email-otp/send', {method:'POST'});
        const immediateCount = window.__codexEmailOtpValidateRequestCount;
        setTimeout(()=>console.log(JSON.stringify({count:immediateCount,
          installed:window.__codexEmailOtpValidateRequestCounterInstalled,
          sameFetch:hookedFetch===window.fetch,sameSend:hookedSend===XMLHttpRequest.prototype.send,
          fetches,sends,bodyReads,responses:window.__codexEmailOtpValidateResponses.length})),0);
        """.replace("SCRIPT", json.dumps(script))
        result = subprocess.run([shutil.which("node"), "-e", source], capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), {
            "count": 2, "installed": True, "sameFetch": True, "sameSend": True, "fetches": 2, "sends": 1,
            "bodyReads": 0, "responses": 0,
        })

    def test_session_identity_accepts_only_the_target_mailbox(self):
        roxy._validate_registration_session_identity(
            {"user": {"email": " Alice@Example.test "}}, "alice@example.test"
        )
        with self.assertRaisesRegex(RuntimeError, "session_identity_mismatch") as caught:
            roxy._validate_registration_session_identity(
                {"user": {"email": "other@example.test"}}, "alice@example.test"
            )
        self.assertNotIn("@", str(caught.exception))
        self.assertTrue(roxy._is_registration_request_unknown(caught.exception))

    def test_session_without_identity_never_authorizes_saving_credentials(self):
        for session in ({}, {"user": {}}, {"user": None}, {"accessToken": "test-only"}):
            with self.subTest(session=session):
                with self.assertRaisesRegex(RuntimeError, "session_identity_unverified"):
                    roxy._validate_registration_session_identity(session, "alice@example.test")

    def test_retained_browser_still_finishes_capture_without_close_or_delete(self):
        client = RoxyBrowserClient(api_base="http://roxy.example")
        opened = RoxyOpenResult(profile_id="test-profile", raw={}, created_by_run=True)
        with patch.object(roxy._cfg, "ROXY_KEEP_BROWSER_OPEN", True), patch.object(
            roxy._cfg, "ROXY_DELETE_PROFILE_AFTER_RUN", True
        ), patch.object(roxy._cfg, "ROXY_ONE_PROFILE_PER_ACCOUNT", True), patch(
            "core.browser.traffic.finish_roxy_capture"
        ) as finish, patch.object(client, "close_profile") as close, patch.object(
            client, "delete_profile"
        ) as delete:
            client.cleanup_profile(opened)
        finish.assert_called_once_with(opened)
        close.assert_not_called()
        delete.assert_not_called()
