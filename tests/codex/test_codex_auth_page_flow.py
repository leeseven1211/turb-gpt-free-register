"""Codex 真实编排在模拟 Auth 服务中保留页面状态，避免仅验证包装器。"""
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth


def response(payload, url="https://auth.openai.com/api/accounts/authorize/continue", status=200):
    return SimpleNamespace(status_code=status, url=url, headers={}, text=json.dumps(payload), json=lambda: payload)


class AuthPageFlowTests(unittest.TestCase):
    def test_external_follow_payload_preserves_auth_page_and_existing_workspace_cache(self):
        from core.codex.auth_page import CodexAuthPageSession

        for value in ("external-page", ""):
            with self.subTest(auth_page=value):
                external_response = response({
                    "continue_url": "/add-phone?auth_page=" + value,
                    "oai-client-auth-session": {"workspaces": [{"id": "existing-workspace"}]},
                }, url="https://bridge.example.test/continue")
                base = SimpleNamespace(
                    get_auth_headers=lambda **_: {}, get_auth_navigate_headers=lambda **_: {},
                    get=Mock(return_value=external_response),
                    session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _: None)),
                )
                session = CodexAuthPageSession(base)
                session.observe_url("/log-in?auth_page=selected-page")

                result = oauth._follow_login_continue_step(session, "https://bridge.example.test/continue", "state")

                self.assertEqual(result, ("phone", ""))
                self.assertEqual(session.get_auth_headers().get("OpenAI-Auth-Page"), "selected-page")
                self.assertEqual(session._codex_auth_session_payload, {"workspaces": [{"id": "existing-workspace"}]})
                base.get.assert_called_once_with(
                    "https://bridge.example.test/continue", headers={}, allow_redirects=False,
                )

    def test_auth_api_query_only_continuation_does_not_become_document_context(self):
        from core.codex.auth_page import CodexAuthPageSession

        session = CodexAuthPageSession(SimpleNamespace(get_auth_headers=lambda **_: {}))
        session.observe_url("/log-in?auth_page=selected-page")
        oauth._cache_auth_session_metadata(session, response(
            {"continue_url": "?auth_page=api-page"},
            url="https://auth.openai.com/api/accounts/continue",
        ))
        self.assertEqual(session.get_auth_headers()["OpenAI-Auth-Page"], "selected-page")

    def test_metadata_without_explicit_https_origin_cannot_supply_auth_page(self):
        from core.codex.auth_page import CodexAuthPageSession

        for url in (None, "", "/api/accounts/continue", "//auth.openai.com/api/accounts/continue"):
            with self.subTest(response_url=url):
                session = CodexAuthPageSession(SimpleNamespace(get_auth_headers=lambda **_: {}))
                session.observe_url("/log-in?auth_page=selected-page")
                oauth._cache_auth_session_metadata(session, response({"continue_url": "/add-phone?auth_page=unproven-page"}, url=url))
                self.assertEqual(session.get_auth_headers()["OpenAI-Auth-Page"], "selected-page")

    def test_actual_protocol_flow_uses_bootstrap_and_latest_continuation_page(self):
        requests = []

        def post(url, *, headers, **kwargs):
            requests.append((url, dict(headers)))
            if url.endswith("/authorize/continue"):
                return response({"page": {"type": "add_phone"}, "continue_url": "/add-phone?auth_page=phone-page"})
            return response({"error": {"code": "invalid_state", "message": "Synthetic controlled rejection"}}, url=url, status=409)

        base = SimpleNamespace(
            device_id="synthetic-device", auth_session_logging_id="synthetic-session",
            get_auth_headers=lambda **_: {}, get_auth_navigate_headers=lambda **_: {},
            get=Mock(return_value=response({}, url="https://auth.openai.com/log-in?auth_page=bootstrap-page")),
            post=post, session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _: None), close=Mock()),
        )
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth, "BrowserSession", return_value=base))
            for name in ("network_preflight", "human_delay", "check_cancelled", "report_stage"):
                stack.enter_context(patch.object(oauth, name))
            stack.enter_context(patch.object(oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(oauth, "request_sentinel_token", return_value={}))
            stack.enter_context(patch.object(oauth, "build_sentinel_header", return_value=("synthetic-sentinel", None)))
            stack.enter_context(patch.object(oauth.sms_provider, "_http", return_value=SimpleNamespace(close=Mock())))
            acquire = stack.enter_context(patch.object(oauth.sms_provider, "acquire_number", return_value=("synthetic-order", "15550001234")))
            stack.enter_context(patch.object(oauth.sms_provider, "cancel"))
            result = oauth.run_codex_oauth("account@example.test", proxy="", driver_override="protocol", force=True)

        self.assertEqual(requests[0][1].get("OpenAI-Auth-Page"), "bootstrap-page")
        self.assertEqual(requests[1][1].get("OpenAI-Auth-Page"), "phone-page")
        self.assertEqual(result["auth_diagnostics"]["server_code"], "invalid_state")
        self.assertEqual(acquire.call_count, 1)
        self.assertNotIn("phone-page", str(result))

    def test_shared_password_and_mfa_helpers_receive_each_updated_page(self):
        from core.codex.auth_page import CodexAuthPageSession

        requests = []

        def post(url, *, headers, **kwargs):
            requests.append((url, dict(headers)))
            if url.endswith("/password/verify"):
                return response({"page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
                                 "continue_url": "/mfa-challenge/factor-1?auth_page=mfa-page"})
            if url.endswith("/mfa/verify"):
                return response({"page": {"type": "add_phone"}, "continue_url": "/add-phone?auth_page=phone-page"})
            return response({})

        base = SimpleNamespace(
            get_auth_headers=lambda **_: {}, get_auth_navigate_headers=lambda **_: {}, post=post,
            get=Mock(return_value=response({}, url="https://auth.openai.com/log-in/password?auth_page=password-page")),
            session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _: None)),
        )
        session = CodexAuthPageSession(base)
        with patch("core.accounts.liveness.protocol.v2.request_sentinel_token", return_value={}), patch(
            "core.accounts.liveness.protocol.v2.build_sentinel_header", return_value=("synthetic-sentinel", None)
        ), patch("core.accounts.liveness.protocol.v2._totp_code", return_value="123456"), patch.object(
            oauth, "report_stage"
        ), patch.object(oauth, "check_cancelled"):
            step = oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password?auth_page=password-page",
                login_password="synthetic-password", login_totp_secret="synthetic-secret",
            )

        self.assertEqual([item[1].get("OpenAI-Auth-Page") for item in requests], ["password-page", "mfa-page", "mfa-page"])
        self.assertEqual(step[:2], ("phone", "/add-phone?auth_page=phone-page"))
        self.assertEqual(session.get_auth_headers()["OpenAI-Auth-Page"], "phone-page")
