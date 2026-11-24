"""真实 PostgreSQL 验证任务中心原生重试的集合追加和旧语义。"""
from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from psycopg import Cursor

from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class TaskCenterRetryStorageTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"center-retry-{index}@example.test", "access_token": "isolated-value",
             "status": "success", "updated_at": "2000-01-01T00:00:00"}
            for index in range(1, 104)
        ])

    def retry(self, conn, specs):
        return import_module("core.storage.operations.bulk_retry_tasks").retry_tasks_many(conn, specs)

    def tasks(self, count=1, *, task_type="fixture_native", source_system="native_operations", account_offset=0):
        specs = [{"task_type": task_type, "account_id": index + account_offset,
            "email": f"center-retry-{index + account_offset}@example.test",
            "source_system": source_system, "source_id": f"fixture-{task_type}-{index + account_offset}",
            "data": {"task_only": "preserved", "shared": "task"}}
            for index in range(1, count + 1)]
        with store._connect() as conn:
            submitted = [store.create_runtime_task(**spec, conn=conn) for spec in specs]
            created = [{"task_id": row["id"], "run_id": row["run"]["id"]} for row in submitted]
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {store._table('operation_runs')} SET status='failed',completed_at=now(),
                    data=data || '{{"previous_only":"preserved","shared":"previous",
                    "remote_intent":{{"kind":"remote_write"}},"remote_receipt":{{"outcome":"unknown"}}}}'::jsonb
                    WHERE id=ANY(%s)""", ([row["run_id"] for row in created],))
                cur.execute(f"""UPDATE {store._table('operation_tasks')} SET status='failed',completed_at=now(),
                    error_code='prior-failure',target_status='failed' WHERE id=ANY(%s)""",
                    ([row["task_id"] for row in created],))
        return created

    def rows(self, table, where="TRUE", params=()):
        with store._connect() as conn, conn.cursor() as cur:
            order = "run_id" if table == "extract_link_provider_jobs" else "id"
            cur.execute(f"SELECT * FROM {store._table(table)} WHERE {where} ORDER BY {order}", params)
            return [dict(row) for row in cur.fetchall()]

    def test_hundred_append_runs_use_constant_sql_and_preserve_history(self):
        created = self.tasks(100)
        before = self.rows("operation_runs")
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, patch.object(Cursor, "execute", measured):
            reply = self.retry(conn, [{"task_id": row["task_id"],
                "data": {"shared": "request", "request_only": "present"}} for row in created])
        print(f"任务中心 100 个原生 Task 重试 SQL={len(statements)}")
        self.assertEqual(len(reply), 100)
        self.assertTrue(all(row["accepted"] for row in reply.values()))
        self.assertLessEqual(len(statements), 12, f"实际 SQL：{len(statements)}")
        self.assertEqual(self.rows("operation_runs", "run_no=1"), before)
        queued = self.rows("operation_runs", "run_no=2")
        self.assertEqual(len(queued), 100)
        for old, new in zip(before, queued, strict=True):
            self.assertEqual(new["task_id"], old["task_id"])
            self.assertEqual(new["status"], "queued")
            self.assertEqual(new["source_system"], old["source_system"])
            self.assertNotEqual(new["source_id"], old["source_id"])
            self.assertEqual(new["resource_family"], old["resource_family"])
            self.assertEqual(new["data"]["previous_only"], "preserved")
            self.assertEqual(new["data"]["task_only"], "preserved")
            self.assertEqual(new["data"]["shared"], "request")
            self.assertEqual(new["data"]["retry_trigger"], "manual_retry")
            self.assertNotIn("remote_intent", new["data"])
            self.assertNotIn("remote_receipt", new["data"])
            self.assertTrue(reply[new["task_id"]]["log_file"])
        self.assertEqual(len(self.rows("operation_events", "event_type='run.queued'")), 200)

    def test_mixed_rejections_and_duplicate_ids_do_not_touch_unselected_tasks(self):
        created = self.tasks(5)
        ids = [row["task_id"] for row in created]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='running' WHERE id=%s", (ids[1],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET target_status='account_deactivated' WHERE id=%s", (ids[2],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET source_system='account_action_tasks' WHERE id=%s", (ids[3],))
        unselected = self.rows("operation_tasks", "id=%s", (ids[4],))[0]
        with store._connect() as conn:
            reply = self.retry(conn, [{"task_id": ident} for ident in (ids[0], ids[0], ids[1], ids[2], ids[3], 999999)])
        self.assertEqual(len(reply), 5)
        self.assertTrue(reply[ids[0]]["accepted"])
        self.assertEqual(reply[ids[1]]["error"], "任务仍在执行")
        self.assertEqual(reply[ids[2]]["error"], "账号已废号，禁止重跑")
        self.assertIn("历史兼容任务", reply[ids[3]]["error"])
        self.assertEqual(reply[999999]["error"], "任务不存在")
        self.assertEqual(self.rows("operation_tasks", "id=%s", (ids[4],))[0], unselected)
        self.assertEqual(len(self.rows("operation_runs", "run_no>1")), 1)

    def test_stage_reset_keeps_old_no_guard_and_current_trigger(self):
        plan = self.tasks(task_type="plan_check")[0]
        live = self.tasks(task_type="token_refresh", account_offset=1)[0]
        with store._connect() as conn:
            records.patch_row(records.ACCOUNTS, 1, changes={"plan_check_status": "running",
                "plan_check_deadline_at": "2099-01-01T00:00:00", "plan_check_queued_at": "old",
                "current_plan_type": "plus"}, conn=conn)
            records.patch_row(records.ACCOUNTS, 2, changes={"live_check_status": "running",
                "live_check_queued_at": "old", "live_check_http_status": 503}, conn=conn)
            reply = self.retry(conn, [{"task_id": plan["task_id"]},
                {"task_id": live["task_id"], "trigger": "custom_manual_retry"}])
        self.assertTrue(all(row["accepted"] for row in reply.values()))
        plan_account = records.get_row(records.ACCOUNTS, 1)
        self.assertEqual(plan_account["plan_check_status"], "queued")
        self.assertIsNone(plan_account["plan_check_deadline_at"])
        self.assertEqual(plan_account["current_plan_type"], "plus")
        live_account = records.get_row(records.ACCOUNTS, 2)
        self.assertEqual(live_account["live_check_status"], "queued")
        self.assertEqual(live_account["live_check_trigger"], "custom_manual_retry")
        self.assertIsNone(live_account["live_check_http_status"])

    def test_codex_state_keeps_asset_status_and_updates_promoted_timestamp(self):
        created = self.tasks(3, task_type="codex_retry")
        with store._connect() as conn:
            for ident, asset, legacy in ((1, "valid", "failed"), (2, "pending_confirmation", "failed"), (3, "", "success")):
                records.patch_row(records.ACCOUNTS, ident, changes={"codex_credential_state": asset,
                    "codex_status": legacy, "codex_last_run_status": "failed",
                    "updated_at": "2000-01-01T00:00:00"}, conn=conn)
            reply = self.retry(conn, [{"task_id": row["task_id"], "codex_state": True} for row in created])
        for ident, legacy in ((1, "success"), (2, "pending_confirmation"), (3, "success")):
            account = records.get_row(records.ACCOUNTS, ident)
            self.assertEqual(account["codex_status"], legacy)
            self.assertEqual(account["codex_execution_status"], "queued")
            self.assertEqual(account["codex_active_run_id"], reply[created[ident - 1]["task_id"]]["run_id"])
            self.assertEqual(account["codex_last_run_status"], "failed")
            self.assertNotEqual(account["updated_at"], "2000-01-01T00:00:00")

    def test_event_failure_rolls_back_append_task_and_account_state(self):
        created = self.tasks(3, task_type="plan_check")
        before_runs = self.rows("operation_runs")
        before_tasks = self.rows("operation_tasks")
        before_account = records.get_row(records.ACCOUNTS, 1)
        execute = Cursor.execute

        def failed(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("队列事件写入故障")
            return execute(cursor, query, params, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "队列事件写入故障"):
            with store._connect() as conn, patch.object(Cursor, "execute", failed):
                self.retry(conn, [{"task_id": row["task_id"]} for row in created])
        self.assertEqual(self.rows("operation_runs"), before_runs)
        self.assertEqual(self.rows("operation_tasks"), before_tasks)
        self.assertEqual(records.get_row(records.ACCOUNTS, 1), before_account)

    def test_latest_attempt_and_expected_previous_id_are_checked_after_task_lock(self):
        original = self.tasks()[0]
        with store._connect() as conn:
            second = self.retry(conn, [{"task_id": original["task_id"]}])[original["task_id"]]
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed',run_no=9 WHERE id=%s", (second["run_id"],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (original["task_id"],))
            stale = self.retry(conn, [{"task_id": original["task_id"], "expected_previous_run_id": original["run_id"]}])
            self.assertTrue(stale[original["task_id"]]["dependency_stale"])
            third = self.retry(conn, [{"task_id": original["task_id"]}])[original["task_id"]]
        self.assertEqual(store.get_run(third["run_id"])["run_no"], 10)

    def test_other_task_unique_conflict_is_per_item_and_does_not_queue_its_account(self):
        created = self.tasks(2, task_type="plan_check")
        conflict = store.create_runtime_task(task_type="fixture_busy", account_id=1,
            email="center-retry-1@example.test")
        with store._connect() as conn:
            records.patch_row(records.ACCOUNTS, 1, changes={"plan_check_status": "failed"}, conn=conn)
            reply = self.retry(conn, [{"task_id": row["task_id"]} for row in created])
        self.assertFalse(reply[created[0]["task_id"]]["accepted"])
        self.assertTrue(reply[created[0]["task_id"]]["busy"])
        self.assertTrue(reply[created[1]["task_id"]]["accepted"])
        self.assertEqual(records.get_row(records.ACCOUNTS, 1)["plan_check_status"], "failed")
        self.assertEqual(store.get_run(conflict["run"]["id"])["status"], "queued")
        self.assertEqual(len(self.rows("operation_runs", "task_id=%s AND run_no>1", (created[0]["task_id"],))), 0)

    def test_helper_savepoint_rolls_back_partial_writes_if_caller_catches_failure(self):
        created = self.tasks(task_type="plan_check")[0]
        execute = Cursor.execute

        def failed(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("回执写入失败")
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn:
            records.patch_row(records.ACCOUNTS, 2, changes={"note": "调用方之前写入"}, conn=conn)
            try:
                with patch.object(Cursor, "execute", failed):
                    self.retry(conn, [{"task_id": created["task_id"]}])
            except RuntimeError:
                pass
        self.assertEqual(records.get_row(records.ACCOUNTS, 2)["note"], "调用方之前写入")
        self.assertEqual(len(self.rows("operation_runs")), 1)
        self.assertEqual(self.rows("operation_tasks")[0]["last_run_id"], created["run_id"])

    def test_idle_shared_connection_does_not_commit_before_caller(self):
        created = self.tasks(task_type="plan_check")[0]
        with self.assertRaisesRegex(RuntimeError, "调用方回滚"):
            with store._connect() as conn:
                reply = self.retry(conn, [{"task_id": created["task_id"]}])
                self.assertTrue(reply[created["task_id"]]["accepted"])
                raise RuntimeError("调用方回滚")
        self.assertEqual(len(self.rows("operation_runs")), 1)
        self.assertEqual(self.rows("operation_tasks")[0]["last_run_id"], created["run_id"])

    def test_extract_sync_copies_only_exact_task_and_provider_snapshot(self):
        created = self.tasks(task_type="extract_link")[0]
        other = self.tasks(task_type="extract_link", account_offset=1)[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('extract_link_provider_jobs')}
                (run_id,provider_id,job_id,public_state,private_data)
                VALUES (%s,'first','provider-first','{{"visible":true}}','{{"private":"isolated"}}'),
                       (%s,'other','provider-other','{{}}','{{}}')""",
                (created["run_id"], other["run_id"]))
            reply = self.retry(conn, [{"task_id": created["task_id"],
                "data": {"workbench_action": "sync_status", "provider_id": "first",
                         "provider_job_run_id": created["run_id"]}}])
        copied = self.rows("extract_link_provider_jobs", "run_id=%s", (reply[created["task_id"]]["run_id"],))
        self.assertEqual(len(copied), 1)
        self.assertEqual((copied[0]["provider_id"], copied[0]["job_id"]), ("first", "provider-first"))
        self.assertEqual(copied[0]["private_data"], {"private": "isolated"})

    def test_parent_reopens_waiting_run_without_rewriting_previous_terminal_evidence(self):
        parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="parent@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success' WHERE id=%s",
                (parent["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                (parent["id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                (child["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                (child["id"],))
            reply = self.retry(conn, [{"task_id": child["id"]}])
        self.assertTrue(reply[child["id"]]["accepted"])
        self.assertEqual(store.get_run(parent["run"]["id"])["status"], "partial_success")
        after = self.rows("operation_tasks", "id=%s", (parent["id"],))[0]
        self.assertEqual(after["status"], "waiting")
        self.assertNotEqual(after["last_run_id"], parent["run"]["id"])
        self.assertEqual(store.get_run(after["last_run_id"])["status"], "waiting")

    def test_public_parent_prelock_returns_precise_parent_generation(self):
        parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="parent@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        unrelated = store.create_runtime_task(task_type="fixture_native", account_id=2,
            email="center-retry-2@example.test")
        leaf = import_module("core.storage.operations.bulk_retry_tasks")
        with store._connect() as conn:
            self.assertEqual(leaf.lock_retry_parents_many(conn, [child["id"], child["id"]]),
                             {parent["id"]: parent["run"]["id"]})
            self.assertEqual(leaf.lock_retry_parents_many(conn, [unrelated["id"]]), {})

    def test_registration_password_handoff_reconciles_current_parent_only(self):
        child = self.tasks(task_type="password_setup", source_system="webui_runtime")[0]
        job_id = records.insert_row(records.JOBS, {"email": "center-retry-1@example.test",
            "account_id": 1, "status": "partial_success"})
        parent = store.create_runtime_task(task_type="registration_resume", account_id=None,
            email="center-retry-1@example.test", source_system="registration_chains", source_id=str(job_id),
            resource_family="registration_chain", data={"completion_handoff": {
                "task_id": child["task_id"], "run_id": child["run_id"], "remaining_error": ""}})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success',source_id=%s WHERE id=%s",
                (str(job_id), parent["run"]["id"]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                (parent["id"],))
            reply = self.retry(conn, [{"task_id": child["task_id"]}])
        self.assertTrue(reply[child["task_id"]]["accepted"])
        parent_task = self.rows("operation_tasks", "id=%s", (parent["id"],))[0]
        self.assertEqual(parent_task["status"], "waiting")
        self.assertEqual(parent_task["last_run_id"], parent["run"]["id"])
        parent_run = store.get_run(parent_task["last_run_id"])
        self.assertEqual(parent_run["result_summary"]["completion_handoff"]["run_id"],
                         reply[child["task_id"]]["run_id"])

    def test_managed_marker_never_enters_generic_retry(self):
        created = self.tasks()[0]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET data=data || %s::jsonb WHERE id=%s",
                (store._json({"bulk_target_round_id": 991}), created["run_id"]))
            reply = self.retry(conn, [{"task_id": created["task_id"]}])
        self.assertTrue(reply[created["task_id"]]["managed"])
        self.assertFalse(reply[created["task_id"]]["accepted"])
        self.assertEqual(len(self.rows("operation_runs")), 1)

    def test_concurrent_retry_keeps_only_one_new_attempt(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        created = self.tasks()[0]
        ready = Barrier(2)

        def submit():
            ready.wait(timeout=10)
            with store._connect() as conn:
                return self.retry(conn, [{"task_id": created["task_id"]}])[created["task_id"]]

        with ThreadPoolExecutor(max_workers=2) as pool:
            left, right = pool.submit(submit), pool.submit(submit)
            replies = [left.result(timeout=15), right.result(timeout=15)]
        self.assertCountEqual([row["accepted"] for row in replies], [True, False])
        self.assertEqual(len(self.rows("operation_runs", "run_no>1")), 1)

    def test_previous_run_lock_is_not_taken_after_task_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        created = self.tasks()[0]
        run_locked, task_locked = Event(), Event()
        execute = Cursor.execute

        def late_update():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE",
                    (created["run_id"],))
                run_locked.set()
                if not task_locked.wait(10):
                    raise RuntimeError("测试未取得 Task 锁")
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET updated_at=now() WHERE id=%s",
                    (created["task_id"],))

        def observed(cursor, query, params=None, **kwargs):
            if "SELECT DISTINCT ON (task_id)" in str(query):
                task_locked.set()
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            late = pool.submit(late_update)
            self.assertTrue(run_locked.wait(10))
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    reply = self.retry(conn, [{"task_id": created["task_id"]}])
            finally:
                task_locked.set()
            late.result(timeout=10)
        self.assertTrue(reply[created["task_id"]]["accepted"])

    def test_traditional_batch_projection_is_scoped_to_changed_tasks(self):
        created = self.tasks(3)
        batches = [store.create_runtime_batch(batch_type="fixture", title=f"fixture {index}", requested_count=1)
                   for index in range(3)]
        with store._connect() as conn, conn.cursor() as cur:
            for task, batch in zip(created, batches, strict=True):
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET batch_id=%s WHERE id=%s",
                    (batch["id"], task["task_id"]))
                cur.execute(f"UPDATE {store._table('operation_runs')} SET batch_id=%s WHERE id=%s",
                    (batch["id"], task["run_id"]))
        untouched = self.rows("operation_batches", "id=%s", (batches[2]["id"],))[0]
        with store._connect() as conn:
            reply = self.retry(conn, [{"task_id": task["task_id"]} for task in created[:2]])
        self.assertTrue(all(row["accepted"] for row in reply.values()))
        for batch in batches[:2]:
            result = self.rows("operation_batches", "id=%s", (batch["id"],))[0]
            self.assertEqual((result["status"], result["queued_count"]), ("queued", 1))
        self.assertEqual(self.rows("operation_batches", "id=%s", (batches[2]["id"],))[0], untouched)

    def test_selected_active_parent_and_child_do_not_reverse_worker_run_task_locks(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event, current_thread
        parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="parent@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                (child["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                (child["id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='queued' WHERE id=%s",
                (parent["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='queued' WHERE id=%s",
                (parent["id"],))
        worker_holds_run, allow_worker_task = Event(), Event()
        execute = Cursor.execute

        def observed(cursor, query, params=None, **kwargs):
            sql = str(query)
            if current_thread().name.startswith("retry-worker") and (
                    f"UPDATE {store._table('operation_tasks')}" in sql):
                worker_holds_run.set()
                if not allow_worker_task.wait(10):
                    raise RuntimeError("测试未达到父 Run 锁")
            if not current_thread().name.startswith("retry-worker") and (
                    "operation_runs" in sql and "FOR UPDATE" in sql):
                allow_worker_task.set()
            return execute(cursor, query, params, **kwargs)

        with patch.object(Cursor, "execute", observed), ThreadPoolExecutor(max_workers=1,
                thread_name_prefix="retry-worker") as pool:
            worker = pool.submit(store.claim_run, parent["run"]["id"],
                execution_id="parent-worker", worker_pid=1)
            self.assertTrue(worker_holds_run.wait(10))
            try:
                with store._connect() as conn:
                    reply = self.retry(conn, [{"task_id": parent["id"]}, {"task_id": child["id"]}])
            finally:
                allow_worker_task.set()
            self.assertEqual(worker.result(timeout=10)["status"], "running")
        self.assertFalse(reply[parent["id"]]["accepted"])
        self.assertTrue(reply[parent["id"]]["busy"])
        self.assertTrue(reply[child["id"]]["accepted"])

    def test_single_retry_task_then_account_lock_does_not_deadlock_bulk(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        created = self.tasks()[0]
        task_locked, account_locked = Event(), Event()
        execute = Cursor.execute

        def single_retry_order():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE",
                    (created["task_id"],))
                task_locked.set()
                if not account_locked.wait(10):
                    raise RuntimeError("测试未取得批量账号锁")
                return records.get_row(records.ACCOUNTS, 1, conn=conn, for_update=True)

        def observed(cursor, query, params=None, **kwargs):
            result = execute(cursor, query, params, **kwargs)
            if records._qualified(records.ACCOUNTS) in str(query) and "ANY" in str(query) and "FOR UPDATE" in str(query):
                account_locked.set()
            return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            single = pool.submit(single_retry_order)
            self.assertTrue(task_locked.wait(10))
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    reply = self.retry(conn, [{"task_id": created["task_id"]}])[created["task_id"]]
            finally:
                account_locked.set()
            self.assertEqual(single.result(timeout=10)["id"], 1)
        self.assertFalse(reply["accepted"])
        self.assertTrue(reply["busy"])
        self.assertEqual(len(self.rows("operation_runs")), 1)

    def test_child_only_prelocks_account_parent_before_child_account(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        parent = store.create_runtime_task(task_type="account_completion", account_id=1,
            email="center-retry-1@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s", (child["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (child["id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='queued' WHERE id=%s", (parent["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='queued' WHERE id=%s", (parent["id"],))
        worker_run_locked, retry_reaches_parent_run = Event(), Event()
        execute = Cursor.execute

        def worker():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE", (parent["run"]["id"],))
                worker_run_locked.set()
                if not retry_reaches_parent_run.wait(10):
                    raise RuntimeError("测试未先读取父 Run")
                records.get_row(records.ACCOUNTS, 1, conn=conn, for_update=True)
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET updated_at=now() WHERE id=%s", (parent["id"],))

        def observed(cursor, query, params=None, **kwargs):
            if "operation_runs" in str(query) and "FOR UPDATE" in str(query):
                retry_reaches_parent_run.set()
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting_worker = pool.submit(worker)
            self.assertTrue(worker_run_locked.wait(10))
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    reply = self.retry(conn, [{"task_id": child["id"]}])
            finally:
                retry_reaches_parent_run.set()
            waiting_worker.result(timeout=10)
        self.assertTrue(reply[child["id"]]["accepted"])

    def test_parent_generation_change_retries_wave_before_any_run_append(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="parent@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed'")
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed'")
        observed_parent = Event()
        replacement_done = Event()
        execute = Cursor.execute
        observed_count = []

        def replace_parent():
            if not observed_parent.wait(10):
                raise RuntimeError("测试未观察父代次")
            replacement = store.retry_runtime_task(parent["id"])
            replacement_done.set()
            return replacement

        def observed(cursor, query, params=None, **kwargs):
            sql = str(query)
            if "operation_runs" in sql and "FOR UPDATE" in sql and not observed_count:
                observed_count.append(True)
                observed_parent.set()
                if not replacement_done.wait(10):
                    raise RuntimeError("测试父代次未完成切换")
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            replace = pool.submit(replace_parent)
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    reply = self.retry(conn, [{"task_id": child["id"]}])
            finally:
                observed_parent.set()
                replacement_done.set()
            replacement = replace.result(timeout=10)
        self.assertTrue(reply[child["id"]]["accepted"])
        self.assertEqual(len(self.rows("operation_runs", "task_id=%s AND run_no>1", (child["id"],))), 1)
        self.assertEqual(self.rows("operation_tasks", "id=%s", (parent["id"],))[0]["last_run_id"], replacement["id"])

    def test_single_child_holding_account_can_reconcile_parent_without_bulk_deadlock(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        parent = store.create_runtime_task(task_type="account_completion", account_id=1,
            email="center-retry-1@example.test", resource_family="completion_coordinator")
        child = store.create_runtime_task(task_type="twofa_setup", account_id=1,
            email="center-retry-1@example.test", source_system="webui_runtime",
            parent_task_id=parent["id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s", (child["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s", (child["id"],))
        single_account_locked, bulk_parent_locked = Event(), Event()
        execute = Cursor.execute

        def single_child_order():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE", (child["id"],))
                records.get_row(records.ACCOUNTS, 1, conn=conn, for_update=True)
                single_account_locked.set()
                if not bulk_parent_locked.wait(10):
                    raise RuntimeError("测试未取得批量父 Run 锁")
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE", (parent["run"]["id"],))
                cur.fetchone()

        def observed(cursor, query, params=None, **kwargs):
            result = execute(cursor, query, params, **kwargs)
            if "operation_runs" in str(query) and "FOR UPDATE" in str(query):
                bulk_parent_locked.set()
            return result

        with ThreadPoolExecutor(max_workers=1) as pool:
            single = pool.submit(single_child_order)
            self.assertTrue(single_account_locked.wait(10))
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    reply = self.retry(conn, [{"task_id": child["id"]}])[child["id"]]
            finally:
                bulk_parent_locked.set()
            single.result(timeout=10)
        self.assertFalse(reply["accepted"])
        self.assertTrue(reply["busy"])
        self.assertEqual(len(self.rows("operation_runs", "task_id=%s", (child["id"],))), 1)
