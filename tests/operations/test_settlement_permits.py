"""Offline permit ownership regressions; never load private configuration or connect."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
import threading
import time
import inspect
import uuid
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from unittest.mock import patch

from core.operations import concurrency, settlement
from core.storage.operations import permits


class _Database:
    """Stateful SQL boundary for permit release/recovery, with no actual connection."""
    def __init__(self, rows):
        self.autocommit = False
        self.rows = rows
        self.writes = []
        self.last = ""
        self.params = ()
        self.rowcount = 0
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self, **_):
        return self

    def execute(self, query, params=None):
        self.last, self.params = str(query), params
        self.queries.append((self.last, params))
        self.rowcount = 0
        if "SET released_at=now()" in self.last:
            reason, permit_id, execution_id = params
            for row in self.rows:
                if row["permit_id"] == permit_id and row["execution_id"] == execution_id and not row.get("released_at"):
                    row.update(released_at=True, release_reason=reason)
                    self.rowcount += 1
        if self.last.lstrip().startswith("UPDATE"):
            self.writes.append((self.last, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if "to_regclass" in self.last:
            return ("present",)
        if "WHERE permit_id=%s AND execution_id=%s" in self.last:
            return next((row for row in self.rows if (row["permit_id"], row["execution_id"]) == tuple(self.params)), None)
        if "SELECT task_uuid FROM" in self.last:
            return {"task_uuid": "task-original"}
        if "SELECT task_type, batches, lanes" in self.last:
            return {"task_type": "", "batches": {}, "lanes": {}}
        return None


class _AdmissionDatabase(_Database):
    def __init__(self):
        super().__init__([])
        self.ticket = None
        self.claimed = False

    def transaction(self):
        return self

    def execute(self, query, params=None):
        super().execute(query, params)
        if "INSERT INTO" in self.last and "operation_execution_permits" in self.last:
            import json
            self.ticket = json.loads(params[-1]).get("settlement_ticket")
            self.claimed_before_insert = self.claimed


class SettlementPermitTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(permits.postgres, "database_url", return_value="postgresql://offline/settlement"))
        self.stack.enter_context(patch.object(permits.postgres, "schema_name", return_value="permit_original"))
        self.stack.enter_context(patch.object(permits.postgres, "connect", side_effect=AssertionError("offline: unexpected database checkout")))
        self.stack.enter_context(patch.object(permits, "_LOCAL_EXITS", set()))
        self.stack.enter_context(patch.object(concurrency, "_RELEASE_PENDING", {}))
        self.stack.enter_context(patch.object(concurrency, "_REGISTRATION_FAILED", threading.Event(), create=True))
        self.stack.enter_context(patch.object(settlement, "responsibility", return_value=None, create=True))
        self.stack.enter_context(patch.object(settlement, "release_eligible", return_value=False, create=True))
        self.stack.enter_context(patch.object(settlement, "request_release", create=True))

    def execution(self, participating=True):
        context = concurrency.ExecutionContext("permit-original", "execution-original", "operation_run:7", "plan_check",
                                               {"id": 7, "run_uuid": "run-original", "task_id": 3})
        context.settlement_ticket = {"ticket_id": "ticket-original"} if participating else None
        return context

    def test_pending_responsibility_blocks_finally_and_does_not_mark_local_exit(self):
        context = self.execution()
        released = []
        with patch.object(concurrency, "release_permit", side_effect=lambda *args, **kwargs: released.append(args) or True):
            self.assertFalse(concurrency.release_execution(context))
        self.assertFalse(context.released)
        self.assertFalse(context._stop.is_set())
        self.assertEqual([], released)
        self.assertEqual(set(), permits._LOCAL_EXITS)
        self.assertEqual({}, concurrency._RELEASE_PENDING)

    def test_registry_registration_gap_retains_participating_permit(self):
        context = self.execution()
        # A committed ticket exists even if post-commit local registration failed.
        with patch.object(concurrency, "release_permit", return_value=True):
            self.assertFalse(concurrency.release_execution(context))
        self.assertFalse(context.released)

    def test_legacy_nonparticipant_still_releases_immediately(self):
        context = self.execution(participating=False)
        released = []
        with patch.object(concurrency, "release_permit", side_effect=lambda *args, **kwargs: released.append(args) or True):
            self.assertTrue(concurrency.release_execution(context))
        self.assertTrue(context.released)
        self.assertTrue(context._stop.is_set())
        self.assertEqual([("permit-original", "execution-original", "worker_exit")], released)
        self.assertEqual(set(), permits._LOCAL_EXITS)

    def test_confirmed_participant_failure_never_enters_legacy_retry_daemon(self):
        context = self.execution()
        with patch.object(settlement, "responsibility", return_value=object(), create=True), \
                patch.object(settlement, "release_eligible", return_value=True, create=True), \
                patch.object(concurrency, "release_permit", side_effect=OSError("synthetic unavailable")), \
                patch.object(concurrency.threading, "Thread") as thread:
            self.assertFalse(concurrency.release_execution(context))
        self.assertFalse(context.released)
        self.assertEqual({}, concurrency._RELEASE_PENDING)
        self.assertEqual(set(), permits._LOCAL_EXITS)
        thread.assert_not_called()

    def row(self, **changes):
        owner = {"host_id": permits._HOST_ID, "pid": 101, "process_start": "original-start", "thread_id": -1}
        ticket = {"version": 1, "ticket_id": "ticket-original", "domain_id": "domain-original",
                  "operation_schema": "operation_original", "permit_schema": "permit_original",
                  "run_id": 7, "run_uuid": "run-original", "execution_id": "execution-original",
                  "permit_id": "permit-original", "owner": {key: value for key, value in owner.items() if key != "thread_id"}}
        return {"permit_id": "permit-original", "execution_id": "execution-original", "owner": owner,
                "metadata": {"settlement_ticket": ticket}, **changes}

    def recover(self, row, **patches):
        database = _Database([row])
        with ExitStack() as stack:
            stack.enter_context(patch.object(permits, "ensure_tables"))
            stack.enter_context(patch.object(permits.postgres, "connect", return_value=database))
            stack.enter_context(patch.object(permits, "_owner_process_start", return_value="original-start"))
            stack.enter_context(patch.object(permits.os, "getpid", return_value=101))
            stack.enter_context(patch.object(permits.os, "kill"))
            stack.enter_context(patch.object(permits, "_cleanup_blocks_permit", return_value=True, create=True))
            for key, value in patches.items():
                stack.enter_context(patch.object(permits, key, **value))
            result = permits.recover_execution_permits()
        return result, database

    def test_callback_thread_death_cannot_recover_participating_capacity(self):
        result, database = self.recover(self.row())
        self.assertEqual({"released": 0, "alive": 1, "unverified": 0}, result)
        self.assertFalse(any(row.get("released_at") for row in database.rows))

    def test_local_exit_marker_cannot_bypass_participating_responsibility(self):
        permits.mark_execution_exited("permit-original", "execution-original")
        result, database = self.recover(self.row())
        self.assertEqual(0, result["released"])
        self.assertFalse(any(row.get("released_at") for row in database.rows))

    def test_dead_process_without_cleanup_proof_retains_capacity(self):
        row = self.row()
        result, database = self.recover(row, owner_liveness={"return_value": "exited"})
        self.assertEqual(0, result["released"])
        self.assertEqual(1, result["unverified"])
        self.assertFalse(row.get("released_at"))

    def test_direct_release_cannot_bypass_durable_cleanup(self):
        row = self.row()
        database = _Database([row])
        with patch.object(permits.postgres, "connect", return_value=database), \
                patch.object(permits, "_cleanup_blocks_permit", return_value=True, create=True):
            self.assertFalse(permits.release("permit-original", "execution-original"))
        self.assertFalse(row.get("released_at"))

    def admit(self, key="operation_run:7", metadata=None, claimed=None):
        database = _AdmissionDatabase()
        claimed = claimed or {"id": 7, "task_id": 3, "run_uuid": "run-original", "execution_id": "execution-original"}
        def claim(conn, execution_id):
            self.assertIs(database, conn)
            self.assertEqual("execution-original", execution_id)
            database.claimed = True
            return claimed
        with patch.object(permits.postgres, "connect", return_value=database), \
                patch.object(permits, "ensure_tables"):
            result = permits.try_admit(
                execution_key=key, task_type="plan_check", execution_id="execution-original", run_id=7,
                batch_key="", owner={"host_id": "offline-host", "pid": 101, "process_start": "original-start"},
                metadata=metadata or {}, policy=lambda conn: ([], 11, []), claim=claim,
            )
        return result, database

    def test_ticket_has_complete_original_identity_and_is_immutable(self):
        result, database = self.admit()
        ticket = result["settlement_ticket"]
        self.assertTrue(database.claimed_before_insert)
        self.assertEqual("task-original", database.ticket["task_uuid"])
        self.assertEqual("run-original", database.ticket["run_uuid"])
        self.assertEqual("execution-original", database.ticket["execution_id"])
        self.assertEqual(result["permit_id"], database.ticket["permit_id"])
        with self.assertRaises(TypeError):
            ticket["owner"]["pid"] = 999
        self.assertNotIn("postgresql://", str(database.ticket))

    def test_caller_metadata_cannot_tag_a_legacy_nonparticipant(self):
        result, database = self.admit("registration_job:7", metadata={"settlement_ticket": {"ticket_id": "injected"}})
        self.assertIsNone(result["settlement_ticket"])
        self.assertIsNone(database.ticket)

    def test_direct_release_ack_loss_can_confirm_exact_already_released_permit(self):
        row = self.row(released_at=True)
        database = _Database([row])
        with patch.object(permits.postgres, "connect", return_value=database):
            self.assertTrue(permits.release("permit-original", "execution-original"))
            self.assertFalse(permits.release("permit-original", "different-execution"))
        self.assertEqual([], database.writes)

    def test_admission_cannot_move_permit_after_claim_changes_environment(self):
        database = _AdmissionDatabase()
        schema = ["permit_original"]
        url = ["postgresql://offline/original"]
        def claim(conn, execution_id):
            database.claimed = True
            schema[0] = "permit_changed"
            url[0] = "postgresql://offline/changed"
            return {"id": 7, "task_id": 3, "task_uuid": "task-original", "run_uuid": "run-original"}
        with patch.object(permits.postgres, "schema_name", side_effect=lambda: schema[0]), \
                patch.object(permits.postgres, "database_url", side_effect=lambda: url[0]), \
                patch.object(permits.postgres, "connect", return_value=database), \
                patch.object(permits, "ensure_tables"):
            result = permits.try_admit(
                execution_key="operation_run:7", task_type="plan_check", execution_id="execution-original", run_id=7,
                batch_key="", owner={"pid": 101}, metadata={}, policy=lambda conn: ([], 11, []), claim=claim,
            )
        insert_queries = [query for query, _ in database.queries if "INSERT INTO" in query and "operation_execution_permits" in query]
        self.assertEqual(1, len(insert_queries))
        self.assertIn('"permit_original"."operation_execution_permits"', insert_queries[0])
        self.assertEqual("permit_original", result["settlement_domain"].permit_schema)
        self.assertEqual("postgresql://offline/original", result["settlement_domain"].database_url)

    def test_two_finalizers_release_exact_participant_once(self):
        context = self.execution()
        entered, resume = threading.Event(), threading.Event()
        releases = []
        def release(*args, **kwargs):
            releases.append(args)
            entered.set()
            self.assertTrue(resume.wait(1))
            return True
        results = []
        with patch.object(settlement, "responsibility", return_value=object()), \
                patch.object(settlement, "release_eligible", return_value=True), \
                patch.object(concurrency, "release_permit", side_effect=release):
            first = threading.Thread(target=lambda: results.append(concurrency.release_execution(context)))
            second = threading.Thread(target=lambda: results.append(concurrency.release_execution(context)))
            first.start()
            self.assertTrue(entered.wait(1))
            second.start()
            resume.set()
            first.join(1)
            second.join(1)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual([False, True], sorted(results))
        self.assertEqual(1, len(releases))

    def test_legacy_retry_pending_is_reported_and_blocks_clean_stop(self):
        context = self.execution(participating=False)
        concurrency._RELEASE_PENDING[("permit-original", "execution-original")] = (context, "worker_exit")
        status = getattr(concurrency, "release_runtime_status", lambda: {"pending": 0, "inflight": 0, "alive": False})()
        self.assertEqual(1, status["pending"])
        stop = getattr(concurrency, "stop_release_runtime", lambda deadline: True)
        self.assertFalse(stop(time.monotonic() - 1))

    def test_participating_release_propagates_absolute_deadline_to_checkout(self):
        row = self.row()
        database = _Database([row])
        deadline = time.monotonic() + 1
        checkouts = []
        def connect(*args, **kwargs):
            checkouts.append(kwargs.get("deadline"))
            return database
        # The probe still exercises the pre-deadline implementation so RED is
        # the lost checkout bound, rather than a missing-keyword TypeError.
        options = {"deadline": deadline} if "deadline" in inspect.signature(permits.release).parameters else {}
        with patch.object(permits.postgres, "connect", side_effect=connect), \
                patch.object(permits, "_ticket_liveness", return_value="exited"), \
                patch.object(permits, "_cleanup_blocks_permit", return_value=False):
            self.assertTrue(permits.release("permit-original", "execution-original", **options))
        self.assertEqual([deadline], checkouts)

    def test_release_deadline_bounds_waiting_for_another_finalizer(self):
        context = self.execution()
        locked = threading.Event()
        def holder():
            with context._release_lock:
                locked.set()
                threading.Event().wait(.25)
        thread = threading.Thread(target=holder)
        thread.start()
        self.assertTrue(locked.wait(1))
        started = time.monotonic()
        try:
            result = concurrency.release_execution(context, deadline=started + .02)
            elapsed = time.monotonic() - started
        finally:
            thread.join(1)
        self.assertFalse(result)
        self.assertLess(elapsed, .15)

    def test_exhausted_responsibility_capacity_blocks_before_database_claim(self):
        claims = []
        @contextmanager
        def reservation():
            yield False
        def admit(**kwargs):
            claims.append(kwargs)
            return {"blocked_by": []}
        with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
                patch.object(settlement, "reserve_admission", reservation, create=True), \
                patch.object(permits, "current_owner", return_value={"pid": 101}), \
                patch.object(permits, "try_admit", side_effect=admit):
            result = concurrency.try_admit_and_claim(execution_key="operation_run:7", task_type="plan_check",
                                                     claim=lambda conn, execution_id: {})
        self.assertEqual([], claims)
        self.assertEqual(("settlement_capacity",), result.blocked_by)

    def test_postcommit_registration_failure_preserves_exact_context_and_stops_admission(self):
        @contextmanager
        def reservation():
            yield True
        # This test starts after reservation and database admission succeeded.
        domain = SimpleNamespace(database_url="postgresql://offline/original", permit_schema="permit_original",
                                 operation_schema="operation_original", domain_id="domain-original")
        admitted = {"permit_id": "permit-original", "claimed_run": {"id": 7}, "policy_revision": 11,
                    "settlement_ticket": {"permit_id": "permit-original", "execution_id": "execution-original"},
                    "settlement_domain": domain}
        with patch("core.runtime.execution_access.execution_allowed", return_value=True), \
                patch.object(settlement, "reserve_admission", reservation), \
                patch("core.runtime.process.get_runtime_context", return_value=None), \
                patch.object(permits, "current_owner", return_value={"pid": 101}), \
                patch.object(permits, "try_admit", return_value=admitted), \
                patch.object(settlement, "register_execution", side_effect=RuntimeError("synthetic registration failure")):
            with self.assertRaises(concurrency.ConcurrencyStoreUnavailable) as error:
                concurrency.try_admit_and_claim(execution_key="operation_run:7", task_type="plan_check",
                                                execution_id="execution-original", claim=lambda conn, eid: {})
            context = error.exception.execution_context
            try:
                following = concurrency.try_admit_and_claim(execution_key="operation_run:8", task_type="plan_check",
                                                            claim=lambda conn, eid: {})
            except concurrency.ConcurrencyStoreUnavailable:
                following = concurrency.AdmissionResult(blocked_by=("reentered_database_claim",))
        self.assertEqual("permit-original", context.permit_id)
        self.assertEqual("postgresql://offline/original", context._domain_url)
        self.assertFalse(context.released)
        self.assertEqual(("settlement_registration",), following.blocked_by)

    def test_cross_database_recovery_never_relabels_original_ticket_domain(self):
        from core.storage.operations import settlements
        with patch.object(settlements, "cleanup_blocks_permit", return_value=False):
            blocked = permits._cleanup_blocks_permit(
                self.row(), conn=object(), database_url="postgresql://offline/different", schema="permit_original",
            )
        self.assertTrue(blocked)

    def test_registration_failure_latch_blocks_clean_stop(self):
        concurrency._REGISTRATION_FAILED.set()
        self.assertFalse(concurrency.stop_release_runtime(time.monotonic()))

    def test_legacy_carrier_is_tracked_until_physical_thread_exit(self):
        returned, leave = threading.Event(), threading.Event()
        class ImmediateWait:
            def wait(self, _):
                return False
        def carrier():
            concurrency._retry_releases()
            returned.set()
            leave.wait(1)
        thread = threading.Thread(target=carrier)
        with patch.object(concurrency, "_RELEASE_RETRY_THREAD", thread), \
                patch.object(concurrency.threading, "Event", ImmediateWait):
            thread.start()
            try:
                self.assertTrue(returned.wait(1))
                self.assertTrue(concurrency.release_runtime_status()["alive"])
                self.assertFalse(concurrency.stop_release_runtime(time.monotonic()))
            finally:
                leave.set()
                thread.join(1)


class PermitRenewalResponsibilityTests(unittest.TestCase):
    def test_blocked_original_heartbeat_prevents_settlement_and_shutdown_completion(self):
        from core.operations.settlement_contracts import seal_intent
        entered, leave = threading.Event(), threading.Event()
        actual_event = threading.Event
        class FastEvent(actual_event):
            def wait(self, timeout=None):
                return super().wait(.001 if timeout == 10 else timeout)
        def renew(*args, **kwargs):
            entered.set()
            leave.wait(2)
            return True
        context = concurrency.ExecutionContext("heartbeat-permit", "heartbeat-execution", "operation_run:7",
            "plan_check", {"id": 7}, domain_schema="offline", _domain_url="offline",
            settlement_ticket={"permit_id": "heartbeat-permit", "execution_id": "heartbeat-execution"})
        self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
        self.assertTrue(all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status())
        stack = ExitStack()

        def restore_original_scope():
            self.assertTrue(context.released, "original heartbeat responsibility remains owned")
            renewal = getattr(context, "_permit_renewal", None)
            self.assertTrue(renewal is None or (renewal.release_confirmed and not renewal.thread.is_alive()))
            stack.close()

        self.addCleanup(restore_original_scope)
        # This test advances its own original responsibility manually.
        # A previous clean stop must not fence this independent fixture.
        stack.enter_context(patch.object(settlement, "_THREAD", None))
        stack.enter_context(patch.object(settlement, "_STOP", False))
        stack.enter_context(patch.object(settlement, "_REGISTRY", {}))
        stack.enter_context(patch.object(settlement, "_EXPECTED", set()))
        stack.enter_context(patch.object(settlement, "_REGISTRY_ERROR", ""))
        stack.enter_context(patch.object(settlement, "_ADMISSION", None))
        stack.enter_context(patch.object(settlement, "_DEADLINE", None))
        stack.enter_context(patch.object(concurrency, "_PERMIT_RENEWALS", {}, create=True))
        stack.enter_context(patch.object(concurrency, "validate_execution", return_value=True))
        stack.enter_context(patch.object(concurrency.permits, "heartbeat", return_value=True))
        stack.enter_context(patch.object(concurrency, "heartbeat_permit", side_effect=renew))
        stack.enter_context(patch.object(concurrency, "release_permit", return_value=True))
        stack.enter_context(patch.object(permits.postgres, "connect", side_effect=AssertionError("offline checkout forbidden")))
        stack.enter_context(patch.object(concurrency.threading, "Event", FastEvent))
        settlement.register_execution(context, context.settlement_ticket)
        try:
            with concurrency.execution_scope(context):
                self.assertTrue(settlement.callback_started(context))
                self.assertTrue(entered.wait(1))
                intent = seal_intent(kind="terminal", origin=context.settlement_ticket, payload={"status": "success"})
                settlement.settle(context, intent, lambda frozen, deadline: {"transition_id": frozen.transition_id})
            settlement.callback_exited(context)
            settlement.request_release(context)
            with patch.object(settlement, "_DEADLINE", time.monotonic() + .02):
                settlement._progress(settlement.responsibility(context))
            self.assertFalse(context.released)
            self.assertEqual(1, settlement.active_counts()["resource_pending"])
            self.assertFalse(concurrency.stop_release_runtime(time.monotonic() + .02))
            self.assertFalse(settlement.release_eligible(context))
            leave.set()
            context._permit_renewal.thread.join(1)
            item = settlement.responsibility(context)
            item.next_attempt = 0.0
            with patch.object(settlement, "_DEADLINE", time.monotonic() + .1):
                settlement._progress(item)
            self.assertTrue(context.released)
            self.assertEqual(0, settlement.active_counts()["registered"])
            self.assertEqual({}, concurrency._PERMIT_RENEWALS)
        finally:
            leave.set()
            for thread in threading.enumerate():
                if thread.name == "execution-permit-heartbea":
                    thread.join(1)

    def test_legacy_recovery_cannot_release_while_local_renewal_is_in_io(self):
        entered, leave = threading.Event(), threading.Event()
        actual_event = threading.Event
        class FastEvent(actual_event):
            def wait(self, timeout=None):
                return super().wait(.001 if timeout == 10 else timeout)
        def renew(*args, **kwargs):
            entered.set()
            leave.wait(2)
            return True
        context = concurrency.ExecutionContext("legacy-heartbeat", "legacy-execution", "legacy:7",
            "plan_check", {"id": 7}, domain_schema="offline", _domain_url="offline")
        row = {"permit_id": context.permit_id, "execution_id": context.execution_id,
               "owner": {"host_id": "synthetic"}, "metadata": {}}
        database = _Database([row])
        with patch.object(concurrency, "_PERMIT_RENEWALS", {}, create=True), \
                patch.object(concurrency, "validate_execution", return_value=True), \
                patch.object(concurrency.permits, "heartbeat", return_value=True), \
                patch.object(concurrency, "heartbeat_permit", side_effect=renew), \
                patch.object(concurrency.threading, "Event", FastEvent):
            try:
                with concurrency.execution_scope(context):
                    self.assertTrue(entered.wait(1))
                with patch.object(permits, "ensure_tables"), \
                        patch.object(permits.postgres, "connect", return_value=database), \
                        patch.object(permits, "owner_liveness", return_value="exited"):
                    recovered = permits.recover_execution_permits()
                self.assertEqual(0, recovered["released"])
                self.assertFalse(row.get("released_at"))
            finally:
                leave.set()
                for thread in threading.enumerate():
                    if thread.name == "execution-permit-legacy-h":
                        thread.join(1)


class NativePermitHandoffFaultTests(unittest.TestCase):
    """Real gateway/barriers/registry, with faults only at repository boundaries."""
    def setUp(self):
        from core.operations import task_gateway
        from core.storage.operations import settlements
        self.gateway = task_gateway
        self.stack = ExitStack()
        self.addCleanup(self.restore_original_scope)
        self.stack.enter_context(patch.object(permits.postgres, "connect", side_effect=AssertionError("offline checkout forbidden")))
        self.stack.enter_context(patch.object(permits.postgres, "database_url", side_effect=AssertionError("offline config forbidden")))
        self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
        self.assertTrue(all(value == 0 for value in settlement.active_counts().values()), settlement.runtime_status())
        # This fixture drives real callbacks and exact cleanup without a carrier.
        self.stack.enter_context(patch.object(settlement, "_THREAD", None))
        self.stack.enter_context(patch.object(settlement, "_STOP", False))
        self.stack.enter_context(patch.object(settlement, "_DEADLINE", None))
        self.stack.enter_context(patch.object(settlement, "_ADMISSION", None))
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        self.stack.enter_context(patch("core.runtime.execution_access.execution_allowed", return_value=True))
        self.stack.enter_context(patch.object(concurrency, "validate_execution", return_value=True))
        self.stack.enter_context(patch.object(permits, "heartbeat", return_value=True))
        self.submissions = []
        self.receipts = {}
        self.submit_blocked = True
        self.submit_ack_lost = False
        self.permit_fail_before_commit = 0
        self.permit_ack_lost = False
        self.permit_released = False
        self.permit_commits = 0
        self.release_attempts = []
        self.stack.enter_context(patch.object(settlements, "submit_intent", side_effect=self.submit))
        self.stack.enter_context(patch.object(concurrency, "release_permit", side_effect=self.release))
        identifier = uuid.uuid4().hex
        self.execution = concurrency.ExecutionContext(
            identifier, "execution-" + identifier, "operation_run:7", "plan_check",
            {"id": 7, "task_id": 8, "run_uuid": "run-" + identifier, "task_type": "plan_check"},
            domain_schema="offline", _domain_url="offline",
        )
        self.execution.settlement_ticket = {
            "permit_id": identifier, "execution_id": self.execution.execution_id,
            "run_id": 7, "task_id": 8, "run_uuid": self.execution.claimed_run["run_uuid"],
            "ticket_id": "ticket-" + identifier,
        }
        settlement.register_execution(self.execution, self.execution.settlement_ticket)
        self.addCleanup(self.close_exact_responsibility)

    def restore_original_scope(self):
        execution = getattr(self, "execution", None)
        if execution is not None:
            self.assertTrue(execution.released, "original native responsibility remains owned")
            renewal = getattr(execution, "_permit_renewal", None)
            self.assertTrue(renewal is None or (renewal.release_confirmed and not renewal.thread.is_alive()))
        self.stack.close()

    def submit(self, intent, *, domain=None, deadline=None):
        self.submissions.append(intent)
        if intent.transition_id in self.receipts:
            return self.receipts[intent.transition_id]
        if self.submit_blocked:
            raise OSError("synthetic repository unavailable")
        receipt = {"transition_id": intent.transition_id, "request_digest": intent.request_digest,
                   "actual_result": {"id": 7, "status": "queued" if intent.kind == "defer" else intent.payload["status"]}}
        self.receipts[intent.transition_id] = receipt
        if self.submit_ack_lost:
            self.submit_ack_lost = False
            raise OSError("synthetic committed transition ACK lost")
        return receipt

    def release(self, permit_id, execution_id, *args, **kwargs):
        self.assertEqual((self.execution.permit_id, self.execution.execution_id), (permit_id, execution_id))
        self.release_attempts.append((permit_id, execution_id))
        if self.permit_fail_before_commit:
            self.permit_fail_before_commit -= 1
            raise OSError("synthetic permit failure before commit")
        if not self.permit_released:
            self.permit_released = True
            self.permit_commits += 1
            if self.permit_ack_lost:
                self.permit_ack_lost = False
                raise OSError("synthetic committed permit ACK lost")
        return True

    def progress_until(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            settlement._progress(settlement.responsibility(self.execution))
            time.sleep(.005)
        self.assertTrue(predicate(), settlement.runtime_status())

    def close_exact_responsibility(self):
        # Never erase pending state. Repair only the injected repository faults,
        # then settle the same registered execution before restoring patches.
        self.submit_blocked = False
        self.permit_fail_before_commit = 0
        item = settlement.responsibility(self.execution)
        if item.intent is None:
            self.gateway.rollback_admission(self.execution, reason="offline_test_unstarted_cleanup")
        settlement.request_release(self.execution)
        self.progress_until(lambda: self.execution.released)
        renewal = getattr(self.execution, "_permit_renewal", None)
        self.assertTrue(renewal is None or renewal.release_confirmed)

    def dispatch(self, mode, handler):
        execution = self.execution
        future = Future()
        owner = self
        class Carrier:
            def available_slots(self):
                return 1
            def try_submit(self, callback, run_id):
                if mode == "submit_error":
                    raise RuntimeError("synthetic executor submission failed")
                if mode == "rejected":
                    return None
                owner.dispatched_callback = lambda: callback(run_id)
                return future
        carrier = Carrier()
        store = SimpleNamespace(list_dispatchable_runs=lambda **kwargs: [execution.claimed_run])
        with patch.object(self.gateway, "_operation", return_value=store), \
                patch.object(self.gateway, "admit_operation_run", return_value=concurrency.AdmissionResult(execution)), \
                patch.object(concurrency, "order_dispatch_candidates", side_effect=lambda rows: rows):
            result = self.gateway._dispatch_registered_group(
                {"plan_check": (handler, None)}, {}, carrier, limit=1,
            )
        return result, future

    def test_terminal_pending_survives_outer_finally_completed_future_retry_and_local_exit(self):
        callback_calls = []
        def callback(run_id):
            callback_calls.append(run_id)
            context = self.gateway.OperationHandlerContext(
                self.execution.claimed_run, execution_id=self.execution.execution_id,
            )
            context.finish(status="success", result_summary={"original": {"value": 1}})
        _, future = self.dispatch("accepted", callback)
        with self.assertRaises(self.gateway.OperationSettlementPending):
            self.dispatched_callback()
        frozen = settlement.responsibility(self.execution).intent
        future.set_exception(self.gateway.OperationSettlementPending("original callback awaits persistence"))
        permits.mark_execution_exited(self.execution.permit_id, self.execution.execution_id)
        self.assertFalse(concurrency.release_execution(self.execution))
        settlement._progress(settlement.responsibility(self.execution))
        row = {"permit_id": self.execution.permit_id, "execution_id": self.execution.execution_id,
               "owner": {"host_id": permits._HOST_ID, "pid": 101, "process_start": "original"},
               "metadata": {"settlement_ticket": {**self.execution.settlement_ticket,
                            "owner": {"host_id": permits._HOST_ID, "pid": 101, "process_start": "original"}}}}
        with patch.object(permits, "ensure_tables"), \
                patch.object(permits.postgres, "connect", return_value=_Database([row])), \
                patch.object(permits, "owner_liveness", return_value="alive"):
            recovered = permits.recover_execution_permits()
        self.assertEqual(0, recovered["released"])
        self.assertEqual([], self.release_attempts)
        self.assertFalse(self.execution.released)
        self.assertEqual([7], callback_calls)
        self.submit_blocked = False
        self.progress_until(lambda: self.execution.released)
        self.assertEqual(1, len(self.receipts))
        self.assertTrue(all(intent is frozen for intent in self.submissions))
        self.assertEqual(1, self.permit_commits)
        permits.clear_execution_exit(self.execution.permit_id, self.execution.execution_id)

    def test_resource_failure_then_permit_failure_and_commit_ack_loss_closes_once(self):
        allow_cleanup = threading.Event()
        class Resource:
            release_confirmed = False
            def release(resource, *, deadline=None):
                if not allow_cleanup.is_set():
                    return False
                resource.release_confirmed = True
                return True
        resource = Resource()
        self.submit_blocked = False
        self.permit_fail_before_commit = 1
        self.permit_ack_lost = True
        callback_calls = []
        def callback():
            callback_calls.append(1)
            context = self.gateway.OperationHandlerContext(self.execution.claimed_run, execution_id=self.execution.execution_id)
            context.register_cleanup(resource, key="exact-resource:7", blocking=True)
            context.finish(status="success")
        try:
            self.gateway.execute_admitted(self.execution, callback)
            item = settlement.responsibility(self.execution)
            settlement._progress(item)
            self.assertEqual(1, settlement.active_counts()["resource_pending"])
            self.assertEqual([], self.release_attempts)
            self.assertFalse(concurrency.release_execution(self.execution))
            allow_cleanup.set()
            self.progress_until(lambda: self.execution.released)
            self.assertEqual([1], callback_calls)
            self.assertEqual(1, len(self.receipts))
            self.assertEqual(1, self.permit_commits)
            self.assertEqual(3, len(self.release_attempts))
            self.assertTrue(resource.release_confirmed)
        finally:
            allow_cleanup.set()

    def test_rollback_failure_then_commit_ack_loss_fences_cancelled_future_callback(self):
        callback_calls = []
        _, future = self.dispatch("accepted", lambda run_id: callback_calls.append(run_id))
        with self.assertLogs("concurrent.futures", level="ERROR"):
            self.assertTrue(future.cancel())
        item = settlement.responsibility(self.execution)
        self.assertEqual("unstarted_rollback", item.intent.payload["subtype"])
        self.assertEqual("submission_cancelled", item.intent.payload["reason"])
        self.assertFalse(self.execution.released)
        self.assertEqual([], self.release_attempts)
        self.submit_blocked = False
        self.submit_ack_lost = True
        self.assertIsNone(self.dispatched_callback())
        self.progress_until(lambda: self.execution.released)
        self.assertEqual([], callback_calls)
        self.assertEqual(1, len(self.receipts))
        self.assertEqual(1, self.permit_commits)
        self.assertEqual(1, len({intent.transition_id for intent in self.submissions}))

    def test_callback_start_wins_against_cancel_and_unstarted_rollback(self):
        entered, leave = threading.Event(), threading.Event()
        calls = []
        self.submit_blocked = False
        def callback():
            calls.append(1)
            entered.set()
            self.assertTrue(leave.wait(2))
            context = self.gateway.OperationHandlerContext(self.execution.claimed_run, execution_id=self.execution.execution_id)
            context.finish(status="cancelled")
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.gateway.execute_admitted, self.execution, callback)
            try:
                self.assertTrue(entered.wait(1))
                with self.assertRaises(self.gateway.OperationSettlementConflict):
                    self.gateway.rollback_admission(self.execution, reason="submission_cancelled")
                self.assertEqual([], self.submissions)
                self.assertFalse(concurrency.release_execution(self.execution))
            finally:
                leave.set()
            future.result(timeout=2)
        self.progress_until(lambda: self.execution.released)
        self.assertEqual([1], calls)
        self.assertEqual({"terminal"}, {intent.kind for intent in self.submissions})
        self.assertEqual(1, len(self.receipts))

    def test_paused_admission_and_executor_error_share_unstarted_barrier(self):
        for mode in ("paused", "submit_error", "rejected"):
            with self.subTest(mode=mode):
                # Each case gets an actual separately registered identity; no
                # pending registry entries are replaced to advance the loop.
                if settlement.responsibility(self.execution).released:
                    self.execution = concurrency.ExecutionContext(
                        uuid.uuid4().hex, uuid.uuid4().hex, "operation_run:7", "plan_check",
                        {"id": 7, "task_id": 8, "task_type": "plan_check"}, domain_schema="offline", _domain_url="offline",
                    )
                    self.execution.settlement_ticket = {"permit_id": self.execution.permit_id,
                        "execution_id": self.execution.execution_id, "run_id": 7, "task_id": 8}
                    settlement.register_execution(self.execution, self.execution.settlement_ticket)
                    self.permit_released = False
                calls = []
                self.submit_blocked = False
                if mode == "paused":
                    with patch("core.runtime.execution_access.execution_allowed", return_value=False):
                        self.gateway.execute_admitted(self.execution, lambda: calls.append(1))
                elif mode == "submit_error":
                    with self.assertLogs(self.gateway.logger, level="ERROR"):
                        self.dispatch(mode, lambda run_id: calls.append(run_id))
                else:
                    self.dispatch(mode, lambda run_id: calls.append(run_id))
                item = settlement.responsibility(self.execution)
                self.assertEqual("unstarted_rollback", item.intent.payload["subtype"])
                self.assertTrue(item.callback_exited)
                self.assertFalse(item._callback_started)
                self.progress_until(lambda: self.execution.released)
                self.assertEqual([], calls)


if __name__ == "__main__":
    unittest.main()
