# -*- coding: utf-8 -*-
"""Read and persist the account-level Roxy Profile binding."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
import re


def _account_extra(account: Mapping | None) -> dict:
    if not isinstance(account, Mapping):
        return {}
    raw = account.get("extra_json") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw = {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _roxy_binding(account: Mapping | None) -> Mapping | None:
    extra_binding = _account_extra(account).get("roxybrowser")
    if isinstance(extra_binding, Mapping):
        return extra_binding
    direct_binding = account.get("roxybrowser") if isinstance(account, Mapping) else None
    return direct_binding if isinstance(direct_binding, Mapping) else None


def account_profile_id(account: Mapping | None) -> str:
    """Return a retained account Profile ID, or empty when none is usable."""
    binding = _roxy_binding(account)
    if binding is None:
        return ""
    retained = binding.get("retained", True)
    if isinstance(retained, str) and retained.strip().lower() in {"0", "false", "no", "off"}:
        return ""
    if retained is False or retained == 0:
        return ""
    return str(binding.get("profile_id") or "").strip()


def last_account_profile_id(account: Mapping | None) -> str:
    """Return the last recorded Profile ID without checking reusability."""
    binding = _roxy_binding(account)
    if binding is None:
        return ""
    return str(binding.get("profile_id") or "").strip()


def _profile_window_name(binding: Mapping | None) -> str:
    """Read the safe Roxy window name from a binding or its open response."""
    if not isinstance(binding, Mapping):
        return ""
    candidates: list[object] = [
        binding.get("window_name"),
        binding.get("windowName"),
        binding.get("name"),
        binding.get("profileName"),
    ]
    open_result = binding.get("open_result")
    if isinstance(open_result, Mapping):
        candidates.extend([
            open_result.get("window_name"),
            open_result.get("windowName"),
            open_result.get("name"),
            open_result.get("profileName"),
        ])
        data = open_result.get("data")
        if isinstance(data, Mapping):
            candidates.extend([
                data.get("windowName"),
                data.get("window_name"),
                data.get("name"),
                data.get("profileName"),
            ])
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value[:200]
    return ""


def last_account_profile_name(account: Mapping | None) -> str:
    """Return the last recorded Roxy window name, independent of retention."""
    return _profile_window_name(_roxy_binding(account))


def last_account_profile(account: Mapping | None) -> dict[str, str]:
    """Return the display-safe last Profile ID and Roxy window name."""
    return {
        "profile_id": last_account_profile_id(account),
        "window_name": last_account_profile_name(account),
    }


def load_historical_profile_bindings(project_root: str | Path | None = None) -> dict[str, dict[str, str]]:
    """Load historical Profile IDs and window names without making them reusable.

    The structured registration export wins over log fallbacks when the same
    email appears in both sources.  Only the display-safe ID and window name
    are returned; raw Roxy responses stay local to the source data.
    """
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[3]
    bindings: dict[str, dict[str, str]] = {}
    export_path = root / "core" / "注册成功的邮箱.json"
    try:
        rows = json.loads(export_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        rows = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        raw = row.get("extra_json") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = {}
        if not isinstance(raw, Mapping):
            continue
        email = str(row.get("email") or "").strip().lower()
        if not email:
            user = raw.get("user")
            email = str(user.get("email") or "").strip().lower() if isinstance(user, Mapping) else ""
        binding = raw.get("roxybrowser")
        profile_id = str(binding.get("profile_id") or "").strip() if isinstance(binding, Mapping) else ""
        window_name = _profile_window_name(binding)
        if email and profile_id:
            bindings[email] = {
                "profile_id": profile_id,
                "window_name": window_name,
            }

    log_pattern = re.compile(r"\[Roxy注册\] 开始：([^，\s]+)，profile=([^\s]+)")
    for log_path in sorted((root / "core" / "注册日志").glob("*.log")):
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for email, profile_id in log_pattern.findall(text):
            normalized_email = str(email or "").strip().lower()
            normalized_profile = str(profile_id or "").strip()
            if normalized_email and normalized_profile:
                bindings.setdefault(normalized_email, {
                    "profile_id": normalized_profile,
                    "window_name": "",
                })
    return bindings


def load_historical_profile_ids(project_root: str | Path | None = None) -> dict[str, str]:
    """Load historical Profile IDs without treating them as reusable bindings.

    The structured registration export wins over log fallbacks when the same
    email appears in both sources.  This function only returns identifiers;
    callers decide whether and how to persist them.
    """
    return {
        email: binding["profile_id"]
        for email, binding in load_historical_profile_bindings(project_root).items()
        if binding.get("profile_id")
    }


def backfill_account_profile_ids(profile_ids: Mapping[str, str | Mapping]) -> dict[str, int]:
    """Persist historical IDs and names as non-reusable display-only bindings."""
    from core import db

    result = {
        "candidates": 0,
        "matched_accounts": 0,
        "already_recorded": 0,
        "updated": 0,
        "window_names_updated": 0,
        "missing_accounts": 0,
        "failed": 0,
    }
    for raw_email, raw_profile in profile_ids.items():
        email = str(raw_email or "").strip().lower()
        if isinstance(raw_profile, Mapping):
            raw_profile_id = raw_profile.get("profile_id")
            window_name = _profile_window_name(raw_profile)
        else:
            raw_profile_id = raw_profile
            window_name = ""
        profile_id = str(raw_profile_id or "").strip()
        if not email or not profile_id:
            continue
        result["candidates"] += 1
        account = db.get_account_by_email(email)
        if not account:
            result["missing_accounts"] += 1
            continue
        result["matched_accounts"] += 1
        recorded_profile_id = last_account_profile_id(account)
        if recorded_profile_id:
            result["already_recorded"] += 1
            if (
                recorded_profile_id == profile_id
                and window_name
                and not last_account_profile_name(account)
            ):
                try:
                    if db.update_account_roxy_profile_window_name(email, window_name):
                        result["window_names_updated"] += 1
                    else:
                        result["failed"] += 1
                except Exception:
                    result["failed"] += 1
            continue
        try:
            if db.update_account_roxy_profile(email, profile_id, retained=False):
                result["updated"] += 1
                if window_name:
                    if db.update_account_roxy_profile_window_name(email, window_name):
                        result["window_names_updated"] += 1
                    else:
                        result["failed"] += 1
            else:
                result["failed"] += 1
        except Exception:
            result["failed"] += 1
    return result


def account_profile_id_by_email(email: str, *, strict: bool = False) -> str:
    """Load only the account Profile ID needed by a browser operation.

    ``strict`` prevents a storage outage from being mistaken for an account
    with no binding, which would otherwise consume another Roxy create slot.
    """
    address = str(email or "").strip()
    if not address:
        return ""
    try:
        from core import db

        return account_profile_id(db.get_account_by_email(address))
    except Exception:
        if strict:
            raise
        return ""


def persist_account_profile_id(email: str, profile_id: str, *, retained: bool = True) -> bool:
    """Persist the Profile binding without replacing account credentials."""
    address = str(email or "").strip()
    profile = str(profile_id or "").strip()
    if not address or not profile:
        return False
    from core import db

    return bool(db.update_account_roxy_profile(address, profile, retained=retained))


__all__ = [
    "account_profile_id",
    "last_account_profile_id",
    "last_account_profile_name",
    "last_account_profile",
    "load_historical_profile_bindings",
    "load_historical_profile_ids",
    "backfill_account_profile_ids",
    "account_profile_id_by_email",
    "persist_account_profile_id",
]
