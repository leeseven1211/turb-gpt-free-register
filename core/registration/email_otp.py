"""Email-entry and OTP browser capabilities shared by auth flows."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import time
import uuid
from dataclasses import replace
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from core.auth_challenge import RemoteExistingAccountError
from core.email_provider import resolve_email_source as _resolve_email_source, wait_for_otp as _wait_for_otp
from core.humanize import delay as _human_delay
from core.registration.state_machine import PageState, StageBudget, StageTimeout, can_resend_otp, classify_page

from .auth_context import (
    AuthExecutionContext,
    checkpoint as _checkpoint,
    current_execution_context,
    current_override,
    execution_context,
    install_dispatches,
    time_proxy,
)
from .browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from .submission_recovery import (
    RECOVERY_WINDOW_SECONDS, auth_session_unavailable, has_visible_auth_inputs, log_submission_diagnostics, recover_submission_page,
)
from .selenium_dom import (
    _auth_terminal_page_state, _budget_timeout, _check_manual_stop, _click_any,
    _click_continue, _find_any, _human_click,
    _human_scroll_to, _human_type_text, _is_login_password_page, _is_signup_password_page,
    _log_prefix, _maybe_accept, _page_snapshot, _safe_get, _type_any,
    _visible, _page_warmup,
)
from .selenium_resource import _browser_actions_enabled
from .session_auth import _has_access_token, _read_profile_session_once

human_delay = _human_delay
wait_for_otp = _wait_for_otp
resolve_email_source = _resolve_email_source
logger = logging.getLogger(__name__)
time = time_proxy

# 邮箱阶段的三个边界：准备、单次请求、整个阶段。提交后的确认沿用当前请求预算；
# 只有确认未派发时，唯一认证兜底才获得新的子预算，始终受同一外层截止约束。
EMAIL_PREPARATION_TIMEOUT = 180
EMAIL_SUBMISSION_TIMEOUT = 60
EMAIL_OUTER_TIMEOUT = 240

_EMAIL_INPUT_SELECTORS = [
    "input[type='email']",
    "input[name='email']",
    "input[name='username']",
    "input#email-input",
    "input[autocomplete='email']",
]

def _email_entry_state(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled;
        const attrText = el => [
          el.id, el.getAttribute('name'), el.getAttribute('type'), el.getAttribute('autocomplete'),
          el.getAttribute('data-testid'), el.getAttribute('data-test-id'), el.getAttribute('data-provider'),
          el.getAttribute('data-auth-provider'), el.getAttribute('href'), el.getAttribute('action'),
          el.getAttribute('formaction'), el.getAttribute('value')
        ].filter(Boolean).join(' ').toLowerCase();
        const inputs = [...document.querySelectorAll('input')].filter(visible).map(el => ({
          type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
          autocomplete: el.getAttribute('autocomplete') || '', value: el.value || ''
        })).slice(0, 30);
        const actions = [...document.querySelectorAll('button,a,[role=button],input[type=button],input[type=submit]')]
          .filter(visible).map(el => ({tag: el.tagName, type: el.getAttribute('type') || '', attrs: attrText(el)})).slice(0, 40);
        return {url: location.href, title: document.title, inputs, actions};
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, "current_url", ""), "error": f"{type(exc).__name__}: {exc}"}

def _find_visible_email_input_js(driver):
    return driver.execute_script(r"""
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
      && !el.disabled && !el.readOnly;
    const selectors = [
      'input[type="email"]',
      'input[name="email"]',
      'input[name="username"]',
      'input#email-input',
      'input[autocomplete="email"]'
    ];
    for (const sel of selectors) {
      const el = [...document.querySelectorAll(sel)].find(visible);
      if (el) return el;
    }
    return null;
    """)

def _is_oauth_consent_like(driver) -> bool:
    """检测是否已到 OAuth 授权/consent 页。这里不能再点任何邮箱分支或全局提交按钮。"""
    try:
        current_url = str(getattr(driver, "current_url", "") or "").lower()
        parsed = urlsplit(current_url)
        # ChatGPT 自己的登录壳可能暂时没有表单，但它仍是注册主流程的
        # 中间页。不能因为空壳里的按钮属性包含 authorize/consent 就把
        # /auth/login?email=... 误判成第三方 OAuth 页面。
        if parsed.hostname == "chatgpt.com" and parsed.path.rstrip("/") == "/auth/login":
            return False
        return bool(driver.execute_script(r"""
        const url = String(location.href || '').toLowerCase();
        if (/oauth|authorize|consent/.test(url) && !/login|signup|identifier|email-verification/.test(url)) return true;
        const formsWithEmail = [...document.querySelectorAll('form')]
          .some(form => form.querySelector('input[type="email"],input[name="email"],input[name="username"],input[autocomplete="email"]'));
        if (formsWithEmail) return false;
        const actions = [...document.querySelectorAll('button,a,[role="button"],input[type="submit"],input[type="button"]')]
          .map(el => [el.id, el.name, el.type, el.getAttribute('data-testid'), el.getAttribute('data-test-id'),
            el.getAttribute('data-provider'), el.getAttribute('data-auth-provider'), el.getAttribute('href'),
            el.getAttribute('formaction'), el.value, el.className].filter(Boolean).join(' ').toLowerCase())
          .join(' ');
        return /oauth|authorize|consent|grant|allow/.test(actions) && !/email|username/.test(actions);
        """))
    except Exception:
        return False

def _is_external_idp_url(url: str) -> bool:
    u = str(url or '').lower()
    return any(x in u for x in (
        'accounts.google.', 'google.com/o/oauth', 'appleid.apple.', 'login.microsoftonline.',
        'login.live.', 'github.com/login/oauth', 'facebook.com/', 'saml', 'sso'
    ))

def _assert_not_external_idp(driver, label: str = '') -> None:
    try:
        current = str(driver.current_url or '')
    except Exception:
        current = ''
    if _is_external_idp_url(current):
        raise RuntimeError(f"误入第三方账号授权页（{label}）：{current}")

def _click_email_entry_option(driver) -> bool:
    """点击“邮箱方式”入口；只看 DOM 技术属性，不看按钮可见文案，并显式排除 Google 等第三方。"""
    if _is_oauth_consent_like(driver):
        logger.info("%s 当前疑似 OAuth 授权页，跳过邮箱入口兜底点击", _log_prefix(driver))
        return False
    target = driver.execute_script(r"""
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
      && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
    const attrText = el => {
      const own = [
        el.id, el.getAttribute('name'), el.getAttribute('type'), el.getAttribute('autocomplete'),
        el.getAttribute('data-testid'), el.getAttribute('data-test-id'), el.getAttribute('data-provider'),
        el.getAttribute('data-auth-provider'), el.getAttribute('data-idp'), el.getAttribute('href'), el.getAttribute('action'),
        el.getAttribute('formaction'), el.getAttribute('value'), el.getAttribute('aria-label'), el.className
      ].filter(Boolean).join(' ');
      const desc = [...el.querySelectorAll('img,svg,use,[aria-label],[data-provider],[data-testid],[data-test-id]')]
        .map(x => [x.getAttribute('alt'), x.getAttribute('src'), x.getAttribute('href'), x.getAttribute('xlink:href'),
          x.getAttribute('aria-label'), x.getAttribute('data-provider'), x.getAttribute('data-testid'), x.getAttribute('data-test-id'), x.className]
          .filter(Boolean).join(' ')).join(' ');
      return `${own} ${desc}`.toLowerCase();
    };
    const bad = /google|apple|microsoft|github|facebook|saml|sso|oauth|social|oidc|idp|provider|authorize|consent|grant|allow/;
    const good = /(^|[^a-z])(email|mail|username|passwordless|otp|magic)([^a-z]|$)/;
    const candidates = [...document.querySelectorAll('button,a,[role="button"],input[type="button"],input[type="submit"]')]
      .filter(visible)
      .map(el => ({el, attrs: attrText(el), hasLogo: !!el.querySelector('img,svg,use')}))
      .filter(x => good.test(x.attrs) && !bad.test(x.attrs) && !x.hasLogo);
    if (candidates.length !== 1) return null;
    candidates[0].el.scrollIntoView({block:'center'});
    return candidates[0].el;
    """)
    if target:
        _human_click(driver, target, label="email_entry")
        return True
    return False

def _is_blank_chatgpt_auth_shell(driver, state: dict | None = None) -> bool:
    """识别 /auth/login 路由还在、但登录表单被前端异常卸载的空壳页面。"""
    try:
        current_url = str((state or {}).get("url") or getattr(driver, "current_url", "") or "")
        parsed = urlsplit(current_url)
        if parsed.hostname != "chatgpt.com" or parsed.path.rstrip("/") != "/auth/login":
            return False
    except Exception:
        return False

    try:
        detected = bool(driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const hasEmail = [...document.querySelectorAll(
          'input[type="email"],input[name="email"],input[name="username"],input[autocomplete*="email"]'
        )].some(visible);
        if (hasEmail) return false;
        const hasHome = !!document.querySelector('a[href="/?slm=1"]');
        const hasDismiss = !!document.querySelector(
          '#dismiss-welcome,.dismiss-welcome,[data-testid="dismiss-welcome"],a[href="#"]'
        );
        return hasHome && hasDismiss;
        """))
        if detected:
            return True
    except Exception:
        pass

    # Selenium 在 SPA 卸载瞬间执行脚本偶发返回 false/异常；使用已采集的页面状态兜底。
    # 生产日志中的空壳页稳定只剩 /?slm=1 与 dismiss-welcome 两个壳层入口。
    shell_state = state if isinstance(state, dict) else _email_entry_state(driver)
    if shell_state.get("inputs"):
        return False
    action_attrs = " ".join(
        str(action.get("attrs") or "").lower()
        for action in (shell_state.get("actions") or [])
        if isinstance(action, dict)
    )
    if "/?slm=1" in action_attrs and "dismiss-welcome" in action_attrs:
        return True
    if shell_state.get("actions"):
        return False
    # A second blank-shell variant has no actions at all. It is still the
    # ChatGPT auth route, but React never mounted the login form; refreshing
    # this state is equivalent to the user's manual refresh recovery.
    title = str(shell_state.get("title") or "").strip().lower()
    if title in {
        "开始使用 | chatgpt",
        "開始する | chatgpt",
        "get started | chatgpt",
    }:
        return True
    # The same unmounted shell is localized by the browser profile. Keep the
    # detection limited to a ChatGPT start-page title with no actions/inputs,
    # so a normal mounted login page cannot be mistaken for this recovery case.
    localized_start_markers = (
        "start", "begin", "get started", "शुरु", "शुरू", "开始", "開始", "始め",
        "bắt đầu", "commenc", "comenz", "empez", "iniciar", "iniz", "avvia", "нач",
    )
    return title.endswith("| chatgpt") and any(marker in title for marker in localized_start_markers)

def _reload_blank_chatgpt_auth_shell(driver) -> None:
    """刷新异常空壳登录页，使 React 登录表单重新挂载。"""
    advanced_state = _email_submit_advanced_state(driver)
    if advanced_state:
        logger.info(
            "%s 登录空壳刷新前页面已进入下一步，取消刷新：%s",
            _log_prefix(driver), advanced_state,
        )
        return
    if not _is_blank_chatgpt_auth_shell(driver):
        logger.info("%s 页面已离开 ChatGPT 登录空壳，取消刷新", _log_prefix(driver))
        return
    logger.warning("%s 检测到 ChatGPT 登录空壳页，刷新后重新进入邮箱步骤", _log_prefix(driver))
    try:
        driver.refresh()
    except Exception:
        _safe_get(
            driver,
            "https://chatgpt.com/auth/login",
            timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com", "auth.openai.com"),
        )
    human_delay("navigate")
    _page_warmup(driver, reason="reload_blank_auth_shell")
    if _is_blank_chatgpt_auth_shell(driver):
        # 普通 refresh 仍可能复用损坏的 SPA 状态；带一次性查询参数强制新导航。
        recovery_url = f"https://chatgpt.com/auth/login?recover={int(time.time() * 1000)}"
        logger.warning("%s 刷新后仍是登录空壳页，执行强制新导航", _log_prefix(driver))
        _safe_get(
            driver,
            recovery_url,
            timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com", "auth.openai.com"),
        )
        human_delay("navigate")
        _page_warmup(driver, reason="reload_blank_auth_shell_hard")

def _clear_confirmed_email_submission(driver) -> None:
    """仅在确认后续认证步骤时释放提交屏障，供同一浏览器后续登录使用。"""
    if isinstance(getattr(driver, "_email_submission_receipt", None), dict):
        driver._email_submission_receipt = None


def _confirm_email_submission_fact(driver, *, result: str = "success") -> None:
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if receipt is None:
        return
    # 已有 Attempt 上下文时，确认事实落库失败必须向上抛出；否则页面成功会
    # 被错误地当作本地已确认，后续恢复无法知道原提交边界。
    record_browser_submission_fact(driver, "confirmed", receipt=receipt, result=result)


def _email_submit_advanced_state(driver, *, budget: StageBudget | None = None) -> str | None:
    """识别邮箱提交后已经到达的稳定下一步，避免按过期页面状态继续重试。"""
    if _is_login_password_page(driver):
        _confirm_email_submission_fact(driver)
        _clear_confirmed_email_submission(driver)
        return "login_password"
    if _is_email_verification_page(driver):
        _confirm_email_submission_fact(driver)
        _clear_confirmed_email_submission(driver)
        return "otp"
    if _is_signup_password_page(driver):
        _confirm_email_submission_fact(driver)
        _clear_confirmed_email_submission(driver)
        return "password"
    receipt = getattr(driver, "_email_submission_receipt", None)
    if isinstance(receipt, dict) and _is_email_login_page_still_present(driver):
        # 明确仍在邮箱表单时，避免每轮都发送 session 请求；DOM 下一步始终优先。
        now = time.monotonic()
        last_probe = receipt.get("session_probe_at")
        if isinstance(last_probe, (int, float)) and now - last_probe < 3.0:
            return None
        receipt["session_probe_at"] = now
    if (_has_access_token(driver, budget=budget) if budget is not None else _has_access_token(driver)):
        _confirm_email_submission_fact(driver)
        _clear_confirmed_email_submission(driver)
        return "logged_in"
    return None

def _type_email_address(
    driver,
    email: str,
    timeout: int | None = None,
    *,
    stop_on_advanced: bool = False,
) -> str | None:
    """进入邮箱登录/注册方式并填写邮箱。全程不依赖页面可见文字，避免非日本出口本地化后误点 Google。"""
    wait_seconds = int(_cfg.ROXY_SELENIUM_TIMEOUT) if timeout is None else max(0.0, float(timeout))
    if wait_seconds <= 0:
        raise StageTimeout("邮箱输入准备预算已耗尽，未填写或提交邮箱")
    end = time.time() + wait_seconds
    last_state = None
    clicked_email_option = False
    reloaded_blank_shell = False
    while time.time() < end:
        if stop_on_advanced:
            advanced_state = _email_submit_advanced_state(driver)
            if advanced_state:
                logger.info(
                    "%s 重填邮箱前页面已进入下一步，停止重填：%s",
                    _log_prefix(driver), advanced_state,
                )
                return advanced_state
        el = _find_visible_email_input_js(driver)
        if el:
            _human_type_text(driver, el, email, clear=True)
            return "email"
        last_state = _email_entry_state(driver)
        if not reloaded_blank_shell and _is_blank_chatgpt_auth_shell(driver, last_state):
            _reload_blank_chatgpt_auth_shell(driver)
            reloaded_blank_shell = True
            clicked_email_option = False
            continue
        if not clicked_email_option and _click_email_entry_option(driver):
            clicked_email_option = True
            time.sleep(1.0)
            _assert_not_external_idp(driver, "点击邮箱入口后")
            continue
        time.sleep(0.4)
    if stop_on_advanced:
        advanced_state = _email_submit_advanced_state(driver)
        if advanced_state:
            logger.info(
                "%s 邮箱入口等待结束时页面已进入下一步：%s",
                _log_prefix(driver), advanced_state,
            )
            return advanced_state
    raise RuntimeError(f"找不到邮箱输入框/邮箱入口（未使用文字识别），state={last_state}")

def _submit_nearest_form_for_active_input(driver) -> bool:
    if _is_oauth_consent_like(driver):
        logger.info("%s 当前疑似 OAuth 授权页，禁止执行邮箱提交", _log_prefix(driver))
        return False
    result = driver.execute_script(_EMAIL_FRONTEND_READY_JS + r"""
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
      && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
    const input = [...document.querySelectorAll('input[type="email"],input[name="email"],input[name="username"],input[autocomplete="email"]')]
      .find(visible);
    if (!input) return {ok:false, reason:'missing_email_input'};
    const value = String(input.value || '').trim();
    if (!value || !value.includes('@')) return {ok:false, reason:'email_value_not_ready', value};
    const form = input.closest('form');
    if (!form) return {ok:false, reason:'missing_form'};

    const bad = /google|apple|microsoft|github|facebook|saml|sso|oauth|social|oidc|sso|saml|idp|provider|authorize|consent|grant|allow/;
    const attrText = el => {
      const own = [el.id, el.name, el.type, el.getAttribute('data-testid'), el.getAttribute('data-test-id'),
        el.getAttribute('data-provider'), el.getAttribute('data-auth-provider'), el.getAttribute('data-idp'),
        el.getAttribute('aria-label'), el.getAttribute('href'), el.getAttribute('formaction'), el.value, el.className]
        .filter(Boolean).join(' ');
      const desc = [...el.querySelectorAll('img,svg,use,[aria-label],[data-provider],[data-testid],[data-test-id]')]
        .map(x => [x.getAttribute('alt'), x.getAttribute('src'), x.getAttribute('href'), x.getAttribute('xlink:href'),
          x.getAttribute('aria-label'), x.getAttribute('data-provider'), x.getAttribute('data-testid'), x.getAttribute('data-test-id'), x.className]
          .filter(Boolean).join(' '))
        .join(' ');
      return `${own} ${desc}`.toLowerCase();
    };
    const inputRect = input.getBoundingClientRect();
    const formId = form.getAttribute('id') || '';
    const scopedButtons = [
      ...form.querySelectorAll('button,input[type="submit"]'),
      ...(formId ? [...document.querySelectorAll(`button[form="${CSS.escape(formId)}"],input[type="submit"][form="${CSS.escape(formId)}"]`)] : [])
    ].filter((el, idx, arr) => arr.indexOf(el) === idx);
    const rawButtons = scopedButtons
      .filter(visible)
      .map((el, idx) => {
        const r = el.getBoundingClientRect();
        const attrs = attrText(el);
        const hasLogo = !!el.querySelector('img,svg,use');
        const isBad = bad.test(attrs) || hasLogo;
        const belowInput = r.top >= inputRect.bottom - 10;
        const distance = Math.max(0, r.top - inputRect.bottom) + Math.abs((r.left + r.right) / 2 - (inputRect.left + inputRect.right) / 2) / 10;
        const cls = String(el.className || '').toLowerCase();
        const type = String(el.getAttribute('type') || '').toLowerCase();
        // ChatGPT 新版邮箱页的主按钮形如：
        // <button class="... btn-primary ... w-full ..." type="submit"><div>続行</div></button>
        // 优先选择同 form 下的 primary submit，而不是因为多个按钮距离接近误判歧义。
        const isPrimarySubmit = (el.tagName === 'BUTTON' || el.tagName === 'INPUT') && type === 'submit'
          && (/\bbtn-primary\b/.test(cls) || /\b_primary_/.test(cls) || /\bw-full\b/.test(cls));
        const score = (isPrimarySubmit ? 1000 : 0) + (type === 'submit' ? 100 : 0) - distance;
        return {el, idx, attrs, isBad, hasLogo, belowInput, distance, score, isPrimarySubmit, tag: el.tagName, type};
      });
    const safe = rawButtons.filter(x => !x.isBad && x.belowInput)
      .sort((a,b) => b.score - a.score || a.distance - b.distance || a.idx - b.idx);
    if (!safe.length) {
      return {ok:false, reason:'no_safe_submit', buttons: rawButtons.map(x => ({idx:x.idx, isBad:x.isBad, hasLogo:x.hasLogo, belowInput:x.belowInput, primary:x.isPrimarySubmit, attrs:x.attrs.slice(0,160), type:x.type}))};
    }
    // 多个安全按钮时，若没有明确 primary submit，且距离接近，才认为页面歧义。
    if (!safe[0].isPrimarySubmit && safe.length > 1 && Math.abs(safe[0].distance - safe[1].distance) < 8) {
      return {ok:false, reason:'ambiguous_submit', buttons: safe.slice(0,3).map(x => ({idx:x.idx, distance:x.distance, score:x.score, primary:x.isPrimarySubmit, attrs:x.attrs.slice(0,160), type:x.type}))};
    }
    const target = safe[0].el;
    if (!emailFrontendReady(input, form, target)) return {ok:false, reason:'email_frontend_not_ready'};
    target.scrollIntoView({block:'center'});
    window.__roxy_email_submit_debug = {at: Date.now(), targetAttrs: safe[0].attrs.slice(0,240), buttonCount: rawButtons.length, primary:safe[0].isPrimarySubmit};
    return {ok:true, reason:safe[0].isPrimarySubmit ? 'primary_submit' : 'safe_submit', target, targetAttrs:safe[0].attrs.slice(0,160), primary:safe[0].isPrimarySubmit};
    """) or {}
    if result.get("reason") == "email_frontend_not_ready":
        raise _EmailFrontendNotReady("email_frontend_not_ready: 登录表单接管状态发生变化，未发送邮箱")
    if result.get("ok"):
        target = result.get("target")
        if target:
            submission_id = uuid.uuid4().hex
            receipt = BrowserSubmissionReceipt(
                kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "email",
                stage="submit_email", submission_id=submission_id,
                endpoint_kind="email_submit", http_method="POST",
            )
            driver._browser_submission_receipt = receipt
            driver._email_submission_receipt = {"id": submission_id}
            record_browser_submission_fact(driver, "dispatch_intent", receipt=receipt)
            try:
                _human_click(driver, target, label="email_submit")
                record_browser_submission_fact(driver, "ui_dispatched", receipt=receipt)
            except Exception as exc:
                record_browser_submission_fact(
                    driver, "unknown", receipt=receipt, result="unknown",
                    error_type=type(exc).__name__,
                )
                raise
        else:
            logger.warning("%s 邮箱提交未返回目标元素，保留页面等待恢复", _log_prefix(driver))
            return False
        logger.info("%s 邮箱表单安全提交：%s", _log_prefix(driver), result.get("reason"))
        time.sleep(0.8)
        _assert_not_external_idp(driver, "提交邮箱后")
        return True
    logger.warning("%s 未执行邮箱提交：%s", _log_prefix(driver), result.get("reason"))
    return False

def _current_email_input_value(driver) -> str:
    try:
        state = _email_input_value_state(driver)
        for item in state.get("inputs") or []:
            value = str(item.get("value") or "").strip()
            if "@" in value:
                return value
    except Exception:
        pass
    return ""

def _stabilize_email_input_before_submit(driver, email: str) -> dict:
    """提交前把 DOM value / React 受控状态 / blur-change 状态统一稳定下来。"""
    try:
        return driver.execute_script(r"""
        const email = String(arguments[0] || '').trim();
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const input = [...document.querySelectorAll('input[type="email"],input[name="email"],input[name="username"],input[autocomplete*="email"]')]
          .find(visible);
        if (!input) return {ok:false, reason:'missing_email_input'};

        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
        input.scrollIntoView({block:'center', inline:'nearest'});
        input.focus();
        if (setter) setter.call(input, email); else input.value = email;

        // 让 React/表单校验尽量收到完整输入链路。
        try { input.dispatchEvent(new InputEvent('beforeinput', {bubbles:true, cancelable:true, inputType:'insertText', data:email})); } catch (_) {}
        try { input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:email})); } catch (_) {
          input.dispatchEvent(new Event('input', {bubbles:true}));
        }
        input.dispatchEvent(new Event('change', {bubbles:true}));
        input.dispatchEvent(new FocusEvent('blur', {bubbles:true}));
        input.blur();
        input.focus();

        const form = input.closest('form');
        const submit = form?.querySelector('button[type="submit"],input[type="submit"]');
        return {
          ok:true,
          value: input.value,
          active: document.activeElement === input,
          hasForm: !!form,
          hasSubmit: !!submit,
          submitDisabled: submit ? (!!submit.disabled || String(submit.getAttribute('aria-disabled') || '').toLowerCase() === 'true') : null,
          url: location.href
        };
        """, email) or {}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

_EMAIL_FRONTEND_READY_JS = r"""
const emailFrontendReady = (input, form, submit) => {
  if (location.hostname !== 'chatgpt.com' || !/^\/auth\/login\/?$/.test(location.pathname)) return true;
  // SSR 输入框可见不代表 React 已接管提交；只观察事件处理器，不调用页面内部函数。
  const props = node => {
    if (!node) return [];
    return Object.getOwnPropertyNames(node)
      .filter(key => key.startsWith('__reactProps$') || key.startsWith('__reactEventHandlers$'))
      .map(key => node[key]).filter(Boolean);
  };
  return !!input && (props(form).some(value => typeof value.onSubmit === 'function')
    || props(submit).some(value => typeof value.onClick === 'function')
    || typeof form?.onsubmit === 'function');
};
"""


class _EmailFrontendNotReady(RuntimeError):
    """前端未接管，尚未执行任何邮箱提交，可转入一次有界导航兜底。"""


class _EmailSubmissionUnknown(RuntimeError):
    """已交给前端的提交尚未确认结果，禁止重复提交或导航兜底。"""


def _email_ui_submission_state(driver) -> str | None:
    receipt = getattr(driver, "_email_submission_receipt", None)
    if not isinstance(receipt, dict):
        return None
    snapshot = {"phase": "unknown", "same_document": False}
    try:
        state = driver.execute_script("""
        const receipt = window.__turbEmailSubmission;
        return receipt && typeof receipt.snapshot === 'function'
          ? receipt.snapshot() : receipt ? {id:receipt.id, phase:receipt.phase} : null;
        """)
        if isinstance(state, dict) and state.get("id") == receipt.get("id"):
            snapshot["same_document"] = True
            phase = state.get("phase")
            if phase in {"queued", "dispatched", "cancelled", "unknown"}:
                snapshot["phase"] = phase
            for key in ("input_connected", "form_connected", "submit_connected", "input_matches",
                        "input_enabled", "submit_enabled", "input_valid", "form_valid"):
                if type(state.get(key)) is bool:
                    snapshot[key] = state[key]
            for key in ("elapsed_ms", "dispatched_elapsed_ms"):
                value = state.get(key)
                if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                    snapshot[key] = round(value)
            if state.get("reason") in {"queue_timeout", "input_changed", "input_invalid", "control_unavailable",
                                        "frontend_unready", "detached", "click_error"}:
                snapshot["reason"] = state["reason"]
            driver._email_submission_diagnostics = snapshot
            if phase == "cancelled":
                try:
                    record_browser_submission_fact(
                        driver, "not_dispatched", receipt=getattr(driver, "_browser_submission_receipt", None),
                        result="cancelled",
                    )
                except Exception:
                    logger.exception("%s 邮箱提交取消事实保存失败", _log_prefix(driver))
                driver._email_submission_receipt = None
                return "cancelled"
            if phase == "dispatched":
                try:
                    record_browser_submission_fact(
                        driver, "ui_dispatched", receipt=getattr(driver, "_browser_submission_receipt", None),
                    )
                except Exception:
                    logger.exception("%s 邮箱 UI 派发事实保存失败", _log_prefix(driver))
            elif phase == "queued":
                try:
                    record_browser_submission_fact(
                        driver, "ui_queued", receipt=getattr(driver, "_browser_submission_receipt", None),
                    )
                except Exception:
                    logger.exception("%s 邮箱 UI 排队事实保存失败", _log_prefix(driver))
            if phase in {"queued", "dispatched"}:
                return phase
    except Exception:
        pass
    # 导航/执行上下文更换不能证明上一个文档没有发出 signin。
    previous = getattr(driver, "_email_submission_diagnostics", None)
    if isinstance(previous, dict) and previous.get("same_document"):
        snapshot["last_confirmed_phase"] = previous["phase"]
    elif isinstance(previous, dict) and previous.get("last_confirmed_phase"):
        snapshot["last_confirmed_phase"] = previous["last_confirmed_phase"]
    driver._email_submission_diagnostics = snapshot
    return "unknown"


def _cancel_queued_email_submission(driver) -> bool:
    """只在原文档原回执仍未点击时，原子取消定时器并释放提交屏障。"""
    receipt = getattr(driver, "_email_submission_receipt", None)
    if not isinstance(receipt, dict):
        return False
    try:
        cancelled = driver.execute_script("""
        const receipt = window.__turbEmailSubmission;
        if (!receipt || receipt.id !== arguments[0] || receipt.phase !== 'queued') return false;
        clearTimeout(receipt.timer);
        receipt.phase = 'cancelled';
        receipt.reason = 'queue_timeout';
        return true;
        """, receipt.get("id"))
        if cancelled is True:
            _email_ui_submission_state(driver)
            driver._email_submission_receipt = None
            return True
    except Exception:
        # 取消结果不明时仍保留屏障，不能因为读不到回执而重发。
        pass
    return False


def _log_email_submission_timeout(driver) -> None:
    """只记录白名单回执事实，工作回执清理后仍保留诊断快照。"""
    _email_ui_submission_state(driver)
    snapshot = getattr(driver, "_email_submission_diagnostics", None)
    logger.warning("%s 邮箱提交等待超时，提交回执诊断=%s", _log_prefix(driver), snapshot)


def _wait_email_frontend_ready(driver, timeout: float | None = None) -> None:
    """等待登录表单接管提交，耗尽预算时保留页面，不触发原生 GET。"""
    budget = getattr(driver, "_registration_stage_budget", None)
    if not isinstance(budget, StageBudget):
        budget = None
    # 注册页面的输入框会先于关键脚本出现；沿用准备预算等脚本接管，
    # 直接调用的 Codex 等入口仍使用原有 30 秒等待。
    wait_limit = timeout if timeout is not None else budget.remaining() if budget else 30.0
    started = time.monotonic()
    deadline = started + _budget_timeout(budget, wait_limit, minimum=0.0)
    next_progress = started

    def report(phase: str, message: str) -> None:
        callback = getattr(driver, "_registration_email_progress", None)
        if callable(callback):
            try:
                callback(phase, message)
            except Exception:
                logger.exception("%s 上报邮箱页面加载进度失败", _log_prefix(driver))

    while time.monotonic() < deadline:
        _checkpoint()
        _check_manual_stop()
        if budget is not None:
            budget.check_cancelled()
        try:
            ready = driver.execute_script(_EMAIL_FRONTEND_READY_JS + r"""
            const input = [...document.querySelectorAll('input[type="email"],input[name="email"],input[name="username"]')]
              .find(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
            const form = input?.closest('form');
            const submit = form?.querySelector('button[type="submit"],input[type="submit"]');
            return emailFrontendReady(input, form, submit);
            """)
            if ready is True:
                elapsed = time.monotonic() - started
                if elapsed >= 10:
                    logger.info("%s 邮箱表单已就绪，等待 %.1f 秒后自动继续提交", _log_prefix(driver), elapsed)
                    report("frontend_ready", "邮箱表单已就绪，正在自动提交邮箱")
                return
        except Exception:
            # 水合期间元素和执行上下文可能被替换，继续在同一预算内观察。
            pass
        now = time.monotonic()
        if now >= next_progress:
            elapsed = now - started
            message = f"邮箱已填写，页面功能仍在加载（已等待 {elapsed:.0f} 秒），就绪后自动点击继续"
            logger.info("%s %s", _log_prefix(driver), message)
            report("waiting_frontend", message)
            next_progress = now + 10.0
        time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    raise _EmailFrontendNotReady("email_frontend_not_ready: 登录表单尚未接管提交，未发送邮箱")


def _submit_email_form_stable(driver, email: str) -> dict:
    """等前端接管后稳定输入值，仅排入一次按钮点击。"""
    if _email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
        return {"ok": True, "reason": "email_submission_pending"}
    submission_id = uuid.uuid4().hex
    receipt = BrowserSubmissionReceipt(
        kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "email",
        stage="submit_email", submission_id=submission_id,
        endpoint_kind="email_submit", http_method="POST",
    )
    driver._browser_submission_receipt = receipt
    log_submission_diagnostics(driver, "email", "before_submit", receipt=receipt)
    # 围栏必须在定时器排队和 click 之前落库；UI queued/click 不是 HTTP 成功。
    record_browser_submission_fact(driver, "dispatch_intent", receipt=receipt)
    driver._email_submission_receipt = {"id": submission_id}
    try:
        result = driver.execute_script(_EMAIL_FRONTEND_READY_JS + r"""
        const email = String(arguments[0] || '').trim();
        const submissionId = arguments[1];
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
        const editable = el => visible(el) && !el.readOnly;
        const input = [...document.querySelectorAll('input[type="email"],input[name="email"],input[name="username"],input[autocomplete*="email"]')]
          .find(editable);
        if (!input) return {ok:false, reason:'missing_email_input'};
        if (!email || !email.includes('@')) return {ok:false, reason:'empty_email', value: email};

        const form = input.closest('form');
        if (!form) return {ok:false, reason:'missing_form'};

        const bad = /google|apple|microsoft|github|facebook|saml|sso|oauth|social|oidc|idp|provider|authorize|consent|grant|allow/;
        const attrText = el => {
          const own = [el.id, el.name, el.type, el.getAttribute('data-testid'), el.getAttribute('data-test-id'),
            el.getAttribute('data-provider'), el.getAttribute('data-auth-provider'), el.getAttribute('data-idp'),
            el.getAttribute('aria-label'), el.getAttribute('href'), el.getAttribute('formaction'), el.value, el.className]
            .filter(Boolean).join(' ');
          const desc = [...el.querySelectorAll('img,svg,use,[aria-label],[data-provider],[data-testid],[data-test-id]')]
            .map(x => [x.getAttribute('alt'), x.getAttribute('src'), x.getAttribute('href'), x.getAttribute('xlink:href'),
              x.getAttribute('aria-label'), x.getAttribute('data-provider'), x.getAttribute('data-testid'), x.getAttribute('data-test-id'), x.className]
              .filter(Boolean).join(' '))
            .join(' ');
          return `${own} ${desc}`.toLowerCase();
        };

        const formId = form.getAttribute('id') || '';
        const buttons = [
          ...form.querySelectorAll('button,input[type="submit"]'),
          ...(formId ? [...document.querySelectorAll(`button[form="${CSS.escape(formId)}"],input[type="submit"][form="${CSS.escape(formId)}"]`)] : [])
        ].filter((el, idx, arr) => arr.indexOf(el) === idx)
          .filter(el => visible(el) && !bad.test(attrText(el)) && !el.querySelector('img,svg,use'));
        const submit = buttons.find(el => (el.getAttribute('type') || '').toLowerCase() === 'submit') || buttons[0] || null;
        if (!submit) return {ok:false, reason:'missing_safe_submit'};
        if (!emailFrontendReady(input, form, submit)) return {ok:false, reason:'email_frontend_not_ready'};

        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
        input.scrollIntoView({block:'center', inline:'nearest'});
        input.focus();
        if (setter) setter.call(input, email); else input.value = email;
        try { input.dispatchEvent(new InputEvent('beforeinput', {bubbles:true, cancelable:true, inputType:'insertText', data:email})); } catch (_) {}
        try { input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:email})); } catch (_) {
          input.dispatchEvent(new Event('input', {bubbles:true}));
        }
        input.dispatchEvent(new Event('change', {bubbles:true}));
        input.dispatchEvent(new FocusEvent('blur', {bubbles:true}));
        input.blur();
        input.focus();

        submit.scrollIntoView({block:'center', inline:'nearest'});

        // 不要在 execute_script 同步执行 submit.click()：
        // ChromeDriver 会等前端 submit/navigation，Roxy/Chrome 150 上可能卡到 page/script timeout。
        // setTimeout 让 Selenium 先返回，点击在页面事件循环里异步发生，和补交逻辑一致。
        const receipt = {id:submissionId, phase:'queued', queuedAt:Date.now()};
        const enabled = el => !el.disabled && !el.matches?.(':disabled')
          && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        receipt.snapshot = () => ({
          id:receipt.id, phase:receipt.phase, reason:receipt.reason || '',
          elapsed_ms:Math.max(0, Date.now() - receipt.queuedAt),
          dispatched_elapsed_ms:receipt.dispatchedAt === undefined ? null : Math.max(0, Date.now() - receipt.dispatchedAt),
          input_connected:!!input.isConnected, form_connected:!!form.isConnected,
          submit_connected:!!submit.isConnected,
          input_matches:String(input.value || '').trim().toLowerCase() === email.toLowerCase(),
          input_enabled:enabled(input) && !input.readOnly, submit_enabled:enabled(submit),
          input_valid:input.validity?.valid !== false, form_valid:!form.matches?.(':invalid')
        });
        window.__turbEmailSubmission = receipt;
        receipt.timer = setTimeout(() => {
          try {
            if (window.__turbEmailSubmission !== receipt || receipt.id !== submissionId || receipt.phase !== 'queued') return;
            const state = receipt.snapshot();
            if (!input.isConnected || !form.isConnected || !submit?.isConnected
                || input.closest('form') !== form || submit.form !== form) receipt.reason = 'detached';
            else if (!state.input_matches) receipt.reason = 'input_changed';
            else if (!state.input_valid || !state.form_valid) receipt.reason = 'input_invalid';
            else if (!state.input_enabled || !state.submit_enabled) receipt.reason = 'control_unavailable';
            else if (!emailFrontendReady(input, form, submit)) receipt.reason = 'frontend_unready';
            if (receipt.reason) { receipt.phase = 'cancelled'; return; }
            receipt.phase = 'dispatched';
            receipt.dispatchedAt = Date.now();
            submit.click();
          } catch (_) { receipt.phase = 'unknown'; receipt.reason = 'click_error'; }
        }, 80);

        window.__roxy_email_submit_debug = {
          at: Date.now(),
          mode: 'stable_async_click',
          submitAttrs: attrText(submit).slice(0, 240)
        };
        return {
          ok:true,
          reason:'stable_async_click',
          submitDisabled: !!submit.disabled || String(submit.getAttribute('aria-disabled') || '').toLowerCase() === 'true',
          submitAttrs: attrText(submit).slice(0, 180),
          url: location.pathname
        };
        """, email, submission_id) or {}
        if isinstance(result, dict) and result.get("ok") is False:
            record_browser_submission_fact(driver, "not_dispatched", receipt=receipt, result="cancelled")
            driver._email_submission_receipt = None
            # 明确未排队时，NextAuth 兜底必须建立新的 submission_id；复用已
            # not_dispatched 的回执会把两个动作混成一条事实链，破坏跨 Run 围栏。
            driver._browser_submission_receipt = None
            return result
        record_browser_submission_fact(driver, "ui_queued", receipt=receipt)
        return result if isinstance(result, dict) and result.get("ok") is True else {"ok": True, "reason": "email_submission_result_unknown"}
    except Exception:
        # 驱动没有收到脚本结果时，排队动作仍可能已经生效。
        # 此处不能把异常当作未派发，保留 dispatch_intent/unknown 围栏。
        try:
            record_browser_submission_fact(driver, "unknown", receipt=receipt, result="unknown")
        except Exception:
            logger.exception("%s 邮箱提交事实保存失败", _log_prefix(driver))
        return {"ok": True, "reason": "email_submission_result_unknown"}

def _submit_email_step(driver, email: str | None = None) -> None:
    # 可见的 SSR 表单还不能提交；先等前端绑定，再沿页面原有邮箱流程执行一次点击。
    email_value = str(email or _current_email_input_value(driver) or "").strip()
    _wait_email_frontend_ready(driver)
    stable = _stabilize_email_input_before_submit(driver, email_value)
    logger.info("%s 邮箱提交前状态稳定：ok=%s", _log_prefix(driver), stable.get("ok"))
    time.sleep(random.uniform(0.8, 1.8) if _browser_actions_enabled() else 0.4)
    before_dispatch = getattr(driver, "_registration_before_email_dispatch", None)
    if callable(before_dispatch):
        # 前端已接管且即将进入稳定提交函数；从此处开始使用唯一 60 秒
        # submission_budget，避免 click 后才新开预算。
        before_dispatch()

    submission_budget = getattr(driver, "_registration_stage_budget", None)
    if isinstance(submission_budget, StageBudget):
        # 预检失败后的首次点击仍共用原预算；前端临近截止才就绪时，
        # 不能让输入稳定等待跨过截止后继续派发。
        submission_budget.require("邮箱首次提交")

    stable_submit = _submit_email_form_stable(driver, email_value)
    if stable_submit.get("ok"):
        logger.info("%s 邮箱稳定表单提交：%s", _log_prefix(driver), stable_submit.get("reason"))
        time.sleep(1.0)
        _assert_not_external_idp(driver, "稳定表单提交邮箱后")
        return
    if stable_submit.get("reason") == "email_frontend_not_ready":
        raise _EmailFrontendNotReady("email_frontend_not_ready: 登录表单接管状态发生变化，未发送邮箱")
    _wait_email_frontend_ready(driver)
    logger.warning("%s 邮箱稳定表单提交失败，回退 UI 点击提交：%s", _log_prefix(driver), stable_submit.get("reason"))
    if _submit_nearest_form_for_active_input(driver):
        return
    raise RuntimeError(f"无法提交邮箱步骤（拒绝按页面文字或首个 submit 兜底，避免误点第三方登录），state={_email_entry_state(driver)}")

def _recover_email_submit_if_stuck(driver, email: str) -> dict:
    """只有明确的原生 GET 回环且本次未被前端接手时，才允许一次受控补交。"""
    if _email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
        return {"ok": False, "reason": "email_submission_pending"}
    try:
        native_get = driver.execute_script(r"""
        const navigation = performance.getEntriesByType('navigation')[0];
        if (!navigation || window.__turbEmailSubmission) return false;
        const original = new URL(navigation.name);
        // SPA 改写地址不会改变 navigation.name；不能只根据 location.search 补交。
        return original.origin === 'https://chatgpt.com' && original.pathname === '/auth/login'
          && original.searchParams.has('email') && navigation.type === 'navigate';
        """)
    except Exception:
        native_get = False
    if native_get is not True:
        return {"ok": False, "reason": "native_get_not_confirmed"}
    return _submit_email_form_stable(driver, email)

def _submit_email_via_browser_nextauth(driver, email: str) -> dict:
    """在 Roxy 浏览器上下文里调用 ChatGPT NextAuth signin。

    UI submit 在 Roxy/Chrome 150 上会偶发只跳到 `/auth/login?email=...` 后停住。
    这里改走浏览器页面内 fetch，仍使用当前 Roxy 浏览器的 cookie / 指纹环境，
    拿到 auth.openai.com authorize URL 后让浏览器跳转。
    """
    budget = getattr(driver, "_registration_stage_budget", None)
    if not isinstance(budget, StageBudget):
        budget = None
    if budget is not None:
        budget.require("邮箱认证导航兜底")
    advanced_state = _email_submit_advanced_state(driver, budget=budget)
    if advanced_state:
        return {
            "ok": True,
            "stage": "already_advanced",
            "state": advanced_state,
            "url": _diagnostic_url(getattr(driver, "current_url", "")),
        }
    if _email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
        raise _EmailSubmissionUnknown("request_unknown: 邮箱已交给前端提交，禁止重复认证导航")
    try:
        current = str(getattr(driver, "current_url", "") or "")
        if "chatgpt.com" not in current:
            return {"ok": False, "reason": "not_on_chatgpt", "url": _diagnostic_url(current)}
    except Exception:
        current = ""

    did = str(uuid.uuid4())
    auth_log_id = str(uuid.uuid4())
    nextauth_receipt = getattr(driver, "_browser_submission_receipt", None)
    if nextauth_receipt is None:
        nextauth_receipt = BrowserSubmissionReceipt(
            kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "email",
            stage="nextauth", endpoint_kind="nextauth_signin", http_method="POST",
        )
        driver._browser_submission_receipt = nextauth_receipt
    old_script_timeout = int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)
    fetch_timeout = _budget_timeout(budget, 25.0, minimum=0.0)
    signin_dispatch_started = False
    try:
        try:
            previous = driver.timeouts.script
            if isinstance(previous, (int, float)):
                old_script_timeout = previous
        except Exception:
            pass
        try:
            driver.set_script_timeout(fetch_timeout)
        except Exception:
            pass
        csrf_result = driver.execute_async_script(r"""
        const callback = arguments[arguments.length - 1];
        const controller = new AbortController();
        let settled = false;
        const done = value => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          callback(value);
        };
        const timer = setTimeout(() => {
          controller.abort();
          done({ok:false, stage:'timeout', reason:'nextauth_budget_exhausted'});
        }, arguments[3]);
        if (location.origin !== 'https://chatgpt.com') {
          done({ok:false, reason:'not_on_chatgpt'}); return;
        }
        (async () => {
          try {
            const csrfResp = await fetch('/api/auth/csrf', {
              method: 'GET',
              signal: controller.signal,
              credentials: 'include',
              headers: {
                'accept': 'application/json',
                'cache-control': 'no-cache',
                'pragma': 'no-cache'
              }
            });
            const csrfText = await csrfResp.text();
            let csrfData = {};
            try { csrfData = JSON.parse(csrfText); } catch (_) {}
            const csrfToken = csrfData.csrfToken || '';
            if (!csrfResp.ok || !csrfToken) {
              done({ok:false, stage:'csrf', status:csrfResp.status, error_type:'csrf_http'});
              return;
            }
            // Token 仅经当前 WebDriver 调用返回，不落库、不写日志。
            done({ok:true, stage:'csrf_ready', csrf_token:csrfToken});
          } catch (e) {
            done({ok:false, stage:'exception', error_type:'nextauth_exception'});
          }
        })();
        """, email, did, auth_log_id, max(1, int(fetch_timeout * 1000) - 50)) or {}
        if not isinstance(csrf_result, dict):
            return {"ok": False, "not_dispatched": True, "reason": "csrf_preflight_result_unknown"}
        if not csrf_result.get("ok") or csrf_result.get("stage") != "csrf_ready":
            return {**csrf_result, "not_dispatched": True}
        csrf_token = str(csrf_result.get("csrf_token") or "")
        if not csrf_token:
            return {"ok": False, "not_dispatched": True, "reason": "csrf_preflight_token_missing"}

        if budget is not None:
            budget.require("NextAuth signin 请求")
        signin_timeout = _budget_timeout(budget, 25.0, minimum=0.0)
        if signin_timeout <= 0:
            return {"ok": False, "not_dispatched": True, "reason": "nextauth_budget_exhausted"}
        try:
            driver.set_script_timeout(signin_timeout)
        except Exception:
            pass
        # CSRF 是只读预检；只有它成功后才为即将发送的 signin POST 建立围栏。
        record_browser_submission_fact(driver, "dispatch_intent", receipt=nextauth_receipt)
        signin_dispatch_started = True
        result = driver.execute_async_script(r"""
        const email = String(arguments[0] || '').trim();
        const did = String(arguments[1] || '');
        const authLogId = String(arguments[2] || '');
        const csrfToken = String(arguments[3] || '');
        const callback = arguments[arguments.length - 1];
        const controller = new AbortController();
        let settled = false;
        const done = value => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          callback(value);
        };
        const timer = setTimeout(() => {
          controller.abort();
          done({ok:false, stage:'timeout', reason:'nextauth_budget_exhausted'});
        }, arguments[4]);
        if (location.origin !== 'https://chatgpt.com') {
          done({ok:false, not_dispatched:true, reason:'not_on_chatgpt'}); return;
        }
        (async () => {
          if (!csrfToken) {
            done({ok:false, stage:'signin', not_dispatched:true, error_type:'csrf_state_missing'});
            return;
          }
          try {
            const q = new URLSearchParams({
              prompt: 'login',
              'ext-oai-did': did,
              auth_session_logging_id: authLogId,
              'ext-passkey-client-capabilities': '11111',
              screen_hint: 'login_or_signup',
              login_hint: email
            });
            const body = new URLSearchParams({
              callbackUrl: 'https://chatgpt.com/', csrfToken, json: 'true'
            });
            const resp = await fetch('/api/auth/signin/openai?' + q.toString(), {
              method: 'POST', signal: controller.signal, credentials: 'include',
              headers: {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'cache-control': 'no-cache',
                'pragma': 'no-cache'
              },
              body: body.toString()
            });
            const text = await resp.text();
            let data = {};
            try { data = JSON.parse(text); } catch (_) {}
            let url = data.url || '';
            if (!resp.ok || !url) {
              done({ok:false, stage:'signin', status:resp.status, error_type:'signin_http'});
              return;
            }
            try {
              const u = new URL(url, location.href);
              if (!u.searchParams.get('screen_hint')) u.searchParams.set('screen_hint', 'login_or_signup');
              if (!u.searchParams.get('login_hint')) u.searchParams.set('login_hint', email);
              if (!u.searchParams.get('ext-oai-did')) u.searchParams.set('ext-oai-did', did);
              if (!u.searchParams.get('auth_session_logging_id')) u.searchParams.set('auth_session_logging_id', authLogId);
              url = u.toString();
            } catch (_) {}
            // 先把目标 URL 返回给 Python，再由 Selenium 发起顶层导航。
            // 若在 async callback 返回前直接 location.assign，页面卸载会吞掉 callback，
            // 最终表现为 execute_async_script 超时，实际跳转结果也无法确认。
            done({ok:true, stage:'redirect_ready', url});
          } catch (e) {
            done({ok:false, stage:'exception', error_type:'nextauth_exception'});
          }
        })();
        """, email, did, auth_log_id, csrf_token, max(1, int(signin_timeout * 1000) - 50)) or {}
        if not isinstance(result, dict):
            record_browser_submission_fact(driver, "unknown", receipt=nextauth_receipt, result="unknown")
            return {"ok": False, "reason": "invalid_result", "result": str(result)[:300]}
        if not result.get("ok"):
            if result.get("not_dispatched"):
                record_browser_submission_fact(
                    driver, "not_dispatched", receipt=nextauth_receipt,
                    result="cancelled", error_type=str(result.get("error_type") or "not_dispatched"),
                )
                return result
            status = result.get("status")
            try:
                status_code = int(status)
            except (TypeError, ValueError):
                status_code = 0
            # signin POST 被明确拒绝才可收口；预检 GET 不进入提交事实。
            phase = "rejected" if status_code in {400, 401} else "response_observed"
            record_browser_submission_fact(
                driver, phase, receipt=nextauth_receipt,
                http_status=status, result="failure", error_type=str(result.get("stage") or "nextauth_error"),
            )
            return result

        target_url = str(result.get("url") or "").strip()
        try:
            parsed = urlsplit(target_url)
        except Exception:
            parsed = None
        if not parsed or parsed.scheme != "https" or parsed.hostname not in ("auth.openai.com", "chatgpt.com"):
            record_browser_submission_fact(driver, "unknown", receipt=nextauth_receipt, result="unknown", error_type="unsafe_redirect")
            return {"ok": False, "reason": "unsafe_redirect_url", "url": _diagnostic_url(target_url)}

        if budget is not None:
            budget.require("邮箱认证跳转")
            # 同一剩余预算内交给调用方确认落点，不让 WebDriver 导航另启 45 秒等待。
            driver.execute_script("const target = arguments[0]; setTimeout(() => location.assign(target), 0);", target_url)
            record_browser_submission_fact(driver, "ui_dispatched", receipt=nextauth_receipt)
            return {"ok": True, "stage": "redirect_dispatched", "target_url": _diagnostic_url(target_url)}

        _safe_get(
            driver,
            target_url,
            timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("auth.openai.com", "chatgpt.com"),
        )
        human_delay("navigate")
        _page_warmup(driver, reason="nextauth_email_fallback")
        landing_url = str(getattr(driver, "current_url", "") or "")
        advanced_state = _email_submit_advanced_state(driver)
        if advanced_state:
            record_browser_submission_fact(driver, "confirmed", receipt=nextauth_receipt, result="success")
            return {
                "ok": True,
                "stage": "landed",
                "state": advanced_state,
                "url": _diagnostic_url(landing_url),
                "target_url": _diagnostic_url(target_url),
            }
        try:
            landing_host = str(urlsplit(landing_url).hostname or "").lower()
        except Exception:
            landing_host = ""
        if landing_host == "auth.openai.com":
            return {
                "ok": True,
                "stage": "auth_landed",
                "url": _diagnostic_url(landing_url),
                "target_url": _diagnostic_url(target_url),
            }
        return {
            "ok": False,
            "reason": "redirect_not_landed",
            "url": _diagnostic_url(landing_url),
            "target_url": _diagnostic_url(target_url),
        }
    except Exception as exc:
        if signin_dispatch_started:
            try:
                record_browser_submission_fact(driver, "unknown", receipt=nextauth_receipt, result="unknown", error_type=type(exc).__name__)
            except Exception:
                logger.exception("%s NextAuth 提交未知事实保存失败", _log_prefix(driver))
        return {
            "ok": False, "not_dispatched": not signin_dispatch_started,
            "reason": f"NextAuth 浏览器请求失败（{type(exc).__name__}）",
        }
    finally:
        try:
            driver.set_script_timeout(old_script_timeout)
        except Exception:
            pass

def _email_input_value_state(driver) -> dict:
    """读取当前可见邮箱框状态，用于提交后确认是否真的进入下一步。"""
    try:
        return driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const inputs = [...document.querySelectorAll('input[type="email"],input[name="email"],input[name="username"],input[autocomplete*="email"]')]
          .filter(visible)
          .map(el => ({type: el.getAttribute('type') || '', name: el.name || '', id: el.id || '', autocomplete: el.getAttribute('autocomplete') || '', value: el.value || ''}));
        return {url: location.href, inputs};
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, "current_url", ""), "error": f"{type(exc).__name__}: {exc}"}

def _is_email_login_page_still_present(driver) -> bool:
    state = _email_input_value_state(driver)
    return bool(state.get("inputs"))

def _diagnostic_url(value: object) -> str:
    """诊断日志只保留 URL 路径，避免记录授权 state、code 等查询参数。"""
    text = str(value or "").strip()
    try:
        parsed = urlsplit(text)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        pass
    return text[:240]

def _redact_diagnostic_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"https?://[^\s\"'<>]+", lambda m: _diagnostic_url(m.group(0)), text)
    text = re.sub(
        r"(?i)\b(access[_-]?token|csrf[_-]?token|state|code)=([^\s&]+)",
        lambda m: f"{m.group(1)}=<redacted>",
        text,
    )
    return text[:500]

def _log_blank_auth_shell_diagnostics(driver, state: dict | None = None) -> None:
    """记录空白认证壳的轻量现场，供区分页面渲染失败和请求失败。"""
    snapshot: dict = {}
    try:
        snapshot = driver.execute_script(r"""
        const safeUrl = value => {
          try { const u = new URL(String(value || ''), location.href); return `${u.origin}${u.pathname}`; }
          catch (_) { return String(value || '').slice(0, 240); }
        };
        const resources = (performance.getEntriesByType('resource') || []).slice(-20).map(item => ({
          url: safeUrl(item.name),
          type: item.initiatorType || '',
          duration_ms: Math.round(Number(item.duration || 0)),
          transfer_size: Number(item.transferSize || 0)
        }));
        return {
          url: safeUrl(location.href),
          title: document.title || '',
          ready_state: document.readyState || '',
          body_text_length: (document.body?.innerText || '').length,
          html_length: (document.documentElement?.outerHTML || '').length,
          script_count: document.scripts?.length || 0,
          resources
        };
        """) or {}
    except Exception as exc:
        snapshot = {"snapshot_error": f"{type(exc).__name__}: {exc}"}

    console_errors: list[dict] = []
    try:
        for item in (driver.get_log("browser") or [])[-20:]:
            level = str(item.get("level") or "").upper()
            if level not in {"WARNING", "SEVERE"}:
                continue
            console_errors.append({
                "level": level,
                "message": _redact_diagnostic_text(item.get("message")),
            })
    except Exception:
        # debuggerAddress 模式不一定开启 browser log，缺失不影响注册流程。
        pass

    if state and not snapshot.get("url"):
        snapshot["url"] = _diagnostic_url(state.get("url"))
    snapshot["console"] = console_errors
    logger.warning("%s 登录空白壳诊断：%s", _log_prefix(driver), snapshot)

def _wait_email_submit_next_state(
    driver,
    email: str,
    timeout: int = 18,
    *,
    wait_through_transient: bool = False,
    budget: StageBudget | None = None,
    blank_shell_grace: float = 0.0,
) -> str:
    """邮箱提交后等待进入 password / otp / logged_in；仍停留邮箱页则返回 email_page。

    ``wait_through_transient`` 用于 NextAuth 已发起导航后的最终落点确认：此时登录空壳
    和被清空的邮箱框都只视为过渡态，持续等到明确下一步或整体超时。

    Cloak/Playwright 路径里，点击 submit 后页面经常先发生一次 SPA 导航：
    `chatgpt.com/auth/login?email=...`，同时 React 会短暂把 email input 清空。
    旧逻辑一看到空 input 就立刻返回 `email_cleared`，导致在真正跳到
    `auth.openai.com/...` 前过早重填，形成“提交 -> 清空 -> 重填”的循环。
    已有前端提交凭据时等待同一预算，结果未知不得重试；仅无当前提交凭据的
    旧原生 GET 路径使用短暂去抖，再由导航证据决定是否允许恢复。
    """
    if budget is None:
        budget = getattr(driver, "_registration_stage_budget", None)
    timeout = _budget_timeout(budget, timeout, minimum=0.0)
    clock = budget.clock if budget is not None else time.time
    end = clock() + max(0.0, timeout)
    last = None
    cleared_seen_at: float | None = None
    cleared_last_log_at = 0.0
    cleared_recover_done = False
    blank_shell_seen_at: float | None = None
    blank_shell_logged = False
    transient_shell_logged = False
    queued_seen_at: float | None = None
    recovery_attempted = False
    wait_started = end - max(0.0, timeout)
    next_diagnostic_at = wait_started + 15.0

    def observe_recovery(recovery_budget):
        snapshot = _page_snapshot(driver)
        if classify_page(snapshot) in {PageState.PASSWORD_CREATE, PageState.PASSWORD_LOGIN, PageState.OTP_EMAIL}:
            if not has_visible_auth_inputs(snapshot):
                return None
        return _email_submit_advanced_state(driver, budget=recovery_budget)

    expected_email = str(email or "").strip().lower()
    try:
        blank_shell_grace = max(0.0, min(10.0, float(blank_shell_grace or 0.0)))
    except (TypeError, ValueError):
        blank_shell_grace = 0.0
    while True:
        _check_manual_stop()
        loop_now = clock()
        if loop_now >= end:
            break
        active_receipt = isinstance(getattr(driver, "_email_submission_receipt", None), dict)
        submission_state = _email_ui_submission_state(driver)
        if submission_state in {"queued", "dispatched", "unknown"} and budget is not None:
            end = max(end, budget.deadline)
        # NextAuth 落点也可能只加载了验证码页 HTML，尚未挂载表单。
        # 必须先于按路由判断的下一步检测，避免把空壳确认成 OTP 并清除提交屏障。
        try:
            current = urlsplit(str(getattr(driver, "current_url", "") or ""))
            at_verification = current.hostname == "auth.openai.com" and current.path.rstrip("/") == "/email-verification"
        except ValueError:
            at_verification = False
        if at_verification:
            otp_state = _email_otp_page_state(driver)
            if _email_otp_page_recovery_reason(otp_state):
                refreshed = _recover_email_otp_page_if_needed(driver, otp_state, budget=StageBudget(end, clock=clock))
                if getattr(driver, "_email_otp_page_refresh_done", False):
                    recovery_attempted = True
                if loop_now >= next_diagnostic_at:
                    log_submission_diagnostics(
                        driver, "email", "waiting_for_verification_form",
                        receipt=getattr(driver, "_browser_submission_receipt", None),
                    )
                    next_diagnostic_at = loop_now + 15.0
                if not refreshed:
                    time.sleep(min(0.4, max(0.0, end - clock())))
                continue
        advanced_state = _email_submit_advanced_state(driver, budget=budget) if active_receipt else _email_submit_advanced_state(driver)
        if advanced_state:
            return advanced_state
        http_receipt = getattr(driver, "_browser_submission_receipt", None)
        if (getattr(http_receipt, "http_status", None) in {403, 429}
                and getattr(http_receipt, "result", "") == "failure"):
            # 已有明确响应时不再把整个等待耗在禁用的旧表单上；是否开始
            # 新登录由外层核验原身份及新文档，不能在这里重放旧提交。
            status = http_receipt.http_status
            log_submission_diagnostics(driver, "email", "http_rejected", receipt=http_receipt)
            raise _EmailSubmissionUnknown(
                f"request_unknown: email_auth_http_{status}: 邮箱认证请求返回 HTTP {status}，页面尚未进入下一步"
            )
        if submission_state == "cancelled":
            logger.info("%s 邮箱点击前校验未通过，未执行提交：%s", _log_prefix(driver),
                        getattr(driver, "_email_submission_diagnostics", None))
            return "email_frontend_not_ready"
        if submission_state in {"queued", "dispatched", "unknown"}:
            if submission_state == "queued":
                if queued_seen_at is None:
                    queued_seen_at = clock()
                if clock() - queued_seen_at >= 3.0 and _cancel_queued_email_submission(driver):
                    logger.info("%s 邮箱点击排队超时，已确认取消未执行的点击：%s", _log_prefix(driver),
                                getattr(driver, "_email_submission_diagnostics", None))
                    return "email_frontend_not_ready"
            else:
                queued_seen_at = None
            # 已交给前端的请求共享整个剩余预算；输入框清空不是提交失败证据。
            if loop_now >= next_diagnostic_at:
                log_submission_diagnostics(
                    driver, "email", "waiting", receipt=getattr(driver, "_browser_submission_receipt", None),
                    ui=getattr(driver, "_email_submission_diagnostics", None),
                )
                next_diagnostic_at = loop_now + 15.0
            if (not recovery_attempted and loop_now - wait_started >= 5.0
                    and loop_now >= end - RECOVERY_WINDOW_SECONDS):
                recovery_attempted = True
                recovered = recover_submission_page(
                    driver, "email", observe_recovery,
                    budget=StageBudget(end, clock=clock),
                    receipt=getattr(driver, "_browser_submission_receipt", None), sleeper=time.sleep,
                )
                if recovered:
                    logger.info("%s 邮箱提交等待已通过刷新进入下一步：%s", _log_prefix(driver), recovered)
                    return recovered
            time.sleep(min(0.4, max(0.0, end - clock())))
            continue
        state = _email_input_value_state(driver)
        last = state
        inputs = state.get("inputs") or []
        if not inputs and _is_blank_chatgpt_auth_shell(driver):
            if not wait_through_transient:
                if blank_shell_grace > 0:
                    if blank_shell_seen_at is None:
                        blank_shell_seen_at = loop_now
                    if not blank_shell_logged:
                        logger.info(
                            "%s 邮箱提交后检测到登录空壳，先等待页面组件挂载：grace=%.1fs",
                            _log_prefix(driver), blank_shell_grace,
                        )
                        blank_shell_logged = True
                    if loop_now - blank_shell_seen_at < blank_shell_grace:
                        time.sleep(min(0.4, max(0.0, end - loop_now)))
                        continue
                logger.warning("%s 邮箱提交后进入 ChatGPT 登录空壳页，立即切换认证兜底", _log_prefix(driver))
                return "blank_shell"
            if not transient_shell_logged:
                logger.info("%s 认证兜底后仍在登录过渡页，继续等待最终跳转", _log_prefix(driver))
                transient_shell_logged = True
        else:
            blank_shell_seen_at = None
            blank_shell_logged = False
        if inputs:
            values = [str(i.get("value") or "") for i in inputs]
            url = str(state.get("url") or "")
            has_blank = any(v == "" for v in values)
            has_expected = any(v.strip().lower() == expected_email for v in values)
            if has_blank and not has_expected:
                now = clock()
                if cleared_seen_at is None:
                    cleared_seen_at = now
                # 当前没有前端提交凭据才会进入此旧路径；URL 带 email 本身
                # 不能证明原生 GET，下面的恢复函数还会验证最初文档导航。
                debounce = 4.0 if ("/auth/login" in url and "email=" in url) else 5.0
                if now - cleared_last_log_at > 2.0:
                    logger.info(
                        "%s 邮箱提交后检测到输入框短暂清空，继续等待跳转：elapsed=%.1fs debounce=%.1fs url=%s",
                        _log_prefix(driver), now - cleared_seen_at, debounce, url[:180],
                    )
                    cleared_last_log_at = now
                if (
                    not cleared_recover_done
                    and not wait_through_transient
                    and "/auth/login" in url
                    and "email=" in url
                    and now - cleared_seen_at >= 2.0
                ):
                    if budget is not None:
                        budget.require("email submit recovery")
                    recover = _recover_email_submit_if_stuck(driver, email)
                    cleared_recover_done = True
                    logger.info("%s 邮箱提交后仍停留在 login?email，中途补交一次表单：%s", _log_prefix(driver), recover)
                    if _email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
                        continue
                if now - cleared_seen_at >= debounce and not wait_through_transient:
                    return "email_cleared"
            else:
                cleared_seen_at = None
            # 仍是当前邮箱页，继续短等。
        # Reuse the timestamp already sampled for this iteration.  Besides
        # avoiding an unnecessary clock call, this keeps test doubles and
        # monotonic accounting deterministic when the page is a transient SPA.
        sleep_now = now if cleared_seen_at is not None else loop_now
        time.sleep(min(0.8, max(0.0, end - sleep_now)))
    if _email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
        _log_email_submission_timeout(driver)
        log_submission_diagnostics(
            driver, "email", "timeout", receipt=getattr(driver, "_browser_submission_receipt", None),
            ui=getattr(driver, "_email_submission_diagnostics", None),
        )
        raise _EmailSubmissionUnknown("request_unknown: 邮箱提交结果在共享预算内未确认，未重复点击或发送认证请求")
    logger.info("%s 邮箱提交后等待下一步超时，最后邮箱页状态=%s", _log_prefix(driver), last)
    return "email_page" if _is_email_login_page_still_present(driver) else "unknown"


def _recover_saved_login_email_page(driver, *, budget: StageBudget) -> str | None:
    """原身份续跑只在受控 GET 后的新页面恢复，不重新点击旧邮箱表单。"""
    if not getattr(driver, "_registration_resume_login", False) or budget.expired():
        return None

    def document_time_origin():
        try:
            value = driver.execute_script("return performance.timeOrigin;")
            if type(value) in (int, float) and math.isfinite(value) and value > 0:
                return float(value)
        except Exception:
            pass
        return None

    original_document = document_time_origin()
    if original_document is None:
        return None

    def observe(recovery_budget):
        snapshot = _page_snapshot(driver)
        page_state = classify_page(snapshot)
        if (page_state in {PageState.PASSWORD_CREATE, PageState.PASSWORD_LOGIN, PageState.OTP_EMAIL}
                and not has_visible_auth_inputs(snapshot)):
            return None
        advanced = _email_submit_advanced_state(driver, budget=recovery_budget)
        if advanced:
            return advanced
        _email_ui_submission_state(driver)
        diagnostics = getattr(driver, "_email_submission_diagnostics", None)
        if not isinstance(diagnostics, dict) or diagnostics.get("same_document") is not False:
            return None
        current_document = document_time_origin()
        if current_document is None or current_document == original_document:
            return None
        current = urlsplit(str(snapshot.get("url") or ""))
        trusted_email_route = (
            current.scheme == "https" and current.port in (None, 443)
            and not current.username and not current.password
            and (current.hostname, current.path.rstrip("/")) in {
                ("chatgpt.com", "/auth/login"), ("auth.openai.com", "/log-in"),
                ("auth.openai.com", "/log-in/email"),
            }
        )
        email_input_present = any(
            isinstance(item, dict) and item.get("visible") is not False
            and (str(item.get("type") or "").lower() == "email"
                 or str(item.get("name") or "").lower() in {"email", "username"}
                 or str(item.get("autocomplete") or "").lower() == "email")
            for item in snapshot.get("inputs") or []
        )
        if trusted_email_route and email_input_present:
            return "email_resume_ready"
        return None

    return recover_submission_page(
        driver, "email", observe, budget=budget,
        receipt=getattr(driver, "_browser_submission_receipt", None), sleeper=time.sleep,
    )


def _submit_email_and_wait_next(
    driver,
    email: str,
    attempts: int = 3,
    on_submitted=None,
    total_timeout: int = EMAIL_OUTER_TIMEOUT,
    allow_login_password: bool = False,
    on_progress=None,
) -> str:
    """一次流程独占提交凭据，结束后不把状态带入下一账号或独立调用。"""
    driver._email_submission_receipt = None
    driver._email_submission_diagnostics = None
    # 仅显式续跑入口可标记为 resume_login；存储层仍会核对原 Attempt
    # 已保存密码和恢复 checkpoint，普通入口不能借此绕过未知提交围栏。
    # 这些属性只属于本次邮箱流程；补密码会在同一 driver 上再次独立登录，
    # 不能沿用本次已耗尽的预算，也不能删除调用方或外层流程自己的回调。
    scope_attributes = (
        "_registration_resume_login", "_registration_email_progress",
        "_registration_stage_budget", "_registration_before_email_dispatch",
    )
    previous_scope = {
        name: (hasattr(driver, name), getattr(driver, name, None))
        for name in scope_attributes
    }
    driver._registration_resume_login = bool(allow_login_password)
    try:
        return _submit_email_and_wait_next_impl(
            driver, email, attempts, on_submitted, total_timeout, allow_login_password, on_progress,
        )
    except StageTimeout as exc:
        if isinstance(getattr(driver, "_email_submission_receipt", None), dict):
            _log_email_submission_timeout(driver)
            raise _EmailSubmissionUnknown("request_unknown: 邮箱提交后阶段预算耗尽，远端结果未确认") from exc
        raise
    finally:
        driver._email_submission_receipt = None
        for name, (existed, previous_value) in previous_scope.items():
            if existed:
                setattr(driver, name, previous_value)
            else:
                try:
                    delattr(driver, name)
                except AttributeError:
                    pass


def _submit_email_and_wait_next_impl(
    driver,
    email: str,
    attempts: int = 3,
    on_submitted=None,
    total_timeout: int = EMAIL_OUTER_TIMEOUT,
    allow_login_password: bool = False,
    on_progress=None,
) -> str:
    """填写并提交邮箱：准备、单次提交和整个阶段各自受有界预算约束。"""
    last_state = None
    nextauth_fallback_done = False
    submitted_reported = False
    submission_started = False
    saved_login_restarted = False

    def _progress(phase: str, detail: str) -> None:
        if on_progress is not None:
            try:
                on_progress(phase, detail)
            except Exception:
                logger.exception("%s 上报邮箱观察进度失败", _log_prefix(driver))
    requested_timeout = EMAIL_OUTER_TIMEOUT if total_timeout is None else float(total_timeout)
    # 240 秒是默认软上限；调用方传入更小预算时必须原样收紧，不能用历史的
    # “至少 10 秒”兜底把测试/取消预算重新放大。
    outer_budget = StageBudget.start(max(0.0, min(float(EMAIL_OUTER_TIMEOUT), requested_timeout)))
    # 准备和提交各自只有一份子预算。提交预算只在真正进入提交/兜底阶段时
    # 创建一次，且两者都受同一个外层截止时间约束。
    def _phase_budget(limit: float, *, initial: bool = False):
        child = getattr(outer_budget, "child", None)
        if callable(child):
            return child(limit)
        if initial:
            return outer_budget
        # 兼容旧测试/适配器提供的最小预算替身；生产 StageBudget 始终受
        # outer_budget 截止时间约束。
        return StageBudget.start(limit)

    preparation_budget = _phase_budget(EMAIL_PREPARATION_TIMEOUT, initial=True)
    submission_budget = None
    budget = preparation_budget
    # Keep the helper's historical call signature stable for integrations that
    # patch it, while still sharing the active budget with the real helper.
    try:
        setattr(driver, "_registration_stage_budget", budget)
    except Exception:
        pass

    def _remaining(limit: int) -> int:
        return max(0.0, min(float(limit), budget.remaining()))

    def _use_submission_budget(*, new_request: bool = False) -> StageBudget:
        nonlocal submission_budget, budget
        if submission_budget is None or new_request:
            submission_budget = _phase_budget(EMAIL_SUBMISSION_TIMEOUT)
        budget = submission_budget
        try:
            setattr(driver, "_registration_stage_budget", submission_budget)
        except Exception:
            pass
        return submission_budget

    driver._registration_email_progress = _progress

    def _accept_advanced_state(state_name: str | None, source: str) -> str | None:
        nonlocal submitted_reported
        if state_name == "login_password":
            if allow_login_password:
                logger.info(
                    "%s %s已进入登录密码页；这是待验证账号恢复任务，继续使用已保存密码",
                    _log_prefix(driver),
                    source,
                )
            else:
                raise RemoteExistingAccountError(
                    f"邮箱提交后进入登录密码页，已注册/不可用邮箱；检测到远端已有账号，进入人工协调: "
                    f"url={getattr(driver, 'current_url', '') or 'https://auth.openai.com/log-in/password'}"
                )
        if state_name in ("password", "otp", "logged_in", "login_password"):
            logger.info("%s %s已进入下一步：%s", _log_prefix(driver), source, state_name)
            if not submitted_reported:
                if submission_started and on_submitted is not None:
                    try:
                        # 保留零参回调契约；只有明确下一页才能结束邮箱提交步骤。
                        on_submitted()
                    except Exception:
                        logger.exception("%s 上报邮箱确认阶段失败", _log_prefix(driver))
                elif not submission_started:
                    _progress("skipped", "当前已在认证下一步，本次无需填写或提交邮箱")
                submitted_reported = True
            return state_name
        return None

    for attempt in range(1, attempts + 1):
        _check_manual_stop()
        if outer_budget.expired():
            break
        if isinstance(getattr(driver, "_email_submission_receipt", None), dict):
            # 提交后所有观察、NextAuth 兜底和落点确认共用同一份 60 秒预算。
            budget = submission_budget or preparation_budget
        else:
            # 重填只继续消耗唯一准备预算，不能每轮重新计时。
            budget = submission_budget or preparation_budget
            try:
                setattr(driver, "_registration_stage_budget", budget)
            except Exception:
                pass
        _progress("waiting_input", "正在等待可见的邮箱输入框")
        entry_state = _type_email_address(
            driver,
            email,
            timeout=_remaining(20),
            stop_on_advanced=True,
        )
        accepted = _accept_advanced_state(entry_state, "重填邮箱前页面")
        if accepted:
            return accepted
        state = _email_input_value_state(driver)
        last_state = state
        values = [str(i.get("value") or "") for i in (state.get("inputs") or [])]
        if not any(v.strip().lower() == email.strip().lower() for v in values):
            active_receipt = getattr(driver, "_browser_submission_receipt", None)
            if isinstance(getattr(driver, "_email_submission_receipt", None), dict) or (
                active_receipt is not None
                and getattr(active_receipt, "endpoint_kind", "") in {"email_submit", "nextauth_signin"}
                and getattr(active_receipt, "phase", "") in {
                    "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed", "response_observed", "unknown",
                }
            ):
                raise _EmailSubmissionUnknown("request_unknown: 邮箱提交仍待确认，未改写当前输入框")
            # send_keys 返回不代表 React 受控值已保持；提交前用当前 DOM 的
            # 原生 setter 补齐一次，再跨渲染时序确认，整个过程不点击或发请求。
            budget.require("邮箱输入恢复")
            stable = _stabilize_email_input_before_submit(driver, email)
            budget.require("邮箱输入恢复结果")
            time.sleep(min(0.2, budget.remaining()))
            budget.require("邮箱输入稳定校验")
            state = _email_input_value_state(driver)
            values = [str(i.get("value") or "") for i in (state.get("inputs") or [])]
            matched = any(v.strip().lower() == email.strip().lower() for v in values)
            logger.info("%s 邮箱输入恢复：ok=%s matched=%s value_lengths=%s", _log_prefix(driver),
                        bool(stable.get("ok")), matched, [len(value) for value in values])
            if not matched:
                last_state = {"input_count": len(values), "value_lengths": [len(value) for value in values]}
                logger.warning("%s 邮箱写入校验失败，准备重试：attempt=%s/%s value_lengths=%s",
                               _log_prefix(driver), attempt, attempts, last_state["value_lengths"])
                time.sleep(min(0.8, budget.remaining()))
                continue
        logger.info("%s 已填写邮箱并校验通过", _log_prefix(driver))
        _progress("filled", "邮箱已填写并校验，正在等待表单就绪")
        human_delay("form")
        frontend_not_ready = False
        try:
            setattr(driver, "_registration_before_email_dispatch", _use_submission_budget)
        except Exception:
            pass
        try:
            submission_started = True
            _submit_email_step(driver, email)
        except _EmailFrontendNotReady:
            submission_started = False
            frontend_not_ready = True
            state_name = "email_frontend_not_ready"
            logger.warning("%s 登录表单未接管提交，保留当前预算转入一次导航兜底", _log_prefix(driver))
        else:
            # Selenium click/submit may itself block until the browser finishes a slow
            # navigation.  Once the form has been dispatched, waiting for the remote
            # auth result is a new request and must receive a fresh budget.  Otherwise
            # the first state check can fail immediately even though the page is still
            # legitimately transitioning (observed with a 91-second proxy response).
            # 进入可能派发窗口后，确认链路获得至多 60 秒；不再重置为一份新的
            # 外层预算，且继续受 outer_budget 的截止时间约束。
            _use_submission_budget()
            _progress("pending", "邮箱提交已进入排队或派发阶段，正在确认认证下一页")
            logger.info("%s 邮箱提交尚待页面确认，等待密码页或验证码页（%s/%s）", _log_prefix(driver), attempt, attempts)
            try:
                state_name = _wait_email_submit_next_state(
                    driver,
                    email,
                    timeout=_remaining(20),
                    blank_shell_grace=3,
                )
            except _EmailSubmissionUnknown:
                if (not allow_login_password or saved_login_restarted
                        or attempt >= attempts or outer_budget.expired()):
                    raise
                saved_login_restarted = True
                recovered = _recover_saved_login_email_page(
                    driver, budget=outer_budget.child(RECOVERY_WINDOW_SECONDS),
                )
                accepted = _accept_advanced_state(recovered, "原身份邮箱提交恢复")
                if accepted:
                    return accepted
                if recovered != "email_resume_ready":
                    raise
                # 原动作保留未知/拒绝事实；新页面开始独立登录，使用唯一新
                # submission_id。两次登录仍共享外层截止时间，最多恢复一次。
                previous = getattr(driver, "_browser_submission_receipt", None)
                if previous is not None and getattr(previous, "phase", "") not in {"confirmed", "rejected", "not_dispatched", "unknown"}:
                    record_browser_submission_fact(driver, "unknown", receipt=previous,
                                                   result=getattr(previous, "result", "") or "unknown")
                driver._email_submission_receipt = None
                driver._email_submission_diagnostics = None
                driver._registration_otp_after_ts = time.time()
                submission_started = False
                _use_submission_budget(new_request=True)
                _progress("recovering", "登录页已刷新，沿用原邮箱继续同一账号认证")
                continue
            frontend_not_ready = state_name == "email_frontend_not_ready"
        accepted = _accept_advanced_state(state_name, "邮箱提交后")
        if accepted:
            return accepted
        retry_state_name = state_name
        if state_name == "blank_shell":
            _log_blank_auth_shell_diagnostics(driver, last_state)
            logger.info("%s 首次确认登录空壳，立即切换 NextAuth 导航兜底", _log_prefix(driver))
        if state_name in ("email_page", "email_cleared", "unknown", "blank_shell", "email_frontend_not_ready") and not nextauth_fallback_done:
            # 稳定脚本已经进入 unknown 后，NextAuth 也属于第二次认证 POST；
            # 只有明确 not_dispatched 才允许建立新的 submission_id 走兜底。
            submission_state = _email_ui_submission_state(driver)
            active_receipt = getattr(driver, "_browser_submission_receipt", None)
            if submission_state in {"queued", "dispatched", "unknown"} or (
                active_receipt is not None
                and getattr(active_receipt, "phase", "") in {
                    "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed",
                    "response_observed", "unknown",
                }
            ):
                raise _EmailSubmissionUnknown(
                    "request_unknown: 邮箱提交已进入可能派发窗口，禁止 NextAuth 重复认证导航"
                )
            # 前置请求明确未派发时，NextAuth 是唯一一次独立认证请求；
            # 使用新的请求预算，但仍受同一外层截止时间约束。
            _use_submission_budget(new_request=True)
            budget.require("邮箱认证导航兜底")
            nextauth_fallback_done = True
            submission_started = True
            _progress("fallback", "邮箱表单未确认派发，正在通过当前浏览器建立认证跳转")
            logger.warning("%s 邮箱认证未进入下一步，启用一次 NextAuth 导航兜底", _log_prefix(driver))
            fallback = _submit_email_via_browser_nextauth(driver, email)
            logger.info(
                "%s NextAuth 邮箱导航兜底结果：%s",
                _log_prefix(driver),
                {k: v for k, v in fallback.items() if k != "url"} | ({"url": str(fallback.get("url") or "")[:180]} if fallback.get("url") else {}),
            )
            fallback_state = str(fallback.get("state") or "")
            accepted = _accept_advanced_state(fallback_state, "NextAuth 兜底前页面")
            if accepted:
                return accepted
            should_settle = bool(fallback.get("ok")) or fallback.get("reason") == "redirect_not_landed"
            if should_settle:
                fallback_state = _wait_email_submit_next_state(
                    driver,
                    email,
                    timeout=_remaining(35),
                    wait_through_transient=True,
                )
                retry_state_name = fallback_state or retry_state_name
                accepted = _accept_advanced_state(fallback_state, "NextAuth 兜底后")
                if accepted:
                    return accepted
                if not frontend_not_ready and fallback_state in ("blank_shell", "unknown") and _is_blank_chatgpt_auth_shell(driver):
                    _reload_blank_chatgpt_auth_shell(driver)
            elif frontend_not_ready and fallback.get("not_dispatched") is True:
                # CSRF GET 失败没有发送认证 POST；页面脚本可能在预检期间
                # 刚刚加载完成。沿用剩余提交预算等就绪，再执行首次 UI 点击。
                submission_state = _email_ui_submission_state(driver)
                active_receipt = getattr(driver, "_browser_submission_receipt", None)
                no_dispatch = submission_state in {None, "cancelled"} and (
                    active_receipt is None or getattr(active_receipt, "phase", "") in {"prepared", "not_dispatched"}
                )
                if no_dispatch and not budget.expired():
                    submission_started = False
                    _progress("waiting_frontend", "认证预检未发出提交，继续等待页面就绪后自动点击继续")
                    try:
                        _submit_email_step(driver, email)
                    except _EmailFrontendNotReady:
                        pass
                    else:
                        submission_started = True
                        _progress("pending", "邮箱首次提交已进入排队或派发阶段，正在确认认证下一页")
                        fallback_state = _wait_email_submit_next_state(
                            driver, email, timeout=_remaining(35), wait_through_transient=True,
                        )
                        accepted = _accept_advanced_state(fallback_state, "页面加载完成后邮箱提交")
                        if accepted:
                            return accepted
            elif state_name == "blank_shell" and _is_blank_chatgpt_auth_shell(driver):
                # NextAuth 自身也失败时才刷新页面，保留一次 UI 重试机会。
                _reload_blank_chatgpt_auth_shell(driver)
        if frontend_not_ready and outer_budget.expired():
            break
        late_state = _email_submit_advanced_state(driver)
        accepted = _accept_advanced_state(late_state, "重试前页面")
        if accepted:
            return accepted
        if frontend_not_ready:
            # 未执行 UI 提交；导航兜底仅一次，失败后保留现场，不循环重填或重复发起。
            break
        current_state = _email_input_value_state(driver)
        last_state = current_state
        logger.warning("%s 邮箱提交后仍未进入下一步：%s，准备重填重试 state=%s", _log_prefix(driver), retry_state_name, current_state)
        time.sleep(min(1.0, max(0.0, budget.remaining())))
    if outer_budget.expired():
        raise RuntimeError(f"邮箱提交/认证跳转超过总预算 {EMAIL_OUTER_TIMEOUT} 秒，最后状态={last_state}")
    raise RuntimeError(f"邮箱提交后未进入密码页/验证码页，最后状态={last_state}")

def _type_otp(driver, code: str, *, timeout: int = 20, before_input=None) -> None:
    from selenium.webdriver.common.by import By

    # 邮件通常比认证页渲染更快。收到验证码后继续等输入框出现，避免把页面竞态
    # 误判成注册失败；同时保留硬超时，防止页面真的卡死。
    input_timeout = _budget_timeout(None, max(1, int(timeout or 20)), minimum=0)
    deadline = time.monotonic() + input_timeout
    input_budget = StageBudget(deadline, clock=time.monotonic)
    otp_send_route_seen_at = None
    otp_send_route_recovered = False
    while time.monotonic() < deadline:
        _check_manual_stop()
        current_url = str(getattr(driver, "current_url", "") or "").lower()
        if "/api/accounts/email-otp/send" in current_url:
            if otp_send_route_seen_at is None:
                otp_send_route_seen_at = time.monotonic()
                if not otp_send_route_recovered:
                    otp_send_route_recovered = True
                    try:
                        back = getattr(driver, "back", None)
                        if callable(back):
                            back()
                            time.sleep(0.8)
                            continue
                    except Exception as exc:
                        logger.warning(
                            "%s[OTP] 当前停在 email-otp/send API 路由，返回验证码页失败：%s",
                            _log_prefix(driver), type(exc).__name__,
                        )
            elif time.monotonic() - otp_send_route_seen_at >= 3.0:
                raise RuntimeError(
                    "otp_page_navigation_failed: 浏览器停留在 /api/accounts/email-otp/send，"
                    "3 秒内未恢复到验证码输入页"
                )
        else:
            otp_send_route_seen_at = None
        # 单输入框
        for selector in [
            "input[autocomplete='one-time-code']",
            "input[name='code']",
            "input[inputmode='numeric']",
            "input[type='tel']",
        ]:
            els = [e for e in driver.find_elements(By.CSS_SELECTOR, selector) if _visible(e)]
            if len(els) == 1:
                if before_input is not None:
                    before_input([els[0]])
                _human_type_text(driver, els[0], code, clear=True)
                return

        # 6 个分格输入框
        boxes = [e for e in driver.find_elements(By.CSS_SELECTOR, "input") if _visible(e)]
        numeric_boxes = []
        for e in boxes:
            attrs = " ".join(str(e.get_attribute(k) or "") for k in ("inputmode", "autocomplete", "aria-label", "name", "id", "type"))
            if any(x in attrs.lower() for x in ("numeric", "one-time", "code", "otp", "tel")):
                numeric_boxes.append(e)
        if len(numeric_boxes) >= len(code):
            selected_boxes = numeric_boxes[:len(code)]
            if before_input is not None:
                before_input(selected_boxes)
            for e, ch in zip(selected_boxes, code):
                if _browser_actions_enabled():
                    _human_scroll_to(driver, e)
                    time.sleep(random.uniform(0.04, 0.18))
                e.send_keys(ch)
                if _browser_actions_enabled():
                    human_delay("keystroke")
            return
        # 这里只在尚未输入任何验证码时恢复空壳，不重放已经填写的验证码。
        _recover_email_otp_page_if_needed(driver, budget=input_budget)
        time.sleep(min(0.35, max(0.0, deadline - time.monotonic())))

    raise RuntimeError(
        f"等待 OTP 输入框超时（{int(timeout or 20)} 秒），当前页面={str(getattr(driver, 'current_url', '') or '')[:180]}"
    )

def _email_otp_page_state(driver) -> dict:
    try:
        # 与密码入口共用初始化观测，空白的认证页仍可能在加载会话和发码接口。
        from .password_auth import _AUTH_INITIALIZATION_SNAPSHOT_JS

        return driver.execute_script(_AUTH_INITIALIZATION_SNAPSHOT_JS + r"""
        const bodyText = (document.body?.innerText || '').replace(/\s+/g, ' ').trim();
        const bodyLower = bodyText.toLowerCase();
        const emailVerified = /email\s+verified|email\s+verification\s+(?:complete|completed)|邮箱已验证|邮箱验证完成|認証が完了/.test(bodyLower);
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const inputs = [...document.querySelectorAll('input')].filter(visible).map(el => {
          const attrs = [el.type, el.name, el.id, el.autocomplete, el.inputMode,
            el.getAttribute('aria-label')].join(' ').toLowerCase();
          const sensitive = /password|one-time|otp|verification|code|token|secret|auth/.test(attrs);
          return {
            type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
            autocomplete: el.getAttribute('autocomplete') || '', inputmode: el.getAttribute('inputmode') || '',
            ariaInvalid: el.getAttribute('aria-invalid') || '', value: sensitive ? '<redacted>' : (el.value || '')
          };
        });
        const buttons = [...document.querySelectorAll('button,a,[role=button],input[type=button],input[type=submit]')].filter(visible).map(el => ({
          tag: el.tagName, type: el.getAttribute('type') || '', value: el.getAttribute('value') || '',
          action: el.getAttribute('data-dd-action-name') || '', aria: el.getAttribute('aria-label') || '',
          disabled: !!el.disabled || String(el.getAttribute('aria-disabled') || '').toLowerCase() === 'true',
          text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120)
        }));
        const errors = [...document.querySelectorAll('.react-aria-FieldError,[slot="errorMessage"],[id$="-error"],[aria-invalid="true"] + *,[class*="error"]')]
          .filter(visible).map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
        const challengePresent = [...document.querySelectorAll(
          'iframe[src*="challenges.cloudflare.com"],iframe[src*="captcha"],[data-sitekey],#challenge-running,#challenge-stage'
        )].some(visible);
        return {url: location.href, title: document.title, inputs, buttons, errors, text: bodyText.slice(0, 1200), emailVerified, challengePresent, initialization:authInitialization};
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, 'current_url', ''), "error": f"{type(exc).__name__}: {exc}"}


def _email_otp_form_is_ready(state: dict) -> bool:
    """以实际挂载的验证码输入框判断就绪，不能只相信 SPA 路由。"""
    for item in state.get("inputs") or []:
        if not isinstance(item, dict) or item.get("visible") is False:
            continue
        attrs = " ".join(str(item.get(key) or "") for key in (
            "type", "name", "id", "autocomplete", "inputmode",
        )).lower()
        if any(marker in attrs for marker in ("one-time-code", "otp", "code", "numeric", "tel")):
            return True
    return False


def _email_otp_page_recovery_reason(state: dict) -> str:
    """只恢复邮箱验证路由的空壳、内容类型错误和明确的服务端路由错误。"""
    if not isinstance(state, dict):
        return ""
    try:
        parsed = urlsplit(str(state.get("url") or ""))
        if (parsed.scheme != "https" or parsed.hostname != "auth.openai.com" or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.path.rstrip("/") != "/email-verification"):
            return ""
    except ValueError:
        return ""
    if state.get("error") or state.get("emailVerified") or state.get("challengePresent") or state.get("inputs"):
        return ""
    text = str(state.get("text") or "").strip().lower()
    if any(marker in text for marker in (
        "captcha", "challenge", "verify you are human", "checking your browser", "account_deactivated",
        "deactivated", "disabled", "banned", "account deleted", "账号停用", "账号禁用", "账号已删除",
    )):
        return ""
    if all(marker in text for marker in ("route error", "400", "invalid content type", "text/html")):
        return "route_content_type_error"
    if re.search(r"route error\s*\(\s*5\d{2}\b", text):
        return "route_server_error"
    if state.get("errors") or "text" not in state:
        return ""
    for button in state.get("buttons") or []:
        if str(button.get("tag") or "").upper() != "A":
            return ""
        text = text.replace(str(button.get("text") or "").strip().lower(), "")
    if text.replace("chatgpt", "").replace("openai", "").strip():
        return ""
    return "blank_shell"


def _email_otp_initialization_pending(state: dict) -> bool:
    initialization = state.get("initialization")
    return bool(isinstance(initialization, dict) and initialization and (
        initialization.get("pending") or initialization.get("ready") != "complete"
        or initialization.get("recent_activity")
        or (initialization.get("hydration_started") and not initialization.get("hydration_ended"))
    ))


def _recover_email_otp_page_if_needed(driver, state: dict | None = None, *, budget: StageBudget | None = None) -> bool:
    """每个浏览器执行最多刷新一次，保留 Python 中的原提交回执。"""
    state = state if isinstance(state, dict) else _email_otp_page_state(driver)
    reason = _email_otp_page_recovery_reason(state)
    if not reason:
        driver._email_otp_blank_seen_at = None
        return False
    if getattr(driver, "_email_otp_page_refresh_done", False):
        return False
    if budget is not None and budget.remaining() < 1:
        return False
    if reason == "blank_shell":
        if _email_otp_initialization_pending(state):
            driver._email_otp_blank_seen_at = None
            return False
        now = time.monotonic()
        seen_at = getattr(driver, "_email_otp_blank_seen_at", None)
        if seen_at is None:
            driver._email_otp_blank_seen_at = now
            return False
        if now - seen_at < 3:
            return False
    # 刷新前重新读取现场，避免用旧快照刷新已经进入资料页的浏览器。
    fresh = _email_otp_page_state(driver)
    if (_email_otp_page_recovery_reason(fresh) != reason
            or (reason == "blank_shell" and _email_otp_initialization_pending(fresh))
            or str(getattr(driver, "current_url", "")) != str(fresh.get("url") or "")):
        driver._email_otp_blank_seen_at = None
        return False
    try:
        refresh_timeout = _budget_timeout(budget, 10, minimum=0)
    except StageTimeout:
        return False
    if refresh_timeout < 1:
        return False
    setter = getattr(driver, "set_page_load_timeout", None)
    old_timeout = None
    try:
        logger.warning("%s[OTP] 验证码页异常，执行一次受限刷新；保留原提交且不重发：reason=%s", _log_prefix(driver), reason)
        log_submission_diagnostics(driver, "otp", "before_form_refresh", receipt=getattr(driver, "_browser_submission_receipt", None))
        latest = _email_otp_page_state(driver)
        if (_email_otp_page_recovery_reason(latest) != reason
                or (reason == "blank_shell" and _email_otp_initialization_pending(latest))
                or str(getattr(driver, "current_url", "")) != str(fresh.get("url") or "")):
            return False
        refresh_timeout = _budget_timeout(budget, 10, minimum=0)
        if refresh_timeout < 1:
            return False
        if callable(setter):
            old_timeout = float(driver.timeouts.page_load)
            setter(refresh_timeout)
        driver._email_otp_page_refresh_done = True
        # 明确 GET 验证码页面，避免浏览器重新发送上一份表单 POST。
        driver.get(str(fresh.get("url")))
        log_submission_diagnostics(driver, "otp", "after_form_refresh", receipt=getattr(driver, "_browser_submission_receipt", None))
        return True
    except Exception as exc:
        from selenium.common.exceptions import TimeoutException

        logger.warning("%s[OTP] 验证码页刷新异常，继续确认原结果，不追加刷新或提交：%s", _log_prefix(driver), type(exc).__name__)
        if isinstance(exc, TimeoutException):
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
        return False
    finally:
        if old_timeout is not None:
            try:
                setter(old_timeout)
            except Exception:
                pass


def _wait_email_otp_page_ready(driver, timeout: float = 45, *, budget: StageBudget | None = None) -> str:
    """收码前等待表单挂载；页面恢复与轮询共用原阶段的剩余预算。"""
    if budget is not None and budget.expired():
        return "stuck"
    timeout = _budget_timeout(budget, timeout, minimum=0)
    ready_budget = budget.child(timeout) if budget is not None else StageBudget.start(timeout, clock=time.monotonic)
    # 页面慢挂载时给刷新后的观察留出时间，仍受原 OTP 总预算裁剪。
    log_submission_diagnostics(driver, "otp", "waiting_for_form", receipt=getattr(driver, "_browser_submission_receipt", None))
    while not ready_budget.expired():
        _check_manual_stop()
        ready_budget.check_cancelled()
        state = _email_otp_page_state(driver)
        if not isinstance(state, dict):
            return "stuck"
        try:
            parsed = urlsplit(str(state.get("url") or ""))
        except ValueError:
            return "stuck"
        page_state = classify_page(state)
        if page_state == PageState.MFA_TOTP:
            return "totp_required"
        if state.get("emailVerified") or page_state == PageState.EMAIL_VERIFIED:
            return "email_verified"
        if page_state in (PageState.PROFILE, PageState.AUTHENTICATED):
            return "accepted"
        if page_state == PageState.LOGGED_OUT or auth_session_unavailable(driver):
            log_submission_diagnostics(driver, "otp", "auth_session_unavailable", receipt=getattr(driver, "_browser_submission_receipt", None))
            return "session_expired"
        if page_state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
            return "stuck"
        if _email_otp_form_is_ready(state):
            driver._email_otp_blank_seen_at = None
            return "ready"
        # 未确认的其他路由不进入收码，避免把未知页面当成就绪表单。
        if parsed.hostname != "auth.openai.com" or parsed.path.rstrip("/") != "/email-verification":
            return "stuck"
        if _recover_email_otp_page_if_needed(driver, state, budget=ready_budget):
            continue
        time.sleep(min(0.35, ready_budget.remaining()))
    log_submission_diagnostics(driver, "otp", "form_timeout", receipt=getattr(driver, "_browser_submission_receipt", None))
    return "stuck"


def _is_email_verification_page(driver) -> bool:
    try:
        url = str(driver.current_url or '').lower()
    except Exception:
        url = ''
    if '/log-in/password' in url:
        return False
    state = _email_otp_page_state(driver)
    if not isinstance(state, dict):
        state = {}
    if state.get("emailVerified"):
        return False
    if 'email-verification' in url:
        _clear_confirmed_email_submission(driver)
        return True
    attrs = ' '.join(' '.join(str(i.get(k) or '') for k in ('type','name','id','autocomplete','inputmode')) for i in (state.get('inputs') or [])).lower()
    confirmed = 'one-time-code' in attrs or 'otp' in attrs or 'code' in attrs
    if confirmed:
        _clear_confirmed_email_submission(driver)
    return confirmed

def _clear_otp_inputs(driver) -> None:
    try:
        driver.execute_script(r"""
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const inputs = [...document.querySelectorAll('input')].filter(visible).filter(el => {
          const attrs = [el.type, el.name, el.id, el.autocomplete, el.inputMode, el.getAttribute('aria-label')].join(' ').toLowerCase();
          return /one-time|otp|code|numeric|tel/.test(attrs);
        });
        for (const el of inputs) {
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
          if (setter) setter.call(el, ''); else el.value = '';
          el.dispatchEvent(new Event('input', {bubbles:true}));
          el.dispatchEvent(new Event('change', {bubbles:true}));
        }
        """)
    except Exception:
        pass


def _read_resend_receipt(driver, receipt: dict, *, timeout: float, budget: StageBudget | None,
                         initial_now: float | None = None) -> dict:
    """重发已点击后的只读收口；读取异常不能再次点击同一控件。"""
    now = initial_now if initial_now is not None else time.monotonic()
    end = now + _budget_timeout(budget, timeout, minimum=0.1)
    last_error = None
    while now < end:
        _check_manual_stop()
        try:
            state_after = _email_otp_page_state(driver)
            buttons_after = state_after.get("buttons") if isinstance(state_after, dict) else []
            buttons_after = buttons_after if isinstance(buttons_after, list) else []
            resend_pattern = re.compile(r"resend|send.*new|send.*again|重新发送|重发|再次发送|再送信|届かない", re.I)
            matching = [
                item for item in buttons_after
                if resend_pattern.search(" ".join(str(item.get(key) or "") for key in ("text", "action", "aria", "value")))
            ]
            ui_ack = "confirmed" if (
                not _is_email_verification_page(driver)
                or any(bool(item.get("disabled")) for item in matching)
            ) else "unconfirmed"
            result = {
                "ok": True, "text": receipt.get("text", ""), "ui_ack": ui_ack,
                "requested_after_ts": receipt.get("requested_after_ts"),
            }
            # 读取已经完成，下一次独立重发可建立新的围栏；本次读取失败则保留围栏。
            driver._otp_resend_receipt = None
            return result
        except Exception as exc:
            last_error = exc
            now = time.monotonic()
            time.sleep(min(0.5, max(0.0, end - now)))
    raise RuntimeError(f"验证码重发点击后状态读取未确认，禁止再次点击: {type(last_error).__name__ if last_error else 'timeout'}")

def _click_resend_email_otp(driver, timeout: int = 20, *, budget: StageBudget | None = None) -> dict:
    """点击重新发送邮箱验证码。优先按 DOM 属性识别，文本仅兜底。"""
    prior = getattr(driver, "_otp_resend_receipt", None)
    if isinstance(prior, dict) and prior.get("clicked"):
        return _read_resend_receipt(driver, prior, timeout=timeout, budget=budget)
    timeout = _budget_timeout(budget, timeout, minimum=0.1)
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        _check_manual_stop()
        prior = getattr(driver, "_otp_resend_receipt", None)
        if isinstance(prior, dict) and prior.get("clicked"):
            return _read_resend_receipt(driver, prior, timeout=max(0.1, end - time.monotonic()), budget=budget)
        try:
            btn = driver.execute_script(r"""
            const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
            const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
            const candidates = [...document.querySelectorAll('button,a,[role=button],[role=link],input[type=button],input[type=submit]')].filter(visible);
            const attrHit = candidates.find(el => {
              if (!enabled(el)) return false;
              const attrs = [el.id, el.getAttribute('name'), el.getAttribute('value'), el.getAttribute('data-dd-action-name'), el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-testid')]
                .join(' ').toLowerCase();
              const name = String(el.getAttribute('name') || '').toLowerCase();
              const value = String(el.getAttribute('value') || '').toLowerCase();
              if (name === 'intent' && value === 'resend') return true;
              return /resend|send.*new|new.*code|again/.test(attrs);
            });
            if (attrHit) return attrHit;
            // 兜底：多语言文本，避免因页面没有稳定属性时卡死。
            return candidates.find(el => enabled(el) && /resend|send\s+(?:a\s+)?new\s+code|send\s+again|重新发送|重新发送电子邮件|重发|再次发送|再送信|新しい|届かない/.test((el.innerText || el.textContent || '').toLowerCase())) || null;
            """)
            if btn:
                text = str(btn.text or btn.get_attribute('value') or btn.get_attribute('data-dd-action-name') or '').strip()
                # 以真正派发点击的时刻作为下一封邮件的时间边界。必须在 click
                # 前立即取值，既排除点击前旧码，也不会漏掉点击后瞬间到达的邮件。
                requested_after_ts = time.time()
                resend_receipt = {
                    "clicked": True, "text": text, "requested_after_ts": requested_after_ts,
                }
                driver._otp_resend_receipt = resend_receipt
                browser_receipt = BrowserSubmissionReceipt(
                    kind="resume_login" if getattr(driver, "_registration_resume_login", False) else "otp",
                    stage="otp_resend", endpoint_kind="otp_resend", http_method="POST",
                )
                driver._browser_submission_receipt = browser_receipt
                # 重发点击前先建立 durable dispatch 围栏；点击或读取结果未知时，
                # 下一 Run 只能核对原动作，不能再次点击。
                record_browser_submission_fact(driver, "prepared", receipt=browser_receipt)
                record_browser_submission_fact(driver, "dispatch_intent", receipt=browser_receipt)
                try:
                    _human_click(driver, btn, label="resend_otp")
                    record_browser_submission_fact(driver, "ui_dispatched", receipt=browser_receipt)
                except Exception as exc:
                    # click 结果不明时保存围栏，后续只读，不再点第二次。
                    record_browser_submission_fact(
                        driver, "unknown", receipt=browser_receipt, result="unknown",
                        error_type=type(exc).__name__,
                    )
                    raise RuntimeError("验证码重发点击结果未知，已禁止重复点击") from exc
                logger.info("%s[OTP] 已点击重新发送验证码按钮：%s", _log_prefix(driver), text or '-')
                delay = random.uniform(1.1, 2.4) if _browser_actions_enabled() else 1.5
                if budget is not None:
                    delay = min(delay, budget.remaining())
                if delay > 0:
                    time.sleep(delay)
                result = _read_resend_receipt(
                    driver, resend_receipt, timeout=max(0.1, timeout - delay), budget=budget,
                    initial_now=end - max(0.0, timeout - delay),
                )
                logger.info("%s[OTP] 重发请求页面确认：%s", _log_prefix(driver), result.get("ui_ack"))
                log_submission_diagnostics(driver, "otp", "resend_observed", receipt=browser_receipt)
                return result
        except Exception as exc:
            last = exc
        time.sleep(min(0.5, max(0.0, budget.remaining())) if budget is not None else 0.5)
    raise RuntimeError(f"找不到可点击的重新发送验证码按钮: last={last}, state={_email_otp_page_state(driver)}")

def _resend_email_otp_after_failure(driver, *, reason: str, budget: StageBudget | None = None) -> dict:
    """只在仍处于邮箱验证码页时调用现有的 OTP 重发逻辑。"""
    active_otp_page = _is_email_verification_page(driver)
    otp_state = _email_otp_page_state(driver)
    if not isinstance(otp_state, dict):
        otp_state = {}
    if not active_otp_page or not can_resend_otp(
        PageState.OTP_EMAIL,
        email_verified=bool(otp_state.get("emailVerified")),
    ):
        raise RuntimeError(
            f"{reason}，当前页面已离开邮箱验证码页，未执行 OTP 重发："
            f"url={getattr(driver, 'current_url', '')} state={otp_state}"
        )
    return _click_resend_email_otp(driver, timeout=25, budget=budget)

def _classify_otp_wait_failure(exc: Exception, *, last_ui_ack: str) -> tuple[str, str]:
    """Classify a no-code result without claiming that a DOM click sent mail."""
    text = str(exc or "")
    mailbox_markers = ("登录失败", "连接失败", "建连失败", "读取失败", "IMAP 兜底不可用")
    if any(marker in text for marker in mailbox_markers):
        return "otp_mailbox_unavailable", "验证码收件链路不可用"
    if str(last_ui_ack or "").strip().lower() != "confirmed":
        return "otp_request_unconfirmed", "验证码请求缺少页面或网络确认；不能断言服务端已经发信"
    return "otp_delivery_missing", "验证码请求已有页面确认，但预算内未收到匹配邮件"

def _complete_registration_totp_after_email_otp(
    driver,
    email: str,
    existing_password: str | None,
    existing_totp_secret: str | None,
    *,
    timeout: int = 45,
    budget: StageBudget | None = None,
    challenge_resolver=None,
) -> str:
    """Finish an existing-account login when email OTP is followed by TOTP."""
    if not existing_password or not existing_totp_secret:
        raise RuntimeError(
            "邮箱验证码已通过，但远端继续要求 Authenticator TOTP；本地缺少可用密码或 TOTP，已停止"
        )
    context = current_execution_context()
    resolver = (
        challenge_resolver
        or getattr(context, "challenge_resolver", None)
        or current_override("complete_openai_login_challenge")
    )
    if not callable(resolver):
        raise RuntimeError("邮箱验证码后需要 TOTP，但未注入登录 challenge resolver")
    if budget is not None:
        timeout = _budget_timeout(budget, timeout)
        child = budget.child(timeout)
        context = replace(context, budget=child) if context is not None else AuthExecutionContext(budget=child)
    with execution_context(context):
        state = resolver(
            driver,
            email,
            existing_password,
            str(existing_totp_secret),
            timeout=timeout,
        )
    if state != "advanced":
        raise RuntimeError(f"邮箱验证码后 TOTP 登录链未完成：state={state}")
    return state

def _wait_after_email_otp_submit(
    driver,
    timeout: int = 60,
    *,
    budget: StageBudget | None = None,
    baseline_state: dict | None = None,
    expected_email: str | None = None,
) -> str:
    """提交 OTP 后等待明确的资料页、邮箱已验证提示或登录态。

    只有页面明确出现验证码错误（aria-invalid / 错误文案）才判定为无效；
    网络慢时最多等待完整 timeout；超时没有明确成功证据时按 stuck 保留
    原提交，不把空壳、未知跳转或无错误标记当成验证成功，也不自动重发。
    """
    timeout = _budget_timeout(budget, timeout, minimum=0.0)
    end = time.monotonic() + max(0.0, timeout)
    confirmation_budget = StageBudget(end, clock=time.monotonic, cancellation=budget.cancellation if budget is not None else None)
    last = {}
    diagnostic_logged = False
    diagnostic_at = min(30.0, max(0.0, timeout))
    started = time.monotonic()
    baseline_state = baseline_state if isinstance(baseline_state, dict) else {}
    baseline_errors = tuple(str(item) for item in (baseline_state.get("errors") or []))
    baseline_invalid = tuple(
        str(item.get("id") or item.get("name") or index)
        for index, item in enumerate(baseline_state.get("inputs") or [])
        if isinstance(item, dict) and str(item.get("ariaInvalid") or "").lower() == "true"
    )
    receipt = getattr(driver, "_browser_submission_receipt", None)
    if not isinstance(receipt, BrowserSubmissionReceipt) or receipt.endpoint_kind != "otp_submit":
        receipt = None
    recovery_id = receipt.submission_id if receipt is not None else "without_receipt"
    recovery_attempted = getattr(driver, "_email_otp_submission_recovery_id", None) == recovery_id
    recovery_at = started + max(5.0, timeout - RECOVERY_WINDOW_SECONDS)
    next_diagnostic_at = started + 15.0
    session_probe_started = False
    session_probe_failed = False
    recovery_session_probes = 0
    log_submission_diagnostics(driver, "otp", "submitted", receipt=receipt)

    def authenticated_home(read_budget, *, recovery=False):
        nonlocal session_probe_started, session_probe_failed, recovery_session_probes
        if not expected_email:
            return _has_access_token(driver, budget=read_budget)
        current = urlsplit(str(getattr(driver, "current_url", "") or ""))
        if (current.scheme != "https" or current.hostname != "chatgpt.com" or current.port not in (None, 443)
                or current.username or current.password or current.path.startswith(("/api/", "/auth/", "/login"))):
            return False
        if recovery:
            if recovery_session_probes >= 2:
                return False
            recovery_session_probes += 1
        elif session_probe_started:
            return False
        session_probe_started = True
        remaining = read_budget.remaining(5 if recovery else 30)
        if remaining <= 0:
            return False
        try:
            _read_profile_session_once(driver, timeout=remaining, expected_email=expected_email)
            return True
        except RuntimeError as exc:
            if not any(marker in str(exc) for marker in ("profile_session_read_failed", "profile_session_unconfirmed")):
                raise
            session_probe_failed = True
            log_submission_diagnostics(driver, "otp", "session_read_failed", receipt=receipt)
            return False

    def _new_error_mark(state: dict) -> bool:
        errors = tuple(str(item) for item in (state.get("errors") or []))
        invalid = tuple(
            str(item.get("id") or item.get("name") or index)
            for index, item in enumerate(state.get("inputs") or [])
            if isinstance(item, dict) and str(item.get("ariaInvalid") or "").lower() == "true"
        )
        return bool(set(errors) - set(baseline_errors) or set(invalid) - set(baseline_invalid))

    def observe_recovery(recovery_budget):
        state = _email_otp_page_state(driver)
        state = state if isinstance(state, dict) else {}
        page_state = classify_page(state)
        if page_state == PageState.LOGGED_OUT:
            return "session_expired"
        if page_state == PageState.AUTH_ERROR:
            return None
        if state.get("emailVerified"):
            return "email_verified"
        if has_visible_auth_inputs(state, allow_password=False):
            if page_state == PageState.MFA_TOTP:
                return "totp_required"
            if page_state == PageState.PROFILE:
                return "accepted"
        if authenticated_home(recovery_budget, recovery=True):
            return "accepted"
        if auth_session_unavailable(driver):
            return "session_expired"
        if _email_otp_form_is_ready(state) and _new_error_mark(state) and not _email_otp_page_recovery_reason(state):
            return "invalid"
        return None

    def recover_once():
        nonlocal recovery_attempted
        if recovery_attempted:
            return None
        recovery_attempted = True
        driver._email_otp_submission_recovery_id = recovery_id
        # 收码前的空壳恢复与这次提交的恢复分别计数；不重新填码或点击。
        return recover_submission_page(driver, "otp", observe_recovery, budget=confirmation_budget,
                                       receipt=receipt, sleeper=time.sleep)

    while True:
        _check_manual_stop()
        confirmation_budget.check_cancelled()
        now = time.monotonic()
        if now >= end:
            break
        if not diagnostic_logged and now - started >= diagnostic_at:
            diagnostic_logged = True
            logger.info("%s[OTP] 提交后 30 秒诊断检查点：仍等待原提交确认，不重发验证码", _log_prefix(driver))
        if now >= next_diagnostic_at:
            log_submission_diagnostics(driver, "otp", "waiting", receipt=receipt)
            next_diagnostic_at = time.monotonic() + 15.0
        time.sleep(min(0.5, max(0.0, end - now)))
        last = _email_otp_page_state(driver)
        if not isinstance(last, dict):
            last = {}
        page_state = classify_page(last)
        if page_state == PageState.MFA_TOTP:
            logger.info("%s[OTP] 邮箱验证码后进入 Authenticator TOTP，交给公共登录状态机", _log_prefix(driver))
            return "totp_required"
        if last.get("emailVerified"):
            return "email_verified"
        if (page_state == PageState.PROFILE and (not recovery_attempted or has_visible_auth_inputs(last, allow_password=False))
                or authenticated_home(confirmation_budget)):
            return 'accepted'
        if page_state == PageState.LOGGED_OUT or auth_session_unavailable(driver):
            log_submission_diagnostics(driver, "otp", "auth_session_unavailable", receipt=receipt)
            return "session_expired"
        if not _email_otp_page_recovery_reason(last) and _is_email_verification_page(driver) and _new_error_mark(last):
            return 'invalid'
        reason = _email_otp_page_recovery_reason(last)
        if reason == "blank_shell":
            seen_at = getattr(driver, "_email_otp_blank_seen_at", None)
            if seen_at is None:
                driver._email_otp_blank_seen_at = time.monotonic()
            if seen_at is None or time.monotonic() - seen_at < 3.0:
                reason = ""
        else:
            driver._email_otp_blank_seen_at = None
        if not recovery_attempted and (reason or session_probe_failed or page_state in {PageState.AUTH_ERROR, PageState.LOGGED_OUT}
                                       or time.monotonic() >= recovery_at):
            recovered = recover_once()
            if recovered:
                return recovered
        if page_state in {PageState.AUTH_ERROR, PageState.LOGGED_OUT}:
            return 'stuck'
    log_submission_diagnostics(driver, "otp", "timeout", receipt=receipt)
    if _is_email_verification_page(driver):
        # 超时仍停留：有错误标记是 invalid；没有错误标记也说明提交没有产生跳转，
        # 返回 stuck，让上层保留原提交并等待同一 Attempt 恢复。
        last = _email_otp_page_state(driver)
        has_error_mark = _new_error_mark(last)
        if has_error_mark and not _email_otp_page_recovery_reason(last):
            logger.warning("%s[OTP] 提交后仍停留验证码页且存在错误标记，按验证码无效处理 snapshot=%s", _log_prefix(driver), last)
            return 'invalid'
        logger.warning(
            "%s[OTP] 提交后 %ss 仍在验证码页但无错误标记，原提交结果未知，保留恢复上下文 snapshot=%s",
            _log_prefix(driver), timeout, last
        )
        return 'stuck'
    if isinstance(last, dict) and last.get("emailVerified"):
        return "email_verified"
    # 页面离开验证码路由不代表验证成功；空壳或未知跳转保持原提交待确认。
    return 'stuck'


install_dispatches(globals(), (
    "human_delay", "wait_for_otp", "resolve_email_source",
    "_email_entry_state", "_find_visible_email_input_js", "_is_oauth_consent_like",
    "_is_external_idp_url", "_assert_not_external_idp", "_click_email_entry_option",
    "_is_blank_chatgpt_auth_shell", "_reload_blank_chatgpt_auth_shell",
    "_email_submit_advanced_state", "_type_email_address",
    "_submit_nearest_form_for_active_input", "_current_email_input_value",
    "_stabilize_email_input_before_submit", "_submit_email_form_stable",
    "_submit_email_step", "_recover_email_submit_if_stuck",
    "_submit_email_via_browser_nextauth", "_email_input_value_state",
    "_is_email_login_page_still_present", "_diagnostic_url", "_redact_diagnostic_text",
    "_log_blank_auth_shell_diagnostics", "_wait_email_submit_next_state",
    "_submit_email_and_wait_next", "_type_otp", "_email_otp_page_state",
    "_email_otp_page_recovery_reason", "_recover_email_otp_page_if_needed", "_wait_email_otp_page_ready",
    "_is_email_verification_page", "_clear_otp_inputs", "_click_resend_email_otp",
    "_resend_email_otp_after_failure", "_classify_otp_wait_failure",
    "_complete_registration_totp_after_email_otp", "_wait_after_email_otp_submit",
))

__all__ = [
    "_EMAIL_INPUT_SELECTORS", "EMAIL_PREPARATION_TIMEOUT", "EMAIL_SUBMISSION_TIMEOUT", "EMAIL_OUTER_TIMEOUT",
    "human_delay", "wait_for_otp", "resolve_email_source",
    "_email_entry_state", "_find_visible_email_input_js", "_is_oauth_consent_like",
    "_is_external_idp_url", "_assert_not_external_idp", "_click_email_entry_option",
    "_is_blank_chatgpt_auth_shell", "_reload_blank_chatgpt_auth_shell",
    "_email_submit_advanced_state", "_type_email_address",
    "_submit_nearest_form_for_active_input", "_current_email_input_value",
    "_stabilize_email_input_before_submit", "_submit_email_form_stable",
    "_submit_email_step", "_recover_email_submit_if_stuck",
    "_submit_email_via_browser_nextauth", "_email_input_value_state",
    "_is_email_login_page_still_present", "_diagnostic_url", "_redact_diagnostic_text",
    "_log_blank_auth_shell_diagnostics", "_wait_email_submit_next_state",
    "_submit_email_and_wait_next", "_type_otp", "_email_otp_page_state",
    "_email_otp_page_recovery_reason", "_recover_email_otp_page_if_needed", "_wait_email_otp_page_ready",
    "_is_email_verification_page", "_clear_otp_inputs", "_click_resend_email_otp",
    "_resend_email_otp_after_failure", "_classify_otp_wait_failure",
    "_complete_registration_totp_after_email_otp", "_wait_after_email_otp_submit",
]
