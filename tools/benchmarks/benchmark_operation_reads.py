#!/usr/bin/env python3
"""在非生产独立schema比较当前与指定Git版本的任务列表读取。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import signal
import subprocess
import sys
import time
import types
from urllib.parse import urlsplit
import uuid


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--compare-ref", default="HEAD")
    parser.add_argument("--variant", choices=("both", "before", "after"), default="both")
    parser.add_argument("--modes", default="compact,full,status_filter")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    database = urlsplit(os.environ.get("DATABASE_URL", "")).path.lstrip("/")
    if not database or database == "turb_console":
        raise SystemExit("必须显式提供非生产DATABASE_URL，禁止生产数据库。")
    if args.rows < 2000 or args.samples < 3:
        raise SystemExit("至少2000条历史与3次样本；p95交付须30次。")
    os.environ.pop("TURB_ALLOW_PRODUCTION_DB", None)
    benchmark_schema = "test_operation_read_" + uuid.uuid4().hex[:10]
    os.environ.update(PYTHON_DOTENV_DISABLED="1", COMPAT_EXPORT_MODE="disabled",
                      TURB_DB_SCHEMA=benchmark_schema, ACCOUNT_TASK_DB_SCHEMA=benchmark_schema)
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo))
    from core.storage import postgres, records
    from core.storage.operations import legacy_task_store, store
    from tools.benchmarks.test_performance import _seed_terminal_operation_history

    old = types.ModuleType("benchmark_original_operation_store")
    old.__file__ = str(repo / "core/storage/operations/store.py")
    sys.modules[old.__name__] = old
    source = subprocess.check_output(["git", "show", args.compare_ref + ":core/storage/operations/store.py"], cwd=repo, text=True)
    results = []
    def stop_benchmark(_signum, _frame):
        raise KeyboardInterrupt("基准已停止，正在清理隔离schema")
    signal.signal(signal.SIGTERM, stop_benchmark)
    try:
        records.init()
        legacy_task_store.init()
        store.init()
        exec(compile(source, old.__file__, "exec"), old.__dict__)
        old.init()
        with records.transaction() as conn:
            ids = [records.insert_row(records.ACCOUNTS, {"email": f"read-benchmark-{n}@example.test"}, conn=conn) for n in range(1000)]
        _seed_terminal_operation_history(rows=args.rows, operation=store, postgres_store=postgres, account_ids=ids)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute("ANALYZE " + store._table("operation_tasks"))
            cur.execute("ANALYZE " + store._table("operation_runs"))
        expected = {}
        for variant, method in (("before", old.list_tasks), ("after", store.list_tasks)):
            if args.variant != "both" and args.variant != variant:
                continue
            for mode, kwargs in (("compact", {"include_facets": False}),
                                 ("full", {"include_facets": True}),
                                 ("status_filter", {"include_facets": False, "status": "success"})):
                if mode not in args.modes.split(","):
                    continue
                method(page_size=50, **kwargs)
                timings = []
                for _ in range(args.samples):
                    start = time.perf_counter()
                    result = method(page_size=50, **kwargs)
                    timings.append((time.perf_counter() - start) * 1000)
                identities = [(item["id"], item.get("last_run_id"), item["status"], item["run_count"])
                              for item in result["items"]]
                if variant == "before":
                    expected[mode] = identities
                elif mode in expected and identities != expected[mode]:
                    raise RuntimeError(f"{mode}列表结果不等价，不能将性能结果作为验收")
                row = {"variant": variant, "mode": mode, "samples": len(timings),
                       "history_rows": args.rows, "total": result["total"], "page_size": len(result["items"]),
                       "p50_ms": statistics.median(timings), "p95_ms": sorted(timings)[max(0, int(len(timings) * .95 + .9999) - 1)],
                       "max_ms": max(timings)}
                print(json.dumps(row, ensure_ascii=False), flush=True)
                results.append(row)
    finally:
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute("DROP SCHEMA " + postgres.quote_identifier(os.environ["TURB_DB_SCHEMA"]) + " CASCADE")
    if args.output:
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
