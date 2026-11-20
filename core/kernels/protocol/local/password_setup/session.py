"""Cookie source conversion without account storage or cache policy."""

from __future__ import annotations
import json


def _object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def saved_token_session(account, *, _object=_object):
    """保存的 sessionToken 才是 Cookie 凭据，普通会话 JSON 和 AT 不作替代。"""
    info = _object(account.get("chatgpt_session"))
    token = next(
        (
            value.strip()
            for key in ("sessionToken", "session_token")
            if isinstance(value := info.get(key), str) and value.strip()
        ),
        "",
    )
    if not token:
        return None
    user, target = _object(info.get("user")), _object(info.get("account"))
    device_id = _object(account.get("extra_json")).get("device_id")
    return {
        "device_id": device_id.strip() if isinstance(device_id, str) else "",
        "user_id": str(user.get("id") or ""),
        "chatgpt_account_id": str(target.get("id") or ""),
        "cookies": [
            {
                "name": "__Secure-next-auth.session-token",
                "value": token,
                "domain": "chatgpt.com",
                "path": "/",
                "secure": True,
                "expires": None,
            }
        ],
    }
