# -*- coding: utf-8 -*-
"""受控迁移 HME 固定收件路由；只修改 profile 引用，不修改业务状态。"""
from __future__ import annotations

from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from core import postgres_store, record_store
from core.storage import email_address_allocations as store


@contextmanager
def _connection(conn=None):
    if conn is not None:
        yield conn
    else:
        with postgres_store.connect(row_factory=dict_row) as own:
            yield own


def _tables():
    return tuple(postgres_store.qualified(table.name) for table in (
        record_store.EMAIL_ADDRESS_ALLOCATIONS, record_store.EMAIL_INBOX_PROFILES, record_store.ICLOUD_HIDE_POOL))


def _snapshot(conn, *, lock=False):
    ledger, profiles, parents = _tables()
    suffix = " FOR UPDATE OF a" if lock else ""
    allocations = conn.execute(f"""SELECT a.id, a.inbox_profile_id AS old_profile_id FROM {ledger} a
        JOIN {profiles} p ON p.id=a.inbox_profile_id
        WHERE a.source='icloud_hide' AND p.connector='forward_imap' ORDER BY a.id{suffix}""").fetchall()
    suffix = " FOR UPDATE OF p" if lock else ""
    parent_rows = conn.execute(f"""SELECT p.id, (p.data#>>'{{derivation_policy,inbox_profile_id}}')::bigint AS old_profile_id
        FROM {parents} p JOIN {profiles} r ON r.id=(p.data#>>'{{derivation_policy,inbox_profile_id}}')::bigint
        WHERE r.connector='forward_imap' ORDER BY p.id{suffix}""").fetchall()
    return [dict(row) for row in allocations], [dict(row) for row in parent_rows]


def _validate_routes(value: dict) -> None:
    """拒绝错误版本或损坏回执，不能在校验失败前触碰路由。"""
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("email_cutover_target_invalid: 迁移预览或回执版本无效")
    for key, count_key in (("allocations", "allocation_count"), ("parents", "parent_count")):
        rows = value.get(key)
        if not isinstance(rows, list) or value.get(count_key) != len(rows):
            raise ValueError("email_cutover_target_invalid: 迁移预览或回执数量不一致")
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or any(type(row.get(field)) is not int or row[field] < 1
                    for field in ("id", "old_profile_id")) or row["id"] in seen):
                raise ValueError("email_cutover_target_invalid: 迁移预览或回执路由无效")
            seen.add(row["id"])


def _validate_target(api_base: str, mailbox_email: str, credential_ref: str) -> dict:
    from core.email_derivation import _butler_locator_valid

    locator = {"api_base": str(api_base).strip().rstrip("/"), "mailbox_email": str(mailbox_email).strip().lower()}
    if not _butler_locator_valid(locator) or not str(credential_ref).startswith("EMAIL_DERIVATION_BUTLER_SECRET_"):
        raise ValueError("email_cutover_target_invalid: Butler 地址、最终邮箱或版本化密钥引用无效")
    return locator


def plan_cutover(*, api_base: str, mailbox_email: str, credential_ref: str, conn=None) -> dict:
    """只 SELECT 预览原路由，调用方可在只读事务中执行，不初始化表或写密钥。"""
    locator = _validate_target(api_base, mailbox_email, credential_ref)
    with _connection(conn) as current:
        allocations, parents = _snapshot(current)
    return {"version": 1, "locator": locator, "credential_ref": str(credential_ref),
        "allocations": allocations, "parents": parents, "allocation_count": len(allocations), "parent_count": len(parents)}


def apply_cutover(plan: dict, *, conn=None) -> dict:
    """锁定并核对快照；外部 conn 必须在创建事务及任何读取前完成 record_store.init。"""
    import hashlib

    _validate_routes(plan)
    locator = plan.get("locator") or {}
    locator = _validate_target(locator.get("api_base", ""), locator.get("mailbox_email", ""), plan.get("credential_ref", ""))
    if conn is None:
        # 自有事务同样先初始化，不能持有读锁/行锁后由另一连接尝试 DDL。
        record_store.init()
    ledger, _profiles, parents_table = _tables()
    with _connection(conn) as current:
        current.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("hme-butler-route-cutover",))
        allocations, parents = _snapshot(current, lock=True)
        if allocations != plan["allocations"] or parents != plan["parents"]:
            raise RuntimeError("email_cutover_route_changed: 预览后的路由发生变化，请重新预览")
        if not allocations and not parents:
            return {"version": 1, "new_profile_id": None, "allocations": [], "parents": [], "allocation_count": 0, "parent_count": 0}
        identity = hashlib.sha256(f"butler:{locator['api_base']}:{locator['mailbox_email']}".encode()).hexdigest()
        profile = store.create_inbox_profile(inbox_key=f"butler:{identity}", connector="forward_butler",
            credential_ref=plan["credential_ref"], inbox_locator=locator,
            data={"evidence_rules_version": 1, "require_recipient_evidence": True}, conn=current)
        new_id = int(profile["id"])
        for row in allocations:
            current.execute(f"UPDATE {ledger} SET inbox_profile_id=%s WHERE id=%s AND inbox_profile_id=%s",
                (new_id, row["id"], row["old_profile_id"]))
        for row in parents:
            current.execute(f"UPDATE {parents_table} SET data=jsonb_set(data,'{{derivation_policy,inbox_profile_id}}',%s) WHERE id=%s",
                (Jsonb(new_id), row["id"]))
        return {"version": 1, "new_profile_id": new_id, "allocations": allocations, "parents": parents,
            "allocation_count": len(allocations), "parent_count": len(parents)}


def rollback_cutover(receipt: dict, *, conn=None) -> dict:
    """按迁移回执恢复原路由；已回滚可重复执行，路由被他人改动则拒绝覆盖。"""
    _validate_routes(receipt)
    new_id = receipt.get("new_profile_id")
    if new_id is not None and (type(new_id) is not int or new_id < 1):
        raise ValueError("email_cutover_target_invalid: 回执目标 profile 无效")
    if new_id is None and (receipt["allocations"] or receipt["parents"]):
        raise ValueError("email_cutover_target_invalid: 回执缺少目标 profile")
    if not new_id:
        return {"restored_allocations": 0, "restored_parents": 0}
    ledger, _profiles, parents_table = _tables()
    restored = {"restored_allocations": 0, "restored_parents": 0}
    with _connection(conn) as current:
        current.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("hme-butler-route-cutover",))
        for row in receipt["allocations"]:
            found = current.execute(f"SELECT inbox_profile_id FROM {ledger} WHERE id=%s AND source='icloud_hide' FOR UPDATE", (row["id"],)).fetchone()
            if not found or found["inbox_profile_id"] not in {new_id, row["old_profile_id"]}:
                raise RuntimeError("email_cutover_route_changed: 回滚目标的路由已被其他操作修改")
            if found["inbox_profile_id"] == new_id:
                current.execute(f"UPDATE {ledger} SET inbox_profile_id=%s WHERE id=%s", (row["old_profile_id"], row["id"]))
                restored["restored_allocations"] += 1
        for row in receipt["parents"]:
            found = current.execute(f"SELECT data#>>'{{derivation_policy,inbox_profile_id}}' AS profile_id FROM {parents_table} WHERE id=%s FOR UPDATE", (row["id"],)).fetchone()
            if not found or str(found["profile_id"]) not in {str(new_id), str(row["old_profile_id"])}:
                raise RuntimeError("email_cutover_route_changed: 回滚母资源的路由已被其他操作修改")
            if str(found["profile_id"]) == str(new_id):
                current.execute(f"UPDATE {parents_table} SET data=jsonb_set(data,'{{derivation_policy,inbox_profile_id}}',%s) WHERE id=%s", (Jsonb(row["old_profile_id"]), row["id"]))
                restored["restored_parents"] += 1
    return restored
