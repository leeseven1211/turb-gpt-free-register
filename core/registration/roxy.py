# -*- coding: utf-8 -*-
"""通过 RoxyBrowser 指纹浏览器 + Selenium 执行 ChatGPT 注册。"""
from __future__ import annotations

import logging
import copy
import json
import math
import random
import re
import string
import time
import uuid
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from config import codex as _codex_cfg
from config import twofa as _twofa_cfg
from core.account_export import setup_2fa_protocol
from core.email_provider import wait_for_otp, resolve_email_source, validate_email_source
from core.humanize import delay as human_delay
from core.openai_auth import AccountUnusableError
from core.roxybrowser_client import RoxyBrowserClient, RoxyOpenResult, RoxyProfileQuotaExceeded
from core.session import BrowserSession
from core.registration.state_machine import (
    PageState,
    StageBudget,
    StageTimeout,
    can_resend_otp,
    classify_page,
)
from core.registration.auth_context import AuthExecutionContext
from core.registration.email_otp import _EmailSubmissionUnknown
from core.registration.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration.submission_recovery import diagnostics_for, log_submission_diagnostics
from core.registration.selenium_dom import _dispatch_trusted_click
from core.registration.retained_browser import (
    persist_browser_resume_context, recover_attempt_failed_browser,
    recover_bound_failed_browser, retain_failed_browser, take_failed_browser,
)
from core.registration.retained_resume import _is_native_resume_start_page, prepare_retained_resume
from core.auth_challenge import (
    MfaSecretMissingError,
    PasswordRejectedError,
    PasswordSetupNotReadyError,
    RemoteExistingAccountError,
    auth_result_for_registration,
    classify_registration_identity,
)

logger = logging.getLogger(__name__)


def _receipt_accepts_submission_endpoint(receipt, endpoint_kind: str) -> bool:
    expected = str(getattr(receipt, "endpoint_kind", "") or "")
    endpoint_kind = str(endpoint_kind or "")
    if expected == "email_submit":
        # UI 邮箱点击实际发送 NextAuth signin；CSRF GET 只是前置读取，
        # 不能把它的成功或失败写成这次邮箱 POST 的回执。
        return endpoint_kind in {"email_submit", "nextauth_signin"}
    return bool(expected and expected == endpoint_kind)


def _unique_submission_receipt_for_endpoint(driver, endpoint_kind: str):
    """仅在本 Run 存在唯一候选时把 CDP request 关联到提交事实。"""
    history = getattr(driver, "_browser_submission_receipts", None)
    if not isinstance(history, list):
        history = []
    candidates = [
        item for item in history
        if getattr(item, "phase", "") not in {"prepared", "not_dispatched"}
        and _receipt_accepts_submission_endpoint(item, endpoint_kind)
    ]
    # 同 target/endpoint 的迟到 request 无法证明属于哪一次提交时，宁可不
    # 补 request_fact，页面回执仍保留原有的安全结论。
    return candidates[0] if len(candidates) == 1 else None


def _submission_response_fact(endpoint_kind: str, status: object) -> tuple[str, str]:
    """把已绑定响应转换为保守事实，不把 CSRF 失败冒充 signin 拒绝。"""
    try:
        code = int(status or 0)
    except (TypeError, ValueError):
        code = 0
    if endpoint_kind == "nextauth_csrf":
        return "response_observed", ""
    if code in {400, 401}:
        return "rejected", "failure"
    if endpoint_kind == "nextauth_signin" and code == 403:
        # 挑战拦截属于本次请求失败，不证明账号或后续同身份登录被永久拒绝。
        return "response_observed", "failure"
    if 100 <= code < 400:
        return "response_observed", "success"
    return "response_observed", ""


def _make_submission_observer(driver):
    """为当前浏览器连接配对请求与响应，不发起任何认证请求。"""
    submission_requests = {}

    def observe(meta):
        request_key = (
            str(meta.get("target_id") or ""),
            str(meta.get("request_id") or ""),
        )
        endpoint_kind = str(meta.get("endpoint_kind") or "")
        # 没有 CDP requestId 时无法把 response 与同端点提交绑定。
        if not request_key[1]:
            return
        if meta.get("response"):
            receipt = submission_requests.pop(request_key, None)
            if receipt is None:
                # 响应必须沿用请求时已绑定的回执，不重选当前提交或处理重复响应。
                return
        else:
            receipt = _unique_submission_receipt_for_endpoint(driver, endpoint_kind)
            if receipt is None:
                return
            submission_requests[request_key] = receipt
        phase, response_result = _submission_response_fact(endpoint_kind, meta.get("http_status"))
        if not meta.get("response"):
            phase, response_result = "request_observed", ""
        record_browser_submission_fact(
            driver, phase, receipt=receipt,
            endpoint_kind=endpoint_kind,
            http_method=meta.get("http_method"),
            http_status=meta.get("http_status"),
            duration_ms=meta.get("duration_ms"),
            result=response_result,
        )

    return observe


# These failures happen before a local account checkpoint exists. Keeping the
# temporary Profile for them only consumes a Roxy slot; failures after a
# password/OTP submit are deliberately excluded by the state guards below.
_DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS = (
    "err_tunnel_connection_failed",
    "err_proxy_connection_failed",
    "chrome-error://chromewebdata/",
    "邮箱提交/认证跳转超过总预算",
    "roxy registration stage timeout exhausted",
    "email otp input budget exhausted",
    "page_not_hydrated",
)

_REGISTRATION_REQUEST_UNKNOWN_MARKERS = (
    "auth_session_unavailable:",
    "session_identity_unverified",
    "session_identity_mismatch",
    "邮箱提交后未识别到",
    "邮箱提交/认证跳转超过总预算",
    "注册页状态未知",
    "后续页面类型未知",
    "认证跳转结果未知",
)


def _validate_registration_session_identity(session_info: dict, email: str) -> None:
    """保存凭据前确认浏览器会话确实属于本任务邮箱。"""
    user = session_info.get("user") if isinstance(session_info, dict) else None
    actual = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
    expected = str(email or "").strip().casefold()
    if not actual or not expected:
        raise RuntimeError("session_identity_unverified: 登录会话缺少可核验的邮箱身份，已停止保存凭据")
    if actual != expected:
        raise RuntimeError("session_identity_mismatch: 登录会话与任务邮箱不一致，已停止保存凭据")


def _read_registration_resume_session(driver, email: str, *, budget: StageBudget | None = None) -> dict | None:
    """原环境在 ChatGPT 同源页时，只读一次完整会话；未知结果不触发新的登录提交。"""
    from .session_auth import ChatGPTSessionUnavailable, _read_chatgpt_session_once

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
        session = _read_chatgpt_session_once(driver, timeout=timeout, strict_read=True)
    except ChatGPTSessionUnavailable:
        return None
    except Exception as exc:
        _check_manual_stop()
        try:
            native_start_page = _is_native_resume_start_page(getattr(driver, "current_url", ""))
        except Exception:
            native_start_page = False
        if getattr(driver, "_registration_resume_login", False) and native_start_page:
            # 启动恢复标签页可能在会话预读期间才落到浏览器错误页；原身份
            # 续跑应进入正常登录 GET，不能让这次 origin_changed 挡住恢复。
            return None
        raise RuntimeError("request_unknown: resume_session_probe_incomplete: 原环境会话读取未完成，已保留原提交") from exc
    if session is not None:
        _validate_registration_session_identity(session, email)
        logger.info("[Roxy注册] 原环境会话已核验：token_present=%s identity_matched=%s", True, True)
    return session


def _retained_profile_can_attach(client, opened) -> bool:
    """只把明确关闭或缺失当成原窗口不可用；查询未知不能新建环境。"""
    try:
        row = client._find_active_profile_by_id(opened.profile_id)
    except Exception:
        raise RuntimeError("request_unknown: 原浏览器状态未能核验，已保留原提交") from None
    if row is None:
        return False
    status = str(row.get("openStatus", row.get("open_status", ""))).strip().lower()
    return status not in {"0", "false", "closed", "close"}


_OTP_PREPARE_CURRENT_FORM_SCRIPT = r"""
const inputs = arguments[0];
const ready = el => !!(el && el.isConnected && el.getClientRects().length)
  && !el.matches(':disabled') && !el.readOnly;
const form = inputs?.[0]?.form;
if (!Array.isArray(inputs) || !inputs.length || !form
    || !inputs.every(el => ready(el) && el.form === form)
    || window.__codexEmailOtpValidateRequestCounterInstalled !== true) return false;
const previous = window.__turbRegistrationOtpSubmitGuard;
if (previous?.listener) document.removeEventListener('submit', previous.listener, true);
const guard = {form, inputs, clickIssued: false, submitEventSeen: false,
  submitDefaultPrevented: false, nativeSubmitPossible: false,
  formPostCalls: 0, unknownFormPostCalls: 0,
  requestCount: Number(window.__codexEmailOtpValidateRequestCount || 0)};
const listener = event => {
  if (event.target !== guard.form) return;
  guard.submitEventSeen = true;
  // 捕获阶段早于框架取消事件；事件本身不能证明验证码请求已派发。
  queueMicrotask(() => {
    guard.submitDefaultPrevented = event.defaultPrevented === true;
    guard.nativeSubmitPossible = guard.nativeSubmitPossible || (!event.defaultPrevented
      && String(guard.form.method || '').toLowerCase() === 'post');
  });
};
guard.listener = listener;
window.__turbRegistrationOtpSubmitGuard = guard;
document.addEventListener('submit', listener, true);
// Remix 表单也可能 POST 当前页面路径；只读取 intent，不保存请求正文。
if (!window.__turbRegistrationOtpFormRequestHooked) {
  const markFormPost = (url, method, body) => {
    const active = window.__turbRegistrationOtpSubmitGuard;
    if (!active?.form || !url || String(method || 'GET').toUpperCase() !== 'POST') return;
    try {
      const target = new URL(String(url || ''), location.href);
      const action = new URL(active.form.action, location.href);
      if (target.origin !== action.origin || target.pathname !== action.pathname) return;
      let intent = null;
      if (body && typeof body.get === 'function') intent = body.get('intent');
      else if (typeof body === 'string') intent = new URLSearchParams(body).get('intent');
      if (intent === 'resend') return;
      if (intent === 'validate') active.formPostCalls += 1;
      else active.unknownFormPostCalls += 1;
    } catch (_) {}
  };
  const originalFetch = window.fetch;
  if (typeof originalFetch === 'function') {
    window.fetch = function(input, init) {
      markFormPost(typeof input === 'string' ? input : input?.url || input?.href,
        init?.method || input?.method || 'GET', init?.body);
      return originalFetch.apply(this, arguments);
    };
  }
  if (typeof XMLHttpRequest !== 'undefined') {
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
      this.__turbOtpFormMethod = method;
      this.__turbOtpFormUrl = url;
      return originalOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
      markFormPost(this.__turbOtpFormUrl, this.__turbOtpFormMethod, body);
      return originalSend.apply(this, arguments);
    };
  }
  window.__turbRegistrationOtpFormRequestHooked = true;
}
return true;
"""


_OTP_SUBMIT_CURRENT_FORM_SCRIPT = r"""
const visible = el => !!(el && el.getClientRects().length);
const path = location.pathname.toLowerCase();
const guard = window.__turbRegistrationOtpSubmitGuard;
const count = value => Number.isFinite(Number(value)) ? Math.max(0, Math.trunc(Number(value))) : 0;
const result = (clicked, reason) => ({clicked, reason, diagnostics: {
  submit_event_seen: guard?.submitEventSeen === true,
  submit_default_prevented: guard?.submitDefaultPrevented === true,
  native_submit_possible: guard?.nativeSubmitPossible === true,
  explicit_click_issued: guard?.clickIssued === true,
  form_connected: guard?.form?.isConnected === true,
  baseline_request_count: count(guard?.requestCount),
  validate_request_count: count(window.__codexEmailOtpValidateRequestCount),
  form_post_call_count: count(guard?.formPostCalls),
  unknown_form_post_call_count: count(guard?.unknownFormPostCalls),
}});
if (!path.includes('email-verification')) return result(false, 'page_advanced');
if (!guard) return result(false, 'otp_guard_missing');
if (guard.clickIssued) return result(false, 'explicit_click_pending');
if (Number(window.__codexEmailOtpValidateRequestCount || 0) > guard.requestCount)
  return result(false, 'validate_request_observed');
if (guard.formPostCalls || guard.unknownFormPostCalls) return result(false, 'form_post_observed');
if (guard.nativeSubmitPossible) return result(false, 'native_submit_pending');
const {form, inputs} = guard;
if (!form?.isConnected || !inputs.every(el => el.isConnected && el.form === form))
  return result(false, 'otp_form_replaced');
const button = [...form.querySelectorAll('button[type="submit"],input[type="submit"]')].find(el =>
  visible(el) && !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true'
  && !/resend/.test([el.name, el.value, el.getAttribute('data-dd-action-name')].join(' ').toLowerCase())
);
if (!button || !inputs.every(el => !!el.value) || !form.checkValidity())
  return result(false, 'otp_form_not_ready');
if (arguments[0] === true) {
  button.scrollIntoView({block:'center'});
  const r = button.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !button.contains(document.elementFromPoint(x, y)))
    return result(false, 'otp_submit_obscured');
  guard.clickIssued = true;
  return {...result(true, 'otp_form_submitted'), trusted_click:{x,y}};
}
guard.clickIssued = true;
button.click();
return result(true, 'otp_form_submitted');
"""


def _prepare_email_otp_current_form(driver, inputs, *, budget: StageBudget | None = None,
                                    capture_responses: bool = False) -> None:
    """输入控件实际挂载后，复用验证码请求观察器并绑定同一表单。"""
    from core.roxy_codex_oauth import _install_email_otp_validate_hook

    if budget is not None:
        budget.require("验证码输入准备")
    _install_email_otp_validate_hook(driver, capture_responses=capture_responses)
    if driver.execute_script(_OTP_PREPARE_CURRENT_FORM_SCRIPT, inputs) is not True:
        record_browser_submission_fact(driver, "not_dispatched", result="cancelled")
        raise RuntimeError("otp_form_not_ready: 验证码输入前表单未就绪，未填写或提交验证码")


def _submit_email_otp_current_form(driver) -> dict:
    """仅点击当前邮箱验证码表单，自动跳转后不触碰下一页按钮。"""
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if getattr(receipt, "endpoint_kind", "") == "otp_submit" and getattr(receipt, "phase", "") in {
        "request_observed", "response_observed", "confirmed", "rejected", "unknown",
    }:
        return {"clicked": False, "reason": "request_observed"}
    result = driver.execute_script(
        _OTP_SUBMIT_CURRENT_FORM_SCRIPT, callable(getattr(driver, "execute_cdp_cmd", None)),
    )
    if isinstance(result, dict) and result.get("trusted_click"):
        _dispatch_trusted_click(driver, result.pop("trusted_click"))
    if isinstance(result, dict):
        diagnostics = result.get("diagnostics") or {}
        safe_diagnostics = {
            key: value for key, value in diagnostics.items()
            if key in {"submit_event_seen", "submit_default_prevented", "native_submit_possible", "explicit_click_issued",
                       "form_connected", "baseline_request_count", "validate_request_count", "form_post_call_count",
                       "unknown_form_post_call_count"}
            and type(value) in (bool, int)
        } if isinstance(diagnostics, dict) else {}
        logger.info("[Roxy注册][OTP] 提交控件判断：clicked=%s diagnostics=%s", result.get("clicked") is True, safe_diagnostics)
    return result if isinstance(result, dict) else {"clicked": False, "reason": "receipt_unknown"}

_PASSWORD_ENTRY_FAILURE_MARKERS = (
    "password_entry_page_not_hydrated",
    "password_entry_not_offered",
    "password_entry_recovery_exhausted",
)


class _OtpAttemptTracker:
    """Prevent one registration run from submitting the same OTP twice."""

    def __init__(self) -> None:
        self._submitted: set[str] = set()

    def accept(self, code: object) -> bool:
        normalized = str(code or "").strip()
        if not normalized or normalized in self._submitted:
            return False
        self._submitted.add(normalized)
        return True


def _is_registration_request_unknown(error_text: object) -> bool:
    """Recognize an observed-but-unclassified remote registration state."""
    if isinstance(error_text, _EmailSubmissionUnknown):
        return True
    text = str(error_text or "")
    if text.startswith("request_unknown:"):
        return True
    return any(marker in text for marker in _REGISTRATION_REQUEST_UNKNOWN_MARKERS)


def _is_disposable_pre_account_failure(
    error_text: str,
    *,
    create_acknowledged: bool,
    account_id: int | None,
) -> bool:
    """Return whether a run-created Profile can be discarded safely."""
    if create_acknowledged or account_id is not None:
        return False
    normalized = str(error_text or "").lower()
    # 密码入口阶段已在 OpenAI 侧推进过注册身份。即使页面仍是空壳，也要保留
    # Profile/cookie 给同一 Attempt 继续恢复，不能按普通首屏空壳回收。
    if any(marker in normalized for marker in _PASSWORD_ENTRY_FAILURE_MARKERS):
        return False
    if any(marker in normalized for marker in _DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS):
        return True
    # The page-not-hydrated classifier is persisted separately from the raw
    # exception. Match its characteristic empty ChatGPT auth snapshot too.
    empty_actions = "'actions': []" in normalized or '"actions": []' in normalized
    empty_inputs = "'inputs': []" in normalized or '"inputs": []' in normalized
    return (
        "找不到邮箱输入框/邮箱入口" in normalized
        and "chatgpt.com/auth/login" in normalized
        and empty_actions
        and empty_inputs
    )



from core.registration import auth_capabilities as _auth_capabilities


def _shared_compat_overrides() -> dict[str, object]:
    """收集当前 Roxy 模块被旧测试/集成显式覆盖的绑定。"""
    overrides: dict[str, object] = {}
    for name in _auth_capabilities._COMPAT_BINDING_NAMES:
        candidate = globals().get(name)
        if candidate is None or getattr(candidate, "__roxy_shared_wrapper__", False):
            continue
        overrides[name] = candidate
    return overrides


def _call_shared_capability(name: str, *args, **kwargs):
    """调用共享能力；兼容覆盖是单次、显式且线程隔离的。"""
    overrides = _shared_compat_overrides()
    # 开源驱动仅在指定阶段注入页面辅助，不能重绑共享模块或影响其他注册任务。
    overrides.update(kwargs.pop("_helper_overrides", None) or {})
    if kwargs.get("context") is None:
        try:
            from core.registration_service import StopRequested, is_stop_requested

            kwargs["context"] = AuthExecutionContext(
                cancellation=lambda: bool(is_stop_requested()),
                budget=kwargs.get("budget") if isinstance(kwargs.get("budget"), StageBudget) else None,
                cancellation_error=lambda: StopRequested("认证能力收到注册任务停止请求"),
            )
        except (ImportError, AttributeError):
            # Keep direct/unit capability calls usable when the registration
            # service is intentionally not loaded.  The service-facing path
            # supplies the concrete cancellation exception above.
            pass
    # The shared MFA/registration challenge capability accepts callbacks; it
    # must not import this OAuth orchestrator just to preserve the historical
    # Roxy monkeypatch points.  Resolve those adapters only on the old Roxy
    # path and inject them into the same ContextVar override scope.
    if name in {
        "_complete_registration_totp_after_email_otp",
        "_complete_settings_email_reauth",
    }:
        try:
            from core import roxy_codex_oauth as _oauth

            for callback_name in (
                "complete_openai_login_challenge",
                "_is_totp_login_page",
                "_submit_saved_login_totp",
            ):
                callback = getattr(_oauth, callback_name, None)
                if callable(callback):
                    overrides[callback_name] = callback
        except Exception:
            # A direct registration flow may not have loaded the OAuth module;
            # the capability will report a missing injected resolver only if
            # it actually reaches a chained challenge.
            pass
    return _auth_capabilities.call_with_compatibility(
        name,
        overrides,
        *args,
        **kwargs,
    )


def _make_shared_compatibility_wrapper(name: str):
    def wrapper(*args, **kwargs):
        return _call_shared_capability(name, *args, **kwargs)

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    wrapper.__module__ = __name__
    wrapper.__roxy_shared_wrapper__ = True
    wrapper.__shared_capability__ = True
    return wrapper


_log_prefix = _make_shared_compatibility_wrapper("_log_prefix")
_build_driver = _make_shared_compatibility_wrapper("_build_driver")
_quit_driver = _make_shared_compatibility_wrapper("quit_driver")
_center_browser_window = _make_shared_compatibility_wrapper("_center_browser_window")
_wait = _make_shared_compatibility_wrapper("_wait")
_budget_timeout = _make_shared_compatibility_wrapper("_budget_timeout")
_roxy_page_state = _make_shared_compatibility_wrapper("_roxy_page_state")
_auth_terminal_page_state = _make_shared_compatibility_wrapper("_auth_terminal_page_state")
_safe_get = _make_shared_compatibility_wrapper("_safe_get")
_visible = _make_shared_compatibility_wrapper("_visible")
_browser_actions_enabled = _make_shared_compatibility_wrapper("_browser_actions_enabled")
_apply_browser_automation_mask = _make_shared_compatibility_wrapper("_apply_browser_automation_mask")
_human_scroll_to = _make_shared_compatibility_wrapper("_human_scroll_to")
_human_click = _make_shared_compatibility_wrapper("_human_click")
_human_type_text = _make_shared_compatibility_wrapper("_human_type_text")
_page_warmup = _make_shared_compatibility_wrapper("_page_warmup")
_refresh_chatgpt_settings_shell_if_needed = _make_shared_compatibility_wrapper("_refresh_chatgpt_settings_shell_if_needed")
_settings_page_not_ready = _make_shared_compatibility_wrapper("_settings_page_not_ready")
_find_any = _make_shared_compatibility_wrapper("_find_any")
_click_any = _make_shared_compatibility_wrapper("_click_any")
_type_any = _make_shared_compatibility_wrapper("_type_any")
_email_entry_state = _make_shared_compatibility_wrapper("_email_entry_state")
_find_visible_email_input_js = _make_shared_compatibility_wrapper("_find_visible_email_input_js")
_is_oauth_consent_like = _make_shared_compatibility_wrapper("_is_oauth_consent_like")
_is_external_idp_url = _make_shared_compatibility_wrapper("_is_external_idp_url")
_assert_not_external_idp = _make_shared_compatibility_wrapper("_assert_not_external_idp")
_click_email_entry_option = _make_shared_compatibility_wrapper("_click_email_entry_option")
_is_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_is_blank_chatgpt_auth_shell")
_reload_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_reload_blank_chatgpt_auth_shell")
_email_submit_advanced_state = _make_shared_compatibility_wrapper("_email_submit_advanced_state")
_type_email_address = _make_shared_compatibility_wrapper("_type_email_address")
_submit_nearest_form_for_active_input = _make_shared_compatibility_wrapper("_submit_nearest_form_for_active_input")
_current_email_input_value = _make_shared_compatibility_wrapper("_current_email_input_value")
_stabilize_email_input_before_submit = _make_shared_compatibility_wrapper("_stabilize_email_input_before_submit")
_submit_email_form_stable = _make_shared_compatibility_wrapper("_submit_email_form_stable")
_submit_email_step = _make_shared_compatibility_wrapper("_submit_email_step")
_recover_email_submit_if_stuck = _make_shared_compatibility_wrapper("_recover_email_submit_if_stuck")
_submit_email_via_browser_nextauth = _make_shared_compatibility_wrapper("_submit_email_via_browser_nextauth")
_email_input_value_state = _make_shared_compatibility_wrapper("_email_input_value_state")
_is_email_login_page_still_present = _make_shared_compatibility_wrapper("_is_email_login_page_still_present")
_diagnostic_url = _make_shared_compatibility_wrapper("_diagnostic_url")
_redact_diagnostic_text = _make_shared_compatibility_wrapper("_redact_diagnostic_text")
_log_blank_auth_shell_diagnostics = _make_shared_compatibility_wrapper("_log_blank_auth_shell_diagnostics")
_wait_email_submit_next_state = _make_shared_compatibility_wrapper("_wait_email_submit_next_state")
_submit_email_and_wait_next = _make_shared_compatibility_wrapper("_submit_email_and_wait_next")
_type_otp = _make_shared_compatibility_wrapper("_type_otp")
_email_otp_page_state = _make_shared_compatibility_wrapper("_email_otp_page_state")
_wait_email_otp_page_ready = _make_shared_compatibility_wrapper("_wait_email_otp_page_ready")
_recover_email_otp_page_if_needed = _make_shared_compatibility_wrapper("_recover_email_otp_page_if_needed")
_email_otp_page_recovery_reason = _make_shared_compatibility_wrapper("_email_otp_page_recovery_reason")
_is_email_verification_page = _make_shared_compatibility_wrapper("_is_email_verification_page")
_clear_otp_inputs = _make_shared_compatibility_wrapper("_clear_otp_inputs")
_click_resend_email_otp = _make_shared_compatibility_wrapper("_click_resend_email_otp")
_resend_email_otp_after_failure = _make_shared_compatibility_wrapper("_resend_email_otp_after_failure")
_classify_otp_wait_failure = _make_shared_compatibility_wrapper("_classify_otp_wait_failure")
_complete_registration_totp_after_email_otp = _make_shared_compatibility_wrapper("_complete_registration_totp_after_email_otp")
_wait_after_email_otp_submit = _make_shared_compatibility_wrapper("_wait_after_email_otp_submit")
_click_continue = _make_shared_compatibility_wrapper("_click_continue")
_maybe_accept = _make_shared_compatibility_wrapper("_maybe_accept")
_page_snapshot = _make_shared_compatibility_wrapper("_page_snapshot")
_has_access_token = _make_shared_compatibility_wrapper("_has_access_token")
_is_profile_like = _make_shared_compatibility_wrapper("_is_profile_like")
_set_element_value = _make_shared_compatibility_wrapper("_set_element_value")
_select_or_type = _make_shared_compatibility_wrapper("_select_or_type")
_fill_birthday_or_age = _make_shared_compatibility_wrapper("_fill_birthday_or_age")
_generate_roxy_password = _make_shared_compatibility_wrapper("_generate_roxy_password")
_registration_password = _make_shared_compatibility_wrapper("_registration_password")
_registration_auth_mode = _make_shared_compatibility_wrapper("_registration_auth_mode")
_password_transition_timeout_seconds = _make_shared_compatibility_wrapper("_password_transition_timeout_seconds")
_password_page_state = _make_shared_compatibility_wrapper("_password_page_state")
_is_signup_password_page = _make_shared_compatibility_wrapper("_is_signup_password_page")
_is_login_password_page = _make_shared_compatibility_wrapper("_is_login_password_page")
_click_passwordless_signup_if_present = _make_shared_compatibility_wrapper("_click_passwordless_signup_if_present")
_click_signup_password_from_otp_if_present = _make_shared_compatibility_wrapper("_click_signup_password_from_otp_if_present")
_fill_password_page_if_present = _make_shared_compatibility_wrapper("_fill_password_page_if_present")
_accept_profile_consents = _make_shared_compatibility_wrapper("_accept_profile_consents")
_complete_profile_page = _make_shared_compatibility_wrapper("_complete_profile_page")
_click_if_enabled_submit = _make_shared_compatibility_wrapper("_click_if_enabled_submit")
_read_chatgpt_session_once = _make_shared_compatibility_wrapper("_read_chatgpt_session_once")
_switch_to_chatgpt_window_if_any = _make_shared_compatibility_wrapper("_switch_to_chatgpt_window_if_any")
_fetch_chatgpt_session = _make_shared_compatibility_wrapper("_fetch_chatgpt_session")
_wait_registration_homepage = _make_shared_compatibility_wrapper("_wait_registration_homepage")
_check_manual_stop = _make_shared_compatibility_wrapper("_check_manual_stop")
_probe_chatgpt_password_eligibility = _make_shared_compatibility_wrapper("_probe_chatgpt_password_eligibility")
_totp_secret_candidate = _make_shared_compatibility_wrapper("_totp_secret_candidate")
_first_visible_css = _make_shared_compatibility_wrapper("_first_visible_css")
_is_stale_element_error = _make_shared_compatibility_wrapper("_is_stale_element_error")
_visible_new_password_inputs = _make_shared_compatibility_wrapper("_visible_new_password_inputs")
_wait_visible_css = _make_shared_compatibility_wrapper("_wait_visible_css")
_detect_mfa_enrollment_step = _make_shared_compatibility_wrapper("_detect_mfa_enrollment_step")
_wait_mfa_enrollment_step = _make_shared_compatibility_wrapper("_wait_mfa_enrollment_step")
_wait_after_mfa_email_submit = _make_shared_compatibility_wrapper("_wait_after_mfa_email_submit")
_dismiss_single_action_dialog = _make_shared_compatibility_wrapper("_dismiss_single_action_dialog")
_dismiss_chatgpt_pricing_modal = _make_shared_compatibility_wrapper("_dismiss_chatgpt_pricing_modal")
_click_chatgpt_settings_control = _make_shared_compatibility_wrapper("_click_chatgpt_settings_control")
_reveal_chatgpt_settings_navigation = _make_shared_compatibility_wrapper("_reveal_chatgpt_settings_navigation")
_click_password_setting_fallback = _make_shared_compatibility_wrapper("_click_password_setting_fallback")
_open_chatgpt_security_settings = _make_shared_compatibility_wrapper("_open_chatgpt_security_settings")
_disable_roxy_2fa = _make_shared_compatibility_wrapper("_disable_roxy_2fa")
_complete_settings_email_reauth = _make_shared_compatibility_wrapper("_complete_settings_email_reauth")
set_roxy_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
_button_after_input = _make_shared_compatibility_wrapper("_button_after_input")
_read_totp_secret_from_dialog = _make_shared_compatibility_wrapper("_read_totp_secret_from_dialog")
_manual_totp_secret = _make_shared_compatibility_wrapper("_manual_totp_secret")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")
set_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")

# Constants/classes retained for old tests and integrations.  They are values
# from the shared responsibility modules, not implementations copied back into
# this compatibility surface.
_PasswordTransitionTimeout = _auth_capabilities._PasswordTransitionTimeout
_CHATGPT_HOME_URL = _auth_capabilities._mfa_auth._CHATGPT_HOME_URL
_CHATGPT_SECURITY_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_SECURITY_SETTINGS_URL
_CHATGPT_PASSWORD_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_PASSWORD_SETTINGS_URL
_MFA_EMAIL_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_EMAIL_CODE_SELECTOR
_MFA_TOTP_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_TOTP_CODE_SELECTOR

def _is_roxy_window_capacity_error(error: object) -> bool:
    """只识别明确的窗口容量错误，避免把网络/配置故障误当成可等待状态。"""
    text = str(error or "").strip().lower()
    if not text:
        return False
    markers = (
        "窗口额度不足",
        "窗口数量已达上限",
        "窗口数已达上限",
        "窗口达到上限",
        "window quota",
        "window limit",
        "maximum number of windows",
        "too many windows",
    )
    return any(marker in text for marker in markers)


def _wait_for_roxy_window_retry(seconds: float) -> None:
    """可被手动停止打断的容量等待，最多每秒检查一次停止信号。"""
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        _check_manual_stop()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1.0, remaining))


def _open_roxy_profile_with_capacity_wait(
    client,
    proxy_url: str | None,
    *,
    profile_id: str | None = None,
    progress_callback=None,
    data_saver_flow: str | None = None,
) -> RoxyOpenResult:
    """仅在 /browser/open 遇到可恢复的窗口忙时等待，避免快速消费后续任务槽位。"""
    timeout = max(0, int(getattr(_cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 900) or 0))
    interval = max(1, int(getattr(_cfg, "ROXY_WINDOW_WAIT_INTERVAL", 10) or 10))
    started = time.monotonic()
    attempt = 0

    while True:
        _check_manual_stop()
        attempt += 1
        try:
            debug_headless = None
            try:
                from core.registration_debug import current_session
                debug_session = current_session()
                # failure_only 只在最终失败时保存现场，不需要为了采集而
                # 显示浏览器窗口；只有显式全量调试才强制可见。这样普通
                # 诊断和线程池遗留的 failure_only 会话都不会覆盖无头配置。
                if getattr(debug_session, "capture_mode", "") == "full":
                    debug_headless = False
            except Exception:
                pass
            open_kwargs = {"proxy_url": proxy_url}
            if data_saver_flow is not None:
                open_kwargs["data_saver_flow"] = data_saver_flow
            if debug_headless is not None:
                open_kwargs["headless"] = debug_headless
            if profile_id is None:
                opened = client.open_profile(**open_kwargs)
            else:
                opened = client.open_profile_for_account(
                    profile_id=profile_id,
                    **open_kwargs,
                )
            if attempt > 1:
                logger.info(
                    "[Roxy注册] 已等到空闲窗口并成功启动环境：attempt=%s waited=%.1fs profile=%s",
                    attempt,
                    time.monotonic() - started,
                    opened.profile_id,
                )
            return opened
        except Exception as exc:
            if isinstance(exc, RoxyProfileQuotaExceeded):
                raise
            if not _is_roxy_window_capacity_error(exc) or timeout <= 0:
                raise

            elapsed = time.monotonic() - started
            remaining = timeout - elapsed
            if remaining <= 0:
                raise RuntimeError(
                    f"等待 Roxy 空闲窗口超时（>{timeout}s），最后错误: {str(exc)[:180]}"
                ) from exc

            delay = min(float(interval), remaining)
            detail = (
                f"Roxy 窗口已满，等待空闲名额：已等 {int(elapsed)}s，"
                f"{int(delay)}s 后重试，最长 {timeout}s"
            )
            if progress_callback is not None:
                progress_callback("browser", "running", detail)
            logger.warning(
                "[Roxy注册] %s（attempt=%s，剩余 %.1fs）：%s",
                detail,
                attempt,
                remaining,
                str(exc)[:180],
            )
            _wait_for_roxy_window_retry(delay)


def _install_registration_postprocess_data_saver(opened, driver):
    """为注册后的 2FA/账号操作切换认证规则，并由外层统一收口统计。"""
    try:
        from core.browser_flow_policy import install_for_flow

        return install_for_flow(
            "account_action",
            opened,
            driver,
            label="ChatGPT 账号操作",
        )
    except Exception:
        logger.exception("[Roxy注册] 安装注册后账号操作省流量规则失败；后续流程继续")
        return None



def _registration_otp_attempt_wait_seconds(deadline: float, attempt: int, max_attempts: int) -> int:
    """Split one total OTP budget across remaining resend attempts."""
    remaining = max(0.0, float(deadline) - time.monotonic())
    attempts_left = max(1, int(max_attempts) - int(attempt) + 1)
    return int(math.ceil(remaining / attempts_left)) if remaining > 0 else 0


def _save_roxy_account_checkpoint(
    *,
    email: str,
    access_token: str,
    session_info: dict,
    opened: RoxyOpenResult,
    openai_password: str | None,
    proxy: str | None,
    email_source: str | None = None,
    totp_secret: str | None = None,
    codex_result: dict | None = None,
    twofa_result: dict | None = None,
    registration_driver: str = "roxy",
) -> int:
    """只落库、不做套餐查询的注册检查点。"""
    from core.db import insert_account

    user = session_info.get("user") or {}
    account = session_info.get("account") or {}
    codex = codex_result or {}
    codex_status = str(codex.get("status") or "").strip() or None
    codex_error = str(codex.get("message") or "").strip() if codex_status == "failed" else None
    extra = {
        "user": user,
        "account": account,
        "expires": session_info.get("expires"),
        "roxybrowser": {
            "profile_id": opened.profile_id,
            "open_result": opened.raw,
            "retained": True,
        },
        "registration_checkpoint": "registered",
        "registration_driver": registration_driver,
        "codex": codex_result,
        "twofa": twofa_result,
    }
    # 本轮直接复用登录态时可能没有返回密码，空值不能清除账号已有凭据。
    if str(openai_password or "").strip():
        extra["account_password"] = openai_password
    twofa_status = str((twofa_result or {}).get("status") or "").strip().lower()
    if totp_secret and twofa_status in {"running", "failed"}:
        # The key is already persisted, but OpenAI has not yet been confirmed
        # enabled. Keep this checkpoint explicit so a later browser retry can
        # verify/finish enrollment instead of assuming the secret is active.
        extra["totp_setup_pending"] = True
    account_id = insert_account(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        user_id=user.get("id"),
        user_name=user.get("name"),
        plan_type=account.get("planType"),
        expires_at=session_info.get("expires"),
        proxy_used=proxy or None,
        email_source=email_source or resolve_email_source(email),
        extra=extra,
        chatgpt_session=session_info,
        codex_status=codex_status,
        codex_error=codex_error,
    )
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


def _save_pending_email_verification_checkpoint(
    *,
    email: str,
    openai_password: str,
    opened: RoxyOpenResult,
    proxy: str | None,
    email_source: str | None = None,
) -> int:
    """密码提交请求发出后立即保存待邮箱验证账号。

    OpenAI 在密码提交时已经创建邮箱身份；即使验证码邮件没有到达，本地也必须保存
    这组邮箱/密码，后续重试才能走登录流程继续收码。空 access_token 明确表示账号
    尚未完成邮箱验证，不能被套餐查询或 Codex 当成完整账号使用。
    """
    from core.registration.checkpoints import save_email_verification_checkpoint

    account_id = save_email_verification_checkpoint(
        email=email,
        password=openai_password,
        proxy=proxy,
        email_source=email_source,
        profile_metadata={
            "profile_id": opened.profile_id,
            "open_result": opened.raw,
            "retained": True,
        },
    )
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


def _run_in_isolated_browser_tab(driver, callback, *, label: str):
    """在同一浏览器 Profile 的新标签页执行操作，结束后恢复原标签页。

    Cookie 仍由同一个 Roxy Profile 共享，但 OAuth 的 URL/表单/失败页面不会覆盖
    注册完成后的 ChatGPT 标签页。callback 成功或抛错都会关闭本次新建的全部标签页。
    """
    original_handles = list(getattr(driver, "window_handles", []) or [])
    original_handle = getattr(driver, "current_window_handle", None)
    if not original_handle:
        raise RuntimeError(f"{label} 无法读取原浏览器标签页")
    if original_handle not in original_handles:
        original_handles.append(original_handle)
    original_set = set(original_handles)

    try:
        driver.switch_to.new_window("tab")
    except Exception as first_exc:
        # 兼容缺少 Selenium new_window 的浏览器适配层。
        try:
            driver.switch_to.window(original_handle)
            driver.execute_script("window.open('about:blank', '_blank');")
            end = time.time() + 5
            new_handles = []
            while time.time() < end:
                new_handles = [h for h in (getattr(driver, "window_handles", []) or []) if h not in original_set]
                if new_handles:
                    break
                time.sleep(0.1)
            if not new_handles:
                raise RuntimeError("window.open 未创建新标签页")
            driver.switch_to.window(new_handles[-1])
        except Exception as fallback_exc:
            try:
                driver.switch_to.window(original_handle)
            except Exception:
                pass
            raise RuntimeError(
                f"无法为 {label} 创建独立标签页，已停止以避免污染注册登录态："
                f"new_window={type(first_exc).__name__}: {first_exc}; "
                f"fallback={type(fallback_exc).__name__}: {fallback_exc}"
            ) from fallback_exc

    isolated_handle = getattr(driver, "current_window_handle", None)
    if not isolated_handle or isolated_handle in original_set:
        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass
        raise RuntimeError(f"{label} 独立标签页创建后句柄未变化")

    logger.info("[Roxy注册] %s 已在独立标签页启动，原 ChatGPT 标签页保持不变", label)
    try:
        return callback()
    finally:
        # callback 可能又打开 callback/popup 标签页；只关闭本次操作新增的句柄。
        try:
            current_handles = list(getattr(driver, "window_handles", []) or [])
        except Exception:
            current_handles = []
        for handle in reversed(current_handles):
            if handle in original_set:
                continue
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception as exc:
                logger.debug("[Roxy注册] 关闭 %s 新标签页失败 handle=%s: %s", label, handle, exc)
        try:
            remaining = list(getattr(driver, "window_handles", []) or [])
            target = original_handle if original_handle in remaining else next(
                (h for h in original_handles if h in remaining),
                None,
            )
            if not target:
                raise RuntimeError("原标签页已不存在")
            driver.switch_to.window(target)
            logger.info("[Roxy注册] %s 已结束并切回原 ChatGPT 标签页", label)
        except Exception as exc:
            raise RuntimeError(f"{label} 结束后无法恢复原 ChatGPT 标签页：{exc}") from exc


def run_roxy_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: str = None,
    otp_code: str = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    profile_id: str | None = None,
    registration_options: dict | None = None,
    email_source: str | None = None,
    *,
    _browser_helpers=None,
) -> dict:
    """Roxy 指纹浏览器自动化注册入口。"""
    registration_driver = _browser_helpers.driver_name if _browser_helpers is not None else "roxy"
    submit_email = (
        _browser_helpers.submit_email_and_wait_next if _browser_helpers is not None
        else _submit_email_and_wait_next
    )
    complete_profile = (
        _browser_helpers.complete_profile_page if _browser_helpers is not None
        else _complete_profile_page
    )
    if not str(proxy or "").strip():
        raise RuntimeError(
            "Roxy 注册必须使用统一代理池已领取线路，禁止无代理 Profile 或直连"
        )
    from core.registration_service import report_job_otp_evidence, report_job_progress, report_registered_account

    selected_email_source = validate_email_source(email_source) if email_source else None
    options = dict(registration_options or {})
    password_required = bool(options.get("password_enabled", _registration_auth_mode() == "password"))
    twofa_enabled = bool(options.get("twofa_enabled", _twofa_cfg.ENABLE_2FA))
    # ``dict.get`` evaluates its default argument eagerly.  Read the live
    # config only for legacy callers that did not provide a job snapshot; this
    # keeps submitted choices authoritative and avoids touching Codex config
    # while Codex is disabled.
    codex_enabled = (
        bool(options["codex_enabled"])
        if "codex_enabled" in options
        else bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False))
    )
    plan_check_enabled = bool(options.get("plan_check_enabled", True))

    from core.registration_service import registration_fact_context

    facts = registration_fact_context()
    retained = take_failed_browser(email=email, profile_id=profile_id, facts=facts)
    if retained is None:
        retained = recover_attempt_failed_browser(email=email, profile_id=profile_id, facts=facts)
    if retained is None:
        retained = recover_bound_failed_browser(email=email, profile_id=profile_id, facts=facts)
    report_job_progress("browser", "running", "正在接管原失败窗口" if retained else "正在打开或创建 Roxy 浏览器环境")
    client = RoxyBrowserClient()
    retained_driver = None
    if retained:
        retained_driver = retained.driver
        try:
            if retained_driver is None:
                raise RuntimeError("原 Selenium 连接未保存在当前进程")
            str(retained_driver.current_url)
        except Exception:
            try:
                if not _retained_profile_can_attach(client, retained.opened):
                    retained = None
                    retained_driver = None
                else:
                    # 只连接保存的原 debugger；重连的活页还需独立核验邮箱身份。
                    retained_driver = _build_driver(retained.opened)
                    retained_driver._registration_retained_identity_required = True
                    for attr in ("_browser_submission_receipt", "_browser_submission_receipts",
                                 "_registration_otp_after_ts", "_registration_otp_tracker", "_email_otp_page_refresh_done"):
                        if retained.driver is not None and hasattr(retained.driver, attr):
                            setattr(retained_driver, attr, getattr(retained.driver, attr))
            except Exception:
                if retained.driver is not None:
                    retain_failed_browser(retained.driver, retained.opened, email=email, facts=facts)
                raise RuntimeError("request_unknown: 原浏览器连接未能恢复，已保留原提交") from None
    if retained:
        # 旧 worker 已退出；沿用原连接，重新建立本轮观察器，不发送 browser/open。
        opened = copy.copy(retained.opened)
        opened.created_by_run = False
        opened.traffic_capture = None
        client.attach_retained_profile_relay(opened)
        opened.proxy_route_retained = True
    else:
        opened = _open_roxy_profile_with_capacity_wait(
            client,
            proxy,
            profile_id=profile_id,
            progress_callback=report_job_progress,
            data_saver_flow="registration",
        )
    try:
        from core import browser_traffic
        if retained:
            browser_traffic.start_roxy_capture(opened, purpose="registration")
        browser_traffic.bind_roxy_capture(
            opened,
            purpose="registration",
            registration_job_id=facts.get("job_id"),
            operation_run_id=facts.get("run_id"),
        )
    except Exception:
        logger.exception("[浏览器流量] 关联注册任务上下文失败；注册流程继续")
    if profile_id and str(opened.profile_id) != str(profile_id):
        try:
            from core.roxy_profile_binding import persist_account_profile_id

            if not persist_account_profile_id(email, opened.profile_id):
                raise RuntimeError("账号 Roxy Profile 绑定写回失败")
            opened.account_bound = True
            client.mark_profile_bound(opened.profile_id)
            logger.info("[Roxy注册] 账号绑定环境已替换为可用 Profile")
        except Exception:
            logger.exception("[Roxy注册] 回写替代 Profile 绑定失败；停止使用未绑定环境")
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[Roxy注册] 绑定失败后的替代环境清理失败")
            raise
    driver = retained_driver
    data_saver = None
    public_asset_cache = None
    postprocess_data_saver = None
    profile_discarded = False
    create_acknowledged = False
    openai_password: str | None = None
    access_token: str | None = None
    core_persisted = False
    account_id: int | None = None
    totp_secret: str | None = None
    plan_check_session = None
    remote_identity = "unknown"
    auth_challenge_chain: list[str] = []
    failed = False
    try:
        try:
            from core.registration_debug import attach_current_roxy
            attach_current_roxy(opened.debugger_address)
        except Exception:
            logger.exception("[Roxy注册][Debug] 启动浏览器网络抓包失败；注册流程继续执行")
        if bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
            if retained is not None and driver is not None:
                # 新 Selenium 连接没有旧 driver 属性；首次保存前恢复原邮件
                # 边界，避免在认证页读取失败时把持久时间覆盖为空。
                driver._registration_otp_after_ts = retained.otp_after_ts
            persist_browser_resume_context(driver, opened, email=email, facts=facts)
        if driver is None:
            driver = _build_driver(opened)
        # 认证事实共用当前 Attempt/Run；CDP 观察器只需从 driver 读取这份只读
        # 上下文，不另起消费者或在事件里复制敏感凭据。
        try:
            from core.registration_service import registration_fact_context
            driver._registration_fact_context = dict(registration_fact_context())
        except Exception:
            driver._registration_fact_context = None
        # 只有明确的 registration_resume Run 才能进入恢复登录 action scope。
        # 普通注册人工重跑即使带着旧密码，也不能借 resume_login 绕过旧未知围栏。
        resume_scope = False
        context = driver._registration_fact_context or {}
        if existing_password and context.get("run_id") is not None:
            try:
                from core.storage import registration

                run = registration.get_run(int(context["run_id"])) or {}
                resume_scope = (
                    str(run.get("action_type") or "") == "registration_resume"
                    and str(run.get("status") or "") in {"queued", "running"}
                )
            except Exception:
                logger.exception("[Roxy注册] 校验 registration_resume Run 失败，关闭恢复提交范围")
        driver._registration_resume_login = resume_scope
        from .password_auth import _install_auth_initialization_observer
        _install_auth_initialization_observer(driver)
        from core.browser_asset_policy import start_registration_asset_cache
        public_asset_cache = start_registration_asset_cache(opened, driver=driver, proxy_url=proxy)
        from core.browser_data_saver import BrowserDataSaver
        data_saver = BrowserDataSaver(label="Roxy注册")
        data_saver.install_selenium(driver)
        traffic_capture = getattr(opened, "traffic_capture", None)
        if traffic_capture is not None:
            diagnostic_observer = getattr(traffic_capture, "set_auth_diagnostic_observer", None)
            if callable(diagnostic_observer):
                diagnostic_observer(diagnostics_for(driver).observe_network)
            setter = getattr(traffic_capture, "set_data_saver", None)
            if callable(setter):
                setter(data_saver)
            observe = getattr(traffic_capture, "set_submission_observer", None)
            if callable(observe):
                observe(_make_submission_observer(driver))
        from core import registration_plan_capture
        registration_plan_capture.install_selenium(driver)
        report_job_progress("browser", "success", "Roxy 浏览器环境已启动")
        _center_browser_window(driver)
        driver.set_page_load_timeout(int(_cfg.ROXY_SELENIUM_TIMEOUT))
        try:
            driver.set_script_timeout(12)
        except Exception:
            pass
        logger.info("[Roxy注册] 开始：%s，profile=%s", email, opened.profile_id)

        verified_resume_session = None
        retained_state = None
        restart_login = False
        if retained or (resume_scope and existing_password and profile_id and str(opened.profile_id) == str(profile_id)):
            report_job_progress("page", "running", "正在核验原浏览器环境的登录态")
            verified_resume_session = _read_registration_resume_session(driver, email)
        if retained:
            retained_state = prepare_retained_resume(
                driver, email=email, existing_password=existing_password, facts=context,
                verified_session=verified_resume_session,
                otp_after_ts=retained.otp_after_ts,
            )
            existing_password = retained_state.password
            restart_login = bool(getattr(retained_state, "restart_login", False))
            if restart_login:
                logger.info("[Roxy注册] 原认证提交仍未确认，使用原邮箱和保存密码自动继续登录")
                retained_state = None
                driver._registration_otp_tracker = None
        otp_after_ts = retained.otp_after_ts if retained and not restart_login else time.time()
        if (retained_state and retained_state.page_state == PageState.OTP_EMAIL
                and retained_state.pending_otp is None and otp_after_ts is None):
            raise RuntimeError("request_unknown: 原验证码邮件时间未能核验，已保留原浏览器")
        driver._registration_otp_after_ts = otp_after_ts
        if verified_resume_session:
            report_job_progress("page", "skipped", "原环境登录态已核验，无需打开登录页")
        elif retained_state:
            report_job_progress("page", "skipped", "已接管原失败窗口，从当前认证页面继续")
        else:
            report_job_progress("page", "running", "正在打开 ChatGPT 注册页")
            logger.info("[Roxy注册] 打开登录页：https://chatgpt.com/auth/login")
            _safe_get(
                driver,
                "https://chatgpt.com/auth/login",
                timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
                attempts=2,
                accept_hosts=("chatgpt.com", "auth.openai.com"),
            )
            human_delay("navigate")
            _page_warmup(driver, reason="login_page")
            report_job_progress("page", "success", "登录页已打开，待确认邮箱入口")
            logger.info("[Roxy注册] 登录页已打开，开始确认邮箱入口")
            _maybe_accept(driver)
        _check_manual_stop()

        # 填邮箱。OpenAI UI 会随出口 IP/语言变化；这里只按 DOM 技术属性找邮箱入口，
        # 并排除 Google/Apple/Microsoft 等第三方入口，不依赖按钮可见文字。
        def _report_email_progress(phase: str, detail: str) -> None:
            report_job_progress("submit_email", "skipped" if phase == "skipped" else "running", detail)
            if phase in {"pending", "fallback"}:
                report_job_progress("auth_redirect", "running", "正在确认密码页、邮箱验证码页或登录态")

        def _mark_email_submitted() -> None:
            report_job_progress("submit_email", "success", "邮箱认证已确认进入下一步")

        if verified_resume_session:
            next_state = "authenticated"
            report_job_progress("submit_email", "skipped", "原环境登录态已核验，无需再次提交邮箱")
            report_job_progress("auth_redirect", "skipped", "原环境登录态已核验，无需认证跳转")
        elif retained_state:
            next_state = {
                PageState.PASSWORD_CREATE: "password", PageState.PASSWORD_LOGIN: "login_password",
                PageState.OTP_EMAIL: "otp", PageState.PROFILE: "profile",
                PageState.MFA_TOTP: "totp", PageState.EMAIL_VERIFIED: "email_verified",
            }.get(retained_state.page_state, "authenticated")
            report_job_progress("submit_email", "skipped", "已核验原任务窗口，无需再次提交邮箱")
            report_job_progress("auth_redirect", "skipped", "从原窗口当前认证步骤继续")
        else:
            report_job_progress("submit_email", "running", "正在等待可见的邮箱输入框")
            next_state = submit_email(
                driver,
                email,
                attempts=3,
                on_submitted=_mark_email_submitted,
                allow_login_password=resume_scope,
                on_progress=_report_email_progress,
            )
        remote_identity = classify_registration_identity(next_state)
        _check_manual_stop()
        # 只要已经到达 OpenAI 的密码/OTP 等下一页，认证跳转就已经完成。密码创建是
        # 独立业务阶段，不能继续挂在 auth_redirect 上导致失败原因误导。
        if not verified_resume_session and not retained_state:
            report_job_progress("auth_redirect", "success", f"已进入认证下一步：{next_state}")

        # 新版注册流可能先进入 /create-account/password；参考 FlowPilot 的 fill-password 步骤，
        # 先设置密码并提交，然后再等待邮箱验证码页。
        password_stage_expected = password_required or bool(existing_password)
        if verified_resume_session:
            password_progress_detail = "原环境登录态已核验，保留原密码且无需再次提交"
        elif existing_password:
            password_progress_detail = "正在继续待验证账号的登录流程"
        elif password_required:
            password_progress_detail = "正在创建并确认账号密码"
        else:
            password_progress_detail = "一次性验证码模式，无需创建账号密码"
        report_job_progress(
            "login_password",
            "running" if password_stage_expected and not verified_resume_session else "skipped",
            password_progress_detail,
        )

        password_submitted_this_run = False
        password_prepared_this_run = False

        def _checkpoint_prepared_password(password: str) -> None:
            """在异步密码点击前保存原密码，供同一 Attempt 续跑。"""
            nonlocal password_prepared_this_run
            password_prepared_this_run = True
            try:
                from core.registration.checkpoints import save_protocol_password_checkpoint

                save_protocol_password_checkpoint(
                    email=email, password=password, state="prepared", proxy=proxy,
                    email_source=selected_email_source,
                )
            except Exception:
                # 生产浏览器入口没有 Attempt 就不能证明原密码已持久化；
                # 只有测试/显式旧适配器标记允许继续，避免异步点击后丢失恢复凭据。
                context = getattr(driver, "_registration_fact_context", {}) or {}
                if context.get("attempt_id") is not None or not getattr(driver, "_registration_legacy_compat", False):
                    raise

        def _checkpoint_submitted_password(password: str) -> None:
            nonlocal password_submitted_this_run
            password_submitted_this_run = True
            try:
                from core.registration.checkpoints import save_protocol_password_checkpoint

                save_protocol_password_checkpoint(
                    email=email, password=password, state="started", proxy=proxy,
                    email_source=selected_email_source,
                )
            except Exception:
                context = getattr(driver, "_registration_fact_context", {}) or {}
                if context.get("attempt_id") is not None or not getattr(driver, "_registration_legacy_compat", False):
                    raise

        try:
            if verified_resume_session or (retained_state and retained_state.page_state not in {
                PageState.PASSWORD_CREATE, PageState.PASSWORD_LOGIN,
            }):
                openai_password = existing_password
            else:
                openai_password = _fill_password_page_if_present(
                    driver,
                    email,
                    timeout=120,
                    existing_password=existing_password,
                    on_password_prepared=_checkpoint_prepared_password,
                    on_password_submitted=_checkpoint_submitted_password,
                ) or existing_password
        except _PasswordTransitionTimeout:
            report_job_progress("login_password", "failed", "已触发密码提交操作，远端结果仍待确认")
            raise
        except Exception as exc:
            if password_stage_expected and not verified_resume_session:
                report_job_progress("login_password", "failed", f"账号密码处理失败: {type(exc).__name__}: {str(exc)[:180]}")
            raise
        else:
            if password_stage_expected and not verified_resume_session:
                if password_submitted_this_run:
                    password_result_state = "success"
                    password_result_detail = "账号密码已提交并进入下一步"
                elif existing_password and openai_password and _is_email_verification_page(driver):
                    password_result_state = "success"
                    password_result_detail = "已复用待验证账号的密码信息；本次直接进入邮箱验证码，未重新提交密码"
                else:
                    password_result_state = "success" if openai_password else "skipped"
                    password_result_detail = (
                        "当前认证流先验证邮箱，但密码流程未返回新密码"
                        if _is_email_verification_page(driver)
                        else "密码流程未返回新密码"
                    )
                report_job_progress(
                    "login_password",
                    password_result_state,
                    password_result_detail,
                )
        if not verified_resume_session and (existing_password or openai_password):
            auth_challenge_chain.append("password")
        if not verified_resume_session and openai_password and account_id is None:
            account_id = _save_pending_email_verification_checkpoint(
                email=email,
                openai_password=openai_password,
                opened=opened,
                proxy=proxy,
                email_source=selected_email_source,
            )
            report_registered_account(account_id)
            create_acknowledged = True
            logger.info(
                "[Roxy注册] 密码已提交，待邮箱验证账号检查点已保存：id=%s email=%s resume=%s",
                account_id,
                email,
                bool(existing_password),
            )
        resume_login_state = ""
        # 会话失效后的新登录必须按新的邮件时间收码，不能沿用原表单的邮件边界。
        otp_after_ts = getattr(driver, "_registration_otp_after_ts", otp_after_ts)
        if existing_password and not verified_resume_session and not retained_state:
            # 密码提交后可能进入邮箱 OTP，也可能进入 Authenticator TOTP。
            # 两种页面外观相似，必须与 Codex OAuth 共用同一个认证状态机。
            from core.roxy_codex_oauth import complete_openai_login_challenge

            resume_kwargs = {"timeout": 45}
            if password_submitted_this_run:
                resume_kwargs["password_already_submitted"] = True
            if selected_email_source is not None:
                resume_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                    address,
                    email_source=selected_email_source,
                    **kwargs,
                )
            resume_login_state = complete_openai_login_challenge(
                driver,
                email,
                existing_password,
                str(existing_totp_secret or ""),
                **resume_kwargs,
            )
            logger.info(
                "[Roxy注册] 待验证账号公共登录状态机完成：email=%s state=%s",
                email,
                resume_login_state,
            )
        _check_manual_stop()

        if not verified_resume_session:
            report_job_progress("email_otp", "running", "正在等待并验证邮箱验证码")
            report_job_otp_evidence(
                request_kind="resume_login" if existing_password else "initial",
                ui_ack="unconfirmed",
                detail="页面已进入邮箱验证码步骤，但仅凭页面状态不能确认邮件请求已被接受",
            )
        last_otp_ui_ack = "unconfirmed"
        current_otp = otp_code
        submitted_otps = getattr(driver, "_registration_otp_tracker", None) if retained else None
        if not isinstance(submitted_otps, _OtpAttemptTracker):
            submitted_otps = _OtpAttemptTracker()
        driver._registration_otp_tracker = submitted_otps
        max_otp_attempts = 3
        try:
            from config import email as _email_cfg
            otp_total_wait = max(1, int(getattr(_email_cfg, "OTP_MAX_WAIT", 240) or 240))
        except Exception:
            otp_total_wait = 240
        otp_budget = StageBudget.start(otp_total_wait)
        otp_wait_deadline = otp_budget.deadline
        otp_already_complete = (
            bool(verified_resume_session)
            or bool(retained_state and retained_state.page_state in {PageState.PROFILE, PageState.EMAIL_VERIFIED})
            or resume_login_state == "advanced" or _has_access_token(driver)
        )
        if retained_state and retained_state.pending_otp:
            # 未确认的原 POST 只观察同一回执；不进入收码、填码或重发分支。
            outcome = _wait_after_email_otp_submit(driver, timeout=60, budget=otp_budget, expected_email=email)
            if outcome == "session_expired":
                raise RuntimeError("request_unknown: auth_session_unavailable: 原验证码页认证会话不可用，已保留原 Attempt，需沿用原身份重新登录")
            if outcome not in {"accepted", "email_verified", "totp_required"}:
                raise RuntimeError("request_unknown: otp_request_unconfirmed: 原验证码提交仍未确认，已保留原窗口，未重新填码或重发")
            # 观察期间页面可能变更；同源页面/完整会话再次核验后才收口原回执。
            otp_budget.require("原验证码提交再次核验")
            verified_resume_session = _read_registration_resume_session(driver, email, budget=otp_budget)
            retained_state = prepare_retained_resume(
                driver, email=email, existing_password=existing_password, facts=context,
                verified_session=verified_resume_session,
                otp_after_ts=getattr(driver, "_registration_otp_after_ts", otp_after_ts),
            )
            if retained_state.pending_otp is not None or retained_state.page_state not in {
                PageState.PROFILE, PageState.EMAIL_VERIFIED, PageState.MFA_TOTP, PageState.AUTHENTICATED,
            }:
                raise RuntimeError("request_unknown: 原验证码提交未能再次核验，已保留原窗口")
            if retained_state.page_state == PageState.MFA_TOTP:
                _complete_registration_totp_after_email_otp(
                    driver, email, existing_password, existing_totp_secret, budget=otp_budget,
                )
                remote_identity = "existing"
                auth_challenge_chain.append("totp")
            otp_already_complete = True
            auth_challenge_chain.append("email_otp")
        for otp_attempt in range(1, max_otp_attempts + 1):
            if otp_already_complete:
                break
            ready_outcome = _wait_email_otp_page_ready(driver, budget=otp_budget)
            if ready_outcome in {"stuck", "session_expired"}:
                failure_code = "auth_session_unavailable" if ready_outcome == "session_expired" else "otp_request_unconfirmed"
                failure_detail = ("验证码页认证会话不可用；保留原 Attempt，需沿用原身份重新登录，未填码或追加重发"
                                  if ready_outcome == "session_expired" else
                                  "验证码页表单未就绪，受限恢复后仍未确认；保留原 Attempt，本轮未追加重发")
                latest_submission = getattr(driver, "_browser_submission_receipt", None)
                if isinstance(latest_submission, BrowserSubmissionReceipt) and latest_submission.endpoint_kind == "otp_resend":
                    status = latest_submission.http_status
                    failure_detail += (f"；此前已尝试重发，接口 HTTP {status}" if status is not None
                                       else "；此前已尝试重发，接口结果未确认")
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            if ready_outcome == "totp_required":
                remote_identity = "existing"
                post_otp_state = _complete_registration_totp_after_email_otp(
                    driver, email, existing_password, existing_totp_secret,
                    timeout=min(45, otp_budget.require("邮箱验证后 TOTP")),
                    budget=otp_budget,
                )
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                if "totp" not in auth_challenge_chain:
                    auth_challenge_chain.append("totp")
                resume_login_state = "advanced"
                break
            if ready_outcome in ("accepted", "email_verified"):
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                break
            if current_otp is None:
                if otp_after_ts is None:
                    raise RuntimeError("request_unknown: 原验证码邮件时间未能核验，已保留原窗口，未收码或重发")
                logger.info("[Roxy注册][OTP] 等待验证码：%s（第 %s/%s 次）", email, otp_attempt, max_otp_attempts)
                try:
                    attempt_wait = _registration_otp_attempt_wait_seconds(
                        otp_wait_deadline,
                        otp_attempt,
                        max_otp_attempts,
                    )
                    otp_budget.require("email OTP")
                    if attempt_wait <= 0:
                        raise TimeoutError(f"邮箱验证码总等待已达到 {otp_total_wait}s")
                    otp_kwargs = {
                        "after_ts": otp_after_ts,
                        "max_wait": attempt_wait,
                    }
                    if selected_email_source is not None:
                        otp_kwargs["email_source"] = selected_email_source
                    # 将同一份 240 秒总预算传入邮箱 provider；provider 内部会
                    # 通过 mailbox_wait 裁剪实际 HTTP/IMAP I/O，不能只限制外层
                    # Python 循环的 max_wait。
                    current_otp = wait_for_otp(email, budget=otp_budget, **otp_kwargs)
                except Exception as exc:
                    if otp_attempt >= max_otp_attempts:
                        failure_code, failure_detail = _classify_otp_wait_failure(
                            exc,
                            last_ui_ack=last_otp_ui_ack,
                        )
                        report_job_otp_evidence(
                            detail=failure_detail,
                            failure_code=failure_code,
                        )
                        report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                        raise RuntimeError(f"{failure_code}: {failure_detail}") from exc
                    # 不再用 after_ts=0 宽松捞旧码。高并发/重发场景下，旧码可能
                    # 属于同一邮箱的上一轮认证，提交后只会造成额外等待和再次重发。
                    logger.warning(
                        "[Roxy注册][OTP] 单轮等待结束仍未收到新验证码，重新发送后只等待新邮件（下一轮 %s/%s）：%s: %s",
                        otp_attempt + 1,
                        max_otp_attempts,
                        type(exc).__name__,
                        str(exc)[:180],
                    )
                    try:
                        resend_result = _resend_email_otp_after_failure(
                            driver,
                            reason="等待邮箱验证码超时/未收到新验证码",
                            budget=otp_budget,
                        )
                    except Exception as resend_exc:
                        failure_code = "otp_request_unconfirmed"
                        failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
                        report_job_otp_evidence(
                            request_kind="resend",
                            ui_ack="rejected",
                            detail=failure_detail,
                            failure_code=failure_code,
                        )
                        report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                        raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
                    otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
                    driver._registration_otp_after_ts = otp_after_ts
                    last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                    report_job_otp_evidence(
                        request_kind="resend",
                        ui_ack=last_otp_ui_ack,
                        detail="等待超时后请求重新发送验证码",
                    )
                    human_delay("api", budget=otp_budget)
                    current_otp = None
                    continue
            if not submitted_otps.accept(current_otp):
                failure_detail = "收码器返回了本次运行已经提交过的验证码，拒绝重复提交"
                logger.warning("[Roxy注册][OTP] %s", failure_detail)
                if otp_attempt >= max_otp_attempts:
                    failure_code = "otp_reused_after_resend"
                    report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}")
                try:
                    resend_result = _resend_email_otp_after_failure(
                        driver,
                        reason=failure_detail,
                        budget=otp_budget,
                    )
                except Exception as resend_exc:
                    failure_code = "otp_request_unconfirmed"
                    failure_detail = "重复验证码已拒绝，但验证码重发控件未能完成或缺少确认"
                    report_job_otp_evidence(
                        request_kind="resend",
                        ui_ack="rejected",
                        detail=failure_detail,
                        failure_code=failure_code,
                    )
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
                otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
                driver._registration_otp_after_ts = otp_after_ts
                last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                report_job_otp_evidence(
                    request_kind="resend",
                    ui_ack=last_otp_ui_ack,
                    detail="拒绝重复验证码后请求重新发送",
                )
                human_delay("api", budget=otp_budget)
                current_otp = None
                continue
            logger.info("[Roxy注册][OTP] 已收到验证码")
            # 某些验证码控件在最后一位输入后可能自动提交；因此在清空/填写
            # 之前先落库本次提交意图和页面基线，任何自动提交都归属于本回执。
            otp_submission = BrowserSubmissionReceipt(
                kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "otp",
                stage="email_otp", endpoint_kind="otp_submit", http_method="POST",
            )
            driver._browser_submission_receipt = otp_submission
            record_browser_submission_fact(driver, "prepared", receipt=otp_submission)
            record_browser_submission_fact(driver, "dispatch_intent", receipt=otp_submission)
            log_submission_diagnostics(driver, "otp", "before_submit", receipt=otp_submission)
            try:
                otp_submit_baseline = _email_otp_page_state(driver)
            except Exception:
                otp_submit_baseline = {}
            _clear_otp_inputs(driver)
            otp_input_timeout = _budget_timeout(otp_budget, 20, minimum=1)
            if otp_input_timeout < 1:
                raise StageTimeout("email OTP input budget exhausted")
            _type_otp(
                driver, current_otp, timeout=max(1, int(otp_input_timeout)),
                before_input=lambda inputs: _prepare_email_otp_current_form(driver, inputs, budget=otp_budget),
            )
            logger.info("[Roxy注册][OTP] 已填写邮箱验证码")
            _check_manual_stop()
            # OTP 页面已经确认可提交；保留极短的人类化停顿，但不要让默认
            # 的“切回邮箱/阅读验证码”长区间拖慢每个批次。
            human_delay("otp_input", minimum=0.35, maximum=1.0, budget=otp_budget)
            try:
                otp_click = _submit_email_otp_current_form(driver)
                if otp_click.get("clicked") is True:
                    record_browser_submission_fact(driver, "ui_dispatched", receipt=otp_submission)
                    logger.info("[Roxy注册][OTP] 已点击当前验证码表单，等待资料页或登录态")
                else:
                    logger.info("[Roxy注册][OTP] 未追加点击，继续确认原验证码输入结果：reason=%s", otp_click.get("reason"))
            except Exception as exc:
                # 点击回调抛错不能证明没有派发；保守保留未知围栏，禁止同一候选重放。
                record_browser_submission_fact(
                    driver, "unknown", receipt=otp_submission, result="unknown",
                    error_type=type(exc).__name__,
                )
                logger.info("[Roxy注册][OTP] 未找到显式提交按钮，继续等待页面状态：%s", str(exc)[:120])

            outcome = _wait_after_email_otp_submit(
                driver, timeout=60, budget=otp_budget,
                baseline_state=otp_submit_baseline,
                expected_email=email,
            )
            if outcome in ("accepted", "email_verified", "totp_required"):
                record_browser_submission_fact(driver, "confirmed", receipt=otp_submission, result="success")
            elif outcome == "invalid":
                record_browser_submission_fact(driver, "rejected", receipt=otp_submission, result="failure")
            elif outcome in {"stuck", "session_expired"}:
                # 60 秒确认截止仍未知时，不能把停页解释为验证码错误并重发。
                record_browser_submission_fact(driver, "unknown", receipt=otp_submission,
                                               result="unknown" if outcome == "session_expired" else "timeout")
                failure_code = "auth_session_unavailable" if outcome == "session_expired" else "otp_request_unconfirmed"
                failure_detail = ("验证码提交后的认证会话不可用；保留原提交和原 Attempt，需沿用原身份重新登录，未追加提交或重发"
                                  if outcome == "session_expired" else
                                  "验证码提交可能已派发，但 60 秒内未确认结果；保留原 Attempt，未自动重发")
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            if outcome == "totp_required":
                # A TOTP challenge after email verification proves that this
                # address is continuing an existing account authentication;
                # it must never fall through to the new-account profile page.
                remote_identity = "existing"
                post_otp_state = _complete_registration_totp_after_email_otp(
                    driver,
                    email,
                    existing_password,
                    existing_totp_secret,
                    budget=otp_budget,
                )
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                if "totp" not in auth_challenge_chain:
                    auth_challenge_chain.append("totp")
                resume_login_state = "advanced"
                break
            if outcome in ('accepted', 'email_verified'):
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                break
            if otp_attempt >= max_otp_attempts:
                failure_code = "otp_invalid_or_expired"
                failure_detail = "已取得并提交验证码，但页面未接受或验证码已过期"
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            logger.warning("[Roxy注册][OTP] 验证码错误/过期，准备重新发送并重新获取验证码（%s/%s）", otp_attempt + 1, max_otp_attempts)
            try:
                resend_result = _resend_email_otp_after_failure(
                    driver,
                    reason="邮箱验证码提交后页面无效或卡住",
                    budget=otp_budget,
                )
            except Exception as resend_exc:
                failure_code = "otp_request_unconfirmed"
                failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
                report_job_otp_evidence(
                    request_kind="resend",
                    ui_ack="rejected",
                    detail=failure_detail,
                    failure_code=failure_code,
                )
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
            otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
            driver._registration_otp_after_ts = otp_after_ts
            last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
            report_job_otp_evidence(
                request_kind="resend",
                ui_ack=last_otp_ui_ack,
                detail="验证码无效或页面未推进后请求重新发送",
            )
            human_delay("api", budget=otp_budget)
            current_otp = None

        report_job_progress(
            "email_otp",
            "skipped" if otp_already_complete else "success",
            "已有登录态，无需再次验证邮箱" if otp_already_complete else "邮箱验证码已通过",
        )
        # about-you / profile 信息页：必须完成或确认已有登录态，不能静默跳过。
        _check_manual_stop()
        profile_submitted = False
        if not verified_resume_session:
            report_job_progress("profile", "running", "正在填写账号资料")
            logger.info("[Roxy注册] 开始等待资料页/登录态")
            profile_submitted = complete_profile(
                driver,
                name,
                birthday,
                timeout=60,
                expected_email=email,
                transition_timeout=90,
            )
        if profile_submitted:
            remote_identity = "new_candidate"
            create_acknowledged = True
            # 给 OAuth 回调 / session cookie 写入一点时间。
            # 资料页已离开后，token 阶段仍会独立等待 session；这里只保留
            # 很短的 cookie 落盘缓冲，不改变任何认证等待预算。
            human_delay("post_auth", minimum=0.25, maximum=0.8)
            report_job_progress("profile", "success", "账号资料已提交")
        else:
            remote_identity = "existing"
            report_job_progress("profile", "skipped", "已有登录态，无需填写资料")

        report_job_progress("token", "running", "正在等待登录态并获取 Token")
        logger.info("[Roxy注册] 等待 ChatGPT 跳转并写入 session/accessToken")
        _check_manual_stop()
        token_budget = StageBudget.start(120)
        lightweight_post_auth = bool(data_saver is not None and data_saver.enabled)
        session_info = verified_resume_session or _fetch_chatgpt_session(
            driver, timeout=120, budget=token_budget, prefer_homepage=not lightweight_post_auth,
        )
        _validate_registration_session_identity(session_info, email)
        access_token = session_info["accessToken"]
        logger.info("[Roxy注册] 已拿到 accessToken：%s", email)

        # 注册主体到这里已经成功。先保存账号、随机登录密码和 Token，并立即绑定任务；
        # 再响应停止请求或查询套餐，避免后续操作中断时丢失已经核验的完整会话。
        from core.registration_service import persist_registration_core

        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            chatgpt_session=session_info,
            email_source=selected_email_source or resolve_email_source(email),
            proxy_used=proxy or None,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "roxybrowser": {
                    "profile_id": opened.profile_id,
                    "open_result": opened.raw,
                    "retained": True,
                },
                **({"account_password": openai_password} if str(openai_password or "").strip() else {}),
                "registration_checkpoint": "core_persisted",
                "registration_driver": registration_driver,
            },
        )
        core_persisted = True
        opened.account_bound = True
        client.mark_profile_bound(opened.profile_id)
        logger.info("[Roxy注册] 注册主体已保存检查点：id=%s email=%s", account_id, email)

        _check_manual_stop()
        # 先保留首页自然返回的权益快照，避免后续安全设置导航清空页面内缓存。
        # 此处不等待、不主动请求；需要补查时统一计入最后的套餐阶段。
        captured_plan_result = None
        if plan_check_enabled and lightweight_post_auth:
            captured_plan_result = registration_plan_capture.read_selenium(driver, access_token, wait_seconds=0)

        if lightweight_post_auth:
            from .session_auth import _park_verified_registration_page

            data_saver.activate_post_auth()
            parked = _park_verified_registration_page(driver, budget=token_budget, check_stop=_check_manual_stop)
            logger.info("[Roxy注册] 省流量后处理：轻量同源页面=%s，跳过完整首页加载", parked)
            report_job_progress("token", "success", "已保存完整登录会话，省流量模式跳过完整首页加载")
        else:
            report_job_progress("token", "running", "登录会话已保存，正在确认正常首页就绪")
            try:
                homepage = _wait_registration_homepage(driver, budget=token_budget)
            except StageTimeout:
                # 会话已保存；可选首页观察不能成为再次注册的理由。
                homepage = {"ready": False, "reason": "timeout"}
            if homepage["ready"]:
                if data_saver is not None:
                    data_saver.activate_post_auth()
                report_job_progress("token", "success", "已获取 accessToken，正常首页已就绪")
            else:
                logger.warning("[Roxy注册] 首页未确认就绪，保持核心资源加载：reason=%s", homepage["reason"])
                report_job_progress("token", "success", "已获取 accessToken；首页未确认就绪，保持核心资源加载")
            if plan_check_enabled:
                captured_plan_result = registration_plan_capture.read_selenium(driver, access_token, wait_seconds=0)

        codex_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_CODEX_AUTO=False，跳过 Codex",
        }
        try:
            if codex_enabled:
                report_job_progress("codex", "running", "正在执行 Codex OAuth")
                # 注册流程本身已创建 Roxy 一号一环境。这里不能再新建第二个 Roxy 环境；
                # 复用当前注册窗口并保留刚建立的登录态，直接开始 Codex 授权。
                from core.roxy_codex_oauth import run_roxy_codex_oauth
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=True，复用当前注册 Roxy 窗口执行 Codex 授权，不创建新环境")
                _check_manual_stop()
                codex_kwargs = {}
                if selected_email_source is not None:
                    codex_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                        address,
                        email_source=selected_email_source,
                        **kwargs,
                    )
                codex_result = _run_in_isolated_browser_tab(
                    driver,
                    lambda: run_roxy_codex_oauth(
                        email,
                        proxy=proxy,
                        reuse_existing_profile=True,
                        existing_driver=driver,
                        existing_opened=opened,
                        force=True,
                        # 当前 Roxy 环境刚完成这个账号的注册，保留登录态可直接进入
                        # consent/手机验证；若登录态不可复用，页面仍会回落到邮箱 OTP。
                        clear_existing_state=False,
                        **codex_kwargs,
                    ),
                    label="Codex OAuth",
                )
                report_job_progress(
                    "codex",
                    "success" if codex_result.get("ok") else "failed",
                    str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
                )
            else:
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=False，注册后跳过 Codex OAuth")
                report_job_progress("codex", "skipped", "未启用 Codex 自动授权")
        except AccountUnusableError:
            raise
        except Exception as exc:
            codex_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            report_job_progress("codex", "failed", codex_result["message"])

        browser_twofa_prepared = False

        def _prepare_browser_twofa():
            nonlocal postprocess_data_saver, browser_twofa_prepared
            # 只有实际进入浏览器设置时才恢复核心资源，协议成功不启动首页。
            browser_twofa_prepared = True
            postprocess_data_saver = _install_registration_postprocess_data_saver(
                opened,
                driver,
            )

        # 先跑 Codex，最大化复用注册完成后的 auth.openai.com 账号选择态；
        # 未完成的 MFA enrollment 会改变授权页状态，不能放在 Codex 前面。
        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            proxy=proxy,
            email_source=selected_email_source,
            codex_result=codex_result,
            registration_driver=registration_driver,
        )
        report_registered_account(account_id)

        twofa_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_2FA=False，跳过 Authenticator 2FA",
        }
        if twofa_enabled:
            report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
            try:
                def _checkpoint_totp_secret(secret: str) -> None:
                    nonlocal account_id, totp_secret
                    totp_secret = secret
                    account_id = _save_roxy_account_checkpoint(
                        email=email,
                        access_token=access_token,
                        session_info=session_info,
                        opened=opened,
                        openai_password=openai_password,
                        proxy=proxy,
                        email_source=selected_email_source,
                        totp_secret=totp_secret,
                        codex_result=codex_result,
                        registration_driver=registration_driver,
                        twofa_result={
                            "status": "running",
                            "ok": False,
                            "message": "已保存 Authenticator key，正在激活 2FA",
                        },
                    )
                    report_registered_account(account_id)
                    logger.info("[Roxy注册][2FA] Authenticator key 已写入账号检查点，准备激活")

                twofa_driver = _twofa_cfg.get_twofa_driver_for_options(options)
                twofa_kwargs = {"on_secret": _checkpoint_totp_secret}
                if selected_email_source is not None:
                    twofa_kwargs["otp_provider"] = lambda address, **kwargs: wait_for_otp(
                        address,
                        email_source=selected_email_source,
                        **kwargs,
                    )
                if twofa_driver == "protocol":
                    protocol_session = BrowserSession(proxy=proxy or "")
                    plan_check_session = protocol_session
                    totp_secret, fallback_used = setup_protocol_2fa_with_browser_fallback(
                        driver,
                        email,
                        protocol_session,
                        access_token,
                        before_browser=_prepare_browser_twofa,
                        **twofa_kwargs,
                    )
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": (
                            "协议失败后已通过浏览器 UI 启用 2FA"
                            if fallback_used
                            else "协议 2FA 已启用"
                        ),
                        "driver": "browser_fallback" if fallback_used else "protocol",
                    }
                else:
                    _prepare_browser_twofa()
                    totp_secret = setup_roxy_2fa(driver, email, **twofa_kwargs)
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": "浏览器 2FA 已启用",
                        "driver": "browser",
                    }
                report_job_progress("twofa", "success", twofa_result["message"])
            except Exception as exc:
                message = f"{type(exc).__name__}: {str(exc)[:180]}"
                twofa_result = {"status": "failed", "ok": False, "message": message}
                logger.error("[Roxy注册][2FA] 设置失败：%s", message)
                logger.debug("[Roxy注册][2FA] 错误详情", exc_info=True)
                report_job_progress("twofa", "failed", f"2FA 设置失败: {message}")
        else:
            report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            proxy=proxy,
            email_source=selected_email_source,
            totp_secret=totp_secret,
            codex_result=codex_result,
            twofa_result=twofa_result,
            registration_driver=registration_driver,
        )
        report_registered_account(account_id)

        if lightweight_post_auth and browser_twofa_prepared and twofa_result.get("ok"):
            # 设置已确认并保存；保留窗口也不继续加载设置页的后台资源。
            _park_verified_registration_page(driver, budget=StageBudget.start(10), check_stop=_check_manual_stop)

        # Final account metadata is updated by the existing checkpoint helper.
        # Plan lookup is independent work and is queued after the core account
        # has already been persisted, so a network failure cannot roll back
        # registration success.
        plan_result = {"status": "pending", "ok": False, "message": "套餐查询已独立入队"}
        if plan_check_enabled:
            _check_manual_stop()
            report_job_progress("plan_check", "running", "正在查询注册会话中的套餐与 Plus 优惠资格")
            plan_started = time.monotonic()
            try:
                # 在同一个阶段完成套餐捕获与额度读取，计时不再跨越首页观察和 2FA。
                try:
                    if captured_plan_result is None:
                        captured_plan_result = registration_plan_capture.read_or_fetch_selenium(driver, access_token)
                except Exception as exc:
                    logger.warning("[Roxy注册][套餐] 浏览器查询失败，将尝试后台查询：%s", type(exc).__name__)
                from core import db
                if isinstance(captured_plan_result, dict) and captured_plan_result.get("ok"):
                    captured = dict(captured_plan_result)
                    if not captured.get("quota_status"):
                        from core.chatgpt_plan import query_account_quota
                        captured.update(query_account_quota(
                            access_token,
                            proxy=proxy or None,
                            session=plan_check_session,
                        ))
                    captured["trigger"] = "registration_browser_response"
                    db.update_account_plan_check(acc_id=account_id, result=captured)
                    plan_result = {"status": "success", "ok": True, "message": "复用浏览器权益数据"}
                else:
                    from core.plan_check_service import enqueue_account_plan_check
                    queued = enqueue_account_plan_check(
                        account_id=account_id,
                        email=email,
                        access_token=access_token,
                        trigger="registration_auto",
                    )
                    plan_result = {
                        "status": "pending" if queued.get("accepted") or queued.get("busy") else "failed",
                        "ok": False,
                        "message": (
                            "套餐查询已提交后台任务，等待查询结果"
                            if queued.get("accepted")
                            else "账号已有套餐查询，等待查询结果"
                            if queued.get("busy")
                            else str(queued.get("error") or "套餐查询未入队")
                        ),
                    }
            except Exception as exc:
                plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            finally:
                source = (captured_plan_result or {}).get("source", "browser_response") if isinstance(captured_plan_result, dict) else "background_queue"
                logger.info("[Roxy注册][套餐] 本轮查询结束：耗时=%.3fs 来源=%s 状态=%s",
                            max(0.0, time.monotonic() - plan_started), source, plan_result["status"])
        else:
            plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}
        if plan_check_enabled:
            report_job_progress(
                "plan_check",
                plan_result["status"] if plan_result["status"] in {"success", "failed"} else "pending",
                plan_result["message"],
            )
        codex_ok = codex_result.get("ok") or codex_result.get("status") == "skipped"
        twofa_ok = twofa_result.get("ok") or twofa_result.get("status") == "skipped"
        errors = []
        if not codex_ok:
            errors.append(f"Codex 未完成: {codex_result.get('message')}")
        if not twofa_ok:
            errors.append(f"2FA 未完成: {twofa_result.get('message')}")
        if not plan_result.get("ok"):
            errors.append(f"套餐查询待处理: {plan_result.get('message')}")
        postprocess_ok = bool(codex_ok and twofa_ok and plan_result.get("ok"))
        from core.registration_postprocess import summarize_postprocess
        readiness = summarize_postprocess(
            core_success=True,
            password_present=bool(openai_password),
            outcomes={"twofa": twofa_result, "codex": codex_result, "plan_check": plan_result},
            password_required=password_required,
            twofa_required=twofa_enabled,
            codex_enabled=codex_enabled,
            plan_check_required=plan_check_enabled,
        )
        return {
            # 账号和 Token 已在前面的检查点落库，注册主体就是成功。Codex/2FA
            # 属于后置能力，失败时返回部分成功，不能让服务层误判为“没注册出账号”。
            "success": True,
            "registration_success": True,
            "core_persisted": core_persisted,
            "postprocess_success": postprocess_ok,
            "partial_success": not postprocess_ok,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "codex": codex_result,
            "twofa": twofa_result,
            "plan_check": plan_result,
            "next_actions": [action.as_dict() for action in readiness.next_actions],
            "account_readiness": readiness.account_readiness,
            "remote_identity": remote_identity,
            "remote_identity_state": "confirmed",
            "registration_intent": "reconcile" if remote_identity == "existing" else "new",
            "auth": auth_result_for_registration(
                {"success": True},
                auth_method=registration_driver,
                remote_identity=remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": None if not errors else "; ".join(errors),
        }
    except Exception as exc:
        failed = True
        logger.error("[Roxy注册] 失败：%s: %s", type(exc).__name__, exc)
        logger.debug("[Roxy注册] 失败详情", exc_info=True)
        try:
            from core.registration_service import is_stop_requested
            stopped = is_stop_requested()
        except Exception:
            stopped = False
        if not stopped:
            try:
                if driver is not None:
                    log_submission_diagnostics(driver, diagnostics_for(driver).stage, "final_failure",
                                               receipt=getattr(driver, "_browser_submission_receipt", None))
                from core.registration_debug import pause_current_failure
                pause_current_failure(driver, f"{type(exc).__name__}: {str(exc)[:500]}")
            except Exception:
                logger.exception("[Roxy注册][Debug] 保留失败现场失败；继续按原失败流程收口")
        # 未确认创建前通常可以回收邮箱；但 password 模式下缺少创建密码入口时，
        # 该地址可能已经在 OpenAI 侧进入已有账号/半成品账号状态。继续放回池里只会
        # 让后续任务反复命中登录 OTP 页，永远无法完成“账号+密码”注册。
        password_result_unknown = isinstance(exc, _PasswordTransitionTimeout)
        email_result_unknown = isinstance(exc, _EmailSubmissionUnknown)
        error_text = str(exc)
        account_unusable = isinstance(exc, AccountUnusableError)
        pre_account_transport_failure = _is_disposable_pre_account_failure(
            error_text,
            create_acknowledged=create_acknowledged,
            account_id=account_id,
        ) and not (password_result_unknown or email_result_unknown)
        request_unknown = (
            password_result_unknown or _is_registration_request_unknown(exc)
        ) and not pre_account_transport_failure
        remote_existing = isinstance(exc, RemoteExistingAccountError) or remote_identity == "existing"
        password_rejected = isinstance(exc, PasswordRejectedError)
        account_create_rejected = "account_create_rejected" in error_text.lower()
        password_entry_error_code = next(
            (
                code
                for marker, code in (
                    ("password_entry_page_not_hydrated", "workflow.password_entry_not_hydrated"),
                    ("password_entry_not_offered", "workflow.password_entry_not_offered"),
                    ("password_entry_recovery_exhausted", "workflow.password_entry_recovery_exhausted"),
                )
                if marker in error_text.lower()
            ),
            None,
        )
        mfa_secret_missing = isinstance(exc, MfaSecretMissingError) or any(marker in error_text.lower() for marker in (
            "缺少可用密码或 totp",
            "没有 totp 密钥",
            "没有可用 totp",
            "mfa_secret_missing",
        ))
        disposable_proxy_failure = pre_account_transport_failure
        if disposable_proxy_failure and opened.created_by_run:
            try:
                client.discard_profile(opened)
                profile_discarded = True
                logger.info(
                    "[Roxy注册] 注册前阶段失败且未产生远端账号状态，已软删除临时环境释放重试额度：profile=%s",
                    opened.profile_id,
                )
            except Exception:
                logger.exception("[Roxy注册] 释放代理失败临时环境时出错；保留原失败结果")
        try:
            if account_unusable:
                from core.email_provider import mark_email_permanently_unusable

                mark_email_permanently_unusable(
                    email,
                    source=selected_email_source,
                    note=f"上游明确确认账号永久失效: {error_text[:180]}",
                )
            else:
                from core.email_provider import retain_email

                retain_email(
                    email,
                    source=selected_email_source,
                    note=f"Roxy注册中途失败，保留给原任务链: {error_text[:180]}",
                )
        except Exception:
            pass
        auth_remote_identity = "existing" if remote_existing else remote_identity
        auth_error_code = (
            "password_rejected"
            if password_rejected
            else "account_create_rejected"
            if account_create_rejected
            else password_entry_error_code
            if password_entry_error_code
            else "mfa_secret_missing"
            if mfa_secret_missing
            else
            "remote_existing"
            if remote_existing
            else "request_unknown"
            if request_unknown
            else "registration_failed"
        )
        error_prefix = (
            f"{auth_error_code}: "
            if auth_error_code and auth_error_code.casefold() not in error_text.casefold()
            else ""
        )
        return {
            "success": False,
            "core_persisted": core_persisted,
            "registration_pending": bool(account_id and not access_token),
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "request_unknown": request_unknown,
            "email_submission_unconfirmed": bool(email_result_unknown and not create_acknowledged and account_id is None),
            "manual_reconcile": remote_existing,
            "remote_identity": "existing" if remote_existing else remote_identity,
            "remote_identity_state": "confirmed" if remote_existing else "unknown",
            "remote_account_state": "confirmed" if remote_existing else "request_unknown" if request_unknown else "not_started",
            "error_code": auth_error_code,
            "email_permanently_unusable": account_unusable,
            "account_unusable_error_code": (
                exc.error_code or "account_deactivated"
                if account_unusable
                else None
            ),
            "auth": auth_result_for_registration(
                {"success": False, "error_code": auth_error_code},
                auth_method=registration_driver,
                remote_identity=auth_remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
            "error": f"{error_prefix}{type(exc).__name__}: {str(exc)[:300]}",
        }
    finally:
        if postprocess_data_saver is not None:
            try:
                postprocess_data_saver.stop()
            except Exception:
                logger.exception("[Roxy注册] 收口注册后账号操作省流量统计失败")
        from core.browser_asset_policy import stop_registration_asset_cache
        stop_registration_asset_cache(public_asset_cache)
        if data_saver is not None:
            try:
                data_saver.stop()
            except Exception:
                logger.exception("[Roxy注册] 收口省流量统计失败")
        if not profile_discarded:
            try:
                from core.browser_traffic import finish_roxy_capture
                # Profiler 需要活着的 CDP target，必须先于 driver.quit 收口。
                finish_roxy_capture(opened)
            except Exception:
                logger.exception("[Roxy注册] 收口浏览器流量与执行覆盖率失败")
        if driver and not profile_discarded and not bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
            try:
                _quit_driver(driver)
            except Exception:
                pass
        if not profile_discarded:
            try:
                client.cleanup_profile(opened)
            finally:
                if failed and driver is not None and bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
                    try:
                        persist_browser_resume_context(driver, opened, email=email, facts=facts)
                    except Exception:
                        logger.error("[Roxy注册] 原窗口恢复关联保存失败，仍保留当前进程连接")
                    retain_failed_browser(driver, opened, email=email, facts=facts)
        if plan_check_session is not None:
            try:
                plan_check_session.session.close()
            except Exception:
                pass
