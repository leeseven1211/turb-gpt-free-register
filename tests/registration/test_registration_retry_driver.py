"""单任务继续邮箱验证时的注册驱动选择边界。"""

from __future__ import annotations

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core import db
from core.operations import task_gateway
from core.registration import service as registration_service
from webui.app import create_app


class RegistrationRetryDriverTests(unittest.TestCase):
    def _facts(self):
        source = {
            "id": 21,
            "root_job_id": 21,
            "attempt_id": 70,
            "account_id": 44,
            "status": "partial_success",
            "job_type": "registration",
            "email": "pending@example.test",
            "email_source": "icloud_hide",
            "config_snapshot": {
                "registration_driver": "protocol",
                "password_enabled": True,
                "twofa_enabled": True,
            },
            "batch_id": "original-batch",
            "batch_index": 3,
            "batch_size": 10,
            "batch_workers": 2,
        }
        account = {
            "id": 44,
            "email": "pending@example.test",
            "access_token": "",
            "extra_json": {
                "registration_checkpoint": "email_verification_pending",
                "account_password": "SavedPassword!123",
            },
        }
        attempt = {
            "id": 70,
            "root_job_id": 21,
            "email": "pending@example.test",
            "email_snapshot": "pending@example.test",
            "checkpoint": "otp_started",
            "target_status": "request_unknown",
            "remote_identity_state": "confirmed",
            "remote_account_state": "request_unknown",
            "account_id": None,
        }
        return source, account, attempt

    def _retry(self, source, account, attempt, *, action="registration_resume", child=None,
               debug_patch=None, executor=None, driver_choice="roxy", **kwargs):
        created = child is None
        child = child or {
            "id": 22,
            "status": "pending",
            "job_type": "registration_resume",
            "log_file": "/tmp/test-registration-retry.log",
        }
        executor = executor if executor is not None else Mock()

        def patch_child(ident, **changes):
            self.assertEqual(ident, child["id"])
            child.update(changes)
            return True

        debug_patch = debug_patch if debug_patch is not None else Mock(side_effect=patch_child)
        with ExitStack() as stack:
            stack.enter_context(patch.object(db, "get_job", side_effect=lambda ident: child if ident == child["id"] else source))
            stack.enter_context(patch.object(db, "update_job", side_effect=patch_child))
            stack.enter_context(patch("core.registration.debug.patch_job", new=debug_patch))
            stack.enter_context(patch.object(registration_service, "_account_for_job", return_value=account))
            stack.enter_context(patch.object(registration_service, "_enrich_account_registration_state", side_effect=lambda value: value))
            stack.enter_context(patch.object(registration_service, "get_retry_info", return_value={
                "retryable": True,
                "retry_action": action,
            }))
            stack.enter_context(patch.object(registration_service, "_read_linked_attempt_for_job", return_value=(attempt, False)))
            create_retry = stack.enter_context(patch.object(db, "create_retry_job", return_value=(child, created)))
            stack.enter_context(patch.object(registration_service, "_enqueue_job", new=executor))
            stack.enter_context(patch.object(registration_service.codex_retry_service, "reserve", return_value=True))
            stack.enter_context(patch.object(registration_service.codex_retry_service, "release"))
            stack.enter_context(patch.object(registration_service.account_task_store, "create_task", return_value=77))
            native = stack.enter_context(patch.object(task_gateway, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 81, "run_id": 82,
            }))
            stack.enter_context(patch("core.operation_task_store.find_task_by_source", return_value=None))
            result = registration_service.retry_job(21, registration_driver=driver_choice, **kwargs)
            call = native.call_args if action == "twofa" else create_retry.call_args
        return result, call, executor

    def test_roxy_resume_overrides_only_new_child_snapshot(self):
        source, account, attempt = self._facts()
        original = copy.deepcopy(source)

        with patch("config.register.REGISTRATION_COUNTRY", "US"):
            result, create_call, executor = self._retry(source, account, attempt)

        self.assertTrue(result["ok"])
        self.assertEqual(create_call.kwargs["job_type"], "registration_resume")
        self.assertEqual(create_call.kwargs["email"], "pending@example.test")
        self.assertEqual(create_call.kwargs["account_id"], 44)
        self.assertEqual(create_call.kwargs["data"]["config_snapshot"], {
            "registration_driver": "roxy",
            "password_enabled": True,
            "password_mode": "password",
            "twofa_enabled": True,
            "proxy_country": "US",
        })
        self.assertEqual(source, original)
        executor.assert_called_once()

    def test_open_source_resume_keeps_frozen_driver_and_password_mode(self):
        for driver in ("protocol_oss", "protocol_oss_2", "roxy_oss"):
            with self.subTest(driver=driver):
                source, account, attempt = self._facts()
                source["config_snapshot"] = {
                    "registration_driver": driver,
                    "password_enabled": True,
                    "password_mode": "password",
                    "twofa_enabled": True,
                }

                result, create_call, executor = self._retry(
                    source,
                    account,
                    attempt,
                    driver_choice=None,
                )

                self.assertTrue(result["ok"])
                snapshot = create_call.kwargs["data"]["config_snapshot"]
                self.assertEqual(snapshot["registration_driver"], "roxy" if driver == "roxy_oss" else "protocol_oss_2")
                self.assertTrue(snapshot["password_enabled"])
                self.assertEqual(snapshot["password_mode"], "password")
                executor.assert_called_once()

    def test_roxy_resume_rejects_non_resume_and_unverified_identity(self):
        for changed, action in (
            ({}, "codex"),
            ({}, "plan_check"),
            ({"account": {"access_token": "already-complete"}}, "registration_resume"),
            ({"account": {"extra_json": {"registration_checkpoint": "completed", "account_password": "SavedPassword!123"}}}, "registration_resume"),
            ({"account": {"extra_json": {"registration_checkpoint": "email_verification_pending"}}}, "registration_resume"),
            ({"account": {"email": "different@example.test"}}, "registration_resume"),
            ({"source": {"attempt_id": None}}, "registration_resume"),
            ({"attempt": {"root_job_id": 99}}, "registration_resume"),
            ({"attempt": {"email": "different@example.test"}}, "registration_resume"),
            ({"attempt": {"checkpoint": "core_persisted"}}, "registration_resume"),
        ):
            with self.subTest(changed=changed, action=action):
                source, account, attempt = self._facts()
                source.update(changed.get("source", {}))
                account.update(changed.get("account", {}))
                attempt.update(changed.get("attempt", {}))
                result, create_call, executor = self._retry(source, account, attempt, action=action)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], 409)
                self.assertIsNone(create_call)
                executor.assert_not_called()

    def test_roxy_registration_retry_keeps_original_identity_and_new_snapshot_only(self):
        source, _account, attempt = self._facts()
        source["account_id"] = None
        source["config_snapshot"]["registration_driver"] = "protocol_oss_2"
        original = copy.deepcopy(source)

        result, create_call, executor = self._retry(
            source, None, attempt, action="registration", debug_enabled=True,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(create_call.args, (21,))
        self.assertEqual(create_call.kwargs["job_type"], "registration")
        self.assertEqual(create_call.kwargs["email"], "pending@example.test")
        self.assertEqual(create_call.kwargs["email_source"], "icloud_hide")
        self.assertIsNone(create_call.kwargs["account_id"])
        self.assertEqual(create_call.kwargs["data"]["config_snapshot"]["registration_driver"], "roxy")
        self.assertEqual(source, original)
        self.assertIs(result["job"]["debug_enabled"], True)
        executor.assert_called_once_with(22, account_task_id=None)

    def test_roxy_setup_retry_uses_native_run_and_keeps_original_snapshot(self):
        source, account, attempt = self._facts()
        account["access_token"] = "unit-existing-token"
        source["config_snapshot"].update(registration_driver="protocol_oss_2", twofa_driver="protocol")
        original = copy.deepcopy(source)
        result, call, executor = self._retry(source, account, attempt, action="twofa", debug_enabled=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(call.kwargs["task_type"], "account_setup_retry")
        self.assertEqual(call.kwargs["config_snapshot"]["password_driver"], "roxy")
        self.assertEqual(call.kwargs["config_snapshot"]["twofa_driver"], "browser")
        self.assertIs(result["debug_enabled"], False)
        self.assertTrue(result["debug_warning"])
        self.assertEqual(call.kwargs["account_id"], 44)
        self.assertEqual(result["operation_task_id"], 81)
        self.assertEqual(source, original)
        executor.assert_not_called()

    def test_proto2_setup_retry_does_not_require_browser_or_legacy_worker(self):
        source, account, attempt = self._facts()
        account["access_token"] = "unit-existing-token"
        source["config_snapshot"].update(registration_driver="protocol_oss_2", twofa_driver="protocol")
        with patch("config.deployment.browser_enabled", return_value=False), patch(
            "config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", False,
        ):
            result, call, executor = self._retry(source, account, attempt, action="twofa", driver_choice=None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(call.kwargs["config_snapshot"]["password_driver"], "protocol")
        self.assertEqual(call.kwargs["config_snapshot"]["twofa_driver"], "protocol")
        self.assertIn("password", call.kwargs["data"]["required_steps"])
        executor.assert_not_called()

    def test_roxy_resume_does_not_reuse_active_protocol_child(self):
        source, account, attempt = self._facts()
        active = {
            "id": 22,
            "status": "pending",
            "job_type": "registration_resume",
            "data": {"config_snapshot": {"registration_driver": "protocol"}},
        }

        result, create_call, executor = self._retry(source, account, attempt, child=active)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 409)
        self.assertIsNotNone(create_call)
        executor.assert_not_called()

    def test_roxy_resume_reuses_active_same_driver_without_resubmission(self):
        source, account, attempt = self._facts()
        active = {"id": 22, "status": "running", "job_type": "registration_resume",
                  "config_snapshot": {"registration_driver": "roxy"}}
        result, _, executor = self._retry(source, account, attempt, child=active)
        self.assertTrue(result["ok"])
        self.assertTrue(result["reused"])
        self.assertEqual(result["job"]["id"], 22)
        executor.assert_not_called()

    def test_single_job_retry_api_passes_roxy_choice(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job", return_value={"ok": True, "created": True}) as retry:
            response = client.post(
                "/api/jobs/21/retry",
                json={"registration_driver": "roxy", "workers": 2},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 200)
        retry.assert_called_once_with(21, workers=2, registration_driver="roxy")

    def test_single_job_retry_api_rejects_unknown_driver(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job") as retry:
            response = client.post(
                "/api/jobs/21/retry",
                json={"registration_driver": "unknown"},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 400)
        retry.assert_not_called()

    def test_single_retry_can_enable_capture_without_changing_source(self):
        source, account, attempt = self._facts()
        original = copy.deepcopy(source)
        submitted_jobs = []
        executor = Mock()
        executor.side_effect = lambda job_id, **_kwargs: submitted_jobs.append(copy.deepcopy(db.get_job(job_id)))
        result, _, executor = self._retry(source, account, attempt, debug_enabled=True, executor=executor)
        self.assertTrue(result["ok"])
        self.assertEqual(source, original)
        self.assertIs(result["job"]["debug_enabled"], True)
        self.assertTrue(result["job"]["debug_policy"]["hold_on_failure"])
        executor.assert_called_once()
        self.assertIs(submitted_jobs[0]["debug_enabled"], True)

    def test_missing_debug_option_still_inherits_source_capture(self):
        source, account, attempt = self._facts()
        source["debug_enabled"] = True
        result, _, executor = self._retry(source, account, attempt)
        self.assertTrue(result["ok"])
        self.assertIs(result["job"]["debug_enabled"], True)
        executor.assert_called_once()

    def test_explicit_debug_off_overrides_inherited_capture(self):
        source, account, attempt = self._facts()
        source["debug_enabled"] = True
        debug_patch = Mock()
        result, _, _ = self._retry(source, account, attempt, debug_patch=debug_patch, debug_enabled=False)
        self.assertTrue(result["ok"])
        debug_patch.assert_not_called()

    def test_debug_setup_failure_closes_child_without_submitting_executor(self):
        for debug_patch in (
            Mock(return_value=False),
            Mock(return_value=True),
            Mock(side_effect=RuntimeError("测试调试元数据保存失败")),
        ):
            with self.subTest(debug_patch=debug_patch):
                source, account, attempt = self._facts()
                original = copy.deepcopy(source)
                result, _, executor = self._retry(
                    source, account, attempt, debug_patch=debug_patch, debug_enabled=True,
                )
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], 500)
                self.assertEqual(result["job"]["status"], "failed")
                self.assertTrue(result["job"]["completed_at"])
                self.assertEqual(source, original)
                executor.assert_not_called()

    def test_debug_retry_does_not_reuse_an_active_run_without_capture(self):
        source, account, attempt = self._facts()
        child = {"id": 22, "status": "running", "job_type": "registration_resume",
                 "config_snapshot": {"registration_driver": "roxy"}}
        result, _, executor = self._retry(source, account, attempt, child=child, debug_enabled=True)
        self.assertEqual(result["status"], 409)
        executor.assert_not_called()

    def test_retry_debug_flag_is_strict_and_passes_to_service(self):
        client = create_app(auth_code="test-auth").test_client()
        for enabled in (True, False, "true", None):
            with self.subTest(enabled=enabled), patch("webui.app.svc.retry_job", return_value={"ok": True}) as retry:
                response = client.post("/api/jobs/21/retry", json={"workers": 1, "debug_enabled": enabled},
                                       headers={"X-Auth-Code": "test-auth"})
                if type(enabled) is bool:
                    self.assertEqual(response.status_code, 200)
                    retry.assert_called_once_with(21, workers=1, debug_enabled=enabled)
                else:
                    self.assertEqual(response.status_code, 400)
                    retry.assert_not_called()

    def test_retry_apis_reject_non_object_json_bodies(self):
        client = create_app(auth_code="test-auth").test_client()
        for path, payload in (
            ("/api/jobs/21/retry", []),
            ("/api/jobs/21/retry", False),
            ("/api/jobs/retry-bulk", []),
            ("/api/jobs/retry-bulk", False),
        ):
            with self.subTest(path=path, payload=payload), patch("webui.app.svc.retry_job") as retry:
                response = client.post(
                    path,
                    json=payload,
                    headers={"X-Auth-Code": "test-auth"},
                )
                self.assertEqual(response.status_code, 400)
                retry.assert_not_called()

    def test_bulk_retry_api_rejects_driver_choice(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job") as retry:
            response = client.post(
                "/api/jobs/retry-bulk",
                json={"job_ids": [21], "registration_driver": "roxy"},
                headers={"X-Auth-Code": "test-auth"},
            )

        self.assertEqual(response.status_code, 400)
        retry.assert_not_called()

    def test_bulk_retry_preserves_explicit_debug_setting_for_each_job(self):
        client = create_app(auth_code="test-auth").test_client()
        for enabled in (True, False):
            with self.subTest(enabled=enabled), patch("webui.app.svc.retry_job", return_value={"ok": True}) as retry:
                response = client.post("/api/jobs/retry-bulk", json={
                    "job_ids": [21, 23], "workers": 1, "debug_enabled": enabled,
                }, headers={"X-Auth-Code": "test-auth"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([call.kwargs for call in retry.call_args_list], [
                    {"workers": 1, "debug_enabled": enabled},
                    {"workers": 1, "debug_enabled": enabled},
                ])

    def test_bulk_retry_rejects_invalid_debug_flag_before_submitting_any_job(self):
        client = create_app(auth_code="test-auth").test_client()
        for enabled in ("true", None, 1):
            with self.subTest(enabled=enabled), patch("webui.app.svc.retry_job") as retry:
                response = client.post("/api/jobs/retry-bulk", json={
                    "job_ids": [21, 23], "debug_enabled": enabled,
                }, headers={"X-Auth-Code": "test-auth"})
                self.assertEqual(response.status_code, 400)
                retry.assert_not_called()

    def test_setup_retry_keeps_debug_request_with_native_operation(self):
        source, account, attempt = self._facts()
        account["access_token"] = "unit-existing-token"
        result, call, executor = self._retry(source, account, attempt, action="twofa",
                                            driver_choice=None, debug_enabled=True)
        self.assertTrue(result["ok"], result)
        self.assertIs(result["debug_enabled"], False)
        self.assertTrue(result["debug_warning"])
        self.assertEqual(call.kwargs["data"]["source_job_id"], source["id"])
        executor.assert_not_called()

    def test_debug_request_does_not_block_native_codex_or_plan_retry(self):
        for action in ("codex", "plan_check"):
            with self.subTest(action=action):
                source, account, attempt = self._facts()
                account["access_token"] = "unit-existing-token"
                with patch("core.codex.operation_service.submit", return_value={
                    "accepted": True, "task_id": 81, "run_id": 82,
                }), patch("core.operation_task_store.find_task_by_source", return_value=None), patch(
                    "core.accounts.plans.service.enqueue_account_plan_check", return_value={
                        "accepted": True, "task_id": 83, "run_id": 84,
                    },
                ):
                    result, _, executor = self._retry(source, account, attempt, action=action,
                                                     driver_choice=None, debug_enabled=True)
                self.assertTrue(result["ok"], result)
                self.assertIs(result["debug_enabled"], False)
                self.assertTrue(result["debug_warning"])
                executor.assert_not_called()

    def test_proxy_country_override_changes_only_new_roxy_child(self):
        for action in ("registration", "registration_resume", "twofa"):
            with self.subTest(action=action):
                source, account, attempt = self._facts()
                source["config_snapshot"].update(registration_driver="roxy", proxy_country="IN")
                original_source, original_attempt = copy.deepcopy(source), copy.deepcopy(attempt)
                if action == "registration":
                    account = None
                elif action == "twofa":
                    account["access_token"] = "unit-existing-token"
                result, create_call, executor = self._retry(
                    source, account, attempt, action=action, driver_choice=None, proxy_country="JP",
                )
                self.assertTrue(result["ok"], result)
                if action == "twofa":
                    self.assertEqual(create_call.kwargs["data"]["proxy_country_override"], "JP")
                    executor.assert_not_called()
                else:
                    snapshot = create_call.kwargs["data"]["config_snapshot"]
                    self.assertEqual(snapshot["proxy_country"], "JP")
                    self.assertEqual(snapshot["retry_proxy_country_override"], "JP")
                    executor.assert_called_once()
                self.assertEqual(create_call.kwargs["email"], source["email"])
                self.assertEqual(source, original_source)
                self.assertEqual(attempt, original_attempt)

    def test_proxy_country_override_rejects_invalid_values_before_storage(self):
        for country in ("", "  ", "ZZ", "Japan", 1, True, [], {}):
            with self.subTest(country=country), patch.object(db, "get_job") as read:
                result = registration_service.retry_job(21, proxy_country=country)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], 400)
                read.assert_not_called()

    def test_proxy_country_override_requires_roxy_registration_or_twofa_action(self):
        for driver, action in (("protocol_oss_2", "registration"),
                               ("roxy", "codex"), ("roxy", "plan_check")):
            with self.subTest(driver=driver, action=action):
                source, account, attempt = self._facts()
                source["config_snapshot"]["registration_driver"] = driver
                result, create_call, executor = self._retry(
                    source, account, attempt, action=action, driver_choice=None, proxy_country="JP",
                )
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], 409)
                self.assertIsNone(create_call)
                executor.assert_not_called()

    def test_proxy_country_override_only_reuses_matching_active_job(self):
        for status in ("pending", "running"):
            for country, marker, expected in (("IN", None, False), ("JP", None, False),
                                             ("JP", "IN", False), ("JP", "JP", True)):
                with self.subTest(status=status, country=country, marker=marker):
                    source, account, attempt = self._facts()
                    source["config_snapshot"].update(registration_driver="roxy", proxy_country="IN")
                    active = {"id": 22, "status": status, "job_type": "registration_resume",
                              "config_snapshot": {"registration_driver": "roxy", "proxy_country": country}}
                    if marker:
                        active["config_snapshot"]["retry_proxy_country_override"] = marker
                    original = copy.deepcopy(active)
                    result, _, executor = self._retry(
                        source, account, attempt, child=active, proxy_country="JP", driver_choice=None,
                    )
                    self.assertIs(result["ok"], expected, result)
                    if expected:
                        self.assertTrue(result["reused"])
                    else:
                        self.assertEqual(result["status"], 409)
                    self.assertEqual(active, original)
                    executor.assert_not_called()

    def test_retry_without_proxy_override_preserves_historical_snapshot(self):
        source, account, attempt = self._facts()
        source["config_snapshot"].update(registration_driver="roxy", proxy_country="IN")
        result, create_call, _ = self._retry(source, account, attempt, driver_choice=None)
        self.assertTrue(result["ok"], result)
        snapshot = create_call.kwargs["data"]["config_snapshot"]
        self.assertEqual(snapshot["proxy_country"], "IN")
        self.assertNotIn("retry_proxy_country_override", snapshot)

    def test_retry_without_new_country_does_not_inherit_old_override_permission(self):
        source, account, attempt = self._facts()
        source["config_snapshot"].update(registration_driver="roxy", proxy_country="JP",
                                         retry_proxy_country_override="JP")
        original = copy.deepcopy(source)
        result, create_call, _ = self._retry(source, account, attempt, driver_choice=None)
        self.assertTrue(result["ok"], result)
        snapshot = create_call.kwargs["data"]["config_snapshot"]
        self.assertEqual(snapshot["proxy_country"], "JP")
        self.assertNotIn("retry_proxy_country_override", snapshot)
        self.assertEqual(source, original)

    def test_retry_api_validates_and_passes_explicit_proxy_country(self):
        client = create_app(auth_code="test-auth").test_client()
        for country in ("JP", " jp ", "", None, 1, True, [], {}, "ZZ"):
            with self.subTest(country=country), patch("webui.app.svc.retry_job", return_value={"ok": True}) as retry:
                response = client.post("/api/jobs/21/retry", json={"workers": 1, "proxy_country": country},
                                       headers={"X-Auth-Code": "test-auth"})
                if isinstance(country, str) and country.strip().upper() == "JP":
                    self.assertEqual(response.status_code, 200)
                    retry.assert_called_once_with(21, workers=1, proxy_country="JP")
                else:
                    self.assertEqual(response.status_code, 400)
                    retry.assert_not_called()

    def test_bulk_retry_rejects_proxy_country_before_submitting_any_job(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("webui.app.svc.retry_job", return_value={"ok": True}) as retry:
            response = client.post("/api/jobs/retry-bulk", json={"job_ids": [21, 23], "proxy_country": "JP"},
                                   headers={"X-Auth-Code": "test-auth"})
        self.assertEqual(response.status_code, 400)
        retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
