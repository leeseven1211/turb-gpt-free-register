# -*- coding: utf-8 -*-
"""Rust 刷新驱动的契约：驱动解析、结果投影与桥接边界。"""
from __future__ import annotations

import unittest
from unittest import mock

from contracts.operation_drivers import operation_driver_options
from core.accounts.liveness import service as live_service
from core.kernels import registry
from core.kernels.rust.sentinel_rs import _rust_refresh_result, run_refresh_at
from contracts.kernel_catalog import operation_binding


class RustRefreshDriverTests(unittest.TestCase):
    def test_driver_is_exposed_third_option(self):
        self.assertIn(("rust", "Rust sentinel-rs"), operation_driver_options("refresh_at"))

    def test_binding_and_runner_are_fixed(self):
        binding = operation_binding("refresh_at", "rust")
        self.assertEqual((binding.kernel, binding.implementation, binding.variant), ("rust", "sentinel_rs", None))
        self.assertEqual(registry.resolve_operation_runner(binding), run_refresh_at)

    def test_resolve_refresh_driver_accepts_rust_and_aliases(self):
        for value in ("rust", "sentinel_rs", "sentinel-rs", "RUST"):
            self.assertEqual(live_service._resolve_refresh_driver(value), "rust", value)
        self.assertEqual(
            live_service._resolve_refresh_driver(None, config_snapshot={"refresh_driver": "rust"}),
            "rust",
        )
        self.assertEqual(live_service._refresh_driver_request("rust"), "rust")
        self.assertIsNone(live_service._refresh_protocol_version("browser_roxy"))

    def test_success_result_matches_v3_shape(self):
        payload = {
            "ok": True,
            "access_token": "at-1",
            "session": {"accessToken": "at-1", "user": {"id": "u-1"}, "account": {"id": "a-1"}},
            "cookies": [{"name": "c", "value": "v", "domain": "auth.openai.com"}],
            "session_reused": False,
            "methods": ["password", "email_otp"],
            "device_id": "d-1",
        }
        result = _rust_refresh_result(
            email="user@example.com", checked_at="2026-11-25T00:00:00+00:00",
            payload=payload, remote_started=True,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "live")
        self.assertEqual(result["access_token"], "at-1")
        self.assertEqual(result["auth_method"], "password_email_otp")
        self.assertEqual(result["live_check_driver"], "rust")
        self.assertEqual(result["password_auth_status"], "verified")
        self.assertEqual(result["email_otp_status"], "success")
        self.assertEqual(result["mfa_status"], "skipped")
        self.assertTrue(result["remote_request_started"])
        self.assertIn("auth", result)

    def test_failure_result_keeps_error_contract(self):
        payload = {
            "ok": False,
            "status": "failed",
            "error_code": "password_rejected",
            "error_category": "auth",
            "retryable": False,
            "roxy_fallback_allowed": False,
            "detail": "bad password",
        }
        result = _rust_refresh_result(
            email="user@example.com", checked_at="2026-11-25T00:00:00+00:00",
            payload=payload, remote_started=True,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "password_rejected")
        self.assertEqual(result["error_category"], "auth")
        self.assertFalse(result["roxy_fallback_allowed"])
        self.assertTrue(result["remote_request_started"])
        self.assertIn("rust_refresh", result["auth_diagnostics"]["operation"])

    def test_unknown_error_defaults_to_rust_code(self):
        result = _rust_refresh_result(
            email="user@example.com", checked_at="2026-11-25T00:00:00+00:00",
            payload={"ok": False}, remote_started=False,
        )
        self.assertEqual(result["error"], "protocol_rust_unknown_error")
        self.assertEqual(result["error_category"], "runtime")


class RustRefreshFacadeTests(unittest.TestCase):
    def test_facade_passes_cached_session_and_saves_new_cookies(self):
        payload = {
            "ok": True,
            "access_token": "at-new",
            "session": {
                "accessToken": "at-new",
                "user": {"id": "u-1", "email": "user@example.com"},
                "account": {"id": "a-1"},
            },
            "cookies": [{"name": "c", "value": "v", "domain": "auth.openai.com"}],
            "device_id": "d-new",
            "session_reused": False,
            "methods": ["password"],
        }
        calls = {}

        def fake_run(request, *, on_progress=None):
            calls["request"] = request
            if on_progress:
                on_progress("authenticate", "running", None)
            return payload

        hooks = []
        with mock.patch(
            "core.kernels.rust.sentinel_rs.bridge.run_refresh_protocol", side_effect=fake_run,
        ), mock.patch(
            "core.kernels.rust.sentinel_rs.bridge.resolve_binary", return_value="/bin/true",
        ), mock.patch(
            "core.storage.accounts.get_account",
            return_value={"id": 7, "email": "user@example.com", "user_id": "u-1", "chatgpt_account_id": "a-1"},
        ), mock.patch(
            "core.storage.accounts.get_account_by_email",
            return_value={"id": 7, "email": "user@example.com", "user_id": "u-1", "chatgpt_account_id": "a-1"},
        ), mock.patch(
            "core.accounts.credentials.get_account_login_credentials", return_value=("pw", "SECRET"),
        ), mock.patch(
            "core.storage.accounts.protocol_sessions.load_session",
            return_value={
                "cookies": [{"name": "old", "value": "1", "domain": "auth.openai.com"}],
                "device_id": "d-old",
                "browser_profile": {"locale": "en-US"},
            },
        ), mock.patch(
            "core.storage.accounts.protocol_sessions.save_session", return_value=True,
        ) as save:
            result = run_refresh_at(
                "user@example.com", proxy="http://proxy", account_id=7,
                on_authenticated=lambda value, session: (hooks.append((value, session)), value)[1],
            )

        self.assertTrue(result["ok"])
        self.assertEqual(calls["request"].device_id, "d-old")
        self.assertEqual(calls["request"].password, "pw")
        self.assertEqual(calls["request"].totp_secret, "SECRET")
        self.assertEqual(calls["request"].cookies[0]["name"], "old")
        self.assertEqual(len(hooks), 1)
        self.assertIsNone(hooks[0][1])
        self.assertTrue(save.called)

    def test_facade_surfaces_failure_without_raising(self):
        payload = {
            "ok": False,
            "error": "email_verification_required",
            "error_category": "email",
            "roxy_fallback_allowed": False,
        }
        with mock.patch(
            "core.kernels.rust.sentinel_rs.bridge.run_refresh_protocol", return_value=payload,
        ), mock.patch(
            "core.kernels.rust.sentinel_rs.bridge.resolve_binary", return_value="/bin/true",
        ), mock.patch(
            "core.storage.accounts.get_account", return_value={"id": 7, "email": "user@example.com"},
        ), mock.patch(
            "core.storage.accounts.get_account_by_email", return_value={"id": 7, "email": "user@example.com"},
        ), mock.patch(
            "core.accounts.credentials.get_account_login_credentials", return_value=("", ""),
        ), mock.patch(
            "core.storage.accounts.protocol_sessions.load_session", return_value=None,
        ):
            result = run_refresh_at("user@example.com", account_id=7)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "email_verification_required")
        self.assertEqual(result["error_category"], "email")


class RustRefreshProtocolBridgeTests(unittest.TestCase):
    def test_protocol_roundtrip_returns_structured_result(self):
        import json
        import os
        import stat
        import tempfile
        from pathlib import Path

        from core.kernels.rust.sentinel_rs.bridge import RefreshBridgeRequest, run_refresh_protocol

        with tempfile.TemporaryDirectory() as workdir:
            stub = Path(workdir) / "stub-refresh"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "print(json.dumps({'v':1,'type':'ready','data':{'capabilities':['refresh']}}),flush=True)\n"
                "start=json.loads(sys.stdin.readline())\n"
                "assert start['type']=='start'\n"
                "assert start['data']['email']=='user@example.com'\n"
                "print(json.dumps({'v':1,'type':'progress','data':{'stage':'session_cache','state':'running'}}),flush=True)\n"
                "print(json.dumps({'v':1,'type':'result','data':{'ok':True,'access_token':'at-1',"
                "'session':{'accessToken':'at-1'},'cookies':[],'methods':['session_cookie'],'session_reused':True}}),flush=True)\n",
                encoding="utf-8",
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            request = RefreshBridgeRequest(
                email="user@example.com", binary=stub, timeout_seconds=20,
                cookies=({"name": "c", "value": "1", "domain": "auth.openai.com"},),
            )
            stages = []
            result = run_refresh_protocol(request, on_progress=lambda s, st, d: stages.append((s, st)))
        self.assertTrue(result["ok"])
        self.assertEqual(result["access_token"], "at-1")
        self.assertEqual(stages, [("session_cache", "running")])

    def test_protocol_failure_payload_is_returned(self):
        import json
        import stat
        import tempfile
        from pathlib import Path

        from core.kernels.rust.sentinel_rs.bridge import RefreshBridgeRequest, run_refresh_protocol

        with tempfile.TemporaryDirectory() as workdir:
            stub = Path(workdir) / "stub-refresh"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "print(json.dumps({'v':1,'type':'ready','data':{}}),flush=True)\n"
                "sys.stdin.readline()\n"
                "print(json.dumps({'v':1,'type':'result_partial','data':{'ok':False,"
                "'error_code':'password_rejected','error_category':'auth','roxy_fallback_allowed':False}}),flush=True)\n",
                encoding="utf-8",
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            request = RefreshBridgeRequest(email="user@example.com", binary=stub, timeout_seconds=20)
            result = run_refresh_protocol(request)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "password_rejected")
        self.assertFalse(result["roxy_fallback_allowed"])


if __name__ == "__main__":
    unittest.main()
