"""协议凭据早存与服务端下一步分派的离线故障注入。"""
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core import record_store
from core.registration import protocol
from core.storage import operation, registration
from tests.support_pg import PostgresTestCase


class ProtocolCredentialBoundaryTests(unittest.TestCase):
    def test_attempt_projection_derives_password_marker_without_exposing_secret(self):
        projected = registration._row({
            "private_context": {"password": "OfflinePassword!123", "password_state": "started"},
            "data": {"password_state": "started"},
        })

        self.assertTrue(projected["data"]["has_password"])
        self.assertNotIn("private_context", projected)
        self.assertNotIn("OfflinePassword!123", str(projected))

    def _run(self, *, response=None, existing_password=None, register_error=None,
             save_error_phase=None, twofa=False, setup=None, warmup_error=None,
             totp_save_error_phase=None, resume_state=None, auth_url=None,
             core_save_error=None):
        events = []
        session = SimpleNamespace(proxy="", device_id="offline", close=lambda: events.append("close"))
        def save_password(**kwargs):
            events.append(kwargs["state"])
            if kwargs["state"] == save_error_phase:
                raise OSError("离线检查点故障")
            return {"account_id": 7 if kwargs["state"] == "confirmed" else None}
        def save_totp(**kwargs):
            phase = "totp_confirmed" if kwargs["confirmed"] else "totp_pending"
            events.append(phase)
            if phase == totp_save_error_phase:
                raise OSError("离线 2FA 写入故障")
        def warmup(*args, **kwargs):
            events.append("warmup")
            if warmup_error:
                raise warmup_error
        def persist_core(**kwargs):
            events.append("core")
            if core_save_error:
                raise core_save_error
            return 7
        with ExitStack() as stack:
            if resume_state:
                stack.enter_context(patch("core.registration_service.registration_fact_context", return_value={"attempt_id": 7}))
                stack.enter_context(patch("core.storage.registration.get_private_resume_context",
                    return_value={"password": existing_password, "password_state": resume_state}))
            for name in ("network_preflight", "get_providers", "probe_auth_session", "human_delay",
                         "navigate_create_account_password", "navigate_about_you"):
                stack.enter_context(patch.object(protocol, name))
            stack.enter_context(patch.object(protocol, "BrowserSession", return_value=session))
            stack.enter_context(patch.object(protocol, "get_csrf_token", return_value="offline"))
            stack.enter_context(patch.object(protocol, "signin_openai", return_value="offline"))
            stack.enter_context(patch.object(protocol, "follow_authorize", return_value=auth_url or ("https://auth.openai.com/log-in/password" if existing_password else "https://auth.openai.com/create-account/password")))
            stack.enter_context(patch.object(protocol, "generate_registration_password", return_value="OfflinePassword!123"))
            for name in ("request_password_sentinel_bundle", "request_sentinel_token"):
                stack.enter_context(patch.object(protocol, name, return_value={}))
            stack.enter_context(patch.object(protocol, "build_sentinel_header", return_value=(None, None)))
            register = stack.enter_context(patch.object(protocol, "register_user", side_effect=register_error,
                return_value={"continue_url": "/api/accounts/email-otp/send"}))
            send = stack.enter_context(patch.object(protocol, "navigate_email_otp_send", return_value="https://auth.openai.com/email-verification"))
            verify = stack.enter_context(patch.object(protocol, "_run_protocol_existing_password_stage", return_value=response))
            otp = stack.enter_context(patch.object(protocol, "validate_email_otp", return_value={"page": {"type": "about_you"}, "continue_url": "https://auth.openai.com/about-you"}))
            create = stack.enter_context(patch.object(protocol, "create_account", return_value={"continue_url": "https://auth.openai.com/authorize/continue"}))
            final = stack.enter_context(patch.object(protocol, "_finalize_registration_session", return_value=({"accessToken": "offline-token"}, "offline-token")))
            mfa = stack.enter_context(patch.object(protocol, "_complete_protocol_resume_mfa", return_value=({"accessToken": "offline-token"}, "offline-token")))
            persist = stack.enter_context(patch("core.registration_service.persist_registration_core", side_effect=persist_core))
            stack.enter_context(patch("core.registration.checkpoints.save_protocol_password_checkpoint", side_effect=save_password))
            stack.enter_context(patch("core.registration.checkpoints.save_protocol_totp_checkpoint", side_effect=save_totp))
            stack.enter_context(patch("core.registration_service.report_job_progress"))
            stack.enter_context(patch("core.registration_service.report_registered_account"))
            stack.enter_context(patch("core.email_provider.retain_email"))
            stack.enter_context(patch.object(protocol._protocol_cfg, "CHATGPT_ANON_BOOTSTRAP_ENABLED", False))
            stack.enter_context(patch.object(protocol._protocol_cfg, "CHATGPT_AUTH_BOOTSTRAP_ENABLED", True))
            stack.enter_context(patch("core.chatgpt_bootstrap.authenticated_bootstrap", side_effect=warmup))
            stack.enter_context(patch.object(protocol, "setup_2fa_protocol", side_effect=setup))
            stack.enter_context(patch("core.db.update_account_codex_status"))
            stack.enter_context(patch("core.db.update_account_twofa_status"))
            stack.enter_context(patch("core.flow_trigger.trigger_flow", return_value={"ok": True}))
            stack.enter_context(patch("core.registration_postprocess.summarize_postprocess", return_value=SimpleNamespace(next_actions=(), account_readiness={})))
            result = protocol.run_protocol_registration("offline@example.test", "离线测试", "2000-01-01",
                proxy="http://pool.example:8080",
                otp_code="000000", existing_password=existing_password, existing_totp_secret="offline-secret",
                registration_options={"password_enabled": True, "twofa_enabled": twofa, "codex_enabled": False, "plan_check_enabled": False})
        return result, events, {"register": register, "send": send, "otp": otp, "create": create, "final": final, "mfa": mfa, "verify": verify, "persist": persist}

    def test_password_saves_before_request_and_unknown_retains_original(self):
        result, events, calls = self._run(register_error=TimeoutError())
        self.assertFalse(result["success"])
        self.assertTrue(result["request_unknown"])
        self.assertEqual(events[:2], ["prepared", "started"])
        self.assertIsNone(result["account_id"])
        calls["register"].assert_called_once()
        calls["send"].assert_not_called()

    def test_save_failure_closes_before_remote_request(self):
        for phase in ("prepared", "started"):
            with self.subTest(phase=phase):
                result, _, calls = self._run(save_error_phase=phase)
                self.assertFalse(result["success"])
                self.assertFalse(result["request_unknown"])
                calls["register"].assert_not_called()

    def test_confirmed_write_failure_preserves_remote_confirmation(self):
        result, events, calls = self._run(save_error_phase="confirmed")
        self.assertTrue(result["register_response_confirmed"])
        self.assertTrue(result["request_unknown"])
        self.assertEqual(events[:3], ["prepared", "started", "confirmed"])
        calls["send"].assert_not_called()

    def test_explicit_rejection_keeps_original_password_without_unknown_success(self):
        error = RuntimeError("离线明确拒绝")
        error.response = SimpleNamespace(status_code=400)
        result, events, calls = self._run(register_error=error)
        self.assertFalse(result["request_unknown"])
        self.assertFalse(result["register_response_confirmed"])
        self.assertEqual(events[:2], ["prepared", "started"])
        calls["send"].assert_not_called()

    def test_stop_after_request_start_preserves_unknown_facts(self):
        from core.registration_service import StopRequested
        with patch("core.registration_service._mark_registration_request_unknown") as mark:
            with self.assertRaises(StopRequested):
                self._run(register_error=protocol.AuthCancelledError())
        mark.assert_called_once()
        self.assertFalse(mark.call_args.kwargs["facts"]["register_response_confirmed"])

    def test_core_persists_before_failing_warmup(self):
        result, events, _ = self._run(warmup_error=TimeoutError())
        self.assertTrue(result["registration_success"])
        self.assertTrue(result["core_persisted"])
        self.assertLess(events.index("core"), events.index("warmup"))

    def test_core_save_failure_does_not_confirm_pending_account(self):
        from core.registration_service import registration_result_status

        result, events, calls = self._run(core_save_error=OSError("离线核心落库失败"))
        self.assertFalse(result["core_persisted"])
        self.assertEqual(result["account_id"], 7)
        self.assertEqual(registration_result_status(result), "failed")
        calls["persist"].assert_called_once()
        self.assertNotIn("warmup", events)

    def test_strict_warmup_failure_keeps_core_and_reports_partial_result(self):
        with patch.object(protocol._protocol_cfg, "CHATGPT_BOOTSTRAP_STRICT", True):
            result, events, _ = self._run(warmup_error=TimeoutError())
        self.assertTrue(result["registration_success"])
        self.assertFalse(result["postprocess_success"])
        self.assertTrue(result["postprocess_warnings"])
        self.assertLess(events.index("core"), events.index("warmup"))

    def test_twofa_secret_saved_before_activation_failure(self):
        def fail_activation(session, token, *, on_secret):
            on_secret("offline-secret")
            raise TimeoutError()
        result, events, _ = self._run(twofa=True, setup=fail_activation)
        self.assertTrue(result["registration_success"])
        self.assertFalse(result["postprocess_success"])
        self.assertIn("totp_pending", events)
        self.assertNotIn("totp_confirmed", events)
        self.assertIsNone(result["totp_secret"])

    def test_twofa_pending_save_failure_prevents_activation(self):
        activated = []
        def setup(session, token, *, on_secret):
            on_secret("offline-secret")
            activated.append(True)
            return "offline-secret"
        result, events, _ = self._run(twofa=True, setup=setup, totp_save_error_phase="totp_pending")
        self.assertTrue(result["registration_success"])
        self.assertFalse(activated)
        self.assertNotIn("totp_confirmed", events)

    def test_twofa_confirmation_is_saved_before_postprocess_returns(self):
        def setup(session, token, *, on_secret):
            on_secret("offline-secret")
            return "offline-secret"
        result, events, _ = self._run(twofa=True, setup=setup)
        self.assertTrue(result["postprocess_success"])
        self.assertLess(events.index("totp_pending"), events.index("totp_confirmed"))
        self.assertEqual(result["totp_secret"], "offline-secret")

    def test_direct_password_continuations_skip_email_otp(self):
        responses = [
            ({"page": {"type": "mfa_challenge"}, "continue_url": "https://auth.openai.com/mfa-challenge/totp"}, "mfa"),
            ({"page": {"type": "external_url"}, "continue_url": "https://chatgpt.com/api/auth/callback/openai"}, "final"),
            ({"page": {"type": "about_you"}, "continue_url": "https://auth.openai.com/about-you"}, "create"),
        ]
        for response, expected in responses:
            with self.subTest(expected=expected):
                result, _, calls = self._run(response=response, existing_password="OfflinePassword!123")
                self.assertTrue(result["success"], result)
                calls["otp"].assert_not_called()
                calls["send"].assert_not_called()
                calls["register"].assert_not_called()
                calls[expected].assert_called_once()

    def test_unknown_password_continuation_stops_without_otp_or_create(self):
        result, _, calls = self._run(response={"page": {"type": "unknown"}}, existing_password="OfflinePassword!123")
        self.assertFalse(result["success"])
        calls["otp"].assert_not_called()
        calls["send"].assert_not_called()
        calls["create"].assert_not_called()

    def test_private_password_allows_original_attempt_retry_without_account(self):
        from core.registration_service import _pre_account_retry_facts_match
        root = {"id": 11, "attempt_id": 7, "email": "offline@example.test"}
        job = {"id": 12, "root_job_id": 11, "attempt_id": 7, "email": "offline@example.test"}
        attempt = {"id": 7, "root_job_id": 11, "source_root_job_id": 11,
                   "email_snapshot": "offline@example.test", "checkpoint": "failed",
                   "remote_identity_state": "request_unknown", "remote_account_state": "not_started",
                   "local_account_state": "none", "target_status": "request_unknown", "data": {"has_password": True}}
        self.assertTrue(_pre_account_retry_facts_match(job, root, attempt))
        self.assertFalse(_pre_account_retry_facts_match({**job, "email": "other@example.test"}, root, attempt))
        self.assertFalse(_pre_account_retry_facts_match(job, root, {**attempt, "target_status": "deactivated"}))

    def test_unconfirmed_saved_password_is_not_promoted_when_otp_skips_password_verify(self):
        for phase in ("prepared", "started"):
            with self.subTest(phase=phase):
                result, _, calls = self._run(existing_password="OfflinePassword!123", resume_state=phase,
                    auth_url="https://auth.openai.com/email-verification")
                self.assertTrue(result["registration_success"])
                self.assertFalse(result["postprocess_success"])
                calls["verify"].assert_not_called()
                self.assertNotIn("account_password", calls["persist"].call_args.kwargs["extra"])

    def test_saved_prepared_password_is_reused_when_server_requests_registration(self):
        result, _, calls = self._run(existing_password="OfflinePassword!123", resume_state="prepared",
            auth_url="https://auth.openai.com/create-account/password")
        self.assertTrue(result["registration_success"])
        self.assertEqual(calls["register"].call_args.args[2], "OfflinePassword!123")
        self.assertEqual(calls["persist"].call_args.kwargs["extra"]["account_password"], "OfflinePassword!123")

    def test_twofa_cancel_propagates_after_core_is_saved(self):
        from core.registration_service import StopRequested
        def setup(session, token, *, on_secret):
            on_secret("offline-secret")
            raise protocol.AuthCancelledError()
        with self.assertRaises(StopRequested):
            self._run(twofa=True, setup=setup)

    def test_existing_password_helper_accepts_only_explicit_supported_states(self):
        states = [
            {"page": {"type": "email_otp"}},
            {"page": {"type": "mfa_challenge"}},
            {"page": {"type": "external_url"}, "continue_url": "https://chatgpt.com/api/auth/callback/openai"},
            {"page": {"type": "about_you"}},
        ]
        for response in states:
            with self.subTest(page=response["page"]["type"]), patch("core.protocol_v2_liveness._password_verify", return_value=response):
                self.assertEqual(protocol._run_protocol_existing_password_stage(object(), "offline@example.test", "OfflinePassword!123"), response)
        with patch("core.protocol_v2_liveness._password_verify", return_value={"page": {"type": "unknown"}}):
            with self.assertRaisesRegex(RuntimeError, "页面未知"):
                protocol._run_protocol_existing_password_stage(object(), "offline@example.test", "OfflinePassword!123")


class ProtocolPrivateCredentialStorageTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.email = "private-offline@example.test"
        self.attempt = registration.create_attempt(self.email)
        self.run = registration.start_run(self.attempt["id"], initial_status="running", execution_id="offline-current")

    def _save(self, state, **changes):
        kwargs = {"email": self.email, "password": "OfflinePassword!123", "state": state,
                  "run_id": self.run["id"], "execution_id": "offline-current"}
        kwargs.update(changes)
        return registration.save_password_checkpoint(self.attempt["id"], **kwargs)

    def test_prepared_is_private_and_does_not_create_registered_account(self):
        self._save("prepared")
        self.assertIsNone(record_store.get_row_by(record_store.ACCOUNTS, "email", self.email))
        self.assertNotIn("private_context", registration.get_attempt(self.attempt["id"]))
        self.assertNotIn("OfflinePassword!123", str(registration.list_attempts()))
        self.assertNotIn("OfflinePassword!123", str(registration.events(self.attempt["id"])))
        self.assertNotIn("private_context", operation._row({"private_context": {"password": "hidden"}}))
        self.assertEqual(registration.get_private_resume_context(self.attempt["id"], email=self.email)["password_state"], "prepared")

    def test_worker_and_original_password_guard(self):
        self._save("prepared")
        for changes in ({"execution_id": "offline-stale"}, {"email": "other@example.test"}, {"password": "Replacement!123"}):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                self._save("started", **changes)

    def test_confirmed_account_and_totp_pending_do_not_project_enabled(self):
        pool_id = record_store.insert_row(record_store.OUTLOOK_POOL, {"email": self.email})
        self._save("started")
        saved = self._save("confirmed", account={"email_source": "generic_api"})
        self.assertIsNotNone(saved["account_id"])
        registration.persist_core_account(self.attempt["id"], access_token="offline-token", account={"email": self.email},
            run_id=self.run["id"], execution_id="offline-current")
        registration.save_totp_checkpoint(self.attempt["id"], email=self.email, secret="offline-secret", confirmed=False,
            run_id=self.run["id"], execution_id="offline-current")
        account = record_store.get_row_by(record_store.ACCOUNTS, "email", self.email)
        self.assertFalse(account.get("totp_secret"))
        self.assertFalse(record_store.get_row(record_store.OUTLOOK_POOL, pool_id).get("totp_secret"))
        extra = json.loads(account["extra_json"]) if isinstance(account["extra_json"], str) else account["extra_json"]
        self.assertTrue(extra["totp_setup_pending"])
        self.assertEqual(extra["twofa"]["status"], "pending")
        registration.save_totp_checkpoint(self.attempt["id"], email=self.email, secret="offline-secret", confirmed=True,
            run_id=self.run["id"], execution_id="offline-current")
        account = record_store.get_row_by(record_store.ACCOUNTS, "email", self.email)
        self.assertEqual(account["totp_secret"], "offline-secret")
        self.assertEqual(record_store.get_row(record_store.OUTLOOK_POOL, pool_id)["totp_secret"], "offline-secret")

    def test_unknown_without_account_recovers_same_attempt_core_and_session(self):
        self._save("started")
        registration.mark_request_unknown(self.attempt["id"], target="identity")
        registration.finish_run(self.run["id"], status="failed")
        registration.advance_checkpoint(self.attempt["id"], "failed")
        self.run = registration.start_run(self.attempt["id"], initial_status="running", execution_id="offline-current")
        result = registration.persist_core_account(self.attempt["id"], access_token="offline-token",
            account={"email": self.email, "chatgpt_session": {"accessToken": "offline-token", "expires": "offline"}},
            run_id=self.run["id"], execution_id="offline-current")
        self.assertEqual(result["attempt"]["id"], self.attempt["id"])
        self.assertEqual(result["attempt"]["checkpoint"], "core_persisted")
        account = record_store.get_row(record_store.ACCOUNTS, result["account_id"])
        session = json.loads(account["chatgpt_session"]) if isinstance(account["chatgpt_session"], str) else account["chatgpt_session"]
        self.assertEqual(session["expires"], "offline")
