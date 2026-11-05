"""注册任务链的 Roxy 2FA 覆盖只作用于冻结的浏览器子任务。"""
from contextlib import ExitStack
import copy
import unittest
from unittest.mock import patch

from core.codex import retry_service as codex_retry_service
from core.registration import service as registration_service


class RegistrationRoxyRetryWorkerTests(unittest.TestCase):
    def _run_worker(self, snapshot, *, nested=False, expected_status="success"):
        job = {"id": 31, "root_job_id": 21, "attempt_id": 41, "account_id": 44, "status": "running"}
        if snapshot is not None:
            if nested:
                job["data"] = {"config_snapshot": copy.deepcopy(snapshot)}
            else:
                job["config_snapshot"] = copy.deepcopy(snapshot)
        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context",
                         "_bind_progress_route_context", "_persist_job_progress", "_finish_registration_run"):
                stack.enter_context(patch.object(registration_service, name))
            stack.enter_context(patch.object(registration_service.db, "get_job", side_effect=lambda _id: dict(job)))
            stack.enter_context(patch.object(registration_service, "_claim_job_for_worker", return_value=True))
            stack.enter_context(patch.object(registration_service.db, "finish_job_progress"))
            stack.enter_context(patch.object(registration_service.db, "update_job", side_effect=lambda _id, **fields: job.update(fields)))
            stack.enter_context(patch.object(registration_service, "is_stop_requested", return_value=False))
            stack.enter_context(patch.object(registration_service, "_registration_proxy_correlation", return_value={
                "account_id": 44, "operation_task_id": 501, "operation_run_id": 601,
            }))
            worker = stack.enter_context(patch.object(codex_retry_service, "run_twofa_worker", return_value={
                "ok": True, "status": "success",
            }))
            stack.enter_context(patch.object(codex_retry_service, "release"))
            stack.enter_context(patch.object(registration_service.account_task_store, "finish_task"))
            registration_service._run_twofa_retry_job(31, "/tmp/unit-roxy-twofa.log", "unit@example.test", 44, 81)
        self.assertEqual(job["status"], expected_status)
        if expected_status == "failed":
            worker.assert_not_called()
            self.assertIn("国家覆盖", job["error"])
            return None
        return worker.call_args.kwargs

    def test_roxy_browser_snapshot_selects_existing_browser_executors(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                kwargs = self._run_worker({"registration_driver": "roxy", "twofa_driver": "browser"}, nested=nested)
                self.assertEqual(kwargs["twofa_driver_override"], "browser")
                self.assertEqual(kwargs["password_driver_override"], "roxy")
                self.assertEqual(kwargs["task_id"], 81)
                self.assertEqual(kwargs["task_trigger"], "registration_job_retry")
                self.assertFalse(kwargs["clear_log"])

    def test_legacy_or_unselected_modes_keep_worker_defaults(self):
        for snapshot in (None, {"registration_driver": "protocol_oss_2", "twofa_driver": "browser"},
                         {"registration_driver": "roxy", "twofa_driver": "auto"},
                         {"registration_driver": "roxy", "twofa_driver": "protocol"},
                         {"registration_driver": "roxy"}):
            with self.subTest(snapshot=snapshot):
                kwargs = self._run_worker(snapshot)
                self.assertNotIn("twofa_driver_override", kwargs)
                self.assertNotIn("password_driver_override", kwargs)

    def test_explicit_roxy_retry_country_reaches_account_worker(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                kwargs = self._run_worker({
                    "registration_driver": "roxy", "twofa_driver": "browser",
                    "proxy_country": "JP", "retry_proxy_country_override": "JP",
                }, nested=nested)
                self.assertEqual(kwargs["proxy_country_override"], "JP")

    def test_ordinary_country_snapshot_does_not_override_account_worker(self):
        for snapshot in (
            {"registration_driver": "roxy", "proxy_country": "JP"},
            {"registration_driver": "protocol", "proxy_country": "JP", "retry_proxy_country_override": "JP"},
        ):
            with self.subTest(snapshot=snapshot):
                kwargs = self._run_worker(snapshot)
                self.assertNotIn("proxy_country_override", kwargs)

    def test_invalid_or_mismatched_country_permission_blocks_account_worker(self):
        for nested in (False, True):
            for country, marker in (("JP", "IN"), ("JP", "ZZ"), ("JP", ""),
                                    ("JP", 1), ("JP", True), (None, "JP")):
                with self.subTest(nested=nested, country=country, marker=marker):
                    self._run_worker({
                        "registration_driver": "roxy", "twofa_driver": "browser",
                        "proxy_country": country, "retry_proxy_country_override": marker,
                    }, nested=nested, expected_status="failed")


if __name__ == "__main__":
    unittest.main()
