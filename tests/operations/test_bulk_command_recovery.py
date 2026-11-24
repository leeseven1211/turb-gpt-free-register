"""Bulk command recovery uses the durable gateway and the original receipts."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import account_task_store
from core.operations import bulk_mutation_worker as worker
from core.operations import reconciliation, task_gateway
from core.operations.contracts import BulkItemResult
from core.runtime import assembly, process
from core.runtime.bootstrap import RuntimeBootstrap
from core.storage.operations import bulk_mutations as commands
from core.storage.operations import store as operation_store
from tests.support_pg import PostgresTestCase
from tests.support_settlement import install_native_settlement_fixture


class BulkCommandRecoveryTests(PostgresTestCase):
    def setUp(self):
        schema_patch = patch.multiple(account_task_store, _SCHEMA=self.schema, _READY_KEY="")
        schema_patch.start()
        self.addCleanup(schema_patch.stop)
        account_task_store.init()
        commands.init()
        with operation_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""CREATE TABLE IF NOT EXISTS {operation_store._table('test_bulk_counters')}
                (id bigint PRIMARY KEY, value integer NOT NULL DEFAULT 0)""")

    def _increment(self, chunk, parameters, *, conn):
        with conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {operation_store._table('test_bulk_counters')} (id, value)
                SELECT id, 1 FROM unnest(%s::bigint[]) AS id
                ON CONFLICT (id) DO UPDATE SET value = test_bulk_counters.value + 1""", (list(chunk),))
        return [BulkItemResult(key, "updated") for key in chunk]

    def _submit(self, callback):
        worker.register_bulk_mutation_handler("test_bulk_recovery", callback, chunk_size=1)
        return worker.submit_bulk_mutation("test_bulk_recovery", [1, 2], {},
            idempotency_key="bulk-command-recovery", trigger="manual")

    def _stale_claim(self, command, *, cancelled=False):
        run = operation_store.claim_run(command["run_id"], execution_id="recovery-old", worker_pid=123)
        self.assertIsNotNone(run)
        if cancelled:
            operation_store.request_run_cancel(run["id"], reason="test cancellation")
        with operation_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {operation_store._table('operation_runs')}
                SET heartbeat_at = now() - interval '30 minutes' WHERE id = %s""", (run["id"],))
        return task_gateway.OperationHandlerContext(run, execution_id="recovery-old")

    def test_recovery_enqueues_one_new_run_without_replaying_the_committed_chunk(self):
        operation_store.reset_ready()
        operation_store.init()
        install_native_settlement_fixture(self)

        def first_chunk_then_crash(chunk, parameters, *, conn):
            if chunk == (2,):
                raise KeyboardInterrupt("simulated worker exit")
            return self._increment(chunk, parameters, conn=conn)

        command = self._submit(first_chunk_then_crash)
        context = self._stale_claim(command)
        with self.assertRaises(KeyboardInterrupt):
            worker._handle_claimed_bulk_mutation(context)
        with operation_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {operation_store._table('operation_runs')}
                SET heartbeat_at = now() - interval '30 minutes' WHERE id = %s""", (context.run_id,))
        worker.register_bulk_mutation_handler("test_bulk_recovery", self._increment, chunk_size=1)
        worker.register_runtime_handler()

        reconciliation.recover_stale_runtime_runs()
        reconciliation.recover_stale_runtime_runs()

        current = operation_store.get_task(command["task_id"], include_events=False)
        self.assertEqual("interrupted", operation_store.get_run(context.run_id)["status"])
        self.assertEqual("queued", current["status"])
        self.assertEqual(2, len(current["runs"]))
        result = worker.run_bulk_mutation(current["last_run_id"])
        self.assertEqual("success", result["status"])
        with operation_store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id, value FROM {operation_store._table('test_bulk_counters')} ORDER BY id")
            self.assertEqual([{"id": 1, "value": 1}, {"id": 2, "value": 1}], cur.fetchall())

    def test_recovery_leaves_an_interrupted_cancellation_terminal(self):
        command = self._submit(self._increment)
        self._stale_claim(command, cancelled=True)

        reconciliation.recover_stale_runtime_runs()

        current = operation_store.get_task(command["task_id"], include_events=False)
        self.assertEqual("interrupted", current["status"])
        self.assertEqual(1, len(current["runs"]))

    def test_independent_worker_installs_bulk_handlers_before_dispatch(self):
        with TemporaryDirectory() as directory, patch.object(process, "_RUNTIME", None), \
                patch.object(process, "_LIFECYCLE", None), patch.dict(worker._HANDLERS, clear=True):
            assembly.install(RuntimeBootstrap("worker", "bulk-integration", Path(directory), "a" * 40))
            self.assertTrue({"account_archive", "codex_delete", "email_pool_status"}
                            <= set(worker.registered_bulk_mutation_operations()))
            self.assertIn(worker.TASK_TYPE, task_gateway.registered_dispatch_types())
