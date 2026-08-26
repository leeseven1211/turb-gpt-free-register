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

def create_dashboard_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("dashboard", __name__)
    logger = context.logger
    _prepared_downloads = context.prepared_downloads

    @bp.get("/api/downloads/<download_id>")
    def api_prepared_download(download_id: str):
        item = _prepared_downloads.pop(str(download_id or ""), None)
        if not item:
            return jsonify({"ok": False, "error": "下载已过期或不存在，请重新生成"}), 404
        content = item.get("content") or b""
        filename = item.get("filename") or "download.zip"
        mimetype = item.get("mimetype") or "application/octet-stream"
        return Response(
            content,
            mimetype=mimetype,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
                "X-Download-Options": "noopen",
            },
        )

    @bp.get("/favicon.ico", endpoint="favicon")
    def favicon():
        return redirect(url_for("static", filename="favicon.svg"), code=308)

    @bp.get("/")
    def index():
        requested_ui = (request.args.get("ui") or "").strip().lower()
        if requested_ui in {"legacy", "modern"}:
            ui_mode = requested_ui
        else:
            ui_mode = (request.cookies.get("ui_mode") or "modern").strip().lower()
            if ui_mode not in {"legacy", "modern"}:
                ui_mode = "modern"

        template_name = "index_legacy.html" if ui_mode == "legacy" else "index.html"
        resp = make_response(render_template(template_name))
        if requested_ui in {"legacy", "modern"}:
            resp.set_cookie("ui_mode", ui_mode, max_age=60 * 60 * 24 * 365, samesite="Lax")
        return resp

    @bp.get("/api/summary")
    def api_summary():
        from config import email as _email_cfg
        from core.email_provider import parse_email_sources
        pool = {"total": 0, "available": 0, "used": 0, "failed": 0}
        for src in parse_email_sources(_email_cfg.EMAIL_SOURCE):
            # GPTMail/MailNest/CloudMail 地址按需生成，不属于本地邮箱池。
            if src in ("gptmail", "mailnest", "cloudmail", "cloudflare", "email_butler"):
                continue
            one = (
                db.generic_api_email_pool_summary() if src == "generic_api"
                else db.domain_email_pool_summary() if src == "cloudflare_domain"
                else db.icloud_hide_email_pool_summary() if src == "icloud_hide"
                else db.outlook_pool_summary()
            )
            for k in pool:
                pool[k] += int(one.get(k, 0) or 0)
        domain_pool = db.domain_email_pool_summary()
        return jsonify({
            "accounts": db.count_accounts(),
            "outlook_total": pool.get("total", 0),
            "outlook_available": pool.get("available", 0),
            "outlook_used": pool.get("used", 0),
            "outlook_failed": pool.get("failed", 0),
            "domain_total": domain_pool.get("total", 0),
            "domain_available": domain_pool.get("available", 0),
            "domain_used": domain_pool.get("used", 0),
            "domain_failed": domain_pool.get("failed", 0),
        })

    @bp.get("/api/dashboard")
    def api_dashboard():
        """平台总览：仅返回聚合、配置状态与脱敏的运行中租约。"""
        from config import email as email_cfg
        from core.email_provider import EMAIL_SOURCE_LABELS, parse_email_sources
        from core.proxy_provider import active_proxy_leases, registration_proxy_mode
        aggregates = admin_repository.dashboard_aggregates()
        account_counts = aggregates["accounts"]
        job_counts = dict(aggregates["jobs"]["counts"])
        job_counts["active"] = sum(int(job_counts.get(key, 0) or 0) for key in ("pending", "running", "stopping"))
        today = datetime.now().date().isoformat()
        today_counts = {key: int(aggregates["jobs"]["today_counts"].get(key, 0) or 0) for key in ("success", "partial_success", "failed")}
        pool_counts: dict[str, dict[str, int]] = {}
        for row in aggregates["email_status_rows"]:
            source = str(row.get("source") or "")
            status = str(row.get("status") or "available")
            pool_counts.setdefault(source, {})[status] = int(row.get("count") or 0)
        local_pools = []
        for source, label in (
            ("outlook", "Outlook"),
            ("generic_api", "通用 API"),
            ("cloudflare_domain", "域名邮箱"),
            ("icloud_hide", "iCloud 隐藏邮箱"),
        ):
            summary = dict(pool_counts.get(source) or {})
            summary["total"] = sum(summary.values())
            local_pools.append((source, label, summary))
        enabled_sources = set(parse_email_sources(email_cfg.EMAIL_SOURCE))
        pool_rows = [
            {
                "source": source,
                "label": label,
                "kind": "local_pool",
                "enabled": source in enabled_sources,
                **{key: int(summary.get(key, 0) or 0) for key in ("total", "available", "used", "failed", "disabled")},
            }
            for source, label, summary in local_pools
        ]
        on_demand_sources = ("email_butler", "gptmail", "mailnest", "cloudmail", "cloudflare")
        pool_rows.extend({
            "source": source,
            "label": EMAIL_SOURCE_LABELS.get(source, source),
            "kind": "on_demand",
            "enabled": source in enabled_sources,
        } for source in on_demand_sources)

        active_leases = active_proxy_leases()
        return jsonify({
            "ok": True,
            "accounts": {
                "total": int(account_counts.get("total") or 0),
                "active": int(account_counts.get("active") or 0),
                "archived": int(account_counts.get("archived") or 0),
                "codex_ready": int(account_counts.get("codex_ready") or 0),
                "plans": account_counts.get("plans") or {},
            },
            "jobs": {
                "total": int(aggregates["jobs"].get("total") or 0),
                "counts": job_counts,
                "today": today,
                "today_counts": today_counts,
            },
            "email": {
                "sources": pool_rows,
                "local_total": sum(int(item.get("total", 0) or 0) for item in pool_rows),
                "local_available": sum(int(item.get("available", 0) or 0) for item in pool_rows),
                "enabled_count": len(enabled_sources),
            },
            "proxy": {
                "platform": registration_proxy_mode(),
                "active_leases": len(active_leases),
                "leases": active_leases,
            },
            "codex": aggregates["codex"],
        })

    @bp.get("/api/capabilities")
    def api_capabilities():
        """返回不含密钥的功能可用性及缺失配置原因。"""
        from core.feature_availability import feature_availability
        return jsonify(feature_availability())

    return bp
