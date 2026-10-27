# -*- coding: utf-8 -*-
"""Email Butler `/v1` 通用邮箱 API 客户端。"""
from __future__ import annotations

from core.mailbox_wait import WAIT_INTERRUPTED, bounded_sleep, bounded_timeout
import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote

import requests

from config import email as _email_cfg
from core.otp_utils import extract_otp

logger = logging.getLogger(__name__)

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
        raise EmailButlerClientError("Email Butler API 地址未配置，请填写 /v1 根地址。")
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


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    timeout: int | float | None = None,
    retry_connection_error: bool = False,
) -> dict:
    attempts = 2 if retry_connection_error else 1
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(
                method,
                _api_base(api_base) + path,
                params=params,
                json=json,
                headers={
                    "Authorization": f"Bearer {_api_key(api_key)}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=bounded_timeout(timeout if timeout is not None else _request_timeout()),
            )
            break
        except requests.ConnectionError as exc:
            if attempt < attempts:
                logger.warning(
                    "[EmailButler] 连接瞬时中断，0.5s 后重试一次：path=%s error=%s",
                    path,
                    str(exc)[:180],
                )
                bounded_sleep(0.5)
                continue
            raise EmailButlerClientError(
                f"Email Butler 请求失败 ({path}): {type(exc).__name__}: {exc}"
            ) from exc
        except requests.RequestException as exc:
            raise EmailButlerClientError(
                f"Email Butler 请求失败 ({path}): {type(exc).__name__}: {exc}"
            ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise EmailButlerClientError(
            f"Email Butler 响应不是 JSON ({path}): HTTP {response.status_code}",
            status_code=response.status_code,
        ) from exc

    if response.status_code == 401:
        raise EmailButlerClientError("Email Butler API Key 非法、已停用或已轮换", status_code=401, error_code="invalid_key")
    if response.status_code >= 400:
        message = payload.get("message") if isinstance(payload, dict) else str(payload)
        error_code = str(payload.get("error_code") or "") if isinstance(payload, dict) else ""
        if path == "/identities/report" and response.status_code == 404 and not error_code:
            error_code = "icloud_identity_not_found"
        raise EmailButlerClientError(
            f"Email Butler 请求失败 ({path}): HTTP {response.status_code}; {error_code}; {str(message)[:220]}",
            status_code=response.status_code, error_code=error_code,
        )
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 200:
        raise EmailButlerClientError(f"Email Butler 响应异常 ({path}): {payload}")
    return payload


def test_connection(*, api_base: str | None = None, api_key: str | None = None) -> dict:
    """调用 `/me` 验证 URL、Key、客户端策略和必要能力。"""
    payload = _request("GET", "/me", api_base=api_base, api_key=api_key)
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), list) else []
    required = {
        "mailboxes.create",
        "mailboxes.messages",
        "mailboxes.release",
        "signals.scan",
        "inbound.code",
    }
    missing = sorted(required.difference(str(item) for item in capabilities))
    if missing:
        raise EmailButlerClientError(f"Email Butler 缺少必要能力: {', '.join(missing)}")
    return {
        "ok": True,
        "name": str(payload.get("name") or ""),
        "consumer": str(policy.get("consumer") or ""),
        "service": str(policy.get("service") or ""),
        "capabilities": capabilities,
    }


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
    """扫描一个 Butler 邮箱中的高置信度 OpenAI 封号通知。"""
    target = str(email or "").strip().lower()
    if not target or "@" not in target:
        raise EmailButlerClientError("待扫描邮箱地址无效")
    if not strict_family:
        context = get_account_context(target)
        if context is None:
            context = _restore_hme_context(target)
        if context is not None and context.provider == "icloud_hme":
            api_base, api_key = context.api_base, context.api_key
            mailbox_email, strict_family = context.mailbox_email, True
    mailbox = _cache_key(mailbox_email)
    request_data = _signal_request(lookback_days=lookback_days, strict_family=strict_family, mailbox_email=mailbox)
    request_data["email"] = target
    connection = {name: value for name, value in {"api_base": api_base, "api_key": api_key}.items() if value is not None}
    payload = _request(
        "POST",
        "/signals/scan",
        json=request_data,
        **connection,
        **({"timeout": max(_request_timeout(), 55)} if strict_family else {}),
        # 封号信号是只读查询，连接被网关瞬时断开时可安全重试一次。
        retry_connection_error=True,
    )
    return _signal_result(payload, target, strict_family=strict_family, mailbox_email=mailbox)


def scan_openai_deactivation_bulk(emails: list[str], *, lookback_days: int = 120,
                                 api_base: str | None = None, api_key: str | None = None,
                                 mailbox_email: str, strict_family: bool = True) -> dict[str, dict]:
    """同一固定 Butler 收件箱共享批量扫描；单个地址失败不抹去其他结果。"""
    targets = sorted({_cache_key(value) for value in emails})
    if any(not target.partition("@")[0] or not target.partition("@")[2] for target in targets):
        raise EmailButlerClientError("待扫描邮箱地址无效")
    mailbox = _cache_key(mailbox_email)
    data = _signal_request(lookback_days=lookback_days, strict_family=strict_family, mailbox_email=mailbox)
    connection = {name: value for name, value in {"api_base": api_base, "api_key": api_key}.items() if value is not None}
    results = {}
    for offset in range(0, len(targets), 5000):
        batch = targets[offset:offset + 5000]
        try:
            payload = _request("POST", "/signals/scan", json={**data, "emails": batch},
                **connection, timeout=max(_request_timeout(), 55), retry_connection_error=True)
            rows = payload.get("results")
            if not isinstance(rows, dict):
                raise EmailButlerClientError("signal_receipt_invalid: 批量信号扫描缺少逐地址结果")
        except EmailButlerClientError as exc:
            results.update({target: {"ok": False, "error": str(exc), "error_code": "signal_scan_failed"} for target in batch})
            continue
        for target in batch:
            item = rows.get(target)
            try:
                if not isinstance(item, dict):
                    raise EmailButlerClientError("signal_receipt_invalid: 批量信号扫描缺少该完整地址")
                results[target] = _signal_result(item, target, strict_family=strict_family, mailbox_email=mailbox)
            except EmailButlerClientError as exc:
                error_code = item.get("error_code") if isinstance(item, dict) else ""
                results[target] = {"ok": False, "error": str(exc),
                    "error_code": str(error_code or str(exc).partition(":")[0])}
    return results


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


def pick_account(*, owner_kind: str | None = None, owner_id=None, acquisition_id: str | None = None) -> EmailButlerAccount:
    """按 API Key 策略租用一个邮箱身份，并缓存租约上下文。"""
    intent = {}
    saved = None
    connection = {}
    if acquisition_id:
        if not owner_kind or owner_id is None:
            raise EmailButlerIntentLocked("email_derivation_identity_conflict: Butler 领取缺少完整业务意图")
        intent = {"owner_kind": str(owner_kind), "owner_id": str(owner_id), "acquisition_id": str(acquisition_id)}
        from core.storage import email_butler_claims as claims
        from core.email_derivation import _save_profile_secret, _profile_credentials

        saved = claims.get_intent(str(acquisition_id))
        if saved is None:
            base, key = _api_base(), _api_key()
            version = hashlib.sha256(f"{base}:{key}".encode()).hexdigest()
            reference = f"EMAIL_DERIVATION_BUTLER_SECRET_{version[:20].upper()}"
            try:
                _save_profile_secret(reference, key)
            except Exception as exc:
                raise EmailButlerClientError("email_derivation_profile_unavailable: Butler 领取前固定连接保存失败") from exc
        else:
            base, reference = saved['api_base'], saved['credential_ref']
        try:
            saved = claims.prepare(**intent, api_base=base, credential_ref=reference)
        except ValueError as exc:
            raise EmailButlerIntentLocked(str(exc)) from exc
        try:
            pinned = _profile_credentials({'connector':'forward_butler','credential_ref':saved['credential_ref'],
                'inbox_locator':{'api_base':saved['api_base']}, 'id':saved['id'], 'inbox_key':'butler-claim', 'revision':1})
        except Exception as exc:
            raise EmailButlerClaimUnknown("request_unknown: 原 Butler 领取连接不可用，已保留原意图") from exc
        connection = {'api_base':pinned['api_base'], 'api_key':pinned['api_key']}
    execution = None
    try:
        mailbox = None
        if saved and saved['status'] != 'claimed':
            # The capability at the original submission is part of the intent.
            # A later key policy change cannot make an old generic claim safe.
            try:
                capability = _request("GET", "/me", **connection)
                recovery_capable = "mailboxes.acquisition.v1" in capability.get("capabilities", [])
            except Exception as exc:
                if getattr(exc, "status_code", None) in {401, 403}:
                    raise
                recovery_capable = False
            first_submit, saved = claims.mark_submitting(str(acquisition_id), recovery_capable=recovery_capable)
            if first_submit:
                execution = saved['submission_execution']
            elif saved['status'] != 'claimed' and not (saved.get('acquisition_capable') and recovery_capable):
                raise EmailButlerClaimUnknown("request_unknown: 原 Butler 领取未具备可靠恢复能力，禁止重新发号")
        if saved and saved['status'] == 'claimed':
            mailbox = saved['mailbox']
            if mailbox.get('provider') != 'icloud_hme':
                try:
                    expiry = datetime.fromisoformat(str(mailbox.get('leased_until') or '').replace('Z', '+00:00'))
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    usable = expiry > datetime.now(timezone.utc)
                except (TypeError, ValueError):
                    usable = False
                if not usable:
                    raise EmailButlerIntentLocked('lease_restore_required: 原 Butler 普通邮箱租约已过期或无法确认，禁止改领新地址',
                        status_code=409, error_code='lease_restore_required')
        else:
            payload = _request("POST", "/mailboxes", json=intent, **connection)
            mailbox = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else {}
        email = str(mailbox.get("email") or "").strip()
        mailbox_id = str(mailbox.get("id") or "").strip()
        if not email or "@" not in email or not mailbox_id:
            raise EmailButlerClientError("Email Butler 发号响应缺少 mailbox.id/email")
        account = _mailbox_account(mailbox, **connection)
        account.acquisition_id = str(acquisition_id or "")
        if account.provider == "icloud_hme":
            _persist_hme_context(account)
        if saved:
            claims.record_result(str(acquisition_id), mailbox=mailbox)
    except Exception as exc:
        if saved:
            if getattr(exc, "definite_rejection", False):
                current = claims.record_result(str(acquisition_id), rejected=True, execution=execution)
                if current['status'] in {'submitting', 'request_unknown'}:
                    raise EmailButlerClaimUnknown('request_unknown: 先前 Butler 领取结果尚未明确，保留原意图') from exc
                raise
            claims.record_result(str(acquisition_id), unknown=True)
            raise EmailButlerClaimUnknown("request_unknown: Butler 领取结果待核验，请恢复原领取意图；" + str(exc)) from exc
        raise
    _CONTEXT_CACHE[_cache_key(email)] = account
    logger.info("[EmailButler] 已租用邮箱: %s provider=%s", email, account.provider or "?")
    return account


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
        if account.mailbox_id and (account.provider != "icloud_hme" or account.lease_id)
    ]


def restore_account_context(email: str, *, purpose: str = "live-check", api_base: str | None = None,
                            api_key: str | None = None) -> EmailButlerAccount:
    """HME 优先恢复原固定身份，其余邮箱沿用精确租约恢复。"""
    key = _cache_key(email)
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
    connection = {name: value for name, value in {"api_base": api_base, "api_key": api_key}.items() if value is not None}
    payload = _request(
        "POST",
        "/mailboxes",
        json={"requested_email": email, "purpose": purpose},
        **connection,
    )
    mailbox = payload.get("mailbox") if isinstance(payload.get("mailbox"), dict) else {}
    mailbox_id = str(mailbox.get("id") or "").strip()
    mailbox_email = str(mailbox.get("email") or "").strip()
    if not mailbox_id or not mailbox_email or "@" not in mailbox_email:
        raise EmailButlerClientError("Email Butler 按邮箱恢复上下文失败: " + email)
    if _cache_key(mailbox_email) != key:
        raise EmailButlerClientError("recipient_mismatch: Butler 恢复返回的完整邮箱与原身份不一致")
    account = _mailbox_account(mailbox, api_base=api_base, api_key=api_key)
    if account.provider == "icloud_hme":
        _persist_hme_context(account)
    _CONTEXT_CACHE[key] = account
    logger.info("[EmailButler] 已按邮箱恢复上下文: %s", email)
    return account


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
    from core.email_derivation import _save_profile_secret
    from core.storage import email_address_allocations as store

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
    from core.email_derivation import _profile_credentials
    from core.storage import email_address_allocations as store

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
        identity_type=str(identity.get("identity_type") or "primary"), parent_email=str(identity.get("parent_email") or ""),
        identity_id=str(identity.get("identity_id") or ""))


def report_hme_identity(account: EmailButlerAccount, *, status: str, note: str | None = None) -> None:
    """同一完整身份和归一化结果始终使用相同上报编号，可跨重启重试。"""
    state = str(status or "").strip().lower()
    if state in {"request_unknown", "unknown", "running", "reserved"}:
        return
    result = "ok" if state in {"used", "success", "succeeded", "registered"} else "disabled" if state in {"disabled", "retired"} else "provider_error"
    identity = account.acquisition_id or _cache_key(account.email)
    operation_id = hashlib.sha256(f"turb-hme:{identity}:{result}".encode()).hexdigest()
    _request("POST", "/identities/report", json={"email": _cache_key(account.email), "status": result,
        "service": "openai", "consumer": "turb-gpt-register", "message": str(note or "")[:300],
        "operation_id": operation_id}, api_base=account.api_base, api_key=account.api_key)


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    """HME 幂等上报后收口本地上下文，远端保留原 TTL；其他来源释放租约。"""
    key = _cache_key(email)
    if str(status or "").strip().lower() in {"request_unknown", "unknown", "running", "reserved"}:
        return
    account = _CONTEXT_CACHE.get(key)
    if not account:
        account = _restore_hme_context(email)
        if account:
            _CONTEXT_CACHE[key] = account
    if not account:
        logger.info("[EmailButler] 邮箱上下文已不存在，跳过释放: %s", email)
        return
    if account.provider == "icloud_hme":
        fixed = _restore_hme_context(email)
        if fixed:
            account = fixed
            _CONTEXT_CACHE[key] = fixed
        else:
            _persist_hme_context(account)
        report_hme_identity(account, status=status, note=note)
        _CONTEXT_CACHE.pop(key, None)
        logger.info("[EmailButler] 已报告 HME 完整身份结果: %s", email)
        return
    try:
        _request(
            "POST",
            f"/mailboxes/{quote(account.mailbox_id, safe='')}/release",
            json={"outcome": _outcome_for_status(status), "message": str(note or "")[:300]},
            **{name: value for name, value in {"api_base": account.api_base, "api_key": account.api_key}.items() if value is not None},
        )
    finally:
        _CONTEXT_CACHE.pop(key, None)
    logger.info("[EmailButler] 已释放邮箱: %s outcome=%s", email, _outcome_for_status(status))


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
            raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 缺少能力声明接口") from exc
        raise
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, list) or _RECIPIENT_CAPABILITY not in capabilities:
        raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 未声明严格收件证据能力")
    _RECIPIENT_CAPABILITY_CACHE[identity] = now + 60


def _validate_recipient_match(payload: dict, target: str, strict_family: bool, mailbox: str) -> None:
    """正负查询回执都必须声明原完整地址、族隔离和最终收件箱。"""
    if payload.get("recipient_mode") != _RECIPIENT_MODE or not isinstance(payload.get("recipient_match"), dict):
        raise EmailButlerClientError("recipient_contract_unsupported: Email Butler 缺少严格收件回执")
    match = payload["recipient_match"]
    if _cache_key(match.get("email")) != target or match.get("strict_family") is not strict_family:
        raise EmailButlerClientError("recipient_mismatch: 严格收件回执的完整地址或族隔离标志不一致")
    if _cache_key(match.get("mailbox_email")) != mailbox:
        raise EmailButlerClientError("mailbox_mismatch: 严格收件回执的最终收件箱不一致")


def _validate_recipient_receipt(payload: dict, target: str, strict_family: bool, mailbox: str) -> None:
    """候选邮件还必须有可唯一匹配完整原地址的投递证据。"""
    _validate_recipient_match(payload, target, strict_family, mailbox)
    evidence = payload.get("recipient_evidence")
    address_fields = ("original_recipients", "displayed_recipients", "forwarding_destinations", "received_for",
                      "hme_recipients", "conflicting_original_families")
    if (not isinstance(evidence, dict) or not any(evidence.get(field) for field in address_fields)
            or any(not isinstance(evidence.get(field, []), list)
                   or any(not isinstance(value, str) for value in evidence.get(field, [])) for field in address_fields)):
        raise EmailButlerClientError("recipient_evidence_missing: 严格收件回执缺少有效投递证据")
    from core.email_recipients import candidate_match

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
        raise EmailButlerClientError(f"{error_code}: 原始收件证据无法唯一匹配完整地址")


def fetch_inbound_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
    local_probe: Callable[[], str | None] | None = None,
    *,
    require_recipient_evidence: bool = False,
    strict_family: bool = False,
    mailbox_email: str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
) -> str:
    """Wait on Email Butler's PG-backed forwarded-mail cache.

    The server performs one initial exact query and then waits on PostgreSQL
    LISTEN/NOTIFY. Long waits are split into gateway-safe chunks because the
    public endpoint can be behind Cloudflare, whose timeout is shorter than the
    configured OTP wait. Every chunk uses the same ``since`` anchor, so a
    notification received between requests is found by the next exact query.
    Callers that own the forwarding mailbox may also provide ``local_probe``.
    Email Butler remains the primary source; after each remote miss or
    transient failure the local mailbox is probed once before the next remote
    wait. The probe only loops for the lifetime of this OTP wait and never
    becomes a process-wide mailbox scanner.
    """
    target = _cache_key(email)
    if "@" not in target:
        raise EmailButlerClientError("待查询的转发邮箱地址无效")
    strict = bool(require_recipient_evidence or strict_family or "+" in target.partition("@")[0])
    mailbox = _cache_key(mailbox_email)
    connection = {}
    if strict:
        if not mailbox.partition("@")[0] or not mailbox.partition("@")[2]:
            raise EmailButlerClientError("mailbox_mismatch: 严格取码必须指定最终收件箱")
        connection = {"api_base": _api_base(api_base), "api_key": _api_key(api_key)}
        _require_recipient_capability(**connection)
        local_probe = None
    else:
        if api_base is not None:
            connection["api_base"] = api_base
        if api_key is not None:
            connection["api_key"] = api_key
    wait_seconds = max(
        1,
        int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT),
    )
    anchor = float(after_ts if after_ts is not None else time.time())
    if not strict or after_ts is None:
        anchor -= 30
    since = datetime.fromtimestamp(anchor, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    interval = max(0, int(poll_interval if poll_interval is not None else 1))
    logger.info("[EmailButler] 等待 PG 入站验证码：%s，最长 %ss", target, wait_seconds)
    started = time.monotonic()
    deadline = started + wait_seconds
    last_error = "尚未收到新的 OpenAI 验证码邮件"
    chunk_index = 0
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        # 有本机探测时缩短远端等待段，避免邮件已到 Gmail 但尚未入 PG 时
        # 仍被一个长请求挡住很久；纯远端模式继续使用 75 秒网关安全段。
        chunk_limit = 15 if local_probe is not None else _INBOUND_WAIT_CHUNK_SECONDS
        chunk_seconds = max(1, min(chunk_limit, int(math.ceil(remaining))))
        chunk_index += 1
        try:
            request_data = {"email": target, "since": since, "timeout_seconds": chunk_seconds}
            if strict:
                request_data.update(recipient_mode=_RECIPIENT_MODE, strict_family=bool(strict_family), mailbox_email=mailbox)
            payload = _request(
                "POST",
                "/inbound/code",
                json=request_data,
                **connection,
                timeout=max(_request_timeout(), chunk_seconds + 10),
                # 等待入站通知是只读、幂等操作；Oracle/Nginx 偶发在建连阶段断开时，
                # 立即重连一次即可继续等待，不需要重新扫描 Gmail。
                retry_connection_error=True,
            )
            otp = _message_otp(payload)
            if otp:
                if strict:
                    _validate_recipient_receipt(payload, target, bool(strict_family), mailbox)
                    from core.email_auth_guard import observe_candidate

                    message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
                    message_id = str(payload.get("message_id") or message.get("id") or message.get("message_id") or "").strip()
                    identity = hashlib.sha256(f"{connection['api_base']}:{mailbox}".encode()).hexdigest()[:24]
                    observe_candidate(f"butler:{identity}:{message_id}" if message_id else "",
                        evidence=payload["recipient_evidence"],
                        cursor={"inbox_key": identity, "message_id": message_id,
                            "message_mapping": "stable_id" if message_id else "unknown"})
                elapsed = time.monotonic() - started
                logger.info("[EmailButler] 已从 PG 入站缓存取得 OTP，接口等待 %.1fs", elapsed)
                return otp
            last_error = "; ".join(str(payload.get(key) or "") for key in ("error_code", "message")).strip("; ") or "inbound_code_timeout: PG 入站等待结束但没有 OTP"
        except EmailButlerClientError as exc:
            if not _is_transient_inbound_error(exc):
                raise
            last_error = str(exc)
            logger.warning(
                "[EmailButler] PG 入站等待第 %s 段瞬时失败，继续剩余等待：%s",
                chunk_index,
                str(exc)[:220],
            )

        # 接口优先。只有这一段没有拿到验证码时才探测本地转发邮箱；下一轮
        # 仍会先请求接口，因此 Butler 恢复或 PG 完成入库后会回到主链路。
        if local_probe is not None:
            try:
                local_otp = str(local_probe() or "").strip()
            except WAIT_INTERRUPTED:
                raise
            except Exception as exc:
                logger.warning(
                    "[EmailButler] 本机收件兜底探测失败，继续等待 PG：%s: %s",
                    type(exc).__name__,
                    str(exc)[:180],
                )
            else:
                if _OTP_RE.fullmatch(local_otp):
                    elapsed = time.monotonic() - started
                    logger.info("[EmailButler] 接口未命中，已从本机收件兜底取得 OTP，等待 %.1fs", elapsed)
                    return local_otp

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        if interval:
            bounded_sleep(min(interval, remaining))

    elapsed = time.monotonic() - started
    logger.warning("[EmailButler] PG 入站等待结束但没有 OTP，累计等待 %.1fs", elapsed)
    raise EmailButlerClientError(
        f"等待 Email Butler 入站验证码超时（>{wait_seconds}s）：{target}; {last_error}"
    )


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    """轮询 Butler `/messages`，返回当前租约内最新 OpenAI 六位验证码。"""
    account = get_account_context(email)
    if not account:
        try:
            account = restore_account_context(email)
        except EmailButlerClientError as exc:
            raise EmailButlerClientError(f"Email Butler 邮箱租约上下文恢复失败: {email}; {exc}") from exc

    if account.provider == "icloud_hme":
        return fetch_inbound_otp(
            email, after_ts=after_ts, max_wait=max_wait, poll_interval=poll_interval, settle_seconds=settle_seconds,
            require_recipient_evidence=True, strict_family=True, mailbox_email=account.mailbox_email,
            api_base=account.api_base, api_key=account.api_key,
        )

    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    deadline = time.monotonic() + max(0, wait_seconds)
    since = ""
    if after_ts is not None:
        since = datetime.fromtimestamp(float(after_ts) - 30, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    best_otp: str | None = None
    settle_until: float | None = None
    last_error = "尚未收到验证码"
    logger.info("[EmailButler] 开始轮询邮箱 %s，最长 %ss", email, wait_seconds)
    while time.monotonic() <= deadline:
        remaining = max(1, int(deadline - time.monotonic()))
        params = {"timeout_seconds": min(3, remaining), "interval_seconds": 1}
        if since:
            params["since"] = since
        try:
            payload = _request(
                "GET",
                f"/mailboxes/{quote(account.mailbox_id, safe='')}/messages",
                params=params,
                **{name: value for name, value in {"api_base": account.api_base, "api_key": account.api_key}.items() if value is not None},
            )
            otp = _message_otp(payload)
            if otp and otp != best_otp:
                best_otp = otp
                settle_until = time.monotonic() + settle
                logger.info("[EmailButler] 锁定 OTP 候选，等待 %ss 确认", settle)
            if best_otp and settle_until is not None and time.monotonic() >= settle_until:
                return best_otp
        except EmailButlerClientError as exc:
            last_error = str(exc)

        remaining_float = deadline - time.monotonic()
        if remaining_float <= 0:
            break
        bounded_sleep(min(interval, remaining_float))

    if best_otp:
        return best_otp
    raise EmailButlerClientError(f"等待 Email Butler 验证码超时: {email}; {last_error}")
