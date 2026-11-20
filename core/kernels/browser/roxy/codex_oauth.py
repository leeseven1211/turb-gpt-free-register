# -*- coding: utf-8 -*-
"""Codex browser execution. Domain services inject current compatibility helpers.

This module owns requests/page transitions; credential reads, task reporting,
resource acquisition and callback settlement remain with the caller.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse


@dataclass(frozen=True)
class BrowserExecutionContext:
    """Explicit current-call dependencies; no domain module or mutable globals.

    Compatibility wrappers build this for every invocation so replacing a legacy
    helper continues to affect the same point in the execution chain.
    """

    AccountUnusableError: Any
    AuthPageError: Any
    EmailSubmissionUnknown: Any
    MfaSecretMissingError: Any
    PageState: Any
    PasswordRejectedError: Any
    PasswordTransitionTimeout: Any
    StageBudget: Any
    TimeoutException: Any
    account_dead_login_codes: Any
    auth_checkpoint: Any
    auth_page_error: Any
    auth_path_for_log: Callable[..., Any]
    bind_auth_observer: Any
    call_cancellable: Any
    load_callback_timeout: Callable[[], int]
    cancellable_sleep: Any
    check_cancelled: Any
    classify_page: Any
    clear_confirmed_email_submission: Any
    click_any: Any
    click_consent_retry_button: Callable[..., Any]
    click_if_present: Callable[..., Any]
    click_passwordless_signup_if_present: Any
    current_execution_context: Any
    detect_account_unusable_login_state: Callable[..., Any]
    detect_account_unusable_response_body: Any
    do_phone_verification_if_present: Callable[..., Any]
    email_otp_page_state: Any
    email_ui_submission_state: Any
    extract_callback_url_from_any_window: Callable[..., Any]
    extract_callback_url_from_page: Callable[..., Any]
    fill_password_page_if_present: Any
    has_access_token: Any
    has_strict_add_phone_form: Callable[..., Any]
    human_delay: Any
    is_browser_error_page_state: Callable[..., Any]
    is_callback_url: Callable[..., Any]
    is_email_verification_page: Any
    is_empty_auth_challenge_state: Callable[..., Any]
    is_explicit_password_rejection_state: Callable[..., Any]
    is_login_advanced: Callable[..., Any]
    is_login_password_page: Any
    is_password_recovery_profile_page: Callable[..., Any]
    is_phone_code_page: Callable[..., Any]
    is_saved_create_password_page: Callable[..., Any]
    is_saved_login_password_route: Callable[..., Any]
    is_terminal_auth_error_page: Callable[..., Any]
    is_totp_login_page: Callable[..., Any]
    logger: Any
    clock: Any
    login_challenge_state: Callable[..., Any]
    open_offered_saved_password: Callable[..., Any]
    password_evidence: Any
    password_prepare_reasons: Any
    password_receipt_ids: Any
    password_rejection_markers: Any
    password_recovery_pending: Callable[[Any], bool]
    raise_auth_page_error: Callable[..., Any]
    record_browser_submission_fact: Any
    recover_email_submit_if_stuck: Any
    refresh_auth_challenge_after_submit: Callable[..., Any]
    report_login_stage: Callable[..., Any]
    reset_password_via_email: Callable[..., Any]
    safe_get: Any
    select_existing_account_if_present: Callable[..., Any]
    submit_email_via_browser_nextauth: Any
    submit_saved_login_password: Callable[..., Any]
    submit_saved_login_totp: Callable[..., Any]
    type_otp: Any
    uses_roxy_saved_password_entry: Callable[..., Any]
    wait_for_callback: Callable[..., Any]


def _is_callback_url(execution: BrowserExecutionContext, url: str) -> bool:
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


def _auth_path_for_log(execution: BrowserExecutionContext, value: str | None) -> str:
    """日志只保留受信任的固定路径，丢弃查询参数和动态路径段。"""
    try:
        parsed = urlparse(str(value or ""))
        host = (parsed.hostname or "").lower()
        path = parsed.path.rstrip("/").lower() or "/"
        port = parsed.port
    except ValueError:
        return "-"
    if parsed.scheme.lower() == "http" and host in ("localhost", "127.0.0.1"):
        return "/auth/callback" if port == 1455 and path == "/auth/callback" else "-"
    if parsed.scheme.lower() != "https" or host not in ("auth.openai.com", "chatgpt.com"):
        return "-"
    if path.startswith("/mfa-challenge/"):
        return "/mfa-challenge/*"
    if path.startswith("/sign-in-with-chatgpt/"):
        return "/sign-in-with-chatgpt/*"
    if path in {
        "/auth/login", "/auth/error", "/log-in", "/log-in/password",
        "/email-verification", "/add-phone", "/phone-verification",
        "/workspace", "/consent", "/oauth/authorize",
    }:
        return path
    return "/other"


def _extract_callback_url_from_page(execution: BrowserExecutionContext, driver) -> str:
    """从当前页面提取 OAuth callback URL。

    浏览器跳转到 http://localhost:1455/auth/callback?... 时，本地没有服务监听会显示
    chrome-error://chromewebdata/。地址栏可能变成 chrome-error，但 Chromium 的
    performance navigation entry 仍保留原始 callback URL，可直接提取后提交 CPA。
    """
    try:
        current = str(driver.current_url or "")
        if execution.is_callback_url(current):
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
            if execution.is_callback_url(str(url)):
                execution.logger.info("[Codex][Browser] 已从浏览器性能记录提取 callback")
                return str(url)
    except Exception as exc:
        execution.logger.debug("[Codex][Browser] 从页面提取 callback 失败：%s", type(exc).__name__)
    return ""


def _extract_callback_url_from_any_window(execution: BrowserExecutionContext, driver) -> str:
    found = execution.extract_callback_url_from_page(driver)
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
                found = execution.extract_callback_url_from_page(driver)
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


def _wait_for_callback(execution: BrowserExecutionContext, driver, timeout: int | None = None) -> str:
    end = execution.clock.time() + (timeout or int(execution.load_callback_timeout()))
    last_url = ""
    while execution.clock.time() < end:
        execution.check_cancelled()
        try:
            current = str(driver.current_url or "")
            if current != last_url:
                execution.logger.debug("[Codex][Browser] 当前页面 path=%s", execution.auth_path_for_log(current))
                last_url = current
            callback = execution.extract_callback_url_from_any_window(driver)
            if callback:
                return callback
        except Exception:
            pass
        execution.cancellable_sleep(0.5)
    raise RuntimeError(f"等待 Codex callback 超时，最后 path={execution.auth_path_for_log(last_url)}")


def _click_if_present(execution: BrowserExecutionContext, driver, selectors: list[str], timeout: int = 3) -> bool:
    try:
        execution.click_any(driver, selectors, timeout=timeout)
        return True
    except Exception:
        return False


def _click_consent_retry_button(execution: BrowserExecutionContext, driver, *, timeout: int = 2) -> bool:
    """Retry a consent page whose own data request failed to load.

    OpenAI renders this state as a generic ``Failed to fetch`` page with a
    ``Try again`` button.  It is distinct from the OAuth authorization button;
    without explicitly clicking it the browser can remain on the consent URL
    while the callback wait loop has nothing to observe.
    """
    return execution.click_if_present(
        driver,
        [
            "//button[contains(normalize-space(.), 'Try again')]",
            "//button[contains(normalize-space(.), 'Retry')]",
            "//button[contains(normalize-space(.), '重试')]",
            "//button[contains(@aria-label, 'Try again')]",
            "//button[contains(@aria-label, 'Retry')]",
            "//button[contains(@aria-label, '重试')]",
        ],
        timeout=timeout,
    )


def _login_challenge_state(execution: BrowserExecutionContext, driver) -> dict:
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
        # driver 失效时再次读取 current_url 也可能抛 InvalidSessionId，不能让诊断覆盖原始错误。
        try:
            fallback_url = str(driver.current_url or "")
        except Exception:
            fallback_url = ""
        return {"url": fallback_url, "error": f"{type(exc).__name__}: {exc}"}


def _is_totp_login_page(execution: BrowserExecutionContext, driver, state: dict | None = None) -> bool:
    state = state or execution.login_challenge_state(driver)
    if not isinstance(state, dict):
        return False
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


def _is_explicit_password_rejection_state(execution: BrowserExecutionContext, state: dict | None) -> bool:
    """Distinguish a confirmed wrong password from a page/transport timeout."""
    if not isinstance(state, dict):
        return False
    text = " ".join(
        (
            str(state.get("text") or ""),
            " ".join(str(item) for item in (state.get("errors") or [])),
        )
    ).lower()
    return any(marker in text for marker in execution.password_rejection_markers)


def _is_saved_login_password_route(execution: BrowserExecutionContext, driver) -> bool:
    try:
        current = urlparse(str(driver.current_url or ""))
        return (
            current.scheme == "https"
            and current.hostname == "auth.openai.com"
            and current.port in (None, 443)
            and not current.username
            and not current.password
            and current.path.rstrip("/") == "/log-in/password"
        )
    except (TypeError, ValueError):
        return False


def _is_saved_create_password_page(execution: BrowserExecutionContext, driver, state: dict) -> bool:
    """新增创建密码分支只接受 Roxy 的真实可信认证表单。"""
    if not execution.uses_roxy_saved_password_entry(driver) or execution.classify_page(state) != execution.PageState.PASSWORD_CREATE:
        return False
    try:
        current = urlparse(str(state.get("url") or ""))
        return (
            current.scheme == "https" and current.hostname == "auth.openai.com"
            and current.port in (None, 443) and not current.username and not current.password
        )
    except (TypeError, ValueError):
        return False


def _submit_saved_login_password(execution: BrowserExecutionContext, driver, email: str, password: str, *, on_candidate_password_confirmed=None) -> None:
    if not password:
        raise RuntimeError("账号已进入登录密码页，但本地没有保存注册密码，已在手机号验证前停止")
    # 共享能力等待表单接管、准确点击提交按钮并观察一次提交的结果；
    # requestSubmit 会绕过按钮的 onClick，不能替代真实密码按钮流程。
    deadline = execution.clock.monotonic() + 120
    fill_kwargs = {
        "existing_password": password,
        "login_rejection_detector": execution.is_explicit_password_rejection_state,
    }
    if execution.uses_roxy_saved_password_entry(driver):
        fill_kwargs["prefer_saved_password_entry"] = True
        # 调度已选定真实密码表单；若等待时回到 OTP，不能再点击一次入口。
        fill_kwargs["saved_password_entry_already_attempted"] = True
    candidate_confirmation_failed = False
    if on_candidate_password_confirmed is not None:
        def confirm_candidate(*args, **kwargs):
            nonlocal candidate_confirmation_failed
            try:
                return on_candidate_password_confirmed(*args, **kwargs)
            except BaseException:
                candidate_confirmation_failed = True
                raise

        fill_kwargs['on_candidate_password_confirmed'] = confirm_candidate
    try:
        execution.fill_password_page_if_present(
            driver, email, timeout=60, **fill_kwargs,
        )
    except RuntimeError as exc:
        if candidate_confirmation_failed or isinstance(exc, execution.AuthPageError):
            raise
        receipt = getattr(driver, "_browser_submission_receipt", None)
        if (
            "password_form_not_ready" not in str(exc)
            or getattr(receipt, "phase", "") != "not_dispatched"
            or not execution.is_saved_login_password_route(driver)
        ):
            raise

        prepare_reason = getattr(driver, "_password_prepare_reason", "")
        prepare_reason = prepare_reason if isinstance(prepare_reason, str) and prepare_reason in execution.password_prepare_reasons else "unexpected_result"
        prepare_stage = getattr(driver, "_password_prepare_stage", "")
        prepare_stage = prepare_stage if isinstance(prepare_stage, str) and prepare_stage in {"input", "typing", "queue"} else "input"
        execution.logger.warning(
            "[Codex][Browser] 密码准备预算耗尽且确认未派发：阶段=%s，原因=%s；沿用原恢复条件检查同页刷新",
            prepare_stage, prepare_reason,
        )
        execution.raise_auth_page_error(driver, execution.login_challenge_state(driver), remaining=deadline - execution.clock.monotonic())
        execution.auth_checkpoint()
        remaining = deadline - execution.clock.monotonic()
        if remaining <= 1:
            raise
        old_timeout = getattr(getattr(driver, "timeouts", None), "page_load", None)
        try:
            driver.set_page_load_timeout(min(10.0, remaining))
            try:
                driver.refresh()
            except execution.TimeoutException:
                if not execution.is_saved_login_password_route(driver):
                    raise
                execution.logger.warning("[Codex][Browser] 密码登录页刷新等待超时，仍停留在原登录入口")
        finally:
            if isinstance(old_timeout, (int, float)):
                driver.set_page_load_timeout(old_timeout)

        execution.raise_auth_page_error(driver, execution.login_challenge_state(driver), remaining=deadline - execution.clock.monotonic())
        if not execution.is_saved_login_password_route(driver):
            return
        execution.auth_checkpoint()
        remaining = deadline - execution.clock.monotonic()
        if remaining <= 0:
            raise
        execution.logger.warning("[Codex][Browser] 密码准备未完成且确认未派发，已刷新同一登录页并继续剩余预算：阶段=%s，原因=%s", prepare_stage, prepare_reason)
        execution.fill_password_page_if_present(
            driver, email, timeout=max(1, int(remaining)), **fill_kwargs,
        )
    execution.logger.info("[Codex][Browser] 已使用保存密码确认后续登录分支：email=%s", email)


def _submit_saved_login_totp(execution: BrowserExecutionContext, driver, email: str, totp_secret: str) -> None:
    if not totp_secret:
        raise execution.MfaSecretMissingError(
            "登录要求 Authenticator 验证，但本地没有 TOTP 密钥，已在手机号验证前停止"
        )
    import pyotp

    remaining = 30 - (int(execution.clock.time()) % 30)
    if remaining < 6:
        context = execution.current_execution_context()
        if context is not None and context.budget is not None:
            context.budget.sleep(remaining + 1, sleeper=execution.clock.sleep)
        else:
            execution.clock.sleep(remaining + 1)
    execution.auth_checkpoint()
    execution.type_otp(driver, pyotp.TOTP(totp_secret).now(), timeout=15)
    if not execution.click_if_present(driver, [
        "button[type='submit']",
        "input[type='submit']",
        "//button[contains(., 'Continue')]",
        "//button[contains(., '继续')]",
        "//button[contains(., 'Verify')]",
        "//button[contains(., '验证')]",
        "//button[contains(., '確認')]",
    ], timeout=8):
        raise RuntimeError("Authenticator 验证页缺少提交按钮")
    execution.logger.info("[Codex][Browser] 已使用本地 TOTP 提交 Authenticator 登录：email=%s", email)


def _is_login_advanced(execution: BrowserExecutionContext, driver, state: dict | None = None) -> bool:
    state = state or execution.login_challenge_state(driver)
    url = str(state.get("url") or "").lower()
    if execution.auth_page_error(state) is not None or execution.is_terminal_auth_error_page(state):
        return False
    if execution.is_callback_url(url):
        return True
    try:
        location = urlparse(url)
        if (location.scheme != "https" or location.port not in (None, 443)
                or location.username or location.password):
            return False
    except ValueError:
        return False
    if location.hostname == "chatgpt.com" and not location.path.startswith("/auth/"):
        return bool(execution.has_access_token(driver))
    mounted_controls = any(
        isinstance(item, dict) and item.get("visible", True)
        for item in [*(state.get("inputs") or []), *(state.get("buttons") or [])]
    )
    if location.hostname == "auth.openai.com" and mounted_controls:
        # 这里只确认真实页面可交给手机号/工作区/授权处理，Session 成功由调用方核验。
        return any(marker in location.path for marker in ("/add-phone", "/workspace", "/consent", "/oauth/authorize"))
    return False


def _is_browser_error_page_state(execution: BrowserExecutionContext, state: dict | None) -> bool:
    """Recognize Chrome's navigation error page before the challenge timeout."""
    state = state or {}
    url = str(state.get("url") or "").strip().lower()
    errors = " ".join(str(item or "") for item in (state.get("errors") or [])).lower()
    return url.startswith("chrome-error://") or "chrome-error://" in errors


def _is_terminal_auth_error_page(execution: BrowserExecutionContext, state: dict | None) -> bool:
    """Recognize ChatGPT's auth error route before generic home-page logic."""
    state = state or {}
    try:
        parsed = urlparse(str(state.get("url") or ""))
    except Exception:
        return False
    return parsed.hostname in {"chatgpt.com", "auth.openai.com"} and parsed.path.rstrip("/").endswith("/auth/error")


def _detect_account_unusable_login_state(execution: BrowserExecutionContext, state: dict | None) -> str:
    """Read structured account errors exposed by the auth page diagnostics.

    Roxy can expose an OpenAI auth error in the page's error nodes after the
    password/TOTP submit, before any email-OTP response hook runs. Restrict
    this path to the real auth origin and an explicit error_code field so
    ordinary page copy or network diagnostics cannot mark an account dead.
    """
    state = state or {}
    try:
        parsed = urlparse(str(state.get("url") or ""))
        if parsed.scheme.lower() != "https" or parsed.hostname != "auth.openai.com":
            return ""
    except Exception:
        return ""
    pattern = re.compile(r"\berror_code\s*[:=]\s*([a-z0-9_]+)\b", re.IGNORECASE)
    for item in state.get("errors") or []:
        match = pattern.search(str(item or ""))
        if match:
            code = match.group(1).lower()
            if code in execution.account_dead_login_codes:
                return code
    return ""


def _complete_login_challenge_after_email(execution: BrowserExecutionContext,
    driver,
    email: str,
    password: str,
    totp_secret: str,
    *,
    timeout: int = 45,
    otp_provider=None,
    allow_password_reset: bool = False,
    on_password_reset_submitted=None,
    on_password_confirmed=None,
    force_password_reset: bool = False,
    stage_reporter=None,
    password_already_submitted: bool = False,
    password_recovery=None,
    allow_profile_handoff: bool = False,
    on_candidate_password_confirmed=None,
    allow_passwordless_fallback: bool = False,
    page_classifier=None,
) -> str:
    """解析登录挑战；启用恢复时可返回资料交接，完整会话仍由上层核验。"""
    classify = page_classifier if callable(page_classifier) else execution.classify_page
    end = execution.clock.time() + max(5, int(timeout))
    password_submitted_at = 0.0
    password_unknown_retry_done = False
    password_unknown_receipt = None
    saved_password_created = False
    totp_submitted_at = 0.0
    passwordless_clicked = False
    passwordless_clicks = 0
    passwordless_wait_started = 0.0
    passwordless_last_result: dict = {}
    totp_refresh_done = False
    initial_empty_challenge_seen_at = 0.0
    initial_challenge_refresh_done = False
    email_shell_seen_at = 0.0
    blank_login_shell_seen_at = 0.0
    email_resubmit_done = False
    nextauth_fallback_done = False
    # 注册驱动可能已提交过保存密码，再交给公共状态机处理 OTP/TOTP。
    # 这次交接不能重新获得一次密码入口和提交机会。
    roxy_saved_password_entry = execution.uses_roxy_saved_password_entry(driver)
    offered_password_attempted = password_already_submitted
    passwordless_fallback_allowed = bool(
        allow_passwordless_fallback and not force_password_reset and password_recovery is None
        and on_candidate_password_confirmed is None
    )
    if passwordless_fallback_allowed and getattr(driver, "_account_passwordless_fallback_active", False) is True:
        password = ""
        allow_password_reset = False
        offered_password_attempted = True
    last_state: dict = {}
    last_url = ""
    last_wait_state = None
    next_wait_log_at = 0.0
    candidate_confirmation_failed = False

    def confirm_candidate_password(receipt=None, *, original=None, budget=None):
        nonlocal candidate_confirmation_failed, password_unknown_receipt
        if on_candidate_password_confirmed is None or saved_password_created:
            return
        receipt = receipt if receipt is not None else getattr(driver, '_browser_submission_receipt', None)
        if original is None and password_unknown_receipt is not receipt:
            original = password_unknown_receipt
        confirmation_budget = execution.StageBudget(end, clock=execution.clock.time)
        if budget is not None:
            confirmation_budget = confirmation_budget.child(budget.remaining())
        try:
            on_candidate_password_confirmed(
                receipt, original=original, budget=confirmation_budget,
            )
        except BaseException:
            candidate_confirmation_failed = True
            raise
        password_unknown_receipt = None

    def reset_password(*, forced: bool = False) -> bool:
        nonlocal password
        if otp_provider is None:
            raise RuntimeError("强制密码修改缺少邮箱验证码提供器" if forced else "密码重置流程缺少邮箱验证码提供器")
        checkpoint = {} if forced and password_recovery is None else {"on_password_submitted": on_password_reset_submitted}
        if password_recovery is not None:
            checkpoint.update(recovery=password_recovery, allow_profile_handoff=True)
        result = execution.reset_password_via_email(
            driver, email, otp_provider,
            stage_reporter=stage_reporter,
            on_password_confirmed=on_password_confirmed,
            totp_secret=totp_secret,
            **checkpoint,
        )
        if isinstance(result, str):
            password = result
        return bool(result)

    def reset_next_state() -> str:
        if allow_profile_handoff or password_recovery is not None:
            if execution.is_password_recovery_profile_page(driver):
                return 'profile_handoff'
            if execution.is_email_verification_page(driver):
                return 'email_otp'
        return 'advanced'

    if password_recovery is not None:
        if execution.password_recovery_pending(password_recovery):
            if reset_password():
                return reset_next_state()

    def confirm_unknown_password_receipt() -> None:
        nonlocal password_unknown_receipt
        if password_unknown_receipt is not None:
            execution.record_browser_submission_fact(
                driver, "confirmed", receipt=password_unknown_receipt, result="success",
            )
            if on_candidate_password_confirmed is not None:
                confirm_candidate_password(password_unknown_receipt)
            password_unknown_receipt = None

    def reject_unknown_password_receipt() -> None:
        nonlocal password_unknown_receipt
        if password_unknown_receipt is not None:
            execution.record_browser_submission_fact(
                driver, "rejected", receipt=password_unknown_receipt,
                result="failure", error_type="PasswordRejectedError",
            )
            password_unknown_receipt = None

    def password_transition_confirmed(state: dict) -> bool:
        return (
            execution.is_email_verification_page(driver)
            or execution.is_totp_login_page(driver, state)
            or execution.is_login_advanced(driver, state)
            or execution.has_access_token(driver)
        )

    def open_initial_saved_password_entry() -> bool:
        nonlocal offered_password_attempted
        if password and not offered_password_attempted and not password_submitted_at:
            offered_password_attempted = True
            return execution.open_offered_saved_password(driver, end)
        return False

    def continue_with_email_after_password_rejection() -> bool:
        nonlocal password, password_submitted_at, offered_password_attempted, allow_password_reset
        if not passwordless_fallback_allowed or saved_password_created:
            return False
        password = ""
        password_submitted_at = 0.0
        offered_password_attempted = True
        allow_password_reset = False
        driver._account_passwordless_fallback_active = True
        driver._registration_password_creation_chain = None
        driver._registration_otp_after_ts = execution.clock.time()
        execution.report_login_stage(stage_reporter, "login", "本地候选密码被明确拒绝，正在使用邮箱验证码继续补密码")
        return True

    while (loop_now := execution.clock.time()) < end:
        # 注册的邮箱验证恢复携带原阶段预算，页面转换不能重新延长它。
        execution.auth_checkpoint()
        state = execution.login_challenge_state(driver)
        last_state = state
        execution.raise_auth_page_error(driver, state, remaining=end - loop_now)
        dead_code = execution.detect_account_unusable_login_state(state)
        if dead_code:
            raise execution.AccountUnusableError(f"账号已废（{dead_code}）", error_code=dead_code)
        if execution.is_browser_error_page_state(state):
            raise RuntimeError(
                "浏览器导航失败："
                f"path={execution.auth_path_for_log(state.get('url'))}"
            )
        if execution.is_terminal_auth_error_page(state):
            raise RuntimeError(
                "OpenAI 认证错误页："
                f"path={execution.auth_path_for_log(state.get('url'))}"
            )
        if allow_profile_handoff and execution.is_password_recovery_profile_page(driver, state):
            if on_candidate_password_confirmed is not None:
                confirm_unknown_password_receipt()
                confirm_candidate_password()
            execution.clear_confirmed_email_submission(driver)
            return 'profile_handoff'
        url = str(state.get("url") or "")
        if url != last_url:
            execution.logger.info("[Codex][Browser] 邮箱提交后登录分支：path=%s", execution.auth_path_for_log(url))
            last_url = url

        page_state = classify(state)
        if roxy_saved_password_entry and saved_password_created and page_state == execution.PageState.PROFILE:
            error = RuntimeError("profile_completion_required: 保存密码已提交，账号仍需沿原注册任务补全资料")
            error.code = "profile_completion_required"
            raise error
        if page_state == execution.PageState.PASSWORD_LOGIN:
            waiting_for = "等待密码提交后的认证结果" if password_submitted_at else "等待密码表单就绪，随后提交一次并等待认证结果"
        elif page_state == execution.PageState.MFA_TOTP:
            waiting_for = "等待 TOTP 提交后的认证结果" if totp_submitted_at else "转入本地 TOTP 验证"
        elif page_state == execution.PageState.OTP_EMAIL:
            waiting_for = "转入邮箱验证码处理"
        elif not state.get("inputs") and not state.get("buttons"):
            waiting_for = "等待前端加载并挂载认证表单"
        else:
            waiting_for = "识别当前认证页面并交给对应处理"
        wait_state = (page_state, waiting_for)
        now = loop_now
        if wait_state != last_wait_state or now >= next_wait_log_at:
            context = execution.current_execution_context()
            remaining = max(0.0, end - now)
            if context is not None and context.remaining() is not None:
                remaining = min(remaining, context.remaining())
            execution.logger.info("[Codex][Browser] 页面状态=%s，%s，剩余预算=%.1f 秒", page_state.value, waiting_for, remaining)
            last_wait_state = wait_state
            next_wait_log_at = now + 15.0

        # Roxy/Chrome occasionally leaves the SPA at /auth/login?email=... after
        # the first submit. Re-submit the same email form once after a short
        # debounce so the normal password/OTP branch can continue.
        inputs = state.get("inputs") or []
        has_email_input = any(
            str(item.get("type") or "").lower() == "email"
            or "email" in str(item.get("autocomplete") or "").lower()
            or str(item.get("name") or "").lower() in {"email", "username"}
            for item in inputs
        )
        has_challenge_input = any(
            str(item.get("type") or "").lower() == "password"
            or any(marker in " ".join(
                str(item.get(key) or "") for key in ("name", "id", "autocomplete", "inputmode")
            ).lower() for marker in ("password", "one-time-code", "otp", "totp", "code"))
            for item in inputs
        )
        # After the email form is submitted, ChatGPT can leave the browser at
        # /auth/login?email=... with *no* mounted inputs at all.  The previous
        # recovery only handled an empty-but-present email input, so this
        # variant waited until the whole challenge budget expired.  Treat the
        # route as a transient auth shell and use the same in-browser NextAuth
        # navigation fallback before deciding that login is broken.
        if execution.email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"} and (
            "/auth/login" in url.lower() and not has_challenge_input
        ):
            # 前端已接手的请求共用当前等待预算，不能由清空输入框触发第二次认证。
            execution.clock.sleep(0.5)
            continue
        blank_login_shell = "/auth/login" in url.lower() and "email=" in url.lower() and not inputs
        if blank_login_shell:
            now = execution.clock.time()
            if not blank_login_shell_seen_at:
                blank_login_shell_seen_at = now
            elif not nextauth_fallback_done and now - blank_login_shell_seen_at >= 1.0:
                fallback = execution.submit_email_via_browser_nextauth(driver, email)
                nextauth_fallback_done = True
                safe_fallback = {
                    key: fallback.get(key)
                    for key in ("ok", "stage", "state")
                    if key in fallback
                }
                execution.logger.warning(
                    "[Codex][Browser] 登录页停留在无控件 login?email 空壳，已启用 NextAuth 兜底：%s",
                    safe_fallback,
                )
                fallback_state = str(fallback.get("state") or "").strip().lower()
                if fallback.get("ok") and fallback_state == "otp":
                    if (roxy_saved_password_entry and on_candidate_password_confirmed is None
                            and open_initial_saved_password_entry()):
                        continue
                    if on_candidate_password_confirmed is not None:
                        confirm_unknown_password_receipt()
                        confirm_candidate_password()
                    return "email_otp"
                if fallback.get("ok") and fallback_state == "advanced":
                    if on_candidate_password_confirmed is not None:
                        confirm_unknown_password_receipt()
                        confirm_candidate_password()
                    return "advanced"
                if fallback.get("ok"):
                    end = max(end, now + 45)
                    execution.human_delay("form")
            execution.clock.sleep(0.5)
            continue
        blank_login_shell_seen_at = 0.0
        if "/auth/login" in url.lower() and has_email_input and not has_challenge_input:
            now = execution.clock.time()
            if not email_shell_seen_at:
                email_shell_seen_at = now
            elif not nextauth_fallback_done and now - email_shell_seen_at >= 2.0:
                # UI 提交可能只更新 URL，不触发真正的 Auth 分支。先使用当前
                # Roxy 会话调用 ChatGPT NextAuth，避免在同一个 SPA 壳里反复等待。
                fallback = execution.submit_email_via_browser_nextauth(driver, email)
                nextauth_fallback_done = True
                safe_fallback = {
                    key: fallback.get(key)
                    for key in ("ok", "stage", "state", "reason")
                    if key in fallback
                }
                execution.logger.warning("[Codex][Browser] 登录页停留在 login?email，已启用 NextAuth 兜底：%s", safe_fallback)
                # NextAuth 导航可能已经落到 OTP 页，但当前 Selenium 句柄的
                # SPA 状态仍短暂保留旧的 login?email 壳。优先消费兜底返回的
                # 稳定状态，避免再次读取旧 DOM 等到总超时。
                fallback_state = str(fallback.get("state") or "").strip().lower()
                if fallback.get("ok") and fallback_state == "otp":
                    if (roxy_saved_password_entry and on_candidate_password_confirmed is None
                            and open_initial_saved_password_entry()):
                        continue
                    if on_candidate_password_confirmed is not None:
                        confirm_unknown_password_receipt()
                        confirm_candidate_password()
                    return "email_otp"
                if fallback.get("ok") and fallback_state == "advanced":
                    if on_candidate_password_confirmed is not None:
                        confirm_unknown_password_receipt()
                        confirm_candidate_password()
                    return "advanced"
                if fallback.get("ok"):
                    end = max(end, now + 45)
                    execution.human_delay("form")
                    continue

            if not email_resubmit_done and nextauth_fallback_done and now - email_shell_seen_at >= 8.0:
                recovery = execution.recover_email_submit_if_stuck(driver, email)
                email_resubmit_done = True
                safe_recovery = {
                    key: recovery.get(key)
                    for key in ("ok", "hasForm", "hasSubmit")
                    if key in recovery
                }
                execution.logger.warning("[Codex][Browser] 邮箱提交后停留在 login?email，已补交邮箱表单：%s", safe_recovery)
                if recovery.get("ok"):
                    end = max(end, now + 45)
                    execution.human_delay("form")
                    continue

        # Roxy can land on the MFA route before React mounts any controls. This
        # is an initial renderer/navigation transition, not evidence that the
        # account has no TOTP challenge. Give it one bounded refresh before
        # declaring the branch unknown; no password or TOTP is repeated here.
        if not password_submitted_at and not totp_submitted_at and not initial_challenge_refresh_done:
            if execution.is_empty_auth_challenge_state(state):
                now = execution.clock.time()
                if not initial_empty_challenge_seen_at:
                    initial_empty_challenge_seen_at = now
                elif now - initial_empty_challenge_seen_at >= 3:
                    initial_challenge_refresh_done = True
                    execution.refresh_auth_challenge_after_submit(driver, "初始认证挑战")
                    end = max(end, execution.clock.time() + 25)
                    continue
            else:
                initial_empty_challenge_seen_at = 0.0

        # TOTP may be rendered in-place while the stale URL still ends in
        # /log-in/password, so inspect the live controls before trusting the URL.
        if execution.is_totp_login_page(driver, state):
            if on_candidate_password_confirmed is not None:
                confirm_unknown_password_receipt()
                confirm_candidate_password()
            execution.clear_confirmed_email_submission(driver)
            if totp_submitted_at:
                if state.get("errors") or any(
                    str(item.get("ariaInvalid") or "").lower() == "true" for item in (state.get("inputs") or [])
                ):
                    raise RuntimeError(f"本地 TOTP 未通过页面校验：errors={(state.get('errors') or [])[:3]}")
                if execution.clock.time() - totp_submitted_at > 20:
                    raise RuntimeError("提交本地 TOTP 后页面 20 秒未继续，已在手机号验证前停止")
                context = execution.current_execution_context()
                if context is not None and context.budget is not None:
                    context.budget.sleep(0.5, sleeper=execution.clock.sleep)
                else:
                    execution.clock.sleep(0.5)
                continue
            execution.auth_checkpoint()
            execution.submit_saved_login_totp(driver, email, totp_secret)
            totp_submitted_at = execution.clock.time()
            end = max(end, totp_submitted_at + 25)
            context = execution.current_execution_context()
            if context is not None and context.budget is not None:
                execution.human_delay("form", budget=context.budget)
            else:
                execution.human_delay("form")
            continue

        # After a valid TOTP submit, OpenAI can briefly leave the browser on
        # the same MFA challenge with all controls unmounted. Treat that as a
        # renderer/navigation transition and refresh once; never resend TOTP.
        if (
            totp_submitted_at
            and not totp_refresh_done
            and execution.is_empty_auth_challenge_state(state)
            and execution.clock.time() - totp_submitted_at >= 3
        ):
            totp_refresh_done = True
            execution.refresh_auth_challenge_after_submit(driver, "TOTP")
            end = max(end, execution.clock.time() + 25)
            continue

        saved_password_create_page = (
            bool(password) and execution.is_saved_create_password_page(driver, state)
        )
        if execution.is_login_password_page(driver) or saved_password_create_page:
            execution.clear_confirmed_email_submission(driver)
            if force_password_reset and not saved_password_create_page:
                if reset_password(forced=True):
                    return reset_next_state()
                raise RuntimeError("登录密码页没有找到忘记密码入口")
            if password_submitted_at:
                if execution.is_explicit_password_rejection_state(state):
                    if continue_with_email_after_password_rejection():
                        continue
                    if allow_password_reset and not saved_password_create_page and reset_password():
                        return reset_next_state()
                    raise execution.PasswordRejectedError(
                        "远端明确拒绝本地保存的账号密码；已停止重复提交"
                    )
                if state.get("errors") or any(
                    str(item.get("ariaInvalid") or "").lower() == "true" for item in (state.get("inputs") or [])
                ):
                    raise RuntimeError(f"本地保存的注册密码未通过页面校验：errors={(state.get('errors') or [])[:3]}")
                execution.clock.sleep(0.5)
                continue
            if password:
                previous_password_receipts = execution.password_receipt_ids(driver)
                saved_password_created = saved_password_create_page
                try:
                    execution.submit_saved_login_password(
                        driver, email, password,
                        **({'on_candidate_password_confirmed': confirm_candidate_password}
                           if on_candidate_password_confirmed is not None and not saved_password_create_page else {}),
                    )
                except execution.PasswordRejectedError:
                    if continue_with_email_after_password_rejection():
                        continue
                    if allow_password_reset and not saved_password_create_page and reset_password():
                        return reset_next_state()
                    raise
                except execution.PasswordTransitionTimeout as exc:
                    # 创建密码只确认本次接收，不借用登录恢复的重试/重置语义。
                    if saved_password_create_page:
                        raise
                    if candidate_confirmation_failed:
                        raise
                    if password_unknown_retry_done:
                        raise
                    password_unknown_receipt = getattr(driver, "_browser_submission_receipt", None)
                    retry_state = execution.login_challenge_state(driver)
                    execution.raise_auth_page_error(driver, retry_state, remaining=end - execution.clock.time())
                    if execution.is_explicit_password_rejection_state(retry_state):
                        reject_unknown_password_receipt()
                        if continue_with_email_after_password_rejection():
                            continue
                        if allow_password_reset and reset_password():
                            return reset_next_state()
                        raise execution.PasswordRejectedError(
                            "远端明确拒绝本地保存的账号密码；已停止重复提交"
                        ) from exc
                    has_validation_error = bool(retry_state.get("errors")) or any(
                        str(item.get("ariaInvalid") or "").lower() == "true"
                        for item in (retry_state.get("inputs") or [])
                    )
                    if has_validation_error:
                        raise
                    if not execution.is_login_password_page(driver):
                        if not password_transition_confirmed(retry_state):
                            raise
                        confirm_unknown_password_receipt()
                        password_submitted_at = execution.clock.time()
                        end = max(end, password_submitted_at + 25)
                        continue

                    execution.refresh_auth_challenge_after_submit(driver, "登录密码")
                    retry_state = execution.login_challenge_state(driver)
                    execution.raise_auth_page_error(driver, retry_state, remaining=end - execution.clock.time())
                    if execution.is_explicit_password_rejection_state(retry_state):
                        reject_unknown_password_receipt()
                        if continue_with_email_after_password_rejection():
                            continue
                        if allow_password_reset and reset_password():
                            return reset_next_state()
                        raise execution.PasswordRejectedError(
                            "远端明确拒绝本地保存的账号密码；已停止重复提交"
                        ) from exc
                    has_validation_error = bool(retry_state.get("errors")) or any(
                        str(item.get("ariaInvalid") or "").lower() == "true"
                        for item in (retry_state.get("inputs") or [])
                    )
                    if has_validation_error:
                        raise
                    if not execution.is_login_password_page(driver):
                        if not password_transition_confirmed(retry_state):
                            raise
                        confirm_unknown_password_receipt()
                        password_submitted_at = execution.clock.time()
                        end = max(end, password_submitted_at + 25)
                        continue

                    password_unknown_retry_done = True
                    end = max(end, execution.clock.time() + 25)
                    execution.logger.warning(
                        "[Codex][Browser] 密码提交结果未知，刷新后仍停留在无错误密码页，允许重试一次"
                    )
                    continue
                finally:
                    if roxy_saved_password_entry:
                        evidence = execution.password_evidence(driver, exclude_ids=previous_password_receipts)
                        password_stage_result = {
                            "verified": ("success", "账号密码验证通过"),
                            "accepted": ("success", "账号密码设置已被接受"),
                            "rejected": ("failed", "远端拒绝本次账号密码提交"),
                            "unknown": ("failed", "本次密码提交结果未确认"),
                        }.get(evidence["credential_check"])
                        if password_stage_result is not None:
                            password_stage_state, password_stage_message = password_stage_result
                            execution.report_login_stage(
                                stage_reporter, "login_password", password_stage_message,
                                state=password_stage_state,
                                detail={"auth_facts": evidence},
                            )
                confirm_unknown_password_receipt()
                password_submitted_at = execution.clock.time()
                # 密码提交和转换已由共享能力确认，保留后续 OTP/TOTP 分支的处理时间。
                end = max(end, password_submitted_at + 25)
                execution.human_delay("form")
                continue
            if not passwordless_clicked and passwordless_clicks < 2:
                if allow_password_reset:
                    if reset_password():
                        return reset_next_state()
                if not passwordless_wait_started:
                    passwordless_wait_started = execution.clock.monotonic()
                result = execution.click_passwordless_signup_if_present(driver)
                passwordless_last_result = result
                if result.get("ok"):
                    passwordless_clicks += 1
                    passwordless_clicked = not bool(result.get("followup"))
                    execution.logger.info("[Codex][Browser] 已选择页面提供的邮箱一次性验证码入口：email=%s", email)
                    execution.human_delay("form")
                    continue
                # Password input and the alternate email-code action are
                # hydrated independently. Give the password page a bounded
                # observation window instead of failing on the first scan.
                if (
                    execution.clock.monotonic() - passwordless_wait_started < 10
                    and execution.clock.time() < end - 0.5
                ):
                    execution.clock.sleep(0.5)
                    continue
                # The old browser flow had one more recovery opportunity here:
                # after landing on auth.openai.com/log-in/password, reopen the
                # ChatGPT login shell and let the existing in-browser NextAuth
                # fallback create a fresh authorization branch. This matters
                # for accounts whose passwordless action is not rendered in
                # the first auth-page variant.
                if not nextauth_fallback_done:
                    nextauth_fallback_done = True
                    try:
                        execution.safe_get(
                            driver,
                            "https://chatgpt.com/auth/login",
                            timeout=30,
                            attempts=2,
                            accept_hosts=("chatgpt.com", "auth.openai.com"),
                        )
                        fallback = execution.submit_email_via_browser_nextauth(driver, email)
                        safe_fallback = {
                            key: fallback.get(key)
                            for key in ("ok", "stage", "state", "reason")
                            if key in fallback
                        }
                        execution.logger.warning(
                            "[Codex][Browser] 密码页未找到无密码入口，已执行一次 NextAuth 重新授权兜底：%s",
                            safe_fallback,
                        )
                        fallback_state = str(fallback.get("state") or "").strip().lower()
                        if fallback.get("ok") and fallback_state == "otp":
                            return "email_otp"
                        if fallback.get("ok") and fallback_state == "advanced":
                            return "advanced"
                        if fallback.get("ok"):
                            passwordless_wait_started = 0.0
                            end = max(end, execution.clock.time() + 45)
                            execution.human_delay("form")
                            continue
                        passwordless_last_result = fallback
                    except Exception as exc:
                        passwordless_last_result = {
                            "ok": False,
                            "reason": f"nextauth_fallback:{type(exc).__name__}: {str(exc)[:160]}",
                        }
            raise RuntimeError(
                "账号进入登录密码页，本地无注册密码且页面无邮箱验证码入口，已在手机号验证前停止："
                f"detail={passwordless_last_result}"
            )

        if execution.is_email_verification_page(driver):
            if open_initial_saved_password_entry():
                continue
            if on_candidate_password_confirmed is not None:
                confirm_unknown_password_receipt()
                confirm_candidate_password()
            execution.clear_confirmed_email_submission(driver)
            execution.logger.info("[Codex][Browser] 页面明确进入邮箱验证码分支：email=%s", email)
            return "email_otp"
        if execution.is_login_advanced(driver, state):
            if on_candidate_password_confirmed is not None:
                confirm_unknown_password_receipt()
                confirm_candidate_password()
            execution.clear_confirmed_email_submission(driver)
            return "advanced"
        execution.clock.sleep(0.5)

    if execution.email_ui_submission_state(driver) in {"queued", "dispatched", "unknown"}:
        raise execution.EmailSubmissionUnknown("request_unknown: 邮箱提交结果在认证预算内未确认，未重复发送")
    safe_state = {
        "url": last_state.get("url"),
        "inputs": last_state.get("inputs"),
        "errors": (last_state.get("errors") or [])[:3],
    }
    raise RuntimeError(f"邮箱提交后未识别到密码、TOTP 或邮箱验证码分支：state={safe_state}")


def _maybe_click_passwordless_after_email(execution: BrowserExecutionContext, driver, email: str, timeout: int = 18) -> None:
    """
    Codex OAuth 提交邮箱后也可能跳到 /log-in/password 或 /create-account/password。
    优先点击“使用一次性验证码/one-time code”入口，进入邮箱验证码页。
    """
    end = execution.clock.time() + timeout
    last_url = ""
    clicked = False
    while execution.clock.time() < end:
        try:
            if execution.is_email_verification_page(driver):
                if clicked:
                    execution.logger.info("[Codex][Browser] 一次性验证码入口已进入邮箱验证码页")
                return
            url = str(driver.current_url or "")
            if url != last_url:
                execution.logger.info("[Codex][Browser] 提交邮箱后检测密码/OTP 跳转：path=%s", execution.auth_path_for_log(url))
                last_url = url
            lower = url.lower()
            if any(x in lower for x in ("phone", "workspace", "consent", "authorize", "localhost:1455")):
                return
            if "/password" in lower or "auth.openai.com" in lower:
                result = execution.click_passwordless_signup_if_present(driver)
                if result.get("ok"):
                    clicked = True
                    execution.logger.info("[Codex][Browser] 已点击一次性验证码入口")
                    execution.human_delay("form")
                    continue
        except Exception as exc:
            execution.logger.debug("[Codex][Browser] 密码页一次性验证码入口探测失败：%s", type(exc).__name__)
        execution.clock.sleep(0.5)
    if clicked:
        execution.logger.info("[Codex][Browser] 已点击一次性验证码入口，未立即检测到 OTP 页，继续后续 OTP 轮询")


def _wait_for_otp_input(execution: BrowserExecutionContext, driver, timeout: int = 30) -> None:
    """验证码已收到但 OTP 输入框可能尚未出现（点完一次性验证码后常有中间页/延迟渲染）。

    等待期间若仍停留在登录密码页，则补点一次性验证码入口（最多 2 次、间隔 6s）；
    超时仍未出现时打印页面状态便于定位。
    """
    end = execution.clock.time() + timeout
    passwordless_retries = 0
    while execution.clock.time() < end:
        if execution.is_email_verification_page(driver):
            return
        if execution.is_login_password_page(driver) and passwordless_retries < 2:
            passwordless_retries += 1
            result = execution.click_passwordless_signup_if_present(driver)
            if result.get("ok"):
                execution.logger.info("[Codex][Browser] 仍停留登录密码页，补点一次性验证码入口：%s", result.get("reason"))
                execution.human_delay("form")
            execution.clock.sleep(6)
            continue
        execution.clock.sleep(0.8)
    state = execution.email_otp_page_state(driver)
    execution.logger.warning(
        "[Codex][Browser] 等待 OTP 输入框超时，页面 url=%s inputs=%s buttons=%s 文本前300字=%s",
        str(state.get("url") or ""),
        len(state.get("inputs") or []),
        [(b.get("text") or "")[:24] for b in (state.get("buttons") or [])][:8],
        str(state.get("text") or "")[:300],
    )
    raise RuntimeError("等待 OTP 输入框超时，页面未出现验证码输入框")


def _select_existing_account_if_present(execution: BrowserExecutionContext, driver, email: str) -> bool:
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
            execution.logger.info("[Codex][Browser] 已选择当前登录账号，继续 OAuth（可见操作数=%s）", result.get("actionCount"))
            return True
    except Exception as exc:
        execution.logger.debug("[Codex][Browser] 当前账号选择探测失败：%s", type(exc).__name__)
    return False


def _wait_for_fresh_email_otp(execution: BrowserExecutionContext, otp_provider, email: str, after_ts: float, used_codes: set[str] | None = None, timeout: int = 90) -> str:
    """获取一个未提交过的邮箱 OTP。

    通用 API 邮箱的取码接口有时会先返回缓存旧码；验证码错误后重发时，
    这里会拒绝复用已失败的 code，持续轮询直到出现新 code 或超时。
    """
    used_codes = {str(x) for x in (used_codes or set()) if x}
    end = execution.clock.time() + timeout
    last_code = ""
    while True:
        execution.check_cancelled()
        remaining = max(1, int(end - execution.clock.time()))
        kwargs = {"after_ts": after_ts}
        try:
            params = inspect.signature(otp_provider).parameters.values()
            if any(p.name == "max_wait" or p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
                kwargs["max_wait"] = remaining
        except (TypeError, ValueError):
            pass
        code = str(execution.call_cancellable(execution.bind_auth_observer(otp_provider), email, **kwargs) or "").strip()
        if code and code not in used_codes:
            return code
        last_code = code or last_code
        remaining = int(end - execution.clock.time())
        if remaining <= 0:
            raise RuntimeError("等待新的邮箱验证码超时，取码接口仍返回已失败验证码")
        execution.logger.warning(
            "[Codex][Browser] 取码接口仍返回已提交过的旧 OTP，继续等待最新验证码（剩余 %ss）",
            remaining,
        )
        execution.clock.sleep(min(5, max(1, remaining)))


def _install_email_otp_validate_hook(execution: BrowserExecutionContext, driver, *, capture_responses: bool = True) -> None:
    """
    在页面内 hook fetch/XHR，捕获 email-otp/validate 的接口响应体。

    指纹浏览器不能像纯协议模式一样直接拿 requests.Response，因此在提交邮箱 OTP 前
    注入此 hook，后续只读取接口 JSON error.code，不靠页面文字判断废号。
    """
    script = r"""
    (() => {
      window.__codexEmailOtpValidateResponses = [];
      window.__codexEmailOtpValidateCaptureResponses = arguments[0] !== false;
      window.__codexEmailOtpValidateRequestCount = Number(window.__codexEmailOtpValidateRequestCount || 0);
      if (window.__codexEmailOtpValidateHooked) return true;
      window.__codexEmailOtpValidateHooked = true;
      const hit = (url) => String(url || '').includes('/api/accounts/email-otp/validate');
      const markRequest = url => {
        if (hit(url)) window.__codexEmailOtpValidateRequestCount += 1;
      };
      const save = (url, status, body) => {
        try {
          if (!hit(url) || !window.__codexEmailOtpValidateCaptureResponses) return;
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
          const url = (typeof input === 'string') ? input : (input && (input.url || input.href));
          markRequest(url);
          const resp = await origFetch.apply(this, arguments);
          try {
            if (hit(url) && window.__codexEmailOtpValidateCaptureResponses) {
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
          markRequest(this.__codexOtpValidateUrl);
          this.addEventListener('loadend', function() {
            try {
              if (hit(this.__codexOtpValidateUrl) && window.__codexEmailOtpValidateCaptureResponses)
                save(this.__codexOtpValidateUrl, this.status, this.responseText);
            } catch (e) {}
          });
        } catch (e) {}
        return origSend.apply(this, arguments);
      };
      window.__codexEmailOtpValidateRequestCounterInstalled = true;
      return true;
    })();
    """
    try:
        driver.execute_script(script, capture_responses)
    except Exception as exc:
        execution.logger.debug("[Codex][Browser] 注入 email-otp/validate 响应 hook 失败：%s", type(exc).__name__)


def _read_email_otp_validate_dead_code(execution: BrowserExecutionContext, driver) -> str:
    try:
        rows = driver.execute_script("return window.__codexEmailOtpValidateResponses || [];") or []
    except Exception:
        return ""
    if not isinstance(rows, list):
        return ""
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        code = execution.detect_account_unusable_response_body(str(row.get("body") or ""))
        if code:
            execution.logger.warning(
                "[Codex][Browser] email-otp/validate 响应识别账号已废：code=%s status=%s",
                code,
                row.get("status"),
            )
            return code
    return ""


def _finish_consent_workspace(execution: BrowserExecutionContext, driver, email: str = "", *, phone_enabled: bool | None = None) -> str:
    """点击 Codex consent/workspace 页面里的继续/允许按钮，直到 callback。

    手机验证页可能在最初 8 秒探测窗口之后才出现。Callback 循环必须持续识别
    add-phone/phone-verification，不能在该页面空等到 180 秒超时。
    """
    end = execution.clock.time() + int(execution.load_callback_timeout())
    consent_retry_attempts = 0
    max_consent_retry_attempts = 3
    while execution.clock.time() < end:
        execution.check_cancelled()
        callback = execution.extract_callback_url_from_any_window(driver)
        if callback:
            return callback
        current = str(driver.current_url or "")
        if execution.has_strict_add_phone_form(driver) or execution.is_phone_code_page(driver):
            execution.logger.info(
                "[Codex][Browser] Callback 等待期间检测到延迟出现的手机号验证页，立即处理：path=%s",
                execution.auth_path_for_log(current),
            )
            execution.do_phone_verification_if_present(driver, phone_enabled=phone_enabled)
            continue
        if consent_retry_attempts < max_consent_retry_attempts and execution.click_consent_retry_button(driver):
            consent_retry_attempts += 1
            execution.logger.warning(
                "[Codex][Browser] consent 页面数据加载失败，点击 Try again 重试：%s/%s",
                consent_retry_attempts,
                max_consent_retry_attempts,
            )
            execution.human_delay("form")
            continue
        clicked = False
        if email and execution.select_existing_account_if_present(driver, email):
            clicked = True
            execution.human_delay("form")
        for selectors in [
            ["//button[contains(., 'Allow')]", "//button[contains(., 'Authorize')]", "//button[contains(., 'Continue')]"],
            ["//button[contains(., 'Select')]", "//button[contains(., 'Use workspace')]", "//button[contains(., 'Confirm')]"],
            ["//button[contains(., '允许')]", "//button[contains(., '授权')]", "//button[contains(., '继续')]", "//button[contains(., '确认')]"],
            ["button[type='submit']"],
        ]:
            if not clicked and execution.click_if_present(driver, selectors, timeout=2):
                clicked = True
                execution.human_delay("form")
                break
        if not clicked:
            execution.cancellable_sleep(0.8)
    return execution.wait_for_callback(driver, timeout=5)
