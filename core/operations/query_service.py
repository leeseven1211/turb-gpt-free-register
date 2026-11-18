"""任务中心只读查询、能力元数据和公开结果投影。"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from core import account_task_store, operation_task_store
from core.codex import token_refresh_service as codex_token_refresh_service
from core.operations.contracts import OperationQuery
from core.operations.errors import classify_task_error
from core.operations.presentation import public_progress_snapshot, public_result_status
from core.registration import service as svc


def _project_owned_record(result: dict, *, task_type: str = "") -> dict:
    """就地投影查询服务独占的响应副本。"""
    summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
    original_status = result.get("internal_status", result.get("status"))
    for key in ("status", "target_status"):
        original = result.get(f"internal_{key}", result.get(key))
        projected = public_result_status(original, summary)
        if original is not None and projected != original:
            result[f"internal_{key}"] = original
            result[key] = projected
    if result.get("error_message") or result.get("status") in {"failed", "partial_success", "interrupted", "deactivated"}:
        info = classify_task_error(
            result.get("error_message") or result.get("error"),
            stage=str(result.get("failure_stage") or summary.get("failure_stage") or
                      (result.get("data") or {}).get("failure_stage") or
                      result.get("current_stage") or result.get("progress_stage") or ""),
            task_type=str(result.get("task_type") or task_type),
            error_code=str(result.get("error_code") or ""),
            result_summary=summary,
            task_status=str(original_status or ""),
        )
        if info:
            result["error_info"] = info
    return result


def _attach_owned_legacy_task_error(task: dict, *, task_status: str) -> None:
    error_info = classify_task_error(
        task.get("error"),
        stage="complete",
        task_type=str(task.get("task_type") or ""),
        error_code=str(task.get("error_code") or ""),
        result_summary=task.get("result_summary"),
        task_status=task_status,
    )
    if error_info:
        task["error_info"] = error_info


def list_legacy_account_tasks(
    *, page: int = 1, page_size: int = 50, task_type: str = "", status: str = "", q: str = "",
) -> dict:
    from core.accounts.token_refresh import settings as token_refresh_settings

    result = dict(account_task_store.list_tasks(
        public_status=True, page=page, page_size=page_size, task_type=task_type, status=status, q=q,
    ))
    items = deepcopy(result.get("items") or [])
    for task in items:
        _attach_owned_legacy_task_error(task, task_status=str(task.get("internal_status") or task.get("status") or ""))
        _project_owned_record(task)
    result["items"] = items
    result["token_refresh"] = token_refresh_settings()
    result["codex_token_refresh"] = codex_token_refresh_service.settings()
    return result


def get_legacy_account_task(task_id: int) -> dict | None:
    source = account_task_store.get_task(task_id)
    if not source:
        return None
    task = deepcopy(source)
    _attach_owned_legacy_task_error(task, task_status=str(task.get("status") or ""))
    return _project_owned_record(task)


def list_operations(query: OperationQuery) -> dict:
    result = dict(operation_task_store.list_tasks(**query.store_arguments(), public_status=True))
    if not query.include_batches:
        result.pop("batches", None)
    if not query.include_facets:
        result.pop("facets", None)
    items = deepcopy(result.get("items") or [])
    # 能力元数据以内部状态为准，响应保留原有的公开状态。
    for task in items:
        for key in ("status", "target_status"):
            if f"internal_{key}" in task:
                task[key] = task[f"internal_{key}"]
    svc.attach_registration_resume_retry_info(items)
    result["items"] = [_project_owned_record(task) for task in items]
    if query.include_batches:
        fields = {"id", "batch_uuid", "title", "batch_type", "status", "created_at"}
        result["batches"] = [
            {key: public_result_status(value) if key == "status" else value
             for key, value in batch.items() if key in fields}
            for batch in operation_task_store.list_batches(limit=50)
        ]
    result["revision"] = hashlib.sha256(json.dumps(
        [result.get("total"), result.get("items")], sort_keys=True, default=str,
    ).encode()).hexdigest()[:20]
    return result


def get_operation(task_id: int, *, include_events: bool = True) -> dict | None:
    source = operation_task_store.get_task(task_id, include_events=include_events)
    if not source:
        return None
    task = deepcopy(source)
    svc.attach_registration_resume_retry_info([task])
    _project_owned_record(task)
    task["runs"] = [_project_owned_record(run, task_type=str(task.get("task_type") or ""))
                    for run in task.get("runs") or []]
    if isinstance(task.get("parent"), dict):
        _project_owned_record(task["parent"])
    return task


def get_run_progress(task_id: int, run_id: int) -> dict:
    progress = operation_task_store.get_run_progress(task_id, run_id, public_status=True)
    return public_progress_snapshot(progress)


def list_run_events(task_id: int, run_id: int, *, after_id: int | None = None, limit: int = 200) -> dict:
    """省略游标读取最近一页，传 0 从最早事件开始。"""
    return operation_task_store.list_task_events(task_id, run_id=run_id, after_id=after_id, limit=limit)
