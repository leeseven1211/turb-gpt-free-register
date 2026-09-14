"""账号任务统一提交、事件和持久调度边界。

兼容期仍由 ``legacy_task_store`` 写入旧账号任务；本模块负责把任务和
依赖交给 PostgreSQL 的统一运行时。进程内线程只负责轮询和提交，真正的
claim 以及父子推进都由存储层的原子状态转换决定。
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from core.operation_runtime import CancellationToken, OperationCancelled, operation_context


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
_OPERATION_HANDLERS: dict[str, Callable[[OperationHandlerContext], Any]] = {}
_OPERATION_ACTIONS: dict[str, dict[str, Callable[[Mapping[str, Any]], Any]]] = {}
_DISPATCH_HANDLER_LOCK = threading.RLock()
_RUN_DISPATCHED: set[int] = set()
_RUN_DISPATCH_LOCK = threading.RLock()
_RUN_DISPATCH_WAKE = threading.Event()
_RUN_DISPATCH_STOP = threading.Event()
_RUN_DISPATCH_THREAD: threading.Thread | None = None
_RUN_DISPATCH_INTERVAL_SECONDS = 0.5
_RUN_DISPATCH_BATCH_SIZE = 32


_MISSING = object()
_CONFIG_SECRET_PARTS = frozenset({"password", "secret", "token", "cookie", "otp", "authorization"})


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
            revision = payload.get("revision", payload.get("version"))
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
        lowered = f"{target} {source}".lower()
        if any(part in lowered.split("_") for part in _CONFIG_SECRET_PARTS):
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
    """Explicit handler result; ``request_unknown`` is never retried here."""

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
        message: str = "远端请求结果待确认",
        summary: Mapping[str, Any] | None = None,
    ) -> "OperationResult":
        values = dict(summary or {})
        values.update({"outcome": "request_unknown", "reconcile_required": True})
        return cls("request_unknown", values, message, message)

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


class OperationLeaseLost(RuntimeError):
    """The current worker lost its lease fence while remote work was possible."""


class OperationLease:
    """A DB-backed account/resource lease owned by one handler context."""

    def __init__(
        self,
        *,
        run_id: int,
        account_id: int,
        resource_family: str,
        token: str,
        ttl_seconds: int = 600,
    ) -> None:
        self.run_id = int(run_id)
        self.account_id = int(account_id)
        self.resource_family = str(resource_family)
        self.token = str(token)
        self.ttl_seconds = max(60, min(24 * 60 * 60, int(ttl_seconds or 600)))
        self._released = False
        self._heartbeat_lost = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_interval = max(0.5, min(30.0, self.ttl_seconds / 3.0))
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"operation-lease-{self.run_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    @property
    def released(self) -> bool:
        return self._released

    @property
    def lost(self) -> bool:
        return self._heartbeat_lost

    def heartbeat(self, *, ttl_seconds: int = 600) -> bool:
        if self._released:
            return False
        effective_ttl = max(60, min(24 * 60 * 60, int(ttl_seconds or self.ttl_seconds)))
        alive = bool(
            _operation().heartbeat_run(
                self.run_id, self.token, ttl_seconds=effective_ttl,
            )
        )
        if not alive:
            self._heartbeat_lost = True
        return alive

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval):
            if self._released or not self.heartbeat(ttl_seconds=self.ttl_seconds):
                return

    def release(self) -> bool:
        if self._released:
            return False
        self._released = True
        self._heartbeat_stop.set()
        if (
            self._heartbeat_thread is not threading.current_thread()
            and self._heartbeat_thread.is_alive()
        ):
            self._heartbeat_thread.join(timeout=min(1.0, self._heartbeat_interval))
        return bool(_operation().release_account_lease(self.run_id, self.token))

    def __enter__(self) -> "OperationLease":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


class OperationTaskReporter:
    """Structured progress reporter bound to one claimed Run."""

    def __init__(self, run_id: int) -> None:
        self.run_id = int(run_id)

    def report(self, **event: Any) -> dict:
        return _operation().append_runtime_event(self.run_id, **event)

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
            checker=_operation().is_run_cancel_requested,
        )
        self._lease: OperationLease | None = None
        self._finished = False
        self._last_result: OperationResult | None = None

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def cancellation(self) -> CancellationToken:
        return self._token

    def report(self, **event: Any) -> dict:
        return self.task_reporter.report(**event)

    def checkpoint(self, message: str = "任务收到取消请求") -> None:
        if self._lease is not None and not self._lease.released:
            if not self._lease.heartbeat():
                raise OperationLeaseLost("账号 lease 心跳失败，远端结果必须重新核验")
        self._token.checkpoint(message)

    def is_cancel_requested(self, *, force: bool = False) -> bool:
        return self._token.requested(force=force)

    def acquire_lease(
        self,
        *,
        resource_family: str | None = None,
        ttl_seconds: int = 600,
    ) -> OperationLease:
        if self.account_id is None:
            raise ValueError("无 account_id 的操作不能申请账号 lease")
        family = str(resource_family or self.resource_family)
        token = _operation().acquire_account_lease(
            account_id=self.account_id,
            run_id=self.run_id,
            resource_family=family,
            ttl_seconds=ttl_seconds,
        )
        if not token:
            raise OperationLeaseUnavailable(
                f"账号 lease 不可用：account_id={self.account_id} resource_family={family}"
            )
        lease = OperationLease(
            run_id=self.run_id, account_id=self.account_id,
            resource_family=family, token=token,
            ttl_seconds=ttl_seconds,
        )
        self._lease = lease
        return lease

    @contextmanager
    def lease(self, *, resource_family: str | None = None, ttl_seconds: int = 600) -> Iterator[OperationLease]:
        lease = self.acquire_lease(resource_family=resource_family, ttl_seconds=ttl_seconds)
        try:
            yield lease
        finally:
            lease.release()
            if self._lease is lease:
                self._lease = None

    def release_lease(self) -> bool:
        if self._lease is None:
            return False
        lease = self._lease
        self._lease = None
        return lease.release()

    def register_resource(self, **kwargs: Any) -> dict:
        return _operation().register_resource(self.run_id, **kwargs)

    def release_resource(self, resource_id: int, **kwargs: Any) -> bool:
        return bool(_operation().release_resource(int(resource_id), **kwargs))

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
        return _operation().record_remote_intent(
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
        return _operation().record_remote_receipt(
            self.run_id,
            execution_id=self.execution_id,
            lease_token=self._lease.token if self._lease and not self._lease.released else None,
            outcome=str(outcome or "unknown"),
            receipt_state=receipt_state,
            action=action,
            request_id=request_id,
            detail=dict(detail or {}),
        )

    def finish(
        self,
        result: OperationResult | Mapping[str, Any] | None = None,
        *,
        status: str | None = None,
        message: str = "",
        result_summary: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> dict:
        normalized = _coerce_operation_result(
            result, status=status, message=message,
            result_summary=result_summary, error=error,
        )
        self._last_result = normalized
        db_status = "attention_required" if normalized.status == "request_unknown" else normalized.status
        summary = dict(normalized.summary)
        summary.setdefault("execution_id", self.execution_id)
        summary.setdefault(
            "lease_owner",
            self.execution_id if self._lease is not None and not self._lease.released else "released",
        )
        if normalized.status == "request_unknown":
            summary.setdefault("outcome", "request_unknown")
            summary.setdefault("reconcile_required", True)
        row = _operation().finish_run(
            self.run_id,
            status=db_status,
            message=normalized.message,
            result_summary=summary,
            error=normalized.error,
            execution_id=self.execution_id,
            lease_token=(
                self._lease.token
                if self._lease is not None and not self._lease.released else None
            ),
        )
        self._finished = True
        return row

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
            return OperationResult.request_unknown(result_message or "远端请求结果待确认", dict(summary))
        return OperationResult(result_status or "failed", dict(summary), result_message, result_error)
    result_status = str(status or "").strip().lower()
    if not result_status:
        raise ValueError("handler 必须返回 OperationResult 或显式 status")
    if result_status in {"unknown", "request_unknown"}:
        return OperationResult.request_unknown(message or "远端请求结果待确认", result_summary)
    return OperationResult(result_status, dict(result_summary or {}), message, error)


def _legacy():
    from core.operations import legacy_task_store

    return legacy_task_store


def _operation():
    from core.storage import operation

    return operation


def _executor():
    from core.account_operation_executor import executor

    return executor


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
) -> None:
    """Register the reusable context-based durable handler contract.

    The handler is submitted to the process-wide ``AccountOperationExecutor``
    by the existing dispatcher. It receives a context only after the worker
    atomically claims the Run; it must perform business writeback and then
    return or call ``context.finish`` with an explicit result.
    """
    name = str(task_type or "").strip()
    if not name:
        raise ValueError("task_type 不能为空")
    if not callable(handler):
        raise TypeError("operation handler 必须可调用")
    with _DISPATCH_HANDLER_LOCK:
        _OPERATION_HANDLERS[name] = handler
        if config_allowlist is not None:
            _OPERATION_HANDLER_ALLOWLISTS[name] = config_allowlist

    def invoke(run_id: int, *, _task_type: str = name) -> Any:
        return _execute_operation_handler(_task_type, run_id)

    register_dispatch_handler(name, invoke, source_systems=source_systems)
    if retry_handler is not None or cancel_handler is not None:
        register_operation_actions(
            name, retry_handler=retry_handler, cancel_handler=cancel_handler,
        )


def unregister_operation_handler(task_type: str) -> None:
    name = str(task_type or "").strip()
    with _DISPATCH_HANDLER_LOCK:
        _OPERATION_HANDLERS.pop(name, None)
        _OPERATION_HANDLER_ALLOWLISTS.pop(name, None)
        _OPERATION_ACTIONS.pop(name, None)
    unregister_dispatch_handler(name)


def register_operation_actions(
    task_type: str,
    *,
    retry_handler: Callable[[Mapping[str, Any]], Any] | None = None,
    cancel_handler: Callable[[Mapping[str, Any]], Any] | None = None,
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
    if retry_handler is None and cancel_handler is None:
        return
    with _DISPATCH_HANDLER_LOCK:
        actions = dict(_OPERATION_ACTIONS.get(name) or {})
        if retry_handler is not None:
            actions["retry"] = retry_handler
        if cancel_handler is not None:
            actions["cancel"] = cancel_handler
        _OPERATION_ACTIONS[name] = actions


def operation_action(
    task_type: str,
    action: str,
) -> Callable[[Mapping[str, Any]], Any] | None:
    with _DISPATCH_HANDLER_LOCK:
        return (_OPERATION_ACTIONS.get(str(task_type or "").strip()) or {}).get(
            str(action or "").strip().lower()
        )


def operation_requires_reconciliation(task: Mapping[str, Any] | None) -> bool:
    """Whether a task's current result forbids a blind retry."""
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


def submit_durable_operation(
    *,
    task_type: str,
    account_id: int | None,
    email: str,
    trigger: str = "manual",
    source_system: str = "native_operations",
    source_id: str | None = None,
    idempotency_key: str | None = None,
    parent_task_id: int | None = None,
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    resource_family: str = "openai_interactive",
    data: Mapping[str, Any] | None = None,
    config_snapshot: Any | None = None,
    config_snapshot_provider: Callable[[], Any] | None = None,
    config_allowlist: Iterable[str] | Mapping[str, str] | None = None,
    dispatch: bool = True,
) -> dict[str, Any]:
    """Persist one task/run and optionally wake the shared durable scanner.

    ``source_system`` + ``source_id`` (or ``idempotency_key``) is the
    migration mapping. Config is captured once at submission and only the
    explicit allowlist is stored; no service-specific config is read here.
    """
    name = str(task_type or "").strip()
    if not name:
        return {"accepted": False, "error": "task_type 为空"}
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
        )
    except Exception as exc:
        if "uq_operation_runs_active_account_family" in str(exc) or "duplicate key" in str(exc).lower():
            active = _operation().active_run_for_account(
                int(account_id), str(resource_family or "openai_interactive"),
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
    run = created.get("run") if isinstance(created.get("run"), Mapping) else {}
    run_id = int(run.get("id") or 0) or None
    task_id = int(created.get("id") or 0) or None
    status = str(run.get("status") or created.get("status") or "queued")
    reused = bool(created.get("idempotent"))
    result: dict[str, Any] = {
        "accepted": True,
        # ``busy`` is a rejection/conflict signal for compatibility callers;
        # a newly accepted durable queue item is not a busy result.
        "busy": bool(reused and status in {"queued", "running", "cancelling", "settling", "waiting"}),
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
    payload = result.as_dict()
    payload.update({
        "task_id": context.task_id,
        "run_id": context.run_id,
        "source_system": context.source_system,
        "database_status": database_status or (
            "attention_required" if result.status == "request_unknown" else result.status
        ),
    })
    return payload


def _execute_operation_handler(task_type: str, run_id: int) -> dict[str, Any]:
    """Claim and run one context handler inside the shared executor budget."""
    with _DISPATCH_HANDLER_LOCK:
        handler = _OPERATION_HANDLERS.get(str(task_type))
    if handler is None:
        return {"status": "not_registered", "run_id": int(run_id)}
    execution_id = uuid.uuid4().hex
    claimed = _operation().claim_run(
        int(run_id), execution_id=execution_id, worker_pid=os.getpid(),
    )
    if not claimed:
        return {"status": "not_claimed", "run_id": int(run_id)}
    context = OperationHandlerContext(claimed, execution_id=execution_id)
    try:
        with operation_context(context.cancellation, reporter=context.report):
            context.checkpoint()
            returned = handler(context)
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
    except OperationLeaseUnavailable as exc:
        if context.is_cancel_requested(force=True):
            result = OperationResult.cancelled("任务在取得账号 lease 前收到取消请求")
            if not context.finished:
                context.finish(result)
            return _operation_handler_result_payload(context, result)
        requeued = _operation().requeue_claimed_run(
            context.run_id,
            execution_id=execution_id,
            reason=str(exc),
            delay_seconds=1.0,
        )
        if requeued:
            notify_dispatch()
        return {
            "status": "deferred" if requeued else "not_claimed",
            "run_id": context.run_id,
            "task_id": context.task_id,
            "reason": str(exc),
        }
    except OperationLeaseLost as exc:
        # A lost lease can mean that a remote write was accepted. Never
        # requeue this run; preserve the attempt for reconciliation instead.
        context.release_lease()
        result = OperationResult.request_unknown(
            "账号 lease 心跳失败，远端结果待核验",
            {"lease_lost": True, "error": str(exc), "execution_id": execution_id},
        )
        try:
            if not context.finished:
                context.finish(result)
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
        result = OperationResult.cancelled(str(exc) or "任务已在安全检查点取消")
        if not context.finished:
            context.finish(result)
        return _operation_handler_result_payload(context, result)
    except PermissionError as exc:
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
        logger.exception("durable operation handler 执行失败：task_type=%s run_id=%s", task_type, run_id)
        result = OperationResult.failed(f"{type(exc).__name__}: {exc}")
        if not context.finished:
            context.finish(result)
        return _operation_handler_result_payload(context, result)
    finally:
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


def recover_interrupted() -> int:
    return _legacy().recover_interrupted()


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
    handler = _dependency_handler()
    if handler is None:
        return 0
    # Do not claim a large ready backlog while the shared account-operation
    # budget is already full. The callback still rechecks the budget because
    # another producer can win the race between this snapshot and submit.
    slots = _executor().available_slots()
    if slots <= 0:
        return 0
    claimed_count = 0
    try:
        candidates = _operation().list_ready_task_dependencies(
            limit=min(_DEPENDENCY_BATCH_SIZE, slots),
            initialize=False,
        )
        for candidate in candidates:
            # This is the only claim site in the process. A second process can
            # race safely because the SQL update is a ready->running CAS.
            claimed = _operation().claim_task_dependency(
                int(candidate.get("id") or 0), initialize=False,
            )
            if not claimed:
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
                    _operation().complete_task_dependency(
                        int(claimed["id"]),
                        success=False,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    notify_dependency_ready(claimed)
                except Exception:
                    logger.exception(
                        "父任务依赖失败状态写回失败：dependency_id=%s", claimed.get("id"),
                    )
    except Exception:
        logger.exception("持久父任务依赖 dispatcher 轮询失败")
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
            return False
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
    if not callable(handler):
        raise TypeError("task handler 必须可调用")
    allowed_sources = None if source_systems is None else tuple(
        str(item).strip() for item in source_systems if str(item).strip()
    )
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS[name] = (handler, allowed_sources)
    _RUN_DISPATCH_WAKE.set()


def unregister_dispatch_handler(task_type: str) -> None:
    with _DISPATCH_HANDLER_LOCK:
        _DISPATCH_HANDLERS.pop(str(task_type or "").strip(), None)
        _OPERATION_HANDLERS.pop(str(task_type or "").strip(), None)
        _OPERATION_HANDLER_ALLOWLISTS.pop(str(task_type or "").strip(), None)
        _OPERATION_ACTIONS.pop(str(task_type or "").strip(), None)


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


def _run_handler_snapshot() -> dict[str, tuple[Callable[[int], Any], tuple[str, ...] | None]]:
    with _DISPATCH_HANDLER_LOCK:
        return dict(_DISPATCH_HANDLERS)


def dispatch_registered_once(*, limit: int | None = None) -> int:
    """Submit a finite batch of registered durable runs through the budget."""
    handlers = _run_handler_snapshot()
    if not handlers:
        return 0
    slots = _executor().available_slots()
    if slots <= 0:
        return 0
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
    scan_limit = max(slots, min(5000, requested_limit))
    try:
        runs = _operation().list_dispatchable_runs(
            limit=scan_limit,
            task_types=tuple(handlers),
            source_systems=None if accepts_all_sources else tuple(sorted(source_systems)),
        )
    except (AttributeError, TypeError):
        # Compatibility with an older storage wrapper during a rolling update.
        try:
            runs = _operation().list_queued_runs(limit=scan_limit)
        except AttributeError:
            runs = []
    submitted = 0
    for run in runs:
        if submitted >= slots:
            break
        task_type = str(run.get("task_type") or "")
        entry = handlers.get(task_type)
        if entry is None:
            continue
        handler, allowed_sources = entry
        source_system = str(run.get("source_system") or "")
        if allowed_sources is not None and source_system not in allowed_sources:
            continue
        if not reserve_dispatch(int(run["id"])):
            continue
        try:
            future = _executor().try_submit(handler, int(run["id"]))
        except Exception:
            release_dispatch(int(run["id"]))
            logger.exception("提交 durable operation 失败：run_id=%s", run.get("id"))
            continue
        if future is None:
            release_dispatch(int(run["id"]))
            break
        submitted += 1
        try:
            future.add_done_callback(
                lambda _completed, run_id=int(run["id"]): release_dispatch(run_id)
            )
        except AttributeError:
            release_dispatch(int(run["id"]))
    return submitted


def notify_dispatch() -> None:
    """Wake the durable task dispatcher after a new run is persisted."""
    _RUN_DISPATCH_WAKE.set()


def _run_dispatch_loop() -> None:
    while not _RUN_DISPATCH_STOP.is_set():
        submitted = dispatch_registered_once()
        if submitted:
            continue
        _RUN_DISPATCH_WAKE.wait(_RUN_DISPATCH_INTERVAL_SECONDS)
        _RUN_DISPATCH_WAKE.clear()


def start_dispatcher(*, interval_seconds: float = 0.5, batch_size: int = 32) -> bool:
    """Start the shared task-type dispatcher for durable operation runs."""
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
            return False
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
    "OperationLeaseUnavailable", "OperationLeaseLost", "OperationLease",
    "OperationTaskReporter", "OperationHandlerContext", "OperationContext",
    "register_operation_handler", "unregister_operation_handler", "registered_operation_types",
    "register_operation_actions", "operation_action", "operation_requires_reconciliation",
    "submit_durable_operation", "submit_operation", "register_durable_handler",
    "start_dispatcher", "stop_dispatcher", "dispatcher_status",
]
