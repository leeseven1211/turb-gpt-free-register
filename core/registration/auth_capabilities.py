"""Public capability boundary for browser authentication.

Concrete browser work is deliberately split by responsibility:

* :mod:`selenium_resource` owns driver construction and navigation resources;
* :mod:`selenium_dom` owns DOM snapshots, page recognition, and interactions;
* :mod:`email_otp` owns email submission and OTP state handling;
* :mod:`password_auth` owns password/profile flows;
* :mod:`session_auth` owns ChatGPT session acquisition; and
* :mod:`mfa_auth` owns Authenticator/security settings.

This module is a small stable facade.  It also hosts the explicit compatibility
boundary used by old Roxy monkeypatches.  Overrides live in a ``ContextVar``
for one call/task and never rebind a shared module global.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Mapping

from core.auth_challenge import AuthCancelledError, AuthErrorCode, AuthStepResult, StepResult, normalize_step_result
from core.registration.auth_context import (
    AuthExecutionContext,
    Cancellation,
    CancellationRequested,
    StageBudget,
    StageTimeout,
    checkpoint,
    compatibility_overrides,
    current_execution_context,
    execution_context,
    install_dispatches,
    remaining_timeout,
)
from core.registration.state_machine import PageState, classify_page

from . import email_otp as _email_otp
from . import mfa_auth as _mfa_auth
from . import password_auth as _password_auth
from . import selenium_dom as _selenium_dom
from . import selenium_resource as _selenium_resource
from . import session_auth as _session_auth


_MODULES = (
    _selenium_resource,
    _selenium_dom,
    _email_otp,
    _password_auth,
    _session_auth,
    _mfa_auth,
)


_CAPABILITY_NAMES = (
    # resource
    "_log_prefix", "_build_driver", "_center_browser_window", "_wait",
    "_budget_timeout", "_roxy_page_state", "_auth_terminal_page_state", "_safe_get",
    "_visible", "_browser_actions_enabled", "_apply_browser_automation_mask",
    "_human_scroll_to", "_human_click", "_human_type_text", "_page_warmup",
    "_refresh_chatgpt_settings_shell_if_needed", "_settings_page_not_ready",
    "_find_any", "_click_any", "_type_any",
    # email/OTP
    "_email_entry_state", "_find_visible_email_input_js", "_is_oauth_consent_like",
    "_is_external_idp_url", "_assert_not_external_idp", "_click_email_entry_option",
    "_is_blank_chatgpt_auth_shell", "_reload_blank_chatgpt_auth_shell",
    "_email_submit_advanced_state", "_type_email_address",
    "_submit_nearest_form_for_active_input", "_current_email_input_value",
    "_stabilize_email_input_before_submit", "_submit_email_form_stable",
    "_submit_email_step", "_recover_email_submit_if_stuck",
    "_submit_email_via_browser_nextauth", "_email_input_value_state",
    "_is_email_login_page_still_present", "_diagnostic_url", "_redact_diagnostic_text",
    "_log_blank_auth_shell_diagnostics", "_wait_email_submit_next_state",
    "_submit_email_and_wait_next", "_type_otp", "_email_otp_page_state",
    "_is_email_verification_page", "_clear_otp_inputs", "_click_resend_email_otp",
    "_resend_email_otp_after_failure", "_classify_otp_wait_failure",
    "_complete_registration_totp_after_email_otp", "_wait_after_email_otp_submit",
    "complete_openai_login_challenge", "_is_totp_login_page", "_submit_saved_login_totp",
    # DOM/profile/password
    "_click_continue", "_maybe_accept", "_page_snapshot", "_has_access_token",
    "_is_profile_like", "_set_element_value", "_select_or_type", "_fill_birthday_or_age",
    "_generate_roxy_password", "_registration_password", "_registration_auth_mode",
    "_password_transition_timeout_seconds", "_password_page_state",
    "_is_signup_password_page", "_is_login_password_page",
    "_click_passwordless_signup_if_present", "_click_signup_password_from_otp_if_present",
    "_fill_password_page_if_present", "_accept_profile_consents", "_complete_profile_page",
    "_click_if_enabled_submit", "_button_after_input", "_check_manual_stop",
    "_PasswordTransitionTimeout", "_probe_chatgpt_password_eligibility",
    # session
    "_read_chatgpt_session_once", "_switch_to_chatgpt_window_if_any", "_fetch_chatgpt_session",
    # MFA/security
    "_totp_secret_candidate", "_first_visible_css", "_is_stale_element_error",
    "_visible_new_password_inputs", "_wait_visible_css", "_detect_mfa_enrollment_step",
    "_wait_mfa_enrollment_step", "_wait_after_mfa_email_submit",
    "_dismiss_single_action_dialog", "_dismiss_chatgpt_pricing_modal",
    "_click_chatgpt_settings_control", "_reveal_chatgpt_settings_navigation",
    "_click_password_setting_fallback", "_open_chatgpt_security_settings", "_disable_roxy_2fa",
    "_complete_settings_email_reauth", "_read_totp_secret_from_dialog", "_manual_totp_secret",
    "set_roxy_login_password", "setup_roxy_2fa", "setup_protocol_2fa_with_browser_fallback",
    # external dependencies that old Roxy tests patch
    "human_delay", "wait_for_otp", "resolve_email_source", "setup_2fa_protocol",
    "time",
)


def _find_module_binding(name: str) -> Any:
    for module in _MODULES:
        value = getattr(module, name, None)
        if value is not None:
            return value
    return None


for _name in _CAPABILITY_NAMES:
    _value = _find_module_binding(_name)
    if _value is not None:
        globals()[_name] = _value


_COMPAT_BINDING_NAMES = frozenset(_CAPABILITY_NAMES)


def call_with_compatibility(name: str, overrides: Mapping[str, object] | None, *args: Any, **kwargs: Any) -> Any:
    """Call one facade binding with explicit, context-local legacy overrides."""
    context = kwargs.pop("context", None)
    with execution_context(context), compatibility_overrides(overrides):
        target = globals().get(str(name))
        if not callable(target):
            raise AttributeError(f"未知共享认证能力: {name}")
        return target(*args, **kwargs)


_PUBLIC_ALIASES = {
    "build_driver": "_build_driver",
    "center_browser_window": "_center_browser_window",
    "safe_get": "_safe_get",
    "page_warmup": "_page_warmup",
    "find_any": "_find_any",
    "click_any": "_click_any",
    "type_any": "_type_any",
    "human_click": "_human_click",
    "human_type_text": "_human_type_text",
    "click_email_entry_option": "_click_email_entry_option",
    "type_email_address": "_type_email_address",
    "submit_email_step": "_submit_email_step",
    "recover_email_submit_if_stuck": "_recover_email_submit_if_stuck",
    "submit_email_via_browser_nextauth": "_submit_email_via_browser_nextauth",
    "submit_email_and_wait_next": "_submit_email_and_wait_next",
    "wait_email_submit_next_state": "_wait_email_submit_next_state",
    "type_otp": "_type_otp",
    "email_otp_page_state": "_email_otp_page_state",
    "clear_otp_inputs": "_clear_otp_inputs",
    "click_resend_email_otp": "_click_resend_email_otp",
    "wait_after_email_otp_submit": "_wait_after_email_otp_submit",
    "click_continue": "_click_continue",
    "maybe_accept": "_maybe_accept",
    "has_access_token": "_has_access_token",
    "is_email_verification_page": "_is_email_verification_page",
    "is_login_password_page": "_is_login_password_page",
    "click_passwordless_signup_if_present": "_click_passwordless_signup_if_present",
    "fill_password_page_if_present": "_fill_password_page_if_present",
    "complete_profile_page": "_complete_profile_page",
    "fetch_chatgpt_session": "_fetch_chatgpt_session",
    "check_manual_stop": "_check_manual_stop",
    "registration_password": "_registration_password",
    "set_login_password": "set_roxy_login_password",
    "setup_roxy_2fa": "setup_roxy_2fa",
    "setup_protocol_2fa_with_browser_fallback": "setup_protocol_2fa_with_browser_fallback",
}


def _make_public_adapter(public_name: str, private_name: str):
    target = globals().get(private_name)

    def adapter(*args: Any, context: AuthExecutionContext | None = None, **kwargs: Any) -> Any:
        current_target = globals().get(private_name)
        # For aliases whose public and private names are identical (for
        # example ``setup_roxy_2fa``), installing the adapter replaces that
        # facade binding.  Keep the original dispatch target instead of
        # recursively looking up the adapter itself.
        if current_target is adapter or private_name == public_name:
            current_target = target
        if not callable(current_target):
            raise AttributeError(f"未知共享认证能力: {private_name}")
        with execution_context(context):
            return current_target(*args, **kwargs)

    if callable(target):
        adapter = wraps(target)(adapter)

    adapter.__name__ = public_name
    adapter.__qualname__ = public_name
    adapter.__module__ = __name__
    adapter.__shared_capability__ = True
    adapter.__capability_name__ = public_name
    return adapter


for _public_name, _private_name in _PUBLIC_ALIASES.items():
    if _private_name in globals():
        globals()[_public_name] = _make_public_adapter(_public_name, _private_name)


# Short public names are the only names imported by new callers.  Private
# bindings remain available in the facade solely for the Roxy compatibility
# bridge and its existing monkeypatch points.
__all__ = tuple(_PUBLIC_ALIASES) + (
    "AuthCancelledError", "AuthErrorCode", "AuthExecutionContext", "AuthStepResult",
    "Cancellation", "CancellationRequested", "PageState", "StageBudget", "StageTimeout",
    "StepResult", "call_with_compatibility", "checkpoint", "classify_page",
    "compatibility_overrides", "current_execution_context", "execution_context",
    "normalize_step_result", "remaining_timeout",
)
