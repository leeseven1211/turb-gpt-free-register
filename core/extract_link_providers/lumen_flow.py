from __future__ import annotations

import re
from urllib.parse import quote

from core.task_run_log import redact_text

from .contracts import (
    ExtractRequest,
    ProviderError,
    ProviderJob,
    ProviderUnsupported,
    normalize_state,
    request,
    require_capability,
    safe_links,
)


_EXTRACTION = {
    "QUEUED": "queued",
    "RUNNING": "running",
    "AWAITING_BLIK_CODE": "running",
    "SUCCEEDED": "succeeded",
    "FAILED": "failed",
    "CANCELED": "failed",
}
_PAYMENT = {
    "PENDING": "pending",
    "REQUIRES_ACTION": "pending",
    "REQUIRES_CONFIRMATION": "pending",
    "PROCESSING": "pending",
    "SUCCEEDED": "succeeded",
    "CANCELED": "failed",
    "REQUIRES_PAYMENT_METHOD": "failed",
    "FAILED": "failed",
    "UNKNOWN": "unknown",
}
_AUTOMATIC_PAYMENT = {
    "CHECKOUT_RUNNING": "pending",
    "PAYMENT_READY": "pending",
    "PAYMENT_SUBMITTING": "pending",
    "PAYMENT_PENDING": "pending",
    "PAYMENT_SUCCEEDED": "succeeded",
    "PAYMENT_FAILED": "failed",
    "PAYMENT_UNCERTAIN": "unknown",
    "SUBMISSION_UNKNOWN": "unknown",
    "CHECKOUT_FAILED": "failed",
    "CANCELED": "failed",
}
_OPTION_FIELDS = {
    "payment_method": "paymentMethodType",
    "processing_mode": "processingMode",
    "plan_name": "planName",
    "promo_code": "promoCode",
    "max_amount_cents": "maxAmountCents",
    "apply_promotion": "applyPromotion",
    "promotion_campaign_id": "promotionCampaignId",
}
_URL_RE = re.compile(r"(?i)\b(?:https?|wss?|upi)://[^\s<>\"']+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(cdk|access[_ -]?token|refresh[_ -]?token|token|password|secret|authorization|cookie)"
    r"[\"']?\s*[:=：]\s*(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;\"'}]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;\"'}]+")
_CDK_RE = re.compile(r"(?i)\b[A-Z]{3}-[A-F0-9]{32}\b")


def _safe_message(value: object, *, secrets: tuple[str, ...] = ()) -> str:
    if not isinstance(value, str):
        return ""
    text = value
    for secret in secrets:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, "[REDACTED]")
    text = _CREDENTIAL_RE.sub(r"\1=[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    text = redact_text(text, len(text))
    text = _URL_RE.sub("[REDACTED_URL]", text)
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _CDK_RE.sub("[REDACTED_CDK]", text)
    return " ".join(text.split())[:300]


def _failure_message(*sources: dict, secrets: tuple[str, ...] = ()) -> str:
    """只保留失败原因文本，不把完整平台响应带入公开摘要。"""
    for source in sources:
        for key in ("error", "errorMessage", "failureReason", "message", "reason", "detail"):
            value = source.get(key)
            if isinstance(value, dict):
                value = next((
                    value.get(name) for name in ("message", "errorMessage", "reason", "detail", "description")
                    if isinstance(value.get(name), str) and value.get(name).strip()
                ), None)
            message = _safe_message(value, secrets=secrets)
            if message:
                return message
    return ""


class LumenFlowProvider:
    provider_id = "lumen_flow"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
        item = {
            "cdk": self.config.cdk,
            "accessToken": request_data.access_token,
            "paymentMethodType": str(
                request_data.options.get("payment_method") or request_data.link_type or ""
            ).strip().upper(),
        }
        for source, target in _OPTION_FIELDS.items():
            if source in request_data.options:
                item[target] = request_data.options[source]
        if request_data.mode == "auto_payment":
            require_capability(self.config, "payment")
            if item.get("paymentMethodType", "").upper() != "MOMO":
                raise ProviderError("Lumen 自动支付仅支持 MOMO")
            item["automaticMomoPayment"] = True
        data = request(self.transport, "POST", "/public/api/checkout/flow/submit-batch", body={"requests": [item]}, timeout=self.config.timeout)
        results = data.get("results")
        row = results[0] if isinstance(results, list) and results and isinstance(results[0], dict) else {}
        outcome = row.get("outcome")
        task = row.get("task") if isinstance(row.get("task"), dict) else {}
        if outcome not in {"ACCEPTED", "REUSED"}:
            state = "failed" if outcome == "REJECTED" else "unknown"
            summary = {"outcome": outcome if outcome in {"REJECTED", "UNKNOWN"} else "UNKNOWN"}
            if state == "failed":
                message = _failure_message(row, task, secrets=(self.config.cdk, request_data.access_token))
                if message:
                    summary["failure_message"] = message
            return ProviderJob(extraction_state=state, summary=summary)
        return self._job(task, secrets=(request_data.access_token,))

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        data = request(self.transport, "GET", f"/public/api/checkout/flow/{quote(str(job_ref), safe='')}", timeout=self.config.timeout)
        return self._job(data, expected_job_id=str(job_ref))

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    def sync_payment_state(self, job_ref: str) -> ProviderJob:
        require_capability(self.config, "payment")
        path = f"/public/api/checkout/flow/{quote(str(job_ref), safe='')}/sync-payment-state"
        data = request(self.transport, "POST", path, body=None, timeout=self.config.timeout)
        return self._job(data)

    def get_automatic_payment_status(self, job_ref: str) -> ProviderJob:
        require_capability(self.config, "payment")
        path = f"/public/api/checkout/flow/{quote(str(job_ref), safe='')}/momo-payment"
        data = request(self.transport, "GET", path, timeout=self.config.timeout)
        payment_state = normalize_state(data.get("status"), _AUTOMATIC_PAYMENT)
        return self._job(data, payment_state=payment_state)

    def sync_plus_verification(self, job_ref: str, access_token: str) -> ProviderJob:
        require_capability(self.config, "payment")
        if not isinstance(access_token, str) or not access_token.strip():
            raise ProviderError("Plus 同步需要原始访问令牌")
        path = f"/public/api/checkout/flow/{quote(str(job_ref), safe='')}/sync-plus-verification"
        data = request(
            self.transport,
            "POST",
            path,
            body={"accessToken": access_token},
            timeout=self.config.timeout,
        )
        return self._job(data, secrets=(access_token,))

    def _job(
        self, data: dict, *, payment_state: str | None = None,
        secrets: tuple[str, ...] = (), expected_job_id: str | None = None,
    ) -> ProviderJob:
        if expected_job_id is not None:
            for key in ("taskId", "checkoutTaskId"):
                value = data.get(key)
                if value is None or value == "":
                    continue
                if isinstance(value, bool) or not isinstance(value, (str, int)):
                    raise ProviderError("流光状态响应的任务编号无效")
                if str(value) != expected_job_id:
                    raise ProviderError("流光状态响应的任务编号与请求不一致")
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        artifact = result.get("paymentArtifact") if isinstance(result.get("paymentArtifact"), dict) else {}
        payment = payment_state or normalize_state(
            data.get("paymentStatus") or result.get("paymentStatus"), _PAYMENT
        )
        summary = {}
        secrets = (self.config.cdk, *secrets)
        remote_status = data.get("status")
        remote_status = remote_status.strip().upper() if isinstance(remote_status, str) else ""
        if remote_status in _EXTRACTION:
            summary["remote_status"] = remote_status
        if remote_status in {"FAILED", "CANCELED"}:
            summary["remote_terminal_failure"] = True
        extraction_state = normalize_state(data.get("status"), _EXTRACTION)
        if extraction_state == "failed" or payment == "failed":
            message = _failure_message(data, result, secrets=secrets)
            if message:
                summary["failure_message"] = message
        for key in ("currentStep", "plusVerificationStatus"):
            value = data.get(key)
            if isinstance(value, str):
                summary["current_step" if key == "currentStep" else "plus_verification_status"] = _safe_message(value, secrets=secrets)
        next_sync_at = data.get("nextPaymentStateSyncAt")
        private_data = {}
        if isinstance(next_sync_at, str) and next_sync_at.strip():
            private_data["next_payment_state_sync_at"] = next_sync_at.strip()[:80]
        return ProviderJob(
            job_id=str(data.get("taskId") or data.get("checkoutTaskId") or expected_job_id) if data.get("taskId") or data.get("checkoutTaskId") or expected_job_id else None,
            extraction_state=extraction_state,
            payment_state=payment,
            links=safe_links(result.get("paymentUrl"), result.get("checkoutUrl"), result.get("shortLink")),
            payment_links=safe_links(
                result.get("hostedUrl"),
                artifact.get("url"),
                artifact.get("processorUrl"),
                artifact.get("hostedInstructionsUrl"),
            ),
            private_data=private_data,
            summary=summary,
        )
