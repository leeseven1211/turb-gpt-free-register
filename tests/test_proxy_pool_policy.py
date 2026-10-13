"""验证不可能满足的池策略在访问供应商之前失败。"""
from unittest.mock import patch

import pytest

from config import proxy as cfg
from core import proxy_pool


def test_impossible_lifetime_fails_before_start_or_supplier_request():
    with patch.object(proxy_pool, "start") as start, patch.object(cfg, "PROXY_POOL_MIN_TTL", 300):
        with pytest.raises(proxy_pool.ProxyPoolConfigurationError):
            proxy_pool.acquire(api_url="https://example.test/proxies", session_minutes=5)
    start.assert_not_called()


def test_incompatible_prewarm_profile_does_not_spend_supplier_requests():
    with patch.object(proxy_pool, "_profiles", {}), patch.object(proxy_pool, "_prewarm", True), \
         patch.object(cfg, "REGISTRATION_PROXY_MODE", "1024"), \
         patch.object(cfg, "PROXY_1024_API_URL", "https://example.test/proxies"), \
         patch.object(cfg, "PROXY_1024_SESSION_MINUTES", 5), patch.object(cfg, "PROXY_POOL_MIN_TTL", 300), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "reserve_slot") as reserve, \
         patch.object(proxy_pool.store, "take_check") as check, \
         patch("core.proxy_supply.fetch_candidates") as fetch:
        assert proxy_pool.maintain_once() is False
        assert proxy_pool.maintain_once() is False
    reserve.assert_not_called()
    check.assert_not_called()
    fetch.assert_not_called()


def test_late_database_claim_is_returned_without_delivery():
    clock = [0.0]
    lease = object()
    def slow_claim(*args, **kwargs):
        clock[0] = 2.0
        return lease
    with patch.object(proxy_pool, "start"), patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool.store, "claim", side_effect=slow_claim), \
         patch.object(proxy_pool.store, "release") as release:
        with pytest.raises(proxy_pool.ProxyPoolTimeout):
            proxy_pool.acquire(api_url="https://example.test/proxies", session_minutes=30, timeout=1)
    release.assert_called_once_with(lease, reason="allocation_cancelled", cooldown=0)
