"""共享业务预算的跨进程、原子认领、退出释放与恢复回归。"""
from __future__ import annotations

import multiprocessing
import os
import threading
import time
from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.operations import concurrency, task_gateway
from core.storage import postgres, runtime_config
from core.storage.operations import permits, store
from tests.support_pg import PostgresTestCase


def _compete_for_last_slot(start, stop, results, name):
    start.wait(10)
    admitted = concurrency.try_admit_and_claim(
        execution_key=name, task_type="live_check", claim=lambda conn, execution_id: {"id": 1},
    )
    results.put(admitted.admitted)
    stop.wait(15)
    if admitted.context:
        concurrency.release_execution(admitted.context)
    postgres.close_pools()


class ExecutionPermitTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.key = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        self.key.start()
        self.addCleanup(self.key.stop)
        from core.storage.operations import legacy_task_store

        for name, value in (("_SCHEMA", self.schema), ("_READY_KEY", "")):
            legacy = patch.object(legacy_task_store, name, value)
            legacy.start()
            self.addCleanup(legacy.stop)
        legacy_task_store.init()
        self.contexts = []
        self.addCleanup(self._release_all)
        permits.ensure_tables()

    def _release_all(self):
        for context in self.contexts:
            concurrency.release_execution(context)

    def policy(self, **updates):
        from config.concurrency import policy_values

        values = policy_values({})
        values.update(updates)
        runtime_config.write_values({key: str(value) for key, value in values.items()}, activate=True, source="test")

    def admit(self, key, task_type="live_check", **kwargs):
        result = concurrency.try_admit_and_claim(
            execution_key=key, task_type=task_type,
            claim=kwargs.pop("claim", lambda conn, execution_id: {"id": 1}), **kwargs,
        )
        if result.context:
            self.contexts.append(result.context)
        return result

    def test_global_and_type_limits_allow_unused_type_capacity(self):
        self.policy(GLOBAL_TASK_WORKERS=10, ACCOUNT_LIVE_CHECK_WORKERS=4,
                    ACCOUNT_PLAN_CHECK_WORKERS=6, CODEX_OAUTH_WORKERS=2)
        for index in range(4):
            self.assertTrue(self.admit(f"live:{index}"))
        self.assertIn("type_capacity", self.admit("live:overflow").blocked_by)
        for index in range(6):
            self.assertTrue(self.admit(f"plan:{index}", "plan_check"))
        self.assertIn("global_capacity", self.admit("codex:overflow", "codex_retry").blocked_by)
        self.assertEqual(10, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_batch_provider_and_account_scopes_are_atomic(self):
        self.policy(GLOBAL_TASK_WORKERS=4)
        first = self.admit("one", "extract_link", batch_key="b1", batch_limit=1,
                           provider_key="legacy", provider_limit=2,
                           extra_scopes=[{"kind": "account", "key": "a1", "limit": 1}])
        self.assertTrue(first)
        blocked = self.admit("two", "extract_link", batch_key="b1", batch_limit=1,
                             provider_key="legacy", provider_limit=2)
        self.assertIn("batch_capacity", blocked.blocked_by)
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        self.assertIn("account_busy", self.admit("three", extra_scopes=[{"kind": "account", "key": "a1", "limit": 1}]).blocked_by)
        self.assertTrue(self.admit("other-provider", "extract_link", provider_key="huanguang", provider_limit=1))

    def test_same_execution_key_cannot_reenter_until_worker_exit(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        first = self.admit("stable")
        self.assertTrue(first)
        # Run 终态或 defer 的业务写回不会释放执行许可。
        self.assertIn("execution_active", self.admit("stable").blocked_by)
        self.assertTrue(concurrency.release_execution(first.context))
        self.assertFalse(concurrency.release_execution(first.context))
        second = self.admit("stable")
        self.assertTrue(second)
        self.assertFalse(concurrency.release_permit(first.context.permit_id, first.context.execution_id))
        self.assertTrue(concurrency.validate_execution(second.context))

    def test_claim_failure_rolls_back_its_business_write(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE TABLE {postgres.qualified('permit_claim_probe')} (id INTEGER)")

        def rejected(conn, execution_id):
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO {postgres.qualified('permit_claim_probe')} VALUES (1)")
            return None

        self.assertFalse(self.admit("rejected", claim=rejected))
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {postgres.qualified('permit_claim_probe')}")
            self.assertEqual(0, cur.fetchone()[0])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_config_lowering_drains_and_increasing_refills(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        for index in range(3):
            self.assertTrue(self.admit(f"old:{index}"))
        self.policy(GLOBAL_TASK_WORKERS=1)
        self.assertTrue(concurrency.get_concurrency_status()["global"]["draining"])
        self.assertIn("global_capacity", self.admit("new", "plan_check").blocked_by)
        self.policy(GLOBAL_TASK_WORKERS=4)
        self.assertTrue(self.admit("new", "plan_check"))

    def test_old_install_requires_explicit_complete_migration(self):
        runtime_config.write_values({"ACCOUNT_BATCH_WORKERS": "7"}, activate=True, source="test")
        result = self.admit("old-install")
        self.assertIn("concurrency_policy_migration_required", result.blocked_by)
        self.assertTrue(concurrency.get_concurrency_status()["migration_required"])
        self.policy(GLOBAL_TASK_WORKERS=3)
        self.assertTrue(self.admit("old-install"))

    def test_global_one_nested_sync_steps_reuse_the_same_permit(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        admitted = self.admit("inspection", "account_inspection")
        with concurrency.execution_scope(admitted.context):
            with concurrency.execution_scope(admitted.context):
                self.assertIs(admitted.context, concurrency.current_execution())
                self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_persistent_type_and_batch_fairness(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        current = self.admit("current", "token_refresh", batch_key="b0", batch_limit=3)
        self.assertFalse(self.admit("next-token", "token_refresh", batch_key="b0", batch_limit=3))
        self.assertFalse(self.admit("next-live", "live_check"))
        concurrency.release_execution(current.context)
        self.assertIn("fairness_turn", self.admit("next-token", "token_refresh", batch_key="b0", batch_limit=3).blocked_by)
        following = self.admit("next-live", "live_check")
        self.assertTrue(following)
        concurrency.release_execution(following.context)
        token = self.admit("next-token", "token_refresh", batch_key="b0", batch_limit=3)
        self.assertTrue(token)
        self.assertFalse(self.admit("batch-zero", "token_refresh", batch_key="b0", batch_limit=3))
        self.assertFalse(self.admit("batch-one", "token_refresh", batch_key="b1", batch_limit=3))
        concurrency.release_execution(token.context)
        self.assertIn("fairness_turn", self.admit("batch-zero", "token_refresh", batch_key="b0", batch_limit=3).blocked_by)
        self.assertTrue(self.admit("batch-one", "token_refresh", batch_key="b1", batch_limit=3))

    def test_paused_batch_does_not_block_other_type_or_batch(self):
        self.policy(GLOBAL_TASK_WORKERS=4)

        def paused(conn, execution_id):
            raise permits.ClaimUnavailable("batch_paused")

        waiting = self.admit("paused", "live_check", batch_key="a", batch_limit=2, claim=paused)
        self.assertEqual(("batch_paused",), waiting.blocked_by)
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])
        other_type = self.admit("other-type", "plan_check")
        self.assertTrue(other_type)
        concurrency.release_execution(other_type.context)
        other_batch = self.admit("other-batch", "live_check", batch_key="b", batch_limit=2)
        self.assertTrue(other_batch)
        concurrency.release_execution(other_batch.context)
        self.assertTrue(self.admit("paused", "live_check", batch_key="a", batch_limit=2))

    def test_recovery_keeps_live_owner_despite_stale_heartbeat(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        admitted = self.admit("live-owner")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_execution_permits')} SET heartbeat_at=now()-interval '2 days'")
        self.assertEqual(0, concurrency.recover_execution_permits()["released"])
        self.assertTrue(concurrency.validate_execution(admitted.context))

    def test_pid_reuse_is_verified_using_process_start(self):
        owner = permits.current_owner()
        owner["process_start"] = "已退出的旧进程启动身份"
        self.assertEqual("exited", concurrency.owner_liveness(owner))
        owner["host_id"] = "other-host"
        self.assertEqual("unverified", concurrency.owner_liveness(owner))

    def test_release_failure_after_thread_exit_is_retried(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        admitted = self.admit("release-retry")
        original = concurrency.release_permit
        with patch.object(concurrency, "release_permit", side_effect=OSError("测试数据库暂断")):
            self.assertFalse(concurrency.release_execution(admitted.context))
            self.assertFalse(admitted.context.released)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and not admitted.context.released:
            time.sleep(.05)
        self.assertTrue(admitted.context.released)
        self.assertFalse(original(admitted.context.permit_id, admitted.context.execution_id))

    def test_two_processes_share_the_last_slot(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        context = multiprocessing.get_context("spawn")
        start, stop, results = context.Event(), context.Event(), context.Queue()
        processes = [context.Process(target=_compete_for_last_slot,
                                     args=(start, stop, results, f"process:{index}")) for index in range(2)]
        try:
            for process in processes:
                process.start()
            start.set()
            outcomes = [results.get(timeout=20), results.get(timeout=20)]
            self.assertEqual([False, True], sorted(outcomes))
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        finally:
            stop.set()
            for process in processes:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=3)

    def test_native_wrapper_uses_exactly_one_claim_and_blocks_defer_reentry(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        created = store.create_runtime_task(task_type="maintenance_check", account_id=None, email="", data={})
        run_id = created["run"]["id"]
        calls = []

        def handle(context):
            calls.append(context.execution_id)
            context.defer(delay_seconds=0, reason="测试续查")
            concurrent = task_gateway.admit_operation_run(store.get_run(run_id))
            self.assertIn("execution_active", concurrent.blocked_by)
            return None

        task_gateway.register_operation_handler("maintenance_check", handle)
        self.addCleanup(task_gateway.unregister_operation_handler, "maintenance_check")
        with patch.object(store, "claim_run", wraps=store.claim_run) as claim:
            result = task_gateway._execute_operation_handler("maintenance_check", run_id)
        self.assertEqual("deferred", result["status"])
        self.assertEqual(1, len(calls))
        self.assertEqual(1, claim.call_count)
        self.assertIn("conn", claim.call_args.kwargs)
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_unknown_task_type_cannot_register_a_handler(self):
        with self.assertRaises(concurrency.ConcurrencyPolicyError) as caught:
            task_gateway.register_dispatch_handler("missing_policy", lambda run_id: None)
        self.assertEqual("concurrency_policy_missing", caught.exception.code)

    def test_account_busy_candidate_does_not_block_another_type(self):
        self.policy(GLOBAL_TASK_WORKERS=1)

        def busy(conn, execution_id):
            raise permits.ClaimUnavailable("account_busy")

        self.assertIn("account_busy", self.admit("busy-account", "live_check", claim=busy).blocked_by)
        self.assertTrue(self.admit("free-account", "token_refresh"))

    def test_queued_count_reads_durable_queue_before_first_dispatch(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        store.create_runtime_task(task_type="live_check", account_id=None, email="", data={})
        store.create_runtime_task(task_type="plan_check", account_id=None, email="", data={})
        status = concurrency.get_concurrency_status()
        types = {row["key"]: row for row in status["types"]}
        self.assertEqual(1, types["live_check"]["queued"])
        self.assertEqual(1, types["plan_check"]["queued"])

    def test_different_type_is_visible_beyond_old_batch_scan_window(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        for index in range(70):
            batch = store.create_runtime_batch(batch_type="live_check", title="测试批次", requested_count=1)
            store.create_runtime_task(task_type="live_check", account_id=None, email="", data={}, batch_id=batch["id"])
        later = store.create_runtime_task(task_type="plan_check", account_id=None, email="", data={})
        candidates = store.list_dispatchable_runs(limit=8, task_types=("live_check", "plan_check"))
        self.assertIn(later["run"]["id"], [row["id"] for row in candidates])

    def test_new_work_and_saved_order_polling_alternate_persistently(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        first = self.admit("extract-new-1", "extract_link", metadata={"dispatch_lane": "new"})
        self.assertFalse(self.admit("extract-new-2", "extract_link", metadata={"dispatch_lane": "new"}))
        self.assertFalse(self.admit("extract-poll", "extract_link", metadata={"dispatch_lane": "continuation"}))
        concurrency.release_execution(first.context)
        self.assertIn("fairness_turn", self.admit("extract-new-2", "extract_link", metadata={"dispatch_lane": "new"}).blocked_by)
        polling = self.admit("extract-poll", "extract_link", metadata={"dispatch_lane": "continuation"})
        self.assertTrue(polling)
        concurrency.release_execution(polling.context)
        self.assertTrue(self.admit("extract-new-2", "extract_link", metadata={"dispatch_lane": "new"}))

    def test_cancel_and_terminal_cleanup_keep_permit_until_worker_exit(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        created = store.create_runtime_task(task_type="live_check", account_id=None, email="", data={})
        run = store.get_run(created["run"]["id"])
        admitted = task_gateway.admit_operation_run(run)
        self.contexts.append(admitted.context)
        store.request_run_cancel(run["id"])
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        store.finish_run(run["id"], status="cancelled", execution_id=admitted.context.execution_id)
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        concurrency.set_execution_state(admitted.context, "cleaning")
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["cleaning"])
        self.assertFalse(self.admit("cannot-start-during-cleanup", "plan_check"))
        concurrency.release_execution(admitted.context)
        self.assertTrue(self.admit("cannot-start-during-cleanup", "plan_check"))

    def test_old_recovery_does_not_replace_a_live_owner(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        created = store.create_runtime_task(task_type="live_check", account_id=None, email="", data={})
        run_id = created["run"]["id"]
        admitted = task_gateway.admit_operation_run(store.get_run(run_id))
        self.contexts.append(admitted.context)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_runs')} SET heartbeat_at=now()-interval '2 days' WHERE id=%s", (run_id,))
        self.assertEqual(0, store.recover_interrupted_runtime_runs(stale_after_seconds=1))
        current = store.get_run(run_id)
        self.assertEqual("running", current["status"])
        self.assertEqual(admitted.context.execution_id, current["execution_id"])

    def test_submit_rejection_requeues_without_permit_leak(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        created = store.create_runtime_task(task_type="maintenance_check", account_id=None, email="", data={})
        run_id = created["run"]["id"]
        admitted = task_gateway.admit_operation_run(store.get_run(run_id))
        task_gateway.rollback_admission(admitted.context)
        self.assertEqual("queued", store.get_run(run_id)["status"])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_delayed_runs_are_separate_from_ready_queue_and_unknown_types_are_visible(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        extract = store.create_runtime_task(task_type="extract_link", account_id=None, email="", data={})
        regular = store.create_runtime_task(task_type="live_check", account_id=None, email="", data={})
        store.create_runtime_task(task_type="unsupported_old_task", account_id=None, email="", data={})
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {postgres.qualified('operation_runs')} SET next_attempt_at=now()+interval '1 hour' WHERE id=ANY(%s)", ([extract["run"]["id"], regular["run"]["id"]],))
        status = concurrency.get_concurrency_status()
        self.assertEqual(0, status["queued"])
        self.assertEqual(1, status["scheduled"])
        self.assertEqual(1, status["remote_waiting"])
        self.assertEqual([{"task_type": "unsupported_old_task", "queued": 1, "code": "concurrency_policy_missing"}], status["unknown_types"])

    def test_gateway_single_local_slot_rotates_types_with_durable_cursor(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        created = []
        for kind in ("live_check", "live_check", "plan_check"):
            created.append(store.create_runtime_task(task_type=kind, account_id=None, email="", data={}))
        seen = []
        for kind in ("live_check", "plan_check"):
            task_gateway.register_operation_handler(kind, lambda context: (seen.append(context.task_type), task_gateway.OperationResult.success({}))[1])
            self.addCleanup(task_gateway.unregister_operation_handler, kind)
        for _ in range(2):
            self.assertEqual(1, task_gateway.dispatch_registered_once(limit=8))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if not concurrency.active_execution_keys():
                    break
                time.sleep(.02)
        self.assertEqual(["live_check", "plan_check"], seen)

    def test_context_release_remains_in_its_original_schema(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        admitted = self.admit("domain-bound")
        other_schema = self.schema + "_other"
        from tests.support_pg import drop_schema

        try:
            with patch.dict(os.environ, {"TURB_DB_SCHEMA": other_schema}):
                permits.ensure_tables()
                self.policy(GLOBAL_TASK_WORKERS=1)
                next_domain = self.admit("domain-bound")
                self.assertTrue(next_domain)
                self.assertTrue(concurrency.validate_execution(admitted.context))
                self.assertTrue(concurrency.release_execution(admitted.context))
                self.assertTrue(concurrency.validate_execution(next_domain.context))
                concurrency.release_execution(next_domain.context)
        finally:
            drop_schema(other_schema)
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_dispatcher_survives_a_store_outage_without_unlimited_fallback(self):
        ready = threading.Event()
        calls = []

        def dispatch():
            calls.append(1)
            if len(calls) == 1:
                raise concurrency.ConcurrencyStoreUnavailable("测试数据库暂不可用")
            ready.set()
            return 0

        try:
            with patch.object(task_gateway, "dispatch_registered_once", side_effect=dispatch), patch.object(
                task_gateway, "_recover_stale_runtime_runs_if_due"
            ):
                task_gateway.start_dispatcher(interval_seconds=.05)
                self.assertTrue(ready.wait(2))
                self.assertTrue(task_gateway.dispatcher_status()["alive"])
        finally:
            task_gateway.stop_dispatcher()

    def test_restart_registers_and_executes_existing_peripheral_queue_without_new_requests(self):
        from core.integrations.c2a import manual_sync
        from core.integrations.sub2api import manual_upload, monitor
        from core.maintenance import sentinel
        from webui import runtime

        self.policy(GLOBAL_TASK_WORKERS=3)
        types = ("sentinel_maintenance_check", "sub2api_scan", "sub2api_manual_upload", "c2a_session_reimport")
        tasks = [store.create_runtime_task(task_type=kind, account_id=None, email="", data={}) for kind in types]
        for kind in types:
            task_gateway.unregister_operation_handler(kind)
        handled = []

        def handler(context):
            handled.append(context.task_type)
            return task_gateway.OperationResult.success({"restart_recovered": True})

        stop_targets = (
            "core.proxy.pool.start", "core.registration.service.start_dispatcher",
            "core.browser.roxy.client.cleanup_orphaned_profiles", "core.registration.debug.cleanup_expired_artifacts",
            "core.accounts.deactivation.mail_scan.start_periodic_scanner",
            "core.accounts.token_refresh.start_periodic_refresher", "core.codex.token_refresh_service.start_periodic_refresher",
            "core.integrations.sub2api.jobs.start_periodic_sync", "core.integrations.sub2api.monitor.start_periodic_monitor",
            "core.bulk_operations.service.start_workers",
            "core.accounts.auth_context_cleanup.start_periodic_cleanup", "core.operations.retention.start_periodic_cleanup",
            "core.email.email_butler.usage_reports.start_worker",
        )
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(runtime, "_runtime_started", False))
                stack.enter_context(patch.object(runtime, "_runtime_started_at", None))
                stack.enter_context(patch.object(sentinel, "_handle_check", side_effect=handler))
                stack.enter_context(patch.object(monitor, "_handle_scan", side_effect=handler))
                stack.enter_context(patch.object(manual_upload, "_handle", side_effect=handler))
                stack.enter_context(patch.object(manual_sync, "_handle", side_effect=handler))
                for target in stop_targets:
                    stack.enter_context(patch(target, return_value={}))
                stack.enter_context(patch.object(runtime.sms_provider, "start_cancel_worker"))
                stack.enter_context(patch.object(runtime.operation_task_store, "start_projection_worker"))
                stack.enter_context(patch.object(runtime.account_task_store, "start_dependency_dispatcher"))
                stack.enter_context(patch.object(runtime.codex_operation_service, "resume_queued", return_value=0))
                self.assertTrue(runtime.start_runtime())
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    states = [store.get_run(task["run"]["id"])["status"] for task in tasks]
                    if states == ["success"] * len(types) and not concurrency.active_execution_keys():
                        break
                    time.sleep(.05)
                self.assertEqual(["success"] * len(types), states)
                self.assertCountEqual(types, handled)
        finally:
            task_gateway.stop_dispatcher()
            for kind in types:
                task_gateway.unregister_operation_handler(kind)

    def test_policy_write_and_admission_share_one_transaction_lock(self):
        self.policy(GLOBAL_TASK_WORKERS=2)
        self.assertTrue(self.admit("already-running"))
        changed, commit = threading.Event(), threading.Event()

        def update():
            with runtime_config.transaction() as conn:
                runtime_config.write_values({"GLOBAL_TASK_WORKERS": "1"}, conn=conn, source="test")
                changed.set()
                self.assertTrue(commit.wait(5))

        def claim():
            self.assertTrue(changed.wait(5))
            return self.admit("config-racer", "plan_check")

        with ThreadPoolExecutor(max_workers=2) as pool:
            writer = pool.submit(update)
            self.assertTrue(changed.wait(5))
            claimant = pool.submit(claim)
            try:
                self.assertFalse(claimant.done())
            finally:
                commit.set()
            writer.result(timeout=5)
            result = claimant.result(timeout=5)
        self.assertFalse(result.admitted)
        self.assertIn("global_capacity", result.blocked_by)

    def test_full_provider_with_more_than_a_window_of_batches_cannot_hide_another_provider(self):
        self.policy(GLOBAL_TASK_WORKERS=3, EXTRACT_LINK_WORKERS=3)
        current = self.admit("legacy-already-running", "extract_link", provider_key="legacy", provider_limit=1)
        self.assertTrue(current)
        for _ in range(70):
            batch = store.create_runtime_batch(batch_type="extract_link", title="旧满平台批次", requested_count=1)
            store.create_runtime_task(task_type="extract_link", account_id=None, email="", data={"provider_id": "legacy"}, batch_id=batch["id"])
        later = store.create_runtime_task(task_type="extract_link", account_id=None, email="", data={"provider_id": "huanguang"})
        candidates = store.list_dispatchable_runs(limit=8, task_types=("extract_link",))
        target = next((row for row in candidates if row["id"] == later["run"]["id"]), None)
        self.assertIsNotNone(target)
        admitted = task_gateway.admit_operation_run(target)
        self.assertTrue(admitted)
        self.contexts.append(admitted.context)

    def test_concurrency_errors_have_fixed_classification_and_waits_are_not_failures(self):
        from core.operations.errors import classify_task_error

        for code in ("concurrency_policy_invalid", "concurrency_policy_missing", "scheduler_store_unavailable",
                     "executor_submit_failed", "permit_owner_lost"):
            with self.subTest(code=code):
                projected = classify_task_error(code, error_code=code)
                self.assertEqual(code, projected["code"])
                self.assertTrue(projected["is_error"])
                self.assertNotIn("UNK", projected["display_code"])
        for code in ("global_capacity", "type_capacity", "batch_capacity", "provider_capacity", "account_busy",
                     "execution_active", "fairness_turn", "concurrency_policy_migration_required"):
            with self.subTest(wait=code):
                projected = classify_task_error(code, error_code=code)
                self.assertEqual("task.pending", projected["code"])
                self.assertFalse(projected["is_error"])

    def test_active_deferred_execution_is_excluded_from_fairness_candidates(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        active = self.admit("old-maintenance", "maintenance_check")
        self.assertTrue(active)
        self.assertIn("execution_active", self.admit("old-maintenance", "maintenance_check").blocked_by)
        # maintenance 位于 token_refresh 之后；旧 active request 不能截走下一轮机会。
        following = self.admit("next-token", "token_refresh")
        self.assertTrue(following)
        concurrency.release_execution(following.context)
        self.assertTrue(self.admit("next-live", "live_check"))

    def test_batch_limit_is_observed_without_a_waiting_request(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        self.assertTrue(self.admit("registration-one", "registration_roxy", batch_key="registration:stable", batch_limit=2))
        self.assertTrue(self.admit("butler-one", "email_import", batch_key="butler-import:stable", batch_limit=4))
        limits = {row["key"]: row["limit"] for row in concurrency.get_concurrency_status()["batches"]}
        self.assertEqual(2, limits["registration:stable"])
        self.assertEqual(4, limits["butler-import:stable"])

    def test_xxsyun_lane_requires_saved_remote_order_and_preserves_business_flag(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        task_ids = []
        for index, remote_order in enumerate(("saved-order", None)):
            task = store.create_runtime_task(task_type="extract_link", account_id=None, email="", data={
                "provider_id": "legacy", "payment_source": "xxsyun", "workbench_action": "sync_status",
                "extract_poll_continuation": False,
            })
            task_ids.append(task["run"]["id"])
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"""INSERT INTO {postgres.qualified('extract_link_payment_orders')}
                    (task_id,origin_run_id,extract_provider_id,extract_job_id,material_job_id,payment_provider,
                     attempt_no,api_base,idempotency_key,remote_order_id,material_fingerprint,private_encrypted,submission_state)
                    VALUES (%s,%s,'legacy','fixture-job','fixture-material','xxsyun',1,
                            'https://fixture.test',%s,%s,'fixture-fingerprint','fixture-encrypted','unknown')""",
                            (task["id"], task["run"]["id"], f"fixture-order-{index}", remote_order))
        candidates = {row["id"]: row for row in store.list_dispatchable_runs(limit=8)}
        self.assertEqual("continuation", candidates[task_ids[0]]["dispatch_lane"])
        self.assertEqual("new", candidates[task_ids[1]]["dispatch_lane"])
        self.assertIs(False, candidates[task_ids[0]]["data"]["extract_poll_continuation"])

    def test_legacy_registration_codex_worker_reuses_parent_at_global_one(self):
        from core import db
        from core.codex import retry_service, operation_service
        from core.registration import admission, service
        from core.storage import records

        self.policy(GLOBAL_TASK_WORKERS=1)
        account_id = records.insert_row(records.ACCOUNTS, {"email": "fixture-codex@example.test", "access_token": "fixture-token"})
        job = db.create_job("outlook", batch_workers=1, data={"config_snapshot": {"registration_driver": "roxy"}})
        db._patch_job(job["id"], {"job_type": "codex_retry", "email": "fixture-codex@example.test", "account_id": account_id})
        seen = []

        def legacy(email, **kwargs):
            context = concurrency.current_execution()
            self.assertEqual("codex_retry", context.task_type)
            self.assertEqual(f"registration_job:{job['id']}", context.execution_key)
            self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
            seen.append(email)
            return {"status": "success", "ok": True}

        with patch.object(retry_service, "_run_worker_legacy", side_effect=legacy), patch.object(
            operation_service, "submit", side_effect=AssertionError("父许可内禁止入队并等待子任务")
        ) as submit:
            admission.run_job(job["id"], lambda: service._run_codex_retry_job(
                job["id"], job["log_file"], "fixture-codex@example.test", account_id,
            ))
        submit.assert_not_called()
        self.assertEqual(["fixture-codex@example.test"], seen)
        self.assertEqual("success", db.get_job(job["id"])["status"])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_inline_codex_cannot_use_another_accounts_execution_permit(self):
        from core.codex import retry_service

        self.policy(GLOBAL_TASK_WORKERS=1)
        context = self.admit("owner-one", "codex_retry", claim=lambda conn, execution_id: {
            "id": 1, "email": "owner@example.test", "account_id": 4,
        }).context
        with concurrency.execution_scope(context), patch.object(retry_service.db, "get_account_by_email", return_value={"id": 5}), patch.object(
            retry_service, "_run_worker_legacy"
        ) as remote:
            with self.assertRaises(concurrency.ConcurrencyPolicyError) as caught:
                retry_service.run_worker("other@example.test")
        self.assertEqual("concurrency_policy_invalid", caught.exception.code)
        remote.assert_not_called()

    def test_dependency_callback_locks_run_before_task_and_cannot_deadlock_admission(self):
        from psycopg.rows import dict_row

        self.policy(GLOBAL_TASK_WORKERS=1)
        parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                           source_system="webui_runtime", resource_family="completion_coordinator")
        run_id, task_id = parent["run"]["id"], parent["id"]

        @contextmanager
        def callback_connection():
            with postgres.connect(row_factory=dict_row) as conn:
                conn.execute("SET application_name TO 'permit-dependency-lock-test'")
                yield conn

        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(store, "_connect", callback_connection):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {postgres.qualified('operation_runs')} WHERE id=%s FOR UPDATE", (run_id,))
                result = pool.submit(store.apply_task_dependency_result,
                                     parent_source_system="webui_runtime", parent_source_id=str(task_id),
                                     child_status="failed", expected_parent_run_id=run_id)
                deadline, waiting = time.monotonic() + 5, False
                while time.monotonic() < deadline:
                    with postgres.connect() as probe, probe.cursor() as probe_cur:
                        probe_cur.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='permit-dependency-lock-test' AND wait_event_type='Lock')")
                        waiting = bool(probe_cur.fetchone()[0])
                    if waiting:
                        break
                    time.sleep(.02)
                self.assertTrue(waiting)
                # 回调正等 Run，此时不能已持 Task；准入认领可沿 Run→Task 继续。
                cur.execute(f"SELECT id FROM {postgres.qualified('operation_tasks')} WHERE id=%s FOR UPDATE NOWAIT", (task_id,))
                self.assertEqual(task_id, cur.fetchone()[0])
            self.assertIsNotNone(result.result(timeout=5))

    def test_old_dependency_result_never_overwrites_a_retried_parent_generation(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                           source_system="webui_runtime", resource_family="completion_coordinator")
        old_run = parent["run"]["id"]
        store.finish_run(old_run, status="partial_success")
        new_run = store.retry_runtime_task(parent["id"])
        result = store.apply_task_dependency_result(parent_source_system="webui_runtime", parent_source_id=str(parent["id"]),
                                                    child_status="failed", expected_parent_run_id=old_run)
        self.assertTrue(result["dependency_stale"])
        self.assertEqual("queued", store.get_run(new_run["id"])["status"])

    def test_sibling_completion_reconciles_parent_without_locking_other_workers_task(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                           resource_family="completion_coordinator")
        children = [store.create_runtime_task(task_type="token_refresh", account_id=None, email="", data={},
                                             parent_task_id=parent["id"]) for _ in range(2)]
        barrier = threading.Barrier(2)
        original = store._reconcile_parent_task_cur

        def together(cur, parent_task_id, **kwargs):
            barrier.wait(timeout=5)
            return original(cur, parent_task_id, **kwargs)

        with patch.object(store, "_reconcile_parent_task_cur", side_effect=together), ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(store.finish_run, child["run"]["id"], status="success") for child in children]
            for result in results:
                result.result(timeout=10)
        self.assertEqual("success", store.get_task(parent["id"], include_events=False)["status"])

    def test_legacy_dependencies_with_multiple_parent_runs_never_mutate_or_reopen_current_run(self):
        from webui import runtime

        self.policy(GLOBAL_TASK_WORKERS=1)
        for child_status in ("success", "failed"):
            with self.subTest(child_status=child_status):
                parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                                   source_system="webui_runtime", resource_family="completion_coordinator")
                store.finish_run(parent["run"]["id"], status="partial_success")
                dependency = store.register_task_dependency(parent_source_system="webui_runtime", parent_source_id=str(parent["id"]),
                    child_source_system="legacy_child", child_source_id=str(parent["id"]), dependency_type="account_completion", payload={})
                store.mark_task_dependency_ready(child_source_system="legacy_child", child_source_id=str(parent["id"]), child_status=child_status)
                new_run = store.retry_runtime_task(parent["id"])
                claimed = store.claim_task_dependency(dependency["id"])
                runtime._handle_ready_completion_dependency(claimed)
                detail = store.get_task(parent["id"], include_events=False)
                self.assertEqual(2, len(detail["runs"]))
                self.assertEqual(new_run["id"], detail["last_run_id"])
                self.assertEqual("queued", store.get_run(new_run["id"])["status"])

    def test_legacy_single_parent_run_dependency_still_recovers_normally(self):
        from webui import runtime

        self.policy(GLOBAL_TASK_WORKERS=1)
        for child_status in ("success", "failed"):
            with self.subTest(child_status=child_status):
                parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                                   source_system="webui_runtime", resource_family="completion_coordinator")
                store.finish_run(parent["run"]["id"], status="partial_success")
                dependency = store.register_task_dependency(parent_source_system="webui_runtime", parent_source_id=str(parent["id"]),
                    child_source_system="legacy_child", child_source_id=str(parent["id"]), dependency_type="account_completion", payload={})
                store.mark_task_dependency_ready(child_source_system="legacy_child", child_source_id=str(parent["id"]), child_status=child_status)
                claimed = store.claim_task_dependency(dependency["id"])
                runtime._handle_ready_completion_dependency(claimed)
                detail = store.get_task(parent["id"], include_events=False)
                if child_status == "success":
                    self.assertEqual(2, len(detail["runs"]))
                    self.assertEqual("queued", detail["status"])
                else:
                    self.assertEqual(1, len(detail["runs"]))
                    self.assertEqual("partial_success", detail["status"])

    def test_dependency_auto_retry_cas_ignores_a_newer_manual_run(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        parent = store.create_runtime_task(task_type="account_completion", account_id=None, email="", data={},
                                           resource_family="completion_coordinator")
        store.finish_run(parent["run"]["id"], status="partial_success")
        newer = store.retry_runtime_task(parent["id"])
        ignored = store.retry_runtime_task(parent["id"], trigger="dependency_resume",
                                           expected_previous_run_id=parent["run"]["id"])
        self.assertTrue(ignored["dependency_stale"])
        self.assertEqual(newer["id"], store.get_task(parent["id"], include_events=False)["last_run_id"])
