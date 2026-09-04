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
from webui.route_helpers import _feature_unavailable

logger = logging.getLogger(__name__)

def create_codex_blueprint(context: WebUIContext):
    bp = LegacyEndpointBlueprint("codex", __name__)
    logger = context.logger
    _enqueue_codex_retry = context.enqueue_codex_retry

    @bp.get("/api/codex")
    def api_codex_list():
        archived_mode = str(request.args.get("archived", default="0") or "0").lower()
        date_from = str(request.args.get("date_from", default="") or "").strip()
        date_to = str(request.args.get("date_to", default="") or "").strip()
        q = str(request.args.get("q", default="") or "").strip()
        plan_filter = str(request.args.get("plan", default="") or "").strip().lower()
        status_filter = str(request.args.get("status", default="") or "").strip().lower()
        oauth_filter = str(request.args.get("oauth_status", default="") or "").strip().lower()
        account_filter = str(request.args.get("account_id", default="") or "").strip()
        expired_date = str(request.args.get("expired_date", default="") or "").strip()
        limit = request.args.get("limit", default=500, type=int)
        paged = str(request.args.get("paged", default="") or "").lower() in {"1", "true", "yes"}
        page_arg = request.args.get("page", default=None, type=int)
        page_size_arg = request.args.get("page_size", default=None, type=int)
        page = max(1, int(page_arg or 1))
        page_size = max(1, min(500, int(page_size_arg or limit or 50)))
        result = admin_repository.list_codex(
            admin_repository.PageRequest(page=page, page_size=page_size, filters={
                "archived": archived_mode,
                "date_from": date_from,
                "date_to": date_to,
                "q": q,
                "plan": plan_filter,
                "status": status_filter,
                "oauth_status": oauth_filter,
                "account_id": account_filter,
                "expired_date": expired_date,
            })
        )
        if not (paged or page_arg is not None or page_size_arg is not None):
            result["accounts"] = result.get("accounts", [])[:limit]
        return jsonify(result)

    @bp.post("/api/codex/refresh-token-bulk")
    def api_codex_refresh_token_bulk():
        """手动刷新选中的 Codex OAuth token，不触发邮箱/短信授权。"""
        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 500:
            return jsonify({"ok": False, "error": "单次最多刷新 500 个凭证"}), 400

        unique = []
        seen = set()
        for raw in filenames:
            filename = str(raw or "").strip()
            if filename and filename not in seen:
                seen.add(filename)
                unique.append(filename)
        batch_id = account_task_store.create_batch(
            action_type="codex_token_refresh",
            trigger="manual_bulk",
            total_count=len(unique),
        )
        started, skipped = [], []
        for filename in unique:
            result = codex_token_refresh_service.enqueue_refresh(
                filename,
                trigger="manual_bulk",
                batch_id=batch_id,
            )
            if result.get("accepted"):
                started.append(result)
            else:
                skipped.append({"filename": filename, "reason": result.get("error") or "无法刷新"})
        if not started:
            return jsonify({"ok": False, "error": "没有可刷新的凭证", "skipped": skipped}), 409
        return jsonify({
            "ok": True,
            "message": f"已创建 {len(started)} 个 OAuth Token 刷新任务",
            "started": started,
            "started_count": len(started),
            "skipped": skipped,
            "batch_id": batch_id,
        }), 202

    @bp.post("/api/codex/archive")
    def api_codex_archive():
        """归档/取消归档一条 Codex 授权凭证。Body {filename, archived}。"""
        data = request.get_json(silent=True) or {}
        filename = str(data.get("filename") or "").strip()
        archived = bool(data.get("archived", True))
        if not filename:
            return jsonify({"ok": False, "error": "filename 必填"}), 400
        try:
            rec = db.archive_codex(filename=filename, archived=archived)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if rec is None:
            return jsonify({"ok": False, "error": f"凭证不存在: {filename}"}), 404
        return jsonify({"ok": True, "filename": filename, "archived": archived, "record": rec})

    @bp.post("/api/codex/archive-bulk")
    def api_codex_archive_bulk():
        """批量归档/取消归档 Codex 授权凭证。Body {filenames:[...], archived}。"""
        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        archived = bool(data.get("archived", True))
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 1000:
            return jsonify({"ok": False, "error": "单次最多 1000 个"}), 400
        updated = []
        skipped = []
        seen = set()
        for fname in filenames:
            if not isinstance(fname, str) or not fname:
                skipped.append({"filename": str(fname), "reason": "非法文件名"})
                continue
            if fname in seen:
                continue
            seen.add(fname)
            try:
                rec = db.archive_codex(filename=fname, archived=archived)
            except ValueError as exc:
                skipped.append({"filename": fname, "reason": str(exc)})
                continue
            if rec is None:
                skipped.append({"filename": fname, "reason": "凭证不存在"})
            else:
                updated.append({"filename": fname, "archived": archived})
        return jsonify({"ok": True, "updated": updated, "updated_count": len(updated), "archived": archived, "skipped": skipped})

    @bp.get("/api/codex/download/<path:filename>")
    def api_codex_download(filename: str):
        """
        下载一个 CPA 兼容的 codex-*.json 文件，下载即标记为已导出（计数+1）。
        前端通过浏览器原生下载触发（a 标签 / window.location）。
        """
        try:
            content, fname = db.read_codex_credential(filename)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        db.mark_codex_exported(fname)
        return Response(
            content,
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    @bp.get("/api/codex/download-from-cpa/<path:filename>")
    def api_codex_download_from_cpa(filename: str):
        """按本地 codex 文件/回执匹配 CPA auth-files，并从 CPA 下载实际 Codex JSON。"""
        unavailable = _feature_unavailable("cpa_download")
        if unavailable:
            return unavailable
        try:
            content, fname = db.read_codex_credential(filename)
            import json as _json
            try:
                local = _json.loads(content)
            except Exception:
                local = {}
            email = str(local.get("email") or "").strip()
            from core.codex_oauth import download_cpa_codex_auth_text
            cpa_text, cpa_name, _meta = download_cpa_codex_auth_text(email=email, local_filename=fname)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 502
        db.mark_codex_exported(fname)
        return Response(
            cpa_text,
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{cpa_name}"'},
        )

    @bp.post("/api/codex/download-bulk-from-cpa")
    def api_codex_download_bulk_from_cpa():
        """
        批量从 CPA 下载选中的 Codex 凭证，打包成 zip；zip 内每个文件都是 CPA 原始 JSON。
        Body: {"filenames": ["codex-xxx-cpa-callback.json", ...]}
        """
        unavailable = _feature_unavailable("cpa_download")
        if unavailable:
            return unavailable
        import io
        import json as _json
        import zipfile
        from datetime import datetime as _dt
        from core.codex_oauth import download_cpa_codex_auth_text

        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 1000:
            return jsonify({"ok": False, "error": "单次最多 1000 个"}), 400

        errors = []
        added = []
        used_names = set()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in filenames:
                if not isinstance(fname, str):
                    errors.append({"filename": str(fname), "error": "非字符串"})
                    continue
                try:
                    content, real_fname = db.read_codex_credential(fname)
                    try:
                        local = _json.loads(content)
                    except Exception:
                        local = {}
                    email = str(local.get("email") or "").strip()
                    cpa_text, cpa_name, _meta = download_cpa_codex_auth_text(email=email, local_filename=real_fname)
                    arcname = cpa_name
                    if arcname in used_names:
                        stem, dot, ext = arcname.rpartition(".")
                        arcname = f"{stem or arcname}-{len(used_names)+1}{dot}{ext}" if dot else f"{arcname}-{len(used_names)+1}"
                    used_names.add(arcname)
                    zf.writestr(arcname, cpa_text)
                    added.append({"local_filename": real_fname, "cpa_filename": cpa_name})
                    db.mark_codex_exported(real_fname)
                except Exception as exc:
                    errors.append({"filename": fname, "error": f"{type(exc).__name__}: {exc}"})
            manifest = {
                "exported_at": _dt.now().isoformat(timespec="seconds"),
                "source": "cpa",
                "count": len(added),
                "files": added,
                "errors": errors,
            }
            zf.writestr("manifest.json", _json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

        if not added:
            return jsonify({"ok": False, "error": "没有成功从 CPA 下载任何凭证", "errors": errors}), 502
        now = _dt.now()
        dl_name = f"codex-cpa-bulk-{now.strftime('%Y%m%d-%H%M%S')}.zip"
        buf.seek(0)
        return Response(
            buf.getvalue(),
            mimetype="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{dl_name}"'},
        )

    @bp.post("/api/codex/download-bulk")
    def api_codex_download_bulk():
        """
        批量下载选中的 codex 凭证，打包到一个 JSON 文件里。

        Body: {"filenames": ["codex-xxx.json", ...]}
        响应：聚合 JSON（attachment 触发浏览器下载），结构：
            {
              "exported_at": "...",
              "count": N,
              "credentials": [{"filename": "...", "data": {...原始凭证内容...}}, ...],
              "errors": [...]   // 仅当部分失败时出现
            }
        注意：聚合格式**不能直接被 CPA 读**，CPA 是按单文件加载 auths/ 目录的。
              本接口主要用途是备份 / 跨机迁移 / 二次处理。
        每个成功的凭证会自动标记 mark_exported（计数+1）。
        """
        import json as _json
        from datetime import datetime as _dt

        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 1000:
            return jsonify({"ok": False, "error": "单次最多 1000 个"}), 400

        bundle = []
        errors = []
        for fname in filenames:
            if not isinstance(fname, str):
                errors.append({"filename": str(fname), "error": "非字符串"})
                continue
            try:
                content, real_fname = db.read_codex_credential(fname)
                parsed = _json.loads(content)
                bundle.append({"filename": real_fname, "data": parsed})
                db.mark_codex_exported(real_fname)
            except Exception as exc:
                errors.append({"filename": fname, "error": f"{type(exc).__name__}: {exc}"})

        now = _dt.now()
        result = {
            "exported_at": now.isoformat(timespec="seconds"),
            "count": len(bundle),
            "credentials": bundle,
        }
        if errors:
            result["errors"] = errors

        dl_name = f"codex-bulk-{now.strftime('%Y%m%d-%H%M%S')}.json"
        return Response(
            _json.dumps(result, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{dl_name}"'},
        )

    @bp.post("/api/codex/reset-export")
    def api_codex_reset_export():
        """清掉某个 codex 凭证的导出状态（重新标为未导出）。body {filename}。"""
        data = request.get_json(silent=True) or {}
        fname = (data.get("filename") or "").strip()
        if not fname:
            return jsonify({"ok": False, "error": "filename 为空"}), 400
        try:
            db.reset_codex_exported(fname)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True})

    @bp.post("/api/codex/delete")
    def api_codex_delete():
        """删除一个 codex 凭证文件。body {filename}。"""
        data = request.get_json(silent=True) or {}
        fname = (data.get("filename") or "").strip()
        if not fname:
            return jsonify({"ok": False, "error": "filename 为空"}), 400
        try:
            deleted = db.delete_codex_credential(fname)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if not deleted:
            return jsonify({"ok": False, "error": "凭证文件不存在"}), 404
        return jsonify({"ok": True, "deleted": fname})

    @bp.post("/api/codex/delete-bulk")
    def api_codex_delete_bulk():
        """批量删除 codex 凭证文件。body {filenames:[...]}。"""
        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        if not isinstance(filenames, list) or not filenames:
            return jsonify({"ok": False, "error": "filenames 必须是非空数组"}), 400
        if len(filenames) > 1000:
            return jsonify({"ok": False, "error": "单次最多删除 1000 个"}), 400
        deleted = []
        skipped = []
        seen = set()
        for fname in filenames:
            fname = str(fname or "").strip()
            if not fname or fname in seen:
                continue
            seen.add(fname)
            try:
                ok = db.delete_codex_credential(fname)
                if ok:
                    deleted.append(fname)
                else:
                    skipped.append({"filename": fname, "reason": "文件不存在"})
            except Exception as exc:
                skipped.append({"filename": fname, "reason": f"{type(exc).__name__}: {exc}"})
        return jsonify({"ok": True, "deleted": deleted, "deleted_count": len(deleted), "skipped": skipped})

    @bp.post("/api/codex/stop")
    def api_codex_stop():
        """停止单个 Codex 补跑。Body {email}。"""
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        acc = db.get_account_by_email(email)
        if acc is None:
            return jsonify({"ok": False, "error": f"账号不存在: {email}"}), 404
        result = codex_operation_service.request_cancel(email=email)
        status = int(result.pop("status", 200) or 200)
        return jsonify(result), status

    @bp.post("/api/codex/stop-bulk")
    def api_codex_stop_bulk():
        """批量停止 Codex 补跑。Body {emails:[...]} 或 {account_ids:[...]}。"""
        data = request.get_json(silent=True) or {}
        emails = data.get("emails") or []
        ids = data.get("account_ids") or data.get("ids") or []
        targets = []
        if isinstance(emails, list) and emails:
            targets = [str(x or "").strip() for x in emails]
        elif isinstance(ids, list) and ids:
            for raw in ids:
                try:
                    acc = db.get_account(int(raw))
                except Exception:
                    acc = None
                if acc and acc.get("email"):
                    targets.append(str(acc.get("email") or "").strip())
        else:
            return jsonify({"ok": False, "error": "emails 或 account_ids 必须是非空数组"}), 400
        if len(targets) > 500:
            return jsonify({"ok": False, "error": "单次最多停止 500 个"}), 400
        stopped = []
        skipped = []
        seen = set()
        for email in targets:
            key = email.lower()
            if not email or key in seen:
                continue
            seen.add(key)
            acc = db.get_account_by_email(email)
            if acc is None:
                skipped.append({"email": email, "reason": "账号不存在"})
                continue
            if not codex_operation_service.is_retrying(email):
                skipped.append({"email": email, "reason": "未处于补跑中"})
                continue
            r = codex_operation_service.request_cancel(email=email)
            if r.get("ok"):
                stopped.append({"email": email, "run_id": r.get("run_id"), "running": r.get("running")})
            else:
                skipped.append({"email": email, "reason": r.get("error") or "停止失败"})
        return jsonify({"ok": True, "stopped": stopped, "stopped_count": len(stopped), "skipped": skipped})

    @bp.post("/api/codex/reset-retrying")
    def api_codex_reset_retrying():
        """手动重置某账号的 Codex 补跑中状态。Body {email, status?}。"""
        from datetime import datetime as _dt

        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        raw_status = (data.get("status") or "failed").strip().lower()
        if raw_status in ("", "none", "null", "clear"):
            raw_status = "empty"
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        if raw_status not in ("failed", "skipped", "empty"):
            return jsonify({"ok": False, "error": "status 仅支持 failed/skipped/empty"}), 400

        acc = db.get_account_by_email(email)
        if acc is None:
            return jsonify({"ok": False, "error": f"账号不存在: {email}"}), 404

        new_status = "" if raw_status == "empty" else raw_status
        err = None if raw_status == "empty" else "用户手动重置补跑中状态"
        ok = db.update_account_codex_status(email, new_status, err)
        if not ok:
            return jsonify({"ok": False, "error": f"账号不存在: {email}"}), 404

        if codex_operation_service.is_retrying(email):
            return jsonify({"ok": False, "error": "任务仍在数据库队列或运行中，请先停止并等待收口"}), 409

        try:
            log_path = codex_operation_service.log_path(email)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                ts = _dt.now().strftime("%H:%M:%S")
                shown = new_status or "空"
                f.write(f"{ts} [WARNING] [Codex 补跑] 用户手动重置补跑中状态，当前状态={shown}\n")
        except Exception:
            logger.exception("写入 Codex 补跑重置日志失败")

        return jsonify({"ok": True, "message": "已重置补跑中状态", "status": new_status})

    @bp.post("/api/codex/retry")
    def api_codex_retry():
        """手动补跑某账号的 Codex 授权。Body {email}。"""
        unavailable = _feature_unavailable("codex_retry")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        queued = _enqueue_codex_retry(email, trigger="manual")
        if queued.get("busy"):
            return jsonify({"ok": False, **queued}), 409
        if not queued.get("accepted"):
            status = 404 if str(queued.get("error") or "").startswith("账号不存在") else 409
            return jsonify({"ok": False, **queued}), status
        return jsonify({
            "ok": True,
            **queued,
            "message": f"已创建任务实例 #{queued['task_id']}，后台开始补跑",
        }), 202

    @bp.post("/api/codex/retry-bulk")
    def api_codex_retry_bulk():
        """批量补跑 Codex。Body {account_ids:[...]} 或 {filenames:[...]}。"""
        unavailable = _feature_unavailable("codex_retry")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        ids = data.get("account_ids") or data.get("ids") or []
        filenames = data.get("filenames") or []
        if not isinstance(ids, list) or not isinstance(filenames, list):
            return jsonify({"ok": False, "error": "account_ids 和 filenames 必须是数组"}), 400
        if not ids and not filenames:
            return jsonify({"ok": False, "error": "account_ids 或 filenames 必须是非空数组"}), 400
        if len(ids) + len(filenames) > 500:
            return jsonify({"ok": False, "error": "单次最多选择 500 个账号"}), 400
        skipped = []
        selected_ids = list(ids)
        if filenames:
            credentials = {
                str(item.get("filename") or ""): item
                for item in db.list_codex_accounts(archived="all")
            }
            seen_filenames = set()
            for raw in filenames:
                filename = str(raw or "").strip()
                if not filename or filename in seen_filenames:
                    continue
                seen_filenames.add(filename)
                credential = credentials.get(filename)
                if not credential:
                    skipped.append({"filename": filename, "reason": "Codex 凭证不存在"})
                    continue
                email = str(credential.get("email") or "").strip()
                if not email:
                    skipped.append({"filename": filename, "reason": "凭证邮箱为空"})
                    continue
                account = db.get_account_by_email(email)
                if not account:
                    skipped.append({"filename": filename, "email": email, "reason": "未找到对应的已注册账号"})
                    continue
                selected_ids.append(account.get("id"))

        seen_ids = set()
        normalized_ids = []
        for raw in selected_ids:
            try:
                acc_id = int(raw)
            except (TypeError, ValueError):
                skipped.append({"id": raw, "reason": "ID 非法"})
                continue
            if acc_id in seen_ids:
                continue
            seen_ids.add(acc_id)
            normalized_ids.append(acc_id)

        if not normalized_ids:
            return jsonify({"ok": False, "error": "没有可补跑的账号", "skipped": skipped}), 409
        result = codex_operation_service.submit_bulk(normalized_ids, trigger="manual_bulk")
        result["skipped"] = skipped + list(result.get("skipped") or [])
        if not result.get("accepted"):
            return jsonify({"ok": False, **result}), 503 if result.get("unavailable") else 409
        return jsonify({
            "ok": True,
            **result,
            "message": f"已创建 {result['started_count']} 个数据库执行实例",
        }), 202

    @bp.get("/api/codex/retry-log")
    def api_codex_retry_log():
        """读取某邮箱最近一次补跑的日志。?email=xxx"""
        email = (request.args.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        p = codex_operation_service.log_path(email)
        if not p.exists():
            return jsonify({"ok": True, "log": "", "running": False})
        max_bytes = 50_000
        size = p.stat().st_size
        with p.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            content = f.read().decode("utf-8", errors="replace")
        return jsonify({
            "ok": True,
            "log": content,
            "running": codex_operation_service.is_retrying(email),
        })

    return bp
