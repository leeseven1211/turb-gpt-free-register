from __future__ import annotations

from .contracts import ProviderConfig, ProviderError
from .huanguang import HuanguangProvider
from .legacy import LegacyProvider
from .lumen_flow import LumenFlowProvider


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
