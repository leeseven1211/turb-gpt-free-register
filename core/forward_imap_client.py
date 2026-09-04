# -*- coding: utf-8 -*-
"""Hide My Email 转发收件适配层。

支持两种 Gmail 转发收件模式：``forward_imap`` 本机直接读取 Gmail，或
``forward_butler`` 使用 Oracle Email Butler 的 PostgreSQL 缓存；两者都复用
同一套目标别名过滤和 OTP 提取逻辑。
"""
from __future__ import annotations

import email as email_lib
import imaplib
import logging
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email
from core.qqmail_client import _msg_to_dict

logger = logging.getLogger(__name__)


class ForwardIMAPError(RuntimeError):
    pass


_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
_DEFAULT_IMAP_RETRY_ATTEMPTS = 3
_DEFAULT_IMAP_RETRY_DELAY_SECONDS = 0.5
_MAX_BULK_SNAPSHOT_MESSAGES = 5000


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
        timeout = max(3, int(getattr(_email_cfg, "ICLOUD_HME_REQUEST_TIMEOUT", 35) or 35))
    except (TypeError, ValueError):
        timeout = 35
    try:
        mail = imaplib.IMAP4_SSL(server, port, timeout=timeout)
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


def _imap_retry_attempts() -> int:
    try:
        value = int(os.environ.get("ICLOUD_HME_IMAP_RETRY_ATTEMPTS", str(_DEFAULT_IMAP_RETRY_ATTEMPTS)) or _DEFAULT_IMAP_RETRY_ATTEMPTS)
    except (TypeError, ValueError):
        value = _DEFAULT_IMAP_RETRY_ATTEMPTS
    return max(1, min(value, 5))


def _run_with_imap_retry(operation):
    """Retry a complete read-only IMAP operation after a transient disconnect."""
    attempts = _imap_retry_attempts()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (ForwardIMAPError, imaplib.IMAP4.error, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt >= attempts:
                break
            delay = _DEFAULT_IMAP_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "[HME Forward IMAP] 只读扫描连接中断，将在 %.1fs 后重试 (%s/%s): %s",
                delay,
                attempt,
                attempts,
                str(exc)[:180],
            )
            time.sleep(delay)
    if isinstance(last_error, ForwardIMAPError):
        raise last_error
    raise ForwardIMAPError(
        f"隐藏邮箱转发 IMAP 扫描失败: {type(last_error).__name__}: {last_error}"
    ) from last_error


def test_connection() -> dict:
    try:
        from core.email_butler_client import test_connection as test_butler

        result = test_butler()
        return {
            "method": "email_butler_pg",
            "status": "ok",
            "consumer": result.get("consumer") or "",
            "capabilities": result.get("capabilities") or [],
        }
    except Exception as exc:
        raise ForwardIMAPError(f"Email Butler 入站缓存不可用: {exc}") from exc


def test_local_connection() -> dict:
    """Check the local Gmail IMAP path without touching Email Butler."""
    mail = _connect()
    try:
        return {
            "method": "local_forward_imap",
            "status": "ok",
            "server": str(getattr(_email_cfg, "ICLOUD_HME_FORWARD_IMAP_SERVER", "") or ""),
            "mailbox": "INBOX",
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


def _recipient_addresses(msg) -> set[str]:
    """Extract exact recipient addresses from all forwarding headers."""
    return {
        match.group(0).lower()
        for name in ("To", "Delivered-To", "X-Original-To", "X-Forwarded-To", "Envelope-To")
        for value in (msg.get_all(name, []) or [])
        for match in _EMAIL_RE.finditer(str(value or ""))
    }


def _internal_date(meta: object) -> str:
    marker = 'INTERNALDATE "'
    raw = str(meta or "")
    if marker not in raw:
        return ""
    return raw.split(marker, 1)[1].split('"', 1)[0]


def _apply_internal_date(item: dict, meta: object) -> dict:
    raw_internal = _internal_date(meta)
    if raw_internal:
        try:
            internal_dt = parsedate_to_datetime(raw_internal)
            item["receivedDateTime"] = internal_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            pass
    return item


def _fetch_raw_message(mail: imaplib.IMAP4_SSL, message_id: bytes, spec: str) -> tuple[object, bytes]:
    status, data = mail.fetch(message_id, spec)
    if status != "OK" or not data:
        raise ForwardIMAPError(f"隐藏邮箱转发 IMAP 读取邮件失败: {message_id!r}")
    for entry in data:
        if isinstance(entry, tuple) and len(entry) >= 2 and isinstance(entry[1], (bytes, bytearray)):
            return entry[0], bytes(entry[1])
    raise ForwardIMAPError(f"隐藏邮箱转发 IMAP 响应缺少邮件内容: {message_id!r}")


def _message_from_fetch(
    mail: imaplib.IMAP4_SSL,
    message_id: bytes,
    *,
    spec: str,
) -> tuple[dict, str, str]:
    meta, raw = _fetch_raw_message(mail, message_id, spec)
    msg = email_lib.message_from_bytes(raw)
    item = _apply_internal_date(_msg_to_dict(msg), meta)
    recipient_headers = _recipient_headers(msg)
    return item, recipient_headers, message_id.decode("ascii", errors="ignore")


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
    search_errors: list[Exception] = []
    successful_search = False
    for header in ("To", "X-Original-To", "Delivered-To", "Envelope-To"):
        try:
            status, ids_data = mail.search(
                None,
                f'(SINCE "{since}" HEADER {header} "{target}")',
            )
        except Exception as exc:
            search_errors.append(exc)
            continue
        if status == "OK":
            successful_search = True
            if ids_data and ids_data[0]:
                ids.update(ids_data[0].split())

    if not successful_search and search_errors:
        raise ForwardIMAPError(
            f"隐藏邮箱转发 IMAP 搜索失败: {type(search_errors[-1]).__name__}: {search_errors[-1]}"
        )

    selected = sorted(ids, key=lambda value: int(value))[-max(1, limit):]
    out: list[tuple[dict, str, str]] = []
    for mid in reversed(selected):
        try:
            item, recipient_headers, message_id = _message_from_fetch(
                mail,
                mid,
                spec="(INTERNALDATE RFC822)",
            )
            out.append((
                item,
                recipient_headers,
                message_id,
            ))
        except ForwardIMAPError:
            # A dropped socket must escape so the outer read-only operation
            # can reconnect and retry the complete scan.
            raise
        except Exception as exc:
            logger.debug("[HME Forward IMAP] 解析邮件失败: %s: %s", type(exc).__name__, exc)
    return out


def _imap_ids(data: list[bytes] | list[str] | None) -> list[bytes]:
    if not data or not data[0]:
        return []
    raw = data[0]
    if isinstance(raw, str):
        raw = raw.encode("ascii", errors="ignore")
    return list(raw.split())


def _imap_id_sort_key(value: bytes) -> tuple[int, str]:
    text = value.decode("ascii", errors="ignore")
    try:
        return int(text), text
    except ValueError:
        return -1, text


def _messages_for_mailbox_snapshot(
    mail: imaplib.IMAP4_SSL,
    targets: set[str],
    after_ts: float,
    *,
    limit: int = _MAX_BULK_SNAPSHOT_MESSAGES,
) -> dict[str, list[tuple[dict, str, str]]]:
    """Read one shared inbox snapshot and index candidate messages by HME alias."""
    after_dt = datetime.fromtimestamp(after_ts, tz=timezone.utc)
    since = after_dt.strftime("%d-%b-%Y")
    try:
        status, ids_data = mail.search(None, f'(SINCE "{since}" FROM "openai.com")')
    except Exception as exc:
        raise ForwardIMAPError(
            f"隐藏邮箱转发 IMAP 批量搜索失败: {type(exc).__name__}: {exc}"
        ) from exc
    if status != "OK":
        raise ForwardIMAPError("隐藏邮箱转发 IMAP 批量搜索失败")

    ids = sorted(_imap_ids(ids_data), key=_imap_id_sort_key)[-max(1, int(limit)) :]
    indexed: dict[str, list[tuple[dict, str, str]]] = {target: [] for target in targets}
    for message_id in ids:
        _meta, raw_header = _fetch_raw_message(mail, message_id, "(INTERNALDATE BODY.PEEK[HEADER])")
        header_msg = email_lib.message_from_bytes(raw_header)
        matching_targets = targets.intersection(_recipient_addresses(header_msg))
        if not matching_targets:
            continue
        full_item, recipient_headers, message_id_text = _message_from_fetch(
            mail,
            message_id,
            spec="(INTERNALDATE RFC822)",
        )
        full_item["to"] = recipient_headers
        for target in matching_targets:
            indexed[target].append((full_item, recipient_headers, message_id_text))
    return indexed


def _message_timestamp(item: dict) -> float:
    # IMAP INTERNALDATE is the actual mailbox delivery time.  The sender Date
    # header can be minutes older after HME forwarding and must not exclude a
    # message that arrived inside the current OTP request window.
    raw = str(item.get("receivedDateTime") or item.get("date") or "").strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _latest_forwarded_otp(mail: imaplib.IMAP4_SSL, target: str, after_ts: float) -> str | None:
    """从已打开的转发收件箱中读取目标别名最新的新 OTP。"""
    try:
        mail.noop()
    except Exception:
        # 部分 IMAP mock/旧服务没有 NOOP；后续 SEARCH 仍可能正常工作。
        pass
    cutoff = float(after_ts if after_ts is not None else time.time()) - 30
    for item, recipient_headers, _message_id in _messages_for_recipient(mail, target, cutoff, limit=80):
        if target not in recipient_headers:
            continue
        received_at = _message_timestamp(item)
        if received_at and received_at < cutoff:
            continue
        if not looks_like_openai_email(item):
            continue
        otp = extract_otp(item)
        if otp:
            return otp
    return None


def _deactivation_result(target: str, messages: list[tuple[dict, str, str]]) -> dict:
    from core.cf_temp_mail_client import _is_openai_deactivation

    matches: list[dict] = []
    for item, recipient_headers, message_id in messages:
        if target not in recipient_headers:
            continue
        # The index already proved that this message was delivered to target;
        # pass the exact alias to the shared detector instead of a combined
        # forwarding-header string.
        candidate = {**item, "to": target, "id": message_id}
        matched, probe = _is_openai_deactivation(candidate, target)
        if not matched:
            continue
        matches.append({
            "received_at": str(item.get("receivedDateTime") or item.get("date") or ""),
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


def _scan_openai_deactivation_once(target: str, since_ts: float) -> dict:
    mail = _connect()
    try:
        messages = _messages_for_recipient(mail, target, since_ts)
        return _deactivation_result(target, messages)
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def scan_openai_deactivation(email: str, *, lookback_days: int = 120) -> dict:
    """扫描转发收件箱中的高置信度 OpenAI 封号通知，不访问 OpenAI AT。"""
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        raise ForwardIMAPError("待扫描隐藏邮箱地址无效")
    lookback = max(1, min(int(lookback_days or 120), 365))
    since_ts = time.time() - lookback * 86400
    return _run_with_imap_retry(lambda: _scan_openai_deactivation_once(target, since_ts))


def scan_openai_deactivation_bulk(emails: list[str], *, lookback_days: int = 120) -> dict[str, dict]:
    """Scan many aliases from one shared Gmail mailbox snapshot.

    The result is keyed by normalized alias and contains the same safe fields
    as :func:`scan_openai_deactivation`. Mail bodies and credentials never
    leave this process.
    """
    targets = {str(email or "").strip().lower() for email in (emails or [])}
    targets.discard("")
    if any("@" not in target for target in targets):
        raise ForwardIMAPError("待扫描隐藏邮箱地址无效")
    if not targets:
        return {}
    lookback = max(1, min(int(lookback_days or 120), 365))
    since_ts = time.time() - lookback * 86400

    def _scan_once() -> dict[str, dict]:
        mail = _connect()
        try:
            indexed = _messages_for_mailbox_snapshot(mail, targets, since_ts)
            return {
                target: _deactivation_result(target, indexed.get(target, []))
                for target in sorted(targets)
            }
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    return _run_with_imap_retry(_scan_once)


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        raise ForwardIMAPError("待查询的转发邮箱地址无效")
    anchor = float(after_ts if after_ts is not None else time.time())

    if str(getattr(_email_cfg, "ICLOUD_HME_INBOX_MODE", "") or "").strip().lower() == "forward_imap":
        return _fetch_latest_otp_local(
            target,
            anchor,
            max_wait=max_wait,
            poll_interval=poll_interval,
        )

    mail = None
    try:
        from core.email_butler_client import fetch_inbound_otp

        try:
            mail = _connect()
        except Exception as exc:
            logger.warning(
                "[HME Forward IMAP] 本机 IMAP 兜底不可用，仅等待 Email Butler PG：%s: %s",
                type(exc).__name__,
                str(exc)[:180],
            )

        def _probe() -> str | None:
            if mail is None:
                return None
            otp = _latest_forwarded_otp(mail, target, anchor)
            if otp:
                logger.info("[HME Forward IMAP] 已直接取得新 OTP：%s", target)
            return otp

        return fetch_inbound_otp(
            target,
            after_ts=after_ts,
            max_wait=max_wait,
            poll_interval=poll_interval,
            settle_seconds=settle_seconds,
            local_probe=_probe if mail is not None else None,
        )
    except Exception as exc:
        raise ForwardIMAPError(f"Email Butler PG 缓存取码失败: {exc}") from exc
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass


def _fetch_latest_otp_local(
    target: str,
    anchor: float,
    *,
    max_wait: int | None = None,
    poll_interval: int | None = None,
) -> str:
    """Poll Gmail directly for local ``forward_imap`` mode."""
    wait_seconds = max(1, int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT))
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    deadline = time.monotonic() + wait_seconds
    mail = None
    last_error = "尚未收到新的 OpenAI 验证码邮件"
    logger.info("[HME Forward IMAP] 本机 Gmail IMAP 等待验证码：%s，最长 %ss", target, wait_seconds)
    try:
        while time.monotonic() < deadline:
            if mail is None:
                try:
                    mail = _connect()
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("[HME Forward IMAP] 本机 Gmail IMAP 建连失败，将重试：%s", str(exc)[:180])
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        time.sleep(min(interval, remaining))
                    continue
            try:
                otp = _latest_forwarded_otp(mail, target, anchor)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning("[HME Forward IMAP] 本机 Gmail IMAP 读取失败，将重连：%s", str(exc)[:180])
                try:
                    mail.logout()
                except Exception:
                    pass
                mail = None
            else:
                if otp:
                    logger.info("[HME Forward IMAP] 本机已取得新 OTP：%s", target)
                    return otp

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(interval, remaining))
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass
    raise ForwardIMAPError(f"本机 Gmail IMAP 等待验证码超时（>{wait_seconds}s）：{target}; {last_error}")
