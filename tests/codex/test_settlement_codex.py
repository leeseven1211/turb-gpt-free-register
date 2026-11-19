"""Offline native Codex adapter settlement boundaries; no PostgreSQL fixtures."""
from contextlib import ExitStack, contextmanager, nullcontext
import json
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.codex import token_refresh_service as refresh
from core.codex import operation_service as oauth
from core.operations.settlement_contracts import (
    OperationSettlementConflict, OperationSettlementFenced, OperationSettlementPending,
)


class RefreshContext:
    run = {"id": 73, "task_id": 72, "data": {"credential_filename": "synthetic.json"}}
    run_id = 73
    task_id = 72
    account_id = 4
    email = "synthetic@example.test"
    config_snapshot = {}
    execution_id = "synthetic-execution"

    def __init__(self, error=None):
        self.error = error
        self.scope_kind = None
        self.held = False
        self.finish_held = False
        self.obligations = []
        self.result = None

    @contextmanager
    def lease(self, **kwargs):
        self.scope_kind = kwargs.get("scope_kind")
        self.held = True
        try:
            yield SimpleNamespace(heartbeat=lambda: True, token="synthetic-lease")
        finally:
            if self.scope_kind != "final":
                self.held = False

    def add_settlement_obligation(self, kind, *, resource_identity, payload, blocks_permit=True):
        self.obligations.append({"kind": kind, "resource_identity": resource_identity, "payload": payload})

    def finish(self, result):
        self.finish_held = self.held
        self.result = result
        if self.error:
            raise self.error
        return {"status": "success"}

    def remote_request_started(self, **kwargs):
        return {}


class CodexSettlementTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("core.storage.postgres.connect", side_effect=AssertionError("offline")))
        self.stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("offline")))

    def refresh_dependencies(self):
        self.stack.enter_context(patch.object(refresh, "operation_log_context", return_value=nullcontext()))
        self.account_writes = self.stack.enter_context(patch.object(refresh, "_update_account_state"))
        self.unknown = self.stack.enter_context(patch.object(refresh, "_mark_unknown"))
        self.failure = self.stack.enter_context(patch.object(refresh, "_mark_refresh_failure"))
        self.clear = self.stack.enter_context(patch.object(refresh, "_clear_refresh_marker_after_terminal"))
        self.stack.enter_context(patch.object(refresh.db, "get_codex_account", return_value={
            "filename": "synthetic.json", "mtime": "version-1", "oauth_refresh_error": "request_pending",
            "oauth_refresh_attempted_at": "attempt-1",
        }))

        def grant(_filename, **kwargs):
            kwargs["on_remote_dispatch"]("synthetic-request")
            return {"filename": "synthetic.json", "status": "success", "credential_persisted": True,
                    "_settlement_marker": {"filename": "synthetic.json", "credential_id": 9,
                        "run_id": 73, "marker_version": "synthetic-marker",
                        "expected_record_version": "104", "expected_mtime": "version-1"}}

        self.perform = self.stack.enter_context(patch.object(refresh, "_perform_refresh", side_effect=grant))

    def test_finish_control_error_does_not_rewrite_refresh_outcome(self):
        self.refresh_dependencies()
        for error_type in (OperationSettlementPending, OperationSettlementConflict, OperationSettlementFenced):
            with self.subTest(error=error_type.__name__):
                context = RefreshContext(error_type("synthetic"))
                self.account_writes.reset_mock()
                with self.assertRaises(error_type):
                    refresh._handle_operation_context(context)
                self.assertEqual(["running", "empty"], [
                    call.kwargs["execution_status"] for call in self.account_writes.call_args_list
                ])
                self.unknown.assert_not_called()
                self.failure.assert_not_called()
                self.clear.assert_not_called()
                self.assertEqual("success", context.result.status)

    def test_refresh_final_fence_survives_scope_exit_and_marker_is_declared_before_finish(self):
        self.refresh_dependencies()
        context = RefreshContext()
        refresh._handle_operation_context(context)
        self.assertTrue(context.finish_held, "final account fence must survive lexical scope exit")
        self.assertEqual(1, len(context.obligations))
        self.assertEqual("version-1", context.obligations[0]["payload"]["expected_mtime"])
        self.assertEqual(73, context.obligations[0]["payload"]["run_id"])
        self.clear.assert_not_called()

    def oauth_dependencies(self, *, route_release_error=None):
        run = {
            "id": 83, "task_id": 82, "account_id": 4, "email_snapshot": "synthetic@example.test",
            "resource_family": "openai_interactive",
            "data": {"config_snapshot": {"oauth_driver": "protocol"}},
        }
        execution = SimpleNamespace(execution_id="synthetic-execution", claimed_run=run)
        self.stack.enter_context(patch.object(oauth.task_gateway, "_operation", return_value=oauth.operation_task_store))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "get_run", return_value=run))
        self.stack.enter_context(patch.object(oauth, "_deployment_unavailable", return_value=None))
        self.stack.enter_context(patch.object(oauth, "_feature_ready", return_value=(True, "")))
        self.stack.enter_context(patch.object(oauth.task_run_log, "TaskRunLogHandler", return_value=logging.NullHandler()))
        self.stack.enter_context(patch("core.operations.concurrency.set_execution_state"))
        self.stack.enter_context(patch("core.operations.concurrency.current_execution", return_value=execution))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "is_run_cancel_requested", return_value=False))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "acquire_account_lease", return_value="synthetic-lease"))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "heartbeat_run", return_value=True))
        self.stack.enter_context(patch.object(oauth.task_gateway.OperationLease, "_heartbeat_loop"))
        self.stack.enter_context(patch.object(oauth.task_gateway.OperationHandlerContext, "register_cleanup"))
        self.lease_release = self.stack.enter_context(patch.object(oauth.operation_task_store, "release_account_lease", return_value=True))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "append_runtime_event", return_value={}))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "record_remote_intent", return_value={}))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "record_remote_receipt", return_value={}))
        self.stack.enter_context(patch.object(oauth.operation_task_store, "register_resource", return_value={
            "id": 11, "resource_uuid": "synthetic-resource",
        }))
        self.resource_release = self.stack.enter_context(patch.object(oauth.operation_task_store, "release_resource", return_value=True))
        self.legacy_finish = self.stack.enter_context(patch.object(oauth.operation_task_store, "finish_run", return_value={"status": "success"}))
        self.account_writes = self.stack.enter_context(patch.object(oauth.db, "update_account_codex_operation_state", return_value=True))
        self.stack.enter_context(patch.object(oauth.db, "get_account_by_email", return_value={"codex_credential_state": "valid"}))
        route = Mock(provider="synthetic", mode="direct", region="ZZ", proxy_url=None)
        route.public_dict.return_value = {}
        route.release.side_effect = route_release_error
        self.stack.enter_context(patch("core.proxy.account_routes.acquire_account_proxy", return_value=route))
        self.oauth_grant = self.stack.enter_context(patch("core.codex.oauth.run_codex_oauth", return_value={
            "ok": True, "status": "success", "credential_confirmed": True,
            "remote_response_received": True, "message": "synthetic confirmed",
        }))
        return execution, route

    def test_old_oauth_finish_pending_never_rewrites_account_or_repeats_oauth(self):
        execution, _ = self.oauth_dependencies()
        with patch.object(oauth.task_gateway.OperationHandlerContext, "finish", side_effect=OperationSettlementPending("synthetic")):
            with self.assertRaises(OperationSettlementPending):
                oauth._execute_claimed_run(83, execution)
        self.assertEqual(1, self.oauth_grant.call_count)
        self.assertEqual(["running", "empty"], [
            call.kwargs["execution_status"] for call in self.account_writes.call_args_list
        ])
        self.legacy_finish.assert_not_called()
        self.lease_release.assert_not_called()

    def test_old_oauth_physical_route_release_failure_never_marks_resource_released(self):
        execution, _ = self.oauth_dependencies(route_release_error=RuntimeError("synthetic release unavailable"))
        with self.assertRaises((RuntimeError, OperationSettlementPending)):
            oauth._execute_claimed_run(83, execution)
        self.assertFalse(any(
            call.kwargs.get("state") == "released" for call in self.resource_release.call_args_list
        ), "a failed physical release must retain resource cleanup responsibility")

    def marker_repository(self, row):
        from core.storage import postgres, records
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.rowcount = 1
        write = Mock()
        state = dict(row)
        state.setdefault("filename", "synthetic.json")

        def execute(sql, params):
            if sql.startswith("UPDATE "):
                write(sql, params)
                if str(state["__record_version"]) == str(params[-1]):
                    state.update(json.loads(params[0]))
                    state["__record_version"] = str(int(state["__record_version"]) + 1)
                else:
                    cursor.rowcount = 0

        def fetchone():
            raw = {key: value for key, value in state.items()
                   if key in records.CODEX_CREDENTIALS.promoted or key in {"id", "__record_version"}}
            raw["data"] = {key: value for key, value in state.items()
                           if key not in records.CODEX_CREDENTIALS.promoted and key not in {"id", "__record_version"}}
            return raw

        cursor.execute.side_effect = execute
        cursor.fetchone.side_effect = fetchone
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value = cursor
        self.stack.enter_context(patch.object(postgres, "connect", return_value=connection))
        self.stack.enter_context(patch.object(records, "init", side_effect=AssertionError("cleanup attempted DDL")))
        return write

    def test_marker_cleanup_clears_exact_original_generation_and_rechecks_by_xmin(self):
        payload = {"filename": "synthetic.json", "credential_id": 9, "run_id": 73,
                   "marker_version": "original", "expected_record_version": "104", "expected_mtime": "v1"}
        write = self.marker_repository({
            "id": 9, "__record_version": "104", "mtime": "v1", "oauth_refresh_error": "request_pending",
            "oauth_refresh_settlement_run_id": 73, "oauth_refresh_settlement_version": "original",
        })
        self.assertIs(True, refresh.apply_settlement_marker(payload))
        self.assertEqual("104", write.call_args.args[1][-1])
        self.assertIsNone(json.loads(write.call_args.args[1][0])["oauth_refresh_error"])

    def test_marker_cleanup_never_clears_newer_run_even_at_same_filename(self):
        payload = {"filename": "synthetic.json", "credential_id": 9, "run_id": 73,
                   "marker_version": "original", "expected_record_version": "104", "expected_mtime": "v1"}
        write = self.marker_repository({
            "id": 9, "__record_version": "105", "mtime": "v2", "oauth_refresh_error": "request_pending",
            "oauth_refresh_settlement_run_id": 74, "oauth_refresh_settlement_version": "newer",
        })
        self.assertEqual("superseded", refresh.apply_settlement_marker(payload)["state"])
        write.assert_not_called()

    def test_marker_cleanup_unrelated_version_change_keeps_original_pending(self):
        payload = {"filename": "synthetic.json", "credential_id": 9, "run_id": 73,
                   "marker_version": "original", "expected_record_version": "104", "expected_mtime": "v1"}
        write = self.marker_repository({
            "id": 9, "__record_version": "105", "mtime": "v1", "oauth_refresh_error": "request_pending",
            "oauth_refresh_settlement_run_id": 73, "oauth_refresh_settlement_version": "original",
        })
        with self.assertRaises(OperationSettlementConflict):
            refresh.apply_settlement_marker(payload)
        write.assert_not_called()

    def test_marker_cleanup_committed_ack_loss_readback_does_not_clear_again(self):
        payload = {"filename": "synthetic.json", "credential_id": 9, "run_id": 73,
                   "marker_version": "original", "expected_record_version": "104", "expected_mtime": "v1"}
        write = self.marker_repository({
            "id": 9, "__record_version": "105", "mtime": "v1", "oauth_refresh_error": None,
            "oauth_refresh_settlement_state": "cleared",
            "oauth_refresh_settlement_run_id": 73, "oauth_refresh_settlement_version": "original",
        })
        self.assertIs(True, refresh.apply_settlement_marker(payload))
        write.assert_not_called()

    def test_route_cleanup_does_not_repeat_physical_release_after_metadata_ack_loss(self):
        route = Mock()
        cleanup = oauth._RouteCleanup(route, 83, 11)
        with patch.object(oauth.operation_task_store, "release_resource", side_effect=[RuntimeError("synthetic ACK"), True]):
            with self.assertRaises(RuntimeError):
                cleanup.release()
            self.assertFalse(cleanup.released)
            self.assertTrue(cleanup.release())
        self.assertEqual(1, route.release.call_count)

    def test_old_oauth_actual_receipt_result_controls_return_value(self):
        execution, _ = self.oauth_dependencies()
        actual_summary = {"outcome": "request_unknown", "reconcile_required": True,
                          "receipt_authority": "synthetic-actual-receipt"}
        actual_message = "synthetic remote reconciliation from actual receipt"
        actual_error = "synthetic actual receipt error"
        captured = []

        def committed_transition(context, *, kind, payload):
            captured.append((context, kind, payload))
            return {"actual_result": {"status": "attention_required",
                    "result_summary": actual_summary, "message": actual_message,
                    "error_message": actual_error}}

        with patch.object(oauth.task_gateway.OperationHandlerContext, "_submit_transition",
                          new=committed_transition):
            result = oauth._execute_claimed_run(83, execution)
        self.assertEqual(1, len(captured))
        context, kind, requested = captured[0]
        self.assertEqual("terminal", kind)
        self.assertEqual("success", requested["status"])
        self.assertEqual("synthetic confirmed", requested["message"])
        self.assertIsNone(requested["error"])
        self.assertNotEqual(actual_summary, requested["result_summary"])
        self.assertTrue(context.finished)
        self.assertEqual("request_unknown", context.last_result.status)
        self.assertEqual(actual_summary, dict(context.last_result.summary))
        self.assertEqual(actual_message, context.last_result.message)
        self.assertEqual(actual_error, context.last_result.error)
        self.assertEqual("attention_required", result["status"])
        self.assertFalse(result["ok"])
        self.assertEqual(actual_message, result["message"])
        self.assertEqual(actual_error, result["error"])

    def test_old_oauth_resource_registration_failure_still_cleans_exact_live_route(self):
        execution, route = self.oauth_dependencies()
        with patch.object(oauth.operation_task_store, "register_resource", side_effect=RuntimeError("synthetic unavailable")):
            oauth._execute_claimed_run(83, execution)
        route.release.assert_called_once()
        self.resource_release.assert_not_called()

    def test_route_cleanup_early_provider_released_flag_cannot_replace_persistent_confirmation(self):
        from core.storage import postgres, records
        route = Mock()
        route.lease = SimpleNamespace(lease_id="original-proxy", state="released",
                                      metadata={"persistent_lease": True})
        cleanup = oauth._RouteCleanup(route, 83, 11)
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.side_effect = [
            {"lease_id": "original-proxy", "state": "leased"},
            {"lease_id": "original-proxy", "state": "released"},
        ]
        connection = Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
        connection.__enter__.return_value = connection
        connection.cursor.return_value = cursor
        with (
            patch.object(postgres, "connect", return_value=connection),
            patch.object(records, "init", side_effect=AssertionError("cleanup attempted DDL")),
            patch.object(oauth.operation_task_store, "release_resource", return_value=True) as mark,
        ):
            with self.assertRaises(OperationSettlementPending):
                cleanup.release()
            self.assertFalse(cleanup.released)
            mark.assert_not_called()
            self.assertTrue(cleanup.release())
            self.assertEqual(["original-proxy", "original-proxy"], [
                call.args[1][0] for call in cursor.execute.call_args_list
            ])
        self.assertEqual(1, route.release.call_count)

    def test_marker_cleanup_captured_domain_never_reinitializes_records_after_cache_drift(self):
        from core.storage import postgres, records
        from core.storage.operations.common import settlement_scope
        from core.operations.settlement_contracts import SettlementDomain

        payload = {"filename": "synthetic.json", "credential_id": 9, "run_id": 73,
                   "marker_version": "original", "expected_record_version": "104", "expected_mtime": "v1"}
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = {
            "id": 9, "filename": "synthetic.json", "__record_version": "104", "mtime": "v1",
            "data": {"oauth_refresh_error": "request_pending", "oauth_refresh_settlement_run_id": 73,
                     "oauth_refresh_settlement_version": "original"},
        }
        cursor.rowcount = 1
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value = cursor
        domain = SettlementDomain("synthetic-offline", "operation_origin", "credential_origin", "synthetic-domain")
        with (
            patch.object(postgres, "connect", return_value=connection) as connect,
            patch.object(records, "_READY_KEY", "different-database-schema"),
            patch.object(records, "init", side_effect=AssertionError("cleanup attempted DDL")) as init,
            settlement_scope(domain, deadline=123.0),
        ):
            self.assertIs(True, refresh.apply_settlement_marker(payload, deadline=123.0))
        init.assert_not_called()
        connect.assert_called_once()
        self.assertEqual(123.0, connect.call_args.kwargs["deadline"])
        sql = [str(call.args[0]) for call in cursor.execute.call_args_list]
        self.assertTrue(any('"credential_origin"."codex_credentials"' in statement for statement in sql))
        self.assertFalse(any("CREATE" in statement.upper() for statement in sql))

    def test_marker_capture_uses_existing_table_after_cache_drift_and_keeps_secrets_out_of_payload(self):
        write = self.marker_repository({
            "id": 9, "__record_version": "104", "mtime": "v1",
            "oauth_refresh_error": "request_pending",
            "content": {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"},
        })
        with patch.object(refresh.operation_runtime_store, "fence_execution", return_value={}) as fence:
            payload = refresh._capture_settlement_marker(
                "synthetic.json", 73,
                {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"},
                execution_id="synthetic-execution", lease_token="synthetic-lease",
            )
        fence.assert_called_once()
        self.assertEqual("105", payload["expected_record_version"])
        self.assertEqual("104", write.call_args.args[1][-1])
        self.assertEqual(73, payload["run_id"])
        self.assertNotIn("synthetic-access", json.dumps(payload))
        self.assertNotIn("synthetic-refresh", json.dumps(payload))

    def test_route_cleanup_persistent_readback_never_initializes_records(self):
        from core.storage import postgres, records
        from core.operations.settlement_contracts import SettlementDomain

        route = Mock()
        route.lease = SimpleNamespace(lease_id="original-proxy", state="released",
                                      metadata={"persistent_lease": True})
        domain = SettlementDomain("synthetic-offline", "operation_origin", "credential_origin", "synthetic-domain")
        cleanup = oauth._RouteCleanup(route, 83, None, domain=domain)
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchone.return_value = {"lease_id": "original-proxy", "state": "released"}
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.cursor.return_value = cursor
        with (
            patch.object(postgres, "connect", return_value=connection) as connect,
            patch.object(records, "_READY_KEY", "different-database-schema"),
            patch.object(records, "init", side_effect=AssertionError("cleanup attempted DDL")) as init,
        ):
            self.assertTrue(cleanup.release(deadline=123.0))
        init.assert_not_called()
        self.assertEqual(123.0, connect.call_args.kwargs["deadline"])
        self.assertIn('"credential_origin"."proxy_leases"', cursor.execute.call_args.args[0])
        self.assertEqual(("original-proxy",), cursor.execute.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
