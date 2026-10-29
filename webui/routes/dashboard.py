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
from flask import Response, jsonify, redirect, render_template, request, url_for

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
from webui.display_statistics import DisplayStatisticsCache

logger = logging.getLogger(__name__)

def create_dashboard_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("dashboard", __name__)
    logger = context.logger
    _prepared_downloads = context.prepared_downloads
    statistics = DisplayStatisticsCache(ttl=15)

    def display_supply():
        from core.email_supply import email_supply_summary
        return statistics.get("email_supply", lambda: email_supply_summary(include_next_expiry=True))

    @bp.after_app_request
    def invalidate_changed_statistics(response):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 400:
            statistics.invalidate()
        return response

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
        # 统一使用当前界面，历史书签参数和界面偏好 Cookie 不再参与模板选择。
        return render_template("index.html")

    @bp.get("/api/summary")
    def api_summary():
        pool = display_supply()
        domain_pool = next((row for row in pool['sources'] if row['source'] == 'cloudflare_domain'), {})
        return jsonify({
            "email_supply": pool,
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
        from core.proxy_pool import pool_source
        from core.proxy_provider import active_proxy_leases
        aggregates = admin_repository.dashboard_aggregates()
        account_counts = aggregates["accounts"]
        job_counts = dict(aggregates["jobs"]["counts"])
        job_counts["active"] = sum(int(job_counts.get(key, 0) or 0) for key in ("pending", "running", "stopping"))
        today = datetime.now().date().isoformat()
        today_counts = {key: int(aggregates["jobs"]["today_counts"].get(key, 0) or 0) for key in ("success", "partial_success", "failed")}
        supply = display_supply()
        pool_rows = [{**row, 'dependency': False, 'dependency_reason': '',
                      'history_available': bool(row.get('total')), 'default_visible': bool(row.get('total'))}
                     for row in supply['sources']]
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
                "supply": supply,
                "sources": pool_rows,
                "local_total": sum(int(item.get("total", 0) or 0) for item in pool_rows),
                "local_available": sum(int(item.get("available", 0) or 0) for item in pool_rows),
                "enabled_count": sum(row["available"] > 0 for row in pool_rows),
            },
            "proxy": {
                "platform": pool_source(),
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
