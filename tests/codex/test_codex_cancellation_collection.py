"""停止 Codex 的集合取消事实、状态竞争及事务边界。"""
import json
import uuid
from unittest.mock import patch

from psycopg import Cursor

from core.codex import bulk_submission as service
from core.bulk_operations import adapters
from core.storage import records
from core.storage.codex import bulk_submission as storage
from core.storage.operations import bulk, bulk_runtime, bulk_submission as shared, cancellation, common, schema, store as operations
from tests.support_pg import PostgresTestCase


class CodexCancellationCollectionTests(PostgresTestCase):
    def setUp(self):
        self.seed(records.ACCOUNTS, [
            {"id": number, "email": f"stop-{number}@example.test"} for number in range(1, 23)
        ])
        schema.init_operation_schema()

    def create_runs(self, account_ids):
        with common._connect() as conn:
            batch = shared.create_batch(conn=conn, task_type="codex_retry",
                requested_count=len(account_ids), trigger="fixture", title="停止测试")
            runs = shared.create_specs([
                {"task_type": "codex_retry", "account_id": number,
                 "email": f"stop-{number}@example.test", "source_id": f"stop-fixture-{number}",
                 "batch_id": batch["id"], "data": {}}
                for number in account_ids
            ], conn=conn)
            storage.project_queued(conn, runs)
        return runs

    def test_cancel_sql_is_bounded_for_twenty_runs_and_does_not_call_single_cancel(self):
        self.create_runs(list(range(1, 22)))
        execute = Cursor.execute
        counts = []
        for ids in ([1], list(range(2, 22))):
            queries = []
            def count(cursor, query, *args, **kwargs):
                queries.append(str(query))
                return execute(cursor, query, *args, **kwargs)
            with patch.object(Cursor, "execute", count), \
                 patch("core.storage.operations.runtime.request_run_cancel", side_effect=AssertionError("single cancel")):
                result = service.cancel_reauthorization(account_ids=ids)
            self.assertEqual(len(ids), result["stopped_count"])
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])
        self.assertLessEqual(counts[1], 14)
        print(f"Codex 同批取消 SQL：1 Run={counts[0]}，20 Runs={counts[1]}")

    def test_cancel_sql_is_bounded_across_twenty_distinct_batches(self):
        for number in range(1, 22):
            self.create_runs([number])
        execute = Cursor.execute
        counts = []
        for ids in ([1], list(range(2, 22))):
            queries = []
            def count(cursor, query, *args, **kwargs):
                queries.append(str(query))
                return execute(cursor, query, *args, **kwargs)
            with patch.object(Cursor, "execute", count):
                result = service.cancel_reauthorization(account_ids=ids)
            self.assertEqual(len(ids), result["stopped_count"])
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])
        print(f"Codex 跨批取消 SQL：1 batch={counts[0]}，20 batches={counts[1]}")
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status,cancelled_count FROM {common._table('operation_batches')}")
            batches = cur.fetchall()
        self.assertEqual([("stopped", 1)] * 21, [(row["status"], row["cancelled_count"]) for row in batches])

    def test_email_resolution_does_not_cancel_other_accounts_with_the_same_email(self):
        runs = self.create_runs([1, 2])
        records.patch_row(records.ACCOUNTS, 1, {"email": "Duplicate@example.test"})
        records.patch_row(records.ACCOUNTS, 2, {"email": "duplicate@example.test"})
        result = service.cancel_reauthorization(emails=["duplicate@example.test"])
        self.assertEqual(1, result["stopped_count"])
        self.assertEqual(2, result["stopped"][0]["id"])
        self.assertEqual(["queued", "cancelled"], [
            operations.get_run(run["run_id"])["status"] for run in runs
        ])

    def test_mixed_queued_and_active_preserves_remote_evidence_and_flags_existing_leases(self):
        runs = self.create_runs([1, 2, 3])
        evidence = {"remote_intent": {"kind": "remote_write", "state": "started"},
                    "remote_receipt": {"state": "request_unknown"}}
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET status='running',started_at=now(),"
                        "data=data || %s::jsonb WHERE id=%s", (json.dumps(evidence), runs[1]["run_id"]))
            cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='running' WHERE id=%s",
                        (runs[1]["task_id"],))
            cur.execute(f"INSERT INTO {common._table('account_operation_leases')} "
                        "(account_id,resource_family,run_id,lease_token,expires_at) "
                        "VALUES (2,'openai_interactive',%s,'fixture-stop-lease',now()+interval '1 hour')",
                        (runs[1]["run_id"],))
        result = service.cancel_reauthorization(account_ids=[1, 2])
        self.assertEqual(2, result["stopped_count"])
        self.assertEqual([False, True], [item["running"] for item in result["stopped"]])
        self.assertEqual(["cancelled", "cancelling", "queued"], [
            operations.get_run(item["run_id"])["status"] for item in runs
        ])
        active = operations.get_run(runs[1]["run_id"])
        self.assertEqual(evidence, {key: active["data"][key] for key in evidence})
        self.assertIsNone(active["completed_at"])
        self.assertIsNotNone(active["started_at"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT cancel_requested_at,lease_token FROM {common._table('account_operation_leases')}")
            lease = cur.fetchone()
            self.assertIsNotNone(lease["cancel_requested_at"])
            self.assertEqual("fixture-stop-lease", lease["lease_token"])
            cur.execute(f"SELECT run_id,detail FROM {common._table('operation_events')} "
                        "WHERE event_type='run.cancel_requested' ORDER BY run_id")
            events = cur.fetchall()
        self.assertEqual([
            (runs[0]["run_id"], {"previous_status": "queued", "status": "cancelled"}),
            (runs[1]["run_id"], {"previous_status": "running", "status": "cancelling"}),
        ], [(event["run_id"], event["detail"]) for event in events])

    def test_status_changes_and_late_runs_are_skipped_without_new_cancel_events(self):
        original = self.create_runs([1, 2])
        prefetched = storage.reauthorization_runs
        late_runs = []

        def mutate_after_prefetch(conn, account_ids):
            selected = prefetched(conn, account_ids)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {common._table('operation_runs')} SET status='running',started_at=now() WHERE id=%s",
                            (original[0]["run_id"],))
                cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='running' WHERE id=%s",
                            (original[0]["task_id"],))
                cur.execute(f"UPDATE {common._table('operation_runs')} SET status='success' WHERE id=%s",
                            (original[1]["run_id"],))
                cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='success' WHERE id=%s",
                            (original[1]["task_id"],))
            late_runs.append(operations.retry_runtime_task(
                original[1]["task_id"], expected_previous_run_id=original[1]["run_id"], conn=conn,
            ))
            return selected

        with patch.object(storage, "reauthorization_runs", side_effect=mutate_after_prefetch):
            result = service.cancel_reauthorization(account_ids=[1, 2])
        self.assertEqual(0, result["stopped_count"])
        self.assertEqual(["run_state_changed"] * 2, [item["reason_code"] for item in result["skipped"]])
        self.assertEqual("queued", operations.get_run(late_runs[0]["id"])["status"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_events')} "
                        "WHERE event_type='run.cancel_requested'")
            self.assertEqual(0, cur.fetchone()["n"])

    def test_shared_cancel_preserves_per_run_reasons_and_terminal_idempotence(self):
        runs = self.create_runs([1, 2, 3])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET status='success' WHERE id=%s",
                        (runs[2]["run_id"],))
            cur.execute(f"UPDATE {common._table('operation_tasks')} SET status='success' WHERE id=%s",
                        (runs[2]["task_id"],))
            result = cancellation.cancel_runs_many(conn, [
                {"id": runs[0]["run_id"], "expected_status": "queued", "reason": "reason-one"},
                {"id": runs[1]["run_id"], "expected_status": "queued", "reason": "reason-two"},
                {"id": runs[2]["run_id"], "expected_status": "success", "reason": "ignored"},
            ])
        self.assertEqual("success", result[runs[2]["run_id"]]["status"])
        self.assertFalse(result[runs[2]["run_id"]].get("cancel_skipped"))
        self.assertEqual(["reason-one", "reason-two", None], [
            operations.get_run(run["run_id"])["cancel_reason"] for run in runs
        ])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT message FROM {common._table('operation_events')} "
                        "WHERE event_type='run.cancel_requested' ORDER BY run_id")
            self.assertEqual(["reason-one", "reason-two"], [row["message"] for row in cur.fetchall()])

    def test_shared_cancel_uses_native_event_source_for_empty_historical_source(self):
        run = self.create_runs([1])[0]
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET source_system='' WHERE id=%s",
                        (run["run_id"],))
            cancellation.cancel_runs_many(conn, [
                {"id": run["run_id"], "expected_status": "queued", "reason": "fixture"},
            ])
            cur.execute(f"SELECT source_system FROM {common._table('operation_events')} "
                        "WHERE event_type='run.cancel_requested'")
            self.assertEqual("native_operations", cur.fetchone()["source_system"])

    def test_missing_exact_run_is_reported_missing(self):
        original = self.create_runs([1])[0]
        with common._connect() as conn:
            result = cancellation.cancel_runs_many(conn, [
                {"id": original["run_id"] + 99, "expected_status": "queued", "reason": "fixture"},
            ])
        self.assertEqual({original["run_id"] + 99: None}, result)
        self.assertEqual("queued", operations.get_run(original["run_id"])["status"])

    def test_projection_failure_rolls_back_all_cancel_facts(self):
        original = self.create_runs([1, 2])
        with patch.object(storage, "project_cancel_requested", side_effect=RuntimeError("projection failed")):
            with self.assertRaises(RuntimeError):
                service.cancel_reauthorization(account_ids=[1, 2])
        self.assertEqual(["queued", "queued"], [
            operations.get_run(item["run_id"])["status"] for item in original
        ])

    def test_inner_failure_rolls_back_cancel_facts_but_retains_outer_write(self):
        original = self.create_runs([1, 2])
        with common._connect() as conn, conn.cursor() as cur:
            records.patch_row(records.ACCOUNTS, 22, {"note": "caller-write"}, conn=conn)
            execute = Cursor.execute
            def fail_after_mutation(cursor, query, *args, **kwargs):
                result = execute(cursor, query, *args, **kwargs)
                if "WITH input AS" in str(query) and "run.cancel_requested" in str(query):
                    raise RuntimeError("after cancel SQL")
                return result
            with patch.object(Cursor, "execute", fail_after_mutation):
                with self.assertRaises(RuntimeError):
                    cancellation.cancel_runs_many(conn, [
                        {"id": item["run_id"], "expected_status": "queued", "reason": "fixture"}
                        for item in original
                    ])
        self.assertEqual("caller-write", records.get_row(records.ACCOUNTS, 22)["note"])
        self.assertEqual(["queued", "queued"], [
            operations.get_run(item["run_id"])["status"] for item in original
        ])

    def test_managed_cancellation_has_bounded_sql_and_updates_only_selected_target_facts(self):
        bulk.reset_ready()
        bulk.init()
        records.patch_rows_where(records.ACCOUNTS, changes={"access_token": "fixture-at"},
                                where="id=ANY(%s)", params=(list(range(1, 23)),))
        selection = bulk.create_selection(request_key=uuid.uuid4().hex,
            source={"kind": "ids", "ids": list(range(1, 23))}, operation_key="codex_retry",
            parameters={}, config_revision="fixture", config_snapshot={"oauth_driver": "protocol"})
        bulk.freeze_selection(selection["id"])
        with patch("core.bulk_operations.catalog.capture_settings",
                   return_value={"config_revision": "fixture", "effective_settings": {}}):
            batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
                selection_revision=1, operation_key="codex_retry", parameters={}, config_revision="fixture",
                max_concurrency=50)
        with patch("core.codex.operation_service._deployment_unavailable", return_value=None), \
             patch("core.codex.operation_service._feature_ready", return_value=(True, "")), \
             patch("core.operations.task_gateway.notify_dispatch"):
            self.assertEqual(22, bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)["submitted"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,source_revision FROM {common._table('operation_batch_target_rounds')} ORDER BY id")
            before = cur.fetchall()
        execute = Cursor.execute
        counts = []
        for ids in ([1], list(range(2, 22))):
            queries = []
            def count(cursor, query, *args, **kwargs):
                queries.append(str(query))
                return execute(cursor, query, *args, **kwargs)
            with patch.object(Cursor, "execute", count), \
                 patch("core.storage.operations.runtime.request_run_cancel", side_effect=AssertionError("single cancel")), \
                 patch.object(bulk_runtime, "record_managed_change", side_effect=AssertionError("single fact hook")):
                result = service.cancel_reauthorization(account_ids=ids)
            self.assertEqual(len(ids), result["stopped_count"])
            counts.append(len(queries))
        self.assertEqual(counts[0], counts[1])
        self.assertLessEqual(counts[1], 25)
        print(f"受管 Codex 取消 SQL：1 Run={counts[0]}，20 Runs={counts[1]}")
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,source_revision,chain_state FROM {common._table('operation_batch_target_rounds')} ORDER BY id")
            after = cur.fetchall()
        self.assertEqual([item["source_revision"] + (index < 21) for index, item in enumerate(before)],
                         [item["source_revision"] for item in after])
        self.assertEqual(["closed"] * 21 + ["not_started"], [item["chain_state"] for item in after])

