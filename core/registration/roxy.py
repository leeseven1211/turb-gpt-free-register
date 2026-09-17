# -*- coding: utf-8 -*-
"""通过 RoxyBrowser 指纹浏览器 + Selenium 执行 ChatGPT 注册。"""
from __future__ import annotations

import logging
import json
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
from core.registration.auth_context import AuthExecutionContext
from core.auth_challenge import (
    MfaSecretMissingError,
    PasswordRejectedError,
    PasswordSetupNotReadyError,
    RemoteExistingAccountError,
    auth_result_for_registration,
    classify_registration_identity,
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

_REGISTRATION_REQUEST_UNKNOWN_MARKERS = (
    "邮箱提交后未识别到",
    "邮箱提交/认证跳转超过总预算",
    "注册页状态未知",
    "后续页面类型未知",
    "认证跳转结果未知",
)

_PASSWORD_ENTRY_FAILURE_MARKERS = (
    "password_entry_page_not_hydrated",
    "password_entry_not_offered",
    "password_entry_recovery_exhausted",
)


class _OtpAttemptTracker:
    """Prevent one registration run from submitting the same OTP twice."""

    def __init__(self) -> None:
        self._submitted: set[str] = set()

    def accept(self, code: object) -> bool:
        normalized = str(code or "").strip()
        if not normalized or normalized in self._submitted:
            return False
        self._submitted.add(normalized)
        return True


def _is_registration_request_unknown(error_text: object) -> bool:
    """Recognize an observed-but-unclassified remote registration state."""
    text = str(error_text or "")
    return any(marker in text for marker in _REGISTRATION_REQUEST_UNKNOWN_MARKERS)


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
    # 密码入口阶段已在 OpenAI 侧推进过注册身份。即使页面仍是空壳，也要保留
    # Profile/cookie 给同一 Attempt 继续恢复，不能按普通首屏空壳回收。
    if any(marker in normalized for marker in _PASSWORD_ENTRY_FAILURE_MARKERS):
        return False
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



from core.registration import auth_capabilities as _auth_capabilities


def _shared_compat_overrides() -> dict[str, object]:
    """收集当前 Roxy 模块被旧测试/集成显式覆盖的绑定。"""
    overrides: dict[str, object] = {}
    for name in _auth_capabilities._COMPAT_BINDING_NAMES:
        candidate = globals().get(name)
        if candidate is None or getattr(candidate, "__roxy_shared_wrapper__", False):
            continue
        overrides[name] = candidate
    return overrides


def _call_shared_capability(name: str, *args, **kwargs):
    """调用共享能力；兼容覆盖是单次、显式且线程隔离的。"""
    overrides = _shared_compat_overrides()
    if kwargs.get("context") is None:
        try:
            from core.registration_service import StopRequested, is_stop_requested

            kwargs["context"] = AuthExecutionContext(
                cancellation=lambda: bool(is_stop_requested()),
                budget=kwargs.get("budget") if isinstance(kwargs.get("budget"), StageBudget) else None,
                cancellation_error=lambda: StopRequested("认证能力收到注册任务停止请求"),
            )
        except (ImportError, AttributeError):
            # Keep direct/unit capability calls usable when the registration
            # service is intentionally not loaded.  The service-facing path
            # supplies the concrete cancellation exception above.
            pass
    # The shared MFA/registration challenge capability accepts callbacks; it
    # must not import this OAuth orchestrator just to preserve the historical
    # Roxy monkeypatch points.  Resolve those adapters only on the old Roxy
    # path and inject them into the same ContextVar override scope.
    if name in {
        "_complete_registration_totp_after_email_otp",
        "_complete_settings_email_reauth",
    }:
        try:
            from core import roxy_codex_oauth as _oauth

            for callback_name in (
                "complete_openai_login_challenge",
                "_is_totp_login_page",
                "_submit_saved_login_totp",
            ):
                callback = getattr(_oauth, callback_name, None)
                if callable(callback):
                    overrides[callback_name] = callback
        except Exception:
            # A direct registration flow may not have loaded the OAuth module;
            # the capability will report a missing injected resolver only if
            # it actually reaches a chained challenge.
            pass
    return _auth_capabilities.call_with_compatibility(
        name,
        overrides,
        *args,
        **kwargs,
    )


def _make_shared_compatibility_wrapper(name: str):
    def wrapper(*args, **kwargs):
        return _call_shared_capability(name, *args, **kwargs)

    wrapper.__name__ = name
    wrapper.__qualname__ = name
    wrapper.__module__ = __name__
    wrapper.__roxy_shared_wrapper__ = True
    wrapper.__shared_capability__ = True
    return wrapper


_log_prefix = _make_shared_compatibility_wrapper("_log_prefix")
_build_driver = _make_shared_compatibility_wrapper("_build_driver")
_center_browser_window = _make_shared_compatibility_wrapper("_center_browser_window")
_wait = _make_shared_compatibility_wrapper("_wait")
_budget_timeout = _make_shared_compatibility_wrapper("_budget_timeout")
_roxy_page_state = _make_shared_compatibility_wrapper("_roxy_page_state")
_auth_terminal_page_state = _make_shared_compatibility_wrapper("_auth_terminal_page_state")
_safe_get = _make_shared_compatibility_wrapper("_safe_get")
_visible = _make_shared_compatibility_wrapper("_visible")
_browser_actions_enabled = _make_shared_compatibility_wrapper("_browser_actions_enabled")
_apply_browser_automation_mask = _make_shared_compatibility_wrapper("_apply_browser_automation_mask")
_human_scroll_to = _make_shared_compatibility_wrapper("_human_scroll_to")
_human_click = _make_shared_compatibility_wrapper("_human_click")
_human_type_text = _make_shared_compatibility_wrapper("_human_type_text")
_page_warmup = _make_shared_compatibility_wrapper("_page_warmup")
_refresh_chatgpt_settings_shell_if_needed = _make_shared_compatibility_wrapper("_refresh_chatgpt_settings_shell_if_needed")
_settings_page_not_ready = _make_shared_compatibility_wrapper("_settings_page_not_ready")
_find_any = _make_shared_compatibility_wrapper("_find_any")
_click_any = _make_shared_compatibility_wrapper("_click_any")
_type_any = _make_shared_compatibility_wrapper("_type_any")
_email_entry_state = _make_shared_compatibility_wrapper("_email_entry_state")
_find_visible_email_input_js = _make_shared_compatibility_wrapper("_find_visible_email_input_js")
_is_oauth_consent_like = _make_shared_compatibility_wrapper("_is_oauth_consent_like")
_is_external_idp_url = _make_shared_compatibility_wrapper("_is_external_idp_url")
_assert_not_external_idp = _make_shared_compatibility_wrapper("_assert_not_external_idp")
_click_email_entry_option = _make_shared_compatibility_wrapper("_click_email_entry_option")
_is_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_is_blank_chatgpt_auth_shell")
_reload_blank_chatgpt_auth_shell = _make_shared_compatibility_wrapper("_reload_blank_chatgpt_auth_shell")
_email_submit_advanced_state = _make_shared_compatibility_wrapper("_email_submit_advanced_state")
_type_email_address = _make_shared_compatibility_wrapper("_type_email_address")
_submit_nearest_form_for_active_input = _make_shared_compatibility_wrapper("_submit_nearest_form_for_active_input")
_current_email_input_value = _make_shared_compatibility_wrapper("_current_email_input_value")
_stabilize_email_input_before_submit = _make_shared_compatibility_wrapper("_stabilize_email_input_before_submit")
_submit_email_form_stable = _make_shared_compatibility_wrapper("_submit_email_form_stable")
_submit_email_step = _make_shared_compatibility_wrapper("_submit_email_step")
_recover_email_submit_if_stuck = _make_shared_compatibility_wrapper("_recover_email_submit_if_stuck")
_submit_email_via_browser_nextauth = _make_shared_compatibility_wrapper("_submit_email_via_browser_nextauth")
_email_input_value_state = _make_shared_compatibility_wrapper("_email_input_value_state")
_is_email_login_page_still_present = _make_shared_compatibility_wrapper("_is_email_login_page_still_present")
_diagnostic_url = _make_shared_compatibility_wrapper("_diagnostic_url")
_redact_diagnostic_text = _make_shared_compatibility_wrapper("_redact_diagnostic_text")
_log_blank_auth_shell_diagnostics = _make_shared_compatibility_wrapper("_log_blank_auth_shell_diagnostics")
_wait_email_submit_next_state = _make_shared_compatibility_wrapper("_wait_email_submit_next_state")
_submit_email_and_wait_next = _make_shared_compatibility_wrapper("_submit_email_and_wait_next")
_type_otp = _make_shared_compatibility_wrapper("_type_otp")
_email_otp_page_state = _make_shared_compatibility_wrapper("_email_otp_page_state")
_is_email_verification_page = _make_shared_compatibility_wrapper("_is_email_verification_page")
_clear_otp_inputs = _make_shared_compatibility_wrapper("_clear_otp_inputs")
_click_resend_email_otp = _make_shared_compatibility_wrapper("_click_resend_email_otp")
_resend_email_otp_after_failure = _make_shared_compatibility_wrapper("_resend_email_otp_after_failure")
_classify_otp_wait_failure = _make_shared_compatibility_wrapper("_classify_otp_wait_failure")
_complete_registration_totp_after_email_otp = _make_shared_compatibility_wrapper("_complete_registration_totp_after_email_otp")
_wait_after_email_otp_submit = _make_shared_compatibility_wrapper("_wait_after_email_otp_submit")
_click_continue = _make_shared_compatibility_wrapper("_click_continue")
_maybe_accept = _make_shared_compatibility_wrapper("_maybe_accept")
_page_snapshot = _make_shared_compatibility_wrapper("_page_snapshot")
_has_access_token = _make_shared_compatibility_wrapper("_has_access_token")
_is_profile_like = _make_shared_compatibility_wrapper("_is_profile_like")
_set_element_value = _make_shared_compatibility_wrapper("_set_element_value")
_select_or_type = _make_shared_compatibility_wrapper("_select_or_type")
_fill_birthday_or_age = _make_shared_compatibility_wrapper("_fill_birthday_or_age")
_generate_roxy_password = _make_shared_compatibility_wrapper("_generate_roxy_password")
_registration_password = _make_shared_compatibility_wrapper("_registration_password")
_registration_auth_mode = _make_shared_compatibility_wrapper("_registration_auth_mode")
_password_transition_timeout_seconds = _make_shared_compatibility_wrapper("_password_transition_timeout_seconds")
_password_page_state = _make_shared_compatibility_wrapper("_password_page_state")
_is_signup_password_page = _make_shared_compatibility_wrapper("_is_signup_password_page")
_is_login_password_page = _make_shared_compatibility_wrapper("_is_login_password_page")
_click_passwordless_signup_if_present = _make_shared_compatibility_wrapper("_click_passwordless_signup_if_present")
_click_signup_password_from_otp_if_present = _make_shared_compatibility_wrapper("_click_signup_password_from_otp_if_present")
_fill_password_page_if_present = _make_shared_compatibility_wrapper("_fill_password_page_if_present")
_accept_profile_consents = _make_shared_compatibility_wrapper("_accept_profile_consents")
_complete_profile_page = _make_shared_compatibility_wrapper("_complete_profile_page")
_click_if_enabled_submit = _make_shared_compatibility_wrapper("_click_if_enabled_submit")
_read_chatgpt_session_once = _make_shared_compatibility_wrapper("_read_chatgpt_session_once")
_switch_to_chatgpt_window_if_any = _make_shared_compatibility_wrapper("_switch_to_chatgpt_window_if_any")
_fetch_chatgpt_session = _make_shared_compatibility_wrapper("_fetch_chatgpt_session")
_check_manual_stop = _make_shared_compatibility_wrapper("_check_manual_stop")
_probe_chatgpt_password_eligibility = _make_shared_compatibility_wrapper("_probe_chatgpt_password_eligibility")
_totp_secret_candidate = _make_shared_compatibility_wrapper("_totp_secret_candidate")
_first_visible_css = _make_shared_compatibility_wrapper("_first_visible_css")
_is_stale_element_error = _make_shared_compatibility_wrapper("_is_stale_element_error")
_visible_new_password_inputs = _make_shared_compatibility_wrapper("_visible_new_password_inputs")
_wait_visible_css = _make_shared_compatibility_wrapper("_wait_visible_css")
_detect_mfa_enrollment_step = _make_shared_compatibility_wrapper("_detect_mfa_enrollment_step")
_wait_mfa_enrollment_step = _make_shared_compatibility_wrapper("_wait_mfa_enrollment_step")
_wait_after_mfa_email_submit = _make_shared_compatibility_wrapper("_wait_after_mfa_email_submit")
_dismiss_single_action_dialog = _make_shared_compatibility_wrapper("_dismiss_single_action_dialog")
_dismiss_chatgpt_pricing_modal = _make_shared_compatibility_wrapper("_dismiss_chatgpt_pricing_modal")
_click_chatgpt_settings_control = _make_shared_compatibility_wrapper("_click_chatgpt_settings_control")
_reveal_chatgpt_settings_navigation = _make_shared_compatibility_wrapper("_reveal_chatgpt_settings_navigation")
_click_password_setting_fallback = _make_shared_compatibility_wrapper("_click_password_setting_fallback")
_open_chatgpt_security_settings = _make_shared_compatibility_wrapper("_open_chatgpt_security_settings")
_disable_roxy_2fa = _make_shared_compatibility_wrapper("_disable_roxy_2fa")
_complete_settings_email_reauth = _make_shared_compatibility_wrapper("_complete_settings_email_reauth")
set_roxy_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
_button_after_input = _make_shared_compatibility_wrapper("_button_after_input")
_read_totp_secret_from_dialog = _make_shared_compatibility_wrapper("_read_totp_secret_from_dialog")
_manual_totp_secret = _make_shared_compatibility_wrapper("_manual_totp_secret")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")
set_login_password = _make_shared_compatibility_wrapper("set_roxy_login_password")
setup_roxy_2fa = _make_shared_compatibility_wrapper("setup_roxy_2fa")
setup_protocol_2fa_with_browser_fallback = _make_shared_compatibility_wrapper("setup_protocol_2fa_with_browser_fallback")

# Constants/classes retained for old tests and integrations.  They are values
# from the shared responsibility modules, not implementations copied back into
# this compatibility surface.
_PasswordTransitionTimeout = _auth_capabilities._PasswordTransitionTimeout
_CHATGPT_HOME_URL = _auth_capabilities._mfa_auth._CHATGPT_HOME_URL
_CHATGPT_SECURITY_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_SECURITY_SETTINGS_URL
_CHATGPT_PASSWORD_SETTINGS_URL = _auth_capabilities._mfa_auth._CHATGPT_PASSWORD_SETTINGS_URL
_MFA_EMAIL_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_EMAIL_CODE_SELECTOR
_MFA_TOTP_CODE_SELECTOR = _auth_capabilities._mfa_auth._MFA_TOTP_CODE_SELECTOR

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


def _open_roxy_profile_with_capacity_wait(
    client,
    proxy_url: str | None,
    *,
    profile_id: str | None = None,
    progress_callback=None,
) -> RoxyOpenResult:
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
                debug_session = current_session()
                # failure_only 只在最终失败时保存现场，不需要为了采集而
                # 显示浏览器窗口；只有显式全量调试才强制可见。这样普通
                # 诊断和线程池遗留的 failure_only 会话都不会覆盖无头配置。
                if getattr(debug_session, "capture_mode", "") == "full":
                    debug_headless = False
            except Exception:
                pass
            open_kwargs = {"proxy_url": proxy_url}
            if debug_headless is not None:
                open_kwargs["headless"] = debug_headless
            if profile_id is None:
                opened = client.open_profile(**open_kwargs)
            else:
                opened = client.open_profile_for_account(
                    profile_id=profile_id,
                    **open_kwargs,
                )
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
        "roxybrowser": {
            "profile_id": opened.profile_id,
            "open_result": opened.raw,
            "retained": True,
        },
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
    account_id = insert_account(
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
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


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

    account_id = insert_account(
        email=email,
        access_token="",
        proxy_used=proxy or None,
        email_source=resolve_email_source(email),
        extra={
            "account_password": openai_password,
            "registration_checkpoint": "email_verification_pending",
            "registration_pending_reason": "email_otp_pending",
            "roxybrowser": {
                "profile_id": opened.profile_id,
                "open_result": opened.raw,
                "retained": True,
            },
        },
    )
    opened.account_bound = True
    RoxyBrowserClient.mark_profile_bound(opened.profile_id)
    return account_id


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
    profile_id: str | None = None,
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

    report_job_progress("browser", "running", "正在打开或创建 Roxy 浏览器环境")
    client = RoxyBrowserClient()
    opened = _open_roxy_profile_with_capacity_wait(
        client,
        proxy,
        profile_id=profile_id,
        progress_callback=report_job_progress,
    )
    try:
        from core import browser_traffic
        from core.registration_service import registration_fact_context

        facts = registration_fact_context()
        browser_traffic.bind_roxy_capture(
            opened,
            purpose="registration",
            registration_job_id=facts.get("job_id"),
            operation_run_id=facts.get("run_id"),
        )
    except Exception:
        logger.exception("[浏览器流量] 关联注册任务上下文失败；注册流程继续")
    if profile_id and str(opened.profile_id) != str(profile_id):
        try:
            from core.roxy_profile_binding import persist_account_profile_id

            if not persist_account_profile_id(email, opened.profile_id):
                raise RuntimeError("账号 Roxy Profile 绑定写回失败")
            opened.account_bound = True
            client.mark_profile_bound(opened.profile_id)
            logger.info("[Roxy注册] 账号绑定环境已替换为可用 Profile")
        except Exception:
            logger.exception("[Roxy注册] 回写替代 Profile 绑定失败；停止使用未绑定环境")
            try:
                client.cleanup_profile(opened)
            except Exception:
                logger.exception("[Roxy注册] 绑定失败后的替代环境清理失败")
            raise
    driver = None
    profile_discarded = False
    create_acknowledged = False
    openai_password: str | None = None
    access_token: str | None = None
    account_id: int | None = None
    totp_secret: str | None = None
    plan_check_session = None
    remote_identity = "unknown"
    auth_challenge_chain: list[str] = []
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
        remote_identity = classify_registration_identity(next_state)
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
        if existing_password or openai_password:
            auth_challenge_chain.append("password")
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
        submitted_otps = _OtpAttemptTracker()
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
                    otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
                    last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                    report_job_otp_evidence(
                        request_kind="resend",
                        ui_ack=last_otp_ui_ack,
                        detail="等待超时后请求重新发送验证码",
                    )
                    human_delay("api")
                    current_otp = None
                    continue
            if not submitted_otps.accept(current_otp):
                failure_detail = "收码器返回了本次运行已经提交过的验证码，拒绝重复提交"
                logger.warning("[Roxy注册][OTP] %s", failure_detail)
                if otp_attempt >= max_otp_attempts:
                    failure_code = "otp_reused_after_resend"
                    report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}")
                try:
                    resend_result = _resend_email_otp_after_failure(
                        driver,
                        reason=failure_detail,
                        budget=otp_budget,
                    )
                except Exception as resend_exc:
                    failure_code = "otp_request_unconfirmed"
                    failure_detail = "重复验证码已拒绝，但验证码重发控件未能完成或缺少确认"
                    report_job_otp_evidence(
                        request_kind="resend",
                        ui_ack="rejected",
                        detail=failure_detail,
                        failure_code=failure_code,
                    )
                    report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                    raise RuntimeError(f"{failure_code}: {failure_detail}") from resend_exc
                otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
                last_otp_ui_ack = str(resend_result.get("ui_ack") or "unconfirmed")
                report_job_otp_evidence(
                    request_kind="resend",
                    ui_ack=last_otp_ui_ack,
                    detail="拒绝重复验证码后请求重新发送",
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
            if outcome == "totp_required":
                # A TOTP challenge after email verification proves that this
                # address is continuing an existing account authentication;
                # it must never fall through to the new-account profile page.
                remote_identity = "existing"
                post_otp_state = _complete_registration_totp_after_email_otp(
                    driver,
                    email,
                    existing_password,
                    existing_totp_secret,
                )
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                if "totp" not in auth_challenge_chain:
                    auth_challenge_chain.append("totp")
                resume_login_state = "advanced"
                break
            if outcome in ('accepted', 'email_verified'):
                if "email_otp" not in auth_challenge_chain:
                    auth_challenge_chain.append("email_otp")
                break
            if otp_attempt >= max_otp_attempts:
                failure_code = "otp_invalid_or_expired"
                failure_detail = "已取得并提交验证码，但页面未接受或验证码已过期"
                report_job_otp_evidence(detail=failure_detail, failure_code=failure_code)
                report_job_progress("email_otp", "failed", f"{failure_code}: {failure_detail}")
                raise RuntimeError(f"{failure_code}: {failure_detail}")
            logger.warning("[Roxy注册][OTP] 验证码错误/过期，准备重新发送并重新获取验证码（%s/%s）", otp_attempt + 1, max_otp_attempts)
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
            otp_after_ts = float(resend_result.get("requested_after_ts") or time.time())
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
            remote_identity = "new_candidate"
            create_acknowledged = True
            # 给 OAuth 回调 / session cookie 写入一点时间。
            human_delay("post_auth")
            report_job_progress("profile", "success", "账号资料已提交")
        else:
            remote_identity = "existing"
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
                "roxybrowser": {
                    "profile_id": opened.profile_id,
                    "open_result": opened.raw,
                    "retained": True,
                },
                "account_password": openai_password,
                "registration_checkpoint": "core_persisted",
            },
        )
        opened.account_bound = True
        client.mark_profile_bound(opened.profile_id)
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

                twofa_driver = _twofa_cfg.get_twofa_driver_for_options(options)
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
                    if not captured.get("quota_status"):
                        from core.chatgpt_plan import query_account_quota
                        captured.update(query_account_quota(
                            access_token,
                            proxy=proxy or None,
                            session=plan_check_session,
                        ))
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
            "remote_identity": remote_identity,
            "remote_identity_state": "confirmed",
            "registration_intent": "reconcile" if remote_identity == "existing" else "new",
            "auth": auth_result_for_registration(
                {"success": True},
                auth_method="roxy",
                remote_identity=remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
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
        request_unknown = password_result_unknown or _is_registration_request_unknown(error_text)
        remote_existing = isinstance(exc, RemoteExistingAccountError) or remote_identity == "existing"
        password_rejected = isinstance(exc, PasswordRejectedError)
        mfa_secret_missing = isinstance(exc, MfaSecretMissingError) or any(marker in error_text.lower() for marker in (
            "缺少可用密码或 totp",
            "没有 totp 密钥",
            "没有可用 totp",
            "mfa_secret_missing",
        ))
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
            password_target_missing = any(
                marker in error_text.lower()
                for marker in _PASSWORD_ENTRY_FAILURE_MARKERS
            )
            release_email(
                email,
                status=(
                    "failed"
                    if create_acknowledged
                    or password_target_missing
                    or request_unknown
                    or remote_existing
                    else "available"
                ),
                note=f"Roxy注册失败: {error_text[:180]}",
            )
        except Exception:
            pass
        auth_remote_identity = "existing" if remote_existing else remote_identity
        auth_error_code = (
            "password_rejected"
            if password_rejected
            else "mfa_secret_missing"
            if mfa_secret_missing
            else
            "remote_existing"
            if remote_existing
            else "request_unknown"
            if request_unknown
            else "registration_failed"
        )
        return {
            "success": False,
            "registration_pending": bool(account_id and not access_token),
            "email": email,
            "account_id": account_id,
            "access_token": access_token,
            "totp_secret": totp_secret,
            "request_unknown": request_unknown,
            "manual_reconcile": remote_existing,
            "remote_identity": "existing" if remote_existing else remote_identity,
            "remote_identity_state": "confirmed" if remote_existing else "unknown",
            "remote_account_state": "confirmed" if remote_existing else "request_unknown" if request_unknown else "not_started",
            "error_code": auth_error_code,
            "auth": auth_result_for_registration(
                {"success": False, "error_code": auth_error_code},
                auth_method="roxy",
                remote_identity=auth_remote_identity,
                challenge_chain=auth_challenge_chain,
            ).as_dict(),
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
