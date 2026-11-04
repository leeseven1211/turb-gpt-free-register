# -*- coding: utf-8 -*-
import sys
import types
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from core.auth.protocol.openai_auth import AccountUnusableError
from core.registration import roxy
from core.auth.state_machine import StageBudget


class RegistrationDriverEmailRetentionTests(unittest.TestCase):
    email = "held@example.test"
    failure = "ordinary mid-flow failure"
    email_source = "icloud_hide"

    def test_roxy_email_submission_unknown_is_never_not_started_or_disposable(self):
        from core.auth.browser.email_otp import _EmailSubmissionUnknown
        client = MagicMock()
        opened = SimpleNamespace(profile_id="test-profile", debugger_address="127.0.0.1:9222", created_by_run=True)
        # 即使消息同时含有旧首屏超时标记，专用结果未知异常仍须保留身份与环境。
        failure = _EmailSubmissionUnknown("request_unknown: 邮箱提交结果未知; page_not_hydrated")
        with (
            patch("core.registration.service.report_job_progress"),
            patch("core.registration.service.is_stop_requested", return_value=False),
            patch("core.registration.debug.attach_current_roxy"),
            patch("core.registration.debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(roxy, "_build_driver", side_effect=failure),
            patch("core.email.provider.retain_email") as retain,
            patch("core.email.provider.release_email") as release,
        ):
            result = roxy.run_roxy_registration(self.email, "Test", "2000-01-01", proxy="http://pool.example:8080", email_source=self.email_source,
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
            "core.browser.flow_policy.install_for_flow", return_value=saver
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
            patch("core.registration.service.report_job_progress"),
            patch("core.registration.service.is_stop_requested", return_value=False),
            patch("core.registration.debug.attach_current_roxy"),
            patch("core.registration.debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(roxy, "_build_driver", side_effect=RuntimeError(self.failure)),
            patch("core.email.provider.retain_email") as retain_email,
            patch("core.email.provider.release_email") as release_email,
        ):
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                proxy="http://pool.example:8080",
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
            patch("core.registration.service.report_job_progress"),
            patch("core.registration.service.is_stop_requested", return_value=False),
            patch("core.registration.debug.attach_current_roxy"),
            patch("core.registration.debug.pause_current_failure"),
            patch.object(roxy, "RoxyBrowserClient", return_value=client),
            patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened),
            patch.object(
                roxy,
                "_build_driver",
                side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
            ),
            patch("core.email.provider.mark_email_permanently_unusable") as mark_unusable,
            patch("core.email.provider.retain_email") as retain_email,
            patch("core.email.provider.release_email") as release_email,
        ):
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                proxy="http://pool.example:8080",
                registration_options={
                    "password_enabled": False,
                    "twofa_enabled": False,
                    "codex_enabled": False,
                    "plan_check_enabled": False,
                },
                email_source=self.email_source,
            )

        self._assert_permanently_failed_without_release(result, mark_unusable, retain_email, release_email)









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
            stack.enter_context(patch("core.registration.service.report_job_progress"))
            stack.enter_context(patch("core.registration.service.report_job_otp_evidence"))
            stack.enter_context(patch("core.registration.service.report_registered_account"))
            stack.enter_context(patch("core.registration.service.is_stop_requested", return_value=False))
            stack.enter_context(patch("core.registration.debug.attach_current_roxy"))
            stack.enter_context(patch("core.registration.debug.pause_current_failure"))
            stack.enter_context(patch.object(roxy, "RoxyBrowserClient", return_value=client))
            stack.enter_context(patch.object(roxy, "_open_roxy_profile_with_capacity_wait", return_value=opened))
            stack.enter_context(patch.object(roxy, "_build_driver", return_value=driver))
            stack.enter_context(patch("core.browser.data_saver.BrowserDataSaver"))
            stack.enter_context(patch("core.registration.plan_capture.install_selenium"))
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
            stack.enter_context(patch.object(roxy, "_wait_email_otp_page_ready", return_value="ready"))
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
                patch("core.registration.service.persist_registration_core", return_value=17)
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
                    "core.codex.roxy.oauth.run_roxy_codex_oauth",
                    side_effect=AccountUnusableError("account deactivated", error_code="account_deactivated"),
                )
            )
            mark_unusable = stack.enter_context(patch("core.email.provider.mark_email_permanently_unusable"))
            retain_email = stack.enter_context(patch("core.email.provider.retain_email"))
            release_email = stack.enter_context(patch("core.email.provider.release_email"))
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                proxy="http://pool.example:8080",
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




if __name__ == "__main__":
    unittest.main()
