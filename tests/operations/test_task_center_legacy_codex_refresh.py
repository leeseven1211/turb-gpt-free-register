"""历史 Codex refresh 的任务中心人工重试保持原未知结果许可。"""
from contextlib import ExitStack
from unittest.mock import patch

from psycopg import Cursor

from core.codex import token_refresh_service as refresh
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


def _submit(tasks, accounts):
    from core.operations.task_center_legacy_codex_refresh import submit_legacy
    return submit_legacy(tasks, accounts)


class LegacyCodexRefreshCollectionTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch.object(refresh, "_register_worker"))
        self.stack.enter_context(patch.object(refresh, "_snapshot_for_submission",
            return_value={"CODEX_REQUEST_TIMEOUT": 17, "config_snapshot_revision": 31}))
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"legacy-refresh-{index}@example.test", "access_token": "isolated-at",
             "codex_status": "success", "codex_credential_state": "valid", "updated_at": "2000-01-01T00:00:00"}
            for index in range(1, 32)
        ])
        self.seed(records.CODEX_CREDENTIALS, [
            {"filename": f"codex-legacy-refresh-{index}-free.json", "email": f"legacy-refresh-{index}@example.test",
             "content": {"email": f"legacy-refresh-{index}@example.test", "access_token": "isolated-access",
                         "refresh_token": "isolated-refresh", "expired": "2020-01-01T00:00:00Z"}}
            for index in range(1, 32)
        ])

    def tasks(self, ids):
        return {1000 + index: {"id": index, "task_type": "codex_token_refresh", "account_id": index,
            "status": "failed", "result_summary": {"filename": f"codex-legacy-refresh-{index}-free.json"},
            "data": {}} for index in ids}

    def accounts(self):
        return {row["id"]: row for row in records.list_rows(records.ACCOUNTS)}

    def test_one_and_twenty_manual_retries_have_constant_sql(self):
        counts = []
        for ids in ([1], list(range(2, 22))):
            statements = []
            execute = Cursor.execute

            def measured(cursor, query, params=None, **kwargs):
                statements.append(str(query))
                return execute(cursor, query, params, **kwargs)

            accounts = self.accounts()
            with patch.object(Cursor, "execute", measured):
                result = _submit(self.tasks(ids), accounts)
            self.assertEqual({status for _, status in result.values()}, {202})
            counts.append(len(statements))
            for task_id, (payload, _) in result.items():
                run = store.get_run(payload["run_id"])
                self.assertEqual(run["task_type"], "codex_token_refresh")
                self.assertTrue(run["data"]["manual_retry_unknown"])
                self.assertEqual(run["data"]["config_snapshot"]["request_timeout"], 17)
                self.assertEqual(run["data"]["credential_filename"],
                                 f"codex-legacy-refresh-{task_id - 1000}-free.json")
                self.assertNotIn("isolated-refresh", str(run))
                account = records.get_row(records.ACCOUNTS, task_id - 1000)
                self.assertEqual(account["codex_active_run_id"], run["id"])
                self.assertEqual(account["codex_status"], "success")
                self.assertEqual(account["codex_execution_status"], "queued")
        self.assertEqual(counts[0], counts[1], counts)
        self.assertLessEqual(counts[1], 14, counts)

    def test_manual_unknown_retry_ignores_marker_and_old_durable_unknown_fence(self):
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS,
            changes={"oauth_refresh_error": "request_unknown: needs_reconciliation"},
            where="filename=%s", params=("codex-legacy-refresh-1-free.json",))
        previous = store.create_runtime_task(task_type="codex_token_refresh", account_id=1,
            email="legacy-refresh-1@example.test")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')}
                SET status='attention_required',result_summary='{{"outcome":"request_unknown"}}'::jsonb WHERE id=%s""",
                        (previous["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='attention_required' WHERE id=%s",
                        (previous["id"],))
        first = _submit(self.tasks([1]), self.accounts())[1001]
        self.assertEqual(first[1], 202, first)
        self.assertTrue(first[0]["accepted"])
        run = store.get_run(first[0]["run_id"])
        self.assertTrue(run["data"]["manual_retry_unknown"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT source_id FROM {store._table('operation_tasks')} WHERE id=%s""",
                        (first[0]["task_id"],))
            first_key = cur.fetchone()["source_id"]
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s", (run["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first[0]["task_id"],))
        second = _submit(self.tasks([1]), self.accounts())[1001]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT source_id FROM {store._table('operation_tasks')} WHERE id=%s",
                        (second[0]["task_id"],))
            second_key = cur.fetchone()["source_id"]
        self.assertNotEqual(first_key, second_key)
        self.assertIn(":task-center-retry:", first_key)

    def test_summary_filename_has_priority_and_invalid_missing_refresh_and_reauth_match_single(self):
        tasks = self.tasks(range(1, 7))
        tasks[1001]["data"]["credential_filename"] = "codex-nonexistent-free.json"
        tasks[1002]["result_summary"]["filename"] = "../bad"
        tasks[1003]["result_summary"]["filename"] = "codex-nonexistent-free.json"
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS,
            changes={"content": {"email": "legacy-refresh-4@example.test", "access_token": "isolated-access"}},
            where="filename=%s", params=("codex-legacy-refresh-4-free.json",))
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS, changes={"oauth_refresh_error": "invalid_grant"},
            where="filename=%s", params=("codex-legacy-refresh-5-free.json",))
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS, changes={"sub2api_http_status": 401},
            where="filename=%s", params=("codex-legacy-refresh-6-free.json",))
        result = _submit(tasks, self.accounts())
        self.assertEqual([result[index][1] for index in tasks], [202, 400, 400, 400, 400, 400])
        self.assertEqual(result[1001][0]["filename"], "codex-legacy-refresh-1-free.json")
        self.assertEqual(result[1002][0]["error"], "Codex 凭证不存在")
        self.assertEqual(result[1003][0]["error"], "Codex 凭证不存在")
        self.assertEqual([result[index][0]["error_code"] for index in (1004, 1005, 1006)],
                         ["reauth_required"] * 3)

    def test_credential_email_decides_real_account_and_deactivation_marks_all_its_credentials(self):
        tasks = self.tasks([1])
        tasks[1001]["result_summary"]["filename"] = "codex-legacy-refresh-2-free.json"
        # 历史 Task 的账号仍有效；凭据属于另一账号时原入口按凭证邮箱重新关联。
        records.patch_row(records.ACCOUNTS, 2, {"account_status": "deactivated",
            "account_status_reason": "isolated-deactivation"})
        records.insert_row(records.CODEX_CREDENTIALS, {"filename": "codex-duplicate-2-free.json",
            "email": "legacy-refresh-2@example.test", "content": {"access_token": "isolated",
                "refresh_token": "isolated-refresh"}})
        result = _submit(tasks, self.accounts())[1001]
        self.assertEqual(result[1], 400, result)
        self.assertEqual(result[0]["error_code"], "account_deactivated", result)
        credentials = records.list_rows(records.CODEX_CREDENTIALS,
            where="email=%s", params=("legacy-refresh-2@example.test",))
        self.assertEqual(len(credentials), 2)
        for credential in credentials:
            self.assertEqual(credential["oauth_account_status"], "deactivated")
            self.assertEqual(credential["oauth_status"], "deactivated")
            self.assertEqual(credential["oauth_account_status_reason"], "isolated-deactivation")

    def test_duplicate_targets_and_existing_active_runs_return_original_busy_reference(self):
        tasks = self.tasks([1, 2, 3])
        tasks[1002]["result_summary"]["filename"] = "codex-legacy-refresh-1-free.json"
        active = store.create_runtime_task(task_type="plan_check", account_id=3,
            email="legacy-refresh-3@example.test")
        replies = _submit(tasks, self.accounts())
        self.assertEqual([replies[index][1] for index in tasks], [202, 409, 409])
        self.assertEqual(replies[1002][0]["run_id"], replies[1001][0]["run_id"])
        self.assertEqual(replies[1003][0]["run_id"], active["run"]["id"])
        self.assertEqual(replies[1003][0]["task_id"], active["id"])

    def test_missing_real_account_uses_reference_error_and_provider_id_is_not_local_id(self):
        tasks = self.tasks([1])
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS,
            changes={"email": "unregistered@example.test", "account_id": "1",
                     "content": {"email": "unregistered@example.test", "access_token": "isolated",
                                 "refresh_token": "isolated-refresh"}},
            where="filename=%s", params=("codex-legacy-refresh-1-free.json",))
        reply = _submit(tasks, self.accounts())[1001]
        self.assertEqual(reply[1], 400)
        self.assertEqual(reply[0]["error_code"], "account_reference_missing")

    def test_batch_insert_failure_rolls_back_all_tasks_runs_and_account_projection(self):
        execute = Cursor.execute

        def fail_event(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("isolated event failure")
            return execute(cursor, query, params, **kwargs)

        accounts = self.accounts()
        with patch.object(Cursor, "execute", fail_event):
            result = _submit(self.tasks([1, 2]), accounts)
        self.assertEqual({status for _, status in result.values()}, {400})
        self.assertEqual({payload["error_code"] for payload, _ in result.values()}, {"durable_submit_failed"})
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 0)
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 0)
        self.assertIsNone(records.get_row(records.ACCOUNTS, 1).get("codex_active_run_id"))

    def test_web_acceptance_does_not_install_handler_or_start_dispatcher(self):
        with patch.object(refresh, "_register_worker", side_effect=AssertionError("Worker assembly owns handlers")), \
                patch.object(task_gateway, "start_dispatcher", side_effect=AssertionError("Web must only notify")):
            reply = _submit(self.tasks([1]), self.accounts())[1001]
        self.assertEqual(reply[1], 202, reply)

    def test_active_family_states_match_single_and_waiting_does_not_add_new_fence(self):
        statuses = ("queued", "running", "cancelling", "settling", "stopping", "waiting")
        with store._connect() as conn, conn.cursor() as cur:
            for index, status in enumerate(statuses, 1):
                prior = store.create_runtime_task(task_type="plan_check", account_id=index,
                    email=f"legacy-refresh-{index}@example.test", conn=conn)
                cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                            (status, prior["run"]["id"]))
        replies = _submit(self.tasks(range(1, 7)), self.accounts())
        self.assertEqual([replies[index][1] for index in range(1001, 1007)], [409] * 5 + [202])

    def test_concurrent_manual_retries_for_same_account_create_one_run(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        gate = threading.Barrier(2)
        accounts = self.accounts()

        def submit():
            gate.wait(timeout=10)
            return _submit(self.tasks([1]), accounts)[1001]

        with ThreadPoolExecutor(max_workers=2) as pool:
            left, right = pool.submit(submit), pool.submit(submit)
            replies = [left.result(timeout=15), right.result(timeout=15)]
        self.assertCountEqual([reply[1] for reply in replies], [202, 409])
        accepted = next(reply[0] for reply in replies if reply[1] == 202)
        busy = next(reply[0] for reply in replies if reply[1] == 409)
        self.assertEqual(accepted["run_id"], busy["run_id"])

    def test_five_hundred_and_one_distinct_manual_retries_split_recordset_payloads(self):
        import json
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {records._qualified(records.ACCOUNTS)}
                (id,email,created_at,updated_at,data)
                SELECT n,'legacy-refresh-'||n||'@example.test',now()::text,now()::text,'{{}}'::jsonb
                FROM generate_series(32,501) n""")
            cur.execute(f"""INSERT INTO {records._qualified(records.CODEX_CREDENTIALS)}
                (filename,email,created_at,updated_at,data)
                SELECT 'codex-legacy-refresh-'||n||'-free.json','legacy-refresh-'||n||'@example.test',
                    now()::text,now()::text,jsonb_build_object('content',
                        jsonb_build_object('access_token','isolated','refresh_token','isolated-refresh'))
                FROM generate_series(32,501)n""")
        payload_sizes = []
        execute = Cursor.execute

        def measured(cursor, query, params=None, **kwargs):
            if "jsonb_to_recordset" in str(query):
                for parameter in params or ():
                    if isinstance(parameter, str) and parameter.startswith("["):
                        payload_sizes.append(len(json.loads(parameter)))
            return execute(cursor, query, params, **kwargs)

        accounts = self.accounts()
        with patch.object(Cursor, "execute", measured):
            result = _submit(self.tasks(range(1, 502)), accounts)
        self.assertEqual(len(result), 501)
        self.assertEqual({status for _, status in result.values()}, {202})
        self.assertEqual(max(payload_sizes), 500)
        self.assertIn(1, payload_sizes)

    def test_case_insensitive_codex_asset_state_keeps_original_queued_projection(self):
        records.patch_row(records.ACCOUNTS, 1, {"codex_credential_state": "VALID", "codex_status": "failed"})
        records.patch_row(records.ACCOUNTS, 2, {"codex_credential_state": "", "codex_status": "SUCCESS"})
        result = _submit(self.tasks([1, 2]), self.accounts())
        self.assertEqual({status for _, status in result.values()}, {202})
        self.assertEqual(records.get_row(records.ACCOUNTS, 1)["codex_status"], "success")
        self.assertEqual(records.get_row(records.ACCOUNTS, 2)["codex_status"], "SUCCESS")

    def test_deactivated_marker_write_failure_keeps_rejection_and_other_valid_submissions(self):
        tasks = self.tasks([1, 3])
        tasks[1001]["result_summary"]["filename"] = "codex-legacy-refresh-2-free.json"
        records.patch_row(records.ACCOUNTS, 2, {"account_status": "deactivated"})
        execute = Cursor.execute

        def fail_marker(cursor, query, params=None, **kwargs):
            if str(query).lstrip().startswith(f"UPDATE {records._qualified(records.CODEX_CREDENTIALS)}"):
                raise RuntimeError("isolated marker failure")
            return execute(cursor, query, params, **kwargs)

        accounts = self.accounts()
        with patch.object(Cursor, "execute", fail_marker):
            result = _submit(tasks, accounts)
        self.assertEqual(result[1001][0]["error_code"], "account_deactivated")
        self.assertEqual(result[1003][1], 202, result)

    def test_prepare_exposes_every_eligible_candidate_without_creating_runs(self):
        from core.operations import task_center_legacy_codex_refresh as legacy

        tasks = self.tasks([1, 2])
        tasks[1001]["result_summary"]["filename"] = "codex-legacy-refresh-2-free.json"
        accounts = self.accounts()
        with records.transaction() as conn:
            prepared = legacy.prepare_legacy(
                conn, tasks, accounts, snapshot={"CODEX_REQUEST_TIMEOUT": 19, "config_snapshot_revision": 37})
            self.assertEqual(list(prepared["specs"]), [1001, 1002])
            self.assertEqual(prepared["replies"], {})
            self.assertEqual(
                [spec["account_id"] for spec in prepared["specs"].values()], [2, 2])
            self.assertEqual(
                [spec["resource_family"] for spec in prepared["specs"].values()],
                ["openai_interactive", "openai_interactive"])
            self.assertNotEqual(prepared["specs"][1001]["source_id"], prepared["specs"][1002]["source_id"])
            self.assertEqual(prepared["resolved"][1001]["email"], "legacy-refresh-2@example.test")
            self.assertEqual(prepared["resolved"][1001]["filename"], "codex-legacy-refresh-2-free.json")
            self.assertEqual(prepared["resolved"][1001]["config_snapshot_revision"], 37)
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
                self.assertEqual(cur.fetchone()["n"], 0)
                cur.execute(f"SELECT codex_active_run_id FROM {records._qualified(records.ACCOUNTS)} WHERE id=2")
                self.assertIsNone(cur.fetchone()["codex_active_run_id"])

    def test_caller_can_choose_winner_format_busy_and_rollback_entire_composition(self):
        from core.operations import task_center_legacy_codex_refresh as legacy
        from core.storage.operations.bulk_submission import create_specs

        tasks = self.tasks([1, 2])
        tasks[1002]["result_summary"]["filename"] = "codex-legacy-refresh-1-free.json"
        accounts = self.accounts()
        with self.assertRaisesRegex(RuntimeError, "isolated rollback"):
            with records.transaction() as conn:
                prepared = legacy.prepare_legacy(conn, tasks, accounts)
                chosen = [prepared["specs"][1002]]
                created = create_specs(chosen, conn=conn)
                legacy.project_prepared(conn, chosen, created)
                receipt = created[0]
                replies = legacy.format_prepared(prepared, {
                    1001: {**receipt, "accepted": False, "busy": True},
                    1002: receipt,
                })
                self.assertEqual([replies[index][1] for index in tasks], [409, 202])
                self.assertEqual(replies[1001][0]["run_id"], receipt["run_id"])
                self.assertEqual(replies[1001][0]["task_id"], receipt["task_id"])
                self.assertEqual(replies[1001][0]["filename"], "codex-legacy-refresh-1-free.json")
                self.assertEqual(replies[1002][0]["config_snapshot_revision"], 31)
                self.assertEqual(replies[1002][0]["email"], "legacy-refresh-1@example.test")
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT codex_active_run_id FROM {records._qualified(records.ACCOUNTS)} WHERE id=1")
                    self.assertEqual(cur.fetchone()["codex_active_run_id"], receipt["run_id"])
                raise RuntimeError("isolated rollback")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 0)
            cur.execute(f"SELECT count(*) AS n FROM {store._table('operation_runs')}")
            self.assertEqual(cur.fetchone()["n"], 0)
        self.assertIsNone(records.get_row(records.ACCOUNTS, 1).get("codex_active_run_id"))

    def test_preparation_sees_caller_uncommitted_deactivation_and_rolls_back_marker(self):
        from core.operations import task_center_legacy_codex_refresh as legacy

        tasks = self.tasks([1])
        tasks[1001]["result_summary"]["filename"] = "codex-legacy-refresh-2-free.json"
        accounts = self.accounts()
        with self.assertRaisesRegex(RuntimeError, "isolated rollback"):
            with records.transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
                        SET data=data || '{{"account_status":"deactivated",
                            "account_status_reason":"same-connection"}}'::jsonb WHERE id=2""")
                prepared = legacy.prepare_legacy(conn, tasks, accounts)
                self.assertEqual(prepared["specs"], {})
                self.assertEqual(prepared["replies"][1001][1], 400)
                self.assertEqual(prepared["replies"][1001][0]["error_code"], "account_deactivated")
                with conn.cursor() as cur:
                    cur.execute(f"""SELECT oauth_account_status FROM {records._qualified(records.CODEX_CREDENTIALS)}
                        WHERE filename='codex-legacy-refresh-2-free.json'""")
                    self.assertEqual(cur.fetchone()["oauth_account_status"], "deactivated")
                raise RuntimeError("isolated rollback")
        credential = records.list_rows(records.CODEX_CREDENTIALS,
            where="filename=%s", params=("codex-legacy-refresh-2-free.json",))[0]
        self.assertNotEqual(credential.get("oauth_account_status"), "deactivated")

    def test_resolver_uses_actual_credential_email_without_creating_or_locking_runs(self):
        from core.operations import task_center_legacy_codex_refresh as legacy

        tasks = self.tasks([1, 3, 4])
        tasks[1001]["result_summary"]["filename"] = "codex-legacy-refresh-2-free.json"
        tasks[1003]["result_summary"]["filename"] = "../invalid"
        tasks[1004]["result_summary"]["filename"] = "codex-nonexistent-free.json"
        with records.transaction() as conn:
            self.assertEqual(legacy.resolve_account_ids(conn, tasks), {2})
            with store._connect() as other, other.cursor() as cur:
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=2 FOR UPDATE NOWAIT")
                self.assertEqual(cur.fetchone()["id"], 2)

    def test_preparation_detects_changed_resolution_before_locking_new_account(self):
        from core.operations import task_center_legacy_codex_refresh as legacy

        tasks = self.tasks([1])
        accounts = self.accounts()
        with records.transaction() as conn:
            resolved = legacy.resolve_account_ids(conn, tasks)
            self.assertEqual(resolved, {1})
            with conn.cursor() as cur:
                cur.execute(f"""UPDATE {records._qualified(records.CODEX_CREDENTIALS)}
                    SET email='legacy-refresh-2@example.test',
                        data=data || '{{"content":{{"email":"legacy-refresh-2@example.test",
                            "access_token":"isolated","refresh_token":"isolated-refresh"}}}}'::jsonb
                    WHERE filename='codex-legacy-refresh-1-free.json'""")
            with self.assertRaises(legacy.ResolvedAccountsChanged) as changed:
                legacy.prepare_legacy(conn, tasks, accounts, locked_account_ids=resolved)
            self.assertEqual(changed.exception.unlocked_account_ids, {2})
            with store._connect() as other, other.cursor() as cur:
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=2 FOR UPDATE NOWAIT")
                self.assertEqual(cur.fetchone()["id"], 2)
            with self.assertRaises(legacy.ResolvedAccountsChanged):
                legacy.prepare_legacy(conn, tasks, accounts, locked_account_ids=set())

    def test_missing_credential_email_cannot_bind_historical_empty_email_account(self):
        from core.operations import task_center_legacy_codex_refresh as legacy

        records.insert_row(records.ACCOUNTS, {"id": 99, "email": ""})
        records.patch_rows_where_returning(records.CODEX_CREDENTIALS,
            changes={"email": "", "content": {"access_token": "isolated", "refresh_token": "isolated-refresh"}},
            where="filename=%s", params=("codex-legacy-refresh-1-free.json",))
        accounts = self.accounts()
        with records.transaction() as conn:
            self.assertEqual(legacy.resolve_account_ids(conn, self.tasks([1])), set())
            prepared = legacy.prepare_legacy(conn, self.tasks([1]), accounts)
            self.assertEqual(prepared["specs"], {})
            self.assertEqual(prepared["replies"][1001][0]["error_code"], "account_reference_missing")
