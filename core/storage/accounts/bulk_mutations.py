"""账号本地批量事实；每个调用在一个事务中集合写入并返回逐项目回执。"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from datetime import datetime, timezone
import json

from core.operations.contracts import BulkItemResult
from core.storage import postgres, records as rs
from core.storage.email import validity


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _targets(account_ids):
    ids, invalid, seen = [], [], set()
    for raw in account_ids or ():
        if type(raw) is int and 0 < raw < 2**63:
            value = raw
        elif isinstance(raw, str) and raw.isascii() and raw.isdecimal() and 0 < int(raw) < 2**63:
            value = int(raw)
        else:
            invalid.append(BulkItemResult(raw, "skipped", "invalid_target", "ID 非法"))
            continue
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids, invalid


def _account_rows(conn, ids=None, *, addresses=None):
    predicate, values = ("id = ANY(%s::bigint[])", ids) if addresses is None else (
        "LOWER(BTRIM(email)) = ANY(%s::text[])", addresses,
    )
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, email FROM {postgres.qualified(rs.ACCOUNTS.name)} "
            f"WHERE {predicate} ORDER BY id FOR UPDATE", (values,),
        )
        return [dict(row) for row in cur.fetchall()]


def _receipt(ids, rows, *, changes=None, skipped=None, invalid=()):
    by_id = {int(row["id"]): row for row in rows}
    failures = skipped or {}
    items = []
    for account_id in ids:
        if account_id in failures:
            code, reason = failures[account_id]
            items.append(BulkItemResult(account_id, "skipped", code, reason))
        elif account_id not in by_id:
            items.append(BulkItemResult(account_id, "skipped", "account_not_found", "账号不存在"))
        else:
            items.append(BulkItemResult(account_id, "updated", data={
                "id": account_id, "email": by_id[account_id]["email"], **(changes or {}),
            }))
    return tuple([*items, *invalid])


def _write_many(account_ids, changes=None, *, delete=False, conn=None):
    ids, invalid = _targets(account_ids)
    if not ids:
        return tuple(invalid)
    rs.init()
    with nullcontext(conn) if conn is not None else rs.transaction() as connection:
        rows = _account_rows(connection, ids)
        selected = [row["id"] for row in rows]
        if selected:
            with connection.cursor() as cur:
                table = postgres.qualified(rs.ACCOUNTS.name)
                if delete:
                    cur.execute(f"DELETE FROM {table} WHERE id = ANY(%s::bigint[]) RETURNING id, email", (selected,))
                else:
                    sets, args = rs._build_set_clause(rs.ACCOUNTS, changes, partial=True)
                    cur.execute(
                        f"UPDATE {table} SET {', '.join(sets)} WHERE id = ANY(%s::bigint[]) RETURNING id, email",
                        [*args, selected],
                    )
                rows = [dict(row) for row in cur.fetchall()]
        return _receipt(ids, rows, changes=changes, invalid=invalid)


def archive_many(account_ids, archived=True, *, conn=None):
    at = _now()
    return _write_many(account_ids, {
        "archived": bool(archived), "archived_at": at if archived else None, "updated_at": at,
    }, conn=conn)


def delete_many(account_ids, *, conn=None):
    return _write_many(account_ids, delete=True, conn=conn)


def update_note_many(account_ids, note, *, conn=None):
    text = str(note or "")
    if len(text) > 2000:
        raise ValueError("备注最多 2000 个字符")
    at = _now()
    return _write_many(account_ids, {"note": text, "note_updated_at": at, "updated_at": at}, conn=conn)


def _patch_facts(spec, values, *, conn):
    """每张表一次 UPDATE；逐行差异仅作为 JSONB 参数传入。"""
    if not values:
        return
    payload = [{"id": row_id, "facts": facts} for row_id, facts in values]
    at = _now()
    promoted = "email_invalid" in spec.promoted
    sets = ("email_invalid = (patch.facts->>'email_invalid')::boolean, " if promoted else "")
    fragment = "(patch.facts - 'email_invalid')" if promoted else "patch.facts"
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {postgres.qualified(spec.name)} AS target "
            f"SET {sets}data = target.data || {fragment}, updated_at = %s "
            "FROM jsonb_to_recordset(%s::jsonb) AS patch(id bigint, facts jsonb) "
            "WHERE target.id = patch.id RETURNING target.id",
            (at, json.dumps(payload, ensure_ascii=False)),
        )
        cur.fetchall()


def _locked_resources(spec, where, params, *, conn):
    return validity._rows(spec, where, params, conn=conn, locked=True)


def set_email_invalid_many(
    account_ids=None, *, invalid, reason="", expected_emails=None,
    icloud_account_id=None, source="manual", conn=None,
):
    """沿用邮箱事实协调锁和账号→账本→母资源锁序，保留关联范围和作用域。"""
    if type(invalid) is not bool:
        raise ValueError("invalid 必须是布尔值")
    if not isinstance(reason, str) or len(reason.strip()) > 300:
        raise ValueError("邮箱失效原因最多 300 字")
    if icloud_account_id is not None and account_ids is not None:
        raise ValueError("账号 ID 与 iCloud 副号范围不能同时指定")
    group = str(icloud_account_id or "").strip()
    if icloud_account_id is not None and not group:
        raise ValueError("iCloud 副号不能为空")
    if expected_emails is not None and not isinstance(expected_emails, Mapping):
        raise ValueError("expected_emails 必须是账号 ID 到邮箱的映射")
    ids, invalid_items = _targets(account_ids)
    if not group and not ids:
        if invalid_items:
            return tuple(invalid_items)
        raise ValueError("必须指定非空账号 ID 列表或 iCloud 副号")
    expected = {int(key): validity._address(value) for key, value in (expected_emails or {}).items()}
    reason, source, at = reason.strip(), str(source or "manual").strip()[:80] or "manual", _now()
    rs.init()
    with nullcontext(conn) if conn is not None else rs.transaction() as connection:
        validity.lock_email_validity(connection)
        pools, bindings = {}, []
        if group:
            parents = validity._rows(rs.ICLOUD_HIDE_POOL, "account_id=%s", (group,), conn=connection)
            parent_ids = [int(row["id"]) for row in parents]
            pools.update({("icloud_hide", int(row["id"])): (rs.ICLOUD_HIDE_POOL, row) for row in parents})
            bindings = validity._rows(rs.EMAIL_ADDRESS_ALLOCATIONS, "source=%s AND parent_id=ANY(%s)",
                                      ("icloud_hide", parent_ids), conn=connection)
            addresses = sorted({validity._address(row["email"]) for row in parents}
                               | {validity._address(row["address"]) for row in bindings})
            accounts = _account_rows(connection, addresses=addresses)
            ids = [int(row["id"]) for row in accounts]
        else:
            accounts = _account_rows(connection, ids)
        stale = {int(row["id"]): ("account_email_changed", "账号邮箱已变更")
                 for row in accounts if int(row["id"]) in expected
                 and validity._address(row["email"]) != expected[int(row["id"])]}
        accounts = [row for row in accounts if int(row["id"]) not in stale]
        addresses = sorted({validity._address(row["email"]) for row in accounts})
        if not group:
            bindings = validity._rows(rs.EMAIL_ADDRESS_ALLOCATIONS, "address_norm=ANY(%s)", (addresses,), conn=connection)
            for selected_source, spec in validity._POOLS.items():
                for row in validity._rows(spec, "LOWER(BTRIM(email))=ANY(%s)", (addresses,), conn=connection):
                    pools[(selected_source, int(row["id"]))] = (spec, row)
            for selected_source, spec in validity._POOLS.items():
                parent_ids = sorted({int(row["parent_id"]) for row in bindings if row["source"] == selected_source})
                if parent_ids:
                    for row in validity._rows(spec, "id=ANY(%s)", (parent_ids,), conn=connection):
                        pools[(selected_source, int(row["id"]))] = (spec, row)
        binding_ids = sorted(int(row["id"]) for row in bindings)
        if binding_ids:
            bindings = _locked_resources(rs.EMAIL_ADDRESS_ALLOCATIONS, "id=ANY(%s)", (binding_ids,), conn=connection)
        for selected_source, spec in sorted(validity._POOLS.items()):
            parent_ids = sorted(key[1] for key in pools if key[0] == selected_source)
            if parent_ids:
                for row in _locked_resources(spec, "id=ANY(%s)", (parent_ids,), conn=connection):
                    pools[(selected_source, int(row["id"]))] = (spec, row)
        if group:
            bindings = _locked_resources(
                rs.EMAIL_ADDRESS_ALLOCATIONS, "source=%s AND parent_id=ANY(%s)",
                ("icloud_hide", sorted(key[1] for key in pools)), conn=connection,
            )
        scopes_by_address = {validity._address(row["email"]): f"account:{row['id']}" for row in accounts}
        scopes_by_parent = {}
        if not group:
            for binding in bindings:
                key = (str(binding["source"]), int(binding["parent_id"]))
                scopes_by_parent.setdefault(key, set()).add(scopes_by_address[validity._address(binding["address"])])
        group_scope = [f"icloud_account:{group}"] if group else []
        _patch_facts(rs.ACCOUNTS, [
            (int(row["id"]), validity._facts(invalid, row["email"], reason, source, at)) for row in accounts
        ], conn=connection)
        _patch_facts(rs.EMAIL_ADDRESS_ALLOCATIONS, [
            (int(row["id"]), validity._resource_facts(
                row, row["address"], group_scope or [scopes_by_address[validity._address(row["address"])]],
                invalid=invalid, reason=reason, source=source, at=at,
            )) for row in bindings
        ], conn=connection)
        for selected_source, spec in sorted(validity._POOLS.items()):
            values = []
            for (pool_source, pool_id), (_, row) in sorted(pools.items()):
                if pool_source != selected_source:
                    continue
                scopes = set(scopes_by_parent.get((pool_source, pool_id), ()))
                if validity._address(row["email"]) in scopes_by_address:
                    scopes.add(scopes_by_address[validity._address(row["email"])])
                values.append((pool_id, validity._resource_facts(
                    row, row["email"], group_scope or sorted(scopes),
                    invalid=invalid, reason=reason, source=source, at=at,
                )))
            _patch_facts(spec, values, conn=connection)
        counts = {
            "pool_updated_count": len(pools), "allocation_updated_count": len(bindings),
            "matched_account_count": len(accounts) + len(stale),
            "matched_pool_count": len(pools), "matched_allocation_count": len(bindings),
        }
        if group:
            return (BulkItemResult(group, "updated", data={
                **counts, "account_ids": [int(row["id"]) for row in accounts], "updated_count": len(accounts),
            }),)
        items = _receipt(ids, accounts, skipped=stale, invalid=invalid_items)
        return tuple(BulkItemResult(item.key, item.status, item.reason_code, item.reason,
                                    {"id": item.key, **counts} if item.status == "updated" else item.data)
                     for item in items)


def register_handlers():
    """由 Web/Worker 的组装入口显式调用；导入模块本身不安装运行时。"""
    from core.operations import task_gateway

    task_gateway.register_bulk_mutation_handler(
        "account_archive", lambda chunk, params, *, conn=None: archive_many(
            chunk, archived=params.get("archived", True), conn=conn,
        ),
        parameter_allowlist=("archived",),
    )
    task_gateway.register_bulk_mutation_handler(
        "account_delete", lambda chunk, params, *, conn=None: delete_many(chunk, conn=conn),
    )
    task_gateway.register_bulk_mutation_handler(
        "account_note", lambda chunk, params, *, conn=None: update_note_many(chunk, note=params.get("note", ""), conn=conn),
        parameter_allowlist=("note",),
    )
    task_gateway.register_bulk_mutation_handler(
        "account_email_invalid", _email_invalid_handler,
        parameter_allowlist=("invalid", "reason", "expected_emails", "icloud_account_id", "source"),
    )


def _email_invalid_handler(chunk, parameters, *, conn=None):
    params = {key: parameters[key] for key in (
        "invalid", "reason", "expected_emails", "icloud_account_id", "source",
    ) if key in parameters}
    return set_email_invalid_many(None if params.get("icloud_account_id") is not None else chunk, **params, conn=conn)
