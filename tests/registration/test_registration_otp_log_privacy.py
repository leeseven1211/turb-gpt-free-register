# -*- coding: utf-8 -*-
"""注册 OTP 处理只记录结果，不记录验证码或认证会话。"""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.auth.protocol import openai_auth
from core.registration import roxy


class _OtpResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        import json
        self.text = json.dumps(payload)

    def json(self):
        return self.payload

    def raise_for_status(self):
        raise RuntimeError(f"HTTP {self.status_code}")


class _OtpSession:
    def __init__(self, response):
        self.response = response
        self.sent_body = None

    def get_auth_headers(self, referer=""):
        return {"referer": referer}

    def post(self, _url, *, headers, data):
        self.sent_body = data
        return self.response


class RegistrationOtpLogPrivacyTests(unittest.TestCase):
    def test_protocol_success_log_excludes_code_and_auth_session(self):
        fake_code = "731842"
        fake_session = "fake-auth-session-context"
        payload = {
            "page": {"type": "about_you"},
            "oai-client-auth-session": {"context": fake_session},
        }
        session = _OtpSession(_OtpResponse(200, payload))

        with self.assertLogs(openai_auth.logger, level="INFO") as captured:
            result = openai_auth.validate_email_otp(session, fake_code)

        self.assertEqual(result, payload)
        self.assertIn(fake_code, session.sent_body)
        messages = "\n".join(captured.output)
        self.assertIn("about_you", messages)
        self.assertNotIn(fake_code, messages)
        self.assertNotIn(fake_session, messages)

    def test_protocol_invalid_code_log_and_exception_exclude_response_body(self):
        fake_code = "731842"
        fake_session = "fake-error-context"
        payload = {"error": {"code": "invalid_otp", "message": "验证码错误", "context": fake_session}}
        session = _OtpSession(_OtpResponse(400, payload))

        with self.assertLogs(openai_auth.logger, level="INFO") as captured:
            with self.assertRaises(openai_auth.EmailOtpInvalidError) as caught:
                openai_auth.validate_email_otp(session, fake_code)

        messages = "\n".join(captured.output)
        self.assertIn("invalid_otp", messages)
        self.assertNotIn(fake_code, messages)
        self.assertNotIn(fake_session, messages)
        self.assertNotIn(fake_session, str(caught.exception))

    def test_protocol_response_labels_do_not_accept_arbitrary_text(self):
        fake_session = "fake-session-context"
        success = _OtpSession(_OtpResponse(200, {
            "page": {"type": f"about_you {fake_session}"},
        }))
        failure = _OtpSession(_OtpResponse(400, {
            "error": {"code": f"invalid_otp {fake_session}"},
        }))

        with self.assertLogs(openai_auth.logger, level="INFO") as captured:
            openai_auth.validate_email_otp(success, "731842")
            with self.assertRaises(openai_auth.EmailOtpInvalidError) as caught:
                openai_auth.validate_email_otp(failure, "731842")

        self.assertNotIn(fake_session, "\n".join(captured.output))
        self.assertNotIn(fake_session, str(caught.exception))

    def test_roxy_receiving_otp_does_not_log_code(self):
        fake_code = "731842"
        opened = SimpleNamespace(
            profile_id="test-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
            raw={},
            traffic_capture=None,
            account_bound=False,
        )
        driver = MagicMock()
        driver.current_url = "https://auth.openai.com/email-verification"
        client = MagicMock()
        with ExitStack() as stack:
            stack.enter_context(patch("core.registration.service.report_job_progress"))
            stack.enter_context(patch("core.registration.service.report_job_otp_evidence"))
            stack.enter_context(patch("core.registration.service.report_registered_account"))
            stack.enter_context(patch("core.registration.service.is_stop_requested", return_value=False))
            stack.enter_context(patch("core.browser.traffic.bind_roxy_capture"))
            stack.enter_context(patch("core.registration.debug.attach_current_roxy"))
            stack.enter_context(patch("core.registration.debug.pause_current_failure"))
            stack.enter_context(patch("core.browser.data_saver.BrowserDataSaver"))
            stack.enter_context(patch("core.registration.plan_capture.install_selenium"))
            stack.enter_context(patch("core.email.provider.retain_email"))
            stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened))
            stack.enter_context(patch.object(roxy, "_build_driver", return_value=driver))
            for name in (
                "_center_browser_window", "_safe_get", "human_delay", "_page_warmup",
                "_maybe_accept", "_check_manual_stop", "_clear_otp_inputs", "_type_otp",
                "_click_continue", "_quit_driver",
            ):
                stack.enter_context(patch.object(roxy, name))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="email_otp"))
            stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(roxy, "_wait_email_otp_page_ready", return_value="ready"))
            stack.enter_context(patch.object(roxy, "wait_for_otp", return_value=fake_code))
            stack.enter_context(patch.object(roxy, "_wait_after_email_otp_submit", side_effect=RuntimeError("测试在提交验证码后结束")))
            with self.assertLogs(roxy.logger, level="INFO") as captured:
                result = roxy.run_roxy_registration(
                    "alias@example.test",
                    "Test User",
                    "2000-01-01",
                    proxy="http://pool.example:8080",
                    registration_options={"password_enabled": False, "twofa_enabled": False, "codex_enabled": False, "plan_check_enabled": False},
                    email_source="icloud_hide",
                )

        self.assertFalse(result["success"])
        messages = "\n".join(captured.output)
        self.assertIn("收到验证码", messages)
        self.assertNotIn(fake_code, messages)


if __name__ == "__main__":
    unittest.main()
