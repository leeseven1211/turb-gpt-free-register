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
from core.live_check_router import LiveCheckDriverError
from webui import config_editor
from webui.blueprint import LegacyEndpointBlueprint
from webui.runtime import WebUIContext
from webui.route_helpers import _account_secret_value, _compact_account_for_list, _feature_unavailable

logger = logging.getLogger(__name__)

def create_accounts_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("accounts", __name__)
    logger = context.logger
    _enqueue_account_setup = context.enqueue_account_setup
    _enqueue_account_completion = context.enqueue_account_completion
    _put_prepared_download = context.put_prepared_download
    def _is_extract_eligible(acc: dict) -> bool:
        plan = str(acc.get("current_plan_type") or acc.get("plan_type") or "").lower()
        return plan == "free" and bool(acc.get("plus_trial_eligible"))
    def _join_sub2_url(base: str, path: str) -> str:
        base = str(base or "").strip().rstrip("/")
        path = str(path or "").strip()
        if not base or not path:
            return ""
        parsed = urlparse(path)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return path
        return f"{base}/{path.lstrip('/')}"
    def _sub2_codex_session_import_url() -> str:
        from config import sub2api as sub2api_cfg
        api_base = str(getattr(sub2api_cfg, "SUB2API_API_BASE", "") or "").strip()
        if api_base:
            return _join_sub2_url(api_base, "/api/v1/admin/accounts/import/codex-session")
        # 兼容旧配置：之前 SUB2API_API_URL 是完整上传接口 URL。
        return str(getattr(sub2api_cfg, "SUB2API_API_URL", "") or "").strip()
    def _codex_oauth_auth_for_account(acc: dict) -> tuple[str, str]:
        """读取账号可导入 sub2api 的 Codex OAuth JSON。"""
        email = str(acc.get("email") or "").strip().lower()
        if (acc.get("codex_status") or "") != "success":
            raise RuntimeError("该账号尚未完成 Codex OAuth")
        match = next((
            item for item in db.list_codex_accounts(archived="all")
            if str(item.get("email") or "").strip().lower() == email
        ), None)
        if not match:
            raise RuntimeError("Codex 状态已通过，但本地未找到对应 OAuth JSON")
        return db.read_codex_credential(str(match.get("filename") or ""))
    def _upload_codex_auth_to_sub2(auth_json: dict, filename: str) -> dict:
        """把一份已解析的 Codex OAuth JSON 上传到 sub2api。"""
        from core.sub2api_client import upload_configured_codex_oauth_credential

        result = upload_configured_codex_oauth_credential(auth_json)
        result["filename"] = filename
        db.mark_codex_exported(filename)
        db.mark_codex_sub2_uploaded(filename)
        return result
    def _upload_codex_filename_to_sub2(filename: str) -> dict:
        """按 Codex 凭证文件名上传到 sub2api。"""
        import json as _json

        text, actual_filename = db.read_codex_credential(filename)
        try:
            auth_json = _json.loads(text)
        except Exception as exc:
            raise RuntimeError(f"Codex 凭证 JSON 无效: {exc}") from exc
        return _upload_codex_auth_to_sub2(auth_json, actual_filename)
    def _upload_account_codex_to_sub2(acc: dict) -> dict:
        """把账号的 Codex OAuth JSON 上传到 sub2api。"""
        import json as _json

        text, filename = _codex_oauth_auth_for_account(acc)
        try:
            auth_json = _json.loads(text)
        except Exception as exc:
            raise RuntimeError(f"Codex 凭证 JSON 无效: {exc}") from exc
        return _upload_codex_auth_to_sub2(auth_json, filename)

    @bp.get("/api/accounts")
    def api_accounts():
        limit = request.args.get("limit", default=500, type=int)
        archived = str(request.args.get("archived", default="0") or "0").lower()
        plan_filter = str(request.args.get("plan", default="") or "").lower()
        q = str(request.args.get("q", default="") or "").strip()
        column_filters = {
            key: str(request.args.get(key, default="") or "").strip().lower()
            for key in ("id", "email", "source", "token", "password", "trial", "totp", "risk", "codex", "account_status")
        }
        date_from = str(request.args.get("date_from", default="") or "").strip() or None
        date_to = str(request.args.get("date_to", default="") or "").strip() or None
        # 新分页接口：传 page/page_size 或 paged=1 时返回 {items,total,page,page_size,...}
        paged = str(request.args.get("paged", default="") or "").lower() in {"1", "true", "yes"}
        page_arg = request.args.get("page", default=None, type=int)
        page_size_arg = request.args.get("page_size", default=None, type=int)
        page = max(1, int(page_arg or 1))
        page_size = max(1, min(500, int(page_size_arg or limit or 50)))
        result = admin_repository.list_accounts(
            admin_repository.PageRequest(page=page, page_size=page_size, filters=column_filters),
            archived=archived,
            plan=plan_filter,
            q=q,
            date_from=date_from or "",
            date_to=date_to or "",
        )
        result["items"] = [_compact_account_for_list(r) for r in (result.get("items") or [])]
        result.update({"ok": True, "page": page, "page_size": page_size, "compact": True})
        # 旧调用方不传分页参数时仍返回数组，但底层也只执行 SQL 分页，不再加载全表。
        if not (paged or page_arg is not None or page_size_arg is not None):
            return jsonify(result["items"])
        return jsonify(result)

    @bp.get("/api/accounts/plan-check-status")
    def api_account_plan_check_status():
        """套餐查询轻量状态，不返回 Token、邮箱密码等敏感字段。"""
        limit = request.args.get("limit", default=5000, type=int)
        archived = str(request.args.get("archived", default="0") or "0").lower()
        plan_filter = str(request.args.get("plan", default="") or "").lower()
        q = str(request.args.get("q", default="") or "").strip()
        page_arg = request.args.get("page", default=None, type=int)
        page_size_arg = request.args.get("page_size", default=None, type=int)
        page = max(1, int(page_arg or 1))
        page_size = max(1, min(500, int(page_size_arg or limit or 50)))
        snapshot = admin_repository.list_account_statuses(
            admin_repository.PageRequest(page=page, page_size=page_size),
            archived=archived,
            plan=plan_filter,
            q=q,
        )
        snapshot.update({"offset": (page - 1) * page_size, "limit": page_size})
        snapshot["queue"] = plan_check_service.queue_settings()
        return jsonify(snapshot)

    @bp.post("/api/accounts/<int:acc_id>/setup")
    def api_account_setup(acc_id: int):
        """只补齐账号密码、套餐和 Authenticator 2FA，不执行 Codex。"""
        queued = _enqueue_account_setup(acc_id, trigger="manual_account_setup")
        if queued.get("busy"):
            return jsonify({"ok": False, **queued}), 409
        if not queued.get("accepted"):
            status = 404 if queued.get("error") == "账号不存在" else 400
            return jsonify({"ok": False, **queued}), status
        return jsonify({"ok": True, **queued}), 202

    @bp.post("/api/accounts/setup-bulk")
    def api_accounts_setup_bulk():
        """批量只补齐账号密码、套餐和 Authenticator 2FA，不执行 Codex。"""
        data = request.get_json(silent=True) or {}
        raw_ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(raw_ids) > 500:
            return jsonify({"ok": False, "error": "单次最多补齐 500 个账号"}), 400
        started, reused, skipped = [], [], []
        seen = set()
        for raw_id in raw_ids:
            try:
                acc_id = int(raw_id)
            except (TypeError, ValueError):
                skipped.append({"id": raw_id, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            result = _enqueue_account_setup(acc_id, trigger="manual_account_setup_bulk")
            if result.get("busy"):
                skipped.append({"id": acc_id, "reason": result.get("error") or "账号正在执行其它操作"})
            elif not result.get("accepted"):
                skipped.append({"id": acc_id, "reason": result.get("error") or "不能补齐账号配置"})
            else:
                started.append(result)
        if not started and not skipped:
            return jsonify({"ok": False, "error": "没有可补齐的账号"}), 409
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "reused": reused,
            "reused_count": len(reused),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }), 202

    def _account_action_result(acc_id: int, action: str, *, trigger: str):
        action = str(action or "").strip().lower()
        if action == "password":
            queued = _enqueue_account_setup(acc_id, trigger=trigger, steps={"password"}, task_type="password_setup")
        elif action == "twofa":
            queued = _enqueue_account_setup(acc_id, trigger=trigger, steps={"twofa"}, task_type="twofa_setup")
        elif action == "complete":
            queued = _enqueue_account_completion(acc_id, trigger=trigger)
        else:
            return {"accepted": False, "error": "action 只支持 password、twofa、complete"}, 400
        if queued.get("busy"):
            return {"accepted": False, **queued}, 409
        if queued.get("accepted"):
            return {"accepted": True, **queued}, 202
        # “补全”发现当前账号已经满足配置时是幂等成功，不应显示成异常。
        if queued.get("ready"):
            return {"accepted": False, "ready": True, **queued}, 200
        return {"accepted": False, **queued}, 409 if queued.get("blocked") else 400

    @bp.post("/api/accounts/<int:acc_id>/action")
    def api_account_action(acc_id: int):
        data = request.get_json(silent=True) or {}
        payload, status = _account_action_result(
            acc_id,
            data.get("action"),
            trigger=f"manual_account_{str(data.get('action') or 'action').strip().lower()}",
        )
        return jsonify({"ok": status < 400, **payload}), status

    @bp.post("/api/accounts/complete-bulk")
    def api_accounts_complete_bulk():
        data = request.get_json(silent=True) or {}
        raw_ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(raw_ids) > 500:
            return jsonify({"ok": False, "error": "单次最多补全 500 个账号"}), 400
        started, ready, skipped = [], [], []
        seen = set()
        for raw_id in raw_ids:
            try:
                acc_id = int(raw_id)
            except (TypeError, ValueError):
                skipped.append({"id": raw_id, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            payload, status = _account_action_result(
                acc_id,
                "complete",
                trigger="manual_account_completion_bulk",
            )
            if status == 202 and payload.get("accepted"):
                started.append(payload)
            elif payload.get("ready"):
                ready.append(payload)
            else:
                skipped.append({"id": acc_id, "reason": payload.get("error") or "不能补全账号"})
        if not started and not ready and not skipped:
            return jsonify({"ok": False, "error": "没有可补全的账号"}), 409
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "ready": ready,
            "ready_count": len(ready),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }), 202

    @bp.post("/api/accounts/action-bulk")
    def api_accounts_action_bulk():
        data = request.get_json(silent=True) or {}
        action = str(data.get("action") or "").strip().lower()
        raw_ids = data.get("account_ids") or data.get("ids") or []
        if action not in {"password", "twofa", "complete"}:
            return jsonify({"ok": False, "error": "action 只支持 password、twofa、complete"}), 400
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(raw_ids) > 500:
            return jsonify({"ok": False, "error": "单次最多操作 500 个账号"}), 400
        started, ready, skipped = [], [], []
        seen = set()
        for raw_id in raw_ids:
            try:
                acc_id = int(raw_id)
            except (TypeError, ValueError):
                skipped.append({"id": raw_id, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            payload, status = _account_action_result(acc_id, action, trigger=f"manual_account_{action}_bulk")
            if status == 202 and payload.get("accepted"):
                started.append(payload)
            elif payload.get("ready"):
                ready.append(payload)
            else:
                skipped.append({"id": acc_id, "reason": payload.get("error") or "操作未入队"})
        return jsonify({
            "ok": True,
            "action": action,
            "started": started,
            "started_count": len(started),
            "ready": ready,
            "ready_count": len(ready),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }), 202

    @bp.post("/api/accounts/<int:acc_id>/check-deactivation-mail")
    def api_account_check_deactivation_mail(acc_id: int):
        unavailable = _feature_unavailable("deactivation_mail")
        if unavailable:
            return unavailable
        result = deactivation_mail_service.enqueue(acc_id, trigger="manual")
        if result.get("busy"):
            return jsonify({"ok": False, **result}), 409
        if not result.get("accepted"):
            return jsonify({"ok": False, **result}), 400
        return jsonify({
            "ok": True,
            **result,
            "queue": deactivation_mail_service.queue_settings(),
        }), 202

    @bp.post("/api/accounts/check-deactivation-mail-bulk")
    def api_accounts_check_deactivation_mail_bulk():
        unavailable = _feature_unavailable("deactivation_mail")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多扫描 500 个账号"}), 400
        started, busy, skipped = [], [], []
        seen = set()
        valid_ids = []
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                continue
            if acc_id not in seen:
                seen.add(acc_id)
                valid_ids.append(acc_id)
        seen.clear()
        batch_id = account_task_store.create_batch(
            action_type="deactivation_mail",
            trigger="manual_bulk",
            total_count=len(valid_ids),
        ) if valid_ids else None
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            result = deactivation_mail_service.enqueue(acc_id, trigger="manual_bulk", batch_id=batch_id)
            item = {"id": acc_id, **result}
            if result.get("accepted"):
                started.append(item)
            elif result.get("busy"):
                busy.append(item)
            else:
                skipped.append({"id": acc_id, "reason": result.get("error") or "不支持扫描"})
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "busy": busy,
            "busy_count": len(busy),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "queue": deactivation_mail_service.queue_settings(),
            "batch_id": batch_id,
        }), 202

    @bp.get("/api/accounts/<int:acc_id>/secret")
    def api_account_secret(acc_id: int):
        """按需读取单账号敏感值，避免账号列表一次性下发完整 Token/整行。"""
        field = str(request.args.get("field") or "").strip()
        acc = db.get_account(acc_id)
        if not acc:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        try:
            value = _account_secret_value(acc, field)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "id": acc_id, "field": field, "value": value})

    @bp.get("/api/accounts/<int:acc_id>/totp-code")
    def api_account_totp_code(acc_id: int):
        """按需生成当前 TOTP 验证码，不向前端返回原始密钥。"""
        acc = db.get_account(acc_id)
        if not acc:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        secret = str(acc.get("totp_secret") or "").strip()
        if not secret:
            return jsonify({"ok": False, "error": "该账号未设置 TOTP"}), 400
        now = int(time.time())
        try:
            code = pyotp.TOTP(secret).at(now)
        except Exception:
            return jsonify({"ok": False, "error": "该账号的 TOTP 密钥无效"}), 400
        return jsonify({
            "ok": True,
            "id": acc_id,
            "code": code,
            "remaining_seconds": 30 - (now % 30),
        })

    @bp.post("/api/accounts/secret-bulk")
    def api_accounts_secret_bulk():
        """按需批量读取账号敏感值。Body {account_ids:[...], field}."""
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        field = str(data.get("field") or "").strip()
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 5000:
            return jsonify({"ok": False, "error": "单次最多读取 5000 个账号"}), 400
        values = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            try:
                value = _account_secret_value(acc, field)
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            if value:
                values.append({"id": acc_id, "email": acc.get("email"), "value": value})
            else:
                skipped.append({"id": acc_id, "email": acc.get("email"), "reason": "值为空"})
        return jsonify({"ok": True, "field": field, "values": values, "count": len(values), "skipped": skipped})

    @bp.post("/api/accounts/<int:acc_id>/archive")
    def api_account_archive(acc_id: int):
        """归档/取消归档一个账号。Body {archived: true|false}。"""
        data = request.get_json(silent=True) or {}
        archived = bool(data.get("archived", True))
        updated = db.archive_account(acc_id=acc_id, archived=archived)
        if not updated:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        return jsonify({"ok": True, "updated": True, "id": acc_id, "archived": archived})

    @bp.post("/api/accounts/archive-bulk")
    def api_accounts_archive_bulk():
        """批量归档/取消归档账号。Body {account_ids:[...], archived:true|false}。"""
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        archived = bool(data.get("archived", True))
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 5000:
            return jsonify({"ok": False, "error": "单次最多归档 5000 个账号"}), 400
        account_ids = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            account_ids.append(acc_id)
        updated, db_skipped = db.archive_accounts(account_ids=account_ids, archived=archived)
        skipped.extend(db_skipped)
        return jsonify({"ok": True, "updated": updated, "updated_count": len(updated), "archived": archived, "skipped": skipped})

    @bp.post("/api/accounts/<int:acc_id>/delete")
    def api_account_delete(acc_id: int):
        """删除一个已注册账号记录。只删除本地保存的账号/token记录，不改邮箱池状态。"""
        deleted = db.delete_account(acc_id=acc_id)
        if not deleted:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        return jsonify({"ok": True, "deleted": True})

    @bp.post("/api/accounts/delete-bulk")
    def api_accounts_delete_bulk():
        """批量删除已注册账号记录。Body {account_ids: [...]} 或 {ids: [...]}。"""
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 5000:
            return jsonify({"ok": False, "error": "单次最多删除 5000 个账号"}), 400
        account_ids = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            account_ids.append(acc_id)
        deleted, db_skipped = db.delete_accounts(account_ids=account_ids)
        skipped.extend(db_skipped)
        return jsonify({
            "ok": True,
            "deleted": deleted,
            "deleted_count": len(deleted),
            "skipped": skipped,
        })

    @bp.post("/api/accounts/<int:acc_id>/note")
    def api_account_note(acc_id: int):
        """更新单个已注册账号备注。Body {note: "..."}，空字符串表示清空。"""
        data = request.get_json(silent=True) or {}
        note = str(data.get("note") or "")
        if len(note) > 2000:
            return jsonify({"ok": False, "error": "备注最多 2000 个字符"}), 400
        updated = db.update_account_note(acc_id=acc_id, note=note)
        if not updated:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        return jsonify({"ok": True, "updated": True, "id": acc_id, "note": note})

    @bp.post("/api/accounts/note-bulk")
    def api_accounts_note_bulk():
        """批量更新已注册账号备注。Body {account_ids: [...], note: "..."}，空字符串表示清空。"""
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        note = str(data.get("note") or "")
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 5000:
            return jsonify({"ok": False, "error": "单次最多备注 5000 个账号"}), 400
        if len(note) > 2000:
            return jsonify({"ok": False, "error": "备注最多 2000 个字符"}), 400

        account_ids = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            account_ids.append(acc_id)
        updated, db_skipped = db.update_accounts_note(account_ids=account_ids, note=note)
        skipped.extend(db_skipped)
        return jsonify({
            "ok": True,
            "updated": updated,
            "updated_count": len(updated),
            "skipped": skipped,
            "skipped_count": len(skipped),
        })

    @bp.post("/api/accounts/check-live-bulk")
    def api_accounts_check_live_bulk():
        """批量查活：只在线验证现有 AT，不发送邮箱 OTP、不刷新 AT。"""
        unavailable = _feature_unavailable("live_check")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        requested_driver = data.get("driver")
        if requested_driver is not None and not isinstance(requested_driver, str):
            return jsonify({"ok": False, "error": "driver 必须是字符串"}), 400
        requested_driver = str(requested_driver or "").strip().lower() or None
        try:
            effective_driver = live_check_service.resolve_driver(requested_driver)
        except LiveCheckDriverError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多查活 500 个账号"}), 400

        account_ids: list[int] = []
        skipped: list[dict] = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            account_ids.append(acc_id)

        accounts = []
        for acc_id in account_ids:
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            email = str(acc.get("email") or "").strip()
            if not email:
                skipped.append({"id": acc_id, "reason": "邮箱为空"})
                continue
            if db.account_is_deactivated(acc):
                skipped.append({"id": acc_id, "email": email, "reason": "账号已标记为封号"})
                continue
            accounts.append(acc)

        batch_id = account_task_store.create_batch(
            action_type="live_check",
            trigger="manual_bulk",
            total_count=len(accounts),
        ) if accounts else None
        started = []
        busy_count = 0
        failed = []
        for acc in accounts:
            acc_id = int(acc.get("id") or 0)
            email = str(acc.get("email") or "")
            queued = live_check_service.enqueue_account_live_check(
                account_id=acc_id,
                email=email,
                trigger="manual_bulk",
                # 未显式传入时，由账号代理服务按注册国家申请新的平台租约，
                # 或按 ACCOUNT_ACTION_PROXY_MODE 使用静态代理池/直连。
                proxy=None,
                batch_id=batch_id,
                force_refresh=False,
                driver=effective_driver,
            )
            if queued.get("accepted"):
                started.append({"id": acc_id, "email": email, "status": "queued"})
            elif queued.get("busy"):
                busy_count += 1
                skipped.append({"id": acc_id, "email": email, "reason": queued.get("error") or "正在查活"})
            else:
                failed.append({"id": acc_id, "email": email, "error": queued.get("error") or "入队失败"})

        return jsonify({
            "ok": True,
            "message": f"已入队 {len(started)} 个查活任务",
            "started": started,
            "started_count": len(started),
            "busy_count": busy_count,
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "queue": live_check_service.queue_settings(),
            "batch_id": batch_id,
            "live_check_driver": effective_driver,
        }), 202

    @bp.post("/api/accounts/refresh-token-bulk")
    def api_accounts_refresh_token_bulk():
        """批量刷新 AT：明确通过邮箱登录重新获取并保存最新 accessToken。"""
        unavailable = _feature_unavailable("live_check")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多刷新 500 个账号"}), 400

        account_ids: list[int] = []
        skipped: list[dict] = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            account_ids.append(acc_id)

        accounts = []
        for acc_id in account_ids:
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            email = str(acc.get("email") or "").strip()
            if not email:
                skipped.append({"id": acc_id, "reason": "邮箱为空"})
                continue
            if db.account_is_deactivated(acc):
                skipped.append({"id": acc_id, "email": email, "reason": "账号已标记为封号"})
                continue
            accounts.append(acc)

        batch_id = account_task_store.create_batch(
            action_type="token_refresh",
            trigger="manual_bulk",
            total_count=len(accounts),
        ) if accounts else None
        started = []
        busy_count = 0
        failed = []
        for acc in accounts:
            acc_id = int(acc.get("id") or 0)
            email = str(acc.get("email") or "")
            queued = live_check_service.enqueue_account_live_check(
                account_id=acc_id,
                email=email,
                trigger="token_refresh_manual",
                proxy=None,
                batch_id=batch_id,
                force_refresh=True,
            )
            if queued.get("accepted"):
                started.append({"id": acc_id, "email": email, "status": "queued"})
            elif queued.get("busy"):
                busy_count += 1
                skipped.append({"id": acc_id, "email": email, "reason": queued.get("error") or "账号操作进行中"})
            else:
                failed.append({"id": acc_id, "email": email, "error": queued.get("error") or "入队失败"})

        return jsonify({
            "ok": True,
            "message": f"已入队 {len(started)} 个刷新AT任务",
            "started": started,
            "started_count": len(started),
            "busy_count": busy_count,
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "queue": live_check_service.queue_settings(),
            "batch_id": batch_id,
        }), 202

    @bp.post("/api/accounts/check-plan")
    def api_account_check_plan():
        """把单账号套餐查询加入后台队列；线路统一由账号功能代理策略决定。"""
        unavailable = _feature_unavailable("plan_check")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        acc_id = data.get("account_id") or data.get("id")
        email = (data.get("email") or "").strip()
        acc = None
        if acc_id is not None:
            try:
                acc = db.get_account(int(acc_id))
            except Exception:
                acc = None
        if acc is None and email:
            acc = db.get_account_by_email(email)
        if not acc:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        if db.account_is_deactivated(acc):
            return jsonify({"ok": False, "deactivated": True, "error": "账号已标记为封号，停止查活/刷新 AT"}), 409
        token = (acc.get("access_token") or "").strip()
        if not token:
            return jsonify({"ok": False, "error": "该账号没有 access_token"}), 400
        account_id = int(acc.get("id"))
        queued = plan_check_service.enqueue_account_plan_check(
            account_id=account_id,
            email=acc.get("email") or "",
            access_token=token,
            trigger="manual",
            proxy=None,
            timezone_offset_min=str(data.get("timezone_offset_min") or "-"),
        )
        if queued.get("busy"):
            return jsonify({"ok": False, **queued}), 409
        if not queued.get("accepted"):
            return jsonify({"ok": False, **queued}), 503
        return jsonify({"ok": True, "started": True, **queued}), 202

    @bp.post("/api/accounts/check-plan-bulk")
    def api_accounts_check_plan_bulk():
        """批量把套餐查询加入统一后台队列；每个账号独立获取线路。"""
        unavailable = _feature_unavailable("plan_check")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多查询 500 个账号"}), 400
        timezone_offset_min = str(data.get("timezone_offset_min") or "-")

        items = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except Exception:
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            if not (acc.get("access_token") or "").strip():
                skipped.append({"id": acc_id, "email": acc.get("email"), "reason": "缺少 access_token"})
                continue
            items.append(acc)

        started = []
        busy = []
        failed = []
        batch_id = account_task_store.create_batch(
            action_type="plan_check",
            trigger="manual_bulk",
            total_count=len(items),
        ) if items else None
        for acc in items:
            queued = plan_check_service.enqueue_account_plan_check(
                account_id=int(acc.get("id")),
                email=acc.get("email") or "",
                access_token=acc.get("access_token") or "",
                trigger="manual_bulk",
                proxy=None,
                timezone_offset_min=timezone_offset_min,
                batch_id=batch_id,
            )
            item = {"id": acc.get("id"), "email": acc.get("email"), **queued}
            if queued.get("accepted"):
                started.append(item)
            elif queued.get("busy"):
                busy.append(item)
            else:
                failed.append(item)
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "busy": busy,
            "busy_count": len(busy),
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "skipped_count": len(skipped),
            "batch_id": batch_id,
        }), 202

    @bp.get("/api/extract-link/cdk")
    def api_extract_link_cdk():
        """查询当前配置或传入 CDK 的剩余次数。"""
        unavailable = _feature_unavailable("extract_link")
        if unavailable:
            return unavailable
        code = (request.args.get("code") or "").strip() or None
        try:
            return jsonify({"ok": True, **extract_link_service.query_cdk(cdk=code)})
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @bp.post("/api/accounts/extract-link")
    def api_account_extract_link():
        """单账号提链。Body {account_id|id, link_type?, cdk?}。"""
        unavailable = _feature_unavailable("extract_link")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        acc_id = data.get("account_id") or data.get("id")
        try:
            acc = db.get_account(int(acc_id))
        except Exception:
            acc = None
        if not acc:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        if not _is_extract_eligible(acc):
            return jsonify({"ok": False, "error": "仅支持 free(可Plus试用) 账号提链；请先查询套餐确认资格"}), 400
        token = (acc.get("access_token") or "").strip()
        if not token:
            return jsonify({"ok": False, "error": "该账号没有 access_token"}), 400
        try:
            queued = extract_link_service.enqueue_account_extract(
                account_id=int(acc.get("id")),
                email=acc.get("email") or "",
                access_token=token,
                trigger="manual",
                link_type=data.get("link_type"),
                cdk=data.get("cdk"),
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400
        if queued.get("busy"):
            return jsonify({"ok": False, **queued}), 409
        if not queued.get("accepted"):
            return jsonify({"ok": False, **queued}), 503
        return jsonify({"ok": True, "started": True, **{k: v for k, v in queued.items() if k != "future"}}), 202

    @bp.post("/api/accounts/extract-link-bulk")
    def api_accounts_extract_link_bulk():
        """批量提链。Body {account_ids:[...], link_type?, cdk?}。"""
        unavailable = _feature_unavailable("extract_link")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多提链 500 个账号"}), 400

        started = []
        busy = []
        failed = []
        skipped = []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except Exception:
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            email = acc.get("email")
            if not _is_extract_eligible(acc):
                skipped.append({"id": acc_id, "email": email, "reason": "不是 free(可Plus试用)"})
                continue
            token = (acc.get("access_token") or "").strip()
            if not token:
                skipped.append({"id": acc_id, "email": email, "reason": "缺少 access_token"})
                continue
            try:
                queued = extract_link_service.enqueue_account_extract(
                    account_id=acc_id,
                    email=email or "",
                    access_token=token,
                    trigger="manual_bulk",
                    link_type=data.get("link_type"),
                    cdk=data.get("cdk"),
                )
            except Exception as exc:
                failed.append({"id": acc_id, "email": email, "error": f"{type(exc).__name__}: {exc}"})
                continue
            item = {"id": acc_id, "email": email, **{k: v for k, v in queued.items() if k != "future"}}
            if queued.get("accepted"):
                started.append(item)
            elif queued.get("busy"):
                busy.append(item)
            else:
                failed.append(item)
        return jsonify({
            "ok": True,
            "started": started,
            "started_count": len(started),
            "busy": busy,
            "busy_count": len(busy),
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "skipped_count": len(skipped),
        }), 202

    @bp.post("/api/accounts/<int:acc_id>/codex/upload-sub2")
    def api_account_codex_upload_sub2(acc_id: int):
        """上传单账号的 Codex OAuth 凭证到 sub2api。"""
        unavailable = _feature_unavailable("sub2_upload")
        if unavailable:
            return unavailable
        acc = db.get_account(acc_id)
        if not acc:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        try:
            result = _upload_account_codex_to_sub2(acc)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400
        return jsonify({"ok": True, "account_id": acc_id, "email": acc.get("email"), "result": result})

    @bp.post("/api/accounts/codex/upload-sub2-bulk")
    def api_accounts_codex_upload_sub2_bulk():
        """批量上传 Codex OAuth 凭证。Body {account_ids:[...]}。"""
        unavailable = _feature_unavailable("sub2_upload")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 500:
            return jsonify({"ok": False, "error": "单次最多提交 500 个账号"}), 400

        uploaded, failed, skipped = [], [], []
        seen = set()
        for raw in ids:
            try:
                acc_id = int(raw)
            except Exception:
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen:
                continue
            seen.add(acc_id)
            acc = db.get_account(acc_id)
            if not acc:
                skipped.append({"id": acc_id, "reason": "账号不存在"})
                continue
            email = acc.get("email")
            if (acc.get("codex_status") or "") != "success":
                skipped.append({"id": acc_id, "email": email, "reason": "尚未完成 Codex OAuth"})
                continue
            try:
                result = _upload_account_codex_to_sub2(acc)
                uploaded.append({
                    "id": acc_id,
                    "email": email,
                    "url": result.get("url"),
                    "status_code": result.get("status_code"),
                })
            except Exception as exc:
                failed.append({"id": acc_id, "email": email, "error": f"{type(exc).__name__}: {exc}"})
        return jsonify({
            "ok": True,
            "uploaded": uploaded,
            "uploaded_count": len(uploaded),
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "skipped_count": len(skipped),
        })

    @bp.post("/api/codex/upload-sub2-bulk")
    def api_codex_upload_sub2_bulk():
        """从 Codex 管理页批量上传 OAuth 凭证。Body {filenames:[...]}。"""
        unavailable = _feature_unavailable("sub2_upload")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 500:
            return jsonify({"ok": False, "error": "单次最多提交 500 个凭证"}), 400

        uploaded, failed, skipped = [], [], []
        seen = set()
        for raw in filenames:
            filename = str(raw or "").strip() if isinstance(raw, str) else ""
            if not filename:
                skipped.append({"filename": str(raw), "reason": "文件名非法"})
                continue
            if filename in seen:
                continue
            seen.add(filename)
            try:
                result = _upload_codex_filename_to_sub2(filename)
                uploaded.append({
                    "filename": result.get("filename") or filename,
                    "url": result.get("url"),
                    "status_code": result.get("status_code"),
                })
            except Exception as exc:
                failed.append({"filename": filename, "error": f"{type(exc).__name__}: {exc}"})
        return jsonify({
            "ok": True,
            "uploaded": uploaded,
            "uploaded_count": len(uploaded),
            "failed": failed,
            "failed_count": len(failed),
            "skipped": skipped,
            "skipped_count": len(skipped),
        })

    @bp.post("/api/accounts/download-cpa-bulk")
    def api_accounts_download_cpa_bulk():
        """
        从账号列表选中的账号直接到 CPA auth-files 下载 Codex CPA JSON，并打包为 ZIP。
        Body: {"account_ids": [1,2,...]} 或 {"ids": [...]}
        """
        unavailable = _feature_unavailable("cpa_download")
        if unavailable:
            return unavailable
        import io
        import json as _json
        import zipfile
        from datetime import datetime as _dt
        from core.codex_oauth import download_cpa_codex_auth_text, list_cpa_codex_auth_files

        data = request.get_json(silent=True) or {}
        if not data and request.form:
            ids_text = (request.form.get("account_ids") or request.form.get("ids") or "").strip()
            try:
                ids = _json.loads(ids_text) if ids_text else []
            except Exception:
                ids = [x.strip() for x in ids_text.split(",") if x.strip()]
        else:
            ids = data.get("account_ids") or data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return jsonify({"ok": False, "error": "account_ids 必须是非空数组"}), 400
        if len(ids) > 1000:
            return jsonify({"ok": False, "error": "单次最多下载 1000 个账号"}), 400

        try:
            cpa_files = list_cpa_codex_auth_files()
        except Exception as exc:
            return jsonify({"ok": False, "error": f"读取 CPA auth-files 失败: {type(exc).__name__}: {exc}"}), 502

        def _match_cpa_file(email: str, local_filename: str = "") -> dict | None:
            """在已缓存的 CPA 文件列表中匹配，避免每个账号都重新请求 auth-files。"""
            email_l = str(email or "").strip().lower()
            local_name_l = str(local_filename or "").strip().lower()
            local_stem_l = local_name_l[:-5] if local_name_l.endswith(".json") else local_name_l

            def score(item: dict) -> int:
                name_l = str(item.get("name") or "").lower()
                item_email_l = str(item.get("email") or "").lower()
                s = 0
                if local_name_l and name_l == local_name_l:
                    s = max(s, 100)
                if local_stem_l and name_l.startswith(local_stem_l):
                    s = max(s, 80)
                if email_l and item_email_l == email_l:
                    s = max(s, 70)
                if email_l and email_l in name_l:
                    s = max(s, 60)
                if local_stem_l.endswith("-cpa-callback"):
                    base = local_stem_l[:-len("-cpa-callback")]
                    if base and name_l.startswith(base + "-"):
                        s = max(s, 75)
                return s

            ranked = sorted(((score(item), item) for item in cpa_files), key=lambda x: x[0], reverse=True)
            return ranked[0][1] if ranked and ranked[0][0] > 0 else None

        # 建立 email -> 本地 codex 文件名索引；有本地文件名时传给 CPA 匹配逻辑可提升命中率。
        local_by_email: dict[str, str] = {}
        try:
            for item in db.list_codex_accounts():
                email_key = str(item.get("email") or "").strip().lower()
                fname = str(item.get("filename") or "").strip()
                if email_key and fname and email_key not in local_by_email:
                    local_by_email[email_key] = fname
        except Exception:
            local_by_email = {}

        errors = []
        added = []
        used_names = set()
        seen_ids = set()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for raw_id in ids:
                try:
                    acc_id = int(raw_id)
                except (TypeError, ValueError):
                    errors.append({"id": raw_id, "error": "ID 非法"})
                    continue
                if acc_id in seen_ids:
                    continue
                seen_ids.add(acc_id)

                acc = db.get_account(acc_id)
                if not acc:
                    errors.append({"id": acc_id, "error": "账号不存在"})
                    continue
                email = str(acc.get("email") or "").strip()
                if not email:
                    errors.append({"id": acc_id, "error": "账号缺少 email"})
                    continue

                local_filename = local_by_email.get(email.lower(), "")
                try:
                    meta = _match_cpa_file(email=email, local_filename=local_filename)
                    cpa_name_hint = str((meta or {}).get("name") or "").strip()
                    if not cpa_name_hint:
                        raise RuntimeError(f"[Codex][CPA] 未在 CPA auth-files 中找到匹配的 Codex 凭证: {email}")
                    cpa_text, cpa_name, meta = download_cpa_codex_auth_text(
                        cpa_name=cpa_name_hint,
                    )
                    arcname = cpa_name
                    if arcname in used_names:
                        stem, dot, ext = arcname.rpartition(".")
                        arcname = f"{stem or arcname}-{len(used_names)+1}{dot}{ext}" if dot else f"{arcname}-{len(used_names)+1}"
                    used_names.add(arcname)
                    zf.writestr(arcname, cpa_text)
                    added.append({
                        "id": acc_id,
                        "email": email,
                        "local_filename": local_filename,
                        "cpa_filename": cpa_name,
                        "cpa_meta": meta,
                    })
                    if local_filename:
                        try:
                            db.mark_codex_exported(local_filename)
                        except Exception:
                            pass
                except Exception as exc:
                    errors.append({"id": acc_id, "email": email, "error": f"{type(exc).__name__}: {exc}"})

            manifest = {
                "exported_at": _dt.now().isoformat(timespec="seconds"),
                "source": "accounts-cpa",
                "count": len(added),
                "files": added,
                "errors": errors,
            }
            zf.writestr("manifest.json", _json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

        if not added:
            return jsonify({"ok": False, "error": "没有成功从 CPA 下载任何凭证", "errors": errors}), 502
        now = _dt.now()
        dl_name = f"accounts-cpa-bulk-{now.strftime('%Y%m%d-%H%M%S')}.zip"
        buf.seek(0)
        zip_bytes = buf.getvalue()
        if isinstance(data, dict) and data.get("prepare"):
            download_id = _put_prepared_download(zip_bytes, dl_name, "application/zip")
            return jsonify({
                "ok": True,
                "prepared": True,
                "download_id": download_id,
                "download_url": f"/api/downloads/{download_id}",
                "filename": dl_name,
                "added_count": len(added),
                "error_count": len(errors),
            })
        return Response(
            zip_bytes,
            mimetype="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{dl_name}"',
                "Content-Length": str(len(zip_bytes)),
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
                "X-Download-Options": "noopen",
            },
        )

    @bp.get("/api/accounts/live-check-log")
    def api_account_live_check_log():
        """读取某邮箱最近一次查活日志。?email=xxx"""
        from core import account_liveness
        email = (request.args.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        p = account_liveness.log_path(email)
        if not p.exists():
            return jsonify({"ok": True, "log": "", "running": live_check_service.is_checking(email)})
        max_bytes = 80_000
        size = p.stat().st_size
        with p.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            content = f.read().decode("utf-8", errors="replace")
        return jsonify({
            "ok": True,
            "log": content,
            "running": live_check_service.is_checking(email),
        })

    return bp
