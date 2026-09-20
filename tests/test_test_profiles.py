"""Tests for the isolated pytest profile argument contract."""

import pytest

from tools import test_isolated


def test_default_profile_excludes_extended_items():
    assert test_isolated.apply_profile(["-q"], "default") == ["-q", "-m", "not extended"]


def test_extended_profile_selects_only_extended_items():
    assert test_isolated.apply_profile(["-q"], "extended") == ["-q", "-m", "extended"]


def test_all_profile_does_not_add_a_marker():
    assert test_isolated.apply_profile(["-q"], "all") == ["-q"]


def test_unknown_profile_and_conflicting_marker_are_rejected():
    with pytest.raises(ValueError):
        test_isolated.apply_profile(["-q"], "missing")
    with pytest.raises(ValueError):
        test_isolated.apply_profile(["-m", "not slow"], "default")
