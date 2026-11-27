# -*- coding: utf-8 -*-
"""改密专用刷新认证结果捕获契约测试。"""
from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from requests.cookies import RequestsCookieJar


EMAIL = "capture@example.test"
AUTH = "https://auth.openai.com"
CHAT = "https://chatgpt.com"
SESSION_INFO = {
    "accessToken": "fixture-at",
    "user": {"email": EMAIL, "id": "user-1"},
    "account": {"id": "account-1"},
}


class _Response:
    def __init__(self, payload=None, status=200, location=None):
        self.payload = payload
        self.status_code = status
        self.headers = {"location": location} if location else {}
        self.text = "{}"
        self.url = ""

    def json(self):
        return self.payload


class _Session:
    def __init__(self, routes=None):
        self.proxy = ""
        self.device_id = "device-1"
        self.browser_profile = {
            "screen_width": 1920,
            "screen_height": 1080,
            "device_pixel_ratio": 1,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "js_heap_size_limit": 4096000000,
        }
        self.session = SimpleNamespace(cookies=RequestsCookieJar(), close=self.close)
        self.session.cookies.set(
            "__Secure-next-auth.session-token",
            "cookie-1",
            domain="chatgpt.com",
            path="/",
        )
        self.routes = {
            ("GET", CHAT + "/api/auth/session"): _Response(SESSION_INFO),
            ("GET", AUTH + "/authorize/start"): _Response(
                status=302, location=AUTH + "/log-in/password"
            ),
            ("GET", AUTH + "/log-in/password"): _Response({}),
            ("POST", AUTH + "/api/accounts/password/verify"): _Response(
                {"continue_url": CHAT + "/api/auth/callback/openai"}
            ),
            ("GET", CHAT + "/api/auth/callback/openai"): _Response({}),
        }
        self.routes.update(routes or {})
        self.calls = []
        self.closed = False

    def close(self):
        self.closed = True

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.routes.get((method, url))
        if response is None:
            raise AssertionError(f"意外请求：{method} {url}")
        if isinstance(response, BaseException):
            raise response
        response.url = url
        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get_auth_headers(self, **kwargs):
        return {}

    get_auth_navigate_headers = get_auth_headers
    get_chatgpt_navigate_headers = get_auth_headers
    get_nextauth_headers = get_auth_headers


class ProtocolV3RefreshCaptureTests(TestCase):
    def setUp(self):
        from core.accounts.liveness.protocol import v3
        from core.accounts.liveness.protocol import v2

        self.v3 = v3
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.target = {
            "id": 7,
            "email": EMAIL,
            "user_id": "user-1",
            "chatgpt_account_id": "account-1",
        }
        for name in ("get_account", "get_account_by_email"):
            self.stack.enter_context(patch.object(v3.db, name, return_value=self.target))
        self.stack.enter_context(
            patch.object(
                v3,
                "get_account_login_credentials",
                return_value=("fixture-password", ""),
            )
        )
        self.stack.enter_context(patch.object(v3, "account_email_is_invalid", return_value=False))
        self.stack.enter_context(patch.object(v2, "request_sentinel_token", return_value={}))
        self.stack.enter_context(patch.object(v2, "build_sentinel_header", return_value=("fixture", None)))
        self.stack.enter_context(patch.object(v3, "send_email_otp"))
        self.stack.enter_context(patch.object(v3, "wait_for_otp", return_value="654321"))
        self.load = self.stack.enter_context(
            patch.object(v3.protocol_sessions, "load_session", return_value=None)
        )
        self.save = self.stack.enter_context(patch.object(v3.protocol_sessions, "save_session"))
        self.remember = self.stack.enter_context(
            patch.object(v3.device_profiles, "remember_session")
        )

    def _run(self, session, **kwargs):
        with patch.object(
            self.v3,
            "_network_preflight_with_retry",
            return_value=(session, AUTH + "/authorize/start"),
        ):
            return self.v3.refresh_access_token(EMAIL, account_id=7, proxy="", **kwargs)

    def _cache(self):
        return {
            "cookies": [
                {
                    "name": "__Secure-next-auth.session-token",
                    "value": "cached-cookie",
                    "domain": "chatgpt.com",
                    "path": "/",
                }
            ],
            "device_id": "device-1",
            "browser_profile": _Session().browser_profile,
            "user_id": "user-1",
            "chatgpt_account_id": "account-1",
        }

    def test_v3_opt_out_captures_fresh_session_without_private_store_side_effects(self):
        result = self._run(_Session(), persist_session=False, reuse_session=False)

        self.assertTrue(result["ok"], result)
        self.assertIn("_protocol_session", result)
        self.assertNotIn("_protocol_session", result["auth"])
        captured = result["_protocol_session"]
        self.assertEqual("device-1", captured["device_id"])
        self.assertEqual("user-1", captured["user_id"])
        self.assertEqual("account-1", captured["chatgpt_account_id"])
        self.assertEqual("cookie-1", captured["cookies"][0]["value"])
        self.save.assert_not_called()
        self.remember.assert_not_called()

    def test_v3_opt_out_does_not_load_old_cookie_session(self):
        self.load.return_value = self._cache()
        result = self._run(_Session(), persist_session=False, reuse_session=False)

        self.assertTrue(result["ok"], result)
        self.assertEqual("password", result["auth_method"])
        self.load.assert_not_called()
        self.save.assert_not_called()
        self.remember.assert_not_called()

    def test_v3_can_reuse_valid_cached_session_without_persisting_it(self):
        self.load.return_value = self._cache()
        cached = _Session()
        with patch.object(self.v3, "BrowserSession", return_value=cached):
            result = self.v3.refresh_access_token(
                EMAIL,
                account_id=7,
                proxy="",
                persist_session=False,
                reuse_session=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual("session_cookie", result["auth_method"])
        self.assertIn("_protocol_session", result)
        self.assertNotIn("_protocol_session", result["auth"])
        self.save.assert_not_called()
        self.remember.assert_not_called()


class RustRefreshCaptureTests(TestCase):
    def _payload(self, *, ok=True):
        if not ok:
            return {"ok": False, "error_code": "password_rejected", "error_category": "auth"}
        return {
            "ok": True,
            "access_token": "at-new",
            "session": {
                **SESSION_INFO,
            },
            "cookies": [
                {
                    "name": "session",
                    "value": "cookie-new",
                    "domain": "chatgpt.com",
                    "path": "/",
                }
            ],
            "device_id": "device-new",
            "browser_profile": {"user_agent": "fixture-agent"},
            "session_reused": False,
            "methods": ["password"],
        }

    def _patches(self, payload, *, cached=None, remembered=None):
        stack = ExitStack()
        calls = {}

        def fake_run(request, *, on_progress=None):
            calls["request"] = request
            return payload

        stack.enter_context(
            patch(
                "core.kernels.rust.sentinel_rs.bridge.run_refresh_protocol",
                side_effect=fake_run,
            )
        )
        stack.enter_context(
            patch(
                "core.kernels.rust.sentinel_rs.bridge.resolve_binary",
                return_value="/bin/true",
            )
        )
        stack.enter_context(
            patch(
                "core.storage.accounts.get_account",
                return_value={
                    "id": 7,
                    "email": EMAIL,
                    "user_id": "user-1",
                    "chatgpt_account_id": "account-1",
                },
            )
        )
        stack.enter_context(
            patch("core.storage.accounts.get_account_by_email", return_value={})
        )
        stack.enter_context(
            patch(
                "core.accounts.credentials.get_account_login_credentials",
                return_value=("pw", "SECRET"),
            )
        )
        stack.enter_context(
            patch("core.storage.accounts.protocol_sessions.load_session", return_value=cached or {})
        )
        stack.enter_context(
            patch("core.storage.accounts.device_profiles.load_profile", return_value=remembered or {})
        )
        save = stack.enter_context(
            patch("core.storage.accounts.protocol_sessions.save_session")
        )
        remember = stack.enter_context(
            patch("core.storage.accounts.device_profiles.remember_session")
        )
        return stack, save, remember, calls

    def test_rust_opt_out_captures_native_session_without_private_store_side_effects(self):
        from core.kernels.rust.sentinel_rs import run_refresh_at

        stack, save, remember, calls = self._patches(
            self._payload(),
            cached={
                "cookies": [{"name": "old", "value": "old-cookie", "domain": "chatgpt.com"}],
                "device_id": "old-device",
                "browser_profile": {"user_agent": "old-agent"},
            },
            remembered={"device_id": "remembered-device", "browser_profile": {"user_agent": "remembered-agent"}},
        )
        with stack:
            callbacks = []
            result = run_refresh_at(
                EMAIL,
                account_id=7,
                persist_session=False,
                reuse_session=False,
                on_authenticated=lambda value, session: (
                    callbacks.append((value, session)),
                    value,
                )[1],
            )

        self.assertTrue(result["ok"], result)
        captured = result["_protocol_session"]
        self.assertEqual("cookie-new", captured["cookies"][0]["value"])
        self.assertEqual("device-new", captured["device_id"])
        self.assertEqual({"user_agent": "fixture-agent"}, captured["browser_profile"])
        self.assertEqual("user-1", captured["user_id"])
        self.assertEqual("account-1", captured["chatgpt_account_id"])
        self.assertEqual([(result, None)], callbacks)
        self.assertEqual("remembered-device", calls["request"].device_id)
        self.assertEqual((), calls["request"].cookies)
        self.assertNotIn("_protocol_session", result["auth"])
        save.assert_not_called()
        remember.assert_not_called()

    def test_rust_opt_out_failure_does_not_attach_private_session_payload(self):
        from core.kernels.rust.sentinel_rs import run_refresh_at

        stack, save, remember, _ = self._patches(self._payload(ok=False))
        with stack:
            result = run_refresh_at(EMAIL, account_id=7, persist_session=False)

        self.assertFalse(result["ok"])
        self.assertNotIn("_protocol_session", result.get("auth", {}))
        save.assert_not_called()
        remember.assert_not_called()

    def test_rust_can_reuse_valid_cached_session_without_persisting_it(self):
        from core.kernels.rust.sentinel_rs import run_refresh_at

        cached = {
            "cookies": [{"name": "old", "value": "old-cookie", "domain": "chatgpt.com"}],
            "device_id": "old-device",
            "browser_profile": {"user_agent": "old-agent"},
        }
        payload = {
            **self._payload(),
            "session_reused": True,
            "methods": ["session_cookie"],
        }
        stack, save, remember, calls = self._patches(payload, cached=cached)
        with stack:
            result = run_refresh_at(
                EMAIL,
                account_id=7,
                persist_session=False,
                reuse_session=True,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual("session_cookie", result["auth_method"])
        self.assertEqual("old-device", calls["request"].device_id)
        self.assertEqual(1, len(calls["request"].cookies))
        self.assertNotIn("_protocol_session", result["auth"])
        self.assertIn("_protocol_session", result)
        save.assert_not_called()
        remember.assert_not_called()

    def test_password_reset_verification_wires_rust_capture_to_top_level_result(self):
        from core.accounts.password_setup import reset

        stack, save, remember, calls = self._patches(
            self._payload(),
            cached={
                "cookies": [{"name": "old", "value": "old-cookie", "domain": "chatgpt.com"}],
                "device_id": "old-device",
                "browser_profile": {"user_agent": "old-agent"},
            },
            remembered={"device_id": "remembered-device", "browser_profile": {"user_agent": "remembered-agent"}},
        )
        with (
            stack,
            patch("core.accounts.liveness.service._resolve_refresh_driver", return_value="rust"),
            patch(
                "core.accounts.credentials.get_account_totp_secret_candidate",
                return_value="",
            ),
        ):
            result = reset._run_password_verification(
                EMAIL,
                "Candidate-password-1",
                account={"id": 7, "email": EMAIL},
                proxy="http://proxy",
                proxy_supplier=None,
                identity={"device_id": "explicit-device", "browser_profile": {"user_agent": "explicit-agent"}},
                refresh_driver="rust",
            )

        self.assertTrue(result["ok"], result)
        self.assertIn("_protocol_session", result)
        self.assertNotIn("_protocol_session", result["auth"])
        self.assertEqual("explicit-device", calls["request"].device_id)
        self.assertEqual((), calls["request"].cookies)
        save.assert_not_called()
        remember.assert_not_called()
