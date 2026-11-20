# -*- coding: utf-8 -*-
"""CloudMail/Cloud Mail API 邮箱客户端。"""
from __future__ import annotations

from core.email.mailbox_wait import WAIT_INTERRUPTED, bounded_sleep, bounded_timeout
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from config import email as _email_cfg
from core.email.otp import extract_otp, looks_like_openai_email

logger = logging.getLogger('core.cloudmail_client')

REQUEST_TIMEOUT = 20


class CloudMailError(RuntimeError):
    """CloudMail/Cloud Mail 服务请求或邮箱取码失败。"""


@dataclass
class CloudMailAccount:
    email: str
    domain: str


_CONTEXT_CACHE: dict[str, CloudMailAccount] = {}


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _base_url() -> str:
    base = str(getattr(_email_cfg, "CLOUDMAIL_API_BASE", "") or "").strip().rstrip("/")
    if not base:
        raise CloudMailError("CloudMail API 地址未配置，请设置 CLOUDMAIL_API_BASE")
    if not re.match(r"^https?://", base, re.I):
        base = "https://" + base
    return base


def _token() -> str:
    token = str(getattr(_email_cfg, "CLOUDMAIL_AUTH_TOKEN", "") or "").strip()
    if not token:
        raise CloudMailError("CloudMail Authorization Token 未配置，请设置 CLOUDMAIL_AUTH_TOKEN")
    return token


def _request(path: str, body: dict | None = None):
    url = _base_url() + path
    try:
        resp = requests.post(
            url,
            json=body or {},
            headers={"Authorization": _token(), "Accept": "application/json"},
            timeout=bounded_timeout(REQUEST_TIMEOUT),
        )
    except requests.RequestException as exc:
        raise CloudMailError(f"CloudMail 请求失败 ({path}): {type(exc).__name__}: {exc}") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise CloudMailError(f"CloudMail 响应不是 JSON ({path}): HTTP {resp.status_code}") from exc

    code = payload.get("code") if isinstance(payload, dict) else None
    if resp.status_code >= 400 or code not in (200, "200"):
        message = payload.get("message") if isinstance(payload, dict) else ""
        raise CloudMailError(f"CloudMail 请求失败 ({path}): HTTP {resp.status_code}; code={code}; {message or str(payload)[:200]}")
    return payload.get("data")


def get_account_context(email: str) -> CloudMailAccount | None:
    return _CONTEXT_CACHE.get(_cache_key(email))


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    _CONTEXT_CACHE.pop(_cache_key(email), None)
    logger.info("[CloudMail] 已释放邮箱上下文: %s（status=%s, note=%s）", email, status, note or "")


def _parse_time(raw) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            # 文档标注 createTime 为 UTC。
            return datetime.strptime(text.replace("Z", ""), fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _otp_item(mail: dict) -> dict:
    return {
        "id": mail.get("emailId") or mail.get("id"),
        "from": mail.get("sendEmail") or mail.get("from") or "",
        "subject": mail.get("subject") or "",
        "text": mail.get("text") or "",
        "html": mail.get("content") or mail.get("html") or "",
    }


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    target = str(email or "").strip()
    if not target:
        raise CloudMailError("CloudMail 取码缺少邮箱地址")

    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_timestamp = float("-inf")
    settle_until: float | None = None
    last_error = "收件箱为空或尚未出现新的 OpenAI 验证码"

    logger.info("[CloudMail] 开始轮询邮箱 %s，最长 %ss", target, wait_seconds)
    while time.monotonic() <= deadline:
        try:
            mails = _request(
                "/api/public/emailList",
                {
                    "toEmail": target,
                    "timeSort": "desc",
                    "type": 0,
                    "isDel": 0,
                    "num": 1,
                    "size": 20,
                },
            )
            if not isinstance(mails, list):
                raise CloudMailError("CloudMail 邮件查询响应 data 不是数组")
            for mail in sorted(mails, key=lambda item: _parse_time((item or {}).get("createTime")) or float("-inf"), reverse=True):
                if not isinstance(mail, dict):
                    continue
                ts = _parse_time(mail.get("createTime"))
                if after_ts is not None and ts is not None and ts < after_ts - 30:
                    continue
                item = _otp_item(mail)
                if not looks_like_openai_email(item):
                    continue
                otp = extract_otp(item)
                if not otp:
                    continue
                candidate_time = float("-inf") if ts is None else ts
                if best_otp is None or candidate_time > best_timestamp or (candidate_time == best_timestamp and otp != best_otp):
                    best_otp = otp
                    best_timestamp = candidate_time
                    settle_until = time.monotonic() + settle
                    logger.info("[CloudMail] 锁定 OTP 候选，等待 %ss 确认", settle)

            now = time.monotonic()
            if best_otp and settle_until is not None and now >= settle_until:
                return best_otp
        except WAIT_INTERRUPTED:
            raise
        except CloudMailError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        bounded_sleep(min(interval, remaining))

    if best_otp:
        return best_otp
    raise CloudMailError(f"等待 CloudMail 验证码超时: {target}; {last_error}")
