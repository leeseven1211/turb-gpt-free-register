# -*- coding: utf-8 -*-
"""套餐、Go / Plus 优惠查询后台队列。"""
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
from core import task_run_log
from core.operations import task_gateway as account_task_store
from core.storage import accounts as db
from core.chatgpt_plan import check_account_plan
from core.plus_promotion import sanitize_promotion_text
from core.task_reporter import TaskReporter
from core.account_operation_executor import configured_workers, operation_log_context
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
    "proxy_allow_reuse": "PLAN_CHECK_PROXY_ALLOW_REUSE",
    "proxy_reuse_limit": "PLAN_CHECK_PROXY_REUSE_LIMIT",
    "countries": "PLAN_CHECK_COUNTRIES",
    "country_wait_timeout": "PLAN_CHECK_COUNTRY_WAIT_TIMEOUT",
    "legacy_route_source": "ACCOUNT_ACTION_PROXY_MODE",
    "registration_route_source": "REGISTRATION_PROXY_MODE",
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
            self._native_report("preflight", state="running", message=message)

    def _native_report(self, stage: str, **event):
        task_run_log.set_current_stage(
            stage, task_id=getattr(self._context, "task_id", None),
            run_id=getattr(self._context, "run_id", None),
        )
        result = self._context.report(stage=stage, **event)
        if isinstance(result, dict):
            task_run_log.set_current_stage(
                stage,
                event_id=result.get("event_id", result.get("id")),
                event_uuid=result.get("event_uuid"),
                source_event_id=result.get("source_event_id"),
                source_system=result.get("source_system"),
                main_step_id=result.get("main_step_id"),
            )
        return result

    def stage(self, stage: str, state: str, message: str, **kwargs) -> None:
        if self._context is None:
            self._legacy.stage(stage, state, message, **kwargs)
        else:
            self._native_report(stage, state=state, message=message, **kwargs)

    def note(self, message: str, *, stage: str = "event", **kwargs) -> None:
        if self._context is None:
            self._legacy.note(message, stage=stage, **kwargs)
        else:
            self._native_report(stage, message=message, **kwargs)

    def resource(self, event_type: str, message: str, *, stage: str = "network", **kwargs) -> None:
        if self._context is None:
            self._legacy.resource(event_type, message, stage=stage, **kwargs)
        else:
            self._native_report(stage, message=message, event_type=event_type, **kwargs)

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


def _wait_for_rate_slot(config_snapshot: dict | None = None, *, deadline_at: float | None = None,
                        operation_context=None) -> None:
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
    if deadline_at is None:
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return
    while True:
        _checkpoint(operation_context, "套餐限速等待时检查取消状态")
        remaining = deadline_at - time.time()
        if remaining <= 0:
            raise TimeoutError("国家查询总期限已到")
        wait_seconds = scheduled - time.monotonic()
        if wait_seconds <= 0:
            return
        time.sleep(min(.25, wait_seconds, remaining))


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
    query_history = [_plan_query_record(result, phase="initial")]

    recheck_delay = _registration_recheck_delay(config_snapshot)
    should_recheck = (
        trigger == "registration_auto"
        and recheck_delay > 0
        and bool(result.get("ok"))
        and str(result.get("current_plan_type") or "").lower() == "free"
        and not bool(result.get("plus_promo_eligible", result.get("plus_trial_eligible")))
    )
    if should_recheck:
        logger.info("[Plan] 新账号暂未发现 Plus 优惠，%.1fs 后复查一次: %s", recheck_delay, email)
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
        query_history.append(_plan_query_record(recheck_result, phase="registration_recheck"))
        if recheck_result.get("ok"):
            result = recheck_result
        else:
            logger.warning(
                "[Plan] 新账号资格复查失败，保留首次成功结果: %s, %s",
                email,
                recheck_result.get("error") or "未知错误",
            )
    result["promotion_query_history"] = query_history
    return result


def _plan_query_record(result: dict, *, phase: str) -> dict:
    """逐次保存已脱敏活动信息，首次响应不会被注册复查覆盖。"""
    record = {
        "phase": phase,
        "ok": bool(result.get("ok")),
        "http_status": result.get("http_status"),
        "checked_at": result.get("checked_at"),
        "current_plan_type": result.get("current_plan_type"),
    }
    if not result.get("ok"):
        record["error"] = sanitize_promotion_text(result.get("error"))
    for key in ("account_promotions", "promotion_query_snapshot"):
        if key in result:
            record[key] = result[key]
    return record


def _record_promotion_queries(reporter, result: dict) -> None:
    """每次响应单独写入任务事件，证据保持扁平以兼容日志深度限制。"""
    records = result.get("promotion_query_history")
    if not isinstance(records, list):
        records = [_plan_query_record(result, phase="initial")]
    for record in records:
        detail = {key: value for key, value in record.items() if key != "promotion_query_snapshot"}
        snapshot = record.get("promotion_query_snapshot")
        if isinstance(snapshot, dict):
            detail.update(snapshot)
        reporter.note(
            "已保存套餐优惠响应记录", stage="plan_check",
            event_type="promotion.query.recorded", detail=detail,
        )


def _plan_result_summary(result: dict) -> dict:
    """把套餐结果和活动证据写入每次任务，避免账号快照更新后丢失历史。"""
    keys = (
        "http_status", "current_plan_type", "plus_trial_eligible",
        "plus_discount_eligible", "plus_promo_kind", "plus_promo_discount_percentage",
        "plus_promo_duration_num_periods", "plus_promo_duration_period",
        "checked_at", "token_expires_at", "plan_check_countries", "plan_check_partial",
        "country_success_count", "country_total_count", "failed_countries",
    )
    summary = {"ok": bool(result.get("ok")), **{key: result.get(key) for key in keys}}
    for key in ("account_promotions", "promotion_query_snapshot"):
        if key in result:
            summary[key] = result[key]
    if isinstance(result.get("promotion_query_history"), list):
        # 完整证据按响应保存在独立任务事件中，摘要只保存查询索引。
        summary["promotion_query_history"] = [
            {key: record.get(key) for key in ("phase", "country", "ok", "http_status", "checked_at", "current_plan_type")}
            for record in result["promotion_query_history"]
        ]
    return summary


def _run_country_plan_checks(
    *, account_id: int, email: str, access_token: str, trigger: str, proxy: str | None,
    timezone_offset_min: str, countries: list[str], reporter, operation_context,
    config_snapshot: dict | None, proxy_source: str | None, fence: dict | None = None,
) -> dict:
    """逐国查询并立即保存结果，单国缺货或请求失败不会跳过后续国家。"""
    from core.account_proxy import acquire_account_proxy
    from core.plan_check_countries import aggregate_country_results, now_iso
    from core.storage import plan_countries

    from config.countries import normalize_plan_check_countries
    countries = normalize_plan_check_countries(countries)
    timeout = max(1, min(60, float(_snapshot_value(config_snapshot, "plan_check_timeout", 15))))
    attempts = max(1, min(4, int(_snapshot_value(config_snapshot, "plan_check_max_attempts", 2))))
    wait_timeout = float(_snapshot_value(config_snapshot, "country_wait_timeout", getattr(proxy_cfg, "PLAN_CHECK_COUNTRY_WAIT_TIMEOUT", 60)))
    rate_budget = (float(_snapshot_value(config_snapshot, "min_interval", .4)) + float(_snapshot_value(config_snapshot, "jitter", .3))) * (configured_workers() + 1)
    budget = len(countries) * (wait_timeout + timeout * (attempts + 1) + 30 * (attempts - 1) + rate_budget + 35)
    rows, progress = plan_countries.initialize_country_checks(
        account_id, countries, fence=fence, budget_seconds=budget,
        wait_seconds=wait_timeout, max_attempts=attempts,
    )
    countries = list(progress["countries"])
    attempts = progress["max_attempts"]
    while any(state["pending"] for state in progress["countries"].values()):
        made_progress = False
        for country in countries:
            state = progress["countries"][country]
            if not state["pending"]:
                continue
            _checkpoint(operation_context, "逐国查询前检查取消状态")
            now = time.time()
            expired = progress["deadline_at"] - now < 2
            exhausted = state["http_attempts"] >= attempts
            no_supply_budget = state["wait_used"] >= progress["wait_limit"]
            if expired or exhausted or no_supply_budget:
                error = "国家查询总期限已到" if expired else "该国家请求次数已耗尽" if exhausted else "该国库存暂缺，累计等待预算已耗尽"
                rows, progress = plan_countries.update_country_progress(
                    account_id, country, progress, action="result", fence=fence,
                    result={"ok": False, "error": error, "checked_at": now_iso()},
                )
                made_progress = True
                continue
            if state.get("retry_not_before", 0) > now:
                continue
            made_progress = True
            route = None
            answer = None
            rows, progress = plan_countries.update_country_progress(
                account_id, country, progress, action="wait_start", fence=fence, slice_seconds=5,
            )
            state = progress["countries"][country]
            try:
                reporter.stage("network", "running", f"正在申请 {country} 套餐查询线路")
                def report_wait(message, selected=country):
                    _checkpoint(operation_context, "等待国家代理时检查取消状态")
                    reporter.note(f"{selected} · {message}", stage="network")
                try:
                    # 切片持久化与进度上报已消耗的时间不能再次交给线路领取。
                    slice_timeout = min(state["wait_slice_deadline_at"], progress["deadline_at"]) - time.time()
                    if slice_timeout <= 0:
                        raise TimeoutError("国家线路等待切片期限已到")
                    route = acquire_account_proxy(
                        account_id=account_id, email=email, purpose="plan-check", region=country,
                        explicit_proxy=proxy,
                        source=proxy_source or _snapshot_value(config_snapshot, "route_source") or None,
                        allow_reuse=bool(_snapshot_value(config_snapshot, "proxy_allow_reuse", getattr(proxy_cfg, "PLAN_CHECK_PROXY_ALLOW_REUSE", True))),
                        reuse_limit=int(_snapshot_value(config_snapshot, "proxy_reuse_limit", getattr(proxy_cfg, "PLAN_CHECK_PROXY_REUSE_LIMIT", 3))),
                        timeout=slice_timeout,
                        cancel=lambda: _checkpoint(operation_context, "等待国家代理时检查取消状态"),
                        progress_callback=report_wait,
                    )
                except TimeoutError:
                    rows, progress = plan_countries.update_country_progress(
                        account_id, country, progress, action="wait_timeout", fence=fence,
                    )
                    reporter.note(f"{country} 库存暂缺，继续其他国家后补试", stage="network")
                    continue
                rows, progress = plan_countries.update_country_progress(
                    account_id, country, progress, action="wait_end", fence=fence,
                )
                route_info = route.public_dict()
                actual_country = str(route_info.get("proxy_region") or getattr(route, "region", "") or "").upper()
                if actual_country != country:
                    raise ValueError(f"请求 {country} 出口，实际检测为 {actual_country or '未知'}，未执行该国查询；请使用支持指定国家的代理来源")
                reporter.resource("resource.acquired", message=f"已领取 {country} 查询线路", detail={**route_info, "country": country})
                reporter.stage("network", "success", f"{country} 查询线路已就绪")
                reporter.stage("plan_check", "running", f"正在查询 {country} 套餐优惠")
                _checkpoint(operation_context)
                _wait_for_rate_slot(config_snapshot, deadline_at=progress["deadline_at"],
                                    operation_context=operation_context)
                _checkpoint(operation_context)
                remaining = progress["deadline_at"] - time.time()
                if remaining < 2:
                    raise TimeoutError("国家查询总期限已到")
                rows, progress = plan_countries.update_country_progress(
                    account_id, country, progress, action="http_start", fence=fence,
                )
                remaining = progress["deadline_at"] - time.time()
                if remaining < 2:
                    raise TimeoutError("国家查询总期限已到")
                # 一轮套餐请求仍可能附带一次额度请求，两次共用剩余期限。
                # 换线也共用 Run 中已冻结的套餐请求总次数。
                answer = check_account_plan(
                    access_token, proxy=route.proxy_url, timezone_offset_min=timezone_offset_min,
                    timeout=min(timeout, remaining / 2), max_attempts=1, retry_delay=0,
                    deadline_at=progress["deadline_at"],
                )
                answer.update({key: value for key, value in route_info.items() if key not in {"proxy_used", "proxy_url"}})
            except (account_task_store.OperationLeaseLost, OperationCancelled):
                raise
            except Exception as exc:
                answer = {"ok": False, "checked_at": now_iso(), "error": sanitize_promotion_text(f"{type(exc).__name__}: {exc}")}
            finally:
                if route is not None:
                    route.release(reason=f"plan-check-{account_id}-{country}", **(
                        {"fault": True} if answer and answer.get("proxy_transport_failure") is True else {}
                    ))
            _checkpoint(operation_context, "保存国家查询结果前检查取消状态")
            state = progress["countries"][country]
            retry = (not answer.get("ok") and bool(answer.get("retryable"))
                     and answer.get("http_status") not in {401, 403, 429}
                     and state["http_attempts"] < attempts)
            delay = max(0, min(30, float(_snapshot_value(config_snapshot, "plan_check_retry_delay", 1.5)))) * state["http_attempts"] if retry else 0
            rows, progress = plan_countries.update_country_progress(
                account_id, country, progress, action="result", fence=fence,
                result=answer, retry=retry, retry_delay=min(30, delay),
            )
            records = [{**_plan_query_record(answer, phase="initial"), "country": country}]
            _record_promotion_queries(reporter, {**answer, "promotion_query_history": records})
            reporter.note(
                f"{country} 套餐查询{'成功' if answer.get('ok') else '失败，继续其他国家'}",
                stage="plan_check", level="INFO" if answer.get("ok") else "WARNING",
                detail={"country": country, "ok": bool(answer.get("ok")), "error": sanitize_promotion_text(answer.get("error"))},
            )
        if not made_progress:
            pending = [state for state in progress["countries"].values() if state["pending"]]
            if pending:
                # 领取立即超时也尊重原切片截止，轮转期间保持取消响应且不忙循环。
                wake_at = min(progress["deadline_at"], *(state["retry_not_before"] for state in pending))
                _checkpoint(operation_context, "国家补试等待时检查取消状态")
                time.sleep(max(.01, min(.25, wake_at - time.time())))
    history = [record for state in progress["countries"].values() for record in state["history"]]
    result = aggregate_country_results(rows)
    result["promotion_query_history"] = history
    plan_countries.save_country_summary(account_id, result, fence=fence)
    count = result["country_success_count"]
    message = f"国家查询完成：{count}/{len(countries)} 成功"
    if result["failed_countries"]:
        message += "；失败国家：" + "、".join(result["failed_countries"])
    reporter.stage("plan_check", "success" if result["ok"] else "failed", message)
    task_status = "partial_success" if result["plan_check_partial"] else "success" if result["ok"] else "failed"
    reporter.finish(status=task_status, message=message,
                    error=result.get("error"), result_summary=_plan_result_summary(result), validation_method="access_token")
    return result


def _interrupted_country_result(account_id: int, error_result: dict, *, fence: dict | None) -> dict:
    from core.storage.plan_countries import finish_unfinished_countries
    from core.plan_check_countries import aggregate_country_results
    rows = finish_unfinished_countries(account_id, status=error_result.get("status") or "failed", error=error_result["error"], fence=fence)
    result = aggregate_country_results(rows)
    result.update(error_result)
    result["promotion_query_history"] = [
        {"phase": "initial", "country": row["country"], "ok": row.get("status") == "success",
         "http_status": row.get("http_status"), "checked_at": row.get("checked_at")}
        for row in rows
    ]
    return result


def _log_plan_result(email: str, trigger: str, result: dict) -> None:
    if result.get("ok"):
        logger.info(
            "[Plan] 后台查询成功: %s, plan=%s, plus_promo=%s, trigger=%s",
            email,
            result.get("current_plan_type") or "unknown",
            result.get("plus_promo_kind") or "none",
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
    countries: list[str] | None = None,
) -> dict:
    account_route = None
    result = None
    reporter = _ReporterAdapter(task_id, operation_context)
    preflight_open = True
    failure_stage = "preflight"
    multi_country = bool(countries) and not str(trigger).startswith("registration")
    fence = None
    if multi_country:
        from core.storage import plan_countries
    try:
        if multi_country:
            fence = getattr(operation_context, "execution_fence", None)
        _checkpoint(operation_context)
        if multi_country:
            marked = plan_countries.mark_country_task_running(account_id, fence=fence)
        else:
            marked = db.mark_account_plan_check_running(account_id)
        if not marked:
            reporter.finish(
                status="cancelled",
                message="账号已删除或套餐查询状态已被重置",
            )
            return {"ok": False, "error": "账号已删除或套餐查询状态已被重置"}
        reporter.start(message="开始查询账号套餐")
        # 预检只覆盖本地任务/账号状态和冻结的选路配置；网络租约单独计入
        # network，避免线路申请异常被错误归到 plan_check。
        reporter.stage("preflight", "success", "套餐查询预检通过")
        preflight_open = False

        if multi_country:
            return _run_country_plan_checks(
                account_id=account_id, email=email, access_token=access_token, trigger=trigger,
                proxy=proxy, timezone_offset_min=timezone_offset_min, countries=countries,
                reporter=reporter, operation_context=operation_context,
                config_snapshot=config_snapshot, proxy_source=proxy_source, fence=fence,
            )

        from core.account_proxy import acquire_account_proxy
        _checkpoint(operation_context, "套餐查询申请线路前检查取消状态")
        route_kwargs = {
            "account_id": account_id,
            "email": email,
            "purpose": "plan-check",
            "explicit_proxy": proxy,
            "progress_callback": lambda message: reporter.note(message, stage="network"),
        }
        if operation_context is not None:
            route_kwargs["cancel"] = lambda: _checkpoint(operation_context, "套餐查询等待线路时检查取消状态")
        if isinstance(config_snapshot, dict) and "proxy_allow_reuse" in config_snapshot:
            route_kwargs["allow_reuse"] = bool(config_snapshot["proxy_allow_reuse"])
        if isinstance(config_snapshot, dict):
            route_kwargs["reuse_limit"] = int(config_snapshot.get("proxy_reuse_limit", 3))
        selected_source = proxy_source or _snapshot_value(config_snapshot, "route_source")
        if selected_source:
            route_kwargs["source"] = selected_source
        failure_stage = "network"
        reporter.stage("network", "running", "正在申请套餐查询线路")
        account_route = acquire_account_proxy(**route_kwargs)
        reporter.resource(
            "resource.acquired",
            message="已选择套餐查询线路",
            stage="network",
            detail=account_route.public_dict(),
        )
        reporter.stage("network", "success", "套餐查询线路已就绪")

        failure_stage = "plan_check"
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
        if countries == [] and not str(trigger).startswith("registration"):
            result.update(plan_check_countries=[], plan_check_partial=False)
        result.update({
            key: value
            for key, value in account_route.public_dict().items()
            if key not in {"proxy_mode", "network_route", "proxy_used"} or not result.get(key)
        })
        _record_promotion_queries(reporter, result)
        db.update_account_plan_check(acc_id=account_id, result=result)
        _log_plan_result(email, trigger, result)
        reporter.stage(
            "plan_check", "success" if result.get("ok") else "failed",
            "套餐查询成功" if result.get("ok") else "套餐查询失败",
            level="INFO" if result.get("ok") else "ERROR",
            detail={
                "http_status": result.get("http_status"),
                "current_plan_type": result.get("current_plan_type"),
                "plus_promo_kind": result.get("plus_promo_kind"),
                "account_promotions": result.get("account_promotions"),
            },
        )
        reporter.finish(
            status="success" if result.get("ok") else "failed",
            message="套餐查询成功" if result.get("ok") else "套餐查询失败",
            error=result.get("error") if not result.get("ok") else None,
            result_summary=_plan_result_summary(result),
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
        if multi_country:
            result = _interrupted_country_result(account_id, result, fence=fence)
        try:
            if multi_country:
                plan_countries.save_country_summary(account_id, result, fence=fence)
            else:
                db.update_account_plan_check(acc_id=account_id, result=result)
        except account_task_store.OperationLeaseLost:
            raise
        except Exception:
            logger.exception("[Plan] 取消状态写回失败: account_id=%s", account_id)
        if preflight_open:
            reporter.note("套餐查询在预检完成前取消", stage="preflight", level="WARNING", detail={"cancelled": True})
        reporter.finish(status="cancelled", message="套餐查询任务已取消", error=result["error"], result_summary=_plan_result_summary(result))
        return result
    except Exception as exc:
        result = {
            "ok": False,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "error": f"{type(exc).__name__}: {str(exc)[:180]}",
        }
        if multi_country:
            result = _interrupted_country_result(account_id, result, fence=fence)
        try:
            if multi_country:
                plan_countries.save_country_summary(account_id, result, fence=fence)
            else:
                db.update_account_plan_check(acc_id=account_id, result=result)
        except account_task_store.OperationLeaseLost:
            raise
        except Exception:
            logger.exception("[Plan] 写入后台查询异常状态失败: account_id=%s", account_id)
        logger.exception("[Plan] 后台查询异常: %s", email)
        reporter.stage(
            failure_stage, "failed",
            "套餐查询预检失败" if preflight_open else "套餐查询线路申请失败" if failure_stage == "network" else "套餐查询后台执行异常",
            level="ERROR", detail={"error": result["error"]},
        )
        reporter.finish(
            status="failed",
            message="套餐查询后台执行异常",
            error=result["error"],
            route=account_route.public_dict() if account_route is not None else None,
            validation_method="access_token",
            result_summary=_plan_result_summary(result),
        )
        return result
    finally:
        if account_route is not None:
            if result and not result.get("ok") and result.get("proxy_transport_failure") is True:
                account_route.release(reason=f"plan-check-{account_id}", fault=True)
            else:
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
    preflight_open = True
    try:
        if not db.mark_account_plan_check_running(account_id):
            reporter.finish(
                status="cancelled",
                message="账号已删除或套餐查询状态已被重置",
            )
            return {"ok": False, "error": "账号已删除或套餐查询状态已被重置"}
        reporter.start(message="注册完成，开始自动查询套餐")
        reporter.stage("preflight", "success", "注册后套餐查询预检通过")
        preflight_open = False
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
        _record_promotion_queries(reporter, result)
        db.update_account_plan_check(acc_id=account_id, result=result)
        _log_plan_result(str(email or "").strip(), trigger, result)
        reporter.stage(
            "plan_check", "success" if result.get("ok") else "failed",
            "注册后套餐查询成功" if result.get("ok") else "注册后套餐查询失败",
            level="INFO" if result.get("ok") else "ERROR",
            detail={
                "http_status": result.get("http_status"),
                "current_plan_type": result.get("current_plan_type"),
                "plus_promo_kind": result.get("plus_promo_kind"),
                "account_promotions": result.get("account_promotions"),
            },
        )
        reporter.finish(
            status="success" if result.get("ok") else "failed",
            message="注册后套餐查询成功" if result.get("ok") else "注册后套餐查询失败",
            error=result.get("error") if not result.get("ok") else None,
            result_summary=_plan_result_summary(result),
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
            "preflight" if preflight_open else "plan_check", "failed",
            "注册后套餐查询预检失败" if preflight_open else "注册后套餐查询异常",
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
        _ReporterAdapter(context.task_id, context).stage("preflight", "failed", "套餐查询缺少账号", level="ERROR")
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
        _ReporterAdapter(context.task_id, context).stage("preflight", "failed", error, level="ERROR")
        db.update_account_plan_check(
            acc_id=int(context.account_id),
            result={"ok": False, "status": "failed", "error": error},
        )
        context.finish(status="failed", message=error, error=error)
        return None
    with context.lease(resource_family="openai_interactive"):
        with operation_log_context(context, stage="preflight"):
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
                countries=data.get("countries") if isinstance(data.get("countries"), list) else None,
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


def _country_proxy_source(snapshot) -> str:
    """国家、线路与预算都从同一不可变配置版本派生。"""
    from core.account_proxy import normalize_proxy_source
    values = snapshot.as_dict() if callable(getattr(snapshot, "as_dict", None)) else snapshot
    configured = str(values.get("ACCOUNT_PLAN_CHECK_PROXY_MODE", "direct") or "direct")
    legacy = str(values.get("ACCOUNT_ACTION_PROXY_MODE", "registration") or "registration")
    sources = getattr(snapshot, "sources", {})
    if sources.get("ACCOUNT_PLAN_CHECK_PROXY_MODE", "default") == "default" and configured == "direct" and normalize_proxy_source(legacy) != "registration":
        configured = legacy
    mode = normalize_proxy_source(configured)
    if mode != "registration":
        return mode
    registration = str(values.get("REGISTRATION_PROXY_MODE", "pool") or "none").lower()
    if registration in {"none", "direct"}:
        return "direct"
    if registration == "pool":
        return "pool"
    if registration in {"1024", "1024proxy", "provider"}:
        return "provider:1024proxy"
    raise ValueError("无法解析冻结的注册代理来源")


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
    country_data = {}
    snapshot_kwargs = {"config_snapshot_provider": get_config_snapshot}
    if not str(trigger).startswith("registration"):
        from config.countries import normalize_plan_check_countries
        snapshot = get_config_snapshot()
        values = snapshot.as_dict() if callable(getattr(snapshot, "as_dict", None)) else snapshot
        country_data["countries"] = normalize_plan_check_countries(values.get("PLAN_CHECK_COUNTRIES", []))
        source = _country_proxy_source(snapshot)
        snapshot_kwargs = {"config_snapshot": snapshot}
    else:
        source = _captured_proxy_source("plan-check")
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
            **country_data,
            "timezone_offset_min": str(timezone_offset_min or "-"),
            # This is a route mode, never a proxy URL.  Capturing the
            # effective source also preserves the legacy registration-mode
            # fallback while preventing a queued Run from changing route
            # halfway through execution.
            "proxy_source": source,
        },
        **snapshot_kwargs,
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
    account = db.get_account(account_id)
    if not account:
        return {"accepted": False, "busy": False, "error": "账号不存在"}
    if db.account_is_deactivated(account):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已废号，不能查询套餐",
        }
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
