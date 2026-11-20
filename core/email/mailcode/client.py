# -*- coding: utf-8 -*-
"""域名邮箱 MailCode：幂等购买、通道初始化及按邮箱游标取码。"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from config import email as _cfg
from core.email.mailbox_wait import bounded_sleep, bounded_timeout, cooperative_lock
from core.storage.email import provider_orders as orders

logger = logging.getLogger('core.mailcode_client')
_PREFIX = "/api/open/v1"
_CONTEXT_CACHE: dict[str, "MailCodeAccount"] = {}
_LOCK = threading.RLock()
_UNSET = object()


class MailCodeError(RuntimeError):
    def __init__(self, message, *, status=0, code="", retry_after=0):
        super().__init__(message)
        self.status, self.code, self.retry_after = status, code, retry_after


def _base():
    # 固定官方服务；不接受旧 .env 或运行时配置重定向 API Key。
    return "https://mailcode.bzb.qzz.io"


def _key():
    key = str(getattr(_cfg, "MAILCODE_API_KEY", "") or "").strip()
    if not key:
        raise MailCodeError("MailCode API Key 未配置，请设置 MAILCODE_API_KEY")
    return key


def _identity():
    return orders.supplier_ref(_base(), _key())


def _get(path, *, params=None):
    headers = {"Authorization": "Bearer " + _key(), "Accept": "application/json"}
    try:
        response = requests.request("GET", _base() + _PREFIX + path, params=params,
                                    headers=headers, timeout=bounded_timeout(max(1, int(_cfg.MAILCODE_REQUEST_TIMEOUT))),
                                    allow_redirects=False)
    except requests.RequestException as exc:
        # 不输出完整 URL/请求头，避免泄漏凭据。
        raise MailCodeError(f"MailCode 网络请求失败：{type(exc).__name__}") from None
    try:
        delay = max(0, float(response.headers.get("Retry-After", 0)))
    except (TypeError, ValueError):
        delay = 0
    try:
        payload = response.json()
    except ValueError:
        raise MailCodeError(f"MailCode 响应不是 JSON，HTTP {response.status_code}",
                            status=response.status_code, retry_after=delay) from None
    if not isinstance(payload, dict):
        raise MailCodeError("MailCode 响应结构无效", status=response.status_code)
    error = payload.get("error") or {}
    if not 200 <= response.status_code < 300 or error:
        code = str(error.get("code", "")) if isinstance(error, dict) else ""
        safe_code = code if re.fullmatch(r"[A-Z0-9_]{0,80}", code) else "SUPPLIER_ERROR"
        raise MailCodeError(f"MailCode HTTP {response.status_code} {safe_code}",
                            status=response.status_code, code=code, retry_after=delay)
    if "data" not in payload:
        raise MailCodeError("MailCode 响应缺少 data", status=response.status_code)
    return payload["data"]


def _mailbox_path(mailbox_id, suffix):
    return "/mailboxes/" + quote(str(mailbox_id), safe="") + suffix


def get_codes(mailbox_id, after_sequence=None):
    params = {"limit": 100}
    if after_sequence is not None:
        params["after_sequence"] = str(after_sequence)
    data = _get(_mailbox_path(mailbox_id, "/codes"), params=params)
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise MailCodeError("MailCode 取码响应缺少 records 数组")
    return data


@dataclass
class MailCodeAccount:
    email: str
    mailbox_id: str
    order_id: str = ""
    next_sequence: str = "0"
    order_pk: int = 0
    lock: object = field(default_factory=threading.RLock, repr=False)


def get_account_context(email):
    row = orders.get_by_email("mailcode", email, identity=_identity())
    return _account(row) if row else None


def _remember(account):
    with _LOCK:
        _CONTEXT_CACHE[account.email.lower()] = account
    return account


def _account(row):
    private = row.get("private_json") or {}
    return _remember(MailCodeAccount(row["email"], private["mailbox_id"], row["order_id"],
                                     str(private.get("next_sequence", "0")), int(row["id"])))


def _save_context(account, candidate=_UNSET):
    private = {"next_sequence": account.next_sequence}
    if candidate is not _UNSET:
        private["otp_candidate"] = candidate
    # 游标与候选必须在同一次 UPDATE 提交，避免重启后越过尚未返回的验证码。
    orders.update(account.order_pk, private=private)


def _restore_candidate(private, after_ts):
    candidate = private.get("otp_candidate")
    if not isinstance(candidate, dict) or not isinstance(candidate.get("code"), str) or not re.fullmatch(r"[0-9]{6}", candidate["code"]):
        return None
    try:
        received, expires = float(candidate["received_at"]), float(candidate.get("expires_at") or 0)
        sequence, settle_until = int(candidate["sequence"]), float(candidate["settle_until"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in (received, expires, settle_until)):
        return None
    if (after_ts is not None and received < after_ts) or (expires and expires <= time.time()):
        return None
    state = candidate.get("delivery_status")
    if state == "returned":
        # 同一验证码挑战的重入可恢复“已准备返回、调用方尚未收到”窗口。
        # 新挑战不重放旧交付；无 after_ts 的兼容调用仍只读取新记录。
        if after_ts is None or candidate.get("request_after_ts") != after_ts:
            return None
    elif state != "pending":
        return None
    return dict(candidate, received_at=received, expires_at=expires, sequence=sequence, settle_until=settle_until)


def _return_candidate(account, candidate, after_ts):
    if candidate.get("expires_at") and candidate["expires_at"] <= time.time():
        _save_context(account, None)
        raise MailCodeError("MailCode 候选验证码已过期，原订单保留，可继续取码")
    delivered = dict(candidate, delivery_status="returned", request_after_ts=after_ts, returned_at=time.time())
    # returned 只代表客户端准备返回，不代表 OpenAI 已接收或验证成功。
    _save_context(account, delivered)
    return candidate["code"]


def _cursor(data, current):
    value = str(data.get("next_sequence", current))
    if not re.fullmatch(r"[0-9]+", value) or int(value) > 9000000000000000000:
        raise MailCodeError("MailCode 返回了无效 next_sequence")
    return value  # 服务端游标原样使用，不能 +1，也不能按验证码数字去重。


def release_account(email, status="available", note=None):
    # 付费邮箱保留在 PostgreSQL；普通失败后仍可重跑原订单，不退款或改领。
    return None


def _restore(email):
    account = get_account_context(email)
    if account is None:
        raise MailCodeError("MailCode 原订单未保存在 PostgreSQL，不能猜测订单或重新购买")
    return account


def restore_account_context(email, **_kwargs):
    return _restore(email)


def fetch_latest_otp(email, after_ts=None, max_wait=None, poll_interval=None, settle_seconds=None):
    account = get_account_context(email) or _restore(str(email).strip())
    deadline = time.monotonic() + max(0, int(_cfg.OTP_MAX_WAIT if max_wait is None else max_wait))
    interval = max(5, int(_cfg.OTP_POLL_INTERVAL if poll_interval is None else poll_interval))
    settle = max(0, int(_cfg.OTP_SETTLE_SECONDS if settle_seconds is None else settle_seconds))
    best, best_order = None, (-1, -1)
    last_error = "尚无新验证码"
    with cooperative_lock(account.lock), orders.order_lock("mailcode", f"mailbox:{account.mailbox_id}"):
        # 其他进程可能推进过游标，进入跨进程锁后重新读取事实。
        row = orders.get_by_email("mailcode", email, identity=_identity())
        private = row["private_json"] or {}
        account.next_sequence = str(private.get("next_sequence", "0"))
        candidate = _restore_candidate(private, after_ts)
        if candidate:
            best, best_order = candidate["code"], (candidate["received_at"], candidate["sequence"])
        while True:
            delay = interval
            try:
                data = get_codes(account.mailbox_id, account.next_sequence)
                for record in data["records"]:
                    code = record.get("code")
                    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code):
                        continue
                    received = float(record.get("received_at") or 0) / 1000
                    expires = float(record.get("expires_at") or 0) / 1000
                    if (after_ts is not None and received < after_ts) or (expires and expires <= time.time()):
                        continue
                    order = (received, int(record.get("sequence") or 0))
                    if order > best_order:
                        best, best_order = code, order
                        candidate = {"code": code, "received_at": received, "expires_at": expires,
                                     "sequence": order[1], "settle_until": time.time() + settle,
                                     "delivery_status": "pending", "request_after_ts": after_ts}
                previous = account.next_sequence
                account.next_sequence = _cursor(data, previous)
                _save_context(account, candidate)
                if data.get("has_more"):
                    if account.next_sequence == previous:
                        raise MailCodeError("MailCode 分页游标未前进")
                    if time.monotonic() < deadline:
                        continue
                if best and time.time() >= candidate["settle_until"]:
                    return _return_candidate(account, candidate, after_ts)
                if data.get("channel_status") in {"CLOSED", "PAUSED"}:
                    raise MailCodeError("MailCode 取码通道已关闭/暂停", status=404)
            except MailCodeError as exc:
                if exc.status in {400, 401, 403, 404}:
                    raise
                last_error = str(exc)
                delay = max(interval, exc.retry_after)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            bounded_sleep(min(delay, remaining))
        if best:
            return _return_candidate(account, candidate, after_ts)
    raise MailCodeError(f"等待 MailCode 验证码超时；{last_error}")
