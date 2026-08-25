#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一任务中心迁移工具。

默认只报告；--apply 才会创建新表并幂等回填。旧表始终保留，回滚只需让 WebUI
重新读取旧接口，不需要反向改写或删除任何表。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.env_loader import ensure_loaded  # noqa: E402
from core import operation_task_store, postgres_store  # noqa: E402


def legacy_report() -> dict:
    from psycopg.rows import dict_row

    counts: dict[str, int] = {}
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        for table in (
            "registered_accounts", "registration_jobs", "account_action_batches",
            "account_action_tasks", "account_action_events",
        ):
            cur.execute(f'SELECT COUNT(*) AS n FROM {postgres_store.qualified(table)}')
            counts[table] = int(cur.fetchone()["n"])
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM information_schema.tables
            WHERE table_schema=%s AND table_name IN (
                'registration_attempts', 'operation_batches', 'operation_tasks',
                'operation_runs', 'operation_events', 'operation_batch_items',
                'account_operation_leases', 'operation_resources'
            )
            """,
            (operation_task_store._schema_name(),),
        )
        unified_table_count = int(cur.fetchone()["n"])
    return {
        "mode": "dry_run",
        "database": postgres_store._database_name(postgres_store.database_url()),
        "legacy": counts,
        "unified_table_count": unified_table_count,
        "will_delete_legacy_data": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="幂等迁移注册与账号任务到统一任务中心")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="创建新表并回填")
    mode.add_argument("--verify", action="store_true", help="只验证已回填数据")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args()

    ensure_loaded()
    postgres_store.require_ready()
    if args.apply:
        migrated = operation_task_store.reconcile_all()
        result = {"mode": "apply", "migrated": migrated, "verification": operation_task_store.verify()}
    elif args.verify:
        result = {"mode": "verify", "verification": operation_task_store.verify()}
    else:
        result = legacy_report()
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2, default=str))
    verification = result.get("verification")
    return 0 if not verification or verification.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
