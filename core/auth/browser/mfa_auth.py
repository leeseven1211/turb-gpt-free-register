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

from core.kernels.browser.roxy import twofa as _twofa_browser_kernel


def _mfa_otp_wait_seconds():
    from config import email as email_cfg

    return getattr(email_cfg, "OTP_MAX_WAIT", 240)


def _mfa_login_credentials(email):
    from core.accounts.credentials import get_account_login_credentials

    return get_account_login_credentials(email)


def _probe_existing_roxy_totp(driver, email: str, *, timeout: float = 15.0) -> dict:
    return _twofa_browser_kernel._probe_existing_roxy_totp(
        driver, email, timeout=timeout, _checkpoint=_checkpoint, current_execution_context=current_execution_context
    )


def _totp_secret_candidate(value: object) -> str | None:
    return _twofa_browser_kernel._totp_secret_candidate(value)

def _first_visible_css(driver, selector: str):
    return _twofa_browser_kernel._first_visible_css(driver, selector, _visible=_visible)

def _find_authenticator_toggle(driver):
    return _twofa_browser_kernel._find_authenticator_toggle(
        driver, _first_visible_css=_first_visible_css, _visible=_visible
    )

def _is_stale_element_error(exc: BaseException) -> bool:
    return _twofa_browser_kernel._is_stale_element_error(exc)

def _visible_new_password_inputs(driver) -> list:
    return _twofa_browser_kernel._visible_new_password_inputs(driver)

def _wait_visible_css(driver, selector: str, *, timeout: int, label: str):
    return _twofa_browser_kernel._wait_visible_css(
        driver,
        selector,
        timeout=timeout,
        label=label,
        _check_manual_stop=_check_manual_stop,
        _first_visible_css=_first_visible_css,
        clock=time,
    )

def _detect_mfa_enrollment_step(driver, *, monitor_mfa_enrollment: bool = False):
    return _twofa_browser_kernel._detect_mfa_enrollment_step(
        driver,
        monitor_mfa_enrollment=monitor_mfa_enrollment,
        _check_manual_stop=_check_manual_stop,
        _first_visible_css=_first_visible_css,
        auth_page_error=auth_page_error,
    )


_MfaStepChanged = _twofa_browser_kernel._MfaStepChanged


def _wait_mfa_email_code(driver, email, after_ts, provider):
    return _twofa_browser_kernel._wait_mfa_email_code(
        driver,
        email,
        after_ts,
        provider,
        _check_manual_stop=_check_manual_stop,
        _detect_mfa_enrollment_step=_detect_mfa_enrollment_step,
        _log_prefix=_log_prefix,
        bounded_sleep=bounded_sleep,
        current_execution_context=current_execution_context,
        use_budget=use_budget,
        use_cooperative_wait=use_cooperative_wait,
        timeout_provider=_mfa_otp_wait_seconds,
    )

def _wait_mfa_enrollment_step(driver, *, timeout: int = 90, monitor_mfa_enrollment: bool = False):
    return _twofa_browser_kernel._wait_mfa_enrollment_step(
        driver,
        timeout=timeout,
        monitor_mfa_enrollment=monitor_mfa_enrollment,
        _check_manual_stop=_check_manual_stop,
        _detect_mfa_enrollment_step=_detect_mfa_enrollment_step,
        clock=time,
    )

def _wait_after_mfa_email_submit(
    driver, *, timeout: int = 30, resubmit_after: float = 8.0, monitor_mfa_enrollment: bool = False
):
    return _twofa_browser_kernel._wait_after_mfa_email_submit(
        driver,
        timeout=timeout,
        resubmit_after=resubmit_after,
        monitor_mfa_enrollment=monitor_mfa_enrollment,
        _button_after_input=_button_after_input,
        _check_manual_stop=_check_manual_stop,
        _detect_mfa_enrollment_step=_detect_mfa_enrollment_step,
        _human_click=_human_click,
        _log_prefix=_log_prefix,
        clock=time,
    )

def _dismiss_single_action_dialog(driver) -> bool:
    return _twofa_browser_kernel._dismiss_single_action_dialog(
        driver, _human_click=_human_click, _log_prefix=_log_prefix
    )

def _dismiss_chatgpt_pricing_modal(driver) -> bool:
    return _twofa_browser_kernel._dismiss_chatgpt_pricing_modal(
        driver, _human_click=_human_click, _log_prefix=_log_prefix,
        clock=time,
    )

def _click_chatgpt_settings_control(driver, element, *, label: str = "") -> None:
    return _twofa_browser_kernel._click_chatgpt_settings_control(
        driver, element, label=label, _human_click=_human_click
    )

def _reveal_chatgpt_settings_navigation(driver) -> bool:
    return _twofa_browser_kernel._reveal_chatgpt_settings_navigation(driver)

def _click_password_setting_fallback(driver) -> bool:
    return _twofa_browser_kernel._click_password_setting_fallback(
        driver, _click_chatgpt_settings_control=_click_chatgpt_settings_control, _visible=_visible
    )

def _open_chatgpt_security_settings(driver, *, timeout: int = 75):
    return _twofa_browser_kernel._open_chatgpt_security_settings(
        driver,
        timeout=timeout,
        _check_manual_stop=_check_manual_stop,
        _click_chatgpt_settings_control=_click_chatgpt_settings_control,
        _dismiss_chatgpt_pricing_modal=_dismiss_chatgpt_pricing_modal,
        _dismiss_single_action_dialog=_dismiss_single_action_dialog,
        _find_authenticator_toggle=_find_authenticator_toggle,
        _page_warmup=_page_warmup,
        _refresh_chatgpt_settings_shell_if_needed=_refresh_chatgpt_settings_shell_if_needed,
        _safe_get=_safe_get,
        navigation_timeout=lambda: (getattr(_cfg, "ROXY_SELENIUM_TIMEOUT", 90) or 90),
        clock=time,
    )

def _disable_roxy_2fa(driver, toggle, *, timeout: int = 60) -> None:
    return _twofa_browser_kernel._disable_roxy_2fa(
        driver,
        toggle,
        timeout=timeout,
        _check_manual_stop=_check_manual_stop,
        _find_authenticator_toggle=_find_authenticator_toggle,
        _human_click=_human_click,
        _log_prefix=_log_prefix,
        clock=time,
    )

def _complete_settings_email_reauth(driver, email: str, *, challenge_detector=None, challenge_submitter=None) -> None:
    return _twofa_browser_kernel._complete_settings_email_reauth(
        driver,
        email,
        challenge_detector=challenge_detector,
        challenge_submitter=challenge_submitter,
        _button_after_input=_button_after_input,
        _check_manual_stop=_check_manual_stop,
        _clear_otp_inputs=_clear_otp_inputs,
        _first_visible_css=_first_visible_css,
        _human_click=_human_click,
        _is_email_verification_page=_is_email_verification_page,
        _log_prefix=_log_prefix,
        _roxy_page_state=_roxy_page_state,
        _type_otp=_type_otp,
        current_execution_context=current_execution_context,
        current_override=current_override,
        wait_for_otp=wait_for_otp,
        credentials_reader=_mfa_login_credentials,
        clock=time,
    )

def _read_totp_secret_from_dialog(driver, field, *, monitor_mfa_enrollment: bool = False) -> str | None:
    return _twofa_browser_kernel._read_totp_secret_from_dialog(
        driver, field, monitor_mfa_enrollment=monitor_mfa_enrollment, _totp_secret_candidate=_totp_secret_candidate
    )

def _manual_totp_secret(driver, field, *, timeout: int = 20, monitor_mfa_enrollment: bool = False) -> str:
    return _twofa_browser_kernel._manual_totp_secret(
        driver,
        field,
        timeout=timeout,
        monitor_mfa_enrollment=monitor_mfa_enrollment,
        _check_manual_stop=_check_manual_stop,
        _detect_mfa_enrollment_step=_detect_mfa_enrollment_step,
        _human_click=_human_click,
        _log_prefix=_log_prefix,
        _read_totp_secret_from_dialog=_read_totp_secret_from_dialog,
        clock=time,
    )

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
    return _twofa_browser_kernel.setup_roxy_2fa(
        driver,
        email,
        on_secret=on_secret,
        existing_secret=existing_secret,
        force_reconfigure=force_reconfigure,
        on_disabled=on_disabled,
        otp_provider=otp_provider,
        monitor_mfa_enrollment=monitor_mfa_enrollment,
        _button_after_input=_button_after_input,
        _check_manual_stop=_check_manual_stop,
        _detect_mfa_enrollment_step=_detect_mfa_enrollment_step,
        _disable_roxy_2fa=_disable_roxy_2fa,
        _find_authenticator_toggle=_find_authenticator_toggle,
        _first_visible_css=_first_visible_css,
        _human_click=_human_click,
        _human_type_text=_human_type_text,
        _log_prefix=_log_prefix,
        _manual_totp_secret=_manual_totp_secret,
        _open_chatgpt_security_settings=_open_chatgpt_security_settings,
        _probe_existing_roxy_totp=_probe_existing_roxy_totp,
        _totp_secret_candidate=_totp_secret_candidate,
        _wait_after_mfa_email_submit=_wait_after_mfa_email_submit,
        _wait_mfa_email_code=_wait_mfa_email_code,
        _wait_mfa_enrollment_step=_wait_mfa_enrollment_step,
        wait_for_otp=wait_for_otp,
        clock=time,
    )

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
