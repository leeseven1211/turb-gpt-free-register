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


def _snapshot(conn, *, lock=False, include_unpinned_parents=False):
    ledger, profiles, parents = _tables()
    suffix = " FOR UPDATE OF a" if lock else ""
    allocations = conn.execute(f"""SELECT a.id, a.inbox_profile_id AS old_profile_id FROM {ledger} a
        JOIN {profiles} p ON p.id=a.inbox_profile_id
        WHERE a.source='icloud_hide' AND p.connector='forward_imap' ORDER BY a.id{suffix}""").fetchall()
    suffix = " FOR UPDATE OF p" if lock else ""
    metadata = """, CASE WHEN NOT (p.data ? 'derivation_policy') THEN 'missing'
            WHEN jsonb_typeof(p.data->'derivation_policy') = 'null' THEN 'null'
            ELSE 'object' END AS old_policy_state,
            COALESCE((p.data->'derivation_policy') ? 'inbox_profile_id', false) AS old_profile_present""" if include_unpinned_parents else ""
    unpinned = """OR (p.data#>>'{derivation_policy,inbox_profile_id}' IS NULL
            AND (NOT (p.data ? 'derivation_policy')
                 OR jsonb_typeof(p.data->'derivation_policy') IN ('null', 'object')))""" if include_unpinned_parents else ""
    parent_rows = conn.execute(f"""SELECT p.id, (p.data#>>'{{derivation_policy,inbox_profile_id}}')::bigint AS old_profile_id{metadata}
        FROM {parents} p LEFT JOIN {profiles} r ON r.id=(p.data#>>'{{derivation_policy,inbox_profile_id}}')::bigint
        WHERE r.connector='forward_imap' {unpinned} ORDER BY p.id{suffix}""").fetchall()
    return [dict(row) for row in allocations], [dict(row) for row in parent_rows]


def _validate_routes(value: dict) -> None:
    """拒绝错误版本或损坏回执，不能在校验失败前触碰路由。"""
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] not in (1, 2):
        raise ValueError("email_cutover_target_invalid: 迁移预览或回执版本无效")
    if value["version"] == 2 and value.get("include_unpinned_parents") is not True:
        raise ValueError("email_cutover_target_invalid: 未固定母资源迁移范围无效")
    for key, count_key in (("allocations", "allocation_count"), ("parents", "parent_count")):
        rows = value.get(key)
        if not isinstance(rows, list) or value.get(count_key) != len(rows):
            raise ValueError("email_cutover_target_invalid: 迁移预览或回执数量不一致")
        seen = set()
        for row in rows:
            if (not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 1 or row["id"] in seen):
                raise ValueError("email_cutover_target_invalid: 迁移预览或回执路由无效")
            old_id = row.get("old_profile_id")
            if key == "parents" and value["version"] == 2:
                state, present = row.get("old_policy_state"), row.get("old_profile_present")
                if ("old_profile_id" not in row or state not in ("missing", "null", "object") or type(present) is not bool
                        or (state != "object" and (present or old_id is not None))
                        or (old_id is not None and (type(old_id) is not int or old_id < 1 or not present))):
                    raise ValueError("email_cutover_target_invalid: 母资源原路由状态无效")
            elif type(old_id) is not int or old_id < 1:
                raise ValueError("email_cutover_target_invalid: 迁移预览或回执路由无效")
            seen.add(row["id"])


def _validate_target(api_base: str, mailbox_email: str, credential_ref: str) -> dict:
    from core.email_derivation import _butler_locator_valid

    locator = {"api_base": str(api_base).strip().rstrip("/"), "mailbox_email": str(mailbox_email).strip().lower()}
    if not _butler_locator_valid(locator) or not str(credential_ref).startswith("EMAIL_DERIVATION_BUTLER_SECRET_"):
        raise ValueError("email_cutover_target_invalid: Butler 地址、最终邮箱或版本化密钥引用无效")
    return locator


def plan_cutover(*, api_base: str, mailbox_email: str, credential_ref: str,
                 include_unpinned_parents: bool = False, conn=None) -> dict:
    """只 SELECT 预览原路由，调用方可在只读事务中执行，不初始化表或写密钥。"""
    locator = _validate_target(api_base, mailbox_email, credential_ref)
    if type(include_unpinned_parents) is not bool:
        raise ValueError("email_cutover_target_invalid: 未固定母资源开关必须为布尔值")
    with _connection(conn) as current:
        allocations, parents = _snapshot(current, include_unpinned_parents=include_unpinned_parents)
    return {"version": 2 if include_unpinned_parents else 1,
        **({"include_unpinned_parents": True} if include_unpinned_parents else {}),
        "locator": locator, "credential_ref": str(credential_ref),
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
    version = {"version": plan["version"], **({"include_unpinned_parents": True} if plan["version"] == 2 else {})}
    with _connection(conn) as current:
        current.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("hme-butler-route-cutover",))
        allocations, parents = _snapshot(current, lock=True, include_unpinned_parents=plan["version"] == 2)
        if allocations != plan["allocations"] or parents != plan["parents"]:
            raise RuntimeError("email_cutover_route_changed: 预览后的路由发生变化，请重新预览")
        if not allocations and not parents:
            return {**version, "new_profile_id": None, "allocations": [], "parents": [], "allocation_count": 0, "parent_count": 0}
        identity = hashlib.sha256(f"butler:{locator['api_base']}:{locator['mailbox_email']}".encode()).hexdigest()
        profile = store.create_inbox_profile(inbox_key=f"butler:{identity}", connector="forward_butler",
            credential_ref=plan["credential_ref"], inbox_locator=locator,
            data={"evidence_rules_version": 1, "require_recipient_evidence": True}, conn=current)
        new_id = int(profile["id"])
        for row in allocations:
            current.execute(f"UPDATE {ledger} SET inbox_profile_id=%s WHERE id=%s AND inbox_profile_id=%s",
                (new_id, row["id"], row["old_profile_id"]))
        for row in parents:
            current.execute(f"""UPDATE {parents_table} SET data=jsonb_set(data,'{{derivation_policy}}',
                COALESCE(NULLIF(data->'derivation_policy', 'null'::jsonb), '{{}}'::jsonb) || %s) WHERE id=%s""",
                (Jsonb({"inbox_profile_id": new_id}), row["id"]))
        return {**version, "new_profile_id": new_id, "allocations": allocations, "parents": parents,
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
            found = current.execute(f"""SELECT data ? 'derivation_policy' AS policy_present,
                data->'derivation_policy' AS policy FROM {parents_table} WHERE id=%s FOR UPDATE""", (row["id"],)).fetchone()
            if not found:
                raise RuntimeError("email_cutover_route_changed: 回滚母资源的路由已被其他操作修改")
            policy = found["policy"]
            state = "missing" if not found["policy_present"] else "null" if policy is None else "object"
            present = isinstance(policy, dict) and "inbox_profile_id" in policy
            profile_id = policy.get("inbox_profile_id") if isinstance(policy, dict) else None
            if receipt["version"] == 2:
                already_restored = (state == row["old_policy_state"] and present == row["old_profile_present"]
                    and str(profile_id) == str(row["old_profile_id"]))
            else:
                already_restored = str(profile_id) == str(row["old_profile_id"])
            if already_restored:
                continue
            if str(profile_id) != str(new_id):
                raise RuntimeError("email_cutover_route_changed: 回滚母资源的路由已被其他操作修改")
            old_state = row.get("old_policy_state", "object")
            if old_state != "object":
                if set(policy) != {"inbox_profile_id"}:
                    raise RuntimeError("email_cutover_route_changed: 回滚不能删除迁移后新增的母资源配置")
                if old_state == "missing":
                    current.execute(f"UPDATE {parents_table} SET data=data-'derivation_policy' WHERE id=%s", (row["id"],))
                else:
                    current.execute(f"UPDATE {parents_table} SET data=jsonb_set(data,'{{derivation_policy}}','null'::jsonb) WHERE id=%s", (row["id"],))
            elif row.get("old_profile_present", True):
                current.execute(f"UPDATE {parents_table} SET data=jsonb_set(data,'{{derivation_policy,inbox_profile_id}}',%s) WHERE id=%s", (Jsonb(row["old_profile_id"]), row["id"]))
            else:
                current.execute(f"UPDATE {parents_table} SET data=data#-'{{derivation_policy,inbox_profile_id}}' WHERE id=%s", (row["id"],))
            restored["restored_parents"] += 1
    return restored
