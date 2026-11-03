# -*- coding: utf-8 -*-
"""Shared protocol-version selection for protocol-capable account steps."""
from __future__ import annotations

import os

from config import openai_protocol


VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})
DEFAULT_PROTOCOL_VERSION = "v1"

# A step only consults the global version when multiple implementations exist.
# Browser steps are intentionally absent: they do not use the Protocol version.
PROTOCOL_STEP_CAPABILITIES = {
    "registration": frozenset({"v1"}),
    "twofa": frozenset({"v1"}),
    "plan_check": frozenset({"v1"}),
    "live_check": frozenset({"v1"}),
    "refresh_at": frozenset({"v1", "v2", "v3"}),
    "codex_oauth": frozenset({"v1"}),
}


def normalize_protocol_version(value: str | None, default: str = DEFAULT_PROTOCOL_VERSION) -> str:
    """将公开协议版本规范化为 v1、v2 或 v3。"""
    fallback = str(default or DEFAULT_PROTOCOL_VERSION).strip().lower()
    if fallback in {"1", "v_1"}:
        fallback = "v1"
    elif fallback in {"2", "v_2"}:
        fallback = "v2"
    elif fallback in {"3", "v_3"}:
        fallback = "v3"
    if fallback not in VALID_PROTOCOL_VERSIONS:
        fallback = DEFAULT_PROTOCOL_VERSION

    raw = fallback if value is None else str(value or "").strip().lower()
    normalized = {
        "1": "v1",
        "v_1": "v1",
        "2": "v2",
        "v_2": "v2",
        "3": "v3",
        "v_3": "v3",
    }.get(raw, raw or fallback)
    if normalized not in VALID_PROTOCOL_VERSIONS:
        raise ValueError("协议版本只支持 v1、v2 或 v3")
    return normalized


def configured_protocol_version() -> str:
    """Read the hot-reloadable shared Protocol version configuration."""
    # Existing deployments may still have only the old refresh selector in
    # their .env.  Translate that value once at the compatibility boundary;
    # a new OPENAI_PROTOCOL_VERSION always takes precedence.
    configured = os.getenv("OPENAI_PROTOCOL_VERSION")
    if configured is not None:
        return normalize_protocol_version(configured)
    legacy_refresh = str(os.getenv("ACCOUNT_TOKEN_REFRESH_DRIVER") or "").strip().lower()
    if legacy_refresh == "protocol_v2":
        return "v2"
    if legacy_refresh in {"legacy", "current", "protocol", "protocol_current"}:
        return "v1"
    return normalize_protocol_version(
        getattr(openai_protocol, "OPENAI_PROTOCOL_VERSION", DEFAULT_PROTOCOL_VERSION)
    )


def resolve_protocol_version(step: str, requested: str | None = None) -> str:
    """Resolve a step's effective version from its declared capabilities.

    A single-version step always uses that implementation.  Only a step with
    multiple versions follows the global configuration or an explicit
    normalized request.
    """
    step_name = str(step or "").strip().lower()
    try:
        supported = PROTOCOL_STEP_CAPABILITIES[step_name]
    except KeyError as exc:
        raise ValueError(f"未声明协议能力的步骤: {step_name or '-'}") from exc
    if not supported:
        raise ValueError(f"步骤不使用协议版本: {step_name or '-'}")
    if len(supported) == 1:
        return next(iter(supported))
    return normalize_protocol_version(
        configured_protocol_version() if requested is None else requested
    )


__all__ = [
    "DEFAULT_PROTOCOL_VERSION",
    "PROTOCOL_STEP_CAPABILITIES",
    "VALID_PROTOCOL_VERSIONS",
    "configured_protocol_version",
    "normalize_protocol_version",
    "resolve_protocol_version",
]
