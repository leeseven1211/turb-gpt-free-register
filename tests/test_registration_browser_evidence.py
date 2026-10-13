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
from core.registration.browser_submission import BrowserSubmissionReceipt
from core.registration.state_machine import StageBudget
from core.roxy_codex_oauth import _install_email_otp_validate_hook
from core.roxybrowser_client import RoxyBrowserClient, RoxyOpenResult


class RegistrationBrowserEvidenceTests(unittest.TestCase):
    def test_otp_preparation_uses_current_budget_instead_of_expired_email_budget(self):
        driver = SimpleNamespace(
            _registration_stage_budget=StageBudget.start(0), execute_script=Mock(return_value=True),
        )
        with patch("core.roxy_codex_oauth._install_email_otp_validate_hook") as install:
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
        with patch("core.roxy_codex_oauth._install_email_otp_validate_hook"), patch.object(
            roxy, "record_browser_submission_fact"
        ) as record:
            with self.assertRaisesRegex(RuntimeError, "otp_form_not_ready"):
                roxy._prepare_email_otp_current_form(driver, [object()])
        record.assert_called_once_with(driver, "not_dispatched", result="cancelled")

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
            "core.browser_traffic.finish_roxy_capture"
        ) as finish, patch.object(client, "close_profile") as close, patch.object(
            client, "delete_profile"
        ) as delete:
            client.cleanup_profile(opened)
        finish.assert_called_once_with(opened)
        close.assert_not_called()
        delete.assert_not_called()
