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
from pathlib import Path
from typing import Iterable

from core.storage import accounts as db
from core.storage import operation_runtime_store as operation_task_store
from core import task_run_log
from core.operation_runtime import CancellationToken, OperationCancelled, operation_context
from core.account_operation_executor import configured_workers
from core.account_operation_executor import executor as _EXECUTOR

logger = logging.getLogger(__name__)

_LOG_DIR = Path(__file__).resolve().parent.parent / "注册日志"
_LOCAL_TOKENS: dict[int, CancellationToken] = {}
_LOCAL_TOKENS_LOCK = threading.RLock()


def log_path(email: str) -> Path:
    safe = str(email or "").replace("/", "_").replace("\\", "_").replace(":", "_")
    return _LOG_DIR / f"codex-retry-{safe}.log"


def _executor():
    """Compatibility accessor for the shared account-operation executor."""
    return _EXECUTOR


def _feature_ready() -> tuple[bool, str]:
    from core.feature_availability import require_feature

    return require_feature("codex_retry")


def _config_snapshot(driver_override: str | None = None) -> dict:
    """只保存可复现执行路径所需的非敏感配置。"""
    from config import codex as cfg
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
        "account_proxy_mode": str(getattr(proxy_cfg, "ACCOUNT_ACTION_PROXY_MODE", "registration") or "registration"),
    }


def _append_log(email: str, message: str, *, clear: bool = False) -> None:
    path = log_path(email)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if clear else "a"
    with path.open(mode, encoding="utf-8") as handle:
        handle.write(str(message).rstrip() + "\n")


def _dispatch(run_id: int) -> None:
    _EXECUTOR.submit(_execute_run, int(run_id))


def _dispatch_bulk(run_ids: list[int], workers: int | None = None) -> None:
    """Submit every run to the common account-operation pool.

    ``workers`` remains accepted for compatibility with older callers, but
    ACCOUNT_BATCH_WORKERS is authoritative.
    """
    for run_id in run_ids:
        _EXECUTOR.submit(_execute_run, int(run_id))


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
        )
    except Exception as exc:
        # 活跃 run 的部分唯一索引是跨进程防重事实；不再依赖进程内 email set。
        if "uq_operation_runs_active_account_family" in str(exc) or "duplicate key" in str(exc).lower():
            return _duplicate_result(account_id)
        logger.exception("创建 Codex operation 失败：email=%s", email)
        return {"accepted": False, "error": f"创建任务失败：{type(exc).__name__}: {exc}"}
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


def resume_queued(*, limit: int = 500) -> int:
    """进程启动后恢复数据库队列；claim_run 保证多进程不会重复执行。"""
    runs = operation_task_store.list_queued_runs(limit=limit)
    for run in runs:
        _dispatch(int(run["id"]))
    return len(runs)


def _execute_run(run_id: int) -> dict:
    execution_id = uuid.uuid4().hex
    run = operation_task_store.claim_run(run_id, execution_id=execution_id, worker_pid=os.getpid())
    if not run:
        return {"status": "not_claimed", "run_id": run_id}
    current = operation_task_store.get_run(run_id) or run
    email = str(current.get("email_snapshot") or "")
    account_id = int(current.get("account_id") or 0)
    cancellation_token = str(current.get("cancellation_token") or "")
    token = CancellationToken(
        run_id=run_id,
        token=cancellation_token,
        checker=operation_task_store.is_run_cancel_requested,
    )
    lease_token = ""
    route = None
    route_resource_id: int | None = None
    result: dict = {"status": "failed", "ok": False, "message": "OAuth 未返回结果"}
    root_logger = logging.getLogger()
    file_handler: logging.Handler | None = None

    def report(**event):
        return operation_task_store.append_runtime_event(run_id, **event)

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

            result = run_codex_oauth(
                email,
                proxy=route.proxy_url if route is not None else None,
                force=True,
                driver_override=driver,
            )
            confirmed = bool(result.get("credential_confirmed"))
            callback_submitted = bool(result.get("callback_submitted"))
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
            operation_task_store.finish_run(
                run_id,
                status=final_status,
                message=str(result.get("message") or ""),
                error=final_error,
                result_summary={
                    "ok": final_status == "success",
                    "status": final_status,
                    "message": result.get("message"),
                    "credential_confirmed": confirmed,
                    "callback_submitted": callback_submitted,
                    "credential_file": Path(str(result.get("file_path") or "")).name or None,
                    "receipt_file": Path(str(result.get("receipt_path") or "")).name or None,
                    "oauth_driver": driver,
                },
            )
            db.update_account_codex_operation_state(
                email,
                credential_state=credential_state,
                execution_status="empty",
                last_run_status=final_status,
                error=final_error,
                active_run_id=0,
            )
            if final_status == "deactivated":
                persisted = db.mark_account_deactivated(
                    account_id,
                    reason=final_error or "account_deactivated",
                    source="codex_oauth",
                )
                if not persisted:
                    logger.error("Codex OAuth 废号状态写回失败：account_id=%s run_id=%s", account_id, run_id)
            return {**result, "status": final_status, "run_id": run_id}
    except OperationCancelled as exc:
        message = str(exc) or "用户手动停止 Codex 补跑"
        operation_task_store.finish_run(run_id, status="cancelled", error=message, result_summary={"ok": False, "status": "cancelled", "message": message})
        db.update_account_codex_operation_state(
            email, execution_status="empty", last_run_status="cancelled",
            error=message, active_run_id=0,
        )
        return {"status": "cancelled", "ok": False, "message": message, "run_id": run_id}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        logger.exception("Codex operation 执行失败：run=%s email=%s", run_id, email)
        operation_task_store.finish_run(run_id, status="failed", error=message, result_summary={"ok": False, "status": "failed", "message": message})
        db.update_account_codex_operation_state(
            email, execution_status="empty", last_run_status="failed",
            error=message, active_run_id=0,
        )
        return {"status": "failed", "ok": False, "message": message, "run_id": run_id}
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
        if lease_token:
            operation_task_store.release_account_lease(run_id, lease_token)
        with _LOCAL_TOKENS_LOCK:
            _LOCAL_TOKENS.pop(run_id, None)
