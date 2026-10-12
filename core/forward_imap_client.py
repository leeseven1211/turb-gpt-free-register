# -*- coding: utf-8 -*-
"""Hide My Email 转发收件适配层。

支持两种 Gmail 转发收件模式：``forward_imap`` 本机直接读取 Gmail，或
``forward_butler`` 使用 Oracle Email Butler 的 PostgreSQL 缓存；两者都复用
同一套目标别名过滤和 OTP 提取逻辑。
"""
from __future__ import annotations

from core.mailbox_wait import WAIT_INTERRUPTED, bounded_sleep, bounded_timeout, current_budget
import email as email_lib
import imaplib
import logging
import os
import re
import socket
import threading
import time
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email
from core.qqmail_client import _msg_to_dict

logger = logging.getLogger(__name__)


class ForwardIMAPError(RuntimeError):
    pass


class ForwardIMAPNoMailTimeout(ForwardIMAPError):
    """IMAP 读取正常，但在本次发送窗口内没有找到新邮件。"""


_DEFAULT_IMAP_RETRY_ATTEMPTS = 3
_DEFAULT_IMAP_RETRY_DELAY_SECONDS = 0.5
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b")
_RECIPIENT_SEARCH_CHUNK_SIZE = 50
_MAX_BULK_MATCHED_MESSAGES = 5000
# Gmail IMAP INTERNALDATE 与本机点击时间可能存在极小的秒级偏差；容忍范围
# 必须足够小，避免重发前刚到达的旧验证码再次被当成新码。
_OTP_CLOCK_SKEW_TOLERANCE = 2
# 仅本机收码使用这些槽位；DNS 或驱动异常阻塞时也不能无限积累后台线程。
_IMAP_IO_SLOTS = threading.BoundedSemaphore(8)


class _IMAPDeadlineExceeded(ForwardIMAPError):
    """本次收码的共同预算已耗尽，禁止接受晚到结果。"""


def _abort_imap_socket(mail) -> None:
    """先中断底层读取，不等待 LOGOUT 响应或文件缓冲区锁。"""
    sock = getattr(mail, "sock", None)
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


def _close_imap(mail) -> None:
    """只读会话无需 LOGOUT 确认，直接释放本地连接和读取缓冲区。"""
    if mail is None:
        return
    _abort_imap_socket(mail)
    pending = getattr(mail, "_forward_imap_pending_io", None)
    if pending is not None and not pending.is_set():
        return
    stream = getattr(mail, "file", None)
    if stream is not None:
        try:
            stream.close()
        except Exception:
            pass


def _configured_socket_timeout() -> int:
    try:
        return max(3, int(getattr(_email_cfg, "ICLOUD_HME_REQUEST_TIMEOUT", 35) or 35))
    except (TypeError, ValueError):
        return 35


class _IMAPBudget:
    """每次收码独享截止时间；同步网络命令也必须在预算内结束。"""

    def __init__(self, seconds: float):
        self.deadline = time.monotonic() + seconds
        self.request_timeout = _configured_socket_timeout()
        self.parent = current_budget()

    def remaining(self) -> float:
        remaining = max(0.0, self.deadline - time.monotonic())
        return min(remaining, self.parent.remaining()) if self.parent is not None else remaining

    def require(self) -> float:
        if self.parent is not None:
            self.parent.require("本机 IMAP 收码")
        remaining = self.remaining()
        if remaining <= 0:
            raise _IMAPDeadlineExceeded("本机 IMAP 收码总预算已耗尽")
        return remaining

    def socket_timeout(self) -> float:
        return min(self.request_timeout, self.require())

    def call(self, stage: str, operation, *, mail=None, connection_result: bool = False):
        started = time.monotonic()
        outcome = "失败"
        error_type = "-"
        try:
            # 槽位等待也计入总预算，不向执行器提交无界排队的工作。
            slots = _IMAP_IO_SLOTS
            if self.parent is None:
                if not slots.acquire(timeout=self.require()):
                    raise _IMAPDeadlineExceeded("本机 IMAP 等待网络执行槽位超时")
            else:
                while not slots.acquire(timeout=min(0.1, self.require())):
                    pass
            try:
                timeout = self.socket_timeout()
                sock = getattr(mail, "sock", None)
                if sock is not None:
                    sock.settimeout(timeout)
                finished = threading.Event()
                cancelled = threading.Event()
                lock = threading.Lock()
                result = []
                if mail is not None:
                    mail._forward_imap_pending_io = finished

                def run():
                    value = None
                    ok = False
                    try:
                        try:
                            value = operation()
                            ok = True
                        except BaseException as exc:
                            value = exc
                        with lock:
                            abandoned = cancelled.is_set()
                            if not abandoned:
                                result.append((ok, value))
                            finished.set()
                        if abandoned:
                            # DNS/TLS 构造可能在调用方超时后才结束；晚到连接不能遗留。
                            _close_imap(value if connection_result and ok else mail)
                    finally:
                        slots.release()

                worker = threading.Thread(target=run, name="hme-imap-io", daemon=True)
                try:
                    worker.start()
                except BaseException:
                    finished.set()
                    raise
            except BaseException:
                slots.release()
                raise
            wait_deadline = time.monotonic() + min(timeout, self.remaining())
            try:
                while not finished.wait(min(0.1, max(0.0, wait_deadline - time.monotonic()))):
                    self.require()
                    if time.monotonic() >= wait_deadline:
                        break
            except BaseException:
                completed_connection = None
                with lock:
                    if not finished.is_set():
                        cancelled.set()
                    elif connection_result and result and result[0][0]:
                        # worker 已成功产出但调用方尚未接管，取消竞态必须
                        # 在调用方释放这条连接，不能依赖 worker 的 abandoned。
                        completed_connection = result[0][1]
                if cancelled.is_set():
                    _abort_imap_socket(mail)
                if completed_connection is not None:
                    _close_imap(completed_connection)
                raise
            if not finished.is_set():
                with lock:
                    if not finished.is_set():
                        cancelled.set()
                if cancelled.is_set():
                    # 文件缓冲区由结束后的工作线程释放，避免此处等待其读取锁。
                    _abort_imap_socket(mail)
                    outcome = "超时"
                    self.require()
                    raise ForwardIMAPError(f"本机 IMAP 网络阶段超时：{stage}")
            ok, value = result[0]
            try:
                self.require()
            except BaseException:
                _close_imap(value if connection_result and ok else mail)
                outcome = "超时"
                raise
            if not ok:
                raise value
            outcome = "完成"
            return value
        except BaseException as exc:
            error_type = type(exc).__name__
            if isinstance(exc, _IMAPDeadlineExceeded):
                outcome = "超时"
            raise
        finally:
            logger.info(
                "[HME Forward IMAP] 阶段=%s 耗时=%.3fs 结果=%s 异常类型=%s",
                stage, time.monotonic() - started, outcome, error_type,
            )


def _imap_call(mail, stage: str, operation, budget: _IMAPBudget | None = None):
    parent = current_budget()
    if budget is None and parent is not None:
        budget = _IMAPBudget(parent.require("本机 IMAP 命令"))
    return budget.call(stage, operation, mail=mail) if budget is not None else operation()


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


def _connect(*, budget: _IMAPBudget | None = None) -> imaplib.IMAP4_SSL:
    parent = current_budget()
    if budget is None and parent is not None:
        budget = _IMAPBudget(parent.require("本机 IMAP 建连"))
    server, port, username, password = _settings()
    timeout = _configured_socket_timeout()
    mail = None
    try:
        if budget is None:
            mail = imaplib.IMAP4_SSL(server, port, timeout=bounded_timeout(timeout))
        else:
            mail = budget.call(
                "连接及TLS",
                lambda: imaplib.IMAP4_SSL(server, port, timeout=bounded_timeout(budget.socket_timeout())),
                connection_result=True,
            )
        _imap_call(mail, "登录", lambda: mail.login(username, password), budget)
        status, _ = _imap_call(mail, "只读选箱", lambda: mail.select("INBOX", readonly=True), budget)
        if status != "OK":
            raise ForwardIMAPError("隐藏邮箱转发 IMAP 无法打开 INBOX")
        return mail
    except WAIT_INTERRUPTED:
        _close_imap(mail)
        raise
    except ForwardIMAPError:
        _close_imap(mail)
        raise
    except imaplib.IMAP4.error as exc:
        _close_imap(mail)
        raise ForwardIMAPError(f"隐藏邮箱转发 IMAP 登录失败: {exc}") from exc
    except Exception as exc:
        _close_imap(mail)
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
        except WAIT_INTERRUPTED:
            raise
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
            bounded_sleep(delay)
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


def _recipient_addresses(headers: str) -> set[str]:
    return {match.group(0).lower() for match in _EMAIL_RE.finditer(headers or "")}


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


def _fetch_raw_message(
    mail: imaplib.IMAP4_SSL,
    message_id: bytes,
    spec: str,
    *,
    budget: _IMAPBudget | None = None,
) -> tuple[object, bytes]:
    status, data = _imap_call(mail, "FETCH", lambda: mail.fetch(message_id, spec), budget)
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
    budget: _IMAPBudget | None = None,
) -> tuple[dict, str, str]:
    meta, raw = _fetch_raw_message(mail, message_id, spec, budget=budget)
    msg = email_lib.message_from_bytes(raw)
    item = _apply_internal_date(_msg_to_dict(msg), meta)
    recipient_headers = _recipient_headers(msg)
    return item, recipient_headers, message_id.decode("ascii", errors="ignore")


def _imap_recipient_search(header: str, targets: list[str]) -> str:
    """Build a bounded IMAP OR expression for one recipient header."""
    expression = f'HEADER {header} "{targets[0]}"'
    for target in targets[1:]:
        expression = f'OR {expression} HEADER {header} "{target}"'
    return expression


def _search_message_ids(
    mail: imaplib.IMAP4_SSL,
    targets: set[str],
    after_ts: float,
    limit: int = 200,
    *,
    budget: _IMAPBudget | None = None,
) -> list[bytes]:
    """合并四个收件人字段的匹配结果，保留最新优先所需的消息序号。"""
    if not targets:
        return []
    after_dt = datetime.fromtimestamp(after_ts, tz=timezone.utc)
    since = after_dt.strftime("%d-%b-%Y")
    ids: set[bytes] = set()
    search_errors: list[Exception] = []
    successful_search = False
    ordered_targets = sorted(targets)
    for header in ("To", "X-Original-To", "Delivered-To", "Envelope-To"):
        for start in range(0, len(ordered_targets), _RECIPIENT_SEARCH_CHUNK_SIZE):
            chunk = ordered_targets[start:start + _RECIPIENT_SEARCH_CHUNK_SIZE]
            query = f'(SINCE "{since}" {_imap_recipient_search(header, chunk)})'
            try:
                status, ids_data = _imap_call(
                    mail, f"SEARCH/{header}", lambda: mail.search(None, query), budget,
                )
            except Exception as exc:
                if budget is not None:
                    # 收码命令中断后立即交给外层重连，不能在失效连接上继续四轮搜索。
                    raise
                search_errors.append(exc)
                continue
            if status == "OK":
                successful_search = True
                if ids_data and ids_data[0]:
                    ids.update(ids_data[0].split())
            if budget is not None:
                logger.info(
                    "[HME Forward IMAP] SEARCH字段=%s 匹配数量=%s",
                    header, len(ids_data[0].split()) if status == "OK" and ids_data and ids_data[0] else 0,
                )

    if not successful_search and search_errors:
        raise ForwardIMAPError(
            f"隐藏邮箱转发 IMAP 搜索失败: {type(search_errors[-1]).__name__}: {search_errors[-1]}"
        )

    max_messages = min(
        _MAX_BULK_MATCHED_MESSAGES,
        max(1, int(limit)) * max(1, len(targets)),
    )
    return sorted(ids, key=lambda value: int(value))[-max_messages:]


def _messages_for_recipients(
    mail: imaplib.IMAP4_SSL,
    targets: set[str],
    after_ts: float,
    limit: int = 200,
) -> dict[str, list[tuple[dict, str, str]]]:
    """Search all aliases server-side, then fetch each matching message once."""
    indexed: dict[str, list[tuple[dict, str, str]]] = {target: [] for target in targets}
    selected = _search_message_ids(mail, targets, after_ts, limit)
    for mid in reversed(selected):
        try:
            item, recipient_headers, message_id = _message_from_fetch(
                mail,
                mid,
                spec="(INTERNALDATE BODY.PEEK[])",
            )
            recipients = _recipient_addresses(recipient_headers)
            for target in targets:
                if target in recipients:
                    indexed[target].append((item, recipient_headers, message_id))
        except ForwardIMAPError:
            # A dropped socket must escape so the outer read-only operation
            # can reconnect and retry the complete scan.
            raise
        except Exception as exc:
            logger.debug("[HME Forward IMAP] 解析邮件失败: %s: %s", type(exc).__name__, exc)
    return indexed


def _messages_for_recipient(
    mail: imaplib.IMAP4_SSL,
    target: str,
    after_ts: float,
    limit: int = 200,
) -> list[tuple[dict, str, str]]:
    """在 IMAP 端按收件人头过滤，避免下载整个共享收件箱。"""
    return _messages_for_recipients(mail, {target}, after_ts, limit).get(target, [])


def _iter_messages_for_recipient(
    mail: imaplib.IMAP4_SSL,
    target: str,
    after_ts: float,
    limit: int = 80,
    *,
    budget: _IMAPBudget | None = None,
):
    """收码按最新候选逐封读取，命中后不再下载其余邮件。"""
    selected = _search_message_ids(mail, {target}, after_ts, limit, budget=budget)
    for mid in reversed(selected):
        try:
            yield _message_from_fetch(mail, mid, spec="(INTERNALDATE BODY.PEEK[])", budget=budget)
        except (ForwardIMAPError, imaplib.IMAP4.error, OSError):
            raise
        except Exception as exc:
            logger.debug("[HME Forward IMAP] 解析候选邮件失败：%s", type(exc).__name__)


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


def _latest_forwarded_otp(
    mail: imaplib.IMAP4_SSL, target: str, after_ts: float, *, budget: _IMAPBudget | None = None,
) -> str | None:
    """从已打开的转发收件箱中读取目标别名最新的新 OTP。"""
    try:
        _imap_call(mail, "NOOP", mail.noop, budget)
    except WAIT_INTERRUPTED:
        raise
    except Exception:
        if budget is not None:
            raise
        # 部分 IMAP mock/旧服务没有 NOOP；后续 SEARCH 仍可能正常工作。
        pass
    cutoff = float(after_ts if after_ts is not None else time.time()) - _OTP_CLOCK_SKEW_TOLERANCE
    for item, recipient_headers, _message_id in _iter_messages_for_recipient(mail, target, cutoff, budget=budget):
        if target not in _recipient_addresses(recipient_headers):
            continue
        received_at = _message_timestamp(item)
        if received_at and received_at < cutoff:
            continue
        if not looks_like_openai_email(item):
            continue
        otp = extract_otp(item)
        if otp:
            if budget is not None:
                budget.require()
            return otp
    return None


def _deactivation_result(target: str, messages: list[tuple[dict, str, str]]) -> dict:
    from core.cf_temp_mail_client import _is_openai_deactivation

    matches: list[dict] = []
    for item, recipient_headers, message_id in messages:
        if target not in _recipient_addresses(recipient_headers):
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
    """Scan many aliases through one shared Gmail connection.

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
            indexed = _messages_for_recipients(mail, targets, since_ts)
            return {
                target: _deactivation_result(
                    target,
                    indexed.get(target, []),
                )
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
        except WAIT_INTERRUPTED:
            raise
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
    except WAIT_INTERRUPTED:
        raise
    except Exception as exc:
        raise ForwardIMAPError(f"Email Butler PG 缓存取码失败: {exc}") from exc
    finally:
        if mail is not None:
            if current_budget() is not None:
                _close_imap(mail)
                mail = None
        if mail is not None:
            try:
                mail.logout()
            except WAIT_INTERRUPTED:
                raise
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
    budget = _IMAPBudget(wait_seconds)
    mail = None
    last_error = "尚未收到新的 OpenAI 验证码邮件"
    successful_poll = False
    found_otp = None
    logger.info("[HME Forward IMAP] 本机 Gmail IMAP 等待验证码，最长 %ss", wait_seconds)
    try:
        while budget.remaining() > 0:
            if mail is None:
                try:
                    mail = _connect(budget=budget)
                    budget.require()
                except WAIT_INTERRUPTED:
                    raise
                except _IMAPDeadlineExceeded:
                    last_error = "连接阶段耗尽总预算"
                    break
                except Exception as exc:
                    last_error = type(exc).__name__
                    logger.warning("[HME Forward IMAP] 建连失败，将在剩余预算内重试：%s", last_error)
                    remaining = budget.remaining()
                    if remaining > 0:
                        bounded_sleep(min(interval, remaining))
                    continue
            try:
                otp = _latest_forwarded_otp(mail, target, anchor, budget=budget)
                budget.require()
            except WAIT_INTERRUPTED:
                raise
            except _IMAPDeadlineExceeded:
                last_error = "读取阶段耗尽总预算"
                break
            except Exception as exc:
                last_error = type(exc).__name__
                logger.warning("[HME Forward IMAP] 读取失败，将在剩余预算内重连：%s", last_error)
                _close_imap(mail)
                mail = None
            else:
                successful_poll = True
                last_error = "尚未收到新的 OpenAI 验证码邮件"
                if otp:
                    found_otp = otp
                    logger.info("[HME Forward IMAP] 本机已取得新 OTP")
                    break

            remaining = budget.remaining()
            if remaining > 0:
                bounded_sleep(min(interval, remaining))
    finally:
        started = time.monotonic()
        _close_imap(mail)
        logger.info("[HME Forward IMAP] 阶段=关闭连接 耗时=%.3fs", time.monotonic() - started)
    if found_otp:
        budget.require()
        return found_otp
    detail = f"本机 Gmail IMAP 等待验证码超时（>{wait_seconds}s）；{last_error}"
    if successful_poll and last_error == "尚未收到新的 OpenAI 验证码邮件":
        raise ForwardIMAPNoMailTimeout(detail)
    raise ForwardIMAPError(detail)
