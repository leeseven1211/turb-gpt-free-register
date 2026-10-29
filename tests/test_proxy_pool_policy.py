"""验证不可能满足的池策略在访问供应商之前失败。"""
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace

import pytest

from config import proxy as cfg
from core import proxy_pool
from core.operation_runtime import CancellationToken, OperationCancelled, operation_context
from core.proxy_lease_store import ProxyReuseLimitError


@pytest.mark.parametrize("provider", ["1024proxy", "proxy_pool"])
def test_zero_configured_timeout_waits_past_sixty_seconds_for_inventory(provider):
    clock = [0.0]
    lease = object()
    progress = []

    def wait_for_supply(_seconds):
        clock[0] += 65.0

    with patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 0), \
         patch.object(proxy_pool, "start"), patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool._stop, "wait", side_effect=wait_for_supply), \
         patch.object(proxy_pool.store, "claim", side_effect=[None, None, lease]):
        received = proxy_pool.acquire(
            provider=provider, api_url="https://example.test/proxies",
            static_urls=["http://192.0.2.1:8080"], progress_callback=progress.append,
        )
        assert all(profile.waiting == 0 for profile in proxy_pool._profiles.values())

    assert received is lease
    assert clock[0] == 130.0
    assert any("等待" in message and "65" in message for message in progress)


def test_waiting_for_inventory_obeys_operation_cancellation_without_explicit_callback():
    token = CancellationToken(run_id=1, token="test", checker=lambda *_args: False)

    def no_inventory(*_args, **_kwargs):
        token.request_local()
        return None

    with operation_context(token), patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 0), \
         patch.object(proxy_pool, "start"), patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool._stop, "wait"), \
         patch.object(proxy_pool.store, "claim", side_effect=no_inventory) as claim:
        with pytest.raises(OperationCancelled):
            proxy_pool.acquire(api_url="https://example.test/proxies")
        assert all(profile.waiting == 0 for profile in proxy_pool._profiles.values())
    claim.assert_called_once()


def test_operation_cancellation_returns_just_claimed_route_without_delivery():
    token = CancellationToken(run_id=1, token="test", checker=lambda *_args: False)
    lease = object()

    def late_claim(*_args, **_kwargs):
        token.request_local()
        return lease

    with operation_context(token), patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 0), \
         patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.store, "claim", side_effect=late_claim), \
         patch.object(proxy_pool.store, "release") as release:
        with pytest.raises(OperationCancelled):
            proxy_pool.acquire(api_url="https://example.test/proxies")
    release.assert_called_once_with(lease, reason="allocation_cancelled", cooldown=0)


def test_stopped_pool_ends_unbounded_wait():
    with patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 0), patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool._stop, "is_set", return_value=True), \
         patch.object(proxy_pool.store, "claim", return_value=None):
        with pytest.raises(proxy_pool.ProxyPoolTimeout, match="已停止"):
            proxy_pool.acquire(api_url="https://example.test/proxies")


def test_explicit_zero_timeout_still_ends_immediately():
    with patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 0), patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.store, "claim") as claim:
        with pytest.raises(proxy_pool.ProxyPoolTimeout):
            proxy_pool.acquire(api_url="https://example.test/proxies", timeout=0)
    claim.assert_not_called()


def test_positive_configured_timeout_keeps_its_wait_budget():
    clock = [0.0]

    def no_inventory(*_args, **_kwargs):
        clock[0] = 2.0
        return None

    with patch.object(cfg, "PROXY_POOL_WAIT_TIMEOUT", 1), patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool._stop, "wait"), \
         patch.object(proxy_pool.store, "claim", side_effect=no_inventory) as claim:
        with pytest.raises(proxy_pool.ProxyPoolTimeout, match="等待超时"):
            proxy_pool.acquire(api_url="https://example.test/proxies")
    claim.assert_called_once()


def test_reuse_limit_exhaustion_waits_for_other_inventory_in_same_budget():
    clock = [0.0]
    lease = object()
    progress = []
    attempts = [ProxyReuseLimitError("198.51.100.1", 3), lease]
    with patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool._stop, "wait"), \
         patch.object(proxy_pool.store, "claim", side_effect=attempts):
        received = proxy_pool.acquire(
            api_url="https://example.test/proxies", purpose="plan-check", allow_reuse=True,
            reuse_limit=3, timeout=1, progress_callback=progress.append,
        )
    assert received is lease
    assert any("查询次数上限" in message for message in progress)


def test_reuse_limit_exhaustion_remains_visible_when_wait_budget_ends():
    clock = [0.0]

    def exhausted(*_args, **_kwargs):
        clock[0] = 2.0
        raise ProxyReuseLimitError("198.51.100.1", 3)

    with patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool._stop, "wait"), \
         patch.object(proxy_pool.store, "claim", side_effect=exhausted):
        with pytest.raises(proxy_pool.ProxyPoolTimeout, match="查询次数上限"):
            proxy_pool.acquire(
                api_url="https://example.test/proxies", purpose="plan-check", allow_reuse=True,
                reuse_limit=3, timeout=1,
            )


def test_equal_demand_profiles_both_receive_maintenance():
    """某地区持续复检不能占满另一地区的全部维护机会。"""
    first = proxy_pool.Profile("first", "1024proxy", {"session_minutes": 30}, waiting=1, touched=1)
    second = proxy_pool.Profile("second", "1024proxy", {"session_minutes": 30}, waiting=1, touched=2)
    seen = []
    def take_check(key, **kwargs):
        seen.append(key)
        return {"id": len(seen)}
    with patch.object(proxy_pool, "_profiles", {"first": first, "second": second}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "_current_profile_keys", return_value={"first", "second"}), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", side_effect=take_check), \
         patch.object(proxy_pool, "_check"):
        for _ in range(4):
            assert proxy_pool.maintain_once() is True
    assert set(seen) == {"first", "second"}
    assert abs(seen.count("first") - seen.count("second")) <= 1


def test_two_workers_reserve_different_waiting_profiles_before_network_work():
    first = proxy_pool.Profile("first", "1024proxy", {"session_minutes": 30}, waiting=1)
    second = proxy_pool.Profile("second", "1024proxy", {"session_minutes": 30}, waiting=1)
    seen = []
    barrier = threading.Barrier(2)
    def check(resource, policy):
        barrier.wait(timeout=3)
    def take_check(key, **kwargs):
        seen.append(key)
        return {"id": key}
    with patch.object(proxy_pool, "_profiles", {"first": first, "second": second}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "_current_profile_keys", return_value={"first", "second"}), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]), \
         patch.object(proxy_pool.store, "take_check", side_effect=take_check), \
         patch.object(proxy_pool, "_check", side_effect=check), \
         ThreadPoolExecutor(max_workers=2) as executor:
        assert all(executor.map(lambda _: proxy_pool.maintain_once(), range(2)))
    assert set(seen) == {"first", "second"}


def test_twenty_workers_merge_global_maintenance_before_database_work():
    started = threading.Barrier(20)
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def maintain(**kwargs):
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return []

    def run(_):
        started.wait(timeout=5)
        return proxy_pool.maintain_once(role="check")

    with patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "_current_profile_keys", return_value=set()), \
         patch.object(proxy_pool.store, "maintenance", side_effect=maintain), \
         ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(run, index) for index in range(20)]
        try:
            assert entered.wait(3)
            # 重复请求可继续执行各自的复检/供给，不等全局维护完成。
            from concurrent.futures import wait
            finished, _ = wait(futures, timeout=0.5)
            completed_while_maintenance_runs = len(finished)
        finally:
            release.set()
        assert all(future.result(timeout=5) is False for future in futures)
    assert completed_while_maintenance_runs == 19
    assert len(calls) == 1


def test_busy_worker_merges_repeated_global_maintenance_within_one_tick():
    policy = dict(proxy_pool.settings(), workers=20)
    with patch.object(proxy_pool, "settings", return_value=policy), \
         patch.object(proxy_pool, "_profiles", {}), \
         patch.object(proxy_pool, "_global_maintenance_due", 0), \
         patch.object(proxy_pool, "_prewarm", False), \
         patch.object(proxy_pool, "_current_profile_keys", return_value=set()), \
         patch.object(proxy_pool.time, "monotonic", return_value=1000), \
         patch.object(proxy_pool._stop, "is_set", side_effect=[False, False, False, True]), \
         patch.object(proxy_pool._wake, "wait"), \
         patch.object(proxy_pool.store, "maintenance", return_value=[]) as maintain:
        proxy_pool._worker(19)
    assert maintain.call_count == 1


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


@pytest.mark.parametrize("cancel_during_confirmation", [False, True])
def test_slow_delivery_confirmation_returns_unhanded_lease(cancel_during_confirmation):
    clock = [0.0]
    token = CancellationToken(run_id=1, token="test", checker=lambda *_args: False)
    lease = SimpleNamespace(metadata={"pool_resource_id": "test-resource"})

    def confirm(_lease):
        clock[0] = 3.0
        if cancel_during_confirmation:
            token.request_local()
        return True

    expected_error = OperationCancelled if cancel_during_confirmation else proxy_pool.ProxyPoolTimeout
    with operation_context(token), patch.object(proxy_pool, "start"), \
         patch.object(proxy_pool.time, "monotonic", side_effect=lambda: clock[0]), \
         patch.object(proxy_pool.store, "claim", return_value=lease), \
         patch.object(proxy_pool.store, "mark_delivered", side_effect=confirm), \
         patch.object(proxy_pool.store, "release") as release:
        with pytest.raises(expected_error):
            proxy_pool.acquire(api_url="https://example.test/proxies", timeout=1)
    release.assert_called_once_with(lease, reason="allocation_cancelled", cooldown=0, before_delivery=True)
