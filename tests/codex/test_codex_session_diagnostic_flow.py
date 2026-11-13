"""真实 Codex 编排的按次诊断在任何购号/授权副作用前停止。"""
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth


def response(payload, url, status=200):
    return SimpleNamespace(status_code=status, url=url, headers={}, text=json.dumps(payload), json=lambda: payload)


class DiagnosticFlowTests(unittest.TestCase):
    def _run(self, *, mfa=True, dump_error=None, continue_url="/add-phone", login_error=None):
        calls = []

        def get(url, **kwargs):
            calls.append(("GET", url))
            if url.endswith("/client_auth_session_dump"):
                if dump_error:
                    raise dump_error
                return response({"client_auth_session": {"is_authenticated": True}, "checksum": "synthetic-private-checksum", "session_id": "synthetic-private-session"}, url)
            return response({}, "https://auth.openai.com/log-in/password")

        def post(url, **kwargs):
            calls.append(("POST", url))
            if url.endswith("/password/verify"):
                if login_error:
                    raise login_error
                return response({"page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}}, "continue_url": "/mfa-challenge/factor-1"}, url)
            if url.endswith("/mfa/verify"):
                return response({"page": {"type": "add_phone" if continue_url == "/add-phone" else "email_otp_send"}, "continue_url": continue_url}, url)
            return response({}, url)

        close = Mock()
        base = SimpleNamespace(
            get=get, post=post, get_auth_headers=lambda **_: {}, get_auth_navigate_headers=lambda **_: {},
            device_id="synthetic-device", auth_session_logging_id="synthetic-logging", close=close,
            document_navigation_id="synthetic-document",
            session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _: None), close=close),
        )
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth, "BrowserSession", return_value=base))
            for name in ("network_preflight", "human_delay", "check_cancelled", "report_stage", "_bootstrap_authorize"):
                stack.enter_context(patch.object(oauth, name))
            stack.enter_context(patch.object(oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(oauth, "_submit_email", return_value=("password", "/log-in/password", 100) if mfa else ("phone", "/add-phone", 100)))
            stack.enter_context(patch("core.accounts.liveness.protocol.v2.request_sentinel_token", return_value={}))
            stack.enter_context(patch("core.accounts.liveness.protocol.v2.build_sentinel_header", return_value=("synthetic-sentinel", None)))
            stack.enter_context(patch("core.accounts.liveness.protocol.v2._totp_code", return_value="123456"))
            phone = stack.enter_context(patch.object(oauth, "_do_phone_verification"))
            acquire = stack.enter_context(patch.object(oauth.sms_provider, "acquire_number"))
            select = stack.enter_context(patch.object(oauth, "_select_workspace_and_get_callback"))
            exchange = stack.enter_context(patch.object(oauth, "exchange_codex_token"))
            save = stack.enter_context(patch.object(oauth, "save_codex_credential"))
            send = stack.enter_context(patch.object(oauth, "navigate_email_otp_send"))
            result = oauth.run_codex_oauth(
                "account@example.test", proxy="", force=True, driver_override="protocol",
                login_password="synthetic-password", login_totp_secret="synthetic-secret", diagnostic_after_mfa=True,
            )
        for action in (phone, acquire, select, exchange, save, send):
            action.assert_not_called()
        close.assert_called_once()
        self.assertFalse(result["ok"])
        self.assertFalse(result["credential_confirmed"])
        self.assertFalse(result["callback_submitted"])
        self.assertNotIn("synthetic-private-", str(result))
        return result, calls

    def test_mfa_query_happens_once_and_stops_before_phone(self):
        result, calls = self._run()
        self.assertEqual("interrupted", result["status"])
        self.assertTrue(result["diagnostic_complete"])
        self.assertEqual(1, sum(url.endswith("/client_auth_session_dump") for _, url in calls))

    def test_dump_transport_failure_still_stops_without_phone(self):
        result, calls = self._run(dump_error=RuntimeError("synthetic-private-error"))
        self.assertEqual("interrupted", result["status"])
        self.assertEqual(1, sum(url.endswith("/client_auth_session_dump") for _, url in calls))

    def test_no_mfa_stops_without_dump_or_phone(self):
        result, calls = self._run(mfa=False)
        self.assertEqual("interrupted", result["status"])
        self.assertFalse(any(url.endswith("/client_auth_session_dump") for _, url in calls))

    def test_mfa_next_email_send_does_not_send_before_diagnostic_stop(self):
        result, _ = self._run(continue_url="/api/accounts/email-otp/send")
        self.assertEqual("interrupted", result["status"])

    def test_diagnostic_error_does_not_trigger_cpa_relogin(self):
        result, calls = self._run(login_error=RuntimeError("Timeout waiting for OAuth callback"))
        self.assertEqual("attention_required", result["status"])
        self.assertEqual(1, sum(url.endswith("/password/verify") for _, url in calls))
        self.assertTrue(result["session_diagnostics"]["stages"]["primary_verify"]["observed"])
