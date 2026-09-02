# -*- coding: utf-8 -*-
"""Safe, public-facing fingerprint summaries.

The summary is an observation of a BrowserSession.  It deliberately contains
no account identifier, email, token, cookie, device ID, session ID, proxy URL,
or response body.  Raw correlation values belong to the private auth context
store and are never accepted by this module's public summary contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_SUMMARY_FIELDS = frozenset({
    "schema_version",
    "source",
    "profile_version",
    "profile_ref",
    "browser_family",
    "browser_os",
    "browser_version",
    "user_agent",
    "accept_language",
    "navigator_language",
    "navigator_languages",
    "timezone_iana",
    "timezone_offset_minutes",
    "screen_width",
    "screen_height",
    "device_pixel_ratio",
    "hardware_concurrency",
    "device_memory",
    "js_heap_size_limit",
    "geo_country",
    "geo_timezone",
    "proxy_mode",
    "transport_profile",
    "observed_at",
})


def _text(value: Any, limit: int = 240) -> str:
    return str(value or "")[:limit]


def clean_safe_fingerprint_summary(summary: dict | None) -> dict[str, Any]:
    """Normalize a summary through the allowlist before persistence or display."""
    if not isinstance(summary, dict):
        return {}
    clean: dict[str, Any] = {}
    for key in _SUMMARY_FIELDS:
        if key not in summary or summary[key] is None:
            continue
        value = summary[key]
        if key == "navigator_languages":
            if isinstance(value, (list, tuple)):
                clean[key] = [_text(item, 32) for item in list(value)[:8] if str(item or "").strip()]
            continue
        if key in {
            "schema_version", "profile_version", "timezone_offset_minutes", "screen_width", "screen_height",
            "hardware_concurrency", "device_memory", "js_heap_size_limit",
        }:
            try:
                clean[key] = int(value)
            except (TypeError, ValueError):
                continue
            continue
        clean[key] = _text(value)
    return clean


def build_safe_fingerprint_summary(
    session,
    *,
    source: str,
    profile_version: int | None = None,
    profile_ref: str | None = None,
    route: dict | None = None,
    transport_profile: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Build the common P0 summary from an existing session without side effects."""
    profile = getattr(session, "browser_profile", {}) or {}
    geo = getattr(session, "exit_geo", {}) or {}
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(geo, dict):
        geo = {}
    route = route if isinstance(route, dict) else {}
    summary = {
        "schema_version": 1,
        "source": _text(source, 32),
        "profile_version": profile_version,
        "profile_ref": profile_ref,
        "browser_family": profile.get("browser_family"),
        "browser_os": profile.get("browser_os"),
        "browser_version": profile.get("chrome_major") or profile.get("safari_version"),
        "user_agent": profile.get("user_agent"),
        "accept_language": profile.get("accept_language"),
        "navigator_language": profile.get("navigator_language"),
        "navigator_languages": profile.get("navigator_languages"),
        "timezone_iana": profile.get("timezone_iana"),
        "timezone_offset_minutes": profile.get("timezone_offset_minutes"),
        "screen_width": profile.get("screen_width"),
        "screen_height": profile.get("screen_height"),
        "device_pixel_ratio": profile.get("device_pixel_ratio"),
        "hardware_concurrency": profile.get("hardware_concurrency"),
        "device_memory": profile.get("device_memory"),
        "js_heap_size_limit": profile.get("js_heap_size_limit"),
        "geo_country": geo.get("country") or geo.get("country_code"),
        "geo_timezone": geo.get("timezone"),
        "proxy_mode": route.get("proxy_mode"),
        "transport_profile": transport_profile,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return clean_safe_fingerprint_summary(summary)


def safe_fingerprint_summary_text(summary: dict | None) -> str:
    """Render a compact stable text form for an account list or task summary."""
    value = clean_safe_fingerprint_summary(summary)
    if not value:
        return ""
    browser = "/".join(
        item for item in (value.get("browser_family"), value.get("browser_version"), value.get("browser_os"))
        if item
    )
    screen = "x".join(
        str(value[key]) for key in ("screen_width", "screen_height") if value.get(key) is not None
    )
    parts = [
        f"source={value.get('source')}" if value.get("source") else "",
        f"profile={value.get('profile_ref')}" if value.get("profile_ref") else "",
        f"browser={browser}" if browser else "",
        f"screen={screen}@{value.get('device_pixel_ratio')}" if screen and value.get("device_pixel_ratio") is not None else "",
        f"cpu={value.get('hardware_concurrency')}" if value.get("hardware_concurrency") is not None else "",
        f"memory={value.get('device_memory')}GB" if value.get("device_memory") is not None else "",
        f"language={value.get('navigator_language')}" if value.get("navigator_language") else "",
        f"timezone={value.get('timezone_iana')}" if value.get("timezone_iana") else "",
        f"geo={value.get('geo_country')}" if value.get("geo_country") else "",
        f"proxy={value.get('proxy_mode')}" if value.get("proxy_mode") else "",
        f"transport={value.get('transport_profile')}" if value.get("transport_profile") else "",
    ]
    return " ".join(item for item in parts if item)


__all__ = [
    "build_safe_fingerprint_summary",
    "clean_safe_fingerprint_summary",
    "safe_fingerprint_summary_text",
]
