"""从本次浏览器提交回执投影密码结果，不改变认证行为。"""
from __future__ import annotations

from collections.abc import Collection

from core.auth.browser.browser_submission import BrowserSubmissionReceipt


def _password_receipts(driver) -> list[BrowserSubmissionReceipt]:
    history = getattr(driver, "_browser_submission_receipts", None)
    receipts = list(history) if isinstance(history, (list, tuple)) else []
    current = getattr(driver, "_browser_submission_receipt", None)
    if isinstance(current, BrowserSubmissionReceipt) and all(current is not item for item in receipts):
        receipts.append(current)
    return [item for item in receipts if isinstance(item, BrowserSubmissionReceipt)
            and item.endpoint_kind == "password_submit" and item.http_method == "POST"]


def password_receipt_ids(driver) -> frozenset[str]:
    """标记调用前已存在的回执，避免把旧密码验证投影成本轮成功。"""
    return frozenset(item.submission_id for item in _password_receipts(driver))


def password_evidence(driver, *, exclude_ids: Collection[str] = ()) -> dict:
    """返回低敏枚举；页面确认、明确拒绝与未知派发分别记录。"""
    receipts = [item for item in _password_receipts(driver) if item.submission_id not in exclude_ids]
    if not receipts:
        return {"credential_check": "skipped", "submitted": False}
    # 后续表单只准备但未提交时，仍保留本轮最后一次实际派发的结果。
    dispatched = [item for item in receipts if item.phase not in {"prepared", "not_dispatched"}]
    receipt = (dispatched or receipts)[-1]
    submitted = receipt.phase not in {"prepared", "not_dispatched"}
    status = "unknown" if submitted else "skipped"
    http_failed = type(receipt.http_status) is int and not 200 <= receipt.http_status < 300
    error_code = receipt.auth_error.get("code") if isinstance(receipt.auth_error, dict) else None
    explicit_rejection = (error_code in {"incorrect_password", "invalid_password"}
                          or receipt.error_type == "PasswordRejectedError")
    if submitted and explicit_rejection:
        status = "rejected"
    elif (receipt.phase == "confirmed" and receipt.result == "success" and not http_failed
          and not receipt.auth_error):
        status = {"login_password": "verified", "password_create": "accepted"}.get(receipt.stage, "unknown")
    return {
        "credential_check": status,
        "submitted": submitted,
        "stage": receipt.stage,
        "http_method": receipt.http_method,
        "http_status": receipt.http_status,
        "response_observed": receipt.response_binding is not None,
    }
