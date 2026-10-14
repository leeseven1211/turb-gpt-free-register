"""只读核验原失败窗口，并沿用同一 Attempt 的提交回执。"""
from __future__ import annotations

from dataclasses import dataclass, fields
import re
import time
from typing import Any, Mapping
from urllib.parse import urlsplit

from core.storage import registration

from .browser_submission import (
    BrowserSubmissionReceipt, SUBMISSION_PHASES,
    record_browser_submission_fact, unresolved_submission_ids,
)
from .email_otp import _email_otp_page_state
from .selenium_dom import _check_manual_stop
from .state_machine import PageState, classify_page


@dataclass(frozen=True)
class RetainedResumeState:
    """原页的可继续步骤；未决 OTP 必须先观察原提交。"""

    page_state: PageState
    password: str | None
    pending_otp: BrowserSubmissionReceipt | None = None


_EMAIL_HINT = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
_PASSWORD_STATES = {PageState.PASSWORD_CREATE, PageState.PASSWORD_LOGIN}
_AFTER_PASSWORD = {PageState.OTP_EMAIL, PageState.PROFILE, PageState.MFA_TOTP, PageState.EMAIL_VERIFIED}
_AFTER_OTP = {PageState.PROFILE, PageState.MFA_TOTP, PageState.EMAIL_VERIFIED}
_UNRESOLVED_PHASE_ORDER = (
    "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown",
)
_UNRESOLVED_PHASES = frozenset(_UNRESOLVED_PHASE_ORDER)
_ROUTES = {
    PageState.PASSWORD_CREATE: {"/create-account/password", "/signup/password"},
    PageState.PASSWORD_LOGIN: {"/log-in/password", "/login/password"},
    PageState.OTP_EMAIL: {"/email-verification"},
    PageState.EMAIL_VERIFIED: {"/email-verification"},
    PageState.PROFILE: {"/about-you", "/profile", "/signup/profile", "/create-account/profile"},
    PageState.MFA_TOTP: {"/mfa-challenge/totp", "/mfa-challenge"},
}


def _unknown(detail: str) -> RuntimeError:
    return RuntimeError(f"request_unknown: {detail}，已保留原窗口，未重新提交")


def _page_state(driver: Any, email: str) -> PageState:
    """来源、可见身份及当前页面必须同时可核验。"""
    _check_manual_stop()
    try:
        snapshot = _email_otp_page_state(driver)
    except Exception:
        raise _unknown("原窗口页面读取失败") from None
    if not isinstance(snapshot, Mapping) or snapshot.get("error") or snapshot.get("challengePresent"):
        raise _unknown("原窗口页面暂不可核验")
    try:
        url = urlsplit(str(snapshot.get("url") or ""))
        trusted = (
            url.scheme == "https" and url.hostname in {"auth.openai.com", "chatgpt.com"}
            and url.port in {None, 443} and url.username is None and url.password is None
        )
    except ValueError:
        trusted = False
    if not trusted:
        raise _unknown("原窗口来源无法核验")
    text = str(snapshot.get("text") or "")
    if any(marker in text.casefold() for marker in (
        "account_deactivated", "account deleted", "deactivated", "banned", "账号停用", "账号禁用", "账号已删除",
    )):
        raise _unknown("原窗口显示账号异常")
    hints = _EMAIL_HINT.findall(text)
    for item in snapshot.get("inputs") or ():
        if not isinstance(item, Mapping) or item.get("visible") is False:
            continue
        attrs = " ".join(str(item.get(key) or "") for key in ("type", "name", "id", "autocomplete")).casefold()
        if any(marker in attrs for marker in ("email", "username")):
            hints.extend(_EMAIL_HINT.findall(str(item.get("value") or "")))
    expected = str(email or "").strip().casefold()
    if not expected or any(hint.casefold() != expected for hint in hints):
        raise _unknown("原窗口的邮箱身份与原任务不一致")
    if getattr(driver, "_registration_retained_identity_required", False) and not hints:
        raise _unknown("重新连接的原窗口缺少可核验的邮箱身份")
    state = PageState.EMAIL_VERIFIED if snapshot.get("emailVerified") else classify_page(snapshot)
    # 页面技术属性可能匹配 OTP，但陌生路由不能据此接管或确认旧提交。
    if url.path.rstrip("/") not in _ROUTES.get(state, set()):
        raise _unknown("原窗口当前认证步骤无法核验")
    if url.hostname != "auth.openai.com" and state != PageState.PROFILE:
        raise _unknown("原窗口当前认证步骤来源不匹配")
    return state


def _submission_kind(fact: Mapping[str, Any]) -> str:
    endpoint = str(fact.get("endpoint_kind") or "unknown")
    kind = str(fact.get("kind") or "")
    if str(fact.get("stage") or "") == "otp_resend" or endpoint == "otp_resend":
        return ""
    if kind == "resume_login":
        return {"email_submit": "email", "nextauth_signin": "email", "password_submit": "password", "otp_submit": "otp"}.get(endpoint, "")
    allowed = {
        "email": {"unknown", "email_submit", "nextauth_signin"},
        "password": {"unknown", "password_submit"},
        "otp": {"unknown", "otp_submit"},
    }
    return kind if endpoint in allowed.get(kind, set()) else ""


def _pending_receipts(driver: Any, facts: Any) -> dict[str, BrowserSubmissionReceipt]:
    """先核验全部未决动作，避免确认一部分后才发现另一条围栏。"""
    if facts is None:
        facts = []
    if not isinstance(facts, (list, tuple)):
        raise _unknown("原任务提交事实无法读取")
    for item in facts:
        if not isinstance(item, Mapping) or str(item.get("phase") or "") not in SUBMISSION_PHASES:
            raise _unknown("原任务提交事实不完整")
        if item.get("phase") in _UNRESOLVED_PHASES and not str(item.get("submission_id") or "").strip():
            raise _unknown("原任务未决提交缺少标识")
    pending_ids = unresolved_submission_ids(facts)
    current = getattr(driver, "_browser_submission_receipt", None)
    history = list(getattr(driver, "_browser_submission_receipts", None) or [])
    if current is not None and all(item is not current for item in history):
        history.append(current)
    by_id = {item.submission_id: item for item in history if isinstance(item, BrowserSubmissionReceipt)}
    if isinstance(current, BrowserSubmissionReceipt):
        by_id[current.submission_id] = current
    receipt_fields = {item.name for item in fields(BrowserSubmissionReceipt)}
    pending: dict[str, BrowserSubmissionReceipt] = {}
    for submission_id in pending_ids:
        records = [item for item in facts if item.get("submission_id") == submission_id]
        kinds = {_submission_kind(item) for item in records}
        if len(kinds) != 1 or not next(iter(kinds)):
            raise _unknown("原任务仍有无法核验的未决提交")
        kind = next(iter(kinds))
        if kind in pending:
            raise _unknown("原任务存在多条同类未决提交")
        # 迟到的 UI/CDP 低阶段事实不能把 unknown 降回待派发状态。
        raw = max((item for item in records if item.get("phase") in _UNRESOLVED_PHASES),
                  key=lambda item: _UNRESOLVED_PHASE_ORDER.index(item["phase"]))
        receipt = by_id.get(submission_id)
        if receipt is None:
            try:
                receipt = BrowserSubmissionReceipt(**{key: value for key, value in raw.items() if key in receipt_fields})
            except (TypeError, ValueError):
                raise _unknown("原任务提交回执无法恢复") from None
            history.append(receipt)
        pending[kind] = receipt
    driver._browser_submission_receipts = history
    return pending


def prepare_retained_resume(driver: Any, *, email: str, existing_password: str | None,
                            facts: Mapping[str, Any], verified_session: dict | None = None) -> RetainedResumeState:
    """只观察原页，确认已前进的原提交；不导航、刷新、填写或点击。"""
    _check_manual_stop()
    try:
        attempt_id = int(facts["attempt_id"])
        if attempt_id <= 0:
            raise ValueError
        private = registration.get_private_resume_context(attempt_id, email=email)
        if not isinstance(private, Mapping):
            raise ValueError
    except Exception:
        raise _unknown("同一 Attempt 的恢复凭据无法核验") from None
    original_password = private.get("password") or None
    if original_password is not None and not isinstance(original_password, str):
        raise _unknown("原任务密码格式无法核验")
    if original_password and existing_password and original_password != existing_password:
        raise _unknown("原任务密码与恢复凭据不一致")
    password = original_password or existing_password or None
    pending = _pending_receipts(driver, private.get("submission_facts"))
    if verified_session is not None:
        user = verified_session.get("user") if isinstance(verified_session, Mapping) else None
        actual = str(user.get("email") or "").strip() if isinstance(user, Mapping) else ""
        if (not isinstance(verified_session, Mapping) or not verified_session.get("accessToken")
                or not actual or actual.casefold() != str(email).strip().casefold()):
            raise _unknown("原窗口登录态与原任务邮箱身份不一致")
        state = PageState.AUTHENTICATED
    else:
        state = _page_state(driver, email)
    if "password" in pending and state in _PASSWORD_STATES:
        deadline = time.monotonic() + 25.0
        while state in _PASSWORD_STATES and time.monotonic() < deadline:
            _check_manual_stop()
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
            state = _page_state(driver, email)
    # 所有原动作必须可确认或可继续观察，再开始写确认事实。
    for kind in pending:
        allowed = _PASSWORD_STATES | _AFTER_PASSWORD if kind == "email" else _AFTER_PASSWORD
        if kind == "otp":
            allowed = {PageState.OTP_EMAIL} | _AFTER_OTP
        allowed = allowed | {PageState.AUTHENTICATED}
        if state not in allowed:
            raise _unknown("原提交在受限观察后仍未确认")
    pending_otp = pending.get("otp") if state == PageState.OTP_EMAIL else None
    for receipt in pending.values():
        if receipt is not pending_otp:
            record_browser_submission_fact(driver, "confirmed", receipt=receipt, result="success")
    if pending_otp is not None:
        driver._browser_submission_receipt = pending_otp
    return RetainedResumeState(state, password, pending_otp)


__all__ = ["RetainedResumeState", "prepare_retained_resume"]
