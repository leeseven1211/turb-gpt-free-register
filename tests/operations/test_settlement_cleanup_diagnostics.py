"""S14 storage-return diagnostics, without configuration, DB or process I/O.

The real storage dispatcher/coordinator remain under test. Only the repository
claim/completion and typed action I/O seams are replaced with controlled rows.
Root owns genuine PostgreSQL permissions/CAS and restart acceptance.
"""
from contextlib import ExitStack
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from psycopg import OperationalError, errors

from core.operations import settlement
from core.operations.settlement_contracts import (
    OperationSettlementConflict, OperationSettlementFenced, SettlementDomain, seal_intent,
)
from core.runtime.readiness import component_ready
from core.storage import postgres
from core.storage.operations import settlements


def domain_for(name="cleanup_diag"):
    parts = ["postgresql://unit.invalid/not-contacted", name, name]
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    return SettlementDomain(*parts, digest)


def job_for(domain, *, attempts=1):
    return dict(id=17, receipt_id=23, domain_id=domain.domain_id, run_id=29,
                run_uuid="original-run", execution_id="original-execution",
                permit_id="original-permit", action_kind="resource_release",
                resource_identity="original-resource", payload={}, blocks_permit=True,
                state="claimed", claim_token="exact-claim", attempts=attempts)


class CleanupDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.domain = domain_for()
        self.row = job_for(self.domain)
        self.completed = []
        self.actions = []
        self.error = errors.InsufficientPrivilege("private password=never-export")
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("offline DB forbidden")))
        self.stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("offline config forbidden")))
        self.stack.enter_context(patch.object(settlements, "_claim_cleanup", side_effect=lambda **kw: dict(self.row)))
        self.stack.enter_context(patch.object(settlements, "cleanup_diagnostics", return_value=[]))
        self.stack.enter_context(patch.object(settlements, "_complete_cleanup", side_effect=self.complete))
        self.stack.enter_context(patch.object(settlements, "_execute_cleanup", side_effect=self.action))

    def complete(self, job, **kwargs):
        self.completed.append((dict(job), kwargs))
        return True

    def action(self, job, **kwargs):
        self.actions.append(job["id"])
        raise self.error

    def run_once(self):
        return settlements.run_cleanup_once(domain=self.domain)

    def test_action_permission_return_keeps_stable_error_and_durable_block(self):
        result = self.run_once()
        self.assertEqual("settlement_storage_permission_denied", result["error_code"])
        self.assertEqual("reconciliation_required", result["state"])
        self.assertIs(True, result["blocked"])
        self.assertEqual("settlement_storage_permission_denied", self.completed[0][1]["error_code"])
        self.assertEqual("reconciliation_required", self.completed[0][1]["disposition"])
        self.assertNotIn("never-export", json.dumps(result) + json.dumps(self.completed[0][1], default=str))

    def test_action_auth_unknown_and_protocol_errors_are_permanent(self):
        cases = [
            (errors.InvalidPassword("private"), "settlement_storage_authentication_failed"),
            (errors.lookup("XX000")("private"), "settlement_storage_sqlstate_unknown"),
            (OperationSettlementFenced("private"), "operation_settlement_fenced"),
            (OperationSettlementConflict("private"), "operation_settlement_conflict"),
        ]
        for error, code in cases:
            with self.subTest(code=code):
                self.error = error
                result = self.run_once()
                self.assertEqual(code, result["error_code"])
                self.assertTrue(result["blocked"])

    def test_transient_action_backoff_uses_persistent_attempts(self):
        self.error = errors.SerializationFailure("private")
        delays = []
        for attempts in (1, 2, 5, 20):
            self.row["attempts"] = attempts
            result = self.run_once()
            self.assertEqual("settlement_storage_unavailable", result["error_code"])
            self.assertFalse(result["blocked"])
            self.assertEqual("pending", result["state"])
            delays.append(result["retry_after_seconds"])
        self.assertGreater(delays[1], delays[0])
        self.assertGreater(delays[2], delays[1])
        self.assertGreaterEqual(delays[0], .05)
        self.assertLessEqual(delays[-1], 5)

    def test_unproved_physical_release_is_waiting_not_permanently_blocked(self):
        self.error = ValueError("physical_resource_release_unproved")
        result = self.run_once()
        self.assertEqual("pending", result["state"])
        self.assertIs(False, result.get("blocked"))
        self.assertEqual("settlement_cleanup_waiting", result["error_code"])

    def test_failed_completion_cas_is_never_acknowledged_as_durable_block(self):
        with patch.object(settlements, "_complete_cleanup", return_value=False):
            result = self.run_once()
        self.assertEqual("claim_lost", result["state"])
        self.assertIsNot(result.get("blocked"), True)

    def test_blocked_return_carries_exact_job_identity_for_explicit_retry(self):
        identity = self.run_once().get("identity", {})
        for field, value in {"cleanup_id": 17, "receipt_id": 23, "run_uuid": "original-run",
                             "execution_id": "original-execution", "permit_id": "original-permit",
                             "action_kind": "resource_release", "resource_identity": "original-resource"}.items():
            self.assertEqual(value, identity.get(field), field)

    def test_existing_persistent_block_remains_visible_while_other_due_action_progresses(self):
        diagnostic = {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                      "error_code": "settlement_storage_permission_denied"}
        self.row["id"] = 18
        def complete_other(job, **kwargs):
            self.actions.append(job["id"])
        with patch.object(settlements, "cleanup_diagnostics", return_value=[diagnostic]), \
                patch.object(settlements, "_execute_cleanup", side_effect=complete_other):
            result = self.run_once()
        self.assertEqual(18, result["cleanup_id"])
        self.assertEqual("done", result["state"])
        self.assertEqual([17], [row["cleanup_id"] for row in result["diagnostics"]])
        self.assertEqual([18], self.actions)

    def test_no_due_action_prioritizes_blocking_wait_over_nonblocking_block(self):
        rows = [
            {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
             "error_code": "settlement_storage_permission_denied", "blocks_permit": False},
            {"cleanup_id": 18, "state": "pending", "blocked": False,
             "error_code": "settlement_cleanup_waiting", "blocks_permit": True},
        ]
        with patch.object(settlements, "cleanup_diagnostics", return_value=rows), \
                patch.object(settlements, "_claim_cleanup", return_value=None):
            result = self.run_once()
        self.assertEqual(18, result["cleanup_id"])
        self.assertEqual([17], [row["cleanup_id"] for row in result["diagnostics"]])


class _Admission:
    def __init__(self):
        self.blocked = set()
    def block(self, reason):
        self.blocked.add(reason)
    def unblock(self, reason):
        self.blocked.discard(reason)
    def reasons(self):
        return set(self.blocked)


class CleanupScannerDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.domain = domain_for()
        self.gate = _Admission()
        self.clock = SimpleNamespace(value=100., monotonic=lambda: self.clock.value)
        for key, value in (
            ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
            ("_CARRIER_ERROR", ""), ("_DOMAINS", {self.domain.domain_id: self.domain}),
            ("_SCAN_BLOCKED", {}), ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}),
            ("_SCAN_ERROR", ""), ("_SCAN_INFLIGHT", 0), ("_RESERVATIONS", 0), ("_STOP", False),
            ("_SCAN_DIAGNOSTICS", {}),
            ("_STOP_WITH_PENDING", False), ("_DEADLINE", None), ("_STARTED", True),
            ("_THREAD", SimpleNamespace(is_alive=lambda: True)), ("_ADMISSION", self.gate),
        ):
            self.stack.enter_context(patch.object(settlement, key, value))
        self.stack.enter_context(patch.object(settlement, "time", self.clock))
        self.stack.enter_context(patch.object(postgres, "connect", side_effect=AssertionError("offline DB forbidden")))
        self.stack.enter_context(patch.object(postgres, "database_url", side_effect=AssertionError("offline config forbidden")))

    def _read_timeout(self):
        with patch.object(settlements, "cleanup_diagnostics", side_effect=TimeoutError("private")), \
                patch.object(settlements, "_claim_cleanup") as claim:
            settlement._scan_domains()
        claim.assert_not_called()

    def _begin_owner_loss_shutdown(self):
        self.gate.block("owner_lost")
        self.gate.block("draining")
        settlement.begin_shutdown(self.clock.value)

    def test_owner_loss_shutdown_can_exit_after_read_only_scan_timeout(self):
        self._read_timeout()
        self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])
        self.assertFalse(component_ready("settlement", settlement.runtime_status()))
        self.gate.block("owner_lost")
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self._begin_owner_loss_shutdown()
        self.assertTrue(settlement.drain_runtime(self.clock.value))
        self.assertEqual(0, settlement.drain_counts()["unverified_scan_pending"])
        self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])

        carrier = settlement._THREAD
        carrier.join = lambda timeout: setattr(carrier, "is_alive", lambda: False)
        self.assertTrue(settlement.stop_runtime(self.clock.value))
        self.assertEqual({"owner_lost", "draining", "settlement"}, self.gate.blocked)
        self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])

    def test_owner_loss_shutdown_still_blocks_on_known_cleanup_after_read_timeout(self):
        durable = {"state": "pending", "error_code": "settlement_storage_unavailable",
                   "blocks_permit": True, "identity": {"permit_id": "original-permit"}}
        with patch.object(settlements, "cleanup_diagnostics", return_value=[durable]), \
                patch.object(settlements, "_claim_cleanup", return_value=None):
            settlement._scan_domains()
        self.clock.value += 1
        self._read_timeout()
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])

    def test_owner_loss_shutdown_still_blocks_after_ambiguous_cleanup_claim(self):
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_claim_cleanup", side_effect=OperationalError("private")):
            settlement._scan_domains()
        self.clock.value += 1
        self._read_timeout()
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])

    def test_owner_loss_shutdown_can_exit_after_candidate_read_unavailable(self):
        for boundary in ("checkout", "query"):
            with self.subTest(boundary=boundary):
                cursor = MagicMock()
                cursor.execute.side_effect = TimeoutError("private")
                connect = MagicMock(side_effect=OperationalError("private") if boundary == "checkout" else None)
                connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
                with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                        patch.object(settlements._common, "_connect", connect):
                    settlement._scan_domains()
                self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])
                self.assertTrue(settlement.idle_for_owner_retry())
                if boundary == "query":
                    self.assertTrue(cursor.execute.call_args.args[0].lstrip().startswith("SELECT "))
                self._begin_owner_loss_shutdown()
                self.assertTrue(settlement.drain_runtime(self.clock.value))
                self.gate.unblock("owner_lost")
                self.gate.unblock("draining")
                self.assertTrue(settlement.end_shutdown(self.clock.value))
                self.clock.value += 1

    def test_candidate_read_failure_retains_durable_work_observed_in_same_scan(self):
        durable = {"state": "pending", "error_code": "settlement_storage_unavailable",
                   "blocked": False, "blocks_permit": True, "identity": {"permit_id": "original-permit"}}
        with patch.object(settlements, "cleanup_diagnostics", return_value=[durable]), \
                patch.object(settlements._common, "_connect", side_effect=TimeoutError("private")):
            settlement._scan_domains()
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(durable["identity"], settlement._SCAN_DIAGNOSTICS[self.domain.domain_id]["identity"])

    def test_candidate_read_failure_does_not_assume_nonblocking_diagnostic_is_only_work(self):
        diagnostic = {"state": "pending", "blocked": False, "blocks_permit": False,
                      "error_code": "settlement_storage_unavailable"}
        with patch.object(settlements, "cleanup_diagnostics", return_value=[diagnostic]), \
                patch.object(settlements._common, "_connect", side_effect=TimeoutError("private")):
            settlement._scan_domains()
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])

    def _assert_partial_scan_preserves_prior_block(self, *, ambiguous):
        observed = {"state": "pending", "error_code": "settlement_storage_unavailable", "blocked": False,
                    "blocks_permit": True, "identity": {"permit_id": "original-permit",
                                                        "execution_id": "original-execution"}}
        prior = {**observed, "identity": {"permit_id": "prior-permit", "execution_id": "prior-execution"}}
        with patch.object(settlements, "cleanup_diagnostics", return_value=[] if ambiguous else [prior]), \
                patch.object(settlements, "_claim_cleanup", return_value=None,
                             side_effect=OperationalError("write result unknown") if ambiguous else None):
            settlement._scan_domains()
        self.clock.value += 1
        with patch.object(settlements, "cleanup_diagnostics", return_value=[observed]), \
                patch.object(settlements._common, "_connect", side_effect=TimeoutError("private")):
            settlement._scan_domains()
        execution = SimpleNamespace(**observed["identity"], settlement_domain=self.domain, released=False)
        ticket = {**observed["identity"], "domain_id": self.domain.domain_id}
        item = settlement.register_execution(execution, ticket)
        item.intent = seal_intent(kind="terminal", origin=ticket, payload={"status": "success"})
        item._receipt = {"transition_id": item.intent.transition_id}
        item.callback_exited = item.release_requested = item._durable_pending = True
        self._begin_owner_loss_shutdown()
        with patch.object(settlements, "mark_cleanup_handoff", return_value=True), \
                patch.object(settlements, "run_cleanup_once", return_value=None), \
                patch.object(settlements, "cleanup_blocks_permit", return_value=False), \
                patch.object(settlement, "_release_execution",
                             side_effect=lambda *args: setattr(execution, "released", True)):
            settlement._progress(item)
        self.assertTrue(execution.released)
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])
        expected = None if ambiguous else prior["identity"]
        actual = settlement._SCAN_DIAGNOSTICS[self.domain.domain_id].get("identity")
        self.assertEqual(expected, actual)

    def test_partial_scan_preserves_prior_cleanup_through_unrelated_owned_success(self):
        self._assert_partial_scan_preserves_prior_block(ambiguous=False)

    def test_partial_scan_preserves_ambiguous_claim_through_unrelated_owned_success(self):
        self._assert_partial_scan_preserves_prior_block(ambiguous=True)

    def test_owner_loss_shutdown_still_blocks_on_claim_write_timeout(self):
        reader, writer = MagicMock(), MagicMock()
        reader.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            {"id": 17, "handoff_receipt_id": 23},
        ]
        writer_cursor = writer.__enter__.return_value.cursor.return_value.__enter__.return_value
        writer_cursor.execute.side_effect = TimeoutError("write result unknown")
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements._common, "_connect", side_effect=[reader, writer]):
            settlement._scan_domains()
        self.assertTrue(writer_cursor.execute.call_args.args[0].lstrip().startswith("UPDATE "))
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))

    def test_empty_due_scan_keeps_ambiguous_claim_until_unfinished_work_is_checked(self):
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_claim_cleanup", side_effect=OperationalError("write result unknown")):
            settlement._scan_domains()
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_claim_cleanup", return_value=None), \
                patch.object(settlements._common, "_connect", return_value=connection):
            cursor.fetchone.return_value = {"present": 1}
            self.clock.value += 1
            settlement._scan_domains()
            self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])
            query, parameters = cursor.execute.call_args.args
            self.assertIn("blocks_permit", query)
            self.assertIn("state <> 'done'", query)
            self.assertIn("state <> 'superseded'", query)
            self.assertNotIn("claim_until", query)
            self.assertNotIn("next_attempt_at", query)
            self.assertEqual((self.domain.domain_id,), parameters)
            cursor.fetchone.return_value = None
            self.clock.value += 1
            settlement._scan_domains()
        self.assertEqual(0, settlement.drain_counts()["unverified_scan_pending"])

    def test_owner_loss_shutdown_still_blocks_on_permanent_read_error(self):
        with patch.object(settlements, "cleanup_diagnostics",
                          side_effect=errors.InsufficientPrivilege("private")):
            settlement._scan_domains()
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])

    def test_permanent_candidate_error_blocks_shutdown_after_nonblocking_cleanup(self):
        nonblocking = {"state": "pending", "blocked": False, "blocks_permit": False,
                       "error_code": "settlement_storage_unavailable"}
        with patch.object(settlements, "cleanup_diagnostics", return_value=[nonblocking]), \
                patch.object(settlements, "_claim_cleanup", return_value=None):
            settlement._scan_domains()
        self.assertEqual(0, settlement.drain_counts()["unverified_scan_pending"])
        self.clock.value += 1
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements._common, "_connect",
                             side_effect=errors.InsufficientPrivilege("private")):
            settlement._scan_domains()
        self.assertEqual("settlement_storage_permission_denied",
                         settlement.runtime_status()["cleanup_scan_error_code"])
        self._begin_owner_loss_shutdown()
        self.assertFalse(settlement.drain_runtime(self.clock.value))
        self.assertEqual(1, settlement.drain_counts()["unverified_scan_pending"])

    def test_owner_loss_shutdown_still_waits_for_inflight_work_after_read_timeout(self):
        self._read_timeout()
        with settlement.reserve_admission() as granted:
            self.assertTrue(granted)
            self._begin_owner_loss_shutdown()
            self.assertFalse(settlement.drain_runtime(self.clock.value))
        with patch.object(settlement, "_SCAN_INFLIGHT", 1):
            self.assertFalse(settlement.drain_runtime(self.clock.value))
        execution = SimpleNamespace(permit_id="live-permit", execution_id="live-execution")
        settlement.register_execution(execution, vars(execution).copy())
        self.assertTrue(settlement.callback_started(execution))
        self.assertFalse(settlement.drain_runtime(self.clock.value))

    def test_owner_retry_rejects_ambiguous_work_but_can_recheck_with_read_only_scan_error(self):
        self._read_timeout()
        self.assertTrue(settlement.idle_for_owner_retry())
        with patch.object(settlement, "_SCAN_INFLIGHT", 1):
            self.assertFalse(settlement.idle_for_owner_retry())
        with settlement.reserve_admission() as granted:
            self.assertTrue(granted)
            self.assertFalse(settlement.idle_for_owner_retry())
        self.clock.value += 1
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_claim_cleanup", side_effect=OperationalError("private")):
            settlement._scan_domains()
        self.assertFalse(settlement.idle_for_owner_retry())

    def test_paused_owner_neither_claims_local_work_nor_starts_durable_scans(self):
        self.gate.block("owner_probe_paused")
        with settlement.reserve_admission() as granted:
            self.assertFalse(granted)
        with patch.object(settlements, "run_cleanup_once") as scan, \
                patch.object(settlements, "retry_cleanup") as retry:
            settlement._scan_domains()
            with self.assertRaises(OperationSettlementFenced):
                settlement.retry_cleanup(domain=self.domain, identity={})
        scan.assert_not_called()
        retry.assert_not_called()

    def test_real_dispatcher_blocked_return_makes_empty_registry_unready(self):
        row = job_for(self.domain)
        with patch.object(settlements, "_claim_cleanup", return_value=row), \
                patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_execute_cleanup", side_effect=errors.InsufficientPrivilege("secret")), \
                patch.object(settlements, "_complete_cleanup", return_value=True):
            settlement._scan_domains()
        status = settlement.runtime_status()
        self.assertFalse(component_ready("settlement", status))
        self.assertEqual("settlement_storage_permission_denied", status["cleanup_scan_error_code"])
        self.assertGreaterEqual(status["counts"]["unverified_scan_pending"], 1)
        self.assertIn("settlement", self.gate.blocked)

    def test_successful_other_domain_does_not_clear_blocked_domain_diagnostic(self):
        other = domain_for("other")
        settlement._DOMAINS[other.domain_id] = other
        outcomes = [{"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                     "error_code": "settlement_storage_permission_denied"}, None]
        with patch.object(settlements, "run_cleanup_once", side_effect=outcomes):
            settlement._scan_domains()
        status = settlement.runtime_status()
        self.assertEqual("settlement_storage_permission_denied", status["cleanup_scan_error_code"])
        self.assertFalse(component_ready("settlement", status))

    def test_new_consumer_discovers_persistent_block_without_eligible_job(self):
        self.assertTrue(callable(getattr(settlements, "cleanup_diagnostics", None)),
                        "storage needs bounded persistent blocked readback")
        diagnostic = {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                      "error_code": "settlement_storage_permission_denied", "blocks_permit": True}
        with patch.object(settlements, "_claim_cleanup", return_value=None), \
                patch.object(settlements, "cleanup_diagnostics", return_value=[diagnostic]):
            settlement._scan_domains()
        self.assertFalse(component_ready("settlement", settlement.runtime_status()))

    def test_capability_restart_preserves_durable_block_and_retry_gate_across_domains(self):
        from core.runtime.context import AdmissionGate
        gate = AdmissionGate()
        gate.unblock("startup")
        diagnostic = {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                      "error_code": "settlement_storage_permission_denied", "blocks_permit": True,
                      "retry_after_seconds": 5.0,
                      "identity": {"permit_id": "original-permit", "execution_id": "original-execution"}}
        with patch.object(settlement, "_ADMISSION", gate):
            with patch.object(settlements, "run_cleanup_once", return_value=diagnostic):
                settlement._scan_domains()
            next_attempt = settlement._SCAN_NEXT[self.domain.domain_id]
            with patch.object(settlements, "verify_domain", return_value={"schema_version": 1}):
                self.assertTrue(settlement.start_runtime(domain=self.domain))
            self.assertFalse(gate.is_open())
            self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])
            self.assertEqual(next_attempt, settlement._SCAN_NEXT[self.domain.domain_id])
            self.assertEqual(diagnostic["identity"],
                             settlement._SCAN_DIAGNOSTICS[self.domain.domain_id]["identity"])
            other = domain_for("healthy_other")
            settlement._DOMAINS[other.domain_id] = other
            with patch.object(settlements, "run_cleanup_once", return_value=None):
                settlement._scan_domains()
            self.assertFalse(component_ready("settlement", settlement.runtime_status()))
            self.assertFalse(gate.is_open())
            self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])

    def test_explicit_retry_cannot_rearm_stopped_or_owner_lost_runtime(self):
        self.assertTrue(callable(getattr(settlement, "retry_cleanup", None)),
                        "an explicit guarded cleanup remediation entry is required")
        self.assertTrue(callable(getattr(settlements, "retry_cleanup", None)))
        with patch.object(settlements, "retry_cleanup", side_effect=AssertionError("must reject before DB")):
            settlement._STOP = True
            with self.assertRaises(OperationSettlementFenced):
                settlement.retry_cleanup(domain=self.domain, identity={})
            settlement._STOP = False
            self.gate.block("owner_lost")
            with self.assertRaises(OperationSettlementFenced):
                settlement.retry_cleanup(domain=self.domain, identity={})

    def test_explicit_retry_rejects_incomplete_identity_before_repository_io(self):
        self.assertTrue(callable(getattr(settlements, "retry_cleanup", None)))
        with self.assertRaises((OperationSettlementFenced, ValueError)):
            settlements.retry_cleanup(domain=self.domain, identity={})

    def test_owned_progress_consumes_real_dispatcher_block_and_same_intent_rearms_only_it(self):
        execution = SimpleNamespace(permit_id="original-permit", execution_id="original-execution",
                                    settlement_domain=self.domain, released=False)
        ticket = dict(permit_id=execution.permit_id, execution_id=execution.execution_id,
                      domain_id=self.domain.domain_id)
        item = settlement.register_execution(execution, ticket)
        intent = seal_intent(kind="terminal", origin=ticket, payload={"status": "success"})
        item.intent = intent
        item._receipt = {"transition_id": intent.transition_id}
        item.callback_exited = item.release_requested = True
        item._durable_pending = True
        job = job_for(self.domain)
        with patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "_claim_cleanup", return_value=job), \
                patch.object(settlements, "_execute_cleanup", side_effect=errors.InsufficientPrivilege("private")), \
                patch.object(settlements, "_complete_cleanup", return_value=True), \
                patch.object(settlements, "mark_cleanup_handoff", return_value=True):
            settlement._progress(item)
        self.assertEqual("settlement_storage_permission_denied", item._blocked_error)
        self.assertFalse(execution.released)
        original_identity = dict(item._blocked_cleanup)
        self.assertEqual(17, original_identity["cleanup_id"])
        retries = []
        def retry(**kwargs):
            retries.append(dict(kwargs["identity"]))
            return {"state": "pending"}
        def release(*args):
            execution.released = True
        with patch.object(settlements, "retry_cleanup", side_effect=retry), \
                patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "mark_cleanup_handoff", return_value=True), \
                patch.object(settlements, "run_cleanup_once", return_value={"state": "done"}), \
                patch.object(settlements, "cleanup_blocks_permit", return_value=False), \
                patch.object(settlement, "_release_execution", side_effect=release):
            receipt = settlement.settle(execution, intent, lambda *args: self.fail("business resubmit forbidden"))
        self.assertEqual(intent.transition_id, receipt["transition_id"])
        self.assertEqual([original_identity], retries)
        self.assertTrue(execution.released)
        self.assertEqual("", item._blocked_error)

    def test_owner_lost_does_not_leave_resolved_transport_scan_block_after_owned_compensation(self):
        execution = SimpleNamespace(permit_id="original-permit", execution_id="original-execution",
                                    settlement_domain=self.domain, released=False)
        ticket = dict(permit_id=execution.permit_id, execution_id=execution.execution_id,
                      domain_id=self.domain.domain_id)
        item = settlement.register_execution(execution, ticket)
        item.intent = seal_intent(kind="terminal", origin=ticket, payload={"status": "success"})
        item._receipt = {"transition_id": item.intent.transition_id}
        item.callback_exited = item.release_requested = item._durable_pending = True
        settlement._SCAN_BLOCKED[self.domain.domain_id] = "settlement_storage_unavailable"
        self.gate.block("owner_lost")
        with patch.object(settlements, "mark_cleanup_handoff", return_value=True), \
                patch.object(settlements, "run_cleanup_once", return_value=None), \
                patch.object(settlements, "cleanup_blocks_permit", return_value=False), \
                patch.object(settlement, "_release_execution",
                             side_effect=lambda *args: setattr(execution, "released", True)):
            settlement._progress(item)
        self.assertTrue(execution.released)
        self.assertEqual(0, settlement.active_counts()["unverified_scan_pending"])
        self.assertIn("owner_lost", self.gate.blocked)

    def test_scoped_nonblocking_failure_cannot_erase_known_foreign_blocking_action(self):
        foreign = {"cleanup_id": 71, "state": "reconciliation_required", "blocked": True,
                   "error_code": "settlement_storage_permission_denied", "blocks_permit": True,
                   "identity": {"permit_id": "foreign-permit", "execution_id": "foreign-execution"}}
        with patch.object(settlements, "run_cleanup_once", return_value=foreign):
            settlement._scan_domains()
        execution = SimpleNamespace(permit_id="original-permit", execution_id="original-execution",
                                    settlement_domain=self.domain, released=False)
        ticket = dict(permit_id=execution.permit_id, execution_id=execution.execution_id,
                      domain_id=self.domain.domain_id)
        item = settlement.register_execution(execution, ticket)
        item.intent = seal_intent(kind="terminal", origin=ticket, payload={"status": "success"})
        item._receipt = {"transition_id": item.intent.transition_id}
        item.callback_exited = item.release_requested = item._durable_pending = True
        self.gate.block("owner_lost")
        scoped = {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                  "error_code": "settlement_storage_permission_denied", "blocks_permit": False,
                  "identity": {"permit_id": execution.permit_id, "execution_id": execution.execution_id}}
        with patch.object(settlements, "mark_cleanup_handoff", return_value=True), \
                patch.object(settlements, "run_cleanup_once", return_value=scoped), \
                patch.object(settlements, "cleanup_blocks_permit", return_value=False), \
                patch.object(settlement, "_release_execution",
                             side_effect=lambda *args: setattr(execution, "released", True)):
            settlement._progress(item)
        self.assertTrue(execution.released)
        self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])
        self.assertEqual("foreign-permit",
                         settlement._SCAN_DIAGNOSTICS[self.domain.domain_id]["identity"]["permit_id"])
        self.assertFalse(settlement.drain_runtime(self.clock.value))

    def test_retry_one_job_does_not_hide_another_block_in_same_domain(self):
        diagnostic = {"cleanup_id": 18, "state": "reconciliation_required", "blocked": True,
                      "error_code": "settlement_storage_permission_denied"}
        settlement._SCAN_BLOCKED[self.domain.domain_id] = diagnostic["error_code"]
        with patch.object(settlements, "retry_cleanup", return_value={"state": "pending"}), \
                patch.object(settlements, "cleanup_diagnostics", return_value=[diagnostic]):
            settlement.retry_cleanup(domain=self.domain, identity={"cleanup_id": 17})
        self.assertFalse(component_ready("settlement", settlement.runtime_status()))

    def test_nonblocking_handedoff_error_is_unready_but_does_not_block_owned_drain(self):
        diagnostic = {"cleanup_id": 17, "state": "reconciliation_required", "blocked": True,
                      "error_code": "settlement_storage_permission_denied", "blocks_permit": False,
                      "age_seconds": 44}
        with patch.object(settlements, "run_cleanup_once", return_value=diagnostic):
            settlement._scan_domains()
        status = settlement.runtime_status()
        self.assertFalse(component_ready("settlement", status))
        self.assertEqual(0, status["counts"]["unverified_scan_pending"])
        self.assertEqual(1, status["durable_cleanup_errors"])
        self.assertGreaterEqual(status["oldest_age_seconds"], 44)
        self.assertTrue(settlement.drain_runtime(self.clock.value + 1))

    def test_real_context_cached_receipt_allows_only_exact_blocked_action_retry(self):
        from core.operations import task_gateway as gateway
        execution = SimpleNamespace(permit_id="original-permit", execution_id="original-execution",
                                    settlement_domain=self.domain, released=False)
        ticket = dict(permit_id=execution.permit_id, execution_id=execution.execution_id,
                      domain_id=self.domain.domain_id, run_id=29, task_id=31, ticket_id="original-ticket")
        execution.settlement_ticket = ticket
        item = settlement.register_execution(execution, ticket)
        with patch.object(gateway, "_current_settlement_execution", return_value=execution):
            context = gateway.OperationHandlerContext({"id": 29, "task_id": 31},
                                                       execution_id=execution.execution_id)
        def submit(frozen, **kwargs):
            return {"transition_id": frozen.transition_id, "request_digest": frozen.request_digest,
                    "receipt_id": 23, "actual_result": {"status": "success", "result_summary": {}}}
        with patch.object(settlements, "submit_intent", side_effect=submit):
            context.finish(status="success")
        item.callback_exited = item.release_requested = True
        item._blocked_cleanup = {"cleanup_id": 17, "receipt_id": 23, "run_uuid": "original-run",
                                "execution_id": execution.execution_id, "permit_id": execution.permit_id,
                                "action_kind": "resource_release", "resource_identity": "original-resource"}
        item.error_code = item._blocked_error = "settlement_storage_permission_denied"
        original_receipt = dict(context._settlement_receipt)
        for field in ("transition_id", "request_digest", "receipt_id"):
            context._settlement_receipt = {**original_receipt, field: "foreign"}
            with self.subTest(field=field), self.assertRaises(OperationSettlementConflict):
                context.finish(status="success")
        context._settlement_receipt = original_receipt
        retried = []
        def rearm(**kwargs):
            retried.append(kwargs["identity"]["cleanup_id"])
            return {"state": "pending"}
        with patch.object(settlements, "retry_cleanup", side_effect=rearm), \
                patch.object(settlements, "cleanup_diagnostics", return_value=[]), \
                patch.object(settlements, "mark_cleanup_handoff", return_value=True), \
                patch.object(settlements, "run_cleanup_once", return_value={"state": "done"}), \
                patch.object(settlements, "cleanup_blocks_permit", return_value=False), \
                patch.object(settlements, "submit_intent", side_effect=AssertionError("business resubmit forbidden")), \
                patch.object(settlement, "_release_execution",
                             side_effect=lambda *args: setattr(execution, "released", True)):
            context.finish(status="success")
        self.assertEqual([17], retried)
        self.assertTrue(execution.released)


class CleanupRetryRepositoryTests(unittest.TestCase):
    def test_changed_original_identity_never_rearms_a_job(self):
        domain = domain_for()
        row = job_for(domain)
        row.update(state="reconciliation_required", claim_token=None,
                   disposition={"retry_blocked": True}, last_error_code="settlement_storage_permission_denied",
                   origin={"domain_id": domain.domain_id, "run_uuid": row["run_uuid"],
                           "execution_id": row["execution_id"], "permit_id": row["permit_id"]},
                   handoff_receipt_id=row["receipt_id"])
        identity = {"cleanup_id": row["id"], **{key: row[key] for key in (
            "receipt_id", "run_uuid", "execution_id", "permit_id", "action_kind", "resource_identity")}}
        writes = []
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, query, parameters):
                if query.lstrip().startswith("UPDATE"):
                    writes.append(parameters)
            def fetchone(self): return dict(row)
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def cursor(self): return Cursor()
        with patch.object(postgres, "connect", side_effect=AssertionError("DB forbidden")), \
                patch.object(postgres, "database_url", side_effect=AssertionError("config forbidden")), \
                patch.object(settlements._common, "_connect", return_value=Connection()):
            for field in ("receipt_id", "run_uuid", "execution_id", "permit_id", "action_kind", "resource_identity"):
                changed = {**identity, field: "foreign"}
                with self.subTest(field=field), self.assertRaises(OperationSettlementFenced):
                    settlements.retry_cleanup(domain=domain, identity=changed)
        self.assertEqual([], writes)


if __name__ == "__main__":
    unittest.main()
