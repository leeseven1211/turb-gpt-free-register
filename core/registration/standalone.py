"""让 CLI 和兼容调用具有与任务驱动相同的凭据保存边界。"""
from __future__ import annotations

import os
import logging
import socket
import sys
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_registration_in_context(
    driver,
    kwargs: dict,
    *,
    entrypoint: str = "protocol_cli",
    driver_name: str = "protocol",
):
    """复用已有上下文，或为 CLI 建立并收口独立 Attempt/Run。"""
    from core import registration_service as service
    from core.storage import registration, registration_standalone

    source = str(entrypoint or "protocol_cli").strip() or "protocol_cli"
    persisted_driver = str(driver_name or "protocol").strip() or "protocol"
    facts = service.registration_fact_context()
    if all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id")):
        return driver(**kwargs)
    if any(facts.values()):
        raise RuntimeError("注册执行上下文不完整，拒绝创建第二条任务链")

    attempt = registration_standalone.prepare_attempt(
        kwargs["email"], email_source=kwargs.get("email_source"),
        entrypoint=source, driver=persisted_driver,
    )
    execution = str(uuid.uuid4())
    run = registration.start_run(
        int(attempt["id"]), action_type="registration_resume" if attempt.get("checkpoint") != "created" else "registration",
        execution_id=execution, worker_pid=os.getpid(), initial_status="running",
        data={"entrypoint": source, "worker_host": socket.gethostname(), "driver": persisted_driver},
        started_at=datetime.now(timezone.utc),
    )
    if run.get("execution_id") != execution or run.get("status") != "running":
        raise RuntimeError("此注册意图已有活动执行，请等待原执行收口")
    sentinel = object()
    previous = {key: getattr(service._THREAD_CTX, key, sentinel) for key in facts}
    for key, value in {"attempt_id": int(attempt["id"]), "run_id": int(run["id"]),
                       "execution_id": execution, "job_id": None}.items():
        setattr(service._THREAD_CTX, key, value)
    status = "interrupted"
    result = None
    core_saved = False
    try:
        registration.advance_checkpoint(
            int(attempt["id"]), "auth_started", run_id=int(run["id"]),
            execution_id=execution, message=f"CLI {source} 执行已绑定原注册意图",
        )
        private = registration.get_private_resume_context(int(attempt["id"]), email=kwargs["email"])
        restored = dict(kwargs)
        # 兼容未显式传入来源的旧 CLI/外部调用：恢复原 Attempt 保存的来源，
        # 避免进程重启后按当前 EMAIL_SOURCE 顺序误走其他邮箱平台。
        if not str(restored.get("email_source") or "").strip():
            saved_source = str(attempt.get("email_source") or "").strip()
            if saved_source:
                restored["email_source"] = saved_source
        password = private.get("password")
        if password:
            if restored.get("existing_password") and restored["existing_password"] != password:
                raise ValueError("CLI 提供密码与原注册意图不一致")
            restored["existing_password"] = password
        from core import protocol_traffic, task_run_log
        with task_run_log.stage_context("registration", source_system=source, inherit=False), protocol_traffic.correlation_context(
            inherit=False,
            purpose="registration", registration_attempt_id=int(attempt["id"]), registration_run_id=int(run["id"]),
        ):
            result = driver(**restored)
        if not isinstance(result, dict):
            raise RuntimeError("注册驱动未返回有效注册结果")
        # CLI 与 WebUI 共用明确落库事实；旧调用继续使用既有结果契约。
        core_saved = (
            service.registration_result_status(result) == "success"
            if "core_persisted" in result
            else bool(result.get("registration_success"))
        )
        if core_saved:
            status = "success" if result.get("postprocess_success") else "partial_success"
            service._mark_registration_result(result)
        else:
            reported = str(result.get("status") or "")
            if result.get("request_unknown"):
                status = "request_unknown"
                service._mark_registration_request_unknown(
                    str(result.get("error") or "CLI 注册结果待核验"), facts=result,
                )
            elif result.get("manual_reconcile"):
                status = "manual_reconcile"
                service._mark_registration_manual_reconcile(
                    str(result.get("error") or "CLI 注册结果需要人工对账"),
                )
            elif reported in registration.TERMINAL_RUN_STATUSES and reported != "success":
                # 没有 registration_success 事实时，驱动返回 success 文案不能单独
                # 将远端注册或后处理标为成功。
                status = (
                    "failed" if "core_persisted" in result and reported == "partial_success"
                    else reported
                )
            else:
                status = "failed"
        return result
    except service.StopRequested:
        status = "stopped"
        raise
    finally:
        driver_raised = sys.exc_info()[0] is not None
        try:
            if status in {"interrupted", "stopped"}:
                try:
                    latest = registration.get_attempt(int(attempt["id"])) or {}
                    private = registration.get_private_resume_context(int(attempt["id"]), email=kwargs["email"])
                    if latest.get("account_id") and latest.get("local_account_state") == "persisted":
                        core_saved = True
                        status = "partial_success"
                    elif private.get("password_state") in {"started", "confirmed"}:
                        status = "request_unknown"
                except Exception:
                    # 无法读取持久事实时，不把中断当成已确认的远端失败。
                    status = "request_unknown"
            try:
                registration.finish_run(
                    int(run["id"]), status=status, error_code="request_unknown" if status == "request_unknown" else None,
                    result_summary={"entrypoint": source, "driver": persisted_driver, "registration_success": core_saved,
                        "postprocess_success": bool(core_saved and isinstance(result, dict) and result.get("postprocess_success"))},
                )
            except Exception as exc:
                if not driver_raised:
                    raise
                # 保留原始停止/网络异常；旧 Run 若未能收口，下一次只在
                # 确认本机旧 PID 退出后恢复，不重复创建意图或覆盖密码。
                logger.warning("CLI 注册 Run 收口失败，保留原异常：%s", type(exc).__name__)
        finally:
            for key, value in previous.items():
                if value is sentinel:
                    if hasattr(service._THREAD_CTX, key):
                        delattr(service._THREAD_CTX, key)
                else:
                    setattr(service._THREAD_CTX, key, value)


def run_protocol_in_context(driver, kwargs: dict):
    """Protocol 旧入口兼容包装；生命周期由通用 CLI 入口统一处理。"""
    return run_registration_in_context(
        driver, kwargs, entrypoint="protocol_cli", driver_name="protocol",
    )


def run_protocol_oss_in_context(driver, kwargs: dict):
    """开源 Protocol 入口包装；Attempt/Run 使用独立 driver 标识。"""
    return run_registration_in_context(
        driver, kwargs, entrypoint="protocol_cli", driver_name="protocol_oss",
    )
