# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from core import account_task_store, db, operation_task_store, postgres_store, record_store, task_run_log
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

        self.assertEqual(1, operation_task_store.recover_interrupted_runtime_runs())
        detail = operation_task_store.get_task(int(task["id"]))
        self.assertEqual("interrupted", detail["status"])
        self.assertEqual("run.interrupted", detail["events"][-1]["event_type"])
        self.assertEqual("reconciliation_required", detail["resources"][0]["state"])
        self.assertEqual("worker_restart", detail["resources"][0]["detail"]["reason"])
        self.assertTrue(operation_task_store.verify()["ok"])

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
