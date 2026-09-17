# -*- coding: utf-8 -*-
"""iCloud Hide My Email sidecar 客户端。

依赖本机 icloud-hme 服务完成：
  - 同步/创建 Hide My Email 别名
  - iCloud 直收走 sidecar；Gmail 转发可走本机 IMAP 或 Email Butler PG

turb 只保存别名领取状态，不保存 Apple Cookie 或 App 专用密码。
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from config import email as _email_cfg
from core.otp_utils import extract_otp, looks_like_openai_email

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.trust_env = False
_SYNC_LOCK = threading.Lock()
_LAST_SYNC_AT = 0.0
_LAST_SYNC_KEY = ""
_LAST_ACCOUNT_ID = ""
_LAST_SYNC_RESULT: dict = {}


class ICloudHMEError(RuntimeError):
    """iCloud HME sidecar 请求或收码错误。"""


@dataclass
class ICloudHMEAccount:
    email: str
    account_id: str
    anonymous_id: str = ""
    label: str = ""
    forward_to_email: str = ""


def _cfg_str(name: str, default: str = "") -> str:
    return str(getattr(_email_cfg, name, default) or default).strip()


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(getattr(_email_cfg, name, default) or default)
    except (TypeError, ValueError):
        return default


def _cfg_bool(name: str, default: bool = False) -> bool:
    return bool(getattr(_email_cfg, name, default))


def _forward_domain(value: str | None) -> str:
    text = str(value or "").strip().lower()
    return text.rsplit("@", 1)[-1] if "@" in text else ""


def _is_icloud_mailbox(value: str | None) -> bool:
    return _forward_domain(value) in {"icloud.com", "me.com", "mac.com"}


def _inbox_mode() -> str:
    value = _cfg_str("ICLOUD_HME_INBOX_MODE", "sidecar").lower()
    return value if value in {"sidecar", "forward_imap", "forward_butler"} else "sidecar"


def _prepare_imap_aliases(
    aliases: list[dict],
    *,
    inbox_mode: str | None = None,
    forward_imap_email: str | None = None,
) -> tuple[list[dict], dict]:
    """按实际收件模式准备 HME 别名。

    ``forward_imap`` 使用当前配置的 Gmail 凭据读取收件箱，因此 Apple 返回的
    ``forwardToEmail`` 必须与该 Gmail 完全一致。不同 Apple 账号可以保留在同一
    池中，但只有路由匹配的别名才允许被领取。

    ``sidecar`` 仍拒绝明确转发到外部邮箱，因为 sidecar 只能读取 iCloud IMAP；
    ``forward_butler`` 保持原有的直接目标校验。
    """
    prepared: list[dict] = []
    known_domains: set[str] = set()
    incompatible = 0
    usable = 0
    mode = str(inbox_mode or _inbox_mode()).strip().lower()
    expected_forward = str(
        forward_imap_email
        if forward_imap_email is not None
        else _cfg_str("ICLOUD_HME_FORWARD_IMAP_EMAIL")
    ).strip().lower()
    for item in aliases:
        row = dict(item)
        forward = str(row.get("forwardToEmail") or row.get("forward_to_email") or "").strip()
        domain = _forward_domain(forward)
        if domain:
            known_domains.add(domain)
        if mode == "forward_imap":
            # The local IMAP credentials identify one mailbox. Do not claim an
            # alias whose Apple-side route points at another mailbox; a local
            # IMAP connection can be healthy while that alias is unreachable.
            compatible = bool(forward and expected_forward and forward.lower() == expected_forward)
        elif mode == "forward_butler":
            compatible = bool(forward and expected_forward and forward.lower() == expected_forward)
        else:
            compatible = not forward or _is_icloud_mailbox(forward)
        if not compatible:
            row["active"] = False
            incompatible += 1
        elif row.get("active", True):
            usable += 1
        prepared.append(row)
    return prepared, {
        "forward_domains": sorted(known_domains),
        "forward_incompatible": incompatible,
        "remote_usable": usable,
        "inbox_mode": mode,
    }


def _normalize_base(value: str | None = None) -> str:
    base = str(value or _cfg_str("ICLOUD_HME_API_BASE", "http://127.0.0.1:8081")).strip()
    if not base:
        raise ICloudHMEError("iCloud HME API 地址未配置")
    if not base.lower().startswith(("http://", "https://")):
        base = "http://" + base
    return base.rstrip("/")


def _timeout(value: int | None = None) -> int:
    return max(3, int(value if value is not None else _cfg_int("ICLOUD_HME_REQUEST_TIMEOUT", 35)))


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = _cfg_str("ICLOUD_HME_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-API-Token"] = token
    return headers


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    api_base: str | None = None,
    timeout: int | None = None,
) -> Any:
    url = _normalize_base(api_base) + "/" + str(path or "").lstrip("/")
    try:
        response = _SESSION.request(
            method.upper(),
            url,
            headers=_headers(),
            params=params,
            json=json_body,
            timeout=_timeout(timeout),
        )
    except requests.RequestException as exc:
        raise ICloudHMEError(f"无法连接 iCloud HME 服务: {type(exc).__name__}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ICloudHMEError(
            f"iCloud HME 返回非 JSON 响应: HTTP {response.status_code}; {(response.text or '')[:180]}"
        ) from exc

    success = isinstance(payload, dict) and payload.get("success") is True
    if response.status_code >= 400 or not success:
        message = payload.get("message") if isinstance(payload, dict) else ""
        raise ICloudHMEError(
            f"iCloud HME 请求失败 ({path}): HTTP {response.status_code}; {message or str(payload)[:180]}"
        )
    return payload.get("data")


def list_accounts(*, api_base: str | None = None, timeout: int | None = None) -> list[dict]:
    data = _request("GET", "/api/accounts", api_base=api_base, timeout=timeout)
    return [item for item in (data or []) if isinstance(item, dict)]


def resolve_account_id(
    account_id: str | None = None,
    *,
    api_base: str | None = None,
    timeout: int | None = None,
) -> str:
    configured = str(account_id or _cfg_str("ICLOUD_HME_ACCOUNT_ID")).strip()
    accounts = list_accounts(api_base=api_base, timeout=timeout)
    if configured:
        if not any(str(item.get("id") or "") == configured for item in accounts):
            raise ICloudHMEError(f"iCloud HME 账号不存在: {configured}")
        return configured
    active = [item for item in accounts if str(item.get("status") or "").lower() == "active"]
    selected = active[0] if active else (accounts[0] if accounts else None)
    if not selected or not selected.get("id"):
        raise ICloudHMEError("iCloud HME 服务中没有可用账号")
    return str(selected["id"])


def select_accounts(
    account_id: str | None = None,
    *,
    api_base: str | None = None,
    timeout: int | None = None,
) -> list[dict]:
    """返回固定模式下的一个账号，或动态模式下的所有 active 账号。"""
    configured = str(account_id or _cfg_str("ICLOUD_HME_ACCOUNT_ID")).strip()
    accounts = list_accounts(api_base=api_base, timeout=timeout)
    if configured:
        selected = next(
            (item for item in accounts if str(item.get("id") or "") == configured),
            None,
        )
        if selected is None:
            raise ICloudHMEError(f"iCloud HME 账号不存在: {configured}")
        return [selected]

    active = [
        item for item in accounts
        if str(item.get("status") or "").strip().lower() == "active" and item.get("id")
    ]
    active.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")))
    if not active:
        raise ICloudHMEError("iCloud HME 服务中没有可用 active 账号")
    return active


def list_aliases(
    account_id: str | None = None,
    *,
    api_base: str | None = None,
    timeout: int | None = None,
) -> tuple[str, list[dict]]:
    selected = resolve_account_id(account_id, api_base=api_base, timeout=timeout)
    data = _request(
        "GET",
        "/api/aliases",
        params={"account_id": selected},
        api_base=api_base,
        timeout=timeout,
    ) or {}
    aliases = data.get("aliases") if isinstance(data, dict) else []
    return selected, [item for item in (aliases or []) if isinstance(item, dict)]


def sync_aliases(
    *,
    force: bool = False,
    account_id: str | None = None,
    api_base: str | None = None,
    timeout: int | None = None,
) -> dict:
    """按 TTL 将一个或多个 Apple 侧别名集合同步到本地领取池。"""
    global _LAST_SYNC_AT, _LAST_SYNC_KEY, _LAST_ACCOUNT_ID, _LAST_SYNC_RESULT
    base = _normalize_base(api_base)
    ttl = max(0, _cfg_int("ICLOUD_HME_SYNC_TTL", 300))

    with _SYNC_LOCK:
        selected_accounts = select_accounts(account_id, api_base=base, timeout=timeout)
        account_ids = [str(item.get("id") or "").strip() for item in selected_accounts]
        sync_key = (
            f"{base}|{','.join(account_ids)}|{_inbox_mode()}|"
            f"{_cfg_str('ICLOUD_HME_FORWARD_IMAP_EMAIL').lower()}"
        )
        now = time.monotonic()
        if not force and _LAST_SYNC_KEY == sync_key and now - _LAST_SYNC_AT < ttl and _LAST_SYNC_RESULT:
            cached = dict(_LAST_SYNC_RESULT)
            cached["cached"] = True
            return cached

        from core import db
        account_results: list[dict] = []
        account_errors: list[dict] = []
        synced_account_ids: list[str] = []
        remote_count = remote_active = remote_usable = 0
        inserted = updated = disabled = 0
        routing_domains: set[str] = set()
        routing_incompatible = 0
        for account in selected_accounts:
            selected = str(account.get("id") or "").strip()
            try:
                data = _request(
                    "GET",
                    "/api/aliases",
                    params={"account_id": selected},
                    api_base=base,
                    timeout=timeout,
                ) or {}
                aliases = data.get("aliases") if isinstance(data, dict) else []
                aliases = [item for item in (aliases or []) if isinstance(item, dict)]
                prepared, routing = _prepare_imap_aliases(aliases)
                sync = db.sync_icloud_hide_aliases(prepared, selected, full_snapshot=True)
                synced_account_ids.append(selected)
                remote_count += len(aliases)
                remote_active += sum(1 for item in aliases if item.get("active", True))
                remote_usable += int(routing.get("remote_usable") or 0)
                routing_domains.update(routing.get("forward_domains") or [])
                routing_incompatible += int(routing.get("forward_incompatible") or 0)
                inserted += int(sync.get("inserted") or 0)
                updated += int(sync.get("updated") or 0)
                disabled += int(sync.get("disabled") or 0)
                account_results.append({
                    "account_id": selected,
                    "name": str(account.get("name") or ""),
                    "status": str(account.get("status") or ""),
                    "remote_aliases": len(aliases),
                    "remote_active": sum(1 for item in aliases if item.get("active", True)),
                    "remote_usable": int(routing.get("remote_usable") or 0),
                    "sync": sync,
                })
            except Exception as exc:
                account_errors.append({
                    "account_id": selected,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                })

        if not synced_account_ids and account_errors:
            details = "; ".join(
                f"{item['account_id']}: {item['error']}" for item in account_errors
            )
            raise ICloudHMEError(f"iCloud HME 所有账号同步失败: {details[:500]}")

        grouped = db.icloud_hide_email_pool_summary_by_account(synced_account_ids)
        result = {
            "inserted": inserted,
            "updated": updated,
            "disabled": disabled,
            "total": db.icloud_hide_email_pool_summary().get("total", 0),
            "cached": False,
            "account_id": account_ids[0] if account_ids else "",
            "account_ids": account_ids,
            "synced_account_ids": synced_account_ids,
            "accounts": account_results,
            "account_errors": account_errors,
            "remote_count": remote_count,
            "remote_active": remote_active,
            "remote_usable": remote_usable,
            "forward_domains": sorted(routing_domains),
            "forward_incompatible": routing_incompatible,
            "inbox_mode": _inbox_mode(),
            "pool": db.icloud_hide_email_pool_summary(),
            "pool_by_account": grouped,
        }
        _LAST_SYNC_AT = time.monotonic()
        _LAST_SYNC_KEY = sync_key
        _LAST_ACCOUNT_ID = account_ids[0] if account_ids else ""
        _LAST_SYNC_RESULT = dict(result)
        return result


def create_address(label: str | None = None, account_id: str | None = None) -> ICloudHMEAccount:
    selected = resolve_account_id(account_id)
    prefix = _cfg_str("ICLOUD_HME_CREATE_LABEL_PREFIX", "turb") or "turb"
    create_label = str(label or f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}").strip()
    data = _request(
        "POST",
        "/api/create",
        json_body={"account_id": selected, "label": create_label},
        timeout=max(_timeout(), 45),
    ) or {}
    email = str(data.get("email") or "").strip()
    if not email:
        raise ICloudHMEError("iCloud HME 创建成功响应中缺少邮箱地址")
    remote = {
        "email": email,
        "label": data.get("label") or create_label,
        "forwardToEmail": data.get("forwardToEmail") or data.get("forward_to_email") or "",
        "createdAt": data.get("created_at") or "",
        "active": True,
    }
    from core import db
    prepared, _routing = _prepare_imap_aliases([remote])
    db.sync_icloud_hide_aliases(prepared, selected, full_snapshot=False)
    return ICloudHMEAccount(
        email=email,
        account_id=selected,
        label=str(remote["label"]),
        forward_to_email=str(remote.get("forwardToEmail") or ""),
    )


def pick_account() -> ICloudHMEAccount:
    from core import db

    synced = sync_aliases(force=False)
    selected = str(synced.get("account_id") or _cfg_str("ICLOUD_HME_ACCOUNT_ID") or "").strip()
    selected_ids = [str(value).strip() for value in synced.get("synced_account_ids") or [] if str(value).strip()]
    row = db.claim_next_icloud_hide_email(account_ids=selected_ids or None)
    if row is None:
        synced = sync_aliases(force=True)
        selected = str(synced.get("account_id") or selected).strip()
        selected_ids = [str(value).strip() for value in synced.get("synced_account_ids") or [] if str(value).strip()]
        row = db.claim_next_icloud_hide_email(account_ids=selected_ids or None)
    if row is None and _cfg_bool("ICLOUD_HME_AUTO_CREATE", False):
        for candidate_id in selected_ids:
            try:
                create_address(account_id=candidate_id)
            except Exception as exc:
                logger.warning("[iCloud HME] 账号 %s 按需创建失败: %s", candidate_id, exc)
                continue
            row = db.claim_next_icloud_hide_email(account_id=candidate_id)
            if row is not None:
                break
    if row is None:
        raise ICloudHMEError(
            "iCloud 隐藏邮箱池没有可用地址。请在配置页点击“连接并同步”；如库存确实为空，可开启自动创建。"
        )
    return ICloudHMEAccount(
        email=str(row.get("email") or ""),
        account_id=str(row.get("account_id") or selected),
        anonymous_id=str(row.get("anonymous_id") or ""),
        label=str(row.get("label") or ""),
        forward_to_email=str(row.get("forward_to_email") or ""),
    )


def get_account_context(email: str) -> ICloudHMEAccount | None:
    from core import db
    row = db.get_icloud_hide_email_by_email(email)
    if not row:
        return None
    return ICloudHMEAccount(
        email=str(row.get("email") or ""),
        account_id=str(row.get("account_id") or ""),
        anonymous_id=str(row.get("anonymous_id") or ""),
        label=str(row.get("label") or ""),
        forward_to_email=str(row.get("forward_to_email") or ""),
    )


def _validate_forward_route(email: str) -> None:
    """Fail before OTP polling when a persisted HME route cannot reach IMAP."""
    if _inbox_mode() not in {"forward_imap", "forward_butler"}:
        return
    context = get_account_context(str(email or "").strip())
    if context is None:
        return
    actual = str(context.forward_to_email or "").strip().lower()
    expected = _cfg_str("ICLOUD_HME_FORWARD_IMAP_EMAIL").lower()
    if actual and expected and actual != expected:
        raise ICloudHMEError(
            "隐藏邮箱转发目标与当前 IMAP 收件账号不一致；请重新同步 HME 别名，"
            "或为该 Apple 账号配置对应的转发收件箱"
        )


def release_account(email: str, status: str = "available", note: str | None = None) -> None:
    from core import db
    db.release_icloud_hide_email(email, status=status, note=note)


def _message_timestamp(item: dict) -> float:
    raw = str(item.get("date") or item.get("receivedDateTime") or "").strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _otp_probe(item: dict) -> dict:
    preview = str(item.get("preview") or item.get("body") or "")
    return {
        "id": item.get("id"),
        "from": item.get("from") or "",
        "to": item.get("to") or "",
        "subject": item.get("subject") or "",
        "text": preview,
        "bodyPreview": preview,
        "date": item.get("date") or "",
    }


def fetch_latest_otp(
    email: str,
    after_ts: float | None = None,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
) -> str:
    if _inbox_mode() in {"forward_imap", "forward_butler"}:
        _validate_forward_route(email)
        from core.forward_imap_client import fetch_latest_otp as fetch_forwarded_otp
        return fetch_forwarded_otp(
            email,
            after_ts=after_ts,
            max_wait=max_wait,
            poll_interval=poll_interval,
            settle_seconds=settle_seconds,
        )

    target = str(email or "").strip()
    context = get_account_context(target)
    if context is None or not context.account_id:
        raise ICloudHMEError(f"iCloud 隐藏邮箱上下文缺失: {target}")

    wait_seconds = int(max_wait if max_wait is not None else _email_cfg.OTP_MAX_WAIT)
    interval = max(1, int(poll_interval if poll_interval is not None else _email_cfg.OTP_POLL_INTERVAL))
    settle = max(0, int(settle_seconds if settle_seconds is not None else _email_cfg.OTP_SETTLE_SECONDS))
    after = float(after_ts if after_ts is not None else time.time()) - 30
    deadline = time.monotonic() + max(0, wait_seconds)
    best_otp: str | None = None
    best_ts = float("-inf")
    settle_until: float | None = None
    last_error = "尚未收到新的 OpenAI 验证码邮件"

    logger.info("[iCloud HME] 开始轮询 %s，最长 %ss", target, wait_seconds)
    while time.monotonic() < deadline:
        try:
            data = _request(
                "GET",
                "/api/inbox",
                params={
                    "account_id": context.account_id,
                    "alias": target,
                    "limit": 20,
                    "days": 1,
                },
                timeout=max(_timeout(), 40),
            ) or {}
            method = str(data.get("method") or "")
            if method and method != "imap":
                last_error = f"收件当前使用 {method}，建议检查 App 专用密码"
            messages = data.get("messages") if isinstance(data, dict) else []
        except ICloudHMEError as exc:
            last_error = str(exc)
            logger.warning("[iCloud HME] 拉取邮件失败: %s", exc)
            time.sleep(interval)
            continue

        ordered = sorted(
            [item for item in (messages or []) if isinstance(item, dict)],
            key=_message_timestamp,
            reverse=True,
        )
        for item in ordered:
            ts = _message_timestamp(item)
            if ts and ts < after:
                continue
            to_field = str(item.get("to") or "").lower()
            if to_field and target.lower() not in to_field:
                continue
            probe = _otp_probe(item)
            if not looks_like_openai_email(probe):
                continue
            otp = extract_otp(probe)
            if not otp:
                continue
            score_ts = ts or time.time()
            if score_ts > best_ts:
                best_otp = otp
                best_ts = score_ts
                settle_until = time.monotonic() + settle
            break

        if best_otp and settle_until is not None and time.monotonic() >= settle_until:
            logger.info("[iCloud HME] 已取得 OTP: %s", target)
            return best_otp
        time.sleep(interval)

    if best_otp:
        return best_otp
    raise ICloudHMEError(f"等待 {target} 的 OTP 超时（>{wait_seconds}s）：{last_error}")


def test_connection(
    *,
    api_base: str | None = None,
    account_id: str | None = None,
    timeout: int | None = None,
) -> dict:
    """WebUI 使用：检查账号、同步别名，并确认收件是否走 IMAP。"""
    from core import db
    sync = sync_aliases(force=True, account_id=account_id, api_base=api_base, timeout=timeout)
    selected_ids = [
        str(value).strip() for value in sync.get("synced_account_ids") or sync.get("account_ids") or []
        if str(value).strip()
    ]
    selected = selected_ids[0] if selected_ids else str(sync.get("account_id") or "").strip()
    mode = _inbox_mode()
    if mode == "forward_imap":
        from core.forward_imap_client import test_local_connection
        inbox = test_local_connection()
    elif mode == "forward_butler":
        from core.forward_imap_client import test_connection as test_forward_imap
        inbox = test_forward_imap()
    else:
        inbox = _request(
            "GET",
            "/api/inbox",
            params={"account_id": selected, "limit": 1, "days": 1},
            api_base=_normalize_base(api_base),
            timeout=max(_timeout(timeout), 40),
        ) or {}
    routing = {
        "forward_domains": sync.get("forward_domains") or [],
        "forward_incompatible": int(sync.get("forward_incompatible") or 0),
        "remote_usable": int(sync.get("remote_usable") or 0),
        "inbox_mode": sync.get("inbox_mode") or mode,
    }
    if routing["forward_incompatible"] and not routing["remote_usable"]:
        domains = ", ".join(routing["forward_domains"]) or "非 iCloud 邮箱"
        if mode in {"forward_imap", "forward_butler"}:
            raise ICloudHMEError(
                f"隐藏邮箱实际转发到 {domains}，与配置的转发目标邮箱不一致；"
                "请确认 Gmail 地址后重新同步"
            )
        raise ICloudHMEError(
            f"隐藏邮箱当前转发到 {domains}，但 sidecar 读取的是 iCloud IMAP；"
            "可改为 iCloud 转发，或把收件模式设为 forward_imap 并配置本机 Gmail IMAP"
        )
    return {
        "account_id": selected,
        "account_ids": sync.get("account_ids") or selected_ids,
        "remote_aliases": int(sync.get("remote_count") or 0),
        "remote_active": int(sync.get("remote_active") or 0),
        "inbox_method": str(inbox.get("method") or ""),
        **routing,
        "pool": sync.get("pool") or db.icloud_hide_email_pool_summary(),
        "pool_by_account": sync.get("pool_by_account") or [],
        "accounts": sync.get("accounts") or [],
        "account_errors": sync.get("account_errors") or [],
        "sync": sync,
    }
