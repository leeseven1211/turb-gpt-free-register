"""Tests for collection-time extended marker assignment."""

from pathlib import Path

from tests import conftest


class _FakeItem:
    def __init__(self, path: str, nodeid: str, cls=None):
        self.fspath = Path(path)
        self.nodeid = nodeid
        self.cls = cls
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker.name)


def test_collection_hook_marks_extended_postgres_and_diagnostic_items():
    postgres_base = type("PostgresTestCase", (), {})
    postgres_case = type("SyntheticPostgresCase", (postgres_base,), {})
    root = Path(__file__).resolve().parents[2]
    smoke = _FakeItem(
        root / "tests/storage/test_record_store.py",
        "tests/storage/test_record_store.py::RecordStoreSchemaTests::test_promoted_and_jsonb_fields_round_trip_as_one_flat_dict",
        postgres_case,
    )
    database_risk = _FakeItem(
        root / "tests/storage/test_record_store.py",
        "tests/storage/test_record_store.py::RecordStoreSchemaTests::test_sparse_field_is_not_materialised_as_column",
        postgres_case,
    )
    release_risk = _FakeItem(
        root / "tests/tools/test_release_checks.py",
        "tests/tools/test_release_checks.py::test_one",
    )

    conftest.pytest_collection_modifyitems(None, [smoke, database_risk, release_risk])

    assert smoke.markers == []
    assert database_risk.markers == ["extended"]
    assert release_risk.markers == ["extended"]
