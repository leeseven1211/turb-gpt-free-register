"""ChatGPT browser-session acquisition shared by auth flows."""
from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlsplit

from core.registration.state_machine import PageState, StageBudget, StageTimeout

from .auth_context import (
    checkpoint as _checkpoint,
    current_execution_context,
    install_dispatches,
    time_proxy,
)
from .selenium_dom import _auth_terminal_page_state, _budget_timeout, _check_manual_stop
from .selenium_resource import _log_prefix, _safe_get

logger = logging.getLogger(__name__)
time = time_proxy
_CHATGPT_SESSION_URL = "https://chatgpt.com/api/auth/session"


def _diagnostic_url(value: object) -> str:
    """Keep session errors to a URL path; query strings may contain secrets."""
    try:
        parsed = urlsplit(str(value or ""))
        return parsed.path[:240] or "/"
    except Exception:
        return "<unknown>"

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


def _read_chatgpt_session_document(driver) -> dict | None:
    """Read the JSON document loaded at ``/api/auth/session``.

    Opening the endpoint as a document avoids loading the ChatGPT SPA merely
    to run the same session fetch from its homepage.  Keep this as a narrow
    fallback: if the browser returns HTML or a non-JSON body, the caller can
    still use the existing page-fetch path.
    """
    try:
        body = driver.execute_script(
            "return document.body ? (document.body.innerText || document.body.textContent || '') : '';"
        )
        data = json.loads(str(body or "").strip())
    except Exception:
        return None
    if isinstance(data, dict) and data.get("accessToken"):
        logger.info("%s /api/auth/session JSON 文档已返回 accessToken", _log_prefix(driver))
        return data
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
    context = current_execution_context()
    if budget is None and context is not None:
        budget = context.budget
    timeout = _budget_timeout(budget, timeout, minimum=0.0)
    end = time.monotonic() + max(0.0, timeout)
    auto_jump_end = time.monotonic() + max(3, int(auto_jump_wait or 15))
    last_data = None
    forced_chatgpt_open = False

    while time.monotonic() < end:
        _checkpoint()
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
                        _CHATGPT_SESSION_URL,
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

        # A successful callback may already have landed on the ChatGPT home
        # page. Replace that expensive SPA load with the small session JSON
        # document before probing the page via JavaScript.
        if (
            'chatgpt.com' in current
            and not forced_chatgpt_open
            and "/api/auth/session" not in current_lower
        ):
            try:
                safe_timeout = _budget_timeout(budget, 35, minimum=1)
                if budget is not None and safe_timeout < 1:
                    raise StageTimeout("OAuth session navigation budget exhausted")
                _safe_get(
                    driver,
                    _CHATGPT_SESSION_URL,
                    timeout=max(1, int(safe_timeout)),
                    attempts=2,
                    accept_hosts=("chatgpt.com",),
                )
                forced_chatgpt_open = True
                current = str(getattr(driver, "current_url", "") or "")
                document_data = _read_chatgpt_session_document(driver)
                if document_data:
                    return document_data
            except Exception as exc:
                last_data = f"{type(exc).__name__}: {exc}"

        if 'chatgpt.com' in current:
            document_data = (
                _read_chatgpt_session_document(driver)
                if "/api/auth/session" in current.lower()
                else None
            )
            if document_data:
                return document_data
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
        else:
            bounded_delay = current_execution_context()
            if bounded_delay is not None:
                delay = min(delay, bounded_delay.remaining(delay) or 0.0)
        if delay > 0:
            time.sleep(delay)

    raise RuntimeError(f"等待 /api/auth/session accessToken 超时，最后响应: {str(last_data)[:800]}")


install_dispatches(globals(), (
    "_read_chatgpt_session_once", "_switch_to_chatgpt_window_if_any",
    "_fetch_chatgpt_session", "_has_access_token", "_diagnostic_url",
))

__all__ = [
    "_read_chatgpt_session_once", "_switch_to_chatgpt_window_if_any",
    "_fetch_chatgpt_session", "_has_access_token",
]
