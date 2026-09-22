from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pyotp
from flask import Response, jsonify, make_response, redirect, render_template, request, url_for

from core import (
    account_task_store,
    admin_repository,
    codex_operation_service,
    codex_retry_service,
    codex_token_refresh_service,
    db,
    deactivation_mail_service,
    extract_link_service,
    live_check_service,
    operation_task_store,
    plan_check_service,
)
from core import registration_service as svc
from core.operations import task_gateway
from core.task_errors import classify_task_error
from config import codex as codex_config
from webui import config_editor
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext

logger = logging.getLogger(__name__)

def create_operations_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("operations", __name__)
    logger = context.logger
    _retry_account_task_result = context.retry_account_task_result
    active_operation_statuses = {
        "queued", "running", "stopping", "cancelling", "settling", "waiting",
    }

    def _perform_operation_action(task_id: int, action: str, *, expected_status: str | None = None):
        """执行统一任务中心的单条动作，供单条和批量入口共用。"""
        task = operation_task_store.get_task(task_id)
        if not task:
            return {"ok": False, "error": "任务不存在"}, 404

        task_type = str(task.get("task_type") or "").strip()
        source_system = str(task.get("source_system") or "").strip()
        current_status = str(task.get("status") or "").strip().lower()
        if expected_status and current_status != expected_status:
            return {"ok": False, "error": "任务状态已变化，请刷新后重试"}, 409
        if action == "retry":
            if task_gateway.operation_is_deactivated(task):
                return {
                    "ok": False,
                    "deactivated": True,
                    "error": "账号已废号，不能重跑",
                }, 409
            if task.get("status") in active_operation_statuses:
                return {"ok": False, "error": "任务仍在执行"}, 409
            registered_action = task_gateway.operation_action(
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
                queued = codex_operation_service.retry_task(int(task_id), trigger="manual_retry")
                if queued.get("busy"):
                    return {"ok": False, **queued}, 409
                if not queued.get("accepted"):
                    return {"ok": False, **queued}, 503 if queued.get("unavailable") else 409
                return {"ok": True, **queued}, 202
            next_action = (task.get("next_actions") or [{}])[0]
            source_job_id = next_action.get("source_job_id") if isinstance(next_action, dict) else None
            if str((next_action or {}).get("action") or "") in {"registration_resume", "registration_retry"} and source_job_id:
                result = svc.retry_job(int(source_job_id))
                status = int(result.pop("status", 200 if result.get("ok") else 400))
                return result, status
            runs = task.get("runs") or []
            latest = runs[-1] if runs else {}
            source_system = str(latest.get("source_system") or "")
            source_id = str(latest.get("source_id") or "")
            if source_system == "registration_jobs" and source_id.isdigit():
                result = svc.retry_job(int(source_id))
                status = int(result.pop("status", 200 if result.get("ok") else 400))
                return result, status
            if source_system == "account_action_tasks" and source_id.isdigit():
                payload, status = _retry_account_task_result(int(source_id))
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

    @bp.get("/api/account-tasks")
    def api_account_tasks():
        """账号操作任务实例列表；结果与事件均不包含账号凭据。"""
        result = account_task_store.list_tasks(
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=50, type=int),
            task_type=str(request.args.get("type") or "").strip(),
            status=str(request.args.get("status") or "").strip(),
            q=str(request.args.get("q") or "").strip(),
        )
        for task in result.get("items") or []:
            error_info = classify_task_error(
                task.get("error"),
                stage="complete",
                task_type=str(task.get("task_type") or ""),
                error_code=str(task.get("error_code") or ""),
            )
            if error_info:
                task["error_info"] = error_info
        from core.token_refresh_service import settings as token_refresh_settings
        result["token_refresh"] = token_refresh_settings()
        result["codex_token_refresh"] = codex_token_refresh_service.settings()
        return jsonify(result)

    @bp.get("/api/account-tasks/<int:task_id>")
    def api_account_task_detail(task_id: int):
        task = account_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务实例不存在"}), 404
        error_info = classify_task_error(
            task.get("error"),
            stage="complete",
            task_type=str(task.get("task_type") or ""),
            error_code=str(task.get("error_code") or ""),
        )
        if error_info:
            task["error_info"] = error_info
        return jsonify({"ok": True, "task": task})

    @bp.post("/api/account-tasks/<int:task_id>/retry")
    def api_account_task_retry(task_id: int):
        payload, status = _retry_account_task_result(task_id)
        return jsonify(payload), status

    @bp.get("/api/operations")
    def api_operations():
        """统一任务中心列表：注册、恢复、Codex 与账号操作共用一个读模型。"""
        result = operation_task_store.list_tasks(
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=50, type=int),
            task_type=str(request.args.get("type") or "").strip(),
            status=str(request.args.get("status") or "").strip(),
            source=str(request.args.get("source") or "").strip(),
            q=str(request.args.get("q") or "").strip(),
            batch_id=request.args.get("batch_id", default=None, type=int),
            task_id=str(request.args.get("task_id") or "").strip(),
            target=str(request.args.get("target") or "").strip(),
            target_status=str(request.args.get("target_status") or "").strip(),
            batch=str(request.args.get("batch") or "").strip(),
            run_count=str(request.args.get("run_count") or "").strip(),
            stage=str(request.args.get("stage") or "").strip(),
            created_from=str(request.args.get("created_from") or "").strip(),
            created_to=str(request.args.get("created_to") or "").strip(),
            result=str(request.args.get("result") or "").strip(),
        )
        for task in result.get("items") or []:
            if task.get("error_message"):
                task["error_info"] = classify_task_error(
                    task.get("error_message"),
                    stage=str(task.get("current_stage") or ""),
                    task_type=str(task.get("task_type") or ""),
                    error_code=str(task.get("error_code") or ""),
                )
        result["batches"] = operation_task_store.list_batches(limit=50)
        return jsonify(result)

    @bp.get("/api/operations/<int:task_id>")
    def api_operation_detail(task_id: int):
        include_events = str(request.args.get("include_events") or "1").strip().lower() not in {
            "0", "false", "no", "off",
        }
        task = operation_task_store.get_task(task_id, include_events=include_events)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if task.get("error_message"):
            task["error_info"] = classify_task_error(
                task.get("error_message"),
                stage=str(task.get("current_stage") or ""),
                task_type=str(task.get("task_type") or ""),
                error_code=str(task.get("error_code") or ""),
            )
        return jsonify({"ok": True, "task": task})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/progress")
    def api_operation_run_progress(task_id: int, run_id: int):
        try:
            progress = operation_task_store.get_run_progress(task_id, run_id)
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, "progress": progress})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/events")
    def api_operation_run_events(task_id: int, run_id: int):
        try:
            result = operation_task_store.list_task_events(
                task_id,
                run_id=run_id,
                after_id=request.args.get("after_id", default=None, type=int),
                limit=request.args.get("limit", default=200, type=int),
            )
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, **result})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/logs")
    def api_operation_run_logs(task_id: int, run_id: int):
        try:
            result = operation_task_store.read_task_run_log(
                task_id,
                run_id,
                cursor=request.args.get("cursor", default=None, type=int),
                limit=request.args.get("limit", default=500, type=int),
            )
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, **result})

    @bp.post("/api/operations/<int:task_id>/retry")
    def api_operation_retry(task_id: int):
        """由服务端 next_actions 和来源映射选择重跑入口，前端不猜流程。"""
        payload, status = _perform_operation_action(task_id, "retry")
        return jsonify(payload), status

    @bp.post("/api/operations/bulk")
    def api_operations_bulk():
        """批量执行任务中心动作；逐条校验并返回跳过原因。"""
        data = request.get_json(silent=True) or {}
        action = str(data.get("action") or "").strip().lower()
        raw_ids = data.get("task_ids") or data.get("ids") or []
        if action not in {"retry", "cancel", "terminate"}:
            return jsonify({"ok": False, "error": "action 必须是 retry、cancel 或 terminate"}), 400
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"ok": False, "error": "task_ids 必须是非空数组"}), 400
        task_ids = []
        for raw_id in raw_ids:
            if isinstance(raw_id, bool) or not isinstance(raw_id, int):
                return jsonify({"ok": False, "error": "task_ids 必须都是整数"}), 400
            task_id = raw_id
            if task_id <= 0:
                return jsonify({"ok": False, "error": "task_ids 必须是正整数"}), 400
            if task_id not in task_ids:
                task_ids.append(task_id)
        if len(task_ids) > 100:
            return jsonify({"ok": False, "error": "单次最多处理 100 个任务"}), 400

        accepted = []
        skipped = []
        for task_id in task_ids:
            task = operation_task_store.get_task(task_id)
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
            payload, status = _perform_operation_action(
                task_id,
                action,
                expected_status=task_status,
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
        return jsonify({
            "ok": True,
            "action": action,
            "accepted": accepted,
            "accepted_count": len(accepted),
            "skipped": skipped,
            "skipped_count": len(skipped),
        })

    @bp.post("/api/operations/<int:task_id>/cancel")
    def api_operation_cancel(task_id: int):
        payload, status = _perform_operation_action(task_id, "cancel")
        return jsonify(payload), status

    @bp.post("/api/operations/<int:task_id>/terminate")
    def api_operation_terminate(task_id: int):
        """终止任务中心中的活动 durable operation；排队任务按取消收口。"""
        payload, status = _perform_operation_action(task_id, "terminate")
        return jsonify(payload), status

    return bp
