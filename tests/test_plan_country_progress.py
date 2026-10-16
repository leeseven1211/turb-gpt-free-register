"""验证国家等待切片、同 Run 恢复与请求次数的持久预算。"""
from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import chatgpt_plan, plan_check_service, record_store
from core.storage import operation, plan_countries
from tests.support_pg import PostgresTestCase
from tests.test_plan_country_check import offer_result


class CountryProgressTests(PostgresTestCase):
    def setUp(self):
        self.account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "progress@example.test", "access_token": "synthetic-token", "plan_check_status": "queued",
        })
        self.clock = datetime.now().timestamp()
        self.reporter = SimpleNamespace(stage=Mock(), note=Mock(), resource=Mock(), finish=Mock())

    def fence(self):
        task = operation.create_runtime_task(task_type="plan_check", account_id=self.account_id,
                                             email="progress@example.test", trigger="manual")
        run_id = int(task["run"]["id"])
        operation.claim_run(run_id, execution_id="test-worker", worker_pid=1)
        token = operation.acquire_account_lease(account_id=self.account_id, run_id=run_id)
        return {"run_id": run_id, "execution_id": "test-worker", "lease_token": token}

    def route(self, country):
        return SimpleNamespace(proxy_url=country, region=country, release=Mock(),
                               public_dict=lambda: {"proxy_region": country, "proxy_provider": "1024proxy"})

    def sleep(self, seconds):
        self.clock += seconds

    def execute(self, acquire, *, countries=None, fence=None, query=None, real_rate=False, context=None):
        with (
            patch("time.time", side_effect=lambda: self.clock),
            patch("time.monotonic", side_effect=lambda: self.clock),
            patch.object(plan_check_service.time, "sleep", side_effect=self.sleep),
            patch("core.account_proxy.acquire_account_proxy", side_effect=acquire),
            patch.object(plan_check_service, "check_account_plan", side_effect=query or (lambda token, **kw: offer_result(kw["proxy"]))),
            nullcontext() if real_rate else patch.object(plan_check_service, "_wait_for_rate_slot"),
        ):
            return plan_check_service._run_country_plan_checks(
                account_id=self.account_id, email="progress@example.test", access_token="synthetic-token",
                trigger="manual", proxy=None, timezone_offset_min="-", countries=countries or ["JP", "VN"],
                reporter=self.reporter, operation_context=context, config_snapshot={"country_wait_timeout": 60,
                "min_interval": 0, "jitter": 0,
                "plan_check_max_attempts": 2, "plan_check_retry_delay": 0}, proxy_source="provider:1024proxy", fence=fence,
            )

    def test_first_supply_slice_yields_to_next_country_then_retries_missing_country(self):
        # 若首国仍独占完整 60 秒等待，VN 的查询会晚于五秒，且 JP 没有公平补试。
        events = []
        def acquire(**kwargs):
            country = kwargs["region"]
            events.append((country, kwargs["timeout"], self.clock))
            if len(events) == 1:
                self.clock += kwargs["timeout"]
                raise TimeoutError("库存暂缺")
            return self.route(country)
        result = self.execute(acquire)
        self.assertEqual(["JP", "VN", "JP"], [item[0] for item in events])
        self.assertEqual(5, events[0][1])
        self.assertEqual(5, events[1][2] - events[0][2])
        self.assertEqual(2, result["country_success_count"])

    def test_same_run_resume_keeps_success_and_interrupted_wait_budget(self):
        # 若初始化重置已成功国家或未结算切片，恢复会多查 JP 或返还 VN 的 5 秒。
        fence = self.fence()
        seen = []
        def interrupted(**kwargs):
            seen.append(kwargs["region"])
            if kwargs["region"] == "VN":
                self.clock += 5
                raise KeyboardInterrupt()
            return self.route(kwargs["region"])
        with self.assertRaises(KeyboardInterrupt):
            self.execute(interrupted, fence=fence)
        def resume(**kwargs):
            seen.append(kwargs["region"])
            self.clock += kwargs["timeout"]
            raise TimeoutError("库存暂缺")
        self.execute(resume, fence=fence)
        progress = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]
        self.assertEqual(1, seen.count("JP"))
        self.assertEqual(60, progress["countries"]["VN"]["wait_used"])
        self.assertTrue(progress["countries"]["JP"]["success"])

    def test_transport_rotations_share_single_country_frozen_http_limit(self):
        # 若每条线路重新获得两次内部重试，则实际请求会超过冻结的两次。
        fence = self.fence()
        calls = []
        routes = []
        def acquire(**kwargs):
            route = self.route(kwargs["region"])
            routes.append(route)
            return route
        def query(token, **kwargs):
            calls.append(kwargs["max_attempts"])
            return {"ok": False, "retryable": True, "proxy_transport_failure": True,
                    "error": "TLS 连接失败", "attempt_count": 1}
        result = self.execute(acquire, countries=["JP"], fence=fence, query=query)
        self.assertEqual([1, 1], calls)
        self.assertFalse(result["ok"])
        self.assertEqual(2, len(routes))
        self.assertTrue(all(route.release.call_args.kwargs.get("fault") for route in routes))
        progress = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]
        self.assertEqual(2, progress["countries"]["JP"]["http_attempts"])
        self.assertEqual("TLS 连接失败", progress["countries"]["JP"]["history"][0]["error"])

    def test_failed_acquisition_settles_slice_and_does_not_leave_restart_reservation(self):
        # 普通选路错误已经收口，不能留下未结算切片供重启再次扣费。
        fence = self.fence()
        def acquire(**kwargs):
            self.clock += 1
            raise ValueError("所选来源不支持目标国家")
        self.execute(acquire, countries=["JP"], fence=fence)
        state = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]["countries"]["JP"]
        self.assertIsNone(state["wait_slice_started_at"])
        self.assertEqual(1, state["wait_used"])
        self.assertFalse(state["pending"])

    def test_explicit_http_failures_do_not_rotate_even_when_marked_retryable(self):
        for status in (401, 403, 429):
            with self.subTest(http_status=status):
                calls = []
                def query(token, **kwargs):
                    calls.append(kwargs["proxy"])
                    return {"ok": False, "retryable": True, "http_status": status, "error": f"HTTP {status}"}
                result = self.execute(lambda **kw: self.route(kw["region"]), countries=["JP"], query=query)
                self.assertEqual(["JP"], calls)
                self.assertFalse(result["ok"])
                self.assertEqual(status, record_store.get_row(record_store.ACCOUNTS, self.account_id)["plan_check_country_results"][0]["http_status"])

    def test_immediate_supply_failure_waits_between_slices_and_never_exceeds_sixty_seconds(self):
        events = []
        def acquire(**kwargs):
            events.append((self.clock, kwargs["timeout"]))
            raise TimeoutError("库存暂缺")
        self.execute(acquire, countries=["JP"])
        self.assertEqual(12, len(events))
        self.assertEqual(60, sum(item[1] for item in events))
        self.assertGreaterEqual(events[-1][0] - events[0][0], 55)

    def test_initialization_and_resumption_preserve_original_run_deadline(self):
        fence = self.fence()
        with patch("time.time", side_effect=lambda: self.clock):
            _, first = plan_countries.initialize_country_checks(self.account_id, ["JP"], fence=fence,
                                                               wait_seconds=60, max_attempts=2, budget_seconds=150)
            self.clock += 10
            _, second = plan_countries.initialize_country_checks(self.account_id, ["JP", "VN"], fence=fence,
                                                                wait_seconds=300, max_attempts=4, budget_seconds=999)
        self.assertEqual(first["deadline_at"], second["deadline_at"])
        self.assertEqual(60, second["wait_limit"])
        self.assertEqual(2, second["max_attempts"])
        self.assertEqual(["JP"], list(second["countries"]))

    def test_stale_execution_cannot_consume_budget_and_new_run_starts_independently(self):
        from core import postgres_store
        fence = self.fence()
        _, first = plan_countries.initialize_country_checks(self.account_id, ["JP"], fence=fence)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET execution_id=%s WHERE id=%s", ("replacement", fence["run_id"]))
        with self.assertRaises(plan_check_service.account_task_store.OperationLeaseLost):
            plan_countries.update_country_progress(self.account_id, "JP", first, action="http_start", fence=fence)
        unchanged = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]
        self.assertEqual(0, unchanged["countries"]["JP"]["http_attempts"])
        replacement = {**fence, "execution_id": "replacement"}
        plan_countries.update_country_progress(self.account_id, "JP", first, action="http_start", fence=replacement)
        operation.release_account_lease(run_id=fence["run_id"], lease_token=fence["lease_token"])
        operation.finish_run(fence["run_id"], status="failed", message="测试收口")
        retry = operation.retry_runtime_task(operation.get_run(fence["run_id"])["task_id"])
        retry_id = int(retry["id"])
        operation.claim_run(retry_id, execution_id="retry-worker", worker_pid=1)
        retry_token = operation.acquire_account_lease(account_id=self.account_id, run_id=retry_id)
        fresh_fence = {"run_id": retry_id, "execution_id": "retry-worker", "lease_token": retry_token}
        _, fresh = plan_countries.initialize_country_checks(self.account_id, ["JP"], fence=fresh_fence)
        self.assertEqual(0, fresh["countries"]["JP"]["http_attempts"])
        self.assertEqual(0, fresh["countries"]["JP"]["wait_used"])
        self.assertEqual(1, operation.get_run(fence["run_id"])["data"]["plan_country_progress"]["countries"]["JP"]["http_attempts"])

    def test_account_and_quota_requests_together_fit_remaining_run_deadline(self):
        # 套餐成功后还会调用一次额度接口，两个 timeout 不能各自取完整剩余期限。
        fence = self.fence()
        with patch("time.time", side_effect=lambda: self.clock):
            _, progress = plan_countries.initialize_country_checks(self.account_id, ["JP"], fence=fence, budget_seconds=120)
        self.clock += 112
        def query(token, **kwargs):
            self.clock += kwargs["timeout"] * 2
            return offer_result("JP")
        result = self.execute(lambda **kw: self.route(kw["region"]), countries=["JP"], fence=fence, query=query)
        self.assertTrue(result["ok"])
        self.assertLessEqual(self.clock, progress["deadline_at"])

    def prepare_near_deadline(self):
        fence = self.fence()
        with patch("time.time", side_effect=lambda: self.clock):
            _, progress = plan_countries.initialize_country_checks(
                self.account_id, ["JP"], fence=fence, budget_seconds=120,
            )
        self.clock += 112
        return fence, progress["deadline_at"]

    def execute_real_checker(self, fence, get, *, real_rate=False, context=None):
        env = SimpleNamespace(get=get, session=SimpleNamespace(close=lambda: None),
                              js_timezone_offset_min=lambda: "0")
        route = self.route("JP")
        route.proxy_url = "http://proxy.invalid:8080"
        with (
            patch.object(chatgpt_plan, "BrowserSession", return_value=env),
            patch.object(chatgpt_plan, "_common_headers", return_value={}),
            patch.object(chatgpt_plan, "_quota_headers", return_value={}),
        ):
            return self.execute(lambda **kw: route, countries=["JP"], fence=fence,
                                query=chatgpt_plan.check_account_plan, real_rate=real_rate, context=context)

    def response(self, url):
        payload = {"accounts": {"default": {"account": {"plan_type": "free"}}}} if "accounts/check" in url else {}
        return SimpleNamespace(status_code=200, text="{}", json=lambda: payload)

    def test_rate_wait_stops_at_original_deadline_without_http(self):
        # 共享限速槽在期限之后时，应在原期限收口，不持有线路继续睡完整个槽。
        fence, deadline = self.prepare_near_deadline()
        requests = []
        def get(url, **kwargs):
            requests.append(url)
            return self.response(url)
        with patch.object(plan_check_service, "_NEXT_REQUEST_AT", deadline + 4):
            result = self.execute_real_checker(fence, get, real_rate=True)
        self.assertFalse(result["ok"])
        self.assertEqual([], requests)
        self.assertLessEqual(self.clock, deadline)

    def test_rate_wait_checks_cancel_before_reserved_slot_arrives(self):
        # 限速等待中应每个短片段检查取消，不能直到共享槽到达才响应。
        fence, deadline = self.prepare_near_deadline()
        cancel_at = self.clock + 1
        def checkpoint(message):
            if self.clock >= cancel_at:
                raise plan_check_service.OperationCancelled("用户取消测试")
        with patch.object(plan_check_service, "_NEXT_REQUEST_AT", deadline + 4):
            with self.assertRaises(plan_check_service.OperationCancelled):
                self.execute_real_checker(fence, lambda *args, **kw: self.fail("取消后不应发起 HTTP"),
                                          real_rate=True, context=SimpleNamespace(checkpoint=checkpoint))
        self.assertLessEqual(self.clock, cancel_at + .25)

    def test_real_checker_deducts_http_start_transaction_latency(self):
        # http_start 事务耗时必须从两次真实 GET 的共享期限扣除。
        fence, deadline = self.prepare_near_deadline()
        actual_update = plan_countries.update_country_progress
        requests = []
        def update(*args, **kwargs):
            result = actual_update(*args, **kwargs)
            if kwargs["action"] == "http_start":
                self.clock += 3
            return result
        def get(url, **kwargs):
            requests.append(kwargs["timeout"])
            self.clock += kwargs["timeout"]
            return self.response(url)
        with patch.object(plan_countries, "update_country_progress", side_effect=update):
            result = self.execute_real_checker(fence, get)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(requests))
        self.assertLessEqual(self.clock, deadline)

    def test_expired_http_start_transaction_does_not_send_http(self):
        # 预占事务用尽原期限后，不应再用事务前取得的 timeout 发起请求。
        fence, deadline = self.prepare_near_deadline()
        actual_update = plan_countries.update_country_progress
        requests = []
        def update(*args, **kwargs):
            result = actual_update(*args, **kwargs)
            if kwargs["action"] == "http_start":
                self.clock = deadline + 1
            return result
        def get(url, **kwargs):
            requests.append(url)
            return self.response(url)
        with patch.object(plan_countries, "update_country_progress", side_effect=update):
            result = self.execute_real_checker(fence, get)
        self.assertFalse(result["ok"])
        self.assertEqual([], requests)

    def test_real_http_observes_running_country_in_account_and_run(self):
        # 实际 HTTP 开始后，账号行与 Run 预算行都必须表示 running。
        fence, _ = self.prepare_near_deadline()
        observed = []
        def get(url, **kwargs):
            account = record_store.get_row(record_store.ACCOUNTS, self.account_id)
            progress = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]
            observed.append((account["plan_check_country_results"][0]["status"],
                             progress["countries"]["JP"]["status"]))
            return self.response(url)
        result = self.execute_real_checker(fence, get)
        self.assertTrue(result["ok"])
        self.assertEqual([("running", "running"), ("running", "running")], observed)

    def test_real_checker_shares_deadline_after_response_parsing_delay(self):
        # 首次 GET 之后的解析耗时也必须扣除，第二次 GET 不能使用旧剩余额度。
        fence, deadline = self.prepare_near_deadline()
        requests = []
        def get(url, **kwargs):
            requests.append(kwargs["timeout"])
            self.clock += kwargs["timeout"]
            response = self.response(url)
            if "accounts/check" in url:
                actual_json = response.json
                def delayed_json():
                    self.clock += 3
                    return actual_json()
                response.json = delayed_json
            return response
        result = self.execute_real_checker(fence, get)
        self.assertTrue(result["ok"])
        self.assertEqual(2, len(requests))
        self.assertLessEqual(self.clock, deadline)

    def test_real_checker_does_not_report_success_after_deadline(self):
        # 即便底层 I/O 迟到返回 200，也不能在原 Run 期限以后记为成功。
        fence, deadline = self.prepare_near_deadline()
        def get(url, **kwargs):
            self.clock = deadline + 1
            return self.response(url)
        result = self.execute_real_checker(fence, get)
        self.assertFalse(result["ok"])

    def test_proxy_acquisition_deducts_wait_start_transaction_latency(self):
        # 切片保存后只剩一秒时，实际领取不能重新使用完整四秒切片。
        fence, deadline = self.prepare_near_deadline()
        self.clock += 4
        actual_update = plan_countries.update_country_progress
        observed = []
        def update(*args, **kwargs):
            result = actual_update(*args, **kwargs)
            if kwargs["action"] == "wait_start":
                self.clock += 3
            return result
        def acquire(**kwargs):
            observed.append((self.clock, kwargs["timeout"]))
            self.clock += kwargs["timeout"]
            raise TimeoutError("测试库存暂缺")
        with patch.object(plan_countries, "update_country_progress", side_effect=update):
            result = self.execute(acquire, countries=["JP"], fence=fence)
        self.assertFalse(result["ok"])
        self.assertEqual([(deadline - 1, 1)], observed)
        self.assertEqual(deadline, self.clock)
        state = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]["countries"]["JP"]
        self.assertEqual(4, state["wait_used"])
        self.assertIsNone(state["wait_slice_started_at"])

    def test_expired_wait_start_transaction_settles_without_acquiring(self):
        # 事务耗尽原 Run 期限时，结算切片并收口，不发起过期的线路领取。
        fence, deadline = self.prepare_near_deadline()
        self.clock += 4
        actual_update = plan_countries.update_country_progress
        requests = []
        def update(*args, **kwargs):
            result = actual_update(*args, **kwargs)
            if kwargs["action"] == "wait_start":
                self.clock = deadline
            return result
        def acquire(**kwargs):
            requests.append(kwargs["timeout"])
            self.clock += kwargs["timeout"]
            raise TimeoutError("测试库存暂缺")
        with patch.object(plan_countries, "update_country_progress", side_effect=update):
            result = self.execute(acquire, countries=["JP"], fence=fence)
        self.assertFalse(result["ok"])
        self.assertEqual([], requests)
        self.assertEqual(deadline, self.clock)
        state = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]["countries"]["JP"]
        self.assertEqual(4, state["wait_used"])
        self.assertIsNone(state["wait_slice_started_at"])
        self.assertFalse(state["pending"])

    def test_expired_slice_transaction_counts_wait_and_uses_next_slice(self):
        # 原 Run 尚有预算但首片段已耗尽时，先扣除五秒，再领取后续切片。
        fence = self.fence()
        actual_update = plan_countries.update_country_progress
        starts = []
        requests = []
        started_at = self.clock
        def update(*args, **kwargs):
            result = actual_update(*args, **kwargs)
            if kwargs["action"] == "wait_start":
                starts.append(self.clock)
                if len(starts) == 1:
                    self.clock += 5
            return result
        def acquire(**kwargs):
            requests.append((self.clock, kwargs["timeout"]))
            self.clock += kwargs["timeout"]
            raise TimeoutError("测试库存暂缺")
        with patch.object(plan_countries, "update_country_progress", side_effect=update):
            self.execute(acquire, countries=["JP"], fence=fence)
        self.assertEqual(12, len(starts))
        self.assertEqual(11, len(requests))
        self.assertEqual(60, self.clock - started_at)
        state = operation.get_run(fence["run_id"])["data"]["plan_country_progress"]["countries"]["JP"]
        self.assertEqual(60, state["wait_used"])
        self.assertIsNone(state["wait_slice_started_at"])
