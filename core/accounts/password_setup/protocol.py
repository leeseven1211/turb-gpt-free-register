"""已有账号补密码的独立协议接口，不改变注册或登录驱动。"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from core.accounts.liveness.protocol import v2 as protocol_auth
from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.auth.protocol.openai_auth import build_sentinel_header, request_sentinel_token
from core.auth.protocol.sentinel_runner import generate_sentinel_token
from core.auth.state_machine import CancellationRequested
from core.email import provider as email_provider
from core.email.mailbox_wait import use_cooperative_wait
from core.network.response_diagnostics import _auth_payload_from_body
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost

from core.kernels.protocol.local.password_setup import protocol as _protocol_kernel

_CHATGPT = "https://chatgpt.com"
_AUTH = "https://auth.openai.com"
_PASSWORD_PAGE = _AUTH + "/reset-password/new-password"
_CONTROL_ERRORS = (CancellationRequested, OperationCancelled, OperationLeaseLost)
_PENDING_TYPES = {"password", "new_password", "password_reset", "email_verification", "email_otp", "mfa_challenge", "about_you"}
logger = logging.getLogger(__name__)
_OTP_RESPONSE_OPERATIONS = {"otp_context", "otp_context_recheck", "otp_initial_send", "otp_resend"}
_OTP_REMOTE_ERROR_CODES = {
    "invalid_auth_step", "invalid_request", "invalid_request_error", "invalid_state", "missing_session",
    "session_expired", "session_invalid", "session_not_found", "login_required", "identity_provider_mismatch",
    "rate_limit_exceeded", "too_many_requests", "access_denied", "account_deactivated", "account_suspended",
}


ProtocolPasswordSetupError = _protocol_kernel.ProtocolPasswordSetupError


def _default_password_otp_provider(email, *, after_ts):
    source = email_provider.resolve_email_source(email, fallback=False)
    return email_provider.wait_for_otp(email, after_ts=after_ts, email_source=source)


def _check(checkpoint: Callable[[], None] | None) -> None:
    return _protocol_kernel._check(checkpoint)


def _trusted_url(value: str, *, unknown: bool = False) -> str:
    return _protocol_kernel._trusted_url(value, unknown=unknown)


def _request(session, method: str, url: str, *, checkpoint=None, final: bool = False, **kwargs):
    return _protocol_kernel._request(
        session,
        method,
        url,
        checkpoint=checkpoint,
        final=final,
        _check=_check,
        is_proxy_transport_failure=is_proxy_transport_failure,
        **kwargs,
    )


def _payload(response, *, final: bool = False) -> dict:
    return _protocol_kernel._payload(response, final=final)


def _response_ok(response, *, unknown: bool = False) -> None:
    return _protocol_kernel._response_ok(response, unknown=unknown, _payload=_payload)


def _follow(session, url: str, *, referer: str, checkpoint=None, final: bool = False) -> str:
    return _protocol_kernel._follow(
        session,
        url,
        referer=referer,
        checkpoint=checkpoint,
        final=final,
        _request=_request,
        _response_ok=_response_ok,
        _trusted_url=_trusted_url,
    )


def _sentinel_headers(session, flow: str, checkpoint=None) -> dict[str, str]:
    return _protocol_kernel._sentinel_headers(
        session,
        flow,
        checkpoint,
        _check=_check,
        build_sentinel_header=build_sentinel_header,
        generate_sentinel_token=generate_sentinel_token,
        is_proxy_transport_failure=is_proxy_transport_failure,
        request_sentinel_token=request_sentinel_token,
        reraise_control=protocol_auth._reraise_control,
    )


def _auth_post(session, path: str, payload: dict, *, referer: str, flow: str, checkpoint=None):
    return _protocol_kernel._auth_post(
        session,
        path,
        payload,
        referer=referer,
        flow=flow,
        checkpoint=checkpoint,
        _request=_request,
        _sentinel_headers=_sentinel_headers,
    )


def _log_otp_response(operation: str, response) -> None:
    return _protocol_kernel._log_otp_response(
        operation,
        response,
        _auth_payload_from_body=_auth_payload_from_body,
        reraise_control=protocol_auth._reraise_control,
    )


def _email_verification_context(
    session, email: str, *, referer: str, checkpoint=None, operation: str = "otp_context"
) -> dict:
    return _protocol_kernel._email_verification_context(
        session,
        email,
        referer=referer,
        checkpoint=checkpoint,
        operation=operation,
        _log_otp_response=_log_otp_response,
        _payload=_payload,
        _request=_request,
    )


def _send_email_verification_code(session, email: str, *, referer: str, after_ts: float, checkpoint=None) -> float:
    return _protocol_kernel._send_email_verification_code(
        session,
        email,
        referer=referer,
        after_ts=after_ts,
        checkpoint=checkpoint,
        _email_verification_context=_email_verification_context,
        _log_otp_response=_log_otp_response,
        _payload=_payload,
        _request=_request,
        _sentinel_headers=_sentinel_headers,
        clock=time,
    )


def _require_password_page(url: str) -> None:
    return _protocol_kernel._require_password_page(url)


def _continuation(data: dict) -> str:
    return _protocol_kernel._continuation(data)


def _is_mfa_page(url: str) -> bool:
    return _protocol_kernel._is_mfa_page(url)


def _verify_mfa(session, data: dict, url: str, secret: str, *, checkpoint=None) -> str:
    return _protocol_kernel._verify_mfa(
        session,
        data,
        url,
        secret,
        checkpoint=checkpoint,
        _check=_check,
        _continuation=_continuation,
        _payload=_payload,
        _request=_request,
        _trusted_url=_trusted_url,
        extract_factor_id=protocol_auth._extract_factor_id,
        totp_code=protocol_auth._totp_code,
        mfa_error=protocol_auth.ProtocolV2AuthError,
    )


def _follow_password_page(session, url: str, *, referer: str, checkpoint=None) -> str:
    return _protocol_kernel._follow_password_page(
        session,
        url,
        referer=referer,
        checkpoint=checkpoint,
        _follow=_follow,
        _require_password_page=_require_password_page,
    )


def _confirm_result(session, data: dict, *, checkpoint=None) -> None:
    return _protocol_kernel._confirm_result(
        session, data, checkpoint=checkpoint, _continuation=_continuation, _follow=_follow, _trusted_url=_trusted_url
    )


def add_password(
    session,
    email: str,
    password: str,
    *,
    checkpoint=None,
    on_dispatched=None,
    on_confirmed=None,
    otp_provider=None,
    totp_secret: str = "",
) -> dict:
    return _protocol_kernel.add_password(
        session,
        email,
        password,
        checkpoint=checkpoint,
        on_dispatched=on_dispatched,
        on_confirmed=on_confirmed,
        otp_provider=otp_provider,
        totp_secret=totp_secret,
        _auth_post=_auth_post,
        _check=_check,
        _confirm_result=_confirm_result,
        _continuation=_continuation,
        _follow=_follow,
        _follow_password_page=_follow_password_page,
        _is_mfa_page=_is_mfa_page,
        _payload=_payload,
        _request=_request,
        _require_password_page=_require_password_page,
        _send_email_verification_code=_send_email_verification_code,
        _sentinel_headers=_sentinel_headers,
        _trusted_url=_trusted_url,
        _verify_mfa=_verify_mfa,
        use_cooperative_wait=use_cooperative_wait,
        default_otp_provider=_default_password_otp_provider,
        clock=time,
    )
