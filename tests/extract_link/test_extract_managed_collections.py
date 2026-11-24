"""受管提链原单续接也必须集合锁定、继承和收口父任务。"""
import json
import os
import uuid
from unittest.mock import patch
from contextlib import nullcontext

from psycopg import Cursor

from core.extract_link import workbench_bulk
from core.storage.extract_link import jobs
from core.storage.operations import bulk, store as operation
from tests.extract_link import test_extract_workbench_bulk as fixtures
from tests.support_pg import PostgresTestCase


class ExtractManagedCollectionTests(PostgresTestCase):
    accounts = fixtures.ExtractWorkbenchBulkTests.accounts
    finished_task = fixtures.ExtractWorkbenchBulkTests.finished_task
    provider_patches = fixtures.ExtractWorkbenchBulkTests.provider_patches

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.previous = os.environ.get("OPERATION_TASK_DB_SCHEMA")
        os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.schema
        operation.reset_ready()

    @classmethod
    def tearDownClass(cls):
        operation.reset_ready()
        if cls.previous is None:
            os.environ.pop("OPERATION_TASK_DB_SCHEMA", None)
        else:
            os.environ["OPERATION_TASK_DB_SCHEMA"] = cls.previous
        super().tearDownClass()

    def setUp(self):
        operation.init()
        bulk.reset_ready()
        bulk.init()

    def managed_sources(self, count, *, parents=False):
        account_ids = self.accounts([{"email": f"managed-{uuid.uuid4().hex}@example.test"} for _ in range(count)])
        tasks = [self.finished_task(account_id) for account_id in account_ids]
        for task in tasks:
            jobs.save_provider_job(task["run"]["id"], "legacy", f"original-{task['id']}",
                {"payment_state": "succeeded"}, {"job_secret": f"private-original-{task['id']}"})
        with patch("core.bulk_operations.catalog.capture_settings", return_value={
                "config_revision": "frozen-config", "effective_settings": {}}):
            selection = bulk.create_selection(request_key=uuid.uuid4().hex,
                source={"kind": "ids", "ids": account_ids}, operation_key="plan_check", parameters={},
                config_revision="frozen-config")
            selection = bulk.freeze_selection(selection["id"])
            batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
                selection_revision=1, operation_key="plan_check", parameters={}, config_revision="frozen-config",
                max_concurrency=1)
        bulk.materialize_targets(batch["id"], limit=count)
        parent_ids = []
        if parents:
            for task in tasks:
                parent = operation.create_runtime_task(task_type="account_completion", account_id=None,
                    email="", resource_family="completion_coordinator")
                parent_ids.append(parent["id"])
                with operation._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {operation._table('operation_runs')} SET status='success' WHERE id=%s",
                                (parent["run"]["id"],))
                    cur.execute(f"UPDATE {operation._table('operation_tasks')} SET status='success' WHERE id=%s",
                                (parent["id"],))
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {operation._table('operation_batch_target_rounds')} "
                        "WHERE batch_id=%s ORDER BY ordinal", (batch["id"],))
            targets = [row["id"] for row in cur.fetchall()]
            for index, (task, target_id) in enumerate(zip(tasks, targets, strict=True)):
                cur.execute(f"UPDATE {operation._table('operation_batch_target_rounds')} SET "
                            "admission_state='submitted',chain_state='started',chain_started_at=now(),"
                            "next_execution_generation=2 WHERE id=%s", (target_id,))
                cur.execute(f"UPDATE {operation._table('operation_runs')} SET batch_id=%s,"
                            "data=data||%s::jsonb WHERE id=%s",
                            (batch["id"], json.dumps({"bulk_target_round_id": target_id, "frozen_provider": "original"}),
                             task["run"]["id"]))
                cur.execute(f"INSERT INTO {operation._table('operation_batch_run_links')} "
                            "(target_round_id,task_id,run_id,task_id_snapshot,run_id_snapshot,"
                            "step_key,execution_generation,relation) VALUES (%s,%s,%s,%s,%s,'extract_link',1,'owned_root')",
                            (target_id, task["id"], task["run"]["id"], task["id"], task["run"]["id"]))
                if parents:
                    cur.execute(f"UPDATE {operation._table('operation_tasks')} SET parent_task_id=%s WHERE id=%s",
                                (parent_ids[index], task["id"]))
        return tasks, targets, parent_ids

    def submit_measured(self, tasks):
        statements = []
        execute = Cursor.execute

        def capture(cursor, query, *args, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        with self.provider_patches(), operation._connect() as conn, patch.object(Cursor, "execute", capture):
            result = workbench_bulk.sync_status_many([str(task["id"]) for task in tasks], {}, conn=conn)
        return result, statements

    def test_twenty_managed_sources_keep_ownership_with_bounded_sql(self):
        single, _, _ = self.managed_sources(1)
        _, single_statements = self.submit_measured(single)
        tasks, targets, _ = self.managed_sources(20)
        result, statements = self.submit_measured(tasks)
        self.assertTrue(all(row.status == "updated" for row in result))
        self.assertLessEqual(len(statements), 30, f"{len(statements)} SQL")
        self.assertLessEqual(len(statements), len(single_statements) + 1)
        for task, target_id, receipt in zip(tasks, targets, result, strict=True):
            run = operation.get_run(receipt.data["run_id"])
            self.assertEqual(run["data"]["bulk_target_round_id"], target_id)
            self.assertEqual(run["data"]["provider_job_run_id"], task["run"]["id"])
            self.assertEqual(run["data"]["frozen_provider"], "original")
            self.assertEqual(jobs.get_provider_job_private(run["id"])["private_data"]["job_secret"],
                             f"private-original-{task['id']}")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT target_round_id,execution_generation,relation FROM "
                        f"{operation._table('operation_batch_run_links')} WHERE run_id=ANY(%s) ORDER BY target_round_id",
                        ([item.data["run_id"] for item in result],))
            links = list(cur.fetchall())
            self.assertEqual([row["target_round_id"] for row in links], targets)
            self.assertEqual({row["execution_generation"] for row in links}, {2})
            self.assertEqual({row["relation"] for row in links}, {"owned_continuation"})

    def test_twenty_parent_sources_reopen_parents_in_collection(self):
        tasks, _, parent_ids = self.managed_sources(20, parents=True)
        result, statements = self.submit_measured(tasks)
        self.assertTrue(all(row.status == "updated" for row in result))
        self.assertLessEqual(len(statements), 48, f"{len(statements)} SQL")
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status FROM {operation._table('operation_tasks')} WHERE id=ANY(%s)", (parent_ids,))
            self.assertEqual({row["status"] for row in cur.fetchall()}, {"waiting"})

    def test_inheritance_failure_rolls_back_all_new_runs_and_provider_copies(self):
        from core.storage.operations import bulk_runtime

        tasks, targets, _ = self.managed_sources(3)
        with patch.object(bulk_runtime, "record_managed_changes_many", side_effect=RuntimeError("synthetic projection failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic projection failure"):
                self.submit_measured(tasks)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 3)
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('extract_link_provider_jobs')}")
            self.assertEqual(cur.fetchone()["n"], 3)
            cur.execute(f"SELECT next_execution_generation FROM "
                        f"{operation._table('operation_batch_target_rounds')} WHERE id=ANY(%s)", (targets,))
            self.assertEqual({row["next_execution_generation"] for row in cur.fetchall()}, {2})

    def test_python_failure_in_borrowed_transaction_keeps_no_partial_inheritance(self):
        from core.storage.operations import bulk_runtime

        tasks, _, _ = self.managed_sources(2)
        with operation._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TEMP TABLE caller_sentinel(value integer)")
                cur.execute("INSERT INTO caller_sentinel VALUES (7)")
            with (
                self.provider_patches(),
                patch.object(operation, "_connect", return_value=nullcontext(conn)),
                patch.object(bulk_runtime, "record_managed_changes_many", side_effect=RuntimeError("synthetic rollback")),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
                    workbench_bulk.sync_status_many([str(task["id"]) for task in tasks], {}, conn=conn)
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_runs')}")
                self.assertEqual(cur.fetchone()["n"], 2)
                cur.execute("SELECT value FROM caller_sentinel")
                self.assertEqual(cur.fetchone()["value"], 7)

    def test_idle_borrowed_connection_keeps_the_wave_in_the_callers_transaction(self):
        from core.storage.extract_link import workbench_bulk as storage

        tasks, _, _ = self.managed_sources(1)
        with self.provider_patches():
            snapshot = storage.read_snapshots([tasks[0]["id"]])[tasks[0]["id"]]
            prepared, _, _ = workbench_bulk._prepare_sync(snapshot)
        self.assertIsNotNone(prepared)
        with operation._connect() as conn:
            storage.retry_sync_many([prepared], conn=conn)
            conn.rollback()
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 1)

    def test_parent_transition_does_not_wait_back_on_the_selected_account(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        tasks, _, parents = self.managed_sources(1, parents=True)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT last_run_id FROM {operation._table('operation_tasks')} WHERE id=%s",
                        (parents[0],))
            parent_run_id = cur.fetchone()["last_run_id"]
        parent_locked, retry_reaches_parent = Event(), Event()
        execute = Cursor.execute

        def parent_transition():
            with operation._connect() as conn, conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='2s'")
                cur.execute(f"SELECT id FROM {operation._table('operation_runs')} WHERE id=%s FOR UPDATE",
                            (parent_run_id,))
                parent_locked.set()
                if not retry_reaches_parent.wait(5):
                    raise RuntimeError("sync did not reach the parent")
                from core.storage import records
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=%s FOR UPDATE",
                            (tasks[0]["account_id"],))

        def observed(cursor, query, *args, **kwargs):
            if "operation_runs" in str(query) and "FOR UPDATE" in str(query):
                retry_reaches_parent.set()
            return execute(cursor, query, *args, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            transition = pool.submit(parent_transition)
            try:
                self.assertTrue(parent_locked.wait(5))
                with (
                    self.provider_patches(), operation._connect() as conn,
                    patch.object(Cursor, "execute", observed),
                ):
                    conn.execute("SET LOCAL lock_timeout='2s'")
                    replies = workbench_bulk.sync_status_many([str(tasks[0]["id"])], {}, conn=conn)
                self.assertEqual(replies[0].status, "updated")
            finally:
                retry_reaches_parent.set()
            transition.result(timeout=10)

    def test_locked_account_or_task_only_skips_its_source(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        from core.storage import records

        for locked_table in ("account", "task"):
            with self.subTest(locked_table=locked_table):
                tasks, _, _ = self.managed_sources(2, parents=True)
                locked, release = Event(), Event()

                def hold_single_lock():
                    with operation._connect() as conn, conn.cursor() as cur:
                        table = (records._qualified(records.ACCOUNTS) if locked_table == "account"
                                 else operation._table("operation_tasks"))
                        row_id = tasks[0]["account_id"] if locked_table == "account" else tasks[0]["id"]
                        cur.execute(f"SELECT id FROM {table} WHERE id=%s FOR UPDATE", (row_id,))
                        locked.set()
                        if not release.wait(5):
                            raise RuntimeError("single source lock wait expired")

                with ThreadPoolExecutor(max_workers=1) as pool:
                    held = pool.submit(hold_single_lock)
                    try:
                        self.assertTrue(locked.wait(5))
                        with self.provider_patches(), operation._connect() as conn:
                            conn.execute("SET LOCAL lock_timeout='200ms'")
                            replies = workbench_bulk.sync_status_many(
                                [str(task["id"]) for task in tasks], {}, conn=conn,
                            )
                        self.assertEqual([reply.status for reply in replies], ["skipped", "updated"])
                    finally:
                        release.set()
                    held.result(timeout=10)
