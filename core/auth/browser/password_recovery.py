"""浏览器密码恢复的私有检查点会话，不把候选凭据放入任务数据。"""
from __future__ import annotations

import hmac
from collections.abc import Mapping

from core.auth.browser.browser_submission import BrowserSubmissionReceipt, _PHASE_PRIORITY
from core.storage.accounts import password_recovery as store


class PasswordRecoverySession:
    """绑定真实执行归属，所有读取和推进仍经过存储层执行围栏。"""

    def __init__(self, **owner):
        self._owner = dict(owner)
        self._checkpoint: store.PrivateCheckpoint | None = None

    @property
    def checkpoint(self) -> store.PrivateCheckpoint | None:
        return self._checkpoint

    def resume(self) -> bool:
        self._checkpoint = store.resume_password_recovery(**self._owner)
        return self._checkpoint is not None

    def prepare(self, candidate_factory) -> str:
        if self._checkpoint is None:
            self._checkpoint = store.prepare_password_recovery(
                **self._owner, candidate_factory=candidate_factory,
            )
        else:
            self._checkpoint = store.get_password_recovery(self._checkpoint.recovery_id, **self._owner)
        return self._checkpoint.password

    def _transition(self, state: str, confirmation: str | None = None) -> str:
        if self._checkpoint is None:
            raise store.PasswordRecoveryError("checkpoint_missing")
        self._checkpoint = store.transition_password_recovery(
            self._checkpoint.recovery_id, **self._owner,
            expected_version=self._checkpoint.version, state=state, confirmation=confirmation,
        )
        return self._checkpoint.password

    def mark_started(self) -> None:
        self._transition("started")

    def mark_unknown(self) -> None:
        self._transition("unknown")

    def confirm(self, confirmation: str) -> str:
        return self._transition("confirmed", confirmation)

    def confirm_candidate_login(self, driver, *, email: str, password: str,
                                receipt: BrowserSubmissionReceipt, original=None) -> str:
        """只凭当前注册续跑的配对密码认证，在同一事务内正式换密并收口旧登录。"""
        checkpoint = self._checkpoint
        if checkpoint is None:
            raise store.PasswordRecoveryError("checkpoint_missing")
        if (checkpoint.purpose != "registration" or self._owner.get("purpose") != "registration"
                or not all(getattr(checkpoint, key) == self._owner.get(key) for key in (
                    "account_id", "operation_run_id", "operation_execution_id", "attempt_id",
                    "registration_run_id", "registration_execution_id"))
                or str(self._owner.get("email") or "").strip().casefold() != checkpoint.email
                or str(email or "").strip().casefold() != checkpoint.email.casefold()
                or not isinstance(password, str) or not hmac.compare_digest(password.encode(), checkpoint.password.encode())
                or getattr(driver, "_registration_resume_login", False) is not True):
            raise store.PasswordRecoveryError("candidate_login_context_invalid")
        context = getattr(driver, "_registration_fact_context", None)
        if (not isinstance(context, Mapping) or context.get("attempt_id") != checkpoint.attempt_id
                or context.get("run_id") != checkpoint.registration_run_id
                or context.get("execution_id") != checkpoint.registration_execution_id
                or type(context.get("job_id")) is not int or context["job_id"] < 1):
            raise store.PasswordRecoveryError("candidate_login_context_invalid")
        def password_receipt(item):
            return (isinstance(item, BrowserSubmissionReceipt) and item.kind == "resume_login"
                    and item.stage == "login_password" and item.endpoint_kind == "password_submit"
                    and item.http_method == "POST" and bool(item.submission_id))
        request = receipt.request_binding if isinstance(receipt, BrowserSubmissionReceipt) else None
        if (not password_receipt(receipt) or receipt.phase != "confirmed" or receipt.result != "success"
                or type(receipt.http_status) is not int or not 200 <= receipt.http_status < 300
                or not isinstance(request, tuple) or len(request) != 2 or not all(request)
                or request != receipt.response_binding or request[0] != receipt.dispatch_target_id or receipt.auth_error):
            raise store.PasswordRecoveryError("candidate_login_receipt_invalid")
        if original is not None and (not password_receipt(original) or original is receipt
                or original.submission_id == receipt.submission_id
                or original.phase not in {"unknown", "superseded", "rejected", "confirmed", "not_dispatched"}):
            raise store.PasswordRecoveryError("candidate_login_receipt_invalid")
        confirmed = store.transition_password_recovery(
            checkpoint.recovery_id, **self._owner, expected_version=checkpoint.version,
            state="confirmed", confirmation="candidate_login", candidate_login_submission_id=receipt.submission_id,
            candidate_login_original_submission_id=original.submission_id if original is not None else None,
            candidate_login_job_id=context["job_id"],
        )
        # 函数返回意味着数据库已提交；并发迟到终态的优先级高于 superseded。
        self._checkpoint = confirmed
        fact = confirmed.candidate_login_original_fact
        if original is not None and fact and _PHASE_PRIORITY.get(fact["phase"], 0) >= _PHASE_PRIORITY.get(original.phase, 0):
            original.transition(fact["phase"], **{key: fact[key] for key in (
                "result", "error_type", "http_status", "replacement_submission_id") if key in fact})
        return confirmed.password


__all__ = ["PasswordRecoverySession"]
