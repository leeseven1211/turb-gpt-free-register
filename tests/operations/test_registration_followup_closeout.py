# -*- coding: utf-8 -*-
"""注册账号配置补跑收口的后端状态回写回归测试。"""
from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import patch

from core import account_task_store, db
from core.operations import task_gateway
from core.storage import postgres as postgres_store
from core.storage import records, registration
from core.storage.operations import runtime as operation_runtime
from core.storage.operations import store as operation
from core.registration import service
from tests.support_pg import PostgresTestCase


class RegistrationFollowupCloseoutTests(PostgresTestCase):
    def setUp(self):
        self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        self.enterContext(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        records.reset_ready()
        records.init()
        operation.reset_ready()
        operation.init()

        self.email = "registration-followup-closeout@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email,
            "access_token": "fixture-access-token",
            "extra_json": {
                "account_password": "fixture-password",
                "account_password_state": "confirmed",
            },
            "plan_check_status": "success",
            "totp_secret": "fixture-totp-secret",
            "codex_status": "success",
        })
        self.snapshot = {
            "password_enabled": True,
            "plan_check_enabled": True,
            "twofa_enabled": True,
            "codex_enabled": False,
            "password_driver": "protocol",
            "twofa_driver": "protocol",
        }

        root = db.create_job("outlook")
        db.update_job(root["id"], status="failed", email=self.email, account_id=self.account_id)
        registration.finish_run(registration.list_runs(root["attempt_id"])[0]["id"], status="failed")

        self.job, _ = db.create_retry_job(
            root["id"],
            job_type="registration_resume",
            email_source="outlook",
            email=self.email,
            account_id=self.account_id,
            data={
                "config_snapshot": dict(self.snapshot),
                "progress_steps": {
                    "twofa": {"state": "failed", "detail": "历史 2FA 失败"},
                },
            },
        )
        self.run = registration.start_run(
            self.job["attempt_id"],
            job_id=self.job["id"],
            action_type="registration_resume",
            execution_id="fixture-registration-followup",
            initial_status="running",
        )
        registration.finish_run(
            self.run["id"],
            status="partial_success",
            error_code="twofa_setup_failed",
            error_message="历史 2FA 失败",
        )
        db.update_job(
            self.job["id"],
            status="partial_success",
            email=self.email,
            account_id=self.account_id,
            error="历史 2FA 失败",
        )
        records.patch_row(records.JOBS, self.job["id"], {
            "progress_steps": {
                "twofa": {"state": "failed", "detail": "历史 2FA 失败"},
            },
        })

        parent = operation.find_task_by_source(
            "registration_chains",
            f"{root['id']}:registration_resume",
            include_runs=True,
        )
        self.assertIsNotNone(parent)
        self.parent_id = int(parent["id"])
        self.parent_run_id = int(operation.get_task(self.parent_id, include_events=False)["last_run_id"])
        operation.append_runtime_event(
            self.parent_run_id,
            stage="twofa",
            state="failed",
            level="ERROR",
            message="历史 2FA 失败",
        )

    def enqueue_child(self, *, source_job_id: int | None = None, source_tag: str = "") -> dict:
        job_id = int(source_job_id or self.job["id"])
        settings = dict(self.snapshot)
        source_suffix = source_tag or str(job_id)
        return task_gateway.submit_durable_operation(
            task_type="account_setup_retry",
            account_id=self.account_id,
            email=self.email,
            trigger="registration_job_retry",
            source_system="webui_runtime",
            source_id=f"registration-account-setup:{source_suffix}",
            parent_task_id=self.parent_id,
            resource_family="openai_interactive",
            data={
                "steps": ["twofa"],
                "required_steps": ["twofa"],
                "task_trigger": "registration_job_retry",
                "source_job_id": job_id,
            },
            config_snapshot=settings,
            config_allowlist=tuple(settings),
            dispatch=False,
        )

    def enqueue_plan_check(self) -> dict:
        settings = dict(self.snapshot)
        return task_gateway.submit_durable_operation(
            task_type="plan_check",
            account_id=self.account_id,
            email=self.email,
            trigger="registration_job_retry_plan_check",
            source_system="native_operations",
            source_id=f"registration-plan-check:{self.job['id']}",
            resource_family="openai_interactive",
            data={
                "task_trigger": "registration_job_retry_plan_check",
                "source_job_id": int(self.job["id"]),
            },
            config_snapshot=settings,
            config_allowlist=tuple(settings),
            dispatch=False,
        )

    def enqueue_codex_retry(self) -> dict:
        settings = {**self.snapshot, "codex_enabled": True}
        return task_gateway.submit_durable_operation(
            task_type="codex_retry",
            account_id=self.account_id,
            email=self.email,
            trigger="registration_job_retry_codex",
            source_system="native_operations",
            source_id=f"registration-codex-retry:{self.job['id']}",
            parent_task_id=self.parent_id,
            resource_family="openai_interactive",
            data={
                "task_trigger": "registration_job_retry_codex",
                "source_job_id": int(self.job["id"]),
            },
            config_snapshot=settings,
            config_allowlist=tuple(settings),
            dispatch=False,
        )

    def parent(self) -> dict:
        return operation.get_task(self.parent_id, include_events=True)

    def persisted_task_run(self, task_id: int, run_id: int) -> tuple[dict, dict]:
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id,status,last_run_id,batch_id,error_message "
                f"FROM {operation._table('operation_tasks')} WHERE id=%s",
                (int(task_id),),
            )
            task = dict(cur.fetchone())
            cur.execute(
                f"SELECT id,task_id,status,error_message FROM {operation._table('operation_runs')} WHERE id=%s",
                (int(run_id),),
            )
            run = dict(cur.fetchone())
        return task, run

    def test_real_child_success_closes_legacy_job_and_sync_keeps_failure_evidence(self):
        queued = self.enqueue_child()
        child = operation.get_task(queued["task_id"], include_events=False)
        self.assertEqual("webui_runtime", child["source_system"])
        self.assertEqual("account_setup_retry", child["task_type"])
        self.assertEqual(self.parent_id, child["parent_task_id"])
        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])

        operation.finish_run(
            queued["run_id"],
            status="success",
            result_summary={"setup_step_receipts": [{
                "step": "twofa", "ok": True, "receipt_state": "confirmed",
            }]},
        )

        child_after = operation.get_task(queued["task_id"], include_events=False)
        self.assertEqual("success", child_after["status"])
        self.assertEqual("success", operation.get_run(queued["run_id"])["status"])
        parent_batch_id = self.parent()["batch_id"]
        self.assertIsNotNone(parent_batch_id)
        batch = next(item for item in operation.list_batches() if item["id"] == parent_batch_id)
        self.assertEqual(1, batch["success_count"])

        closed = db.get_job(self.job["id"])
        self.assertEqual("success", closed["status"])
        self.assertEqual("", closed["error_message"] or "")
        self.assertEqual("failed", closed["progress_steps"]["twofa"]["state"])
        self.assertEqual("历史 2FA 失败", closed["progress_steps"]["twofa"]["detail"])

        task = self.parent()
        self.assertTrue(any(event["message"] == "历史 2FA 失败" for event in task["events"]))
        operation.sync_registration_job(self.job["id"])
        synced = db.get_job(self.job["id"])
        self.assertEqual("success", synced["status"])
        self.assertEqual("", synced["error_message"] or "")
        self.assertTrue(any(event["message"] == "历史 2FA 失败" for event in self.parent()["events"]))

    def test_child_success_rolls_back_with_parent_job_and_child_run(self):
        queued = self.enqueue_child()

        with self.assertRaisesRegex(RuntimeError, "故意回滚"):
            with operation._connect() as conn:
                operation_runtime.finish_run(
                    queued["run_id"],
                    status="success",
                    result_summary={"ok": True},
                    _settlement_conn=conn,
                )
                raise RuntimeError("故意回滚")

        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])
        self.assertNotEqual("success", operation.get_run(queued["run_id"])["status"])

    def test_old_child_success_cannot_close_job_after_child_retry_created(self):
        queued = self.enqueue_child()
        operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})
        db.update_job(self.job["id"], status="partial_success", error="新的补跑待完成")

        retried = operation.retry_runtime_task(queued["task_id"], trigger="manual_retry")
        self.assertNotEqual(queued["run_id"], retried["id"])
        operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})

        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])
        self.assertEqual("queued", operation.get_run(retried["id"])["status"])

    def test_old_child_success_cannot_close_old_job_after_parent_run_is_newer(self):
        queued = self.enqueue_child()
        newer, _ = db.create_retry_job(
            self.job["id"],
            job_type="registration_resume",
            email_source="outlook",
            email=self.email,
            account_id=self.account_id,
        )
        latest_parent = operation.get_task(self.parent_id, include_events=False)["last_run_id"]
        self.assertNotEqual(self.parent_run_id, latest_parent)

        operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})

        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])
        self.assertIn(db.get_job(newer["id"])["status"], {"pending", "queued", "running"})

    def test_closeout_uses_job_snapshot_and_does_not_treat_missing_required_step_as_skipped(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"codex_status": "failed"})
        records.patch_row(records.JOBS, self.job["id"], {
            "data": {
                "config_snapshot": {
                    "password_enabled": True,
                    "plan_check_enabled": True,
                    "twofa_enabled": True,
                    "codex_enabled": False,
                },
                "progress_steps": {},
            },
        })
        queued = self.enqueue_child()
        operation.finish_run(
            queued["run_id"],
            status="success",
            result_summary={"setup_step_receipts": [{
                "step": "twofa", "ok": True, "receipt_state": "confirmed",
            }]},
        )
        self.assertEqual("success", db.get_job(self.job["id"])["status"])

        records.patch_row(records.ACCOUNTS, self.account_id, {"totp_secret": ""})
        db.update_job(self.job["id"], status="partial_success", error="等待原要求步骤")
        retried = operation.retry_runtime_task(queued["task_id"], trigger="manual_retry")
        operation.finish_run(
            retried["id"],
            status="success",
            result_summary={"setup_step_receipts": [{
                "step": "twofa", "ok": True, "receipt_state": "confirmed",
            }]},
        )
        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])

    def test_periodic_closeout_repairs_historical_successful_child(self):
        queued = self.enqueue_child()
        from core.storage.operations import registration_completion

        with patch.object(
            registration_completion,
            "reconcile_parent_registration_job_for_child",
            return_value=False,
        ):
            operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})

        self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])
        real_connect = postgres_store.connect

        @contextmanager
        def schema_connection(*args, **kwargs):
            with real_connect(*args, **kwargs) as conn, conn.cursor() as cur:
                cur.execute(
                    f"SET search_path TO {postgres_store.quote_identifier(self.schema)}"
                )
                yield conn

        with patch.object(postgres_store, "connect", side_effect=schema_connection):
            closed = service.close_jobs_for_completed_account_tasks(limit=50)
        self.assertGreaterEqual(closed, 1)
        self.assertEqual("success", db.get_job(self.job["id"])["status"])
        self.assertEqual("", db.get_job(self.job["id"])["error_message"] or "")

    def test_native_plan_check_success_closes_job_from_failed_account_status(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "plan_check_status": "failed",
            "plan_check_ok": False,
        })
        queued = self.enqueue_plan_check()
        self.assertIsNone(operation.get_task(queued["task_id"], include_events=False)["parent_task_id"])
        records.patch_row(records.ACCOUNTS, self.account_id, {
            "plan_check_status": "failed",
            "plan_check_ok": False,
        })
        self.assertEqual("failed", records.get_row(records.ACCOUNTS, self.account_id)["plan_check_status"])

        records.patch_row(records.ACCOUNTS, self.account_id, {
            "plan_check_status": "success",
            "plan_check_ok": True,
        })
        operation.finish_run(
            queued["run_id"],
            status="success",
            result_summary={"ok": True, "current_plan_type": "free"},
        )

        self.assertEqual("success", operation.get_task(queued["task_id"], include_events=False)["status"])
        self.assertEqual("success", operation.get_run(queued["run_id"])["status"])
        self.assertEqual("success", records.get_row(records.ACCOUNTS, self.account_id)["plan_check_status"])
        self.assertEqual("success", db.get_job(self.job["id"])["status"])
        self.assertEqual("", db.get_job(self.job["id"])["error_message"] or "")
        self.assertEqual("success", self.parent()["status"])
        batch = next(item for item in operation.list_batches() if item["id"] == self.parent()["batch_id"])
        self.assertEqual(1, batch["success_count"])

    def test_native_codex_retry_success_closes_job_and_persists_parent_success(self):
        job_data = dict(db.get_job(self.job["id"]).get("data") or {})
        job_data["config_snapshot"] = {**self.snapshot, "codex_enabled": True}
        records.patch_row(records.JOBS, self.job["id"], {"data": job_data})
        records.patch_row(records.ACCOUNTS, self.account_id, {"codex_status": "failed"})

        queued = self.enqueue_codex_retry()
        child = operation.get_task(queued["task_id"], include_events=False)
        self.assertEqual("native_operations", child["source_system"])
        self.assertEqual(self.parent_id, child["parent_task_id"])
        parent_before = operation.get_task(self.parent_id, include_events=False)
        parent_run_id = int(parent_before["last_run_id"])
        batch_id = int(parent_before["batch_id"])

        records.patch_row(records.ACCOUNTS, self.account_id, {"codex_status": "success"})
        operation.finish_run(
            queued["run_id"],
            status="success",
            result_summary={"ok": True, "codex_status": "success"},
        )

        child_after = operation.get_task(queued["task_id"], include_events=False)
        self.assertEqual("success", child_after["status"])
        self.assertEqual("success", operation.get_run(queued["run_id"])["status"])
        parent_after, parent_run_after = self.persisted_task_run(self.parent_id, parent_run_id)
        self.assertEqual("success", parent_after["status"])
        self.assertEqual("success", parent_run_after["status"])
        self.assertEqual("success", db.get_job(self.job["id"])["status"])
        batch = next(item for item in operation.list_batches() if item["id"] == batch_id)
        self.assertEqual(1, batch["success_count"])

    def test_late_child_success_does_not_overwrite_cancelled_or_stopped_parent_run(self):
        for terminal_status in ("cancelled", "stopped"):
            with self.subTest(terminal_status=terminal_status):
                queued = self.enqueue_child(source_tag=f"late-parent-{terminal_status}")
                parent_before = operation.get_task(self.parent_id, include_events=False)
                parent_run_id = int(parent_before["last_run_id"])
                parent_batch_id = int(parent_before["batch_id"])
                db.update_job(
                    self.job["id"],
                    status="partial_success",
                    email=self.email,
                    account_id=self.account_id,
                    error="历史 2FA 失败",
                )
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {operation._table('operation_runs')}
                            SET status=%s, completed_at=now(), progress_stage='complete',
                                error_message=%s
                            WHERE id=%s""",
                        (terminal_status, f"父协调 Run 已{terminal_status}", parent_run_id),
                    )
                    cur.execute(
                        f"""UPDATE {operation._table('operation_tasks')}
                            SET status=%s, current_stage='complete', completed_at=now(),
                                error_message=%s
                            WHERE id=%s""",
                        (terminal_status, f"父协调 Task 已{terminal_status}", self.parent_id),
                    )
                operation.finish_run(
                    queued["run_id"],
                    status="success",
                    result_summary={"ok": True},
                )

                parent_after, parent_run_after = self.persisted_task_run(self.parent_id, parent_run_id)
                self.assertEqual(terminal_status, parent_after["status"])
                self.assertEqual(terminal_status, parent_run_after["status"])
                self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])
                self.assertEqual("历史 2FA 失败", db.get_job(self.job["id"])["error_message"])
                self.assertEqual(parent_batch_id, parent_after["batch_id"])

    def test_closeout_defers_while_parent_batch_lock_is_held_then_repairs(self):
        queued = self.enqueue_child()
        from core.storage.operations import registration_completion

        with patch.object(
            registration_completion,
            "reconcile_parent_registration_job_for_child",
            return_value=False,
        ):
            operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})
        parent = operation.get_task(self.parent_id, include_events=False)
        batch_id = int(parent["batch_id"])

        def invoke_helper() -> bool:
            with operation._connect() as conn, conn.cursor() as cur:
                return registration_completion.reconcile_parent_registration_job_for_child(
                    cur, queued["task_id"], child_run_id=queued["run_id"],
                )

        for lock_kind in ("row", "advisory"):
            with self.subTest(lock_kind=lock_kind):
                db.update_job(
                    self.job["id"],
                    status="partial_success",
                    email=self.email,
                    account_id=self.account_id,
                    error="锁竞争下待收口",
                )
                locked = Event()
                release = Event()

                def hold_lock():
                    with operation._connect() as conn, conn.cursor() as cur:
                        if lock_kind == "row":
                            cur.execute(
                                f"SELECT id FROM {operation._table('operation_batches')} "
                                "WHERE id=%s FOR UPDATE",
                                (batch_id,),
                            )
                        else:
                            cur.execute("SELECT pg_advisory_xact_lock(%s)", (batch_id,))
                        locked.set()
                        if not release.wait(5):
                            raise RuntimeError("锁释放事件超时")

                with ThreadPoolExecutor(max_workers=2) as pool:
                    holder = pool.submit(hold_lock)
                    self.assertTrue(locked.wait(5))
                    helper = pool.submit(invoke_helper)
                    try:
                        changed = helper.result(timeout=2)
                    except TimeoutError:
                        self.fail(f"helper 在 {lock_kind} 锁竞争下阻塞")
                    finally:
                        release.set()
                    holder.result(timeout=5)
                self.assertFalse(changed)
                self.assertEqual("partial_success", db.get_job(self.job["id"])["status"])

                closed = service.close_jobs_for_completed_account_tasks(limit=50)
                self.assertGreaterEqual(closed, 1)
                task_after, run_after = self.persisted_task_run(
                    self.parent_id, int(parent["last_run_id"]),
                )
                self.assertEqual("success", task_after["status"])
                self.assertEqual("success", run_after["status"])
                self.assertEqual("success", db.get_job(self.job["id"])["status"])
                batch = next(item for item in operation.list_batches() if item["id"] == batch_id)
                self.assertEqual(1, batch["success_count"])

    def test_late_child_success_does_not_reopen_cancelled_or_stopped_job(self):
        for terminal_status in ("cancelled", "stopped"):
            with self.subTest(terminal_status=terminal_status):
                queued = self.enqueue_child()
                expected_error = f"原注册任务已{terminal_status}"
                db.update_job(
                    self.job["id"],
                    status=terminal_status,
                    email=self.email,
                    account_id=self.account_id,
                    error=expected_error,
                )
                operation.finish_run(queued["run_id"], status="success", result_summary={"ok": True})

                closed = db.get_job(self.job["id"])
                self.assertEqual(terminal_status, closed["status"])
                self.assertEqual(expected_error, closed["error_message"])
