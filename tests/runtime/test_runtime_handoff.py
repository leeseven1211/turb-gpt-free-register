"""Product durable handoff regressions with in-memory storage and injected I/O.

Migrated from the approved Phase 6 T4 candidate. Product modules are imported
normally; tests never load candidate files, compile extracted bodies, or connect.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager, nullcontext
from pathlib import Path
import threading
import types
import unittest
from unittest.mock import Mock, patch
import uuid
from datetime import datetime, timedelta, timezone

from config import email as email_config
from core.email.email_butler import manual_import as manual
from core.email.email_butler import manual_import_v2 as manual_v2
from core.maintenance import sentinel
from core.runtime import process
from core.storage import postgres
from core.storage.email import butler_manual_imports as store
from core.storage.operations import runtime as operations
from core.storage.operations import sentinel_checks as queue


class Records(types.ModuleType):
    def __init__(self):
        super().__init__("core.storage.records")
        for name in ("EMAIL_BUTLER_IMPORT_BATCHES", "EMAIL_BUTLER_IMPORT_ITEMS", "EMAIL_BUTLER_IMPORT_PREVIEWS",
                     "EMAIL_INBOX_PROFILES", "EMAIL_BUTLER_POOL", "ACCOUNTS", "EMAIL_ADDRESS_ALLOCATIONS",
                     "LOCAL_EMAIL_CLAIMS", "EMAIL_BUTLER_CLAIM_INTENTS"):
            setattr(self, name, name)
        self.rows = {}
        self.events = []
        self.current = None

    @contextmanager
    def transaction(self):
        previous, old = copy.deepcopy(self.rows), self.current
        conn = object()
        self.current = conn
        self.events.append(("begin", conn))
        try:
            yield conn
        except BaseException:
            self.rows = previous
            raise
        else:
            self.events.append(("commit", conn))
        finally:
            self.current = old

    def advisory_xact_lock(self, conn, key):
        if conn is not self.current:
            raise AssertionError("advisory lock must use current transaction")
        self.events.append(("lock", key, conn))

    def insert_row(self, spec, values, *, conn=None):
        rows = self.rows.setdefault(spec, {})
        identifier = max(rows, default=0) + 1
        rows[identifier] = {"id": identifier, **copy.deepcopy(values)}
        self.events.append(("insert", spec, conn))
        return identifier

    def get_row(self, spec, identifier, *, conn=None):
        return copy.deepcopy(self.rows.get(spec, {}).get(identifier))

    def get_row_by(self, spec, field, value, *, conn=None, **kw):
        return next((copy.deepcopy(row) for row in self.rows.get(spec, {}).values() if row.get(field) == value), None)

    def list_rows(self, spec, *, where="", params=(), conn=None, order_by="", limit=None, **kw):
        rows = list(self.rows.get(spec, {}).values())
        if spec == self.EMAIL_BUTLER_IMPORT_ITEMS and params:
            rows = [r for r in rows if r.get("batch_id") == params[0]]
        if spec == self.EMAIL_BUTLER_IMPORT_BATCHES:
            if "dispatch_requested" in where:
                rows = [r for r in rows if r.get("dispatch_requested") is True and r["status"] not in {"cancelled", "completed"}]
            elif where == "status = %s":
                rows = [r for r in rows if r["status"] == params[0]]
        return copy.deepcopy(rows[:limit] if limit else rows)

    def patch_row(self, spec, identifier, changes, *, conn=None):
        self.rows[spec][identifier].update(copy.deepcopy(changes))
        self.events.append(("patch", spec, conn, copy.deepcopy(changes)))
        return True

    def claim_row(self, spec, identifier, *, changes, guard="", guard_params=(), conn=None):
        row = self.rows[spec][identifier]
        if "status <> 'cancelled'" in guard and row["status"] == "cancelled":
            return False
        if "worker_execution_id" in guard and row.get("worker_execution_id") != guard_params[0]:
            return False
        if "dispatch_requested" in guard and row.get("dispatch_requested") is not True:
            return False
        self.patch_row(spec, identifier, changes, conn=conn)
        return True


class Result:
    @staticmethod
    def failed(message, summary=None):
        return {"status": "failed", "message": message, "summary": summary}

    @staticmethod
    def success(summary, message=""):
        return {"status": "success", "message": message, "summary": summary}


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.records = Records()
        self.role = "web"
        self.open = False
        self.manual, self.v2, self.store = manual, manual_v2, store
        self.sentinel, self.operations, self.queue = sentinel, operations, queue
        self.concurrency = types.SimpleNamespace(
            owner_liveness=lambda owner: "exited",
            ConcurrencyStoreUnavailable=type("ConcurrencyStoreUnavailable", (Exception,), {}),
            ConcurrencyPolicyError=type("ConcurrencyPolicyError", (Exception,), {}),
            AdmissionResult=lambda **kw: types.SimpleNamespace(context=None, **kw),
            admission_transaction=self.records.transaction,
            active_execution_keys=lambda **kw: (),
            try_admit_and_claim=Mock(side_effect=AssertionError("unexpected permit acquisition")),
            execution_scope=lambda ctx: nullcontext(),
            release_execution=Mock(),
        )
        self.api = types.SimpleNamespace(
            normalize_base=lambda base: base,
            me=Mock(return_value={"client_id": "fixture-client", "permissions": ["*"], "allowed_services": ["openai"]}),
            availability=Mock(return_value={"service": "openai", "available": 2}),
            create_lease=Mock(side_effect=AssertionError("request must not allocate")),
            get_lease=Mock(), list_leases=Mock(),
            ButlerV2Error=type("ButlerV2Error", (Exception,), {}),
        )
        self.imports = types.SimpleNamespace(
            _fixed_butler_profile=lambda conn, **kw: {"id": 17},
            butler_forward_address=lambda value: value,
        )
        self.gateway = types.SimpleNamespace(
            OperationResult=Result,
            register_operation_handler=Mock(), notify_dispatch=Mock(),
            register_operation_actions=Mock(), default_operation_terminate=Mock(),
            default_operation_cancel=Mock(return_value={"accepted": True}),
            submit_durable_operation=Mock(return_value={"accepted": True, "task_id": 11, "run_id": 19, "status": "queued"}),
            _execute_operation_handler=Mock(side_effect=AssertionError("request must not execute")),
        )
        self.assetcheck = lambda status, reason=None, artifact=None: types.SimpleNamespace(
            status=status, reason=reason, artifact=artifact)
        for guard in (
            patch.object(postgres, "connect", side_effect=AssertionError("real database forbidden")),
            patch.object(process, "get_runtime_context", side_effect=lambda: types.SimpleNamespace(mode=self.role, executes=self.role != "web")),
            patch.object(process, "execution_admitted", side_effect=lambda: self.open and self.role in {"worker", "combined"}),
            patch.object(email_config, "EMAIL_BUTLER_API_BASE", "https://butler.invalid/v2"),
            patch.object(email_config, "EMAIL_BUTLER_API_KEY", "fixture"),
            patch.object(store, "record_store", self.records),
            patch.object(manual, "record_store", self.records),
            patch.object(manual, "concurrency", self.concurrency),
            patch.object(manual, "current_owner", return_value={"pid": 123, "process_start": "fixture"}),
            patch.object(manual, "_DISPATCH_STOP", threading.Event()),
            patch.object(manual, "_DISPATCH_WAKE", threading.Event()),
            patch.object(manual, "_DISPATCH_THREAD", None),
            patch.object(manual, "_BATCH_THREADS", {}),
            patch.object(manual, "_FINISHED_BATCH_EXECUTIONS", set()),
            patch.object(manual, "_OWNER_RELEASE_PENDING", {}),
            patch.object(manual, "_DISPATCH_ERROR", None),
            patch.object(manual_v2, "record_store", self.records),
            patch.object(manual_v2, "concurrency", self.concurrency),
            patch.object(manual_v2, "v2", self.api),
            patch.object(manual_v2, "imports", self.imports),
            patch.object(sentinel, "task_gateway", self.gateway),
            patch.object(sentinel, "_SERVICE", None),
            patch.object(sentinel, "_SERVICE_INSTANCES", {}),
            patch.object(sentinel, "_CACHE_DIRECTORY", None),
            patch.object(sentinel, "SentinelAssetManager", side_effect=lambda path: types.SimpleNamespace(cache_dir=Path(path))),
            patch.object(queue, "active_check", return_value=None),
            patch.object(queue, "request_check", side_effect=lambda key, create: create(object())),
            patch.object(operations, "retry_runtime_task", return_value={"id": 23, "task_id": 11}),
        ):
            guard.start()
            self.addCleanup(guard.stop)

    def create_batch(self):
        preview = self.manual.preview({"provider": "icloud_hme", "count": 2})
        request = {"preview_token": preview["preview_token"], "request_id": str(uuid.uuid4())}
        with patch.object(threading, "Thread", side_effect=AssertionError("Web must not start a thread")):
            batch = self.manual.create(request)
        return batch, request

    def sentinel_service(self):
        manager = types.SimpleNamespace(cache_dir=Path("/fixture/stable/cache"))
        service = self.sentinel.SentinelMaintenanceService(
            manager=manager, builtin_path="/fixture/builtin.js", builtin_version="fixture",
            executor=Mock(side_effect=AssertionError("request must not dispatch")))
        service._load_local = Mock()
        service._lease = Mock(side_effect=AssertionError("request must not acquire a file lease"))
        service._external_running = Mock(return_value=False)
        service._persist_check = Mock()
        return service

    def test_preview_reads_availability_but_never_claims_remote_or_creates_batch(self):
        result = self.manual.preview({"provider": "icloud_hme", "count": 2})
        self.assertEqual([], result["items"])
        self.assertEqual(2, result["selected"])
        self.assertEqual({}, self.records.rows.get(self.records.EMAIL_BUTLER_IMPORT_BATCHES, {}))
        self.api.create_lease.assert_not_called()

    def test_create_commits_dispatch_request_with_original_batch_and_slots_without_thread(self):
        batch, request = self.create_batch()
        row = self.store.batch(batch["batch_id"])
        self.assertIs(row.get("dispatch_requested"), True)
        items = self.store.items(batch["batch_id"])
        self.assertEqual(2, len(items))
        self.assertEqual(items[0]["idempotency_key"], items[0]["external_ref"])
        batch_insert = next(e for e in self.records.events if e[:2] == ("insert", self.records.EMAIL_BUTLER_IMPORT_BATCHES))
        request_write = next(e for e in self.records.events if e[0] == "patch" and e[3].get("dispatch_requested"))
        self.assertIs(batch_insert[2], request_write[2])
        again = self.manual.create(request)
        self.assertEqual(batch["batch_id"], again["batch_id"])
        self.assertEqual(items, self.store.items(batch["batch_id"]))
        self.api.create_lease.assert_not_called()

    def test_handoff_write_failure_rolls_back_batch_and_original_intents(self):
        self.assertTrue(hasattr(self.store, "request_execution"), "durable request seam absent")
        preview = self.manual.preview({"provider": "icloud_hme", "count": 2})
        with patch.object(self.store, "request_execution", side_effect=RuntimeError("write unavailable")):
            with self.assertRaisesRegex(RuntimeError, "write unavailable"):
                self.manual.create({"preview_token": preview["preview_token"], "request_id": str(uuid.uuid4())})
        self.assertEqual({}, self.records.rows.get(self.records.EMAIL_BUTLER_IMPORT_BATCHES, {}))
        self.assertEqual({}, self.records.rows.get(self.records.EMAIL_BUTLER_IMPORT_ITEMS, {}))

    def test_retry_marks_same_batch_and_does_not_replace_remote_identity_or_spawn(self):
        batch, _ = self.create_batch()
        row = self.store.batch(batch["batch_id"])
        self.records.patch_row(self.records.EMAIL_BUTLER_IMPORT_BATCHES, row["id"],
                               {"status": "partial", "dispatch_requested": False})
        before = self.store.items(batch["batch_id"])
        with patch.object(threading, "Thread", side_effect=AssertionError("Web thread")):
            self.manual.retry(batch["batch_id"])
        self.assertTrue(self.store.batch(batch["batch_id"])["dispatch_requested"])
        self.assertEqual(before, self.store.items(batch["batch_id"]))

    def test_cancel_clears_pending_dispatch_without_releasing_remote_lease(self):
        batch, _ = self.create_batch()
        items = self.store.items(batch["batch_id"])
        with patch.object(threading, "Thread", side_effect=AssertionError("Web thread")):
            receipt = self.manual.cancel(batch["batch_id"])
        self.assertEqual("cancelled", receipt["status"])
        self.assertFalse(self.store.batch(batch["batch_id"])["dispatch_requested"])
        self.assertEqual(items, self.store.items(batch["batch_id"]))
        self.api.create_lease.assert_not_called()

    def test_web_and_closed_gate_do_not_scan_or_claim_batches(self):
        self.assertTrue(hasattr(self.manual, "dispatch_pending_once"), "durable dispatcher absent")
        with patch.object(self.store, "pending_batches", side_effect=AssertionError("must not read dispatch queue")):
            self.assertEqual(0, self.manual.dispatch_pending_once())
            self.role = "worker"
            self.assertEqual(0, self.manual.dispatch_pending_once())

    def test_claim_consumes_only_pending_request_and_checks_gate_before_owner(self):
        batch, _ = self.create_batch()
        self.assertIsNone(self.manual._claim_batch_owner(batch["batch_id"]))
        self.assertTrue(self.store.batch(batch["batch_id"])["dispatch_requested"])
        self.role, self.open = "worker", True
        owned = self.manual._claim_batch_owner(batch["batch_id"])
        self.assertIsNotNone(owned)
        self.assertFalse(self.store.batch(batch["batch_id"])["dispatch_requested"])
        self.assertIsNone(self.manual._claim_batch_owner(batch["batch_id"]))

    def test_reconcile_preserves_unclaimed_durable_request_and_never_retries_claimed_unknown(self):
        batch, _ = self.create_batch()
        self.assertEqual(0, self.manual.reconcile_interrupted())
        row = self.store.batch(batch["batch_id"])
        self.records.patch_row(self.records.EMAIL_BUTLER_IMPORT_BATCHES, row["id"],
                               {"dispatch_requested": False, "worker_owner": {"pid": 999}, "worker_execution_id": "dead"})
        self.assertEqual(1, self.manual.reconcile_interrupted())
        current = self.store.batch(batch["batch_id"])
        self.assertEqual("partial", current["status"])
        self.assertFalse(current["dispatch_requested"])
        self.api.create_lease.assert_not_called()

    def test_waiting_for_permit_exits_on_closed_gate_without_claim_or_remote(self):
        batch, _ = self.create_batch()
        self.role = "worker"
        self.assertIsNone(self.manual._wait_import_execution(
            self.store.batch(batch["batch_id"]), "item:1", Mock(side_effect=AssertionError("must not claim"))))
        self.concurrency.try_admit_and_claim.assert_not_called()

    def test_sentinel_acceptance_creates_durable_run_without_lease_or_executor(self):
        service = self.sentinel_service()
        receipt = service.start_check()
        self.assertTrue(receipt["accepted"])
        self.assertTrue(receipt["started"])
        self.assertEqual((11, 19, "queued"), (receipt["task_id"], receipt["run_id"], receipt["status"]))
        service._lease.assert_not_called()
        service.executor.assert_not_called()
        self.gateway._execute_operation_handler.assert_not_called()
        submitted = self.gateway.submit_durable_operation.call_args.kwargs
        self.assertEqual({"cache_key": self.sentinel._cache_key(service)}, submitted["data"])
        self.assertFalse(submitted["dispatch"])

    def test_sentinel_duplicate_reuses_persisted_task_run_across_service_instances(self):
        self.queue.request_check.side_effect = None
        self.queue.request_check.return_value = {"accepted": True, "reused": True, "task_id": 11, "run_id": 19, "status": "queued"}
        service = self.sentinel_service()
        receipt = service.start_check()
        self.assertFalse(receipt["started"])
        self.assertTrue(receipt["running"])
        self.assertEqual((11, 19), (receipt["task_id"], receipt["run_id"]))
        self.gateway.submit_durable_operation.assert_not_called()
        service._lease.assert_not_called()

    def test_sentinel_status_after_web_restart_reads_durable_activity_without_claim(self):
        service = self.sentinel_service()
        self.queue.active_check.return_value = {"task_id": 11, "run_id": 19, "status": "queued"}
        self.assertTrue(service.status()["running"])
        self.queue.active_check.assert_called_once_with(self.sentinel._cache_key(service))
        service._lease.assert_not_called()
        service.executor.assert_not_called()

    def test_sentinel_worker_rebuilds_from_trusted_cache_and_acquires_only_at_execution(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        lease = Mock()
        service._lease.side_effect = None
        service._lease.return_value = lease
        service._run_check = Mock(return_value=self.assetcheck("refreshed"))
        service.status = Mock(return_value={"last_status": "refreshed"})
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock(), defer=Mock())
        with patch.object(self.sentinel, "get_service", return_value=service):
            self.sentinel._SERVICE_INSTANCES.clear()
            result = self.sentinel._handle_check(context)
        self.assertEqual("success", result["status"])
        service._lease.assert_called_once_with(create=True)
        service._run_check.assert_called_once_with(lease)
        self.assertEqual((19, 11), (service._queued_run_id, service._queued_task_id))

    def test_sentinel_closed_gate_defers_same_run_before_cache_lease(self):
        service = self.sentinel_service()
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock(), defer=Mock(return_value={"status": "deferred"}))
        with patch.object(self.sentinel, "get_service", return_value=service):
            result = self.sentinel._handle_check(context)
        self.assertEqual("deferred", result["status"])
        service._lease.assert_not_called()
        self.gateway.submit_durable_operation.assert_not_called()

    def test_sentinel_terminal_receipt_does_not_report_its_own_run_as_active(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        lease = Mock()
        service._lease.side_effect = None
        service._lease.return_value = lease
        def finish(current):
            current.close()
            service._running = False
            service._last_status = "refreshed"
            return self.assetcheck("refreshed")
        service._run_check = Mock(side_effect=finish)
        self.queue.active_check.return_value = {"task_id": 11, "run_id": 19, "status": "running"}
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock())
        with patch.object(self.sentinel, "get_service", return_value=service):
            result = self.sentinel._handle_check(context)
        self.assertFalse(result["summary"]["running"])
        self.assertEqual("refreshed", result["summary"]["last_status"])
        self.queue.active_check.assert_not_called()

    def test_sentinel_changed_trusted_cache_does_not_fetch_original_or_new_location(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        context = types.SimpleNamespace(run={"data": {"cache_key": "different"}}, run_id=19, task_id=11, checkpoint=Mock())
        with patch.object(self.sentinel, "get_service", return_value=service):
            result = self.sentinel._handle_check(context)
        self.assertEqual("maintenance_cache_changed", result["summary"]["error_code"])
        service._lease.assert_not_called()

    def test_sentinel_owner_loss_after_cache_lease_defers_and_closes_before_remote(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        lease = Mock()
        def acquire(*, create):
            self.open = False
            return lease
        service._lease.side_effect = acquire
        service._run_check = Mock(side_effect=AssertionError("must not start remote check"))
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock(), defer=Mock(return_value={"status": "deferred"}))
        with patch.object(self.sentinel, "get_service", return_value=service):
            self.assertEqual("deferred", self.sentinel._handle_check(context)["status"])
        lease.close.assert_called_once()
        self.assertFalse(service._running)

    def test_sentinel_cancel_checkpoint_after_lease_closes_without_remote(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        lease = Mock()
        service._lease.side_effect = None
        service._lease.return_value = lease
        service._run_check = Mock(side_effect=AssertionError("must not start remote check"))
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock(side_effect=[None, RuntimeError("cancel requested")]))
        with patch.object(self.sentinel, "get_service", return_value=service), self.assertRaisesRegex(RuntimeError, "cancel requested"):
            self.sentinel._handle_check(context)
        lease.close.assert_called_once()
        self.assertFalse(service._running)

    def test_web_actions_register_without_execution_handler_or_thread(self):
        self.assertTrue(hasattr(self.sentinel, "register_actions"))
        with patch.object(threading, "Thread", side_effect=AssertionError("no request thread")):
            self.sentinel.register_actions()
        self.gateway.register_operation_handler.assert_not_called()
        values = self.gateway.register_operation_actions.call_args
        self.assertEqual("sentinel_maintenance_check", values.args[0])
        self.assertIs(self.sentinel._retry_check, values.kwargs["retry_handler"])
        self.assertIs(self.sentinel._cancel_check, values.kwargs["cancel_handler"])

    def test_sentinel_acceptance_failure_is_safe_and_does_not_write_cache_or_cancel(self):
        service = self.sentinel_service()
        self.queue.request_check.side_effect = RuntimeError("private database endpoint")
        result = service.start_check()
        self.assertFalse(result["started"])
        self.assertEqual("scheduler_store_unavailable", result["error_code"])
        self.assertNotIn("private", repr(result))
        service._lease.assert_not_called()
        service._persist_check.assert_not_called()
        self.gateway.default_operation_cancel.assert_not_called()

    def test_sentinel_cancel_only_writes_durable_cancel_request(self):
        service = self.sentinel_service()
        lease = service._pending_lease = Mock()
        service._queued_task_id = 11
        self.sentinel._SERVICE_INSTANCES["key"] = service
        self.sentinel._cancel_check({"id": 11})
        self.gateway.default_operation_cancel.assert_called_once_with({"id": 11})
        lease.close.assert_not_called()

    def test_explicit_sentinel_retry_uses_same_cache_lock_and_original_task(self):
        self.assertTrue(hasattr(self.sentinel, "_retry_check"), "cache-key retry seam absent")
        key = "a" * 64
        task = {"id": 11, "data": {"cache_key": key}, "source_system": "native_operations", "status": "failed"}
        receipt = self.sentinel._retry_check(task)
        self.assertEqual((11, 23), (receipt["task_id"], receipt["run_id"]))
        self.queue.request_check.assert_called_once()
        self.assertEqual(key, self.queue.request_check.call_args.args[0])
        self.assertEqual(11, self.operations.retry_runtime_task.call_args.args[0])
        self.gateway.submit_durable_operation.assert_not_called()

    def test_explicit_sentinel_retry_reuses_active_run_before_creating_attempt(self):
        self.assertTrue(hasattr(self.sentinel, "_retry_check"), "cache-key retry seam absent")
        self.queue.request_check.side_effect = None
        self.queue.request_check.return_value = {"accepted": True, "reused": True, "task_id": 11, "run_id": 19, "status": "queued"}
        receipt = self.sentinel._retry_check({"id": 11, "data": {"cache_key": "a" * 64}, "status": "failed"})
        self.assertEqual((11, 19), (receipt["task_id"], receipt["run_id"]))
        self.operations.retry_runtime_task.assert_not_called()

    def test_sentinel_busy_lease_defers_existing_run_without_replacement(self):
        self.role, self.open = "worker", True
        service = self.sentinel_service()
        service._lease.side_effect = None
        service._lease.return_value = None
        context = types.SimpleNamespace(run={"data": {"cache_key": self.sentinel._cache_key(service)}},
            run_id=19, task_id=11, checkpoint=Mock(), defer=Mock(return_value={"status": "deferred"}))
        with patch.object(self.sentinel, "get_service", return_value=service):
            self.assertEqual({"status": "deferred"}, self.sentinel._handle_check(context))
        context.defer.assert_called_once_with(delay_seconds=1, reason="maintenance_cache_busy")
        self.gateway.submit_durable_operation.assert_not_called()

    def test_cache_directory_configuration_is_explicit_stable_and_not_hot_switched(self):
        self.assertTrue(hasattr(self.sentinel, "configure_cache_directory"))
        with self.assertRaises(ValueError):
            self.sentinel.configure_cache_directory(Path("relative/cache"))
        self.sentinel.configure_cache_directory(Path("/fixture/stable/sentinel"))
        service = self.sentinel.get_service()
        self.assertEqual(Path("/fixture/stable/sentinel"), service.manager.cache_dir)
        self.sentinel.configure_cache_directory(Path("/fixture/stable/sentinel"))
        with self.assertRaises(RuntimeError):
            self.sentinel.configure_cache_directory(Path("/fixture/other"))

    def test_worker_scans_without_wake_event_and_keeps_same_batch_on_dispatch(self):
        self.assertTrue(hasattr(self.manual, "dispatch_pending_once"))
        batch, _ = self.create_batch()
        self.role, self.open = "worker", True
        self.manual._DISPATCH_WAKE.clear()
        observed = []
        class InlineThread:
            def __init__(self, *, target, **kwargs):
                self.target = target
            def start(self):
                self.target()
            def is_alive(self):
                return False
        with patch.object(self.manual, "_run_batch", side_effect=observed.append), patch.object(threading, "Thread", InlineThread):
            self.assertEqual(1, self.manual.dispatch_pending_once())
        self.assertEqual([batch["batch_id"]], observed)
        self.assertEqual(2, len(self.store.items(batch["batch_id"])))

    def test_stop_keeps_running_batch_reference_and_does_not_mark_batch_cancelled(self):
        self.assertTrue(hasattr(self.manual, "stop_dispatcher"))
        batch, _ = self.create_batch()
        thread = Mock()
        thread.is_alive.return_value = True
        self.manual._BATCH_THREADS[batch["batch_id"]] = thread
        self.assertFalse(self.manual.stop_dispatcher(timeout=0))
        self.assertIs(thread, self.manual._BATCH_THREADS[batch["batch_id"]])
        self.assertEqual("running", self.store.batch(batch["batch_id"])["status"])
        thread.is_alive.return_value = False
        self.assertTrue(self.manual.stop_dispatcher(timeout=0))

    def test_owner_release_outage_is_tracked_without_unmanaged_retry_thread(self):
        batch, _ = self.create_batch()
        self.role, self.open = "worker", True
        owned = self.manual._claim_batch_owner(batch["batch_id"])
        with patch.object(self.manual, "_release_batch_owner_record", side_effect=RuntimeError("store down")), \
                patch.object(threading, "Thread", side_effect=AssertionError("no detached release worker")):
            self.manual._release_batch_owner(owned)
        self.assertEqual(1, self.manual.dispatcher_status()["pending_owner_releases"])
        self.assertFalse(self.manual.stop_dispatcher(timeout=0))
        self.manual._flush_owner_releases()
        self.assertEqual(0, self.manual.dispatcher_status()["pending_owner_releases"])
        self.assertIsNone(self.store.batch(batch["batch_id"])["worker_execution_id"])

    def test_dispatcher_drain_retries_pending_owner_release_before_thread_exit(self):
        self.role, self.open = "worker", True
        captured = []
        class CapturedThread:
            def __init__(self, *, target, **kw):
                captured.append(target)
            def start(self):
                pass
            def is_alive(self):
                return True
        with patch.object(threading, "Thread", CapturedThread):
            self.assertTrue(self.manual.start_dispatcher())
        self.manual._DISPATCH_STOP.set()
        self.manual._OWNER_RELEASE_PENDING["old"] = {"worker_execution_id": "old"}
        with patch.object(self.manual, "_flush_owner_releases",
                          side_effect=self.manual._OWNER_RELEASE_PENDING.clear) as flush:
            captured[0]()
        flush.assert_called_once_with()
        self.assertEqual({}, self.manual._OWNER_RELEASE_PENDING)

    def run_original_item(self, *, saved_lease=None, expired=False):
        batch, _ = self.create_batch()
        row = self.store.batch(batch["batch_id"])
        item = self.store.items(batch["batch_id"])[0]
        item["status"] = "unknown"
        if saved_lease is not None:
            item["lease"] = saved_lease
        if expired:
            item["first_submitted_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        lease = {"id": "original-lease", "email": "fixture@example.invalid", "status": "active", "service": "openai",
                 "client_id": "fixture-client", "provider": "icloud_hme", "expires_at": None,
                 "external_ref": item["external_ref"]}
        self.api.create_lease.side_effect = None
        self.api.create_lease.return_value = lease
        self.api.get_lease.return_value = lease
        self.api.list_leases.return_value = [lease]
        with patch.object(self.manual, "_wait_import_execution", return_value=object()), \
                patch.object(self.v2, "_finish") as finish:
            self.v2._item(row, item, {"credential_ref": "fixture"}, {"api_base": "https://fixed.invalid/v2", "api_key": "fixture"})
        return item, finish

    def test_unknown_slot_reuses_original_idempotency_external_ref_and_acquisition(self):
        item, finish = self.run_original_item()
        sent = self.api.create_lease.call_args.kwargs
        self.assertEqual(item["idempotency_key"], sent["idempotency_key"])
        self.assertEqual(item["external_ref"], sent["external_ref"])
        self.assertEqual(item["acquisition_id"], finish.call_args.args[3]["acquisition_id"])
        self.assertIsNone(sent["ttl_seconds"])

    def test_saved_original_lease_is_read_and_never_reallocated(self):
        item, finish = self.run_original_item(saved_lease={"id": "original-lease"})
        self.api.create_lease.assert_not_called()
        self.api.get_lease.assert_called_once_with("original-lease", api_base="https://fixed.invalid/v2", api_key="fixture")
        self.assertEqual("original-lease", finish.call_args.args[3]["lease_id"])

    def test_expired_unknown_slot_only_queries_original_external_ref_without_post(self):
        item, finish = self.run_original_item(expired=True)
        self.api.create_lease.assert_not_called()
        self.assertEqual(item["external_ref"], self.api.list_leases.call_args.kwargs["external_ref"])
        self.assertEqual(item["acquisition_id"], finish.call_args.args[3]["acquisition_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
