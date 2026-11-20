# -*- coding: utf-8 -*-
"""Shared 2FA execution-mode and authentication-context planning."""
from __future__ import annotations

from dataclasses import dataclass

from contracts.operation_drivers import (
    TWOFA_MODE_ALIASES as TWOFA_MODE_ALIASES,
    VALID_TWOFA_MODES as VALID_TWOFA_MODES,
    canonical_twofa_executor as canonical_twofa_executor,
    normalize_twofa_mode as normalize_twofa_mode,
)


@dataclass(frozen=True)
class TwofaContextPlan:
    """The executor and context source selected for one 2FA action."""

    mode: str
    executor: str
    auth_source: str
    direct_preferred: bool


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
