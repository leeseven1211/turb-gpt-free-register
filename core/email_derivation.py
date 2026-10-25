# -*- coding: utf-8 -*-
"""邮箱子地址的生成、持久恢复及收件链路解析。"""
from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from config import email as email_config
from core import record_store
from core.storage import email_address_allocations as store

_SUPPORTED_SOURCES = {"icloud_hide", "outlook"}
_POLICY = ContextVar("email_derivation_policy", default=None)
_PROFILE_LOCK = threading.RLock()


def policy_snapshot() -> dict:
    """只冻结非敏感生成选项，旧绑定不依赖此开关恢复。"""
    raw = getattr(email_config, "EMAIL_DERIVATION_SOURCES", "icloud_hide")
    sources = raw.replace(";", ",").split(",") if isinstance(raw, str) else list(raw or [])
    return {
        "enabled": bool(getattr(email_config, "EMAIL_DERIVATION_ENABLED", False)),
        "sources": list(dict.fromkeys(str(value).strip() for value in sources if str(value).strip())),
        "max_children": max(1, int(getattr(email_config, "EMAIL_DERIVATION_MAX_CHILDREN", 3) or 3)),
        "tag_length": max(4, min(24, int(getattr(email_config, "EMAIL_DERIVATION_TAG_LENGTH", 6) or 6))),
    }


@contextmanager
def use_policy(policy: dict | None):
    """同线程的一次领取使用任务入队时的策略。"""
    token = _POLICY.set(dict(policy) if isinstance(policy, dict) else None)
    try:
        yield
    finally:
        _POLICY.reset(token)


def enabled_for(source: str, *, policy: dict | None = None) -> bool:
    selected = policy if isinstance(policy, dict) else (_POLICY.get() or policy_snapshot())
    return bool(selected.get("enabled") and source in selected.get("sources", []))


def find_binding(address: str) -> dict | None:
    raw = str(address or "").strip()
    # 首期账本只生成 plus_tag；历史原地址保持既有读路径与连接开销。
    if not raw or "+" not in raw.rsplit("@", 1)[0]:
        return None
    return store.find_allocation(address=raw)


def _save_profile_secret(reference: str, password: str) -> None:
    """收件账号变化后仍保留旧版本密钥，密钥只进入 .env。"""
    from config.env_loader import env_file_lock, read_env_file, write_env_values

    with _PROFILE_LOCK, env_file_lock():
        persisted = read_env_file()
        if persisted.get(reference) != password:
            write_env_values({reference: password})
        os.environ[reference] = password


def _forward_profile() -> dict:
    if str(getattr(email_config, "ICLOUD_HME_INBOX_MODE", "sidecar")) != "forward_imap":
        raise RuntimeError("当前 iCloud 收件连接器尚未声明子地址隔离能力，请使用已验证的本机 Gmail IMAP 链路")
    server = str(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_SERVER", "imap.gmail.com") or "").strip()
    port = int(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_PORT", 993) or 993)
    username = str(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "") or "").strip()
    password = str(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_PASSWORD", "") or "").replace(" ", "").strip()
    if not server or not username or not password:
        raise RuntimeError("子地址收件链路缺少 Gmail IMAP 配置")
    identity = hashlib.sha256(f"imap:{server.lower()}:{port}:{username.lower()}".encode()).hexdigest()
    version = hashlib.sha256(f"{identity}:{password}".encode()).hexdigest()
    reference = f"EMAIL_DERIVATION_IMAP_SECRET_{version[:20].upper()}"
    _save_profile_secret(reference, password)
    return store.create_inbox_profile(
        inbox_key=f"imap:{identity}", connector="forward_imap", credential_ref=reference,
        inbox_locator={"server": server, "port": port, "email": username, "folder": "INBOX"},
        data={"evidence_rules_version": 1},
    )


def _outlook_profile(parent: dict, conn) -> dict:
    return store.create_inbox_profile(
        inbox_key=f"outlook-pool:{int(parent['id'])}", connector="outlook",
        credential_ref=f"parent:outlook:{int(parent['id'])}",
        inbox_locator={"parent_id": int(parent["id"]), "email": str(parent.get("email") or "")},
        data={"evidence_rules_version": 1}, conn=conn,
    )


def acquire_address(
    source: str, *, owner_kind: str | None, owner_id: Any,
    acquisition_id: str | None, job_id: int | None = None,
    attempt_id: int | None = None, policy: dict | None = None,
) -> str:
    """同一稳定意图重复调用返回原子地址，不改领母地址。"""
    if not owner_kind or owner_id is None or not str(acquisition_id or "").strip():
        raise RuntimeError("派生邮箱领取缺少持久业务意图，不能临时生成后缀")
    previous = store.find_allocation(acquisition_id=str(acquisition_id))
    if previous:
        if (previous["source"], previous["owner_kind"], str(previous["owner_id"])) != (source, owner_kind, str(owner_id)):
            raise RuntimeError("原子地址领取身份与当前业务不一致")
        if previous.get("state") in {"retired", "replaced"}:
            raise RuntimeError("原子地址已明确退役或被换出，请沿对应账号记录恢复")
        store.allocate_address(
            source=source, acquisition_id=str(acquisition_id), owner_kind=owner_kind, owner_id=owner_id,
            job_id=job_id, attempt_id=attempt_id,
        )
        return str(previous["address"])
    selected = dict(policy if isinstance(policy, dict) else (_POLICY.get() or policy_snapshot()))
    if not enabled_for(source, policy=selected):
        raise RuntimeError("当前任务未启用该来源的邮箱派生")
    if source not in _SUPPORTED_SOURCES:
        raise RuntimeError("该邮箱连接器尚未声明子地址的精确取码及持久恢复能力")
    kwargs: dict[str, Any] = {}
    if source == "icloud_hide":
        # 同步只确认真实母资源；不领取原地址，也不创建新的 Apple 别名。
        from core.icloud_hme_client import sync_aliases

        profile = _forward_profile()
        synced = sync_aliases(force=False)
        accounts = [str(value) for value in synced.get("synced_account_ids", []) if str(value)]
        if not accounts and synced.get("account_id"):
            accounts = [str(synced["account_id"])]
        if not accounts:
            raise RuntimeError("没有成功同步的 iCloud 母资源账号，保留原库存等待恢复")
        kwargs.update(inbox_profile_id=int(profile["id"]), account_ids=accounts)
    else:
        kwargs["profile_factory"] = _outlook_profile
    allocation = store.allocate_address(
        source=source, acquisition_id=str(acquisition_id), owner_kind=owner_kind, owner_id=owner_id,
        max_children=int(selected.get("max_children", 3)), tag_length=int(selected.get("tag_length", 6)),
        job_id=job_id, attempt_id=attempt_id, **kwargs,
    )
    if not allocation:
        raise RuntimeError("没有可派生的母邮箱，或每母邮箱派生额度已用完；提高额度后原任务可重跑")
    return str(allocation["address"])


def resolve_route(address: str, *, source: str | None = None) -> dict | None:
    binding = find_binding(address)
    if binding is None:
        return None
    if source and binding["source"] != source:
        raise RuntimeError("子地址的原邮箱来源与当前任务不一致")
    parent = store.get_parent(binding["source"], int(binding["parent_id"]))
    profile = store.get_inbox_profile(int(binding["inbox_profile_id"]))
    if parent is None or profile is None:
        raise RuntimeError("子地址的母资源或原收件配置缺失，不能猜测其他邮箱代收")
    return {"binding": binding, "parent": parent, "profile": profile, "exact_target": binding["address"]}


def restore_address(address: str, *, source: str | None = None) -> dict | None:
    route = resolve_route(address, source=source)
    if route and route["binding"]["state"] == "retired":
        raise RuntimeError("该完整子地址已被明确退役")
    return route


def material_line(address: str) -> str | None:
    route = resolve_route(address)
    if route is None:
        return None
    # 子地址和母收件身份分开保存；凭据本身仍在母资源及原保护位置。
    return str(address)


def release_address(address: str, *, status: str, note: str | None = None, permanent: bool = False) -> bool:
    binding = find_binding(address)
    if binding is None:
        return False
    if status == "used":
        store.mark_allocation_state(int(binding["id"]), "used")
    elif status == "replaced":
        store.mark_allocation_state(int(binding["id"]), "replaced")
    elif permanent or status in {"disabled", "retired"}:
        # 明确的完整地址永久失效只影响该地址，普通回收保留原意图。
        store.mark_allocation_state(int(binding["id"]), "retired", data={"retired_reason": "explicit_permanent_unusable"})
    elif status == "failed":
        store.mark_allocation_state(int(binding["id"]), binding["state"], data={"last_task_outcome": "failed"})
    return True


def _profile_credentials(profile: dict) -> dict:
    from config.env_loader import read_env_file

    reference = str(profile.get("credential_ref") or "")
    password = str(os.environ.get(reference) or read_env_file().get(reference) or "").strip()
    if not password:
        raise RuntimeError("原收件配置的应用密码引用缺失，不能切换当前全局收件账号")
    return {
        **dict(profile.get("inbox_locator") or {}), "connector": profile["connector"], "password": password,
        "id": profile["id"], "inbox_key": profile["inbox_key"], "revision": profile["revision"],
    }


def inbox_profiles_for_addresses(addresses: list[str]) -> dict[str, dict]:
    """一次查出批量地址及其母地址的固定收件配置，不逐地址查整池。"""
    targets = list(dict.fromkeys(str(value or "").strip().lower() for value in addresses if str(value or "").strip()))
    if not targets:
        return {}
    rows = record_store.list_rows(
        record_store.EMAIL_ADDRESS_ALLOCATIONS,
        where="source = %s AND (address_norm = ANY(%s) OR LOWER(parent_address) = ANY(%s))",
        params=("icloud_hide", targets, targets), order_by="id DESC",
    )
    result: dict[str, dict] = {}
    profiles: dict[int, dict] = {}
    for row in rows:
        profile_id = int(row["inbox_profile_id"])
        if profile_id not in profiles:
            profile = store.get_inbox_profile(profile_id)
            if profile is None or profile.get("connector") != "forward_imap":
                raise RuntimeError("历史子地址的固定 IMAP 收件配置缺失")
            profiles[profile_id] = _profile_credentials(profile)
        child, parent = str(row["address_norm"]), str(row["parent_address"]).lower()
        if child in targets:
            result[child] = dict(profiles[profile_id])
        if parent in targets and parent not in result:
            result[parent] = {**profiles[profile_id], "strict_family": True}
    return result


def inbox_profile_for_address(address: str) -> dict | None:
    return inbox_profiles_for_addresses([address]).get(str(address or "").strip().lower())


def fetch_bound_otp(address: str, *, after_ts: float, **kwargs) -> str:
    route = restore_address(address)
    if route is None:
        raise RuntimeError("完整子地址没有持久收件绑定")
    profile = route["profile"]
    if profile["connector"] == "forward_imap":
        from core.forward_imap_client import fetch_latest_otp, use_inbox_profile

        with use_inbox_profile(_profile_credentials(profile)):
            return fetch_latest_otp(address, after_ts=after_ts, **kwargs)
    if profile["connector"] == "outlook":
        from core.outlook_client import OutlookAccount, fetch_otp_with_account

        parent = route["parent"]
        account = OutlookAccount(
            email=str(parent["email"]), password=str(parent.get("password") or ""),
            client_id=str(parent.get("client_id") or "").strip() or str(parent.get("clientId") or "").strip(),
            refresh_token=str(parent.get("refresh_token") or "").strip() or str(parent.get("refreshToken") or "").strip(),
        )
        return fetch_otp_with_account(account, after_ts=after_ts, target_email=address, **kwargs)
    raise RuntimeError("原子地址收件连接器尚未支持精确取码")


def capacity_summary(source: str) -> dict:
    """只读取本地事实估算新意图容量，不同步母资源，也不创建路由或持久密钥。"""
    from psycopg.rows import dict_row
    from core import postgres_store

    selected = str(source or "").strip()
    policy = policy_snapshot()
    result = {"source": selected, "enabled": False, "remaining": 0, "parent_count": 0,
              "remaining_parent_count": 0, "issued": 0, "max_children": policy["max_children"], "reason": ""}
    if not enabled_for(selected, policy=policy):
        result["reason"] = "该来源未启用邮箱派生"
        return result
    if selected not in _SUPPORTED_SOURCES:
        result["reason"] = "该邮箱连接器尚未声明精确子地址能力"
        return result
    if selected == "icloud_hide":
        if str(getattr(email_config, "ICLOUD_HME_INBOX_MODE", "sidecar")) != "forward_imap":
            result["reason"] = "iCloud 子地址需要 forward_imap 精确收件链路"
            return result
        missing = [name for name in ("ICLOUD_HME_API_BASE", "ICLOUD_HME_FORWARD_IMAP_SERVER",
                                     "ICLOUD_HME_FORWARD_IMAP_EMAIL", "ICLOUD_HME_FORWARD_IMAP_PASSWORD")
                   if not str(getattr(email_config, name, "") or "").replace(" ", "").strip()]
        try:
            port_ok = 1 <= int(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_PORT", 993) or 993) <= 65535
        except (ValueError, TypeError):
            port_ok = False
        if missing or not port_ok:
            result["reason"] = "子地址收件链路缺少完整 Gmail IMAP 配置" if not port_ok else "、".join(missing) + " 未配置"
            return result
    table = record_store.ICLOUD_HIDE_POOL if selected == "icloud_hide" else record_store.OUTLOOK_POOL
    parent_table = postgres_store.qualified(table.name)
    ledger_table = postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)
    profiles_table = postgres_store.qualified(record_store.EMAIL_INBOX_PROFILES.name)
    conditions = ["COALESCE(p.status, 'available') IN ('available', 'used', 'replaced', 'reserved')",
                  "COALESCE(p.data->>'remote_active', 'true') <> 'false'",
                  "COALESCE(p.data->>'archived', 'false') <> 'true'",
                  "COALESCE(p.data->>'email_invalid', 'false') <> 'true'",
                  "COALESCE(p.data->>'disabled_reason', '') NOT IN ('remote_inactive', 'remote_missing', 'manual_disabled')",
                  "COALESCE(p.data->'derivation_policy'->>'enabled', 'true') <> 'false'",
                  "position('+' in split_part(p.email, '@', 1)) = 0",
                  "position('@' in p.email) > 1",
                  "octet_length(split_part(p.email, '@', 1)) + 1 + COALESCE((p.data->'derivation_policy'->>'tag_length')::integer, %s) <= 64",
                  "octet_length(p.email) + 1 + COALESCE((p.data->'derivation_policy'->>'tag_length')::integer, %s) <= 254",
                  "(p.data->'derivation_policy'->>'inbox_profile_id' IS NULL OR profile.state = 'active')"]
    values: list[Any] = [selected, policy["max_children"], policy["tag_length"], policy["tag_length"]]
    if selected == "outlook":
        conditions += ["COALESCE(NULLIF(BTRIM(p.data->>'client_id'), ''), NULLIF(BTRIM(p.data->>'clientId'), '')) IS NOT NULL",
                       "COALESCE(NULLIF(BTRIM(p.data->>'refresh_token'), ''), NULLIF(BTRIM(p.data->>'refreshToken'), '')) IS NOT NULL"]
    else:
        conditions.append("NULLIF(BTRIM(p.account_id), '') IS NOT NULL")
        account_id = str(getattr(email_config, "ICLOUD_HME_ACCOUNT_ID", "") or "").strip()
        if account_id:
            conditions.append("p.account_id = %s")
            values.append(account_id)
    # 不调用 record_store.init：容量预览仅执行 SELECT，缺失新表视为尚无可用容量。
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS parents, to_regclass(%s) AS ledger, to_regclass(%s) AS profiles",
                    (parent_table, ledger_table, profiles_table))
        relations = cur.fetchone()
        if not all(relations.values()):
            result["reason"] = "子地址账本尚未初始化"
            return result
        cur.execute(f"""
            WITH issued AS (
                SELECT parent_id, count(*) AS amount FROM {ledger_table}
                WHERE source = %s GROUP BY parent_id
            ), eligible AS (
                SELECT COALESCE(issued.amount, 0) AS issued,
                       GREATEST(0, COALESCE((p.data->'derivation_policy'->>'max_children')::bigint, %s)) AS ceiling
                FROM {parent_table} p LEFT JOIN issued ON issued.parent_id = p.id
                LEFT JOIN {profiles_table} profile ON profile.id = (p.data->'derivation_policy'->>'inbox_profile_id')::bigint
                WHERE {' AND '.join(conditions)}
            )
            SELECT count(*) AS parent_count, count(*) FILTER (WHERE ceiling > issued) AS remaining_parent_count,
                   COALESCE(sum(GREATEST(0, ceiling - issued)), 0) AS remaining,
                   COALESCE(sum(issued), 0) AS issued FROM eligible
        """, values)
        result.update({key: int(value) for key, value in cur.fetchone().items()})
    result["enabled"] = result["remaining"] > 0
    if not result["enabled"]:
        result["reason"] = "没有可派生的母邮箱，或每母邮箱派生额度已用完"
    return result


def public_summary(source: str | None = None) -> dict:
    from core import postgres_store

    selected = str(source or "").strip()
    policy = policy_snapshot()
    groups = store.parent_allocation_counts(source=selected)
    tables = {"icloud_hide": record_store.ICLOUD_HIDE_POOL, "outlook": record_store.OUTLOOK_POOL,
              "generic_api": record_store.GENERIC_API_POOL, "cloudflare_domain": record_store.DOMAIN_POOL}
    parent_rows = {}
    with record_store.transaction() as conn, conn.cursor() as cur:
        for parent_source in dict.fromkeys(row["source"] for row in groups):
            spec = tables.get(parent_source)
            ids = [int(row["parent_id"]) for row in groups if row["source"] == parent_source]
            if spec and ids:
                cur.execute(f"SELECT id, email, data->'derivation_policy' AS policy, COALESCE(data->>'email_invalid', 'false') = 'true' AS email_invalid FROM {postgres_store.qualified(spec.name)} WHERE id = ANY(%s)", (ids,))
                parent_rows.update({(parent_source, int(row["id"])): row for row in cur.fetchall()})
    parents = []
    summary = {"total": 0, "parent_count": len(groups), "reserved": 0, "used": 0, "replaced": 0, "retired": 0}
    for group in groups:
        key = (group["source"], int(group["parent_id"]))
        parent = parent_rows.get(key) or {}
        max_children = int((parent.get("policy") or {}).get("max_children", policy["max_children"]))
        child_count = int(group["issued"])
        parents.append({"source": key[0], "parent_id": key[1], "parent_email": parent.get("email", ""),
                        "child_count": child_count, "max_children": max_children,
                        "remaining": 0 if parent.get("email_invalid") else max(0, max_children - child_count)})
        summary["total"] += child_count
        for state in ("reserved", "used", "replaced", "retired"):
            summary[state] += int(group[state])
    return {**policy, **summary, "parents": parents}


def list_allocations(source: str | None = None, parent_id: int | None = None, page: int = 1, page_size: int = 50) -> dict:
    page, page_size = max(1, int(page)), max(1, min(100, int(page_size)))
    selected = str(source or "").strip()
    rows = store.list_allocations(source=selected, parent_id=parent_id, limit=page_size, offset=(page - 1) * page_size)
    clauses, values = [], []
    if selected:
        clauses.append("source = %s")
        values.append(selected)
    if parent_id is not None:
        clauses.append("parent_id = %s")
        values.append(int(parent_id))
    total = record_store.count_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, where=" AND ".join(clauses), params=values)
    public = [{
        "id": row["id"], "email": row["address"], "parent_id": row["parent_id"],
        "parent_email": row["parent_address"], "source": row["source"], "state": row["state"],
        "registered_account_id": row.get("account_id"),
        "root_task_id": row.get("owner_id") if row.get("owner_kind") == "registration_root" else None,
        "created_at": row.get("created_at"),
    } for row in rows]
    return {"items": public, "total": total, "page": page, "page_size": page_size}


def parent_has_allocations(source: str, parent_id: int, *, conn=None) -> bool:
    return bool(store.list_allocations(source=source, parent_id=int(parent_id), limit=1, conn=conn))


def mark_registered(address: str, account_id: int, *, conn) -> int | None:
    binding = store.find_allocation(address=address, conn=conn)
    if binding is None:
        return None
    store.mark_allocation_state(int(binding["id"]), "used", account_id=int(account_id), conn=conn)
    return int(binding["id"])
