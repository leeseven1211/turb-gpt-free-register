"""协议补密码的真实私有检查点、执行围栏及服务编排。"""
from __future__ import annotations

import importlib
import json
import os
import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as pg, records as records
from core.storage.accounts import password_recovery as store
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase


class PasswordSetupFixture:
    def setUp(self):
        key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        key.start()
        self.addCleanup(key.stop)
        operations.init()
        self.email = "add-password@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "access_token": "old-token", "password": "mail-only-password",
            "extra_json": json.dumps({"preserved": 42}), "account_status": "active",
        })
        self.owner = self.make_owner()

    def make_owner(self, task_type="password_setup", steps=None):
        execution = uuid.uuid4().hex
        source_id = uuid.uuid4().hex
        data = {} if steps is None else {"steps": steps}
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {pg.qualified('operation_tasks')} "
                        "(task_uuid,source_system,source_id,task_type,target_type,account_id,email_snapshot,requested_action,status,data) "
                        "VALUES (%s,'webui_runtime',%s,%s,'account',%s,%s,%s,'running',%s::jsonb) RETURNING id",
                        (uuid.uuid4().hex, source_id, task_type, self.account_id, self.email, task_type, json.dumps(data)))
            task_id = cur.fetchone()[0]
            cur.execute(f"INSERT INTO {pg.qualified('operation_runs')} "
                        "(run_uuid,task_id,run_no,source_system,source_id,status,execution_id,account_id) "
                        "VALUES (%s,%s,1,'webui_runtime',%s,'running',%s,%s) RETURNING id",
                        (uuid.uuid4().hex, task_id, source_id, execution, self.account_id))
            run_id = cur.fetchone()[0]
        lease = operations.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        return dict(email=self.email, account_id=self.account_id, purpose="manual", operation_run_id=run_id,
                    operation_execution_id=execution, operation_lease_token=lease,
                    attempt_id=None, registration_run_id=None, registration_execution_id=None)

    def end_owner(self):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET status='failed' WHERE id=%s", (self.owner["operation_run_id"],))
            cur.execute(f"DELETE FROM {pg.qualified('account_operation_leases')} WHERE account_id=%s", (self.account_id,))

    def extra(self):
        return json.loads(records.get_row(records.ACCOUNTS, self.account_id)["extra_json"])

    def prepare(self):
        return store.prepare_password_recovery(**self.owner, candidate_factory=lambda: "Candidate-pass-42")

    def transition(self, cp, state, confirmation=None):
        return store.transition_password_recovery(cp.recovery_id, **self.owner, expected_version=cp.version,
                                                  state=state, confirmation=confirmation)


class PasswordSetupStoreTests(PasswordSetupFixture, PostgresTestCase):
    def test_setup_candidate_is_private_until_explicit_add_confirmation(self):
        cp = self.prepare()
        self.assertEqual("", cp.old_password)
        self.assertNotIn("account_password", self.extra())
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT credential_ciphertext FROM {pg.qualified('account_password_recoveries')}")
            self.assertNotIn("Candidate-pass-42", cur.fetchone()[0])
        cp = self.transition(cp, "started")
        self.transition(cp, "confirmed", "password_add_response")
        self.assertEqual({"account_password": "Candidate-pass-42", "preserved": 42}, self.extra())

    def test_combined_setup_requires_password_step(self):
        self.end_owner()
        self.owner = self.make_owner("account_setup_retry", ["password", "twofa"])
        self.assertEqual("prepared", self.prepare().state)

    def test_twofa_and_completion_coordinator_cannot_own_password_candidate(self):
        for task_type, steps in [("twofa_setup", None), ("account_completion", ["password"]),
                                 ("account_setup_retry", ["twofa"])]:
            with self.subTest(task_type=task_type):
                self.end_owner()
                self.owner = self.make_owner(task_type, steps)
                with self.assertRaisesRegex(store.PasswordRecoveryError, "manual_operation_mismatch"):
                    self.prepare()

    def test_add_confirmation_cannot_overwrite_an_existing_password(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "Already-set-1"})})
        cp = self.transition(self.prepare(), "started")
        with self.assertRaisesRegex(store.PasswordRecoveryError, "password_add_context_invalid"):
            self.transition(cp, "confirmed", "password_add_response")
        self.assertEqual("Already-set-1", self.extra()["account_password"])

    def test_session_write_checks_current_execution_and_preserves_candidate(self):
        cp = self.prepare()
        save_session = getattr(store, "save_password_recovery_session", None)
        self.assertTrue(callable(save_session), "协议会话应在执行围栏事务内保存")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET execution_id='replacement' WHERE id=%s",
                        (self.owner["operation_run_id"],))
        with self.assertRaisesRegex(store.PasswordRecoveryError, "operation_execution_mismatch"):
            save_session(cp.recovery_id, **self.owner, access_token="stale-token", session_info={})
        self.assertEqual("old-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_session_write_keeps_unrelated_fields_without_confirming_password(self):
        cp = self.prepare()
        save_session = getattr(store, "save_password_recovery_session", None)
        self.assertTrue(callable(save_session), "协议会话应在执行围栏事务内保存")
        save_session(cp.recovery_id, **self.owner, access_token="fresh-token", session_info={"expires": "2099-01-01"})
        account = records.get_row(records.ACCOUNTS, self.account_id)
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual("mail-only-password", account["password"])
        self.assertEqual(42, self.extra()["preserved"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("prepared", store.resume_password_recovery(**self.owner).state)


class PasswordSetupServiceTests(PasswordSetupFixture, PostgresTestCase):
    def setUp(self):
        super().setUp()
        try:
            self.service = importlib.import_module("core.accounts.password_setup.service")
        except ModuleNotFoundError:
            self.fail("尚未实现纯协议补密码服务")

    def run_service(self, add, *, login=None, checkpoint=None, report=None):
        def authenticated(email, **kwargs):
            return kwargs["on_authenticated"]({"ok": True, "access_token": "fresh-token",
                "session": {"accessToken": "fresh-token", "expires": "2099-01-01"}}, object())
        with patch.object(self.service, "refresh_access_token", side_effect=login or authenticated), \
                patch.object(self.service, "add_password", side_effect=add):
            return self.service.run_protocol_password_setup(self.email, proxy=None, checkpoint=checkpoint, report=report,
                execution_fence={"run_id": self.owner["operation_run_id"],
                    "execution_id": self.owner["operation_execution_id"], "lease_token": self.owner["operation_lease_token"]})

    def test_service_persists_before_dispatch_and_only_confirms_after_response(self):
        def add(session, email, password, **kwargs):
            cp = store.resume_password_recovery(**self.owner)
            self.assertEqual(password, cp.password)
            self.assertEqual("prepared", cp.state)
            self.assertNotIn("account_password", self.extra())
            kwargs["on_dispatched"]()
            self.assertEqual("started", store.resume_password_recovery(**self.owner).state)
            kwargs["on_confirmed"]()
            return {"ok": True}
        result = self.run_service(add)
        self.assertTrue(result["ok"])
        self.assertEqual("confirmed", result["remote_receipt_state"])
        self.assertTrue(self.extra()["account_password"])
        self.assertEqual("fresh-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])
        self.assertNotIn(self.extra()["account_password"], json.dumps(result))
        self.assertNotIn("fresh-token", json.dumps(result))

    def test_unknown_dispatch_keeps_same_candidate_after_execution_restart(self):
        candidates = []
        def unknown(session, email, password, **kwargs):
            candidates.append(password)
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_transport", "请求无回执", request_unknown=True)
        first = self.run_service(unknown)
        self.assertEqual("unknown", first["remote_receipt_state"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("unknown", store.resume_password_recovery(**self.owner).state)
        self.end_owner()
        self.owner = self.make_owner()
        def confirmed(session, email, password, **kwargs):
            candidates.append(password)
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            return {"ok": True}
        self.assertTrue(self.run_service(confirmed)["ok"])
        self.assertEqual(candidates[0], candidates[1])
        self.assertEqual(candidates[0], self.extra()["account_password"])

    def test_explicit_remote_rejection_keeps_candidate_and_refreshed_token(self):
        def rejected(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_already_set", "远端已有密码")
        result = self.run_service(rejected)
        self.assertFalse(result["ok"])
        self.assertEqual("rejected", result["remote_receipt_state"])
        self.assertNotIn("account_password", self.extra())
        self.assertEqual("fresh-token", records.get_row(records.ACCOUNTS, self.account_id)["access_token"])

    def test_existing_password_skips_without_network(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "Already-set-1"})})
        def forbidden(*args, **kwargs):
            self.fail("已有密码不应登录或补密码")
        self.assertEqual("skipped", self.run_service(forbidden, login=forbidden)["status"])
        self.assertEqual("Already-set-1", self.extra()["account_password"])

    def test_lost_execution_cannot_submit_or_confirm_password(self):
        def stale(session, email, password, **kwargs):
            with pg.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET execution_id='replacement' WHERE id=%s",
                            (self.owner["operation_run_id"],))
            kwargs["on_dispatched"]()
            self.fail("失去执行身份应在提交前阻断")
        result = self.run_service(stale)
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation_submitted"])
        self.assertNotIn("account_password", self.extra())

    def test_cancellation_from_callback_survives_auth_adapter(self):
        from core.operations.runtime import OperationCancelled
        def cancelled(session, email, password, **kwargs):
            raise OperationCancelled("stop")
        with self.assertRaises(OperationCancelled):
            self.run_service(cancelled)

    def test_auth_failure_does_not_dispatch_and_raw_error_is_not_returned(self):
        def forbidden(*args, **kwargs):
            self.fail("登录失败不可补密码")
        result = self.run_service(forbidden, login=lambda *a, **k: {"ok": False, "error": "raw-cookie=SECRET"})
        self.assertFalse(result["ok"])
        self.assertFalse(result["mutation_submitted"])
        self.assertNotIn("SECRET", json.dumps(result))

    def test_auth_deactivation_is_preserved_without_submitting_password(self):
        def forbidden(*args, **kwargs):
            self.fail("已停用账号不可补密码")
        result = self.run_service(forbidden, login=lambda *a, **k: {
            "ok": False, "status": "deactivated", "error": "account_deactivated",
        })
        self.assertEqual("deactivated", result["status"])
        self.assertEqual("account_deactivated", result["error_code"])
        self.assertFalse(result["mutation_submitted"])

    def test_confirmed_password_closes_authentication_and_password_progress(self):
        from core.operations.progress import build_progress_snapshot
        events = []
        def confirmed(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            return {"ok": True}
        result = self.run_service(confirmed, report=lambda **event: events.append(event))
        persisted = [{**event, "id": index, "event_type": "stage." + event["state"]}
                     for index, event in enumerate(events, 1)]
        progress = build_progress_snapshot(1, 2, "password_setup", {
            "status": "success", "data": {"config_snapshot": {"password_driver": "protocol"}},
            "result_summary": result,
        }, persisted)
        states = {step["id"]: step["state"] for step in progress["main_steps"]}
        self.assertEqual("success", states["authenticate"])
        self.assertEqual("success", states["set_password"])

    def test_rejected_password_closes_failed_progress_without_hiding_authenticated_success(self):
        events = []
        def rejected(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            raise self.service.ProtocolPasswordSetupError("password_setup_already_set", "远端已有密码")
        self.run_service(rejected, report=lambda **event: events.append(event))
        terminal = [(event["stage"], event["state"]) for event in events if event["state"] != "running"]
        self.assertEqual([("login", "success"), ("set_password", "failed")], terminal)

    def test_cancellation_after_confirmation_keeps_success_receipt_and_stops_followup(self):
        from core.operations.runtime import OperationCancelled
        def confirmed(session, email, password, **kwargs):
            kwargs["on_dispatched"]()
            kwargs["on_confirmed"]()
            raise OperationCancelled("确认后取消")
        result = self.run_service(confirmed)
        self.assertTrue(result["ok"])
        self.assertTrue(result["stop_requested"])
        self.assertEqual("confirmed", result["remote_receipt_state"])
        self.assertTrue(self.extra()["account_password"])
