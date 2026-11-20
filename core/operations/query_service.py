"""任务中心只读应用服务：收拢查询、能力说明与公开结果投影。

该服务只读取既有仓储；注册重跑能力仍由注册服务核验。HTTP 参数与文件响应留在路由，
执行、状态写入、重试与调度均继续使用原有入口。
"""
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
from core.storage.task_query_context import task_query


def public_operation_record(record: dict, *, task_type: str = "") -> dict:
    """只调整公开结果，原始状态和回执继续供执行器与排障使用。"""
    return _project_owned_record(deepcopy(record), task_type=task_type)


def _project_owned_record(result: dict, *, task_type: str = "") -> dict:
    """投影查询服务已独占的响应副本；不得传入仓储原对象。"""
    summary = result.get("result_summary") if isinstance(result.get("result_summary"), dict) else {}
    original_status = result.get("internal_status", result.get("status"))
    for key in ("status", "target_status"):
        original = result.get(f"internal_{key}", result.get(key))
        projected = public_result_status(original, summary)
        if original is not None and projected != original:
            result[f"internal_{key}"] = original
            result[key] = projected
    if result.get("error_message") or result.get("status") in {"failed", "partial_success", "interrupted", "deactivated", "cancelled"}:
        info = classify_task_error(
            result.get("error_message") or result.get("error"),
            stage=str(result.get("failure_stage") or summary.get("failure_stage") or
                      (result.get("data") or {}).get("failure_stage") or
                      result.get("current_stage") or result.get("progress_stage") or ""),
            task_type=str(result.get("task_type") or task_type),
            error_code=str(result.get("error_code") or ""),
            result_summary=summary,
            task_status=str(original_status or ""),
            cancel_reason=str(result.get("cancel_reason") or ""),
        )
        if info:
            result["error_info"] = info
    return result


def _attach_owned_legacy_task_error(task: dict, *, task_status: str) -> None:
    """在服务独占的副本上保留旧来源的完成阶段分类。"""
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


@task_query()
def list_legacy_account_tasks(
    *, page: int = 1, page_size: int = 50, task_type: str = "", status: str = "", q: str = "",
) -> dict:
    """读取旧账号任务来源，保留分页、错误信息及两类刷新配置。"""
    result = dict(account_task_store.list_tasks(
        public_status=True, page=page, page_size=page_size, task_type=task_type, status=status, q=q,
    ))
    items = deepcopy(result.get("items") or [])
    for task in items:
        _attach_owned_legacy_task_error(
            task, task_status=str(task.get("internal_status") or task.get("status") or ""),
        )
    result["items"] = [_project_owned_record(task) for task in items]
    from core.accounts.token_refresh import settings as token_refresh_settings
    result["token_refresh"] = token_refresh_settings()
    result["codex_token_refresh"] = codex_token_refresh_service.settings()
    return result


@task_query()
def get_legacy_account_task(task_id: int) -> dict | None:
    """按旧任务 ID 读取详情，保留详情与列表原有的分类输入差异。"""
    source = account_task_store.get_task(task_id)
    if not source:
        return None
    task = deepcopy(source)
    _attach_owned_legacy_task_error(task, task_status=str(task.get("status") or ""))
    return _project_owned_record(task)


def _attach_public_registration_actions(items: list[dict]) -> None:
    """注册重跑能力始终用内部事实核验，完成后再恢复公开结果。"""
    for task in items:
        for key in ("status", "target_status"):
            if f"internal_{key}" in task:
                task[key] = task[f"internal_{key}"]
    svc.attach_registration_resume_retry_info(items)


@task_query()
def list_operations(query: OperationQuery) -> dict:
    """读取一页任务；元数据和列表修订保持现有接口语义。"""
    result = dict(operation_task_store.list_tasks(**query.store_arguments(), public_status=True))
    if not query.include_batches:
        result.pop("batches", None)
    if not query.include_facets:
        result.pop("facets", None)
    # 能力校验先读取内部事实，公开投影只在响应副本上进行。
    items = deepcopy(result.get("items") or [])
    _attach_public_registration_actions(items)
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


@task_query()
def find_account_request_receipts(request_key: str) -> list[dict[str, str]]:
    """按账号页请求编号找回已受理任务。"""
    return operation_task_store.find_account_request_receipts(request_key)


@task_query()
def get_operation_receipt_statuses(references: list[tuple[int, int | None]]) -> list[dict]:
    """只投影回执轮询所需的公开状态与提示。"""
    items = []
    for row in operation_task_store.get_operation_receipt_statuses(references):
        status = public_result_status(row["status"], {"requested_status": row["requested_status"]}) or "queued"
        items.append({
            "task_id": str(row["task_id"]),
            "run_id": str(row["run_id"]) if row["run_id"] is not None else None,
            "status": status,
            "message": row["error_message"] or row["summary_message"] or ("已确认完成" if status == "success" else ""),
        })
    return items


@task_query()
def get_operation(task_id: int, *, include_events: bool = True) -> dict | None:
    """读取详情，公开每次运行的结果且保留完整历史和恢复能力。"""
    source = operation_task_store.get_task(task_id, include_events=include_events)
    if not source:
        return None
    task = deepcopy(source)
    svc.attach_registration_resume_retry_info([task])
    task = _project_owned_record(task)
    task["runs"] = [_project_owned_record(run, task_type=str(task.get("task_type") or ""))
                    for run in task.get("runs") or []]
    if isinstance(task.get("parent"), dict):
        task["parent"] = _project_owned_record(task["parent"])
    return task


@task_query()
def get_run_progress(task_id: int, run_id: int) -> dict:
    """公开进度保留原始回执证据，实例归属由现有仓储核验。"""
    progress = operation_task_store.get_run_progress(task_id, run_id, public_status=True)
    return public_progress_snapshot(progress)


@task_query()
def list_run_events(task_id: int, run_id: int, *, after_id: int | None = None, limit: int = 200) -> dict:
    """省略游标读取最近一页；传 0 从最早事件开始。"""
    return operation_task_store.list_task_events(task_id, run_id=run_id, after_id=after_id, limit=limit)


@task_query()
def read_run_logs(task_id: int, run_id: int, *, cursor: int | None = None, limit: int = 500) -> dict:
    """沿用日志字节游标与既有任务/实例归属核验。"""
    return operation_task_store.read_task_run_log(task_id, run_id, cursor=cursor, limit=limit)
