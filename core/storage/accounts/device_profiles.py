# -*- coding: utf-8 -*-
"""Account-bound device fingerprint store, independent from login sessions.

登录会话（Cookie）只该短期有效，但“这台设备上次长什么样”必须长期可查：
改密、二号验证等动作都要沿用同一套指纹，否则会被判定为新设备。
本模块只保存设备层（device_id / browser_profile / impersonate），不保存 Cookie，
也不设过期时间；加密方式与 `protocol_sessions` 一致。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from psycopg.rows import dict_row

from core.storage import postgres as postgres_store, records as record_store
from core.storage.runtime_config import decrypt_private_text, encrypt_private_text

_TABLE = "account_device_profiles"
_READY_KEY = ""
_LOCK = threading.RLock()

# 只接受设备层字段，避免把路由凭据、页面地址或调试信息落库。
_DEVICE_FIELDS = (
    "device_id",
    "browser_profile",
    "impersonate",
)


def _now(value=None):
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def init() -> None:
    global _READY_KEY
    key = (postgres_store.database_url(), postgres_store.schema_name())
    with _LOCK:
        if _READY_KEY == key:
            return
        record_store.init()
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {postgres_store.qualified(_TABLE)} (
                    account_id BIGINT PRIMARY KEY REFERENCES {postgres_store.qualified('registered_accounts')}(id) ON DELETE CASCADE,
                    normalized_email TEXT NOT NULL,
                    encrypted_payload TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    last_used_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        _READY_KEY = key


def _device_payload(source: dict) -> dict:
    payload = {}
    if source.get("device_id"):
        payload["device_id"] = str(source["device_id"])
    profile = source.get("browser_profile")
    if isinstance(profile, dict) and profile:
        payload["browser_profile"] = json.loads(json.dumps(profile, ensure_ascii=False))
    impersonate = source.get("impersonate") or (profile or {}).get("impersonate")
    if impersonate:
        payload["impersonate"] = str(impersonate)
    return payload


def save_profile(
    account_id: int,
    email: str,
    source: dict,
    *,
    origin: str = "",
    now=None,
) -> bool:
    """写入/更新账号最近一次实际使用的设备层信息；没有 device_id 直接跳过。"""
    normalized = str(email or "").strip().lower()
    payload = _device_payload(source if isinstance(source, dict) else {})
    if not normalized or not payload.get("device_id"):
        return False
    init()
    current = _now(now)
    encrypted = encrypt_private_text(json.dumps({
        "version": 1, "account_id": int(account_id), "email": normalized,
        "updated_at": current.isoformat(), "payload": payload,
    }, ensure_ascii=False))
    with postgres_store.connect() as conn, conn.cursor() as cur:
        # 与账号邮箱绑定，防止账号换绑后复用别人的设备画像。
        cur.execute(
            f"SELECT id FROM {postgres_store.qualified('registered_accounts')} "
            "WHERE id=%s AND lower(trim(email))=%s FOR UPDATE",
            (int(account_id), normalized),
        )
        if not cur.fetchone():
            return False
        cur.execute(f"""
            INSERT INTO {postgres_store.qualified(_TABLE)}
                (account_id, normalized_email, encrypted_payload, source, last_used_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,now())
            ON CONFLICT (account_id) DO UPDATE SET
                normalized_email=EXCLUDED.normalized_email,
                encrypted_payload=EXCLUDED.encrypted_payload,
                source=EXCLUDED.source,
                last_used_at=EXCLUDED.last_used_at,
                updated_at=now()
        """, (int(account_id), normalized, encrypted, str(origin or "")[:64], current))
    return True


def load_profile(account_id: int, email: str) -> dict | None:
    """读取账号的设备层信息；不存在、解密失败或邮箱已变更都返回 None。"""
    init()
    normalized = str(email or "").strip().lower()
    if not normalized:
        return None
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT d.encrypted_payload, d.source FROM {postgres_store.qualified(_TABLE)} d
            JOIN {postgres_store.qualified('registered_accounts')} a ON a.id=d.account_id
            WHERE d.account_id=%s AND d.normalized_email=%s AND lower(trim(a.email))=%s
        """, (int(account_id), normalized, normalized))
        row = cur.fetchone()
    if not row:
        return None
    try:
        value = json.loads(decrypt_private_text(row["encrypted_payload"]))
        if (value.get("version") != 1 or value.get("account_id") != int(account_id)
                or value.get("email") != normalized
                or not isinstance(value.get("payload"), dict)):
            return None
        payload = dict(value["payload"])
        if row.get("source"):
            payload["source"] = str(row["source"])
        return payload
    except Exception:
        # 解密异常不得把原始密文或堆栈泄漏到上层诊断。
        return None


def remember_session(account_id: int, email: str, session_payload: dict, *, origin: str = "") -> bool:
    """从会话缓存（cookies + 设备字段）里抽出设备层长期保存。"""
    if not account_id or not isinstance(session_payload, dict):
        return False
    try:
        return save_profile(account_id, email, session_payload, origin=origin)
    except Exception:
        return False


def forget(account_id: int, email: str) -> None:
    init()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM {postgres_store.qualified(_TABLE)} WHERE account_id=%s AND normalized_email=%s",
            (int(account_id), str(email or "").strip().lower()),
        )
