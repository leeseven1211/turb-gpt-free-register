# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from core.codex import oauth as codex_oauth
from core.codex import operation_service as codex_operation_service
from core import account_task_store
from core.storage import records as record_store
from core.operations import run_log as task_run_log
from core.codex.operation_service import classify_codex_operation_result
from core.operations.runtime import CancellationToken, OperationCancelled
from core.operations.errors import classify_task_error
from tests.support_pg import PostgresTestCase


class CodexCredentialSemanticsTests(unittest.TestCase):
    def test_account_deactivated_result_is_terminal_even_when_wrapped_as_attention(self):
        status, credential_state, error = classify_codex_operation_result(
            {
                "status": "attention_required",
                "message": "账号已废（account_deactivated）",
            },
            confirmed=False,
            callback_submitted=False,
            existing_valid=True,
        )

        self.assertEqual("deactivated", status)
        self.assertEqual("deactivated", credential_state)
        self.assertEqual("账号已废（account_deactivated）", error)

    def test_remote_write_attention_without_deactivation_stays_pending(self):
        status, credential_state, error = classify_codex_operation_result(
            {
                "status": "attention_required",
                "message": "远端凭证待确认",
            },
            confirmed=False,
            callback_submitted=True,
            existing_valid=True,
        )

        self.assertEqual("attention_required", status)
        self.assertEqual("valid", credential_state)
        self.assertEqual("远端凭证待确认", error)

    def test_callback_receipt_is_not_reported_as_saved_credential(self):
        with patch.object(
            codex_oauth, "_save_cpa_local_record",
            return_value=Path("/tmp/codex-user-cpa-callback.json"),
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"message": "accepted"},
            )
        self.assertFalse(result["ok"])
        self.assertEqual("attention_required", result["status"])
        self.assertFalse(result["credential_confirmed"])
        self.assertIsNone(result["file_path"])
        self.assertTrue(result["receipt_path"].endswith("-cpa-callback.json"))

    def test_embedded_auth_json_is_confirmed_success(self):
        with patch.object(
            codex_oauth, "_save_cpa_local_record",
            return_value=Path("/tmp/codex-user-free.json"),
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"auth_json": {"type": "codex", "access_token": "secret"}},
            )
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        self.assertTrue(result["credential_confirmed"])
        self.assertTrue(result["file_path"].endswith("-free.json"))
        self.assertIsNone(result["receipt_path"])

    def test_cpa_reconciliation_confirms_new_remote_credential(self):
        confirmed_path = Path("/tmp/codex-user-free.json")
        with (
            patch.object(
                codex_oauth, "_save_cpa_local_record",
                return_value=Path("/tmp/codex-user-cpa-callback.json"),
            ),
            patch.object(
                codex_oauth, "_confirm_cpa_credential_after_callback",
                return_value=confirmed_path,
            ) as confirm,
        ):
            result = codex_oauth._remote_callback_result(
                source="cpa",
                email="user@example.com",
                callback_url="http://localhost/callback",
                auth_url="https://auth.example",
                state="state",
                submit_payload={"message": "accepted"},
                cpa_baseline={"captured": True, "fingerprint": "old"},
            )
        confirm.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertEqual("success", result["status"])
        self.assertTrue(result["credential_confirmed"])
        self.assertEqual(str(confirmed_path), result["file_path"])
        self.assertIsNone(result["receipt_path"])

    def test_retry_task_rejects_currently_deactivated_account(self):
        task = {
            "id": 41,
            "source_system": "native_operations",
            "account_id": 7,
            "status": "failed",
            "target_status": "failed",
        }
        with (
            patch.object(codex_operation_service.operation_task_store, "get_task", return_value=task),
            patch.object(
                codex_operation_service.db,
                "get_account",
                return_value={"id": 7, "account_status": "deactivated"},
            ),
            patch.object(codex_operation_service.operation_task_store, "active_run_for_account") as active,
            patch.object(codex_operation_service.operation_task_store, "retry_runtime_task") as retry,
        ):
            result = codex_operation_service.retry_task(41)

        self.assertFalse(result["accepted"])
        self.assertTrue(result["deactivated"])
        active.assert_not_called()
        retry.assert_not_called()

    def test_retry_task_overrides_only_new_run_driver_snapshot(self):
        task = {
            "id": 41,
            "task_type": "codex_retry",
            "source_system": "native_operations",
            "account_id": 7,
            "email_snapshot": "user@example.test",
            "status": "attention_required",
        }
        snapshot = {"oauth_driver": "roxy", "auth_source": "local"}
        with (
            patch.object(codex_operation_service.operation_task_store, "get_task", return_value=task),
            patch.object(codex_operation_service.db, "get_account", return_value={"id": 7}),
            patch.object(codex_operation_service.db, "account_is_deactivated", return_value=False),
            patch.object(codex_operation_service.operation_task_store, "active_run_for_account", return_value=None),
            patch.object(codex_operation_service, "_feature_ready", return_value=(True, "")),
            patch.object(codex_operation_service, "_config_snapshot", return_value=snapshot) as config,
            patch.object(
                codex_operation_service.operation_task_store,
                "retry_runtime_task",
                return_value={"id": 52, "log_file": None},
            ) as retry,
            patch.object(codex_operation_service.db, "update_account_codex_operation_state"),
            patch.object(codex_operation_service.task_run_log, "append"),
            patch.object(codex_operation_service, "_dispatch") as dispatch,
        ):
            result = codex_operation_service.retry_task(41, driver="roxy")

        self.assertTrue(result["accepted"])
        self.assertEqual(52, result["run_id"])
        config.assert_called_once_with(driver_override="roxy")
        retry.assert_called_once_with(
            41,
            trigger="manual_retry",
            data={"config_snapshot": snapshot},
        )
        dispatch.assert_called_once_with(52)

    def test_retry_task_rejects_unsupported_driver_before_storage_access(self):
        with patch.object(codex_operation_service.operation_task_store, "get_task") as get_task:
            result = codex_operation_service.retry_task(41, driver="api")
        self.assertFalse(result["accepted"])
        get_task.assert_not_called()


class CodexFailureDiagnosticsPersistenceTests(PostgresTestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        log_root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.object(task_run_log, "_LOG_ROOT", log_root))
        stack.enter_context(patch.object(task_run_log, "_TASK_LOG_ROOT", log_root / "tasks"))
        stack.enter_context(patch.dict(os.environ, {"OPERATION_TASK_DB_SCHEMA": self.schema}))
        stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()

    def _execute_failed_consent(self, diagnostics, *, cause_code="codex_consent_unverifiable", error_category="auth"):
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": "consent@example.test",
            "codex_status": "failed",
            "account_status": "active",
        })
        store = codex_operation_service.operation_task_store
        task = store.create_runtime_task(
            task_type="codex_retry", account_id=account_id, email="consent@example.test",
            data={"config_snapshot": {"oauth_driver": "protocol"}},
        )
        route = Mock(proxy_url=None, provider="test", mode="direct", region="")
        route.public_dict.return_value = {"network_route": "test-direct"}
        with (
            patch.object(codex_operation_service, "_feature_ready", return_value=(True, "")),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(codex_oauth, "run_codex_oauth", return_value={
                "ok": False,
                "status": "failed",
                "message": "Codex 授权确认页无法继续，需浏览器驱动",
                "cause_code": cause_code,
                "error_category": error_category,
                "auth_diagnostics": diagnostics,
                "raw_response": "synthetic-private-response",
            }),
        ):
            returned = codex_operation_service._execute_run(int(task["run"]["id"]))
        detail = store.get_task(int(task["id"]))
        run = store.get_run(int(task["run"]["id"]))
        return returned, detail, run

    def test_consent_cause_survives_run_and_task_projection_without_secret_fields(self):
        expected = {
            "operation": "consent",
            "failure_kind": "next_step_unverifiable",
            "oauth_driver": "protocol",
            "page_path": "/sign-in-with-chatgpt/codex/consent",
        }
        returned, detail, run = self._execute_failed_consent({
            **expected,
            "access_token": "synthetic-private-access",
            "cookie": "synthetic-private-cookie",
            "response_body": "synthetic-private-body",
            "opaque_value": "synthetic-private-opaque",
        })

        self.assertEqual("attention_required", returned["status"])
        self.assertEqual("attention_required", run["status"])
        for summary in (run["result_summary"], detail["result_summary"], detail["runs"][-1]["result_summary"]):
            self.assertEqual("request_unknown", summary["outcome"])
            self.assertTrue(summary["reconcile_required"])
            self.assertEqual("codex_consent_unverifiable", summary["cause_code"])
            self.assertEqual("auth", summary["error_category"])
            self.assertEqual(expected, summary["auth_diagnostics"])
            self.assertNotIn("raw_response", summary)
        projection = classify_task_error(
            detail["error_message"], task_type=detail["task_type"],
            task_status=detail["status"], error_code=detail["error_code"],
            result_summary=detail["result_summary"],
        )
        self.assertEqual("OA-CODEX-CONSENT-001", projection["display_code"])
        self.assertEqual("manual_reconcile", projection["next_action"])
        self.assertEqual("OA-CODEX-CONSENT-001", projection["cause_display_code"])
        self.assertEqual("Codex 授权确认页无法继续，需浏览器驱动", projection["cause_summary"])
        audit = json.dumps({"summary": run["result_summary"], "events": detail["events"]}, ensure_ascii=False)
        audit += Path(run["log_file"]).read_text(encoding="utf-8")
        self.assertNotIn("synthetic-private-", audit)

    def test_consent_diagnostics_reject_unrecognized_values_in_allowlisted_fields(self):
        _, _, run = self._execute_failed_consent({
            "operation": "synthetic-private-operation",
            "failure_kind": "next_step_unverifiable",
            "oauth_driver": "synthetic-private-driver",
            "page_path": "/sign-in-with-chatgpt/codex/consent?state=synthetic-private-state",
        }, error_category="synthetic-private-category")

        summary = run["result_summary"]
        self.assertEqual("codex_consent_unverifiable", summary["cause_code"])
        self.assertNotIn("error_category", summary)
        self.assertEqual({"failure_kind": "next_step_unverifiable"}, summary["auth_diagnostics"])
        self.assertNotIn("synthetic-private-", json.dumps(summary))

    def test_unknown_cause_cannot_persist_arbitrary_diagnostics(self):
        _, _, run = self._execute_failed_consent(
            {"operation": "consent", "response_body": "synthetic-private-body"},
            cause_code="synthetic-private-cause",
        )

        self.assertEqual("attention_required", run["status"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        self.assertNotIn("cause_code", run["result_summary"])
        self.assertNotIn("error_category", run["result_summary"])
        self.assertNotIn("auth_diagnostics", run["result_summary"])


class CancellationTokenTests(unittest.TestCase):
    def test_cancellation_is_cooperative_and_scoped_to_run(self):
        requested = {12: False}
        token = CancellationToken(12, "token-12", lambda run_id, _token: requested[run_id], poll_interval=0)
        token.checkpoint()
        requested[12] = True
        with self.assertRaises(OperationCancelled):
            token.checkpoint()


if __name__ == "__main__":
    unittest.main()
