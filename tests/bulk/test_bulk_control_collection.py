"""真实 PostgreSQL 验证控制结算的集合写入与精确取消边界。"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from threading import Event
from unittest.mock import patch

from psycopg import Cursor

from core.bulk_operations import adapters
from core.storage import records
from core.storage.operations import bulk, bulk_control, bulk_runtime, store
from tests.support_pg import PostgresTestCase


class BulkControlCollectionTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"control-{index}@example.test", "access_token": "isolated-value",
             "status": "success"} for index in range(1, 121)
        ])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("core.bulk_operations.catalog.capture_settings",
            return_value={"config_revision": "control-test", "effective_settings": {}}))
        self.stack.enter_context(patch("core.operations.task_gateway.notify_dispatch"))
        self.stack.enter_context(patch("core.accounts.liveness.service.deployment_unavailable", return_value=None))

    def batch(self, ids, *, key="plan_check", submit=True):
        selection = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "ids", "ids": list(ids)}, operation_key=key, parameters={},
            config_revision="control-test", config_snapshot={
                "auto_refresh_at_enabled": True, "countries": ["JP"], "config_snapshot_revision": 1,
            })
        bulk.freeze_selection(selection["id"])
        batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
            selection_revision=1, operation_key=key, parameters={}, config_revision="control-test",
            max_concurrency=64)
        if submit:
            self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)["submitted"], len(ids))
        else:
            bulk.materialize_targets(batch["id"], limit=100)
        return batch

    def command(self, batch, *, action="cancel_not_started"):
        return bulk.request_control(batch["id"], request_key=uuid.uuid4().hex,
            action=action, expected_control_revision=1)

    def rows(self, name, *, where="TRUE", args=()):
        with store._connect() as conn, conn.cursor() as cur:
            order = "account_id,resource_family" if name == "account_operation_leases" else "id"
            cur.execute(f"SELECT * FROM {store._table(name)} WHERE {where} ORDER BY {order}", args)
            return [dict(row) for row in cur.fetchall()]

    def measure(self, command):
        statements = []
        original = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return original(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", measured):
            bulk.settle_control(command["id"], limit=100)
        return statements

    def test_hundred_queued_cancellations_have_constant_sql(self):
        small = self.batch([1])
        large = self.batch(list(range(2, 102)))
        one = self.measure(self.command(small))
        hundred = self.measure(self.command(large))
        print(f"控制结算 SQL：1 个目标={len(one)}，100 个目标={len(hundred)}")
        self.assertLessEqual(len(hundred), len(one) + 2,
            f"1个目标 {len(one)} SQL；100个目标 {len(hundred)} SQL")
        self.assertLessEqual(len(hundred), 50)
        self.assertEqual({row["status"] for row in self.rows("operation_runs")}, {"cancelled"})
        events = self.rows("operation_events", where="event_type='run.cancel_requested'")
        self.assertEqual(len(events), 101)

    def test_refresh_queue_release_is_precise_and_constant_sql(self):
        batch = self.batch([1, 2, 3], key="token_refresh")
        records.patch_row(records.ACCOUNTS, 2, changes={"live_check_queued_at": "newer-queue"})
        records.patch_row(records.ACCOUNTS, 3, changes={"live_check_trigger": "auto"})
        self.measure(self.command(batch))
        first = records.get_row(records.ACCOUNTS, 1)
        self.assertEqual(first["live_check_status"], "cancelled")
        self.assertFalse(first["live_check_ok"])
        self.assertEqual(first["live_check_error"], "批量任务取消未开始")
        self.assertEqual(records.get_row(records.ACCOUNTS, 2)["live_check_status"], "queued")
        self.assertEqual(records.get_row(records.ACCOUNTS, 3)["live_check_status"], "queued")

    def test_replay_keeps_one_event_and_revision_per_target(self):
        batch = self.batch([1, 2, 3])
        before = self.rows("operation_batch_target_rounds")
        command = self.command(batch)
        bulk.settle_control(command["id"])
        once = self.rows("operation_batch_target_rounds")
        bulk.settle_control(command["id"])
        bulk.settle_control(command["id"])
        self.assertEqual(self.rows("operation_batch_target_rounds"), once)
        self.assertEqual([row["source_revision"] for row in once],
                         [row["source_revision"] + 1 for row in before])
        self.assertEqual(len(self.rows("operation_events", where="event_type='run.cancel_requested'")), 3)
        outbox = self.rows("operation_projection_outbox")
        self.assertEqual(len({row["event_key"] for row in outbox}), len(outbox))
        bulk.project_pending()
        self.assertEqual(bulk.get_batch(batch["id"])["counts"]["cancelled"], 3)

    def test_scope_without_owned_runs_keeps_other_batch_untouched(self):
        selected = self.batch([1, 2], submit=False)
        other = self.batch([3, 4])
        before = self.rows("operation_runs", where="batch_id=%s", args=(other["id"],))
        bulk.settle_control(self.command(selected)["id"])
        self.assertEqual(self.rows("operation_runs", where="batch_id=%s", args=(other["id"],)), before)
        targets = self.rows("operation_batch_target_rounds", where="batch_id=%s", args=(selected["id"],))
        self.assertEqual({row["admission_state"] for row in targets}, {"cancelled"})
        self.assertEqual({row["chain_state"] for row in targets}, {"closed"})

    def test_external_blocker_run_is_not_cancelled(self):
        selected = self.batch([1], submit=False)
        self.batch([2])
        blocker = self.rows("operation_runs")[0]
        target = self.rows("operation_batch_target_rounds", where="batch_id=%s", args=(selected["id"],))[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('operation_batch_run_links')}
                (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,step_key,execution_generation,relation)
                VALUES (%s,%s,%s,%s,%s,'blocker',1,'external_blocker')""",
                (target["id"], blocker["task_id"], blocker["id"], blocker["task_id"], blocker["id"]))
        bulk.settle_control(self.command(selected)["id"])
        self.assertEqual(self.rows("operation_runs")[0], blocker)
        self.assertEqual(self.rows("operation_batch_target_rounds", where="id=%s",
            args=(target["id"],))[0]["admission_state"], "cancelled")

    def test_stop_running_is_cooperative_and_retains_lease(self):
        batch = self.batch([1, 2])
        runs = self.rows("operation_runs")
        claimed = store.claim_run(runs[0]["id"], execution_id="control-running-owner", worker_pid=1)
        self.assertEqual(claimed["status"], "running")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('account_operation_leases')}
                (account_id,resource_family,run_id,lease_token,expires_at)
                VALUES (1,'control-test',%s,%s,now()+interval '5 minutes')""",
                (runs[0]["id"], uuid.uuid4().hex))
        before = self.rows("account_operation_leases", where="run_id=%s", args=(runs[0]["id"],))
        bulk.settle_control(self.command(batch, action="request_stop")["id"])
        after = self.rows("operation_runs")
        self.assertEqual([row["status"] for row in after], ["cancelling", "cancelled"])
        self.assertIsNone(after[0]["completed_at"])
        leases = self.rows("account_operation_leases", where="run_id=%s", args=(runs[0]["id"],))
        self.assertTrue(leases)
        self.assertIsNotNone(leases[0]["cancel_requested_at"])
        self.assertEqual(leases[0]["lease_token"], before[0]["lease_token"])

    def test_cancel_not_started_skips_started_chain(self):
        batch = self.batch([1, 2])
        runs = self.rows("operation_runs")
        store.claim_run(runs[0]["id"], execution_id="control-started-owner", worker_pid=1)
        before = store.get_run(runs[0]["id"])
        bulk.settle_control(self.command(batch)["id"])
        self.assertEqual(store.get_run(runs[0]["id"]), before)
        self.assertEqual(store.get_run(runs[1]["id"])["status"], "cancelled")

    def test_control_blocks_claim_before_collection_settlement(self):
        batch = self.batch([1])
        run_id = self.rows("operation_runs")[0]["id"]
        command = self.command(batch)
        with self.assertRaises(bulk.BulkError):
            store.claim_run(run_id, execution_id="late-claim", worker_pid=1)
        self.assertEqual(store.get_run(run_id)["status"], "queued")
        bulk.settle_control(command["id"])
        self.assertEqual(store.get_run(run_id)["status"], "cancelled")

    def test_claim_wins_control_race_and_started_run_is_preserved(self):
        batch = self.batch([1])
        run_id = self.rows("operation_runs")[0]["id"]
        claimed_target = Event()
        release_claim = Event()
        control_waiting = Event()
        claim_original = bulk.ensure_managed_claim
        require_original = bulk_control.require_row

        def hold_claim(conn, selected_run_id):
            target = claim_original(conn, selected_run_id)
            claimed_target.set()
            if not release_claim.wait(10):
                raise RuntimeError("测试认领等待超时")
            return target

        def observe_control(cur, query, params=()):
            if "operation_batch_controls" in query and "FOR UPDATE" in query:
                control_waiting.set()
            return require_original(cur, query, params)

        with patch.object(bulk, "ensure_managed_claim", side_effect=hold_claim), \
                patch.object(bulk_control, "require_row", side_effect=observe_control), \
                ThreadPoolExecutor(max_workers=2) as pool:
            claim = pool.submit(store.claim_run, run_id, execution_id="claim-race-winner", worker_pid=1)
            try:
                self.assertTrue(claimed_target.wait(10))
                control = pool.submit(self.command, batch)
                self.assertTrue(control_waiting.wait(10))
            finally:
                release_claim.set()
            self.assertEqual(claim.result(timeout=10)["status"], "running")
            command = control.result(timeout=10)
        bulk.settle_control(command["id"])
        run = store.get_run(run_id)
        self.assertEqual(run["status"], "running")
        self.assertIsNone(run["cancel_requested_at"])

    def test_injected_callback_remains_supported(self):
        batch = self.batch([1, 2])
        called = []

        def cancel(run_id, *, reason, conn):
            called.append(run_id)
            return store.request_run_cancel(run_id, reason=reason, conn=conn)

        bulk.settle_control(self.command(batch)["id"], cancel_run=cancel)
        self.assertEqual(called, [row["id"] for row in self.rows("operation_runs")])
        self.assertEqual({row["status"] for row in self.rows("operation_runs")}, {"cancelled"})

    def test_outbox_failure_rolls_back_runs_events_accounts_and_cursor(self):
        batch = self.batch([1, 2], key="token_refresh")
        command = self.command(batch)
        before = self.rows("operation_batch_target_rounds")
        accounts = [records.get_row(records.ACCOUNTS, index) for index in (1, 2)]
        with patch.object(bulk_control, "record_managed_changes_many", side_effect=RuntimeError("outbox rollback")):
            with self.assertRaisesRegex(RuntimeError, "outbox rollback"):
                bulk.settle_control(command["id"])
        self.assertEqual({row["status"] for row in self.rows("operation_runs")}, {"queued"})
        self.assertEqual(self.rows("operation_events", where="event_type='run.cancel_requested'"), [])
        self.assertEqual(self.rows("operation_batch_target_rounds"), before)
        self.assertEqual([records.get_row(records.ACCOUNTS, index) for index in (1, 2)], accounts)
        self.assertEqual(self.rows("operation_batch_control_commands")[0]["settlement_cursor"], 0)
        bulk.settle_control(command["id"])
        self.assertEqual({row["status"] for row in self.rows("operation_runs")}, {"cancelled"})

    def test_round_control_does_not_cancel_previous_round(self):
        batch = self.batch([1, 2])
        before = self.rows("operation_runs")
        retry = bulk.create_round(batch["id"], request_key="control-only-second-round",
            source={"view": "current"}, selection={"kind": "all"})
        bulk.freeze_round(retry["id"])
        bulk.materialize_targets(batch["id"], limit=100)
        command = bulk.request_control(batch["id"], request_key="round-scoped-control",
            action="cancel_not_started", expected_control_revision=2, round_id=retry["id"])
        bulk.settle_control(command["id"])
        self.assertEqual(self.rows("operation_runs"), before)
        selected = self.rows("operation_batch_target_rounds", where="round_id=%s", args=(retry["id"],))
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["admission_state"] for row in selected}, {"cancelled"})
        self.assertEqual({row["chain_state"] for row in selected}, {"closed"})

    def test_many_fact_hook_deduplicates_ids_and_waits_for_current_parent_receipt(self):
        self.batch([1])
        run = self.rows("operation_runs")[0]
        task = self.rows("operation_tasks")[0]
        target = self.rows("operation_batch_target_rounds")[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET status='partial_success',started_at=now(),
                    result_summary='{{"awaiting_steps":["codex"]}}'::jsonb WHERE id=%s""", (run["id"],))
            cur.execute(f"""INSERT INTO {store._table('operation_task_dependencies')}
                (parent_source_system,parent_source_id,child_source_system,child_source_id,dependency_type,status,payload)
                VALUES (%s,%s,'test','old-child','account_completion','completed',%s::jsonb) RETURNING id""",
                (task["source_system"], task["source_id"], store._json({"parent_run_id": run["id"] - 1})))
            dependency_id = cur.fetchone()["id"]
            changed = bulk_runtime.record_managed_changes_many(conn, [target["id"], target["id"]])
        self.assertEqual(changed, {target["id"]: target["source_revision"] + 1})
        current = self.rows("operation_batch_target_rounds")[0]
        self.assertEqual(current["chain_state"], "started")
        self.assertIsNone(current["chain_closed_at"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_task_dependencies')} SET payload=%s::jsonb WHERE id=%s",
                (store._json({"parent_run_id": run["id"]}), dependency_id))
            bulk_runtime.record_managed_changes_many(conn, [target["id"]])
        self.assertEqual(self.rows("operation_batch_target_rounds")[0]["chain_state"], "closed")
