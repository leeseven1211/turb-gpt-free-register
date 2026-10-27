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

    @bp.get("/api/extract-link/types")
    def api_extract_link_types():
        """代理读取提链服务当前启用的类型，不要求配置 CDK。"""
        try:
            return jsonify(extract_link_service.query_link_types())
        except Exception as exc:
            logger.warning("读取提链类型失败：%s", type(exc).__name__)
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}), 400

    @bp.get("/api/extract-link/huanguang/cdk-quota")
    def api_huanguang_cdk_quota():
        """只读查询已保存的提链和扫码 CDK，不接受草稿密钥。"""
        def response(payload, status=200):
            result = jsonify(payload)
            result.status_code = status
            result.headers["Cache-Control"] = "no-store"
            return result

        if request.args or request.content_length:
            return response({"ok": False, "error": "此接口仅查询已保存的 CDK，不接受查询参数或草稿密钥"}, 400)
        try:
            quota = extract_link_service.query_huanguang_cdk_quota()
            if not isinstance(quota, dict) or quota.get("ok") is not True:
                raise ValueError("额度结果未确认")
            return response(quota)
        except Exception as exc:
            logger.warning("查询幻光 CDK 剩余次数失败：%s", type(exc).__name__)
            return response({"ok": False, "error": "无法确认幻光 CDK 剩余次数，请检查已保存的 CDK 或稍后重试"}, 503)

    @bp.post("/api/extract-link/huanguang/xxsyun-quota")
    def api_huanguang_xxsyun_quota():
        """查询幻光备用扫码剩余次数，不保存草稿 Key。"""
        def response(payload, status=200):
            result = jsonify(payload)
            result.status_code = status
            result.headers["Cache-Control"] = "no-store"
            return result

        data = request.get_json(silent=True)
        if (not isinstance(data, dict) or set(data) - {"api_key"}
                or ("api_key" in data and (not isinstance(data["api_key"], str) or len(data["api_key"]) > 512))):
            return response({"ok": False, "error": "查询参数无效，请检查 XXSYUN API Key"}, 400)
        try:
            return response(extract_link_service.query_huanguang_xxsyun_quota(api_key=data.get("api_key")))
        except Exception as exc:
            logger.warning("查询 XXSYUN 剩余次数失败：%s", type(exc).__name__)
            return response({"ok": False, "error": "查询未成功，请核对 XXSYUN API Key 或在平台查看剩余次数"}, 400)

    @bp.get("/api/icloud-hme/accounts")
    def api_icloud_hme_accounts():
        """只读已保存连接的账号目录，不同步、创建或领取隐藏邮箱。"""
        try:
            from core.icloud_hme_client import list_accounts

            accounts = list_accounts()
            return jsonify({"ok": True, "items": [
                {"id": str(item["id"]), "label": str(item.get("name") or item.get("label") or item["id"]),
                 "status": str(item.get("status") or "unknown")}
                for item in accounts if isinstance(item, dict) and item.get("id")
            ]})
        except Exception as exc:
            # 异常可能携带服务 URL 或凭据；页面只显示可操作的简短说明。
            logger.warning("读取 iCloud 账号目录失败：%s", type(exc).__name__)
            return jsonify({"ok": False, "error": "无法读取 iCloud 账号目录，请检查已保存的连接配置；当前账号选择已保留"}), 400

    @bp.post("/api/proxy-provider/test")
    def api_proxy_provider_test():
        """通过同一供给适配器提取、检测并释放一条测试线路。"""
        data = request.get_json(silent=True) or {}
        lease = None
        try:
            from contextlib import closing
            from core.proxy_provider import release_proxy
            from core.proxy_sources import get_source
            from core.proxy_supply import fetch_candidates

            source = get_source(str(data.get("provider") or "1024proxy"))
            options = source.options(
                api_url=str(data.get("api_url") or "").strip() or None,
                protocol=str(data.get("protocol") or "").strip() or None,
                # 空字符串沿用提取 URL 的 region，不回退历史供应商国家。
                region=str(data.get("region") or "").strip(),
                session_minutes=data.get("session_minutes"),
            )
            with closing(fetch_candidates(options, count=1, source=source.name)) as candidates:
                lease = next(candidates, None)
            if lease is None:
                raise RuntimeError("本轮没有通过出口检测的代理线路")
            result = lease.public_dict()
            release_proxy(lease, reason="webui_test")
            lease = None
            return jsonify({
                "ok": True,
                "lease": result,
                "message": f"已成功提取并检测 1 个 {source.label} IP；测试租约已在本地释放",
            })
        except Exception as exc:
            logger.warning("代理供应商本地测试失败：%s", type(exc).__name__)
            # 网络异常可能携带提取 URL、白名单 IP 或凭据，不向浏览器回传正文。
            return jsonify({"ok": False, "error": f"代理测试失败（{type(exc).__name__}），请检查当前来源的提取 API、白名单、额度和目标国家"}), 400
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
        data = request.get_json(silent=True)
        request_id = data.get("request_id") if isinstance(data, dict) else None
        try:
            valid_request_id = isinstance(request_id, str) and str(uuid.UUID(request_id)) == request_id
        except (ValueError, AttributeError):
            valid_request_id = False
        if not valid_request_id:
            return jsonify({"ok": False, "code": "invalid_request_id", "request_unknown": False,
                            "error": "request_id 必须是浏览器保存的有效 UUID"}), 400
        try:
            from core.email_butler_client import active_mailbox_leases, pick_account
            account = pick_account(owner_kind="manual", owner_id=request_id, acquisition_id="manual:" + request_id)
            item = next(
                (row for row in active_mailbox_leases() if row.get("email") == account.email),
                {"email": account.email, "mailbox_id": account.mailbox_id},
            )
            return jsonify({"ok": True, "item": item, "request_id": request_id, "request_unknown": False})
        except Exception as exc:
            unknown = bool(getattr(exc, "request_unknown", False))
            return jsonify({"ok": False, "request_id": request_id, "request_unknown": unknown,
                            "code": "request_unknown" if unknown else getattr(exc, "error_code", "") or "email_butler_claim_failed",
                            "error": f"{type(exc).__name__}: {str(exc)[:260]}"}), 409 if unknown else 400

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
