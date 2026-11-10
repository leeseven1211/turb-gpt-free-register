"""批量 AT 刷新沿用既有认证与回执边界，仅在独立 schema 使用合成材料。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import uuid

from core.accounts.liveness import service as live_service
from core.bulk_operations import adapters, catalog, results, service
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import bulk, store
from tests.support_pg import PostgresTestCase


class TokenRefreshResultTests(TestCase):
    def evidence(self):
        return {"run": {"status": "success", "data": {"force_refresh": True,
            "remote_intent": {"action": "token_refresh", "receipt_state": "confirmed"}},
            "result_summary": {"ok": True, "status": "live", "validation_method": "authenticated_session",
                "token_refresh_driver": "protocol_v2", "protocol_version": "v2", "token_expired": False}}}

    def test_only_current_refresh_confirmed_receipt_counts_success(self):
        value = results.project_one(self.evidence(), operation_key="token_refresh")
        self.assertEqual(value["state"], "success")
        self.assertEqual(value["result"]["refresh_outcome"], "success")
        self.assertEqual(value["contribution"]["dimensions"], {"account.token_refresh.confirmed": 1})

    def test_success_without_refresh_or_confirmed_writeback_is_attention(self):
        variants = [{"force_refresh": False}, {"force_refresh": None},
                    {"remote_intent": {"action": "other_action", "receipt_state": "confirmed"}},
                    {"remote_intent": {"action": "token_refresh", "receipt_state": "local_commit_required"}}]
        for change in variants:
            with self.subTest(change=change):
                evidence = self.evidence()
                evidence["run"]["data"].update(change)
                value = results.project_one(evidence, operation_key="token_refresh")
                self.assertEqual(value["state"], "attention_required")
                self.assertEqual(value["reason"]["code"], "refresh_confirmation_missing")
                self.assertNotIn("account.token_refresh.confirmed", value["contribution"]["dimensions"])
        for change in ({"ok": False}, {"validation_method": "access_token"}, {"reconcile_required": True}, {"manual_reconcile": True}):
            with self.subTest(change=change):
                evidence = self.evidence()
                evidence["run"]["result_summary"].update(change)
                self.assertEqual(results.project_one(evidence, operation_key="token_refresh")["state"], "attention_required")

    def test_pending_failure_cancel_and_unknown_do_not_reuse_cached_success(self):
        for status, outcome, dimensions in (("queued", "pending", {}), ("running", "pending", {}),
                ("cancelled", "not_executed", {}), ("not_executed", "not_executed", {}),
                ("failed", "failed", {"account.token_refresh.failed": 1}),
                ("request_unknown", "unconfirmed", {"account.token_refresh.unconfirmed": 1})):
            with self.subTest(status=status):
                evidence = self.evidence()
                evidence["run"]["status"] = status
                evidence["run"]["result_summary"]["access_token"] = "private-test-token"
                value = results.project_one(evidence, operation_key="token_refresh")
                self.assertEqual(value["result"]["refresh_outcome"], outcome)
                self.assertEqual(value["contribution"]["dimensions"], dimensions)
                self.assertNotIn("private-test-token", str(value))

    def test_catalog_freezes_live_settings_and_checks_local_availability(self):
        captured = {"revision": 71, "values": {"ACCOUNT_AT_REFRESH_DRIVER": "protocol",
            "OPENAI_PROTOCOL_VERSION": "v2", "ACCOUNT_AT_REFRESH_COUNTRY": "JP", "ACCOUNT_REFRESH_AT_PROXY_MODE": "pool",
            "ACCOUNT_AT_REFRESH_NETWORK_RETRIES": 2, "LIVE_CHECK_ROXY_FALLBACK_ENABLED": False,
            "EMAIL_BUTLER_API_KEY": "private-key"}}
        with patch("config.schema.non_sensitive_snapshot", return_value=captured), \
                patch.object(live_service, "deployment_unavailable", return_value=None) as deployment, \
                patch("core.proxy.account_routes.proxy_configuration_status", return_value={"ok": True}) as proxy:
            settings = catalog.capture_settings("token_refresh")
        self.assertEqual(settings["config_revision"], "71")
        self.assertEqual(settings["config_snapshot"]["refresh_protocol_version"], "v2")
        self.assertEqual(settings["config_snapshot"]["refresh_at_country"], "JP")
        self.assertNotIn("private-key", str(settings))
        self.assertTrue(deployment.call_args.kwargs["force_refresh"])
        proxy.assert_called_once_with("token-refresh")
        with patch.object(live_service, "deployment_unavailable", return_value=None), \
                patch("core.proxy.account_routes.proxy_configuration_status", return_value={"ok": False, "reason": "test proxy missing"}):
            self.assertFalse(catalog.capture_settings("token_refresh")["availability"]["available"])
        with patch.object(catalog, "capture_settings", return_value=settings):
            operation = next(value for value in catalog.catalog()["operations"] if value["key"] == "token_refresh")
        self.assertEqual(operation["label"], "刷新 AT")
        self.assertEqual(operation["result_panel"], "token_refresh")


class TokenRefreshStoreTests(PostgresTestCase):
    def setUp(self):
        from core.storage.operations import legacy_task_store
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        bulk.reset_ready()
        bulk.init()
        task_gateway.init()
        live_service.register_operation_handlers()
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch.object(live_service, "deployment_unavailable", return_value=None))
        self.stack.enter_context(patch.object(live_service, "_append_log"))
        self.ids = self.seed(records.ACCOUNTS, [{"email": f"at-bulk-{index}@example.test", "access_token": "old-synthetic-at",
            "account_status": "active", "email_source": "cloudflare", "registration_proxy_region": "JP"} for index in range(1, 5)])
        self.snapshot = {"config_snapshot_revision": 71, "refresh_driver": "protocol", "refresh_protocol_version": "v2",
            "refresh_at_country": "JP", "refresh_at_proxy_mode": "pool", "roxy_fallback_enabled": False,
            "network_retry_limit": 0, "network_timeout_seconds": 30}
        self.stack.enter_context(patch("core.bulk_operations.catalog.capture_settings", return_value={
            "config_revision": "71", "config_snapshot": self.snapshot, "effective_settings": self.snapshot,
            "parameters": {}, "availability": {"available": True}}))

    def make_batch(self, ids=None):
        selected = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": ids or self.ids[:1]},
            operation_key="token_refresh", config_revision="71", config_snapshot=self.snapshot)
        selected = bulk.freeze_selection(selected["id"])
        return bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selected["id"], selection_revision=1,
            operation_key="token_refresh", parameters={}, config_revision="71", max_concurrency=3)

    def submit(self, batch):
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)
        row = bulk.list_targets(batch["id"])["items"][0]
        return row["run_id"], row["task_id"]

    def run_mocked_refresh(self, run_id, response):
        route = SimpleNamespace(proxy_url="http://192.0.2.10:8080", release=Mock(), public_dict=lambda: {
            "network_route": "proxy", "proxy_provider": "fixture", "proxy_region": "JP", "proxy_used": True})
        def refresh(_email, **kwargs):
            kwargs["on_remote_request_started"]()
            return dict(response)
        with patch("core.proxy.account_routes.acquire_account_proxy", return_value=route), \
                patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=refresh), \
                patch("core.accounts.liveness.protocol.legacy.check_account_liveness", side_effect=AssertionError("不能验证旧AT替代刷新")):
            return task_gateway._execute_operation_handler("token_refresh", run_id)

    def test_submission_freezes_driver_and_claims_live_projection_atomically(self):
        batch = self.make_batch()
        run_id, _task_id = self.submit(batch)
        run = store.get_run(run_id)
        self.assertEqual(run["task_type"], "token_refresh")
        self.assertEqual(run["resource_family"], "openai_interactive")
        self.assertTrue(run["data"]["force_refresh"])
        self.assertEqual(run["data"]["refresh_driver"], "v2")
        self.assertEqual(run["data"]["config_snapshot"]["config_snapshot_revision"], 71)
        self.assertNotIn("old-synthetic-at", str(run))
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["live_check_status"], "queued")

    def test_submission_rollback_leaves_no_run_or_live_stage(self):
        batch = self.make_batch()
        bulk.materialize_targets(batch["id"])
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with store._connect() as conn:
                target = bulk.list_targets(batch["id"])["items"][0]
                adapters.submit_chunk(conn, [{"target_round_id": target["target_round_id"], "account_id": self.ids[0]}],
                    {"operation_key": "token_refresh", "batch_id": batch["id"], "config_snapshot": self.snapshot})
                raise RuntimeError("rollback")
        self.assertNotEqual(records.get_row(records.ACCOUNTS, self.ids[0]).get("live_check_status"), "queued")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_hundred_refresh_targets_use_bounded_domain_sql(self):
        from psycopg import Cursor
        ids = self.seed(records.ACCOUNTS, [{"email": f"at-bounded-{index}@example.test", "access_token": "old-synthetic-at"}
            for index in range(100)])
        targets = [{"target_round_id": 1000 + index, "account_id": account_id} for index, account_id in enumerate(ids)]
        statements = []
        execute = Cursor.execute
        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)
        with patch.object(Cursor, "execute", measured), store._connect() as conn:
            receipts = adapters.submit_chunk(conn, targets, {"operation_key": "token_refresh", "batch_id": 900,
                "config_snapshot": self.snapshot, "parameters": {}})
        self.assertEqual(len(receipts), 100)
        self.assertEqual({value["disposition"] for value in receipts}, {"created"})
        self.assertLessEqual(len(statements), 12, f"实际SQL {len(statements)}")

    def test_http_catalog_to_fixed_selection_and_batch_acceptance(self):
        from webui.app import create_app
        client = create_app(auth_code="bulk-at-test").test_client()
        headers = {"X-Auth-Code": "bulk-at-test"}
        response = client.get("/api/bulk/catalog", headers=headers)
        entry = next(value for value in response.json["data"]["operations"] if value["key"] == "token_refresh")
        self.assertEqual(entry["label"], "刷新 AT")
        headers["Idempotency-Key"] = uuid.uuid4().hex
        response = client.post("/api/bulk/selections", headers=headers, json={"operation": {"key": "token_refresh", "version": 1},
            "source": {"kind": "ids", "ids": [str(self.ids[0])]}, "parameters": {}, "expected_config_revision": "71"})
        self.assertEqual(response.status_code, 202, response.json)
        selected_id = response.json["data"]["id"]
        service.run_once("selection")
        selected = client.get(f"/api/bulk/selections/{selected_id}", headers=headers).json["data"]
        self.assertEqual(selected["preflight"]["ready"], 1)
        headers["Idempotency-Key"] = uuid.uuid4().hex
        response = client.post("/api/bulk/batches", headers=headers, json={"operation": {"key": "token_refresh", "version": 1},
            "selection_id": selected_id, "selection_revision": selected["selection_revision"], "parameters": {},
            "expected_config_revision": "71", "execution": {"max_concurrency": 2}})
        self.assertEqual(response.status_code, 202, response.json)
        batch_id = response.json["data"]["id"]
        service.run_once("expand")
        detail = client.get(f"/api/bulk/batches/{batch_id}", headers=headers).json["data"]
        self.assertEqual(detail["action_key"], "token_refresh")
        self.assertNotIn("old-synthetic-at", str(detail))

    def test_cancel_before_start_releases_only_its_projection_and_can_retry_immediately(self):
        batch = self.make_batch()
        run_id, task_id = self.submit(batch)
        command = bulk.request_control(batch["id"], request_key="cancel-at-first", action="cancel_not_started", expected_control_revision=1)
        bulk.settle_control(command["id"])
        bulk.project_pending()
        self.assertEqual(store.get_run(run_id)["status"], "cancelled")
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["live_check_status"], "cancelled")
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["cancelled"], 1)
        receipt = service.retry_managed_task(task_id, request_key="retry-cancelled-at")
        bulk.freeze_round(int(receipt["round_id"]))
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["live_check_status"], "queued")
        # 第二轮也需保留精确stage标识，不可被通用retry的秒级时间覆盖。
        current = bulk.get_batch(batch["id"])
        command = bulk.request_control(batch["id"], request_key="cancel-at-second", action="cancel_not_started",
            expected_control_revision=current["control_revision"])
        bulk.settle_control(command["id"])
        bulk.project_pending()
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["live_check_status"], "cancelled")
        again = service.retry_managed_task(task_id, request_key="retry-cancelled-at-second")
        bulk.freeze_round(int(again["round_id"]))
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)

    def test_old_cancel_does_not_clear_a_newer_account_stage(self):
        batch = self.make_batch()
        run_id, _task_id = self.submit(batch)
        records.patch_row(records.ACCOUNTS, self.ids[0], {"live_check_queued_at": "2099-01-01T00:00:00", "live_check_trigger": "manual_bulk"})
        store.request_run_cancel(run_id)
        account = records.get_row(records.ACCOUNTS, self.ids[0])
        self.assertEqual(account["live_check_status"], "queued")
        self.assertEqual(account["live_check_queued_at"], "2099-01-01T00:00:00")

    def test_narrow_preflight_matches_refresh_material_and_busy_rules(self):
        records.patch_row(records.ACCOUNTS, self.ids[1], {"access_token": ""})
        records.patch_row(records.ACCOUNTS, self.ids[2], {"account_status": "deactivated"})
        store.create_runtime_task(task_type="plan_check", account_id=self.ids[3], email="at-bulk-4@example.test")
        targets = [{"id": index + 100, "account_id": account} for index, account in enumerate(self.ids)]
        context = {"operation_key": "token_refresh", "config_snapshot": self.snapshot}
        with store._connect() as conn:
            expected = adapters.prepare_many(targets, context=context, conn=conn)
            with patch.object(records, "list_rows", side_effect=AssertionError("预检不能加载完整账号")):
                actual = adapters.prepare_many(targets, context=context, conn=conn, preflight_only=True)
        self.assertEqual([(value["disposition"], value["reason_code"]) for value in expected],
                         [(value["disposition"], value["reason_code"]) for value in actual])
        self.assertEqual([value["reason_code"] for value in actual], [None, "access_token_missing", "account_deactivated", "account_busy"])
        self.assertNotIn("old-synthetic-at", str(actual))

    def test_real_handler_confirms_writeback_and_round_projection(self):
        batch = self.make_batch()
        run_id, task_id = self.submit(batch)
        result = self.run_mocked_refresh(run_id, {"ok": True, "status": "live", "access_token": "fresh-synthetic-at",
            "validation_method": "authenticated_session", "live_check_driver": "protocol_v2", "auth_method": "email_otp",
            "session": {"account": {"planType": "free"}}, "roxy_fallback_allowed": False})
        self.assertEqual(result["status"], "success")
        self.assertEqual(store.get_run(run_id)["data"]["remote_intent"]["receipt_state"], "confirmed")
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["access_token"], "fresh-synthetic-at")
        bulk.project_pending()
        detail = bulk.get_batch(batch["id"])
        self.assertEqual(detail["counts"]["success"], 1)
        self.assertEqual(detail["metrics"]["account.token_refresh.confirmed"], 1)
        self.assertNotIn("fresh-synthetic-at", str(bulk.list_targets(batch["id"])))
        # 批量人工重跑继续使用同一Task、新Run，冻结设置保持原轮配置。
        receipt = service.retry_managed_task(task_id, request_key="token-refresh-owned-retry")
        bulk.freeze_round(int(receipt["round_id"]))
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,data FROM {store._table('operation_runs')} WHERE task_id=%s ORDER BY run_no DESC", (task_id,))
            rows = list(cur.fetchall())
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["data"]["force_refresh"])
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["live_check_status"], "queued")

    def test_unknown_remote_result_preserves_prior_token_and_counts_unconfirmed(self):
        batch = self.make_batch()
        run_id, _task_id = self.submit(batch)
        self.run_mocked_refresh(run_id, {"ok": False, "status": "failed", "error": "response_missing",
            "error_code": "request_unknown", "reconcile_required": True, "mutation_submitted": True,
            "live_check_driver": "protocol_v2", "roxy_fallback_allowed": False})
        bulk.project_pending()
        detail = bulk.get_batch(batch["id"])
        self.assertEqual(detail["counts"]["attention_required"], 1)
        self.assertEqual(detail["metrics"]["account.token_refresh.unconfirmed"], 1)
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["access_token"], "old-synthetic-at")
