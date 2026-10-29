"""展示统计缓存合并请求，但不缓存失败或跨过邮箱绝对有效期。"""
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from webui.display_statistics import DisplayStatisticsCache


def test_concurrent_reads_share_one_snapshot_and_return_independent_values():
    cache = DisplayStatisticsCache(ttl=15)
    entered, release = threading.Event(), threading.Event()
    calls = []

    def load():
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return {"sources": [{"available": 3}]}

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(cache.get, "supply", load) for _ in range(8)]
        assert entered.wait(3)
        release.set()
        values = [future.result(timeout=3) for future in futures]
    assert len(calls) == 1
    values[0]["sources"][0]["available"] = 0
    assert values[1]["sources"][0]["available"] == 3
    assert values[0]["statistics_updated_at"]


def test_expiry_boundary_forces_fresh_count_before_ttl():
    cache = DisplayStatisticsCache(ttl=15)
    with patch("webui.display_statistics.time.time", return_value=100):
        assert cache.get("supply", lambda: {"available": 1, "next_expiry_epoch": 102})["available"] == 1
    with patch("webui.display_statistics.time.time", return_value=103):
        assert cache.get("supply", lambda: {"available": 0})["available"] == 0


def test_invalidation_during_read_does_not_publish_stale_snapshot():
    cache = DisplayStatisticsCache(ttl=15)

    def load_old():
        cache.invalidate()
        return {"available": 1}

    cache.get("supply", load_old)
    assert cache.get("supply", lambda: {"available": 2})["available"] == 2


def test_mutation_invalidation_does_not_wait_for_slow_statistics():
    cache = DisplayStatisticsCache(ttl=15)
    entered, release = threading.Event(), threading.Event()

    def load():
        entered.set()
        assert release.wait(3)
        return {"available": 1}

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cache.get, "supply", load)
        assert entered.wait(3)
        invalidated = executor.submit(cache.invalidate)
        try:
            invalidated.result(timeout=0.2)
        finally:
            release.set()
        first.result(timeout=3)
    assert cache.get("supply", lambda: {"available": 2})["available"] == 2


def test_failed_refresh_does_not_serve_previous_success():
    cache = DisplayStatisticsCache(ttl=0)
    cache.get("supply", lambda: {"available": 1})

    def fail():
        raise RuntimeError("统计查询失败")

    try:
        cache.get("supply", fail)
    except RuntimeError:
        pass
    else:
        raise AssertionError("失败不能显示为历史成功")
    assert cache.get("supply", lambda: {"available": 0})["available"] == 0
