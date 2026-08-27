# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

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
                    batch_id="retry-batch-demo",
                    batch_index=2,
                    batch_size=3,
                    batch_workers=4,
                )

                self.assertTrue(created)
                self.assertEqual(retry["retry_action"], "codex")
                self.assertEqual(retry["parent_job_id"], source["id"])
                self.assertEqual(retry["batch_id"], "retry-batch-demo")
                self.assertEqual(retry["batch_index"], 2)
                self.assertEqual(retry["batch_size"], 3)
                self.assertEqual(retry["batch_workers"], 4)

    def test_registration_batch_email_claim_is_unique_but_cross_batch_reusable(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                self.assertTrue(
                    db.claim_registration_batch_email(
                        "batch-a", "Same@Example.com", job_id=1, email_source="icloud_hide"
                    )
                )
                self.assertFalse(
                    db.claim_registration_batch_email(
                        "batch-a", "same@example.com", job_id=2, email_source="icloud_hide"
                    )
                )
                self.assertTrue(
                    db.claim_registration_batch_email(
                        "batch-b", "same@example.com", job_id=3, email_source="icloud_hide"
                    )
                )

    def test_registration_batch_email_claim_blocks_existing_job_email(self):
        with tempfile.TemporaryDirectory() as td:
            patches = self._storage_patches(Path(td))
            with patches[0], patches[1], patches[2], patches[3]:
                job = db.create_job("icloud_hide", batch_id="batch-existing")
                db.update_job(job["id"], email="already@example.com")
                self.assertFalse(
                    db.claim_registration_batch_email(
                        "batch-existing", "already@example.com", job_id=job["id"] + 1
                    )
                )

    def test_prepare_registration_args_releases_duplicate_candidate_after_new_claim(self):
        from config import email as email_config, register as register_config

        with (
            patch.object(register_config, "REGISTER_EMAIL", ""),
            patch.object(email_config, "USE_EMAIL_SERVICE", True),
            patch.object(registration_service, "_random_display_name", return_value="Test User"),
            patch("core.profile_utils.generate_random_birthday", return_value="1990-01-01"),
            patch("core.email_provider.acquire_email", side_effect=["same@example.com", "new@example.com"]),
            patch.object(db, "claim_registration_batch_email", side_effect=[False, True]),
            patch("core.email_provider.release_email") as release_email,
        ):
            result = registration_service._prepare_registration_args(
                "icloud_hide", batch_id="batch-a", job_id=2
            )

        self.assertEqual(result, ("new@example.com", "Test User", "1990-01-01"))
        release_email.assert_called_once_with(
            "same@example.com", status="available", note=ANY
        )

    def test_prepare_registration_args_stops_if_provider_repeats_rejected_email(self):
        from config import email as email_config, register as register_config

        with (
            patch.object(register_config, "REGISTER_EMAIL", ""),
            patch.object(email_config, "USE_EMAIL_SERVICE", True),
            patch.object(registration_service, "_random_display_name", return_value="Test User"),
            patch("core.profile_utils.generate_random_birthday", return_value="1990-01-01"),
            patch("core.email_provider.acquire_email", side_effect=["same@example.com", "SAME@example.com"]),
            patch.object(db, "claim_registration_batch_email", return_value=False),
            patch("core.email_provider.release_email") as release_email,
        ):
            with self.assertRaisesRegex(RuntimeError, "重复返回同一候选"):
                registration_service._prepare_registration_args(
                    "icloud_hide", batch_id="batch-a", job_id=2
                )

        release_email.assert_called_once_with(
            "same@example.com", status="available", note=ANY
        )

    def test_account_lookup_does_not_cross_match_duplicate_batch_email(self):
        job = {
            "id": 10,
            "batch_id": "batch-a",
            "email": "same@example.com",
            "account_id": None,
        }
        with (
            patch.object(db, "count_registration_jobs_by_batch_email", return_value=2),
            patch.object(db, "get_account_by_email") as lookup,
        ):
            account = registration_service._account_for_job(job)

        self.assertIsNone(account)
        lookup.assert_not_called()

    def test_skipped_codex_is_not_offered_as_codex_retry(self):
        job = {
            "id": 11,
            "status": "success",
            "account_id": 42,
            "progress_steps": {
                "codex": {"state": "skipped"},
                "twofa": {"state": "success"},
            },
        }
        account = {
            "id": 42,
            "email": "skipped@example.com",
            "access_token": "saved-token",
            # 兼容历史上误写成 failed 的账号字段：任务进度明确 skipped 时，
            # UI 仍不能把它展示成 Codex 失败。
            "codex_status": "failed",
            "plan_check_status": "success",
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "extra_json": '{"account_password":"AccountPassword!123"}',
        }
        with patch.object(db, "get_successful_retry_for_job", return_value=None), patch.object(
            registration_service, "_account_for_job", return_value=account
        ):
            info = registration_service.get_retry_info(job)

        self.assertFalse(info["retryable"])
        self.assertEqual(info["retry_action"], None)
        self.assertIn("跳过", info["retry_reason"])

    def test_registration_codex_retry_delegates_to_native_operation_without_legacy_job(self):
        source = {"id": 17, "status": "partial_success", "email": "native@example.com", "account_id": 42}
        account = {"id": 42, "email": "native@example.com", "codex_status": "failed"}
        with (
            patch.object(db, "get_job", return_value=source),
            patch.object(registration_service, "get_retry_info", return_value={
                "retryable": True, "retry_action": "codex",
            }),
            patch.object(registration_service, "_account_for_job", return_value=account),
            patch("core.operation_task_store.find_task_by_source", return_value={"id": 700}),
            patch("core.codex_operation_service.submit", return_value={
                "accepted": True, "task_id": 701, "run_id": 702,
            }) as submit,
            patch.object(db, "create_retry_job") as legacy_create,
        ):
            result = registration_service.retry_job(17)

        self.assertTrue(result["ok"])
        self.assertEqual(701, result["operation_task_id"])
        self.assertEqual(702, result["run_id"])
        submit.assert_called_once_with(
            "native@example.com", trigger="registration_job_retry", parent_task_id=700,
        )
        legacy_create.assert_not_called()

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
        repository_payload = {
            "ok": True,
            "items": rows,
            "total": len(rows),
            "page": 1,
            "page_size": 20,
            "revision": "2:test",
            "facets": {},
            "status_counts": {"success": 1, "running": 1, "active": 1},
            "progress_rows": rows,
        }
        with patch("webui.app.admin_repository.list_jobs", return_value=repository_payload):
            response = client.get(
                "/api/jobs?paged=1&page=1&page_size=20",
                headers={"X-Auth-Code": "test-auth"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["progress_batch"]["batch_id"], "new-batch")
        self.assertEqual(len(payload["progress_batch"]["items"]), 2)

    def test_jobs_api_passes_selected_progress_batch_to_repository(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        repository_payload = {
            "ok": True,
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "revision": "0:test",
            "facets": {},
            "status_counts": {"active": 0},
            "progress_rows": [],
            "progress_batches": [],
        }
        with patch("webui.app.admin_repository.list_jobs", return_value=repository_payload) as list_jobs:
            response = client.get(
                "/api/jobs?paged=1&page=1&page_size=20&progress_batch_id=older-batch",
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list_jobs.call_args.kwargs["progress_batch_id"], "older-batch")

    def test_jobs_api_passes_per_batch_debug_flag_to_service(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()
        fake_jobs = [{"id": 88, "batch_id": "debug-batch", "debug_enabled": True}]
        with patch("config.email.USE_EMAIL_SERVICE", False), patch(
            "config.register.REGISTER_EMAIL", "manual@example.com"
        ), patch(
            "config.roxybrowser.REGISTRATION_DRIVER", "roxy"
        ), patch(
            "webui.routes.jobs.svc.submit_registration", return_value=fake_jobs
        ) as submit:
            response = client.post(
                "/api/jobs",
                json={"count": 1, "workers": 4, "debug_enabled": True},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["debug_enabled"])
        submit.assert_called_once_with(count=1, workers=4, debug_enabled=True)

    def test_bulk_retry_uses_one_shared_batch(self):
        app = create_app(auth_code="test-auth")
        client = app.test_client()

        def fake_retry(job_id, workers=None, **kwargs):
            return {
                "ok": True,
                "created": True,
                "job": {"id": job_id + 100, "batch_id": kwargs["batch_id"]},
                "batch": kwargs,
            }

        with patch("webui.app.svc.retry_job", side_effect=fake_retry) as retry_job:
            response = client.post(
                "/api/jobs/retry-bulk",
                json={"job_ids": [11, 12], "workers": 3},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["started_count"], 2)
        self.assertTrue(payload["batch_id"])
        calls = retry_job.call_args_list
        self.assertEqual(calls[0].kwargs["batch_id"], calls[1].kwargs["batch_id"])
        self.assertEqual([call.kwargs["batch_index"] for call in calls], [1, 2])
        self.assertTrue(all(call.kwargs["batch_size"] == 2 for call in calls))

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
