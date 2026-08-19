# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import registration_service as svc


class RegistrationEmailReleaseTests(unittest.TestCase):
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
            "main.run_registration", side_effect=run_registration
        ):
            svc._run_one_job(1, str(Path(td) / "job.log"))
        return release_email, update_progress, finish_progress

    def test_returned_failure_is_not_released_twice_by_service(self):
        release_email, _update_progress, _finish_progress = self._run_job(
            result={"success": False, "email": "alias@icloud.com", "error": "browser failed"}
        )
        release_email.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
