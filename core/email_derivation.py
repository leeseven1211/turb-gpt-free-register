# -*- coding: utf-8 -*-
"""邮箱子地址的生成、持久恢复及收件链路解析。"""
from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit

from config import email as email_config
from core import record_store
from core.storage import email_address_allocations as store

_SUPPORTED_SOURCES = {"icloud_hide", "outlook"}
_POLICY = ContextVar("email_derivation_policy", default=None)
_PROFILE_LOCK = threading.RLock()
EmailDerivationError = store.EmailDerivationError


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
    if str(getattr(email_config, "ICLOUD_HME_INBOX_MODE", "sidecar")) == "forward_butler":
        base = str(getattr(email_config, "EMAIL_BUTLER_API_BASE", "") or "").strip().rstrip("/")
        mailbox = str(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "") or "").strip().lower()
        key = str(getattr(email_config, "EMAIL_BUTLER_API_KEY", "") or "").strip()
        if not _butler_locator_valid({"api_base": base, "mailbox_email": mailbox}) or not key:
            raise RuntimeError("子地址收件链路缺少完整 Butler API 地址、Key 或最终收件箱")
        identity = hashlib.sha256(f"butler:{base}:{mailbox}".encode()).hexdigest()
        version = hashlib.sha256(f"{identity}:{key}".encode()).hexdigest()
        reference = f"EMAIL_DERIVATION_BUTLER_SECRET_{version[:20].upper()}"
        _save_profile_secret(reference, key)
        return store.create_inbox_profile(
            inbox_key=f"butler:{identity}", connector="forward_butler", credential_ref=reference,
            inbox_locator={"api_base": base, "mailbox_email": mailbox},
            data={"evidence_rules_version": 1, "require_recipient_evidence": True},
        )
    if str(getattr(email_config, "ICLOUD_HME_INBOX_MODE", "sidecar")) != "forward_imap":
        raise RuntimeError("当前 iCloud 收件连接器尚未声明子地址隔离能力，请使用 Gmail IMAP 或严格 Butler 链路")
    server = str(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_SERVER", "imap.gmail.com") or "").strip()
    try:
        port = int(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_PORT", 993) or 993)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("子地址收件链路的 IMAP 端口无效") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("子地址收件链路的 IMAP 端口须为 1–65535")
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
    """同一意图恢复原身份；新意图只领取已生成人工库存。"""
    if not owner_kind or owner_id is None or not str(acquisition_id or "").strip():
        raise EmailDerivationError("email_derivation_identity_conflict", "子地址领取缺少持久业务意图")
    previous = store.find_allocation(acquisition_id=str(acquisition_id))
    selected = dict(policy if isinstance(policy, dict) else (_POLICY.get() or policy_snapshot()))
    if not previous and not enabled_for(source, policy=selected):
        raise EmailDerivationError("email_derivation_source_disabled", "当前任务未启用该来源的邮箱子地址库存")
    if source not in _SUPPORTED_SOURCES:
        raise EmailDerivationError("email_derivation_source_unsupported", "该邮箱连接器尚未声明子地址的精确取码及持久恢复能力")
    account_id = str(getattr(email_config, "ICLOUD_HME_ACCOUNT_ID", "") or "").strip()
    allocation = store.claim_address(
        source=source, acquisition_id=str(acquisition_id), owner_kind=owner_kind, owner_id=owner_id,
        job_id=job_id, attempt_id=attempt_id,
        account_ids=[account_id] if source == "icloud_hide" and account_id else None,
        profile_validator=lambda profile: _inventory_profile_usable(profile, source),
    )
    if not allocation:
        raise EmailDerivationError("email_derivation_inventory_empty", "可领取子地址库存不足，请先生成或恢复可用库存后重跑原任务")
    return str(allocation["address"])


def generate_inventory(source: str, count: int, request_id: str, parent_id: int | None = None) -> dict:
    """人工生成无业务归属库存；请求重试先恢复原结果，再考虑上游准备。"""
    source = str(source or "").strip().lower()
    if source not in _SUPPORTED_SOURCES:
        raise EmailDerivationError("email_derivation_source_unsupported", "该来源尚未支持精确子地址库存")
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 1000:
        raise EmailDerivationError("email_derivation_request_conflict", "生成数量必须是 1–1000 的整数")
    request_id = str(request_id or "").strip()
    if not request_id or len(request_id) > 200 or (parent_id is not None and (isinstance(parent_id, bool) or not isinstance(parent_id, int) or parent_id < 1)):
        raise EmailDerivationError("email_derivation_request_conflict", "生成请求身份或母资源编号无效")
    request = {"request_id": request_id, "source": source, "count": count, "parent_id": parent_id}
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, f"email-address-generation-request:{request_id}")
        saved_request = record_store.get_row_by(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS,
            "request_id", request_id, conn=conn)
        if saved_request:
            if (saved_request["source"], int(saved_request["requested"]), saved_request.get("parent_id")) != (source, count, parent_id):
                raise EmailDerivationError("email_derivation_request_conflict", "该生成请求已用于不同来源、数量或母资源")
            result = dict(saved_request["result"])
            result["reused"] = int(result["created"]) + int(result["reused"])
            result["created"] = 0
            return result
        previous = record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS,
            where="data->>'generation_request_id' = %s", params=(request_id,), order_by="id ASC", conn=conn)
        if previous:
            if any(row.get("generation_request") != request for row in previous):
                raise EmailDerivationError("email_derivation_request_conflict", "该生成请求已用于不同来源、数量或母资源")
            failure = previous[0].get("generation_result") or {}
            return _generation_result(count, created=0, reused=len(previous), failure=failure)
        selected = policy_snapshot()
        kwargs: dict[str, Any] = {}
        if source == "icloud_hide":
            from core.icloud_hme_client import sync_aliases
            try:
                profile = _forward_profile()
            except RuntimeError as exc:
                raise EmailDerivationError("email_derivation_profile_unavailable", str(exc)) from exc
            try:
                synced = sync_aliases(force=False)
            except Exception as exc:
                raise EmailDerivationError("email_derivation_parent_unavailable", "iCloud 母资源同步失败，请恢复服务后重试原生成请求") from exc
            accounts = [str(value) for value in synced.get("synced_account_ids", []) if str(value)]
            if not accounts and synced.get("account_id"):
                accounts = [str(synced["account_id"])]
            if not accounts:
                raise EmailDerivationError("email_derivation_parent_unavailable", "没有成功同步的 iCloud 母资源账号")
            kwargs.update(inbox_profile_id=int(profile["id"]), account_ids=accounts)
        else:
            kwargs["profile_factory"] = _outlook_profile
        created = 0
        generated_ids = []
        failure = {}
        request_key = hashlib.sha256(request_id.encode()).hexdigest()
        for number in range(count):
            row = store.allocate_address(source=source, acquisition_id=None, owner_kind=None, owner_id=None,
                parent_id=parent_id, max_children=selected["max_children"], tag_length=selected["tag_length"],
                generation_key=f"{request_key}:{number}", generation_request=request, failure=failure,
                profile_validator=lambda profile: _inventory_profile_usable(profile, source), conn=conn, **kwargs)
            if row is None:
                break
            created += 1
            generated_ids.append(int(row["id"]))
        result = _generation_result(count, created=created, reused=0, failure=failure)
        if generated_ids:
            record_store.patch_row(record_store.EMAIL_ADDRESS_ALLOCATIONS, generated_ids[0], {
                "generation_result": {"reason_code": result["reason_code"], "reason": result["reason"]},
            }, conn=conn)
        # 零结果也留下事实，重试不能改变生成范围或再次依赖上游准备。
        record_store.insert_row(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS, {
            "request_id": request_id, "source": source, "requested": count, "parent_id": parent_id,
            "result": result,
        }, conn=conn)
        return result


def _generation_result(requested: int, *, created: int, reused: int, failure: dict | None = None) -> dict:
    shortfall = max(0, requested - created - reused)
    failure = failure or {}
    return {"requested": requested, "created": created, "reused": reused, "shortfall": shortfall,
        "reason_code": failure.get("reason_code", "email_derivation_capacity_exhausted") if shortfall else "",
        "reason": failure.get("reason", "合格母资源的累计生成额度已用完") if shortfall else ""}


def update_inventory_status(ids: list[int], state: str) -> dict:
    if not isinstance(ids, list) or not ids or len(ids) > 1000 or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in ids):
        raise EmailDerivationError("email_derivation_request_conflict", "请选择 1–1000 个有效子地址编号")
    return store.update_inventory_status(ids, state)


def resolve_route(address: str, *, source: str | None = None) -> dict | None:
    binding = find_binding(address)
    if binding is None:
        return None
    if source and binding["source"] != source:
        raise EmailDerivationError("email_derivation_identity_conflict", "子地址的原邮箱来源与当前任务不一致")
    parent = store.get_parent(binding["source"], int(binding["parent_id"]))
    profile = store.get_inbox_profile(int(binding["inbox_profile_id"]))
    if parent is None:
        raise EmailDerivationError("email_derivation_parent_unavailable", "子地址的原母资源缺失，不能猜测其他邮箱代收")
    if profile is None:
        raise EmailDerivationError("email_derivation_profile_unavailable", "子地址的原收件配置缺失，不能猜测其他邮箱代收")
    return {"binding": binding, "parent": parent, "profile": profile, "exact_target": binding["address"]}


def restore_address(address: str, *, source: str | None = None) -> dict | None:
    route = resolve_route(address, source=source)
    if route and route["binding"]["state"] == "retired":
        raise EmailDerivationError("email_derivation_identity_conflict", "该完整子地址已被明确退役")
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
        raise EmailDerivationError("email_derivation_profile_unavailable", "原收件配置的凭据引用缺失，不能切换当前全局收件账号")
    secret_field = "api_key" if profile["connector"] == "forward_butler" else "password"
    return {
        **dict(profile.get("inbox_locator") or {}), "connector": profile["connector"], secret_field: password,
        "id": profile["id"], "inbox_key": profile["inbox_key"], "revision": profile["revision"],
        **({"require_recipient_evidence": True} if profile["connector"] == "forward_butler" else {}),
    }


def _butler_locator_valid(locator: dict) -> bool:
    """固定 Butler 路由只接受 HTTP API 地址与完整最终邮箱。"""
    try:
        parsed = urlsplit(str(locator.get("api_base") or ""))
        mailbox = str(locator.get("mailbox_email") or "").strip()
        return bool(parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username
                    and mailbox.partition("@")[0] and mailbox.partition("@")[2])
    except ValueError:
        return False


def _inventory_profile_usable(profile: dict, source: str, *, secret_cache: dict | None = None) -> bool:
    """新领取只认固定路由及其原密钥引用，不探测网络或当前全局收件账号。"""
    connectors = {"forward_imap", "forward_butler"} if source == "icloud_hide" else {"outlook"}
    if not profile or profile.get("state") != "active" or profile.get("connector") not in connectors:
        return False
    reference = str(profile.get("credential_ref") or "").strip()
    if not reference:
        return False
    if source != "icloud_hide":
        return True
    locator = profile.get("inbox_locator") or {}
    if not isinstance(locator, dict):
        return False
    if profile["connector"] == "forward_butler":
        if not _butler_locator_valid(locator):
            return False
    else:
        if not str(locator.get("server") or "").strip():
            return False
        email = str(locator.get("email") or "").strip()
        if not email.partition("@")[0] or not email.partition("@")[2]:
            return False
        try:
            if not 1 <= int(locator.get("port", 993)) <= 65535:
                return False
        except (TypeError, ValueError):
            return False
    if str(os.environ.get(reference) or "").strip():
        return True
    from config.env_loader import read_env_file
    if secret_cache is None:
        secret_cache = {}
    if "persisted" not in secret_cache:
        secret_cache["persisted"] = read_env_file()
    return bool(str(secret_cache["persisted"].get(reference) or "").strip())


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
            if profile is None or profile.get("connector") not in {"forward_imap", "forward_butler"}:
                raise RuntimeError("历史子地址的固定收件配置缺失")
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
    if profile["connector"] in {"forward_imap", "forward_butler"}:
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
    """仅 SELECT 统计实际可领取库存，复用领取健康条件及已固定收件配置。"""
    from psycopg.rows import dict_row
    from core import postgres_store

    selected = str(source or "").strip()
    policy = policy_snapshot()
    result = {"source": selected, "enabled": False, "remaining": 0, "parent_count": 0,
        "remaining_parent_count": 0, "issued": 0, "max_children": policy["max_children"], "reason": ""}
    if not enabled_for(selected, policy=policy):
        result["reason"] = "该来源未启用邮箱子地址库存"
        return result
    if selected not in _SUPPORTED_SOURCES:
        result["reason"] = "该邮箱连接器尚未声明精确子地址能力"
        return result
    table = record_store.ICLOUD_HIDE_POOL if selected == "icloud_hide" else record_store.OUTLOOK_POOL
    parents = postgres_store.qualified(table.name)
    ledger = postgres_store.qualified(record_store.EMAIL_ADDRESS_ALLOCATIONS.name)
    profiles = postgres_store.qualified(record_store.EMAIL_INBOX_PROFILES.name)
    account_id = str(getattr(email_config, "ICLOUD_HME_ACCOUNT_ID", "") or "").strip()
    conditions, values = store.inventory_eligibility(selected,
        account_ids=[account_id] if selected == "icloud_hide" and account_id else None)
    with postgres_store.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS parents, to_regclass(%s) AS ledger, to_regclass(%s) AS profiles", (parents, ledger, profiles))
        if not all(cur.fetchone().values()):
            result["reason"] = "子地址账本尚未初始化"
            return result
        cur.execute(f"""SELECT profile.id, profile.state, profile.connector, profile.credential_ref, profile.data,
                   count(*) AS stock, array_agg(DISTINCT a.parent_id) AS parent_ids
            FROM {ledger} a JOIN {parents} p ON p.id = a.parent_id
            JOIN {profiles} profile ON profile.id = a.inbox_profile_id
            WHERE {' AND '.join(conditions)} GROUP BY profile.id""", values)
        eligible_parents, secret_cache = set(), {}
        for row in cur.fetchall():
            profile = {**dict(row.get("data") or {}), **dict(row)}
            if _inventory_profile_usable(profile, selected, secret_cache=secret_cache):
                result["remaining"] += int(row["stock"])
                eligible_parents.update(row["parent_ids"])
        result["parent_count"] = len(eligible_parents)
        result["remaining_parent_count"] = result["parent_count"]
        cur.execute(f"SELECT count(*) AS issued FROM {ledger} WHERE source = %s", (selected,))
        result["issued"] = int(cur.fetchone()["issued"])
    result["enabled"] = result["remaining"] > 0
    if not result["enabled"]:
        result["reason"] = "可领取子地址库存不足，请先生成或恢复可用库存后重跑"
    return result


def generation_capacity_summary(source: str) -> dict:
    """只读取本地事实估算新意图容量，不同步母资源，也不创建路由或持久密钥。"""
    from psycopg.rows import dict_row
    from core import postgres_store

    selected = str(source or "").strip()
    policy = policy_snapshot()
    result = {"source": selected, "enabled": False, "remaining": 0, "parent_count": 0,
              "remaining_parent_count": 0, "issued": 0, "max_children": policy["max_children"], "reason": ""}
    if selected not in _SUPPORTED_SOURCES:
        result["reason"] = "该邮箱连接器尚未声明精确子地址能力"
        return result
    if selected == "icloud_hide":
        mode = str(getattr(email_config, "ICLOUD_HME_INBOX_MODE", "sidecar"))
        if mode not in {"forward_imap", "forward_butler"}:
            result["reason"] = "iCloud 子地址需要 Gmail IMAP 或严格 Butler 收件链路"
            return result
        names = (("ICLOUD_HME_API_BASE", "EMAIL_BUTLER_API_BASE", "EMAIL_BUTLER_API_KEY", "ICLOUD_HME_FORWARD_IMAP_EMAIL")
                 if mode == "forward_butler" else ("ICLOUD_HME_API_BASE", "ICLOUD_HME_FORWARD_IMAP_SERVER",
                    "ICLOUD_HME_FORWARD_IMAP_EMAIL", "ICLOUD_HME_FORWARD_IMAP_PASSWORD"))
        missing = [name for name in names
                   if not str(getattr(email_config, name, "") or "").replace(" ", "").strip()]
        try:
            port_ok = 1 <= int(getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_PORT", 993) or 993) <= 65535
        except (ValueError, TypeError):
            port_ok = False
        if mode == "forward_butler":
            port_ok = _butler_locator_valid({"api_base": getattr(email_config, "EMAIL_BUTLER_API_BASE", ""),
                "mailbox_email": getattr(email_config, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "")})
        if missing or not port_ok:
            if mode == "forward_butler":
                result["reason"] = "子地址收件链路缺少完整 Butler API 地址、Key 或最终收件箱"
                return result
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
    summary = {"total": 0, "parent_count": len(groups), "available": 0, "disabled": 0, "reserved": 0, "used": 0, "replaced": 0, "retired": 0}
    for group in groups:
        key = (group["source"], int(group["parent_id"]))
        parent = parent_rows.get(key) or {}
        max_children = int((parent.get("policy") or {}).get("max_children", policy["max_children"]))
        child_count = int(group["issued"])
        parents.append({"source": key[0], "parent_id": key[1], "parent_email": parent.get("email", ""),
                        "child_count": child_count, "max_children": max_children,
                        "remaining": 0 if parent.get("email_invalid") else max(0, max_children - child_count)})
        summary["total"] += child_count
        for state in ("available", "disabled", "reserved", "used", "replaced", "retired"):
            summary[state] += int(group[state])
    return {**policy, **summary, "parents": parents}


def list_allocations(source: str | None = None, parent_id: int | None = None, page: int = 1, page_size: int = 50,
                     q: str = "", parent_q: str = "", state: str = "", related_q: str = "",
                     created_from: str = "", created_to: str = "") -> dict:
    page, page_size = max(1, int(page)), max(1, min(100, int(page_size)))
    if state and state not in store._STATES:
        raise EmailDerivationError("email_derivation_request_conflict", "未知的子地址库存状态")
    if created_from or created_to:
        from datetime import date
        try:
            for value in (created_from, created_to):
                if value:
                    date.fromisoformat(value)
        except (TypeError, ValueError) as exc:
            raise EmailDerivationError("email_derivation_request_conflict", "生成时间须为有效日期") from exc
        if created_from and created_to and created_from > created_to:
            raise EmailDerivationError("email_derivation_request_conflict", "生成时间起始日期不能晚于结束日期")
    filters = dict(source=str(source or "").strip(), parent_id=parent_id, q=q, parent_q=parent_q,
        state=state, related_q=related_q, created_from=created_from, created_to=created_to)
    rows = store.list_allocations(**filters, limit=page_size, offset=(page - 1) * page_size)
    clauses, values = store.allocation_filters(**filters)
    total = record_store.count_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS, where=" AND ".join(clauses), params=values)
    public = []
    for row in rows:
        unassigned = all(row.get(key) is None for key in ("acquisition_id", "owner_kind", "owner_id", "account_id"))
        public.append({
            "id": row["id"], "email": row["address"], "parent_id": row["parent_id"],
            "parent_email": row["parent_address"], "source": row["source"], "state": row["state"],
            "registered_account_id": row.get("account_id"),
            "root_task_id": row.get("owner_id") if row.get("owner_kind") == "registration_root" else None,
            "created_at": row.get("created_at"), "updated_at": row.get("updated_at"),
            "can_disable": unassigned and row["state"] == "available",
            "can_restore": unassigned and row["state"] == "disabled",
        })
    return {"items": public, "total": total, "page": page, "page_size": page_size}


def parent_has_allocations(source: str, parent_id: int, *, conn=None) -> bool:
    return bool(store.list_allocations(source=source, parent_id=int(parent_id), limit=1, conn=conn))


def mark_registered(address: str, account_id: int, *, conn) -> int | None:
    binding = store.find_allocation(address=address, conn=conn)
    if binding is None:
        return None
    store.mark_allocation_state(int(binding["id"]), "used", account_id=int(account_id), conn=conn)
    return int(binding["id"])
