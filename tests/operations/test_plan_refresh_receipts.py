"""套餐补查失败与已确认的 AT 刷新分别保留事实。"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from core.operations import run_log
from core.storage import records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class PlanRefreshReceiptTests(PostgresTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for key, value in (("_LOG_ROOT", Path(temp.name)), ("_TASK_LOG_ROOT", Path(temp.name) / "tasks")):
            context = patch.object(run_log, key, value)
            context.start()
            self.addCleanup(context.stop)
        operation.reset_ready()
        operation.init()

    def make_run(self, *, task_type="plan_check", action="token_refresh", outcome="confirmed", old_run=False):
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": f"receipt-{uuid.uuid4().hex}@example.test", "access_token": "synthetic-at",
        })
        task = operation.create_runtime_task(
            task_type=task_type, account_id=account_id, email="receipt@example.test",
            source_system="native_operations",
        )
        run_id = int(task["run"]["id"])
        operation.claim_run(run_id, execution_id="receipt-worker", worker_pid=101)
        lease_token = operation.acquire_account_lease(account_id=account_id, run_id=run_id)
        fence = {"execution_id": "receipt-worker", "lease_token": lease_token}
        request_id = f"token-refresh:{run_id + 100 if old_run else run_id}:synthetic-request"
        operation.record_remote_intent(run_id, action=action, request_id=request_id, **fence)
        operation.record_remote_receipt(run_id, action=action, request_id=request_id, outcome=outcome, detail={
            "remote_result_confirmed": True,
            "local_business_writeback_confirmed": True,
            "local_readback_confirmed": True,
        }, **fence)
        return run_id, fence

    def finish(self, run_id, fence, *, status="failed", **summary):
        return operation.finish_run(run_id, status=status, message="套餐后续查询失败", error="代理超时",
            result_summary={"auto_refresh_at": {"attempted": True, "ok": True}, **summary}, **fence)

    def test_confirmed_refresh_does_not_turn_later_plan_failure_into_unknown(self):
        for status in ("failed", "partial_success"):
            with self.subTest(status=status):
                run_id, fence = self.make_run()
                finished = self.finish(run_id, fence, status=status)
                self.assertEqual(status, finished["status"])
                self.assertFalse(finished["result_summary"].get("reconcile_required", False))
                self.assertEqual("confirmed", operation.get_run(run_id)["data"]["remote_receipt"]["receipt_state"])

    def test_confirmed_refresh_allows_later_read_only_query_to_be_cancelled(self):
        for status in ("cancelled", "stopped"):
            with self.subTest(status=status):
                run_id, fence = self.make_run()
                finished = self.finish(run_id, fence, status=status)
                self.assertEqual(status, finished["status"])
                self.assertFalse(finished["result_summary"].get("reconcile_required", False))

    def test_cancellation_cannot_hide_an_unconfirmed_refresh(self):
        for status in ("cancelled", "stopped"):
            with self.subTest(status=status):
                run_id, fence = self.make_run(outcome="response_received")
                finished = self.finish(run_id, fence, status=status)
                self.assertEqual("attention_required", finished["status"])
                self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_success_summary_does_not_confirm_a_received_only_refresh(self):
        run_id, fence = self.make_run(outcome="response_received")
        finished = self.finish(run_id, fence)
        self.assertEqual("attention_required", finished["status"])
        self.assertTrue(finished["result_summary"]["reconcile_required"])

    def test_refresh_failure_or_unconfirmed_result_cannot_use_exception(self):
        for summary in (
            {"auto_refresh_at": {"attempted": True, "ok": False}},
            {"auto_refresh_at": {"attempted": False, "ok": True}},
            {"auto_refresh_at": {"attempted": True, "ok": True, "reconcile_required": True}},
            {"reconcile_required": True}, {"manual_reconcile": True}, {"outcome": "request_unknown"},
        ):
            with self.subTest(summary=summary):
                run_id, fence = self.make_run()
                finished = self.finish(run_id, fence, **summary)
                self.assertEqual("attention_required", finished["status"])

    def test_other_actions_and_task_types_keep_existing_remote_write_boundary(self):
        for options in ({"action": "password_change"}, {"task_type": "registration"}, {"task_type": "token_refresh"}):
            with self.subTest(options=options):
                run_id, fence = self.make_run(**options)
                finished = self.finish(run_id, fence)
                self.assertEqual("attention_required", finished["status"])

    def test_receipt_from_a_different_run_does_not_confirm_this_refresh(self):
        run_id, fence = self.make_run(old_run=True)
        self.assertEqual("attention_required", self.finish(run_id, fence)["status"])

    def test_each_confirmation_proof_is_required_even_if_state_says_confirmed(self):
        for missing in ("remote_result_confirmed", "local_business_writeback_confirmed", "local_readback_confirmed"):
            with self.subTest(missing=missing):
                run_id, fence = self.make_run()
                data = operation.get_run(run_id)["data"]
                data["remote_receipt"]["detail"].pop(missing)
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {operation._table('operation_runs')} SET data=%s::jsonb WHERE id=%s",
                                (json.dumps(data), run_id))
                finished = self.finish(run_id, fence)
                self.assertEqual("attention_required", finished["status"])
