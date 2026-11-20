"""Roxy account password settings execution; durable candidates belong to callers."""

from __future__ import annotations
import logging
import random
import re
from urllib.parse import urlsplit
from core.auth.challenge import PasswordSetupNotReadyError
from core.auth.browser.auth_context import time_proxy as time
from core.auth.browser.selenium_dom import (
    _button_after_input,
    _check_manual_stop,
    _human_click,
    _human_type_text,
    _log_prefix,
    _page_warmup,
    _refresh_chatgpt_settings_shell_if_needed,
    _safe_get,
    _settings_page_not_ready,
)
from core.kernels.browser.roxy.twofa import (
    _click_chatgpt_settings_control,
    _click_password_setting_fallback,
    _complete_settings_email_reauth,
    _dismiss_chatgpt_pricing_modal,
    _dismiss_single_action_dialog,
    _is_stale_element_error,
    _reveal_chatgpt_settings_navigation,
    _visible_new_password_inputs,
)

logger = logging.getLogger("core.registration.password_auth")
_CHATGPT_PASSWORD_SETTINGS_URL = "https://chatgpt.com/#settings/Security"


class PasswordSetupResultUnknownError(RuntimeError):
    """添加密码已提交，但本次远端结果仍无法确认。"""

    code = "password_setup_result_unconfirmed"
    request_unknown = True

    def __init__(self):
        super().__init__(
            "request_unknown: password_setup_result_unconfirmed: 添加密码已提交，尚未取得明确成功结果，已保留候选"
        )


def _password_setup_success_marker(state: object) -> str:
    """只识别可信页面明确表示密码已完成的文案，空壳和表单消失均不算。"""
    if not isinstance(state, dict):
        return ""
    try:
        url = urlsplit(str(state.get("url") or ""))
        if (
            url.scheme != "https"
            or url.hostname not in {"chatgpt.com", "auth.openai.com"}
            or url.port not in (None, 443)
            or url.username
            or url.password
        ):
            return ""
    except ValueError:
        return ""
    text = re.sub(r"\s+", " ", str(state.get("body") or "")).strip().casefold()
    patterns = (
        r"\b(?:your\s+)?password\s+(?:(?:has\s+been|was)\s+)?(?:successfully\s+)?(?:added|set|created|updated|changed)(?:\s+successfully)?\b",
        r"密码(?:已|已经|已經)(?:成功)?(?:添加|新增|设置|設定|创建|建立|更新|修改|更改)",
        r"密码(?:添加|新增|设置|設定|创建|更新|修改|更改)成功",
        r"パスワード(?:を|が)?(?:正常に)?(?:追加|設定|作成|更新|変更)(?:されました|しました|しました。)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match is not None:
            context = text[max(0, match.start() - 25) : match.end() + 30]
            if re.search(r"\b(?:not|failed|failure|unable)\b|失败|失敗|未成功", context):
                continue
            return match.group(0)
    return ""


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
    on_password_prepared=None,
    on_password_submitted=None,
    _button_after_input=_button_after_input,
    _check_manual_stop=_check_manual_stop,
    _click_chatgpt_settings_control=_click_chatgpt_settings_control,
    _click_password_setting_fallback=_click_password_setting_fallback,
    _complete_settings_email_reauth=_complete_settings_email_reauth,
    _dismiss_chatgpt_pricing_modal=_dismiss_chatgpt_pricing_modal,
    _dismiss_single_action_dialog=_dismiss_single_action_dialog,
    _human_click=_human_click,
    _human_type_text=_human_type_text,
    _is_stale_element_error=_is_stale_element_error,
    _log_prefix=_log_prefix,
    _page_warmup=_page_warmup,
    _password_setup_success_marker=_password_setup_success_marker,
    _probe_chatgpt_password_eligibility=_probe_chatgpt_password_eligibility,
    _refresh_chatgpt_settings_shell_if_needed=_refresh_chatgpt_settings_shell_if_needed,
    _reveal_chatgpt_settings_navigation=_reveal_chatgpt_settings_navigation,
    _safe_get=_safe_get,
    _settings_page_not_ready=_settings_page_not_ready,
    _visible_new_password_inputs=_visible_new_password_inputs,
    clock=time,
    navigation_timeout=lambda: 90,
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
        timeout=min(45, int(navigation_timeout())),
        attempts=2,
        accept_hosts=("chatgpt.com",),
    )
    _page_warmup(driver, reason="chatgpt_password_settings")
    settings_shell_refreshes = int(
        _refresh_chatgpt_settings_shell_if_needed(driver, reason="chatgpt_password_settings")
    )
    end = clock.time() + max(10, int(timeout))
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

    while clock.time() < end:
        _check_manual_stop()
        if _dismiss_chatgpt_pricing_modal(driver):
            continue
        if _dismiss_single_action_dialog(driver):
            clock.sleep(1.0)
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
            end = max(end, clock.time() + 45)
            continue
        state = (
            driver.execute_script(r"""
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
          body: (document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 3000),
          password_controls: controls,
          password_lines: lines,
          profile_action: profileAction,
          settings_action: settingsAction,
          security_action: securityAction,
          page_meta: JSON.stringify(pageMeta),
        };
        """)
            or {}
        )
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
                clock.sleep(0.8)
                continue
        if action is None and settings_action is None and security_action is None and profile_action is None:
            if (
                settings_shell_refreshes < 2
                and not last_password_controls
                and not last_password_lines
                and _refresh_chatgpt_settings_shell_if_needed(driver, reason="chatgpt_password_settings_empty_shell")
            ):
                settings_shell_refreshes += 1
                clock.sleep(0.8)
                continue
        if (
            security_action is None
            and settings_clicks >= 1
            and settings_navigation_reveals < 5
            and _reveal_chatgpt_settings_navigation(driver)
        ):
            settings_navigation_reveals += 1
            clock.sleep(0.8)
            continue
        if action is not None:
            _click_chatgpt_settings_control(driver, action, label="account_password_settings")
            action = None
            clock.sleep(0.8)
        elif security_action is not None and security_clicks < 1:
            _click_chatgpt_settings_control(driver, security_action, label="chatgpt_security_navigation")
            security_clicks += 1
            clock.sleep(1.2)
        elif settings_action is not None and settings_clicks < 1:
            _click_chatgpt_settings_control(driver, settings_action, label="chatgpt_settings_navigation")
            settings_clicks += 1
            clock.sleep(1.2)
        elif profile_action is not None and profile_clicks < 1:
            _click_chatgpt_settings_control(driver, profile_action, label="chatgpt_profile_menu")
            profile_clicks += 1
            clock.sleep(0.8)
        else:
            clock.sleep(0.5)

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
                _log_prefix(driver),
                diagnostic,
            )
            raise PasswordSetupNotReadyError(f"账号设置页尚未稳定或添加密码入口未打开，页面诊断：{diagnostic}")
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
        raise RuntimeError(f"账号设置只提供当前密码输入框，未进入“Add password/设置密码”流程；页面诊断：{diagnostic}")

    previous_success_marker = _password_setup_success_marker(state)
    # 真实新密码表单已就绪；派发前保存同一候选，点击抛异常也能恢复。
    if on_password_prepared is not None:
        on_password_prepared(normalized)
    for submit_attempt in range(2):
        try:
            for field in new_inputs:
                _human_type_text(driver, field, normalized, clear=True)
            submit = _button_after_input(driver, new_inputs[-1])
            if submit is not None:
                _human_click(driver, submit, label="account_password_submit")
            else:
                submitted = bool(
                    driver.execute_script(
                        r"""
                const input = arguments[0];
                const form = input?.closest('form');
                if (!form) return false;
                if (typeof form.requestSubmit === 'function') form.requestSubmit();
                else form.submit();
                return true;
                """,
                        new_inputs[-1],
                    )
                )
                if not submitted:
                    raise RuntimeError("账号密码设置页缺少提交按钮")
            break
        except Exception as exc:
            if submit_attempt == 0 and _is_stale_element_error(exc):
                logger.warning(
                    "%s 新增密码表单已被页面重绘，重新获取控件后重试一次：email=%s",
                    _log_prefix(driver),
                    email,
                )
                clock.sleep(random.uniform(0.2, 0.6))
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

    end = clock.time() + max(8, int(timeout))
    last_text = ""
    while clock.time() < end:
        _check_manual_stop()
        try:
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
        return {url: location.href, inputs, errors,
          body: (document.body?.innerText || '').replace(/\\s+/g, ' ').slice(0, 3000)};
        """)
        except Exception:
            # 页面跳转或采集异常只消耗本次确认预算，不能据读取失败确认成功。
            state = None
        if not isinstance(state, dict):
            clock.sleep(0.5)
            continue
        marker = _password_setup_success_marker(state)
        last_text = "; ".join((state.get("errors") or [])[:3]) or str(state.get("body") or "")[-400:]
        errors = [
            item
            for item in state.get("errors") or []
            if not _password_setup_success_marker({"url": state.get("url"), "body": item})
        ]
        if errors:
            raise RuntimeError(f"账号密码设置失败：{last_text}")
        if marker and marker != previous_success_marker and not state.get("inputs"):
            logger.info("%s 已补充 ChatGPT 账号密码：email=%s length=%s", _log_prefix(driver), email, len(normalized))
            return normalized
        clock.sleep(0.5)
    raise PasswordSetupResultUnknownError()
