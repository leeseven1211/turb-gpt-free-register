"""手动上传经共享准入执行，原手动步骤不恢复远端调度。"""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import patch

from core.integrations.sub2api import client, manual_upload
from core.operations import concurrency, task_gateway
from core.storage import codex, records, runtime_config
from core.storage.operations import store as operation
from core.storage.operations import legacy_task_store
from tests.support_pg import PostgresTestCase


class Sub2ApiManualUploadTests(PostgresTestCase):
    def setUp(self):
        operation.reset_ready()
        operation.init()
        legacy_schema = patch.object(legacy_task_store, "_SCHEMA", self.schema)
        legacy_schema.start()
        self.addCleanup(legacy_schema.stop)
        task_gateway.init()
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": "manual-upload@example.test", "codex_status": "success",
            "created_at": "2026-11-05", "updated_at": "2026-11-05",
        })
        self.filename = "codex-manual-upload@example.test-free.json"
        self.auth = {"email": "manual-upload@example.test", "access_token": "fixture-at", "refresh_token": "fixture-rt"}
        codex.save_codex_credential_record(self.filename, self.auth)
        for context in (
            patch.object(client, "configured_backend_identity", return_value="fixture-backend"),
            patch.object(task_gateway, "notify_dispatch"),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.addCleanup(task_gateway.unregister_operation_handler, manual_upload.TASK_TYPE)

    def execute(self, queued):
        return task_gateway._execute_operation_handler(manual_upload.TASK_TYPE, queued["run_id"])

    def test_queue_does_not_upload_and_persists_only_original_reference(self):
        with patch.object(client, "upload_configured_codex_oauth_credential") as upload:
            result = manual_upload.queue_filename(self.filename)
        upload.assert_not_called()
        self.assertTrue(result["accepted"])
        self.assertEqual("queued", result["status"])
        run = operation.get_run(result["run_id"])
        self.assertEqual(manual_upload.TASK_TYPE, run["task_type"])
        self.assertEqual("sub2api_sync", concurrency.resolve_admission_class(run).key)
        self.assertNotIn("fixture-at", str(run["data"]))
        self.assertNotIn("fixture-rt", str(run["data"]))
        self.assertGreater(run["data"]["credential_id"], 0)

    def test_worker_keeps_manual_steps_and_marks_local_state_only_after_upload(self):
        result = manual_upload.queue_filename(self.filename)
        with patch.object(client, "upload_configured_codex_oauth_credential", return_value={"ok": True, "status_code": 200}) as upload, patch.object(
            client, "upload_and_enable_configured_codex_oauth_credential"
        ) as automatic, patch.object(client, "_enable_account") as enable:
            finished = self.execute(result)
        self.assertTrue(finished["ok"])
        self.assertEqual(self.auth, upload.call_args.args[0])
        self.assertEqual("fixture-backend", upload.call_args.kwargs["expected_backend"])
        self.assertTrue(callable(upload.call_args.kwargs["checkpoint"]))
        automatic.assert_not_called()
        enable.assert_not_called()
        row = next(item for item in codex.list_codex_accounts(archived="all") if item["filename"] == self.filename)
        self.assertEqual(1, row["exported_count"])
        self.assertEqual(1, row["sub2_uploaded_count"])
        self.assertEqual(0, concurrency.get_concurrency_status()["global"]["occupied"])

    def test_remote_failure_keeps_export_counters_and_classified_final_result(self):
        result = manual_upload.queue_filename(self.filename)
        with patch.object(client, "upload_configured_codex_oauth_credential", side_effect=client.Sub2ApiSyncError(
            "upload", "sub2api_auth_rejected", "Sub2API 鉴权失败"
        )):
            self.assertFalse(self.execute(result)["ok"])
        run = operation.get_run(result["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("sub2api_auth_rejected", run["result_summary"]["error_code"])
        row = codex.list_codex_accounts(archived="all")[0]
        self.assertEqual(0, row["exported_count"])
        self.assertEqual(0, row["sub2_uploaded_count"])

    def test_timeout_remains_unknown_and_explicit_retry_is_not_blocked(self):
        result = manual_upload.queue_filename(self.filename)
        with patch.object(client, "upload_configured_codex_oauth_credential", side_effect=client.Sub2ApiSyncError(
            "upload", "sub2api_timeout", "Sub2API 请求超时"
        )):
            self.execute(result)
        task = operation.get_task(result["task_id"])
        self.assertEqual("attention_required", task["status"])
        retried = task_gateway.default_operation_retry(task)
        self.assertTrue(retried["accepted"])
        self.assertNotEqual(result["run_id"], retried["run_id"])

    def test_backend_or_credential_generation_change_does_not_upload(self):
        result = manual_upload.queue_filename(self.filename)
        with patch.object(client, "configured_backend_identity", return_value="other-backend"), patch.object(
            client, "upload_configured_codex_oauth_credential"
        ) as upload:
            self.execute(result)
        upload.assert_not_called()
        self.assertEqual("sub2api_backend_changed", operation.get_run(result["run_id"])["result_summary"]["error_code"])

    def test_deleted_original_id_never_falls_back_to_recreated_same_filename(self):
        result = manual_upload.queue_filename(self.filename)
        original_id = operation.get_run(result["run_id"])["data"]["credential_id"]
        records.delete_rows(records.CODEX_CREDENTIALS, [original_id])
        codex.save_codex_credential_record(self.filename, self.auth)
        replacement = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
        self.assertNotEqual(original_id, replacement["id"])
        with patch.object(client, "upload_configured_codex_oauth_credential") as upload:
            self.execute(result)
        upload.assert_not_called()
        self.assertEqual("sub2api_credential_missing", operation.get_run(result["run_id"])["result_summary"]["error_code"])
        self.assertEqual(0, records.get_row(records.CODEX_CREDENTIALS, replacement["id"])["exported_count"])

    def test_remote_success_cannot_increment_new_generation_or_same_name_replacement(self):
        for replace_row in (False, True):
            with self.subTest(replace_row=replace_row):
                codex.save_codex_credential_record(self.filename, self.auth)
                queued = manual_upload.queue_filename(self.filename)
                original_id = operation.get_run(queued["run_id"])["data"]["credential_id"]
                def upload(*_args, **_kwargs):
                    if replace_row:
                        records.delete_rows(records.CODEX_CREDENTIALS, [original_id])
                    codex.save_codex_credential_record(self.filename, {**self.auth, "refresh_token": "fixture-new-generation"})
                    return {"ok": True, "status_code": 200}
                with patch.object(client, "upload_configured_codex_oauth_credential", side_effect=upload):
                    self.assertFalse(self.execute(queued)["ok"])
                run = operation.get_run(queued["run_id"])
                self.assertEqual("attention_required", run["status"])
                self.assertTrue(run["result_summary"]["uploaded"])
                self.assertEqual("local_writeback", run["result_summary"]["stage"])
                current = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
                self.assertEqual(0, current["exported_count"])
                self.assertEqual(0, int(current.get("sub2_uploaded_count") or 0))

    def test_counter_write_and_readback_failure_rolls_back_both_counters(self):
        queued = manual_upload.queue_filename(self.filename)
        original_patch = records.patch_row
        def broken_patch(table, row_id, changes, **kwargs):
            applied = original_patch(table, row_id, changes, **kwargs)
            if table is records.CODEX_CREDENTIALS and "sub2_uploaded_count" in changes:
                raise RuntimeError("测试原子写回失败")
            return applied
        with patch.object(client, "upload_configured_codex_oauth_credential", return_value={"ok": True}), patch.object(records, "patch_row", side_effect=broken_patch):
            self.execute(queued)
        current = records.get_row_by(records.CODEX_CREDENTIALS, "filename", self.filename)
        self.assertEqual(0, current["exported_count"])
        self.assertEqual(0, int(current.get("sub2_uploaded_count") or 0))
        run = operation.get_run(queued["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("sub2api_manual_local_writeback_failed", run["result_summary"]["error_code"])

    def test_manual_upload_uses_global_and_sync_type_budget_with_other_business(self):
        queued = manual_upload.queue_filename(self.filename)
        entered, release = threading.Event(), threading.Event()
        def upload(*_args, **_kwargs):
            entered.set()
            self.assertTrue(release.wait(10))
            return {"ok": True}
        policy = {"GLOBAL_TASK_WORKERS": "1", "SUB2API_SYNC_WORKERS": "1", "CONCURRENCY_POLICY_REVISION": "1"}
        with patch.object(runtime_config, "read_values", return_value=policy), patch.object(
            client, "upload_configured_codex_oauth_credential", side_effect=upload
        ), ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(self.execute, queued)
            try:
                self.assertTrue(entered.wait(5))
                snapshot = concurrency.get_concurrency_status()
                self.assertEqual(1, snapshot["global"]["occupied"])
                sync = next(item for item in snapshot["types"] if item["key"] == "sub2api_sync")
                self.assertEqual(1, sync["occupied"])
                other = concurrency.try_admit_and_claim(execution_key="fixture:other", task_type="plan_check", claim=lambda _conn, _execution: {"id": 999})
                self.assertFalse(other.admitted)
                self.assertIn("global_capacity", other.blocked_by)
            finally:
                release.set()
            self.assertTrue(pending.result(timeout=10)["ok"])


class ManualUploadClientCompatibilityTests(PostgresTestCase):
    def test_omitted_optional_parameters_preserve_original_manual_mode(self):
        auth = {"email": "fixture@example.test", "refresh_token": "fixture"}
        with patch.object(client, "_configured_upload", return_value={"ok": True}) as upload:
            self.assertTrue(client.upload_configured_codex_oauth_credential(auth)["ok"])
        upload.assert_called_once_with(auth, checkpoint=None, enable=False, expected_backend=None)
