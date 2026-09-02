# -*- coding: utf-8 -*-
"""Read-only, non-logging access to saved OpenAI account credentials.

The email provider password is deliberately not considered here.  Only the
OpenAI account password stored in the account's controlled ``extra_json`` and
the account's TOTP secret are returned to an authentication adapter in memory.
"""
from __future__ import annotations

import json


def get_account_login_credentials(email: str) -> tuple[str, str]:
    """Return ``(OpenAI password, TOTP secret)`` without logging either value."""
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
    totp_secret = str(account.get("totp_secret") or "").strip()
    return password, totp_secret
