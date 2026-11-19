"""Thread/barrier coverage; no config, PostgreSQL or business handlers."""
import threading
import time
import hashlib
import json
from contextlib import ExitStack
from types import SimpleNamespace, ModuleType
import sys
from unittest.mock import patch

import pytest

from core.operations import settlement as coordinator
from core.operations.settlement_contracts import (
    OperationSettlementConflict, OperationSettlementFenced, OperationSettlementPending, SettlementDomain, seal_intent, thaw,
)


def execution(name):
    return SimpleNamespace(permit_id=f"p-{name}", execution_id=f"e-{name}", released=False)


def intent_for(execution, **payload):
    return seal_intent(kind="terminal",
                       origin={"permit_id": execution.permit_id, "execution_id": execution.execution_id},
                       payload=payload, transition_id=execution.execution_id)


def domain_for(name):
    url = f"postgresql://{name}.invalid/not-contacted"
    operation_schema = f"test_{name}"
    permit_schema = f"permit_{name}"
    domain_id = hashlib.sha256(json.dumps(
        [url, operation_schema, permit_schema], ensure_ascii=True, separators=(",", ":")
    ).encode()).hexdigest()
    return SettlementDomain(url, operation_schema, permit_schema, domain_id)


@pytest.fixture
def registry():
    # Swap process-global ownership only while no test carrier is running.
    previous_thread = coordinator._THREAD
    assert previous_thread is None or not previous_thread.is_alive()
    assert all(value == 0 for value in coordinator.active_counts().values()), coordinator.runtime_status()
    assert not coordinator._EXPECTED and not coordinator._SCAN_BLOCKED
    assert coordinator._RESERVATIONS == coordinator._SCAN_INFLIGHT == 0
    assert coordinator._RESERVATION.get() is None
    with ExitStack() as outer:
        # stop_runtime also installs a deadline on an idle Thread=None runtime.
        # Capture every lifecycle/error global it may mutate before calling it.
        for name in ("_DEADLINE", "_STOP", "_STARTED", "_STOP_WITH_PENDING",
                     "_REGISTRY_ERROR", "_CARRIER_ERROR"):
            outer.enter_context(patch.object(coordinator, name, getattr(coordinator, name)))
        assert coordinator.stop_runtime(time.monotonic() + 1)
        with ExitStack() as isolated:
            for name, value in (
                ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
                ("_CARRIER_ERROR", ""), ("_DOMAINS", {}), ("_DEADLINE", None),
                ("_THREAD", None), ("_STARTED", False), ("_STOP", False),
                ("_STOP_WITH_PENDING", False), ("_ADMISSION", None),
                ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""),
                ("_SCAN_BLOCKED", {}), ("_SCAN_INFLIGHT", 0), ("_RESERVATIONS", 0),
            ):
                isolated.enter_context(patch.object(coordinator, name, value))
            yield
            # Pending fixtures deliberately have no real permit repository. Remove
            # their isolated ownership only after ensuring no carrier is in I/O.
            worker = coordinator._THREAD
            assert worker is None or not worker.is_alive() or not any(
                row.inflight for row in coordinator._REGISTRY.values())
            coordinator._REGISTRY.clear()
            coordinator._EXPECTED.clear()
            coordinator._REGISTRY_ERROR = ""
            coordinator.stop_runtime(time.monotonic() + 1)
            if worker is not None:
                worker.join(1)
                assert not worker.is_alive()


def test_duplicate_confirmation_returns_original_snapshot_and_conflict_never_submits(registry):
    job = execution("duplicate")
    ticket = {"permit_id": job.permit_id, "execution_id": job.execution_id}
    coordinator.register_execution(job, ticket)
    frozen = intent_for(job, status="success")
    calls = []

    def submit(intent, deadline):
        calls.append(intent)
        return {"transition_id": intent.transition_id, "result": {"status": "success"}}

    receipt = coordinator.settle(job, frozen, submit)
    receipt["result"]["status"] = "tampered"
    assert coordinator.settle(job, frozen, submit)["result"]["status"] == "success"
    assert len(calls) == 1
    with pytest.raises(OperationSettlementConflict):
        coordinator.settle(job, intent_for(job, status="failed"), submit)
    assert len(calls) == 1


def test_callback_exit_handoff_keeps_permit_until_exact_retry_is_confirmed(registry):
    job = execution("retry")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    coordinator.callback_started(job)
    frozen = intent_for(job, status="success", summary={"steps": [{"state": "done"}]})
    recovered = threading.Event()
    attempts = []

    def submit(intent, deadline):
        attempts.append(intent)
        if not recovered.is_set():
            raise OSError("database unavailable with private DSN")
        return {"transition_id": intent.transition_id, "result": thaw(intent.payload)}

    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, frozen, submit)
    coordinator.request_release(job)
    assert not coordinator.release_eligible(job)
    coordinator.callback_exited(job)
    assert not coordinator.release_eligible(job)
    facts = coordinator.active_counts()
    assert facts["settlement_pending"] == 1
    assert facts["unpersisted"] == 1
    assert facts["permit_pending"] == 0
    assert "private DSN" not in str(coordinator.runtime_status())
    # No release requested from the fixture's permit adapter: explicitly prove
    # the coordinator uses its local exact-release seam, not a business callback.
    with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: setattr(item, "released", True) or True):
        recovered.set()
        coordinator.start_runtime()
        assert coordinator.drain_runtime(time.monotonic() + 2)
    assert job.released
    assert all(item is frozen for item in attempts)
    assert coordinator.active_counts()["unpersisted"] == 0


def test_confirmed_terminal_does_not_release_while_callback_has_not_exited(registry):
    job = execution("active")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    coordinator.callback_started(job)
    coordinator.settle(job, intent_for(job, status="success"), lambda item, deadline: {"transition_id": item.transition_id})
    coordinator.request_release(job)
    assert not coordinator.release_eligible(job)
    assert not job.released
    coordinator.callback_exited(job)
    assert coordinator.release_eligible(job)


def test_status_and_stop_do_not_wait_for_uninterruptible_storage_io(registry):
    job = execution("blocked")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    entered = threading.Event()
    allow_exit = threading.Event()
    attempts = []

    def submit(item, deadline):
        attempts.append(deadline)
        if len(attempts) == 1:
            raise OSError("offline")
        entered.set()
        allow_exit.wait(2)
        return {"transition_id": item.transition_id}

    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, intent_for(job, status="success"), submit)
    coordinator.callback_exited(job)
    coordinator.start_runtime()
    assert entered.wait(1)
    started = time.monotonic()
    assert coordinator.active_counts()["compensation_inflight"] == 1
    assert coordinator.runtime_status()["thread_alive"]
    deadline = time.monotonic() + 0.02
    assert not coordinator.stop_runtime(deadline)
    assert time.monotonic() - started < 0.3
    assert not coordinator.stop_runtime(time.monotonic() + 1)
    allow_exit.set()
    # Join uses the original deadline on repeated stop. Wait for the real
    # carrier to finish without claiming that an expired join killed its I/O.
    worker = coordinator._THREAD
    worker.join(1)
    assert not worker.is_alive()


def test_blocking_actor_cleanup_happens_after_callback_exit_before_storage(registry):
    job = execution("actor")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    coordinator.callback_started(job)
    order = []
    released = threading.Event()

    class Cleanup:
        before_transition = True

        def release(self, deadline=None):
            order.append("actor_stop")
            released.set()
            return True

    cleanup = Cleanup()
    coordinator.register_cleanup(job, cleanup, key="actor:original")
    coordinator.register_cleanup(job, cleanup, key="actor:original")
    with pytest.raises(OperationSettlementConflict):
        coordinator.register_cleanup(job, Cleanup(), key="actor:original")

    def submit(item, deadline):
        assert released.is_set()
        order.append("persist")
        return {"transition_id": item.transition_id}

    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, intent_for(job, status="success"), submit)
    assert order == []
    coordinator.request_release(job)
    coordinator.callback_exited(job)
    with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: order.append("permit") or setattr(item, "released", True) or True):
        coordinator.start_runtime()
        assert coordinator.drain_runtime(time.monotonic() + 1)
    assert order == ["actor_stop", "persist", "permit"]


def test_failed_cleanup_stays_pending_without_persist_or_permit_release(registry):
    job = execution("cleanup-failed")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    coordinator.callback_started(job)
    cleanup_attempt = threading.Event()

    class Cleanup:
        before_transition = True

        def release(self, deadline=None):
            cleanup_attempt.set()
            return False

    coordinator.register_cleanup(job, Cleanup(), key="actor:failed")
    persisted = []
    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, intent_for(job, status="success"),
                           lambda item, deadline: persisted.append(item) or {"transition_id": item.transition_id})
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    coordinator.start_runtime()
    assert cleanup_attempt.wait(1)
    assert not coordinator.drain_runtime(time.monotonic() + .03)
    assert persisted == []
    assert not job.released
    assert coordinator.active_counts()["resource_pending"] == 1


def test_unstarted_rollback_and_callback_start_share_one_barrier(registry):
    job = execution("rollback")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    intent = seal_intent(kind="defer", origin={"permit_id": job.permit_id, "execution_id": job.execution_id},
                         payload={"subtype": "unstarted_rollback"})
    coordinator.settle(job, intent, lambda item, deadline: {"transition_id": item.transition_id})
    assert coordinator.callback_started(job) is False
    other = execution("started")
    coordinator.register_execution(other, {"permit_id": other.permit_id, "execution_id": other.execution_id})
    assert coordinator.callback_started(other) is True
    with pytest.raises(OperationSettlementConflict):
        coordinator.settle(other, seal_intent(kind="defer",
                           origin={"permit_id": other.permit_id, "execution_id": other.execution_id},
                           payload={"subtype": "unstarted_rollback"}),
                           lambda item, deadline: {"transition_id": item.transition_id})


def test_deadline_is_published_without_waiting_and_never_extended(registry):
    coordinator.start_runtime()
    deadline = time.monotonic() + .04
    before = time.monotonic()
    coordinator.begin_shutdown(deadline)
    coordinator.begin_shutdown(deadline + 20)
    assert coordinator._attempt_deadline() <= deadline
    assert time.monotonic() - before < .02


def test_completed_drain_lifts_only_its_matching_background_deadline(registry):
    coordinator.start_runtime()
    deadline = time.monotonic() + .01
    coordinator.begin_shutdown(deadline)
    assert coordinator.end_shutdown(deadline + 1) is False
    assert coordinator._attempt_deadline() <= deadline
    assert coordinator.end_shutdown(deadline) is True
    assert coordinator._attempt_deadline() > deadline
    assert coordinator.runtime_status()["stopping"] is False
    assert coordinator.end_shutdown(deadline) is False


def test_missing_original_registry_prevents_new_reservation_and_another_ticket(registry):
    original = execution("lost")
    coordinator.register_execution(original, {"permit_id": original.permit_id, "execution_id": original.execution_id})
    coordinator._REGISTRY.clear()
    with coordinator.reserve_admission() as granted:
        assert granted is False
    another = execution("another")
    with pytest.raises(OperationSettlementFenced):
        coordinator.register_execution(another, {"permit_id": another.permit_id, "execution_id": another.execution_id})
    assert coordinator.responsibility(original) is None
    assert coordinator.active_counts()["registered"] >= 1


def test_carrier_periodically_detects_lost_registry_without_status_poll(registry):
    blocked = threading.Event()

    class Gate:
        def block(self, reason):
            if reason == "settlement_registry_missing":
                blocked.set()

        def unblock(self, reason):
            pass

        def reasons(self):
            return ()

    coordinator.start_runtime(admission=Gate())
    original = execution("lost-periodic")
    coordinator.register_execution(original, {"permit_id": original.permit_id, "execution_id": original.execution_id})
    coordinator._REGISTRY.clear()
    assert blocked.wait(.2)
    assert coordinator.release_eligible(original) is False


def test_explicit_finalization_can_join_stopped_carrier_with_a_new_join_budget(registry):
    domain = domain_for("join_only")
    entered = threading.Event()
    let_exit = threading.Event()
    storage = ModuleType("core.storage.operations.settlements")
    storage.verify_domain = lambda *args, **kwargs: True

    def scan(**kwargs):
        entered.set()
        let_exit.wait(1)

    storage.run_cleanup_once = scan
    import core.storage.operations as storage_package
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        coordinator.start_runtime(domain=domain)
        assert entered.wait(.5)
        original = time.monotonic() + .01
        coordinator.begin_shutdown(original)
        assert coordinator.stop_runtime(original) is False
        assert coordinator._STOP is True
        assert coordinator.end_shutdown(original) is False
        next_deadline = time.monotonic() + .5
        coordinator.begin_finalization(next_deadline)
        assert coordinator._STOP is True
        let_exit.set()
        assert coordinator.stop_runtime(next_deadline) is True
        assert not coordinator._THREAD.is_alive()


def test_admission_reservation_prevents_claim_without_capacity(registry):
    with patch.object(coordinator, "_MAX_RESPONSIBILITIES", 1):
        with coordinator.reserve_admission() as granted:
            assert granted is True
            with coordinator.reserve_admission() as second:
                assert second is False
            job = execution("reserved")
            coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
        with coordinator.reserve_admission() as second:
            assert second is False


def test_status_does_not_acquire_a_lease_lock_held_during_database_io(registry):
    job = execution("lease-io")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    release_lock = threading.Lock()

    class Lease:
        _state = "held"

        @property
        def released(self):
            with release_lock:
                return self._state == "release_confirmed"

    coordinator.register_lease(job, Lease())
    coordinator.settle(job, intent_for(job, status="success"),
                       lambda item, deadline: {"transition_id": item.transition_id})
    with release_lock:
        checked = threading.Event()
        observer = threading.Thread(target=lambda: (coordinator.runtime_status(), checked.set()))
        observer.start()
        assert checked.wait(.1)
    observer.join(1)


def test_same_receipt_remains_confirmable_after_completed_index_is_reclaimed(registry):
    job = execution("history")
    ticket = {"permit_id": job.permit_id, "execution_id": job.execution_id}
    coordinator.register_execution(job, ticket)
    intent = intent_for(job, status="success")
    receipt = coordinator.settle(job, intent, lambda item, deadline: {"transition_id": item.transition_id})
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: setattr(item, "released", True) or True):
        coordinator.start_runtime()
        assert coordinator.drain_runtime(time.monotonic() + 1)
    other = execution("history-other")
    coordinator.register_execution(other, {"permit_id": other.permit_id, "execution_id": other.execution_id})
    assert coordinator.settle(job, intent, lambda item, deadline: pytest.fail("duplicate storage write")) == receipt


def test_durable_cleanup_is_exact_and_cannot_claim_before_physical_handoff(registry):
    job = execution("durable")
    job.settlement_domain = domain_for("durable")
    ticket = {"permit_id": job.permit_id, "execution_id": job.execution_id,
              "ticket_id": "original-ticket", "domain_id": job.settlement_domain.domain_id}
    coordinator.register_execution(job, ticket)
    coordinator.callback_started(job)
    coordinator.settle(job, intent_for(job, status="success"),
                       lambda item, deadline: {"transition_id": item.transition_id})
    assert not coordinator.cleanup_handoff_ready(ticket)
    assert not coordinator.cleanup_handoff_ready({**ticket, "ticket_id": "another-ticket"})
    durable_pending = threading.Event()
    durable_pending.set()
    cleanup_seen = threading.Event()
    storage = ModuleType("core.storage.operations.settlements")
    calls = []

    def run_cleanup_once(*, domain, deadline, permit_id=None, execution_id=None):
        if permit_id is None and execution_id is None:
            return None  # Domain scan has no original owned-item selection.
        assert coordinator.cleanup_handoff_ready(ticket)
        assert domain is job.settlement_domain
        assert (permit_id, execution_id) == (job.permit_id, job.execution_id)
        assert deadline > time.monotonic()
        calls.append("durable")
        cleanup_seen.set()

    def cleanup_blocks_permit(permit_id, execution_id, *, domain, deadline):
        return durable_pending.is_set()

    storage.run_cleanup_once = run_cleanup_once
    storage.cleanup_blocks_permit = cleanup_blocks_permit
    storage.mark_cleanup_handoff = lambda *args, **kwargs: {"handoff": "confirmed"}
    import core.storage.operations as storage_package
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: calls.append("permit") or setattr(item, "released", True) or True):
            coordinator.start_runtime()
            assert cleanup_seen.wait(1)
            assert coordinator.active_counts()["resource_pending"] == 1
            assert not job.released
            durable_pending.clear()
            assert coordinator.drain_runtime(time.monotonic() + 1)
    assert calls[-1] == "permit"


def test_final_lease_thread_must_really_exit_before_permit_can_release(registry):
    job = execution("lease-thread")
    job.settlement_domain = domain_for("lease-thread")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    finish_thread = threading.Event()
    thread = threading.Thread(target=lambda: finish_thread.wait(1))
    thread.start()

    class Lease:
        def __init__(self):
            self._state = "held"
            self._heartbeat_thread = thread

        def mark_release_confirmed(self, receipt=None):
            self._state = "release_confirmed"
            return True

    lease = Lease()
    coordinator.register_lease(job, lease)
    coordinator.settle(job, intent_for(job, status="success"),
                       lambda item, deadline: {"transition_id": item.transition_id})
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    coordinator.start_runtime()
    assert not coordinator.drain_runtime(time.monotonic() + .02)
    assert not coordinator.release_eligible(job)
    assert not job.released
    finish_thread.set()
    thread.join(1)
    coordinator.stop_runtime(time.monotonic() + 1)
    coordinator._THREAD.join(1)
    assert not coordinator._THREAD.is_alive()


def test_mismatched_authoritative_receipt_is_a_conflict_and_preserves_intent(registry):
    job = execution("wrong-receipt")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    intent = intent_for(job, status="success")
    with pytest.raises(OperationSettlementConflict):
        coordinator.settle(job, intent, lambda item, deadline: {"transition_id": "other-transition"})
    assert coordinator.responsibility(job).intent is intent
    assert coordinator.responsibility(job).receipt is None


def test_live_superseded_keeps_original_intent_separate_from_authority_disposition(registry):
    job = execution("superseded")
    job.settlement_domain = domain_for("superseded")
    ticket = {"domain_id": job.settlement_domain.domain_id, "ticket_id": "original-ticket",
              "permit_id": job.permit_id, "execution_id": job.execution_id}
    coordinator.register_execution(job, ticket)
    coordinator.callback_started(job)
    original = seal_intent(kind="terminal", origin=ticket, payload={"status": "success"})
    local_actor_stopped = threading.Event()

    class Actor:
        before_transition = True

        def release(self, deadline=None):
            local_actor_stopped.set()
            return True

    class Lease:
        def __init__(self):
            self._state = "held"

        def mark_disposition_confirmed(self, disposition):
            assert disposition["original_intent_committed"] is False
            assert disposition["lease_disposition"] == "exact_original_token_absent"
            self._state = "release_confirmed"
            return True

    coordinator.register_lease(job, Lease())
    coordinator.register_cleanup(job, Actor(), key="actor", before_transition=True)
    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, original, lambda item, deadline: (_ for _ in ()).throw(OperationSettlementFenced("admin terminal")))
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    storage = ModuleType("core.storage.operations.settlements")
    authority = {
        **ticket,
        "disposition_kind": "live_superseded", "original_intent_committed": False,
        "transition_id": original.transition_id, "request_digest": original.request_digest,
        "lease_disposition": "exact_original_token_absent",
        "result": {"status": "cancelled", "event_uuid": "authoritative-event",
                   "original_intent_committed": False, "resource_disposition": "no_blocking_resources"},
    }
    proofs = []

    def reconcile(item, *, domain, deadline):
        assert item is original
        assert local_actor_stopped.is_set()
        assert coordinator.superseded_handoff_ready(ticket)
        proofs.append(item)
        return authority

    storage.reconcile_superseded = reconcile
    storage.run_cleanup_once = lambda **kwargs: None
    storage.cleanup_blocks_permit = lambda *args, **kwargs: False
    import core.storage.operations as storage_package
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: setattr(item, "released", True) or True):
            coordinator.start_runtime()
            assert coordinator.drain_runtime(time.monotonic() + 1), (coordinator.runtime_status(), proofs)
    state = coordinator.responsibility(job)
    assert state.intent is original
    assert state.receipt is None
    assert state.disposition["result"]["status"] == "cancelled"
    assert state.disposition["original_intent_committed"] is False
    assert proofs == [original]


def test_domain_scanner_keeps_durable_jobs_supervised_after_ticket_reclaimed(registry):
    domain = domain_for("durable")
    job = execution("released-nonblocking")
    job.settlement_domain = domain
    ticket = {"domain_id": domain.domain_id, "permit_id": job.permit_id, "execution_id": job.execution_id}
    coordinator.register_execution(job, ticket)
    coordinator.settle(job, intent_for(job, status="success"),
                       lambda item, deadline: {"transition_id": item.transition_id})
    coordinator.callback_exited(job)
    coordinator.request_release(job)
    handed = threading.Event()
    scanned_after_release = threading.Event()
    storage = ModuleType("core.storage.operations.settlements")

    def mark(ticket, *, domain, deadline):
        assert coordinator.cleanup_handoff_ready(ticket)
        handed.set()
        return {"handoff": "confirmed"}

    def scan(*, domain, deadline, permit_id=None, execution_id=None):
        if permit_id is None and job.released:
            assert handed.is_set()
            scanned_after_release.set()

    storage.mark_cleanup_handoff = mark
    storage.verify_domain = lambda value, **kwargs: True
    storage.run_cleanup_once = scan
    storage.cleanup_blocks_permit = lambda *args, **kwargs: False
    import core.storage.operations as storage_package
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        with patch.object(coordinator, "_release_execution", side_effect=lambda item, reason, deadline: setattr(item, "released", True) or True):
            coordinator.start_runtime(domain=domain)
            assert coordinator.drain_runtime(time.monotonic() + 1)
            other = execution("prune")
            coordinator.register_execution(other, {"permit_id": other.permit_id, "execution_id": other.execution_id})
            assert scanned_after_release.wait(1)
            assert all(item.execution is not job for item in coordinator._REGISTRY.values())


def test_owner_lost_prevents_foreign_domain_cleanup_scan(registry):
    class Gate:
        def reasons(self):
            return ("owner_lost",)

        def block(self, reason):
            pass

        def unblock(self, reason):
            pass

    domain = domain_for("startup")
    storage = ModuleType("core.storage.operations.settlements")
    foreign = threading.Event()
    storage.verify_domain = lambda value, **kwargs: True
    storage.run_cleanup_once = lambda **kwargs: foreign.set()
    import core.storage.operations as storage_package
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        coordinator.start_runtime(domain=domain, admission=Gate())
        assert not foreign.wait(.1)


def test_domain_version_is_verified_before_any_carrier_starts(registry):
    gate = SimpleNamespace(blocked=set())
    gate.block = gate.blocked.add
    gate.unblock = gate.blocked.discard
    domain = SimpleNamespace(domain_id="unsupported-version")
    storage = ModuleType("core.storage.operations.settlements")

    def verify(value, *, deadline):
        assert value is domain
        assert deadline > time.monotonic()
        raise OperationSettlementFenced("unsupported schema version")

    storage.verify_domain = verify
    import core.storage.operations as storage_package
    with patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True):
        with pytest.raises(OperationSettlementFenced):
            coordinator.start_runtime(domain=domain, admission=gate)
    assert "settlement_version" in gate.blocked
    assert coordinator.runtime_status()["alive"] is False


@pytest.mark.parametrize("boundary", ["stopped", "dead", "draining", "owner_lost"])
def test_blocked_domain_rearm_never_revives_or_clears_lifecycle_boundary(boundary):
    domain = domain_for("blocked_lifecycle")
    blocked = {domain.domain_id: "settlement_storage_permission_denied"}
    reasons = (boundary,) if boundary in ("draining", "owner_lost") else ()
    gate = SimpleNamespace(reasons=lambda: reasons)
    carrier = SimpleNamespace(is_alive=lambda: boundary != "dead")
    storage = ModuleType("core.storage.operations.settlements")
    storage.verify_domain = lambda *args, **kwargs: pytest.fail("lifecycle rejection must precede checkout")
    import core.storage.operations as storage_package
    with patch.object(coordinator, "_CARRIER_ERROR", ""), patch.object(
            coordinator, "_STARTED", False), patch.object(coordinator, "_STOP_WITH_PENDING", False), patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True), patch.object(
            coordinator, "_SCAN_BLOCKED", blocked), patch.object(
            coordinator, "_THREAD", carrier), patch.object(
            coordinator, "_STOP", boundary == "stopped"), patch.object(coordinator, "_ADMISSION", gate):
        assert coordinator.start_runtime(domain=domain) is False
        assert blocked == {domain.domain_id: "settlement_storage_permission_denied"}


def test_blocked_domain_rearm_rechecks_lifecycle_after_capability_probe():
    domain = domain_for("blocked_probe_race")
    blocked = {domain.domain_id: "settlement_storage_permission_denied"}
    gate = SimpleNamespace(reasons=lambda: ())
    carrier = SimpleNamespace(is_alive=lambda: True)
    storage = ModuleType("core.storage.operations.settlements")
    def verify(*args, **kwargs):
        coordinator._STOP = True
    storage.verify_domain = verify
    import core.storage.operations as storage_package
    with patch.object(coordinator, "_CARRIER_ERROR", ""), patch.object(
            coordinator, "_STARTED", False), patch.object(coordinator, "_STOP_WITH_PENDING", False), patch.dict(sys.modules, {"core.storage.operations.settlements": storage}), patch.object(
            storage_package, "settlements", storage, create=True), patch.object(
            coordinator, "_SCAN_BLOCKED", blocked), patch.object(
            coordinator, "_THREAD", carrier), patch.object(
            coordinator, "_STOP", False), patch.object(coordinator, "_ADMISSION", gate):
        assert coordinator.start_runtime(domain=domain) is False
        assert blocked == {domain.domain_id: "settlement_storage_permission_denied"}


def test_stop_remembers_unverified_scan_even_without_local_registry():
    with patch.object(coordinator, "_REGISTRY", {}), patch.object(
            coordinator, "_EXPECTED", set()), patch.object(coordinator, "_REGISTRY_ERROR", ""), patch.object(
            coordinator, "_SCAN_BLOCKED", {"blocked-domain": "settlement_storage_permission_denied"}), patch.object(
            coordinator, "_SCAN_INFLIGHT", 0), patch.object(coordinator, "_THREAD", None), patch.object(
            coordinator, "_DEADLINE", None), patch.object(coordinator, "_STOP", False), patch.object(
            coordinator, "_STOP_WITH_PENDING", False):
        assert coordinator.stop_runtime(time.monotonic()) is False
        assert coordinator._STOP_WITH_PENDING is True


@pytest.mark.parametrize("healthy", [False, True])
def test_same_intent_can_retry_blocked_superseded_cleanup_once_without_receipt(registry, healthy):
    job = execution("superseded_blocked")
    ticket = {"permit_id": job.permit_id, "execution_id": job.execution_id}
    item = coordinator.register_execution(job, ticket)
    frozen = intent_for(job, status="success")
    item.intent = frozen
    item._disposition = coordinator._freeze({
        "disposition_kind": "live_superseded", "original_intent_committed": False,
        "result": {"original_intent_committed": False}})
    item.callback_exited = True
    item.error_code = item._blocked_error = "settlement_storage_permission_denied"
    item.next_attempt = time.monotonic() + 3600
    calls = []
    class PermissionDenied(Exception):
        sqlstate = "42501"
    def release(**kwargs):
        calls.append(kwargs)
        if not healthy:
            raise PermissionDenied("private synthetic text")
        return True
    coordinator.register_cleanup(job, SimpleNamespace(release=release), key="exact-original")
    with pytest.raises(OperationSettlementFenced, match="settlement_original_intent_superseded"):
        coordinator.settle(job, frozen, lambda *args: pytest.fail("superseded intent must never resubmit"))
    assert len(calls) == 1
    assert item.intent is frozen
    assert item.receipt is None
    assert item.disposition["original_intent_committed"] is False
    assert bool(item._blocked_error) is not healthy


@pytest.mark.parametrize("healthy", [False, True])
def test_same_intent_rearms_pretransition_cleanup_once_and_retains_original_submit(registry, healthy):
    job = execution("pretransition_blocked")
    item = coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    frozen = intent_for(job, status="success")
    calls, submits = [], []
    repaired = [False]
    class PermissionDenied(Exception):
        sqlstate = "42501"
    def release(**kwargs):
        calls.append(kwargs)
        if not repaired[0]:
            raise PermissionDenied("private synthetic text")
        return True
    def submit(intent, deadline):
        submits.append(intent)
        return {"transition_id": intent.transition_id}
    coordinator.register_cleanup(job, SimpleNamespace(release=release),
                                 key="exact-original-before", before_transition=True)
    coordinator.callback_started(job)
    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, frozen, submit)
    coordinator.callback_exited(job)
    coordinator._progress(item)
    assert len(calls) == 1 and not submits
    assert item._blocked_error == "settlement_storage_permission_denied"
    repaired[0] = healthy
    with pytest.raises(OperationSettlementPending):
        coordinator.settle(job, frozen, lambda *args: pytest.fail("must preserve original submit adapter"))
    assert len(calls) == 2 and not submits
    assert item.intent is frozen
    if healthy:
        assert item.error_code == "" and item._blocked_error == ""
        coordinator._progress(item)
        assert submits == [frozen]
        assert item.receipt["transition_id"] == frozen.transition_id
    else:
        assert item.error_code == item._blocked_error == "settlement_storage_permission_denied"
        item.next_attempt = 0
        coordinator._progress(item)
        assert len(calls) == 2 and not submits


def test_initial_unmanaged_reservation_and_callback_remain_compatible(registry):
    with coordinator.reserve_admission() as granted:
        assert granted is True
    job = execution("unmanaged")
    coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    assert coordinator.callback_started(job) is True


def test_unexpected_carrier_exit_is_sticky_even_without_local_registry(registry):
    gate = SimpleNamespace(blocked=set())
    gate.block = gate.blocked.add
    gate.unblock = gate.blocked.discard
    gate.reasons = lambda: tuple(gate.blocked)
    with patch.object(coordinator, "_STARTED", True), patch.object(
            coordinator, "_THREAD", SimpleNamespace(is_alive=lambda: False)), patch.object(
            coordinator, "_ADMISSION", gate):
        with coordinator.reserve_admission() as granted:
            assert granted is False
        status = coordinator.runtime_status()
        assert status["error_code"] == "settlement_carrier_unavailable"
        assert status["counts"]["registered"] >= 1
        assert "settlement_carrier_unavailable" in gate.blocked
        assert coordinator.start_runtime() is False


def test_actual_managed_carrier_death_blocks_claims_and_callbacks_with_intact_registry(registry):
    from core.runtime.context import AdmissionGate
    gate = AdmissionGate()
    job = execution("carrier_owned")
    item = coordinator.register_execution(job, {"permit_id": job.permit_id, "execution_id": job.execution_id})
    assert coordinator.callback_started(job)
    assert coordinator.start_runtime(admission=gate)
    gate.unblock("startup")
    assert gate.is_open()
    carrier = coordinator._THREAD
    with coordinator._CONDITION:
        coordinator._STOP = True
        coordinator._CONDITION.notify_all()
    carrier.join(.5)
    assert not carrier.is_alive()
    assert set(coordinator._REGISTRY) == coordinator._EXPECTED
    with coordinator.reserve_admission() as granted:
        assert granted is False
    assert not gate.is_open()
    assert coordinator.callback_started(execution("new_callback")) is False
    status = coordinator.runtime_status()
    assert status["error_code"] == "settlement_carrier_unavailable"
    assert status["counts"]["registered"] == 1
    assert coordinator.drain_runtime(time.monotonic()) is False
    assert coordinator.stop_runtime(time.monotonic()) is False
    assert coordinator.start_runtime() is False
    assert coordinator.responsibility(job) is item and not job.released
    frozen = intent_for(job, status="success")
    # Only the exact admitted owner may confirm its original local settlement.
    receipt = coordinator.settle(job, frozen,
        lambda intent, deadline: {"transition_id": intent.transition_id})
    assert receipt["transition_id"] == frozen.transition_id
    assert coordinator._CARRIER_ERROR == "settlement_carrier_unavailable"
