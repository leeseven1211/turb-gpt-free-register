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
    safe_payment_artifact,
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
_AUTOMATIC_PAYMENT_TERMINAL = {
    "PAYMENT_SUCCEEDED", "PAYMENT_FAILED", "PAYMENT_UNCERTAIN",
    "SUBMISSION_UNKNOWN", "CHECKOUT_FAILED", "CANCELED",
}
_AUTOMATIC_PAYMENT_RECONCILE = {"PAYMENT_UNCERTAIN", "SUBMISSION_UNKNOWN"}
_AUTOMATIC_PAYMENT_MESSAGES = {
    "PAYMENT_FAILED": "自动支付已明确失败",
    "PAYMENT_UNCERTAIN": "自动支付结果不确定，需要人工核对",
    "SUBMISSION_UNKNOWN": "自动支付提交结果不确定，需要人工核对",
    "CHECKOUT_FAILED": "提链失败，自动支付未完成",
    "CANCELED": "提链已取消，自动支付未完成",
}
_FAILURE_MESSAGES = {
    "INVALID_SESSION": "未取得可用的结账会话，需检查令牌或会话后端",
    "UNSUPPORTED_CHECKOUT": "当前结账流程或配置不受支持",
    "PROXY_REQUIRED": "缺少必需的代理出口",
    "PROXY_EGRESS_UNAVAILABLE": "代理出口不可用或认证失败",
    "PROXY_EGRESS_CHANGED": "结账过程中代理出口发生变化",
    "PAYMENT_METHOD_UNAVAILABLE": "当前会话或地区不提供所选支付方式",
    "PROMOTION_NOT_ELIGIBLE": "账号不符合指定优惠资格",
    "PROMOTION_NOT_APPLIED": "优惠或结账选项未成功应用",
    "AMOUNT_POLICY_REJECTED": "结账金额超过设置的金额上限",
    "PAYMENT_METHOD_CREATION_FAILED": "支付处理方未创建可用的支付方式",
    "SETUP_INTENT_FAILED": "支付方式设置流程失败",
    "CONFIRM_FAILED": "支付确认失败，需核对支付状态和验证信息",
    "APPROVAL_BLOCKED": "支付授权或审批被阻止",
    "PAYMENT_ARTIFACT_MISSING": "未获得可用支付链接或二维码，需核对支付状态",
    "PROVIDER_REJECTED": "上游服务拒绝当前操作",
    "CHECKOUT_RISK_BLOCKED": "上游结账风控拦截",
    "REQUEST_REJECTED": "上游拒绝结账请求",
    "RATE_LIMITED": "上游限制请求频率",
    "TRANSPORT_FAILURE": "上游网络连接或读写失败",
    "RETRY_EXHAUSTED": "流程重试次数或执行预算已用尽",
    "PROVIDER_ERROR": "上游服务异常或响应缺少必需数据",
    "CANCELED": "平台任务已取消",
    "TIMEOUT": "上游请求或结账流程超时，需核对已有任务与支付状态",
    "UNEXPECTED": "平台发生未归类异常",
}
_PROGRESS_FIELDS = {
    "progressPercent": "percent", "completedSteps": "completed_steps",
    "totalSteps": "total_steps", "runAttempt": "run_attempt", "stepAttempt": "step_attempt",
}
_PLUS_VERIFICATION_STATUSES = {
    "NOT_APPLICABLE", "WAITING_FOR_PAYMENT", "CHECKING", "CONFIRMED", "NOT_CONFIRMED", "CHECK_FAILED",
}
_METADATA_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,119}\Z")
_EVENT_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
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


def _safe_metadata_code(value: object, *, secrets: tuple[str, ...], event: bool = False) -> str:
    """诊断元数据仅接收有界的标识符，不接受任意正文、嵌套对象或凭据。"""
    pattern = _EVENT_NAME_RE if event else _METADATA_CODE_RE
    if not isinstance(value, str) or len(value) > 160:
        return ""
    value = _safe_message(value, secrets=secrets)
    return value if pattern.fullmatch(value) else ""


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
        return self._job(data, payment_state=payment_state, automatic_payment=True)

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
        automatic_payment: bool = False,
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
        for source, target in _PROGRESS_FIELDS.items():
            value = data.get(source)
            upper = 100 if source == "progressPercent" else 1_000_000
            if type(value) is int and 0 <= value <= upper:
                summary[target] = value
        for source, target in (("failureCode", "failure_code"), ("failureType", "failure_type"), ("lastEvent", "last_event")):
            value = _safe_metadata_code(data.get(source), secrets=secrets, event=source == "lastEvent")
            if value:
                summary[target] = value
        if extraction_state == "failed" or payment == "failed":
            code = summary.get("failure_code")
            message = _FAILURE_MESSAGES.get(code, "") if not automatic_payment else ""
            message = message or _failure_message(data, result, secrets=secrets)
            if not message and code:
                message = f"平台提链失败（错误码：{code}）"
            if message:
                summary["failure_message"] = message
        if automatic_payment:
            if remote_status in _AUTOMATIC_PAYMENT:
                summary["automatic_payment_status"] = remote_status
            summary["automatic_payment_terminal"] = remote_status in _AUTOMATIC_PAYMENT_TERMINAL
            summary["automatic_payment_requires_reconcile"] = remote_status in _AUTOMATIC_PAYMENT_RECONCILE
            if remote_status in _AUTOMATIC_PAYMENT_MESSAGES:
                summary["failure_message"] = _AUTOMATIC_PAYMENT_MESSAGES[remote_status]
        current_step = data.get("currentStep")
        if isinstance(current_step, str):
            summary["current_step"] = _safe_message(current_step, secrets=secrets)
        plus_status = data.get("plusVerificationStatus")
        if isinstance(plus_status, str) and plus_status in _PLUS_VERIFICATION_STATUSES:
            summary["plus_verification_status"] = plus_status
        next_sync_at = data.get("nextPaymentStateSyncAt")
        private_data = {}
        if "nextPaymentStateSyncAt" in data and next_sync_at is None:
            private_data["next_payment_state_sync_at"] = None
        elif isinstance(next_sync_at, str) and next_sync_at.strip():
            private_data["next_payment_state_sync_at"] = next_sync_at.strip()[:80]
        payment_artifact = safe_payment_artifact({
            "payment_page_url": result.get("hostedUrl"),
            "payment_url": next(iter(safe_links(
                artifact.get("hostedInstructionsUrl"), artifact.get("url"), artifact.get("processorUrl"),
            )), None),
            "qr_data": artifact.get("data"),
            "qr_image_url_png": artifact.get("imageUrlPng"),
            "qr_image_url_svg": artifact.get("imageUrlSvg"),
            "amount": result.get("amount") if result.get("amount") is not None else artifact.get("amount"),
            "currency": result.get("currency") or artifact.get("currency"),
            "expires_at": artifact.get("expiresAt"),
            "payment_status": data.get("paymentStatus") or result.get("paymentStatus"),
            "platform_plus_status": data.get("plusVerificationStatus"),
        })
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
            payment_artifact=payment_artifact,
            private_data=private_data,
            summary=summary,
        )
