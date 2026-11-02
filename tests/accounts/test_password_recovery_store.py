"""密码恢复凭据与事务边界的真实隔离 PostgreSQL 验证。"""
from __future__ import annotations

import importlib
import json
import os
import threading
import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as pg, records as rs, registration
from core.storage.operations import store as operations
from core.storage.registration import jobs
from tests.support_pg import PostgresTestCase


class Password_Recovery_Store(PostgresTestCase):
    def setUp(self):
        try:
            self.store = importlib.import_module("core.storage.accounts.password_recovery")
        except ModuleNotFoundError:
            self.fail("尚未实现可恢复的私有密码存储")
        self.key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.key.start()
        self.addCleanup(self.key.stop)
        operations.init()
        self.email = "recover@example.test"
        self.account_id = rs.insert_row(rs.ACCOUNTS, {
            "email": self.email, "access_token": "retained-token", "password": "mail-password",
            "extra_json": json.dumps({"account_password": "Old-login-1", "unrelated": "保留"}),
            "current_plan_type": "plus", "account_status": "active",
        })
        root = jobs.create_job("outlook", data={"registration_driver": "roxy"})
        self.root_job_id = int(root["id"])
        jobs.update_job(self.root_job_id, email=self.email, account_id=self.account_id, status="failed")
        self.attempt_id = int(jobs.get_job(self.root_job_id)["attempt_id"])
        first_run = registration.list_runs(self.attempt_id)[0]
        registration.finish_run(int(first_run["id"]), status="failed")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET account_id=%s, checkpoint='otp_confirmed', private_context=%s::jsonb WHERE id=%s",
                        (self.account_id, json.dumps({"password": "Old-login-1", "password_state": "confirmed", "preserve": 42}), self.attempt_id))
        self.owner = self._registration_owner()

    def _registration_owner(self):
        job, created = jobs.create_retry_job(
            self.root_job_id, job_type="registration_resume", email_source="outlook",
            email=self.email, account_id=self.account_id,
        )
        self.assertTrue(created)
        context = self._start_job_run(job)
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        operation_run = operations.get_run(int(task["last_run_id"]))
        self.assertEqual(str(job["id"]), operation_run["source_id"])
        self.assertEqual(job["job_uuid"], operation_run["execution_id"])
        return dict(email=self.email, account_id=self.account_id, purpose="registration",
                    operation_run_id=operation_run["id"], operation_execution_id=operation_run["execution_id"],
                    operation_lease_token=None, attempt_id=self.attempt_id, registration_run_id=context["run_id"],
                    registration_execution_id=context["execution_id"])

    def _start_job_run(self, job):
        from core.registration import service

        self.assertTrue(jobs.claim_job_for_execution(int(job["id"])))
        with patch.multiple(service._THREAD_CTX, job_id=int(job["id"]), attempt_id=None,
                            run_id=None, execution_id=None, create=True):
            context = service._ensure_registration_run_context(jobs.get_job(int(job["id"])))
        self.assertIsNotNone(context)
        return context

    def _operation_run(self, source, source_id, execution_id, action):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {pg.qualified('operation_tasks')} (task_uuid,source_system,source_id,task_type,target_type,account_id,attempt_id,email_snapshot,requested_action,status) VALUES (%s,%s,%s,%s,'account',%s,%s,%s,%s,'running') RETURNING id",
                        (uuid.uuid4().hex, source, source_id, action, self.account_id, self.attempt_id, self.email, action))
            task_id = cur.fetchone()[0]
            cur.execute(f"INSERT INTO {pg.qualified('operation_runs')} (run_uuid,task_id,run_no,source_system,source_id,status,execution_id,account_id) VALUES (%s,%s,1,%s,%s,'running',%s,%s) RETURNING id",
                        (uuid.uuid4().hex, task_id, source, source_id, execution_id,
                         None if source == "registration_jobs" else self.account_id))
            return cur.fetchone()[0]

    def _manual_owner(self):
        execution_id = uuid.uuid4().hex
        run_id = self._operation_run("account_action_tasks", uuid.uuid4().hex, execution_id, "password_change")
        token = operations.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        return dict(email=self.email, account_id=self.account_id, purpose="manual",
                    operation_run_id=run_id, operation_execution_id=execution_id, operation_lease_token=token,
                    attempt_id=None, registration_run_id=None, registration_execution_id=None)

    def _prepare(self, owner=None):
        return self.store.prepare_password_recovery(**(owner or self.owner), candidate_factory=lambda: "New-login-2")

    def _transition(self, cp, state, owner=None, confirmation=None, version=None):
        return self.store.transition_password_recovery(cp.recovery_id, **(owner or self.owner),
                    expected_version=cp.version if version is None else version, state=state, confirmation=confirmation)

    def _private(self):
        return registration.get_private_resume_context(self.attempt_id, email=self.email)

    def test_real_retry_job_without_execution_id_can_prepare_resume_and_confirm(self):
        run = registration.get_run(self.owner["registration_run_id"])
        job = jobs.get_job(int(run["job_id"]))
        self.assertIsNone(job.get("execution_id"))
        self.assertIsNone(registration.get_attempt(self.attempt_id).get("active_execution_id"))
        self.assertNotEqual(self.owner["registration_execution_id"], job["job_uuid"])
        self.assertIsNone(self.store.resume_password_recovery(**self.owner))
        cp = self._transition(self._prepare(), "started")
        self.assertEqual(cp.recovery_id, self.store.resume_password_recovery(**self.owner).recovery_id)
        self.assertEqual("confirmed", self._transition(cp, "confirmed", confirmation="candidate_login").state)

    def test_batch_projection_keeps_current_retry_password_recovery_active(self):
        operation_run = operations.get_run(self.owner["operation_run_id"])
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        self.assertEqual("running", operation_run["status"])
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertIsNone(self.store.resume_password_recovery(**self.owner))
        self.assertEqual("running", operations.get_run(self.owner["operation_run_id"])["status"])
        self.assertEqual("running", registration.get_run(self.owner["registration_run_id"])["status"])
        cp = self._transition(self._prepare(), "started")
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual("confirmed", self._transition(cp, "confirmed", confirmation="candidate_login").state)

    def test_batch_projection_repairs_finished_job_without_closing_new_retry(self):
        old_owner = self.owner
        old_run = registration.get_run(old_owner["registration_run_id"])
        jobs.update_job(int(old_run["job_id"]), status="failed")
        registration.finish_run(int(old_run["id"]), status="failed", error_message="上一轮已失败")
        self.owner = self._registration_owner()
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET status='running', completed_at=NULL "
                        "WHERE id=%s", (old_owner["operation_run_id"],))
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual("failed", operations.get_run(old_owner["operation_run_id"])["status"])
        self.assertEqual("running", operations.get_run(self.owner["operation_run_id"])["status"])
        self.assertIsNone(self.store.resume_password_recovery(**self.owner))

    def test_batch_projection_does_not_assign_unlinked_historical_fact(self):
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_runs')} SET job_id=NULL "
                        "WHERE attempt_id=%s AND status='failed'", (self.attempt_id,))
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual("running", operations.get_run(self.owner["operation_run_id"])["status"])
        self.assertIsNone(self.store.resume_password_recovery(**self.owner))

    def test_batch_projection_does_not_close_native_run_from_registration_history(self):
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET source_system='native_operations' "
                        "WHERE id=%s", (self.owner["operation_run_id"],))
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual("running", operations.get_run(self.owner["operation_run_id"])["status"])

    def test_batch_projection_keeps_matching_unknown_result_attention_required(self):
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:registration_resume")
        registration.finish_run(self.owner["registration_run_id"], status="request_unknown")
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual("attention_required", operations.get_run(self.owner["operation_run_id"])["status"])
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "operation_inactive"):
            self.store.resume_password_recovery(**self.owner)

    def test_batch_projection_keeps_other_task_run_active_in_same_attempt(self):
        previous = registration.get_run(self.owner["registration_run_id"])
        jobs.update_job(int(previous["job_id"]), status="failed")
        registration.finish_run(int(previous["id"]), status="failed")
        job, created = jobs.create_retry_job(
            int(previous["job_id"]), job_type="twofa_retry", email_source="outlook",
            email=self.email, account_id=self.account_id,
        )
        self.assertTrue(created)
        current = self._start_job_run(job)
        task = operations.find_task_by_source("registration_chains", f"{self.root_job_id}:twofa_retry")
        operations._project_claimed_batch({
            "batch_id": task["batch_id"], "batch_source_system": "registration_batches",
        })
        self.assertEqual(self.attempt_id, registration.get_run(current["run_id"])["attempt_id"])
        self.assertEqual("running", operations.get_run(task["last_run_id"])["status"])

    def test_prepare_once_keeps_current_credentials_and_ciphertext_private(self):
        calls = []
        def candidate():
            calls.append(1)
            return "New-login-2"
        cp = self.store.prepare_password_recovery(**self.owner, candidate_factory=candidate)
        repeated = self.store.prepare_password_recovery(**self.owner, candidate_factory=candidate)
        self.assertEqual(cp.recovery_id, repeated.recovery_id)
        self.assertEqual([1], calls)
        self.assertEqual("prepared", cp.state)
        self.assertEqual("Old-login-1", self._private()["password"])
        self.assertIn("Old-login-1", rs.get_row(rs.ACCOUNTS, self.account_id)["extra_json"])
        for secret in ("Old-login-1", "New-login-2"):
            self.assertNotIn(secret, repr(cp))
            with pg.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT row_to_json(r)::text FROM {pg.qualified('account_password_recoveries')} r")
                self.assertNotIn(secret, cur.fetchone()[0])
            self.assertNotIn(secret, json.dumps(registration.get_attempt(self.attempt_id)))
        self.assertEqual(cp.password, self.store.get_password_recovery(cp.recovery_id, **self.owner).password)

    def test_concurrent_prepare_generates_one_candidate(self):
        self.store.init()
        values, calls, failures = [], [], []
        def prepare():
            try:
                values.append(self.store.prepare_password_recovery(**self.owner, candidate_factory=lambda: calls.append(1) or "New-login-2"))
            except Exception as exc:
                failures.append(type(exc).__name__)
        threads = [threading.Thread(target=prepare) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        self.assertEqual([], failures)
        self.assertEqual(4, len(values))
        self.assertEqual([1], calls)
        self.assertEqual(1, len({cp.recovery_id for cp in values}))

    def test_wrong_email_execution_mapping_and_version_are_rejected(self):
        cp = self._prepare()
        for changes in ({"email": "other@example.test"}, {"operation_execution_id": "stale"},
                        {"registration_execution_id": "stale"}, {"registration_run_id": 999999}):
            with self.subTest(changes=changes), self.assertRaises(self.store.PasswordRecoveryError):
                self.store.get_password_recovery(cp.recovery_id, **{**self.owner, **changes})
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "version_conflict"):
            self._transition(cp, "started", version=cp.version + 1)
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET source_id='999999' WHERE id=%s", (self.owner["operation_run_id"],))
        with self.assertRaises(self.store.PasswordRecoveryError):
            self.store.get_password_recovery(cp.recovery_id, **self.owner)

    def test_resume_takes_over_finished_execution_and_rejects_old_worker(self):
        cp = self._transition(self._prepare(), "started")
        cp = self._transition(cp, "unknown")
        old_owner = self.owner
        self.assertEqual(cp.recovery_id, self.store.resume_password_recovery(**old_owner).recovery_id)
        with pg.connect() as conn, conn.cursor() as cur:
            for table, identifier in (("registration_runs", old_owner["registration_run_id"]), ("operation_runs", old_owner["operation_run_id"])):
                cur.execute(f"UPDATE {pg.qualified(table)} SET status='interrupted' WHERE id=%s", (identifier,))
        old_run = registration.get_run(old_owner["registration_run_id"])
        jobs.update_job(int(old_run["job_id"]), status="interrupted")
        self.owner = self._registration_owner()
        recovered = self.store.resume_password_recovery(**self.owner)
        self.assertEqual(cp.recovery_id, recovered.recovery_id)
        self.assertEqual("New-login-2", recovered.password)
        self.assertEqual("unknown", recovered.state)
        self.assertGreater(recovered.version, cp.version)
        for action in (lambda: self.store.get_password_recovery(cp.recovery_id, **old_owner),
                       lambda: self._transition(cp, "confirmed", owner=old_owner, confirmation="candidate_login")):
            with self.assertRaises(self.store.PasswordRecoveryError):
                action()

    def test_active_owner_prevents_takeover(self):
        cp = self._prepare()
        new_owner = self._manual_owner()
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "owner_active"):
            self.store.resume_password_recovery(**new_owner)
        self.assertEqual(cp.version, self.store.get_password_recovery(cp.recovery_id, **self.owner).version)

    def test_manual_requires_current_account_lease(self):
        owner = self._manual_owner()
        cp = self._prepare(owner)
        for token in (None, "wrong"):
            with self.assertRaisesRegex(self.store.PasswordRecoveryError, "lease"):
                self.store.get_password_recovery(cp.recovery_id, **{**owner, "operation_lease_token": token})
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('account_operation_leases')} SET expires_at=now()-interval '1 second'")
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "lease"):
            self._transition(cp, "started", owner)

    def test_confirm_atomically_updates_matching_attempt_and_preserves_other_fields(self):
        checkpoint_before = registration.get_attempt(self.attempt_id)["checkpoint"]
        cp = self._transition(self._prepare(), "started")
        rs.patch_row(rs.ACCOUNTS, self.account_id, {"current_plan_type": "pro", "note": "并发套餐更新"})
        confirmed = self._transition(cp, "confirmed", confirmation="password_change_response")
        account = rs.get_row(rs.ACCOUNTS, self.account_id)
        self.assertEqual("New-login-2", json.loads(account["extra_json"])["account_password"])
        self.assertEqual("retained-token", account["access_token"])
        self.assertEqual("mail-password", account["password"])
        self.assertEqual("pro", account["current_plan_type"])
        self.assertEqual("active", account["account_status"])
        self.assertEqual("并发套餐更新", account["note"])
        self.assertEqual("保留", json.loads(account["extra_json"])["unrelated"])
        self.assertEqual("New-login-2", self._private()["password"])
        self.assertEqual(42, self._private()["preserve"])
        self.assertEqual(checkpoint_before, registration.get_attempt(self.attempt_id)["checkpoint"])
        self.assertEqual("Old-login-1", confirmed.old_password)
        self.assertEqual(confirmed, self._transition(cp, "confirmed", confirmation="password_change_response"))
        self.assertIsNone(self.store.resume_password_recovery(**self.owner))

    def test_manual_confirmation_also_updates_original_linked_attempt(self):
        owner = self._manual_owner()
        cp = self._transition(self._prepare(owner), "started", owner)
        self._transition(cp, "confirmed", owner, "candidate_login")
        self.assertEqual("New-login-2", self._private()["password"])

    def test_confirm_accepts_candidate_already_applied_to_either_local_record(self):
        cp = self._transition(self._prepare(), "started")
        cp = self._transition(cp, "unknown")
        rs.patch_row(rs.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "New-login-2"})})
        confirmed = self._transition(cp, "confirmed", confirmation="candidate_login")
        self.assertEqual("confirmed", confirmed.state)
        self.assertEqual("New-login-2", self._private()["password"])

    def test_confirm_accepts_attempt_already_applied_candidate(self):
        cp = self._transition(self._prepare(), "started")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET private_context=jsonb_set(private_context,'{{password}}','\"New-login-2\"'::jsonb) WHERE id=%s", (self.attempt_id,))
        self._transition(cp, "confirmed", confirmation="candidate_login")
        self.assertEqual("New-login-2", json.loads(rs.get_row(rs.ACCOUNTS, self.account_id)["extra_json"])["account_password"])

    def test_registration_task_nullable_account_uses_exact_job_attempt_mapping(self):
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_tasks')} SET account_id=NULL WHERE id=(SELECT task_id FROM {pg.qualified('operation_runs')} WHERE id=%s)",
                        (self.owner["operation_run_id"],))
        cp = self._prepare()
        self.assertEqual(self.account_id, cp.account_id)
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_tasks')} SET account_id=999999 WHERE id=(SELECT task_id FROM {pg.qualified('operation_runs')} WHERE id=%s)",
                        (self.owner["operation_run_id"],))
        with self.assertRaises(self.store.PasswordRecoveryError):
            self.store.get_password_recovery(cp.recovery_id, **self.owner)

    def test_confirmation_waits_for_attempt_before_taking_account_lock(self):
        cp = self._transition(self._prepare(), "started")
        entered, finished = threading.Event(), threading.Event()
        errors = []
        def confirm():
            entered.set()
            try:
                self._transition(cp, "confirmed", confirmation="candidate_login")
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                finished.set()
        with pg.connect(row_factory=__import__('psycopg').rows.dict_row) as conn, conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout='800ms'")
            cur.execute(f"SELECT id FROM {pg.qualified('registration_attempts')} WHERE id=%s FOR UPDATE", (self.attempt_id,))
            thread = threading.Thread(target=confirm)
            thread.start()
            self.assertTrue(entered.wait(timeout=2))
            # 等待该事务真正阻塞在 Attempt，避免仅以线程启动时点判断锁序。
            with pg.connect() as observer, observer.cursor() as watching:
                for _ in range(100):
                    watching.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE %s",
                                     (f'%"{self.schema}".%',))
                    if watching.fetchone()[0]:
                        break
                    threading.Event().wait(0.01)
                else:
                    self.fail("确认事务未进入等待锁状态")
            try:
                cur.execute(f"SELECT id FROM {pg.qualified('registered_accounts')} WHERE id=%s FOR UPDATE", (self.account_id,))
            except Exception as exc:
                self.fail(f"确认事务与原密码存储锁序反向：{type(exc).__name__}")
        self.assertTrue(finished.wait(timeout=5))
        thread.join(timeout=5)
        self.assertEqual([], errors)

    def test_confirmation_does_not_reverse_finish_run_lock_order(self):
        cp = self._transition(self._prepare(), "started")
        done = threading.Event()
        failures = []
        def confirm():
            try:
                self._transition(cp, "confirmed", confirmation="candidate_login")
            except Exception as exc:
                failures.append(type(exc).__name__)
            finally:
                done.set()
        thread = threading.Thread(target=confirm)
        try:
            # finish_run 先持有 Run，再更新 Attempt；恢复流程不能反向等候该 Run。
            with pg.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {pg.qualified('registration_runs')} WHERE id=%s FOR UPDATE", (self.owner["registration_run_id"],))
                thread.start()
                self.assertTrue(done.wait(timeout=3), "恢复确认反向锁定了 RegistrationRun")
                cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET active_execution_id=NULL WHERE id=%s", (self.attempt_id,))
        finally:
            thread.join(timeout=5)
        self.assertEqual([], failures)

    def test_password_conflict_preserves_pending_record_and_both_local_values(self):
        cp = self._transition(self._prepare(), "started")
        rs.patch_row(rs.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "Other-password-3"})})
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "password_conflict"):
            self._transition(cp, "confirmed", confirmation="candidate_login")
        self.assertEqual("started", self.store.get_password_recovery(cp.recovery_id, **self.owner).state)
        self.assertEqual("Old-login-1", self._private()["password"])
        self.assertEqual("Other-password-3", json.loads(rs.get_row(rs.ACCOUNTS, self.account_id)["extra_json"])["account_password"])

    def test_attempt_password_conflict_rolls_back_account_and_recovery(self):
        cp = self._transition(self._prepare(), "started")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET private_context=jsonb_set(private_context,'{{password}}','\"Other-password-3\"'::jsonb) WHERE id=%s", (self.attempt_id,))
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "password_conflict"):
            self._transition(cp, "confirmed", confirmation="candidate_login")
        self.assertEqual("Old-login-1", json.loads(rs.get_row(rs.ACCOUNTS, self.account_id)["extra_json"])["account_password"])
        self.assertEqual("started", self.store.get_password_recovery(cp.recovery_id, **self.owner).state)

    def test_password_change_after_prepare_stops_before_dispatch(self):
        cp = self._prepare()
        rs.patch_row(rs.ACCOUNTS, self.account_id, {"extra_json": json.dumps({"account_password": "Other-password-3"})})
        for action in (lambda: self._prepare(), lambda: self.store.resume_password_recovery(**self.owner),
                       lambda: self._transition(cp, "started")):
            with self.assertRaisesRegex(self.store.PasswordRecoveryError, "password_conflict"):
                action()

    def test_manual_prepare_checks_original_attempt_before_generating_candidate(self):
        owner = self._manual_owner()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET private_context=jsonb_set(private_context,'{{password}}','\"Other-password-3\"'::jsonb) WHERE id=%s", (self.attempt_id,))
        calls = []
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "password_conflict"):
            self.store.prepare_password_recovery(**owner, candidate_factory=lambda: calls.append(1) or "candidate")
        self.assertEqual([], calls)

    def test_registration_job_replaced_execution_cannot_access_checkpoint(self):
        cp = self._prepare()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_jobs')} SET execution_id='replacement' WHERE id=(SELECT job_id FROM {pg.qualified('registration_runs')} WHERE id=%s)",
                        (self.owner["registration_run_id"],))
        with self.assertRaises(self.store.PasswordRecoveryError):
            self.store.get_password_recovery(cp.recovery_id, **self.owner)

    def test_replaced_job_uuid_cannot_access_or_advance_checkpoint(self):
        cp = self._prepare()
        run = registration.get_run(self.owner["registration_run_id"])
        rs.patch_row(rs.JOBS, int(run["job_id"]), {"job_uuid": str(uuid.uuid4())})
        for action in (lambda: self.store.get_password_recovery(cp.recovery_id, **self.owner),
                       lambda: self.store.resume_password_recovery(**self.owner),
                       lambda: self._transition(cp, "started")):
            with self.subTest(action=action), self.assertRaisesRegex(
                    self.store.PasswordRecoveryError, "registration_operation_mapping_mismatch"):
                action()

    def test_different_real_registration_run_cannot_access_checkpoint(self):
        cp = self._prepare()
        other = jobs.create_job("outlook")
        jobs.update_job(int(other["id"]), email="other@example.test")
        context = self._start_job_run(other)
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "registration_execution_mismatch"):
            self.store.get_password_recovery(cp.recovery_id, **{
                **self.owner, "registration_run_id": context["run_id"],
            })

    def test_replaced_attempt_execution_cannot_access_checkpoint(self):
        cp = self._prepare()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('registration_attempts')} SET active_execution_id='replacement' WHERE id=%s",
                        (self.attempt_id,))
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "registration_identity_mismatch"):
            self.store.get_password_recovery(cp.recovery_id, **self.owner)

    def test_wrong_master_key_and_ciphertext_fail_without_exposing_credentials(self):
        cp = self._prepare()
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            with self.assertRaisesRegex(self.store.PasswordRecoveryError, "credential_decryption_failed"):
                self.store.get_password_recovery(cp.recovery_id, **self.owner)
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('account_password_recoveries')} SET credential_ciphertext='broken' WHERE id=%s", (cp.recovery_id,))
        with self.assertRaisesRegex(self.store.PasswordRecoveryError, "credential_decryption_failed"):
            self.store.get_password_recovery(cp.recovery_id, **self.owner)

    def test_new_manual_execution_can_take_over_expired_lease_candidate(self):
        old = self._manual_owner()
        cp = self._transition(self._prepare(old), "started", old)
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {pg.qualified('operation_runs')} SET status='interrupted' WHERE id=%s", (old["operation_run_id"],))
            cur.execute(f"UPDATE {pg.qualified('account_operation_leases')} SET expires_at=now()-interval '1 second'")
        new = self._manual_owner()
        recovered = self.store.resume_password_recovery(**new)
        self.assertEqual(cp.recovery_id, recovered.recovery_id)
        self.assertEqual(cp.password, recovered.password)
        with self.assertRaises(self.store.PasswordRecoveryError):
            self.store.get_password_recovery(cp.recovery_id, **old)

    def test_database_failure_after_account_update_rolls_back_whole_transaction(self):
        cp = self._transition(self._prepare(), "started")
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE FUNCTION {pg.qualified('reject_recovery')}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '测试事务回滚'; END $$")
            cur.execute(f"CREATE TRIGGER reject_recovery BEFORE UPDATE ON {pg.qualified('account_password_recoveries')} FOR EACH ROW EXECUTE FUNCTION {pg.qualified('reject_recovery')}()")
        try:
            with self.assertRaises(self.store.PasswordRecoveryError):
                self._transition(cp, "confirmed", confirmation="candidate_login")
            self.assertEqual("Old-login-1", self._private()["password"])
            self.assertEqual("Old-login-1", json.loads(rs.get_row(rs.ACCOUNTS, self.account_id)["extra_json"])["account_password"])
            self.assertEqual("started", self.store.get_password_recovery(cp.recovery_id, **self.owner).state)
        finally:
            with pg.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DROP TRIGGER reject_recovery ON {pg.qualified('account_password_recoveries')}")
                cur.execute(f"DROP FUNCTION {pg.qualified('reject_recovery')}()")

    def test_missing_key_fails_before_generating_candidate(self):
        calls = []
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": ""}):
            with self.assertRaisesRegex(self.store.PasswordRecoveryError, "encryption_key_missing"):
                self.store.prepare_password_recovery(**self.owner, candidate_factory=lambda: calls.append(1) or "candidate")
        self.assertEqual([], calls)

    def test_pending_survives_operation_history_deletion(self):
        cp = self._prepare()
        with pg.connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {pg.qualified('operation_runs')} WHERE id=%s", (self.owner["operation_run_id"],))
            cur.execute(f"SELECT COUNT(*) FROM {pg.qualified('account_password_recoveries')} WHERE id=%s", (cp.recovery_id,))
            self.assertEqual(1, cur.fetchone()[0])

    def test_normal_creation_checkpoint_still_cannot_replace_password(self):
        with self.assertRaisesRegex(ValueError, "拒绝替换"):
            registration.save_password_checkpoint(self.attempt_id, email=self.email, password="New-login-2", state="prepared",
                run_id=self.owner["registration_run_id"], execution_id=self.owner["registration_execution_id"])

    def test_invalid_transition_cannot_confirm_without_explicit_evidence(self):
        cp = self._prepare()
        for state, confirmation in (("confirmed", None), ("confirmed", "page_changed"), ("unknown", None)):
            with self.subTest(state=state, confirmation=confirmation), self.assertRaises(self.store.PasswordRecoveryError):
                self._transition(cp, state, confirmation=confirmation)
