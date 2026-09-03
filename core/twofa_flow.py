# -*- coding: utf-8 -*-
"""Shared 2FA execution-mode and authentication-context planning."""
from __future__ import annotations

from dataclasses import dataclass


VALID_TWOFA_MODES = frozenset({"auto", "protocol", "browser"})
TWOFA_MODE_ALIASES = {
    "protocol_direct": "auto",
    "api": "protocol",
    "http": "protocol",
    "roxy": "browser",
    "roxybrowser": "browser",
}


@dataclass(frozen=True)
class TwofaContextPlan:
    """The executor and context source selected for one 2FA action."""

    mode: str
    executor: str
    auth_source: str
    direct_preferred: bool


def normalize_twofa_mode(value: str | None, default: str = "auto") -> str:
    """Normalize public/legacy values to the three supported 2FA modes."""
    default_mode = str(default or "auto").strip().lower() or "auto"
    default_mode = TWOFA_MODE_ALIASES.get(default_mode, default_mode)
    if default_mode not in VALID_TWOFA_MODES:
        default_mode = "auto"
    raw = default_mode if value is None else str(value or "").strip().lower()
    normalized = TWOFA_MODE_ALIASES.get(raw, raw or default_mode)
    if normalized not in VALID_TWOFA_MODES:
        raise ValueError("2FA 驱动只支持 auto、protocol 或 browser")
    return normalized


def canonical_twofa_executor(mode: str | None) -> str:
    """Return the concrete 2FA executor for a normalized/public mode."""
    return "browser" if normalize_twofa_mode(mode) == "browser" else "protocol"


def plan_twofa_context(
    mode: str | None,
    *,
    has_access_token: bool,
    browser_session_required: bool,
) -> TwofaContextPlan:
    """Choose how to obtain authentication context before executing 2FA.

    ``protocol`` and ``auto`` prefer an existing AT when no browser-only step
    is required.  If a browser session is already required (for example to
    set a password), the browser session supplies the fresh AT and Protocol
    still performs the 2FA API operation.  Without an AT, Protocol reauth is
    the first context source.  Explicit ``browser`` always uses the browser
    security-settings flow.
    """
    normalized = normalize_twofa_mode(mode)
    if normalized == "browser":
        return TwofaContextPlan(normalized, "browser", "browser_session", False)
    if browser_session_required:
        return TwofaContextPlan(normalized, "protocol", "browser_session", False)
    if has_access_token:
        return TwofaContextPlan(normalized, "protocol", "existing_at", True)
    return TwofaContextPlan(normalized, "protocol", "protocol_reauth", False)
