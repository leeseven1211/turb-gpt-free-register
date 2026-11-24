from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest

from core.operations import bulk_mutation_worker as worker, task_gateway
from core.operations.bulk_mutations import BulkItemResult
from core.operations.runtime import OperationCancelled
from core.storage.operations import bulk_mutations as commands, store as operation
from tests.support_pg import PostgresTestCase


@pytest.fixture(autouse=True)
def _restore_registries():
    from core.operations import concurrency
    names = ('_DISPATCH_HANDLERS', '_DISPATCH_CAPACITY_HANDLERS', '_OPERATION_HANDLERS',
        '_OPERATION_ACTIONS', '_OPERATION_ACTION_SOURCES', '_OPERATION_HANDLER_ALLOWLISTS')
    snapshots = {name:dict(getattr(task_gateway, name)) for name in names}
    old_handlers = dict(worker._HANDLERS)
    old_registered = worker._RUNTIME_REGISTERED
    old_aliases = dict(concurrency._ALIASES)
    yield
    worker._HANDLERS.clear()
    worker._HANDLERS.update(old_handlers)
    worker._RUNTIME_REGISTERED = old_registered
    concurrency._ALIASES.clear()
    concurrency._ALIASES.update(old_aliases)
    for name, values in snapshots.items():
        getattr(task_gateway, name).clear()
        getattr(task_gateway, name).update(values)


def test_unknown_operation_is_rejected_before_persistence():
    with pytest.raises(ValueError, match="bulk_handler_not_registered"):
        worker.submit_bulk_mutation("unregistered-test", [1], {},
            idempotency_key="unknown", trigger="manual")


def test_parameters_require_allowlist_and_reject_sensitive_fields():
    worker.register_bulk_mutation_handler("test_allowlist", lambda chunk, parameters, *, conn: [],
        parameter_allowlist=("note", "session"))
    for parameters in ({"other": 1}, {"session": "secret"}, {"note": object()}):
        with pytest.raises((ValueError, TypeError)):
            worker.submit_bulk_mutation("test_allowlist", [1], parameters,
                idempotency_key="invalid", trigger="manual")


def test_invalid_chunk_size_and_foreign_run_are_rejected_before_claim():
    for size in (0, 501, True):
        with pytest.raises(ValueError, match="invalid_bulk_chunk_size"):
            worker.register_bulk_mutation_handler("chunk_validation", lambda chunk, parameters, *, conn: [], chunk_size=size)
    with patch.object(task_gateway, '_operation') as storage, patch.object(task_gateway, '_execute_operation_handler') as execute:
        storage.return_value.get_run.return_value = {'id':4,'task_type':'codex_retry',
            'source_system':'native_operations','data':{'command_id':1}}
        assert worker.run_bulk_mutation(4)['status'] == 'not_bulk_mutation'
        execute.assert_not_called()


@pytest.mark.parametrize('secret', [
    'Bearer synthetic-bearer-secret',
    'sk-syntheticsecret000000000000000',
    '-----BEGIN PRIVATE KEY-----\nsynthetic-private-value\n-----END PRIVATE KEY-----',
])
def test_receipt_redacts_all_credential_patterns(secret):
    receipt = worker._receipt_value({'reason':secret,'values':[secret]})
    assert secret not in receipt['reason']
    assert secret not in receipt['values'][0]
    assert 'synthetic-private-value' not in receipt['reason']


class BulkMutationWorkerTests(PostgresTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        from core import account_task_store
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        operation.reset_ready()
        operation.init()
        commands.init()
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE TABLE IF NOT EXISTS {operation._table('test_bulk_counters')} "
                "(id bigint PRIMARY KEY, value integer NOT NULL DEFAULT 0)")

    def _register(self, name="test_increment", *, handler=None, parameter_allowlist=()):
        def increment(chunk, parameters, *, conn):
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO {operation._table('test_bulk_counters')} (id,value) "
                    "SELECT value,1 FROM unnest(%s::bigint[]) value "
                    "ON CONFLICT(id) DO UPDATE SET value=test_bulk_counters.value+1", (list(chunk),))
            return [BulkItemResult(key=key, status="updated") for key in chunk]
        worker.register_bulk_mutation_handler(name, handler or increment,
            parameter_allowlist=parameter_allowlist)
        return increment

    def _submit(self, targets, *, key="request", operation_name="test_increment", parameters=None):
        return worker.submit_bulk_mutation(operation_name, targets, parameters or {},
            idempotency_key=key, trigger="manual")

    def _claim(self, submitted, *, execution="test-worker"):
        run = operation.claim_run(submitted["run_id"], execution_id=execution, worker_pid=123)
        self.assertIsNotNone(run)
        return task_gateway.OperationHandlerContext(run, execution_id=execution)

    def _counters(self):
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id,value FROM {operation._table('test_bulk_counters')} ORDER BY id")
            return {row['id']: row['value'] for row in cur.fetchall()}

    def test_complete_targets_and_receipts_survive_above_five_thousand(self):
        self._register()
        submitted = self._submit(list(range(5001)))
        command = commands.get_command(submitted["command_id"])
        self.assertEqual(list(range(5001)), command["targets"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual({"command_id", "operation", "bulk_mutation"}, set(run["data"]))
        result = worker._handle_claimed_bulk_mutation(self._claim(submitted))
        self.assertEqual(5001, result.summary["updated_count"])
        persisted = commands.get_command_result(submitted["command_id"])
        self.assertEqual(5001, len(persisted["items"]))
        self.assertEqual(list(range(5001)), [item["key"] for item in persisted["items"]])
        self.assertEqual({1}, set(self._counters().values()))
        events = operation.list_task_events(submitted["task_id"], run_id=submitted["run_id"], limit=100)
        self.assertTrue(events["items"])
        self.assertTrue(all("items" not in event["detail"] for event in events["items"]))

    def test_crash_after_business_write_rolls_back_chunk_and_reentry_does_not_increment_twice(self):
        increment = self._register()
        submitted = self._submit([1, 2])
        context = self._claim(submitted)

        def crash(chunk, parameters, *, conn):
            increment(chunk, parameters, conn=conn)
            raise KeyboardInterrupt("simulated crash before receipt")

        worker.register_bulk_mutation_handler("test_increment", crash)
        with self.assertRaises(KeyboardInterrupt):
            worker._handle_claimed_bulk_mutation(context)
        self.assertEqual({}, self._counters())
        self.assertEqual([], commands.get_command_result(submitted["command_id"])["items"])
        self._register()
        first = worker._handle_claimed_bulk_mutation(context)
        second = worker._handle_claimed_bulk_mutation(context)
        self.assertEqual(2, first.summary["updated_count"])
        self.assertEqual(2, second.summary["updated_count"])
        self.assertEqual({1: 1, 2: 1}, self._counters())

    def test_committed_chunk_receipt_survives_new_run_after_interruption(self):
        increment = self._register()
        submitted = self._submit(list(range(501)))
        context = self._claim(submitted)

        def crash_second(chunk, parameters, *, conn):
            if chunk[0] == 500:
                raise KeyboardInterrupt("worker restart")
            return increment(chunk, parameters, conn=conn)

        worker.register_bulk_mutation_handler("test_increment", crash_second)
        with self.assertRaises(KeyboardInterrupt):
            worker._handle_claimed_bulk_mutation(context)
        operation.finish_run(context.run_id, status="interrupted", execution_id=context.execution_id)
        retry = operation.retry_runtime_task(submitted["task_id"])
        self._register()
        next_context = self._claim({**submitted, "run_id": retry["id"]}, execution="replacement-worker")
        result = worker._handle_claimed_bulk_mutation(next_context)
        self.assertEqual(501, result.summary["updated_count"])
        self.assertEqual(501, len(commands.get_command_result(submitted["command_id"])["items"]))
        self.assertEqual({1}, set(self._counters().values()))

    def test_same_key_different_payload_conflicts_and_concurrent_same_key_creates_once(self):
        self._register(parameter_allowlist=("note",))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self._submit([1, 2], parameters={"note": "a"}), range(2)))
        self.assertEqual(results[0]["command_id"], results[1]["command_id"])
        self.assertEqual(results[0]["run_id"], results[1]["run_id"])
        with self.assertRaisesRegex(ValueError, "idempotency_key_conflict"):
            self._submit([1, 3], parameters={"note": "a"})
        with self.assertRaisesRegex(ValueError, "idempotency_key_conflict"):
            self._submit([1, 2], parameters={"note": "b"})
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_bulk_mutation_commands')}")
            self.assertEqual(1, cur.fetchone()["n"])
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')} WHERE task_type='bulk_mutation'")
            self.assertEqual(1, cur.fetchone()["n"])

    def test_cancel_between_chunks_preserves_committed_chunk_and_stops_remaining(self):
        self._register()
        submitted = self._submit(list(range(501)))
        context = self._claim(submitted)
        original_report = context.report

        def report(**event):
            stored = original_report(**event)
            if event.get("event_type") == "bulk.chunk.completed":
                operation.request_run_cancel(context.run_id, reason="test cancellation")
            return stored

        with patch.object(context, "report", report):
            with self.assertRaises(OperationCancelled):
                worker._handle_claimed_bulk_mutation(context)
        self.assertEqual(500, len(self._counters()))
        self.assertEqual(500, len(commands.get_command_result(submitted["command_id"])["items"]))

    def test_missing_result_is_failed_and_failure_reason_is_durable(self):
        self._register(handler=lambda chunk, parameters, *, conn: [
            BulkItemResult(key=1, status="failed", reason_code="target_locked")])
        submitted = self._submit([1, 2])
        result = worker._handle_claimed_bulk_mutation(self._claim(submitted))
        self.assertEqual(2, result.summary["failed_count"])
        persisted = commands.get_command_result(submitted["command_id"])
        self.assertEqual(["target_locked", "bulk_result_missing"],
            [item["reason_code"] for item in persisted["items"]])

    def test_failed_chunk_rolls_back_mutation_and_records_stable_reason(self):
        increment = self._register()
        def fail(chunk, parameters, *, conn):
            increment(chunk, parameters, conn=conn)
            raise worker.BulkChunkFailed()
        self._register(handler=fail)
        submitted = self._submit([1])
        result = worker._handle_claimed_bulk_mutation(self._claim(submitted))
        self.assertEqual("failed", result.status)
        self.assertEqual({}, self._counters())
        self.assertEqual("bulk_chunk_failed",
            commands.get_command_result(submitted["command_id"])["items"][0]["reason_code"])
        self.assertEqual("failed", commands.get_command_result(submitted["command_id"])["chunks"][0]["status"])

    def test_database_failure_does_not_become_a_permanent_failed_receipt(self):
        from psycopg import OperationalError
        increment = self._register()
        def fail(chunk, parameters, *, conn):
            increment(chunk, parameters, conn=conn)
            raise OperationalError("synthetic connection failure")
        self._register(handler=fail)
        submitted = self._submit([1])
        context = self._claim(submitted)
        result = worker._handle_claimed_bulk_mutation(context)
        self.assertEqual('deferred', result['status'])
        self.assertEqual({}, self._counters())
        self.assertEqual([], commands.get_command_result(submitted["command_id"])["items"])
        self._register()
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET next_attempt_at=NULL WHERE id=%s", (context.run_id,))
        recovered = worker._handle_claimed_bulk_mutation(self._claim(submitted, execution='replacement'))
        self.assertEqual(1, recovered.summary['updated_count'])
        self.assertEqual({1:1}, self._counters())

    def test_deterministic_handler_errors_are_stable_failed_receipts(self):
        handlers = [
            lambda chunk, parameters, *, conn: [{'key':1,'status':'invalid-status'}],
            lambda chunk, parameters, *, conn: [BulkItemResult(1,'updated',data=object())],
            lambda chunk, parameters, *, conn: (_ for _ in ()).throw(TypeError('synthetic contract error')),
        ]
        for index, handler in enumerate(handlers):
            self._register(handler=handler)
            submitted = self._submit([1], key=f'contract-error-{index}')
            context = self._claim(submitted)
            result = worker._handle_claimed_bulk_mutation(context)
            self.assertEqual('failed', result.status)
            receipt = commands.get_command_result(submitted['command_id'])
            self.assertEqual('bulk_handler_error', receipt['items'][0]['reason_code'])
            self.assertEqual('bulk_handler_error', receipt['chunks'][0]['reason_code'])
            self.assertEqual('failed', receipt['chunks'][0]['status'])
            self._register()
            repeated = worker._handle_claimed_bulk_mutation(context)
            self.assertEqual('failed', repeated.status)
            self.assertEqual({}, self._counters())

    def test_committed_mixed_item_results_do_not_imply_whole_chunk_rollback(self):
        self._register(handler=lambda chunk, parameters, *, conn: [
            BulkItemResult(1,'updated'),BulkItemResult(2,'failed','target_locked')])
        submitted = self._submit([1,2])
        worker._handle_claimed_bulk_mutation(self._claim(submitted))
        chunk = commands.get_command_result(submitted['command_id'])['chunks'][0]
        self.assertEqual('updated', chunk['status'])
        self.assertNotIn('reason_code', chunk)

    def test_idempotency_is_operation_scoped_and_ignores_order_duplicates_and_chunk_size(self):
        increment = self._register(parameter_allowlist=('note',))
        first = self._submit([2,1,1], parameters={'note':'a'})
        worker.register_bulk_mutation_handler('test_increment', increment,
            parameter_allowlist=('note',), chunk_size=1)
        same = self._submit([1,2], parameters={'note':'a'})
        self.assertEqual(first['command_id'], same['command_id'])
        self._register('different_operation')
        other = self._submit([1,2], operation_name='different_operation')
        self.assertNotEqual(first['command_id'], other['command_id'])

    def test_chunk_transaction_reads_only_sql_target_slice(self):
        self._register()
        submitted = self._submit(list(range(1001)))
        context = self._claim(submitted)
        seen = []
        actual = commands._chunk_command
        def capture(cur, command_id, index):
            row = actual(cur, command_id, index)
            seen.append(row)
            return row
        with patch.object(commands, '_chunk_command', capture):
            worker._handle_claimed_bulk_mutation(context)
        self.assertEqual([500,500,1], [len(row['chunk']) for row in seen])
        self.assertTrue(all('input_targets' not in row and 'targets' not in row for row in seen))

    def test_commit_failure_leaves_no_receipt_and_can_retry(self):
        from psycopg import OperationalError
        increment = self._register()
        armed = False
        def increment_before_commit(chunk, parameters, *, conn):
            nonlocal armed
            values = increment(chunk, parameters, conn=conn)
            armed = True
            return values
        self._register(handler=increment_before_commit)
        submitted = self._submit([1])
        context = self._claim(submitted)
        original = commands.common._connect
        @contextmanager
        def fail_commit_once():
            nonlocal armed
            with original() as conn:
                yield conn
                if armed:
                    armed = False
                    raise OperationalError('synthetic commit failure')
        with patch.object(commands.common, '_connect', fail_commit_once):
            result = worker._handle_claimed_bulk_mutation(context)
        self.assertEqual('deferred', result['status'])
        self.assertEqual({}, self._counters())
        self.assertEqual([], commands.get_command_result(submitted['command_id'])['items'])

    def test_note_business_text_is_preserved_and_receipt_diagnostics_are_redacted(self):
        note = '用户记录 https://user:password@example.test 和 eyJabcdefghijklm.abcdefghijklmn.abcdefghijklmn'
        observed = []
        def handler(chunk, parameters, *, conn):
            observed.append(parameters['note'])
            return [BulkItemResult(1,'failed','explicit_failure',reason=note,
                data={'note':note,'access_token':'should-not-persist'})]
        self._register(handler=handler,parameter_allowlist=('note',))
        submitted = self._submit([1], parameters={'note':note})
        worker._handle_claimed_bulk_mutation(self._claim(submitted))
        self.assertEqual([note], observed)
        self.assertEqual(note,commands.get_command(submitted['command_id'])['parameters']['note'])
        receipt = commands.get_command_result(submitted['command_id'])['items'][0]
        self.assertNotIn('user:password',receipt['reason'])
        self.assertNotIn('eyJabcdefghijklm',receipt['reason'])
        self.assertNotIn('access_token',receipt['data'])

    def test_stale_execution_fence_cannot_mutate_or_store_receipt(self):
        self._register()
        submitted = self._submit([1])
        context = self._claim(submitted)
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {operation._table('operation_runs')} SET execution_id='new-owner' WHERE id=%s", (context.run_id,))
        with self.assertRaises(PermissionError):
            worker._handle_claimed_bulk_mutation(context)
        self.assertEqual({}, self._counters())
        self.assertEqual([], commands.get_command_result(submitted["command_id"])["items"])

    def test_submission_rollback_leaves_neither_command_nor_task(self):
        self._register()
        actual_attach = commands.attach_task
        def reject(*args, **kwargs):
            actual_attach(*args, **kwargs)
            raise RuntimeError('abort queue transaction')
        with patch.object(commands, 'attach_task', reject):
            with self.assertRaisesRegex(RuntimeError, 'abort queue transaction'):
                self._submit([1])
        with operation._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_bulk_mutation_commands')}")
            self.assertEqual(0, cur.fetchone()['n'])
            cur.execute(f"SELECT count(*) AS n FROM {operation._table('operation_tasks')} WHERE task_type='bulk_mutation'")
            self.assertEqual(0, cur.fetchone()['n'])

    def test_after_commit_observes_committed_data_and_reentry_reissues_idempotent_notification(self):
        increment = self._register()
        observed = []
        def after_commit(chunk, parameters, items):
            observed.append((self._counters(), len(items)))
        worker.register_bulk_mutation_handler('test_increment', increment, after_commit=after_commit)
        submitted = self._submit([1, 2])
        context = self._claim(submitted)
        worker._handle_claimed_bulk_mutation(context)
        worker._handle_claimed_bulk_mutation(context)
        self.assertEqual([({1:1,2:1},2),({1:1,2:1},2)], observed)
