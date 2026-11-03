# -*- coding: utf-8 -*-
"""Encrypted, account-bound protocol login sessions, never public account data."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone

from psycopg.rows import dict_row

from core.storage import postgres as postgres_store, records as record_store
from core.storage.runtime_config import decrypt_private_text, encrypt_private_text

_TABLE = "account_protocol_sessions"
_READY_KEY = ""
_LOCK = threading.RLock()
_MAX_TTL_SECONDS = 7 * 86400


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
                    expires_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        _READY_KEY = key


def save_session(account_id: int, email: str, payload: dict, *, now=None, ttl_seconds: int = 86400) -> bool:
    """Bind the ciphertext internally as well as in SQL to prevent row swapping."""
    init()
    normalized = str(email or "").strip().lower()
    if not normalized or not isinstance(payload, dict):
        raise ValueError("invalid_protocol_session")
    expires = _now(now) + timedelta(seconds=max(1, min(int(ttl_seconds), _MAX_TTL_SECONDS)))
    encrypted = encrypt_private_text(json.dumps({
        "version": 1, "account_id": int(account_id), "email": normalized,
        "expires_at": expires.isoformat(), "payload": payload,
    }, ensure_ascii=False))
    with postgres_store.connect() as conn, conn.cursor() as cur:
        # Hold the account lock so a concurrent email change cannot race the save.
        cur.execute(f"SELECT id FROM {postgres_store.qualified('registered_accounts')} WHERE id=%s AND lower(trim(email))=%s FOR UPDATE", (int(account_id), normalized))
        if not cur.fetchone():
            return False
        cur.execute(f"""
            INSERT INTO {postgres_store.qualified(_TABLE)} (account_id, normalized_email, encrypted_payload, expires_at)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (account_id) DO UPDATE SET normalized_email=EXCLUDED.normalized_email,
                encrypted_payload=EXCLUDED.encrypted_payload, expires_at=EXCLUDED.expires_at, updated_at=now()
        """, (int(account_id), normalized, encrypted, expires))
    return True


def load_session(account_id: int, email: str, *, now=None) -> dict | None:
    """Return only unexpired, decryptable data for the account's current email."""
    init()
    normalized = str(email or "").strip().lower()
    current = _now(now)
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT s.encrypted_payload FROM {postgres_store.qualified(_TABLE)} s
            JOIN {postgres_store.qualified('registered_accounts')} a ON a.id=s.account_id
            WHERE s.account_id=%s AND s.normalized_email=%s AND lower(trim(a.email))=%s AND s.expires_at>%s
        """, (int(account_id), normalized, normalized, current))
        row = cur.fetchone()
    if not row:
        return None
    try:
        value = json.loads(decrypt_private_text(row["encrypted_payload"]))
        if (value.get("version") != 1 or value.get("account_id") != int(account_id)
                or value.get("email") != normalized
                or _now(datetime.fromisoformat(value["expires_at"])) <= current
                or not isinstance(value.get("payload"), dict)):
            return None
        return value["payload"]
    except Exception:
        # No raw ciphertext or decryption exception escapes to diagnostics.
        return None


def invalidate_session(account_id: int, email: str) -> None:
    init()
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute(f"DELETE FROM {postgres_store.qualified(_TABLE)} WHERE account_id=%s AND normalized_email=%s", (int(account_id), str(email or "").strip().lower()))
