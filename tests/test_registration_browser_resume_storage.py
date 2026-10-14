"""原浏览器连接只保存到同一 Attempt 的私有恢复上下文。"""
from __future__ import annotations

from core import postgres_store, record_store
from core.storage import registration
from tests.support_pg import PostgresTestCase


class BrowserResumeStorageTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.email = "retained-browser@example.test"
        self.root_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "browser-root", "email": self.email,
            "status": "running", "job_type": "registration",
        })
        self.attempt = registration.ensure_attempt_for_job(self.root_id)
        self.run = registration.start_run(
            self.attempt["id"], job_id=self.root_id,
            initial_status="running", execution_id="browser-execution",
        )

    def save(self, **overrides):
        kwargs = {
            "email": self.email, "run_id": self.run["id"],
            "execution_id": "browser-execution", "job_id": self.root_id,
            "profile_id": "local-profile", "debugger_address": "127.0.0.1:9222",
            "driver_path": "/tmp/test-chromedriver", "otp_after_ts": 123.5,
        }
        kwargs.update(overrides)
        return registration.save_browser_resume_context(self.attempt["id"], **kwargs)

    def test_private_connection_survives_without_account_or_public_projection(self):
        registration.save_password_checkpoint(
            self.attempt["id"], email=self.email, password="SavedOriginal123!",
            state="started", run_id=self.run["id"], execution_id="browser-execution",
        )
        registration.record_submission_fact(
            self.attempt["id"], submission_id="retained-unknown", kind="password",
            stage="password_create", phase="unknown", run_id=self.run["id"],
            execution_id="browser-execution",
        )
        before = registration.get_attempt(self.attempt["id"])
        stored = self.save()
        private = registration.get_private_resume_context(self.attempt["id"], email=self.email)
        self.assertEqual(stored, private["retained_browser"])
        self.assertEqual(set(stored), {
            "profile_id", "debugger_address", "driver_path", "job_id", "root_job_id",
            "run_id", "otp_after_ts",
        })
        self.assertEqual(stored["root_job_id"], self.root_id)
        self.assertEqual(private["password"], "SavedOriginal123!")
        self.assertEqual(private["submission_facts"][0]["submission_id"], "retained-unknown")
        public = registration.get_attempt(self.attempt["id"])
        self.assertIsNone(public["account_id"])
        self.assertEqual(public["checkpoint"], before["checkpoint"])
        self.assertEqual(public["data"], before["data"])
        self.assertNotIn("private_context", public)
        self.assertNotIn("local-profile", str(public))
        self.assertNotIn("127.0.0.1:9222", str(public))
        self.assertEqual(record_store.get_row(record_store.JOBS, self.root_id)["account_id"], None)
        self.assertEqual(record_store.list_rows(record_store.ACCOUNTS), [])

    def test_current_execution_and_matching_job_email_are_required(self):
        other_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "other-job", "email": self.email,
            "status": "running", "job_type": "registration",
        })
        registration.ensure_attempt_for_job(other_id)
        for overrides in ({"email": "different@example.test"},
                          {"execution_id": "stale-execution"}, {"job_id": other_id}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.save(**overrides)
        registration.finish_run(self.run["id"], status="failed")
        with self.assertRaises(ValueError):
            self.save()
        self.assertNotIn("retained_browser", registration.get_private_resume_context(
            self.attempt["id"], email=self.email,
        ))

    def test_corrupt_job_identity_and_root_chain_are_rejected(self):
        for changes in ({"email": "wrong@example.test"}, {"job_type": "codex_retry"},
                        {"root_job_id": self.root_id + 100}, {"attempt_id": None}):
            with self.subTest(changes=changes):
                original = record_store.get_row(record_store.JOBS, self.root_id)
                record_store.patch_row(record_store.JOBS, self.root_id, changes)
                with self.assertRaises(ValueError):
                    self.save()
                record_store.patch_row(record_store.JOBS, self.root_id, {
                    key: original.get(key) for key in changes
                })
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('registration_attempts')} "
                "SET source_root_job_id=%s WHERE id=%s",
                (self.root_id + 100, self.attempt["id"]),
            )
        with self.assertRaises(ValueError):
            self.save()

    def test_only_local_debugger_addresses_and_local_paths_are_allowed(self):
        for address in (
            "https://127.0.0.1:9222", "user@127.0.0.1:9222", "127.0.0.1:9222/path",
            "127.0.0.1:9222?token=hidden", "example.test:9222", "192.168.1.1:9222",
            "127.0.0.1:0", "127.0.0.1:65536", "127.0.0.1", "::1:9222", "",
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.save(debugger_address=address)
        for path in ("https://example.test/driver", "relative/driver", "file:///tmp/driver"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.save(driver_path=path)
        for timestamp in (-1, float("inf"), float("nan"), "not-a-time", True):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.save(otp_after_ts=timestamp)
        for address in ("127.0.0.1:9222", "localhost:9222", "[::1]:9222"):
            with self.subTest(address=address):
                stored = self.save(debugger_address=address, driver_path="", otp_after_ts=None)
                self.assertEqual(stored["debugger_address"], address)
                self.assertEqual(stored["driver_path"], "")
                self.assertIsNone(stored["otp_after_ts"])

    def test_new_run_of_same_attempt_can_replace_connection(self):
        self.save()
        registration.finish_run(self.run["id"], status="failed")
        child_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "browser-child", "email": self.email,
            "status": "running", "job_type": "registration_resume",
            "parent_job_id": self.root_id, "root_job_id": self.root_id,
            "attempt_id": self.attempt["id"],
        })
        next_run = registration.start_run(
            self.attempt["id"], job_id=child_id, action_type="registration_resume",
            initial_status="running", execution_id="next-execution",
        )
        stored = self.save(
            run_id=next_run["id"], execution_id="next-execution", job_id=child_id,
            profile_id="new-local-profile", debugger_address="127.0.0.1:9333",
        )
        self.assertEqual(stored["job_id"], child_id)
        self.assertEqual(stored["root_job_id"], self.root_id)
        self.assertEqual(stored["run_id"], next_run["id"])
        self.assertEqual(registration.get_private_resume_context(
            self.attempt["id"], email=self.email,
        )["retained_browser"], stored)
        with self.assertRaises(ValueError):
            self.save()
