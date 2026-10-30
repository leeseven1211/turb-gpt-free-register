# -*- coding: utf-8 -*-
"""Codex Protocol 登录挑战的本地响应模拟测试。"""
import base64
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth as codex_oauth


class CodexOAuthChallengeTests(unittest.TestCase):
    def _submit_with_response(self, payload, *, status_code=200):
        response = SimpleNamespace(status_code=status_code, json=lambda: payload)
        with patch.object(codex_oauth, "request_sentinel_token", return_value={}), patch.object(
            codex_oauth, "build_sentinel_header", return_value=("sentinel", None)
        ), patch.object(codex_oauth, "_post_json", return_value=response), patch.object(
            codex_oauth.time, "time", return_value=100.0
        ), patch.object(codex_oauth, "navigate_email_otp_send") as send:
            step = codex_oauth._submit_email(object(), "account@example.test")
        return step, send

    def _run_after_login(
        self, step, next_url, *, follow_result=None, otp_payload=None,
        phone_payload=None, workspace_payload=None, workspace_cookie=None,
    ):
        callback = "http://localhost:1455/auth/callback?code=private-code&state=state"
        otp_provider = Mock(return_value="123456")
        with ExitStack() as stack:
            browser = stack.enter_context(patch.object(codex_oauth, "BrowserSession"))
            browser.return_value.session.cookies.jar = (
                [SimpleNamespace(name="oai-client-auth-session", value=workspace_cookie)]
                if workspace_cookie else []
            )
            browser.return_value.session.cookies.get.return_value = None
            browser.return_value._codex_auth_session_payload = workspace_payload or {}
            stack.enter_context(patch.object(codex_oauth, "check_cancelled"))
            stack.enter_context(patch.object(codex_oauth, "report_stage"))
            stack.enter_context(patch.object(codex_oauth, "human_delay"))
            stack.enter_context(patch.object(codex_oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(codex_oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(codex_oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(codex_oauth, "network_preflight"))
            stack.enter_context(patch.object(codex_oauth, "_bootstrap_authorize"))
            stack.enter_context(patch.object(
                codex_oauth, "_submit_email", return_value=(step, next_url, 100.0)
            ))
            if follow_result is not None:
                stack.enter_context(patch.object(
                    codex_oauth, "_follow_login_continue_step", return_value=follow_result
                ))
            if otp_payload is not None:
                stack.enter_context(patch.object(
                    codex_oauth, "_submit_email_otp", return_value=otp_payload
                ))
            select = stack.enter_context(patch.object(
                codex_oauth, "_select_workspace_and_get_callback", return_value=callback
            ))
            phone = stack.enter_context(patch.object(codex_oauth, "_do_phone_verification"))
            if phone_payload is not None:
                phone.return_value = phone_payload
            stack.enter_context(patch.object(
                codex_oauth, "exchange_codex_token", side_effect=RuntimeError("换 token 前模拟停止")
            ))
            result = codex_oauth.run_codex_oauth(
                "account@example.test", otp_provider=otp_provider,
                proxy="", force=True, driver_override="protocol",
            )
        return result, select, phone, otp_provider

    def test_direct_email_verification_waits_without_extra_send(self):
        result, send = self._submit_with_response({
            "page": {"type": "email_verification"},
            "continue_url": "/email-verification",
        })
        self.assertEqual(result, ("verify", "/email-verification", 100.0))
        send.assert_not_called()

    def test_email_send_follows_only_confirmed_auth_route(self):
        result, send = self._submit_with_response({
            "page": {"type": "email_otp_send"},
            "continue_url": "/api/accounts/email-otp/send",
        })
        self.assertEqual(result, ("verify", "", 100.0))
        send.assert_called_once_with(
            unittest.mock.ANY,
            continue_url="/api/accounts/email-otp/send",
            referer="https://auth.openai.com/log-in",
        )

    def test_password_challenge_does_not_wait_or_send_email(self):
        result, send = self._submit_with_response({
            "page": {"type": "login_password"},
            "continue_url": "/log-in/password",
        })
        self.assertEqual(result, ("password", "/log-in/password", 100.0))
        send.assert_not_called()

    def test_workspace_select_is_reserved_for_existing_post_flow(self):
        result, send = self._submit_with_response({
            "continue_url": "/api/accounts/workspace/select",
        })
        self.assertEqual(result, ("workspace", "", 100.0))
        send.assert_not_called()

    def test_callback_log_keeps_path_without_authorization_code(self):
        path = codex_oauth._url_path_for_log(
            "http://localhost:1455/auth/callback?code=private-code&state=private-state"
        )
        self.assertEqual(path, "/auth/callback")

    def test_continue_json_callback_needs_no_workspace_cookie(self):
        callback = "http://localhost:1455/auth/callback?code=private-code&state=state"
        response = SimpleNamespace(
            status_code=200,
            url="https://auth.openai.com/api/accounts/continue",
            headers={},
            json=lambda: {"continue_url": callback},
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=response),
            session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _key: None)),
        )
        with self.assertLogs(codex_oauth.logger, level="INFO") as captured:
            step, url = codex_oauth._follow_login_continue_step(
                session, "/api/accounts/continue", "state"
            )
        self.assertEqual((step, url), ("callback", callback))
        diagnostic = "\n".join(captured.output)
        self.assertIn("status=200", diagnostic)
        self.assertIn("page_type=unknown", diagnostic)
        self.assertIn("path=/api/accounts/continue", diagnostic)
        self.assertIn("cookie=False cache=False", diagnostic)
        self.assertNotIn("private-code", diagnostic)
        self.assertNotIn("state=state", diagnostic)
        session.get.assert_called_once()

    def test_continue_json_workspace_requires_explicit_selection(self):
        response = SimpleNamespace(
            status_code=200,
            url="https://auth.openai.com/api/accounts/continue",
            headers={},
            json=lambda: {"continue_url": "/api/accounts/workspace/select"},
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=response),
        )
        self.assertEqual(
            codex_oauth._follow_login_continue_step(session, "/api/accounts/continue", "state"),
            ("workspace", ""),
        )
        session.get.assert_called_once()

    def test_continue_phone_challenge_does_not_get_send_endpoint(self):
        response = SimpleNamespace(
            status_code=200,
            url="https://auth.openai.com/api/accounts/continue",
            headers={},
            json=lambda: {"continue_url": "/api/accounts/add-phone/send"},
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=response),
        )
        self.assertEqual(
            codex_oauth._follow_login_continue_step(session, "/api/accounts/continue", "state"),
            ("phone", ""),
        )
        session.get.assert_called_once()

    def test_continue_consent_without_next_step_stops_before_workspace(self):
        result, select, phone, _ = self._run_after_login(
            "continue", "/api/accounts/continue", follow_result=("consent", ""),
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("需使用浏览器驱动", result["message"])
        self.assertNotIn("private-code", result["message"])
        self.assertEqual(result["cause_code"], "codex_consent_unverifiable")
        self.assertEqual(result["auth_diagnostics"]["operation"], "consent")
        select.assert_not_called()
        phone.assert_not_called()

    def _consent_session(self, workspaces, *, cookie_workspaces=None, status=200, path=None):
        cookie = None
        if cookie_workspaces is not None:
            cookie = base64.urlsafe_b64encode(
                json.dumps({"workspaces": cookie_workspaces}).encode()
            ).decode().rstrip("=") + ".signature"
        response = SimpleNamespace(
            status_code=status,
            url="https://auth.openai.com" + (path or "/sign-in-with-chatgpt/codex/consent"),
            headers={"content-type": "text/html"},
            json=lambda: {},
        )
        return SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get_auth_headers=Mock(return_value={}),
            get=Mock(return_value=response),
            post=Mock(),
            session=SimpleNamespace(cookies=SimpleNamespace(jar=[], get=lambda _key: cookie)),
            _codex_auth_session_payload={"workspaces": workspaces},
        )

    def test_observed_consent_selects_unique_workspace_and_validates_callback(self):
        # 浏览器实测：consent 页提交 workspace_id，响应 JSON 直接给 callback。
        callback = "http://localhost:1455/auth/callback?code=private-code&state=state"
        for source in ("cache", "cookie"):
            with self.subTest(source=source):
                workspaces = [{"id": "private-workspace"}]
                session = self._consent_session(
                    workspaces if source == "cache" else [],
                    cookie_workspaces=workspaces if source == "cookie" else None,
                )
                session.post.return_value = SimpleNamespace(
                    status_code=200, headers={},
                    json=lambda: {"continue_url": callback},
                )
                with self.assertLogs(codex_oauth.logger, level="INFO") as captured:
                    step, url = codex_oauth._follow_login_continue_step(
                        session, "/sign-in-with-chatgpt/codex/consent", "state",
                    )
                    self.assertEqual((step, url), ("workspace", "private-workspace"))
                    # 确认后的提交始终使用同一 ID，不重新从变化后的缓存中选首项。
                    session._codex_auth_session_payload = {"workspaces": [{"id": "later-workspace"}]}
                    actual = codex_oauth._select_workspace_and_get_callback(session, "state", workspace_id=url)
                self.assertEqual(actual, callback)
                session.post.assert_called_once()
                self.assertEqual(session.post.call_args.args[0], "https://auth.openai.com/api/accounts/workspace/select")
                self.assertEqual(json.loads(session.post.call_args.kwargs["data"]), {"workspace_id": "private-workspace"})
                diagnostic = "\n".join(captured.output)
                for secret in ("private-workspace", "private-code", "state=state"):
                    self.assertNotIn(secret, diagnostic)

    def test_consent_missing_or_ambiguous_workspaces_still_requires_browser(self):
        for workspaces, cookie_workspaces in (
            ([], None),
            ([{"id": "one"}, {"id": "two"}], None),
            ([{"id": "one"}], [{"id": "two"}]),
            ([{"id": "one"}], [{"id": "one"}, {"id": "two"}]),
            ([{"id": "one"}, {}], None),
        ):
            with self.subTest(workspaces=workspaces, cookie_workspaces=cookie_workspaces):
                session = self._consent_session(workspaces, cookie_workspaces=cookie_workspaces)
                self.assertEqual(codex_oauth._follow_login_continue_step(
                    session, "/sign-in-with-chatgpt/codex/consent", "state",
                ), ("consent", ""))
                session.post.assert_not_called()

    def test_consent_non_200_or_explicit_challenge_does_not_select_workspace(self):
        for status, payload in (
            (204, {}), (302, {}),
            (200, {"page": {"type": "login_password"}}),
            (200, {"page": {"type": "mfa_challenge"}}),
            (200, {"page": {"type": "phone_verification"}}),
            (200, {"error": {"code": "challenge_pending"}}),
        ):
            with self.subTest(status=status, payload=payload):
                session = self._consent_session([{"id": "one"}], status=status)
                session.get.return_value.json = lambda: payload
                self.assertEqual(codex_oauth._follow_login_continue_step(
                    session, "/sign-in-with-chatgpt/codex/consent", "state",
                ), ("consent", ""))
                session.post.assert_not_called()

    def test_consent_selected_workspace_rejects_mismatched_callback_state(self):
        session = self._consent_session([{"id": "one"}])
        callback = "http://localhost:1455/auth/callback?code=private-code&state=other-private-state"
        session.post.return_value = SimpleNamespace(
            status_code=200, headers={}, json=lambda: {"continue_url": callback},
        )
        step, workspace_id = codex_oauth._follow_login_continue_step(
            session, "/sign-in-with-chatgpt/codex/consent", "expected-state",
        )
        self.assertEqual(step, "workspace")
        with self.assertRaises(RuntimeError) as raised:
            codex_oauth._select_workspace_and_get_callback(
                session, "expected-state", workspace_id=workspace_id,
            )
        self.assertNotIn("private-code", str(raised.exception))
        self.assertNotIn("other-private-state", str(raised.exception))

    def test_consent_confirmed_workspace_reaches_selection_in_main_flow(self):
        _, select, phone, _ = self._run_after_login(
            "continue", "/sign-in-with-chatgpt/codex/consent",
            follow_result=("workspace", "confirmed-workspace"),
        )
        self.assertEqual(select.call_args.kwargs, {"workspace_id": "confirmed-workspace"})
        phone.assert_not_called()

    def test_only_successful_exact_consent_page_can_select_cached_workspace(self):
        for status, path in ((403, None), (200, "/unknown-consent")):
            with self.subTest(status=status, path=path):
                session = self._consent_session([{"id": "one"}], status=status, path=path)
                with self.assertRaises(RuntimeError):
                    codex_oauth._follow_login_continue_step(
                        session, "/sign-in-with-chatgpt/codex/consent", "state",
                    )
                session.post.assert_not_called()

    def test_direct_callback_skips_workspace_selection(self):
        callback = "http://localhost:1455/auth/callback?code=private-code&state=state"
        result, select, phone, _ = self._run_after_login(
            "continue", "/api/accounts/continue", follow_result=("callback", callback),
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("换 token 前模拟停止", result["message"])
        select.assert_not_called()
        phone.assert_not_called()

    def test_only_explicit_workspace_step_selects_workspace(self):
        result, select, phone, _ = self._run_after_login("workspace", "")
        self.assertEqual(result["status"], "failed")
        select.assert_called_once()
        phone.assert_not_called()

    def test_empty_phone_response_without_workspace_stops_safely(self):
        result, select, phone, _ = self._run_after_login(
            "phone", "/add-phone", phone_payload={},
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("未确认后续地址或工作区", result["message"])
        select.assert_not_called()
        phone.assert_called_once()

    def test_empty_phone_response_uses_existing_workspace_id(self):
        cookie = base64.urlsafe_b64encode(
            b'{"workspaces":[{"id":"workspace-1"}]}'
        ).decode().rstrip("=") + ".payload.signature"
        for source, options in (
            ("cache", {"workspace_payload": {"workspaces": [{"id": "workspace-1"}]}}),
            ("cookie", {"workspace_cookie": cookie}),
        ):
            with self.subTest(source=source):
                result, select, phone, _ = self._run_after_login(
                    "phone", "/add-phone", phone_payload={}, **options,
                )
                self.assertEqual(result["status"], "failed")
                self.assertIn("换 token 前模拟停止", result["message"])
                select.assert_called_once()
                phone.assert_called_once()

    def test_empty_email_otp_response_does_not_trigger_phone_provider(self):
        result, select, phone, otp_provider = self._run_after_login(
            "verify", "/email-verification", otp_payload={},
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("未返回明确下一步", result["message"])
        otp_provider.assert_called_once()
        select.assert_not_called()
        phone.assert_not_called()

    def test_untrusted_continue_location_is_rejected_without_echo(self):
        response = SimpleNamespace(
            status_code=302,
            url="https://auth.openai.com/api/accounts/continue",
            headers={"Location": "https://untrusted.example/private-code?state=private-state"},
            json=lambda: {},
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=response),
        )
        with self.assertLogs(codex_oauth.logger, level="INFO") as captured:
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._follow_login_continue_step(session, "/api/accounts/continue", "state")
        self.assertNotIn("private-code", str(raised.exception))
        self.assertNotIn("private-state", str(raised.exception))
        self.assertNotIn("private-code", "\n".join(captured.output))
        self.assertNotIn("private-state", "\n".join(captured.output))
        session.get.assert_called_once()

    def test_untrusted_response_origin_is_rejected_before_metadata_cache(self):
        response = SimpleNamespace(
            status_code=200,
            url="https://untrusted.example/api/accounts/continue",
            headers={},
            json=lambda: {"auth_session": {"workspaces": [{"id": "private-workspace"}]}},
        )
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=response),
        )
        with self.assertRaises(RuntimeError):
            codex_oauth._follow_login_continue_step(session, "/api/accounts/continue", "state")
        self.assertFalse(hasattr(session, "_codex_auth_session_payload"))

    def test_callback_error_does_not_echo_query(self):
        location = "http://localhost:1455/auth/callback?state=private-state&trace=private-value"
        with self.assertRaises(RuntimeError) as raised:
            codex_oauth._extract_code(location, "private-state")
        self.assertNotIn("private-state", str(raised.exception))
        self.assertNotIn("private-value", str(raised.exception))

    def test_callback_requires_present_matching_state(self):
        callback = "http://localhost:1455/auth/callback?code=private-code"
        with self.assertRaises(RuntimeError) as missing:
            codex_oauth._extract_code(callback, "expected-state")
        with self.assertRaises(RuntimeError) as mismatch:
            codex_oauth._extract_code(callback + "&state=other-state", "expected-state")
        with self.assertRaises(RuntimeError) as duplicate:
            codex_oauth._extract_code(
                callback + "&state=expected-state&state=other-state", "expected-state"
            )
        self.assertNotIn("private-code", str(missing.exception))
        self.assertNotIn("other-state", str(mismatch.exception))
        self.assertNotIn("other-state", str(duplicate.exception))
        self.assertEqual(
            codex_oauth._extract_code(callback + "&state=expected-state", "expected-state"),
            "private-code",
        )

    def test_phone_verification_logs_omit_number_and_activation(self):
        response = SimpleNamespace(status_code=200, text="", json=lambda: {})
        with patch.object(codex_oauth.sms_provider, "_http", return_value=Mock()), patch.object(
            codex_oauth.sms_provider, "acquire_number", return_value=("private-activation", "15550000000")
        ), patch.object(codex_oauth.sms_provider, "set_status"), patch.object(
            codex_oauth.sms_provider, "wait_for_sms_code", return_value="123456"
        ), patch.object(codex_oauth.sms_provider, "complete"), patch.object(
            codex_oauth, "_post_json", side_effect=[response, response]
        ), patch.object(codex_oauth, "_sms_provider_name", return_value="mock"), patch.object(
            codex_oauth, "check_cancelled"
        ), self.assertLogs(codex_oauth.logger, level="INFO") as captured:
            self.assertEqual(codex_oauth._do_phone_verification(Mock()), {})
        diagnostic = "\n".join(captured.output)
        self.assertIn("provider=mock", diagnostic)
        self.assertNotIn("15550000000", diagnostic)
        self.assertNotIn("private-activation", diagnostic)

    def test_sub2_callback_summary_excludes_unknown_payload(self):
        summary = codex_oauth._summarize_sub2_response({
            "message": "private-secret", "credential": "private-token", "success": True,
        })
        self.assertEqual(summary, "success=true")

    def test_cpa_callback_failure_keeps_retry_category_without_remote_body(self):
        response = SimpleNamespace(
            status_code=409,
            json=lambda: {"message": "timeout waiting for oauth callback private-token"},
            text="private-token",
        )
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"), patch.object(
            codex_oauth, "_cpa_management_key", return_value="private-key"
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._cpa_request_json("POST", "/v0/management/oauth-callback", {})
        message = str(raised.exception)
        self.assertNotIn("private-token", message)
        self.assertIn("category=oauth_callback_timeout", message)
        self.assertTrue(codex_oauth._is_cpa_callback_reauth_error(raised.exception))

    def test_sub2_failure_does_not_echo_remote_response(self):
        response = SimpleNamespace(
            status_code=502,
            json=lambda: {"detail": "private-token"},
            text="private-token",
        )
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_sub2_codex_base", return_value="https://sub2.example.test"), patch.object(
            codex_oauth, "_sub2_codex_headers", return_value={}
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._sub2_codex_request_json("POST", "/callback", {})
        self.assertNotIn("private-token", str(raised.exception))
        self.assertIn("status=502", str(raised.exception))

    def test_cpa_auth_file_download_failure_does_not_echo_remote_response(self):
        response = SimpleNamespace(status_code=502, text="private-token")
        session = Mock(request=Mock(return_value=response), close=Mock())
        with patch.object(codex_oauth, "_cpa_management_origin", return_value="https://cpa.example.test"), patch.object(
            codex_oauth, "_cpa_management_key", return_value="private-key"
        ), patch.object(codex_oauth.curl_requests, "Session", return_value=session):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._cpa_request_raw("GET", "/v0/management/auth-files/download")
        self.assertNotIn("private-token", str(raised.exception))
        self.assertIn("status=502", str(raised.exception))

    def test_unknown_or_untrusted_step_does_not_send_email(self):
        for payload in (
            {},
            {"page": {"type": "email_otp_send"}},
            {"continue_url": "https://untrusted.example/api/accounts/email-otp/send"},
            {"continue_url": "https://auth.openai.com:bad/email-verification"},
            {"page": {"type": "login_password"}, "continue_url": "/api/accounts/email-otp/send"},
            {"page": {"type": "phone_verification"}, "continue_url": "/sign-in-with-chatgpt/codex/consent"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(RuntimeError) as raised:
                    self._submit_with_response(payload)
                self.assertNotIn("untrusted.example", str(raised.exception))

    def test_saved_password_can_continue_without_email_otp(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        with patch("core.accounts.credentials.get_account_login_credentials", return_value=("private-password", "")), patch(
            "core.accounts.liveness.protocol.v2._password_verify",
            return_value={"continue_url": "/api/accounts/continue"},
        ) as verify:
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password?state=opaque"
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        verify.assert_called_once_with(session, "private-password")
        self.assertEqual(
            session.get.call_args.args[0],
            "https://auth.openai.com/log-in/password?state=opaque",
        )

    def test_saved_password_mfa_uses_existing_totp_protocol(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        password_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "/mfa-challenge/factor-1",
        }
        with patch("core.accounts.credentials.get_account_login_credentials", return_value=("private-password", "private-secret")), patch(
            "core.accounts.liveness.protocol.v2._password_verify", return_value=password_result,
        ), patch("core.accounts.liveness.protocol.v2._mfa_issue_challenge") as issue, patch(
            "core.accounts.liveness.protocol.v2._totp_code", return_value="123456"
        ), patch("core.accounts.liveness.protocol.v2._mfa_verify", return_value={
            "continue_url": "/api/accounts/continue",
            "auth_session": {
                "workspaces": [{"id": "workspace-1", "private": "do-not-cache"}],
                "private": "do-not-cache",
            },
        }) as verify, patch.object(codex_oauth, "report_stage"), patch.object(
            codex_oauth, "check_cancelled"
        ):
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password"
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        issue.assert_called_once_with(session, "factor-1")
        verify.assert_called_once_with(session, "factor-1", "123456")
        self.assertEqual(session._codex_auth_session_payload, {
            "workspaces": [{"id": "workspace-1"}],
        })

    def test_password_response_caches_only_workspace_id(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        password_result = {
            "continue_url": "/api/accounts/continue",
            "auth_session": {
                "workspaces": [{"id": "workspace-1", "private": "do-not-cache"}],
                "private": "do-not-cache",
            },
        }
        with patch("core.accounts.liveness.protocol.v2._password_verify", return_value=password_result):
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password",
                login_password="private-password",
            )
        self.assertEqual(step[0], "continue")
        self.assertEqual(session._codex_auth_session_payload, {
            "workspaces": [{"id": "workspace-1"}],
        })

    def test_new_registration_credentials_need_no_database_read(self):
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        password_result = {
            "page": {"type": "mfa_challenge", "payload": {"factor_id": "factor-1"}},
            "continue_url": "/mfa-challenge/factor-1",
        }
        with patch("core.accounts.credentials.get_account_login_credentials") as saved, patch(
            "core.accounts.liveness.protocol.v2._password_verify", return_value=password_result
        ) as password_verify, patch(
            "core.accounts.liveness.protocol.v2._mfa_issue_challenge"
        ), patch("core.accounts.liveness.protocol.v2._totp_code", return_value="123456") as totp_code, patch(
            "core.accounts.liveness.protocol.v2._mfa_verify", return_value={
                "continue_url": "/api/accounts/continue"
            }
        ), patch.object(codex_oauth, "report_stage"), patch.object(codex_oauth, "check_cancelled"):
            step = codex_oauth._verify_saved_login_password(
                session, "account@example.test", "/log-in/password",
                login_password="Password!123", login_totp_secret="private-secret",
            )
        self.assertEqual(step[0:2], ("continue", "/api/accounts/continue"))
        password_verify.assert_called_once_with(session, "Password!123")
        totp_code.assert_called_once_with("private-secret")
        saved.assert_not_called()

    def test_password_result_unknown_is_not_classified_as_failed(self):
        from core.accounts.liveness.protocol.v2 import ProtocolV2AuthError

        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=SimpleNamespace(
                status_code=200, url="https://auth.openai.com/log-in/password"
            )),
        )
        with patch(
            "core.accounts.liveness.protocol.v2._password_verify",
            side_effect=ProtocolV2AuthError("password_result_unknown"),
        ):
            with self.assertRaises(codex_oauth.CodexAuthResultUnknown):
                codex_oauth._verify_saved_login_password(
                    session, "account@example.test", "/log-in/password",
                    login_password="Password!123",
                )

    def test_email_otp_rejection_does_not_echo_code_or_response(self):
        response = SimpleNamespace(
            status_code=400,
            text="private response 123456",
            json=lambda: {"error": {"code": "invalid_code"}},
        )
        with patch.object(codex_oauth, "request_sentinel_token", return_value={}), patch.object(
            codex_oauth, "build_sentinel_header", return_value=("sentinel", None)
        ), patch.object(codex_oauth, "_post_json", return_value=response):
            with self.assertRaises(RuntimeError) as raised:
                codex_oauth._submit_email_otp(object(), "123456")
        self.assertNotIn("123456", str(raised.exception))
        self.assertNotIn("private response", str(raised.exception))

    def test_password_continue_skips_otp_and_phone_waiters(self):
        otp_provider = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_oauth, "BrowserSession"))
            stack.enter_context(patch.object(codex_oauth, "check_cancelled"))
            stack.enter_context(patch.object(codex_oauth, "report_stage"))
            stack.enter_context(patch.object(codex_oauth, "human_delay"))
            stack.enter_context(patch.object(codex_oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(codex_oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(codex_oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(codex_oauth, "network_preflight"))
            stack.enter_context(patch.object(codex_oauth, "_bootstrap_authorize"))
            stack.enter_context(patch.object(
                codex_oauth, "_submit_email", return_value=("password", "/log-in/password", 100.0)
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_verify_saved_login_password",
                return_value=("continue", "/api/accounts/continue", 101.0),
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_follow_login_continue_step", side_effect=RuntimeError("授权后续模拟停止")
            ))
            submit_otp = stack.enter_context(patch.object(codex_oauth, "_submit_email_otp"))
            phone = stack.enter_context(patch.object(codex_oauth, "_do_phone_verification"))
            result = codex_oauth.run_codex_oauth(
                "account@example.test",
                otp_provider=otp_provider,
                proxy="",
                force=True,
                driver_override="protocol",
            )
        self.assertEqual(result["status"], "failed")
        self.assertIn("授权后续模拟停止", result["message"])
        otp_provider.assert_not_called()
        submit_otp.assert_not_called()
        phone.assert_not_called()

    def test_password_post_unknown_requires_reconciliation(self):
        otp_provider = Mock()
        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_oauth, "BrowserSession"))
            stack.enter_context(patch.object(codex_oauth, "check_cancelled"))
            stack.enter_context(patch.object(codex_oauth, "report_stage"))
            stack.enter_context(patch.object(codex_oauth, "human_delay"))
            stack.enter_context(patch.object(codex_oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(codex_oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(codex_oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(codex_oauth, "network_preflight"))
            stack.enter_context(patch.object(codex_oauth, "_bootstrap_authorize"))
            stack.enter_context(patch.object(
                codex_oauth, "_submit_email", return_value=("password", "/log-in/password", 100.0)
            ))
            stack.enter_context(patch.object(
                codex_oauth, "_verify_saved_login_password",
                side_effect=codex_oauth.CodexAuthResultUnknown("结果未知"),
            ))
            submit_otp = stack.enter_context(patch.object(codex_oauth, "_submit_email_otp"))
            phone = stack.enter_context(patch.object(codex_oauth, "_do_phone_verification"))
            result = codex_oauth.run_codex_oauth(
                "account@example.test", otp_provider=otp_provider,
                proxy="", force=True, driver_override="protocol",
            )
        self.assertEqual(result["status"], "attention_required")
        self.assertEqual(result["outcome"], "request_unknown")
        self.assertTrue(result["reconcile_required"])
        otp_provider.assert_not_called()
        submit_otp.assert_not_called()
        phone.assert_not_called()


if __name__ == "__main__":
    unittest.main()
