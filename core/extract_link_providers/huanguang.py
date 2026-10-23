from __future__ import annotations

import re
from urllib.parse import urlencode

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


_EXTRACTION = {"QUEUED": "queued", "RUNNING": "running", "DONE": "failed", "ERROR": "failed", "CANCELLED": "failed", "CANCELED": "failed"}
_PAYMENT = {
    "AWAITING_PAYMENT": "pending", "ACTIVATION_PENDING": "pending",
    "COMPLETED": "unknown", "FAILED": "failed", "EXPIRED": "failed",
    "PAYMENT_TIMEOUT": "unknown", "PAYMENT_CHECK_ERROR": "unknown",
    "VERIFICATION_UNAVAILABLE": "unknown",
}
_PAYMENT_CHECK_STATUSES = {"running", "completed", "failed", "expired", "timeout", "error"}
_CDK_STATES = {"queued", "reserved", "consumed", "free_reserved", "reused", "refunded", "pending", "review", "bypassed"}
_URL_RE = re.compile(r"(?i)\b(?:https?|wss?|upi)://[^\s<>\"']+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CREDENTIAL_RE = re.compile(
    r"(?i)\b(cdk|(?:access|refresh)[_ -]?token|token|at|(?:job[_ -]?)?secret|password|authorization|cookie)"
    r"[\"']?\s*[:=：]\s*(?:\"[^\"]*\"|'[^']*'|(?:Bearer\s+)?[^\s,;\"'}]+)"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;\"'}]+")
_CDK_RE = re.compile(r"(?i)\b(?:CDK(?:-[A-Z0-9]{4}){4}|[A-Z]{3}-[A-F0-9]{32})\b")


def _safe_message(value: object, *, secrets: tuple[str, ...]) -> str:
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


def _progress_summary(data: dict, *, secrets: tuple[str, ...]) -> dict:
    summary = {}
    for source, target, maximum in (
        ("percent", "percent", 100), ("queue_position", "queue_position", 1000000),
        ("attempt", "step_attempt", 1000000), ("max_attempts", "max_attempts", 1000000),
    ):
        value = data.get(source)
        if type(value) is int and 0 <= value <= maximum:
            summary[target] = value
    text = _safe_message(data.get("text"), secrets=secrets)
    if text:
        summary["current_step"] = text
    cdk_state = data.get("cdk_state")
    if isinstance(cdk_state, str) and cdk_state in _CDK_STATES:
        summary["cdk_state"] = cdk_state
    return summary


class HuanguangProvider:
    provider_id = "huanguang"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport
        self._secrets: dict[str, str] = {}

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
        if request_data.link_type != "upi":
            raise ProviderError("幻光提链仅支持 UPI")
        if not request_data.entry_proxy or not request_data.exit_proxy:
            raise ProviderError("幻光提链需要已分配的入口和出口代理")
        if request_data.mode == "auto_payment":
            raise ProviderUnsupported()
        body = {
            "token": request_data.access_token,
            "cdk": self.config.cdk,
            "link_type": request_data.link_type,
            "entry_proxies": [request_data.entry_proxy],
            "exit_proxies": [request_data.exit_proxy],
        }
        data = request(self.transport, "POST", "/api/checkout", body=body, timeout=self.config.timeout)
        job_id = data.get("job_id")
        secret = data.get("job_secret")
        if not isinstance(job_id, (str, int)) or not str(job_id).strip() or not isinstance(secret, str) or not secret:
            return ProviderJob(extraction_state="unknown", summary={"outcome": "UNKNOWN"})
        job_id = str(job_id)
        self._secrets[job_id] = secret
        summary = _progress_summary(data, secrets=(self.config.cdk, request_data.access_token, secret))
        summary.update({"remote_status": "QUEUED", "remote_polling": True})
        return ProviderJob(job_id=job_id, extraction_state="queued", private_data={"job_secret": secret}, summary=summary)

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        job_id = str(job_ref)
        secret = private_data.get("job_secret") if isinstance(private_data, dict) else None
        secret = secret if isinstance(secret, str) and secret else self._secrets.get(job_id)
        if not secret:
            raise ProviderError("幻光任务凭证不可用")
        headers = {"X-Pay153-Job-Secret": secret}
        path = "/api/checkout-progress?" + urlencode({"job_id": job_id})
        data = request(self.transport, "GET", path, headers=headers, timeout=self.config.timeout)
        return self._job(data, job_id, secret, secrets=(self.config.cdk,))

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    @staticmethod
    def _job(data, fallback_id, secret, *, secrets=()):
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        secrets = (*secrets, secret)
        raw_status = data.get("status")
        remote_status = raw_status.strip().upper() if isinstance(raw_status, str) else "UNKNOWN"
        remote_status = remote_status if remote_status in _EXTRACTION else "UNKNOWN"
        status = normalize_state(remote_status, _EXTRACTION)
        links = safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"), result.get("qr_data"))
        payment_links = safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"))
        artifact = safe_payment_artifact({
            "payment_page_url": next(iter(payment_links), None),
            "payment_url": next(iter(safe_links(result.get("payment_url"), result.get("hosted_instructions_url"))), None),
            "qr_data": result.get("qr_data"),
            "amount": result.get("amount"), "currency": result.get("currency"),
            "expires_at": result.get("expires_at"),
        })
        for target, sources in (
            ("qr_image_url_png", ("qr_image_png", "image_url_png", "qr_image_url_png")),
            ("qr_image_url_svg", ("qr_image_svg", "image_url_svg", "qr_image_url_svg")),
        ):
            for source in sources:
                image = safe_payment_artifact({target: result.get(source)})
                if image:
                    artifact.update(image)
                    break
        if any(artifact.get(name) for name in (
            "payment_page_url", "payment_url", "qr_data", "qr_image_url_png", "qr_image_url_svg",
        )):
            status = "succeeded"

        summary = _progress_summary(data, secrets=secrets)
        summary["remote_status"] = remote_status
        payment_status = result.get("payment_status")
        payment_status = payment_status.strip().lower() if isinstance(payment_status, str) else ""
        payment_state = normalize_state(payment_status, _PAYMENT) if payment_status else "not_started"
        if payment_status.upper() in _PAYMENT:
            summary["payment_status"] = payment_status
            artifact["payment_status"] = payment_status
        for name in ("entitlement_active", "entitlement_inferred"):
            if type(result.get(name)) is bool:
                summary[name] = result[name]
        directly_verified = (
            payment_status == "completed" and result.get("entitlement_active") is True
            and result.get("plan_type") == "plus" and result.get("has_active_subscription") is True
            and ("entitlement_inferred" not in result or result["entitlement_inferred"] is False)
        )
        if directly_verified:
            payment_state = "succeeded"
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "verified"
        elif result.get("entitlement_inferred") is True:
            payment_state = "unknown"
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "inferred"
        elif payment_status == "completed":
            summary["platform_plus_status"] = artifact["platform_plus_status"] = "unknown"
        check_status = result.get("payment_check_status")
        if isinstance(check_status, str) and check_status in _PAYMENT_CHECK_STATUSES:
            summary["payment_check_status"] = check_status
        summary["remote_polling"] = (
            remote_status in {"QUEUED", "RUNNING"}
            or any(result.get(name) is True for name in ("chongyun_polling", "xxsyun_polling", "seashore_polling"))
            or (check_status == "running" and remote_status not in {"CANCELLED", "CANCELED"})
        )
        if status == "failed":
            summary["remote_terminal_failure"] = True
            message = ""
            for source in (data, result):
                for name in ("error", "message", "detail", "text"):
                    message = _safe_message(source.get(name), secrets=secrets)
                    if message:
                        break
                if message:
                    break
            summary["failure_message"] = message or "幻光任务已结束，但未返回有效支付材料"
        return ProviderJob(
            job_id=str(data.get("id") or fallback_id),
            extraction_state=status,
            payment_state=payment_state,
            links=links,
            payment_links=payment_links,
            payment_artifact=artifact,
            private_data={"job_secret": secret},
            summary=summary,
        )
