# -*- coding: utf-8 -*-
"""把 sub2api OpenAI OAuth 账号资料同步到本地账号与 Codex 存储。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Iterable

from core import db, record_store
from core.account_credentials import get_account_login_credentials

DEFAULT_SYNC_PROXY_REGION = "US"
_HTTP_STATUS_RE = re.compile(r"(?:HTTP\s*)?\(?\b([45]\d{2})\b\)?", re.IGNORECASE)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def merge_sync_metadata(existing: Any, updates: dict[str, Any]) -> dict[str, Any]:
    """合并同步标记，保留本地扩展字段和密码。"""
    merged = _as_dict(existing)
    merged.update(dict(updates or {}))
    return merged


def _has_local_password(account: dict[str, Any] | None) -> bool:
    if not account:
        return False
    password, _ = get_account_login_credentials(str(account.get("email") or ""))
    if password:
        return True
    extra = _as_dict(account.get("extra_json"))
    return bool(
        str(
            extra.get("account_password")
            or extra.get("login_password")
            or extra.get("registration_password")
            or account.get("password")
            or account.get("login_password")
            or account.get("registration_password")
            or ""
        ).strip()
    )


def _credential(raw: dict[str, Any]) -> dict[str, Any]:
    value = raw.get("credentials")
    return dict(value) if isinstance(value, dict) else {}


def _email(raw: dict[str, Any], credentials: dict[str, Any]) -> str:
    return str(credentials.get("email") or raw.get("name") or "").strip()


def build_sub2api_status(raw: dict[str, Any]) -> dict[str, Any]:
    """提取 Sub2API 远端状态；401 表示远端 OAuth Token revoked。"""
    if "status" not in raw and "error_message" not in raw:
        return {}
    status = str(raw.get("status") or "").strip().lower()
    error_message = str(raw.get("error_message") or "").strip()
    match = _HTTP_STATUS_RE.search(error_message)
    result: dict[str, Any] = {"sub2api_status": status, "sub2api_http_status": None}
    if match:
        result["sub2api_http_status"] = int(match.group(1))
    return result


def build_account_sync_payload(
    raw: dict[str, Any],
    *,
    existing: dict[str, Any] | None,
    email_source: str = "email_butler",
    proxy_region: str = DEFAULT_SYNC_PROXY_REGION,
) -> dict[str, Any]:
    """构造本地账号的增量字段；已有账号不返回敏感/来源字段。"""
    credentials = _credential(raw)
    email = _email(raw, credentials)
    if not email or "@" not in email:
        raise ValueError("sub2api 账号缺少有效邮箱")
    access_token = str(credentials.get("access_token") or "").strip()
    if not access_token:
        raise ValueError(f"sub2api 账号缺少 access_token: {email}")

    has_password = _has_local_password(existing)
    has_totp = bool(str((existing or {}).get("totp_secret") or "").strip())
    metadata = {
        "sub2api_account_id": raw.get("id"),
        "sub2api_platform": str(raw.get("platform") or "openai"),
        "sub2api_type": str(raw.get("type") or "oauth"),
        **build_sub2api_status(raw),
        "sub2api_synced_at": _now(),
        "account_password_missing": not has_password,
        "totp_missing": not has_totp,
        "email_source_expected": str(email_source or "email_butler"),
    }
    payload: dict[str, Any] = {
        "email": email,
        "access_token": access_token,
        "user_id": credentials.get("chatgpt_user_id") or credentials.get("user_id"),
        "plan_type": credentials.get("plan_type"),
        "expires_at": credentials.get("expires_at"),
        "registration_proxy_region": str(proxy_region or "").strip().upper() or None,
        "extra": merge_sync_metadata((existing or {}).get("extra_json"), metadata),
    }
    if existing is None:
        payload["email_source"] = str(email_source or "email_butler").strip() or "email_butler"
    return payload


def build_codex_filename(email: str, plan: str | None) -> str:
    safe_email = str(email or "").strip().replace("/", "_").replace("\\", "_").replace("..", "_")
    normalized_plan = str(plan or "free").strip().lower() or "free"
    return f"codex-{safe_email}-{normalized_plan}.json"


def build_codex_content(raw: dict[str, Any]) -> dict[str, Any]:
    credentials = _credential(raw)
    email = _email(raw, credentials)
    if not email or "@" not in email:
        raise ValueError("sub2api Codex 凭证缺少有效邮箱")
    if not str(credentials.get("refresh_token") or credentials.get("access_token") or "").strip():
        raise ValueError(f"sub2api Codex 凭证缺少 token: {email}")
    content = dict(credentials)
    content.setdefault("type", "codex")
    content["email"] = email
    if not content.get("account_id") and content.get("chatgpt_account_id"):
        content["account_id"] = content["chatgpt_account_id"]
    return content


def missing_account_fields(account: dict[str, Any]) -> list[str]:
    """返回后续账号操作仍缺少的本地资料字段。"""
    missing: list[str] = []
    if not _has_local_password(account):
        missing.append("account_password")
    if not str(account.get("totp_secret") or "").strip():
        missing.append("totp_secret")
    if str(account.get("email_source") or "").strip().lower() != "email_butler":
        missing.append("email_source=email_butler")
    if not str(account.get("registration_proxy_provider") or "").strip():
        missing.append("registration_proxy_provider")
    if not str(account.get("registration_proxy_region") or "").strip():
        missing.append("registration_proxy_region")
    return missing


def sync_sub2api_records(
    records: Iterable[dict[str, Any]],
    *,
    email_source: str = "email_butler",
    sync_codex: bool = True,
) -> dict[str, Any]:
    """幂等同步账号和 Codex 凭证，绝不创建 OAuth 重授权任务。"""
    # 旧迁移可能保留了手工导入的高位 id，但没有同步 PostgreSQL identity
    # sequence；先校准，避免第一条新增账号因主键冲突被跳过。
    record_store.sync_identity(record_store.ACCOUNTS)
    if sync_codex:
        record_store.sync_identity(record_store.CODEX_CREDENTIALS)
    existing_accounts = {
        str(row.get("email") or "").strip().lower(): row
        for row in db.list_accounts(limit=5000, offset=0, archived="all")
        if str(row.get("email") or "").strip()
    }
    existing_codex = {
        str(row.get("email") or "").strip().lower(): row
        for row in db.list_codex_accounts(archived="all")
        if str(row.get("email") or "").strip()
    }
    summary: dict[str, Any] = {
        "accounts_created": 0,
        "accounts_updated": 0,
        "codex_created": 0,
        "codex_updated": 0,
        "failed": [],
        "items": [],
    }
    for raw in records:
        try:
            credentials = _credential(raw)
            email = _email(raw, credentials)
            key = email.lower()
            existing = existing_accounts.get(key)
            account_payload = build_account_sync_payload(
                raw,
                existing=existing,
                email_source=email_source,
            )
            extra = account_payload.pop("extra")
            account_payload["extra_json"] = json.dumps(extra, ensure_ascii=False)
            if existing is None:
                account_id = record_store.upsert_row_by(record_store.ACCOUNTS, "email", account_payload)
                summary["accounts_created"] += 1
                account = {**account_payload, "id": account_id}
            else:
                record_store.patch_row(record_store.ACCOUNTS, int(existing["id"]), account_payload)
                summary["accounts_updated"] += 1
                account = {**existing, **account_payload, "extra_json": account_payload["extra_json"]}
            existing_accounts[key] = account

            codex_filename = None
            if sync_codex:
                content = build_codex_content(raw)
                old_codex = existing_codex.get(key)
                codex_filename = str(old_codex.get("filename") or "") if old_codex else ""
                if not codex_filename:
                    codex_filename = build_codex_filename(email, content.get("plan_type"))
                db.save_codex_credential_record(codex_filename, content)
                record_store.patch_row(
                    record_store.CODEX_CREDENTIALS,
                    int(record_store.get_row_by(
                        record_store.CODEX_CREDENTIALS,
                        "filename",
                        codex_filename,
                    )["id"]),
                    build_sub2api_status(raw),
                )
                if old_codex:
                    summary["codex_updated"] += 1
                else:
                    summary["codex_created"] += 1
                existing_codex[key] = {"filename": codex_filename, "email": email}

            refreshed = db.get_account_by_email(email) or account
            summary["items"].append({
                "email": email,
                "account_id": int(refreshed.get("id") or account.get("id") or 0),
                "codex_filename": codex_filename,
                "missing_fields": missing_account_fields(refreshed),
            })
        except Exception as exc:
            summary["failed"].append({
                "email": _email(raw, _credential(raw)),
                "error": f"{type(exc).__name__}: {exc}",
            })
    summary["failed_count"] = len(summary["failed"])
    summary["item_count"] = len(summary["items"])
    return summary
