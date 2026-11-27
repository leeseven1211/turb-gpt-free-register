# -*- coding: utf-8 -*-
"""协议改密确认后的凭据写回、读回和只读业务核验。"""
from __future__ import annotations

import json
from typing import Any

from core import db
from core.accounts.liveness.protocol.v3 import _verify_identity
from core.accounts.plans.client import check_account_plan, token_claims
from core.accounts.password_setup.reset_support import ProtocolPasswordResetError
from core.auth.state_machine import CancellationRequested
from core.operations.runtime import OperationCancelled
from core.operations.task_gateway import OperationLeaseLost
from core.storage.accounts import protocol_sessions
from core.storage.accounts.password_recovery import (
    complete_manual_password_change,
    save_manual_password_change_session,
)

ResetCompletionError = ProtocolPasswordResetError
_SAFE_BUSINESS_CODES = {
    "account_deactivated",
    "account_not_found",
    "auth_failed",
    "forbidden",
    "invalid_token",
    "rate_limited",
    "security_policy",
    "token_expired",
    "token_revoked",
    "unauthorized",
}


def _error(code: str, *, stage: str, cause_code: str | None = None,
           category: str = "runtime", retryable: bool = False,
           request_unknown: bool = False) -> ProtocolPasswordResetError:
    cause = cause_code or code
    return ProtocolPasswordResetError(
        code, cause, stage=stage, category=category, cause_code=cause,
        retryable=retryable, request_unknown=request_unknown,
    )


def _code(error: BaseException, default: str) -> str:
    value = getattr(error, "cause_code", None) or getattr(error, "code", None)
    if isinstance(value, str) and value and len(value) <= 120 and all(
        char.isalnum() or char in {"_", "-", "."} for char in value
    ):
        return value
    return default


def _preview_code(value: Any) -> str:
    if isinstance(value, str):
        code = value.strip().lower()
        if code in _SAFE_BUSINESS_CODES:
            return code
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return ""
    if isinstance(value, dict):
        for key in ("code", "error_code", "errorCode", "type"):
            code = str(value.get(key) or "").strip().lower()
            if code in _SAFE_BUSINESS_CODES:
                return code
        for key in ("error", "errors", "details"):
            code = _preview_code(value.get(key))
            if code:
                return code
    elif isinstance(value, list):
        for item in value[:8]:
            code = _preview_code(item)
            if code:
                return code
    return ""


def _business_cause(result: dict | None) -> str:
    if isinstance(result, dict):
        code = _preview_code(result.get("response_preview"))
        if code:
            return code
        for key in ("cause_code", "error_code", "code", "error"):
            code = _preview_code(result.get(key))
            if code:
                return code
        status = result.get("http_status")
        if isinstance(status, int):
            if status == 200:
                return "response_invalid"
            if status == 401:
                return "http_401"
            if status == 403:
                return "http_403"
            if status == 429:
                return "http_429"
            if status >= 500:
                return "http_5xx"
            return f"http_{status}"
    return "business_check_failed"


def _business_category(result: dict | None) -> str:
    if isinstance(result, dict):
        status = result.get("http_status")
        if status == 401:
            return "auth"
        if status == 403:
            return "security"
        if status == 200:
            return "response"
        if isinstance(status, int):
            return "network"
    return "network"


def _business_retryable(result: dict | None) -> bool:
    if not isinstance(result, dict):
        return True
    status = result.get("http_status")
    if isinstance(status, int):
        return status in {408, 409, 425, 429} or status >= 500
    return bool(result.get("retryable"))


def _result(*, stage: str, cause_code: str, retryable: bool = False,
            request_unknown: bool = False, error_category: str | None = None) -> dict[str, Any]:
    category = {
        "password_authentication": "auth",
        "credential_writeback": "runtime",
        "credential_readback": "runtime",
        "private_session_readback": "runtime",
        "business_verification": "network",
        "credential_completion": "runtime",
    }.get(stage, "runtime")
    message = {
        "password_authentication": "新密码认证会话验证失败",
        "credential_writeback": "新会话凭据保存失败",
        "credential_readback": "账号凭据读回核验失败",
        "private_session_readback": "私有协议会话读回核验失败",
        "business_verification": "新 AT 业务身份核验失败",
        "credential_completion": "改密收尾状态提交失败",
    }.get(stage, "密码重置收尾失败")
    return {
        "ok": False,
        "status": "failed",
        "error": "password_reset_completion_failed",
        "message": message,
        "error_category": error_category or category,
        "password_reset": "confirmed",
        "password_confirmed": True,
        "completion_pending": True,
        "stage": stage,
        "cause_code": cause_code,
        "retryable": bool(retryable),
        "request_unknown": bool(request_unknown),
    }


def _private_session_matches(payload: Any, account: dict, session: dict) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("cookies"), list):
        return False
    user = session.get("user") if isinstance(session.get("user"), dict) else {}
    account_info = session.get("account") if isinstance(session.get("account"), dict) else {}
    expected_user = str(account.get("user_id") or user.get("id") or "")
    expected_account = str(account.get("chatgpt_account_id") or account_info.get("id") or "")
    return (
        bool(payload["cookies"])
        and any(
            str(item.get("name") or "").startswith("__Secure-next-auth.session-token")
            and str(item.get("value") or "").strip()
            for item in payload["cookies"] if isinstance(item, dict)
        )
        and (not expected_user or not payload.get("user_id") or str(payload["user_id"]) == expected_user)
        and (
            not expected_account
            or not payload.get("chatgpt_account_id")
            or str(payload["chatgpt_account_id"]) == expected_account
        )
    )


def _private_session_matches_expected(payload: dict, expected: dict | None) -> bool:
    if not isinstance(expected, dict):
        return True
    actual = {
        (str(item.get("name") or ""), str(item.get("domain") or "").lower(), str(item.get("path") or "/")):
        str(item.get("value") or "")
        for item in payload.get("cookies") or []
        if isinstance(item, dict)
    }
    for item in expected.get("cookies") or []:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue
        key = (str(item["name"]), str(item.get("domain") or "").lower(), str(item.get("path") or "/"))
        if actual.get(key) != str(item.get("value") or ""):
            return False
    return True


def validate_password_session(account: dict, email: str, auth: dict) -> dict:
    """验证认证结果的完整 Session 与目标账号身份。"""
    if not isinstance(auth, dict) or auth.get("ok") is not True:
        raise _error(
            "password_authentication_failed",
            stage="password_authentication",
            cause_code="authentication_failed",
            retryable=bool(isinstance(auth, dict) and auth.get("retryable")),
        )
    token = str(auth.get("access_token") or "").strip()
    session = auth.get("session")
    if not token:
        raise _error("access_token_missing", stage="password_authentication")
    if not isinstance(session, dict):
        raise _error("session_invalid", stage="password_authentication")
    if str(session.get("accessToken") or "").strip() != token:
        raise _error(
            "session_token_mismatch",
            stage="password_authentication",
            cause_code="session_token_mismatch",
        )
    try:
        _verify_identity(session, str(email or ""), account)
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as error:
        raise _error(
            "session_identity_invalid",
            stage="password_authentication",
            cause_code=_code(error, "identity_mismatch"),
            retryable=bool(getattr(error, "retryable", False)),
        ) from None
    return {"access_token": token, "session": session}


def _notify(stage: str, *, checkpoint=None, report=None, message: str = "") -> None:
    if callable(checkpoint):
        checkpoint()
    if callable(report):
        try:
            report(stage=stage, state="running", message=message or stage, detail=None)
        except (CancellationRequested, OperationCancelled, OperationLeaseLost):
            raise
        except Exception:
            pass


def _failure(error: BaseException, stage: str, default: str) -> dict:
    if isinstance(error, (CancellationRequested, OperationCancelled, OperationLeaseLost)):
        raise error
    if isinstance(error, ProtocolPasswordResetError):
        stage = getattr(error, "stage", None) or stage
    default = getattr(error, "cause_code", None) or getattr(error, "code", None) or default
    return _result(
        stage=stage,
        cause_code=default,
        retryable=bool(getattr(error, "retryable", False)),
        request_unknown=bool(getattr(error, "request_unknown", False)),
    )


def _success() -> dict[str, Any]:
    return {
        "ok": True,
        "status": "success",
        "message": "密码重置与新会话验证完成",
        "password_reset": "confirmed",
        "password_confirmed": True,
        "credentials_saved": True,
        "business_verified": True,
        "credential_writeback": "confirmed",
        "business_verification": "confirmed",
        "completion_pending": False,
    }


def _verify_saved_credentials(
    *,
    account: dict,
    email: str,
    token: str,
    session: dict,
    protocol_session: dict | None = None,
    proxy=None,
    checkpoint=None,
    report=None,
) -> dict | None:
    _notify("credential_readback", checkpoint=checkpoint, report=report, message="读回账号凭据")
    try:
        stored = db.get_account(int(account.get("id") or 0))
        saved_session = db.get_account_chatgpt_session(int(account.get("id") or 0))
        if (
            not isinstance(stored, dict)
            or str(stored.get("access_token") or "").strip() != token
            or not isinstance(saved_session, dict)
            or str(saved_session.get("accessToken") or "").strip() != token
        ):
            raise _error("credential_readback_mismatch", stage="credential_readback")
        _verify_identity(saved_session, email, account)
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as error:
        return _failure(error, "credential_readback", "credential_readback_failed")

    _notify("private_session_readback", checkpoint=checkpoint, report=report, message="读回私有协议会话")
    try:
        cached = protocol_sessions.load_session(int(account.get("id") or 0), email)
        if (not _private_session_matches(cached, account, session)
                or not _private_session_matches_expected(cached, protocol_session)):
            raise _error(
                "private_session_readback_failed",
                stage="private_session_readback",
                cause_code="private_session_missing_or_mismatched",
            )
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as error:
        return _failure(error, "private_session_readback", "private_session_readback_failed")

    _notify("business_verification", checkpoint=checkpoint, report=report, message="核验新 AT 业务身份")
    try:
        business = check_account_plan(token, proxy=proxy, session=None)
    except (CancellationRequested, OperationCancelled, OperationLeaseLost):
        raise
    except Exception as error:
        return _failure(error, "business_verification", "business_check_failed")
    if not isinstance(business, dict) or business.get("ok") is not True:
        return _result(
            stage="business_verification",
            cause_code=_business_cause(business),
            retryable=_business_retryable(business),
            request_unknown=bool(isinstance(business, dict) and business.get("request_unknown")),
            error_category=_business_category(business),
        )
    session_account = session.get("account") if isinstance(session.get("account"), dict) else {}
    try:
        claims = token_claims(token)
    except Exception:
        claims = {}
    expected_account = str(
        account.get("chatgpt_account_id")
        or session_account.get("id")
        or claims.get("account_id")
        or ""
    )
    observed_account = str(business.get("response_account_id") or "")
    if not expected_account or not observed_account or observed_account == "default":
        return _result(stage="business_verification", cause_code="business_identity_missing")
    if expected_account and expected_account != observed_account:
        return _result(stage="business_verification", cause_code="business_identity_mismatch")
    return None


def complete_password_reset(
    *,
    recovery,
    owner: dict,
    account: dict,
    email: str,
    auth: dict,
    proxy=None,
    checkpoint=None,
    report=None,
) -> dict:
    """保存认证凭据，逐项读回核验，最后清理 completion_pending。"""
    _notify("password_authentication", checkpoint=checkpoint, report=report, message="验证新密码认证会话")
    try:
        verified = validate_password_session(account, email, auth)
    except ProtocolPasswordResetError as error:
        return _failure(error, "password_authentication", "authentication_failed")

    cp = getattr(recovery, "checkpoint", None) or recovery
    recovery_id = getattr(cp, "recovery_id", None)
    expected_version = getattr(cp, "version", None)
    pending = getattr(cp, "completion_pending", True)
    if getattr(cp, "state", "confirmed") != "confirmed":
        return _result(stage="credential_writeback", cause_code="recovery_checkpoint_invalid")
    if pending and (recovery_id is None or expected_version is None):
        return _result(stage="credential_writeback", cause_code="recovery_checkpoint_invalid")
    token, session = verified["access_token"], verified["session"]

    if pending:
        _notify("credential_writeback", checkpoint=checkpoint, report=report, message="保存新会话凭据")
        try:
            save_manual_password_change_session(
                int(recovery_id),
                **dict(owner or {}),
                access_token=token,
                session_info=session,
                protocol_session=auth.get("_protocol_session"),
                auth_method=str(auth.get("auth_method") or ""),
            )
        except Exception as error:
            return _failure(error, "credential_writeback", "credential_writeback_failed")

    failure = _verify_saved_credentials(
        account=account,
        email=email,
        token=token,
        session=session,
        protocol_session=auth.get("_protocol_session"),
        proxy=proxy,
        checkpoint=checkpoint,
        report=report,
    )
    if failure is not None:
        return failure

    if pending:
        _notify("credential_completion", checkpoint=checkpoint, report=report, message="完成改密收尾")
        try:
            complete_manual_password_change(
                int(recovery_id),
                **dict(owner or {}),
                expected_version=int(expected_version),
                access_token=token,
            )
        except Exception as error:
            return _failure(error, "credential_completion", "credential_completion_failed")
    return _success()


def verify_completed_password_reset(
    *,
    account: dict,
    email: str,
    auth: dict,
    proxy=None,
    checkpoint=None,
    report=None,
) -> dict:
    """重跑已完成的改密检查点，只读核验已存凭据和业务身份。"""
    _notify("password_authentication", checkpoint=checkpoint, report=report, message="验证已保存的认证会话")
    try:
        verified = validate_password_session(account, email, auth)
    except ProtocolPasswordResetError as error:
        return _failure(error, "password_authentication", "authentication_failed")
    failure = _verify_saved_credentials(
        account=account,
        email=email,
        token=verified["access_token"],
        session=verified["session"],
        protocol_session=auth.get("_protocol_session"),
        proxy=proxy,
        checkpoint=checkpoint,
        report=report,
    )
    return failure or _success()


__all__ = [
    "ResetCompletionError",
    "ProtocolPasswordResetError",
    "validate_password_session",
    "complete_password_reset",
    "verify_completed_password_reset",
]
