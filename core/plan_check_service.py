# -*- coding: utf-8 -*-
"""套餐/Plus 资格查询后台队列。"""
from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from datetime import datetime

from config import proxy as proxy_cfg
from config.schema import get_config_snapshot
from core.operation_runtime import OperationCancelled
from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.chatgpt_plan import check_account_plan
from core.task_reporter import TaskReporter
from core.account_operation_executor import configured_workers
from core.account_operation_executor import executor as _ACCOUNT_EXECUTOR

logger = logging.getLogger(__name__)


def _int_setting(name: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(getattr(proxy_cfg, name, default) or default)
    except (TypeError, ValueError):
        value = default
    return max(lower, min(upper, value))


def _float_setting(name: str, default: float, lower: float, upper: float) -> float:
    try:
        value = float(getattr(proxy_cfg, name, default) or 0.0)
    except (TypeError, ValueError):
        value = default
    return max(lower, min(upper, value))


_WORKERS = _int_setting("PLAN_CHECK_WORKERS", 3, 1, 16)
_QUEUE_LIMIT = _int_setting("PLAN_CHECK_QUEUE_LIMIT", 500, _WORKERS, 5000)
_QUEUE_SLOTS = threading.BoundedSemaphore(_QUEUE_LIMIT)  # synchronous compatibility only
_RATE_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0


class _RegistrationExecutorCompatibility:
    """Keep the old registration-pool patch surface without a local worker."""

    def submit(self, *_args, **_kwargs):
        raise RuntimeError(
            "plan_check native operations must be submitted through task_gateway"
        )


# Older callers/tests patch this symbol to observe the registration boundary.
# Native standalone plan checks never call it; the durable gateway owns claim
# and dispatch, while ``_ACCOUNT_EXECUTOR`` preserves the common-pool identity
# expected by the remaining account-operation compatibility surface.
_EXECUTOR = _RegistrationExecutorCompatibility()

# Only stable, non-sensitive execution settings are copied into a durable
# Run.  The actual proxy URL/API token remains an on-demand resource owned by
# the account/HTTP clients and is never part of task data.
PLAN_CONFIG_ALLOWLIST = {
    "plan_check_timeout": "PLAN_CHECK_TIMEOUT",
    "plan_check_max_attempts": "PLAN_CHECK_MAX_ATTEMPTS",
    "plan_check_retry_delay": "PLAN_CHECK_RETRY_DELAY",
    "registration_recheck_delay": "PLAN_CHECK_REGISTRATION_RECHECK_DELAY",
    "min_interval": "PLAN_CHECK_MIN_INTERVAL",
    "jitter": "PLAN_CHECK_JITTER",
    "route_source": "ACCOUNT_PLAN_CHECK_PROXY_MODE",
    "driver": "ACCOUNT_PLAN_CHECK_DRIVER",
}


def _snapshot_value(snapshot, key: str, default=None):
    if isinstance(snapshot, dict) and key in snapshot:
        return snapshot[key]
    return default


def _captured_proxy_source(purpose: str) -> str | None:
    """Resolve the effective route once, without persisting its URL/secret."""
    try:
        from core.account_proxy import account_action_proxy_mode

        return str(account_action_proxy_mode(purpose) or "").strip() or None
    except Exception:
        logger.exception("[Plan] 读取账号动作线路配置失败: purpose=%s", purpose)
        return None


class _ReporterAdapter:
    """Route the established reporter calls to a native operation context."""

    def __init__(self, task_id: int | None, context=None):
        self._legacy = TaskReporter(task_id) if context is None else None
        self._context = context

    def start(self, message: str = "开始执行") -> None:
        if self._context is None:
            self._legacy.start(message)
        else:
            self._context.report(stage="preflight", state="running", message=message)

    def stage(self, stage: str, state: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.stage(stage, state, message, **kwargs)
        else:
            self._context.report(stage=stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs) -> None:
        if self._context is None:
            self._legacy.note(message, stage=stage, **kwargs)
        else:
            self._context.report(stage=stage, message=message, **kwargs)

    def resource(self, event_type: str, message: str, *, stage: str = "network", **kwargs) -> None:
        if self._context is None:
            self._legacy.resource(event_type, message, stage=stage, **kwargs)
        else:
            self._context.report(stage=stage, message=message, event_type=event_type, **kwargs)

    def finish(self, *, status: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.finish(status=status, message=message, **kwargs)
            return
        summary = dict(kwargs.get("result_summary") or {})
        for key in ("route", "validation_method"):
            if kwargs.get(key) is not None:
                summary[key] = kwargs[key]
        self._context.finish(
            status=status,
            message=message,
            error=kwargs.get("error"),
            result_summary=summary,
        )


def _checkpoint(context, message: str = "用户手动停止套餐查询") -> None:
    if context is not None:
        context.checkpoint(message)


def _wait_for_rate_slot(config_snapshot: dict | None = None) -> None:
    """为所有查询线程分配错开的请求启动时间。"""
    global _NEXT_REQUEST_AT
    min_interval = _float_setting(
        "PLAN_CHECK_MIN_INTERVAL", 0.4, 0.0, 30.0,
    ) if config_snapshot is None else max(
        0.0,
        min(30.0, float(_snapshot_value(config_snapshot, "min_interval", 0.4) or 0.0)),
    )
    jitter = _float_setting(
        "PLAN_CHECK_JITTER", 0.3, 0.0, 30.0,
    ) if config_snapshot is None else max(
        0.0,
        min(30.0, float(_snapshot_value(config_snapshot, "jitter", 0.3) or 0.0)),
    )
    with _RATE_LOCK:
        now = time.monotonic()
        scheduled = max(now, _NEXT_REQUEST_AT) + (random.uniform(0.0, jitter) if jitter else 0.0)
        _NEXT_REQUEST_AT = scheduled + min_interval
    wait_seconds = scheduled - now
    if wait_seconds > 0:
        time.sleep(wait_seconds)


def _registration_recheck_delay(config_snapshot: dict | None = None) -> float:
    if config_snapshot is None:
        return _float_setting("PLAN_CHECK_REGISTRATION_RECHECK_DELAY", 2.0, 0.0, 30.0)
    try:
        value = float(_snapshot_value(config_snapshot, "registration_recheck_delay", 2.0) or 0.0)
    except (TypeError, ValueError):
        value = 2.0
    return max(0.0, min(30.0, value))


def _query_account_plan(
    *,
    email: str,
    access_token: str,
    trigger: str,
    proxy: str | None,
    timezone_offset_min: str,
    session=None,
    config_snapshot: dict | None = None,
) -> dict:
    """执行套餐查询和新注册账号复查，不负责队列/数据库状态流转。"""
    _wait_for_rate_slot(config_snapshot)
    query_kwargs = {
        "proxy": proxy,
        "timezone_offset_min": timezone_offset_min,
    }
    if config_snapshot is not None:
        try:
            timeout = max(
                1.0,
                min(60.0, float(_snapshot_value(config_snapshot, "plan_check_timeout", 15.0) or 15.0)),
            )
        except (TypeError, ValueError):
            timeout = 15.0
        try:
            max_attempts = max(
                1,
                min(4, int(_snapshot_value(config_snapshot, "plan_check_max_attempts", 2) or 1)),
            )
        except (TypeError, ValueError):
            max_attempts = 2
        try:
            retry_delay = max(
                0.0,
                min(30.0, float(_snapshot_value(config_snapshot, "plan_check_retry_delay", 1.5) or 0.0)),
            )
        except (TypeError, ValueError):
            retry_delay = 1.5
        query_kwargs.update({
            "timeout": timeout,
            "max_attempts": max_attempts,
            "retry_delay": retry_delay,
        })
    if session is not None:
        query_kwargs["session"] = session
    result = check_account_plan(access_token, **query_kwargs)

    recheck_delay = _registration_recheck_delay(config_snapshot)
    should_recheck = (
        trigger == "registration_auto"
        and recheck_delay > 0
        and bool(result.get("ok"))
        and str(result.get("current_plan_type") or "").lower() == "free"
        and not bool(result.get("plus_trial_eligible"))
    )
    if should_recheck:
        logger.info("[Plan] 新账号暂未发现 Plus 试用资格，%.1fs 后复查一次: %s", recheck_delay, email)
        time.sleep(recheck_delay)
        _wait_for_rate_slot(config_snapshot)
        recheck_kwargs = {
            "proxy": proxy,
            "timezone_offset_min": timezone_offset_min,
            "max_attempts": 1,
        }
        if config_snapshot is not None:
            try:
                recheck_kwargs["timeout"] = max(
                    1.0,
                    min(60.0, float(_snapshot_value(config_snapshot, "plan_check_timeout", 15.0) or 15.0)),
                )
                recheck_kwargs["retry_delay"] = max(
                    0.0,
                    min(30.0, float(_snapshot_value(config_snapshot, "plan_check_retry_delay", 1.5) or 0.0)),
                )
            except (TypeError, ValueError):
                recheck_kwargs.update({"timeout": 15.0, "retry_delay": 1.5})
        if session is not None:
            recheck_kwargs["session"] = session
        recheck_result = check_account_plan(access_token, **recheck_kwargs)
        if recheck_result.get("ok"):
            result = recheck_result
        else:
            logger.warning(
                "[Plan] 新账号资格复查失败，保留首次成功结果: %s, %s",
                email,
                recheck_result.get("error") or "未知错误",
            )
    return result


def _log_plan_result(email: str, trigger: str, result: dict) -> None:
    if result.get("ok"):
        logger.info(
            "[Plan] 后台查询成功: %s, plan=%s, plus_trial=%s, trigger=%s",
            email,
            result.get("current_plan_type") or "unknown",
            bool(result.get("plus_trial_eligible")),
            trigger,
        )
    else:
        logger.warning(
            "[Plan] 后台查询失败: %s, trigger=%s, error=%s",
            email,
            trigger,
            result.get("error") or "未知错误",
        )


def _run_plan_check(
    *,
    account_id: int,
    email: str,
    access_token: str,
    trigger: str,
    proxy: str | None,
    timezone_offset_min: str,
    task_id: int | None = None,
    operation_context=None,
    release_queue_slot: bool = False,
    config_snapshot: dict | None = None,
    proxy_source: str | None = None,
) -> dict:
    account_route = None
    reporter = _ReporterAdapter(task_id, operation_context)
    try:
        _checkpoint(operation_context)
        if not db.mark_account_plan_check_running(account_id):
            reporter.finish(
                status="cancelled",
                message="账号已删除或套餐查询状态已被重置",
            )
            return {"ok": False, "error": "账号已删除或套餐查询状态已被重置"}
        reporter.start(message="开始查询账号套餐")

        from core.account_proxy import acquire_account_proxy
        _checkpoint(operation_context, "套餐查询申请线路前检查取消状态")
        route_kwargs = {
            "account_id": account_id,
            "email": email,
            "purpose": "plan-check",
            "explicit_proxy": proxy,
        }
        selected_source = proxy_source or _snapshot_value(config_snapshot, "route_source")
        if selected_source:
            route_kwargs["source"] = selected_source
        account_route = acquire_account_proxy(
            **route_kwargs,
        )
        reporter.resource(
            "resource.acquired",
            message="已选择套餐查询线路",
            stage="network",
            detail=account_route.public_dict(),
        )
        reporter.stage("network", "success", "套餐查询线路已就绪")

        reporter.stage("plan_check", "running", "请求 ChatGPT 套餐接口")
        _checkpoint(operation_context, "请求套餐接口前检查取消状态")
        result = _query_account_plan(
            email=email,
            access_token=access_token,
            trigger=trigger,
            proxy=account_route.proxy_url,
            timezone_offset_min=timezone_offset_min,
            config_snapshot=config_snapshot,
        )
        result.update({
            key: value
            for key, value in account_route.public_dict().items()
            if key not in {"proxy_mode", "network_route", "proxy_used"} or not result.get(key)
        })
        db.update_account_plan_check(acc_id=account_id, result=result)
        _log_plan_result(email, trigger, result)
        reporter.stage(
            "plan_check", "success" if result.get("ok") else "failed",
            "套餐查询成功" if result.get("ok") else "套餐查询失败",
            level="INFO" if result.get("ok") else "ERROR",
            detail={"http_status": result.get("http_status"), "current_plan_type": result.get("current_plan_type")},
        )
        reporter.finish(
            status="success" if result.get("ok") else "failed",
            message="套餐查询成功" if result.get("ok") else "套餐查询失败",
            error=result.get("error") if not result.get("ok") else None,
            result_summary={
                "ok": bool(result.get("ok")),
                "http_status": result.get("http_status"),
                "current_plan_type": result.get("current_plan_type"),
                "plus_trial_eligible": result.get("plus_trial_eligible"),
                "checked_at": result.get("checked_at"),
                "token_expires_at": result.get("token_expires_at"),
            },
            route=account_route.public_dict(),
            validation_method="access_token",
        )
        return result
    except account_task_store.OperationLeaseLost:
        # Native lease loss must be fenced by the gateway as request_unknown.
        raise
    except OperationCancelled as exc:
        result = {
            "ok": False,
            "status": "cancelled",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc) or "套餐查询任务已取消",
            "cancelled": True,
        }
        try:
            db.update_account_plan_check(acc_id=account_id, result=result)
        except Exception:
            logger.exception("[Plan] 取消状态写回失败: account_id=%s", account_id)
        reporter.finish(status="cancelled", message="套餐查询任务已取消", error=result["error"])
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }
        try:
            db.update_account_plan_check(acc_id=account_id, result=result)
        except Exception:
            logger.exception("[Plan] 写入后台查询异常状态失败: account_id=%s", account_id)
        logger.exception("[Plan] 后台查询异常: %s", email)
        reporter.stage(
            "plan_check", "failed", "套餐查询后台执行异常",
            level="ERROR", detail={"error": result["error"]},
        )
        reporter.finish(
            status="failed",
            message="套餐查询后台执行异常",
            error=result["error"],
            route=account_route.public_dict() if account_route is not None else None,
            validation_method="access_token",
        )
        return result
    finally:
        if account_route is not None:
            account_route.release(reason=f"plan-check-{account_id}")
        if release_queue_slot:
            _QUEUE_SLOTS.release()


def check_registration_account_plan(
    *,
    account_id: int,
    email: str,
    access_token: str,
    proxy: str,
    session=None,
    timezone_offset_min: str = "-",
    trigger: str = "registration_auto",
) -> dict:
    """用注册任务的同一代理同步查询套餐，返回后调用方才可释放代理租约。"""
    account_id = int(account_id)
    trigger = str(trigger or "registration_auto")
    if not db.claim_account_plan_check(acc_id=account_id, trigger=trigger):
        return {"ok": False, "busy": True, "error": "该账号正在查询套餐"}
    task_id = account_task_store.create_task(
        task_type="plan_check",
        account_id=account_id,
        email=str(email or "").strip(),
        trigger=trigger,
    )
    reporter = TaskReporter(task_id)
    try:
        if not db.mark_account_plan_check_running(account_id):
            reporter.finish(
                status="cancelled",
                message="账号已删除或套餐查询状态已被重置",
            )
            return {"ok": False, "error": "账号已删除或套餐查询状态已被重置"}
        reporter.start(message="注册完成，开始自动查询套餐")
        reporter.stage("network", "success", "复用注册任务网络线路")
        reporter.stage("plan_check", "running", "复用注册线路请求套餐接口")
        query_kwargs = {
            "email": str(email or "").strip(),
            "access_token": str(access_token or "").strip(),
            "trigger": trigger,
            "proxy": str(proxy or "").strip(),
            "timezone_offset_min": str(timezone_offset_min or "-"),
        }
        if session is not None:
            query_kwargs["session"] = session
        result = _query_account_plan(
            **query_kwargs,
        )
        db.update_account_plan_check(acc_id=account_id, result=result)
        _log_plan_result(str(email or "").strip(), trigger, result)
        reporter.stage(
            "plan_check", "success" if result.get("ok") else "failed",
            "注册后套餐查询成功" if result.get("ok") else "注册后套餐查询失败",
            level="INFO" if result.get("ok") else "ERROR",
            detail={"http_status": result.get("http_status"), "current_plan_type": result.get("current_plan_type")},
        )
        reporter.finish(
            status="success" if result.get("ok") else "failed",
            message="注册后套餐查询成功" if result.get("ok") else "注册后套餐查询失败",
            error=result.get("error") if not result.get("ok") else None,
            result_summary={
                "ok": bool(result.get("ok")),
                "http_status": result.get("http_status"),
                "current_plan_type": result.get("current_plan_type"),
                "plus_trial_eligible": result.get("plus_trial_eligible"),
                "checked_at": result.get("checked_at"),
                "token_expires_at": result.get("token_expires_at"),
            },
            route={"network_route": "registration_proxy", "proxy_used": proxy},
            validation_method="access_token",
        )
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }
        try:
            db.update_account_plan_check(acc_id=account_id, result=result)
        except Exception:
            logger.exception("[Plan] 写入同步查询异常状态失败: account_id=%s", account_id)
        logger.exception("[Plan] 注册代理同步查询异常: %s", email)
        reporter.stage(
            "plan_check", "failed", "注册后套餐查询异常",
            level="ERROR", detail={"error": result["error"]},
        )
        reporter.finish(
            status="failed",
            message="注册后套餐查询异常",
            error=result["error"],
            route={"network_route": "registration_proxy", "proxy_used": proxy},
            validation_method="access_token",
        )
        return result


def _numeric_batch_id(value: str | int | None) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip().isdigit() else None
    except (TypeError, ValueError):
        return None


def _native_response(submitted: dict, *, account_id: int, email: str, trigger: str) -> dict:
    accepted = bool(submitted.get("accepted"))
    response = {
        "accepted": accepted,
        "busy": bool(submitted.get("busy")) and not accepted,
        "account_id": account_id,
        "email": email,
        "status": submitted.get("status") or ("queued" if accepted else "failed"),
        "trigger": trigger,
        "task_id": submitted.get("task_id"),
        "run_id": submitted.get("run_id"),
        "reused": bool(submitted.get("reused")),
    }
    if submitted.get("error"):
        response["error"] = submitted["error"]
    return response


def _cancel_unclaimed_native_run(run_id: int | None) -> None:
    if not run_id:
        return
    try:
        from core.storage import operation_runtime_store

        operation_runtime_store.request_run_cancel(int(run_id), reason="账号套餐查询业务状态已被其他请求占用")
    except Exception:
        logger.exception("[Plan] 取消孤立 durable run 失败: run_id=%s", run_id)


def _handle_plan_operation(context):
    if context.account_id is None:
        context.finish(status="failed", message="套餐查询缺少账号", error="套餐查询缺少账号")
        return None
    data = context.run.get("data") if isinstance(context.run.get("data"), dict) else {}
    account = db.get_account(int(context.account_id))
    if not account:
        context.finish(status="cancelled", message="账号不存在，取消套餐查询", error="账号不存在")
        return None
    access_token = str((account or {}).get("access_token") or "").strip()
    email = str((account or {}).get("email") or context.email or "").strip()
    if not access_token:
        error = "账号缺少 access_token"
        db.update_account_plan_check(
            acc_id=int(context.account_id),
            result={"ok": False, "status": "failed", "error": error},
        )
        context.finish(status="failed", message=error, error=error)
        return None
    with context.lease(resource_family="openai_interactive"):
        _run_plan_check(
            account_id=int(context.account_id),
            email=email,
            access_token=access_token,
            trigger=str(context.run.get("trigger") or "manual"),
            proxy=None,
            timezone_offset_min=str(data.get("timezone_offset_min") or "-"),
            task_id=int(context.task_id),
            operation_context=context,
            release_queue_slot=False,
            config_snapshot=context.config_snapshot,
            proxy_source=str(
                data.get("proxy_source")
                or _snapshot_value(context.config_snapshot, "route_source")
                or ""
            ).strip() or None,
        )
    return None


def register_operation_handlers() -> bool:
    register = getattr(account_task_store, "register_operation_handler", None)
    if not callable(register):
        return False
    register(
        "plan_check",
        _handle_plan_operation,
        source_systems=("native_operations",),
        config_allowlist=PLAN_CONFIG_ALLOWLIST,
    )
    return True


def start_dispatcher() -> bool:
    if not register_operation_handlers():
        return False
    starter = getattr(account_task_store, "start_dispatcher", None)
    return bool(starter()) if callable(starter) else False


def _submit_native_plan(
    *, account_id: int, email: str, trigger: str, timezone_offset_min: str,
    batch_id: str | None, idempotency_key: str | None,
) -> dict:
    register_operation_handlers()
    key = str(idempotency_key or "").strip() or None
    source_id = (
        f"maintenance:plan_check:{account_id}:{key}"
        if key else f"maintenance:plan_check:{account_id}:{uuid.uuid4().hex}"
    )
    return account_task_store.submit_durable_operation(
        task_type="plan_check",
        account_id=account_id,
        email=email,
        trigger=trigger,
        source_system="native_operations",
        source_id=source_id,
        idempotency_key=key,
        batch_id=_numeric_batch_id(batch_id),
        resource_family="openai_interactive",
        data={
            "timezone_offset_min": str(timezone_offset_min or "-"),
            # This is a route mode, never a proxy URL.  Capturing the
            # effective source also preserves the legacy registration-mode
            # fallback while preventing a queued Run from changing route
            # halfway through execution.
            "proxy_source": _captured_proxy_source("plan-check"),
        },
        config_snapshot_provider=get_config_snapshot,
        config_allowlist=PLAN_CONFIG_ALLOWLIST,
        dispatch=True,
    )


def enqueue_account_plan_check(
    *,
    account_id: int,
    email: str,
    access_token: str,
    trigger: str,
    proxy: str | None = None,
    timezone_offset_min: str = "-",
    batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Persist a plan check in the native operation queue when available."""
    account_id = int(account_id)
    email = str(email or "").strip()
    trigger = str(trigger or "manual")
    access_token = str(access_token or "").strip()
    if not access_token:
        return {"accepted": False, "busy": False, "error": "账号缺少 access_token"}
    if not db.get_account(account_id):
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    claimed = False
    key = str(idempotency_key or "").strip() or None
    if not key:
        if not db.claim_account_plan_check(acc_id=account_id, trigger=trigger):
            return {"accepted": False, "busy": True, "error": "该账号正在查询套餐"}
        claimed = True
    try:
        submitted = _submit_native_plan(
            account_id=account_id, email=email, trigger=trigger,
            timezone_offset_min=str(timezone_offset_min or "-"),
            batch_id=batch_id, idempotency_key=key,
        )
    except Exception as exc:
        error = f"套餐查询任务持久化失败: {type(exc).__name__}: {str(exc)[:300]}"
        if claimed:
            db.update_account_plan_check(acc_id=account_id, result={"ok": False, "error": error})
        return {"accepted": False, "busy": False, "error": error}
    if not submitted.get("accepted"):
        return _native_response(submitted, account_id=account_id, email=email, trigger=trigger)
    if key and not submitted.get("reused"):
        if not db.claim_account_plan_check(acc_id=account_id, trigger=trigger):
            _cancel_unclaimed_native_run(submitted.get("run_id"))
            return {
                "accepted": False, "busy": True, "account_id": account_id,
                "email": email, "task_id": submitted.get("task_id"),
                "run_id": submitted.get("run_id"), "error": "该账号正在查询套餐",
            }
    return _native_response(submitted, account_id=account_id, email=email, trigger=trigger)


def queue_settings() -> dict:
    return {
        "workers": configured_workers(),
        "registration_workers": _WORKERS,
        "queue_limit": _QUEUE_LIMIT,
        "min_interval": _float_setting("PLAN_CHECK_MIN_INTERVAL", 0.4, 0.0, 30.0),
        "jitter": _float_setting("PLAN_CHECK_JITTER", 0.3, 0.0, 30.0),
    }


register_operation_handlers()
