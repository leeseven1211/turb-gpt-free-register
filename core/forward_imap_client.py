# -*- coding: utf-8 -*-
"""读取 Hide My Email 实际转发目标的通用 IMAP 客户端。"""
from __future__ import annotations

import email as email_lib
import imaplib
import logging
import time
from datetime import datetime, timezone
from email.utils import parseaddr

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email
from core.qqmail_client import _msg_to_dict

logger = logging.getLogger(__name__)


class ForwardIMAPError(RuntimeError):
    pass


def _settings() -> tuple[str, int, str, str]:
    server = str(getattr(_email_cfg, "ICLOUD_HME_FORWARD_IMAP_SERVER", "imap.gmail.com") or "").strip()
    port = int(getattr(_email_cfg, "ICLOUD_HME_FORWARD_IMAP_PORT", 993) or 993)
    username = str(getattr(_email_cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "") or "").strip()
    password = str(getattr(_email_cfg, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "") or "").replace(" ", "").strip()
    if not server or not username or not password:
        raise ForwardIMAPError(
            "隐藏邮箱转发 IMAP 未配置：请填写服务器、邮箱和应用专用密码"
        )
    return server, port, username, password


def _connect() -> imaplib.IMAP4_SSL:
    server, port, username, password = _settings()
    try:
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        status, _ = mail.select("INBOX", readonly=True)
        if status != "OK":
            raise ForwardIMAPError("隐藏邮箱转发 IMAP 无法打开 INBOX")
        return mail
    except ForwardIMAPError:
        raise
    except imaplib.IMAP4.error as exc:
        raise ForwardIMAPError(f"隐藏邮箱转发 IMAP 登录失败: {exc}") from exc
    except Exception as exc:
        raise ForwardIMAPError(f"隐藏邮箱转发 IMAP 连接失败: {type(exc).__name__}: {exc}") from exc


def test_connection() -> dict:
    server, port, username, _ = _settings()
    mail = _connect()
    try:
        status, data = mail.status("INBOX", "(MESSAGES)")
        return {
            "method": "forward_imap",
            "server": server,
            "port": port,
            "email_domain": username.rsplit("@", 1)[-1].lower() if "@" in username else "",
            "status": str(status or ""),
            "mailbox": str((data or [b""])[0], errors="replace")[:120] if data else "",
        }
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def _recipient_headers(msg) -> str:
    values: list[str] = []
    for name in ("To", "Delivered-To", "X-Original-To", "X-Forwarded-To", "Envelope-To"):
        values.extend(str(value or "") for value in (msg.get_all(name, []) or []))
    return " ".join(values).lower()


def _recent_messages(mail: imaplib.IMAP4_SSL, after_ts: float, limit: int = 50) -> list[tuple[dict, str]]:
    after_dt = datetime.fromtimestamp(after_ts - 60, tz=timezone.utc)
    status, ids_data = mail.search(None, f'(SINCE "{after_dt.strftime("%d-%b-%Y")}")')
    if status != "OK":
        return []
    ids = (ids_data[0].split() if ids_data and ids_data[0] else [])[-max(1, limit):]
    out: list[tuple[dict, str]] = []
    for mid in reversed(ids):
        status, data = mail.fetch(mid, "(RFC822)")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            continue
        try:
            msg = email_lib.message_from_bytes(data[0][1])
            out.append((_msg_to_dict(msg), _recipient_headers(msg)))
        except Exception as exc:
            logger.debug("[HME Forward IMAP] 解析邮件失败: %s: %s", type(exc).__name__, exc)
    return out


def _messages_for_recipient(
    mail: imaplib.IMAP4_SSL,
    target: str,
    after_ts: float,
    limit: int = 200,
) -> list[tuple[dict, str, str]]:
    """在 IMAP 端先按收件人头过滤，避免为每个隐藏邮箱下载整个收件箱。"""
    after_dt = datetime.fromtimestamp(after_ts, tz=timezone.utc)
    since = after_dt.strftime("%d-%b-%Y")
    ids: set[bytes] = set()
    for header in ("To", "X-Original-To", "Delivered-To", "Envelope-To"):
        try:
            status, ids_data = mail.search(
                None,
                f'(SINCE "{since}" HEADER {header} "{target}")',
            )
        except Exception:
            continue
        if status == "OK" and ids_data and ids_data[0]:
            ids.update(ids_data[0].split())

    selected = sorted(ids, key=lambda value: int(value))[-max(1, limit):]
    out: list[tuple[dict, str, str]] = []
    for mid in reversed(selected):
        status, data = mail.fetch(mid, "(RFC822)")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            continue
        try:
            msg = email_lib.message_from_bytes(data[0][1])
            out.append((
                _msg_to_dict(msg),
                _recipient_headers(msg),
                mid.decode("ascii", errors="ignore"),
            ))
        except Exception as exc:
            logger.debug("[HME Forward IMAP] 解析邮件失败: %s: %s", type(exc).__name__, exc)
    return out


def scan_openai_deactivation(email: str, *, lookback_days: int = 120) -> dict:
    """扫描转发收件箱中的高置信度 OpenAI 封号通知，不访问 OpenAI AT。"""
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        raise ForwardIMAPError("待扫描隐藏邮箱地址无效")
    lookback = max(1, min(int(lookback_days or 120), 365))
    since_ts = time.time() - lookback * 86400
    mail = _connect()
    try:
        messages = _messages_for_recipient(mail, target, since_ts)
    finally:
        try:
            mail.logout()
        except Exception:
            pass

    # 复用 Cloudflare 邮箱已经过测试的高置信度判定规则；只传入标准化字段，
    # 不保存正文，也不会把普通通知误判成封号通知。
    from core.cf_temp_mail_client import _is_openai_deactivation

    matches: list[dict] = []
    for item, recipient_headers, message_id in messages:
        if target not in recipient_headers:
            continue
        candidate = {**item, "to": target, "id": message_id}
        matched, probe = _is_openai_deactivation(candidate, target)
        if not matched:
            continue
        matches.append({
            "received_at": str(item.get("date") or item.get("receivedDateTime") or ""),
            "subject": str(probe.get("subject") or "")[:300],
            "sender": parseaddr(str(probe.get("from") or ""))[1][:200],
            "message_id": str(message_id or "")[:300],
        })
    matches.sort(key=lambda item: item["received_at"], reverse=True)
    latest = matches[0] if matches else {}
    return {
        "ok": True,
        "detected": bool(matches),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "received_at": latest.get("received_at") or "",
        "subject": latest.get("subject") or "",
        "sender": latest.get("sender") or "",
        "message_id": latest.get("message_id") or "",
        "confidence": "high" if matches else "none",
    }


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    target = str(email or "").strip().lower()
    after = float(after_ts if after_ts is not None else time.time())
    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_ts = float("-inf")
    settle_until: float | None = None

    logger.info("[HME Forward IMAP] 开始轮询转发收件箱，最长 %ss", wait_seconds)
    while time.monotonic() < deadline:
        mail = None
        try:
            mail = _connect()
            messages = _recent_messages(mail, after)
        except ForwardIMAPError as exc:
            logger.warning("[HME Forward IMAP] 拉取失败: %s", exc)
            messages = []
        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

        for item, recipient_headers in messages:
            if target and target not in recipient_headers:
                continue
            if not looks_like_openai_email(item):
                continue
            otp = extract_otp(item)
            if not otp:
                continue
            raw_ts = str(item.get("date") or item.get("receivedDateTime") or "")
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
            except (TypeError, ValueError):
                ts = time.time()
            if ts < after - 60:
                continue
            if ts > best_ts:
                best_otp = otp
                best_ts = ts
                settle_until = time.monotonic() + settle
            break

        if best_otp and settle_until is not None and time.monotonic() >= settle_until:
            logger.info("[HME Forward IMAP] 已取得新的 OpenAI OTP")
            return best_otp
        time.sleep(interval)

    if best_otp:
        return best_otp
    raise ForwardIMAPError(f"等待隐藏邮箱 OTP 超时（>{wait_seconds}s）：转发收件箱没有新的 OpenAI 验证码邮件")
