"""Roxy registration OTP DOM execution; persistence is an injected callback."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.auth.browser.browser_submission import BrowserSubmissionReceipt
from core.auth.state_machine import StageBudget, StageTimeout


@dataclass(frozen=True)
class OtpFormCallbacks:
    record_submission: Callable[..., Any]
    install_validate_hook: Callable[..., Any]
    dispatch_trusted_click: Callable[..., Any]
    logger: Any


@dataclass(frozen=True)
class OtpExecutionCallbacks:
    record_submission: Callable[..., Any]
    log_submission_diagnostics: Callable[..., Any]
    email_otp_page_state: Callable[..., Any]
    clear_otp_inputs: Callable[..., Any]
    budget_timeout: Callable[..., Any]
    type_otp: Callable[..., Any]
    prepare_current_form: Callable[..., Any]
    submit_current_form: Callable[..., Any]
    check_stop: Callable[[], None]
    human_delay: Callable[..., Any]
    wait_after_submit: Callable[..., Any]
    logger: Any


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


def prepare_email_otp_current_form(driver, inputs, *, budget: StageBudget | None = None,
                                    capture_responses: bool = False, callbacks: OtpFormCallbacks) -> None:
    """输入控件实际挂载后，复用验证码请求观察器并绑定同一表单。"""
    if budget is not None:
        budget.require("验证码输入准备")
    callbacks.install_validate_hook(driver, capture_responses=capture_responses)
    if driver.execute_script(_OTP_PREPARE_CURRENT_FORM_SCRIPT, inputs) is not True:
        callbacks.record_submission(driver, "not_dispatched", result="cancelled")
        raise RuntimeError("otp_form_not_ready: 验证码输入前表单未就绪，未填写或提交验证码")


def submit_email_otp_current_form(driver, *, callbacks: OtpFormCallbacks) -> dict:
    """仅点击当前邮箱验证码表单，自动跳转后不触碰下一页按钮。"""
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if getattr(receipt, "endpoint_kind", "") == "otp_submit" and getattr(receipt, "phase", "") in {
        "request_observed", "response_observed", "confirmed", "rejected", "unknown", "superseded",
    }:
        return {"clicked": False, "reason": "request_observed"}
    result = driver.execute_script(
        _OTP_SUBMIT_CURRENT_FORM_SCRIPT, callable(getattr(driver, "execute_cdp_cmd", None)),
    )
    if isinstance(result, dict) and result.get("trusted_click"):
        callbacks.dispatch_trusted_click(driver, result.pop("trusted_click"))
    if isinstance(result, dict):
        diagnostics = result.get("diagnostics") or {}
        safe_diagnostics = {
            key: value for key, value in diagnostics.items()
            if key in {"submit_event_seen", "submit_default_prevented", "native_submit_possible", "explicit_click_issued",
                       "form_connected", "baseline_request_count", "validate_request_count", "form_post_call_count",
                       "unknown_form_post_call_count"}
            and type(value) in (bool, int)
        } if isinstance(diagnostics, dict) else {}
        callbacks.logger.info("[Roxy注册][OTP] 提交控件判断：clicked=%s diagnostics=%s", result.get("clicked") is True, safe_diagnostics)
    return result if isinstance(result, dict) else {"clicked": False, "reason": "receipt_unknown"}


def submit_registration_email_otp(driver, otp_code: str, *, budget: StageBudget,
                                   expected_email: str, on_refresh_retry=None,
                                   monitor_otp_network: bool = False, callbacks: OtpExecutionCallbacks):
    """每轮验证码刷新后补交原码一次，各次提交保留独立回执和同一总预算。"""
    for submission_attempt in range(2):
        # 某些验证码控件在最后一位输入后可能自动提交；因此在清空/填写
        # 之前先落库本次提交意图和页面基线，任何自动提交都归属于本回执。
        otp_submission = BrowserSubmissionReceipt(
            kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "otp",
            stage="email_otp", endpoint_kind="otp_submit", http_method="POST",
        )
        driver._browser_submission_receipt = otp_submission
        callbacks.record_submission(driver, "prepared", receipt=otp_submission)
        callbacks.record_submission(driver, "dispatch_intent", receipt=otp_submission)
        callbacks.log_submission_diagnostics(driver, "otp", "before_submit", receipt=otp_submission)
        try:
            otp_submit_baseline = callbacks.email_otp_page_state(driver)
        except Exception:
            otp_submit_baseline = {}
        callbacks.clear_otp_inputs(driver)
        otp_input_timeout = callbacks.budget_timeout(budget, 20, minimum=1)
        if otp_input_timeout < 1:
            raise StageTimeout("email OTP input budget exhausted")
        callbacks.type_otp(
            driver, otp_code, timeout=max(1, int(otp_input_timeout)),
            before_input=lambda inputs: callbacks.prepare_current_form(driver, inputs, budget=budget),
        )
        callbacks.logger.info("[Roxy注册][OTP] 已填写邮箱验证码")
        callbacks.check_stop()
        # OTP 页面已经确认可提交；保留极短的人类化停顿，但不要让默认
        # 的“切回邮箱/阅读验证码”长区间拖慢每个批次。
        callbacks.human_delay("otp_input", minimum=0.35, maximum=1.0, budget=budget)
        try:
            otp_click = callbacks.submit_current_form(driver)
            if otp_click.get("clicked") is True:
                callbacks.record_submission(driver, "ui_dispatched", receipt=otp_submission)
                callbacks.logger.info("[Roxy注册][OTP] 已点击当前验证码表单，等待资料页或登录态")
            else:
                callbacks.logger.info("[Roxy注册][OTP] 未追加点击，继续确认原验证码输入结果：reason=%s", otp_click.get("reason"))
        except Exception as exc:
            # 点击回调抛错不能证明没有派发；保守保留未知围栏，禁止同一候选重放。
            callbacks.record_submission(
                driver, "unknown", receipt=otp_submission, result="unknown",
                error_type=type(exc).__name__,
            )
            callbacks.logger.info("[Roxy注册][OTP] 未找到显式提交按钮，继续等待页面状态：%s", str(exc)[:120])

        outcome = callbacks.wait_after_submit(
            driver, timeout=60, budget=budget,
            baseline_state=otp_submit_baseline,
            expected_email=expected_email,
            retry_after_refresh=submission_attempt == 0,
            **({"monitor_otp_network": True} if monitor_otp_network else {}),
        )
        if outcome != "retry_previous_otp":
            return outcome, otp_submission
        if submission_attempt:
            return "stuck", otp_submission
        budget.require("刷新后补交原验证码")
        callbacks.record_submission(
            driver, "superseded", receipt=otp_submission,
            result="unknown", error_type="otp_refresh_retry",
        )
        callbacks.log_submission_diagnostics(driver, "otp", "retry_previous_otp", receipt=otp_submission)
        callbacks.logger.info("[Roxy注册][OTP] 刷新后仍在邮箱验证码页，使用上次验证码补交一次")
        if on_refresh_retry is not None:
            on_refresh_retry()
    return "stuck", otp_submission
