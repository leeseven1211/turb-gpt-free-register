"""真实执行承载满额时仍展示数据库容量原因，观察不能认领或改变调度。"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

from core.operations import concurrency, task_gateway
from core.storage import postgres, records, runtime_config
from core.storage.operations import legacy_task_store, permits, store
from tests.support_pg import PostgresTestCase


class ConcurrencyWaitObservationTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        encryption = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()})
        encryption.start()
        self.addCleanup(encryption.stop)
        for name, value in (("_SCHEMA", self.schema), ("_READY_KEY", "")):
            legacy = patch.object(legacy_task_store, name, value)
            legacy.start()
            self.addCleanup(legacy.stop)
        legacy_task_store.init()
        store.reset_ready()
        store.init()
        self.contexts = []
        self.addCleanup(lambda: [concurrency.release_execution(context) for context in self.contexts])

    def policy(self, **updates):
        from config.concurrency import policy_values

        values = policy_values({})
        values.update(updates)
        runtime_config.write_values({key: str(value) for key, value in values.items()}, activate=True, source="test")

    def queued(self, kind):
        task = store.create_runtime_task(task_type=kind, account_id=None, email="", data={})
        return store.get_run(task["run"]["id"])

    def admit(self, run):
        admitted = task_gateway.admit_operation_run(run)
        self.assertTrue(admitted)
        self.contexts.append(admitted.context)
        return admitted.context

    def request(self, run_id):
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {postgres.qualified('operation_execution_requests')} WHERE execution_key=%s",
                        (f"operation_run:{run_id}",))
            return cur.fetchone()

    def dispatch_full(self, types, *, other_pool_slots=0):
        full = SimpleNamespace(available_slots=lambda: 0, try_submit=Mock())
        other = SimpleNamespace(available_slots=lambda: other_pool_slots, try_submit=Mock())
        handlers = {kind: (Mock(), ("native_operations",)) for kind in types}
        before = permits.dispatch_cursor()
        task_gateway._RUN_DISPATCH_WAKE.clear()
        with patch.object(task_gateway, "_executor", return_value=full), patch.object(
            task_gateway, "_extract_executor", return_value=other
        ), patch.dict(task_gateway._DISPATCH_HANDLERS, handlers, clear=True), patch.dict(
            task_gateway._DISPATCH_CAPACITY_HANDLERS, {}, clear=True
        ), patch.object(store, "claim_run", wraps=store.claim_run) as claim:
            for _ in range(2):
                self.assertEqual(0, task_gateway.dispatch_registered_once(limit=8))
                self.assertFalse(task_gateway._RUN_DISPATCH_WAKE.is_set())
        claim.assert_not_called()
        full.try_submit.assert_not_called()
        other.try_submit.assert_not_called()
        self.assertEqual(before, permits.dispatch_cursor())

    def test_zero_slots_for_the_whole_carrier_records_global_wait_without_claim_or_wakeup(self):
        self.policy(GLOBAL_TASK_WORKERS=1, ACCOUNT_LIVE_CHECK_WORKERS=1, ACCOUNT_PLAN_CHECK_WORKERS=1)
        self.admit(self.queued("live_check"))
        waiting = self.queued("plan_check")
        before = {key: waiting.get(key) for key in ("status", "execution_id", "run_no", "next_attempt_at", "data")}
        self.dispatch_full(("live_check", "plan_check"))
        request = self.request(waiting["id"])
        self.assertEqual(["global_capacity"], request["blocked_by"])
        self.assertTrue(request["observed_only"])
        after = store.get_run(waiting["id"])
        self.assertEqual(before, {key: after.get(key) for key in before})
        self.assertEqual([{"code": "global_capacity", "occupied": 1, "limit": 1,
                           "scope_kind": "global", "scope_key": "deployment"}], after["admission_wait_reasons"])
        self.assertEqual("global_capacity", store.get_task(waiting["task_id"], include_events=False)["admission_wait_reason"])
        status = concurrency.get_concurrency_status()
        self.assertEqual(1, status["global"]["occupied"])
        plan = next(row for row in status["types"] if row["key"] == "plan_check")
        self.assertIn("global_capacity", plan["blocked_by"])

    def test_full_account_carrier_is_observed_when_extract_carrier_has_free_slots(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        self.admit(self.queued("live_check"))
        waiting = self.queued("plan_check")
        self.dispatch_full(("live_check", "plan_check", "extract_link"), other_pool_slots=1)
        self.assertEqual(["global_capacity"], self.request(waiting["id"])["blocked_by"])
        self.assertEqual("queued", store.get_run(waiting["id"])["status"])

    def test_observed_type_wait_uses_free_global_budget_and_clears_after_owner_exits(self):
        self.policy(GLOBAL_TASK_WORKERS=3, ACCOUNT_PLAN_CHECK_WORKERS=1)
        active = self.admit(self.queued("plan_check"))
        waiting = self.queued("plan_check")
        self.dispatch_full(("plan_check",))
        self.assertEqual(["type_capacity"], self.request(waiting["id"])["blocked_by"])
        self.assertEqual(1, concurrency.get_concurrency_status()["global"]["occupied"])
        concurrency.release_execution(active)
        # 即使下个观察周期尚未开始，API 不可继续展示已经消退的类型满额。
        self.assertEqual([], store.get_run(waiting["id"])["admission_wait_reasons"])
        status = concurrency.get_concurrency_status()
        plan = next(row for row in status["types"] if row["key"] == "plan_check")
        self.assertNotIn("type_capacity", plan["blocked_by"])
        self.dispatch_full(("plan_check",))
        self.assertEqual(["executor_capacity"], self.request(waiting["id"])["blocked_by"])
        self.assertNotIn("global_capacity", self.request(waiting["id"])["blocked_by"])
        self.admit(store.get_run(waiting["id"]))
        self.assertIsNone(self.request(waiting["id"]))

    def test_observation_neither_moves_cursor_nor_enters_other_process_fairness(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        observed = self.queued("live_check")
        self.dispatch_full(("live_check",))
        self.assertEqual(["executor_capacity"], self.request(observed["id"])["blocked_by"])
        # 首轮按类型名称 live_check 在 plan_check 前；观察记录不能截走实际准入机会。
        self.admit(self.queued("plan_check"))

    def test_observing_a_snapshot_after_another_process_admitted_it_does_not_create_false_wait(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        stale = self.queued("plan_check")
        self.admit(stale)
        cursor = permits.dispatch_cursor()
        observed = task_gateway.observe_operation_run(stale)
        self.assertEqual(("execution_active",), observed.blocked_by)
        self.assertIsNone(self.request(stale["id"]))
        self.assertEqual(cursor, permits.dispatch_cursor())
        plan = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "plan_check")
        self.assertEqual([], plan["blocked_by"])

    def test_observer_never_rewrites_another_process_actual_fairness_request_or_claim_blocker(self):
        self.policy(GLOBAL_TASK_WORKERS=3)
        waiting = self.queued("plan_check")

        def account_busy(conn, execution_id):
            raise permits.ClaimUnavailable("account_busy")

        real = concurrency.try_admit_and_claim(execution_key=f"operation_run:{waiting['id']}", task_type="plan_check", claim=account_busy)
        self.assertEqual(("account_busy",), real.blocked_by)
        before = self.request(waiting["id"])
        self.assertFalse(before["observed_only"])
        task_gateway.observe_operation_run(waiting)
        self.assertEqual(before, self.request(waiting["id"]))
        self.assertEqual([{"code": "account_busy"}],store.get_run(waiting["id"])["admission_wait_reasons"])
        plan = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "plan_check")
        self.assertIn("account_busy",plan["blocked_by"])

    def test_unattempted_registration_queue_shows_current_capacity_without_lock_or_writes(self):
        self.policy(GLOBAL_TASK_WORKERS=1, REGISTRATION_PROTO2_WORKERS=1)
        admitted = concurrency.try_admit_and_claim(
            execution_key="registration_job:active", task_type="registration_proto2",
            batch_key="registration:容量观察", batch_limit=1,
            claim=lambda _conn, execution_id: {"execution_id": execution_id},
        )
        self.assertTrue(admitted.admitted)
        self.contexts.append(admitted.context)
        waiting_id = records.insert_row(records.JOBS, {
            "status": "pending", "job_type": "registration", "batch_id": "容量观察", "batch_workers": 1,
            "config_snapshot": {"registration_driver": "protocol_oss_2"},
        })
        with patch.object(permits, "admission_lock", side_effect=AssertionError("状态查询不应争抢准入锁")):
            status = concurrency.get_concurrency_status()
        proto = next(row for row in status["types"] if row["key"] == "registration_proto2")
        self.assertEqual(1, proto["queued"])
        self.assertEqual({"global_capacity", "type_capacity", "batch_capacity"}, set(proto["blocked_by"]))
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {postgres.qualified('operation_execution_requests')}")
            self.assertEqual(0, cur.fetchone()[0])
        self.assertEqual("pending", records.get_row(records.JOBS, waiting_id)["status"])
        self.policy(GLOBAL_TASK_WORKERS=2, REGISTRATION_PROTO2_WORKERS=2)
        proto = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "registration_proto2")
        self.assertEqual(["batch_capacity"], proto["blocked_by"])
        concurrency.release_execution(admitted.context)
        proto = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "registration_proto2")
        self.assertEqual([], proto["blocked_by"])

    def test_unattempted_registration_waits_clear_on_policy_increase_or_queue_removal(self):
        self.policy(GLOBAL_TASK_WORKERS=1, REGISTRATION_PROTO2_WORKERS=1)
        admitted = concurrency.try_admit_and_claim(
            execution_key="registration_job:active", task_type="registration_proto2",
            batch_key="registration:另一批次", batch_limit=1,
            claim=lambda _conn, execution_id: {"execution_id": execution_id},
        )
        self.assertTrue(admitted.admitted)
        self.contexts.append(admitted.context)
        waiting_id = records.insert_row(records.JOBS, {
            "status": "pending", "job_type": "registration", "batch_id": "未执行批次", "batch_workers": 1,
            "config_snapshot": {"registration_driver": "protocol_oss_2"},
        })
        proto = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "registration_proto2")
        self.assertEqual({"global_capacity", "type_capacity"}, set(proto["blocked_by"]))
        self.policy(GLOBAL_TASK_WORKERS=2, REGISTRATION_PROTO2_WORKERS=2)
        proto = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "registration_proto2")
        self.assertEqual([], proto["blocked_by"])
        self.policy(GLOBAL_TASK_WORKERS=1, REGISTRATION_PROTO2_WORKERS=1)
        records.patch_row(records.JOBS, waiting_id, {"status": "cancelled"})
        proto = next(row for row in concurrency.get_concurrency_status()["types"] if row["key"] == "registration_proto2")
        self.assertEqual(0, proto["queued"])
        self.assertEqual([], proto["blocked_by"])

    def test_loop_waits_for_the_poll_interval_after_full_carrier_observation(self):
        self.policy(GLOBAL_TASK_WORKERS=1)
        self.admit(self.queued("live_check"))
        self.queued("plan_check")
        full = SimpleNamespace(available_slots=lambda: 0, try_submit=Mock())
        wake = Mock()

        def wait_for_next_tick(interval):
            self.assertGreaterEqual(interval, .05)
            task_gateway._RUN_DISPATCH_STOP.set()

        wake.wait.side_effect = wait_for_next_tick
        handlers = {"plan_check": (Mock(), ("native_operations",))}
        task_gateway._RUN_DISPATCH_STOP.clear()
        try:
            with patch.object(task_gateway, "_executor", return_value=full), patch.dict(
                task_gateway._DISPATCH_HANDLERS, handlers, clear=True
            ), patch.object(task_gateway, "_RUN_DISPATCH_WAKE", wake), patch.object(
                task_gateway, "_recover_stale_runtime_runs_if_due"
            ):
                task_gateway._run_dispatch_loop()
            wake.wait.assert_called_once()
            wake.set.assert_not_called()
        finally:
            task_gateway._RUN_DISPATCH_STOP.clear()
