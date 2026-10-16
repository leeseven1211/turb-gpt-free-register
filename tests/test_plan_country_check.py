"""验证独立套餐查询按国家执行、落库与失败隔离。"""
from types import SimpleNamespace
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from core import plan_check_service, record_store
from core.chatgpt_plan import parse_accounts_check
from core.operation_runtime import OperationCancelled
from core.storage import accounts as db
from core import admin_repository
from tests.support_pg import PostgresTestCase


def offer_result(country, percentage=0):
    campaigns = {} if not percentage else {"plus": {"id": f"offer-{country}", "metadata": {
        "discount": {"percentage": percentage},
        "duration": {"num_periods": 1, "period": "month"},
    }}}
    result = parse_accounts_check({"accounts": {"default": {
        "account": {"plan_type": "free"}, "eligible_promo_campaigns": campaigns,
    }}})
    return {**result, "http_status": 200}


class CountryPlanCheckTests(PostgresTestCase):
    def setUp(self):
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "country-plan@example.test", "access_token": "synthetic-token",
            "plan_check_status": "queued", "current_plan_type": "free",
        })
        self.context = SimpleNamespace(checkpoint=Mock(), report=Mock(return_value={}), finish=Mock())
        self.routes = []

    def execute(self, answers, countries=None, *, mismatch=None, trigger="manual"):
        def acquire(**kwargs):
            country = kwargs.get("region") or "JP"
            answer = answers[country]
            if isinstance(answer, BaseException):
                raise answer
            route = SimpleNamespace(
                proxy_url=country, region=mismatch or country,
                public_dict=lambda: {"proxy_region": mismatch or country, "proxy_provider": "1024proxy", "network_route": "proxy"},
                release=Mock(),
            )
            self.routes.append(route)
            return route

        def query(token, **kwargs):
            return dict(answers[kwargs["proxy"]])

        with (
            patch("core.account_proxy.acquire_account_proxy", side_effect=acquire),
            patch.object(plan_check_service, "check_account_plan", side_effect=query),
            patch.object(plan_check_service, "_wait_for_rate_slot"),
            patch.object(plan_check_service, "_log_plan_result"),
        ):
            return plan_check_service._run_plan_check(
                account_id=self.account_id, email="country-plan@example.test",
                access_token="synthetic-token", trigger=trigger, proxy=None,
                timezone_offset_min="-", operation_context=self.context,
                config_snapshot={"country_wait_timeout": 5, "route_source": "provider:1024proxy"},
                countries=countries if countries is not None else ["JP", "VN", "IN"],
            )

    def test_country_offers_are_saved_separately_and_best_is_aggregated(self):
        result = self.execute({"JP": offer_result("JP"), "VN": offer_result("VN", 100), "IN": offer_result("IN", 50)})
        account = db.get_account(self.account_id)
        self.assertTrue(result["ok"])
        self.assertFalse(account["plan_check_partial"])
        self.assertEqual(["JP", "VN", "IN"], account["plan_check_countries"])
        self.assertEqual(["success"] * 3, [r["status"] for r in account["plan_check_country_results"]])
        self.assertEqual("free_trial", account["plus_promo_kind"])
        self.assertEqual("offer-VN", account["plus_promo_campaign_id"])
        self.assertEqual({"JP", "VN", "IN"}, {p["country"] for p in account["account_promotions"]})
        self.assertTrue(all(route.release.call_count == 1 for route in self.routes))

    def test_country_supply_failure_continues_and_keeps_its_previous_offer(self):
        self.execute({"JP": offer_result("JP", 100)}, ["JP"])
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id))
        result = self.execute({"JP": TimeoutError("该国库存暂缺"), "VN": offer_result("VN"), "IN": offer_result("IN", 50)})
        rows = db.get_account(self.account_id)["plan_check_country_results"]
        self.assertTrue(result["ok"])
        self.assertTrue(result["plan_check_partial"])
        self.assertEqual(["failed", "success", "success"], [r["status"] for r in rows])
        self.assertEqual("free_trial", rows[0]["result"]["plus_promo_kind"])
        self.assertTrue(rows[0]["last_success_at"])
        self.assertEqual(2, result["country_success_count"])
        self.assertIn("JP", result["failed_countries"])
        self.assertEqual("partial_success", self.context.finish.call_args.kwargs["status"])

    def test_all_countries_fail_without_clearing_successful_snapshots(self):
        self.execute({"JP": offer_result("JP", 100)}, ["JP"])
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id))
        result = self.execute({"JP": TimeoutError("库存暂缺"), "VN": {"ok": False, "http_status": 403, "error": "HTTP 403"}}, ["JP", "VN"])
        account = db.get_account(self.account_id)
        self.assertFalse(result["ok"])
        self.assertIsNone(result.get("http_status"))
        self.assertEqual("failed", account["plan_check_status"])
        self.assertEqual("free_trial", account["plus_promo_kind"])
        self.assertEqual("failed", account["plan_check_country_results"][1]["status"])
        self.assertIsNone(account["plan_check_country_results"][1].get("result"))

    def test_mismatched_exit_is_failed_instead_of_labelled_as_target_country(self):
        result = self.execute({"VN": offer_result("VN", 100)}, ["VN"], mismatch="JP")
        row = db.get_account(self.account_id)["plan_check_country_results"][0]
        self.assertFalse(result["ok"])
        self.assertEqual("failed", row["status"])
        self.assertIsNone(row.get("result"))
        self.assertIn("JP", row["error"])
        self.assertEqual(1, self.routes[0].release.call_count)

    def test_completed_country_is_durable_when_next_country_is_cancelled(self):
        result = self.execute({"JP": offer_result("JP", 100), "VN": OperationCancelled("测试取消"), "IN": offer_result("IN")})
        rows = db.get_account(self.account_id)["plan_check_country_results"]
        self.assertEqual("cancelled", result["status"])
        self.assertEqual(["success", "cancelled", "cancelled"], [r["status"] for r in rows])
        self.assertEqual("free_trial", rows[0]["result"]["plus_promo_kind"])

    def test_public_country_evidence_excludes_credentials_and_raw_responses(self):
        answer = offer_result("JP", 100)
        answer.update({"access_token": "secret-value", "email": "private@example.test", "raw_response": {"cookie": "private"}})
        answer["account_promotions"][1]["access_token"] = "nested-secret"
        self.execute({"JP": answer}, ["JP"])
        from webui.route_helpers import _compact_account_for_list
        # 实际的列表投影必须仍经过白名单边界。
        public = _compact_account_for_list(db.get_account(self.account_id))
        evidence = str(public.get("plan_check_country_results"))
        self.assertIn("JP", evidence)
        self.assertNotIn("secret-value", evidence)
        self.assertNotIn("nested-secret", evidence)
        self.assertNotIn("private@example.test", evidence)
        self.assertNotIn("cookie", evidence)
        polling = admin_repository.list_account_statuses(admin_repository.PageRequest())
        self.assertEqual(["JP"], polling["items"][0]["plan_check_countries"])
        self.assertEqual("JP", polling["items"][0]["plan_check_country_results"][0]["country"])

    def test_restart_marks_only_unfinished_country_results_failed(self):
        from core.storage import plan_countries
        plan_countries.begin_country_checks(self.account_id, ["JP", "VN", "IN"])
        plan_countries.record_country_result(self.account_id, "JP", offer_result("JP", 100))
        plan_countries.set_country_running(self.account_id, "VN")
        self.assertEqual(1, db.recover_interrupted_plan_checks())
        account = db.get_account(self.account_id)
        self.assertEqual(["success", "failed", "failed"], [r["status"] for r in account["plan_check_country_results"]])
        self.assertEqual("free_trial", account["plan_check_country_results"][0]["result"]["plus_promo_kind"])

    def test_queued_country_list_is_frozen_and_registration_tasks_stay_single(self):
        submitted = []
        from config.schema import ConfigSnapshot
        snapshot = ConfigSnapshot({
            "PLAN_CHECK_COUNTRIES": ["JP", "VN", "IN"],
            "ACCOUNT_PLAN_CHECK_PROXY_MODE": "provider:1024proxy",
            "PLAN_CHECK_COUNTRY_WAIT_TIMEOUT": 60,
        }, {"ACCOUNT_PLAN_CHECK_PROXY_MODE": "env"}, revision=7)
        with (
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_COUNTRIES", ["JP", "VN", "IN"]),
            patch.object(plan_check_service, "get_config_snapshot", return_value=snapshot),
            patch.object(plan_check_service, "register_operation_handlers"),
            patch.object(plan_check_service.account_task_store, "submit_durable_operation", side_effect=lambda **kw: submitted.append(kw) or {}),
        ):
            for trigger in ["manual", "registration_auto", "registration_retry_plan_check"]:
                plan_check_service._submit_native_plan(
                    account_id=self.account_id, email="country-plan@example.test", trigger=trigger,
                    timezone_offset_min="-", batch_id=None, idempotency_key=None,
                )
            plan_check_service.proxy_cfg.PLAN_CHECK_COUNTRIES.append("US")
        self.assertEqual(["JP", "VN", "IN"], submitted[0]["data"]["countries"])
        self.assertIs(snapshot, submitted[0]["config_snapshot"])
        self.assertEqual("pool", submitted[0]["data"]["proxy_source"])
        self.assertNotIn("countries", submitted[1]["data"])
        self.assertNotIn("countries", submitted[2]["data"])

    def test_registration_execution_ignores_multi_country_request(self):
        result = self.execute({"JP": offer_result("JP", 100)}, trigger="registration_retry_plan_check")
        self.assertTrue(result["ok"])
        self.assertEqual(1, len(self.routes))
        self.assertNotIn("plan_check_country_results", db.get_account(self.account_id))

    def test_empty_country_config_returns_to_single_query_without_inventing_country(self):
        self.execute({"JP": offer_result("JP", 100)}, ["JP"])
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id))
        result = self.execute({"JP": offer_result("JP")}, [])
        account = db.get_account(self.account_id)
        self.assertTrue(result["ok"])
        self.assertEqual([], account["plan_check_countries"])
        self.assertEqual("none", account["plus_promo_kind"])

    def test_failed_current_request_keeps_token_expiration_evidence_separate_from_history(self):
        self.execute({"JP": offer_result("JP", 100)}, ["JP"])
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id))
        self.execute({"JP": {"ok": False, "http_status": 401, "token_expired": True, "error": "AT已失效"}}, ["JP"])
        account = db.get_account(self.account_id)
        self.assertTrue(account["token_expired"])
        self.assertEqual("free_trial", account["plan_check_country_results"][0]["result"]["plus_promo_kind"])

    def test_retry_without_response_does_not_reuse_previous_token_expiration_evidence(self):
        self.execute({"JP": {"ok": False, "http_status": 401, "token_expired": True,
                             "token_expires_at": "2026-10-01T00:00:00", "error": "AT已失效"}}, ["JP"])
        self.assertTrue(db.claim_account_plan_check(acc_id=self.account_id))
        result = self.execute({"JP": TimeoutError("该国库存暂缺")}, ["JP"])
        row = db.get_account(self.account_id)["plan_check_country_results"][0]
        self.assertFalse(result.get("token_expired"))
        self.assertNotIn("token_expired", row)
        self.assertNotIn("token_expires_at", row)
        self.assertIn("库存暂缺", row["error"])

    def test_frozen_country_deadline_prevents_120_second_false_stale_and_duplicate_claim(self):
        record_store.patch_row(record_store.ACCOUNTS, self.account_id, {
            "plan_check_status": "running",
            "plan_check_started_at": (datetime.now() - timedelta(seconds=180)).isoformat(timespec="seconds"),
            "plan_check_deadline_at": (datetime.now() + timedelta(seconds=300)).isoformat(timespec="seconds"),
        })
        self.assertEqual("running", db.get_account(self.account_id)["plan_check_status"])
        self.assertFalse(db.claim_account_plan_check(acc_id=self.account_id))
        record_store.patch_row(record_store.ACCOUNTS, self.account_id, {
            "plan_check_deadline_at": (datetime.now() - timedelta(seconds=1)).isoformat(timespec="seconds"),
        })
        polling = admin_repository.list_account_statuses(admin_repository.PageRequest())
        self.assertEqual("failed", polling["items"][0]["plan_check_status"])

    def test_old_execution_cannot_overwrite_country_or_summary_after_owner_changes(self):
        from core.storage import operation, plan_countries
        from core import postgres_store
        operation.init()
        task = operation.create_runtime_task(task_type="plan_check", account_id=self.account_id, email="country-plan@example.test", trigger="test_fence")
        run_id = int(task["run"]["id"])
        self.assertIsNotNone(operation.claim_run(run_id, execution_id="old-worker", worker_pid=1))
        token = operation.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        fence = {"run_id": run_id, "execution_id": "old-worker", "lease_token": token}
        plan_countries.begin_country_checks(self.account_id, ["JP"], fence=fence)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET execution_id=%s WHERE id=%s", ("new-worker", run_id))
        with self.assertRaises(plan_check_service.account_task_store.OperationLeaseLost):
            plan_countries.record_country_result(self.account_id, "JP", offer_result("JP", 100), fence=fence)
        with self.assertRaises(plan_check_service.account_task_store.OperationLeaseLost):
            plan_countries.save_country_summary(self.account_id, {"ok": True, "plus_promo_kind": "free_trial"}, fence=fence)
        account = db.get_account(self.account_id)
        self.assertEqual("queued", account["plan_check_country_results"][0]["status"])
        self.assertIsNone(account["plan_check_country_results"][0]["result"])

    def test_native_run_and_retry_execute_frozen_countries_with_real_lease_fence(self):
        from core.storage import operation
        from core.operations import task_gateway
        task_gateway.init()
        plan_check_service.register_operation_handlers()
        task = operation.create_runtime_task(
            task_type="plan_check", account_id=self.account_id, email="country-plan@example.test",
            trigger="manual", data={"countries": ["JP", "VN"], "proxy_source": "provider:1024proxy"},
        )

        def acquire(**kwargs):
            country = kwargs["region"]
            return SimpleNamespace(proxy_url=country, region=country,
                                   public_dict=lambda: {"proxy_region": country, "proxy_provider": "1024proxy"}, release=Mock())

        with (
            patch("core.account_proxy.acquire_account_proxy", side_effect=acquire),
            patch.object(plan_check_service, "check_account_plan", side_effect=lambda token, **kw: offer_result(kw["proxy"], 100 if kw["proxy"] == "VN" else 0)),
            patch.object(plan_check_service, "_wait_for_rate_slot"),
        ):
            first = task_gateway._execute_operation_handler("plan_check", int(task["run"]["id"]))
            self.assertEqual("success", first["status"])
            first_run = operation.get_run(int(task["run"]["id"]))
            self.assertEqual(2, first_run["result_summary"]["country_success_count"])
            retry = operation.retry_runtime_task(int(task["id"]))
            self.assertEqual(["JP", "VN"], retry["data"]["countries"])
            second = task_gateway._execute_operation_handler("plan_check", int(retry["id"]))
        self.assertEqual("success", second["status"])
        self.assertEqual(["JP", "VN"], db.get_account(self.account_id)["plan_check_countries"])
        self.assertEqual(first_run["result_summary"], operation.get_run(int(task["run"]["id"]))["result_summary"])
        self.assertNotIn("lease_token", str(first_run["result_summary"]))
