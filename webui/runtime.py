# -*- coding: utf-8 -*-
"""WebUI request context and explicit process lifecycle."""
from __future__ import annotations

import logging
import atexit
import os
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from flask import Flask

from core.codex import operation_service as codex_operation_service, retry_service as codex_retry_service, token_refresh_service as codex_token_refresh_service
from core import db
from core.accounts import (
    completion_dependencies,
    completion_execution,
    operation_results,
    operation_handlers,
    operation_settings,
    setup_execution,
)
from core.accounts.operation_coordinator import COMPLETION_RESOURCE_FAMILY, RUNTIME_SOURCE_SYSTEM
from core.accounts.deactivation import mail_scan as deactivation_mail_service
from core.extract_link import service as extract_link_service
from core.accounts.liveness import service as live_check_service
from core import operation_task_store
from core.accounts.plans import service as plan_check_service
from core.sms import provider as sms_provider
from core.operations import action_service, reconciliation, task_gateway
from core.operations import task_gateway as account_task_store
from core.operations.executor import executor as _ACCOUNT_EXECUTOR

logger = logging.getLogger(__name__)

_RUNTIME_SOURCE_SYSTEM = RUNTIME_SOURCE_SYSTEM
_COMPLETION_RESOURCE_FAMILY = COMPLETION_RESOURCE_FAMILY

# 兼容既有调用方；执行字段白名单仅由账号核心模块维护。
_RUNTIME_CONFIG_ALLOWLIST = operation_settings.RUNTIME_CONFIG_ALLOWLIST
_RUNTIME_HANDLER_TYPES = operation_handlers.RUNTIME_HANDLER_TYPES
_LEGACY_DURABLE_TASK_TYPES = reconciliation.LEGACY_DURABLE_TASK_TYPES


def _runtime_config_snapshot() -> Any | None:
    """兼容旧入口，配置快照由账号核心模块提供。"""
    return operation_settings.runtime_config_snapshot()


def _legacy_runtime_snapshot(settings: Mapping[str, Any]) -> dict[str, Any]:
    """兼容旧入口，沿用账号核心模块的旧格式快照。"""
    return operation_settings.legacy_runtime_snapshot(settings)


def _completion_settings_from_snapshot(
    snapshot: Mapping[str, Any] | None,
    *,
    fallback: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """兼容旧入口，由账号核心模块投影补全设置。"""
    return operation_settings.completion_settings_from_snapshot(snapshot, fallback=fallback)


def _runtime_submission_snapshot(settings: Mapping[str, Any]) -> tuple[Any, Mapping[str, str]]:
    """兼容旧入口，由账号核心模块捕获提交快照。"""
    return operation_settings.runtime_submission_snapshot(settings)


def _runtime_execution_settings(
    settings: Mapping[str, Any],
) -> tuple[Any, Mapping[str, str], dict[str, object]]:
    """兼容旧入口，保留配置捕获时机与本入口日志。"""
    return operation_settings.runtime_execution_settings(settings, operation_logger=logger)


def _account_setup_readback(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[bool, dict[str, bool]]:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return operation_results.account_setup_readback(
        account_id,
        email,
        steps,
        result,
    )


def _account_setup_receipt(
    account_id: int,
    email: str,
    steps: set[str],
    result: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return operation_results.account_setup_receipt(
        account_id,
        email,
        steps,
        result,
    )


def _submit_native_account_setup_child(
    context: task_gateway.OperationHandlerContext,
    *,
    steps: set[str],
    task_trigger: str,
) -> dict[str, Any]:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return setup_execution.submit_native_account_setup_child(
        context,
        steps=steps,
        task_trigger=task_trigger,
    )


def _safe_operation_result(
    value: Any,
    *,
    default_message: str = "账号操作未完成",
) -> task_gateway.OperationResult:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return operation_results.safe_operation_result(
        value,
        default_message=default_message,
    )


_NativeTaskLifecycle = operation_results.NativeTaskLifecycle


def _run_codex_retry_worker(
    email: str,
    *,
    batch_label: str | None = None,
    clear_log: bool = True,
    task_id: int | None = None,
    task_trigger: str = "manual",
) -> None:
    """Execute one Codex retry; callers must reserve the account first."""
    codex_retry_service.run_worker(
        email,
        batch_label=batch_label,
        clear_log=clear_log,
        task_id=task_id,
        task_trigger=task_trigger,
    )


def _run_account_setup_worker(
    email: str,
    *,
    task_id: int,
    task_trigger: str,
    steps: set[str] | tuple[str, ...] | list[str] | None = None,
    force_password_reset: bool = False,
    force_twofa_change: bool = False,
) -> dict:
    """Execute selected account configuration repair without starting Codex OAuth."""
    return codex_retry_service.run_twofa_worker(
        email,
        task_id=task_id,
        task_trigger=task_trigger,
        steps=steps,
        force_password_reset=force_password_reset,
        force_twofa_change=force_twofa_change,
    )


def _run_account_completion_worker(
    email: str,
    *,
    account_id: int,
    task_id: int,
    task_trigger: str,
    planned_steps: list[str],
    settings: dict[str, object],
    initial_result_summary: dict[str, Any] | None = None,
    context: task_gateway.OperationHandlerContext | None = None,
    reservation_held: bool | None = None,
) -> task_gateway.OperationResult | None:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return completion_execution.run_account_completion_worker(
        email,
        account_id=account_id,
        task_id=task_id,
        task_trigger=task_trigger,
        planned_steps=planned_steps,
        settings=settings,
        initial_result_summary=initial_result_summary,
        context=context,
        reservation_held=reservation_held,
    )


def _native_task_data(context: task_gateway.OperationHandlerContext) -> dict[str, Any]:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return operation_results.native_task_data(
        context,
    )


def _finish_native_context(
    context: task_gateway.OperationHandlerContext,
    result: task_gateway.OperationResult,
) -> task_gateway.OperationResult:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return operation_results.finish_native_context(
        context,
        result,
    )


def _handle_native_account_setup(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return setup_execution.handle_native_account_setup(
        context,
    )


def _handle_native_account_completion(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return completion_execution.handle_native_account_completion(
        context,
    )


def _handle_native_registration_resume(context: task_gateway.OperationHandlerContext) -> task_gateway.OperationResult:
    """兼容旧入口，历史注册续跑 handler 由账号核心模块持有。"""
    return operation_handlers.handle_native_registration_resume(context)


def _completion_deployment_unavailable(steps: set[str], settings: dict) -> dict | None:
    """兼容旧入口，补全能力组合由账号核心模块判断。"""
    return operation_settings.completion_deployment_unavailable(steps, settings)


def _retry_native_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """兼容旧入口，任务重跑业务由动作应用层持有。"""
    return action_service.retry_runtime_task(task)


def _cancel_native_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    """兼容旧入口，任务停止业务由动作应用层持有。"""
    return action_service.cancel_runtime_task(task)


def _register_runtime_handlers() -> None:
    """组合根保留启动入口，注册状态仅由核心模块维护。"""
    operation_handlers.register_runtime_handlers()


def _legacy_recovery_exclusions(
    task_types: set[str] | frozenset[str] | tuple[str, ...],
    *,
    legacy_source_systems: tuple[str, ...] | list[str] | set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
    """兼容旧入口，行级恢复规则由核心 reconciliation 服务拥有。"""
    return reconciliation.legacy_recovery_exclusions(
        task_types, legacy_source_systems=legacy_source_systems, operation_logger=logger,
    )


def _legacy_recovery_allowed(task_types: set[str] | frozenset[str] | tuple[str, ...]) -> bool:
    """兼容旧入口，启动恢复使用核心服务的行级排除项。"""
    return reconciliation.legacy_recovery_allowed(task_types, operation_logger=logger)


def _handle_ready_completion_dependency(dependency: dict) -> None:
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return completion_dependencies.handle_ready_completion_dependency(
        dependency,
    )


def _submit_ready_completion_dependency(dependency: dict):
    """兼容旧入口，委托账号核心模块的唯一实现。"""
    return completion_dependencies.submit_ready_completion_dependency(
        dependency,
    )


@dataclass
class WebUIContext:
    """Explicit dependencies shared by route groups."""

    app: Flask
    logger: logging.Logger
    prepared_downloads: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put_prepared_download(
        self,
        content: bytes,
        filename: str,
        mimetype: str = "application/zip",
    ) -> str:
        now = time.time()
        # Prune short-lived downloads before adding the next one.
        for key, value in list(self.prepared_downloads.items()):
            if now - float(value.get("created_at") or 0) > 600:
                self.prepared_downloads.pop(key, None)
        download_id = uuid.uuid4().hex
        self.prepared_downloads[download_id] = {
            "content": bytes(content),
            "filename": filename,
            "mimetype": mimetype,
            "created_at": now,
        }
        return download_id

    def enqueue_codex_retry(self, email: str, *, trigger: str = "manual") -> dict:
        """Compatibility name for the unified Codex operation coordinator."""
        return codex_operation_service.submit(email, trigger=trigger)

    def enqueue_account_setup(
        self,
        account_id: int,
        *,
        trigger: str = "manual_account_setup",
        steps: set[str] | tuple[str, ...] | list[str] | None = None,
        task_type: str | None = None,
        operation: str | None = None,
    ) -> dict:
        """委托共享账号协调器，保留现有入口与配置捕获。"""
        from config.account import completion_settings
        from core.accounts import operation_coordinator
        return operation_coordinator.enqueue_account_setup(
            account_id, trigger=trigger, steps=steps, task_type=task_type, operation=operation,
            snapshot_bundle=_runtime_execution_settings(completion_settings()),
            register_handlers=_register_runtime_handlers, operation_logger=self.logger,
        )

    def enqueue_account_completion(
        self,
        account_id: int,
        *,
        trigger: str = "manual_account_completion",
    ) -> dict:
        """委托共享账号协调器，保留现有入口与配置捕获。"""
        from config.account import completion_settings
        from core.accounts import operation_coordinator
        return operation_coordinator.enqueue_account_completion(
            account_id, trigger=trigger,
            snapshot_bundle=_runtime_execution_settings(completion_settings()),
            register_handlers=_register_runtime_handlers, operation_logger=self.logger,
        )

    def retry_account_task_result(self, task_id: int) -> tuple[dict, int]:
        """兼容旧入口，历史任务重跑由动作应用层持有。"""
        return action_service.retry_legacy_account_task(task_id, operation_logger=self.logger)


_runtime_lock = threading.Lock()
_runtime_started = False
_runtime_started_at: float | None = None
_legacy_settlement_started = False
_legacy_settlement_atexit_registered = False


def _stop_legacy_settlement_if_idle(timeout: float = 1.0) -> bool:
    """Join only our idle carrier; this is not a legacy worker shutdown."""
    global _legacy_settlement_started
    from core.operations import settlement
    from core.operations.executor import extract_executor
    if not _legacy_settlement_started:
        return True
    # This compatibility entrypoint has no unified legacy producer stop proof.
    # Do not stop compensation while any legacy producer can create more work.
    with _runtime_lock:
        if _runtime_started:
            return False
    if settlement.active_counts().get("registered"):
        return False
    if any(int(value or 0) for carrier in (_ACCOUNT_EXECUTOR, extract_executor)
           for key, value in carrier.runtime_status().items() if key in {"active", "accepted"}):
        return False
    deadline = time.monotonic() + max(0.0, float(timeout))
    if not settlement.drain_runtime(deadline) or not settlement.stop_runtime(deadline):
        return False
    _legacy_settlement_started = False
    return True


def _legacy_settlement_atexit() -> None:
    if not _stop_legacy_settlement_if_idle(timeout=1.0):
        logger.warning("legacy_settlement_stop_incomplete")


def _start_legacy_settlement() -> None:
    global _legacy_settlement_started, _legacy_settlement_atexit_registered
    from core.operations import settlement
    from core.runtime.execution_access import component_start_allowed
    if not component_start_allowed():
        return
    if settlement.start_runtime():
        _legacy_settlement_started = True
    if _legacy_settlement_started and not _legacy_settlement_atexit_registered:
        atexit.register(_legacy_settlement_atexit)
        _legacy_settlement_atexit_registered = True


def runtime_status() -> dict[str, Any]:
    """Read-only process runtime state for the release agent's health route.

    The structure intentionally contains no account, token, proxy or database
    payload.  ``ready`` means WebUI startup completed; component liveness is
    exposed separately so a health route can choose strict or degraded policy.
    """
    from core.runtime.process import get_runtime_context
    from core.operations import settlement
    if get_runtime_context() is not None:
        from core.runtime.process import runtime_status as managed_status
        return managed_status()
    with _runtime_lock:
        started = bool(_runtime_started)
        started_at = _runtime_started_at
    try:
        executor_status = _ACCOUNT_EXECUTOR.status()
    except Exception as exc:
        executor_status = {"error": type(exc).__name__}
    try:
        dispatcher_status = codex_operation_service.dispatcher_status()
    except Exception as exc:
        dispatcher_status = {"error": type(exc).__name__}
    try:
        dependency_dispatcher_status = account_task_store.dependency_dispatcher_status()
    except Exception as exc:
        dependency_dispatcher_status = {"error": type(exc).__name__}
    try:
        projection_status = operation_task_store.projection_worker_status()
    except Exception as exc:
        projection_status = {"error": type(exc).__name__}
    try:
        from core.email.email_butler import usage_reports as email_usage_reports
        usage_reports_status = email_usage_reports.worker_status()
    except Exception as exc:
        usage_reports_status = {"error": type(exc).__name__}
    try:
        from core.email.email_butler import service_facts
        service_sync_status = service_facts.worker_status()
    except Exception as exc:
        service_sync_status = {"error": type(exc).__name__}
    try:
        from core.bulk_operations import service as bulk_service
        bulk_status = bulk_service.worker_status()
    except Exception as exc:
        bulk_status = {"error": type(exc).__name__}
    return {
        "ready": started,
        "started": started,
        "pid": os.getpid(),
        "started_at": started_at,
        "executor": executor_status,
        "codex_dispatcher": dispatcher_status,
        "dependency_dispatcher": dependency_dispatcher_status,
        "projection_worker": projection_status,
        "email_usage_reports": usage_reports_status,
        "email_service_sync": service_sync_status,
        "bulk_operations": bulk_status,
        "settlement": settlement.runtime_status(),
    }


def start_runtime(runtime_logger: logging.Logger | None = None) -> bool:
    """Start WebUI recovery and periodic workers once per process."""
    from core.runtime.process import get_runtime_context
    if get_runtime_context() is not None:
        from core.runtime.process import start_runtime as managed_start
        return managed_start(runtime_logger)
    global _runtime_started, _runtime_started_at
    active_logger = runtime_logger or logger
    with _runtime_lock:
        if _runtime_started:
            return False

        operation_task_store.init()
        from core.storage.operations import bulk
        bulk.init()
        _start_legacy_settlement()
        reconciliation.recover_before_handlers(active_logger)
        try:
            from core.proxy import pool as proxy_pool

            # 代理池独立维护库存；任务线程只负责有界领取租约。
            proxy_pool.start(prewarm=True)
        except Exception:
            active_logger.exception("独立代理池启动失败；代理任务将在领取时返回明确错误")
        _register_runtime_handlers()
        from core.maintenance import sentinel
        from core.integrations.sub2api import monitor as sub2api_monitor
        from core.integrations.sub2api import manual_upload
        from core.integrations.c2a import manual_sync as c2a_manual_sync

        sentinel.register_handler()
        sub2api_monitor.register_handler()
        manual_upload.register_handler()
        c2a_manual_sync.register_handler()
        reconciliation.recover_before_dispatchers(active_logger)
        operation_task_store.start_projection_worker()
        from core.registration import service as registration_service

        registration_service.start_dispatcher()
        account_task_store.start_dispatcher()
        account_task_store.set_dependency_ready_handler(_submit_ready_completion_dependency)
        account_task_store.start_dependency_dispatcher()
        from core.bulk_operations import service as bulk_service
        bulk_service.start_workers()
        reconciliation.recover_ready_dependencies(active_logger)
        reconciliation.recover_local_artifacts(active_logger)
        sms_provider.start_cancel_worker()
        reconciliation.recover_account_background_state(active_logger)
        from core.accounts.deactivation.mail_scan import start_periodic_scanner
        from core.accounts.token_refresh import start_periodic_refresher
        from core.codex.token_refresh_service import start_periodic_refresher as start_codex_token_refresher

        start_periodic_scanner()
        start_periodic_refresher()
        start_codex_token_refresher()
        from core.integrations.sub2api.jobs import start_periodic_sync
        from core.integrations.sub2api.monitor import start_periodic_monitor

        start_periodic_sync()
        start_periodic_monitor()
        from core.accounts.auth_context_cleanup import start_periodic_cleanup
        from core.operations.retention import start_periodic_cleanup as start_task_center_retention

        start_periodic_cleanup()
        start_task_center_retention()
        try:
            from core.email.email_butler import usage_reports as email_usage_reports
            email_usage_reports.start_worker()
        except Exception as exc:
            active_logger.warning("HME 结果后台队列暂不可用 (%s)", type(exc).__name__)
        try:
            from core.email.email_butler import service_facts
            service_facts.start_worker()
        except Exception as exc:
            active_logger.warning("邮箱服务事实同步队列暂不可用 (%s)", type(exc).__name__)
        _runtime_started = True
        _runtime_started_at = time.time()
        return True


def stop_runtime(timeout: float = 60.0) -> bool:
    """Stop an explicitly installed managed runtime with truthful drain status."""
    from core.runtime.process import get_runtime_context
    if get_runtime_context() is None:
        # Idle failed startup may relinquish only the carrier this entrypoint
        # created. Other legacy components have no proven shutdown here.
        _stop_legacy_settlement_if_idle(timeout=min(1.0, max(0.0, timeout)))
        return False
    from core.runtime.process import stop_runtime as managed_stop
    return managed_stop(timeout=timeout)
