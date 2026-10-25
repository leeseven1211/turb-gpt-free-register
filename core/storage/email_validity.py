"""邮箱失效独立事实及关联账号的原子更新。"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from core import postgres_store, record_store


_POOLS = {
    "icloud_hide": record_store.ICLOUD_HIDE_POOL,
    "outlook": record_store.OUTLOOK_POOL,
    "generic_api": record_store.GENERIC_API_POOL,
    "cloudflare_domain": record_store.DOMAIN_POOL,
}


def _address(value) -> str:
    return str(value or "").strip().lower()


def lock_email_validity(conn, *, shared: bool = False) -> None:
    """在任何账号、账本或母资源行锁之前协调邮箱事实变更。

    注册与确认换绑取得共享锁，彼此仍可并行；批量打标取得排他锁，避免
    扫描旧邮箱时恰好发生新账号写回或换绑。锁内只允许本地数据库操作。
    """
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    with conn.cursor() as cur:
        cur.execute(f"SELECT {function}(hashtextextended(%s, 0))", (f"email-validity:{postgres_store.schema_name()}",))


def _rows(spec, where: str, params, *, conn, locked: bool = False) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT * FROM {postgres_store.qualified(spec.name)} WHERE {where} ORDER BY id"
            + (" FOR UPDATE" if locked else ""), params,
        )
        return [record_store.merge_row(spec, row) for row in cur.fetchall()]


def _facts(invalid: bool, email: str, reason: str, source: str, at: str) -> dict:
    return {
        "email_invalid": invalid,
        "email_invalid_reason": reason if invalid else None,
        "email_invalid_source": source,
        "email_invalid_at": at,
        "email_invalid_email": str(email or "").strip(),
    }


def _resource_facts(row: dict, email: str, scopes: list[str], *, invalid: bool,
                    reason: str, source: str, at: str) -> dict:
    """解除单账号标记不能抹掉同一母资源上更广的副号失效依据。"""
    existing = row.get("email_invalid_scopes")
    remaining = dict(existing) if isinstance(existing, dict) else {}
    if row.get("email_invalid") is True and not remaining:
        remaining["existing"] = {
            "reason": row.get("email_invalid_reason") or "",
            "source": row.get("email_invalid_source") or "manual", "at": row.get("email_invalid_at") or at,
        }
    for scope in scopes:
        if invalid:
            remaining[scope] = {"reason": reason, "source": source, "at": at}
        else:
            remaining.pop(scope, None)
    latest = list(remaining.values())[-1] if remaining else {}
    return {
        **_facts(bool(remaining), email, latest.get("reason", ""), latest.get("source", source), latest.get("at", at)),
        "email_invalid_scopes": remaining,
    }


def facts_for_address(address: str, *, source: str = "", conn) -> dict:
    """调用方先持有共享业务锁，再为新账号或换绑继承目标完整地址事实。

    排他打标此时无法改变失效事实，因此这里无需追加账本或母资源行锁，
    避免与先锁母资源的派生分配形成反向等待。
    """
    normalized = _address(address)
    bindings = _rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, "address_norm=%s", (normalized,), conn=conn)
    resources = list(bindings)
    checked = set()
    for binding in bindings:
        spec = _POOLS.get(str(binding.get("source") or ""))
        if spec is not None:
            checked.add((spec.name, int(binding["parent_id"])))
            parent = record_store.get_row(spec, int(binding["parent_id"]), conn=conn)
            if parent is not None:
                resources.append(parent)
    for candidate_source, spec in _POOLS.items():
        if source and candidate_source != source:
            continue
        parents = _rows(spec, "LOWER(BTRIM(email))=%s", (normalized,), conn=conn)
        resources.extend(parent for parent in parents if (spec.name, int(parent["id"])) not in checked)
    for resource in resources:
        if resource.get("email_invalid") is True:
            return _facts(True, address, str(resource.get("email_invalid_reason") or ""),
                          str(resource.get("email_invalid_source") or "manual"), str(resource.get("email_invalid_at") or ""))
    return _facts(False, address, "", "email_change", datetime.now(timezone.utc).isoformat(timespec="seconds"))


def set_accounts_email_invalid(account_ids=None, *, invalid: bool, reason: str = "",
                               expected_emails: Mapping[int, str] | None = None,
                               icloud_account_id: str | None = None, source: str = "manual") -> dict:
    """按显式账号或真实 HME 副号关联范围更新邮箱事实，不改变使用或认证状态。"""
    if type(invalid) is not bool:
        raise ValueError("invalid 必须是布尔值")
    if not isinstance(reason, str) or len(reason) > 300:
        raise ValueError("邮箱失效原因最多 300 字")
    if icloud_account_id is not None and account_ids is not None:
        raise ValueError("账号 ID 与 iCloud 副号范围不能同时指定")
    group = str(icloud_account_id or "").strip()
    if icloud_account_id is not None and not group:
        raise ValueError("iCloud 副号不能为空")
    if expected_emails is not None and not isinstance(expected_emails, Mapping):
        raise ValueError("expected_emails 必须是账号 ID 到邮箱的映射")
    expected = {int(key): _address(value) for key, value in (expected_emails or {}).items()}
    ids = []
    if not group:
        if not isinstance(account_ids, (list, tuple, set)) or not account_ids:
            raise ValueError("必须指定非空账号 ID 列表或 iCloud 副号")
        for value in account_ids:
            if isinstance(value, bool) or not str(value).strip().isdigit() or int(value) <= 0:
                raise ValueError("账号 ID 必须是正整数")
            ids.append(int(value))
        ids = sorted(set(ids))
    reason, source = reason.strip(), str(source or "manual").strip()[:80] or "manual"
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record_store.init()
    with record_store.transaction() as conn:
        lock_email_validity(conn)
        pools: dict[tuple[str, int], tuple[object, dict]] = {}
        bindings = []
        if group:
            parents = _rows(record_store.ICLOUD_HIDE_POOL, "account_id=%s", (group,), conn=conn)
            parent_ids = [int(row["id"]) for row in parents]
            pools.update({("icloud_hide", int(row["id"])): (record_store.ICLOUD_HIDE_POOL, row) for row in parents})
            bindings = _rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, "source=%s AND parent_id=ANY(%s)",
                             ("icloud_hide", parent_ids), conn=conn)
            addresses = sorted({_address(row["email"]) for row in parents} | {_address(row["address"]) for row in bindings})
            accounts = _rows(record_store.ACCOUNTS, "LOWER(BTRIM(email))=ANY(%s)", (addresses,), conn=conn, locked=True)
        else:
            accounts = _rows(record_store.ACCOUNTS, "id=ANY(%s)", (ids,), conn=conn, locked=True)
        seen = {int(row["id"]) for row in accounts}
        matched_account_count = len(accounts)
        skipped = [{"id": item, "reason": "账号不存在"} for item in ids if item not in seen]
        selected = []
        for row in accounts:
            account_id = int(row["id"])
            if account_id in expected and _address(row["email"]) != expected[account_id]:
                skipped.append({"id": account_id, "reason": "账号邮箱已变更"})
            else:
                selected.append(row)
        accounts = selected
        if not group:
            addresses = sorted({_address(row["email"]) for row in accounts})
            bindings = _rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, "address_norm=ANY(%s)", (addresses,), conn=conn)
            for selected_source, spec in _POOLS.items():
                for row in _rows(spec, "LOWER(BTRIM(email))=ANY(%s)", (addresses,), conn=conn):
                    pools[(selected_source, int(row["id"]))] = (spec, row)
            for binding in bindings:
                selected_source = str(binding["source"])
                spec = _POOLS.get(selected_source)
                if spec is not None:
                    row = record_store.get_row(spec, int(binding["parent_id"]), conn=conn)
                    if row is not None:
                        pools[(selected_source, int(row["id"]))] = (spec, row)
        # 与换绑保持账号→已有账本→母资源的顺序；共享锁已阻止账号身份变动。
        for binding in bindings:
            record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, int(binding["id"]), conn=conn, for_update=True)
        for key in sorted(pools):
            spec, row = pools[key]
            locked = record_store.get_row(spec, int(row["id"]), conn=conn, for_update=True)
            pools[key] = (spec, locked)
        if group:
            # 派生领取先持有母资源锁；锁定母资源后纳入它刚提交的完整子地址。
            bindings = _rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, "source=%s AND parent_id=ANY(%s)",
                             ("icloud_hide", [key[1] for key in pools]), conn=conn, locked=True)
        selected_ids = [int(row["id"]) for row in accounts]
        account_scopes = {int(row["id"]): "account:" + str(row["id"]) for row in accounts}
        group_scope = ["icloud_account:" + group] if group else []
        scopes_by_address = {_address(row["email"]): account_scopes[int(row["id"])] for row in accounts}
        scopes_by_parent: dict[tuple[str, int], set[str]] = {}
        if not group:
            for binding in bindings:
                key = (str(binding["source"]), int(binding["parent_id"]))
                scopes_by_parent.setdefault(key, set()).add(scopes_by_address[_address(binding["address"])])
        for row in accounts:
            record_store.patch_row(record_store.ACCOUNTS, int(row["id"]),
                                   _facts(invalid, row["email"], reason, source, at), conn=conn)
        for binding in bindings:
            scopes = group_scope or [scopes_by_address[_address(binding["address"])]]
            record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, int(binding["id"]),
                                   _resource_facts(binding, binding["address"], scopes, invalid=invalid,
                                                   reason=reason, source=source, at=at), conn=conn)
        for (pool_source, pool_id), (spec, row) in pools.items():
            scopes = set(scopes_by_parent.get((pool_source, pool_id), ()))
            if _address(row["email"]) in scopes_by_address:
                scopes.add(scopes_by_address[_address(row["email"])])
            scopes = group_scope or sorted(scopes)
            record_store.patch_row(spec, pool_id, _resource_facts(
                row, row["email"], scopes, invalid=invalid, reason=reason, source=source, at=at,
            ), conn=conn)
        return {
            "updated_count": len(accounts), "pool_updated_count": len(pools),
            "allocation_updated_count": len(bindings), "matched_account_count": matched_account_count,
            "matched_pool_count": len(pools), "matched_allocation_count": len(bindings),
            "account_ids": selected_ids, "skipped": sorted(skipped, key=lambda item: item["id"]),
        }
