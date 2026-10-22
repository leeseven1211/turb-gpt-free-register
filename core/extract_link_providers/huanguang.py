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
)


_EXTRACTION = {"QUEUED": "queued", "RUNNING": "running", "DONE": "succeeded", "ERROR": "failed", "CANCELLED": "failed", "CANCELED": "failed"}


class HuanguangProvider:
    provider_id = "huanguang"

    def __init__(self, config, transport):
        self.config, self.transport = config, transport
        self._secrets: dict[str, str] = {}

    def create_job(self, request_data: ExtractRequest) -> ProviderJob:
        require_capability(self.config, "extract")
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
        return ProviderJob(job_id=job_id, extraction_state="queued", private_data={"job_secret": secret})

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
        return self._job(data, job_id, secret)

    def start_payment(self, job_ref: str, options: dict) -> ProviderJob:
        require_capability(self.config, "payment")
        raise ProviderUnsupported()

    @staticmethod
    def _job(data, fallback_id, secret):
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        status = normalize_state(data.get("status"), _EXTRACTION)
        links = safe_links(result.get("short_link"), result.get("provider_redirect_url"), result.get("checkout_url"), result.get("qr_data"))
        return ProviderJob(
            job_id=str(data.get("id") or fallback_id),
            extraction_state=status,
            links=links,
            payment_links=safe_links(
                result.get("short_link"),
                result.get("provider_redirect_url"),
                result.get("checkout_url"),
            ),
            private_data={"job_secret": secret},
            summary={"percent": data.get("percent") if isinstance(data.get("percent"), int) else None},
        )
