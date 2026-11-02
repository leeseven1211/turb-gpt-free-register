"""显式换国家的重跑快照只属于子任务与 Run，不改写原 Attempt。"""
from __future__ import annotations

import copy

from core import db
from core.storage import db_legacy, registration
from tests.support_pg import PostgresTestCase


class RegistrationRetryCountryStorageTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.original_snapshot = {"registration_driver": "roxy", "proxy_country": "IN"}
        self.root = db.create_job("outlook", data={"config_snapshot": self.original_snapshot})
        db.update_job(self.root["id"], status="failed", email="country-retry@example.test")
        registration.finish_run(registration.list_runs(self.root["attempt_id"])[0]["id"], status="failed")
        self.source, created = db.create_retry_job(
            self.root["id"], job_type="registration_resume", email_source="outlook",
            email="country-retry@example.test", data={"config_snapshot": self.original_snapshot},
        )
        self.assertTrue(created)
        db.update_job(self.source["id"], status="failed")
        self.attempt_id = int(self.source["attempt_id"])
        registration.finish_run(registration.list_runs(self.attempt_id)[0]["id"], status="failed")
        self.attempt_before = copy.deepcopy(registration.get_attempt(self.attempt_id)["data"])
        self.root_before = copy.deepcopy(db.get_job(self.root["id"])["config_snapshot"])
        self.source_before = copy.deepcopy(db.get_job(self.source["id"])["config_snapshot"])

    def _jp_retry(self):
        snapshot = {"registration_driver": "roxy", "proxy_country": "JP",
                    "retry_proxy_country_override": "JP"}
        child, created = db.create_retry_job(
            self.source["id"], job_type="registration_resume", email_source="outlook",
            email="country-retry@example.test",
            data={"config_snapshot": snapshot, "country_retry_note": "keep-child-metadata"},
        )
        self.assertTrue(created)
        return child, snapshot

    def _assert_original_snapshots(self):
        attempt = registration.get_attempt(self.attempt_id)
        self.assertEqual(attempt["data"]["config_snapshot"], self.attempt_before["config_snapshot"])
        self.assertEqual(db.get_job(self.root["id"])["config_snapshot"], self.root_before)
        self.assertEqual(db.get_job(self.source["id"])["config_snapshot"], self.source_before)
        self.assertNotIn("retry_proxy_country_override", attempt["data"]["config_snapshot"])

    def test_explicit_country_changes_child_and_run_but_preserves_original_snapshots(self):
        child, snapshot = self._jp_retry()

        self._assert_original_snapshots()
        self.assertEqual(child["attempt_id"], self.attempt_id)
        self.assertEqual(child["parent_job_id"], self.source["id"])
        self.assertEqual(child["root_job_id"], self.root["id"])
        self.assertEqual(db.get_job(child["id"])["config_snapshot"], snapshot)
        runs = registration.list_runs(self.attempt_id)
        self.assertIn(child["id"], [int(row["job_id"]) for row in runs], [(row["id"], row["job_id"]) for row in runs])
        run = next(row for row in runs if int(row["job_id"]) == child["id"])
        self.assertEqual(run["data"]["config_snapshot"], snapshot)
        self.assertEqual(run["data"]["country_retry_note"], "keep-child-metadata")
        self.assertEqual(registration.get_attempt(self.attempt_id)["data"]["country_retry_note"],
                         "keep-child-metadata")

    def test_relinking_explicit_country_child_never_changes_original_attempt_snapshot(self):
        child, snapshot = self._jp_retry()
        original_run_ids = {row["id"] for row in registration.list_runs(self.attempt_id)}

        for _ in range(2):
            db_legacy._ensure_registration_attempt_job(child)
            self._assert_original_snapshots()

        runs = registration.list_runs(self.attempt_id)
        self.assertEqual({row["id"] for row in runs}, original_run_ids)
        run = next(row for row in runs if int(row["job_id"]) == child["id"])
        self.assertEqual(run["data"]["config_snapshot"], snapshot)

    def test_ordinary_retry_keeps_existing_attempt_metadata_merge_behavior(self):
        snapshot = {"registration_driver": "roxy", "proxy_country": "JP"}
        child, created = db.create_retry_job(
            self.source["id"], job_type="registration_resume", email_source="outlook",
            email="country-retry@example.test", data={"config_snapshot": snapshot},
        )
        self.assertTrue(created)
        self.assertEqual(registration.get_attempt(self.attempt_id)["data"]["config_snapshot"], snapshot)
        self.assertEqual(child["data"]["config_snapshot"], snapshot)
