"""ChatGPT browser-session acquisition shared by auth flows."""
from __future__ import annotations

import json
import logging
import time
from urllib.parse import urlsplit

from core.auth.state_machine import PageState, StageBudget, StageTimeout

from core.auth.browser.auth_context import checkpoint as _checkpoint, current_execution_context, install_dispatches, time_proxy
from core.auth.browser.selenium_dom import _auth_terminal_page_state, _budget_timeout, _check_manual_stop
from core.auth.browser.selenium_resource import _log_prefix, _safe_get

logger = logging.getLogger('core.registration.session_auth')
time = time_proxy
_CHATGPT_SESSION_URL = "https://chatgpt.com/api/auth/session"
_CHATGPT_HOME_URL = "https://chatgpt.com/"


def _park_verified_registration_page(driver, *, budget: StageBudget, check_stop=None) -> bool:
    """完整会话已核验并落库后，停止首页加载并保留套餐查询所需的同源页面。"""
    def checkpoint():
        budget.check_cancelled()
        (check_stop or _check_manual_stop)()

    checkpoint()
    try:
        current = urlsplit(str(driver.current_url or ""))
        if (current.scheme != "https" or current.hostname != "chatgpt.com"
                or current.port not in (None, 443) or current.username or current.password):
            return False
        if current.path == "/api/auth/session":
            return True
        # 账号已经保存；先中止应用壳下载，导航异常也不会继续拉取大包。
        try:
            driver.execute_script("window.stop();")
        except Exception:
            # 脚本连接可能暂时不可用；导航仍有机会停止旧文档下载。
            checkpoint()
        checkpoint()
        if budget.expired():
            return False
        old_timeout = driver.timeouts.page_load
        try:
            driver.set_page_load_timeout(max(0.1, min(10, budget.remaining())))
            driver.get(_CHATGPT_SESSION_URL)
        finally:
            driver.set_page_load_timeout(old_timeout)
        checkpoint()
        current = urlsplit(str(driver.current_url or ""))
        return (current.scheme == "https" and current.hostname == "chatgpt.com"
                and current.port in (None, 443) and not current.username and not current.password
                and current.path == "/api/auth/session")
    except Exception as exc:
        checkpoint()
        logger.warning("%s 省流量页面收口未完成：%s；已保存的账号继续后处理", _log_prefix(driver), type(exc).__name__)
        return False


def _wait_registration_homepage(driver, *, timeout: float = 30, budget: StageBudget | None = None) -> dict:
    """只观察正常首页就绪；失败时保留已取得的会话和完整资源，不重新认证。"""
    wait = budget.child(timeout) if budget is not None else StageBudget.start(timeout)
    wait.check_cancelled()

    def pending(reason: str) -> dict:
        return {"ready": False, "reason": reason}

    try:
        current = urlsplit(str(driver.current_url or ""))
        if current.scheme != "https" or current.hostname != "chatgpt.com" or current.port not in (None, 443):
            return pending("foreign_origin")
        if current.path == "/api/auth/session":
            _check_manual_stop()
            if wait.expired():
                return pending("timeout")
            old_timeout = driver.timeouts.page_load
            try:
                driver.set_page_load_timeout(max(0.1, min(15, wait.remaining())))
                driver.get(_CHATGPT_HOME_URL)
            finally:
                driver.set_page_load_timeout(old_timeout)
    except Exception:
        wait.check_cancelled()
        _check_manual_stop()
        return pending("navigation_failed")

    while not wait.expired():
        _check_manual_stop()
        wait.check_cancelled()
        try:
            state = driver.execute_script(r"""
            const trusted = location.origin === 'https://chatgpt.com';
            const path = location.pathname || '/';
            if (!trusted) return {ready:false, reason:'foreign_origin'};
            if (path.startsWith('/api/') || path.startsWith('/auth/') || path === '/login') {
              return {ready:false, reason:'auth_page'};
            }
            const visible = el => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
              && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
            const hydrated = el => {
              for (let node = el, depth = 0; node && depth < 6; node = node.parentElement, depth++) {
                if (Object.keys(node).some(key => key.startsWith('__reactProps$') || key.startsWith('__reactFiber$'))) return true;
              }
              return false;
            };
            const composer = document.querySelector('#prompt-textarea');
            const editable = composer && (['INPUT','TEXTAREA'].includes(composer.tagName)
              ? !composer.disabled && !composer.readOnly : composer.isContentEditable === true);
            const composerReady = visible(composer) && editable
              && composer.getAttribute('aria-disabled') !== 'true' && hydrated(composer);
            const dialogVisible = [...document.querySelectorAll('[role="dialog"],[role="alertdialog"]')].some(visible);
            const ready = composerReady && !dialogVisible;
            return {ready, reason:ready ? 'ready' : 'app_loading'};
            """)
        except Exception:
            wait.check_cancelled()
            _check_manual_stop()
            return pending("probe_failed")
        wait.check_cancelled()
        _check_manual_stop()
        if wait.expired():
            return pending("timeout")
        if not isinstance(state, dict) or type(state.get("ready")) is not bool:
            return pending("probe_unavailable")
        if state["ready"]:
            return {"ready": True, "reason": "ready"}
        if state.get("reason") == "foreign_origin":
            return pending("foreign_origin")
        try:
            wait.sleep(min(0.5, wait.remaining()))
        except StageTimeout:
            return pending("timeout")
    return pending("timeout")


class ChatGPTSessionUnavailable(RuntimeError):
    """The session endpoint answered, but the browser is not authenticated."""

    code = "chatgpt_session_unavailable"


def _session_warning_banner(data: object) -> bool:
    """识别 ChatGPT 返回的未登录/拦截壳，而不是把它当成持续加载。"""
    if not isinstance(data, dict):
        return False
    return "WARNING_BANNER" in data or any(
        "WARNING_BANNER" in str(value or "") for value in data.values()
    )


def _session_unavailable_message(data: object, status: object = None) -> str:
    status_text = str(status or (data.get("_http_status") if isinstance(data, dict) else "unknown"))
    marker = "WARNING_BANNER" if _session_warning_banner(data) else "no_access_token"
    return (
        f"{ChatGPTSessionUnavailable.code}: /api/auth/session 未返回 accessToken "
        f"(status={status_text}, marker={marker})"
    )


def _diagnostic_url(value: object) -> str:
    """Keep session errors to a URL path; query strings may contain secrets."""
    try:
        parsed = urlsplit(str(value or ""))
        return parsed.path[:240] or "/"
    except Exception:
        return "<unknown>"

def _has_access_token(driver, *, budget: StageBudget | None = None, timeout: float = 2.0) -> bool:
    """仅在 ChatGPT 同源页面执行有界探测，认证站点交给本地页面状态识别。"""
    _checkpoint()
    probe_timeout = _budget_timeout(budget, max(0.0, min(timeout, 2.0)), minimum=0.0)
    if probe_timeout <= 0:
        return False
    try:
        current = urlsplit(str(getattr(driver, "current_url", "") or ""))
        if current.scheme != "https" or current.hostname != "chatgpt.com" or current.port not in (None, 443):
            return False
        result = driver.execute_async_script(r"""
        const timeoutMs = arguments[0];
        const done = arguments[arguments.length - 1];
        // Python 检查后仍可能发生导航；浏览器内再次校验，禁止跨域探测。
        if (location.origin !== 'https://chatgpt.com') { done(false); return; }
        const controller = new AbortController();
        let settled = false;
        const finish = value => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          done(value);
        };
        const timer = setTimeout(() => { controller.abort(); finish(false); }, timeoutMs);
        fetch('/api/auth/session', {credentials:'include', signal:controller.signal})
          .then(r => r.json()).then(j => finish(Boolean(j && j.accessToken)))
          .catch(() => finish(false));
        """, max(1, int(probe_timeout * 1000)))
        return bool(result)
    except Exception:
        return False

def _read_chatgpt_session_once(driver, *, timeout: float | None = None, strict_read: bool = False) -> dict | None:
    """当前页面必须在 chatgpt.com；读取 /api/auth/session，拿不到 token 返回 None。"""
    script = r"""
    const done = arguments[arguments.length - 1];
    const timeoutMs = arguments.length > 1 ? Number(arguments[0]) : 0;
    if (timeoutMs > 0 && location.origin !== 'https://chatgpt.com') {
      done({ok:false, error_type:'origin_changed'}); return;
    }
    const controller = timeoutMs > 0 ? new AbortController() : null;
    let settled = false, timer = null;
    const finish = result => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      done(result);
    };
    if (controller) timer = setTimeout(() => {
      controller.abort(); finish({ok:false, error_type:'timeout'});
    }, timeoutMs);
    fetch('/api/auth/session', {credentials: 'include', ...(controller ? {signal:controller.signal} : {})})
      .then(async r => {
        const text = await r.text();
        let data = {}, jsonValid = Boolean(text.trim());
        try { data = JSON.parse(text || '{}'); } catch (_) { data = {text: text}; jsonValid = false; }
        if (data && typeof data === 'object') data._http_status = r.status;
        finish({ok: true, status: r.status, data: data, json_valid: jsonValid});
      })
      .catch(() => finish({ok:false, error_type:'session_read_failed'}));
    """
    old_script_timeout = None
    if timeout is not None:
        timeout = _budget_timeout(None, max(0.0, float(timeout)), minimum=0.0)
        if timeout <= 0:
            raise StageTimeout("会话读取预算已耗尽")
        current = urlsplit(str(getattr(driver, "current_url", "") or ""))
        if current.scheme != "https" or current.hostname != "chatgpt.com" or current.port not in (None, 443):
            if strict_read:
                raise RuntimeError("request_unknown: session_probe_origin_changed: 会话读取页面已变化")
            return None
        # Selenium 导航路径可能留下 8 秒脚本上限；只为本次完整响应体读取放宽并恢复。
        previous = getattr(getattr(driver, "timeouts", None), "script", None)
        if isinstance(previous, (int, float)) and callable(getattr(driver, "set_script_timeout", None)):
            driver.set_script_timeout(timeout + 1.0)
            old_script_timeout = previous
    read_started = time.monotonic()
    driver._registration_session_diagnostic = {"status": None, "token_present": None}
    try:
        result = (driver.execute_async_script(script) if timeout is None else
                  driver.execute_async_script(script, max(1, int(timeout * 1000))))
    except Exception:
        driver._registration_session_diagnostic = {
            "status": None, "token_present": None, "error_type": "browser_read_failed",
            "duration_ms": max(0, int((time.monotonic() - read_started) * 1000)),
        }
        raise
    finally:
        if old_script_timeout is not None:
            try:
                driver.set_script_timeout(old_script_timeout)
            except Exception:
                logger.debug("%s 恢复 session 读取脚本超时失败", _log_prefix(driver))
    response = result if isinstance(result, dict) else {}
    response_data = response.get("data") if isinstance(response.get("data"), dict) else {}
    body_confirmed = response.get("ok") is True and isinstance(response.get("data"), dict) and response.get("json_valid") is not False
    status = response.get("status")
    driver._registration_session_diagnostic = {
        "status": status if type(status) is int and 100 <= status <= 599 else None,
        "duration_ms": max(0, int((time.monotonic() - read_started) * 1000)),
        "token_present": bool(response_data.get("accessToken")) if body_confirmed else None,
        "json_valid": response.get("json_valid") if type(response.get("json_valid")) is bool else None,
        "marker": ("" if response_data.get("accessToken") else
                   "WARNING_BANNER" if _session_warning_banner(response_data) else "no_access_token" if body_confirmed else ""),
        "error_type": response.get("error_type") if response.get("error_type") in {
            "origin_changed", "timeout", "session_read_failed",
        } else "",
    }
    if strict_read:
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("request_unknown: session_probe_incomplete: 会话响应未完整读取")
        if result.get("status") in {401, 403}:
            raise ChatGPTSessionUnavailable(_session_unavailable_message({}, result.get("status")))
        if (result.get("status") != 200 or result.get("json_valid") is False
                or not isinstance(result.get("data"), dict)):
            raise RuntimeError("request_unknown: session_probe_incomplete: 会话响应无法核验")
    if result and result.get("ok"):
        data = result.get("data") or {}
        if data.get("accessToken"):
            logger.info("%s /api/auth/session 已返回 accessToken", _log_prefix(driver))
            return data
        if _session_warning_banner(data) or result.get("status") in {401, 403}:
            raise ChatGPTSessionUnavailable(
                _session_unavailable_message(data, result.get("status"))
            )
        logger.info(
            "%s 等待 ChatGPT session 写入 accessToken，当前响应 keys=%s status=%s",
            _log_prefix(driver), list(data.keys()), result.get("status"),
        )
    return None


def _read_profile_session_once(driver, *, timeout: float, expected_email: str | None = None) -> dict:
    """认证后读取完整会话，匹配身份后供资料确认和 Token 阶段短时复用。"""
    expected = str(expected_email or "").strip().casefold()
    cached = getattr(driver, "_registration_verified_session", None)
    if timeout > 0 and expected and isinstance(cached, dict):
        data = cached.get("data")
        user = data.get("user") if isinstance(data, dict) else None
        actual = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
        if (isinstance(data, dict) and data.get("accessToken") and actual == expected == cached.get("email")
                and time.monotonic() < cached.get("expires_at", 0)
                and str(getattr(driver, "current_url", "")) == cached.get("url")):
            return data
    try:
        data = _read_chatgpt_session_once(driver, timeout=timeout)
    except Exception as exc:
        _checkpoint()
        # 只记录异常类型，避免把浏览器原文中的 Cookie、Token 或账号带入摘要。
        exception_type = type(exc).__name__
        logger.warning("%s 完整会话读取未完成，异常类型=%s", _log_prefix(driver), exception_type)
        raise RuntimeError(
            "request_unknown: profile_session_read_failed: "
            f"认证提交后的会话读取未完成，已保留原提交（异常类型={exception_type}）"
        ) from exc
    if not isinstance(data, dict) or not data.get("accessToken"):
        raise RuntimeError("request_unknown: profile_session_unconfirmed: 认证提交后的会话尚未确认登录态，已保留原提交")
    if expected:
        user = data.get("user")
        actual = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
        if not actual or actual != expected:
            raise RuntimeError("request_unknown: session_identity_mismatch: 会话身份未匹配任务邮箱，已停止确认")
        driver._registration_verified_session = {
            "data": data, "email": expected, "url": str(driver.current_url),
            "expires_at": time.monotonic() + 30.0,
        }
    return data


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
    if _session_warning_banner(data):
        raise ChatGPTSessionUnavailable(_session_unavailable_message(data))
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
    prefer_homepage: bool = False,
) -> dict:
    """等待页面完成跳转并从 ChatGPT 页面内读取登录 session/accessToken。

    旧逻辑会在 auth.openai.com 上一直等到总超时，Cloak/部分 Chromium 场景下
    实际账号已创建成功但当前句柄 URL 没及时更新，导致白等 120 秒。现在只给
    自动跳转 `auto_jump_wait` 秒；超过后立即主动打开 chatgpt.com 读 session。
    Roxy 注册通过 prefer_homepage 保留正常首页，其他认证调用沿用原有文档读取路径。
    """
    context = current_execution_context()
    if budget is None and context is not None:
        budget = context.budget
    timeout = _budget_timeout(budget, timeout, minimum=0.0)
    end = time.monotonic() + max(0.0, timeout)
    cached = getattr(driver, "_registration_verified_session", None)
    if isinstance(cached, dict):
        driver._registration_verified_session = None
        data = cached.get("data")
        user = data.get("user") if isinstance(data, dict) else None
        actual = str(user.get("email") or "").strip().casefold() if isinstance(user, dict) else ""
        if (timeout > 0 and isinstance(data, dict) and data.get("accessToken") and actual
                and actual == cached.get("email") and time.monotonic() < cached.get("expires_at", 0)
                and str(getattr(driver, "current_url", "")) == cached.get("url")):
            logger.info("%s 复用资料阶段已确认身份的完整会话", _log_prefix(driver))
            return data
    auto_jump_end = time.monotonic() + max(3, int(auto_jump_wait or 15))
    last_data = None
    forced_chatgpt_open = False
    warning_banner_probes = 0

    def _remember_session_probe_error(exc: Exception) -> None:
        nonlocal last_data, warning_banner_probes
        last_data = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, ChatGPTSessionUnavailable):
            warning_banner_probes += 1
            # WARNING_BANNER/401/403 is an explicit unauthenticated response.
            # Give a just-completed callback a few short probes, but do not
            # burn the full 120-second token budget on a known auth shell.
            if warning_banner_probes >= 3:
                raise RuntimeError(
                    f"等待 /api/auth/session accessToken 超时；{last_data}"
                ) from exc
        else:
            warning_banner_probes = 0

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
                        _CHATGPT_HOME_URL if prefer_homepage else _CHATGPT_SESSION_URL,
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
                    _remember_session_probe_error(exc)
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
            and not prefer_homepage
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
                _remember_session_probe_error(exc)

        if 'chatgpt.com' in current:
            document_data = (
                _read_chatgpt_session_document(driver)
                if "/api/auth/session" in current.lower()
                else None
            )
            if document_data:
                return document_data
            _checkpoint()
            # 页面识别、跳转和前次轮询已经消耗的时间不能再分配给本次读取。
            read_timeout = _budget_timeout(budget, max(0.0, end - time.monotonic()), minimum=0.0)
            if read_timeout <= 0:
                break
            try:
                data = _read_chatgpt_session_once(driver, timeout=read_timeout)
                if data:
                    return data
                last_data = "session 暂无 accessToken"
            except Exception as exc:
                _remember_session_probe_error(exc)
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
    "_fetch_chatgpt_session", "_wait_registration_homepage", "_has_access_token", "_diagnostic_url",
))

__all__ = [
    "_read_chatgpt_session_once", "_switch_to_chatgpt_window_if_any",
    "_fetch_chatgpt_session", "_wait_registration_homepage", "_has_access_token", "ChatGPTSessionUnavailable",
]
