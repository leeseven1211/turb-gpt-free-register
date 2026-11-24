"""执行类 Codex 批量受理使用集合数据库事实，不调用外部服务。"""
from unittest.mock import patch
from psycopg import Cursor

from core.storage import records
from core.storage.operations import store as operations
from core.operations import task_gateway
from core.codex import operation_service, token_refresh_service
from core.integrations.sub2api import client, manual_upload
from tests.support_pg import PostgresTestCase


class CodexBulkSubmissionTests(PostgresTestCase):
    def setUp(self):
        from core.codex import bulk_submission
        self.service = bulk_submission
        operations.reset_ready()
        operations.init()
        self.names = []
        self.ids = []
        for index in range(20):
            email = f"bulk-{index}@example.test"
            self.ids.append(records.insert_row(records.ACCOUNTS, {"email": email, "codex_status": "success"}))
            name = f"codex-{index}.json"
            self.names.append(name)
            records.insert_row(records.CODEX_CREDENTIALS, {
                "filename": name, "email": email,
                "content": {"email": email, "access_token": "private-at", "refresh_token": "private-rt"},
                "oauth_status": "valid",
            })
        for context in (
            patch.object(task_gateway, "notify_dispatch"),
            patch.object(token_refresh_service, "_snapshot_for_submission", return_value={"CODEX_REQUEST_TIMEOUT": 30}),
            patch.object(operation_service, "_config_snapshot", return_value={"oauth_driver": "protocol"}),
            patch.object(operation_service, "_deployment_unavailable", return_value=None),
            patch.object(operation_service, "_feature_ready", return_value=(True, "")),
            patch.object(client, "configured_backend_identity", return_value="test-backend"),
        ):
            self.enterContext(context)

    def measured(self, call):
        statements = []
        execute = Cursor.execute
        def capture(cursor, query, *args, **kwargs):
            statements.append(str(query))
            return execute(cursor, query, *args, **kwargs)
        with patch.object(Cursor, "execute", capture):
            result = call()
        return result, statements

    def test_refresh_bulk_has_bounded_sql_and_keeps_secrets_out_of_tasks(self):
        with (
            patch.object(token_refresh_service, "enqueue_refresh", side_effect=AssertionError("single enqueue")),
            patch.object(token_refresh_service, "_request_refresh", side_effect=AssertionError("remote refresh")),
        ):
            result, queries = self.measured(lambda: self.service.submit_refresh(self.names))
        self.assertEqual(result["started_count"], 20)
        self.assertLess(len(queries), 25, queries)
        self.assertEqual(len([q for q in queries if "INSERT INTO" in q and "operation_tasks" in q]), 1)
        for item in result["started"]:
            run = operations.get_run(item["run_id"])
            self.assertEqual(run["task_type"], "codex_token_refresh")
            self.assertNotIn("private-", str(run["data"]))
            self.assertEqual(run["data"]["config_snapshot"]["request_timeout"], 30)
            self.assertEqual(run["batch_id"], result["batch_id"])

    def test_reauthorization_by_filename_deduplicates_registered_accounts(self):
        with patch.object(operation_service, "submit", side_effect=AssertionError("single submit")):
            result, queries = self.measured(lambda: self.service.submit_reauthorization(
                account_ids=[self.ids[0]], filenames=[self.names[0], self.names[1], "codex-missing.json"]))
        self.assertEqual(result["started_count"], 2)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertLess(len(queries), 25, queries)
        account = records.get_row(records.ACCOUNTS, self.ids[0])
        self.assertEqual(account["codex_status"], "success")
        self.assertEqual(account["codex_execution_status"], "queued")

    def test_upload_bulk_binds_original_generation_and_does_not_upload(self):
        with (
            patch.object(manual_upload, "queue_filename", side_effect=AssertionError("single queue")),
            patch.object(client, "upload_configured_codex_oauth_credential", side_effect=AssertionError("remote upload")),
        ):
            result, queries = self.measured(lambda: manual_upload.queue_filenames(self.names))
        self.assertEqual(result["queued_count"], 20)
        self.assertLess(len(queries), 25, queries)
        first = operations.get_run(result["queued"][0]["run_id"])
        self.assertEqual(first["task_type"], manual_upload.TASK_TYPE)
        self.assertEqual(first["data"]["backend_identity"], "test-backend")
        self.assertGreater(first["data"]["credential_id"], 0)
        self.assertNotIn("private-", str(first["data"]))

    def test_upload_backend_config_failure_keeps_both_bulk_routes_classified(self):
        from webui.app import create_app

        app_client = create_app(auth_code="synthetic-auth").test_client()
        for endpoint, body, identity in (
            ("/api/accounts/codex/upload-sub2-bulk",
             {"account_ids": [self.ids[0], "bad", 999999]}, {"id": str(self.ids[0])}),
            ("/api/codex/upload-sub2-bulk",
             {"filenames": [self.names[0], "../bad.json", "codex-missing.json"]},
             {"filename": self.names[0]}),
        ):
            with self.subTest(endpoint=endpoint), \
                    patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                    patch.object(client, "configured_backend_identity",
                                 side_effect=client.Sub2ApiSyncError(
                                     "configuration", "sub2api_config_invalid",
                                     "private-synthetic-secret")) as capture, \
                    patch.object(task_gateway, "notify_dispatch") as notify:
                response = app_client.post(
                    endpoint, json=body, headers={"X-Auth-Code": "synthetic-auth"},
                )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json["queued_count"], 0)
            self.assertEqual(response.json["failed_count"], 1)
            self.assertEqual(response.json["skipped_count"], 2)
            self.assertEqual(response.json["failed"][0]["error_code"], "sub2api_config_invalid")
            self.assertEqual({key: response.json["failed"][0][key] for key in identity}, identity)
            self.assertNotIn("private-synthetic-secret", response.get_data(as_text=True))
            capture.assert_called_once()
            notify.assert_not_called()
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {operations._table('operation_tasks')}")
            self.assertEqual(cur.fetchone()["n"], 0)
            cur.execute(f"SELECT COUNT(*) AS n FROM {operations._table('operation_batches')}")
            self.assertEqual(cur.fetchone()["n"], 0)

    def test_busy_missing_deactivated_and_refresh_unknown_are_stable_skips(self):
        records.patch_row(records.ACCOUNTS, self.ids[1], {"account_status": "deactivated"})
        records.patch_row(records.CODEX_CREDENTIALS, 3, {"oauth_refresh_error": token_refresh_service.REQUEST_UNKNOWN})
        operations.create_runtime_task(task_type="plan_check", account_id=self.ids[0], email="bulk-0@example.test")
        result = self.service.submit_refresh([*self.names[:4], self.names[3], "codex-missing.json", "../bad.json"])
        self.assertEqual(result["started_count"], 1)
        self.assertEqual({item["reason_code"] for item in result["skipped"]},
                         {"account_busy", "account_deactivated", "refresh_reconciliation_required",
                          "credential_missing", "invalid_filename"})

    def test_refresh_durable_unknown_fence_blocks_without_local_marker(self):
        prior = operations.create_runtime_task(task_type="codex_token_refresh", account_id=self.ids[0],
                                               email="bulk-0@example.test")
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operations._table('operation_tasks')} SET status='attention_required' WHERE id=%s", (prior["id"],))
            cur.execute(f"UPDATE {operations._table('operation_runs')} SET status='attention_required' WHERE id=%s", (prior["run"]["id"],))
        result = self.service.submit_refresh(self.names[:1])
        self.assertEqual(result["started_count"], 0)
        self.assertEqual(result["skipped"][0]["reason_code"], "refresh_reconciliation_required")

    def test_failed_set_creation_rolls_back_batch_tasks_and_account_projection(self):
        from core.storage.codex import bulk_submission as storage
        with patch.object(storage, "create_tasks", side_effect=RuntimeError("database failure")):
            with self.assertRaises(RuntimeError):
                self.service.submit_reauthorization(account_ids=self.ids)
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {operations._table('operation_batches')}")
            self.assertEqual(cur.fetchone()["n"], 0)
        self.assertFalse(records.get_row(records.ACCOUNTS, self.ids[0]).get("codex_execution_status"))

    def test_cancel_reauthorization_prefetches_runs_and_cancels_only_selected(self):
        first = operations.create_runtime_task(
            task_type="codex_retry", account_id=self.ids[0], email="bulk-0@example.test",
        )
        second = operations.create_runtime_task(
            task_type="codex_retry", account_id=self.ids[1], email="bulk-1@example.test",
        )
        records.patch_row(records.ACCOUNTS, self.ids[0], {"codex_active_run_id": first["run"]["id"]})
        records.patch_row(records.ACCOUNTS, self.ids[1], {"codex_active_run_id": second["run"]["id"]})
        result = self.service.cancel_reauthorization(account_ids=[self.ids[0], self.ids[1], 999999])
        self.assertEqual(result["stopped_count"], 2)
        self.assertEqual({item["run_id"] for item in result["stopped"]},
                         {first["run"]["id"], second["run"]["id"]})
        self.assertEqual(result["skipped"][0]["reason_code"], "account_missing")
        self.assertEqual(operations.get_run(first["run"]["id"])["status"], "cancelled")
        self.assertEqual(operations.get_run(second["run"]["id"])["status"], "cancelled")
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["codex_execution_status"], "empty")
        self.assertIsNone(records.get_row(records.ACCOUNTS, self.ids[0])["codex_active_run_id"])

    def test_cancel_reauthorization_skips_other_task_types_sources_and_unselected_runs(self):
        created = [
            operations.create_runtime_task(
                task_type=task_type, source_system=source_system,
                account_id=self.ids[index], email=f"bulk-{index}@example.test",
                resource_family="completion_coordinator" if task_type == "account_completion" else "openai_interactive",
            )
            for index, (task_type, source_system) in enumerate([
                ("codex_token_refresh", "native_operations"),
                ("plan_check", "native_operations"),
                ("codex_retry", "legacy_fixture"),
                ("account_completion", "webui_runtime"),
                ("codex_retry", "native_operations"),
            ])
        ]
        result = self.service.cancel_reauthorization(account_ids=self.ids[:4])
        self.assertEqual(result["stopped_count"], 0)
        self.assertEqual(len(result["skipped"]), 4)
        for queued in created:
            self.assertEqual(operations.get_run(queued["run"]["id"])["status"], "queued")

    def test_stop_does_not_overwrite_result_when_run_finishes_after_prefetch(self):
        from core.storage.operations import cancellation
        queued = operations.create_runtime_task(task_type="codex_retry", account_id=self.ids[0],
                                               email="bulk-0@example.test")
        records.patch_row(records.ACCOUNTS, self.ids[0], {"codex_active_run_id": queued["run"]["id"]})
        cancel = cancellation.cancel_runs_many

        def finish_before_cancel(conn, expected_runs, **kwargs):
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {operations._table('operation_runs')} SET status='success' WHERE id=%s", (queued["run"]["id"],))
                cur.execute(f"UPDATE {operations._table('operation_tasks')} SET status='success' WHERE id=%s", (queued["id"],))
            records.patch_row(records.ACCOUNTS, self.ids[0],
                              {"codex_execution_status": "empty", "codex_last_run_status": "success",
                               "codex_active_run_id": 0}, conn=conn)
            return cancel(conn, expected_runs, **kwargs)

        with patch.object(cancellation, "cancel_runs_many", side_effect=finish_before_cancel):
            result = self.service.cancel_reauthorization(account_ids=self.ids[:1])
        self.assertEqual(result["stopped_count"], 0)
        self.assertEqual(result["skipped"][0]["reason_code"], "run_state_changed")
        self.assertEqual(records.get_row(records.ACCOUNTS, self.ids[0])["codex_last_run_status"], "success")

    def test_upload_uses_content_email_for_original_credential_identity(self):
        records.patch_row(records.CODEX_CREDENTIALS, 1, {
            "content": {"email": "bulk-1@example.test", "access_token": "private-at", "refresh_token": "private-rt"},
        })
        result = manual_upload.queue_filenames(self.names[:1])
        run = operations.get_run(result["queued"][0]["run_id"])
        self.assertEqual(run["account_id"], self.ids[1])
        self.assertEqual(run["email_snapshot"], "bulk-1@example.test")
        bound = manual_upload._bound_reference(run["data"], expected_email=run["email_snapshot"])
        self.assertEqual(bound["filename"], self.names[0])

    def test_refresh_and_retry_fall_back_to_content_email_for_legacy_rows(self):
        records.patch_row(records.CODEX_CREDENTIALS, 1, {"email": ""})
        result = self.service.submit_refresh(self.names[:1])
        self.assertEqual(result["started_count"], 1)
        self.assertEqual(result["started"][0]["account_id"], self.ids[0])
        records.patch_row(records.CODEX_CREDENTIALS, 2, {"email": ""})
        result = self.service.submit_reauthorization(filenames=self.names[1:2])
        self.assertEqual(result["started_count"], 1)
        self.assertEqual(result["started"][0]["account_id"], self.ids[1])

    def test_non_integral_and_out_of_postgres_range_ids_are_skipped(self):
        result = self.service.submit_reauthorization(account_ids=[1.9, True, "1.5", 2**63, self.ids[0]])
        self.assertEqual(result["started_count"], 1)
        self.assertEqual(len(result["skipped"]), 4)
        self.assertEqual({item["reason_code"] for item in result["skipped"]}, {"invalid_id"})

    def test_reused_refresh_keeps_original_batch_and_frozen_snapshot(self):
        first = self.service.submit_refresh(self.names[:1])
        queued = first["started"][0]
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operations._table('operation_runs')} SET status='cancelled' WHERE id=%s", (queued["run_id"],))
            cur.execute(f"UPDATE {operations._table('operation_tasks')} SET status='cancelled' WHERE id=%s", (queued["task_id"],))
        with patch.object(token_refresh_service, "_snapshot_for_submission",
                          return_value={"revision": 2, "CODEX_REQUEST_TIMEOUT": 45}):
            second = self.service.submit_refresh(self.names[:1])
        self.assertEqual(second["batch_id"], first["batch_id"])
        self.assertEqual(second["started"][0]["run_id"], queued["run_id"])
        self.assertTrue(second["started"][0]["reused"])
        self.assertEqual(operations.get_run(queued["run_id"])["data"]["config_snapshot"]["request_timeout"], 30)
        with operations._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {operations._table('operation_batches')}")
            self.assertEqual(cur.fetchone()["n"], 1)

    def test_bulk_submission_never_registers_executable_handlers_in_web_process(self):
        with (
            patch.object(operation_service, "register_handler", side_effect=AssertionError("web OAuth handler")),
            patch.object(token_refresh_service, "_register_worker", side_effect=AssertionError("web refresh handler")),
            patch.object(manual_upload, "register_handler", side_effect=AssertionError("web upload handler")),
            patch.object(task_gateway, "register_operation_handler", side_effect=AssertionError("web executable handler")),
        ):
            self.assertEqual(self.service.submit_refresh(self.names[:1])["started_count"], 1)
            self.assertEqual(self.service.submit_reauthorization(account_ids=self.ids[1:2])["started_count"], 1)
            self.assertEqual(manual_upload.queue_filenames(self.names[2:3])["queued_count"], 1)
