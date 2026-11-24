"""批量终止只受理一条持久命令，worker 对冻结 Run 独立安全收口。"""
from __future__ import annotations

import importlib
import logging
import uuid
from unittest.mock import Mock, patch

from flask import Flask
from psycopg import Cursor, OperationalError

from core.operations import action_service, bulk_mutation_service, task_gateway
from core.storage import records
from core.storage.operations import bulk_mutations as commands, bulk_submission, common, legacy_task_store, runtime, schema
from tests.support_pg import PostgresTestCase
from webui.routes.operations import create_operations_blueprint
from webui.runtime import WebUIContext


class BulkTerminateCommandTests(PostgresTestCase):
    def setUp(self):
        records.init()
        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        schema.init_operation_schema()
        commands.init()
        self.enterContext(patch.object(task_gateway, "notify_dispatch"))
        task_gateway.register_operation_actions(
            "fixture_terminate", terminate_handler=task_gateway.default_operation_terminate,
            source_systems=("native_operations",),
        )
        app = Flask(__name__)
        app.register_blueprint(create_operations_blueprint(WebUIContext(app, logging.getLogger(__name__))))
        self.client = app.test_client()

    @staticmethod
    def service():
        return importlib.import_module("core.operations.bulk_terminate_command")

    def target(self, *, remote_unknown=False, parent_task_id=None, task_type="fixture_terminate"):
        account_id = records.insert_row(records.ACCOUNTS, {"email": f"target-{uuid.uuid4().hex}@example.test"})
        task = runtime.create_runtime_task(
            task_type=task_type, account_id=account_id, email="fixture@example.test",
            parent_task_id=parent_task_id,
            data={"remote_intent": {"kind": "remote_write", "receipt_state": "started"}} if remote_unknown else {},
        )
        run = runtime.claim_run(task["run"]["id"], execution_id=f"target-{task['id']}", worker_pid=123)
        self.assertEqual("running", run["status"])
        return task

    def submit(self, ids, key="terminate-request"):
        response = self.client.post(
            "/api/operations/bulk", json={"action": "terminate", "task_ids": ids},
            headers={"Idempotency-Key": key},
        )
        self.assertEqual(202, response.status_code)
        return response.get_json()

    def claim(self, accepted, name="bulk-worker"):
        service = self.service()
        service.register_worker()
        run = runtime.claim_run(int(accepted["run_id"]), execution_id=name, worker_pid=456)
        return task_gateway.OperationHandlerContext(run, execution_id=name)

    def test_http_accepts_once_without_performing_any_target_termination(self):
        target = self.target()
        with patch.object(action_service, "accept_bulk_operation_action", side_effect=AssertionError("HTTP executed target")):
            response = self.client.post(
                "/api/operations/bulk", json={"action": "terminate", "task_ids": [target["id"]]},
                headers={"Idempotency-Key": "accept-only"},
            )
        self.assertEqual(202, response.status_code)
        accepted = response.get_json()
        self.assertTrue(accepted["accepted"])
        self.assertIsInstance(accepted["command_id"], str)
        self.assertNotIn("accepted_count", accepted)
        self.assertEqual("running", runtime.get_run(target["run"]["id"])["status"])
        replay = self.submit([target["id"]], "accept-only")
        self.assertEqual(accepted["command_id"], replay["command_id"])
        self.assertEqual(accepted["run_id"], replay["run_id"])

    def test_worker_keeps_remote_unknown_and_closes_each_target_independently(self):
        first, second = self.target(remote_unknown=True), self.target()
        accepted = self.submit([first["id"], second["id"]])
        context = self.claim(accepted)
        result = self.service().handle(context)
        self.assertEqual(2, result.summary["updated_count"])
        self.assertEqual("attention_required", runtime.get_run(first["run"]["id"])["status"])
        self.assertEqual("stopped", runtime.get_run(second["run"]["id"])["status"])
        receipt = commands.get_command_result(int(accepted["command_id"]))
        self.assertEqual(["attention_required", "stopped"], [item["data"]["state"] for item in receipt["items"]])
        self.assertEqual(2, len(receipt["items"]))
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('account_operation_leases')} WHERE run_id=ANY(%s)",
                        ([first["run"]["id"], second["run"]["id"]],))
            self.assertEqual(0, cur.fetchone()["n"])

    def test_completed_action_before_receipt_crash_replays_original_run_without_new_finish(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        with patch.object(commands, "execute_chunk", side_effect=KeyboardInterrupt("after target commit")):
            with self.assertRaises(KeyboardInterrupt):
                self.service().handle(context)
        self.assertEqual("stopped", runtime.get_run(target["run"]["id"])["status"])
        self.assertEqual([], commands.get_command_result(int(accepted["command_id"]))["items"])
        with patch.object(runtime, "terminate_run", side_effect=AssertionError("already terminated")):
            result = self.service().handle(context)
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual(1, len(commands.get_command_result(int(accepted["command_id"]))["items"]))

    def test_receipt_connection_failure_defers_and_preserves_finished_target_for_reentry(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        with patch.object(commands, "execute_chunk", side_effect=OperationalError("synthetic receipt failure")):
            result = self.service().handle(context)
        self.assertEqual("deferred", result["status"])
        self.assertEqual("stopped", runtime.get_run(target["run"]["id"])["status"])
        self.assertEqual([], commands.get_command_result(int(accepted["command_id"]))["items"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET next_attempt_at=NULL WHERE id=%s",
                        (context.run_id,))
        result = self.service().handle(self.claim(accepted, "replacement"))
        self.assertEqual(1, result.summary["updated_count"])

    def test_registered_terminate_storage_failure_remains_retryable(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        task_gateway.register_operation_actions(
            "fixture_terminate", terminate_handler=Mock(side_effect=OperationalError("temporary storage failure")),
        )
        result = self.service().handle(context)
        self.assertEqual("deferred", result["status"])
        self.assertEqual([], commands.get_command_result(int(accepted["command_id"]))["items"])
        self.assertEqual("running", runtime.get_run(target["run"]["id"])["status"])

    def test_codex_reentry_completes_token_and_account_projection_after_run_commit(self):
        from core.codex import operation_service as codex
        codex.register_actions()
        target = self.target(task_type="codex_retry")
        records.patch_row(records.ACCOUNTS, target["account_id"], changes={
            "codex_execution_status": "running", "codex_active_run_id": target["run"]["id"],
        })
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        terminate = runtime.terminate_run
        token = Mock()
        codex._LOCAL_TOKENS[target["run"]["id"]] = token
        self.addCleanup(codex._LOCAL_TOKENS.pop, target["run"]["id"], None)

        def finish_then_crash(*args, **kwargs):
            terminate(*args, **kwargs)
            raise KeyboardInterrupt("committed run before Codex projection")

        with patch.object(runtime, "terminate_run", side_effect=finish_then_crash):
            with self.assertRaises(KeyboardInterrupt):
                self.service().handle(context)
        self.assertEqual("stopped", runtime.get_run(target["run"]["id"])["status"])
        result = self.service().handle(context)
        self.assertEqual(1, result.summary["updated_count"])
        account = records.get_row(records.ACCOUNTS, target["account_id"])
        self.assertEqual("empty", account["codex_execution_status"])
        self.assertIsNone(account["codex_active_run_id"])
        token.request_local.assert_called_once()

    def test_codex_projection_after_finish_cannot_clear_a_later_run(self):
        from core.codex import operation_service as codex
        from core.storage.operations import bulk_terminate
        codex.register_actions()
        target = self.target(task_type="codex_retry")
        accepted = self.submit([target["id"]])
        project = bulk_terminate.project_codex
        later = []

        def race_after_finish(run):
            retry = runtime.retry_runtime_task(target["id"])
            runtime.claim_run(retry["id"], execution_id="new-codex-run", worker_pid=321)
            later.append(retry["id"])
            records.patch_row(records.ACCOUNTS, target["account_id"], changes={
                "codex_active_run_id": retry["id"], "codex_execution_status": "running",
            })
            project(run)

        with patch.object(bulk_terminate, "project_codex", side_effect=race_after_finish):
            result = self.service().handle(self.claim(accepted))
        self.assertEqual(1, result.summary["updated_count"])
        account = records.get_row(records.ACCOUNTS, target["account_id"])
        self.assertEqual(later[0], account["codex_active_run_id"])
        self.assertEqual("running", account["codex_execution_status"])
        self.assertEqual("running", runtime.get_run(later[0])["status"])

    def test_codex_unknown_termination_projects_nullable_legacy_state(self):
        from core.codex import operation_service as codex
        codex.register_actions()
        target = self.target(task_type="codex_retry", remote_unknown=True)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
                SET codex_status=NULL,codex_credential_state=NULL WHERE id=%s""", (target["account_id"],))
        accepted = self.submit([target["id"]])
        result = self.service().handle(self.claim(accepted))
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual("attention_required", records.get_row(records.ACCOUNTS, target["account_id"])["codex_status"])

    def test_inspection_parent_freezes_all_children_without_expanding_to_later_runs(self):
        from core.accounts.inspection import service as inspection
        from core.storage.operations import bulk_terminate
        inspection.register_actions()
        parent = runtime.create_runtime_task(
            task_type="account_inspection_batch", account_id=None, email="", resource_family="inspection_coordinator")
        runtime.claim_run(parent["run"]["id"], execution_id="parent-worker", worker_pid=123)
        with common._connect() as conn, conn.cursor() as cur:
            children = bulk_submission.create_specs([
                {"task_type": "fixture_terminate", "account_id": None, "email": "",
                 "source_id": f"frozen-child-{index}", "resource_family": "inspection_snapshot"}
                for index in range(125)
            ], conn=conn)
            cur.execute(f"""UPDATE {common._table('operation_tasks')} SET parent_task_id=%s,root_task_id=%s
                WHERE id=ANY(%s)""", (parent["id"], parent["id"], [row["task_id"] for row in children]))
        accepted = self.submit([parent["id"]])
        frozen = bulk_terminate.targets(int(accepted["command_id"]))
        self.assertEqual(125, len(frozen[0]["children"]))
        later = runtime.create_runtime_task(
            task_type="fixture_terminate", account_id=None, email="", parent_task_id=parent["id"])
        inserts = []
        execute = Cursor.execute

        def capture(cursor, query, *args, **kwargs):
            if "INSERT INTO" in str(query) and '"operation_events"' in str(query):
                inserts.append(str(query))
            return execute(cursor, query, *args, **kwargs)

        context = self.claim(accepted)
        with patch.object(Cursor, "execute", capture):
            result = self.service().handle(context)
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual(1, len(inserts), "巡检子Run应集合取消并一次写事件")
        self.assertEqual("queued", runtime.get_run(later["run"]["id"])["status"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_runs')} WHERE id=ANY(%s) AND status='cancelled'",
                        ([row["run_id"] for row in children],))
            self.assertEqual(125, cur.fetchone()["n"])

    def test_inspection_queued_child_claim_race_defers_then_cancels_fixed_run(self):
        from core.accounts.inspection import service as inspection
        from core.storage.operations import cancellation
        inspection.register_actions()
        parent = runtime.create_runtime_task(
            task_type="account_inspection_batch", account_id=None, email="", resource_family="inspection_coordinator")
        runtime.claim_run(parent["run"]["id"], execution_id="parent-worker", worker_pid=123)
        child = runtime.create_runtime_task(
            task_type="fixture_terminate", account_id=None, email="", parent_task_id=parent["id"])
        accepted = self.submit([parent["id"]])
        context = self.claim(accepted)
        cancel = cancellation.cancel_runs_many

        def race(conn, requests):
            runtime.claim_run(child["run"]["id"], execution_id="raced-child", worker_pid=123)
            return cancel(conn, requests)

        with patch.object(cancellation, "cancel_runs_many", side_effect=race):
            result = self.service().handle(context)
        self.assertEqual("deferred", result["status"])
        self.assertEqual("running", runtime.get_run(child["run"]["id"])["status"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET next_attempt_at=NULL WHERE id=%s",
                        (context.run_id,))
        result = self.service().handle(self.claim(accepted, "replacement"))
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual("cancelling", runtime.get_run(child["run"]["id"])["status"])

    def test_later_retry_run_is_never_terminated_by_an_older_command(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        runtime.finish_run(target["run"]["id"], status="success")
        retry = runtime.retry_runtime_task(target["id"])
        runtime.claim_run(retry["id"], execution_id="later-target", worker_pid=999)
        result = self.service().handle(self.claim(accepted))
        self.assertEqual(1, result.summary["skipped_count"])
        self.assertEqual("running", runtime.get_run(retry["id"])["status"])
        item = commands.get_command_result(int(accepted["command_id"]))["items"][0]
        self.assertEqual("target_run_changed", item["reason_code"])

    def test_http_selection_preserves_queued_skip_and_missing_task_receipts(self):
        running = self.target()
        queued = runtime.create_runtime_task(task_type="fixture_terminate", account_id=None, email="")
        accepted = self.submit([queued["id"], running["id"], 999999])
        result = self.service().handle(self.claim(accepted))
        self.assertEqual((1, 2), (result.summary["updated_count"], result.summary["skipped_count"]))
        items = commands.get_command_result(int(accepted["command_id"]))["items"]
        self.assertEqual(["target_not_running", None, "task_not_found"], [item["reason_code"] for item in items])
        self.assertEqual("queued", runtime.get_run(queued["run"]["id"])["status"])

    def test_inspection_terminal_parent_replays_children_after_receipt_crash(self):
        from core.accounts.inspection import service as inspection
        inspection.register_actions()
        parent = runtime.create_runtime_task(
            task_type="account_inspection_batch", account_id=None, email="", resource_family="inspection_coordinator")
        runtime.claim_run(parent["run"]["id"], execution_id="parent-worker", worker_pid=123)
        child = runtime.create_runtime_task(
            task_type="fixture_terminate", account_id=None, email="", parent_task_id=parent["id"])
        accepted = self.submit([parent["id"]])
        context = self.claim(accepted)
        with patch.object(commands, "execute_chunk", side_effect=KeyboardInterrupt("after child cancellation")):
            with self.assertRaises(KeyboardInterrupt):
                self.service().handle(context)
        runtime.finish_run(parent["run"]["id"], status="cancelled")
        result = self.service().handle(context)
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual("cancelled", runtime.get_run(child["run"]["id"])["status"])

    def test_command_recovery_keeps_original_target_run_snapshot(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        runtime.finish_run(context.run_id, status="interrupted", result_summary={"recovery_reason": "worker_restart"})
        self.assertEqual(1, bulk_mutation_service.resume_interrupted_commands())
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT last_run_id FROM {common._table('operation_tasks')} WHERE id=%s",
                        (int(accepted["task_id"]),))
            next_run = cur.fetchone()["last_run_id"]
        self.assertNotEqual(context.run_id, next_run)
        result = self.service().handle(self.claim({**accepted, "run_id": next_run}, "replacement"))
        self.assertEqual(1, result.summary["updated_count"])
        self.assertEqual("stopped", runtime.get_run(target["run"]["id"])["status"])

    def test_lost_command_owner_cannot_finish_any_target(self):
        target = self.target()
        accepted = self.submit([target["id"]])
        context = self.claim(accepted)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common._table('operation_runs')} SET execution_id='replacement' WHERE id=%s",
                        (context.run_id,))
        with self.assertRaises((PermissionError, task_gateway.OperationLeaseLost)):
            self.service().handle(context)
        self.assertEqual("running", runtime.get_run(target["run"]["id"])["status"])
