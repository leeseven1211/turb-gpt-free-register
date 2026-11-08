# -*- coding: utf-8 -*-
"""Email Butler v2 业务适配；历史完整身份保持固定归属。"""
from __future__ import annotations

from core.email.mailbox_wait import bounded_sleep, cooperative_checkpoint, cooperative_poll_limit
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from config import email as _email_cfg
from core.email.otp import extract_otp

logger = logging.getLogger('core.email_butler_client')

_OTP_RE = re.compile(r"^\d{6}$")
_INBOUND_WAIT_CHUNK_SECONDS = 75
_TRANSIENT_INBOUND_ERROR_MARKERS = (
    "ConnectionError",
    "ConnectTimeout",
    "ReadTimeout",
    "SSLError",
    "Timeout",
    "HTTP 408",
    "HTTP 425",
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "HTTP 520",
    "HTTP 522",
    "HTTP 523",
    "HTTP 524",
)


class EmailButlerClientError(RuntimeError):
    """Email Butler 连接、租用或收信失败。"""
    def __init__(self, message: str, *, status_code: int | None = None, error_code: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.definite_rejection = status_code is not None and 400 <= status_code < 500 and status_code != 408


class EmailButlerClaimUnknown(EmailButlerClientError):
    """The claim may have committed remotely; only the same intent may recover it."""
    request_unknown = True


class EmailButlerIntentLocked(EmailButlerClientError):
    """An existing intent cannot switch address, owner or provider."""
    identity_locked = True


@dataclass
class EmailButlerAccount:
    email: str
    mailbox_id: str
    lease_id: str = ""
    leased_until: str = ""
    provider: str = ""
    mailbox_email: str = ""
    recipient_mode: str = ""
    strict_family: bool = False
    api_base: str | None = None
    api_key: str | None = field(default=None, repr=False)
    acquisition_id: str = ""
    identity_type: str = "primary"
    parent_email: str = ""
    identity_id: str = ""
    credential_ref: str = ""
    client_id: str = ""
    api_version: int = 2


_CONTEXT_CACHE: dict[str, EmailButlerAccount] = {}
_RECIPIENT_CAPABILITY_CACHE: dict[tuple[str, str], float] = {}
_RECIPIENT_CAPABILITY = "inbound.recipient_evidence.v1"
_RECIPIENT_MODE = "forwarded_exact_v1"


def _cache_key(email: str) -> str:
    return str(email or "").strip().lower()


def _api_base(override: str | None = None) -> str:
    base = str(
        override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_BASE", "") or ""
    ).strip()
    if not base:
        raise EmailButlerClientError("Email Butler API 地址未配置，请填写 /v2 根地址。")
    return base.rstrip("/")


def _api_key(override: str | None = None) -> str:
    key = str(
        override if override is not None else getattr(_email_cfg, "EMAIL_BUTLER_API_KEY", "") or ""
    ).strip()
    if not key:
        raise EmailButlerClientError("Email Butler API Key 未配置。")
    return key


def _request_timeout() -> int:
    return max(3, int(getattr(_email_cfg, "EMAIL_BUTLER_REQUEST_TIMEOUT", 20) or 20))


def _request(method: str, path: str, **kwargs) -> dict:
    """旧合同仅保留可定位错误，禁止向退役接口提交业务写入。"""
    raise EmailButlerClientError("api_version_retired: 请使用 Email Butler v2 租约接口",
                                 status_code=410, error_code="api_version_retired")


def test_connection(*, api_base: str | None = None, api_key: str | None = None) -> dict:
    """只读验证 v2 身份及现有、新导入各自所需的权限。"""
    from core.email.email_butler import v2
    try:
        who = v2.me(api_base=_api_base(api_base), api_key=_api_key(api_key), timeout=_request_timeout())
    except v2.ButlerV2Error as exc:
        raise _v2_error(exc) from exc
    services, permissions = who['allowed_services'], who['permissions']
    if services != '*' and not {'openai', '*'}.intersection(services):
        raise EmailButlerClientError('service_not_allowed: 当前 Key 未授权 openai 服务',
                                     status_code=403, error_code='service_not_allowed')
    required = {'leases.read', 'codes.read', 'leases.release', 'leases.create', 'leases.long_term'}
    missing = sorted(required.difference(permissions)) if '*' not in permissions else []
    return {'ok': True, 'ready': not missing, 'api_version': 2, 'name': who.get('name') or '',
            'consumer': who['client_id'], 'service': 'openai', 'permissions': permissions,
            'capabilities': permissions, 'missing_permissions': missing,
            'api_base': v2.normalize_base(_api_base(api_base)), 'limits': who['limits']}


def _signal_result(payload: dict, target: str, *, strict_family: bool, mailbox_email: str) -> dict:
    try:
        code = int(payload.get("code") or 200)
    except (ValueError, TypeError):
        raise EmailButlerClientError("signal_receipt_invalid: 邮件信号扫描状态无效") from None
    if payload.get("ok") is False or code >= 400:
        error = str(payload.get("error_code") or "signal_scan_failed")
        raise EmailButlerClientError(f"{error}: {str(payload.get('error') or payload.get('message') or '邮件信号扫描未完成')[:300]}")
    signal = payload.get("signal")
    if not isinstance(signal, dict) or not isinstance(signal.get("detected"), bool):
        raise EmailButlerClientError("signal_receipt_invalid: 邮件信号扫描缺少明确结果")
    if strict_family:
        _validate_recipient_match(payload, target, True, mailbox_email)
        if signal["detected"]:
            _validate_recipient_receipt(payload, target, True, mailbox_email)
    return {
        "ok": True,
        "detected": signal["detected"],
        "checked_at": str(payload.get("checked_at") or ""),
        "received_at": str(signal.get("received_at") or ""),
        "subject": str(signal.get("subject") or "")[:300],
        "sender": str(signal.get("from") or "")[:200],
        "message_id": str(signal.get("message_id") or "")[:300],
        "confidence": str(signal.get("confidence") or "none"),
    }


def _signal_request(*, lookback_days: int, strict_family: bool, mailbox_email: str) -> dict:
    result = {
        "signal_type": "openai_account_deactivation",
        "lookback_days": max(1, min(int(lookback_days or 120), 365)),
        "folders": ["inbox", "junk"],
    }
    if strict_family:
        if not mailbox_email.partition("@")[0] or not mailbox_email.partition("@")[2]:
            raise EmailButlerClientError("mailbox_mismatch: 严格信号扫描必须指定最终收件箱")
        result.update(recipient_mode=_RECIPIENT_MODE, strict_family=True, mailbox_email=mailbox_email)
    return result


def scan_openai_deactivation(email: str, *, lookback_days: int = 120,
                            api_base: str | None = None, api_key: str | None = None,
                            mailbox_email: str = "", strict_family: bool = False) -> dict:
    """v2 公开接口没有邮件信号扫描，不能用验证码结果推断账号存活。"""
    raise EmailButlerClientError('signal_scan_unsupported: Email Butler v2 未提供封号邮件扫描接口',
                                 error_code='signal_scan_unsupported')


def scan_openai_deactivation_bulk(emails: list[str], *, lookback_days: int = 120,
                                 api_base: str | None = None, api_key: str | None = None,
                                 mailbox_email: str, strict_family: bool = True) -> dict[str, dict]:
    """逐地址明确不支持扫描，不伪造阴性结果。"""
    return {_cache_key(email): {'ok': False, 'error_code': 'signal_scan_unsupported',
            'error': 'Email Butler v2 未提供封号邮件扫描接口'} for email in emails}


def _mailbox_account(mailbox: dict, *, api_base: str | None = None, api_key: str | None = None) -> EmailButlerAccount:
    """统一核对 HME 租约的严格收件声明，不能用普通邮箱响应代替。"""
    account = EmailButlerAccount(
        email=str(mailbox.get("email") or "").strip(), mailbox_id=str(mailbox.get("id") or "").strip(),
        lease_id=str(mailbox.get("lease_id") or ""), leased_until=str(mailbox.get("leased_until") or ""),
        provider=str(mailbox.get("provider") or ""), mailbox_email=str(mailbox.get("mailbox_email") or mailbox.get("email") or ""),
        recipient_mode=str(mailbox.get("recipient_mode") or ""), strict_family=mailbox.get("strict_family") is True,
        api_base=api_base if api_base is not None else (str(getattr(_email_cfg, "EMAIL_BUTLER_API_BASE", "") or "").strip().rstrip("/") or None),
        api_key=api_key if api_key is not None else (str(getattr(_email_cfg, "EMAIL_BUTLER_API_KEY", "") or "").strip() or None),
        identity_type=str(mailbox.get("identity_type") or "primary"),
        parent_email=str(mailbox.get("parent_email") or "").strip().lower(),
        identity_id=str(mailbox.get("identity_id") or mailbox.get("id") or ""),
    )
    if account.identity_type != "primary":
        if (account.provider != "icloud_hme" or account.recipient_mode != _RECIPIENT_MODE
                or not account.strict_family or not account.parent_email.partition("@")[2]
                or not account.identity_id):
            raise EmailButlerClientError("recipient_contract_unsupported: 子邮箱缺少已支持的精确收件及持久身份声明")
    if account.provider == "icloud_hme":
        if account.recipient_mode != _RECIPIENT_MODE or not account.strict_family:
            raise EmailButlerClientError("recipient_contract_unsupported: HME 租约缺少严格收件声明")
        if not str(mailbox.get("mailbox_email") or "").partition("@")[2]:
            raise EmailButlerClientError("mailbox_mismatch: HME 租约缺少最终收件箱")
    return account


def _account_from_legacy_intent(intent: dict) -> EmailButlerAccount:
    """只恢复已确认远端结果；不会重新提交旧领取请求。"""
    from core.email.derivation import _profile_credentials

    if intent.get("status") != "claimed" or not intent.get("mailbox"):
        raise EmailButlerClaimUnknown("request_unknown: 原 Butler 领取结果尚未明确，保留原意图")
    connection = _profile_credentials({"connector": "forward_butler", "credential_ref": intent["credential_ref"],
        "inbox_locator": {"api_base": intent["api_base"]}, "id": intent["id"], "inbox_key": "butler-claim", "revision": 1})
    account = _mailbox_account(intent["mailbox"], api_base=connection["api_base"], api_key=connection["api_key"])
    if not _cache_key(account.email) or _cache_key(account.email) != _cache_key(intent.get('address_norm')):
        raise EmailButlerIntentLocked('recipient_mismatch: 原 Butler 意图保存的完整邮箱不一致')
    account.acquisition_id = intent["acquisition_id"]
    account.credential_ref = intent["credential_ref"]
    account.lease_id = ""
    if account.provider == 'icloud_hme' and not _restore_hme_context(account.email):
        _persist_hme_context(account)
    _CONTEXT_CACHE[_cache_key(account.email)] = account
    return account


def restore_local_account(email_or_row) -> EmailButlerAccount | None:
    """只恢复已导入库存及固定路由，网络映射在取码前精确核验。"""
    from core.storage import records as record_store
    from core.email.derivation import _profile_credentials
    row = email_or_row if isinstance(email_or_row, dict) else record_store.get_row_by(
        record_store.EMAIL_BUTLER_POOL, 'email', _cache_key(email_or_row), lower=True)
    if not row:
        return None
    profile_id = row.get('local_inbox_profile_id') or row.get('inbox_profile_id')
    profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(profile_id)) if profile_id else None
    if not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
        raise EmailButlerClientError('email_derivation_profile_unavailable: 原邮箱缺少固定收件配置',
                                     error_code='email_derivation_profile_unavailable')
    connection = _profile_credentials(profile)
    handoff, mailbox = row.get('butler_handoff') or {}, row.get('mailbox') or {}
    address = _cache_key(row.get('email'))
    account = EmailButlerAccount(email=address, mailbox_id=str(row.get('mailbox_id') or mailbox.get('id') or ''),
        lease_id=str(handoff.get('lease_id') or ''), provider=str(row.get('provider') or 'icloud_hme'),
        mailbox_email=_cache_key(connection.get('mailbox_email') or row.get('mailbox_email')),
        recipient_mode=_RECIPIENT_MODE, strict_family=True,
        api_base=connection['api_base'], api_key=connection['api_key'],
        acquisition_id=original_handoff_acquisition(address, row=row, profile=profile),
        identity_type=str(row.get('identity_type') or ('plus_alias' if '+' in address.partition('@')[0] else 'primary')),
        parent_email=str(row.get('parent_email') or ''), identity_id=str(row.get('identity_id') or ''),
        credential_ref=profile['credential_ref'], client_id=str(handoff.get('client_id') or ''))
    _CONTEXT_CACHE[address] = account
    return account


def original_handoff_acquisition(address: str, *, row=None, profile=None) -> str:
    """读取远端原归属，不把本地任务 acquisition 当作 Butler 的交接编号。"""
    if row and _cache_key(row.get('email')) == _cache_key(address):
        acquisition = (row.get('butler_handoff') or {}).get('acquisition_id')
        if acquisition:
            return str(acquisition)
    identity = (profile or {}).get('butler_identity') or {}
    if _cache_key(identity.get('email')) == _cache_key(address):
        return str(identity.get('acquisition_id') or '')
    return ''


def pick_local_account(*, owner_kind=None, owner_id=None, acquisition_id=None, batch_id=None, job_id=None) -> EmailButlerAccount:
    """只领取已手动导入的本地 Butler 邮箱。"""
    from core.email.inventory import claim

    row = claim("email_butler", owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id,
                batch_id=batch_id, job_id=job_id)
    if not row:
        raise EmailButlerClientError("local_email_inventory_empty: 本地 Butler 邮箱库存为空，请先手动导入")
    if row.get("_legacy_butler_intent"):
        return _account_from_legacy_intent(row["_legacy_butler_intent"])
    return restore_local_account(row)


def pick_account(*, owner_kind=None, owner_id=None, acquisition_id=None, batch_id=None, job_id=None) -> EmailButlerAccount:
    """兼容公共入口；新领取始终使用本地库存。"""
    return pick_local_account(owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id,
                              batch_id=batch_id, job_id=job_id)


def get_account_context(email: str) -> EmailButlerAccount | None:
    return _CONTEXT_CACHE.get(_cache_key(email))


def active_mailbox_leases() -> list[dict]:
    """返回当前 WebUI 进程持有的 Email Butler 租约，不包含 API Key。"""
    return [
        {
            "email": account.email,
            "mailbox_id": account.mailbox_id,
            "lease_id": account.lease_id,
            "leased_until": account.leased_until,
            "provider": account.provider,
            "mailbox_email": account.mailbox_email,
        }
        for account in sorted(_CONTEXT_CACHE.values(), key=lambda item: item.email.lower())
        if account.lease_id or account.mailbox_id
    ]


def restore_account_context(email: str, *, purpose: str = "live-check", api_base: str | None = None,
                            api_key: str | None = None) -> EmailButlerAccount:
    """HME 优先恢复原固定身份，其余邮箱沿用精确租约恢复。"""
    key = _cache_key(email)
    local = restore_local_account(email)
    if local:
        return local
    cached = _CONTEXT_CACHE.get(key)
    cache_matches = cached and (api_base is None or cached.api_base == api_base) and (api_key is None or cached.api_key == api_key)
    if cache_matches and cached.provider != "icloud_hme":
        return cached
    fixed = _restore_hme_context(email)
    if fixed:
        _CONTEXT_CACHE[key] = fixed
        return fixed
    if cache_matches:
        return cached
    from core.storage import records as record_store
    intents = record_store.list_rows(record_store.EMAIL_BUTLER_CLAIM_INTENTS,
        where="address_norm = %s AND status = %s", params=(key, "claimed"), order_by="id DESC", limit=1)
    if intents:
        return _account_from_legacy_intent(intents[0])
    raise EmailButlerIntentLocked("lease_restore_required: 缺少原完整邮箱的固定收件或已确认租约，不能重新申请邮箱")


def _outcome_for_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "succeeded", "registered", "used"}:
        return "succeeded"
    if normalized in {"failed", "disabled", "bad", "error"}:
        return "failed"
    return "abandoned"


def _hme_profile_key(email: str) -> str:
    return "butler-hme-identity:" + hashlib.sha256(_cache_key(email).encode()).hexdigest()


def _persist_hme_context(account: EmailButlerAccount) -> None:
    """完整 HME 身份使用独立固定 profile，密钥仅保存版本引用。"""
    from core.email.derivation import _save_profile_secret
    from core.storage.email import address_allocations as store

    try:
        if not account.acquisition_id:
            original = _restore_hme_context(account.email)
            if original:
                account.acquisition_id = original.acquisition_id
                account.api_base, account.api_key = original.api_base, original.api_key
                account.mailbox_email = original.mailbox_email
        base, key = _api_base(account.api_base), _api_key(account.api_key)
        identity = hashlib.sha256(f"butler:{base}:{account.mailbox_email}".encode()).hexdigest()
        version = hashlib.sha256(f"{identity}:{key}".encode()).hexdigest()
        reference = f"EMAIL_DERIVATION_BUTLER_SECRET_{version[:20].upper()}"
        _save_profile_secret(reference, key)
        store.create_inbox_profile(inbox_key=_hme_profile_key(account.email), connector="forward_butler",
            credential_ref=reference, inbox_locator={"api_base": base, "mailbox_email": account.mailbox_email},
            data={"require_recipient_evidence": True, "butler_identity": {
                "email": _cache_key(account.email), "provider": "icloud_hme", "acquisition_id": account.acquisition_id,
                "identity_type": account.identity_type, "parent_email": account.parent_email,
                "identity_id": account.identity_id}})
    except Exception as exc:
        raise EmailButlerClientError(f"email_derivation_profile_unavailable: HME 固定身份保存失败 ({type(exc).__name__})") from exc


def _restore_hme_context(email: str) -> EmailButlerAccount | None:
    """无进程缓存时只查精确身份 profile，不按共享最终邮箱猜测 provider。"""
    from core.email.derivation import _profile_credentials
    from core.storage.email import address_allocations as store

    profiles = store.list_inbox_profiles(inbox_key=_hme_profile_key(email))
    if not profiles:
        return None
    profile = profiles[0]
    identity = profile.get("butler_identity") or {}
    if (profile.get("state") != "active" or profile.get("connector") != "forward_butler"
            or identity.get("provider") != "icloud_hme" or identity.get("email") != _cache_key(email)):
        raise EmailButlerClientError("email_derivation_profile_unavailable: 原 HME 完整身份的固定配置不可用")
    connection = _profile_credentials(profile)
    return EmailButlerAccount(email=_cache_key(email), mailbox_id="", provider="icloud_hme",
        mailbox_email=connection["mailbox_email"], recipient_mode=_RECIPIENT_MODE, strict_family=True,
        api_base=connection["api_base"], api_key=connection["api_key"], acquisition_id=str(identity.get("acquisition_id") or ""),
        lease_id=str(identity.get("lease_id") or ""), credential_ref=profile["credential_ref"],
        client_id=str(identity.get("client_id") or ""),
        identity_type=str(identity.get("identity_type") or "primary"), parent_email=str(identity.get("parent_email") or ""),
        identity_id=str(identity.get("identity_id") or ""))


def report_hme_identity(account: EmailButlerAccount, *, status: str, note: str | None = None) -> None:
    """先持久化结果；网络失败由后台队列重试，不阻塞注册完成。"""
    state = str(status or "").strip().lower()
    if state in {"request_unknown", "unknown", "running", "reserved", "available"}:
        return
    from core.email.email_butler import usage_reports as email_usage_reports
    # Existing profiles win over a stale process cache and mutable global config.
    if email_usage_reports.enqueue(account.email, status=state, source="email_butler") is not None:
        return
    if email_usage_reports.has_success(account.email):
        return
    _persist_hme_context(account)
    email_usage_reports.enqueue(account.email, status=state, source="email_butler")


def _return_account_context(address: str) -> tuple[EmailButlerAccount | None, str]:
    """退号只读取原交接编号和固定连接，不申请或续租邮箱。"""
    from core.storage.email.local_imports import get_butler_email
    from core.storage import records as record_store
    from core.email.derivation import _profile_credentials

    row = get_butler_email(address)
    if row:
        profile_id = row.get('local_inbox_profile_id') or row.get('inbox_profile_id')
        profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(profile_id)) if profile_id else None
        if not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
            raise EmailButlerClientError('fixed_route_unavailable: 退号缺少原固定收件配置')
        connection = _profile_credentials(profile)
        identity = profile.get('butler_identity') or {}
        handoff = row.get('butler_handoff') or {}
        # 本地领取意图与 Butler 交接意图不同，必须使用已保存的远端交接编号。
        acquisition = str(handoff.get('acquisition_id') or identity.get('acquisition_id') or '')
        if not acquisition and not handoff.get('lease_id'):
            raise EmailButlerClientError('acquisition_required: 退号缺少原 Butler 交接编号')
        return EmailButlerAccount(email=address, mailbox_id='', provider=str(row.get('provider') or 'icloud_hme'),
            acquisition_id=acquisition, lease_id=str(handoff.get('lease_id') or ''),
            credential_ref=profile['credential_ref'], client_id=str(handoff.get('client_id') or ''),
            api_base=connection['api_base'], api_key=connection['api_key']), acquisition
    account = _restore_hme_context(address) or get_account_context(address)
    return account, str(account.acquisition_id or '') if account else ''


def return_account(email: str, service: str = 'openai', *, api_base: str | None = None,
                   api_key: str | None = None, acquisition_id: str = '', lease_id: str = '',
                   client_id: str = '') -> dict:
    """只结束原操作对应租约；失败交给持久出站队列沿原意图恢复。"""
    from core.email.email_butler import v2, lease_bindings
    address = _cache_key(email)
    if '@' not in address or service != 'openai':
        return {'ok': False, 'error_code': 'return_identity_invalid', 'reason': '退租地址或服务无效'}
    try:
        account = None
        if not acquisition_id and not lease_id:
            account, acquisition_id = _return_account_context(address)
            if account:
                api_base, api_key, lease_id = account.api_base, account.api_key, account.lease_id
        connection = {'api_base': _api_base(api_base), 'api_key': _api_key(api_key)}
        binding = lease_bindings.resolve(address, **connection, acquisition_id=acquisition_id,
            lease_id=lease_id, client_id=client_id or (account.client_id if account else ''),
            credential_ref=(account.credential_ref if account else ''), for_release=True)
        result = v2.release(binding['lease_id'], **connection, reason='Turb 显式删除未使用邮箱')
        if (_cache_key(result.get('email')) != address or result.get('service') != service
                or result.get('client_id') != binding['client_id']):
            raise v2.ButlerV2Error('lease_identity_mismatch', '退租回执未确认原地址及服务')
        lease_bindings.save(result, api_base=connection['api_base'], credential_ref=binding['credential_ref'],
                            client_id=binding['client_id'], acquisition_id=acquisition_id)
        _CONTEXT_CACHE.pop(address, None)
        return {'ok': True, 'email': address, 'service': service, 'lease_id': result['id'],
                'released': result['status'] == 'released' or result.get('already_inactive', False),
                'removed': int(result.get('service_tag_removed', False)), 'remaining': [],
                'service_tags': [], 'already_inactive': result.get('already_inactive', False)}
    except (v2.ButlerV2Error, EmailButlerClientError) as exc:
        return {'ok': False, 'error_code': exc.error_code or 'butler_return_unconfirmed',
                'reason': str(exc), 'retryable': getattr(exc, 'retryable', False),
                'request_unknown': getattr(exc, 'request_unknown', False), 'status_code': exc.status_code}


def release_account(email: str, status: str = 'available', note: str | None = None) -> None:
    """任务结果只更新本地业务事实；远端读取权保留到显式删除退租。"""
    from core.email.inventory import record_outcome
    if str(status or '').lower() in {'request_unknown', 'unknown', 'running', 'reserved'}:
        return
    if not record_outcome(email, source='email_butler', status=status, note=note):
        from core.email.email_butler import usage_reports
        usage_reports.enqueue(email, status=status, source='email_butler')
    if str(status or '').lower() != 'available':
        _CONTEXT_CACHE.pop(_cache_key(email), None)


def _message_otp(payload: dict) -> str | None:
    direct = str(payload.get("verification_code") or "").strip()
    if _OTP_RE.fullmatch(direct):
        return direct
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    for message in messages:
        if not isinstance(message, dict):
            continue
        direct = str(message.get("code") or "").strip()
        if _OTP_RE.fullmatch(direct):
            return direct
        item = {
            "from": message.get("from") or "",
            "subject": message.get("subject") or "",
            "text": message.get("body_text") or message.get("snippet") or "",
            "html": message.get("body_html") or "",
        }
        extracted = extract_otp(item)
        if extracted:
            return extracted
    return None


def _is_transient_inbound_error(exc: Exception) -> bool:
    message = str(exc or "")
    return any(marker in message for marker in _TRANSIENT_INBOUND_ERROR_MARKERS)


def _require_recipient_capability(api_base: str, api_key: str) -> None:
    """能力只缓存一分钟，并按固定地址和密钥身份隔离，缓存不持有密钥值。"""
    identity = (api_base, hashlib.sha256(api_key.encode()).hexdigest())
    now = time.monotonic()
    if _RECIPIENT_CAPABILITY_CACHE.get(identity, 0) > now:
        return
    try:
        payload = _request("GET", "/me", api_base=api_base, api_key=api_key)
    except EmailButlerClientError as exc:
        if re.search(r"HTTP (404|405)\b", str(exc)):
            raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 缺少能力声明接口", error_code="recipient_contract_unsupported") from exc
        raise
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or _RECIPIENT_CAPABILITY not in capabilities:
        raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 未声明严格收件证据能力", error_code="recipient_contract_unsupported")
    _RECIPIENT_CAPABILITY_CACHE[identity] = now + 60


def _validate_recipient_match(payload: dict, target: str, strict_family: bool, mailbox: str) -> None:
    """正负查询回执都必须声明原完整地址、族隔离和最终收件箱。"""
    if payload.get("recipient_mode") != _RECIPIENT_MODE or not isinstance(payload.get("recipient_match"), dict):
        raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 缺少严格收件回执", error_code="recipient_contract_unsupported")
    match = payload["recipient_match"]
    if _cache_key(match.get("email")) != target or match.get("strict_family") is not strict_family:
        raise EmailButlerClientError("recipient_mismatch: 严格收件回执的完整地址或族隔离标志不一致", error_code="recipient_mismatch")
    if _cache_key(match.get("mailbox_email")) != mailbox:
        raise EmailButlerClientError("mailbox_mismatch: 严格收件回执的最终收件箱不一致", error_code="mailbox_mismatch")


def _validate_recipient_receipt(payload: dict, target: str, strict_family: bool, mailbox: str) -> None:
    """候选邮件还必须有可唯一匹配完整原地址的投递证据。"""
    _validate_recipient_match(payload, target, strict_family, mailbox)
    evidence = payload.get("recipient_evidence")
    address_fields = ("original_recipients", "displayed_recipients", "forwarding_destinations", "received_for",
                      "hme_recipients", "conflicting_original_families")
    if (not isinstance(evidence, dict) or not any(evidence.get(field) for field in address_fields)
            or any(not isinstance(evidence.get(field, []), list)
                   or any(not isinstance(value, str) for value in evidence.get(field, [])) for field in address_fields)):
        raise EmailButlerClientError("recipient_evidence_missing: 严格收件回执缺少有效投递证据", error_code="recipient_evidence_missing")
    from core.email.recipients import candidate_match

    if not candidate_match(target, {"recipient_evidence": evidence}, forwarded=True, strict_family=strict_family):
        originals = {_cache_key(value) for value in evidence.get("original_recipients", [])}
        family = target.partition("@")[0].split("+", 1)[0] + "@" + target.partition("@")[2]

        def same_family(address: str) -> bool:
            return address.partition("@")[0].split("+", 1)[0] + "@" + address.partition("@")[2] == family

        displayed = {_cache_key(value) for value in evidence.get("displayed_recipients", []) if same_family(_cache_key(value))}
        # 严格母地址只有显示母地址时，无法排除被改写的子地址，统一归为歧义。
        ambiguous_parent = (strict_family and "+" not in target.partition("@")[0]
                            and not any(same_family(value) for value in originals) and displayed == {target})
        error_code = "recipient_ambiguous" if target in originals or ambiguous_parent else "recipient_mismatch"
        raise EmailButlerClientError(f"{error_code}: 原始收件证据无法唯一匹配完整地址", error_code=error_code)


def fetch_inbound_otp(email: str, after_ts: float | None = None, max_wait: int | None = None,
                      poll_interval: int | None = None, settle_seconds: int | None = None,
                      local_probe: Callable[[], str | None] | None = None, *,
                      require_recipient_evidence: bool = False, strict_family: bool = False,
                      mailbox_email: str | None = None, api_base: str | None = None,
                      api_key: str | None = None, acquisition_id: str = '',
                      lease_id: str = '', client_id: str = '', credential_ref: str = '') -> str:
    """通过原 v2 租约取码，保留完整地址、服务及挑战时间边界。"""
    target = _cache_key(email)
    cached = get_account_context(target)
    if (cached is not None and (api_base is None or cached.api_base == api_base)
            and (api_key is None or cached.api_key == api_key)):
        account = cached
    else:
        account = EmailButlerAccount(email=target, mailbox_id='', api_base=api_base, api_key=api_key,
            provider='icloud_hme', mailbox_email=_cache_key(mailbox_email), acquisition_id=acquisition_id)
    if acquisition_id:
        account.acquisition_id = acquisition_id
    if lease_id:
        account.lease_id = lease_id
    if client_id:
        account.client_id = client_id
    if credential_ref:
        account.credential_ref = credential_ref
    return _fetch_v2_otp(account, after_ts=after_ts, max_wait=max_wait, poll_interval=poll_interval)


def fetch_latest_otp(email: str, after_ts: float | None = None, max_wait: int | None = None,
                     poll_interval: int | None = None, settle_seconds: int | None = None) -> str:
    """所有 Butler Provider 均使用固定租约取码，不暴露物理收件箱。"""
    account = get_account_context(email) or restore_account_context(email)
    return _fetch_v2_otp(account, after_ts=after_ts, max_wait=max_wait, poll_interval=poll_interval)


def _v2_error(exc):
    error = EmailButlerClientError(str(exc), status_code=exc.status_code, error_code=exc.error_code)
    error.retryable = exc.retryable
    error.request_unknown = exc.request_unknown
    error.request_id = exc.request_id
    return error


def _fetch_v2_otp(account, *, after_ts=None, max_wait=None, poll_interval=None):
    from core.email.email_butler import v2, lease_bindings
    from core.auth.email_guard import observe_candidate, current_session
    connection = {'api_base': _api_base(account.api_base), 'api_key': _api_key(account.api_key)}
    try:
        binding = lease_bindings.resolve(account.email, **connection,
            credential_ref=account.credential_ref, acquisition_id=account.acquisition_id,
            lease_id=account.lease_id, client_id=account.client_id)
    except v2.ButlerV2Error as exc:
        raise _v2_error(exc) from exc
    account.lease_id, account.client_id = binding['lease_id'], binding['client_id']
    account.api_base = binding['api_base']
    _CONTEXT_CACHE[_cache_key(account.email)] = account
    wait_seconds = max(1, int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT))
    interval = max(0, int(poll_interval if poll_interval is not None else 1))
    anchor = float(after_ts) if after_ts is not None else time.time() - 30
    since = datetime.fromtimestamp(anchor, timezone.utc).isoformat().replace('+00:00', 'Z')
    session = current_session()
    cursor = dict((session.row if session else {}).get('cursor') or {})
    after_code_id = cursor.get('butler_v2_after_code_id')
    if cursor.get('butler_v2_lease_id') != binding['lease_id']:
        after_code_id = None
    deadline = time.monotonic() + wait_seconds
    last_code, last_error = 'inbound_code_timeout', '尚未收到当前时间窗口内的验证码'
    while time.monotonic() < deadline:
        cooperative_checkpoint()
        remaining = max(0, deadline - time.monotonic())
        chunk = min(20, int(cooperative_poll_limit(20)), int(remaining))
        try:
            result = v2.code(binding['lease_id'], **connection, since=since, after_code_id=after_code_id,
                wait_seconds=max(0, chunk), timeout=min(remaining + 1, max(_request_timeout(), chunk + 5)))
            cooperative_checkpoint()
            if result['service'] != 'openai' or result['lease_id'] != binding['lease_id']:
                raise v2.ButlerV2Error('lease_identity_mismatch', '验证码回执不属于原服务租约')
            if result['status'] == 'matched':
                if not _OTP_RE.fullmatch(result['verification_code']):
                    raise v2.ButlerV2Error('otp_format_invalid', 'OpenAI 验证码须为六位数字')
                received = datetime.fromisoformat(result['received_at'].replace('Z', '+00:00'))
                if received.timestamp() < anchor:
                    raise v2.ButlerV2Error('otp_before_challenge', '验证码邮件早于本次挑战')
                event = result['code_id']
                identity = hashlib.sha256(f"{binding['api_base']}:{binding['lease_id']}".encode()).hexdigest()[:24]
                # 记录 v2 的租约授权与邮件事件回执，不伪造旧 MIME 收件证据。
                observe_candidate(f'butler-v2:{identity}:{event}',
                    evidence={'contract': 'butler.v2.lease', 'recipient': _cache_key(account.email),
                              'lease_id': binding['lease_id'], 'service': 'openai',
                              'code_id': event, 'received_at': result['received_at']},
                    cursor={'inbox_key': identity, 'message_id': event, 'message_mapping': 'stable_id',
                            'butler_v2_lease_id': binding['lease_id'], 'butler_v2_after_code_id': event})
                return result['verification_code']
            last_code = 'inbound_code_ambiguous' if result['status'] == 'ambiguous' else 'inbound_code_timeout'
            last_error = ('同一挑战窗口存在多个投递候选，未任取验证码' if result['status'] == 'ambiguous'
                          else '尚未收到当前时间窗口内的验证码')
        except v2.ButlerV2Error as exc:
            if not exc.retryable:
                raise _v2_error(exc) from exc
            last_code, last_error = exc.error_code, str(exc)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            bounded_sleep(min(max(interval, .1), remaining))
    raise EmailButlerClientError(f'{last_code}: 等待 Email Butler 验证码超时；{last_error}', error_code=last_code)
