# -*- coding: utf-8 -*-
"""Read and persist the account-level Roxy Profile binding."""
from __future__ import annotations

import json
from collections.abc import Mapping


def _account_extra(account: Mapping | None) -> dict:
    if not isinstance(account, Mapping):
        return {}
    raw = account.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def account_profile_id(account: Mapping | None) -> str:
    """Return a retained account Profile ID, or empty when none is usable."""
    binding = _account_extra(account).get("roxybrowser")
    if not isinstance(binding, Mapping):
        return ""
    retained = binding.get("retained", True)
    if isinstance(retained, str) and retained.strip().lower() in {"0", "false", "no", "off"}:
        return ""
    if retained is False or retained == 0:
        return ""
    return str(binding.get("profile_id") or "").strip()


def account_profile_id_by_email(email: str, *, strict: bool = False) -> str:
    """Load only the account Profile ID needed by a browser operation.

    ``strict`` prevents a storage outage from being mistaken for an account
    with no binding, which would otherwise consume another Roxy create slot.
    """
    address = str(email or "").strip()
    if not address:
        return ""
    try:
        from core import db

        return account_profile_id(db.get_account_by_email(address))
    except Exception:
        if strict:
            raise
        return ""


def persist_account_profile_id(email: str, profile_id: str, *, retained: bool = True) -> bool:
    """Persist the Profile binding without replacing account credentials."""
    address = str(email or "").strip()
    profile = str(profile_id or "").strip()
    if not address or not profile:
        return False
    from core import db

    return bool(db.update_account_roxy_profile(address, profile, retained=retained))


__all__ = ["account_profile_id", "account_profile_id_by_email", "persist_account_profile_id"]
