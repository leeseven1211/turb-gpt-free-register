"""让 CLI 和兼容调用具有与任务驱动相同的凭据保存边界。"""
from __future__ import annotations

import os
import logging
import socket
import sys
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_protocol_in_context(driver, kwargs: dict):
    """已有执行上下文直接复用；无上下文时建立并收口独立 Attempt/Run。"""
    from core import registration_service as service
    from core.storage import registration, registration_standalone

    facts = service.registration_fact_context()
    if all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id")):
        return driver(**kwargs)
    if any(facts.values()):
        raise RuntimeError("注册执行上下文不完整，拒绝创建第二条任务链")

    attempt = registration_standalone.prepare_attempt(
        kwargs["email"], email_source=kwargs.get("email_source"),
    )
    execution = str(uuid.uuid4())
    run = registration.start_run(
        int(attempt["id"]), action_type="registration_resume" if attempt.get("checkpoint") != "created" else "registration",
        execution_id=execution, worker_pid=os.getpid(), initial_status="running",
        data={"entrypoint": "protocol_cli", "worker_host": socket.gethostname()},
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
            execution_id=execution, message="CLI 协议执行已绑定原注册意图",
        )
        private = registration.get_private_resume_context(int(attempt["id"]), email=kwargs["email"])
        restored = dict(kwargs)
        password = private.get("password")
        if password:
            if restored.get("existing_password") and restored["existing_password"] != password:
                raise ValueError("CLI 提供密码与原注册意图不一致")
            restored["existing_password"] = password
        from core import protocol_traffic, task_run_log
        with task_run_log.stage_context("registration", source_system="protocol_cli", inherit=False), protocol_traffic.correlation_context(
            inherit=False,
            purpose="registration", registration_attempt_id=int(attempt["id"]), registration_run_id=int(run["id"]),
        ):
            result = driver(**restored)
        if not isinstance(result, dict):
            raise RuntimeError("协议驱动未返回有效注册结果")
        if result.get("registration_success"):
            status = "success" if result.get("postprocess_success") else "partial_success"
            service._mark_registration_result(result)
        else:
            reported = str(result.get("status") or "")
            status = ("request_unknown" if result.get("request_unknown") else
                      "manual_reconcile" if result.get("manual_reconcile") else
                      reported if reported in registration.TERMINAL_RUN_STATUSES else "failed")
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
                    result_summary={"entrypoint": "protocol_cli", "registration_success": core_saved or bool(
                        isinstance(result, dict) and result.get("registration_success")),
                        "postprocess_success": bool(isinstance(result, dict) and result.get("postprocess_success"))},
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
