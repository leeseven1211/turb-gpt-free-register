"""协议改密沿用已配置的刷新驱动，不因局部变量缺失而失败。"""
import unittest
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from core.accounts.liveness import service as live_service
from core.accounts import credentials
from core.accounts.password_setup import reset
from core.auth.browser.password_recovery import PasswordRecoverySession
from core.storage import postgres as pg, records
from core.storage.accounts import password_recovery as recovery_store
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase


class ProtocolPasswordResetRefreshTests(unittest.TestCase):
    def test_candidate_credentials_are_context_local_and_restore_after_exception(self):
        account = {
            "email": "password-reset@example.test",
            "extra_json": json.dumps({"account_password": "stored-password"}),
            "totp_secret": "stored-totp",
        }
        with patch("core.db.get_account_by_email", return_value=account):
            self.assertEqual(("stored-password", "stored-totp"),
                             credentials.get_account_login_credentials(account["email"]))
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with credentials.override_account_login_credentials(
                    account["email"], "candidate-password", "candidate-totp",
                ):
                    self.assertEqual(
                        ("candidate-password", "candidate-totp"),
                        credentials.get_account_login_credentials(account["email"]),
                    )
                    self.assertEqual(
                        ("stored-password", "stored-totp"),
                        credentials.get_account_login_credentials("other@example.test"),
                    )
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        self.assertEqual(
                            ("stored-password", "stored-totp"),
                            executor.submit(credentials.get_account_login_credentials, account["email"]).result(),
                        )
                    raise RuntimeError("stop")
            self.assertEqual(("stored-password", "stored-totp"),
                             credentials.get_account_login_credentials(account["email"]))

    def test_expired_session_refresh_uses_configured_driver(self):
        runner = Mock(return_value={"ok": True})
        with (
            patch.object(live_service, "_resolve_refresh_driver", return_value="protocol_v3"),
            patch.object(live_service, "_refresh_execution_runner", return_value=runner),
        ):
            result = reset._refresh_before_reset(
                "password-reset@example.test", proxy=None, proxy_supplier=None,
            )
        self.assertIsNone(result)

    def test_pending_candidate_is_used_by_pre_reset_refresh_and_restored_afterward(self):
        observed = []

        def refresh_runner(email, **_kwargs):
            observed.append(credentials.get_account_login_credentials(email))
            return {"ok": True}

        account = {"totp_secret": "candidate-totp"}
        with (
            patch.object(live_service, "_resolve_refresh_driver", return_value="protocol_v3"),
            patch.object(live_service, "_refresh_execution_runner", return_value=refresh_runner),
            patch("core.db.get_account_by_email", return_value={
                "email": "password-reset@example.test",
                "extra_json": json.dumps({"account_password": "stored-password"}),
                "totp_secret": "stored-totp",
            }),
        ):
            result = reset._refresh_before_reset(
                "password-reset@example.test",
                proxy=None,
                proxy_supplier=None,
                account=account,
                password_override="candidate-password",
            )
            self.assertIsNone(result)
            self.assertEqual([("candidate-password", "candidate-totp")], observed)
            self.assertEqual(
                ("stored-password", "stored-totp"),
                credentials.get_account_login_credentials("password-reset@example.test"),
            )

    def test_password_verification_rejects_cookie_reuse_or_missing_password_evidence(self):
        self.assertFalse(reset._password_verification_accepted({
            "ok": True,
            "password_auth_status": "skipped",
            "auth_method": "session_cookie",
        }))
        self.assertFalse(reset._password_verification_accepted({
            "ok": True,
            "password_auth_status": "verified",
            "auth_method": "session_cookie",
            "session_reused": True,
        }))
        self.assertTrue(reset._password_verification_accepted({
            "ok": True,
            "password_auth_status": "verified",
            "auth_method": "password_mfa",
        }))

    def test_unknown_remote_response_marks_private_checkpoint_unknown(self):
        recovery = Mock()
        recovery.checkpoint = SimpleNamespace(state="prepared")
        recovery.prepare.return_value = "Candidate-pass-42"
        recovery.mark_started.side_effect = lambda: setattr(recovery.checkpoint, "state", "started")
        recovery.mark_unknown.side_effect = lambda: setattr(recovery.checkpoint, "state", "unknown")
        session = _ResetSession(
            post_responses=[
                _Response(200, {"page": {"type": "new_password"}}),
                _Response(502),
            ],
        )
        account = {"id": 42, "email": "password-reset@example.test", "access_token": "fixture-access"}
        with (
            patch("core.db.get_account_by_email", return_value=account),
            patch.object(reset, "_session_stale", return_value=False),
            patch.object(reset, "_send_reset_otp"),
            patch.object(reset, "_wait_reset_otp", return_value="123456"),
            patch.object(reset, "_check_reset_mailbox"),
            patch.object(reset, "request_sentinel_token", return_value="sentinel"),
            patch.object(reset, "build_sentinel_header", return_value=("sentinel", "")),
            patch.object(reset, "_network_preflight_with_retry", return_value=(session, "https://auth.example.test/authorize")),
            patch("core.auth.browser.password_recovery.PasswordRecoverySession", return_value=recovery),
            patch("core.storage.accounts.protocol_sessions.load_session", return_value={}),
            patch("core.storage.accounts.protocol_sessions.save_session"),
            patch("core.storage.accounts.protocol_sessions.invalidate_session"),
            patch("core.storage.accounts.device_profiles.load_profile", return_value={}),
            patch("core.storage.accounts.device_profiles.remember_session"),
        ):
            result = reset.run_protocol_password_reset(
                account["email"],
                execution_fence={"run_id": 7, "execution_id": "worker", "lease_token": "lease"},
                refresh_before_reset=False,
            )

        self.assertEqual("password_reset_request_unknown", result["error"])
        self.assertTrue(result["request_unknown"])
        self.assertEqual("unknown", recovery.checkpoint.state)
        recovery.mark_unknown.assert_called_once()

    def test_confirm_requires_explicit_password_authentication_and_avoids_legacy_write(self):
        recovery = Mock()
        recovery.checkpoint = SimpleNamespace(state="prepared", password="Candidate-pass-42")
        recovery.prepare.return_value = "Candidate-pass-42"
        recovery.confirm.side_effect = lambda _confirmation, **_kwargs: (
            setattr(recovery.checkpoint, "state", "confirmed") or "Candidate-pass-42"
        )
        recovery.mark_started.side_effect = lambda: setattr(recovery.checkpoint, "state", "started")
        session = _ResetSession(
            post_responses=[
                _Response(200, {"page": {"type": "new_password"}}),
                _Response(200),
            ],
        )
        account = {"id": 42, "email": "password-reset@example.test", "access_token": "fixture-access"}
        with (
            patch("core.db.get_account_by_email", return_value=account),
            patch.object(reset, "_session_stale", return_value=False),
            patch.object(reset, "_send_reset_otp"),
            patch.object(reset, "_wait_reset_otp", return_value="123456"),
            patch.object(reset, "_check_reset_mailbox"),
            patch.object(reset, "request_sentinel_token", return_value="sentinel"),
            patch.object(reset, "build_sentinel_header", return_value=("sentinel", "")),
            patch.object(reset, "_network_preflight_with_retry", return_value=(session, "https://auth.example.test/authorize")),
            patch.object(reset, "_run_password_verification", return_value={
                "ok": True, "password_auth_status": "verified", "auth_method": "password",
                "access_token": "fresh-token", "session": {
                    "accessToken": "fresh-token", "user": {"email": account["email"], "id": "fixture-user"},
                    "account": {"id": "fixture-account"},
                },
            }),
            patch.object(reset, "_complete_reset", return_value={"ok": True, "status": "success"}),
            patch("core.auth.browser.password_recovery.PasswordRecoverySession", return_value=recovery),
            patch("core.storage.accounts.protocol_sessions.load_session", return_value={}),
            patch("core.storage.accounts.protocol_sessions.save_session"),
            patch("core.storage.accounts.protocol_sessions.invalidate_session"),
            patch("core.storage.accounts.device_profiles.load_profile", return_value={}),
            patch("core.storage.accounts.device_profiles.remember_session"),
            patch("core.db.update_account_login_password") as legacy_write,
        ):
            result = reset.run_protocol_password_reset(
                account["email"],
                execution_fence={"run_id": 7, "execution_id": "worker", "lease_token": "lease"},
                refresh_before_reset=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(2, recovery.prepare.call_count)
        recovery.confirm.assert_called_once_with("password_change_response", completion_pending=True)
        legacy_write.assert_not_called()


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.text = ""
        self._payload = payload or {}

    def json(self):
        return self._payload


class _ResetSession:
    def __init__(self, post_responses):
        self.session = SimpleNamespace(cookies=SimpleNamespace(set=Mock()), close=Mock())
        self._post_responses = list(post_responses)

    def get_auth_headers(self, **_kwargs):
        return {}

    def get_auth_navigate_headers(self, **_kwargs):
        return {}

    def get(self, *_args, **_kwargs):
        return _Response(200)

    def post(self, *_args, **_kwargs):
        return self._post_responses.pop(0)


class PasswordRecoverySessionContractTests(PostgresTestCase):
    def setUp(self):
        key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        key.start()
        self.addCleanup(key.stop)
        loader = patch("config.runtime.load_values", return_value=None)
        loader.start()
        self.addCleanup(loader.stop)
        operations.init()
        self.email = "password-reset-contract@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email,
            "access_token": "fixture-access",
            "extra_json": json.dumps({"preserved": True}),
            "account_status": "active",
        })
        execution_id = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {pg.qualified('operation_tasks')} "
                "(task_uuid,source_system,source_id,task_type,target_type,account_id,email_snapshot,requested_action,status,data) "
                "VALUES (%s,'webui_runtime',%s,'password_change','account',%s,%s,'password_change','running',%s::jsonb) "
                "RETURNING id",
                (uuid.uuid4().hex, source_id, self.account_id, self.email, json.dumps({"steps": ["password"]})),
            )
            task_id = cur.fetchone()[0]
            cur.execute(
                f"INSERT INTO {pg.qualified('operation_runs')} "
                "(run_uuid,task_id,run_no,source_system,source_id,status,execution_id,account_id) "
                "VALUES (%s,%s,1,'webui_runtime',%s,'running',%s,%s) RETURNING id",
                (uuid.uuid4().hex, task_id, source_id, execution_id, self.account_id),
            )
            run_id = cur.fetchone()[0]
        lease_token = operations.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        self.owner = {
            "email": self.email,
            "account_id": self.account_id,
            "purpose": "manual",
            "operation_run_id": run_id,
            "operation_execution_id": execution_id,
            "operation_lease_token": lease_token,
            "attempt_id": None,
            "registration_run_id": None,
            "registration_execution_id": None,
        }

    def test_confirm_returns_password_and_updates_checkpoint_state(self):
        session = PasswordRecoverySession(**self.owner)
        self.assertFalse(session.resume())
        candidate = session.prepare(lambda: "Candidate-pass-42")
        session.mark_started()
        confirmed_password = session.confirm("password_change_response")
        self.assertEqual(candidate, confirmed_password)
        self.assertEqual("confirmed", session.checkpoint.state)
        self.assertIsNone(recovery_store.resume_password_recovery(**self.owner))
