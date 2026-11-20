from __future__ import annotations

import re

from flask import jsonify, request, send_file

from core import operation_task_store
from core.storage.task_query_context import TaskSchemaUnavailable
from core.operations.contracts import OperationQuery
from core.operations import action_service, query_service
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext


_RECEIPT_REFERENCE = re.compile(r"([1-9][0-9]{0,18})(?::([1-9][0-9]{0,18}))?")


def create_operations_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("operations", __name__)
    logger = context.logger

    @bp.app_errorhandler(TaskSchemaUnavailable)
    def task_schema_unavailable(_error):
        return jsonify({"ok": False, "error_code": "task_schema_not_ready", "error": "任务中心数据库结构尚未就绪"}), 503

    @bp.get("/api/account-tasks")
    def api_account_tasks():
        """账号操作任务实例列表；结果与事件均不包含账号凭据。"""
        result = query_service.list_legacy_account_tasks(
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=50, type=int),
            task_type=str(request.args.get("type") or "").strip(),
            status=str(request.args.get("status") or "").strip(),
            q=str(request.args.get("q") or "").strip(),
        )
        return jsonify(result)

    @bp.get("/api/account-tasks/<int:task_id>")
    def api_account_task_detail(task_id: int):
        task = query_service.get_legacy_account_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务实例不存在"}), 404
        return jsonify({"ok": True, "task": task})

    @bp.post("/api/account-tasks/<int:task_id>/retry")
    def api_account_task_retry(task_id: int):
        payload, status = action_service.retry_legacy_account_task(task_id, operation_logger=logger)
        return jsonify(payload), status

    @bp.get("/api/operations")
    def api_operations():
        """统一任务中心列表：注册、恢复、Codex 与账号操作共用一个读模型。"""
        include_facets = str(request.args.get("include_facets") or "1").lower() not in {"0", "false", "no"}
        include_batches = str(request.args.get("include_batches") or "1").lower() not in {"0", "false", "no"}
        query = OperationQuery(
            include_facets=include_facets,
            include_batches=include_batches,
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
        result = query_service.list_operations(query)
        return jsonify(result)

    @bp.get("/api/operations/receipts")
    def api_operation_receipt_statuses():
        references = request.args.getlist("ref")
        if not 1 <= len(references) <= 20:
            return jsonify({"ok": False, "error": "每次可查询 1 至 20 条任务回执"}), 400
        pairs = []
        for value in references:
            match = _RECEIPT_REFERENCE.fullmatch(value)
            if match is None:
                return jsonify({"ok": False, "error": "任务回执编号格式无效"}), 400
            task_id = int(match[1])
            run_id = int(match[2]) if match[2] else None
            if task_id >= 2**63 or (run_id is not None and run_id >= 2**63):
                return jsonify({"ok": False, "error": "任务回执编号超出范围"}), 400
            pairs.append((task_id, run_id))
        response = jsonify({"ok": True, "items": query_service.get_operation_receipt_statuses(pairs)})
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/api/operations/<int:task_id>")
    def api_operation_detail(task_id: int):
        include_events = str(request.args.get("include_events") or "1").strip().lower() not in {
            "0", "false", "no", "off",
        }
        task = query_service.get_operation(task_id, include_events=include_events)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        for run in task.get("runs") or []:
            if task.get("source_system") == "native_operations":
                from core.operations import debug as operation_debug

                debug = operation_debug.describe(task, run)
                if debug["available"]:
                    base = f"/api/operations/{task_id}/runs/{int(run['id'])}/debug"
                    debug["har_url"] = f"{base}/har"
                    debug["page_state_url"] = f"{base}/page-state" if debug["page_state_available"] else ""
                    debug["screenshot_url"] = f"{base}/screenshot" if debug["screenshot_available"] else ""
                    run["debug_artifacts"] = debug
        return jsonify({"ok": True, "task": task})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/debug/<artifact>")
    def api_operation_debug_artifact(task_id: int, run_id: int, artifact: str):
        """通过任务归属校验读取对应 Run 的诊断，不接受任意文件路径。"""
        from core.operations import debug as operation_debug
        from core.registration import debug as registration_debug

        task = operation_task_store.get_task(task_id, include_events=False)
        if not task or task.get("source_system") != "native_operations":
            return jsonify({"ok": False, "error": "刷新 AT 调试任务不存在"}), 404
        run = next((item for item in task.get("runs") or [] if int(item["id"]) == run_id), None)
        if run is None or artifact not in {"har", "page-state", "screenshot"}:
            return jsonify({"ok": False, "error": "调试运行或产物不存在"}), 404
        debug = operation_debug.describe(task, run)
        if not debug["available"]:
            return jsonify({"ok": False, "error": "该次运行未生成调试产物"}), 404
        job = operation_debug.artifact_job(task, run)
        if artifact == "screenshot":
            screenshot = registration_debug.screenshot_path(job)
            if screenshot is None:
                return jsonify({"ok": False, "error": "该次运行没有失败截图"}), 404
            response = send_file(screenshot, mimetype="image/png", max_age=0)
        else:
            if artifact == "page-state" and not debug["page_state_available"]:
                return jsonify({"ok": False, "error": "该次运行没有页面现场"}), 404
            payload = registration_debug.build_har(job) if artifact == "har" else registration_debug.read_page_state(job)
            response = jsonify(payload)
            extension = "har" if artifact == "har" else "json"
            response.headers["Content-Disposition"] = f'attachment; filename="at-refresh-{task_id}-{run_id}.{extension}"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/progress")
    def api_operation_run_progress(task_id: int, run_id: int):
        try:
            progress = query_service.get_run_progress(task_id, run_id)
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, "progress": progress})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/events")
    def api_operation_run_events(task_id: int, run_id: int):
        try:
            result = query_service.list_run_events(
                task_id,
                run_id,
                after_id=request.args.get("after_id", default=None, type=int),
                limit=request.args.get("limit", default=200, type=int),
            )
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        return jsonify({"ok": True, **result})

    @bp.get("/api/operations/<int:task_id>/runs/<int:run_id>/logs")
    def api_operation_run_logs(task_id: int, run_id: int):
        try:
            result = query_service.read_run_logs(
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
        data = request.get_json(silent=True)
        driver_override = None
        if isinstance(data, dict) and "driver" in data:
            driver_override = data["driver"]
            if not isinstance(driver_override, str) or driver_override not in {"roxy", "protocol"}:
                return jsonify({"ok": False, "error": "driver 只能是 roxy 或 protocol"}), 400
        retry_options = {}
        if isinstance(data, dict) and "diagnostic_after_mfa" in data:
            diagnostic_after_mfa = data["diagnostic_after_mfa"]
            if not isinstance(diagnostic_after_mfa, bool):
                return jsonify({"ok": False, "error": "diagnostic_after_mfa 必须是布尔值"}), 400
            if diagnostic_after_mfa:
                if driver_override != "protocol":
                    return jsonify({"ok": False, "error": "diagnostic_after_mfa=true 必须显式指定 driver=protocol"}), 400
                retry_options["diagnostic_after_mfa"] = True
        payload, status = action_service.perform_operation_action(
            task_id, "retry", driver_override=driver_override, **retry_options,
            request_key=request.headers.get("Idempotency-Key"), operation_logger=logger,
        )
        return jsonify(payload), status

    @bp.post("/api/operations/<int:task_id>/delete")
    def api_operation_delete(task_id: int):
        """从任务中心隐藏单个非执行中的任务，但保留审计记录。"""
        payload, status = action_service.delete_operation(task_id)
        return jsonify(payload), status

    @bp.post("/api/operations/bulk")
    def api_operations_bulk():
        """批量执行任务中心动作；逐条校验并返回跳过原因。"""
        data = request.get_json(silent=True) or {}
        action = str(data.get("action") or "").strip().lower()
        raw_ids = data.get("task_ids") or data.get("ids") or []
        if action not in {"retry", "cancel", "terminate", "delete"}:
            return jsonify({"ok": False, "error": "action 必须是 retry、cancel、terminate 或 delete"}), 400
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

        result = action_service.perform_bulk_action(
            task_ids, action, request_key=request.headers.get("Idempotency-Key"), operation_logger=logger,
        )
        return jsonify(result)

    @bp.post("/api/operations/<int:task_id>/cancel")
    def api_operation_cancel(task_id: int):
        payload, status = action_service.perform_operation_action(task_id, "cancel", operation_logger=logger)
        return jsonify(payload), status

    @bp.post("/api/operations/<int:task_id>/terminate")
    def api_operation_terminate(task_id: int):
        """终止任务中心中的活动 durable operation；排队任务按取消收口。"""
        payload, status = action_service.perform_operation_action(task_id, "terminate", operation_logger=logger)
        return jsonify(payload), status

    return bp
