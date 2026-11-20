"""账号任务统一提交、事件和持久调度边界。

兼容期仍由 ``legacy_task_store`` 写入旧账号任务；本模块负责把任务和
依赖交给 PostgreSQL 的统一运行时。进程内线程只负责轮询和提交，真正的
claim 以及父子推进都由存储层的原子状态转换决定。
"""
from __future__ import annotations

import logging
import hashlib
import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from core.operations.runtime import CancellationToken, OperationAccountDeactivated, OperationCancelled, operation_context
from core.operations import account_receipts
from core.operations.settlement_contracts import (
    OperationSettlementPending, OperationSettlementConflict, OperationSettlementFenced,
    seal_intent, same_intent, thaw as settlement_thaw,
)

SETTLEMENT_CONTROL_ERRORS = (OperationSettlementPending, OperationSettlementConflict, OperationSettlementFenced)


logger = logging.getLogger(__name__)

# A dependency has exactly one claim owner: the persistent scanner below. The
# installed callback only submits the already-claimed row to the shared
# account-operation budget; it must not claim the row again.
_DEPENDENCY_HANDLER: Callable[[dict], Any] | None = None
_DEPENDENCY_HANDLER_LOCK = threading.RLock()
_DEPENDENCY_WAKE = threading.Event()
_DEPENDENCY_STOP = threading.Event()
_DEPENDENCY_THREAD: threading.Thread | None = None
_DEPENDENCY_LOCK = threading.RLock()
_DEPENDENCY_INTERVAL_SECONDS = 0.5
_DEPENDENCY_BATCH_SIZE = 32

# Native operation dispatch is task-type based rather than Codex-specific.
# A handler is registered at the gateway boundary and receives a run id. The
# gateway scans every native/compatibility operation row that has a registered
# task type, so adding a maintenance handler does not require another raw
# scheduler thread.
_DISPATCH_HANDLERS: dict[str, tuple[Callable[[int], Any], tuple[str, ...] | None]] = {}
_DISPATCH_CAPACITY_HANDLERS: dict[
    str,
    tuple[Callable[[Mapping[str, Any]], Any], Callable[[Any], Any]],
] = {}
_OPERATION_HANDLERS: dict[str, Callable[[OperationHandlerContext], Any]] = {}
_OPERATION_ACTIONS: dict[str, dict[str, Callable[[Mapping[str, Any]], Any]]] = {}
_OPERATION_ACTION_SOURCES: dict[str, tuple[str, ...] | None] = {}
_DISPATCH_HANDLER_LOCK = threading.RLock()
_RUN_DISPATCHED: set[int] = set()
_RUN_DISPATCH_LOCK = threading.RLock()
_RUN_DISPATCH_WAKE = threading.Event()
_RUN_DISPATCH_STOP = threading.Event()
_RUN_DISPATCH_THREAD: threading.Thread | None = None
_RUN_DISPATCH_INTERVAL_SECONDS = 0.5
_RUN_DISPATCH_BATCH_SIZE = 32
_RUNTIME_RECOVERY_INTERVAL_SECONDS = 60.0
_LAST_RUNTIME_RECOVERY_AT = 0.0
_PREFER_EXTRACT_CONTINUATIONS = False


_MISSING = object()
_CONFIG_SECRET_PARTS = frozenset({"password", "secret", "token", "cookie", "otp", "authorization"})
_SAFE_PASSWORD_POLICY_KEYS = frozenset({
    # C-owned schema names.
    "ACCOUNT_COMPLETION_PASSWORD_ENABLED",
    "ACCOUNT_PASSWORD_RESET_ENABLED",
    "ACCOUNT_PASSWORD_DRIVER",
    "ACCOUNT_PASSWORD_PROXY_MODE",
    "ACCOUNT_AUTH_PASSWORD_EMAIL_FALLBACK",
    # Stable execution projections used inside durable task data.
    "password_enabled",
    "password_reset_enabled",
    "password_driver",
    "password_proxy_mode",
    "auth_password_email_fallback",
})


def _config_key_is_sensitive(*names: str) -> bool:
    """Reject credential values while allowing exact policy/config names."""
    for name in names:
        text = str(name).strip()
        parts = {part for part in text.lower().split("_") if part}
        if parts & {"secret", "token", "cookie", "otp", "authorization"}:
            return True
        # Only the schema/policy names above are safe. Checking for a generic
        # ``proxy``/``enabled``/``driver`` suffix would allow names such as
        # PASSWORD_PROXY_PASSWORD, which are credential material.
        if "password" in parts and text not in _SAFE_PASSWORD_POLICY_KEYS:
            return True
    return False


def _thaw(value: Any) -> Any:
    """Copy immutable config containers without deepcopying mapping proxies."""
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return {_thaw(item) for item in value}
    return value


def normalize_config_snapshot(
    snapshot: Any,
    *,
    allowlist: Iterable[str] | Mapping[str, str],
) -> dict[str, Any]:
    """Project one immutable non-sensitive config snapshot for a task.

    The configuration owner remains outside the gateway.  This boundary only
    understands the stable C object shape (``revision`` plus ``values``),
    recursively thaws immutable mappings, and copies explicitly allowlisted
    keys.  A mapping allowlist can rename a schema key to the execution key,
    for example ``{"oauth_driver": "CODEX_OAUTH_DRIVER"}``.
    """
    revision = getattr(snapshot, "revision", _MISSING)
    if isinstance(snapshot, Mapping):
        payload = _thaw(snapshot)
        if revision is _MISSING:
            revision = payload.get("revision", payload.get("version", payload.get("config_snapshot_revision", _MISSING)))
        values = payload.get("values")
        if values is None:
            values = payload.get("snapshot")
        if values is None:
            values = payload
    else:
        values = getattr(snapshot, "values", None)
        if not isinstance(values, Mapping):
            as_dict = getattr(snapshot, "as_dict", None)
            values = as_dict() if callable(as_dict) else None
    values = _thaw(values)
    if not isinstance(values, Mapping):
        raise TypeError("配置 snapshot 必须提供 Mapping values")

    if isinstance(allowlist, Mapping):
        pairs = [(str(target), str(source)) for target, source in allowlist.items()]
    else:
        pairs = [(str(key), str(key)) for key in allowlist]
    projected: dict[str, Any] = {}
    for target, source in pairs:
        target = target.strip()
        source = source.strip()
        if not target or not source:
            continue
        if _config_key_is_sensitive(target, source):
            raise ValueError(f"配置 snapshot allowlist 包含敏感字段: {target}")
        if source in values:
            projected[target] = _thaw(values[source])
    if revision is _MISSING:
        revision = values.get("revision", values.get("config_snapshot_revision"))
    if revision is not _MISSING and revision is not None:
        projected["config_snapshot_revision"] = _thaw(revision)
    return projected


def _stored_config_snapshot(run: Mapping[str, Any]) -> dict[str, Any]:
    data = run.get("data")
    if not isinstance(data, Mapping):
        return {}
    value = data.get("config_snapshot")
    return _thaw(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class OperationResult:
    """显式 handler 结果；旧回执标记保留原 Run 供后续核验。"""

    status: str
    summary: Mapping[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str | None = None

    @classmethod
    def success(cls, summary: Mapping[str, Any] | None = None, *, message: str = "") -> "OperationResult":
        return cls("success", dict(summary or {}), message)

    @classmethod
    def failed(cls, message: str, summary: Mapping[str, Any] | None = None) -> "OperationResult":
        return cls("failed", dict(summary or {}), message, message)

    @classmethod
    def cancelled(cls, message: str = "任务已在安全检查点取消") -> "OperationResult":
        return cls("cancelled", {"cancelled": True}, message, message)

    @classmethod
    def request_unknown(
        cls,
        message: str = "当前步骤未保存完整回执",
        summary: Mapping[str, Any] | None = None,
        *,
        error: str | None = None,
    ) -> "OperationResult":
        values = dict(summary or {})
        values.update({"outcome": "request_unknown", "reconcile_required": True})
        return cls("request_unknown", values, message, error or message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ok": self.status == "success",
            "message": self.message,
            "error": self.error,
            "result_summary": _thaw(dict(self.summary)),
        }


class OperationLeaseUnavailable(RuntimeError):
    """The run was claimed but its account/resource lease is temporarily busy."""


class OperationResourceCleanupPending(OperationSettlementPending):
    """Exact registered local cleanup stopped business before a result existed."""

    def __init__(self, *, cleanup, resource_identity: str, facts: Mapping[str, Any] | None = None):
        if not resource_identity or not isinstance(resource_identity, str):
            raise ValueError("cleanup resource identity is required")
        if facts is not None and not isinstance(facts, Mapping):
            raise TypeError("cleanup facts must be a mapping")
        from core.storage.operations.common import _scrub
        self.cleanup = cleanup
        self.resource_identity = resource_identity
        self.facts = seal_intent(kind="terminal", origin={}, payload=_scrub(_thaw(facts or {}))).payload
        super().__init__("registered_resource_cleanup_pending")


class OperationLeaseLost(RuntimeError):
    """The current worker lost its lease fence while remote work was possible."""


def _domain_scope(domain, *, deadline=None):
    if domain is None:
        return nullcontext()
    from core.storage.operations.common import settlement_scope
    return settlement_scope(domain, deadline=deadline)


def _current_settlement_execution(run_id, execution_id):
    from core.operations import concurrency
    execution = concurrency.current_execution()
    if (execution is not None and str(execution.execution_id) == str(execution_id)
            and int(execution.claimed_run.get("id") or 0) == int(run_id)):
        return execution
    return None


class OperationLease:
    """Exact original lease handle; failed DELETE never gives up ownership."""

    def __init__(self, *, run_id: int, account_id: int, resource_family: str,
                 token: str, ttl_seconds: int = 600, domain=None,
                 scope_kind: str = "step", scope_id: str | None = None,
                 generation: int = 1, execution_id: str | None = None) -> None:
        if scope_kind not in {"step", "final"}:
            raise ValueError("lease scope_kind must be step or final")
        if not token:
            raise ValueError("an exact lease token is required")
        self.run_id = int(run_id)
        self.account_id = int(account_id)
        self.resource_family = str(resource_family)
        self.token = str(token)
        self.domain = domain
        self.scope_kind = scope_kind
        self.scope_id = scope_id or str(uuid.uuid4())
        self.generation = int(generation)
        self.execution_id = str(execution_id) if execution_id is not None else None
        self.ttl_seconds = max(60, min(24 * 60 * 60, int(ttl_seconds or 600)))
        self._state = "held"
        self._released = False
        self._state_lock = threading.RLock()
        self._heartbeat_lost = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_interval = max(0.5, min(30.0, self.ttl_seconds / 3.0))
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop,
            name=f"operation-lease-{self.run_id}", daemon=True)
        self._heartbeat_thread.start()

    @property
    def state(self) -> str:
        with self._state_lock:
            return self._state

    @property
    def released(self) -> bool:
        with self._state_lock:
            return self._state == "release_confirmed"

    @property
    def lost(self) -> bool:
        return self._heartbeat_lost

    def heartbeat(self, *, ttl_seconds: int | None = None) -> bool:
        # Same lock spans the I/O: renewal cannot race after an exact DELETE.
        with self._state_lock:
            if self._state != "held" or self._heartbeat_lost:
                return False
            ttl = max(60, min(24 * 60 * 60, int(ttl_seconds or self.ttl_seconds)))
            try:
                with _domain_scope(self.domain):
                    alive = bool(_operation().heartbeat_run(self.run_id, self.token, ttl_seconds=ttl))
            except Exception:
                logger.error("operation lease heartbeat unavailable: run_id=%s", self.run_id)
                alive = False
            if not alive:
                self._heartbeat_lost = True
            return alive

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            if not self.heartbeat(ttl_seconds=self.ttl_seconds):
                return

    def mark_release_confirmed(self, receipt=None) -> bool:
        """Called only after exact DELETE commit or authoritative settlement receipt."""
        with self._state_lock:
            changed = self._state != "release_confirmed"
            self._state = "release_confirmed"
            self._released = True
            self._heartbeat_stop.set()
            return changed

    def mark_disposition_confirmed(self, disposition) -> bool:
        """Accept proved old-token absence, never original terminal success.

        The coordinator first checks the full original intent against this
        separate administrative disposition. This handle independently checks
        its exact captured domain, Run, execution and token fingerprint.
        """
        if (not isinstance(disposition, Mapping)
                or disposition.get("disposition_kind") != "live_superseded"
                or disposition.get("original_intent_committed") is not False
                or disposition.get("lease_disposition") != "exact_original_token_absent"
                or int(disposition.get("run_id") or 0) != self.run_id
                or disposition.get("lease_fingerprint") != hashlib.sha256(self.token.encode()).hexdigest()
                or (self.domain is not None and disposition.get("domain_id") != self.domain.domain_id)
                or (self.execution_id is not None and disposition.get("execution_id") != self.execution_id)):
            raise ValueError("unproved original lease disposition")
        # This changes only the exact resource fact; no context result/receipt.
        return self.mark_release_confirmed()

    def join(self, *, deadline=None) -> bool:
        thread = self._heartbeat_thread
        if thread is threading.current_thread():
            return False
        timeout = max(0.0, deadline - time.monotonic()) if deadline is not None else min(1.0, self._heartbeat_interval)
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def release(self, *, deadline=None) -> bool:
        with self._state_lock:
            changed = self._state != "release_confirmed"
            if changed:
                self._state = "release_pending"
                self._heartbeat_stop.set()
                with _domain_scope(self.domain, deadline=deadline):
                    _operation().release_account_lease(self.run_id, self.token)
                # Zero rows proves the exact old token absent after confirmed
                # commit. Unknown ACK keeps pending and retains this handle.
                self.mark_release_confirmed()
        # A heartbeat already waiting for the state lock must physically exit;
        # joining under that lock would deadlock its final state check.
        joined = self.join(deadline=deadline)
        return changed and joined

    def __enter__(self) -> "OperationLease":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


class OperationTaskReporter:
    """Structured progress reporter bound to one claimed Run."""

    def __init__(self, run_id: int) -> None:
        self.run_id = int(run_id)

    def report(self, **event: Any) -> dict:
        from core.operations import run_log as task_run_log

        task_run_log.set_current_stage(str(event.get("stage") or "event"), run_id=self.run_id, identifier_namespace="operation")
        persisted = _operation().append_runtime_event(self.run_id, **event)
        if isinstance(persisted, dict):
            task_run_log.set_current_stage(
                str(event.get("stage") or "event"),
                task_id=persisted.get("task_id"), run_id=self.run_id,
                event_id=persisted.get("id"), event_uuid=persisted.get("event_uuid"),
                source_system=persisted.get("source_system"),
            )
        return persisted

    def stage(self, stage: str, state: str, message: str, **kwargs: Any) -> dict:
        return self.report(stage=stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs: Any) -> dict:
        return self.report(stage=stage, message=message, **kwargs)


class OperationHandlerContext:
    """Stable execution contract passed to a durable operation handler.

    The handler owns business writeback and calls :meth:`finish` only after
    that writeback is confirmed.  The gateway owns claim, cancellation,
    event reporting, lease cleanup and terminal result persistence.
    """

    def __init__(self, run: Mapping[str, Any], *, execution_id: str) -> None:
        self.run = _thaw(dict(run))
        self.run_id = int(self.run["id"])
        self.task_id = int(self.run["task_id"])
        self.account_id = int(self.run["account_id"]) if self.run.get("account_id") else None
        self.email = str(self.run.get("email_snapshot") or "")
        self.task_type = str(self.run.get("task_type") or "")
        self.source_system = str(self.run.get("source_system") or "native_operations")
        self.resource_family = str(self.run.get("resource_family") or "openai_interactive")
        self.execution_id = str(execution_id)
        self.cancellation_token = str(self.run.get("cancellation_token") or "")
        self.config_snapshot = _stored_config_snapshot(self.run)
        self.config_revision = self.config_snapshot.get("config_snapshot_revision")
        self.task_reporter = OperationTaskReporter(self.run_id)
        self._token = CancellationToken(
            run_id=self.run_id,
            token=self.cancellation_token,
            checker=lambda run_id, token: self._call_storage("is_run_cancel_requested", run_id, token),
        )
        self._execution = _current_settlement_execution(self.run_id, self.execution_id)
        self._domain = getattr(self._execution, "settlement_domain", None)
        self._lease: OperationLease | None = None
        self._leases: list[OperationLease] = []
        self._transition_lock = threading.RLock()
        self._settlement_intent = None
        self._settlement_receipt = None
        self._settlement_control = None
        self._settlement_origin = None
        self._step_release_failed: OperationLease | None = None
        self._settlement_obligations: dict[tuple[str, str], Mapping] = {}
        self._registered_cleanups: dict[str, Any] = {}
        self._finished = False
        self._deferred_result: dict[str, Any] | None = None
        self._last_result: OperationResult | None = None

    def _call_storage(self, name: str, *args, **kwargs):
        with _domain_scope(self._domain):
            return getattr(_operation(), name)(*args, **kwargs)

    @property
    def settlement_domain(self):
        """Captured in-memory origin; connection material must never be serialized."""
        return self._domain

    def storage_scope(self, *, deadline=None):
        return _domain_scope(self._domain, deadline=deadline)

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def deferred(self) -> bool:
        return self._deferred_result is not None

    def _origin(self) -> dict:
        if self._settlement_origin is not None:
            return settlement_thaw(self._settlement_origin)
        ticket = getattr(self._execution, "settlement_ticket", None)
        origin = _thaw(ticket or {})
        origin.update(run_id=self.run_id, task_id=self.task_id, execution_id=self.execution_id)
        active = self._lease if self._lease is not None and not self._lease.released else None
        # A final scope remains a required original fence even after a caller
        # physically released its handle. Never downgrade it to no-lease authority.
        if active is None:
            active = next((item for item in reversed(self._leases) if item.scope_kind == "final"), None)
        origin["lease_token"] = active.token if active else None
        origin["lease_requirement"] = ("final" if active else "steps_confirmed" if self._leases
                                       else "accountless" if self.account_id is None else "not_acquired")
        if self._step_release_failed is not None:
            failed = self._step_release_failed
            origin.update(lease_requirement="step_release_unconfirmed", lease_token=failed.token,
                          scope_id=failed.scope_id, scope_kind="step", generation=failed.generation)
        origin["leases"] = [{"scope_id": lease.scope_id, "scope_kind": lease.scope_kind,
            "generation": lease.generation, "run_id": lease.run_id, "account_id": lease.account_id,
            "resource_family": lease.resource_family, "lease_token": lease.token,
            "state": lease.state} for lease in self._leases]
        return origin

    def add_settlement_obligation(self, action_kind: str, *, resource_identity: str,
                                  payload: Mapping[str, Any], blocks_permit: bool = True) -> Mapping:
        """Declare an audited typed local tail before freezing terminal/defer."""
        allowed = {"run_log", "dependency_ready", "completion_dependency", "codex_refresh_marker",
                   "extract_plan_verify", "extract_provider_writeback", "resource_release"}
        if action_kind not in allowed or not resource_identity or len(str(resource_identity)) > 1000:
            raise ValueError("unsupported settlement obligation")
        if not isinstance(payload, Mapping):
            raise TypeError("settlement obligation payload must be a mapping")
        with self._transition_lock:
            if self._settlement_intent is not None:
                raise OperationSettlementConflict("settlement intent already frozen")
            from core.storage.operations.common import _scrub
            safe_payload = _scrub(_thaw(payload))
            item = settlement_thaw(seal_intent(kind="terminal", origin={}, payload={
                "action_kind": action_kind, "resource_identity": str(resource_identity),
                "payload": safe_payload, "blocks_permit": bool(blocks_permit),
            }).payload)
            key = (action_kind, str(resource_identity))
            old = self._settlement_obligations.get(key)
            if old is not None and old != item:
                raise OperationSettlementConflict("conflicting settlement obligation")
            self._settlement_obligations[key] = item
            return _thaw(item)

    def register_cleanup(self, cleanup, *, key: str, blocking: bool = True,
                         before_transition: bool = False):
        """Transfer one exact live local handle, never an arbitrary callback."""
        if self._execution is None or not getattr(self._execution, "settlement_ticket", None):
            raise OperationSettlementFenced("local cleanup requires an admission responsibility")
        from core.operations import settlement
        registered = settlement.register_cleanup(self._execution, cleanup, key=key, blocking=blocking,
                                                 before_transition=before_transition)
        self._registered_cleanups[key] = cleanup
        return registered

    def finish_cleanup_failure(self, error: OperationResourceCleanupPending) -> dict:
        """Seal a technical exit only for a precise already-owned local handle."""
        with self._transition_lock:
            # A later resource failure cannot replace an original terminal or
            # deferral, including a confirmed result returned by the database.
            self.raise_if_settlement_pending()
            if self.deferred:
                return _thaw(self._deferred_result)
            if self.finished and self.last_result is not None:
                return _operation_handler_result_payload(self, self.last_result)
            if (not isinstance(error, OperationResourceCleanupPending)
                    or self._registered_cleanups.get(error.resource_identity) is not error.cleanup):
                raise OperationSettlementFenced("cleanup signal does not belong to this execution")
            from core.operations import settlement
            owner = settlement.responsibility(self._execution)
            if (owner is None or not any(item.key == error.resource_identity and item.handle is error.cleanup
                                         for item in owner._cleanups)):
                raise OperationSettlementFenced("cleanup responsibility is unproved")
            stored = self.run.get("result_summary")
            summary = _thaw(stored) if isinstance(stored, Mapping) else {}
            summary.update(settlement_thaw(error.facts))
            summary.setdefault("cause_code", "resource_release_unconfirmed")
            if str(summary.get("outcome") or "").lower() not in {"request_unknown", "attention_required"}:
                summary["outcome"] = "resource_cleanup_pending"
            summary["automatic_business_retry"] = False
            summary["cleanup_resource_identity"] = error.resource_identity
            self.finish(OperationResult("attention_required", summary,
                "原资源释放尚未确认，后续业务步骤未执行"))
            return _operation_handler_result_payload(self, self.last_result)

    register_settlement_obligation = add_settlement_obligation

    def _submit_transition(self, *, kind: str, payload: Mapping[str, Any]) -> dict:
        with self._transition_lock:
            origin = self._origin()
            candidate = seal_intent(kind=kind, origin=origin, payload=_thaw(payload),
                obligations=tuple(self._settlement_obligations.values()),
                transition_id=self._settlement_intent.transition_id if self._settlement_intent else None)
            if self._settlement_intent is not None:
                if not same_intent(self._settlement_intent, candidate):
                    raise OperationSettlementConflict("execution already owns a different settlement intent")
                if self._settlement_receipt is not None:
                    from core.operations import settlement
                    responsibility = (settlement.responsibility(self._execution)
                        if self._execution is not None and getattr(self._execution, "settlement_ticket", None) else None)
                    if responsibility is None or responsibility._blocked_cleanup is None:
                        return _thaw(self._settlement_receipt)
                    # Only explicit confirmation of this exact cached intent
                    # may rearm its recorded original cleanup. It never
                    # resubmits the transition or reenters a business callback.
                    cached = self._settlement_receipt
                    authoritative = responsibility.receipt or {}
                    if (not same_intent(responsibility.intent, candidate)
                            or cached.get("transition_id") != candidate.transition_id
                            or cached.get("request_digest") != candidate.request_digest
                            or authoritative != cached
                            or responsibility._blocked_cleanup.get("receipt_id") != cached.get("receipt_id")):
                        raise OperationSettlementConflict("cleanup retry cached receipt identity mismatch")
            else:
                self._settlement_intent = candidate
                self._settlement_origin = candidate.origin
            intent = self._settlement_intent

            def submit(frozen, deadline):
                if self._execution is not None and getattr(self._execution, "settlement_ticket", None):
                    from core.storage.operations.settlements import submit_intent
                    return submit_intent(frozen, domain=self._domain, deadline=deadline)
                # Nonparticipants keep the native repository contract. Only
                # these local storage operations can run again on confirmation.
                values = settlement_thaw(frozen.payload)
                values.pop("subtype", None)
                run_id = values.pop("run_id")
                with _domain_scope(self._domain, deadline=deadline):
                    row = (_operation().finish_run(run_id, **values) if frozen.kind == "terminal"
                           else _operation().requeue_claimed_run(run_id, **values))
                if row is None:
                    raise OperationSettlementFenced("original execution no longer owns transition")
                return row

            try:
                if self._execution is not None and getattr(self._execution, "settlement_ticket", None):
                    from core.operations import settlement
                    receipt = settlement.settle(self._execution, intent, submit)
                else:
                    receipt = submit(intent, None)
            except SETTLEMENT_CONTROL_ERRORS as exc:
                self._settlement_control = exc
                raise
            except PermissionError as exc:
                self._settlement_control = OperationSettlementFenced("original execution transition rejected")
                raise OperationSettlementFenced("original execution transition rejected") from None
            except Exception as exc:
                raise OperationSettlementPending("original settlement awaits local persistence") from None
            self._settlement_receipt = _thaw(receipt)
            # Atomic terminal/defer removes only the captured final token. Step
            # release remains its own confirmed transaction before next action.
            if self._lease is not None and self._lease.scope_kind == "final":
                self._lease.mark_release_confirmed(receipt)
            return _thaw(receipt)

    def raise_if_settlement_pending(self) -> None:
        if self._settlement_intent is not None and self._settlement_receipt is None:
            if self._settlement_control is not None:
                raise self._settlement_control
            raise OperationSettlementPending("original settlement remains pending")

    def defer(self, *, delay_seconds: float, reason: str,
              data: Mapping[str, Any] | None = None, stage: str = "remote_sync") -> dict[str, Any]:
        """Freeze one same-Run deferral; retries only confirm this exact intent."""
        with self._transition_lock:
            if self._settlement_intent is None:
                self.checkpoint()
            token = self._origin().get("lease_token")
            receipt = self._submit_transition(kind="defer", payload={
                "run_id": self.run_id, "execution_id": self.execution_id, "lease_token": token,
                "reason": str(reason), "delay_seconds": delay_seconds,
                "data": _thaw(data) if data is not None else None, "stage": stage,
            })
            actual = receipt.get("actual_result") or receipt
            actual_status = str(actual.get("status") or "queued")
            if actual_status != "queued":
                summary = actual.get("result_summary") if isinstance(actual.get("result_summary"), Mapping) else {}
                message = str(actual.get("message") or actual.get("error_message") or "")
                self._last_result = (OperationResult.request_unknown(message, summary)
                    if summary.get("outcome") == "request_unknown" else OperationResult(
                        actual_status, _thaw(summary), message, actual.get("error_message")))
                self._finished = True
                return _operation_handler_result_payload(self, self._last_result)
            self._deferred_result = {"status": "deferred", "ok": False,
                "database_status": actual.get("status") or "queued", "task_id": self.task_id,
                "run_id": self.run_id, "source_system": self.source_system, "reason": str(reason)}
            notify_dispatch()
            return _thaw(self._deferred_result)

    @property
    def cancellation(self) -> CancellationToken:
        return self._token

    def report(self, **event: Any) -> dict:
        return self.task_reporter.report(**event)

    def checkpoint(self, message: str = "任务收到取消请求") -> None:
        self.raise_if_settlement_pending()
        if self._lease is not None and not self._lease.released:
            if not self._lease.heartbeat():
                raise OperationLeaseLost("账号 lease 心跳失败，远端结果必须重新核验")
        self._token.checkpoint(message)

    @property
    def execution_fence(self) -> dict[str, Any]:
        """内部仓储在同事务写入前校验当前执行与账号租约。"""
        if self._lease is None or self._lease.released:
            raise OperationLeaseLost("当前执行已没有账号租约，禁止写入任务结果")
        return {"run_id": self.run_id, "execution_id": self.execution_id, "lease_token": self._lease.token}

    def is_cancel_requested(self, *, force: bool = False) -> bool:
        return self._token.requested(force=force)

    def adopt_lease(self, lease: OperationLease, *, scope_kind: str = "final") -> OperationLease:
        with self._transition_lock:
            if scope_kind not in {"step", "final"}:
                raise ValueError("lease scope_kind must be step or final")
            if (lease.run_id != self.run_id or lease.account_id != self.account_id
                    or (lease.domain is not None and self._domain is not None and lease.domain != self._domain)):
                raise OperationSettlementFenced("lease belongs to a different original execution domain")
            if self._settlement_intent is not None:
                raise OperationSettlementConflict("cannot acquire after settlement freeze")
            if any(not item.released or item._heartbeat_thread.is_alive() for item in self._leases):
                raise OperationSettlementPending("previous lease release is unconfirmed")
            lease.scope_kind = scope_kind
            if lease.execution_id is not None and lease.execution_id != self.execution_id:
                raise OperationSettlementFenced("lease belongs to a different original execution")
            if lease.domain is None:
                lease.domain = self._domain
            lease.execution_id = self.execution_id
            self._leases.append(lease)
            self._lease = lease
            if self._execution is not None and getattr(self._execution, "settlement_ticket", None):
                from core.operations import settlement
                settlement.register_lease(self._execution, lease, scope_kind=scope_kind)
            return lease

    def acquire_lease(self, *, resource_family: str | None = None, ttl_seconds: int = 600,
                      scope_kind: str = "step") -> OperationLease:
        with self._transition_lock:
            if scope_kind not in {"step", "final"}:
                raise ValueError("lease scope_kind must be step or final")
            if self.account_id is None:
                raise ValueError("无 account_id 的操作不能申请账号 lease")
            if self._settlement_intent is not None:
                raise OperationSettlementConflict("cannot acquire after settlement freeze")
            if any(not item.released or item._heartbeat_thread.is_alive() for item in self._leases):
                raise OperationSettlementPending("previous lease release is unconfirmed")
            family = str(resource_family or self.resource_family)
            with _domain_scope(self._domain):
                token = _operation().acquire_account_lease(account_id=self.account_id,
                    run_id=self.run_id, resource_family=family, ttl_seconds=ttl_seconds)
            if not token:
                raise OperationLeaseUnavailable(
                    f"账号 lease 不可用：account_id={self.account_id} resource_family={family}")
            lease = OperationLease(run_id=self.run_id, account_id=self.account_id,
                resource_family=family, token=token, ttl_seconds=ttl_seconds,
                domain=self._domain, scope_kind=scope_kind, generation=len(self._leases) + 1,
                execution_id=self.execution_id)
            return self.adopt_lease(lease, scope_kind=scope_kind)

    @contextmanager
    def lease(self, *, resource_family: str | None = None, ttl_seconds: int = 600,
              scope_kind: str = "step") -> Iterator[OperationLease]:
        lease = self.acquire_lease(resource_family=resource_family,
                                   ttl_seconds=ttl_seconds, scope_kind=scope_kind)
        try:
            yield lease
        finally:
            if scope_kind == "step":
                self.release_lease()

    def release_lease(self) -> bool:
        with self._transition_lock:
            if self._lease is None:
                return False
            lease = self._lease
            # Once sealed, the original final token belongs to the transition.
            # A finally block must never delete it before receipt confirmation.
            if lease.scope_kind == "final" and self._settlement_intent is not None:
                return False
            try:
                result = lease.release()
            except SETTLEMENT_CONTROL_ERRORS:
                raise
            except Exception as exc:
                if lease.scope_kind == "step" and self._settlement_intent is None:
                    self._step_release_failed = lease
                    # Never resume the next business step after unknown DELETE.
                    # Preserve completed-step facts separately from remote-result
                    # uncertainty; this conservative result is storage-fenced.
                    self.finish(OperationResult("attention_required", {
                        "reason": "step_lease_release_unconfirmed",
                        "scope_id": lease.scope_id, "scope_kind": "step",
                        "completed_steps_preserved": True,
                    }, "步骤租约释放尚未确认，后续步骤未执行"))
                raise OperationSettlementPending("original lease release remains unconfirmed") from None
            if lease.released and not lease._heartbeat_thread.is_alive():
                self._lease = None
            return result

    def register_resource(self, **kwargs: Any) -> dict:
        return self._call_storage("register_resource", self.run_id, **kwargs)

    def release_resource(self, resource_id: int, **kwargs: Any) -> bool:
        return bool(self._call_storage("release_resource", int(resource_id), **kwargs))

    def remote_request_started(
        self,
        action: str,
        *,
        intent_kind: str = "remote_write",
        request_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> dict:
        """Persist a remote request boundary before invoking the remote API.

        ``detail`` is for non-sensitive routing/request metadata only.  The
        storage boundary scrubs it and fences the update by this execution and
        its current account lease.
        """
        return self._call_storage("record_remote_intent",
            self.run_id,
            execution_id=self.execution_id,
            lease_token=self._lease.token if self._lease and not self._lease.released else None,
            action=str(action or "remote_operation"),
            intent_kind=str(intent_kind or "remote_write"),
            request_id=request_id,
            detail=dict(detail or {}),
        )

    def remote_request_receipt(
        self,
        *,
        outcome: str | None = None,
        receipt_state: str | None = None,
        action: str | None = None,
        request_id: str | None = None,
        detail: Mapping[str, Any] | None = None,
    ) -> dict:
        """Persist a remote response without treating it as task success.

        ``received``/``response_received``/``response_observed`` (and the
        compatibility alias ``accepted``) only mean that an HTTP/remote
        response was observed. ``local_commit_required`` means the remote
        side may have accepted the write but local persistence is incomplete.
        ``confirmed`` is reserved for a receipt whose detail explicitly marks
        ``remote_result_confirmed``, ``local_business_writeback_confirmed``
        and ``local_readback_confirmed``. A receipt on a crashed non-terminal
        run still remains reconciliation-required rather than being replayed
        blindly.
        """
        return self._call_storage("record_remote_receipt",
            self.run_id,
            execution_id=self.execution_id,
            lease_token=self._lease.token if self._lease and not self._lease.released else None,
            outcome=str(outcome or "unknown"),
            receipt_state=receipt_state,
            action=action,
            request_id=request_id,
            detail=dict(detail or {}),
        )

    def finish(self, result: OperationResult | Mapping[str, Any] | None = None, *,
               status: str | None = None, message: str = "",
               result_summary: Mapping[str, Any] | None = None, error: str | None = None) -> dict:
        with self._transition_lock:
            normalized = _coerce_operation_result(result, status=status, message=message,
                                                  result_summary=result_summary, error=error)
            db_status = "attention_required" if normalized.status == "request_unknown" else normalized.status
            summary = _thaw(normalized.summary)
            summary.setdefault("execution_id", self.execution_id)
            origin = self._origin()
            summary.setdefault("lease_owner", self.execution_id if origin.get("lease_token") else "released")
            if normalized.status == "request_unknown":
                summary.setdefault("outcome", "request_unknown")
                summary.setdefault("reconcile_required", True)
            receipt = self._submit_transition(kind="terminal", payload={
                "run_id": self.run_id, "status": db_status, "message": normalized.message,
                "result_summary": summary, "error": normalized.error,
                "execution_id": self.execution_id, "lease_token": origin.get("lease_token"),
            })
            row = receipt.get("actual_result") or receipt.get("result") or receipt
            actual_status = str(row.get("status") or db_status)
            actual_summary = _thaw(row.get("result_summary") if isinstance(row.get("result_summary"), Mapping) else summary)
            actual_message = str(row.get("message") or row.get("error_message") or normalized.message)
            actual_error = row.get("error_message", row.get("error", normalized.error))
            if actual_summary.get("outcome") == "request_unknown":
                self._last_result = OperationResult.request_unknown(actual_message, actual_summary, error=actual_error)
            else:
                self._last_result = OperationResult(actual_status, actual_summary, actual_message, actual_error)
            self._finished = True
            return _thaw(row)

    @property
    def last_result(self) -> OperationResult | None:
        return self._last_result


def _coerce_operation_result(
    result: OperationResult | Mapping[str, Any] | None,
    *,
    status: str | None = None,
    message: str = "",
    result_summary: Mapping[str, Any] | None = None,
    error: str | None = None,
) -> OperationResult:
    if isinstance(result, OperationResult):
        return result
    if isinstance(result, Mapping):
        result_status = str(result.get("status") or status or "").strip().lower()
        summary = result.get("result_summary")
        if not isinstance(summary, Mapping):
            summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
        if not summary:
            summary = {
                str(key): _thaw(value) for key, value in result.items()
                if key not in {"status", "ok", "message", "error", "result_summary", "summary"}
            }
        result_message = str(result.get("message") or message or "")
        result_error = str(result.get("error") or error) if (result.get("error") or error) else None
        if result_status in {"unknown", "request_unknown"}:
            return OperationResult.request_unknown(
                result_message or result_error or "当前步骤未保存完整回执", dict(summary), error=result_error,
            )
        return OperationResult(result_status or "failed", dict(summary), result_message, result_error)
    result_status = str(status or "").strip().lower()
    if not result_status:
        raise ValueError("handler 必须返回 OperationResult 或显式 status")
    if result_status in {"unknown", "request_unknown"}:
        return OperationResult.request_unknown(message or error or "当前步骤未保存完整回执", result_summary, error=error)
    return OperationResult(result_status, dict(result_summary or {}), message, error)


def _legacy():
    from core.storage.operations import legacy_task_store

    return legacy_task_store


def _operation():
    from core.storage.operations import store as operation

    return operation


def _executor():
    from core.operations.executor import executor

    return executor


def _extract_executor():
    from core.operations.executor import extract_executor

    return extract_executor


_OPERATION_HANDLER_ALLOWLISTS: dict[str, Iterable[str] | Mapping[str, str]] = {}


def registered_operation_types() -> tuple[str, ...]:
    with _DISPATCH_HANDLER_LOCK:
        return tuple(sorted(_OPERATION_HANDLERS))


def register_operation_handler(
    task_type: str,
    handler: Callable[[OperationHandlerContext], Any],
    *,
    source_systems: tuple[str, ...] | list[str] | None = ("native_operations",),
    config_allowlist: Iterable[str] | Mapping[str, str] | None = None,
    retry_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    cancel_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    terminate_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    dispatch_capacity_key: Callable[[Mapping[str, Any]], Any] | None = None,
    dispatch_capacity_limit: Callable[[Any], Any] | None = None,
) -> None:
    """Register the reusable context-based durable handler contract.

    The handler is submitted to its task type's executor by the dispatcher.
    It receives a context only after the worker
    atomically claims the Run; it must perform business writeback and then
    return or call ``context.finish`` with an explicit result.
    """
    name = str(task_type or "").strip()
    if not name:
        raise ValueError("task_type 不能为空")
    from core.operations.concurrency import resolve_admission_class

    resolve_admission_class(name)
    if not callable(handler):
        raise TypeError("operation handler 必须可调用")
    with _DISPATCH_HANDLER_LOCK:
        _OPERATION_HANDLERS[name] = handler
        if config_allowlist is not None:
            _OPERATION_HANDLER_ALLOWLISTS[name] = config_allowlist

    def invoke(run_id: int, *, _task_type: str = name) -> Any:
        return _execute_operation_handler(_task_type, run_id)

    register_dispatch_handler(
        name,
        invoke,
        source_systems=source_systems,
        dispatch_capacity_key=dispatch_capacity_key,
        dispatch_capacity_limit=dispatch_capacity_limit,
    )
    # Maintenance adapters commonly only need to provide their execution
    # handler. Install the shared safe route actions at this boundary so a
    # newly migrated native type remains controllable from the task center.
    # Explicit adapter actions still replace these defaults one at a time.
    register_operation_actions(
        name,
        retry_handler=retry_handler or default_operation_retry,
        cancel_handler=cancel_handler or default_operation_cancel,
        terminate_handler=terminate_handler or default_operation_terminate,
        source_systems=source_systems,
    )


def unregister_operation_handler(task_type: str) -> None:
    name = str(task_type or "").strip()
    with _DISPATCH_HANDLER_LOCK:
        _OPERATION_HANDLERS.pop(name, None)
        _OPERATION_HANDLER_ALLOWLISTS.pop(name, None)
        _OPERATION_ACTIONS.pop(name, None)
        _OPERATION_ACTION_SOURCES.pop(name, None)
    unregister_dispatch_handler(name)


def register_operation_actions(
    task_type: str,
    *,
    retry_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    cancel_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    terminate_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    source_systems: tuple[str, ...] | list[str] | None = ("native_operations",),
) -> None:
    """Register task-type route actions without coupling services to Flask.

    The route supplies the complete task read model.  A handler may return a
    normal response mapping or raise its own domain exception; the route owns
    HTTP status mapping.  Omitting one action preserves a previously installed
    action so adapters can register retry and cancel independently.
    """
    name = str(task_type or "").strip()
    if not name:
        raise ValueError("task_type 不能为空")
    if retry_handler is None and cancel_handler is None and terminate_handler is None:
        return
    with _DISPATCH_HANDLER_LOCK:
        actions = dict(_OPERATION_ACTIONS.get(name) or {})
        if retry_handler is not None:
            actions["retry"] = retry_handler
        if cancel_handler is not None:
            actions["cancel"] = cancel_handler
        if terminate_handler is not None:
            actions["terminate"] = terminate_handler
        _OPERATION_ACTIONS[name] = actions
        if source_systems is None:
            _OPERATION_ACTION_SOURCES[name] = None
        else:
            _OPERATION_ACTION_SOURCES[name] = tuple(
                str(item).strip() for item in source_systems if str(item).strip()
            )


_ACTIVE_OPERATION_TASK_STATUSES = frozenset({
    "queued", "running", "cancelling", "settling", "stopping", "waiting",
})


def default_operation_retry(task: Mapping[str, Any]) -> dict[str, Any]:
    """通过 durable storage 边界重试一个已注册的任务。

    该入口不绑定具体服务：只要任务类型已经注册 handler，任务中心就能在同一逻辑
    任务下创建新的 Run。远端结果未知时保留旧 Run 的请求证据，但不再阻止操作员
    创建新的 Run。
    """
    from core.bulk_operations.execution import retry_managed
    managed_retry = retry_managed(task)
    if managed_retry is not None:
        return managed_retry
    if operation_is_deactivated(task):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已废号，不能重跑",
        }
    if str(task.get("status") or "").strip().lower() in _ACTIVE_OPERATION_TASK_STATUSES:
        return {"accepted": False, "busy": True, "error": "任务仍在执行"}
    task_id = int(task.get("id") or 0)
    if not task_id:
        return {"accepted": False, "busy": False, "error": "任务缺少 id"}
    try:
        run = _operation().retry_runtime_task(
            task_id,
            trigger="manual_retry",
            data={"retry_action": "manual_retry"},
        )
    except (LookupError, ValueError) as exc:
        if "账号已废号" in str(exc):
            return {
                "accepted": False,
                "busy": False,
                "deactivated": True,
                "error": "账号已废号，不能重跑",
            }
        return {
            "accepted": False,
            "busy": False,
            "reconcile_required": "核验" in str(exc),
            "error": str(exc),
        }
    notify_dispatch()
    return {
        "accepted": True,
        "busy": False,
        "reused": False,
        "task_id": task_id,
        "run_id": int(run.get("id") or 0) or None,
        "account_id": int(task.get("account_id") or 0) or None,
        "email": str(task.get("email_snapshot") or ""),
        "status": "queued",
        "source_system": str(task.get("source_system") or "native_operations"),
    }


def default_operation_cancel(task: Mapping[str, Any]) -> dict[str, Any]:
    """Request cooperative cancellation for a registered durable operation."""
    active = next(
        (
            run for run in reversed(task.get("runs") or [])
            if isinstance(run, Mapping)
            and str(run.get("status") or "").strip().lower()
            in _ACTIVE_OPERATION_TASK_STATUSES
        ),
        None,
    )
    if not active:
        return {
            "ok": True,
            "running": False,
            "state": "empty",
            "message": "任务没有活跃 attempt",
        }
    run_id = int(active.get("id") or 0)
    if not run_id:
        return {"ok": False, "error": "活动 attempt 缺少 id"}
    try:
        expected_status = str(task.get("_expected_run_status") or "")
        if expected_status:
            run = _operation().request_run_cancel(
                run_id,
                reason="用户手动停止统一 durable operation",
                expected_status=expected_status,
            )
        else:
            run = _operation().request_run_cancel(
                run_id,
                reason="用户手动停止统一 durable operation",
            )
    except LookupError as exc:
        return {"ok": False, "error": str(exc)}
    if run.get("cancel_skipped"):
        return {
            "ok": False,
            "state": str(run.get("state") or run.get("status") or "unknown"),
            "message": run.get("message") or "任务状态已变化，请刷新后重试",
        }
    notify_dispatch()
    state = str(run.get("status") or "cancelling")
    return {
        "ok": True,
        "run_id": run_id,
        "running": state != "cancelled",
        "state": state,
        "message": "已记录停止请求，任务将在安全检查点收口",
    }


def default_operation_terminate(task: Mapping[str, Any]) -> dict[str, Any]:
    """强制收口一个已注册 durable operation；不尝试杀 worker 线程。"""
    active = next(
        (
            run for run in reversed(task.get("runs") or [])
            if isinstance(run, Mapping)
            and str(run.get("status") or "").strip().lower()
            in _ACTIVE_OPERATION_TASK_STATUSES
        ),
        None,
    )
    if not active:
        return {
            "ok": True,
            "running": False,
            "state": "empty",
            "message": "任务没有活跃 attempt",
        }
    run_id = int(active.get("id") or 0)
    if not run_id:
        return {"ok": False, "error": "活动 attempt 缺少 id"}
    try:
        run = _operation().terminate_run(
            run_id, reason="用户手动终止统一 durable operation",
        )
    except LookupError as exc:
        return {"ok": False, "error": str(exc)}
    notify_dispatch()
    state = str(run.get("status") or "stopped")
    return {
        "ok": True,
        "run_id": run_id,
        "running": state in _ACTIVE_OPERATION_TASK_STATUSES,
        "state": state,
        "message": (
            "任务已取消" if state == "cancelled"
            else "任务已终止，但远端结果待核验" if state == "attention_required"
            else "任务已终止"
        ),
    }


def operation_action(
    task_type: str,
    action: str,
    *,
    source_system: str | None = None,
) -> Callable[[Mapping[str, Any]], Any] | None:
    with _DISPATCH_HANDLER_LOCK:
        name = str(task_type or "").strip()
        handler = (_OPERATION_ACTIONS.get(name) or {}).get(
            str(action or "").strip().lower()
        )
        if handler is None or source_system is None:
            return handler
        allowed_sources = _OPERATION_ACTION_SOURCES.get(name)
        if allowed_sources is not None and str(source_system).strip() not in allowed_sources:
            return None
        return handler


def operation_requires_reconciliation(task: Mapping[str, Any] | None) -> bool:
    """Return whether a task retains unconfirmed remote-result evidence.

    该信号用于展示与人工核验，不再阻止任务中心在同一逻辑任务下创建新的 Run。
    """
    if not isinstance(task, Mapping):
        return False
    if str(task.get("status") or "").strip().lower() == "attention_required":
        return True
    summary = task.get("result_summary")
    if isinstance(summary, Mapping) and (
        str(summary.get("outcome") or "").strip().lower() == "request_unknown"
        or bool(summary.get("reconcile_required"))
    ):
        return True
    for run in task.get("runs") or []:
        if not isinstance(run, Mapping):
            continue
        run_summary = run.get("result_summary")
        if isinstance(run_summary, Mapping) and (
            str(run_summary.get("outcome") or "").strip().lower() == "request_unknown"
            or bool(run_summary.get("reconcile_required"))
        ):
            return True
    actions = task.get("next_actions")
    return any(
        isinstance(item, Mapping)
        and str(item.get("action") or "").strip().lower() == "reconcile"
        for item in (actions if isinstance(actions, list) else [])
    )


def operation_is_deactivated(task: Mapping[str, Any] | None) -> bool:
    """判断任务是否已有明确的账号停用结果。"""
    if not isinstance(task, Mapping):
        return False
    status = str(task.get("status") or "").strip().lower()
    target_status = str(task.get("target_status") or "").strip().lower()
    if status == "deactivated" or target_status in {"deactivated", "account_deactivated"}:
        return True
    summary = task.get("result_summary")
    if not isinstance(summary, Mapping):
        return False
    return any(
        str(summary.get(key) or "").strip().lower() == "deactivated"
        for key in ("status", "requested_status")
    )


def list_reconciliation_accounts(**kwargs: Any) -> list[dict[str, Any]]:
    """Read the shared account fence used by producers before credential writes."""
    return _operation().list_reconciliation_accounts(**kwargs)


def submit_durable_operation(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str = "manual",
    source_system: str = "native_operations",
    source_id: str | None = None,
    idempotency_key: str | None = None,
    account_request_key: str | None = None,
    account_request_target: str | None = None,
    claim_before_create: Callable[[Any], bool] | None = None,
    parent_task_id: int | None = None,
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    resource_family: str = "openai_interactive",
    data: Mapping[str, Any] | None = None,
    config_snapshot: Any | None = None,
    config_snapshot_provider: Callable[[], Any] | None = None,
    config_allowlist: Iterable[str] | Mapping[str, str] | None = None,
    dispatch: bool = True,
    conn=None,
) -> dict[str, Any]:
    """Persist one task/run and optionally wake the shared durable scanner.

    ``source_system`` + ``source_id`` (or ``idempotency_key``) is the
    migration mapping. Config is captured once at submission and only the
    explicit allowlist is stored; no service-specific config is read here.
    """
    name = str(task_type or "").strip()
    if not name:
        return {"accepted": False, "error": "task_type 为空"}
    if account_request_key:
        target = account_request_target or str(account_id)
        source_id = f"{account_receipts.source_prefix(account_request_key)}:{name}:{trigger}:{target}"
    if config_snapshot is None and config_snapshot_provider is not None:
        config_snapshot = config_snapshot_provider()
    if config_snapshot is not None:
        if config_allowlist is None:
            config_allowlist = _OPERATION_HANDLER_ALLOWLISTS.get(name)
        if config_allowlist is None:
            raise ValueError(f"{name} 未提供 config_allowlist，拒绝保存全量配置")
        captured_config = normalize_config_snapshot(
            config_snapshot, allowlist=config_allowlist,
        )
    else:
        captured_config = None
    payload = dict(data or {})
    # Do not silently accept a caller's unfiltered config nested in ``data``.
    payload.pop("config_snapshot", None)
    if captured_config is not None:
        payload["config_snapshot"] = captured_config
    try:
        # 外层逐项事务持有账号锁；保存点保证约束冲突不会污染账号状态回写。
        with (conn.transaction() if conn is not None else nullcontext()):
            created = _operation().create_runtime_task(
                task_type=name,
                account_id=account_id,
                email=str(email or "").strip(),
                trigger=str(trigger or "manual"),
                source_system=str(source_system or "native_operations"),
                source_id=source_id,
                idempotency_key=idempotency_key,
                parent_task_id=parent_task_id,
                batch_id=batch_id,
                batch_ordinal=batch_ordinal,
                resource_family=str(resource_family or "openai_interactive"),
                data=payload,
                **({"account_request": True, "lock_account_request": account_request_target is not None,
                    "claim_before_create": claim_before_create} if account_request_key else {}),
                **({"conn": conn} if conn is not None else {}),
            )
    except Exception as exc:
        if isinstance(exc, OperationAccountDeactivated):
            return {
                "accepted": False,
                "busy": False,
                "deactivated": True,
                "error_code": "account_deactivated",
                "error": str(exc) or "账号已废号，禁止创建任务",
            }
        if "uq_operation_runs_active_account_family" in str(exc) or "duplicate key" in str(exc).lower():
            active = _operation().active_run_for_account(
                int(account_id), str(resource_family or "openai_interactive"),
                **({"conn": conn} if conn is not None else {}),
            ) if account_id else None
            return {
                "accepted": False,
                "busy": True,
                "reused": False,
                "error": "该账号已有排队或运行中的账号操作",
                "task_id": int(active.get("task_id") or 0) or None if active else None,
                "run_id": int(active.get("id") or 0) or None if active else None,
            }
        raise
    if created.get("request_rejected"):
        return {"accepted": False, **created["request_rejected"]}
    run = created.get("run") if isinstance(created.get("run"), Mapping) else {}
    run_id = int(run.get("id") or 0) or None
    task_id = int(created.get("id") or 0) or None
    status = str(run.get("status") or created.get("status") or "queued")
    reused = bool(created.get("idempotent"))
    result: dict[str, Any] = {
        "accepted": True,
        # ``busy`` is a rejection/conflict signal for compatibility callers;
        # a newly accepted durable queue item is not a busy result.
        "busy": bool(not account_request_key and reused and status in {"queued", "running", "cancelling", "settling", "waiting"}),
        "reused": reused,
        "task_id": task_id,
        "run_id": run_id,
        "account_id": int(account_id) if account_id else None,
        "email": str(email or "").strip(),
        "status": status,
        "source_system": str(created.get("source_system") or source_system),
        "source_id": str(created.get("source_id") or source_id or idempotency_key or ""),
        "trigger": str(trigger or "manual"),
    }
    if captured_config is not None:
        result["config_snapshot_revision"] = captured_config.get("config_snapshot_revision")
    if dispatch and not reused:
        notify_dispatch()
    return result


def _operation_handler_result_payload(
    context: OperationHandlerContext,
    result: OperationResult,
    *,
    database_status: str | None = None,
) -> dict[str, Any]:
    if context.finished and context.last_result is not None:
        result = context.last_result
        database_status = "attention_required" if result.status == "request_unknown" else result.status
    payload = result.as_dict()
    payload.update({
        "task_id": context.task_id,
        "run_id": context.run_id,
        "source_system": context.source_system,
        "database_status": database_status or (
            "attention_required" if result.status == "request_unknown" else result.status
        ),
    })
    if result.status in {"request_unknown", "attention_required"}:
        # 业务调用方接收具体失败；数据库的待核验状态继续保护原始请求。
        payload.update({
            "status": "failed", "ok": False, "reconcile_required": True,
            "manual_reconcile": True, "next_action": "manual_reconcile",
        })
    return payload


def _execute_operation_handler(task_type: str, run_id: int) -> dict[str, Any]:
    """Claim and run one context handler inside the shared executor budget."""
    with _DISPATCH_HANDLER_LOCK:
        handler = _OPERATION_HANDLERS.get(str(task_type))
    if handler is None:
        return {"status": "not_registered", "run_id": int(run_id)}
    from core.operations import concurrency

    execution = concurrency.current_execution()
    if execution is None:
        run = _operation().get_run(int(run_id))
        if not run:
            return {"status": "not_claimed", "run_id": int(run_id)}
        admitted = admit_operation_run(run)
        if not admitted.admitted:
            return {"status": "queued", "run_id": int(run_id), "blocked_by": list(admitted.blocked_by)}
        return execute_admitted(admitted.context, lambda: _execute_operation_handler(task_type, run_id))
    if int(execution.claimed_run.get("id") or 0) != int(run_id) or not concurrency.validate_execution(execution):
        return {"status": "fenced", "run_id": int(run_id), "reason": "permit_owner_lost"}
    execution_id = execution.execution_id
    claimed = execution.claimed_run
    context = OperationHandlerContext(claimed, execution_id=execution_id)
    if claimed.get("_deactivated_before_execution"):
        result = OperationResult("deactivated", {"status": "deactivated", "reason": "account_deactivated_before_execution"},
                                 "账号已确认停用，队列任务未执行")
        context.finish(result)
        return _operation_handler_result_payload(context, result)
    from core.operations.executor import operation_log_context
    from core.storage.email.address_allocations import OtpLeaseBusy

    with operation_log_context(context):
        try:
            from core.auth.email_guard import email_auth_session

            auth_scope = (
                email_auth_session(context.email)
                if context.resource_family in {"openai_interactive", "registration_completion"} and context.email
                else nullcontext(None)
            )
            with _domain_scope(context._domain), operation_context(context.cancellation, reporter=context.report), auth_scope as auth_session:
                context.checkpoint()
                returned = handler(context)
                if auth_session is not None and not context.deferred:
                    auth_session.set_result(context.last_result if context.finished else returned)
            if context.deferred:
                return dict(context._deferred_result)
            if not context.finished:
                if returned is None:
                    raise RuntimeError("durable operation handler 未报告 terminal result")
                context.finish(returned)
            if context.last_result is not None:
                result = context.last_result
            elif returned is not None:
                result = _coerce_operation_result(returned, status="failed", message="")
            else:
                result = OperationResult.failed("durable operation handler 未报告 terminal result")
            return _operation_handler_result_payload(
                context, result,
                database_status="attention_required" if result.status == "request_unknown" else result.status,
            )
        except OperationResourceCleanupPending as exc:
            return context.finish_cleanup_failure(exc)
        except SETTLEMENT_CONTROL_ERRORS:
            raise
        except (OperationLeaseUnavailable, OtpLeaseBusy) as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            if context.is_cancel_requested(force=True):
                result = OperationResult.cancelled("任务在取得账号 lease 前收到取消请求")
                if not context.finished:
                    context.finish(result)
                return _operation_handler_result_payload(context, result)
            return context.defer(delay_seconds=1.0, reason=str(exc), stage="lease_wait")
        except OperationAccountDeactivated as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            result = OperationResult(
                "deactivated",
                {
                    "status": "deactivated",
                    "requested_status": "deactivated",
                    "reason": "account_deactivated",
                    "execution_id": execution_id,
                },
                str(exc) or "账号已废号，任务未执行",
                str(exc) or "账号已废号，任务未执行",
            )
            if not context.finished:
                context.finish(result)
            return _operation_handler_result_payload(context, result)
        except OperationLeaseLost as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            # A lost lease can mean that a remote write was accepted. Never
            # requeue this run; preserve the attempt for reconciliation instead.
            result = OperationResult.request_unknown(
                "账号 lease 心跳失败，远端结果待核验",
                {"lease_lost": True, "error": str(exc), "execution_id": execution_id},
            )
            try:
                if not context.finished:
                    context.finish(result)
            except SETTLEMENT_CONTROL_ERRORS:
                raise
            except PermissionError:
                logger.error("写入 lease 丢失的 request_unknown 结果被 fence 拒绝：run_id=%s", run_id)
                return {
                    "status": "fenced",
                    "run_id": context.run_id,
                    "task_id": context.task_id,
                    "reason": str(exc),
                }
            return _operation_handler_result_payload(context, result)
        except OperationCancelled as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            result = OperationResult.cancelled(str(exc) or "任务已在安全检查点取消")
            if not context.finished:
                context.finish(result)
            return _operation_handler_result_payload(context, result)
        except PermissionError as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            # A terminal write can race with lease expiry/recovery.  Keep this
            # worker from reporting a misleading failure or touching a newer
            # execution; the fenced row remains available for reconciliation.
            logger.warning(
                "durable operation result 被 execution/lease fence 拒绝：task_type=%s run_id=%s",
                task_type, run_id,
            )
            return {
                "status": "fenced",
                "run_id": context.run_id,
                "task_id": context.task_id,
                "reason": str(exc),
            }
        except Exception as exc:
            context.raise_if_settlement_pending()
            if context.deferred:
                return _thaw(context._deferred_result)
            if context.finished and context.last_result is not None:
                return _operation_handler_result_payload(context, context.last_result)
            logger.exception("durable operation handler 执行失败：task_type=%s run_id=%s", task_type, run_id)
            if context.deferred:
                return dict(context._deferred_result)
            result = OperationResult.failed(f"{type(exc).__name__}: {exc}")
            if not context.finished:
                context.finish(result)
            return _operation_handler_result_payload(context, result)
        finally:
            try:
                concurrency.set_execution_state(execution, "cleaning")
            except Exception:
                logger.exception("执行清理状态暂未同步，许可继续保留：run_id=%s", run_id)
            # Participating final scopes belong to their immutable transition;
            # the coordinator acts only after callback_exited. Step cleanup is
            # retained as an exact handle if its DELETE is still unconfirmed.
            if not _participates(execution):
                context.release_lease()

def init() -> None:
    return _legacy().init()


def create_batch(**kwargs: Any) -> str:
    return _legacy().create_batch(**kwargs)


def create_task(**kwargs: Any) -> int:
    return _legacy().create_task(**kwargs)


def start_task(task_id: int | None, **kwargs: Any) -> None:
    return _legacy().start_task(task_id, **kwargs)


def append_event(task_id: int | None, **kwargs: Any) -> None:
    return _legacy().append_event(task_id, **kwargs)


def finish_task(task_id: int | None, **kwargs: Any) -> None:
    result = _legacy().finish_task(task_id, **kwargs)
    if task_id:
        _mark_dependency_ready(
            child_source_system="account_action_tasks",
            child_source_id=str(int(task_id)),
            child_status=str(kwargs.get("status") or "failed"),
            child_result=kwargs.get("result_summary") if isinstance(kwargs.get("result_summary"), dict) else {},
        )
    return result


def recover_interrupted(**kwargs: Any) -> int:
    """Recover compatibility tasks outside the row-level durable fences."""
    return _legacy().recover_interrupted(**kwargs)


def list_tasks(**kwargs: Any) -> dict:
    return _legacy().list_tasks(**kwargs)


def get_task(task_id: int) -> dict | None:
    return _legacy().get_task(task_id)


def register_task_dependency(**kwargs: Any) -> dict:
    """Persist a handoff between legacy and native task IDs."""
    return _operation().register_task_dependency(**kwargs)


def _mark_dependency_ready(**kwargs: Any) -> None:
    try:
        ready = _operation().mark_task_dependency_ready(**kwargs)
    except Exception:
        logger.exception(
            "更新账号任务父子依赖失败：child=%s:%s",
            kwargs.get("child_source_system"), kwargs.get("child_source_id"),
        )
        return
    if ready:
        # Wake the one persistent claim owner.  Do not invoke a callback on
        # the child worker stack and do not claim rows in this notification
        # path.
        notify_dependency_ready(ready[0])


def set_dependency_ready_handler(handler: Callable[[dict], Any] | None) -> None:
    """Install the continuation submission hook used by the WebUI runtime."""
    global _DEPENDENCY_HANDLER
    with _DEPENDENCY_HANDLER_LOCK:
        _DEPENDENCY_HANDLER = handler
    _DEPENDENCY_WAKE.set()


def _dependency_handler() -> Callable[[dict], Any] | None:
    with _DEPENDENCY_HANDLER_LOCK:
        return _DEPENDENCY_HANDLER


def _dependency_tick() -> int:
    from core.runtime.execution_access import execution_allowed
    if not execution_allowed():
        return 0
    handler = _dependency_handler()
    if handler is None:
        return 0
    # Do not claim a large ready backlog while the shared account-operation
    # budget is already full. The callback still rechecks the budget because
    # another producer can win the race between this snapshot and submit.
    claimed_count = 0
    try:
        slots = _executor().available_slots()
        if slots <= 0:
            return 0
        candidates = _operation().list_ready_task_dependencies(
            limit=min(_DEPENDENCY_BATCH_SIZE, slots),
            initialize=False,
        )
        for candidate in candidates:
            # This is the only claim site in the process. A second process can
            # race safely because the SQL update is a ready->running CAS.
            from core.operations import concurrency

            dependency_id = int(candidate.get("id") or 0)
            payload = candidate.get("payload") if isinstance(candidate.get("payload"), Mapping) else {}
            account_id = payload.get("account_id")
            admission = concurrency.try_admit_and_claim(
                execution_key=f"operation_dependency:{dependency_id}", task_type="account_setup_retry",
                claim=lambda conn, execution_id, dependency_id=dependency_id: _operation().claim_task_dependency(
                    dependency_id, initialize=False, conn=conn,
                ),
                metadata={key: candidate.get(key) for key in ("parent_source_system", "parent_source_id")},
                extra_scopes=[{"kind": "account", "key": f"{int(account_id)}:openai_interactive", "limit": 1}]
                if account_id else [],
            )
            if not admission.admitted:
                continue
            claimed = dict(admission.context.claimed_run)
            claimed["_execution_context"] = admission.context
            if not execution_allowed():
                rollback_admission(admission.context, reason="runtime_execution_paused")
                continue
            claimed_count += 1
            try:
                # The callback is a non-blocking executor submission boundary.
                # It must return the row to ready itself when the shared budget
                # is full.
                handler(dict(claimed))
            except Exception as exc:
                logger.exception(
                    "提交父任务依赖续接失败：dependency_id=%s", claimed.get("id"),
                )
                try:
                    rollback_admission(admission.context, reason="executor_submit_failed")
                except Exception:
                    logger.exception(
                        "父任务依赖失败状态写回失败：dependency_id=%s", claimed.get("id"),
                    )
    except Exception as exc:
        logger.exception("dependency_scheduler_unavailable：父任务依赖调度暂不可用，保留持久队列：error_type=%s", type(exc).__name__)
    return claimed_count


def _dependency_loop() -> None:
    while not _DEPENDENCY_STOP.is_set():
        claimed = _dependency_tick()
        if claimed:
            # Drain only a finite batch per pass. This prevents a large ready
            # backlog from starving the rest of the process.
            continue
        _DEPENDENCY_WAKE.wait(_DEPENDENCY_INTERVAL_SECONDS)
        _DEPENDENCY_WAKE.clear()


def start_dependency_dispatcher(
    *, interval_seconds: float = 0.5, batch_size: int = 32,
) -> bool:
    """Start one persistent ready-queue scanner for completion handoffs."""
    from core.runtime.execution_access import component_start_allowed
    if not component_start_allowed():
        return False
    global _DEPENDENCY_THREAD, _DEPENDENCY_INTERVAL_SECONDS, _DEPENDENCY_BATCH_SIZE
    with _DEPENDENCY_LOCK:
        _DEPENDENCY_INTERVAL_SECONDS = max(0.05, min(30.0, float(interval_seconds)))
        _DEPENDENCY_BATCH_SIZE = max(1, min(500, int(batch_size)))
        if _DEPENDENCY_THREAD is not None and _DEPENDENCY_THREAD.is_alive():
            _DEPENDENCY_WAKE.set()
            return False
        _DEPENDENCY_STOP.clear()
        try:
            recovered = _operation().recover_stale_task_dependencies()
            if recovered:
                logger.warning("已恢复 %s 个超时的父任务依赖 claim", recovered)
        except Exception:
            logger.exception("恢复父任务依赖 claim 失败；持久 ready 扫描仍会继续")
        _DEPENDENCY_WAKE.set()
        _DEPENDENCY_THREAD = threading.Thread(
            target=_dependency_loop,
            name="operation-dependency-dispatcher",
            daemon=True,
        )
        _DEPENDENCY_THREAD.start()
        return True


def stop_dependency_dispatcher(*, timeout: float = 2.0) -> bool:
    global _DEPENDENCY_THREAD
    with _DEPENDENCY_LOCK:
        thread = _DEPENDENCY_THREAD
        if thread is None:
            return True
        _DEPENDENCY_STOP.set()
        _DEPENDENCY_WAKE.set()
    thread.join(max(0.0, float(timeout)))
    with _DEPENDENCY_LOCK:
        if _DEPENDENCY_THREAD is thread and not thread.is_alive():
            _DEPENDENCY_THREAD = None
    return not thread.is_alive()


def dependency_dispatcher_status() -> dict[str, object]:
    with _DEPENDENCY_LOCK:
        thread = _DEPENDENCY_THREAD
        return {
            "started": thread is not None,
            "alive": bool(thread and thread.is_alive()),
            "name": thread.name if thread is not None else None,
            "claim_owner": "operation-dependency-dispatcher",
        }


def notify_dependency_ready(dependency: dict | None = None) -> None:
    """Wake the persistent scanner for a row already marked ``ready``."""
    _DEPENDENCY_WAKE.set()


def drain_ready_dependencies(*, limit: int = 100, initialized: bool = False) -> int:
    """Wake and count durable ready rows without claiming them.

    Startup and child completion share the same scanner. Keeping this method
    notification-only is important: a startup caller must not claim a row and
    then hand it to a callback that attempts a second ready->running CAS.
    """
    rows = _operation().list_ready_task_dependencies(
        limit=limit, initialize=not initialized,
    )
    _DEPENDENCY_WAKE.set()
    return len(rows)


def register_dispatch_handler(
    task_type: str,
    handler: Callable[[int], Any],
    *,
    source_systems: tuple[str, ...] | list[str] | None = ("native_operations",),
    dispatch_capacity_key: Callable[[Mapping[str, Any]], Any] | None = None,
    dispatch_capacity_limit: Callable[[Any], Any] | None = None,
) -> None:
    """Register a durable run handler by task type and source namespace.

    Native handlers default to native rows so a compatibility task that still
    has its old service scheduler cannot be executed a second time. A handler
    that has completed a source migration can explicitly pass ``None`` or its
    allowed source systems.
    """
    name = str(task_type or "").strip()
    if not name:
        raise ValueError("task_type 不能为空")
    from core.operations.concurrency import resolve_admission_class

    resolve_admission_class(name)
    if not callable(handler):
        raise TypeError("task handler 必须可调用")
    if (dispatch_capacity_key is None) != (dispatch_capacity_limit is None):
        raise ValueError("dispatch capacity key 和 limit 必须同时提供")
    if dispatch_capacity_key is not None and not callable(dispatch_capacity_key):
        raise TypeError("dispatch capacity key 必须可调用")
    if dispatch_capacity_limit is not None and not callable(dispatch_capacity_limit):
        raise TypeError("dispatch capacity limit 必须可调用")
    allowed_sources = None if source_systems is None else tuple(
        str(item).strip() for item in source_systems if str(item).strip()
    )
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS[name] = (handler, allowed_sources)
        if dispatch_capacity_key is None:
            _DISPATCH_CAPACITY_HANDLERS.pop(name, None)
        else:
            _DISPATCH_CAPACITY_HANDLERS[name] = (
                dispatch_capacity_key,
                dispatch_capacity_limit,
            )
    _RUN_DISPATCH_WAKE.set()


def unregister_dispatch_handler(task_type: str) -> None:
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS.pop(str(task_type or "").strip(), None)
        _DISPATCH_CAPACITY_HANDLERS.pop(str(task_type or "").strip(), None)
        _OPERATION_HANDLERS.pop(str(task_type or "").strip(), None)
        _OPERATION_HANDLER_ALLOWLISTS.pop(str(task_type or "").strip(), None)
        _OPERATION_ACTIONS.pop(str(task_type or "").strip(), None)
        _OPERATION_ACTION_SOURCES.pop(str(task_type or "").strip(), None)


def registered_dispatch_types() -> tuple[str, ...]:
    with _DISPATCH_HANDLER_LOCK:
        return tuple(sorted(_DISPATCH_HANDLERS))


def reserve_dispatch(run_id: int) -> bool:
    """Reserve a run for either direct submit or the persistent scanner."""
    with _RUN_DISPATCH_LOCK:
        value = int(run_id)
        if value in _RUN_DISPATCHED:
            return False
        _RUN_DISPATCHED.add(value)
        return True


def release_dispatch(run_id: int) -> None:
    with _RUN_DISPATCH_LOCK:
        _RUN_DISPATCHED.discard(int(run_id))
    _RUN_DISPATCH_WAKE.set()


def _run_handler_snapshot() -> tuple[
    dict[str, tuple[Callable[[int], Any], tuple[str, ...] | None]],
    dict[str, tuple[Callable[[Mapping[str, Any]], Any], Callable[[Any], Any]]],
]:
    with _DISPATCH_HANDLER_LOCK:
        return dict(_DISPATCH_HANDLERS), dict(_DISPATCH_CAPACITY_HANDLERS)


def _is_extract_continuation(run: Mapping[str, Any]) -> bool:
    data = run.get("data")
    return bool(
        str(run.get("task_type") or "") == "extract_link"
        and isinstance(data, Mapping)
        and (run.get("dispatch_lane") == "continuation"
             or (data.get("provider_id") in {"huanguang", "legacy", "anguang"}
                 and data.get("extract_poll_continuation") is True))
    )


def _operation_admission_arguments(run: Mapping[str, Any], capacity_handler=None, *, observation=False) -> dict:
    from core.operations import concurrency

    task_type = str(run.get("task_type") or "")
    classification = concurrency.resolve_admission_class(run)
    data = run.get("data") if isinstance(run.get("data"), Mapping) else {}
    batch_key = f"operation:{run['batch_id']}" if run.get("batch_id") else None
    batch_limit = run.get("batch_workers")
    provider = str(data.get("provider_id") or "legacy") if task_type == "extract_link" else None
    provider_limit = None
    extra_scopes = []
    if run.get("account_id"):
        extra_scopes.append({"kind": "account", "key": f"{int(run['account_id'])}:{run.get('resource_family') or 'openai_interactive'}", "limit": 1})
        if data.get("registration_completion") and run.get("resource_family") == "registration_completion":
            extra_scopes.append({"kind": "account", "key": f"{int(run['account_id'])}:openai_interactive", "limit": 1})
    if capacity_handler is None:
        with _DISPATCH_HANDLER_LOCK:
            capacity_handler = _DISPATCH_CAPACITY_HANDLERS.get(task_type)
    if capacity_handler is not None:
        key_fn, limit_fn = capacity_handler
        raw = key_fn(run)
        requirements = raw if isinstance(raw, Mapping) else {str(raw): limit_fn(raw)}
        for key, value in requirements.items():
            if str(key).startswith("batch:"):
                batch_limit = int(value)
            elif task_type == "extract_link" and str(key) == provider:
                provider_limit = int(value)
            else:
                extra_scopes.append({"kind": "resource", "key": f"{task_type}:{key}", "limit": int(value)})
    if _is_extract_continuation(run):
        # 平台上限在同连接读取当前策略；续查独立最多两项，不能缓存旧平台值形成隐藏门限。
        extra_scopes.append({"kind": "continuation", "key": str(provider), "limit": 2})
    if data.get("bulk_target_round_id"):
        batch_limit = None
        fixed_scopes = tuple(extra_scopes)
        def managed_scopes(conn):
            from core.storage.operations import store
            with conn.cursor() as cur:
                cur.execute(f"""SELECT c.batch_id,c.desired_workers FROM {store._table('operation_batch_controls')} c
                    JOIN {store._table('operation_batch_target_rounds')} tr ON tr.batch_id=c.batch_id
                    JOIN {store._table('operation_batch_run_links')} l ON l.target_round_id=tr.id
                    WHERE l.run_id=%s AND l.relation IN ('owned_root','owned_child','owned_continuation')""", (int(run["id"]),))
                managed = cur.fetchone()
            if managed is None:
                raise concurrency.ConcurrencyPolicyError("bulk_ownership_missing", "批量执行归属缺失，暂停新准入")
            return [*fixed_scopes, {"kind": "batch", "key": f"operation:{managed['batch_id']}", "limit": int(managed["desired_workers"])}]
        extra_scopes = fixed_scopes if observation else managed_scopes
    run_id = int(run["id"])
    return dict(
        execution_key=f"operation_run:{run_id}", task_type=classification.key, run_id=run_id,
        batch_key=batch_key, batch_limit=int(batch_limit) if batch_limit is not None else None,
        provider_key=provider, provider_limit=provider_limit, extra_scopes=extra_scopes,
        metadata={"dispatch_lane": "continuation" if _is_extract_continuation(run) else "new"},
    )


def admit_operation_run(run: Mapping[str, Any], capacity_handler=None):
    """同事务取得多维许可并认领 Run；worker 只接收已认领上下文。"""
    from core.operations import concurrency

    return concurrency.try_admit_and_claim(
        **_operation_admission_arguments(run,capacity_handler),
        claim=lambda conn,execution_id: _operation().claim_run(
            int(run["id"]),execution_id=execution_id,worker_pid=os.getpid(),conn=conn),
    )


def observe_operation_runs(runs: list[Mapping[str, Any]], capacity_handlers=None):
    """满载候选集合观察，批次约束也在同一只读配置快照内一次定位。"""
    from core.operations import concurrency
    capacity_handlers = capacity_handlers or {}
    requests = [_operation_admission_arguments(run,capacity_handlers.get(str(run.get("task_type") or "")),observation=True) for run in runs]
    managed_ids = [int(run["id"]) for run in runs if (run.get("data") or {}).get("bulk_target_round_id")]
    def prepare_scopes(conn):
        if not managed_ids:
            return {}
        from core.storage.operations import store
        with conn.cursor() as cur:
            cur.execute(f"""SELECT l.run_id,c.batch_id,c.desired_workers
                FROM {store._table('operation_batch_run_links')} l
                JOIN {store._table('operation_batch_target_rounds')} tr ON tr.id=l.target_round_id
                JOIN {store._table('operation_batch_controls')} c ON c.batch_id=tr.batch_id
                WHERE l.run_id=ANY(%s) AND l.relation IN ('owned_root','owned_child','owned_continuation')""", (managed_ids,))
            limits = {int(row["run_id"]): row for row in cur.fetchall()}
        result = {}
        for item in requests:
            if item["run_id"] not in managed_ids:
                continue
            managed = limits.get(item["run_id"])
            if managed is None:
                raise concurrency.ConcurrencyPolicyError("bulk_ownership_missing", "批量执行归属缺失，暂停等待观察")
            result[item["execution_key"]] = [*item["extra_scopes"], {"kind": "batch", "key": f"operation:{managed['batch_id']}", "limit": int(managed["desired_workers"])}]
        return result
    return concurrency.observe_waiting_many(requests, prepare_scopes=prepare_scopes)


def observe_operation_run(run: Mapping[str, Any], capacity_handler=None):
    handlers = {str(run.get("task_type") or ""): capacity_handler} if capacity_handler is not None else None
    return observe_operation_runs([run], handlers)[0]


def _participates(execution) -> bool:
    return bool(getattr(execution, "settlement_ticket", None))


def _handoff_execution(execution, *, reason="worker_exit") -> None:
    if _participates(execution):
        from core.operations import settlement
        settlement.request_release(execution, reason=reason)
    else:
        from core.operations import concurrency
        concurrency.release_execution(execution, reason=reason)
    notify_dispatch()


def execute_admitted(execution, callback: Callable[[], Any]):
    from core.operations import concurrency, settlement
    from core.runtime.execution_access import execution_allowed

    participant = _participates(execution)
    callback_started = False
    rolled_back = False
    try:
        with concurrency.execution_scope(execution):
            if not execution_allowed():
                rolled_back = True
                rollback_admission(execution, reason="runtime_execution_paused")
                return None
            if participant:
                if not settlement.callback_started(execution):
                    return None
                callback_started = True
            return callback()
    except Exception:
        if participant and not callback_started and not rolled_back:
            # Scope validation and its first permit heartbeat occur before the
            # business start barrier. They may fail after durable admission,
            # so they own the same exact rollback receipt as submit rejection.
            rolled_back = True
            rollback_admission(execution, reason="execution_scope_entry_failed")
        raise
    finally:
        if participant and callback_started:
            settlement.callback_exited(execution)
        if not rolled_back:
            _handoff_execution(execution)


def rollback_admission(execution, *, reason: str = "executor_submit_failed") -> None:
    """Rollback only before callback start; retain original receipt responsibility."""
    if _participates(execution):
        from core.operations import settlement
        frozen = getattr(execution, "_gateway_rollback_intent", None)
        if frozen is None:
            claimed = execution.claimed_run
            origin = _thaw(execution.settlement_ticket)
            origin.update(lease_requirement="accountless" if not claimed.get("account_id") else "not_acquired",
                          lease_token=None, leases=[])
            frozen = seal_intent(kind="defer", origin=origin, payload={
                "run_id": int(claimed["id"]), "execution_id": execution.execution_id,
                "lease_token": None, "reason": str(reason), "delay_seconds": 0,
                "data": None, "stage": "dispatch", "subtype": "unstarted_rollback",
            })
            execution._gateway_rollback_intent = frozen

        def submit(intent, deadline):
            from core.storage.operations.settlements import submit_intent
            return submit_intent(intent, domain=execution.settlement_domain, deadline=deadline)

        try:
            settlement.settle(execution, frozen, submit)
        finally:
            # settle owns the unstarted/start barrier and the exit fact; a
            # racing callback must never be marked exited by this caller.
            settlement.request_release(execution, reason=reason)
            notify_dispatch()
        return
    from core.operations import concurrency
    try:
        claimed = execution.claimed_run
        run_id = int(claimed.get("id") or 0)
        if str(execution.execution_key).startswith("operation_dependency:"):
            from core.storage.operations import dependency_handoffs
            dependency_handoffs.requeue_dependency(run_id, permit_id=execution.permit_id,
                execution_id=execution.execution_id, attempts=int(claimed.get("attempts") or 0), reason=reason)
        elif run_id:
            _operation().requeue_claimed_run(run_id, execution_id=execution.execution_id,
                                            reason=reason, delay_seconds=0)
    finally:
        concurrency.release_execution(execution, reason=reason)
        notify_dispatch()


def dispatch_registered_once(*, limit: int | None = None) -> int:
    """所有类型共享持久公平游标与数据库业务预算，线程承载保留领域隔离。"""
    from core.runtime.execution_access import execution_allowed
    if not execution_allowed():
        return 0
    handlers, capacity_handlers = _run_handler_snapshot()
    if not handlers:
        return 0
    return _dispatch_registered_group(handlers, capacity_handlers, None, limit=limit)


def _dispatch_registered_group(handlers, capacity_handlers, pool, *, limit: int | None = None) -> int:
    global _PREFER_EXTRACT_CONTINUATIONS
    # 每轮只读一次承载配置；最终许可和try_submit仍在实际提交时校验。
    account_pool = pool if pool is not None else _executor() if any(name != "extract_link" for name in handlers) else None
    extract_pool = pool if pool is not None else _extract_executor() if "extract_link" in handlers else None
    carriers = {id(value): value for value in (account_pool, extract_pool) if value is not None}
    capacity_hints = {key: carrier.available_slots() for key, carrier in carriers.items()}
    slots = sum(capacity_hints.values())
    source_systems: set[str] = set()
    accepts_all_sources = False
    for _handler, allowed_sources in handlers.values():
        if allowed_sources is None:
            accepts_all_sources = True
            break
        source_systems.update(allowed_sources)
    if not accepts_all_sources and not source_systems:
        return 0
    requested_limit = int(limit or (_RUN_DISPATCH_BATCH_SIZE * 2))
    scan_limit = max(1,slots,min(5000,requested_limit))
    with _RUN_DISPATCH_LOCK:
        prefer_continuations = _PREFER_EXTRACT_CONTINUATIONS
    try:
        runs = _operation().list_dispatchable_runs(
            limit=scan_limit,
            task_types=tuple(handlers),
            source_systems=None if accepts_all_sources else tuple(sorted(source_systems)),
            prioritize_continuations=prefer_continuations,
        )
    except (AttributeError, TypeError):
        # Compatibility with an older storage wrapper during a rolling update.
        try:
            runs = _operation().list_queued_runs(limit=scan_limit)
        except AttributeError:
            runs = []
    from core.operations.concurrency import order_dispatch_candidates

    runs = order_dispatch_candidates(runs)
    submitted = 0
    waiting_observations = []
    for run in runs:
        task_type = str(run.get("task_type") or "")
        entry = handlers.get(task_type)
        if entry is None:
            continue
        handler, allowed_sources = entry
        source_system = str(run.get("source_system") or "")
        if allowed_sources is not None and source_system not in allowed_sources:
            continue
        selected_pool = pool if pool is not None else extract_pool if task_type == "extract_link" else account_pool
        if capacity_hints[id(selected_pool)] <= 0:
            waiting_observations.append(run)
            continue
        if submitted >= slots:
            continue
        if not reserve_dispatch(int(run["id"])):
            continue
        try:
            admission = admit_operation_run(run, capacity_handlers.get(task_type))
        except Exception:
            release_dispatch(int(run["id"]))
            logger.exception("业务准入失败，任务保留排队：run_id=%s", run.get("id"))
            continue
        if not admission.admitted:
            release_dispatch(int(run["id"]))
            continue
        execution = admission.context
        try:
            future = selected_pool.try_submit(
                lambda run_id, execution=execution, handler=handler: execute_admitted(execution, lambda: handler(run_id)),
                int(run["id"]),
            )
        except Exception:
            release_dispatch(int(run["id"]))
            rollback_admission(execution)
            logger.exception("提交 durable operation 失败：run_id=%s", run.get("id"))
            continue
        if future is None:
            release_dispatch(int(run["id"]))
            rollback_admission(execution)
            break
        submitted += 1
        capacity_hints[id(selected_pool)] -= 1
        data = run.get("data")
        if task_type == "extract_link" and isinstance(data, Mapping) and data.get("provider_id") in {"huanguang", "legacy", "anguang"}:
            with _RUN_DISPATCH_LOCK:
                _PREFER_EXTRACT_CONTINUATIONS = not _is_extract_continuation(run)
        try:
            def completed(_completed, *, run_id=int(run["id"]), execution=execution):
                from core.operations import concurrency

                release_dispatch(run_id)
                if _completed is not None and _completed.cancelled():
                    rollback_admission(execution, reason="submission_cancelled")
                else:
                    _handoff_execution(execution, reason="future_completed")

            future.add_done_callback(completed)
        except Exception:
            release_dispatch(int(run["id"]))
    if waiting_observations:
        try:
            observe_operation_runs(waiting_observations,capacity_handlers)
        except Exception:
            logger.exception("等待原因集合观察暂不可用，任务继续排队：count=%s", len(waiting_observations))
    return submitted


def notify_dispatch() -> None:
    """Wake the durable task dispatcher after a new run is persisted."""
    _RUN_DISPATCH_WAKE.set()


def _reconcile_recovered_projections() -> int:
    """兼容旧入口，领域恢复编排由核心 reconciliation 服务拥有。"""
    from core.operations import reconciliation

    return reconciliation.reconcile_recovered_projections(logger)


def _recover_stale_runtime_runs_if_due(*, now: float | None = None) -> int:
    """周期性收口失去 worker 的 Run；节流状态仍由唯一 dispatcher 持有。"""
    global _LAST_RUNTIME_RECOVERY_AT
    current = time.monotonic() if now is None else float(now)
    with _RUN_DISPATCH_LOCK:
        if current - _LAST_RUNTIME_RECOVERY_AT < _RUNTIME_RECOVERY_INTERVAL_SECONDS:
            return 0
        _LAST_RUNTIME_RECOVERY_AT = current
    from core.operations import reconciliation

    return reconciliation.recover_stale_runtime_runs(logger)


def _run_dispatch_loop() -> None:
    from core.runtime.execution_access import execution_allowed
    while not _RUN_DISPATCH_STOP.is_set():
        try:
            submitted = 0
            if execution_allowed():
                _recover_stale_runtime_runs_if_due()
                submitted = dispatch_registered_once()
        except Exception:
            submitted = 0
            logger.exception("scheduler_store_unavailable：本轮暂停新准入，保留持久队列")
        if submitted:
            continue
        _RUN_DISPATCH_WAKE.wait(_RUN_DISPATCH_INTERVAL_SECONDS)
        _RUN_DISPATCH_WAKE.clear()


def start_dispatcher(*, interval_seconds: float = 0.5, batch_size: int = 32) -> bool:
    """Start the shared task-type dispatcher for durable operation runs."""
    from core.runtime.execution_access import component_start_allowed
    if not component_start_allowed():
        return False
    global _RUN_DISPATCH_THREAD, _RUN_DISPATCH_INTERVAL_SECONDS, _RUN_DISPATCH_BATCH_SIZE
    with _RUN_DISPATCH_LOCK:
        _RUN_DISPATCH_INTERVAL_SECONDS = max(0.05, min(30.0, float(interval_seconds)))
        _RUN_DISPATCH_BATCH_SIZE = max(1, min(500, int(batch_size)))
        if _RUN_DISPATCH_THREAD is not None and _RUN_DISPATCH_THREAD.is_alive():
            _RUN_DISPATCH_WAKE.set()
            return False
        _RUN_DISPATCH_STOP.clear()
        _RUN_DISPATCH_WAKE.set()
        _RUN_DISPATCH_THREAD = threading.Thread(
            target=_run_dispatch_loop,
            name="operation-task-dispatcher",
            daemon=True,
        )
        _RUN_DISPATCH_THREAD.start()
        return True


def stop_dispatcher(*, timeout: float = 2.0) -> bool:
    global _RUN_DISPATCH_THREAD
    with _RUN_DISPATCH_LOCK:
        thread = _RUN_DISPATCH_THREAD
        if thread is None:
            return True
        _RUN_DISPATCH_STOP.set()
        _RUN_DISPATCH_WAKE.set()
    thread.join(max(0.0, float(timeout)))
    with _RUN_DISPATCH_LOCK:
        if _RUN_DISPATCH_THREAD is thread and not thread.is_alive():
            _RUN_DISPATCH_THREAD = None
    return not thread.is_alive()


def dispatcher_status() -> dict[str, object]:
    with _RUN_DISPATCH_LOCK:
        thread = _RUN_DISPATCH_THREAD
        return {
            "started": thread is not None,
            "alive": bool(thread and thread.is_alive()),
            "name": thread.name if thread is not None else None,
            "dispatched_runs": len(_RUN_DISPATCHED),
            "registered_task_types": registered_dispatch_types(),
        }


# Short aliases make the contract convenient for maintenance service agents
# while keeping the descriptive names above as the canonical documentation.
submit_operation = submit_durable_operation
register_durable_handler = register_operation_handler
OperationContext = OperationHandlerContext


__all__ = [
    "init", "create_batch", "create_task", "start_task", "append_event", "finish_task",
    "recover_interrupted", "list_tasks", "get_task", "register_task_dependency",
    "set_dependency_ready_handler", "notify_dependency_ready", "drain_ready_dependencies",
    "start_dependency_dispatcher", "stop_dependency_dispatcher", "dependency_dispatcher_status",
    "register_dispatch_handler", "unregister_dispatch_handler", "registered_dispatch_types",
    "reserve_dispatch", "release_dispatch", "dispatch_registered_once",
    "notify_dispatch", "normalize_config_snapshot", "OperationResult",
    "OperationLeaseUnavailable", "OperationLeaseLost", "OperationLease", "OperationResourceCleanupPending",
    "OperationSettlementPending", "OperationSettlementConflict", "OperationSettlementFenced",
    "SETTLEMENT_CONTROL_ERRORS",
    "OperationTaskReporter", "OperationHandlerContext", "OperationContext",
    "register_operation_handler", "unregister_operation_handler", "registered_operation_types",
    "register_operation_actions", "operation_action", "operation_requires_reconciliation", "operation_is_deactivated",
    "default_operation_retry", "default_operation_cancel", "default_operation_terminate",
    "list_reconciliation_accounts",
    "submit_durable_operation", "submit_operation", "register_durable_handler",
    "start_dispatcher", "stop_dispatcher", "dispatcher_status",
]
