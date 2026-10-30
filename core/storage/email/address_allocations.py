# -*- coding: utf-8 -*-
"""完整邮箱地址、固定收件配置和认证租约的 PostgreSQL 事实仓储。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import secrets
import string
from typing import Any, Callable

from core.storage import postgres as postgres_store, records as record_store

DEFAULT_MAX_CHILDREN = 3
DEFAULT_TAG_LENGTH = 6
_PARENT_TABLES = {
    "icloud_hide": record_store.ICLOUD_HIDE_POOL,
    "outlook": record_store.OUTLOOK_POOL,
    "cloudflare_domain": record_store.DOMAIN_POOL,
    "generic_api": record_store.GENERIC_API_POOL,
}
_STATES = {"available", "disabled", "reserved", "used", "replaced", "retired"}
_SECRET_KEYS = {"password", "secret", "token", "cookie", "code", "otp", "body", "raw_message", "access_token", "refresh_token"}


class OtpLeaseBusy(RuntimeError):
    """同一完整地址已有其他认证执行持有租约。"""


class StaleOtpFence(RuntimeError):
    """认证执行已过期或被新的执行替代。"""


class EmailDerivationError(RuntimeError):
    """子地址业务错误保留稳定分类，包装成普通异常后仍可识别。"""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _expires(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(1, int(seconds)))).isoformat(timespec="microseconds")


def normalize_address(address: str) -> str:
    """仅规范大小写和空白，保留点号及完整标签。"""
    return str(address or "").strip().lower()


@contextmanager
def _connection(conn=None):
    if conn is not None:
        yield conn
    else:
        with record_store.transaction() as own:
            yield own


def _metadata(value: dict | None) -> dict:
    """新账本不接受验证码、原文或凭据副本。"""
    def inspect(item):
        if isinstance(item, dict):
            for key, child in item.items():
                lowered = str(key).lower()
                if lowered in _SECRET_KEYS or any(lowered.endswith("_" + part) for part in ("password", "secret", "token", "cookie", "otp")):
                    raise ValueError("邮箱地址账本不能保存密钥、验证码或邮件原文")
                inspect(child)
        elif isinstance(item, (tuple, list)):
            for child in item:
                inspect(child)
    result = dict(value or {})
    inspect(result)
    return result


def _parent_table(source: str):
    try:
        return _PARENT_TABLES[str(source)]
    except KeyError:
        raise ValueError(f"邮箱来源不支持持久母资源：{source}") from None


def get_parent(source: str, parent_id: int, *, conn=None) -> dict | None:
    return record_store.get_row(_parent_table(source), int(parent_id), conn=conn)


def configure_parent(source: str, parent_id: int, *, enabled: bool = True,
                     max_children: int = DEFAULT_MAX_CHILDREN, inbox_profile_id: int | None = None,
                     conn=None) -> dict:
    if int(max_children) < 0:
        raise ValueError("母资源派生上限不能为负数")
    table = _parent_table(source)
    with _connection(conn) as current:
        row = record_store.get_row(table, parent_id, conn=current, for_update=True)
        if not row:
            raise ValueError("母邮箱资源不存在")
        policy = dict(row.get("derivation_policy") or {})
        policy.update(enabled=bool(enabled), max_children=int(max_children))
        if inbox_profile_id is not None:
            if not get_inbox_profile(inbox_profile_id, conn=current):
                raise ValueError("收件配置版本不存在")
            policy["inbox_profile_id"] = int(inbox_profile_id)
        record_store.patch_row(table, parent_id, {"derivation_policy": policy}, conn=current)
        return record_store.get_row(table, parent_id, conn=current)


def get_allocation(allocation_id: int, *, conn=None) -> dict | None:
    return record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, allocation_id, conn=conn)


def find_allocation(*, address: str = "", acquisition_id: str = "", conn=None) -> dict | None:
    if acquisition_id:
        return record_store.get_row_by(record_store.EMAIL_ADDRESS_ALLOCATIONS, "acquisition_id", acquisition_id, conn=conn)
    if address:
        return record_store.get_row_by(record_store.EMAIL_ADDRESS_ALLOCATIONS, "address_norm", normalize_address(address), conn=conn)
    raise ValueError("需要完整地址或领取身份")


def list_allocations(*, source: str = "", parent_id: int | None = None, owner_kind: str = "",
                     owner_id: Any = "", state: str = "", limit: int = 100, offset: int = 0,
                     q: str = "", parent_q: str = "", related_q: str = "", created_from: str = "", created_to: str = "", conn=None) -> list[dict]:
    predicates, values = allocation_filters(source=source, parent_id=parent_id, owner_kind=owner_kind,
        owner_id=owner_id, state=state, q=q, parent_q=parent_q, related_q=related_q,
        created_from=created_from, created_to=created_to)
    return record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, where=" AND ".join(predicates), params=values,
                                  order_by="id ASC", limit=max(1, int(limit)), offset=max(0, int(offset)), conn=conn)


def allocation_filters(*, source="", parent_id=None, owner_kind="", owner_id="", state="",
                       q="", parent_q="", related_q="", created_from="", created_to="") -> tuple[list[str], list]:
    """列表与总数共用同一组筛选，所有用户文本仅作为绑定参数。"""
    predicates, values = [], []
    for name, value in (("source", source), ("parent_id", parent_id), ("owner_kind", owner_kind), ("owner_id", owner_id), ("state", state)):
        if value is not None and value != "":
            predicates.append(f'"{name}" = %s')
            values.append(str(value) if name == "owner_id" else value)
    for column, value in (("address", q), ("parent_address", parent_q)):
        if str(value or "").strip():
            predicates.append(f"{column} ILIKE %s")
            values.append("%" + str(value).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if str(related_q or "").strip():
        predicates.append("(owner_id ILIKE %s OR account_id::text ILIKE %s)")
        term = "%" + str(related_q).strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        values.extend((term, term))
    if created_from:
        predicates.append("created_at::timestamptz >= %s::timestamptz")
        values.append(created_from)
    if created_to:
        predicates.append("created_at::timestamptz < (%s::date + INTERVAL '1 day')")
        values.append(created_to)
    return predicates, values


def allocation_summary(*, source: str = "", conn=None) -> dict:
    with _connection(conn) as current, current.cursor() as cur:
        where = " WHERE source = %s" if source else ""
        cur.execute(f"SELECT state, count(*) AS n FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)}{where} GROUP BY state", (source,) if source else ())
        counts = {row["state"]: int(row["n"]) for row in cur.fetchall()}
        parents = parent_allocation_counts(source=source, conn=current)
        return {"total": sum(counts.values()), "parent_count": len(parents),
                **{state: counts.get(state, 0) for state in sorted(_STATES)}}


def parent_allocation_counts(*, source: str = "", parent_ids: list[int] | None = None, conn=None) -> list[dict]:
    """管理列表一次聚合母资源历史额度，避免逐母资源查询账本。"""
    clauses, values = [], []
    if source:
        clauses.append("source = %s")
        values.append(source)
    if parent_ids is not None:
        clauses.append("parent_id = ANY(%s)")
        values.append([int(item) for item in parent_ids])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with _connection(conn) as current, current.cursor() as cur:
        cur.execute(f"""SELECT source, parent_id, count(*) AS issued,
                        count(*) FILTER (WHERE state = 'available') AS available,
                        count(*) FILTER (WHERE state = 'disabled') AS disabled,
                        count(*) FILTER (WHERE state = 'reserved') AS reserved,
                        count(*) FILTER (WHERE state = 'used') AS used,
                        count(*) FILTER (WHERE state = 'replaced') AS replaced,
                        count(*) FILTER (WHERE state = 'retired') AS retired
                        FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)}{where}
                        GROUP BY source, parent_id ORDER BY source, parent_id""", values)
        return [dict(row) for row in cur.fetchall()]


def mark_allocation_state(allocation_id: int, state: str, *, account_id: int | None = None,
                          data: dict | None = None, conn=None) -> dict | None:
    if state not in _STATES:
        raise ValueError("未知的子地址状态")
    with _connection(conn) as current:
        row = record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, allocation_id, conn=current, for_update=True)
        if not row:
            return None
        if state in {"available", "disabled"} and (row["state"] not in {"available", "disabled"} or any(
            row.get(key) is not None for key in ("acquisition_id", "owner_kind", "owner_id", "account_id")
        )):
            raise ValueError("已领取或已绑定的子地址不能重新投入库存")
        if row["state"] in {"replaced", "retired"} and state != row["state"]:
            raise ValueError("已替换或退役的子地址不能重新分配")
        metadata = _metadata(data)
        if set(metadata) & set(record_store.EMAIL_ADDRESS_ALLOCATIONS.promoted):
            raise ValueError("子地址身份字段不能通过扩展事实修改")
        changes = {**metadata, "state": state}
        if account_id is not None:
            changes["account_id"] = int(account_id)
        record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, allocation_id, changes, conn=current)
        return get_allocation(allocation_id, conn=current)


def create_inbox_profile(*, inbox_key: str, connector: str, credential_ref: str,
                         inbox_locator: dict, data: dict | None = None, conn=None) -> dict:
    if not all(str(value or "").strip() for value in (inbox_key, connector, credential_ref)):
        raise ValueError("收件配置需要稳定身份、连接器和密钥引用")
    metadata = _metadata(data)
    locator = _metadata(inbox_locator)
    with _connection(conn) as current:
        record_store.advisory_xact_lock(current, f"email-inbox-profile:{inbox_key}")
        versions = record_store.list_rows(record_store.EMAIL_INBOX_PROFILES, where="inbox_key = %s", params=(inbox_key,),
                                          order_by="revision DESC", limit=1, conn=current)
        previous = versions[0] if versions else None
        if previous and previous["state"] == "active" and all(previous.get(key) == value for key, value in {
            "connector": connector, "credential_ref": credential_ref, "inbox_locator": locator, **metadata,
        }.items()):
            return previous
        profile_id = record_store.insert_row(record_store.EMAIL_INBOX_PROFILES, {
            **metadata, "inbox_key": inbox_key, "revision": int(previous["revision"]) + 1 if previous else 1,
            "connector": connector, "credential_ref": credential_ref, "inbox_locator": locator,
            "evidence_rules_version": metadata.get("evidence_rules_version", 1), "state": "active",
        }, conn=current)
        return get_inbox_profile(profile_id, conn=current)


def get_inbox_profile(profile_id: int, *, conn=None) -> dict | None:
    return record_store.get_row(record_store.EMAIL_INBOX_PROFILES, profile_id, conn=conn)


def list_inbox_profiles(*, inbox_key: str = "", state: str = "", conn=None) -> list[dict]:
    clauses, values = [], []
    for name, value in (("inbox_key", inbox_key), ("state", state)):
        if value:
            clauses.append(f"{name} = %s")
            values.append(value)
    return record_store.list_rows(record_store.EMAIL_INBOX_PROFILES, where=" AND ".join(clauses), params=values,
                                  order_by="id DESC", conn=conn)


def retire_inbox_profile(profile_id: int, *, conn=None) -> dict | None:
    record_store.patch_row(record_store.EMAIL_INBOX_PROFILES, profile_id, {"state": "retired"}, conn=conn)
    return get_inbox_profile(profile_id, conn=conn)


def address_is_taken(address: str, *, conn=None) -> bool:
    """包含归档账号和所有池记录，完整地址一经使用便不跨意图复用。"""
    normalized = normalize_address(address)
    with _connection(conn) as current:
        if find_allocation(address=normalized, conn=current):
            return True
        for table in (record_store.ACCOUNTS, *_PARENT_TABLES.values()):
            if record_store.get_row_by(table, "email", normalized, lower=True, conn=current):
                return True
        return False


def _new_address(parent_address: str, tag_length: int) -> tuple[str, str]:
    local, separator, domain = parent_address.rpartition("@")
    if not separator or not local or not domain or "+" in local:
        raise ValueError("母资源必须是未带标签的完整邮箱地址")
    tag = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(tag_length))
    address = f"{local}+{tag}@{domain}"
    if len((local + "+" + tag).encode("utf-8")) > 64 or len(address.encode("utf-8")) > 254:
        raise ValueError("派生地址超过邮箱长度限制")
    return address, tag


def _bind_business(allocation: dict, *, job_id=None, attempt_id=None, root_task_id=None, conn):
    """外部传入连接时，地址与原 job、Attempt 的绑定同提交同回滚。"""
    changes = {"email": allocation["address"], "email_source": allocation["source"],
               "email_address_id": allocation["id"], "email_lease_id": f"allocation:{allocation['id']}"}
    job = record_store.get_row(record_store.JOBS, int(job_id), conn=conn, for_update=True) if job_id else None
    if job_id:
        if not job:
            raise ValueError("注册任务不存在")
        record_store.patch_row(record_store.JOBS, int(job_id), changes, conn=conn)
        attempt_id = attempt_id or job.get("attempt_id")
    with conn.cursor() as cur:
        attempts = postgres_store.qualified("registration_attempts")
        cur.execute("SELECT to_regclass(%s) AS relation", (attempts,))
        if cur.fetchone()["relation"]:
            where = "id = %s" if attempt_id else "root_job_id = %s"
            lookup = attempt_id or (job.get("root_job_id") or job_id if job else None)
            if lookup:
                cur.execute(f"UPDATE {attempts} SET email = %s, email_snapshot = %s, email_source = %s, data = data || %s::jsonb, updated_at = now() WHERE {where}",
                            (allocation["address"], allocation["address"], allocation["source"], json.dumps(changes), int(lookup)))
                if attempt_id and cur.rowcount != 1:
                    raise ValueError("注册 Attempt 不存在")
        if root_task_id:
            tasks = postgres_store.qualified("operation_tasks")
            cur.execute("SELECT to_regclass(%s) AS relation", (tasks,))
            if cur.fetchone()["relation"]:
                cur.execute(f"UPDATE {tasks} SET data = data || %s::jsonb, updated_at = now() WHERE id = %s", (json.dumps(changes), int(root_task_id)))
    batch_id = str(job.get("batch_id") or "").strip() if job else ""
    if batch_id:
        claim_key = f"{batch_id}\x1f{allocation['address_norm']}"
        record_store.upsert_row_by(record_store.REGISTRATION_BATCH_EMAIL_CLAIMS, "claim_key", {
            "claim_key": claim_key, "batch_id": batch_id, "email": allocation["address"], "job_id": int(job_id),
            "email_source": allocation["source"], "claimed_at": _now(),
        }, conn=conn)


def allocate_address(*, source: str, acquisition_id: str, owner_kind: str, owner_id: Any,
                     parent_id: int | None = None, parent_ids: list[int] | None = None,
                     account_ids: list[str] | None = None, inbox_profile_id: int | None = None,
                     max_children: int = DEFAULT_MAX_CHILDREN, tag_length: int = DEFAULT_TAG_LENGTH,
                     job_id: int | None = None, attempt_id: int | None = None,
                     root_task_id: int | None = None,
                     profile_factory: Callable[[dict, Any], dict] | None = None,
                     generation_key: str | None = None, generation_request: dict | None = None,
                     failure: dict | None = None, profile_validator: Callable[[dict], bool] | None = None,
                     conn=None) -> dict | None:
    """兼容底层直接分配；人工生成传入 generation_key，只创建无归属库存。"""
    if not generation_key and (not acquisition_id or not owner_kind or str(owner_id or "") == ""):
        raise ValueError("派生领取必须提供稳定领取身份和业务归属")
    if not 1 <= int(tag_length) <= 32 or int(max_children) < 0:
        raise ValueError("派生后缀长度或额度无效")
    table = _parent_table(source)
    with _connection(conn) as current:
        identity = f"generation:{generation_key}" if generation_key else f"acquisition:{acquisition_id}"
        record_store.advisory_xact_lock(current, f"email-address-{identity}")
        existing = (record_store.get_row_by(record_store.EMAIL_ADDRESS_ALLOCATIONS, "generation_key", generation_key, conn=current)
                    if generation_key else find_allocation(acquisition_id=acquisition_id, conn=current))
        if existing:
            if generation_key:
                return existing
            if (existing["source"], existing["owner_kind"], existing["owner_id"]) != (source, owner_kind, str(owner_id)):
                raise ValueError("领取身份已归属于其他业务")
            _bind_business(existing, job_id=job_id, attempt_id=attempt_id, root_task_id=root_task_id, conn=current)
            return existing
        # SQL 先剔除配额已满的母资源，每次只锁一行；取得父锁后再次检查实际累计额度。
        conditions = ["COALESCE(status, 'available') IN ('available', 'used', 'replaced', 'reserved')",
                      "COALESCE(data->>'remote_active', 'true') <> 'false'",
                      "COALESCE(data->>'archived', 'false') <> 'true'",
                      "COALESCE(data->>'email_invalid', 'false') <> 'true'",
                      "COALESCE(data->>'disabled_reason', '') NOT IN ('remote_inactive', 'remote_missing', 'manual_disabled')",
                      "COALESCE(data->'derivation_policy'->>'enabled', 'true') <> 'false'",
                      "position('+' in split_part(p.email, '@', 1)) = 0"]
        args: list[Any] = []
        if source == "icloud_hide":
            conditions.append("NULLIF(BTRIM(p.account_id), '') IS NOT NULL")
        elif source == "outlook":
            conditions += ["COALESCE(NULLIF(BTRIM(p.data->>'client_id'), ''), NULLIF(BTRIM(p.data->>'clientId'), '')) IS NOT NULL",
                           "COALESCE(NULLIF(BTRIM(p.data->>'refresh_token'), ''), NULLIF(BTRIM(p.data->>'refreshToken'), '')) IS NOT NULL"]
        if parent_id is not None:
            conditions.append("p.id = %s")
            args.append(int(parent_id))
        if parent_ids is not None:
            conditions.append("p.id = ANY(%s)")
            args.append([int(item) for item in parent_ids])
        if account_ids is not None:
            if source != "icloud_hide":
                raise ValueError("仅 HME 母资源支持上游账号范围")
            conditions.append("p.account_id = ANY(%s)")
            args.append([str(item) for item in account_ids])
        if failure is not None:
            # 在取额前区分“没有健康母资源”和“母资源仍健康但历史额度耗尽”。
            with current.cursor() as cur:
                cur.execute(f"SELECT count(*) AS n FROM {postgres_store.qualified(table.name)} p WHERE {' AND '.join(conditions)}", args)
                healthy = int(cur.fetchone()["n"])
            failure.update({"reason_code": "email_derivation_capacity_exhausted" if healthy else "email_derivation_parent_unavailable",
                "reason": "合格母资源的累计生成额度已用完，请提高额度后发起新的生成请求" if healthy else "没有符合当前范围且健康可用的母邮箱，请检查母资源状态和来源范围"})
        last_id = 0
        while True:
            with current.cursor() as cur:
                cur.execute(f"""
                    SELECT p.id FROM {postgres_store.qualified(table.name)} p
                    LEFT JOIN (
                        SELECT parent_id, count(*) AS issued
                        FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)}
                        WHERE source = %s GROUP BY parent_id
                    ) issued ON issued.parent_id = p.id
                    WHERE {' AND '.join(conditions)} AND p.id > %s
                      AND COALESCE(issued.issued, 0) < COALESCE((p.data->'derivation_policy'->>'max_children')::bigint, %s)
                    ORDER BY p.id LIMIT 1 FOR UPDATE OF p
                """, [source, *args, last_id, int(max_children)])
                selected = cur.fetchone()
            if not selected:
                break
            candidate_id = last_id = int(selected["id"])
            parent = record_store.get_row(table, candidate_id, conn=current)
            # 等待母资源行锁期间可能刚被标记失效，取得锁后再次确认。
            if parent.get("email_invalid"):
                continue
            policy = dict(parent.get("derivation_policy") or {})
            ceiling = int(policy.get("max_children", max_children))
            count = record_store.count_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, where="source = %s AND parent_id = %s", params=(source, candidate_id), conn=current)
            if count >= ceiling:
                continue
            profile_id = policy.get("inbox_profile_id") or inbox_profile_id
            profile = get_inbox_profile(int(profile_id), conn=current) if profile_id else None
            if not profile_id and profile_factory is not None:
                profile = profile_factory(parent, current)
                profile_id = profile.get("id") if profile else None
            if not profile_id or not profile or profile["state"] != "active" or (profile_validator is not None and not profile_validator(profile)):
                if failure is not None:
                    failure.update(reason_code="email_derivation_profile_unavailable", reason="母邮箱固定收件配置缺失或已停用，不能生成新的子地址")
                continue
            parent_address = str(parent["email"]).strip()
            for _ in range(5):
                try:
                    address, tag = _new_address(parent_address, int(policy.get("tag_length", tag_length)))
                except ValueError:
                    if failure is not None:
                        failure.update(reason_code="email_derivation_address_invalid", reason="母邮箱格式或生成后的地址长度不符合邮箱限制")
                    break
                record_store.advisory_xact_lock(current, f"registered-account:{normalize_address(address)}")
                if address_is_taken(address, conn=current):
                    if failure is not None:
                        failure.update(reason_code="email_derivation_address_collision", reason="生成后缀连续与历史地址冲突，请重新发起生成请求")
                    continue
                allocation_id = record_store.insert_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, {
                    "address": address, "address_norm": normalize_address(address), "source": source,
                    "parent_kind": table.name, "parent_id": candidate_id, "parent_address": parent_address,
                    "inbox_profile_id": int(profile_id), "strategy": "plus_tag", "tag": tag,
                    "acquisition_id": None if generation_key else acquisition_id,
                    "owner_kind": None if generation_key else owner_kind, "owner_id": None if generation_key else str(owner_id),
                    "state": "available" if generation_key else "reserved", "generation_key": generation_key,
                    "policy_version": 1, "max_children_at_issue": ceiling,
                    **({"generation_request_id": generation_request["request_id"], "generation_request": generation_request}
                       if generation_request else {}),
                }, conn=current)
                if not policy.get("inbox_profile_id"):
                    # 首次成功分配即固定母资源路由，后续同母子地址不跟随全局收件箱切换。
                    record_store.patch_row(table, candidate_id, {
                        "derivation_policy": {**policy, "inbox_profile_id": int(profile_id)},
                    }, conn=current)
                allocation = get_allocation(allocation_id, conn=current)
                if not generation_key:
                    _bind_business(allocation, job_id=job_id, attempt_id=attempt_id, root_task_id=root_task_id, conn=current)
                return allocation
        return None


def inventory_eligibility(source: str, *, account_ids: list[str] | None = None) -> tuple[list[str], list]:
    """容量与领取共用健康条件；既有库存不再受生成额度或全局收件箱影响。"""
    conditions = ["a.source = %s", "a.state = 'available'", "a.acquisition_id IS NULL",
        "a.owner_kind IS NULL", "a.owner_id IS NULL", "a.account_id IS NULL",
        "COALESCE(p.status, 'available') IN ('available', 'used', 'replaced', 'reserved')",
        "COALESCE(p.data->>'remote_active', 'true') <> 'false'",
        "COALESCE(p.data->>'archived', 'false') <> 'true'",
        "COALESCE(p.data->>'email_invalid', 'false') <> 'true'",
        "COALESCE(p.data->>'disabled_reason', '') NOT IN ('remote_inactive', 'remote_missing', 'manual_disabled')",
        "COALESCE(p.data->'derivation_policy'->>'enabled', 'true') <> 'false'",
        "profile.state = 'active'", "profile.connector = ANY(%s)"]
    values: list[Any] = [source, ["forward_imap", "forward_butler"] if source == "icloud_hide" else ["outlook"]]
    if source == "icloud_hide":
        conditions.append("NULLIF(BTRIM(p.account_id), '') IS NOT NULL")
        if account_ids is not None:
            conditions.append("p.account_id = ANY(%s)")
            values.append(account_ids)
    elif source == "outlook":
        conditions += ["COALESCE(NULLIF(BTRIM(p.data->>'client_id'), ''), NULLIF(BTRIM(p.data->>'clientId'), '')) IS NOT NULL",
            "COALESCE(NULLIF(BTRIM(p.data->>'refresh_token'), ''), NULLIF(BTRIM(p.data->>'refreshToken'), '')) IS NOT NULL"]
    return conditions, values


def claim_address(*, source: str, acquisition_id: str, owner_kind: str, owner_id: Any,
                  job_id=None, attempt_id=None, root_task_id=None, account_ids=None,
                  profile_validator: Callable[[dict], bool] | None = None, conn=None) -> dict | None:
    """同一意图恢复原记录，新意图仅原子领取预生成库存。"""
    if not acquisition_id or not owner_kind or owner_id is None:
        raise EmailDerivationError("email_derivation_identity_conflict", "子地址领取缺少稳定业务身份")
    table = _parent_table(source)
    with _connection(conn) as current:
        record_store.advisory_xact_lock(current, f"email-address-acquisition:{acquisition_id}")
        previous = find_allocation(acquisition_id=acquisition_id, conn=current)
        if previous:
            if (previous["source"], previous["owner_kind"], str(previous["owner_id"])) != (source, owner_kind, str(owner_id)):
                raise EmailDerivationError("email_derivation_identity_conflict", "领取身份已归属于其他业务")
            if previous["state"] in {"retired", "replaced"}:
                raise EmailDerivationError("email_derivation_identity_conflict", "原子地址已退役或被换出，请沿原账号记录恢复")
            _bind_business(previous, job_id=job_id, attempt_id=attempt_id, root_task_id=root_task_id, conn=current)
            return previous
        conditions, values = inventory_eligibility(source, account_ids=account_ids)
        joins = f"FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)} a JOIN {postgres_store.qualified(table.name)} p ON p.id = a.parent_id JOIN {postgres_store.qualified(record_store.EMAIL_INBOX_PROFILES.name)} profile ON profile.id = a.inbox_profile_id"
        last_id = 0
        while True:
            with current.cursor() as cur:
                # 候选校验失败时撤销本轮行锁，不能持有多个母资源锁继续扫描。
                cur.execute("SAVEPOINT email_inventory_candidate")
                cur.execute(f"SELECT a.id, a.parent_id {joins} WHERE {' AND '.join(conditions)} AND a.id > %s ORDER BY a.id LIMIT 1 FOR UPDATE OF a SKIP LOCKED", [*values, last_id])
                selected = cur.fetchone()
            if not selected:
                with current.cursor() as cur:
                    cur.execute("RELEASE SAVEPOINT email_inventory_candidate")
                return None
            last_id = int(selected["id"])
            # 母资源更新、删除也锁同一父行，取锁后重读，避免等待期间健康状态变化。
            record_store.get_row(table, int(selected["parent_id"]), conn=current, for_update=True)
            with current.cursor() as cur:
                cur.execute(f"SELECT a.id {joins} WHERE {' AND '.join(conditions)} AND a.id = %s", [*values, last_id])
                eligible = bool(cur.fetchone())
            if eligible and profile_validator is not None:
                allocation = get_allocation(last_id, conn=current)
                eligible = profile_validator(get_inbox_profile(int(allocation["inbox_profile_id"]), conn=current))
            if not eligible:
                with current.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT email_inventory_candidate")
                    cur.execute("RELEASE SAVEPOINT email_inventory_candidate")
                continue
            record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, last_id, {
                "state": "reserved", "acquisition_id": acquisition_id,
                "owner_kind": owner_kind, "owner_id": str(owner_id), "claimed_at": _now(),
            }, conn=current)
            allocation = get_allocation(last_id, conn=current)
            _bind_business(allocation, job_id=job_id, attempt_id=attempt_id, root_task_id=root_task_id, conn=current)
            with current.cursor() as cur:
                cur.execute("RELEASE SAVEPOINT email_inventory_candidate")
            return allocation


def update_inventory_status(ids: list[int], state: str, *, conn=None) -> dict:
    if state not in {"available", "disabled"}:
        raise EmailDerivationError("email_derivation_request_conflict", "库存操作仅支持停用或恢复可领取")
    results = []
    with _connection(conn) as current:
        # 多个批量操作先按统一顺序取锁，避免选择顺序相反时互相等待。
        with current.cursor() as cur:
            cur.execute(f"SELECT id FROM {postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)} WHERE id = ANY(%s) ORDER BY id FOR UPDATE", (list(dict.fromkeys(ids)),))
            cur.fetchall()
        for allocation_id in dict.fromkeys(ids):
            row = record_store.get_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, int(allocation_id), conn=current, for_update=True)
            reason_code, reason = "", ""
            if not row:
                reason_code, reason = "email_derivation_inventory_missing", "子地址库存不存在"
            elif row["state"] not in {"available", "disabled"} or any(row.get(key) is not None for key in ("acquisition_id", "owner_kind", "owner_id", "account_id")):
                reason_code, reason = "email_derivation_inventory_assigned", "子地址已领取或绑定，不能重新投入库存"
            elif row["state"] == state:
                reason_code, reason = "email_derivation_inventory_unchanged", "库存已处于目标状态"
            else:
                record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, int(allocation_id), {"state": state}, conn=current)
            results.append({"id": int(allocation_id), "ok": not reason_code, "reason_code": reason_code, "reason": reason})
    updated = sum(item["ok"] for item in results)
    return {"updated": updated, "skipped": len(results) - updated, "results": results}


def get_otp_request(request_id: int, *, conn=None) -> dict | None:
    return record_store.get_row(record_store.EMAIL_OTP_REQUESTS, request_id, conn=conn)


def find_active_otp_request(address: str, *, conn=None) -> dict | None:
    rows = record_store.list_rows(record_store.EMAIL_OTP_REQUESTS, where="address_key = %s AND state = 'active'",
                                  params=(normalize_address(address),), order_by="id DESC", limit=1, conn=conn)
    return rows[0] if rows else None


def list_otp_requests(address: str, *, limit: int = 100, conn=None) -> list[dict]:
    return record_store.list_rows(record_store.EMAIL_OTP_REQUESTS, where="address_key = %s", params=(normalize_address(address),),
                                  order_by="id DESC", limit=limit, conn=conn)


def acquire_otp_request(*, address: str, owner_kind: str, owner_id: Any,
                        address_binding_id: int | None = None, attempt_id: int | None = None,
                        challenge_id: str = "", new_generation: bool = True, lease_seconds: int = 120,
                        execution_token: str = "", conn=None) -> dict:
    address_key = normalize_address(address)
    if not address_key or not owner_kind or str(owner_id or "") == "":
        raise ValueError("认证租约必须提供完整地址和业务归属")
    with _connection(conn) as current:
        record_store.advisory_xact_lock(current, f"email-otp-address:{address_key}")
        if address_binding_id is not None:
            binding = get_allocation(address_binding_id, conn=current)
            if not binding or binding["address_norm"] != address_key:
                raise ValueError("认证请求与完整地址绑定不一致")
        previous_rows = list_otp_requests(address_key, limit=1, conn=current)
        previous = previous_rows[0] if previous_rows else None
        active = find_active_otp_request(address_key, conn=current)
        same_owner = active and (active["owner_kind"], active["owner_id"]) == (owner_kind, str(owner_id))
        if active and active["lease_expires_at"] > _now() and (not same_owner or execution_token != active["execution_token"]):
            raise OtpLeaseBusy("该完整邮箱已有活跃认证执行")
        fence = max(int(previous["fence"]) if previous else 0, int(active["fence"]) if active else 0) + 1
        if active and same_owner and not new_generation:
            if challenge_id and challenge_id != active["challenge_id"]:
                raise ValueError("复用认证请求时 challenge 必须保持一致")
            record_store.patch_row(record_store.EMAIL_OTP_REQUESTS, active["id"], {
                "execution_token": execution_token or secrets.token_hex(16), "fence": fence,
                "lease_expires_at": _expires(lease_seconds),
            }, conn=current)
            return get_otp_request(active["id"], conn=current)
        if active:
            record_store.patch_row(record_store.EMAIL_OTP_REQUESTS, active["id"], {"state": "superseded", "lease_expires_at": _now()}, conn=current)
        generation = int(previous["send_generation"]) + 1 if previous else 1
        request_id = record_store.insert_row(record_store.EMAIL_OTP_REQUESTS, {
            "address_key": address_key, "address_binding_id": address_binding_id, "owner_kind": owner_kind,
            "owner_id": str(owner_id), "attempt_id": attempt_id, "challenge_id": challenge_id or secrets.token_hex(16),
            "send_generation": generation, "requested_at": _now(), "send_state": "prepared", "state": "active",
            "submission_state": "not_started", "execution_token": execution_token or secrets.token_hex(16),
            "fence": fence, "lease_expires_at": _expires(lease_seconds),
        }, conn=current)
        return get_otp_request(request_id, conn=current)


def _update_otp(request_id, *, execution_token, fence, changes, conn=None):
    with _connection(conn) as current:
        row = record_store.get_row(record_store.EMAIL_OTP_REQUESTS, request_id, conn=current, for_update=True)
        if not row or row["state"] != "active" or row["execution_token"] != execution_token or int(row["fence"]) != int(fence) or row["lease_expires_at"] <= _now():
            raise StaleOtpFence("认证执行资格已经失效")
        record_store.patch_row(record_store.EMAIL_OTP_REQUESTS, request_id, changes, conn=current)
        return get_otp_request(request_id, conn=current)


def renew_otp_lease(request_id: int, *, execution_token: str, fence: int, lease_seconds: int = 120, conn=None) -> dict:
    return _update_otp(request_id, execution_token=execution_token, fence=fence,
                       changes={"lease_expires_at": _expires(lease_seconds)}, conn=conn)


def update_otp_send(request_id: int, *, execution_token: str, fence: int, send_state: str,
                    cursor: dict | None = None, conn=None) -> dict:
    if send_state not in {"prepared", "sent", "request_unknown", "failed"}:
        raise ValueError("未知发码状态")
    changes = {"send_state": send_state}
    if cursor is not None:
        changes["cursor"] = _metadata(cursor)
    return _update_otp(request_id, execution_token=execution_token, fence=fence, changes=changes, conn=conn)


def record_otp_candidate(request_id: int, *, execution_token: str, fence: int, message_key: str,
                         evidence: dict | None = None, cursor: dict | None = None, conn=None) -> dict:
    if not str(message_key or "").strip():
        raise ValueError("验证码候选必须具有稳定消息标识")
    changes = {"candidate_message_key": message_key, "candidate_evidence": _metadata(evidence)}
    if cursor is not None:
        changes["cursor"] = _metadata(cursor)
    with _connection(conn) as current:
        row = record_store.get_row(record_store.EMAIL_OTP_REQUESTS, request_id, conn=current, for_update=True)
        if row and row.get("candidate_message_key") and row["candidate_message_key"] != message_key and row["submission_state"] in {"started", "result_unknown"}:
            raise ValueError("提交结果未明确前不能替换原验证码候选事实")
        return _update_otp(request_id, execution_token=execution_token, fence=fence, changes=changes, conn=current)


def record_otp_submission(request_id: int, *, execution_token: str, fence: int, submission_state: str, conn=None) -> dict:
    if submission_state not in {"offered", "started", "confirmed", "result_unknown", "rejected"}:
        raise ValueError("未知验证码提交状态")
    changes = {"submission_state": submission_state}
    if submission_state == "confirmed":
        changes.update(state="confirmed", lease_expires_at=_now())
    return _update_otp(request_id, execution_token=execution_token, fence=fence, changes=changes, conn=conn)


def finish_otp_request(request_id: int, *, execution_token: str, fence: int, state: str = "confirmed", conn=None) -> dict:
    if state not in {"confirmed", "invalid", "cancelled", "expired"}:
        raise ValueError("未知认证请求终态")
    return _update_otp(request_id, execution_token=execution_token, fence=fence,
                       changes={"state": state, "lease_expires_at": _now()}, conn=conn)
