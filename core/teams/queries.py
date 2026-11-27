"""候选账号的本地集合读取，不解密或返回认证材料。"""
from __future__ import annotations

import hashlib
import json

from psycopg.rows import dict_row

from core.storage import postgres, records
from core.teams.domain import classify


def _table(name):
    return postgres.qualified(name)


def _rows(conn, sql, params=()):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def account_refs(account_ids, *, conn):
    return {row["id"]: {"id": str(row["id"]), "email": row["email"], "archived": bool(row["archived"])}
            for row in _rows(conn, f"SELECT id,email,archived FROM {_table(records.ACCOUNTS.name)} "
                                   "WHERE id=ANY(%s::bigint[])", (list(map(int, account_ids)),))}


def _candidate(state):
    category, reason = classify(state)
    return {
        "account": {"id": str(state["id"]), "email": state.get("email"),
                    "archived": bool(state.get("archived"))},
        "category": category, "auth_capability": state.get("auth_capability", "unknown"),
        "has_access_token": bool(state.get("has_access_token")),
        "has_password": bool(state.get("has_password")), "totp_enabled": bool(state.get("totp_enabled")),
        "email_status": state.get("email_status") or "unmarked",
        "other_teams": [{**team, "id": str(team["id"])} for team in state.get("other_teams") or []],
        "disabled": category in {"unavailable", "another_team", "missing_auth"}, "reason_code": reason,
    }


def _matches_account(alias, email_column):
    """只给尚未关联且邮箱全局唯一的远端事实补充读取关联。"""
    return (
        f"({alias}.account_id=a.id OR ({alias}.account_id IS NULL "
        f"AND lower(btrim(COALESCE({alias}.{email_column},'')))=lower(btrim(COALESCE(a.email,''))) "
        "AND btrim(a.email)<>'' "
        f"AND NOT EXISTS(SELECT 1 FROM {_table(records.ACCOUNTS.name)} duplicate "
        "WHERE duplicate.id<>a.id AND lower(btrim(COALESCE(duplicate.email,'')))="
        "lower(btrim(COALESCE(a.email,''))))))"
    )


def candidates(team_id, query, *, conn):
    from core.storage.teams.repository import get_account_states
    where, params = [], []
    archived = query.get("archived", "0")
    if archived != "all":
        where.append("a.archived=%s")
        params.append(archived == "only")
    if query.get("scope", "unassigned") == "unassigned":
        where.extend([
            f"NOT EXISTS(SELECT 1 FROM {_table('team_account_ownership')} o WHERE o.account_id=a.id)",
            f"NOT EXISTS(SELECT 1 FROM {_table('team_workspaces')} t WHERE t.manager_account_id=a.id)",
            f"NOT EXISTS(SELECT 1 FROM {_table('team_members')} m WHERE {_matches_account('m', 'email')} AND m.membership_state='joined')",
            f"NOT EXISTS(SELECT 1 FROM {_table('team_invitations')} i WHERE {_matches_account('i', 'email_snapshot')} "
            "AND (i.active OR i.seat_reserved OR i.invitation_state='pending' OR i.membership_state='joined'))",
        ])
    if query.get("q"):
        where.append("(a.email ILIKE %s OR a.id::text=%s)")
        params.extend([f"%{query['q']}%", query["q"]])
    for field, column in (("has_access_token", "account_has_access_token"),
                          ("has_password", "account_has_password"), ("totp_enabled", "account_totp_enabled")):
        if field in query:
            where.append(f"COALESCE(a.{column},FALSE)=%s")
            params.append(query[field])
    if query.get("email_status"):
        where.append("COALESCE(a.email_invalid,FALSE)=%s")
        params.append(query["email_status"] == "invalid")
    predicate = " AND ".join(where) or "TRUE"
    total = _rows(conn, f"SELECT count(*) AS total FROM {_table(records.ACCOUNTS.name)} a WHERE {predicate}", params)[0]["total"]
    page, size = query.get("page", 1), query.get("page_size", 20)
    rows = _rows(conn, f"SELECT a.id FROM {_table(records.ACCOUNTS.name)} a WHERE {predicate} "
                       "ORDER BY a.id DESC LIMIT %s OFFSET %s", (*params, size, (page - 1) * size))
    states = get_account_states(team_id, [row["id"] for row in rows], conn=conn)
    items = [_candidate(states[row["id"]]) for row in rows]
    revision = hashlib.sha256(json.dumps([total, items], sort_keys=True, default=str).encode()).hexdigest()[:24]
    result = {"items": items, "total": total, "page": page, "page_size": size, "revision": revision}
    if query.get("include_facets"):
        result["facets"] = {}
    return result


def resolve(team_id, values, *, conn):
    from core.storage.teams.repository import get_account_states
    normalized = [value.strip() for value in values]
    # 邮箱大小写与现有账号规范一致，数量按规范化输入计算。
    unique = list(dict.fromkeys(value if value.isascii() and value.isdecimal() else value.casefold()
                                for value in normalized))
    ids = [int(value) for value in unique if value.isascii() and value.isdecimal()]
    emails = [value for value in unique if not (value.isascii() and value.isdecimal())]
    rows = _rows(conn, f"SELECT id,email FROM {_table(records.ACCOUNTS.name)} "
                       "WHERE id=ANY(%s::bigint[]) OR lower(btrim(COALESCE(email,'')))=ANY(%s::text[]) ORDER BY id",
                 (ids, emails))
    states = get_account_states(team_id, [row["id"] for row in rows], conn=conn)
    by_id = {str(row["id"]): row["id"] for row in rows}
    by_email = {}
    for row in rows:
        by_email.setdefault(str(row.get("email") or "").strip().casefold(), []).append(row["id"])
    items = []
    for value in unique:
        matches = ([by_id[value]] if value in by_id else []) if value.isascii() and value.isdecimal() else by_email.get(value, [])
        items.append({
            "input": value, "match_status": "not_found" if not matches else ("matched" if len(matches) == 1 else "ambiguous"),
            "candidates": [_candidate(states[account_id]) for account_id in matches],
            "reason_code": "account_not_found" if not matches else None,
        })
    return {"requested_count": len(values), "unique_count": len(unique),
            "duplicate_count": len(values) - len(unique), "items": items}
