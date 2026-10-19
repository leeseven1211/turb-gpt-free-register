# -*- coding: utf-8 -*-
"""
注册任务服务层：
    - 线程池并发执行 run_registration
    - 每个任务在 data/registration_jobs.json 里有一条记录
    - 每个任务的日志写到 data/logs/<job_uuid>.log，便于 Web UI 实时尾巴

使用：
    submit_registration(email_source="outlook", count=5)
    → 创建 5 个任务，丢入线程池，立即返回 [job_dict, ...]
"""
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core import codex_retry_service, db, task_run_log
from core.operations import task_gateway as account_task_store
from core.registration_postprocess import summarize_postprocess, decide_recovery
from core.remail_client import RemailOrderUncertain
from core.task_errors import REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES

logger = logging.getLogger(__name__)

# 全局线程池，最大并发数（WebUI 每次提交时可按最新 workers 重建）
_DEFAULT_MAX_WORKERS = 4
_MIN_MAX_WORKERS = 1
_MAX_MAX_WORKERS = 16
_executor: ThreadPoolExecutor | None = None
_executor_workers = _DEFAULT_MAX_WORKERS
_executor_generation = 0
_retired_executors: list[ThreadPoolExecutor] = []
_executor_lock = threading.RLock()

_STOP_EVENTS: dict[int, threading.Event] = {}
_ACTIVE_JOBS: set[int] = set()
_STOP_LOCK = threading.Lock()
_THREAD_CTX = threading.local()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_REGISTRATION_DRIVER_LABELS = {
    "protocol": "本地优化 Protocol",
    "protocol_oss": "开源 Protocol",
    "roxy": "本地 Roxy",
    "roxy_oss": "开源 Roxy",
}
_REGISTRATION_DRIVER_HINTS = {
    "protocol": "本项目优化实现；认证方式按本批密码配置执行。",
    "protocol_oss": "上游流程固定使用邮箱验证码和密码，后续账号处理仍走本地服务。",
    "roxy": "使用本地 RoxyBrowser 注册与账号后处理流程。",
    "roxy_oss": "使用固定上游页面识别与表单辅助，认证提交、任务恢复和账号后处理沿用本地服务。",
}
_REGISTRATION_DRIVER_ALIASES = {
    "api": "protocol",
    "http": "protocol",
    "roxybrowser": "roxy",
    "fingerprint": "roxy",
    "browser": "roxy",
}


def registration_driver_choices() -> list[dict[str, str]]:
    """返回注册页使用的 canonical driver 名称和标签。"""
    return [
        {"value": value, "label": label, "description": _REGISTRATION_DRIVER_HINTS[value]}
        for value, label in _REGISTRATION_DRIVER_LABELS.items()
    ]


def configured_registration_driver() -> str:
    """读取并归一化全局默认 driver，兼容历史别名。"""
    from config import roxybrowser as roxy_cfg

    raw = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    return _REGISTRATION_DRIVER_ALIASES.get(raw, raw)


def validate_registration_driver(value: object) -> str:
    """校验注册批次显式选择的 canonical driver。"""
    driver = str(value or "").strip().lower()
    if driver not in _REGISTRATION_DRIVER_LABELS:
        raise ValueError("registration_driver 只能是 protocol、protocol_oss、roxy 或 roxy_oss")
    return driver


def codex_driver_for_registration(options: dict | None = None) -> str:
    """按注册任务快照解析当前支持的 Codex OAuth 驱动。"""
    from config import codex as codex_cfg

    values = options if isinstance(options, dict) else {}
    driver = str(
        values.get("codex_driver")
        or getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "same_as_registration")
        or "same_as_registration"
    ).strip().lower()
    if driver == "same_as_registration":
        registration_driver = str(
            values.get("registration_driver") or configured_registration_driver()
        ).strip().lower()
        registration_driver = _REGISTRATION_DRIVER_ALIASES.get(registration_driver, registration_driver)
        driver = {
            "protocol_oss": "protocol",
            "roxy_oss": "roxy",
        }.get(registration_driver, registration_driver)
    driver = {
        "api": "protocol",
        "http": "protocol",
        "roxybrowser": "roxy",
        "fingerprint": "roxy",
        "browser": "roxy",
    }.get(driver, driver)
    if driver not in {"protocol", "roxy"}:
        raise ValueError(f"注册后的 Codex OAuth 不支持 driver {driver}")
    return driver


def _apply_registration_driver_snapshot(snapshot: dict[str, object], driver: str) -> dict[str, object]:
    """把所选注册驱动及其固有认证要求写入任务快照。"""
    canonical = _REGISTRATION_DRIVER_ALIASES.get(str(driver or "").strip().lower(), str(driver or "").strip().lower())
    snapshot["registration_driver"] = canonical
    if canonical == "protocol_oss":
        snapshot["password_enabled"] = True
        snapshot["password_mode"] = "password"
    return snapshot


def registration_config_snapshot() -> dict[str, object]:
    """Return the non-sensitive registration choices captured per job.

    A registration task must keep the choices it was submitted with even if
    the WebUI configuration is changed while the worker is running.
    """
    from config import codex as codex_cfg
    from config import register as register_cfg
    from config import roxybrowser as roxy_cfg
    from config import twofa as twofa_cfg

    auth_mode = str(getattr(register_cfg, "REGISTRATION_AUTH_MODE", "otp") or "otp").strip().lower()
    if auth_mode not in {"otp", "password"}:
        auth_mode = "otp"
    registration_driver = str(getattr(roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
    snapshot = {
        "registration_driver": registration_driver,
        # 注册国家在入队时冻结；worker 只按业务国家向统一池领取，
        # 不受代理池默认国家或排队期间配置修改的影响。
        "proxy_country": _registration_proxy_country_for_job(None),
        "password_enabled": auth_mode == "password",
        "password_mode": auth_mode,
        "twofa_enabled": bool(getattr(twofa_cfg, "ENABLE_2FA", False)),
        # Store the public normalized mode in the job snapshot.  Older .env
        # values such as protocol_direct remain accepted by config.twofa but
        # must not leak into downstream registration validators.
        "twofa_driver": twofa_cfg.get_twofa_mode(),
        "codex_enabled": bool(getattr(codex_cfg, "ENABLE_CODEX_AUTO", False)),
        "codex_driver": str(getattr(codex_cfg, "CODEX_OAUTH_DRIVER", "same_as_registration") or "same_as_registration").strip().lower(),
        "plan_check_enabled": bool(getattr(register_cfg, "REGISTRATION_PLAN_CHECK_ENABLED", True)),
    }
    return _apply_registration_driver_snapshot(snapshot, registration_driver)


def _normalize_registration_country(value: object) -> str:
    """归一化一个历史任务中可能保存的出口国家。"""
    country = str(value or "").strip().upper()
    if not country:
        return ""
    try:
        from config.countries import ISO_3166_ALPHA2

        return country if country in ISO_3166_ALPHA2 else ""
    except Exception:
        # 配置/测试兼容入口不应因为国家目录不可用而阻断重跑；两位字母
        # 仍是旧任务实际出口字段可安全恢复的最小格式。
        return country if len(country) == 2 and country.isalpha() else ""


def _snapshot_registration_country(snapshot: object) -> str:
    if not isinstance(snapshot, dict):
        return ""
    # proxy_country 是当前快照字段；其余名称只为兼容早期实验快照，不能
    # 覆盖已经存在的当前字段。
    for key in ("proxy_country", "registration_proxy_country", "country"):
        country = _normalize_registration_country(snapshot.get(key))
        if country:
            return country
    return ""


def _historical_registration_country(job: dict | None) -> str:
    """从旧任务记录恢复实际出口国家，不读取当前配置。"""
    if not isinstance(job, dict):
        return ""
    containers: list[dict] = [job]
    raw_data = job.get("data")
    if isinstance(raw_data, dict):
        containers.append(raw_data)
        for key in ("result", "route", "proxy", "proxy_info", "network"):
            nested = raw_data.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
    # proxy_region 是当前任务字段；exitcountry 等名称覆盖历史导出/供应商
    # 结果字段。按实际出口优先于旧配置字段，避免把旧 provider/source 当成
    # 国家选择。
    for container in containers:
        for key in (
            "proxy_region",
            "exitcountry",
            "exit_country",
            "proxy_exit_country",
            "proxy_country",
            "proxy_country_code",
        ):
            country = _normalize_registration_country(container.get(key))
            if country:
                return country
    return ""


def _registration_proxy_country_for_job(job: dict | None) -> str:
    """返回注册任务领取代理时应使用的冻结国家。

    新任务由 config_snapshot.proxy_country 固定国家。历史任务没有该字段时
    先恢复已经记录的实际线路国家，最后才使用当前注册国家。
    """
    snapshot = None
    if isinstance(job, dict):
        snapshot = job.get("config_snapshot")
        if not isinstance(snapshot, dict):
            raw_data = job.get("data")
            if isinstance(raw_data, dict):
                snapshot = raw_data.get("config_snapshot")
    country = _snapshot_registration_country(snapshot)
    if country:
        return country
    country = _historical_registration_country(job)
    if country:
        return country
    from config import register as register_cfg

    country = _normalize_registration_country(register_cfg.REGISTRATION_COUNTRY)
    if not country:
        raise ValueError("请在注册主链路选择有效的注册国家")
    return country


def registration_options_for_job(job: dict | None) -> dict[str, object]:
    """Read a job snapshot, falling back to current config for old jobs."""
    if isinstance(job, dict):
        snapshot = job.get("config_snapshot")
        if isinstance(snapshot, dict):
            options = dict(snapshot)
            # 旧任务的快照可能没有国家，但已有任务行记录实际出口；将该
            # 事实带入重跑子任务，避免重跑时误跟随新的池默认国家。
            if not _snapshot_registration_country(options):
                options["proxy_country"] = _registration_proxy_country_for_job(job)
            return options
        raw_data = job.get("data")
        if isinstance(raw_data, dict) and isinstance(raw_data.get("config_snapshot"), dict):
            options = dict(raw_data["config_snapshot"])
            if not _snapshot_registration_country(options):
                options["proxy_country"] = _registration_proxy_country_for_job(job)
            return options
    options = registration_config_snapshot()
    if isinstance(job, dict):
        options["proxy_country"] = _registration_proxy_country_for_job(job)
    return options


# Workflow B owns these facts.  This adapter only translates the existing job
# progress vocabulary into one-way checkpoints; it never creates a parallel
# state store or guesses an Attempt from an email address.
_PROGRESS_CHECKPOINTS = {
    ("email", "success"): "email_claimed",
    ("auth_redirect", "running"): "auth_started",
    ("auth_redirect", "success"): "auth_started",
    # running 只表示进入密码阶段；密码输入完成后的 prepared/started 事实由
    # password_auth 的回调持久化。这里提前推进到 request_started 会把“页面已
    # 进入”误报成“请求已发出”。
    ("password", "running"): "auth_started",
    ("password", "success"): "password_confirmed",
    ("login_password", "running"): "auth_started",
    ("login_password", "success"): "password_confirmed",
    ("email_otp", "running"): "otp_started",
    ("email_otp", "success"): "otp_confirmed",
    ("profile", "running"): "account_request_started",
    ("profile", "success"): "account_confirmed",
    ("token", "success"): "token_obtained",
}


class StopRequested(RuntimeError):
    """用户手动停止注册任务。"""


def _activate_job(job_id: int) -> None:
    _THREAD_CTX.job_id = int(job_id)
    _THREAD_CTX.debug_token = None
    # A worker thread can be reused by the executor.  Never leak a previous
    # registration's Attempt/Run identifiers into the next task.
    _THREAD_CTX.attempt_id = None
    _THREAD_CTX.run_id = None
    _THREAD_CTX.operation_run_id = None
    _THREAD_CTX.execution_id = None
    _THREAD_CTX.route_attempt_no = None
    _THREAD_CTX.step_instances = {}
    _THREAD_CTX.progress_context = None
    try:
        from core import registration_debug

        debug_job = db.get_job(int(job_id)) or {}
        _THREAD_CTX.debug_token = registration_debug.activate_for_job(debug_job)
    except Exception:
        logger.exception("[Job %s] 启动注册调试记录器失败；注册流程继续执行", job_id)
    try:
        from core import sms_provider

        job = db.get_job(int(job_id)) or {}
        sms_provider.set_sms_batch_context(str(job.get("batch_id") or f"job-{job_id}"))
    except Exception:
        logger.exception("[Job %s] 设置接码批次上下文失败", job_id)
    with _STOP_LOCK:
        _STOP_EVENTS.setdefault(int(job_id), threading.Event())
        _ACTIVE_JOBS.add(int(job_id))


def _deactivate_job(job_id: int) -> None:
    try:
        from core import registration_debug

        final_job = db.get_job(int(job_id)) or {}
        registration_debug.deactivate_for_job(
            getattr(_THREAD_CTX, "debug_token", None),
            status=str(final_job.get("status") or ""),
        )
    except Exception:
        logger.exception("[Job %s] 收口注册调试记录器失败", job_id)
    with _STOP_LOCK:
        _STOP_EVENTS.pop(int(job_id), None)
        _ACTIVE_JOBS.discard(int(job_id))
    try:
        delattr(_THREAD_CTX, "job_id")
    except Exception:
        pass
    try:
        delattr(_THREAD_CTX, "debug_token")
    except Exception:
        pass
    for attr in ("attempt_id", "run_id", "operation_run_id", "execution_id", "route_attempt_no", "step_instances", "progress_context"):
        try:
            delattr(_THREAD_CTX, attr)
        except Exception:
            pass
    try:
        from core import sms_provider

        sms_provider.clear_sms_batch_context()
    except Exception:
        pass
    task_run_log.clear_current_context()


def is_job_worker_active(job_id: int) -> bool:
    """确认当前进程的原任务 worker 是否尚未完成收口。"""
    with _STOP_LOCK:
        return int(job_id) in _ACTIVE_JOBS


def is_stop_requested(job_id: int | None = None) -> bool:
    if job_id is None:
        job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return False
    with _STOP_LOCK:
        ev = _STOP_EVENTS.get(int(job_id))
        if ev and ev.is_set():
            return True
    job = db.get_job(int(job_id))
    return bool(job and job.get("status") in ("stopping", "stopped", "cancelled"))


def check_stop_requested() -> None:
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if is_stop_requested(job_id):
        raise StopRequested(f"任务 #{job_id} 已被用户手动停止")


def _ensure_registration_run_context(job: dict | None) -> dict | None:
    """Bind the current worker to B's Attempt/Run when the job carries it.

    Older unit tests and CLI callers use lightweight job dictionaries without
    ``attempt_id``.  Those callers retain the old behavior and do not trigger a
    database import.  Real jobs created by ``core.storage.jobs`` always carry
    the field and therefore get durable lifecycle facts.
    """
    if not isinstance(job, dict) or "attempt_id" not in job:
        return None
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return None
    try:
        from core.storage import registration

        attempt_id = job.get("attempt_id")
        attempt = (
            registration.get_attempt(int(attempt_id))
            if attempt_id is not None
            else registration.ensure_attempt_for_job(int(job_id))
        )
        if not attempt:
            attempt = registration.ensure_attempt_for_job(int(job_id))
        attempt_id = int(attempt["id"])
        execution_id = str(job.get("execution_id") or uuid.uuid4())
        run = registration.start_run(
            attempt_id,
            job_id=int(job_id),
            action_type=str(job.get("job_type") or job.get("action_type") or "registration"),
            execution_id=execution_id,
            worker_pid=os.getpid(),
            initial_status="running",
            started_at=datetime.now().astimezone(),
        )
        _THREAD_CTX.attempt_id = attempt_id
        _THREAD_CTX.run_id = int(run["id"]) if run.get("id") is not None else None
        _THREAD_CTX.execution_id = execution_id
        return {"attempt_id": attempt_id, "run_id": getattr(_THREAD_CTX, "run_id", None), "execution_id": execution_id}
    except Exception:
        # Storage availability must not turn compatibility/test jobs into a
        # second failure path.  The job's legacy lifecycle remains authoritative
        # until the next worker/recovery pass can persist the B facts.
        logger.exception("[Job %s] 绑定 RegistrationAttempt/Run 失败，沿用旧任务生命周期", job_id)
        return None


def _bind_progress_route_context(route_attempt_no: int | None) -> None:
    """固定当前线路上下文，并在换线时丢弃旧阶段实例。"""
    try:
        route_no = max(1, int(route_attempt_no or 1))
    except (TypeError, ValueError):
        route_no = 1
    previous = getattr(_THREAD_CTX, "route_attempt_no", None)
    if previous is not None and int(previous) != route_no:
        _THREAD_CTX.step_instances = {}
    _THREAD_CTX.route_attempt_no = route_no
    if not isinstance(getattr(_THREAD_CTX, "step_instances", None), dict):
        _THREAD_CTX.step_instances = {}
    _THREAD_CTX.progress_context = {
        "route_attempt_no": route_no,
        "operation_run_id": getattr(_THREAD_CTX, "operation_run_id", None),
    }


def _progress_step_instance(stage: str, state: str) -> str:
    """同一阶段生命周期复用实例，重新进入阶段才创建新实例。"""
    stage_key = str(stage or "event").strip().lower()
    state_key = str(state or "running").strip().lower()
    instances = getattr(_THREAD_CTX, "step_instances", None)
    if not isinstance(instances, dict):
        instances = {}
        _THREAD_CTX.step_instances = instances
    current = instances.get(stage_key)
    terminal_states = {"success", "failed", "skipped", "stopped"}
    if not current or (state_key == "running" and current.get("state") in terminal_states):
        current = {"id": uuid.uuid4().hex, "state": state_key}
        instances[stage_key] = current
    else:
        current["state"] = state_key
    return str(current["id"])


def _persist_job_progress(
    job_id: int,
    stage: str,
    state: str = "running",
    detail: str | None = None,
    *,
    route_attempt_no: int | None = None,
    operation_run_id: int | None = None,
    step_instance_id: str | None = None,
) -> None:
    """统一把不可变 Run/线路/步骤实例上下文写入进度事件。"""
    fixed_context = getattr(_THREAD_CTX, "progress_context", None)
    fixed_context = fixed_context if isinstance(fixed_context, dict) else {}
    route_no = route_attempt_no if route_attempt_no is not None else fixed_context.get("route_attempt_no")
    if route_no is None:
        route_no = getattr(_THREAD_CTX, "route_attempt_no", None)
    operation_run_id = operation_run_id if operation_run_id is not None else fixed_context.get("operation_run_id")
    if operation_run_id is None:
        operation_run_id = getattr(_THREAD_CTX, "operation_run_id", None)
    if route_no is None:
        db.update_job_progress(int(job_id), stage, state=state, detail=detail)
        return
    step_instance_id = step_instance_id or _progress_step_instance(stage, state)
    db.update_job_progress(
        int(job_id), stage, state=state, detail=detail,
        route_attempt_no=int(route_no), step_instance_id=step_instance_id,
        operation_run_id=operation_run_id,
    )


def _advance_registration_checkpoint(stage: str, state: str, detail: str | None = None) -> None:
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    if attempt_id is None:
        return
    checkpoint = _PROGRESS_CHECKPOINTS.get((str(stage or "").strip().lower(), str(state or "").strip().lower()))
    if checkpoint is None:
        return
    try:
        from core.storage import registration

        registration.advance_checkpoint(
            int(attempt_id),
            checkpoint,
            run_id=getattr(_THREAD_CTX, "run_id", None),
            job_id=getattr(_THREAD_CTX, "job_id", None),
            execution_id=getattr(_THREAD_CTX, "execution_id", None),
            message=detail,
        )
    except Exception:
        # Checkpoint writes are additive audit facts.  A transient storage
        # outage should be visible in logs but cannot erase the legacy task.
        logger.exception("[Job %s] 写入 Registration checkpoint 失败: %s/%s", getattr(_THREAD_CTX, "job_id", None), stage, state)


def _registration_request_unknown_facts(result: dict | None) -> dict[str, object]:
    """只保存注册驱动的固定原因码和明确响应布尔值。"""
    facts: dict[str, object] = {"outcome": "request_unknown"}
    if not isinstance(result, dict):
        return facts
    cause_code = result.get("cause_code")
    if isinstance(cause_code, str) and cause_code in REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES:
        facts["cause_code"] = cause_code
    if type(result.get("register_response_confirmed")) is bool:
        facts["register_response_confirmed"] = result["register_response_confirmed"]
    return facts


def _mark_registration_request_unknown(message: str, *, facts: dict[str, object] | None = None) -> None:
    """Persist an ambiguous password submit without allowing a fresh registration."""
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    if attempt_id is None:
        return
    try:
        from core.storage import registration

        safe_facts = _registration_request_unknown_facts(facts)
        registration.mark_request_unknown(
            int(attempt_id),
            target="identity",
            identity_response_confirmed=safe_facts.get("register_response_confirmed") is True,
            run_id=getattr(_THREAD_CTX, "run_id", None),
            job_id=getattr(_THREAD_CTX, "job_id", None),
            execution_id=getattr(_THREAD_CTX, "execution_id", None),
            message=str(message or "密码提交结果待确认")[:1000],
            detail={"next_action": "reconcile_session", **safe_facts},
        )
    except Exception:
        logger.exception("[Job %s] 写入密码提交 request_unknown 失败", getattr(_THREAD_CTX, "job_id", None))


def _mark_registration_manual_reconcile(message: str, *, detail: dict | None = None) -> None:
    """Persist a remote-existing/ambiguous registration for operator reconciliation."""
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    if attempt_id is None:
        return
    try:
        from core.storage import registration

        registration.mark_manual_reconcile(
            int(attempt_id),
            run_id=getattr(_THREAD_CTX, "run_id", None),
            job_id=getattr(_THREAD_CTX, "job_id", None),
            execution_id=getattr(_THREAD_CTX, "execution_id", None),
            message=str(message or "远端账号需要人工对账")[:1000],
            detail=detail or {"next_action": "account_reconcile"},
        )
    except Exception:
        logger.exception("[Job %s] 写入 manual_reconcile 失败", getattr(_THREAD_CTX, "job_id", None))


def registration_result_status(result: dict | None) -> str:
    """注册未确认完成一律按失败收口，远端未知事实另存于 Attempt。"""
    if not isinstance(result, dict):
        return "failed"
    if "core_persisted" in result:
        # 待验证账号也有 account_id，浏览器拿到的 Token 仍可能只在内存中。
        # 新驱动必须明确确认核心落库，不能用这两个字段推断持久化成功。
        return "success" if (
            result.get("core_persisted") is True
            and result.get("account_id")
            and not result.get("registration_pending")
        ) else "failed"
    # 兼容尚未提供明确落库事实的外部驱动与历史结果。
    if not result.get("registration_pending") and result.get("account_id") and str(result.get("access_token") or "").strip():
        return "success"
    if result.get("manual_reconcile") or result.get("request_unknown") or result.get("registration_pending"):
        return "failed"
    return "success" if result.get("success") or result.get("registration_success") else "failed"


def _persisted_result_error(result: dict | None, message: object) -> str:
    """Keep a driver's stable error code visible to the task projection.

    Legacy jobs persist one error string while the driver returns structured
    fields.  Prefixing the safe code lets the unified operation projection
    classify the task consistently without storing page bodies or credentials.
    """
    text = str(message or "").strip()
    code = str((result or {}).get("error_code") or "").strip() if isinstance(result, dict) else ""
    if not code and isinstance(result, dict) and result.get("request_unknown"):
        code = "request_unknown"
    if code and code.casefold() not in text.casefold():
        text = f"{code}: {text}" if text else code
    return text[:500]


def _confirmed_postprocess_email_unusable(result: dict | None) -> dict | None:
    """只接受 OAuth 明确返回的永久失效标志，不能从普通失败文案推断。"""
    if not isinstance(result, dict):
        return None
    candidates = (result, result.get("codex"))
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("email_permanently_unusable") is True:
            return candidate
    return None


def _finish_registration_run(status: str, *, error_message: str | None = None, result_summary: dict | None = None) -> None:
    run_id = getattr(_THREAD_CTX, "run_id", None)
    if run_id is None:
        return
    try:
        from core.storage import registration

        registration.finish_run(
            int(run_id),
            status=str(status or "failed"),
            error_code="request_unknown" if status == "request_unknown" else None,
            error_message=error_message,
            result_summary=result_summary or {},
        )
    except Exception:
        logger.exception("[Job %s] 收口 RegistrationRun 失败: run_id=%s", getattr(_THREAD_CTX, "job_id", None), run_id)
        return
    # 旧 job 先终态化，RegistrationRun 后收口；再同步一次才能把安全原因
    # 带到统一任务中心的当前任务与历史 Run。
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if job_id is not None:
        try:
            from core import operation_task_store

            operation_task_store.sync_registration_job(int(job_id))
        except Exception:
            logger.exception("[Job %s] 同步 RegistrationRun 原因到任务中心失败", job_id)


def _mark_registration_result(result: dict | None) -> None:
    """Advance Attempt after a driver result without changing legacy status rules."""
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    if attempt_id is None or not isinstance(result, dict):
        return
    checkpoint = "completed" if result.get("postprocess_success") and not result.get("next_actions") else "postprocessing"
    try:
        from core.storage import registration

        registration.advance_checkpoint(
            int(attempt_id),
            checkpoint,
            run_id=getattr(_THREAD_CTX, "run_id", None),
            job_id=getattr(_THREAD_CTX, "job_id", None),
            execution_id=getattr(_THREAD_CTX, "execution_id", None),
            message="注册核心与后处理结果已记录" if checkpoint == "completed" else "注册核心成功，仍有后处理动作",
            detail={
                "next_actions": result.get("next_actions") or [],
                "account_readiness": result.get("account_readiness"),
            },
            target_status="completed" if checkpoint == "completed" else "account_available",
        )
    except Exception:
        logger.exception("[Job %s] 写入注册结果 checkpoint 失败", getattr(_THREAD_CTX, "job_id", None))


def registration_fact_context() -> dict[str, int | str | None]:
    """Expose the current B identifiers to registration drivers."""
    return {
        "attempt_id": getattr(_THREAD_CTX, "attempt_id", None),
        "run_id": getattr(_THREAD_CTX, "run_id", None),
        "execution_id": getattr(_THREAD_CTX, "execution_id", None),
        "job_id": getattr(_THREAD_CTX, "job_id", None),
    }


def bind_registration_email(
    email: str,
    *,
    email_source: str | None = None,
    root_job_id: int | None = None,
) -> None:
    """Refresh B's Attempt email snapshot after the provider lease is claimed."""
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    job_id = getattr(_THREAD_CTX, "job_id", None)
    address = str(email or "").strip()
    if attempt_id is None or not job_id or not address:
        return
    try:
        from core.storage import registration

        # ``create_attempt`` is idempotent for the original root job. 重跑子任务
        # 必须继续写回同一个 Attempt，不能各自声明一份邮箱租约。
        root_id = int(root_job_id or job_id)
        registration.create_attempt(
            address,
            email_source=email_source,
            root_job_id=root_id,
            data={"email_lease_id": f"root:{root_id}:{address.lower()}"},
        )
    except Exception:
        logger.exception("[Job %s] 绑定 Attempt 邮箱租约快照失败", job_id)


def persist_registration_core(
    *,
    email: str,
    access_token: str,
    totp_secret: str | None = None,
    extra: dict | None = None,
    chatgpt_session: dict | None = None,
    email_source: str | None = None,
    proxy_used: str | None = None,
) -> int:
    """Save the core account and mirror it into B's Attempt atomically where available."""
    from core.account_export import persist_account_core

    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    recovered_core = None
    if attempt_id is not None:
        from core.storage import registration

        attempt = registration.get_attempt(int(attempt_id)) or {}
        if attempt.get("checkpoint") in {"failed", "manual_reconcile"} or getattr(_THREAD_CTX, "execution_id", None):
            # 先在同一事务中核验恢复身份和执行实例，再写原账号 Token。
            # 拒绝必须向驱动抛出，不能先写兼容账号后再吞掉校验异常。
            recovered_core = registration.persist_core_account(
                int(attempt_id), access_token=access_token,
                account={"id": attempt.get("account_id"), "email": email,
                         **({"chatgpt_session": chatgpt_session} if chatgpt_session is not None else {}),
                         **({"totp_secret": totp_secret} if totp_secret else {}),
                         **({"email_source": email_source} if email_source else {}),
                         **({"proxy_used": proxy_used} if proxy_used else {}),
                         **({"extra_json": json.dumps(extra, ensure_ascii=False)} if extra else {})},
                run_id=getattr(_THREAD_CTX, "run_id", None),
                job_id=getattr(_THREAD_CTX, "job_id", None),
                execution_id=getattr(_THREAD_CTX, "execution_id", None),
            )

    # 核心恢复确认后沿用原入口补齐账号元数据并收口邮箱素材。
    account_id = persist_account_core(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        extra=extra,
        chatgpt_session=chatgpt_session,
        email_source=email_source,
        proxy_used=proxy_used,
    )
    if attempt_id is not None:
        try:
            from core.storage import registration

            payload = dict(extra or {})
            payload.update({"id": account_id, "email": email})
            if chatgpt_session is not None:
                payload["chatgpt_session"] = chatgpt_session
            result = recovered_core
            if result is None:
                result = registration.persist_core_account(
                    int(attempt_id),
                    access_token=access_token,
                    account=payload,
                    run_id=getattr(_THREAD_CTX, "run_id", None),
                    job_id=getattr(_THREAD_CTX, "job_id", None),
                    execution_id=getattr(_THREAD_CTX, "execution_id", None),
                )
            account_id = int(result.get("account_id") or account_id)
            # The account is now durable; any remaining work is explicitly
            # post-processing and can be recovered without re-registering.
            try:
                registration.advance_checkpoint(
                    int(attempt_id),
                    "postprocessing",
                    run_id=getattr(_THREAD_CTX, "run_id", None),
                    job_id=getattr(_THREAD_CTX, "job_id", None),
                    execution_id=getattr(_THREAD_CTX, "execution_id", None),
                    message="核心账号已持久化，进入独立后处理",
                )
            except Exception:
                logger.exception("[Job %s] 标记后处理 checkpoint 失败", getattr(_THREAD_CTX, "job_id", None))
        except Exception:
            logger.exception("[Job %s] 核心账号已写入兼容表，但 Attempt 核心持久化失败", getattr(_THREAD_CTX, "job_id", None))
    report_registered_account(account_id)
    return account_id


def recover_registration_attempts(*, limit: int = 100) -> list[dict]:
    """Recover interrupted Runs and return storage-neutral decisions.

    This is intentionally an adapter boundary: it does not mutate leases or
    create jobs.  Callers can schedule the returned action on the same Attempt.
    """
    from core.storage import registration

    registration.recover_interrupted_runs()
    decisions = []
    for attempt in registration.list_attempts(limit=limit):
        snapshot = {
            "checkpoint": attempt.get("checkpoint"),
            "remote_identity_state": attempt.get("remote_identity_state"),
            "remote_account_state": attempt.get("remote_account_state"),
            "local_account_state": attempt.get("local_account_state"),
            "target_status": attempt.get("target_status"),
            "email_resume_capability": (attempt.get("data") or {}).get("email_resume_capability", "manual_only"),
            "has_password": bool((attempt.get("data") or {}).get("has_password")),
            "has_access_token": bool((attempt.get("data") or {}).get("has_access_token")),
            "account_id": attempt.get("account_id"),
            "active_execution": bool(attempt.get("active_execution_id")),
        }
        decisions.append({"attempt": attempt, "decision": decide_recovery(snapshot).as_dict()})
    return decisions


def report_job_progress(stage: str, state: str = "running", detail: str | None = None) -> None:
    """注册驱动调用的轻量进度上报；CLI 场景没有 job_id 时自动忽略。"""
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        _advance_registration_checkpoint(stage, state, detail)
        return
    try:
        from core import registration_debug

        registration_debug.update_current_stage(stage, state=state, detail=detail)
    except Exception:
        logger.exception("[Job %s] 写入调试阶段标记失败: stage=%s state=%s", job_id, stage, state)
    try:
        _persist_job_progress(int(job_id), stage, state=state, detail=detail)
    except Exception:
        logger.exception("[Job %s] 写入进度失败: stage=%s state=%s", job_id, stage, state)
    _advance_registration_checkpoint(stage, state, detail)


def report_job_otp_evidence(
    *,
    request_kind: str | None = None,
    ui_ack: str | None = None,
    detail: str | None = None,
    failure_code: str | None = None,
) -> None:
    """Persist only redacted OTP delivery evidence for the active job."""
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return
    try:
        db.record_job_otp_evidence(
            int(job_id),
            request_kind=request_kind,
            ui_ack=ui_ack,
            detail=detail,
            failure_code=failure_code,
        )
    except Exception:
        logger.exception("[Job %s] 写入 OTP 证据失败", job_id)


def report_registered_account(account_id: int) -> None:
    """注册主体一旦落库，立即把账号绑定到当前任务。

    2FA、Codex 或 WebUI 进程随后中断时，启动恢复逻辑仍能定位并保留这个账号。
    CLI 场景没有 job_id 时自动忽略。
    """
    job_id = getattr(_THREAD_CTX, "job_id", None)
    if not job_id:
        return
    try:
        db.update_job(int(job_id), account_id=int(account_id))
    except Exception:
        logger.exception("[Job %s] 绑定注册账号失败: account_id=%s", job_id, account_id)


def _append_job_log(job_id: int, message: str) -> None:
    try:
        job = db.get_job(job_id)
        log_file = job.get("log_file") if job else None
        if not log_file:
            return
        task_run_log.append(
            log_file,
            level="WARNING",
            message=message,
            task_id=int(job_id),
            stage="cancelling",
            event_type="run.cancel_requested",
        )
    except Exception:
        pass


def _random_display_name() -> str:
    """生成符合 OpenAI 限制的英文字母显示名。"""
    from core.name_samples import random_display_name

    return random_display_name()


def _release_rejected_batch_email(email: str, *, batch_id: str, job_id: int) -> None:
    """释放本次领取但已被批次去重拒绝的邮箱租约。"""
    try:
        from core.email_provider import release_email

        release_email(
            email,
            status="available",
            note=f"注册批次 {batch_id} 已使用该邮箱，任务 #{job_id} 改领新邮箱",
        )
    except Exception:
        logger.exception(
            "[Service] 释放批次重复邮箱失败: batch_id=%s job_id=%s email=%s",
            batch_id,
            job_id,
            email,
        )


def _prepare_registration_args(
    email_source: str | None = None,
    *,
    batch_id: str | None = None,
    job_id: int | None = None,
    owner_kind: str | None = None,
    owner_id: str | int | None = None,
    acquisition_id: str | None = None,
) -> tuple[str, str, str]:
    """复用 CLI 的默认规则，为旧 Web 任务入口补齐注册参数。"""
    # 用模块属性读，支持 WebUI 热加载
    from config import register as _r, email as _e
    from core.email_provider import acquire_email
    from core.profile_utils import generate_random_birthday

    email = str(getattr(_r, "REGISTER_EMAIL", "") or "").strip()
    name = str(getattr(_r, "REGISTER_NAME", "") or "").strip()
    # WebUI/配置里有时会把空值存成 "-"，这不是合法 OpenAI 显示名，按空处理并自动生成
    if name in {"-", "—", "无", "空", "none", "None", "null", "NULL"}:
        name = ""

    if not name:
        # 手动模式也自动生成显示名，减少配置负担
        name = _random_display_name()

    birthday = generate_random_birthday()

    # 邮箱领取会把池状态置为 used，因此放在所有其他准备逻辑之后。
    # 同一注册批次的 claim 历史即使任务失败也保留，避免释放回池的邮箱被批次内
    # 后续任务再次领取。重复候选暂时保持租约，先领取到新地址后再释放，避免本地
    # 邮箱池按 id 排序时反复拿到同一候选。
    normalized_batch_id = str(batch_id or "").strip()
    rejected: list[str] = []
    rejected_keys: set[str] = set()
    try:
        if email:
            if normalized_batch_id and not db.claim_registration_batch_email(
                normalized_batch_id,
                email,
                job_id=job_id,
                email_source=email_source,
            ):
                raise RuntimeError(
                    f"注册批次 {normalized_batch_id} 已使用邮箱，不能重复提交：{email}"
                )
        elif _e.USE_EMAIL_SERVICE:
            attempt = 0
            while not email:
                attempt += 1
                acquire_kwargs = {
                    "batch_id": normalized_batch_id or None,
                    "job_id": job_id,
                }
                # Remail 付费领取必须有 root owner 与稳定 acquisition_id；
                # 旧的无身份入口只继续支持非付费邮箱来源，不能静默生成临时 ID。
                if str(email_source or "").strip().lower() in {"remail", "mailcode", "xigua"}:
                    if not owner_kind or owner_id is None or not str(acquisition_id or "").strip():
                        raise RuntimeError("付费邮箱注册领取缺少稳定 owner/acquisition_id，已停止下单")
                    acquire_kwargs.update({
                        "owner_kind": owner_kind,
                        "owner_id": owner_id,
                        "acquisition_id": str(acquisition_id).strip(),
                    })
                candidate = str(acquire_email(email_source, **acquire_kwargs) or "").strip()
                if not candidate:
                    raise RuntimeError("邮箱来源返回空地址，无法继续注册")
                try:
                    accepted = not normalized_batch_id or db.claim_registration_batch_email(
                        normalized_batch_id,
                        candidate,
                        job_id=job_id,
                        email_source=email_source,
                    )
                except Exception:
                    _release_rejected_batch_email(
                        candidate,
                        batch_id=normalized_batch_id or f"job-{job_id or 0}",
                        job_id=int(job_id or 0),
                    )
                    raise
                if accepted:
                    email = candidate
                    break
                candidate_key = str(candidate or "").strip().lower()
                if candidate_key in rejected_keys:
                    raise RuntimeError(
                        f"注册批次 {normalized_batch_id} 的邮箱来源重复返回同一候选，"
                        f"无法领取新邮箱：{candidate}"
                    )
                rejected_keys.add(candidate_key)
                rejected.append(candidate)
                logger.warning(
                    "[Job %s] 批次邮箱重复，改领新邮箱: batch_id=%s email=%s attempt=%s",
                    job_id or "-",
                    normalized_batch_id,
                    candidate,
                    attempt,
                )
                # 拒绝的候选会保持 used，直到拿到新地址后才释放，因此邮箱池不会
                # 反复返回同一个地址；循环会一直尝试到池确实没有可用邮箱为止。
        else:
            raise RuntimeError(
                "手动模式未配置邮箱。请在 WebUI 配置页设置 REGISTER_EMAIL，"
                "或开启 USE_EMAIL_SERVICE 并从邮箱池领取。"
            )
    finally:
        for duplicate in rejected:
            _release_rejected_batch_email(
                duplicate,
                batch_id=normalized_batch_id or f"job-{job_id or 0}",
                job_id=int(job_id or 0),
            )

    return email, name, birthday


def _release_unconsumed_job_email(email: str | None, reason: str) -> None:
    """仅供明确未开始注册的管理路径回收尚未消耗的邮箱。"""
    if not email:
        return
    try:
        from core.email_provider import release_email_if_unconsumed

        release_email_if_unconsumed(email, note=f"任务未消耗，已自动回收: {reason[:180]}")
    except Exception:
        logger.exception("[Service] 回收未消耗邮箱失败: %s", email)


def _retain_job_email(email: str | None, reason: str, *, source: str | None = None) -> None:
    """中途失败时保留原邮箱，避免其他任务领取或自动停用。"""
    address = str(email or "").strip()
    if not address:
        return
    try:
        from core.email_provider import retain_email

        selected_source = retain_email(
            address,
            source=source,
            note=f"注册任务中途结束，保留给原任务链重跑: {str(reason or '')[:180]}",
        )
        logger.warning(
            "[Service] 已保留注册邮箱，等待原任务链重跑或人工对账: source=%s email=%s",
            selected_source,
            address,
        )
    except Exception:
        logger.exception("[Service] 保留注册邮箱失败: %s", address)


def _mark_job_email_permanently_unusable(
    email: str | None,
    reason: str,
    *,
    source: str | None,
) -> bool:
    """仅处理 OAuth 的结构化永久失效结果，且必须使用任务已确认的来源。"""
    address = str(email or "").strip()
    if not address:
        return False
    selected_source = str(source or "").strip()
    if not selected_source:
        logger.error("[Service] 缺少任务邮箱来源，拒绝标记邮箱永久失效: %s", address)
        return False
    try:
        from core.email_provider import mark_email_permanently_unusable

        resolved_source = mark_email_permanently_unusable(
            address,
            source=selected_source,
            note=f"上游明确确认账号永久失效: {str(reason or '')[:180]}",
        )
        logger.warning(
            "[Service] 已按上游明确结果标记注册邮箱永久失效: source=%s email=%s",
            resolved_source,
            address,
        )
        return True
    except Exception:
        logger.exception("[Service] 标记注册邮箱永久失效失败: %s", address)
        return False


def _mark_registration_attempt_deactivated(
    account_id: int | None,
    reason: str,
    *,
    error_code: str | None = None,
) -> bool:
    """收口上游已明确永久失效的 Attempt 与已落库账号。"""
    normalized_reason = str(reason or "账号已明确永久失效").strip()[:1000]
    normalized_code = str(error_code or "").strip()[:120]
    try:
        resolved_account_id = int(account_id) if account_id is not None else None
    except (TypeError, ValueError):
        resolved_account_id = None
    changed = False
    attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
    if attempt_id is not None:
        try:
            from core.storage import registration

            registration.advance_checkpoint(
                int(attempt_id),
                "failed",
                run_id=getattr(_THREAD_CTX, "run_id", None),
                job_id=getattr(_THREAD_CTX, "job_id", None),
                execution_id=getattr(_THREAD_CTX, "execution_id", None),
                event_type="account_deactivated",
                level="WARNING",
                message=normalized_reason,
                detail={"account_unusable_error_code": normalized_code} if normalized_code else {},
                remote_identity_state="confirmed",
                remote_account_state="confirmed",
                local_account_state="persisted" if resolved_account_id is not None else "none",
                target_status="deactivated",
            )
            changed = True
        except Exception:
            logger.exception("[Job %s] 写入账号永久失效 Attempt 失败", getattr(_THREAD_CTX, "job_id", None))

    if resolved_account_id is not None:
        try:
            changed = db.mark_account_deactivated(
                resolved_account_id,
                normalized_reason,
                source="registration_postprocess",
            ) or changed
        except Exception:
            logger.exception("[Service] 标记已落库账号永久失效失败: account_id=%s", resolved_account_id)
    return changed


def _mark_completed_registration_email(
    email: str | None,
    account_id: int | None,
    *,
    resumed: bool = False,
    source: str | None = None,
) -> bool:
    """注册主体成功后把邮箱收口为已使用，并让邮箱服务登记 OpenAI。"""
    if not email:
        return False
    try:
        from core.email_provider import release_email

        note_prefix = "继续注册已完成" if resumed else "注册已完成"
        release_kwargs = {"source": source} if source else {}
        resolved_source = release_email(
            email,
            status="used",
            note=f"{note_prefix}，已绑定账号 #{account_id or '-'}",
            **release_kwargs,
        )
        logger.info(
            "[Service] 已收口注册账号邮箱: source=%s account_id=%s resumed=%s",
            resolved_source,
            account_id,
            resumed,
        )
        return True
    except Exception:
        logger.exception("[Service] 收口注册账号邮箱失败: account_id=%s resumed=%s", account_id, resumed)
        return False


def _mark_completed_resume_email(
    email: str | None,
    account_id: int | None,
    *,
    source: str | None = None,
) -> bool:
    """恢复任务成功后把曾被失败分支标记的邮箱重新收口为已使用。"""
    return _mark_completed_registration_email(email, account_id, resumed=True, source=source)


def _registration_proxy_retry_limit() -> int:
    """读取注册换线重试次数；只允许有限次数，避免任务无限占用线程。"""
    try:
        from config import proxy as proxy_config

        value = int(getattr(proxy_config, "REGISTRATION_PROXY_RETRIES", 2) or 0)
    except (TypeError, ValueError, ImportError):
        value = 2
    return max(0, min(3, value))


def _registration_proxy_retry_delay() -> float:
    try:
        from config import proxy as proxy_config

        value = float(getattr(proxy_config, "REGISTRATION_PROXY_RETRY_DELAY", 1.0) or 0)
    except (TypeError, ValueError, ImportError):
        value = 1.0
    return max(0.0, min(10.0, value))


def _is_transient_registration_proxy_error(error: object) -> bool:
    """只识别线路级瞬时错误，不把页面状态错误伪装成可重试。"""
    text = str(error or "").lower()
    if not text:
        return False
    markers = (
        "err_tunnel_connection_failed",
        "err_proxy_connection_failed",
        "err_connection_reset",
        "err_connection_closed",
        "err_timed_out",
        "proxy connection",
        "ssl_error_syscall",
        "err_ssl_protocol_error",
        "err_ssl_version_or_cipher_mismatch",
        "ssl handshake",
        "ssl protocol",
        "tls handshake",
        "tls error",
        "unexpected eof while reading",
        "remote end closed connection",
        "connection aborted",
        "chrome-error://chromewebdata/",
    )
    if any(marker in text for marker in markers):
        return True
    # A blank ChatGPT auth shell is recorded as an element-not-found error,
    # but it is a recoverable line-level failure when no account checkpoint
    # exists. The empty state snapshot is safe to retry with a new IP.
    empty_actions = "'actions': []" in text or '"actions": []' in text
    empty_inputs = "'inputs': []" in text or '"inputs": []' in text
    return (
        "找不到邮箱输入框/邮箱入口" in text
        and "chatgpt.com/auth/login" in text
        and empty_actions
        and empty_inputs
    )


def _is_pre_account_transport_failure(result: dict | None) -> bool:
    """识别认证页挂载前的线路失败，不把它升级成待人工对账。"""
    if not isinstance(result, dict):
        return False
    if _has_registration_safety_fence(result):
        return False
    error_text = str(result.get("error") or "").strip().lower()
    if any(marker in error_text for marker in ("passwordtransitiontimeout", "密码提交", "password submit")):
        return False
    return _is_transient_registration_proxy_error(result.get("error"))


def _has_registration_safety_fence(result: dict) -> bool:
    """判断结果是否已有账号、检查点或明确不可用状态，禁止从头换线。"""
    dead_codes = {"account_deactivated", "account_deleted", "account_banned"}
    if (
        result.get("account_id") is not None
        or result.get("request_unknown")
        or result.get("pending_submission_id")
        or result.get("registration_pending")
        or str(result.get("access_token") or "").strip()
        or result.get("manual_reconcile")
        or result.get("email_permanently_unusable") is True
        or str(result.get("error_code") or "").strip().lower() in dead_codes
        or str(result.get("account_unusable_error_code") or "").strip().lower() in dead_codes
    ):
        return True
    for key in ("remote_identity", "remote_identity_state"):
        identity = str(result.get(key) or "").strip().lower()
        if identity not in {"", "unknown", "not_started"}:
            return True
    if str(result.get("remote_account_state") or "").strip().lower() not in {
        "", "unknown", "not_started"
    }:
        return True
    checkpoint = str(
        result.get("checkpoint") or result.get("registration_checkpoint") or ""
    ).strip().lower()
    if checkpoint not in {"", "created", "email_claimed", "auth_started"}:
        return True
    error_text = str(result.get("error") or "").strip().lower()
    return any(marker in error_text for marker in ("passwordtransitiontimeout", "密码提交", "password submit"))


def _should_retry_registration_with_new_proxy(
    result: object,
    proxy_lease: object,
    retry_attempt: int,
) -> bool:
    """决定是否释放当前线路并用新线路重新执行整段浏览器注册。"""
    if retry_attempt >= _registration_proxy_retry_limit():
        return False
    if not isinstance(result, dict):
        return False
    # 已落库的账号、待邮箱验证检查点或 access token 都不能再从头注册。
    # 明确的资料页拒绝也只做分类和人工对账，不自动新建第二个账号。
    if result.get("account_id") is not None or result.get("registration_pending"):
        return False
    if str(result.get("access_token") or "").strip():
        return False
    # 本地尚未拿到 account_id 并不等于远端尚未创建账号；只要身份或
    # checkpoint 已推进，就必须先走恢复/对账，禁止从头注册同一邮箱。
    if _has_registration_safety_fence(result):
        return False
    if str(getattr(proxy_lease, "provider", "") or "").strip().lower() != "1024proxy":
        return False
    # Auth authorize 在密码、OTP 和账号持久化之前被当前边缘路由拒绝时，
    # Protocol 会明确标记 retry_as_new_route。此时可释放 1024Proxy 租约后
    # 继续使用同一原邮箱重跑；任何未带该结构化标记的 HTTP 4xx 仍不自动重试。
    if (
        bool(result.get("retry_as_new_route"))
        and str(result.get("error_code") or "") == "auth_route_rejected"
    ):
        return (
            not _has_registration_safety_fence(result)
            and str(result.get("remote_identity") or "").strip().lower() in {"", "unknown"}
            and not result.get("request_unknown")
            and not result.get("manual_reconcile")
        )
    try:
        from core.auth_challenge import safe_to_start_new_registration

        pre_auth_transport_failure = _is_pre_account_transport_failure(result)
        if not safe_to_start_new_registration(result):
            # Before the email/auth page mounts, the remote identity is often
            # still unknown. A pure transport failure at that point has not
            # acknowledged account creation, so it is safe to rotate the
            # disposable registration route. A legacy driver may still carry
            # request_unknown for this pre-account transport failure; the
            # durable account/checkpoint guards above remain authoritative.
            if not pre_auth_transport_failure:
                return False
    except Exception:
        # Keep the existing conservative guards if the compatibility adapter
        # cannot be imported during a legacy test/bootstrap path.
        pass
    return _is_transient_registration_proxy_error(result.get("error"))


def _is_retryable_registration_proxy_acquisition_error(error: object) -> bool:
    """识别代理申请阶段的可恢复错误，避免配置类错误被盲目重试。"""
    text = str(error or "").lower()
    if not text:
        return False
    if _is_transient_registration_proxy_error(error):
        return True
    # 1024Proxy 的底层异常会被 acquire_* 统一包成这两类错误；其中也包含
    # 批次返回重复/隔离端点的情况，下一次请求会使用新的轮换序号。
    return "1024proxy 获取失败" in text or "1024proxy 批量获取失败" in text


def _registration_proxy_correlation(job_id: int, job: dict | None) -> dict[str, int | None]:
    """Resolve durable operation IDs without making them a runtime dependency."""
    current = job if isinstance(job, dict) else {}
    raw_data = current.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}
    account_id = current.get("account_id")
    if account_id is None:
        account_id = data.get("account_id")
    operation_task_id = current.get("operation_task_id")
    if operation_task_id is None:
        operation_task_id = data.get("operation_task_id")
    operation_run_id = current.get("operation_run_id")
    if operation_run_id is None:
        operation_run_id = data.get("operation_run_id")
    if operation_run_id is None:
        operation_run_id = getattr(_THREAD_CTX, "operation_run_id", None)

    # Projection writes may lag the legacy job row. When the mapping is already
    # present, fill the correlation from its durable task/current run; a
    # compatibility-only schema simply keeps these fields nullable.
    if operation_task_id is None:
        try:
            from core import operation_task_store

            root_job_id = int(current.get("root_job_id") or job_id)
            raw_task_type = str(current.get("job_type") or "registration").strip().lower()
            task_type = raw_task_type if raw_task_type in {
                "registration", "registration_resume", "codex_retry", "twofa_retry",
            } else "registration"
            operation_task = operation_task_store.find_task_by_source(
                "registration_chains", f"{root_job_id}:{task_type}"
            )
            if operation_task:
                operation_task_id = operation_task.get("id")
                if operation_run_id is None:
                    operation_run_id = operation_task.get("last_run_id")
                if account_id is None:
                    account_id = operation_task.get("account_id")
        except Exception:
            logger.debug("[Job %s] operation proxy correlation unavailable", job_id, exc_info=True)

    def optional_int(value: object) -> int | None:
        if value is None or str(value).strip() == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "account_id": optional_int(account_id),
        "operation_task_id": optional_int(operation_task_id),
        "operation_run_id": optional_int(operation_run_id),
    }


def _acquire_registration_proxy_with_retries(
    *,
    acquire_proxy,
    job_id: int,
    batch_id: str | None,
    batch_size: int,
    batch_workers: int,
    progress_callback,
    log_logger: logging.Logger,
    account_id: int | None = None,
    purpose: str | None = "registration",
    operation_task_id: int | None = None,
    operation_run_id: int | None = None,
    registration_job_id: int | None = None,
    route_attempt_no: int | None = None,
    country: str | None = None,
    retry_kind: str = "proxy_acquisition",
):
    """兼容调用入口；供应商重试由独立池维护，任务只等待一次领取。"""
    check_stop_requested()
    correlation = {
        "account_id": account_id, "purpose": purpose,
        "operation_task_id": operation_task_id, "operation_run_id": operation_run_id,
        "registration_job_id": registration_job_id if registration_job_id is not None else job_id,
        "route_attempt_no": route_attempt_no,
    }
    acquire_kwargs = {
        "job_id": job_id,
        "progress_callback": progress_callback,
        "cancel": check_stop_requested,
        **{key: value for key, value in correlation.items() if value is not None},
    }
    if country:
        acquire_kwargs["country"] = country
    return acquire_proxy(**acquire_kwargs)


def _normalize_workers(max_workers: int | None) -> int:
    if max_workers is None:
        return _DEFAULT_MAX_WORKERS
    try:
        value = int(max_workers)
    except (TypeError, ValueError):
        value = _DEFAULT_MAX_WORKERS
    return max(_MIN_MAX_WORKERS, min(_MAX_MAX_WORKERS, value))


def get_executor(max_workers: int | None = None) -> ThreadPoolExecutor:
    """返回注册线程池。

    旧逻辑只在首次创建线程池时使用 max_workers，后续 WebUI 改线程数再提交仍会复用
    上一次的池。这里改成：每次传入的 max_workers 和当前池不一致时，立即创建新池供
    新提交任务使用；旧池不接收新任务，但会继续把已经排队/运行的任务跑完。
    """
    global _executor, _executor_workers, _executor_generation
    requested_workers = _normalize_workers(max_workers) if max_workers is not None else _executor_workers
    with _executor_lock:
        if _executor is None or requested_workers != _executor_workers:
            old_executor = _executor
            if old_executor is not None:
                # 不取消旧池里已提交的任务，只是不再往旧池追加新任务。
                old_executor.shutdown(wait=False, cancel_futures=False)
                _retired_executors.append(old_executor)
                logger.info(
                    "[Service] 注册线程池 workers 从 %s 切换为 %s；旧池继续处理已排队任务",
                    _executor_workers,
                    requested_workers,
                )
            _executor_workers = requested_workers
            _executor_generation += 1
            _executor = ThreadPoolExecutor(
                max_workers=requested_workers,
                thread_name_prefix=f"reg-worker-{_executor_generation}",
            )
    return _executor


def get_executor_workers() -> int:
    """当前新提交注册任务会使用的线程数。"""
    with _executor_lock:
        return _executor_workers


def shutdown_executor(wait: bool = True) -> None:
    global _executor
    with _executor_lock:
        executors = []
        if _executor is not None:
            executors.append(_executor)
            _executor = None
        executors.extend(_retired_executors)
        _retired_executors.clear()
    for ex in executors:
        ex.shutdown(wait=wait, cancel_futures=False)


# ============================================================
# 单任务执行：日志重定向到任务专属文件
# ============================================================

class _JobLogContext:
    """让本线程的根 logger 多一个脱敏 Run JSONL handler，结束后移除。"""

    def __init__(self, log_path: str, *, task_id: int | None = None):
        self.log_path = log_path
        self.task_id = task_id
        self.handler: logging.Handler | None = None
        self._stage_scope = None

    def __enter__(self):
        task_run_log.resolve_path(self.log_path, for_write=True).parent.mkdir(parents=True, exist_ok=True)
        # 具体阶段由 report_job_progress/TaskReporter 推进；这里仅建立注册任务
        # 的初始边界，ContextVar 退出时恢复，避免线程池复用污染下一任务。
        self._stage_scope = task_run_log.stage_context(
            "registration",
            task_id=self.task_id,
            run_id=getattr(_THREAD_CTX, "run_id", None),
            identifier_namespace="registration",
        )
        self._stage_scope.__enter__()
        self.handler = task_run_log.TaskRunLogHandler(
            self.log_path,
            task_id=self.task_id,
            stage="registration",
        )
        self.handler.setLevel(logging.INFO)
        # 按线程 ID 过滤，重名线程也不能串写任务日志。
        thread_id = threading.get_ident()
        self.handler.addFilter(lambda r: r.thread == thread_id)
        logging.getLogger().addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handler is not None:
            self.handler.close()
            logging.getLogger().removeHandler(self.handler)
        if self._stage_scope is not None:
            self._stage_scope.__exit__(exc_type, exc, tb)
            self._stage_scope = None


def _run_one_job(job_id: int, log_file: str) -> None:
    """单任务入口（线程池里跑这个）。"""
    log_logger = logging.getLogger(__name__)
    _activate_job(job_id)

    # 取消检查：用户可能在任务排队期间点了"取消排队"，把 status 改成了 cancelled。
    # 因为 Future 已经 submit 进线程池无法撤回，只能在真正执行前自检一下，跳过 cancelled 的。
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current:
        log_logger.info(f"[Job {job_id}] 任务记录已删除，跳过执行")
        _deactivate_job(job_id)
        return
    batch_id = str(current.get("batch_id") or "").strip()
    try:
        batch_size = max(1, int(current.get("batch_size") or 1))
    except (TypeError, ValueError):
        batch_size = 1
    try:
        batch_workers = max(1, int(current.get("batch_workers") or 1))
    except (TypeError, ValueError):
        batch_workers = 1
    # 重试子任务要继续挂在原批次下，供 UI/统计合并展示；但它是一个新的
    # 独立执行，不应再次加入原批次的代理预取和隔离状态。
    is_retry_job = current.get("parent_job_id") is not None
    proxy_batch_id = batch_id if batch_id and batch_size > 1 and not is_retry_job else None
    proxy_batch_size = batch_size if proxy_batch_id else 1
    proxy_batch_workers = batch_workers if proxy_batch_id else 1
    if current.get("status") == "cancelled":
        log_logger.info(f"[Job {job_id}] 已被用户取消，跳过执行")
        if proxy_batch_id:
            try:
                from core.proxy_provider import finalize_registration_proxy_batch

                finalize_registration_proxy_batch(proxy_batch_id)
            except Exception:
                logger.exception("[Job %s] 收口已取消注册批次失败", job_id)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=_now_iso(),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        # 停止/取消可能发生在工作线程刚从线程池取出任务、尚未开始执行的窗口。
        # 条件抢占失败表示数据库状态已经被控制接口改变，不能再把它启动回来。
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=_now_iso(),
                error="用户手动停止",
            )
        _deactivate_job(job_id)
        return
    _ensure_registration_run_context(db.get_job(job_id) or current)
    _bind_progress_route_context((db.get_job(job_id) or current).get("route_attempt_no") or 1)
    proxy_correlation = _registration_proxy_correlation(job_id, db.get_job(job_id) or current)
    _THREAD_CTX.operation_run_id = proxy_correlation.get("operation_run_id")
    _bind_progress_route_context((db.get_job(job_id) or current).get("route_attempt_no") or 1)
    try:
        initial_route_attempt_no = max(1, int(current.get("route_attempt_no") or 1))
    except (TypeError, ValueError):
        initial_route_attempt_no = 1
    proxy_correlation.update({
        "registration_job_id": job_id,
        "route_attempt_no": initial_route_attempt_no,
    })
    registration_country = _registration_proxy_country_for_job(
        db.get_job(job_id) or current
    )
    _bind_progress_route_context(initial_route_attempt_no)
    _persist_job_progress(job_id, "network", state="running", detail="正在申请或分配网络线路")
    # 代理申请回调可能由供应商适配层的其他线程触发；提前捕获步骤实例，
    # 回调不依赖目标线程的 thread-local 状态。
    initial_network_instance = _progress_step_instance("network", "running")

    email: str | None = None
    proxy_lease = None
    unknown_facts: dict[str, object] = {}
    try:
        with _JobLogContext(log_file, task_id=job_id):
            from core.registration.dispatcher import run_registration
            from core.proxy_provider import acquire_registration_proxy, mask_endpoint, mask_ip, release_proxy

            def _bind_proxy_lease(lease) -> None:
                attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
                if attempt_id is not None:
                    metadata = getattr(lease, "metadata", None)
                    if isinstance(metadata, dict):
                        metadata["attempt_id"] = int(attempt_id)
                db.update_job(
                    job_id,
                    proxy_provider=lease.provider,
                    proxy_status="leased",
                    proxy_endpoint=mask_endpoint(lease.endpoint),
                    proxy_exit_ip=mask_ip(lease.exit_ip) or "-",
                    proxy_region=lease.region or "-",
                    proxy_acquired_at=lease.acquired_at.isoformat(timespec="seconds"),
                    proxy_expires_at=lease.expires_at.isoformat(timespec="seconds") if lease.expires_at else "-",
                )
                # 库存由独立池提前维护；本任务只记录领取租约的时间。
                _persist_job_progress(
                    job_id,
                    "network",
                    state="success",
                    detail="网络线路已分配",
                )

            log_logger.info(f"[Job {job_id}] 开始注册任务")
            db.update_job(job_id, proxy_status="acquiring")
            proxy_progress_route = int(proxy_correlation["route_attempt_no"] or 1)
            proxy_progress_run = proxy_correlation.get("operation_run_id")

            def _proxy_progress(
                detail: str,
                *,
                _route=proxy_progress_route,
                _run=proxy_progress_run,
                _instance=initial_network_instance,
            ) -> None:
                _persist_job_progress(
                    job_id, "network", state="running", detail=detail,
                    route_attempt_no=_route, operation_run_id=_run,
                    step_instance_id=_instance,
                )

            proxy_lease = _acquire_registration_proxy_with_retries(
                acquire_proxy=acquire_registration_proxy,
                job_id=job_id,
                batch_id=proxy_batch_id,
                batch_size=proxy_batch_size,
                batch_workers=proxy_batch_workers,
                progress_callback=_proxy_progress,
                log_logger=log_logger,
                country=registration_country,
                **proxy_correlation,
            )
            _bind_proxy_lease(proxy_lease)
            _persist_job_progress(job_id, "email", state="running", detail="正在领取或复用注册邮箱")
            existing_password = ""
            existing_totp_secret = ""
            bound_profile_id = ""
            is_registration_retry = (
                is_retry_job
                and str(current.get("job_type") or "") == "registration"
            )
            root_email = ""
            child_email = ""
            reuses_original_email = False
            try:
                registration_root_id = int(current.get("root_job_id") or current.get("id") or job_id)
            except (TypeError, ValueError):
                registration_root_id = int(job_id)
            registration_acquisition_id = _registration_acquisition_id_for_root(registration_root_id)
            if is_registration_retry:
                root_job_id = int(current.get("root_job_id") or current.get("id") or job_id)
                root_job = current if root_job_id == job_id else db.get_job(root_job_id)
                if not root_job:
                    raise RuntimeError("重跑任务的根任务不存在，不能确认原邮箱来源或邮箱")
                try:
                    from core.email_provider import validate_email_source

                    root_source = validate_email_source(str(root_job.get("email_source") or ""))
                    child_source = validate_email_source(str(current.get("email_source") or ""))
                except ValueError:
                    raise RuntimeError("重跑任务的原邮箱来源不明确，不能切换来源或邮箱")
                if child_source != root_source:
                    raise RuntimeError("重跑任务邮箱来源与根任务不一致，不能切换来源或邮箱")
                root_email = str(root_job.get("email") or "").strip()
                child_email = str(current.get("email") or "").strip()
                if root_email and child_email and root_email.casefold() != child_email.casefold():
                    raise RuntimeError("重跑任务邮箱与根任务不一致，不能切换来源或邮箱")
                selected_source = root_source
                reuses_original_email = bool(root_email or child_email)
            else:
                selected_source = str(current.get("email_source") or "").strip()
                try:
                    from core.email_provider import validate_email_source

                    selected_source = validate_email_source(selected_source)
                except ValueError:
                    # 兼容改造前已经存在的多来源历史任务；新任务 API 不再允许这种值。
                    from core.email_provider import parse_email_sources

                    selected_source = parse_email_sources(selected_source)[0]
            from core.roxy_profile_binding import account_profile_id
            bound_profile_id = account_profile_id(_account_for_job(current))
            if str(current.get("job_type") or "") == "registration_resume":
                resume_account = _enrich_account_registration_state(_account_for_job(current))
                email = str((resume_account or {}).get("email") or current.get("email") or "").strip()
                bound_profile_id = account_profile_id(resume_account)
                existing_password = _pending_registration_password(resume_account)
                if resume_account is None:
                    existing_password = _private_registration_resume_password(current)
                existing_totp_secret = str((resume_account or {}).get("totp_secret") or "").strip()
                if not email or not existing_password:
                    raise RuntimeError("待邮箱验证账号缺少邮箱或已保存账号密码，无法继续验证")
                if selected_source == "remail":
                    # registration_resume 也必须恢复根任务的原领取意图；否则
                    # wait_for_otp 会在重启后失去 service token，不能按邮箱猜测新订单。
                    _restore_remail_registration_resume_context(
                        email=email,
                        registration_root_id=registration_root_id,
                        acquisition_id=registration_acquisition_id,
                    )
                from core.profile_utils import generate_random_birthday

                name = _random_display_name()
                birthday = generate_random_birthday()
                _persist_job_progress(
                    job_id,
                    "email",
                    state="success",
                    detail="已复用原任务邮箱和保存的账号密码",
                )
                log_logger.info("[Job %s] 继续验证已保存账号：account_id=%s", job_id, (resume_account or {}).get("id"))
            elif reuses_original_email:
                email = child_email or root_email
                if not email:
                    raise RuntimeError("重跑任务缺少原注册邮箱，不能改用其他邮箱")
                from core.profile_utils import generate_random_birthday
                if selected_source == "remail":
                    # Remail 重跑只能按根任务稳定 acquisition_id 恢复原意图；
                    # 不按同邮箱搜索最新订单，也不在原意图缺失时新下单。
                    from core.remail_order_coordinator import RemailOrderCoordinator
                    from core.storage import remail_orders

                    intent = remail_orders.get_intent(registration_acquisition_id, private=True)
                    if not intent:
                        raise RuntimeError("重跑任务缺少原 Remail 领取意图，不能按邮箱猜测订单或重新下单")
                    if (
                        str(intent.get("owner_kind") or "") != "registration_root"
                        or str(intent.get("owner_id") or "") != str(registration_root_id)
                        or str(intent.get("acquisition_id") or "") != str(registration_acquisition_id)
                    ):
                        raise RuntimeError("原 Remail 领取意图与注册根任务不匹配，不能继续")
                    coordinator = RemailOrderCoordinator()
                    durable_account = coordinator._account_from_intent(intent)
                    if not durable_account and str(intent.get("supplier_identity_ref") or "") != coordinator._supplier_ref():
                        raise RuntimeError("原 Remail 订单供应商身份与当前配置不匹配，不能继续")
                    account = coordinator.acquire(
                        owner_kind="registration_root",
                        owner_id=registration_root_id,
                        acquisition_id=registration_acquisition_id,
                    )
                    if str(account.email or "").strip().casefold() != email.casefold():
                        raise RuntimeError("原 Remail 订单邮箱与注册根任务不匹配，不能继续")
                    email = account.email
                else:
                    from core.email_provider import restore_email_context

                    restore_email_context(
                        email,
                        source=selected_source,
                        purpose="registration_retry",
                    )
                name = _random_display_name()
                birthday = generate_random_birthday()
                _persist_job_progress(
                    job_id,
                    "email",
                    state="success",
                    detail="已复用原任务邮箱，不会改领新邮箱",
                )
            else:
                email, name, birthday = _prepare_registration_args(
                    selected_source,
                    batch_id=batch_id,
                    job_id=job_id,
                    **({
                        "owner_kind": "registration_root",
                        "owner_id": registration_root_id,
                        "acquisition_id": registration_acquisition_id,
                    } if selected_source in {"remail", "mailcode", "xigua"} else {}),
                )
            from core.email_provider import remember_email_source

            remember_email_source(email, selected_source)
            bind_registration_email(
                email,
                email_source=selected_source,
                root_job_id=int(current.get("root_job_id") or job_id),
            )
            db.update_job(job_id, email=email)
            if reuses_original_email and not existing_password:
                attempt_id = getattr(_THREAD_CTX, "attempt_id", None)
                if attempt_id is not None:
                    from core.storage import registration
                    private_resume = registration.get_private_resume_context(int(attempt_id), email=email)
                    existing_password = str(private_resume.get("password") or "").strip()
            if not existing_password:
                if not reuses_original_email:
                    _persist_job_progress(job_id, "email", state="success", detail=f"已从 {selected_source} 领取邮箱")
            check_stop_requested()
            retry_attempt = 0
            while True:
                check_stop_requested()
                # A missing bound Profile may be replaced during the previous
                # attempt. Re-read the durable account row before a proxy
                # retry so the next attempt opens that replacement instead of
                # retrying the stale Profile ID.
                bound_profile_id = account_profile_id(_account_for_job(current))
                from core.protocol_traffic import correlation_context
                with correlation_context(**{**proxy_correlation,
                        "proxy_lease_id": getattr(proxy_lease, "lease_id", None),
                        "route_attempt_no": proxy_correlation["route_attempt_no"],
                        "registration_attempt_id": getattr(_THREAD_CTX, "attempt_id", None),
                        "registration_run_id": getattr(_THREAD_CTX, "run_id", None)}):
                    result = run_registration(
                        email=email,
                        name=name,
                        birthday=birthday,
                        proxy=proxy_lease.proxy_url,
                        existing_password=existing_password or None,
                        existing_totp_secret=existing_totp_secret or None,
                        profile_id=bound_profile_id or None,
                        registration_options=registration_options_for_job(current),
                        email_source=selected_source,
                    )
                if not _should_retry_registration_with_new_proxy(result, proxy_lease, retry_attempt):
                    break

                retry_attempt += 1
                retry_error = str((result or {}).get("error") or "代理线路瞬时失败")[:220]
                log_logger.warning(
                    "[Job %s] 注册遇到代理瞬时错误，释放旧线路并换线重试 (%s/%s): %s",
                    job_id,
                    retry_attempt,
                    _registration_proxy_retry_limit(),
                    retry_error,
                )
                release_proxy(proxy_lease, reason=f"registration_proxy_retry_{retry_attempt}")
                proxy_lease = None
                db.update_job(
                    job_id,
                    proxy_status="acquiring",
                    error=f"代理线路瞬时失败，准备换线重试: {retry_error}",
                )
                next_route_no = db.begin_job_route_attempt(
                    job_id,
                    retry_kind="proxy_rotation",
                    retry_reason=retry_error,
                )
                _bind_progress_route_context(next_route_no)
                _persist_job_progress(
                    job_id,
                    "network",
                    state="running",
                    detail=f"线路瞬时失败，正在更换代理重试 ({retry_attempt}/{_registration_proxy_retry_limit()})",
                )
                retry_network_instance = _progress_step_instance("network", "running")
                retry_delay = _registration_proxy_retry_delay()
                if retry_delay:
                    time.sleep(retry_delay)
                check_stop_requested()
                retry_proxy_correlation = dict(proxy_correlation)
                retry_proxy_correlation["route_attempt_no"] = int(next_route_no)
                proxy_correlation["route_attempt_no"] = int(next_route_no)
                proxy_progress_route = int(next_route_no)
                proxy_progress_run = proxy_correlation.get("operation_run_id")

                def _retry_proxy_progress(
                    detail: str,
                    *,
                    _route=proxy_progress_route,
                    _run=proxy_progress_run,
                    _instance=retry_network_instance,
                ) -> None:
                    _persist_job_progress(
                        job_id, "network", state="running", detail=detail,
                        route_attempt_no=_route, operation_run_id=_run,
                        step_instance_id=_instance,
                    )

                proxy_lease = _acquire_registration_proxy_with_retries(
                    acquire_proxy=acquire_registration_proxy,
                    job_id=job_id,
                    # 换线仍向同一个独立池申请，供应商细节不进入任务循环。
                    batch_id=None,
                    batch_size=1,
                    batch_workers=1,
                    progress_callback=_retry_proxy_progress,
                    log_logger=log_logger,
                    retry_kind="proxy_rotation_acquisition",
                    country=registration_country,
                    **retry_proxy_correlation,
                )
                _bind_proxy_lease(proxy_lease)
                _persist_job_progress(
                    job_id,
                    "email",
                    state="running",
                    detail="新线路已就绪，将继续使用原注册邮箱",
                )
                if not existing_password:
                    _persist_job_progress(
                        job_id,
                        "email",
                        state="success",
                        detail="换线重试继续使用原注册邮箱，不会改领新邮箱",
                    )
                else:
                    _persist_job_progress(
                        job_id,
                        "email",
                        state="success",
                        detail="换线重试继续使用已保存账号邮箱",
                    )
            # Codex 失败时注册账号可能已经创建并保存。代理地区属于账号注册事实，
            # 不能只在整项任务 success 时落库，否则后续补跑/查套餐无法稳定沿用地区。
            if isinstance(result, dict) and result.get("account_id"):
                db.update_account_registration_proxy(
                    int(result.get("account_id")),
                    provider=proxy_lease.provider,
                    region=proxy_lease.region,
                )
            result_is_dict = isinstance(result, dict)
            confirmed_unusable = _confirmed_postprocess_email_unusable(result)
            if is_stop_requested(job_id) and confirmed_unusable is None:
                # run_registration 正常返回前，各注册驱动已经完成邮箱状态收口。
                # 这里不能再次释放：失败邮箱可能已经被下一任务重新领取，二次释放
                # 会把别的线程正在使用的租约错误改回 available。
                db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
                db.update_job(
                    job_id,
                    status="stopped",
                    error="用户手动停止",
                    completed_at=_now_iso(),
                )
                log_logger.warning(f"[Job {job_id}] 已按用户请求停止")
                return
            registration_succeeded = bool(
                result_is_dict
                and registration_result_status(result) == "success"
            )
            partial_success = bool(
                registration_succeeded
                and (
                    result.get("partial_success")
                    or result.get("postprocess_success") is False
                    or not result.get("success")
                )
            )
            if confirmed_unusable is not None:
                result_email = str(result.get("email") or email or "").strip()
                unusable_code = str(confirmed_unusable.get("account_unusable_error_code") or "").strip()
                unusable_message = str(
                    confirmed_unusable.get("message") or result.get("error") or "账号已明确永久失效"
                ).strip()
                unusable_reason = (
                    f"{unusable_code}: {unusable_message}"
                    if unusable_code and unusable_code.casefold() not in unusable_message.casefold()
                    else unusable_message
                )
                persisted_err = _persisted_result_error(result, unusable_reason)
                _mark_job_email_permanently_unusable(
                    result_email,
                    unusable_reason,
                    source=selected_source,
                )
                _mark_registration_attempt_deactivated(
                    result.get("account_id"),
                    unusable_message,
                    error_code=unusable_code or None,
                )
                db.finish_job_progress(job_id, success=False, detail=persisted_err[:300])
                db.update_job(
                    job_id,
                    status="failed",
                    email=result.get("email"),
                    account_id=result.get("account_id"),
                    error=persisted_err,
                    completed_at=_now_iso(),
                )
                log_logger.error("[Job %s] Codex 明确确认账号永久失效: %s", job_id, unusable_reason)
            elif registration_succeeded:
                _mark_registration_result(result)
                warning = _persisted_result_error(result, result.get("error"))
                registration_pending = bool(
                    not result.get("success")
                    and result.get("account_id")
                    and (
                        result.get("registration_pending")
                        or not str(result.get("access_token") or "").strip()
                    )
                )
                if not registration_pending:
                    completed_email = str(result.get("email") or email or "").strip()
                    completed_account_id = int(result.get("account_id")) if result.get("account_id") else None
                    _mark_completed_registration_email(
                        completed_email,
                        completed_account_id,
                        resumed=str(current.get("job_type") or "") == "registration_resume",
                        source=selected_source,
                    )
                if registration_pending:
                    # 密码已经保存只能说明账号进入了“待邮箱验证”，不能把当前
                    # 验证码节点及后续未执行节点涂成绿色。先保留真实失败节点，
                    # finish_job_progress 再把从未上报的后续节点收口为 skipped。
                    progress = db.get_job(job_id) or {}
                    failed_stage = str(progress.get("progress_stage") or "email_otp")
                    if failed_stage not in {key for key, _label in db.JOB_PROGRESS_STAGES} or failed_stage == "complete":
                        failed_stage = "email_otp"
                    _persist_job_progress(
                        job_id,
                        failed_stage,
                        state="failed",
                        detail=(warning or "账号已保存，邮箱验证尚未完成")[:300],
                    )
                db.finish_job_progress(job_id, success=True)
                final_status = "partial_success" if partial_success else "success"
                db.update_job(
                    job_id,
                    status=final_status,
                    email=result.get("email"),
                    account_id=result.get("account_id"),
                    # A successful later route must not retain the transient
                    # proxy/browser error that triggered its automatic retry.
                    error=warning,
                    completed_at=_now_iso(),
                )
                if partial_success:
                    if registration_pending:
                        log_logger.warning(
                            "[Job %s] 密码已提交并保存恢复检查点，远端结果待确认: %s",
                            job_id,
                            warning or "请继续登录同一账号完成邮箱验证",
                        )
                    else:
                        log_logger.warning(
                            "[Job %s] 注册主体成功，后置步骤部分未完成: %s",
                            job_id,
                            warning or "请查看 Codex/2FA 子步骤",
                        )
                else:
                    log_logger.info(f"[Job {job_id}] 成功: {result.get('email')}")
            else:
                # 注意：失败也可能伴随 account_id（如 Codex 失败但账号已注册成功）
                err = (result or {}).get("error") if isinstance(result, dict) else "unknown"
                persisted_err = _persisted_result_error(result, err)
                result_email = (result or {}).get("email") if isinstance(result, dict) else None
                request_unknown = bool(isinstance(result, dict) and result.get("request_unknown"))
                manual_reconcile = bool(isinstance(result, dict) and result.get("manual_reconcile"))
                pre_account_transport_failure = _is_pre_account_transport_failure(result)
                email_submission_unconfirmed = bool(result_is_dict and result.get("email_submission_unconfirmed"))
                if request_unknown and not pre_account_transport_failure and not email_submission_unconfirmed:
                    unknown_facts = _registration_request_unknown_facts(result)
                    _mark_registration_request_unknown(
                        str(err or "密码提交结果待确认"), facts=unknown_facts,
                    )
                if manual_reconcile:
                    _mark_registration_manual_reconcile(
                        str(err or "远端账号已存在，需要人工协调"),
                        detail={"next_action": "account_reconcile", "remote_identity": "existing"},
                    )
                if result_is_dict and result.get("registration_pending"):
                    progress = db.get_job(job_id) or {}
                    failed_stage = str(progress.get("progress_stage") or "email_otp")
                    if failed_stage not in {key for key, _label in db.JOB_PROGRESS_STAGES} or failed_stage == "complete":
                        failed_stage = "email_otp"
                    _persist_job_progress(job_id, failed_stage, state="failed", detail=persisted_err[:300])
                try:
                    from core.registration_debug import capture_current_failure
                    capture_current_failure(str(err)[:1000])
                except Exception:
                    logger.exception("[Job %s] 保存失败诊断现场失败", job_id)
                db.finish_job_progress(job_id, success=False, detail=persisted_err[:300])
                db.update_job(
                    job_id,
                    status=registration_result_status(result),
                    email=result_email,
                    account_id=(result or {}).get("account_id") if isinstance(result, dict) else None,
                    error=persisted_err,
                    completed_at=_now_iso(),
                )
                email_to_handle = str(result_email or email or "").strip()
                _retain_job_email(
                    email_to_handle,
                    str(err),
                    source=selected_source,
                )
                if manual_reconcile or request_unknown:
                    log_logger.warning("[Job %s] 注册未确认成功，按失败收口；保留原邮箱和恢复断点供重跑: %s", job_id, err)
                else:
                    log_logger.error(f"[Job {job_id}] 失败: {err}")
    except RemailOrderUncertain as exc:
        # 邮箱供应商可能已经扣款；即使尚未取得地址，也不能按普通失败重新下单。
        message = "Remail 邮箱订单结果待核验，请先核对原订单，禁止直接重试下单"
        safe_details = exc.safe_details()
        unknown_facts = {
            "outcome": "request_unknown",
            "cause_code": "remail_order_request_unknown",
            "safe_details": safe_details,
        }
        db.finish_job_progress(job_id, success=False, detail=message)
        db.update_job(
            job_id,
            status="request_unknown",
            error=f"request_unknown: {message}",
            completed_at=_now_iso(),
        )
        log_logger.warning("[Job %s] %s", job_id, message)
    except StopRequested as exc:
        _retain_job_email(email, str(exc), source=str(current.get("email_source") or "") or None)
        db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
        log_logger.warning(f"[Job {job_id}] 已停止: {exc}")
        db.update_job(
            job_id,
            status="stopped",
            error="用户手动停止",
            completed_at=_now_iso(),
        )
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        try:
            from core.registration_debug import capture_current_failure
            capture_current_failure(err_text[:1000])
        except Exception:
            logger.exception("[Job %s] 保存失败诊断现场失败", job_id)
        _retain_job_email(email, err_text, source=str(current.get("email_source") or "") or None)
        if is_stop_requested(job_id):
            log_logger.warning(f"[Job {job_id}] 停止中捕获异常，按停止处理: {type(exc).__name__}: {exc}")
            db.finish_job_progress(job_id, success=False, detail="用户手动停止", failure_state="stopped")
            db.update_job(
                job_id,
                status="stopped",
                error="用户手动停止",
                completed_at=_now_iso(),
            )
            return
        log_logger.exception(f"[Job {job_id}] 异常")
        db.finish_job_progress(job_id, success=False, detail=err_text[:300])
        db.update_job(
            job_id,
            status="failed",
            proxy_status="failed" if proxy_lease is None else "leased",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=_now_iso(),
        )
    finally:
        final_job = db.get_job(job_id) or {}
        final_status = str(final_job.get("status") or "failed").strip().lower()
        if final_status not in {"queued", "running", "success", "partial_success", "failed", "stopped", "cancelled", "interrupted", "request_unknown", "manual_reconcile"}:
            final_status = "failed"
        if final_status in {"queued", "running"}:
            final_status = "failed"
        _finish_registration_run(
            final_status,
            error_message=str(final_job.get("error") or "")[:2000] or None,
            result_summary={
                "job_id": job_id, "status": final_status,
                **unknown_facts,
            },
        )
        if proxy_lease is not None:
            try:
                from core.proxy_provider import release_proxy

                release_proxy(proxy_lease, reason=str(final_job.get("status") or "completed"))
                db.update_job(job_id, proxy_status="released")
            except Exception:
                logger.exception("[Job %s] 释放代理租约失败", job_id)
        if proxy_batch_id:
            try:
                from core.proxy_provider import finalize_registration_proxy_batch

                finalize_registration_proxy_batch(proxy_batch_id)
            except Exception:
                logger.exception("[Job %s] 收口注册代理批次失败", job_id)
        _deactivate_job(job_id)


def _run_codex_retry_job(
    job_id: int,
    log_file: str,
    email: str,
    account_id: int,
    account_task_id: int | None = None,
) -> None:
    """把 Codex 补跑作为标准任务执行，并复用任务状态、日志和停止入口。"""
    _activate_job(job_id)
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current or current.get("status") == "cancelled":
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务已取消，Codex 补跑未执行",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=_now_iso(),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=_now_iso(),
                error="用户手动停止",
            )
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务未启动，已取消",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return
    _ensure_registration_run_context(db.get_job(job_id) or current)
    _bind_progress_route_context((db.get_job(job_id) or current).get("route_attempt_no") or 1)
    for stage, _label in db.JOB_PROGRESS_STAGES:
        if stage not in {"codex", "complete"}:
            _persist_job_progress(job_id, stage, state="skipped", detail="Codex 补跑任务")
    _persist_job_progress(job_id, "codex", state="running", detail="正在补跑 Codex 授权")
    try:
        result = codex_retry_service.run_worker(
            email,
            clear_log=False,
            target_log_path=log_file,
            task_id=account_task_id,
            task_trigger="registration_job_retry",
        )
        now_iso = _now_iso()
        proxy_fields = {}
        if result.get("proxy_provider"):
            proxy_fields = {
                "proxy_provider": result.get("proxy_provider"),
                "proxy_region": result.get("proxy_region") or "-",
                "proxy_status": "released",
            }
        if is_stop_requested(job_id) or result.get("status") == "stopped":
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "用户手动停止")[:300], failure_state="stopped")
            db.update_job(job_id, status="stopped", email=email, account_id=account_id, error=str(result.get("message") or "用户手动停止")[:500], completed_at=now_iso, **proxy_fields)
        elif result.get("ok"):
            _persist_job_progress(job_id, "codex", state="success", detail="Codex 补跑已确认完成")
            db.finish_job_progress(job_id, success=True)
            db.update_job(
                job_id,
                status="success",
                email=email,
                account_id=account_id,
                completed_at=now_iso,
                **proxy_fields,
            )
        else:
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "Codex 补跑失败")[:300])
            db.update_job(
                job_id,
                status="failed",
                email=email,
                account_id=account_id,
                error=str(result.get("message") or "Codex 补跑失败")[:500],
                completed_at=now_iso,
                **proxy_fields,
            )
    except Exception as exc:
        db.finish_job_progress(job_id, success=False, detail=f"{type(exc).__name__}: {exc}"[:300])
        db.update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=_now_iso(),
        )
        codex_retry_service.release(email)
        logger.exception("[Job %s] Codex 补跑异常", job_id)
    finally:
        final_job = db.get_job(job_id) or {}
        final_status = str(final_job.get("status") or "failed").strip().lower()
        if final_status in {"queued", "running"} or final_status not in {
            "success", "partial_success", "failed", "stopped", "cancelled", "interrupted", "request_unknown", "manual_reconcile"
        }:
            final_status = "failed"
        _finish_registration_run(
            final_status,
            error_message=str(final_job.get("error") or "")[:2000] or None,
            result_summary={"job_id": job_id, "action": "retry_codex", "status": final_status},
        )
        _deactivate_job(job_id)


def _run_twofa_retry_job(
    job_id: int,
    log_file: str,
    email: str,
    account_id: int,
    account_task_id: int | None = None,
) -> None:
    """把账号配置检查/补齐作为标准注册重试任务执行。"""
    _activate_job(job_id)
    try:
        current = db.get_job(job_id)
    except Exception:
        _deactivate_job(job_id)
        raise
    if not current or current.get("status") == "cancelled":
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务已取消，账号配置重试未执行",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return

    try:
        claimed = db.claim_job_for_execution(
            job_id,
            started_at=_now_iso(),
        )
    except Exception:
        _deactivate_job(job_id)
        raise
    if not claimed:
        latest = db.get_job(job_id) or {}
        if latest.get("status") == "stopping":
            db.transition_job_status(
                job_id,
                ("stopping",),
                "stopped",
                completed_at=_now_iso(),
                error="用户手动停止",
            )
        account_task_store.finish_task(
            account_task_id,
            status="cancelled",
            message="注册重试任务未启动，已取消",
        )
        codex_retry_service.release(email)
        _deactivate_job(job_id)
        return
    _ensure_registration_run_context(db.get_job(job_id) or current)
    _bind_progress_route_context((db.get_job(job_id) or current).get("route_attempt_no") or 1)
    for stage, _label in db.JOB_PROGRESS_STAGES:
        if stage not in {"twofa", "complete"}:
            _persist_job_progress(job_id, stage, state="skipped", detail="账号配置重试任务")
    _persist_job_progress(job_id, "twofa", state="running", detail="正在补齐账号密码、套餐和 Authenticator 2FA")
    try:
        result = codex_retry_service.run_twofa_worker(
            email,
            clear_log=False,
            target_log_path=log_file,
            task_id=account_task_id,
            task_trigger="registration_job_retry",
        )
        now_iso = _now_iso()
        proxy_fields = {}
        if result.get("proxy_provider"):
            proxy_fields = {
                "proxy_provider": result.get("proxy_provider"),
                "proxy_region": result.get("proxy_region") or "-",
                "proxy_status": "released",
            }
        if is_stop_requested(job_id) or result.get("status") == "stopped":
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "用户手动停止")[:300], failure_state="stopped")
            db.update_job(job_id, status="stopped", email=email, account_id=account_id, error=str(result.get("message") or "用户手动停止")[:500], completed_at=now_iso, **proxy_fields)
        elif result.get("ok"):
            _persist_job_progress(job_id, "twofa", state="success", detail="账号密码、套餐和 Authenticator 2FA 已确认")
            db.finish_job_progress(job_id, success=True)
            db.update_job(job_id, status="success", email=email, account_id=account_id, completed_at=now_iso, **proxy_fields)
        else:
            _persist_job_progress(job_id, "twofa", state="failed", detail=str(result.get("message") or "账号配置重试失败")[:300])
            db.finish_job_progress(job_id, success=False, detail=str(result.get("message") or "账号配置重试失败")[:300])
            db.update_job(job_id, status="failed", email=email, account_id=account_id, error=str(result.get("message") or "账号配置重试失败")[:500], completed_at=now_iso, **proxy_fields)
    except Exception as exc:
        _persist_job_progress(job_id, "twofa", state="failed", detail=f"{type(exc).__name__}: {exc}"[:300])
        db.finish_job_progress(job_id, success=False, detail=f"{type(exc).__name__}: {exc}"[:300])
        db.update_job(
            job_id,
            status="failed",
            error=f"{type(exc).__name__}: {exc}"[:500],
            completed_at=_now_iso(),
        )
        codex_retry_service.release(email)
        logger.exception("[Job %s] 账号配置重试异常", job_id)
    finally:
        final_job = db.get_job(job_id) or {}
        final_status = str(final_job.get("status") or "failed").strip().lower()
        if final_status in {"queued", "running"} or final_status not in {
            "success", "partial_success", "failed", "stopped", "cancelled", "interrupted", "request_unknown", "manual_reconcile"
        }:
            final_status = "failed"
        _finish_registration_run(
            final_status,
            error_message=str(final_job.get("error") or "")[:2000] or None,
            result_summary={"job_id": job_id, "action": "retry_twofa", "status": final_status},
        )
        _deactivate_job(job_id)


# ============================================================
# 公共接口
# ============================================================

def submit_registration(
    count: int = 1,
    email_source: str | None = None,
    workers: int | None = None,
    *,
    debug_enabled: bool = False,
    registration_driver: str | None = None,
) -> list[dict]:
    """
    创建 N 个注册任务并提交到线程池。
    email_source 会写入每个任务，任务执行时严格使用该来源，不跨平台兜底。

    Returns:
        N 个新创建的 job dict
    """
    selected_driver = (
        validate_registration_driver(registration_driver)
        if registration_driver is not None
        else None
    )
    if email_source is None:
        from config import email as _email_cfg
        from core.email_provider import parse_email_sources
        email_source = parse_email_sources(_email_cfg.EMAIL_SOURCE)[0]
    from core.email_provider import validate_email_source
    email_source = validate_email_source(email_source)

    # 创建/切换线程池和提交本批任务必须整体串行化：否则另一请求在本批提交中途
    # 切换 workers 并 shutdown 旧池，会导致后续 submit 报 cannot schedule new futures after shutdown。
    with _executor_lock:
        executor = get_executor(max_workers=workers)
        effective_workers = get_executor_workers()
        batch_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        # 同一批任务共享入队瞬间的国家快照；即使配置在提交循环期间热加载，
        # 也不能让同一批排队任务分裂到不同的默认国家。
        registration_snapshot = registration_config_snapshot()
        if selected_driver is not None:
            _apply_registration_driver_snapshot(registration_snapshot, selected_driver)
        jobs = []
        for index in range(count):
            job = db.create_job(
                email_source=email_source,
                batch_id=batch_id,
                batch_index=index + 1,
                batch_size=count,
                batch_workers=effective_workers,
                data={"config_snapshot": dict(registration_snapshot)},
            )
            if debug_enabled:
                from core.registration_debug import patch_job
                patch_job(
                    int(job["id"]),
                    debug_enabled=True,
                    debug_state="pending",
                    debug_policy={
                        "capture_network": True,
                        "hold_on_failure": True,
                        "preserve_success_browser": False,
                    },
                )
                job = db.get_job(int(job["id"])) or job
            try:
                executor.submit(_run_one_job, job["id"], job["log_file"])
            except Exception as exc:
                db.update_job(
                    int(job["id"]),
                    status="failed",
                    error=f"队列提交失败：{type(exc).__name__}: {exc}"[:500],
                    completed_at=_now_iso(),
                )
                logger.exception("[Service] 注册任务 #%s 提交线程池失败", job["id"])
            jobs.append(db.get_job(int(job["id"])) or job)
    logger.info(
        "[Service] 已提交 %s 个注册任务，源=%s，driver=%s，workers=%s，debug=%s",
        count,
        email_source,
        selected_driver or registration_snapshot.get("registration_driver"),
        effective_workers,
        bool(debug_enabled),
    )
    return jobs


def _account_for_job(job: dict) -> dict | None:
    account_id = job.get("account_id")
    if account_id is not None:
        try:
            account = db.get_account(int(account_id))
            if account is not None:
                return account
        except (TypeError, ValueError):
            pass
    email = str(job.get("email") or "").strip()
    if not email and _attempt_id_for_job(job) is not None:
        attempt, read_failed = _read_linked_attempt_for_job(job)
        if not read_failed and attempt:
            email = _registration_identity_email(job, job, attempt)
            if email and attempt.get("account_id") is not None:
                account = db.get_account(int(attempt["account_id"]))
                if account and str(account.get("email") or "").strip().casefold() == email:
                    return account
    batch_id = str(job.get("batch_id") or "").strip()
    if batch_id and email:
        try:
            # 同批次重复邮箱说明当前任务无法唯一对应到账号；不能因为另一个任务
            # 后来用同一地址建号，就把本任务误判成“已有账号，仅补跑 Codex”。
            if db.count_registration_jobs_by_batch_email(batch_id, email) > 1:
                logger.warning(
                    "[Service] 同批次邮箱关联不唯一，忽略按邮箱回查账号: batch_id=%s email=%s job_id=%s",
                    batch_id,
                    email,
                    job.get("id"),
                )
                return None
        except Exception:
            logger.exception(
                "[Service] 检查同批次邮箱唯一性失败，忽略按邮箱回查账号: batch_id=%s job_id=%s",
                batch_id,
                job.get("id"),
            )
            return None
    return db.get_account_by_email(email) if email else None


def _enrich_account_registration_state(account: dict | None) -> dict | None:
    """Attach normalized Attempt state for an actual resume decision.

    This is deliberately opt-in at execution boundaries. Retry-info list
    projections must stay query-bounded and therefore only use fields already
    present on the account row.
    """
    if not account or str(account.get("access_token") or "").strip():
        return account
    account_id = account.get("id")
    if account_id is None:
        return account
    try:
        from core.storage import registration as registration_store

        attempt = registration_store.get_latest_attempt_by_account(int(account_id))
    except Exception:
        return account
    if not attempt:
        return account
    enriched = dict(account)
    enriched["registration_target_status"] = attempt.get("target_status")
    enriched["registration_remote_account_state"] = attempt.get("remote_account_state")
    enriched["registration_checkpoint"] = enriched.get("registration_checkpoint") or attempt.get("checkpoint")
    return enriched


def _account_extra(account: dict | None) -> dict:
    if not account:
        return {}
    raw = account.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _pending_registration_password(account: dict | None) -> str:
    extra = _account_extra(account)
    checkpoint = str(extra.get("registration_checkpoint") or "").strip().lower()
    target_status = str(
        (account or {}).get("registration_target_status")
        or (account or {}).get("target_status")
        or ""
    ).strip().lower()
    if checkpoint != "email_verification_pending" and target_status != "email_verification_pending":
        return ""
    if str((account or {}).get("access_token") or "").strip():
        return ""
    return str(
        extra.get("account_password")
        or extra.get("registration_password")
        or extra.get("login_password")
        or ""
    ).strip()


def _restore_remail_registration_resume_context(
    *,
    email: str,
    registration_root_id: int,
    acquisition_id: str,
):
    """恢复 registration_resume 的原 Remail 上下文。

    优先读取注册根任务对应的持久领取意图；只有旧数据已经把 service token
    （或原订单号）保存到账号私有字段时，才允许在缺少意图的情况下恢复。这里
    不调用按邮箱搜索订单的兼容入口，避免重启后把同邮箱的其他订单误认成原订单。
    """
    address = str(email or "").strip()
    stable_id = str(acquisition_id or "").strip()
    if not address or not stable_id:
        raise RuntimeError("待邮箱验证账号缺少稳定 Remail 领取身份，无法继续验证")

    from core.storage import remail_orders

    intent = remail_orders.get_intent(stable_id, private=True)
    if intent:
        if (
            str(intent.get("owner_kind") or "") != "registration_root"
            or str(intent.get("owner_id") or "") != str(registration_root_id)
            or str(intent.get("acquisition_id") or "") != stable_id
        ):
            raise RuntimeError("原 Remail 领取意图与注册根任务不匹配，不能继续验证")
        from core.remail_order_coordinator import RemailOrderCoordinator

        coordinator = RemailOrderCoordinator()
        durable_account = coordinator._account_from_intent(intent)
        if not durable_account and str(intent.get("supplier_identity_ref") or "") != coordinator._supplier_ref():
            raise RuntimeError("原 Remail 订单供应商身份与当前配置不匹配，不能继续验证")
        account = coordinator.acquire(
            owner_kind="registration_root",
            owner_id=registration_root_id,
            acquisition_id=stable_id,
        )
    else:
        # 旧账号没有 remail_order_intents 时，只接受账号私有保存的 token/order_no。
        # restore_account_context 默认禁止按邮箱搜索最新订单。
        from core.remail_client import restore_account_context

        account = restore_account_context(address)
        if account is None:
            raise RuntimeError("原 Remail 领取意图和账号私有取件凭据均不存在，不能按邮箱猜测订单")

    if str(account.email or "").strip().casefold() != address.casefold():
        raise RuntimeError("原 Remail 订单邮箱与待验证账号不匹配，不能继续")
    return account


def _account_login_password(account: dict | None) -> str:
    """读取账号当前密码；旧账号兼容历史字段。"""
    extra = _account_extra(account)
    return str(
        extra.get("account_password")
        or extra.get("login_password")
        or extra.get("registration_password")
        or ""
    ).strip()


def _account_twofa_ready(account: dict | None, twofa_failed: bool = False) -> bool:
    if twofa_failed or not account or not str(account.get("totp_secret") or "").strip():
        return False
    extra = _account_extra(account)
    return not bool(extra.get("totp_setup_pending"))


def _account_plan_ready(account: dict | None) -> bool:
    return bool(account and str(account.get("plan_check_status") or "").strip().lower() == "success")


_DEACTIVATED_ATTEMPT_RETRY_REASON = "注册 Attempt 已被上游明确确认永久失效，禁止重跑"
_ATTEMPT_READ_FAILED_RETRY_REASON = "注册 Attempt 读取失败，请稍后重试"
_RETRYABLE_REGISTRATION_JOB_STATUSES = (
    "success",
    "failed",
    "partial_success",
    "stopped",
    "cancelled",
    "interrupted",
    "request_unknown",
    "manual_reconcile",
)


def _attempt_is_deactivated(attempt: dict | None) -> bool:
    return str((attempt or {}).get("target_status") or "").strip().lower() == "deactivated"


def _attempt_id_for_job(job: dict) -> int | None:
    """仅为已建立事实链接的任务读取 Attempt；旧轻量任务不触发存储初始化。"""
    try:
        attempt_id = int(job.get("attempt_id"))
    except (TypeError, ValueError):
        return None
    return attempt_id if attempt_id > 0 else None


def _root_job_id_for_job(job: dict) -> int:
    try:
        root_job_id = int(job.get("root_job_id") or job.get("id") or 0)
    except (TypeError, ValueError):
        return 0
    return root_job_id if root_job_id > 0 else 0


def _registration_acquisition_id_for_root(root_job_id: int | str) -> str:
    """同一注册根任务在首次领取、子 Run 和人工重跑间共用的领取 ID。"""
    try:
        value = int(root_job_id)
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        raise ValueError("注册根任务缺少有效 ID，不能创建 Remail 领取意图")
    return f"registration:{value}"


def _read_linked_attempt_for_job(job: dict) -> tuple[dict | None, bool]:
    """读取任务关联的 Attempt，并明确区分未关联与读取失败。"""
    attempt_id = _attempt_id_for_job(job)
    if attempt_id is None:
        return None, False
    try:
        from core.storage import registration as registration_store

        attempt = registration_store.get_attempt(attempt_id)
        # 已建立 durable link 却找不到 Attempt，说明事实链不完整；不能把
        # “查不到”当成“没有永久失效”，否则会放行一条无法核验邮箱状态的重跑。
        return attempt, attempt is None
    except Exception:
        logger.exception("[Job %s] 读取根注册 Attempt 失败", job.get("id"))
        return None, True


def _registration_identity_email(source: dict, root: dict, attempt: dict | None) -> str:
    """从同一根链核验邮箱；空根记录只复用 Attempt 已领取的身份。"""
    if not attempt:
        return ""
    root_id = _root_job_id_for_job(source)
    attempt_id = _attempt_id_for_job(source)
    if (not root_id or str(root.get("id")) != str(root_id) or not attempt_id
            or _attempt_id_for_job(root) != attempt_id or str(attempt.get("id")) != str(attempt_id)):
        return ""
    links = [attempt[key] for key in ("root_job_id", "source_root_job_id") if attempt.get(key) is not None]
    if not links or any(str(value) != str(root_id) for value in links):
        return ""
    root_email = str(root.get("email") or "").strip().casefold()
    snapshot = str(attempt.get("email_snapshot") or "").strip().casefold()
    source_email = str(source.get("email") or "").strip().casefold()
    expected = root_email or snapshot
    if not expected or snapshot != expected:
        return ""
    if not root_email:
        selected = str(root.get("email_source") or "").strip()
        if (not selected or str(source.get("email_source") or "").strip() != selected
                or (attempt.get("email_source") and str(attempt["email_source"]).strip() != selected)):
            return ""
        # 根任务领邮箱前即失败时没有地址；子任务仍必须保存同一领取结果。
        if not source_email and str(source.get("id")) == str(root_id):
            source_email = expected
    legacy = str(attempt.get("email") or "").strip().casefold()
    return expected if source_email == expected and (not legacy or legacy == expected) else ""


def _registration_identity_facts_match(
    source: dict,
    root_job: dict,
    account: dict | None,
    attempt: dict | None,
    *,
    root_id: int,
) -> bool:
    """核验任务根链、原邮箱、账号和 Attempt 是否属于同一身份。"""
    if not account or not attempt:
        return False
    if not root_job:
        return False
    try:
        if int(root_job.get("id") or 0) != root_id:
            return False
        account_id = int(account.get("id"))
        attempt_id = int(attempt.get("id"))
        source_attempt_id = int(source.get("attempt_id"))
        root_attempt_id = int(root_job.get("attempt_id"))
    except (TypeError, ValueError):
        return False
    if account_id <= 0 or attempt_id <= 0 or source_attempt_id != attempt_id or root_attempt_id != attempt_id:
        return False
    for item in (source, root_job, attempt):
        linked_account_id = item.get("account_id")
        if linked_account_id is not None:
            try:
                if int(linked_account_id) != account_id:
                    return False
            except (TypeError, ValueError):
                return False
    for field in ("root_job_id", "source_root_job_id"):
        linked_root_id = attempt.get(field)
        if linked_root_id is not None:
            try:
                if int(linked_root_id) != root_id:
                    return False
            except (TypeError, ValueError):
                return False
    if attempt.get("root_job_id") is None and attempt.get("source_root_job_id") is None:
        return False
    expected_email = _registration_identity_email(source, root_job, attempt)
    if not expected_email:
        return False
    for address in (
        account.get("email"),
        attempt.get("email_snapshot"),
    ):
        if str(address or "").strip().casefold() != expected_email:
            return False
    legacy_attempt_email = str(attempt.get("email") or "").strip()
    if legacy_attempt_email and legacy_attempt_email.casefold() != expected_email:
        return False
    return True


def _roxy_resume_facts_match(
    source: dict, root_job: dict, account: dict | None, attempt: dict | None, *, root_id: int,
) -> bool:
    """恢复资料完整时继续同一身份，不以历史失败标记阻断续跑。"""
    if not _registration_identity_facts_match(source, root_job, account, attempt, root_id=root_id):
        return False
    extra = _account_extra(account)
    registration_checkpoint = str(
        extra.get("registration_checkpoint")
        or account.get("registration_checkpoint")
        or ""
    ).strip().lower()
    if registration_checkpoint != "email_verification_pending":
        return False
    if not _pending_registration_password(account):
        return False
    attempt_checkpoint = str(attempt.get("checkpoint") or "").strip().lower()
    if attempt_checkpoint in {
        "core_persisted", "completed",
    }:
        return False
    if attempt_checkpoint not in {
        "password_request_started", "password_confirmed", "otp_started", "otp_confirmed",
        "account_request_started", "account_confirmed", "token_obtained", "postprocessing",
        "manual_reconcile", "failed",
    }:
        return False
    attempt_target = str(attempt.get("target_status") or "").strip().lower()
    if attempt_target in {
        "completed", "deactivated",
    }:
        return False
    return True


def _pre_account_identity_facts_match(
    job: dict, root: dict | None, attempt: dict | None, *, allow_unclaimed_email: bool = False,
) -> bool:
    """无账号记录时，自动确认原任务链和 Attempt 使用同一邮箱。"""
    if not root or not attempt:
        return False
    root_id = _root_job_id_for_job(job)
    if str(root.get("id")) != str(root_id):
        return False
    if any(item.get("account_id") is not None for item in (job, root, attempt)):
        return False
    if not _attempt_id_for_job(job) or _attempt_id_for_job(job) != _attempt_id_for_job(root):
        return False
    if str(attempt.get("id")) != str(_attempt_id_for_job(job)):
        return False
    if str(attempt.get("root_job_id") or attempt.get("source_root_job_id")) != str(root_id):
        return False
    if any(attempt.get(key) is not None and str(attempt[key]) != str(root_id)
           for key in ("root_job_id", "source_root_job_id")):
        return False
    email = _registration_identity_email(job, root, attempt)
    if (not str(root.get("email") or "").strip() and not str(attempt.get("email_snapshot") or "").strip()
            and allow_unclaimed_email):
        # 邮箱尚未领取、注册尚未开始时没有原邮箱可复用；仍核对同一来源及 Attempt，
        # 让新 Run 继续领取。已有邮箱、密码或任何远端提交事实都不能进入此分支。
        source = str(root.get("email_source") or "").strip()
        return bool(
            source and str(job.get("email_source") or "").strip() == source
            and (not attempt.get("email_source") or str(attempt["email_source"]).strip() == source)
            and not any(str(value or "").strip() for value in (
                job.get("email"), attempt.get("email_snapshot"), attempt.get("email"),
            ))
            and attempt.get("checkpoint") == "created"
            and attempt.get("remote_identity_state") == "not_started"
            and attempt.get("remote_account_state") == "not_started"
            and attempt.get("local_account_state") in {"none", "not_started"}
            and (attempt.get("data") or {}).get("has_password") is not True
        )
    return bool(email)


def _pre_account_resume_facts_match(job: dict, root: dict | None, attempt: dict | None) -> bool:
    """原密码已保存时直接续跑；旧提交未知不要求人工核对。"""
    if not _pre_account_identity_facts_match(job, root, attempt):
        return False
    return (
        (attempt.get("data") or {}).get("has_password") is True
        and attempt.get("checkpoint") in {
            "password_request_started", "password_confirmed", "otp_started", "otp_confirmed",
            "account_request_started", "account_confirmed", "token_obtained", "postprocessing",
            "manual_reconcile", "failed",
        }
        and attempt.get("local_account_state") in {"none", "not_started"}
        and attempt.get("remote_account_state") != "confirmed"
        and attempt.get("target_status") not in {"completed", "deactivated"}
    )


def _private_registration_resume_password(job: dict) -> str:
    """执行时读取原 Attempt 私有密码，不创建待验证账号或替换凭据。"""
    from core.storage import registration

    root_id = _root_job_id_for_job(job)
    root = job if root_id == int(job.get("id") or 0) else db.get_job(root_id)
    attempt, read_failed = _read_linked_attempt_for_job(job)
    if read_failed or not _pre_account_resume_facts_match(job, root, attempt):
        raise RuntimeError("原任务邮箱或密码恢复资料不完整，无法继续原注册任务")
    private = registration.get_private_resume_context(int(attempt["id"]), email=str(job["email"]).strip())
    password = private.get("password")
    if not isinstance(password, str) or not password.strip():
        raise RuntimeError("原注册 Attempt 缺少已保存密码，无法继续原任务")
    return password


def _pre_account_retry_facts_match(job: dict, root: dict | None, attempt: dict | None) -> bool:
    """未落库任务按原邮箱和 Attempt 身份重跑，远端未知状态不关闭入口。"""
    if not _pre_account_identity_facts_match(job, root, attempt, allow_unclaimed_email=True):
        return False
    # 新 Run 复用原邮箱和 Attempt；旧回执、远端状态与历史检查点不作为重跑门槛。
    return (
        attempt.get("local_account_state") not in {"persisted", "saved"}
        and attempt.get("target_status") not in {"deactivated", "completed"}
    )


def _pre_account_submission_retry_reason(attempt: dict | None) -> str:
    """解释为什么账号尚未落库的注册任务不能重新派发。"""
    if not attempt or attempt.get("id") is None:
        return "缺少可核验的原邮箱或注册 Attempt，无法重跑原任务"
    return "缺少可核验的原邮箱或注册 Attempt，无法重跑原任务"


def _build_retry_info(
    job: dict,
    *,
    account: dict | None,
    successful_retry: dict | None,
    attempt: dict | None = None,
    attempt_read_failed: bool = False,
    root_job: dict | None = None,
) -> dict:
    """纯函数版本的任务重试投影；列表页可批量准备关联数据后复用。"""
    status = str(job.get("status") or "")
    info = {
        "retryable": False,
        "retry_action": None,
        "retry_label": None,
        "retry_reason": None,
        "display_status": status,
        "next_actions": [],
    }
    if status not in _RETRYABLE_REGISTRATION_JOB_STATUSES:
        return info

    if attempt_read_failed:
        info.update({
            "display_status": "failed",
            "retry_reason": _ATTEMPT_READ_FAILED_RETRY_REASON,
        })
        return info

    if _attempt_is_deactivated(attempt):
        info.update({
            "display_status": "failed",
            "retry_reason": _DEACTIVATED_ATTEMPT_RETRY_REASON,
        })
        return info

    attempt_target = str((attempt or {}).get("target_status") or "").strip().lower()
    root_id = _root_job_id_for_job(job)
    resume_root = job if root_id == int(job.get("id") or 0) else root_job
    error = str(job.get("error_message") or job.get("error") or "")
    if "remail_order_request_unknown" in error or ("Remail" in error and "订单结果待核验" in error):
        info["retry_reason"] = "邮箱订单结果待核验，不能重复下单；需先恢复原订单邮箱"
        return info
    pre_account_retryable = account is None and _pre_account_retry_facts_match(
        job, resume_root, attempt,
    )
    private_resume = account is None and _pre_account_resume_facts_match(job, resume_root, attempt)
    if status in {"request_unknown", "manual_reconcile"} or attempt_target in {"request_unknown", "manual_reconcile"}:
        info["display_status"] = "failed"
        can_resume = private_resume or bool(
            account
            and resume_root
            and _roxy_resume_facts_match(job, resume_root, account, attempt, root_id=root_id)
        )
        can_retry = pre_account_retryable
        confirmed_core = bool(
            account and str(account.get("access_token") or "").strip()
            and attempt and attempt.get("remote_account_state") == "confirmed"
            and attempt.get("local_account_state") in {"persisted", "saved"}
            and _registration_identity_facts_match(job, resume_root, account, attempt, root_id=root_id)
        )
        if not can_resume and not can_retry and not confirmed_core:
            info["retry_reason"] = "缺少可核验的原邮箱或账号恢复资料，无法重跑原任务"
            return info
        if can_retry:
            info["retry_reason"] = "注册尚未进入账号创建阶段，复用原邮箱重跑"

    account_status = str((account or {}).get("account_status") or "").strip().lower()
    codex_status = str((account or {}).get("codex_status") or "").strip().lower()
    if account_status == "deactivated" or codex_status == "deactivated":
        info.update({
            "display_status": "failed",
            "retry_reason": "账号已被上游明确确认永久失效，禁止补跑注册后处理",
        })
        return info

    if successful_retry is not None:
        info["retry_reason"] = f"后续重试任务 #{successful_retry.get('id')} 已成功"
        info["successful_retry_job_id"] = successful_retry.get("id")
        return info

    if private_resume:
        info.update({
            "display_status": "failed",
            "retryable": True,
            "retry_action": "registration_resume",
            "retry_label": "继续注册",
            "retry_reason": "复用原邮箱和已保存密码，自动继续同一注册 Attempt",
            "next_actions": [{"action": "registration_resume", "retryable": True,
                              "reason": "使用原密码自动继续认证"}],
        })
        return info

    if account is None and not pre_account_retryable:
        info["display_status"] = "failed"
        info["retry_reason"] = _pre_account_submission_retry_reason(attempt)
        return info

    if status == "success" and account is None:
        return info
    if account and db.account_is_deactivated(account):
        info.update({
            "display_status": "deactivated",
            "retry_reason": "账号已废号，不能补跑 Codex",
            "next_actions": [],
        })
        return info
    pending_password = _pending_registration_password(account)
    pending_checkpoint = str(
        _account_extra(account).get("registration_checkpoint")
        or (account or {}).get("registration_checkpoint")
        or (account or {}).get("registration_target_status") or ""
    ).strip().lower()
    if (account and not str(account.get("access_token") or "").strip()
            and pending_checkpoint == "email_verification_pending" and not pending_password):
        info["retry_reason"] = "待验证账号缺少已保存密码，不能续跑"
        return info
    if account and pending_password:
        if not resume_root or not _roxy_resume_facts_match(
            job, resume_root, account, attempt, root_id=root_id,
        ):
            info["retry_reason"] = "待验证账号与原注册 Attempt 未核验，不能续跑"
            return info
        info.update({
            "display_status": "failed",
            "retryable": True,
            "retry_action": "registration_resume",
            "retry_label": "继续邮箱验证",
            "retry_reason": "注册尚未完成；复用原邮箱和已保存密码继续同一账号验证",
            "next_actions": [{
                "action": "registration_resume",
                "reason": "同一 Attempt 继续完成邮箱验证",
                "retryable": True,
            }],
        })
        return info

    steps = job.get("progress_steps") if isinstance(job.get("progress_steps"), dict) else {}
    codex_step = steps.get("codex") if isinstance(steps.get("codex"), dict) else {}
    codex_step_state = str(codex_step.get("state") or "").strip().lower()
    # 注册任务明确记录为 skipped 时，以任务运行事实为准。历史上曾在注册已
    # 跳过 Codex 后误创建补跑任务，随后把账号的兼容字段写成 failed；不能让
    # 这个旧字段再次把“跳过”展示成 Codex 失败。
    if codex_step_state == "skipped" and codex_status != "deactivated":
        codex_status = "skipped"
    twofa_step = steps.get("twofa") if isinstance(steps.get("twofa"), dict) else {}
    twofa_failed = str(twofa_step.get("state") or "") == "failed"
    if not twofa_failed and account:
        try:
            import json

            extra = json.loads(str(account.get("extra_json") or "{}"))
            twofa = extra.get("twofa") if isinstance(extra, dict) else None
            twofa_failed = isinstance(twofa, dict) and str(twofa.get("status") or "") == "failed"
        except Exception:
            pass

    registration_snapshot = job.get("config_snapshot") if isinstance(job.get("config_snapshot"), dict) else None
    password_required = bool(registration_snapshot.get("password_enabled", True)) if registration_snapshot else True
    plan_check_required = bool(registration_snapshot.get("plan_check_enabled", True)) if registration_snapshot else True
    twofa_required = (
        bool(registration_snapshot.get("twofa_enabled", True))
        if registration_snapshot
        else str(twofa_step.get("state") or "").strip().lower() != "skipped"
    )
    codex_required = bool(registration_snapshot.get("codex_enabled", True)) if registration_snapshot else codex_status != "skipped"
    setup_missing = bool(account) and (
        (password_required and not _account_login_password(account))
        or (plan_check_required and not _account_plan_ready(account))
        or (twofa_required and not _account_twofa_ready(account, twofa_failed))
    )

    if account and job.get("account_id") is not None:
        codex_complete = (not codex_required) or codex_status in {"success", "skipped"}
        info["display_status"] = (
            "success"
            if codex_complete and not setup_missing
            else "partial_success"
        )

    # Expose the durable action vocabulary alongside the legacy single-action
    # projection.  A single account can legitimately need more than one
    # independent follow-up (for example Codex plus plan check).
    if account:
        twofa_state = "failed" if twofa_failed else "success" if _account_twofa_ready(account) else "pending"
        codex_state = codex_status or "failed"
        plan_state = "success" if _account_plan_ready(account) else "pending"
        summary = summarize_postprocess(
            core_success=True,
            password_present=bool(_account_login_password(account)),
            password_required=password_required,
            outcomes={
                "twofa": {"status": twofa_state, "ok": twofa_state == "success"},
                "codex": {"status": codex_state, "ok": codex_state in {"success", "skipped"}},
                "plan_check": {"status": plan_state, "ok": plan_state == "success"},
            },
            twofa_required=twofa_required,
            codex_enabled=codex_required,
            plan_check_required=plan_check_required,
        )
        info["next_actions"] = [action.as_dict() for action in summary.next_actions]

    if account:
        if codex_status == "deactivated":
            info["next_actions"] = []
            info["retry_reason"] = "账号已废号，不能补跑 Codex"
            return info
        if (
            setup_missing
            and codex_status in {"success", "skipped"}
            and bool(_account_login_password(account))
            and _account_twofa_ready(account, twofa_failed)
            and not _account_plan_ready(account)
        ):
            info.update({
                "retryable": True,
                "retry_action": "plan_check",
                "retry_label": "重试套餐查询",
                "retry_reason": "账号核心、密码和 2FA 已就绪，仅套餐状态待确认",
            })
            return info
        if codex_status in {"success", "skipped"}:
            if setup_missing:
                config_only = not twofa_failed and (
                    not _account_login_password(account)
                    or not _account_plan_ready(account)
                )
                info.update({
                    "retryable": True,
                    "retry_action": "twofa",
                    "retry_label": "补齐账号配置" if config_only else "重试 2FA",
                    "retry_reason": (
                        "账号和 Codex 已完成，重新登录补齐账号密码、套餐和 Authenticator 2FA"
                        if codex_status == "success"
                        else "账号已创建，Codex 当前为跳过状态，重新登录补齐账号配置"
                    ),
                })
                return info
            info["retry_reason"] = (
                "账号和 Codex 授权均已完成"
                if codex_status == "success"
                else "账号已完成，Codex 自动授权已跳过"
            )
            return info
        if codex_status == "attention_required":
            info["next_actions"] = []
            info["retry_reason"] = "Codex 登录验证结果待核对，不能自动重新提交"
            return info
        info.update({
            "retryable": True,
            "retry_action": "codex",
            "retry_label": "补跑 Codex",
        })
        return info

    info.update({
        "retryable": True,
        "retry_action": "registration",
        "retry_label": "重试",
        "next_actions": [{
            "action": "registration_new",
            "reason": "未发现已持久化账号，可按 Attempt 恢复策略重新开始",
            "retryable": True,
        }],
    })
    return info


def get_retry_info(job: dict, *, account_override: dict | None = None) -> dict:
    """返回给 API/UI 的重试能力描述，不依赖前端猜测错误阶段。"""
    status = str(job.get("status") or "")
    if status not in _RETRYABLE_REGISTRATION_JOB_STATUSES:
        return _build_retry_info(job, account=None, successful_retry=None)
    successful_retry = db.get_successful_retry_for_job(int(job.get("id") or 0))
    account = None if successful_retry is not None else (
        account_override if account_override is not None else _account_for_job(job)
    )
    attempt, attempt_read_failed = _read_linked_attempt_for_job(job)
    roots = _retry_roots_for_jobs([job])
    return _build_retry_info(
        job,
        account=account,
        successful_retry=successful_retry,
        attempt=attempt,
        attempt_read_failed=attempt_read_failed,
        root_job=roots.get(_root_job_id_for_job(job)),
    )


def _retry_jobs_by_ids(job_ids: list[int]) -> dict[int, dict]:
    """批量读取重试来源，避免任务中心每行单独查询。"""
    if not job_ids:
        return {}
    from core import record_store

    rows = record_store.list_rows(record_store.JOBS, where='id = ANY(%s)', params=(job_ids,))
    return {int(row["id"]): row for row in rows}


def _retry_roots_for_jobs(jobs: list[dict]) -> dict[int, dict]:
    """子任务续跑必须核对根记录；缺失或读取失败时保持拒绝。"""
    ids = sorted({
        _root_job_id_for_job(job) for job in jobs
        if _root_job_id_for_job(job) != int(job.get("id") or 0)
    })
    try:
        return _retry_jobs_by_ids(ids)
    except Exception:
        logger.exception("读取续跑根任务失败，保持身份校验拒绝")
        return {}


def get_retry_info_bulk(jobs: list[dict]) -> dict[int, dict]:
    """批量生成列表重试信息，查询次数固定，不随当前页行数增长。"""
    rows = [dict(job) for job in (jobs or [])]
    terminal = [
        job for job in rows
        if str(job.get("status") or "") in _RETRYABLE_REGISTRATION_JOB_STATUSES
    ]
    successful_by_job = db.get_successful_retries_for_jobs(terminal)
    needs_accounts = [job for job in terminal if int(job.get("id") or 0) not in successful_by_job]
    roots = _retry_roots_for_jobs(terminal)
    root_ids = sorted({
        root_job_id
        for job in terminal
        if _attempt_id_for_job(job) is not None
        for root_job_id in [_root_job_id_for_job(job)]
        if root_job_id > 0
    })
    attempts_by_root = {}
    attempt_read_failed_roots: set[int] = set()
    if root_ids:
        try:
            from core.storage import registration as registration_store

            attempts_by_root = registration_store.get_attempts_for_root_jobs(root_ids)
        except Exception:
            logger.exception("批量读取根注册 Attempt 失败")
            # 任何已建立 Attempt link 的行都必须 fail closed；不能因一次
            # 批量读取异常而重新显示“重新执行注册”。
            attempt_read_failed_roots.update(root_ids)
        else:
            # 查询成功但缺少某个已链接根任务，同样属于事实链损坏。
            attempt_read_failed_roots.update(set(root_ids) - set(attempts_by_root))
    account_lookup_jobs = []
    for job in needs_accounts:
        lookup = job
        if not str(job.get("email") or "").strip():
            root_id = _root_job_id_for_job(job)
            attempt = attempts_by_root.get(root_id)
            root = roots.get(root_id) or job
            email = _registration_identity_email(job, root, attempt)
            if email:
                lookup = dict(job, email=email, account_id=job.get("account_id") or attempt.get("account_id"))
        account_lookup_jobs.append(lookup)
    accounts_by_job = db.get_accounts_for_jobs(account_lookup_jobs)
    return {
        int(job.get("id") or 0): _build_retry_info(
            job,
            account=accounts_by_job.get(int(job.get("id") or 0)),
            successful_retry=successful_by_job.get(int(job.get("id") or 0)),
            attempt=attempts_by_root.get(_root_job_id_for_job(job)),
            attempt_read_failed=_root_job_id_for_job(job) in attempt_read_failed_roots,
            root_job=roots.get(_root_job_id_for_job(job)),
        )
        for job in rows
    }


def attach_registration_resume_retry_info(tasks: list[dict]) -> None:
    """原注册与续跑按钮统一使用执行入口的校验，兼容旧待确认记录。"""
    task_actions = {
        "registration": "registration_retry", "registration_resume": "registration_resume",
        "codex": "codex_retry", "twofa": "twofa_retry", "plan_check": "plan_check",
    }
    selected: list[tuple[dict, int]] = []
    for task in tasks:
        if task.get("task_type") not in {"registration", "registration_resume"} or task.get("source_system") != "registration_chains":
            continue
        if task.get("target_status") not in {
            "not_created", "email_verification_pending", "request_unknown",
            "attention_required", "manual_reconcile", "account_available",
        }:
            continue
        task["retryable"] = False
        if task.get("status") in {"queued", "running", "stopping", "cancelling", "settling", "waiting"}:
            task["next_actions"] = []
            task["retry_reason"] = "任务仍在执行"
            continue
        source_id = next((
            action.get("source_job_id") for action in task.get("next_actions") or []
            if isinstance(action, dict) and action.get("action") in task_actions.values()
        ), None)
        if not source_id:
            runs = task.get("runs") or []
            latest = runs[-1] if runs else {}
            source_id = latest.get("source_id") if latest.get("source_system") == "registration_jobs" else None
        if not source_id:
            source_id = task.get("latest_legacy_job_id") or (task.get("data") or {}).get("latest_legacy_job_id")
        if not source_id:
            source_id = str(task.get("source_id") or "").split(":", 1)[0]
        task["next_actions"] = []
        task["retry_reason"] = "注册任务来源缺失，不能核验续跑身份"
        if str(source_id).isdigit():
            selected.append((task, int(source_id)))
    if not selected:
        return
    try:
        jobs = _retry_jobs_by_ids(sorted({ident for _, ident in selected}))
        infos = get_retry_info_bulk(list(jobs.values()))
    except Exception:
        logger.exception("任务中心读取注册重试能力失败，暂不展示续跑按钮")
        return
    for task, ident in selected:
        info = infos.get(ident) or {}
        task["retry_reason"] = info.get("retry_reason") or task["retry_reason"]
        if info.get("retryable") and info.get("retry_action") in task_actions:
            task["retryable"] = True
            task["retry_reason"] = info.get("retry_reason") or "可以重跑未完成步骤"
            action = task_actions[info["retry_action"]]
            task["next_actions"] = [{"action": action, "label": info.get("retry_label") or "重跑", "source_job_id": ident}]


def retry_job(
    job_id: int,
    workers: int | None = None,
    *,
    batch_id: str | None = None,
    batch_index: int | None = None,
    batch_size: int | None = None,
    registration_driver: str | None = None,
    debug_enabled: bool | None = None,
) -> dict:
    """智能重试终态任务：未生成账号则重新注册，已有账号则仅补跑 Codex。"""
    if registration_driver is not None and registration_driver != "roxy":
        return {"ok": False, "error": "仅支持为单个待验证账号选择 roxy 续跑", "status": 400}
    if debug_enabled is not None and type(debug_enabled) is not bool:
        return {"ok": False, "error": "debug_enabled 必须是布尔值", "status": 400}
    source = db.get_job(job_id)
    if source is None:
        return {"ok": False, "error": "任务不存在", "status": 404}
    # 终态会先于 worker 的代理、调试记录器及浏览器资源收口写入数据库。
    # 等原 worker 完成退出后才能重跑，避免旧清理动作关闭新任务复用的现场。
    if is_job_worker_active(job_id):
        return {"ok": False, "error": "原任务仍在收口，暂不能重跑", "status": 409}

    account = _enrich_account_registration_state(_account_for_job(source))
    retry_info = get_retry_info(source, account_override=account)
    if not retry_info["retryable"]:
        reason = retry_info.get("retry_reason") or f"当前状态不支持重试：{source.get('status')}"
        return {"ok": False, "error": reason, "status": 409}

    action = str(retry_info["retry_action"])
    retry_debug_enabled = bool(source.get("debug_enabled", False)) if debug_enabled is None else debug_enabled
    debug_notice = ({
        "debug_enabled": False,
        "debug_warning": "此类补跑暂不支持完整网络抓包，已正常入队并保留步骤日志",
    } if retry_debug_enabled and action in {"codex", "plan_check"} else {})
    root_id = int(source.get("root_job_id") or source.get("id") or job_id)
    root_record = db.get_job(root_id)
    root_job = root_record or source
    attempt_job = root_job if _attempt_id_for_job(root_job) is not None else source
    attempt, attempt_read_failed = _read_linked_attempt_for_job(attempt_job)
    if attempt_read_failed:
        return {"ok": False, "error": _ATTEMPT_READ_FAILED_RETRY_REASON, "status": 409}
    if _attempt_is_deactivated(attempt):
        return {"ok": False, "error": _DEACTIVATED_ATTEMPT_RETRY_REASON, "status": 409}
    if action == "registration_resume" and not (
        _roxy_resume_facts_match(source, root_job, account, attempt, root_id=root_id)
        or (account is None and _pre_account_resume_facts_match(source, root_job, attempt))
    ):
        return {
            "ok": False,
            "error": "续跑仅适用于原邮箱、保存密码及注册 Attempt 均可核验的待验证账号",
            "status": 409,
        }
    if registration_driver == "roxy":
        if action != "registration_resume":
            return {
                "ok": False,
                "error": "Roxy 续跑仅适用于原邮箱、保存密码及注册 Attempt 均可核验的待验证账号",
                "status": 409,
            }
    if batch_id is None:
        batch_id = str(root_job.get("batch_id") or source.get("batch_id") or "") or None
        batch_index = int(root_job.get("batch_index") or source.get("batch_index") or 1)
        batch_size = int(root_job.get("batch_size") or source.get("batch_size") or 1)
    if workers is None:
        workers = max(1, int(root_job.get("batch_workers") or source.get("batch_workers") or 1))
    source_email = str(source.get("email") or "").strip()
    root_email = str(root_job.get("email") or "").strip()
    email = str((account or {}).get("email") or source_email or "").strip()
    account_id = int(account["id"]) if account and account.get("id") is not None else None
    if action == "registration":
        # 普通注册重跑属于同一根任务链；根任务保存的地址才是不可替换的原邮箱。
        # 仅为兼容根记录尚未回填邮箱的历史链，才退回当前失败任务自身的快照。
        email = root_email or source_email or _registration_identity_email(source, root_job, attempt)
    elif action == "registration_resume" and not email:
        email = _registration_identity_email(source, root_job, attempt)
    if action == "registration":
        if root_record is None and root_id != int(source.get("id") or 0):
            return {
                "ok": False,
                "error": "原注册根任务不存在，无法确认原邮箱来源",
                "status": 409,
            }
        try:
            from core.email_provider import validate_email_source

            retry_email_source = validate_email_source(str(root_job.get("email_source") or ""))
        except ValueError:
            return {
                "ok": False,
                "error": "原邮箱来源缺失或不明确，不能切换来源或邮箱重跑",
                "status": 409,
            }
    else:
        retry_email_source = str(source.get("email_source") or root_job.get("email_source") or "outlook")
    if action == "plan_check":
        if not email or account_id is None:
            return {"ok": False, "error": "已保存账号信息不完整，无法查询套餐", "status": 409}
        try:
            from core.plan_check_service import enqueue_account_plan_check

            queued = enqueue_account_plan_check(
                account_id=account_id,
                email=email,
                access_token=str((account or {}).get("access_token") or ""),
                trigger="registration_retry_plan_check",
            )
        except Exception as exc:
            return {"ok": False, "error": f"套餐查询入队异常：{type(exc).__name__}: {exc}", "status": 503}
        if not queued.get("accepted") and not queued.get("busy"):
            return {"ok": False, "error": queued.get("error") or "套餐查询入队失败", "status": 409}
        return {
            "ok": True,
            "created": bool(queued.get("accepted")),
            "reused": bool(queued.get("busy")),
            "retry_action": action,
            "source_job_id": int(job_id),
            "operation_task_id": queued.get("task_id"),
            "run_id": queued.get("run_id"),
            "message": "套餐查询已入队" if queued.get("accepted") else "已有套餐查询正在执行",
            **debug_notice,
        }
    if action == "codex":
        # 注册任务只提供父上下文；Codex 补跑本身由原生 operation run 执行，
        # 不再额外创建 registration_job + account_action_task 两份重复记录。
        from core import codex_operation_service, operation_task_store

        parent = operation_task_store.find_task_by_source("registration_jobs", str(job_id))
        queued = codex_operation_service.submit(
            email,
            trigger="registration_job_retry",
            parent_task_id=int(parent["id"]) if parent else None,
        )
        if not queued.get("accepted"):
            return {
                "ok": False,
                "error": queued.get("error") or "Codex 补跑入队失败",
                "status": 503 if queued.get("unavailable") else 409,
                **queued,
            }
        return {
            "ok": True,
            "created": True,
            "reused": False,
            "message": f"已创建 Codex 子任务 #{queued['task_id']}，attempt #{queued['run_id']}",
            "source_job_id": int(job_id),
            "retry_action": action,
            "operation_task_id": queued["task_id"],
            "run_id": queued["run_id"],
            "job": source,
            **debug_notice,
        }
    reserved_account_action = False
    if action == "twofa":
        if not email or account_id is None:
            return {"ok": False, "error": "已保存账号信息不完整，无法执行账号补跑", "status": 409}
        if not codex_retry_service.reserve(email):
            return {"ok": False, "error": "该账号正在执行 Codex/2FA 补跑，请稍候", "status": 409}
        reserved_account_action = True

    retry_snapshot = registration_options_for_job(source)
    if registration_driver == "roxy":
        retry_snapshot["registration_driver"] = "roxy"
    try:
        job_type = {
            "codex": "codex_retry",
            "twofa": "twofa_retry",
            "registration_resume": "registration_resume",
        }.get(action, "registration")
        job, created = db.create_retry_job(
            int(job_id),
            job_type=job_type,
            email_source=retry_email_source,
            email=(email or None) if action in {"codex", "twofa", "registration_resume", "registration"} else None,
            account_id=account_id if action in {"codex", "twofa", "registration_resume"} else None,
            batch_id=batch_id,
            batch_index=batch_index,
            batch_size=batch_size,
            batch_workers=workers,
            data={"config_snapshot": retry_snapshot},
        )
    except LookupError as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        return {"ok": False, "error": str(exc), "status": 404}
    except ValueError as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        return {"ok": False, "error": str(exc), "status": 409}

    if not created:
        if reserved_account_action:
            codex_retry_service.release(email)
        if debug_enabled is not None and bool(job.get("debug_enabled", False)) != debug_enabled:
            return {"ok": False, "error": "同一 Attempt 已有不同调试设置的运行，不能中途切换抓包", "status": 409}
        if registration_driver == "roxy":
            active_snapshot = job.get("config_snapshot")
            if not isinstance(active_snapshot, dict):
                active_data = job.get("data")
                active_snapshot = active_data.get("config_snapshot") if isinstance(active_data, dict) else None
            if not isinstance(active_snapshot, dict) or active_snapshot.get("registration_driver") != "roxy":
                return {
                    "ok": False,
                    "error": "同一 Attempt 已有其他驱动的任务在排队或运行",
                    "status": 409,
                }
        return {
            "ok": True,
            "created": False,
            "reused": True,
            "message": f"已有重试任务 #{job['id']} 在排队或运行中",
            "source_job_id": int(job_id),
            "retry_action": action,
            "job": job,
        }

    account_task_id = None
    try:
        if retry_debug_enabled and action in {"registration", "registration_resume", "twofa"}:
            from core.registration_debug import patch_job
            if not patch_job(
                int(job["id"]),
                debug_enabled=True,
                debug_state="pending",
                debug_policy=dict(source.get("debug_policy") or {
                    "capture_network": True,
                    "hold_on_failure": True,
                    "preserve_success_browser": False,
                }),
            ):
                raise RuntimeError("重试任务调试设置保存失败")
            debug_job = db.get_job(int(job["id"]))
            if not debug_job or debug_job.get("debug_enabled") is not True:
                raise RuntimeError("重试任务调试设置未确认保存成功")
            job = debug_job

        if action in {"codex", "twofa"}:
            account_task_id = account_task_store.create_task(
                task_type="codex_retry" if action == "codex" else "twofa_retry",
                account_id=int(account_id),
                email=email,
                trigger="registration_job_retry",
            )
        if action == "codex":
            db.update_account_codex_status(email, "retrying", None)
        with _executor_lock:
            executor = get_executor(max_workers=workers)
            if action == "codex":
                executor.submit(
                    _run_codex_retry_job,
                    job["id"],
                    job["log_file"],
                    email,
                    int(account_id),
                    account_task_id,
                )
            elif action == "twofa":
                executor.submit(
                    _run_twofa_retry_job,
                    job["id"],
                    job["log_file"],
                    email,
                    int(account_id),
                    account_task_id,
                )
            else:
                executor.submit(_run_one_job, job["id"], job["log_file"])
    except Exception as exc:
        if reserved_account_action:
            codex_retry_service.release(email)
        if action == "codex":
            db.update_account_codex_status(email, "failed", f"队列提交失败：{type(exc).__name__}: {exc}"[:500])
        if account_task_id:
            account_task_store.finish_task(
                account_task_id,
                status="failed",
                message="账号补跑任务入队失败",
                error=f"{type(exc).__name__}: {exc}",
            )
        db.update_job(
            int(job["id"]),
            status="failed",
            error=f"队列提交失败：{type(exc).__name__}: {exc}"[:500],
            completed_at=_now_iso(),
        )
        logger.exception("[Service] 重试任务 #%s 提交线程池失败", job["id"])
        return {"ok": False, "error": "重试任务创建成功，但提交执行失败", "status": 500, "job": db.get_job(int(job["id"]))}

    return {
        "ok": True,
        "created": True,
        "reused": False,
        "message": f"已创建重试任务 #{job['id']}（{ {'codex': 'Codex 补跑', 'twofa': '账号配置补跑', 'registration_resume': '继续邮箱验证'}.get(action, '完整注册') }）",
        "source_job_id": int(job_id),
        "retry_action": action,
        "job": job,
    }


def cancel_pending_jobs(*, batch_id: str | None = None) -> int:
    """
    把 status=pending 的任务批量改成 cancelled，避免它们被执行。
    如果传入 batch_id，只处理指定批次。
    已经在 running 的任务不动（线程池中无法中途打断）。
    返回成功取消的数量。
    """
    cancelled = db.cancel_pending_jobs(batch_id=batch_id)
    scope = f"批次 {batch_id}" if batch_id else "全部"
    logger.info("[Service] 已取消 %s 个排队任务（范围=%s）", cancelled, scope)
    return cancelled


def request_stop_job(job_id: int) -> dict:
    """手动停止单个注册任务。pending 直接取消；running 设置停止标记，运行线程会在检查点退出。"""
    job = db.get_job(job_id)
    if not job:
        return {"ok": False, "error": "任务不存在", "status": 404}
    status = job.get("status")
    now_iso = _now_iso()
    if status == "pending":
        changed = db.transition_job_status(
            job_id,
            ("pending",),
            "cancelled",
            completed_at=now_iso,
            error_message="用户手动停止/取消排队",
        )
        if not changed:
            latest = db.get_job(job_id) or {}
            return request_stop_job(job_id) if latest.get("status") != status else {
                "ok": False,
                "error": "任务状态刚刚发生变化，请刷新后重试",
                "status": 409,
            }
        _append_job_log(job_id, "用户手动停止：任务尚未运行，已取消排队。")
        return {"ok": True, "message": "排队任务已取消", "job_id": job_id, "state": "cancelled"}
    if status in ("success", "partial_success", "failed", "cancelled", "stopped", "interrupted"):
        return {"ok": True, "message": f"任务已结束：{status}", "job_id": job_id, "state": status}
    if status in ("running", "stopping"):
        with _STOP_LOCK:
            active = int(job_id) in _ACTIVE_JOBS
            ev = _STOP_EVENTS.get(int(job_id)) if active else None
            if ev is not None:
                ev.set()
        if not active or ev is None:
            # Web 服务重启、线程异常退出、历史残留 stopping，或之前手动停止时只创建了 stop event
            # 但没有真实线程实例：直接落为 stopped，避免永远卡在“停止中”。
            with _STOP_LOCK:
                _STOP_EVENTS.pop(int(job_id), None)
                _ACTIVE_JOBS.discard(int(job_id))
            changed = db.transition_job_status(
                job_id,
                ("running", "stopping"),
                to_status="stopped",
                completed_at=now_iso,
                error_message="用户手动停止（任务实例不存在）",
            )
            if not changed:
                latest = db.get_job(job_id) or {}
                return {
                    "ok": True,
                    "message": f"任务已结束：{latest.get('status') or 'unknown'}",
                    "job_id": job_id,
                    "state": latest.get("status") or "unknown",
                }
            _retain_job_email(
                str(job.get("email") or "").strip() or None,
                "任务实例不存在，注册结果无法确认",
                source=str(job.get("email_source") or "") or None,
            )
            _append_job_log(job_id, "用户手动停止：未找到运行中的任务实例，已直接标记为已停止。")
            logger.warning("[Service] 用户停止任务 #%s：任务实例不存在，已直接标记 stopped", job_id)
            return {"ok": True, "message": "任务实例不存在，已直接标记为已停止", "job_id": job_id, "state": "stopped"}
        changed = db.transition_job_status(
            job_id,
            ("running",),
            "stopping",
            error_message="用户手动停止中",
        )
        if not changed:
            latest = db.get_job(job_id) or {}
            if latest.get("status") in ("stopping", "stopped"):
                return {
                    "ok": True,
                    "message": f"任务已{('停止中' if latest.get('status') == 'stopping' else '停止')}",
                    "job_id": job_id,
                    "state": latest.get("status"),
                }
            return {
                "ok": False,
                "error": f"任务状态刚刚变为：{latest.get('status') or '未知'}",
                "status": 409,
            }
        _append_job_log(job_id, "用户手动停止：已发送停止信号，任务会在当前步骤检查点退出。")
        logger.warning("[Service] 用户请求停止任务 #%s", job_id)
        return {"ok": True, "message": "已发送停止信号", "job_id": job_id, "state": "stopping"}
    return {"ok": False, "error": f"当前状态不支持停止：{status}", "status": 409}


def request_stop_batch(batch_id: str, *, cancel_pending: bool = False) -> dict:
    """在服务端一次处理整个注册批次，避免前端并发发出 N 个控制请求。"""
    batch_key = str(batch_id or "").strip()
    if not batch_key:
        return {"ok": False, "error": "批次 ID 为空", "status": 400}

    jobs = [
        row for row in db.list_jobs(limit=1000)
        if str(row.get("batch_id") or "").strip() == batch_key
    ]
    if not jobs:
        return {"ok": False, "error": "批次不存在", "status": 404}

    cancelled = cancel_pending_jobs(batch_id=batch_key) if cancel_pending else 0
    stopping = 0
    stopped = 0
    completed = 0
    for row in jobs:
        if row.get("status") not in ("running", "stopping"):
            continue
        result = request_stop_job(int(row["id"]))
        if result.get("state") == "stopping":
            stopping += 1
        elif result.get("state") == "stopped":
            stopped += 1
        elif result.get("state") in ("success", "failed", "cancelled", "partial_success"):
            completed += 1

    return {
        "ok": True,
        "batch_id": batch_key,
        "cancelled": cancelled,
        "stopping": stopping,
        "stopped": stopped,
        "completed": completed,
        "message": (
            f"已请求停止 {stopping} 个运行中任务"
            + (f"，取消 {cancelled} 个排队任务" if cancel_pending else "")
        ),
    }


def read_job_log(job_id: int, max_bytes: int = 50_000) -> str:
    """读取任务日志文件最后 max_bytes 字节，给 Web UI 显示。"""
    job = db.get_job(job_id)
    if not job or not job.get("log_file"):
        return ""
    p = task_run_log.resolve_path(job["log_file"])
    if not p.exists():
        return ""
    payload = task_run_log.read_incremental(job.get("log_file"), limit=1000, max_bytes=max_bytes)
    if payload.get("available"):
        lines = []
        for item in payload.get("items") or []:
            if item.get("event_type") == "log.text":
                lines.append(str(item.get("message") or ""))
                continue
            lines.append(
                f"{item.get('ts') or ''} [{item.get('level') or 'INFO'}] "
                f"{item.get('message') or ''}"
            )
        return "\n".join(lines)
    return ""
