# -*- coding: utf-8 -*-
"""Email Butler `/v1` 通用邮箱 API 客户端。"""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

import requests

from config import email as _email_cfg
from core.otp_utils import extract_otp

logger = logging.getLogger(__name__)

_OTP_RE = re.compile(r"^\d{6}$")
_INBOUND_WAIT_CHUNK_SECONDS = 75
_TRANSIENT_INBOUND_ERROR_MARKERS = (
    "ConnectionError",
    "ConnectTimeout",
    "ReadTimeout",
    "SSLError",
    "Timeout",
    "HTTP 408",
    "HTTP 425",
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "HTTP 520",
    "HTTP 522",
    "HTTP 523",
    "HTTP 524",
)


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
    base = str(
        override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_BASE", "") or ""
    ).strip()
    if not base:
        raise EmailButlerClientError("Email Butler API 地址未配置，请填写 /v1 根地址。")
    return base.rstrip("/")


def _api_key(override: str | None = None) -> str:
    key = str(
        override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_KEY", "") or ""
    ).strip()
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
    timeout: int | float | None = None,
    retry_connection_error: bool = False,
) -> dict:
    attempts = 2 if retry_connection_error else 1
    for attempt in range(1, attempts + 1):
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
                timeout=timeout if timeout is not None else _request_timeout(),
            )
            break
        except requests.ConnectionError as exc:
            if attempt < attempts:
                logger.warning(
                    "[EmailButler] 连接瞬时中断，0.5s 后重试一次：path=%s error=%s",
                    path,
                    str(exc)[:180],
                )
                time.sleep(0.5)
                continue
            raise EmailButlerClientError(
                f"Email Butler 请求失败 ({path}): {type(exc).__name__}: {exc}"
            ) from exc
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
    """调用 `/me` 验证 URL、Key、客户端策略和必要能力。"""
    payload = _request("GET", "/me", api_base=api_base, api_key=api_key)
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), list) else []
    required = {
        "mailboxes.create",
        "mailboxes.messages",
        "mailboxes.release",
        "signals.scan",
        "inbound.code",
    }
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
    """扫描一个 Butler 邮箱中的高置信度 OpenAI 封号通知。"""
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
    """按 API Key 策略租用一个邮箱身份，并缓存租约上下文。"""
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


def active_mailbox_leases() -> list[dict]:
    """返回当前 WebUI 进程持有的 Email Butler 租约，不包含 API Key。"""
    return [
        {
            "email": account.email,
            "mailbox_id": account.mailbox_id,
            "lease_id": account.lease_id,
            "leased_until": account.leased_until,
            "provider": account.provider,
            "mailbox_email": account.mailbox_email,
        }
        for account in sorted(_CONTEXT_CACHE.values(), key=lambda item: item.email.lower())
    ]


def restore_account_context(email: str, *, purpose: str = "live-check") -> EmailButlerAccount:
    """按邮箱从 Butler 精确租用并恢复进程内上下文。"""
    key = _cache_key(email)
    cached = _CONTEXT_CACHE.get(key)
    if cached:
        return cached
    payload = _request(
        "POST",
        "/mailboxes",
        json={"requested_email": email, "purpose": purpose},
    )
    mailbox = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else {}
    mailbox_id = str(mailbox.get("id") or "").strip()
    mailbox_email = str(mailbox.get("email") or "").strip()
    if not mailbox_id or not mailbox_email or "@" not in mailbox_email:
        raise EmailButlerClientError("Email Butler 按邮箱恢复上下文失败: " + email)
    account = EmailButlerAccount(
        email=mailbox_email,
        mailbox_id=mailbox_id,
        lease_id=str(mailbox.get("lease_id") or ""),
        leased_until=str(mailbox.get("leased_until") or ""),
        provider=str(mailbox.get("provider") or ""),
        mailbox_email=str(mailbox.get("mailbox_email") or mailbox_email),
    )
    _CONTEXT_CACHE[key] = account
    logger.info("[EmailButler] 已按邮箱恢复上下文: %s", email)
    return account


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


def _is_transient_inbound_error(exc: Exception) -> bool:
    message = str(exc or "")
    return any(marker in message for marker in _TRANSIENT_INBOUND_ERROR_MARKERS)


def fetch_inbound_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
    local_probe: Callable[[], str | None] | None = None,
) -> str:
    """Wait on Email Butler's PG-backed forwarded-mail cache.

    The server performs one initial exact query and then waits on PostgreSQL
    LISTEN/NOTIFY. Long waits are split into gateway-safe chunks because the
    public endpoint can be behind Cloudflare, whose timeout is shorter than the
    configured OTP wait. Every chunk uses the same ``since`` anchor, so a
    notification received between requests is found by the next exact query.
    Callers that own the forwarding mailbox may also provide ``local_probe``.
    Email Butler remains the primary source; after each remote miss or
    transient failure the local mailbox is probed once before the next remote
    wait. The probe only loops for the lifetime of this OTP wait and never
    becomes a process-wide mailbox scanner.
    """
    target = _cache_key(email)
    if "@" not in target:
        raise EmailButlerClientError("待查询的转发邮箱地址无效")
    wait_seconds = max(
        1,
        int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT),
    )
    anchor = float(after_ts if after_ts is not None else time.time()) - 30
    since = datetime.fromtimestamp(anchor, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    interval = max(0, int(poll_interval if poll_interval is not None else 1))
    logger.info("[EmailButler] 等待 PG 入站验证码：%s，最长 %ss", target, wait_seconds)
    started = time.monotonic()
    deadline = started + wait_seconds
    last_error = "尚未收到新的 OpenAI 验证码邮件"
    chunk_index = 0
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        # 有本机探测时缩短远端等待段，避免邮件已到 Gmail 但尚未入 PG 时
        # 仍被一个长请求挡住很久；纯远端模式继续使用 75 秒网关安全段。
        chunk_limit = 15 if local_probe is not None else _INBOUND_WAIT_CHUNK_SECONDS
        chunk_seconds = max(1, min(chunk_limit, int(math.ceil(remaining))))
        chunk_index += 1
        try:
            payload = _request(
                "POST",
                "/inbound/code",
                json={
                    "email": target,
                    "since": since,
                    "timeout_seconds": chunk_seconds,
                },
                timeout=max(_request_timeout(), chunk_seconds + 10),
                # 等待入站通知是只读、幂等操作；Oracle/Nginx 偶发在建连阶段断开时，
                # 立即重连一次即可继续等待，不需要重新扫描 Gmail。
                retry_connection_error=True,
            )
            otp = _message_otp(payload)
            if otp:
                elapsed = time.monotonic() - started
                logger.info("[EmailButler] 已从 PG 入站缓存取得 OTP，接口等待 %.1fs", elapsed)
                return otp
            last_error = "PG 入站等待结束但没有 OTP"
        except EmailButlerClientError as exc:
            if not _is_transient_inbound_error(exc):
                raise
            last_error = str(exc)
            logger.warning(
                "[EmailButler] PG 入站等待第 %s 段瞬时失败，继续剩余等待：%s",
                chunk_index,
                str(exc)[:220],
            )

        # 接口优先。只有这一段没有拿到验证码时才探测本地转发邮箱；下一轮
        # 仍会先请求接口，因此 Butler 恢复或 PG 完成入库后会回到主链路。
        if local_probe is not None:
            try:
                local_otp = str(local_probe() or "").strip()
            except Exception as exc:
                logger.warning(
                    "[EmailButler] 本机收件兜底探测失败，继续等待 PG：%s: %s",
                    type(exc).__name__,
                    str(exc)[:180],
                )
            else:
                if _OTP_RE.fullmatch(local_otp):
                    elapsed = time.monotonic() - started
                    logger.info("[EmailButler] 接口未命中，已从本机收件兜底取得 OTP，等待 %.1fs", elapsed)
                    return local_otp

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if interval:
            time.sleep(min(interval, remaining))

    elapsed = time.monotonic() - started
    logger.warning("[EmailButler] PG 入站等待结束但没有 OTP，累计等待 %.1fs", elapsed)
    raise EmailButlerClientError(
        f"等待 Email Butler 入站验证码超时（>{wait_seconds}s）：{target}; {last_error}"
    )


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
        try:
            account = restore_account_context(email)
        except EmailButlerClientError:
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
        params = {"timeout_seconds": min(3, remaining), "interval_seconds": 1}
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
