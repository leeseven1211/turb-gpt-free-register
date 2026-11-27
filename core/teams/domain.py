"""Team 本地预检的纯规则，不读写数据库或远端。"""
from __future__ import annotations

from collections.abc import Mapping

CATEGORIES = ("unavailable", "another_team", "already_member", "same_team_active",
              "missing_auth", "resume_invite", "new")
ACTIVE_STATUSES = frozenset({"queued", "running", "waiting", "cancelling", "settling", "stopping"})


def classify(state: Mapping | None, expected_email: str | None = None) -> tuple[str, str | None]:
    """按契约优先级分类，保证一个目标只落入一个统计桶。"""
    if not state or not state.get("id"):
        return "unavailable", "account_not_found"
    if expected_email is not None and str(state.get("email") or "").strip(" ").lower() != expected_email.strip(" ").lower():
        return "unavailable", "account_identity_changed"
    if state.get("account_unavailable"):
        return "unavailable", "account_unavailable"
    if state.get("other_teams"):
        return "another_team", "already_in_another_team"
    if state.get("already_member"):
        return "already_member", "already_member"
    if state.get("active_invitation"):
        return "same_team_active", None
    if state.get("auth_capability") == "missing":
        return "missing_auth", "missing_auth_materials"
    invitation = state.get("invitation") or {}
    if invitation.get("invitation_state") == "pending":
        return "resume_invite", None
    return "new", None


def capacity(facts: Mapping, *, additional_required: int | None,
             eligible_count: int) -> dict:
    """已购为零仍是明确上限；等待同步或容量不阻断持久受理。"""
    purchased = facts.get("purchased_seats")
    planned = facts.get("planned_member_limit")
    if purchased is not None:
        basis = "purchased_seats"
        limit = purchased if planned is None else min(purchased, planned)
    elif planned is not None:
        basis, limit = "planned_member_limit", planned
    else:
        basis, limit = "unavailable", None
    occupied = facts.get("occupied_count")
    reason = "team_limit_required" if limit is None else (
        "no_eligible_targets" if not eligible_count else None)
    return {
        "basis": basis, "purchased_seats": purchased, "planned_member_limit": planned,
        "effective_limit": limit, "occupied_count": occupied,
        "available_count": max(0, limit - occupied) if limit is not None and occupied is not None else None,
        "additional_required": additional_required,
        "can_submit": reason is None, "blocking_reason_code": reason,
    }


def preview(account_ids: list[str], states: Mapping[int, Mapping], facts: Mapping,
            expected_emails: Mapping[str, str] | None = None) -> dict:
    unique = list(dict.fromkeys(account_ids))
    expected = expected_emails or {}
    counts = {f"{name}_count": 0 for name in CATEGORIES}
    additional = 0
    for account_id in unique:
        state = states.get(int(account_id))
        category, _ = classify(state, expected.get(account_id))
        counts[f"{category}_count"] += 1
        if category in {"new", "resume_invite", "same_team_active"}:
            invitation = (state or {}).get("invitation") or {}
            if not ((state or {}).get("already_occupied") or (state or {}).get("reservation_active") or
                    invitation.get("invitation_state") == "pending" or
                    invitation.get("membership_state") == "joined"):
                additional += 1
    counts.update(
        requested_count=len(account_ids), unique_count=len(unique),
        duplicate_count=len(account_ids) - len(unique),
        eligible_count=sum(counts[f"{name}_count"] for name in
                           ("new", "resume_invite", "same_team_active")),
    )
    return {
        "counts": counts,
        "capacity": capacity(facts, additional_required=(
            None if additional and facts.get("occupied_count") is None else additional
        ), eligible_count=counts["eligible_count"]),
        "requires_sync": facts.get("occupied_count") is None,
    }
