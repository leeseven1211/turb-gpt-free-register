"""Account date filters share the dashboard's Beijing calendar days."""
from __future__ import annotations

import uuid

from core.accounts import query
from core.storage import admin_repository as admin, postgres, records
from core.storage.operations import bulk_selections
from tests.support_pg import PostgresTestCase


class AccountCreationDateTests(PostgresTestCase):
    def setUp(self):
        records.reset_ready()
        records.init()
        self.ids = {}
        fixtures = {
            "before": "2026-11-25T15:59:59Z",
            "utc_start": "2026-11-25T16:00:00Z",
            "utc_end": "2026-11-26T15:59:59.999999+00:00",
            "after": "2026-11-26T16:00:00+00:00",
            "positive_offset": "2026-11-26T00:00:00+08:00",
            "negative_offset": "2026-11-25T18:00:00-06:00",
            "compact_offset": "2026-11-26T23:59:59+0800",
            "hour_offset": "2026-11-26T00:00:00+08",
            "naive_start": "2026-11-26T00:00:00",
            "naive_end": "2026-11-26 23:59:59.999999",
            "date_only": "2026-11-26",
            "empty": "",
            "whitespace": "   ",
            "invalid_time": "2026-11-26T25:00:00",
            "invalid_suffix": "2026-11-26invalid",
            "invalid_offset": "2026-11-26T08:00:00+99:99",
            "invalid_calendar": "2026-02-29T08:00:00",
            "invalid_month": "2026-13-01T08:00:00Z",
            "zero_year": "0000-11-26T08:00:00Z",
            "infinity": "infinity",
            "relative": "now",
        }
        for name, created_at in fixtures.items():
            self.ids[name] = records.insert_row(records.ACCOUNTS, {
                "email": f"beijing-created-{name}@example.test",
                "created_at": created_at,
            })
        self.day_names = set(fixtures) - {
            "before", "after", "empty", "whitespace", "invalid_time",
            "invalid_suffix", "invalid_offset", "invalid_calendar",
            "invalid_month", "zero_year", "infinity", "relative",
        }

    def _assert_query_members(self, expected_names, **dates):
        expected = {self.ids[name] for name in expected_names}
        spec = query.from_legacy(q="邮箱:beijing-created-", **dates)
        where, params = query.compile_query(spec)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT a.id FROM {postgres.qualified(records.ACCOUNTS.name)} a WHERE {where}",
                params,
            )
            self.assertEqual({row[0] for row in cur.fetchall()}, expected)

        listed = admin.list_accounts(
            admin.PageRequest(page_size=100), q=spec["q"], **dates,
        )
        self.assertEqual({item["id"] for item in listed["items"]}, expected)
        self.assertEqual(listed["total"], len(expected))
        self.assertEqual(admin.account_query_count(spec), len(expected))

        selection = bulk_selections.create_selection(
            request_key=uuid.uuid4().hex,
            source={"kind": "query", "query": spec},
            operation_key="plan_check",
            config_revision="test-date-filter",
        )
        frozen = bulk_selections.freeze_selection(
            selection["id"], where_sql=where, params=params,
        )
        self.assertEqual(frozen["total_count"], len(expected))
        selected = bulk_selections.get_selection(selection["id"], limit=100)
        self.assertEqual(
            {item["target_id"] for item in selected["targets"]}, expected,
        )

    def test_single_day_matches_beijing_boundaries_in_list_count_and_bulk(self):
        self._assert_query_members(
            self.day_names, date_from="2026-11-26", date_to="2026-11-26",
        )

    def test_open_date_boundaries_are_inclusive_and_skip_invalid_dates(self):
        self._assert_query_members(
            self.day_names | {"after"}, date_from="2026-11-26",
        )
        self._assert_query_members(
            self.day_names | {"before"}, date_to="2026-11-26",
        )

    def test_date_expression_is_independent_of_database_timezone(self):
        from core.storage.account_dates import account_created_date_sql

        expression = account_created_date_sql()
        with postgres.connect() as conn, conn.cursor() as cur:
            for timezone in ("UTC", "America/Los_Angeles", "Asia/Tokyo"):
                cur.execute("SELECT set_config('TimeZone', %s, true)", (timezone,))
                cur.execute(
                    f"""SELECT a.id, ({expression})::text
                          FROM {postgres.qualified(records.ACCOUNTS.name)} a""",
                )
                actual = dict(cur.fetchall())
                expected_dates = {
                    self.ids[name]: "2026-11-26" for name in self.day_names
                }
                expected_dates[self.ids["before"]] = "2026-11-25"
                expected_dates[self.ids["after"]] = "2026-11-27"
                self.assertEqual(
                    {key: value for key, value in actual.items() if value is not None},
                    expected_dates,
                    timezone,
                )
