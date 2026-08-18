import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import db, roxy_registration


class RoxyTwoFactorTests(unittest.TestCase):
    def test_job_progress_runs_codex_before_twofa(self):
        stages = [key for key, _label in db.JOB_PROGRESS_STAGES]
        self.assertIn("twofa", stages)
        self.assertLess(stages.index("token"), stages.index("codex"))
        self.assertLess(stages.index("codex"), stages.index("twofa"))

    def test_totp_secret_candidate_normalizes_manual_key(self):
        secret = "JBSW Y3DP-EHPK 3PXP JBSW Y3DP-EHPK 3PXP"
        self.assertEqual(
            roxy_registration._totp_secret_candidate(secret),
            "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        )

    def test_totp_secret_candidate_rejects_page_text(self):
        self.assertIsNone(roxy_registration._totp_secret_candidate("Authenticator app"))
        self.assertIsNone(roxy_registration._totp_secret_candidate("ABC123"))

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
        self.assertEqual(insert.call_args.kwargs["extra"]["registration_password"], "RandomPassword!123")
        self.assertEqual(insert.call_args.kwargs["access_token"], "token")

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
