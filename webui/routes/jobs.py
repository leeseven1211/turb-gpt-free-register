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
from flask import Response, jsonify, make_response, redirect, render_template, request, send_file, url_for

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
from core.task_stages import (
    DIAGNOSTIC_CONTEXT_FIELDS,
    ERROR_FIELDS,
    EVENT_BASE_FIELDS,
    EVENT_TYPES,
    STAGE_EVENT_FIELDS,
    WAIT_REASONS,
)
from config import codex as codex_config
from webui import config_editor
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext
from webui.route_helpers import _compact_job_for_list, _latest_progress_batch

logger = logging.getLogger(__name__)


def _diagnostic_event_contract() -> dict:
    return {
        "event_types": sorted(EVENT_TYPES),
        "base_fields": sorted(EVENT_BASE_FIELDS),
        "context_fields": sorted(DIAGNOSTIC_CONTEXT_FIELDS),
        "stage_fields": sorted(STAGE_EVENT_FIELDS),
        "wait_reasons": sorted(WAIT_REASONS),
        "error_fields": sorted(ERROR_FIELDS),
    }

def create_jobs_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("jobs", __name__)
    logger = context.logger


    @bp.get("/api/jobs")
    def api_jobs():
        limit = request.args.get("limit", default=100, type=int)
        status_filter = str(request.args.get("status", default="") or "").strip().lower()
        query = str(request.args.get("q", default="") or "").strip()
        id_filter = str(request.args.get("id", default="") or "").strip().lstrip("#")
        email_filter = str(request.args.get("email", default="") or "").strip().lower()
        email_source_filter = str(request.args.get("email_source", default="") or "").strip().lower()
        proxy_filter = str(request.args.get("proxy", default="") or "").strip().lower()
        error_filter = str(request.args.get("error", default="") or "").strip().lower()
        date_from = str(request.args.get("date_from", default="") or "").strip()
        date_to = str(request.args.get("date_to", default="") or "").strip()
        progress_batch_id = str(request.args.get("progress_batch_id", default="") or "").strip()
        paged = str(request.args.get("paged", default="") or "").lower() in {"1", "true", "yes"}
        page_arg = request.args.get("page", default=None, type=int)
        page_size_arg = request.args.get("page_size", default=None, type=int)
        from config import email as _email_cfg
        manual_otp_required = not bool(getattr(_email_cfg, "USE_EMAIL_SERVICE", True))
        page = max(1, int(page_arg or 1))
        page_size = max(1, min(500, int(page_size_arg or limit or 50)))
        result = admin_repository.list_jobs(
            admin_repository.PageRequest(
                page=page,
                page_size=page_size,
                filters={
                    "status": status_filter,
                    "q": query,
                    "id": id_filter,
                    "email": email_filter,
                    "email_source": email_source_filter,
                    "proxy": proxy_filter,
                    "error": error_filter,
                    "date_from": date_from,
                    "date_to": date_to,
                },
            ),
            progress_batch_id=progress_batch_id,
        )
        rows = result.get("items") or []
        for row in rows:
            row["manual_otp_required"] = manual_otp_required
        result["items"] = [_compact_job_for_list(row) for row in rows]
        result["progress_batch"] = _latest_progress_batch(result.pop("progress_rows", []))
        result["compact"] = True
        if not (paged or page_arg is not None or page_size_arg is not None):
            return jsonify(result["items"])
        return jsonify(result)

    @bp.get("/api/email-sources")
    def api_email_sources():
        """返回注册页可明确选择的邮箱来源；顺序来自全局启用列表。"""
        from config import email as _email_cfg
        from core.email_provider import EMAIL_SOURCE_LABELS, parse_email_sources

        use_service = bool(getattr(_email_cfg, "USE_EMAIL_SERVICE", True))
        sources = parse_email_sources(_email_cfg.EMAIL_SOURCE) if use_service else []
        return jsonify({
            "ok": True,
            "manual_mode": not use_service,
            "sources": [
                {"value": source, "label": EMAIL_SOURCE_LABELS.get(source, source)}
                for source in sources
            ],
        })

    @bp.post("/api/jobs")
    def api_jobs_create():
        """启动批量注册：body {count, workers, email_source, debug_enabled}。"""
        data = request.get_json(silent=True) or {}
        debug_enabled = bool(data.get("debug_enabled", False))
        try:
            count = int(data.get("count", 1))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "count 非法"}), 400
        if count < 1 or count > 200:
            return jsonify({"ok": False, "error": "count 需在 1~200 之间"}), 400

        # workers 控制本次新提交任务使用的线程池；若和上次不同，服务层会为新任务切换到新池。
        try:
            workers = max(1, min(16, int(data.get("workers", 3))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "workers 非法"}), 400

        if debug_enabled:
            from config import roxybrowser as _roxy_cfg
            driver_mode = str(getattr(_roxy_cfg, "REGISTRATION_DRIVER", "protocol") or "protocol").strip().lower()
            if driver_mode not in {"protocol", "api", "http", "roxy", "roxybrowser", "fingerprint", "browser"}:
                return jsonify({
                    "ok": False,
                    "error": f"调试抓包当前仅支持 Roxy 和 protocol，当前注册驱动为 {driver_mode}",
                }), 400

        # 提交前先确认池里有足够可用邮箱，给前端一个温和提示（不阻断）
        from config import email as _email_cfg
        from config import register as _register_cfg
        from core.email_provider import parse_email_sources, validate_email_source
        if not bool(getattr(_email_cfg, "USE_EMAIL_SERVICE", True)):
            reg_email = str(getattr(_register_cfg, "REGISTER_EMAIL", "") or "").strip()
            if not reg_email:
                return jsonify({
                    "ok": False,
                    "error": "手动模式未配置 REGISTER_EMAIL。请到配置页填写「手动注册邮箱」，或开启自动取邮箱+收码。",
                }), 400
            if count > 1:
                return jsonify({
                    "ok": False,
                    "error": "手动模式建议每次只跑 1 个任务（同一 REGISTER_EMAIL）。请把数量设为 1。",
                }), 400
            submit_kwargs = {"count": count, "workers": workers}
            if debug_enabled:
                submit_kwargs["debug_enabled"] = True
            jobs = svc.submit_registration(**submit_kwargs)
            return jsonify({
                "ok": True,
                "submitted": len(jobs),
                "jobs": jobs,
                "warning": f"手动 OTP 模式：将使用 {reg_email}；验证码请在任务页提交",
                "workers": workers,
                "debug_enabled": debug_enabled,
            })
        try:
            selected_source = validate_email_source(data.get("email_source"))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        configured_sources = parse_email_sources(_email_cfg.EMAIL_SOURCE)
        if selected_source not in configured_sources:
            return jsonify({
                "ok": False,
                "error": f"邮箱来源 {selected_source} 未在配置页 EMAIL_SOURCE 中启用",
            }), 400
        sources = [selected_source]
        if "email_butler" in sources:
            api_base = str(getattr(_email_cfg, "EMAIL_BUTLER_API_BASE", "") or "").strip()
            api_key = str(getattr(_email_cfg, "EMAIL_BUTLER_API_KEY", "") or "").strip()
            if not api_base:
                return jsonify({
                    "ok": False,
                    "error": "已选择 email_butler 邮箱来源，请填写 Email Butler API 地址（配置 → 邮箱 / OTP）。",
                }), 400
            if not api_key:
                return jsonify({
                    "ok": False,
                    "error": "已选择 email_butler 邮箱来源，请填写 Email Butler API Key（配置 → 邮箱 / OTP）。",
                }), 400
        if "gptmail" in sources:
            api_key = str(getattr(_email_cfg, "GPTMAIL_API_KEY", "") or "").strip()
            if not api_key:
                return jsonify({
                    "ok": False,
                    "error": "已选择 gptmail 邮箱来源，请填写 GPTMail API Key（配置 → 邮箱 / OTP）。",
                }), 400
        if "cloudflare" in sources:
            api_base = str(getattr(_email_cfg, "CLOUDFLARE_API_BASE", "") or "").strip()
            if not api_base:
                return jsonify({
                    "ok": False,
                    "error": "已选择 cloudflare 邮箱来源，请填写 Cloudflare API 地址（配置 → 邮箱 / OTP）。",
                }), 400
            auth_mode = str(getattr(_email_cfg, "CLOUDFLARE_AUTH_MODE", "none") or "none").strip().lower()
            accounts_path = str(getattr(_email_cfg, "CLOUDFLARE_PATH_ACCOUNTS", "/api/new_address") or "").strip().lower()
            api_key = str(getattr(_email_cfg, "CLOUDFLARE_API_KEY", "") or "").strip()
            needs_key = auth_mode in ("x-admin-auth", "bearer", "x-api-key", "query-key") or accounts_path.rstrip("/").endswith("/admin/new_address")
            if needs_key and not api_key:
                return jsonify({
                    "ok": False,
                    "error": "Cloudflare admin/鉴权模式需要填写 Cloudflare API Key（配置 → 邮箱 / OTP）。",
                }), 400
        if "mailnest" in sources:
            api_key = str(getattr(_email_cfg, "MAIL_NEST_API_KEY", "") or "").strip()
            project_code = str(getattr(_email_cfg, "MAIL_NEST_PROJECT_CODE", "") or "").strip()
            if not api_key:
                return jsonify({
                    "ok": False,
                    "error": "已选择 mailnest 邮箱来源，请填写 MailNest API Key（配置 → 邮箱 / OTP）。",
                }), 400
            if not project_code:
                return jsonify({
                    "ok": False,
                    "error": "已选择 mailnest 邮箱来源，请填写 MailNest 项目代码（配置 → 邮箱 / OTP）。",
                }), 400
        if "cloudmail" in sources:
            api_base = str(getattr(_email_cfg, "CLOUDMAIL_API_BASE", "") or "").strip()
            token = str(getattr(_email_cfg, "CLOUDMAIL_AUTH_TOKEN", "") or "").strip()
            if not api_base:
                return jsonify({
                    "ok": False,
                    "error": "已选择 cloudmail 邮箱来源，请填写 CloudMail API 地址（配置 → 邮箱 / OTP）。",
                }), 400
            if not token:
                return jsonify({
                    "ok": False,
                    "error": "已选择 cloudmail 邮箱来源，请填写 CloudMail Token（配置 → 邮箱 / OTP）。",
                }), 400
        if "icloud_hide" in sources:
            api_base = str(getattr(_email_cfg, "ICLOUD_HME_API_BASE", "") or "").strip()
            if not api_base:
                return jsonify({
                    "ok": False,
                    "error": "已选择 icloud_hide 邮箱来源，请填写 iCloud HME 服务地址（配置 → 邮箱 / OTP）。",
                }), 400
            try:
                from core.icloud_hme_client import sync_aliases
                sync_aliases(force=False)
            except Exception as exc:
                return jsonify({
                    "ok": False,
                    "error": f"iCloud HME 服务不可用：{type(exc).__name__}: {str(exc)[:240]}",
                }), 400
        if "gptmail" in sources or "mailnest" in sources or "cloudmail" in sources or "cloudflare" in sources or "email_butler" in sources:
            # 临时邮箱在任务开始时动态生成，不需要本地邮箱池容量提示。
            warning = ""
        elif sources == ["icloud_hide"]:
            pool = db.icloud_hide_email_pool_summary()
            warning = ""
            if pool.get("available", 0) < count:
                auto_create = bool(getattr(_email_cfg, "ICLOUD_HME_AUTO_CREATE", False))
                suffix = "，不足的会按需创建" if auto_create else "，不足的会失败"
                warning = f"iCloud 隐藏邮箱池仅 {pool.get('available', 0)} 个可用，少于任务数 {count}{suffix}"
        elif "cloudflare_domain" in sources:
            pool = db.domain_email_pool_summary()
            warning = ""
            if sources == ["cloudflare_domain"] and pool.get("available", 0) < count:
                warning = f"域名邮箱池仅 {pool.get('available', 0)} 个可用，少于任务数 {count}，不足的会自动生成"
        elif sources == ["generic_api"]:
            pool = db.generic_api_email_pool_summary()
            warning = ""
            if pool.get("available", 0) < count:
                warning = f"通用 API 邮箱池仅 {pool.get('available', 0)} 个可用，少于任务数 {count}，不足的会失败"
        elif len(sources) > 1:
            available = 0
            if "outlook" in sources:
                available += db.outlook_pool_summary().get("available", 0)
            if "generic_api" in sources:
                available += db.generic_api_email_pool_summary().get("available", 0)
            if "cloudflare_domain" in sources:
                available += db.domain_email_pool_summary().get("available", 0)
            if "icloud_hide" in sources:
                available += db.icloud_hide_email_pool_summary().get("available", 0)
            warning = ""
            if available < count:
                warning = f"多个邮箱池合计仅 {available} 个可用，少于任务数 {count}，不足的会失败"
        else:
            pool = db.outlook_pool_summary()
            warning = ""
            if pool.get("available", 0) < count:
                warning = f"可用邮箱仅 {pool.get('available', 0)} 个，少于任务数 {count}，不足的会失败"
        submit_kwargs = {"count": count, "email_source": selected_source, "workers": workers}
        if debug_enabled:
            submit_kwargs["debug_enabled"] = True
        jobs = svc.submit_registration(**submit_kwargs)
        return jsonify({
            "ok": True,
            "submitted": len(jobs),
            "jobs": jobs,
            "warning": warning,
            "workers": workers,
            "email_source": selected_source,
            "debug_enabled": debug_enabled,
        })

    @bp.get("/api/manual-otp/waiting")
    def api_manual_otp_waiting():
        """列出当前正在等待手动验证码的邮箱。"""
        from core.manual_otp import list_waiting
        return jsonify({"ok": True, "waiting": list_waiting()})

    @bp.post("/api/manual-otp")
    def api_manual_otp_submit():
        """提交手动邮箱验证码。Body: {email, code} 或 {job_id, code}。"""
        from core.manual_otp import submit_manual_otp
        data = request.get_json(silent=True) or {}
        code = (data.get("code") or data.get("otp") or "").strip()
        email = (data.get("email") or "").strip()
        job_id = data.get("job_id")
        if not email and job_id is not None:
            job = db.get_job(int(job_id))
            email = (job or {}).get("email") or ""
        if not email:
            return jsonify({"ok": False, "error": "email/job_id 缺失"}), 400
        try:
            result = submit_manual_otp(email, code)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @bp.post("/api/jobs/cancel-pending")
    def api_jobs_cancel_pending():
        """取消所有还在排队（status=pending）的任务。已在 running 的不动。"""
        cancelled = svc.cancel_pending_jobs()
        return jsonify({"ok": True, "cancelled": cancelled})

    @bp.post("/api/jobs/batches/<batch_id>/cancel")
    def api_batch_jobs_cancel(batch_id: str):
        """只取消指定批次中尚未启动的任务。"""
        cancelled = svc.cancel_pending_jobs(batch_id=batch_id)
        return jsonify({"ok": True, "batch_id": batch_id, "cancelled": cancelled})

    @bp.post("/api/jobs/batches/<batch_id>/stop")
    def api_batch_jobs_stop(batch_id: str):
        """一次停止指定批次的运行中任务，避免前端逐任务并发请求。"""
        data = request.get_json(silent=True) or {}
        result = svc.request_stop_batch(
            batch_id,
            cancel_pending=bool(data.get("cancel_pending", False)),
        )
        if not result.get("ok"):
            return jsonify(result), int(result.get("status") or 400)
        return jsonify(result)

    @bp.post("/api/jobs/<int:job_id>/stop")
    def api_job_stop(job_id: int):
        """手动停止单个注册任务。pending 取消；running 发送停止信号。"""
        result = svc.request_stop_job(job_id)
        if not result.get("ok"):
            return jsonify({"ok": False, "error": result.get("error") or "停止失败"}), int(result.get("status") or 400)
        return jsonify(result)

    @bp.post("/api/jobs/<int:job_id>/retry")
    def api_job_retry(job_id: int):
        """重试失败/停止/取消任务；服务端自动判断完整注册或 Codex 补跑。"""
        data = request.get_json(silent=True) or {}
        try:
            workers = max(1, min(16, int(data.get("workers", svc.get_executor_workers()))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "workers 非法"}), 400
        result = svc.retry_job(job_id, workers=workers)
        if not result.get("ok"):
            return jsonify(result), int(result.get("status") or 400)
        return jsonify(result)

    @bp.post("/api/jobs/retry-bulk")
    def api_jobs_retry_bulk():
        """批量重试任务；不支持项逐条跳过并返回原因。"""
        data = request.get_json(silent=True) or {}
        job_ids = data.get("job_ids") or data.get("ids") or []
        if not isinstance(job_ids, list) or not job_ids:
            return jsonify({"ok": False, "error": "job_ids 必须是非空数组"}), 400
        if len(job_ids) > 500:
            return jsonify({"ok": False, "error": "单次最多重试 500 个任务"}), 400
        try:
            workers = max(1, min(16, int(data.get("workers", svc.get_executor_workers()))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "workers 非法"}), 400

        started: list[dict] = []
        reused: list[dict] = []
        skipped: list[dict] = []
        retry_batch_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-retry-{uuid.uuid4().hex[:8]}"
        created_in_batch = 0
        seen: set[int] = set()
        normalized_ids: list[int] = []
        for raw_id in job_ids:
            try:
                one_id = int(raw_id)
            except (TypeError, ValueError):
                skipped.append({"id": raw_id, "reason": "ID 非法"})
                continue
            if one_id in seen:
                continue
            seen.add(one_id)
            normalized_ids.append(one_id)
        for one_id in normalized_ids:
            result = svc.retry_job(
                one_id,
                workers=workers,
                batch_id=retry_batch_id,
                batch_index=created_in_batch + 1,
                batch_size=len(normalized_ids),
            )
            result_job = result.get("job") or {}
            if str(result_job.get("batch_id") or "") == retry_batch_id:
                created_in_batch += 1
            if not result.get("ok"):
                skipped.append({"id": one_id, "reason": result.get("error") or "不能重试"})
            elif result.get("reused"):
                reused.append(result)
            else:
                started.append(result)
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "reused": reused,
            "reused_count": len(reused),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "workers": workers,
            "batch_id": retry_batch_id if created_in_batch else "",
        })

    @bp.post("/api/jobs/<int:job_id>/delete")
    def api_job_delete(job_id: int):
        """删除一个任务记录。运行中的任务不允许删除；排队任务删除后执行前会自动跳过。"""
        debug_job = db.get_job(job_id)
        deleted, skipped = db.delete_jobs([job_id], delete_log=True, allow_running=False)
        if not deleted:
            reason = skipped[0]["reason"] if skipped else "任务不存在"
            status_code = 409 if "运行中" in reason else 404
            return jsonify({"ok": False, "error": reason}), status_code
        if debug_job:
            try:
                from core.registration_debug import delete_job_artifacts
                delete_job_artifacts(debug_job)
            except Exception:
                logger.exception("删除任务 #%s 的调试产物失败", job_id)
        return jsonify({"ok": True, "deleted": True})

    @bp.post("/api/jobs/delete-bulk")
    def api_jobs_delete_bulk():
        """批量删除任务记录。running 任务跳过，其它任务删除记录和日志。"""
        data = request.get_json(silent=True) or {}
        job_ids = data.get("job_ids") or data.get("ids") or []
        if not isinstance(job_ids, list) or not job_ids:
            return jsonify({"ok": False, "error": "job_ids 必须是非空数组"}), 400
        if len(job_ids) > 1000:
            return jsonify({"ok": False, "error": "单次最多删除 1000 个任务"}), 400

        invalid: list[dict] = []
        seen: set[int] = set()
        valid_ids: list[int] = []
        for raw_id in job_ids:
            try:
                job_id = int(raw_id)
            except (TypeError, ValueError):
                invalid.append({"id": raw_id, "reason": "ID 非法"})
                continue
            if job_id in seen:
                continue
            seen.add(job_id)
            valid_ids.append(job_id)

        debug_jobs = {job_id: db.get_job(job_id) for job_id in valid_ids}
        deleted_rows, skipped = db.delete_jobs(valid_ids, delete_log=True, allow_running=False)
        skipped = invalid + skipped
        deleted = [int(row["id"]) for row in deleted_rows]
        try:
            from core.registration_debug import delete_job_artifacts
            for deleted_id in deleted:
                debug_job = debug_jobs.get(deleted_id)
                if debug_job:
                    delete_job_artifacts(debug_job)
        except Exception:
            logger.exception("批量删除注册任务调试产物失败")
        return jsonify({"ok": True, "deleted": deleted, "deleted_count": len(deleted), "skipped": skipped})

    @bp.get("/api/jobs/<int:job_id>/debug")
    def api_job_debug(job_id: int):
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if not bool(job.get("debug_enabled", False)):
            return jsonify({"ok": True, "enabled": False, "job_id": job_id, "events": []})
        from core.registration_debug import active_summary, read_events
        errors_only = str(request.args.get("errors_only", "") or "").lower() in {"1", "true", "yes"}
        try:
            limit = max(1, min(1000, int(request.args.get("limit", 300) or 300)))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit 必须是整数"}), 400
        try:
            events = read_events(job, limit=limit, errors_only=errors_only)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        return jsonify({
            "ok": True,
            "enabled": True,
            "job_id": job_id,
            "state": job.get("debug_state") or "",
            "hold_until": job.get("debug_hold_until") or "",
            "pause_reason": job.get("debug_pause_reason") or "",
            "summary": active_summary(job_id) or job.get("debug_capture_summary") or {},
            "events": events,
        })

    @bp.get("/api/jobs/<int:job_id>/diagnostics")
    def api_job_diagnostics(job_id: int):
        """读取普通模式失败现场；不会把它伪装成全量调试抓包。"""
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        from config import registration_debug as diagnostics_config
        diagnostics_enabled = bool(getattr(diagnostics_config, "REGISTRATION_FAILURE_DIAGNOSTICS_ENABLED", True))
        summary = job.get("failure_diagnostics_summary") or {}
        state = str(job.get("failure_diagnostics_state") or "")
        captured = bool(summary) or state in {"captured", "completed"}
        if not captured:
            return jsonify({
                "ok": True,
                "enabled": diagnostics_enabled,
                "captured": False,
                "job_id": job_id,
                "event_contract": _diagnostic_event_contract(),
            })
        from core.registration_debug import read_events, read_page_state, read_timeline, screenshot_path
        try:
            limit = max(1, min(300, int(request.args.get("limit", 100) or 100)))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "limit 必须是整数"}), 400
        try:
            page_state = read_page_state(job)
            events = read_events(job, limit=limit, errors_only=True)
            timeline = read_timeline(job, limit=limit)
            screenshot = screenshot_path(job)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        error_info = classify_task_error(
            job.get("error_message") or job.get("error") or page_state.get("reason") or "",
            stage=str(job.get("progress_stage") or page_state.get("failure_stage") or ""),
            task_type=str(job.get("job_type") or "registration"),
            error_code=str(job.get("error_code") or ""),
        )
        summary = dict(summary) if isinstance(summary, dict) else {}
        context = {
            "job_id": job_id,
            "attempt_id": summary.get("attempt_id", job.get("attempt_id") or job.get("registration_attempt_id")),
            "run_id": summary.get("run_id", job.get("run_id") or job.get("registration_run_id")),
            "execution_id": summary.get("execution_id", job.get("execution_id")),
            "trigger_stage": summary.get("trigger_stage") or page_state.get("trigger_stage") or job.get("trigger_stage") or job.get("progress_stage") or "",
            "last_confirmed_state": summary.get("last_confirmed_state") or page_state.get("last_confirmed_state") or job.get("last_confirmed_state") or "",
            "failure_stage": summary.get("failure_stage") or page_state.get("failure_stage") or job.get("failure_stage") or job.get("progress_stage") or "",
        }
        return jsonify({
            "ok": True,
            "enabled": diagnostics_enabled,
            "captured": True,
            "job_id": job_id,
            "state": state or str(summary.get("state") or "captured"),
            "category": job.get("failure_diagnostics_category") or page_state.get("failure_category") or "unknown",
            "category_label": job.get("failure_diagnostics_category_label") or page_state.get("failure_category_label") or "未分类",
            "failure_reason": job.get("failure_diagnostics_failure_reason") or page_state.get("reason") or "",
            "summary": summary,
            "context": context,
            "email_evidence": summary.get("email_evidence") or page_state.get("email_evidence") or job.get("email_evidence") or {},
            "stage_timings": summary.get("stage_timings") or page_state.get("stage_timings") or [],
            "network_error_observed": bool(summary.get("network_error_observed", page_state.get("network_error_observed", False))),
            "error_info": summary.get("error_info") or page_state.get("error_info") or error_info or {},
            "error": summary.get("error") or page_state.get("error") or error_info or {},
            "page_state": page_state,
            "screenshot_url": f"/api/jobs/{job_id}/diagnostics/screenshot" if screenshot else "",
            "events": events,
            "timeline": timeline,
            "event_contract": _diagnostic_event_contract(),
        })

    @bp.get("/api/jobs/<int:job_id>/diagnostics/screenshot")
    def api_job_diagnostics_screenshot(job_id: int):
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        from core.registration_debug import screenshot_path
        try:
            path = screenshot_path(job)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        if path is None:
            return jsonify({"ok": False, "error": "失败现场截图不存在"}), 404
        response = send_file(path, mimetype="image/png", as_attachment=False, max_age=0)
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.post("/api/jobs/<int:job_id>/debug/release")
    def api_job_debug_release(job_id: int):
        data = request.get_json(silent=True) or {}
        from core.registration_debug import release_job
        result = release_job(job_id, action=str(data.get("action") or "finish"))
        if not result.get("ok"):
            return jsonify(result), int(result.get("status") or 409)
        return jsonify(result)

    @bp.get("/api/jobs/<int:job_id>/debug/har")
    def api_job_debug_har(job_id: int):
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if not bool(job.get("debug_enabled", False)):
            return jsonify({"ok": False, "error": "该任务未开启调试抓包"}), 409
        from core.registration_debug import build_har
        try:
            har = build_har(job)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 409
        payload = json.dumps(har, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response = Response(payload, mimetype="application/json")
        response.headers["Content-Disposition"] = f'attachment; filename="registration-job-{job_id}-raw.har"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @bp.get("/api/jobs/<int:job_id>/debug/compare")
    def api_job_debug_compare(job_id: int):
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if not bool(job.get("debug_enabled", False)):
            return jsonify({"ok": False, "error": "该任务未开启调试抓包"}), 409
        baseline_id = request.args.get("baseline_job_id", default=None, type=int)
        baseline = db.get_job(baseline_id) if baseline_id else None
        if baseline is not None and (
            not bool(baseline.get("debug_enabled", False))
            or str(baseline.get("batch_id") or "") != str(job.get("batch_id") or "")
            or str(baseline.get("status") or "") not in {"success", "partial_success"}
        ):
            return jsonify({"ok": False, "error": "对比任务必须是同批次的成功调试任务"}), 400
        if baseline is None:
            same_batch = [
                row for row in db.list_jobs(limit=2000)
                if int(row.get("id") or 0) != job_id
                and str(row.get("batch_id") or "") == str(job.get("batch_id") or "")
                and str(row.get("status") or "") in {"success", "partial_success"}
                and bool(row.get("debug_enabled", False))
            ]
            baseline = same_batch[0] if same_batch else None
        if baseline is None:
            return jsonify({"ok": False, "error": "同批次没有可用于对比的成功调试任务"}), 409
        from core.registration_debug import compare_jobs
        return jsonify({"ok": True, **compare_jobs(job, baseline)})

    @bp.get("/api/jobs/<int:job_id>/log")
    def api_job_log(job_id: int):
        job = db.get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        error_info = classify_task_error(
            job.get("error_message"),
            stage=str(job.get("progress_stage") or ""),
            task_type=str(job.get("job_type") or "registration"),
        )
        if error_info:
            job["error_info"] = error_info
        return jsonify({
            "ok": True,
            "job": job,
            "log": svc.read_job_log(job_id),
        })

    return bp
