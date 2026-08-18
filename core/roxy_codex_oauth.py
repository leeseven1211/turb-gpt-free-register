# -*- coding: utf-8 -*-
"""通过 RoxyBrowser 指纹浏览器执行 Codex OAuth 授权。"""
from __future__ import annotations

import logging
import inspect
import json
import random
import time
from contextvars import ContextVar
from urllib.parse import urlparse

from config import roxybrowser as _roxy_cfg
from core.email_provider import wait_for_otp
from core.humanize import delay as human_delay
from core import sms_provider
from core.openai_auth import AccountUnusableError, detect_account_unusable_response_body
from core.roxybrowser_client import RoxyBrowserClient
from core.roxy_registration import (
    _build_driver,
    _center_browser_window,
    _click_any,
    _click_continue,
    _find_any,
    _maybe_accept,
    _type_any,
    _type_email_address,
    _submit_email_step,
    _click_email_entry_option,
    _type_otp,
    _clear_otp_inputs,
    _email_otp_page_state,
    _is_email_verification_page,
    _is_login_password_page,
    _click_passwordless_signup_if_present,
    _human_click,
    _human_type_text,
)

_base_logger = logging.getLogger(__name__)
_CODEX_BROWSER_KIND: ContextVar[str] = ContextVar("codex_browser_kind", default="Roxy")


def _codex_prefix() -> str:
    return f"[Codex][{_CODEX_BROWSER_KIND.get()}]"


def _codex_driver_name() -> str:
    return _CODEX_BROWSER_KIND.get()


def _detect_browser_kind(opened=None) -> str:
    try:
        raw = getattr(opened, "raw", None) or {}
        if isinstance(raw, dict) and str(raw.get("driver") or "").lower().startswith("cloak"):
            return "Cloak"
    except Exception:
        pass
    return "Roxy"


class _CodexLogger:
    """把流程内部统一占位前缀替换成当前真实浏览器类型。"""
    def __init__(self, base):
        self._base = base

    def _msg(self, msg):
        return str(msg).replace("[Codex][Browser]", _codex_prefix())

    def debug(self, msg, *args, **kwargs):
        return self._base.debug(self._msg(msg), *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        return self._base.info(self._msg(msg), *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        return self._base.warning(self._msg(msg), *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        return self._base.error(self._msg(msg), *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        return self._base.exception(self._msg(msg), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._base, name)


logger = _CodexLogger(_base_logger)


def _is_callback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return (
        parsed.scheme in ("http", "https")
        and parsed.hostname in ("localhost", "127.0.0.1")
        and parsed.port == 1455
        and parsed.path == "/auth/callback"
    )


def _extract_callback_url_from_page(driver) -> str:
    """从当前页面提取 OAuth callback URL。

    浏览器跳转到 http://localhost:1455/auth/callback?... 时，本地没有服务监听会显示
    chrome-error://chromewebdata/。地址栏可能变成 chrome-error，但 Chromium 的
    performance navigation entry 仍保留原始 callback URL，可直接提取后提交 CPA。
    """
    try:
        current = str(driver.current_url or "")
        if _is_callback_url(current):
            return current
    except Exception:
        pass
    try:
        urls = driver.execute_script(r"""
        const out = [];
        const push = v => { if (v && typeof v === 'string') out.push(v); };
        try { push(location.href); } catch (e) {}
        try { push(document.URL); } catch (e) {}
        try { push(document.documentURI); } catch (e) {}
        try { for (const e of performance.getEntriesByType('navigation')) push(e.name); } catch (e) {}
        try { for (const e of performance.getEntries()) push(e.name); } catch (e) {}
        return [...new Set(out)];
        """) or []
        for url in urls:
            if _is_callback_url(str(url)):
                logger.info("[Codex][Browser] 已从浏览器性能记录提取 callback URL：%s", str(url)[:160])
                return str(url)
    except Exception as exc:
        logger.debug("[Codex][Browser] 从页面提取 callback URL 失败：%s", exc)
    return ""


def _extract_callback_url_from_any_window(driver) -> str:
    found = _extract_callback_url_from_page(driver)
    if found:
        return found
    original_handle = None
    try:
        original_handle = driver.current_window_handle
    except Exception:
        pass
    try:
        for handle in list(getattr(driver, "window_handles", []) or []):
            try:
                driver.switch_to.window(handle)
                found = _extract_callback_url_from_page(driver)
                if found:
                    return found
            except Exception:
                continue
    except Exception:
        pass
    if original_handle is not None:
        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass
    return ""


def _wait_for_callback(driver, timeout: int | None = None) -> str:
    end = time.time() + (timeout or int(_roxy_cfg.ROXY_CODEX_CALLBACK_TIMEOUT))
    last_url = ""
    while time.time() < end:
        try:
            current = str(driver.current_url or "")
            if current != last_url:
                logger.debug("[Codex][Browser] 当前 URL: %s", current)
                last_url = current
            callback = _extract_callback_url_from_any_window(driver)
            if callback:
                return callback
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"等待 Codex callback 超时，最后 URL={last_url}")


def _click_if_present(driver, selectors: list[str], timeout: int = 3) -> bool:
    try:
        _click_any(driver, selectors, timeout=timeout)
        return True
    except Exception:
        return False


def _account_login_credentials(email: str) -> tuple[str, str]:
    """Return the saved OpenAI password and TOTP secret without logging either value."""
    try:
        from core import db

        account = db.get_account_by_email(email) or {}
    except Exception:
        logger.debug("[Codex][Browser] 读取账号登录凭据失败", exc_info=True)
        return "", ""

    raw_extra = account.get("extra_json") or {}
    if isinstance(raw_extra, str):
        try:
            raw_extra = json.loads(raw_extra)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_extra = {}
    password = str(raw_extra.get("registration_password") or "").strip() if isinstance(raw_extra, dict) else ""
    totp_secret = str(account.get("totp_secret") or "").strip()
    return password, totp_secret


def _login_challenge_state(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const inputs = [...document.querySelectorAll('input')].filter(visible).map(el => ({
          type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
          autocomplete: el.getAttribute('autocomplete') || '', inputmode: el.getAttribute('inputmode') || '',
          ariaInvalid: el.getAttribute('aria-invalid') || ''
        }));
        const buttons = [...document.querySelectorAll('button,input[type="submit"]')].filter(visible).map(el => {
          const r = el.getBoundingClientRect();
          return {
            tag: el.tagName, type: el.getAttribute('type') || '', name: el.getAttribute('name') || '',
            value: el.getAttribute('value') || '', aria: el.getAttribute('aria-label') || '',
            testid: el.getAttribute('data-testid') || '', action: el.getAttribute('data-dd-action-name') || '',
            text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100),
            top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right)
          };
        });
        const errors = [...document.querySelectorAll('.react-aria-FieldError,[slot="errorMessage"],[role="alert"],[aria-invalid="true"] + *,[class*="error"]')]
          .filter(visible).map(el => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
        return {
          url: location.href,
          inputs,
          buttons,
          errors,
          text: (document.body?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 1200)
        };
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, "current_url", ""), "error": f"{type(exc).__name__}: {exc}"}


def _is_totp_login_page(driver, state: dict | None = None) -> bool:
    state = state or _login_challenge_state(driver)
    url = str(state.get("url") or "").lower()
    if "email-verification" in url:
        return False
    inputs = state.get("inputs") or []
    attrs = " ".join(
        " ".join(str(item.get(key) or "") for key in ("type", "name", "id", "autocomplete", "inputmode"))
        for item in inputs
    ).lower()
    has_code_input = any(marker in attrs for marker in ("one-time-code", "otp", "code", "numeric", "tel"))
    has_password_input = any(
        str(item.get("type") or "").lower() == "password"
        or str(item.get("autocomplete") or "").lower() == "current-password"
        or "password" in str(item.get("name") or "").lower()
        for item in inputs
    )
    if has_password_input:
        return False
    if "totp" in attrs or any(marker in url for marker in ("/mfa", "/totp", "/authenticator")):
        return has_code_input
    text = str(state.get("text") or "").lower()
    authenticator_markers = (
        "authenticator app", "authentication app", "two-factor authentication",
        "身份验证器", "身份驗證器", "验证器应用", "驗證器應用",
        "認証アプリ", "認証システム", "인증 앱",
    )
    if has_code_input and any(marker in text for marker in authenticator_markers):
        return True
    # OpenAI occasionally swaps the password form for the Authenticator challenge
    # without changing /log-in/password. A code input with no password input on that
    # stale URL is the post-password TOTP step, not an email OTP request.
    return has_code_input and "/log-in/password" in url


def _login_password_targets(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const input = [...document.querySelectorAll('input[type="password"],input[autocomplete="current-password"],input[name*="password" i]')]
          .find(visible);
        if (!input) return {ok:false, reason:'missing_password_input'};
        const form = input.closest('form');
        const buttons = [...(form || document).querySelectorAll('button,input[type="submit"]')]
          .filter(el => visible(el) && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true');
        const submitter = buttons.find(el =>
          String(el.getAttribute('name') || '').toLowerCase() === 'intent'
          && String(el.getAttribute('value') || '').toLowerCase() === 'validate')
          || buttons.find(el => String(el.getAttribute('data-dd-action-name') || '').toLowerCase() === 'continue')
          || buttons.find(el => String(el.getAttribute('type') || '').toLowerCase() === 'submit');
        if (!form || !submitter) return {ok:false, reason:'missing_password_form_submitter'};
        return {ok:true, input, submitter};
        """) or {}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def _submit_saved_login_password(driver, email: str, password: str) -> None:
    if not password:
        raise RuntimeError("账号已进入登录密码页，但本地没有保存注册密码，已在手机号验证前停止")
    targets = _login_password_targets(driver)
    password_input = targets.pop("input", None)
    submitter = targets.pop("submitter", None)
    if not targets.get("ok") or password_input is None or submitter is None:
        raise RuntimeError(f"登录密码页控件识别失败：{targets}")
    _human_type_text(driver, password_input, password, clear=True)
    human_delay("form", minimum=0.4, maximum=1.2)
    submitted = bool(driver.execute_script(r"""
    const input = arguments[0], submitter = arguments[1];
    const form = input?.closest('form');
    if (!form || !submitter) return false;
    if (typeof form.requestSubmit === 'function') form.requestSubmit(submitter);
    else form.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}));
    return true;
    """, password_input, submitter))
    if not submitted:
        password_input.send_keys("\ue007")
    logger.info(
        "[Codex][Browser] 已使用本地保存的注册密码提交登录：email=%s method=%s",
        email,
        "form_request_submit" if submitted else "password_enter",
    )


def _submit_saved_login_totp(driver, email: str, totp_secret: str) -> None:
    if not totp_secret:
        raise RuntimeError("登录要求 Authenticator 验证，但本地没有 TOTP 密钥，已在手机号验证前停止")
    import pyotp

    remaining = 30 - (int(time.time()) % 30)
    if remaining < 6:
        time.sleep(remaining + 1)
    _type_otp(driver, pyotp.TOTP(totp_secret).now(), timeout=15)
    if not _click_if_present(driver, [
        "button[type='submit']",
        "input[type='submit']",
        "//button[contains(., 'Continue')]",
        "//button[contains(., '继续')]",
        "//button[contains(., 'Verify')]",
        "//button[contains(., '验证')]",
        "//button[contains(., '確認')]",
    ], timeout=8):
        raise RuntimeError("Authenticator 验证页缺少提交按钮")
    logger.info("[Codex][Browser] 已使用本地 TOTP 提交 Authenticator 登录：email=%s", email)


def _is_login_advanced(driver, state: dict | None = None) -> bool:
    state = state or _login_challenge_state(driver)
    url = str(state.get("url") or "").lower()
    if _is_callback_url(url):
        return True
    if any(marker in url for marker in ("/add-phone", "/workspace", "/consent")):
        return True
    if url.startswith("https://chatgpt.com/") and "/auth/login" not in url:
        return True
    if "/oauth/authorize" in url and not state.get("inputs"):
        return True
    return False


def _complete_login_challenge_after_email(
    driver,
    email: str,
    password: str,
    totp_secret: str,
    *,
    timeout: int = 45,
) -> str:
    """Resolve password/TOTP challenges and return ``email_otp`` or ``advanced``."""
    end = time.time() + max(5, int(timeout))
    password_submitted_at = 0.0
    totp_submitted_at = 0.0
    passwordless_clicked = False
    last_state: dict = {}
    last_url = ""
    while time.time() < end:
        state = _login_challenge_state(driver)
        last_state = state
        url = str(state.get("url") or "")
        if url != last_url:
            logger.info("[Codex][Browser] 邮箱提交后登录分支：url=%s", url or "-")
            last_url = url

        # TOTP may be rendered in-place while the stale URL still ends in
        # /log-in/password, so inspect the live controls before trusting the URL.
        if _is_totp_login_page(driver, state):
            if totp_submitted_at:
                if state.get("errors") or any(
                    str(item.get("ariaInvalid") or "").lower() == "true" for item in (state.get("inputs") or [])
                ):
                    raise RuntimeError(f"本地 TOTP 未通过页面校验：errors={(state.get('errors') or [])[:3]}")
                if time.time() - totp_submitted_at > 20:
                    raise RuntimeError("提交本地 TOTP 后页面 20 秒未继续，已在手机号验证前停止")
                time.sleep(0.5)
                continue
            _submit_saved_login_totp(driver, email, totp_secret)
            totp_submitted_at = time.time()
            end = max(end, totp_submitted_at + 25)
            human_delay("form")
            continue

        if _is_login_password_page(driver):
            if password_submitted_at:
                if state.get("errors") or any(
                    str(item.get("ariaInvalid") or "").lower() == "true" for item in (state.get("inputs") or [])
                ):
                    raise RuntimeError(f"本地保存的注册密码未通过页面校验：errors={(state.get('errors') or [])[:3]}")
                if time.time() - password_submitted_at > 20:
                    safe_state = {
                        "url": state.get("url"),
                        "inputs": state.get("inputs"),
                        "buttons": state.get("buttons"),
                        "errors": (state.get("errors") or [])[:3],
                        "text": str(state.get("text") or "")[:400],
                    }
                    logger.warning("[Codex][Browser] 密码提交未推进页面诊断（不含输入值）：%s", safe_state)
                    raise RuntimeError(
                        f"提交本地注册密码后页面 20 秒未继续，已在手机号验证前停止：state={safe_state}"
                    )
                time.sleep(0.5)
                continue
            if password:
                _submit_saved_login_password(driver, email, password)
                password_submitted_at = time.time()
                # Slow OpenAI edges can consume nearly the entire outer budget
                # before the password page appears. Give this submitted step its
                # own bounded settle window.
                end = max(end, password_submitted_at + 25)
                human_delay("form")
                continue
            if not passwordless_clicked:
                result = _click_passwordless_signup_if_present(driver)
                if result.get("ok"):
                    passwordless_clicked = True
                    logger.info("[Codex][Browser] 本地无注册密码，已切换到邮箱一次性验证码：email=%s", email)
                    human_delay("form")
                    continue
            raise RuntimeError("账号进入登录密码页，本地无注册密码且页面无邮箱验证码入口，已在手机号验证前停止")

        if _is_email_verification_page(driver):
            logger.info("[Codex][Browser] 页面明确进入邮箱验证码分支：email=%s", email)
            return "email_otp"
        if _is_login_advanced(driver, state):
            return "advanced"
        time.sleep(0.5)

    safe_state = {
        "url": last_state.get("url"),
        "inputs": last_state.get("inputs"),
        "errors": (last_state.get("errors") or [])[:3],
    }
    raise RuntimeError(f"邮箱提交后未识别到密码、TOTP 或邮箱验证码分支：state={safe_state}")


def _maybe_click_passwordless_after_email(driver, email: str, timeout: int = 18) -> None:
    """
    Codex OAuth 提交邮箱后也可能跳到 /log-in/password 或 /create-account/password。
    优先点击“使用一次性验证码/one-time code”入口，进入邮箱验证码页。
    """
    end = time.time() + timeout
    last_url = ""
    clicked = False
    while time.time() < end:
        try:
            if _is_email_verification_page(driver):
                if clicked:
                    logger.info("[Codex][Browser] 一次性验证码入口已进入邮箱验证码页")
                return
            url = str(driver.current_url or "")
            if url != last_url:
                logger.info("[Codex][Browser] 提交邮箱后检测密码/OTP 跳转：url=%s", url or "-")
                last_url = url
            lower = url.lower()
            if any(x in lower for x in ("phone", "workspace", "consent", "authorize", "localhost:1455")):
                return
            if "/password" in lower or "auth.openai.com" in lower:
                result = _click_passwordless_signup_if_present(driver)
                if result.get("ok"):
                    clicked = True
                    logger.info("[Codex][Browser] 已点击一次性验证码入口：email=%s detail=%s", email, result)
                    human_delay("form")
                    continue
        except Exception as exc:
            logger.debug("[Codex][Browser] 密码页一次性验证码入口探测失败：%s", str(exc)[:140])
        time.sleep(0.5)
    if clicked:
        logger.info("[Codex][Browser] 已点击一次性验证码入口，未立即检测到 OTP 页，继续后续 OTP 轮询")


def _wait_for_otp_input(driver, timeout: int = 30) -> None:
    """验证码已收到但 OTP 输入框可能尚未出现（点完一次性验证码后常有中间页/延迟渲染）。

    等待期间若仍停留在登录密码页，则补点一次性验证码入口（最多 2 次、间隔 6s）；
    超时仍未出现时打印页面状态便于定位。
    """
    end = time.time() + timeout
    passwordless_retries = 0
    while time.time() < end:
        if _is_email_verification_page(driver):
            return
        if _is_login_password_page(driver) and passwordless_retries < 2:
            passwordless_retries += 1
            result = _click_passwordless_signup_if_present(driver)
            if result.get("ok"):
                logger.info("[Codex][Browser] 仍停留登录密码页，补点一次性验证码入口：%s", result.get("reason"))
                human_delay("form")
            time.sleep(6)
            continue
        time.sleep(0.8)
    state = _email_otp_page_state(driver)
    logger.warning(
        "[Codex][Browser] 等待 OTP 输入框超时，页面 url=%s inputs=%s buttons=%s 文本前300字=%s",
        str(state.get("url") or ""),
        len(state.get("inputs") or []),
        [(b.get("text") or "")[:24] for b in (state.get("buttons") or [])][:8],
        str(state.get("text") or "")[:300],
    )
    raise RuntimeError("等待 OTP 输入框超时，页面未出现验证码输入框")


def _select_existing_account_if_present(driver, email: str) -> bool:
    """登录态复用时选择当前邮箱账号，避免停在 account chooser。

    OpenAI 的账号选择按钮没有稳定的文字按钮名，但可见文本会包含当前邮箱，
    内部属性通常还带 session_id。只允许点击文本精确包含目标邮箱的元素，避免
    多账号 Profile 下误选其它账号。
    """
    target = str(email or "").strip().lower()
    if not target:
        return False
    try:
        result = driver.execute_script(r"""
        const target = String(arguments[0] || '').trim().toLowerCase();
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const actions = [...document.querySelectorAll('button,a,[role="button"]')].filter(visible);
        const matched = actions.find(el => String(el.innerText || el.textContent || '').trim().toLowerCase().includes(target));
        if (!matched) return {clicked:false, actionCount:actions.length};
        matched.scrollIntoView({block:'center'});
        matched.click();
        return {clicked:true, actionCount:actions.length};
        """, target) or {}
        if result.get("clicked"):
            logger.info("[Codex][Browser] 已选择当前登录账号，继续 OAuth（可见操作数=%s）", result.get("actionCount"))
            return True
    except Exception as exc:
        logger.debug("[Codex][Browser] 当前账号选择探测失败：%s", str(exc)[:160])
    return False


def _fill_email_and_otp(driver, email: str, otp_provider, auth_url: str) -> None:
    otp_after_ts = time.time()
    password, totp_secret = _account_login_credentials(email)
    logger.info("[Codex][Browser] 打开授权地址")
    logger.info("[Codex][Browser] 完整授权地址: %s", auth_url)
    driver.get(auth_url)
    human_delay("navigate")
    logger.info("[Codex][Browser] 授权页加载完成，检查是否需要邮箱登录")
    _maybe_accept(driver)
    if _select_existing_account_if_present(driver, email):
        human_delay("form")

    # 可能已经处于账号选择/授权页；如果有邮箱输入框则完整登录。
    # 非日本出口时按钮文案/顺序会变，不能按可见文字点“继续”，否则可能误点 Google。
    try:
        _type_email_address(driver, email, timeout=12)
        logger.info("[Codex][Browser] 已填写邮箱：%s", email)
        human_delay("form")
        _submit_email_step(driver)
        logger.info("[Codex][Browser] 已提交邮箱，识别密码、TOTP 或邮箱 OTP 分支")
    except Exception as exc:
        state = _login_challenge_state(driver)
        if _is_login_password_page(driver) or _is_totp_login_page(driver, state) or _is_email_verification_page(driver):
            logger.info("[Codex][Browser] 邮箱输入阶段页面已进入下一登录分支，继续按页面状态处理")
        elif _is_login_advanced(driver, state):
            logger.info("[Codex][Browser] 当前会话已越过登录挑战，无需邮箱 OTP")
            return
        else:
            logger.info("[Codex][Browser] 未检测到邮箱输入框，可能已登录或进入下一步：%s", str(exc)[:120])
            return

    next_state = _complete_login_challenge_after_email(
        driver,
        email,
        password,
        totp_secret,
        timeout=45,
    )
    if next_state == "advanced":
        logger.info("[Codex][Browser] 密码/TOTP 登录已完成，无需邮箱 OTP")
        return

    # 提交邮箱后不再执行任何全局“继续/授权/分支”兜底点击；后续只等待验证码页。
    # 避免页面已进入 OAuth consent 时误点授权按钮。

    used_codes: set[str] = set()
    max_otp_attempts = 3

    def _restart_email_otp_flow(reason: str) -> str:
        """Codex Auth 上直接点 resend 可能触发服务端 500；这里改为重新打开授权地址并提交邮箱。"""
        nonlocal otp_after_ts
        logger.info("[Codex][Browser] 重新触发邮箱 OTP：%s", reason)
        otp_after_ts = time.time()
        driver.get(auth_url)
        human_delay("navigate")
        _maybe_accept(driver)
        try:
            _type_email_address(driver, email, timeout=12)
            human_delay("form")
            _submit_email_step(driver)
            logger.info("[Codex][Browser] 已重新提交邮箱，重新识别登录分支")
            restart_state = _complete_login_challenge_after_email(
                driver,
                email,
                password,
                totp_secret,
                timeout=45,
            )
            if restart_state == "advanced":
                return "advanced"
        except Exception as exc:
            # 如果重进授权地址后已经停在验证码/下一步页面，就不要再强行提交。
            if not _is_email_verification_page(driver):
                raise
            else:
                logger.info("[Codex][Browser] 重开授权后已在邮箱 OTP 页面")
        human_delay("api")
        return "email_otp"

    for otp_attempt in range(1, max_otp_attempts + 1):
        logger.info("[Codex][Browser] 等待邮箱 OTP：%s（第 %s/%s 次）", email, otp_attempt, max_otp_attempts)
        try:
            code = _wait_for_fresh_email_otp(
                otp_provider,
                email,
                after_ts=otp_after_ts,
                used_codes=used_codes,
                timeout=90,
            )
        except Exception as exc:
            if otp_attempt >= max_otp_attempts:
                raise
            logger.warning(
                "[Codex][Browser] 一直未收到邮箱 OTP，点击“重新发送电子邮件”后继续等待（下一轮 %s/%s）：%s: %s",
                otp_attempt + 1,
                max_otp_attempts,
                type(exc).__name__,
                str(exc)[:180],
            )
            if _restart_email_otp_flow("等待验证码超时，避免点击 resend 导致 500") == "advanced":
                return
            continue
        used_codes.add(str(code))
        logger.info("[Codex][Browser] 邮箱 OTP 收到：%s", code)
        _wait_for_otp_input(driver, timeout=30)
        _clear_otp_inputs(driver)
        _type_otp(driver, code)
        logger.info("[Codex][Browser] 已填写邮箱 OTP")
        human_delay("otp_input")
        _install_email_otp_validate_hook(driver)
        clicked = _click_if_present(driver, [
            "button[type='submit']",
            "//button[contains(., 'Continue')]",
            "//button[contains(., '继续')]",
            "//button[contains(., 'Verify')]",
            "//button[contains(., '验证')]",
        ], timeout=8)
        if clicked:
            logger.info("[Codex][Browser] 已提交邮箱 OTP，等待后续授权/手机号页面")
        else:
            logger.info("[Codex][Browser] 未找到显式提交按钮，继续等待页面状态")

        outcome = _wait_after_email_otp_submit(driver, timeout=45)
        logger.info("[Codex][Browser] 邮箱 OTP 提交后状态：%s", outcome)
        if outcome == "accepted":
            return
        if str(outcome).startswith("deactivated:"):
            error_code = str(outcome).split(":", 1)[1] or "account_deactivated"
            raise AccountUnusableError(f"账号已废（{error_code}）", error_code=error_code)

        if otp_attempt >= max_otp_attempts:
            raise RuntimeError("Codex 邮箱验证码连续错误/过期，已达到最大重试次数")

        logger.warning(
            "[Codex][Browser] 邮箱验证码错误/过期或页面未跳转，准备重新发送并重新获取最新验证码（%s/%s）",
            otp_attempt + 1,
            max_otp_attempts,
        )
        if _restart_email_otp_flow("验证码错误/过期或页面未跳转，避免点击 resend 导致 500") == "advanced":
            return



def _wait_for_fresh_email_otp(otp_provider, email: str, after_ts: float, used_codes: set[str] | None = None, timeout: int = 90) -> str:
    """获取一个未提交过的邮箱 OTP。

    通用 API 邮箱的取码接口有时会先返回缓存旧码；验证码错误后重发时，
    这里会拒绝复用已失败的 code，持续轮询直到出现新 code 或超时。
    """
    used_codes = {str(x) for x in (used_codes or set()) if x}
    end = time.time() + timeout
    last_code = ""
    while True:
        remaining = max(1, int(end - time.time()))
        kwargs = {"after_ts": after_ts}
        try:
            params = inspect.signature(otp_provider).parameters.values()
            if any(p.name == "max_wait" or p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
                kwargs["max_wait"] = remaining
        except (TypeError, ValueError):
            pass
        code = str(otp_provider(email, **kwargs) or "").strip()
        if code and code not in used_codes:
            return code
        last_code = code or last_code
        remaining = int(end - time.time())
        if remaining <= 0:
            raise RuntimeError(f"等待新的邮箱验证码超时，取码接口仍返回已失败验证码：{last_code or '-'}")
        logger.warning(
            "[Codex][Browser] 取码接口仍返回已提交过的旧 OTP=%s，继续等待最新验证码（剩余 %ss）",
            last_code or "-",
            remaining,
        )
        time.sleep(min(5, max(1, remaining)))


def _install_email_otp_validate_hook(driver) -> None:
    """
    在页面内 hook fetch/XHR，捕获 email-otp/validate 的接口响应体。

    指纹浏览器不能像纯协议模式一样直接拿 requests.Response，因此在提交邮箱 OTP 前
    注入此 hook，后续只读取接口 JSON error.code，不靠页面文字判断废号。
    """
    script = r"""
    (() => {
      window.__codexEmailOtpValidateResponses = [];
      if (window.__codexEmailOtpValidateHooked) return true;
      window.__codexEmailOtpValidateHooked = true;
      const hit = (url) => String(url || '').includes('/api/accounts/email-otp/validate');
      const save = (url, status, body) => {
        try {
          if (!hit(url)) return;
          window.__codexEmailOtpValidateResponses.push({
            url: String(url || ''),
            status: Number(status || 0),
            body: String(body || '').slice(0, 2000),
            ts: Date.now(),
          });
        } catch (e) {}
      };
      const origFetch = window.fetch;
      if (origFetch) {
        window.fetch = async function(input, init) {
          const resp = await origFetch.apply(this, arguments);
          try {
            const url = (typeof input === 'string') ? input : (input && input.url);
            if (hit(url)) {
              resp.clone().text().then(t => save(url, resp.status, t)).catch(() => {});
            }
          } catch (e) {}
          return resp;
        };
      }
      const origOpen = XMLHttpRequest.prototype.open;
      const origSend = XMLHttpRequest.prototype.send;
      XMLHttpRequest.prototype.open = function(method, url) {
        this.__codexOtpValidateUrl = url;
        return origOpen.apply(this, arguments);
      };
      XMLHttpRequest.prototype.send = function() {
        try {
          this.addEventListener('loadend', function() {
            try {
              if (hit(this.__codexOtpValidateUrl)) save(this.__codexOtpValidateUrl, this.status, this.responseText);
            } catch (e) {}
          });
        } catch (e) {}
        return origSend.apply(this, arguments);
      };
      return true;
    })();
    """
    try:
        driver.execute_script(script)
    except Exception as exc:
        logger.debug("[Codex][Browser] 注入 email-otp/validate 响应 hook 失败：%s", exc)


def _read_email_otp_validate_dead_code(driver) -> str:
    try:
        rows = driver.execute_script("return window.__codexEmailOtpValidateResponses || [];") or []
    except Exception:
        return ""
    if not isinstance(rows, list):
        return ""
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        code = detect_account_unusable_response_body(str(row.get("body") or ""))
        if code:
            logger.warning(
                "[Codex][Browser] email-otp/validate 响应识别账号已废：code=%s status=%s",
                code,
                row.get("status"),
            )
            return code
    return ""


# 邮箱验证码页判断复用 roxy_registration 的强版本（URL + 输入框属性识别，
# 且明确排除 /log-in/password），不使用本地弱化版，避免点完一次性验证码后
# 页面已渲染 OTP 输入框却因 URL 不含 email-verification 而识别失败。

def _wait_after_email_otp_submit(driver, timeout: int = 45) -> str:
    """
    提交邮箱 OTP 后等待页面离开 /email-verification。

    返回：
      - accepted：已离开邮箱验证码页 / 进入手机号页 / 进入 callback；
      - invalid：页面明确报错、输入框标红，或长时间停留验证码页。
    """
    end = time.time() + timeout
    last_url = ""
    last_log = 0.0
    while time.time() < end:
        try:
            dead_code = _read_email_otp_validate_dead_code(driver)
            if dead_code:
                return f"deactivated:{dead_code}"
            url = str(driver.current_url or "")
            if url != last_url:
                logger.info("[Codex][Browser] 邮箱 OTP 后等待跳转：url=%s", url)
                last_url = url
            if _is_callback_url(url):
                return "accepted"
            if _has_strict_add_phone_form(driver) or _is_phone_code_page(driver):
                return "accepted"
            # 已经离开 email-verification，交给后续授权/手机号/consent 流程处理。
            if "email-verification" not in url.lower():
                return "accepted"

            state = _email_otp_page_state(driver)
            invalid = any(str(i.get("ariaInvalid") or "").lower() == "true" for i in (state.get("inputs") or []))
            errors = [str(x) for x in (state.get("errors") or []) if str(x).strip()]
            body_text = str(state.get("text") or "").lower()
            error_hit = any(x in body_text for x in (
                "invalid code", "incorrect code", "wrong code", "expired",
                "验证码错误", "验证码无效", "验证码已过期", "コードが正しく", "無効", "期限",
            ))
            if invalid or errors or error_hit:
                logger.warning(
                    "[Codex][Browser] 邮箱 OTP 提交后检测到错误/仍需验证码：errors=%s invalid=%s url=%s",
                    errors[:3],
                    invalid,
                    url,
                )
                return "invalid"

            if time.time() - last_log > 6:
                logger.info("[Codex][Browser] 邮箱 OTP 后仍在 email-verification，继续等待页面自动跳转")
                last_log = time.time()
        except Exception:
            pass
        time.sleep(0.5)
    logger.warning("[Codex][Browser] 邮箱 OTP 后等待跳转超时，当前 url=%s，按验证码无效/过期处理", getattr(driver, "current_url", ""))
    return "invalid"


def _phone_page_state(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const radios = [...document.querySelectorAll('input[type=radio]')].map(el => ({
          name: el.name || '', value: el.value || '', checked: !!el.checked, id: el.id || '', visible: visible(el)
        }));
        const inputs = [...document.querySelectorAll('input,select,textarea')].filter(visible).map(el => ({
          tag: el.tagName, type: el.getAttribute('type') || '', name: el.getAttribute('name') || '',
          id: el.id || '', autocomplete: el.getAttribute('autocomplete') || '', placeholder: el.getAttribute('placeholder') || '',
          ariaInvalid: el.getAttribute('aria-invalid') || '', value: el.value || ''
        }));
        const controls = [...document.querySelectorAll('button,a,label,[role=radio],[role=tab]')]
          .filter(visible).map(el => ({
            tag: el.tagName, role: el.getAttribute('role') || '',
            text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 160),
            ariaChecked: el.getAttribute('aria-checked') || '',
            ariaSelected: el.getAttribute('aria-selected') || '',
            dataState: el.getAttribute('data-state') || '',
          }));
        const forms = [...document.querySelectorAll('form')].map(f => ({action: f.getAttribute('action') || ''}));
        const bodyText = (document.body?.innerText || '').slice(0, 1200);
        return {url: location.href, radios, inputs, controls, forms, bodyText};
        """) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "url": getattr(driver, 'current_url', '')}


def _has_sms_word(text: str) -> bool:
    value = str(text or '').lower()
    return any(marker in value for marker in (
        'sms', 'text message', 'text-message', '短信', '短訊',
        'ショートメッセージ', 'テキストメッセージ',
    ))


def _body_indicates_whatsapp_only(state: dict) -> bool:
    body = str(state.get('bodyText') or '')
    if 'whatsapp' not in body.lower():
        return False
    radios = state.get('radios') or []
    controls = state.get('controls') or []
    has_sms_radio = any(_has_sms_word(str(r.get('value') or '')) for r in radios)
    has_sms_control = any(_has_sms_word(str(c.get('text') or '')) for c in controls)
    return not has_sms_radio and not has_sms_control and not _has_sms_word(body)


def _phone_channel_selection(state: dict) -> dict:
    """从 React/native 控件状态判断 SMS/WhatsApp 是否真的被选中。"""
    radios = state.get('radios') or []
    controls = state.get('controls') or []

    def radio_kind(item: dict) -> str:
        value = str(item.get('value') or '').lower().replace(' ', '_').replace('-', '_')
        if value in ('sms', 'text', 'text_message'):
            return 'sms'
        if 'whatsapp' in value:
            return 'whatsapp'
        return ''

    def control_kind(item: dict) -> str:
        text = str(item.get('text') or '')
        if _has_sms_word(text):
            return 'sms'
        if 'whatsapp' in text.lower():
            return 'whatsapp'
        return ''

    def control_selected(item: dict) -> bool:
        values = (
            item.get('ariaChecked'),
            item.get('ariaSelected'),
            item.get('dataState'),
        )
        return any(str(value or '').strip().lower() in ('true', 'checked', 'selected', 'on') for value in values)

    radio_rows = [(radio_kind(item), bool(item.get('checked'))) for item in radios]
    control_rows = [(control_kind(item), control_selected(item)) for item in controls]
    rows = radio_rows + control_rows
    return {
        'has_sms': any(kind == 'sms' for kind, _selected in rows),
        'has_whatsapp': any(kind == 'whatsapp' for kind, _selected in rows),
        'selected_sms': any(kind == 'sms' and selected for kind, selected in rows),
        'selected_whatsapp': any(kind == 'whatsapp' and selected for kind, selected in rows),
    }


def _verify_sms_channel_selected(driver, *, timeout: float = 4.0) -> dict:
    """提交手机号前确认 React 最终状态确实选择了 SMS。"""
    end = time.time() + max(0.2, float(timeout or 4.0))
    last_state = {}
    last_selection = {}
    while time.time() < end:
        last_state = _phone_page_state(driver)
        last_selection = _phone_channel_selection(last_state)
        if last_selection.get('selected_sms') and not last_selection.get('selected_whatsapp'):
            return last_selection
        if not last_selection.get('has_sms') and not last_selection.get('has_whatsapp'):
            if _body_indicates_whatsapp_only(last_state):
                raise RuntimeError(f"whatsapp_channel: 页面仅提供 WhatsApp 通道 state={last_state}")
            # 没有显式通道控件的旧页面默认就是 SMS。
            return {**last_selection, 'implicit_sms': True}
        time.sleep(0.15)

    if last_selection.get('selected_whatsapp'):
        raise RuntimeError(f"whatsapp_channel: 点击 SMS 后实际仍选中 WhatsApp state={last_state}")
    raise RuntimeError(f"sms_channel_not_selected: 点击 SMS 后控件未确认选中 state={last_state}")


def _select_sms_channel_or_raise(driver) -> None:
    state = _phone_page_state(driver)
    # 如果存在 WhatsApp 且没有 SMS/text 可选，当前接码平台无法读取 WhatsApp，直接换号。
    selection = _phone_channel_selection(state)
    has_whatsapp = bool(selection.get('has_whatsapp'))
    has_sms = bool(selection.get('has_sms'))
    if has_whatsapp and not has_sms:
        raise RuntimeError(f"whatsapp_channel: 页面仅提供 WhatsApp 通道 state={state}")
    # 选择 SMS/text radio；新版页面也可能用 role=radio/tab、button 或 label。
    selected = driver.execute_script(r"""
    const radios = [...document.querySelectorAll('input[type=radio]')];
    const sms = radios.find(el => /^(sms|text|text_message|text-message)$/i.test(el.value || ''));
    if (sms) {
      // 使用此前稳定的原生 radio 点击。点击 label 后再手工派发事件会让
      // React-Aria 在部分页面重复切换状态，并可能重建/清空手机号输入框。
      sms.click();
      sms.dispatchEvent(new Event('input', {bubbles:true}));
      sms.dispatchEvent(new Event('change', {bubbles:true}));
      return 'input-radio';
    }
    const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const isSms = text => /(^|\b)(sms|text message)(\b|$)|短信|短訊|ショートメッセージ|テキストメッセージ/i.test(text || '');
    const controls = [...document.querySelectorAll('button,a,label,[role=radio],[role=tab]')].filter(visible);
    const control = controls.find(el => isSms((el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim()));
    if (!control) return false;
    control.click();
    return 'clickable-control';
    """)
    if selected:
        logger.info("[Codex][Browser] 已选择 SMS 短信通道：%s", selected)
        return
    # 旧逻辑把“无 input radio”一律当默认 SMS。OpenAI 新版页面会直接写明
    # “通过 WhatsApp 发送”且没有通道控件，这时继续提交只会浪费 SMS 接码号。
    if _body_indicates_whatsapp_only(state):
        raise RuntimeError(f"whatsapp_channel: 当前授权页仅提供 WhatsApp，无法使用 SMS 接码 state={state}")


def _is_phone_code_state(state: dict) -> bool:
    url = str(state.get('url') or '').lower()
    if 'email-verification' in url:
        # 邮箱 OTP 页面也会出现 autocomplete=one-time-code，不能误判成手机验证码页。
        return False
    if 'phone-verification' in url:
        return True
    forms = state.get('forms') or []
    form_actions = ' '.join(str(f.get('action') or '') for f in forms).lower()
    if 'phone-verification' in form_actions:
        return True
    inputs = state.get('inputs') or []
    attrs = ' '.join(' '.join(str(i.get(k) or '') for k in ('type','name','id','autocomplete','placeholder')) for i in inputs).lower()
    body = str(state.get('bodyText') or '').lower()
    has_code_input = 'one-time-code' in attrs or 'otp' in attrs or 'code' in attrs
    phone_hint = (
        'phone' in url or 'phone' in form_actions
        or 'check your phone' in body
        or 'verification code we just sent' in body
        or 'enter the verification code' in body and ('text message' in body or 'phone' in body)
        or 'resend text message' in body
        or 'sent to +' in body
    )
    return bool(phone_hint and has_code_input)


def _is_phone_code_page(driver) -> bool:
    return _is_phone_code_state(_phone_page_state(driver))


def _is_add_phone_page(driver) -> bool:
    state = _phone_page_state(driver)
    url = str(state.get('url') or '').lower()
    inputs = state.get('inputs') or []
    attrs = ' '.join(' '.join(str(i.get(k) or '') for k in ('type','name','id','autocomplete')) for i in inputs).lower()
    return 'add-phone' in url or 'type tel' in attrs or 'phone' in attrs or 'tel' in attrs


_PHONE_INPUT_SELECTORS = [
    "input[type='tel']",
    "input[name='phone']",
    "input[name='phone_number']",
    "input[autocomplete='tel']",
    "input[id*='phone']",
    "input[placeholder*='Phone']",
    "input[placeholder*='phone']",
]


def _has_strict_add_phone_form(driver) -> bool:
    try:
        return bool(driver.execute_script(r"""
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const form = document.querySelector('form[action*="/add-phone" i]')
          || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
        if (!form) return false;
        return !![...form.querySelectorAll('input[type="tel"], input[name="__reservedForPhoneNumberInput_tel"], input[autocomplete="tel"], input[name="phone"], input[name="phone_number"]')].find(visible);
        """))
    except Exception:
        return False


def _auth_origin(driver) -> str:
    try:
        parsed = urlparse(str(driver.current_url or ""))
        if parsed.scheme and parsed.netloc and parsed.hostname and parsed.hostname.endswith("openai.com"):
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return "https://auth.openai.com"


def _ensure_add_phone_input(driver, *, reason: str = ""):
    """确保当前页面回到 add-phone，并返回手机号输入框。

    换号时如果还停留在 phone-verification/OTP 页，必须先回到手机号页，
    再把新号码重新写入页面并重新提交。
    """
    if _has_strict_add_phone_form(driver):
        return _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=2)

    current = str(getattr(driver, "current_url", "") or "")
    if "email-verification" in current.lower():
        logger.info("[Codex][Browser] 当前仍在 email-verification，先等待授权流程自动跳转，避免 invalid_auth_step")
        _wait_after_email_otp_submit(driver, timeout=45)
        if _has_strict_add_phone_form(driver):
            return _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=2)
        current = str(getattr(driver, "current_url", "") or "")

    target = _auth_origin(driver).rstrip("/") + "/add-phone"
    logger.info(
        "[Codex][Browser] 当前不在手机号输入页，准备重新打开 add-phone 后换号：reason=%s url=%s target=%s",
        reason or "retry", current, target,
    )
    try:
        driver.get(target)
        human_delay("navigate")
        return _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=10)
    except Exception as first_exc:
        # 某些流程不允许直接打开 /add-phone，尝试浏览器返回到上一页。
        logger.info("[Codex][Browser] 直接打开 add-phone 未拿到输入框，尝试 history back：%s", str(first_exc)[:160])
        try:
            driver.back()
            human_delay("navigate")
            return _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=8)
        except Exception as back_exc:
            raise RuntimeError(
                f"无法回到手机号输入页以重新换号: direct={type(first_exc).__name__}: {first_exc}; "
                f"back={type(back_exc).__name__}: {back_exc}; state={_phone_page_state(driver)}"
            )


def _select_phone_country_by_calling_code(driver, phone: str, *, timeout: int = 8) -> dict:
    """通过 React Aria 的可见国家列表选择与号码匹配的国家。

    OpenAI 当前的国家选择器使用 React Aria Select。页面同时渲染了一个仅供无障碍使用的
    隐藏 ``select``，直接修改它的 ``value`` 不会更新 React 状态；结果是界面/提交仍保留
    默认国家（通常是美国），即使隐藏 phoneNumber 被临时改成了其它国家的 E.164 号码。

    这里打开真实 listbox，按选项文案里的国际区号匹配号码，再用 Enter 选择。列表是虚拟
    滚动的，因此逐屏扫描，而不是假设目标选项已经出现在 DOM 中。
    """
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        raise RuntimeError("手机号为空，无法选择国家代码")

    info = driver.execute_script(r"""
    const form = document.querySelector('form[action*="/add-phone" i]')
      || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
    const button = form?.querySelector('button[aria-haspopup="listbox"]');
    const text = String(button?.innerText || button?.textContent || '').replace(/\s+/g, ' ').trim();
    const match = text.match(/\+(\d{1,4})\b/);
    return {hasButton: !!button, text, dialCode: match ? match[1] : '', expanded: button?.getAttribute('aria-expanded') || ''};
    """) or {}
    if not info.get("hasButton"):
        # 兼容旧版原生 select 页面；调用方会退回现有 select 解析逻辑。
        return {"selected": False, "dialCode": "", "selectedText": "", "countryKey": ""}

    current_code = str(info.get("dialCode") or "")
    if current_code and digits.startswith(current_code):
        return {
            "selected": True,
            "changed": False,
            "dialCode": current_code,
            "selectedText": str(info.get("text") or ""),
            "countryKey": "",
        }

    button = driver.execute_script(r"""
    const form = document.querySelector('form[action*="/add-phone" i]')
      || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
    return form?.querySelector('button[aria-haspopup="listbox"]') || null;
    """)
    if not button:
        raise RuntimeError("手机号国家选择按钮不存在")
    try:
        button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", button)

    end = time.time() + max(2, int(timeout or 8))
    last = {}
    while time.time() < end:
        scan = driver.execute_script(r"""
        const digits = String(arguments[0] || '');
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const list = [...document.querySelectorAll('[role="listbox"]')].find(visible);
        if (!list) return {ready:false};
        const candidates = [...list.querySelectorAll('[role="option"][data-key]')]
          .filter(visible)
          .map(el => {
            const text = String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
            const match = text.match(/\+(\d{1,4})\b/);
            return {el, text, code: match ? match[1] : '', key: el.getAttribute('data-key') || ''};
          })
          .filter(x => x.code && digits.startsWith(x.code))
          .sort((a, b) => b.code.length - a.code.length);
        if (candidates.length) {
          const found = candidates[0];
          return {ready:true, found:true, option:found.el, text:found.text, code:found.code, key:found.key};
        }
        const before = list.scrollTop;
        const step = Math.max(120, Math.floor((list.clientHeight || 320) * 0.75));
        const max = Math.max(0, list.scrollHeight - list.clientHeight);
        list.scrollTop = Math.min(max, before + step);
        list.dispatchEvent(new Event('scroll', {bubbles:true}));
        return {ready:true, found:false, before, after:list.scrollTop, max};
        """, digits) or {}
        last = scan
        if scan.get("option"):
            option = scan["option"]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].focus();", option)
            time.sleep(0.12)
            # React Aria 的 option 首次 click 可能只聚焦；Enter 会可靠触发 selection。
            option.send_keys("\ue007")
            selected_code = str(scan.get("code") or "")
            selected_key = str(scan.get("key") or "")
            selected_text = str(scan.get("text") or "")
            verify_end = time.time() + 2.5
            while time.time() < verify_end:
                verify = driver.execute_script(r"""
                const form = document.querySelector('form[action*="/add-phone" i]')
                  || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
                const button = form?.querySelector('button[aria-haspopup="listbox"]');
                const hiddenSelect = form?.querySelector('[data-testid="hidden-select-container"] select');
                const text = String(button?.innerText || button?.textContent || '').replace(/\s+/g, ' ').trim();
                const match = text.match(/\+(\d{1,4})\b/);
                return {text, dialCode:match ? match[1] : '', countryKey:hiddenSelect?.value || '', expanded:button?.getAttribute('aria-expanded') || ''};
                """) or {}
                if str(verify.get("dialCode") or "") == selected_code and (
                    not selected_key or str(verify.get("countryKey") or "") == selected_key
                ):
                    return {
                        "selected": True,
                        "changed": True,
                        "dialCode": selected_code,
                        "selectedText": str(verify.get("text") or selected_text),
                        "countryKey": str(verify.get("countryKey") or selected_key),
                    }
                time.sleep(0.1)
            raise RuntimeError(f"手机号国家选择后未生效：expected_code={selected_code} expected_key={selected_key} actual={verify}")

        if scan.get("ready") and scan.get("after") == scan.get("before") == scan.get("max"):
            break
        time.sleep(0.08)

    try:
        driver.switch_to.active_element.send_keys("\ue00c")  # Escape
    except Exception:
        pass
    raise RuntimeError(f"手机号国家列表找不到匹配区号：phone=+{digits} last={last}")


def _set_phone_value(driver, phone: str, *, timeout: int = 10) -> dict:
    """按 FlowPilot 第 9 步逻辑填写 add-phone 表单。

    要点：
    - 所有元素 scoped 到 form[action*="/add-phone"]；
    - 可见 tel 输入框写入“页面期望显示的号码”；
    - 如果页面存在隐藏 input[name="phoneNumber"]，同步写入完整 E.164 号码；
    - 触发 input/change 并 blur，让 React/React-Aria 完成校验。
    """
    if not _has_strict_add_phone_form(driver):
        raise RuntimeError(f"当前不是 add-phone 手机号输入页，不能填写手机号: state={_phone_page_state(driver)}")

    # PhoneInput 清空号码时会把国家恢复成默认值，因此必须先清空、再选国家；如果反过来，
    # Backspace 会把刚选好的 CL/+56 重置回 US/+1。
    initial_input = driver.execute_script(r"""
    const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const form = document.querySelector('form[action*="/add-phone" i]')
      || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
    return [...(form?.querySelectorAll('input[type="tel"],input[autocomplete="tel"],input[name="phone"],input[name="phone_number"]') || [])].find(visible) || null;
    """)
    if initial_input is None:
        raise RuntimeError(f"手机号可见输入框不存在 state={_phone_page_state(driver)}")
    try:
        initial_input.click()
        initial_input.send_keys("\ue03d", "a")  # Meta+A（macOS）
        initial_input.send_keys("\ue003")       # Backspace
        if str(initial_input.get_attribute("value") or ""):
            initial_input.send_keys("\ue009", "a")  # Control+A 兜底
            initial_input.send_keys("\ue003")
    except Exception as exc:
        raise RuntimeError(f"清空旧手机号失败：{type(exc).__name__}: {exc}") from exc

    country = _select_phone_country_by_calling_code(driver, phone, timeout=timeout)
    if country.get("changed"):
        # DOM 上的 SelectValue/隐藏 select 会先更新；React PhoneInput 的内部 country state
        # 稍后才提交。立即输入号码会被旧的 US state 重新格式化为 +1。
        time.sleep(0.5)
    result = driver.execute_script(r"""
    const rawPhone = String(arguments[0] || '').trim();
    const selectedDialCode = String(arguments[1] || '').trim();
    const selectedCountryText = String(arguments[2] || '').trim();
    const selectedCountryKey = String(arguments[3] || '').trim();
    const countryWasChanged = !!arguments[4];
    const e164 = rawPhone.startsWith('+') ? rawPhone : ('+' + rawPhone.replace(/\D+/g, ''));
    const digits = e164.replace(/\D+/g, '');
    const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const form = document.querySelector('form[action*="/add-phone" i]')
      || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
    if (!form) {
      return {ok:false, error:'missing_add_phone_form', url: location.href};
    }
    const phoneInput = [...form.querySelectorAll('input[type="tel"], input[name="__reservedForPhoneNumberInput_tel"], input[autocomplete="tel"], input[name="phone"], input[name="phone_number"]')]
      .find(visible);
    if (!phoneInput) {
      return {ok:false, error:'missing_phone_input', url: location.href};
    }

    const hiddenPhoneNumberInput = form.querySelector('input[name="phoneNumber"]');
    const select = form.querySelector('select');
    let dialCode = selectedDialCode;
    let selectedText = selectedCountryText;
    let selectedChanged = countryWasChanged;
    const optionDialCode = (opt) => {
      const text = String(opt?.textContent || opt?.label || opt?.value || '').replace(/\s+/g, ' ').trim();
      const m = text.match(/\+(\d{1,4})\b/);
      return m ? m[1] : '';
    };
    if (select && !dialCode) {
      // 参考 FlowPilot ensureCountrySelected：按号码前缀选择对应国家/区号，避免默认国家与号码不一致。
      const options = [...select.options];
      const matched = options
        .map(opt => ({opt, code: optionDialCode(opt)}))
        .filter(x => x.code && digits.startsWith(x.code))
        .sort((a, b) => b.code.length - a.code.length)[0];
      if (matched && select.value !== matched.opt.value) {
        select.value = matched.opt.value;
        select.dispatchEvent(new Event('input', {bubbles:true}));
        select.dispatchEvent(new Event('change', {bubbles:true}));
        selectedChanged = true;
      }
      if (select.selectedIndex >= 0 && select.options[select.selectedIndex]) {
        const opt = select.options[select.selectedIndex];
        selectedText = String(opt.textContent || opt.label || opt.value || '').replace(/\s+/g, ' ').trim();
        dialCode = optionDialCode(opt);
      }
    }

    // FlowPilot：可见框一般填 national number；隐藏 phoneNumber 填完整 E.164。
    // 若无法判断页面区号，则可见框填完整 +E164，避免丢国家码。
    let visibleValue = e164;
    if (dialCode && digits.startsWith(dialCode) && digits.length > dialCode.length + 3) {
      visibleValue = digits.slice(dialCode.length);
      if (!visibleValue) visibleValue = e164;
    }

    phoneInput.scrollIntoView({block:'center'});
    return {
      ok: true,
      phoneInput,
      e164,
      visibleValue,
      dialCode,
      selectedText,
      selectedChanged,
      countryKey: selectedCountryKey || (select ? (select.value || '') : ''),
      inputName: phoneInput.getAttribute('name') || '',
      inputId: phoneInput.id || '',
      url: location.href,
    };
    """, phone, country.get("dialCode") or "", country.get("selectedText") or "", country.get("countryKey") or "", bool(country.get("changed")))
    if not result or not result.get("ok"):
        raise RuntimeError(f"手机号写入失败 result={result} state={_phone_page_state(driver)}")

    # React Aria PhoneInput 必须走真实键盘事件。直接调用原生 value setter 虽然能短暂改变
    # DOM，却会在下一次 React 更新时把国家恢复成默认值（实测为 US/+1）。
    phone_input = result.pop("phoneInput", None)
    if phone_input is None:
        raise RuntimeError(f"手机号可见输入框不存在 result={result} state={_phone_page_state(driver)}")
    try:
        phone_input.click()
        phone_input.send_keys(str(result.get("visibleValue") or ""))
        phone_input.send_keys("\ue004")  # Tab，触发 blur/校验
    except Exception as exc:
        raise RuntimeError(f"手机号真实键盘输入失败：{type(exc).__name__}: {exc}") from exc

    # 等 React 完成格式化并同步隐藏 E.164 字段，再做最终校验。
    settle_end = time.time() + 2.5
    values = {}
    while time.time() < settle_end:
        values = driver.execute_script(r"""
        const form = document.querySelector('form[action*="/add-phone" i]')
          || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const input = [...(form?.querySelectorAll('input[type="tel"],input[autocomplete="tel"],input[name="phone"],input[name="phone_number"]') || [])].find(visible);
        const hidden = form?.querySelector('input[name="phoneNumber"]');
        const button = form?.querySelector('button[aria-haspopup="listbox"]');
        const select = form?.querySelector('[data-testid="hidden-select-container"] select');
        return {
          actualVisible: String(input?.value || ''),
          hiddenValue: String(hidden?.value || ''),
          selectedText: String(button?.innerText || button?.textContent || '').replace(/\s+/g, ' ').trim(),
          countryKey: String(select?.value || ''),
        };
        """) or {}
        result.update(values)
        actual_digits_now = "".join(ch for ch in str(values.get("actualVisible") or "") if ch.isdigit())
        hidden_digits_now = "".join(ch for ch in str(values.get("hiddenValue") or "") if ch.isdigit())
        expected_digits_now = "".join(ch for ch in str(result.get("e164") or "") if ch.isdigit())
        visible_digits_now = "".join(ch for ch in str(result.get("visibleValue") or "") if ch.isdigit())
        if actual_digits_now in (visible_digits_now, expected_digits_now) and (
            not values.get("hiddenValue") or hidden_digits_now == expected_digits_now
        ):
            break
        time.sleep(0.1)

    actual = str(result.get("actualVisible") or "").strip()
    visible_value = str(result.get("visibleValue") or "").strip()
    hidden_value = str(result.get("hiddenValue") or "").strip()
    e164 = str(result.get("e164") or "").strip()
    # OpenAI/React-Aria 电话框会自动格式化，例如 +84925154291 -> +84 925 154 291。
    # 不能按界面字符串精确比较，只比较数字归一化后的值。
    actual_digits = ''.join(ch for ch in actual if ch.isdigit())
    visible_digits = ''.join(ch for ch in visible_value if ch.isdigit())
    e164_digits = ''.join(ch for ch in e164 if ch.isdigit())
    hidden_digits = ''.join(ch for ch in hidden_value if ch.isdigit())
    expected_visible_ok = bool(actual_digits) and (actual_digits == visible_digits or actual_digits == e164_digits)
    if not expected_visible_ok:
        raise RuntimeError(f"手机号可见输入框校验失败 expected_digits={visible_digits or e164_digits} actual={actual} result={result} state={_phone_page_state(driver)}")
    if hidden_value and hidden_digits != e164_digits:
        raise RuntimeError(f"手机号隐藏字段校验失败 expected={e164} actual={hidden_value} result={result} state={_phone_page_state(driver)}")
    return result


def _blur_active_input_and_wait(driver, *, label: str = "输入完成") -> None:
    """输入手机号后移开焦点，并给前端校验/格式化留处理时间。"""
    try:
        driver.execute_script(r"""
        const active = document.activeElement;
        if (active && typeof active.blur === 'function') active.blur();
        document.body?.focus?.();
        document.dispatchEvent(new Event('change', {bubbles:true}));
        """)
    except Exception:
        pass
    seconds = random.uniform(1.8, 3.2)
    logger.info("[Codex][Browser] %s，已移开焦点，等待页面处理 %.1f 秒", label, seconds)
    time.sleep(seconds)


def _verify_add_phone_value_before_submit(driver, expected_e164: str) -> dict:
    result = driver.execute_script(r"""
    const expected = String(arguments[0] || '').trim();
    const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    const form = document.querySelector('form[action*="/add-phone" i]')
      || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
    if (!form) return {ok:false, error:'missing_add_phone_form', url: location.href};
    const input = [...form.querySelectorAll('input[type="tel"], input[name="__reservedForPhoneNumberInput_tel"], input[autocomplete="tel"], input[name="phone"], input[name="phone_number"]')].find(visible);
    const hidden = form.querySelector('input[name="phoneNumber"]');
    const visibleValue = String(input?.value || '').trim();
    const hiddenValue = String(hidden?.value || '').trim();
    const digits = value => String(value || '').replace(/\D+/g, '');
    const visibleDigits = digits(visibleValue);
    const hiddenDigits = digits(hiddenValue);
    const expectedDigits = digits(expected);
    // 输入框可能被自动格式化，按数字比较；隐藏字段如果存在必须等于完整 E.164。
    const visibleMatches = visibleDigits === expectedDigits
      || (!!hiddenDigits && hiddenDigits === expectedDigits && expectedDigits.endsWith(visibleDigits));
    const ok = !!visibleDigits && visibleMatches && (!hidden || hiddenDigits === expectedDigits);
    return {ok, visibleValue, hiddenValue, expected, visibleDigits, hiddenDigits, expectedDigits, url: location.href};
    """, expected_e164)
    if not result or not result.get("ok"):
        raise RuntimeError(f"手机号提交前校验失败 result={result} state={_phone_page_state(driver)}")
    return result


def _prepare_phone_form_for_submit(driver, phone: str, *, attempts: int = 2) -> dict:
    """稳定 add-phone 表单，并保证最后一次交互后手机号和 SMS 通道同时有效。

    OpenAI 的 React-Aria 表单在切换 SMS/WhatsApp 通道时可能重建手机号输入框。
    因此不能只在切换通道前验证号码；若切换后号码消失，使用同一个接码订单
    重新填写一次，而不是把页面状态问题误判成号码失败并重新买号。
    """
    attempts = max(1, min(2, int(attempts or 1)))
    last_exc: Exception | None = None
    for form_attempt in range(1, attempts + 1):
        _ensure_add_phone_input(driver, reason=f"same-number-form-attempt-{form_attempt}")
        phone_fill = _set_phone_value(driver, phone, timeout=10)
        logger.info(
            "[Codex][Browser] 已重新设置手机号：e164=%s visible=%s hidden=%s dialCode=%s country=%s",
            phone_fill.get("e164"),
            phone_fill.get("actualVisible"),
            phone_fill.get("hiddenValue") or "-",
            phone_fill.get("dialCode") or "-",
            str(phone_fill.get("selectedText") or "-")
            + (" [changed]" if phone_fill.get("selectedChanged") else ""),
        )
        _blur_active_input_and_wait(driver, label="手机号输入完成")
        expected_e164 = str(phone_fill.get("e164") or phone)
        phone_verify = _verify_add_phone_value_before_submit(driver, expected_e164)
        logger.info(
            "[Codex][Browser] 手机号通道选择前校验通过：visible=%s hidden=%s",
            phone_verify.get("visibleValue"),
            phone_verify.get("hiddenValue") or "-",
        )

        logger.info("[Codex][Browser] 检查并选择 SMS 短信通道")
        _select_sms_channel_or_raise(driver)
        _blur_active_input_and_wait(driver, label="短信通道确认完成")
        channel_selection = _verify_sms_channel_selected(driver, timeout=4)
        logger.info("[Codex][Browser] SMS 短信通道实际选中状态已确认：%s", channel_selection)
        try:
            final_verify = _verify_add_phone_value_before_submit(driver, expected_e164)
        except Exception as exc:
            last_exc = exc
            if form_attempt < attempts:
                logger.warning(
                    "[Codex][Browser] SMS 通道切换后手机号状态丢失，使用同一号码重填（%s/%s）：%s",
                    form_attempt + 1,
                    attempts,
                    str(exc)[:220],
                )
                continue
            break
        logger.info(
            "[Codex][Browser] 最终提交前手机号校验通过：visible=%s hidden=%s",
            final_verify.get("visibleValue"),
            final_verify.get("hiddenValue") or "-",
        )
        return {"phone_fill": phone_fill, "phone_verify": final_verify, "channel": channel_selection}

    raise RuntimeError(f"phone_form_unstable: SMS 通道切换后手机号状态仍不稳定；{last_exc}")


def _wait_page_settle_after_submit() -> None:
    """点击提交后先等待页面处理，再检查发送状态。"""
    seconds = random.uniform(2.0, 4.0)
    logger.info("[Codex][Browser] 已点击提交，等待页面发送/跳转处理 %.1f 秒后检查状态", seconds)
    time.sleep(seconds)


def _refresh_add_phone_for_retry(driver, *, reason: str = "") -> None:
    """发送失败/换号前刷新手机号页，避免旧错误状态和旧号码残留。"""
    try:
        logger.info("[Codex][Browser] 发送失败/准备换号，刷新手机号页面：%s", reason or "retry")
        driver.refresh()
        human_delay("navigate")
        try:
            _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=8)
            return
        except Exception:
            pass
        # 如果刷新后仍不在输入页，强制回 add-phone。
        target = _auth_origin(driver).rstrip("/") + "/add-phone"
        logger.info("[Codex][Browser] 刷新后未找到手机号输入框，重新打开：%s", target)
        driver.get(target)
        human_delay("navigate")
        _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=8)
    except Exception as exc:
        logger.info("[Codex][Browser] 刷新手机号页失败，下一轮会再次尝试回到 add-phone：%s", str(exc)[:180])


def _click_add_phone_continue_button(driver, *, timeout: int = 10) -> dict:
    """点击 add-phone 表单里的 Continue/続行 按钮。

    参考 FlowPilot 的 getAddPhoneSubmitButton + simulateClick：优先在 add-phone form 内找
    enabled submit，点击失败时用 form.requestSubmit(button) 兜底。
    """
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            btn = driver.execute_script(r"""
            const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
            const enabled = el => {
              if (!el) return false;
              if (el.disabled) return false;
              if (String(el.getAttribute('aria-disabled') || '').toLowerCase() === 'true') return false;
              return true;
            };
            const form = document.querySelector('form[action*="/add-phone" i]')
              || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
            if (!form) return null;
            const buttons = [...form.querySelectorAll('button[type="submit"], input[type="submit"]')];
            return buttons.find(b => visible(b) && enabled(b) && (b.getAttribute('data-dd-action-name') || '').toLowerCase() === 'continue')
              || buttons.find(b => visible(b) && enabled(b))
              || buttons.find(b => visible(b))
              || null;
            """)
            if btn:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                time.sleep(random.uniform(0.3, 0.8))
                try:
                    text = str(getattr(btn, 'text', '') or btn.get_attribute('value') or btn.get_attribute('data-dd-action-name') or '').strip()
                except Exception:
                    text = ''
                try:
                    btn.click()
                    _wait_page_settle_after_submit()
                    return {"ok": True, "method": "click", "text": text}
                except Exception as click_exc:
                    last = click_exc
                    submitted = driver.execute_script(r"""
                    const btn = arguments[0];
                    const form = btn?.form || btn?.closest?.('form');
                    if (form && typeof form.requestSubmit === 'function') {
                      form.requestSubmit(btn);
                      return true;
                    }
                    if (btn && typeof btn.click === 'function') {
                      btn.click();
                      return true;
                    }
                    return false;
                    """, btn)
                    if submitted:
                        _wait_page_settle_after_submit()
                        return {"ok": True, "method": "requestSubmit", "text": text, "click_error": str(click_exc)[:160]}
        except Exception as exc:
            last = exc
        time.sleep(0.25)
    raise RuntimeError(f"submit_missing: add-phone Continue/続行 submit button not found last={last} state={_phone_page_state(driver)}")


def _force_submit_add_phone_form(driver) -> dict:
    """add-phone 页面点击按钮没生效时，直接 requestSubmit 当前 form。"""
    try:
        return driver.execute_script(r"""
        const visible = el => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const form = document.querySelector('form[action*="/add-phone" i]')
          || [...document.querySelectorAll('form')].find(f => /add-phone/i.test(f.getAttribute('action') || ''));
        if (!form) return {ok:false, reason:'missing_form', url: location.href};
        const btn = [...form.querySelectorAll('button[type="submit"],input[type="submit"]')]
          .find(el => visible(el) && !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true')
          || form.querySelector('button[type="submit"],input[type="submit"]');
        if (btn) btn.scrollIntoView({block:'center'});
        if (typeof form.requestSubmit === 'function') form.requestSubmit(btn || undefined);
        else if (btn && typeof btn.click === 'function') btn.click();
        else form.submit();
        return {ok:true, method: btn ? 'requestSubmit(button)' : 'requestSubmit(form)', url: location.href};
        """) or {}
    except Exception as exc:
        return {ok:false, reason:f'{type(exc).__name__}: {exc}', url:getattr(driver, 'current_url', '')}


def _wait_after_phone_send(driver, timeout: int = 12) -> str:
    """等待手机号提交结果。

    只有页面出现明确的号码拒绝/发送失败文案时才抛出换号错误。单独的
    ``aria-invalid``、"需要电话号码" 或仍停留在 add-phone 都可能只是 React
    重渲染/路由延迟；这类不确定状态交给上层继续守住当前接码订单，不能立即买新号。
    """
    end = time.time() + timeout
    last = {}
    force_submitted = False
    while time.time() < end:
        time.sleep(1)
        last = _phone_page_state(driver)
        # 必须优先判断验证码页：页面文案里可能包含 send/limit/check 等词，不能把
        # “Check your phone / Enter the verification code...” 误判成发送失败。
        if _is_phone_code_state(last):
            return 'code_page'
        body = str(last.get('bodyText') or '')
        reason = _classify_phone_page_failure(last)
        if reason:
            raise RuntimeError(f"{reason}: {body[:240]}")
        if _is_add_phone_page(driver):
            # Cloak/React-Aria 场景下 btn.click 可能只聚焦没触发表单提交；补一次 requestSubmit。
            if not force_submitted and time.time() > end - timeout + 3:
                info = _force_submit_add_phone_form(driver)
                logger.info("[Codex][Browser] add-phone 点击后仍停留本页，补执行 form.requestSubmit：%s", info)
                force_submitted = True
                time.sleep(2)
    if _is_phone_code_state(last) or _is_phone_code_page(driver):
        return 'code_page'
    if _is_add_phone_page(driver):
        logger.warning(
            "[Codex][Browser] 手机号提交后页面状态仍不确定，将继续等待当前号码短信，"
            "不立即换号：state=%s",
            last,
        )
        return 'submission_uncertain'
    return 'unknown'


def _ensure_phone_code_page_after_sms(driver, *, timeout: int = 15) -> None:
    """短信已经到达时，确保浏览器进入验证码页；失败时由上层止损，禁止再买号。"""
    if _is_phone_code_page(driver):
        return
    end = time.time() + max(2, int(timeout or 15))
    while time.time() < end:
        if _is_phone_code_page(driver):
            return
        time.sleep(0.5)

    target = _auth_origin(driver).rstrip("/") + "/phone-verification"
    logger.warning(
        "[Codex][Browser] 当前号码已收到短信但页面尚未跳转，尝试恢复验证码页：%s",
        target,
    )
    try:
        driver.get(target)
    except Exception as exc:
        logger.warning("[Codex][Browser] 恢复手机验证码页导航异常，继续检查 DOM：%s", str(exc)[:180])
    end = time.time() + max(5, min(15, int(timeout or 15)))
    while time.time() < end:
        if _is_phone_code_page(driver):
            return
        time.sleep(0.5)
    raise RuntimeError(
        "sms_received_but_phone_code_page_missing: 当前号码已经收到短信，"
        "但浏览器无法恢复验证码页；已停止继续购买号码"
    )


def _wait_after_phone_otp_submit(driver, timeout: int = 20) -> str:
    """手机验证码提交后等待结果。

    成功时通常会跳出 phone-verification，进入 consent/workspace/callback；不能在提交后
    3 秒立刻读取旧页面文案并按 send_limited 判失败。只有明确仍在手机号流程且出现错误时
    才返回失败。
    """
    end = time.time() + timeout
    last = {}
    while time.time() < end:
        time.sleep(1)
        current = str(getattr(driver, "current_url", "") or "")
        if _is_callback_url(current):
            return "callback"
        last = _phone_page_state(driver)
        # 已离开手机验证码/加手机号页面，说明验证码被接受，后续交给 consent/callback 流程。
        if not _is_phone_code_state(last) and not _is_add_phone_page(driver):
            return "left_phone_flow"
        # 仍在验证码页时，只把明确错误当失败；普通 Check your phone 页面继续等。
        if _is_phone_code_state(last):
            inputs = last.get('inputs') or []
            invalid = any(str(i.get('ariaInvalid') or '').lower() == 'true' for i in inputs)
            body = str(last.get('bodyText') or '').lower()
            if invalid or any(k in body for k in (
                'invalid code', 'incorrect code', 'wrong code', 'expired code',
                'code is invalid', 'code was invalid', '验证码无效', '验证码错误', '验证码已过期',
                '認証コードが無効', 'コードが正しく',
            )):
                raise RuntimeError(f"invalid_phone_code: {(last.get('bodyText') or '')[:240]}")
            continue
        reason = _classify_phone_page_failure(last)
        if reason:
            raise RuntimeError(f"{reason}: {(last.get('bodyText') or '')[:240]}")
    # 超时后再看一次：如果已经离开手机号流程，视为通过；如果仍在验证码页但没明确错误，交给后续流程继续试。
    current = str(getattr(driver, "current_url", "") or "")
    if _is_callback_url(current):
        return "callback"
    last = _phone_page_state(driver)
    if not _is_phone_code_state(last) and not _is_add_phone_page(driver):
        return "left_phone_flow"
    if _is_phone_code_state(last):
        return "still_code_page"
    return "unknown"


def _classify_phone_page_failure(state: dict) -> str:
    if _is_phone_code_state(state):
        return ''
    # WhatsApp 可能是选中的 input radio，也可能是新版页面唯一提供的正文通道。
    # 若页面同时出现 SMS 选项/文字，则不能仅凭 bodyText 含 WhatsApp 判失败。
    radios = state.get('radios') or []
    checked_whatsapp = any(
        'whatsapp' in str(r.get('value', '')).lower().replace(' ', '') and r.get('checked')
        for r in radios
    )
    if checked_whatsapp:
        # 页面同时提供 SMS 时，提交后回到 WhatsApp 选中态通常是 React 表单
        # 重渲染导致的通道回退；它不是号码失败，也不应该触发购买新号码。
        selection = _phone_channel_selection(state)
        if selection.get('has_sms'):
            return 'sms_channel_reset'
        return 'whatsapp_channel'
    if _body_indicates_whatsapp_only(state):
        return 'whatsapp_channel'
    text = str(state.get('bodyText') or '').lower()
    if 'invalid_auth_step' in text or 'invalid auth step' in text:
        return 'invalid_auth_step'
    if any(k in text for k in ('invalid phone', 'not a valid phone', 'phone number is not valid', '号码无效', '手机号无效')):
        return 'invalid_phone'
    if any(k in text for k in (
        'cannot send', 'could not send', 'unable to send', 'failed to send', 'send failed',
        '发送失败', '发送失败了', '无法发送', '不能发送', '无法向',
        '送信できません', '送信に失敗', '送信できなかった',
    )):
        return 'delivery_refused'
    if any(k in text for k in ('too many', 'rate limit', 'throttle', '频繁', '限流')):
        return 'send_limited'
    return ''


def _is_codex_retry_stopped_exception(exc: BaseException) -> bool:
    """识别 WebUI Codex 补跑的异步停止信号，避免被换号重试捕获后继续买号。"""
    try:
        from core.codex_retry_service import CodexRetryStopped
    except Exception:
        return False
    return isinstance(exc, CodexRetryStopped)


def _phone_error_allows_number_rotation(exc: Exception) -> bool:
    """只有明确的号码/发送失败才允许购买下一个号码。"""
    if isinstance(exc, sms_provider.SmsCodeTimeout):
        return True
    text = str(exc or "").strip().lower()
    return text.startswith((
        "invalid_phone:",
        "delivery_refused:",
        "send_limited:",
    )) or "激活已被取消" in text or "status_cancel" in text


def _phone_error_counts_country_failure(exc: Exception) -> bool:
    """页面自动化/会话限流不污染接码国家成功率，只统计号码侧失败。"""
    if isinstance(exc, sms_provider.SmsCodeTimeout):
        return True
    text = str(exc or "").strip().lower()
    return text.startswith((
        "invalid_phone:",
        "delivery_refused:",
    ))


def _report_phone_progress(detail: str) -> None:
    """给 WebUI 写手机验证心跳；CLI/独立补跑没有注册任务上下文时自动忽略。"""
    try:
        from core.registration_service import report_job_progress

        report_job_progress("codex", "running", detail)
    except Exception:
        logger.debug("[Codex][Browser] 手机验证进度上报失败", exc_info=True)


def _sleep_before_phone_retry(
    attempt: int,
    max_retries: int,
    *,
    prefix: str = "[Codex][Browser]",
    deadline: float | None = None,
) -> None:
    """换号前随机等待，至少 3 秒，避免连续提交号码过快。"""
    if attempt >= max_retries:
        return
    seconds = random.uniform(3.0, 8.0)
    if deadline is not None:
        seconds = min(seconds, max(0.0, deadline - time.monotonic()))
    if seconds <= 0:
        return
    logger.info("%s 换号前随机等待 %.1f 秒", prefix, seconds)
    time.sleep(seconds)


def _do_phone_verification_if_present(driver) -> None:
    """如果页面要求手机号验证，则用当前 sms_provider 自动完成。"""
    provider = str(getattr(sms_provider._cfg, "SMS_PROVIDER", "") or "").strip().lower() if hasattr(sms_provider, "_cfg") else ""
    http = sms_provider._http()
    max_retries = int(getattr(sms_provider._cfg, "SMS_MAX_RETRIES", 10) or 10) if hasattr(sms_provider, "_cfg") else 10
    total_budget = max(30, int(getattr(sms_provider._cfg, "CODEX_PHONE_TOTAL_TIMEOUT", 300) or 300))
    deadline = time.monotonic() + total_budget
    try:
        # 如果页面没有手机号输入框，直接返回。
        try:
            end_detect = time.time() + 8
            while time.time() < end_detect and not _has_strict_add_phone_form(driver):
                # 如果已经在验证码页，说明手机步骤之前已提交过；继续处理验证码页，不应当跳过。
                if _is_phone_code_page(driver):
                    break
                time.sleep(0.5)
            if not (_has_strict_add_phone_form(driver) or _is_phone_code_page(driver)):
                raise RuntimeError("not_phone_flow")
        except Exception:
            logger.info("[Codex][Browser] 未检测到手机号验证页，跳过手机步骤")
            return

        # 通道是整个授权页的能力，不是某个接码号码的属性。若页面明确只提供
        # WhatsApp，在购买 SMS 号码之前就终止；换国家/换号也无法解决。
        initial_phone_state = _phone_page_state(driver)
        if _body_indicates_whatsapp_only(initial_phone_state):
            raise RuntimeError(
                "whatsapp_channel: 当前授权页仅提供 WhatsApp，已在取号前停止，避免购买 SMS 号码"
            )

        last_err = None
        for attempt in range(1, max_retries + 1):
            remaining = max(0, int(deadline - time.monotonic()))
            if remaining <= 0:
                break
            activation_id = None
            sms_received = False
            try:
                _report_phone_progress(
                    f"手机验证第 {attempt}/{max_retries} 次，整段剩余约 {remaining} 秒，正在取号"
                )
                activation_id, phone = sms_provider.acquire_number(http)
                logger.info("[Codex][Browser] 手机验证尝试 %s/%s，provider=%s，号码=+%s", attempt, max_retries, provider, phone)
                logger.info("[Codex][Browser] 准备手机号输入页，稳定同一个号码与 SMS 通道")
                _prepare_phone_form_for_submit(driver, f"+{phone}", attempts=2)
                submit_info = _click_add_phone_continue_button(driver, timeout=10)
                logger.info("[Codex][Browser] 已点击手机号 Continue/続行 按钮：%s，等待进入短信验证码页", submit_info)

                # 明确的号码拒绝会直接抛错并换号；页面暂态则继续守住当前接码订单。
                remaining = max(1, int(deadline - time.monotonic()))
                try:
                    send_outcome = _wait_after_phone_send(driver, timeout=min(15, remaining))
                except RuntimeError as send_exc:
                    # 新版 React 表单偶尔会在首次 submit 后把通道重置回 WhatsApp。
                    # 复用当前已购买的号码重选 SMS，并用 requestSubmit 补交一次；
                    # 仍失败则交给外层取消该订单并终止，绝不购买第二个号码。
                    if not str(send_exc).strip().lower().startswith("sms_channel_reset:"):
                        raise
                    logger.warning(
                        "[Codex][Browser] 首次提交后 SMS 通道被页面重置，使用同一号码重选并补交一次"
                    )
                    _prepare_phone_form_for_submit(driver, f"+{phone}", attempts=2)
                    retry_submit = _force_submit_add_phone_form(driver)
                    if not retry_submit.get("ok"):
                        raise RuntimeError(
                            f"sms_channel_reset: 同号重选 SMS 后补交失败 info={retry_submit}"
                        ) from send_exc
                    _wait_page_settle_after_submit()
                    remaining = max(1, int(deadline - time.monotonic()))
                    send_outcome = _wait_after_phone_send(driver, timeout=min(15, remaining))
                if send_outcome == "code_page":
                    logger.info("[Codex][Browser] 已进入手机验证码页")
                else:
                    logger.warning(
                        "[Codex][Browser] 手机号页面尚未确认跳转（%s），继续等待当前号码短信，禁止立即换号",
                        send_outcome,
                    )

                sms_provider.set_status(activation_id, 1, http=http)
                logger.info(
                    "[Codex][Browser] 手机号已提交并设置接码订单就绪，开始轮询验证码 "
                    "activation_id=%s wait=%ss interval=%ss",
                    activation_id, sms_provider._cfg.SMS_CODE_WAIT, sms_provider._cfg.SMS_POLL_INTERVAL
                )
                remaining = max(0, int(deadline - time.monotonic()))
                if remaining <= 0:
                    raise TimeoutError("phone_total_timeout: 手机验证整段预算已耗尽")
                wait_limit = min(
                    int(getattr(sms_provider._cfg, "SMS_CODE_WAIT", 120) or 120),
                    remaining,
                )
                sms_code = sms_provider.wait_for_sms_code(
                    activation_id,
                    http,
                    max_wait=wait_limit,
                    progress_callback=lambda elapsed, left, _round: _report_phone_progress(
                        f"手机验证第 {attempt}/{max_retries} 次，已等短信 {elapsed} 秒，"
                        f"本号码剩余约 {left} 秒，整段剩余约 {max(0, int(deadline - time.monotonic()))} 秒"
                    ),
                )
                sms_received = True
                logger.info("[Codex][Browser] 手机 OTP 收到：%s", sms_code)
                _ensure_phone_code_page_after_sms(driver, timeout=15)
                _type_otp(driver, sms_code)
                logger.info("[Codex][Browser] 已填写手机 OTP")
                human_delay("otp_input")
                if not _click_if_present(driver, ["button[type='submit']", "input[type='submit']"], timeout=10):
                    raise RuntimeError(f"verify_submit_missing: phone verification submit not found state={_phone_page_state(driver)}")
                logger.info("[Codex][Browser] 已提交手机 OTP，等待验证结果")
                otp_outcome = _wait_after_phone_otp_submit(driver, timeout=25)
                logger.info("[Codex][Browser] 手机 OTP 提交后状态：%s", otp_outcome)
                sms_provider.complete(activation_id, http)
                return
            except Exception as exc:
                last_err = exc
                err_text = str(exc) or ""
                # 用户点击停止时，先释放本轮已取号码，再立即退出；不能把停止异常
                # 当成普通手机号错误继续进入下一轮，否则会继续产生接码订单。
                if _is_codex_retry_stopped_exception(exc):
                    if activation_id:
                        try:
                            sms_provider.cancel(activation_id, http, background=True)
                        except Exception:
                            pass
                    logger.info("[Codex][Browser] 收到补跑停止信号，已停止继续换号")
                    raise

                # 号码已经收到短信就已经产生费用。后续即使浏览器无法恢复，也必须
                # 终止本任务的购号循环，绝不能再买第二个号码制造重复扣费。
                if activation_id and sms_received:
                    try:
                        sms_provider.complete(activation_id, http)
                    except Exception:
                        pass
                    logger.error(
                        "[Codex][Browser] 当前号码已收到短信但后续页面处理失败，已停止继续买号：%s",
                        err_text[:240],
                    )
                    raise RuntimeError(
                        f"当前号码已收到短信但浏览器流程未完成，已停止继续买号：{err_text[:180]}"
                    ) from exc

                # 余额不足 / 无可用号码：重试多少次都不会成功，立即失败止损，
                # 避免白等 N 轮换号重试（每轮还要刷新页面 + 随机等待）。
                if any(k in err_text for k in (
                    "NO_BALANCE", "NO_NUMBERS", "WRONG_MAX_PRICE", "SMS_MAX_PRICE", "BALANCE", "余额不足",
                    "暂无可用号码", "没有可用号码", "insufficient", "not enough balance",
                )):
                    raise RuntimeError(
                        f"接码平台余额/价格上限不足或无可用号码，已停止换号止损：{err_text[:180]}"
                    ) from exc
                if "invalid_auth_step" in str(exc):
                    raise RuntimeError(
                        "手机号流程进入 invalid_auth_step，说明授权状态还未从 email-verification 正常跳转或已失效；"
                        "已停止继续换号，避免继续消耗号码"
                    ) from exc

                # WhatsApp/SMS 通道由当前 OAuth 页面决定，换接码国家和号码不会
                # 修复通道错误。当前订单进入取消队列后立即终止，最多只产生一单。
                if err_text.strip().lower().startswith("whatsapp_channel:"):
                    if activation_id:
                        try:
                            sms_provider.cancel(activation_id, http, background=True)
                        except Exception:
                            pass
                    logger.error(
                        "[Codex][Browser] 当前 OAuth 页面不接受 SMS，已停止换号并取消当前订单：%s",
                        err_text[:240],
                    )
                    raise RuntimeError(
                        "当前 OAuth 页面不接受 SMS，已停止继续买号；当前接码订单已进入取消队列"
                    ) from exc

                rotate_number = _phone_error_allows_number_rotation(exc)
                if activation_id:
                    try:
                        if rotate_number and _phone_error_counts_country_failure(exc):
                            sms_provider.report_activation_failure(activation_id, err_text)
                        # 明确号码失败可立即换号，取消继续放后台；页面/自动化故障也
                        # 会尝试回收当前订单，但下面会终止购号循环。
                        sms_provider.cancel(activation_id, http, background=True)
                    except Exception:
                        pass

                if not rotate_number:
                    logger.error(
                        "[Codex][Browser] 手机页面/自动化状态异常，未计入国家失败并停止继续买号：%s",
                        err_text[:240],
                    )
                    raise RuntimeError(
                        f"手机号页面状态异常，已停止继续买号：{err_text[:180]}"
                    ) from exc

                logger.warning("[Codex][Browser] 已确认号码或发送失败，允许直接换号：%s", err_text[:240])
                # 如果已经离开手机号/验证码相关页面，认为通过或不再需要；
                # 如果仍在 phone-verification，则下一轮必须回 add-phone 重新填新号码再提交。
                try:
                    if _is_phone_code_page(driver):
                        logger.info("[Codex][Browser] 当前仍在手机验证码页，下一轮将返回 add-phone 重新设置新号码")
                    else:
                        _find_any(driver, _PHONE_INPUT_SELECTORS, timeout=2)
                except Exception:
                    if _is_add_phone_page(driver) or _is_phone_code_page(driver):
                        logger.info("[Codex][Browser] 仍处于手机号流程，继续换号重试")
                    else:
                        logger.info("[Codex][Browser] 手机输入页已消失，继续后续流程")
                        return
                if attempt < max_retries:
                    _refresh_add_phone_for_retry(driver, reason=str(exc)[:120])
                _sleep_before_phone_retry(attempt, max_retries, deadline=deadline)
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Roxy 手机验证超过整段预算 {total_budget} 秒，已停止继续买号，最后错误：{last_err}"
            )
        raise RuntimeError(f"Roxy 手机验证重试 {max_retries} 次仍失败，最后错误：{last_err}")
    finally:
        try:
            http.close()
        except Exception:
            pass


def _finish_consent_workspace(driver, email: str = "") -> str:
    """点击 Codex consent/workspace 页面里的继续/允许按钮，直到 callback。

    手机验证页可能在最初 8 秒探测窗口之后才出现。Callback 循环必须持续识别
    add-phone/phone-verification，不能在该页面空等到 180 秒超时。
    """
    end = time.time() + int(_roxy_cfg.ROXY_CODEX_CALLBACK_TIMEOUT)
    while time.time() < end:
        callback = _extract_callback_url_from_any_window(driver)
        if callback:
            return callback
        current = str(driver.current_url or "")
        if _has_strict_add_phone_form(driver) or _is_phone_code_page(driver):
            logger.info(
                "[Codex][Browser] Callback 等待期间检测到延迟出现的手机号验证页，立即处理：url=%s",
                current,
            )
            _do_phone_verification_if_present(driver)
            continue
        clicked = False
        if email and _select_existing_account_if_present(driver, email):
            clicked = True
            human_delay("form")
        for selectors in [
            ["//button[contains(., 'Allow')]", "//button[contains(., 'Authorize')]", "//button[contains(., 'Continue')]"],
            ["//button[contains(., 'Select')]", "//button[contains(., 'Use workspace')]", "//button[contains(., 'Confirm')]"],
            ["//button[contains(., '允许')]", "//button[contains(., '授权')]", "//button[contains(., '继续')]", "//button[contains(., '确认')]"],
            ["button[type='submit']"],
        ]:
            if not clicked and _click_if_present(driver, selectors, timeout=2):
                clicked = True
                human_delay("form")
                break
        if not clicked:
            time.sleep(0.8)
    return _wait_for_callback(driver, timeout=5)




def clear_roxy_browser_auth_state(driver) -> None:
    """清空当前 Roxy 浏览器里的 OpenAI/ChatGPT 登录态与缓存，用于注册后复用同一环境跑 Codex。"""
    origins = [
        "https://auth.openai.com",
        "https://chatgpt.com",
        "https://openai.com",
        "https://platform.openai.com",
    ]
    logger.info("[Codex][Browser] 复用注册窗口：开始清理 Cookie / localStorage / sessionStorage / cache")
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass
    try:
        driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
        logger.info("[Codex][Browser] 已清理浏览器 Cookie")
    except Exception as exc:
        logger.info("[Codex][Browser] 清理 Cookie 失败，继续尝试其它缓存：%s", str(exc)[:160])
    try:
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        logger.info("[Codex][Browser] 已清理浏览器 Cache")
    except Exception as exc:
        logger.info("[Codex][Browser] 清理 Cache 失败，继续：%s", str(exc)[:160])
    for origin in origins:
        try:
            driver.execute_cdp_cmd("Storage.clearDataForOrigin", {
                "origin": origin,
                "storageTypes": "all",
            })
            logger.info("[Codex][Browser] 已清理站点数据：%s", origin)
        except Exception as exc:
            logger.debug("[Codex][Browser] 清理站点数据失败 %s: %s", origin, exc)
    try:
        driver.get("about:blank")
    except Exception:
        pass
    time.sleep(1.0)
    logger.info("[Codex][Browser] 注册窗口登录态清理完成，准备开始 Codex 授权")

def _run_roxy_codex_oauth_once(
    email: str,
    otp_provider=None,
    proxy: str | None = None,
    force: bool = False,
    existing_driver=None,
    existing_opened=None,
    reuse_existing_profile: bool = False,
    clear_existing_state: bool = True,
    before_oauth_setup=None,
) -> dict:
    """指纹浏览器 Codex OAuth 入口。

    existing_driver/existing_opened 用于“注册成功后立刻跑 Codex”：
    复用注册时的 Roxy 窗口。默认可清理状态；注册流程会明确选择保留刚建立的登录态。
    """
    from core import codex_oauth as proto

    if not force and not proto._cfg.ENABLE_CODEX_AUTO:
        return proto._codex_result(status="skipped", message="ENABLE_CODEX_AUTO=False")
    if not email:
        return proto._codex_result(status="skipped", message="email 为空")
    if otp_provider is None:
        otp_provider = wait_for_otp

    client = None if reuse_existing_profile else RoxyBrowserClient()
    opened = existing_opened if reuse_existing_profile else client.open_profile(proxy_url=proxy)
    browser_kind_token = _CODEX_BROWSER_KIND.set(_detect_browser_kind(opened))
    driver = existing_driver if reuse_existing_profile else None
    owns_driver = not reuse_existing_profile
    try:
        auth_source = proto._codex_auth_url_source()
        code_verifier = None
        if auth_source == "cpa":
            cpa_auth = proto._request_cpa_authorize_url()
            state = cpa_auth["state"]
            auth_url = cpa_auth["auth_url"]
            logger.info("[Codex][Browser] 当前使用 CPA 授权地址: %s", auth_url)
        elif auth_source == "sub2":
            sub2_auth = proto._request_sub2_authorize_url()
            state = sub2_auth["state"]
            auth_url = sub2_auth["auth_url"]
            logger.info("[Codex][Browser] 当前使用 sub2 授权地址: %s", auth_url)
        elif auth_source == "local":
            code_verifier, code_challenge = proto._generate_pkce()
            state = proto._generate_state()
            # 注册后复用同一窗口时不要附带 prompt=login，否则 OpenAI 会无条件要求
            # 再登录一次。若现有 auth cookie 不可用，页面仍会自然回落到登录流程。
            prompt = None if reuse_existing_profile and not clear_existing_state else "login"
            auth_url = proto._build_authorize_url(state, code_challenge, prompt=prompt)
            logger.info("[Codex][Browser] 当前使用本地 PKCE 授权地址: %s", auth_url)
        else:
            raise RuntimeError(f"[Codex][Browser] 不支持的 CODEX_AUTH_URL_SOURCE={auth_source!r}")

        if not driver:
            driver = _build_driver(opened)
            _center_browser_window(driver)
        driver.set_page_load_timeout(int(_roxy_cfg.ROXY_SELENIUM_TIMEOUT))
        logger.info("[Codex][Browser] 开始授权：%s，profile=%s，reuse_existing_profile=%s", email, opened.profile_id, reuse_existing_profile)
        if reuse_existing_profile and clear_existing_state:
            clear_roxy_browser_auth_state(driver)

        if before_oauth_setup is not None:
            # Codex OAuth 的 auth.openai.com 登录态本身不会建立 ChatGPT 的
            # NextAuth session，直接打开安全设置只会得到没有控件的登录空壳。
            # 缺 2FA 时先独立完成一次 ChatGPT 登录，确认 session 后再设置 2FA；
            # 全程还没有进入手机号页面，因此失败也不会产生接码费用。
            logger.info("[Codex][Browser] 账号缺少 2FA，先建立 ChatGPT 登录态")
            _fill_email_and_otp(driver, email, otp_provider, "https://chatgpt.com/auth/login")
            from core.roxy_registration import _fetch_chatgpt_session

            _fetch_chatgpt_session(driver, timeout=90, auto_jump_wait=10)
            setup_changed = bool(before_oauth_setup(driver))
            if setup_changed:
                logger.info("[Codex][Browser] 2FA 已补齐，重新打开授权地址继续 OAuth")
        _fill_email_and_otp(driver, email, otp_provider, auth_url)
        human_delay("api")
        logger.info("[Codex][Browser] 检查是否需要手机号验证")
        _do_phone_verification_if_present(driver)
        logger.info("[Codex][Browser] 手机验证处理完成/无需处理，等待授权确认和 callback")
        callback_url = _finish_consent_workspace(driver, email=email)
        code = proto._extract_code(callback_url, state)
        logger.info("[Codex][Browser] 已捕获 callback code：%s...", code[:24])

        if auth_source == "cpa":
            submit_payload = proto._submit_cpa_callback(callback_url)
            path = proto._save_cpa_local_record(
                email=email,
                callback_url=callback_url,
                auth_url=auth_url,
                state=state,
                submit_payload=submit_payload,
            )
            msg = submit_payload.get("message") or submit_payload.get("status_message") or "CPA callback submitted"
            return proto._codex_result(
                status="success",
                ok=True,
                email=email,
                file_path=str(path) if path else None,
                callback_url=callback_url,
                message=f"{_codex_driver_name()}: {msg}",
            )

        if auth_source == "sub2":
            submit_payload = proto._submit_sub2_callback(
                callback_url,
                session_id=(sub2_auth or {}).get("session_id", ""),
                redirect_uri=(proto.parse_qs(proto.urlparse(auth_url or "").query).get("redirect_uri") or [""])[0],
            )
            path = proto._save_sub2_local_record(
                email=email,
                callback_url=callback_url,
                auth_url=auth_url,
                state=state,
                submit_payload=submit_payload,
            )
            msg = submit_payload.get("message") or submit_payload.get("status_message") or "sub2 callback uploaded"
            return proto._codex_result(
                status="success",
                ok=True,
                email=email,
                file_path=str(path) if path else None,
                callback_url=callback_url,
                message=f"{_codex_driver_name()}: {msg}",
            )

        if not code_verifier:
            raise RuntimeError("[Codex][Browser] local 模式缺少 code_verifier")
        session = proto.BrowserSession(proxy=proxy)
        token_resp = proto.exchange_codex_token(session, code, code_verifier)
        id_claims = proto._parse_id_token(token_resp.get("id_token", ""))
        effective_email = id_claims.get("email") or email
        storage = proto.build_codex_storage(token_resp, id_claims)
        path = proto.save_codex_credential(storage, effective_email, id_claims.get("plan_type", ""))
        return proto._codex_result(
            status="success",
            ok=True,
            email=effective_email,
            file_path=str(path),
            callback_url=callback_url,
            message=f"{_codex_driver_name()} plan={id_claims.get('plan_type') or 'unknown'}",
        )
    except AccountUnusableError as exc:
        logger.warning("[Codex][Browser] 账号已废：%s，%s", email, exc.error_code)
        return proto._codex_result(
            status="deactivated",
            email=email,
            message=f"账号已废（{exc.error_code or 'account_deactivated'}）",
        )
    except Exception as exc:
        logger.warning("[Codex][Browser] 失败：%s，%s: %s", email, type(exc).__name__, str(exc)[:240])
        logger.debug("[Codex][Browser] 失败详情", exc_info=True)
        return proto._codex_result(status="failed", email=email, message=f"{type(exc).__name__}: {str(exc)[:220]}")
    finally:
        # 注册后复用窗口时，driver/profile 生命周期由注册流程统一清理，
        # 这里不能 quit/delete，否则会提前销毁注册环境。
        if owns_driver and driver and not bool(_roxy_cfg.ROXY_KEEP_BROWSER_OPEN):
            try:
                driver.quit()
            except Exception:
                pass
        if owns_driver and client and not bool(_roxy_cfg.ROXY_KEEP_BROWSER_OPEN):
            client.cleanup_profile(opened)
        try:
            _CODEX_BROWSER_KIND.reset(browser_kind_token)
        except Exception:
            pass


def run_roxy_codex_oauth(
    email: str,
    otp_provider=None,
    proxy: str | None = None,
    force: bool = False,
    existing_driver=None,
    existing_opened=None,
    reuse_existing_profile: bool = False,
    clear_existing_state: bool = True,
    before_oauth_setup=None,
) -> dict:
    """指纹浏览器 Codex OAuth 入口；可恢复错误时重新开启一轮授权。"""
    from core import codex_oauth as proto

    max_rounds = 2
    last_result = None
    for round_no in range(1, max_rounds + 1):
        if round_no > 1:
            logger.warning(
                "[Codex][Browser] 上一轮授权遇到可恢复错误，使用新环境开启第 %s/%s 轮 Codex 授权：%s reason=%s",
                round_no, max_rounds, email, str((last_result or {}).get('message') or '')[:160],
            )
        result = _run_roxy_codex_oauth_once(
            email=email,
            otp_provider=otp_provider,
            proxy=proxy,
            force=force,
            existing_driver=existing_driver,
            existing_opened=existing_opened,
            reuse_existing_profile=reuse_existing_profile,
            clear_existing_state=clear_existing_state,
            before_oauth_setup=before_oauth_setup,
        )
        last_result = result
        if result.get("ok"):
            return result
        msg = result.get("message") or result.get("error") or ""
        retry_whatsapp = (not reuse_existing_profile) and "whatsapp" in str(msg).lower()
        if not (proto._is_cpa_callback_reauth_error(msg) or retry_whatsapp):
            return result
    if last_result:
        last_result = dict(last_result)
        last_message = str(last_result.get("message") or "")
        if proto._is_cpa_callback_reauth_error(last_message):
            last_result["message"] = f"CPA callback 超时，已重新授权 {max_rounds} 轮仍失败：{last_message}"
        else:
            last_result["message"] = f"可恢复授权错误已使用新环境重试 {max_rounds} 轮仍失败：{last_message}"
        return last_result
    return proto._codex_result(status="failed", email=email, message="CPA callback 超时，重新授权失败")
