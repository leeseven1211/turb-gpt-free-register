# -*- coding: utf-8 -*-
"""Codex OAuth 唯一调度入口。

Web、注册恢复、批量操作和 CLI 都只创建 operation task/run；执行阶段通过数据库
认领、账号租约和取消令牌协调，不再向 Python 线程异步注入异常。
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from concurrent.futures import Future
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Iterable

from core.storage import accounts as db
from core.storage import operation_runtime_store as operation_task_store
from core import task_run_log
from core.operations import task_gateway
from core.operation_runtime import CancellationToken, OperationCancelled, operation_context
from core.account_operation_executor import configured_workers
from core.account_operation_executor import executor as _EXECUTOR

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
_LOCAL_TOKENS: dict[int, CancellationToken] = {}
_LOCAL_TOKENS_LOCK = threading.RLock()
_DISPATCHED_RUNS: set[int] = set()
_DISPATCH_LOCK = threading.RLock()
_CONFIG_SNAPSHOT_PROVIDER: Callable[..., Any] | None = None
_CONFIG_PROVIDER_LOCK = threading.RLock()

# C's schema snapshot is intentionally broad because it is also consumed by
# the configuration UI.  A Codex operation must capture only the choices that
# its execution boundary can use.  Keep the translation here so the task
# payload remains stable while C evolves its schema names.
_SNAPSHOT_MISSING = object()
_SNAPSHOT_REVISION_KEY = "config_snapshot_revision"
_ACCOUNT_PROXY_MODE_KEYS = {
    "password": ("ACCOUNT_PASSWORD_PROXY_MODE", "password_proxy_mode"),
    "twofa": ("ACCOUNT_2FA_PROXY_MODE", "twofa_proxy_mode"),
    "plan_check": ("ACCOUNT_PLAN_CHECK_PROXY_MODE", "plan_check_proxy_mode"),
    "live_check": ("ACCOUNT_LIVE_CHECK_PROXY_MODE", "live_check_proxy_mode"),
    "refresh_at": ("ACCOUNT_REFRESH_AT_PROXY_MODE", "refresh_at_proxy_mode"),
    "codex": ("ACCOUNT_CODEX_PROXY_MODE", "codex_proxy_mode"),
}


def log_path(email: str) -> Path:
    safe = str(email or "").replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"codex-retry-{safe}.log"


def _executor():
    """Compatibility accessor for the shared account-operation executor."""
    return _EXECUTOR


def _feature_ready() -> tuple[bool, str]:
    from core.feature_availability import require_feature

    return require_feature("codex_retry")


def set_config_snapshot_provider(provider: Callable[..., Any] | None) -> None:
    """Install C's immutable non-sensitive snapshot provider at the boundary.

    The provider is intentionally dependency-injected: this service does not
    define configuration fields or persist secrets.  It may accept the
    ``driver_override`` keyword and return either a values mapping or
    ``ConfigSnapshot`` (or a compatible mapping) is preferred. The current
    config reader remains a compatibility fallback until C's schema module is
    present in this checkout.
    """
    global _CONFIG_SNAPSHOT_PROVIDER
    with _CONFIG_PROVIDER_LOCK:
        _CONFIG_SNAPSHOT_PROVIDER = provider


def _legacy_config_snapshot(driver_override: str | None = None) -> dict:
    """Compatibility reader for deployments before C's provider is installed."""
    from config import codex as cfg
    from config import account as account_cfg
    from config import proxy as proxy_cfg
    from config import roxybrowser as roxy_cfg

    driver = str(
        driver_override if driver_override is not None
        else getattr(cfg, "CODEX_OAUTH_DRIVER", "protocol")
    ).strip().lower()
    if driver == "same_as_registration":
        driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    return {
        "oauth_driver": driver,
        "auth_source": str(getattr(cfg, "CODEX_AUTH_URL_SOURCE", "cpa") or "cpa").strip().lower(),
        "sms_provider": str(getattr(cfg, "SMS_PROVIDER", "grizzly") or "grizzly").strip().lower(),
        "sms_country": str(getattr(cfg, "SMS_COUNTRY", "") or ""),
        "account_proxy_mode": str(
            getattr(account_cfg, "ACCOUNT_CODEX_PROXY_MODE", None)
            or getattr(proxy_cfg, "ACCOUNT_ACTION_PROXY_MODE", "registration")
            or "registration"
        ),
        "account_proxy_modes": {
            "password": str(getattr(account_cfg, "ACCOUNT_PASSWORD_PROXY_MODE", "registration") or "registration"),
            "twofa": str(getattr(account_cfg, "ACCOUNT_2FA_PROXY_MODE", "registration") or "registration"),
            "plan_check": str(getattr(account_cfg, "ACCOUNT_PLAN_CHECK_PROXY_MODE", "direct") or "direct"),
            "live_check": str(getattr(account_cfg, "ACCOUNT_LIVE_CHECK_PROXY_MODE", "direct") or "direct"),
            "refresh_at": str(getattr(account_cfg, "ACCOUNT_REFRESH_AT_PROXY_MODE", "registration") or "registration"),
            "codex": str(getattr(account_cfg, "ACCOUNT_CODEX_PROXY_MODE", "registration") or "registration"),
        },
    }


def _snapshot_payload(raw: Any) -> tuple[dict, object | None]:
    """Normalize C's immutable ConfigSnapshot without retaining its object.

    C's ``as_dict`` deliberately returns the thawed values only, so read the
    revision before calling it.  The recursive thaw also handles a compatible
    provider that exposes nested ``MappingProxyType`` values; ``deepcopy``
    cannot copy those proxies directly.
    """
    revision = getattr(raw, "revision", _SNAPSHOT_MISSING)
    if isinstance(raw, Mapping):
        payload = _thaw_snapshot_value(raw)
        revision = payload.get("revision", revision)
        if revision is _SNAPSHOT_MISSING or revision is None:
            # Test/rolling providers from before C's revision contract may
            # still publish one of these envelope names.  Do not use these
            # aliases for the real ConfigSnapshot object.
            revision = payload.get("version")
            if revision is None:
                revision = payload.get("config_version")
        values = payload.get("values")
        if values is None:
            values = payload.get("snapshot")
        values = values if isinstance(values, Mapping) else payload
    else:
        as_dict = getattr(raw, "as_dict", None)
        values = as_dict() if callable(as_dict) else getattr(raw, "values", None)
    if not isinstance(values, Mapping):
        raise TypeError("配置 snapshot 必须提供 Mapping values")
    return _thaw_snapshot_value(values), (
        None if revision is _SNAPSHOT_MISSING else revision
    )


def _thaw_snapshot_value(value: Any) -> Any:
    """Copy ordinary snapshot containers without copying mapping proxies."""
    if isinstance(value, Mapping):
        return {key: _thaw_snapshot_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_snapshot_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return {_thaw_snapshot_value(item) for item in value}
    return value


def _snapshot_value(values: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in values:
            return values[key]
    return default


def _snapshot_text(value: Any, default: str, *, lower: bool = False) -> str:
    text = str(value if value is not None else default).strip()
    return text.lower() if lower else text


def _registration_driver_for_snapshot(values: Mapping[str, Any]) -> str:
    configured = _snapshot_value(
        values,
        "REGISTRATION_DRIVER",
        "registration_driver",
        default=None,
    )
    if configured is None or not str(configured).strip():
        # This fallback is only for old injected/partial providers.  The real
        # C snapshot contains REGISTRATION_DRIVER and is resolved without
        # consulting mutable module globals.
        try:
            from config import roxybrowser as roxy_cfg

            configured = getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol")
        except (ImportError, AttributeError):
            configured = "protocol"
    return _snapshot_text(configured, "protocol", lower=True)


def _project_config_snapshot(
    values: Mapping[str, Any],
    revision: object | None,
    *,
    driver_override: str | None = None,
) -> dict[str, Any]:
    """Project C's uppercase schema values into the execution snapshot.

    The returned mapping is the only representation persisted in an
    operation task.  In particular, it intentionally excludes C's ``sources``
    and every unrelated non-sensitive schema field.
    """
    override = driver_override
    configured_driver = _snapshot_value(
        values,
        "CODEX_OAUTH_DRIVER",
        "oauth_driver",
        default="protocol",
    )
    driver = _snapshot_text(
        configured_driver if override is None else override,
        "protocol",
        lower=True,
    )
    if driver == "same_as_registration":
        driver = _registration_driver_for_snapshot(values)

    action_proxy = _snapshot_value(
        values,
        "ACCOUNT_ACTION_PROXY_MODE",
        "account_proxy_mode",
        default="registration",
    )
    codex_proxy = _snapshot_value(
        values,
        "ACCOUNT_CODEX_PROXY_MODE",
        "codex_proxy_mode",
        default=None,
    )
    effective_codex_proxy = codex_proxy
    # C publishes both the newer purpose-specific key and the historical
    # ACCOUNT_ACTION_PROXY_MODE key.  If the newer value is still its default
    # and the legacy value is explicitly non-default, retain the old env
    # compatibility behavior; a purpose-specific non-default always wins.
    if (
        effective_codex_proxy is None
        or (
            str(effective_codex_proxy).strip().lower() in {"", "registration"}
            and str(action_proxy or "").strip().lower() not in {"", "registration"}
        )
    ):
        effective_codex_proxy = action_proxy
    modes: dict[str, str] = {}
    nested_modes = _snapshot_value(values, "account_proxy_modes", default=None)
    if isinstance(nested_modes, Mapping):
        nested_modes = _thaw_snapshot_value(nested_modes)
    else:
        nested_modes = {}
    for name, keys in _ACCOUNT_PROXY_MODE_KEYS.items():
        value = _snapshot_value(values, *keys, default=None)
        if value is None:
            value = _snapshot_value(nested_modes, name, default=None)
        if value is None and name == "codex":
            value = effective_codex_proxy
        if value is None:
            value = "direct" if name in {"plan_check", "live_check"} else "registration"
        modes[name] = str(value or ("direct" if name in {"plan_check", "live_check"} else "registration"))

    output: dict[str, Any] = {
        "oauth_driver": driver,
        "auth_source": _snapshot_text(
            _snapshot_value(values, "CODEX_AUTH_URL_SOURCE", "auth_source", default="cpa"),
            "cpa",
            lower=True,
        ),
        "sms_provider": _snapshot_text(
            _snapshot_value(values, "SMS_PROVIDER", "sms_provider", default="grizzly"),
            "grizzly",
            lower=True,
        ),
        "sms_country": str(
            _snapshot_value(values, "SMS_COUNTRY", "sms_country", default="") or ""
        ),
        "account_proxy_mode": str(effective_codex_proxy or action_proxy or "registration"),
        "account_proxy_modes": modes,
    }
    if revision is not None:
        output[_SNAPSHOT_REVISION_KEY] = revision
    return output


def _schema_config_snapshot(driver_override: str | None = None) -> dict | None:
    """Read the pluggable, atomic non-sensitive snapshot supplied by C."""
    try:
        from config import schema
    except ImportError:
        return None
    provider = getattr(schema, "non_sensitive_snapshot", None)
    if provider is None:
        return None
    values, revision = _snapshot_payload(provider())
    return _project_config_snapshot(values, revision, driver_override=driver_override)


def _config_snapshot(driver_override: str | None = None) -> dict:
    """Return a copied, revision-carrying non-sensitive execution snapshot."""
    with _CONFIG_PROVIDER_LOCK:
        provider = _CONFIG_SNAPSHOT_PROVIDER
    if provider is None:
        schema_snapshot = _schema_config_snapshot(driver_override)
        return schema_snapshot if schema_snapshot is not None else _legacy_config_snapshot(driver_override)
    try:
        raw = provider(driver_override=driver_override)
    except TypeError:
        raw = provider()
    values, revision = _snapshot_payload(raw)
    return _project_config_snapshot(values, revision, driver_override=driver_override)


def _append_log(email: str, message: str, *, clear: bool = False) -> None:
    path = log_path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if clear else "a"
    with path.open(mode, encoding="utf-8") as handle:
        handle.write(str(message).rstrip() + "\n")


def _forget_dispatched(run_id: int) -> None:
    with _DISPATCH_LOCK:
        _DISPATCHED_RUNS.discard(int(run_id))
    task_gateway.release_dispatch(int(run_id))


def _dispatch(run_id: int) -> bool:
    """Submit one durable run once per process; DB claim remains authoritative."""
    run_id = int(run_id)
    if not task_gateway.reserve_dispatch(run_id):
        return False
    with _DISPATCH_LOCK:
        if run_id in _DISPATCHED_RUNS:
            task_gateway.release_dispatch(run_id)
            return False
        _DISPATCHED_RUNS.add(run_id)
    try:
        future = _EXECUTOR.submit(_execute_run, run_id)
    except Exception:
        _forget_dispatched(run_id)
        raise
    # Real Futures release the process-local de-duplication marker when the
    # work ends.  A mocked/compatible submit result is not allowed to poison a
    # later test or caller forever.
    if isinstance(future, Future):
        future.add_done_callback(lambda _completed: _forget_dispatched(run_id))
    else:
        _forget_dispatched(run_id)
    return True


def _dispatch_bulk(run_ids: list[int], workers: int | None = None) -> None:
    """Submit every run to the common account-operation pool.

    ``workers`` remains accepted for compatibility with older callers, but
    ACCOUNT_BATCH_WORKERS is authoritative.
    """
    for run_id in run_ids:
        _dispatch(int(run_id))


def _dispatch_queued_once(*, scan_limit: int | None = None) -> int:
    """Seed the gateway's registered task-type dispatcher once."""
    return task_gateway.dispatch_registered_once(limit=scan_limit)


def start_dispatcher() -> bool:
    """Register Codex and start the shared task-type dispatcher."""
    task_gateway.register_dispatch_handler("codex_retry", _execute_run)
    return task_gateway.start_dispatcher()


def stop_dispatcher(*, timeout: float = 2.0) -> bool:
    return task_gateway.stop_dispatcher(timeout=timeout)


def dispatcher_status() -> dict[str, object]:
    return task_gateway.dispatcher_status()


def _duplicate_result(account_id: int) -> dict:
    active = operation_task_store.active_run_for_account(account_id)
    return {
        "accepted": False,
        "busy": True,
        "error": "该账号已有排队或运行中的账号操作",
        "task_id": int(active.get("task_id") or 0) or None if active else None,
        "run_id": int(active.get("id") or 0) or None if active else None,
        "status": str(active.get("status") or "") if active else "",
    }


def submit(
    email: str,
    *,
    trigger: str = "manual",
    parent_task_id: int | None = None,
    batch_id: int | None = None,
    batch_ordinal: int | None = None,
    dispatch: bool = True,
    driver: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """提交一个 Codex OAuth 逻辑任务和第一次 attempt。"""
    email = str(email or "").strip()
    if not email:
        return {"accepted": False, "error": "email 为空"}
    account = db.get_account_by_email(email)
    if not account:
        return {"accepted": False, "error": f"账号不存在: {email}"}
    account_id = int(account.get("id") or 0)
    if str(account.get("account_status") or "").lower() == "deactivated" or str(account.get("codex_status") or "").lower() == "deactivated":
        return {"accepted": False, "error": "账号已废号，不能补跑 Codex"}
    enabled, reason = _feature_ready()
    if not enabled:
        return {"accepted": False, "feature": "codex_retry", "error": reason, "unavailable": True}
    try:
        created = operation_task_store.create_runtime_task(
            task_type="codex_retry",
            account_id=account_id,
            email=email,
            trigger=trigger,
            parent_task_id=parent_task_id,
            batch_id=batch_id,
            batch_ordinal=batch_ordinal,
            data={"config_snapshot": _config_snapshot(driver_override=driver)},
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        # 活跃 run 的部分唯一索引是跨进程防重事实；不再依赖进程内 email set。
        if "uq_operation_runs_active_account_family" in str(exc) or "duplicate key" in str(exc).lower():
            return _duplicate_result(account_id)
        logger.exception("创建 Codex operation 失败：email=%s", email)
        return {"accepted": False, "error": f"创建任务失败：{type(exc).__name__}: {exc}"}
    if created.get("idempotent"):
        existing_run = created.get("run") if isinstance(created.get("run"), dict) else {}
        existing_status = str(existing_run.get("status") or created.get("status") or "queued")
        return {
            "accepted": True,
            "busy": existing_status in {"queued", "running", "cancelling", "settling", "waiting"},
            "reused": True,
            "task_id": int(created["id"]),
            "run_id": int(existing_run.get("id") or 0) or None,
            "account_id": account_id,
            "email": email,
            "status": existing_status,
            "trigger": str(trigger or "manual"),
        }
    run = created["run"]
    run_id = int(run["id"])
    db.update_account_codex_operation_state(
        email,
        execution_status="queued",
        active_run_id=run_id,
    )
    task_run_log.append(
        run.get("log_file"), level="INFO", message="Codex operation 已进入数据库队列",
        task_id=int(created["id"]), run_id=run_id, stage="queued", event_type="note.info",
    )
    if dispatch:
        _dispatch(run_id)
        task_gateway.notify_dispatch()
    return {
        "accepted": True,
        "busy": False,
        "task_id": int(created["id"]),
        "run_id": run_id,
        "account_id": account_id,
        "email": email,
        "status": "queued",
        "trigger": str(trigger or "manual"),
    }


def submit_bulk(
    account_ids: Iterable[int],
    *,
    trigger: str = "manual_bulk",
    title: str = "批量补跑 Codex OAuth",
    workers: int | None = None,
) -> dict:
    ids: list[int] = []
    for raw in account_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value not in ids:
            ids.append(value)
    if not ids:
        return {"accepted": False, "error": "没有可补跑的账号"}
    enabled, reason = _feature_ready()
    if not enabled:
        return {"accepted": False, "feature": "codex_retry", "error": reason, "unavailable": True}
    batch = operation_task_store.create_runtime_batch(
        batch_type="codex_retry",
        title=title,
        requested_count=len(ids),
        trigger=trigger,
    )
    started: list[dict] = []
    skipped: list[dict] = []
    for ordinal, account_id in enumerate(ids, 1):
        account = db.get_account(account_id)
        if not account:
            skipped.append({"id": account_id, "reason": "账号不存在"})
            continue
        email = str(account.get("email") or "").strip()
        queued = submit(
            email,
            trigger=trigger,
            batch_id=int(batch["id"]),
            batch_ordinal=ordinal,
            dispatch=False,
        )
        if queued.get("accepted"):
            started.append(queued)
        else:
            skipped.append({"id": account_id, "email": email, "reason": queued.get("error") or "无法入队"})
    operation_task_store.set_runtime_batch_skipped(int(batch["id"]), skipped)
    if not started:
        operation_task_store.mark_runtime_batch_empty(int(batch["id"]), status="failed")
    if started:
        _dispatch_bulk([int(item["run_id"]) for item in started])
    return {
        "accepted": bool(started),
        "batch_id": int(batch["id"]),
        "batch_uuid": batch.get("batch_uuid"),
        "started": started,
        "started_count": len(started),
        "workers": configured_workers(),
        "skipped": skipped,
    }


def retry_task(task_id: int, *, trigger: str = "manual_retry") -> dict:
    task = operation_task_store.get_task(int(task_id))
    if not task:
        return {"accepted": False, "error": "任务不存在"}
    if str(task.get("source_system") or "") != "native_operations":
        return {"accepted": False, "error": "该历史任务尚未迁移为原生运行任务"}
    account_id = int(task.get("account_id") or 0)
    if operation_task_store.active_run_for_account(account_id):
        return _duplicate_result(account_id)
    enabled, reason = _feature_ready()
    if not enabled:
        return {"accepted": False, "feature": "codex_retry", "error": reason, "unavailable": True}
    try:
        run = operation_task_store.retry_runtime_task(int(task_id), trigger=trigger, data={"config_snapshot": _config_snapshot()})
    except (LookupError, ValueError) as exc:
        return {"accepted": False, "error": str(exc)}
    email = str(task.get("email_snapshot") or "")
    run_id = int(run["id"])
    db.update_account_codex_operation_state(email, execution_status="queued", active_run_id=run_id)
    task_run_log.append(
        run.get("log_file"), level="INFO", message="Codex operation 作为新 Run 进入队列",
        task_id=int(task_id), run_id=run_id, stage="queued", event_type="retry.scheduled",
    )
    _dispatch(run_id)
    return {"accepted": True, "task_id": int(task_id), "run_id": run_id, "account_id": account_id, "email": email, "status": "queued"}


def request_cancel(*, run_id: int | None = None, email: str = "", account_id: int | None = None) -> dict:
    if run_id is None:
        if account_id is None and email:
            account = db.get_account_by_email(email) or {}
            account_id = int(account.get("id") or 0) or None
        if not account_id:
            return {"ok": False, "error": "未找到账号"}
        active = operation_task_store.active_run_for_account(int(account_id))
        if not active:
            return {"ok": True, "running": False, "state": "empty", "message": "没有排队或运行中的账号操作"}
        run_id = int(active["id"])
        email = str(active.get("email_snapshot") or email)
    try:
        run = operation_task_store.request_run_cancel(int(run_id), reason="用户手动停止 Codex 补跑")
    except LookupError as exc:
        return {"ok": False, "error": str(exc)}
    with _LOCAL_TOKENS_LOCK:
        token = _LOCAL_TOKENS.get(int(run_id))
        if token:
            token.request_local()
    if not email:
        current = operation_task_store.get_run(int(run_id)) or {}
        email = str(current.get("email_snapshot") or "")
    if email:
        terminal = str(run.get("status") or "") == "cancelled"
        db.update_account_codex_operation_state(
            email,
            execution_status="empty" if terminal else "cancelling",
            last_run_status="cancelled" if terminal else None,
            error="用户手动停止 Codex 补跑",
            active_run_id=0 if terminal else int(run_id),
        )
        task_run_log.append(
            run.get("log_file"), level="WARNING", message="已请求协作式取消",
            task_id=int(run.get("task_id") or 0) or None, run_id=int(run_id),
            stage="cancelling", event_type="run.cancel_requested",
        )
    return {
        "ok": True,
        "run_id": int(run_id),
        "running": str(run.get("status") or "") != "cancelled",
        "state": str(run.get("status") or "cancelling"),
        "message": "已记录停止请求，任务将在安全检查点收口",
    }


def is_retrying(email: str) -> bool:
    account = db.get_account_by_email(str(email or "")) or {}
    account_id = int(account.get("id") or 0)
    return bool(account_id and operation_task_store.active_run_for_account(account_id))


def resume_queued(*, limit: int | None = None) -> int:
    """启动 durable dispatcher and seed the queue without a 500-row ceiling."""
    start_dispatcher()
    submitted = _dispatch_queued_once(scan_limit=limit)
    task_gateway.notify_dispatch()
    return submitted


def _execute_run(run_id: int) -> dict:
    execution_id = uuid.uuid4().hex
    run = operation_task_store.claim_run(run_id, execution_id=execution_id, worker_pid=os.getpid())
    if not run:
        return {"status": "not_claimed", "run_id": run_id}
    current = operation_task_store.get_run(run_id) or run
    email = str(current.get("email_snapshot") or "")
    account_id = int(current.get("account_id") or 0)
    task_trigger = str(current.get("trigger") or "").strip()
    cancellation_token = str(current.get("cancellation_token") or "")
    token = CancellationToken(
        run_id=run_id,
        token=cancellation_token,
        checker=operation_task_store.is_run_cancel_requested,
    )
    lease_token = ""
    lease_guard: task_gateway.OperationLease | None = None
    remote_intent_started = False
    remote_receipt_state: str | None = None
    route = None
    route_resource_id: int | None = None
    result: dict = {"status": "failed", "ok": False, "message": "OAuth 未返回结果"}
    root_logger = logging.getLogger()
    file_handler: logging.Handler | None = None

    def report(**event):
        return operation_task_store.append_runtime_event(run_id, **event)

    def _finish_fenced(
        status: str,
        *,
        message: str = "",
        error: str | None = None,
        summary: Mapping[str, Any] | None = None,
    ) -> bool:
        values = dict(summary or {})
        values.setdefault("execution_id", execution_id)
        values.setdefault("lease_owner", execution_id)
        try:
            operation_task_store.finish_run(
                run_id,
                status=status,
                message=message,
                error=error,
                result_summary=values,
                execution_id=execution_id,
                lease_token=lease_token or None,
            )
        except PermissionError:
            logger.warning(
                "Codex operation 终态写入被 execution/lease fence 拒绝：run=%s",
                run_id,
            )
            return False
        return True

    with _LOCAL_TOKENS_LOCK:
        _LOCAL_TOKENS[run_id] = token
    try:
        worker_name = threading.current_thread().name
        file_handler = task_run_log.TaskRunLogHandler(
            str(current.get("log_file") or ""),
            task_id=int(current["task_id"]),
            run_id=run_id,
            stage="codex",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(lambda record: record.threadName == worker_name)
        root_logger.addHandler(file_handler)
        lease_token = operation_task_store.acquire_account_lease(account_id=account_id, run_id=run_id) or ""
        if not lease_token:
            raise RuntimeError("账号操作租约被另一执行占用")
        lease_guard = task_gateway.OperationLease(
            run_id=run_id,
            account_id=account_id,
            resource_family=str(current.get("resource_family") or "openai_interactive"),
            token=lease_token,
            ttl_seconds=600,
        )
        db.update_account_codex_operation_state(email, execution_status="running", active_run_id=run_id)
        with operation_context(token, reporter=report):
            report(stage="preflight", message="开始执行统一配置预检", state="running")
            enabled, reason = _feature_ready()
            if not enabled:
                raise RuntimeError(f"配置预检失败：{reason}")
            raw_data = current.get("data") if isinstance(current.get("data"), dict) else {}
            snapshot = dict(raw_data.get("config_snapshot") or {}) if isinstance(raw_data.get("config_snapshot"), dict) else _config_snapshot()
            report(stage="preflight", message="配置预检通过", state="success", detail={"config_snapshot": snapshot})
            token.checkpoint()

            driver = str(snapshot.get("oauth_driver") or "protocol")
            from core.account_proxy import acquire_account_proxy

            report(stage="network", message="正在申请账号 OAuth 网络线路", state="running")
            route = acquire_account_proxy(account_id=account_id, email=email, purpose="codex-oauth")
            public = route.public_dict()
            resource = operation_task_store.register_resource(
                run_id,
                resource_type="proxy_lease",
                provider=str(route.provider or ""),
                detail={
                    "proxy_mode": route.mode,
                    "proxy_region": route.region,
                    "network_route": public.get("network_route"),
                },
            )
            route_resource_id = int(resource["id"])
            report(
                stage="network", message="账号 OAuth 网络线路已就绪", state="success",
                detail={
                    "proxy_mode": route.mode,
                    "proxy_provider": route.provider,
                    "proxy_region": route.region,
                    "network_route": public.get("network_route"),
                },
            )

            report(stage="browser", message=f"启动 {driver} OAuth 驱动", state="running", detail={"oauth_driver": driver})
            from core.codex_oauth import run_codex_oauth

            remote_intent_started = True
            operation_task_store.record_remote_intent(
                run_id,
                execution_id=execution_id,
                lease_token=lease_token,
                action="codex_oauth",
                intent_kind="remote_write",
                request_id=f"codex-oauth:{run_id}",
                detail={"checkpoint": "oauth_request_dispatched", "driver": driver},
            )

            allow_password_reset = task_trigger == "manual_sub2api_repair"

            def _checkpoint_password_reset(value: str) -> None:
                if not db.update_account_login_password(email, value, source="password_reset"):
                    raise RuntimeError("密码重置提交后写入账号检查点失败")
                report(
                    stage="login_password",
                    message="邮箱重置新密码提交后已写入本地检查点，等待页面确认",
                    state="running",
                    detail={"saved": True, "checkpoint": "password_reset_submitted"},
                )

            result = run_codex_oauth(
                email,
                proxy=route.proxy_url if route is not None else None,
                force=True,
                driver_override=driver,
                allow_password_reset=allow_password_reset,
                on_password_reset_submitted=(_checkpoint_password_reset if allow_password_reset else None),
            )
            confirmed = bool(result.get("credential_confirmed"))
            callback_submitted = bool(result.get("callback_submitted"))
            if callback_submitted or result.get("remote_response_received"):
                remote_receipt_state = "response_received"
                operation_task_store.record_remote_receipt(
                    run_id,
                    execution_id=execution_id,
                    lease_token=lease_token,
                    outcome="response_received",
                    action="codex_oauth",
                    request_id=f"codex-oauth:{run_id}",
                    detail={"callback_submitted": callback_submitted},
                )
            elif result.get("remote_write_rejected"):
                remote_receipt_state = "rejected"
                operation_task_store.record_remote_receipt(
                    run_id,
                    execution_id=execution_id,
                    lease_token=lease_token,
                    outcome="rejected",
                    action="codex_oauth",
                    request_id=f"codex-oauth:{run_id}",
                    detail={"remote_write_rejected": True},
                )
            # callback 之后收到取消信号时不能简单宣称“已取消”：远端可能仍在落凭证。
            if callback_submitted and not confirmed and token.requested(force=True):
                result["status"] = "attention_required"
                result["message"] = "停止请求发生在 callback 提交后；远端凭证状态待确认"
            elif not confirmed:
                token.checkpoint()

            account = db.get_account_by_email(email) or {}
            existing_valid = (
                str(account.get("codex_credential_state") or "").lower() == "valid"
                or str(account.get("codex_status") or "").lower() == "success"
            )
            if confirmed and result.get("ok"):
                final_status = "success"
                credential_state = "valid"
                final_error = None
                report(stage="credential_confirm", message="真实 Codex 凭证已确认", state="success")
            elif str(result.get("status") or "") == "attention_required" or callback_submitted:
                final_status = "attention_required"
                credential_state = "valid" if existing_valid else "pending_confirmation"
                final_error = str(result.get("message") or "远端凭证待确认")
            elif str(result.get("status") or "") == "deactivated":
                final_status = "deactivated"
                credential_state = "deactivated"
                final_error = str(result.get("message") or "账号已停用")
            else:
                final_status = "failed"
                credential_state = "valid" if existing_valid else None
                final_error = str(result.get("message") or "Codex OAuth 失败")
            run_summary = {
                "ok": final_status == "success",
                "status": final_status,
                "message": result.get("message"),
                "credential_confirmed": confirmed,
                "callback_submitted": callback_submitted,
                "credential_file": Path(str(result.get("file_path") or "")).name or None,
                "receipt_file": Path(str(result.get("receipt_path") or "")).name or None,
                "oauth_driver": driver,
                "execution_id": execution_id,
                "lease_owner": execution_id,
            }
            if lease_guard is not None and lease_guard.lost:
                raise task_gateway.OperationLeaseLost(
                    "Codex OAuth 执行期间账号 lease 心跳丢失"
                )
            if remote_intent_started and remote_receipt_state != "rejected":
                if (
                    final_status == "success"
                    and confirmed
                    and lease_guard is not None
                    and not lease_guard.lost
                ):
                    # The account-state write below is the durable business
                    # commit. The readback immediately after it is part of
                    # the confirmed receipt proof.
                    pass
                else:
                    final_status = "attention_required"
                    credential_state = "valid" if existing_valid else "pending_confirmation"
                    final_error = final_error or "远端 OAuth 结果待确认"
                    run_summary.update({
                        "outcome": "request_unknown",
                        "reconcile_required": True,
                        "remote_receipt_state": remote_receipt_state or "started",
                    })
            # Persist the business outcome before publishing the child Run's
            # terminal/dependency-ready state. A continuation must not race
            # the account row and conclude from a stale credential state.
            account_writeback_confirmed = db.update_account_codex_operation_state(
                email,
                credential_state=credential_state,
                execution_status="empty",
                last_run_status=final_status,
                error=final_error,
                active_run_id=0,
            )
            account_after = db.get_account_by_email(email) or {}
            local_readback_confirmed = (
                final_status == "success"
                and str(account_after.get("codex_credential_state") or "").lower() == "valid"
            )
            if final_status == "success" and not (
                account_writeback_confirmed and local_readback_confirmed
            ):
                final_status = "attention_required"
                credential_state = "valid" if existing_valid else "pending_confirmation"
                final_error = "Codex 凭证本地写回或 readback 未确认"
                run_summary.update({
                    "status": final_status,
                    "ok": False,
                    "outcome": "request_unknown",
                    "reconcile_required": True,
                    "remote_receipt_state": remote_receipt_state or "started",
                })
                db.update_account_codex_operation_state(
                    email,
                    credential_state=credential_state,
                    execution_status="empty",
                    last_run_status=final_status,
                    error=final_error,
                    active_run_id=0,
                )
            run_summary.update({
                "status": final_status,
                "ok": final_status == "success",
            })
            if final_status == "success":
                remote_receipt_state = "confirmed"
                operation_task_store.record_remote_receipt(
                    run_id,
                    execution_id=execution_id,
                    lease_token=lease_token,
                    outcome="confirmed",
                    action="codex_oauth",
                    request_id=f"codex-oauth:{run_id}",
                    detail={
                        "remote_result_confirmed": True,
                        "local_business_writeback_confirmed": account_writeback_confirmed,
                        "local_readback_confirmed": local_readback_confirmed,
                    },
                )
            elif remote_intent_started and remote_receipt_state != "rejected":
                run_summary.setdefault("outcome", "request_unknown")
                run_summary.setdefault("reconcile_required", True)
                run_summary.setdefault("remote_receipt_state", remote_receipt_state or "started")
            if final_status == "deactivated":
                persisted = db.mark_account_deactivated(
                    account_id,
                    reason=final_error or "account_deactivated",
                    source="codex_oauth",
                )
                if not persisted:
                    logger.error("Codex OAuth 废号状态写回失败：account_id=%s run_id=%s", account_id, run_id)
            operation_task_store.finish_run(
                run_id,
                status=final_status,
                message=str(result.get("message") or ""),
                error=final_error,
                result_summary=run_summary,
                execution_id=execution_id,
                lease_token=lease_token,
            )
            return {**result, "status": final_status, "run_id": run_id}
    except task_gateway.OperationLeaseLost as exc:
        message = str(exc) or "账号操作租约丢失，远端结果待核验"
        logger.error("Codex operation lease 丢失：run=%s", run_id)
        _finish_fenced(
            "attention_required",
            message="Codex OAuth 远端结果待核验，禁止自动重做",
            error=message,
            summary={
                "ok": False,
                "status": "attention_required",
                "outcome": "request_unknown",
                "reconcile_required": True,
                "lease_lost": True,
            },
        )
        return {
            "status": "attention_required",
            "ok": False,
            "message": "Codex OAuth 远端结果待核验，禁止自动重做",
            "run_id": run_id,
        }
    except OperationCancelled as exc:
        message = str(exc) or "用户手动停止 Codex 补跑"
        if remote_intent_started and remote_receipt_state != "rejected":
            _finish_fenced(
                "attention_required",
                message="停止请求发生在远端边界后；结果待核验",
                error=message,
                summary={
                    "ok": False,
                    "status": "attention_required",
                    "outcome": "request_unknown",
                    "reconcile_required": True,
                    "remote_receipt_state": remote_receipt_state or "started",
                },
            )
            return {
                "status": "attention_required",
                "ok": False,
                "message": "停止请求发生在远端边界后；结果待核验",
                "run_id": run_id,
            }
        db.update_account_codex_operation_state(
            email, execution_status="empty", last_run_status="cancelled",
            error=message, active_run_id=0,
        )
        _finish_fenced(
            "cancelled",
            error=message,
            summary={"ok": False, "status": "cancelled", "message": message},
        )
        return {"status": "cancelled", "ok": False, "message": message, "run_id": run_id}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        logger.exception("Codex operation 执行失败：run=%s email=%s", run_id, email)
        final_status = "attention_required" if (
            remote_intent_started and remote_receipt_state != "rejected"
        ) else "failed"
        final_summary = {
            "ok": final_status == "success",
            "status": final_status,
            "message": message,
            "execution_id": execution_id,
            "lease_owner": execution_id,
        }
        if final_status == "attention_required":
            final_summary.update({
                "outcome": "request_unknown",
                "reconcile_required": True,
                "remote_receipt_state": remote_receipt_state or "started",
            })
        db.update_account_codex_operation_state(
            email, execution_status="empty", last_run_status=final_status,
            error=message, active_run_id=0,
        )
        _finish_fenced(final_status, error=message, summary=final_summary)
        return {"status": final_status, "ok": False, "message": message, "run_id": run_id}
    finally:
        if file_handler is not None:
            try:
                root_logger.removeHandler(file_handler)
                file_handler.close()
            except Exception:
                pass
        if route is not None:
            try:
                route.release(reason=f"codex-operation-{run_id}")
            finally:
                if route_resource_id:
                    operation_task_store.release_resource(route_resource_id, state="released")
        if lease_guard is not None:
            lease_guard.release()
        elif lease_token:
            operation_task_store.release_account_lease(run_id, lease_token)
        with _LOCAL_TOKENS_LOCK:
            _LOCAL_TOKENS.pop(run_id, None)
        _forget_dispatched(run_id)
