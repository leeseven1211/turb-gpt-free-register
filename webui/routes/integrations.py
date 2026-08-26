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

def create_integrations_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("integrations", __name__)
    logger = context.logger


    @bp.get("/api/roxy/workspaces")
    def api_roxy_workspaces():
        try:
            from core.roxybrowser_client import RoxyBrowserClient
            result = RoxyBrowserClient().list_workspaces()
            return jsonify(result)
        except Exception as exc:
            logger.exception("获取 Roxy 团队/工作区失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @bp.post("/api/proxy-provider/test")
    def api_proxy_provider_test():
        """实际提取并检测一个 1024Proxy IP，供配置页本地联调。"""
        data = request.get_json(silent=True) or {}
        lease = None
        try:
            from core.proxy_provider import acquire_1024_proxy, release_proxy

            lease = acquire_1024_proxy(
                api_url=str(data.get("api_url") or "").strip() or None,
                protocol=str(data.get("protocol") or "").strip() or None,
                # 空字符串有明确语义：本次测试沿用 API URL 里的 region，
                # 不能回退到进程中已经保存的 PROXY_1024_REGION。
                region=str(data.get("region") or "").strip(),
                session_minutes=data.get("session_minutes"),
                validate=bool(data.get("validate", True)),
                job_id="webui-test",
            )
            result = lease.public_dict()
            release_proxy(lease, reason="webui_test")
            lease = None
            return jsonify({
                "ok": True,
                "lease": result,
                "message": "已成功提取并检测 1 个 1024Proxy IP；测试租约已在本地释放",
            })
        except Exception as exc:
            logger.warning("1024Proxy 本地测试失败：%s", type(exc).__name__)
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}), 400
        finally:
            if lease is not None:
                try:
                    from core.proxy_provider import release_proxy
                    release_proxy(lease, reason="webui_test_failed")
                except Exception:
                    pass

    @bp.post("/api/icloud-hme/test")
    def api_icloud_hme_test():
        """连接本机 iCloud HME 服务、同步别名池并验证实际转发收件通道。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.icloud_hme_client import test_connection

            result = test_connection(
                api_base=str(data.get("api_base") or "").strip() or None,
                account_id=str(data.get("account_id") or "").strip() or None,
                timeout=data.get("timeout"),
            )
            return jsonify({
                "ok": True,
                **result,
                "message": (
                    f"连接成功：远端 {result.get('remote_aliases', 0)} 个别名，"
                    f"本地可用 {result.get('pool', {}).get('available', 0)} 个，"
                    f"收件通道 {result.get('inbox_method') or 'unknown'}"
                ),
            })
        except Exception as exc:
            logger.warning("iCloud HME 本地测试失败：%s", type(exc).__name__)
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}), 400

    @bp.post("/api/email-butler/test-connection")
    def api_email_butler_test_connection():
        """验证 Email Butler URL、Key、策略与必要能力，不回显 Key。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.email_butler_client import test_connection

            result = test_connection(
                api_base=str(data.get("api_base") or "").strip() or None,
                api_key=str(data.get("api_key") or "").strip() or None,
            )
            return jsonify(result)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:260]}"}), 400

    @bp.get("/api/email-butler/leases")
    def api_email_butler_leases():
        """列出当前 WebUI 进程持有的 Email Butler 租约。"""
        from core.email_butler_client import active_mailbox_leases
        return jsonify({"ok": True, "items": active_mailbox_leases()})

    @bp.post("/api/email-butler/leases")
    def api_email_butler_lease_create():
        """手动租用一个邮箱，供资源页检查平台供给情况。"""
        try:
            from core.email_butler_client import active_mailbox_leases, pick_account
            account = pick_account()
            item = next(
                (row for row in active_mailbox_leases() if row.get("email") == account.email),
                {"email": account.email, "mailbox_id": account.mailbox_id},
            )
            return jsonify({"ok": True, "item": item})
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:260]}"}), 400

    @bp.post("/api/email-butler/leases/release")
    def api_email_butler_lease_release():
        """释放一个由当前 WebUI 进程持有的 Email Butler 租约。"""
        data = request.get_json(silent=True) or {}
        email = str(data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return jsonify({"ok": False, "error": "email 参数无效"}), 400
        try:
            from core.email_butler_client import get_account_context, release_account
            if get_account_context(email) is None:
                return jsonify({"ok": False, "error": "当前进程未持有该邮箱租约"}), 404
            release_account(email, status=str(data.get("status") or "available"), note="WebUI 手动释放")
            return jsonify({"ok": True, "email": email})
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:260]}"}), 400

    return bp
