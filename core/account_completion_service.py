# -*- coding: utf-8 -*-
"""账号管理“补全账号”的纯规划逻辑。

这里只判断账号缺什么、配置允许补什么；真正执行仍由现有的账号操作服务负责。
这样单独操作和组合补全共享同一套缺失判断，不会因为前端按钮不同而产生两套规则。
"""
from __future__ import annotations

import json
from collections.abc import Mapping


STEP_LABELS = {
    "registration_resume": "继续注册",
    "refresh_at": "刷新 AT",
    "password": "账号密码",
    "plan_check": "套餐状态",
    "twofa": "Authenticator 2FA",
    "codex": "Codex",
}


def _extra(account: Mapping) -> dict:
    raw = account.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    return dict(raw) if isinstance(raw, dict) else {}


def _password_present(account: Mapping) -> bool:
    extra = _extra(account)
    return bool(
        str(
            extra.get("account_password")
            or extra.get("login_password")
            or extra.get("registration_password")
            or account.get("password")
            or account.get("login_password")
            or account.get("registration_password")
            or ""
        ).strip()
    )


def _twofa_present(account: Mapping) -> bool:
    if str(account.get("totp_secret") or "").strip():
        return not bool(_extra(account).get("totp_setup_pending"))
    return False


def _token_needs_refresh(account: Mapping) -> bool:
    if not str(account.get("access_token") or "").strip():
        return True
    value = account.get("token_expired")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "expired"}
    return bool(value)


def needs_registration_resume(account: Mapping | None) -> bool:
    """Whether this no-token row is a partially completed registration.

    ``registration_target_status`` comes from the durable RegistrationAttempt
    projection.  The legacy checkpoint in ``extra_json`` remains a fallback for
    older rows and for callers that only have the account record.
    """
    account = account if isinstance(account, Mapping) else {}
    if str(account.get("access_token") or "").strip():
        return False
    extra = _extra(account)
    checkpoint = str(
        account.get("registration_checkpoint")
        or extra.get("registration_checkpoint")
        or ""
    ).strip().lower()
    target_status = str(
        account.get("registration_target_status")
        or account.get("target_status")
        or ""
    ).strip().lower()
    return checkpoint == "email_verification_pending" or target_status == "email_verification_pending"


def _settings(settings: Mapping | None = None) -> dict:
    if settings is not None:
        return dict(settings)
    from config.account import completion_settings

    return completion_settings()


def completion_plan(account: Mapping | None, settings: Mapping | None = None) -> dict:
    """Return configured, missing and blocked steps without exposing secrets."""
    account = account if isinstance(account, Mapping) else {}
    cfg = _settings(settings)
    enabled = {
        "password": bool(cfg.get("password_enabled", True)),
        "plan_check": bool(cfg.get("plan_check_enabled", True)),
        "twofa": bool(cfg.get("twofa_enabled", True)),
        "codex": bool(cfg.get("codex_enabled", True)),
        "refresh_at": bool(cfg.get("refresh_at_enabled", False)),
    }
    missing: list[str] = []
    blocked: list[dict] = []
    registration_resume = needs_registration_resume(account)
    if registration_resume:
        if _password_present(account):
            missing.append("registration_resume")
        else:
            blocked.append({
                "step": "registration_resume",
                "reason": "账号注册尚未完成且缺少已保存密码，不能安全继续注册",
            })
    else:
        if _token_needs_refresh(account):
            if enabled["refresh_at"]:
                missing.append("refresh_at")
            else:
                blocked.append({"step": "refresh_at", "reason": "账号缺少可用 access_token，请先单独执行刷新 AT"})
        if enabled["password"] and not _password_present(account):
            missing.append("password")
        if enabled["plan_check"] and str(account.get("plan_check_status") or "").strip().lower() != "success":
            missing.append("plan_check")
        if enabled["twofa"] and not _twofa_present(account):
            missing.append("twofa")
    execution_state = str(account.get("codex_execution_status") or "").strip().lower()
    legacy_codex_state = str(account.get("codex_status") or "").strip().lower()
    credential_state = str(account.get("codex_credential_state") or "").strip().lower()
    if execution_state in {"queued", "running", "cancelling"}:
        codex_state = execution_state
    elif legacy_codex_state == "success" or credential_state in {"valid", "success"}:
        codex_state = "success"
    else:
        codex_state = legacy_codex_state or credential_state or execution_state
    if not registration_resume and enabled["codex"] and codex_state not in {"success"}:
        missing.append("codex")
    return {
        "enabled": enabled,
        "configured_steps": [step for step in ("password", "plan_check", "twofa", "codex", "refresh_at") if enabled[step]],
        "missing_steps": missing,
        "missing_labels": [STEP_LABELS[step] for step in missing],
        "blocked": blocked,
        "registration_resume": registration_resume,
        "ready": not missing and not blocked,
    }


__all__ = ["STEP_LABELS", "completion_plan", "needs_registration_resume"]
