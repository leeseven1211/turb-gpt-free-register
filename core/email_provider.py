# -*- coding: utf-8 -*-
"""
邮箱来源调度层。

EMAIL_SOURCE 支持单个或多个来源：
    "outlook"
    "cloudflare_domain"   # 自有域名 + QQ IMAP
    "cloudflare"          # Cloudflare Worker 临时邮箱
    "email_butler"        # Email Butler 通用 /v1 API
    "generic_api"
    "gptmail"
    "mailnest"
    "cloudmail"
    "remail"
    "icloud_hide"
    "outlook,generic_api,mailnest,cloudmail"          # WebUI 可选来源列表
    ["outlook", "generic_api", "mailnest", "cloudmail"]  # 也兼容列表写法

WebUI 注册任务始终传入一个明确来源并严格使用。未传 source 的 CLI/兼容调用仍按
EMAIL_SOURCE 顺序尝试，以免破坏旧入口。
"""
import logging
from typing import Iterable

logger = logging.getLogger(__name__)

_VALID_SOURCES = ("outlook", "generic_api", "cloudflare_domain", "cloudflare", "email_butler", "gptmail", "mailnest", "cloudmail", "remail", "mailcode", "xigua", "icloud_hide")
EMAIL_SOURCE_LABELS = {
    "outlook": "Outlook 邮箱池",
    "generic_api": "通用 API 邮箱",
    "cloudflare_domain": "Cloudflare 域名邮箱",
    "cloudflare": "Cloudflare 临时邮箱",
    "email_butler": "Email Butler",
    "gptmail": "GPTMail",
    "mailnest": "MailNest",
    "cloudmail": "CloudMail",
    "remail": "Remail",
    "mailcode": "域名邮箱 MailCode",
    "xigua": "西瓜邮箱",
    "icloud_hide": "iCloud 隐藏邮箱",
}

# 注册驱动只接收邮箱字符串；任务执行时记住明确选择的来源，避免临时邮箱在
# 配置顺序变化或进程缓存存在时被错误识别为其他来源。
_EMAIL_SOURCE_HINTS: dict[str, str] = {}


def parse_email_sources(value=None) -> list[str]:
    """把 EMAIL_SOURCE 解析为有序来源列表，去重并过滤空值。"""
    if value is None:
        from config import email as _email_cfg
        value = _email_cfg.EMAIL_SOURCE
    if isinstance(value, str):
        raw = value.replace(";", ",").replace("|", ",").split(",")
    elif isinstance(value, Iterable):
        raw = list(value)
    else:
        raw = [value]

    out: list[str] = []
    for item in raw:
        s = str(item or "").strip().strip('"\'')
        if not s:
            continue
        if s not in _VALID_SOURCES:
            logger.warning(f"[EmailProvider] 未知邮箱来源 {s!r}，已忽略")
            continue
        if s not in out:
            out.append(s)
    return out or ["outlook"]


def validate_email_source(source: str) -> str:
    """校验任务明确选择的单个邮箱来源，不接受逗号分隔和静默回退。"""
    selected = str(source or "").strip().strip('"\'').lower()
    if not selected:
        raise ValueError("请选择本次注册使用的邮箱来源")
    if any(separator in selected for separator in (",", ";", "|")):
        raise ValueError("每个注册批次只能明确选择一个邮箱来源")
    if selected not in _VALID_SOURCES:
        raise ValueError(f"不支持的邮箱来源: {selected}")
    return selected


def requires_acquisition_identity(source: str) -> bool:
    """Every Butler allocation retains the business intent across retries."""
    from core import email_butler_bridge

    return (source in {"remail", "mailcode", "xigua", "email_butler"}
            or source == "icloud_hide" and email_butler_bridge.enabled())


def remember_email_source(email: str, source: str) -> str:
    """记录任务已明确选择的邮箱来源，供同一任务链后续恢复使用。"""
    address = str(email or "").strip()
    if not address:
        raise ValueError("邮箱不能为空")
    selected = validate_email_source(source)
    _EMAIL_SOURCE_HINTS[address.lower()] = selected
    return selected


def retain_email(email: str, *, source: str | None = None, note: str | None = None) -> str:
    """保留邮箱租约，不改变本地池或远端供应商状态。"""
    address = str(email or "").strip()
    if not address:
        raise ValueError("邮箱不能为空")
    selected = remember_email_source(address, source) if source else resolve_email_source(address)
    logger.warning(
        "[EmailProvider] 保留邮箱租约: source=%s, email=%s, note=%s",
        selected,
        address,
        str(note or "")[:300],
    )
    return selected


def mark_email_permanently_unusable(
    email: str,
    *,
    source: str | None = None,
    note: str | None = None,
) -> str:
    """仅在上游明确确认永久失效时标记 failed，绝不标记 disabled。"""
    address = str(email or "").strip()
    if not address:
        raise ValueError("邮箱不能为空")
    selected = remember_email_source(address, source) if source else resolve_email_source(address, fallback=False)
    if not selected:
        raise RuntimeError("邮箱来源无法确认，不能标记为永久失效")
    from core.email_derivation import release_address

    if release_address(address, status="failed", note=note, permanent=True):
        return selected
    release_email(address, status="failed", note=note, source=selected)
    logger.warning(
        "[EmailProvider] 上游确认邮箱永久失效: source=%s, email=%s, note=%s",
        selected,
        address,
        str(note or "")[:300],
    )
    return selected


def _is_configured_manual_email(email: str) -> bool:
    """手动配置的固定邮箱不依赖邮箱池上下文，也必须原样重跑。"""
    try:
        from config import register as _register_cfg

        configured = str(getattr(_register_cfg, "REGISTER_EMAIL", "") or "").strip()
    except Exception:
        configured = ""
    return bool(configured and configured.lower() == str(email or "").strip().lower())


def _require_retained_local_email(row: dict | None, email: str, source: str) -> None:
    status = str((row or {}).get("status") or "").strip().lower()
    if status != "used":
        raise RuntimeError(
            f"原注册邮箱不再处于保留状态（source={source}, status={status or 'unknown'}），"
            "不能改用其他邮箱重跑"
        )


def restore_email_context(
    email: str,
    *,
    source: str,
    purpose: str = "registration_retry",
    acquisition_id: str | None = None,
    legacy_remail_compatibility: bool = False,
) -> str:
    """恢复原邮箱的必要上下文；无法安全恢复时拒绝改领新邮箱。"""
    address = str(email or "").strip()
    if not address:
        raise RuntimeError("重跑任务缺少原注册邮箱，不能改用其他邮箱")
    selected = remember_email_source(address, source)
    from core import email_butler_bridge
    if selected == "icloud_hide" and email_butler_bridge.enabled():
        email_butler_bridge.restore_context(address, purpose=purpose)
        return selected
    from core.email_derivation import restore_address

    if restore_address(address, source=selected) is not None:
        return selected
    if _is_configured_manual_email(address):
        return selected

    if selected == "email_butler":
        from core.email_butler_client import restore_account_context

        account = restore_account_context(address, purpose=purpose)
        if str(account.email or "").strip().lower() != address.lower():
            raise RuntimeError("Email Butler 未能恢复原注册邮箱，不能改用其他邮箱重跑")
        return selected

    if selected == "outlook":
        from core import db
        from core.outlook_client import get_account_context

        if get_account_context(address) is None:
            raise RuntimeError("原 Outlook 注册邮箱上下文不可恢复，不能改用其他邮箱重跑")
        _require_retained_local_email(db.get_outlook_by_email(address), address, selected)
        return selected

    if selected == "generic_api":
        from core import db
        from core.generic_api_mail_client import get_account_context

        if get_account_context(address) is None:
            raise RuntimeError("原通用 API 注册邮箱上下文不可恢复，不能改用其他邮箱重跑")
        _require_retained_local_email(db.get_generic_api_email_by_email(address), address, selected)
        return selected

    if selected == "icloud_hide":
        from core import db
        from core.icloud_hme_client import get_account_context

        if get_account_context(address) is None:
            raise RuntimeError("原 iCloud 隐藏邮箱上下文不可恢复，不能改用其他邮箱重跑")
        _require_retained_local_email(db.get_icloud_hide_email_by_email(address), address, selected)
        return selected

    if selected == "cloudflare_domain":
        from core import db

        row = db.get_domain_email_by_email(address)
        if row is None:
            raise RuntimeError("原域名注册邮箱不可恢复，不能改用其他邮箱重跑")
        _require_retained_local_email(row, address, selected)
        return selected

    if selected == "remail":
        stable_id = str(acquisition_id or "").strip()
        if not stable_id:
            if not legacy_remail_compatibility:
                raise RuntimeError("原 Remail 恢复缺少稳定 acquisition_id，不能按邮箱猜测订单")
            from core.remail_client import restore_account_context

            account = restore_account_context(address, compatibility=True)
            if account is None or str(account.email or "").strip().casefold() != address.casefold():
                raise RuntimeError("原 Remail 订单取件上下文不可恢复，不能改用其他邮箱重跑")
            return selected

        from core.remail_order_coordinator import RemailOrderCoordinator
        from core.storage import remail_orders

        intent = remail_orders.get_intent(stable_id, private=True)
        if not intent:
            raise RuntimeError("原 Remail 领取意图不存在，不能按邮箱猜测订单")
        account = RemailOrderCoordinator().acquire(
            owner_kind=str(intent.get("owner_kind") or ""),
            owner_id=str(intent.get("owner_id") or ""),
            acquisition_id=stable_id,
        )
        if str(account.email or "").strip().casefold() != address.casefold():
            raise RuntimeError("原 Remail 订单邮箱与注册任务不匹配，不能继续")
        return selected

    if selected in {"mailcode", "xigua"}:
        module = __import__(f"core.{selected}_client", fromlist=["restore_account_context"])
        account = module.restore_account_context(address, purpose=purpose)
        if str(account.email).strip().casefold() != address.casefold():
            raise RuntimeError("原付费邮箱订单与任务邮箱不一致，不能改领其他邮箱")
        return selected

    # 其余临时邮箱的可用性只存在于进程内上下文。上下文丢失时不能猜测
    # 该地址仍归当前任务链所有，必须让任务明确失败而不是悄悄换邮箱。
    context_getters = {
        "gptmail": ("core.gptmail_client", "get_account_context"),
        "cloudflare": ("core.cf_temp_mail_client", "get_account_context"),
        "mailnest": ("core.mailnest_client", "get_account_context"),
        "cloudmail": ("core.cloudmail_client", "get_account_context"),
    }
    module_name, getter_name = context_getters[selected]
    module = __import__(module_name, fromlist=[getter_name])
    if getattr(module, getter_name)(address) is None:
        raise RuntimeError(f"原 {EMAIL_SOURCE_LABELS[selected]} 上下文不可恢复，不能改用其他邮箱重跑")
    return selected


def _registered_email_source(email: str) -> str | None:
    """Return the source recorded for a completed account, if it is valid.

    A registered account is the durable owner of an address.  OTP fallback must
    not guess a different provider from process-local caches or the current
    ``EMAIL_SOURCE`` ordering after a restart.
    """
    try:
        from core import db

        account = db.get_account_by_email(email)
    except Exception:
        return None
    raw = str((account or {}).get("email_source") or "").strip()
    if not raw:
        return None
    selected = raw.replace(";", ",").replace("|", ",").split(",", 1)[0].strip()
    try:
        return validate_email_source(selected)
    except ValueError:
        return None


def _pick_from_source(
    source: str,
    *,
    batch_id: str | None = None,
    job_id: int | None = None,
    owner_kind: str | None = None,
    owner_id: str | int | None = None,
    acquisition_id: str | None = None,
    legacy_remail_compatibility: bool = False,
) -> str:
    from core import email_derivation
    from core import email_butler_bridge

    if source == "icloud_hide" and email_butler_bridge.enabled():
        return email_butler_bridge.pick_account(owner_kind=owner_kind, owner_id=owner_id,
            acquisition_id=acquisition_id).email

    if acquisition_id and email_derivation.store.find_allocation(acquisition_id=acquisition_id):
        return email_derivation.acquire_address(
            source, owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id,
            job_id=job_id,
        )
    if source == "gptmail":
        from core.gptmail_client import pick_account
        return pick_account().email
    if source == "cloudflare":
        from core.cf_temp_mail_client import pick_account
        return pick_account().email
    if source == "email_butler":
        from core.email_butler_client import pick_account
        return pick_account(owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id).email
    if source == "cloudflare_domain":
        from core.qqmail_client import pick_domain_email
        return pick_domain_email()
    if source == "generic_api":
        from core.generic_api_mail_client import pick_account
        return pick_account().email
    if source == "mailnest":
        from core.mailnest_client import pick_account
        return pick_account().email
    if source == "cloudmail":
        from core.cloudmail_client import pick_account
        return pick_account().email
    if source == "remail":
        from core.remail_client import pick_account
        kwargs = {}
        if owner_kind and owner_id is not None and acquisition_id:
            kwargs.update(owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id)
        elif not legacy_remail_compatibility:
            raise RuntimeError("Remail 领取缺少稳定 owner/acquisition_id，已停止下单")
        else:
            kwargs["compatibility"] = True
        return pick_account(**kwargs).email
    if source in {"mailcode", "xigua"}:
        module = __import__(f"core.{source}_client", fromlist=["pick_account"])
        # 任务重跑继承根任务 owner；CLI 与换绑也显式提供自己的稳定身份。
        selected_owner_kind, selected_owner_id = owner_kind, owner_id
        if not selected_owner_kind and job_id is not None:
            selected_owner_kind, selected_owner_id = "registration_job", str(job_id)
        return module.pick_account(owner_kind=selected_owner_kind, owner_id=selected_owner_id,
                                   acquisition_id=acquisition_id).email
    if source == "icloud_hide":
        from core.icloud_hme_client import pick_account
        return pick_account(batch_id=batch_id, job_id=job_id).email
    from core.outlook_client import pick_account
    return pick_account().email


def acquire_email(
    source: str | None = None,
    *,
    batch_id: str | None = None,
    job_id: int | None = None,
    owner_kind: str | None = None,
    owner_id: str | int | None = None,
    acquisition_id: str | None = None,
    legacy_remail_compatibility: bool = False,
) -> str:
    """领取邮箱；任务传入 source 时严格使用该来源，不自动切换平台。"""
    explicit = source is not None
    sources = [validate_email_source(source)] if explicit else parse_email_sources()
    last_exc: Exception | None = None
    for source in sources:
        try:
            kwargs = {"batch_id": batch_id, "job_id": job_id}
            if owner_kind is not None or owner_id is not None or acquisition_id is not None:
                kwargs.update(owner_kind=owner_kind, owner_id=owner_id, acquisition_id=acquisition_id)
            if legacy_remail_compatibility:
                kwargs["legacy_remail_compatibility"] = True
            email = _pick_from_source(source, **kwargs)
            remember_email_source(email, source)
            logger.info(f"[EmailProvider] 使用邮箱来源: {source}, email={email}")
            return email
        except Exception as exc:
            if source in {"mailcode", "xigua"}:
                # 付费供应商的普通失败仍可由原任务重跑；本次领取不跨平台重购。
                raise
            # 邮箱下单结果不明时必须保留核验状态，不能包装成普通失败或换平台。
            if getattr(exc, "request_unknown", False) or getattr(exc, "identity_locked", False):
                raise
            last_exc = exc
            logger.warning(f"[EmailProvider] 来源 {source} 领取邮箱失败: {type(exc).__name__}: {exc}")
            if explicit:
                break
            continue
    if explicit:
        raise RuntimeError(f"所选邮箱来源 {sources[0]} 领取失败: {last_exc}")
    raise RuntimeError(f"所有邮箱来源均领取失败: {sources}; last={last_exc}")


def resolve_email_source(email: str, *, fallback: bool = True) -> str | None:
    """根据邮箱在各池中的归属判断实际来源；可禁止按当前配置猜测。"""
    from core.email_derivation import find_binding

    binding = find_binding(email)
    if binding is not None:
        return str(binding["source"])
    registered_source = _registered_email_source(email)
    if registered_source:
        return registered_source

    hinted_source = _EMAIL_SOURCE_HINTS.get(str(email or "").strip().lower())
    if hinted_source:
        return hinted_source

    from core.storage import mail_provider_orders
    try:
        durable_source = mail_provider_orders.find_source(email)
    except Exception:
        durable_source = None
    if durable_source:
        return durable_source

    from core.gptmail_client import get_account_context as get_gptmail_context
    if get_gptmail_context(email):
        return "gptmail"
    from core.cf_temp_mail_client import get_account_context as get_cf_context
    if get_cf_context(email):
        return "cloudflare"
    from core.email_butler_client import get_account_context as get_email_butler_context
    if get_email_butler_context(email):
        return "email_butler"
    from core.mailnest_client import get_account_context as get_mailnest_context
    if get_mailnest_context(email):
        return "mailnest"
    from core.cloudmail_client import get_account_context as get_cloudmail_context
    if get_cloudmail_context(email):
        return "cloudmail"
    from core.remail_client import get_account_context as get_remail_context
    if get_remail_context(email):
        return "remail"
    from core.icloud_hme_client import get_account_context as get_icloud_context
    if get_icloud_context(email):
        return "icloud_hide"

    from core import db
    if db.get_generic_api_email_by_email(email):
        return "generic_api"
    if db.get_outlook_by_email(email):
        return "outlook"
    if db._find_domain_email(db._load_domain_pool(), email):  # 内部轻量查询，仅本项目使用
        return "cloudflare_domain"
    # 兜底：如果域名匹配 EMAIL_DOMAIN，则按域名邮箱处理
    try:
        from config import email as _email_cfg
        domain = (_email_cfg.EMAIL_DOMAIN or "").lower().strip()
        if domain and domain != "-" and email.lower().endswith("@" + domain):
            return "cloudflare_domain"
    except Exception:
        pass
    return parse_email_sources()[0] if fallback else None


def wait_for_otp(
    email: str,
    after_ts: float,
    max_wait: int | None = None,
    poll_interval: int | None = None,
    settle_seconds: int | None = None,
    *,
    email_source: str | None = None,
    force_service: bool | None = None,
    budget=None,
) -> str:
    """等待并返回该邮箱最新的 ChatGPT OTP（6 位数字字符串）。

    USE_EMAIL_SERVICE=False 时走手动验证码通道（WebUI 提交 / CLI 输入），
    不再强制要求 Outlook clientId/refreshToken。
    """
    if budget is not None:
        import math
        from core.mailbox_wait import use_budget
        with use_budget(budget):
            remaining = budget.require("邮箱验证码")
            # 旧 provider 会把 max_wait 转成整数；向上取整避免不足一秒时被
            # 提前判超时，实际网络和轮询仍由精确的共享预算裁剪。
            wait_seconds = math.ceil(min(remaining, max_wait) if max_wait is not None else remaining)
            otp = wait_for_otp(
                email, after_ts=after_ts,
                max_wait=wait_seconds,
                poll_interval=poll_interval, settle_seconds=settle_seconds,
                email_source=email_source, force_service=force_service,
            )
            budget.require("邮箱验证码")
            return otp
    try:
        from config import email as _email_cfg
        use_service = bool(
            getattr(_email_cfg, "USE_EMAIL_SERVICE", True)
            if force_service is None else force_service
        )
    except Exception:
        use_service = True

    if not use_service:
        from core.manual_otp import wait_for_manual_otp
        from config import email as _email_cfg
        timeout = int(max_wait if max_wait is not None else (getattr(_email_cfg, "OTP_MAX_WAIT", 180) or 180))
        job_id = None
        try:
            from core import registration_service as svc
            job_id = getattr(svc._THREAD_CTX, "job_id", None)
        except Exception:
            job_id = None
        return wait_for_manual_otp(email, timeout=timeout, job_id=job_id)

    extra_kwargs = {}
    if max_wait is not None:
        extra_kwargs["max_wait"] = max_wait
    if poll_interval is not None:
        extra_kwargs["poll_interval"] = poll_interval
    if settle_seconds is not None:
        extra_kwargs["settle_seconds"] = settle_seconds

    source = validate_email_source(email_source) if email_source else resolve_email_source(email)
    from core import email_derivation
    from core.email_auth_guard import begin_generation, checkpoint, current_session
    from core.storage.email_address_allocations import StaleOtpFence

    session = current_session()
    if session is not None and session.email != str(email or "").strip().lower():
        raise StaleOtpFence("验证码目标与当前完整邮箱认证地址不一致")
    checkpoint()
    begin_generation(after_ts)

    if email_derivation.find_binding(email) is not None:
        code = email_derivation.fetch_bound_otp(email, after_ts=after_ts, **extra_kwargs)
        checkpoint()
        return code
    if source == "gptmail":
        from core.gptmail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "cloudflare":
        from core.cf_temp_mail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "email_butler":
        from core.email_butler_client import fetch_latest_otp
        code = fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
        checkpoint()
        return code
    if source == "cloudflare_domain":
        from core.qqmail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "generic_api":
        from core.generic_api_mail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "mailnest":
        from core.mailnest_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "cloudmail":
        from core.cloudmail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "remail":
        from core.remail_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source in {"mailcode", "xigua"}:
        module = __import__(f"core.{source}_client", fromlist=["fetch_latest_otp"])
        return module.fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    if source == "icloud_hide":
        from core.icloud_hme_client import fetch_latest_otp
        return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)
    from core.outlook_client import fetch_latest_otp
    return fetch_latest_otp(email, after_ts=after_ts, **extra_kwargs)


def email_material_line(email: str, source: str | None = None) -> str:
    """Return the private mailbox material line for an acquired address.

    This is intentionally an on-demand worker helper.  The line is used only
    during the atomic account writeback and is never placed in task events or
    ordinary account responses.
    """
    address = str(email or "").strip()
    if not address:
        return ""
    from core.email_derivation import material_line

    derived_material = material_line(address)
    if derived_material is not None:
        return derived_material
    selected = validate_email_source(source) if source else resolve_email_source(address)
    from core import db

    if selected == "outlook":
        row = db.get_outlook_by_email(address) or {}
        return "----".join([
            str(row.get("email") or address),
            str(row.get("password") or ""),
            str(row.get("client_id") or ""),
            str(row.get("refresh_token") or ""),
        ])
    if selected == "generic_api":
        row = db.get_generic_api_email_by_email(address) or {}
        return "----".join([str(row.get("email") or address), str(row.get("code_url") or "")])
    if selected == "cloudflare_domain":
        row = db.get_domain_email_by_email(address) or {}
        return "----".join([str(row.get("email") or address), str(row.get("password") or "")])
    if selected == "icloud_hide":
        row = db.get_icloud_hide_email_by_email(address) or {}
        return "----".join([str(row.get("email") or address), str(row.get("remote_address") or "")])
    # Remote mailbox providers keep their credentials outside the account row;
    # retain the address as the stable material reference without copying them.
    return address


def release_email(
    email: str,
    status: str = "available",
    note: str | None = None,
    *,
    source: str | None = None,
) -> str:
    """按已确认或解析出的邮箱来源回收状态，返回来源名。"""
    selected = remember_email_source(email, source) if source else resolve_email_source(email)
    from core import email_butler_bridge
    if selected == "icloud_hide" and email_butler_bridge.enabled():
        from core.icloud_hme_client import release_account
        release_account(email, status=status, note=note)
        return selected
    from core.email_derivation import release_address

    if release_address(email, status=status, note=note):
        return selected
    if selected == "gptmail":
        from core.gptmail_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "cloudflare":
        from core.cf_temp_mail_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "email_butler":
        from core.email_butler_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "cloudflare_domain":
        from core.qqmail_client import release_domain_email
        release_domain_email(email, status=status, note=note)
    elif selected == "generic_api":
        from core.generic_api_mail_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "mailnest":
        from core.mailnest_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "cloudmail":
        from core.cloudmail_client import release_account
        release_account(email, status=status, note=note)
    elif selected == "remail":
        from core.remail_client import release_account
        release_account(email, status=status, note=note)
    elif selected in {"mailcode", "xigua"}:
        module = __import__(f"core.{selected}_client", fromlist=["release_account"])
        module.release_account(email, status=status, note=note)
    elif selected == "icloud_hide":
        from core.icloud_hme_client import release_account
        release_account(email, status=status, note=note)
    else:
        from core.outlook_client import release_account
        release_account(email, status=status, note=note)
    return selected


def release_email_if_unconsumed(email: str, note: str | None = None) -> bool:
    """回收仍停留在 used 的任务领取，且绝不覆盖已注册/已判废状态。"""
    if not (email or "").strip():
        return False

    from core.email_derivation import find_binding

    if find_binding(email) is not None:
        # 已生成地址继续属于原业务意图，不放回母资源或其他任务。
        return False

    source = resolve_email_source(email)
    from core import db

    if source == "outlook":
        changed = db.release_unconsumed_outlook(email, note=note)
    elif source == "generic_api":
        changed = db.release_unconsumed_generic_api_email(email, note=note)
    elif source == "cloudflare_domain":
        changed = db.release_unconsumed_domain_email(email, note=note)
    elif source == "icloud_hide":
        changed = db.release_unconsumed_icloud_hide_email(email, note=note)
    else:
        # 临时邮箱不重新进入本地池，只清理进程上下文；已有本地账号时保留上下文。
        if db.get_account_by_email(email) is not None:
            return False
        release_email(email, status="available", note=note)
        changed = True

    if changed:
        logger.info("[EmailProvider] 已回收未消耗邮箱: source=%s, email=%s", source, email)
    return changed
