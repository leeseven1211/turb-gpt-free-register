"""Authenticator MFA and security-settings capabilities."""
from __future__ import annotations

import logging
import inspect
import random
import re
import time
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from core.accounts.export import TwofaProtocolTransportError, setup_2fa_protocol as _setup_2fa_protocol
from core.email.provider import wait_for_otp as _wait_for_otp
from core.operations.runtime import OperationCancelled
from core.auth.state_machine import CancellationRequested, PageState, StageBudget, StageTimeout, classify_page
from core.auth.protocol.session import BrowserSession
from core.auth.page_errors import auth_page_error
from core.email.mailbox_wait import bounded_sleep, use_budget, use_cooperative_wait

from core.auth.browser.auth_context import checkpoint as _checkpoint, current_execution_context, current_override, install_dispatches, time_proxy
from core.auth.browser.email_otp import _clear_otp_inputs, _is_email_verification_page, _type_otp
from core.auth.browser.selenium_dom import _button_after_input, _check_manual_stop, _click_any, _human_click, _human_type_text, _log_prefix, _page_snapshot, _refresh_chatgpt_settings_shell_if_needed, _page_warmup, _roxy_page_state, _visible, _safe_get, _settings_page_not_ready, _wait

wait_for_otp = _wait_for_otp
setup_2fa_protocol = _setup_2fa_protocol
logger = logging.getLogger('core.registration.mfa_auth')
time = time_proxy

_CHATGPT_HOME_URL = "https://chatgpt.com/"

_CHATGPT_SECURITY_SETTINGS_URL = "https://chatgpt.com/#settings/Security"

_CHATGPT_PASSWORD_SETTINGS_URL = _CHATGPT_SECURITY_SETTINGS_URL

_MFA_EMAIL_CODE_SELECTOR = (
    'input[name="code"][autocomplete="one-time-code"], '
    'input[autocomplete="one-time-code"]:not([name="totp_otp"])'
)

_MFA_TOTP_CODE_SELECTOR = 'input[name="totp_otp"]'

_AUTHENTICATOR_TOGGLE_LABELS = frozenset({
    "authenticator", "authenticator app", "ऑथेंटिकेटर ऐप", "身份验证器应用",
    "驗證器應用程式", "認証アプリ",
})

def _probe_existing_roxy_totp(driver, email: str, *, timeout: float = 15.0) -> dict:
    """同浏览器只读确认远端 TOTP 状态，不验证候选密钥，也不修改任何 factor。"""
    _checkpoint()
    try:
        current = urlsplit(str(getattr(driver, "current_url", "") or ""))
        trusted = (current.scheme == "https" and current.hostname == "chatgpt.com"
                   and current.port in (None, 443) and not current.username and not current.password)
    except ValueError:
        trusted = False
    if not trusted:
        return {"confirmed": False, "reason": "untrusted_origin"}
    wait_seconds = min(15.0, max(0.0, float(timeout)))
    context = current_execution_context()
    if context is not None:
        wait_seconds = context.remaining(wait_seconds)
    if wait_seconds <= 0:
        return {"confirmed": False, "reason": "timeout"}
    old_script_timeout = None
    try:
        previous = driver.timeouts.script
        if isinstance(previous, (int, float)):
            old_script_timeout = previous
    except Exception:
        pass
    try:
        driver.set_script_timeout(wait_seconds)
        result = driver.execute_async_script(r"""
        const expectedEmail = String(arguments[0] || '').trim().toLowerCase();
        const timeoutMs = arguments[1];
        const callback = arguments[arguments.length - 1];
        const controller = new AbortController();
        let settled = false;
        const done = (confirmed, reason) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          callback({confirmed, reason});
        };
        const timer = setTimeout(() => {
          controller.abort();
          done(false, 'timeout');
        }, timeoutMs);
        const trusted = () => {
          try {
            const u = new URL(location.href);
            return u.protocol === 'https:' && u.hostname === 'chatgpt.com'
              && (!u.port || u.port === '443') && !u.username && !u.password;
          } catch (_) { return false; }
        };
        (async () => {
          try {
            if (!trusted()) { done(false, 'untrusted_origin'); return; }
            const sessionResp = await fetch('/api/auth/session', {
              method:'GET', credentials:'include', redirect:'error', signal:controller.signal,
              headers:{accept:'application/json'}
            });
            if (sessionResp.status !== 200) { done(false, 'session_http'); return; }
            let session;
            try { session = await sessionResp.json(); }
            catch (_) { done(false, 'session_json'); return; }
            const actualEmail = typeof session?.user?.email === 'string' ? session.user.email.trim().toLowerCase() : '';
            if (!expectedEmail || !actualEmail) { done(false, 'session_identity_unverified'); return; }
            if (actualEmail !== expectedEmail) { done(false, 'session_identity_mismatch'); return; }
            const accessToken = typeof session?.accessToken === 'string' ? session.accessToken.trim() : '';
            if (!accessToken) { done(false, 'session_token_missing'); return; }
            if (!trusted()) { done(false, 'untrusted_origin'); return; }
            const infoResp = await fetch('/backend-api/accounts/mfa_info', {
              method:'GET', credentials:'include', redirect:'error', signal:controller.signal,
              headers:{accept:'application/json', Authorization:'Bearer ' + accessToken}
            });
            if (infoResp.status !== 200) { done(false, 'mfa_http'); return; }
            let info;
            try { info = await infoResp.json(); }
            catch (_) { done(false, 'mfa_json'); return; }
            if (info?.mfa_enabled !== true || info?.mfa_enabled_v2 !== true) {
              done(false, 'mfa_not_enabled'); return;
            }
            const totp = info?.factors?.totp;
            const enabled = Array.isArray(totp) && totp.some(factor => factor && typeof factor === 'object'
              && !Array.isArray(factor) && factor.factor_type === 'totp' && factor.is_recovery === false);
            done(enabled, enabled ? 'totp_enabled' : 'totp_not_enabled');
          } catch (_) { done(false, controller.signal.aborted ? 'timeout' : 'read_failed'); }
        })();
        """, str(email or "").strip(), max(1, int(wait_seconds * 1000) - 50))
    except (StageTimeout, CancellationRequested, OperationCancelled):
        raise
    except Exception:
        result = {"confirmed": False, "reason": "read_failed"}
    finally:
        if old_script_timeout is not None:
            try:
                driver.set_script_timeout(old_script_timeout)
            except Exception:
                pass
    _checkpoint()
    reasons = {
        "untrusted_origin", "timeout", "session_http", "session_json", "session_identity_unverified",
        "session_identity_mismatch", "session_token_missing", "mfa_http", "mfa_json", "mfa_not_enabled",
        "totp_enabled", "totp_not_enabled", "read_failed",
    }
    if not isinstance(result, dict) or result.get("reason") not in reasons:
        return {"confirmed": False, "reason": "invalid_response"}
    reason = result["reason"]
    return {"confirmed": result.get("confirmed") is True and reason == "totp_enabled", "reason": reason}


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

def _find_authenticator_toggle(driver):
    """优先使用旧稳定标记；新版仅按可信安全页的精确关联标签识别唯一开关。"""
    from selenium.webdriver.common.by import By

    legacy = _first_visible_css(driver, '[data-testid="mfa-authenticator-toggle"]')
    if legacy is not None:
        return legacy

    def trusted_security_page() -> bool:
        current = urlsplit(str(getattr(driver, "current_url", "") or ""))
        if (current.scheme != "https" or current.hostname != "chatgpt.com"
                or current.port not in (None, 443) or current.username is not None or current.password is not None):
            return False
        path = current.path.lower().rstrip("/")
        fragment = current.fragment.lower().rstrip("/")
        return path == "/settings/security" or (not path and fragment == "settings/security")

    try:
        if not trusted_security_page():
            return None
        matches = []
        for element in driver.find_elements(By.CSS_SELECTOR, '[role="switch"][aria-labelledby]'):
            if not _visible(element):
                continue
            label_ids = str(element.get_attribute("aria-labelledby") or "").split()
            if not label_ids:
                continue
            labels = []
            for label_id in label_ids:
                targets = driver.find_elements(By.ID, label_id)
                if len(targets) != 1:
                    break
                labels.append(str(targets[0].get_attribute("textContent") or ""))
            if len(labels) != len(label_ids):
                continue
            name = re.sub(r"\s+", " ", " ".join(labels)).strip().casefold()
            if name in _AUTHENTICATOR_TOGGLE_LABELS:
                matches.append(element)
        return matches[0] if len(matches) == 1 and trusted_security_page() else None
    except (StageTimeout, CancellationRequested, OperationCancelled):
        raise
    except Exception:
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

def _detect_mfa_enrollment_step(driver, *, monitor_mfa_enrollment: bool = False):
    """默认沿用原字段识别；显式监控才读取实际安全页与活动弹窗语义。"""
    if not monitor_mfa_enrollment:
        totp_field = _first_visible_css(driver, _MFA_TOTP_CODE_SELECTOR)
        if totp_field is not None:
            return "totp", totp_field
        email_code_field = _first_visible_css(driver, _MFA_EMAIL_CODE_SELECTOR)
        if email_code_field is not None:
            return "email", email_code_field
        return None, None
    _check_manual_stop()
    snapshot = driver.execute_script(r"""
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const text = el => String(el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim();
    const all = [...document.querySelectorAll('dialog[open],[role="dialog"]')].filter(visible);
    const dialogs = all.filter(dlg => !all.some(other => other !== dlg && dlg.contains(other)));
    return {url:location.href,title:document.title,ready_state:document.readyState,text:text(document.body).slice(0, 4000),
      alerts:[...document.querySelectorAll('[role="alert"],[aria-live="assertive"]')].filter(visible).map(text).filter(Boolean),
      dialogs:dialogs.map(dlg => ({
        title:[...(dlg.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean)
          .map(id => text(document.getElementById(id))),
          ...[...dlg.querySelectorAll('h1,h2,h3,[role="heading"]')].filter(visible).map(text)].join(' '),
        text:text(dlg).slice(0,4000),settings_shell:dlg.getAttribute('data-testid') === 'modal-settings',
        fields:[...dlg.querySelectorAll('input[name="totp_otp"],input[name="verification-code"],input[name="code"],input[autocomplete="one-time-code"]')]
          .filter(el => visible(el) && !el.disabled && !el.readOnly).map(el => ({element:el,
            name:el.getAttribute('name') || '',autocomplete:el.getAttribute('autocomplete') || '',
            invalid:el.getAttribute('aria-invalid') === 'true'}))
      }))};
    """)
    if not isinstance(snapshot, dict):
        return None, None
    try:
        location = urlsplit(str(snapshot.get("url") or ""))
        trusted = (location.scheme == "https" and location.hostname == "chatgpt.com"
                   and location.port in (None, 443) and not location.username and not location.password)
        security = trusted and (location.path.lower().rstrip("/") == "/settings/security"
            or (not location.path.rstrip("/") and location.fragment.lower().rstrip("/") == "settings/security"))
    except ValueError:
        return None, None
    body = str(snapshot.get("text") or "")
    if location.scheme == "chrome-error" or trusted:
        network = re.search(r"\bERR_(?:TUNNEL_CONNECTION_FAILED|PROXY_CONNECTION_FAILED|CONNECTION_RESET|CONNECTION_CLOSED|HTTP2_PING_FAILED|NAME_NOT_RESOLVED)\b", body)
        if network:
            raise RuntimeError(f"mfa_network_error: net::{network.group(0)}")
    error = auth_page_error(snapshot)
    if error is not None:
        raise error
    if not security:
        return None, None
    alerts = " ".join(str(value) for value in snapshot.get("alerts") or [])
    if re.search(r"error|failed|invalid|incorrect|couldn.?t|cannot|unable|went wrong|try again|错误|失敗|失败|无效|重试|गलत|गड़बड़ी|गड़बड़ी|अमान्य|दोबारा", alerts, re.IGNORECASE) or re.search(r"\bfailed to fetch\b", body, re.IGNORECASE):
        raise RuntimeError("mfa_enrollment_page_error: MFA 页面显示明确错误")
    dialogs = snapshot.get("dialogs") or []
    document_ready = snapshot.get("ready_state") in {"interactive", "complete"} and bool(body.strip())
    if not dialogs and document_ready:
        return "complete", None
    if len(dialogs) != 1:
        return None, None
    dialog = dialogs[0]
    title = str(dialog.get("title") or "").casefold()
    text = str(dialog.get("text") or "").casefold()
    combined = title + " " + text
    if re.search(r"\bsms\b|text message|push notification|短信|简讯|推送|एसएमएस|पुश", combined):
        raise RuntimeError("mfa_enrollment_unsupported: 当前为短信或推送验证，不能当作邮箱或 Authenticator 验证码")
    fields = dialog.get("fields") or []
    authenticator = bool(re.search(r"authenticator|ऑथेंटिकेटर|身份验证器|驗證器|認証アプリ", combined))
    setup = bool(re.search(r"qr|scan|manual|setup|connect|6.?digit|स्कैन|मैन्युअल|कनेक्ट|6.?अंक|扫码|手动|手動|スキャン", combined))
    legacy = any(field.get("name") == "totp_otp" for field in fields)
    if legacy or authenticator and setup:
        if len(fields) != 1:
            return "transition", None
        field = fields[0]
        if field.get("invalid") is True:
            raise RuntimeError("totp_rejected: Authenticator 验证码被页面判定为无效")
        return "totp", field.get("element")
    email = bool(re.search(r"(?:check|verify|confirm) your email|code we sent.*email|email.*(?:sent|verification|code)|查看.*邮|邮件.*(?:验证码|已发)|邮箱.*验证码|ईमेल.*(?:भेज|कोड)|इनबॉक्स", combined))
    if email and len(fields) == 1:
        field = fields[0]
        if field.get("invalid") is True:
            raise RuntimeError("email_otp_invalid: 2FA 邮箱重认证验证码被页面判定为无效")
        return "email", field.get("element")
    if dialog.get("settings_shell") is True and not fields and document_ready:
        return "complete", None
    return None, None


class _MfaStepChanged(Exception):
    """邮箱读取期间实际页面已转入TOTP；不冒充用户取消或邮件成功。"""

    def __init__(self, field):
        self.field = field


def _wait_mfa_email_code(driver, email, after_ts, provider):
    """同worker协作收码，原发码边界及总预算只创建一次。"""
    _check_manual_stop()
    from config import email as email_cfg

    timeout = max(1, int(getattr(email_cfg, "OTP_MAX_WAIT", 240)))
    context = current_execution_context()
    remaining = context.remaining(timeout) if context is not None else timeout
    budget = StageBudget.start(remaining, cancel=lambda: (_check_manual_stop(), False)[1])
    try:
        parameters = inspect.signature(provider).parameters.values()
        accepts_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters)
        names = {parameter.name for parameter in parameters}
    except (TypeError, ValueError):
        names, accepts_kwargs = set(), False
    if not accepts_kwargs and not {"page_checkpoint", "max_wait"}.issubset(names):
        raise RuntimeError("mfa_otp_provider_not_cooperative: MFA 收码适配器必须支持页面检查点与等待预算")

    def page_checkpoint():
        _check_manual_stop()
        budget.require("2FA 邮箱重认证")
        step, field = _detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)
        if step == "totp":
            raise _MfaStepChanged(field)

    try:
        with use_budget(budget), use_cooperative_wait(page_checkpoint):
            kwargs = {"after_ts": after_ts, "max_wait": budget.remaining(), "page_checkpoint": page_checkpoint}
            if accepts_kwargs or "budget" in names:
                kwargs["budget"] = budget
            code = provider(email, **kwargs)
            # 候选返回时重判实际字段；转场空壳只占用原预算，不能填旧字段。
            while True:
                page_checkpoint()
                step, field = _detect_mfa_enrollment_step(driver, monitor_mfa_enrollment=True)
                if step == "email" and field is not None:
                    return "email", field, code
                bounded_sleep(0.25)
    except _MfaStepChanged as changed:
        logger.info("%s[2FA] 收邮件期间已观察到 Authenticator 页面，结束无关邮件等待", _log_prefix(driver))
        return "totp", changed.field, None

def _wait_mfa_enrollment_step(driver, *, timeout: int = 90, monitor_mfa_enrollment: bool = False):
    end = time.time() + max(1, int(timeout))
    last_url = ""
    while time.time() < end:
        _check_manual_stop()
        step, field = _detect_mfa_enrollment_step(
            driver, **({"monitor_mfa_enrollment": True} if monitor_mfa_enrollment else {}),
        )
        if step and (not monitor_mfa_enrollment or step in {"email", "totp"}):
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
    monitor_mfa_enrollment: bool = False,
):
    """邮箱重认证提交后等待二维码页；若仍停在原表单，仅补交一次。"""
    started = time.monotonic()
    deadline = started + max(3, int(timeout or 30))
    resubmitted = False
    last_step = "transition"
    last_url = ""
    while time.monotonic() < deadline:
        _check_manual_stop()
        step, field = _detect_mfa_enrollment_step(
            driver, **({"monitor_mfa_enrollment": True} if monitor_mfa_enrollment else {}),
        )
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
        toggle = _find_authenticator_toggle(driver)
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
        current = _find_authenticator_toggle(driver)
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
    from core.accounts.credentials import get_account_login_credentials

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

def _read_totp_secret_from_dialog(driver, field, *, monitor_mfa_enrollment: bool = False) -> str | None:
    """Read an Authenticator secret without activating any external-protocol link."""
    values = driver.execute_script(r"""
    const input = arguments[0];
    const monitored = arguments[1] === true;
    const root = monitored ? input.closest('[role="dialog"],dialog[open]')
      : (input.closest('[role="dialog"]') || document);
    if (!root) return [];
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
    """, field, monitor_mfa_enrollment) or []
    for value in values:
        secret = _totp_secret_candidate(value)
        if secret:
            return secret
    return None

def _manual_totp_secret(driver, field, *, timeout: int = 20, monitor_mfa_enrollment: bool = False) -> str:
    """Read the QR binding URI, or safely switch the dialog to a manual key."""
    monitor_kwargs = {"monitor_mfa_enrollment": True} if monitor_mfa_enrollment else {}
    secret = _read_totp_secret_from_dialog(driver, field, **monitor_kwargs)
    if secret:
        logger.info("%s[2FA] 已从二维码绑定信息读取 Authenticator key，未打开外部应用", _log_prefix(driver))
        return secret

    manual_button = driver.execute_script(r"""
    const input = arguments[0];
    const monitored = arguments[1] === true;
    const root = monitored ? input.closest('[role="dialog"],dialog[open]')
      : (input.closest('[role="dialog"]') || input.closest('form') || document);
    if (!root) return null;
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
    const monitoredWanted = /स्कैन नहीं कर पा रहे|कोड मैन्युअल रूप से डालें/;
    const unwanted = /cancel|close|back|previous|キャンセル|閉じる|戻る|取消|关闭|返回/;
    return candidates.find(el => (wanted.test(attrs(el)) || monitored && monitoredWanted.test(attrs(el)))
      && !unwanted.test(attrs(el)) && !external(el)) || null;
    """, field, monitor_mfa_enrollment)
    if not manual_button:
        raise RuntimeError("TOTP 设置弹窗未提供安全可点击的手动密钥入口")
    _human_click(driver, manual_button, label="totp_show_manual_secret")

    end = time.time() + max(2, int(timeout))
    while time.time() < end:
        _check_manual_stop()
        if monitor_mfa_enrollment:
            step, current_field = _detect_mfa_enrollment_step(driver, **monitor_kwargs)
            if step == "email":
                raise RuntimeError("mfa_enrollment_step_changed: 读取密钥时页面返回邮箱重认证，未继续激活")
            secret = _read_totp_secret_from_dialog(driver, current_field, **monitor_kwargs) if step == "totp" and current_field is not None else None
        else:
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
    otp_provider=None,
    monitor_mfa_enrollment: bool = False,
) -> str:
    """默认保留共享设置行为；本地 Roxy 注册可显式启用持续页面监控。"""
    import pyotp

    monitor_kwargs = {"monitor_mfa_enrollment": True} if monitor_mfa_enrollment else {}
    recovered = _totp_secret_candidate(existing_secret)
    if recovered and not force_reconfigure:
        evidence = _probe_existing_roxy_totp(driver, email)
        if evidence["reason"] in {"session_identity_unverified", "session_identity_mismatch"}:
            raise RuntimeError(f"{evidence['reason']}: 远端 TOTP 状态核验未匹配当前任务身份")
        if evidence["confirmed"]:
            logger.info("%s[2FA] 只读接口已确认远端 TOTP 启用，保留本地检查点密钥", _log_prefix(driver))
            return recovered
        logger.info("%s[2FA] 远端 TOTP 只读核验未确认，继续安全设置页：reason=%s", _log_prefix(driver), evidence["reason"])
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
            toggle = _find_authenticator_toggle(driver)
            if toggle is None:
                raise RuntimeError("关闭旧 Authenticator 后未找到新的设置开关")
        else:
            recovered = _totp_secret_candidate(existing_secret)
            if recovered:
                if monitor_mfa_enrollment:
                    step, _field = _detect_mfa_enrollment_step(driver, **monitor_kwargs)
                    if step != "complete":
                        raise RuntimeError("mfa_activation_unconfirmed: 开关已启用但安全页仍有未确认的弹窗步骤")
                    evidence = _probe_existing_roxy_totp(driver, email)
                    if not evidence["confirmed"]:
                        raise RuntimeError(f"mfa_activation_unconfirmed: 既有密钥远端状态未通过同邮箱只读核验，reason={evidence['reason']}")
                    logger.info("%s[2FA] 已确认开关与同邮箱远端 TOTP，保留本地检查点密钥", _log_prefix(driver))
                else:
                    logger.info("%s[2FA] 已确认远端 Authenticator 开关启用，保留本地检查点密钥", _log_prefix(driver))
                return recovered
            raise RuntimeError("Authenticator 2FA 已启用，但当前流程无法恢复既有 secret")

    otp_after_ts = time.time()
    _human_click(driver, toggle, label="mfa_authenticator_toggle")
    step, field = _wait_mfa_enrollment_step(driver, timeout=90, **monitor_kwargs)
    if step == "email":
        logger.info("%s[2FA] 当前会话要求邮箱重认证", _log_prefix(driver))
        _check_manual_stop()
        provider = otp_provider or wait_for_otp
        if monitor_mfa_enrollment:
            step, field, email_code = _wait_mfa_email_code(driver, email, otp_after_ts, provider)
        else:
            email_code = provider(email, after_ts=otp_after_ts)
        if step == "email":
            _human_type_text(driver, field, email_code, clear=True)
            submit_email_code = _button_after_input(driver, field)
            if not submit_email_code:
                raise RuntimeError("2FA 重认证页缺少验证码提交按钮")
            _human_click(driver, submit_email_code, label="mfa_reauth_otp_submit")
            logger.info("%s[2FA] 已提交邮箱重认证验证码", _log_prefix(driver))
            totp_field = _wait_after_mfa_email_submit(driver, timeout=30, resubmit_after=8, **monitor_kwargs)
        else:
            totp_field = field
    else:
        # 刚完成注册时 pwd_auth_time 足够新，OpenAI 会直接展示二维码而不再发邮件。
        logger.info("%s[2FA] 当前登录态仍新鲜，已跳过邮箱重认证并直达二维码设置页", _log_prefix(driver))
        totp_field = field
    secret = _manual_totp_secret(driver, totp_field, **monitor_kwargs)
    # 必须在激活前持久化：一旦 OpenAI 接受下面的 TOTP，若进程恰好中断，
    # 没有这个 secret 就无法再次登录账号。
    if on_secret is not None:
        on_secret(secret)

    # Avoid submitting a code in the final few seconds of its validity window.
    remaining = 30 - (int(time.time()) % 30)
    if remaining < 6:
        time.sleep(remaining + 1)
    if monitor_mfa_enrollment:
        step, totp_field = _detect_mfa_enrollment_step(driver, **monitor_kwargs)
        if step != "totp" or totp_field is None:
            raise RuntimeError("mfa_enrollment_step_changed: 激活前已不是原 Authenticator 设置步骤，未提交验证码")
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
        if monitor_mfa_enrollment:
            step, current_field = _detect_mfa_enrollment_step(driver, **monitor_kwargs)
        current_toggle = _find_authenticator_toggle(driver)
        enabled = current_toggle is not None and (
            str(current_toggle.get_attribute("aria-checked") or "").lower() == "true"
            or str(current_toggle.get_attribute("data-state") or "").lower() == "checked"
        )
        if monitor_mfa_enrollment:
            complete = step == "complete"
        else:
            complete = enabled and _first_visible_css(driver, 'input[name="totp_otp"]') is None
        if enabled and complete:
            if monitor_mfa_enrollment:
                evidence = _probe_existing_roxy_totp(driver, email, timeout=min(15.0, max(0.0, end - time.time())))
                if not evidence["confirmed"]:
                    raise RuntimeError(f"mfa_activation_unconfirmed: 开关已启用但同邮箱只读核验未通过，reason={evidence['reason']}")
                logger.info("%s[2FA] Authenticator 开关及同邮箱远端 TOTP 均已确认启用", _log_prefix(driver))
            else:
                logger.info("%s[2FA] Authenticator 2FA 已启用", _log_prefix(driver))
            return secret
        if not monitor_mfa_enrollment:
            current_field = _first_visible_css(driver, _MFA_TOTP_CODE_SELECTOR)
        # The code can cross a 30-second boundary while ChatGPT is processing
        # the first click. If the dialog is still present, submit one fresh
        # code instead of waiting until the whole step times out.
        fresh_code = pyotp.TOTP(secret).now()
        if (not monitor_mfa_enrollment or step == "totp") and current_field is not None and not resubmitted and fresh_code != submitted_code:
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
    otp_provider=None,
    before_browser=None,
    monitor_mfa_enrollment: bool = False,
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
            fallback_kwargs = dict(
                on_secret=_remember_secret,
                existing_secret=checkpoint["secret"] or None,
            )
            if otp_provider is not None:
                fallback_kwargs["otp_provider"] = otp_provider
            if monitor_mfa_enrollment:
                fallback_kwargs["monitor_mfa_enrollment"] = True
            if before_browser is not None:
                before_browser()
            secret = setup_roxy_2fa(
                driver,
                email,
                **fallback_kwargs,
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
    "_first_visible_css", "_find_authenticator_toggle", "_is_stale_element_error", "_visible_new_password_inputs",
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
    "_totp_secret_candidate", "_first_visible_css", "_find_authenticator_toggle", "_is_stale_element_error",
    "_visible_new_password_inputs", "_wait_visible_css", "_detect_mfa_enrollment_step",
    "_wait_mfa_enrollment_step", "_wait_after_mfa_email_submit",
    "_dismiss_single_action_dialog", "_dismiss_chatgpt_pricing_modal",
    "_click_chatgpt_settings_control", "_reveal_chatgpt_settings_navigation",
    "_click_password_setting_fallback", "_open_chatgpt_security_settings",
    "_disable_roxy_2fa", "_complete_settings_email_reauth",
    "_read_totp_secret_from_dialog", "_manual_totp_secret", "setup_roxy_2fa",
    "setup_protocol_2fa_with_browser_fallback",
]
