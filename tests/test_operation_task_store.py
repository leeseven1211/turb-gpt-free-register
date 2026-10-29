# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from psycopg.errors import DeadlockDetected

from core import account_task_store, db, operation_task_store, postgres_store, record_store, registration_debug, task_run_log
from core.storage import operation, registration
from core.operations import task_gateway
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class OperationTaskStoreTests(PostgresTestCase):
    def setUp(self):
        self.task_log_tempdir = tempfile.TemporaryDirectory()
        self.task_log_root_patch = patch.object(task_run_log, "_LOG_ROOT", Path(self.task_log_tempdir.name))
        self.task_log_tasks_patch = patch.object(task_run_log, "_TASK_LOG_ROOT", Path(self.task_log_tempdir.name) / "tasks")
        self.task_log_root_patch.start()
        self.task_log_tasks_patch.start()
        self.schema_patch = patch.object(account_task_store, "_SCHEMA", self.schema)
        self.ready_patch = patch.object(account_task_store, "_READY_KEY", "")
        self.schema_patch.start()
        self.ready_patch.start()
        account_task_store.init()
        operation_task_store.reset_ready()
        operation_task_store.init()

    def tearDown(self):
        self.ready_patch.stop()
        self.schema_patch.stop()
        self.task_log_tasks_patch.stop()
        self.task_log_root_patch.stop()
        self.task_log_tempdir.cleanup()

    def test_password_page_failures_keep_failed_status_and_unknown_receipt(self):
        for index, (task_type, code) in enumerate((
            ("token_refresh", "password_change_required"),
            ("live_check", "password_page_error"),
        )):
            account_id = self._seed_runtime_account(f"page-error-{index}@example.test")
            batch = operation_task_store.create_runtime_batch(
                batch_type=task_type, title="页面错误", requested_count=1, trigger="test",
            )
            task = operation_task_store.create_runtime_task(
                task_type=task_type, account_id=account_id,
                email=f"page-error-{index}@example.test", trigger="test", batch_id=int(batch["id"]),
            )
            run_id = int(task["run"]["id"])
            execution = f"page-error-{index}"
            operation_task_store.claim_run(run_id, execution_id=execution, worker_pid=123)
            lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
            operation_task_store.record_remote_intent(run_id, execution_id=execution, lease_token=lease, action="token_refresh")
            operation_task_store.record_remote_receipt(run_id, execution_id=execution, lease_token=lease, outcome="unknown", detail={"response_observed": False})
            completed = operation_task_store.finish_run(
                run_id, status="failed", error="密码页显示明确错误",
                result_summary={"cause_code": code, "status": "failed"},
                execution_id=execution, lease_token=lease,
            )
            self.assertEqual("failed", completed["status"])
            self.assertEqual("request_unknown", completed["result_summary"]["outcome"])
            self.assertEqual("unknown", completed["data"]["remote_intent"]["receipt_state"])
            self.assertFalse(completed["data"]["remote_receipt"]["detail"]["response_observed"])
            task_detail = operation_task_store.get_task(int(task["id"]))
            self.assertEqual("failed", task_detail["status"])
            self.assertEqual("retry", task_detail["next_actions"][0]["action"])
            filtered = operation_task_store.list_tasks(task_type=task_type, status="failed")
            self.assertIn(int(task["id"]), [row["id"] for row in filtered["items"]])
            batch_result = next(row for row in operation_task_store.list_batches() if row["id"] == batch["id"])
            self.assertEqual(1, batch_result["failed_count"])
            with postgres_store.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {postgres_store.qualified('operation_tasks')} SET completed_at=now() - interval '8 days' WHERE id=%s", (int(task["id"]),))
                cur.execute(f"UPDATE {postgres_store.qualified('operation_runs')} SET completed_at=now() - interval '8 days' WHERE id=%s", (run_id,))
            operation_task_store.cleanup_terminal_history(retention_days=7, limit=100, archive=lambda snapshot: None)
            self.assertIsNotNone(operation_task_store.get_task(int(task["id"])))
            retried = operation_task_store.retry_runtime_task(int(task["id"]))
            self.assertEqual("queued", retried["status"])
            self.assertEqual("unknown", operation_task_store.get_run(run_id)["data"]["remote_intent"]["receipt_state"])

    def test_password_page_failure_does_not_change_other_remote_unknown_tasks(self):
        for index, (task_type, status, cause) in enumerate((
            ("extract_link", "failed", "password_change_required"),
            ("registration_resume", "failed", "password_page_error"),
            ("token_refresh", "cancelled", "password_change_required"),
            ("token_refresh", "failed", "password_result_unknown"),
        )):
            account_id = self._seed_runtime_account(f"page-control-{index}@example.test")
            task = operation_task_store.create_runtime_task(
                task_type=task_type, account_id=account_id,
                email=f"page-control-{index}@example.test", trigger="test",
            )
            run_id = int(task["run"]["id"])
            execution = f"page-control-{index}"
            operation_task_store.claim_run(run_id, execution_id=execution, worker_pid=123)
            lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
            operation_task_store.record_remote_intent(run_id, execution_id=execution, lease_token=lease, action="token_refresh")
            operation_task_store.record_remote_receipt(run_id, execution_id=execution, lease_token=lease, outcome="unknown")
            completed = operation_task_store.finish_run(
                run_id, status=status, error="密码页显示明确错误", result_summary={"cause_code": cause},
                execution_id=execution, lease_token=lease,
            )
            self.assertEqual("attention_required", completed["status"])
            self.assertEqual("unknown", completed["data"]["remote_intent"]["receipt_state"])

    def test_password_page_failure_keeps_unknown_parent_reconciliation(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="parent-page@example.test",
            trigger="test", resource_family="completion_coordinator",
        )
        account_id = self._seed_runtime_account("child-page@example.test")
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=account_id, email="child-page@example.test",
            trigger="test", parent_task_id=int(parent["id"]),
        )
        run_id = int(child["run"]["id"])
        operation_task_store.claim_run(run_id, execution_id="child-page", worker_pid=123)
        lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation_task_store.record_remote_intent(run_id, execution_id="child-page", lease_token=lease, action="token_refresh")
        operation_task_store.record_remote_receipt(run_id, execution_id="child-page", lease_token=lease, outcome="unknown")
        completed = operation_task_store.finish_run(
            run_id, status="failed", error="密码页显示明确错误", result_summary={"cause_code": "password_change_required"},
            execution_id="child-page", lease_token=lease,
        )
        self.assertEqual("failed", completed["status"])
        self.assertEqual("attention_required", operation_task_store.get_task(int(parent["id"]))["status"])

    def test_password_page_unknown_receipt_survives_successful_retry_retention(self):
        account_id = self._seed_runtime_account("page-retry-retention@example.test")
        task = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=account_id,
            email="page-retry-retention@example.test", trigger="test",
        )
        run_id = int(task["run"]["id"])
        operation_task_store.claim_run(run_id, execution_id="page-old", worker_pid=123)
        lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation_task_store.record_remote_intent(run_id, execution_id="page-old", lease_token=lease, action="token_refresh")
        operation_task_store.record_remote_receipt(run_id, execution_id="page-old", lease_token=lease, outcome="unknown")
        operation_task_store.finish_run(
            run_id, status="failed", error="密码页显示明确错误", result_summary={"cause_code": "password_change_required"},
            execution_id="page-old", lease_token=lease,
        )
        retry = operation_task_store.retry_runtime_task(int(task["id"]))
        operation_task_store.finish_run(int(retry["id"]), status="success")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres_store.qualified('operation_tasks')} SET completed_at=now() - interval '8 days' WHERE id=%s", (int(task["id"]),))
            cur.execute(f"UPDATE {postgres_store.qualified('operation_runs')} SET completed_at=now() - interval '8 days' WHERE task_id=%s", (int(task["id"]),))
        archived = []
        operation_task_store.cleanup_terminal_history(retention_days=7, limit=100, archive=lambda snapshot: archived.append(snapshot))
        self.assertIsNotNone(operation_task_store.get_task(int(task["id"])))
        self.assertEqual("unknown", operation_task_store.get_run(run_id)["data"]["remote_intent"]["receipt_state"])

    def test_existing_projection_queue_is_locked_before_batch_sync(self):
        class RecordingCursor:
            def __init__(self):
                self.calls = []

            def execute(self, query, params=()):
                self.calls.append((query, params))

            def fetchone(self):
                return {"id": 9}

        cur = RecordingCursor()
        operation._lock_existing_projection_queue(cur, 9)

        self.assertEqual(1, len(cur.calls))
        self.assertIn("operation_projection_queue", cur.calls[0][0])
        self.assertIn("FOR UPDATE", cur.calls[0][0])
        self.assertEqual((9,), cur.calls[0][1])

    def _seed_pending_registration(self):
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "pending@example.com",
            "access_token": "",
            "codex_status": "failed",
            "created_at": "2026-08-25T10:00:00",
            "updated_at": "2026-08-25T10:01:00",
            "extra_json": json.dumps({
                "account_password": "never-expose-this",
                "registration_checkpoint": "email_verification_pending",
            }),
        })
        job_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "job-pending-1",
            "email": "pending@example.com",
            "status": "partial_success",
            "job_type": "registration",
            "account_id": account_id,
            "created_at": "2026-08-25T10:00:00",
            "updated_at": "2026-08-25T10:02:00",
            "completed_at": "2026-08-25T10:02:00",
            "progress_stage": "complete",
            "progress_steps": {
                "email_otp": {"state": "success", "detail": "邮箱验证码已通过"},
                "profile": {"state": "failed", "detail": "停在 about-you"},
            },
            "error_message": "停在 about-you，未取得 session",
        })
        return account_id, job_id

    def test_registration_unknown_projection_keeps_confirmed_response_and_safe_cause(self):
        job = db.create_job("outlook")
        job_id = int(job["id"])
        attempt_id = int(job["attempt_id"])
        registration.advance_checkpoint(
            attempt_id, "password_confirmed", remote_identity_state="confirmed",
        )
        registration.mark_request_unknown(
            attempt_id, target="identity", identity_response_confirmed=True,
            detail={"cause_code": "email_otp_no_mail"},
        )
        pending_account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "pending-unknown@example.test",
            "access_token": "",
            "extra_json": json.dumps({"registration_checkpoint": "email_verification_pending"}),
        })
        db.update_job(
            job_id, status="request_unknown", error="request_unknown",
            email="pending-unknown@example.test", account_id=pending_account_id,
            completed_at="2026-10-08T12:00:00+00:00",
        )
        registration_run = registration.list_runs(attempt_id)[0]
        registration.finish_run(
            int(registration_run["id"]), status="request_unknown", error_code="request_unknown",
            error_message="request_unknown",
            result_summary={
                "outcome": "request_unknown", "cause_code": "email_otp_no_mail",
                "register_response_confirmed": True, "raw_response": "不可投影",
            },
        )
        operation_task_store.sync_registration_job(job_id)
        operation_task_store.sync_registration_job(job_id)

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {postgres_store.qualified('operation_tasks')} "
                "WHERE source_system='registration_chains' AND source_id=%s",
                (f"{job_id}:registration",),
            )
            task_id = int(cur.fetchone()[0])
        detail = operation_task_store.get_task(task_id, include_events=False)
        self.assertEqual("confirmed", detail["attempt"]["remote_identity_state"])
        self.assertEqual("request_unknown", detail["attempt"]["remote_account_state"])
        self.assertEqual("request_unknown", detail["target_status"])
        self.assertEqual([], detail["next_actions"])
        self.assertEqual("request_unknown", detail["result_summary"]["outcome"])
        self.assertEqual("email_otp_no_mail", detail["result_summary"]["cause_code"])
        self.assertTrue(detail["result_summary"]["register_response_confirmed"])
        self.assertNotIn("raw_response", detail["result_summary"])
        run = detail["runs"][-1]
        self.assertEqual("email_otp_no_mail", run["error_code"])
        self.assertEqual("email_otp_no_mail", run["result_summary"]["cause_code"])
        listed = operation_task_store.list_tasks(page_size=20)["items"]
        listed_task = next(item for item in listed if int(item["id"]) == task_id)
        self.assertEqual("email_otp_no_mail", listed_task["result_summary"]["cause_code"])

    def test_reconcile_is_idempotent_and_preserves_pending_registration_target(self):
        account_id, job_id = self._seed_pending_registration()
        batch_id = account_task_store.create_batch(
            action_type="account_setup_retry", trigger="manual", total_count=1,
        )
        legacy_task_id = account_task_store.create_task(
            task_type="account_setup_retry", account_id=account_id,
            email="pending@example.com", trigger="manual", batch_id=batch_id,
        )
        account_task_store.finish_task(
            legacy_task_id, status="failed", message="账号配置失败", error="停在 about-you",
        )

        operation_task_store.reconcile_all()
        first = operation_task_store.verify()
        operation_task_store.reconcile_all()
        second = operation_task_store.verify()

        self.assertTrue(first["ok"])
        self.assertEqual(first, second)
        self.assertEqual(1, first["checks"]["pending_email_verification_attempts"])
        rows = operation_task_store.list_tasks(page_size=20, q=str(account_id))["items"]
        registration = next(item for item in rows if item["task_type"] == "registration")
        wrong_entry = next(item for item in rows if item["task_type"] == "account_setup_retry")
        self.assertEqual("email_verification_pending", registration["target_status"])
        self.assertEqual("registration_resume", registration["next_actions"][0]["action"])
        self.assertEqual(job_id, registration["next_actions"][0]["source_job_id"])
        self.assertEqual("email_verification_pending", wrong_entry["target_status"])
        self.assertEqual("registration_resume", wrong_entry["next_actions"][0]["action"])

    def test_compatibility_resync_does_not_bump_task_updated_at_when_unchanged(self):
        account_id, job_id = self._seed_pending_registration()
        operation_task_store.reconcile_all()
        registration = operation_task_store.list_tasks(
            page_size=10, q=str(account_id), task_type="registration",
        )["items"][0]
        expected_updated_at = "2026-08-26T10:00:00+00:00"
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} SET updated_at=%s WHERE id=%s",
                (expected_updated_at, int(registration["id"])),
            )

        operation_task_store.sync_registration_job(job_id)

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT updated_at FROM {postgres_store.qualified('operation_tasks')} WHERE id=%s",
                (int(registration["id"]),),
            )
            self.assertEqual(expected_updated_at, cur.fetchone()[0].isoformat())

    def test_registration_projection_normalizes_legacy_naive_timestamps(self):
        account_id, _job_id = self._seed_pending_registration()

        operation_task_store.reconcile_all()

        registration = operation_task_store.list_tasks(
            page_size=10, q=str(account_id), task_type="registration",
        )["items"][0]
        self.assertEqual("2026-08-25T02:00:00+00:00", registration["created_at"])
        self.assertEqual("2026-08-25T02:02:00+00:00", registration["completed_at"])

    def _seed_running_debug_registration(self):
        job = db.create_job("icloud_hide")
        job_id = int(job["id"])
        db.update_job(job_id, status="running", email="debug-pause@example.test")
        db.update_job_progress(job_id, "submit_email", "running", "等待邮箱提交结果")
        task = operation_task_store.list_tasks(page_size=10, task_type="registration")["items"][0]
        return job_id, int(task["id"]), int(task["last_run_id"])

    def test_registration_debug_pause_projects_live_json_without_finishing_run(self):
        job_id, task_id, run_id = self._seed_running_debug_registration()
        registration_debug.patch_job(
            job_id, debug_state="paused",
            debug_paused_at="2026-10-13T18:00:30",
            debug_hold_until="2026-10-13T18:30:30+08:00",
            debug_pause_reason="private-debug-pause-reason",
        )
        pause = {
            "state": "paused", "paused_at": "2026-10-13T10:00:30+00:00",
            "hold_until": "2026-10-13T10:30:30+00:00",
        }
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        listed = client.get("/api/operations?task_type=registration").get_json()["items"][0]
        detail = client.get(f"/api/operations/{task_id}?include_events=0").get_json()["task"]
        selected = next(run for run in detail["runs"] if int(run["id"]) == run_id)
        progress = client.get(f"/api/operations/{task_id}/runs/{run_id}/progress").get_json()["progress"]
        for value in (listed, detail, selected):
            self.assertEqual(pause, value.get("debug_pause"))
            self.assertEqual("running", value["status"])
            self.assertIsNone(value["completed_at"])
        self.assertEqual(pause, progress["debug_pause"])
        authentication = next(step for step in progress["main_steps"] if step["id"] == "authenticate")
        self.assertEqual("running", authentication["state"])
        self.assertEqual("debug_paused", authentication["display_status"])
        self.assertIsNone(authentication["completed_at"])
        self.assertEqual(pause, authentication["debug_pause"])
        self.assertNotIn("private-debug-pause-reason", json.dumps([listed, detail, progress]))
        persisted = operation_task_store.get_run(run_id)
        self.assertEqual("running", persisted["status"])
        self.assertIsNone(persisted["completed_at"])
        self.assertNotIn("debug_pause", persisted)

    def test_registration_debug_pause_is_scoped_to_source_job_and_selected_run(self):
        job_id, task_id, first_run_id = self._seed_running_debug_registration()
        db.update_job_progress(job_id, "submit_email", "failed", "第一 Run 失败")
        db.update_job(job_id, status="failed", completed_at="2026-10-13T10:00:10Z")
        retry, created = db.create_retry_job(
            job_id, job_type="registration", email_source="icloud_hide",
            email="debug-pause@example.test",
        )
        self.assertTrue(created)
        retry_id = int(retry["id"])
        db.update_job(retry_id, status="running")
        db.update_job_progress(retry_id, "submit_email", "running", "第二 Run 等待结果")
        registration_debug.patch_job(
            retry_id, debug_state="paused", debug_paused_at="2026-10-13T10:01:00Z",
            debug_hold_until="2026-10-13T10:31:00Z",
        )
        detail = operation_task_store.get_task(task_id, include_events=False)
        first, second = detail["runs"]
        self.assertEqual(first_run_id, int(first["id"]))
        self.assertEqual("failed", first["status"])
        self.assertTrue(first["completed_at"])
        self.assertNotIn("debug_pause", first)
        self.assertEqual("running", second["status"])
        self.assertIsNone(second["completed_at"])
        self.assertEqual(second["debug_pause"], detail["debug_pause"])
        self.assertEqual(int(second["id"]), int(detail["last_run_id"]))
        old_progress = operation_task_store.get_run_progress(task_id, first_run_id)
        self.assertNotIn("debug_pause", old_progress)
        self.assertNotIn("debug_paused", [step["display_status"] for step in old_progress["main_steps"]])
        current_progress = operation_task_store.get_run_progress(task_id, int(second["id"]))
        self.assertEqual(second["debug_pause"], current_progress["debug_pause"])
        listed = operation_task_store.list_tasks(page_size=10, task_type="registration")["items"][0]
        self.assertEqual(second["debug_pause"], listed["debug_pause"])

    def test_registration_debug_pause_sanitizes_time_and_clears_on_release_or_terminal(self):
        job_id, task_id, run_id = self._seed_running_debug_registration()
        registration_debug.patch_job(
            job_id, debug_state="paused", debug_paused_at="private-invalid-time",
            debug_hold_until={"private": "invalid-time"},
        )
        for value in (
            operation_task_store.get_task(task_id, include_events=False),
            operation_task_store.get_run_progress(task_id, run_id),
        ):
            self.assertEqual({"state": "paused", "paused_at": None, "hold_until": None}, value["debug_pause"])
            self.assertNotIn("private-invalid-time", json.dumps(value))
        registration_debug.patch_job(job_id, debug_state="released")
        for value in (
            operation_task_store.list_tasks(page_size=10)["items"][0],
            operation_task_store.get_task(task_id, include_events=False),
            operation_task_store.get_run_progress(task_id, run_id),
        ):
            self.assertNotIn("debug_pause", value)
        # 即使旧调试字段未清理，终态也必须保留其成功/失败事实。
        registration_debug.patch_job(job_id, debug_state="paused")
        for status in ("success", "failed"):
            with self.subTest(status=status):
                db.update_job(job_id, status=status, completed_at="2026-10-13T10:02:00Z")
                detail = operation_task_store.get_task(task_id, include_events=False)
                selected = detail["runs"][0]
                for value in (operation_task_store.list_tasks(page_size=10)["items"][0], detail, selected):
                    self.assertEqual(status, value["status"])
                    self.assertTrue(value["completed_at"])
                    self.assertNotIn("debug_pause", value)
                self.assertNotIn("debug_pause", operation_task_store.get_run_progress(task_id, run_id))

    def test_legacy_registration_read_model_normalizes_run_start_steps_and_events(self):
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "legacy-time@example.test",
            "access_token": "",
            "codex_status": "failed",
            "created_at": "2026-09-08T10:05:00",
            "updated_at": "2026-09-08T10:11:15",
            "extra_json": json.dumps({"registration_checkpoint": "failed"}),
        })
        job_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "legacy-time-job",
            "email": "legacy-time@example.test",
            "status": "failed",
            "job_type": "registration",
            "account_id": account_id,
            "created_at": "2026-09-08T10:05:00",
            "started_at": "2026-09-08T10:05:46",
            "updated_at": "2026-09-08T10:11:15",
            "completed_at": "2026-09-08T10:11:15",
            "progress_stage": "complete",
            "progress_steps": {
                "network": {
                    "state": "success",
                    "started_at": "2026-09-08T10:05:46",
                    "completed_at": "2026-09-08T10:05:53",
                },
                "profile": {
                    "state": "failed",
                    "started_at": "2026-09-08T10:08:00",
                    "completed_at": "2026-09-08T10:08:12",
                },
            },
            "error_message": "历史任务失败",
        })
        operation_task_store.reconcile_all()
        task = operation_task_store.list_tasks(page_size=10, task_type="registration")["items"][0]
        task_id = int(task["id"])
        run_id = int(task["last_run_id"])

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET started_at=%s WHERE id=%s",
                ("2026-09-08T10:05:46+00:00", run_id),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_events')} "
                "SET created_at=%s WHERE run_id=%s AND source_system='registration_progress'",
                ("2026-09-08T10:08:12+00:00", run_id),
            )

        detail = operation_task_store.get_task(task_id)
        run = detail["runs"][0]
        self.assertEqual("2026-09-08T02:05:46+00:00", run["started_at"])
        self.assertEqual(
            "2026-09-08T02:05:46+00:00",
            run["progress_steps"]["network"]["started_at"],
        )
        progress_events = [
            event for event in detail["events"]
            if event["source_system"] == "registration_progress"
        ]
        self.assertTrue(progress_events)
        self.assertTrue(all(
            str(event["created_at"]).startswith("2026-09-08T02:")
            for event in progress_events
        ))
        self.assertEqual(
            {"network": "2026-09-08T02:05:53+00:00", "profile": "2026-09-08T02:08:12+00:00"},
            {event["stage"]: event["created_at"] for event in progress_events},
        )

        page = operation_task_store.list_task_events(task_id, run_id=run_id, limit=100)
        ids = [int(event["id"]) for event in page["items"]]
        self.assertEqual(sorted(ids), ids)
        self.assertEqual(max(ids), int(page["next_after_id"]))
        self.assertEqual(
            {event["id"]: event["created_at"] for event in progress_events},
            {event["id"]: event["created_at"] for event in page["items"]},
        )
        cursor, seen = 0, []
        while True:
            increment = operation_task_store.list_task_events(
                task_id, run_id=run_id, after_id=cursor, limit=1,
            )
            seen.extend(event["id"] for event in increment["items"])
            cursor = increment["next_after_id"]
            if not increment["has_more"]:
                break
        self.assertEqual(ids, seen)
        with patch.object(operation, "build_progress_snapshot", wraps=operation.build_progress_snapshot) as build:
            operation_task_store.get_run_progress(task_id, run_id)
        self.assertEqual("2026-09-08T02:05:46+00:00", build.call_args.args[3]["started_at"])
        self.assertEqual(
            [event["created_at"] for event in progress_events],
            [event["created_at"] for event in build.call_args.args[4]],
        )
        # 读取只修正投影，不回写历史物理行或原始阶段快照。
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT started_at FROM {postgres_store.qualified('operation_runs')} WHERE id=%s",
                (run_id,),
            )
            self.assertEqual("2026-09-08T10:05:46+00:00", cur.fetchone()[0].isoformat())
            cur.execute(
                f"SELECT created_at FROM {postgres_store.qualified('operation_events')} WHERE run_id=%s",
                (run_id,),
            )
            self.assertTrue(all(row[0].isoformat() == "2026-09-08T10:08:12+00:00" for row in cur.fetchall()))
        self.assertEqual("2026-09-08T10:05:46", record_store.get_row(record_store.JOBS, job_id)["started_at"])

    def test_compatibility_time_read_preserves_aware_missing_and_native_values(self):
        for source, detail, expected in (
            ("registration_progress", {"completed_at": "2026-10-08T08:48:32Z"}, "2026-10-08T08:48:32+00:00"),
            ("registration_progress", {"completed_at": "2026-10-08T08:48:32+09:00"}, "2026-10-07T23:48:32+00:00"),
            # 旧快照没有可靠事件时间时，数据库默认时间也不能冒充实际发生时间。
            ("registration_progress", {}, None),
            ("registration_progress", {"completed_at": "invalid"}, None),
            ("registration_events", {"completed_at": "2026-10-08T08:48:32+09:00"}, "2026-10-08T08:48:32+00:00"),
            ("native_operations", {"completed_at": "2026-10-08T08:48:32+09:00"}, "2026-10-08T08:48:32+00:00"),
        ):
            with self.subTest(source=source, detail=detail):
                event = operation._normalize_compatibility_event({
                    "source_system": source, "created_at": "2026-10-08T08:48:32+00:00", "detail": detail,
                })
                self.assertEqual(expected, event["created_at"])
        run = operation._normalize_compatibility_run({
            "source_system": "registration_jobs", "started_at": "2026-10-08T08:48:32+00:00",
        })
        self.assertEqual("2026-10-08T08:48:32+00:00", run["started_at"])

    def test_legacy_account_task_read_model_normalizes_started_at_from_source(self):
        batch_id = account_task_store.create_batch(
            action_type="account_setup_retry", trigger="test", total_count=1,
        )
        legacy_task_id = account_task_store.create_task(
            task_type="account_setup_retry", account_id=7001,
            email="legacy-account-time@example.test", trigger="test", batch_id=batch_id,
        )
        account_task_store.start_task(legacy_task_id)
        account_task_store.finish_task(legacy_task_id, status="failed", message="历史任务失败")
        operation_task_store.reconcile_all()
        task = operation_task_store.list_tasks(page_size=10, task_type="account_setup_retry")["items"][0]
        task_id = int(task["id"])
        run_id = int(task["last_run_id"])

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('account_action_tasks')} "
                "SET started_at=%s WHERE id=%s",
                ("2026-09-08T10:05:46", legacy_task_id),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET started_at=%s WHERE id=%s",
                ("2026-09-08T10:05:46+00:00", run_id),
            )

        detail = operation_task_store.get_task(task_id, include_events=False)
        self.assertEqual("2026-09-08T02:05:46+00:00", detail["runs"][0]["started_at"])

    def test_task_list_sorts_by_current_run_creation_time(self):
        def seed_registration(email, created_at):
            account_id = record_store.insert_row(record_store.ACCOUNTS, {
                "email": email,
                "access_token": "",
                "codex_status": "success",
                "created_at": created_at,
                "updated_at": created_at,
                "extra_json": json.dumps({"registration_checkpoint": "registered"}),
            })
            job_id = record_store.insert_row(record_store.JOBS, {
                "job_uuid": f"job-{email}",
                "email": email,
                "status": "success",
                "job_type": "registration",
                "account_id": account_id,
                "created_at": created_at,
                "updated_at": created_at,
                "completed_at": created_at,
                "progress_stage": "complete",
                "progress_steps": {},
            })
            return account_id, job_id

        first_account_id, first_job_id = seed_registration(
            "first@example.com", "2026-08-25T10:00:00",
        )
        second_account_id, _second_job_id = seed_registration(
            "second@example.com", "2026-08-25T10:01:00",
        )
        operation_task_store.reconcile_all()

        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_jobs')} SET created_at=%s WHERE id=%s",
                ("2026-08-25T11:00:00", int(first_job_id)),
            )

        listed = operation_task_store.list_tasks(page_size=10, task_type="registration")["items"]
        self.assertEqual(
            [int(first_account_id), int(second_account_id)],
            [int(item["account_id"]) for item in listed[:2]],
        )
        self.assertEqual("2026-08-25T03:00:00+00:00", listed[0]["created_at"])

    def test_task_list_sorts_by_creation_time_regardless_of_status(self):
        historical = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=101, email="historical@example.com", trigger="manual",
        )
        operation_task_store.finish_run(
            historical["run"]["id"], status="success", message="历史任务完成",
        )
        recent_terminal = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=102, email="recent@example.com", trigger="manual",
        )
        operation_task_store.finish_run(
            recent_terminal["run"]["id"], status="success", message="最近任务完成",
        )
        active = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=103, email="active@example.com", trigger="manual",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            task_table = postgres_store.qualified("operation_tasks")
            cur.execute(
                f"UPDATE {task_table} SET created_at=%s, updated_at=%s WHERE id=%s",
                ("2026-08-17T14:38:43Z", "2026-09-03T18:00:00Z", int(historical["id"])),
            )
            cur.execute(
                f"UPDATE {task_table} SET created_at=%s, updated_at=%s WHERE id=%s",
                ("2026-09-03T09:00:00Z", "2026-09-03T09:00:00Z", int(recent_terminal["id"])),
            )
            cur.execute(
                f"UPDATE {task_table} SET created_at=%s, updated_at=%s WHERE id=%s",
                ("2026-09-03T08:00:00Z", "2026-09-03T08:00:00Z", int(active["id"])),
            )

        listed = operation_task_store.list_tasks(page_size=10, task_type="live_check")["items"]

        self.assertEqual(
            [int(recent_terminal["id"]), int(active["id"]), int(historical["id"])],
            [int(item["id"]) for item in listed[:3]],
        )

    def test_new_session_advances_checkpoint_and_unified_target(self):
        account_id, _job_id = self._seed_pending_registration()
        operation_task_store.reconcile_all()

        self.assertTrue(db.update_account_session(
            "pending@example.com", "fresh-session-token", expires_at="2026-09-01T00:00:00Z",
        ))

        account = db.get_account(account_id)
        extra = json.loads(account["extra_json"])
        self.assertEqual("fresh-session-token", account["access_token"])
        self.assertEqual("registered", extra["registration_checkpoint"])
        rows = operation_task_store.list_tasks(page_size=20, q=str(account_id))["items"]
        registration = next(item for item in rows if item["task_type"] == "registration")
        self.assertEqual("account_available", registration["target_status"])
        self.assertNotEqual("registration_resume", (registration["next_actions"] or [{}])[0].get("action"))

    def test_unified_api_returns_runs_events_and_server_actions(self):
        _account_id, _job_id = self._seed_pending_registration()
        operation_task_store.reconcile_all()
        task = operation_task_store.list_tasks(page_size=10, task_type="registration")["items"][0]

        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        response = client.get("/api/operations?page_size=10")
        detail = client.get(f"/api/operations/{task['id']}")

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.get_json()["total"])
        self.assertEqual(200, detail.status_code)
        payload = detail.get_json()["task"]
        self.assertEqual("registration", payload["task_type"])
        self.assertEqual(1, len(payload["runs"]))
        self.assertTrue(payload["events"])
        self.assertTrue(payload["flow"])
        self.assertNotIn("never-expose-this", json.dumps(payload, ensure_ascii=False))

    def test_run_progress_api_is_scoped_to_selected_run_and_independent_of_timeline_page(self):
        task = operation_task_store.create_runtime_task(
            task_type="password_setup",
            account_id=701,
            email="progress-run@example.com",
            trigger="test",
        )
        first_run_id = int(task["run"]["id"])
        operation_task_store.append_runtime_event(
            first_run_id, stage="network", state="success", message="第一 Run 网络就绪",
        )
        operation_task_store.finish_run(first_run_id, status="failed", message="第一 Run 失败")

        second = operation_task_store.retry_runtime_task(int(task["id"]), trigger="manual_retry")
        second_run_id = int(second["id"])
        for stage, state in (
            ("network", "success"),
            ("browser", "running"),
            ("login", "running"),
            ("email_otp", "running"),
            ("login_password", "running"),
        ):
            operation_task_store.append_runtime_event(
                second_run_id, stage=stage, state=state, message=f"第二 Run {stage}",
            )

        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        progress = client.get(
            f"/api/operations/{task['id']}/runs/{second_run_id}/progress",
        )
        detail = client.get(f"/api/operations/{task['id']}?include_events=0")
        timeline = client.get(
            f"/api/operations/{task['id']}/runs/{second_run_id}/events?limit=1",
        )

        self.assertEqual(200, progress.status_code)
        snapshot = progress.get_json()["progress"]
        self.assertEqual(second_run_id, snapshot["run_id"])
        self.assertEqual(
            ["network", "browser", "authenticate", "set_password", "result"],
            [item["id"] for item in snapshot["main_steps"]],
        )
        self.assertEqual("set_password", snapshot["current"]["step_id"])
        self.assertEqual([], detail.get_json()["task"]["events"])
        self.assertEqual(200, timeline.status_code)
        self.assertEqual(1, len(timeline.get_json()["items"]))

        other = operation_task_store.create_runtime_task(
            task_type="password_setup",
            account_id=702,
            email="other-progress-run@example.com",
            trigger="test",
        )
        denied = client.get(
            f"/api/operations/{other['id']}/runs/{second_run_id}/progress",
        )
        missing = client.get(
            f"/api/operations/{task['id']}/runs/999999999/progress",
        )
        self.assertEqual(404, denied.status_code)
        self.assertEqual(404, missing.status_code)

    def test_unified_task_list_supports_column_filters_and_facets(self):
        failed = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=101, email="column-filter@example.com", trigger="manual_bulk",
        )
        operation_task_store.finish_run(
            failed["run"]["id"], status="failed", message="OTP timeout", error="OTP timeout",
        )
        success = operation_task_store.create_runtime_task(
            task_type="plan_check", account_id=202, email="other@example.com", trigger="scheduled",
        )
        operation_task_store.finish_run(
            success["run"]["id"], status="success", message="套餐查询完成", result_summary={"current_plan_type": "free"},
        )

        result = operation_task_store.list_tasks(
            page_size=20,
            task_id=str(failed["id"]),
            target="101",
            target_status="failed",
            run_count="1",
            stage="complete",
            result="OTP",
        )
        self.assertEqual(1, result["total"])
        self.assertEqual(failed["id"], result["items"][0]["id"])
        self.assertEqual({"task_type", "status", "target_status", "stage", "run_count"}, set(result["facets"]))
        self.assertIn({"value": "live_check", "count": 1}, result["facets"]["task_type"])

    def test_account_step_states_are_projected_without_treating_running_as_success(self):
        legacy_task_id = account_task_store.create_task(
            task_type="account_setup_retry",
            account_id=None,
            email="step-state@example.com",
            trigger="manual",
        )
        account_task_store.start_task(legacy_task_id, message="开始补跑")
        account_task_store.append_event(
            legacy_task_id, stage="network", message="线路已分配", state="success",
        )
        account_task_store.append_event(
            legacy_task_id, stage="browser", message="正在重新登录", state="running",
        )
        account_task_store.append_event(
            legacy_task_id, stage="plan_check", message="已有套餐记录，跳过", state="skipped",
        )

        summary = operation_task_store.list_tasks(page_size=10, q="step-state@example.com")["items"][0]
        detail = operation_task_store.get_task(summary["id"])
        projected = {
            event["stage"]: event["event_type"]
            for event in detail["events"]
            if event["stage"] in {"network", "browser", "plan_check"}
        }
        self.assertEqual("stage.success", projected["network"])
        self.assertEqual("stage.running", projected["browser"])
        self.assertEqual("stage.skipped", projected["plan_check"])
        self.assertEqual("browser", detail["current_stage"])
        self.assertTrue(any(event["event_type"] == "run.running" for event in detail["events"]))
        self.assertTrue(all(event["run_id"] == detail["last_run_id"] for event in detail["events"]))

        with self.assertRaisesRegex(ValueError, "步骤状态"):
            account_task_store.append_event(
                legacy_task_id, stage="twofa", message="非法状态", state="done",
            )

    def test_incremental_event_and_run_log_api_use_explicit_contract(self):
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=909, email="runtime-log@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        note = operation_task_store.append_runtime_event(
            run_id,
            stage="preflight",
            message="预检说明，不改变阶段状态",
        )
        self.assertEqual("note.info", note["event_type"])
        self.assertEqual("queued", operation_task_store.get_task(task["id"], include_events=False)["current_stage"])
        operation_task_store.append_runtime_event(
            run_id,
            stage="network",
            state="success",
            message="网络线路已就绪",
            detail={"access_token": "never-store-this", "network_route": "proxy"},
        )

        app = create_app(auth_code="test-auth")
        client = app.test_client()
        client.environ_base["HTTP_X_AUTH_CODE"] = "test-auth"
        detail = client.get(f"/api/operations/{task['id']}?include_events=0")
        events = client.get(f"/api/operations/{task['id']}/runs/{run_id}/events?limit=20")
        logs = client.get(f"/api/operations/{task['id']}/runs/{run_id}/logs?limit=20")

        self.assertEqual([], detail.get_json()["task"]["events"])
        event_items = events.get_json()["items"]
        self.assertEqual("stage.success", event_items[-1]["event_type"])
        self.assertEqual("success", event_items[-1]["detail"]["step_state"])
        self.assertTrue(event_items[-1]["has_detail"])
        self.assertNotIn("never-store-this", json.dumps(event_items))
        log_payload = logs.get_json()
        self.assertTrue(log_payload["available"])
        self.assertTrue(any(item.get("event_type") == "stage.success" for item in log_payload["items"]))
        self.assertNotIn("never-store-this", json.dumps(log_payload))

    def _seed_runtime_account(self, email="runtime@example.com"):
        return record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "registered-token",
            "codex_status": "failed",
            "created_at": "2026-08-25T10:00:00",
            "updated_at": "2026-08-25T10:00:00",
        })

    def test_runtime_prevents_duplicate_active_account_and_queued_cancel_is_terminal(self):
        account_id = self._seed_runtime_account()
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="runtime@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        with self.assertRaises(Exception):
            operation_task_store.create_runtime_task(
                task_type="codex_retry", account_id=account_id,
                email="runtime@example.com", trigger="duplicate",
            )

        cancelled = operation_task_store.request_run_cancel(run_id, reason="test cancel")
        self.assertEqual("cancelled", cancelled["status"])
        self.assertTrue(operation_task_store.is_run_cancel_requested(run_id, task["run"]["cancellation_token"]))
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("cancelled", detail["status"])
        self.assertEqual("complete", detail["current_stage"])
        self.assertEqual("run.cancel_requested", detail["events"][-1]["event_type"])

        replacement = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="runtime@example.com", trigger="after_cancel",
        )
        self.assertNotEqual(run_id, replacement["run"]["id"])

    def test_retry_creates_new_attempt_under_same_logical_task(self):
        account_id = self._seed_runtime_account("attempt@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="attempt@example.com", trigger="test",
        )
        first_run = int(task["run"]["id"])
        operation_task_store.finish_run(
            first_run, status="failed", error="temporary failure",
            result_summary={"ok": False},
        )
        second = operation_task_store.retry_runtime_task(int(task["id"]), trigger="manual_retry")
        self.assertEqual(2, second["run_no"])
        self.assertEqual(int(task["id"]), second["task_id"])
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual([1, 2], [run["run_no"] for run in detail["runs"]])
        self.assertEqual("queued", detail["status"])

    def test_retry_reopens_terminal_batch_and_clears_completed_time(self):
        account_id = self._seed_runtime_account("retry-batch@example.com")
        batch = operation_task_store.create_runtime_batch(
            batch_type="codex_retry", title="retry batch", requested_count=1, trigger="test",
        )
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="retry-batch@example.com", trigger="test", batch_id=int(batch["id"]),
        )
        operation_task_store.finish_run(int(task["run"]["id"]), status="failed", error="temporary failure")
        terminal = next(item for item in operation_task_store.list_batches() if item["id"] == batch["id"])
        self.assertEqual("failed", terminal["status"])
        self.assertIsNotNone(terminal["completed_at"])

        operation_task_store.retry_runtime_task(int(task["id"]), trigger="manual_retry")

        reopened = next(item for item in operation_task_store.list_batches() if item["id"] == batch["id"])
        self.assertEqual("queued", reopened["status"])
        self.assertEqual(1, reopened["queued_count"])
        self.assertIsNone(reopened["completed_at"])

    def test_active_retry_wins_over_stale_terminal_task_projection(self):
        account_id = self._seed_runtime_account("active-attempt@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="active-attempt@example.com", trigger="test",
        )
        first_run = int(task["run"]["id"])
        operation_task_store.finish_run(first_run, status="failed", error="old failure")
        second_run = operation_task_store.retry_runtime_task(int(task["id"]), trigger="manual_retry")
        second_run_id = int(second_run["id"])

        # Reproduce an older terminal write landing after the retry row was
        # created.  The active run is the authoritative read state.
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified("operation_tasks")}
                SET status='failed', current_stage='complete', completed_at='2026-08-25T10:02:00Z'
                WHERE id=%s
                """,
                (int(task["id"]),),
            )

        listed = operation_task_store.list_tasks(page_size=10, q="active-attempt@example.com")
        current = listed["items"][0]
        self.assertEqual("queued", current["status"])
        self.assertEqual("queued", current["current_stage"])
        self.assertEqual(second_run_id, int(current["last_run_id"]))
        self.assertIsNone(current["completed_at"])
        self.assertEqual(1, operation_task_store.list_tasks(
            page_size=10, q="active-attempt@example.com", status="queued",
        )["total"])
        self.assertEqual(1, operation_task_store.list_tasks(
            page_size=10, q="active-attempt@example.com", stage="queued",
        )["total"])
        self.assertEqual(0, operation_task_store.list_tasks(
            page_size=10, q="active-attempt@example.com", status="failed",
        )["total"])

        detail = operation_task_store.get_task(int(task["id"]), include_events=False)
        self.assertEqual("queued", detail["status"])
        self.assertEqual(second_run_id, int(detail["last_run_id"]))

        operation_task_store.claim_run(second_run_id, execution_id="active-worker", worker_pid=123)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified("operation_tasks")}
                SET status='partial_success', current_stage='complete', completed_at='2026-08-25T10:03:00Z'
                WHERE id=%s
                """,
                (int(task["id"]),),
            )
        running = operation_task_store.list_tasks(page_size=10, q="active-attempt@example.com")["items"][0]
        self.assertEqual("running", running["status"])
        self.assertEqual("preflight", running["current_stage"])
        self.assertIsNone(running["completed_at"])

    def test_compatibility_source_status_overrides_stale_operation_projection(self):
        legacy_task_id = account_task_store.create_task(
            task_type="deactivation_mail",
            account_id=None,
            email="compatibility-state@example.com",
            trigger="manual",
        )
        account_task_store.start_task(legacy_task_id, message="开始扫描")
        account_task_store.finish_task(
            legacy_task_id, status="success", message="扫描完成", result_summary={"detected": False},
        )
        projected = operation_task_store.list_tasks(
            page_size=10, q="compatibility-state@example.com",
        )["items"][0]
        run_id = int(projected["last_run_id"])

        # Reproduce a compatibility callback that left the unified projection
        # behind after the source task had already reached its terminal state.
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('operation_runs')}
                SET status='running', progress_stage='queued', completed_at=NULL,
                    error_message='stale projection'
                WHERE id=%s
                """,
                (run_id,),
            )

            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('operation_tasks')}
                SET status='running', current_stage='queued', completed_at=NULL
                WHERE id=%s
                """,
                (int(projected["id"]),),
            )

        listed = operation_task_store.list_tasks(
            page_size=10, q="compatibility-state@example.com",
        )["items"][0]
        self.assertEqual("success", listed["status"])
        self.assertEqual("complete", listed["current_stage"])
        self.assertTrue(listed["completed_at"])
        self.assertEqual(1, operation_task_store.list_tasks(
            page_size=10, q="compatibility-state@example.com", status="success",
        )["total"])
        self.assertEqual(0, operation_task_store.list_tasks(
            page_size=10, q="compatibility-state@example.com", status="running",
        )["total"])

        detail = operation_task_store.get_task(int(projected["id"]), include_events=False)
        self.assertEqual("success", detail["status"])
        self.assertEqual("complete", detail["current_stage"])
        self.assertEqual("success", detail["runs"][0]["status"])

        self.assertEqual(1, operation_task_store.repair_stale_compatibility_projections())
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_runs')} WHERE id=%s",
                (run_id,),
            )
            self.assertEqual("success", cur.fetchone()[0])

    def test_finish_task_persists_partial_success_as_terminal_status(self):
        task_id = account_task_store.create_task(
            task_type="account_completion",
            account_id=None,
            email="partial@example.com",
            trigger="manual",
        )
        account_task_store.start_task(task_id, message="开始补全")
        account_task_store.finish_task(
            task_id,
            status="partial_success",
            message="密码/2FA 已完成，套餐查询待重试",
            result_summary={"pending_steps": ["plan_check"]},
        )

        stored = account_task_store.get_task(task_id)
        self.assertEqual("partial_success", stored["status"])
        self.assertEqual("run.partial_success", stored["events"][-1]["event_type"])

    def test_batch_accounts_for_items_rejected_before_run_creation(self):
        account_id = self._seed_runtime_account("batch@example.com")
        batch = operation_task_store.create_runtime_batch(
            batch_type="codex_retry", title="batch", requested_count=2, trigger="test",
        )
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="batch@example.com", trigger="test",
            batch_id=int(batch["id"]), batch_ordinal=1,
        )
        operation_task_store.set_runtime_batch_skipped(
            int(batch["id"]), [{"id": 999, "reason": "账号不存在"}],
        )
        operation_task_store.finish_run(int(task["run"]["id"]), status="success")
        refreshed = next(item for item in operation_task_store.list_batches() if item["id"] == batch["id"])
        self.assertEqual(2, refreshed["requested_count"])
        self.assertEqual(1, refreshed["success_count"])
        self.assertEqual(1, refreshed["skipped_count"])
        self.assertEqual("partial_success", refreshed["status"])

    def test_projection_write_retries_a_deadlock_with_bounded_backoff(self):
        calls = []

        def write_once():
            calls.append(len(calls) + 1)
            if len(calls) == 1:
                raise DeadlockDetected("deadlock")
            return "written"

        with patch.object(operation.time, "sleep") as sleep:
            result = operation._run_projection_write_with_retry(write_once, operation_name="test")

        self.assertEqual("written", result)
        self.assertEqual([1, 2], calls)
        sleep.assert_called_once()

    def test_batch_counts_one_effective_root_after_child_retry(self):
        batch = operation_task_store.create_runtime_batch(
            batch_type="registration", title="registration", requested_count=1, trigger="test",
        )
        parent = operation_task_store.create_runtime_task(
            task_type="registration", account_id=None, email="root@example.com",
            trigger="test", batch_id=int(batch["id"]), batch_ordinal=1,
        )
        operation_task_store.finish_run(
            int(parent["run"]["id"]), status="partial_success", message="首次线路失败",
        )
        child = operation_task_store.create_runtime_task(
            task_type="registration_resume", account_id=None, email="root@example.com",
            trigger="manual_retry", batch_id=int(batch["id"]),
            parent_task_id=int(parent["id"]),
        )
        operation_task_store.finish_run(
            int(child["run"]["id"]), status="success", message="续跑成功",
        )

        refreshed = next(item for item in operation_task_store.list_batches() if item["id"] == batch["id"])
        self.assertEqual(1, refreshed["requested_count"])
        self.assertEqual(1, refreshed["success_count"])
        self.assertEqual(0, refreshed["partial_count"])
        self.assertEqual(0, refreshed["failed_count"])

    def test_child_terminal_state_advances_waiting_parent(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="parent@example.com",
            trigger="test", resource_family="completion_coordinator",
        )
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=None, email="parent@example.com",
            trigger="test", parent_task_id=int(parent["id"]), resource_family="openai_interactive",
        )

        waiting = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("waiting", waiting["status"])
        self.assertEqual("waiting", waiting["runs"][0]["status"])
        self.assertIsNone(operation_task_store.active_run_for_account(1))

        operation_task_store.finish_run(int(child["run"]["id"]), status="success")
        completed = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("success", completed["status"])
        self.assertEqual("success", completed["runs"][0]["status"])
        self.assertEqual("task.children_reconciled", completed["events"][-1]["event_type"])

    def test_deactivated_native_child_marks_parent_deactivated_without_retry(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="parent-deactivated@example.test",
            trigger="test", resource_family="completion_coordinator",
        )
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=None, email="parent-deactivated@example.test",
            trigger="test", parent_task_id=int(parent["id"]), resource_family="openai_interactive",
        )

        operation_task_store.finish_run(
            int(child["run"]["id"]),
            status="deactivated",
            result_summary={"status": "deactivated"},
        )

        completed = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("deactivated", completed["status"])
        self.assertEqual("account_deactivated", completed["target_status"])
        self.assertEqual([], completed["next_actions"])
        self.assertEqual("deactivated", completed["runs"][0]["status"])

    def test_deactivated_dependency_callback_marks_parent_without_retry(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="dependency-deactivated@example.test",
            trigger="test", resource_family="completion_coordinator",
        )

        operation_task_store.apply_task_dependency_result(
            parent_source_system="webui_runtime",
            parent_source_id=str(parent["id"]),
            child_status="deactivated",
            child_result={"status": "deactivated", "reason": "account_deactivated"},
        )

        completed = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("deactivated", completed["status"])
        self.assertEqual("account_deactivated", completed["target_status"])
        self.assertEqual([], completed["next_actions"])
        self.assertEqual("deactivated", completed["runs"][0]["status"])

    def test_retrying_terminal_child_returns_parent_to_waiting(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="retry-child-parent@example.test",
            trigger="test", resource_family="completion_coordinator",
        )
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=None, email="retry-child-parent@example.test",
            trigger="test", parent_task_id=int(parent["id"]), resource_family="openai_interactive",
        )
        operation_task_store.finish_run(
            int(child["run"]["id"]), status="failed", error="temporary child failure",
        )
        terminal_parent = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("partial_success", terminal_parent["status"])

        operation_task_store.retry_runtime_task(int(child["id"]), trigger="manual_retry")

        waiting_parent = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("waiting", waiting_parent["status"])
        self.assertEqual([], waiting_parent["next_actions"])
        self.assertEqual(["partial_success", "waiting"], [run["status"] for run in waiting_parent["runs"]])
        self.assertEqual(2, len(waiting_parent["runs"]))
        self.assertEqual("waiting", waiting_parent["runs"][-1]["status"])
        with self.assertRaisesRegex(ValueError, "任务仍在执行"):
            operation_task_store.retry_runtime_task(int(parent["id"]), trigger="manual_retry")

    def test_waiting_parent_does_not_compete_with_same_account_child_retry(self):
        account_id = self._seed_runtime_account("same-family-parent@example.test")
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=account_id,
            email="same-family-parent@example.test", trigger="test",
            resource_family="openai_interactive",
        )
        operation_task_store.finish_run(int(parent["run"]["id"]), status="partial_success")
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=account_id,
            email="same-family-parent@example.test", trigger="test",
            parent_task_id=int(parent["id"]), resource_family="openai_interactive",
        )
        self.assertEqual("waiting", operation_task_store.get_task(int(parent["id"]))["status"])
        operation_task_store.finish_run(int(child["run"]["id"]), status="failed", error="temporary failure")

        retried = operation_task_store.retry_runtime_task(int(child["id"]), trigger="manual_retry")

        self.assertEqual("queued", retried["status"])
        parent_detail = operation_task_store.get_task(int(parent["id"]))
        self.assertEqual("waiting", parent_detail["status"])
        self.assertEqual("waiting", parent_detail["runs"][-1]["status"])

    def test_restart_reconciles_interrupted_native_child_to_parent(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=None, email="restart-parent@example.com",
            trigger="test", resource_family="completion_coordinator",
        )
        child = operation_task_store.create_runtime_task(
            task_type="token_refresh", account_id=None, email="restart-parent@example.com",
            trigger="test", parent_task_id=int(parent["id"]), resource_family="openai_interactive",
        )
        child_run_id = int(child["run"]["id"])
        operation_task_store.claim_run(child_run_id, execution_id="crashed-worker", worker_pid=987)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (child_run_id,),
            )

        self.assertEqual(1, operation_task_store.recover_interrupted_runtime_runs())
        recovered_parent = operation_task_store.get_task(int(parent["id"]))
        recovered_child = operation_task_store.get_task(int(child["id"]))
        self.assertEqual("partial_success", recovered_parent["status"])
        self.assertEqual("interrupted", recovered_child["status"])

    def test_native_submission_key_is_idempotent(self):
        first = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=None, email="idempotent@example.com",
            trigger="test", idempotency_key="request-123",
        )
        second = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=None, email="idempotent@example.com",
            trigger="retry-of-http-request", idempotency_key="request-123",
        )
        self.assertEqual(int(first["id"]), int(second["id"]))
        self.assertEqual(int(first["run"]["id"]), int(second["run"]["id"]))
        self.assertTrue(second["idempotent"])
        self.assertEqual(1, len(operation_task_store.get_task(int(first["id"]))["runs"]))

    def test_dependency_drain_has_one_claim_owner_and_recovers_after_restart(self):
        parent_id = account_task_store.create_task(
            task_type="account_completion",
            account_id=None,
            email="dependency-parent@example.com",
            trigger="test",
        )
        child_id = account_task_store.create_task(
            task_type="token_refresh",
            account_id=None,
            email="dependency-parent@example.com",
            trigger="test",
        )
        dependency = operation_task_store.register_task_dependency(
            parent_source_system="account_action_tasks",
            parent_source_id=str(parent_id),
            child_source_system="account_action_tasks",
            child_source_id=str(child_id),
            dependency_type="account_completion",
            payload={"remaining_steps": ["plan_check"]},
        )
        operation_task_store.mark_task_dependency_ready(
            child_source_system="account_action_tasks",
            child_source_id=str(child_id),
            child_status="success",
            child_result={"ok": True},
        )

        # Startup drain is notification-only. It must not claim a row before
        # the persistent scanner gets ownership.
        with patch.object(operation, "claim_task_dependency", side_effect=AssertionError("drain claimed")):
            self.assertEqual(
                1,
                task_gateway.drain_ready_dependencies(limit=10, initialized=True),
            )

        handled: list[dict] = []
        task_gateway.set_dependency_ready_handler(lambda row: handled.append(row))
        try:
            self.assertEqual(1, task_gateway._dependency_tick())
            self.assertEqual(1, len(handled))
            self.assertEqual("running", handled[0]["status"])
            # A second tick sees no ready row and cannot claim the same child.
            self.assertEqual(0, task_gateway._dependency_tick())
        finally:
            task_gateway.set_dependency_ready_handler(None)
            operation_task_store.complete_task_dependency(int(dependency["id"]), success=True)

        stale = operation_task_store.register_task_dependency(
            parent_source_system="account_action_tasks",
            parent_source_id=str(parent_id),
            child_source_system="account_action_tasks",
            child_source_id=str(child_id + 1),
            dependency_type="account_completion",
            payload={},
        )
        operation_task_store.mark_task_dependency_ready(
            child_source_system="account_action_tasks",
            child_source_id=str(child_id + 1),
            child_status="success",
        )
        first_claim = operation_task_store.claim_task_dependency(int(stale["id"]))
        self.assertEqual(1, first_claim["attempts"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_task_dependencies')} "
                "SET updated_at=now() - interval '1 hour' WHERE id=%s",
                (int(stale["id"]),),
            )
        self.assertEqual(1, operation_task_store.recover_stale_task_dependencies())
        ready_again = operation_task_store.list_ready_task_dependencies()
        self.assertEqual(int(stale["id"]), int(ready_again[0]["id"]))
        second_claim = operation_task_store.claim_task_dependency(int(stale["id"]))
        self.assertEqual(2, second_claim["attempts"])
        operation_task_store.complete_task_dependency(int(stale["id"]), success=True)

    def test_running_cancel_uses_db_token_and_resource_ledger(self):
        account_id = self._seed_runtime_account("cancel@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="cancel@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        claimed = operation_task_store.claim_run(run_id, execution_id="worker-1", worker_pid=123)
        self.assertEqual("running", claimed["status"])
        lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        self.assertTrue(lease)
        resource = operation_task_store.register_resource(
            run_id, resource_type="sms_activation", provider="test", external_id="activation-1",
        )
        cancelling = operation_task_store.request_run_cancel(run_id, reason="stop")
        self.assertEqual("cancelling", cancelling["status"])
        self.assertTrue(operation_task_store.is_run_cancel_requested(run_id, task["run"]["cancellation_token"]))
        self.assertTrue(operation_task_store.release_resource(resource["id"], state="cancelled"))
        operation_task_store.finish_run(run_id, status="cancelled", error="stop")
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("cancelled", detail["status"])
        self.assertEqual("cancelled", detail["resources"][0]["state"])
        self.assertEqual(
            ["run.cancel_requested", "run.cancelled"],
            [event["event_type"] for event in detail["events"][-2:]],
        )

    def test_terminate_queued_run_is_terminal_cancelled(self):
        account_id = self._seed_runtime_account("terminate-queued@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="terminate-queued@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])

        terminated = operation_task_store.terminate_run(run_id, reason="用户确认取消排队任务")

        self.assertEqual("cancelled", terminated["status"])
        self.assertEqual("用户确认取消排队任务", terminated["cancel_reason"])
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("cancelled", detail["status"])
        self.assertEqual("complete", detail["current_stage"])
        self.assertEqual("run.cancelled", detail["events"][-1]["event_type"])

    def test_terminate_running_run_forces_terminal_state_and_reconciles_resources(self):
        account_id = self._seed_runtime_account("terminate-running@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="terminate-running@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        operation_task_store.claim_run(run_id, execution_id="orphaned-worker", worker_pid=123)
        operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation_task_store.register_resource(
            run_id, resource_type="sms_activation", provider="test", external_id="terminate-orphan",
        )

        terminated = operation_task_store.terminate_run(run_id, reason="用户确认终止孤儿任务")

        self.assertEqual("stopped", terminated["status"])
        self.assertEqual("用户确认终止孤儿任务", terminated["cancel_reason"])
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("stopped", detail["status"])
        self.assertEqual("reconciliation_required", detail["resources"][0]["state"])
        self.assertEqual("stopped", detail["resources"][0]["detail"]["terminal_run_status"])
        self.assertEqual("run.stopped", detail["events"][-1]["event_type"])
        self.assertIsNone(operation_task_store.active_run_for_account(account_id))

    def test_terminate_preserves_unknown_remote_write_as_attention_required(self):
        account_id = self._seed_runtime_account("terminate-unknown@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="extract_link", account_id=account_id,
            email="terminate-unknown@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        execution_id = "remote-orphan-worker"
        operation_task_store.claim_run(run_id, execution_id=execution_id, worker_pid=123)
        lease_token = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation_task_store.record_remote_intent(
            run_id,
            execution_id=execution_id,
            lease_token=lease_token,
            action="extract_link",
        )

        terminated = operation_task_store.terminate_run(run_id, reason="用户确认终止远端未知任务")

        self.assertEqual("attention_required", terminated["status"])
        self.assertEqual("request_unknown", terminated["result_summary"]["outcome"])
        self.assertEqual("stopped", terminated["result_summary"]["requested_status"])
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("attention_required", detail["status"])
        self.assertEqual("run.attention_required", detail["events"][-1]["event_type"])

    def test_terminal_run_marks_unreleased_resource_for_reconciliation(self):
        account_id = self._seed_runtime_account("resource@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="resource@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        operation_task_store.register_resource(
            run_id, resource_type="sms_activation", provider="test", external_id="activation-orphan",
        )
        operation_task_store.finish_run(run_id, status="failed", error="provider disconnected")
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("reconciliation_required", detail["resources"][0]["state"])
        self.assertEqual("failed", detail["resources"][0]["detail"]["terminal_run_status"])
        self.assertEqual("run.failed", detail["events"][-1]["event_type"])

    def test_startup_recovery_interrupts_run_and_preserves_resource_for_reconciliation(self):
        account_id = self._seed_runtime_account("restart@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="restart@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        operation_task_store.claim_run(run_id, execution_id="lost-worker", worker_pid=123)
        operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        operation_task_store.register_resource(
            run_id, resource_type="sms_activation", provider="test", external_id="restart-activation",
        )
        # A valid lease belongs to another worker; only make this fixture an
        # orphan explicitly so startup recovery has an unambiguous target.
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('operation_runs')}
                SET heartbeat_at=now() - interval '1 hour'
                WHERE id=%s
                """,
                (run_id,),
            )
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('account_operation_leases')}
                SET expires_at=now() - interval '1 minute'
                WHERE run_id=%s
                """,
                (run_id,),
            )

        self.assertEqual(1, operation_task_store.recover_interrupted_runtime_runs())
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("interrupted", detail["status"])
        self.assertEqual("run.interrupted", detail["events"][-1]["event_type"])
        self.assertEqual("reconciliation_required", detail["resources"][0]["state"])
        self.assertEqual("worker_restart", detail["resources"][0]["detail"]["reason"])
        self.assertTrue(operation_task_store.verify()["ok"])

    def test_startup_recovery_preserves_run_with_valid_other_worker_lease(self):
        account_id = self._seed_runtime_account("live-worker@example.com")
        task = operation_task_store.create_runtime_task(
            task_type="codex_retry", account_id=account_id,
            email="live-worker@example.com", trigger="test",
        )
        run_id = int(task["run"]["id"])
        operation_task_store.claim_run(run_id, execution_id="other-worker", worker_pid=456)
        lease = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id)
        self.assertTrue(lease)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {postgres_store.qualified('operation_runs')}
                SET heartbeat_at=now() - interval '1 hour'
                WHERE id=%s
                """,
                (run_id,),
            )

        self.assertEqual(0, operation_task_store.recover_interrupted_runtime_runs())
        self.assertEqual("running", operation_task_store.get_run(run_id)["status"])

    def test_retention_deletes_only_expired_terminal_tasks_after_archive(self):
        expired = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=501,
            email="expired-retention@example.test", trigger="test",
        )
        operation_task_store.finish_run(expired["run"]["id"], status="success")
        recent = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=502,
            email="recent-retention@example.test", trigger="test",
        )
        operation_task_store.finish_run(recent["run"]["id"], status="success")
        uncertain = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=503,
            email="uncertain-retention@example.test", trigger="test",
        )
        operation_task_store.finish_run(uncertain["run"]["id"], status="failed")
        active = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=504,
            email="active-retention@example.test", trigger="test",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            tasks = postgres_store.qualified("operation_tasks")
            runs = postgres_store.qualified("operation_runs")
            cur.execute(
                f"UPDATE {tasks} SET completed_at=now() - interval '8 days' WHERE id IN (%s, %s)",
                (int(expired["id"]), int(uncertain["id"])),
            )
            cur.execute(
                f"UPDATE {runs} SET completed_at=now() - interval '8 days' WHERE task_id IN (%s, %s)",
                (int(expired["id"]), int(uncertain["id"])),
            )
            cur.execute(
                f"UPDATE {tasks} SET status='request_unknown' WHERE id=%s",
                (int(uncertain["id"]),),
            )

        archived = []
        result = operation_task_store.cleanup_terminal_history(
            retention_days=7,
            limit=100,
            archive=lambda snapshot: archived.append(snapshot),
        )

        self.assertEqual(1, result["deleted_tasks"])
        self.assertEqual([int(expired["id"])], [row["id"] for row in archived[0]["tasks"]])
        self.assertEqual(
            [str(expired["run"]["log_file"])],
            result["native_log_files"],
        )
        self.assertIsNone(operation_task_store.get_task(int(expired["id"])))
        self.assertIsNotNone(operation_task_store.get_task(int(recent["id"])))
        self.assertIsNotNone(operation_task_store.get_task(int(uncertain["id"])))
        self.assertIsNotNone(operation_task_store.get_task(int(active["id"])))

    def test_user_deleted_task_is_hidden_without_reappearing_after_projection_sync(self):
        task = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=505,
            email="user-delete@example.test", trigger="test",
        )
        operation_task_store.finish_run(task["run"]["id"], status="success")

        delete_tasks = getattr(operation_task_store, "delete_tasks", None)
        self.assertTrue(callable(delete_tasks))
        result = delete_tasks([int(task["id"])])

        self.assertEqual([int(task["id"])], result["deleted"])
        operation_task_store.reconcile_all()
        self.assertEqual([], operation_task_store.list_tasks(page_size=20, q="user-delete@example.test")["items"])
        self.assertIsNone(operation_task_store.get_task(int(task["id"])))

    def test_user_delete_skips_active_task(self):
        task = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=506,
            email="user-delete-active@example.test", trigger="test",
        )

        delete_tasks = getattr(operation_task_store, "delete_tasks", None)
        self.assertTrue(callable(delete_tasks))
        result = delete_tasks([int(task["id"])])

        self.assertEqual([], result["deleted"])
        self.assertEqual("任务仍在执行，不能删除", result["skipped"][0]["error"])
        self.assertIsNotNone(operation_task_store.get_task(int(task["id"])))

    def test_retention_reports_more_work_after_deleting_expired_child(self):
        parent = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=601,
            email="retention-parent@example.test", trigger="test",
        )
        operation_task_store.finish_run(parent["run"]["id"], status="success")
        child = operation_task_store.create_runtime_task(
            task_type="plan_check", account_id=601,
            email="retention-parent@example.test", trigger="test",
            parent_task_id=int(parent["id"]),
        )
        operation_task_store.finish_run(child["run"]["id"], status="success")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} "
                "SET completed_at=now() - interval '8 days' WHERE id IN (%s, %s)",
                (int(parent["id"]), int(child["id"])),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET completed_at=now() - interval '8 days' WHERE task_id IN (%s, %s)",
                (int(parent["id"]), int(child["id"])),
            )

        first = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )
        second = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )

        self.assertEqual(1, first["deleted_tasks"])
        self.assertTrue(first["has_more"])
        self.assertEqual(1, second["deleted_tasks"])
        self.assertIsNone(operation_task_store.get_task(int(parent["id"])))
        self.assertIsNone(operation_task_store.get_task(int(child["id"])))

    def test_retention_preserves_stale_terminal_projection_of_active_source_task(self):
        legacy_task_id = account_task_store.create_task(
            task_type="live_check", account_id=None,
            email="active-source-retention@example.test", trigger="test",
        )
        account_task_store.start_task(legacy_task_id, message="源任务仍在执行")
        projected = operation_task_store.list_tasks(
            page_size=10, q="active-source-retention@example.test",
        )["items"][0]
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} "
                "SET status='failed', completed_at=now() - interval '8 days' WHERE id=%s",
                (int(projected["id"]),),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET status='failed', completed_at=now() - interval '8 days' WHERE task_id=%s",
                (int(projected["id"]),),
            )

        result = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )

        self.assertEqual(0, result["deleted_tasks"])
        self.assertIsNotNone(operation_task_store.get_task(int(projected["id"])))

    def test_retention_rolls_back_when_archive_fails(self):
        task = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=701,
            email="archive-failure@example.test", trigger="test",
        )
        operation_task_store.finish_run(task["run"]["id"], status="success")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} "
                "SET completed_at=now() - interval '8 days' WHERE id=%s",
                (int(task["id"]),),
            )

        def fail_archive(_snapshot):
            raise RuntimeError("archive unavailable")

        with self.assertRaisesRegex(RuntimeError, "archive unavailable"):
            operation_task_store.cleanup_terminal_history(
                retention_days=7, limit=100, archive=fail_archive,
            )

        self.assertIsNotNone(operation_task_store.get_task(int(task["id"])))

    def test_retention_preserves_task_with_unfinished_dependency(self):
        task = operation_task_store.create_runtime_task(
            task_type="account_completion", account_id=702,
            email="waiting-dependency@example.test", trigger="test",
        )
        operation_task_store.finish_run(task["run"]["id"], status="success")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} "
                "SET completed_at=now() - interval '8 days' WHERE id=%s",
                (int(task["id"]),),
            )
            cur.execute(
                f"""
                INSERT INTO {postgres_store.qualified('operation_task_dependencies')} (
                    parent_source_system, parent_source_id,
                    child_source_system, child_source_id, dependency_type
                ) VALUES (%s, %s, 'native_operations', 'pending-child', 'account_completion')
                """,
                (str(task["source_system"]), str(task["source_id"])),
            )

        result = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )

        self.assertEqual(0, result["deleted_tasks"])
        self.assertIsNotNone(operation_task_store.get_task(int(task["id"])))

    def test_retention_removes_expired_batch_only_after_last_task(self):
        batch = operation_task_store.create_runtime_batch(
            batch_type="live_check", title="retention batch",
            requested_count=1, trigger="test",
        )
        task = operation_task_store.create_runtime_task(
            task_type="live_check", account_id=703,
            email="batch-retention@example.test", trigger="test",
            batch_id=int(batch["id"]), batch_ordinal=1,
        )
        operation_task_store.finish_run(task["run"]["id"], status="success")
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_tasks')} "
                "SET completed_at=now() - interval '8 days' WHERE id=%s",
                (int(task["id"]),),
            )
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_batches')} "
                "SET completed_at=now() - interval '8 days' WHERE id=%s",
                (int(batch["id"]),),
            )

        result = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )

        self.assertEqual(1, result["deleted_tasks"])
        self.assertEqual(1, result["deleted_batches"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM {postgres_store.qualified('operation_batches')} WHERE id=%s",
                (int(batch["id"]),),
            )
            self.assertEqual(0, cur.fetchone()[0])

    def test_retention_archives_and_removes_expired_empty_batch(self):
        expired = operation_task_store.create_runtime_batch(
            batch_type="live_check", title="expired empty batch",
            requested_count=0, trigger="test",
        )
        recent = operation_task_store.create_runtime_batch(
            batch_type="live_check", title="recent empty batch",
            requested_count=0, trigger="test",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_batches')} "
                "SET status='failed', created_at=now() - interval '8 days', "
                "completed_at=now() - interval '8 days' WHERE id=%s",
                (int(expired["id"]),),
            )
        archived = []

        result = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100,
            archive=lambda snapshot: archived.append(snapshot),
        )

        self.assertEqual(0, result["deleted_tasks"])
        self.assertEqual(1, result["deleted_batches"])
        self.assertEqual([int(expired["id"])], [row["id"] for row in archived[0]["batches"]])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT id FROM {postgres_store.qualified('operation_batches')} ORDER BY id",
            )
            self.assertEqual([int(recent["id"])], [row[0] for row in cur.fetchall()])

    def test_retention_preserves_expired_empty_batch_that_is_not_terminal(self):
        active = operation_task_store.create_runtime_batch(
            batch_type="live_check", title="active empty batch",
            requested_count=0, trigger="test",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_batches')} "
                "SET status='running', created_at=now() - interval '8 days' WHERE id=%s",
                (int(active["id"]),),
            )

        result = operation_task_store.cleanup_terminal_history(
            retention_days=7, limit=100, archive=lambda snapshot: None,
        )

        self.assertEqual(0, result["deleted_batches"])
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status FROM {postgres_store.qualified('operation_batches')} WHERE id=%s",
                (int(active["id"]),),
            )
            self.assertEqual("running", cur.fetchone()[0])

    def test_retention_candidate_lookup_has_status_completion_index(self):
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexdef FROM pg_indexes
                WHERE schemaname=%s AND indexname='idx_operation_tasks_retention'
                """,
                (self.schema,),
            )
            row = cur.fetchone()

        self.assertIsNotNone(row)
        self.assertIn("(status, completed_at, id)", row[0])

    def test_failed_reauthorization_does_not_erase_existing_valid_asset(self):
        self._seed_runtime_account("valid@example.com")
        db.update_account_codex_operation_state(
            "valid@example.com", credential_state="valid",
            execution_status="running", active_run_id=77,
        )
        db.update_account_codex_operation_state(
            "valid@example.com", execution_status="empty",
            last_run_status="failed", error="reauthorization failed", active_run_id=0,
        )
        account = db.get_account_by_email("valid@example.com")
        self.assertEqual("valid", account["codex_credential_state"])
        self.assertEqual("success", account["codex_status"])
        self.assertEqual("failed", account["codex_last_run_status"])
