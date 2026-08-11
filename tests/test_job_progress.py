# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import db
from webui.app import _latest_progress_batch, create_app


class JobProgressTests(unittest.TestCase):
    def _storage_patches(self, root: Path):
        return (
            patch.object(db, "_DATA_DIR", root),
            patch.object(db, "_LOG_DIR", root / "logs"),
            patch.object(db, "_JOBS_JSON", root / "jobs.json"),
            patch.object(db, "_LEGACY_JOBS_JSON", root / "legacy_jobs.json"),
        )

    def test_progress_tracks_stages_and_keeps_explicit_failure(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                job = db.create_job(
                    "icloud_hide",
                    batch_id="batch-demo",
                    batch_index=2,
                    batch_size=4,
                    batch_workers=3,
                )
                db.update_job_progress(job["id"], "email", "running", "领取邮箱")
                db.update_job_progress(job["id"], "browser", "running", "启动浏览器")

                row = db.get_job(job["id"])
                self.assertEqual(row["progress_steps"]["email"]["state"], "success")
                self.assertEqual(row["progress_steps"]["browser"]["state"], "running")
                self.assertEqual(row["batch_index"], 2)
                self.assertEqual(row["batch_size"], 4)
                self.assertEqual(row["batch_workers"], 3)

                db.update_job_progress(job["id"], "codex", "failed", "OAuth 超时")
                db.finish_job_progress(job["id"], success=True)
                row = db.get_job(job["id"])
                self.assertEqual(row["progress_steps"]["codex"]["state"], "failed")
                self.assertEqual(row["progress_steps"]["codex"]["detail"], "OAuth 超时")

    def test_failed_job_lands_on_current_stage(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                job = db.create_job("icloud_hide")
                db.update_job_progress(job["id"], "email_otp", "running")
                db.finish_job_progress(job["id"], success=False, detail="验证码超时")
                row = db.get_job(job["id"])
                self.assertEqual(row["progress_steps"]["email_otp"]["state"], "failed")
                self.assertEqual(row["progress_steps"]["email_otp"]["detail"], "验证码超时")

    def test_startup_recovers_interrupted_jobs_and_codex_account(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            patches = self._storage_patches(root)
            with patches[0], patches[1], patches[2], patches[3], patch.object(
                db, "_ACCOUNTS_JSON", root / "accounts.json"
            ):
                job = db.create_job("icloud_hide")
                db.update_job(job["id"], status="running", proxy_status="leased")
                db.update_job_progress(job["id"], "email_otp", "running", "等待验证码")

                recovered = db.recover_interrupted_registration_jobs()

                self.assertEqual(recovered, 1)
                row = db.get_job(job["id"])
                self.assertEqual(row["status"], "failed")
                self.assertEqual(row["proxy_status"], "interrupted")
                self.assertEqual(row["progress_steps"]["email_otp"]["state"], "failed")
                self.assertIn("WebUI 进程重启", row["error_message"])

    def test_jobs_api_returns_latest_batch_progress(self):
        rows = [
            {
                "id": 2,
                "status": "running",
                "batch_id": "new-batch",
                "batch_index": 2,
                "batch_size": 2,
                "batch_workers": 2,
                "email": "second@example.com",
                "progress_stage": "browser",
                "progress_steps": {"browser": {"state": "running"}},
                "created_at": "2026-08-10T12:00:00",
                "started_at": "2026-08-10T12:00:01",
            },
            {
                "id": 1,
                "status": "success",
                "batch_id": "new-batch",
                "batch_index": 1,
                "batch_size": 2,
                "batch_workers": 2,
                "email": "first@example.com",
                "progress_stage": "codex",
                "progress_steps": {"codex": {"state": "success"}},
                "created_at": "2026-08-10T12:00:00",
                "started_at": "2026-08-10T12:00:01",
                "completed_at": "2026-08-10T12:01:00",
            },
        ]
        batch = _latest_progress_batch(rows)
        self.assertEqual([item["id"] for item in batch["items"]], [1, 2])
        self.assertEqual(batch["status_counts"]["success"], 1)
        self.assertEqual(batch["status_counts"]["running"], 1)
        self.assertEqual([stage["key"] for stage in batch["stages"]], [key for key, _ in db.JOB_PROGRESS_STAGES])

        app = create_app(auth_code="test-auth")
        client = app.test_client()
        with patch.object(db, "list_jobs", return_value=rows):
            response = client.get(
                "/api/jobs?paged=1&page=1&page_size=20",
                headers={"X-Auth-Code": "test-auth"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["progress_batch"]["batch_id"], "new-batch")
        self.assertEqual(len(payload["progress_batch"]["items"]), 2)


if __name__ == "__main__":
    unittest.main()
