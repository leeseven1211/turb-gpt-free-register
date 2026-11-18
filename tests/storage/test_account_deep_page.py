"""Account deep-page SQL selection without a database connection.

These tests exercise both repository entry points and their SQL boundary.
PostgreSQL row equivalence and query performance are verified separately.
"""
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import patch

import pytest

from core.accounts.query import FILTER_FIELDS
from core.storage import admin_repository as repo


class _ReadCursor:
    def __init__(self, total, rows):
        self.total = total
        self.rows = rows
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, deepcopy(params)))

    def fetchone(self):
        assert len(self.queries) == 1
        return {"total": self.total, "latest": "2026-11-16T12:00:00"}

    def fetchall(self):
        assert len(self.queries) in (2, 3)
        return deepcopy(self.rows) if len(self.queries) == 2 else []

    @contextmanager
    def cursor(self):
        yield self


def _read(entry, request, *, total=100000, rows=(), **kwargs):
    cursor = _ReadCursor(total, rows)

    @contextmanager
    def connect():
        yield cursor

    with patch.object(repo, "_connect", connect):
        response = getattr(repo, entry)(request, **kwargs)
    assert len(cursor.queries) == (3 if entry == "list_accounts" else 2)
    return response, cursor.queries


ENTRIES = ("list_accounts", "list_account_statuses")


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize(
    "total,offset,enabled",
    (
        (99999, 10000, False),
        (100000, 9999, False),
        (100000, 10000, True),
        (100001, 10000, False),
        (100001, 10001, True),
        (300000, 0, False),
        (300000, 299999, True),
        (100000, 100001, True),
        (0, 10000, False),
    ),
)
def test_narrow_ids_only_at_approved_population_and_depth(entry, total, offset, enabled):
    result, queries = _read(entry, repo.PageRequest(page=offset + 1, page_size=1), total=total)
    page_sql, params = queries[1]
    assert page_sql.startswith("WITH ") is enabled
    assert params == (1, offset)
    assert result["total"] == total
    assert result["page"] == offset + 1
    assert result["items"] == []


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("field,value", (
    ("q", "example.test"), ("q", "方式:roxy"), ("q", " "),
    ("plan", "plus"), ("plan", "all"),
    ("date_from", "2026-11-01"), ("date_to", "2026-11-16"),
    ("date_from", " "),
))
def test_search_plan_and_dates_keep_original_page_strategy(entry, field, value):
    _, queries = _read(entry, repo.PageRequest(page=10001, page_size=1), **{field: value})
    assert queries[1][0].startswith("SELECT ")
    assert queries[1][0].endswith("ORDER BY a.id DESC LIMIT %s OFFSET %s")


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("field", (*FILTER_FIELDS, "trial", "future_filter"))
def test_any_business_filter_keeps_original_page_strategy(entry, field):
    request = repo.PageRequest(page=10001, page_size=1, filters={field: "has"})
    _, queries = _read(entry, request)
    assert queries[1][0].startswith("SELECT ")


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("archived,predicate", (
    ("0", "a.archived IS FALSE"),
    ("only", "a.archived IS TRUE"),
    ("1", "a.archived IS TRUE"),
    ("all", "TRUE"),
    ("include", "TRUE"),
))
def test_archived_scope_is_retained_inside_narrow_page(entry, archived, predicate):
    _, queries = _read(entry, repo.PageRequest(page=10001, page_size=1), archived=archived)
    page_sql = queries[1][0]
    assert page_sql.startswith("WITH ")
    assert f" a WHERE {predicate} ORDER BY a.id DESC LIMIT %s OFFSET %s)" in page_sql
    assert queries[1][1] == (1, 10000)


@pytest.mark.parametrize("entry", ENTRIES)
def test_empty_column_filters_do_not_disable_deep_page(entry):
    request = repo.PageRequest(page=10001, page_size=1, filters={key: "" for key in FILTER_FIELDS})
    _, queries = _read(entry, request)
    assert queries[1][0].startswith("WITH ")


@pytest.mark.parametrize("entry", ENTRIES)
def test_deep_page_preserves_projection_parameters_count_and_facets(entry):
    request = repo.PageRequest(page=10001, page_size=1)
    _, original = _read(entry, request, total=99999)
    _, optimized = _read(entry, request, total=100000)
    baseline_sql, baseline_params = original[1]
    optimized_sql, optimized_params = optimized[1]
    table = repo._q(repo.record_store.ACCOUNTS)
    projection = baseline_sql.removeprefix("SELECT ").rsplit(f" FROM {table} a", 1)[0]

    assert optimized_sql == (
        f"WITH account_page_ids AS MATERIALIZED (SELECT a.id FROM {table} a"
        " WHERE a.archived IS FALSE ORDER BY a.id DESC LIMIT %s OFFSET %s) "
        f"SELECT {projection} FROM {table} a"
        " JOIN account_page_ids AS page_ids ON page_ids.id = a.id ORDER BY a.id DESC"
    )
    assert optimized_params == baseline_params
    assert optimized[0] == original[0]
    assert optimized[2:] == original[2:]
    assert "a.data - ARRAY['access_token'" in projection
    assert 'a."chatgpt_session"' not in projection


@pytest.mark.parametrize("entry", ENTRIES)
def test_count_changes_select_strategy_again_without_caching(entry):
    request = repo.PageRequest(page=10001, page_size=1)
    observed = [
        _read(entry, request, total=total)[1][1][0].startswith("WITH ")
        for total in (100000, 99999, 100001, 100000)
    ]
    assert observed == [True, False, False, True]


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("compact", (False, True))
def test_page_output_and_revision_keep_existing_decoration(entry, compact):
    request = repo.PageRequest(page=10001, page_size=1)
    rows = [{
        "id": 90000, "email": "deep-page@example.test", "archived": False,
        "plan_type": "free", "current_plan_type": "free",
        "data": {"has_access_token": True, "has_account_password": True,
                 "last_password_auth_status": "verified", "plan_check_error": "synthetic"},
    }]
    kwargs = {"compact": compact} if entry == "list_account_statuses" else {}
    result, _ = _read(entry, request, rows=rows, **kwargs)
    assert result["items"][0]["id"] == 90000
    assert result["items"][0]["email"] == "deep-page@example.test"
    assert result["items"][0]["has_account_password"] is True
    assert result["items"][0]["last_password_auth_status"] == "verified"
    assert result["revision"].startswith("100000:2026-11-16T12:00:00:")
    assert ("status_fields" in result) is (entry == "list_account_statuses" and compact)
    changed = deepcopy(rows)
    changed[0]["data"]["last_password_auth_status"] = "rejected"
    updated, _ = _read(entry, request, rows=changed, **kwargs)
    assert updated["revision"] != result["revision"]
