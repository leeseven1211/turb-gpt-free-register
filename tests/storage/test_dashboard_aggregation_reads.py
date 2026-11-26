"""总览聚合保持历史口径，并使账号 JSON 读取量随账号数而非任务数增长。"""

from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import re
from unittest.mock import patch

import psycopg

from core.storage import admin_repository as repository, postgres, records
from core.storage.registration import analytics
from tests.support_pg import PostgresTestCase


class DashboardAggregationReadTests(PostgresTestCase):
    def setUp(self):
        records.init()

    def _account(self, name, *, extra_json=None, **values):
        return records.insert_row(records.ACCOUNTS, {
            "email": f"{name}@example.test",
            "password": "synthetic-password",
            "totp_secret": "synthetic-totp",
            "plan_check_status": "success",
            "codex_status": "success",
            "extra_json": {} if extra_json is None else extra_json,
            **values,
        })

    def _job(self, name, account_id=None, *, status="success", created_at=None, **values):
        return records.insert_row(records.JOBS, {
            "job_uuid": name,
            "email": f"{name.split('-job')[0]}@example.test",
            "account_id": account_id,
            "status": status,
            "created_at": created_at or datetime.now().isoformat(),
            **values,
        })

    @contextmanager
    def _account_json_reads(self):
        """在 PostgreSQL 实际执行时计数；结果和业务 SQL 都仍使用真实数据。"""
        sequence = postgres.qualified("dashboard_json_reads")
        function = postgres.qualified("observe_dashboard_json")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence}")
            cur.execute(f"ALTER SEQUENCE {sequence} RESTART WITH 1")
            cur.execute(f"""CREATE OR REPLACE FUNCTION {function}(value jsonb) RETURNS jsonb
                LANGUAGE plpgsql VOLATILE AS $$
                BEGIN
                    PERFORM nextval('{sequence}');
                    RETURN value;
                END $$""")
        original = psycopg.Cursor.execute
        original_server = psycopg.ServerCursor.execute
        counts = {}

        def observed_query(query):
            if isinstance(query, str):
                query = re.sub(
                    r"\b(?:a|account)\.data\b",
                    lambda match: f"{function}({match.group(0)})",
                    query,
                )
            return query

        def execute(cursor, query, params=None, **kwargs):
            return original(cursor, observed_query(query), params, **kwargs)

        def server_execute(cursor, query, params=None, **kwargs):
            return original_server(cursor, observed_query(query), params, **kwargs)

        with patch.object(psycopg.Cursor, "execute", execute), patch.object(
            psycopg.ServerCursor, "execute", server_execute
        ):
            yield counts
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT CASE WHEN is_called THEN last_value ELSE 0 END FROM {sequence}")
            counts["reads"] = int(cur.fetchone()[0])

    def test_dashboard_reads_account_json_once_for_repeated_historical_jobs(self):
        account_id = self._account("repeated")
        today = datetime.now()
        for index in range(12):
            self._job(
                f"repeated-job-{index}", account_id,
                created_at=(today - timedelta(days=index % 2)).isoformat(),
            )

        with self._account_json_reads() as counts:
            result = repository.dashboard_aggregates(public_status=True, include_email_status=False)

        self.assertEqual(result["jobs"]["counts"], {"success": 12})
        self.assertEqual(result["jobs"]["today_counts"], {"success": 6})
        self.assertEqual(counts["reads"], 1)

    def test_daily_reads_account_evidence_once_and_ignores_repeated_registration_jobs(self):
        account_id = self._account("daily-repeated", created_at="2026-11-25T08:00:00+08:00")
        for index in range(12):
            self._job(
                f"daily-repeated-job-{index}", account_id,
                created_at=f"2026-11-{25 + index % 2}T08:00:00+08:00",
            )

        with self._account_json_reads() as counts:
            result = analytics.registration_daily_analytics(
                date_from="2026-11-25", date_to="2026-11-26",
            )

        self.assertEqual(result["summary"]["accounts_total"], 1)
        self.assertEqual([row["accounts_total"] for row in result["rows"]], [1, 0])
        self.assertEqual(result["summary"]["promotion_presence"], {"eligible": 0, "none": 0, "unknown": 1})
        self.assertEqual(counts["reads"], 1)

    def test_missing_other_setup_requirements_skip_account_json(self):
        cases = (
            ("codex-missing", {"codex_status": "failed"}, {}),
            ("password-missing", {"password": ""}, {}),
            ("plan-missing", {"plan_check_status": "failed"}, {}),
            ("totp-missing", {"totp_secret": ""}, {}),
            ("twofa-disabled", {}, {"config_snapshot": {"twofa_enabled": False}}),
        )
        for name, values, job_values in cases:
            account_id = self._account(name, extra_json={"totp_setup_pending": True}, **values)
            self._job(
                f"{name}-job", account_id, created_at="2026-11-26T08:00:00+08:00",
                **job_values,
            )

        with self._account_json_reads() as counts:
            dashboard = repository.dashboard_aggregates(public_status=True, include_email_status=False)
        self.assertEqual(dashboard["jobs"]["counts"], {"success": 1, "partial_success": 4})
        self.assertEqual(counts["reads"], 0)

    def test_dashboard_keeps_current_setup_and_requested_status_rules(self):
        cases = (
            ("object-pending", {"totp_setup_pending": True}, "partial_success"),
            ("string-pending", json.dumps({"totp_setup_pending": "yes"}), "partial_success"),
            ("string-ready", json.dumps({"totp_setup_pending": False}), "success"),
            ("invalid-string", "{invalid", "success"),
            ("non-object", ["totp_setup_pending"], "success"),
        )
        for name, extra, _expected in cases:
            account_id = self._account(name, extra_json=extra)
            self._job(f"{name}-job", account_id, created_at="2026-11-26T08:00:00+08:00")
        pending = self._account("disabled-twofa", extra_json={"totp_setup_pending": True})
        self._job(
            "disabled-twofa-job", pending, created_at="2026-11-26T08:00:00+08:00",
            config_snapshot={"twofa_enabled": False},
        )
        self._job(
            "saved-partial-job", status="request_unknown", created_at="2026-11-26T08:00:00+08:00",
            requested_status="partial_success",
        )
        self._job(
            "nested-partial-job", status="manual_reconcile", created_at="2026-11-26T08:00:00+08:00",
            result_summary={"requested_status": "partial_success"},
        )
        running = self._account("running-account")
        self._job(
            "running-account-job", running, status="running",
            created_at="2026-11-26T08:00:00+08:00",
        )

        dashboard = repository.dashboard_aggregates(public_status=True, include_email_status=False)
        # 任务概览继续按当前账号完成性重算显式关联任务。
        self.assertEqual(dashboard["jobs"]["counts"], {"success": 5, "partial_success": 3, "failed": 1})
