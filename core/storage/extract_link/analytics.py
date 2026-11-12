"""提链统计的只读聚合；每个任务仅计入最新一次运行的结果。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.operations.errors import classify_task_error
from core.storage.extract_link import jobs
from core.storage.operations import store as operation_store

_TIMEZONE = ZoneInfo("Asia/Shanghai")
_COUNTS = (
    "total", "extracted", "paid", "plus_confirmed", "failed", "processing",
    "awaiting_payment", "needs_review", "extraction_failed", "payment_failed",
)
_FAILURE_LABELS = {
    "network.dns": "域名解析失败",
    "network.timeout": "网络请求超时",
    "network.connection": "网络连接或 TLS 失败",
    "account.credential": "账号凭据无效或已过期",
    "quota.unavailable": "平台额度不足或不可用",
    "diagnostics.extraction_missing": "提链失败原因未记录",
    "diagnostics.payment_missing": "支付失败原因未记录",
    "diagnostics.task_missing": "任务失败原因未记录",
}


def _failure_identity(code: str, fallback: str) -> tuple[str, str]:
    """只输出共享分类器已识别的固定文案，不返回任意远端错误原文。"""
    info = classify_task_error(
        "", task_type="extract_link", error_code=code,
        result_summary={"cause_code": code}, task_status="failed",
    ) if code else None
    if info and str(info.get("code") or "") == code and code not in {
        "unknown", "unknown.unclassified", "request_unknown", "remote_response_missing",
    }:
        return code, str(info.get("summary") or info.get("kind_label") or "任务失败")
    return fallback, _FAILURE_LABELS[fallback]


def _metrics(row: dict) -> dict:
    result = {key: int(row.get(key) or 0) for key in _COUNTS}
    for numerator, failure, field in (
        ("extracted", "extraction_failed", "extraction_rate"),
        ("paid", "payment_failed", "payment_rate"),
    ):
        denominator = result[numerator] + result[failure]
        result[field] = round(result[numerator] / denominator, 4) if denominator else None
    seconds = row.get("avg_seconds")
    result["avg_seconds"] = round(float(seconds)) if seconds is not None else None
    return result


def workbench_analytics(*, days: int = 7, provider_id: str | None = None, now: datetime | None = None) -> dict:
    """按北京时间创建日期统计，当前积压不受日期范围限制。"""
    if days not in {7, 30, 90}:
        raise ValueError("统计天数仅支持 7、30 或 90 天")
    instant = (now or datetime.now(_TIMEZONE)).astimezone(_TIMEZONE)
    end_date = instant.date()
    start_date = end_date - timedelta(days=days - 1)
    start = datetime.combine(start_date, time.min, _TIMEZONE)
    end = datetime.combine(end_date + timedelta(days=1), time.min, _TIMEZONE)
    operation_store.init()
    clauses, params = jobs._workbench_where(provider_id=provider_id)
    projection = jobs._workbench_projection_sql(clauses, public_status=True, materialized=True)
    conditions = jobs.workbench_status_conditions(public_status=True)
    aggregate = ",\n".join([
        "COUNT(*) AS total",
        "COUNT(*) FILTER (WHERE extraction_status='success') AS extracted",
        "COUNT(*) FILTER (WHERE payment_status='paid') AS paid",
        "COUNT(*) FILTER (WHERE plus_status='confirmed') AS plus_confirmed",
        f"COUNT(*) FILTER (WHERE {conditions['failed']}) AS failed",
        f"COUNT(*) FILTER (WHERE {conditions['processing']}) AS processing",
        f"COUNT(*) FILTER (WHERE {conditions['awaiting_payment']}) AS awaiting_payment",
        f"COUNT(*) FILTER (WHERE {conditions['needs_review']}) AS needs_review",
        "COUNT(*) FILTER (WHERE extraction_status='failed' AND task_status NOT IN ('cancelled','stopped')) AS extraction_failed",
        "COUNT(*) FILTER (WHERE mode IN ('manual_payment','auto_payment') AND extraction_status='success' AND payment_status='failed' AND task_status NOT IN ('cancelled','stopped')) AS payment_failed",
        "AVG(duration_seconds) FILTER (WHERE task_status='success' AND duration_seconds >= 0) AS avg_seconds",
    ])
    # 错误原文只在数据库内用于识别固定类型；不会被读取到统计结果。
    failure_bucket = """CASE
        WHEN error_text ~* 'dns|name.?resolution|域名解析' THEN 'network.dns'
        WHEN error_text ~* 'timeout|timed.?out|超时' THEN 'network.timeout'
        WHEN error_text ~* 'connection|tls|ssl|连接失败|连接中断|证书' THEN 'network.connection'
        WHEN error_text ~* 'token_revoked|credential.expired|token.*(expired|invalid)|凭据.*(无效|过期)' THEN 'account.credential'
        WHEN error_text ~* 'quota|额度|积分不足|cdk.*(invalid|无效|用完)' THEN 'quota.unavailable'
        WHEN extraction_status='success' AND payment_status='failed' THEN 'diagnostics.payment_missing'
        WHEN extraction_status='failed' THEN 'diagnostics.extraction_missing'
        ELSE 'diagnostics.task_missing' END"""
    # 与共享错误分类器的提链平台细分保持一致；通用原因码不能盖过明确失败证据。
    provider_failure_code = """CASE
        WHEN stored_failure_code='extract_provider_failed'
            OR (stored_failure_code='' AND error_text LIKE '%%平台提链失败%%') THEN CASE
            WHEN error_text ~* 'checkout approval' AND error_text ~* 'result=blocked' THEN 'extract_checkout_blocked'
            WHEN error_text ~ '今日应付金额不是[[:space:]]*0' THEN 'extract_nonzero_amount'
            WHEN error_text ~* 'openai checkout http 400'
                AND error_text ~* 'billing country must match request country' THEN 'extract_country_mismatch'
            WHEN error_text ~* 'upi 支付确认' AND error_text LIKE '%%支付提供商拒绝%%' THEN 'extract_upi_rejected'
            WHEN error_text ~* 'openai checkout http 401' AND error_text ~* 'token_revoked' THEN 'extract_checkout_token_revoked'
            WHEN error_text LIKE '%%支付确认被拦截%%' THEN 'extract_payment_blocked'
            WHEN error_text LIKE '%%优惠未生效%%' THEN 'extract_promotion_not_applied'
            WHEN error_text LIKE '%%支付提交失败%%' THEN 'extract_payment_submit_failed'
            WHEN error_text ~* 'sentinel 校验' AND error_text LIKE '%%网络或上游校验异常%%' THEN 'extract_sentinel_failed'
            WHEN error_text LIKE '%%网络连接失败%%' THEN 'extract_connection_failed'
            WHEN error_text LIKE '%%支付授权或审批被阻止%%' THEN 'extract_payment_approval_blocked'
            WHEN error_text ~* 'checkout create failed' AND error_text ~* 'http 400'
                AND error_text ~* 'unusual activity' THEN 'extract_checkout_unusual_activity'
            WHEN error_text LIKE '%%支付方式设置流程失败%%' THEN 'extract_payment_method_failed'
            WHEN error_text LIKE '%%上游结账风控拦截%%' THEN 'extract_checkout_risk_blocked'
            WHEN error_text ~* 'cdk is invalid or unavailable' THEN 'extract_cdk_invalid'
            WHEN error_text ~* 'token_revoked' AND error_text LIKE '%%access_token 已失效%%' THEN 'extract_token_revoked'
            WHEN error_text LIKE '%%请求超时%%' OR (error_text ~* 'curl: [(]28[)]'
                AND error_text ~* 'operation timed out') THEN 'extract_request_timeout'
            WHEN error_text ~* 'curl: [(]35[)]' AND error_text ~* 'tls connect error' THEN 'extract_tls_error'
            WHEN error_text ~* 'curl: [(]60[)]' AND error_text ~* 'ssl certificate problem' THEN 'extract_certificate_error'
            WHEN error_text ~* 'stripe confirm 后审批/结果查询阶段失败' THEN 'extract_approval_query_failed'
            WHEN error_text LIKE '%%任务处理失败%%' THEN 'extract_provider_task_failed'
            ELSE stored_failure_code END
        ELSE stored_failure_code END"""
    sql = f"""WITH {projection}, enriched AS MATERIALIZED (
        SELECT p.*, (p.task_created_at AT TIME ZONE 'Asia/Shanghai')::date AS task_date,
            EXTRACT(EPOCH FROM (r.completed_at-r.started_at)) AS duration_seconds,
            COALESCE(NULLIF(r.result_summary->>'cause_code',''),
                NULLIF(job.public_state->'summary'->>'failure_code',''),
                NULLIF(r.error_code,''), '') AS stored_failure_code,
            COALESCE(r.error_message,'') AS error_text
        FROM projected p
        JOIN filtered_tasks task ON task.id=p.task_id
        LEFT JOIN {operation_store._table('operation_runs')} r ON r.id=task.last_run_id
        LEFT JOIN {operation_store._table('extract_link_provider_jobs')} job ON job.run_id=r.id
    ), diagnosed AS (
        SELECT enriched.*, {provider_failure_code} AS failure_code FROM enriched
    ), scoped AS MATERIALIZED (
        SELECT * FROM diagnosed WHERE task_created_at >= %s AND task_created_at < %s
    ), grouped AS (
        SELECT GROUPING(task_date) AS g_date, GROUPING(provider_id) AS g_provider,
            GROUPING(mode) AS g_mode, task_date, provider_id, mode, {aggregate}
        FROM scoped GROUP BY GROUPING SETS ((), (task_date), (provider_id), (mode))
    ), failures AS (
        SELECT failure_code, {failure_bucket} AS bucket, COUNT(*) AS count
        FROM scoped WHERE {conditions['failed']}
        GROUP BY failure_code, bucket
    )
    SELECT 'metrics' AS kind, to_jsonb(grouped) AS data FROM grouped
    UNION ALL SELECT 'failure', to_jsonb(failures) FROM failures
    UNION ALL SELECT 'current', jsonb_build_object(
        'all', COUNT(*),
        'processing', COUNT(*) FILTER (WHERE {conditions['processing']}),
        'awaiting_payment', COUNT(*) FILTER (WHERE {conditions['awaiting_payment']}),
        'needs_review', COUNT(*) FILTER (WHERE {conditions['needs_review']})) FROM enriched"""
    with operation_store._connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (*params, start, end))
        rows = [dict(row) for row in cur.fetchall()]
    totals = _metrics({})
    providers, modes, daily = [], [], {}
    failures = defaultdict(int)
    current = {"all": 0, "processing": 0, "awaiting_payment": 0, "needs_review": 0}
    for row in rows:
        item = row["data"]
        if row["kind"] == "failure":
            identity = _failure_identity(str(item.get("failure_code") or ""), item["bucket"])
            failures[identity] += int(item["count"])
        elif row["kind"] == "current":
            current = {key: int(item.get(key) or 0) for key in current}
        else:
            metrics = _metrics(item)
            if not item["g_date"]:
                daily[str(item["task_date"])] = metrics
            elif not item["g_provider"]:
                providers.append({"provider_id": item["provider_id"], **metrics})
            elif not item["g_mode"]:
                modes.append({"mode": item["mode"], **metrics})
            else:
                totals = metrics
    return {
        "days": days, "date_from": start_date.isoformat(), "date_to": end_date.isoformat(),
        "totals": totals,
        "daily": [
            {"date": day.isoformat(), **daily.get(day.isoformat(), _metrics({}))}
            for day in (start_date + timedelta(days=index) for index in range(days))
        ],
        "providers": sorted(providers, key=lambda item: (-item["total"], item["provider_id"])),
        "modes": sorted(modes, key=lambda item: item["mode"]),
        "failures": [{"code": code, "label": label, "count": count}
                     for (code, label), count in sorted(failures.items(), key=lambda item: (-item[1], item[0][0]))],
        "current": current, "generated_at": instant.isoformat(),
    }
