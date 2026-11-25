from __future__ import annotations

from unittest.mock import patch
from psycopg import Cursor
from concurrent.futures import ThreadPoolExecutor

from core.accounts import bulk_submission
from core.storage import records
from core.storage.operations import common, schema, bulk_submission as shared
from tests.support_pg import PostgresTestCase


class AccountBulkSubmissionTests(PostgresTestCase):
    def account(self, account_id, **changes):
        return records.insert_row(records.ACCOUNTS, {
            "id": account_id, "email": f"account-{account_id}@example.test", "access_token": "synthetic", **changes,
        })

    def tasks(self):
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT t.*,r.data AS run_data FROM {common._table('operation_tasks')} t JOIN {common._table('operation_runs')} r ON r.id=t.last_run_id ORDER BY t.id")
            return [dict(row) for row in cur.fetchall()]

    def test_live_bulk_creates_native_tasks_without_single_enqueue_or_external_calls(self):
        self.seed(records.ACCOUNTS, [
            {"id": 7, "email": "a@example.test", "access_token": "synthetic"},
            {"id": 8, "email": "b@example.test", "access_token": "synthetic"},
        ])
        with patch("core.accounts.liveness.service.enqueue_account_live_check", side_effect=AssertionError("single enqueue")), \
                patch("core.accounts.liveness.service.register_operation_handlers", side_effect=AssertionError("web installs executable handler")), \
                patch("core.operations.task_gateway.notify_dispatch") as notify:
            result = bulk_submission.submit_accounts([7, 8, 7, 99], operation="live")
        self.assertEqual(result["started_count"], 2)
        self.assertEqual(result["skipped"], [{"id": 99, "reason": "账号不存在"}])
        notify.assert_called_once()
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT task_type,account_id FROM {common._table('operation_tasks')} ORDER BY account_id")
            self.assertEqual([(row["task_type"], row["account_id"]) for row in cur.fetchall()], [
                ("live_check", 7), ("live_check", 8),
            ])

    def test_same_request_reuses_original_before_active_claim_and_does_not_notify_again(self):
        self.account(7)
        with patch("core.operations.task_gateway.notify_dispatch") as notify:
            first = bulk_submission.submit_accounts([7], operation="live", request_key="a" * 32)
            second = bulk_submission.submit_accounts([7], operation="live", request_key="a" * 32)
        self.assertEqual(first["started_count"], 1)
        self.assertEqual(second["started_count"], 1)
        self.assertEqual(second["started"][0]["task_id"], first["started"][0]["task_id"])
        self.assertTrue(second["started"][0]["reused"])
        self.assertEqual(second["skipped_count"], 0)
        notify.assert_called_once()
        self.assertTrue(self.tasks()[0]["source_id"].startswith("webui-account-request:" + "a" * 32))

    def test_mixed_submission_keeps_skipped_facts_and_partial_batch_status(self):
        from core.storage.operations import runtime

        self.account(7)
        with patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([7, 99], operation="live")
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT requested_count,skipped_count,queued_count,status "
                f"FROM {common._table('operation_batches')} WHERE id=%s",
                (result["batch_id"],),
            )
            batch = cur.fetchone()
        self.assertEqual(dict(batch), {
            "requested_count": 2, "skipped_count": 1, "queued_count": 1, "status": "queued",
        })
        runtime.finish_run(result["started"][0]["run_id"], status="success", result_summary={"ok": True})
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT status,skipped_count,success_count,queued_count "
                f"FROM {common._table('operation_batches')} WHERE id=%s",
                (result["batch_id"],),
            )
            batch = cur.fetchone()
        self.assertEqual(dict(batch), {
            "status": "partial_success", "skipped_count": 1, "success_count": 1, "queued_count": 0,
        })

    def test_setup_keeps_source_steps_flags_and_snapshot_projection(self):
        self.account(7)
        settings = {"password_driver": "protocol", "twofa_driver": "protocol", "twofa_browser_fallback_enabled": False}
        with patch.object(bulk_submission, "_capture", return_value=(settings, tuple(settings), settings)), \
                patch("core.runtime.capabilities.account_setup_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([7], operation="setup", trigger="manual_account_setup_bulk")
        self.assertEqual(result["started_count"], 1)
        task = self.tasks()[0]
        self.assertEqual(task["source_system"], "webui_runtime")
        self.assertEqual(task["task_type"], "account_setup_retry")
        self.assertEqual(task["run_data"]["steps"], ["password", "plan_check", "twofa"])
        self.assertFalse(task["run_data"].get("force_password_reset"))
        self.assertFalse(task["run_data"]["force_twofa_change"])
        self.assertEqual(task["run_data"]["task_trigger"], "manual_account_setup_bulk")
        self.assertEqual(task["run_data"]["config_snapshot"]["password_driver"], "protocol")

    def test_token_freezes_driver_and_invalid_email_fallback_without_reading_single_accounts(self):
        self.account(7, email_invalid=True)
        snapshot = {"refresh_driver": "protocol", "refresh_protocol_version": "v1"}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"), \
                patch("core.accounts.liveness.service.db.get_account", side_effect=AssertionError("single read")):
            result = bulk_submission.submit_accounts([7], operation="token", trigger="token_refresh_manual")
        self.assertEqual(result["started_count"], 1)
        self.assertEqual(result["started"][0]["token_refresh_driver"], "protocol_v2")
        data = self.tasks()[0]["run_data"]
        self.assertTrue(data["force_refresh"])
        self.assertEqual(data["refresh_driver"], "v2")
        self.assertIn("proxy_source", data)
        row = records.get_row(records.ACCOUNTS, 7)
        self.assertEqual(row["live_check_status"], "queued")
        self.assertEqual(row["live_check_trigger"], "token_refresh_manual")
        self.assertIsNone(row["live_check_started_at"])

    def test_replayed_token_receipt_uses_original_driver_revision_and_email_snapshot(self):
        self.account(7)
        snapshot = {"refresh_driver": "protocol", "refresh_protocol_version": "v3", "config_snapshot_revision": "original"}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"):
            first = bulk_submission.submit_accounts([7], operation="token", request_key="b" * 32)
            records.patch_row(records.ACCOUNTS, 7, {"email": "changed@example.test"})
            replacement = {"refresh_driver": "browser_roxy", "config_snapshot_revision": "changed"}
            with patch.object(bulk_submission, "_capture", return_value=(replacement, tuple(replacement), replacement)):
                replay = bulk_submission.submit_accounts([7], operation="token", request_key="b" * 32)
        original, reused = first["started"][0], replay["started"][0]
        self.assertEqual(reused["task_id"], original["task_id"])
        self.assertEqual(reused["email"], "account-7@example.test")
        self.assertEqual(reused["refresh_driver"], "protocol_v3")
        self.assertEqual(reused["config_snapshot_revision"], "original")

    def test_replay_keeps_existing_deactivation_token_and_deployment_admission(self):
        for account_id in (7, 8, 9):
            self.account(account_id)
        snapshot = {"refresh_driver": "protocol", "refresh_protocol_version": "v1"}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch") as notify:
            bulk_submission.submit_accounts([7, 8, 9], operation="token", request_key="c" * 32)
            records.patch_row(records.ACCOUNTS, 7, {"account_status": "deactivated"})
            records.patch_row(records.ACCOUNTS, 8, {"access_token": ""})
            replay = bulk_submission.submit_accounts([7, 8], operation="token", request_key="c" * 32)
            with patch("core.accounts.liveness.service.deployment_unavailable",
                       return_value={"accepted": False, "error": "synthetic unavailable"}):
                unavailable = bulk_submission.submit_accounts([9], operation="token", request_key="c" * 32)
        self.assertEqual(replay["started_count"], 0)
        self.assertEqual(replay["skipped"][0]["id"], 7)
        self.assertEqual(replay["failed"][0]["id"], 8)
        self.assertEqual(unavailable["started_count"], 0)
        self.assertEqual(unavailable["failed_count"], 1)
        self.assertEqual(len(self.tasks()), 3)
        notify.assert_called_once()

    def test_plan_respects_auto_refresh_gate_and_persists_countries_and_timezone(self):
        self.account(7, access_token="")
        self.account(8)
        snapshot = {"auto_refresh_at_enabled": False, "countries": ["US", "JP"]}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([7, 8], operation="plan", parameters={"timezone_offset_min": "480"})
        self.assertEqual([item["id"] for item in result["started"]], [8])
        self.assertEqual(result["skipped"][0]["reason"], "缺少 access_token")
        data = self.tasks()[0]["run_data"]
        self.assertEqual(data["countries"], ["US", "JP"])
        self.assertEqual(data["timezone_offset_min"], "480")
        self.assertEqual(data["proxy_source"], "pool")
        self.assertEqual(records.get_row(records.ACCOUNTS, 8)["plan_check_status"], "queued")

    def test_completion_ready_blocked_and_registration_busy_keep_original_decisions(self):
        self.account(7)
        self.account(8, access_token="")
        self.account(9)
        records.insert_row(records.JOBS, {"account_id": 9, "email": "account-9@example.test", "status": "running", "job_type": "registration"})
        settings = {"password_enabled": False, "plan_check_enabled": False, "twofa_enabled": False,
                    "codex_enabled": False, "refresh_at_enabled": False}
        with patch.object(bulk_submission, "_capture", return_value=(settings, tuple(settings), settings)), \
                patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([7, 8, 9], operation="complete")
        self.assertEqual([item["id"] for item in result["ready"]], [7])
        self.assertEqual(result["started_count"], 0)
        self.assertEqual({item["id"] for item in result["skipped"]}, {8, 9})

    def test_c2a_bulk_only_persists_original_account_reference_and_backend(self):
        self.account(7)
        with patch("core.integrations.c2a.client.configured_backend_identity", return_value="synthetic-backend"), \
                patch("core.integrations.c2a.manual_sync.queue_account", side_effect=AssertionError("single enqueue")), \
                patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([7], operation="c2a", trigger="c2a_manual_reimport")
        self.assertEqual(result["queued_count"], 1)
        task = self.tasks()[0]
        self.assertEqual(task["task_type"], "c2a_session_reimport")
        self.assertEqual(task["run_data"], {"backend_identity": "synthetic-backend"})
        self.assertEqual(task["trigger"], "c2a_manual_reimport")

    def test_c2a_strict_ids_and_deactivated_failures_keep_classified_receipts(self):
        self.account(7)
        self.account(8, account_status="deactivated")
        with patch("core.integrations.c2a.client.configured_backend_identity", return_value="synthetic-backend"), \
                patch("core.operations.task_gateway.notify_dispatch"):
            result = bulk_submission.submit_accounts([True, 7.0, "07", "7", 8, 99], operation="c2a")
        self.assertEqual(result["queued_count"], 1)
        self.assertEqual([item["input_index"] for item in result["skipped"] if "input_index" in item], [1, 2, 3])
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["failed"][0]["error_code"], "c2a_account_deactivated")
        self.assertEqual(result["skipped"][-1]["error_code"], "c2a_local_account_missing")

    def test_c2a_config_capture_failure_returns_classified_json_without_creating_tasks(self):
        from core.integrations.c2a.client import C2AError
        from webui.app import create_app
        self.account(7)
        self.account(8, account_status="deactivated")
        client = create_app(auth_code="synthetic-auth").test_client()
        with patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                patch("core.integrations.c2a.client.configured_backend_identity",
                      side_effect=C2AError("configuration", "c2a_config_invalid", "private-synthetic-secret")) as capture, \
                patch("core.operations.task_gateway.notify_dispatch") as notify:
            response = client.post("/api/accounts/c2a/sync-bulk", json={"account_ids": ["bad", 7, 8, 99]},
                                   headers={"X-Auth-Code": "synthetic-auth"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["queued_count"], 0)
        self.assertEqual(response.json["failed_count"], 2)
        self.assertEqual([item["error_code"] for item in response.json["failed"]],
                         ["c2a_config_invalid", "c2a_account_deactivated"])
        self.assertEqual(response.json["skipped_count"], 2)
        self.assertNotIn("private-synthetic-secret", response.get_data(as_text=True))
        self.assertEqual(self.tasks(), [])
        capture.assert_called_once()
        notify.assert_not_called()

    def test_sql_count_is_bounded_for_twenty_targets(self):
        for account_id in range(1, 22):
            self.account(account_id)
        schema.init_operation_schema()
        settings = {"live_check_driver": "protocol"}
        original = Cursor.execute
        calls = []
        def count_sql(cursor, query, *args, **kwargs):
            calls.append(str(query))
            return original(cursor, query, *args, **kwargs)
        with patch.object(bulk_submission, "_capture", return_value=(settings, tuple(settings), settings)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"), patch.object(Cursor, "execute", count_sql):
            one = bulk_submission.submit_accounts([21], operation="live")
            first_count = len(calls)
            calls.clear()
            many = bulk_submission.submit_accounts(list(range(1, 21)), operation="live")
            twenty_count = len(calls)
        self.assertEqual(one["started_count"], 1)
        self.assertEqual(many["started_count"], 20)
        self.assertEqual(first_count, twenty_count)
        self.assertLessEqual(twenty_count, 16)

    def test_concurrent_collection_submissions_classify_active_accounts_and_preserve_unrelated(self):
        for account_id in (7, 8, 9):
            self.account(account_id)
        snapshot = {"live_check_driver": "protocol"}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"):
            bulk_submission.submit_accounts([7], operation="live")
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: bulk_submission.submit_accounts([7, 8, 9], operation="live"), range(2)))
        self.assertEqual(sum(item["started_count"] for item in results), 2)
        self.assertEqual(len(self.tasks()), 3)
        self.assertTrue(all(any(item["id"] == 7 for item in value["skipped"]) for value in results))

    def test_claims_and_tasks_rollback_together_when_collection_creation_fails(self):
        self.account(7)
        with patch("core.operations.task_gateway.notify_dispatch") as notify, \
                patch.object(shared, "create_specs", side_effect=RuntimeError("collection failure")):
            with self.assertRaisesRegex(RuntimeError, "collection failure"):
                bulk_submission.submit_accounts([7], operation="live")
        notify.assert_not_called()
        self.assertIsNone(records.get_row(records.ACCOUNTS, 7)["live_check_status"])
        self.assertEqual(self.tasks(), [])

    def test_token_precondition_failures_and_plan_busy_keep_original_collections(self):
        self.account(7, access_token="")
        self.account(8)
        snapshot = {"refresh_driver": "protocol", "refresh_protocol_version": "v1", "auto_refresh_at_enabled": True}
        with patch.object(bulk_submission, "_capture", return_value=(snapshot, tuple(snapshot), snapshot)), \
                patch("core.accounts.liveness.service.deployment_unavailable", return_value=None), \
                patch("core.operations.task_gateway.notify_dispatch"):
            token = bulk_submission.submit_accounts([7], operation="token")
            bulk_submission.submit_accounts([8], operation="plan")
            plan = bulk_submission.submit_accounts([8], operation="plan")
        self.assertEqual(token["failed_count"], 1)
        self.assertEqual(token["skipped_count"], 0)
        self.assertEqual(plan["busy_count"], 1)
        self.assertEqual(plan["skipped_count"], 0)

    def test_execution_routes_submit_whole_selection_once(self):
        from webui.app import create_app
        client = create_app(auth_code="synthetic-auth").test_client()
        headers = {"X-Auth-Code": "synthetic-auth"}
        response = {"accepted": True, "started": [{"id": 7, "task_id": 9007199254740993, "run_id": 9007199254740995}],
                    "batch_id": 9007199254740997, "started_count": 1, "skipped": [], "skipped_count": 0}
        for endpoint, body, operation in (
            ("setup-bulk", {"account_ids": [7, 8]}, "setup"),
            ("action-bulk", {"account_ids": [7, 8], "action": "password"}, "password"),
            ("complete-bulk", {"account_ids": [7, 8]}, "complete"),
            ("check-live-bulk", {"account_ids": [7, 8]}, "live"),
            ("refresh-token-bulk", {"account_ids": [7, 8]}, "token"),
            ("check-plan-bulk", {"account_ids": [7, 8]}, "plan"),
            ("c2a/sync-bulk", {"account_ids": [7, 8]}, "c2a"),
        ):
            with self.subTest(endpoint=endpoint), patch("webui.routes.accounts._feature_unavailable", return_value=None), \
                    patch.object(bulk_submission, "submit_accounts", return_value=response) as submit:
                result = client.post("/api/accounts/" + endpoint, json=body, headers=headers)
                self.assertEqual(result.status_code, 202)
                self.assertEqual(submit.call_args.args, ([7, 8],))
                self.assertEqual(submit.call_args.kwargs["operation"], operation)
                submit.assert_called_once()
                self.assertEqual(result.json["started"][0]["id"], "7")
                self.assertEqual(result.json["started"][0]["task_id"], "9007199254740993")
                self.assertEqual(result.json["batch_id"], "9007199254740997")
