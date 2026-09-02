# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from core import codex_retry_service
from core.account_export import TwofaEnrollmentAuthRequired


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
            "config.codex.CODEX_OAUTH_DRIVER", "roxy"
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
                steps={"twofa"},
                manage_task=False,
                clear_log=False,
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
        self.assertEqual("protocol_direct", result["twofa_driver"])
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
        self.assertEqual("protocol_direct", result["twofa_driver"])
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
        self.assertEqual("protocol_reauth", result["twofa_driver"])
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
        self.assertEqual("protocol_direct", result["twofa_driver"])
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
        self.assertEqual("protocol_direct", result["twofa_driver"])
        self.assertFalse(result["browser_opened"])
        setup_protocol.assert_not_called()
        browser_session.assert_not_called()
        run_browser.assert_not_called()
        db_mocks["update_account_totp_secret"].assert_not_called()
        db_mocks["update_account_twofa_status"].assert_not_called()
        route.release.assert_called_once_with(reason="twofa-retry-a@example.com")


if __name__ == "__main__":
    unittest.main()
