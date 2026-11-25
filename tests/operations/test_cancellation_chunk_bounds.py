"""取消集合的语句分块上限与调用方事务原子性。"""
from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from psycopg import Cursor

from core.storage import records
from core.storage.operations import bulk, bulk_submission, cancellation, common, legacy_task_store, schema
from tests.support_pg import PostgresTestCase


class CancellationChunkBoundsTests(PostgresTestCase):
    def setUp(self):
        records.init()
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        schema.init_operation_schema()

    def runs(self, count, *, accounts=(), targets=(), batch_id=None):
        prefix = uuid.uuid4().hex
        with common._connect() as conn:
            return bulk_submission.create_specs([
                {"task_type": "chunk_cancel", "account_id": accounts[index] if accounts else None, "email": "",
                 "resource_family": "inspection_snapshot", "source_id": f"{prefix}-{index}",
                 "batch_id": batch_id,
                 "data": {"bulk_target_round_id": targets[index], "force_refresh": True,
                          "live_check_queued_at": "original-queue"} if targets else {}}
                for index in range(count)
            ], conn=conn)

    def managed_runs(self, count):
        bulk.reset_ready()
        bulk.init()
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {records._qualified(records.ACCOUNTS)}
                    (email,created_at,updated_at,live_check_status,data)
                    SELECT %s||n||'@example.test',%s,%s,'queued',%s::jsonb
                    FROM generate_series(1,%s) n RETURNING id""",
                (uuid.uuid4().hex, records._now(), records._now(), json.dumps({
                    "status": "success", "access_token": "isolated-value",
                    "live_check_queued_at": "original-queue", "live_check_trigger": "manual_bulk",
                }), count),
            )
            accounts = sorted(row["id"] for row in cur.fetchall())
        with patch("core.bulk_operations.catalog.capture_settings", return_value={
                "config_revision": "chunk-test", "effective_settings": {}}):
            selection = bulk.create_selection(
                request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": accounts},
                operation_key="plan_check", parameters={}, config_revision="chunk-test")
            bulk.freeze_selection(selection["id"])
            batch = bulk.create_batch(
                request_key=uuid.uuid4().hex, selection_id=selection["id"], selection_revision=1,
                operation_key="plan_check", parameters={}, config_revision="chunk-test", max_concurrency=1)
        targets = []
        while len(targets) < count:
            materialized = bulk.materialize_targets(batch["id"], limit=100)
            self.assertTrue(materialized, "fixture必须完整物化所有受管目标")
            targets.extend(row["id"] for row in materialized)
        runs = self.runs(count, accounts=accounts, targets=targets, batch_id=batch["id"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO {common._table('operation_batch_run_links')}
                    (target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,
                     step_key,execution_generation,relation)
                    SELECT target_id,task_id,run_id,task_id,run_id,'chunk_cancel',1,'owned_root'
                    FROM jsonb_to_recordset(%s::jsonb) AS item(target_id bigint,task_id bigint,run_id bigint)""",
                (json.dumps([{"target_id": target, "task_id": run["task_id"], "run_id": run["run_id"]}
                             for target, run in zip(targets, runs, strict=True)]),),
            )
            cur.execute(
                f"""UPDATE {common._table('operation_batch_target_rounds')}
                    SET admission_state='submitted' WHERE id=ANY(%s)""", (targets,))
            cur.execute(
                f"""INSERT INTO {common._table('account_operation_leases')}
                    (account_id,resource_family,run_id,lease_token,expires_at)
                    SELECT account_id,resource_family,id,'chunk-lease-'||id,now()+interval '5 minutes'
                    FROM {common._table('operation_runs')} WHERE id=ANY(%s)""",
                ([row["run_id"] for row in runs],),
            )
        return runs, accounts, targets

    @staticmethod
    def requests(runs):
        return [{"id": row["run_id"], "expected_status": "queued", "reason": "chunk test"} for row in runs]

    def test_501_cancellations_never_send_more_than_500_json_rows(self):
        runs = self.runs(501)
        sizes = []
        execute = Cursor.execute

        def bounded(cursor, query, params=None, **kwargs):
            if "jsonb_to_recordset" in str(query):
                for value in params or ():
                    if isinstance(value, str) and value.startswith("["):
                        size = len(json.loads(value))
                        sizes.append(size)
                        self.assertLessEqual(size, 500, "取消语句超过500条")
            return execute(cursor, query, params, **kwargs)

        with common._connect() as conn, patch.object(Cursor, "execute", bounded):
            replies = cancellation.cancel_runs_many(conn, self.requests(runs))
        self.assertEqual(len(replies), 501)
        self.assertEqual({row["status"] for row in replies.values()}, {"cancelled"})
        self.assertEqual(sorted(sizes), [1, 500])

    @staticmethod
    def mutation_kind(query):
        if "jsonb_to_recordset" not in query:
            return None
        if "expected_status text,event_uuid text" in query:
            return "cancel"
        if "AS item(account_id bigint,queued_at text)" in query:
            return "release"
        if "source_revision=target.source_revision+1" in query:
            return "managed"
        return None

    def test_managed_501_bounds_all_writes_after_global_prelocks_and_preserves_release_cas(self):
        runs, accounts, targets = self.managed_runs(501)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {records._qualified(records.ACCOUNTS)} SET data=data||%s::jsonb WHERE id=%s",
                (json.dumps({"live_check_queued_at": "newer-queue"}), accounts[0]))
            cur.execute(
                f"UPDATE {records._qualified(records.ACCOUNTS)} SET data=data||%s::jsonb WHERE id=%s",
                (json.dumps({"live_check_trigger": "auto"}), accounts[1]))
        sizes = {"cancel": [], "release": [], "managed": []}
        prelocks = []
        execute = Cursor.execute

        def bounded(cursor, query, params=None, **kwargs):
            text = str(query)
            if not sizes["cancel"] and "FOR UPDATE" in text:
                prelocks.append((text, params))
            kind = self.mutation_kind(text)
            if kind:
                for value in params or ():
                    if isinstance(value, str) and value.startswith("["):
                        size = len(json.loads(value))
                        sizes[kind].append(size)
                        self.assertLessEqual(size, 500, f"{kind}语句超过500条")
            return execute(cursor, query, params, **kwargs)

        with common._connect() as conn, patch.object(Cursor, "execute", bounded):
            replies = cancellation.cancel_runs_many(conn, self.requests(runs)[::-1])
        self.assertEqual(sizes, {"cancel": [500, 1], "release": [500, 1], "managed": [500, 1]})
        self.assertEqual(len(prelocks), 4)
        self.assertIn("FOR UPDATE OF target", prelocks[0][0])
        for position, table in enumerate(("registered_accounts", "operation_tasks", "operation_runs"), 1):
            self.assertIn(f'"{table}"', prelocks[position][0])
        self.assertEqual([len(params[0]) for _, params in prelocks], [501, 501, 501, 501])
        self.assertTrue(all(row["status"] == "cancelled" for row in replies.values()))
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,live_check_status FROM {records._qualified(records.ACCOUNTS)} "
                        "WHERE id=ANY(%s) ORDER BY id", (accounts,))
            statuses = list(cur.fetchall())
            self.assertEqual([row["live_check_status"] for row in statuses[:2]], ["queued", "queued"])
            self.assertEqual({row["live_check_status"] for row in statuses[2:]}, {"cancelled"})
            cur.execute(f"SELECT source_revision,chain_state FROM {common._table('operation_batch_target_rounds')} "
                        "WHERE id=ANY(%s)", (targets,))
            self.assertEqual({(row["source_revision"], row["chain_state"]) for row in cur.fetchall()}, {(1, "closed")})
            cur.execute(f"SELECT target_round_id FROM {common._table('operation_projection_outbox')} "
                        "WHERE target_round_id=ANY(%s)", (targets,))
            self.assertEqual(sorted(row["target_round_id"] for row in cur.fetchall()), sorted(targets))

    def snapshot(self, runs, accounts, targets, *, conn):
        run_ids = [row["run_id"] for row in runs]
        task_ids = [row["task_id"] for row in runs]
        queries = [
            (f"SELECT id,status,cancel_requested_at,completed_at FROM {common._table('operation_runs')} "
             "WHERE id=ANY(%s) ORDER BY id", run_ids),
            (f"SELECT id,status,current_stage,completed_at FROM {common._table('operation_tasks')} "
             "WHERE id=ANY(%s) ORDER BY id", task_ids),
            (f"SELECT run_id,lease_token,cancel_requested_at FROM {common._table('account_operation_leases')} "
             "WHERE run_id=ANY(%s) ORDER BY run_id", run_ids),
            (f"SELECT id,live_check_status,data FROM {records._qualified(records.ACCOUNTS)} "
             "WHERE id=ANY(%s) ORDER BY id", accounts),
            (f"SELECT id,source_revision,chain_state,chain_closed_at FROM "
             f"{common._table('operation_batch_target_rounds')} WHERE id=ANY(%s) ORDER BY id", targets),
            (f"SELECT run_id FROM {common._table('operation_events')} "
             "WHERE run_id=ANY(%s) AND event_type='run.cancel_requested' ORDER BY run_id", run_ids),
            (f"SELECT target_round_id,source_revision FROM {common._table('operation_projection_outbox')} "
             "WHERE target_round_id=ANY(%s) ORDER BY target_round_id,source_revision", targets),
        ]
        result = []
        with conn.cursor() as cur:
            for query, ids in queries:
                cur.execute(query, (ids,))
                result.append(list(cur.fetchall()))
        return result

    def test_second_chunk_failure_rolls_back_entire_wave_but_keeps_caller_note(self):
        for stage in ("cancel", "release", "managed"):
            with self.subTest(stage=stage):
                runs, accounts, targets = self.managed_runs(501)
                note_id = records.insert_row(records.ACCOUNTS, {"email": f"note-{uuid.uuid4().hex}@example.test"})
                execute = Cursor.execute
                writes = 0

                def fail_second(cursor, query, params=None, **kwargs):
                    nonlocal writes
                    if self.mutation_kind(str(query)) == stage:
                        writes += 1
                        if writes == 2:
                            raise RuntimeError("second chunk failed")
                    return execute(cursor, query, params, **kwargs)

                with common._connect() as conn:
                    before = self.snapshot(runs, accounts, targets, conn=conn)
                    conn.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
                        SET data=data||'{{"caller_note":"keep me"}}'::jsonb WHERE id=%s""", (note_id,))
                    with patch.object(Cursor, "execute", fail_second):
                        with self.assertRaisesRegex(RuntimeError, "second chunk failed"):
                            cancellation.cancel_runs_many(conn, self.requests(runs))
                    self.assertEqual(writes, 2)
                    self.assertEqual(self.snapshot(runs, accounts, targets, conn=conn), before)
                    self.assertEqual(conn.execute(f"""SELECT data->>'caller_note' AS note
                        FROM {records._qualified(records.ACCOUNTS)} WHERE id=%s""", (note_id,)).fetchone()["note"],
                        "keep me")
                with common._connect() as conn:
                    self.assertEqual(self.snapshot(runs, accounts, targets, conn=conn), before)
                    self.assertEqual(conn.execute(f"""SELECT data->>'caller_note' AS note
                        FROM {records._qualified(records.ACCOUNTS)} WHERE id=%s""", (note_id,)).fetchone()["note"],
                        "keep me")

    def test_managed_targets_publish_once_even_when_all_run_cas_checks_are_skipped(self):
        runs, _, targets = self.managed_runs(501)
        requests = self.requests(runs)
        for item in requests:
            item["expected_status"] = "running"
        with common._connect() as conn:
            replies = cancellation.cancel_runs_many(conn, requests)
        self.assertTrue(all(row.get("cancel_skipped") and row["status"] == "queued" for row in replies.values()))
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT source_revision,chain_state FROM {common._table('operation_batch_target_rounds')} "
                        "WHERE id=ANY(%s)", (targets,))
            self.assertEqual({(row["source_revision"], row["chain_state"]) for row in cur.fetchall()},
                             {(1, "not_started")})
            cur.execute(f"SELECT target_round_id FROM {common._table('operation_projection_outbox')} "
                        "WHERE target_round_id=ANY(%s)", (targets,))
            self.assertEqual(sorted(row["target_round_id"] for row in cur.fetchall()), sorted(targets))
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_events')} "
                        "WHERE run_id=ANY(%s) AND event_type='run.cancel_requested'",
                        ([row["run_id"] for row in runs],))
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_idle_connection_retains_caller_rollback_authority_over_all_chunks(self):
        runs = self.runs(501)
        with common._connect() as conn:
            cancellation.cancel_runs_many(conn, self.requests(runs))
            conn.rollback()
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status,cancel_requested_at FROM {common._table('operation_runs')} "
                        "WHERE id=ANY(%s)", ([row["run_id"] for row in runs],))
            self.assertEqual({(row["status"], row["cancel_requested_at"]) for row in cur.fetchall()}, {("queued", None)})

    def test_same_task_across_chunks_uses_largest_changed_run_for_task_projection(self):
        runs = self.runs(501)
        shared_task = runs[0]["task_id"]
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {common._table('operation_runs')} SET task_id=%s,run_no=2,status='running',
                started_at=now() WHERE id=%s""", (shared_task, runs[-1]["run_id"]))
        requests = self.requests(runs)
        requests[-1]["expected_status"] = "running"
        with common._connect() as conn:
            replies = cancellation.cancel_runs_many(conn, requests[::-1])
        self.assertEqual(replies[runs[0]["run_id"]]["status"], "cancelled")
        self.assertEqual(replies[runs[-1]["run_id"]]["status"], "cancelling")
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status,current_stage,completed_at FROM {common._table('operation_tasks')} WHERE id=%s",
                        (shared_task,))
            self.assertEqual(dict(cur.fetchone()), {
                "status": "cancelling", "current_stage": "cancelling", "completed_at": None})
