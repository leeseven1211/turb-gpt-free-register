# -*- coding: utf-8 -*-
"""
Flask 本地控制台。

复用现有后端：
    core.db                     —— 账号 / 邮箱池 / 任务的文件持久化与查询
    core.registration_service   —— 线程池批量注册 + 任务日志
    webui.config_editor         —— 安全读写 config/*.py

所有接口返回 JSON；前端是单文件 templates/index.html（原生 JS + fetch）。
默认绑定 127.0.0.1，仅本地访问。
"""
import logging
import threading
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse

import pyotp
from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, url_for

from core import (
    admin_repository,
    account_task_store,
    codex_operation_service,
    codex_token_refresh_service,
    codex_retry_service,
    db,
    plan_check_service,
    extract_link_service,
    live_check_service,
    deactivation_mail_service,
    operation_task_store,
    sms_provider,
)
from webui.auth import init_auth, register_auth_routes
from core import registration_service as svc
from core.task_errors import classify_task_error
from config import codex as codex_config
from webui import config_editor

logger = logging.getLogger(__name__)


def _feature_unavailable(name: str):
    """配置不完整时返回统一 503；页面禁用之外再做后端兜底。"""
    from core.feature_availability import require_feature
    enabled, reason = require_feature(name)
    if enabled:
        return None
    return jsonify({"ok": False, "feature": name, "error": reason}), 503

def _pool_source_arg(default: str = "outlook") -> str:
    src = (request.args.get("source") or "").strip()
    if not src and request.method == "POST":
        data = request.get_json(silent=True) or {}
        src = (data.get("source") or data.get("type") or "").strip()
    return src if src in ("all", "outlook", "generic_api", "cloudflare_domain", "icloud_hide") else default


def _with_pool_source(rows: list[dict], source: str) -> list[dict]:
    out = []
    for r in rows:
        x = dict(r)
        x["source"] = source
        if not x.get("copy_line"):
            x["copy_line"] = x.get("email") or ""
        out.append(x)
    return out




def _matches_query(row: dict, q: str | None) -> bool:
    q = str(q or "").strip().lower()
    if not q:
        return True
    try:
        return q in "\n".join(str(v) for v in row.values()).lower()
    except Exception:
        return False


def _contains_value(row: dict, keys: tuple[str, ...], value: str | None) -> bool:
    needle = str(value or "").strip().lower()
    if not needle:
        return True
    return any(needle in str(row.get(key) or "").lower() for key in keys)


def _matches_account_columns(row: dict, filters: dict[str, str]) -> bool:
    if not _contains_value(row, ("id",), filters.get("id")):
        return False
    if not _contains_value(row, ("email", "user_name"), filters.get("email")):
        return False
    if not _contains_value(row, ("email_source",), filters.get("source")):
        return False
    if not _contains_value(row, ("note",), filters.get("note")):
        return False
    trial = filters.get("trial")
    if trial and _account_trial_value(row) != trial:
        return False
    token = filters.get("token")
    if token == "has" and not str(row.get("access_token") or "").strip():
        return False
    if token == "none" and str(row.get("access_token") or "").strip():
        return False
    password = filters.get("password")
    has_password = bool(_account_login_password(row))
    if password == "has" and not has_password:
        return False
    if password == "none" and has_password:
        return False
    totp = filters.get("totp")
    has_totp = bool(row.get("totp_secret") or row.get("totp_enabled"))
    if totp == "enabled" and not has_totp:
        return False
    if totp == "disabled" and has_totp:
        return False
    risk = filters.get("risk")
    risk_status = str(row.get("deactivation_mail_scan_status") or "")
    if risk == "detected" and row.get("deactivation_mail_detected") is not True:
        return False
    if risk == "clear" and not (risk_status == "success" and row.get("deactivation_mail_detected") is not True):
        return False
    if risk == "pending" and risk_status in {"success"}:
        return False
    codex = filters.get("codex")
    if codex and str(row.get("codex_status") or "").lower() != codex:
        return False
    return True


def _paginate_items(items: list[dict], *, page: int, page_size: int) -> dict:
    page = max(1, int(page or 1))
    page_size = max(1, min(500, int(page_size or 50)))
    total = len(items)
    offset = (page - 1) * page_size
    return {
        "ok": True,
        "items": items[offset:offset + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "offset": offset,
        "limit": page_size,
    }


def _facet_values(rows: list[dict], value_getter) -> list[dict]:
    """Return stable, data-backed select options for a list column."""
    counts: dict[str, int] = {}
    for row in rows:
        value = str(value_getter(row) or "").strip().lower()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [
        {"value": value, "count": counts[value]}
        for value in sorted(counts, key=lambda item: (-counts[item], item))
    ]


def _account_risk_value(row: dict) -> str:
    if row.get("deactivation_mail_detected") is True:
        return "detected"
    if str(row.get("deactivation_mail_scan_status") or "") == "success":
        return "clear"
    return "pending"


def _account_trial_value(row: dict) -> str:
    """Return the normalized Plus trial state used by the account list filter."""
    plan = str(row.get("current_plan_type") or row.get("plan_type") or "").strip().lower()
    if plan and plan != "free":
        return "not_applicable"
    if not plan or str(row.get("plan_check_status") or "").lower() in {"queued", "running"}:
        return "pending"

    status = str(row.get("plan_check_status") or "").lower()
    if status == "failed":
        return "eligible" if row.get("plan_last_success_at") and bool(row.get("plus_trial_eligible")) else (
            "ineligible" if row.get("plan_last_success_at") else "failed"
        )
    if status != "success" and row.get("plan_check_ok") is not True:
        return "pending"
    return "eligible" if bool(row.get("plus_trial_eligible")) else "ineligible"


def _compact_account_for_list(row: dict) -> dict:
    """账号列表轻量对象：只返回当前表格渲染和按钮判断必需字段。

    原则：
    - 不返回完整 Token / Token 预览 / TOTP Secret。
    - 时间戳、错误原因、提链详情等只在前端确实要展示时返回；空值不返回。
    - 复制/下载敏感内容时再通过 /secret 接口按需读取。
    """
    out = {
        "id": row.get("id"),
        "email": row.get("email"),
        "has_access_token": bool(row.get("has_access_token")) or bool(str(row.get("access_token") or "").strip()),
        "has_account_password": bool(row.get("has_account_password")) or bool(_account_password(row)),
        "totp_enabled": bool(row.get("totp_enabled")) or bool(row.get("totp_secret")),
    }

    # 这些是列表固定列直接展示字段。
    for key in (
        "user_name", "email_source", "note", "archived", "created_at",
        "plan_type", "current_plan_type", "plus_trial_eligible",
        "plan_check_status", "codex_status", "codex_credential_state",
        "codex_execution_status", "codex_last_run_status", "codex_active_run_id", "account_status",
        "registration_proxy_provider", "registration_proxy_region",
        "deactivation_mail_detected", "deactivation_mail_scan_status",
    ):
        if key in row:
            out[key] = row.get(key)

    if row.get("plan_check_status") in ("queued", "running") or row.get("plan_check_ok") is False:
        out["plan_check_ok"] = row.get("plan_check_ok")

    # 下面字段仅在有值时返回，避免每行堆满 null/空字符串/内部状态。
    optional_keys = (
        # 套餐展示补充：付费到期/折扣/失败原因。
        "plan_check_error", "plan_check_trigger", "plan_check_queued_at", "plan_check_started_at",
        "plan_last_success_at", "plan_expires_at", "plan_renews_at", "renews_at",
        "billing_period", "billing_currency", "discount_amount", "discount_type",
        "discount_expires_at", "discount_promo_campaign_id",
        "token_expired", "token_expires_at", "account_status_reason", "account_status_at",
        # 查活状态。
        "live_check_status", "live_check_error", "live_checked_at",
        # 提链成功/失败时才需要。
        "extract_link_status", "extract_link_type", "extract_link_message", "extract_link_error",
        "extract_link_long_url", "extract_link_copy_paste", "extract_link_image_url_png",
        "extract_link_image_url_svg", "extract_link_expires_at",
        # Codex 状态提示。
        "codex_error",
        # 封号邮件信号缓存（不包含邮件正文和任何凭据）。
        "deactivation_mail_checked_at", "deactivation_mail_received_at",
        "deactivation_mail_subject", "deactivation_mail_sender", "deactivation_mail_error",
        "deactivation_mail_confidence", "deactivation_mail_scan_trigger",
    )
    for key in optional_keys:
        value = row.get(key)
        if value is not None and value != "":
            out[key] = value
    if out["has_access_token"] and not out.get("token_expires_at"):
        from core.chatgpt_plan import token_claims
        claims = token_claims(str(row.get("access_token") or ""))
        if claims.get("token_expires_at"):
            out["token_expires_at"] = claims.get("token_expires_at")
            out["token_expired"] = claims.get("token_expired")
    plan = str(row.get("current_plan_type") or row.get("plan_type") or "").lower()
    if any(x in plan for x in ("plus", "pro", "team", "go")):
        expire = row.get("expires_at")
        if expire:
            out["expires_at"] = expire
    return out


def _account_secret_value(row: dict, field: str) -> str:
    field = (field or "").strip()
    if field == "access_token":
        return str(row.get("access_token") or "")
    if field == "copy_line":
        return str(row.get("copy_line") or "")
    if field in {"account_password", "registration_password", "login_password"}:
        return _account_password(row)
    if field in {"account_password_line", "registration_password_line", "login_password_line"}:
        password = _account_password(row)
        return f"{row.get('email') or ''}----{password}" if password else ""
    if field == "totp_secret":
        return str(row.get("totp_secret") or "")
    raise ValueError("field 仅支持 access_token/copy_line/account_password/account_password_line/totp_secret")


def _account_password(row: dict) -> str:
    extra = row.get("extra_json") or {}
    if isinstance(extra, str):
        try:
            import json
            extra = json.loads(extra)
        except (TypeError, ValueError):
            extra = {}
    if not isinstance(extra, dict):
        return ""
    return str(
        extra.get("account_password")
        or extra.get("login_password")
        or extra.get("registration_password")
        or ""
    )


def _account_registration_password(row: dict) -> str:
    """旧字段兼容别名；新账号统一使用 account_password。"""
    return _account_password(row)


def _account_login_password(row: dict) -> str:
    """旧字段兼容别名；新账号统一使用 account_password。"""
    return _account_password(row)


def _compact_job_for_list(row: dict) -> dict:
    """注册任务列表轻量对象：只返回表格展示和按钮判断需要的字段。"""
    out = {
        "id": row.get("id"),
        "status": row.get("status"),
    }
    for key in (
        "parent_job_id", "retry_attempt", "email", "started_at", "completed_at",
        "email_source",
        "display_status", "retryable", "retry_action", "retry_label",
        "manual_otp_required", "proxy_provider", "proxy_status", "proxy_endpoint",
        "proxy_exit_ip", "proxy_region", "proxy_acquired_at", "proxy_expires_at",
        "batch_id", "batch_index", "batch_size", "batch_workers",
        "progress_stage", "progress_updated_at", "progress_steps",
    ):
        value = row.get(key)
        if value is not None and value != "" and value is not False:
            out[key] = value
    err = str(row.get("error_message") or "").strip()
    if err:
        # 列表只需要摘要；完整错误和堆栈看“任务日志”。
        out["error_message"] = err[:240] + ("…" if len(err) > 240 else "")
        out["error_info"] = classify_task_error(
            err,
            stage=str(row.get("progress_stage") or ""),
            task_type=str(row.get("job_type") or "registration"),
        )
    raw_steps = out.get("progress_steps")
    if isinstance(raw_steps, dict):
        # 列表兼容字段只应作用于返回副本，不能改写历史任务原始数据。
        steps = {key: dict(value) if isinstance(value, dict) else value for key, value in raw_steps.items()}
        changed = False
    else:
        steps = None
        changed = False
    if isinstance(steps, dict) and "auth_redirect" not in steps:
        submit_step = steps.get("submit_email")
        reached_later_stage = any(
            isinstance(steps.get(key), dict)
            for key in ("email_otp", "profile", "token", "twofa", "codex")
        )
        if isinstance(submit_step, dict) and reached_later_stage:
            # 兼容新增“认证跳转”阶段之前的历史任务，避免已完成批次中间
            # 永久出现一个 pending 节点；历史数据没有独立耗时，只能标记跳过。
            completed_at = submit_step.get("completed_at") or submit_step.get("started_at")
            steps["auth_redirect"] = {
                "state": "skipped",
                "detail": "历史任务未单独记录认证跳转耗时",
                "started_at": completed_at,
                "completed_at": completed_at,
            }
            changed = True
    terminal_status = str(row.get("status") or "")
    if isinstance(steps, dict) and terminal_status in {"success", "partial_success", "failed", "cancelled", "stopped"}:
        completed_at = row.get("completed_at")
        if "twofa" not in steps:
            prior = steps.get("token") if isinstance(steps.get("token"), dict) else {}
            twofa_timestamp = prior.get("completed_at") or completed_at
            steps["twofa"] = {
                "state": "skipped",
                "detail": "历史任务未单独记录 2FA 设置耗时",
                "started_at": twofa_timestamp,
                "completed_at": twofa_timestamp,
            }
            changed = True
        if "plan_check" not in steps:
            prior = steps.get("codex") if isinstance(steps.get("codex"), dict) else {}
            plan_timestamp = prior.get("completed_at") or completed_at
            steps["plan_check"] = {
                "state": "skipped",
                "detail": "历史任务未单独记录套餐查询耗时",
                "started_at": plan_timestamp,
                "completed_at": plan_timestamp,
            }
            changed = True
        if "complete" not in steps:
            complete_state = "success" if terminal_status in {"success", "partial_success"} else "stopped" if terminal_status in {"cancelled", "stopped"} else "failed"
            steps["complete"] = {
                "state": complete_state,
                "detail": "历史任务已完成" if complete_state == "success" else "历史任务已结束",
                "started_at": row.get("started_at") or row.get("created_at") or completed_at,
                "completed_at": completed_at,
            }
            changed = True
    if changed:
        out["progress_steps"] = steps
    return out


def _job_status_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    counts["active"] = sum(int(counts.get(s, 0) or 0) for s in ("pending", "running", "stopping"))
    return counts


def _latest_progress_batch(rows: list[dict]) -> dict | None:
    """构造最新提交批次的邮箱级进度数据。旧任务没有 batch_id 时不展示。"""
    latest = next((row for row in rows if row.get("batch_id")), None)
    if latest is None:
        return None
    batch_id = str(latest.get("batch_id") or "")
    batch_rows = [row for row in rows if str(row.get("batch_id") or "") == batch_id]
    if not batch_rows:
        return None
    batch_rows.sort(key=lambda row: (int(row.get("batch_index") or 0), int(row.get("id") or 0)))
    counts = _job_status_counts(batch_rows)
    items = [_compact_job_for_list(row) for row in batch_rows]
    return {
        "batch_id": batch_id,
        "total": len(batch_rows),
        "workers": int(latest.get("batch_workers") or 1),
        "created_at": min((str(row.get("created_at") or "") for row in batch_rows), default=""),
        "started_at": min((str(row.get("started_at") or "") for row in batch_rows if row.get("started_at")), default=""),
        "completed_at": max((str(row.get("completed_at") or "") for row in batch_rows if row.get("completed_at")), default=""),
        "status_counts": counts,
        "stages": [{"key": key, "label": label} for key, label in db.JOB_PROGRESS_STAGES],
        "items": items,
    }

def create_app(auth_code: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    _prepared_downloads: dict[str, dict] = {}

    def _put_prepared_download(content: bytes, filename: str, mimetype: str = "application/zip") -> str:
        now = time.time()
        # 顺手清理 10 分钟前的临时下载，避免内存堆积。
        for k, v in list(_prepared_downloads.items()):
            if now - float(v.get("created_at") or 0) > 600:
                _prepared_downloads.pop(k, None)
        download_id = uuid.uuid4().hex
        _prepared_downloads[download_id] = {
            "content": bytes(content),
            "filename": filename,
            "mimetype": mimetype,
            "created_at": now,
        }
        return download_id

    @app.get("/api/downloads/<download_id>")
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

    init_auth(app, auth_code=auth_code)
    register_auth_routes(app)
    # 恢复进程重启前尚未到期/尚未完成的 Grizzly 取消订单。
    sms_provider.start_cancel_worker()
    recovered_plan_checks = db.recover_interrupted_plan_checks()
    if recovered_plan_checks:
        logger.warning("已恢复 %s 个因 WebUI 重启中断的套餐查询状态", recovered_plan_checks)
    recovered_extract_links = db.recover_interrupted_extract_links()
    if recovered_extract_links:
        logger.warning("已恢复 %s 个因 WebUI 重启中断的提链状态", recovered_extract_links)
    recovered_live_checks = db.recover_interrupted_live_checks()
    if recovered_live_checks:
        logger.warning("已恢复 %s 个因 WebUI 重启中断的查活状态", recovered_live_checks)
    backfilled_proxy_context = db.backfill_account_registration_proxy_context()
    if backfilled_proxy_context:
        logger.info("已为 %s 个历史账号补齐注册代理来源/国家", backfilled_proxy_context)

    # ----------------------------------------------------------
    # 页面
    # ----------------------------------------------------------
    @app.get("/favicon.ico", endpoint="favicon")
    def favicon():
        return redirect(url_for("static", filename="favicon.svg"), code=308)

    @app.get("/")
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

    # ----------------------------------------------------------
    # 统计概览
    # ----------------------------------------------------------
    @app.get("/api/summary")
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

    @app.get("/api/dashboard")
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

    @app.get("/api/capabilities")
    def api_capabilities():
        """返回不含密钥的功能可用性及缺失配置原因。"""
        from core.feature_availability import feature_availability
        return jsonify(feature_availability())

    # ----------------------------------------------------------
    # 已注册账号
    # ----------------------------------------------------------
    @app.get("/api/accounts")
    def api_accounts():
        limit = request.args.get("limit", default=500, type=int)
        archived = str(request.args.get("archived", default="0") or "0").lower()
        plan_filter = str(request.args.get("plan", default="") or "").lower()
        q = str(request.args.get("q", default="") or "").strip()
        column_filters = {
            key: str(request.args.get(key, default="") or "").strip().lower()
            for key in ("id", "email", "source", "token", "password", "trial", "totp", "risk", "codex")
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

    @app.get("/api/accounts/plan-check-status")
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

    @app.get("/api/account-tasks")
    def api_account_tasks():
        """账号操作任务实例列表；结果与事件均不包含账号凭据。"""
        result = account_task_store.list_tasks(
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=50, type=int),
            task_type=str(request.args.get("type") or "").strip(),
            status=str(request.args.get("status") or "").strip(),
            q=str(request.args.get("q") or "").strip(),
        )
        for task in result.get("items") or []:
            error_info = classify_task_error(
                task.get("error"),
                stage="complete",
                task_type=str(task.get("task_type") or ""),
            )
            if error_info:
                task["error_info"] = error_info
        from core.token_refresh_service import settings as token_refresh_settings
        result["token_refresh"] = token_refresh_settings()
        result["codex_token_refresh"] = codex_token_refresh_service.settings()
        return jsonify(result)

    @app.get("/api/account-tasks/<int:task_id>")
    def api_account_task_detail(task_id: int):
        task = account_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务实例不存在"}), 404
        error_info = classify_task_error(
            task.get("error"),
            stage="complete",
            task_type=str(task.get("task_type") or ""),
        )
        if error_info:
            task["error_info"] = error_info
        return jsonify({"ok": True, "task": task})

    def _retry_account_task_result(task_id: int) -> tuple[dict, int]:
        task = account_task_store.get_task(task_id)
        if not task:
            return {"ok": False, "error": "任务实例不存在"}, 404
        if task.get("status") in {"queued", "running"}:
            return {"ok": False, "error": "任务仍在执行"}, 409
        account = db.get_account(int(task.get("account_id") or 0))
        if not account:
            return {"ok": False, "error": "关联账号不存在"}, 404
        task_type = str(task.get("task_type") or "")
        if task_type in {"live_check", "token_refresh"}:
            queued = live_check_service.enqueue_account_live_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                trigger="token_refresh_manual_retry" if task_type == "token_refresh" else "manual_retry",
                proxy=None,
                force_refresh=task_type == "token_refresh",
            )
        elif task_type == "plan_check":
            queued = plan_check_service.enqueue_account_plan_check(
                account_id=int(account["id"]),
                email=str(account.get("email") or ""),
                access_token=str(account.get("access_token") or ""),
                trigger="manual_retry",
                proxy=None,
            )
        elif task_type == "deactivation_mail":
            queued = deactivation_mail_service.enqueue(int(account["id"]), trigger="manual_retry")
        elif task_type == "codex_retry":
            queued = _enqueue_codex_retry(
                email=str(account.get("email") or ""),
                trigger="manual_retry",
            )
        elif task_type == "account_setup_retry":
            queued = _enqueue_account_setup(
                int(account["id"]),
                trigger="manual_retry",
            )
        elif task_type == "codex_token_refresh":
            filename = str((task.get("result_summary") or {}).get("filename") or "")
            queued = codex_token_refresh_service.enqueue_refresh(
                filename,
                trigger="manual_retry",
            )
        else:
            return {"ok": False, "error": "该任务类型暂不支持重跑"}, 400
        if queued.get("busy"):
            return {"ok": False, **queued}, 409
        if not queued.get("accepted"):
            return {"ok": False, **queued}, 400
        return {"ok": True, **queued}, 202

    @app.post("/api/account-tasks/<int:task_id>/retry")
    def api_account_task_retry(task_id: int):
        payload, status = _retry_account_task_result(task_id)
        return jsonify(payload), status

    @app.get("/api/operations")
    def api_operations():
        """统一任务中心列表：注册、恢复、Codex 与账号操作共用一个读模型。"""
        result = operation_task_store.list_tasks(
            page=request.args.get("page", default=1, type=int),
            page_size=request.args.get("page_size", default=50, type=int),
            task_type=str(request.args.get("type") or "").strip(),
            status=str(request.args.get("status") or "").strip(),
            source=str(request.args.get("source") or "").strip(),
            q=str(request.args.get("q") or "").strip(),
            batch_id=request.args.get("batch_id", default=None, type=int),
        )
        for task in result.get("items") or []:
            if task.get("error_message"):
                task["error_info"] = classify_task_error(
                    task.get("error_message"),
                    stage=str(task.get("current_stage") or ""),
                    task_type=str(task.get("task_type") or ""),
                )
        result["batches"] = operation_task_store.list_batches(limit=50)
        return jsonify(result)

    @app.get("/api/operations/<int:task_id>")
    def api_operation_detail(task_id: int):
        task = operation_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if task.get("error_message"):
            task["error_info"] = classify_task_error(
                task.get("error_message"),
                stage=str(task.get("current_stage") or ""),
                task_type=str(task.get("task_type") or ""),
            )
        return jsonify({"ok": True, "task": task})

    @app.post("/api/operations/<int:task_id>/retry")
    def api_operation_retry(task_id: int):
        """由服务端 next_actions 和来源映射选择重跑入口，前端不猜流程。"""
        task = operation_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if task.get("status") in {"queued", "running", "stopping", "cancelling", "settling", "waiting"}:
            return jsonify({"ok": False, "error": "任务仍在执行"}), 409
        if str(task.get("source_system") or "") == "native_operations":
            queued = codex_operation_service.retry_task(int(task_id), trigger="manual_retry")
            if queued.get("busy"):
                return jsonify({"ok": False, **queued}), 409
            if not queued.get("accepted"):
                return jsonify({"ok": False, **queued}), 503 if queued.get("unavailable") else 409
            return jsonify({"ok": True, **queued}), 202
        next_action = (task.get("next_actions") or [{}])[0]
        source_job_id = next_action.get("source_job_id") if isinstance(next_action, dict) else None
        if str((next_action or {}).get("action") or "") in {"registration_resume", "registration_retry"} and source_job_id:
            result = svc.retry_job(int(source_job_id))
            status = int(result.pop("status", 200 if result.get("ok") else 400))
            return jsonify(result), status
        runs = task.get("runs") or []
        latest = runs[-1] if runs else {}
        source_system = str(latest.get("source_system") or "")
        source_id = str(latest.get("source_id") or "")
        if source_system == "registration_jobs" and source_id.isdigit():
            result = svc.retry_job(int(source_id))
            status = int(result.pop("status", 200 if result.get("ok") else 400))
            return jsonify(result), status
        if source_system == "account_action_tasks" and source_id.isdigit():
            payload, status = _retry_account_task_result(int(source_id))
            return jsonify(payload), status
        return jsonify({"ok": False, "error": "该历史任务没有可用的重跑来源"}), 409

    @app.post("/api/operations/<int:task_id>/cancel")
    def api_operation_cancel(task_id: int):
        task = operation_task_store.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": "任务不存在"}), 404
        if str(task.get("source_system") or "") != "native_operations":
            return jsonify({"ok": False, "error": "历史兼容任务请使用原任务停止入口"}), 409
        active = next(
            (
                run for run in reversed(task.get("runs") or [])
                if run.get("status") in {"queued", "running", "cancelling", "settling"}
            ),
            None,
        )
        if not active:
            return jsonify({"ok": True, "state": "empty", "message": "任务没有活跃 attempt"})
        result = codex_operation_service.request_cancel(run_id=int(active["id"]))
        return jsonify(result), 200 if result.get("ok") else 409

    @app.post("/api/accounts/<int:acc_id>/setup")
    def api_account_setup(acc_id: int):
        """只补齐账号密码、套餐和 Authenticator 2FA，不执行 Codex。"""
        queued = _enqueue_account_setup(acc_id, trigger="manual_account_setup")
        if queued.get("busy"):
            return jsonify({"ok": False, **queued}), 409
        if not queued.get("accepted"):
            status = 404 if queued.get("error") == "账号不存在" else 400
            return jsonify({"ok": False, **queued}), status
        return jsonify({"ok": True, **queued}), 202

    @app.post("/api/accounts/setup-bulk")
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


    @app.post("/api/accounts/<int:acc_id>/check-deactivation-mail")
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

    @app.post("/api/accounts/check-deactivation-mail-bulk")
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


    @app.get("/api/accounts/<int:acc_id>/secret")
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

    @app.get("/api/accounts/<int:acc_id>/totp-code")
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

    @app.post("/api/accounts/secret-bulk")
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

    @app.post("/api/accounts/<int:acc_id>/archive")
    def api_account_archive(acc_id: int):
        """归档/取消归档一个账号。Body {archived: true|false}。"""
        data = request.get_json(silent=True) or {}
        archived = bool(data.get("archived", True))
        updated = db.archive_account(acc_id=acc_id, archived=archived)
        if not updated:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        return jsonify({"ok": True, "updated": True, "id": acc_id, "archived": archived})

    @app.post("/api/accounts/archive-bulk")
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

    @app.post("/api/accounts/<int:acc_id>/delete")
    def api_account_delete(acc_id: int):
        """删除一个已注册账号记录。只删除本地保存的账号/token记录，不改邮箱池状态。"""
        deleted = db.delete_account(acc_id=acc_id)
        if not deleted:
            return jsonify({"ok": False, "error": "账号不存在"}), 404
        return jsonify({"ok": True, "deleted": True})

    @app.post("/api/accounts/delete-bulk")
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

    @app.post("/api/accounts/<int:acc_id>/note")
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

    @app.post("/api/accounts/note-bulk")
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

    @app.post("/api/accounts/check-live-bulk")
    def api_accounts_check_live_bulk():
        """批量查活：只在线验证现有 AT，不发送邮箱 OTP、不刷新 AT。"""
        unavailable = _feature_unavailable("live_check")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
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
        }), 202


    @app.post("/api/accounts/refresh-token-bulk")
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


    @app.post("/api/accounts/check-plan")
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

    @app.post("/api/accounts/check-plan-bulk")
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

    @app.get("/api/extract-link/cdk")
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

    def _is_extract_eligible(acc: dict) -> bool:
        plan = str(acc.get("current_plan_type") or acc.get("plan_type") or "").lower()
        return plan == "free" and bool(acc.get("plus_trial_eligible"))

    @app.post("/api/accounts/extract-link")
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

    @app.post("/api/accounts/extract-link-bulk")
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

    @app.post("/api/accounts/<int:acc_id>/codex/upload-sub2")
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

    @app.post("/api/accounts/codex/upload-sub2-bulk")
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

    @app.post("/api/codex/upload-sub2-bulk")
    def api_codex_upload_sub2_bulk():
        """从 Codex 管理页批量上传 OAuth 凭证。Body {filenames:[...]}。"""
        unavailable = _feature_unavailable("sub2_upload")
        if unavailable:
            return unavailable
        data = request.get_json(silent=True) or {}
        filenames = data.get("filenames") or []
        try:
            workers = max(1, min(16, int(data.get("workers", codex_config.ACCOUNT_BATCH_WORKERS))))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "workers 必须是数字"}), 400
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

    @app.post("/api/accounts/download-cpa-bulk")
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

    # ----------------------------------------------------------
    # 邮箱池
    # ----------------------------------------------------------
    @app.get("/api/outlook")
    def api_outlook():
        status = request.args.get("status") or None
        limit = request.args.get("limit", default=500, type=int)
        source = _pool_source_arg()
        q = str(request.args.get("q", default="") or "").strip()
        token_filter = str(request.args.get("token", default="") or "").strip().lower()
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
                "token": token_filter,
                "imported_date": imported_date,
                "used_date": used_date,
            })
        )
        if not (paged or page_arg is not None or page_size_arg is not None):
            return jsonify(result["items"])
        return jsonify(result)

    @app.get("/api/outlook/secret")
    def api_outlook_secret():
        """按需读取单条邮箱素材，普通列表不会下发密码、Token 或取码地址。"""
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

    @app.post("/api/outlook/secret-bulk")
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

    @app.post("/api/outlook/import")
    def api_outlook_import():
        """
        粘贴文本导入邮箱素材。
        Outlook：email----password----clientId----refreshToken
        通用 API：email----code_url
        分隔符兼容 ---- 与 ====。
        """
        data = request.get_json(silent=True) or {}
        source = (data.get("source") or data.get("type") or "").strip()
        if source not in ("outlook", "generic_api"):
            return jsonify({"ok": False, "error": "导入时请选择具体类型：Outlook 或 通用 API"}), 400
        text = data.get("text") or ""
        as_registered = bool(data.get("as_registered", False))
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("----") if "----" in line else line.split("====")
            parts = [p.strip() for p in parts]
            if source == "generic_api":
                if len(parts) < 2:
                    continue
                records.append({
                    "email": parts[0],
                    "code_url": parts[1],
                    "access_token": parts[2] if len(parts) > 2 else "",
                    "totp_secret": parts[3] if len(parts) > 3 else "",
                })
                continue
            if len(parts) < 4:
                continue
            records.append({
                "email": parts[0],
                "password": parts[1],
                "client_id": parts[2],
                "refresh_token": parts[3],
                "access_token": parts[4] if len(parts) > 4 else "",
                "totp_secret": parts[5] if len(parts) > 5 else "",
            })
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
        })

    @app.post("/api/outlook/status")
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

    @app.post("/api/outlook/status-bulk")
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

    @app.post("/api/outlook/delete")
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

    @app.post("/api/outlook/delete-bulk")
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

    # ----------------------------------------------------------
    # 域名邮箱池（Cloudflare 域名邮箱模式）
    # ----------------------------------------------------------
    @app.get("/api/domain-pool")
    def api_domain_pool():
        status = request.args.get("status") or None
        limit = request.args.get("limit", default=500, type=int)
        return jsonify(db.list_domain_email_pool(status=status, limit=limit))

    @app.post("/api/domain-pool/status")
    def api_domain_pool_status():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        status = (data.get("status") or "").strip()
        if not email or status not in ("available", "used", "failed"):
            return jsonify({"ok": False, "error": "email 或 status 非法"}), 400
        db.release_domain_email(email, status=status, note=data.get("note"))
        return jsonify({"ok": True})

    @app.post("/api/domain-pool/delete")
    def api_domain_pool_delete():
        data = request.get_json(silent=True) or {}
        email = (data.get("email") or "").strip()
        if not email:
            return jsonify({"ok": False, "error": "email 为空"}), 400
        deleted = db.delete_domain_email(email)
        return jsonify({"ok": True, "deleted": deleted})

    # ----------------------------------------------------------
    # Codex 授权账号（CPA 兼容凭证）
    # ----------------------------------------------------------
    @app.get("/api/codex")
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

    @app.post("/api/codex/refresh-token-bulk")
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

    @app.post("/api/codex/archive")
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

    @app.post("/api/codex/archive-bulk")
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

    @app.get("/api/codex/download/<path:filename>")
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

    @app.get("/api/codex/download-from-cpa/<path:filename>")
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

    @app.post("/api/codex/download-bulk-from-cpa")
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

    @app.post("/api/codex/download-bulk")
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

    @app.post("/api/codex/reset-export")
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

    @app.post("/api/codex/delete")
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

    @app.post("/api/codex/delete-bulk")
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

    def _reserve_codex_retry(email: str) -> bool:
        """进程内防重复占位；成功返回 True。"""
        return codex_retry_service.reserve(email)

    def _release_codex_retry(email: str) -> None:
        codex_retry_service.release(email)

    def _run_codex_retry_worker(
        email: str,
        *,
        batch_label: str | None = None,
        clear_log: bool = True,
        task_id: int | None = None,
        task_trigger: str = "manual",
    ) -> None:
        """执行一个账号的 Codex 补跑。调用前必须已经 reserve。"""
        codex_retry_service.run_worker(
            email,
            batch_label=batch_label,
            clear_log=clear_log,
            task_id=task_id,
            task_trigger=task_trigger,
        )

    def _enqueue_codex_retry(email: str, *, trigger: str = "manual") -> dict:
        """兼容旧调用名；实际只委托统一 Codex operation 协调器。"""
        return codex_operation_service.submit(email, trigger=trigger)

    def _run_account_setup_worker(email: str, *, task_id: int, task_trigger: str) -> None:
        """执行只补账号配置的任务，不触发 Codex OAuth。"""
        codex_retry_service.run_twofa_worker(
            email,
            task_id=task_id,
            task_trigger=task_trigger,
        )

    def _enqueue_account_setup(account_id: int, *, trigger: str = "manual_account_setup") -> dict:
        """给账号单独排队账号密码、套餐和 2FA 配置补跑。"""
        try:
            acc = db.get_account(int(account_id))
        except (TypeError, ValueError):
            acc = None
        if acc is None:
            return {"accepted": False, "error": "账号不存在"}
        email = str(acc.get("email") or "").strip()
        if not email:
            return {"accepted": False, "error": "账号邮箱为空"}
        if str(acc.get("account_status") or "").lower() == "deactivated":
            return {"accepted": False, "error": "账号已废号，不能补齐配置"}
        if not codex_retry_service.reserve(email):
            return {"accepted": False, "busy": True, "error": "该账号正在执行账号操作，请稍候"}

        try:
            task_id = account_task_store.create_task(
                task_type="account_setup_retry",
                account_id=int(acc.get("id") or 0) or None,
                email=email,
                trigger=str(trigger or "manual_account_setup"),
            )
        except Exception as exc:
            codex_retry_service.release(email)
            logger.exception("创建账号配置补跑任务实例失败：email=%s", email)
            return {"accepted": False, "error": f"任务实例创建失败：{type(exc).__name__}: {exc}"}

        worker = threading.Thread(
            target=_run_account_setup_worker,
            kwargs={"email": email, "task_id": task_id, "task_trigger": str(trigger or "manual_account_setup")},
            name=f"account-setup-{email}",
            daemon=True,
        )
        try:
            worker.start()
        except Exception as exc:
            codex_retry_service.release(email)
            error = f"账号配置补跑启动失败：{type(exc).__name__}: {exc}"
            account_task_store.finish_task(task_id, status="failed", message="账号配置补跑启动失败", error=error)
            return {"accepted": False, "task_id": task_id, "error": error}
        return {
            "accepted": True,
            "busy": False,
            "task_id": task_id,
            "account_id": int(acc.get("id") or 0) or None,
            "email": email,
            "status": "queued",
            "trigger": str(trigger or "manual_account_setup"),
        }


    @app.post("/api/codex/stop")
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

    @app.post("/api/codex/stop-bulk")
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

    @app.post("/api/codex/reset-retrying")
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

    @app.post("/api/codex/retry")
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

    @app.post("/api/codex/retry-bulk")
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
        try:
            workers = int(data.get("workers") or getattr(codex_config, "ACCOUNT_BATCH_WORKERS", 3) or 3)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "workers 必须是整数"}), 400
        if workers < 1 or workers > 16:
            return jsonify({"ok": False, "error": "workers 必须在 1 到 16 之间"}), 400

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
        result = codex_operation_service.submit_bulk(normalized_ids, trigger="manual_bulk", workers=workers)
        result["skipped"] = skipped + list(result.get("skipped") or [])
        if not result.get("accepted"):
            return jsonify({"ok": False, **result}), 503 if result.get("unavailable") else 409
        return jsonify({
            "ok": True,
            **result,
            "message": f"已创建 {result['started_count']} 个数据库执行实例",
        }), 202

    @app.get("/api/codex/retry-log")
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

    @app.get("/api/accounts/live-check-log")
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

    # ----------------------------------------------------------
    # 注册任务
    # ----------------------------------------------------------
    @app.get("/api/jobs")
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

    @app.get("/api/email-sources")
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

    @app.post("/api/jobs")
    def api_jobs_create():
        """启动批量注册：body {count, workers, email_source}。"""
        data = request.get_json(silent=True) or {}
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
            jobs = svc.submit_registration(count=count, workers=workers)
            return jsonify({
                "ok": True,
                "submitted": len(jobs),
                "jobs": jobs,
                "warning": f"手动 OTP 模式：将使用 {reg_email}；验证码请在任务页提交",
                "workers": workers,
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
        jobs = svc.submit_registration(count=count, email_source=selected_source, workers=workers)
        return jsonify({
            "ok": True,
            "submitted": len(jobs),
            "jobs": jobs,
            "warning": warning,
            "workers": workers,
            "email_source": selected_source,
        })

    @app.get("/api/manual-otp/waiting")
    def api_manual_otp_waiting():
        """列出当前正在等待手动验证码的邮箱。"""
        from core.manual_otp import list_waiting
        return jsonify({"ok": True, "waiting": list_waiting()})

    @app.post("/api/manual-otp")
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

    @app.post("/api/jobs/cancel-pending")
    def api_jobs_cancel_pending():
        """取消所有还在排队（status=pending）的任务。已在 running 的不动。"""
        cancelled = svc.cancel_pending_jobs()
        return jsonify({"ok": True, "cancelled": cancelled})

    @app.post("/api/jobs/batches/<batch_id>/cancel")
    def api_batch_jobs_cancel(batch_id: str):
        """只取消指定批次中尚未启动的任务。"""
        cancelled = svc.cancel_pending_jobs(batch_id=batch_id)
        return jsonify({"ok": True, "batch_id": batch_id, "cancelled": cancelled})

    @app.post("/api/jobs/batches/<batch_id>/stop")
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

    @app.post("/api/jobs/<int:job_id>/stop")
    def api_job_stop(job_id: int):
        """手动停止单个注册任务。pending 取消；running 发送停止信号。"""
        result = svc.request_stop_job(job_id)
        if not result.get("ok"):
            return jsonify({"ok": False, "error": result.get("error") or "停止失败"}), int(result.get("status") or 400)
        return jsonify(result)

    @app.post("/api/jobs/<int:job_id>/retry")
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

    @app.post("/api/jobs/retry-bulk")
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

    @app.post("/api/jobs/<int:job_id>/delete")
    def api_job_delete(job_id: int):
        """删除一个任务记录。运行中的任务不允许删除；排队任务删除后执行前会自动跳过。"""
        deleted, skipped = db.delete_jobs([job_id], delete_log=True, allow_running=False)
        if not deleted:
            reason = skipped[0]["reason"] if skipped else "任务不存在"
            status_code = 409 if "运行中" in reason else 404
            return jsonify({"ok": False, "error": reason}), status_code
        return jsonify({"ok": True, "deleted": True})

    @app.post("/api/jobs/delete-bulk")
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

        deleted_rows, skipped = db.delete_jobs(valid_ids, delete_log=True, allow_running=False)
        skipped = invalid + skipped
        deleted = [int(row["id"]) for row in deleted_rows]
        return jsonify({"ok": True, "deleted": deleted, "deleted_count": len(deleted), "skipped": skipped})

    @app.get("/api/jobs/<int:job_id>/log")
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

    # ----------------------------------------------------------
    # RoxyBrowser 辅助接口
    # ----------------------------------------------------------
    @app.get("/api/roxy/workspaces")
    def api_roxy_workspaces():
        try:
            from core.roxybrowser_client import RoxyBrowserClient
            result = RoxyBrowserClient().list_workspaces()
            return jsonify(result)
        except Exception as exc:
            logger.exception("获取 Roxy 团队/工作区失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

    @app.post("/api/proxy-provider/test")
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

    @app.post("/api/icloud-hme/test")
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

    @app.post("/api/email-butler/test-connection")
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

    @app.get("/api/email-butler/leases")
    def api_email_butler_leases():
        """列出当前 WebUI 进程持有的 Email Butler 租约。"""
        from core.email_butler_client import active_mailbox_leases
        return jsonify({"ok": True, "items": active_mailbox_leases()})

    @app.post("/api/email-butler/leases")
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

    @app.post("/api/email-butler/leases/release")
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

    # ----------------------------------------------------------
    # 配置读写
    # ----------------------------------------------------------
    @app.get("/api/config")
    def api_config_get():
        return jsonify(config_editor.get_config())

    @app.post("/api/cloudmail/gen-token")
    def api_cloudmail_gen_token():
        """手动生成 CloudMail Authorization Token，并把本次填写的 CloudMail 配置一并写入 .env。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.cloudmail_client import gen_token
            from config.env_loader import write_env_values

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
            written = write_env_values(updates)
            try:
                import config as _config_pkg
                _config_pkg.reload_all()
            except Exception:
                logger.exception("CloudMail Token 写入后热加载失败")
            return jsonify({
                "ok": True,
                "token": token,
                "written": written,
                "message": "CloudMail Token 已生成，且当前 CloudMail 配置已保存",
            })
        except Exception as exc:
            logger.exception("生成 CloudMail Token 失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @app.post("/api/cloudmail/domains")
    def api_cloudmail_domains():
        """从 CloudMail 平台获取域名列表，并可写入 .env 作为本地缓存。"""
        data = request.get_json(silent=True) or {}
        try:
            from core.cloudmail_client import fetch_domains
            from config.env_loader import write_env_values

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
            if updates:
                write_env_values(updates)
                import config as _config_pkg
                _config_pkg.reload_all()

            domains = fetch_domains(force=True)
            written = write_env_values({"CLOUDMAIL_DOMAINS": "\n".join(domains)})
            try:
                import config as _config_pkg
                _config_pkg.reload_all()
            except Exception:
                logger.exception("CloudMail 域名写入后热加载失败")
            return jsonify({
                "ok": True,
                "domains": domains,
                "count": len(domains),
                "written": written,
                "message": f"已获取 {len(domains)} 个 CloudMail 可用域名并保存",
            })
        except Exception as exc:
            logger.exception("获取 CloudMail 域名失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 400

    @app.post("/api/config")
    def api_config_set():
        data = request.get_json(silent=True) or {}
        updates = data.get("updates") if isinstance(data.get("updates"), dict) else data
        if not isinstance(updates, dict) or not updates:
            return jsonify({"ok": False, "error": "无更新内容"}), 400
        try:
            result = config_editor.update_config(updates)
        except Exception as exc:
            logger.exception("配置写入失败")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500

        # 写盘成功后立即热加载所有 config 子模块，让运行时代码看到新值。
        reload_ok = True
        reload_err = ""
        try:
            import config as _config_pkg
            _config_pkg.reload_all()
        except Exception as exc:
            reload_ok = False
            reload_err = f"{type(exc).__name__}: {exc}"
            logger.exception("配置热加载失败")

        return jsonify({
            "ok": True,
            "updated": result["updated"],
            "ignored": result["ignored"],
            "reloaded": reload_ok,
            "note": (
                "✅ 已保存并热加载，新值立即生效"
                if reload_ok
                else f"⚠️ 已写入文件但热加载失败（{reload_err}），需重启 Web 服务才能生效"
            ),
        })

    return app
