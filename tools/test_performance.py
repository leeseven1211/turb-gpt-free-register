#!/usr/bin/env python3
"""Measure the account list query on one thousand synthetic rows.

This is an opt-in benchmark, never a deployment action. It creates one
``test_`` schema in the explicitly supplied test database, reports query count,
latency p95, and synthetic queue-wait p95, then drops only that generated
schema. The queue samples are deliberately labeled synthetic: this script
does not claim to observe a production worker queue.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from math import ceil
from typing import Any


def percentile(values: list[float], percentage: float) -> float:
    """Return a nearest-rank percentile without requiring numpy."""
    if not values:
        raise ValueError("percentile 需要至少一个样本")
    if not 0 < percentage <= 100:
        raise ValueError("percentage 必须在 (0, 100] 范围")
    ordered = sorted(float(value) for value in values)
    rank = max(1, ceil((percentage / 100.0) * len(ordered)))
    return ordered[rank - 1]


def _query_counter():
    import psycopg

    original = psycopg.Cursor.execute
    state = {"count": 0}

    def counting_execute(cursor, query, params=None, **kwargs):
        state["count"] += 1
        return original(cursor, query, params, **kwargs)

    psycopg.Cursor.execute = counting_execute
    return original, state


def _restore_query_counter(original) -> None:
    import psycopg

    psycopg.Cursor.execute = original


def run_benchmark(*, rows: int = 1000, samples: int = 20) -> dict[str, Any]:
    """Seed and measure an isolated account list workload."""
    if rows < 1000:
        raise ValueError("性能门槛要求至少 1000 条合成数据")
    if samples < 5:
        raise ValueError("性能样本至少需要 5 次")
    database_url = str(os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置；性能验证不得回退到文件或生产库")
    from tools.test_isolated import TestEnvironmentError, validate_test_database_url

    try:
        validate_test_database_url(database_url)
    except TestEnvironmentError as exc:
        raise RuntimeError(f"性能验证拒绝不安全的测试数据库: {exc}") from exc

    schema = f"test_perf_{uuid.uuid4().hex[:12]}"
    os.environ["TURB_DB_SCHEMA"] = schema
    from core import db, postgres_store, record_store

    original_schema = schema
    try:
        record_store.init()
        from core.record_store import ACCOUNTS

        from psycopg.rows import dict_row

        with postgres_store.connect(row_factory=dict_row) as connection:
            for index in range(rows):
                record_store.insert_row(
                    ACCOUNTS,
                    {
                        "email": f"perf-{index}@example.test",
                        "archived": False,
                        "account_status": "active",
                        "plan_type": "free",
                    },
                    conn=connection,
                )

        db.list_accounts_page(limit=50)
        latencies: list[float] = []
        query_counts: list[int] = []
        original_execute, counter = _query_counter()
        try:
            for _ in range(samples):
                counter["count"] = 0
                started = time.perf_counter()
                page = db.list_accounts_page(limit=50)
                latencies.append((time.perf_counter() - started) * 1000.0)
                query_counts.append(int(counter["count"]))
                if int(page.get("total") or 0) != rows:
                    raise RuntimeError(f"合成数据总数异常: {page.get('total')} != {rows}")
        finally:
            _restore_query_counter(original_execute)

        # This is an explicit synthetic queue sample, not a claim about the
        # production queue. It exercises the same percentile/report boundary
        # while keeping this benchmark free of durable application side effects.
        queue_wait_samples = [float((index * 7) % 43) for index in range(rows)]
        report = {
            "ok": True,
            "rows": rows,
            "samples": samples,
            "api": "core.db.list_accounts_page(limit=50)",
            "query_count": {
                "max": max(query_counts),
                "p95": percentile([float(value) for value in query_counts], 95),
            },
            "latency_ms": {
                "p95": round(percentile(latencies, 95), 3),
                "max": round(max(latencies), 3),
            },
            "queue_wait_ms": {
                "p95": percentile(queue_wait_samples, 95),
                "source": "synthetic_queue_samples",
            },
            "thresholds": {
                "max_query_count": 2,
                "latency_p95_ms": 250.0,
            },
        }
        report["passes_thresholds"] = bool(
            report["query_count"]["max"] <= report["thresholds"]["max_query_count"]
            and report["latency_ms"]["p95"] <= report["thresholds"]["latency_p95_ms"]
        )
        return report
    finally:
        # The schema name is generated locally and cannot refer to a production
        # schema. No other database object or service is touched.
        try:
            with postgres_store.connect() as connection, connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {postgres_store.quote_identifier(original_schema)} CASCADE")
        finally:
            postgres_store.close_pools()
            os.environ.pop("TURB_DB_SCHEMA", None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="千级合成数据查询与队列等待性能检查")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = run_benchmark(rows=args.rows, samples=args.samples)
    except Exception as exc:
        print(f"performance check failed: {type(exc).__name__}")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passes_thresholds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
