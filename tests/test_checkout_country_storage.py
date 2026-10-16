"""验证逐国支付预检随活动落库、公开投影及执行隔离。"""
from copy import deepcopy
import json

from core import record_store
from core.chatgpt_plan import parse_accounts_check
from core.operations.task_gateway import OperationLeaseLost
from core.plan_check_countries import aggregate_country_results
from core.storage import accounts, operation, plan_countries
from tests.support_pg import PostgresTestCase
from webui.app import create_app


def checkout_result(country, *, discount=100, session_type="oaics", methods=None, amount=0):
    result = parse_accounts_check({"accounts": {"default": {
        "account": {"plan_type": "free"}, "eligible_promo_campaigns": {
            "plus": {"id": f"plus-{country}", "metadata": {
                "discount": {"percentage": discount}, "duration": {"num_periods": 1, "period": "month"},
            }},
        },
    }}})
    details = {
        "checkout_status": "success", "checkout_checked_at": "2026-10-16T10:00:00",
        "checkout_http_status": 200, "session_type": session_type,
        "payment_method_types": methods or ["card", "link"], "checkout_amount_due_minor": amount,
        "checkout_currency": "JPY" if country == "JP" else "VND", "checkout_currency_exponent": 0,
        "checkout_amount_source": "invoice.amount_due", "checkout_source": "checkout", "checkout_country": country,
    }
    for item in [*result["account_promotions"], *result["promotion_query_snapshot"]["campaigns"]]:
        if item["plan"] == "plus":
            item.update(details)
    return {**result, "http_status": 200, "proxy_region": country}


class CheckoutCountryStorageTests(PostgresTestCase):
    def setUp(self):
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "checkout-country@example.test", "access_token": "fixture-account-token",
            "current_plan_type": "free", "plan_check_status": "queued",
        })

    def save(self, results):
        plan_countries.begin_country_checks(self.account_id, list(results))
        for country, result in results.items():
            rows = plan_countries.record_country_result(self.account_id, country, result)
        summary = aggregate_country_results(rows)
        self.assertTrue(plan_countries.save_country_summary(self.account_id, summary))
        return accounts.get_account(self.account_id)

    def plus(self, result):
        return next(item for item in result["account_promotions"] if item["plan"] == "plus")

    def test_country_checkout_fields_keep_arrays_zero_amount_and_discount_independent(self):
        account = self.save({
            "JP": checkout_result("JP"),
            "VN": checkout_result("VN", discount=50, session_type="cs_live", methods=["card", "upi"], amount=129500),
        })
        rows = {row["country"]: row for row in account["plan_check_country_results"]}
        jp, vn = self.plus(rows["JP"]["result"]), self.plus(rows["VN"]["result"])
        self.assertEqual(("free_trial", "oaics", ["card", "link"], 0, "JP"),
                         (jp["kind"], jp["session_type"], jp["payment_method_types"], jp["checkout_amount_due_minor"], jp["checkout_country"]))
        self.assertEqual(("discount", 50, "cs_live", ["card", "upi"], 129500, "VN"),
                         (vn["kind"], vn["discount_percentage"], vn["session_type"], vn["payment_method_types"], vn["checkout_amount_due_minor"], vn["checkout_country"]))
        for country, row in rows.items():
            self.assertEqual("success", row["status"])
            plus = self.plus(row["result"])
            campaign = next(item for item in row["result"]["promotion_query_snapshot"]["campaigns"] if item["plan"] == "plus")
            self.assertEqual(plus["payment_method_types"], campaign["payment_method_types"])
            self.assertEqual(country, campaign["checkout_country"])
            go = next(item for item in row["result"]["account_promotions"] if item["plan"] == "go")
            self.assertNotIn("checkout_status", go, "未预检的 Go 活动不能借用 Plus 支付信息")
        aggregated = {item["country"]: item for item in account["account_promotions"] if item["plan"] == "plus"}
        self.assertEqual(jp["payment_method_types"], aggregated["JP"]["payment_method_types"])
        self.assertEqual(vn["payment_method_types"], aggregated["VN"]["payment_method_types"])

    def test_payment_failure_preserves_confirmed_offer_in_storage_and_real_account_apis(self):
        self.save({"JP": checkout_result("JP")})
        failed = checkout_result("JP", discount=50)
        for item in [*failed["account_promotions"], *failed["promotion_query_snapshot"]["campaigns"]]:
            if item["plan"] == "plus":
                item.update({"checkout_status": "failed", "checkout_http_status": 403,
                             "checkout_error": "结账会话状态查询失败", "payment_method_types": [],
                             "checkout_amount_due_minor": None})
        self.save({"JP": failed})
        app = create_app(auth_code="checkout-country-test")
        client = app.test_client()
        for url in ("/api/accounts", "/api/accounts?paged=1&page=1&page_size=20", "/api/accounts/plan-check-status"):
            with self.subTest(url=url):
                response = client.get(url, headers={"X-Auth-Code": "checkout-country-test"})
                self.assertEqual(200, response.status_code)
                payload = response.get_json()
                account = payload["items"][0] if isinstance(payload, dict) else payload[0]
                self.assertEqual("success", account["plan_check_status"])
                self.assertEqual("discount", account["plus_promo_kind"])
                row = account["plan_check_country_results"][0]
                self.assertEqual("success", row["status"], "支付预检失败不能改写套餐查询成功")
                plus = self.plus(row["result"])
                self.assertEqual(("discount", 50, "failed", [], "结账会话状态查询失败"),
                                 (plus["kind"], plus["discount_percentage"], plus["checkout_status"], plus["payment_method_types"], plus["checkout_error"]))
                self.assertEqual("failed", self.plus(account)["checkout_status"])

    def test_raw_checkout_credentials_are_removed_before_persistence_and_public_projection(self):
        malicious = checkout_result("JP")
        raw = {"checkout_url": "https://checkout.example/private-path", "session_id": "cs_live_private-session",
               "client_secret": "fixture-client-private", "access_token": "fixture-upstream-private",
               "raw_response": {"secret": "fixture-nested-private"}}
        for item in [*malicious["account_promotions"], *malicious["promotion_query_snapshot"]["campaigns"]]:
            if item["plan"] == "plus":
                item.update(raw)
                item["payment_method_types"] += [raw["session_id"], raw["checkout_url"], raw["client_secret"]]
                item["checkout_error"] = raw["client_secret"]
                item["checkout_amount_source"] = raw["checkout_url"]
        malicious.update(raw)
        account = self.save({"JP": malicious})
        stored = json.dumps({key: account.get(key) for key in ("plan_check_country_results", "account_promotions", "promotion_query_snapshot", "plan_last_success_result_json")})
        for private in ("private-path", "private-session", "fixture-client-private", "fixture-upstream-private", "fixture-nested-private"):
            self.assertNotIn(private, stored)
        self.assertEqual(["card", "link"], self.plus(account)["payment_method_types"])
        app = create_app(auth_code="checkout-country-test")
        for url in ("/api/accounts", "/api/accounts/plan-check-status"):
            payload = app.test_client().get(url, headers={"X-Auth-Code": "checkout-country-test"}).get_json()
            public = json.dumps(payload)
            for private in ("private-path", "private-session", "fixture-client-private", "fixture-upstream-private", "fixture-nested-private", "fixture-account-token"):
                self.assertNotIn(private, public)

    def test_recovery_and_new_run_preserve_checkout_history_and_reject_old_fence(self):
        task = operation.create_runtime_task(task_type="plan_check", account_id=self.account_id,
                                             email="checkout-country@example.test", trigger="test_checkout_fence")

        def claim(run_id, owner):
            self.assertIsNotNone(operation.claim_run(run_id, execution_id=owner, worker_pid=1))
            lease = operation.acquire_account_lease(account_id=self.account_id, run_id=run_id)
            self.assertTrue(lease)
            return {"run_id": run_id, "execution_id": owner, "lease_token": lease}

        old = claim(int(task["run"]["id"]), "checkout-old")
        _, progress = plan_countries.initialize_country_checks(self.account_id, ["JP", "VN"], fence=old)
        plan_countries.update_country_progress(self.account_id, "JP", progress, action="result", result=checkout_result("JP"), fence=old)
        recovered, restored = plan_countries.initialize_country_checks(self.account_id, ["VN", "IN"], fence=old)
        self.assertEqual(["JP", "VN"], list(restored["countries"]), "恢复必须沿用原 Run 的国家快照")
        self.assertEqual("success", recovered[0]["status"])
        self.assertEqual("oaics", self.plus(recovered[0]["result"])["session_type"])
        operation.finish_run(old["run_id"], status="failed", execution_id=old["execution_id"], lease_token=old["lease_token"])
        operation.release_account_lease(old["run_id"], old["lease_token"])
        retry = operation.retry_runtime_task(int(task["id"]))
        current = claim(int(retry["id"]), "checkout-new")
        rows, _ = plan_countries.initialize_country_checks(self.account_id, ["JP", "VN"], fence=current)
        self.assertEqual(["queued", "queued"], [row["status"] for row in rows])
        self.assertEqual(["card", "link"], self.plus(rows[0]["result"])["payment_method_types"])
        rows = plan_countries.record_country_result(self.account_id, "VN", checkout_result("VN", discount=50, session_type="cs_live", methods=["card", "upi"], amount=129500), fence=current)
        self.assertTrue(plan_countries.save_country_summary(self.account_id, aggregate_country_results(rows), fence=current))
        before = deepcopy(accounts.get_account(self.account_id)["plan_check_country_results"])
        with self.assertRaises(OperationLeaseLost):
            plan_countries.record_country_result(self.account_id, "VN", checkout_result("VN"), fence=old)
        with self.assertRaises(OperationLeaseLost):
            plan_countries.save_country_summary(self.account_id, {"ok": True}, fence=old)
        self.assertEqual(before, accounts.get_account(self.account_id)["plan_check_country_results"])
