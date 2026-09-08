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
        task = operation_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if task.get("status") in {"queued", "running", "stopping", "cancelling", "settling", "waiting"}:
            return jsonify({"ok": False, "error": "任务仍在执行"}), 409
        if str(task.get("source_system") or "") == "native_operations":
            queued = codex_operation_service.retry_task(int(task_id), trigger="manual_retry")
            if queued.get("busy"):
                return jsonify({"ok": False, **queued}), 409
            if not queued.get("accepted"):
                return jsonify({"ok": False, **queued}), 503 if queued.get("unavailable") else 409
            return jsonify({"ok": True, **queued}), 202
        next_action = (task.get("next_actions") or [{}])[0]
        source_job_id = next_action.get("source_job_id") if isinstance(next_action, dict) else None
        if str((next_action or {}).get("action") or "") in {"registration_resume", "registration_retry"} and source_job_id:
            result = svc.retry_job(int(source_job_id))
            status = int(result.pop("status", 200 if result.get("ok") else 400))
            return jsonify(result), status
        runs = task.get("runs") or []
        latest = runs[-1] if runs else {}
        source_system = str(latest.get("source_system") or "")
        source_id = str(latest.get("source_id") or "")
        if source_system == "registration_jobs" and source_id.isdigit():
            result = svc.retry_job(int(source_id))
            status = int(result.pop("status", 200 if result.get("ok") else 400))
            return jsonify(result), status
        if source_system == "account_action_tasks" and source_id.isdigit():
            payload, status = _retry_account_task_result(int(source_id))
            return jsonify(payload), status
        return jsonify({"ok": False, "error": "该历史任务没有可用的重跑来源"}), 409

    @bp.post("/api/operations/<int:task_id>/cancel")
    def api_operation_cancel(task_id: int):
        task = operation_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if str(task.get("source_system") or "") != "native_operations":
            return jsonify({"ok": False, "error": "历史兼容任务请使用原任务停止入口"}), 409
        active = next(
            (
                run for run in reversed(task.get("runs") or [])
                if run.get("status") in {"queued", "running", "cancelling", "settling"}
            ),
            None,
        )
        if not active:
            return jsonify({"ok": True, "state": "empty", "message": "任务没有活跃 attempt"})
        result = codex_operation_service.request_cancel(run_id=int(active["id"]))
        return jsonify(result), 200 if result.get("ok") else 409

    return bp
