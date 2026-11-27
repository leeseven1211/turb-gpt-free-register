#!/usr/bin/env python3
"""在独立 test_ schema 测量 Team 本地加入预览，不读取项目 .env。

调用方必须显式提供本机非生产 DATABASE_URL。脚本清洗子进程环境后生成合成账号，
测量输入校验、真实 service.preview_join、公开 DTO 投影及 Flask JSON 序列化，
最后删除自己的临时 schema。示例：

    DATABASE_URL=已配置的本机开发库 python tools/benchmarks/team_join_preview.py --output /tmp/team-preview.json
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
from math import ceil
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_PREFIX = "test_team_preview_"


def _validate_database(database):
    from psycopg.conninfo import conninfo_to_dict
    from tools.test_isolated import validate_test_database_url

    label = validate_test_database_url(database)
    connection = conninfo_to_dict(database)
    if connection.get("dbname") != "turb_dev":
        raise RuntimeError("此基准只允许显式连接 turb_dev。")
    if connection.get("service") or connection.get("servicefile"):
        raise RuntimeError("此基准不接受 libpq service 间接连接。")
    if connection.get("hostaddr") not in {None, "", "127.0.0.1", "::1"}:
        raise RuntimeError("此基准的 hostaddr 必须为本机回环地址。")
    return label


def _percentile(values, percent):
    return sorted(values)[max(0, ceil(len(values) * percent / 100) - 1)]


def _summary(values):
    return {
        "p50_ms": round(statistics.median(values), 3),
        "p95_ms": round(_percentile(values, 95), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def _save_result(path, result):
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="10,100,1000,10000", help="显式 ID 数量，逗号分隔，各项 1–10000")
    parser.add_argument("--warmups", type=int, default=2, help="每个规模预热次数")
    parser.add_argument("--samples", type=int, default=20, help="每个规模正式测量次数")
    parser.add_argument("--accounts", type=int, help="合成目标账号总数；默认使用最大测量规模")
    parser.add_argument("--output", type=Path, help="JSON 结果文件；不包含数据库凭据")
    parser.add_argument("--profile", action="store_true", help="额外记录各 SQL 耗时并对最慢 SQL 执行 EXPLAIN ANALYZE")
    parser.add_argument("--with-email-snapshots", action="store_true", help="另测最大规模的完整邮箱快照路径")
    parser.add_argument("--isolated", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        args.sizes = [int(value) for value in args.sizes.split(",")]
    except ValueError:
        parser.error("sizes 必须为逗号分隔的整数。")
    if not args.sizes or any(not 1 <= size <= 10000 for size in args.sizes):
        parser.error("显式 ID 规模必须在 1–10000。")
    if args.warmups < 0 or args.samples < 1:
        parser.error("warmups 不能为负，samples 必须大于零。")
    if args.accounts is not None and args.accounts < max(args.sizes):
        parser.error("accounts 不得小于最大测量规模。")
    return args


def _seed(size):
    from core.storage import postgres, records
    from core.storage.teams import schema

    records.init()
    print("合成基准：账号表初始化完成。", flush=True)
    schema.init()
    print("合成基准：Team 表初始化完成。", flush=True)
    with postgres.connect() as conn, conn.cursor() as cur:
        # 一次集合 INSERT 准备数据，不逐行初始化，也不放入认证材料。
        cur.execute(
            f"""INSERT INTO {postgres.qualified(records.ACCOUNTS.name)}
                (id,email,created_at,updated_at,archived,email_source,data)
                SELECT n,'team-preview-'||n||'@example.test',
                       '2026-11-27T00:00:00','2026-11-27T00:00:00',false,'synthetic','{{}}'::jsonb
                FROM generate_series(1,%s) n""",
            (size + 1,),
        )
        cur.execute(
            f"""INSERT INTO {postgres.qualified('team_workspaces')}
                (id,workspace_id,manager_account_id,name,role,purchased_seats,
                 confirmed_member_count,pending_invite_count,members_complete,invitations_complete,
                 members_synced_at,invitations_synced_at,last_synced_at,last_sync_status,snapshot_sequence)
                VALUES (1,'synthetic-preview-workspace',1,'合成基准 Team','owner',%s,
                        1,0,true,true,now(),now(),now(),'success',1)""",
            (size + 1,),
        )
        cur.execute(
            f"""INSERT INTO {postgres.qualified('team_members')}
                (team_id,identity_key,remote_user_id,email,account_id,role,membership_state,last_verified_at)
                VALUES (1,'account:1','synthetic-manager','team-preview-1@example.test',1,'owner','joined',now())"""
        )
        for table in ("registered_accounts", "team_workspaces", "team_members", "team_invitations",
                      "team_account_ownership"):
            cur.execute("ANALYZE " + postgres.qualified(table))
    return [str(value) for value in range(2, size + 2)]


def _business_counts():
    from core.storage import postgres

    tables = ("registered_accounts", "team_workspaces", "team_members", "team_invitations",
              "team_join_requests", "team_join_request_items", "team_outbox", "team_account_ownership",
              "team_auth_contexts", "team_request_receipts")
    counts = {}
    with postgres.connect() as conn, conn.cursor() as cur:
        for name in tables:
            cur.execute("SELECT to_regclass(%s)", (postgres.qualified(name),))
            if cur.fetchone()[0] is not None:
                cur.execute("SELECT count(*) FROM " + postgres.qualified(name))
                counts[name] = cur.fetchone()[0]
    return counts


@contextmanager
def _read_audit(*, profile=False):
    """记录真实 SQL，要求每个读事务先声明 READ ONLY，禁止写入或隐式初始化。"""
    import psycopg
    from core.storage import records
    from core.storage.teams import schema
    from core.teams import service
    from core.teams.auth import TeamAuthenticator
    from core.teams.remote import TeamRemoteAdapter

    original = psycopg.Cursor.execute
    state = {"queries": 0, "read_only_transactions": 0, "external_boundary_calls": 0, "statements": {}}

    def execute(cursor, query, params=None, **kwargs):
        text = " ".join(str(query).strip().split()).upper()
        if text.startswith("SET TRANSACTION "):
            if "READ ONLY" not in text:
                raise AssertionError("预览事务没有声明 READ ONLY。")
            state["read_only_transactions"] += 1
        elif not (text.startswith("SELECT ") or text.startswith("WITH ")):
            raise AssertionError("预览出现非只读 SQL。")
        if re.search(r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|CALL|COPY)\b", text):
            raise AssertionError("预览 SQL 包含写入、锁定或迁移语句。")
        state["queries"] += 1
        if not profile:
            return original(cursor, query, params, **kwargs)
        started = time.perf_counter()
        try:
            return original(cursor, query, params, **kwargs)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            statement = state["statements"].setdefault(str(query), {"sql": str(query), "samples_ms": [], "params": params})
            statement["samples_ms"].append(elapsed)

    def unexpected_remote(*args, **kwargs):
        state["external_boundary_calls"] += 1
        raise AssertionError("本地预览不得进入远端认证或请求。")

    def unexpected_mutation(*args, **kwargs):
        raise AssertionError("本地预览不得初始化存储或创建任务。")

    with ExitStack() as stack:
        stack.enter_context(patch.object(psycopg.Cursor, "execute", execute))
        stack.enter_context(patch.object(records, "init", unexpected_mutation))
        stack.enter_context(patch.object(schema, "init", unexpected_mutation))
        stack.enter_context(patch.object(service, "_enqueue", unexpected_mutation))
        stack.enter_context(patch.object(TeamRemoteAdapter, "_request", unexpected_remote))
        stack.enter_context(patch.object(TeamAuthenticator, "open", unexpected_remote))
        yield state


def measure_preview(team_id, account_ids, *, expected_emails=None, warmups=2, samples=20, profile=False):
    """供本脚本或已准备好隔离合成 schema 的诊断进程复用相同采样口径。"""
    if os.environ.get("PYTHON_DOTENV_DISABLED") != "1" or os.environ.get("TURB_ALLOW_PRODUCTION_DB") != "0":
        raise RuntimeError("复用采样必须先通过隔离环境构建器清洗。")
    from flask import Flask
    from core.storage import postgres
    from core.teams import service
    from core.teams.validation import local_id, validate_payload
    from webui.routes.teams import _PREVIEW, _project

    schema_name = postgres.schema_name()
    if not schema_name.startswith("test_") or schema_name == "public":
        raise RuntimeError("复用采样同样只接受独立 test_ schema。")
    _validate_database(str(os.environ.get("DATABASE_URL") or ""))
    app = Flask(__name__)
    body = {"account_ids": list(account_ids)}
    if expected_emails is not None:
        body["expected_emails"] = dict(expected_emails)
    timings = {"total": [], "validation": [], "service": [], "serialization": []}
    sql_counts = []
    with _read_audit(profile=profile) as audit:
        for sample in range(warmups + samples):
            query_start = audit["queries"]
            transaction_start = audit["read_only_transactions"]
            started = time.perf_counter()
            normalized_team_id = local_id(str(team_id), "team_id")
            payload = validate_payload("preview", body)
            validated_at = time.perf_counter()
            data = service.preview_join(normalized_team_id, payload)
            read_at = time.perf_counter()
            serialized = app.json.dumps({
                "ok": True, "request_id": "benchmark-request", "data": _project(data, _PREVIEW),
            })
            finished = time.perf_counter()
            if audit["read_only_transactions"] - transaction_start != 1:
                raise AssertionError("每次预览必须恰好使用一个 READ ONLY 事务。")
            if data["counts"]["new_count"] != len(account_ids) or data["counts"]["unique_count"] != len(account_ids):
                raise AssertionError("合成目标没有按预期完成本地分类。")
            if sample >= warmups:
                timings["total"].append((finished - started) * 1000)
                timings["validation"].append((validated_at - started) * 1000)
                timings["service"].append((read_at - validated_at) * 1000)
                timings["serialization"].append((finished - read_at) * 1000)
                sql_counts.append(audit["queries"] - query_start)
    total = _summary(timings["total"])
    result = {
        **total, "meets_p95_target": total["p95_ms"] < 50,
        "validation": _summary(timings["validation"]), "service": _summary(timings["service"]),
        "serialization": _summary(timings["serialization"]),
        "sql_per_preview": {"min": min(sql_counts), "max": max(sql_counts)},
        "json_bytes": len(serialized.encode()), "samples_ms": [round(value, 3) for value in timings["total"]],
        "read_only_transactions": audit["read_only_transactions"],
        "external_boundary_calls": audit["external_boundary_calls"],
    }
    if profile:
        ranked = sorted(audit["statements"].values(),
                        key=lambda item: statistics.median(item["samples_ms"]), reverse=True)
        result["sql_profile"] = [{"sql": item["sql"], **_summary(item["samples_ms"])} for item in ranked]
        hotspot = next(item for item in ranked if not item["sql"].strip().upper().startswith("SET "))
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + hotspot["sql"], hotspot["params"])
            result["hotspot_explain"] = cur.fetchone()[0]
    return result


def _run(args):
    database = str(os.environ.get("DATABASE_URL") or "").strip()
    label = _validate_database(database)
    schema_name = os.environ.get("TURB_DB_SCHEMA", "")
    if not re.fullmatch(r"test_team_preview_[0-9a-f]{12}", schema_name):
        raise RuntimeError("基准只接受自身生成的 test_team_preview_ 临时 schema。")
    if os.environ.get("PYTHON_DOTENV_DISABLED") != "1" or os.environ.get("TURB_ALLOW_PRODUCTION_DB") != "0":
        raise RuntimeError("基准必须使用禁用 dotenv 且拒绝生产库的隔离环境。")

    from tests.support_pg import drop_schema

    result = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "database": label, "schema": schema_name, "python": platform.python_version(),
        "platform": platform.platform(), "warmups": args.warmups, "samples": args.samples,
        "scope": "输入校验 + service.preview_join + 公开 DTO 投影 + Flask JSON 序列化；不含 HTTP 传输",
        "data_profile": "合成账号无凭据；单个已确认母号；完整空邀请快照；所有目标为 new，auth_capability=unknown",
        "target_p95_ms": 50, "measurements": {}, "completed": False,
    }
    source_paths = ("core/teams/service.py", "core/teams/validation.py", "core/storage/teams/reads.py", "core/storage/teams/joins.py",
                    "core/storage/teams/preview.py")
    source_hashes = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in source_paths if (ROOT / path).exists()
    }
    result["source_sha256"] = source_hashes
    try:
        started = time.perf_counter()
        ids = _seed(args.accounts or max(args.sizes))
        result["accounts"] = len(ids)
        result["seed_ms"] = round((time.perf_counter() - started) * 1000, 3)
        before = _business_counts()
        for size in args.sizes:
            entry = measure_preview("1", ids[:size], warmups=args.warmups, samples=args.samples, profile=args.profile)
            result["measurements"][str(size)] = entry
            print(json.dumps({"规模": size, "p50_ms": entry["p50_ms"], "p95_ms": entry["p95_ms"]},
                             ensure_ascii=False), flush=True)
            _save_result(args.output, result)
        if args.with_email_snapshots:
            size = max(args.sizes)
            targets = ids[:size]
            result["full_email_snapshots"] = {
                "targets": size,
                **measure_preview("1", targets, expected_emails={
                    account_id: f"team-preview-{account_id}@example.test" for account_id in targets
                }, warmups=args.warmups, samples=args.samples, profile=args.profile),
            }
            _save_result(args.output, result)
        after = _business_counts()
        if before != after:
            raise AssertionError("预览前后业务行数发生变化。")
        result["business_rows_unchanged"] = True
        result["business_rows"] = before
        result["external_boundary_calls"] = 0
        result["all_sizes_meet_p95_target"] = all(
            entry["meets_p95_target"] for entry in result["measurements"].values()
        ) and result.get("full_email_snapshots", {}).get("meets_p95_target", True)
    finally:
        drop_schema(schema_name)
        result["temporary_schema_deleted"] = True
        _save_result(args.output, result)
    result["sources_changed_during_measurement"] = any(
        not (ROOT / path).exists() or hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != checksum
        for path, checksum in source_hashes.items()
    )
    result["completed"] = True
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        _save_result(args.output, result)
        print(json.dumps({"结果文件": str(args.output), "全部规模达到目标": result["all_sizes_meet_p95_target"],
                          "临时schema已删除": True}, ensure_ascii=False), flush=True)
    else:
        print(rendered, end="", flush=True)
    return 0


def main():
    args = _arguments()
    if not args.isolated:
        from tools.test_isolated import build_isolated_environment
        database = str(os.environ.get("DATABASE_URL") or "").strip()
        if not database:
            raise SystemExit("必须显式提供非生产 DATABASE_URL；脚本不会读取项目 .env。")
        _validate_database(database)
        environment = build_isolated_environment(
            database_url=database, schema=_PREFIX + uuid.uuid4().hex[:12], project_root=ROOT,
        )
        return subprocess.call([sys.executable, __file__, *sys.argv[1:], "--isolated"], env=environment, cwd=ROOT)
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
