"""注册任务链的 Roxy 2FA 覆盖只作用于冻结的浏览器子任务。"""
from contextlib import ExitStack
import copy
import unittest
from unittest.mock import patch

from core import operation_task_store
from core.codex import retry_service as codex_retry_service
from core.operations import task_gateway
from core.registration import service as registration_service


class RegistrationRoxyRetryWorkerTests(unittest.TestCase):
    def _run_worker(self, snapshot, *, nested=False):
        job = {"id": 31, "root_job_id": 21, "attempt_id": 41, "account_id": 44, "status": "running"}
        if snapshot is not None:
            if nested:
                job["data"] = {"config_snapshot": copy.deepcopy(snapshot)}
            else:
                job["config_snapshot"] = copy.deepcopy(snapshot)
        account = {"id": 44, "email": "unit@example.test"}
        with ExitStack() as stack:
            for name in ("_activate_job", "_deactivate_job", "_ensure_registration_run_context",
                         "_bind_progress_route_context", "_persist_job_progress", "_finish_registration_run"):
                stack.enter_context(patch.object(registration_service, name))
            stack.enter_context(patch.object(registration_service.db, "get_job", side_effect=lambda _id: copy.deepcopy(job)))
            stack.enter_context(patch.object(registration_service.db, "get_account", return_value=account))
            stack.enter_context(patch.object(registration_service, "_claim_job_for_worker", return_value=True))
            stack.enter_context(patch.object(registration_service.db, "finish_job_progress"))
            stack.enter_context(patch.object(registration_service.db, "update_job", side_effect=lambda _id, **fields: job.update(fields)))
            stack.enter_context(patch.object(registration_service, "registration_config_snapshot", return_value={
                "registration_driver": "protocol_oss_2", "proxy_country": "US",
                "password_enabled": True, "twofa_enabled": True, "plan_check_enabled": True,
            }))
            stack.enter_context(patch("config.account.completion_settings", return_value={
                "plan_check_driver": "protocol", "password_proxy_mode": "pool",
                "twofa_proxy_mode": "pool", "plan_check_proxy_mode": "pool",
            }))
            stack.enter_context(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
            stack.enter_context(patch.object(operation_task_store, "find_task_by_source", return_value=None))
            submit = stack.enter_context(patch.object(task_gateway, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 501, "run_id": 601,
            }))
            worker = stack.enter_context(patch.object(codex_retry_service, "run_twofa_worker"))
            stack.enter_context(patch.object(codex_retry_service, "release"))
            finish = stack.enter_context(patch.object(registration_service.account_task_store, "finish_task"))
            registration_service._run_twofa_retry_job(31, "/tmp/unit-roxy-twofa.log", "unit@example.test", 44, 81)
        submit.assert_called_once()
        worker.assert_not_called()
        self.assertEqual(job["status"], "partial_success")
        self.assertEqual(job["registration_account_task_id"], 501)
        self.assertEqual(finish.call_args.kwargs["result_summary"], {"operation_task_id": 501, "run_id": 601})
        values = submit.call_args.kwargs
        self.assertEqual(values["task_type"], "account_setup_retry")
        self.assertEqual(values["account_id"], 44)
        self.assertEqual(values["source_id"], "registration-account-setup:31")
        self.assertEqual(values["data"]["source_job_id"], 31)
        self.assertEqual(values["data"]["registration_attempt_id"], 41)
        self.assertEqual(values["data"]["required_steps"], ["password", "plan_check", "twofa"])
        return values

    def _run_legacy_country_guard(self, snapshot, *, nested=False, expected_status="failed"):
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
            stack.enter_context(patch.object(registration_service.db, "get_account", return_value={
                "id": 44, "email": "unit@example.test",
            }))
            stack.enter_context(patch.object(registration_service, "_claim_job_for_worker", return_value=True))
            stack.enter_context(patch.object(registration_service.db, "finish_job_progress"))
            stack.enter_context(patch.object(registration_service.db, "update_job", side_effect=lambda _id, **fields: job.update(fields)))
            stack.enter_context(patch.object(registration_service, "is_stop_requested", return_value=False))
            stack.enter_context(patch("config.register.REGISTRATION_COUNTRY", "JP"))
            stack.enter_context(patch("config.account.completion_settings", return_value={
                "plan_check_driver": "protocol", "password_proxy_mode": "pool",
                "twofa_proxy_mode": "pool", "plan_check_proxy_mode": "pool",
            }))
            stack.enter_context(patch("core.runtime.capabilities.account_setup_unavailable", return_value=None))
            stack.enter_context(patch.object(operation_task_store, "find_task_by_source", return_value=None))
            submit = stack.enter_context(patch.object(task_gateway, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 501, "run_id": 601,
            }))
            retry = stack.enter_context(patch.object(operation_task_store, "retry_runtime_task"))
            notify = stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
            options = stack.enter_context(patch.object(registration_service, "registration_options_for_job",
                                                      wraps=registration_service.registration_options_for_job))
            worker = stack.enter_context(patch.object(codex_retry_service, "run_twofa_worker", return_value={
                "ok": True, "status": "success",
            }))
            stack.enter_context(patch.object(codex_retry_service, "release"))
            stack.enter_context(patch.object(registration_service.account_task_store, "finish_task"))
            registration_service._run_twofa_retry_job(31, "/tmp/unit-roxy-twofa.log", "unit@example.test", 44, 81)
        self.assertEqual(job["status"], expected_status)
        if expected_status == "failed":
            worker.assert_not_called()
            submit.assert_not_called()
            retry.assert_not_called()
            notify.assert_not_called()
            options.assert_not_called()
            self.assertIn("国家覆盖", job["error"])
            return None
        return worker.call_args.kwargs

    def test_roxy_browser_snapshot_selects_existing_browser_executors(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                kwargs = self._run_worker({"registration_driver": "roxy", "twofa_driver": "browser"}, nested=nested)
                self.assertEqual(kwargs["config_snapshot"]["twofa_driver"], "browser")
                self.assertEqual(kwargs["config_snapshot"]["password_driver"], "roxy")
                self.assertEqual(kwargs["data"]["task_trigger"], "registration_job_retry")

    def test_legacy_or_unselected_modes_keep_worker_defaults(self):
        for snapshot, password_driver, twofa_driver in (
            (None, "protocol", "protocol"),
            ({"registration_driver": "protocol_oss_2", "twofa_driver": "browser"}, "protocol", "protocol"),
            ({"registration_driver": "roxy", "twofa_driver": "auto"}, "roxy", "auto"),
            ({"registration_driver": "roxy", "twofa_driver": "protocol"}, "roxy", "protocol"),
            ({"registration_driver": "roxy"}, "roxy", "browser"),
        ):
            with self.subTest(snapshot=snapshot):
                kwargs = self._run_worker(snapshot)
                self.assertEqual(kwargs["config_snapshot"]["password_driver"], password_driver)
                self.assertEqual(kwargs["config_snapshot"]["twofa_driver"], twofa_driver)
                self.assertIsNone(kwargs["data"]["proxy_country_override"])

    def test_explicit_roxy_retry_country_reaches_account_worker(self):
        for nested in (False, True):
            with self.subTest(nested=nested):
                kwargs = self._run_worker({
                    "registration_driver": "roxy", "twofa_driver": "browser",
                    "proxy_country": "JP", "retry_proxy_country_override": "JP",
                }, nested=nested)
                self.assertEqual(kwargs["data"]["proxy_country_override"], "JP")

    def test_ordinary_country_snapshot_does_not_override_account_worker(self):
        for snapshot in (
            {"registration_driver": "roxy", "proxy_country": "JP"},
            {"registration_driver": "protocol", "proxy_country": "JP", "retry_proxy_country_override": "JP"},
        ):
            with self.subTest(snapshot=snapshot):
                kwargs = self._run_worker(snapshot)
                self.assertIsNone(kwargs["data"]["proxy_country_override"])

    def test_invalid_or_mismatched_country_permission_blocks_account_worker(self):
        for nested in (False, True):
            for country, marker in (("JP", "IN"), ("JP", "ZZ"), ("JP", ""),
                                    ("JP", 1), ("JP", True), (None, "JP")):
                with self.subTest(nested=nested, country=country, marker=marker):
                    self._run_legacy_country_guard({
                        "registration_driver": "roxy", "twofa_driver": "browser",
                        "proxy_country": country, "retry_proxy_country_override": marker,
                    }, nested=nested, expected_status="failed")


if __name__ == "__main__":
    unittest.main()
