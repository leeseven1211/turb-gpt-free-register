"""任务中心写入应用层：统一动作路由、历史兼容回退与既有响应契约。"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from core import db, operation_task_store
from core.accounts import operation_settings
from core.accounts.operation_coordinator import RUNTIME_SOURCE_SYSTEM
from core.accounts.deactivation import mail_scan as deactivation_mail_service
from core.accounts.liveness import service as live_check_service
from core.accounts.plans import service as plan_check_service
from core.codex import operation_service as codex_operation_service
from core.codex import token_refresh_service as codex_token_refresh_service
from core.extract_link import service as extract_link_service
from core.operations import task_gateway
from core.operations import task_gateway as account_task_store
from core.registration import service as registration_service

# 保留迁移前的日志归属与入口可注入的 logger。
action_logger = logging.getLogger("webui.routes.operations")
runtime_logger = logging.getLogger("webui.runtime")
active_operation_statuses = {
    "queued", "running", "stopping", "cancelling", "settling", "waiting",
}


def _get_operation_action_task(task_id: int, action: str):
    """停止前只读任务状态，避免载入与取消无关的完整事件历史。"""
    if action in {"cancel", "terminate"}:
        return operation_task_store.get_task(task_id, include_events=False)
    return operation_task_store.get_task(task_id)


def perform_operation_action(
    task_id: int,
    action: str,
    *,
    expected_status: str | None = None,
    driver_override: str | None = None,
    diagnostic_after_mfa: bool = False,
    request_key: str | None = None,
    operation_logger: logging.Logger | None = None,
):
    """读取单个任务并分发动作。"""
    task = _get_operation_action_task(task_id, action)
    if not task:
        return {"ok": False, "error": "任务不存在"}, 404
    return _dispatch_operation_action(
        task_id, task, action, expected_status=expected_status, driver_override=driver_override,
        diagnostic_after_mfa=diagnostic_after_mfa, request_key=request_key,
        operation_logger=operation_logger,
    )


def _dispatch_operation_action(
    task_id: int,
    task: dict,
    action: str,
    *,
    expected_status: str | None = None,
    driver_override: str | None = None,
    diagnostic_after_mfa: bool = False,
    request_key: str | None = None,
    operation_logger: logging.Logger | None = None,
    managed_retry_checked: bool = False,
):
    logger = operation_logger or action_logger
    task_type = str(task.get("task_type") or "").strip()
    source_system = str(task.get("source_system") or "").strip()
    current_status = str(task.get("status") or "").strip().lower()
    if expected_status and current_status != expected_status:
        return {"ok": False, "error": "任务状态已变化，请刷新后重试"}, 409
    if action == "retry":
        if diagnostic_after_mfa:
            if not codex_operation_service.session_diagnostic_target_supported(task, driver_override):
                return {"ok": False, "error": "MFA 诊断仅支持单条非批量原生 Codex protocol 补跑任务"}, 400
        elif not managed_retry_checked:
            from core.bulk_operations.service import retry_managed_task
            try:
                retry_key = request_key
                if retry_key and len(retry_key) > 128:
                    return {"ok": False, "error": "Idempotency-Key 不能超过 128 字符"}, 422
                managed_retry = retry_managed_task(task_id, request_key=f"operations-retry:{retry_key}:{task_id}" if retry_key else None)
            except ValueError as exc:
                return {"ok": False, "error": str(exc), "error_code": getattr(exc, "code", "bulk_retry_failed")}, getattr(exc, "status", 409)
            if managed_retry is not None:
                return managed_retry, 202
        if driver_override is not None and not (
            source_system == "native_operations" and task_type == "codex_retry"
        ):
            return {"ok": False, "error": "只有原生 Codex 补跑任务支持指定 driver"}, 400
        if task_gateway.operation_is_deactivated(task):
            return {
                "ok": False,
                "deactivated": True,
                "error": "账号已废号，不能重跑",
            }, 409
        if task.get("status") in active_operation_statuses:
            return {"ok": False, "error": "任务仍在执行"}, 409
        # 驱动和本次诊断选项由 Codex 服务写入新 Run 的配置快照。
        registered_action = None if driver_override is not None or diagnostic_after_mfa else task_gateway.operation_action(
            task_type, "retry", source_system=source_system,
        )
        if registered_action is not None:
            try:
                result = registered_action(task)
            except Exception as exc:
                logger.exception("统一任务类型重试 handler 失败：task_id=%s type=%s", task_id, task_type)
                return {"ok": False, "error": f"重试入口异常：{type(exc).__name__}: {exc}"}, 503
            payload = dict(result) if isinstance(result, dict) else {"accepted": bool(result)}
            payload.setdefault("ok", bool(payload.get("accepted", True)))
            if payload.get("busy"):
                return payload, 409
            if not payload.get("accepted", payload.get("ok")):
                return payload, 503 if payload.get("unavailable") else 409
            return payload, 202
        if source_system == "native_operations" and task_type == "codex_retry":
            retry_kwargs = {"trigger": "manual_retry"}
            if driver_override is not None:
                retry_kwargs["driver"] = driver_override
            if diagnostic_after_mfa:
                retry_kwargs["diagnostic_after_mfa"] = True
            queued = codex_operation_service.retry_task(int(task_id), **retry_kwargs)
            if queued.get("busy"):
                return {"ok": False, **queued}, 409
            if not queued.get("accepted"):
                return {"ok": False, **queued}, 503 if queued.get("unavailable") else 409
            return {"ok": True, **queued}, 202
        source_job_id = _registration_retry_job_id(task)
        if source_job_id is not None:
            result = registration_service.retry_job(source_job_id)
            status = int(result.pop("status", 200 if result.get("ok") else 400))
            return result, status
        runs = task.get("runs") or []
        latest = runs[-1] if runs else {}
        source_system = str(latest.get("source_system") or "")
        source_id = str(latest.get("source_id") or "")
        if source_system == "account_action_tasks" and source_id.isdigit():
            payload, status = retry_legacy_account_task(int(source_id), operation_logger=operation_logger)
            return payload, status
        return {"ok": False, "error": "该历史任务没有可用的重跑来源"}, 409

    if action not in {"cancel", "terminate"}:
        return {"ok": False, "error": "不支持的任务操作"}, 400
    registered_action = task_gateway.operation_action(
        task_type, action, source_system=source_system,
    )
    if registered_action is not None:
        try:
            action_task = dict(task)
            if expected_status and action == "cancel":
                action_task["_expected_run_status"] = expected_status
            result = registered_action(action_task)
        except Exception as exc:
            logger.exception("统一任务类型%s handler 失败：task_id=%s type=%s", action, task_id, task_type)
            return {"ok": False, "error": f"停止入口异常：{type(exc).__name__}: {exc}"}, 503
        payload = dict(result) if isinstance(result, dict) else {"ok": bool(result)}
        payload.setdefault("ok", True)
        return payload, 200 if payload.get("ok") else 409
    if source_system != "native_operations" or task_type != "codex_retry":
        return {"ok": False, "error": "历史兼容任务请使用原任务停止入口"}, 409
    active = next(
        (
            run for run in reversed(task.get("runs") or [])
            if run.get("status") in active_operation_statuses
        ),
        None,
    )
    if not active:
        return {"ok": True, "state": "empty", "message": "任务没有活跃 attempt"}, 200
    if action == "cancel":
        cancel_kwargs = {"run_id": int(active["id"])}
        if expected_status:
            cancel_kwargs["expected_status"] = expected_status
        result = codex_operation_service.request_cancel(**cancel_kwargs)
    else:
        result = codex_operation_service.terminate(run_id=int(active["id"]))
    return result, 200 if result.get("ok") else 409


def delete_operation(task_id: int):
    """从任务中心隐藏单个非执行中的任务，但保留审计记录。"""
    result = operation_task_store.delete_tasks([task_id])
    if task_id in result.get("deleted", []):
        payload = dict(result)
        payload.update({"ok": True, "deleted": True})
        return payload, 200
    skipped = result.get("skipped") or []
    error = skipped[0].get("error") if skipped else "任务未删除"
    status = 409 if error == "任务仍在执行，不能删除" else 404
    payload = dict(result)
    payload.update({"ok": False, "deleted": False, "error": error})
    return payload, status


def accept_bulk_operation_action(
    action: str,
    task_ids: list[int],
    *,
    request_key: str | None = None,
    operation_logger: logging.Logger | None = None,
) -> dict:
    """按集合读取和归组，精确受理选中的任务。"""
    if action == "delete":
        result = operation_task_store.delete_tasks_many(task_ids)
        accepted = [
            {"task_id": task_id, "state": "deleted", "message": "任务已从任务中心隐藏"}
            for task_id in result.get("deleted", [])
        ]
        return {
            "ok": True,
            "action": action,
            "accepted": accepted,
            "accepted_count": len(accepted),
            **result,
        }

    observed = operation_task_store.get_action_tasks_many(task_ids)
    tasks = {task_id: observed[task_id] for task_id in task_ids if task_id in observed}
    managed_task_ids = {task_id for task_id, task in tasks.items() if task.get("_managed_target_round_id")}
    if action == "retry":
        from core.operations.task_center_retry_wave import accept_retries
        native_retries = accept_retries(tasks, excluded=managed_task_ids,
            request_key=request_key, operation_logger=operation_logger)
        from core.operations.task_center_sentinel import accept_retries as accept_sentinel_retries
        sentinel_retries = (
            accept_sentinel_retries(tasks) if not request_key or len(request_key) <= 128 else {}
        )
        from core.operations.task_center_inspection import accept_retries as accept_inspection_retries
        inspection_retries = (
            accept_inspection_retries(tasks) if not request_key or len(request_key) <= 128 else {}
        )
        managed_retries = _accept_managed_retries(tasks, request_key=request_key)
    else:
        managed_retries = {}
        native_retries = {}
        sentinel_retries = {}
        inspection_retries = {}
    cancelled = _accept_pending_cancellations(tasks) if action == "cancel" else {}
    if action == "cancel":
        from core.operations.task_center_cancel import accept_cancellations
        special_cancellations = accept_cancellations(tasks)
    else:
        special_cancellations = {}
    accepted: list[dict] = []
    skipped: list[dict] = []
    for task_id in task_ids:
        task = tasks.get(task_id)
        if not task:
            skipped.append({"task_id": task_id, "error": "任务不存在"})
            continue
        task_status = str(task.get("status") or "").strip().lower()
        if action == "cancel" and task_status != "queued":
            skipped.append({"task_id": task_id, "error": "只有排队中的任务可以取消"})
            continue
        if action == "terminate" and (
            str(task.get("source_system") or "") != "native_operations"
            or task_status not in active_operation_statuses
            or task_status == "queued"
        ):
            skipped.append({"task_id": task_id, "error": "只有原生执行中的任务可以终止"})
            continue
        if task_id in managed_retries:
            payload, status = managed_retries[task_id]
        elif task_id in native_retries:
            payload, status = native_retries[task_id]
        elif task_id in sentinel_retries:
            payload, status = sentinel_retries[task_id]
        elif task_id in inspection_retries:
            payload, status = inspection_retries[task_id]
        elif task_id in cancelled:
            error = cancelled[task_id]
            payload, status = (
                ({"ok": False, "error": error}, 409) if error else
                ({"ok": True, "state": "cancelled", "message": "已记录停止请求，任务将在安全检查点收口"}, 200)
            )
        elif task_id in special_cancellations:
            payload, status = special_cancellations[task_id]
        elif action == "retry" and request_key and len(request_key) > 128:
            payload, status = {"ok": False, "error": "Idempotency-Key 不能超过 128 字符"}, 422
        else:
            payload, status = _dispatch_operation_action(
                task_id, task, action, expected_status=task_status,
                operation_logger=operation_logger, managed_retry_checked=True,
            )
        if 200 <= status < 300 and payload.get("ok", payload.get("accepted", False)) and payload.get("state") != "empty":
            accepted.append({
                "task_id": task_id,
                "state": payload.get("state") or payload.get("status") or "accepted",
                "message": payload.get("message") or "",
            })
        else:
            skipped.append({
                "task_id": task_id,
                "error": payload.get("error") or payload.get("message") or "操作未接受",
            })
    return {
        "ok": True,
        "action": action,
        "accepted": accepted,
        "accepted_count": len(accepted),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


def _registration_retry_job_id(task: Mapping) -> int | None:
    """保持显式下一动作优先于最后 Run 来源的历史路由规则。"""
    next_action = (task.get("next_actions") or [{}])[0]
    if isinstance(next_action, Mapping):
        source_job_id = next_action.get("source_job_id")
        if str(next_action.get("action") or "") in {"registration_resume", "registration_retry"} and source_job_id:
            return int(source_job_id)
    runs = task.get("runs") or []
    latest = runs[-1] if runs else {}
    source_id = str(latest.get("source_id") or "")
    if str(latest.get("source_system") or "") == "registration_jobs" and source_id.isdigit():
        return int(source_id)
    return None


def _accept_registration_retries(
    tasks: dict[int, dict],
    *,
    managed_task_ids: set[int],
    request_key: str | None,
    operation_logger: logging.Logger | None,
) -> dict[int, tuple[dict, int]]:
    if request_key and len(request_key) > 128:
        return {}
    selected: dict[int, int] = {}
    for task_id, task in tasks.items():
        if (task_id in managed_task_ids or task_gateway.operation_is_deactivated(task)
                or task.get("status") in active_operation_statuses):
            continue
        task_type = str(task.get("task_type") or "").strip()
        source_system = str(task.get("source_system") or "").strip()
        if (task_gateway.operation_action(task_type, "retry", source_system=source_system) is not None
                or source_system == "native_operations" and task_type == "codex_retry"):
            continue
        source_job_id = _registration_retry_job_id(task)
        if source_job_id is not None:
            selected[task_id] = source_job_id
    if not selected:
        return {}
    try:
        # 注册服务逐来源恢复冻结配置、原批次额度和父上下文。
        results = registration_service.retry_jobs(list(dict.fromkeys(selected.values())), workers=1)
    except Exception:
        (operation_logger or action_logger).exception("任务中心批量注册重跑入队失败")
        return {task_id: ({"ok": False, "error": "原注册任务入队失败，请刷新任务状态后重试"}, 503)
                for task_id in selected}
    replies = {}
    for task_id, source_job_id in selected.items():
        result = dict(results.get(source_job_id) or {"ok": False, "error": "原注册任务当前不可重跑"})
        status = int(result.pop("status", 200 if result.get("ok") else 400))
        replies[task_id] = result, status
    return replies


def _accept_pending_cancellations(tasks: dict[int, dict]) -> dict[int, str | None]:
    from core.storage.operations import bulk_facts

    selected: dict[int, int] = {}
    reasons: dict[int, str] = {}
    for task_id, task in tasks.items():
        if task.get("status") != "queued" or task.get("_managed_target_round_id"):
            continue
        handler = task_gateway.operation_action(
            task.get("task_type") or "", "cancel", source_system=task.get("source_system"),
        )
        if handler is task_gateway.default_operation_cancel:
            reason = "用户手动停止统一 durable operation"
        elif handler is cancel_runtime_task and task.get("source_system") == RUNTIME_SOURCE_SYSTEM:
            reason = "用户手动停止 WebUI durable operation"
        else:
            continue
        run = next((
            run for run in reversed(task.get("runs") or [])
            if run.get("status") == "queued"
        ), None)
        if run and run.get("id") and not (run.get("data") or {}).get("bulk_target_round_id"):
            run_id = int(run["id"])
            selected[task_id] = run_id
            reasons[run_id] = reason
    if not selected:
        return {}
    try:
        replies = bulk_facts.request_cancel_runs_many(reasons)
    except Exception:
        action_logger.exception("批量取消普通排队任务失败")
        return dict.fromkeys(selected, "停止入口异常，请刷新后重试")
    if any(reason is None for reason in replies.values()):
        task_gateway.notify_dispatch()
    return {task_id: replies[run_id] for task_id, run_id in selected.items()}


def _accept_managed_retries(
    tasks: dict[int, dict], *, request_key: str | None,
) -> dict[int, tuple[dict, int]]:
    from core.bulk_operations import service

    identities = {task_id: task.get("_managed_target_round_id") for task_id, task in tasks.items()}
    managed = {task_id: identity for task_id, identity in identities.items() if identity}
    if not managed or (request_key and len(request_key) > 128):
        return {}
    try:
        targets = operation_task_store.get_managed_retry_targets(sorted({int(value) for value in managed.values()}))
    except Exception:
        action_logger.exception("任务中心受管批量重试归属读取失败")
        return {task_id: ({"ok": False, "unavailable": True,
            "error_code": "managed_retry_unavailable", "error": "批量任务重跑暂不可用，请刷新后重试"}, 503)
            for task_id in managed}
    replies = {}
    groups: dict[int, dict[int, int]] = defaultdict(dict)
    for task_id, target_round_id in managed.items():
        target = targets.get(int(target_round_id))
        if not target:
            replies[task_id] = ({"ok": False, "error": "批量任务归属缺失，已保留原任务，请检查数据。"}, 409)
            continue
        groups[int(target["batch_id"])][task_id] = int(target["canonical_target_id"])

    for batch_id, members in groups.items():
        scope = {"kind": "targets", "target_ids": [str(value) for value in sorted(set(members.values()))]}
        try:
            result = service.create_round(
                batch_id, {"source": {"view": "current"}, "selection": scope},
                f"operations-bulk-retry:{request_key}" if request_key else f"manual-task-retry:{uuid.uuid4().hex}",
            )
            reply = {"ok": True, "accepted": True, "state": result["state"]}, 202
        except ValueError as exc:
            reply = {"ok": False, "error": str(exc)}, getattr(exc, "status", 409)
        except Exception:
            action_logger.exception("任务中心受管批量重试轮次创建失败：batch_id=%s", batch_id)
            reply = {"ok": False, "unavailable": True, "error_code": "managed_retry_unavailable",
                "error": "批量任务重跑暂不可用，请刷新后重试"}, 503
        replies.update(dict.fromkeys(members, reply))
    return replies


def perform_bulk_action(
    task_ids: list[int],
    action: str,
    *,
    request_key: str | None = None,
    operation_logger: logging.Logger | None = None,
) -> dict:
    """保留原应用层调用签名。"""
    return accept_bulk_operation_action(action, task_ids, request_key=request_key, operation_logger=operation_logger)


def retry_legacy_account_task(task_id: int, *, operation_logger: logging.Logger | None = None) -> tuple[dict, int]:
    """Resolve a historical account task to its current retry service."""
    task = account_task_store.get_task(task_id)
    if not task:
        return {"ok": False, "error": "任务实例不存在"}, 404
    from core.bulk_operations.execution import retry_managed
    managed_retry = retry_managed(task)
    if managed_retry is not None:
        return {"ok": True, **managed_retry}, 202
    if task.get("status") in {"queued", "running"}:
        return {"ok": False, "error": "任务仍在执行"}, 409
    account = db.get_account(int(task.get("account_id") or 0))
    if not account:
        return {"ok": False, "error": "关联账号不存在"}, 404
    if db.account_is_deactivated(account):
        return {
            "ok": False,
            "deactivated": True,
            "error": "账号已废号，不能重跑",
        }, 409
    task_type = str(task.get("task_type") or "")
    if task_type in {"live_check", "token_refresh"}:
        queued = live_check_service.enqueue_account_live_check(
            account_id=int(account["id"]),
            email=str(account.get("email") or ""),
            trigger="token_refresh_manual_retry" if task_type == "token_refresh" else "manual_retry",
            proxy=None,
            force_refresh=task_type == "token_refresh",
        )
    elif task_type == "plan_check":
        queued = plan_check_service.enqueue_account_plan_check(
            account_id=int(account["id"]),
            email=str(account.get("email") or ""),
            access_token=str(account.get("access_token") or ""),
            trigger="manual_retry",
            proxy=None,
        )
    elif task_type == "deactivation_mail":
        queued = deactivation_mail_service.enqueue(int(account["id"]), trigger="manual_retry")
    elif task_type == "extract_link":
        result_summary = task.get("result_summary") if isinstance(task.get("result_summary"), dict) else {}
        queued = extract_link_service.enqueue_account_extract(
            account_id=int(account["id"]),
            email=str(account.get("email") or ""),
            access_token=str(account.get("access_token") or ""),
            trigger="manual_retry",
            # 失败类型会由提炼服务重新检查并自动换下一个可用类型。
            link_type=str(result_summary.get("link_type") or "") or None,
        )
    elif task_type == "codex_retry":
        queued = codex_operation_service.submit(
            email=str(account.get("email") or ""),
            trigger="manual_retry",
        )
    elif task_type in {"account_setup_retry", "password_setup", "password_change", "twofa_setup", "twofa_change"}:
        step_map = {
            "account_setup_retry": None,
            "password_setup": {"password"},
            "password_change": {"password"},
            "twofa_setup": {"twofa"},
            "twofa_change": {"twofa"},
        }
        operation_map = {
            "password_change": "password_change",
            "twofa_change": "twofa_change",
        }
        from config.account import completion_settings
        from core.accounts import operation_coordinator, operation_handlers

        queued = operation_coordinator.enqueue_account_setup(
            int(account["id"]),
            trigger="manual_retry",
            steps=step_map[task_type],
            task_type=task_type,
            operation=operation_map.get(task_type),
            snapshot_bundle=operation_settings.runtime_execution_settings(completion_settings(), operation_logger=runtime_logger),
            register_handlers=operation_handlers.register_runtime_handlers,
            operation_logger=operation_logger or runtime_logger,
        )
    elif task_type == "account_completion":
        from config.account import completion_settings
        from core.accounts import operation_coordinator, operation_handlers

        queued = operation_coordinator.enqueue_account_completion(
            int(account["id"]),
            trigger="manual_retry_completion",
            snapshot_bundle=operation_settings.runtime_execution_settings(completion_settings(), operation_logger=runtime_logger),
            register_handlers=operation_handlers.register_runtime_handlers,
            operation_logger=operation_logger or runtime_logger,
        )
    elif task_type == "codex_token_refresh":
        summary = task.get("result_summary") if isinstance(task.get("result_summary"), dict) else {}
        task_data = task.get("data") if isinstance(task.get("data"), dict) else {}
        filename = str(
            summary.get("filename")
            or task_data.get("credential_filename")
            or ""
        )
        queued = codex_token_refresh_service.enqueue_refresh(
            filename,
            trigger="manual_task_center_retry",
            allow_unknown_manual_retry=True,
        )
    else:
        return {"ok": False, "error": "该任务类型暂不支持重跑"}, 400
    if queued.get("busy"):
        return {"ok": False, **queued}, 409
    if not queued.get("accepted"):
        return {"ok": False, **queued}, 400
    return {"ok": True, **queued}, 202


def retry_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    from core.bulk_operations.execution import retry_managed
    managed_retry = retry_managed(task)
    if managed_retry is not None:
        return managed_retry
    if str(task.get("source_system") or "") != RUNTIME_SOURCE_SYSTEM:
        return {"accepted": False, "busy": False, "error": "任务来源不属于 WebUI runtime"}
    if task_gateway.operation_is_deactivated(task):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已废号，不能重跑",
        }
    account_id = int(task.get("account_id") or 0)
    if account_id and db.account_is_deactivated(db.get_account(account_id)):
        return {
            "accepted": False,
            "busy": False,
            "deactivated": True,
            "error": "账号已废号，不能重跑",
        }
    if str(task.get("status") or "").lower() in {
        "queued", "running", "cancelling", "settling", "stopping", "waiting",
    }:
        return {"accepted": False, "busy": True, "error": "任务仍在执行"}
    from core.accounts.completion import completion_plan

    data = task.get("data") if isinstance(task.get("data"), Mapping) else {}
    settings = operation_settings.completion_settings_from_snapshot(data.get("config_snapshot"))
    if task.get("task_type") == "account_completion":
        steps = set(completion_plan(db.get_account(account_id), settings)["missing_steps"])
        unavailable = operation_settings.completion_deployment_unavailable(steps, settings)
    elif task.get("task_type") != "registration_resume":
        from core.runtime.capabilities import account_setup_unavailable

        steps = set(data.get("steps") or {"password", "plan_check", "twofa"})
        unavailable = account_setup_unavailable(
            steps, settings, force_twofa_change=bool(data.get("force_twofa_change")),
            force_password_reset=task.get("task_type") == "password_change" or bool(data.get("force_password_reset")),
        )
    else:
        from core.registration import service as registration_service

        source_job = db.get_job(int(data.get("source_job_id") or 0))
        unavailable = registration_service.registration_deployment_unavailable(
            registration_service.registration_options_for_job(source_job),
        )
    if unavailable:
        return unavailable
    try:
        run = operation_task_store.retry_runtime_task(
            int(task["id"]),
            trigger="manual_retry",
            data={"retry_action": "manual_retry"},
        )
    except (LookupError, ValueError) as exc:
        return {"accepted": False, "busy": False, "error": str(exc)}
    task_gateway.notify_dispatch()
    return {
        "accepted": True,
        "busy": False,
        "reused": False,
        "task_id": int(task["id"]),
        "run_id": int(run["id"]),
        "account_id": account_id or None,
        "email": str(task.get("email_snapshot") or ""),
        "status": "queued",
        "source_system": RUNTIME_SOURCE_SYSTEM,
    }


def cancel_runtime_task(task: Mapping[str, Any]) -> dict[str, Any]:
    if str(task.get("source_system") or "") != RUNTIME_SOURCE_SYSTEM:
        return {"ok": False, "error": "任务来源不属于 WebUI runtime"}
    active = next(
        (
            run for run in reversed(task.get("runs") or [])
            if str(run.get("status") or "") in {
                "queued", "running", "cancelling", "settling", "stopping", "waiting",
            }
        ),
        None,
    )
    if not active:
        return {"ok": True, "running": False, "state": "empty", "message": "任务没有活跃 attempt"}
    try:
        cancel_options = {"reason": "用户手动停止 WebUI durable operation"}
        if task.get("_expected_run_status"):
            cancel_options["expected_status"] = task["_expected_run_status"]
        run = operation_task_store.request_run_cancel(int(active["id"]), **cancel_options)
    except LookupError as exc:
        return {"ok": False, "error": str(exc)}
    if run.get("cancel_skipped"):
        return {"ok": False, **run}
    task_gateway.notify_dispatch()
    return {
        "ok": True,
        "run_id": int(active["id"]),
        "running": str(run.get("status") or "") != "cancelled",
        "state": str(run.get("status") or "cancelling"),
        "message": "已记录停止请求，任务将在安全检查点收口",
    }
