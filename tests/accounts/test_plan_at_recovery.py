"""验证独立套餐 AT 恢复额度、先保存后补查及旧结果写回围栏。"""
from __future__ import annotations

import base64
import json
import tempfile
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts.liveness import service as liveness
from core.accounts.plans import service as plans
from core.accounts.plans.at_recovery import PlanAtRecovery
from core.operations import run_log, task_gateway
from core.operations.runtime import OperationCancelled
from core.storage import accounts, records
from core.storage.accounts import plan_refresh
from core.storage.operations import store as operation
from tests.accounts.test_plan_country_check import offer_result
from tests.support_pg import PostgresTestCase


class PlanAtRecoveryTests(PostgresTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for key, value in (("_LOG_ROOT", Path(temp.name)), ("_TASK_LOG_ROOT", Path(temp.name) / "tasks")):
            context = patch.object(run_log, key, value)
            context.start()
            self.addCleanup(context.stop)
        self.email = "recovery@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "access_token": "old-at", "plan_check_status": "queued",
        })
        operation.reset_ready()
        operation.init()

    def make_context(self, *, task=None):
        if task is None:
            task = operation.create_runtime_task(task_type="plan_check", account_id=self.account_id, email=self.email,
                data={"config_snapshot": {"auto_refresh_at_enabled": True, "network_timeout_seconds": 30}})
            run_id = int(task["run"]["id"])
        else:
            run_id = int(operation.retry_runtime_task(int(task["id"]))["id"])
        execution_id = f"plan-at-{uuid.uuid4().hex}"
        claimed = operation.claim_run(run_id, execution_id=execution_id, worker_pid=101)
        context = task_gateway.OperationHandlerContext(claimed, execution_id=execution_id)
        context.acquire_lease()
        self.addCleanup(context.release_lease)
        return context, task

    def recovery(self, context):
        return PlanAtRecovery(context, account_id=self.account_id, email=self.email,
                              config_snapshot={"network_timeout_seconds": 30})

    def saved_result(self, **kwargs):
        context = kwargs["operation_context"]
        state = operation.get_run(context.run_id)["data"]["plan_auto_refresh_at"]
        self.assertTrue(state["attempted"], "发起刷新前必须先持久化本 Run 额度")
        self.assertEqual("running", state["status"])
        result = {"ok": True, "status": "live", "access_token": "new-at"}
        self.assertTrue(kwargs["result_writer"](result))
        self.assertEqual("new-at", accounts.get_account(self.account_id)["access_token"])
        return {"accepted": True, "result": result}

    def test_refresh_saves_new_at_before_return_and_keeps_credentials_out_of_run_state(self):
        context, _ = self.make_context()
        recovery = self.recovery(context)
        with patch.object(liveness, "run_account_live_check_inline", side_effect=self.saved_result) as refresh:
            self.assertEqual("new-at", recovery.refresh("old-at", reason="token_http_401"))
        self.assertTrue(refresh.call_args.kwargs["force_refresh"])
        self.assertTrue(refresh.call_args.kwargs["allow_missing_token"])
        self.assertIs(context, refresh.call_args.kwargs["operation_context"])
        self.assertTrue(recovery.summary["ok"])
        state = operation.get_run(context.run_id)["data"]["plan_auto_refresh_at"]
        self.assertEqual("success", state["status"])
        self.assertNotIn("old-at", json.dumps(state))
        self.assertNotIn("new-at", json.dumps(state))
        self.assertTrue(accounts.get_account(self.account_id)["plan_check_deadline_at"])

    def test_same_run_recreated_recovery_cannot_refresh_twice(self):
        context, _ = self.make_context()
        with patch.object(liveness, "run_account_live_check_inline", side_effect=self.saved_result) as refresh:
            self.assertEqual("new-at", self.recovery(context).refresh("old-at", reason="token_http_401"))
            self.assertIsNone(self.recovery(context).refresh("new-at", reason="token_http_401"))
        self.assertEqual(1, refresh.call_count)

    def test_new_run_gets_a_new_refresh_allowance(self):
        context, task = self.make_context()
        with patch.object(liveness, "run_account_live_check_inline", side_effect=self.saved_result) as refresh:
            self.recovery(context).refresh("old-at", reason="token_http_401")
            context.finish(status="failed", message="测试下一 Run")
            context.release_lease()
            next_context, _ = self.make_context(task=task)
            self.assertNotEqual(context.run_id, next_context.run_id)
            self.assertEqual("new-at", self.recovery(next_context).refresh("new-at", reason="token_http_401"))
        self.assertEqual(2, refresh.call_count)

    def test_ok_without_a_successful_at_write_is_not_a_refresh_success(self):
        context, _ = self.make_context()
        recovery = self.recovery(context)
        with patch.object(liveness, "run_account_live_check_inline", return_value={
            "accepted": True, "result": {"ok": True, "status": "live", "access_token": "unwritten-at"},
        }):
            self.assertIsNone(recovery.refresh("old-at", reason="token_http_401"))
        self.assertFalse(recovery.summary["ok"])
        self.assertEqual("old-at", accounts.get_account(self.account_id)["access_token"])

    def test_email_or_at_changed_during_refresh_cannot_be_overwritten(self):
        for changed in ({"email": "changed@example.test"}, {"access_token": "other-at"}):
            with self.subTest(changed=changed):
                records.patch_row(records.ACCOUNTS, self.account_id, {"email": self.email, "access_token": "old-at"})
                context, _ = self.make_context()
                records.patch_row(records.ACCOUNTS, self.account_id, changed)
                with self.assertRaises(task_gateway.OperationLeaseLost):
                    plan_refresh.save_liveness(self.account_id, {"ok": True, "status": "live", "access_token": "stale-at"},
                        fence=context.execution_fence, expected_email=self.email, expected_token="old-at")
                account = accounts.get_account(self.account_id)
                for key, value in changed.items():
                    self.assertEqual(value, account[key])
                context.finish(status="failed", message="旧写回已被阻止")
                context.release_lease()

    def test_old_worker_cannot_start_refresh_or_write_new_at(self):
        context, _ = self.make_context()
        fence = dict(context.execution_fence)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET execution_id=%s WHERE id=%s",
                        ("replacement-worker", context.run_id))
        with self.assertRaises(task_gateway.OperationLeaseLost):
            plan_refresh.begin(self.account_id, fence=fence, reason="token_http_401", budget_seconds=150)
        with self.assertRaises(task_gateway.OperationLeaseLost):
            plan_refresh.save_liveness(self.account_id, {"ok": True, "status": "live", "access_token": "stale-at"},
                fence=fence, expected_email=self.email, expected_token="old-at")
        self.assertEqual("old-at", accounts.get_account(self.account_id)["access_token"])

    def test_at_expiration_check_distinguishes_missing_expired_and_current_tokens(self):
        def jwt(exp):
            payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
            return f"header.{payload}.signature"
        self.assertTrue(PlanAtRecovery.needs_refresh(""))
        self.assertTrue(PlanAtRecovery.needs_refresh(jwt(time.time() - 60)))
        self.assertFalse(PlanAtRecovery.needs_refresh(jwt(time.time() + 3600)))
        self.assertFalse(PlanAtRecovery.needs_refresh("opaque-at"))

    def test_second_401_after_refresh_does_not_loop_or_repeat_successful_country(self):
        context, _ = self.make_context()
        recovery = self.recovery(context)
        queries = []
        routes = []
        def route(**kwargs):
            country = kwargs["region"]
            item = SimpleNamespace(proxy_url=country, region=country, release=Mock(),
                public_dict=lambda: {"proxy_region": country, "proxy_provider": "1024proxy"})
            routes.append(item)
            return item
        def query(token, **kwargs):
            country = kwargs["proxy"]
            queries.append((country, token))
            if country == "JP":
                return offer_result(country)
            return {"ok": False, "http_status": 401, "error": "AT已过期/失效，请手动查活刷新"}
        reporter = SimpleNamespace(stage=Mock(), note=Mock(), resource=Mock(), finish=Mock())
        with (
            patch("core.proxy.account_routes.acquire_account_proxy", side_effect=route),
            patch.object(plans, "check_account_plan", side_effect=query),
            patch.object(plans, "_wait_for_rate_slot"),
            patch.object(liveness, "run_account_live_check_inline", side_effect=self.saved_result) as refresh,
        ):
            result = plans._run_country_plan_checks(
                account_id=self.account_id, email=self.email, access_token="old-at", trigger="manual",
                proxy=None, timezone_offset_min="-", countries=["JP", "VN"], reporter=reporter,
                operation_context=context, config_snapshot={"plan_check_max_attempts": 1, "country_wait_timeout": 5},
                proxy_source="pool", fence=context.execution_fence, at_recovery=recovery,
            )
        self.assertEqual([("JP", "old-at"), ("VN", "old-at"), ("VN", "new-at")], queries)
        self.assertEqual(1, refresh.call_count)
        self.assertTrue(result["plan_check_partial"])
        self.assertEqual(["VN"], result["failed_countries"])
        self.assertTrue(all(item.release.call_count == 1 for item in routes))
        self.assertTrue(result["auto_refresh_at"]["ok"])

    def test_cancelled_recheck_cannot_mark_the_saved_new_at_as_expired_again(self):
        context, _ = self.make_context()
        recovery = self.recovery(context)
        payload = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + 3600}).encode()).decode().rstrip("=")
        new_at = f"header.{payload}.signature"
        def refresh(**kwargs):
            request_id = f"token-refresh:{context.run_id}:cancel-test"
            context.remote_request_started("token_refresh", request_id=request_id)
            result = {"ok": True, "status": "live", "access_token": new_at}
            self.assertTrue(kwargs["result_writer"](result))
            self.assertFalse(accounts.get_account(self.account_id)["token_expired"])
            context.remote_request_receipt(action="token_refresh", request_id=request_id, outcome="confirmed", detail={
                "remote_result_confirmed": True, "local_business_writeback_confirmed": True,
                "local_readback_confirmed": True,
            })
            return {"accepted": True, "result": result}
        route = SimpleNamespace(proxy_url="VN", region="VN", release=Mock(),
            public_dict=lambda: {"proxy_region": "VN", "proxy_provider": "1024proxy"})
        with (
            patch("core.proxy.account_routes.acquire_account_proxy",
                  side_effect=[route, OperationCancelled("补查线路领取前取消")]),
            patch.object(plans, "check_account_plan", return_value={
                "ok": False, "http_status": 401, "token_expired": True,
                "error": "AT已过期/失效，请手动查活刷新",
            }) as query,
            patch.object(plans, "_wait_for_rate_slot"),
            patch.object(liveness, "run_account_live_check_inline", side_effect=refresh),
        ):
            result = plans._run_plan_check(
                account_id=self.account_id, email=self.email, access_token="old-at", trigger="manual",
                proxy=None, timezone_offset_min="-", operation_context=context,
                config_snapshot={"plan_check_max_attempts": 1, "country_wait_timeout": 5},
                countries=["VN"], at_recovery=recovery,
            )
        self.assertEqual("cancelled", result["status"])
        self.assertEqual(1, query.call_count)
        account = accounts.get_account(self.account_id)
        self.assertEqual(new_at, account["access_token"])
        self.assertIsNot(True, account.get("token_expired"))
        row = account["plan_check_country_results"][0]
        self.assertEqual("cancelled", row["status"])
        self.assertIsNone(row.get("http_status"))
        self.assertNotIn("token_expired", row)
        self.assertNotIn("token_expires_at", row)
        self.assertNotIn("token_expired", result)
        self.assertEqual("cancelled", operation.get_run(context.run_id)["status"])
        self.assertTrue(operation.get_run(context.run_id)["result_summary"]["auto_refresh_at"]["ok"])
