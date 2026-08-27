# -*- coding: utf-8 -*-
"""Pure post-processing and recovery decisions for registration attempts.

This module intentionally has no database, provider, browser, or thread-pool
dependencies.  It is a boundary contract for workflow C while the Attempt /
Run / Checkpoint storage API is being finalized by workflow B.  Callers pass
plain mappings and can adapt the eventual storage rows without introducing a
second persistence model here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


# Public action identifiers.  The legacy registration service currently uses
# shorter values ("codex" / "twofa"); adapters can map these identifiers when
# B's Attempt/Run API is wired in without changing the decision rules.
REGISTRATION_NEW = "registration_new"
REGISTRATION_RESUME = "registration_resume"
REGISTRATION_RECONCILE = "registration_reconcile"
POSTPROCESS = "postprocess"
RETRY_TWOFA = "retry_twofa"
RETRY_CODEX = "retry_codex"
PLAN_CHECK = "plan_check"

POSTPROCESS_ACTIONS = ("twofa", "codex", "plan_check")
_RETRYABLE_POSTPROCESS_STATUSES = {"pending", "failed", "stopped", "interrupted"}
_SUCCESSFUL_POSTPROCESS_STATUSES = {"success", "skipped"}

_ACTION_BY_STAGE = {
    "twofa": RETRY_TWOFA,
    "codex": RETRY_CODEX,
    "plan_check": PLAN_CHECK,
}
_ACTION_REASON = {
    "twofa": "Authenticator 2FA 尚未完成，可在同一账号上补跑",
    "codex": "Codex OAuth 尚未完成，可在同一账号上补跑",
    "plan_check": "套餐状态尚未确认，可在同一账号上补查",
}


def _status(value: Any, *, default: str = "pending") -> str:
    text = str(value or "").strip().lower()
    if not text:
        return default
    # Existing task/progress code uses queued for work that has not started.
    return "pending" if text == "queued" else text


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


@dataclass(frozen=True)
class PostprocessResult:
    """Normalized result for one independent post-processing capability."""

    stage: str
    status: str = "pending"
    ok: bool = False
    message: str | None = None
    error: str | None = None

    @classmethod
    def from_value(cls, stage: str, value: Any) -> "PostprocessResult":
        """Normalize current service dictionaries without invoking services.

        ``value`` is deliberately treated as an untrusted result snapshot;
        secrets and provider-specific payloads are not copied into this model.
        """
        normalized_stage = str(stage or "").strip().lower()
        if normalized_stage not in POSTPROCESS_ACTIONS:
            raise ValueError(f"未知后处理阶段: {stage!r}")
        if isinstance(value, PostprocessResult):
            return value
        if isinstance(value, Mapping):
            raw_status = _status(value.get("status"), default="")
            raw_ok = bool(value.get("ok"))
            if not raw_status:
                raw_status = "success" if raw_ok else "failed"
            ok = raw_ok or raw_status in _SUCCESSFUL_POSTPROCESS_STATUSES
            return cls(
                stage=normalized_stage,
                status=raw_status,
                ok=ok,
                # Do not copy provider-specific ``detail`` payloads: current
                # services may put response metadata or credentials there.
                message=_text(value.get("message")),
                error=_text(value.get("error") or value.get("message") if not ok else None),
            )
        if isinstance(value, bool):
            return cls(
                stage=normalized_stage,
                status="success" if value else "failed",
                ok=value,
            )
        if value is None:
            return cls(stage=normalized_stage)
        return cls(
            stage=normalized_stage,
            status="failed",
            ok=False,
            error=f"无法解析后处理结果: {type(value).__name__}",
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a small compatibility projection for operation events/UI."""
        return {
            "stage": self.stage,
            "status": self.status,
            "ok": self.ok,
            "message": self.message,
            "error": self.error,
        }

    @property
    def needs_retry(self) -> bool:
        return self.status in _RETRYABLE_POSTPROCESS_STATUSES

    @property
    def completed(self) -> bool:
        return self.status in _SUCCESSFUL_POSTPROCESS_STATUSES


@dataclass(frozen=True)
class NextAction:
    """A server-side action the caller may expose to an operator."""

    action: str
    reason: str
    retryable: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class PostprocessSummary:
    """Registration core and account-readiness projection.

    ``registration_core_status`` never depends on a post-processing result.
    This is the key invariant that lets a 2FA/Codex/plan failure become a
    partial account outcome instead of rolling the registration back.
    """

    registration_core_status: str
    account_readiness: str
    results: tuple[PostprocessResult, ...]
    next_actions: tuple[NextAction, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "registration_core_status": self.registration_core_status,
            "account_readiness": self.account_readiness,
            "postprocess": {result.stage: result.as_dict() for result in self.results},
            "next_actions": [action.as_dict() for action in self.next_actions],
        }


def _normalized_results(
    outcomes: Mapping[str, Any] | None,
    *,
    twofa_required: bool,
    codex_enabled: bool,
    plan_check_required: bool,
) -> tuple[PostprocessResult, ...]:
    raw = outcomes if isinstance(outcomes, Mapping) else {}
    required = {
        "twofa": twofa_required,
        "codex": codex_enabled,
        "plan_check": plan_check_required,
    }
    results: list[PostprocessResult] = []
    for stage in POSTPROCESS_ACTIONS:
        if not required[stage]:
            results.append(
                PostprocessResult(
                    stage=stage,
                    status="skipped",
                    ok=True,
                    message="该后处理能力未启用",
                )
            )
        else:
            results.append(PostprocessResult.from_value(stage, raw.get(stage)))
    return tuple(results)


def next_actions_for_postprocess(
    *,
    core_success: bool,
    outcomes: Mapping[str, Any] | None = None,
    twofa_required: bool = True,
    codex_enabled: bool = False,
    plan_check_required: bool = True,
) -> tuple[NextAction, ...]:
    """Return explicit retry actions without reading or writing persistence.

    The function only emits post-processing actions after the registration
    core is confirmed.  A missing required result is treated as ``pending``;
    an active ``running`` result is left alone so recovery can reconcile it.
    """
    if not core_success:
        return ()
    results = _normalized_results(
        outcomes,
        twofa_required=twofa_required,
        codex_enabled=codex_enabled,
        plan_check_required=plan_check_required,
    )
    actions: list[NextAction] = []
    for result in results:
        if result.needs_retry:
            actions.append(
                NextAction(
                    action=_ACTION_BY_STAGE[result.stage],
                    reason=result.error or result.message or _ACTION_REASON[result.stage],
                )
            )
    return tuple(actions)


def summarize_postprocess(
    *,
    core_success: bool,
    password_present: bool,
    outcomes: Mapping[str, Any] | None = None,
    twofa_required: bool = True,
    codex_enabled: bool = False,
    plan_check_required: bool = True,
    account_deactivated: bool = False,
) -> PostprocessSummary:
    """Compute core/readiness independently from post-processing outcomes."""
    results = _normalized_results(
        outcomes,
        twofa_required=twofa_required,
        codex_enabled=codex_enabled,
        plan_check_required=plan_check_required,
    )
    actions = next_actions_for_postprocess(
        core_success=core_success,
        outcomes={result.stage: result for result in results},
        twofa_required=twofa_required,
        codex_enabled=codex_enabled,
        plan_check_required=plan_check_required,
    )
    if account_deactivated:
        readiness = "deactivated"
    else:
        readiness_requirements = (password_present,)
        for result in results:
            if result.stage in {"twofa", "plan_check"}:
                readiness_requirements += (result.completed,)
        readiness = "ready" if core_success and all(readiness_requirements) else "incomplete"
    return PostprocessSummary(
        registration_core_status="success" if core_success else "failed",
        account_readiness=readiness,
        results=results,
        next_actions=actions,
    )


@dataclass(frozen=True)
class RecoveryDecision:
    """Pure restart decision derived from a storage-neutral snapshot."""

    action: str
    email_lease: str
    proxy_lease: str
    safe_to_start_new_registration: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "email_lease": self.email_lease,
            "proxy_lease": self.proxy_lease,
            "safe_to_start_new_registration": self.safe_to_start_new_registration,
            "reason": self.reason,
        }


def _snapshot(snapshot: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(snapshot, Mapping):
        return default
    return snapshot.get(key, default)


def decide_recovery(snapshot: Mapping[str, Any] | None) -> RecoveryDecision:
    """Choose a safe restart action from semantic Attempt facts.

    The mapping keys are deliberately an adapter contract, not a database
    schema.  Workflow B can map its final Attempt/Run/Checkpoint row into:
    ``checkpoint``, ``remote_identity_state``, ``remote_account_state``,
    ``local_account_state``, ``email_resume_capability``, ``has_password``,
    ``has_access_token``, ``account_id`` and optional ``active_execution``.
    Unknown or missing values fail closed to reconciliation.
    """
    checkpoint = _status(_snapshot(snapshot, "checkpoint"), default="unknown")
    remote_identity = _status(_snapshot(snapshot, "remote_identity_state"), default="unknown")
    remote_account = _status(_snapshot(snapshot, "remote_account_state"), default="unknown")
    local_account = _status(_snapshot(snapshot, "local_account_state"), default="none")
    capability = str(_snapshot(snapshot, "email_resume_capability", "manual_only") or "manual_only").strip().lower()
    has_password = bool(_snapshot(snapshot, "has_password", False))
    has_token = bool(_snapshot(snapshot, "has_access_token", False))
    account_id = _snapshot(snapshot, "account_id")
    active_execution = bool(_snapshot(snapshot, "active_execution", False))

    if active_execution:
        return RecoveryDecision(
            action="none",
            email_lease="retain",
            proxy_lease="retain",
            safe_to_start_new_registration=False,
            reason="仍有活动执行者，恢复流程不得抢占 Attempt 或资源租约",
        )

    # A persisted core account is already the registration result.  Recovery
    # may schedule independent post-processing, never a second registration.
    if (
        checkpoint in {"core_persisted", "postprocessing", "completed"}
        or (has_token and account_id is not None and local_account in {"persisted", "saved"})
    ):
        return RecoveryDecision(
            action=POSTPROCESS,
            email_lease="retain",
            proxy_lease="release",
            safe_to_start_new_registration=False,
            reason="注册核心已持久化，仅恢复 2FA/Codex/套餐等后处理",
        )

    # A token observed before core persistence is a conservative reconcile
    # case: the caller must idempotently complete core persistence first.
    if checkpoint == "token_obtained" or has_token:
        return RecoveryDecision(
            action=REGISTRATION_RECONCILE,
            email_lease="quarantine",
            proxy_lease="release",
            safe_to_start_new_registration=False,
            reason="已观察到 Token 但核心账号关联未确认，先对账后处理，禁止重新注册",
        )

    irreversible = {
        "password_request_started",
        "password_confirmed",
        "otp_started",
        "otp_confirmed",
        "account_request_started",
        "account_confirmed",
        "manual_reconcile",
        "legacy_unknown",
    }
    remote_unknown = {"request_unknown", "confirmed", "rejected"}
    if (
        checkpoint in {"manual_reconcile", "legacy_unknown"}
        or remote_identity in {"request_unknown", "rejected"}
        or remote_account in remote_unknown
        or checkpoint in {"account_request_started", "account_confirmed"}
    ):
        return RecoveryDecision(
            action=REGISTRATION_RECONCILE,
            email_lease="quarantine",
            proxy_lease="release",
            safe_to_start_new_registration=False,
            reason="已越过不可逆边界或远端结果未知，只能同 Attempt 对账",
        )

    recoverable_email = capability in {"durable_reconnect", "api_reconnect"}
    if checkpoint in irreversible or remote_identity != "not_started":
        if has_password and recoverable_email:
            return RecoveryDecision(
                action=REGISTRATION_RESUME,
                email_lease="retain",
                proxy_lease="release",
                safe_to_start_new_registration=False,
                reason="同一邮箱和已保存恢复上下文可用，继续同 Attempt 完成注册",
            )
        return RecoveryDecision(
            action=REGISTRATION_RECONCILE,
            email_lease="quarantine",
            proxy_lease="release",
            safe_to_start_new_registration=False,
            reason="已越过不可逆边界但缺少可恢复邮箱或密码，只能人工对账",
        )

    # New registration is allowed only when both remote targets and the local
    # account are explicitly untouched.  Missing/unknown facts never enter
    # this branch.
    pre_boundary = {"created", "email_claimed", "auth_started"}
    if (
        checkpoint in pre_boundary
        and remote_identity == "not_started"
        and remote_account == "not_started"
        and local_account in {"none", "not_started"}
        and not has_token
        and account_id is None
    ):
        return RecoveryDecision(
            action=REGISTRATION_NEW,
            email_lease="release",
            proxy_lease="release",
            safe_to_start_new_registration=True,
            reason="明确确认尚未发出不可逆请求，可释放资源并重新注册",
        )

    return RecoveryDecision(
        action=REGISTRATION_RECONCILE,
        email_lease="quarantine",
        proxy_lease="release",
        safe_to_start_new_registration=False,
        reason="Attempt 状态不完整或未知，默认进入人工对账",
    )


# TODO(B): once the Attempt/Run/Checkpoint contract is frozen, add a narrow
# adapter in workflow C that maps B's storage rows into ``decide_recovery`` and
# maps ``PostprocessSummary.next_actions`` to persisted next_actions.  Do not
# call storage from this module or infer Attempt identity from email alone.


__all__ = [
    "PLAN_CHECK",
    "POSTPROCESS",
    "POSTPROCESS_ACTIONS",
    "REGISTRATION_NEW",
    "REGISTRATION_RECONCILE",
    "REGISTRATION_RESUME",
    "RETRY_CODEX",
    "RETRY_TWOFA",
    "NextAction",
    "PostprocessResult",
    "PostprocessSummary",
    "RecoveryDecision",
    "decide_recovery",
    "next_actions_for_postprocess",
    "summarize_postprocess",
]
