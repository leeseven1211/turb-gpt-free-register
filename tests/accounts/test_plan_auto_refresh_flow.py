"""验证独立套餐 handler 的 AT 自动恢复、逐国补查和手动重跑契约。"""
from __future__ import annotations

import base64
import json
import tempfile
import time
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.accounts.liveness import service as liveness
from core.accounts.plans import service as plans
from core.operations import run_log, task_gateway
from core.storage import accounts, records
from core.storage.operations import store as operation
from tests.accounts.test_plan_country_check import offer_result
from tests.support_pg import PostgresTestCase


class PlanAutoRefreshFlowTests(PostgresTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for key, value in (("_LOG_ROOT", Path(temp.name)), ("_TASK_LOG_ROOT", Path(temp.name) / "tasks")):
            patcher = patch.object(run_log, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.email = "plan-flow@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "access_token": "old-at", "plan_check_status": "queued",
        })
        operation.reset_ready()
        operation.init()
        self.events = []
        self.routes = []
        self.refresh_contexts = []

    def context(self, *, countries=None, enabled=True, trigger="manual", snapshot=None):
        settings = {
            "auto_refresh_at_enabled": enabled, "refresh_driver": "protocol",
            "refresh_protocol_version": "v2", "network_timeout_seconds": 30,
            "plan_check_max_attempts": 1, "country_wait_timeout": 5,
            "min_interval": 0, "jitter": 0, "payment_methods_enabled": False,
        } if snapshot is None else snapshot
        task = operation.create_runtime_task(
            task_type="plan_check", account_id=self.account_id, email=self.email, trigger=trigger,
            data={"countries": ["JP", "VN"] if countries is None else countries,
                  "proxy_source": "pool", "config_snapshot": settings},
        )
        execution_id = f"plan-flow-{uuid.uuid4().hex}"
        claimed = operation.claim_run(task["run"]["id"], execution_id=execution_id, worker_pid=102)
        context = task_gateway.OperationHandlerContext(claimed, execution_id=execution_id)
        self.addCleanup(context.release_lease)
        return context, task

    def acquire(self, **kwargs):
        country = kwargs.get("region") or "JP"
        index = len(self.routes) + 1
        self.events.append(("acquire", country, index))
        item = SimpleNamespace(
            proxy_url=country, region=country,
            public_dict=lambda: {"proxy_region": country, "proxy_provider": "1024proxy"},
            release=Mock(side_effect=lambda **kw: self.events.append(("release", country, index))),
        )
        self.routes.append(item)
        return item

    def refresh(self, **kwargs):
        # 保留真实内联入口，证明刷新沿用父 Run、租约及配置，不生成额外任务。
        context = kwargs["operation_context"]
        self.refresh_contexts.append(context)
        self.assertFalse(kwargs["finish_operation"])
        self.assertTrue(kwargs["force_refresh"])
        self.assertEqual("v2", kwargs["refresh_driver"])
        self.assertEqual("running", operation.get_run(context.run_id)["status"])
        self.assertEqual(context.run_id, context.execution_fence["run_id"])
        self.events.append(("refresh",))
        result = {"ok": True, "status": "live", "access_token": "new-at"}
        self.assertTrue(kwargs["result_writer"](result))
        return result

    def execute(self, context, query, *, refresh=None):
        with ExitStack() as stack:
            stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", side_effect=self.acquire))
            stack.enter_context(patch.object(plans, "check_account_plan", side_effect=query))
            stack.enter_context(patch.object(plans, "_wait_for_rate_slot"))
            stack.enter_context(patch.object(plans, "_log_plan_result"))
            stack.enter_context(patch.object(plans, "_reconcile_extract_payment_after_plan"))
            auth = stack.enter_context(patch.object(liveness, "_run_live_check", side_effect=refresh or self.refresh))
            plans._handle_plan_operation(context)
        return operation.get_run(context.run_id), auth

    def test_multi_country_401_refreshes_once_and_keeps_successful_country(self):
        context, task = self.context()
        queries = []

        def query(token, **kwargs):
            country = kwargs["proxy"]
            queries.append((country, token))
            self.assertEqual(token, accounts.get_account(self.account_id)["access_token"])
            if country == "VN" and token == "old-at":
                return {"ok": False, "http_status": 401, "error": "AT已过期/失效，请手动查活刷新"}
            return offer_result(country)

        run, auth = self.execute(context, query)
        self.assertEqual([("JP", "old-at"), ("VN", "old-at"), ("VN", "new-at")], queries)
        self.assertEqual("success", run["status"])
        self.assertTrue(run["result_summary"]["auto_refresh_at"]["ok"])
        self.assertEqual([context], self.refresh_contexts)
        self.assertEqual(1, auth.call_count)
        self.assertTrue(all(route.release.call_count == 1 for route in self.routes))
        self.assertEqual(task["id"], run["task_id"])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')}")
            self.assertEqual(1, cur.fetchone()["n"])

    def test_second_401_after_refresh_stays_retryable_without_an_automatic_loop(self):
        context, _ = self.context(countries=["JP"])
        tokens = []

        def query(token, **kwargs):
            tokens.append(token)
            return {"ok": False, "http_status": 401, "error": "AT已过期/失效，请手动查活刷新"}

        run, auth = self.execute(context, query)
        self.assertEqual(["old-at", "new-at"], tokens)
        self.assertEqual(1, auth.call_count)
        self.assertEqual("failed", run["status"])
        self.assertTrue(run["result_summary"]["auto_refresh_at"]["ok"])
        retry = operation.retry_runtime_task(run["task_id"])
        self.assertEqual("queued", retry["status"])

    def test_disabled_switch_does_not_refresh_on_401(self):
        context, _ = self.context(countries=["JP"], enabled=False)
        run, auth = self.execute(context, lambda token, **kw: {"ok": False, "http_status": 401, "error": "HTTP 401"})
        auth.assert_not_called()
        self.assertEqual("failed", run["status"])
        self.assertNotIn("plan_auto_refresh_at", run["data"])

    def test_registration_trigger_never_uses_plan_auto_refresh(self):
        context, _ = self.context(countries=["JP", "VN"], trigger="registration_retry_plan_check")
        queries = []

        def query(token, **kwargs):
            queries.append(token)
            return {"ok": False, "http_status": 401, "error": "HTTP 401"}

        run, auth = self.execute(context, query)
        auth.assert_not_called()
        self.assertEqual(["old-at"], queries)
        self.assertNotIn("plan_auto_refresh_at", run["data"])
        self.assertNotIn("plan_check_country_results", accounts.get_account(self.account_id))

    def test_missing_at_refreshes_before_any_country_request(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"access_token": ""})
        context, _ = self.context(countries=["JP"])

        def query(token, **kwargs):
            self.assertEqual("new-at", token)
            self.assertEqual("refresh", self.events[0][0])
            return offer_result("JP")

        run, auth = self.execute(context, query)
        self.assertEqual("success", run["status"])
        self.assertEqual(1, auth.call_count)
        self.assertEqual("token_missing", run["data"]["plan_auto_refresh_at"]["reason"])

    def test_locally_expired_at_refreshes_before_single_country_request(self):
        payload = base64.urlsafe_b64encode(json.dumps({"exp": time.time() - 60}).encode()).decode().rstrip("=")
        records.patch_row(records.ACCOUNTS, self.account_id, {"access_token": f"header.{payload}.signature"})
        context, _ = self.context(countries=[])

        def query(token, **kwargs):
            self.assertEqual("new-at", token)
            self.assertEqual("refresh", self.events[0][0])
            return offer_result("JP")

        run, auth = self.execute(context, query)
        self.assertEqual("success", run["status"])
        self.assertEqual(1, auth.call_count)
        self.assertEqual("token_local_expired", run["data"]["plan_auto_refresh_at"]["reason"])

    def test_failed_refresh_preserves_the_specific_cause_in_task_summary(self):
        records.patch_row(records.ACCOUNTS, self.account_id, {"access_token": ""})
        context, _ = self.context(countries=["JP"])
        query = Mock(side_effect=AssertionError("刷新失败后不应发送套餐请求"))

        def failed_refresh(**kwargs):
            result = {"ok": False, "status": "failed", "error": "邮箱验证码等待超时", "error_code": "email_otp_timeout"}
            self.assertTrue(kwargs["result_writer"](result))
            return result

        run, auth = self.execute(context, query, refresh=failed_refresh)
        query.assert_not_called()
        self.assertEqual(1, auth.call_count)
        self.assertEqual("failed", run["status"])
        summary = run["result_summary"]["auto_refresh_at"]
        self.assertFalse(summary["ok"])
        self.assertEqual("email_otp_timeout", summary["error_code"])
        self.assertEqual("邮箱验证码等待超时", summary["error"])
        self.assertIn("邮箱验证码等待超时", json.dumps(run["result_summary"], ensure_ascii=False))

    def test_single_country_releases_old_route_before_refresh_and_reacquires_afterward(self):
        context, _ = self.context(countries=[])
        tokens = []

        def query(token, **kwargs):
            tokens.append(token)
            return ({"ok": False, "http_status": 401, "error": "HTTP 401"}
                    if token == "old-at" else offer_result("JP"))

        run, auth = self.execute(context, query)
        self.assertEqual(["old-at", "new-at"], tokens)
        self.assertEqual([("acquire", "JP", 1), ("release", "JP", 1), ("refresh",),
                          ("acquire", "JP", 2), ("release", "JP", 2)], self.events)
        self.assertEqual("success", run["status"])
        self.assertEqual(1, auth.call_count)
        self.assertEqual(2, len(run["result_summary"]["promotion_query_history"]))

    def test_old_manual_retry_adds_refresh_config_without_overwriting_frozen_plan_options(self):
        frozen = {"payment_methods_enabled": False, "plan_check_timeout": 7,
                  "plan_check_max_attempts": 1, "country_wait_timeout": 9}
        context, task = self.context(countries=["VN", "JP"], snapshot=frozen)
        context.finish(status="failed", message="历史套餐任务失败", error="全部国家查询失败：VN、JP")
        current = {
            "PLAN_CHECK_AUTO_REFRESH_AT_ENABLED": True, "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
            "OPENAI_PROTOCOL_VERSION": "v3", "ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS": 60,
            "PLAN_CHECK_COUNTRIES": ["US"], "PLAN_CHECK_PAYMENT_METHODS_ENABLED": True,
            "PLAN_CHECK_TIMEOUT": 30, "PLAN_CHECK_MAX_ATTEMPTS": 4, "PLAN_CHECK_COUNTRY_WAIT_TIMEOUT": 120,
        }
        with (patch.object(plans, "get_config_snapshot", return_value=current),
              patch.object(task_gateway, "notify_dispatch")):
            retried = plans._retry_plan_operation({**task, "status": "failed", "last_run_id": context.run_id})
        self.assertTrue(retried["accepted"])
        run = operation.get_run(retried["run_id"])
        snapshot = run["data"]["config_snapshot"]
        self.assertEqual(["VN", "JP"], run["data"]["countries"])
        for key, value in frozen.items():
            self.assertEqual(value, snapshot[key])
        self.assertTrue(snapshot["auto_refresh_at_enabled"])
        self.assertEqual("protocol", snapshot["refresh_driver"])
        self.assertEqual("v3", snapshot["refresh_protocol_version"])
        self.assertEqual("queued", accounts.get_account(self.account_id)["plan_check_status"])

    def test_manual_retry_preserves_an_existing_disabled_switch_and_refresh_driver(self):
        frozen = {"auto_refresh_at_enabled": False, "refresh_driver": "browser_roxy",
                  "refresh_protocol_version": "v1", "plan_check_timeout": 7}
        context, task = self.context(countries=["VN"], snapshot=frozen)
        context.finish(status="failed", message="套餐查询失败", error="HTTP 401")
        with (patch.object(plans, "get_config_snapshot") as current,
              patch.object(task_gateway, "notify_dispatch")):
            retried = plans._retry_plan_operation({**task, "status": "failed", "last_run_id": context.run_id})
        current.assert_not_called()
        self.assertTrue(retried["accepted"])
        run = operation.get_run(retried["run_id"])
        self.assertEqual(frozen, run["data"]["config_snapshot"])
        self.assertEqual(["VN"], run["data"]["countries"])
