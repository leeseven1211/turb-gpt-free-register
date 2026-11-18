"""One lifecycle-owned carrier for execution-local storage settlement.

The registry retains original responsibilities; it never queues or invokes a
business handler. Storage and physical release run outside the registry lock,
so status and bounded shutdown remain available during uninterruptible I/O.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import inspect
import threading
import time
from typing import Any, Callable
from types import SimpleNamespace

from .settlement_contracts import (
    OperationSettlementConflict, OperationSettlementFenced,
    OperationSettlementPending, SettlementIntent, _freeze, same_intent, thaw, classify_failure,
)


@dataclass(eq=False)
class _Cleanup:
    handle: Any = field(repr=False)
    key: str
    blocking: bool
    before_transition: bool
    confirmed: bool = False


@dataclass(eq=False)
class ExecutionResponsibility:
    execution: Any = field(repr=False)
    ticket: Mapping = field(repr=False)
    intent: SettlementIntent | None = None
    _receipt: Any = field(default=None, repr=False)
    _disposition: Any = field(default=None, repr=False)
    _submit: Callable | None = field(default=None, repr=False)
    _leases: list = field(default_factory=list, repr=False)
    _cleanups: list = field(default_factory=list, repr=False)
    callback_active: bool = False
    _callback_started: bool = False
    callback_exited: bool = False
    release_requested: bool = False
    released: bool = False
    inflight: bool = False
    _release_inflight: bool = False
    error_code: str = ""
    stage: str = "callback"
    created_at: float = field(default_factory=time.monotonic)
    next_attempt: float = 0.0
    attempts: int = 0
    reason: str = "worker_exit"
    _durable_pending: bool = False
    _reconcile_required: bool = False
    _blocked_error: str = ""
    _blocked_cleanup: Any = field(default=None, repr=False)

    @property
    def receipt(self):
        return thaw(self._receipt)

    @property
    def disposition(self):
        return thaw(self._disposition)


_REGISTRY: dict[tuple[str, str, str], ExecutionResponsibility] = {}
_EXPECTED: set[tuple[str, str, str]] = set()
_REGISTRY_ERROR = ""
_CARRIER_ERROR = ""
_DOMAINS = {}
_SCAN_INFLIGHT = 0
_SCAN_ERROR = ""
_SCAN_NEXT: dict[str, float] = {}
_SCAN_FAILURES: dict[str, int] = {}
_SCAN_BLOCKED: dict[str, str] = {}
_SCAN_DIAGNOSTICS: dict[str, dict] = {}
_MAX_DOMAINS = 64
_LOCK = threading.RLock()
_CONDITION = threading.Condition(_LOCK)
_THREAD: threading.Thread | None = None
_STOP = False
_STOP_WITH_PENDING = False
_STARTED = False
_DEADLINE: float | None = None
_ADMISSION = None
_MAX_RESPONSIBILITIES = 4096
_ATTEMPT_SECONDS = 5.0
_RESERVATIONS = 0
_RESERVATION: ContextVar[list | None] = ContextVar("settlement_admission_reservation", default=None)


def _key(execution, ticket=None):
    domain = getattr(execution, "settlement_domain", None)
    domain_id = getattr(domain, "domain_id", "") or (ticket or {}).get("domain_id", "")
    return (str(domain_id), str(execution.permit_id), str(execution.execution_id))


def _find(execution):
    key = _key(execution)
    _check_integrity()
    item = _REGISTRY.get(key)
    if item is None and key in _EXPECTED:
        _check_integrity()
    if item is None and not key[0]:
        matches = [item for ident, item in _REGISTRY.items() if ident[1:] == key[1:]]
        item = matches[0] if len(matches) == 1 else None
    if item is None:
        retired = getattr(execution, "_settlement_responsibility", None)
        if retired is not None and retired.execution is execution and retired.released:
            return retired
    return item


def responsibility(execution):
    with _LOCK:
        return _find(execution)


def register_execution(execution, ticket):
    global _RESERVATIONS
    frozen = _freeze(ticket)
    if not isinstance(frozen, Mapping):
        raise TypeError("settlement ticket must be a mapping")
    for name in ("permit_id", "execution_id"):
        if str(frozen.get(name, "")) != str(getattr(execution, name)):
            raise OperationSettlementFenced("settlement_ticket_identity_mismatch")
    with _CONDITION:
        key = _key(execution, frozen)
        if not _check_integrity():
            raise OperationSettlementFenced("settlement_registry_missing")
        if key in _EXPECTED and key not in _REGISTRY:
            _check_integrity()
            raise OperationSettlementFenced("settlement_registry_missing")
        prior = _REGISTRY.get(key)
        if prior is not None:
            if prior.ticket != frozen:
                raise OperationSettlementConflict("settlement_ticket_conflict")
            return prior
        # Never evict pending in-memory results to pretend they are durable.
        for ident in [ident for ident, item in _REGISTRY.items() if item.released]:
            _REGISTRY.pop(ident)
        reservation = _RESERVATION.get()
        reserved = bool(reservation is not None and not reservation[0])
        if len(_EXPECTED) + _RESERVATIONS - int(reserved) >= _MAX_RESPONSIBILITIES:
            if _ADMISSION is not None:
                _ADMISSION.block("settlement")
            raise OperationSettlementPending("settlement_registry_capacity")
        item = ExecutionResponsibility(execution, frozen)
        domain = getattr(execution, "settlement_domain", None)
        if domain is not None:
            _remember_domain(domain)
        setattr(execution, "_settlement_responsibility", item)
        _REGISTRY[key] = item
        _EXPECTED.add(key)
        if reserved:
            reservation[0] = True
            _RESERVATIONS -= 1
        _update_admission()
        _CONDITION.notify_all()
        return item


@contextmanager
def reserve_admission():
    """Reserve registry capacity before an exact participating DB claim."""
    global _RESERVATIONS
    with _CONDITION:
        active = len(_EXPECTED)
        granted = (_check_integrity() and _check_carrier_health()
                   and not (_THREAD is not None and _STOP)
                   and active + _RESERVATIONS < _MAX_RESPONSIBILITIES)
        if granted:
            _RESERVATIONS += 1
        elif _ADMISSION is not None:
            _ADMISSION.block("settlement")
    reservation = [False]
    token = _RESERVATION.set(reservation if granted else None)
    try:
        yield granted
    finally:
        _RESERVATION.reset(token)
        if granted:
            with _CONDITION:
                if not reservation[0]:
                    _RESERVATIONS -= 1
                _update_admission()
                _CONDITION.notify_all()


def callback_started(execution):
    with _CONDITION:
        if (not _check_integrity() or not _check_carrier_health()
                or (_THREAD is not None and _STOP)):
            return False
        item = _find(execution)
        if item is None:
            return True
        if item.callback_exited:
            return False
        if item.intent is not None and item.intent.payload.get("subtype") == "unstarted_rollback":
            return False
        if item.callback_active:
            return False
        item.callback_active = True
        item._callback_started = True
        _CONDITION.notify_all()
        return True


def callback_exited(execution):
    with _CONDITION:
        item = _find(execution)
        if item is not None:
            item.callback_active = False
            item.callback_exited = True
            _update_admission()
            _CONDITION.notify_all()


def _lease_confirmed(lease):
    # Native lease state is changed under its own lock, which deliberately spans
    # database I/O. Read the atomically assigned state without taking that lock.
    data = vars(lease)
    confirmed = (data.get("_state") == "release_confirmed"
                 or data.get("release_confirmed") is True
                 or data.get("released") is True or data.get("_released") is True)
    heartbeat = data.get("_heartbeat_thread")
    return bool(confirmed and (heartbeat is None or not heartbeat.is_alive()))


def _confirmed(resource, result=None):
    if result is False:
        return False
    data = vars(resource)
    return bool(data.get("release_confirmed") is True
                or data.get("released") is True or data.get("_released") is True
                or result is True)


def register_lease(execution, lease, *, scope_kind="final"):
    if scope_kind not in {"final", "step"}:
        raise ValueError("unknown settlement lease scope")
    with _CONDITION:
        item = _find(execution)
        if item is None:
            raise OperationSettlementFenced("settlement_responsibility_missing")
        if item.intent is not None:
            raise OperationSettlementConflict("settlement_already_frozen")
        if any(old is lease for old, _ in item._leases):
            return lease
        if any(not _lease_confirmed(old) for old, _ in item._leases):
            raise OperationSettlementPending("settlement_previous_scope_unconfirmed")
        item._leases.append((lease, scope_kind))
        _CONDITION.notify_all()
        return lease


def register_cleanup(execution, cleanup, *, key, blocking=True, before_transition=False):
    """Attach one existing, identity-bound local cleanup handle.

    ``cleanup`` is intentionally an object with a ``release`` method rather
    than a callable or serialized work item.  The carrier may invoke only
    this exact handle after callback ownership has ended.
    """
    if not key or not isinstance(key, str):
        raise ValueError("cleanup key is required")
    release = getattr(cleanup, "release", None)
    if not callable(release):
        raise TypeError("cleanup must expose release(deadline=...)")
    before_transition = bool(before_transition or getattr(cleanup, "before_transition", False))
    with _CONDITION:
        item = _find(execution)
        if item is None:
            raise OperationSettlementFenced("settlement_responsibility_missing")
        if item.released or item._release_inflight:
            raise OperationSettlementConflict("settlement_release_already_started")
        for old in item._cleanups:
            if old.key == key:
                if (old.handle is cleanup and old.blocking == bool(blocking)
                        and old.before_transition == before_transition):
                    return cleanup
                raise OperationSettlementConflict("settlement_cleanup_conflict")
        if before_transition and item._receipt is not None:
            raise OperationSettlementConflict("settlement_transition_already_confirmed")
        item._cleanups.append(_Cleanup(cleanup, key, bool(blocking), before_transition))
        _update_admission()
        _CONDITION.notify_all()
        return cleanup


def _attempt_deadline():
    candidate = time.monotonic() + _ATTEMPT_SECONDS
    return min(candidate, _DEADLINE) if _DEADLINE is not None else candidate


def _remember_domain(domain):
    domain_id = str(domain.domain_id)
    prior = _DOMAINS.get(domain_id)
    if prior is not None and prior != domain:
        raise OperationSettlementConflict("settlement_domain_identity_conflict")
    if prior is None and len(_DOMAINS) >= _MAX_DOMAINS:
        raise OperationSettlementPending("settlement_domain_capacity")
    _DOMAINS[domain_id] = domain


_PERMANENT_CODES = frozenset({
    "settlement_storage_permission_denied", "settlement_storage_authentication_failed",
    "settlement_storage_sqlstate_unknown", "operation_settlement_fenced", "operation_settlement_conflict",
})


def _failure(item, exc):
    # Error strings can contain a DSN, SQL parameters, tokens or remote data.
    if isinstance(exc, OperationSettlementConflict):
        item.error_code = exc.code
        item._reconcile_required = True
    elif isinstance(exc, OperationSettlementFenced):
        item.error_code = exc.code
        item._reconcile_required = True
    else:
        item.error_code, permanent = classify_failure(exc)
        item._blocked_error = item.error_code if permanent else ""
    item.attempts += 1
    item.next_attempt = time.monotonic() + min(5.0, 0.05 * 2 ** min(item.attempts, 7))


def _update_admission():
    if _ADMISSION is not None:
        full = len(_EXPECTED) + _RESERVATIONS >= _MAX_RESPONSIBILITIES
        blocked = (not _check_carrier_health() or (_THREAD is not None and _STOP)
                   or full or bool(_SCAN_BLOCKED) or any(not item.released and (item.error_code or
                      (item.intent is not None and (not _has_authority(item) or _resources_pending(item)
                       or (item.release_requested and item.callback_exited))))
                      for item in _REGISTRY.values()))
        if blocked:
            _ADMISSION.block("settlement")
        else:
            _ADMISSION.unblock("settlement")


def _check_integrity():
    """Independent bounded membership evidence never reconstructs ownership."""
    global _REGISTRY_ERROR
    actual = {key for key, item in _REGISTRY.items() if not item.released}
    if actual != _EXPECTED:
        _REGISTRY_ERROR = "settlement_registry_missing"
    if _REGISTRY_ERROR and _ADMISSION is not None:
        _ADMISSION.block("settlement_registry_missing")
    return not _REGISTRY_ERROR


def _check_carrier_health():
    """Retain a managed carrier's lost verification without adopting its work."""
    global _CARRIER_ERROR
    alive = _THREAD is not None and _THREAD.is_alive()
    pending = bool(_EXPECTED or _blocking_scans() or _SCAN_INFLIGHT
                   or any(not item.released for item in _REGISTRY.values()))
    if ((_STARTED or _STOP_WITH_PENDING) and not alive
            and (not _STOP or pending)):
        _CARRIER_ERROR = "settlement_carrier_unavailable"
    if _CARRIER_ERROR and _ADMISSION is not None:
        _ADMISSION.block("settlement_carrier_unavailable")
    return not _CARRIER_ERROR


def _submit_once(item):
    try:
        receipt = item._submit(item.intent, _attempt_deadline())
        if not isinstance(receipt, Mapping):
            raise OperationSettlementPending("settlement_receipt_missing")
        if str(receipt.get("transition_id", "")) != item.intent.transition_id:
            raise OperationSettlementConflict("settlement_receipt_identity_mismatch")
        if receipt.get("request_digest", item.intent.request_digest) != item.intent.request_digest:
            raise OperationSettlementConflict("settlement_receipt_digest_mismatch")
        frozen = _freeze(receipt)
    except Exception as exc:
        with _CONDITION:
            item.inflight = False
            _failure(item, exc)
            _update_admission()
            _CONDITION.notify_all()
        if isinstance(exc, (OperationSettlementConflict, OperationSettlementFenced)):
            raise
        raise OperationSettlementPending("operation_settlement_pending") from None
    with _CONDITION:
        item._receipt = frozen
        item._blocked_error = ""
        item._reconcile_required = False
        item._durable_pending = getattr(item.execution, "settlement_domain", None) is not None
        item.error_code = ""
        item.inflight = False
        item.next_attempt = 0.0
        _update_admission()
        _CONDITION.notify_all()
    return thaw(frozen)


def settle(execution, intent, submit):
    if not isinstance(intent, SettlementIntent):
        raise TypeError("settle requires a sealed intent")
    retry_resources = False
    durable_retry = None
    with _CONDITION:
        item = _find(execution)
        if item is None:
            raise OperationSettlementFenced("settlement_responsibility_missing")
        if item.intent is not None and not same_intent(item.intent, intent):
            raise OperationSettlementConflict("settlement_intent_conflict")
        rollback = intent.payload.get("subtype") == "unstarted_rollback"
        if rollback and item._callback_started:
            raise OperationSettlementConflict("settlement_callback_already_started")
        for name in ("permit_id", "execution_id"):
            if str(intent.origin.get(name, "")) != str(item.ticket.get(name, "")):
                raise OperationSettlementFenced("settlement_origin_mismatch")
        if item.inflight:
            raise OperationSettlementPending("operation_settlement_pending")
        if item._receipt is not None:
            if not item._blocked_error:
                return thaw(item._receipt)
            # Explicit repeated same-intent confirmation is the only local
            # rearm boundary; it never invokes a business callback.
            item._blocked_error = ""
            item.error_code = ""
            item.next_attempt = 0.0
            retry_resources = True
            durable_retry = item._blocked_cleanup
        if item._disposition is not None and item._blocked_error in _PERMANENT_CODES:
            # Supersession grants resource authority, never a terminal receipt.
            # Explicit same-intent confirmation may retry only that cleanup.
            item._blocked_error = ""
            item.error_code = ""
            item.next_attempt = 0.0
            retry_resources = True
        if item._disposition is not None and not retry_resources:
            raise OperationSettlementFenced("settlement_original_intent_superseded")
        if item.intent is None:
            item.intent, item._submit = intent, submit
        if rollback:
            # Winning this lock proves the callback has never started and
            # irrevocably closes its admission, including a cancelled future.
            item.callback_exited = True
        precleanup = _precleanup_pending(item)
        if precleanup and item._blocked_error in _PERMANENT_CODES:
            item._blocked_error = ""
            item.error_code = ""
            item.next_attempt = 0.0
            retry_resources = True
        if precleanup and not retry_resources:
            item.stage = "resources"
            item.error_code = item._blocked_error or "settlement_cleanup_pending"
            _update_admission()
            _CONDITION.notify_all()
            raise OperationSettlementPending("operation_settlement_pending")
        if not retry_resources:
            item._blocked_error = ""
            item.inflight = True
            item.stage = "settlement"
            _update_admission()
            _CONDITION.notify_all()
    if retry_resources:
        if durable_retry is not None:
            try:
                retry_cleanup(domain=execution.settlement_domain, identity=durable_retry)
            except Exception as exc:
                with _CONDITION:
                    _failure(item, exc)
                    _update_admission()
                raise OperationSettlementPending("operation_settlement_pending") from None
            item._blocked_cleanup = None
        _progress(item)
        if item._disposition is not None:
            raise OperationSettlementFenced("settlement_original_intent_superseded")
        if item.error_code or item._receipt is None:
            raise OperationSettlementPending("operation_settlement_pending")
        return item.receipt
    return _submit_once(item)


def _resources_pending(item):
    return (any(not _lease_confirmed(lease) for lease, _ in item._leases)
            or any(cleanup.blocking and not _cleanup_confirmed(cleanup) for cleanup in item._cleanups)
            or item._durable_pending)


def cleanup_handoff_ready(ticket):
    """Prove local ownership transfer for this exact persisted obligation."""
    if not isinstance(ticket, Mapping):
        return False
    identity = SimpleNamespace(permit_id=ticket.get("permit_id", ""),
                               execution_id=ticket.get("execution_id", ""),
                               settlement_domain=SimpleNamespace(domain_id=ticket.get("domain_id", "")))
    with _LOCK:
        item = _find(identity)
        if item is None or not _has_authority(item) or not item.callback_exited or item.callback_active:
            return False
        if ticket.get("ticket_id") and ticket.get("ticket_id") != item.ticket.get("ticket_id"):
            return False
        return (all(_lease_confirmed(lease) for lease, _ in item._leases)
                and all(not cleanup.blocking or _cleanup_confirmed(cleanup) for cleanup in item._cleanups))


def _has_authority(item):
    return item._receipt is not None or item._disposition is not None


def superseded_handoff_ready(origin):
    """Prove actors stopped while leaving final-token authority to storage."""
    if not isinstance(origin, Mapping):
        return False
    identity = SimpleNamespace(
        permit_id=origin.get("permit_id", ""), execution_id=origin.get("execution_id", ""),
        settlement_domain=SimpleNamespace(domain_id=origin.get("domain_id", "")))
    with _LOCK:
        item = _find(identity)
        if item is None or item.intent is None or not item.callback_exited or item.callback_active:
            return False
        if origin.get("ticket_id") != item.ticket.get("ticket_id"):
            return False
        for key in ("run_uuid", "run_id", "task_id", "domain_id"):
            if key in item.intent.origin and origin.get(key) != item.intent.origin[key]:
                return False
        if origin.get("transition_id", item.intent.transition_id) != item.intent.transition_id:
            return False
        if origin.get("request_digest", item.intent.request_digest) != item.intent.request_digest:
            return False
        return all(not cleanup.blocking or _cleanup_confirmed(cleanup) for cleanup in item._cleanups)


def _cleanup_confirmed(cleanup):
    return cleanup.confirmed or _confirmed(cleanup.handle)


def _precleanup_pending(item):
    return (any(cleanup.before_transition and not _cleanup_confirmed(cleanup)
                for cleanup in item._cleanups)
            or bool(item.intent is not None
                    and item.intent.origin.get("lease_requirement") == "step_release_unconfirmed"
                    and any(kind == "step" and not _lease_confirmed(lease)
                            for lease, kind in item._leases)))


def _run_cleanups(item, *, before_transition):
    if (before_transition and item.intent is not None
            and item.intent.origin.get("lease_requirement") == "step_release_unconfirmed"):
        for lease, kind in item._leases:
            if kind != "step" or _lease_confirmed(lease):
                continue
            _call_cleanup(lease.release, deadline=_attempt_deadline())
            if not _lease_confirmed(lease):
                raise OperationSettlementPending("settlement_step_scope_unconfirmed")
    for cleanup in item._cleanups:
        if cleanup.before_transition != before_transition or _cleanup_confirmed(cleanup):
            continue
        result = _call_cleanup(cleanup.handle.release, deadline=_attempt_deadline())
        if not _confirmed(cleanup.handle, result):
            raise OperationSettlementPending("settlement_cleanup_unconfirmed")
        with _LOCK:
            cleanup.confirmed = True


def release_eligible(execution):
    with _LOCK:
        item = _find(execution)
        return bool(item is not None and item.callback_exited and not item.callback_active
                    and _has_authority(item) and not item.inflight
                    and not item.error_code and not _resources_pending(item))


def request_release(execution, *, reason="worker_exit"):
    with _CONDITION:
        item = _find(execution)
        if item is None:
            return False
        item.release_requested = True
        item.reason = str(reason)
        _update_admission()
        _CONDITION.notify_all()
        return item.released


def _release_execution(execution, reason, deadline):
    # This adapter invokes only the gated local permit repository path.
    from .concurrency import release_execution
    return release_execution(execution, reason=reason, deadline=deadline)


def _call_cleanup(method, receipt=None, deadline=None):
    parameters = inspect.signature(method).parameters
    keywords = any(item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values())
    kwargs = {"deadline": deadline} if "deadline" in parameters or keywords else {}
    if receipt is not None and ("receipt" in parameters or keywords):
        kwargs["receipt"] = receipt
    return method(**kwargs)


def _join_lease(lease):
    heartbeat = vars(lease).get("_heartbeat_thread")
    if heartbeat is not None and heartbeat is not threading.current_thread():
        heartbeat.join(max(0.0, _attempt_deadline() - time.monotonic()))


def _reconcile_once(item):
    domain = getattr(item.execution, "settlement_domain", None)
    if domain is None:
        raise OperationSettlementFenced("settlement_original_domain_missing")
    _run_cleanups(item, before_transition=True)
    _run_cleanups(item, before_transition=False)
    from core.storage.operations import settlements
    disposition = settlements.reconcile_superseded(
        item.intent, domain=domain, deadline=_attempt_deadline())
    if not isinstance(disposition, Mapping):
        raise OperationSettlementPending("settlement_supersession_unproved")
    if disposition.get("disposition_kind") == "original_receipt":
        receipt = disposition.get("receipt")
        if (not isinstance(receipt, Mapping)
                or receipt.get("transition_id") != item.intent.transition_id
                or receipt.get("request_digest", item.intent.request_digest) != item.intent.request_digest):
            raise OperationSettlementConflict("settlement_receipt_identity_mismatch")
        with _LOCK:
            item._receipt = _freeze(receipt)
            item._durable_pending = True
    else:
        result = disposition.get("result")
        if (disposition.get("disposition_kind") != "live_superseded"
                or disposition.get("original_intent_committed") is not False
                or not isinstance(result, Mapping)
                or result.get("original_intent_committed") is not False
                or not result.get("event_uuid")
                or disposition.get("transition_id", result.get("transition_id")) != item.intent.transition_id
                or disposition.get("request_digest", result.get("request_digest")) != item.intent.request_digest
                or disposition.get("lease_disposition", result.get("lease_disposition")) != "exact_original_token_absent"
                or result.get("resource_disposition") not in {"no_blocking_resources", "cleanup_pending"}):
            raise OperationSettlementConflict("settlement_supersession_proof_mismatch")
        for key in ("domain_id", "permit_id", "execution_id", "ticket_id", "run_id", "run_uuid"):
            if key in item.intent.origin and str(disposition.get(key, "")) != str(item.intent.origin[key]):
                raise OperationSettlementConflict("settlement_supersession_identity_mismatch")
        with _LOCK:
            item._disposition = _freeze(disposition)
            item._durable_pending = result["resource_disposition"] != "no_blocking_resources"
    with _LOCK:
        item._reconcile_required = False
        item.error_code = ""
        item.next_attempt = 0.0


def _progress(item):
    with _CONDITION:
        if item.released or item.inflight or item.next_attempt > time.monotonic():
            return
        if item._blocked_error:
            return
        if item._reconcile_required:
            if not item.callback_exited or item.callback_active:
                return
            item.inflight = True
            action = "reconcile"
        elif _precleanup_pending(item):
            if not item.callback_exited or item.callback_active:
                return
            item.inflight = True
            action = "precleanup"
        elif item.intent is not None and not _has_authority(item):
            item.inflight = True
            action = "submit"
        elif _has_authority(item) and item.callback_exited and not item.callback_active:
            item.inflight = True
            action = "cleanup"
        else:
            return
    if action == "submit":
        try:
            _submit_once(item)
        except (OperationSettlementPending, OperationSettlementConflict, OperationSettlementFenced):
            pass
        return
    try:
        if action == "reconcile":
            _reconcile_once(item)
            return
        if action == "precleanup":
            _run_cleanups(item, before_transition=True)
            with _CONDITION:
                item.error_code = ""
                item.stage = "settlement"
                item.next_attempt = 0.0
            return
        # Callback exit transfers handle ownership before the carrier touches
        # lease heartbeat or pending step release.
        for lease, kind in item._leases:
            if _lease_confirmed(lease):
                continue
            if kind == "final":
                method_name = "mark_release_confirmed" if item._receipt is not None else "mark_disposition_confirmed"
                method = getattr(lease, method_name, None)
                if method is None:
                    raise OperationSettlementPending("settlement_final_scope_unconfirmed")
                if item._receipt is not None:
                    _call_cleanup(method, receipt=item.receipt, deadline=_attempt_deadline())
                else:
                    method(item.disposition)
            else:
                result = _call_cleanup(lease.release, deadline=_attempt_deadline())
            _join_lease(lease)
            if not _lease_confirmed(lease):
                raise OperationSettlementPending("settlement_scope_unconfirmed")
        _run_cleanups(item, before_transition=False)
        domain = getattr(item.execution, "settlement_domain", None)
        if domain is not None:
            from core.storage.operations import settlements
            if (item._disposition is not None
                    and thaw(item._disposition).get("result", {}).get("resource_disposition") == "cleanup_pending"):
                # A superseded disposition may have been created while an
                # original resource was still reconciliation_required.
                # Readback is pure and lets storage append the exact resource
                # confirmation after its own lock/CAS proof.
                refreshed = settlements.reconcile_superseded(
                    item.intent, domain=domain, deadline=_attempt_deadline())
                if isinstance(refreshed, Mapping) and refreshed.get("disposition_kind") == "live_superseded":
                    with _LOCK:
                        item._disposition = _freeze(refreshed)
            if item._receipt is not None:
                handoff = settlements.mark_cleanup_handoff(
                    item.ticket, domain=domain, deadline=_attempt_deadline())
                if not handoff:
                    raise OperationSettlementPending("settlement_cleanup_handoff_unconfirmed")
                cleanup_outcome = settlements.run_cleanup_once(
                    domain=domain, deadline=_attempt_deadline(),
                    permit_id=item.execution.permit_id, execution_id=item.execution.execution_id)
                with _LOCK:
                    cleanup_result = _cleanup_failure_result(cleanup_outcome)
                    if (_record_cleanup_result(domain, cleanup_result, scoped=True)
                            and cleanup_result.get("blocks_permit", True)):
                        item._durable_pending = True
                        item.error_code = cleanup_result.get("error_code") or "settlement_storage_unavailable"
                        item._blocked_error = item.error_code if cleanup_result.get("blocked") else ""
                        item._blocked_cleanup = (_freeze(cleanup_result["identity"])
                                                 if item._blocked_error and cleanup_result.get("identity") else None)
                        item.attempts += 1
                        item.next_attempt = time.monotonic() + float(cleanup_result.get("retry_after_seconds") or .2)
                        return
                    if cleanup_result is None:
                        detail = _SCAN_DIAGNOSTICS.get(domain.domain_id, {})
                        identity = detail.get("identity") or {}
                        if (_SCAN_BLOCKED.get(domain.domain_id) not in _PERMANENT_CODES
                                and (not detail.get("durable")
                                     or (identity.get("permit_id") == item.execution.permit_id
                                         and identity.get("execution_id") == item.execution.execution_id))):
                            # Owned compensation remains allowed after owner
                            # loss. Its successful scoped DB read can retire a
                            # transport failure without reopening domain scans.
                            _clear_scan_diagnostic(domain)
            blocks = settlements.cleanup_blocks_permit(
                item.execution.permit_id, item.execution.execution_id,
                domain=domain, deadline=_attempt_deadline())
            with _LOCK:
                item._durable_pending = bool(blocks)
            if blocks:
                raise OperationSettlementPending("settlement_durable_cleanup_pending")
        with _CONDITION:
            item.inflight = False
            item.error_code = ""
            item.stage = "permit"
            eligible = item.release_requested and release_eligible(item.execution)
            item._release_inflight = eligible
        if eligible:
            _release_execution(item.execution, item.reason, _attempt_deadline())
            if not getattr(item.execution, "released", False):
                code = getattr(item.execution, "_permit_release_error_code", "")
                if code in _PERMANENT_CODES:
                    with _LOCK:
                        item.error_code = code
                        item._blocked_error = code
                        item.attempts += 1
                    raise OperationSettlementPending("settlement_permit_unconfirmed")
                raise OperationSettlementPending("settlement_permit_unconfirmed")
            with _CONDITION:
                item.released = True
                item.stage = "released"
                _EXPECTED.discard(_key(item.execution, item.ticket))
    except Exception as exc:
        with _CONDITION:
            if not item._blocked_error:
                _failure(item, exc)
    finally:
        with _CONDITION:
            item.inflight = False
            item._release_inflight = False
            _update_admission()
            _CONDITION.notify_all()


def active_counts():
    with _LOCK:
        valid = _check_integrity()
        carrier_valid = _check_carrier_health()
        owned = [item for item in _REGISTRY.values() if not item.released]
        terminal = [item for item in owned if item.intent is not None and not _has_authority(item)
                    and not _precleanup_pending(item)]
        resources = [item for item in owned if _precleanup_pending(item)
                     or (_has_authority(item) and _resources_pending(item))]
        permits = [item for item in owned if _has_authority(item) and not _resources_pending(item)
                   and item.callback_exited]
        return {"settlement_pending": len(terminal), "resource_pending": len(resources),
                "permit_pending": len(permits),
                "compensation_inflight": sum(int(item.inflight or item._release_inflight) for item in owned) + _SCAN_INFLIGHT,
                "unpersisted": sum(int(item.intent is not None and not _has_authority(item)) for item in owned),
                "callback_active": sum(int(item.callback_active) for item in owned),
                "unverified_scan_pending": _blocking_scans(),
                "registered": max(len(owned), len(_EXPECTED), int(not valid), int(not carrier_valid))}


def runtime_status():
    with _LOCK:
        counts = active_counts()
        alive = bool(_THREAD is not None and _THREAD.is_alive())
        errors = sorted({item.error_code for item in _REGISTRY.values()
                         if not item.released and item.error_code})
        if _CARRIER_ERROR:
            errors.insert(0, _CARRIER_ERROR)
        if _REGISTRY_ERROR:
            errors.insert(0, _REGISTRY_ERROR)
        if _SCAN_BLOCKED:
            errors.extend(sorted(set(_SCAN_BLOCKED.values())))
        elif _SCAN_ERROR:
            errors.append(_SCAN_ERROR)
        oldest = max((time.monotonic() - item.created_at for item in _REGISTRY.values()
                      if not item.released), default=0.0)
        for domain_id in _SCAN_BLOCKED:
            detail = _SCAN_DIAGNOSTICS.get(domain_id, {})
            oldest = max(oldest, float(detail.get("age_seconds", 0.0))
                         + max(0.0, time.monotonic() - float(detail.get("observed_at", time.monotonic()))))
        return {"started": _STARTED, "alive": alive, "thread_alive": alive,
                "healthy": bool(_STARTED and alive and not errors),
                "stopping": _STOP, "error_code": errors[0] if errors else "",
                "counts": counts, "oldest_age_seconds": oldest,
                "cleanup_scan_error_code": _SCAN_ERROR,
                "durable_cleanup_errors": len(_SCAN_BLOCKED),
                "cleanup_recovery_stage": "blocked" if any(
                    code in _PERMANENT_CODES for code in _SCAN_BLOCKED.values()) else
                    "waiting" if _SCAN_BLOCKED else "",
                "stages": {name: sum(int(item.stage == name and not item.released)
                                    for item in _REGISTRY.values())
                           for name in ("callback", "resources", "settlement", "permit")}}


def _blocking_scans():
    return sum(_SCAN_DIAGNOSTICS.get(key, {}).get("blocks_permit", True)
               for key in _SCAN_BLOCKED)


def _clear_scan_diagnostic(domain):
    global _SCAN_ERROR
    _SCAN_BLOCKED.pop(domain.domain_id, None)
    _SCAN_DIAGNOSTICS.pop(domain.domain_id, None)
    _SCAN_ERROR = sorted(set(_SCAN_BLOCKED.values()))[0] if _SCAN_BLOCKED else ""


def _cleanup_failure_result(result):
    if not isinstance(result, Mapping):
        return None
    candidates = [row for row in result.get("diagnostics", ()) if isinstance(row, Mapping)]
    if result.get("error_code") or result.get("state") == "claim_lost":
        candidates.insert(0, result)
    return max(candidates, key=lambda row: (
        bool(row.get("blocks_permit", True)), bool(row.get("blocked"))), default=None)


def _record_cleanup_result(domain, result, *, scoped=False):
    """Consume safe repository outcomes under the registry lock."""
    global _SCAN_ERROR
    result = _cleanup_failure_result(result)
    if result is None:
        return False
    code = result.get("error_code")
    if code not in _PERMANENT_CODES | {"settlement_storage_unavailable", "settlement_cleanup_waiting"}:
        code = "settlement_storage_unavailable"
    known = _SCAN_DIAGNOSTICS.get(domain.domain_id, {})
    prior_identity = known.get("identity") or {}
    identity = result.get("identity") or {}
    same_owner = (prior_identity.get("permit_id") == identity.get("permit_id")
                  and prior_identity.get("execution_id") == identity.get("execution_id"))
    if (scoped and known.get("durable") and known.get("blocks_permit", True)
            and (not same_owner or not prior_identity.get("permit_id"))):
        # An owned call sees only its original permit/execution. It cannot
        # replace a known foreign domain-wide blocking obligation, even after
        # its own nonblocking handoff safely leaves this process.
        _update_admission()
        return True
    _SCAN_BLOCKED[domain.domain_id] = code
    _SCAN_DIAGNOSTICS[domain.domain_id] = {
        "blocks_permit": bool(result.get("blocks_permit", True)),
        "age_seconds": max(0.0, float(result.get("age_seconds") or 0.0)),
        "observed_at": time.monotonic(),
        "durable": True,
        "identity": dict(result.get("identity") or {}),
    }
    _SCAN_ERROR = sorted(set(_SCAN_BLOCKED.values()))[0]
    _SCAN_FAILURES[domain.domain_id] = _SCAN_FAILURES.get(domain.domain_id, 0) + 1
    delay = min(5.0, max(.05, float(result.get("retry_after_seconds") or .2)))
    _SCAN_NEXT[domain.domain_id] = time.monotonic() + delay
    _update_admission()
    return True


def retry_cleanup(*, domain, identity):
    """Maintenance/same-intent entry: retry only one persisted original action."""
    global _SCAN_ERROR, _SCAN_INFLIGHT
    with _CONDITION:
        if (_STOP or _DEADLINE is not None or not _STARTED or _THREAD is None
                or not _THREAD.is_alive() or not _check_carrier_health()
                or (_ADMISSION is not None
                    and {"owner_lost", "draining"}.intersection(_ADMISSION.reasons()))):
            raise OperationSettlementFenced("cleanup_retry_runtime_unavailable")
        _remember_domain(domain)
        _SCAN_INFLIGHT += 1
    try:
        from core.storage.operations import settlements
        result = settlements.retry_cleanup(domain=domain, identity=identity, deadline=_attempt_deadline())
        diagnostics = settlements.cleanup_diagnostics(domain=domain, deadline=_attempt_deadline())
        with _CONDITION:
            remaining = _cleanup_failure_result({"diagnostics": diagnostics})
            _SCAN_BLOCKED.pop(domain.domain_id, None)
            _SCAN_DIAGNOSTICS.pop(domain.domain_id, None)
            if not _record_cleanup_result(domain, remaining):
                _SCAN_ERROR = sorted(set(_SCAN_BLOCKED.values()))[0] if _SCAN_BLOCKED else ""
                _SCAN_FAILURES[domain.domain_id] = 0
                _SCAN_NEXT[domain.domain_id] = 0.0
            _update_admission()
        return result
    finally:
        with _CONDITION:
            _SCAN_INFLIGHT -= 1
            _CONDITION.notify_all()


def _scan_domains():
    global _SCAN_INFLIGHT, _SCAN_ERROR
    with _CONDITION:
        if _STOP or (_ADMISSION is not None and "owner_lost" in _ADMISSION.reasons()):
            return
        domains = list(_DOMAINS.values())
    for domain in domains:
        with _CONDITION:
            if _STOP or (_ADMISSION is not None and "owner_lost" in _ADMISSION.reasons()):
                return
            if _SCAN_NEXT.get(domain.domain_id, 0.0) > time.monotonic():
                continue
            if (_SCAN_BLOCKED.get(domain.domain_id) in _PERMANENT_CODES
                    and (not _SCAN_DIAGNOSTICS.get(domain.domain_id, {}).get("durable")
                         or _SCAN_DIAGNOSTICS.get(domain.domain_id, {}).get("scan_failed_permanently"))):
                continue
            _SCAN_INFLIGHT += 1
        try:
            from core.storage.operations import settlements
            result = settlements.run_cleanup_once(domain=domain, deadline=_attempt_deadline())
            with _LOCK:
                if not _record_cleanup_result(domain, result):
                    _SCAN_BLOCKED.pop(domain.domain_id, None)
                    _SCAN_DIAGNOSTICS.pop(domain.domain_id, None)
                    _SCAN_ERROR = sorted(set(_SCAN_BLOCKED.values()))[0] if _SCAN_BLOCKED else ""
                    _SCAN_FAILURES[domain.domain_id] = 0
                    _SCAN_NEXT[domain.domain_id] = time.monotonic() + 0.2
                    _update_admission()
        except Exception as exc:
            with _LOCK:
                code, permanent = classify_failure(exc)
                known = _SCAN_DIAGNOSTICS.get(domain.domain_id, {})
                if not known.get("durable") or domain.domain_id not in _SCAN_BLOCKED:
                    _SCAN_BLOCKED[domain.domain_id] = code
                    _SCAN_DIAGNOSTICS.pop(domain.domain_id, None)
                elif permanent:
                    _SCAN_BLOCKED[domain.domain_id] = code
                    known["scan_failed_permanently"] = True
                # A transport failure cannot erase a known foreign durable
                # blocker. Owned scoped success proves only its own work.
                _SCAN_ERROR = sorted(set(_SCAN_BLOCKED.values()))[0]
                _update_admission()
                failures = _SCAN_FAILURES.get(domain.domain_id, 0) + 1
                _SCAN_FAILURES[domain.domain_id] = failures
                _SCAN_NEXT[domain.domain_id] = time.monotonic() + min(5.0, 0.1 * 2 ** min(failures, 6))
        finally:
            with _CONDITION:
                _SCAN_INFLIGHT -= 1
                _CONDITION.notify_all()


def _run():
    while True:
        with _CONDITION:
            if _STOP:
                return
            _check_integrity()
            items = list(_REGISTRY.values())
        for item in items:
            with _LOCK:
                if _STOP:
                    return
            _progress(item)
        _scan_domains()
        with _CONDITION:
            _CONDITION.wait(0.05)


def _domain_rearm_allowed(domain, admission):
    if domain is None or domain.domain_id not in _SCAN_BLOCKED:
        return True
    gates = [gate for gate in (_ADMISSION, admission) if gate is not None]
    lifecycle_blocked = any({"draining", "owner_lost"}.intersection(gate.reasons()) for gate in gates)
    return bool(not _STOP and _THREAD is not None and _THREAD.is_alive() and not lifecycle_blocked)


def start_runtime(*, domain=None, admission=None):
    global _THREAD, _STOP, _STARTED, _DEADLINE, _ADMISSION
    with _CONDITION:
        if not _check_carrier_health() or not _domain_rearm_allowed(domain, admission):
            return False
    if domain is not None:
        try:
            # Startup is the only capability probe. Status never opens a
            # database connection or treats absence as an upgrade invitation.
            from core.storage.operations import settlements
            settlements.verify_domain(domain, deadline=time.monotonic() + _ATTEMPT_SECONDS)
        except Exception:
            if admission is not None:
                admission.block("settlement_version")
            raise
    with _CONDITION:
        if not _check_carrier_health() or not _domain_rearm_allowed(domain, admission):
            return False
        if _STOP and _STOP_WITH_PENDING and (any(not item.released for item in _REGISTRY.values())
                                            or _SCAN_BLOCKED or _SCAN_INFLIGHT):
            return False
        if domain is not None:
            _remember_domain(domain)
            if not _SCAN_DIAGNOSTICS.get(domain.domain_id, {}).get("durable"):
                # A capability probe repairs scanner access, not an original
                # persisted action. Keep that action's error/count/due gate
                # until its exact retry or authoritative completion.
                _SCAN_BLOCKED.pop(domain.domain_id, None)
                _SCAN_DIAGNOSTICS.pop(domain.domain_id, None)
        if _THREAD is not None and _THREAD.is_alive():
            if _STOP:
                return False
            if admission is not None:
                _ADMISSION = admission
            _update_admission()
            return True
        if _STOP_WITH_PENDING and any(not item.released for item in _REGISTRY.values()):
            # Restarting an incomplete stop would silently grant a new budget
            # and revive a carrier whose lifecycle owner is shutting down.
            return False
        _STOP = False
        _STARTED = True
        _DEADLINE = None
        _ADMISSION = admission
        _THREAD = threading.Thread(target=_run, name="operation-settlement", daemon=True)
        _THREAD.start()
        _update_admission()
        return True


def _install_deadline(deadline):
    global _DEADLINE
    _DEADLINE = float(deadline) if _DEADLINE is None else min(_DEADLINE, float(deadline))
    return _DEADLINE


def begin_shutdown(deadline):
    """Publish the original shared budget without waiting for ongoing I/O."""
    with _CONDITION:
        effective = _install_deadline(deadline)
        _CONDITION.notify_all()
        return effective


def end_shutdown(deadline):
    """Lift only a completed drain's background-attempt restriction.

    The lifecycle manager retains its original stop deadline. This does not
    start a carrier, reopen admission, clear fenced evidence or grant another
    stop call a fresh budget; it lets still-owned exact compensation continue
    after the caller truthfully returned stop_incomplete.
    """
    global _DEADLINE
    with _CONDITION:
        if (_DEADLINE != float(deadline) or _STOP
                or _THREAD is None or not _THREAD.is_alive()):
            return False
        _DEADLINE = None
        _CONDITION.notify_all()
        return True


def begin_finalization(deadline):
    """Enter only an explicit retained-resource finalization phase.

    ManagedRuntime validates stop_incomplete before invoking this separate
    operation. A stopped carrier remains stopped: a fresh budget can join its
    actual thread, but cannot revive it or admit business.
    """
    global _DEADLINE
    with _CONDITION:
        _DEADLINE = float(deadline)
        _CONDITION.notify_all()
        return _DEADLINE


def drain_runtime(deadline):
    with _CONDITION:
        effective = _install_deadline(deadline)
        _CONDITION.notify_all()
        while (_SCAN_INFLIGHT or _blocking_scans() or not _check_integrity()
               or not _check_carrier_health() or any(not item.released for item in _REGISTRY.values())):
            remaining = effective - time.monotonic()
            if remaining <= 0:
                return False
            _CONDITION.wait(min(remaining, 0.05))
        return True


def stop_runtime(deadline):
    global _STOP, _STARTED, _STOP_WITH_PENDING
    with _CONDITION:
        _check_carrier_health()
        effective = _install_deadline(deadline)
        _STOP = True
        _STOP_WITH_PENDING = bool(_blocking_scans() or _SCAN_INFLIGHT
                                  or any(not item.released for item in _REGISTRY.values()))
        _CONDITION.notify_all()
        thread = _THREAD
    if thread is not None and thread is not threading.current_thread():
        thread.join(max(0.0, effective - time.monotonic()))
    with _LOCK:
        joined = thread is None or not thread.is_alive()
        if joined:
            _STARTED = False
        return (joined and not _blocking_scans() and _check_integrity() and _check_carrier_health()
                and not any(not item.released for item in _REGISTRY.values()))
