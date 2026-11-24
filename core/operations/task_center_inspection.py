"""任务中心巡检父任务重跑的集合受理；执行仍由原巡检 Worker 负责。"""
from __future__ import annotations

import logging

from core.accounts.inspection import service
from core.operations import run_log, task_gateway
from core.storage.accounts import inspection_retry_many, inspections
from core.storage.operations import store

logger = logging.getLogger("webui.routes.operations")


def accept_retries(tasks: dict[int, dict]) -> dict[int, tuple[dict, int]]:
    selected, output = [], {}
    for task_id, task in tasks.items():
        if task.get("status") in inspections.ACTIVE or task_gateway.operation_is_deactivated(task):
            continue
        handler = task_gateway.operation_action(task.get("task_type") or "", "retry",
                                                source_system=task.get("source_system"))
        if handler is not service._retry_parent:
            continue
        try:
            data = task.get("data") or {}
            workers, archived = int(data.get("workers", 3)), data.get("archived", "0")
            if type(workers) is not int or not 1 <= workers <= 16:
                raise ValueError("巡检并发必须为 1–16 的整数，实际并发同时受账号操作共享预算限制")
            inspections.validate_scope(archived)
        except Exception as exc:
            output[task_id] = ({"ok": False, "error": f"重试入口异常：{type(exc).__name__}: {exc}"}, 503)
            continue
        selected.append({"task_id": task_id, "workers": workers, "archived": archived})
    if not selected:
        return output
    try:
        config = task_gateway.normalize_config_snapshot(service.get_config_snapshot(), allowlist=service.CONFIG_ALLOWLIST)
        store.init()
        with store._connect() as conn, conn.transaction():
            replies, logs = inspection_retry_many.create_retries_many(conn, selected, config_snapshot=config)
    except Exception:
        logger.exception("任务中心批量巡检重跑受理失败")
        output.update({spec["task_id"]: ({"ok": False, "error": "巡检重跑入队失败，请刷新后重试"}, 503)
                       for spec in selected})
        return output
    for log in logs:
        run_log.append(log["log_file"], level="INFO", message=log["message"],
            task_id=log["task_id"], run_id=log["run_id"], stage=log["stage"], event_type=log["event_type"])
    if any(reply["created"] for reply in replies.values()):
        task_gateway.notify_dispatch()
    output.update({task_id: ({"ok": True, **reply}, 202) for task_id, reply in replies.items()})
    return output
