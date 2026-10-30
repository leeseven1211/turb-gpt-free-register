from __future__ import annotations

from core.extract_link.contracts import ProviderConfig, ProviderError
from core.extract_link.huanguang.client import HuanguangProvider
from core.extract_link.legacy.client import LegacyProvider
from core.extract_link.lumen_flow.client import LumenFlowProvider


_REGISTRY = {
    "legacy": LegacyProvider,
    "lumen_flow": LumenFlowProvider,
    "huanguang": HuanguangProvider,
}


def get_provider(provider_id: str, *, config: ProviderConfig, transport, payment_transport=None):
    if not isinstance(config, ProviderConfig) or config.provider_id != provider_id:
        raise ProviderError("Provider 配置不匹配")
    provider_type = _REGISTRY.get(provider_id)
    if provider_type is None:
        raise ProviderError("未知 Provider")
    if provider_id == "legacy":
        return provider_type(config, transport, payment_transport=payment_transport)
    return provider_type(config, transport)


__all__ = ["ProviderConfig", "ProviderError", "get_provider"]
