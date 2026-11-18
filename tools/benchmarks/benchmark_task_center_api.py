#!/usr/bin/env python3
"""在独立 turb_test schema 中交替比较旧、新任务中心 GET 路由和真实 SQL。

先在环境中设置本机 turb_test 的 DATABASE_URL；脚本不会读取 .env 或输出连接参数。
从仓库根目录运行：
    python tools/benchmarks/benchmark_task_center_api.py \
        --compare-ref 2fe57ac --samples 30 --output /绝对路径/task-center-api-benchmark.json
旧路由通过 git show 加载，仓储及其他依赖共用当前代码，不是完整旧进程的回放。
仅比较旧账号 GET 时加 --suite legacy-account --compare-ref HEAD，使用独立的阶段 B 输出文件。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import types
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _source_hashes() -> dict[str, str]:
    paths = ("webui/routes/operations.py", "webui/runtime.py", "core/operations/query_service.py",
             "core/operations/contracts.py", "core/storage/operations/store.py",
             "core/account_task_store.py", "core/storage/operations/legacy_task_store.py",
             "core/operations/presentation.py", "core/operations/errors.py",
             "core/accounts/operation_settings.py", "core/accounts/operation_coordinator.py",
             "tools/benchmarks/benchmark_task_center_api.py")
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def _client(module, name: str):
    from flask import Flask
    from webui.runtime import WebUIContext

    app = Flask(name)
    app.config.update(TESTING=True)
    context = WebUIContext(app, logging.getLogger(name))
    app.register_blueprint(module.create_operations_blueprint(context))
    return app.test_client()


def _summary(samples: list[dict]) -> dict:
    from tools.benchmarks.test_performance import percentile

    milliseconds = [row["milliseconds"] for row in samples]
    return {
        "samples": len(samples),
        "p50_ms": round(percentile(milliseconds, 50), 3),
        "p95_ms": round(percentile(milliseconds, 95), 3),
        "max_ms": round(max(milliseconds), 3),
        "sql_min": min(row["sql"] for row in samples),
        "sql_max": max(row["sql"] for row in samples),
        "response_bytes_min": min(row["response_bytes"] for row in samples),
        "response_bytes_max": max(row["response_bytes"] for row in samples),
    }


def _measure(client, path: str, query: dict, *, expected_status: int = 200) -> tuple[dict, dict]:
    from tools.benchmarks.test_performance import _query_counter, _restore_query_counter

    original, counter = _query_counter()
    started = time.perf_counter_ns()
    try:
        response = client.get(path, query_string=query)
        content = response.get_data()
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
    finally:
        _restore_query_counter(original)
    if response.status_code != expected_status:
        raise RuntimeError(f"基准 GET 返回 HTTP {response.status_code}")
    payload = response.get_json()
    return {"milliseconds": round(elapsed, 6), "sql": counter["count"],
            "response_bytes": len(content), "http_status": response.status_code,
            "response_sha256": hashlib.sha256(content).hexdigest()}, payload


def _seed_legacy_history(*, rows: int, events: int, account_ids: list[int], postgres) -> int:
    """只写独立 schema 的旧任务终态与事件，不经过提交、投影或 dispatcher。"""
    with postgres.connect() as conn, conn.cursor() as cursor:
        cursor.execute(f"""INSERT INTO {postgres.qualified('account_action_tasks')}
            (task_uuid,task_type,account_id,email_snapshot,trigger,status,result_summary,error,
             queued_at,started_at,finished_at,duration_ms,log_file)
            SELECT 'legacy-api-task-'||n,
                CASE WHEN mod(n,3)=0 THEN 'token_refresh' ELSE 'account_setup_retry' END,
                (%s::bigint[])[mod(n,%s)::integer+1],
                'legacy-history-'||n||'@example.test','performance_history',
                (ARRAY['success','failed','interrupted','attention_required','partial_success','unsupported'])[mod(n,6)+1],
                jsonb_build_object('synthetic',true,'ordinal',n,'failure_stage','network',
                    'outcome',CASE WHEN mod(n,6)=3 THEN 'request_unknown' ELSE 'recorded' END),
                CASE WHEN mod(n,6)=0 THEN NULL ELSE 'synthetic network timeout' END,
                '2026-01-01T00:00:00','2026-01-01T00:00:01','2026-01-01T00:00:02',1000,''
            FROM generate_series(1,%s) n""", (account_ids, len(account_ids), rows))
        cursor.execute(f"SELECT MAX(id) FROM {postgres.qualified('account_action_tasks')} "
                       "WHERE status='attention_required'")
        task_id = int(cursor.fetchone()[0])
        cursor.execute(f"""INSERT INTO {postgres.qualified('account_action_events')}
            (task_id,created_at,level,stage,message,detail,event_type,visibility)
            SELECT %s,'2026-01-01T00:00:01','INFO','network','合成旧任务事件 '||n,
                jsonb_build_object('synthetic',true,'ordinal',n),'note.info','timeline'
            FROM generate_series(1,%s) n""", (task_id, events))
        for table in ("registered_accounts", "account_action_tasks", "account_action_events"):
            cursor.execute("ANALYZE " + postgres.qualified(table))
    return task_id


def _run(args) -> dict:
    from tools.test_isolated import parse_conninfo, validate_test_database_url

    database_url = str(os.environ.get("DATABASE_URL") or "")
    validate_test_database_url(database_url)
    if parse_conninfo(database_url).get("dbname") != "turb_test":
        raise RuntimeError("本基准仅允许 turb_test 数据库")
    schema = str(os.environ.get("TURB_DB_SCHEMA") or "")
    if not schema.startswith("test_task_api_"):
        raise RuntimeError("基准必须使用自行生成的 test_task_api_ schema")
    if os.environ.get("TURB_ALLOW_PRODUCTION_DB") != "0" or os.environ.get("PYTHON_DOTENV_DISABLED") != "1":
        raise RuntimeError("基准必须使用隔离环境")

    from core.storage import postgres, records
    from core.storage.operations import store, legacy_task_store
    from tests.support_pg import drop_schema
    from tools.benchmarks.test_performance import _seed_accounts, _seed_terminal_operation_history
    from webui.routes import operations

    baseline_sha = _git("rev-parse", args.compare_ref)
    baseline_source = _git("show", f"{baseline_sha}:webui/routes/operations.py")
    store_paths = (("core/account_task_store.py", "core/storage/operations/legacy_task_store.py")
                   if args.suite == "legacy-account" else ("core/storage/operations/store.py",))
    for store_path in store_paths:
        if _git("show", f"{baseline_sha}:{store_path}") != (ROOT / store_path).read_text().strip():
            raise RuntimeError("仓储与指定基线不同，不能将此基准描述为仅路由与查询服务对照")
    source_hashes = _source_hashes()
    baseline = types.ModuleType("benchmark_baseline_operations")
    baseline.__file__ = str(ROOT / "webui/routes/operations.py")
    sys.modules[baseline.__name__] = baseline
    exec(compile(baseline_source, baseline.__file__, "exec"), baseline.__dict__)
    clients = {"before": _client(baseline, "task_api_before"),
               "after": _client(operations, "task_api_after")}
    with postgres.connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_setting('server_version')")
        database, server_version = cursor.fetchone()
        if database != "turb_test":
            raise RuntimeError("实际连接数据库不是 turb_test")
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname=%s)", (schema,))
        if cursor.fetchone()[0]:
            raise RuntimeError("随机 schema 已存在，拒绝复用或删除")
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_sha": baseline_sha,
        "current_head": _git("rev-parse", "HEAD"),
        "current_worktree_dirty": bool(_git("status", "--porcelain")),
        "source_sha256": source_hashes,
        "baseline_route_sha256": hashlib.sha256(baseline_source.encode()).hexdigest(),
        "scope": "旧路由由 git show 加载，与当前路由及查询服务共用当前未变仓储和数据库；不表示完整旧进程或生产性能",
        "transport": "Flask test_client GET，包含路由、真实 SQL、JSON 序列化；不含鉴权、TCP、TLS、浏览器或外部请求",
        "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
                 "cpu_count": os.cpu_count(), "python": platform.python_version(), "postgres": server_version,
                 "flask": importlib.metadata.version("flask"), "psycopg": importlib.metadata.version("psycopg")},
        "database": "turb_test", "schema": schema, "schema_cleaned": False,
        "suite": args.suite, "unchanged_store_paths": list(store_paths),
        "accounts": args.accounts, "history_tasks": args.rows,
        "history_runs": 0 if args.suite == "legacy-account" else args.rows,
        "detail_events": args.events, "samples_per_variant": args.samples,
        "warmups_per_variant": args.warmups, "external_requests": 0, "dispatcher_started": False,
        "order": "每个场景逐样本交替 before/after；奇数样本反转顺序",
        "measurements": {}, "raw_samples": {},
    }
    clock_patch = None
    try:
        records.init()
        legacy_task_store.init()
        account_ids = _seed_accounts(rows=args.accounts, record_store=records, postgres_store=postgres)
        if args.suite == "legacy-account":
            task_id = _seed_legacy_history(rows=args.rows, events=args.events,
                                          account_ids=account_ids, postgres=postgres)
            result["seeded_counts"] = {"account_action_tasks": args.rows, "account_action_events": args.events}
            # 旧列表的 schedule.next_run_at 会随墙钟变化；只固定这个展示时钟，
            # 保留真实 settings 调用、调度状态读取和 SQL，不删除/归一化响应字段。
            from core.runtime import scheduler_state

            fixed_time = datetime(2026, 1, 1, 12)

            class FrozenSchedulerDateTime(datetime):
                @classmethod
                def now(cls, tz=None):
                    return fixed_time if tz is None else fixed_time.replace(tzinfo=tz)

            clock_patch = patch.object(scheduler_state, "datetime", FrozenSchedulerDateTime)
            clock_patch.start()
            result["presentation_clock"] = {
                "target": "core.runtime.scheduler_state.datetime", "fixed_local_time": fixed_time.isoformat(),
                "reason": "保持完整 schedule JSON 可比较；真实 settings 和数据库读取未替换",
            }
            cases = {
                "legacy_list": ("/api/account-tasks", {"page": 1, "page_size": 50}),
                "legacy_list_combined_filter": ("/api/account-tasks", {"page": 1, "page_size": 50,
                    "type": "token_refresh", "status": "failed", "q": "legacy-history-1"}),
                "legacy_detail_with_events": (f"/api/account-tasks/{task_id}", {}),
                "legacy_detail_missing": (f"/api/account-tasks/{args.rows + 1}", {}),
            }
        else:
            store.init()
            result["seeded_counts"] = _seed_terminal_operation_history(
                rows=args.rows, operation=store, postgres_store=postgres, account_ids=account_ids)
            with postgres.connect() as conn, conn.cursor() as cursor:
                cursor.execute(f"SELECT id,last_run_id FROM {postgres.qualified('operation_tasks')} ORDER BY id DESC LIMIT 1")
                task_id, run_id = cursor.fetchone()
                cursor.execute(f"""INSERT INTO {postgres.qualified('operation_events')}
                    (event_uuid,task_id,run_id,source_system,source_id,level,stage,event_type,message,detail)
                    SELECT 'task-api-event-'||n,%s,%s,'performance_history','task-api-event-'||n,
                        'INFO','complete','note.info','合成任务事件 '||n,
                        jsonb_build_object('synthetic',true,'ordinal',n)
                    FROM generate_series(1,%s) n""", (task_id, run_id, args.events))
                for table in ("registered_accounts", "operation_tasks", "operation_runs", "operation_events"):
                    cursor.execute("ANALYZE " + postgres.qualified(table))
            cases = {
                "list_compact": ("/api/operations", {"page": 1, "page_size": 50, "include_facets": 0, "include_batches": 0}),
                "list_with_metadata": ("/api/operations", {"page": 1, "page_size": 50, "include_facets": 1, "include_batches": 1}),
                "list_combined_filter": ("/api/operations", {"page": 1, "page_size": 50, "include_facets": 1,
                    "include_batches": 0, "type": "performance.history", "status": "success",
                    "target": "performance-history-1", "stage": "complete", "run_count": "1"}),
                "detail_without_events": (f"/api/operations/{task_id}", {"include_events": 0}),
                "detail_with_events": (f"/api/operations/{task_id}", {"include_events": 1}),
            }
        result["detail_task_id"] = task_id
        for mode, (path, query) in cases.items():
            expected_status = 404 if mode == "legacy_detail_missing" else 200
            expected = None
            expected_response = None
            for _ in range(args.warmups):
                for variant in ("before", "after"):
                    measured, payload = _measure(clients[variant], path, query, expected_status=expected_status)
                    if expected is None:
                        expected = payload
                        expected_response = {key: measured[key] for key in ("http_status", "response_sha256", "response_bytes")}
                    elif payload != expected:
                        raise RuntimeError(f"{mode} 两版完整 JSON 响应不等价")
                    if args.suite == "legacy-account" and any(measured[key] != value for key, value in expected_response.items()):
                        raise RuntimeError(f"{mode} 两版 HTTP 或完整 body 不等价")
            if mode in {"legacy_list", "legacy_list_combined_filter"} and not expected.get("items"):
                raise RuntimeError(f"{mode} 合成查询没有命中，拒绝测量空列表")
            if mode == "legacy_detail_with_events" and len(expected["task"].get("events", [])) != args.events:
                raise RuntimeError("旧详情未返回预期全部合成事件")
            samples = {"before": [], "after": []}
            for sample in range(args.samples):
                order = ("before", "after") if sample % 2 == 0 else ("after", "before")
                for variant in order:
                    measured, payload = _measure(clients[variant], path, query, expected_status=expected_status)
                    if payload != expected:
                        raise RuntimeError(f"{mode} 第 {sample + 1} 个样本响应发生变化")
                    if args.suite == "legacy-account" and any(measured[key] != value for key, value in expected_response.items()):
                        raise RuntimeError(f"{mode} 第 {sample + 1} 个样本 HTTP 或完整 body 发生变化")
                    samples[variant].append({"sample": sample + 1, **measured})
                if args.suite == "legacy-account" and samples["before"][-1]["sql"] != samples["after"][-1]["sql"]:
                    raise RuntimeError(f"{mode} 第 {sample + 1} 对样本 SQL 数量不同")
            summary = {variant: _summary(values) for variant, values in samples.items()}
            summary.update(path=path, query=query, complete_json_equal=True,
                           matched_total=expected.get("total"),
                           returned_items=len(expected.get("items", [])),
                           p50_change_percent=round((summary["after"]["p50_ms"] / summary["before"]["p50_ms"] - 1) * 100, 2),
                           p95_change_percent=round((summary["after"]["p95_ms"] / summary["before"]["p95_ms"] - 1) * 100, 2))
            if args.suite == "legacy-account":
                summary.update(**expected_response, complete_body_equal=True, http_status_equal=True,
                               paired_sql_count_equal=True,
                               returned_events=len((expected.get("task") or {}).get("events", [])))
            result["measurements"][mode] = summary
            result["raw_samples"][mode] = samples
            print(json.dumps({"mode": mode, **summary}, ensure_ascii=False), flush=True)
        if _source_hashes() != source_hashes:
            raise RuntimeError("测量期间相关源码发生变化，结果不可验收")
        result["source_unchanged_during_measurement"] = True
    finally:
        if clock_patch is not None:
            clock_patch.stop()
        drop_schema(schema)
        with postgres.connect() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname=%s)", (schema,))
            result["schema_cleaned"] = bool(cursor.fetchone()[0])
        postgres.close_pools()
        print(json.dumps({"schema_cleaned": result["schema_cleaned"]}), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2000)
    parser.add_argument("--accounts", type=int, default=1000)
    parser.add_argument("--events", type=int, default=200)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--compare-ref", default="2fe57ac")
    parser.add_argument("--suite", choices=("operations", "legacy-account"), default="operations")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--isolated", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rows < 2000 or args.accounts < 1000 or args.samples < 20 or args.warmups < 1 or args.events < 0:
        parser.error("至少 2000 条任务、1000 个账号、20 个样本、1 次预热，事件数不得为负")
    if args.suite == "legacy-account" and args.samples < 25:
        parser.error("legacy-account 阶段 B 基准至少 25 个样本")
    if not args.isolated:
        from tools.test_isolated import build_isolated_environment
        env = build_isolated_environment(project_root=ROOT, schema="test_task_api_" + uuid.uuid4().hex[:12])
        return subprocess.call([sys.executable, __file__, *sys.argv[1:], "--isolated"], cwd=ROOT, env=env)

    def stop(_signum, _frame):
        raise KeyboardInterrupt("停止测量并清理隔离 schema")
    signal.signal(signal.SIGTERM, stop)
    result = _run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"任务中心 API 基准失败：{type(exc).__name__}；未输出连接参数。", file=sys.stderr)
        raise SystemExit(1) from None
