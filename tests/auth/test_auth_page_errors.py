"""认证整页错误应优先于旧路由及已卸载的表单。"""
from types import SimpleNamespace
import json
import shutil
import subprocess
import unittest
from unittest.mock import Mock

from core.auth.state_machine import PageState, classify_page
from core.auth.browser import selenium_dom


class AuthPageRecognitionTests(unittest.TestCase):
    def test_operation_timeout_overrides_stale_password_route_and_controls(self):
        for url in (
            "https://auth.openai.com/log-in/password",
            "https://auth.openai.com/email-verification",
            "https://chatgpt.com/auth/login",
        ):
            with self.subTest(url=url):
                self.assertEqual(classify_page({
                    "url": url, "text": "ओह, एक अनजान गड़बड़ी हो गई! Operation timed out",
                    "inputs": [{"type": "password", "autocomplete": "current-password", "visible": True}],
                }), PageState.AUTH_ERROR)

    def test_missing_auth_context_overrides_stale_password_or_otp_route(self):
        for text in (
            "नए सिरे से लॉग इन करें\nइस पेज पर आगे बढ़ने के लिए ज़रूरी जानकारी नहीं है. जिस ऐप या वेबसाइट से आपने शुरुआत की थी, वहाँ वापस जाएँ और फिर से लॉग इन करें.",
            "This page is missing information needed to continue. Go back to the app or website where you started and try logging in again.",
            "此页面缺少继续操作所需的信息。请返回最初发起登录的应用或网站，然后重新登录。",
        ):
            for route in ("log-in/password", "email-verification"):
                with self.subTest(text=text, route=route):
                    self.assertEqual(classify_page({
                        "url": f"https://auth.openai.com/{route}", "text": text, "inputs": [],
                    }), PageState.LOGGED_OUT)

    def test_password_route_without_actual_form_is_not_password_page(self):
        for snapshot in (
            {"url": "https://auth.openai.com/log-in/password", "inputs": [], "text": ""},
            {"url": "https://auth.openai.com/log-in/password", "inputs": [], "text": "Operation timed out"},
            {"url": "https://auth.openai.com/log-in/password", "inputs": [{"type": "password", "visible": False}]},
        ):
            with self.subTest(snapshot=snapshot):
                driver = SimpleNamespace(current_url=snapshot["url"], execute_script=Mock(return_value=snapshot))
                self.assertFalse(selenium_dom._is_login_password_page(driver))
                driver.execute_script.assert_called_once()

    def test_actual_password_form_is_recognized_from_one_snapshot(self):
        snapshot = {"url": "https://auth.openai.com/log-in/password",
                    "inputs": [{"type": "password", "autocomplete": "current-password", "visible": True}],
                    "forms": [{"action": "/api/accounts/login"}]}
        driver = SimpleNamespace(current_url=snapshot["url"], execute_script=Mock(return_value=snapshot))
        self.assertTrue(selenium_dom._is_login_password_page(driver))
        driver.execute_script.assert_called_once()

    def test_totp_form_on_old_password_route_is_not_password_page(self):
        snapshot = {"url": "https://auth.openai.com/log-in/password", "text": "Authenticator code",
                    "inputs": [{"type": "text", "name": "totp", "visible": True}]}
        driver = SimpleNamespace(current_url=snapshot["url"], execute_script=Mock(return_value=snapshot))
        self.assertFalse(selenium_dom._is_login_password_page(driver))
        self.assertEqual(classify_page(snapshot), PageState.MFA_TOTP)

    def test_fixed_page_error_details_require_trusted_origin(self):
        from core.auth.page_errors import auth_page_error

        for url in (
            "http://auth.openai.com/log-in/password",
            "https://auth.openai.com.evil.test/log-in/password",
            "https://auth.openai.com:444/log-in/password",
            "https://someone@auth.openai.com/log-in/password",
            "https://example.test/log-in/password",
        ):
            with self.subTest(url=url):
                self.assertIsNone(auth_page_error({"url": url, "text": "Operation timed out"}))
        error = auth_page_error({"url": "https://auth.openai.com:443/log-in/password",
                                 "text": "Operation timed out secret@example.test"})
        self.assertEqual(error.code, "auth_operation_timeout")
        self.assertEqual(error.page_state, "AUTH_ERROR")
        self.assertEqual(str(error), "认证页面操作超时")
        self.assertNotIn("secret@example.test", str(error))

    def test_generic_login_copy_does_not_imply_missing_context(self):
        from core.auth.page_errors import auth_page_error

        for text in ("Start over", "Please log in again", "Try again", "重新登录", "नए सिरे से लॉग इन करें"):
            with self.subTest(text=text):
                self.assertIsNone(auth_page_error({"url": "https://auth.openai.com/log-in/password", "text": text}))

    def test_structured_error_code_has_fixed_detail_without_echoing_remote_message(self):
        from core.auth.page_errors import auth_page_error

        error = auth_page_error({
            "url": "https://auth.openai.com/log-in/password", "errors": [
                {"error_code": "auth_context_missing", "message": "private@example.test private-token"},
            ],
        })
        self.assertEqual(error.code, "auth_context_missing")
        self.assertEqual(error.page_state, "LOGGED_OUT")
        self.assertEqual(str(error), "登录上下文缺失，需要重新发起登录")

    @unittest.skipUnless(shutil.which("node"), "需要 Node.js 验证浏览器诊断脚本")
    def test_browser_diagnostics_share_error_patterns_with_python(self):
        from core.auth.browser.submission_recovery import _PAGE_SCRIPT

        script = """
const samples = JSON.parse(process.argv[1]);
global.location = {href:'https://auth.openai.com/log-in/password'};
global.performance = {getEntriesByType:() => []};
const read = new Function(JSON.parse(process.argv[2]));
const result = samples.map(text => {
  global.document = {body:{innerText:text},documentElement:{outerHTML:''},querySelectorAll:() => []};
  return read().error_markers;
});
process.stdout.write(JSON.stringify(result));
"""
        samples = ["Operation\n timed out", "इस पेज पर आगे बढ़ने के लिए ज़रूरी जानकारी नहीं है.", "重新登录"]
        result = subprocess.run([shutil.which("node"), "-e", script, json.dumps(samples), json.dumps(_PAGE_SCRIPT)],
                                capture_output=True, text=True, timeout=5, check=True)
        self.assertEqual(json.loads(result.stdout), [["auth_operation_timeout"], ["auth_context_missing"], []])
