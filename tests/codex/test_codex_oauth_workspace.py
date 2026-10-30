# -*- coding: utf-8 -*-
import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth as codex_oauth


class _FakeResponse:
    def __init__(self, payload=None, *, status_code=200, headers=None, text=""):
        self._payload = payload or {}
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeCookies:
    jar = []

    def __init__(self, values):
        self._values = iter(values)

    def get(self, name):
        return next(self._values)


class CodexOAuthWorkspaceTests(unittest.TestCase):
    def test_post_json_caches_auth_session_metadata(self):
        response = _FakeResponse({
            "oai-client-auth-session": {
                "workspaces": [{"id": "workspace-from-response"}],
            },
        })
        session = SimpleNamespace(
            get_auth_headers=Mock(return_value={}),
            post=Mock(return_value=response),
        )

        result = codex_oauth._post_json(
            session,
            "https://auth.openai.com/api/accounts/phone-otp/validate",
            {"code": "123456"},
            referer="https://auth.openai.com/phone-verification",
        )

        self.assertIs(result, response)
        self.assertEqual(
            "workspace-from-response",
            session._codex_auth_session_payload["workspaces"][0]["id"],
        )

    def test_workspace_id_falls_back_to_cached_auth_metadata(self):
        cookies = _FakeCookies([None])
        session = SimpleNamespace(
            session=SimpleNamespace(cookies=cookies),
            _codex_auth_session_payload={
                "workspaces": [{"id": "workspace-from-cache"}],
            },
        )

        with patch.object(codex_oauth, "_WORKSPACE_COOKIE_WAIT_SECONDS", 0):
            result = codex_oauth._get_workspace_id(session)

        self.assertEqual("workspace-from-cache", result)

    def test_workspace_id_waits_for_cookie_before_failing(self):
        payload = {"workspaces": [{"id": "workspace-from-cookie"}]}
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload).encode("utf-8")
        ).decode("ascii").rstrip("=")
        cookies = _FakeCookies([None, encoded + ".signature"])
        session = SimpleNamespace(
            session=SimpleNamespace(cookies=cookies),
            _codex_auth_session_payload={},
        )

        with patch.object(codex_oauth, "_WORKSPACE_COOKIE_WAIT_SECONDS", 1.0), patch.object(
            codex_oauth, "_WORKSPACE_POLL_INTERVAL_SECONDS", 0.2
        ), patch.object(codex_oauth.time, "monotonic", side_effect=[100.0, 100.1]), patch.object(
            codex_oauth.time, "sleep"
        ) as wait:
            result = codex_oauth._get_workspace_id(session)

        self.assertEqual("workspace-from-cookie", result)
        wait.assert_called_once_with(0.2)

    def test_phone_verification_returns_validation_payload(self):
        http = SimpleNamespace(close=Mock())
        send_response = _FakeResponse({})
        validation_response = _FakeResponse({
            "continue_url": "/sign-in-with-chatgpt/codex/consent",
        })

        with patch.object(codex_oauth.sms_provider, "_http", return_value=http), patch.object(
            codex_oauth.sms_provider, "acquire_number", return_value=("activation-1", "15500000000")
        ), patch.object(codex_oauth.sms_provider, "set_status"), patch.object(
            codex_oauth.sms_provider, "wait_for_sms_code", return_value="123456"
        ), patch.object(codex_oauth.sms_provider, "complete"), patch.object(
            codex_oauth, "_post_json", side_effect=[send_response, validation_response]
        ), patch.object(codex_oauth, "check_cancelled"), patch.object(
            codex_oauth._cfg, "SMS_MAX_RETRIES", 1
        ):
            result = codex_oauth._do_phone_verification(object())

        self.assertEqual(validation_response.json(), result)
        http.close.assert_called_once_with()

    def test_login_continue_follows_redirect_to_callback(self):
        callback_url = "http://localhost:1455/auth/callback?code=abc&state=state-1"
        session = SimpleNamespace(
            get_auth_navigate_headers=Mock(return_value={}),
            get=Mock(return_value=_FakeResponse(headers={"Location": callback_url})),
        )

        result = codex_oauth._follow_login_continue(
            session, "/api/accounts/continue", "state-1"
        )

        self.assertEqual(callback_url, result)
        session.get.assert_called_once_with(
            "https://auth.openai.com/api/accounts/continue",
            headers={},
            allow_redirects=False,
        )


if __name__ == "__main__":
    unittest.main()
