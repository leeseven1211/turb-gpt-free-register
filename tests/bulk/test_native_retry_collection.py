"""原生批量重试必须集合追加 Run，保留逻辑任务和历史执行证据。"""
from contextlib import ExitStack
from unittest.mock import patch

from core.bulk_operations import adapters
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class NativeRetryCollectionTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"native-retry-{index}@example.test",
             "access_token": "isolated-at", "status": "success"}
            for index in range(1, 101)
        ])
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in (
            ("core.runtime.capabilities.account_setup_unavailable", None),
            ("core.accounts.operation_settings.completion_deployment_unavailable", None),
            ("core.codex.operation_service._deployment_unavailable", None),
            ("core.codex.operation_service._feature_ready", (True, "")),
            ("core.accounts.liveness.service.deployment_unavailable", None),
            ("core.operations.task_gateway.notify_dispatch", None),
        ):
            self.stack.enter_context(patch(name, return_value=value))

    def context(self, key):
        return {"operation_key": key, "batch_id": 900, "parameters": {},
                "config_snapshot": {"config_snapshot_revision": 12, "countries": ["JP"],
                    "auto_refresh_at_enabled": True, "password_enabled": True,
                    "plan_check_enabled": True, "twofa_enabled": True, "codex_enabled": True,
                    "refresh_at_enabled": True, "password_driver": "protocol", "twofa_driver": "protocol"}}

    def task_row(self, task_id):
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {store._table('operation_tasks')} WHERE id=%s", (task_id,))
            return dict(cur.fetchone())

    def ready_retries(self, key, count=100):
        targets = [{"target_round_id": 1000 + index, "account_id": index}
                   for index in range(1, count + 1)]
        with store._connect() as conn:
            originals = adapters.submit_chunk(conn, targets, self.context(key))
            self.assertEqual({row["disposition"] for row in originals}, {"created"})
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {store._table('operation_runs')}
                    SET status='failed',completed_at=now(),
                        data=data || '{{"remote_intent":{{"kind":"remote_write"}},
                          "remote_receipt":{{"outcome":"unknown"}},"previous_only":"preserved"}}'::jsonb""")
                cur.execute(f"""UPDATE {store._table('operation_tasks')}
                    SET status='failed',target_status='failed',completed_at=now(),
                        error_code='prior_failure',data=data || '{{"task_only":"preserved"}}'::jsonb""")
                records.patch_rows_where_returning(records.ACCOUNTS,
                    changes={"plan_check_status": "failed", "live_check_status": "failed",
                             "plan_check_http_status": 503, "live_check_http_status": 503},
                    where="id=ANY(%s)", params=(list(range(1, count + 1)),), conn=conn, id_only=True)
        retries = [{**target, "target_round_id": target["target_round_id"] + 10000,
                    "source_task_id": original["task_id"], "source_run_id_snapshot": original["run_id"]}
                   for target, original in zip(targets, originals, strict=True)]
        return originals, retries

    def test_hundred_retry_targets_keep_task_identity_with_bounded_sql(self):
        from psycopg import Cursor
        for key in ("plan_check", "token_refresh", "password_setup", "twofa_setup", "account_completion", "codex_retry"):
            with self.subTest(operation=key):
                # 上一子用例只保留历史，不允许干扰本次资格判断。
                with store._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed'")
                    cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed'")
                    records.patch_rows_where_returning(records.ACCOUNTS,
                        changes={"plan_check_status": "failed", "live_check_status": "failed"},
                        where="TRUE", params=(), conn=conn, id_only=True)
                originals, targets = self.ready_retries(key)
                context = self.context(key)
                context["config_snapshot"]["config_snapshot_revision"] = 99
                statements = []
                original_execute = Cursor.execute

                def measured(cursor, query, params=None, **kwargs):
                    statements.append(str(query))
                    return original_execute(cursor, query, params, **kwargs)

                with store._connect() as conn:
                    with patch.object(Cursor, "execute", measured):
                        receipts = adapters.submit_chunk(conn, targets, context)
                    self.assertEqual({row["disposition"] for row in receipts}, {"created"})
                    self.assertEqual([row["task_id"] for row in receipts],
                                     [row["task_id"] for row in originals])
                    self.assertLessEqual(len(statements), 16, f"{key}: {len(statements)} SQL")
                    with conn.cursor() as cur:
                        cur.execute(f"""SELECT t.id AS task_id,t.last_run_id,t.status,t.error_code,
                            t.data AS task_data,r.*,old.data AS previous_data
                            FROM {store._table('operation_tasks')} t
                            JOIN {store._table('operation_runs')} r ON r.id=t.last_run_id
                            JOIN {store._table('operation_runs')} old ON old.task_id=t.id AND old.run_no=1
                            WHERE t.id=ANY(%s) ORDER BY t.account_id""",
                            ([row["task_id"] for row in originals],))
                        rows = list(cur.fetchall())
                        cur.execute(f"""SELECT count(*) AS n FROM {store._table('operation_events')}
                            WHERE run_id=ANY(%s) AND event_type='run.queued'""",
                            ([row["run_id"] for row in receipts],))
                        self.assertEqual(cur.fetchone()["n"], 100)
                    for index, row in enumerate(rows, 1):
                        self.assertEqual(row["run_no"], 2)
                        self.assertEqual(row["status"], "queued")
                        self.assertIsNone(row["error_code"])
                        self.assertEqual(row["data"]["bulk_target_round_id"], index + 11000)
                        self.assertEqual(row["task_data"]["bulk_target_round_id"], index + 1000)
                        self.assertEqual(row["data"]["config_snapshot"]["config_snapshot_revision"], 99)
                        self.assertEqual(row["previous_data"]["config_snapshot"]["config_snapshot_revision"], 12)
                        self.assertEqual(row["data"]["previous_only"], "preserved")
                        self.assertEqual(row["data"]["task_only"], "preserved")
                        self.assertNotIn("remote_intent", row["data"])
                        self.assertNotIn("remote_receipt", row["data"])
                        if key in {"plan_check", "token_refresh"}:
                            stage = "plan_check" if key == "plan_check" else "live_check"
                            account = records.get_row(records.ACCOUNTS, index, conn=conn)
                            self.assertEqual(account[f"{stage}_status"], "queued")
                            self.assertEqual(account[f"{stage}_trigger"], "manual_bulk")
                            self.assertIsNone(account[f"{stage}_http_status"])
                            if key == "token_refresh":
                                self.assertEqual(account["live_check_queued_at"],
                                                 row["data"]["live_check_queued_at"])

    def test_rejected_task_does_not_leave_stage_claim_or_new_run(self):
        originals, targets = self.ready_retries("plan_check", count=3)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET target_status='account_deactivated' WHERE id=%s",
                        (originals[1]["task_id"],))
            records.patch_row(records.ACCOUNTS, 3, {"plan_check_status": "queued",
                "plan_check_queued_at": "2099-01-01T00:00:00"}, conn=conn)
            receipts = adapters.submit_chunk(conn, targets, self.context("plan_check"))
            self.assertEqual([row["disposition"] for row in receipts],
                             ["created", "not_executed", "waiting_account"])
            self.assertEqual(receipts[1]["reason_code"], "operation_precondition_changed")
            self.assertEqual(receipts[2]["reason_code"], "plan_check_busy")
            self.assertEqual(records.get_row(records.ACCOUNTS, 2, conn=conn)["plan_check_status"], "failed")
            cur.execute(f"SELECT task_id,run_no FROM {store._table('operation_runs')} WHERE run_no>1")
            self.assertEqual(list(cur.fetchall()), [{"task_id": originals[0]["task_id"], "run_no": 2}])

    def test_event_insert_failure_rolls_back_run_task_and_account_projection(self):
        from psycopg import Cursor
        originals, targets = self.ready_retries("token_refresh", count=3)
        original_execute = Cursor.execute

        def fail_queue_event(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("isolated event failure")
            return original_execute(cursor, query, params, **kwargs)

        with self.assertRaisesRegex(RuntimeError, "isolated event failure"):
            with store._connect() as conn, patch.object(Cursor, "execute", fail_queue_event):
                adapters.submit_chunk(conn, targets, self.context("token_refresh"))
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 3)
            cur.execute(f"SELECT last_run_id FROM {store._table('operation_tasks')} ORDER BY id")
            self.assertEqual([row["last_run_id"] for row in cur.fetchall()],
                             [row["run_id"] for row in originals])
            self.assertEqual(records.get_row(records.ACCOUNTS, 1, conn=conn)["live_check_status"], "failed")

    def test_late_previous_run_update_does_not_reverse_the_existing_task_lock_order(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from psycopg import Cursor
        originals, targets = self.ready_retries("twofa_setup", count=1)
        run_locked, task_locked = threading.Event(), threading.Event()
        execute = Cursor.execute

        def late_previous_update():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE",
                            (originals[0]["run_id"],))
                run_locked.set()
                if not task_locked.wait(10):
                    raise RuntimeError("retry did not reach latest Run read")
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET updated_at=now() WHERE id=%s",
                            (originals[0]["task_id"],))

        def observed(cursor, query, params=None, **kwargs):
            if "SELECT DISTINCT ON (task_id)" in str(query):
                task_locked.set()
            return execute(cursor, query, params, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as pool:
            late = pool.submit(late_previous_update)
            self.assertTrue(run_locked.wait(10))
            try:
                with store._connect() as conn, patch.object(Cursor, "execute", observed):
                    receipts = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))
            finally:
                task_locked.set()
            late.result(timeout=10)
        self.assertEqual(receipts[0]["disposition"], "created")
        self.assertEqual(self.task_row(originals[0]["task_id"])["last_run_id"],
                         receipts[0]["run_id"])

    def test_special_parent_reconciliation_remains_in_original_retry_path(self):
        originals, targets = self.ready_retries("twofa_setup", count=1)
        parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="parent@example.test", resource_family="completion_coordinator")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success' WHERE id=%s",
                        (parent["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                        (parent["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=%s WHERE id=%s",
                        (parent["id"], originals[0]["task_id"]))
            receipt = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))[0]
        self.assertEqual(receipt["disposition"], "created")
        current_parent = self.task_row(parent["id"])
        self.assertEqual(current_parent["status"], "waiting")
        self.assertNotEqual(current_parent["last_run_id"], parent["run"]["id"])
        self.assertEqual(store.get_run(parent["run"]["id"])["status"], "partial_success")

    def test_password_handoff_without_parent_id_still_reconciles_registration(self):
        originals, targets = self.ready_retries("password_setup", count=1)
        job_id = records.insert_row(records.JOBS, {"email": "native-retry-1@example.test",
            "account_id": 1, "status": "partial_success"})
        parent = store.create_runtime_task(task_type="registration_resume", account_id=None,
            email="native-retry-1@example.test", source_system="registration_chains", source_id=str(job_id),
            resource_family="registration_chain",
            data={"completion_handoff": {"task_id": originals[0]["task_id"],
                "run_id": originals[0]["run_id"], "remaining_error": ""}})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET status='partial_success',source_id=%s WHERE id=%s""",
                        (str(job_id), parent["run"]["id"]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                        (parent["id"],))
            receipt = adapters.submit_chunk(conn, targets, self.context("password_setup"))[0]
        self.assertEqual(receipt["disposition"], "created", receipt)
        current_parent = self.task_row(parent["id"])
        self.assertEqual(current_parent["status"], "waiting")
        parent_run = store.get_run(current_parent["last_run_id"])
        self.assertEqual(parent_run["result_summary"]["completion_handoff"]["run_id"], receipt["run_id"])

    def test_retry_uses_latest_attempt_even_when_selected_source_is_older(self):
        originals, targets = self.ready_retries("twofa_setup", count=1)
        with store._connect() as conn:
            second = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))[0]
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {store._table('operation_runs')}
                    SET status='failed',run_no=9,resource_family='prior_special_family'
                    WHERE id=%s""", (second["run_id"],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                            (originals[0]["task_id"],))
            latest_target = [{**targets[0], "target_round_id": 31001}]
            third = adapters.submit_chunk(conn, latest_target, self.context("twofa_setup"))[0]
        run = store.get_run(third["run_id"])
        self.assertEqual(third["task_id"], originals[0]["task_id"])
        self.assertEqual(third["disposition"], "created")
        self.assertEqual(run["run_no"], 10)
        self.assertEqual(run["resource_family"], "prior_special_family")

    def test_concurrent_replay_creates_only_one_new_attempt(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        originals, targets = self.ready_retries("twofa_setup", count=1)
        gate = threading.Barrier(2)

        def submit():
            gate.wait(timeout=10)
            with store._connect() as conn, conn.cursor() as cur:
                # 与实际 submit_targets 相同：账号锁先于领域资格读取和 Task 锁。
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=1 FOR UPDATE")
                cur.fetchone()
                return adapters.submit_chunk(conn, targets, self.context("twofa_setup"))[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            left, right = pool.submit(submit), pool.submit(submit)
            receipts = [left.result(timeout=15), right.result(timeout=15)]
        self.assertCountEqual([row["disposition"] for row in receipts], ["created", "waiting_account"])
        created = next(row for row in receipts if row["disposition"] == "created")
        waiting = next(row for row in receipts if row["disposition"] == "waiting_account")
        self.assertEqual(waiting["blocker_run_id"], created["run_id"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT run_no FROM {store._table('operation_runs')} WHERE task_id=%s ORDER BY run_no",
                        (originals[0]["task_id"],))
            self.assertEqual([row["run_no"] for row in cur.fetchall()], [1, 2])

    def test_five_hundred_and_one_retries_split_all_recordset_writes(self):
        import json
        from psycopg import Cursor
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"native-retry-{index}@example.test", "access_token": "isolated-at"}
            for index in range(101, 502)
        ])
        originals, targets = self.ready_retries("twofa_setup", count=501)
        payload_sizes = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            if "jsonb_to_recordset" in str(query):
                for parameter in params or ():
                    if isinstance(parameter, str) and parameter.startswith("["):
                        payload_sizes.append(len(json.loads(parameter)))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, patch.object(Cursor, "execute", measured):
            receipts = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))
        self.assertEqual(len(receipts), 501)
        self.assertEqual({row["disposition"] for row in receipts}, {"created"})
        self.assertEqual([row["task_id"] for row in receipts], [row["task_id"] for row in originals])
        self.assertEqual(max(payload_sizes), 500)
        self.assertIn(1, payload_sizes)

    def test_managed_retry_round_links_only_new_runs_and_emits_outbox_in_collection(self):
        import uuid
        from psycopg import Cursor
        from core.storage.operations import bulk
        bulk.reset_ready()
        bulk.init()
        context = self.context("plan_check")
        with patch("core.bulk_operations.catalog.capture_settings", return_value={
                "config_revision": "12", "effective_settings": {}}):
            selection = bulk.create_selection(request_key=uuid.uuid4().hex,
                source={"kind": "ids", "ids": list(range(1, 101))}, operation_key="plan_check",
                parameters={}, config_revision="12", config_snapshot=context["config_snapshot"])
            selection = bulk.freeze_selection(selection["id"])
            batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=selection["id"],
                selection_revision=1, operation_key="plan_check", parameters={}, config_revision="12",
                max_concurrency=64)
            self.assertEqual(bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)["submitted"], 100)
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed',completed_at=now()")
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed',completed_at=now()")
                cur.execute(f"""UPDATE {store._table('operation_batch_target_rounds')}
                    SET chain_state='closed',chain_closed_at=now() WHERE batch_id=%s""", (batch["id"],))
                records.patch_rows_where_returning(records.ACCOUNTS, changes={"plan_check_status": "failed"},
                    where="TRUE", params=(), conn=conn, id_only=True)
            bulk.project_pending()
            retry = bulk.create_round(batch["id"], request_key="collection-second-round",
                source={"view": "current"}, selection={"kind": "result_filter", "outcomes": ["failed"]})
            bulk.freeze_round(retry["id"])
            bulk.materialize_targets(batch["id"], limit=100)
            statements = []
            execute = Cursor.execute

            def measured(cursor, query, params=None, **kwargs):
                statements.append(str(query))
                return execute(cursor, query, params, **kwargs)

            with patch.object(Cursor, "execute", measured):
                result = bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)
        self.assertEqual(result["submitted"], 100)
        self.assertLessEqual(len(statements), 44, f"{len(statements)} SQL")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT tr.round_id,l.target_round_id,l.task_id,l.run_id,r.run_no,
                    (r.data->>'bulk_target_round_id')::bigint AS marker
                FROM {store._table('operation_batch_run_links')} l
                JOIN {store._table('operation_batch_target_rounds')} tr ON tr.id=l.target_round_id
                JOIN {store._table('operation_runs')} r ON r.id=l.run_id ORDER BY l.task_id,r.run_no""")
            links = list(cur.fetchall())
            self.assertEqual(len(links), 200)
            for offset in range(0, 200, 2):
                old, new = links[offset:offset + 2]
                self.assertEqual(old["task_id"], new["task_id"])
                self.assertEqual((old["run_no"], new["run_no"]), (1, 2))
                self.assertNotEqual(old["target_round_id"], new["target_round_id"])
                self.assertEqual(new["round_id"], retry["id"])
                self.assertEqual(new["marker"], new["target_round_id"])
                self.assertEqual(old["marker"], old["target_round_id"])
            cur.execute(f"""SELECT count(*) AS n FROM {store._table('operation_projection_outbox')} outbox
                JOIN {store._table('operation_batch_target_rounds')} tr ON tr.id=outbox.target_round_id
                WHERE tr.round_id=%s AND outbox.event_kind='submitted'""", (retry["id"],))
            self.assertEqual(cur.fetchone()["n"], 100)

    def test_original_preconditions_and_unknown_outcomes_are_preserved(self):
        originals, targets = self.ready_retries("plan_check", count=9)
        with store._connect() as conn, conn.cursor() as cur:
            for index, changes in ((0, "status='deactivated'"), (1, "target_status='deactivated'"),
                    (4, "source_system='registration_jobs'"), (5, "source_system='account_action_tasks'"),
                    (6, "status='request_unknown'"), (7, "status='queued'")):
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET {changes} WHERE id=%s",
                            (originals[index]["task_id"],))
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET result_summary='{{"status":"deactivated"}}'::jsonb WHERE id=%s""",
                (originals[2]["run_id"],))
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET result_summary='{{"requested_status":"deactivated"}}'::jsonb WHERE id=%s""",
                (originals[3]["run_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='request_unknown' WHERE id=%s",
                        (originals[6]["run_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='running' WHERE id=%s",
                        (originals[8]["run_id"],))
            receipts = adapters.submit_chunk(conn, targets, self.context("plan_check"))
            self.assertEqual([row["disposition"] for row in receipts], [
                "not_executed", "not_executed", "not_executed", "not_executed",
                "not_executed", "not_executed", "created", "not_executed", "waiting_account"])
            for account_id in (1, 2, 3, 4, 5, 6, 8, 9):
                self.assertEqual(records.get_row(records.ACCOUNTS, account_id, conn=conn)["plan_check_status"], "failed")
            self.assertEqual(records.get_row(records.ACCOUNTS, 7, conn=conn)["plan_check_status"], "queued")

    def test_traditional_batch_projection_is_refreshed_after_native_retry(self):
        originals, targets = self.ready_retries("twofa_setup", count=1)
        batch = store.create_runtime_batch(batch_type="twofa_setup", title="isolated legacy batch",
                                           requested_count=1)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_batches')} SET status='failed',failed_count=1 WHERE id=%s",
                        (batch["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET batch_id=%s WHERE id=%s",
                        (batch["id"], originals[0]["task_id"]))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET batch_id=%s WHERE id=%s",
                        (batch["id"], originals[0]["run_id"]))
            receipt = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))[0]
            self.assertEqual(receipt["disposition"], "created")
            cur.execute(f"SELECT status,queued_count,failed_count FROM {store._table('operation_batches')} WHERE id=%s",
                        (batch["id"],))
            self.assertEqual(dict(cur.fetchone()), {"status": "queued", "queued_count": 1, "failed_count": 0})
            cur.execute(f"SELECT batch_id FROM {store._table('operation_runs')} WHERE id=%s", (receipt["run_id"],))
            self.assertEqual(cur.fetchone()["batch_id"], batch["id"])

    def test_codex_submission_and_retry_refresh_promoted_updated_at(self):
        old_timestamp = "2000-01-01T00:00:00+00:00"
        with store._connect() as conn:
            records.patch_row(records.ACCOUNTS, 1, {"updated_at": old_timestamp}, conn=conn)
            first = adapters.submit_chunk(conn, [{"target_round_id": 1001, "account_id": 1}],
                                          self.context("codex_retry"))[0]
            first_account = records.get_row(records.ACCOUNTS, 1, conn=conn)
            self.assertEqual(first["disposition"], "created")
            self.assertGreater(first_account["updated_at"], old_timestamp)
            self.assertEqual(first_account["codex_active_run_id"], first["run_id"])
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                            (first["run_id"],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                            (first["task_id"],))
            records.patch_row(records.ACCOUNTS, 1, {"updated_at": old_timestamp,
                "codex_status": "success", "codex_credential_state": "valid"}, conn=conn)
            retry = adapters.submit_chunk(conn, [{"target_round_id": 11001, "account_id": 1,
                "source_task_id": first["task_id"]}], self.context("codex_retry"))[0]
            retry_account = records.get_row(records.ACCOUNTS, 1, conn=conn)
            self.assertEqual(retry["disposition"], "created")
            self.assertGreater(retry_account["updated_at"], old_timestamp)
            self.assertEqual(retry_account["codex_active_run_id"], retry["run_id"])
            self.assertEqual(retry_account["codex_status"], "success")
            self.assertEqual(retry_account["codex_credential_state"], "valid")

    def test_twenty_parent_retries_reconcile_without_per_target_sql_or_savepoints(self):
        from psycopg import Cursor
        originals, targets = self.ready_retries("twofa_setup", count=20)
        parents = []
        for index, original in enumerate(originals):
            parent = store.create_runtime_task(task_type="account_completion", account_id=None,
                email=f"parent-{index}@example.test", resource_family="completion_coordinator")
            parents.append(parent)
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success' WHERE id=%s",
                            (parent["run"]["id"],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                            (parent["id"],))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=%s WHERE id=%s",
                            (parent["id"], original["task_id"]))
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, patch.object(Cursor, "execute", measured):
            receipts = adapters.submit_chunk(conn, targets, self.context("twofa_setup"))
        self.assertEqual({row["disposition"] for row in receipts}, {"created"})
        self.assertLessEqual(len(statements), 32, f"{len(statements)} SQL")
        self.assertFalse(any("SAVEPOINT" in query for query in statements))
        for parent in parents:
            task = self.task_row(parent["id"])
            self.assertEqual(task["status"], "waiting")
            self.assertNotEqual(task["last_run_id"], parent["run"]["id"])
            old = store.get_run(parent["run"]["id"])
            self.assertEqual(old["status"], "partial_success")

    def test_twenty_password_handoffs_reconcile_without_per_target_sql_or_savepoints(self):
        from psycopg import Cursor
        originals, targets = self.ready_retries("password_setup", count=20)
        parents = []
        for index, original in enumerate(originals, 1):
            job_id = records.insert_row(records.JOBS, {"email": f"native-retry-{index}@example.test",
                "account_id": index, "status": "partial_success"})
            parent = store.create_runtime_task(task_type="registration_resume", account_id=None,
                email=f"native-retry-{index}@example.test", source_system="registration_chains",
                source_id=str(job_id), resource_family="registration_chain",
                data={"completion_handoff": {"task_id": original["task_id"], "run_id": original["run_id"],
                    "remaining_error": ""}})
            parents.append(parent)
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success',source_id=%s WHERE id=%s",
                            (str(job_id), parent["run"]["id"]))
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                            (parent["id"],))
        statements = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, params, **kwargs)

        with store._connect() as conn, patch.object(Cursor, "execute", measured):
            receipts = adapters.submit_chunk(conn, targets, self.context("password_setup"))
        self.assertEqual({row["disposition"] for row in receipts}, {"created"})
        self.assertLessEqual(len(statements), 34, f"{len(statements)} SQL")
        self.assertFalse(any("SAVEPOINT" in query for query in statements))
        for parent, child in zip(parents, receipts, strict=True):
            task = self.task_row(parent["id"])
            self.assertEqual(task["status"], "waiting")
            run = store.get_run(task["last_run_id"])
            self.assertEqual(run["result_summary"]["completion_handoff"]["run_id"], child["run_id"])
