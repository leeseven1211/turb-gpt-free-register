import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import db, roxy_registration
from core.auth_challenge import PasswordSetupUnsupportedError
from core.task_stages import flow_for


class RoxyTwoFactorTests(unittest.TestCase):
    def test_password_eligibility_probe_returns_remote_false(self):
        driver = Mock()
        driver.execute_async_script.return_value = {"status": 200, "eligible": False}

        result = roxy_registration._probe_chatgpt_password_eligibility(driver)

        self.assertFalse(result)
        driver.execute_async_script.assert_called_once()

    def test_password_setup_stops_before_settings_when_remote_disallows_it(self):
        driver = Mock()
        driver.execute_async_script.return_value = {"status": 200, "eligible": False}

        with patch.object(roxy_registration, "_safe_get") as safe_get:
            with self.assertRaises(PasswordSetupUnsupportedError):
                roxy_registration.set_roxy_login_password(
                    driver,
                    "new@example.com",
                    "AccountPassword!123",
                )

        safe_get.assert_not_called()

    def test_settings_home_shell_is_refreshed_even_with_stale_home_controls(self):
        driver = Mock()
        driver.execute_script.return_value = {
            "settings_route": True,
            "text_length": 89,
            "interactive": 16,
            "home_shell": True,
        }

        with (
            patch.object(roxy_registration, "_page_warmup") as warmup,
            patch.object(roxy_registration, "_safe_get") as safe_get,
        ):
            refreshed = roxy_registration._refresh_chatgpt_settings_shell_if_needed(
                driver,
                reason="chatgpt_password_settings_empty_shell",
            )

        self.assertTrue(refreshed)
        driver.refresh.assert_called_once_with()
        self.assertEqual(2, warmup.call_count)
        safe_get.assert_called_once()
        self.assertIn("settings_recover=", safe_get.call_args.args[1])
        self.assertIn("#settings/Security", safe_get.call_args.args[1])

    def test_password_setup_uses_account_add_password_flow(self):
        driver = Mock()
        new_input = Mock()
        new_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "password",
            "id": "new-password",
        }.get(name, "")
        confirm_input = Mock()
        confirm_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "confirm_password",
            "id": "confirm-password",
        }.get(name, "")
        add_password = object()
        submit = object()
        submitted = []
        driver.execute_script.side_effect = [
            {"settings_route": False},
            {"action": add_password, "inputs": [], "body": "密码 添加"},
            {"action": None, "inputs": [new_input, confirm_input], "body": "新密码 重新输入新密码"},
            {"inputs": [], "errors": [], "body": "Password added"},
        ]

        with patch.object(roxy_registration, "_safe_get") as safe_get, patch.object(
            roxy_registration, "_check_manual_stop"
        ), patch.object(roxy_registration, "_dismiss_single_action_dialog", return_value=False), patch.object(
            roxy_registration, "_dismiss_chatgpt_pricing_modal", return_value=False
        ), patch.object(
            roxy_registration, "_human_type_text"
        ) as type_text, patch.object(
            roxy_registration, "_button_after_input", return_value=submit
        ), patch.object(roxy_registration, "_human_click") as click, patch.object(
            roxy_registration.time, "sleep"
        ):
            result = roxy_registration.set_roxy_login_password(
                driver,
                "new@example.com",
                "AccountPassword!123",
                timeout=10,
                on_password_submitted=submitted.append,
            )

        self.assertEqual(result, "AccountPassword!123")
        self.assertEqual(safe_get.call_args.args[1], roxy_registration._CHATGPT_PASSWORD_SETTINGS_URL)
        self.assertEqual(
            type_text.call_args_list,
            [
                unittest.mock.call(driver, new_input, "AccountPassword!123", clear=True),
                unittest.mock.call(driver, confirm_input, "AccountPassword!123", clear=True),
            ],
        )
        self.assertEqual(
            click.call_args_list,
            [
                unittest.mock.call(driver, add_password, label="account_password_settings"),
                unittest.mock.call(driver, submit, label="account_password_submit"),
            ],
        )
        self.assertEqual(submitted, ["AccountPassword!123"])

    def test_password_setup_reacquires_form_after_stale_element(self):
        driver = Mock()
        new_input = Mock()
        new_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "password",
            "id": "new-password",
        }.get(name, "")
        confirm_input = Mock()
        confirm_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "confirm_password",
            "id": "confirm-password",
        }.get(name, "")
        fresh_input = Mock()
        fresh_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "password",
            "id": "new-password",
        }.get(name, "")
        fresh_confirm = Mock()
        fresh_confirm.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "confirm_password",
            "id": "confirm-password",
        }.get(name, "")
        add_password = object()
        submit = object()
        stale = RuntimeError("StaleElementReferenceException: stale element reference")
        driver.execute_script.side_effect = [
            {"settings_route": False},
            {"action": add_password, "inputs": [], "body": "密码 添加"},
            {"action": None, "inputs": [new_input, confirm_input], "body": "新密码 重新输入新密码"},
            [fresh_input, fresh_confirm],
            {"inputs": [], "errors": [], "body": "Password added"},
        ]

        with patch.object(roxy_registration, "_safe_get") as safe_get, patch.object(
            roxy_registration, "_check_manual_stop"
        ), patch.object(roxy_registration, "_dismiss_single_action_dialog", return_value=False), patch.object(
            roxy_registration, "_dismiss_chatgpt_pricing_modal", return_value=False
        ), patch.object(
            roxy_registration, "_human_type_text", side_effect=[stale, None, None]
        ) as type_text, patch.object(
            roxy_registration, "_button_after_input", return_value=submit
        ), patch.object(roxy_registration, "_human_click") as click, patch.object(
            roxy_registration.time, "sleep"
        ):
            result = roxy_registration.set_roxy_login_password(
                driver,
                "new@example.com",
                "AccountPassword!123",
                timeout=10,
            )

        self.assertEqual(result, "AccountPassword!123")
        self.assertEqual(type_text.call_count, 3)
        self.assertEqual(click.call_count, 2)
        self.assertEqual(safe_get.call_count, 1)

    def test_password_setup_uses_broader_fallback_for_visible_add_password_control(self):
        driver = Mock()
        new_input = Mock()
        new_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "password",
            "id": "new-password",
        }.get(name, "")
        confirm_input = Mock()
        confirm_input.get_attribute.side_effect = lambda name: {
            "autocomplete": "new-password",
            "name": "confirm_password",
            "id": "confirm-password",
        }.get(name, "")
        add_password = object()
        submit = object()
        driver.execute_script.side_effect = [
            {"settings_route": False},
            {
                "action": None,
                "inputs": [],
                "password_controls": ["Password Add Password"],
                "password_lines": ["Password Add Password"],
            },
            add_password,
            {"action": None, "inputs": [new_input, confirm_input], "body": "新密码 重新输入新密码"},
            {"inputs": [], "errors": [], "body": "Password added"},
        ]

        with patch.object(roxy_registration, "_safe_get"), patch.object(
            roxy_registration, "_check_manual_stop"
        ), patch.object(roxy_registration, "_dismiss_single_action_dialog", return_value=False), patch.object(
            roxy_registration, "_dismiss_chatgpt_pricing_modal", return_value=False
        ), patch.object(roxy_registration, "_click_chatgpt_settings_control") as click_control, patch.object(
            roxy_registration, "_human_type_text"
        ), patch.object(roxy_registration, "_button_after_input", return_value=submit), patch.object(
            roxy_registration, "_human_click"
        ) as human_click, patch.object(roxy_registration.time, "sleep"):
            result = roxy_registration.set_roxy_login_password(
                driver, "new@example.com", "AccountPassword!123", timeout=10
            )

        self.assertEqual(result, "AccountPassword!123")
        click_control.assert_called_once_with(
            driver, add_password, label="account_password_settings_fallback"
        )
        human_click.assert_called_once_with(driver, submit, label="account_password_submit")

    def test_job_progress_runs_codex_before_twofa(self):
        stages = [key for key, _label in db.JOB_PROGRESS_STAGES]
        self.assertLess(stages.index("network"), stages.index("email"))
        self.assertLess(stages.index("email"), stages.index("browser"))
        self.assertIn("twofa", stages)
        self.assertLess(stages.index("token"), stages.index("codex"))
        self.assertLess(stages.index("codex"), stages.index("twofa"))
        self.assertEqual(
            [item["key"] for item in flow_for("registration")[:3]],
            ["network", "email", "browser"],
        )

    def test_totp_secret_candidate_normalizes_manual_key(self):
        secret = "JBSW Y3DP-EHPK 3PXP JBSW Y3DP-EHPK 3PXP"
        self.assertEqual(
            roxy_registration._totp_secret_candidate(secret),
            "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        )

    def test_totp_secret_candidate_rejects_page_text(self):
        self.assertIsNone(roxy_registration._totp_secret_candidate("Authenticator app"))
        self.assertIsNone(roxy_registration._totp_secret_candidate("UseAuthenticatorApplication"))
        self.assertIsNone(roxy_registration._totp_secret_candidate("ABC123"))

    def test_totp_secret_candidate_accepts_unpadded_and_otpauth_keys(self):
        unpadded = "JBSWY3DPEHPK3PXPJBSWY3DPEH"
        self.assertEqual(roxy_registration._totp_secret_candidate(unpadded), unpadded)
        self.assertEqual(
            roxy_registration._totp_secret_candidate(
                f"otpauth://totp/OpenAI?issuer=OpenAI&secret={unpadded}"
            ),
            unpadded,
        )

    def test_manual_totp_secret_reads_otpauth_link_without_clicking_it(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        driver = Mock()
        driver.execute_script.return_value = [
            f"otpauth://totp/OpenAI:test@example.com?issuer=OpenAI&secret={secret}"
        ]

        with patch.object(roxy_registration, "_human_click") as click:
            result = roxy_registration._manual_totp_secret(driver, object())

        self.assertEqual(result, secret)
        click.assert_not_called()
        self.assertEqual(driver.execute_script.call_count, 1)

    def test_registration_otp_attempts_share_one_total_budget(self):
        with patch.object(roxy_registration.time, "monotonic", return_value=100.0):
            self.assertEqual(
                roxy_registration._registration_otp_attempt_wait_seconds(340.0, 1, 3),
                80,
            )
            self.assertEqual(
                roxy_registration._registration_otp_attempt_wait_seconds(340.0, 2, 3),
                120,
            )
            self.assertEqual(
                roxy_registration._registration_otp_attempt_wait_seconds(100.0, 3, 3),
                0,
            )

    def test_mfa_enrollment_detects_direct_qr_totp_step(self):
        totp_field = object()
        with patch.object(
            roxy_registration,
            "_first_visible_css",
            side_effect=lambda _driver, selector: totp_field if selector == roxy_registration._MFA_TOTP_CODE_SELECTOR else None,
        ):
            step, field = roxy_registration._detect_mfa_enrollment_step(object())
        self.assertEqual(step, "totp")
        self.assertIs(field, totp_field)

    def test_mfa_email_transition_resubmits_once_then_reaches_totp(self):
        driver = SimpleNamespace(current_url="https://auth.openai.com/email-verification")
        email_field = Mock()
        email_field.get_attribute.return_value = "false"
        totp_field = object()
        button = object()
        with patch.object(
            roxy_registration,
            "_detect_mfa_enrollment_step",
            side_effect=[("email", email_field), ("totp", totp_field)],
        ), patch.object(
            roxy_registration.time,
            "monotonic",
            side_effect=[100.0, 100.0, 100.0, 101.0],
        ), patch.object(roxy_registration.time, "sleep"), patch.object(
            roxy_registration, "_button_after_input", return_value=button
        ), patch.object(roxy_registration, "_human_click") as click:
            result = roxy_registration._wait_after_mfa_email_submit(
                driver, timeout=30, resubmit_after=0
            )

        self.assertIs(result, totp_field)
        click.assert_called_once_with(driver, button, label="mfa_reauth_otp_resubmit")

    def test_registration_checkpoint_keeps_generated_password(self):
        session_info = {
            "accessToken": "token",
            "user": {"id": "user-1", "name": "Demo"},
            "account": {"planType": "free"},
            "expires": "later",
        }
        opened = SimpleNamespace(profile_id="profile-1", raw={"ok": True})
        with patch("core.db.insert_account", return_value=17) as insert, patch.object(
            roxy_registration, "resolve_email_source", return_value="generic_api"
        ):
            row_id = roxy_registration._save_roxy_account_checkpoint(
                email="new@example.com",
                access_token="token",
                session_info=session_info,
                opened=opened,
                openai_password="RandomPassword!123",
                proxy="http://proxy.example",
            )
        self.assertEqual(row_id, 17)
        self.assertEqual(insert.call_args.kwargs["extra"]["account_password"], "RandomPassword!123")
        self.assertEqual(insert.call_args.kwargs["extra"]["registration_checkpoint"], "registered")
        self.assertEqual(insert.call_args.kwargs["access_token"], "token")

    def test_password_submission_saves_pending_email_verification_account(self):
        opened = SimpleNamespace(profile_id="profile-1", raw={"ok": True})
        with patch("core.db.insert_account", return_value=19) as insert, patch.object(
            roxy_registration, "resolve_email_source", return_value="icloud_hide"
        ):
            row_id = roxy_registration._save_pending_email_verification_checkpoint(
                email="pending@example.com",
                openai_password="StoredPassword!123",
                opened=opened,
                proxy="http://proxy.example",
            )

        self.assertEqual(row_id, 19)
        self.assertEqual(insert.call_args.kwargs["access_token"], "")
        self.assertEqual(
            insert.call_args.kwargs["extra"]["registration_checkpoint"],
            "email_verification_pending",
        )
        self.assertEqual(
            insert.call_args.kwargs["extra"]["account_password"],
            "StoredPassword!123",
        )

    def test_failed_activation_checkpoint_marks_totp_pending(self):
        session_info = {
            "accessToken": "token",
            "user": {"id": "user-1", "name": "Demo"},
            "account": {"planType": "free"},
            "expires": "later",
        }
        opened = SimpleNamespace(profile_id="profile-1", raw={"ok": True})
        with patch("core.db.insert_account", return_value=18) as insert, patch.object(
            roxy_registration, "resolve_email_source", return_value="generic_api"
        ):
            roxy_registration._save_roxy_account_checkpoint(
                email="new@example.com",
                access_token="token",
                session_info=session_info,
                opened=opened,
                openai_password="RandomPassword!123",
                proxy="http://proxy.example",
                totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
                twofa_result={"status": "failed", "ok": False},
            )
        self.assertTrue(insert.call_args.kwargs["extra"]["totp_setup_pending"])

    def test_setup_persists_secret_before_activation(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        toggle = Mock()
        toggle.get_attribute.side_effect = lambda name: "true" if name == "aria-checked" and toggle.enabled else "false"
        toggle.enabled = False
        totp_field = object()
        verify_button = object()
        saved = []

        def click(_driver, element, label=""):
            if element is verify_button:
                toggle.enabled = True

        with patch.object(roxy_registration, "_open_chatgpt_security_settings", return_value=toggle), patch.object(
            roxy_registration, "_wait_mfa_enrollment_step", return_value=("totp", totp_field)
        ), patch.object(roxy_registration, "_manual_totp_secret", return_value=secret), patch.object(
            roxy_registration, "_human_click", side_effect=click
        ), patch.object(roxy_registration, "_human_type_text") as type_text, patch.object(
            roxy_registration, "_button_after_input", return_value=verify_button
        ), patch.object(
            roxy_registration,
            "_first_visible_css",
            side_effect=lambda _driver, selector: toggle if selector == '[data-testid="mfa-authenticator-toggle"]' else None,
        ):
            result = roxy_registration.setup_roxy_2fa(object(), "new@example.com", on_secret=saved.append)

        self.assertEqual(result, secret)
        self.assertEqual(saved, [secret])
        self.assertTrue(type_text.called)

    def test_setup_accepts_enabled_remote_toggle_when_checkpoint_secret_exists(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        toggle = Mock()
        toggle.get_attribute.side_effect = lambda name: "true" if name == "aria-checked" else "checked"
        saved = []

        with patch.object(roxy_registration, "_open_chatgpt_security_settings", return_value=toggle), patch.object(
            roxy_registration, "_human_click"
        ) as click:
            result = roxy_registration.setup_roxy_2fa(
                object(),
                "new@example.com",
                on_secret=saved.append,
                existing_secret=secret,
            )

        self.assertEqual(result, secret)
        self.assertEqual(saved, [])
        click.assert_not_called()

    def test_protocol_twofa_success_does_not_open_browser_settings(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        saved = []
        with patch.object(
            roxy_registration,
            "setup_2fa_protocol",
            side_effect=lambda _session, _token, *, on_secret: (on_secret(secret), secret)[1],
        ), patch.object(roxy_registration, "setup_roxy_2fa") as browser_setup:
            result, fallback_used = roxy_registration.setup_protocol_2fa_with_browser_fallback(
                object(),
                "new@example.com",
                object(),
                "access-token",
                on_secret=saved.append,
            )

        self.assertEqual(result, secret)
        self.assertFalse(fallback_used)
        self.assertEqual(saved, [secret])
        browser_setup.assert_not_called()

    def test_protocol_twofa_failure_falls_back_to_browser_with_checkpoint_secret(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        saved = []

        def fail_after_enroll(_session, _token, *, on_secret):
            on_secret(secret)
            raise RuntimeError("activate rejected")

        with patch.object(
            roxy_registration, "setup_2fa_protocol", side_effect=fail_after_enroll
        ), patch.object(
            roxy_registration, "setup_roxy_2fa", return_value=secret
        ) as browser_setup:
            result, fallback_used = roxy_registration.setup_protocol_2fa_with_browser_fallback(
                object(),
                "new@example.com",
                object(),
                "access-token",
                on_secret=saved.append,
            )

        self.assertEqual(result, secret)
        self.assertTrue(fallback_used)
        self.assertEqual(saved, [secret])
        browser_setup.assert_called_once_with(
            unittest.mock.ANY,
            "new@example.com",
            on_secret=unittest.mock.ANY,
            existing_secret=secret,
        )

    def test_protocol_and_browser_twofa_failures_are_both_reported(self):
        with patch.object(
            roxy_registration,
            "setup_2fa_protocol",
            side_effect=RuntimeError("protocol blocked"),
        ), patch.object(
            roxy_registration,
            "setup_roxy_2fa",
            side_effect=RuntimeError("settings unavailable"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "协议 2FA 失败且浏览器 UI 回退也失败.*protocol blocked.*settings unavailable",
            ):
                roxy_registration.setup_protocol_2fa_with_browser_fallback(
                    object(),
                    "new@example.com",
                    object(),
                    "access-token",
                )

    def test_setup_retries_with_fresh_totp_when_dialog_stays_open(self):
        secret = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        toggle = Mock()
        toggle.enabled = False
        toggle.get_attribute.side_effect = lambda name: (
            "true" if name == "aria-checked" and toggle.enabled else "false"
        )
        totp_field = object()
        verify_button = object()

        def click(_driver, _element, label=""):
            if label == "totp_verify_retry":
                toggle.enabled = True

        def visible(_driver, selector):
            if selector == '[data-testid="mfa-authenticator-toggle"]':
                return toggle
            if selector == roxy_registration._MFA_TOTP_CODE_SELECTOR:
                return None if toggle.enabled else totp_field
            return None

        totp = Mock()
        totp.now.side_effect = ["111111", "222222"]
        with patch.object(roxy_registration, "_open_chatgpt_security_settings", return_value=toggle), patch.object(
            roxy_registration, "_wait_mfa_enrollment_step", return_value=("totp", totp_field)
        ), patch.object(roxy_registration, "_manual_totp_secret", return_value=secret), patch.object(
            roxy_registration, "_human_click", side_effect=click
        ) as click_mock, patch.object(roxy_registration, "_human_type_text"), patch.object(
            roxy_registration, "_button_after_input", return_value=verify_button
        ), patch.object(roxy_registration, "_first_visible_css", side_effect=visible), patch(
            "pyotp.TOTP", return_value=totp
        ):
            result = roxy_registration.setup_roxy_2fa(object(), "new@example.com")

        self.assertEqual(result, secret)
        self.assertIn(
            "totp_verify_retry",
            [call.kwargs.get("label") for call in click_mock.call_args_list],
        )

    def test_codex_isolated_tab_restores_registration_tab_after_failure(self):
        class SwitchTo:
            def __init__(self, driver):
                self.driver = driver

            def new_window(self, _kind):
                self.driver.handles.append("codex")
                self.driver.current = "codex"

            def window(self, handle):
                if handle not in self.driver.handles:
                    raise RuntimeError("missing handle")
                self.driver.current = handle

        class Driver:
            def __init__(self):
                self.handles = ["registration"]
                self.current = "registration"
                self.closed = []
                self.switch_to = SwitchTo(self)

            @property
            def window_handles(self):
                return list(self.handles)

            @property
            def current_window_handle(self):
                return self.current

            def close(self):
                self.closed.append(self.current)
                self.handles.remove(self.current)
                self.current = self.handles[0] if self.handles else None

        driver = Driver()

        def fail_codex():
            self.assertEqual(driver.current, "codex")
            raise RuntimeError("codex failed")

        with self.assertRaisesRegex(RuntimeError, "codex failed"):
            roxy_registration._run_in_isolated_browser_tab(driver, fail_codex, label="Codex OAuth")

        self.assertEqual(driver.current, "registration")
        self.assertEqual(driver.window_handles, ["registration"])
        self.assertEqual(driver.closed, ["codex"])


if __name__ == "__main__":
    unittest.main()
