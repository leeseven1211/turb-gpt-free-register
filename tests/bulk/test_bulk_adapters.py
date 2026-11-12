"""批量领域契约：只在隔离schema写入队列，不执行外部服务。"""
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import patch

from core.bulk_operations import adapters, catalog, results
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class BulkResultTests(TestCase):
    def test_active_query_has_no_failure_or_country_result(self):
        for status in ("queued", "running", "waiting", "pending_submit", "waiting_account"):
            with self.subTest(status=status):
                value = results.project_one({"run": {"status": status}}, operation_key="plan_check")
                self.assertEqual(value["result"]["query_outcome"], "pending")
                self.assertEqual(value["contribution"]["dimensions"], {})

    def test_success_requires_current_operation_confirmation(self):
        for key in catalog.OPERATIONS:
            with self.subTest(key=key):
                value = results.project_one({"run": {"status": "success"}}, operation_key=key)
                self.assertEqual(value["state"], "failed")
                self.assertTrue(value["reason"]["code"].endswith("missing"))

    def test_setup_receipt_list_is_confirmed_without_guessing_change_kind(self):
        value = results.project_one({"run": {"status": "success", "result_summary": {
            "setup_step_receipts": [{"step": "password", "ok": True, "receipt_state": "confirmed"}]}}},
            operation_key="password_setup")
        self.assertEqual(value["state"], "success")
        self.assertEqual(value["result"]["confirmation"], "confirmed")
        self.assertEqual(value["result"]["change_kind"], "not_recorded")

    def test_old_completed_dependency_does_not_finish_new_parent_handoff(self):
        value = results.project_one({"run": {"id": 20, "status": "partial_success", "result_summary": {
            "awaiting_steps": ["codex"]}}, "dependencies": [{"parent_run_id": 10, "status": "completed"}]},
            operation_key="account_completion")
        self.assertEqual(value["state"], "waiting")

    def test_completion_catalog_freezes_child_execution_from_one_revision(self):
        snapshot = {"revision": 42, "values": {"ACCOUNT_COMPLETION_PASSWORD_ENABLED": True,
            "ACCOUNT_COMPLETION_PLAN_CHECK_ENABLED": True, "ACCOUNT_COMPLETION_2FA_ENABLED": True,
            "ACCOUNT_COMPLETION_CODEX_ENABLED": True, "ACCOUNT_COMPLETION_REFRESH_AT_ENABLED": True,
            "ACCOUNT_CODEX_DRIVER": "protocol", "CODEX_OAUTH_DRIVER": "protocol",
            "ACCOUNT_AT_REFRESH_DRIVER": "protocol", "PLAN_CHECK_COUNTRIES": ["JP"],
            "PLAN_CHECK_TIMEOUT": 17}}
        with patch("config.schema.non_sensitive_snapshot", return_value=snapshot):
            captured = catalog.capture_settings("account_completion")
        children = captured["config_snapshot"]["child_execution"]
        self.assertEqual(captured["config_revision"], "42")
        self.assertEqual(children["plan_check"]["countries"], ["JP"])
        self.assertEqual(children["plan_check"]["plan_check_timeout"], 17)
        self.assertEqual(children["refresh_at"]["config_snapshot_revision"], 42)
        self.assertEqual(children["codex"]["config_snapshot_revision"], 42)

    def test_managed_batch_scope_reads_limit_inside_policy_connection(self):
        from unittest.mock import MagicMock
        from config.concurrency import policy_values
        from core.operations import concurrency
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"batch_id": 70, "desired_workers": 1}
        args = task_gateway._operation_admission_arguments({"id": 9, "task_type": "plan_check", "account_id": 2,
            "batch_id": 70, "resource_family": "openai_interactive", "data": {"bulk_target_round_id": 6}})
        self.assertTrue(callable(args["extra_scopes"]))
        provider = concurrency._scope_policy(concurrency.resolve_admission_class("plan_check"),
                                            extra_scopes=args["extra_scopes"])
        with patch.object(concurrency, "_policy", return_value=(policy_values({}), 12, False)):
            scopes, _, _ = provider(connection)
        self.assertIn({"kind": "batch", "key": "operation:70", "limit": 1}, scopes)
        cursor.execute.assert_called_once()

    def test_parameters_reject_silent_overrides_and_bool(self):
        for value in (True, -841, 841, "-480"):
            with self.assertRaises(catalog.ParameterError):
                catalog.normalize_parameters("plan_check", {"timezone_offset_min": value})
        with self.assertRaises(catalog.ParameterError):
            catalog.normalize_parameters("plan_check", {"countries": ["RAND"]})
        self.assertEqual(catalog.normalize_parameters("plan_check"), {})

    def test_failed_query_does_not_count_previous_no_offer(self):
        value = results.project_one({"run": {"status": "failed", "result_summary": {"ok": True, "plus_promo_kind": "none", "current_plan_type": "free"}}}, operation_key="plan_check")
        self.assertFalse(value["result"]["confirmed_no_offer"])
        self.assertEqual(value["result"]["plus_offer_kind"], "unknown")

    def test_partial_parent_waits_for_dependency(self):
        value = results.project_one({"run": {"status": "partial_success"}, "dependencies": [{"status": "ready"}]}, operation_key="account_completion")
        self.assertEqual(value["state"], "waiting")
        self.assertFalse(value["terminal"])

    def test_unmapped_status_is_explicit_contract_error(self):
        value = results.project_one({"run": {"status": "future_status"}}, operation_key="password_setup")
        self.assertEqual(value["reason"]["code"], "adapter_status_unmapped")
        self.assertTrue(value["actions"]["retry"]["available"])


class BulkAdapterStoreTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [{"id": index, "email": f"bulk-{index}@example.test", "access_token": "isolated-test-value", "status": "success"} for index in range(1, 121)])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
        self.stack.enter_context(patch("core.accounts.operation_coordinator._completion_deployment_unavailable", return_value=None))
        self.stack.enter_context(patch("core.codex.operation_service._deployment_unavailable", return_value=None))
        self.stack.enter_context(patch("core.codex.operation_service._feature_ready", return_value=(True, "")))
        self.stack.enter_context(patch("core.accounts.liveness.service.deployment_unavailable", return_value=None))
        self.stack.enter_context(patch("core.operations.task_gateway.notify_dispatch"))

    def context(self, key):
        return {"operation_key": key, "batch_id": 900, "parameters": {}, "config_snapshot": {
            "config_snapshot_revision": 12, "auto_refresh_at_enabled": True, "countries": ["JP", "US"],
            "password_enabled": True, "plan_check_enabled": True, "twofa_enabled": True,
            "codex_enabled": True, "refresh_at_enabled": True, "password_driver": "protocol", "twofa_driver": "protocol",
        }}

    def targets(self, ids):
        return [{"target_round_id": index + 1000, "canonical_target_id": index, "account_id": index, "ordinal": index} for index in ids]

    def test_operations_create_exact_owned_queue_without_dispatch(self):
        for index, key in enumerate(catalog.OPERATIONS, 1):
            with self.subTest(operation=key), store._connect() as conn:
                receipt = adapters.submit_chunk(conn, self.targets([index]), self.context(key))[0]
                self.assertEqual(receipt["disposition"], "created")
                with conn.cursor() as cur:
                    cur.execute(f"SELECT t.task_type,t.source_system,r.data,r.status FROM {store._table('operation_tasks')} t JOIN {store._table('operation_runs')} r ON r.task_id=t.id WHERE r.id=%s", (receipt["run_id"],))
                    row = cur.fetchone()
                self.assertEqual(row["task_type"], key)
                self.assertEqual(row["status"], "queued")
                self.assertEqual(row["data"]["bulk_target_round_id"], index + 1000)
                self.assertEqual(row["data"]["config_snapshot"]["config_snapshot_revision"], 12)
                if key == "plan_check":
                    self.assertEqual(row["data"]["timezone_offset_min"], "-")
                if key == "password_setup":
                    self.assertEqual(row["source_system"], "webui_runtime")

    def test_busy_account_is_blocker_not_owned(self):
        prior = store.create_runtime_task(task_type="plan_check", account_id=1, email="bulk-1@example.test")
        with store._connect() as conn:
            receipt = adapters.submit_chunk(conn, self.targets([1]), self.context("codex_retry"))[0]
        self.assertEqual(receipt["disposition"], "waiting_account")
        self.assertEqual(receipt["blocker_run_id"], prior["run"]["id"])
        self.assertIsNone(receipt["task_id"])

    def test_narrow_preflight_matches_execution_qualification_without_loading_credentials(self):
        records.patch_row(records.ACCOUNTS, 2, {"account_status": "deactivated"})
        records.patch_row(records.ACCOUNTS, 3, {"access_token": ""})
        store.create_runtime_task(task_type="plan_check", account_id=4, email="bulk-4@example.test")
        targets = self.targets([1, 2, 3, 4, 999999])
        context = self.context("plan_check")
        context["config_snapshot"]["auto_refresh_at_enabled"] = False
        with store._connect() as conn:
            expected = adapters.prepare_many(targets, context=context, conn=conn)
            with patch.object(records, "list_rows", side_effect=AssertionError("预检不能读取完整账号/任务材料")):
                actual = adapters.prepare_many(targets, context=context, conn=conn, preflight_only=True)
        keys = ("disposition", "reason_code", "blocker_run_id")
        self.assertEqual([[row.get(key) for key in keys] for row in expected],
                         [[row.get(key) for key in keys] for row in actual])
        self.assertNotIn("isolated-test-value", str(actual))

    def test_hundred_plan_targets_have_bounded_domain_sql(self):
        from psycopg import Cursor
        statements = []
        original = Cursor.execute
        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return original(cursor, query, params, **kwargs)
        with patch.object(Cursor, "execute", measured), store._connect() as conn:
            receipt = adapters.submit_chunk(conn, self.targets(range(1, 101)), self.context("plan_check"))
        self.assertEqual(len(receipt), 100)
        self.assertEqual({item["disposition"] for item in receipt}, {"created"})
        self.assertLessEqual(len(statements), 12)

    def test_transaction_rollback_removes_run_and_account_queue(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with store._connect() as conn:
                adapters.submit_chunk(conn, self.targets([1]), self.context("plan_check"))
                raise RuntimeError("rollback")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 0)
        self.assertNotEqual(records.get_row(records.ACCOUNTS, 1).get("plan_check_status"), "queued")


class ManagedAdapterTests(BulkAdapterStoreTests):
    def setUp(self):
        super().setUp()
        from core import account_task_store
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        from core.storage.operations import bulk
        bulk.reset_ready()
        bulk.init()
        self.stack.enter_context(patch("core.bulk_operations.catalog.capture_settings", return_value={"config_revision": "12", "effective_settings": {}}))

    def batch(self, key="plan_check", count=1):
        from core.storage.operations import bulk
        import uuid
        selection = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": list(range(1, count + 1))},
            operation_key=key, parameters={}, config_revision="12", config_snapshot=self.context(key)["config_snapshot"])
        selection = bulk.freeze_selection(selection["id"])
        return bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"], selection_revision=1,
            operation_key=key, parameters={}, config_revision="12", max_concurrency=64)

    def test_actual_process_claim_finish_and_retry_keeps_task_identity(self):
        from core.storage.operations import bulk
        batch = self.batch()
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,task_id FROM {store._table('operation_runs')}")
            original = dict(cur.fetchone())
        claimed = store.claim_run(original["id"], execution_id="isolated-owner", worker_pid=1)
        self.assertEqual(claimed["status"], "running")
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["running"], 1)
        store.finish_run(original["id"], status="failed", error="测试网络超时")
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["failed"], 1)
        retry = bulk.create_round(batch["id"], request_key="retry-one", source={"view": "current"}, selection={"kind": "result_filter", "outcomes": ["failed"]})
        bulk.freeze_round(retry["id"])
        # 套餐业务本轮失败回写与worker一致，允许新的主动查询。
        records.patch_row(records.ACCOUNTS, 1, changes={"plan_check_status": "failed"})
        self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk)["submitted"], 1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_id,run_no FROM {store._table('operation_runs')} ORDER BY id")
            runs = list(cur.fetchall())
        self.assertEqual([row["task_id"] for row in runs], [original["task_id"], original["task_id"]])
        self.assertEqual([row["run_no"] for row in runs], [1, 2])

    def test_control_prevents_claim_and_settles_queue(self):
        from core.storage.operations import bulk
        batch = self.batch()
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        command = bulk.request_control(batch["id"], request_key="stop-before-claim", action="cancel_not_started", expected_control_revision=1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {store._table('operation_runs')}")
            run_id = cur.fetchone()["id"]
        with self.assertRaises(bulk.BulkError):
            store.claim_run(run_id, execution_id="must-not-start", worker_pid=1)
        bulk.settle_control(command["id"])
        bulk.project_pending()
        self.assertEqual(store.get_run(run_id)["status"], "cancelled")
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["cancelled"], 1)

    def test_full_submission_hundred_accounts_has_bounded_sql(self):
        from core.storage.operations import bulk
        from psycopg import Cursor
        batch = self.batch(count=100)
        bulk.materialize_targets(batch["id"], limit=100)
        statements = []
        original = Cursor.execute
        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return original(cursor, query, params, **kwargs)
        with patch.object(Cursor, "execute", measured):
            value = bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)
        self.assertEqual(value["submitted"], 100)
        self.assertLessEqual(len(statements), 40, f"实际SQL数量 {len(statements)}")

    def test_missing_dependency_recovers_from_parent_handoff_without_duplicate_child(self):
        from core.bulk_operations import execution
        from core.storage.operations import bulk
        batch = self.batch("account_completion")
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,task_id FROM {store._table('operation_runs')} ORDER BY id LIMIT 1")
            parent = dict(cur.fetchone())
        store.claim_run(parent["id"], execution_id="handoff-parent", worker_pid=1)
        target = bulk.lock_managed_target
        with store._connect() as conn:
            target(conn, parent["id"])
            child = store.create_runtime_task(task_type="password_setup", account_id=1, email="bulk-1@example.test",
                source_system="webui_runtime", source_id="managed-handoff-child", data={"steps": ["password"]}, conn=conn)
            bulk.inherit_managed_run(conn, child["run"]["id"], source_run_id=parent["id"],
                                     step_key="password_setup", parent_task_id=parent["task_id"])
        store.finish_run(child["run"]["id"], status="success", result_summary={"setup_step_receipts": [
            {"step": "password", "ok": True, "receipt_state": "confirmed"}]})
        store.finish_run(parent["id"], status="partial_success", result_summary={"awaiting_steps": ["account_setup"],
            "completion_handoff": {"child_source_system": "webui_runtime", "child_source_id": str(child["id"]),
                                   "remaining_steps": []}})
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["waiting"], 1)
        self.assertEqual(execution.repair_pending_handoffs(), 1)
        self.assertEqual(execution.repair_pending_handoffs(), 0)
        ready = store.list_ready_task_dependencies()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["child_status"], "success")
        self.assertEqual(ready[0]["payload"]["parent_run_id"], parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 2)

    def test_retention_skips_managed_history_and_still_cleans_old_ordinary_task(self):
        from core.storage.operations import bulk
        batch = self.batch()
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,task_id FROM {store._table('operation_runs')} ORDER BY id LIMIT 1")
            managed = dict(cur.fetchone())
        store.finish_run(managed["id"], status="failed", error="isolated_failure")
        ordinary = store.create_runtime_task(task_type="plan_check", account_id=2, email="bulk-2@example.test")
        store.finish_run(ordinary["run"]["id"], status="failed", error="isolated_failure")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET completed_at=now()-interval '30 days'")
        result = store.cleanup_terminal_history(retention_days=7, limit=100, archive=lambda _snapshot: {"verified": True})
        self.assertEqual(result["deleted_tasks"], 1)
        self.assertIsNotNone(store.get_task(managed["task_id"]))
        self.assertIsNone(store.get_task(ordinary["id"]))

    def test_actual_completion_child_and_continuation_stay_in_same_round(self):
        from core.storage.operations import bulk
        from webui import runtime
        settings = {"config_snapshot_revision": 12, "password_enabled": False, "plan_check_enabled": False,
                    "twofa_enabled": True, "codex_enabled": False, "refresh_at_enabled": False,
                    "twofa_driver": "protocol", "bulk_execution_frozen": True}
        with patch.object(self, "context", return_value={"config_snapshot": settings}):
            batch = self.batch("account_completion")
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,task_id FROM {store._table('operation_runs')} ORDER BY id LIMIT 1")
            original = dict(cur.fetchone())
        for registry in ("_OPERATION_HANDLERS", "_OPERATION_HANDLER_ALLOWLISTS", "_OPERATION_ACTIONS", "_OPERATION_ACTION_SOURCES", "_DISPATCH_HANDLERS", "_DISPATCH_CAPACITY_HANDLERS"):
            self.stack.enter_context(patch.dict(getattr(task_gateway, registry), {}))
        task_gateway.register_operation_handler("account_completion", runtime._handle_native_account_completion,
            source_systems=("webui_runtime",), config_allowlist=runtime._RUNTIME_CONFIG_ALLOWLIST)
        with patch.object(runtime, "_completion_deployment_unavailable", return_value=None):
            outcome = task_gateway._execute_operation_handler("account_completion", original["id"])
        self.assertEqual(outcome["status"], "partial_success")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT l.*,r.data FROM {store._table('operation_batch_run_links')} l JOIN {store._table('operation_runs')} r ON r.id=l.run_id ORDER BY l.execution_generation")
            links = list(cur.fetchall())
        self.assertEqual([link["relation"] for link in links], ["owned_root", "owned_child"])
        self.assertEqual(len({link["target_round_id"] for link in links}), 1)
        child = links[-1]
        self.assertEqual(child["data"]["config_snapshot"]["config_snapshot_revision"], 12)
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["waiting"], 1)
        records.patch_row(records.ACCOUNTS, 1, changes={"totp_secret": "isolated-material", "totp_enabled": True})
        store.finish_run(child["run_id"], status="success", result_summary={"ok": True})
        dependency = store.list_ready_task_dependencies()[0]
        dependency = store.claim_task_dependency(dependency["id"])
        runtime._handle_ready_completion_dependency(dependency)
        parent = store.get_task(original["task_id"], include_events=False)
        self.assertNotEqual(parent["last_run_id"], original["id"])
        with patch.object(runtime, "_completion_deployment_unavailable", return_value=None):
            outcome = task_gateway._execute_operation_handler("account_completion", int(parent["last_run_id"]))
        self.assertEqual(outcome["status"], "success")
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["success"], 1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(DISTINCT target_round_id) AS targets,count(*) AS runs FROM {store._table('operation_batch_run_links')}")
            counts = cur.fetchone()
        self.assertEqual(counts, {"targets": 1, "runs": 3})

    def test_batch_concurrency_is_enforced_by_real_permits(self):
        from config.concurrency import policy_values
        from core.operations import concurrency
        from core.storage.operations import bulk
        batch = self.batch(count=2)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_batch_controls')} SET desired_workers=1 WHERE batch_id=%s", (batch["id"],))
        bulk.process_batch(batch["id"], adapters.submit_chunk)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {store._table('operation_runs')} ORDER BY id")
            run_ids = [row["id"] for row in cur.fetchall()]
        policy = policy_values({})
        policy.update(GLOBAL_TASK_WORKERS=3, ACCOUNT_PLAN_CHECK_WORKERS=3)
        with patch.object(concurrency, "_policy", return_value=(policy, 12, False)):
            first = task_gateway.admit_operation_run(store.get_run(run_ids[0]))
            self.assertTrue(first.admitted)
            self.addCleanup(concurrency.release_execution, first.context)
            second = task_gateway.admit_operation_run(store.get_run(run_ids[1]))
        self.assertFalse(second.admitted)
        self.assertIn("batch_capacity", second.blocked_by)
        self.assertEqual(store.get_run(run_ids[1])["status"], "queued")
