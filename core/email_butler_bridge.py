# -*- coding: utf-8 -*-
"""在保留历史 HME 业务身份的前提下，显式桥接到 Butler。"""
from __future__ import annotations

from config import email as cfg
from core import email_butler_client as butler


def enabled() -> bool:
    return bool(getattr(cfg, "ICLOUD_HME_BUTLER_BRIDGE_ENABLED", False))


def fixed_context(email: str):
    """既有固定路由独立于当前桥接开关；只查本地，绝不使用全局回退。"""
    from core import db, email_derivation

    address = str(email or '').strip().lower()
    cached = butler.get_account_context(address)
    if cached and cached.provider == 'icloud_hme':
        return cached
    context = butler._restore_hme_context(address)
    if context:
        return context
    parent = db.get_icloud_hide_email_by_email(address)
    profile_id = (parent or {}).get('local_inbox_profile_id') or ((parent or {}).get('derivation_policy') or {}).get('inbox_profile_id')
    if not profile_id:
        return None
    profile = email_derivation.store.get_inbox_profile(int(profile_id))
    if not profile or profile.get('connector') != 'forward_butler':
        return None
    if profile.get('state') != 'active':
        raise butler.EmailButlerClientError('email_derivation_profile_unavailable: 原 HME 固定收件配置不可用')
    connection = email_derivation._profile_credentials(profile)
    return butler.EmailButlerAccount(email=address, mailbox_id='', provider='icloud_hme',
        mailbox_email=connection['mailbox_email'], api_base=connection['api_base'], api_key=connection['api_key'],
        recipient_mode='forwarded_exact_v1', strict_family=True,
        acquisition_id=str((parent or {}).get('local_acquisition_id') or ''))


def restore_context(email: str, *, purpose: str = "historical-hme", profile: dict | None = None):
    """只恢复已导入的原完整地址，不申请替代邮箱，也不调用 Apple。"""
    from core import db, email_derivation

    address = str(email or "").strip().lower()
    fixed = fixed_context(address)
    if fixed:
        return fixed
    route = email_derivation.restore_address(address, source="icloud_hide")
    if route:
        profile = profile or route["profile"]
    else:
        parent = db.get_icloud_hide_email_by_email(address)
        if not parent:
            account = db.get_account_by_email(address)
            if not account or account.get("email_source") != "icloud_hide":
                raise butler.EmailButlerClientError("recipient_mismatch: 历史 HME 完整身份不存在，不能改领新地址")
        profile_id = ((parent or {}).get("derivation_policy") or {}).get("inbox_profile_id")
        if profile_id and profile is None:
            profile = email_derivation.store.get_inbox_profile(int(profile_id))
        if profile is None:
            from core import record_store
            rows = record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS,
                where="source = %s AND LOWER(parent_address) = %s", params=("icloud_hide", address),
                order_by="id DESC", limit=1)
            if rows:
                profile = email_derivation.store.get_inbox_profile(int(rows[0]["inbox_profile_id"]))
    if profile and profile.get("connector") == "forward_butler":
        from core.email_derivation import _profile_credentials

        credentials = _profile_credentials(profile)
        connection = {name: credentials[name] for name in ("api_base", "api_key", "mailbox_email")}
    else:
        connection = {"api_base": butler._api_base(), "api_key": butler._api_key(),
            "mailbox_email": str(getattr(cfg, "ICLOUD_HME_FORWARD_IMAP_EMAIL", "") or "").strip().lower()}
    if not connection["mailbox_email"].partition("@")[2]:
        raise butler.EmailButlerClientError("mailbox_mismatch: 历史 HME 桥接缺少最终收件箱")
    return butler.EmailButlerAccount(email=address, mailbox_id="", provider="icloud_hme",
        recipient_mode="forwarded_exact_v1", strict_family=True, **connection)


def pick_account(*, owner_kind=None, owner_id=None, acquisition_id=None, batch_id=None, job_id=None):
    """新意图只领取本地邮箱，旧意图恢复原完整身份。"""
    from core.email_derivation import store
    from core.local_email_inventory import claim

    previous = store.find_allocation(acquisition_id=acquisition_id) if acquisition_id else None
    if previous:
        if (previous["source"] != "icloud_hide" or previous["owner_kind"] != owner_kind
                or str(previous["owner_id"]) != str(owner_id)):
            raise butler.EmailButlerIntentLocked("email_derivation_identity_conflict: 原 HME 意图的来源或归属不一致")
        return restore_context(previous["address"])
    row = claim("icloud_hide", owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id,
                batch_id=batch_id, job_id=job_id)
    if not row:
        raise butler.EmailButlerClientError("local_email_inventory_empty: 本地 iCloud 隐藏邮箱库存为空，请先手动导入")
    if row.get("_legacy_butler_intent"):
        account = butler._account_from_legacy_intent(row["_legacy_butler_intent"])
        if account.provider != "icloud_hme":
            raise butler.EmailButlerIntentLocked("recipient_contract_unsupported: 原 HME 意图不是 HME provider")
        return account
    # 新库存必须在导入时固定配置，领取后不能再按当前全局连接补建。
    account = fixed_context(row["email"])
    if not account:
        raise butler.EmailButlerIntentLocked('email_derivation_profile_unavailable: 本地 HME 未固定 Butler 收件配置，请重新导入')
    account.acquisition_id = str(row.get("local_acquisition_id") or "")
    butler._CONTEXT_CACHE[str(account.email).lower()] = account
    return account


def fetch_otp(email: str, *, after_ts: float | None = None, profile: dict | None = None, **kwargs) -> str:
    context = restore_context(email, profile=profile)
    return butler.fetch_inbound_otp(email, after_ts=after_ts, require_recipient_evidence=True, strict_family=True,
        mailbox_email=context.mailbox_email, api_base=context.api_base, api_key=context.api_key, **kwargs)


def inbox_profiles_for_addresses(addresses: list[str]) -> dict[str, dict]:
    """批量恢复母子固定收件路由，母地址无需已生成子地址也能固定到 Butler。"""
    from core import email_derivation, record_store

    targets = sorted({str(value or "").strip().lower() for value in addresses if str(value or "").strip()})
    profiles = {}
    if not targets:
        return profiles
    loaded = {}

    def credentials(profile_id):
        key = None
        try:
            key = int(profile_id)
            if key not in loaded:
                profile = email_derivation.store.get_inbox_profile(key)
                if not profile or profile.get("state") != "active" or profile.get("connector") not in {"forward_imap", "forward_butler"}:
                    raise butler.EmailButlerClientError("原固定收件配置不可用")
                loaded[key] = email_derivation._profile_credentials(profile)
            return dict(loaded[key])
        except (RuntimeError, TypeError, ValueError) as exc:
            # 保留失败目标，防止批量调用把缺失的固定配置降级为当前全局邮箱。
            failure = {"error_code": "email_derivation_profile_unavailable",
                "error": f"email_derivation_profile_unavailable: {str(exc)[:300]}"}
            if key is not None:
                loaded[key] = failure
            return dict(failure)

    rows = record_store.list_rows(record_store.EMAIL_ADDRESS_ALLOCATIONS,
        where="source = %s AND (address_norm = ANY(%s) OR LOWER(parent_address) = ANY(%s))",
        params=("icloud_hide", targets, targets), order_by="id DESC")
    for row in rows:
        route = credentials(row["inbox_profile_id"])
        child, parent = str(row["address_norm"]), str(row["parent_address"]).lower()
        if child in targets:
            profiles[child] = dict(route)
        if parent in targets and parent not in profiles:
            profiles[parent] = {**route, "strict_family": True}
    parents = record_store.list_rows(record_store.ICLOUD_HIDE_POOL,
        where="LOWER(email) = ANY(%s)", params=(targets,))
    for parent in parents:
        profile_id = parent.get('local_inbox_profile_id') or (parent.get("derivation_policy") or {}).get("inbox_profile_id")
        if profile_id:
            profiles[str(parent["email"]).strip().lower()] = {**credentials(profile_id), "strict_family": True}
    imported = record_store.list_rows(record_store.EMAIL_BUTLER_POOL,
        where="LOWER(email) = ANY(%s)", params=(targets,))
    for row in imported:
        profile_id = row.get('local_inbox_profile_id') or row.get('inbox_profile_id')
        if profile_id:
            profiles[str(row['email']).strip().lower()] = {**credentials(profile_id), 'strict_family': True}
    return profiles


def release(email: str, *, status: str, note: str | None = None) -> None:
    """未知结果保留租约；其他结果先更新 Butler，再由原入口更新本地状态。"""
    if str(status or "").lower() in {"request_unknown", "unknown", "running", "reserved"}:
        return
    context = restore_context(email)
    if context.mailbox_id:
        butler.release_account(email, status=status, note=note)
        return
    from core.email_derivation import find_binding

    binding = find_binding(email) or {}
    context.acquisition_id = str(binding.get("acquisition_id") or "")
    butler.report_hme_identity(context, status=status, note=note)
