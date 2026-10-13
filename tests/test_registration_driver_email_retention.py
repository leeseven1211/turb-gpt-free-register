# -*- coding: utf-8 -*-
import sys
import types
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from core import cloakbrowser_registration
from core.openai_auth import AccountUnusableError
from core.registration import browser_use, protocol, roxy
from core.registration.state_machine import StageBudget


class RegistrationDriverEmailRetentionTests(unittest.TestCase):
    email = "held@example.test"
    failure = "ordinary mid-flow failure"
    email_source = "icloud_hide"

    def test_roxy_email_submission_unknown_is_never_not_started_or_disposable(self):
        from core.registration.email_otp import _EmailSubmissionUnknown
        client = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222", created_by_run=True)
        # 即使消息同时含有旧首屏超时标记，专用结果未知异常仍须保留身份与环境。
        failure = _EmailSubmissionUnknown("request_unknown: 邮箱提交结果未知; page_not_hydrated")
        with (
            patch("core.registration_service.report_job_progress"),
            patch("core.registration_service.is_stop_requested", return_value=False),
            patch("core.registration_debug.attach_current_roxy"),
            patch("core.registration_debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(roxy, "_build_driver", side_effect=failure),
            patch("core.email_provider.retain_email") as retain,
            patch("core.email_provider.release_email") as release,
        ):
            result = roxy.run_roxy_registration(self.email, "Test", "2000-01-01", email_source=self.email_source,
                registration_options={"password_enabled": False, "twofa_enabled": False, "codex_enabled": False, "plan_check_enabled": False})
        self.assertTrue(result["request_unknown"])
        self.assertEqual(result["remote_account_state"], "request_unknown")
        release.assert_not_called()
        retain.assert_called_once()
        client.discard_profile.assert_not_called()

    def _assert_retained_without_release(self, result, retain_email, release_email, driver_name):
        self.assertFalse(result["success"])
        retain_email.assert_called_once_with(
            self.email,
            source=self.email_source,
            note=f"{driver_name}注册中途失败，保留给原任务链: {self.failure}",
        )
        release_email.assert_not_called()

    def _assert_permanently_failed_without_release(
        self, result, mark_unusable, retain_email, release_email, *,
        expected_note="上游明确确认账号永久失效: account deactivated",
    ):
        self.assertFalse(result["success"])
        self.assertTrue(result["email_permanently_unusable"])
        self.assertEqual("account_deactivated", result["account_unusable_error_code"])
        mark_unusable.assert_called_once_with(
            self.email,
            source=self.email_source,
            note=expected_note,
        )
        retain_email.assert_not_called()
        release_email.assert_not_called()

    def test_registration_postprocess_switch_uses_account_action_policy(self):
        opened = SimpleNamespace(profile_id="profile-1")
        driver = MagicMock()
        saver = MagicMock()
        with patch(
            "core.browser_flow_policy.install_for_flow", return_value=saver
        ) as install_for_flow:
            result = roxy._install_registration_postprocess_data_saver(opened, driver)

        self.assertIs(result, saver)
        install_for_flow.assert_called_once_with(
            "account_action", opened, driver, label="ChatGPT 账号操作"
        )
        saver.stop.assert_not_called()

    def test_roxy_mid_flow_failure_retains_email_without_releasing_it(self):
        client = MagicMock()
        opened = SimpleNamespace(
            profile_id="test-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
        )

        with (
            patch("core.registration_service.report_job_progress"),
            patch("core.registration_service.is_stop_requested", return_value=False),
            patch("core.registration_debug.attach_current_roxy"),
            patch("core.registration_debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(roxy, "_build_driver", side_effect=RuntimeError(self.failure)),
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=self.email_source,
            )

        self._assert_retained_without_release(result, retain_email, release_email, "Roxy")

    def test_roxy_confirmed_unusable_account_marks_failed_without_disabling(self):
        client = MagicMock()
        opened = SimpleNamespace(
            profile_id="test-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
        )

        with (
            patch("core.registration_service.report_job_progress"),
            patch("core.registration_service.is_stop_requested", return_value=False),
            patch("core.registration_debug.attach_current_roxy"),
            patch("core.registration_debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(
                roxy,
                "_build_driver",
                side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
            ),
            patch("core.email_provider.mark_email_permanently_unusable") as mark_unusable,
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=self.email_source,
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)

    def test_browser_use_mid_flow_failure_retains_email_without_releasing_it(self):
        client = MagicMock()
        client.open_session.return_value = SimpleNamespace(
            connect_url="ws://browser-use.test",
            proxy_country_code="",
            profile_id="",
            session_id="",
            raw={},
        )
        fake_playwright = MagicMock()
        fake_playwright.chromium.connect_over_cdp.side_effect = RuntimeError(self.failure)
        playwright_manager = MagicMock()
        playwright_manager.__enter__.return_value = fake_playwright
        playwright_manager.__exit__.return_value = False
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = MagicMock(return_value=playwright_manager)
        playwright_package = types.ModuleType("playwright")
        playwright_package.sync_api = sync_api

        with (
            patch.dict(sys.modules, {"playwright": playwright_package, "playwright.sync_api": sync_api}),
            patch("core.registration_service.report_job_progress"),
            patch.object(browser_use, "BrowserUseClient", return_value=client),
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = browser_use.run_browser_use_registration(
                self.email,
                "Test User",
                "2000-01-01",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=self.email_source,
            )

        self._assert_retained_without_release(result, retain_email, release_email, "BrowserUse")

    def test_browser_use_confirmed_unusable_account_marks_failed_without_disabling(self):
        client = MagicMock()
        client.open_session.return_value = SimpleNamespace(
            connect_url="ws://browser-use.test",
            proxy_country_code="",
            profile_id="",
            session_id="",
            raw={},
        )
        fake_playwright = MagicMock()
        fake_playwright.chromium.connect_over_cdp.side_effect = AccountUnusableError(
            "account deactivated",
            error_code="account_deactivated",
        )
        playwright_manager = MagicMock()
        playwright_manager.__enter__.return_value = fake_playwright
        playwright_manager.__exit__.return_value = False
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = MagicMock(return_value=playwright_manager)
        playwright_package = types.ModuleType("playwright")
        playwright_package.sync_api = sync_api

        with (
            patch.dict(sys.modules, {"playwright": playwright_package, "playwright.sync_api": sync_api}),
            patch("core.registration_service.report_job_progress"),
            patch.object(browser_use, "BrowserUseClient", return_value=client),
            patch("core.email_provider.mark_email_permanently_unusable") as mark_unusable,
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = browser_use.run_browser_use_registration(
                self.email,
                "Test User",
                "2000-01-01",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=self.email_source,
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)

    def test_browser_use_otp_heartbeat_uses_explicit_task_email_source(self):
        page = MagicMock()
        context = MagicMock()
        with (
            patch.object(browser_use, "_browser_use_heartbeat", return_value=page),
            patch.object(browser_use, "wait_for_otp", return_value="123456") as wait_for_otp,
        ):
            otp = browser_use._wait_for_otp_with_browser_heartbeat(
                page,
                context,
                self.email,
                after_ts=123.0,
                email_source=self.email_source,
            )

        self.assertEqual(otp, "123456")
        wait_for_otp.assert_called_once_with(
            self.email,
            after_ts=123.0,
            max_wait=ANY,
            poll_interval=ANY,
            settle_seconds=ANY,
            email_source=self.email_source,
        )

    def test_browser_use_success_persists_explicit_task_email_source(self):
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
            stack.enter_context(patch.object(browser_use, "_fill_password_if_present", return_value=None))
            stack.enter_context(patch.object(browser_use, "_browser_use_heartbeat", return_value=page))
            stack.enter_context(patch.object(browser_use, "_quick_auth_state", return_value={"state": "email_verification", "url": "https://auth.openai.com/email-verification"}))
            stack.enter_context(patch.object(browser_use, "_clear_otp_inputs"))
            stack.enter_context(patch.object(browser_use, "_type_otp"))
            stack.enter_context(patch.object(browser_use, "_click_continue"))
            stack.enter_context(patch.object(browser_use, "_wait_after_otp", return_value="accepted"))
            stack.enter_context(patch.object(browser_use, "_complete_profile_page", return_value=True))
            stack.enter_context(patch.object(browser_use, "_fetch_chatgpt_session", return_value={"accessToken": "token", "user": {}, "account": {}}))
            stack.enter_context(patch.object(browser_use._twofa_cfg, "ENABLE_2FA", False))
            stack.enter_context(patch("config.codex.ENABLE_CODEX_AUTO", False))
            persist_core = stack.enter_context(patch("core.registration_service.persist_registration_core", return_value=17))
            save_account_data = stack.enter_context(patch.object(browser_use, "save_account_data", return_value=17))
            stack.enter_context(
                patch.object(
                    browser_use,
                    "resolve_email_source",
                    side_effect=AssertionError("重跑任务不应按已有账号或当前配置改判邮箱来源"),
                )
            )
            result = browser_use.run_browser_use_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                registration_options={"twofa_enabled": False, "codex_enabled": False},
                email_source=self.email_source,
            )

        self.assertTrue(result["success"], result)
        persist_core.assert_called_once()
        self.assertEqual(persist_core.call_args.kwargs["email_source"], self.email_source)
        self.assertEqual(save_account_data.call_args.kwargs["email_source"], self.email_source)

    def test_cloak_mid_flow_failure_retains_email_without_releasing_it(self):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", raw={})

        with (
            patch("core.registration_service.report_job_progress"),
            patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)),
            patch("core.registration_plan_capture.install_selenium"),
            patch.object(cloakbrowser_registration, "human_delay"),
            patch.object(cloakbrowser_registration, "_maybe_accept"),
            patch.object(cloakbrowser_registration, "_check_manual_stop"),
            patch.object(
                cloakbrowser_registration,
                "_submit_email_and_wait_next",
                side_effect=RuntimeError(self.failure),
            ),
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
                email_source=self.email_source,
            )

        self._assert_retained_without_release(result, retain_email, release_email, "Cloak")

    def test_cloak_confirmed_unusable_account_marks_failed_without_disabling(self):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", raw={})

        with (
            patch("core.registration_service.report_job_progress"),
            patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)),
            patch("core.registration_plan_capture.install_selenium"),
            patch.object(cloakbrowser_registration, "human_delay"),
            patch.object(cloakbrowser_registration, "_maybe_accept"),
            patch.object(cloakbrowser_registration, "_check_manual_stop"),
            patch.object(
                cloakbrowser_registration,
                "_submit_email_and_wait_next",
                side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
            ),
            patch("core.email_provider.mark_email_permanently_unusable") as mark_unusable,
            patch("core.email_provider.retain_email") as retain_email,
            patch("core.email_provider.release_email") as release_email,
        ):
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
                email_source=self.email_source,
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)

    def test_cloak_success_uses_explicit_task_email_source_for_otp_and_account(self):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", raw={})
        with ExitStack() as stack:
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch("core.registration_plan_capture.read_selenium", return_value={}))
            stack.enter_context(patch.object(cloakbrowser_registration, "human_delay"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_maybe_accept"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_check_manual_stop"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_submit_email_and_wait_next", return_value="email_verification"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_fill_password_page_if_present", return_value=None))
            wait_for_otp = stack.enter_context(patch.object(cloakbrowser_registration, "wait_for_otp", return_value="123456"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_clear_otp_inputs"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_type_otp"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_click_continue"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_wait_after_email_otp_submit", return_value="accepted"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_complete_profile_page", return_value=True))
            stack.enter_context(patch.object(cloakbrowser_registration, "_fetch_chatgpt_session", return_value={"accessToken": "token", "user": {}, "account": {}}))
            stack.enter_context(patch.object(cloakbrowser_registration._twofa_cfg, "ENABLE_2FA", False))
            stack.enter_context(patch("config.codex.ENABLE_CODEX_AUTO", False))
            save_account_data = stack.enter_context(patch.object(cloakbrowser_registration, "save_account_data", return_value=17))
            stack.enter_context(
                patch.object(
                    cloakbrowser_registration,
                    "resolve_email_source",
                    side_effect=AssertionError("重跑任务不应按已有账号或当前配置改判邮箱来源"),
                )
            )
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
                email_source=self.email_source,
            )

        self.assertTrue(result["success"], result)
        wait_for_otp.assert_called_once()
        otp_call = wait_for_otp.call_args
        self.assertEqual(otp_call.args[0], self.email)
        self.assertEqual(otp_call.kwargs["email_source"], self.email_source)
        self.assertIsInstance(otp_call.kwargs["budget"], StageBudget)
        self.assertLessEqual(otp_call.kwargs["budget"].remaining(), 240)
        self.assertEqual(save_account_data.call_args.kwargs["email_source"], self.email_source)

    def test_protocol_codex_oauth_unusable_error_reaches_outer_failure_contract(self):
        session = MagicMock()
        session.proxy = ""
        session.device_id = "device-id"
        session.sentinel_sid = None
        session.browser_profile = None

        with ExitStack() as stack:
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "network_preflight"))
            stack.enter_context(patch.object(protocol, "get_providers"))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="csrf"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="authorize"))
            stack.enter_context(patch.object(protocol, "follow_authorize"))
            stack.enter_context(
                patch.object(
                    protocol,
                    "validate_email_otp",
                    return_value={
                        "page": {"type": "about_you"},
                        "continue_url": "https://auth.openai.com/about-you",
                    },
                )
            )
            stack.enter_context(patch.object(protocol, "navigate_about_you"))
            stack.enter_context(patch.object(protocol, "request_sentinel_token", return_value={"token": "opaque"}))
            stack.enter_context(patch.object(protocol, "build_sentinel_header", return_value=("sentinel", None)))
            stack.enter_context(
                patch.object(
                    protocol,
                    "create_account",
                    return_value={"continue_url": "https://auth.openai.com/authorize/continue?state=opaque"},
                )
            )
            stack.enter_context(
                patch.object(
                    protocol,
                    "_finalize_registration_session",
                    return_value=({"accessToken": "fresh-token", "user": {}, "account": {}}, "fresh-token"),
                )
            )
            persist_core = stack.enter_context(
                patch("core.registration_service.persist_registration_core", return_value=7)
            )
            stack.enter_context(
                patch(
                    "core.codex_oauth.run_codex_oauth",
                    side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
                )
            )
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"status": "skipped", "ok": True}))
            stack.enter_context(
                patch(
                    "core.registration_postprocess.summarize_postprocess",
                    return_value=SimpleNamespace(next_actions=(), account_readiness={}),
                )
            )
            mark_unusable = stack.enter_context(patch("core.email_provider.mark_email_permanently_unusable"))
            retain_email = stack.enter_context(patch("core.email_provider.retain_email"))
            release_email = stack.enter_context(patch("core.email_provider.release_email"))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(protocol, "human_delay"))
            stack.enter_context(patch.object(protocol._email_cfg, "USE_EMAIL_SERVICE", True))
            stack.enter_context(
                patch.multiple(
                    protocol._protocol_cfg,
                    CHATGPT_ANON_BOOTSTRAP_ENABLED=False,
                    CHATGPT_AUTH_BOOTSTRAP_ENABLED=False,
                    create=True,
                )
            )
            result = protocol.run_protocol_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source=self.email_source,
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": True,
                    "plan_check_enabled": False,
                },
            )

        self._assert_permanently_failed_without_release(
            result, mark_unusable, retain_email, release_email,
            expected_note="上游明确确认账号永久失效: 注册流程失败：AccountUnusableError",
        )
        self.assertEqual(7, result["account_id"])
        persist_core.assert_called_once()

    def test_roxy_codex_oauth_unusable_error_reaches_outer_failure_contract(self):
        client = MagicMock()
        opened = SimpleNamespace(
            profile_id="test-profile",
            debugger_address="127.0.0.1:9222",
            created_by_run=False,
            account_bound=False,
            raw={},
        )
        driver = MagicMock()

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
            stack.enter_context(patch.object(roxy, "_registration_auth_mode", return_value="passwordless"))
            stack.enter_context(patch.object(roxy, "human_delay"))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="email_verification"))
            stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(roxy, "_clear_otp_inputs"))
            stack.enter_context(patch.object(roxy, "_type_otp"))
            stack.enter_context(patch.object(roxy, "_click_continue"))
            stack.enter_context(patch.object(roxy, "_wait_after_email_otp_submit", return_value="accepted"))
            stack.enter_context(patch.object(roxy, "_complete_profile_page", return_value=True))
            stack.enter_context(
                patch.object(
                    roxy,
                    "_fetch_chatgpt_session",
                    return_value={"accessToken": "token", "user": {"email": self.email}, "account": {}},
                )
            )
            persist_core = stack.enter_context(
                patch("core.registration_service.persist_registration_core", return_value=17)
            )
            stack.enter_context(patch.object(roxy, "_save_roxy_account_checkpoint", return_value=17))
            stack.enter_context(
                patch.object(
                    roxy,
                    "_run_in_isolated_browser_tab",
                    side_effect=lambda _driver, callback, *, label: callback(),
                )
            )
            stack.enter_context(
                patch(
                    "core.roxy_codex_oauth.run_roxy_codex_oauth",
                    side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
                )
            )
            mark_unusable = stack.enter_context(patch("core.email_provider.mark_email_permanently_unusable"))
            retain_email = stack.enter_context(patch("core.email_provider.retain_email"))
            release_email = stack.enter_context(patch("core.email_provider.release_email"))
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source=self.email_source,
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": True,
                    "plan_check_enabled": False,
                },
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)
        self.assertEqual(17, result["account_id"])
        persist_core.assert_called_once()

    def test_browser_use_codex_oauth_unusable_error_reaches_outer_failure_contract(self):
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
            stack.enter_context(patch.object(browser_use, "_fill_password_if_present", return_value=None))
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
            stack.enter_context(patch.object(browser_use._twofa_cfg, "ENABLE_2FA", False))
            stack.enter_context(patch("config.codex.ENABLE_CODEX_AUTO", True))
            stack.enter_context(patch("core.codex_oauth.run_codex_oauth", side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated")))
            persist_core = stack.enter_context(patch("core.registration_service.persist_registration_core", return_value=17))
            stack.enter_context(patch.object(browser_use, "save_account_data", return_value=17))
            stack.enter_context(patch.object(browser_use, "_close_browser_use_session"))
            mark_unusable = stack.enter_context(patch("core.email_provider.mark_email_permanently_unusable"))
            retain_email = stack.enter_context(patch("core.email_provider.retain_email"))
            release_email = stack.enter_context(patch("core.email_provider.release_email"))
            result = browser_use.run_browser_use_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source=self.email_source,
                registration_options={"twofa_enabled": False},
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)
        self.assertIn("account_id", result)
        self.assertEqual(result["account_id"], 17)
        persist_core.assert_called_once()

    def test_cloak_codex_oauth_unusable_error_reaches_outer_failure_contract(self):
        driver = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", raw={})

        with ExitStack() as stack:
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch.object(cloakbrowser_registration, "build_cloak_driver", return_value=(driver, opened)))
            stack.enter_context(patch("core.registration_plan_capture.install_selenium"))
            stack.enter_context(patch("core.registration_plan_capture.read_selenium", return_value={}))
            stack.enter_context(patch.object(cloakbrowser_registration, "human_delay"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_maybe_accept"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_check_manual_stop"))
            stack.enter_context(patch.object(cloakbrowser_registration, "_submit_email_and_wait_next", return_value="email_verification"))
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
            stack.enter_context(patch("core.roxy_codex_oauth.run_roxy_codex_oauth", side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated")))
            stack.enter_context(patch.object(cloakbrowser_registration, "save_account_data", return_value=17))
            mark_unusable = stack.enter_context(patch("core.email_provider.mark_email_permanently_unusable"))
            retain_email = stack.enter_context(patch("core.email_provider.retain_email"))
            release_email = stack.enter_context(patch("core.email_provider.release_email"))
            result = cloakbrowser_registration.run_cloak_registration(
                self.email,
                "Test User",
                "2000-01-01",
                otp_code="123456",
                email_source=self.email_source,
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)
        self.assertIn("account_id", result)
        self.assertIsNone(result["account_id"])


if __name__ == "__main__":
    unittest.main()
