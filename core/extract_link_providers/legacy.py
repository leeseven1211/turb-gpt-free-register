from __future__ import annotations

from dataclasses import replace
import re
from urllib.parse import quote, urlencode

from core.task_run_log import redact_text

from .contracts import (
    ExtractRequest,
    ProviderError,
    ProviderHTTPError,
    ProviderJob,
    ProviderUnsupported,
    normalize_state,
    request,
    response_dict,
    require_capability,
    safe_links,
    safe_payment_artifact,
)


_EXTRACTION = {"CREATED": "queued", "SUBMITTED": "queued", "QUEUED": "queued", "RUNNING": "running", "DONE": "succeeded", "SUCCESS": "succeeded", "SUCCEEDED": "succeeded", "ERROR": "failed", "FAILED": "failed"}
_CREATE_REJECTION_STATUSES = {400, 401, 402, 403, 404, 409, 413, 422, 429}
_PAYMENT_ORDER_STATES = {
    "PENDING": "pending", "ASSIGNED": "pending", "CHECKING": "pending", "COMPLETED": "succeeded",
    "FAILED": "failed", "CANCELLED": "failed", "EXPIRED": "failed", "NEED_REUPLOAD": "failed",
}
_PAYMENT_ORDER_LABELS = {
    "等待处理": "PENDING", "处理中": "ASSIGNED", "检测中": "CHECKING", "已完成": "COMPLETED",
    "失败": "FAILED", "已取消": "CANCELLED", "已超时": "EXPIRED", "需重传": "NEED_REUPLOAD",
}
_PAYMENT_SUBMISSION_STATES = {
    "not_requested": "not_started", "waiting": "pending", "not_submitted": "not_started",
    "submitting": "pending", "submitted": "pending", "failed": "failed", "unknown": "unknown",
}
_URL_RE = re.compile(r"(?i)\b(?:https?|wss?|upi|socks5h?)://[^\s<>\"']+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(cdk|(?:access|refresh)[_ -]?token|token|at|secret|password|authorization|cookie)"
    r"[\"']?\s*[:=：]\s*(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;\"'}]+)"
)


def _safe_message(value, *, secrets=()):
    if not isinstance(value, str):
        return ""
    for secret in secrets:
        if isinstance(secret, str) and secret:
            value = value.replace(secret, "[REDACTED]")
    value = _CREDENTIAL_RE.sub(r"\1=[REDACTED]", value)
    value = redact_text(value, len(value))
    value = _URL_RE.sub("[REDACTED_URL]", value)
    value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    return " ".join(value.split())[:300]


def _failure_summary(data, *, secrets=()):
    """保留平台给出的具体原因，补充稳定分类并清除公开摘要中的凭据。"""
    error = data.get("error")
    nested = error if isinstance(error, dict) else {}
    raw_code = next((source.get(key) for source in (nested, data)
                     for key in ("code", "failure_code", "error_code")
                     if isinstance(source.get(key), str) and source[key].strip()), "")
    message = next((value for value in (
        nested.get("message"), nested.get("reason"), nested.get("detail"),
        error if isinstance(error, str) else None,
        data.get("failure_message"), data.get("message"), data.get("reason"), data.get("detail"),
    ) if isinstance(value, str) and value.strip()), "虾扯蛋链平台未返回失败细项")
    text = f"{raw_code} {message}".lower()
    failure_type = "remote_task_failed"
    for name, markers in (
        ("payment_confirmation_blocked", ("支付确认被拦截",)),
        ("payment_submission_failed", ("支付提交失败，请稍后重试。",)),
        ("task_in_progress", ("in_progress", "未完成任务", "进行中任务")),
        ("quota_exhausted", ("quota", "余额不足", "次数不足", "次数已用完", "额度不足", "exhausted")),
        ("token_invalid", ("token_expired", "token_invalid", "invalid token", "token 失效", "token 已过期", "at 已过期")),
        ("promotion_unavailable", ("不符合", "无优惠", "优惠未生效", "not eligible", "ineligible", "promotion")),
        ("unsupported", ("unsupported", "not supported", "不支持")),
        ("upstream_timeout", ("timeout", "timed out", "超时")),
        ("upstream_network", ("network", "connection", "网络", "连接失败")),
    ):
        if any(marker in text for marker in markers):
            failure_type = name
            break
    safe_code = raw_code.strip()
    if failure_type == "payment_confirmation_blocked" and safe_code.lower() in {"", "blocked"}:
        safe_code = failure_type
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,99}", safe_code) or any(
        secret and secret in safe_code for secret in secrets
    ):
        safe_code = failure_type
    return {"failure_code": safe_code, "failure_type": failure_type,
            "failure_message": _safe_message(message, secrets=secrets)}


class LegacyQueryRejected(ProviderError):
    """查询权限或参数被拒绝，不代表原远端提链任务失败。"""

    code = "extract_status_query_rejected"

    def __init__(self, summary):
        self.failure_code = summary["failure_code"]
        super().__init__(f"虾扯蛋链状态查询被拒绝（{self.failure_code}）：{summary['failure_message']}")


class LegacyProvider:
    provider_id = "legacy"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport
        self._last_jobs: dict[str, ProviderJob] = {}

    def _require_automatic_payment(self):
        require_capability(self.config, "payment")
        require_capability(self.config, "auto_payment")
        if not self.config.payment_cdk.strip():
            raise ProviderError("虾扯蛋链自动支付未配置支付平台 CDK")

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
        if request_data.mode not in {"extract_only", "manual_payment", "auto_payment"}:
            raise ProviderError("虾扯蛋链提链模式无效")
        private = {"mode": request_data.mode, "link_type": request_data.link_type}
        body = {"link_type": request_data.link_type, "cdk": self.config.cdk, "token": request_data.access_token}
        if request_data.mode == "auto_payment":
            self._require_automatic_payment()
            if request_data.link_type != "upi":
                raise ProviderError("虾扯蛋链自动支付仅支持 UPI")
            body["payment_platform"] = {
                "enabled": True, "platform_id": "xiachedan_plus", "cdk": self.config.payment_cdk,
            }
        if request_data.link_type == "paypal":
            for key in ("paypal_region_selected", "paypal_country", "paypal_currency", "paypal_region"):
                if key in request_data.options:
                    body[key] = request_data.options[key]
        failed = False
        try:
            response = self.transport.request("POST", "/api/extract", json=body, headers={}, timeout=self.config.timeout)
        except ProviderError:
            raise
        except Exception:
            failed = True
        if failed:
            raise ProviderError("虾扯蛋链创建请求失败，结果待确认")
        try:
            status = int(getattr(response, "status_code", 200))
        except (TypeError, ValueError):
            raise ProviderError("虾扯蛋链创建响应状态无效，结果待确认") from None
        if not 200 <= status < 300 and status not in _CREATE_REJECTION_STATUSES:
            raise ProviderHTTPError(status)
        try:
            data = response_dict(response)
        except ProviderError:
            if status not in _CREATE_REJECTION_STATUSES:
                raise
            data = {"error": f"虾扯蛋链拒绝提链请求（HTTP {status}）", "code": f"http_{status}"}
        if status in _CREATE_REJECTION_STATUSES or data.get("ok") is False:
            summary = _failure_summary(data, secrets=(self.config.cdk, self.config.payment_cdk, request_data.access_token))
            return ProviderJob(extraction_state="failed", private_data=private, summary={"outcome": "REJECTED", **summary})
        job_id = data.get("job_id")
        if not isinstance(job_id, (str, int)) or not str(job_id).strip():
            return ProviderJob(extraction_state="unknown", private_data=private, summary={"outcome": "UNKNOWN"})
        job = ProviderJob(
            job_id=str(job_id), extraction_state="queued", private_data=private,
            payment_state="pending" if request_data.mode == "auto_payment" else "not_started",
            summary={"automatic_payment_terminal": False} if request_data.mode == "auto_payment" else {},
        )
        return self._remember(job)

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        previous = self._last_jobs.get(str(job_ref))
        private = {**(previous.private_data if previous else {}), **(private_data or {})}
        # 官网也使用此只读接口恢复最终结果，避免 SSE 的 done 事件覆盖此前的 result。
        path = f"/api/jobs/{quote(str(job_ref), safe='')}?" + urlencode({"cdk": self.config.cdk})
        data = request(self.transport, "GET", path, timeout=self.config.timeout)
        if data.get("ok") is False:
            raise LegacyQueryRejected(_failure_summary(data, secrets=(self.config.cdk, self.config.payment_cdk)))
        return self._remember(self._job(
            data, str(job_ref), secrets=(self.config.cdk, self.config.payment_cdk), private_data=private,
        ))

    def get_automatic_payment_status(self, job_ref: str) -> ProviderJob:
        """仅同步已有订单；未提链或尚待远端提交时不提前查询支付。"""
        self._require_automatic_payment()
        job_ref = str(job_ref)
        previous = self._last_jobs.get(job_ref)
        if previous is None or previous.private_data.get("mode") != "auto_payment":
            raise ProviderError("虾扯蛋链自动支付查询缺少原任务模式，需先恢复原任务状态")
        if previous.private_data.get("link_type", "upi") != "upi":
            raise ProviderError("虾扯蛋链自动支付仅支持 UPI")
        if previous.extraction_state != "succeeded" or previous.payment_state in {"succeeded", "failed"}:
            return previous
        private = previous.private_data
        if private.get("legacy_payment_submission_status") not in {"submitting", "submitted"} and not any(
            private.get(key) for key in ("legacy_payment_order_id", "legacy_payment_order_no")
        ):
            return previous
        data = request(self.transport, "POST", "/api/payment-status", body={
            "job_id": job_ref, "cdk": self.config.cdk, "payment_cdk": self.config.payment_cdk,
        }, timeout=self.config.timeout)
        if data.get("ok") is False:
            raise LegacyQueryRejected(_failure_summary(data, secrets=(self.config.cdk, self.config.payment_cdk)))
        return self._remember(self._job(
            data, job_ref, secrets=(self.config.cdk, self.config.payment_cdk), private_data=private,
        ))

    def _remember(self, job):
        if not job.job_id:
            return job
        previous = self._last_jobs.get(job.job_id)
        if previous:
            summary = {**previous.summary, **job.summary}
            payment_observed = "automatic_payment_status" in job.summary
            confirmed_not_submitted = (
                previous.payment_state == "pending"
                and previous.private_data.get("legacy_payment_submission_status") not in {"submitting", "submitted", "unknown"}
                and job.extraction_state == "failed" and job.payment_state == "not_started"
                and job.summary.get("automatic_payment_status") == "NOT_SUBMITTED"
                and job.summary.get("automatic_payment_terminal") is True
                and not any(job.private_data.get(key) for key in ("legacy_payment_order_id", "legacy_payment_order_no"))
            )
            order_changed = any(
                previous.private_data.get(key) and job.private_data.get(key)
                and previous.private_data[key] != job.private_data[key]
                for key in ("legacy_payment_order_id", "legacy_payment_order_no")
            )
            keep_payment_terminal = previous.payment_state in {"succeeded", "failed"} and not order_changed
            if keep_payment_terminal:
                # 原单查询可能仍是提交时的旧快照，同一订单的已确认终态不能回退。
                for key in ("automatic_payment_status", "automatic_payment_terminal", "failure_code", "failure_type", "failure_message"):
                    if key in previous.summary:
                        summary[key] = previous.summary[key]
            elif order_changed and previous.summary.get("failure_type") in {"payment_order_failed", "payment_submission_failed"}:
                for key in ("failure_code", "failure_type", "failure_message"):
                    if key not in job.summary:
                        summary.pop(key, None)
            if not payment_observed and "automatic_payment_status" in previous.summary:
                summary["automatic_payment_terminal"] = previous.summary.get("automatic_payment_terminal", False)
            job = replace(
                job,
                extraction_state=(previous.extraction_state if job.extraction_state == "unknown"
                                  or previous.extraction_state == "succeeded" else job.extraction_state),
                payment_state=previous.payment_state if keep_payment_terminal or (job.payment_state == "not_started" and not confirmed_not_submitted) or not payment_observed else job.payment_state,
                links=tuple(dict.fromkeys((*previous.links, *job.links))),
                payment_links=tuple(dict.fromkeys((*previous.payment_links, *job.payment_links))),
                payment_artifact={**previous.payment_artifact, **job.payment_artifact},
                private_data={**previous.private_data, **job.private_data},
                summary=summary,
            )
        self._last_jobs[job.job_id] = job
        return job

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    @staticmethod
    def _job(data, fallback_id, *, secrets=(), private_data=None):
        job = data.get("job") if isinstance(data.get("job"), dict) else data
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        links = safe_links(result.get("long_url"), result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"))
        artifact = safe_payment_artifact({
            "payment_page_url": next(iter(links), None),
            "payment_url": result.get("payment_url") or result.get("hosted_instructions_url"),
            "qr_data": result.get("qr_data") or result.get("copy_paste"),
            "qr_image_url_png": result.get("image_url_png") or result.get("qr_image_url_png"),
            "qr_image_url_svg": result.get("image_url_svg") or result.get("qr_image_url_svg"),
            "amount": result.get("amount"), "currency": result.get("currency"),
            "expires_at": result.get("expires_at"),
            "payment_status": result.get("payment_status"),
        })
        has_material = bool(links or any(artifact.get(key) for key in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        )))
        extraction_state = normalize_state(job.get("status"), _EXTRACTION)
        summary = {"percent": job.get("percent") if type(job.get("percent")) is int else None}
        if extraction_state == "unknown" and job.get("done") is True:
            if has_material:
                extraction_state = "succeeded"
            elif job.get("error"):
                extraction_state = "failed"
            else:
                summary.update({
                    "failure_code": "missing_payment_material", "failure_type": "missing_payment_material",
                    "failure_message": "虾扯蛋链任务已结束，但未返回可用支付材料，提链结果待确认",
                })
        if extraction_state == "failed":
            summary.update(_failure_summary(job, secrets=secrets))
            summary["remote_terminal_failure"] = True
        private = dict(private_data or {})
        payment = {}
        for source in (result, job, data):
            if isinstance(source.get("payment_platform"), dict):
                payment.update(source["payment_platform"])
        payment_state, payment_summary, payment_private = LegacyProvider._payment_state(payment, private, secrets=secrets)
        summary.update(payment_summary)
        private.update(payment_private)
        if extraction_state == "failed" and payment_state in {"not_started", "pending"} and not any(
            private.get(key) for key in ("legacy_payment_order_id", "legacy_payment_order_no")
        ):
            summary["automatic_payment_terminal"] = True
        return ProviderJob(
            job_id=str(data.get("job_id") or job.get("job_id") or fallback_id),
            extraction_state=extraction_state,
            payment_state=payment_state,
            links=links,
            payment_links=links,
            payment_artifact=artifact,
            private_data=private,
            summary=summary,
        )

    @staticmethod
    def _payment_state(payment, private, *, secrets=()):
        confirmed_state = private.get("legacy_payment_confirmed_state")
        confirmed_status = private.get("legacy_payment_confirmed_status")
        has_confirmed_state = confirmed_state in {"succeeded", "failed"} and confirmed_status in _PAYMENT_ORDER_STATES
        if not payment and not has_confirmed_state:
            return ("pending", {"automatic_payment_terminal": False}, {}) if private.get("mode") == "auto_payment" else ("not_started", {}, {})
        nested = payment.get("order") if isinstance(payment.get("order"), dict) else {}
        raw_order = payment.get("order_status") or nested.get("status")
        order_status = raw_order.strip().upper() if isinstance(raw_order, str) else ""
        if not order_status:
            order_status = _PAYMENT_ORDER_LABELS.get(payment.get("order_status_label"), "")
        raw_status = payment.get("status")
        status = raw_status.strip().lower() if isinstance(raw_status, str) else "unknown"
        state = (_PAYMENT_ORDER_STATES.get(order_status, "unknown") if order_status
                 else _PAYMENT_SUBMISSION_STATES.get(status, "unknown"))
        details = {"legacy_payment_submission_status": status if status in _PAYMENT_SUBMISSION_STATES else "unknown"}
        for name in ("order_id", "order_no"):
            value = payment.get(name) or nested.get(name) or (nested.get("id") if name == "order_id" else None)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip() and len(str(value)) <= 160:
                details[f"legacy_payment_{name}"] = str(value)
        order_changed = any(
            private.get(f"legacy_payment_confirmed_{name}") and details.get(f"legacy_payment_{name}")
            and private[f"legacy_payment_confirmed_{name}"] != details[f"legacy_payment_{name}"]
            for name in ("order_id", "order_no")
        )
        if has_confirmed_state and not order_changed:
            # 私有恢复数据随任务持久化，进程重启后也保留同订单的已确认终态。
            state, order_status = confirmed_state, confirmed_status
        if order_changed:
            details.update({f"legacy_payment_confirmed_{name}": "" for name in ("state", "status", "order_id", "order_no")})
        summary = {
            "automatic_payment_status": order_status if order_status in _PAYMENT_ORDER_STATES else
                status.upper() if status in _PAYMENT_SUBMISSION_STATES and not order_status else "UNKNOWN",
            "automatic_payment_terminal": state in {"succeeded", "failed"},
        }
        if state == "failed":
            failure = _failure_summary({
                **payment,
                "code": f"payment_order_{order_status.lower()}" if order_status else "payment_submission_failed",
                "failure_message": payment.get("message") or payment.get("order_status_label") or "虾扯蛋链自动支付失败",
            }, secrets=secrets)
            if failure["failure_type"] == "remote_task_failed":
                failure["failure_type"] = "payment_order_failed" if order_status else "payment_submission_failed"
            summary.update(failure)
        if state in {"succeeded", "failed"}:
            details.update({
                "legacy_payment_confirmed_state": state,
                "legacy_payment_confirmed_status": order_status or "FAILED",
            })
            for name in ("order_id", "order_no"):
                details[f"legacy_payment_confirmed_{name}"] = details.get(f"legacy_payment_{name}") or private.get(f"legacy_payment_{name}") or ""
        return state, summary, details
