# -*- coding: utf-8 -*-
"""任务运行恢复的应用编排，不拥有线程、执行许可或数据库事务。

启动入口按原顺序调用各恢复阶段；运行中的周期由 task_gateway 的既有
调度器控制。行级恢复规则在此保持唯一实现，实际状态转换仍由仓储拥有。
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from core import db, operation_task_store
from core.accounts.operation_handlers import RUNTIME_HANDLER_TYPES
from core.codex import operation_service as codex_operation_service
from core.extract_link import service as extract_link_service
from core.operations import task_gateway as account_task_store

logger = logging.getLogger("webui.runtime")

LEGACY_DURABLE_TASK_TYPES = frozenset({
    *RUNTIME_HANDLER_TYPES,
    "live_check", "token_refresh", "plan_check", "deactivation_mail",
    "extract_link", "codex_token_refresh", "codex_retry",
})


def legacy_recovery_exclusions(
    task_types: set[str] | frozenset[str] | tuple[str, ...],
    *,
    legacy_source_systems: tuple[str, ...] | list[str] | set[str] | frozenset[str] | None = None,
    operation_logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """Return row-level fences for legacy recovery.

    A category-wide ``has_active`` bit is unsafe during the migration: an
    active native Run for account A must not leave an unrelated legacy row for
    account B running forever.  A failed safety query deliberately returns
    ``skip_all`` so startup cannot clear a durable worker while its ownership
    is uncertain.
    """
    active_logger = operation_logger or logger
    normalized = tuple(sorted({str(item).strip() for item in task_types if str(item).strip()}))
    target_source_systems = None if legacy_source_systems is None else {
        str(item).strip() for item in legacy_source_systems if str(item).strip()
    }
    empty = {
        "skip_all": False,
        "account_ids": [],
        "source_ids": [],
        "source_fences": [],
    }
    try:
        result = operation_task_store.list_active_runtime_recovery_exclusions(
            task_types=normalized,
        )
    except AttributeError:
        # Keep a safe rolling-upgrade fallback for an older coordinator facade.
        # It may over-skip, but it can never clear a row belonging to an active
        # durable operation.
        try:
            active = operation_task_store.has_active_runtime_operations(task_types=normalized)
        except Exception:
            active_logger.exception("无法确认 durable Run 是否活跃，跳过本次 legacy recovery")
            return {**empty, "skip_all": True}
        return {
            "skip_all": bool(active),
            "account_ids": [],
            "source_ids": [],
            "source_fences": [],
        }
    except Exception:
        # A failed safety query must not let the old recovery code clear a
        # durable worker that may be alive in another process.
        active_logger.exception("无法读取 durable Run 行级恢复排除项，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}

    if not isinstance(result, Mapping):
        active_logger.error("durable Run 行级恢复排除项格式无效，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}
    try:
        account_ids = sorted({int(item) for item in (result.get("account_ids") or ())})
        raw_fences = result.get("source_fences") or ()
        source_fences: list[dict[str, str]] = []
        for item in raw_fences:
            if not isinstance(item, Mapping):
                raise ValueError("source fence 不是对象")
            source_system = str(item.get("source_system") or "").strip()
            source_id = str(item.get("source_id") or "").strip()
            if not source_system or not source_id:
                raise ValueError("source fence 缺少 namespace/id")
            source_fences.append({"source_system": source_system, "source_id": source_id})
        source_fences = sorted(
            source_fences,
            key=lambda item: (item["source_system"], item["source_id"]),
        )
        if target_source_systems is None:
            # Callers that only need a boolean must not receive an
            # unqualified id list that can later be applied to another table.
            source_ids = []
        else:
            source_ids = sorted({
                item["source_id"] for item in source_fences
                if item["source_system"] in target_source_systems
            })
            # A non-empty legacy source_ids response without namespaces is an
            # unsafe partial rollout. Do not clear any legacy category when
            # the exact source fence cannot be reconstructed.
            if not source_fences and result.get("source_ids"):
                return {**empty, "skip_all": True}
    except (TypeError, ValueError):
        active_logger.exception("durable Run 行级恢复排除项包含非法标识，跳过本次 legacy recovery")
        return {**empty, "skip_all": True}
    if account_ids or source_fences:
        active_logger.info(
            "按 durable active Run 行级保留 legacy 状态：types=%s accounts=%s source_fences=%s",
            list(normalized), account_ids, source_fences,
        )
    return {
        "skip_all": False,
        "account_ids": account_ids,
        "source_ids": source_ids,
        "source_fences": source_fences,
    }


def legacy_recovery_allowed(
    task_types: set[str] | frozenset[str] | tuple[str, ...],
    *,
    operation_logger: logging.Logger | None = None,
) -> bool:
    """兼容布尔判断；启动恢复使用行级排除项。"""
    exclusions = legacy_recovery_exclusions(task_types, operation_logger=operation_logger)
    return (
        not exclusions["skip_all"]
        and not exclusions["account_ids"]
        and not exclusions["source_ids"]
        and not exclusions.get("source_fences")
    )


def recover_before_handlers(runtime_logger: logging.Logger | None = None) -> None:
    """恢复执行归属与导入批次；在代理池和任务 handler 注册前调用。"""
    active_logger = runtime_logger or logger
    from core.storage.operations import recovery

    recovered_permits = recovery.recover_participating_executions()
    active_logger.info("执行许可恢复核验：已释放=%s，存活=%s，待核验=%s",
                       recovered_permits["released"], recovered_permits["alive"], recovered_permits["unverified"])
    from core.email.email_butler import manual_import as butler_manual_import
    recovered_imports = butler_manual_import.reconcile_interrupted()
    if recovered_imports:
        active_logger.warning("已恢复 %s 个因服务重启中断的 Butler 导入批次，可继续原批次", recovered_imports)


def recover_before_dispatchers(runtime_logger: logging.Logger | None = None) -> None:
    """恢复任务与兼容状态；在 handler 注册后、各 dispatcher 启动前调用。"""
    active_logger = runtime_logger or logger
    recovered_operation_runs = operation_task_store.recover_interrupted_runtime_runs()
    if recovered_operation_runs:
        active_logger.warning("已收口 %s 个因 WebUI 重启中断的原生账号操作", recovered_operation_runs)
    repaired_compatibility_projections = operation_task_store.repair_stale_compatibility_projections()
    if repaired_compatibility_projections:
        active_logger.warning(
            "已修复 %s 个底层已结束但统一任务仍显示活动的兼容投影",
            repaired_compatibility_projections,
        )
    # 原提链 Run 会内联查活和查询套餐，先恢复旧状态，再启动原单续查和调度。
    live_check_recovery = legacy_recovery_exclusions(
        {"live_check", "token_refresh", "account_inspection"}, legacy_source_systems=(),
    )
    if not live_check_recovery["skip_all"]:
        recovered_live_checks = db.recover_interrupted_live_checks(
            excluded_account_ids=live_check_recovery["account_ids"],
        )
        if recovered_live_checks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的查活状态", recovered_live_checks)
    else:
        active_logger.info("无法安全读取 durable live_check 行级排除项，跳过旧查活恢复")
    plan_check_recovery = legacy_recovery_exclusions(
        {"plan_check"}, legacy_source_systems=(),
    )
    if not plan_check_recovery["skip_all"]:
        recovered_plan_checks = db.recover_interrupted_plan_checks(
            excluded_account_ids=plan_check_recovery["account_ids"],
        )
        if recovered_plan_checks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的套餐查询状态", recovered_plan_checks)
    else:
        active_logger.info("无法安全读取 durable plan_check 行级排除项，跳过旧套餐查询恢复")
    try:
        resumed_extract_jobs = extract_link_service.resume_known_remote_jobs()
        if resumed_extract_jobs:
            active_logger.warning("已为 %s 个中断的提链远端任务排队状态同步", resumed_extract_jobs)
    except Exception:
        active_logger.exception("恢复中断的提链远端状态同步失败")
    registration_recovery = legacy_recovery_exclusions(
        {"registration_resume"},
        legacy_source_systems=("registration_jobs",),
    )
    if not registration_recovery["skip_all"]:
        recovered_jobs = db.recover_interrupted_registration_jobs(
            excluded_account_ids=registration_recovery["account_ids"],
            excluded_source_ids=registration_recovery["source_ids"],
        )
        if recovered_jobs:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的注册/Codex 任务", recovered_jobs)
    else:
        active_logger.info("无法安全读取 durable registration_resume 行级排除项，跳过旧注册状态恢复")
    account_task_recovery = legacy_recovery_exclusions(
        LEGACY_DURABLE_TASK_TYPES,
        legacy_source_systems=("account_action_tasks",),
    )
    if not account_task_recovery["skip_all"]:
        recovered_account_tasks = account_task_store.recover_interrupted(
            excluded_account_ids=account_task_recovery["account_ids"],
            excluded_source_ids=account_task_recovery["source_ids"],
        )
        if recovered_account_tasks:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的账号任务实例", recovered_account_tasks)
    else:
        active_logger.info("无法安全读取 durable 账号操作行级排除项，跳过兼容账号任务恢复")


def recover_ready_dependencies(runtime_logger: logging.Logger | None = None) -> None:
    """唤醒已持久化的依赖续接；唯一 claim owner 仍为现有扫描器。"""
    active_logger = runtime_logger or logger
    try:
        resumed_dependencies = account_task_store.drain_ready_dependencies(initialized=True)
        if resumed_dependencies:
            active_logger.info("已恢复 %s 个待续接的账号补全父任务", resumed_dependencies)
    except Exception:
        # Dependency recovery is additive.  The durable ready rows remain
        # queryable and will be retried on the next startup/reconcile.
        active_logger.exception("恢复账号补全父子依赖失败；不影响 WebUI 启动")


def recover_local_artifacts(runtime_logger: logging.Logger | None = None) -> None:
    """按原有能力开关清理孤儿浏览器与过期调试产物。"""
    active_logger = runtime_logger or logger
    from config.deployment import browser_enabled

    if browser_enabled():
        try:
            from core.browser.roxy.client import cleanup_orphaned_profiles

            orphan_result = cleanup_orphaned_profiles()
            if orphan_result.get("found"):
                active_logger.warning(
                    "Roxy 孤儿环境恢复完成：found=%s cleaned=%s failed=%s",
                    orphan_result.get("found"), orphan_result.get("cleaned"), orphan_result.get("failed"),
                )
        except Exception:
            active_logger.exception("Roxy 孤儿环境启动恢复失败；登记会保留到下次启动继续重试")

    try:
        from core.registration.debug import cleanup_expired_artifacts

        debug_cleanup = cleanup_expired_artifacts()
        if debug_cleanup.get("removed_files") or debug_cleanup.get("removed_dirs"):
            active_logger.info(
                "注册调试产物过期清理完成：files=%s dirs=%s",
                debug_cleanup.get("removed_files", 0),
                debug_cleanup.get("removed_dirs", 0),
            )
    except Exception:
        active_logger.exception("注册调试产物过期清理失败；不影响 WebUI 启动")


def recover_account_background_state(runtime_logger: logging.Logger | None = None) -> None:
    """在 SMS worker 启动后恢复旧提链状态、账号代理上下文和 Codex 队列。"""
    active_logger = runtime_logger or logger
    extract_link_recovery = legacy_recovery_exclusions(
        {"extract_link"}, legacy_source_systems=(),
    )
    if not extract_link_recovery["skip_all"]:
        recovered_extract_links = db.recover_interrupted_extract_links(
            excluded_account_ids=extract_link_recovery["account_ids"],
        )
        if recovered_extract_links:
            active_logger.warning("已恢复 %s 个因 WebUI 重启中断的提链状态", recovered_extract_links)
    else:
        active_logger.info("无法安全读取 durable extract_link 行级排除项，跳过旧提链恢复")
    resumed_codex_runs = codex_operation_service.resume_queued()
    if resumed_codex_runs:
        active_logger.info("已恢复调度 %s 个数据库队列中的 Codex attempt", resumed_codex_runs)


def run_deferred_account_proxy_backfill(
    runtime_logger: logging.Logger | None = None,
) -> int:
    """在 Worker 心跳已启动后补齐历史账号代理上下文。"""
    active_logger = runtime_logger or logger
    try:
        changed = int(db.backfill_account_registration_proxy_context() or 0)
    except Exception:
        active_logger.exception("历史账号注册代理来源/国家回填失败；下次启动将重试")
        return 0
    if changed:
        active_logger.info("已为 %s 个历史账号补齐注册代理来源/国家", changed)
    return changed


def reconcile_recovered_projections(operation_logger: logging.Logger | None = None) -> int:
    """让维护服务收口通用恢复无法直接理解的业务状态投影。"""
    active_logger = operation_logger or logger
    try:
        from core.accounts.deactivation import mail_scan as deactivation_mail_service

        return int(deactivation_mail_service.reconcile_interrupted_scans() or 0)
    except Exception:
        active_logger.exception("恢复中断 Run 的业务状态投影失败")
        return 0


def recover_stale_runtime_runs(operation_logger: logging.Logger | None = None) -> int:
    """收口失联 Run 并恢复领域投影；调用频率由既有 dispatcher 决定。"""
    active_logger = operation_logger or logger
    try:
        recovered = int(operation_task_store.recover_interrupted_runtime_runs() or 0)
    except Exception:
        active_logger.exception("周期性恢复中断 Run 失败")
        return 0
    reconcile_recovered_projections(active_logger)
    try:
        from core.extract_link import service as extract_link_service

        extract_link_service.resume_known_remote_jobs(continuous_only=True)
    except Exception:
        active_logger.exception("恢复中断的提链远端状态同步失败")
    return recovered
