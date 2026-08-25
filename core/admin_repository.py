# -*- coding: utf-8 -*-
"""管理后台只读仓储。

这里是 WebUI 列表、facets、revision 和总览聚合的唯一入口。业务写入仍由 db.py 和
各领域 service 负责；读仓储绝不扫描兼容文件，也不在 GET 请求中同步数据。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from psycopg.rows import dict_row

from core import postgres_store, record_store


@dataclass(frozen=True)
class PageRequest:
    page: int = 1
    page_size: int = 20
    filters: dict[str, str] = field(default_factory=dict)

    @property
    def limit(self) -> int:
        return max(1, min(500, int(self.page_size or 20)))

    @property
    def offset(self) -> int:
        return (max(1, int(self.page or 1)) - 1) * self.limit


def _connect():
    record_store.init()
    return postgres_store.connect(row_factory=dict_row)


def _q(spec: record_store.TableSpec) -> str:
    return postgres_store.qualified(spec.name)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _facet_dict(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        facet = str(row.get("facet") or "")
        value = str(row.get("value") or "").strip().lower()
        if not facet or not value:
            continue
        grouped.setdefault(facet, []).append({"value": value, "count": int(row.get("count") or 0)})
    for items in grouped.values():
        items.sort(key=lambda item: (-int(item["count"]), str(item["value"])))
    return grouped


def _revision(total: int, latest: Any, visible_state: Any = None) -> str:
    """生成不会漏掉同一秒内连续更新的列表版本号。

    业务表里的 ``updated_at`` 仍有一部分历史写法只有秒级精度。只使用
    ``COUNT + MAX(updated_at)`` 时，queued -> running -> success 如果发生在同一秒，
    前端会误判为没有变化。当前页本来就已经读进内存，顺手对可见状态做短签名，
    不增加 SQL，也不随全表规模增长。
    """
    base = f"{int(total)}:{str(latest or '')}"
    if visible_state is None:
        return base
    payload = json.dumps(
        visible_state,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"{base}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


_ACCOUNT_ACCESS_TOKEN_PRESENT = "COALESCE(a.account_has_access_token, FALSE)"
_ACCOUNT_PASSWORD_PRESENT = "COALESCE(a.account_has_password, FALSE)"
_ACCOUNT_TOTP_PRESENT = "COALESCE(a.account_totp_enabled, FALSE)"

_ACCOUNT_TRIAL_VALUE = """CASE
    WHEN COALESCE(a.current_plan_type, a.plan_type, '') <> ''
         AND LOWER(COALESCE(a.current_plan_type, a.plan_type, '')) <> 'free'
      THEN 'not_applicable'
    WHEN COALESCE(a.current_plan_type, a.plan_type, '') = ''
         OR COALESCE(a.plan_check_status, '') IN ('queued', 'running')
      THEN 'pending'
    WHEN COALESCE(a.plan_check_status, '') = 'failed'
      THEN CASE
        WHEN NULLIF(a.data->>'plan_last_success_at', '') IS NOT NULL AND a.plus_trial_eligible IS TRUE THEN 'eligible'
        WHEN NULLIF(a.data->>'plan_last_success_at', '') IS NOT NULL THEN 'ineligible'
        ELSE 'failed'
      END
    WHEN COALESCE(a.plan_check_status, '') <> 'success'
         AND LOWER(COALESCE(a.data->>'plan_check_ok', 'false')) NOT IN ('true', '1', 'yes')
      THEN 'pending'
    WHEN a.plus_trial_eligible IS TRUE THEN 'eligible'
    ELSE 'ineligible'
END"""

_ACCOUNT_RISK_VALUE = """CASE
    WHEN COALESCE(a.account_deactivation_detected, FALSE) THEN 'detected'
    WHEN COALESCE(a.deactivation_mail_scan_status, '') = 'success' THEN 'clear'
    ELSE 'pending'
END"""


def _account_where(
    archived: str,
    plan: str,
    q: str,
    date_from: str,
    date_to: str,
    filters: dict[str, str],
) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    archived = _text(archived).lower()
    if archived in {"1", "true", "yes", "only"}:
        where.append("a.archived IS TRUE")
    elif archived not in {"all", "include"}:
        where.append("a.archived IS FALSE")
    if plan:
        if plan == "plus":
            where.append("LOWER(COALESCE(a.current_plan_type, a.plan_type, '')) LIKE %s AND LOWER(COALESCE(a.current_plan_type, a.plan_type, '')) NOT LIKE %s")
            params.extend(("%plus%", "%free%"))
        else:
            where.append("LOWER(COALESCE(a.current_plan_type, a.plan_type, '')) = %s")
            params.append(plan.lower())
    if q:
        where.append("(a.email ILIKE %s OR COALESCE(a.data->>'user_name', '') ILIKE %s)")
        params.extend((f"%{q}%", f"%{q}%"))
    if date_from:
        where.append("LEFT(a.created_at, 10) >= %s")
        params.append(date_from[:10])
    if date_to:
        where.append("LEFT(a.created_at, 10) <= %s")
        params.append(date_to[:10])

    value = _text(filters.get("id"))
    if value:
        where.append("CAST(a.id AS TEXT) ILIKE %s")
        params.append(f"%{value.lstrip('#')}%")
    value = _text(filters.get("email"))
    if value:
        where.append("(a.email ILIKE %s OR COALESCE(a.data->>'user_name', '') ILIKE %s)")
        params.extend((f"%{value}%", f"%{value}%"))
    value = _text(filters.get("source")).lower()
    if value:
        where.append("LOWER(COALESCE(a.email_source, '')) = %s")
        params.append(value)
    value = _text(filters.get("token")).lower()
    if value in {"has", "none"}:
        predicate = _ACCOUNT_ACCESS_TOKEN_PRESENT
        where.append(predicate if value == "has" else f"NOT ({predicate})")
    value = _text(filters.get("password")).lower()
    if value in {"has", "none"}:
        where.append(_ACCOUNT_PASSWORD_PRESENT if value == "has" else f"NOT {_ACCOUNT_PASSWORD_PRESENT}")
    value = _text(filters.get("trial")).lower()
    if value:
        where.append(f"({_ACCOUNT_TRIAL_VALUE}) = %s")
        params.append(value)
    value = _text(filters.get("totp")).lower()
    if value in {"enabled", "disabled"}:
        where.append(_ACCOUNT_TOTP_PRESENT if value == "enabled" else f"NOT {_ACCOUNT_TOTP_PRESENT}")
    value = _text(filters.get("risk")).lower()
    if value:
        where.append(f"({_ACCOUNT_RISK_VALUE}) = %s")
        params.append(value)
    value = _text(filters.get("codex")).lower()
    if value:
        where.append("LOWER(COALESCE(a.codex_status, '')) = %s")
        params.append(value)
    return where, params


def list_accounts(
    request: PageRequest,
    *,
    archived: str = "0",
    plan: str = "",
    q: str = "",
    date_from: str = "",
    date_to: str = "",
) -> dict:
    from core import db

    accounts = _q(record_store.ACCOUNTS)
    where, params = _account_where(archived, plan, q, date_from, date_to, request.filters)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    base_where, base_params = _account_where(archived, "", "", "", "", {})
    base_clause = f" WHERE {' AND '.join(base_where)}" if base_where else ""
    # 旧写法用 9 段 UNION ALL 重复扫描账号表，生产数据里的 extra_json 较大时，
    # facets 一项就要约 200 ms。这里先物化一次轻量投影，再展开九个维度聚合；
    # 复杂 JSON/正则表达式只计算一遍。
    facet_sql = f"""
        WITH base AS MATERIALIZED (
            SELECT
                LOWER(COALESCE(a.email_source, '')) AS source,
                CASE WHEN {_ACCOUNT_ACCESS_TOKEN_PRESENT} THEN 'has' ELSE 'none' END AS token,
                CASE WHEN {_ACCOUNT_PASSWORD_PRESENT} THEN 'has' ELSE 'none' END AS password,
                LOWER(COALESCE(a.current_plan_type, a.plan_type, '')) AS plan,
                {_ACCOUNT_TRIAL_VALUE} AS trial,
                CASE WHEN {_ACCOUNT_TOTP_PRESENT} THEN 'enabled' ELSE 'disabled' END AS totp,
                {_ACCOUNT_RISK_VALUE} AS risk,
                LOWER(COALESCE(a.codex_status, '')) AS codex,
                LOWER(COALESCE(a.data->>'account_status', 'active')) AS account_status
              FROM {accounts} a{base_clause}
        )
        SELECT f.facet, f.value, COUNT(*) AS count
          FROM base b
          CROSS JOIN LATERAL (VALUES
              ('source', b.source),
              ('token', b.token),
              ('password', b.password),
              ('plan', b.plan),
              ('trial', b.trial),
              ('totp', b.totp),
              ('risk', b.risk),
              ('codex', b.codex),
              ('account_status', b.account_status)
          ) AS f(facet, value)
         WHERE NULLIF(f.value, '') IS NOT NULL
         GROUP BY f.facet, f.value
    """
    promoted = ["id", *record_store.ACCOUNTS.promoted]
    selected = ", ".join(f"a.{postgres_store.quote_identifier(column)}" for column in promoted)
    safe_data = (
        "a.data - ARRAY['access_token','id_token','refresh_token','password','login_password',"
        "'registration_password','totp_secret','extra_json','copy_line','original_email_line']::text[] "
        f"|| jsonb_build_object('has_access_token', {_ACCOUNT_ACCESS_TOKEN_PRESENT}, "
        f"'has_account_password', {_ACCOUNT_PASSWORD_PRESENT}, 'totp_enabled', {_ACCOUNT_TOTP_PRESENT})"
    )
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total, MAX(a.updated_at) AS latest FROM {accounts} a{clause}", params)
        aggregate = cur.fetchone()
        cur.execute(
            f"SELECT {selected}, ({safe_data}) AS data FROM {accounts} a{clause} ORDER BY a.id DESC LIMIT %s OFFSET %s",
            (*params, request.limit, request.offset),
        )
        rows = [db.decorate_account(record_store.merge_row(record_store.ACCOUNTS, row)) for row in cur.fetchall()]
        cur.execute(facet_sql, base_params)
        facets = _facet_dict(cur.fetchall())
    total = int(aggregate["total"] or 0)
    return {
        "ok": True,
        "items": rows,
        "total": total,
        "page": max(1, int(request.page or 1)),
        "page_size": request.limit,
        "offset": request.offset,
        "limit": request.limit,
        "revision": _revision(total, aggregate["latest"], rows),
        "facets": facets,
    }


def list_account_statuses(
    request: PageRequest,
    *,
    archived: str = "0",
    plan: str = "",
    q: str = "",
) -> dict:
    accounts = _q(record_store.ACCOUNTS)
    where, params = _account_where(archived, plan, q, "", "", {})
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    fields = (
        "id", "email", "archived", "plan_type", "current_plan_type", "plus_trial_eligible",
        "codex_status", "plan_check_status", "extract_link_status", "updated_at", "data",
    )
    selected = ", ".join(f"a.{postgres_store.quote_identifier(name)}" for name in fields)
    selected += (
        ", (a.data - ARRAY['access_token','id_token','refresh_token','password','login_password',"
        "'registration_password','totp_secret','extra_json']::text[] "
        "|| jsonb_build_object('has_access_token', "
        f"{_ACCOUNT_ACCESS_TOKEN_PRESENT})) AS data"
    )
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total, MAX(a.updated_at) AS latest FROM {accounts} a{clause}", params)
        aggregate = cur.fetchone()
        cur.execute(
            f"SELECT {selected} FROM {accounts} a{clause} ORDER BY a.id DESC LIMIT %s OFFSET %s",
            (*params, request.limit, request.offset),
        )
        raw_rows = cur.fetchall()
    wanted = {
        "plan_check_status", "plan_check_ok", "plan_check_error", "plan_check_trigger",
        "plan_check_queued_at", "plan_check_started_at", "plan_check_completed_at", "plan_checked_at",
        "plan_last_success_at", "plan_check_network_route", "plan_check_proxy_used",
        "plan_check_proxy_fallback_reason", "expires_at", "plan_expires_at", "plan_renews_at", "renews_at",
        "billing_period", "billing_currency", "discount_amount", "discount_type", "discount_expires_at",
        "discount_promo_campaign_id", "extract_link_status", "extract_link_ok", "extract_link_type",
        "extract_link_message", "extract_link_error", "extract_link_long_url", "extract_link_copy_paste",
        "extract_link_image_url_png", "extract_link_image_url_svg", "extract_link_expires_at", "codex_status",
        "codex_error", "access_token",
    }
    items = []
    for raw in raw_rows:
        row = record_store.merge_row(record_store.ACCOUNTS, raw)
        item = {key: value for key, value in row.items() if key in wanted | {"id", "email", "archived", "plan_type", "current_plan_type", "plus_trial_eligible"} and value not in (None, "")}
        item["has_access_token"] = bool(_text(row.get("has_access_token")))
        items.append(item)
    total = int(aggregate["total"] or 0)
    return {
        "ok": True,
        "items": items,
        "total": total,
        "page": max(1, int(request.page or 1)),
        "page_size": request.limit,
        "revision": _revision(total, aggregate["latest"], items),
    }


_JOB_PASSWORD_PRESENT = _ACCOUNT_PASSWORD_PRESENT
_JOB_TOTP_PRESENT = _ACCOUNT_TOTP_PRESENT
_JOB_SETUP_COMPLETE = f"""(
    {_JOB_PASSWORD_PRESENT}
    AND COALESCE(a.plan_check_status, '') = 'success'
    AND {_JOB_TOTP_PRESENT}
    AND COALESCE(j.data#>>'{{progress_steps,twofa,state}}', '') <> 'failed'
    AND COALESCE(a.data->>'extra_json', '') !~ '"twofa"[[:space:]]*:[[:space:]]*\\{{[^}}]*"status"[[:space:]]*:[[:space:]]*"failed"'
)"""
_JOB_DISPLAY_STATUS = f"""CASE
    WHEN a.id IS NOT NULL AND j.account_id IS NOT NULL THEN
      CASE WHEN COALESCE(a.codex_status, '') = 'success' AND {_JOB_SETUP_COMPLETE}
           THEN 'success' ELSE 'partial_success' END
    ELSE COALESCE(j.status, '')
END"""


def _job_where(filters: dict[str, str]) -> tuple[list[str], list[Any]]:
    where: list[str] = []
    params: list[Any] = []
    value = _text(filters.get("q"))
    if value:
        where.append("(CAST(j.id AS TEXT) ILIKE %s OR COALESCE(j.email, '') ILIKE %s OR j.data::text ILIKE %s)")
        params.extend((f"%{value}%", f"%{value}%", f"%{value}%"))
    value = _text(filters.get("id")).lstrip("#")
    if value:
        where.append("CAST(j.id AS TEXT) ILIKE %s")
        params.append(f"%{value}%")
    value = _text(filters.get("email"))
    if value:
        where.append("COALESCE(j.email, '') ILIKE %s")
        params.append(f"%{value}%")
    value = _text(filters.get("email_source")).lower()
    if value:
        where.append("LOWER(COALESCE(j.data->>'email_source', '')) = %s")
        params.append(value)
    value = _text(filters.get("proxy"))
    if value:
        where.append("CONCAT_WS(' ', j.data->>'proxy_provider', j.data->>'proxy_endpoint', j.data->>'proxy_region', j.data->>'proxy_status') ILIKE %s")
        params.append(f"%{value}%")
    value = _text(filters.get("error"))
    if value:
        where.append("COALESCE(j.data->>'error_message', '') ILIKE %s")
        params.append(f"%{value}%")
    value = _text(filters.get("date_from"))
    if value:
        where.append("LEFT(COALESCE(j.data->>'started_at', j.created_at), 10) >= %s")
        params.append(value[:10])
    value = _text(filters.get("date_to"))
    if value:
        where.append("LEFT(COALESCE(j.data->>'completed_at', j.created_at), 10) <= %s")
        params.append(value[:10])
    value = _text(filters.get("status")).lower()
    if value:
        where.append(f"({_JOB_DISPLAY_STATUS}) = %s")
        params.append(value)
    return where, params


def list_jobs(request: PageRequest) -> dict:
    from core import registration_service as service

    jobs = _q(record_store.JOBS)
    accounts = _q(record_store.ACCOUNTS)
    where, params = _job_where(request.filters)
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    from_sql = f" FROM {jobs} j LEFT JOIN {accounts} a ON a.id = j.account_id"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total, MAX(j.updated_at) AS latest{from_sql}{clause}", params)
        aggregate = cur.fetchone()
        cur.execute(
            f"SELECT j.*, ({_JOB_DISPLAY_STATUS}) AS projected_display_status{from_sql}{clause} "
            "ORDER BY j.id DESC LIMIT %s OFFSET %s",
            (*params, request.limit, request.offset),
        )
        raw_page = cur.fetchall()
        facet_where, facet_params = _job_where({key: value for key, value in request.filters.items() if key != "status"})
        facet_clause = f" WHERE {' AND '.join(facet_where)}" if facet_where else ""
        cur.execute(
            f"""
            SELECT 'status' AS facet, ({_JOB_DISPLAY_STATUS}) AS value, COUNT(*) AS count
              {from_sql}{facet_clause} GROUP BY 2
            UNION ALL
            SELECT 'email_source', LOWER(COALESCE(j.data->>'email_source', '')), COUNT(*)
              {from_sql}{facet_clause} GROUP BY 2
            """,
            facet_params * 2,
        )
        facets = _facet_dict(cur.fetchall())
        cur.execute(
            f"""
            WITH latest AS (
                SELECT batch_id FROM {jobs}
                 WHERE NULLIF(batch_id, '') IS NOT NULL
                 ORDER BY id DESC LIMIT 1
            )
            SELECT j.* FROM {jobs} j JOIN latest l ON l.batch_id = j.batch_id
             ORDER BY COALESCE((j.data->>'batch_index')::int, 0), j.id
            """
        )
        progress_rows = [record_store.merge_row(record_store.JOBS, row) for row in cur.fetchall()]
    page_rows = [record_store.merge_row(record_store.JOBS, row) for row in raw_page]
    projected = {int(raw["id"]): str(raw.get("projected_display_status") or "") for raw in raw_page}
    retry = service.get_retry_info_bulk(page_rows)
    for row in page_rows:
        info = retry.get(int(row.get("id") or 0), {})
        row.update(info)
        if not info.get("display_status"):
            row["display_status"] = projected.get(int(row.get("id") or 0), row.get("status"))
    total = int(aggregate["total"] or 0)
    status_counts = {item["value"]: int(item["count"]) for item in facets.get("status", [])}
    status_counts["active"] = sum(status_counts.get(key, 0) for key in ("pending", "running", "stopping"))
    return {
        "ok": True,
        "items": page_rows,
        "total": total,
        "page": max(1, int(request.page or 1)),
        "page_size": request.limit,
        "offset": request.offset,
        "limit": request.limit,
        "revision": _revision(total, aggregate["latest"], [*page_rows, *progress_rows]),
        "facets": facets,
        "status_counts": status_counts,
        "progress_rows": progress_rows,
    }


_POOL_SPECS = {
    "outlook": record_store.OUTLOOK_POOL,
    "generic_api": record_store.GENERIC_API_POOL,
    "cloudflare_domain": record_store.DOMAIN_POOL,
    "icloud_hide": record_store.ICLOUD_HIDE_POOL,
}


def _pool_union() -> str:
    parts = []
    for source, spec in _POOL_SPECS.items():
        parts.append(
            f"SELECT '{source}'::text AS source, id, email, created_at, updated_at, status, used_at, "
            f"registered_account_id, data FROM {_q(spec)}"
        )
    return " UNION ALL ".join(parts)


def list_email_pool(request: PageRequest) -> dict:
    pool = _pool_union()
    accounts = _q(record_store.ACCOUNTS)
    filters = request.filters
    where: list[str] = []
    params: list[Any] = []
    source = _text(filters.get("source")).lower()
    if source and source != "all":
        where.append("p.source = %s")
        params.append(source)
    status = _text(filters.get("status")).lower()
    if status:
        where.append("LOWER(COALESCE(p.status, '')) = %s")
        params.append(status)
    q = _text(filters.get("q"))
    if q:
        where.append("(p.email ILIKE %s OR p.data::text ILIKE %s)")
        params.extend((f"%{q}%", f"%{q}%"))
    token = _text(filters.get("token")).lower()
    token_present = "NULLIF(BTRIM(COALESCE(a.data->>'access_token', p.data->>'access_token', '')), '') IS NOT NULL"
    if token in {"has", "none"}:
        where.append(token_present if token == "has" else f"NOT ({token_present})")
    imported = _text(filters.get("imported_date"))
    if imported:
        where.append("LEFT(COALESCE(p.data->>'imported_at', p.created_at), 10) = %s")
        params.append(imported[:10])
    used = _text(filters.get("used_date"))
    if used:
        where.append("LEFT(COALESCE(p.used_at, ''), 10) = %s")
        params.append(used[:10])
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    from_sql = f" FROM ({pool}) p LEFT JOIN {accounts} a ON LOWER(a.email) = LOWER(p.email)"
    safe_pool_data = (
        "p.data - ARRAY['password','client_id','refresh_token','access_token','totp_secret',"
        "'code_url','copy_line','account_copy_line','original_line']::text[] "
        "|| jsonb_build_object("
        "'has_password', NULLIF(BTRIM(COALESCE(p.data->>'password', '')), '') IS NOT NULL, "
        "'has_refresh_token', NULLIF(BTRIM(COALESCE(p.data->>'refresh_token', '')), '') IS NOT NULL, "
        "'has_code_url', NULLIF(BTRIM(COALESCE(p.data->>'code_url', '')), '') IS NOT NULL)"
    )
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total, MAX(p.updated_at) AS latest{from_sql}{clause}", params)
        aggregate = cur.fetchone()
        cur.execute(
            f"SELECT p.source, p.id, p.email, p.created_at, p.updated_at, p.status, p.used_at, "
            f"p.registered_account_id, ({safe_pool_data}) AS data, "
            f"a.id AS joined_account_id, ({token_present}) AS has_access_token{from_sql}{clause} "
            "ORDER BY COALESCE(p.data->>'imported_at', p.created_at, p.used_at, '') DESC, p.id DESC LIMIT %s OFFSET %s",
            (*params, request.limit, request.offset),
        )
        raw_rows = cur.fetchall()
        cur.execute(
            f"""
            SELECT 'source' AS facet, p.source AS value, COUNT(*) AS count {from_sql} GROUP BY p.source
            UNION ALL
            SELECT 'status', LOWER(COALESCE(p.status, '')), COUNT(*) {from_sql} GROUP BY 2
            UNION ALL
            SELECT 'token', CASE WHEN {token_present} THEN 'has' ELSE 'none' END, COUNT(*) {from_sql} GROUP BY 2
            """
        )
        facets = _facet_dict(cur.fetchall())
    sensitive = {
        "password", "client_id", "refresh_token", "access_token", "totp_secret",
        "code_url", "copy_line", "account_copy_line", "original_line",
    }
    items = []
    for raw in raw_rows:
        source = str(raw["source"])
        spec = _POOL_SPECS[source]
        joined_id = raw.get("joined_account_id")
        has_access_token = bool(raw.get("has_access_token"))
        payload = dict(raw)
        for key in ("source", "joined_account_id", "has_access_token"):
            payload.pop(key, None)
        item = record_store.merge_row(spec, payload)
        item["source"] = source
        item["registered_account_id"] = item.get("registered_account_id") or joined_id
        item["has_access_token"] = has_access_token
        item["has_password"] = bool(item.get("has_password"))
        item["has_refresh_token"] = bool(item.get("has_refresh_token"))
        item["has_code_url"] = bool(item.get("has_code_url"))
        for key in sensitive:
            item.pop(key, None)
        items.append(item)
    total = int(aggregate["total"] or 0)
    return {
        "ok": True,
        "items": items,
        "total": total,
        "page": max(1, int(request.page or 1)),
        "page_size": request.limit,
        "offset": request.offset,
        "limit": request.limit,
        "revision": _revision(total, aggregate["latest"], items),
        "facets": facets,
        "compact": True,
    }


def _codex_item(row: dict) -> dict:
    from core.codex_token_refresh_service import oauth_metadata, refresh_error_requires_reauth

    merged = record_store.merge_row(record_store.CODEX_CREDENTIALS, row)
    # 列表查询刻意不取 content（里面含完整 token）。用写入时保存的生命周期元数据
    # 重新计算时间状态，过期倒计时仍准确，又不会让秘密进入普通 GET 的内存/日志。
    synthetic = {
        "expired": merged.get("expired") or merged.get("oauth_expires_at") or "",
        "access_token": "present" if merged.get("access_token_preview") else "",
        "refresh_token": "present" if merged.get("oauth_refreshable") else "",
    }
    oauth = oauth_metadata(synthetic)
    oauth["oauth_reauth_required"] = refresh_error_requires_reauth(merged.get("oauth_refresh_error"))
    return {
        "filename": merged.get("filename"),
        "email": merged.get("email") or "",
        "plan": merged.get("plan") or "",
        "account_id": merged.get("account_id") or "",
        "type": merged.get("type") or "codex",
        "last_refresh": merged.get("last_refresh") or "",
        "expired": merged.get("expired") or "",
        # 普通列表只表达“已保存”，不返回 token 前缀；短 token 的所谓 preview
        # 很可能就是完整秘密。
        "access_token_preview": "已保存" if merged.get("access_token_preview") else "",
        "size": int(merged.get("size") or 0),
        "mtime": merged.get("mtime") or merged.get("updated_at"),
        "exported_at": merged.get("exported_at"),
        "exported_count": int(merged.get("exported_count") or 0),
        "sub2_uploaded_at": merged.get("sub2_uploaded_at"),
        "sub2_uploaded_count": int(merged.get("sub2_uploaded_count") or 0),
        "sub2_sync_error": merged.get("sub2_sync_error"),
        "oauth_refresh_attempted_at": merged.get("oauth_refresh_attempted_at"),
        "oauth_refresh_error": merged.get("oauth_refresh_error"),
        "archived": bool(merged.get("archived")),
        "archived_at": merged.get("archived_at"),
        **oauth,
    }


def list_codex(request: PageRequest) -> dict:
    table = _q(record_store.CODEX_CREDENTIALS)
    filters = request.filters
    where: list[str] = []
    params: list[Any] = []
    archived = _text(filters.get("archived")).lower()
    if archived in {"1", "true", "yes", "only"}:
        where.append("c.archived IS TRUE")
    elif archived not in {"all", "include"}:
        where.append("c.archived IS FALSE")
    q = _text(filters.get("q"))
    if q:
        where.append("(c.filename ILIKE %s OR COALESCE(c.email, '') ILIKE %s OR COALESCE(c.account_id, '') ILIKE %s)")
        params.extend((f"%{q}%", f"%{q}%", f"%{q}%"))
    for key, column in (("plan", "plan"), ("oauth_status", "oauth_status")):
        value = _text(filters.get(key)).lower()
        if value:
            where.append(f"LOWER(COALESCE(c.{column}, '')) = %s")
            params.append(value)
    status = _text(filters.get("status")).lower()
    if status == "exported":
        where.append("c.exported_count > 0")
    elif status == "unexported":
        where.append("c.exported_count = 0")
    account_id = _text(filters.get("account_id"))
    if account_id:
        where.append("COALESCE(c.account_id, '') ILIKE %s")
        params.append(f"%{account_id}%")
    expired = _text(filters.get("expired_date"))
    if expired:
        where.append("LEFT(COALESCE(c.oauth_expires_at, c.data->>'expired', ''), 10) = %s")
        params.append(expired[:10])
    date_from = _text(filters.get("date_from"))
    if date_from:
        where.append("LEFT(COALESCE(c.mtime, c.updated_at), 10) >= %s")
        params.append(date_from[:10])
    date_to = _text(filters.get("date_to"))
    if date_to:
        where.append("LEFT(COALESCE(c.mtime, c.updated_at), 10) <= %s")
        params.append(date_to[:10])
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    promoted = ["id", *record_store.CODEX_CREDENTIALS.promoted]
    selected = ", ".join(f"c.{postgres_store.quote_identifier(column)}" for column in promoted)
    selected += ", c.data - 'content' AS data"
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total, MAX(c.updated_at) AS latest FROM {table} c{clause}", params)
        aggregate = cur.fetchone()
        cur.execute(f"SELECT {selected} FROM {table} c{clause} ORDER BY COALESCE(c.mtime, c.updated_at) DESC, c.id DESC LIMIT %s OFFSET %s", (*params, request.limit, request.offset))
        rows = [_codex_item(row) for row in cur.fetchall()]
        cur.execute(
            f"""
            SELECT 'plan' AS facet, LOWER(COALESCE(c.plan, '')) AS value, COUNT(*) AS count FROM {table} c GROUP BY 2
            UNION ALL
            SELECT 'status', CASE WHEN c.archived THEN 'archived' WHEN c.exported_count > 0 THEN 'exported' ELSE 'unexported' END, COUNT(*) FROM {table} c GROUP BY 2
            UNION ALL
            SELECT 'oauth_status', LOWER(COALESCE(c.oauth_status, 'unknown')), COUNT(*) FROM {table} c GROUP BY 2
            """
        )
        facets = _facet_dict(cur.fetchall())
        cur.execute(
            f"SELECT COUNT(*) FILTER (WHERE archived IS FALSE) AS total, "
            "COUNT(*) FILTER (WHERE archived IS FALSE AND exported_count > 0) AS exported "
            f"FROM {table}"
        )
        summary_row = cur.fetchone()
    total = int(aggregate["total"] or 0)
    summary_total = int(summary_row["total"] or 0)
    summary_exported = int(summary_row["exported"] or 0)
    return {
        "ok": True,
        "accounts": rows,
        "total": total,
        "page": max(1, int(request.page or 1)),
        "page_size": request.limit,
        "offset": request.offset,
        "limit": request.limit,
        "revision": _revision(total, aggregate["latest"], rows),
        "facets": facets,
        "summary": {"total": summary_total, "exported": summary_exported, "pending": summary_total - summary_exported},
    }


def dashboard_aggregates() -> dict:
    accounts = _q(record_store.ACCOUNTS)
    jobs = _q(record_store.JOBS)
    codex = _q(record_store.CODEX_CREDENTIALS)
    pool = _pool_union()
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE archived IS FALSE) AS active,
                   COUNT(*) FILTER (WHERE archived IS TRUE) AS archived,
                   COUNT(*) FILTER (WHERE archived IS FALSE AND codex_status = 'success') AS codex_ready
              FROM {accounts}
            """
        )
        account_counts = dict(cur.fetchone())
        cur.execute(
            f"""
            SELECT CASE
                     WHEN LOWER(COALESCE(current_plan_type, plan_type, '')) = 'free'
                          AND plus_trial_eligible IS TRUE THEN 'free_trial_eligible'
                     ELSE COALESCE(NULLIF(LOWER(COALESCE(current_plan_type, plan_type, '')), ''), 'unknown')
                   END AS plan,
                   COUNT(*) AS count
              FROM {accounts}
             WHERE archived IS FALSE
             GROUP BY 1
            """
        )
        plans = {str(row["plan"]): int(row["count"]) for row in cur.fetchall()}
        projected_jobs = (
            f"SELECT {_JOB_DISPLAY_STATUS} AS status, j.created_at FROM {jobs} j "
            f"LEFT JOIN {accounts} a ON a.id = j.account_id"
        )
        cur.execute(f"SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count FROM ({projected_jobs}) p GROUP BY 1")
        job_counts = {str(row["status"]): int(row["count"]) for row in cur.fetchall()}
        cur.execute(
            f"SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count FROM ({projected_jobs}) p "
            "WHERE LEFT(created_at, 10) = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD') GROUP BY 1"
        )
        today_counts = {str(row["status"]): int(row["count"]) for row in cur.fetchall()}
        cur.execute(f"SELECT source, COALESCE(status, 'available') AS status, COUNT(*) AS count FROM ({pool}) p GROUP BY source, status")
        pool_rows = [dict(row) for row in cur.fetchall()]
        cur.execute(
            f"SELECT COUNT(*) FILTER (WHERE archived IS FALSE) AS total, "
            f"COUNT(*) FILTER (WHERE archived IS FALSE AND exported_count > 0) AS exported FROM {codex}"
        )
        codex_row = dict(cur.fetchone())
    return {
        "accounts": {key: int(value or 0) for key, value in account_counts.items()} | {"plans": plans},
        "jobs": {"total": sum(job_counts.values()), "counts": job_counts, "today_counts": today_counts},
        "email_status_rows": pool_rows,
        "codex": {
            "total": int(codex_row.get("total") or 0),
            "exported": int(codex_row.get("exported") or 0),
            "pending": int(codex_row.get("total") or 0) - int(codex_row.get("exported") or 0),
        },
    }
