# -*- coding: utf-8 -*-
import sys
import types
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.registration import roxy
from core.accounts.export import persist_account_core


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
            stack.enter_context(patch.object(roxy, "human_delay"))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="login_password"))
            fill_password = stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_is_email_verification_page", return_value=False))
            stack.enter_context(
                patch("core.codex.roxy.oauth.complete_openai_login_challenge", challenge)
            )
            stack.enter_context(patch("core.email.provider.retain_email"))
            result = roxy.run_roxy_registration(
                self.email,
                "Test User",
                "2000-01-01",
                proxy="http://pool.example:8080",
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
        return challenge.call_args, fill_password.call_args

    def test_roxy_resume_legacy_call_omits_otp_provider(self):
        call, _ = self._run_roxy_resume()

        self.assertEqual(call.kwargs, {"timeout": 45})

    def test_roxy_resume_binds_otp_provider_to_explicit_source(self):
        with patch.object(roxy, "wait_for_otp", return_value="123456") as wait_for_otp:
            call, _ = self._run_roxy_resume(email_source=self.email_source)
            provider = call.kwargs["otp_provider"]
            self.assertEqual(provider(self.email, after_ts=123.0, max_wait=30), "123456")

        wait_for_otp.assert_called_once_with(
            self.email,
            after_ts=123.0,
            max_wait=30,
            email_source=self.email_source,
        )

    def test_roxy_password_page_gets_two_minute_readiness_budget(self):
        _, password_call = self._run_roxy_resume()

        self.assertEqual(password_call.kwargs["timeout"], 120)

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
            stack.enter_context(patch.object(roxy, "human_delay"))
            stack.enter_context(patch.object(roxy, "_submit_email_and_wait_next", return_value="email_verification"))
            stack.enter_context(patch.object(roxy, "_fill_password_page_if_present", return_value=None))
            stack.enter_context(patch.object(roxy, "_is_email_verification_page", return_value=True))
            stack.enter_context(patch.object(roxy, "_has_access_token", return_value=False))
            stack.enter_context(patch.object(roxy, "_registration_auth_mode", return_value="passwordless"))
            stack.enter_context(patch.object(roxy, "_wait_email_otp_page_ready", return_value="ready"))
            stack.enter_context(patch.object(roxy, "wait_for_otp", wait_for_otp))
            stack.enter_context(patch("core.email.provider.retain_email"))
            with self.assertRaises(StopAfterOtp):
                roxy.run_roxy_registration(
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
                )




















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
