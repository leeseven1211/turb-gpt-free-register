# -*- coding: utf-8 -*-
import tempfile
import unittest
import json
import traceback
from pathlib import Path
from unittest.mock import Mock, call, patch

from core import codex_retry_service
from core.account_export import (
    TwofaEnrollmentAuthRequired,
    TwofaProtocolHTTPError,
    TwofaProtocolTransportError,
)


class _Response:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or (json.dumps(payload) if payload is not None else "")

    def json(self):
        return self._payload


class ProtocolDirectTwofaTests(unittest.TestCase):
    @staticmethod
    def _route():
        route = Mock(
            proxy_url="http://proxy.example",
            provider="test",
            region="US",
            mode="pool",
        )
        route.public_dict.return_value = {
            "network_route": "proxy",
            "proxy_used": "http://proxy.example",
        }
        return route

    def _run_worker(
        self,
        *,
        account,
        fallback_enabled,
        protocol_side_effect=None,
        existing_action=None,
        protocol_reauth_enabled=True,
        steps=None,
        twofa_driver_override=None,
        oauth_driver="roxy",
    ):
        route = self._route()
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        protocol_session = Mock()
        action = existing_action or Mock()
        db_mocks = {
            "get_account_by_email": Mock(return_value=account),
            "update_account_totp_secret": Mock(return_value=True),
            "update_account_twofa_status": Mock(return_value=True),
            "update_account_session": Mock(return_value=True),
        }

        def setup_protocol(_session, access_token, *, on_secret):
            self.assertEqual("saved-chatgpt-token", access_token)
            if protocol_side_effect is not None:
                raise protocol_side_effect
            on_secret(secret)
            return secret

        def setup_reauth(_session, email, *, on_secret, on_access_token):
            self.assertEqual("a@example.com", email)
            on_access_token("fresh-chatgpt-token")
            on_secret(secret)
            return secret

        with tempfile.TemporaryDirectory() as tempdir, patch.object(
            codex_retry_service.db, "get_account_by_email", db_mocks["get_account_by_email"]
        ), patch.object(
            codex_retry_service.db, "update_account_totp_secret", db_mocks["update_account_totp_secret"]
        ), patch.object(
            codex_retry_service.db, "update_account_twofa_status", db_mocks["update_account_twofa_status"]
        ), patch.object(
            codex_retry_service.db, "update_account_session", db_mocks["update_account_session"]
        ), patch.object(codex_retry_service.account_task_store, "get_task", return_value={}), patch.object(
            codex_retry_service.account_task_store, "append_event"
        ) as append_event, patch("config.reload_all"), patch(
            "config.codex.CODEX_OAUTH_DRIVER", oauth_driver
        ), patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy"), patch(
            "config.account.ACCOUNT_2FA_DRIVER", "protocol_direct"
        ), patch(
            "config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", fallback_enabled
        ), patch(
            "config.account.ACCOUNT_2FA_PROTOCOL_REAUTH_ENABLED", protocol_reauth_enabled
        ), patch(
            "core.account_proxy.acquire_account_proxy", return_value=route
        ), patch(
            "core.account_export.setup_2fa_protocol", side_effect=setup_protocol
        ) as setup_protocol_mock, patch(
            "core.account_export.setup_2fa", side_effect=setup_reauth
        ) as setup_reauth_mock, patch(
            "core.session.BrowserSession", return_value=protocol_session
        ) as browser_session, patch(
            "core.roxy_codex_oauth.run_roxy_chatgpt_account_action"
        ) as run_browser, patch.object(
            codex_retry_service, "check_stop_requested"
        ):
            result = codex_retry_service.run_twofa_worker(
                "a@example.com",
                target_log_path=Path(tempdir) / "twofa.log",
                task_id=101,
                steps=steps or {"twofa"},
                manage_task=False,
                clear_log=False,
                twofa_driver_override=twofa_driver_override,
            )

        return (
            result,
            route,
            db_mocks,
            append_event,
            setup_protocol_mock,
            setup_reauth_mock,
            browser_session,
            run_browser,
            action,
        )

    def test_existing_at_uses_protocol_without_opening_roxy(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        result, route, db_mocks, _events, setup_protocol, _reauth, browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("existing_at", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_called_once()
        browser_session.assert_called_once_with(proxy="http://proxy.example")
        run_browser.assert_not_called()
        self.assertEqual(
            db_mocks["update_account_totp_secret"].call_args_list,
            [
                call("a@example.com", "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", setup_pending=True),
                call("a@example.com", "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP", setup_pending=False),
            ],
        )
        db_mocks["update_account_twofa_status"].assert_called_once_with(
            "a@example.com", "success", "Authenticator 2FA 已启用"
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_protocol_enroll_retries_transient_http_failure(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.side_effect = [
            _Response({"error": "temporary"}, status_code=503),
            _Response({"secret": "JBSWY3DPEHPK3PXP", "session_id": "sid"}),
        ]
        with patch.object(account_export, "_clear_twofa_session_circuit") as reset, patch.object(
            account_export.time, "sleep"
        ):
            result = account_export._enroll_totp(session, "access-token")

        self.assertEqual(("JBSWY3DPEHPK3PXP", "sid"), result)
        self.assertEqual(2, session.post.call_count)
        reset.assert_called_once_with(session, source="MFA enroll")

    def test_protocol_enroll_retry_log_does_not_expose_proxy_credentials(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.side_effect = [
            RuntimeError("Proxy CONNECT aborted: http://proxy-user:proxy-pass@1.2.3.4:8080"),
            _Response({"secret": "JBSWY3DPEHPK3PXP", "session_id": "sid"}),
        ]
        with patch.object(account_export, "_clear_twofa_session_circuit"), patch.object(
            account_export.time, "sleep"
        ), self.assertLogs(account_export.logger, level="WARNING") as captured:
            account_export._enroll_totp(session, "access-token")

        rendered = "\n".join(captured.output)
        self.assertNotIn("proxy-user", rendered)
        self.assertNotIn("proxy-pass", rendered)
        self.assertNotIn("1.2.3.4", rendered)

    def test_protocol_enroll_retry_exhaustion_does_not_expose_proxy_credentials(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.side_effect = [
            RuntimeError("Proxy CONNECT aborted: http://proxy-user:proxy-pass@1.2.3.4:8080"),
            RuntimeError("SSL closed via http://proxy-user:proxy-pass@1.2.3.4:8080"),
        ]
        with patch.object(account_export, "_clear_twofa_session_circuit"), patch.object(
            account_export.time, "sleep"
        ), self.assertRaises(TwofaProtocolTransportError) as raised:
            account_export._enroll_totp(session, "access-token")

        rendered = str(raised.exception)
        self.assertNotIn("proxy-user", rendered)
        self.assertNotIn("proxy-pass", rendered)
        self.assertNotIn("1.2.3.4", rendered)
        rendered_traceback = "".join(traceback.format_exception(raised.exception))
        self.assertNotIn("proxy-user", rendered_traceback)
        self.assertNotIn("proxy-pass", rendered_traceback)
        self.assertNotIn("1.2.3.4", rendered_traceback)

    def test_protocol_http_error_redacts_sensitive_detail_fields(self):
        from core import account_export

        response = _Response({
            "error": {
                "code": "invalid_request",
                "type": "validation_error",
                "detail": (
                    "user@example.com Bearer "
                    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature "
                    "via http://proxy-user:proxy-pass@1.2.3.4:8080"
                ),
            }
        }, status_code=400)

        error = account_export._twofa_http_error("activate", response)
        rendered = str(error)
        self.assertNotIn("user@example.com", rendered)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", rendered)
        self.assertNotIn("proxy-user", rendered)
        self.assertNotIn("proxy-pass", rendered)
        self.assertIn("invalid_request", rendered)

    def test_protocol_activate_retries_a_code_or_session_400_once(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.side_effect = [
            _Response({"detail": "invalid verification code"}, status_code=400),
            _Response({"success": True}),
        ]
        totp = Mock()
        totp.now.side_effect = ["111111", "222222"]
        with patch.object(account_export.pyotp, "TOTP", return_value=totp), patch.object(
            account_export, "_wait_for_next_totp_window"
        ) as wait_window:
            self.assertTrue(account_export._activate_totp(session, "access-token", "secret", "sid"))

        self.assertEqual(2, session.post.call_count)
        wait_window.assert_called_once_with()
        first_body = json.loads(session.post.call_args_list[0].kwargs["data"])
        second_body = json.loads(session.post.call_args_list[1].kwargs["data"])
        self.assertEqual("111111", first_body["code"])
        self.assertEqual("222222", second_body["code"])

    def test_protocol_activate_retries_transient_http_failure(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.side_effect = [
            _Response({"error": "temporary"}, status_code=503),
            _Response({"success": True}),
        ]
        totp = Mock()
        totp.now.return_value = "111111"
        with patch.object(account_export.pyotp, "TOTP", return_value=totp), patch.object(
            account_export, "_clear_twofa_session_circuit"
        ) as reset, patch.object(account_export.time, "sleep"), patch.object(
            account_export, "_wait_for_next_totp_window"
        ) as wait_window:
            self.assertTrue(account_export._activate_totp(session, "access-token", "secret", "sid"))

        self.assertEqual(2, session.post.call_count)
        reset.assert_called_once_with(session, source="MFA activate")
        wait_window.assert_not_called()

    def test_protocol_activate_does_not_retry_generic_invalid_request(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.return_value = _Response(
            {"error": {"type": "invalid_request"}},
            status_code=400,
        )
        with patch.object(account_export.pyotp, "TOTP") as totp, patch.object(
            account_export, "_wait_for_next_totp_window"
        ) as wait_window, self.assertRaises(TwofaProtocolHTTPError):
            totp.return_value.now.return_value = "111111"
            account_export._activate_totp(session, "access-token", "secret", "sid")

        session.post.assert_called_once()
        wait_window.assert_not_called()

    def test_protocol_activate_does_not_retry_top_level_invalid_request(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.return_value = _Response(
            {"error": "invalid_request"},
            status_code=400,
        )
        with patch.object(account_export.pyotp, "TOTP") as totp, patch.object(
            account_export, "_wait_for_next_totp_window"
        ) as wait_window, self.assertRaises(TwofaProtocolHTTPError) as raised:
            totp.return_value.now.return_value = "111111"
            account_export._activate_totp(session, "access-token", "secret", "sid")

        self.assertEqual("invalid_request", raised.exception.error_code)
        session.post.assert_called_once()
        wait_window.assert_not_called()

    def test_reauth_otp_business_403_is_not_retried(self):
        from core import account_export

        session = Mock()
        session.get_auth_headers.return_value = {}
        session.post.return_value = _Response(
            {"error": {"code": "invalid_otp"}},
            status_code=403,
        )
        with patch("config.twofa.TWOFA_REAUTH_MAX_ATTEMPTS", 3, create=True), patch.object(
            account_export.time, "sleep"
        ), self.assertRaises(TwofaProtocolHTTPError):
            account_export._validate_reauth_otp_with_retry(session, "123456")

        session.post.assert_called_once()

    def test_reauth_unknown_exception_traceback_is_redacted(self):
        from core import account_export

        session = Mock()
        leaked = RuntimeError(
            "unexpected adapter failure at http://proxy-user:proxy-pass@1.2.3.4:8080"
        )
        with patch("config.twofa.TWOFA_REAUTH_MAX_ATTEMPTS", 1, create=True), patch.object(
            account_export,
            "_trigger_reauth",
            side_effect=leaked,
        ), self.assertRaises(RuntimeError) as raised:
            account_export._trigger_reauth_with_retry(session, "a@example.com")

        rendered = "".join(traceback.format_exception(raised.exception))
        self.assertNotIn("proxy-user", rendered)
        self.assertNotIn("proxy-pass", rendered)
        self.assertNotIn("1.2.3.4", rendered)

    def test_protocol_enroll_exposes_classified_error_without_retrying_business_4xx(self):
        from core import account_export

        session = Mock()
        session.device_id = "device"
        session.navigator_language.return_value = "en-US"
        session.get_chatgpt_headers.return_value = {}
        session.post.return_value = _Response(
            {"error": {"code": "feature_disabled", "type": "invalid_request"}},
            status_code=400,
        )
        with self.assertRaises(TwofaProtocolHTTPError) as raised:
            account_export._enroll_totp(session, "access-token")

        self.assertEqual(400, raised.exception.status_code)
        self.assertEqual("feature_disabled", raised.exception.error_code)
        session.post.assert_called_once()

    def test_browser_setup_retries_connection_closed_with_a_new_route(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "already-set",
            "extra_json": "{}",
        }
        route = self._route()
        with tempfile.TemporaryDirectory() as tempdir, patch.object(
            codex_retry_service.db, "get_account_by_email", return_value=account
        ), patch.object(codex_retry_service.account_task_store, "get_task", return_value={}), patch.object(
            codex_retry_service.account_task_store, "append_event"
        ) as append_event, patch("config.reload_all"), patch(
            "config.account.ACCOUNT_PASSWORD_DRIVER", "roxy"
        ), patch(
            "core.account_proxy.acquire_account_proxy", return_value=route
        ) as acquire_route, patch(
            "core.roxy_codex_oauth.run_roxy_chatgpt_account_action",
            side_effect=[RuntimeError("WebDriverException: net::ERR_CONNECTION_CLOSED"), None],
        ) as run_browser, patch.object(
            codex_retry_service, "check_stop_requested"
        ), patch.object(codex_retry_service.time, "sleep"):
            result = codex_retry_service.run_twofa_worker(
                "a@example.com",
                target_log_path=Path(tempdir) / "password.log",
                task_id=101,
                steps={"password"},
                manage_task=False,
                clear_log=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(2, run_browser.call_count)
        self.assertEqual(2, acquire_route.call_count)
        self.assertEqual(1, result["browser_retry_attempts"])
        route.release.assert_any_call(reason="browser-retry-1")
        route.release.assert_any_call(reason="twofa-retry-a@example.com")
        retry_events = [call.kwargs for call in append_event.call_args_list if call.kwargs.get("stage") == "browser_retry"]
        self.assertEqual(1, len(retry_events))
        self.assertEqual("err_connection_closed", retry_events[0]["detail"]["reason_code"])

    def test_missing_at_uses_protocol_reauthentication_without_opening_roxy(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "",
            "totp_secret": "",
            "extra_json": "{}",
        }
        result, route, db_mocks, _events, setup_protocol, setup_reauth, browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("protocol_reauth", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_not_called()
        setup_reauth.assert_called_once()
        browser_session.assert_called_once_with(proxy="http://proxy.example")
        run_browser.assert_not_called()
        db_mocks["update_account_session"].assert_called_once_with(
            "a@example.com", "fresh-chatgpt-token"
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_protocol_failure_without_fallback_never_opens_roxy(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        result, route, db_mocks, _events, setup_protocol, _reauth, browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=False,
            protocol_side_effect=RuntimeError("AT rejected"),
        )

        self.assertFalse(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("existing_at", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_called_once()
        browser_session.assert_called_once_with(proxy="http://proxy.example")
        run_browser.assert_not_called()
        db_mocks["update_account_twofa_status"].assert_called_once()
        self.assertEqual("failed", db_mocks["update_account_twofa_status"].call_args.args[1])
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_protocol_failure_with_fallback_enters_existing_roxy_path(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        action = Mock()
        with patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=action) as build_action:
            result, route, _db_mocks, _events, setup_protocol, _reauth, _browser_session, run_browser, _action = self._run_worker(
                account=account,
                fallback_enabled=True,
                protocol_side_effect=RuntimeError("recent auth required"),
                existing_action=action,
            )

        self.assertTrue(result["ok"])
        self.assertEqual("browser_fallback", result["twofa_driver"])
        self.assertTrue(result["browser_opened"])
        setup_protocol.assert_called_once()
        run_browser.assert_called_once()
        build_action.assert_called_once_with(
            "a@example.com",
            101,
            proxy="http://proxy.example",
            include_password=False,
            include_twofa=True,
            twofa_driver="browser",
            browser_fallback_enabled=True,
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_enroll_401_uses_protocol_reauth_and_persists_fresh_at(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        result, route, db_mocks, events, setup_protocol, setup_reauth, browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=True,
            protocol_side_effect=TwofaEnrollmentAuthRequired("recent auth required"),
        )

        self.assertTrue(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("protocol_reauth", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_called_once()
        setup_reauth.assert_called_once()
        browser_session.assert_called_once_with(proxy="http://proxy.example")
        run_browser.assert_not_called()
        db_mocks["update_account_session"].assert_called_once_with(
            "a@example.com", "fresh-chatgpt-token"
        )
        self.assertTrue(any(
            item.kwargs.get("stage") == "token"
            and item.kwargs.get("detail", {}).get("source") == "protocol_reauth"
            for item in events.call_args_list
        ))

    def test_protocol_direct_legacy_value_maps_to_protocol_for_password_and_twofa(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        action = Mock()
        with patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=action) as build_action:
            result, route, _db_mocks, _events, _setup_protocol, _reauth, _browser_session, run_browser, _action = self._run_worker(
                account=account,
                fallback_enabled=True,
                existing_action=action,
                steps={"password", "twofa"},
            )

        self.assertTrue(result["ok"])
        run_browser.assert_called_once()
        build_action.assert_called_once_with(
            "a@example.com",
            101,
            proxy="http://proxy.example",
            include_password=True,
            include_twofa=True,
            twofa_driver="protocol",
            browser_fallback_enabled=True,
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_explicit_browser_mode_uses_browser_security_page(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        action = Mock()
        with patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=action) as build_action:
            result, route, _db_mocks, _events, setup_protocol, _reauth, browser_session, run_browser, _action = self._run_worker(
                account=account,
                fallback_enabled=True,
                existing_action=action,
                twofa_driver_override="browser",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("browser", result["twofa_driver"])
        self.assertEqual("browser_session", result["auth_source"])
        self.assertTrue(result["browser_opened"])
        setup_protocol.assert_not_called()
        browser_session.assert_not_called()
        run_browser.assert_called_once()
        build_action.assert_called_once_with(
            "a@example.com",
            101,
            proxy="http://proxy.example",
            include_password=False,
            include_twofa=True,
            twofa_driver="browser",
            browser_fallback_enabled=True,
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_password_twofa_is_not_blocked_by_independent_codex_protocol_driver(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        action = Mock()
        with patch.object(codex_retry_service, "_build_roxy_account_setup", return_value=action) as build_action:
            result, route, _db_mocks, _events, setup_protocol, _reauth, browser_session, run_browser, _action = self._run_worker(
                account=account,
                fallback_enabled=True,
                existing_action=action,
                steps={"password", "twofa"},
                oauth_driver="protocol",
            )

        self.assertTrue(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("browser_session", result["auth_source"])
        setup_protocol.assert_not_called()
        browser_session.assert_not_called()
        run_browser.assert_called_once()
        build_action.assert_called_once_with(
            "a@example.com",
            101,
            proxy="http://proxy.example",
            include_password=True,
            include_twofa=True,
            twofa_driver="protocol",
            browser_fallback_enabled=True,
        )
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_enroll_401_without_protocol_reauth_uses_existing_fallback_policy(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "",
            "extra_json": "{}",
        }
        result, route, _db_mocks, _events, setup_protocol, setup_reauth, _browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=False,
            protocol_reauth_enabled=False,
            protocol_side_effect=TwofaEnrollmentAuthRequired("recent auth required"),
        )

        self.assertFalse(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("existing_at", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_called_once()
        setup_reauth.assert_not_called()
        run_browser.assert_not_called()
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")

    def test_existing_totp_is_skipped_without_protocol_or_browser(self):
        account = {
            "id": 9,
            "email": "a@example.com",
            "access_token": "saved-chatgpt-token",
            "totp_secret": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
            "extra_json": "{}",
        }
        result, route, db_mocks, _events, setup_protocol, _reauth, browser_session, run_browser, _action = self._run_worker(
            account=account,
            fallback_enabled=True,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("protocol", result["twofa_driver"])
        self.assertEqual("existing_at", result["auth_source"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_not_called()
        browser_session.assert_not_called()
        run_browser.assert_not_called()
        db_mocks["update_account_totp_secret"].assert_not_called()
        db_mocks["update_account_twofa_status"].assert_not_called()
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")


if __name__ == "__main__":
    unittest.main()
