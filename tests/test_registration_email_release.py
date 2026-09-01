# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import registration_service as svc


class RegistrationEmailReleaseTests(unittest.TestCase):
    def test_disable_job_email_marks_email_disabled(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            changed = svc._disable_job_email("alias@icloud.com", "password page")

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@icloud.com",
            status="disabled",
            note="自动停用: password page",
        )

    def test_disable_job_email_without_email_is_noop(self):
        with patch("core.email_provider.release_email") as release:
            self.assertFalse(svc._disable_job_email("", "reason"))

        release.assert_not_called()

    def test_completed_resume_marks_email_used_again(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            changed = svc._mark_completed_resume_email("alias@icloud.com", 347)

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@icloud.com",
            status="used",
            note="继续注册已完成，已绑定账号 #347",
        )

    def test_completed_initial_registration_marks_email_used(self):
        with patch("core.email_provider.release_email", return_value="email_butler") as release:
            changed = svc._mark_completed_registration_email("alias@example.com", 348)

        self.assertTrue(changed)
        release.assert_called_once_with(
            "alias@example.com",
            status="used",
            note="注册已完成，已绑定账号 #348",
        )

    def _run_job(self, result=None, error=None):
        job = {
            "id": 1,
            "status": "pending",
            "email_source": "icloud_hide",
        }
        proxy = SimpleNamespace(
            provider="test",
            endpoint="127.0.0.1:8080",
            exit_ip="127.0.0.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://127.0.0.1:8080",
        )

        def run_registration(**_kwargs):
            if error is not None:
                raise error
            return result

        with tempfile.TemporaryDirectory() as td, patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(
            svc.db, "finish_job_progress"
        ) as finish_progress, patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(
            svc.db, "update_account_registration_proxy"
        ), patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ), patch.object(
            svc, "_release_unconsumed_job_email"
        ) as release_email, patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ), patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", side_effect=run_registration
        ):
            svc._run_one_job(1, str(Path(td) / "job.log"))
        return release_email, update_progress, finish_progress

    def test_returned_failure_is_not_released_twice_by_service(self):
        release_email, _update_progress, _finish_progress = self._run_job(
            result={"success": False, "email": "alias@icloud.com", "error": "browser failed"}
        )
        release_email.assert_not_called()

    def test_returned_success_closes_initial_registration_email(self):
        with patch("core.email_provider.release_email", return_value="icloud_hide") as release:
            self._run_job(
                result={
                    "success": True,
                    "registration_success": True,
                    "postprocess_success": True,
                    "email": "alias@icloud.com",
                    "account_id": 42,
                    "access_token": "token",
                }
            )

        release.assert_called_once_with(
            "alias@icloud.com",
            status="used",
            note="注册已完成，已绑定账号 #42",
        )

    def test_unhandled_registration_exception_uses_service_fallback(self):
        release_email, _update_progress, _finish_progress = self._run_job(error=RuntimeError("unexpected crash"))
        release_email.assert_called_once()

    def test_saved_pending_account_fails_current_stage_before_skipping_rest(self):
        _release_email, update_progress, finish_progress = self._run_job(
            result={
                "success": False,
                "registration_pending": True,
                "email": "alias@icloud.com",
                "account_id": 42,
                "access_token": "",
                "error": "验证码等待超时",
            }
        )

        update_progress.assert_any_call(
            1,
            "email_otp",
            state="failed",
            detail="验证码等待超时",
        )
        finish_progress.assert_called_with(1, success=True)

    def test_transient_proxy_failure_reacquires_fresh_lease(self):
        job = {
            "id": 1,
            "status": "pending",
            "email_source": "icloud_hide",
        }
        proxy1 = SimpleNamespace(
            provider="1024proxy",
            endpoint="1.1.1.1:8080",
            exit_ip="1.1.1.1",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://1.1.1.1:8080",
        )
        proxy2 = SimpleNamespace(
            provider="1024proxy",
            endpoint="2.2.2.2:8080",
            exit_ip="2.2.2.2",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:01"),
            expires_at=None,
            proxy_url="http://2.2.2.2:8080",
        )
        transient = {
            "success": False,
            "email": "alias@icloud.com",
            "error": "RuntimeError: 邮箱提交/认证跳转超过总预算 60 秒，ERR_TUNNEL_CONNECTION_FAILED",
        }
        success = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "alias@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "begin_job_route_attempt"
        ) as begin_route_attempt, patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ), patch.object(svc, "_registration_proxy_retry_limit", return_value=1), patch.object(
            svc, "_registration_proxy_retry_delay", return_value=0
        ), patch(
            "core.proxy_provider.acquire_registration_proxy", side_effect=[proxy1, proxy2]
        ) as acquire_proxy, patch(
            "core.proxy_provider.release_proxy"
        ) as release_proxy, patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", side_effect=[transient, success]
        ) as run_registration:
            svc._run_one_job(1, str(Path(td) / "job.log"))

        self.assertEqual(run_registration.call_count, 2)
        begin_route_attempt.assert_called_once()
        self.assertEqual(acquire_proxy.call_count, 2)
        self.assertEqual(acquire_proxy.call_args_list[1].kwargs["batch_id"], None)
        release_proxy.assert_any_call(proxy1, reason="registration_proxy_retry_1")
        release_proxy.assert_any_call(proxy2, reason="pending")
        stage_transitions = [
            (call.args[1], call.kwargs.get("state"))
            for call in update_progress.call_args_list
        ]
        self.assertEqual(stage_transitions, [
            ("network", "running"),
            ("network", "success"),
            ("email", "running"),
            ("email", "success"),
            ("network", "running"),
            ("network", "success"),
            ("email", "running"),
            ("email", "success"),
        ])

    def test_proxy_acquisition_retries_before_registration(self):
        proxy = SimpleNamespace(
            provider="1024proxy",
            endpoint="1.1.1.1:8080",
            exit_ip="1.1.1.1",
            region="US",
            proxy_url="http://1.1.1.1:8080",
        )
        acquire_proxy = unittest.mock.Mock(
            side_effect=[RuntimeError("1024Proxy 获取失败：连接超时"), proxy]
        )
        with patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ) as update_progress, patch.object(
            svc.db, "begin_job_route_attempt"
        ) as begin_route_attempt, patch.object(
            svc, "_registration_proxy_retry_limit", return_value=1
        ), patch.object(
            svc, "_registration_proxy_retry_delay", return_value=0
        ), patch.object(
            svc, "check_stop_requested"
        ), patch.object(svc.time, "sleep"):
            result = svc._acquire_registration_proxy_with_retries(
                acquire_proxy=acquire_proxy,
                job_id=17,
                batch_id=None,
                batch_size=1,
                batch_workers=1,
                progress_callback=None,
                log_logger=svc.logger,
            )

        self.assertIs(result, proxy)
        self.assertEqual(acquire_proxy.call_count, 2)
        begin_route_attempt.assert_called_once_with(
            17,
            retry_kind="proxy_acquisition",
            retry_reason="RuntimeError: 1024Proxy 获取失败：连接超时",
        )
        self.assertEqual(
            [
                (call.args[1], call.kwargs["state"])
                for call in update_progress.call_args_list
            ],
            [("network", "failed"), ("network", "running")],
        )

    def test_manual_registration_retry_uses_independent_proxy_allocation(self):
        job = {
            "id": 2,
            "status": "pending",
            "job_type": "registration",
            "parent_job_id": 1,
            "root_job_id": 1,
            "batch_id": "source-batch",
            "batch_index": 3,
            "batch_size": 5,
            "batch_workers": 5,
            "email_source": "icloud_hide",
        }
        proxy = SimpleNamespace(
            provider="1024proxy",
            endpoint="2.2.2.2:8080",
            exit_ip="2.2.2.2",
            region="US",
            acquired_at=SimpleNamespace(isoformat=lambda **_kwargs: "2026-08-13T00:00:00"),
            expires_at=None,
            proxy_url="http://2.2.2.2:8080",
        )
        result = {
            "success": True,
            "registration_success": True,
            "postprocess_success": True,
            "email": "alias@icloud.com",
            "account_id": 42,
            "access_token": "token",
        }

        with tempfile.TemporaryDirectory() as td, patch.object(
            svc.db, "get_job", return_value=job
        ), patch.object(svc.db, "update_job"), patch.object(
            svc.db, "update_job_progress"
        ), patch.object(svc.db, "finish_job_progress"), patch.object(
            svc.db, "claim_job_for_execution", return_value=True
        ), patch.object(svc.db, "update_account_registration_proxy"), patch.object(
            svc, "_prepare_registration_args", return_value=("alias@icloud.com", "Test", "1990-01-01")
        ), patch.object(svc, "_release_unconsumed_job_email"), patch(
            "core.proxy_provider.acquire_registration_proxy", return_value=proxy
        ) as acquire_proxy, patch(
            "core.proxy_provider.release_proxy"
        ), patch(
            "core.proxy_provider.finalize_registration_proxy_batch"
        ) as finalize_batch, patch(
            "core.proxy_provider.mask_endpoint", return_value="masked"
        ), patch(
            "core.proxy_provider.mask_ip", return_value="masked"
        ), patch(
            "core.registration.dispatcher.run_registration", return_value=result
        ):
            svc._run_one_job(2, str(Path(td) / "job.log"))

        acquire_proxy.assert_called_once()
        self.assertEqual(acquire_proxy.call_args.kwargs["batch_id"], None)
        self.assertEqual(acquire_proxy.call_args.kwargs["batch_size"], 1)
        self.assertEqual(acquire_proxy.call_args.kwargs["batch_workers"], 1)
        finalize_batch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
