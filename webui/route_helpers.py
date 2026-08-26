# -*- coding: utf-8 -*-
"""Shared, side-effect-free helpers used by WebUI route groups."""
from __future__ import annotations

from flask import jsonify, request

from core import db
from core.task_errors import classify_task_error

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
