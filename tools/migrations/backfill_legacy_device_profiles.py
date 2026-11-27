#!/usr/bin/env python3
"""从账号旧字段补齐缺失设备资料；保留历史来源，不宣称原始注册快照。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import stat

from dotenv import dotenv_values
from psycopg import sql

try:
    from tools.migrations import backfill_account_device_profiles as shared
except ModuleNotFoundError:
    import backfill_account_device_profiles as shared

Config = shared.Config
BackfillError = shared.BackfillError
_SOURCE = "registered_accounts_legacy_device_profiles"
_KINDS = {"legacy_extra_json", "legacy_account_data"}
_REQUIRED = shared._REQUIRED_PROFILE_FIELDS

# 来源：auth._STABLE_PROFILE_FIELDS 与 Proto2 上游 fingerprint/sentinel_runner。
# 不含页面样本、build_id、URL、geo、Cookie、Token、代理、react/session/trace 标识。
_SCALAR_FIELDS = frozenset({
    "device_os", "screen_width", "screen_height", "screen_avail_width", "screen_avail_height",
    "outer_width", "outer_height", "inner_width", "inner_height", "viewport_width", "viewport_height",
    "color_depth", "device_pixel_ratio", "hardware_concurrency", "device_memory", "js_heap_size_limit",
    "browser_family", "browser_type", "browser_os", "navigator_platform", "navigator_vendor",
    "user_agent_data_platform", "safari_version", "safari_webkit_version", "chrome_major",
    "chrome_full_version", "user_agent", "send_client_hints", "sec_ch_ua", "sec_ch_ua_platform",
    "sec_ch_ua_platform_version", "sec_ch_ua_arch", "sec_ch_ua_bitness", "sec_ch_ua_model",
    "sec_ch_ua_full_version_list", "sec_ch_ua_mobile", "impersonate", "navigator_language",
    "accept_language", "timezone_iana", "timezone_offset_minutes", "timezone_name", "locale_profile",
    "webgl_vendor", "webgl_renderer", "max_touch_points", "screen", "lang", "lang_full", "locale",
    "timezone", "country_code", "is_mobile", "has_touch", "fingerprint_id", "akamai_fp",
    "client_hints_high_entropy", "ua_full_version_list", "ua_arch", "ua_bitness", "ua_model",
    "ua_platform_version",
})
_LIST_FIELDS = frozenset({"navigator_languages", "languages", "fallback_impersonates"})
_TLS_FIELDS = frozenset({
    "tls_permute_extensions", "tls_grease", "tls_signature_algorithms", "tls_record_size_limit",
    "http2_stream_weight", "http2_stream_exclusive", "http2_no_priority",
})
_POLICY = shared._digest({
    "version": 1, "scalar": sorted(_SCALAR_FIELDS), "lists": sorted(_LIST_FIELDS),
    "tls": sorted(_TLS_FIELDS), "viewport": ["height", "width"],
})


def _object(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _scalar(value) -> bool:
    return value is None or isinstance(value, (str, bool, int)) or (
        isinstance(value, float) and math.isfinite(value)
    )


def _clean_profile(profile: dict) -> dict:
    result = {key: value for key, value in profile.items() if key in _SCALAR_FIELDS and _scalar(value)}
    for key in _LIST_FIELDS:
        if key not in profile:
            continue
        value = profile[key]
        if value is None or isinstance(value, list) and all(isinstance(item, str) for item in value):
            result[key] = value
    if "tls_fp" in profile:
        value = profile["tls_fp"]
        if isinstance(value, dict):
            result["tls_fp"] = {
                key: item for key, item in value.items() if key in _TLS_FIELDS and (
                    _scalar(item) or key == "tls_signature_algorithms" and isinstance(item, list)
                    and all(isinstance(algorithm, str) for algorithm in item)
                )
            }
        elif _scalar(value):
            result["tls_fp"] = value
    if "viewport" in profile:
        value = profile["viewport"]
        if isinstance(value, dict):
            result["viewport"] = {key: item for key, item in value.items()
                                  if key in {"width", "height"} and _scalar(item)}
        elif value is None:
            result["viewport"] = None
    return json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False))


def _is_rust(value) -> bool:
    driver = str(value or "").strip().lower().replace("-", "_")
    return driver.startswith("rust") or "sentinel_rs" in driver


def _positive_finite(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _extract(data: dict) -> tuple[dict | None, str | None, str | None]:
    extra = _object(data.get("extra_json"))
    if _is_rust(data.get("registration_driver")) or _is_rust(extra.get("registration_driver")):
        return None, None, "rust_registration_placeholder"
    top_device, extra_device = data.get("device_id"), extra.get("device_id")
    top_profile, extra_profile = data.get("browser_profile"), extra.get("browser_profile")
    sources = (("legacy_extra_json", extra_device, extra_profile),
               ("legacy_account_data", top_device, top_profile))
    complete, invalid_numeric = [], False
    for kind, device, profile in sources:
        if not _text(device) or not isinstance(profile, dict) or not profile or not _REQUIRED.issubset(profile):
            continue
        if not all(_positive_finite(profile[key]) for key in _REQUIRED):
            invalid_numeric = True
            continue
        complete.append((kind, device, profile))
    if len(complete) == 2 and complete[0][1:] != complete[1][1:]:
        return None, None, "source_conflict"
    if complete:
        kind, device, profile = complete[0]
        clean = _clean_profile(profile)
        payload = {"device_id": device, "browser_profile": clean}
        if "impersonate" in clean:
            payload["impersonate"] = clean["impersonate"]
        return payload, kind, None
    if invalid_numeric:
        return None, None, "profile_numeric_invalid"
    return None, None, "incomplete_source_pair"


def _source_digest(data: dict) -> str:
    extra = _object(data.get("extra_json"))
    keys = ("device_id", "browser_profile", "registration_driver")
    return shared._digest({
        "top": {key: data.get(key) for key in keys},
        "extra": {key: extra.get(key) for key in keys},
    })


def _source_time(value: str, observed_at: str) -> tuple[str, str]:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            # 无时区历史值只作源版本围栏，不能猜服务器当时的本地时区。
            return shared._utc(datetime.fromisoformat(observed_at)), "migration_observed"
        return shared._utc(parsed), "source_row_updated"
    except (ValueError, TypeError):
        raise BackfillError("source_timestamp_invalid") from None


def _require_tables(conn, config: Config) -> None:
    for name in ("registered_accounts", "account_device_profiles"):
        identifier = sql.Identifier(config.schema, name).as_string(conn)
        if not conn.execute("SELECT to_regclass(%s) relation", (identifier,)).fetchone()["relation"]:
            raise BackfillError("required_table_missing")


def _candidate(row: dict, observed_at: str) -> tuple[dict | None, str | None]:
    data = _object(row["data"])
    payload, kind, reason = _extract(data)
    if reason:
        return None, reason
    email = str(row["email"] or "").strip().lower()
    if not email:
        return None, "account_email_missing"
    try:
        row_updated = row["updated_at"]
        if not isinstance(row_updated, str) or not row_updated:
            raise BackfillError("source_timestamp_invalid")
        if data.get("updated_at") is not None and not isinstance(data["updated_at"], str):
            raise BackfillError("source_timestamp_invalid")
        last_used, basis = _source_time(row_updated, observed_at)
        result = {
            "account_id": row["id"], "email_sha256": shared._digest(email),
            "source_kind": kind, "source_sha256": _source_digest(data),
            "row_updated_at": row_updated, "data_updated_at": data.get("updated_at"),
            "source_last_used_at": last_used, "time_basis": basis,
            "payload_sha256": shared._digest(payload),
        }
    except (ValueError, TypeError, BackfillError):
        return None, "source_timestamp_or_payload_invalid"
    return result, None


def _scan(config: Config) -> dict:
    shared._cipher(config)
    candidates, skipped, sources = [], Counter(), Counter()
    observed_at = shared._utc(datetime.now(timezone.utc))
    with shared._connect(config, read_only=True) as conn:
        _require_tables(conn, config)
        scope = shared._scope(conn, config)
        rows = conn.execute(sql.SQL("""
            SELECT a.id,a.email,a.updated_at,a.data,d.account_id device_account_id
            FROM {} a LEFT JOIN {} d ON d.account_id=a.id ORDER BY a.id
        """).format(
            sql.Identifier(config.schema, "registered_accounts"),
            sql.Identifier(config.schema, "account_device_profiles"),
        )).fetchall()
        for row in rows:
            if row["device_account_id"] is not None:
                skipped["existing_device"] += 1
                continue
            candidate, reason = _candidate(row, observed_at)
            if reason:
                skipped[reason] += 1
            else:
                candidates.append(candidate)
                sources[candidate["source_kind"]] += 1
    manifest = {
        "version": 1, "source": _SOURCE, "scope_sha256": scope, "policy_sha256": _POLICY,
        "created_at": observed_at, "candidates": candidates,
    }
    manifest["manifest_sha256"] = shared._digest(manifest)
    return {"manifest": manifest, "source_count": len(rows), "skipped": dict(skipped),
            "candidate_sources": dict(sources)}


def _read_manifest(path: Path) -> dict:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            status = os.fstat(handle.fileno())
            if not stat.S_ISREG(status.st_mode) or stat.S_IMODE(status.st_mode) & 0o077:
                raise BackfillError("manifest_permissions_invalid")
            manifest = json.load(handle)
    except (OSError, ValueError, UnicodeError):
        raise BackfillError("manifest_unreadable") from None
    if not isinstance(manifest, dict) or manifest.get("manifest_sha256") != shared._digest({
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }):
        raise BackfillError("manifest_digest_mismatch")
    if (
        type(manifest.get("version")) is not int or manifest["version"] != 1
        or manifest.get("source") != _SOURCE or manifest.get("policy_sha256") != _POLICY
        or not isinstance(manifest.get("candidates"), list)
    ):
        raise BackfillError("manifest_invalid")
    previous = 0
    for row in manifest["candidates"]:
        if (
            not isinstance(row, dict) or type(row.get("account_id")) is not int
            or not previous < row["account_id"] <= 9223372036854775807
            or row.get("source_kind") not in _KINDS
            or any(not shared._DIGEST.fullmatch(str(row.get(key) or "")) for key in (
                "email_sha256", "source_sha256", "payload_sha256"))
            or not isinstance(row.get("row_updated_at"), str)
            or row.get("data_updated_at") is not None and not isinstance(row["data_updated_at"], str)
        ):
            raise BackfillError("manifest_invalid")
        try:
            source_time, basis = _source_time(row["row_updated_at"], manifest["created_at"])
            if source_time != row["source_last_used_at"] or basis != row["time_basis"]:
                raise BackfillError("manifest_invalid")
        except (KeyError, BackfillError):
            raise BackfillError("manifest_invalid") from None
        previous = row["account_id"]
    return manifest


def _apply_one(conn, config: Config, candidate: dict, cipher, observed_at: str) -> str:
    row = conn.execute(sql.SQL(
        "SELECT id,email,updated_at,data FROM {} WHERE id=%s FOR UPDATE"
    ).format(sql.Identifier(config.schema, "registered_accounts")), (candidate["account_id"],)).fetchone()
    email = str((row or {}).get("email") or "").strip().lower()
    if not row or shared._digest(email) != candidate["email_sha256"]:
        return "account_changed"
    exists = conn.execute(sql.SQL("SELECT account_id FROM {} WHERE account_id=%s").format(
        sql.Identifier(config.schema, "account_device_profiles")), (candidate["account_id"],)).fetchone()
    if exists:
        return "existing_device"
    fresh, reason = _candidate(row, observed_at)
    if reason or fresh != candidate:
        return "source_changed"
    payload, kind, reason = _extract(_object(row["data"]))
    if reason:
        return "source_changed"
    encrypted = cipher.encrypt(json.dumps({
        "version": 1, "account_id": row["id"], "email": email,
        "updated_at": candidate["source_last_used_at"], "payload": payload,
        "provenance": {"source_kind": kind, "time_basis": candidate["time_basis"],
                       "source_row_updated_raw": candidate["row_updated_at"], "observed_at": observed_at},
    }, ensure_ascii=False, allow_nan=False).encode("utf-8")).decode("ascii")
    inserted = conn.execute(sql.SQL("""
        INSERT INTO {} (account_id,normalized_email,encrypted_payload,source,last_used_at)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT (account_id) DO NOTHING RETURNING account_id
    """).format(sql.Identifier(config.schema, "account_device_profiles")), (
        row["id"], email, encrypted, kind, datetime.fromisoformat(candidate["source_last_used_at"]),
    )).fetchone()
    return "inserted" if inserted else "existing_device"


def run(config: Config, manifest_path: Path, receipt_path: Path, *, apply: bool = False) -> dict:
    """固定同源资料清单后补缺；不会修改旧字段、既有设备行或登录会话。"""
    manifest_path, receipt_path = Path(manifest_path), Path(receipt_path)
    if manifest_path.absolute() == receipt_path.absolute():
        raise BackfillError("private_paths_conflict")
    if not apply:
        scan = _scan(config)
        manifest = scan["manifest"]
        shared._private_new(manifest_path, manifest)
        result = {
            "mode": "dry_run", "completed": True, "source_count": scan["source_count"],
            "candidate_count": len(manifest["candidates"]), "candidate_sources": scan["candidate_sources"],
            "skipped": scan["skipped"], "manifest_sha256": manifest["manifest_sha256"],
        }
        shared._private_new(receipt_path, result)
        return result
    manifest = _read_manifest(manifest_path)
    cipher = shared._cipher(config)
    with shared._connect(config, read_only=True) as conn:
        _require_tables(conn, config)
        if shared._scope(conn, config) != manifest.get("scope_sha256"):
            raise BackfillError("manifest_scope_mismatch")
    result = {
        "mode": "apply", "completed": False, "candidate_count": len(manifest["candidates"]),
        "manifest_sha256": manifest["manifest_sha256"], "results": {}, "items": [],
    }
    shared._private_new(receipt_path, result)
    counts = Counter()
    try:
        with shared._connect(config, read_only=False) as conn:
            _require_tables(conn, config)
            if shared._scope(conn, config) != manifest.get("scope_sha256"):
                raise BackfillError("manifest_scope_mismatch")
            for candidate in manifest["candidates"]:
                outcome = _apply_one(conn, config, candidate, cipher, manifest["created_at"])
                counts[outcome] += 1
                result["items"].append({"account_id": candidate["account_id"], "outcome": outcome})
    except Exception as exc:
        result.update(completed=False, items=[], results={}, error_code=(
            str(exc) if isinstance(exc, BackfillError) else "database_apply_failed"))
        shared._receipt_replace(receipt_path, result)
        raise BackfillError(result["error_code"]) from None
    result.update(completed=True, results=dict(counts))
    shared._receipt_replace(receipt_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path, help="实例配置目录")
    parser.add_argument("--source-instance", required=True, help="实例名称，本地和 Oracle 分开")
    parser.add_argument("--manifest", required=True, type=Path, help="固定清单私有新路径")
    parser.add_argument("--receipt", required=True, type=Path, help="本次回执私有新路径")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true", help="仅应用此前固定清单")
    modes.add_argument("--dry-run", action="store_true", help="默认：只读扫描")
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
        print(json.dumps({"ok": False, "error_code": (
            str(exc) if isinstance(exc, BackfillError) else "legacy_backfill_failed")}, ensure_ascii=False))
        return 1
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
