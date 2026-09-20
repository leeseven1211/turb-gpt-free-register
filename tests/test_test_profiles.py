"""Tests for the isolated pytest profile argument contract."""

import pytest

from tools import test_isolated
from tools import test_profiles


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


def test_database_smoke_allowlist_has_eleven_nodes():
    assert len(test_profiles.DEFAULT_DATABASE_NODE_IDS) == 11
    assert (
        "tests/test_record_store.py::RecordStoreSchemaTests::"
        "test_promoted_and_jsonb_fields_round_trip_as_one_flat_dict"
    ) in test_profiles.DEFAULT_DATABASE_NODE_IDS


def test_classification_keeps_smoke_nodes_default_and_moves_other_risks():
    smoke_node = next(iter(test_profiles.DEFAULT_DATABASE_NODE_IDS))
    assert test_profiles.classify_node("tests/test_record_store.py", smoke_node, is_postgres=True) is None
    assert test_profiles.classify_node(
        "tests/test_record_store.py",
        "tests/test_record_store.py::RecordStoreSchemaTests::test_sparse_field_is_not_materialised_as_column",
        is_postgres=True,
    ) == "extended"
    assert test_profiles.classify_node("tests/test_release_checks.py", "tests/test_release_checks.py::test_one", is_postgres=False) == "extended"
    assert test_profiles.classify_node("tests/test_config_defaults.py", "tests/test_config_defaults.py::test_one", is_postgres=False) is None
