# -*- coding: utf-8 -*-
"""Email Butler `/v1` 通用邮箱 API 客户端。"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from config import email as _email_cfg
from core.otp_utils import extract_otp

logger = logging.getLogger(__name__)

_OTP_RE = re.compile(r"^\d{6}$")


class EmailButlerClientError(RuntimeError):
    """Email Butler 连接、租用或收信失败。"""


@dataclass
class EmailButlerAccount:
    email: str
    mailbox_id: str
    lease_id: str = ""
    leased_until: str = ""
    provider: str = ""
    mailbox_email: str = ""


_CONTEXT_CACHE: dict[str, EmailButlerAccount] = {}


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _api_base(override: str | None = None) -> str:
    base = str(override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_BASE", "") or "").strip()
    if not base:
        raise EmailButlerClientError("Email Butler API 地址未配置，请填写 /v1 根地址。")
    return base.rstrip("/")


def _api_key(override: str | None = None) -> str:
    key = str(override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_KEY", "") or "").strip()
    if not key:
        raise EmailButlerClientError("Email Butler API Key 未配置。")
    return key


def _request_timeout() -> int:
    return max(3, int(getattr(_email_cfg, "EMAIL_BUTLER_REQUEST_TIMEOUT", 20) or 20))


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
) -> dict:
    try:
        response = requests.request(
            method,
            _api_base(api_base) + path,
            params=params,
            json=json,
            headers={
                "Authorization": f"Bearer {_api_key(api_key)}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=_request_timeout(),
        )
    except requests.RequestException as exc:
        raise EmailButlerClientError(
            f"Email Butler 请求失败 ({path}): {type(exc).__name__}: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise EmailButlerClientError(
            f"Email Butler 响应不是 JSON ({path}): HTTP {response.status_code}"
        ) from exc

    if response.status_code == 401:
        raise EmailButlerClientError("Email Butler API Key 非法、已停用或已轮换")
    if response.status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else str(payload)
        raise EmailButlerClientError(
            f"Email Butler 请求失败 ({path}): HTTP {response.status_code}; {str(message)[:220]}"
        )
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 200:
        raise EmailButlerClientError(f"Email Butler 响应异常 ({path}): {payload}")
    return payload


def test_connection(*, api_base: str | None = None, api_key: str | None = None) -> dict:
    """调用 `/me` 验证 URL、Key、客户端策略和能力。"""
    payload = _request("GET", "/me", api_base=api_base, api_key=api_key)
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), list) else []
    required = {"mailboxes.create", "mailboxes.messages", "mailboxes.release", "signals.scan"}
    missing = sorted(required.difference(str(item) for item in capabilities))
    if missing:
        raise EmailButlerClientError(f"Email Butler 缺少必要能力: {', '.join(missing)}")
    return {
        "ok": True,
        "name": str(payload.get("name") or ""),
        "consumer": str(policy.get("consumer") or ""),
        "service": str(policy.get("service") or ""),
        "capabilities": capabilities,
    }


def scan_openai_deactivation(email: str, *, lookback_days: int = 120) -> dict:
    """Scan one Butler-managed identity for a high-confidence OpenAI deactivation notice."""
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        raise EmailButlerClientError("待扫描邮箱地址无效")
    payload = _request(
        "POST",
        "/signals/scan",
        json={
            "email": target,
            "signal_type": "openai_account_deactivation",
            "lookback_days": max(1, min(int(lookback_days or 120), 365)),
            "folders": ["inbox", "junk"],
        },
    )
    signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
    return {
        "ok": True,
        "detected": bool(signal.get("detected")),
        "checked_at": str(payload.get("checked_at") or ""),
        "received_at": str(signal.get("received_at") or ""),
        "subject": str(signal.get("subject") or "")[:300],
        "sender": str(signal.get("from") or "")[:200],
        "message_id": str(signal.get("message_id") or "")[:300],
        "confidence": str(signal.get("confidence") or "none"),
    }


def pick_account() -> EmailButlerAccount:
    """按 API Key 策略租用一个邮箱身份，并缓存 lease 上下文。"""
    payload = _request("POST", "/mailboxes", json={})
    mailbox = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else {}
    email = str(mailbox.get("email") or "").strip()
    mailbox_id = str(mailbox.get("id") or "").strip()
    if not email or "@" not in email or not mailbox_id:
        raise EmailButlerClientError("Email Butler 发号响应缺少 mailbox.id/email")
    account = EmailButlerAccount(
        email=email,
        mailbox_id=mailbox_id,
        lease_id=str(mailbox.get("lease_id") or ""),
        leased_until=str(mailbox.get("leased_until") or ""),
        provider=str(mailbox.get("provider") or ""),
        mailbox_email=str(mailbox.get("mailbox_email") or email),
    )
    _CONTEXT_CACHE[_cache_key(email)] = account
    logger.info("[EmailButler] 已租用邮箱: %s provider=%s", email, account.provider or "?")
    return account


def get_account_context(email: str) -> EmailButlerAccount | None:
    return _CONTEXT_CACHE.get(_cache_key(email))


def _outcome_for_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "succeeded", "registered", "used"}:
        return "succeeded"
    if normalized in {"failed", "disabled", "bad", "error"}:
        return "failed"
    return "abandoned"


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    """释放租约；成功结果由 Butler Key 策略自动标记 service=openai。"""
    key = _cache_key(email)
    account = _CONTEXT_CACHE.get(key)
    if not account:
        logger.info("[EmailButler] 邮箱上下文已不存在，跳过释放: %s", email)
        return
    try:
        _request(
            "POST",
            f"/mailboxes/{quote(account.mailbox_id, safe='')}/release",
            json={"outcome": _outcome_for_status(status), "message": str(note or "")[:300]},
        )
    finally:
        _CONTEXT_CACHE.pop(key, None)
    logger.info("[EmailButler] 已释放邮箱: %s outcome=%s", email, _outcome_for_status(status))


def _message_otp(payload: dict) -> str | None:
    direct = str(payload.get("verification_code") or "").strip()
    if _OTP_RE.fullmatch(direct):
        return direct
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    for message in messages:
        if not isinstance(message, dict):
            continue
        direct = str(message.get("code") or "").strip()
        if _OTP_RE.fullmatch(direct):
            return direct
        item = {
            "from": message.get("from") or "",
            "subject": message.get("subject") or "",
            "text": message.get("body_text") or message.get("snippet") or "",
            "html": message.get("body_html") or "",
        }
        extracted = extract_otp(item)
        if extracted:
            return extracted
    return None


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    """轮询 Butler `/messages`，返回当前租约内最新 OpenAI 六位验证码。"""
    account = get_account_context(email)
    if not account:
        raise EmailButlerClientError(f"Email Butler 邮箱租约上下文不存在: {email}")

    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    since = ""
    if after_ts is not None:
        since = datetime.fromtimestamp(float(after_ts) - 30, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    best_otp: str | None = None
    settle_until: float | None = None
    last_error = "尚未收到验证码"
    logger.info("[EmailButler] 开始轮询邮箱 %s，最长 %ss", email, wait_seconds)
    while time.monotonic() <= deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        params = {
            "timeout_seconds": min(3, remaining),
            "interval_seconds": 1,
        }
        if since:
            params["since"] = since
        try:
            payload = _request(
                "GET",
                f"/mailboxes/{quote(account.mailbox_id, safe='')}/messages",
                params=params,
            )
            otp = _message_otp(payload)
            if otp and otp != best_otp:
                best_otp = otp
                settle_until = time.monotonic() + settle
                logger.info("[EmailButler] 锁定 OTP 候选，等待 %ss 确认", settle)
            if best_otp and settle_until is not None and time.monotonic() >= settle_until:
                return best_otp
        except EmailButlerClientError as exc:
            last_error = str(exc)

        remaining_float = deadline - time.monotonic()
        if remaining_float <= 0:
            break
        time.sleep(min(interval, remaining_float))

    if best_otp:
        return best_otp
    raise EmailButlerClientError(f"等待 Email Butler 验证码超时: {email}; {last_error}")
