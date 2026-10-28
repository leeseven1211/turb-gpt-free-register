"""待确认 TOTP 检查点可恢复登录，但必须另行确认远端启用状态。"""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core import account_credentials, codex_retry_service
from core.registration import mfa_auth


_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


class PendingTotpCredentialsTests(unittest.TestCase):
    def test_login_reads_pending_checkpoint_without_promoting_it(self):
        for encode in (dict, json.dumps):
            with self.subTest(encoding=encode.__name__):
                account = {
                    "totp_secret": "",
                    "extra_json": encode({
                        "account_password": "saved-password",
                        "totp_pending_secret": f" {_SECRET} ",
                        "totp_setup_pending": True,
                    }),
                }
                before = json.dumps(account, sort_keys=True)
                with patch("core.db.get_account_by_email", return_value=account):
                    credentials = account_credentials.get_account_login_credentials("fixture@example.test")
                self.assertEqual(credentials, ("saved-password", _SECRET))
                self.assertEqual(json.dumps(account, sort_keys=True), before)

    def test_active_secret_takes_precedence_over_pending_checkpoint(self):
        account = {
            "totp_secret": " active-secret ",
            "extra_json": {"totp_pending_secret": _SECRET, "totp_setup_pending": True},
        }
        with patch("core.db.get_account_by_email", return_value=account):
            self.assertEqual(
                account_credentials.get_account_login_credentials("fixture@example.test"),
                ("", "active-secret"),
            )

    def test_blank_active_secret_uses_pending_checkpoint(self):
        with patch("core.db.get_account_by_email", return_value={
            "totp_secret": "   ", "extra_json": {"totp_pending_secret": _SECRET},
        }):
            self.assertEqual(
                account_credentials.get_account_login_credentials("fixture@example.test"), ("", _SECRET),
            )

    def test_invalid_extra_does_not_break_active_credentials(self):
        for extra in ("{invalid-json", "[]", [], None):
            with self.subTest(extra=extra), patch(
                "core.db.get_account_by_email",
                return_value={"account_password": "saved-password", "totp_secret": _SECRET, "extra_json": extra},
            ):
                self.assertEqual(
                    account_credentials.get_account_login_credentials("fixture@example.test"),
                    ("saved-password", _SECRET),
                )


class PendingTotpBrowserRecoveryTests(unittest.TestCase):
    def _recover(self, *, enabled, executor="browser", pending_flag=True, browser_fallback_enabled=True):
        extra = {"account_password": "saved-password", "totp_pending_secret": _SECRET}
        if pending_flag:
            extra["totp_setup_pending"] = True
        account = {
            "id": 9, "email": "fixture@example.test", "access_token": "fixture-token",
            "totp_secret": "", "extra_json": json.dumps(extra),
        }
        transitions = []
        toggle = Mock()
        toggle.get_attribute.side_effect = lambda name: (
            "true" if enabled else "false"
        ) if name == "aria-checked" else ""

        def open_settings(_driver):
            self.assertEqual(account["totp_secret"], "")
            self.assertEqual(transitions, [])
            return toggle

        def save_secret(_email, secret, *, setup_pending):
            transitions.append(setup_pending)
            account["totp_secret"] = secret
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(codex_retry_service.db, "get_account_by_email", return_value=account))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_totp_secret", side_effect=save_secret))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_twofa_status", return_value=True))
            stack.enter_context(patch.object(codex_retry_service.db, "update_account_session", return_value=True))
            stack.enter_context(patch.object(codex_retry_service.account_task_store, "append_event"))
            stack.enter_context(patch.object(codex_retry_service, "check_stop_requested"))
            stack.enter_context(patch("config.twofa.get_twofa_driver", return_value=executor))
            stack.enter_context(patch.object(mfa_auth, "_open_chatgpt_security_settings", side_effect=open_settings))
            stack.enter_context(patch.object(mfa_auth, "_human_click"))
            stack.enter_context(patch.object(
                mfa_auth, "_wait_mfa_enrollment_step", side_effect=RuntimeError("远端尚未确认启用"),
            ))
            stack.enter_context(patch(
                "core.registration.selenium_auth.setup_roxy_2fa", side_effect=mfa_auth.setup_roxy_2fa,
            ))
            stack.enter_context(patch(
                "core.registration.selenium_auth.fetch_chatgpt_session",
                **({"return_value": {"accessToken": "fixture-token"}} if not browser_fallback_enabled else {
                    "side_effect": AssertionError("待确认密钥恢复不应先重新执行协议 enroll"),
                }),
            ))
            stack.enter_context(patch(
                "core.account_export.setup_2fa_protocol", side_effect=RuntimeError("协议恢复失败"),
            ))
            stack.enter_context(patch("core.session.BrowserSession"))
            setup = codex_retry_service._build_roxy_account_setup(
                "fixture@example.test", 101, include_password=False,
                browser_fallback_enabled=browser_fallback_enabled,
            )
            if executor == "protocol" and not browser_fallback_enabled:
                with self.assertRaisesRegex(RuntimeError, "协议恢复失败"):
                    setup(Mock())
                self.assertEqual(account["totp_secret"], "")
                self.assertEqual(transitions, [])
            elif enabled:
                self.assertTrue(setup(Mock()))
                self.assertEqual(account["totp_secret"], _SECRET)
                self.assertEqual(transitions, [True, False])
            else:
                with self.assertRaisesRegex(RuntimeError, "远端尚未确认启用"):
                    setup(Mock())
                self.assertEqual(account["totp_secret"], "")
                self.assertEqual(transitions, [])
                self.assertEqual(json.loads(account["extra_json"])["totp_pending_secret"], _SECRET)

    def test_pending_checkpoint_is_promoted_only_after_enabled_toggle(self):
        self._recover(enabled=True)

    def test_disabled_toggle_does_not_promote_or_discard_pending_checkpoint(self):
        self._recover(enabled=False)

    def test_protocol_fallback_checks_existing_pending_before_reenrollment(self):
        self._recover(enabled=True, executor="protocol")

    def test_pending_secret_without_flag_is_not_treated_as_confirmed(self):
        self._recover(enabled=True, pending_flag=False)

    def test_disabled_browser_fallback_does_not_force_pending_recovery_into_browser(self):
        self._recover(enabled=True, executor="protocol", browser_fallback_enabled=False)


if __name__ == "__main__":
    unittest.main()
