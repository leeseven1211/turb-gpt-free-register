# -*- coding: utf-8 -*-
"""派生邮箱认证串行化：同一完整地址只允许一个远端认证执行。"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import inspect
import logging
import math
import os
import threading
from typing import Any, Iterator
import uuid

from core.storage.email import address_allocations as store

logger = logging.getLogger('core.email_auth_guard')
LEASE_SECONDS = 180
HEARTBEAT_SECONDS = 60
_SESSIONS: ContextVar[tuple["EmailAuthSession", ...]] = ContextVar("email_auth_sessions", default=())
_OBSERVER_ADDRESS: ContextVar[str | None] = ContextVar("email_auth_observer_address", default=None)
_OBSERVER_REQUEST: ContextVar[tuple[str, int, int] | None] = ContextVar("email_auth_observer_request", default=None)
_UNSET = object()


def _binding(email: str) -> dict | None:
    # 普通地址不查询新账本，也不启动心跳。包含 + 但无持久绑定的地址沿用原路径。
    if not email or "+" not in email.rsplit("@", 1)[0]:
        return None
    from core.email.derivation import find_binding

    local = find_binding(email)
    if local is not None:
        return local
    from core.email.email_butler.client import _restore_hme_context, restore_account_context, restore_local_account

    remote = restore_local_account(email) or _restore_hme_context(email)
    if remote is None:
        from core import db
        account = db.get_account_by_email(email)
        if (account or {}).get("email_source") == "email_butler":
            # Imported complete identities must be resolved before any auth
            # side effect. requested_email is an exact restore, never a claim.
            remote = restore_account_context(email, purpose="auth-identity")
    if remote is not None and remote.identity_type != "primary":
        return {"id": None, "address_norm": email}
    return None


def _owner() -> tuple[str, str, int | None]:
    from core.registration.service import registration_fact_context

    facts = registration_fact_context() or {}
    attempt = facts.get("attempt_id")
    if attempt:
        return "registration_attempt", str(attempt), int(attempt)
    root = facts.get("root_task_id") or facts.get("root_job_id") or facts.get("job_id")
    if root:
        return "registration_root", str(root), None
    return "auth_execution", uuid.uuid4().hex, None


def _expiry_is_live(value: Any) -> bool:
    try:
        expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


def _generation_marker(requested_at: float | str | None) -> str:
    if requested_at is None:
        return "unspecified"
    if isinstance(requested_at, (int, float)):
        value = float(requested_at)
        if not math.isfinite(value):
            raise ValueError("验证码时间边界必须是有效时间")
        return str(value)
    value = str(requested_at).strip()
    try:
        numeric = float(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return str(parsed.timestamp())
    if not math.isfinite(numeric):
        raise ValueError("验证码时间边界必须是有效时间")
    return str(numeric)


def _result_dict(result: Any) -> dict:
    if isinstance(result, dict):
        return result
    converter = getattr(result, "as_dict", None)
    return converter() if callable(converter) else {}


def _unknown_result(result: Any) -> bool:
    data = _result_dict(result)
    nested = data.get("result_summary") or {}
    return bool(
        data.get("reconcile_required")
        or data.get("result_unknown")
        or data.get("outcome") == "request_unknown"
        or str(data.get("status") or "") in {"request_unknown", "attention_required", "result_unknown"}
        or isinstance(nested, dict) and (nested.get("reconcile_required") or nested.get("outcome") == "request_unknown")
    )


def _successful_result(result: Any) -> bool:
    data = _result_dict(result)
    return not _unknown_result(result) and bool(
        data.get("ok") is True or data.get("success") is True or data.get("registration_success") is True
        or str(data.get("status") or "") in {"success", "succeeded", "live", "completed"}
    )


def _failed_result(result: Any) -> bool:
    data = _result_dict(result)
    status = str(data.get("status") or "")
    if status in {"skipped", "not_needed", "disabled"}:
        return False
    return status in {"failed", "invalid", "cancelled", "deactivated", "rejected"} or data.get("ok") is False or data.get("success") is False


@dataclass
class EmailAuthSession:
    email: str
    binding_id: int | None
    owner_kind: str
    owner_id: str
    attempt_id: int | None
    execution_token: str = field(default_factory=lambda: uuid.uuid4().hex)
    process_id: int = field(default_factory=os.getpid)
    thread_id: int = field(default_factory=threading.get_ident)
    row: dict = field(default_factory=dict)
    result: Any = None
    unknown: bool = False
    marker: Any = field(default_factory=lambda: _UNSET)
    invalid: bool = False
    lock: Any = field(default_factory=threading.RLock)
    stop_event: Any = field(default_factory=threading.Event)
    heartbeat_thread: threading.Thread | None = None

    def _fence(self) -> dict:
        return {"execution_token": self.execution_token, "fence": int(self.row["fence"])}

    def check(self) -> dict:
        with self.lock:
            if self.invalid or self.stop_event.is_set():
                raise store.StaleOtpFence("邮箱认证执行资格已经失效")
            row = store.get_otp_request(int(self.row["id"]))
            if not row or row.get("state") != "active" or row.get("execution_token") != self.execution_token or int(row.get("fence") or 0) != int(self.row["fence"]) or not _expiry_is_live(row.get("lease_expires_at")):
                self.invalid = True
                raise store.StaleOtpFence("邮箱认证执行资格已经失效")
            self.row = row
            return row

    def start(self) -> None:
        self.row = store.acquire_otp_request(
            address=self.email, address_binding_id=self.binding_id,
            owner_kind=self.owner_kind, owner_id=self.owner_id, attempt_id=self.attempt_id,
            execution_token=self.execution_token, lease_seconds=LEASE_SECONDS,
        )
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="email-auth-heartbeat", daemon=True)
        self.heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.wait(HEARTBEAT_SECONDS):
            try:
                with self.lock:
                    if self.stop_event.is_set():
                        return
                    self.row = store.renew_otp_lease(int(self.row["id"]), lease_seconds=LEASE_SECONDS, **self._fence())
            except Exception:
                # 心跳失败后禁止继续接受候选；原事实及到期时间仍由 PostgreSQL 保留。
                with self.lock:
                    self.invalid = True
                return

    def set_result(self, result: Any) -> None:
        with self.lock:
            self.result = result
            # 外层注册成功不能替嵌套 Codex 的失败 challenge 提供提交成功证据。
            if _unknown_result(result) or (_failed_result(result) and self.row.get("submission_state") in {"offered", "started"}):
                self.unknown = True

    def _preserve_unknown(self) -> None:
        self.row = store.record_otp_submission(int(self.row["id"]), submission_state="result_unknown", **self._fence())

    def next_generation(self, requested_at: float | str | None) -> dict:
        marker = _generation_marker(requested_at)
        with self.lock:
            self.check()
            if self.marker is not _UNSET and marker == self.marker:
                return dict(self.row)
            if self.unknown:
                self._preserve_unknown()
            # 初次发码也生成独立 challenge；认证入口的 prepared 行只用于提前占有完整地址。
            self.row = store.acquire_otp_request(
                address=self.email, address_binding_id=self.binding_id,
                owner_kind=self.owner_kind, owner_id=self.owner_id, attempt_id=self.attempt_id,
                challenge_id=uuid.uuid4().hex, execution_token=self.execution_token,
                new_generation=True, lease_seconds=LEASE_SECONDS,
            )
            self.row = store.update_otp_send(
                int(self.row["id"]), send_state="prepared", cursor={"requested_after": marker}, **self._fence(),
            )
            self.marker = marker
            self.unknown = False
            return dict(self.row)

    def candidate(self, message_key: str, evidence: dict | None, cursor: dict | None) -> dict:
        with self.lock:
            self.check()
            _check_observer_generation(self)
            observed_key = str(message_key or "").strip()
            observed_evidence = dict(evidence or {})
            if not observed_key:
                observed_key = f"unknown:{uuid.uuid4().hex}"
                observed_evidence["message_mapping"] = "unknown"
                self.unknown = True
            observed_cursor = {**dict(self.row.get("cursor") or {}), **dict(cursor or {})}
            self.row = store.record_otp_candidate(
                int(self.row["id"]), message_key=observed_key, evidence=observed_evidence,
                cursor=observed_cursor, **self._fence(),
            )
            self.row = store.record_otp_submission(int(self.row["id"]), submission_state="offered", **self._fence())
            return dict(self.row)

    def close(self) -> None:
        self.stop_event.set()
        thread = self.heartbeat_thread
        if thread is not None and thread.ident is not None:
            thread.join()
        if not self.row:
            return
        with self.lock:
            try:
                success = _successful_result(self.result) and not self.unknown
                if self.unknown or (self.row.get("submission_state") in {"offered", "started"} and not success):
                    self._preserve_unknown()
                self.row = store.finish_otp_request(
                    int(self.row["id"]), state="confirmed" if success else "cancelled", **self._fence(),
                )
            except store.StaleOtpFence:
                # 新执行已接管或租约已过期，旧执行不能再改写当前认证事实。
                pass
            except Exception:
                logger.warning("结束邮箱认证租约失败，既有租约将按原到期时间失效")


def current_session() -> EmailAuthSession | None:
    process_id = os.getpid()
    address = _OBSERVER_ADDRESS.get()
    if address == "":
        return None
    return next((session for session in reversed(_SESSIONS.get()) if session.process_id == process_id and (address is None or session.email == address)), None)


@contextmanager
def email_auth_session(email: str) -> Iterator[EmailAuthSession | None]:
    """为持久派生地址取得认证资格，同线程嵌套调用复用本次执行。"""
    address = str(email or "").strip().lower()
    process_id, thread_id = os.getpid(), threading.get_ident()
    existing = next((session for session in reversed(_SESSIONS.get()) if session.email == address and session.process_id == process_id and session.thread_id == thread_id), None)
    if existing is not None:
        existing.check()
        token = _SESSIONS.set((*_SESSIONS.get(), existing))
        address_token = _OBSERVER_ADDRESS.set(address)
        try:
            yield existing
            existing.check()
        except BaseException:
            existing.unknown = True
            raise
        finally:
            _OBSERVER_ADDRESS.reset(address_token)
            _SESSIONS.reset(token)
        return
    binding = _binding(address)
    if binding is None:
        # 普通邮箱的嵌套认证不继承另一完整地址的候选观测上下文。
        address_token = _OBSERVER_ADDRESS.set("")
        try:
            yield None
        finally:
            _OBSERVER_ADDRESS.reset(address_token)
        return
    kind, owner_id, attempt_id = _owner()
    session = EmailAuthSession(address, int(binding["id"]) if binding["id"] is not None else None, kind, owner_id, attempt_id)
    token = _SESSIONS.set((*_SESSIONS.get(), session))
    address_token = _OBSERVER_ADDRESS.set(address)
    observer_token = _OBSERVER_REQUEST.set(None)
    try:
        session.start()
        session.check()
        yield session
        session.check()
    except BaseException:
        session.unknown = True
        raise
    finally:
        try:
            session.close()
        finally:
            _OBSERVER_REQUEST.reset(observer_token)
            _OBSERVER_ADDRESS.reset(address_token)
            _SESSIONS.reset(token)


def serialize_email_auth(function):
    """保留入口签名，在任何远端认证动作之前锁住完整派生地址。"""
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        arguments = signature.bind(*args, **kwargs)
        with email_auth_session(arguments.arguments.get("email", "")) as session:
            result = function(*args, **kwargs)
            if session is not None:
                session.set_result(result)
            return result

    return wrapped


def _check_observer_generation(session: EmailAuthSession) -> None:
    expected = _OBSERVER_REQUEST.get()
    if expected is not None and expected[0] == session.execution_token and expected[1:] != (int(session.row["id"]), int(session.row["fence"])):
        raise store.StaleOtpFence("旧验证码代次的候选已经失效")


def bind_auth_observer(function):
    """显式把当前执行的观察上下文交给阻塞取码线程，不授予跨线程认证重入资格。"""
    if current_session() is None:
        return function
    sessions, request, address = _SESSIONS.get(), _OBSERVER_REQUEST.get(), _OBSERVER_ADDRESS.get()

    @wraps(function)
    def observed(*args, **kwargs):
        sessions_token = _SESSIONS.set(sessions)
        request_token = _OBSERVER_REQUEST.set(request)
        address_token = _OBSERVER_ADDRESS.set(address)
        try:
            checkpoint()
            result = function(*args, **kwargs)
            checkpoint()
            return result
        finally:
            _OBSERVER_ADDRESS.reset(address_token)
            _OBSERVER_REQUEST.reset(request_token)
            _SESSIONS.reset(sessions_token)

    return observed


def checkpoint() -> None:
    """候选返回与认证结束前验证 PostgreSQL 中的执行 fence。"""
    session = current_session()
    if session is not None:
        with session.lock:
            session.check()
            _check_observer_generation(session)


def begin_generation(requested_at: float | str | None) -> dict | None:
    """每次发码时间变化时建立新 challenge，同一边界的轮询复用原 generation。"""
    session = current_session()
    if session is None:
        return None
    row = session.next_generation(requested_at)
    _OBSERVER_REQUEST.set((session.execution_token, int(row["id"]), int(row["fence"])))
    return row


def observe_candidate(message_key: str, evidence: dict | None = None, cursor: dict | None = None) -> dict | None:
    """只保存候选消息身份与收件人证据，不接收验证码或推断远端提交成功。"""
    session = current_session()
    return session.candidate(message_key, evidence, cursor) if session is not None else None
