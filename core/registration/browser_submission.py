"""浏览器认证提交的最小、可恢复事实。

页面定时器排队和 ``click()`` 返回都不能证明远端收到了请求。本模块只保存
提交阶段和白名单网络元数据，供邮箱、密码和验证码流程共用；不会保存请求体、
Cookie、Token、密码或验证码。
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid
from typing import Any, Mapping


SUBMISSION_PHASES = frozenset({
    "prepared", "dispatch_intent", "ui_queued", "ui_dispatched",
    "request_observed", "response_observed", "confirmed", "rejected",
    "not_dispatched", "unknown", "superseded",
})
_ENDPOINT_KINDS = frozenset({
    "email_submit", "nextauth_csrf", "nextauth_signin", "password_submit",
    "otp_submit", "otp_resend", "auth_redirect", "unknown",
})
_RESULTS = frozenset({"success", "failure", "unknown", "cancelled", "timeout", ""})
_UNRESOLVED_PHASES = frozenset({
    "dispatch_intent", "ui_queued", "ui_dispatched", "request_observed",
    "response_observed", "unknown",
})
_PHASE_PRIORITY = {
    "prepared": 10,
    "dispatch_intent": 20,
    "ui_queued": 30,
    "ui_dispatched": 40,
    "request_observed": 50,
    "response_observed": 60,
    "unknown": 70,
    # 页面确认/明确拒绝是收口事实；CDP 观察事件可能在其后才抵达。
    "not_dispatched": 80,
    # 已确认刷新回到验证码表单后，旧动作可由明确记录的补交替代；不冒充成功或未派发。
    "superseded": 85,
    "rejected": 90,
    "confirmed": 100,
}


def _bounded_text(value: Any, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def _safe_status(value: Any) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    return status if 100 <= status <= 599 else None


@dataclass
class BrowserSubmissionReceipt:
    """一个提交动作的内存回执；``persist`` 由调用方注入，便于兼容旧入口。"""

    kind: str
    stage: str
    submission_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    phase: str = "prepared"
    endpoint_kind: str = "unknown"
    http_method: str = ""
    http_status: int | None = None
    result: str = ""
    error_type: str = ""
    started_at: float = field(default_factory=time.monotonic)
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        self.kind = _bounded_text(self.kind, 40) or "unknown"
        self.stage = _bounded_text(self.stage, 40) or "unknown"
        self.endpoint_kind = self.endpoint_kind if self.endpoint_kind in _ENDPOINT_KINDS else "unknown"
        if self.phase not in SUBMISSION_PHASES:
            raise ValueError(f"未知浏览器提交阶段: {self.phase}")

    def safe_fact(self, *, phase: str | None = None, **changes: Any) -> dict[str, Any]:
        current_phase = phase or self.phase
        if current_phase not in SUBMISSION_PHASES:
            raise ValueError(f"未知浏览器提交阶段: {current_phase}")
        if current_phase == "superseded" and not (
            self.kind in {"otp", "resume_login"} and self.stage == "email_otp"
            and self.endpoint_kind == "otp_submit"
            and changes.get("error_type", self.error_type) == "otp_refresh_retry"
        ):
            raise ValueError("只有验证码刷新后补交可以替代原提交回执")
        method = _bounded_text(changes.get("http_method", self.http_method), 12).upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", ""}:
            method = ""
        result = _bounded_text(changes.get("result", self.result), 20).lower()
        if result not in _RESULTS:
            result = "unknown"
        duration = changes.get("duration_ms", self.duration_ms)
        try:
            duration = max(0, min(900_000, int(duration))) if duration is not None else None
        except (TypeError, ValueError):
            duration = None
        return {
            "submission_id": _bounded_text(self.submission_id, 80),
            "kind": self.kind,
            "stage": self.stage,
            "phase": current_phase,
            "endpoint_kind": self.endpoint_kind,
            "http_method": method,
            "http_status": _safe_status(changes.get("http_status", self.http_status)),
            "result": result,
            "error_type": _bounded_text(changes.get("error_type", self.error_type), 80),
            "duration_ms": duration,
        }

    def transition(self, phase: str, **changes: Any) -> dict[str, Any]:
        fact = self.safe_fact(phase=phase, **changes)
        self.phase = phase
        for name in ("http_method", "http_status", "result", "error_type", "duration_ms"):
            if name in changes:
                setattr(self, name, fact[name] if fact[name] is not None else getattr(self, name))
        if self.duration_ms is None and phase in {"confirmed", "rejected", "not_dispatched", "unknown", "response_observed"}:
            self.duration_ms = max(0, int((time.monotonic() - self.started_at) * 1000))
            fact["duration_ms"] = self.duration_ms
        return fact


def fact_from_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """把 CDP/浏览器回调限制为可落库白名单。"""
    raw = dict(value or {})
    kind = _bounded_text(raw.get("kind"), 40) or "unknown"
    stage = _bounded_text(raw.get("stage"), 40) or "unknown"
    receipt = BrowserSubmissionReceipt(
        kind=kind,
        stage=stage,
        submission_id=_bounded_text(raw.get("submission_id"), 80) or uuid.uuid4().hex,
        endpoint_kind=_bounded_text(raw.get("endpoint_kind"), 40),
        http_method=_bounded_text(raw.get("http_method"), 12),
        http_status=_safe_status(raw.get("http_status")),
        result=_bounded_text(raw.get("result"), 20),
        error_type=_bounded_text(raw.get("error_type"), 80),
        duration_ms=raw.get("duration_ms"),
    )
    return receipt.safe_fact(phase=_bounded_text(raw.get("phase"), 40) or "unknown")


def unresolved_submission_ids(facts: Any) -> set[str]:
    """返回最新阶段仍未收口的提交动作 ID。

    Attempt 的提交事实跨 Run 保留；新 Run 只能观察或核验这些动作，不能因为
    创建了新的浏览器对象就把未知 POST 当成从未发生过。
    验证码刷新补交会保留原未知事实，并用 superseded 记录替代关系后再建立新回执。
    """
    latest: dict[str, tuple[int, str]] = {}
    for item in facts if isinstance(facts, (list, tuple)) else ():
        if not isinstance(item, Mapping):
            continue
        submission_id = _bounded_text(item.get("submission_id"), 80)
        phase = _bounded_text(item.get("phase"), 40)
        if submission_id and phase:
            priority = _PHASE_PRIORITY.get(phase, 0)
            if priority >= latest.get(submission_id, (-1, ""))[0]:
                latest[submission_id] = (priority, phase)
    return {submission_id for submission_id, (_, phase) in latest.items() if phase in _UNRESOLVED_PHASES}


def record_browser_submission_fact(driver: Any, phase: str, *, receipt: BrowserSubmissionReceipt | None = None,
                                   **changes: Any) -> dict[str, Any] | None:
    """用浏览器对象上的注册事实上下文持久化一次提交阶段。

    旧入口没有 Attempt 上下文时返回 ``None``，不阻断其既有流程；一旦有上下文，
    持久化失败会向上抛出，避免在无法建立 dispatch 围栏时继续点击。
    """
    if receipt is None:
        receipt = getattr(driver, "_browser_submission_receipt", None)
    if receipt is None:
        return None
    if phase == "dispatch_intent":
        # CDP request 事件可能晚于页面回执到达；保留本次 Run 已进入派发窗口
        # 的候选集合。观测器无法唯一关联时宁可不补 request_fact，也不能把
        # 迟到的旧请求误绑到当前新提交。
        history = getattr(driver, "_browser_submission_receipts", None)
        if not isinstance(history, list):
            history = []
            try:
                setattr(driver, "_browser_submission_receipts", history)
            except Exception:
                pass
        if all(item is not receipt for item in history):
            history.append(receipt)
            del history[:-32]
    fact = receipt.safe_fact(phase=phase, **changes)
    context = getattr(driver, "_registration_fact_context", None)
    if not isinstance(context, Mapping) or context.get("attempt_id") is None:
        # 没有 Attempt 时仍维护本次进程内的单调回执，供共享 CDP 观测器
        # 做唯一候选判断；持久化失败时不会提前改变内存状态。
        if _PHASE_PRIORITY.get(phase, 0) >= _PHASE_PRIORITY.get(receipt.phase, 0):
            receipt.transition(phase, **changes)
        return fact
    from core.storage import registration

    persisted = registration.record_submission_fact(
        int(context["attempt_id"]),
        run_id=context.get("run_id"), execution_id=context.get("execution_id"),
        job_id=context.get("job_id"), **fact,
    )
    # 先 durable，再推进内存 phase；迟到的低优先级 CDP 事件不能把 confirmed
    # 或 not_dispatched 回退成 request_observed。
    if _PHASE_PRIORITY.get(phase, 0) >= _PHASE_PRIORITY.get(receipt.phase, 0):
        receipt.transition(phase, **changes)
    return persisted


__all__ = [
    "SUBMISSION_PHASES", "BrowserSubmissionReceipt", "fact_from_mapping",
    "unresolved_submission_ids", "record_browser_submission_fact",
]
