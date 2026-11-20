"""Read and verify the current Roxy registration session without saving credentials."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.browser.password_auth import ProfileAccountAlreadyExistsError
from core.auth.state_machine import StageBudget


@dataclass(frozen=True)
class SessionCallbacks:
    read_session_once: Callable[..., Any]
    session_unavailable_error: type[Exception]
    route_observer_type: type
    current_route_recovery: Callable[..., Any]
    check_stop: Callable[[], None]
    native_resume_start_page: Callable[..., bool]
    safe_get: Callable[..., Any]
    validate_identity: Callable[..., None]
    logger: Any


def validate_registration_session_identity(session_info: dict, email: str) -> None:
    """保存凭据前确认浏览器会话确实属于本任务邮箱。"""
    user = session_info.get("user") if isinstance(session_info, dict) else None
    actual = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
    expected = str(email or "").strip().casefold()
    if not actual or not expected:
        raise RuntimeError("session_identity_unverified: 登录会话缺少可核验的邮箱身份，已停止保存凭据")
    if actual != expected:
        raise RuntimeError("session_identity_mismatch: 登录会话与任务邮箱不一致，已停止保存凭据")


def registration_password_confirmed_after_token(driver, *, email: str, password: str | None,
                                                previous_receipts=frozenset()) -> bool:
    """同邮箱 Token 已核验后，只确认当前创建链或本轮真实密码登录。"""
    if not str(password or "").strip():
        return False
    history = getattr(driver, "_browser_submission_receipts", None)
    receipts = list(history) if isinstance(history, (list, tuple)) else []
    current = getattr(driver, "_browser_submission_receipt", None)
    if isinstance(current, BrowserSubmissionReceipt) and all(current is not item for item in receipts):
        receipts.append(current)
    for receipt in reversed(receipts):
        if not isinstance(receipt, BrowserSubmissionReceipt) or receipt.submission_id in previous_receipts:
            continue
        if receipt.endpoint_kind != "password_submit" or receipt.phase in {"prepared", "not_dispatched"}:
            continue
        if receipt.stage == "login_password":
            request = receipt.request_binding
            return bool(
                receipt.http_method == "POST" and receipt.phase == "confirmed" and receipt.result == "success"
                and not receipt.auth_error and type(receipt.http_status) is int and 200 <= receipt.http_status < 300
                and request and request == receipt.response_binding and request[0] == receipt.dispatch_target_id
            )
        if receipt.stage != "password_create" or receipt.phase != "confirmed" or receipt.result != "success":
            return False
        break
    chain = getattr(driver, "_registration_password_creation_chain", None)
    if isinstance(chain, dict) and (
        chain.get("email") == str(email).strip().casefold() and chain.get("password") == password
    ):
        receipt = chain.get("receipt")
        if (isinstance(receipt, BrowserSubmissionReceipt) and receipt.stage == "password_create"
                and receipt.endpoint_kind == "password_submit" and receipt.http_method == "POST"
                and receipt.phase == "confirmed" and receipt.result == "success" and not receipt.auth_error
                and (receipt.http_status is None or 200 <= receipt.http_status < 300)):
            return True
    return False


def read_registration_resume_session(driver, email: str, *, budget: StageBudget | None = None, callbacks: SessionCallbacks) -> dict | None:
    """原环境在 ChatGPT 同源页时，只读一次完整会话；未知结果不触发新的登录提交。"""
    current = urlsplit(str(getattr(driver, "current_url", "") or ""))
    if current.scheme != "https" or current.hostname != "chatgpt.com" or current.port not in (None, 443):
        return None
    if (getattr(driver, "_registration_resume_login", False)
            and not current.username and not current.password
            and current.path.rstrip("/") == "/auth/error"):
        # 已知回调错误页没有可复用的完整会话，交给原身份页面恢复选择
        # 新登录；不能在前置探测失败后挡住后面的恢复分支。
        return None
    try:
        timeout = min(30, budget.require("原浏览器会话核验")) if budget is not None else 30
        session = callbacks.read_session_once(driver, timeout=timeout, strict_read=True)
    except callbacks.session_unavailable_error:
        observer = getattr(driver, "_registration_route_observer", None)
        diagnostic = getattr(driver, "_registration_session_diagnostic", None)
        if (isinstance(observer, callbacks.route_observer_type) and callbacks.current_route_recovery() is not None
                and isinstance(diagnostic, dict) and diagnostic.get("status") == 403):
            observer.call_response(driver, "GET", "https://chatgpt.com/api/auth/session", 403)
            observer.raise_if_failed(driver)
        return None
    except Exception as exc:
        observer = getattr(driver, "_registration_route_observer", None)
        if isinstance(observer, callbacks.route_observer_type):
            observer.call_failed(driver, "GET", "https://chatgpt.com/api/auth/session", exc)
        callbacks.check_stop()
        try:
            native_start_page = callbacks.native_resume_start_page(getattr(driver, "current_url", ""))
        except Exception:
            native_start_page = False
        if getattr(driver, "_registration_resume_login", False) and native_start_page:
            # 启动恢复标签页可能在会话预读期间才落到浏览器错误页；原身份
            # 续跑应进入正常登录 GET，不能让这次 origin_changed 挡住恢复。
            return None
        raise RuntimeError("request_unknown: resume_session_probe_incomplete: 原环境会话读取未完成，已保留原提交") from exc
    if session is not None:
        callbacks.validate_identity(session, email)
        callbacks.logger.info("[Roxy注册] 原环境会话已核验：token_present=%s identity_matched=%s", True, True)
    return session


def reconcile_existing_profile_session(driver, email: str, *, callbacks: SessionCallbacks) -> dict:
    """明确账号已存在后，仅用一次固定 GET 和一次同源读取核验原邮箱会话。"""
    budget = StageBudget.start(30)

    def require_session_target():
        try:
            current = urlsplit(str(getattr(driver, "current_url", "") or ""))
            trusted = (
                current.scheme == "https" and current.hostname == "chatgpt.com"
                and current.port in {None, 443} and current.username is None and current.password is None
                and current.path == "/api/auth/session" and not current.query and not current.fragment
            )
        except ValueError:
            trusted = False
        if not trusted:
            raise ProfileAccountAlreadyExistsError(reason="session_origin_unverified")

    try:
        callbacks.safe_get(
            driver, "https://chatgpt.com/api/auth/session", timeout=min(10, int(budget.require("既存账号会话导航"))),
            attempts=1, accept_hosts=("chatgpt.com",),
        )
        require_session_target()
        session = callbacks.read_session_once(
            driver, timeout=budget.require("既存账号会话读取"), strict_read=True,
        )
        budget.require("既存账号会话核验")
        require_session_target()
    except ProfileAccountAlreadyExistsError:
        raise
    except Exception:
        callbacks.check_stop()
        raise ProfileAccountAlreadyExistsError(reason="session_probe_incomplete") from None
    if (not isinstance(session, dict) or not isinstance(session.get("accessToken"), str)
            or not session["accessToken"].strip()):
        raise ProfileAccountAlreadyExistsError(reason="session_unconfirmed")
    try:
        callbacks.validate_identity(session, email)
    except RuntimeError:
        raise ProfileAccountAlreadyExistsError(reason="session_identity_unverified") from None
    callbacks.logger.info("[Roxy注册] 既存账号完整会话已核验：token_present=%s identity_matched=%s", True, True)
    return session
