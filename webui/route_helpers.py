# -*- coding: utf-8 -*-
"""Shared, side-effect-free helpers used by WebUI route groups."""
from __future__ import annotations

from flask import jsonify, request

from core import db
from core.auth_fingerprint import clean_safe_fingerprint_summary
from core.plus_promotion import promotion_kind_from_record
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
    promotion = filters.get("promotion") or filters.get("trial")
    promotion = {"eligible": "free_trial", "ineligible": "none"}.get(promotion, promotion)
    if promotion and _account_promotion_value(row) != promotion:
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


def _account_promotion_value(row: dict) -> str:
    """返回账号列表筛选使用的标准 Plus 优惠状态。"""
    status = str(row.get("plan_check_status") or "").lower()
    if status in {"queued", "running"}:
        return "pending"

    plan = str(row.get("current_plan_type") or row.get("plan_type") or "").strip().lower()
    if plan and plan != "free":
        return "not_applicable"
    if not plan:
        return "pending"

    if status == "failed":
        return promotion_kind_from_record(row) if row.get("plan_last_success_at") else "failed"
    if status != "success" and row.get("plan_check_ok") is not True:
        return "pending"
    return promotion_kind_from_record(row)


def _compact_fingerprint_summary(row: dict) -> dict:
    """把最近认证指纹压缩成详情抽屉需要的安全摘要。"""
    raw = row.get("last_auth_fingerprint")
    if isinstance(raw, str):
        try:
            import json

            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    safe = clean_safe_fingerprint_summary(raw)
    if not safe:
        return {}

    browser = "/".join(
        str(item) for item in (
            safe.get("browser_family"),
            safe.get("browser_version"),
            safe.get("browser_os"),
        ) if item
    )
    width = safe.get("screen_width")
    height = safe.get("screen_height")
    screen = f"{width}x{height}" if width is not None and height is not None else ""
    hardware = " / ".join(
        str(item) for item in (
            f"{safe['hardware_concurrency']} 核" if safe.get("hardware_concurrency") is not None else "",
            f"{safe['device_memory']} GB" if safe.get("device_memory") is not None else "",
        ) if item
    )
    compact = {
        "source": safe.get("source"),
        "profile_ref": safe.get("profile_ref"),
        "browser": browser,
        "screen": screen,
        "device_pixel_ratio": safe.get("device_pixel_ratio"),
        "hardware": hardware,
        "language": safe.get("navigator_language"),
        "timezone": safe.get("timezone_iana"),
        "geo_country": safe.get("geo_country"),
        "proxy_mode": safe.get("proxy_mode"),
        "observed_at": safe.get("observed_at"),
    }
    return {key: value for key, value in compact.items() if value not in (None, "")}


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
        "email_invalid": row.get("email_invalid") is True,
    }
    for key in ("email_invalid_reason", "email_invalid_at", "email_invalid_source"):
        out[key] = row.get(key) if out["email_invalid"] else None

    # 这些是列表固定列直接展示字段。
    for key in (
        "user_name", "email_source", "registration_driver", "note", "archived", "created_at", "updated_at",
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
        "plus_promo_eligible", "plus_promo_kind", "plus_discount_eligible",
        "plus_promo_campaign_id", "plus_promo_title", "plus_promo_summary",
        "plus_promo_discount_percentage", "plus_promo_duration_num_periods",
        "plus_promo_duration_period", "plus_promo_promotion_type",
        "plus_promo_promotion_type_label", "plus_trial_campaign_id", "plus_trial_title",
        "plus_trial_discount_percentage", "plus_trial_duration_num_periods",
        "plus_trial_duration_period", "plus_trial_promotion_type_label",
        "account_promotions", "promotion_query_snapshot", "plan_check_countries", "plan_check_partial",
        # 额度窗口快照（来自 ChatGPT /wham/usage，不返回原始响应）。
        "quota_status", "quota_checked_at", "quota_http_status", "quota_error",
        "quota_type", "quota_windows", "quota_last_success_at",
        "token_expired", "token_expires_at", "account_status_reason", "account_status_at",
        # 查活状态。
        "live_check_status", "live_check_error", "live_check_http_status", "live_checked_at",
        # 最近一次认证的低敏状态；完整认证上下文不进入列表。
        "last_auth_method", "last_auth_fallback_used",
        # 提链成功/失败时才需要。
        "extract_link_status", "extract_link_ok", "extract_link_type", "extract_link_message", "extract_link_error",
        "extract_link_failed_types", "extract_link_last_failed_type", "extract_link_last_failed_at",
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
    if "plan_check_country_results" in row:
        from core.plan_check_countries import public_country_results
        out["plan_check_country_results"] = public_country_results(row["plan_check_country_results"])
    from core.plan_check_countries import promotion_country_from_row
    promotion_country = promotion_country_from_row(row)
    if promotion_country:
        out["plan_promotion_country"] = promotion_country
    fingerprint_summary = _compact_fingerprint_summary(row)
    if fingerprint_summary:
        out["fingerprint_summary"] = fingerprint_summary
    promo_kind = promotion_kind_from_record(row)
    out["plus_promo_kind"] = promo_kind
    out["plus_promo_eligible"] = promo_kind in {"free_trial", "discount", "other_promo"}
    out["plus_trial_eligible"] = promo_kind == "free_trial"
    out["plus_discount_eligible"] = promo_kind == "discount"
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
    raise ValueError("field 仅支持 access_token/copy_line/account_password/account_password_line/totp_secret/chatgpt_session")


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


def _compact_job_for_list(row: dict, *, include_progress: bool = True, summarize_routes: bool = False) -> dict:
    """注册任务列表轻量对象：只返回表格展示和按钮判断需要的字段。"""
    out = {
        "id": row.get("id"),
        "status": row.get("status"),
    }
    config_snapshot = row.get("config_snapshot")
    if not isinstance(config_snapshot, dict):
        row_data = row.get("data")
        config_snapshot = row_data.get("config_snapshot") if isinstance(row_data, dict) else None
    registration_driver = (
        config_snapshot.get("registration_driver")
        if isinstance(config_snapshot, dict)
        else row.get("registration_driver")
    )
    if registration_driver:
        out["registration_driver"] = str(registration_driver)
    for key in (
        "parent_job_id", "root_job_id", "retry_attempt", "email", "started_at", "completed_at",
        "email_source",
        "display_status", "retryable", "retry_action", "retry_label",
        "manual_otp_required", "proxy_provider", "proxy_status", "proxy_endpoint",
        "proxy_exit_ip", "proxy_region", "proxy_acquired_at", "proxy_expires_at",
        "batch_id", "batch_index", "batch_size", "batch_workers",
        "progress_stage", "progress_updated_at", "progress_steps",
        "operation_task_id", "operation_run_id", "progress",
        "route_attempt_no", "route_attempts", "internal_retry_count",
        "internal_retry_kind", "internal_retry_last_reason",
        "legacy_retry_timing",
        "otp_evidence", "otp_request_count", "otp_failure_code",
        "debug_enabled", "debug_state", "debug_hold_until", "debug_pause_reason",
        "debug_capture_summary",
        "failure_diagnostics_state", "failure_diagnostics_category",
        "failure_diagnostics_failure_reason", "failure_diagnostics_summary",
    ):
        if not include_progress and key in {"progress", "progress_steps", "route_attempts"}:
            continue
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
    if (
        str(row.get("status") or "") == "success"
        and "代理线路瞬时失败，准备换线重试" in err
        and not int(row.get("internal_retry_count") or 0)
    ):
        # 兼容结构化自动重试字段上线前的成功任务（例如 #749）。
        out["internal_retry_count"] = 1
        out["internal_retry_kind"] = "proxy_rotation"
        out["internal_retry_last_reason"] = err[:300]
        out["warning_summary"] = err[:300]
        # Older rows only kept one timestamp per stage and overwrote the end
        # after route retry.  Those durations cannot be repaired reliably.
        out["legacy_retry_timing"] = True
        out.pop("error_message", None)
        out.pop("error_info", None)
    # 旧来源尚未映射到 operation Run 时，也使用同一个证据投影器。
    if include_progress and not out.get("progress"):
        from core.task_progress import build_progress_snapshot

        out["progress"] = build_progress_snapshot(
            0, int(row.get("id") or 0), str(row.get("job_type") or "registration"),
            {**row, "error_message": err}, [],
        )
    if summarize_routes and isinstance(out.get("progress"), dict):
        # 已有统一主步骤时不再重复发送旧步骤；旧来源的 fallback 仍保留原始证据。
        source_progress = row.get("progress")
        if isinstance(source_progress, dict) and source_progress.get("main_steps"):
            out.pop("progress_steps", None)
        progress = out["progress"]
        out["progress"] = {
            **progress,
            "routes": [{key: value for key, value in route.items() if key != "steps"}
                       for route in progress.get("routes") or []],
        }
    return out


def _job_status_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    counts["active"] = sum(int(counts.get(s, 0) or 0) for s in ("pending", "running", "stopping"))
    return counts


def _progress_batch_slots(rows: list[dict]) -> tuple[str, dict[int, dict], dict[int, list[dict]]]:
    """按根任务归并重试，并确定实际展示的尝试；查询快照和渲染共用同一规则。"""
    roots = {
        int(row.get("id") or 0): row
        for row in rows
        if not row.get("root_job_id")
    }

    def effective_batch_id(row: dict) -> str:
        if row.get("effective_batch_id"):
            return str(row.get("effective_batch_id") or "")
        root = roots.get(int(row.get("root_job_id") or row.get("id") or 0), row)
        return str(root.get("batch_id") or row.get("batch_id") or "")

    latest = next((row for row in rows if effective_batch_id(row)), None)
    if latest is None:
        return "", roots, {}
    batch_id = effective_batch_id(latest)
    batch_rows = [row for row in rows if effective_batch_id(row) == batch_id]

    slot_rows: dict[int, list[dict]] = {}
    for row in batch_rows:
        root_id = int(row.get("root_job_id") or row.get("id") or 0)
        slot_rows.setdefault(root_id, []).append(row)
    for attempts in slot_rows.values():
        attempts.sort(key=lambda row: (int(row.get("retry_attempt") or 0), int(row.get("id") or 0)))
    return batch_id, roots, slot_rows


def _current_slot_attempt(attempts: list[dict]) -> dict:
    active = [row for row in attempts if str(row.get("status") or "") in {"pending", "running", "stopping"}]
    return active[-1] if active else attempts[-1]


def _current_progress_jobs(rows: list[dict]) -> list[dict]:
    return [_current_slot_attempt(attempts) for attempts in _progress_batch_slots(rows)[2].values()]


def _latest_progress_batch(rows: list[dict], *, summarize_routes: bool = False) -> dict | None:
    """构造批次 TaskSlot 进度；人工重试不重复增加批次任务数。"""
    batch_id, roots, slot_rows = _progress_batch_slots(rows)
    if not batch_id:
        return None
    batch_rows = [row for attempts in slot_rows.values() for row in attempts]
    latest = batch_rows[0]
    selected_rows: list[dict] = []
    items: list[dict] = []
    for root_id, attempts in slot_rows.items():
        current = _current_slot_attempt(attempts)
        root = roots.get(root_id) or attempts[0]
        selected_rows.append(current)
        compact = _compact_job_for_list(current, summarize_routes=summarize_routes)
        attempt_items = []
        for row in attempts:
            attempt_compact = _compact_job_for_list(row, include_progress=False)
            attempt_items.append({
                "id": int(row.get("id") or 0),
                "retry_attempt": int(row.get("retry_attempt") or 0),
                "job_type": str(row.get("job_type") or "registration"),
                "status": str(row.get("status") or "pending"),
                "started_at": row.get("started_at"),
                "completed_at": row.get("completed_at"),
                "error_message": str(attempt_compact.get("error_message") or "")[:240] or None,
                "error_info": attempt_compact.get("error_info") or {},
                "warning_summary": str(attempt_compact.get("warning_summary") or "")[:240] or None,
                "internal_retry_count": int(attempt_compact.get("internal_retry_count") or 0),
            })
        compact.update({
            "root_job_id": root_id,
            "batch_id": batch_id,
            "batch_index": int(root.get("batch_index") or current.get("batch_index") or 1),
            "batch_size": int(root.get("batch_size") or len(slot_rows)),
            "retry_count": max(int(row.get("retry_attempt") or 0) for row in attempts),
            "attempts": attempt_items,
        })
        items.append(compact)

    items.sort(key=lambda row: (int(row.get("batch_index") or 0), int(row.get("root_job_id") or 0)))
    selected_rows.sort(key=lambda row: int((roots.get(int(row.get("root_job_id") or row.get("id") or 0)) or row).get("batch_index") or 0))
    counts = _job_status_counts(selected_rows)
    stage_counts: dict[str, dict] = {}
    failure_counts: dict[str, dict] = {}
    for item in items:
        progress = item.get("progress") or {}
        for location, target in ((progress.get("current"), stage_counts), (progress.get("failure"), failure_counts)):
            if not location:
                continue
            key = str(location.get("step_id") or "unknown")
            bucket = target.setdefault(key, {"step_id": key, "label": location.get("label") or "位置待确认", "count": 0})
            bucket["count"] += 1
    all_terminal = all(str(row.get("status") or "") not in {"pending", "running", "stopping"} for row in selected_rows)
    return {
        "batch_id": batch_id,
        "total": len(slot_rows),
        "workers": int(latest.get("batch_workers") or 1),
        "created_at": min((str(row.get("created_at") or "") for row in batch_rows), default=""),
        "started_at": min((str(row.get("started_at") or "") for row in batch_rows if row.get("started_at")), default=""),
        "completed_at": max((str(row.get("completed_at") or "") for row in selected_rows if row.get("completed_at")), default="") if all_terminal else "",
        "status_counts": counts,
        "current_stage_counts": list(stage_counts.values()),
        "failure_stage_counts": list(failure_counts.values()),
        "stages": [
            {"key": key, "label": "本次总耗时" if key == "complete" else label}
            for key, label in db.JOB_PROGRESS_STAGES
        ],
        "items": items,
    }
