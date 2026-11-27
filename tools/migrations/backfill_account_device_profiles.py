#!/usr/bin/env python3
"""从私有协议会话补齐缺失设备画像；默认只读，不恢复 Cookie 或修改已有画像。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

from cryptography.fernet import Fernet, InvalidToken
from dotenv import dotenv_values
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

# 与 core.accounts.password_setup.session._REQUIRED_PROFILE_FIELDS 一致。
# 运维工具不导入业务启动模块，避免读取时触发配置、schema 或后台任务初始化。
_REQUIRED_PROFILE_FIELDS = frozenset({
    "screen_width", "screen_height", "device_pixel_ratio",
    "hardware_concurrency", "device_memory", "js_heap_size_limit",
})
_TABLES = ("registered_accounts", "account_protocol_sessions", "account_device_profiles")
_SOURCE = "account_protocol_sessions"
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class BackfillError(RuntimeError):
    """仅携带可公开的稳定分类，不包含连接信息或私有会话。"""


@dataclass(frozen=True)
class Config:
    database_url: str
    schema: str
    encryption_key: str
    source_instance: str
    allow_production: bool = False


def _digest(value) -> str:
    raw = value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise BackfillError("source_timestamp_invalid")
    return value.astimezone(timezone.utc).isoformat()


def _cipher(config: Config) -> Fernet:
    try:
        return Fernet(config.encryption_key.encode("ascii"))
    except (AttributeError, ValueError, UnicodeError):
        raise BackfillError("encryption_key_invalid") from None


def _connect(config: Config, *, read_only: bool):
    try:
        values = conninfo_to_dict(config.database_url)
    except psycopg.Error:
        raise BackfillError("database_configuration_invalid") from None
    if not config.source_instance.strip() or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config.schema):
        raise BackfillError("source_scope_invalid")
    if values.get("dbname") == "turb_console" and not config.allow_production:
        raise BackfillError("production_instance_not_authorized")
    # 独立运维连接不修改生产放行环境；测试仍必须留在开发库及独立 schema。
    if "unittest" in sys.modules and (
        values.get("dbname") == "turb_console" or not config.schema.startswith("test_")
    ):
        raise BackfillError("isolated_test_database_required")
    conn = psycopg.connect(
        config.database_url, connect_timeout=5, row_factory=dict_row,
        options="-c default_transaction_read_only=on -c statement_timeout=30000 -c lock_timeout=5000",
    )
    # service、环境变量或默认数据库也可能指向生产，必须复核连接后的真实库名。
    if conn.info.dbname == "turb_console":
        if not config.allow_production:
            conn.close()
            raise BackfillError("production_instance_not_authorized")
        if "unittest" in sys.modules:
            conn.close()
            raise BackfillError("isolated_test_database_required")
    conn.read_only = read_only
    return conn


def _scope(conn, config: Config) -> str:
    row = conn.execute(
        "SELECT current_database() db, current_user username, "
        "inet_server_addr()::text server, inet_server_port() port",
    ).fetchone()
    return _digest({
        "instance": config.source_instance, "schema": config.schema,
        "connection": conninfo_to_dict(config.database_url), "actual": row,
    })


def _require_tables(conn, config: Config) -> None:
    for table in _TABLES:
        qualified = sql.Identifier(config.schema, table).as_string(conn)
        if not conn.execute("SELECT to_regclass(%s) relation", (qualified,)).fetchone()["relation"]:
            raise BackfillError("required_table_missing")


def _device_payload(row: dict, email: str, cipher: Fernet) -> tuple[dict | None, str | None]:
    if not email or row["normalized_email"] != email:
        return None, "account_binding_changed"
    try:
        envelope = json.loads(cipher.decrypt(row["encrypted_payload"].encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeError, AttributeError):
        return None, "source_decryption_failed"
    if (
        not isinstance(envelope, dict) or type(envelope.get("version")) is not int
        or envelope["version"] != 1 or type(envelope.get("account_id")) is not int
        or envelope["account_id"] != row["account_id"] or envelope.get("email") != email
        or not isinstance(envelope.get("payload"), dict)
    ):
        return None, "envelope_binding_invalid"
    source = envelope["payload"]
    device_id, profile = source.get("device_id"), source.get("browser_profile")
    if not isinstance(device_id, str) or not device_id.strip():
        return None, "device_id_missing"
    if not isinstance(profile, dict) or not _REQUIRED_PROFILE_FIELDS.issubset(profile):
        return None, "incomplete_profile"
    payload = {"device_id": device_id, "browser_profile": profile}
    impersonate = source.get("impersonate") or profile.get("impersonate")
    if impersonate:
        payload["impersonate"] = str(impersonate)
    return payload, None


def _scan(config: Config) -> dict:
    cipher = _cipher(config)
    with _connect(config, read_only=True) as conn:
        _require_tables(conn, config)
        scope = _scope(conn, config)
        rows = conn.execute(sql.SQL("""
            SELECT s.account_id,s.normalized_email,s.encrypted_payload,s.updated_at,
                   a.email AS current_email,d.account_id AS device_account_id
            FROM {} s LEFT JOIN {} a ON a.id=s.account_id
            LEFT JOIN {} d ON d.account_id=s.account_id ORDER BY s.account_id
        """).format(
            sql.Identifier(config.schema, _SOURCE),
            sql.Identifier(config.schema, "registered_accounts"),
            sql.Identifier(config.schema, "account_device_profiles"),
        )).fetchall()
        candidates, skipped = [], Counter()
        for row in rows:
            if row["device_account_id"] is not None:
                skipped["existing_device"] += 1
                continue
            email = str(row["current_email"] or "").strip().lower()
            payload, reason = _device_payload(row, email, cipher)
            if reason:
                skipped[reason] += 1
                continue
            candidates.append({
                "account_id": row["account_id"], "email_sha256": _digest(email),
                "source_cipher_sha256": _digest(row["encrypted_payload"]),
                "source_updated_at": _utc(row["updated_at"]),
            })
    manifest = {
        "version": 1, "source": _SOURCE, "scope_sha256": scope,
        "created_at": _utc(datetime.now(timezone.utc)), "candidates": candidates,
    }
    manifest["manifest_sha256"] = _digest(manifest)
    return {"manifest": manifest, "skipped": dict(skipped), "source_count": len(rows)}


def _private_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise BackfillError("private_output_exists") from None
    except OSError:
        raise BackfillError("private_output_unavailable") from None
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _receipt_replace(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".device-profile-receipt-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_manifest(path: Path) -> dict:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            mode = os.fstat(handle.fileno())
            if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) & 0o077:
                raise BackfillError("manifest_permissions_invalid")
            value = json.load(handle)
    except (OSError, ValueError, UnicodeError):
        raise BackfillError("manifest_unreadable") from None
    if not isinstance(value, dict) or value.get("manifest_sha256") != _digest({
        key: item for key, item in value.items() if key != "manifest_sha256"
    }):
        raise BackfillError("manifest_digest_mismatch")
    if value.get("version") != 1 or value.get("source") != _SOURCE or not isinstance(value.get("candidates"), list):
        raise BackfillError("manifest_invalid")
    previous_id = 0
    for row in value["candidates"]:
        if (
            not isinstance(row, dict) or type(row.get("account_id")) is not int
            or not previous_id < row["account_id"] <= 9223372036854775807
            or not _DIGEST.fullmatch(str(row.get("email_sha256") or ""))
            or not _DIGEST.fullmatch(str(row.get("source_cipher_sha256") or ""))
        ):
            raise BackfillError("manifest_invalid")
        try:
            source_time = datetime.fromisoformat(row["source_updated_at"])
            if _utc(source_time) != row["source_updated_at"]:
                raise ValueError()
        except (KeyError, TypeError, ValueError, BackfillError):
            raise BackfillError("manifest_invalid") from None
        previous_id = row["account_id"]
    return value


def _apply_one(conn, config: Config, candidate: dict, cipher: Fernet) -> str:
    account_id = candidate["account_id"]
    account = conn.execute(
        sql.SQL("SELECT email FROM {} WHERE id=%s FOR UPDATE").format(
            sql.Identifier(config.schema, "registered_accounts")), (account_id,),
    ).fetchone()
    email = str((account or {}).get("email") or "").strip().lower()
    if not email or _digest(email) != candidate["email_sha256"]:
        return "account_changed"
    exists = conn.execute(
        sql.SQL("SELECT account_id FROM {} WHERE account_id=%s").format(
            sql.Identifier(config.schema, "account_device_profiles")), (account_id,),
    ).fetchone()
    if exists:
        return "existing_device"
    source = conn.execute(
        sql.SQL("SELECT account_id,normalized_email,encrypted_payload,updated_at FROM {} "
                "WHERE account_id=%s FOR UPDATE").format(
                    sql.Identifier(config.schema, _SOURCE)), (account_id,),
    ).fetchone()
    if not source or _utc(source["updated_at"]) != candidate["source_updated_at"] or (
        _digest(source["encrypted_payload"]) != candidate["source_cipher_sha256"]
    ):
        return "source_changed"
    payload, reason = _device_payload(source, email, cipher)
    if reason:
        return reason
    encrypted = cipher.encrypt(json.dumps({
        "version": 1, "account_id": account_id, "email": email,
        "updated_at": candidate["source_updated_at"], "payload": payload,
    }, ensure_ascii=False, allow_nan=False).encode("utf-8")).decode("ascii")
    inserted = conn.execute(sql.SQL("""
        INSERT INTO {} (account_id,normalized_email,encrypted_payload,source,last_used_at)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT (account_id) DO NOTHING RETURNING account_id
    """).format(sql.Identifier(config.schema, "account_device_profiles")), (
        account_id, email, encrypted, "session_backfill",
        datetime.fromisoformat(candidate["source_updated_at"]),
    )).fetchone()
    return "inserted" if inserted else "existing_device"


def run(config: Config, manifest_path: Path, receipt_path: Path, *, apply: bool = False) -> dict:
    """执行只读预览或固定名单补缺；不调用带隐式建表行为的业务存储 API。"""
    manifest_path, receipt_path = Path(manifest_path), Path(receipt_path)
    if manifest_path.absolute() == receipt_path.absolute():
        raise BackfillError("private_paths_conflict")
    if not apply:
        scan = _scan(config)
        manifest = scan["manifest"]
        _private_new(manifest_path, manifest)
        result = {
            "mode": "dry_run", "completed": True, "source_count": scan["source_count"],
            "candidate_count": len(manifest["candidates"]), "skipped": scan["skipped"],
            "manifest_sha256": manifest["manifest_sha256"],
        }
        _private_new(receipt_path, result)
        return result
    manifest = _read_manifest(manifest_path)
    cipher = _cipher(config)
    with _connect(config, read_only=True) as conn:
        _require_tables(conn, config)
        if _scope(conn, config) != manifest.get("scope_sha256"):
            raise BackfillError("manifest_scope_mismatch")
    result = {
        "mode": "apply", "completed": False, "candidate_count": len(manifest["candidates"]),
        "manifest_sha256": manifest["manifest_sha256"], "results": {}, "items": [],
    }
    _private_new(receipt_path, result)
    counts = Counter()
    try:
        with _connect(config, read_only=False) as conn:
            _require_tables(conn, config)
            if _scope(conn, config) != manifest.get("scope_sha256"):
                raise BackfillError("manifest_scope_mismatch")
            for candidate in manifest["candidates"]:
                outcome = _apply_one(conn, config, candidate, cipher)
                counts[outcome] += 1
                result["items"].append({"account_id": candidate["account_id"], "outcome": outcome})
    except Exception as exc:
        result.update(items=[], results={}, error_code=(
            str(exc) if isinstance(exc, BackfillError) else "database_apply_failed"
        ))
        _receipt_replace(receipt_path, result)
        raise BackfillError(result["error_code"]) from None
    result.update(completed=True, results=dict(counts))
    _receipt_replace(receipt_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="实例配置目录")
    parser.add_argument("--source-instance", required=True, help="本地与 Oracle 使用不同名称")
    parser.add_argument("--manifest", type=Path, required=True, help="固定候选清单私有路径")
    parser.add_argument("--receipt", type=Path, required=True, help="本次回执的新私有路径")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="仅应用既有固定清单")
    mode.add_argument("--dry-run", action="store_true", help="默认：只读扫描")
    args = parser.parse_args()
    try:
        values = dotenv_values(args.source_root / ".env", interpolate=False)
        config = Config(
            str(values.get("DATABASE_URL") or ""), str(values.get("TURB_DB_SCHEMA") or "public"),
            str(values.get("TURB_CONFIG_ENCRYPTION_KEY") or ""), args.source_instance,
            str(values.get("TURB_ALLOW_PRODUCTION_DB") or "") == "1",
        )
        if not config.database_url:
            raise BackfillError("database_configuration_missing")
        result = run(config, args.manifest, args.receipt, apply=args.apply)
    except Exception as exc:
        print(json.dumps({
            "ok": False, "error_code": str(exc) if isinstance(exc, BackfillError) else "backfill_failed",
        }, ensure_ascii=False))
        return 1
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
