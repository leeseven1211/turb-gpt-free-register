"""Pure checks for the reproducible performance benchmark boundaries."""
import pytest

from tools.test_performance import percentile


def test_percentile_uses_nearest_rank_for_small_sample():
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([4, 1, 3, 2], 50) == 2


def test_percentile_rejects_empty_or_invalid_input():
    with pytest.raises(ValueError):
        percentile([], 95)
    with pytest.raises(ValueError):
        percentile([1], 0)
