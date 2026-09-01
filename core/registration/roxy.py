# -*- coding: utf-8 -*-
"""通过 RoxyBrowser 指纹浏览器 + Selenium 执行 ChatGPT 注册。"""
from __future__ import annotations

import logging
import math
import random
import re
import string
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from config import roxybrowser as _cfg
from config import codex as _codex_cfg
from config import twofa as _twofa_cfg
from core.account_export import setup_2fa_protocol
from core.email_provider import wait_for_otp, resolve_email_source
from core.humanize import delay as human_delay
from core.roxybrowser_client import RoxyBrowserClient, RoxyOpenResult
from core.session import BrowserSession
from core.registration.state_machine import (
    PageState,
    StageBudget,
    StageTimeout,
    can_resend_otp,
    classify_page,
)

logger = logging.getLogger(__name__)

# These failures happen before a local account checkpoint exists. Keeping the
# temporary Profile for them only consumes a Roxy slot; failures after a
# password/OTP submit are deliberately excluded by the state guards below.
_DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS = (
    "err_tunnel_connection_failed",
    "err_proxy_connection_failed",
    "chrome-error://chromewebdata/",
    "邮箱提交/认证跳转超过总预算",
    "roxy registration stage timeout exhausted",
    "email otp input budget exhausted",
    "page_not_hydrated",
)


def _is_disposable_pre_account_failure(
    error_text: str,
    *,
    create_acknowledged: bool,
    account_id: int | None,
) -> bool:
    """Return whether a run-created Profile can be discarded safely."""
    if create_acknowledged or account_id is not None:
        return False
    normalized = str(error_text or "").lower()
    if any(marker in normalized for marker in _DISPOSABLE_PRE_ACCOUNT_FAILURE_MARKERS):
        return True
    # The page-not-hydrated classifier is persisted separately from the raw
    # exception. Match its characteristic empty ChatGPT auth snapshot too.
    empty_actions = "'actions': []" in normalized or '"actions": []' in normalized
    empty_inputs = "'inputs': []" in normalized or '"inputs": []' in normalized
    return (
        "找不到邮箱输入框/邮箱入口" in normalized
        and "chatgpt.com/auth/login" in normalized
        and empty_actions
        and empty_inputs
    )


def _log_prefix(driver=None) -> str:
    """按当前浏览器实现返回注册日志前缀。

    CloakBrowser 复用 Roxy 的页面操作函数；这些共享函数必须跟随实际 driver
    输出 `[Cloak注册]`，避免 Cloak 流程里混入 `[Roxy注册]` 日志。
    """
    try:
        explicit = str(getattr(driver, "_registration_log_prefix", "") or "").strip()
        if explicit:
            return explicit
        if driver is not None and driver.__class__.__name__ == "CloakSeleniumDriver":
            return "[Cloak注册]"
    except Exception:
        pass
    return "[Roxy注册]"


def _build_driver(opened: RoxyOpenResult):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

    if opened.debugger_address:
        logger.info("[Roxy] Selenium 连接 debuggerAddress=%s", opened.debugger_address)
        options = Options()
        # 页面里长轮询/风控脚本偶尔会让 driver.get 等到超时；eager 只等 DOMContentLoaded。
        options.page_load_strategy = "eager"
        options.add_experimental_option("debuggerAddress", opened.debugger_address)
        driver_path = ""
        try:
            raw_data = opened.raw.get("data") if isinstance(opened.raw, dict) else {}
            if isinstance(raw_data, dict):
                driver_path = str(raw_data.get("driver") or raw_data.get("driverPath") or raw_data.get("driver_path") or "").strip()
        except Exception:
            driver_path = ""
        if driver_path:
            logger.info("[Roxy] 使用 Roxy chromedriver=%s", driver_path)
            driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=options)
        else:
            driver = webdriver.Chrome(options=options)
        _apply_browser_automation_mask(driver)
        return driver

    if opened.webdriver_url:
        logger.info("[Roxy] Selenium 连接 webdriver_url=%s", opened.webdriver_url)
        options = Options()
        options.page_load_strategy = "eager"
        driver = RemoteWebDriver(command_executor=opened.webdriver_url, options=options)
        _apply_browser_automation_mask(driver)
        return driver

    raise RuntimeError("Roxy 未返回可连接的 Selenium 地址")


def _center_browser_window(driver) -> None:
    """把可见的 Roxy 窗口移动到 Windows 主屏工作区中央。"""
    if bool(getattr(_cfg, "ROXY_OPEN_HEADLESS", False)):
        return
    try:
        import platform
        if platform.system().lower() != "windows":
            return
        import ctypes

        class _Rect(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        work_area = _Rect()
        if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0):
            raise OSError("无法读取 Windows 工作区")
        size = driver.get_window_size()
        width = max(1, int(size.get("width") or 1))
        height = max(1, int(size.get("height") or 1))
        x = int(work_area.left + max(0, (work_area.right - work_area.left - width) // 2))
        y = int(work_area.top + max(0, (work_area.bottom - work_area.top - height) // 2))
        driver.set_window_position(x, y)
        logger.info("[Roxy] 浏览器窗口已居中：x=%s y=%s width=%s height=%s", x, y, width, height)
    except Exception as exc:
        logger.warning("[Roxy] 浏览器窗口居中失败，继续执行：%s", exc)


def _wait(driver, timeout: int | None = None):
    from selenium.webdriver.support.ui import WebDriverWait
    return WebDriverWait(driver, timeout or int(_cfg.ROXY_SELENIUM_TIMEOUT))


def _budget_timeout(budget: StageBudget | None, default: float, *, minimum: float = 0.1) -> float:
    """Return a child timeout without ever extending the stage deadline."""
    if budget is None:
        return max(minimum, float(default))
    remaining = budget.remaining()
    if remaining <= 0:
        raise StageTimeout("Roxy registration stage timeout exhausted")
    # A minimum is useful for legacy callers, but must never make a bounded
    # child outlive its parent stage.
    return min(float(default), remaining)


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


def _safe_get(driver, url: str, *, timeout: int = 45, attempts: int = 2, accept_hosts: tuple[str, ...] = ()) -> None:
    """带容错的页面跳转。

    Roxy/Chrome 150 偶发 `Timed out receiving message from renderer`，实际页面可能已经可用。
    这里超时后先 `window.stop()`，只要当前 URL/DOM 已进入目标页就继续；否则重试一次。
    """
    from selenium.common.exceptions import TimeoutException, WebDriverException

    last_exc: Exception | None = None
    old_timeout = int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)
    hosts = tuple(h.lower() for h in (accept_hosts or ()))
    for attempt in range(1, max(1, attempts) + 1):
        try:
            try:
                driver.set_page_load_timeout(max(10, int(timeout)))
                driver.set_script_timeout(8)
            except Exception:
                pass
            driver.get(url)
            return
        except TimeoutException as exc:
            last_exc = exc
            logger.warning(
                "%s 页面加载超时，尝试停止加载后检查 DOM：url=%s attempt=%s/%s error=%s",
                _log_prefix(driver), url, attempt, attempts, str(exc).splitlines()[0] if str(exc) else "TimeoutException",
            )
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass
            time.sleep(1.0)
            try:
                current = str(driver.current_url or "").lower()
            except Exception:
                current = ""
            try:
                ready = str(driver.execute_script("return document.readyState || ''") or "")
                has_body = bool(driver.execute_script("return !!document.body"))
            except Exception:
                ready = ""
                has_body = False
            target_ok = any(h in current for h in hosts) if hosts else (url.split("/", 3)[2].lower() in current)
            if target_ok and has_body:
                logger.info(
                    "%s 页面加载虽超时但 DOM 可用，继续流程：current=%s readyState=%s",
                    _log_prefix(driver), current[:180], ready or "-",
                )
                return
            if attempt < attempts:
                try:
                    driver.get("about:blank")
                except Exception:
                    pass
                time.sleep(1.5 * attempt)
                continue
        except WebDriverException as exc:
            last_exc = exc
            if attempt < attempts:
                logger.warning("%s 页面跳转失败，准备重试：url=%s attempt=%s/%s error=%s", _log_prefix(driver), url, attempt, attempts, exc)
                time.sleep(1.5 * attempt)
                continue
            raise
        finally:
            try:
                driver.set_page_load_timeout(old_timeout)
            except Exception:
                pass
    raise last_exc or RuntimeError(f"页面跳转失败: {url}")


def _visible(el) -> bool:
    try:
        return el.is_displayed() and el.is_enabled()
    except Exception:
        return False


def _browser_actions_enabled() -> bool:
    try:
        from config import humanize as _hcfg
        return bool(getattr(_hcfg, "ENABLE_HUMANIZE_BROWSER_ACTIONS", True))
    except Exception:
        return True


def _apply_browser_automation_mask(driver) -> None:
    """连接 Selenium 后尽量降低明显自动化特征；失败不影响主流程。"""
    if not _browser_actions_enabled():
        return
    try:
        script = r"""
        Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => undefined});
        if (!window.chrome) window.chrome = {};
        if (!window.chrome.runtime) window.chrome.runtime = {};
        const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
        if (originalQuery) {
          window.navigator.permissions.query = (parameters) => (
            parameters && parameters.name === 'notifications'
              ? Promise.resolve({ state: Notification.permission })
              : originalQuery(parameters)
          );
        }
        """
        if hasattr(driver, "execute_cdp_cmd"):
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        try:
            driver.execute_script(script)
        except Exception:
            pass
        logger.info("%s 已注入浏览器自动化特征弱化脚本", _log_prefix(driver))
    except Exception as exc:
        logger.debug("%s 注入自动化特征弱化脚本失败：%s", _log_prefix(driver), exc)


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
        return {settings_route: settingsRoute, text_length: text.length, interactive};
        """) or {}
    except Exception:
        return False

    # A normal Security page contains substantially more than the single
    # localized settings label. Keep this bounded to one refresh so a real
    # remote outage is still reported by the caller's existing timeout.
    if not state.get("settings_route") or int(state.get("text_length") or 0) >= 500:
        return False
    if int(state.get("interactive") or 0) > 4:
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
    return True


def _find_any(driver, selectors: list[str], timeout: int | None = None):
    from selenium.webdriver.common.by import By

    end = time.time() + (timeout or int(_cfg.ROXY_SELENIUM_TIMEOUT))
    last = None
    while time.time() < end:
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
    return title in {
        "开始使用 | chatgpt",
        "開始する | chatgpt",
        "get started | chatgpt",
    }


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
    timeout = _budget_timeout(budget, timeout, minimum=0.0) if budget is not None else timeout
    clock = budget.clock if budget is not None else time.time
    end = clock() + max(0.0, timeout)
    last = None
    cleared_seen_at: float | None = None
    cleared_last_log_at = 0.0
    cleared_recover_done = False
    transient_shell_logged = False
    expected_email = str(email or "").strip().lower()
    while True:
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
            raise RuntimeError(f"邮箱提交后进入登录密码页，按已注册/不可用邮箱处理并停用: url={getattr(driver, 'current_url', '') or 'https://auth.openai.com/log-in/password'}")
        if state_name in ("password", "otp", "logged_in"):
            logger.info("%s %s已进入下一步：%s", _log_prefix(driver), source, state_name)
            return state_name
        return None

    for attempt in range(1, attempts + 1):
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
    timeout = _budget_timeout(budget, timeout, minimum=0.0) if budget is not None else timeout
    end = time.monotonic() + max(0.0, timeout)
    last = {}
    while time.monotonic() < end:
        time.sleep(min(0.5, max(0.0, end - time.monotonic())))
        last = _email_otp_page_state(driver)
        if not isinstance(last, dict):
            last = {}
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


def _has_access_token(driver) -> bool:
    try:
        result = driver.execute_async_script(r"""
        const done = arguments[0];
        fetch('https://chatgpt.com/api/auth/session', {credentials:'include'})
          .then(r => r.json()).then(j => done(Boolean(j && j.accessToken)))
          .catch(() => done(false));
        """)
        return bool(result)
    except Exception:
        return False


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
            continue
        time.sleep(0.4)

    current_url = str(getattr(driver, "current_url", "") or "")
    candidates = (last_result.get("candidates") or [])[:10]
    candidate_text = " ".join(
        str(item.get(key) or "") for item in candidates for key in ("text", "name", "value", "aria")
    ).lower()
    flow_variant = (
        "otp_only_no_password_entry"
        if "email-verification" in current_url.lower()
        and any(marker in candidate_text for marker in ("resend", "validate", "verification", "code"))
        else "password_entry_not_rendered"
    )
    return {
        "ok": False,
        "reason": "missing_create_account_password_target_after_wait",
        "waited_seconds": wait_seconds,
        "refresh_attempted": refresh_attempted,
        "flow_variant": flow_variant,
        "url": current_url,
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
            return {el, idx, below: r.top >= ir.bottom - 10, dist: Math.max(0, r.top - ir.bottom) + Math.abs((r.left+r.right-ir.left-ir.right)/2)/10};
          })
          .filter(x => x.below)
          .sort((a,b) => a.dist - b.dist || a.idx - b.idx);
        if (!buttons.length) return {ok:false, reason:'missing_submit'};
        buttons[0].el.scrollIntoView({block:'center'});
        return {ok:true, reason:'password_targets', input, button: buttons[0].el};
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
        while time.time() < wait_end:
            _check_manual_stop()
            if _is_email_verification_page(driver):
                logger.info("%s 密码提交后已进入邮箱验证码页", _log_prefix(driver))
                return password
            if _has_access_token(driver):
                logger.info("%s 密码提交后已检测到登录态", _log_prefix(driver))
                return password
            if not (_is_signup_password_page(driver) or _is_login_password_page(driver)):
                return password
            time.sleep(0.5)
        stuck_state = _password_page_state(driver)
        raise _PasswordTransitionTimeout(
            f"密码提交后等待 {int(transition_timeout)} 秒仍未确认远端结果，页面仍停留在密码页："
            f"url={getattr(driver, 'current_url', '')} state={stuck_state}"
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


def _complete_profile_page(driver, name: str, birthday: str, timeout: int = 45) -> bool:
    """等待并完成姓名/生日页；若已经登录成功则返回 False，不把它当失败。"""
    end = time.time() + timeout
    y, m, d = birthday.split('-')
    from datetime import date
    today = date.today()
    age = today.year - int(y) - ((today.month, today.day) < (int(m), int(d)))
    last_snapshot = {}
    while time.time() < end:
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


def _read_chatgpt_session_once(driver) -> dict | None:
    """当前页面必须在 chatgpt.com；读取 /api/auth/session，拿不到 token 返回 None。"""
    script = r"""
    const done = arguments[0];
    fetch('/api/auth/session', {credentials: 'include'})
      .then(r => r.json())
      .then(j => done({ok: true, data: j}))
      .catch(e => done({ok: false, error: String(e)}));
    """
    result = driver.execute_async_script(script)
    if result and result.get("ok"):
        data = result.get("data") or {}
        if data.get("accessToken"):
            logger.info("%s /api/auth/session 已返回 accessToken", _log_prefix(driver))
            return data
        logger.info("%s 等待 ChatGPT session 写入 accessToken，当前响应 keys=%s", _log_prefix(driver), list(data.keys()))
    return None


def _switch_to_chatgpt_window_if_any(driver) -> bool:
    """有些浏览器/适配层会在新窗口完成 callback；尝试切到已有 chatgpt.com 句柄。"""
    try:
        handles = list(getattr(driver, "window_handles", []) or [])
        current_handle = None
        try:
            current_handle = getattr(driver, "current_window_handle", None)
        except Exception:
            current_handle = None
        for handle in handles:
            try:
                driver.switch_to.window(handle)
                if "chatgpt.com" in str(getattr(driver, "current_url", "") or ""):
                    return True
            except Exception:
                continue
        if current_handle is not None:
            try:
                driver.switch_to.window(current_handle)
            except Exception:
                pass
    except Exception:
        pass
    return False


def _fetch_chatgpt_session(
    driver,
    timeout: int = 90,
    auto_jump_wait: int = 15,
    *,
    budget: StageBudget | None = None,
) -> dict:
    """等待页面完成跳转并从 ChatGPT 页面内读取登录 session/accessToken。

    旧逻辑会在 auth.openai.com 上一直等到总超时，Cloak/部分 Chromium 场景下
    实际账号已创建成功但当前句柄 URL 没及时更新，导致白等 120 秒。现在只给
    自动跳转 `auto_jump_wait` 秒；超过后立即主动打开 chatgpt.com 读 session。
    """
    timeout = _budget_timeout(budget, timeout, minimum=0.0) if budget is not None else timeout
    end = time.monotonic() + max(0.0, timeout)
    auto_jump_end = time.monotonic() + max(3, int(auto_jump_wait or 15))
    last_data = None
    forced_chatgpt_open = False

    while time.monotonic() < end:
        terminal_state = _auth_terminal_page_state(driver)
        if terminal_state in (PageState.AUTH_ERROR, PageState.LOGGED_OUT):
            raise RuntimeError(
                f"OAuth callback ended in terminal auth state: {terminal_state.value}; "
                f"url={_diagnostic_url(getattr(driver, 'current_url', ''))}"
            )
        try:
            current = str(driver.current_url or '')
        except Exception:
            current = ''

        current_lower = current.lower()
        needs_chatgpt_home = any(
            marker in current_lower
            for marker in (
                'chatgpt.com/auth/error',
                'chatgpt.com/auth/login',
                'chatgpt.com/login',
            )
        )
        if 'chatgpt.com' not in current or (needs_chatgpt_home and not forced_chatgpt_open):
            if _switch_to_chatgpt_window_if_any(driver):
                current = str(getattr(driver, "current_url", "") or "")
            if not forced_chatgpt_open and (needs_chatgpt_home or time.monotonic() >= auto_jump_end):
                try:
                    logger.info(
                        "%s 当前页面需要回到 ChatGPT 首页读取 session：path=%s",
                        _log_prefix(driver), current_lower[:180],
                    )
                    safe_timeout = _budget_timeout(budget, 35, minimum=1)
                    if budget is not None and safe_timeout < 1:
                        raise StageTimeout("OAuth session navigation budget exhausted")
                    _safe_get(
                        driver,
                        "https://chatgpt.com/",
                        timeout=max(1, int(safe_timeout)),
                        attempts=2,
                        accept_hosts=("chatgpt.com",),
                    )
                    forced_chatgpt_open = True
                    delay = min(3.0, budget.remaining()) if budget is not None else 3.0
                    if delay > 0:
                        time.sleep(delay)
                    current = str(getattr(driver, "current_url", "") or "")
                except Exception as exc:
                    last_data = f"{type(exc).__name__}: {exc}"
            else:
                time.sleep(min(1.0, max(0.0, end - time.monotonic())))
                continue

        if 'chatgpt.com' in current:
            try:
                data = _read_chatgpt_session_once(driver)
                if data:
                    return data
                last_data = "session 暂无 accessToken"
            except Exception as exc:
                last_data = f"{type(exc).__name__}: {exc}"
        delay = min(2.0, max(0.0, end - time.monotonic()))
        if budget is not None:
            delay = min(delay, budget.remaining())
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError(f"等待 /api/auth/session accessToken 超时，最后响应: {str(last_data)[:800]}")


def _check_manual_stop() -> None:
    try:
        from core.registration_service import check_stop_requested
        check_stop_requested()
    except ImportError:
        return


def _is_roxy_window_capacity_error(error: object) -> bool:
    """只识别明确的窗口容量错误，避免把网络/配置故障误当成可等待状态。"""
    text = str(error or "").strip().lower()
    if not text:
        return False
    markers = (
        "窗口额度不足",
        "窗口数量已达上限",
        "窗口数已达上限",
        "窗口达到上限",
        "window quota",
        "window limit",
        "maximum number of windows",
        "too many windows",
    )
    return any(marker in text for marker in markers)


def _wait_for_roxy_window_retry(seconds: float) -> None:
    """可被手动停止打断的容量等待，最多每秒检查一次停止信号。"""
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        _check_manual_stop()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(1.0, remaining))


def _open_roxy_profile_with_capacity_wait(client, proxy_url: str | None, progress_callback=None) -> RoxyOpenResult:
    """窗口满时保持当前 worker 等待，防止失败槽位快速消费整个任务队列。"""
    timeout = max(0, int(getattr(_cfg, "ROXY_WINDOW_WAIT_TIMEOUT", 900) or 0))
    interval = max(1, int(getattr(_cfg, "ROXY_WINDOW_WAIT_INTERVAL", 10) or 10))
    started = time.monotonic()
    attempt = 0

    while True:
        _check_manual_stop()
        attempt += 1
        try:
            debug_headless = None
            try:
                from core.registration_debug import current_session
                if current_session() is not None:
                    debug_headless = False
            except Exception:
                pass
            open_kwargs = {"proxy_url": proxy_url}
            if debug_headless is not None:
                open_kwargs["headless"] = debug_headless
            opened = client.open_profile(**open_kwargs)
            if attempt > 1:
                logger.info(
                    "[Roxy注册] 已等到空闲窗口并成功启动环境：attempt=%s waited=%.1fs profile=%s",
                    attempt,
                    time.monotonic() - started,
                    opened.profile_id,
                )
            return opened
        except Exception as exc:
            if not _is_roxy_window_capacity_error(exc) or timeout <= 0:
                raise

            elapsed = time.monotonic() - started
            remaining = timeout - elapsed
            if remaining <= 0:
                raise RuntimeError(
                    f"等待 Roxy 空闲窗口超时（>{timeout}s），最后错误: {str(exc)[:180]}"
                ) from exc

            delay = min(float(interval), remaining)
            detail = (
                f"Roxy 窗口已满，等待空闲名额：已等 {int(elapsed)}s，"
                f"{int(delay)}s 后重试，最长 {timeout}s"
            )
            if progress_callback is not None:
                progress_callback("browser", "running", detail)
            logger.warning(
                "[Roxy注册] %s（attempt=%s，剩余 %.1fs）：%s",
                detail,
                attempt,
                remaining,
                str(exc)[:180],
            )
            _wait_for_roxy_window_retry(delay)


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
    if testid not in {"accounts-profile-button", "settings-menu-item", "security-tab", "password-setting"}:
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


def set_roxy_login_password(
    driver,
    email: str,
    password: str,
    *,
    timeout: int = 45,
    on_password_submitted=None,
) -> str:
    """在已登录的 ChatGPT 账号设置中补充账号密码。

    无密码账号从“账户安全与登录”里的密码“添加”入口进入新密码页；
    Security 页上的其它密码修改入口可能会要求当前密码，不能用于这类账号。
    """
    normalized = str(password or "").strip()
    if not normalized:
        raise ValueError("账号密码不能为空")

    _safe_get(
        driver,
        _CHATGPT_PASSWORD_SETTINGS_URL,
        timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
        attempts=2,
        accept_hosts=("chatgpt.com",),
    )
    _page_warmup(driver, reason="chatgpt_password_settings")
    _refresh_chatgpt_settings_shell_if_needed(driver, reason="chatgpt_password_settings")
    end = time.time() + max(10, int(timeout))
    password_inputs = []
    action = None
    settings_action = None
    security_action = None
    profile_action = None
    settings_clicks = 0
    security_clicks = 0
    profile_clicks = 0
    reauth_attempts = 0
    last_url = ""
    last_password_controls = []
    last_password_lines = []
    last_page_meta = {}

    def _complete_settings_email_reauth() -> None:
        """Complete the email re-authentication that Settings may require."""
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
        deadline = time.time() + 45
        while time.time() < deadline:
            _check_manual_stop()
            if not _is_email_verification_page(driver):
                logger.info("%s 设置页邮箱重认证已完成", _log_prefix(driver))
                return
            time.sleep(0.5)
        raise RuntimeError(f"设置页邮箱重认证后未返回 ChatGPT 设置页：{str(driver.current_url or '')[:180]}")

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
            _complete_settings_email_reauth()
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
        const passwordSettingNode = [...document.querySelectorAll('[data-testid]')]
          .filter(visible).find(el => passwordSettingTestId.test(testId(el)));
        let target = passwordSettingNode && (passwordSettingNode.matches('button,a,[role="button"]')
          ? passwordSettingNode
          : passwordSettingNode.querySelector('button,a,[role="button"]')
            || passwordSettingNode.closest('button,a,[role="button"]'));
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


def setup_roxy_2fa(driver, email: str, *, on_secret=None, existing_secret: str | None = None) -> str:
    """Enable Authenticator MFA in the existing Roxy browser session."""
    import pyotp

    logger.info("%s[2FA] 打开 ChatGPT 安全设置", _log_prefix(driver))
    toggle = _open_chatgpt_security_settings(driver)
    if (
        str(toggle.get_attribute("aria-checked") or "").lower() == "true"
        or str(toggle.get_attribute("data-state") or "").lower() == "checked"
    ):
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

    try:
        secret = setup_2fa_protocol(
            protocol_session,
            access_token,
            on_secret=_remember_secret,
        )
        return str(secret or checkpoint["secret"]).strip(), False
    except Exception as protocol_exc:
        protocol_error = f"{type(protocol_exc).__name__}: {str(protocol_exc)[:180]}"
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


def _registration_otp_attempt_wait_seconds(deadline: float, attempt: int, max_attempts: int) -> int:
    """Split one total OTP budget across remaining resend attempts."""
    remaining = max(0.0, float(deadline) - time.monotonic())
    attempts_left = max(1, int(max_attempts) - int(attempt) + 1)
    return int(math.ceil(remaining / attempts_left)) if remaining > 0 else 0


def _save_roxy_account_checkpoint(
    *,
    email: str,
    access_token: str,
    session_info: dict,
    opened: RoxyOpenResult,
    openai_password: str | None,
    proxy: str | None,
    totp_secret: str | None = None,
    codex_result: dict | None = None,
    twofa_result: dict | None = None,
) -> int:
    """只落库、不做批次归档/套餐查询的注册检查点。"""
    from core.db import insert_account

    user = session_info.get("user") or {}
    account = session_info.get("account") or {}
    codex = codex_result or {}
    codex_status = str(codex.get("status") or "").strip() or None
    codex_error = str(codex.get("message") or "").strip() if codex_status == "failed" else None
    extra = {
        "user": user,
        "account": account,
        "expires": session_info.get("expires"),
        "roxybrowser": {"profile_id": opened.profile_id, "open_result": opened.raw},
        "account_password": openai_password,
        "registration_checkpoint": "registered",
        "codex": codex_result,
        "twofa": twofa_result,
    }
    twofa_status = str((twofa_result or {}).get("status") or "").strip().lower()
    if totp_secret and twofa_status in {"running", "failed"}:
        # The key is already persisted, but OpenAI has not yet been confirmed
        # enabled. Keep this checkpoint explicit so a later browser retry can
        # verify/finish enrollment instead of assuming the secret is active.
        extra["totp_setup_pending"] = True
    return insert_account(
        email=email,
        access_token=access_token,
        totp_secret=totp_secret,
        user_id=user.get("id"),
        user_name=user.get("name"),
        plan_type=account.get("planType"),
        expires_at=session_info.get("expires"),
        proxy_used=proxy or None,
        email_source=resolve_email_source(email),
        extra=extra,
        codex_status=codex_status,
        codex_error=codex_error,
    )


def _save_pending_email_verification_checkpoint(
    *,
    email: str,
    openai_password: str,
    opened: RoxyOpenResult,
    proxy: str | None,
) -> int:
    """密码提交请求发出后立即保存待邮箱验证账号。

    OpenAI 在密码提交时已经创建邮箱身份；即使验证码邮件没有到达，本地也必须保存
    这组邮箱/密码，后续重试才能走登录流程继续收码。空 access_token 明确表示账号
    尚未完成邮箱验证，不能被套餐查询或 Codex 当成完整账号使用。
    """
    from core.db import insert_account

    return insert_account(
        email=email,
        access_token="",
        proxy_used=proxy or None,
        email_source=resolve_email_source(email),
        extra={
            "account_password": openai_password,
            "registration_checkpoint": "email_verification_pending",
            "registration_pending_reason": "email_otp_pending",
            "roxybrowser": {"profile_id": opened.profile_id, "open_result": opened.raw},
        },
    )


def _run_in_isolated_browser_tab(driver, callback, *, label: str):
    """在同一浏览器 Profile 的新标签页执行操作，结束后恢复原标签页。

    Cookie 仍由同一个 Roxy Profile 共享，但 OAuth 的 URL/表单/失败页面不会覆盖
    注册完成后的 ChatGPT 标签页。callback 成功或抛错都会关闭本次新建的全部标签页。
    """
    original_handles = list(getattr(driver, "window_handles", []) or [])
    original_handle = getattr(driver, "current_window_handle", None)
    if not original_handle:
        raise RuntimeError(f"{label} 无法读取原浏览器标签页")
    if original_handle not in original_handles:
        original_handles.append(original_handle)
    original_set = set(original_handles)

    try:
        driver.switch_to.new_window("tab")
    except Exception as first_exc:
        # 兼容缺少 Selenium new_window 的浏览器适配层。
        try:
            driver.switch_to.window(original_handle)
            driver.execute_script("window.open('about:blank', '_blank');")
            end = time.time() + 5
            new_handles = []
            while time.time() < end:
                new_handles = [h for h in (getattr(driver, "window_handles", []) or []) if h not in original_set]
                if new_handles:
                    break
                time.sleep(0.1)
            if not new_handles:
                raise RuntimeError("window.open 未创建新标签页")
            driver.switch_to.window(new_handles[-1])
        except Exception as fallback_exc:
            try:
                driver.switch_to.window(original_handle)
            except Exception:
                pass
            raise RuntimeError(
                f"无法为 {label} 创建独立标签页，已停止以避免污染注册登录态："
                f"new_window={type(first_exc).__name__}: {first_exc}; "
                f"fallback={type(fallback_exc).__name__}: {fallback_exc}"
            ) from fallback_exc

    isolated_handle = getattr(driver, "current_window_handle", None)
    if not isolated_handle or isolated_handle in original_set:
        try:
            driver.switch_to.window(original_handle)
        except Exception:
            pass
        raise RuntimeError(f"{label} 独立标签页创建后句柄未变化")

    logger.info("[Roxy注册] %s 已在独立标签页启动，原 ChatGPT 标签页保持不变", label)
    try:
        return callback()
    finally:
        # callback 可能又打开 callback/popup 标签页；只关闭本次操作新增的句柄。
        try:
            current_handles = list(getattr(driver, "window_handles", []) or [])
        except Exception:
            current_handles = []
        for handle in reversed(current_handles):
            if handle in original_set:
                continue
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception as exc:
                logger.debug("[Roxy注册] 关闭 %s 新标签页失败 handle=%s: %s", label, handle, exc)
        try:
            remaining = list(getattr(driver, "window_handles", []) or [])
            target = original_handle if original_handle in remaining else next(
                (h for h in original_handles if h in remaining),
                None,
            )
            if not target:
                raise RuntimeError("原标签页已不存在")
            driver.switch_to.window(target)
            logger.info("[Roxy注册] %s 已结束并切回原 ChatGPT 标签页", label)
        except Exception as exc:
            raise RuntimeError(f"{label} 结束后无法恢复原 ChatGPT 标签页：{exc}") from exc


def run_roxy_registration(
    email: str,
    name: str,
    birthday: str,
    proxy: str = None,
    otp_code: str = None,
    batch_dir: Path | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    registration_options: dict | None = None,
) -> dict:
    """Roxy 指纹浏览器自动化注册入口。"""
    from core.registration_service import report_job_otp_evidence, report_job_progress, report_registered_account

    options = dict(registration_options or {})
    password_required = bool(options.get("password_enabled", _registration_auth_mode() == "password"))
    twofa_enabled = bool(options.get("twofa_enabled", _twofa_cfg.ENABLE_2FA))
    # ``dict.get`` evaluates its default argument eagerly.  Read the live
    # config only for legacy callers that did not provide a job snapshot; this
    # keeps submitted choices authoritative and avoids touching Codex config
    # while Codex is disabled.
    codex_enabled = (
        bool(options["codex_enabled"])
        if "codex_enabled" in options
        else bool(getattr(_codex_cfg, "ENABLE_CODEX_AUTO", False))
    )
    plan_check_enabled = bool(options.get("plan_check_enabled", True))

    report_job_progress("browser", "running", "正在创建并启动 Roxy 浏览器环境")
    client = RoxyBrowserClient()
    opened = _open_roxy_profile_with_capacity_wait(
        client,
        proxy,
        progress_callback=report_job_progress,
    )
    driver = None
    profile_discarded = False
    create_acknowledged = False
    openai_password: str | None = None
    access_token: str | None = None
    account_id: int | None = None
    totp_secret: str | None = None
    plan_check_session = None
    try:
        try:
            from core.registration_debug import attach_current_roxy
            attach_current_roxy(opened.debugger_address)
        except Exception:
            logger.exception("[Roxy注册][Debug] 启动浏览器网络抓包失败；注册流程继续执行")
        driver = _build_driver(opened)
        from core import registration_plan_capture
        registration_plan_capture.install_selenium(driver)
        report_job_progress("browser", "success", "Roxy 浏览器环境已启动")
        _center_browser_window(driver)
        driver.set_page_load_timeout(int(_cfg.ROXY_SELENIUM_TIMEOUT))
        try:
            driver.set_script_timeout(12)
        except Exception:
            pass
        logger.info("[Roxy注册] 开始：%s，profile=%s", email, opened.profile_id)

        otp_after_ts = time.time()
        report_job_progress("page", "running", "正在打开 ChatGPT 注册页")
        logger.info("[Roxy注册] 打开登录页：https://chatgpt.com/auth/login")
        _safe_get(
            driver,
            "https://chatgpt.com/auth/login",
            timeout=min(45, int(getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90)),
            attempts=2,
            accept_hosts=("chatgpt.com", "auth.openai.com"),
        )
        human_delay("navigate")
        _page_warmup(driver, reason="login_page")
        report_job_progress("page", "success", "注册页已加载")
        logger.info("[Roxy注册] 登录页加载完成，准备填写邮箱")
        _maybe_accept(driver)
        _check_manual_stop()

        # 填邮箱。OpenAI UI 会随出口 IP/语言变化；这里只按 DOM 技术属性找邮箱入口，
        # 并排除 Google/Apple/Microsoft 等第三方入口，不依赖按钮可见文字。
        report_job_progress("submit_email", "running", "正在填写并提交邮箱")
        def _mark_email_submitted() -> None:
            report_job_progress("submit_email", "success", "邮箱表单已提交")
            report_job_progress("auth_redirect", "running", "正在等待 OpenAI 认证页并处理异常跳转")

        next_state = _submit_email_and_wait_next(
            driver,
            email,
            attempts=3,
            on_submitted=_mark_email_submitted,
            allow_login_password=bool(existing_password),
        )
        _check_manual_stop()
        # 只要已经到达 OpenAI 的密码/OTP 等下一页，认证跳转就已经完成。密码创建是
        # 独立业务阶段，不能继续挂在 auth_redirect 上导致失败原因误导。
        report_job_progress("auth_redirect", "success", f"已进入认证下一步：{next_state}")

        # 新版注册流可能先进入 /create-account/password；参考 FlowPilot 的 fill-password 步骤，
        # 先设置密码并提交，然后再等待邮箱验证码页。
        password_stage_expected = password_required or bool(existing_password)
        report_job_progress(
            "login_password",
            "running" if password_stage_expected else "skipped",
            "正在创建并确认账号密码" if password_stage_expected else "一次性验证码模式，无需创建账号密码",
        )

        def _checkpoint_submitted_password(password: str) -> None:
            nonlocal account_id, create_acknowledged
            if existing_password or account_id is not None:
                return
            account_id = _save_pending_email_verification_checkpoint(
                email=email,
                openai_password=password,
                opened=opened,
                proxy=proxy,
            )
            report_registered_account(account_id)
            create_acknowledged = True
            logger.info(
                "[Roxy注册] 密码提交请求已发出，先保存可恢复检查点：id=%s email=%s",
                account_id,
                email,
            )

        try:
            openai_password = _fill_password_page_if_present(
                driver,
                email,
                timeout=25,
                existing_password=existing_password,
                on_password_submitted=_checkpoint_submitted_password,
            )
        except _PasswordTransitionTimeout:
            report_job_progress("login_password", "failed", "密码已提交，但远端结果仍待确认")
            raise
        except Exception as exc:
            if password_stage_expected:
                report_job_progress("login_password", "failed", f"账号密码处理失败: {type(exc).__name__}: {str(exc)[:180]}")
            raise
        else:
            if password_stage_expected:
                report_job_progress(
                    "login_password",
                    "success" if openai_password else "skipped",
                    "账号密码已提交并进入下一步" if openai_password else "已有登录态，无需再次提交密码",
                )
        if openai_password and account_id is None:
            account_id = _save_pending_email_verification_checkpoint(
                email=email,
                openai_password=openai_password,
                opened=opened,
                proxy=proxy,
            )
            report_registered_account(account_id)
            create_acknowledged = True
            logger.info(
                "[Roxy注册] 密码已提交，待邮箱验证账号检查点已保存：id=%s email=%s resume=%s",
                account_id,
                email,
                bool(existing_password),
            )
        resume_login_state = ""
        if existing_password:
            # 密码提交后可能进入邮箱 OTP，也可能进入 Authenticator TOTP。
            # 两种页面外观相似，必须与 Codex OAuth 共用同一个认证状态机。
            from core.roxy_codex_oauth import complete_openai_login_challenge

            resume_login_state = complete_openai_login_challenge(
                driver,
                email,
                existing_password,
                str(existing_totp_secret or ""),
                timeout=45,
            )
            logger.info(
                "[Roxy注册] 待验证账号公共登录状态机完成：email=%s state=%s",
                email,
                resume_login_state,
            )
        _check_manual_stop()

        report_job_progress("email_otp", "running", "正在等待并验证邮箱验证码")
        report_job_otp_evidence(
            request_kind="resume_login" if existing_password else "initial",
            ui_ack="unconfirmed",
            detail="页面已进入邮箱验证码步骤，但仅凭页面状态不能确认邮件请求已被接受",
        )
        last_otp_ui_ack = "unconfirmed"
        current_otp = otp_code
        max_otp_attempts = 3
        try:
            from config import email as _email_cfg
            otp_total_wait = max(1, int(getattr(_email_cfg, "OTP_MAX_WAIT", 240) or 240))
        except Exception:
            otp_total_wait = 240
        otp_budget = StageBudget.start(otp_total_wait)
        otp_wait_deadline = otp_budget.deadline
        otp_already_complete = resume_login_state == "advanced" or _has_access_token(driver)
        for otp_attempt in range(1, max_otp_attempts + 1):
            if otp_already_complete:
                break
            if current_otp is None:
                logger.info("[Roxy注册][OTP] 等待验证码：%s（第 %s/%s 次）", email, otp_attempt, max_otp_attempts)
                try:
                    attempt_wait = _registration_otp_attempt_wait_seconds(
                        otp_wait_deadline,
                        otp_attempt,
                        max_otp_attempts,
                    )
                    otp_budget.require("email OTP")
                    if attempt_wait <= 0:
                        raise TimeoutError(f"邮箱验证码总等待已达到 {otp_total_wait}s")
                    current_otp = wait_for_otp(
                        email,
                        after_ts=otp_after_ts,
                        max_wait=attempt_wait,
                    )
                except Exception as exc:
                    if otp_attempt >= max_otp_attempts:
                        failure_code, failure_detail = _classify_otp_wait_failure(
                            exc,
                            last_ui_ack=last_otp_ui_ack,
                        )
                        report_job_otp_evidence(
                            detail=failure_detail,
                            failure_code=failure_code,
                        )
                        report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                        raise RuntimeError(f"{failure_code}: {failure_detail}") from exc
                    # 不再用 after_ts=0 宽松捞旧码。高并发/重发场景下，旧码可能
                    # 属于同一邮箱的上一轮认证，提交后只会造成额外等待和再次重发。
                    logger.warning(
                        "[Roxy注册][OTP] 单轮等待结束仍未收到新验证码，重新发送后只等待新邮件（下一轮 %s/%s）：%s: %s",
                        otp_attempt + 1,
                        max_otp_attempts,
                        type(exc).__name__,
                        str(exc)[:180],
                    )
                    otp_after_ts = time.time()
                    try:
                        resend_result = _resend_email_otp_after_failure(
                            driver,
                            reason="等待邮箱验证码超时/未收到新验证码",
                            budget=otp_budget,
                        )
                    except Exception as resend_exc:
                        failure_code = "otp_request_unconfirmed"
                        failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
                        report_job_otp_evidence(
                            request_kind="resend",
                            ui_ack="rejected",
                            detail=failure_detail,
                            failure_code=failure_code,
                        )
                        report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                        raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
                    last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                    report_job_otp_evidence(
                        request_kind="resend",
                        ui_ack=last_otp_ui_ack,
                        detail="等待超时后请求重新发送验证码",
                    )
                    human_delay("api")
                    current_otp = None
                    continue
            logger.info("[Roxy注册][OTP] 收到验证码：%s", current_otp)
            _clear_otp_inputs(driver)
            otp_input_timeout = _budget_timeout(otp_budget, 20, minimum=1)
            if otp_input_timeout < 1:
                raise StageTimeout("email OTP input budget exhausted")
            _type_otp(driver, current_otp, timeout=max(1, int(otp_input_timeout)))
            logger.info("[Roxy注册][OTP] 已填写邮箱验证码")
            _check_manual_stop()
            human_delay("otp_input")
            try:
                _click_continue(driver)
                logger.info("[Roxy注册][OTP] 已提交邮箱验证码，等待资料页或登录态")
            except Exception as exc:
                logger.info("[Roxy注册][OTP] 未找到显式提交按钮，继续等待页面状态：%s", str(exc)[:120])

            outcome = _wait_after_email_otp_submit(driver, timeout=30, budget=otp_budget)
            if outcome in ('accepted', 'email_verified'):
                break
            if otp_attempt >= max_otp_attempts:
                failure_code = "otp_invalid_or_expired"
                failure_detail = "已取得并提交验证码，但页面未接受或验证码已过期"
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            logger.warning("[Roxy注册][OTP] 验证码错误/过期，准备重新发送并重新获取验证码（%s/%s）", otp_attempt + 1, max_otp_attempts)
            otp_after_ts = time.time()
            try:
                resend_result = _resend_email_otp_after_failure(
                    driver,
                    reason="邮箱验证码提交后页面无效或卡住",
                    budget=otp_budget,
                )
            except Exception as resend_exc:
                failure_code = "otp_request_unconfirmed"
                failure_detail = "验证码重发控件未能完成或缺少确认；不能断言服务端已经发信"
                report_job_otp_evidence(
                    request_kind="resend",
                    ui_ack="rejected",
                    detail=failure_detail,
                    failure_code=failure_code,
                )
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
            last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
            report_job_otp_evidence(
                request_kind="resend",
                ui_ack=last_otp_ui_ack,
                detail="验证码无效或页面未推进后请求重新发送",
            )
            human_delay("api")
            current_otp = None

        report_job_progress(
            "email_otp",
            "skipped" if otp_already_complete else "success",
            "已有登录态，无需再次验证邮箱" if otp_already_complete else "邮箱验证码已通过",
        )
        # about-you / profile 信息页：必须完成或确认已有登录态，不能静默跳过。
        report_job_progress("profile", "running", "正在填写账号资料")
        logger.info("[Roxy注册] 开始等待资料页/登录态")
        _check_manual_stop()
        profile_submitted = _complete_profile_page(driver, name, birthday, timeout=60)
        if profile_submitted:
            create_acknowledged = True
            # 给 OAuth 回调 / session cookie 写入一点时间。
            human_delay("post_auth")
            report_job_progress("profile", "success", "账号资料已提交")
        else:
            report_job_progress("profile", "skipped", "已有登录态，无需填写资料")

        report_job_progress("token", "running", "正在等待登录态并获取 Token")
        logger.info("[Roxy注册] 等待 ChatGPT 跳转并写入 session/accessToken")
        _check_manual_stop()
        token_budget = StageBudget.start(120)
        session_info = _fetch_chatgpt_session(driver, timeout=120, budget=token_budget)
        access_token = session_info["accessToken"]
        captured_plan_result = (
            registration_plan_capture.read_or_fetch_selenium(driver, access_token)
            if plan_check_enabled
            else None
        )
        report_job_progress("token", "success", "已获取 accessToken")
        logger.info("[Roxy注册] 已拿到 accessToken：%s", email)
        _check_manual_stop()

        # 注册主体到这里已经成功。先保存账号、随机登录密码和 Token，并立即绑定任务；
        # 后续 Codex/2FA 或 WebUI 进程即使中断，也不能把已创建账号当成注册失败丢掉。
        from core.registration_service import persist_registration_core

        account_id = persist_registration_core(
            email=email,
            access_token=access_token,
            email_source=resolve_email_source(email),
            proxy_used=proxy or None,
            batch_dir=batch_dir,
            extra={
                "user": session_info.get("user"),
                "account": session_info.get("account"),
                "expires": session_info.get("expires"),
                "roxybrowser": {"profile_id": opened.profile_id, "open_result": opened.raw},
                "account_password": openai_password,
                "registration_checkpoint": "core_persisted",
            },
        )
        logger.info("[Roxy注册] 注册主体已保存检查点：id=%s email=%s", account_id, email)

        codex_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_CODEX_AUTO=False，跳过 Codex",
        }
        try:
            if codex_enabled:
                report_job_progress("codex", "running", "正在执行 Codex OAuth")
                # 注册流程本身已创建 Roxy 一号一环境。这里不能再新建第二个 Roxy 环境；
                # 复用当前注册窗口并保留刚建立的登录态，直接开始 Codex 授权。
                from core.roxy_codex_oauth import run_roxy_codex_oauth
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=True，复用当前注册 Roxy 窗口执行 Codex 授权，不创建新环境")
                _check_manual_stop()
                codex_result = _run_in_isolated_browser_tab(
                    driver,
                    lambda: run_roxy_codex_oauth(
                        email,
                        proxy=proxy,
                        reuse_existing_profile=True,
                        existing_driver=driver,
                        existing_opened=opened,
                        force=True,
                        # 当前 Roxy 环境刚完成这个账号的注册，保留登录态可直接进入
                        # consent/手机验证；若登录态不可复用，页面仍会回落到邮箱 OTP。
                        clear_existing_state=False,
                    ),
                    label="Codex OAuth",
                )
                report_job_progress(
                    "codex",
                    "success" if codex_result.get("ok") else "failed",
                    str(codex_result.get("message") or "Codex OAuth 已完成")[:300],
                )
            else:
                logger.info("[Roxy注册][Codex] ENABLE_CODEX_AUTO=False，注册后跳过 Codex OAuth")
                report_job_progress("codex", "skipped", "未启用 Codex 自动授权")
        except Exception as exc:
            codex_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
            report_job_progress("codex", "failed", codex_result["message"])

        # 先跑 Codex，最大化复用注册完成后的 auth.openai.com 账号选择态；
        # 未完成的 MFA enrollment 会改变授权页状态，不能放在 Codex 前面。
        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            proxy=proxy,
            codex_result=codex_result,
        )
        report_registered_account(account_id)

        twofa_result = {
            "status": "skipped",
            "ok": True,
            "message": "ENABLE_2FA=False，跳过 Authenticator 2FA",
        }
        if twofa_enabled:
            report_job_progress("twofa", "running", "正在设置 Authenticator 2FA")
            try:
                def _checkpoint_totp_secret(secret: str) -> None:
                    nonlocal account_id, totp_secret
                    totp_secret = secret
                    account_id = _save_roxy_account_checkpoint(
                        email=email,
                        access_token=access_token,
                        session_info=session_info,
                        opened=opened,
                        openai_password=openai_password,
                        proxy=proxy,
                        totp_secret=totp_secret,
                        codex_result=codex_result,
                        twofa_result={
                            "status": "running",
                            "ok": False,
                            "message": "已保存 Authenticator key，正在激活 2FA",
                        },
                    )
                    report_registered_account(account_id)
                    logger.info("[Roxy注册][2FA] Authenticator key 已写入账号检查点，准备激活")

                twofa_driver = _twofa_cfg.get_twofa_driver()
                if twofa_driver == "protocol":
                    protocol_session = BrowserSession(proxy=proxy or "")
                    plan_check_session = protocol_session
                    totp_secret, fallback_used = setup_protocol_2fa_with_browser_fallback(
                        driver,
                        email,
                        protocol_session,
                        access_token,
                        on_secret=_checkpoint_totp_secret,
                    )
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": (
                            "协议失败后已通过浏览器 UI 启用 2FA"
                            if fallback_used
                            else "协议 2FA 已启用"
                        ),
                        "driver": "browser_fallback" if fallback_used else "protocol",
                    }
                else:
                    totp_secret = setup_roxy_2fa(driver, email, on_secret=_checkpoint_totp_secret)
                    twofa_result = {
                        "status": "success",
                        "ok": True,
                        "message": "浏览器 2FA 已启用",
                        "driver": "browser",
                    }
                report_job_progress("twofa", "success", twofa_result["message"])
            except Exception as exc:
                message = f"{type(exc).__name__}: {str(exc)[:180]}"
                twofa_result = {"status": "failed", "ok": False, "message": message}
                logger.error("[Roxy注册][2FA] 设置失败：%s", message)
                logger.debug("[Roxy注册][2FA] 错误详情", exc_info=True)
                report_job_progress("twofa", "failed", f"2FA 设置失败: {message}")
        else:
            report_job_progress("twofa", "skipped", "未启用 Authenticator 2FA")

        account_id = _save_roxy_account_checkpoint(
            email=email,
            access_token=access_token,
            session_info=session_info,
            opened=opened,
            openai_password=openai_password,
            proxy=proxy,
            totp_secret=totp_secret,
            codex_result=codex_result,
            twofa_result=twofa_result,
        )
        report_registered_account(account_id)

        # Final account metadata is updated by the existing checkpoint helper.
        # Plan lookup is independent work and is queued after the core account
        # has already been persisted, so a network failure cannot roll back
        # registration success.
        plan_result = {"status": "pending", "ok": False, "message": "套餐查询已独立入队"}
        if plan_check_enabled:
            try:
                from core import db
                if isinstance(captured_plan_result, dict) and captured_plan_result.get("ok"):
                    captured = dict(captured_plan_result)
                    captured["trigger"] = "registration_browser_response"
                    db.update_account_plan_check(acc_id=account_id, result=captured)
                    plan_result = {"status": "success", "ok": True, "message": "复用浏览器权益数据"}
                else:
                    from core.plan_check_service import enqueue_account_plan_check
                    queued = enqueue_account_plan_check(
                        account_id=account_id,
                        email=email,
                        access_token=access_token,
                        trigger="registration_auto",
                    )
                    plan_result = {
                        "status": "pending" if queued.get("accepted") or queued.get("busy") else "failed",
                        "ok": False,
                        "message": "套餐查询已入队" if queued.get("accepted") else str(queued.get("error") or "套餐查询未入队"),
                    }
            except Exception as exc:
                plan_result = {"status": "failed", "ok": False, "message": f"{type(exc).__name__}: {str(exc)[:180]}"}
        else:
            plan_result = {"status": "skipped", "ok": True, "message": "未启用注册后自动查套餐"}
        codex_ok = codex_result.get("ok") or codex_result.get("status") == "skipped"
        twofa_ok = twofa_result.get("ok") or twofa_result.get("status") == "skipped"
        errors = []
        if not codex_ok:
            errors.append(f"Codex 未完成: {codex_result.get('message')}")
        if not twofa_ok:
            errors.append(f"2FA 未完成: {twofa_result.get('message')}")
        if not plan_result.get("ok"):
            errors.append(f"套餐查询待处理: {plan_result.get('message')}")
        postprocess_ok = bool(codex_ok and twofa_ok and plan_result.get("ok"))
        from core.registration_postprocess import summarize_postprocess
        readiness = summarize_postprocess(
            core_success=True,
            password_present=bool(openai_password),
            outcomes={"twofa": twofa_result, "codex": codex_result, "plan_check": plan_result},
            password_required=password_required,
            twofa_required=twofa_enabled,
            codex_enabled=codex_enabled,
            plan_check_required=plan_check_enabled,
        )
        return {
            # 账号和 Token 已在前面的检查点落库，注册主体就是成功。Codex/2FA
            # 属于后置能力，失败时返回部分成功，不能让服务层误判为“没注册出账号”。
            "success": True,
            "registration_success": True,
            "postprocess_success": postprocess_ok,
            "partial_success": not postprocess_ok,
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "codex": codex_result,
            "twofa": twofa_result,
            "plan_check": plan_result,
            "next_actions": [action.as_dict() for action in readiness.next_actions],
            "account_readiness": readiness.account_readiness,
            "error": None if not errors else "; ".join(errors),
        }
    except Exception as exc:
        logger.error("[Roxy注册] 失败：%s: %s", type(exc).__name__, exc)
        logger.debug("[Roxy注册] 失败详情", exc_info=True)
        try:
            from core.registration_service import is_stop_requested
            stopped = is_stop_requested()
        except Exception:
            stopped = False
        if not stopped:
            try:
                from core.registration_debug import pause_current_failure
                pause_current_failure(driver, f"{type(exc).__name__}: {str(exc)[:500]}")
            except Exception:
                logger.exception("[Roxy注册][Debug] 保留失败现场失败；继续按原失败流程收口")
        # 未确认创建前通常可以回收邮箱；但 password 模式下缺少创建密码入口时，
        # 该地址可能已经在 OpenAI 侧进入已有账号/半成品账号状态。继续放回池里只会
        # 让后续任务反复命中登录 OTP 页，永远无法完成“账号+密码”注册。
        password_result_unknown = isinstance(exc, _PasswordTransitionTimeout)
        error_text = str(exc)
        disposable_proxy_failure = _is_disposable_pre_account_failure(
            error_text,
            create_acknowledged=create_acknowledged,
            account_id=account_id,
        )
        if disposable_proxy_failure and opened.created_by_run:
            try:
                client.discard_profile(opened)
                profile_discarded = True
                logger.info(
                    "[Roxy注册] 注册前阶段失败且未产生远端账号状态，已软删除临时环境释放重试额度：profile=%s",
                    opened.profile_id,
                )
            except Exception:
                logger.exception("[Roxy注册] 释放代理失败临时环境时出错；保留原失败结果")
        try:
            from core.email_provider import release_email
            password_target_missing = "missing_create_account_password_target_after_wait" in error_text
            release_email(
                email,
                status="failed" if create_acknowledged or password_target_missing or password_result_unknown else "available",
                note=f"Roxy注册失败: {error_text[:180]}",
            )
        except Exception:
            pass
        return {
            "success": False,
            "registration_pending": bool(account_id and not access_token),
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "request_unknown": password_result_unknown,
            "error": f"{type(exc).__name__}: {str(exc)[:300]}",
        }
    finally:
        if driver and not profile_discarded and not bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
            try:
                driver.quit()
            except Exception:
                pass
        if not profile_discarded and not bool(_cfg.ROXY_KEEP_BROWSER_OPEN):
            client.cleanup_profile(opened)
        if plan_check_session is not None:
            try:
                plan_check_session.session.close()
            except Exception:
                pass
