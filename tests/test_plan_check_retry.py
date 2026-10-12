# -*- coding: utf-8 -*-
"""验证套餐查询重跑的账号投影与 durable Run 在同一事务中迁移。"""
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from psycopg.errors import UniqueViolation

from core import db, plan_check_service, record_store, task_run_log
from core.operations import task_gateway
from core.storage import operation
from tests.support_pg import PostgresTestCase


class PlanCheckRetryTests(PostgresTestCase):
    def setUp(self):
        log_dir = tempfile.TemporaryDirectory()
        self.addCleanup(log_dir.cleanup)
        for name, value in (
            ("_LOG_ROOT", Path(log_dir.name)),
            ("_TASK_LOG_ROOT", Path(log_dir.name) / "tasks"),
        ):
            log_patch = patch.object(task_run_log, name, value)
            log_patch.start()
            self.addCleanup(log_patch.stop)
        task_gateway.init()
        operation.reset_ready()
        operation.init()
        self.assertTrue(plan_check_service.register_operation_handlers())
        self.previous_success = {
            "current_plan_type": "plus",
            "subscription_plan": "chatgptplusplan",
            "plan_last_success_at": "2026-10-10T08:00:00+00:00",
            "plus_promo_kind": "discount",
            "plus_promo_campaign_id": "test-campaign",
            "quota_status": "success",
            "quota_type": "test-window",
            "quota_windows": [{"model": "test-model", "remaining": 20}],
            "quota_last_success_at": "2026-10-10T08:00:00+00:00",
        }

    def _terminal_plan(self, status: str, *, email: str) -> tuple[int, dict]:
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-access-token",
            "account_status": "active",
            "plan_check_status": status,
            "plan_check_ok": False,
            "plan_check_trigger": "manual",
            "plan_check_queued_at": "2026-10-11T08:00:00+00:00",
            "plan_check_started_at": "2026-10-11T08:00:01+00:00",
            "plan_check_completed_at": "2026-10-11T08:00:02+00:00",
            "plan_check_http_status": 502,
            "plan_check_error": "上次套餐查询失败",
            **self.previous_success,
        })
        task = operation.create_runtime_task(
            task_type="plan_check", account_id=account_id, email=email,
            trigger="manual", resource_family="openai_interactive",
        )
        operation.finish_run(
            int(task["run"]["id"]), status=status, error="上次套餐查询失败",
        )
        return account_id, task

    def _assert_original_task_unchanged(self, task: dict) -> None:
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status, last_run_id FROM {operation._table('operation_tasks')} WHERE id=%s",
                (int(task["id"]),),
            )
            persisted_task = cur.fetchone()
            cur.execute(
                f"SELECT COUNT(*) AS total FROM {operation._table('operation_runs')} WHERE task_id=%s",
                (int(task["id"]),),
            )
            self.assertEqual(1, int(cur.fetchone()["total"]))
        self.assertEqual("failed", persisted_task["status"])
        self.assertEqual(int(task["run"]["id"]), persisted_task["last_run_id"])

    def test_failed_and_cancelled_retries_queue_account_and_can_start(self):
        for status in ("failed", "cancelled"):
            with self.subTest(status=status):
                account_id, task = self._terminal_plan(
                    status, email=f"retry-{status}@example.test",
                )

                retry = operation.retry_runtime_task(int(task["id"]), trigger="test_retry")

                self.assertEqual("queued", retry["status"])
                self.assertEqual(2, retry["run_no"])
                account = record_store.get_row(record_store.ACCOUNTS, account_id)
                self.assertEqual("queued", account["plan_check_status"])
                self.assertFalse(account["plan_check_ok"])
                self.assertEqual("test_retry", account["plan_check_trigger"])
                self.assertNotEqual("2026-10-11T08:00:00+00:00", account["plan_check_queued_at"])
                self.assertTrue(account["plan_check_queued_at"])
                for key in (
                    "plan_check_started_at", "plan_check_completed_at",
                    "plan_check_error", "plan_check_http_status",
                ):
                    self.assertIsNone(account.get(key), key)
                for key, value in self.previous_success.items():
                    self.assertEqual(value, account[key], key)
                self.assertTrue(db.mark_account_plan_check_running(account_id))
                self.assertEqual("running", db.get_account(account_id)["plan_check_status"])

    def test_run_insert_failure_rolls_back_account_and_task(self):
        account_id, task = self._terminal_plan("failed", email="retry-rollback@example.test")
        account_before = record_store.get_row(record_store.ACCOUNTS, account_id)
        observed_statuses = []

        def fail_insert(cur, **_kwargs):
            account = record_store.get_row(record_store.ACCOUNTS, account_id, conn=cur.connection)
            observed_statuses.append(account["plan_check_status"])
            raise RuntimeError("模拟 Run 插入失败")

        with patch.object(operation, "_insert_runtime_run", side_effect=fail_insert):
            with self.assertRaisesRegex(RuntimeError, "模拟 Run 插入失败"):
                operation.retry_runtime_task(int(task["id"]), trigger="test_retry")

        self.assertEqual(["queued"], observed_statuses)
        self.assertEqual(account_before, record_store.get_row(record_store.ACCOUNTS, account_id))
        self._assert_original_task_unchanged(task)

    def test_another_active_plan_run_rejects_retry_without_overwriting_account(self):
        for active_status in ("queued", "running"):
            with self.subTest(active_status=active_status):
                account_id, task = self._terminal_plan(
                    "failed", email=f"retry-conflict-{active_status}@example.test",
                )
                active = operation.create_runtime_task(
                    task_type="plan_check", account_id=account_id,
                    email=f"retry-conflict-{active_status}@example.test", trigger="active_query",
                    resource_family="openai_interactive",
                )
                if active_status == "running":
                    self.assertIsNotNone(operation.claim_run(
                        int(active["run"]["id"]), execution_id="test-active-worker", worker_pid=1,
                    ))
                record_store.patch_row(record_store.ACCOUNTS, account_id, {
                    "plan_check_status": active_status,
                    "plan_check_trigger": "active_query",
                    "plan_check_queued_at": "2026-10-12T08:00:00+00:00",
                    "plan_check_started_at": "2026-10-12T08:00:01+00:00" if active_status == "running" else None,
                    "plan_check_completed_at": None,
                    "plan_check_error": None,
                    "plan_check_http_status": None,
                })
                account_before = record_store.get_row(record_store.ACCOUNTS, account_id)

                with self.assertRaises(UniqueViolation):
                    operation.retry_runtime_task(int(task["id"]), trigger="test_retry")

                self.assertEqual(account_before, record_store.get_row(record_store.ACCOUNTS, account_id))
                self.assertEqual(active_status, operation.get_run(int(active["run"]["id"]))["status"])
                self._assert_original_task_unchanged(task)

    def test_durable_retry_reaches_proxy_and_plan_query_and_succeeds(self):
        account_id, task = self._terminal_plan("failed", email="retry-handler@example.test")
        route = SimpleNamespace(
            proxy_url=None,
            public_dict=lambda: {"network_route": "direct", "proxy_provider": "test"},
            release=Mock(),
        )
        retry = operation.retry_runtime_task(int(task["id"]), trigger="test_retry")

        with (
            patch("core.account_proxy.acquire_account_proxy", return_value=route) as acquire,
            patch.object(plan_check_service, "_query_account_plan", return_value={
                "ok": True, "http_status": 200, "current_plan_type": "plus",
                "plus_trial_eligible": False,
            }) as query,
        ):
            result = task_gateway._execute_operation_handler("plan_check", int(retry["id"]))

        acquire.assert_called_once()
        self.assertEqual(account_id, acquire.call_args.kwargs["account_id"])
        self.assertEqual("plan-check", acquire.call_args.kwargs["purpose"])
        query.assert_called_once()
        self.assertEqual("test_retry", query.call_args.kwargs["trigger"])
        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(int(retry["id"]))["status"])
        account = db.get_account(account_id)
        self.assertEqual("success", account["plan_check_status"])
        self.assertTrue(account["plan_check_ok"])
        route.release.assert_called_once()
