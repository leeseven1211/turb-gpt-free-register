"""Password and profile authentication capabilities."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import string
import time
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from core.auth_challenge import (
    PasswordRejectedError, PasswordSetupNotReadyError,
)
from core.humanize import delay as _human_delay
from core.registration.state_machine import PageState, StageBudget, StageTimeout, classify_page

from .auth_context import install_dispatches, time_proxy
from .email_otp import (
    _clear_otp_inputs, _is_email_verification_page, _type_otp,
)
from .selenium_dom import (
    _button_after_input, _check_manual_stop, _click_any, _click_if_enabled_submit,
    _fill_birthday_or_age,
    _find_any, _human_click, _human_type_text, _is_login_password_page,
    _is_profile_like, _is_signup_password_page, _log_prefix, _maybe_accept,
    _page_snapshot, _page_warmup, _password_page_state, _refresh_chatgpt_settings_shell_if_needed,
    _safe_get, _select_or_type, _settings_page_not_ready, _set_element_value,
    _type_any,
)
from .session_auth import _has_access_token
from .mfa_auth import (
    _click_chatgpt_settings_control, _click_password_setting_fallback,
    _complete_settings_email_reauth, _dismiss_chatgpt_pricing_modal,
    _dismiss_single_action_dialog, _is_stale_element_error,
    _open_chatgpt_security_settings, _reveal_chatgpt_settings_navigation,
    _visible_new_password_inputs,
)

human_delay = _human_delay
_CHATGPT_PASSWORD_SETTINGS_URL = "https://chatgpt.com/#settings/Security"
logger = logging.getLogger(__name__)
time = time_proxy

def _generate_roxy_password() -> str:
    """参考 FlowPilot 密码策略：8~64 位，含大小写、数字、符号。"""
    upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    lower = 'abcdefghjkmnpqrstuvwxyz'
    digits = '23456789'
    symbols = '!@#$%^&*?_-='
    groups = [upper, lower, digits, symbols]
    all_chars = ''.join(groups)
    chars = [random.choice(g) for g in groups]
    while len(chars) < 14:
        chars.append(random.choice(all_chars))
    random.shuffle(chars)
    return ''.join(chars)

def _registration_password() -> str:
    """Every password-based registration gets an independent random password."""
    return _generate_roxy_password()

def _registration_auth_mode() -> str:
    try:
        from config import register as _register_cfg
        mode = str(getattr(_register_cfg, 'REGISTRATION_AUTH_MODE', 'otp') or 'otp').strip().lower()
    except Exception:
        mode = 'otp'
    return mode if mode in {'otp', 'password'} else 'otp'

def _password_transition_timeout_seconds() -> float:
    """Return the independent budget used after submitting a password form."""
    try:
        from config import register as _register_cfg

        value = float(
            getattr(_register_cfg, 'REGISTRATION_PASSWORD_TRANSITION_TIMEOUT_SECONDS', 60)
            or 60
        )
    except (TypeError, ValueError, ImportError):
        value = 60.0
    return max(20.0, min(180.0, value))

class _PasswordTransitionTimeout(RuntimeError):
    """Password submit was dispatched but the remote result is still unknown."""


_PASSWORD_SUBMIT_REMOTE_ERROR_MARKERS = (
    "account could not be created",
    "couldn't create account",
    "could not create account",
    "アカウントを作成できませんでした",
    "アカウントを作成できない",
    "无法创建账号",
    "无法创建帳戶",
    "无法建立账号",
    "無法建立帳戶",
)

# The profile page can reject account creation with a remote policy/eligibility
# message that is not exposed through the normal form-error selectors.  Keep
# this list deliberately narrow: a generic validation message must still be
# treated as a workflow error, while this marker means the upstream has made a
# decision and we should not burn the whole profile timeout waiting for a
# navigation that will never happen.
_PROFILE_ACCOUNT_REJECTION_MARKERS = (
    "利用規約のため、お客様のアカウントを作成できません",
    "アカウントを作成できません",
    "can't create your account",
    "cannot create your account",
    "couldn't create your account",
    "account cannot be created",
    "无法创建您的账号",
    "无法创建账号",
)


def _profile_account_rejection_marker(driver) -> str | None:
    """Return a stable remote-rejection marker without persisting page text."""
    try:
        body_text = driver.execute_script(
            "return String(document.body?.innerText || document.body?.textContent || '')"
        )
    except Exception:
        return None
    text = re.sub(r"\s+", " ", str(body_text or "")).strip()
    lowered = text.lower()
    for marker in _PROFILE_ACCOUNT_REJECTION_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def _password_submit_error_marker(state: object) -> str | None:
    """Return a stable marker for an explicit post-submit create error.

    The page may remain on ``/create-account/password`` after the request has
    already reached OpenAI.  Only match account-creation error phrases, not a
    generic ``try again`` hint, so a transient form helper cannot prematurely
    turn a still-pending request into an unknown outcome.
    """
    if not isinstance(state, dict):
        return None
    text = re.sub(r"\s+", " ", str(state.get("text") or "")).strip().casefold()
    for marker in _PASSWORD_SUBMIT_REMOTE_ERROR_MARKERS:
        if marker.casefold() in text:
            return "password_submit_remote_error"
    return None


def _password_page_state_summary(state: object) -> str:
    """Build a non-sensitive password-page summary for logs and task errors."""
    if not isinstance(state, dict):
        return f"state_type={type(state).__name__}"
    raw_url = str(state.get("url") or "")
    parsed_url = urlsplit(raw_url)
    return (
        f"path={parsed_url.path or '/'} "
        f"inputs={len(state.get('inputs') or []) if isinstance(state.get('inputs'), list) else 0} "
        f"buttons={len(state.get('buttons') or []) if isinstance(state.get('buttons'), list) else 0} "
        f"text_length={len(str(state.get('text') or ''))}"
    )


def _click_passwordless_signup_if_present(driver) -> dict:
    """
    新版注册/登录流在 password 页可能默认要求密码。
    如果页面提供“使用一次性验证码”按钮，优先点击进入邮箱 OTP 页面。
    """
    try:
        result = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const norm = s => String(s || '').replace(/\s+/g, '').toLowerCase();
        const candidates = [...document.querySelectorAll('button,a,input[type="submit"],[role="button"],[role="link"]')].filter(el => visible(el) && enabled(el));
        const isPasswordlessOtp = el => {
          const name = String(el.getAttribute('name') || '').toLowerCase();
          const value = String(el.getAttribute('value') || '').toLowerCase();
          const attrs = [
            el.id, name, value, el.getAttribute('aria-label'), el.getAttribute('title'),
            el.getAttribute('data-testid'), el.getAttribute('data-dd-action-name'), el.className, el.textContent
          ].join(' ').toLowerCase();
          const text = norm(el.textContent || el.getAttribute('value') || '');
          const compactAttrs = norm(attrs);
          return (
            (name === 'intent' && value.includes('passwordless') && value.includes('send_otp')) ||
            (name === 'intent' && value.includes('passwordless') && value.includes('otp')) ||
            (name === 'intent' && value === 'passwordless_signup_send_otp') ||
            (name === 'intent' && value === 'passwordless_login_send_otp') ||
            attrs.includes('passwordless_signup_send_otp') ||
            attrs.includes('passwordless_login_send_otp') ||
            /passwordless.*otp|otp.*passwordless|one[-_\s]?time.*code|code.*one[-_\s]?time/.test(attrs) ||
            text.includes('使用一次性验证码注册') ||
            text.includes('使用一次性验证码登录') ||
            text.includes('使用一次性验证码') ||
            text.includes('使用一次性驗證碼註冊') ||
            text.includes('使用一次性驗證碼登入') ||
            text.includes('一次性验证码') ||
            text.includes('一次性驗證碼') ||
            text.includes('メールでコード') ||
            text.includes('メールでログイン') ||
            text.includes('メールで続行') ||
            text.includes('メールで認証') ||
            text.includes('メールで確認') ||
            text.includes('コードでログイン') ||
            text.includes('コードを使ってログイン') ||
            text.includes('ワンタイムコード') ||
            text.includes('ワンタイムパスワード') ||
            text.includes('ワンタイムコードを使う') ||
            text.includes('別の方法') ||
            text.includes('パスワードを使わずにログイン') ||
            text.includes('パスワードなしでログイン') ||
            text.includes('認証コード') ||
            text.includes('使用其他方式') ||
            text.includes('尝试其他方式') ||
            text.includes('使用邮箱验证码') ||
            text.includes('使用邮箱登录') ||
            text.includes('邮箱验证码登录') ||
            text.includes('改用邮箱') ||
            text.includes('다른 방법') ||
            text.includes('이메일로 로그인') ||
            text.includes('일회용 코드') ||
            compactAttrs.includes('tryanotherway') ||
            compactAttrs.includes('useanothermethod') ||
            compactAttrs.includes('useemailinstead') ||
            compactAttrs.includes('continuewithemail') ||
            compactAttrs.includes('emailmeacode') ||
            compactAttrs.includes('sendmeacode') ||
            compactAttrs.includes('loginwithemail') ||
            compactAttrs.includes('useacodeinstead') ||
            text.includes('useonetimeregistrationcode') ||
            text.includes('useaone-timecodetosignup') ||
            text.includes('useaone-timecodetoregister') ||
            text.includes('useaone-timecodetologin') ||
            text.includes('continuewithaone-timecode') ||
            text.includes('loginwithaone-timecode') ||
            text.includes('signupwithaone-timecode') ||
            text.includes('one-timecode')
          );
        };
        const isMethodPicker = el => {
          const attrs = norm([
            el.textContent, el.getAttribute('aria-label'), el.getAttribute('title'),
            el.getAttribute('data-testid'), el.getAttribute('data-dd-action-name')
          ].join(' '));
          return attrs.includes('tryanotherway') || attrs.includes('useanothermethod')
            || attrs.includes('別の方法') || attrs.includes('使用其他方式')
            || attrs.includes('尝试其他方式') || attrs.includes('다른 방법');
        };
        const btn = candidates.find(isPasswordlessOtp) || candidates.find(isMethodPicker);
        if (!btn) return {
          ok:false,
          reason:'missing_passwordless_button',
          // 只记录技术属性和短文本，方便区分“入口未挂载”和“当前实验分支不提供 OTP”；
          // 不读取 input value，也不把完整页面正文写入任务错误。
          candidates: candidates.map(el => ({
            tag: el.tagName,
            name: el.getAttribute('name') || '',
            value: el.getAttribute('value') || '',
            testid: el.getAttribute('data-testid') || '',
            action: el.getAttribute('data-dd-action-name') || '',
            aria: el.getAttribute('aria-label') || '',
            text: (el.textContent || el.getAttribute('value') || '').replace(/\\s+/g, ' ').trim().slice(0, 100)
          })).slice(0, 30)
        };
        btn.scrollIntoView({block:'center'});
        return {
          ok:true,
          reason: isMethodPicker(btn) && !isPasswordlessOtp(btn)
            ? 'passwordless_method_picker' : 'passwordless_send_otp_target',
          followup: isMethodPicker(btn) && !isPasswordlessOtp(btn),
          button: btn,
          name: btn.getAttribute('name') || '',
          value: btn.getAttribute('value') || '',
          text: (btn.textContent || '').trim().slice(0, 80)
        };
        """) or {"ok": False, "reason": "empty_result"}
        if result.get("ok") and result.get("button"):
            _human_click(driver, result.get("button"), label="passwordless_otp")
            result["reason"] = (
                "clicked_passwordless_method_picker"
                if result.get("followup") else "clicked_passwordless_send_otp"
            )
            result.pop("button", None)
        return result
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

def _click_signup_password_from_otp_if_present(driver, timeout: int = 15) -> dict:
    """从新账号 OTP 页切换到 create-account/password。

    OpenAI 当前默认先展示邮箱验证码页；password 模式必须主动点击页面上的
    `/create-account/password`，否则会直接完成无密码注册。
    """
    started_at = time.time()
    wait_seconds = max(1, timeout)
    find_end = started_at + wait_seconds
    # SPA 首屏偶尔只完成了 OTP 页骨架，给它一次受控刷新机会；刷新后仍无入口
    # 就明确记录为 OTP-only 变体，不能无密码继续注册。
    refresh_after = (
        started_at + min(5.0, max(1.0, wait_seconds / 3))
        if timeout > 1
        else None
    )
    refresh_attempted = False
    last_result = {"ok": False, "reason": "missing_create_account_password_target"}
    while time.time() < find_end:
        try:
            result = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
        const norm = value => String(value || '').replace(/\s+/g, '').toLowerCase();
        const candidates = [...document.querySelectorAll('a,button,input[type="submit"],[role="button"],[role="link"]')]
          .filter(el => visible(el) && enabled(el));
        const target = candidates.find(el => {
          const href = String(el.getAttribute('href') || '');
          let path = '';
          try { path = new URL(href, location.href).pathname; } catch (_) {}
          const name = String(el.getAttribute('name') || '').toLowerCase();
          const value = String(el.getAttribute('value') || '').toLowerCase();
          const attrs = [
            el.textContent, el.getAttribute('aria-label'), el.getAttribute('title'),
            el.getAttribute('data-testid'), el.getAttribute('data-dd-action-name')
          ].map(norm).join(' ');
          const passwordLabel = (
            attrs.includes('continuewithpassword') ||
            attrs.includes('continuewithapassword') ||
            attrs.includes('パスワードで続行') ||
            attrs.includes('使用密码继续') ||
            attrs.includes('继续使用密码') ||
            attrs.includes('使用密碼繼續') ||
            attrs.includes('繼續使用密碼') ||
            attrs.includes('비밀번호로계속')
          );
          const conflictingLoginPath = path === '/log-in/password';
          return path === '/create-account/password'
            || (!conflictingLoginPath && path.includes('/password') && passwordLabel)
            || (name === 'intent' && value === 'passwordless_signup_use_password')
            || (!conflictingLoginPath && passwordLabel);
        });
        if (!target) return {
          ok:false,
          reason:'missing_create_account_password_target',
          input_count: [...document.querySelectorAll('input')].filter(visible).length,
          button_count: candidates.length,
          body_text_length: String(document.body?.innerText || '').trim().length,
          candidates: candidates.map(el => ({
            tag: el.tagName,
            text: String(el.textContent || el.getAttribute('value') || '').trim().slice(0, 80),
            href: el.getAttribute('href') || '',
            name: el.getAttribute('name') || '',
            value: el.getAttribute('value') || '',
            aria: el.getAttribute('aria-label') || ''
          })).slice(0, 20)
        };
        target.scrollIntoView({block:'center'});
        return {
          ok:true,
          reason:'create_account_password_target',
          target,
          tag: target.tagName,
          href: target.getAttribute('href') || '',
          name: target.getAttribute('name') || '',
          value: target.getAttribute('value') || ''
        };
            """) or {"ok": False, "reason": "empty_result"}
        except Exception as exc:
            last_result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
            time.sleep(0.4)
            continue

        target = result.pop("target", None)
        if result.get("ok") and target is not None:
            _human_click(driver, target, label="signup_use_password")
            wait_end = time.time() + max(1, timeout)
            while time.time() < wait_end:
                if _is_signup_password_page(driver):
                    result["reason"] = "entered_create_account_password"
                    return result
                if _has_access_token(driver):
                    return {**result, "ok": False, "reason": "logged_in_before_password_page"}
                time.sleep(0.4)
            return {**result, "ok": False, "reason": "create_account_password_navigation_timeout"}

        last_result = result
        if _is_signup_password_page(driver):
            return {"ok": True, "reason": "already_on_create_account_password"}
        if _has_access_token(driver):
            return {"ok": False, "reason": "logged_in_before_password_target"}
        if refresh_after is not None and not refresh_attempted and time.time() >= refresh_after:
            refresh_attempted = True
            logger.warning(
                "%s 密码入口在验证码页首轮扫描中未出现，执行一次受控刷新后重新扫描：last=%s",
                _log_prefix(driver),
                last_result,
            )
            try:
                refresh = getattr(driver, "refresh", None)
                if not callable(refresh):
                    raise AttributeError("driver.refresh unavailable")
                refresh()
            except Exception as exc:
                logger.warning("%s 密码入口刷新失败，继续使用原页面诊断：%s", _log_prefix(driver), exc)
            time.sleep(0.8)
            # 刷新会重新挂载 auth.openai.com 的 React 树；不要把刷新本身
            # 计入原来的 15 秒硬窗口，否则空壳刚开始恢复就会被判失败。
            # 这是一次有界的额外等待，不改变页面分支或密码流程。
            find_end = max(find_end, time.time() + min(10.0, wait_seconds))
            continue
        time.sleep(0.4)

    current_url = str(getattr(driver, "current_url", "") or "")
    parsed_url = urlsplit(current_url)
    candidates = (last_result.get("candidates") or [])[:10]
    input_count = int(last_result.get("input_count") or 0)
    button_count = int(last_result.get("button_count") or len(candidates))
    body_text_length = int(last_result.get("body_text_length") or 0)
    page_mounted = bool(candidates or input_count or button_count)
    page_snapshot_observed = (
        last_result.get("reason") == "missing_create_account_password_target"
        and all(key in last_result for key in ("input_count", "button_count", "body_text_length"))
    )
    is_email_verification_route = (
        parsed_url.hostname == "auth.openai.com"
        and parsed_url.path.rstrip("/") == "/email-verification"
    )

    # A same-origin GET of /create-account/password can render a convincing
    # form while the server-side auth step is still the OTP step.  Submitting
    # that form then returns invalid_auth_step (HTTP 400), so it is not a safe
    # recovery.  Keep the profile at the real OTP page and classify the missing
    # password transition instead of guessing a new remote state.
    if refresh_attempted and is_email_verification_route and page_snapshot_observed and not page_mounted:
        return {
            "ok": False,
            "reason": "password_entry_recovery_exhausted",
            "waited_seconds": wait_seconds,
            "refresh_count": 1,
            "direct_navigation_count": 0,
            "page_state": "empty_shell",
            "url_path": parsed_url.path,
            "input_count": input_count,
            "button_count": button_count,
            "body_text_length": body_text_length,
            "last_reason": last_result.get("reason"),
            "candidates": candidates,
        }

    return {
        "ok": False,
        "reason": "password_entry_not_offered" if page_mounted else "password_entry_page_not_hydrated",
        "waited_seconds": wait_seconds,
        "refresh_count": int(refresh_attempted),
        "direct_navigation_count": 0,
        "page_state": "mounted" if page_mounted else "empty_shell",
        "url_path": parsed_url.path,
        "input_count": input_count,
        "button_count": button_count,
        "body_text_length": body_text_length,
        "last_reason": last_result.get("reason"),
        "candidates": candidates,
    }

def _fill_password_page_if_present(
    driver,
    email: str,
    timeout: int = 25,
    *,
    existing_password: str | None = None,
    on_password_submitted=None,
) -> str | None:
    """处理注册/登录密码页，并返回本次确认可用的 OpenAI 账号密码。

    首次注册时生成随机密码；如果本地已有 ``email_verification_pending`` 检查点，
    则使用当时保存的密码登录同一个 OpenAI 身份，继续完成邮箱验证。
    """
    end = time.time() + timeout
    last = {}
    auth_mode = _registration_auth_mode()
    switched_from_otp = False
    while time.time() < end:
        if _is_email_verification_page(driver):
            if existing_password:
                logger.info("%s 待验证账号已进入邮箱验证码页，沿用已保存登录密码：email=%s", _log_prefix(driver), email)
                return existing_password
            if auth_mode != 'password':
                return None
            if switched_from_otp:
                time.sleep(0.4)
                continue
            switched_from_otp = True
            switched = _click_signup_password_from_otp_if_present(driver, timeout=min(15, timeout))
            if not switched.get('ok'):
                raise RuntimeError(
                    f"密码注册模式下已进入验证码页，但无法切换到创建密码页：{switched} "
                    f"url={getattr(driver, 'current_url', '')}"
                )
            logger.info("%s 已从邮箱验证码页切换到创建密码页：email=%s detail=%s", _log_prefix(driver), email, switched)
            end = max(end, time.time() + min(10, max(3, timeout)))
            continue
        if _has_access_token(driver):
            return None
        last = _password_page_state(driver)
        is_signup_password = _is_signup_password_page(driver)
        is_login_password = _is_login_password_page(driver)
        if not (is_signup_password or is_login_password):
            time.sleep(0.5)
            continue
        passwordless = (
            _click_passwordless_signup_if_present(driver)
            if auth_mode == 'otp' and not existing_password
            else {"ok": False, "reason": "password_mode_or_saved_password"}
        )
        if passwordless.get('ok'):
            logger.info("%s 检测到 password 页，已点击一次性验证码入口：email=%s detail=%s", _log_prefix(driver), email, passwordless)
            wait_end = time.time() + 20
            while time.time() < wait_end:
                if _is_email_verification_page(driver):
                    logger.info("%s 一次性验证码入口已进入邮箱验证码页", _log_prefix(driver))
                    return None
                if _has_access_token(driver):
                    logger.info("%s 一次性验证码入口后已检测到登录态", _log_prefix(driver))
                    return None
                time.sleep(0.5)
            logger.info("%s 已点击一次性验证码入口，未立即检测到 OTP 页，交给后续 OTP 阶段继续处理", _log_prefix(driver))
            return None
        if is_login_password and not existing_password:
            logger.info("%s 当前是登录密码页但未找到一次性验证码入口，跳过密码填写并交给 OTP 阶段：state=%s", _log_prefix(driver), last)
            return None
        password = str(existing_password or _registration_password())
        logger.info(
            "%s 检测到%s，准备%s密码（%s 位）：email=%s",
            _log_prefix(driver),
            "log-in/password" if is_login_password else "create-account/password",
            "提交已保存" if existing_password else "设置",
            len(password),
            email,
        )
        result = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const input = [...document.querySelectorAll('input[type="password"],input[name*="password" i],input[autocomplete="new-password"]')]
          .find(visible);
        if (!input) return {ok:false, reason:'missing_password_input'};
        const form = input.closest('form');
        const scope = form || document;
        const buttons = [...scope.querySelectorAll('button,input[type="submit"]')]
          .filter(el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length) && !el.disabled && el.getAttribute('aria-disabled') !== 'true')
          .map((el, idx) => {
            const r = el.getBoundingClientRect();
            const ir = input.getBoundingClientRect();
            const type = String(el.getAttribute('type') || '').toLowerCase();
            const name = String(el.getAttribute('name') || '').toLowerCase();
            const attrs = [
              el.textContent, el.getAttribute('aria-label'), el.getAttribute('title'),
              el.getAttribute('data-testid'), el.getAttribute('data-dd-action-name'),
              type, name, el.getAttribute('value'),
            ].join(' ').replace(/\s+/g, ' ').trim().slice(0, 160);
            const normalized = attrs.toLowerCase();
            const otpOrAlternate = /otp|one[-_ ]?time|passwordless|一次性验证码|一次性驗證碼|intent=/.test(normalized)
              || name === 'intent';
            const primaryText = /continue|proceed|next|submit|sign up|create|続行|次へ|注册|创建|继续|確認|確認する/.test(normalized);
            const priority = otpOrAlternate ? 3 : type === 'submit' ? 0 : primaryText ? 1 : 2;
            return {
              el, idx, type, name, text: attrs,
              priority,
              below: r.top >= ir.bottom - 10,
              dist: Math.max(0, r.top - ir.bottom) + Math.abs((r.left+r.right-ir.left-ir.right)/2)/10,
            };
          })
          .filter(x => x.below)
          .sort((a,b) => a.priority - b.priority || a.dist - b.dist || a.idx - b.idx);
        if (!buttons.length) return {ok:false, reason:'missing_submit'};
        buttons[0].el.scrollIntoView({block:'center'});
        return {
          ok:true,
          reason:'password_targets',
          input,
          button: buttons[0].el,
          button_type: buttons[0].type,
          button_name: buttons[0].name,
          button_text: buttons[0].text,
        };
        """) or {}
        if not result.get('ok'):
            raise RuntimeError(f"密码页处理失败：{result} state={last}")
        _human_type_text(driver, result.get("input"), password, clear=True)
        human_delay("form", minimum=0.4, maximum=1.4)
        _human_click(driver, result.get("button"), label="password_submit")
        logger.info("%s 已填写并提交%s密码页", _log_prefix(driver), "登录" if is_login_password else "注册")
        if on_password_submitted is not None:
            on_password_submitted(password)
        # 密码页识别/切换已经消耗了外层 timeout 的一部分。表单提交属于新的远端请求，
        # 必须从点击成功后使用独立预算；否则慢代理下页面会在任务判失败后才迟到进入 OTP。
        transition_timeout = _password_transition_timeout_seconds()
        wait_end = time.time() + transition_timeout
        transition_probe = 0
        while time.time() < wait_end:
            _check_manual_stop()
            if _is_email_verification_page(driver):
                logger.info("%s 密码提交后已进入邮箱验证码页", _log_prefix(driver))
                return password
            if _has_access_token(driver):
                logger.info("%s 密码提交后已检测到登录态", _log_prefix(driver))
                return password
            # Poll the body only every two seconds.  This catches an explicit
            # upstream create error quickly without turning every 500 ms loop
            # into another full DOM snapshot over the remote browser bridge.
            if transition_probe % 4 == 0:
                post_submit_state = _password_page_state(driver)
                if _password_submit_error_marker(post_submit_state):
                    raise _PasswordTransitionTimeout(
                        "request_unknown: 密码提交后页面报告账号创建失败，远端结果待确认"
                    )
            transition_probe += 1
            if not (_is_signup_password_page(driver) or _is_login_password_page(driver)):
                return password
            time.sleep(0.5)
        stuck_state = _password_page_state(driver)
        raise _PasswordTransitionTimeout(
            f"request_unknown: 密码提交后等待 {int(transition_timeout)} 秒仍未确认远端结果，"
            f"页面仍停留在密码页：{_password_page_state_summary(stuck_state)}"
        )
    if auth_mode == "password" and not existing_password and not _has_access_token(driver):
        raise RuntimeError(
            "password_entry_not_offered: 密码模式要求创建账号密码，但认证跳转预算内未检测到密码页"
        )
    logger.info("%s 未检测到密码页，继续后续流程 last=%s", _log_prefix(driver), last)
    return None

def _accept_profile_consents(driver) -> int:
    """about-you/profile 下出现韩国/日本个人信息同意协议时，默认全部勾选。

    不依赖可见文字；优先处理 allCheckboxes，再处理所有必选 consent checkbox。
    """
    try:
        result = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled;
        const isChecked = el => el.checked === true || String(el.getAttribute('aria-checked') || el.closest('[role="checkbox"]')?.getAttribute('aria-checked') || '').toLowerCase() === 'true';
        const mark = el => {
          if (!el || isChecked(el)) return false;
          const label = el.closest('label');
          try {
            (label && visible(label) ? label : el).scrollIntoView({block:'center'});
            (label && visible(label) ? label : el).click();
          } catch (_) {}
          if (!isChecked(el)) {
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'checked')?.set;
            if (setter) setter.call(el, true); else el.checked = true;
            el.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            el.dispatchEvent(new Event('input', {bubbles:true}));
            el.dispatchEvent(new Event('change', {bubbles:true}));
          }
          return isChecked(el);
        };
        const all = [...document.querySelectorAll('input[type="checkbox"]')]
          .filter(el => visible(el) || visible(el.closest('label')));
        if (!all.length) return {count:0, names:[]};
        const byName = name => all.find(el => String(el.name || '').toLowerCase() === name.toLowerCase());
        const ordered = [];
        const add = el => { if (el && !ordered.includes(el)) ordered.push(el); };
        add(byName('allCheckboxes'));
        for (const name of ['personalInfoConsent', 'thirdPartyConsent', 'overseasTransferConsent']) add(byName(name));
        for (const el of all) {
          const n = String(el.name || '').toLowerCase();
          const id = String(el.id || '').toLowerCase();
          if (/consent|checkbox|agree|required|personal|third|overseas/.test(`${n} ${id}`)) add(el);
        }
        // about-you/profile 页面里的 checkbox 基本都是必选 consent；剩余可见 checkbox 也全部勾选。
        for (const el of all) add(el);
        const clicked = [];
        for (const el of ordered) {
          if (mark(el)) clicked.push(el.name || el.id || 'checkbox');
        }
        return {count: clicked.length, names: clicked};
        """) or {}
        count = int(result.get('count') or 0)
        if count:
            logger.info("%s 已勾选 about-you/profile 同意协议复选框：%s", _log_prefix(driver), result.get('names'))
        return count
    except Exception as exc:
        logger.debug('%s 勾选 profile consent 失败：%s', _log_prefix(driver), exc)
        return 0

def _complete_profile_page(driver, name: str, birthday: str, timeout: int = 45, on_submit=None) -> bool:
    """等待并完成姓名/生日页；若已经登录成功则返回 False，不把它当失败。"""
    end = time.time() + timeout
    y, m, d = birthday.split('-')
    from datetime import date
    today = date.today()
    age = today.year - int(y) - ((today.month, today.day) < (int(m), int(d)))
    last_snapshot = {}
    while time.time() < end:
        _check_manual_stop()
        time.sleep(1)
        if _has_access_token(driver):
            logger.info('%s 已检测到登录态，资料页可能已跳过', _log_prefix(driver))
            return False
        snap = _page_snapshot(driver)
        last_snapshot = snap
        if not _is_profile_like(snap):
            logger.info('%s 等待资料页中：url=%s', _log_prefix(driver), snap.get('url'))
            continue

        logger.info('%s 检测到资料页，开始填写姓名生日：url=%s inputs=%s', _log_prefix(driver), snap.get('url'), snap.get('inputs'))

        # 新版 about-you 在年龄变化时会重新渲染整个 form。现场确认先填姓名再填
        # 年龄会把姓名清空，因此必须先处理年龄/生日，最后再填姓名。
        birth_mode = _fill_birthday_or_age(driver, birthday, age)
        birth_ok = bool(birth_mode)
        if birth_ok:
            if birth_mode == 'age':
                logger.info("%s 已填写年龄字段：%s", _log_prefix(driver), age)
            else:
                logger.info("%s 已填写生日字段 mode=%s value=%s", _log_prefix(driver), birth_mode, birthday)

        name_ok = False
        # 常见单姓名字段
        for selectors in [
            ["input[name='name']", "input[name='fullName']", "input[name='full_name']", "input[autocomplete='name']"],
            ["input[placeholder*='Name']", "input[placeholder*='name']", "input[aria-label*='Name']", "input[aria-label*='name']"],
        ]:
            if _select_or_type(driver, selectors, name, timeout=3):
                logger.info("%s 已填写姓名字段：%s", _log_prefix(driver), name)
                name_ok = True
                break
        # 兼容 first/last 分开
        if not name_ok:
            parts = name.split(' ', 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else 'User'
            first_ok = _select_or_type(driver, ["input[name='firstName']", "input[name='first_name']", "input[placeholder*='First']", "input[aria-label*='First']"], first, timeout=2)
            last_ok = _select_or_type(driver, ["input[name='lastName']", "input[name='last_name']", "input[placeholder*='Last']", "input[aria-label*='Last']"], last, timeout=2)
            name_ok = first_ok or last_ok

        if not name_ok or not birth_ok:
            logger.warning('%s 资料页字段未填完整 name_ok=%s birth_ok=%s snapshot=%s', _log_prefix(driver), name_ok, birth_ok, snap)
            continue

        _accept_profile_consents(driver)
        human_delay('form')
        form_state = driver.execute_script(r"""
        const form = [...document.querySelectorAll('form')].find(el =>
          !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        if (!form) return {valid:false, reason:'form_missing'};
        const fields = [...form.querySelectorAll('input,select,textarea')].map(el => ({
          name: el.name || '', type: el.type || '', valid: el.checkValidity(),
          valuePresent: el.type === 'password' ? !!el.value : String(el.value || '').trim().length > 0,
          validationMessage: String(el.validationMessage || '').slice(0, 200),
        }));
        return {valid:form.checkValidity(), fields};
        """) or {}
        if not form_state.get('valid'):
            logger.warning('%s 资料页提交前表单校验未通过 state=%s', _log_prefix(driver), form_state)
            continue
        for _ in range(3):
            if callable(on_submit):
                try:
                    on_submit()
                except Exception:
                    logger.debug('%s 资料页提交前切换 post-auth 省流量规则失败', _log_prefix(driver), exc_info=True)
            if _click_if_enabled_submit(driver):
                logger.info('%s 已点击资料页提交按钮，等待 OAuth 跳转', _log_prefix(driver))
                submit_end = time.time() + 45
                while time.time() < submit_end:
                    time.sleep(0.5)
                    if _has_access_token(driver):
                        return True
                    submitted_snapshot = _page_snapshot(driver)
                    if not _is_profile_like(submitted_snapshot):
                        return True
                    rejection_marker = _profile_account_rejection_marker(driver)
                    if rejection_marker:
                        raise RuntimeError(
                            "account_create_rejected: 远端资料页明确拒绝创建账号；"
                            "原因属于条款/资格或风控限制"
                        )
                    errors = driver.execute_script(r"""
                    const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                    return [...document.querySelectorAll(
                      '.react-aria-FieldError,[slot="errorMessage"],[role="alert"],[aria-invalid="true"] + *'
                    )].filter(visible).map(el =>
                      String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim()
                    ).filter(Boolean).slice(0, 8);
                    """) or []
                    if errors:
                        raise RuntimeError(f"资料页提交被拒绝：{errors[:3]}")
                raise RuntimeError(
                    f"资料页点击提交后 45 秒仍未离开：{_page_snapshot(driver)}"
                )
            time.sleep(1)
        logger.warning('%s 找不到可点击的资料页提交按钮 snapshot=%s', _log_prefix(driver), _page_snapshot(driver))
    raise RuntimeError(f'等待/填写资料页超时，最后页面：{last_snapshot}')

def _probe_chatgpt_password_eligibility(driver, *, timeout: int = 12) -> bool | None:
    """Read the authenticated ChatGPT password-setup capability.

    The settings SPA can render the normal home shell even when the backend
    explicitly disables adding a password. Use the session's access token as
    the browser frontend does, and treat transport/auth/schema failures as
    unknown so this probe never blocks a potentially supported account.
    """
    try:
        result = driver.execute_async_script(
            r"""
            const done = arguments[arguments.length - 1];
            const timeoutMs = Number(arguments[0]) || 12000;
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), timeoutMs);
            (async () => {
              try {
                const sessionResponse = await fetch('/api/auth/session', {
                  credentials: 'include',
                  headers: {Accept: 'application/json'},
                  signal: controller.signal,
                });
                const session = await sessionResponse.json().catch(() => ({}));
                const accessToken = String(session?.accessToken || '').trim();
                if (!accessToken) {
                  done({status: sessionResponse.status, eligible: null, reason: 'session_missing'});
                  return;
                }
                const response = await fetch('/backend-api/accounts/change_password/eligibility', {
                  credentials: 'include',
                  headers: {Accept: 'application/json', Authorization: `Bearer ${accessToken}`},
                  signal: controller.signal,
                });
                const payload = await response.json().catch(() => ({}));
                const eligible = payload && typeof payload.eligible === 'boolean'
                  ? payload.eligible : null;
                done({status: response.status, eligible});
              } catch (error) {
                done({status: 0, eligible: null, reason: String(error?.name || 'probe_error')});
              } finally {
                clearTimeout(timer);
              }
            })();
            """,
            max(1, int(timeout)) * 1000,
        )
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    eligible = result.get("eligible")
    if eligible is True:
        return True
    if eligible is False and int(result.get("status") or 0) == 200:
        return False
    return None

def set_roxy_login_password(
    driver,
    email: str,
    password: str,
    *,
    timeout: int = 75,
    on_password_submitted=None,
) -> str:
    """在已登录的 ChatGPT 账号设置中补充账号密码。

    无密码账号从“账户安全与登录”里的密码“添加”入口进入新密码页；
    Security 页上的其它密码修改入口可能会要求当前密码，不能用于这类账号。
    """
    normalized = str(password or "").strip()
    if not normalized:
        raise ValueError("账号密码不能为空")

    eligibility = _probe_chatgpt_password_eligibility(driver)
    if eligibility is False:
        # This endpoint describes the backend's password-change capability,
        # but the passwordless account path is the Security -> Add flow. The
        # visible browser UI is the source of truth for that flow; a false
        # probe must not prevent us from trying it.
        logger.warning(
            "%s ChatGPT 密码资格接口返回 eligible=false，仅作参考，继续尝试安全设置页添加密码",
            _log_prefix(driver),
        )

    _safe_get(
        driver,
        _CHATGPT_PASSWORD_SETTINGS_URL,
        timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
        attempts=2,
        accept_hosts=("chatgpt.com",),
    )
    _page_warmup(driver, reason="chatgpt_password_settings")
    settings_shell_refreshes = int(
        _refresh_chatgpt_settings_shell_if_needed(driver, reason="chatgpt_password_settings")
    )
    end = time.time() + max(10, int(timeout))
    password_inputs = []
    action = None
    settings_action = None
    security_action = None
    profile_action = None
    settings_clicks = 0
    security_clicks = 0
    profile_clicks = 0
    settings_navigation_reveals = 0
    reauth_attempts = 0
    password_setting_fallback_clicks = 0
    last_url = ""
    last_password_controls = []
    last_password_lines = []
    last_page_meta = {}

    def _is_current_password(field) -> bool:
        autocomplete = str(field.get_attribute("autocomplete") or "").lower()
        name = str(field.get_attribute("name") or "").lower()
        field_id = str(field.get_attribute("id") or "").lower()
        return autocomplete == "current-password" or any(
            marker in f"{name} {field_id}" for marker in ("current", "old", "existing")
        )

    while time.time() < end:
        _check_manual_stop()
        if _dismiss_chatgpt_pricing_modal(driver):
            continue
        if _dismiss_single_action_dialog(driver):
            time.sleep(1.0)
            continue
        try:
            current_url = str(driver.current_url or "").lower()
        except Exception:
            current_url = ""
        if "email-verification" in current_url:
            if reauth_attempts >= 1:
                raise RuntimeError("设置页邮箱重认证重复出现，已停止避免重复提交")
            reauth_attempts += 1
            _complete_settings_email_reauth(driver, email)
            end = max(end, time.time() + 45)
            continue
        state = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const label = el => [el.innerText, el.textContent, el.getAttribute('aria-label'),
          el.getAttribute('title'), el.getAttribute('data-testid'), el.getAttribute('name'),
          el.getAttribute('value')].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
        const testId = el => String(el.getAttribute('data-testid') || '').trim();
        const passwordMarker = /password|密码|パスワード|비밀번호|mot\s+de\s+passe|contraseña|senha|passwort|пароль/i;
        const passwordSettingTestId = /(?:^|[-_:])password[-_:]?setting(?:$|[-_:])/i;
        const addPassword = /(?:add|set|create)\s+.{0,30}password|password\s+.{0,30}(?:add|set|create)|添加密码|设置密码|新增密码|パスワード.{0,30}(?:追加|設定)|(?:追加|設定).{0,30}パスワード|비밀번호.{0,30}(?:추가|설정)|(?:추가|설정).{0,30}비밀번호|(?:ajouter|définir|configurer).{0,30}(?:mot\s+de\s+passe|password)|(?:mot\s+de\s+passe|password).{0,30}(?:ajouter|définir|configurer)|(?:agregar|añadir|establecer|configurar).{0,30}(?:contraseña|password)|(?:contraseña|password).{0,30}(?:agregar|añadir|establecer|configurar)|(?:adicionar|definir|configurar).{0,30}(?:senha|password)|(?:senha|password).{0,30}(?:adicionar|definir|configurar)|(?:hinzufügen|festlegen|einstellen).{0,30}(?:passwort|password)|(?:passwort|password).{0,30}(?:hinzufügen|festlegen|einstellen)|(?:добавить|установить|настроить).{0,30}(?:пароль|password)|(?:пароль|password).{0,30}(?:добавить|установить|настроить)/i;
        const addAction = /^(?:add|set|create|添加|设置|新增|追加|設定|추가|설정|ajouter|définir|configurer|agregar|añadir|establecer|adicionar|hinzufügen|festlegen|einstellen|добавить|установить|настроить)$/i;
        const negative = /forgot|reset|log.?in|sign.?in|one.?time|otp|忘记|重置|一次性|验证码|パスワードを忘れた|リセット|ログイン|サインイン|ワンタイム|認証コード|비밀번호.?찾기|로그인/i;
        const buttons = [...document.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="tab"]')].filter(visible);
        const settingsMarker = /settings|设置|設定|설정|paramètres|configurações|definições|definicoes/i;
        const securityMarker = /security|安全|セキュリティ|보안|sécurité|seguridad|segurança|sicherheit|безопас/i;
        const profileMarker = /profile|account|avatar|user|账户|账号|个人资料|プロフィール|アカウント/i;
        const href = el => String(el.getAttribute('href') || '');
        const profileAction = buttons.filter(el =>
          el.getAttribute('data-testid') === 'accounts-profile-button'
        ).find(el => label(el).length > 20)
        || [...buttons].reverse().find(el => el.getAttribute('data-testid') === 'accounts-profile-button')
        || buttons.find(el =>
          profileMarker.test(label(el)) && !settingsMarker.test(label(el))
            && !securityMarker.test(label(el))
            && !/new.?chat|chat|conversation|logout|退出/i.test(label(el))
        );
        const settingsAction = buttons.find(el => el.getAttribute('data-testid') === 'settings-menu-item')
          || buttons.find(el => settingsMarker.test(label(el)) || /#settings\/(?:account|general)|\/settings\/(?:account|general)/i.test(href(el)));
        const securityAction = buttons.find(el => el.getAttribute('data-testid') === 'security-tab')
          || buttons.find(el => securityMarker.test(label(el)) || /#settings\/security|\/settings\/security/i.test(href(el)));
        const isClickable = el => !!el && el.matches('button,a,[role="button"],[role="menuitem"],[role="tab"]');
        const isPasswordAction = el => {
          const text = label(el);
          return !negative.test(text) && (addPassword.test(text) || (addAction.test(text) && text.length <= 120));
        };
        const passwordSettingNode = [...document.querySelectorAll('[data-testid]')]
          .filter(visible).find(el => passwordSettingTestId.test(testId(el)));
        const closestClickable = el => el?.closest?.('button,a,[role="button"],[role="menuitem"],[role="tab"]') || el;
        const passwordSettingTarget = root => {
          if (!root) return null;
          if (isClickable(root)) return root;
          const descendants = [...root.querySelectorAll('button,a,[role="button"],[role="menuitem"],[role="tab"]')]
            .filter(visible);
          const clickableAction = descendants.find(isPasswordAction);
          if (clickableAction) return clickableAction;
          const textAction = [...root.querySelectorAll('*')].filter(visible).find(isPasswordAction);
          return closestClickable(textAction) || root;
        };
        let target = passwordSettingTarget(passwordSettingNode);
        if (!target) target = buttons.find(el => addPassword.test(label(el)) && !negative.test(label(el)));
        if (!target) {
          const roots = [...document.querySelectorAll('section,article,li,div')]
            .filter(el => visible(el) && passwordMarker.test(label(el)) && label(el).length <= 500)
            .sort((a, b) => label(a).length - label(b).length);
          for (const root of roots) {
            const candidate = [...root.querySelectorAll('button,a,[role="button"]')]
              .filter(visible).find(el => {
                const text = label(el);
                return !negative.test(text) && (addPassword.test(text) || (addAction.test(text) && text.length <= 120));
              });
            if (candidate) { target = candidate; break; }
          }
        }
        const inputs = [...document.querySelectorAll('input[type="password"],input[autocomplete*="password" i],input[name*="password" i]')]
          .filter(visible);
        const lines = (document.body?.innerText || '').split(/\n+/).map(line => line.replace(/\s+/g, ' ').trim())
          .filter(line => line && (passwordMarker.test(line) || addAction.test(line)))
          .slice(0, 20).map(line => line.slice(0, 240));
        const controls = buttons.map(label)
          .filter(text => text && (passwordMarker.test(text) || addAction.test(text)))
          .slice(0, 30);
        const pageMeta = {
          ready_state: String(document.readyState || ''),
          title: String(document.title || '').slice(0, 120),
          body_text_length: String(document.body?.innerText || '').length,
          html_length: String(document.documentElement?.outerHTML || '').length,
          testids: [...document.querySelectorAll('[data-testid]')].filter(visible)
            .map(el => String(el.getAttribute('data-testid') || '').slice(0, 120)).filter(Boolean).slice(0, 30),
          aria_labels: [...document.querySelectorAll('[aria-label]')].filter(visible)
            .map(el => String(el.getAttribute('aria-label') || '').slice(0, 120)).filter(Boolean).slice(0, 30),
        };
        return {
          action: target,
          inputs,
          url: String(location.href || ''),
          password_controls: controls,
          password_lines: lines,
          profile_action: profileAction,
          settings_action: settingsAction,
          security_action: securityAction,
          page_meta: JSON.stringify(pageMeta),
        };
        """) or {}
        password_inputs = list(state.get("inputs") or [])
        action = state.get("action")
        profile_action = state.get("profile_action")
        settings_action = state.get("settings_action")
        security_action = state.get("security_action")
        last_url = str(state.get("url") or "")
        last_password_controls = [str(value)[:120] for value in (state.get("password_controls") or []) if value]
        last_password_lines = [str(value)[:240] for value in (state.get("password_lines") or []) if value]
        last_page_meta = str(state.get("page_meta") or "")[:1200]
        new_inputs = [field for field in password_inputs if not _is_current_password(field)]
        if new_inputs:
            break
        if action is None:
            if (
                password_setting_fallback_clicks < 2
                and (last_password_controls or last_password_lines)
                and _click_password_setting_fallback(driver)
            ):
                password_setting_fallback_clicks += 1
                time.sleep(0.8)
                continue
        if action is None and settings_action is None and security_action is None and profile_action is None:
            if (
                settings_shell_refreshes < 2
                and not last_password_controls
                and not last_password_lines
                and _refresh_chatgpt_settings_shell_if_needed(
                    driver, reason="chatgpt_password_settings_empty_shell"
                )
            ):
                settings_shell_refreshes += 1
                time.sleep(0.8)
                continue
        if (
            security_action is None
            and settings_clicks >= 1
            and settings_navigation_reveals < 5
            and _reveal_chatgpt_settings_navigation(driver)
        ):
            settings_navigation_reveals += 1
            time.sleep(0.8)
            continue
        if action is not None:
            _click_chatgpt_settings_control(driver, action, label="account_password_settings")
            action = None
            time.sleep(0.8)
        elif security_action is not None and security_clicks < 1:
            _click_chatgpt_settings_control(driver, security_action, label="chatgpt_security_navigation")
            security_clicks += 1
            time.sleep(1.2)
        elif settings_action is not None and settings_clicks < 1:
            _click_chatgpt_settings_control(driver, settings_action, label="chatgpt_settings_navigation")
            settings_clicks += 1
            time.sleep(1.2)
        elif profile_action is not None and profile_clicks < 1:
            _click_chatgpt_settings_control(driver, profile_action, label="chatgpt_profile_menu")
            profile_clicks += 1
            time.sleep(0.8)
        else:
            time.sleep(0.5)

    if not password_inputs:
        diagnostic = (
            f"url={last_url[:180]} controls={last_password_controls[:12]} "
            f"text={last_password_lines[:12]} settings_clicks={settings_clicks} meta={last_page_meta}"
        )
        if _settings_page_not_ready(
            url=last_url,
            password_controls=last_password_controls,
            password_lines=last_password_lines,
            page_meta=last_page_meta,
            security_action=security_action,
        ):
            logger.warning(
                "%s 账号设置页尚未稳定或添加密码入口未打开，标记为可重试：%s",
                _log_prefix(driver), diagnostic,
            )
            raise PasswordSetupNotReadyError(
                f"账号设置页尚未稳定或添加密码入口未打开，页面诊断：{diagnostic}"
            )
        logger.warning("%s 账号设置密码入口诊断：%s", _log_prefix(driver), diagnostic)
        raise RuntimeError(f"账号设置中未找到“Add password/设置密码”入口；页面诊断：{diagnostic}")

    new_inputs = []
    for field in password_inputs:
        if _is_current_password(field):
            continue
        new_inputs.append(field)
    if not new_inputs:
        diagnostic = (
            f"url={last_url[:180]} controls={last_password_controls[:12]} "
            f"text={last_password_lines[:12]} settings_clicks={settings_clicks} meta={last_page_meta}"
        )
        logger.warning("%s 账号设置密码表单诊断：%s", _log_prefix(driver), diagnostic)
        raise RuntimeError(
            f"账号设置只提供当前密码输入框，未进入“Add password/设置密码”流程；页面诊断：{diagnostic}"
        )

    for submit_attempt in range(2):
        try:
            for field in new_inputs:
                _human_type_text(driver, field, normalized, clear=True)
            submit = _button_after_input(driver, new_inputs[-1])
            if submit is not None:
                _human_click(driver, submit, label="account_password_submit")
            else:
                submitted = bool(driver.execute_script(r"""
                const input = arguments[0];
                const form = input?.closest('form');
                if (!form) return false;
                if (typeof form.requestSubmit === 'function') form.requestSubmit();
                else form.submit();
                return true;
                """, new_inputs[-1]))
                if not submitted:
                    raise RuntimeError("账号密码设置页缺少提交按钮")
            break
        except Exception as exc:
            if submit_attempt == 0 and _is_stale_element_error(exc):
                logger.warning(
                    "%s 新增密码表单已被页面重绘，重新获取控件后重试一次：email=%s",
                    _log_prefix(driver), email,
                )
                time.sleep(random.uniform(0.2, 0.6))
                refreshed_inputs = _visible_new_password_inputs(driver)
                if refreshed_inputs:
                    new_inputs = refreshed_inputs
                    continue
            raise

    # 表单提交后远端结果可能需要较长时间才反映到 DOM；先把密码交给
    # 调用方写入恢复检查点，避免后续诊断脚本/网络异常导致“远端已设置、
    # 本地没有保存密码”。这和注册流程的提交后检查点策略保持一致。
    if on_password_submitted is not None:
        on_password_submitted(normalized)

    end = time.time() + max(8, int(timeout))
    last_text = ""
    while time.time() < end:
        _check_manual_stop()
        state = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const inputs = [...document.querySelectorAll('input[type="password"],input[autocomplete*="password" i],input[name*="password" i]')].filter(visible);
        // Do not use [class*="error"] here. The ChatGPT app has unrelated
        // loading/streaming classes whose text can be localized as “思考”; the
        // old broad selector treated that normal state as a password failure.
        const errors = [...document.querySelectorAll(
          '[role="alert"],[aria-live="assertive"],[aria-invalid="true"],'
          + '[data-testid*="error" i],[data-test-id*="error" i],[data-state="error"]'
        )].filter(visible).map(el => (el.innerText || el.textContent || '')
          .replace(/\\s+/g, ' ').trim()).filter(Boolean);
        return {inputs, errors, body: (document.body?.innerText || '').replace(/\\s+/g, ' ').slice(0, 1200)};
        """) or {}
        last_text = "; ".join((state.get("errors") or [])[:3]) or str(state.get("body") or "")[-400:]
        if state.get("errors"):
            raise RuntimeError(f"账号密码设置失败：{last_text}")
        if not state.get("inputs"):
            logger.info("%s 已补充 ChatGPT 账号密码：email=%s length=%s", _log_prefix(driver), email, len(normalized))
            return normalized
        time.sleep(0.5)
    raise RuntimeError(f"提交账号密码后页面未确认完成：{last_text[:300]}")


install_dispatches(globals(), (
    "human_delay", "_generate_roxy_password", "_registration_password",
    "_registration_auth_mode", "_password_transition_timeout_seconds",
    "_PasswordTransitionTimeout", "_click_passwordless_signup_if_present",
    "_click_signup_password_from_otp_if_present", "_fill_password_page_if_present",
    "_accept_profile_consents", "_complete_profile_page",
    "_probe_chatgpt_password_eligibility", "set_roxy_login_password",
))

__all__ = [
    "human_delay", "_generate_roxy_password", "_registration_password",
    "_registration_auth_mode", "_password_transition_timeout_seconds",
    "_PasswordTransitionTimeout", "_click_passwordless_signup_if_present",
    "_click_signup_password_from_otp_if_present", "_fill_password_page_if_present",
    "_accept_profile_consents", "_complete_profile_page",
    "_probe_chatgpt_password_eligibility", "set_roxy_login_password",
]
