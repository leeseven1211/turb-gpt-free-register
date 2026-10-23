from __future__ import annotations

from urllib.parse import urlencode

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


_EXTRACTION = {"QUEUED": "queued", "RUNNING": "running", "DONE": "succeeded", "SUCCESS": "succeeded", "SUCCEEDED": "succeeded", "ERROR": "failed", "FAILED": "failed"}


class LegacyProvider:
    provider_id = "legacy"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
        body = {"link_type": request_data.link_type, "cdk": self.config.cdk, "token": request_data.access_token}
        if request_data.link_type == "paypal":
            for key in ("paypal_region_selected", "paypal_country", "paypal_currency", "paypal_region"):
                if key in request_data.options:
                    body[key] = request_data.options[key]
        data = request(self.transport, "POST", "/api/extract", body=body, timeout=self.config.timeout)
        job_id = data.get("job_id")
        if not isinstance(job_id, (str, int)) or not str(job_id).strip():
            return ProviderJob(extraction_state="unknown", summary={"outcome": "UNKNOWN"})
        return ProviderJob(job_id=str(job_id), extraction_state="queued")

    def get_status(self, job_ref: str, *, private_data: dict | None = None) -> ProviderJob:
        require_capability(self.config, "extract")
        path = f"/api/jobs/{str(job_ref)}/events?" + urlencode({"cdk": self.config.cdk})
        try:
            events = self.transport.events(path, timeout=self.config.timeout)
            latest = None
            for _, event in events:
                if isinstance(event, dict):
                    latest = event
            if not isinstance(latest, dict):
                return ProviderJob(job_id=str(job_ref), extraction_state="unknown")
            return self._job(latest, str(job_ref))
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Legacy 提链状态查询失败") from None

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    @staticmethod
    def _job(data, fallback_id):
        job = data.get("job") if isinstance(data.get("job"), dict) else data
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        return ProviderJob(
            job_id=str(data.get("job_id") or job.get("job_id") or fallback_id),
            extraction_state=normalize_state(job.get("status"), _EXTRACTION),
            links=safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url")),
            payment_links=safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url")),
            payment_artifact=safe_payment_artifact({
                "payment_page_url": next(iter(safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"))), None),
                "payment_url": result.get("payment_url") or result.get("hosted_instructions_url"),
                "qr_data": result.get("qr_data"),
                "qr_image_url_png": result.get("image_url_png") or result.get("qr_image_url_png"),
                "qr_image_url_svg": result.get("image_url_svg") or result.get("qr_image_url_svg"),
                "amount": result.get("amount"), "currency": result.get("currency"),
                "expires_at": result.get("expires_at"),
                "payment_status": result.get("payment_status"),
            }),
            summary={"percent": job.get("percent") if isinstance(job.get("percent"), int) else None},
        )
