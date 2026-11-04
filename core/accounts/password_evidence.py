"""区分可恢复的密码候选与已经完成确认的账号密码。"""
from __future__ import annotations

import json
from collections.abc import Mapping


def _extra(account: Mapping | None) -> dict:
    raw = (account or {}).get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def password_is_confirmed(account: Mapping | None) -> bool:
    """旧记录只有密码值时按候选处理，不能据此跳过密码补全。"""
    extra = _extra(account)
    password = next((str(source.get(key) or "").strip()
                     for source in (extra, account or {})
                     for key in ("account_password", "login_password", "registration_password")
                     if str(source.get(key) or "").strip()), "")
    return bool(password and str((account or {}).get("access_token") or "").strip()
                and extra.get("account_password_state") == "confirmed")


def registration_password_extra(password: str | None, *, confirmed: bool) -> dict:
    """保留原密码用于恢复；注册取得 Token 且有本轮密码证据后才能确认。"""
    value = str(password or "").strip()
    return {"account_password": value,
            "account_password_state": "confirmed" if confirmed else "candidate"} if value else {}


__all__ = ["password_is_confirmed", "registration_password_extra"]
