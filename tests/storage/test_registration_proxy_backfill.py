from __future__ import annotations

from contextlib import contextmanager
import threading

from core.storage import db_legacy
from core.storage import postgres, records
from tests.support_pg import PostgresTestCase


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.statement = ""
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        self.statement = statement
        self.params = params

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
        lambda table, account_id, *, changes, guard, guard_params, conn=None: (
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


def test_backfill_can_process_a_bounded_batch(monkeypatch):
    connection = _Connection([])

    @contextmanager
    def connect(**_kwargs):
        yield connection

    monkeypatch.setattr(db_legacy.postgres_store, "connect", connect)
    assert db_legacy.backfill_account_registration_proxy_context(limit=100) == 0
    assert "JOIN latest" in connection.cursor_instance.statement
    assert connection.cursor_instance.params == (100,)


def test_backfill_query_and_claims_share_one_deadline(monkeypatch):
    now = [100.0]
    rows = [{
        "id": 7, "email": "budget@example.test", "account_provider": None,
        "account_region": None, "proxy_provider": "proxy-a", "proxy_region": "US",
    }]
    connections, claims = [], []

    @contextmanager
    def connect(**kwargs):
        connection = _Connection(rows)
        connections.append((connection, kwargs))
        yield connection

    def claim(_table, _account_id, *, changes, guard, guard_params, conn=None):
        claims.append((changes, conn))
        now[0] += 1.5
        return True

    monkeypatch.setattr(db_legacy.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(postgres, "connect", connect)
    monkeypatch.setattr(records, "claim_row", claim)
    assert db_legacy.backfill_account_registration_proxy_context(deadline=103.0) == 1
    assert [value[1]["deadline"] for value in connections] == [102.0, 102.0, 103.0]
    assert all(conn is not None for _changes, conn in claims)


def test_backfill_stops_claiming_when_its_total_budget_expires(monkeypatch):
    now = [100.0]
    rows = [{
        "id": 7, "email": "budget@example.test", "account_provider": None,
        "account_region": None, "proxy_provider": "proxy-a", "proxy_region": "US",
    }]
    claims = []

    @contextmanager
    def connect(**_kwargs):
        yield _Connection(rows)

    def claim(_table, _account_id, *, changes, **_kwargs):
        claims.append(changes)
        now[0] = 103.0
        return True

    monkeypatch.setattr(db_legacy.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(postgres, "connect", connect)
    monkeypatch.setattr(records, "claim_row", claim)
    assert db_legacy.backfill_account_registration_proxy_context(deadline=103.0) == 1
    assert len(claims) == 1
    assert claims[0]["registration_proxy_provider"] == "proxy-a"
    assert "registration_proxy_region" not in claims[0]


def test_backfill_cancellation_preserves_completed_claims(monkeypatch):
    cancelled = threading.Event()
    rows = [{
        "id": 7, "email": "cancel@example.test", "account_provider": None,
        "account_region": None, "proxy_provider": "proxy-a", "proxy_region": "US",
    }]
    claims = []

    @contextmanager
    def connect(**_kwargs):
        yield _Connection(rows)

    def claim(_table, _account_id, *, changes, **_kwargs):
        claims.append(changes)
        cancelled.set()
        return True

    monkeypatch.setattr(postgres, "connect", connect)
    monkeypatch.setattr(records, "claim_row", claim)
    assert db_legacy.backfill_account_registration_proxy_context(cancelled=cancelled.is_set) == 1
    assert len(claims) == 1
    assert claims[0]["registration_proxy_provider"] == "proxy-a"


def test_backfill_cancelled_before_query_does_not_borrow_a_connection(monkeypatch):
    @contextmanager
    def connect(**_kwargs):
        raise AssertionError("取消后不应借用数据库连接")
        yield

    monkeypatch.setattr(postgres, "connect", connect)
    assert db_legacy.backfill_account_registration_proxy_context(cancelled=lambda: True) == 0


class RegistrationProxyBackfillBatchTests(PostgresTestCase):
    def setUp(self):
        records.init()

    def test_invalid_regions_do_not_starve_a_later_fillable_account(self):
        with records.transaction() as conn:
            for number in range(101):
                account_id = records.insert_row(records.ACCOUNTS, {
                    "email": f"backfill-{number}@example.test",
                    "registration_proxy_provider": "existing",
                }, conn=conn)
                records.insert_row(records.JOBS, {
                    "email": f"backfill-{number}@example.test",
                    "account_id": account_id, "proxy_provider": "historical",
                    "proxy_region": "invalid" if number < 100 else "US",
                }, conn=conn)
        self.assertEqual(1, db_legacy.backfill_account_registration_proxy_context(limit=100))
        final = records.get_row(records.ACCOUNTS, account_id)
        self.assertEqual("US", final["registration_proxy_region"])
        self.assertEqual("existing", final["registration_proxy_provider"])
        self.assertIsNone(records.get_row(records.ACCOUNTS, 1).get("registration_proxy_region"))

    def test_latest_invalid_region_does_not_fall_back_to_an_older_job(self):
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": "latest@example.test", "registration_proxy_provider": "existing",
        })
        for region in ("US", "invalid"):
            records.insert_row(records.JOBS, {
                "email": "latest@example.test", "account_id": account_id,
                "proxy_provider": "historical", "proxy_region": region,
            })
        self.assertEqual(0, db_legacy.backfill_account_registration_proxy_context(limit=100))
        self.assertIsNone(records.get_row(records.ACCOUNTS, account_id).get("registration_proxy_region"))
