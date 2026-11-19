"""S14 deterministic coordinator faults; no DB/config/remote side effects.

Psycopg exceptions are injected at the local repository seam. These are offline
classification/retention tests and never claim actual PostgreSQL role coverage.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import os
import uuid
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psycopg
from psycopg import errors

from core.operations import concurrency, settlement
from core.operations.settlement_contracts import (
    OperationSettlementConflict, OperationSettlementFenced, OperationSettlementPending, SettlementDomain, seal_intent,
)
from core.runtime.readiness import component_ready
from core.storage import postgres
from core.storage.operations import common, settlements


class _UnknownSqlstate(psycopg.DatabaseError):
    sqlstate = "ZZ999"


class _Admission:
    def __init__(self):
        self.blocked = set()

    def block(self, reason):
        self.blocked.add(reason)

    def unblock(self, reason):
        self.blocked.discard(reason)

    def reasons(self):
        return tuple(self.blocked)


class _Clock:
    def __init__(self):
        self.value = 1000.0

    def monotonic(self):
        return self.value


class PersistentSettlementFaultTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.clock = _Clock()
        self.admission = _Admission()
        for field, value in (
            ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
            ("_DOMAINS", {}), ("_ADMISSION", self.admission), ("_DEADLINE", None),
        ):
            self.stack.enter_context(patch.object(settlement, field, value))
        self.stack.enter_context(patch.object(settlement, "time", self.clock))
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("S14 offline DB checkout forbidden")))
        self.stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("S14 offline configuration forbidden")))
        self.stack.enter_context(patch.object(concurrency, "release_permit", return_value=True))
        self.execution = concurrency.ExecutionContext("s14-permit", "s14-execution", "operation_run:7",
            "plan_check", {"id": 7, "task_id": 8}, domain_schema="s14_offline", _domain_url="s14_offline")
        self.ticket = {"permit_id": self.execution.permit_id, "execution_id": self.execution.execution_id,
                       "run_id": 7, "task_id": 8}
        self.execution.settlement_ticket = self.ticket
        settlement.register_execution(self.execution, self.ticket)
        self.intent = seal_intent(kind="terminal", origin=self.ticket,
                                  payload={"status": "success", "result_summary": {"original": "confirmed"}})
        self.healthy = False
        self.release_error = None
        self.resource = None
        self.calls = []
        self.error = errors.InsufficientPrivilege("synthetic private DSN password=do-not-export")
        self.addCleanup(self.heal_exact_original)

    def submit(self, intent, deadline):
        self.calls.append((intent, self.clock.monotonic(), deadline))
        if not self.healthy:
            raise self.error
        return {"transition_id": intent.transition_id, "request_digest": intent.request_digest,
                "actual_result": {"status": "success"}}

    def fail_once(self):
        settlement.callback_started(self.execution)
        with self.assertRaises(OperationSettlementPending):
            settlement.settle(self.execution, self.intent, self.submit)
        settlement.callback_exited(self.execution)
        settlement.request_release(self.execution)
        return settlement.responsibility(self.execution)

    def heal_exact_original(self):
        # Restore only the injected repository, then confirm the same immutable
        # intent and gated permit. Never drop pending membership to clean up.
        self.healthy = True
        self.release_error = None
        if self.resource is not None:
            self.resource.healthy = True
        item = settlement.responsibility(self.execution)
        if item.intent is None:
            settlement.callback_started(self.execution)
            settlement.settle(self.execution, self.intent, self.submit)
            settlement.callback_exited(self.execution)
        else:
            settlement.settle(self.execution, self.intent, self.submit)
        settlement.request_release(self.execution)
        self.clock.value = max(self.clock.value, item.next_attempt) + 1
        settlement._progress(item)
        self.assertTrue(self.execution.released)
        self.assertEqual(set(), settlement._EXPECTED)

    def test_permission_error_retains_distinct_blocked_reason_and_sanitized_status(self):
        self.error = errors.InsufficientPrivilege("synthetic postgresql://private:secret@invalid/db")
        item = self.fail_once()
        self.assertEqual("42501", self.error.sqlstate)
        self.assertEqual("settlement_storage_permission_denied", item.error_code)
        self.assert_retained_and_sanitized()

    def test_authentication_error_retains_distinct_blocked_reason_and_sanitized_status(self):
        self.error = errors.InvalidPassword("synthetic password=do-not-export")
        item = self.fail_once()
        self.assertEqual("28P01", self.error.sqlstate)
        self.assertEqual("settlement_storage_authentication_failed", item.error_code)
        self.assert_retained_and_sanitized()

    def test_unknown_sqlstate_retains_nontransient_blocked_reason(self):
        self.error = _UnknownSqlstate("synthetic raw SQL parameters: token=do-not-export")
        item = self.fail_once()
        self.assertEqual("ZZ999", self.error.sqlstate)
        self.assertEqual("settlement_storage_sqlstate_unknown", item.error_code)
        self.assert_retained_and_sanitized()

    def assert_retained_and_sanitized(self):
        item = settlement.responsibility(self.execution)
        self.assertIs(item.intent, self.intent)
        self.assertEqual(1, item.attempts)
        self.assertFalse(self.execution.released)
        self.assertFalse(settlement.release_eligible(self.execution))
        self.assertFalse(concurrency.release_execution(self.execution))
        self.assertIn("settlement", self.admission.blocked)
        status = settlement.runtime_status()
        self.assertFalse(component_ready("settlement", status))
        self.assertEqual(1, status["counts"]["registered"])
        self.assertEqual(1, status["counts"]["unpersisted"])
        serialized = json.dumps(status)
        for private in ("postgresql://", "do-not-export", "private:secret", "raw SQL", "password=", "token="):
            self.assertNotIn(private, serialized)
        for _ in range(1200):
            self.clock.value += .05
            settlement._progress(item)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(1, item.attempts)

    def test_persistent_authorization_error_does_not_retry_forever_as_transient_unavailable(self):
        item = self.fail_once()
        # A full synthetic minute exceeds all prior exponential retry delays.
        # Calling the real carrier decision repeatedly must not re-submit a
        # nontransient authorization failure until explicit remediation.
        for _ in range(1200):
            self.clock.value += .05
            settlement._progress(item)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(1, item.attempts)
        self.assert_retained_and_sanitized()

    def test_transient_disconnect_retry_counts_and_backoff_are_bounded_and_preserve_intent(self):
        self.error = errors.ConnectionFailure("synthetic transient connection failure")
        item = self.fail_once()
        previous_attempts = 1
        for _ in range(10):
            due = item.next_attempt
            self.assertGreaterEqual(due - self.clock.value, .05)
            self.assertLessEqual(due - self.clock.value, 5.0 + 1e-9)
            self.clock.value = due - .001
            settlement._progress(item)
            self.assertEqual(previous_attempts, item.attempts)
            self.clock.value = due
            settlement._progress(item)
            previous_attempts += 1
            self.assertEqual(previous_attempts, item.attempts)
            self.assertEqual(previous_attempts, len(self.calls))
            self.assertIs(item.intent, self.intent)
            self.assertFalse(self.execution.released)
        self.assertAlmostEqual(5.0, item.next_attempt - self.clock.value)
        self.assertTrue(all(intent is self.intent for intent, _, _ in self.calls))
        self.assertTrue(all(deadline >= started for _, started, deadline in self.calls))

    def test_explicit_same_intent_remediation_clears_block_without_business_replay(self):
        item = self.fail_once()
        self.healthy = True
        receipt = settlement.settle(self.execution, self.intent, self.submit)
        self.assertEqual(self.intent.transition_id, receipt["transition_id"])
        self.assertIs(item.intent, self.intent)
        self.assertEqual("", item.error_code)
        self.assertEqual(2, len(self.calls))
        self.assertFalse(self.execution.released)
        settlement._progress(item)
        self.assertTrue(self.execution.released)
        self.assertEqual(2, len(self.calls))

    def test_persistent_cleanup_permission_failure_blocks_without_repeating_delete(self):
        self.healthy = True
        class Resource:
            release_confirmed = False
            healthy = False
            calls = 0
            def release(resource, *, deadline=None):
                resource.calls += 1
                if not resource.healthy:
                    raise errors.InsufficientPrivilege("synthetic private cleanup SQL token=do-not-export")
                resource.release_confirmed = True
                return True
        self.resource = Resource()
        settlement.register_cleanup(self.execution, self.resource, key="s14-exact-resource")
        settlement.callback_started(self.execution)
        settlement.settle(self.execution, self.intent, self.submit)
        settlement.callback_exited(self.execution)
        settlement.request_release(self.execution)
        item = settlement.responsibility(self.execution)
        settlement._progress(item)
        self.assertEqual("settlement_storage_permission_denied", item.error_code)
        self.assertEqual(1, item.attempts)
        for _ in range(1200):
            self.clock.value += .05
            settlement._progress(item)
        self.assertEqual(1, self.resource.calls)
        self.assertFalse(self.execution.released)
        self.assertEqual(1, settlement.active_counts()["resource_pending"])
        self.assertEqual(1, len(self.calls))
        self.assertIs(item.intent, self.intent)
        self.resource.healthy = True
        settlement.settle(self.execution, self.intent, self.submit)
        self.assertEqual(2, self.resource.calls)
        self.assertTrue(self.execution.released)
        self.assertEqual(1, len(self.calls))

    def test_persistent_permit_permission_failure_does_not_enter_broad_release_retry(self):
        self.healthy = True
        attempts = []
        def release(*args, **kwargs):
            attempts.append((args, kwargs))
            if self.release_error is not None:
                raise self.release_error
            return True
        self.stack.enter_context(patch.object(concurrency.permits, "release", side_effect=release))
        # Keep the actual concurrency adapter so its exception/handoff behavior
        # is tested instead of replacing it with a coordinator-only fake.
        self.stack.enter_context(patch.object(concurrency, "release_permit", wraps=_ORIGINAL_RELEASE_PERMIT))
        self.release_error = errors.InsufficientPrivilege("synthetic permit SQL password=do-not-export")
        settlement.callback_started(self.execution)
        settlement.settle(self.execution, self.intent, self.submit)
        settlement.callback_exited(self.execution)
        settlement.request_release(self.execution)
        item = settlement.responsibility(self.execution)
        settlement._progress(item)
        self.assertEqual("settlement_storage_permission_denied", item.error_code)
        self.assertEqual(1, item.attempts)
        for _ in range(1200):
            self.clock.value += .05
            settlement._progress(item)
        self.assertEqual(1, len(attempts))
        self.assertFalse(self.execution.released)
        self.assertIsNotNone(item.receipt)
        self.assertEqual(1, settlement.active_counts()["permit_pending"])
        self.release_error = None
        settlement.settle(self.execution, self.intent, self.submit)
        self.assertEqual(2, len(attempts))
        self.assertTrue(self.execution.released)
        self.assertEqual(1, len(self.calls))

    def test_conflicting_terminal_and_original_identity_are_rejected_without_new_submit(self):
        self.fail_once()
        attempts = len(self.calls)
        changed = seal_intent(kind="terminal", origin=self.ticket, payload={"status": "failed"})
        with self.assertRaises(OperationSettlementConflict):
            settlement.settle(self.execution, changed, self.submit)
        self.assertEqual(attempts, len(self.calls))
        other = SimpleNamespace(permit_id="unregistered-permit", execution_id=self.execution.execution_id)
        with self.assertRaises(OperationSettlementFenced):
            settlement.settle(other, self.intent, self.submit)
        self.assertEqual(attempts, len(self.calls))
        self.assertIs(settlement.responsibility(self.execution).intent, self.intent)
        self.assertFalse(self.execution.released)


_ORIGINAL_RELEASE_PERMIT = concurrency.release_permit


class PersistentDomainScannerFaultTests(unittest.TestCase):
    def test_permission_denied_domain_scan_is_sticky_sanitized_and_not_retried(self):
        clock, admission = _Clock(), _Admission()
        domain = SettlementDomain("postgresql://unit.invalid/not-contacted", "s14_scan", "s14_scan", "s14-domain")
        attempts = []
        healthy = [False]
        def cleanup(**kwargs):
            attempts.append(kwargs)
            if not healthy[0]:
                raise errors.InsufficientPrivilege("synthetic scanner password=do-not-export")
            return None
        with ExitStack() as stack:
            for field, value in (
                ("_DOMAINS", {domain.domain_id: domain}), ("_SCAN_NEXT", {}),
                ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""), ("_SCAN_BLOCKED", {}),
                ("_SCAN_INFLIGHT", 0), ("_ADMISSION", admission), ("_STOP", False), ("_DEADLINE", None),
            ):
                stack.enter_context(patch.object(settlement, field, value, create=True))
            stack.enter_context(patch.object(settlement, "time", clock))
            stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("offline DB forbidden")))
            stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("offline config forbidden")))
            stack.enter_context(patch.object(settlements, "run_cleanup_once", side_effect=cleanup))
            settlement._scan_domains()
            self.assertEqual("settlement_storage_permission_denied", settlement.runtime_status()["cleanup_scan_error_code"])
            for _ in range(1200):
                clock.value += .05
                settlement._scan_domains()
            self.assertEqual(1, len(attempts))
            status = settlement.runtime_status()
            self.assertFalse(component_ready("settlement", status))
            self.assertNotIn("do-not-export", json.dumps(status))
            self.assertIn("settlement", admission.blocked)
            self.assertGreaterEqual(sum(status["counts"].values()), 1)
            self.assertFalse(settlement.drain_runtime(clock.value))
            # Capability verification is the original public remediation seam;
            # this offline test substitutes only that repository I/O.
            healthy[0] = True
            live_thread = SimpleNamespace(is_alive=lambda: True)
            with patch.object(settlement, "_THREAD", live_thread), \
                    patch.object(settlements, "verify_domain", return_value={"schema_version": 1}):
                self.assertTrue(settlement.start_runtime(domain=domain))
            clock.value += 10
            settlement._scan_domains()
            self.assertEqual(2, len(attempts))
            self.assertEqual("", settlement.runtime_status()["cleanup_scan_error_code"])
            self.assertNotIn("settlement", admission.blocked)


class PersistentSettlementIdentityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.checkouts = []
        def forbidden_checkout(*args, **kwargs):
            self.checkouts.append((args, kwargs))
            raise AssertionError("identity rejection must occur before checkout")
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=forbidden_checkout))
        self.stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("offline config forbidden")))
        url, operation_schema, permit_schema = "postgresql://unit.invalid/not-contacted", "s14_operation", "s14_permit"
        identity = hashlib.sha256(json.dumps([url, operation_schema, permit_schema],
            ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
        self.domain = SettlementDomain(url, operation_schema, permit_schema, identity)
        self.origin = {"domain_id": identity, "operation_schema": operation_schema, "permit_schema": permit_schema,
                       "run_id": 7, "run_uuid": "s14-run", "task_id": 8, "execution_id": "s14-execution",
                       "permit_id": "s14-permit", "ticket_id": "s14-ticket", "lease_requirement": "accountless"}

    def test_wrong_database_domain_and_schema_are_rejected_before_any_target_write(self):
        original = seal_intent(kind="terminal", origin=self.origin, payload={"status": "success"})
        cases = (
            (original, replace(self.domain, database_url="postgresql://different.invalid/not-contacted")),
            (original, replace(self.domain, permit_schema="s14_other")),
            (seal_intent(kind="terminal", origin={**self.origin, "domain_id": "wrong-domain"}, payload={"status": "success"}), self.domain),
            (seal_intent(kind="terminal", origin={**self.origin, "operation_schema": "s14_other"}, payload={"status": "success"}), self.domain),
        )
        for intent, domain in cases:
            with self.subTest(domain=domain.domain_id, origin_schema=intent.origin["operation_schema"]):
                with self.assertRaises(OperationSettlementFenced):
                    settlements.submit_intent(intent, domain=domain)
        self.assertEqual([], self.checkouts)
        self.assertIsNone(common.current_settlement_domain())

    def test_wrong_original_ticket_is_fenced_before_any_business_write(self):
        queries = []
        permit = {"permit_id": self.origin["permit_id"], "execution_id": self.origin["execution_id"],
                  "run_id": self.origin["run_id"], "released_at": None,
                  "metadata": {"settlement_ticket": {**self.origin, "ticket_id": "different-original-ticket"}}}
        class Connection:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def cursor(self, **kwargs):
                return self
            def execute(self, query, params=None):
                queries.append((str(query), params))
                if not str(query).lstrip().startswith("SELECT"):
                    raise AssertionError("identity mismatch reached a mutation")
            def fetchall(self):
                return []
            def fetchone(self):
                return permit
        intent = seal_intent(kind="terminal", origin=self.origin, payload={"status": "success"})
        with patch.object(common, "_connect", return_value=Connection()):
            with self.assertRaisesRegex(OperationSettlementFenced, "original settlement ticket mismatch"):
                settlements.submit_intent(intent, domain=self.domain)
        self.assertEqual(2, len(queries))
        self.assertIn("operation_settlement_receipts", queries[0][0])
        self.assertIn("operation_execution_permits", queries[1][0])
        self.assertEqual([], self.checkouts)


# Root exclusively opts into actual role/permission coverage. An ordinary
# offline import never loads support_pg or private .env.
if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    from contextlib import contextmanager
    from cryptography.fernet import Fernet
    from psycopg import sql
    from tests.support_pg import PostgresTestCase
    from core.operations import task_gateway
    from core.storage.operations import permits, store

    class PersistentSettlementPermissionPostgresTests(PostgresTestCase):
        def setUp(self):
            super().setUp()
            counts = settlement.active_counts()
            self.assertTrue(counts)
            self.assertTrue(all(value == 0 for value in counts.values()), counts)
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
            self.assertFalse(settlement._EXPECTED)
            self.assertFalse(settlement._SCAN_BLOCKED)
            self.assertFalse(any(not item.released for item in settlement._REGISTRY.values()))
            self.assertTrue(settlement.stop_runtime(time.monotonic() + 2))
            self.stack = ExitStack()
            self.addCleanup(self.stack.close)
            self.stack.enter_context(patch.dict(os.environ, {
                "TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            }))
            for name, value in (
                ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
                ("_DOMAINS", {}), ("_DEADLINE", None), ("_THREAD", None),
                ("_STOP", False), ("_STARTED", False), ("_STOP_WITH_PENDING", False),
                ("_ADMISSION", None), ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}),
                ("_SCAN_BLOCKED", {}), ("_SCAN_ERROR", ""), ("_SCAN_INFLIGHT", 0),
            ):
                self.stack.enter_context(patch.object(settlement, name, value))
            self.role = "s14_denied_" + uuid.uuid4().hex[:16]
            self.role_created = False
            self.execution = None
            self.original_submit = settlements.submit_intent
            self.addCleanup(self.cleanup_exact_test_resources)
            store.reset_ready()
            store.init()
            permits.ensure_tables()
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user")
                if not cur.fetchone()[0]:
                    self.skipTest("actual S14 role test requires exclusive disposable DB CREATEROLE")
                cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(self.role)))
                self.role_created = True
                cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(self.role)))
                cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(self.role)))
                cur.execute(sql.SQL("GRANT UPDATE ON {}.operation_execution_permits TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(self.role)))

        def cleanup_exact_test_resources(self):
            if self.execution is not None and not self.execution.released:
                item = settlement.responsibility(self.execution)
                if item.intent is None:
                    task_gateway.rollback_admission(self.execution, reason="s14_native_cleanup_unstarted")
                else:
                    settlement.settle(self.execution, item.intent,
                        lambda intent, deadline: self.original_submit(
                            intent, domain=self.execution.settlement_domain, deadline=deadline))
                settlement.request_release(self.execution)
                deadline = time.monotonic() + 5
                while not self.execution.released and time.monotonic() < deadline:
                    settlement._progress(item)
                    time.sleep(.01)
                self.assertTrue(self.execution.released)
            self.assertTrue(settlement.stop_runtime(time.monotonic() + 2))
            self.assertTrue(concurrency.stop_release_runtime(time.monotonic() + 2))
            self.assertTrue(all(value == 0 for value in settlement.active_counts().values()))
            self.assertFalse(settlement._EXPECTED)
            self.assertFalse(settlement._SCAN_BLOCKED)
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
            if self.role_created:
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(
                        sql.Identifier(self.schema), sql.Identifier(self.role)))
                    cur.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                        sql.Identifier(self.schema), sql.Identifier(self.role)))
                    cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(self.role)))

        def test_s14_real_role_permission_denial_preserves_original_run_then_explicitly_recovers(self):
            from config.concurrency import policy_values
            from core.storage import runtime_config
            values = policy_values({})
            runtime_config.write_values({key: str(value) for key, value in values.items()},
                                        activate=True, source="s14-root-fixture")
            created = store.create_runtime_task(task_type="maintenance_check", account_id=None, email="", data={})
            self.execution = task_gateway.admit_operation_run(store.get_run(created["run"]["id"])).context
            self.assertIsNotNone(self.execution)
            callback_count, native_sqlstates = [], []
            original_connect = common._connect
            @contextmanager
            def denied_connection():
                with original_connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(self.role)))
                    yield conn
            def submit_as_denied_role(intent, *, domain, deadline=None):
                try:
                    with patch.object(common, "_connect", denied_connection):
                        return self.original_submit(intent, domain=domain, deadline=deadline)
                except psycopg.Error as exc:
                    native_sqlstates.append(exc.sqlstate)
                    raise
            def callback():
                callback_count.append(1)
                context = task_gateway.OperationHandlerContext(
                    self.execution.claimed_run, execution_id=self.execution.execution_id)
                context.finish(status="success", result_summary={"local_business": "confirmed"})
            with patch.object(settlements, "submit_intent", side_effect=submit_as_denied_role):
                with self.assertRaises(OperationSettlementPending):
                    task_gateway.execute_admitted(self.execution, callback)
            item = settlement.responsibility(self.execution)
            self.assertEqual(["42501"], native_sqlstates)
            self.assertEqual("settlement_storage_permission_denied", item.error_code)
            self.assertEqual([1], callback_count)
            self.assertFalse(self.execution.released)
            self.assertEqual("running", store.get_run(self.execution.claimed_run["id"])["status"])
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {common._table('operation_settlement_receipts')} "
                            "WHERE permit_id=%s AND execution_id=%s",
                            (self.execution.permit_id, self.execution.execution_id))
                self.assertEqual(0, cur.fetchone()[0])
                cur.execute(f"SELECT released_at FROM {postgres.qualified('operation_execution_permits')} "
                            "WHERE permit_id=%s AND execution_id=%s",
                            (self.execution.permit_id, self.execution.execution_id))
                self.assertIsNone(cur.fetchone()[0])
            intent = item.intent
            settlement.settle(self.execution, intent,
                lambda frozen, deadline: self.original_submit(
                    frozen, domain=self.execution.settlement_domain, deadline=deadline))
            settlement.request_release(self.execution)
            deadline = time.monotonic() + 5
            while not self.execution.released and time.monotonic() < deadline:
                settlement._progress(item)
                time.sleep(.01)
            self.assertTrue(self.execution.released)
            self.assertEqual([1], callback_count)
            self.assertEqual(["42501"], native_sqlstates)
            self.assertEqual("success", store.get_run(self.execution.claimed_run["id"])["status"])
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {common._table('operation_settlement_receipts')} "
                            "WHERE permit_id=%s AND execution_id=%s",
                            (self.execution.permit_id, self.execution.execution_id))
                self.assertEqual(1, cur.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
