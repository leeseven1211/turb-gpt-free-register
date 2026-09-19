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
from config.schema import ConfigValidationError, config_revision
from webui import config_editor
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext

logger = logging.getLogger(__name__)

def create_config_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("config", __name__)
    logger = context.logger


    @bp.get("/api/config")
    def api_config_get():
        return jsonify(config_editor.get_config())

    @bp.get("/api/config/snapshot")
    def api_config_snapshot():
        """返回任务可绑定的非敏感配置快照；进程内对象本身保持不可变。"""
        snapshot = config_editor.get_config_snapshot()
        return jsonify({
            "config_revision": snapshot.revision,
            "values": snapshot.as_dict(),
            "sources": dict(snapshot.sources),
        })

    @bp.get("/api/ui-settings")
    def api_ui_settings():
        """返回前端启动所需的最小非敏感运行参数。

        列表页和注册页只需要这两个值；不要在启动阶段为了读取它们
        下载完整的配置编辑器元数据（其中包含大量字段说明和选项）。
        """
        snapshot = config_editor.get_config_snapshot().as_dict()
        return jsonify({
            "account_batch_workers": snapshot.get("ACCOUNT_BATCH_WORKERS", 3),
            "account_live_check_driver": snapshot.get("ACCOUNT_LIVE_CHECK_DRIVER", ""),
            "config_revision": config_revision(),
        })

    @bp.post("/api/cloudmail/gen-token")
    def api_cloudmail_gen_token():
        """手动生成 CloudMail Authorization Token，并把本次填写的 CloudMail 配置一并写入 .env。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.cloudmail_client import gen_token

            api_base = (data.get("api_base") or "").strip()
            admin_email = (data.get("email") or data.get("admin_email") or "").strip()
            password = (data.get("password") or "").strip()
            path = (data.get("path") or "/api/public/genToken").strip() or "/api/public/genToken"
            token = gen_token(
                email=admin_email,
                password=password,
                path=path,
                base_url=api_base,
            )
            updates = {"CLOUDMAIL_AUTH_TOKEN": token}
            # 生成 Token 时用户通常尚未点“保存配置”；这里同步保存本次填写的字段，
            # 避免 loadConfig() 后 API 地址/账号/密码被旧 .env 值覆盖。
            if api_base:
                updates["CLOUDMAIL_API_BASE"] = api_base
            if admin_email:
                updates["CLOUDMAIL_ADMIN_EMAIL"] = admin_email
            if password:
                updates["CLOUDMAIL_PASSWORD"] = password
            if path:
                updates["CLOUDMAIL_TOKEN_PATH"] = path
            result = config_editor.update_config(updates)
            return jsonify({
                "ok": True,
                "token": token,
                "written": result.get("env_updated", []),
                "reloaded": bool(result.get("reloaded")),
                "config_revision": result.get("config_revision", config_revision()),
                "message": "CloudMail Token 已生成，且当前 CloudMail 配置已保存",
            })
        except ConfigValidationError as exc:
            return jsonify({
                "ok": False,
                "error": "配置校验失败",
                "fields": dict(exc.errors),
            }), 400
        except Exception as exc:
            logger.exception("生成 CloudMail Token 失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @bp.post("/api/cloudmail/domains")
    def api_cloudmail_domains():
        """从 CloudMail 平台获取域名列表，并可写入 .env 作为本地缓存。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.cloudmail_client import fetch_domains

            updates = {}
            api_base = (data.get("api_base") or "").strip()
            admin_email = (data.get("email") or data.get("admin_email") or "").strip()
            password = (data.get("password") or "").strip()
            token = (data.get("token") or "").strip()
            if api_base:
                updates["CLOUDMAIL_API_BASE"] = api_base
            if admin_email:
                updates["CLOUDMAIL_ADMIN_EMAIL"] = admin_email
            if password:
                updates["CLOUDMAIL_PASSWORD"] = password
            if token:
                updates["CLOUDMAIL_AUTH_TOKEN"] = token
            written = []
            config_result = None
            if updates:
                config_result = config_editor.update_config(updates)
                written.extend(config_result.get("env_updated", []))

            domains = fetch_domains(force=True)
            domain_result = config_editor.update_config({
                "CLOUDMAIL_DOMAINS": domains,
            })
            written.extend(domain_result.get("env_updated", []))
            return jsonify({
                "ok": True,
                "domains": domains,
                "count": len(domains),
                "written": written,
                "reloaded": bool(domain_result.get("reloaded")),
                "config_revision": domain_result.get(
                    "config_revision",
                    config_result.get("config_revision", config_revision())
                    if config_result else config_revision(),
                ),
                "message": f"已获取 {len(domains)} 个 CloudMail 可用域名并保存",
            })
        except ConfigValidationError as exc:
            return jsonify({
                "ok": False,
                "error": "配置校验失败",
                "fields": dict(exc.errors),
            }), 400
        except Exception as exc:
            logger.exception("获取 CloudMail 域名失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @bp.post("/api/config")
    def api_config_set():
        data = request.get_json(silent=True) or {}
        updates = data.get("updates") if isinstance(data.get("updates"), dict) else data
        if not isinstance(updates, dict) or not updates:
            return jsonify({"ok": False, "error": "无更新内容"}), 400
        try:
            result = config_editor.update_config(updates)
        except ConfigValidationError as exc:
            # 字段名和校验原因均来自 schema，不回显候选值（尤其是 secret）。
            return jsonify({
                "ok": False,
                "error": "配置校验失败",
                "fields": dict(exc.errors),
            }), 400
        except Exception as exc:
            logger.exception("配置写入失败")
            # update_config 在写盘或 reload 失败时已恢复原文件和进程环境。
            return jsonify({
                "ok": False,
                "error": f"配置保存失败（{type(exc).__name__}，未应用）",
            }), 500

        restart_required = result.get("restart_required", [])
        reload_ok = bool(result.get("reloaded"))
        if reload_ok and restart_required:
            note = f"✅ 已保存并热加载；{', '.join(restart_required)} 需重启后完整生效"
        elif reload_ok:
            note = "✅ 已保存并热加载，新值立即生效"
        else:
            note = "⚠️ 已保存但尚未热加载，需重启 Web 服务才能生效"
        return jsonify({
            "ok": True,
            "updated": result["updated"],
            "ignored": result["ignored"],
            "restart_required": restart_required,
            "reloaded": reload_ok,
            "config_revision": config_revision(),
            "note": note,
        })

    return bp
