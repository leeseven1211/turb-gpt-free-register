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
from webui.route_helpers import _pool_source_arg

logger = logging.getLogger(__name__)


def _pool_row_for_source(email: str, source: str) -> dict | None:
    source = str(source or "").strip().lower()
    if source == "generic_api":
        return db.get_generic_api_email_by_email(email)
    if source == "cloudflare_domain":
        return db.get_domain_email_by_email(email)
    if source == "icloud_hide":
        return db.get_icloud_hide_email_by_email(email)
    return db.get_outlook_by_email(email)


def _parse_email_pool_import(text: str, source: str, *, include_account_fields: bool = False) -> dict:
    """Parse only the fields that belong to an email resource.

    ``include_account_fields`` is retained for old API clients that still send
    ``as_registered``. The new email UI never enables that path.
    """
    source = str(source or "").strip().lower()
    required = 2 if source == "generic_api" else 4
    records: list[dict] = []
    errors: list[dict] = []
    extra_fields = 0
    total_lines = 0
    for line_no, raw_line in enumerate(str(text or "").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        total_lines += 1
        parts = line.split("----") if "----" in line else line.split("====")
        parts = [part.strip() for part in parts]
        if len(parts) < required:
            errors.append({"line": line_no, "reason": f"需要 {required} 段字段"})
            continue
        email = parts[0]
        if "@" not in email or any(char.isspace() for char in email):
            errors.append({"line": line_no, "reason": "邮箱格式不正确"})
            continue
        if any(not part for part in parts[:required]):
            errors.append({"line": line_no, "reason": "必填字段不能为空"})
            continue
        if len(parts) > required:
            extra_fields += len(parts) - required
        if source == "generic_api":
            record = {"email": email, "code_url": parts[1]}
            if include_account_fields:
                record.update({
                    "access_token": parts[2] if len(parts) > 2 else "",
                    "totp_secret": parts[3] if len(parts) > 3 else "",
                })
        else:
            record = {
                "email": email,
                "password": parts[1],
                "client_id": parts[2],
                "refresh_token": parts[3],
            }
            if include_account_fields:
                record.update({
                    "access_token": parts[4] if len(parts) > 4 else "",
                    "totp_secret": parts[5] if len(parts) > 5 else "",
                })
        records.append(record)
    return {
        "records": records,
        "errors": errors,
        "total_lines": total_lines,
        "extra_fields": extra_fields,
    }


def create_email_pool_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("email_pool", __name__)
    logger = context.logger


    @bp.get("/api/outlook")
    def api_outlook():
        status = request.args.get("status") or None
        limit = request.args.get("limit", default=500, type=int)
        source = _pool_source_arg()
        q = str(request.args.get("q", default="") or "").strip()
        imported_date = str(request.args.get("imported_date", default="") or "").strip()
        used_date = str(request.args.get("used_date", default="") or "").strip()
        paged = str(request.args.get("paged", default="") or "").lower() in {"1", "true", "yes"}
        page_arg = request.args.get("page", default=None, type=int)
        page_size_arg = request.args.get("page_size", default=None, type=int)
        page = max(1, int(page_arg or 1))
        page_size = max(1, min(500, int(page_size_arg or limit or 50)))
        result = admin_repository.list_email_pool(
            admin_repository.PageRequest(page=page, page_size=page_size, filters={
                "source": source,
                "q": q,
                "status": status or "",
                "imported_date": imported_date,
                "used_date": used_date,
            })
        )
        if not (paged or page_arg is not None or page_size_arg is not None):
            return jsonify(result["items"])
        return jsonify(result)

    @bp.get("/api/email-derivation/summary")
    def api_email_derivation_summary():
        """子地址概况只返回展示字段，不下发母资源凭据或收件配置。"""
        source = str(request.args.get("source") or "").strip().lower()
        if source in {"", "all"}:
            source = None
        elif source not in {"icloud_hide", "outlook", "generic_api", "cloudflare_domain"}:
            return jsonify({"ok": False, "error": "不支持的邮箱来源"}), 400
        from core import email_derivation

        result = email_derivation.public_summary(source=source)
        summary_keys = {
            "enabled", "max_children", "tag_length", "total", "used", "reserved", "retired",
            "replaced", "parent_count", "eligible_parent_count", "remaining", "capacity",
        }
        parent_keys = {
            "source", "parent_id", "parent_email", "child_count", "max_children", "remaining",
            "eligible", "enabled",
        }
        result = result if isinstance(result, dict) else {}
        public = {key: value for key, value in result.items() if key in summary_keys and isinstance(value, (str, int, float, bool, type(None)))}
        public["sources"] = [value for value in result.get("sources", []) if isinstance(value, str)]
        public["parents"] = [
            {key: value for key, value in row.items() if key in parent_keys and isinstance(value, (str, int, float, bool, type(None)))}
            for row in result.get("parents", []) if isinstance(row, dict)
        ]
        return jsonify(public)

    @bp.get("/api/email-derivation/allocations")
    def api_email_derivation_allocations():
        """分页查看子地址归属，不提供跨任务释放或复用入口。"""
        source = str(request.args.get("source") or "").strip().lower()
        if source in {"", "all"}:
            source = None
        elif source not in {"icloud_hide", "outlook", "generic_api", "cloudflare_domain"}:
            return jsonify({"ok": False, "error": "不支持的邮箱来源"}), 400
        parent_arg = str(request.args.get("parent_id") or "").strip()
        try:
            parent_id = int(parent_arg) if parent_arg else None
            page = int(request.args.get("page") or 1)
            page_size = int(request.args.get("page_size") or 50)
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "母资源编号和分页参数必须是整数"}), 400
        if (parent_id is not None and parent_id < 1) or page < 1 or not 1 <= page_size <= 100:
            return jsonify({"ok": False, "error": "母资源编号和页码须大于零，每页数量须为 1–100"}), 400
        if parent_id is not None and source is None:
            return jsonify({"ok": False, "error": "按母资源筛选时须明确邮箱来源"}), 400
        from core import email_derivation

        result = email_derivation.list_allocations(source=source, parent_id=parent_id, page=page, page_size=page_size)
        result = result if isinstance(result, dict) else {}
        item_keys = {
            "id", "email", "parent_id", "parent_email", "source", "state", "registered_account_id",
            "root_task_id", "created_at", "updated_at", "used_at", "strategy",
        }
        items = [
            {key: value for key, value in row.items() if key in item_keys and isinstance(value, (str, int, float, bool, type(None)))}
            for row in result.get("items", []) if isinstance(row, dict)
        ]
        return jsonify({"items": items, "total": int(result.get("total") or 0), "page": page, "page_size": page_size})

    @bp.get("/api/outlook/secret")
    def api_outlook_secret():
        """按需读取单条邮箱资源，普通列表不会下发敏感凭证或取码地址。"""
        source = str(request.args.get("source") or "outlook").strip()
        email = str(request.args.get("email") or "").strip()
        field = str(request.args.get("field") or "copy_line").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        try:
            value = db.email_pool_secret(source, email, field)
        except LookupError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "source": source, "email": email, "field": field, "value": value})

    @bp.post("/api/outlook/secret-bulk")
    def api_outlook_secret_bulk():
        """按需读取当前选择的邮箱素材，避免列表接口批量暴露秘密。"""
        data = request.get_json(silent=True) or {}
        items = data.get("items") or []
        field = str(data.get("field") or "copy_line").strip()
        if not isinstance(items, list) or not items:
            return jsonify({"ok": False, "error": "items 必须是非空数组"}), 400
        if len(items) > 500:
            return jsonify({"ok": False, "error": "单次最多读取 500 条"}), 400
        values, skipped, seen = [], [], set()
        for raw in items:
            item = raw if isinstance(raw, dict) else {"email": raw}
            email = str(item.get("email") or "").strip()
            source = str(item.get("source") or data.get("source") or "outlook").strip()
            key = (source, email.lower())
            if not email or key in seen:
                continue
            seen.add(key)
            try:
                value = db.email_pool_secret(source, email, field)
            except (LookupError, ValueError) as exc:
                skipped.append({"source": source, "email": email, "reason": str(exc)})
                continue
            if value:
                values.append({"source": source, "email": email, "value": value})
            else:
                skipped.append({"source": source, "email": email, "reason": "值为空"})
        return jsonify({"ok": True, "field": field, "values": values, "count": len(values), "skipped": skipped})

    @bp.post("/api/outlook/import-preview")
    def api_outlook_import_preview():
        """Validate an email resource paste and report duplicates before writing."""
        data = request.get_json(silent=True) or {}
        source = str(data.get("source") or data.get("type") or "").strip().lower()
        if source not in ("outlook", "generic_api"):
            return jsonify({"ok": False, "error": "请选择 Outlook 或通用 API 邮箱来源"}), 400
        parsed = _parse_email_pool_import(data.get("text") or "", source)
        if parsed["total_lines"] > 5000:
            return jsonify({"ok": False, "error": "单次最多预览 5000 行邮箱"}), 400
        emails = [record["email"].lower() for record in parsed["records"]]
        seen: set[str] = set()
        duplicate_count = 0
        for email in emails:
            if email in seen:
                duplicate_count += 1
            seen.add(email)
        existing = admin_repository.email_pool_existing_emails(source, seen)
        unique_valid = len(seen)
        return jsonify({
            "ok": True,
            "source": source,
            "total_lines": parsed["total_lines"],
            "valid": len(parsed["records"]),
            "invalid": len(parsed["errors"]),
            "invalid_rows": parsed["errors"][:100],
            "duplicate_in_input": duplicate_count,
            "existing": len(existing),
            "new": max(0, unique_valid - len(existing)),
            "extra_fields": parsed["extra_fields"],
        })

    @bp.post("/api/outlook/import")
    def api_outlook_import():
        """
        粘贴文本导入邮箱资源。
        Outlook：email----password----clientId----refreshToken
        通用 API：email----code_url
        分隔符兼容 ---- 与 ====。
        """
        data = request.get_json(silent=True) or {}
        source = (data.get("source") or data.get("type") or "").strip()
        if source not in ("outlook", "generic_api"):
            return jsonify({"ok": False, "error": "导入时请选择具体类型：Outlook 或 通用 API"}), 400
        text = data.get("text") or ""
        # Old API clients may still send as_registered; keep the compatibility
        # path while the current UI always imports resources only.
        as_registered = bool(data.get("as_registered", False))
        parsed = _parse_email_pool_import(text, source, include_account_fields=as_registered)
        records = parsed["records"]
        if parsed["total_lines"] > 5000:
            return jsonify({"ok": False, "error": "单次最多导入 5000 行邮箱"}), 400
        if not records:
            need = "2 段：邮箱----取码地址" if source == "generic_api" else "4 段：email----password----clientId----refreshToken"
            return jsonify({"ok": False, "error": f"未解析到有效邮箱行（需 {need}，---- 或 ==== 分隔）"}), 400
        if as_registered:
            inserted, skipped = db.import_registered_email_accounts(records, source=source)
        elif source == "generic_api":
            inserted, skipped = db.import_generic_api_emails(records)
        else:
            inserted, skipped = db.import_outlook_accounts(records)
        return jsonify({
            "ok": True,
            "inserted": inserted,
            "skipped": skipped,
            "parsed": len(records),
            "as_registered": as_registered,
            "invalid": len(parsed["errors"]),
            "extra_fields": parsed["extra_fields"],
        })

    @bp.post("/api/outlook/status")
    def api_outlook_status():
        """手动改邮箱状态：body {email, status, note?, source?}。status ∈ available/used/failed/disabled。"""
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        status = (data.get("status") or "").strip()
        if not email or status not in ("available", "used", "failed", "disabled"):
            return jsonify({"ok": False, "error": "email 或 status 非法"}), 400
        source = (data.get("source") or _pool_source_arg()).strip()
        if source == "all":
            source = "outlook"
        current = _pool_row_for_source(email, source)
        if status == "available" and str((current or {}).get("status") or "").strip().lower() == "replaced":
            return jsonify({"ok": False, "error": "换绑后邮箱不能恢复为可用"}), 409
        if source == "generic_api":
            updated = db.release_generic_api_email(email, status=status, note=data.get("note"))
        elif source == "cloudflare_domain":
            updated = db.release_domain_email(email, status=status, note=data.get("note"))
        elif source == "icloud_hide":
            updated = db.release_icloud_hide_email(email, status=status, note=data.get("note"))
        else:
            updated = db.release_outlook(email, status=status, note=data.get("note"))
        if not updated:
            return jsonify({"ok": False, "error": "邮箱不存在"}), 404
        return jsonify({"ok": True, "updated": True})

    @bp.post("/api/outlook/status-bulk")
    def api_outlook_status_bulk():
        """批量修改邮箱状态。Body {items:[{email,source}], status, note?}。"""
        data = request.get_json(silent=True) or {}
        items = data.get("items") or data.get("emails") or []
        status = (data.get("status") or "").strip()
        note = data.get("note")
        default_source = (data.get("source") or _pool_source_arg()).strip()
        if status not in ("available", "used", "failed", "disabled"):
            return jsonify({"ok": False, "error": "status 非法"}), 400
        if not isinstance(items, list) or not items:
            return jsonify({"ok": False, "error": "items/emails 必须是非空数组"}), 400
        if len(items) > 5000:
            return jsonify({"ok": False, "error": "单次最多操作 5000 个邮箱"}), 400

        updated = []
        skipped = []
        seen = set()
        for raw_item in items:
            if isinstance(raw_item, dict):
                email = (str(raw_item.get("email") or "")).strip()
                item_source = (raw_item.get("source") or default_source or "outlook").strip()
            else:
                email = (str(raw_item or "")).strip()
                item_source = default_source
            if item_source == "all":
                item_source = "outlook"
            key = f"{item_source}:{email.lower()}"
            if not email:
                skipped.append({"email": raw_item, "reason": "邮箱为空"})
                continue
            if key in seen:
                continue
            seen.add(key)
            try:
                current = _pool_row_for_source(email, item_source)
                if status == "available" and str((current or {}).get("status") or "").strip().lower() == "replaced":
                    skipped.append({"email": email, "source": item_source, "reason": "换绑后邮箱不能恢复为可用"})
                    continue
                if item_source == "generic_api":
                    changed = db.release_generic_api_email(email, status=status, note=note)
                elif item_source == "cloudflare_domain":
                    changed = db.release_domain_email(email, status=status, note=note)
                elif item_source == "icloud_hide":
                    changed = db.release_icloud_hide_email(email, status=status, note=note)
                else:
                    changed = db.release_outlook(email, status=status, note=note)
                if changed:
                    updated.append({"email": email, "source": item_source, "status": status})
                else:
                    skipped.append({"email": email, "source": item_source, "reason": "邮箱不存在"})
            except Exception as exc:
                skipped.append({"email": email, "source": item_source, "reason": f"{type(exc).__name__}: {exc}"})
        return jsonify({
            "ok": True,
            "updated": updated,
            "updated_count": len(updated),
            "skipped": skipped,
        })

    @bp.post("/api/outlook/delete")
    def api_outlook_delete():
        """从邮箱池彻底删除一个邮箱：body {email}。"""
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        source = (data.get("source") or _pool_source_arg()).strip()
        if source == "all":
            source = "outlook"
        deleted = (
            db.delete_generic_api_email(email)
            if source == "generic_api"
            else db.delete_domain_email(email)
            if source == "cloudflare_domain"
            else db.delete_icloud_hide_email(email)
            if source == "icloud_hide"
            else db.delete_outlook(email)
        )
        return jsonify({"ok": True, "deleted": deleted})

    @bp.post("/api/outlook/delete-bulk")
    def api_outlook_delete_bulk():
        """从邮箱池批量彻底删除邮箱：body {emails: [...]}。"""
        data = request.get_json(silent=True) or {}
        source = _pool_source_arg()
        emails = data.get("items") or data.get("emails") or []
        if not isinstance(emails, list) or not emails:
            return jsonify({"ok": False, "error": "emails/items 必须是非空数组"}), 400
        if len(emails) > 5000:
            return jsonify({"ok": False, "error": "单次最多删除 5000 个邮箱"}), 400

        deleted: list[str] = []
        skipped: list[dict] = []
        seen: set[str] = set()
        for raw_item in emails:
            if isinstance(raw_item, dict):
                email = (str(raw_item.get("email") or "")).strip()
                item_source = (raw_item.get("source") or source or "outlook").strip()
            else:
                email = (str(raw_item or "")).strip()
                item_source = source
            if item_source == "all":
                item_source = "outlook"
            key = f"{item_source}:{email.lower()}"
            if not email:
                skipped.append({"email": raw_item, "reason": "邮箱为空"})
                continue
            if key in seen:
                continue
            seen.add(key)
            deleted_ok = (
                db.delete_generic_api_email(email)
                if item_source == "generic_api"
                else db.delete_domain_email(email)
                if item_source == "cloudflare_domain"
                else db.delete_icloud_hide_email(email)
                if item_source == "icloud_hide"
                else db.delete_outlook(email)
            )
            if deleted_ok:
                deleted.append({"email": email, "source": item_source})
            else:
                skipped.append({"email": email, "reason": "邮箱不存在"})

        return jsonify({
            "ok": True,
            "deleted": deleted,
            "deleted_count": len(deleted),
            "skipped": skipped,
        })

    @bp.get("/api/domain-pool")
    def api_domain_pool():
        status = request.args.get("status") or None
        limit = request.args.get("limit", default=500, type=int)
        return jsonify(db.list_domain_email_pool(status=status, limit=limit))

    @bp.post("/api/domain-pool/status")
    def api_domain_pool_status():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        status = (data.get("status") or "").strip()
        if not email or status not in ("available", "used", "failed"):
            return jsonify({"ok": False, "error": "email 或 status 非法"}), 400
        db.release_domain_email(email, status=status, note=data.get("note"))
        return jsonify({"ok": True})

    @bp.post("/api/domain-pool/delete")
    def api_domain_pool_delete():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        deleted = db.delete_domain_email(email)
        return jsonify({"ok": True, "deleted": deleted})

    return bp
