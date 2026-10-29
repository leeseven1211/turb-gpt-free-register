"""支付联合核验的只读证据规则，供执行和历史状态补齐共用。"""
from __future__ import annotations


def huanguang_scan_completed(state: dict) -> bool:
    """原单已结束扫码，具备发起独立套餐核验的条件。"""
    summary = state.get("summary") or {}
    artifact = state.get("payment_artifact") or {}
    completed = (
        state.get("extraction_state") == "succeeded" and state.get("payment_state") == "unknown"
        and summary.get("automatic_payment_terminal") is True and summary.get("remote_polling") is False
        and summary.get("remote_status") == "DONE"
        and summary.get("remote_terminal_failure") is not True
        and not summary.get("remote_chain_error")
    )
    inferred_complete = (
        artifact.get("payment_status") == "completed" and summary.get("automatic_payment_status") == "COMPLETED"
        and summary.get("platform_plus_status") == "inferred" and summary.get("entitlement_inferred") is True
        and summary.get("entitlement_active") is True and summary.get("payment_check_status") == "completed"
    )
    fallback_complete = (
        summary.get("automatic_payment_status") == "XXSYUN_COMPLETED"
        and summary.get("xxsyun_status") == "completed"
        and artifact.get("payment_status") in {"completed", "verification_unavailable", "payment_check_error"}
    )
    return bool(completed and (inferred_complete or fallback_complete))
