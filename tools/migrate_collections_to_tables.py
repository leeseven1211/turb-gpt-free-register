#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 app_collections 里的 JSONB blob 迁移成 record_store 的行级表。

数据源是 PostgreSQL 的 `app_collections`（当前主存储），不是根目录那些兼容文件——
文件可能落后于库。兼容文件只在库里没有对应集合时作为兜底。

用法：
    python tools/migrate_collections_to_tables.py --dry-run   # 只报告，不写
    python tools/migrate_collections_to_tables.py --apply     # 导入
    python tools/migrate_collections_to_tables.py --verify    # 逐条对账

id 会原样保留：现有 id 被 codex_accounts 的文件名和 account_action_tasks.account_id
引用，重排会打断这些引用。导入后用 sync_identity 把序列推到 max(id) 之后。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from core import postgres_store, record_store  # noqa: E402
from core.record_store import ACCOUNTS, GENERIC_API_POOL, JOBS, OUTLOOK_POOL  # noqa: E402

# collection 名 -> (目标表, 兼容文件)
MIGRATIONS = [
    ("注册成功的邮箱.json", ACCOUNTS, "注册成功的邮箱.json"),
    ("注册任务.json", JOBS, "注册任务.json"),
    ("用于注册的邮箱.json", OUTLOOK_POOL, "用于注册的邮箱.json"),
    ("用于注册的API邮箱.json", GENERIC_API_POOL, "用于注册的API邮箱.json"),
]

# 写时派生、读时会重算的字段，不入库（见 db._decorate_account）
DROP_FIELDS = {"copy_line"}


def load_source(collection: str, filename: str) -> tuple[list[dict], str]:
    """优先读库里的集合；库里没有再退回兼容文件。"""
    found, payload = postgres_store.load_collection(collection)
    if found and isinstance(payload, list):
        return payload, "app_collections"
    path = _PROJECT_ROOT / filename
    if path.exists() and path.stat().st_size > 2:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data, "文件"
        except (OSError, ValueError):
            pass
    return [], "空"


def normalise(record: dict, spec) -> dict:
    out = {k: v for k, v in record.items() if k not in DROP_FIELDS}
    # created_at / updated_at 在表里是 NOT NULL，历史记录偶有缺失
    stamp = out.get("created_at") or out.get("updated_at") or "1970-01-01T00:00:00"
    out["created_at"] = out.get("created_at") or stamp
    out["updated_at"] = out.get("updated_at") or stamp
    if spec is not JOBS and not str(out.get("email") or "").strip():
        out["email"] = ""
    return out


def report(collection: str, spec, rows: list[dict], origin: str) -> None:
    existing = record_store.count_rows(spec)
    ids = [r.get("id") for r in rows if r.get("id") is not None]
    dupes = len(ids) - len(set(ids))
    no_id = sum(1 for r in rows if r.get("id") is None)
    print(f"  {collection:28s} -> {spec.name:24s} 源={origin:16s} "
          f"{len(rows):5d} 条 | 表中已有 {existing:5d} | 重复 id {dupes} | 缺 id {no_id}")


def do_apply(collection: str, spec, rows: list[dict], origin: str) -> tuple[int, list[str]]:
    inserted, errors = 0, []
    existing_ids = {
        r["id"] for r in record_store.list_rows(spec, order_by="id")
    }
    with record_store.transaction() as conn:
        for record in rows:
            payload = normalise(record, spec)
            rid = payload.get("id")
            if rid is not None and int(rid) in existing_ids:
                continue   # 幂等：重复执行不会翻倍
            try:
                record_store.insert_row(spec, payload, conn=conn)
                inserted += 1
            except Exception as exc:
                errors.append(f"{spec.name} id={rid}: {type(exc).__name__}: {exc}")
    record_store.sync_identity(spec)
    return inserted, errors


def do_verify(collection: str, spec, rows: list[dict], origin: str) -> list[str]:
    """逐条比对：表里的记录必须能完整还原出源 blob 的每个字段。"""
    problems = []
    table_rows = {r["id"]: r for r in record_store.list_rows(spec, order_by="id")}
    if len(table_rows) != len(rows):
        problems.append(f"{spec.name}: 条数不一致，源 {len(rows)} vs 表 {len(table_rows)}")

    for record in rows:
        rid = record.get("id")
        got = table_rows.get(rid)
        if got is None:
            problems.append(f"{spec.name} id={rid}: 表里缺失")
            continue
        for key, want in record.items():
            if key in DROP_FIELDS:
                continue
            have = got.get(key)
            if have != want:
                problems.append(
                    f"{spec.name} id={rid} 字段 {key}: 源={want!r:.60} 表={have!r:.60}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="app_collections blob -> record_store 行级表")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只报告规模，不写库")
    mode.add_argument("--apply", action="store_true", help="导入（幂等，可重复执行）")
    mode.add_argument("--verify", action="store_true", help="逐条对账表与源 blob")
    args = parser.parse_args()

    postgres_store.require_ready()
    record_store.init()
    print(f"schema = {postgres_store.schema_name()}\n")

    total_problems: list[str] = []
    for collection, spec, filename in MIGRATIONS:
        rows, origin = load_source(collection, filename)

        if args.dry_run:
            report(collection, spec, rows, origin)
            continue

        if args.apply:
            inserted, errors = do_apply(collection, spec, rows, origin)
            print(f"  {spec.name:24s} 新增 {inserted:5d} 条"
                  + (f"，{len(errors)} 条失败" if errors else ""))
            total_problems.extend(errors)
            continue

        problems = do_verify(collection, spec, rows, origin)
        status = "一致" if not problems else f"{len(problems)} 处不一致"
        print(f"  {spec.name:24s} 源 {len(rows):5d} 条 -> {status}")
        total_problems.extend(problems)

    if total_problems:
        print(f"\n发现 {len(total_problems)} 个问题：")
        for line in total_problems[:40]:
            print(f"  - {line}")
        if len(total_problems) > 40:
            print(f"  ... 另有 {len(total_problems) - 40} 条")
        return 1

    if not args.dry_run:
        print("\n全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
