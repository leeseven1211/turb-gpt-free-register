"""DOM snapshots, page recognition, and bounded Selenium interactions."""
from __future__ import annotations

import json
import logging
import math
import random
import re
import string
import time
from pathlib import Path
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from core.humanize import delay as _human_delay
from core.registration.state_machine import PageState, StageBudget, StageTimeout, classify_page

from .auth_context import (
    checkpoint as _checkpoint,
    current_execution_context,
    install_dispatches,
    remaining_timeout,
    time_proxy,
)
from .selenium_resource import _browser_actions_enabled, _log_prefix, _safe_get

human_delay = _human_delay
logger = logging.getLogger(__name__)
time = time_proxy

def _wait(driver, timeout: int | None = None):
    from selenium.webdriver.support.ui import WebDriverWait
    return WebDriverWait(driver, timeout or int(_cfg.ROXY_SELENIUM_TIMEOUT))

def _budget_timeout(budget: StageBudget | None, default: float, *, minimum: float = 0.1) -> float:
    """Return a child timeout without ever extending the stage deadline."""
    default = float(default)
    context = current_execution_context() if budget is None else None
    if budget is None:
        budget = context.budget if context is not None else None
    if budget is None:
        # A cancellation-only context does not bound a legacy explicit
        # timeout. In particular, timeout=0 is an intentional immediate
        # observation used by compatibility tests and state probes.
        if default <= 0 or context is None or context.deadline is None:
            return max(minimum, default)
        bounded = remaining_timeout(default)
        if bounded <= 0:
            raise StageTimeout("认证执行 context deadline exhausted")
        return min(default, bounded)
    remaining = budget.remaining()
    if remaining <= 0:
        raise StageTimeout("Roxy registration stage timeout exhausted")
    # A minimum is useful for legacy callers, but must never make a bounded
    # child outlive its parent stage.
    return min(default, remaining)

def _roxy_page_state(driver, *, access_token: bool | None = None) -> PageState:
    """Classify the current page from a bounded DOM snapshot."""
    try:
        snapshot = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const fields = [...document.querySelectorAll('input,textarea,select')].filter(visible).map(el => ({
          type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
          autocomplete: el.getAttribute('autocomplete') || '', inputmode: el.getAttribute('inputmode') || '',
          aria: el.getAttribute('aria-label') || '', visible: true, value: el.type === 'password' ? '<password>' : (el.value || '')
        })).slice(0, 30);
        const forms = [...document.querySelectorAll('form')].filter(visible).map(el => ({action: el.getAttribute('action') || ''}));
        const buttons = [...document.querySelectorAll('button,a,[role=button],input[type=submit]')].filter(visible).map(el => ({
          text: (el.innerText || el.textContent || el.value || '').replace(/\\s+/g, ' ').trim().slice(0, 160),
          name: el.getAttribute('name') || '', value: el.getAttribute('value') || '', aria: el.getAttribute('aria-label') || ''
        })).slice(0, 30);
        return {url: location.href, title: document.title, text: (document.body?.innerText || '').slice(0, 2000), inputs: fields, forms, buttons};
        """) or {}
    except Exception:
        snapshot = {"url": getattr(driver, "current_url", "")}
    return classify_page(snapshot, access_token=bool(access_token))

def _auth_terminal_page_state(driver) -> PageState | None:
    """Detect known callback errors/logout before entering a long session poll."""
    try:
        url = str(getattr(driver, "current_url", "") or "")
    except Exception:
        url = ""
    lowered = url.lower()
    if any(marker in lowered for marker in ("/auth/error", "oauth_error", "callback_error", "/auth/logout", "/session-ended")):
        return classify_page({"url": url})
    try:
        text = str(driver.execute_script("return (document.body && document.body.innerText) || '';" ) or "").lower()
    except Exception:
        text = ""
    if any(marker in text for marker in ("oauth callback error", "authentication error", "session has ended", "you have been logged out")):
        return PageState.AUTH_ERROR if "error" in text or "callback" in text else PageState.LOGGED_OUT
    return None

def _visible(el) -> bool:
    try:
        return el.is_displayed() and el.is_enabled()
    except Exception:
        return False

def _human_scroll_to(driver, el) -> None:
    try:
        block = random.choice(["center", "nearest", "center"])
        driver.execute_script("arguments[0].scrollIntoView({block: arguments[1], inline:'nearest'});", el, block)
        if _browser_actions_enabled():
            time.sleep(random.uniform(0.08, 0.35))
            # 轻微滚动抖动，避免每次都精准居中。
            driver.execute_script("window.scrollBy(0, arguments[0]);", random.randint(-90, 90))
            time.sleep(random.uniform(0.05, 0.22))
            driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", el)
    except Exception:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass

def _human_click(driver, el, *, label: str = "") -> None:
    """快速人工化点击。

    之前用 ActionChains 在 Roxy/Chrome 150 上偶发卡住 1-2 分钟，导致邮箱提交很慢。
    这里改为 CDP 派发鼠标事件；没有 CDP 时再用 JS/原生 click 兜底。
    """
    _human_scroll_to(driver, el)
    if not _browser_actions_enabled():
        time.sleep(0.2)
        el.click()
        return
    try:
        human_delay("click")
        point = driver.execute_script(r"""
        const el = arguments[0];
        const r = el.getBoundingClientRect();
        const x = r.left + r.width * (0.30 + Math.random() * 0.40);
        const y = r.top + r.height * (0.35 + Math.random() * 0.30);
        return {x, y, w:r.width, h:r.height};
        """, el) or {}
        x = float(point.get("x") or 0)
        y = float(point.get("y") or 0)
        if hasattr(driver, "execute_cdp_cmd") and x > 0 and y > 0:
            driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
            time.sleep(random.uniform(0.05, 0.22))
            driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
            time.sleep(random.uniform(0.035, 0.13))
            driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
        else:
            driver.execute_script(r"""
            const el = arguments[0];
            el.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true, cancelable:true, pointerType:'mouse'}));
            el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true, view:window}));
            el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true, view:window}));
            el.click();
            """, el)
    except Exception as exc:
        logger.debug("%s 人工化点击失败，回退 el.click label=%s err=%s", _log_prefix(driver), label, exc)
        time.sleep(random.uniform(0.12, 0.45))
        try:
            driver.execute_script("arguments[0].click();", el)
        except Exception:
            el.click()

def _human_type_text(driver, el, value: str, *, clear: bool = True) -> None:
    """按字符/小段输入，触发真实 key events；失败时回退 JS setter。"""
    if not _browser_actions_enabled():
        if clear:
            try:
                el.clear()
            except Exception:
                pass
        el.send_keys(value)
        return
    try:
        _human_scroll_to(driver, el)
        try:
            _human_click(driver, el, label="input_focus")
        except Exception:
            driver.execute_script("arguments[0].focus();", el)
        # CloakBrowser 已在 locator.press_sequentially 上实现逐键和 humanize。
        # 如果这里再把字符串拆成多个 send_keys 调用，多个异步人类化序列可能交错，
        # 实测会把邮箱末尾字符换序；重试时 Meta+A/Backspace 也可能和输入交错。
        # Cloak 路径因此使用一次完整顺序输入，Roxy/Selenium 保持原有分段逻辑。
        if str(getattr(driver, "_registration_log_prefix", "") or "") == "[Cloak注册]":
            if clear:
                try:
                    el.clear()
                except Exception:
                    _set_element_value(driver, el, "")
                time.sleep(random.uniform(0.04, 0.16))
            el.send_keys(str(value))
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                el,
            )
            return
        if clear:
            from selenium.webdriver.common.keys import Keys
            mod = Keys.COMMAND
            try:
                import platform
                if platform.system().lower() != "darwin":
                    mod = Keys.CONTROL
            except Exception:
                pass
            try:
                el.send_keys(mod, "a")
                time.sleep(random.uniform(0.04, 0.16))
                el.send_keys(Keys.BACKSPACE)
            except Exception:
                try:
                    el.clear()
                except Exception:
                    pass
        text = str(value)
        i = 0
        while i < len(text):
            # 邮箱/密码整体仍逐字符，但偶尔 2 字符一组，节奏更自然。
            step = 2 if random.random() < 0.12 and i + 1 < len(text) else 1
            el.send_keys(text[i:i + step])
            i += step
            human_delay("keystroke")
            if i < len(text) and random.random() < 0.08:
                human_delay("typing_pause")
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el,
        )
    except Exception as exc:
        logger.debug("%s 人工化输入失败，回退 JS setter err=%s", _log_prefix(driver), exc)
        _set_element_value(driver, el, value)

def _page_warmup(driver, *, reason: str = "") -> None:
    if not _browser_actions_enabled():
        return
    try:
        human_delay("page_warmup")
        if hasattr(driver, "execute_cdp_cmd"):
            driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": random.randint(80, 360),
                "y": random.randint(80, 260),
            })
    except Exception:
        pass

def _refresh_chatgpt_settings_shell_if_needed(driver, *, reason: str = "") -> bool:
    """Refresh a barely-mounted ChatGPT settings SPA once.

    A successful document navigation can still leave the settings React tree as
    a tiny locale/menu shell. This is especially easy to hit when a previous
    settings route was ``Security/passkeys``. Treat that state as a page
    hydration problem, not as a missing localized password label.
    """
    try:
        state = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const url = String(location.href || '').toLowerCase();
        const text = String(document.body?.innerText || '').replace(/\s+/g, ' ').trim();
        const interactive = [...document.querySelectorAll('button,a,[role="button"],input,select,textarea')]
          .filter(visible).length;
        const settingsRoute = /#settings\//i.test(url) || /\/settings\//i.test(url);
        const homeShell = [
          '[data-testid="create-new-chat-button"]',
          '[data-testid="send-button"]',
          '[data-testid="composer-plus-btn"]',
          '[data-testid="thread-header-right-actions"]',
        ].some(selector => !!document.querySelector(selector));
        return {settings_route: settingsRoute, text_length: text.length, interactive, home_shell: homeShell};
        """) or {}
    except Exception:
        return False

    # A normal Security page contains substantially more than the single
    # localized settings label. Keep this bounded to one refresh so a real
    # remote outage is still reported by the caller's existing timeout.
    if not state.get("settings_route") or int(state.get("text_length") or 0) >= 500:
        return False
    # A blank settings shell can still contain a handful of stale menu nodes;
    # the absence of mounted text is stronger evidence than the raw node count.
    if (
        not bool(state.get("home_shell"))
        and int(state.get("interactive") or 0) > 4
        and int(state.get("text_length") or 0) > 0
    ):
        return False
    logger.warning(
        "%s 检测到 ChatGPT 设置页前端空壳，刷新一次等待安全设置挂载：reason=%s state=%s",
        _log_prefix(driver), reason or "settings", state,
    )
    try:
        driver.refresh()
    except Exception:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
    _page_warmup(driver, reason=f"settings_shell_refresh:{reason or 'settings'}")
    try:
        after_refresh = driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
        const text = String(document.body?.innerText || '').replace(/\s+/g, ' ').trim();
        const homeShell = [
          '[data-testid="create-new-chat-button"]',
          '[data-testid="send-button"]',
          '[data-testid="composer-plus-btn"]',
          '[data-testid="thread-header-right-actions"]',
        ].some(selector => !!document.querySelector(selector));
        return {home_shell: homeShell, text_length: text.length, visible};
        """) or {}
    except Exception:
        after_refresh = {}
    if bool(after_refresh.get("home_shell")) and int(after_refresh.get("text_length") or 0) < 500:
        recovery_url = f"https://chatgpt.com/?settings_recover={int(time.time() * 1000)}#settings/Security"
        logger.warning(
            "%s 设置页刷新后仍停留首页壳，执行带恢复参数的新导航：reason=%s",
            _log_prefix(driver), reason or "settings",
        )
        _safe_get(
            driver,
            recovery_url,
            timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com",),
        )
        _page_warmup(driver, reason=f"settings_shell_recover:{reason or 'settings'}")
    return True

def _settings_page_not_ready(
    *,
    url: str,
    password_controls: list[str] | tuple[str, ...] | None,
    password_lines: list[str] | tuple[str, ...] | None,
    page_meta: dict | str | None,
    security_action=None,
) -> bool:
    """Distinguish an unmounted settings shell from a stable no-password page.

    A missing Add-password control is only meaningful after the Security tab has
    mounted.  The ChatGPT settings SPA can otherwise show a localized ``Settings``
    label and a few stale menu nodes while the security tree is still loading.
    """
    controls = [str(item or "").strip() for item in (password_controls or []) if item]
    lines = [str(item or "").strip() for item in (password_lines or []) if item]
    password_marker = re.compile(
        r"password|密码|パスワード|비밀번호|mot\s+de\s+passe|contraseña|senha|passwort|пароль",
        re.IGNORECASE,
    )
    add_password_marker = re.compile(
        r"password[-_:]?setting|"
        r"(?:add|set|create).{0,30}password|password.{0,30}(?:add|set|create)|"
        r"添加密码|设置密码|新增密码|"
        r"パスワード.{0,30}(?:追加|設定)|(?:追加|設定).{0,30}パスワード|"
        r"비밀번호.{0,30}(?:추가|설정)|(?:추가|설정).{0,30}비밀번호|"
        r"(?:ajouter|définir|configurer).{0,30}(?:mot\s+de\s+passe|password)|"
        r"(?:agregar|añadir|establecer|configurar).{0,30}(?:contraseña|password)|"
        r"(?:adicionar|definir|configurar).{0,30}(?:senha|password)|"
        r"(?:hinzufügen|festlegen|einstellen).{0,30}(?:passwort|password)|"
        r"(?:добавить|установить|настроить).{0,30}(?:пароль|password)",
        re.IGNORECASE,
    )
    # A visible Add-password control is evidence that the page knows the
    # passwordless flow. If its form did not open, retry the browser state
    # instead of persisting a false unsupported capability.
    if any(add_password_marker.search(value) for value in (*controls, *lines)):
        return True
    if any(password_marker.search(value) for value in (*controls, *lines)):
        return False
    normalized_url = str(url or "").strip().lower()
    if "settings" not in normalized_url:
        # An auth error, login page, or redirect is not evidence that the
        # settings page lacks Add-password. Let the outer retry envelope
        # reacquire the browser state before classifying the account.
        return True
    meta = page_meta
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except (TypeError, ValueError, json.JSONDecodeError):
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    testids = " ".join(str(item or "").lower() for item in (meta.get("testids") or []))
    body_text_length = int(meta.get("body_text_length") or 0)
    security_route = "#settings/security" in normalized_url or "/settings/security" in normalized_url
    security_mounted = (
        "security-tab" in testids
        or "security-setting" in testids
        or security_route
    )
    settings_modal_mounted = (
        "modal-settings" in testids
        or "general-setting-tab" in testids
        or "data-controls" in testids
    )
    return (
        not security_mounted
        or not settings_modal_mounted
        or (body_text_length < 500 and not security_route and security_action is not None)
    )

def _find_any(driver, selectors: list[str], timeout: int | None = None):
    from selenium.webdriver.common.by import By

    end = time.time() + (timeout or int(_cfg.ROXY_SELENIUM_TIMEOUT))
    last = None
    while time.time() < end:
        _check_manual_stop()
        for selector in selectors:
            try:
                by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                items = driver.find_elements(by, selector)
                for item in items:
                    if _visible(item):
                        return item
            except Exception as exc:
                last = exc
        time.sleep(0.4)
    raise RuntimeError(f"找不到页面元素: {selectors}; last={last}")

def _click_any(driver, selectors: list[str], timeout: int | None = None) -> None:
    el = _find_any(driver, selectors, timeout)
    _human_click(driver, el, label="click_any")

def _type_any(driver, selectors: list[str], value: str, timeout: int | None = None, clear: bool = True) -> None:
    el = _find_any(driver, selectors, timeout)
    _human_type_text(driver, el, value, clear=clear)

def _click_continue(driver) -> None:
    _click_any(driver, [
        "button[type='submit']",
        "//button[contains(., 'Continue')]",
        "//button[contains(., '继续')]",
        "//button[contains(., 'Sign up')]",
        "//button[contains(., 'Create')]",
        "//button[contains(., 'Next')]",
    ], timeout=20)

def _maybe_accept(driver) -> None:
    # 只处理明确的 cookie/consent 弹层按钮；不要用 “Continue” 兜底，
    # 非日本出口时 “Continue with Google” 也会命中，导致误点 Google 登录。
    for selectors in ([
        "button#onetrust-accept-btn-handler",
        "button[data-testid='cookie-accept']",
        "button[data-testid='accept-cookies']",
        "//button[contains(., 'Accept')]",
        "//button[contains(., '同意')]",
        "//button[contains(., 'Agree')]",
    ],):
        try:
            _click_any(driver, selectors, timeout=3)
            time.sleep(0.5)
        except Exception:
            pass

def _page_snapshot(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const inputs = [...document.querySelectorAll('input,select,textarea')].map(el => ({
          tag: el.tagName, type: el.getAttribute('type') || '', name: el.getAttribute('name') || '',
          id: el.id || '', placeholder: el.getAttribute('placeholder') || '',
          autocomplete: el.getAttribute('autocomplete') || '', aria: el.getAttribute('aria-label') || '',
          value: el.value || '', visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        })).filter(x => x.visible).slice(0, 30);
        const buttons = [...document.querySelectorAll('button,a[role=button],input[type=submit]')].map(el => ({
          text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
          type: el.getAttribute('type') || '', visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
          disabled: !!el.disabled
        })).filter(x => x.visible).slice(0, 30);
        const widgets = [...document.querySelectorAll('[role=spinbutton], .react-aria-Select, [data-testid="hidden-select-container"] select')].map(el => ({
          tag: el.tagName, role: el.getAttribute('role') || '', dataType: el.getAttribute('data-type') || '',
          aria: el.getAttribute('aria-label') || '', text: (el.innerText || el.textContent || '').trim().slice(0, 80),
          visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        })).slice(0, 30);
        return {url: location.href, title: document.title, text: (document.body?.innerText || '').slice(0, 2000), inputs, buttons, widgets};
        """) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "url": getattr(driver, 'current_url', '')}

def _is_profile_like(snapshot: dict) -> bool:
    """资料页识别：兼容 about-you/profile；年龄/生日控件可能不是 input，而是 React Aria widget。"""
    url = str(snapshot.get('url') or '').lower()
    inputs = snapshot.get('inputs') or []
    widgets = snapshot.get('widgets') or []
    attrs = ' '.join(
        ' '.join(str(i.get(k) or '') for k in ('name', 'id', 'placeholder', 'autocomplete', 'aria', 'type')).lower()
        for i in inputs
    )
    widget_attrs = ' '.join(
        ' '.join(str(i.get(k) or '') for k in ('role', 'dataType', 'aria', 'text', 'tag')).lower()
        for i in widgets
    )
    has_profile_url = any(x in url for x in ('about-you', 'profile', 'signup/profile', 'create-account/profile'))
    has_name_field = (
        'autocomplete name' in attrs
        or ' name ' in f' {attrs} '
        or 'fullname' in attrs
        or 'full_name' in attrs
        or 'firstname' in attrs
        or 'lastname' in attrs
    )
    has_age_or_birth_field = any(x in f' {attrs} {widget_attrs} ' for x in (
        ' age', '-age', '_age', 'birth', 'birthday', 'birthdate',
        ' month', '-month', '_month', 'data-type month',
        ' day', '-day', '_day', 'data-type day',
        ' year', '-year', '_year', 'data-type year',
        'spinbutton', 'react-aria-select', 'type number',
    ))
    # about-you/profile URL 本身已经足够强；部分新版页面会用无 name 的 React Aria 控件。
    return has_profile_url and (has_name_field or has_age_or_birth_field or bool(inputs) or bool(widgets))

def _set_element_value(driver, el, value: str) -> None:
    """兼容 React 受控输入框：用原生 setter 设置值并派发 input/change。"""
    driver.execute_script(r"""
    const el = arguments[0];
    const value = String(arguments[1]);
    const tag = (el.tagName || '').toLowerCase();
    el.scrollIntoView({block:'center'});
    el.focus();
    if (tag === 'select') {
      el.value = value;
    } else {
      const proto = tag === 'textarea' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setter) setter.call(el, value);
      else el.value = value;
    }
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
    el.blur();
    """, el, value)

def _select_or_type(driver, selectors: list[str], value: str, timeout: int = 3) -> bool:
    try:
        el = _find_any(driver, selectors, timeout=timeout)
    except Exception:
        return False
    try:
        tag = (el.tag_name or '').lower()
        if tag == 'select':
            if el.__class__.__name__ == 'CloakElement':
                driver.execute_script(r"""
                const el = arguments[0], value = String(arguments[1]);
                const n = parseInt(value, 10);
                const opts = [...el.options];
                const match = opts.find(o => o.value === value)
                  || opts.find(o => (o.textContent || '').trim() === value)
                  || opts[Math.max(0, n - 1)];
                if (match) el.value = match.value; else el.value = value;
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                """, el, str(value))
            else:
                from selenium.webdriver.support.ui import Select
                sel = Select(el)
                try:
                    sel.select_by_value(str(int(value)))
                except Exception:
                    try:
                        sel.select_by_visible_text(str(int(value)))
                    except Exception:
                        # 月份 select 可能是 0-based，也可能是 1-based；先 value/text，不行再 index。
                        sel.select_by_index(max(0, int(value)-1))
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", el)
        else:
            _human_type_text(driver, el, str(value), clear=True)
            # Roxy 的登录页会拦截 Selenium key events；send_keys 不抛异常但受控
            # input 仍可能保持空值。必须读回验证，并在必要时用 React 原生 setter
            # 兜底，不能把“调用成功”误当成“字段已填写”。
            actual = str(el.get_attribute("value") or "")
            if actual != str(value):
                _set_element_value(driver, el, str(value))
                actual = str(el.get_attribute("value") or "")
            if actual != str(value):
                return False
        return True
    except Exception as exc:
        logger.debug('%s 填写字段失败 selectors=%s value=%s err=%s', _log_prefix(driver), selectors, value, exc)
        return False

def _fill_birthday_or_age(driver, birthday: str, age: int) -> str | None:
    """填写 about-you 的年龄/生日控件。

    参考 FlowPilot：优先处理直接年龄 input；否则兼容 hidden birthday/date、原生年月日
    select/input、React Aria hidden native select、role=spinbutton[data-type=year/month/day]。
    返回 age / birthday / ymd / react_select / spinbutton / None。
    """
    y, m, d = birthday.split('-')
    result = driver.execute_script(r"""
    const birthday = String(arguments[0]);
    const year = String(arguments[1]);
    const month = String(Number(arguments[2]));
    const month2 = String(arguments[2]).padStart(2, '0');
    const day = String(Number(arguments[3]));
    const day2 = String(arguments[3]).padStart(2, '0');
    const age = String(arguments[4]);
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
      && !el.disabled && !el.readOnly;
    const setValue = (el, value) => {
      if (!el) return false;
      el.scrollIntoView?.({block:'center'});
      el.focus?.();
      const tag = (el.tagName || '').toLowerCase();
      const proto = tag === 'textarea' ? HTMLTextAreaElement.prototype
        : tag === 'select' ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setter) setter.call(el, String(value)); else el.value = String(value);
      if (tag === 'select') {
        [...el.options].forEach(opt => { opt.selected = String(opt.value) === String(value); });
      }
      el.dispatchEvent(new Event('input', {bubbles:true}));
      el.dispatchEvent(new Event('change', {bubbles:true}));
      el.blur?.();
      return true;
    };
    const ageInput = [...document.querySelectorAll('input[name="age"], input#age, input[id$="-age"], input[type="number"]')]
      .find(visible);
    if (ageInput && setValue(ageInput, age)) return {ok:true, mode:'age'};

    const dateInput = [...document.querySelectorAll('input[name="birthdate"], input[type="date"], input[name="birthday"]')]
      .find(el => visible(el) || String(el.getAttribute('type') || '').toLowerCase() === 'date');
    if (dateInput && setValue(dateInput, birthday)) return {ok:true, mode:'birthday'};

    const setFirst = (selectors, values) => {
      for (const sel of selectors) {
        for (const el of [...document.querySelectorAll(sel)]) {
          if (!visible(el)) continue;
          for (const val of values) {
            if (el.tagName === 'SELECT') {
              const has = [...el.options].some(o => String(o.value) === String(val) || String(o.textContent || '').trim() === String(val));
              if (!has) continue;
            }
            if (setValue(el, val)) return true;
          }
        }
      }
      return false;
    };
    const yOk = setFirst(['select[name="year"]','input[name="year"]','select[id*="year"]','input[id*="year"]'], [year]);
    const mOk = setFirst(['select[name="month"]','input[name="month"]','select[id*="month"]','input[id*="month"]'], [month, month2]);
    const dOk = setFirst(['select[name="day"]','input[name="day"]','select[id*="day"]','input[id*="day"]'], [day, day2]);
    if (yOk && mOk && dOk) {
      const hidden = document.querySelector('input[name="birthday"]');
      if (hidden) setValue(hidden, birthday);
      return {ok:true, mode:'ymd'};
    }

    // React Aria Select 通常有 hidden native select；不依赖标签文字，按 option 数值范围和 DOM 顺序推断年/月/日。
    const selects = [...document.querySelectorAll('[data-testid="hidden-select-container"] select, .react-aria-Select select, select')]
      .filter(el => !el.disabled);
    const nums = sel => [...sel.options].map(o => Number(o.value)).filter(Number.isFinite);
    const maxNum = sel => Math.max(...nums(sel), -Infinity);
    const minNum = sel => Math.min(...nums(sel), Infinity);
    const hasOption = (sel, val) => [...sel.options].some(o => String(o.value) === String(val));
    const yearSelects = selects.filter(sel => hasOption(sel, year) && maxNum(sel) > 1900);
    const smallSelects = selects.filter(sel => !yearSelects.includes(sel));
    const monthSelects = smallSelects.filter(sel => (hasOption(sel, month) || hasOption(sel, month2)) && minNum(sel) <= 1 && maxNum(sel) <= 12);
    const daySelects = smallSelects.filter(sel => (hasOption(sel, day) || hasOption(sel, day2)) && maxNum(sel) >= 28);
    if (yearSelects.length && monthSelects.length && daySelects.length) {
      const ys = yearSelects[0];
      let ms = monthSelects[0];
      let ds = daySelects.find(x => x !== ms) || daySelects[0];
      setValue(ys, year);
      setValue(ms, hasOption(ms, month) ? month : month2);
      setValue(ds, hasOption(ds, day) ? day : day2);
      const hidden = document.querySelector('input[name="birthday"]');
      if (hidden) setValue(hidden, birthday);
      return {ok:true, mode:'react_select'};
    }

    const spinYear = document.querySelector('[role="spinbutton"][data-type="year"]');
    const spinMonth = document.querySelector('[role="spinbutton"][data-type="month"]');
    const spinDay = document.querySelector('[role="spinbutton"][data-type="day"]');
    if (spinYear && spinMonth && spinDay) return {ok:false, mode:'spinbutton_needed'};
    return {ok:false, mode:'missing'};
    """, birthday, y, m, d, str(age)) or {}
    if result.get('ok'):
        return str(result.get('mode') or 'birthday')
    if result.get('mode') != 'spinbutton_needed':
        return None

    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        mod = Keys.COMMAND
        try:
            import platform
            if platform.system().lower() != 'darwin':
                mod = Keys.CONTROL
        except Exception:
            pass
        for selector, value in [
            ('[role="spinbutton"][data-type="year"]', y),
            ('[role="spinbutton"][data-type="month"]', str(m).zfill(2)),
            ('[role="spinbutton"][data-type="day"]', str(d).zfill(2)),
        ]:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].focus();", el)
            time.sleep(0.1)
            el.send_keys(mod, 'a')
            time.sleep(0.05)
            el.send_keys(str(value))
            time.sleep(0.1)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true})); arguments[0].dispatchEvent(new Event('change', {bubbles:true})); arguments[0].blur();", el)
        driver.execute_script(r"""
        const hidden = document.querySelector('input[name="birthday"]');
        if (hidden) {
          const value = arguments[0];
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
          if (setter) setter.call(hidden, value); else hidden.value = value;
          hidden.dispatchEvent(new Event('input', {bubbles:true}));
          hidden.dispatchEvent(new Event('change', {bubbles:true}));
        }
        """, birthday)
        return 'spinbutton'
    except Exception as exc:
        logger.debug('%s spinbutton 生日填写失败：%s', _log_prefix(driver), exc)
        return None

def _password_page_state(driver) -> dict:
    try:
        return driver.execute_script(r"""
        const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
          && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none'
          && !el.disabled && !el.readOnly;
        const inputs = [...document.querySelectorAll('input')].map(el => ({
          type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
          autocomplete: el.getAttribute('autocomplete') || '', visible: visible(el), value: el.type === 'password' ? '<password>' : (el.value || '')
        })).slice(0, 30);
        const forms = [...document.querySelectorAll('form')].map(f => ({action: f.getAttribute('action') || '', method: f.getAttribute('method') || ''}));
        const buttons = [...document.querySelectorAll('button,input[type="submit"]')].map(el => ({
          type: el.getAttribute('type') || '', name: el.getAttribute('name') || '', id: el.id || '',
          disabled: !!el.disabled, visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
        })).slice(0, 30);
        return {url: location.href, title: document.title || '', text: (document.body?.innerText || '').slice(0, 1200), inputs, forms, buttons};
        """) or {}
    except Exception as exc:
        return {"url": getattr(driver, "current_url", ""), "error": f"{type(exc).__name__}: {exc}"}

def _is_signup_password_page(driver) -> bool:
    state = _password_page_state(driver)
    classified = classify_page(state)
    if classified == PageState.PASSWORD_LOGIN:
        return False
    if classified == PageState.PASSWORD_CREATE:
        return True
    url = str(state.get('url') or '').lower()
    if any(x in url for x in ('/create-account/password', '/u/signup/password', '/signup/password')):
        return True
    if '/log-in/password' in url:
        return False
    inputs = state.get('inputs') or []
    return any(
        i.get('visible') and (
            str(i.get('type') or '').lower() == 'password'
            or 'password' in str(i.get('name') or '').lower()
            or str(i.get('autocomplete') or '').lower() == 'new-password'
        )
        for i in inputs
    )

def _is_login_password_page(driver) -> bool:
    try:
        url = str(driver.current_url or '').lower()
    except Exception:
        url = ''
    if '/log-in/password' in url:
        return True
    state = _password_page_state(driver)
    if classify_page(state) == PageState.PASSWORD_LOGIN:
        return True
    url = str(state.get('url') or '').lower()
    return '/log-in/password' in url

def _click_if_enabled_submit(driver) -> bool:
    """提交资料页：优先 form.requestSubmit/button[type=submit]，不依赖按钮文字。"""
    try:
        target = driver.execute_script(r"""
        const visible = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
        const forms = [...document.querySelectorAll('form')].filter(visible);
        for (const form of forms) {
          const submit = form.querySelector('button[type="submit"], input[type="submit"]');
          if (submit && visible(submit) && !submit.disabled) {
            submit.scrollIntoView({block:'center'});
            return submit;
          }
          if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
            return 'submitted_by_requestSubmit';
          }
        }
        const submitters = [...document.querySelectorAll('button[type="submit"], input[type="submit"]')]
          .filter(el => visible(el) && !el.disabled);
        if (submitters.length) {
          submitters[0].scrollIntoView({block:'center'});
          return submitters[0];
        }
        // 兜底：页面只有一个可点击 button 时点击它，但仍不读文字。
        const buttons = [...document.querySelectorAll('button:not([disabled])')].filter(visible);
        if (buttons.length === 1) {
          buttons[0].scrollIntoView({block:'center'});
          return buttons[0];
        }
        return null;
        """)
        if not target:
            return False
        if isinstance(target, str):
            return True
        _human_click(driver, target, label="profile_submit")
        return True
    except Exception:
        return False

def _button_after_input(driver, field, *, before: bool = False):
    """Return the nearest enabled dialog/form button by DOM order, independent of locale."""
    return driver.execute_script(r"""
    const input = arguments[0], wantBefore = !!arguments[1];
    const root = input.closest('[role="dialog"]') || input.closest('form') || document;
    const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
      && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
    const enabled = el => !el.disabled && String(el.getAttribute('aria-disabled') || '').toLowerCase() !== 'true';
    const buttons = [...root.querySelectorAll('button,input[type="submit"]')].filter(el =>
      visible(el) && enabled(el) && el.getAttribute('data-testid') !== 'close-button');
    const explicitSubmit = buttons.filter(el =>
      String(el.getAttribute('type') || '').toLowerCase() === 'submit'
      || String(el.getAttribute('name') || '').toLowerCase() === 'submit'
      || String(el.getAttribute('data-testid') || '').toLowerCase().includes('submit')
    );
    const ordered = [...explicitSubmit, ...buttons.filter(el => !explicitSubmit.includes(el))];
    const flag = Node.DOCUMENT_POSITION_FOLLOWING;
    if (wantBefore) return ordered.find(el => (el.compareDocumentPosition(input) & flag) !== 0) || null;
    return ordered.find(el => (input.compareDocumentPosition(el) & flag) !== 0) || null;
    """, field, bool(before))


def _check_manual_stop() -> None:
    """Observe the caller-injected cancellation/deadline context."""
    _checkpoint()


install_dispatches(globals(), (
    "human_delay", "_wait", "_budget_timeout", "_roxy_page_state",
    "_auth_terminal_page_state", "_visible", "_human_scroll_to", "_human_click",
    "_human_type_text", "_page_warmup", "_refresh_chatgpt_settings_shell_if_needed",
    "_settings_page_not_ready", "_find_any", "_click_any", "_type_any",
    "_click_continue", "_maybe_accept", "_page_snapshot", "_is_profile_like",
    "_set_element_value", "_select_or_type", "_fill_birthday_or_age",
    "_click_if_enabled_submit", "_password_page_state", "_is_signup_password_page",
    "_is_login_password_page", "_button_after_input", "_check_manual_stop",
))

__all__ = [
    "human_delay", "_wait", "_budget_timeout", "_roxy_page_state",
    "_auth_terminal_page_state", "_visible", "_human_scroll_to", "_human_click",
    "_human_type_text", "_page_warmup", "_refresh_chatgpt_settings_shell_if_needed",
    "_settings_page_not_ready", "_find_any", "_click_any", "_type_any",
    "_click_continue", "_maybe_accept", "_page_snapshot", "_is_profile_like",
    "_set_element_value", "_select_or_type", "_fill_birthday_or_age",
    "_click_if_enabled_submit", "_password_page_state", "_is_signup_password_page",
    "_is_login_password_page", "_button_after_input", "_check_manual_stop",
]
