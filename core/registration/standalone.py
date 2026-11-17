"""让 CLI 和兼容调用具有与任务驱动相同的凭据保存边界。"""
from __future__ import annotations

import os
import logging
import socket
import sys
from datetime import datetime, timezone
from contextlib import ExitStack

logger = logging.getLogger(__name__)


def run_registration_in_context(
    driver,
    kwargs: dict,
    *,
    entrypoint: str = "protocol_cli",
    driver_name: str = "protocol_oss_2",
):
    """验证父许可，或在独立入口先统一准入，再绑定注册事实。"""
    from core.operations import concurrency
    from core.registration import admission, service

    facts = service.registration_fact_context()
    complete = all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id"))
    if any(facts.values()) and not complete:
        raise RuntimeError("注册执行上下文不完整，拒绝创建第二条任务链")
    parent = concurrency.current_execution()
    if complete:
        if parent is None or parent.execution_id != facts["execution_id"] or not concurrency.validate_execution(parent):
            raise RuntimeError("注册执行上下文缺少有效的并发许可")
    with admission.standalone_execution(
        email=kwargs["email"], driver=driver_name, entrypoint=entrypoint,
    ):
        return _run_registration_with_facts(
            driver, kwargs, entrypoint=entrypoint, driver_name=driver_name,
        )


def _run_registration_with_facts(driver, kwargs: dict, *, entrypoint: str, driver_name: str):
    """已有执行许可下复用上下文，或建立并收口独立 Attempt/Run。"""
    from core.registration import service as service
    from core.operations.concurrency import current_execution
    from core.storage import registration
    from core.storage.registration import standalone as registration_standalone

    source = str(entrypoint or "protocol_cli").strip() or "protocol_cli"
    from core.registration.driver_selection import normalize_registration_driver

    persisted_driver = normalize_registration_driver(driver_name)
    facts = service.registration_fact_context()
    if all(facts.get(key) for key in ("attempt_id", "run_id", "execution_id")):
        from core.registration.password_completion import after_registration

        return after_registration(
            driver(**kwargs), run_id=int(facts["run_id"]), options=kwargs.get("registration_options"),
        )
    if any(facts.values()):
        raise RuntimeError("注册执行上下文不完整，拒绝创建第二条任务链")

    attempt = registration_standalone.prepare_attempt(
        kwargs["email"], email_source=kwargs.get("email_source"),
        entrypoint=source, driver=persisted_driver,
    )
    permit = current_execution()
    if permit is None:
        raise RuntimeError("独立注册未取得并发许可")
    execution = permit.execution_id
    action_type = "registration_resume" if attempt.get("checkpoint") != "created" else "registration"
    if (persisted_driver == "protocol_oss_2"
            and attempt.get("checkpoint") in {"created", "email_claimed", "auth_started"}
            and attempt.get("remote_identity_state") not in {"request_unknown", "confirmed"}
            and attempt.get("remote_account_state") not in {"request_unknown", "confirmed"}):
        private = registration.get_private_resume_context(int(attempt["id"]), email=kwargs["email"])
        # 预认证中断或仅生成候选时，原邮箱重试仍需创建密码；已提交的原身份沿认证继续。
        if private.get("password_state") not in {"started", "confirmed"}:
            action_type = "registration"
    run = registration.start_run(
        int(attempt["id"]), action_type=action_type,
        execution_id=execution, worker_pid=os.getpid(), initial_status="running",
        data={"entrypoint": source, "worker_host": socket.gethostname(), "driver": persisted_driver,
              "execution_key": permit.execution_key},
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
        from core.network import protocol_traffic
        from core.operations import run_log as task_run_log
        with task_run_log.stage_context("registration", source_system=source, inherit=False), protocol_traffic.correlation_context(
            inherit=False,
            purpose="registration", registration_attempt_id=int(attempt["id"]), registration_run_id=int(run["id"]),
        ):
            result = _run_managed_registration_driver(driver, restored, driver_name=persisted_driver)
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
            from core.registration.password_completion import after_registration

            result = after_registration(
                result, run_id=int(run["id"]), options=restored.get("registration_options"),
            )
            status = "success" if result.get("postprocess_success") else "partial_success"
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
        from core.registration.admission import mark_execution_state

        mark_execution_state("cleaning")
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
                from dataclasses import asdict
                from core.registration.route_recovery import result_route_failure, safe_registration_recovery_audit
                from core.operations.errors import safe_registration_diagnostics, REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES

                summary = {
                    "entrypoint": source, "driver": persisted_driver, "registration_success": core_saved,
                    "postprocess_success": bool(core_saved and isinstance(result, dict) and result.get("postprocess_success")),
                }
                route_failure = result_route_failure(result)
                if route_failure is not None:
                    summary["route_failure"] = asdict(route_failure)
                if isinstance(result, dict):
                    cause = result.get("cause_code")
                    if isinstance(cause, str) and cause in REGISTRATION_REQUEST_UNKNOWN_CAUSE_CODES:
                        summary["cause_code"] = cause
                    diagnostics = safe_registration_diagnostics(result.get("registration_diagnostics"))
                    if diagnostics:
                        summary["registration_diagnostics"] = diagnostics
                    if result.get("route_recovery_blocked") is True:
                        summary["route_recovery_blocked"] = True
                    audit = safe_registration_recovery_audit(result.get("registration_recovery_audit"))
                    if audit:
                        summary["registration_recovery_audit"] = audit
                registration.finish_run(
                    int(run["id"]), status=status, error_code="request_unknown" if status == "request_unknown" else None,
                    result_summary=summary,
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
    """保留 CLI 生命周期包装，协议注册身份统一为开源protocol-2。"""
    return run_registration_in_context(
        driver, kwargs, entrypoint="protocol_cli", driver_name="protocol_oss_2",
    )


def _run_managed_registration_driver(driver, kwargs: dict, *, driver_name: str = ""):
    """受管 CLI 与 worker 复用业务协调器；直传代理只执行原有驱动。"""
    from core.registration.route_recovery import (
        RegistrationRouteCoordinator, current_managed_registration_owner,
        current_route_recovery, registration_route_recovery, result_route_failure,
    )
    from core.registration import service
    from core.storage import registration
    from core.proxy.provider import acquire_registration_proxy, release_proxy
    from core.network.protocol_traffic import correlation_context

    owner = current_managed_registration_owner()
    if (current_route_recovery() is not None or owner is None or owner.lease is None
            or owner.lease.proxy_url != kwargs.get("proxy")):
        return driver(**kwargs)
    facts = service.registration_fact_context()
    route_no = 1
    country = owner.lease.region
    options = dict(kwargs.get("registration_options") or {})
    with ExitStack() as scopes:
        scopes.enter_context(correlation_context(proxy_lease_id=owner.lease.lease_id, route_attempt_no=route_no))

        def begin_route(reason):
            nonlocal route_no
            route_no += 1
            service._bind_progress_route_context(route_no)
            attempt = registration.get_attempt(int(facts["attempt_id"])) or {}
            registration.advance_checkpoint(
                int(facts["attempt_id"]), attempt.get("checkpoint") or "auth_started",
                run_id=facts["run_id"], execution_id=facts["execution_id"],
                event_type="proxy_rotation", message=reason,
                detail={"route_attempt_no": route_no},
            )
            return route_no

        def on_lease(lease, number):
            registration.authorize_route_resume(
                int(facts["attempt_id"]), email=kwargs["email"], run_id=int(facts["run_id"]),
                execution_id=facts["execution_id"], previous_route_no=number - 1,
                route_attempt_no=number,
            )
            scopes.enter_context(correlation_context(proxy_lease_id=lease.lease_id, route_attempt_no=number))

        coordinator = RegistrationRouteCoordinator(
            owner.lease, limit=service._registration_proxy_retry_limit(),
            delay=service._registration_proxy_retry_delay(),
            acquire=lambda **values: acquire_registration_proxy(
                country=country, purpose="registration", cancel=service.check_stop_requested, **values,
            ),
            release=release_proxy, check_stop=service.check_stop_requested,
            begin_route=begin_route, on_lease=on_lease,
        )

        def recover(failure, current_proxy):
            try:
                return coordinator(failure, current_proxy)
            finally:
                owner.lease = coordinator.lease

        call = dict(kwargs)
        try:
            while True:
                available = coordinator.used < coordinator.limit
                is_roxy = (driver_name or options.get("registration_driver")) == "roxy"
                with registration_route_recovery(recover if available or not is_roxy else None):
                    result = driver(**call)
                coordinator.observe_result(result)
                failure = result_route_failure(result)
                if not (failure and result.get("route_recovery_ready") is True
                        and result.get("route_recovery_state") is not None):
                    return result
                lease = recover(failure, call["proxy"])
                if lease is None:
                    return result
                options["_roxy_route_recovery"] = result["route_recovery_state"]
                call["registration_options"] = options
                call["profile_id"] = result.get("route_recovery_profile_id") or None
                call["proxy"] = lease.proxy_url
                private = registration.get_private_resume_context(int(facts["attempt_id"]), email=kwargs["email"])
                call["existing_password"] = private.get("password") or call.get("existing_password")
        finally:
            owner.lease = coordinator.lease
            owner.fault = coordinator.current_lease_transport_failure
