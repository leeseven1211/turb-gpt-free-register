# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import db, registration_service
from webui.app import _compact_job_for_list, _latest_progress_batch, create_app
from tests.support_pg import PostgresTestCase


class JobProgressTests(PostgresTestCase):
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
                self.assertEqual(row["progress_steps"]["complete"]["state"], "success")
                self.assertEqual(row["progress_steps"]["complete"]["started_at"], row["created_at"])
                self.assertEqual(row["progress_stage"], "complete")

    def test_successful_closeout_marks_never_started_stages_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                job = db.create_job("icloud_hide")
                db.update_job_progress(job["id"], "email_otp", "success", "邮箱验证码已通过")
                db.update_job_progress(job["id"], "profile", "pending", "尚未开始")

                db.finish_job_progress(job["id"], success=True)

                row = db.get_job(job["id"])
                self.assertEqual(row["progress_steps"]["email_otp"]["state"], "success")
                self.assertEqual(row["progress_steps"]["profile"]["state"], "skipped")
                self.assertEqual(row["progress_steps"]["token"]["state"], "skipped")
                self.assertEqual(row["progress_steps"]["plan_check"]["state"], "skipped")
                self.assertEqual(row["progress_steps"]["complete"]["state"], "success")

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
                self.assertEqual(row["progress_steps"]["profile"]["state"], "skipped")
                self.assertEqual(row["progress_steps"]["plan_check"]["state"], "skipped")
                self.assertEqual(row["progress_steps"]["complete"]["state"], "failed")

    def test_failed_codex_is_not_moved_to_successful_plan_check(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                job = db.create_job("icloud_hide")
                db.update_job_progress(job["id"], "codex", "failed", "OAuth 失败")
                db.update_job_progress(job["id"], "plan_check", "running", "正在查套餐")
                db.update_job_progress(job["id"], "plan_check", "success", "free")

                db.finish_job_progress(job["id"], success=False, detail="Codex 未完成")

                row = db.get_job(job["id"])
                self.assertEqual(row["progress_steps"]["codex"]["state"], "failed")
                self.assertEqual(row["progress_steps"]["codex"]["detail"], "OAuth 失败")
                self.assertEqual(row["progress_steps"]["plan_check"]["state"], "success")
                self.assertEqual(row["progress_steps"]["complete"]["state"], "failed")

    def test_partial_success_can_create_codex_retry_job(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                source = db.create_job("icloud_hide")
                db.update_job(
                    source["id"],
                    status="partial_success",
                    email="demo@example.com",
                    account_id=42,
                )

                retry, created = db.create_retry_job(
                    source["id"],
                    job_type="codex_retry",
                    email_source="icloud_hide",
                    email="demo@example.com",
                    account_id=42,
                )

                self.assertTrue(created)
                self.assertEqual(retry["retry_action"], "codex")
                self.assertEqual(retry["parent_job_id"], source["id"])

    def test_partial_success_with_codex_failure_is_retryable(self):
        job = {
            "id": 9,
            "status": "partial_success",
            "account_id": 42,
            "progress_steps": {
                "codex": {"state": "failed"},
                "twofa": {"state": "success"},
            },
        }
        account = {"id": 42, "email": "demo@example.com", "codex_status": "failed"}
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertEqual(info["display_status"], "partial_success")
        self.assertTrue(info["retryable"])
        self.assertEqual(info["retry_action"], "codex")

    def test_twofa_only_failure_offers_dedicated_twofa_retry(self):
        job = {
            "id": 10,
            "status": "partial_success",
            "account_id": 43,
            "progress_steps": {
                "codex": {"state": "success"},
                "twofa": {"state": "failed"},
            },
        }
        account = {"id": 43, "email": "twofa@example.com", "codex_status": "success"}
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertEqual(info["display_status"], "partial_success")
        self.assertTrue(info["retryable"])
        self.assertEqual(info["retry_action"], "twofa")
        self.assertEqual(info["retry_label"], "重试 2FA")

    def test_successful_codex_account_with_missing_setup_offers_account_setup_retry(self):
        job = {
            "id": 12,
            "status": "success",
            "account_id": 45,
            "progress_steps": {"codex": {"state": "success"}},
        }
        account = {
            "id": 45,
            "email": "setup@example.com",
            "access_token": "saved-token",
            "codex_status": "success",
            "plan_check_status": "failed",
            "totp_secret": "",
            "extra_json": "{}",
        }
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertEqual(info["display_status"], "partial_success")
        self.assertTrue(info["retryable"])
        self.assertEqual(info["retry_action"], "twofa")
        self.assertEqual(info["retry_label"], "补齐账号配置")

    def test_account_password_counts_as_current_password(self):
        job = {
            "id": 13,
            "status": "partial_success",
            "account_id": 46,
            "progress_steps": {"codex": {"state": "success"}, "twofa": {"state": "success"}},
        }
        account = {
            "id": 46,
            "email": "new-password@example.com",
            "access_token": "saved-token",
            "codex_status": "success",
            "plan_check_status": "success",
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "extra_json": '{"account_password":"AccountPassword!123"}',
        }
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertFalse(info["retryable"])
        self.assertEqual(info["retry_reason"], "账号和 Codex 授权均已完成")

    def test_pending_email_verification_account_resumes_saved_login(self):
        job = {
            "id": 11,
            "status": "partial_success",
            "account_id": 44,
            "progress_steps": {"email_otp": {"state": "failed"}},
        }
        account = {
            "id": 44,
            "email": "pending@example.com",
            "access_token": "",
            "extra_json": (
                '{"registration_checkpoint":"email_verification_pending",'
                '"registration_password":"StoredPassword!123"}'
            ),
        }
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertTrue(info["retryable"])
        self.assertEqual(info["retry_action"], "registration_resume")
        self.assertEqual(info["retry_label"], "继续邮箱验证")

    def test_historical_job_marks_new_auth_redirect_stage_skipped(self):
        row = {
            "id": 1,
            "status": "success",
            "progress_steps": {
                "submit_email": {
                    "state": "success",
                    "started_at": "2026-08-13T12:00:00",
                    "completed_at": "2026-08-13T12:00:20",
                },
                "email_otp": {"state": "success"},
            },
        }

        compact = _compact_job_for_list(row)

        self.assertEqual(compact["progress_steps"]["auth_redirect"]["state"], "skipped")
        self.assertEqual(
            compact["progress_steps"]["auth_redirect"]["started_at"],
            "2026-08-13T12:00:20",
        )
        self.assertNotIn("auth_redirect", row["progress_steps"])

    def test_historical_terminal_job_gets_plan_and_total_duration_stages(self):
        row = {
            "id": 2,
            "status": "success",
            "created_at": "2026-08-13T12:00:00",
            "started_at": "2026-08-13T12:00:02",
            "completed_at": "2026-08-13T12:01:30",
            "progress_steps": {
                "codex": {
                    "state": "success",
                    "started_at": "2026-08-13T12:01:00",
                    "completed_at": "2026-08-13T12:01:20",
                },
            },
        }

        compact = _compact_job_for_list(row)

        self.assertEqual(compact["progress_steps"]["plan_check"]["state"], "skipped")
        self.assertEqual(compact["progress_steps"]["complete"]["state"], "success")
        self.assertEqual(compact["progress_steps"]["complete"]["started_at"], row["started_at"])
        self.assertEqual(compact["progress_steps"]["complete"]["completed_at"], row["completed_at"])
        self.assertNotIn("plan_check", row["progress_steps"])

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

    def test_job_stop_state_survives_unrelated_worker_update(self):
        job = db.create_job(
            "icloud_hide",
            batch_id="stop-race",
            batch_index=1,
            batch_size=1,
        )
        self.assertTrue(db.claim_job_for_execution(job["id"]))
        self.assertTrue(
            db.transition_job_status(
                job["id"],
                ("running",),
                "stopping",
                error_message="用户手动停止中",
            )
        )

        # 线程停止前仍可能写入代理/邮箱字段，不能把 stopping 覆盖回 running。
        db.update_job(job["id"], proxy_status="leased", email="race@example.com")
        db.finish_job_progress(job["id"], success=False, detail="用户手动停止", failure_state="stopped")
        row = db.get_job(job["id"])
        self.assertEqual(row["status"], "stopping")
        self.assertEqual(row["proxy_status"], "leased")
        self.assertEqual(row["email"], "race@example.com")
        self.assertFalse(db.claim_job_for_execution(job["id"]))

    def test_batch_control_only_changes_target_batch(self):
        first = db.create_job("icloud_hide", batch_id="batch-a", batch_index=1, batch_size=2)
        second = db.create_job("icloud_hide", batch_id="batch-a", batch_index=2, batch_size=2)
        other = db.create_job("icloud_hide", batch_id="batch-b", batch_index=1, batch_size=1)
        self.assertTrue(db.claim_job_for_execution(first["id"]))
        self.assertTrue(db.claim_job_for_execution(other["id"]))

        stopped = registration_service.request_stop_batch("batch-a")
        self.assertTrue(stopped["ok"])
        self.assertEqual(stopped["stopped"], 1)
        self.assertEqual(db.get_job(first["id"])["status"], "stopped")
        self.assertEqual(db.get_job(second["id"])["status"], "pending")
        self.assertEqual(db.get_job(other["id"])["status"], "running")

        cancelled = registration_service.cancel_pending_jobs(batch_id="batch-a")
        self.assertEqual(cancelled, 1)
        self.assertEqual(db.get_job(second["id"])["status"], "cancelled")
        self.assertEqual(db.get_job(other["id"])["status"], "running")


if __name__ == "__main__":
    unittest.main()
