# -*- coding: utf-8 -*-
import sys
import types
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import cloakbrowser_registration, skyvern_registration
from core.registration import browser_use, protocol, roxy
from core.account_export import persist_account_core


class EmailSourceCompatibilityTests(unittest.TestCase):
    email = "compat@example.test"
    email_source = "icloud_hide"

    def _run_roxy_resume(self, *, email_source=None):
        client = MagicMock()
        opened = SimpleNamespace(
            profile_id="compat-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
            account_bound=False,
            raw={},
        )
        driver = MagicMock()
        challenge = MagicMock(side_effect=RuntimeError("stop after resume challenge"))

        with ExitStack() as stack:
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch("core.registration_service.report_job_otp_evidence"))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            stack.enter_context(patch("core.registration_service.is_stop_requested", return_value=False))
            stack.enter_context(patch("core.registration_debug.attach_current_roxy"))
            stack.enter_context(patch("core.registration_debug.pause_current_failure"))
            stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened))
            stack.enter_context(patch.object(roxy, "_build_driver", return_value=driver))
            stack.enter_context(patch("core.browser_data_saver.BrowserDataSaver"))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch.object(roxy, "_center_browser_window"))
            stack.enter_context(patch.object(roxy, "_safe_get"))
            stack.enter_context(patch.object(roxy, "_page_warmup"))
            stack.enter_context(patch.object(roxy, "_maybe_accept"))
            stack.enter_context(patch.object(roxy, "_check_manual_stop"))
            stack.enter_context(patch.object(roxy, "human_delay"))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="login_password"))
            stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_is_email_verification_page", return_value=False))
            stack.enter_context(
                patch("core.roxy_codex_oauth.complete_openai_login_challenge", challenge)
            )
            stack.enter_context(patch("core.email_provider.retain_email"))
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                existing_password="StoredPassword!123",
                registration_options={
                    "password_enabled": True,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=email_source,
            )

        self.assertFalse(result["success"])
        challenge.assert_called_once()
        return challenge.call_args

    def test_roxy_resume_legacy_call_omits_otp_provider(self):
        call = self._run_roxy_resume()

        self.assertEqual(call.kwargs, {"timeout": 45})

    def test_roxy_resume_binds_otp_provider_to_explicit_source(self):
        with patch.object(roxy, "wait_for_otp", return_value="123456") as wait_for_otp:
            call = self._run_roxy_resume(email_source=self.email_source)
            provider = call.kwargs["otp_provider"]
            self.assertEqual(provider(self.email, after_ts=123.0, max_wait=30), "123456")

        wait_for_otp.assert_called_once_with(
            self.email,
            after_ts=123.0,
            max_wait=30,
            email_source=self.email_source,
        )

    def test_roxy_legacy_initial_otp_omits_email_source_keyword(self):
        client = MagicMock()
        opened = SimpleNamespace(
            profile_id="compat-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
            account_bound=False,
            raw={},
        )
        driver = MagicMock()
        class StopAfterOtp(BaseException):
            pass

        def wait_for_otp(*_args, **kwargs):
            self.assertNotIn("email_source", kwargs)
            raise StopAfterOtp()

        with ExitStack() as stack:
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch("core.registration_service.report_job_otp_evidence"))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            stack.enter_context(patch("core.registration_service.is_stop_requested", return_value=False))
            stack.enter_context(patch("core.registration_debug.attach_current_roxy"))
            stack.enter_context(patch("core.registration_debug.pause_current_failure"))
            stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened))
            stack.enter_context(patch.object(roxy, "_build_driver", return_value=driver))
            stack.enter_context(patch("core.browser_data_saver.BrowserDataSaver"))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch.object(roxy, "_center_browser_window"))
            stack.enter_context(patch.object(roxy, "_safe_get"))
            stack.enter_context(patch.object(roxy, "_page_warmup"))
            stack.enter_context(patch.object(roxy, "_maybe_accept"))
            stack.enter_context(patch.object(roxy, "_check_manual_stop"))
            stack.enter_context(patch.object(roxy, "human_delay"))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="email_verification"))
            stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_is_email_verification_page", return_value=True))
            stack.enter_context(patch.object(roxy, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(roxy, "_registration_auth_mode", return_value="passwordless"))
            stack.enter_context(patch.object(roxy, "wait_for_otp", wait_for_otp))
            stack.enter_context(patch("core.email_provider.retain_email"))
            with self.assertRaises(StopAfterOtp):
                roxy.run_roxy_registration(
                    self.email,
                    "Test User",
                    "2000-01-01",
                    registration_options={
                        "password_enabled": False,
                        "twofa_enabled": False,
                        "codex_enabled": False,
                        "plan_check_enabled": False,
                    },
                )

    def test_protocol_legacy_initial_otp_omits_email_source_keyword(self):
        session = MagicMock()
        session.proxy = ""

        class StopAfterOtp(BaseException):
            pass

        observed_kwargs = []

        def wait_for_otp(*_args, **kwargs):
            observed_kwargs.append(kwargs)
            raise StopAfterOtp()

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(protocol, "follow_authorize"))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(protocol, "wait_for_otp", wait_for_otp))
            stack.enter_context(patch.object(protocol, "resolve_email_source", return_value="generic_api"))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(
                patch.multiple(
                    protocol._protocol_cfg,
                    CHATGPT_ANON_BOOTSTRAP_ENABLED=False,
                    create=True,
                )
            )
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            with self.assertRaises(StopAfterOtp):
                protocol.run_protocol_registration(
                    self.email,
                    "Test User",
                    "2000-01-01",
                    registration_options={
                        "password_enabled": False,
                        "twofa_enabled": False,
                        "codex_enabled": False,
                        "plan_check_enabled": False,
                    },
                )

        self.assertEqual(1, len(observed_kwargs))
        self.assertNotIn("email_source", observed_kwargs[0])


    def test_skyvern_legacy_wrapper_omits_new_email_source_keyword(self):
        with patch.object(skyvern_registration, "run_browser_use_registration", return_value={"success": True}) as run:
            result = skyvern_registration.run_skyvern_registration(
                self.email,
                "Test User",
                "2000-01-01",
            )

        self.assertTrue(result["success"])
        self.assertNotIn("email_source", run.call_args.kwargs)

    def test_skyvern_wrapper_forwards_explicit_email_source(self):
        with patch.object(skyvern_registration, "run_browser_use_registration", return_value={"success": True}) as run:
            skyvern_registration.run_skyvern_registration(
                self.email,
                "Test User",
                "2000-01-01",
                email_source=self.email_source,
            )

        self.assertEqual(run.call_args.kwargs["email_source"], self.email_source)

    def _run_cloak_codex(self, *, email_source=None, already_advanced=False):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="compat-profile", raw={})
        oauth = MagicMock(return_value={"ok": True, "status": "success", "message": "ok"})

        def email_step(_driver, _email, **kwargs):
            if already_advanced:
                kwargs["on_progress"]("skipped", "当前已在认证下一步，本次无需填写或提交邮箱")
            return "otp"

        with ExitStack() as stack:
            progress = stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch("core.registration_plan_capture.read_selenium", return_value={}))
            stack.enter_context(patch.object(cloakbrowser_registration, "human_delay"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_maybe_accept"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_check_manual_stop"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_submit_email_and_wait_next", side_effect=email_step))
            stack.enter_context(patch.object(cloakbrowser_registration, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(cloakbrowser_registration, "_clear_otp_inputs"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_type_otp"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_click_continue"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_wait_after_email_otp_submit", return_value="accepted"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_complete_profile_page", return_value=True))
            stack.enter_context(
                patch.object(
                    cloakbrowser_registration,
                    "_fetch_chatgpt_session",
                    return_value={"accessToken": "token", "user": {}, "account": {}},
                )
            )
            stack.enter_context(patch.object(cloakbrowser_registration._twofa_cfg, "ENABLE_2FA", False))
            stack.enter_context(patch("config.codex.ENABLE_CODEX_AUTO", True))
            stack.enter_context(patch("core.roxy_codex_oauth.run_roxy_codex_oauth", oauth))
            stack.enter_context(patch.object(cloakbrowser_registration, "save_account_data", return_value=17))
            stack.enter_context(patch.object(cloakbrowser_registration, "resolve_email_source", return_value="generic_api"))
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source=email_source,
            )

        self.assertTrue(result["success"], result)
        if already_advanced:
            progress.assert_any_call("submit_email", "skipped", "当前已在认证下一步，本次无需填写或提交邮箱")
            progress.assert_any_call("auth_redirect", "success", "已进入认证下一步：otp")
        oauth.assert_called_once()
        return oauth.call_args

    def test_cloak_existing_next_page_reports_email_step_skipped(self):
        self._run_cloak_codex(already_advanced=True)

    def test_cloak_codex_legacy_call_omits_otp_provider(self):
        call = self._run_cloak_codex()

        self.assertNotIn("otp_provider", call.kwargs)

    def test_cloak_codex_binds_otp_provider_to_explicit_source(self):
        with patch.object(cloakbrowser_registration, "wait_for_otp", return_value="123456") as wait_for_otp:
            call = self._run_cloak_codex(email_source=self.email_source)
            provider = call.kwargs["otp_provider"]
            self.assertEqual(provider(self.email, after_ts=123.0, max_wait=30), "123456")

        wait_for_otp.assert_called_once_with(
            self.email,
            after_ts=123.0,
            max_wait=30,
            email_source=self.email_source,
        )

    def test_cloak_legacy_initial_otp_omits_email_source_keyword(self):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="compat-profile", raw={})
        wait_for_otp = MagicMock(return_value="123456")

        with ExitStack() as stack:
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch.object(cloakbrowser_registration, "human_delay"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_maybe_accept"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_check_manual_stop"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_submit_email_and_wait_next", return_value="email_verification"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(cloakbrowser_registration, "wait_for_otp", wait_for_otp))
            stack.enter_context(patch.object(cloakbrowser_registration, "_type_otp", side_effect=RuntimeError("stop after initial otp")))
            stack.enter_context(patch("core.email_provider.retain_email"))
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
            )

        self.assertFalse(result["success"])
        wait_for_otp.assert_called_once()
        self.assertNotIn("email_source", wait_for_otp.call_args.kwargs)

    def test_browser_use_legacy_heartbeat_otp_omits_email_source_keyword(self):
        page = MagicMock()
        context = MagicMock()
        with (
            patch.object(browser_use, "_browser_use_heartbeat", return_value=page),
            patch.object(browser_use, "wait_for_otp", return_value="123456") as wait_for_otp,
        ):
            result = browser_use._wait_for_otp_with_browser_heartbeat(
                page,
                context,
                self.email,
                after_ts=123.0,
            )

        self.assertEqual(result, "123456")
        self.assertNotIn("email_source", wait_for_otp.call_args.kwargs)

    def _run_browser_use_codex(
        self, *, email_source=None, login_password=None, login_totp_secret=None,
        codex_response=None, totp_write_ok=True, twofa_setup_error=None,
        codex_auto_enabled=True,
    ):
        client = MagicMock()
        client.open_session.return_value = SimpleNamespace(
            connect_url="ws://browser-use.test",
            proxy_country_code="",
            profile_id="",
            session_id="",
            raw={},
        )
        page = MagicMock()
        context = MagicMock(pages=[page])
        browser = MagicMock(contexts=[context])
        fake_playwright = MagicMock()
        fake_playwright.chromium.connect_over_cdp.return_value = browser
        playwright_manager = MagicMock()
        playwright_manager.__enter__.return_value = fake_playwright
        playwright_manager.__exit__.return_value = False
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = MagicMock(return_value=playwright_manager)
        playwright_package = types.ModuleType("playwright")
        playwright_package.sync_api = sync_api
        events = []
        def record_core(**_kwargs):
            events.append("core")
            return 17

        def record_totp(*_args):
            events.append("totp")
            return totp_write_ok

        def record_oauth(*_args, **_kwargs):
            events.append("oauth")
            return codex_response or {"ok": True, "status": "success", "message": "ok"}

        def record_final(**_kwargs):
            events.append("final")
            return 17

        oauth = MagicMock(side_effect=record_oauth)

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, {"playwright": playwright_package, "playwright.sync_api": sync_api}))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(browser_use, "BrowserUseClient", return_value=client))
            stack.enter_context(patch("core.registration_plan_capture.install_playwright"))
            stack.enter_context(patch("core.registration_plan_capture.read_playwright", return_value={}))
            stack.enter_context(patch.object(browser_use, "_maybe_accept_cookies"))
            stack.enter_context(patch.object(browser_use, "_check_manual_stop"))
            stack.enter_context(patch.object(browser_use, "_submit_email_until_transition", return_value="email_verification"))
            stack.enter_context(patch.object(browser_use, "_assert_not_external_idp"))
            stack.enter_context(patch.object(browser_use, "_fill_password_if_present", return_value=login_password))
            stack.enter_context(patch.object(browser_use, "_browser_use_heartbeat", return_value=page))
            stack.enter_context(patch.object(browser_use, "_quick_auth_state", return_value={"state": "email_verification", "url": "https://auth.openai.com/email-verification"}))
            stack.enter_context(patch.object(browser_use, "_clear_otp_inputs"))
            stack.enter_context(patch.object(browser_use, "_type_otp"))
            stack.enter_context(patch.object(browser_use, "_click_continue"))
            stack.enter_context(patch.object(browser_use, "_wait_after_otp", return_value="accepted"))
            stack.enter_context(patch.object(browser_use, "_complete_profile_page", return_value=True))
            stack.enter_context(
                patch.object(
                    browser_use,
                    "_fetch_chatgpt_session",
                    return_value={"accessToken": "token", "user": {}, "account": {}},
                )
            )
            stack.enter_context(patch.object(browser_use._twofa_cfg, "ENABLE_2FA", bool(login_totp_secret)))
            stack.enter_context(patch.object(browser_use._twofa_cfg, "get_twofa_driver_for_options", return_value="protocol"))
            stack.enter_context(patch.object(browser_use, "BrowserSession"))
            stack.enter_context(patch.object(
                browser_use, "setup_2fa_protocol", return_value=login_totp_secret,
                side_effect=twofa_setup_error,
            ))
            persist_core = stack.enter_context(patch("core.registration_service.persist_registration_core", side_effect=record_core))
            update_totp = stack.enter_context(patch("core.db.update_account_totp_secret", side_effect=record_totp))
            stack.enter_context(patch("config.codex.ENABLE_CODEX_AUTO", codex_auto_enabled))
            stack.enter_context(patch("core.codex_oauth.run_codex_oauth", oauth))
            save = stack.enter_context(patch.object(browser_use, "save_account_data", side_effect=record_final))
            stack.enter_context(patch.object(browser_use, "resolve_email_source", return_value="generic_api"))
            result = browser_use.run_browser_use_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                registration_options={"twofa_enabled": False},
                email_source=email_source,
            )

        self.assertTrue(result["success"], result)
        persist_core.assert_called_once()
        self.assertEqual(persist_core.call_args.kwargs["extra"].get("account_password"), login_password)
        self.assertEqual(persist_core.call_args.kwargs["extra"]["registration_checkpoint"], "core_persisted")
        save.assert_called_once()
        if login_totp_secret:
            if twofa_setup_error is not None:
                update_totp.assert_not_called()
                oauth.assert_not_called()
                self.assertEqual(events, ["core", "final"])
                return None, result
            update_totp.assert_called_once_with(self.email, login_totp_secret)
            if not totp_write_ok:
                oauth.assert_not_called()
                self.assertEqual(events, ["core", "totp", "final"])
                return None, result
            self.assertEqual(
                events,
                ["core", "totp", "oauth", "final"] if codex_auto_enabled else
                ["core", "totp", "final"],
            )
        else:
            update_totp.assert_not_called()
            self.assertEqual(events, ["core", "oauth", "final"] if codex_auto_enabled else ["core", "final"])
        if not codex_auto_enabled:
            oauth.assert_not_called()
            return None, result
        oauth.assert_called_once()
        return oauth.call_args, result

    def test_browser_use_codex_legacy_call_keeps_original_otp_provider(self):
        call, _ = self._run_browser_use_codex()

        self.assertIs(call.kwargs["otp_provider"], browser_use.wait_for_otp)

    def test_browser_use_codex_binds_otp_provider_to_explicit_source(self):
        with patch.object(browser_use, "wait_for_otp", return_value="123456") as wait_for_otp:
            call, _ = self._run_browser_use_codex(email_source=self.email_source)
            provider = call.kwargs["otp_provider"]
            self.assertEqual(provider(self.email, after_ts=123.0, max_wait=30), "123456")

        wait_for_otp.assert_called_once_with(
            self.email,
            after_ts=123.0,
            max_wait=30,
            email_source=self.email_source,
        )

    def test_browser_use_codex_passes_new_registration_credentials_in_memory(self):
        call, _ = self._run_browser_use_codex(
            login_password="Password!123",
            login_totp_secret="totp-secret",
        )
        self.assertEqual(call.kwargs["login_password"], "Password!123")
        self.assertEqual(call.kwargs["login_totp_secret"], "totp-secret")

    def test_browser_use_codex_unknown_result_marks_registration_partial(self):
        _, result = self._run_browser_use_codex(codex_response={
            "ok": False, "status": "attention_required", "outcome": "request_unknown",
            "message": "验证请求结果未知",
        })
        self.assertFalse(result["postprocess_success"])
        self.assertTrue(result["partial_success"])
        self.assertIn("待核对", result["error"])

    def test_browser_use_stops_codex_if_2fa_secret_write_is_unconfirmed(self):
        call, result = self._run_browser_use_codex(
            login_password="Password!123",
            login_totp_secret="totp-secret",
            totp_write_ok=False,
        )
        self.assertIsNone(call)
        self.assertTrue(result["partial_success"])
        self.assertFalse(result["postprocess_success"])
        self.assertEqual(result["codex"]["status"], "attention_required")
        self.assertIn("待核对", result["error"])

    def test_browser_use_stops_codex_if_2fa_setup_outcome_is_unknown(self):
        call, result = self._run_browser_use_codex(
            login_totp_secret="totp-secret",
            twofa_setup_error=TimeoutError("2FA 结果未知"),
        )
        self.assertIsNone(call)
        self.assertTrue(result["partial_success"])
        self.assertEqual(result["codex"]["status"], "attention_required")

    def test_browser_use_marks_2fa_unknown_partial_even_with_codex_disabled(self):
        call, result = self._run_browser_use_codex(
            login_totp_secret="totp-secret",
            twofa_setup_error=TimeoutError("2FA 结果未知"),
            codex_auto_enabled=False,
        )
        self.assertIsNone(call)
        self.assertTrue(result["partial_success"])
        self.assertFalse(result["postprocess_success"])
        self.assertIn("待核对", result["error"])


class CodexStatusProjectionTests(unittest.TestCase):
    def test_attention_required_replaces_old_codex_error_with_fixed_message(self):
        with patch("core.db.insert_account", return_value=17) as insert:
            row_id = persist_account_core(
                email="account@example.test",
                access_token="private-token",
                extra={"codex": {
                    "status": "attention_required",
                    "message": "private-remote-response",
                }},
            )
        self.assertEqual(row_id, 17)
        self.assertEqual(insert.call_args.kwargs["codex_status"], "attention_required")
        self.assertEqual(
            insert.call_args.kwargs["codex_error"],
            "Codex 登录验证结果待核对，不能自动重新提交",
        )


if __name__ == "__main__":
    unittest.main()
