# -*- coding: utf-8 -*-
"""Read-only, non-logging access to saved OpenAI account credentials.

The email provider password is deliberately not considered here.  Only the
OpenAI account password stored in the account's controlled ``extra_json`` and
the account's TOTP secret are returned to an authentication adapter in memory.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class _CredentialOverride:
    email: str
    password: str = field(repr=False)
    totp_secret: str = field(repr=False)


_CREDENTIAL_OVERRIDE: ContextVar[_CredentialOverride | None] = ContextVar(
    "account_login_credentials_override", default=None,
)


@contextmanager
def override_account_login_credentials(email: str, password: str, totp_secret: str = ""):
    """在当前认证上下文临时提供候选凭据，不影响其他账号或线程。"""
    override = _CredentialOverride(
        email=str(email or "").strip().casefold(),
        password=str(password or "").strip(),
        totp_secret=str(totp_secret or "").strip(),
    )
    token = _CREDENTIAL_OVERRIDE.set(override)
    try:
        yield
    finally:
        _CREDENTIAL_OVERRIDE.reset(token)


def account_email_is_invalid(email: str) -> bool:
    """读取账号独立的邮箱失效标记，不据认证错误推断邮箱状态。"""
    try:
        from core import db

        account = db.get_account_by_email(email) or {}
    except Exception:
        return False
    return account.get("email_invalid") is True


def get_account_totp_secret_candidate(account: dict | None) -> str:
    """优先读取正式密钥，缺失时仅将待确认检查点作为登录候选，不改变启用状态。"""
    account = account or {}
    active_secret = str(account.get("totp_secret") or "").strip()
    if active_secret:
        return active_secret
    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError):
            raw_extra = {}
    if not isinstance(raw_extra, dict):
        return ""
    return str(raw_extra.get("totp_pending_secret") or "").strip()


def get_account_login_credentials(email: str) -> tuple[str, str]:
    """Return ``(OpenAI password, TOTP secret)`` without logging either value."""
    override = _CREDENTIAL_OVERRIDE.get()
    normalized_email = str(email or "").strip().casefold()
    if override is not None and normalized_email == override.email:
        return override.password, override.totp_secret
    try:
        from core import db

        account = db.get_account_by_email(email) or {}
    except Exception:
        return "", ""

    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    password = ""
    if isinstance(raw_extra, dict):
        password = str(
            raw_extra.get("account_password")
            or raw_extra.get("login_password")
            or raw_extra.get("registration_password")
            or ""
        ).strip()
    if not password:
        # A few historical imports kept the OpenAI password as a top-level
        # compatibility field.  Never inspect ``account.password`` here: that
        # field belongs to the email provider and must not be used for OpenAI.
        password = str(
            account.get("account_password")
            or account.get("login_password")
            or account.get("registration_password")
            or ""
        ).strip()
    totp_secret = get_account_totp_secret_candidate(account)
    return password, totp_secret
