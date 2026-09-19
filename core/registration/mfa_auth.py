"""Authenticator MFA and security-settings capabilities."""
from __future__ import annotations

import logging
import random
import re
import time

from config import roxybrowser as _cfg
from core.account_export import (
    TwofaProtocolTransportError,
    setup_2fa_protocol as _setup_2fa_protocol,
)
from core.email_provider import wait_for_otp as _wait_for_otp
from core.registration.state_machine import PageState, StageBudget, StageTimeout, classify_page
from core.session import BrowserSession

from .auth_context import (
    checkpoint as _checkpoint,
    current_execution_context,
    current_override,
    install_dispatches,
    time_proxy,
)
from .email_otp import (
    _clear_otp_inputs, _is_email_verification_page, _type_otp,
)
from .selenium_dom import (
    _button_after_input, _check_manual_stop, _click_any, _human_click,
    _human_type_text, _log_prefix, _page_snapshot, _refresh_chatgpt_settings_shell_if_needed,
    _page_warmup, _roxy_page_state, _visible,
    _safe_get, _settings_page_not_ready, _wait,
)

wait_for_otp = _wait_for_otp
setup_2fa_protocol = _setup_2fa_protocol
logger = logging.getLogger(__name__)
time = time_proxy

_CHATGPT_HOME_URL = "https://chatgpt.com/"

_CHATGPT_SECURITY_SETTINGS_URL = "https://chatgpt.com/#settings/Security"

_CHATGPT_PASSWORD_SETTINGS_URL = _CHATGPT_SECURITY_SETTINGS_URL

_MFA_EMAIL_CODE_SELECTOR = (
    'input[name="code"][autocomplete="one-time-code"], '
    'input[autocomplete="one-time-code"]:not([name="totp_otp"])'
)

_MFA_TOTP_CODE_SELECTOR = 'input[name="totp_otp"]'

def _totp_secret_candidate(value: object) -> str | None:
    """Normalize the manual Authenticator key without ever logging it."""
    text = str(value or "").strip()
    if not text:
        return None

    # Some versions expose an otpauth URI rather than a separate <code> node.
    uri_match = re.search(r"(?:[?&]|\b)secret=([A-Z2-7]{16,128})", text, re.IGNORECASE)
    if uri_match:
        return uri_match.group(1).upper()

    # Compact keys are unambiguous. Grouped keys must contain at least four
    # groups, which avoids treating ordinary UI prose as a Base32 secret.
    compact = re.search(r"(?<![A-Z2-7])([A-Z2-7]{20,128})(?![A-Z2-7])", text)
    if compact:
        return compact.group(1).upper()
    grouped = re.search(
        r"(?<![A-Z2-7])((?:[A-Z2-7]{4,8}[\s-]+){3,}[A-Z2-7]{4,8})(?![A-Z2-7])",
        text,
    )
    if grouped:
        normalized = re.sub(r"[\s-]+", "", grouped.group(1)).upper()
        if 20 <= len(normalized) <= 128:
            return normalized
    return None

def _first_visible_css(driver, selector: str):
    from selenium.webdriver.common.by import By

    for element in driver.find_elements(By.CSS_SELECTOR, selector):
        if _visible(element):
            return element
    return None

def _is_stale_element_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return "staleelementreferenceexception" in text or "stale element reference" in text

def _visible_new_password_inputs(driver) -> list:
    return list(driver.execute_script(r"""
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const isCurrent = el => {
      const autocomplete = String(el.getAttribute('autocomplete') || '').toLowerCase();
      const name = String(el.getAttribute('name') || '').toLowerCase();
      const id = String(el.getAttribute('id') || '').toLowerCase();
      return autocomplete === 'current-password' || /current|old|existing/.test(`${name} ${id}`);
    };
    return [...document.querySelectorAll(
      'input[type="password"],input[autocomplete*="password" i],input[name*="password" i]'
    )].filter(el => visible(el) && !isCurrent(el));
    """) or [])

def _wait_visible_css(driver, selector: str, *, timeout: int, label: str):
    end = time.time() + max(1, int(timeout))
    last_url = ""
    while time.time() < end:
        _check_manual_stop()
        element = _first_visible_css(driver, selector)
        if element is not None:
            return element
        try:
            last_url = str(driver.current_url or "")
        except Exception:
            last_url = ""
        time.sleep(0.5)
    raise RuntimeError(f"等待 {label} 超时，当前页面={last_url[:180]}")

def _detect_mfa_enrollment_step(driver):
    """返回当前 MFA 弹窗步骤；新注册会话可能跳过邮箱重认证直达二维码。"""
    totp_field = _first_visible_css(driver, _MFA_TOTP_CODE_SELECTOR)
    if totp_field is not None:
        return "totp", totp_field
    email_code_field = _first_visible_css(driver, _MFA_EMAIL_CODE_SELECTOR)
    if email_code_field is not None:
        return "email", email_code_field
    return None, None

def _wait_mfa_enrollment_step(driver, *, timeout: int = 90):
    end = time.time() + max(1, int(timeout))
    last_url = ""
    while time.time() < end:
        _check_manual_stop()
        step, field = _detect_mfa_enrollment_step(driver)
        if step:
            return step, field
        try:
            last_url = str(driver.current_url or "")
        except Exception:
            last_url = ""
        time.sleep(0.5)
    raise RuntimeError(f"等待 2FA 邮箱重认证或二维码设置页超时，当前页面={last_url[:180]}")

def _wait_after_mfa_email_submit(
    driver,
    *,
    timeout: int = 30,
    resubmit_after: float = 8.0,
):
    """邮箱重认证提交后等待二维码页；若仍停在原表单，仅补交一次。"""
    started = time.monotonic()
    deadline = started + max(3, int(timeout or 30))
    resubmitted = False
    last_step = "transition"
    last_url = ""
    while time.monotonic() < deadline:
        _check_manual_stop()
        step, field = _detect_mfa_enrollment_step(driver)
        last_step = step or "transition"
        try:
            last_url = str(driver.current_url or "")
        except Exception:
            last_url = ""
        if step == "totp":
            return field
        if step == "email" and field is not None:
            try:
                if str(field.get_attribute("aria-invalid") or "").lower() == "true":
                    raise RuntimeError("2FA 邮箱重认证验证码被页面判定为无效")
            except AttributeError:
                pass
            if not resubmitted and time.monotonic() - started >= max(0.0, float(resubmit_after)):
                button = _button_after_input(driver, field)
                if button is not None:
                    _human_click(driver, button, label="mfa_reauth_otp_resubmit")
                    logger.warning("%s[2FA] 邮箱验证码提交后页面未推进，已补交一次", _log_prefix(driver))
                    resubmitted = True
                else:
                    submitted = bool(driver.execute_script(r"""
                    const input = arguments[0];
                    const form = input?.closest('form');
                    if (!form) return false;
                    if (typeof form.requestSubmit === 'function') form.requestSubmit();
                    else form.submit();
                    return true;
                    """, field))
                    if submitted:
                        logger.warning("%s[2FA] 邮箱验证码提交后页面未推进，已通过表单补交一次", _log_prefix(driver))
                        resubmitted = True
        time.sleep(0.4)
    raise RuntimeError(
        f"2FA 邮箱重认证提交后 {int(timeout or 30)} 秒仍未进入二维码页，"
        f"state={last_step} url={last_url[:180]}"
    )

def _dismiss_single_action_dialog(driver) -> bool:
    """Dismiss the one-button first-login welcome dialog, if it blocks Settings."""
    try:
        button = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        for (const dlg of [...document.querySelectorAll('dialog[open],[role="dialog"]')].filter(visible)) {
          if (dlg.querySelector('input:not([type="hidden"]),textarea,select')) continue;
          const buttons = [...dlg.querySelectorAll('button')].filter(el => visible(el) && enabled(el)
            && el.getAttribute('data-testid') !== 'close-button');
          if (buttons.length === 1) return buttons[0];
        }
        return null;
        """)
        if not button:
            return False
        _human_click(driver, button, label="chatgpt_first_login_continue")
        logger.info("%s[2FA] 已关闭首次登录欢迎页", _log_prefix(driver))
        return True
    except Exception:
        return False

def _dismiss_chatgpt_pricing_modal(driver) -> bool:
    """Close the automatic plan/offer modal that can cover the profile menu."""
    try:
        button = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const label = el => [el.innerText, el.textContent, el.getAttribute('aria-label'),
          el.getAttribute('title'), el.getAttribute('data-testid')].filter(Boolean)
          .join(' ').replace(/\s+/g, ' ').trim();
        const modals = [...document.querySelectorAll('[data-testid="modal-account-payment"],[role="dialog"]')]
          .filter(visible);
        const modal = modals.find(el => /pricing|payment|offer|plan|升级|套餐|プラン|オファー/i.test(label(el)));
        if (!modal) return null;
        return [...modal.querySelectorAll('button,a,[role="button"]')].filter(visible).find(el => {
          const text = label(el);
          return el.getAttribute('data-testid') === 'close-button'
            || /close|dismiss|关闭|閉じる|クローズ|닫기|закрыть/i.test(text);
        }) || null;
        """)
        if not button:
            return False
        _human_click(driver, button, label="chatgpt_pricing_modal_close")
        logger.info("%s 已关闭套餐优惠弹窗", _log_prefix(driver))
        time.sleep(0.8)
        return True
    except Exception:
        return False

def _click_chatgpt_settings_control(driver, element, *, label: str = "") -> None:
    """Click ChatGPT's Radix settings controls, whose DIV buttons may ignore CDP clicks."""
    testid = ""
    try:
        testid = str(element.get_attribute("data-testid") or "")
    except Exception:
        pass
    if testid not in {"accounts-profile-button", "settings-menu-item", "security-tab", "password-setting"} \
            and not re.search(r"(?:^|[-_:])password[-_:]?setting(?:$|[-_:])", testid, re.IGNORECASE):
        _human_click(driver, element, label=label)
        return
    driver.execute_script(r"""
    const el = arguments[0];
    if (!el) return;
    const point = el.getBoundingClientRect();
    const init = {bubbles:true, cancelable:true, view:window, pointerType:'mouse',
      clientX:point.left + point.width * 0.5, clientY:point.top + point.height * 0.5,
      button:0, buttons:1};
    el.dispatchEvent(new PointerEvent('pointerdown', init));
    el.dispatchEvent(new MouseEvent('mousedown', init));
    el.dispatchEvent(new MouseEvent('mouseup', {...init, buttons:0}));
    el.dispatchEvent(new MouseEvent('click', {...init, buttons:0}));
    """, element)

def _reveal_chatgpt_settings_navigation(driver) -> bool:
    """Scroll the virtualized Settings navigation so delayed tabs can mount."""
    try:
        result = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const modal = document.querySelector('[data-testid="modal-settings"]') || document;
        const modalRect = modal.getBoundingClientRect?.();
        const candidates = [...modal.querySelectorAll('*')].filter(el => {
          if (!visible(el) || el.scrollHeight <= el.clientHeight + 8) return false;
          const rect = el.getBoundingClientRect();
          return !modalRect || (rect.left < modalRect.left + modalRect.width * 0.48
            && rect.width > 120 && rect.height > 180);
        });
        const scroller = candidates.sort((a, b) => a.clientHeight - b.clientHeight)[0];
        if (!scroller) return {changed: false};
        const before = scroller.scrollTop;
        const max = Math.max(0, scroller.scrollHeight - scroller.clientHeight);
        scroller.scrollTop = Math.min(max, before + Math.max(120, scroller.clientHeight * 0.7));
        scroller.dispatchEvent(new Event('scroll', {bubbles: true}));
        return {changed: scroller.scrollTop !== before, before, after: scroller.scrollTop, max};
        """) or {}
        return bool(result.get("changed"))
    except Exception:
        return False

def _click_password_setting_fallback(driver) -> bool:
    """Click a visible Add Password control when the structured scan missed it."""
    try:
        from selenium.webdriver.common.by import By

        negative = re.compile(r"forgot|reset|log.?in|sign.?in|one.?time|otp|忘记|重置|一次性|验证码", re.IGNORECASE)
        add_password = re.compile(
            r"(?:add|set|create).{0,30}password|password.{0,30}(?:add|set|create)|"
            r"添加密码|设置密码|新增密码|パスワード.{0,30}(?:追加|設定)|"
            r"(?:追加|設定).{0,30}パスワード|비밀번호.{0,30}(?:추가|설정)|"
            r"(?:추가|설정).{0,30}비밀번호",
            re.IGNORECASE,
        )
        add_action = re.compile(r"^(?:add|set|create|添加|设置|新增|追加|設定|추가|설정)$", re.IGNORECASE)
        password_testid = re.compile(r"(?:^|[-_:])password[-_:]?setting(?:$|[-_:])", re.IGNORECASE)

        def _label(element) -> str:
            values = []
            for name in ("innerText", "textContent", "aria-label", "title", "data-testid"):
                try:
                    value = element.get_attribute(name)
                except Exception:
                    value = ""
                if value:
                    values.append(str(value))
            return re.sub(r"\s+", " ", " ".join(values)).strip()

        def _is_action(element) -> bool:
            text = _label(element)
            return bool(text) and not negative.search(text) and bool(add_password.search(text) or add_action.search(text))

        roots = []
        for selector in ("[data-testid*='password-setting']", "[data-testid*='password_setting']", "[data-testid]"):
            try:
                candidates = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in candidates or []:
                try:
                    testid = str(element.get_attribute("data-testid") or "")
                except Exception:
                    testid = ""
                if not password_testid.search(testid) or not _visible(element):
                    continue
                if all(element is not seen for seen in roots):
                    roots.append(element)
        for root in roots:
            descendants = []
            try:
                descendants = root.find_elements(
                    By.CSS_SELECTOR,
                    "button,a,[role='button'],[role='menuitem'],[role='tab'],*",
                ) or []
            except Exception:
                pass
            for candidate in descendants:
                if _visible(candidate) and _is_action(candidate):
                    _click_chatgpt_settings_control(
                        driver, candidate, label="account_password_settings_fallback"
                    )
                    return True
            _click_chatgpt_settings_control(driver, root, label="account_password_settings_fallback")
            return True
    except Exception:
        pass

    try:
        element = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const label = el => [el.innerText, el.textContent, el.getAttribute('aria-label'),
          el.getAttribute('title'), el.getAttribute('data-testid'), el.getAttribute('href')]
          .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
        const negative = /forgot|reset|log.?in|sign.?in|one.?time|otp|忘记|重置|一次性|验证码/i;
        const nodes = [...document.querySelectorAll('[data-testid],button,a,[role="button"],[role="menuitem"]')]
          .filter(visible);
        const isPasswordAction = el => {
          const text = label(el);
          return !negative.test(text) && (
            /(?:add|set|create).{0,30}password|password.{0,30}(?:add|set|create)|添加密码|设置密码|新增密码/i.test(text)
            || /^(?:add|set|create|添加|设置|新增)$/i.test(text)
          );
        };
        const passwordRoots = nodes.filter(el =>
          /password[-_:]?setting/.test(String(el.getAttribute('data-testid') || '').toLowerCase())
        );
        for (const root of passwordRoots) {
          if (isPasswordAction(root)) return root;
          const descendants = [...root.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="tab"],*')]
            .filter(visible);
          const action = descendants.find(isPasswordAction);
          if (action) return action;
          return root;
        }
        return nodes.find(isPasswordAction) || null;
        """)
        if element is None:
            return False
        _click_chatgpt_settings_control(driver, element, label="account_password_settings_fallback")
        return True
    except Exception:
        return False

def _open_chatgpt_security_settings(driver, *, timeout: int = 75):
    """Open Security settings and return the stable Authenticator toggle."""
    _safe_get(
        driver,
        _CHATGPT_SECURITY_SETTINGS_URL,
        timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
        attempts=2,
        accept_hosts=("chatgpt.com",),
    )
    _page_warmup(driver, reason="chatgpt_security_settings")
    _refresh_chatgpt_settings_shell_if_needed(driver, reason="chatgpt_security_settings")
    end = time.time() + max(10, int(timeout))
    dismissed_welcome = False
    profile_clicks = 0
    settings_clicks = 0
    security_clicks = 0
    last_url = ""
    while time.time() < end:
        _check_manual_stop()
        if _dismiss_chatgpt_pricing_modal(driver):
            continue
        if not dismissed_welcome and _dismiss_single_action_dialog(driver):
            dismissed_welcome = True
            time.sleep(3.0)
            _safe_get(
                driver,
                _CHATGPT_HOME_URL,
                timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
                attempts=2,
                accept_hosts=("chatgpt.com",),
            )
            continue
        # The settings controls can exist behind a blocking first-login <dialog>.
        # Only return the toggle after the welcome layer has been handled.
        toggle = _first_visible_css(driver, '[data-testid="mfa-authenticator-toggle"]')
        if toggle is not None:
            return toggle
        navigation = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const label = el => [el.innerText, el.textContent, el.getAttribute('aria-label'),
          el.getAttribute('title'), el.getAttribute('data-testid'), el.getAttribute('href')]
          .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
        const nodes = [...document.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="tab"]')]
          .filter(visible);
        const settings = /settings|设置|設定|설정|paramètres|configurações|definições|definicoes/i;
        const security = /security|安全|セキュリティ|보안|sécurité|seguridad|segurança|sicherheit|безопас/i;
        const profile = /profile|account|avatar|user|账户|账号|个人资料|プロフィール|アカウント|プロファイル/i;
        const text = el => label(el);
        return {
          profile: nodes.filter(el => el.getAttribute('data-testid') === 'accounts-profile-button')
            .find(el => text(el).length > 20)
            || [...nodes].reverse().find(el => el.getAttribute('data-testid') === 'accounts-profile-button')
            || nodes.find(el => profile.test(text(el)) && !settings.test(text(el)) && !security.test(text(el))),
          settings: nodes.find(el => el.getAttribute('data-testid') === 'settings-menu-item')
            || nodes.find(el => settings.test(text(el)) || /#settings\/(?:account|general)|\/settings\/(?:account|general)/i.test(String(el.getAttribute('href') || ''))),
          security: nodes.find(el => el.getAttribute('data-testid') === 'security-tab')
            || nodes.find(el => security.test(text(el)) || /#settings\/security|\/settings\/security/i.test(String(el.getAttribute('href') || ''))),
        };
        """) or {}
        try:
            if navigation.get("security") is not None and security_clicks < 1:
                _click_chatgpt_settings_control(driver, navigation["security"], label="chatgpt_security_navigation")
                security_clicks += 1
                time.sleep(1.2)
                continue
            if navigation.get("settings") is not None and settings_clicks < 1:
                _click_chatgpt_settings_control(driver, navigation["settings"], label="chatgpt_settings_navigation")
                settings_clicks += 1
                time.sleep(1.2)
                continue
            if navigation.get("profile") is not None and profile_clicks < 1:
                _click_chatgpt_settings_control(driver, navigation["profile"], label="chatgpt_profile_menu")
                profile_clicks += 1
                time.sleep(0.8)
                continue
        except Exception:
            pass
        try:
            last_url = str(driver.current_url or "")
        except Exception:
            last_url = ""
        time.sleep(0.5)
    raise RuntimeError(
        f"ChatGPT 安全设置页未出现 Authenticator 开关，当前页面={last_url[:180]} "
        f"settings_clicks={settings_clicks} security_clicks={security_clicks}"
    )

def _disable_roxy_2fa(driver, toggle, *, timeout: int = 60) -> None:
    """Turn off the existing Authenticator method and confirm the switch is off."""
    is_enabled = lambda element: element is not None and (
        str(element.get_attribute("aria-checked") or "").lower() == "true"
        or str(element.get_attribute("data-state") or "").lower() == "checked"
    )
    if not is_enabled(toggle):
        return
    _human_click(driver, toggle, label="mfa_authenticator_disable")
    end = time.time() + max(10, int(timeout))
    while time.time() < end:
        _check_manual_stop()
        # Some locales show a confirmation dialog after the toggle click.
        # Select only affirmative disable/remove actions, never generic close.
        confirmation = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const label = el => [el.innerText, el.textContent, el.getAttribute('aria-label'),
          el.getAttribute('title'), el.getAttribute('data-testid')]
          .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
        const yes = /disable|remove|turn off|deactivate|关闭|禁用|停用|删除|取消启用|無効|解除|desactivar|désactiver/i;
        const no = /cancel|close|back|取消|关闭窗口|返回|キャンセル|閉じる/i;
        return [...document.querySelectorAll('button,[role="button"],[role="menuitem"]')]
          .filter(visible)
          .find(el => yes.test(label(el)) && !no.test(label(el))) || null;
        """)
        if confirmation is not None:
            _human_click(driver, confirmation, label="mfa_authenticator_disable_confirm")
        current = _first_visible_css(driver, '[data-testid="mfa-authenticator-toggle"]')
        if current is not None and not is_enabled(current):
            logger.info("%s[2FA] 已确认远端 Authenticator 开关关闭", _log_prefix(driver))
            return
        time.sleep(0.4)
    raise RuntimeError("关闭旧 Authenticator 2FA 后未确认开关已关闭")

def _complete_settings_email_reauth(
    driver,
    email: str,
    *,
    challenge_detector=None,
    challenge_submitter=None,
) -> None:
    """Complete Settings email re-authentication, including a follow-up TOTP."""
    otp_after_ts = time.time()
    logger.info("%s 设置页要求邮箱重认证，等待邮箱验证码：email=%s", _log_prefix(driver), email)
    email_code = wait_for_otp(email, after_ts=otp_after_ts)
    _clear_otp_inputs(driver)
    _type_otp(driver, email_code, timeout=30)
    field = _first_visible_css(
        driver,
        'input[autocomplete="one-time-code"],input[name="code"],input[inputmode="numeric"],input[type="tel"]',
    )
    submit = _button_after_input(driver, field) if field is not None else None
    if submit is not None:
        _human_click(driver, submit, label="chatgpt_settings_reauth_submit")
    elif field is not None:
        driver.execute_script(r"""
        const input = arguments[0];
        const form = input?.closest('form');
        if (form && typeof form.requestSubmit === 'function') form.requestSubmit();
        else if (form) form.submit();
        """, field)
    else:
        raise RuntimeError("设置页邮箱重认证缺少验证码提交按钮")

    # Settings re-authentication can chain email OTP -> Authenticator MFA.
    # Reuse the same browser challenge handling as normal account login; a
    # valid account must not remain stranded on /mfa-challenge.
    from core.account_credentials import get_account_login_credentials

    context = current_execution_context()
    challenge_detector = (
        challenge_detector
        or getattr(context, "challenge_detector", None)
        or current_override("_is_totp_login_page")
    )
    challenge_submitter = (
        challenge_submitter
        or getattr(context, "challenge_submitter", None)
        or current_override("_submit_saved_login_totp")
    )
    if not callable(challenge_detector):
        def challenge_detector(current_driver) -> bool:
            return _roxy_page_state(current_driver) == PageState.MFA_TOTP

    _, totp_secret = get_account_login_credentials(email)
    totp_submitted = False
    deadline = time.time() + 45
    while time.time() < deadline:
        _check_manual_stop()
        if challenge_detector(driver):
            if totp_submitted:
                time.sleep(0.5)
                continue
            if not callable(challenge_submitter):
                raise RuntimeError("设置页邮箱重认证后需要 TOTP，但未注入 challenge submitter")
            challenge_submitter(driver, email, totp_secret)
            totp_submitted = True
            continue
        if not _is_email_verification_page(driver):
            logger.info("%s 设置页邮箱重认证已完成", _log_prefix(driver))
            return
        time.sleep(0.5)
    raise RuntimeError(f"设置页邮箱重认证后未返回 ChatGPT 设置页：{str(driver.current_url or '')[:180]}")

def _read_totp_secret_from_dialog(driver, field) -> str | None:
    """Read an Authenticator secret without activating any external-protocol link."""
    values = driver.execute_script(r"""
    const input = arguments[0];
    const root = input.closest('[role="dialog"]') || document;
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const nodes = [root, ...root.querySelectorAll(
      '[aria-label],[data-secret],[data-value],[data-uri],[data-otpauth],code,pre,input,div,span,a,img,svg'
    )].filter(visible).slice(0, 1000);

    // The QR-code fallback is sometimes an otpauth:// link. Clicking it opens a
    // Chrome-level “Open Passwords/Key?” prompt that Selenium cannot inspect.
    // Its href already contains the secret, so make the link inert and read it.
    for (const el of nodes) {
      const link = el.matches?.('a[href]') ? el : el.closest?.('a[href]');
      const href = String(link?.getAttribute('href') || '').trim();
      if (/^(?:otpauth|web\+otpauth|authenticator):/i.test(href)
          && link && link.dataset.codexExternalProtocolBlocked !== '1') {
        link.addEventListener('click', event => event.preventDefault(), true);
        link.dataset.codexExternalProtocolBlocked = '1';
      }
    }

    return nodes.flatMap(el => [
      el.getAttribute?.('data-secret'), el.getAttribute?.('data-value'),
      el.getAttribute?.('data-uri'), el.getAttribute?.('data-otpauth'),
      el.getAttribute?.('value'), el.getAttribute?.('href'),
      el.getAttribute?.('src'), el.getAttribute?.('srcset'),
      el.getAttribute?.('aria-label'), el.innerText, el.textContent
    ]).map(value => String(value || '').trim()).filter(Boolean);
    """, field) or []
    for value in values:
        secret = _totp_secret_candidate(value)
        if secret:
            return secret
    return None

def _manual_totp_secret(driver, field, *, timeout: int = 20) -> str:
    """Read the QR binding URI, or safely switch the dialog to a manual key."""
    secret = _read_totp_secret_from_dialog(driver, field)
    if secret:
        logger.info("%s[2FA] 已从二维码绑定信息读取 Authenticator key，未打开外部应用", _log_prefix(driver))
        return secret

    manual_button = driver.execute_script(r"""
    const input = arguments[0];
    const root = input.closest('[role="dialog"]') || input.closest('form') || document;
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
    const candidates = [...root.querySelectorAll('button,a,[role="button"]')].filter(el =>
      visible(el) && enabled(el) && el.getAttribute('data-testid') !== 'close-button');
    const attrs = el => [
      el.innerText, el.textContent, el.getAttribute('aria-label'), el.getAttribute('data-testid'),
      el.getAttribute('name'), el.getAttribute('value'), el.getAttribute('href')
    ].filter(Boolean).join(' ').toLowerCase();
    const external = el => /^(?:otpauth|web\+otpauth|authenticator):/i.test(
      String((el.closest('a[href]') || el).getAttribute('href') || '').trim()
    );
    const wanted = /manual|setup.?key|secret.?key|enter.?key|can.?t.?scan|unable.?to.?scan|trouble.*scan|scan.?code|手動|手动|設定キー|セットアップキー|スキャンでき|読み込み.*問題|スキャン.*問題/;
    const unwanted = /cancel|close|back|previous|キャンセル|閉じる|戻る|取消|关闭|返回/;
    return candidates.find(el => wanted.test(attrs(el)) && !unwanted.test(attrs(el)) && !external(el)) || null;
    """, field)
    if not manual_button:
        raise RuntimeError("TOTP 设置弹窗未提供安全可点击的手动密钥入口")
    _human_click(driver, manual_button, label="totp_show_manual_secret")

    end = time.time() + max(2, int(timeout))
    while time.time() < end:
        _check_manual_stop()
        secret = _read_totp_secret_from_dialog(driver, field)
        if secret:
            return secret
        time.sleep(0.35)
    raise RuntimeError("TOTP 设置弹窗未显示可读取的手动密钥")

def setup_roxy_2fa(
    driver,
    email: str,
    *,
    on_secret=None,
    existing_secret: str | None = None,
    force_reconfigure: bool = False,
    on_disabled=None,
) -> str:
    """Enable Authenticator MFA in the existing Roxy browser session."""
    import pyotp

    logger.info("%s[2FA] 打开 ChatGPT 安全设置", _log_prefix(driver))
    toggle = _open_chatgpt_security_settings(driver)
    if (
        str(toggle.get_attribute("aria-checked") or "").lower() == "true"
        or str(toggle.get_attribute("data-state") or "").lower() == "checked"
    ):
        if force_reconfigure:
            _disable_roxy_2fa(driver, toggle)
            if on_disabled is not None:
                on_disabled()
            toggle = _first_visible_css(driver, '[data-testid="mfa-authenticator-toggle"]')
            if toggle is None:
                raise RuntimeError("关闭旧 Authenticator 后未找到新的设置开关")
        else:
            recovered = _totp_secret_candidate(existing_secret)
            if recovered:
                logger.info("%s[2FA] 已确认远端 Authenticator 开关启用，保留本地检查点密钥", _log_prefix(driver))
                return recovered
            raise RuntimeError("Authenticator 2FA 已启用，但当前流程无法恢复既有 secret")

    otp_after_ts = time.time()
    _human_click(driver, toggle, label="mfa_authenticator_toggle")
    step, field = _wait_mfa_enrollment_step(driver, timeout=90)
    if step == "email":
        logger.info("%s[2FA] 当前会话要求邮箱重认证", _log_prefix(driver))
        _check_manual_stop()
        email_code = wait_for_otp(email, after_ts=otp_after_ts)
        _human_type_text(driver, field, email_code, clear=True)
        submit_email_code = _button_after_input(driver, field)
        if not submit_email_code:
            raise RuntimeError("2FA 重认证页缺少验证码提交按钮")
        _human_click(driver, submit_email_code, label="mfa_reauth_otp_submit")
        logger.info("%s[2FA] 已提交邮箱重认证验证码", _log_prefix(driver))
        # 旧逻辑会盲等 90 秒；现在 8 秒仍在原页就补交一次，30 秒仍不推进则明确失败。
        totp_field = _wait_after_mfa_email_submit(driver, timeout=30, resubmit_after=8)
    else:
        # 刚完成注册时 pwd_auth_time 足够新，OpenAI 会直接展示二维码而不再发邮件。
        logger.info("%s[2FA] 当前登录态仍新鲜，已跳过邮箱重认证并直达二维码设置页", _log_prefix(driver))
        totp_field = field
    secret = _manual_totp_secret(driver, totp_field)
    # 必须在激活前持久化：一旦 OpenAI 接受下面的 TOTP，若进程恰好中断，
    # 没有这个 secret 就无法再次登录账号。
    if on_secret is not None:
        on_secret(secret)

    # Avoid submitting a code in the final few seconds of its validity window.
    remaining = 30 - (int(time.time()) % 30)
    if remaining < 6:
        time.sleep(remaining + 1)
    totp_code = pyotp.TOTP(secret).now()
    _human_type_text(driver, totp_field, totp_code, clear=True)
    verify_button = _button_after_input(driver, totp_field)
    if not verify_button:
        raise RuntimeError("TOTP 设置弹窗缺少验证按钮")
    _human_click(driver, verify_button, label="totp_verify")

    end = time.time() + 45
    resubmitted = False
    submitted_code = totp_code
    while time.time() < end:
        _check_manual_stop()
        current_toggle = _first_visible_css(driver, '[data-testid="mfa-authenticator-toggle"]')
        enabled = current_toggle is not None and (
            str(current_toggle.get_attribute("aria-checked") or "").lower() == "true"
            or str(current_toggle.get_attribute("data-state") or "").lower() == "checked"
        )
        if enabled and _first_visible_css(driver, 'input[name="totp_otp"]') is None:
            logger.info("%s[2FA] Authenticator 2FA 已启用", _log_prefix(driver))
            return secret
        current_field = _first_visible_css(driver, _MFA_TOTP_CODE_SELECTOR)
        # The code can cross a 30-second boundary while ChatGPT is processing
        # the first click. If the dialog is still present, submit one fresh
        # code instead of waiting until the whole step times out.
        fresh_code = pyotp.TOTP(secret).now()
        if current_field is not None and not resubmitted and fresh_code != submitted_code:
            _human_type_text(driver, current_field, fresh_code, clear=True)
            retry_button = _button_after_input(driver, current_field)
            if retry_button is not None:
                _human_click(driver, retry_button, label="totp_verify_retry")
                logger.warning("%s[2FA] 首次 TOTP 提交后页面未确认，已使用新时段验证码补交一次", _log_prefix(driver))
                resubmitted = True
                submitted_code = fresh_code
                end = max(end, time.time() + 35)
        time.sleep(0.5)
    raise RuntimeError("TOTP 验证提交后未确认 Authenticator 开关已启用")

def setup_protocol_2fa_with_browser_fallback(
    driver,
    email: str,
    protocol_session: BrowserSession,
    access_token: str,
    *,
    on_secret=None,
    existing_secret: str | None = None,
) -> tuple[str, bool]:
    """优先协议开通 2FA，失败时复用当前登录态改走安全设置页。

    返回 ``(secret, fallback_used)``。协议 enroll 可能已经返回 secret、但在
    activate 阶段失败，因此这里会同时记住协议和页面流程产生的最新 secret，
    并在 UI 回退时把检查点 secret 传给页面流程确认远端开关状态。
    """
    checkpoint = {"secret": str(existing_secret or "").strip()}

    def _remember_secret(secret: str) -> None:
        normalized = str(secret or "").strip()
        if not normalized:
            raise RuntimeError("Authenticator key 检查点为空")
        checkpoint["secret"] = normalized
        if on_secret is not None:
            on_secret(normalized)

    protocol_exc = None
    try:
        secret = setup_2fa_protocol(
            protocol_session,
            access_token,
            on_secret=_remember_secret,
        )
        return str(secret or checkpoint["secret"]).strip(), False
    except Exception as protocol_exc:
        # A bounded TLS/connection retry can leave the curl connection pool
        # unhealthy while the browser session and account state remain valid.
        # Reset only that transport and retry once when no secret was
        # checkpointed yet. If enroll already returned a secret, repeating it
        # could create an ambiguous second enrollment, so use the UI fallback.
        protocol_error_exc = protocol_exc
        if isinstance(protocol_exc, TwofaProtocolTransportError) and not checkpoint["secret"]:
            reset_transport = getattr(protocol_session, "reset_transport", None)
            if callable(reset_transport):
                try:
                    reset_transport()
                    logger.warning(
                        "%s[2FA] 协议通道出现临时传输错误，已重置同一会话 transport 并重试一次",
                        _log_prefix(driver),
                    )
                    secret = setup_2fa_protocol(
                        protocol_session,
                        access_token,
                        on_secret=_remember_secret,
                    )
                    logger.info("%s[2FA] 重置协议通道后启用成功", _log_prefix(driver))
                    return str(secret or checkpoint["secret"]).strip(), False
                except Exception as retry_error:
                    protocol_error_exc = retry_error
                    logger.warning(
                        "%s[2FA] 重置协议通道后重试仍失败，继续浏览器 UI 回退：%s",
                        _log_prefix(driver), type(retry_error).__name__,
                    )
        protocol_error = f"{type(protocol_error_exc).__name__}: {str(protocol_error_exc)[:180]}"
        logger.warning(
            "%s[2FA] 协议开通失败，复用当前登录态改走浏览器安全设置页：%s",
            _log_prefix(driver),
            protocol_error,
        )
        try:
            secret = setup_roxy_2fa(
                driver,
                email,
                on_secret=_remember_secret,
                existing_secret=checkpoint["secret"] or None,
            )
        except Exception as browser_exc:
            browser_error = f"{type(browser_exc).__name__}: {str(browser_exc)[:180]}"
            raise RuntimeError(
                f"协议 2FA 失败且浏览器 UI 回退也失败；"
                f"protocol={protocol_error}；browser={browser_error}"
            ) from browser_exc
        logger.info("%s[2FA] 协议失败后已通过浏览器安全设置页启用 Authenticator", _log_prefix(driver))
        return str(secret or checkpoint["secret"]).strip(), True


install_dispatches(globals(), (
    "wait_for_otp", "setup_2fa_protocol", "_totp_secret_candidate",
    "_first_visible_css", "_is_stale_element_error", "_visible_new_password_inputs",
    "_wait_visible_css", "_detect_mfa_enrollment_step", "_wait_mfa_enrollment_step",
    "_wait_after_mfa_email_submit", "_dismiss_single_action_dialog",
    "_dismiss_chatgpt_pricing_modal", "_click_chatgpt_settings_control",
    "_reveal_chatgpt_settings_navigation", "_click_password_setting_fallback",
    "_open_chatgpt_security_settings", "_disable_roxy_2fa",
    "_complete_settings_email_reauth", "_read_totp_secret_from_dialog",
    "_manual_totp_secret", "setup_roxy_2fa",
    "setup_protocol_2fa_with_browser_fallback",
))

__all__ = [
    "_CHATGPT_HOME_URL", "_CHATGPT_SECURITY_SETTINGS_URL",
    "_CHATGPT_PASSWORD_SETTINGS_URL", "_MFA_EMAIL_CODE_SELECTOR",
    "_MFA_TOTP_CODE_SELECTOR", "wait_for_otp", "setup_2fa_protocol",
    "_totp_secret_candidate", "_first_visible_css", "_is_stale_element_error",
    "_visible_new_password_inputs", "_wait_visible_css", "_detect_mfa_enrollment_step",
    "_wait_mfa_enrollment_step", "_wait_after_mfa_email_submit",
    "_dismiss_single_action_dialog", "_dismiss_chatgpt_pricing_modal",
    "_click_chatgpt_settings_control", "_reveal_chatgpt_settings_navigation",
    "_click_password_setting_fallback", "_open_chatgpt_security_settings",
    "_disable_roxy_2fa", "_complete_settings_email_reauth",
    "_read_totp_secret_from_dialog", "_manual_totp_secret", "setup_roxy_2fa",
    "setup_protocol_2fa_with_browser_fallback",
]
