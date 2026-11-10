#!/usr/bin/env python3
"""隔离数据库实测选择、受理、集合提交和大历史下的批次读取；不请求远端。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=int, default=100000)
    parser.add_argument("--history", type=int, default=1000000)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--isolated", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.isolated:
        from tools.test_isolated import build_isolated_environment
        environment = build_isolated_environment(project_root=ROOT)
        return subprocess.call([sys.executable, __file__, *sys.argv[1:], "--isolated"], env=environment, cwd=ROOT)
    if args.samples < 1 or args.accounts < 10000 or args.history < 2000:
        parser.error("至少需要 1 样本、10,000 合成账号、2,000 历史执行。")
    from core.storage import postgres, records
    from core.storage.operations import store, bulk
    from core.bulk_operations import adapters, catalog
    from core.accounts.query import compile_query
    from tools.benchmarks.test_performance import _seed_terminal_operation_history, percentile, _query_counter, _restore_query_counter
    from tests.support_pg import drop_schema
    if not postgres.schema_name().startswith("test_"):
        raise RuntimeError("性能测量只允许 test_ schema")
    schema = postgres.schema_name()
    result = {"samples": args.samples, "accounts": args.accounts, "history_task_run_rows_each": args.history,
              "external_requests": 0, "measurements": {}}

    def measure(fn):
        values = []
        sql = []
        for _ in range(args.samples):
            original, counter = _query_counter()
            started = time.perf_counter()
            try:
                fn()
                values.append((time.perf_counter() - started) * 1000)
                sql.append(counter["count"])
            finally:
                _restore_query_counter(original)
        return {"p50_ms": round(percentile(values, 50), 3), "p95_ms": round(percentile(values, 95), 3),
                "max_ms": round(max(values), 3), "sql_min": min(sql), "sql_max": max(sql)}

    try:
        records.init()
        bulk.init()
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {postgres.qualified('registered_accounts')}
                (email,created_at,updated_at,archived,email_source,current_plan_type,plan_check_status,plan_check_ok,
                 plus_promo_kind,data)
                SELECT 'bulk-benchmark-'||n||'@example.test','2026-10-15T12:00:00','2026-10-15T12:00:00',false,
                  'synthetic','free','success',true,'none','{{"access_token":"synthetic"}}'::jsonb
                FROM generate_series(1,%s) n RETURNING id""", (args.accounts,))
            ids = [row[0] for row in cur.fetchall()]
        # 分段提交合成历史，限制WAL/锁/回滚体积，避免单次百万行事务拖住共享测试实例。
        seeded = 0
        while seeded < args.history:
            chunk = min(20000, args.history - seeded)
            _seed_terminal_operation_history(rows=chunk, operation=store, postgres_store=postgres, account_ids=ids[:1000])
            seeded += chunk
            if seeded % 100000 == 0 or seeded == args.history:
                print(json.dumps({"seeded_history": seeded}), flush=True)
        with postgres.connect() as conn, conn.cursor() as cur:
            for name in ("registered_accounts", "operation_tasks", "operation_runs"):
                cur.execute("ANALYZE " + postgres.qualified(name))
        settings = catalog.capture_settings("plan_check", {})
        batches = []
        for size in (500, 10000):
            selected = []
            def freeze():
                spec = {"limit": size, "date_from": "2026-10-01", "date_to": "2026-10-31", "filters": {"promotion": ["none"]}}
                row = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "query", "query": spec},
                    operation_key="plan_check", config_revision=settings["config_revision"], config_snapshot=settings["config_snapshot"])
                where, params = compile_query(spec)
                def preflight(targets, conn):
                    return adapters.preflight_many(targets, operation_key="plan_check", settings=settings, conn=conn)
                selected.append(bulk.freeze_selection(row["id"], where_sql=where, params=params, preflight=preflight))
            result["measurements"][f"selection_{size}"] = measure(freeze)
            def accept():
                row = selected.pop()
                batches.append(bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=row["id"], selection_revision=1,
                    operation_key="plan_check", parameters={}, config_revision=settings["config_revision"], max_concurrency=64))
            result["measurements"][f"accept_{size}"] = measure(accept)
            print(json.dumps({"completed": f"selection_and_accept_{size}"}), flush=True)
        # 独立账号组确保不把其他批次占用/窗口计入正常集合提交用时。
        next_group = 0
        submitted = []
        def submit():
            nonlocal next_group
            target_ids = ids[next_group:next_group + 100]
            next_group += 100
            row = bulk.create_selection(request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": target_ids},
                operation_key="plan_check", config_revision=settings["config_revision"], config_snapshot=settings["config_snapshot"])
            frozen = bulk.freeze_selection(row["id"])
            batch = bulk.create_batch(request_key=uuid.uuid4().hex, selection_id=frozen["id"], selection_revision=1,
                operation_key="plan_check", parameters={}, config_revision=settings["config_revision"], max_concurrency=64)
            bulk.materialize_targets(batch["id"], limit=100)
            # 从这里另记展开热路径，选择与受理在独立测量项里。
            original, counter = _query_counter()
            started = time.perf_counter()
            try:
                bulk.process_batch(batch["id"], adapters.submit_chunk, limit=100)
                submitted.append({"milliseconds": (time.perf_counter() - started) * 1000, "sql": counter["count"]})
            finally:
                _restore_query_counter(original)
            # 测量夹具只把合成队列转成终态以释放下一样本窗口；不运行 handler、不将此当业务验收。
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {postgres.qualified('operation_runs')} SET status='success' WHERE batch_id=%s", (batch["id"],))
        for _ in range(args.samples):
            submit()
        times = [item["milliseconds"] for item in submitted]
        result["measurements"]["expand_100"] = {"p50_ms": round(percentile(times, 50), 3),
            "p95_ms": round(percentile(times, 95), 3), "max_ms": round(max(times), 3),
            "sql_min": min(x["sql"] for x in submitted), "sql_max": max(x["sql"] for x in submitted),
            "targets_per_second_p50": round(100000 / percentile(times, 50), 2)}
        batch = batches[-1]
        bulk.get_batch(batch["id"])
        result["measurements"]["summary_10000"] = measure(lambda: bulk.get_batch(batch["id"]))
        result["measurements"]["targets_50_of_10000"] = measure(lambda: bulk.list_targets(batch["id"], limit=50))
    finally:
        drop_schema(schema)
    result["schema_cleaned"] = True
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data + "\n")
    print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
