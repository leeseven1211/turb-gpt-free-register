#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""显式核对并补入历史 Codex 文件；运行时不会自动扫描或导入文件。

只插入 filename 和账号身份均缺失的记录，现有数据库行永不被旧快照覆盖。
支持仓库根目录和旧路径错误生成的 core/；callback 回执独立于可用凭证保存。
报告只含数量及错误分类，不输出邮箱、文件名、回执 URL 或 Token。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg_pool import PoolTimeout

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from core import db
from core.storage import postgres as postgres_store, records as record_store  # noqa: E402

_RECEIPT_TYPES = {"codex_cpa_callback": "cpa", "codex_sub2_callback": "sub2"}
_STATE_FIELDS = {
    "exported_at", "exported_count", "sub2_uploaded_at", "sub2_uploaded_count",
    "sub2_sync_error", "oauth_refresh_attempted_at", "oauth_refresh_error",
    "archived", "archived_at",
}
_COUNTERS = {"exported_count", "sub2_uploaded_count"}
_READ_FAILED = object()


def _state_payload(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("invalid_state")
    result = {key: value[key] for key in _STATE_FIELDS if key in value}
    for key, item in result.items():
        if key in _COUNTERS:
            if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 2**63 - 1:
                raise ValueError("invalid_state")
        elif key == "archived":
            if not isinstance(item, bool):
                raise ValueError("invalid_state")
        elif item is not None and not isinstance(item, str):
            raise ValueError("invalid_state")
    return result


def _read_json(path: Path, errors: Counter) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        errors["unreadable_file"] += 1
    except ValueError:
        errors["invalid_json"] += 1
    return _READ_FAILED


def inspect_files(source_root: Path) -> tuple[dict, set[str], Counter, Counter]:
    """只读扫描两个已知历史位置；保留重复候选供数据库补缺前判定冲突。"""
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise ValueError("source_root_not_directory")
    candidates: dict[tuple[str, str], list[dict]] = {}
    state_names: set[str] = set()
    counts: Counter = Counter()
    errors: Counter = Counter()
    for base in (root, root / "core"):
        state: dict[str, dict] = {}
        state_path = base / "codex_导出状态.json"
        if state_path.exists():
            raw_state = _read_json(state_path, errors)
            if raw_state is not _READ_FAILED and not isinstance(raw_state, dict):
                errors["invalid_state"] += 1
            elif isinstance(raw_state, dict):
                for filename, value in raw_state.items():
                    try:
                        db._validate_codex_filename(filename)
                        state[filename] = _state_payload(value)
                        state_names.add(filename)
                    except (ValueError, TypeError):
                        errors["invalid_state"] += 1
        for path in sorted((base / "codex_accounts").glob("codex-*.json")):
            try:
                filename = db._validate_codex_filename(path.name)
            except ValueError:
                errors["invalid_filename"] += 1
                continue
            content = _read_json(path, errors)
            if content is _READ_FAILED:
                continue
            if not isinstance(content, dict):
                errors["invalid_content"] += 1
                continue
            content_type = content.get("type")
            source = _RECEIPT_TYPES.get(content_type) if isinstance(content_type, str) else None
            if source:
                kind = "receipts"
            elif content_type in (None, "", "codex") and any(
                isinstance(content.get(key), str) and content[key].strip()
                for key in ("access_token", "refresh_token", "id_token")
            ):
                kind = "credentials"
            else:
                errors["invalid_content"] += 1
                continue
            if kind == "credentials" and any(
                content.get(key) is not None and not isinstance(content[key], str)
                for key in ("access_token", "refresh_token", "id_token", "email", "expired")
            ):
                errors["invalid_content"] += 1
                continue
            try:
                stamp = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            except OSError:
                errors["unreadable_file"] += 1
                continue
            counts[f"{kind[:-1]}_files"] += 1
            candidates.setdefault((kind, filename), []).append({
                "content": content,
                "state": state.get(filename, {}) if kind == "credentials" else {},
                "source": source,
                "mtime": stamp,
            })
    return candidates, state_names, counts, errors


def _existing_metadata(table: str, columns: tuple[str, ...] = ("filename",)) -> list[dict]:
    """不调用 init，保证 dry-run 不执行建表或其他迁移。"""
    qualified = postgres_store.qualified(table)
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (qualified,))
        if cur.fetchone()[0] is None:
            return []
        selected = ", ".join(postgres_store.quote_identifier(column) for column in columns)
        cur.execute(f"SELECT {selected} FROM {qualified}")
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _identity(filename: str, content: dict) -> tuple[str, tuple[str, ...]]:
    """沿用运行时锁和查询身份；邮箱及套餐比较不区分大小写。"""
    lock_key, identity = db._codex_identity_lock_key(filename, content)
    if identity[0] == "email_plan":
        identity = (identity[0], str(identity[1]).lower(), str(identity[2]).lower())
    return lock_key, identity


def _identity_exists(identity: tuple[str, ...], rows: list[dict]) -> bool:
    if identity[0] == "account_id":
        return any(str(row.get("account_id") or "") == identity[1] for row in rows)
    return any(
        str(row.get("email") or "").lower() == identity[1]
        and str(row.get("plan") or "").lower() == identity[2]
        for row in rows
    )


def _current_credential_match(conn, filename: str, identity: tuple[str, ...]) -> str | None:
    """在运行时身份锁内重查，防止 dry-run 之后并发授权或更名造成重复。"""
    table = postgres_store.qualified("codex_credentials")
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM {table} WHERE filename = %s LIMIT 1", (filename,))
        if cur.fetchone() is not None:
            return "filename"
        if identity[0] == "account_id":
            cur.execute(f"SELECT 1 FROM {table} WHERE account_id = %s LIMIT 1", (identity[1],))
        else:
            cur.execute(
                f"SELECT 1 FROM {table} WHERE lower(COALESCE(email, '')) = %s "
                "AND lower(COALESCE(plan, '')) = %s LIMIT 1",
                identity[1:],
            )
        return "identity" if cur.fetchone() is not None else None


def migrate(source_root: Path, *, apply: bool = False) -> dict:
    """返回无凭据的数量报告；有文件错误或新记录冲突时整次拒绝写入。"""
    candidates, state_names, counts, errors = inspect_files(source_root)
    credential_rows = _existing_metadata("codex_credentials", ("filename", "email", "plan", "account_id"))
    existing = {
        "credentials": {row["filename"] for row in credential_rows},
        "receipts": {row["filename"] for row in _existing_metadata("codex_callback_receipts")},
    }
    report = {
        "credential_files": counts["credential_files"],
        "receipt_files": counts["receipt_files"],
        "existing_credentials": 0, "existing_receipts": 0,
        "existing_identity_credentials": 0,
        "missing_credentials": 0, "missing_receipts": 0,
        "inserted_credentials": 0, "inserted_receipts": 0,
        "orphan_states": len(state_names - existing["credentials"] - {
            filename for kind, filename in candidates if kind == "credentials"
        }),
        "errors": {},
    }
    pending = []
    pending_identities: set[tuple[str, ...]] = set()
    for (kind, filename), snapshots in candidates.items():
        if filename in existing[kind]:
            report[f"existing_{kind}"] += 1
            continue
        first = snapshots[0]
        identity = _identity(filename, first["content"])[1] if kind == "credentials" else None
        if kind == "credentials" and _identity_exists(identity, credential_rows) and all(
            _identity(filename, item["content"])[1] == identity for item in snapshots[1:]
        ):
            report["existing_identity_credentials"] += 1
            continue
        report[f"missing_{kind}"] += 1
        if any((item["content"], item["state"]) != (first["content"], first["state"]) for item in snapshots[1:]):
            errors["conflicting_duplicates"] += 1
            continue
        if kind == "credentials":
            if identity in pending_identities:
                errors["conflicting_identity"] += 1
                continue
            pending_identities.add(identity)
        content = first["content"]
        stamp = first["mtime"]
        try:
            if kind == "credentials":
                payload = db._codex_payload(filename, content)
                payload.update(first["state"])
                payload.update({"created_at": stamp, "updated_at": stamp, "mtime": stamp})
            else:
                payload = {
                    "filename": filename, "email": str(content.get("email") or ""),
                    "source": first["source"], "content": content,
                    "created_at": stamp, "updated_at": stamp,
                }
        except (ValueError, TypeError, OverflowError):
            errors["invalid_content"] += 1
            continue
        pending.append((kind, payload))
    report["errors"] = dict(sorted(errors.items()))
    if not apply or errors:
        return report

    record_store.init()
    # 先完成所有解析和校验，再在同一事务补缺；并发新增由唯一索引兜底。
    with record_store.transaction() as conn:
        # 全部锁按稳定顺序获取，两个迁移进程扫描目录顺序不同时也不会互相死锁。
        lock_keys = sorted({
            _identity(payload["filename"], payload["content"])[0]
            for kind, payload in pending if kind == "credentials"
        })
        for lock_key in lock_keys:
            record_store.advisory_xact_lock(conn, lock_key)
        for kind, payload in pending:
            spec = record_store.CODEX_CREDENTIALS if kind == "credentials" else record_store.CODEX_CALLBACK_RECEIPTS
            if kind == "credentials":
                identity = _identity(payload["filename"], payload["content"])[1]
                current_match = _current_credential_match(conn, payload["filename"], identity)
                if current_match:
                    report["missing_credentials"] -= 1
                    report["existing_credentials" if current_match == "filename" else "existing_identity_credentials"] += 1
                    continue
            if record_store.insert_row_if_absent(spec, "filename", payload, conn=conn) is not None:
                report[f"inserted_{kind}"] += 1
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Codex 历史文件只读对账及显式补缺（不覆盖数据库现有行）")
    parser.add_argument("--source-root", required=True, type=Path, help="历史文件所在仓库根目录")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只读对账，不建表、不写入")
    mode.add_argument("--apply", action="store_true", help="校验通过后仅补入缺失凭证与回执")
    args = parser.parse_args(argv)
    try:
        report = migrate(args.source_root, apply=args.apply)
    except ValueError as exc:
        category = str(exc) if str(exc) == "source_root_not_directory" else "invalid_source"
        print(json.dumps({"errors": {category: 1}}, ensure_ascii=False))
        return 2
    except (psycopg.Error, PoolTimeout) as exc:
        # SQLSTATE 和异常类型能区分连接、权限、约束等原因，原始异常文本可能含连接信息。
        category = f"database_{getattr(exc, 'sqlstate', None) or type(exc).__name__}"
        print(json.dumps({"errors": {category: 1}}, ensure_ascii=False))
        return 2
    except RuntimeError as exc:
        category = "database_not_configured" if str(exc) in {
            "DATABASE_URL 未配置", "record_store 需要配置可用的 DATABASE_URL",
        } else f"operation_{type(exc).__name__}"
        print(json.dumps({"errors": {category: 1}}, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({"errors": {f"operation_{type(exc).__name__}": 1}}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
