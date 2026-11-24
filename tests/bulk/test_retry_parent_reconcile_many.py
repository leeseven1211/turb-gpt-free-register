"""批量重试后的父任务收口保持原审计和定长巡检摘要。"""
import json
from unittest.mock import patch

from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class RetryParentReconcileManyTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()

    def make_pair(self, index=1, *, parent_type="account_completion", parent_status="partial_success",
                  child_status="queued", source="native_operations", parent_data=None):
        parent = store.create_runtime_task(task_type=parent_type, account_id=None,
            email=f"parent-{index}@example.test", source_system=source, source_id=f"parent-{index}",
            resource_family="completion_coordinator", data=parent_data or {})
        child = store.create_runtime_task(task_type="twofa_setup", account_id=index,
            email=f"child-{index}@example.test", parent_task_id=None,
            source_system="webui_runtime", source_id=f"child-{index}",
            data={"failure_stage": "old-stage", "failure_message": "isolated failure"})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_tasks')}
                SET status=%s,completed_at=now(),error_code='parent_prior_code' WHERE id=%s""",
                (parent_status, parent["id"]))
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET status=%s,completed_at=now(),result_summary='{{"old_audit":"retained"}}'::jsonb WHERE id=%s""",
                (parent_status, parent["run"]["id"]))
            cur.execute(f"""UPDATE {store._table('operation_tasks')}
                SET parent_task_id=%s,status=%s WHERE id=%s""", (parent["id"], child_status, child["id"]))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                        (child_status, child["run"]["id"]))
        return parent, child

    def reconcile(self, cur, parent_ids, child_ids=()):
        from core.storage.operations.bulk_retry_reconcile import reconcile_parents_many
        return reconcile_parents_many(cur, parent_ids, child_task_ids=child_ids)

    def test_twenty_parent_reopens_are_collection_and_preserve_old_terminal_audit(self):
        from psycopg import Cursor
        pairs = [self.make_pair(index) for index in range(1, 21)]
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", measured):
            result = self.reconcile(cur, [parent["id"] for parent, _ in pairs],
                                    [child["id"] for _, child in pairs])
        self.assertEqual(result, {"batch_ids": set(), "registration_run_ids": set()})
        self.assertLessEqual(len(statements), 12, f"{len(statements)} SQL")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT t.id,t.status,t.target_status,t.current_stage,t.error_code,t.completed_at,
                    t.next_actions,r.id AS run_id,r.run_no,r.status AS run_status,r.result_summary,
                    old.id AS old_run_id,old.status AS old_status,old.result_summary AS old_summary
                FROM {store._table('operation_tasks')} t
                JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id
                JOIN {store._table('operation_runs')} old ON old.task_id=t.id AND old.run_no=1
                WHERE t.id=ANY(%s) ORDER BY t.id""", ([parent["id"] for parent, _ in pairs],))
            rows = list(cur.fetchall())
            self.assertEqual(len(rows), 20)
            for row, (parent, child) in zip(rows, pairs, strict=True):
                self.assertEqual(row["status"], "waiting")
                self.assertEqual(row["target_status"], "pending")
                self.assertEqual(row["current_stage"], "waiting")
                self.assertIsNone(row["completed_at"])
                self.assertEqual(row["error_code"], "parent_prior_code")
                self.assertEqual(row["run_no"], 2)
                self.assertEqual(row["run_status"], "waiting")
                self.assertEqual(row["old_run_id"], parent["run"]["id"])
                self.assertEqual(row["old_status"], "partial_success")
                self.assertEqual(row["old_summary"], {"old_audit": "retained"})
                self.assertEqual(row["result_summary"]["children"], {str(child["id"]): "queued"})
                child_summary = row["result_summary"]["child_tasks"][0]
                self.assertEqual(child_summary["run_id"], child["run"]["id"])
                self.assertEqual(child_summary["failure_stage"], "old-stage")
                self.assertEqual(child_summary["error_message"], "isolated failure")
            cur.execute(f"""SELECT event_type,count(*) AS n FROM {store._table('operation_events')}
                WHERE task_id=ANY(%s) AND event_type IN ('run.waiting','task.waiting_for_child')
                GROUP BY event_type ORDER BY event_type""", ([parent["id"] for parent, _ in pairs],))
            self.assertEqual(list(cur.fetchall()), [
                {"event_type": "run.waiting", "n": 20}, {"event_type": "task.waiting_for_child", "n": 20}])

    def test_state_priorities_match_original_parent_reconcile(self):
        cases = [
            ("success", "success", "completed"),
            ("deactivated", "deactivated", "account_deactivated"),
            ("attention_required", "attention_required", "attention_required"),
            ("failed", "partial_success", "attention_required"),
            ("queued", "waiting", "pending"),
        ]
        pairs = [self.make_pair(index, parent_status="waiting", child_status=status)
                 for index, (status, _, _) in enumerate(cases, 1)]
        with store._connect() as conn, conn.cursor() as cur:
            self.reconcile(cur, [parent["id"] for parent, _ in pairs])
            cur.execute(f"SELECT status,target_status FROM {store._table('operation_tasks')} WHERE id=ANY(%s) ORDER BY id",
                        ([parent["id"] for parent, _ in pairs],))
            self.assertEqual(list(cur.fetchall()), [
                {"status": desired, "target_status": target} for _, desired, target in cases])
            cur.execute(f"SELECT status FROM {store._table('operation_runs')} WHERE id=ANY(%s) ORDER BY id",
                        ([parent["run"]["id"] for parent, _ in pairs],))
            self.assertEqual([row["status"] for row in cur.fetchall()], [desired for _, desired, _ in cases])

    def test_terminal_parent_run_is_not_rewritten_when_children_already_terminal(self):
        parent, _ = self.make_pair(child_status="success")
        with store._connect() as conn, conn.cursor() as cur:
            self.reconcile(cur, [parent["id"]])
            cur.execute(f"SELECT status FROM {store._table('operation_tasks')} WHERE id=%s", (parent["id"],))
            self.assertEqual(cur.fetchone()["status"], "success")
            cur.execute(f"SELECT status,result_summary FROM {store._table('operation_runs')} WHERE id=%s",
                        (parent["run"]["id"],))
            self.assertEqual(dict(cur.fetchone()), {"status": "partial_success", "result_summary": {"old_audit": "retained"}})

    def test_registration_parent_handoff_and_automatic_child_are_delegated_before_locks(self):
        direct, child = self.make_pair(index=1, source="registration_chains",
            parent_type="registration_resume", parent_data={"completion_handoff": {"task_id": 7}})
        automatic, auto_child = self.make_pair(index=2, source="registration_chains",
            parent_type="registration_resume")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_tasks')}
                SET data=data || '{{"registration_completion":true}}'::jsonb WHERE id=%s""", (auto_child["id"],))
            result = self.reconcile(cur, [direct["id"], automatic["id"]], [child["id"], auto_child["id"]])
            self.assertEqual(result, {"batch_ids": set(),
                "registration_run_ids": {direct["run"]["id"], automatic["run"]["id"]}})
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')} WHERE task_id=ANY(%s)",
                        ([direct["id"], automatic["id"]],))
            self.assertEqual(cur.fetchone()["n"], 2)

    def test_waiting_coordinator_releases_lease_on_its_current_run(self):
        parent, _ = self.make_pair(parent_status="waiting")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('account_operation_leases')}
                (account_id,resource_family,run_id,lease_token,expires_at)
                VALUES (77,'completion_coordinator',%s,'lease',now()+interval '1 hour')""",
                (parent["run"]["id"],))
            self.reconcile(cur, [parent["id"]])
            cur.execute(f"SELECT count(*) AS n FROM {store._table('account_operation_leases')} WHERE run_id=%s",
                        (parent["run"]["id"],))
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_inspection_parent_keeps_fixed_count_summary_and_reopens_audit(self):
        parent, child = self.make_pair(parent_type="account_inspection_batch")
        with store._connect() as conn, conn.cursor() as cur:
            self.reconcile(cur, [parent["id"]], [child["id"]])
            cur.execute(f"""SELECT t.status,t.next_actions,r.run_no,r.result_summary
                FROM {store._table('operation_tasks')} t JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id
                WHERE t.id=%s""", (parent["id"],))
            row = cur.fetchone()
            self.assertEqual(row["status"], "waiting")
            self.assertEqual(row["run_no"], 2)
            self.assertEqual(row["result_summary"], {"child_count": 1, "processed_count": 0, "failed_count": 0})
            self.assertEqual(row["next_actions"], [{"action": "cancel", "label": "停止巡检"}])

    def test_inspection_current_run_replaces_previous_summary_with_fixed_counts(self):
        parent, child = self.make_pair(parent_type="account_inspection_batch", parent_status="waiting")
        with store._connect() as conn, conn.cursor() as cur:
            self.reconcile(cur, [parent["id"]], [child["id"]])
            cur.execute(f"SELECT result_summary FROM {store._table('operation_runs')} WHERE id=%s",
                        (parent["run"]["id"],))
            self.assertEqual(cur.fetchone()["result_summary"],
                             {"child_count": 1, "processed_count": 0, "failed_count": 0})

    def test_parent_summary_hints_and_unknown_refresh_follow_original_rules(self):
        parent, child = self.make_pair(parent_status="waiting", child_status="failed")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET task_type='token_refresh' WHERE id=%s",
                        (child["id"],))
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET result_summary=%s::jsonb,error_code='remote_unknown' WHERE id=%s""",
                (json.dumps({"outcome": "request_unknown", "cause_code": "password_page_error",
                    "failure_stage": "refresh-password", "failure_event_id": "event-7"}), child["run"]["id"]))
            self.reconcile(cur, [parent["id"]])
            cur.execute(f"""SELECT t.status,r.result_summary FROM {store._table('operation_tasks')} t
                JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id WHERE t.id=%s""", (parent["id"],))
            row = cur.fetchone()
            self.assertEqual(row["status"], "attention_required")
            hints = row["result_summary"]["child_tasks"][0]
            self.assertEqual(hints["failure_stage"], "refresh-password")
            self.assertEqual(hints["failure_event_id"], "event-7")
            self.assertEqual(hints["error_code"], "remote_unknown")

    def test_concurrent_parent_generation_change_is_not_overwritten(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from psycopg import Cursor
        from core.storage.operations import runtime
        parent, _ = self.make_pair()
        run_locked, observed = threading.Event(), threading.Event()
        execute = Cursor.execute

        def replace_generation():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE",
                            (parent["run"]["id"],))
                run_locked.set()
                if not observed.wait(10):
                    raise RuntimeError("reconciler did not observe parent")
                replacement = runtime._insert_runtime_run(cur, task_id=parent["id"], run_no=2,
                    source_system="native_operations", account_id=None, batch_id=None,
                    resource_family="completion_coordinator", task_uuid=parent["task_uuid"],
                    data={"new_generation": True}, initial_status="waiting")
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET last_run_id=%s WHERE id=%s",
                            (replacement["id"], parent["id"]))
                return replacement["id"]

        def measured(cursor, query, params=None, **kwargs):
            if "WHERE id=ANY(%s) ORDER BY id FOR UPDATE" in str(query) and "operation_runs" in str(query):
                observed.set()
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(replace_generation)
            self.assertTrue(run_locked.wait(10))
            try:
                with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", measured):
                    result = self.reconcile(cur, [parent["id"]])
            finally:
                observed.set()
            replacement_id = worker.result(timeout=10)
        self.assertEqual(result, {"batch_ids": set(), "registration_run_ids": set()})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT last_run_id,status FROM {store._table('operation_tasks')} WHERE id=%s", (parent["id"],))
            self.assertEqual(dict(cur.fetchone()), {"last_run_id": replacement_id, "status": "partial_success"})
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')} WHERE task_id=%s", (parent["id"],))
            self.assertEqual(cur.fetchone()["n"], 2)

    def test_parent_write_failure_rolls_back_new_run_and_task_projection(self):
        from psycopg import Cursor
        parent, _ = self.make_pair()
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            if "UPDATE" in str(query) and "operation_tasks" in str(query) and "next_actions=s.actions" in str(query):
                raise RuntimeError("isolated parent task failure")
            return execute(cursor, query, params, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "isolated parent task failure"):
            with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", measured):
                self.reconcile(cur, [parent["id"]])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT last_run_id,status FROM {store._table('operation_tasks')} WHERE id=%s", (parent["id"],))
            self.assertEqual(dict(cur.fetchone()), {"last_run_id": parent["run"]["id"], "status": "partial_success"})
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')} WHERE task_id=%s", (parent["id"],))
            self.assertEqual(cur.fetchone()["n"], 1)

    def test_five_hundred_and_one_parent_reopens_split_sql_payloads(self):
        from psycopg import Cursor
        pairs = [self.make_pair(index) for index in range(1, 502)]
        sizes = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            if "jsonb_to_recordset" in str(query):
                for value in params or ():
                    if isinstance(value, str) and value.startswith("["):
                        sizes.append(len(json.loads(value)))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, conn.cursor() as cur, patch.object(Cursor, "execute", measured):
            self.reconcile(cur, [parent["id"] for parent, _ in pairs])
            cur.execute(f"""SELECT count(*) AS n FROM {store._table('operation_runs')}
                WHERE task_id=ANY(%s) AND run_no=2 AND status='waiting'""",
                ([parent["id"] for parent, _ in pairs],))
            self.assertEqual(cur.fetchone()["n"], 501)
        self.assertEqual(max(sizes), 500)
        self.assertIn(1, sizes)
