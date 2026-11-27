"""协议改密的恢复分支、发码时间和新会话交接。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.accounts.password_setup import reset
from tests.accounts.test_password_reset_protocol import _ResetSession, _Response


class PasswordResetP1Tests(TestCase):
    email = "password-reset@example.test"
    account = {"id": 42, "email": email, "access_token": "old-token",
               "extra_json": {"account_password": "Old-password-42"}}

    def test_rust_http_rejection_does_not_prove_candidate_password_is_wrong(self):
        self.assertFalse(reset._candidate_explicitly_rejected({
            "error": "password_rejected", "live_check_driver": "rust",
            "auth_diagnostics": {"detail": '{"error":{"code":"invalid_auth_step"}}'},
        }))
        self.assertTrue(reset._candidate_explicitly_rejected({
            "error": "password_rejected", "live_check_driver": "rust",
            "auth_diagnostics": {"detail": '{"error":{"code":"incorrect_password"}}'},
        }))

    def test_legacy_refresh_choice_uses_existing_password_capable_adapter(self):
        chosen = []

        def choose(driver):
            chosen.append(driver)
            return lambda *_args, **_kwargs: {
                "ok": True, "password_auth_status": "verified", "auth_method": "password",
            }

        with patch("core.accounts.liveness.service._refresh_execution_runner", side_effect=choose):
            result = reset._run_password_verification(
                self.email, "Candidate-password-42", account=self.account, proxy=None,
                proxy_supplier=None, refresh_driver="legacy",
            )
        self.assertEqual(["protocol_v2"], chosen)
        self.assertTrue(result["ok"])

    def test_roxy_verification_accepts_only_supported_runner_arguments(self):
        def browser_runner(email, *, proxy=None, on_authenticated=None):
            return {"ok": True, "password_auth_status": "verified", "auth_method": "roxy_browser"}

        with patch("core.accounts.liveness.service._refresh_execution_runner", return_value=browser_runner):
            result = reset._run_password_verification(
                self.email, "Candidate-password-42", account=self.account,
                proxy="http://fixture.proxy:8080", proxy_supplier=None, refresh_driver="browser_roxy",
            )
        self.assertTrue(result["ok"])

    def test_password_login_captures_private_cookies_and_keeps_selected_device(self):
        identity = {"device_id": "retained-device", "browser_profile": {"impersonate": "chrome149"}}
        cache = {"device_id": "retained-device", "cookies": [{"name": "session", "value": "new"}]}
        auth = {"ok": True, "password_auth_status": "verified", "auth_method": "password",
                "session": {"accessToken": "new-token"}, "access_token": "new-token"}
        seen = {}
        active_session = SimpleNamespace(device_id="retained-device")

        def runner(email, **kwargs):
            seen.update(kwargs)
            callback = kwargs.get("on_authenticated")
            return callback(auth, active_session) if callback else auth

        with (
            patch("core.accounts.liveness.service._resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.accounts.liveness.service._refresh_execution_runner", return_value=runner),
            patch("core.accounts.liveness.protocol.v3._cookie_payload", return_value=cache),
        ):
            result = reset._run_password_verification(
                self.email, "Candidate-password-42", account=self.account,
                proxy="http://fixture.proxy:8080", proxy_supplier=None, identity=identity,
                refresh_driver="protocol_v2",
            )
        self.assertEqual(identity, seen["identity"])
        self.assertEqual(cache, result["_protocol_session"])
        self.assertEqual("new-token", result["access_token"])

    def _run_reset(self, *, state="prepared", verification=None, clock=None, completion_pending=None,
                   validation_error=None):
        recovery = Mock()
        recovery.checkpoint = SimpleNamespace(
            state=state, password="Candidate-password-42",
            completion_pending=(state == "confirmed") if completion_pending is None else completion_pending,
            recovery_id=8, version=2,
        )
        recovery.prepare.return_value = "Candidate-password-42"
        recovery.mark_started.side_effect = lambda: setattr(recovery.checkpoint, "state", "started")
        recovery.mark_unknown.side_effect = lambda: setattr(recovery.checkpoint, "state", "unknown")

        def confirm(*_args, **_kwargs):
            recovery.checkpoint.state = "confirmed"
            return "Candidate-password-42"

        recovery.confirm.side_effect = confirm
        session = _ResetSession([_Response(200, {"page": {"type": "new_password"}}), _Response(200)])
        sent_at = []
        waited_after = []
        fixture_auth = {"ok": True, "password_auth_status": "verified", "auth_method": "password",
                        "access_token": "new-token", "session": {"accessToken": "new-token",
                        "user": {"email": self.email, "id": "u1"}, "account": {"id": "a1"}}}
        with ExitStack() as stack:
            for name, value in (
                ("core.db.get_account_by_email", self.account),
                ("core.storage.accounts.protocol_sessions.load_session", {}),
                ("core.storage.accounts.device_profiles.load_profile", {}),
            ):
                stack.enter_context(patch(name, return_value=value))
            for name in (
                "core.storage.accounts.protocol_sessions.save_session",
                "core.storage.accounts.device_profiles.remember_session",
            ):
                stack.enter_context(patch(name))
            stack.enter_context(patch("core.auth.browser.password_recovery.PasswordRecoverySession", return_value=recovery))
            stack.enter_context(patch("core.db.get_account_chatgpt_session", return_value={
                **fixture_auth["session"], "accessToken": self.account["access_token"],
            }))
            stack.enter_context(patch.object(reset, "_session_stale", return_value=False))
            stack.enter_context(patch.object(reset, "_network_preflight_with_retry", return_value=(session, "https://auth.openai.com/authorize")))
            send = stack.enter_context(patch.object(reset, "_send_reset_otp", side_effect=lambda *_a, **_k: sent_at.append(clock[0] if clock else 0)))

            def wait(_email, after_ts, **_kwargs):
                waited_after.append(after_ts)
                return "123456"

            stack.enter_context(patch.object(reset, "_wait_reset_otp", side_effect=wait))
            stack.enter_context(patch.object(reset, "request_sentinel_token", return_value="sentinel"))
            stack.enter_context(patch.object(reset, "build_sentinel_header", return_value=("sentinel", "")))
            verify = stack.enter_context(patch.object(reset, "_run_password_verification", return_value=verification or fixture_auth))
            if clock is not None:
                def tick():
                    clock[0] += 1
                    return clock[0]
                stack.enter_context(patch.object(reset.time, "time", side_effect=tick))
            # 只替代外部收尾边界；收尾模块另有真实 PostgreSQL 与 HTTP 契约测试。
            complete = stack.enter_context(patch.object(reset, "_complete_reset", create=True, return_value={
                "ok": True, "status": "success", "password_reset": "confirmed",
                "password_confirmed": True, "credentials_saved": True, "business_verified": True,
            }))
            stack.enter_context(patch.object(
                reset, "_validate_reset_auth", create=True,
                return_value=fixture_auth["session"], side_effect=validation_error,
            ))
            stack.enter_context(patch.object(reset, "_check_reset_mailbox", create=True))
            result = reset.run_protocol_password_reset(
                self.email, execution_fence={"run_id": 7, "execution_id": "worker", "lease_token": "lease"},
                refresh_before_reset=False,
            )
        return result, recovery, send, verify, complete, sent_at, waited_after

    def test_confirmed_completion_does_not_reset_password_again(self):
        result, recovery, send, verify, complete, _, _ = self._run_reset(state="confirmed")
        self.assertTrue(result["ok"])
        send.assert_not_called()
        recovery.prepare.assert_not_called()
        recovery.confirm.assert_not_called()
        self.assertEqual("Candidate-password-42", verify.call_args.args[1])
        self.assertTrue(complete.called)

    def test_same_task_already_completed_only_checks_saved_credentials(self):
        result, recovery, send, verify, complete, _, _ = self._run_reset(
            state="confirmed", completion_pending=False,
        )
        self.assertTrue(result["ok"])
        send.assert_not_called()
        verify.assert_not_called()
        recovery.prepare.assert_not_called()
        self.assertTrue(complete.called)

    def test_current_task_completion_is_resolved_before_unrelated_pending_candidate(self):
        result, recovery, send, verify, _, _, _ = self._run_reset(
            state="confirmed", completion_pending=False,
        )
        self.assertTrue(result["ok"])
        recovery.resume_manual_password_change.assert_called_once_with()
        recovery.resume.assert_not_called()
        send.assert_not_called()
        verify.assert_not_called()

    def test_reset_accepted_then_identity_failure_retains_unknown_receipt(self):
        result, recovery, _, _, complete, _, _ = self._run_reset(
            validation_error=reset.ProtocolPasswordResetError(
                "session_identity_invalid", "认证身份不匹配",
                stage="password_authentication", category="auth", cause_code="identity_mismatch",
            ),
        )
        self.assertFalse(result["ok"])
        self.assertEqual("unknown", recovery.checkpoint.state)
        self.assertTrue(result["request_unknown"])
        self.assertEqual("unknown", result["remote_receipt_state"])
        self.assertEqual("identity_mismatch", result["cause_code"])
        complete.assert_not_called()

    def test_unknown_candidate_is_authenticated_before_another_reset(self):
        result, recovery, send, verify, complete, _, _ = self._run_reset(state="unknown")
        self.assertTrue(result["ok"])
        send.assert_not_called()
        recovery.prepare.assert_not_called()
        self.assertEqual("Candidate-password-42", verify.call_args.args[1])
        self.assertEqual("confirmed", recovery.checkpoint.state)
        self.assertTrue(complete.called)

    def test_otp_time_anchor_precedes_send(self):
        result, _, _, _, _, sent_at, waited_after = self._run_reset(clock=[100])
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(sent_at))
        self.assertLessEqual(waited_after[0], sent_at[0])
