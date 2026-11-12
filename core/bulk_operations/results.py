"""由本轮 Run 与依赖证据构建批量公开结果，不读取账号当前历史成功值。"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from core.operations.presentation import public_result_status
from core.operations.errors import classify_task_error

ACTIVE = {"queued", "running", "waiting", "settling", "cancelling", "stopping"}
TERMINAL = {"success", "partial_success", "failed", "not_executed", "cancelled"}


def _mapping(value) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _countries(value) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not value or len(value) > 256:
        return None
    if any(not isinstance(item, str) or len(item.strip()) != 2 or not item.strip().isascii()
           or not item.strip().isalpha() for item in value):
        return None
    return tuple(sorted({item.strip().upper() for item in value}))


def _timestamp(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
    except (ValueError, OverflowError):
        return None


def _flagged(value) -> bool:
    return value not in (None, False, 0, "", "false", "0")


def _plan_baseline(baseline: Mapping) -> tuple[tuple[str, ...], str] | None:
    """只信名单固定时保存的完整历史成功，缺失国家或旧失败不作比较。"""
    basis = _mapping(baseline.get("plan_check"))
    countries = _countries(basis.get("countries"))
    checked, frozen = _timestamp(basis.get("checked_at")), _timestamp(basis.get("frozen_at"))
    if (basis.get("product") != "plus" or basis.get("status") != "success" or basis.get("ok") is not True
            or _flagged(basis.get("partial")) or _flagged(basis.get("stale"))
            or countries is None or checked is None or frozen is None or checked > frozen):
        return None
    rows = basis.get("country_results")
    if not isinstance(rows, list) or len(rows) != len(countries):
        return None
    witnessed = []
    for raw in rows:
        row = _mapping(raw)
        stamp = _timestamp(row.get("checked_at"))
        country = _countries([row.get("country")])
        if (country is None or row.get("status") != "success" or row.get("ok") is not True
                or _flagged(row.get("stale")) or stamp is None or stamp > frozen):
            return None
        witnessed.extend(country)
    if tuple(sorted(witnessed)) != countries:
        return None
    for raw in basis.get("promotions") or []:
        promotion = _mapping(raw)
        if promotion.get("plan") != "plus":
            continue
        expiry = promotion.get("expires_at")
        expires_at = _timestamp(expiry) if expiry else None
        if (_flagged(promotion.get("stale")) or _flagged(promotion.get("expired"))
                or (expiry and (expires_at is None or expires_at <= frozen))):
            return None
    kind = str(basis.get("plus_offer_kind") or "unknown").strip().lower()
    kind = {"ineligible": "none", "half_price": "discount", "other_discount": "discount"}.get(kind, kind)
    return (countries, kind) if kind in {"none", "free_trial", "discount", "other_promo"} else None


def _state(run: Mapping, dependencies: Sequence[Mapping], runs: Sequence[Mapping]) -> tuple[str, str | None]:
    status = str(run.get("status") or "pending_submit")
    active_dependencies = any(str(item.get("status") or "") in {"waiting", "ready", "running"} for item in dependencies)
    if active_dependencies and status not in {"queued", "running", "cancelling", "stopping"}:
        return "waiting", None
    if status in {"success", "partial_success"} and any(str(item.get("status") or "") in ACTIVE for item in runs):
        return "waiting", None
    summary = _mapping(run.get("result_summary"))
    if status == "deactivated" and summary.get("reason") == "account_deactivated_before_execution":
        return "not_executed", None
    if status == "partial_success" and summary.get("awaiting_steps") and not any(
        item.get("status") == "completed" and str(item.get("parent_run_id")) == str(run.get("id"))
        for item in dependencies
    ):
        # 父任务先保存handoff，再登记依赖；快速子任务结束不能把这个窗口算成账号终态。
        return "waiting", None
    public_status = public_result_status(status, summary)
    if public_status != status:
        return public_status, None
    direct = {"pending_submit", "waiting_account", "queued", "running", *TERMINAL}
    if status in direct:
        return status, None
    mapped = {"pending": "queued", "waiting": "waiting", "settling": "waiting", "debug_paused": "waiting",
              "cancelling": "running", "stopping": "running", "request_unknown": "failed",
              "interrupted": "failed", "unsupported": "not_executed", "skipped": "not_executed",
              "deactivated": "failed", "stopped": "cancelled" if run.get("cancel_requested_at") else "failed"}
    if status in mapped:
        return mapped[status], None
    return "failed", "adapter_status_unmapped"


def _plan(summary: Mapping, state: str, baseline: Mapping) -> dict:
    countries = list(summary.get("plan_check_countries") or [])
    total = int(summary.get("country_total_count") or len(countries) or 0)
    succeeded = int(summary.get("country_success_count") or 0)
    success = state in {"success", "partial_success"} and bool(summary.get("ok"))
    if success and not total:
        total, succeeded = 1, 1
    elif success and summary.get("country_success_count") is None and not summary.get("plan_check_partial") and state == "success":
        succeeded = total
    full = success and total > 0 and succeeded == total and not summary.get("plan_check_partial")
    kind = str(summary.get("plus_promo_kind") or "unknown") if success else "unknown"
    if kind in {"none", "ineligible"} and not full:
        kind = "unknown"
    if kind == "ineligible":
        kind = "none"
    outcome = ("pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"}
               else "success" if full else "partial_success" if success
               else "not_executed" if state in {"not_executed", "cancelled"} else "failed")
    comparison = "not_comparable"
    basis = _plan_baseline(baseline) if full and kind != "unknown" else None
    if basis is not None and basis[0] == _countries(countries):
        old = basis[1]
        comparison = "unchanged" if old == kind else "new_offer" if old == "none" and kind not in {"none", "unknown"} else "offer_removed" if kind == "none" else "changed"
    return {"query_outcome": outcome, "countries_requested": countries,
            "country_success_count": succeeded if success else 0, "country_failed_count": max(0, total - succeeded) if success else total,
            "account_plan_type": summary.get("current_plan_type") if success else None,
            "plus_offer_kind": kind, "confirmed_no_offer": full and kind == "none", "comparison": comparison,
            "country_failures": [{key: item.get(key) for key in ("country", "error_code", "http_status", "stage")}
                                 for item in summary.get("country_failures") or [] if isinstance(item, Mapping)]}


def project_one(evidence: Mapping, *, operation_key: str | None = None, schema_version: int = 1) -> dict:
    key = operation_key or str(evidence.get("operation_key") or evidence.get("action_key") or "")
    runs = [_mapping(value) for value in evidence.get("runs") or evidence.get("owned_runs") or []]
    run = _mapping(evidence.get("run"))
    if not run and runs:
        root_runs = [value for value in runs if value.get("relation") in {None, "owned_root", "owned_continuation"}]
        run = max(root_runs or runs, key=lambda value: (int(value.get("generation") or 0), int(value.get("id") or value.get("run_id") or 0)))
    if not run:
        run = {"status": evidence.get("state") or evidence.get("admission_state") or "pending_submit"}
    dependencies = [_mapping(value) for value in evidence.get("dependencies") or []]
    state, contract_error = _state(run, dependencies, runs)
    summary = _mapping(run.get("result_summary") or evidence.get("result_summary"))
    data = _mapping(run.get("data"))
    baseline = _mapping(evidence.get("baseline"))
    receipt = _mapping(data.get("remote_intent"))
    receipt_state = receipt.get("receipt_state") or summary.get("remote_receipt_state")
    if key == "plan_check":
        result = _plan(summary, state, baseline)
        if state == "success" and result["query_outcome"] != "success":
            state, contract_error = "failed", "plan_result_confirmation_missing"
    elif key == "token_refresh":
        # 刷新成功必须来自本轮重新认证、远端回执和写回读回确认；旧AT在线校验不算刷新。
        confirmed = (state == "success" and data.get("force_refresh") is True and summary.get("ok") is True
                     and receipt.get("action") == "token_refresh" and receipt_state == "confirmed"
                     and summary.get("validation_method") != "access_token"
                     and not summary.get("reconcile_required") and not summary.get("manual_reconcile"))
        if state == "success" and not confirmed:
            state, contract_error = "failed", "refresh_confirmation_missing"
        outcome = ("success" if confirmed else "pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"}
                       else "not_executed" if state in {"not_executed", "cancelled"} else "failed")
        result = {"refresh_outcome": outcome,
                  "confirmation": "confirmed" if confirmed else "not_executed" if outcome == "not_executed" else "pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"} else "failed",
                  "validation_method": summary.get("validation_method"),
                  "refresh_driver": summary.get("token_refresh_driver") or summary.get("live_check_driver"),
                  "protocol_version": summary.get("protocol_version"),
                  "token_expired": summary.get("token_expired") if confirmed else None,
                  "needs_live_check": summary.get("needs_live_check") if confirmed else None,
                  "receipt_state": receipt_state,
                  "failure_stage": summary.get("failure_stage") or run.get("progress_stage")}
    elif key in {"password_setup", "twofa_setup"}:
        step = "password" if key == "password_setup" else "twofa"
        step_receipts = summary.get("setup_step_receipts") or {}
        step_receipt = (_mapping(step_receipts.get(step)) if isinstance(step_receipts, Mapping)
                        else next((_mapping(item) for item in step_receipts if isinstance(item, Mapping) and item.get("step") == step), {}))
        step_confirmed = step_receipt.get("confirmed") is True or (
            step_receipt.get("ok") is True and step_receipt.get("receipt_state") == "confirmed")
        confirmed = state == "success" and (receipt_state == "confirmed" or step_confirmed)
        if state == "success" and not confirmed:
            state, contract_error = "failed", "setup_confirmation_missing"
        result = {"confirmation": "confirmed" if confirmed else "not_executed" if state == "not_executed" else "pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"} else "failed",
                  "change_kind": "not_recorded", "failure_stage": summary.get("failure_stage") or run.get("progress_stage")}
        if key == "password_setup":
            result.update(before_state="candidate" if baseline.get("has_password") else "missing",
                          after_state="confirmed" if confirmed else "pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"} else "failed")
        if key == "twofa_setup":
            result["material_state"] = "usable" if confirmed else "pending"
    elif key == "codex_retry":
        confirmed = state == "success" and (summary.get("credential_confirmed") or summary.get("confirmed") or receipt_state == "confirmed")
        if state == "success" and not confirmed:
            state, contract_error = "failed", "codex_credential_confirmation_missing"
        result = {"attempt_outcome": state, "credential_confirmation": "confirmed" if confirmed else "pending" if state in ACTIVE or state in {"pending_submit", "waiting_account"} else "failed",
                  "receipt_state": receipt_state,
                  "asset_state_before": baseline.get("codex_credential_state", "unknown"),
                  "asset_state_after": "valid" if confirmed or summary.get("existing_valid") else "pending_confirmation" if summary.get("callback_submitted") else "unknown",
                  "existing_asset_preserved": bool(summary.get("existing_valid") or summary.get("existing_asset_preserved"))}
    elif key == "account_completion":
        required = list(summary.get("required_steps") or data.get("required_steps") or data.get("configured_steps") or [])
        completed = list(summary.get("completed_steps") or [])
        blocked = list(summary.get("blocked") or data.get("blocked") or [])
        satisfied = (summary.get("ready") is True and not blocked and set(required) <= set(completed))
        if state == "success" and not satisfied:
            state, contract_error = "failed", "completion_confirmation_missing"
        result = {"required_steps": required, "completed_steps": completed,
                  "pending_steps": [step for step in required if step not in completed],
                  "blocked_steps": blocked,
                  "goal_satisfied": state == "success" and satisfied,
                  "dependencies_active": state == "waiting" or any(value.get("status") in {"waiting", "ready", "running"} for value in dependencies)}
    else:
        state, contract_error, result = "failed", "adapter_operation_unmapped", {}
    reason_code = contract_error or evidence.get("reason_code") or run.get("error_code") or summary.get("cause_code")
    if state in {"failed", "partial_success"} and not reason_code:
        reason_code = "diagnostic_cause_unresolved"
    reason = {"code": reason_code, "stage": summary.get("failure_stage") or run.get("progress_stage"),
              "scope": "data_contract" if contract_error else "operation"} if reason_code else None
    if reason is not None and state in {"failed", "partial_success"}:
        info = classify_task_error(run.get("error_message") or reason_code, stage=reason["stage"] or "",
                                   task_type=key, error_code=str(reason_code or ""),
                                   result_summary=summary, task_status=state) or {}
        reason.update(code=info.get("code") or reason_code, summary=info.get("summary"),
                      display_code=info.get("display_code"), stage=info.get("stage") or reason["stage"])
        if "failure_stage" in result:
            result["failure_stage"] = reason["stage"]
    dimensions = {}
    if key == "plan_check":
        if result.get("confirmed_no_offer"):
            dimensions["account.confirmed_no_offer"] = 1
        plan = result.get("account_plan_type")
        if plan in {"free", "plus", "pro", "team", "go"}:
            dimensions[f"account.plan.{plan}"] = 1
        if result.get("plus_offer_kind") not in {None, "unknown"}:
            dimensions[f"account.plus_offer.{result['plus_offer_kind']}"] = 1
        if state in TERMINAL and (result.get("country_success_count") or result.get("country_failed_count")):
            dimensions["country_query.success"] = result.get("country_success_count", 0)
            dimensions["country_query.failed"] = result.get("country_failed_count", 0)
        if state in TERMINAL:
            dimensions[f"account.comparison.{result['comparison']}"] = 1
    elif key == "token_refresh" and result.get("refresh_outcome") in {"success", "failed"}:
        metric = "confirmed" if result["refresh_outcome"] == "success" else result["refresh_outcome"]
        dimensions[f"account.token_refresh.{metric}"] = 1
    elif key in {"password_setup", "twofa_setup"} and result.get("confirmation") == "confirmed":
        dimensions[f"account.{key}.confirmed"] = 1
    elif key == "codex_retry" and result.get("credential_confirmation") == "confirmed":
        dimensions["account.codex.credential_confirmed"] = 1
    elif key == "account_completion":
        for step in result["completed_steps"]:
            dimensions[f"step.{step}.confirmed"] = 1
        for step in result["pending_steps"]:
            dimensions[f"step.{step}.pending"] = 1
    return {"target_round_id": evidence.get("target_round_id") or evidence.get("id"),
            "schema": f"{key}.v{schema_version}", "source_revision": evidence.get("source_revision", 0),
            "state": state, "source_status": public_result_status(run.get("status"), summary), "terminal": state in TERMINAL,
            "reason": reason, "result": result, "contribution": {"state": state, "dimensions": dimensions},
            "actions": {"retry": {"available": state in TERMINAL, "mode": "automatic"}}}


def project_many(evidence: Sequence[Mapping], *, operation_key: str | None = None, schema_version: int = 1) -> list[dict]:
    return [project_one(item, operation_key=operation_key, schema_version=schema_version) for item in evidence]
