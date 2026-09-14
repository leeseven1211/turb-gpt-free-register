"""Email-entry and OTP browser capabilities shared by auth flows."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import time
import uuid
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from core.auth_challenge import RemoteExistingAccountError
from core.email_provider import resolve_email_source as _resolve_email_source, wait_for_otp as _wait_for_otp
from core.humanize import delay as _human_delay
from core.registration.state_machine import PageState, StageBudget, StageTimeout, can_resend_otp, classify_page

from .auth_context import (
    checkpoint as _checkpoint,
    current_execution_context,
    current_override,
    install_dispatches,
    time_proxy,
)
from .selenium_dom import (
    _auth_terminal_page_state, _budget_timeout, _check_manual_stop, _click_any,
    _click_continue, _find_any, _human_click,
    _human_scroll_to, _human_type_text, _is_login_password_page, _is_signup_password_page,
    _log_prefix, _maybe_accept, _page_snapshot, _safe_get, _type_any,
    _visible, _page_warmup,
)
from .selenium_resource import _browser_actions_enabled
from .session_auth import _has_access_token

human_delay = _human_delay
wait_for_otp = _wait_for_otp
resolve_email_source = _resolve_email_source
logger = logging.getLogger(__name__)
time = time_proxy

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

def _email_submit_advanced_state(driver) -> str | None:
    """识别邮箱提交后已经到达的稳定下一步，避免按过期页面状态继续重试。"""
    if _has_access_token(driver):
        return "logged_in"
    if _is_login_password_page(driver):
        return "login_password"
    if _is_email_verification_page(driver):
        return "otp"
    if _is_signup_password_page(driver):
        return "password"
    return None

def _type_email_address(
    driver,
    email: str,
    timeout: int | None = None,
    *,
    stop_on_advanced: bool = False,
) -> str | None:
    """进入邮箱登录/注册方式并填写邮箱。全程不依赖页面可见文字，避免非日本出口本地化后误点 Google。"""
    end = time.time() + (timeout or int(_cfg.ROXY_SELENIUM_TIMEOUT))
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
    result = driver.execute_script(r"""
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
    target.scrollIntoView({block:'center'});
    window.__roxy_email_submit_debug = {at: Date.now(), targetAttrs: safe[0].attrs.slice(0,240), buttonCount: rawButtons.length, primary:safe[0].isPrimarySubmit};
    return {ok:true, reason:safe[0].isPrimarySubmit ? 'primary_submit' : 'safe_submit', target, targetAttrs:safe[0].attrs.slice(0,160), primary:safe[0].isPrimarySubmit};
    """) or {}
    if result.get("ok"):
        target = result.get("target")
        if target:
            _human_click(driver, target, label="email_submit")
        else:
            logger.warning("%s 邮箱提交未返回目标元素，回退 requestSubmit", _log_prefix(driver))
            driver.execute_script("document.querySelector('form')?.requestSubmit?.();")
        logger.info("%s 邮箱表单安全提交：%s", _log_prefix(driver), result)
        time.sleep(0.8)
        _assert_not_external_idp(driver, "提交邮箱后")
        return True
    logger.warning("%s 未执行邮箱提交：%s", _log_prefix(driver), result)
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

def _submit_email_form_stable(driver, email: str) -> dict:
    """第一次提交就按“补交成功”的方式执行：稳定 value 后 Enter + DOM click。"""
    try:
        return driver.execute_script(r"""
        const email = String(arguments[0] || '').trim();
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
        setTimeout(() => {
          try {
            input.focus();
            input.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, cancelable:true, key:'Enter', code:'Enter'}));
            input.dispatchEvent(new KeyboardEvent('keypress', {bubbles:true, cancelable:true, key:'Enter', code:'Enter'}));
            input.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, cancelable:true, key:'Enter', code:'Enter'}));
            if (submit && !submit.disabled) submit.click();
            else if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
          } catch (_) {}
        }, 80);

        window.__roxy_email_submit_debug = {
          at: Date.now(),
          mode: 'stable_async_enter_click',
          value: input.value,
          submitAttrs: attrText(submit).slice(0, 240)
        };
        return {
          ok:true,
          reason:'stable_async_enter_click',
          value: input.value,
          submitDisabled: !!submit.disabled || String(submit.getAttribute('aria-disabled') || '').toLowerCase() === 'true',
          submitAttrs: attrText(submit).slice(0, 180),
          url: location.href
        };
        """, email) or {}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

def _submit_email_step(driver, email: str | None = None) -> None:
    # 不再优先走浏览器内 NextAuth fetch：
    # Roxy/Chrome 150 下 execute_async_script + fetch 偶发卡到 script timeout；
    # 实测 UI 首次提交后若停在 /auth/login?email=...，由 _recover_email_submit_if_stuck 补交表单更稳定。
    email_value = str(email or _current_email_input_value(driver) or "").strip()
    stable = _stabilize_email_input_before_submit(driver, email_value)
    logger.info("%s 邮箱提交前状态稳定：%s", _log_prefix(driver), stable)
    time.sleep(random.uniform(0.8, 1.8) if _browser_actions_enabled() else 0.4)

    stable_submit = _submit_email_form_stable(driver, email_value)
    if stable_submit.get("ok"):
        logger.info("%s 邮箱稳定表单提交：%s", _log_prefix(driver), stable_submit)
        time.sleep(1.0)
        _assert_not_external_idp(driver, "稳定表单提交邮箱后")
        return
    logger.warning("%s 邮箱稳定表单提交失败，回退 UI 点击提交：%s", _log_prefix(driver), stable_submit)
    if _submit_nearest_form_for_active_input(driver):
        return
    raise RuntimeError(f"无法提交邮箱步骤（拒绝按页面文字或首个 submit 兜底，避免误点第三方登录），state={_email_entry_state(driver)}")

def _recover_email_submit_if_stuck(driver, email: str) -> dict:
    """邮箱提交后停在 /auth/login?email= 且输入框被清空时，补一次原生表单提交。"""
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
        input.focus();
        if (setter) setter.call(input, email); else input.value = email;
        input.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:email}));
        input.dispatchEvent(new Event('change', {bubbles:true}));
        const form = input.closest('form');
        const submit = form?.querySelector('button[type="submit"],input[type="submit"]');
        setTimeout(() => {
          try {
            input.dispatchEvent(new KeyboardEvent('keydown', {bubbles:true, cancelable:true, key:'Enter', code:'Enter'}));
            input.dispatchEvent(new KeyboardEvent('keyup', {bubbles:true, cancelable:true, key:'Enter', code:'Enter'}));
            if (submit && !submit.disabled) submit.click();
            else if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
          } catch (_) {}
        }, 80);
        return {ok:true, reason:'resubmitted_email_form', value: input.value, hasForm: !!form, hasSubmit: !!submit};
        """, email) or {}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

def _submit_email_via_browser_nextauth(driver, email: str) -> dict:
    """在 Roxy 浏览器上下文里调用 ChatGPT NextAuth signin。

    UI submit 在 Roxy/Chrome 150 上会偶发只跳到 `/auth/login?email=...` 后停住。
    这里改走浏览器页面内 fetch，仍使用当前 Roxy 浏览器的 cookie / 指纹环境，
    拿到 auth.openai.com authorize URL 后让浏览器跳转。
    """
    advanced_state = _email_submit_advanced_state(driver)
    if advanced_state:
        return {
            "ok": True,
            "stage": "already_advanced",
            "state": advanced_state,
            "url": _diagnostic_url(getattr(driver, "current_url", "")),
        }
    try:
        current = str(getattr(driver, "current_url", "") or "")
        if "chatgpt.com" not in current:
            return {"ok": False, "reason": "not_on_chatgpt", "url": _diagnostic_url(current)}
    except Exception:
        current = ""

    did = str(uuid.uuid4())
    auth_log_id = str(uuid.uuid4())
    old_script_timeout = int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)
    try:
        try:
            driver.set_script_timeout(25)
        except Exception:
            pass
        result = driver.execute_async_script(r"""
        const email = String(arguments[0] || '').trim();
        const did = String(arguments[1] || '');
        const authLogId = String(arguments[2] || '');
        const done = arguments[arguments.length - 1];
        (async () => {
          try {
            const csrfResp = await fetch('/api/auth/csrf', {
              method: 'GET',
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
              done({ok:false, stage:'csrf', status:csrfResp.status, body:csrfText.slice(0, 500)});
              return;
            }

            const q = new URLSearchParams({
              prompt: 'login',
              'ext-oai-did': did,
              auth_session_logging_id: authLogId,
              'ext-passkey-client-capabilities': '11111',
              screen_hint: 'login_or_signup',
              login_hint: email
            });
            const body = new URLSearchParams({
              callbackUrl: 'https://chatgpt.com/',
              csrfToken,
              json: 'true'
            });
            const resp = await fetch('/api/auth/signin/openai?' + q.toString(), {
              method: 'POST',
              credentials: 'include',
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
              done({ok:false, stage:'signin', status:resp.status, body:text.slice(0, 700)});
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
            done({ok:false, stage:'exception', error:String(e && (e.stack || e.message) || e).slice(0, 700)});
          }
        })();
        """, email, did, auth_log_id) or {}
        if not isinstance(result, dict):
            return {"ok": False, "reason": "invalid_result", "result": str(result)[:300]}
        if not result.get("ok"):
            return result

        target_url = str(result.get("url") or "").strip()
        try:
            parsed = urlsplit(target_url)
        except Exception:
            parsed = None
        if not parsed or parsed.scheme != "https" or parsed.hostname not in ("auth.openai.com", "chatgpt.com"):
            return {"ok": False, "reason": "unsafe_redirect_url", "url": _diagnostic_url(target_url)}

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
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
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
) -> str:
    """邮箱提交后等待进入 password / otp / logged_in；仍停留邮箱页则返回 email_page。

    ``wait_through_transient`` 用于 NextAuth 已发起导航后的最终落点确认：此时登录空壳
    和被清空的邮箱框都只视为过渡态，持续等到明确下一步或整体超时。

    Cloak/Playwright 路径里，点击 submit 后页面经常先发生一次 SPA 导航：
    `chatgpt.com/auth/login?email=...`，同时 React 会短暂把 email input 清空。
    旧逻辑一看到空 input 就立刻返回 `email_cleared`，导致在真正跳到
    `auth.openai.com/...` 前过早重填，形成“提交 -> 清空 -> 重填”的循环。
    这里对 email_cleared 做去抖：只记录并继续观察几秒；若期间进入
    password/otp/login_password/logged_in 则按真实状态返回，持续清空才让上层重试。
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
    transient_shell_logged = False
    expected_email = str(email or "").strip().lower()
    while True:
        _check_manual_stop()
        loop_now = clock()
        if loop_now >= end:
            break
        advanced_state = _email_submit_advanced_state(driver)
        if advanced_state:
            return advanced_state
        state = _email_input_value_state(driver)
        last = state
        inputs = state.get("inputs") or []
        if not inputs and _is_blank_chatgpt_auth_shell(driver):
            if not wait_through_transient:
                logger.warning("%s 邮箱提交后进入 ChatGPT 登录空壳页，立即切换认证兜底", _log_prefix(driver))
                return "blank_shell"
            if not transient_shell_logged:
                logger.info("%s 认证兜底后仍在登录过渡页，继续等待最终跳转", _log_prefix(driver))
                transient_shell_logged = True
        if inputs:
            values = [str(i.get("value") or "") for i in inputs]
            url = str(state.get("url") or "")
            has_blank = any(v == "" for v in values)
            has_expected = any(v.strip().lower() == expected_email for v in values)
            if has_blank and not has_expected:
                now = clock()
                if cleared_seen_at is None:
                    cleared_seen_at = now
                # URL 已带 email 查询参数时更像是提交后的中间态，给它更长观察窗口。
                debounce = 18.0 if ("/auth/login" in url and "email=" in url) else 5.0
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
    logger.info("%s 邮箱提交后等待下一步超时，最后邮箱页状态=%s", _log_prefix(driver), last)
    return "email_page" if _is_email_login_page_still_present(driver) else "unknown"

def _submit_email_and_wait_next(
    driver,
    email: str,
    attempts: int = 3,
    on_submitted=None,
    total_timeout: int = 60,
    allow_login_password: bool = False,
) -> str:
    """填写并提交邮箱，必须确认进入下一步；整个跳转链路最多占用 total_timeout 秒。"""
    last_state = None
    nextauth_fallback_done = False
    submitted_reported = False
    budget = StageBudget.start(max(10, int(total_timeout or 60)))
    # Keep the helper's historical call signature stable for integrations that
    # patch it, while still sharing the active budget with the real helper.
    try:
        setattr(driver, "_registration_stage_budget", budget)
    except Exception:
        pass

    def _remaining(limit: int) -> int:
        return max(1, min(int(limit), int(math.ceil(budget.remaining()))))

    def _accept_advanced_state(state_name: str | None, source: str) -> str | None:
        if state_name == "login_password":
            if allow_login_password:
                logger.info(
                    "%s %s已进入登录密码页；这是待验证账号恢复任务，继续使用已保存密码",
                    _log_prefix(driver),
                    source,
                )
                return state_name
            raise RemoteExistingAccountError(
                f"邮箱提交后进入登录密码页，已注册/不可用邮箱；检测到远端已有账号，进入人工协调: "
                f"url={getattr(driver, 'current_url', '') or 'https://auth.openai.com/log-in/password'}"
            )
        if state_name in ("password", "otp", "logged_in"):
            logger.info("%s %s已进入下一步：%s", _log_prefix(driver), source, state_name)
            return state_name
        return None

    for attempt in range(1, attempts + 1):
        _check_manual_stop()
        if budget.expired():
            break
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
            logger.warning("%s 邮箱写入校验失败，准备重试：attempt=%s/%s state=%s", _log_prefix(driver), attempt, attempts, state)
            time.sleep(0.8)
            continue
        logger.info("%s 已填写邮箱并校验通过：%s", _log_prefix(driver), email)
        human_delay("form")
        _submit_email_step(driver, email)
        # Selenium click/submit may itself block until the browser finishes a slow
        # navigation.  Once the form has been dispatched, waiting for the remote
        # auth result is a new request and must receive a fresh budget.  Otherwise
        # the first state check can fail immediately even though the page is still
        # legitimately transitioning (observed with a 91-second proxy response).
        budget = StageBudget.start(max(10, int(total_timeout or 60)))
        try:
            setattr(driver, "_registration_stage_budget", budget)
        except Exception:
            pass
        if not submitted_reported and on_submitted is not None:
            try:
                on_submitted()
            except Exception:
                logger.exception("%s 上报邮箱提交阶段失败", _log_prefix(driver))
            submitted_reported = True
        logger.info("%s 已提交邮箱，等待进入密码页或验证码页（%s/%s）", _log_prefix(driver), attempt, attempts)
        state_name = _wait_email_submit_next_state(driver, email, timeout=_remaining(20))
        accepted = _accept_advanced_state(state_name, "邮箱提交后")
        if accepted:
            return accepted
        retry_state_name = state_name
        if state_name == "blank_shell":
            _log_blank_auth_shell_diagnostics(driver, last_state)
            logger.info("%s 首次确认登录空壳，立即切换 NextAuth 导航兜底", _log_prefix(driver))
        if state_name in ("email_page", "email_cleared", "unknown", "blank_shell") and not nextauth_fallback_done:
            nextauth_fallback_done = True
            logger.warning("%s UI 提交邮箱后未跳转，启用一次 NextAuth 导航兜底", _log_prefix(driver))
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
                if fallback_state in ("blank_shell", "unknown") and _is_blank_chatgpt_auth_shell(driver):
                    _reload_blank_chatgpt_auth_shell(driver)
            elif state_name == "blank_shell" and _is_blank_chatgpt_auth_shell(driver):
                # NextAuth 自身也失败时才刷新页面，保留一次 UI 重试机会。
                _reload_blank_chatgpt_auth_shell(driver)
        late_state = _email_submit_advanced_state(driver)
        accepted = _accept_advanced_state(late_state, "重试前页面")
        if accepted:
            return accepted
        current_state = _email_input_value_state(driver)
        last_state = current_state
        logger.warning("%s 邮箱提交后仍未进入下一步：%s，准备重填重试 state=%s", _log_prefix(driver), retry_state_name, current_state)
        time.sleep(min(1.0, max(0.0, budget.remaining())))
    if budget.expired():
        raise RuntimeError(f"邮箱提交/认证跳转超过总预算 {int(total_timeout or 60)} 秒，最后状态={last_state}")
    raise RuntimeError(f"邮箱提交后未进入密码页/验证码页，最后状态={last_state}")

def _type_otp(driver, code: str, *, timeout: int = 20) -> None:
    from selenium.webdriver.common.by import By

    # 邮件通常比认证页渲染更快。收到验证码后继续等输入框出现，避免把页面竞态
    # 误判成注册失败；同时保留硬超时，防止页面真的卡死。
    deadline = time.monotonic() + max(1, int(timeout or 20))
    while time.monotonic() < deadline:
        _check_manual_stop()
        # 单输入框
        for selector in [
            "input[autocomplete='one-time-code']",
            "input[name='code']",
            "input[inputmode='numeric']",
            "input[type='tel']",
        ]:
            els = [e for e in driver.find_elements(By.CSS_SELECTOR, selector) if _visible(e)]
            if len(els) == 1:
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
            for e, ch in zip(numeric_boxes, code):
                if _browser_actions_enabled():
                    _human_scroll_to(driver, e)
                    time.sleep(random.uniform(0.04, 0.18))
                e.send_keys(ch)
                if _browser_actions_enabled():
                    human_delay("keystroke")
            return
        time.sleep(0.35)

    raise RuntimeError(
        f"等待 OTP 输入框超时（{int(timeout or 20)} 秒），当前页面={str(getattr(driver, 'current_url', '') or '')[:180]}"
    )

def _email_otp_page_state(driver) -> dict:
    try:
        return driver.execute_script(r"""
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
        return {url: location.href, title: document.title, inputs, buttons, errors, text: bodyText.slice(0, 1200), emailVerified};
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, 'current_url', ''), "error": f"{type(exc).__name__}: {exc}"}

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
        return True
    attrs = ' '.join(' '.join(str(i.get(k) or '') for k in ('type','name','id','autocomplete','inputmode')) for i in (state.get('inputs') or [])).lower()
    return 'one-time-code' in attrs or 'otp' in attrs or 'code' in attrs

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

def _click_resend_email_otp(driver, timeout: int = 20, *, budget: StageBudget | None = None) -> dict:
    """点击重新发送邮箱验证码。优先按 DOM 属性识别，文本仅兜底。"""
    timeout = _budget_timeout(budget, timeout, minimum=0.1)
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        _check_manual_stop()
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
                _human_click(driver, btn, label="resend_otp")
                logger.info("%s[OTP] 已点击重新发送验证码按钮：%s", _log_prefix(driver), text or '-')
                delay = random.uniform(1.1, 2.4) if _browser_actions_enabled() else 1.5
                if budget is not None:
                    delay = min(delay, budget.remaining())
                if delay > 0:
                    time.sleep(delay)
                state_after = _email_otp_page_state(driver)
                buttons_after = state_after.get("buttons") if isinstance(state_after, dict) else []
                if not isinstance(buttons_after, list):
                    buttons_after = []
                resend_pattern = re.compile(r"resend|send.*new|send.*again|重新发送|重发|再次发送|再送信|届かない", re.I)
                matching = [
                    item for item in buttons_after
                    if resend_pattern.search(" ".join(str(item.get(key) or "") for key in ("text", "action", "aria", "value")))
                ]
                ui_ack = "confirmed" if (
                    not _is_email_verification_page(driver)
                    or any(bool(item.get("disabled")) for item in matching)
                ) else "unconfirmed"
                logger.info("%s[OTP] 重发请求页面确认：%s", _log_prefix(driver), ui_ack)
                return {"ok": True, "text": text, "ui_ack": ui_ack}
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
    timeout: int = 30,
    *,
    budget: StageBudget | None = None,
) -> str:
    """提交 OTP 后等待页面离开验证码页。

    只有页面明确出现验证码错误（aria-invalid / 错误文案）才判定为无效；
    网络慢时最多等待完整 timeout；超时后仍停在验证码页，即使页面没有显式
    aria-invalid，也必须按 stuck 处理并重新取码。旧逻辑把这种状态当 accepted，
    后续资料页会再白等 60 秒才失败。
    """
    timeout = _budget_timeout(budget, timeout, minimum=0.0)
    end = time.monotonic() + max(0.0, timeout)
    last = {}
    while time.monotonic() < end:
        _check_manual_stop()
        time.sleep(min(0.5, max(0.0, end - time.monotonic())))
        last = _email_otp_page_state(driver)
        if not isinstance(last, dict):
            last = {}
        if classify_page(last) == PageState.MFA_TOTP:
            logger.info("%s[OTP] 邮箱验证码后进入 Authenticator TOTP，交给公共登录状态机", _log_prefix(driver))
            return "totp_required"
        if last.get("emailVerified"):
            return "email_verified"
        if not _is_email_verification_page(driver):
            return 'accepted'
        invalid = any(str(i.get('ariaInvalid') or '').lower() == 'true' for i in (last.get('inputs') or []))
        if invalid or (last.get('errors') or []):
            return 'invalid'
    if _is_email_verification_page(driver):
        # 超时仍停留：有错误标记是 invalid；没有错误标记也说明提交没有产生跳转，
        # 返回 stuck 让上层重发/重新取最新验证码。
        last = _email_otp_page_state(driver)
        has_error_mark = bool(last.get('errors')) or any(
            str(i.get('ariaInvalid') or '').lower() == 'true' for i in (last.get('inputs') or [])
        )
        if has_error_mark:
            logger.warning("%s[OTP] 提交后仍停留验证码页且存在错误标记，按验证码无效处理 snapshot=%s", _log_prefix(driver), last)
            return 'invalid'
        logger.warning(
            "%s[OTP] 提交后 %ss 仍在验证码页但无错误标记，按页面卡住处理并重新取码 snapshot=%s",
            _log_prefix(driver), timeout, last
        )
        return 'stuck'
    if isinstance(last, dict) and last.get("emailVerified"):
        return "email_verified"
    return 'accepted'


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
    "_is_email_verification_page", "_clear_otp_inputs", "_click_resend_email_otp",
    "_resend_email_otp_after_failure", "_classify_otp_wait_failure",
    "_complete_registration_totp_after_email_otp", "_wait_after_email_otp_submit",
))

__all__ = [
    "_EMAIL_INPUT_SELECTORS", "human_delay", "wait_for_otp", "resolve_email_source",
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
    "_is_email_verification_page", "_clear_otp_inputs", "_click_resend_email_otp",
    "_resend_email_otp_after_failure", "_classify_otp_wait_failure",
    "_complete_registration_totp_after_email_otp", "_wait_after_email_otp_submit",
]
