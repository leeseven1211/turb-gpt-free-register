# -*- coding: utf-8 -*-
"""sub2api Codex OAuth 凭证导入客户端。"""
from __future__ import annotations

import json
from typing import Any

import requests


def upload_codex_oauth_credential(
    auth_json: dict[str, Any],
    api_url: str,
    *,
    api_token: str | None = None,
    auth_header: str = "x-api-key",
    auth_prefix: str = "",
    timeout: float = 20.0,
) -> dict[str, Any]:
    """把 Codex OAuth JSON 导入 sub2api 的 Codex Session 接口。"""
    if not isinstance(auth_json, dict):
        raise ValueError("Codex OAuth 凭证必须是 JSON 对象")
    refresh_token = str(auth_json.get("refresh_token") or "").strip()
    access_token = str(auth_json.get("access_token") or "").strip()
    if not refresh_token and not access_token:
        raise ValueError("Codex OAuth 凭证缺少 refresh_token/access_token")

    url = str(api_url or "").strip()
    if not url:
        raise ValueError("SUB2API_API_BASE 为空，无法上传到 sub2api")

    email = str(auth_json.get("email") or "").strip()
    account_id = str(auth_json.get("account_id") or "").strip()
    payload = {
        "contents": [json.dumps(auth_json, ensure_ascii=False)],
        "name": email or (f"codex-{account_id[:8]}" if account_id else "codex-oauth"),
        "update_existing": True,
        "concurrency": 3,
        "priority": 50,
        "confirm_mixed_channel_risk": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "turb-gpt-free-register/sub2api",
    }
    token = str(api_token or "").strip()
    header_name = str(auth_header or "x-api-key").strip() or "x-api-key"
    prefix = str(auth_prefix or "").strip()
    if token:
        headers[header_name] = f"{prefix} {token}".strip() if prefix else token

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    status = int(getattr(resp, "status_code", 0) or 0)
    text = getattr(resp, "text", "") or ""
    try:
        body = resp.json()
    except Exception:
        body = {"text": text[:1000]}
    if status < 200 or status >= 300:
        raise RuntimeError(f"sub2api 上传失败 HTTP {status}: {text[:800]}")
    if isinstance(body, dict) and body.get("code") not in (None, 0, 200):
        raise RuntimeError(f"sub2api 上传失败: {body.get('message') or body.get('error') or str(body)[:800]}")

    data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else body
    if isinstance(data, dict):
        failed = int(data.get("failed") or 0)
        if failed:
            errors = data.get("errors") if isinstance(data.get("errors"), list) else []
            detail = "; ".join(
                str(item.get("message") or item)
                for item in errors[:3]
                if isinstance(item, dict)
            )
            raise RuntimeError(f"sub2api Codex 凭证导入失败: {detail or f'failed={failed}'}")

    return {
        "ok": True,
        "uploaded": True,
        "url": url,
        "status_code": status,
        "email": email or None,
        "account_id": account_id or None,
        "total": data.get("total") if isinstance(data, dict) else None,
        "created": data.get("created") if isinstance(data, dict) else None,
        "updated": data.get("updated") if isinstance(data, dict) else None,
        "skipped": data.get("skipped") if isinstance(data, dict) else None,
        "response": body,
    }
