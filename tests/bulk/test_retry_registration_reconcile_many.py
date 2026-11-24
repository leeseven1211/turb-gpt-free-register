"""注册补密码父任务的集合收口保持原事实、代次与投影规则。"""
from unittest.mock import patch

from core.storage import records
from core.storage.operations import store
from core.storage.operations.bulk_retry_registration import reconcile_registration_many as reconcile_many
from tests.support_pg import PostgresTestCase


class RegistrationReconcileManyTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"handoff-{index}@example.test", "access_token": "isolated-at",
             "extra_json": {"account_password": "isolated-password", "account_password_state": "confirmed"}}
            for index in range(1, 31)
        ])

    def fixture(self, count=1, *, job_status="partial_success", child_status="queued", batch=True):
        batch_row = store.create_runtime_batch(batch_type="registration_resume", title="isolated",
            requested_count=count) if batch else None
        pairs = []
        for index in range(1, count + 1):
            job_id = records.insert_row(records.JOBS, {"email": f"handoff-{index}@example.test",
                "account_id": index, "status": job_status, "job_type": "registration_resume"})
            parent = store.create_runtime_task(task_type="registration_resume", account_id=index,
                email=f"handoff-{index}@example.test", source_system="registration_chains",
                source_id=str(job_id), resource_family="registration_chain",
                batch_id=batch_row["id"] if batch_row else None)
            child = store.create_runtime_task(task_type="password_setup", account_id=index,
                email=f"handoff-{index}@example.test", source_system="webui_runtime",
                resource_family="registration_completion",
                data={"registration_completion": True, "steps": ["password"]})
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"""UPDATE {store._table('operation_runs')}
                    SET status='partial_success',source_id=%s,
                        data=%s::jsonb,result_summary='{{"prior_fact":"preserved"}}'::jsonb,
                        error_message='old error',completed_at=now()
                    WHERE id=%s""", (str(job_id), store._json({"completion_handoff": {
                        "task_id": child["id"], "run_id": child["run"]["id"], "remaining_error": ""}}),
                        parent["run"]["id"]))
                cur.execute(f"""UPDATE {store._table('operation_tasks')}
                    SET status='partial_success',completed_at=now() WHERE id=%s""", (parent["id"],))
                cur.execute(f"""UPDATE {store._table('operation_runs')}
                    SET status=%s,completed_at=CASE WHEN %s='queued' THEN NULL ELSE now() END
                    WHERE id=%s""", (child_status, child_status, child["run"]["id"]))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status=%s WHERE id=%s",
                            (child_status, child["id"]))
            pairs.append({"job_id": job_id, "parent": parent, "child": child})
        return pairs, batch_row

    def snapshot(self, conn, run_id):
        with conn.cursor() as cur:
            cur.execute(f"""SELECT r.status,r.progress_stage,r.error_code,r.error_message,
                r.result_summary,r.completed_at,t.status AS task_status,t.current_stage,
                t.target_status,t.next_actions,t.last_run_id
                FROM {store._table('operation_runs')} r
                JOIN {store._table('operation_tasks')} t ON t.id=r.task_id WHERE r.id=%s""", (run_id,))
            return dict(cur.fetchone())

    def test_twenty_handoffs_reconcile_with_bounded_sql_and_one_projection_queue(self):
        from psycopg import Cursor
        pairs, batch = self.fixture(20)
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur:
            with patch.object(Cursor, "execute", measured):
                reconcile_many(cur, child_task_ids=[pair["child"]["id"] for pair in pairs])
            self.assertLessEqual(len(statements), 15, f"{len(statements)} SQL")
            for pair in pairs:
                row = self.snapshot(conn, pair["parent"]["run"]["id"])
                self.assertEqual(row["status"], "waiting")
                self.assertEqual(row["task_status"], "waiting")
                self.assertEqual(row["target_status"], "account_available")
                self.assertEqual(row["result_summary"]["prior_fact"], "preserved")
                self.assertEqual(row["result_summary"]["completion_handoff"]["status"], "queued")
                self.assertEqual(row["result_summary"]["completion_handoff"]["run_id"],
                                 pair["child"]["run"]["id"])
                self.assertIsNone(row["completed_at"])
            cur.execute(f"SELECT batch_id,status,reason FROM {store._table('operation_projection_queue')}")
            self.assertEqual(list(cur.fetchall()), [{"batch_id": batch["id"], "status": "queued",
                                                     "reason": "registration_completion"}])
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_events')} WHERE event_type='task.completion_updated'")
            self.assertEqual(cur.fetchone()["n"], 20)

    def test_child_success_requires_confirmed_password_evidence(self):
        pairs, _ = self.fixture(3, child_status="success", batch=False)
        with store._connect() as conn, conn.cursor() as cur:
            records.patch_row(records.ACCOUNTS, 2, {"extra_json": {"account_password": "candidate",
                "account_password_state": "candidate"}}, conn=conn)
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET data=jsonb_set(data,'{{completion_handoff,remaining_error}}','"postprocessing still pending"'::jsonb)
                WHERE id=%s""", (pairs[2]["parent"]["run"]["id"],))
            reconcile_many(cur, child_task_ids=[pair["child"]["id"] for pair in pairs])
            rows = [self.snapshot(conn, pair["parent"]["run"]["id"]) for pair in pairs]
            self.assertEqual([row["status"] for row in rows], ["success", "partial_success", "partial_success"])
            self.assertIn("registration_completion_incomplete", rows[1]["error_message"])
            self.assertEqual(rows[2]["error_message"], "postprocessing still pending")
            self.assertEqual(rows[0]["next_actions"], [])
            self.assertEqual(rows[1]["next_actions"][0]["action"], "retry")

    def test_original_job_and_task_type_gates_do_not_reopen_ineligible_parents(self):
        pairs, _ = self.fixture(7, batch=False)
        with store._connect() as conn, conn.cursor() as cur:
            for pair, status in zip(pairs, ["success", "partial_success", "failed", "cancelled",
                                         "running", "pending", "success"], strict=True):
                records.patch_row(records.JOBS, pair["job_id"], {"status": status}, conn=conn)
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET task_type='registration' WHERE id=%s",
                        (pairs[-1]["parent"]["id"],))
            reconcile_many(cur, child_task_ids=[pair["child"]["id"] for pair in pairs])
            rows = [self.snapshot(conn, pair["parent"]["run"]["id"]) for pair in pairs]
            self.assertEqual([row["status"] for row in rows],
                             ["waiting", "waiting", "partial_success", "partial_success",
                              "partial_success", "partial_success", "partial_success"])
            for row in rows[2:]:
                self.assertEqual(row["result_summary"], {"prior_fact": "preserved"})
                self.assertEqual(row["error_message"], "old error")

    def test_failed_child_error_and_idempotent_event_match_original(self):
        pairs, _ = self.fixture(1, child_status="failed", batch=False)
        pair = pairs[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')} SET error_category='remote',
                error_code='isolated_child_failure',error_message='child operation failed' WHERE id=%s""",
                (pair["child"]["run"]["id"],))
            reconcile_many(cur, parent_run_ids=[pair["parent"]["run"]["id"]])
            first = self.snapshot(conn, pair["parent"]["run"]["id"])
            self.assertEqual(first["status"], "partial_success")
            self.assertEqual(first["error_code"], "isolated_child_failure")
            self.assertEqual(first["error_message"], "child operation failed")
            self.assertEqual(first["result_summary"]["child_tasks"][0]["error_code"], "isolated_child_failure")
            self.assertIsNotNone(first["completed_at"])
            reconcile_many(cur, child_task_ids=[pair["child"]["id"]], parent_run_ids=[pair["parent"]["run"]["id"]])
            cur.execute(f"""SELECT count(*) AS n FROM {store._table('operation_events')}
                WHERE run_id=%s AND event_type='task.completion_updated'""", (pair["parent"]["run"]["id"],))
            self.assertEqual(cur.fetchone()["n"], 1)

    def test_running_projection_queue_keeps_current_writer_and_marks_dirty(self):
        pairs, batch = self.fixture(1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('operation_projection_queue')}
                (batch_id,status,available_at,completed_at,last_error,dirty)
                VALUES (%s,'running','2020-01-01T00:00:00Z','2020-01-02T00:00:00Z','old writer failure',FALSE)""",
                (batch["id"],))
            cur.execute(f"""UPDATE {store._table('operation_batches')} SET projection_status='running',
                projection_error='old batch error',projection_next_retry_at=now() WHERE id=%s""", (batch["id"],))
            result = reconcile_many(cur, child_task_ids=[pairs[0]["child"]["id"]])
            self.assertEqual(result, {batch["id"]})
            cur.execute(f"SELECT * FROM {store._table('operation_projection_queue')} WHERE batch_id=%s", (batch["id"],))
            queue = dict(cur.fetchone())
            self.assertEqual(queue["status"], "running")
            self.assertTrue(queue["dirty"])
            self.assertEqual(queue["available_at"].year, 2020)
            self.assertEqual(queue["completed_at"].day, 2)
            self.assertEqual(queue["last_error"], "old writer failure")
            self.assertEqual(queue["source_system"], "registration_completion")
            self.assertEqual(queue["source_id"], str(pairs[0]["parent"]["run"]["id"]))
            cur.execute(f"SELECT projection_status,projection_error,projection_next_retry_at FROM {store._table('operation_batches')} WHERE id=%s",
                        (batch["id"],))
            self.assertEqual(dict(cur.fetchone()), {"projection_status": "running",
                "projection_error": "old batch error", "projection_next_retry_at": None})

    def test_last_run_is_rechecked_after_queue_and_before_parent_fact_write(self):
        from psycopg import Cursor
        from core.storage.operations import runtime
        pairs, batch = self.fixture(1)
        pair = pairs[0]
        with store._connect() as conn, conn.cursor() as cur:
            newer = runtime._insert_runtime_run(cur, task_id=pair["parent"]["id"], run_no=2,
                source_system="registration_chains", account_id=1, batch_id=batch["id"],
                resource_family="registration_chain", data={"later_fact": "untouched"})
        execute = Cursor.execute
        changed = False

        def supersede_before_parent_lock(cursor, query, params=None, **kwargs):
            nonlocal changed
            if (not changed and str(query).startswith(f"SELECT id FROM {store._table('operation_runs')}")
                    and "FOR UPDATE" in str(query)):
                changed = True
                with store._connect() as other, other.cursor() as update:
                    update.execute(f"UPDATE {store._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
                                   (newer["id"], pair["parent"]["id"]))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", supersede_before_parent_lock):
            result = reconcile_many(cur, parent_run_ids=[pair["parent"]["run"]["id"]])
            self.assertEqual(result, {batch["id"]})
            old = self.snapshot(conn, pair["parent"]["run"]["id"])
            self.assertEqual(old["status"], "partial_success")
            self.assertEqual(old["result_summary"], {"prior_fact": "preserved"})
            self.assertEqual(old["last_run_id"], newer["id"])
            cur.execute(f"SELECT data,status FROM {store._table('operation_runs')} WHERE id=%s", (newer["id"],))
            self.assertEqual(dict(cur.fetchone()), {"data": {"later_fact": "untouched"}, "status": "queued"})

    def test_event_failure_rolls_back_parent_and_projection_queue(self):
        from psycopg import Cursor
        pairs, batch = self.fixture(2)
        execute = Cursor.execute

        def fail_event(cursor, query, params=None, **kwargs):
            if str(query).startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("isolated registration event failure")
            return execute(cursor, query, params, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "isolated registration event failure"):
            with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", fail_event):
                reconcile_many(cur, child_task_ids=[pair["child"]["id"] for pair in pairs])
        with store._connect() as conn, conn.cursor() as cur:
            self.assertEqual([self.snapshot(conn, pair["parent"]["run"]["id"])["status"] for pair in pairs],
                             ["partial_success", "partial_success"])
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_projection_queue')} WHERE batch_id=%s",
                        (batch["id"],))
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_projection_writer_and_reconcile_share_queue_then_batch_lock_order(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from psycopg import Cursor
        pairs, batch = self.fixture(1)
        queued, reconcile_started = threading.Event(), threading.Event()
        execute = Cursor.execute
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {store._table('operation_projection_queue')} (batch_id) VALUES (%s)",
                        (batch["id"],))

        def projection_writer():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_projection_queue')} WHERE batch_id=%s FOR UPDATE",
                            (batch["id"],))
                queued.set()
                if not reconcile_started.wait(10):
                    raise RuntimeError("reconciler did not reach queue")
                cur.execute(f"SELECT id FROM {store._table('operation_batches')} WHERE id=%s FOR UPDATE",
                            (batch["id"],))
                cur.execute(f"""UPDATE {store._table('operation_projection_queue')}
                    SET status='running',worker_id='isolated-writer' WHERE batch_id=%s""", (batch["id"],))

        def observed(cursor, query, params=None, **kwargs):
            if str(query).startswith(f"INSERT INTO {store._table('operation_projection_queue')}"):
                reconcile_started.set()
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(projection_writer)
            self.assertTrue(queued.wait(10))
            try:
                with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", observed):
                    reconcile_many(cur, child_task_ids=[pairs[0]["child"]["id"]])
            finally:
                reconcile_started.set()
            writer.result(timeout=10)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT status,dirty,worker_id FROM {store._table('operation_projection_queue')} WHERE batch_id=%s",
                        (batch["id"],))
            self.assertEqual(dict(cur.fetchone()), {"status": "running", "dirty": True, "worker_id": "isolated-writer"})

    def test_five_hundred_and_one_parent_results_are_written_in_bounded_chunks(self):
        import json
        from psycopg import Cursor
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {records._qualified(records.JOBS)}
                (id,created_at,updated_at,status,data)
                SELECT n,now()::text,now()::text,'partial_success','{{}}'::jsonb
                FROM generate_series(1,501) n""")
            children = store.create_runtime_tasks_many([
                {"task_type": "password_setup", "account_id": index, "email": f"chunk-{index}@example.test",
                 "source_system": "webui_runtime", "source_id": f"child-{index}",
                 "resource_family": "registration_completion",
                 "data": {"bulk_target_round_id": index}}
                for index in range(1, 502)], conn=conn)
            parents = store.create_runtime_tasks_many([
                {"task_type": "registration_resume", "account_id": index, "email": f"chunk-{index}@example.test",
                 "source_system": "registration_chains", "source_id": str(index),
                 "resource_family": "registration_chain",
                 "data": {"bulk_target_round_id": index + 1000, "completion_handoff": {
                    "task_id": children[index - 1]["task_id"], "run_id": children[index - 1]["run_id"]}}}
                for index in range(1, 502)], conn=conn)
            cur.execute(f"""UPDATE {store._table('operation_runs')} r
                SET source_id=t.source_id,status='partial_success'
                FROM {store._table('operation_tasks')} t WHERE t.id=r.task_id AND t.task_type='registration_resume'""")
            payload_sizes = []
            execute = Cursor.execute

            def measured(cursor, query, params=None, **kwargs):
                if "jsonb_to_recordset" in str(query):
                    for value in params or ():
                        if isinstance(value, str) and value.startswith("["):
                            payload_sizes.append(len(json.loads(value)))
                return execute(cursor, query, params, **kwargs)

            with patch.object(Cursor, "execute", measured):
                reconcile_many(cur, child_task_ids=[row["task_id"] for row in children])
            self.assertEqual(max(payload_sizes), 500)
            self.assertIn(1, payload_sizes)
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')} WHERE id=ANY(%s) AND status='waiting'",
                        ([row["run_id"] for row in parents],))
            self.assertEqual(cur.fetchone()["n"], 501)

    def test_batch_foreign_key_readers_do_not_block_queue_then_batch_reconciliation(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from psycopg import Cursor
        pairs, batch = self.fixture(1)
        foreign_key_locked, queue_locked = threading.Event(), threading.Event()
        execute = Cursor.execute
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {store._table('operation_projection_queue')} (batch_id) VALUES (%s)",
                        (batch["id"],))

        def concurrent_batch_member():
            with store._connect() as conn, conn.cursor() as cur:
                # 与并发INSERT operation_runs(batch_id)产生的FK锁相同。
                cur.execute(f"SELECT id FROM {store._table('operation_batches')} WHERE id=%s FOR KEY SHARE",
                            (batch["id"],))
                foreign_key_locked.set()
                if not queue_locked.wait(10):
                    raise RuntimeError("reconciler did not acquire projection queue")
                cur.execute(f"SELECT id FROM {store._table('operation_projection_queue')} WHERE batch_id=%s FOR UPDATE",
                            (batch["id"],))

        def observed(cursor, query, params=None, **kwargs):
            result = execute(cursor, query, params, **kwargs)
            if str(query).startswith(f"INSERT INTO {store._table('operation_projection_queue')}"):
                queue_locked.set()
            return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(concurrent_batch_member)
            self.assertTrue(foreign_key_locked.wait(10))
            try:
                with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", observed):
                    reconcile_many(cur, child_task_ids=[pairs[0]["child"]["id"]])
            finally:
                queue_locked.set()
            writer.result(timeout=10)
        with store._connect() as conn:
            self.assertEqual(self.snapshot(conn, pairs[0]["parent"]["run"]["id"])["status"], "waiting")

    def test_legacy_advisory_refresh_and_reconciliation_keep_same_batch_lock_order(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from psycopg import Cursor
        from core.storage.operations.bulk_retry_projection import refresh_batches_many
        pairs, batch = self.fixture(1)
        advisory_locked, enqueue_ready = threading.Event(), threading.Event()
        execute = Cursor.execute

        def concurrent_legacy_refresh():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (batch["id"],))
                advisory_locked.set()
                if not enqueue_ready.wait(10):
                    raise RuntimeError("reconciler did not reach batch lock")
                cur.execute(f"SELECT id FROM {store._table('operation_batches')} WHERE id=%s FOR NO KEY UPDATE",
                            (batch["id"],))

        def observed(cursor, query, params=None, **kwargs):
            statement = str(query)
            if "pg_advisory_xact_lock" in statement:
                enqueue_ready.set()
            result = execute(cursor, query, params, **kwargs)
            if statement.lstrip().startswith(f"UPDATE {store._table('operation_batches')}"):
                enqueue_ready.set()
            return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(concurrent_legacy_refresh)
            self.assertTrue(advisory_locked.wait(10))
            try:
                with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", observed):
                    batches = reconcile_many(cur, child_task_ids=[pairs[0]["child"]["id"]])
                    refresh_batches_many(cur, batches)
            finally:
                enqueue_ready.set()
            writer.result(timeout=10)
