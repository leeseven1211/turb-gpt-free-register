"""西瓜邮箱 API；原订单与幂等键在 PostgreSQL 持久化。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import re
import threading
import time
from urllib.parse import quote, urlsplit

import requests

from config import email as _cfg
from core.email.mailbox_wait import bounded_sleep, bounded_timeout
from core.email.otp import extract_otp
from core.storage.email import provider_orders as orders

logger = logging.getLogger('core.xigua_client')
_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_CACHE: dict[str, "XiguaAccount"] = {}
_LOCK = threading.RLock()


class XiguaError(RuntimeError):
    def __init__(self, message, *, status=0, retry_after=0):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass
class XiguaAccount:
    email: str
    order_id: str
    order_pk: int = 0


def _base():
    base = str(getattr(_cfg, "XIGUA_API_BASE", "https://xigua.dasiqo.com") or "").strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise XiguaError("西瓜 API 地址无效，请检查 XIGUA_API_BASE")
    return base


def _key():
    key = str(getattr(_cfg, "XIGUA_API_KEY", "") or "").strip()
    if not key:
        raise XiguaError("西瓜 API Key 未配置，请设置 XIGUA_API_KEY")
    return key


def _identity():
    return orders.supplier_ref(_base(), _key())


def _get(path):
    headers = {"Accept": "application/json", "Authorization": "Bearer " + _key()}
    try:
        response = requests.request("GET", _base() + path, headers=headers,
                                    timeout=bounded_timeout(max(1, int(_cfg.XIGUA_REQUEST_TIMEOUT))),
                                    allow_redirects=False)
    except requests.RequestException as exc:
        raise XiguaError(f"西瓜网络请求失败：{type(exc).__name__}") from None
    try:
        delay = max(0, float(response.headers.get("Retry-After", 0)))
    except (TypeError, ValueError):
        delay = 0
    if not 200 <= response.status_code < 300:
        raise XiguaError(f"西瓜 HTTP {response.status_code}", status=response.status_code, retry_after=delay)
    try:
        payload = response.json()
    except ValueError:
        raise XiguaError("西瓜响应不是 JSON", status=response.status_code) from None
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise XiguaError("西瓜响应结构无效", status=response.status_code)
    if payload.get("error"):
        raise XiguaError("西瓜返回业务错误", status=response.status_code)
    return payload.get("data") if isinstance(payload.get("data"), (dict, list)) else payload


def _account(row):
    account = XiguaAccount(row["email"], row["order_id"], int(row["id"]))
    with _LOCK:
        _CACHE[account.email.lower()] = account
    return account


def get_account_context(email):
    # 不按供应商邮箱列表猜测最近订单；原任务只能使用持久化的确切订单。
    row = orders.get_by_email("xigua", email, identity=_identity())
    return _account(row) if row else None


def restore_account_context(email, **_kwargs):
    account = get_account_context(email)
    if account is None:
        raise XiguaError("西瓜原订单未保存在 PostgreSQL，不能猜测订单或重新购买")
    return account


def release_account(email, status="available", note=None):
    # 普通失败只保留原付费邮箱，不能自动取消订单后让批量重跑领取另一邮箱。
    return None


def _received_at(data):
    value = next((data.get(key) for key in ("received_at", "receivedAt", "code_received_at") if data.get(key) is not None), None)
    if value is None:
        return None
    try:
        stamp = float(value)
        return stamp / 1000 if stamp > 100000000000 else stamp
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None


def fetch_latest_otp(email, after_ts=0, max_wait=None, poll_interval=None, settle_seconds=None):
    account = restore_account_context(email)
    deadline = time.monotonic() + max(0, int(_cfg.OTP_MAX_WAIT if max_wait is None else max_wait))
    interval = max(1, int(_cfg.XIGUA_POLL_INTERVAL if poll_interval is None else poll_interval))
    attempts = max(1, int(_cfg.XIGUA_POLL_ATTEMPTS))
    settle = max(0, int(_cfg.OTP_SETTLE_SECONDS if settle_seconds is None else settle_seconds))
    with orders.order_lock("xigua", f"order:{account.order_id}"):
        row = orders.get_by_email("xigua", email, identity=_identity())
        previous = str((row.get("private_json") or {}).get("last_code_fingerprint") or "")
        candidate, fingerprint, confirmations, first_seen = None, "", 0, 0
        for attempt in range(attempts):
            if attempt and time.monotonic() > deadline:
                break
            data = _get("/api/v1/orders/" + quote(account.order_id, safe=""))
            received = _received_at(data)
            code_value = data.get("code") or data.get("verification_code") or data.get("verificationCode")
            match = _CODE_RE.search(str(code_value or ""))
            text = " ".join(str(data.get(key) or "") for key in ("subject", "body", "body_preview", "message"))
            code = match.group(1) if match else extract_otp({"subject": text, "body": text, "text": text})
            if code and (received is None or not after_ts or received >= after_ts):
                current = hashlib.sha256(f"{code}\0{received or ''}".encode()).hexdigest()
                if current != previous:
                    if current == fingerprint:
                        confirmations += 1
                    else:
                        candidate, fingerprint, confirmations, first_seen = code, current, 1, time.monotonic()
                    if confirmations >= 2 and time.monotonic() - first_seen >= settle:
                        orders.update(account.order_pk, private={"last_code_fingerprint": fingerprint})
                        logger.info("[Xigua] 原订单验证码已连续确认")
                        return candidate
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            bounded_sleep(min(interval, remaining))
    raise XiguaError("西瓜验证码等待超时；原订单保留，可继续重跑")
