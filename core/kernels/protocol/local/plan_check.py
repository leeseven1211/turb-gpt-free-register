"""Pure HTTP requests and response projections for local plan/quota checks."""

from __future__ import annotations
import base64
import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from core.accounts.plans.promotion import DISCOUNT, FREE_TRIAL, parse_account_promotions, primary_plan_promotion
from core.auth.protocol.session import BrowserSession

logger = logging.getLogger("core.chatgpt_plan")

ACCOUNTS_CHECK_PATH = "/backend-api/accounts/check/v4-2023-04-27"

USAGE_PATH = "/backend-api/wham/usage"

_QUOTA_WINDOW_LABELS = {
    "five_hour": "5小时限额",
    "weekly": "周限额",
    "monthly": "月限额",
    "daily": "日限额",
    "custom": "自定义窗口",
}

_QUOTA_KIND_ORDER = {"five_hour": 0, "daily": 1, "weekly": 2, "monthly": 3, "custom": 4}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_token(token: str) -> str:
    token = (token or "").strip().strip('"').strip("'")
    if token.lower().startswith("authorization:"):
        token = token.split(":", 1)[1].strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def decode_jwt_payload_unverified(token: str, *, normalize_token=normalize_token) -> dict:
    """仅本地解析 JWT payload，不校验签名。"""
    token = normalize_token(token)
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return {}


def token_claims(token: str, *, decode_jwt_payload_unverified=decode_jwt_payload_unverified) -> dict:
    payload = decode_jwt_payload_unverified(token)
    auth = payload.get("https://api.openai.com/auth") or {}
    profile = payload.get("https://api.openai.com/profile") or {}
    exp = payload.get("exp")
    exp_iso = None
    expired = None
    if isinstance(exp, (int, float)):
        exp_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        expired = datetime.now(tz=timezone.utc).timestamp() >= float(exp)
    return {
        "payload": payload,
        "email": profile.get("email"),
        "user_name": profile.get("name"),
        "user_id": auth.get("chatgpt_user_id") or auth.get("user_id"),
        "account_id": auth.get("chatgpt_account_id"),
        "claim_plan_type": auth.get("chatgpt_plan_type"),
        "exp": exp,
        "token_expires_at": exp_iso,
        "token_expired": expired,
    }


def _common_headers(
    env: BrowserSession,
    token: str,
    claims: dict | None = None,
    *,
    normalize_token=normalize_token,
    token_claims=token_claims,
) -> dict[str, str]:
    """Build the same frontend API context used by protocol 2FA requests."""
    headers = env.get_chatgpt_headers(referer="https://chatgpt.com/")
    claims = claims or token_claims(token)
    headers.update(
        {
            "authorization": f"Bearer {normalize_token(token)}",
            "x-openai-target-path": ACCOUNTS_CHECK_PATH,
            "x-openai-target-route": "/backend-api/accounts/check/{version}",
        }
    )
    account_id = str(claims.get("account_id") or "").strip()
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def _quota_headers(
    env: BrowserSession,
    token: str,
    claims: dict | None = None,
    *,
    normalize_token=normalize_token,
    token_claims=token_claims,
) -> dict[str, str]:
    """Build the Codex-style headers used by ChatGPT's ``/wham/usage`` API.

    The header combination follows sub2api's OpenAI quota implementation.  The
    response is only used for a sanitized local snapshot; the upstream payload
    is never persisted or returned to the account list.
    """
    headers = env.get_chatgpt_headers(referer="https://chatgpt.com/")
    claims = claims or token_claims(token)
    headers.update(
        {
            "authorization": f"Bearer {normalize_token(token)}",
            "openai-beta": "codex-1",
            "oai-language": "zh-CN",
            "originator": "Codex Desktop",
            "accept": "application/json",
            "sec-fetch-site": "none",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-dest": "empty",
            "priority": "u=4, i",
            "x-openai-target-path": USAGE_PATH,
            "x-openai-target-route": "/backend-api/wham/usage",
        }
    )
    account_id = str(claims.get("account_id") or "").strip()
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def classify_quota_window(seconds: Any) -> tuple[str, str]:
    """Classify an upstream window by duration, without guessing from plan type."""
    try:
        value = int(float(seconds))
    except (TypeError, ValueError, OverflowError):
        return "custom", _QUOTA_WINDOW_LABELS["custom"]
    if value <= 0:
        return "custom", _QUOTA_WINDOW_LABELS["custom"]
    if value >= 25 * 24 * 60 * 60:
        kind = "monthly"
    elif value >= 6 * 24 * 60 * 60:
        kind = "weekly"
    elif value <= 6 * 60 * 60:
        kind = "five_hour"
    elif value <= 2 * 24 * 60 * 60:
        kind = "daily"
    else:
        kind = "custom"
    return kind, _QUOTA_WINDOW_LABELS[kind]


def _quota_number(value: Any, *, integer: bool = False) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return int(number) if integer else number


def _parse_quota_rate_limit(
    rate_limit: Any, *, _quota_number=_quota_number, classify_quota_window=classify_quota_window
) -> list[dict]:
    if not isinstance(rate_limit, dict):
        return []
    windows = []
    for slot in ("primary_window", "secondary_window"):
        window = rate_limit.get(slot)
        if not isinstance(window, dict):
            continue
        limit_seconds = _quota_number(
            window.get("limit_window_seconds", window.get("limitWindowSeconds")),
            integer=True,
        )
        if not limit_seconds:
            continue
        kind, label = classify_quota_window(limit_seconds)
        used = _quota_number(window.get("used_percent", window.get("usedPercent")))
        if used is not None:
            used = max(0.0, min(100.0, float(used)))
        reset_after = _quota_number(
            window.get("reset_after_seconds", window.get("resetAfterSeconds")),
            integer=True,
        )
        reset_at = _quota_number(window.get("reset_at", window.get("resetAt")), integer=True)
        if reset_at and reset_at > 10**12:
            reset_at //= 1000
        item = {
            "slot": slot.removesuffix("_window"),
            "kind": kind,
            "label": label,
            "window_seconds": limit_seconds,
            "window_minutes": round(limit_seconds / 60),
            "used_percent": round(used, 2) if used is not None else None,
            "remaining_percent": round(100.0 - used, 2) if used is not None else None,
            "reset_after_seconds": reset_after,
            "reset_at": reset_at,
            "allowed": bool(rate_limit.get("allowed")) if "allowed" in rate_limit else None,
            "limit_reached": bool(rate_limit.get("limit_reached")) if "limit_reached" in rate_limit else None,
        }
        windows.append({key: value for key, value in item.items() if value is not None})
    return windows


def parse_quota_usage(data: dict, *, _parse_quota_rate_limit=_parse_quota_rate_limit, now_iso=now_iso) -> dict:
    """Project ``/wham/usage`` into safe, UI-oriented quota metadata."""
    windows = _parse_quota_rate_limit((data or {}).get("rate_limit")) if isinstance(data, dict) else []
    # Some accounts expose only a feature-specific rate limit.  Use it as a
    # fallback, but do not mix it with the account-wide windows above.
    if not windows and isinstance(data, dict):
        for extra in data.get("additional_rate_limits") or []:
            if not isinstance(extra, dict):
                continue
            windows = _parse_quota_rate_limit(
                extra.get("rate_limit"),
            )
            if windows:
                break
    windows.sort(key=lambda item: (_QUOTA_KIND_ORDER.get(item.get("kind"), 99), item.get("window_seconds", 0)))
    kinds = []
    for item in windows:
        label = item.get("label") or _QUOTA_WINDOW_LABELS["custom"]
        if label not in kinds:
            kinds.append(label)
    return {
        "quota_status": "success",
        "quota_checked_at": now_iso(),
        "quota_type": " / ".join(kinds),
        "quota_windows": windows,
    }


def _remaining_request_timeout(timeout: float, deadline_at: float | None, *, clock=time) -> float:
    """每次请求使用同一绝对期限扣除此前事务、解析及请求耗时。"""
    if deadline_at is None:
        return timeout
    remaining = deadline_at - clock.time()
    if remaining <= 0:
        raise TimeoutError("国家查询总期限已到")
    return min(timeout, remaining)


def _query_account_quota(
    env: BrowserSession,
    token: str,
    claims: dict,
    timeout: float,
    deadline_at: float | None = None,
    *,
    _quota_headers=_quota_headers,
    _remaining_request_timeout=_remaining_request_timeout,
    now_iso=now_iso,
    parse_quota_usage=parse_quota_usage,
) -> dict:
    """Fetch quota metadata; quota errors are deliberately non-fatal to plan checks."""
    checked_at = now_iso()
    try:
        response = env.get(
            f"https://chatgpt.com{USAGE_PATH}",
            headers=_quota_headers(env, token, claims),
            allow_redirects=False,
            timeout=_remaining_request_timeout(timeout, deadline_at),
        )
        http_status = int(response.status_code)
        if not (200 <= http_status < 300):
            return {
                "quota_status": "failed",
                "quota_checked_at": checked_at,
                "quota_http_status": http_status,
                "quota_error": "额度查询 AT 已过期/失效" if http_status == 401 else f"额度查询 HTTP {http_status}",
            }
        response_text = response.text or ""
        try:
            data: Any = response.json()
        except Exception:
            data = json.loads(response_text) if response_text.strip().startswith(("{", "[")) else None
        if not isinstance(data, dict):
            return {
                "quota_status": "failed",
                "quota_checked_at": checked_at,
                "quota_http_status": http_status,
                "quota_error": "额度响应不是 JSON 对象",
            }
        parsed = parse_quota_usage(data)
        parsed["quota_checked_at"] = checked_at
        parsed["quota_http_status"] = http_status
        return parsed
    except Exception as exc:
        logger.debug("额度查询失败: %s", type(exc).__name__, exc_info=True)
        return {
            "quota_status": "failed",
            "quota_checked_at": checked_at,
            "quota_http_status": None,
            "quota_error": f"额度查询网络错误: {type(exc).__name__}",
        }


def parse_accounts_check(data: dict, *, token: str = "", now_iso=now_iso, token_claims=token_claims) -> dict:
    """从 accounts/check 响应提取套餐、Go / Plus / Team 优惠与有效期。"""
    claims = token_claims(token) if token else {}
    claim_account_id = claims.get("account_id")
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(accounts, dict):
        raise ValueError("响应缺少 accounts 对象")

    item = None
    account_key = None
    if claim_account_id and isinstance(accounts.get(claim_account_id), dict):
        item = accounts.get(claim_account_id)
        account_key = claim_account_id
    elif isinstance(accounts.get("default"), dict):
        item = accounts.get("default")
        account = item.get("account") or {}
        account_key = account.get("account_id") or "default"
    else:
        for k, v in accounts.items():
            if k != "default" and isinstance(v, dict):
                item = v
                account_key = k
                break
    if not isinstance(item, dict):
        raise ValueError("未找到可解析的账号条目")

    account = item.get("account") or {}
    entitlement = item.get("entitlement") or {}
    last_sub = item.get("last_active_subscription") or {}
    plan_type = account.get("plan_type") or claims.get("claim_plan_type") or ""
    subscription_plan = entitlement.get("subscription_plan") or ""
    has_active_subscription = bool(entitlement.get("has_active_subscription"))
    is_free = str(plan_type).lower() == "free" or str(subscription_plan).lower() == "chatgptfreeplan"
    account_promotions, promotion_query_snapshot = parse_account_promotions(
        item.get("eligible_promo_campaigns"),
        is_free=is_free,
    )
    plus_promotion = primary_plan_promotion(account_promotions, "plus")
    plus_promo_kind = plus_promotion["kind"]
    plus_promo_eligible = plus_promotion["eligible"]
    plus_trial_eligible = plus_promo_kind == FREE_TRIAL
    plus_discount_eligible = plus_promo_kind == DISCOUNT
    promo_percentage = plus_promotion["discount_percentage"]

    offers = (item.get("eligible_offers") or {}).get("offers") or []
    eligible_offer_ids = [o.get("id") for o in offers if isinstance(o, dict) and o.get("id")]

    result = {
        "ok": True,
        "checked_at": now_iso(),
        "account_id": account.get("account_id") or account_key or claim_account_id,
        "account_user_role": account.get("account_user_role"),
        "current_plan_type": plan_type,
        "subscription_plan": subscription_plan,
        "has_active_subscription": has_active_subscription,
        "is_active_subscription_gratis": bool(entitlement.get("is_active_subscription_gratis")),
        "expires_at": entitlement.get("expires_at"),
        "renews_at": entitlement.get("renews_at"),
        "cancels_at": entitlement.get("cancels_at"),
        "billing_period": entitlement.get("billing_period"),
        "billing_currency": entitlement.get("billing_currency"),
        "is_delinquent": bool(entitlement.get("is_delinquent")),
        "discount_type": (entitlement.get("discount") or {}).get("discount_type"),
        "discount_amount": (entitlement.get("discount") or {}).get("amount"),
        "discount_duration_num_periods": (entitlement.get("discount") or {}).get("duration_num_periods"),
        "discount_expires_at": (entitlement.get("discount") or {}).get("discount_expires_at"),
        "discount_cancellation_policy": (entitlement.get("discount") or {}).get("cancellation_policy"),
        "discount_promo_campaign_id": (entitlement.get("discount") or {}).get("promo_campaign_id"),
        "last_purchase_origin_platform": last_sub.get("purchase_origin_platform"),
        "last_will_renew": bool(last_sub.get("will_renew")),
        "account_promotions": account_promotions,
        "promotion_query_snapshot": promotion_query_snapshot,
        "plus_promo_eligible": plus_promo_eligible,
        "plus_promo_kind": plus_promo_kind,
        "plus_discount_eligible": plus_discount_eligible,
        "plus_promo_campaign_id": plus_promotion["campaign_id"],
        "plus_promo_title": plus_promotion["title"],
        "plus_promo_summary": plus_promotion["summary"],
        "plus_promo_discount_percentage": promo_percentage,
        "plus_promo_duration_num_periods": plus_promotion["duration_num_periods"],
        "plus_promo_duration_period": plus_promotion["duration_period"],
        "plus_promo_promotion_type": plus_promotion["promotion_type"],
        "plus_promo_promotion_type_label": plus_promotion["promotion_type_label"],
        # 旧字段保留给历史调用方；其中 eligible 从现在起只代表真正免费试用。
        "plus_trial_eligible": plus_trial_eligible,
        "plus_trial_campaign_id": plus_promotion["campaign_id"],
        "plus_trial_title": plus_promotion["title"],
        "plus_trial_summary": plus_promotion["summary"],
        "plus_trial_discount_percentage": promo_percentage,
        "plus_trial_duration_num_periods": plus_promotion["duration_num_periods"],
        "plus_trial_duration_period": plus_promotion["duration_period"],
        "plus_trial_promotion_type_label": plus_promotion["promotion_type_label"],
        "eligible_offer_ids": eligible_offer_ids,
        "features_count": len(item.get("features") or []),
        "can_access_with_session": bool(item.get("can_access_with_session")),
        "raw_account_plan_type": account.get("plan_type"),
    }
    result.update({k: v for k, v in claims.items() if k != "payload" and v is not None})
    return result


def request_accounts_check(env, *, headers, timezone_offset_min="-", timeout):
    """Issue one existing-token probe using the already selected HTTP session.

    Header and timeout suppliers retain their old evaluation order after the
    session timezone lookup. No lease, retry, account lookup or refresh occurs.
    """
    request_timezone = timezone_offset_min
    if str(request_timezone or "").strip() == "-":
        request_timezone = env.js_timezone_offset_min()
    url = f"https://chatgpt.com{ACCOUNTS_CHECK_PATH}?timezone_offset_min={quote(str(request_timezone))}"
    return env.get(
        url,
        headers=headers() if callable(headers) else headers,
        allow_redirects=False,
        timeout=timeout() if callable(timeout) else timeout,
    )
