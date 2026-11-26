# -*- coding: utf-8 -*-
import unittest
from datetime import datetime

from core.storage import admin_repository
from core.storage import records as rs
from core.storage import postgres as postgres_store
from core.storage import registration
from core.storage.registration import analytics
from core.storage.registration.account_links import registration_account_link
from tests.support_pg import PostgresTestCase


class RegistrationDailyAnalyticsTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def _account(self, email, **values):
        return rs.insert_row(rs.ACCOUNTS, {"email": email, **values})

    def _job(self, email, created_at, *, status="success", job_type=None, account_id=None, batch_id="batch"):
        return rs.insert_row(rs.JOBS, {
            "job_uuid": f"{email}-{created_at}-{status}-{job_type or 'empty'}",
            "email": email,
            "created_at": created_at,
            "status": status,
            "job_type": job_type,
            "account_id": account_id,
            "batch_id": batch_id,
        })

    def _link_attempt(self, root_job_id, *, email_snapshot, account_id=None, email="", email_source=None,
                      source_root_job_id=None):
        attempt = registration.create_attempt(
            email_snapshot,
            email_source=email_source,
            root_job_id=root_job_id,
        )
        attempts = postgres_store.qualified("registration_attempts")
        jobs = postgres_store.qualified(rs.JOBS.name)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {attempts}
                       SET source_root_job_id=%s, email_snapshot=%s, email=%s, account_id=%s,
                           email_source=%s
                     WHERE id=%s""",
                (
                    source_root_job_id if source_root_job_id is not None else root_job_id,
                    email_snapshot,
                    email,
                    account_id,
                    email_source,
                    attempt["id"],
                ),
            )
            cur.execute(
                f"""UPDATE {jobs}
                       SET attempt_id=%s, root_job_id=%s, account_id=%s
                     WHERE id=%s""",
                (attempt["id"], root_job_id, account_id, root_job_id),
            )
        return int(attempt["id"])

    def test_aggregates_jobs_by_beijing_date_and_deduplicates_accounts(self):
        account_a = self._account(
            "daily-a@example.test",
            current_plan_type="free",
            plan_check_status="success",
            plus_promo_kind="none",
            archived=False,
        )
        account_b = self._account(
            "daily-b@example.test",
            current_plan_type="plus",
            plan_check_status="success",
            plus_promo_kind="none",
            archived=True,
        )
        # 2026-11-25 16:30 UTC 是北京时间 2026-11-26 00:30。
        self._job("daily-a@example.test", "2026-11-25T16:30:00+00:00", account_id=account_a)
        # 显式新建的重跑是第二个任务，但当天账号仍只计一个归属成员。
        self._job("daily-a@example.test", "2026-11-25T16:40:00+00:00", status="failed")
        self._job(
            "daily-b@example.test",
            "2026-11-26T15:59:00+00:00",
            status="request_unknown",
            job_type="registration_resume",
            account_id=account_b,
        )
        # 下一北京时间日期和非注册任务应排除。
        self._job("daily-a@example.test", "2026-11-26T16:00:00+00:00", account_id=account_a)
        self._job("daily-a@example.test", "2026-11-25T16:50:00+00:00", job_type="account_setup", account_id=account_a)

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-27",
        )

        self.assertEqual(result["timezone"], "Asia/Shanghai")
        self.assertEqual(result["date_from"], "2026-11-26")
        self.assertEqual(result["date_to"], "2026-11-27")
        rows = {row["date"]: row for row in result["rows"]}
        self.assertEqual(rows["2026-11-26"]["total"], 3)
        self.assertEqual(rows["2026-11-26"]["counts"], {"failed": 2, "partial_success": 1})
        self.assertEqual(rows["2026-11-26"]["accounts_total"], 2)
        self.assertEqual(rows["2026-11-26"]["plans"], {"free": 1, "plus": 1})
        self.assertEqual(rows["2026-11-26"]["unpromoted_count"], 1)
        self.assertEqual(rows["2026-11-27"]["total"], 1)
        self.assertEqual(result["summary"]["total"], 4)
        self.assertEqual(result["summary"]["accounts_total"], 2)

    def test_explicit_account_attribution_does_not_fall_back_to_colliding_batch_email(self):
        account_id = self._account(
            "collision@example.test",
            current_plan_type="free",
            plan_check_status="success",
            plus_promo_kind="none",
        )
        self._job(
            "collision@example.test",
            "2026-11-26T01:00:00+00:00",
            account_id=None,
            batch_id="collision-batch",
        )
        self._job(
            "collision@example.test",
            "2026-11-26T02:00:00+00:00",
            account_id=None,
            batch_id="collision-batch",
        )
        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["accounts_total"], 0)
        self.assertEqual(result["summary"]["unpromoted_count"], 0)

    def test_explicit_account_tasks_retain_non_success_statuses(self):
        statuses = ("running", "cancelled", "failed")
        for status in statuses:
            email = f"status-{status}@example.test"
            account_id = self._account(email)
            self._job(
                email,
                "2026-11-26T01:00:00+00:00",
                status=status,
                account_id=account_id,
            )

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )

        self.assertEqual(
            result["rows"][0]["counts"],
            {"cancelled": 1, "failed": 1, "running": 1},
        )
        self.assertEqual(result["summary"]["counts"], result["rows"][0]["counts"])

    def test_historical_explicit_account_with_empty_email_is_retained(self):
        account_id = self._account("historical-empty-email@example.test")
        self._job(
            "",
            "2026-11-26T01:00:00+00:00",
            account_id=account_id,
            job_type="",
        )

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )

        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["summary"]["accounts_total"], 1)

    def test_invalid_or_empty_created_at_is_ignored_without_breaking_other_jobs(self):
        account_id = self._account("valid-created-at@example.test")
        self._job("valid-created-at@example.test", "2026-11-26T01:00:00+00:00", account_id=account_id)
        self._job("empty-created-at@example.test", "", account_id=account_id)
        self._job("invalid-created-at@example.test", "2026-99-99T99:99:99", account_id=account_id)

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )

        self.assertEqual(result["summary"]["total"], 1)

    def test_compatible_created_at_offset_formats_are_counted(self):
        for index, created_at in enumerate((
            "2026-11-26T01:00:00+0800",
            "2026-11-26T02:00:00z",
            "2026-11-26T03:00:00",
        )):
            self._job(f"created-format-{index}@example.test", created_at)

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )

        self.assertEqual(result["summary"]["total"], 3)

    def test_date_filter_is_inside_materialized_cohort_source(self):
        source = admin_repository._registration_cohort_source_sql(
            date_range=("2026-11-26", "2026-11-26"),
        )
        self.assertLess(
            source.index("::date >= %s::date"),
            source.index("), verified AS MATERIALIZED"),
        )
        self.assertLess(
            source.index("::date <= %s::date"),
            source.index("), verified AS MATERIALIZED"),
        )

    def test_sql_cohort_rejects_conflicting_attempt_identity_and_allows_root_email_backfill(self):
        valid_account = self._account(
            "root-backfill@example.test",
            plan_check_status="success",
            plan_check_ok=True,
            plus_promo_kind="none",
        )
        wrong_email_account = self._account("actual-account@example.test")
        conflicting_root = self._job(
            "root-conflict@example.test", "2026-11-26T01:00:00+00:00",
            account_id=valid_account,
        )
        self._link_attempt(
            conflicting_root,
            email_snapshot="root-conflict@example.test",
            account_id=valid_account,
            source_root_job_id=conflicting_root + 999,
        )
        no_explicit_account = self._job(
            "no-explicit@example.test", "2026-11-26T02:00:00+00:00",
        )
        self._link_attempt(
            no_explicit_account,
            email_snapshot="no-explicit@example.test",
        )
        wrong_email = self._job(
            "wrong-identity@example.test", "2026-11-26T03:00:00+00:00",
            account_id=wrong_email_account,
        )
        self._link_attempt(
            wrong_email,
            email_snapshot="wrong-identity@example.test",
            account_id=wrong_email_account,
        )
        backfilled = self._job(
            "", "2026-11-26T04:00:00+00:00",
            account_id=valid_account,
        )
        # 根任务和 Attempt 都没有明文邮箱，只能由同源 email_source 回填。
        attempts = postgres_store.qualified("registration_attempts")
        jobs = postgres_store.qualified(rs.JOBS.name)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {jobs} SET data=data || %s::jsonb WHERE id=%s",
                ('{"email_source":"outlook"}', backfilled),
            )
        self._link_attempt(
            backfilled,
            email_snapshot="root-backfill@example.test",
            account_id=valid_account,
            email_source="outlook",
        )
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""UPDATE {attempts}
                       SET email_snapshot=%s, email='', email_source='outlook'
                     WHERE root_job_id=%s""",
                ("root-backfill@example.test", backfilled),
            )

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )

        self.assertEqual(result["summary"]["total"], 4)
        self.assertEqual(result["summary"]["accounts_total"], 1)
        self.assertEqual(result["summary"]["plans"], {"unknown": 1})

    def test_unpromoted_count_matches_accounts_returned_by_summary_query(self):
        unpromoted = self._account(
            "unpromoted@example.test",
            current_plan_type="free",
            plus_promo_kind="none",
            plan_check_status="success",
            plan_check_ok=True,
            archived=False,
        )
        queued = self._account(
            "queued-none@example.test",
            current_plan_type="free",
            plus_promo_kind="none",
            plan_check_status="Queued",
            plan_check_ok=True,
            archived=False,
        )
        promoted = self._account(
            "promoted@example.test",
            current_plan_type="free",
            plus_promo_kind="free_trial",
            plus_trial_eligible=True,
            plan_check_status="success",
            plan_check_ok=True,
            archived=False,
        )
        self._job("unpromoted@example.test", "2026-11-26T05:00:00+00:00", account_id=unpromoted)
        self._job("queued-none@example.test", "2026-11-26T05:30:00+00:00", account_id=queued)
        self._job("promoted@example.test", "2026-11-26T06:00:00+00:00", account_id=promoted)

        result = analytics.registration_daily_analytics(
            date_from="2026-11-26",
            date_to="2026-11-26",
        )
        query = result["summary"]["query"]
        matched = admin_repository.account_query_count(query)

        self.assertEqual(result["summary"]["unpromoted_count"], 1)
        self.assertEqual(matched, result["summary"]["unpromoted_count"])


class RegistrationDailyAnalyticsValidationTests(unittest.TestCase):
    def test_date_range_is_bounded_and_has_stable_error_codes(self):
        cases = (
            ({"date_from": "2026-11-27", "date_to": "2026-11-26"}, "date_range_reversed"),
            ({"date_from": "2026-02-30", "date_to": "2026-02-30"}, "date_invalid"),
            ({"date_from": "2025-01-01", "date_to": "2026-01-02"}, "date_range_too_large"),
            ({"date_to": "0001-01-01"}, "date_invalid"),
            ({"date_from": "9999-12-31"}, "date_invalid"),
        )
        for values, code in cases:
            with self.subTest(values=values):
                with self.assertRaises(analytics.RegistrationDailyAnalyticsError) as raised:
                    analytics.registration_daily_analytics(**values)
                self.assertEqual(raised.exception.error_code, code)
                self.assertTrue(str(raised.exception))

    def test_default_range_uses_the_last_seven_beijing_dates(self):
        result = analytics.normalize_registration_date_range(
            now=datetime(2026, 11, 26, 1, 0, 0),
        )
        self.assertEqual(result, ("2026-11-20", "2026-11-26"))

    def test_registration_account_link_rejects_conflicting_attempt_identity(self):
        base_job = {"id": 9, "root_job_id": 9, "attempt_id": 7, "account_id": 11, "email": "a@example.test"}
        root = {
            "id": 9, "root_job_id": None, "attempt_id": 7,
            "account_id": 11, "email": "a@example.test",
        }
        for attempt in (
            {"id": 7, "email_snapshot": "a@example.test", "account_id": 11},
            {"id": 7, "root_job_id": 8, "email_snapshot": "a@example.test", "account_id": 11},
            {"id": 7, "root_job_id": 9, "source_root_job_id": 8,
             "email_snapshot": "a@example.test", "account_id": 11},
            {"id": 7, "root_job_id": 9, "email_snapshot": "other@example.test", "account_id": 11},
            {"id": 7, "root_job_id": 9, "email_snapshot": "a@example.test", "account_id": 12},
        ):
            with self.subTest(attempt=attempt):
                self.assertIsNone(registration_account_link(base_job, root, attempt))

    def test_registration_account_link_allows_root_email_source_backfill(self):
        job = {
            "id": 9, "root_job_id": 9, "attempt_id": 7, "account_id": 11,
            "email": "", "email_source": "outlook",
        }
        root = {
            "id": 9, "root_job_id": None, "attempt_id": 7, "account_id": 11,
            "email": "", "email_source": "outlook",
        }
        attempt = {
            "id": 7, "root_job_id": 9, "email_snapshot": "a@example.test",
            "email": "", "email_source": "outlook", "account_id": 11,
        }
        self.assertEqual(registration_account_link(job, root, attempt), ("a@example.test", 11))
