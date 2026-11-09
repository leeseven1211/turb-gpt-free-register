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

from core import account_task_store
from core.storage import admin_repository
from core.codex import operation_service as codex_operation_service, retry_service as codex_retry_service, token_refresh_service as codex_token_refresh_service
from core import db
from core.accounts.deactivation import mail_scan as deactivation_mail_service
from core.extract_link import service as extract_link_service
from core.accounts.liveness import service as live_check_service
from core import operation_task_store
from core.accounts.plans import service as plan_check_service
from core.registration import service as svc
from core.operations.errors import classify_task_error
from core.storage.email import local_imports as local_email_imports
from core.email.resource_lifetime import normalize_expiry
from config import codex as codex_config
from webui import config_editor
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext
from webui.route_helpers import _pool_source_arg

logger = logging.getLogger(__name__)


def _derivation_request_error(message: str):
    return jsonify({"ok": False, "error": message, "reason_code": "email_derivation_invalid_request"}), 400


def _derivation_managed_by_butler():
    return jsonify({
        "ok": False,
        "error": "子邮箱生成、策略和库存状态已由 Email Butler 管理，请到 Email Butler 操作；Turb 仅保留历史记录及邮箱导入、领取和使用。",
        "reason_code": "email_derivation_managed_by_butler",
    }), 410


def _pool_row_for_source(email: str, source: str) -> dict | None:
    source = str(source or "").strip().lower()
    if source == "generic_api":
        return db.get_generic_api_email_by_email(email)
    if source == "cloudflare_domain":
        return db.get_domain_email_by_email(email)
    if source == "icloud_hide":
        return db.get_icloud_hide_email_by_email(email)
    if source == "email_butler":
        return local_email_imports.get_butler_email(email)
    return db.get_outlook_by_email(email)


_EMAIL_SYNC_SOURCES = frozenset({'outlook', 'generic_api', 'cloudflare_domain', 'icloud_hide', 'email_butler'})
_EMAIL_SYNC_STATES = frozenset({'pending', 'sending', 'delivered', 'blocked', 'not_required'})


def _public_email_sync(value: dict | None) -> dict:
    """同步回执只公开展示字段，连接、凭据和原始请求始终留在服务端。"""
    value = value if isinstance(value, dict) else {}
    state = value.get('state')
    return {
        'state': state if state in _EMAIL_SYNC_STATES else 'not_required',
        'kind': value.get('kind') if value.get('kind') in {'import', 'return'} else '',
        'error_code': str(value.get('error_code') or '')[:120],
        'permanent': value.get('permanent') is True,
    }


def _email_sync_status(source: str, email: str) -> dict:
    from core.email.email_butler import service_facts

    return _public_email_sync(service_facts.sync_status(source, email))


def _pool_import_pending(row: dict | None) -> bool:
    return bool(row and (row.get('status') == 'pending_sync'
        or row.get('service_sync_state') in {'pending', 'sending', 'blocked'}))


def _parse_email_pool_import(text: str, source: str, *, include_account_fields: bool = False, expires_at=None) -> dict:
    """Parse only the fields that belong to an email resource.

    ``include_account_fields`` is retained for old API clients that still send
    ``as_registered``. The new email UI never enables that path.
    """
    source = str(source or "").strip().lower()
    required = 1 if source == "email_butler" else 2 if source == "generic_api" else 4
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
        expected = 3 if source == 'generic_api' and not include_account_fields else required
        if len(parts) > expected:
            extra_fields += len(parts) - expected
        if source == "email_butler":
            try:
                record = {"email": local_email_imports.butler_forward_address(email)}
            except ValueError as exc:
                errors.append({"line": line_no, "reason": str(exc)})
                continue
        elif source == "generic_api":
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
        lifetime = (parts[2] if source == 'generic_api' and not include_account_fields and len(parts) > 2 else '')
        try:
            record.update(normalize_expiry(lifetime or expires_at, reject_expired=True))
        except ValueError as exc:
            errors.append({'line': line_no, 'reason': str(exc), 'reason_code': str(exc).split(':', 1)[0]})
            continue
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

    @bp.get('/api/email-service-sync')
    def api_email_service_sync():
        """读取导入和退号同步进度；已删除邮箱仍可查看原同步结果。"""
        from core.email.email_butler import service_facts

        limit = request.args.get('limit', default=100, type=int)
        if limit is None or not 1 <= limit <= 200:
            return jsonify({'ok': False, 'error': '数量须为 1 至 200', 'error_code': 'invalid_sync_limit'}), 400
        counts = service_facts.summary()
        items = []
        for row in service_facts.list_sync(limit=limit):
            if not isinstance(row, dict):
                continue
            items.append({**_public_email_sync(row), 'source': str(row.get('source') or ''),
                'email': str(row.get('email') or ''), 'updated_at': str(row.get('updated_at') or '')})
        return jsonify({'ok': True, 'summary': {key: int(counts.get(key) or 0)
            for key in ('pending', 'sending', 'delivered', 'blocked')}, 'items': items})

    @bp.post('/api/email-service-sync/retry')
    def api_email_service_sync_retry():
        """只重试原持久同步意图，不重新申请或导入邮箱。"""
        from core.email.email_butler import service_facts

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({'ok': False, 'error': '请求格式无效', 'error_code': 'invalid_sync_request'}), 400
        source, email, kind = (str(data.get(key) or '').strip() for key in ('source', 'email', 'kind'))
        if source not in _EMAIL_SYNC_SOURCES or '@' not in email or kind not in {'import', 'return'}:
            return jsonify({'ok': False, 'error': '邮箱来源、地址或同步类型无效', 'error_code': 'invalid_sync_request'}), 400
        if not service_facts.retry(source, email, kind):
            return jsonify({'ok': False, 'error': '没有可重试的原同步记录', 'error_code': 'sync_event_not_retryable'}), 409
        return jsonify({'ok': True, 'sync': _email_sync_status(source, email)}), 202


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
        from core.email import derivation as email_derivation

        result = email_derivation.public_summary(source=source)
        summary_keys = {
            "enabled", "max_children", "tag_length", "total", "used", "reserved", "retired",
            "replaced", "available", "disabled", "parent_count", "eligible_parent_count", "remaining", "capacity",
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
        """分页筛选子地址库存及历史归属。"""
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
        filters = {key: str(request.args.get(key) or "").strip() for key in
                   ("q", "parent_q", "state", "related_q", "created_from", "created_to")}
        if any(len(value) > 512 for value in filters.values()):
            return _derivation_request_error("筛选内容不能超过 512 个字符")
        if filters["state"] and filters["state"] not in {"available", "disabled", "reserved", "used", "replaced", "retired"}:
            return _derivation_request_error("不支持的子地址状态")
        for key in ("created_from", "created_to"):
            if filters[key]:
                try:
                    parsed = datetime.strptime(filters[key], "%Y-%m-%d")
                    if parsed.strftime("%Y-%m-%d") != filters[key]:
                        raise ValueError
                except ValueError:
                    return _derivation_request_error("生成日期须为有效的 YYYY-MM-DD 日期")
        if filters["created_from"] and filters["created_to"] and filters["created_from"] > filters["created_to"]:
            return _derivation_request_error("生成日期的开始时间不能晚于结束时间")
        from core.email import derivation as email_derivation

        result = email_derivation.list_allocations(source=source, parent_id=parent_id, page=page, page_size=page_size,
                                                  **{key: value for key, value in filters.items() if value})
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

    @bp.post("/api/email-derivation/generate")
    def api_email_derivation_generate():
        """旧调用方收到明确迁移提示，不能再修改本地库存。"""
        return _derivation_managed_by_butler()

    @bp.post("/api/email-derivation/status-bulk")
    def api_email_derivation_status_bulk():
        return _derivation_managed_by_butler()

    @bp.get("/api/outlook/secret")
    def api_outlook_secret():
        """按需读取单条邮箱资源，普通列表不会下发敏感凭证或取码地址。"""
        source = str(request.args.get("source") or "outlook").strip()
        email = str(request.args.get("email") or "").strip()
        field = str(request.args.get("field") or "copy_line").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        try:
            value = (local_email_imports.butler_email_secret(email, field) if source == "email_butler"
                     else db.email_pool_secret(source, email, field))
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
                value = (local_email_imports.butler_email_secret(email, field) if source == "email_butler"
                         else db.email_pool_secret(source, email, field))
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
        if source not in ("outlook", "generic_api", "email_butler"):
            return jsonify({"ok": False, "error": "请选择 Outlook、通用 API 或 Butler 邮箱来源"}), 400
        parsed = _parse_email_pool_import(data.get("text") or "", source, expires_at=data.get('expires_at'))
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

    def _butler_import_action(action, *args, body=False, batch=False, status=200):
        """Keep import failures safe; remote credentials never reach the browser."""
        from core.email.email_butler import manual_import as service, v2

        messages = {
            'invalid_request_id': '导入请求编号无效，请重新预览。',
            'invalid_preview_token': '预览编号无效，请重新预览。',
            'invalid_batch_id': '导入批次编号无效。',
            'invalid_import_count': '导入数量须为大于 0 的整数。',
            'unsupported_import_type': '请选择当前支持的邮箱类型。',
            'invalid_import_domain': '请检查域名筛选。',
            'invalid_import_group': '请检查分组筛选。',
            'butler_configuration_required': '请先配置 Butler /v2 连接地址和 API Key。',
            'butler_filter_unsupported': '新版 Butler 按来源和数量分配邮箱，请清除旧筛选后重新预览。',
            'butler_availability_invalid': 'Butler 可用数量响应无效，请稍后重新预览。',
            'handoff_contract_unsupported': '当前 Butler 连接不支持所需的领取和收码方式，请检查连接配置。',
            'import_preview_not_found': '预览不存在，请重新预览。',
            'import_preview_expired': '预览已过期，请重新预览。',
            'import_preview_empty': '本次预览没有可导入的邮箱。',
            'import_snapshot_conflict': '连接配置已变化，请重新预览。',
            'import_request_conflict': '原请求已关联其他预览，请保留原编号恢复。',
            'import_batch_not_found': '找不到原导入批次，请保留编号核对。',
        }

        if body:
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"ok": False, "error": "请提交 JSON 对象", "code": "invalid_body", "error_code": "invalid_body"}), 400
            args = (data,)
        try:
            result = getattr(service, action)(*args)
            return jsonify({"ok": True, "batch": result} if batch else result), status
        except v2.ButlerV2Error as exc:
            remote_messages = {
                'permission_denied': '当前 Butler Key 缺少所需权限，请检查租约读取和长期租用授权。',
                'service_not_allowed': '当前 Butler Key 无权使用 OpenAI 服务。',
                'invalid_api_key': 'Butler Key 无效或已停用，请检查连接配置。',
                'no_inventory': 'Butler 当前没有符合条件的可租邮箱。',
                'service_unavailable': 'Butler 已暂停此服务的新租用。',
                'api_version_retired': '当前 Butler 接口版本已经退役，请核对 /v2 地址。',
            }
            upstream = getattr(exc, 'status_code', None)
            response_status = upstream if isinstance(upstream, int) and 400 <= upstream < 600 else 502
            if response_status == 401:
                # 上游 Key 失效不等于当前 Turb 登录会话失效。
                response_status = 502
            return jsonify({'ok': False, 'error': remote_messages.get(exc.error_code,
                'Butler 请求未确认，请保留原请求后重试。'), 'code': exc.error_code,
                'error_code': exc.error_code, 'retryable': exc.retryable,
                'request_unknown': exc.request_unknown, 'upstream_status': upstream}), response_status
        except service.RemoteError as exc:
            return jsonify({"ok": False, "error": "暂时无法读取 Butler，请稍后重试。", "code": "butler_unavailable", "error_code": "butler_unavailable"}), 502
        except LookupError as exc:
            code = str(exc).partition(':')[0]
            code = code if code in messages else 'import_not_found'
            return jsonify({"ok": False, "error": messages.get(code, '找不到原导入记录，请保留编号核对。'), "code": code, "error_code": code}), 404
        except ValueError as exc:
            code = str(exc).partition(':')[0]
            code = code if code in messages else 'import_invalid_request'
            conflict = code in {"import_request_conflict", "import_snapshot_conflict"}
            return jsonify({"ok": False, "error": messages.get(code, '导入条件无效，请检查选项或重新预览。'), "code": code, "error_code": code}), 409 if conflict else 400
        except Exception as exc:
            logger.error("Butler manual import action %s failed (%s)", action, type(exc).__name__)
            return jsonify({"ok": False, "error": "导入操作暂未确认，请保留当前批次后重试", "code": "import_internal_error", "error_code": "import_internal_error"}), 500

    @bp.get("/api/email-butler/import-options")
    def api_butler_import_options():
        return _butler_import_action('options')

    @bp.post("/api/email-butler/import-preview")
    def api_butler_import_preview():
        return _butler_import_action('preview', body=True)

    @bp.post("/api/email-butler/imports")
    def api_butler_import_create():
        return _butler_import_action('create', body=True, batch=True, status=202)

    @bp.get("/api/email-butler/imports/<batch_id>")
    def api_butler_import_status(batch_id):
        return _butler_import_action('get', batch_id, batch=True)

    @bp.post("/api/email-butler/imports/<batch_id>/retry")
    def api_butler_import_retry(batch_id):
        return _butler_import_action('retry', batch_id, batch=True, status=202)

    @bp.post("/api/email-butler/imports/<batch_id>/cancel")
    def api_butler_import_cancel(batch_id):
        return _butler_import_action('cancel', batch_id, batch=True)

    @bp.post("/api/outlook/import")
    def api_outlook_import():
        """
        粘贴文本导入邮箱资源。
        Outlook：email----password----clientId----refreshToken
        通用 API：email----code_url[----expires_at（带时区 ISO8601）]
        分隔符兼容 ---- 与 ====。
        """
        data = request.get_json(silent=True) or {}
        source = (data.get("source") or data.get("type") or "").strip().lower()
        if source not in ("outlook", "generic_api", "email_butler"):
            return jsonify({"ok": False, "error": "导入时请选择具体类型：Outlook、通用 API 或 Butler 邮箱"}), 400
        text = data.get("text") or ""
        # Old API clients may still send as_registered; keep the compatibility
        # path while the current UI always imports resources only.
        as_registered = bool(data.get("as_registered", False))
        if as_registered and data.get('expires_at'):
            return jsonify({'ok': False, 'error': '邮箱有效期仅用于资源导入；已注册账号兼容导入不支持批次邮箱有效期'}), 400
        if source == "email_butler" and as_registered:
            return jsonify({"ok": False, "error": "Butler 邮箱仅导入本地资源，不导入为已注册账号"}), 400
        parsed = _parse_email_pool_import(text, source, include_account_fields=as_registered, expires_at=data.get('expires_at'))
        records = parsed["records"]
        if parsed["total_lines"] > 5000:
            return jsonify({"ok": False, "error": "单次最多导入 5000 行邮箱"}), 400
        if not records:
            need = ("每行一个已租用的完整邮箱地址" if source == "email_butler" else
                    "2 段：邮箱----取码地址" if source == "generic_api" else "4 段：email----password----clientId----refreshToken")
            error = parsed['errors'][0]['reason'] if parsed['errors'] else f"未解析到有效邮箱行（需 {need}，---- 或 ==== 分隔）"
            return jsonify({"ok": False, "error": error, 'invalid_rows': parsed['errors'][:100]}), 400
        try:
            if as_registered:
                inserted, skipped = db.import_registered_email_accounts(records, source=source)
            elif source == "email_butler":
                inserted, skipped = local_email_imports.import_resources(records, source=source)
            elif source == "generic_api":
                inserted, skipped = db.import_generic_api_emails(records)
            else:
                inserted, skipped = db.import_outlook_accounts(records)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            from core.email.email_butler.v2 import ButlerV2Error
            if not isinstance(exc, ButlerV2Error):
                raise
            return jsonify({'ok': False, 'error': '原邮箱租约未确认，请保留完整地址后重试。',
                'code': exc.error_code, 'error_code': exc.error_code,
                'upstream_status': exc.status_code, 'retryable': exc.retryable}), 502
        from core.email.email_butler import service_facts
        return jsonify({
            "ok": True,
            "inserted": inserted,
            "skipped": skipped,
            "parsed": len(records),
            'accepted_count': inserted,
            'pending_sync_count': service_facts.pending_count(source, [item['email'] for item in records]),
            "as_registered": as_registered,
            "invalid": len(parsed["errors"]),
            "invalid_rows": parsed['errors'][:100],
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
        if _pool_import_pending(current):
            return jsonify({'ok': False, 'error': '邮箱导入尚未完成，请稍后再试',
                'error_code': 'service_fact_sync_pending'}), 409
        if status == "available" and str((current or {}).get("status") or "").strip().lower() == "replaced":
            return jsonify({"ok": False, "error": "换绑后邮箱不能恢复为可用"}), 409
        if source == "email_butler":
            try:
                updated = local_email_imports.set_butler_status(email, status=status, note=data.get("note"))
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 409
        elif source == "generic_api":
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
                if _pool_import_pending(current):
                    skipped.append({'email': email, 'source': item_source,
                        'reason': '邮箱导入尚未完成，请稍后再试', 'error_code': 'service_fact_sync_pending'})
                    continue
                if status == "available" and str((current or {}).get("status") or "").strip().lower() == "replaced":
                    skipped.append({"email": email, "source": item_source, "reason": "换绑后邮箱不能恢复为可用"})
                    continue
                if item_source == "email_butler":
                    changed = local_email_imports.set_butler_status(email, status=status, note=note)
                elif item_source == "generic_api":
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
        """从本地邮箱池移除未确认注册成功的邮箱：body {email}。"""
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        source = (data.get("source") or _pool_source_arg()).strip()
        if source == "all":
            source = "outlook"
        if local_email_imports.pool_mutation_protected(_pool_row_for_source(email, source)):
            return jsonify({"ok": True, "deleted": False, "local_deleted": False,
                "reason": "邮箱已确认注册成功，不能删除"})
        deleted = (
            local_email_imports.delete_butler_email(email)
            if source == "email_butler"
            else db.delete_generic_api_email(email)
            if source == "generic_api"
            else db.delete_domain_email(email)
            if source == "cloudflare_domain"
            else db.delete_icloud_hide_email(email)
            if source == "icloud_hide"
            else db.delete_outlook(email)
        )
        return jsonify({"ok": True, "deleted": deleted, "local_deleted": deleted,
            "sync": _email_sync_status(source, email) if deleted else None,
            "reason": "" if deleted else "邮箱不存在或当前状态不允许删除"})

    @bp.post("/api/outlook/delete-bulk")
    def api_outlook_delete_bulk():
        """批量移除未确认注册成功的本地邮箱：body {emails: [...]}。"""
        data = request.get_json(silent=True) or {}
        source = _pool_source_arg()
        emails = data.get("items") or data.get("emails") or []
        if not isinstance(emails, list) or not emails:
            return jsonify({"ok": False, "error": "emails/items 必须是非空数组"}), 400
        if len(emails) > 5000:
            return jsonify({"ok": False, "error": "单次最多删除 5000 个邮箱"}), 400

        deleted: list[dict] = []
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
            if local_email_imports.pool_mutation_protected(_pool_row_for_source(email, item_source)):
                skipped.append({"email": email, "source": item_source, "reason": "邮箱已确认注册成功，不能删除"})
                continue
            deleted_ok = (
                local_email_imports.delete_butler_email(email)
                if item_source == "email_butler"
                else db.delete_generic_api_email(email)
                if item_source == "generic_api"
                else db.delete_domain_email(email)
                if item_source == "cloudflare_domain"
                else db.delete_icloud_hide_email(email)
                if item_source == "icloud_hide"
                else db.delete_outlook(email)
            )
            if deleted_ok:
                deleted.append({"email": email, "source": item_source, "local_deleted": True,
                    "sync": _email_sync_status(item_source, email)})
            else:
                skipped.append({"email": email, "reason": "邮箱不存在"})

        return jsonify({
            "ok": True,
            "deleted": deleted,
            "deleted_count": len(deleted),
            "pending_sync_count": sum(item['sync']['state'] in {'pending', 'sending'} for item in deleted),
            "blocked_sync_count": sum(item['sync']['state'] == 'blocked' for item in deleted),
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
