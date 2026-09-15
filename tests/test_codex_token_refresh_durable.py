from __future__ import annotations

import json
import threading
from types import MappingProxyType
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

import config
from config import schema as config_schema
from core import account_operation_executor, db, record_store, task_run_log
from core import codex_token_refresh_service as service
from core.operations import task_gateway
from core.storage import operation, operation_runtime_store
from tests.support_pg import PostgresTestCase


class CodexTokenRefreshRequestBoundaryTests(TestCase):
    def test_transport_timeout_is_one_request_unknown_without_retry(self):
        with patch.object(service.requests, "post", side_effect=requests.Timeout("synthetic timeout")) as post:
            with self.assertRaises(service.TokenRefreshRequestUnknownError) as caught:
                service._request_refresh("synthetic-old-refresh")

        self.assertEqual(1, post.call_count)
        self.assertEqual(service.REQUEST_UNKNOWN, caught.exception.code)
        self.assertFalse(caught.exception.remote_response_received)

    def test_server_error_is_unknown_without_retry_or_sleep(self):
        response = Mock(status_code=503)
        response.json.return_value = {"error": "temporarily unavailable"}
        with patch.object(service.requests, "post", return_value=response) as post:
            with self.assertRaises(service.TokenRefreshRequestUnknownError) as caught:
                service._request_refresh("synthetic-old-refresh")

        self.assertEqual(1, post.call_count)
        self.assertEqual(service.REQUEST_UNKNOWN, caught.exception.code)
        self.assertTrue(caught.exception.remote_response_received)


class CodexTokenRefreshSubmissionTests(TestCase):
    def setUp(self):
        self._old_registered = service._HANDLER_REGISTERED
        service._HANDLER_REGISTERED = False

    def tearDown(self):
        service._HANDLER_REGISTERED = self._old_registered

    @staticmethod
    def _row(**overrides):
        row = {
            "filename": "codex-submit@example.test-free.json",
            "email": "submit@example.test",
            "oauth_status": "expiring",
            "oauth_refreshable": True,
            "oauth_refresh_error": None,
        }
        row.update(overrides)
        return row

    def test_submission_uses_gateway_contract_and_never_direct_executor(self):
        durable_result = {
            "accepted": True,
            "busy": False,
            "reused": False,
            "task_id": 71,
            "run_id": 72,
            "status": "queued",
        }
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[self._row()]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(service.operation_runtime_store, "active_run_for_account", return_value=None),
            patch.object(service.operation_runtime_store, "list_reconciliation_accounts", return_value=[]),
            patch.object(service, "_register_worker"),
            patch.object(service, "_update_account_state"),
            patch.object(service.task_gateway, "submit_durable_operation", return_value=durable_result) as submit,
            patch.object(account_operation_executor.executor, "submit") as direct_submit,
        ):
            result = service.enqueue_refresh(
                "codex-submit@example.test-free.json",
                trigger="manual_bulk",
                batch_id="legacy-batch-id",
                idempotency_key="submit-request-1",
            )

        self.assertTrue(result["accepted"])
        kwargs = submit.call_args.kwargs
        self.assertEqual(service.TASK_TYPE, kwargs["task_type"])
        self.assertEqual("native_operations", kwargs["source_system"])
        self.assertEqual("submit-request-1", kwargs["idempotency_key"])
        self.assertEqual(service.RESOURCE_FAMILY, kwargs["resource_family"])
        self.assertTrue(kwargs["dispatch"])
        self.assertEqual("codex-submit@example.test-free.json", kwargs["data"]["credential_filename"])
        self.assertEqual("legacy-batch-id", kwargs["data"]["legacy_batch_id"])
        self.assertNotIn("config_snapshot", kwargs["data"])
        self.assertEqual({"request_timeout": "CODEX_REQUEST_TIMEOUT"}, kwargs["config_allowlist"])
        self.assertIsInstance(kwargs["config_snapshot"], config_schema.ConfigSnapshot)
        direct_submit.assert_not_called()

    def test_submission_uses_published_canonical_snapshot_and_revision(self):
        candidate = config_schema.ConfigSnapshot(
            MappingProxyType({
                "CODEX_REQUEST_TIMEOUT": 17,
                "CODEX_TOKEN_URL": "https://synthetic.invalid/oauth/token",
                "UNRELATED_GLOBAL_SETTING": "must-not-persist",
            }),
            MappingProxyType({"CODEX_REQUEST_TIMEOUT": "test"}),
            revision=0,
        )
        previous_published = config_schema._PUBLISHED_SNAPSHOT
        try:
            published = config_schema.publish_config_snapshot(candidate)
            durable_result = {
                "accepted": True,
                "busy": False,
                "reused": False,
                "task_id": 171,
                "run_id": 172,
                "status": "queued",
            }
            with (
                patch.object(service.db, "list_codex_accounts", return_value=[self._row()]),
                patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
                patch.object(service.operation_runtime_store, "active_run_for_account", return_value=None),
                patch.object(service.operation_runtime_store, "list_reconciliation_accounts", return_value=[]),
                patch.object(service, "_register_worker"),
                patch.object(service, "_update_account_state"),
                patch.object(config, "non_sensitive_snapshot", return_value=published) as canonical,
                patch.object(service.task_gateway, "submit_durable_operation", return_value=durable_result) as submit,
            ):
                result = service.enqueue_refresh(
                    "codex-submit@example.test-free.json",
                    idempotency_key="canonical-snapshot-request",
                )
        finally:
            config_schema._PUBLISHED_SNAPSHOT = previous_published

        self.assertTrue(result["accepted"])
        snapshot = submit.call_args.kwargs["config_snapshot"]
        self.assertIs(snapshot, published)
        self.assertEqual(published.revision, snapshot.revision)
        self.assertEqual(17, snapshot["CODEX_REQUEST_TIMEOUT"])
        self.assertEqual({"request_timeout": "CODEX_REQUEST_TIMEOUT"}, submit.call_args.kwargs["config_allowlist"])
        canonical.assert_called_once_with()

    def test_duplicate_durable_submission_returns_busy_from_database(self):
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[self._row()]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(service.operation_runtime_store, "active_run_for_account", return_value={"id": 99, "task_id": 98, "status": "queued"}),
            patch.object(service, "_register_worker"),
        ):
            result = service.enqueue_refresh("codex-submit@example.test-free.json")

        self.assertFalse(result["accepted"])
        self.assertTrue(result["busy"])
        self.assertEqual(99, result["run_id"])

    def test_unknown_marker_blocks_normal_submit(self):
        row = self._row(
            oauth_refresh_error="request_unknown: needs_reconciliation",
        )
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(service, "_register_worker"),
            patch.object(service, "_durable_submit") as submit,
        ):
            blocked = service.enqueue_refresh("codex-submit@example.test-free.json")

        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])
        self.assertEqual("manual_reconcile", blocked["next_action"])
        submit.assert_not_called()

    def test_reconcile_flag_cannot_bypass_unknown_marker_or_send_http(self):
        row = self._row(
            oauth_refresh_error="request_unknown: needs_reconciliation",
        )
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(service, "_durable_submit") as submit,
            patch.object(service.requests, "post") as post,
        ):
            blocked = service.enqueue_refresh(
                row["filename"], reconcile=True, idempotency_key="reconcile-attempt",
            )

        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])
        self.assertEqual("manual_reconcile", blocked["next_action"])
        submit.assert_not_called()
        post.assert_not_called()

    def test_manual_submit_uses_durable_fence_when_credential_marker_is_missing(self):
        row = self._row(oauth_refresh_error=None, account_id="provider-account")
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(
                service.operation_runtime_store,
                "list_reconciliation_accounts",
                return_value=[{
                    "account_id": 17,
                    "run_status": "attention_required",
                    "remote_intent_state": "confirmed",
                    "reconcile_required": True,
                }],
            ) as list_fence,
            patch.object(service, "_durable_submit") as submit,
            patch.object(service.requests, "post") as post,
        ):
            blocked = service.enqueue_refresh(row["filename"])

        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])
        self.assertTrue(blocked["reconcile_required"])
        self.assertEqual([17], list_fence.call_args.kwargs["account_ids"])
        submit.assert_not_called()
        post.assert_not_called()

    def test_reconcile_flag_blocks_clean_credential_before_durable_submit(self):
        row = self._row(oauth_refresh_error=None, account_id="provider-account")
        with (
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}),
            patch.object(
                service.operation_runtime_store,
                "list_reconciliation_accounts",
                return_value=[],
            ) as list_fence,
            patch.object(service.operation_runtime_store, "active_run_for_account", return_value=None),
            patch.object(service, "_register_worker"),
            patch.object(
                service,
                "_durable_submit",
                return_value={
                    "accepted": True,
                    "busy": False,
                    "reused": False,
                    "task_id": 18,
                    "run_id": 19,
                    "status": "queued",
                },
            ) as submit,
            patch.object(service, "_update_account_state"),
            patch.object(service.requests, "post") as post,
        ):
            blocked = service.enqueue_refresh(
                row["filename"], reconcile=True, idempotency_key="clean-reconcile-attempt",
            )

        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])
        self.assertEqual("manual_reconcile", blocked["next_action"])
        self.assertTrue(blocked["reconcile_required"])
        self.assertEqual([17], list_fence.call_args.kwargs["account_ids"])
        submit.assert_not_called()
        post.assert_not_called()

    def test_registration_is_once_only_under_concurrent_calls(self):
        service._HANDLER_REGISTERED = False
        with (
            patch.object(service.task_gateway, "register_operation_handler") as register,
            patch.object(service.task_gateway, "notify_dispatch"),
        ):
            threads = [threading.Thread(target=service._register_worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(1, register.call_count)
        self.assertEqual(service.TASK_TYPE, register.call_args.args[0])

    def test_resume_only_lists_and_wakes_queued_runs(self):
        service._HANDLER_REGISTERED = False
        with (
            patch.object(service, "_register_worker"),
            patch.object(service.task_gateway, "notify_dispatch") as notify,
            patch.object(
                service.operation_runtime_store,
                "list_queued_runs",
                return_value=[{"task_type": service.TASK_TYPE}, {"task_type": "other"}],
            ),
            patch.object(service.operation_runtime_store, "claim_run") as claim,
        ):
            resumed = service.resume_queued()

        self.assertEqual(1, resumed)
        notify.assert_called_once_with()
        claim.assert_not_called()

    def test_cancel_is_durable_and_does_not_touch_process_local_executor(self):
        with (
            patch.object(
                service.operation_runtime_store,
                "request_run_cancel",
                return_value={"id": 72, "status": "cancelling"},
            ) as cancel,
            patch.object(service, "_update_account_state"),
            patch.object(service.task_gateway, "notify_dispatch") as notify,
            patch.object(account_operation_executor.executor, "submit") as direct_submit,
        ):
            result = service.request_cancel(run_id=72, email="submit@example.test")

        self.assertTrue(result["ok"])
        self.assertEqual("cancelling", result["state"])
        cancel.assert_called_once_with(72, reason="用户手动停止 Codex token refresh")
        notify.assert_called_once_with()
        direct_submit.assert_not_called()

    def test_producer_resolves_provider_account_id_before_fence_query(self):
        row = self._row(account_id="chatgpt-provider-account")
        with (
            patch.object(service._cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True),
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service.db, "get_account_by_email", return_value={"id": 17}) as get_account,
            patch.object(service, "_reconcile_abandoned_refresh_markers", return_value=0),
            patch.object(
                service.operation_runtime_store,
                "list_reconciliation_accounts",
                return_value=[],
            ) as list_fence,
            patch.object(service, "enqueue_refresh", return_value={"accepted": True}) as enqueue,
        ):
            result = service.enqueue_due_credentials()

        self.assertEqual(1, result["started"])
        get_account.assert_called()
        self.assertEqual([17], list_fence.call_args.kwargs["account_ids"])
        enqueue.assert_called_once_with(
            row["filename"], trigger="codex_token_refresh_scheduled",
        )

    def test_producer_fence_read_failure_is_fail_closed(self):
        row = self._row(account_id=17)
        with (
            patch.object(service._cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True),
            patch.object(service.db, "list_codex_accounts", return_value=[row]),
            patch.object(service, "_reconcile_abandoned_refresh_markers", return_value=0),
            patch.object(
                service.operation_runtime_store,
                "list_reconciliation_accounts",
                side_effect=RuntimeError("synthetic fence outage"),
            ),
            patch.object(service, "enqueue_refresh", return_value={"accepted": True}) as enqueue,
        ):
            result = service.enqueue_due_credentials()

        self.assertEqual(0, result["started"])
        self.assertEqual(1, result["skipped"])
        enqueue.assert_not_called()

    def test_producer_queries_all_candidate_accounts_in_bounded_batches(self):
        rows = [
            self._row(
                filename=f"codex-candidate-{index}.json",
                email="",
                account_id=str(index),
            )
            for index in range(1, 1002)
        ]
        with (
            patch.object(service._cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True),
            patch.object(service.db, "list_codex_accounts", return_value=rows),
            patch.object(service, "_reconcile_abandoned_refresh_markers", return_value=0),
            patch.object(
                service.operation_runtime_store,
                "list_reconciliation_accounts",
                return_value=[],
            ) as list_fence,
            patch.object(service, "enqueue_refresh", return_value={"accepted": True}),
        ):
            service.enqueue_due_credentials()

        self.assertEqual(3, list_fence.call_count)
        queried = [
            account_id
            for call in list_fence.call_args_list
            for account_id in call.kwargs["account_ids"]
        ]
        self.assertEqual(list(range(1, 1002)), queried)
        self.assertTrue(all(len(call.kwargs["account_ids"]) <= 500 for call in list_fence.call_args_list))


class CodexTokenRefreshDurablePostgresTests(PostgresTestCase):
    def setUp(self):
        task_gateway.unregister_operation_handler(service.TASK_TYPE)
        service._HANDLER_REGISTERED = False

    def tearDown(self):
        task_gateway.unregister_operation_handler(service.TASK_TYPE)
        service._HANDLER_REGISTERED = False

    def _seed_credential(self, stem: str, *, expired: str = "2020-01-01T00:00:00Z") -> tuple[int, str, str]:
        email = f"{stem}@example.test"
        filename = f"codex-{stem}@example.test-free.json"
        account_id = record_store.insert_row(record_store.ACCOUNTS, {
            "email": email,
            "access_token": "synthetic-account-access",
            "codex_status": "failed",
            "account_status": "active",
            "created_at": "2026-09-14T10:00:00",
            "updated_at": "2026-09-14T10:00:00",
        })
        db.save_codex_credential_record(filename, {
            "type": "codex",
            "email": email,
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expired": expired,
            "account_id": str(account_id),
        })
        return account_id, email, filename

    @staticmethod
    def _create_run(account_id: int, email: str, filename: str, source_id: str):
        return operation.create_runtime_task(
            task_type=service.TASK_TYPE,
            account_id=account_id,
            email=email,
            source_system="native_operations",
            source_id=source_id,
            data={
                "credential_filename": filename,
                "resource_family": service.RESOURCE_FAMILY,
                "config_snapshot": {"CODEX_REQUEST_TIMEOUT": 5},
            },
        )

    def test_real_submission_persists_only_allowlisted_timeout_and_revision(self):
        _account_id, _email, filename = self._seed_credential("canonical-persist")
        candidate = config_schema.ConfigSnapshot(
            MappingProxyType({
                "CODEX_REQUEST_TIMEOUT": 19,
                "CODEX_TOKEN_URL": "https://synthetic.invalid/oauth/token",
                "UNRELATED_GLOBAL_SETTING": "must-not-persist",
            }),
            MappingProxyType({"CODEX_REQUEST_TIMEOUT": "test"}),
            revision=0,
        )
        previous_published = config_schema._PUBLISHED_SNAPSHOT
        try:
            published = config_schema.publish_config_snapshot(candidate)
            with patch.object(config, "non_sensitive_snapshot", return_value=published):
                submitted = service.enqueue_refresh(
                    filename,
                    trigger="manual",
                    idempotency_key="canonical-persist-request",
                )
        finally:
            config_schema._PUBLISHED_SNAPSHOT = previous_published

        self.assertTrue(submitted["accepted"])
        run = operation.get_run(int(submitted["run_id"]))
        self.assertEqual(
            {
                "request_timeout": 19,
                "config_snapshot_revision": published.revision,
            },
            run["data"]["config_snapshot"],
        )
        self.assertNotIn("CODEX_TOKEN_URL", run["data"]["config_snapshot"])
        self.assertNotIn("UNRELATED_GLOBAL_SETTING", run["data"]["config_snapshot"])

    def test_preferred_handler_persists_rotated_credentials_and_receipt_calls(self):
        account_id, email, filename = self._seed_credential("preferred")
        created = self._create_run(account_id, email, filename, "preferred-run")
        service._register_worker()
        response = {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}
        order = []
        real_persist = service._persist_refreshed_credential

        def persist(*args, **kwargs):
            order.append("credential_persist")
            return real_persist(*args, **kwargs)

        with (
            patch.object(service, "_request_refresh", return_value=response) as refresh,
            patch.object(service, "_sync_sub2_if_needed", return_value={"status": "disabled"}),
            patch.object(service, "_persist_refreshed_credential", side_effect=persist),
            patch.object(task_gateway.OperationHandlerContext, "remote_request_started", create=True) as started,
            patch.object(task_gateway.OperationHandlerContext, "remote_request_receipt", create=True) as receipt,
        ):
            receipt.side_effect = lambda **kwargs: order.append(kwargs["outcome"])
            returned = task_gateway._execute_operation_handler(
                service.TASK_TYPE,
                int(created["run"]["id"]),
            )

        self.assertEqual("success", returned["status"])
        self.assertEqual("success", operation.get_run(int(created["run"]["id"]))["status"])
        refresh.assert_called_once_with("old-refresh", config_snapshot={"CODEX_REQUEST_TIMEOUT": 5})
        started.assert_called_once()
        self.assertEqual("remote_write", started.call_args.kwargs["intent_kind"])
        self.assertEqual(2, receipt.call_count)
        self.assertEqual("received", receipt.call_args_list[0].kwargs["outcome"])
        self.assertFalse(receipt.call_args_list[0].kwargs["detail"]["terminal"])
        self.assertEqual("confirmed", receipt.call_args_list[1].kwargs["outcome"])
        self.assertTrue(receipt.call_args_list[1].kwargs["detail"]["readback_confirmed"])
        self.assertTrue(receipt.call_args_list[1].kwargs["detail"]["remote_result_confirmed"])
        self.assertTrue(receipt.call_args_list[1].kwargs["detail"]["local_business_writeback_confirmed"])
        self.assertTrue(receipt.call_args_list[1].kwargs["detail"]["local_readback_confirmed"])
        self.assertEqual(["received", "credential_persist", "confirmed"], order)
        text, _ = db.read_codex_credential(filename)
        stored = json.loads(text)
        self.assertEqual("new-access", stored["access_token"])
        self.assertEqual("new-refresh", stored["refresh_token"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIsNone(row["oauth_refresh_error"])
        summary = operation.get_run(int(created["run"]["id"]))["result_summary"]
        self.assertTrue(summary["credential_persisted"])
        self.assertTrue(summary["credential_rotated"], summary)
        self.assertTrue(summary["execution_id"])

    def test_cancel_during_http_settles_rotated_credential_once(self):
        account_id, email, filename = self._seed_credential("cancel-during-http")
        created = self._create_run(account_id, email, filename, "cancel-during-http-run")
        service._register_worker()
        run_id = int(created["run"]["id"])
        http_entered = threading.Event()
        release_http = threading.Event()
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "settled-access",
            "refresh_token": "settled-refresh",
            "expires_in": 604800,
        }

        def blocking_post(*_args, **_kwargs):
            http_entered.set()
            if not release_http.wait(timeout=5):
                raise RuntimeError("synthetic HTTP gate was not released")
            return response

        returned: dict[str, object] = {}

        def run_handler() -> None:
            try:
                returned["result"] = task_gateway._execute_operation_handler(
                    service.TASK_TYPE, run_id,
                )
            except BaseException as exc:  # surface worker failures in the test thread
                returned["error"] = exc

        worker = threading.Thread(target=run_handler, name="synthetic-token-refresh")
        with (
            patch.object(service.requests, "post", side_effect=blocking_post) as post,
            patch.object(service, "_sync_sub2_if_needed", return_value={"status": "disabled"}),
        ):
            worker.start()
            self.assertTrue(http_entered.wait(timeout=5))
            cancelled = operation_runtime_store.request_run_cancel(
                run_id, reason="synthetic cancel during HTTP response wait",
            )
            self.assertEqual("cancelling", cancelled["status"])
            release_http.set()
            worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertNotIn("error", returned, returned.get("error"))
        result = returned["result"]
        self.assertEqual("success", result["status"])
        self.assertEqual(1, post.call_count)

        run = operation.get_run(run_id)
        self.assertEqual("success", run["status"])
        self.assertEqual("success", run["result_summary"]["status"])
        self.assertTrue(run["result_summary"]["credential_persisted"])
        self.assertTrue(run["result_summary"]["credential_rotated"])
        self.assertIsNotNone(run["cancel_requested_at"])

        text, _ = db.read_codex_credential(filename)
        stored = json.loads(text)
        self.assertEqual("settled-access", stored["access_token"])
        self.assertEqual("settled-refresh", stored["refresh_token"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIsNone(row["oauth_refresh_error"])

        # The successful settlement has a long-lived access token, so a
        # subsequent producer scan must not create a second refresh attempt.
        with patch.object(service._cfg, "CODEX_TOKEN_AUTO_REFRESH_ENABLED", True):
            due = service.enqueue_due_credentials()
        self.assertEqual(0, due["started"])
        self.assertEqual(1, post.call_count)

    def test_lease_loss_after_http_response_blocks_local_write(self):
        account_id, email, filename = self._seed_credential("lease-loss-after-http")
        created = self._create_run(account_id, email, filename, "lease-loss-after-http-run")
        service._register_worker()
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "must-not-be-written",
            "refresh_token": "must-not-be-written",
            "expires_in": 604800,
        }
        run_id = int(created["run"]["id"])

        with (
            patch.object(service.requests, "post", return_value=response) as post,
            patch.object(service, "_persist_refreshed_credential") as persist,
            patch.object(
                task_gateway.OperationLease,
                "heartbeat",
                side_effect=[True, True, False],
            ),
        ):
            returned = task_gateway._execute_operation_handler(service.TASK_TYPE, run_id)

        self.assertEqual(service.REQUEST_UNKNOWN, returned["status"])
        self.assertEqual(1, post.call_count)
        persist.assert_not_called()
        run = operation.get_run(run_id)
        self.assertEqual("attention_required", run["status"])
        self.assertEqual(service.REQUEST_UNKNOWN, run["result_summary"]["outcome"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        text, _ = db.read_codex_credential(filename)
        stored = json.loads(text)
        self.assertEqual("old-access", stored["access_token"])
        self.assertEqual("old-refresh", stored["refresh_token"])

    def test_timeout_is_attention_required_and_scheduler_cannot_resubmit(self):
        account_id, email, filename = self._seed_credential("timeout")
        created = self._create_run(account_id, email, filename, "timeout-run")
        service._register_worker()
        with patch.object(service.requests, "post", side_effect=requests.Timeout("synthetic timeout")) as post:
            returned = task_gateway._execute_operation_handler(
                service.TASK_TYPE,
                int(created["run"]["id"]),
            )

        self.assertEqual("request_unknown", returned["status"])
        self.assertEqual(1, post.call_count)
        run = operation.get_run(int(created["run"]["id"]))
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("request_unknown", run["result_summary"]["outcome"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIn("request_unknown", row["oauth_refresh_error"])
        blocked = service.enqueue_refresh(filename)
        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])

    def test_manual_submit_is_blocked_by_durable_unknown_without_marker(self):
        account_id, email, filename = self._seed_credential("manual-fence")
        created = self._create_run(account_id, email, filename, "manual-fence-run")
        service._register_worker()
        with patch.object(service.requests, "post", side_effect=requests.Timeout("synthetic timeout")):
            returned = task_gateway._execute_operation_handler(
                service.TASK_TYPE,
                int(created["run"]["id"]),
            )

        self.assertEqual(service.REQUEST_UNKNOWN, returned["status"])
        db.mark_codex_oauth_refresh(filename, error=None)
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIsNone(row["oauth_refresh_error"])
        with (
            patch.object(service, "_durable_submit") as submit,
            patch.object(service.requests, "post") as post,
        ):
            blocked = service.enqueue_refresh(filename)

        self.assertFalse(blocked["accepted"])
        self.assertEqual(service.NEEDS_RECONCILIATION, blocked["error_code"])
        self.assertTrue(blocked["reconcile_required"])
        submit.assert_not_called()
        post.assert_not_called()

    def test_http_response_before_readback_crash_is_not_confirmed_or_retried(self):
        account_id, email, filename = self._seed_credential("response-crash")
        created = self._create_run(account_id, email, filename, "response-crash-run")
        service._register_worker()
        with (
            patch.object(
                service,
                "_request_refresh",
                return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600},
            ) as refresh,
            patch.object(service, "_persist_refreshed_credential", side_effect=SystemExit("synthetic crash")),
        ):
            with self.assertRaises(SystemExit):
                task_gateway._execute_operation_handler(
                    service.TASK_TYPE,
                    int(created["run"]["id"]),
                )

        run_id = int(created["run"]["id"])
        run = operation.get_run(run_id)
        self.assertEqual("settling", run["status"])
        intent = (run.get("data") or {}).get("remote_intent")
        self.assertIsInstance(intent, dict)
        detail = intent
        self.assertEqual("response_received", detail["receipt_state"])
        receipt = (run.get("data") or {}).get("remote_receipt")
        self.assertEqual("response_received", receipt["outcome"])
        self.assertFalse(receipt["detail"].get("terminal", False))
        self.assertNotEqual("confirmed", detail["receipt_state"])
        self.assertEqual(1, refresh.call_count)

        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )
        self.assertEqual(1, operation_runtime_store.recover_interrupted_runtime_runs())
        with patch.object(service, "enqueue_refresh") as enqueue:
            result = service.enqueue_due_credentials()

        self.assertEqual(0, result["started"])
        self.assertEqual(1, result["reconciled"])
        enqueue.assert_not_called()
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIn(service.REQUEST_UNKNOWN, row["oauth_refresh_error"])

    def test_readback_mismatch_keeps_receipt_unknown(self):
        account_id, email, filename = self._seed_credential("readback-mismatch")
        created = self._create_run(account_id, email, filename, "readback-mismatch-run")
        service._register_worker()
        original_read = service.db.read_codex_credential
        reads = 0

        def read_with_stale_value(name):
            nonlocal reads
            reads += 1
            value = original_read(name)
            if reads == 2:
                stale = json.loads(value[0])
                stale["access_token"] = "old-access"
                return json.dumps(stale), value[1]
            return value

        with (
            patch.object(
                service,
                "_request_refresh",
                return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600},
            ),
            patch.object(service.db, "read_codex_credential", side_effect=read_with_stale_value),
        ):
            returned = task_gateway._execute_operation_handler(
                service.TASK_TYPE,
                int(created["run"]["id"]),
            )

        self.assertEqual("request_unknown", returned["status"])
        self.assertGreaterEqual(reads, 2)
        run = operation.get_run(int(created["run"]["id"]))
        intent = (run.get("data") or {}).get("remote_intent")
        self.assertEqual("unknown", intent["receipt_state"])
        receipt = (run.get("data") or {}).get("remote_receipt")
        self.assertEqual("unknown", receipt["outcome"])
        self.assertFalse(receipt["detail"].get("readback_confirmed", False))

    def test_confirmed_receipt_before_terminal_finish_still_blocks_producer(self):
        account_id, email, filename = self._seed_credential("confirmed-crash")
        created = self._create_run(account_id, email, filename, "confirmed-crash-run")
        service._register_worker()
        updates = 0

        def crash_after_worker_success_projection(*args, **kwargs):
            nonlocal updates
            updates += 1
            if updates == 2:
                raise SystemExit("synthetic crash before gateway finish")

        with (
            patch.object(
                service,
                "_request_refresh",
                return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600},
            ) as refresh,
            patch.object(service, "_sync_sub2_if_needed", return_value={"status": "disabled"}),
            patch.object(service, "_update_account_state", side_effect=crash_after_worker_success_projection),
        ):
            with self.assertRaises(SystemExit):
                task_gateway._execute_operation_handler(
                    service.TASK_TYPE,
                    int(created["run"]["id"]),
                )

        run_id = int(created["run"]["id"])
        run = operation.get_run(run_id)
        self.assertEqual("settling", run["status"])
        data = run["data"]
        intent = data["remote_intent"]
        receipt = data["remote_receipt"]
        self.assertEqual("confirmed", intent["receipt_state"])
        self.assertEqual("confirmed", receipt["outcome"])
        self.assertTrue(receipt["detail"]["remote_result_confirmed"])
        self.assertTrue(receipt["detail"]["local_business_writeback_confirmed"])
        self.assertTrue(receipt["detail"]["local_readback_confirmed"])
        self.assertEqual(1, refresh.call_count)
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertEqual(service.REQUEST_PENDING, row["oauth_refresh_error"])

        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )
        self.assertEqual(1, operation_runtime_store.recover_interrupted_runtime_runs())
        recovered = operation.get_run(run_id)
        self.assertEqual("attention_required", recovered["status"])
        self.assertEqual("request_unknown", recovered["result_summary"]["outcome"])
        self.assertEqual("confirmed", recovered["result_summary"]["remote_intent_state"])

        with patch.object(service, "enqueue_refresh") as enqueue:
            result = service.enqueue_due_credentials()
        self.assertEqual(0, result["started"])
        self.assertEqual(1, result["reconciled"])
        enqueue.assert_not_called()

    def test_post_write_marker_restore_crash_uses_durable_producer_fence(self):
        account_id, email, filename = self._seed_credential("post-write-crash")
        created = self._create_run(account_id, email, filename, "post-write-crash-run")
        service._register_worker()
        original_mark = service.db.mark_codex_oauth_refresh
        calls = 0

        def crash_when_restoring_marker(name, *, error=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise SystemExit("synthetic crash after credential readback")
            return original_mark(name, error=error)

        with (
            patch.object(
                service,
                "_request_refresh",
                return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600},
            ) as refresh,
            patch.object(service, "_sync_sub2_if_needed", return_value={"status": "disabled"}),
            patch.object(service.db, "mark_codex_oauth_refresh", side_effect=crash_when_restoring_marker),
        ):
            with self.assertRaises(SystemExit):
                task_gateway._execute_operation_handler(
                    service.TASK_TYPE,
                    int(created["run"]["id"]),
                )

        run_id = int(created["run"]["id"])
        before_recovery = operation.get_run(run_id)
        self.assertEqual("settling", before_recovery["status"])
        self.assertEqual("response_received", before_recovery["data"]["remote_intent"]["receipt_state"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIsNone(row["oauth_refresh_error"])
        self.assertEqual(1, refresh.call_count)

        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )
        self.assertEqual(1, operation_runtime_store.recover_interrupted_runtime_runs())
        with patch.object(service, "enqueue_refresh") as enqueue:
            result = service.enqueue_due_credentials()

        self.assertEqual(0, result["started"])
        self.assertEqual(0, result["reconciled"])
        enqueue.assert_not_called()

    def test_legacy_adapter_keeps_fence_and_marks_unknown_on_writeback_failure(self):
        account_id, email, filename = self._seed_credential("writeback")
        created = self._create_run(account_id, email, filename, "writeback-run")
        with (
            patch.object(service, "_request_refresh", return_value={"access_token": "new-access", "expires_in": 3600}) as refresh,
            patch.object(service.db, "write_codex_credential", side_effect=RuntimeError("synthetic write failure")),
        ):
            result = service._execute_legacy_run(int(created["run"]["id"]))

        self.assertEqual(service.REQUEST_UNKNOWN, result["status"])
        self.assertEqual(1, refresh.call_count)
        run = operation.get_run(int(created["run"]["id"]))
        self.assertEqual("attention_required", run["status"])
        self.assertTrue(run["result_summary"]["needs_reconciliation"])
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIn(service.REQUEST_UNKNOWN, row["oauth_refresh_error"])
        self.assertFalse(service.enqueue_refresh(filename)["accepted"])

    def test_global_recovery_promotes_pending_marker_before_producer_scan(self):
        account_id, email, filename = self._seed_credential("crash")
        created = self._create_run(account_id, email, filename, "crash-run")
        run_id = int(created["run"]["id"])
        self.assertIsNotNone(operation.claim_run(run_id, execution_id="crashed-worker", worker_pid=404))
        db.mark_codex_oauth_refresh(filename, error=service.REQUEST_PENDING)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {operation._table('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )

        self.assertEqual(1, operation_runtime_store.recover_interrupted_runtime_runs())
        self.assertEqual("interrupted", operation.get_run(run_id)["status"])
        with patch.object(service, "enqueue_refresh") as enqueue:
            result = service.enqueue_due_credentials()

        self.assertEqual(0, result["started"])
        self.assertEqual(1, result["reconciled"])
        enqueue.assert_not_called()
        row = record_store.get_row_by(record_store.CODEX_CREDENTIALS, "filename", filename)
        self.assertIn(service.REQUEST_UNKNOWN, row["oauth_refresh_error"])

    def test_success_without_rotated_refresh_token_retains_old_value(self):
        account_id, email, filename = self._seed_credential("retained")
        created = self._create_run(account_id, email, filename, "retained-run")
        with patch.object(service, "_request_refresh", return_value={"access_token": "new-access", "expires_in": 3600}):
            result = service._execute_legacy_run(int(created["run"]["id"]))

        self.assertEqual("success", result["status"])
        text, _ = db.read_codex_credential(filename)
        self.assertEqual("old-refresh", json.loads(text)["refresh_token"])
        self.assertFalse(result["credential_rotated"])


if __name__ == "__main__":
    import unittest

    unittest.main()
