"""查套餐批次的只读报告：固定名单、所属轮次与 Run 证据。"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import threading
import time

from core.operations.presentation import public_result_status
from core.storage.operations import bulk_schema, store
from core.storage.operations.bulk_common import BulkError, OWNED, TERMINAL, connect, require_row, table

_CACHE: dict[tuple, tuple[float, dict]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_SECONDS = 10
_CACHE_SIZE = 64
_REPORT_VERSION = 1


def _timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def _duration(runs: list[dict], state: str, *, has_execution: bool) -> tuple[float | None, bool]:
    """每账号链首个开始至最后结束；并行子任务不重复累加。"""
    if state not in TERMINAL:
        return None, False
    started = [run for run in runs if run.get("started_at")]
    if not started:
        return None, has_execution
    ranges = [(_timestamp(run.get("started_at")), _timestamp(run.get("completed_at"))) for run in started]
    if any(start is None or end is None or end < start for start, end in ranges):
        return None, True
    if any(public_result_status(run.get("status"), run.get("result_summary")) not in TERMINAL
           and run.get("status") not in {"stopped", "deactivated", "unsupported", "skipped", "interrupted"}
           for run in started):
        return None, True
    return (max(end for _, end in ranges) - min(start for start, _ in ranges)).total_seconds(), False


def aggregate_report(targets: list[dict], *, batch: dict, scope: dict, projection: dict) -> dict:
    """纯聚合入口，绝不读取账号表中的历史套餐或令牌。"""
    from core.bulk_operations.plan_report_evidence import normalize_plan_report_evidence

    buckets = Counter()
    plans = Counter()
    offers = Counter()
    offer_plans = Counter()
    offer_kinds = defaultdict(Counter)
    refresh = Counter()
    elapsed = []
    missing_times = 0
    for target in targets:
        runs = target.get("runs") or []
        primary = [run for run in runs if run.get("relation") in {"owned_root", "owned_continuation"}]
        latest = max(primary or runs, key=lambda run: (run.get("generation") or 0, run.get("id") or 0), default={})
        summary = latest.get("result_summary") or {}
        state = public_result_status(target["outcome"], summary)
        buckets[state] += 1
        duration, missing = _duration(runs, state, has_execution=bool(target.get("chain_started_at") or
            (runs and state not in {"not_executed", "cancelled"})))
        if duration is not None:
            elapsed.append(duration)
        missing_times += int(missing)
        evidence = normalize_plan_report_evidence(runs, state=state,
            projected_result=(target.get("result") or {}).get("result") or {})
        plans[evidence.get("plan") or "unknown"] += 1
        offer = evidence.get("offer") or {}
        offers["with_offer_accounts" if offer.get("has_offer") else
               "confirmed_no_offer_accounts" if offer.get("confirmed_none") else "unknown_accounts"] += 1
        # 同一账号在多个国家查询到同套餐/优惠，只贡献一个账号。
        account_kinds = defaultdict(set)
        for row in offer.get("by_plan") or []:
            if row.get("plan"):
                account_kinds[row["plan"]].update(row.get("kinds") or [])
        for plan, kinds in account_kinds.items():
            offer_plans[plan] += 1
            for kind in kinds:
                offer_kinds[plan][kind] += 1
        for key, value in (evidence.get("at_refresh") or {}).items():
            if value is True:
                refresh[f"{key}_accounts"] += 1
    completed = sum(buckets.get(key, 0) for key in TERMINAL)
    total = len(targets)
    complete = (scope.get("state") in {"completed", "ended", "failed"} and completed == total
                and projection["state"] == "current")
    phase = "preparing" if scope.get("state") == "preparing" else "completed" if complete else "running"
    return {
        "schema_version": _REPORT_VERSION, "batch_id": batch["batch_id"], "operation_key": "plan_check",
        "view": {"kind": scope["kind"], "round_id": scope.get("round_id"), "round_no": scope.get("round_no")},
        "phase": phase, "population_ready": scope.get("target_count") is not None,
        "summary_revision": scope["summary_revision"], "generated_at": datetime.now(timezone.utc).isoformat(),
        "projection": projection,
        "totals": {"accounts": total, "completed": completed, "active": total - completed,
                   **{key: buckets.get(key, 0) for key in ("success", "failed", "partial_success", "not_executed", "cancelled")}},
        "duration": {"sample_count": len(elapsed), "missing_count": missing_times,
                     "avg_seconds": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
                     "min_seconds": round(min(elapsed), 3) if elapsed else None,
                     "max_seconds": round(max(elapsed), 3) if elapsed else None,
                     "measurement": "account_execution_elapsed"},
        "plans": [{"plan": plan, "accounts": count} for plan, count in sorted(plans.items())],
        "offers": {**{key: offers.get(key, 0) for key in
                     ("with_offer_accounts", "confirmed_no_offer_accounts", "unknown_accounts")},
                   "by_plan": [{"plan": plan, "accounts": count,
                               "kinds": [{"kind": kind, "accounts": n}
                                         for kind, n in sorted(offer_kinds[plan].items())]}
                              for plan, count in sorted(offer_plans.items())]},
        "at_refresh": {f"{key}_accounts": refresh.get(f"{key}_accounts", 0) for key in
                       ("expired", "invalid", "missing_token", "attempted", "succeeded", "failed", "pending",
                        "not_needed", "unknown", "not_executed")},
    }


def _load_historical_promotions(cur, targets: list[dict]) -> None:
    """仅缺少新版紧凑证据的本轮账号，按所属 Run 批量取最后逐国回执。"""
    from core.bulk_operations.plan_report_evidence import normalize_plan_report_evidence

    candidates = {}
    for target in targets:
        runs = target.get("runs") or []
        roots = [run for run in runs if run.get("relation") in {"owned_root", "owned_continuation"}]
        latest = max(roots, key=lambda run: (run.get("generation") or 0, run.get("id") or 0), default={})
        summary = latest.get("result_summary") or {}
        state = public_result_status(target["outcome"], summary)
        meta = summary.get("plan_report_evidence")
        if (not latest or state not in {"success", "partial_success"} or summary.get("ok") is not True
                or isinstance(meta, dict) and meta.get("version") == 1):
            continue
        normalized = normalize_plan_report_evidence(runs, state=state,
            projected_result=(target.get("result") or {}).get("result") or {})
        offer = normalized.get("offer") or {}
        promotions = summary.get("account_promotions")
        possibly_truncated = isinstance(promotions, list) and len(promotions) >= 120
        if possibly_truncated or not offer.get("has_offer") and not offer.get("confirmed_none"):
            candidates[latest["id"]] = latest
    if not candidates:
        return
    # run_id 的索引限定本次候选；不扫描账号历史，不逐账号发起查询。
    # 每个国家只保留最后回执，后来的失败不能被先前成功覆盖。
    cur.execute(f"""SELECT DISTINCT ON (run_id,COALESCE(detail->>'country','')) run_id,
      jsonb_build_object('country',detail->'country','phase',detail->'phase','ok',detail->'ok',
        'current_plan_type',detail->'current_plan_type','checked_at',detail->'checked_at',
        'account_promotions',detail->'account_promotions',
        'truncated',COALESCE(detail->'truncated',detail->'promotion_query_snapshot'->'truncated'),
        'promotion_query_snapshot',detail->'promotion_query_snapshot') AS detail
      FROM {table('operation_events')}
      WHERE run_id=ANY(%s) AND event_type='promotion.query.recorded'
      ORDER BY run_id,COALESCE(detail->>'country',''),created_at DESC,id DESC""", (list(candidates),))
    for row in cur.fetchall():
        candidates[row["run_id"]].setdefault("promotion_query_records", []).append(row["detail"])


def get_plan_report(batch_id: int, *, round_id: int | None = None) -> dict:
    """一次固定快照读取；短缓存保护运行中报告，详情轮询不触发逐条扫描。"""
    bulk_schema.require_readable()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        batch = require_row(cur, f"SELECT * FROM {table('operation_batch_controls')} WHERE batch_id=%s", (batch_id,))
        if batch["action_key"] != "plan_check":
            raise BulkError("report_operation_unsupported", "当前批次不支持套餐查询报告。", 422)
        if round_id is not None:
            row = require_row(cur, f"SELECT * FROM {table('operation_batch_rounds')} WHERE id=%s AND batch_id=%s",
                              (round_id, batch_id))
            scope = dict(row, kind="round", round_id=row["id"])
            selection_id, join_round, join_args = row["member_selection_id"], "%s", [round_id]
            outcome = f"COALESCE(tr.outcome,'{row['unmaterialized_bucket']}')"
        else:
            scope = dict(batch, kind="current", target_count=0)
            selection_id, join_round, join_args = batch["selection_id"], "COALESCE(m.latest_requested_round_id,%s)", [batch["initial_round_id"]]
            outcome = "COALESCE(tr.outcome,(SELECT e.key FROM jsonb_each_text(m.current_contribution) e WHERE e.value::bigint=1 LIMIT 1),'pending_submit')"
        database = hashlib.sha256(store.postgres_store.database_url().encode()).hexdigest()
        key = (database, store._schema_name(), batch_id, round_id, scope["summary_revision"], batch["control_revision"],
               scope["state"], scope.get("target_count"), _REPORT_VERSION)
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached and time.monotonic() - cached[0] < _CACHE_SECONDS:
                return deepcopy(cached[1])
        cur.execute(f"""SELECT m.id,m.target_id AS account_id,tr.id AS target_round_id,
          tr.chain_started_at,{outcome} AS outcome,COALESCE(tr.result,'{{}}'::jsonb) AS result
          FROM {table('operation_selection_targets')} m
          LEFT JOIN {table('operation_batch_target_rounds')} tr ON
            tr.canonical_target_id=COALESCE(m.canonical_target_id,m.id) AND tr.round_id={join_round}
          WHERE m.selection_id=%s ORDER BY m.ordinal""", (*join_args, selection_id))
        targets = [dict(row) for row in cur.fetchall()]
        ids = [row["target_round_id"] for row in targets if row["target_round_id"]]
        by_target = defaultdict(list)
        if ids:
            cur.execute(f"""SELECT l.target_round_id,l.relation,l.execution_generation AS generation,
              l.run_id_snapshot AS id,r.status,r.started_at,r.completed_at,r.result_summary,r.error_code,
              jsonb_build_object('plan_auto_refresh_at',r.data->'plan_auto_refresh_at') AS data
              FROM {table('operation_batch_run_links')} l
              LEFT JOIN {table('operation_runs')} r ON r.id=l.run_id_snapshot
              WHERE l.target_round_id=ANY(%s) AND l.relation=ANY(%s)
              ORDER BY l.target_round_id,l.execution_generation,l.run_id_snapshot""", (ids, list(OWNED)))
            for row in cur.fetchall():
                by_target[row["target_round_id"]].append(dict(row))
        for target in targets:
            target["runs"] = by_target[target["target_round_id"]]
        _load_historical_promotions(cur, targets)
        cur.execute(f"""SELECT count(DISTINCT e.target_round_id) AS pending,bool_or(e.error_code IS NOT NULL) AS failed
          FROM {table('operation_projection_outbox')} e
          JOIN {table('operation_batch_target_rounds')} tr ON tr.id=e.target_round_id
          WHERE tr.batch_id=%s AND e.consumer_kind='bulk_target' AND e.processed_at IS NULL
            AND (%s::bigint IS NULL OR tr.round_id=%s)""", (batch_id, round_id, round_id))
        pending = cur.fetchone()
        projection = {"state": "failed" if pending["failed"] else "syncing" if pending["pending"] else "current",
                      "pending_targets": pending["pending"]}
        report = aggregate_report(targets, batch=batch, scope=scope, projection=projection)
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_SIZE:
            _CACHE.pop(min(_CACHE, key=lambda item: _CACHE[item][0]))
        _CACHE[key] = (time.monotonic(), deepcopy(report))
    return report
