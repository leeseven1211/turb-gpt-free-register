from __future__ import annotations

from contextlib import contextmanager

from core.storage import db_legacy


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.statement = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement):
        self.statement = statement

    def fetchall(self):
        return self.rows


class _Connection:
    def __init__(self, rows):
        self.cursor_instance = _Cursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_instance


def test_backfill_reads_only_proxy_fields_and_keeps_idempotent_claims(monkeypatch):
    rows = [
        {
            "id": 7,
            "email": "a@example.test",
            "account_provider": None,
            "account_region": None,
            "proxy_provider": "proxy-a",
            "proxy_region": "us",
        },
        {
            "id": 8,
            "email": "b@example.test",
            "account_provider": "existing",
            "account_region": None,
            "proxy_provider": "proxy-b",
            "proxy_region": "ca",
        },
    ]
    connection = _Connection(rows)
    claims = []

    @contextmanager
    def connect(**_kwargs):
        yield connection

    monkeypatch.setattr(db_legacy.postgres_store, "connect", connect)
    monkeypatch.setattr(
        db_legacy.record_store,
        "claim_row",
        lambda table, account_id, *, changes, guard, guard_params: (
            claims.append((table.name, account_id, changes, guard, guard_params)) or True
        ),
    )

    changed = db_legacy.backfill_account_registration_proxy_context()

    assert changed == 2
    assert "candidate_jobs" in connection.cursor_instance.statement
    assert "UNION ALL" in connection.cursor_instance.statement
    assert "SELECT *" not in connection.cursor_instance.statement
    assert [item[1] for item in claims] == [7, 7, 8]
    assert claims[0][2]["registration_proxy_provider"] == "proxy-a"
    assert claims[1][2]["registration_proxy_region"] == "US"
    assert claims[2][2]["registration_proxy_region"] == "CA"
