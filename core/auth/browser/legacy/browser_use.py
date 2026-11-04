"""保留旧 Codex 浏览器认证依赖的页面能力，不包含注册编排。"""
from __future__ import annotations

import logging
import time

from config import browser_use as _cfg

logger = logging.getLogger(__name__)

def _fast_mode() -> bool:
    return bool(getattr(_cfg, "BROWSER_USE_FAST_MODE", True))


def _timeout_ms(seconds: int | None = None) -> int:
    value = int(seconds or getattr(_cfg, "BROWSER_USE_TIMEOUT", 90) or 90)
    return max(5, value) * 1000


def _page_url(page) -> str:
    try:
        return str(page.url or "")
    except Exception:
        return ""


def _visible_locator(page, selectors: list[str], timeout_ms: int = 1500):
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            if loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def _fill_first(page, selectors: list[str], value: str, timeout_ms: int | None = None) -> bool:
    end = time.time() + ((timeout_ms or _timeout_ms()) / 1000)
    last_err = None
    while time.time() < end:
        loc = _visible_locator(page, selectors, timeout_ms=800)
        if loc is not None:
            try:
                loc.scroll_into_view_if_needed(timeout=2000)
                loc.click(timeout=2000)
                loc.fill(value, timeout=5000)
                return True
            except Exception as exc:
                last_err = exc
                # React 受控输入兜底
                try:
                    loc.evaluate(
                        """(el, value) => {
                          const proto = el.tagName === 'TEXTAREA'
                            ? window.HTMLTextAreaElement.prototype
                            : window.HTMLInputElement.prototype;
                          const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                          if (setter) setter.call(el, value); else el.value = value;
                          el.dispatchEvent(new Event('input', {bubbles:true}));
                          el.dispatchEvent(new Event('change', {bubbles:true}));
                        }""",
                        value,
                    )
                    return True
                except Exception as exc2:
                    last_err = exc2
        time.sleep(0.15 if _fast_mode() else 0.3)
    if last_err:
        logger.debug("[BrowserUse] fill failed: %s", last_err)
    return False


def _click_first(page, selectors: list[str], timeout_ms: int | None = None) -> bool:
    end = time.time() + ((timeout_ms or _timeout_ms()) / 1000)
    while time.time() < end:
        loc = _visible_locator(page, selectors, timeout_ms=800)
        if loc is not None:
            try:
                loc.scroll_into_view_if_needed(timeout=2000)
                loc.click(timeout=3000)
                return True
            except Exception:
                try:
                    loc.evaluate("el => el.click()")
                    return True
                except Exception:
                    pass
        time.sleep(0.15 if _fast_mode() else 0.3)
    return False


def _maybe_accept_cookies(page) -> None:
    _click_first(
        page,
        [
            "button:has-text('Accept')",
            "button:has-text('Accept all')",
            "button:has-text('同意')",
            "button:has-text('接受')",
            "button:has-text('I agree')",
        ],
        timeout_ms=2500,
    )


def _quick_auth_state(page) -> dict:
    """一次 JS 查询判断当前 auth 页面状态，避免多组 locator 逐个等待导致几十秒卡顿。"""
    try:
        return page.evaluate(
            """() => {
              const url = String(location.href || '').toLowerCase();
              const visible = (el) => {
                if (!el) return false;
                const st = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return st && st.visibility !== 'hidden' && st.display !== 'none' && r.width > 0 && r.height > 0;
              };
              const q = (s) => !!document.querySelector(s);
              const qv = (s) => Array.from(document.querySelectorAll(s)).some(visible);
              const text = (document.body && document.body.innerText || '').toLowerCase();
              const hasOtp =
                url.includes('email-verification') ||
                url.includes('email_otp') ||
                (url.includes('verify') && url.includes('email')) ||
                qv("input[name='code']") ||
                qv("input[name='otp']") ||
                qv("input[autocomplete='one-time-code']") ||
                qv("input[inputmode='numeric']") ||
                qv("input[type='tel']") ||
                qv("input[maxlength='1']") ||
                qv("input[data-index]") ||
                qv("input[aria-label*='code' i]") ||
                qv("input[aria-label*='digit' i]") ||
                qv("input[placeholder*='code' i]") ||
                (
                  (text.includes('code') || text.includes('verification') || text.includes('verify') ||
                   text.includes('認証コード') || text.includes('確認コード') || text.includes('コード') ||
                   text.includes('验证码') || text.includes('驗證碼')) &&
                  qv("input")
                );
              const hasPassword =
                url.includes('/create-account/password') ||
                url.includes('/u/signup/password') ||
                url.includes('/signup/password') ||
                qv("input[type='password']") ||
                qv("input[name='password']") ||
                qv("input[autocomplete='new-password']");
              const remoteCreateError = new RegExp(
                "account could not be created|couldn't create account|could not create account|"
                + "アカウントを作成できませんでした|アカウントを作成できない|"
                + "无法创建账号|无法创建帳戶|无法建立账号|無法建立帳戶",
                'i'
              ).test(text);
              let state = 'other';
              // /log-in/password 代表该邮箱已走登录密码分支；即便页面 DOM 里有 code/otp 字样，
              // 注册流程也按不可用邮箱处理，不能误判成邮箱验证码页。
              if (url.includes('/log-in/password')) state = 'login_password';
              else if (hasOtp) state = 'email_verification';
              else if (hasPassword) state = 'password';
              else if (url.includes('about-you') || url.includes('profile') || url.includes('create-account/about')) state = 'profile';
              else if (url.includes('chatgpt.com') && !url.includes('/auth/')) state = 'chatgpt';
              return {state, url, hasOtp, hasPassword, remoteCreateError, textPreview: text.slice(0, 160)};
            }"""
        ) or {"state": "other", "url": _page_url(page)}
    except Exception as exc:
        if _is_target_closed_error(exc):
            raise
        return {"state": "other", "url": _page_url(page), "error": f"{type(exc).__name__}: {exc}"}


def _is_email_verification_page(page) -> bool:
    try:
        if "/log-in/password" in (_page_url(page) or "").lower():
            return False
        return _quick_auth_state(page).get("state") == "email_verification"
    except Exception:
        raise
    url = _page_url(page).lower()
    if "email-verification" in url or "email_otp" in url or "verify" in url and "email" in url:
        return True
    loc = _visible_locator(
        page,
        [
            "input[name='code']",
            "input[autocomplete='one-time-code']",
            "input[inputmode='numeric']",
            "input[aria-label*='code' i]",
            "input[placeholder*='code' i]",
        ],
        timeout_ms=500,
    )
    return loc is not None


def _click_passwordless_signup_if_present(page) -> bool:
    """在注册/登录密码页优先点击“使用一次性验证码”，进入邮箱 OTP 流。"""
    selectors = [
        "button[name='intent'][value='passwordless_signup_send_otp']",
        "input[type='submit'][name='intent'][value='passwordless_signup_send_otp']",
        "button[name='intent'][value='passwordless_login_send_otp']",
        "input[type='submit'][name='intent'][value='passwordless_login_send_otp']",
        "button[name='intent'][value*='passwordless'][value*='otp']",
        "input[type='submit'][name='intent'][value*='passwordless'][value*='otp']",
        "button[name='intent'][value*='passwordless'][value*='send_otp']",
        "input[type='submit'][name='intent'][value*='passwordless'][value*='send_otp']",
        "button:has-text('使用一次性验证码注册')",
        "button:has-text('使用一次性验证码登录')",
        "button:has-text('使用一次性验证码')",
        "button:has-text('使用一次性驗證碼註冊')",
        "button:has-text('使用一次性驗證碼登入')",
        "button:has-text('Use a one-time code')",
        "button:has-text('one-time code')",
        "button:has-text('Continue with a one-time code')",
        "button:has-text('Log in with a one-time code')",
        "button:has-text('Sign up with a one-time code')",
        "button:has-text('ワンタイムコード')",
        "button:has-text('認証コード')",
        "a:has-text('使用一次性验证码')",
        "a:has-text('使用一次性驗證碼')",
        "a:has-text('Use a one-time code')",
        "a:has-text('one-time code')",
        "a:has-text('ワンタイムコード')",
        "a:has-text('認証コード')",
        "[role='button']:has-text('使用一次性验证码注册')",
        "[role='button']:has-text('使用一次性验证码登录')",
        "[role='button']:has-text('Continue with a one-time code')",
        "[role='button']:has-text('one-time code')",
    ]
    if _click_first(page, selectors, timeout_ms=1500):
        return True
    try:
        return bool(page.evaluate(
            """() => {
              const visible = el => {
                if (!el) return false;
                const st = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return st.visibility !== 'hidden' && st.display !== 'none' && r.width > 0 && r.height > 0;
              };
              const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
              const norm = s => String(s || '').replace(/\\s+/g, '').toLowerCase();
              const btn = [...document.querySelectorAll('button,a,input[type="submit"],[role="button"],[role="link"]')]
                .filter(el => visible(el) && enabled(el))
                .find(el => {
                  const name = String(el.getAttribute('name') || '').toLowerCase();
                  const value = String(el.getAttribute('value') || '').toLowerCase();
                  const attrs = [
                    el.id, name, value, el.getAttribute('aria-label'), el.getAttribute('title'),
                    el.getAttribute('data-testid'), el.getAttribute('data-dd-action-name'), el.className, el.textContent
                  ].join(' ').toLowerCase();
                  const text = norm(el.textContent || el.getAttribute('value') || '');
                  return (name === 'intent' && value.includes('passwordless') && value.includes('send_otp'))
                    || (name === 'intent' && value.includes('passwordless') && value.includes('otp'))
                    || (name === 'intent' && value === 'passwordless_signup_send_otp')
                    || (name === 'intent' && value === 'passwordless_login_send_otp')
                    || /passwordless.*otp|otp.*passwordless|one[-_\\s]?time.*code|code.*one[-_\\s]?time/.test(attrs)
                    || text.includes('使用一次性验证码注册')
                    || text.includes('使用一次性验证码登录')
                    || text.includes('使用一次性验证码')
                    || text.includes('使用一次性驗證碼註冊')
                    || text.includes('使用一次性驗證碼登入')
                    || text.includes('一次性验证码')
                    || text.includes('一次性驗證碼')
                    || text.includes('ワンタイムコード')
                    || text.includes('認証コード')
                    || text.includes('continuewithaone-timecode')
                    || text.includes('loginwithaone-timecode')
                    || text.includes('signupwithaone-timecode')
                    || text.includes('one-timecode');
                });
              if (!btn) return false;
              btn.scrollIntoView({block:'center'});
              try {
                btn.dispatchEvent(new MouseEvent('pointerdown', {bubbles:true, cancelable:true, view:window}));
                btn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window}));
                btn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, view:window}));
                btn.click();
              } catch (e) {
                const form = btn.closest('form');
                if (form && typeof form.requestSubmit === 'function') form.requestSubmit(btn);
                else if (form) form.submit();
                else throw e;
              }
              return true;
            }"""
        ))
    except Exception:
        return False


def _type_otp(page, code: str) -> None:
    code = str(code or "").strip()
    if not code:
        raise RuntimeError("OTP 为空")

    # 单框
    if _fill_first(
        page,
        [
            "input[name='code']",
            "input[autocomplete='one-time-code']",
            "input[name='otp']",
            "input[aria-label*='code' i]",
            "input[placeholder*='code' i]",
            "input[inputmode='numeric']",
        ],
        code,
        timeout_ms=5000,
    ):
        return

    # 多分框 6 位
    boxes = page.locator("input[maxlength='1'], input[data-index], input[aria-label*='digit' i]")
    try:
        count = boxes.count()
    except Exception:
        count = 0
    if count >= len(code):
        for i, ch in enumerate(code):
            boxes.nth(i).fill(ch)
        return
    raise RuntimeError("找不到 OTP 输入框")


def _clear_otp_inputs(page) -> None:
    try:
        page.evaluate(
            """() => {
              for (const el of document.querySelectorAll('input')) {
                const t = (el.type || '').toLowerCase();
                const n = (el.name || '').toLowerCase();
                const a = (el.autocomplete || '').toLowerCase();
                if (t === 'tel' || t === 'number' || t === 'text' || n.includes('code') || n.includes('otp') || a.includes('one-time')) {
                  const proto = window.HTMLInputElement.prototype;
                  const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                  if (setter) setter.call(el, ''); else el.value = '';
                  el.dispatchEvent(new Event('input', {bubbles:true}));
                  el.dispatchEvent(new Event('change', {bubbles:true}));
                }
              }
            }"""
        )
    except Exception:
        pass


def _wait_after_otp(page, timeout: int = 12) -> str:
    """返回 accepted / invalid / unknown。"""
    end = time.time() + timeout
    while time.time() < end:
        url = _page_url(page).lower()
        body = ""
        try:
            body = (page.locator("body").inner_text(timeout=1000) or "").lower()
        except Exception:
            pass
        if any(x in url for x in ("about-you", "profile", "chatgpt.com", "create-account/about")):
            return "accepted"
        if any(x in body for x in ("incorrect", "invalid", "expired", "错误", "过期", "无效")) and _is_email_verification_page(page):
            return "invalid"
        if "chatgpt.com" in url and "auth" not in url:
            return "accepted"
        time.sleep(0.25 if _fast_mode() else 0.5)
    return "unknown"


def _is_target_closed_error(exc: Exception | str) -> bool:
    text = str(exc).lower()
    return any(x in text for x in ("targetclosed", "target page", "context or browser has been closed", "browser has been closed", "page.is_closed"))


timeout_ms = _timeout_ms
page_url = _page_url
fill_first = _fill_first
click_first = _click_first
maybe_accept_cookies = _maybe_accept_cookies
type_otp = _type_otp
clear_otp_inputs = _clear_otp_inputs
wait_after_otp = _wait_after_otp
click_passwordless_signup_if_present = _click_passwordless_signup_if_present

__all__ = ['timeout_ms', 'page_url', 'fill_first', 'click_first', 'maybe_accept_cookies', 'type_otp', 'clear_otp_inputs', 'wait_after_otp', 'click_passwordless_signup_if_present']
