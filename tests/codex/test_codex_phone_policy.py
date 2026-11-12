"""Codex 手机接码开关在真实挑战边界生效。"""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.codex import oauth
from core.codex.roxy import oauth as roxy


class CodexPhonePolicyTests(unittest.TestCase):
    def _run_protocol(self, step, *, phone_enabled=None):
        callback = "http://localhost:1455/auth/callback?code=test&state=state"
        with ExitStack() as stack:
            for name in ("BrowserSession", "network_preflight", "_bootstrap_authorize", "human_delay", "report_stage"):
                stack.enter_context(patch.object(oauth, name))
            stack.enter_context(patch.object(oauth, "_codex_auth_url_source", return_value="local"))
            stack.enter_context(patch.object(oauth, "_generate_pkce", return_value=("verifier", "challenge")))
            stack.enter_context(patch.object(oauth, "_generate_state", return_value="state"))
            stack.enter_context(patch.object(oauth, "_submit_email", return_value=(step, callback, 100.0)))
            exchange = stack.enter_context(patch.object(oauth, "exchange_codex_token", return_value={}))
            stack.enter_context(patch.object(oauth, "_parse_id_token", return_value={}))
            save = stack.enter_context(patch.object(oauth, "save_codex_credential", return_value="测试凭证.json"))
            result = oauth.run_codex_oauth(
                "account@example.test", otp_provider=Mock(), proxy="", force=True,
                driver_override="protocol", phone_enabled=phone_enabled,
            )
        return result, exchange, save

    def test_protocol_phone_challenge_fails_before_sms_or_callback(self):
        with patch.object(oauth._cfg, "CODEX_PHONE_ENABLED", False), patch.object(
            oauth.sms_provider, "_http"
        ) as http, patch.object(oauth.sms_provider, "acquire_number") as acquire:
            result, exchange, save = self._run_protocol("phone")

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["cause_code"], "codex_phone_verification_disabled")
        self.assertEqual(result["error_category"], "configuration")
        self.assertIn("手机接码已关闭", result["message"])
        self.assertTrue(result["remote_write_rejected"])
        self.assertFalse(result["callback_submitted"])
        self.assertNotIn("reconcile_required", result)
        for action in (http, acquire, exchange, save):
            action.assert_not_called()

    def test_protocol_without_phone_succeeds_with_disabled_sms_and_no_key(self):
        with patch.multiple(oauth._cfg, CODEX_PHONE_ENABLED=False, SMS_API_KEY="", L_ADMIN_AUTH_CODE="", H_ADMIN_AUTH_CODE=""), patch.object(
            oauth.sms_provider, "_http"
        ) as http:
            result, exchange, save = self._run_protocol("callback")

        self.assertTrue(result["ok"])
        self.assertTrue(result["credential_confirmed"])
        http.assert_not_called()
        exchange.assert_called_once()
        save.assert_called_once()

    def test_protocol_uses_disabled_task_snapshot_after_config_changes(self):
        with patch.object(oauth._cfg, "CODEX_PHONE_ENABLED", True), patch.object(
            oauth.sms_provider, "_http"
        ) as http:
            result, _, _ = self._run_protocol("phone", phone_enabled=False)
        self.assertEqual(result["cause_code"], "codex_phone_verification_disabled")
        http.assert_not_called()

    def test_enabled_task_snapshot_still_completes_phone_challenge(self):
        callback = "http://localhost:1455/auth/callback?code=test&state=state"
        with patch.object(oauth._cfg, "CODEX_PHONE_ENABLED", False), patch.object(
            oauth, "_do_phone_verification", return_value={"continue_url": callback}
        ) as phone:
            result, _, _ = self._run_protocol("phone", phone_enabled=True)
            oauth._ensure_phone_verification_enabled(True)
        self.assertTrue(result["ok"])
        self.assertTrue(phone.call_args.kwargs["phone_enabled"])

    def test_sms_challenge_is_recognized_from_url_without_page_type(self):
        self.assertEqual(oauth._authorize_login_step({
            "continue_url": "/phone-verification",
        }), ("phone", "/phone-verification"))

    def test_phone_challenge_after_workspace_uses_disabled_task_snapshot(self):
        response = SimpleNamespace(
            status_code=200, headers={}, url="https://auth.openai.com/phone-verification",
            json=lambda: {},
        )
        session = Mock()
        session.get.return_value = response
        workspace_response = SimpleNamespace(
            status_code=200, headers={},
            json=lambda: {"continue_url": "/phone-verification"},
        )
        with patch.object(oauth._cfg, "CODEX_PHONE_ENABLED", True), patch.object(
            oauth, "_post_json", return_value=workspace_response
        ), patch.object(oauth.sms_provider, "_http") as http:
            with self.assertRaises(oauth.CodexPhoneVerificationDisabled):
                oauth._select_workspace_and_get_callback(
                    session, "state", workspace_id="workspace", phone_enabled=False,
                )
        http.assert_not_called()

    def test_roxy_rejects_phone_input_and_existing_sms_challenges_before_purchase(self):
        for input_present, code_present in ((True, False), (False, True)):
            with self.subTest(input_present=input_present), patch.object(
                roxy, "_has_strict_add_phone_form", return_value=input_present
            ), patch.object(roxy, "_is_phone_code_page", return_value=code_present), patch.object(
                oauth.sms_provider, "_http"
            ) as http, patch.object(oauth.sms_provider, "acquire_number") as acquire:
                with self.assertRaises(oauth.CodexPhoneVerificationDisabled):
                    roxy._do_phone_verification_if_present(Mock(), phone_enabled=False)
            http.assert_not_called()
            acquire.assert_not_called()

    def test_roxy_without_phone_continues_when_sms_is_disabled(self):
        with patch.object(roxy, "_has_strict_add_phone_form", return_value=False), patch.object(
            roxy, "_is_phone_code_page", return_value=False
        ), patch.object(roxy.time, "time", side_effect=[0, 9]), patch.object(oauth.sms_provider, "_http") as http:
            roxy._do_phone_verification_if_present(Mock(), phone_enabled=False)
        http.assert_not_called()

    def test_late_roxy_phone_challenge_obeys_disabled_task_snapshot(self):
        driver = SimpleNamespace(current_url="https://auth.openai.com/add-phone")
        with patch.object(roxy, "_extract_callback_url_from_any_window", return_value=""), patch.object(
            roxy, "_has_strict_add_phone_form", return_value=True
        ), patch.object(oauth.sms_provider, "_http") as http:
            with self.assertRaises(oauth.CodexPhoneVerificationDisabled):
                roxy._finish_consent_workspace(driver, phone_enabled=False)
        http.assert_not_called()

    def test_roxy_entry_preserves_classified_phone_failure(self):
        driver = Mock()
        opened = SimpleNamespace(profile_id="test-profile", raw={})
        with ExitStack() as stack:
            stack.enter_context(patch.object(oauth, "_codex_auth_url_source", return_value="local"))
            for name in ("_bind_password_submission_observer", "_fill_email_and_otp", "human_delay", "report_stage"):
                stack.enter_context(patch.object(roxy, name))
            stack.enter_context(patch("core.browser.flow_policy.install_for_flow", return_value=Mock()))
            stack.enter_context(patch("core.browser.asset_policy.start_auth_asset_cache", return_value=None))
            stack.enter_context(patch("core.browser.asset_policy.stop_asset_cache"))
            stack.enter_context(patch.object(roxy, "_has_strict_add_phone_form", return_value=True))
            callback = stack.enter_context(patch.object(roxy, "_finish_consent_workspace"))
            http = stack.enter_context(patch.object(oauth.sms_provider, "_http"))
            result = roxy._run_roxy_codex_oauth_once(
                "account@example.test", otp_provider=Mock(), force=True,
                existing_driver=driver, existing_opened=opened, reuse_existing_profile=True,
                clear_existing_state=False, phone_enabled=False,
            )
        self.assertEqual(result["cause_code"], "codex_phone_verification_disabled")
        self.assertIn("手机接码已关闭", result["message"])
        callback.assert_not_called()
        http.assert_not_called()

    def test_roxy_does_not_automatically_restart_disabled_phone_failure(self):
        failure = oauth._phone_verification_disabled_result("account@example.test", oauth.CodexPhoneVerificationDisabled())
        with patch.object(roxy, "_run_roxy_codex_oauth_once", return_value=failure) as attempt:
            result = roxy.run_roxy_codex_oauth("account@example.test", force=True, phone_enabled=False)
        self.assertEqual(result, failure)
        attempt.assert_called_once()
        self.assertIs(attempt.call_args.kwargs["phone_enabled"], False)

    def test_protocol_entry_passes_phone_policy_to_roxy_driver(self):
        with patch.object(roxy, "run_roxy_codex_oauth", return_value={"status": "test"}) as run:
            oauth.run_codex_oauth("account@example.test", proxy="", force=True, driver_override="roxy", phone_enabled=False)
        run.assert_called_once()
        self.assertIs(run.call_args.kwargs["phone_enabled"], False)
