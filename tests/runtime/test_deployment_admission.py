"""纯协议部署在入队前拒绝浏览器操作，保留协议重跑能力。"""
import logging
import os
from contextlib import ExitStack
from unittest.mock import Mock, patch

from flask import Flask

from core.accounts.liveness import service as live
from core.codex import operation_service as codex
from core.operations import task_gateway
from core.runtime import capabilities
from core.registration import service as registration
from core.storage import records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase
from webui import runtime
from webui.app import create_app


class DeploymentAdmissionTests(PostgresTestCase):
    def setUp(self):
        super().setUp()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"TURB_BROWSER_ENABLED": "false"}))
        self.stack.enter_context(patch.object(task_gateway, "notify_dispatch"))
        from core import account_task_store
        self.stack.enter_context(patch.object(account_task_store, "_SCHEMA", self.schema))
        self.stack.enter_context(patch.object(account_task_store, "_READY_KEY", ""))
        account_task_store.init()
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": "deployment@example.test", "access_token": "test-access-token",
            "extra_json": {"account_password": "test-password"},
            "plan_check_status": "success", "codex_status": "success",
        })
        self.context = runtime.WebUIContext(app=Flask(__name__), logger=logging.getLogger(__name__))
        self.settings = {
            "password_enabled": True, "plan_check_enabled": True,
            "twofa_enabled": True, "codex_enabled": True, "refresh_at_enabled": False,
            "password_driver": "roxy", "twofa_driver": "protocol",
            "twofa_browser_fallback_enabled": False, "codex_driver": "protocol",
        }
        self.stack.enter_context(patch.object(runtime, "_runtime_execution_settings", side_effect=lambda _:
            (dict(self.settings), tuple(self.settings), dict(self.settings))))
        self.stack.enter_context(patch("config.account.ACCOUNT_2FA_BROWSER_FALLBACK_ENABLED", False))

    def assert_browser_rejected(self, result):
        self.assertFalse(result["accepted"])
        self.assertEqual("browser_unavailable_on_deployment", result["error_code"])
        self.assertIn("浏览器", result["error"])

    def test_explicit_codex_browser_cannot_bypass_protocol_default(self):
        with patch.object(codex, "_feature_ready", return_value=(True, "")):
            self.assert_browser_rejected(codex.submit("deployment@example.test", driver="roxy", dispatch=False))

    def test_protocol_live_check_remains_available_but_browser_and_refresh_fallback_are_rejected(self):
        with patch("config.account.ACCOUNT_LIVE_CHECK_BROWSER_ENABLED", True), patch(
            "config.proxy.LIVE_CHECK_ROXY_FALLBACK_ENABLED", True,
        ):
            self.assert_browser_rejected(live.enqueue_account_live_check(
                account_id=self.account_id, email="deployment@example.test", driver="browser_roxy",
            ))
            self.assert_browser_rejected(live.enqueue_account_live_check(
                account_id=self.account_id, email="deployment@example.test", force_refresh=True, driver="protocol",
            ))
            result = live.enqueue_account_live_check(
                account_id=self.account_id, email="deployment@example.test", driver="protocol",
            )
        self.assertTrue(result["accepted"], result)

    def test_completion_with_existing_password_keeps_protocol_twofa_available(self):
        result = self.context.enqueue_account_completion(self.account_id)
        self.assertTrue(result["accepted"], result)
        self.assertEqual(["twofa"], result["plan"]["missing_steps"])

    def test_password_and_forced_twofa_change_are_rejected_before_queue(self):
        self.assert_browser_rejected(self.context.enqueue_account_setup(self.account_id, steps={"password"}))
        self.assert_browser_rejected(self.context.enqueue_account_setup(
            self.account_id, steps={"twofa"}, operation="twofa_change",
        ))

    def test_native_runtime_retry_checks_historical_browser_snapshot(self):
        created = operation.create_runtime_task(
            task_type="twofa_setup", account_id=self.account_id, email="deployment@example.test",
            source_system="webui_runtime", source_id="deployment-browser-retry",
            data={"steps": ["twofa"], "config_snapshot": {"twofa_driver": "browser"}},
        )
        operation.finish_run(created["run"]["id"], status="failed")
        task = operation.get_task(created["id"])
        self.assert_browser_rejected(runtime._retry_native_runtime_task(task))
        self.assertEqual(1, len(operation.get_task(created["id"])["runs"]))

    def test_capabilities_keep_protocol_live_check_and_report_deployment(self):
        with patch("config.account.ACCOUNT_LIVE_CHECK_DRIVER", "protocol_current"), patch(
            "config.proxy.LIVE_CHECK_ROXY_FALLBACK_ENABLED", False,
        ), patch.object(capabilities, "proxy_configuration_status", return_value={"ok": True}):
            result = capabilities.feature_availability()
        self.assertFalse(result["deployment"]["browser"]["enabled"])
        self.assertTrue(result["features"]["live_check"]["enabled"])
        self.assertFalse(result["features"]["password_setup"]["enabled"])
        self.assertFalse(result["features"]["twofa_change"]["enabled"])

    def test_roxy_api_returns_classified_unavailable_response(self):
        client = create_app(auth_code="test-auth").test_client()
        with patch("core.browser.roxy.client.RoxyBrowserClient", side_effect=AssertionError("不应访问 Roxy")):
            response = client.get("/api/roxy/workspaces", headers={"X-Auth-Code": "test-auth"})
        self.assertEqual(503, response.status_code)
        self.assertEqual("browser_unavailable_on_deployment", response.get_json()["error_code"])

    def test_native_live_retry_rejects_browser_but_keeps_protocol_attempts(self):
        for driver in ("browser_roxy", "protocol_current"):
            with self.subTest(driver=driver):
                created = operation.create_runtime_task(
                    task_type="live_check", account_id=self.account_id, email="deployment@example.test",
                    data={"driver": driver, "config_snapshot": {"live_check_driver": driver}},
                )
                operation.finish_run(created["run"]["id"], status="failed")
                task = operation.get_task(created["id"])
                result = live._retry_live_check_operation(task)
                if driver == "browser_roxy":
                    self.assert_browser_rejected(result)
                    self.assertEqual(1, len(operation.get_task(created["id"])["runs"]))
                else:
                    self.assertTrue(result["accepted"], result)
                    self.assertEqual(2, len(operation.get_task(created["id"])["runs"]))

    def test_native_token_refresh_retry_rejects_current_browser_fallback(self):
        created = operation.create_runtime_task(
            task_type="token_refresh", account_id=self.account_id, email="deployment@example.test",
        )
        operation.finish_run(created["run"]["id"], status="failed")
        with patch("config.proxy.LIVE_CHECK_ROXY_FALLBACK_ENABLED", True):
            result = live._retry_token_refresh_operation(operation.get_task(created["id"]))
        self.assert_browser_rejected(result)
        self.assertEqual(1, len(operation.get_task(created["id"])["runs"]))

    def test_codex_retry_checks_override_before_creating_attempt(self):
        created = operation.create_runtime_task(
            task_type="codex_retry", account_id=self.account_id, email="deployment@example.test",
        )
        operation.finish_run(created["run"]["id"], status="failed")
        with patch.object(codex, "_feature_ready", return_value=(True, "")), patch.object(codex, "_dispatch"):
            self.assert_browser_rejected(codex.retry_task(created["id"], driver="roxy"))
            result = codex.retry_task(created["id"], driver="protocol")
        self.assertTrue(result["accepted"], result)
        self.assertEqual(2, len(operation.get_task(created["id"])["runs"]))

    def test_explicit_protocol_codex_does_not_inherit_global_browser_unavailability(self):
        with patch.multiple("config.codex", CODEX_OAUTH_DRIVER="roxy", CODEX_AUTH_URL_SOURCE="local", SMS_PROVIDER="grizzly", SMS_API_KEY="test-key"), patch.object(
            capabilities, "proxy_configuration_status", return_value={"ok": True},
        ):
            enabled, reason = capabilities.require_feature("codex_retry", driver="protocol")
        self.assertTrue(enabled, reason)

    def test_bulk_refresh_rejects_before_creating_batch_and_protocol_live_override_remains_usable(self):
        client = create_app(auth_code="test-auth").test_client()
        headers = {"X-Auth-Code": "test-auth"}
        with patch("config.proxy.LIVE_CHECK_ROXY_FALLBACK_ENABLED", True):
            result = client.post("/api/accounts/refresh-token-bulk", json={"account_ids": [self.account_id]}, headers=headers)
        self.assertEqual(503, result.status_code)
        self.assertEqual("browser_unavailable_on_deployment", result.get_json()["error_code"])
        with patch("config.account.ACCOUNT_LIVE_CHECK_DRIVER", "browser_roxy"), patch.object(
            capabilities, "proxy_configuration_status", return_value={"ok": True},
        ):
            result = client.post("/api/accounts/check-live-bulk", json={"account_ids": [self.account_id], "driver": "protocol"}, headers=headers)
        self.assertEqual(202, result.status_code)
        self.assertEqual(1, result.get_json()["started_count"])

    def test_registration_creation_checks_effective_driver_before_creating_jobs(self):
        from core.storage import postgres

        with patch.object(registration, "get_executor", return_value=Mock()), patch.object(
            registration, "get_executor_workers", return_value=1,
        ), patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy"), patch("config.codex.ENABLE_CODEX_AUTO", False):
            for driver in ("roxy", "roxy_oss"):
                with self.subTest(driver=driver), self.assertRaisesRegex(ValueError, "browser_unavailable_on_deployment"):
                    registration.submit_registration(1, email_source="outlook", registration_driver=driver)
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {postgres.qualified(records.JOBS.name)}")
                self.assertEqual(0, cur.fetchone()[0])
            for driver in ("protocol", "protocol_oss", "protocol_oss_2"):
                with self.subTest(driver=driver):
                    jobs = registration.submit_registration(1, email_source="outlook", registration_driver=driver)
                    self.assertEqual(driver, registration.registration_options_for_job(jobs[0])["registration_driver"])

    def test_registration_retry_checks_snapshot_and_override_without_blocking_protocol(self):
        from core import db

        with patch.object(registration, "get_executor", return_value=Mock()), patch.object(
            registration, "get_retry_info", return_value={"retryable": True, "retry_action": "registration"},
        ):
            for index, driver in enumerate(("roxy", "protocol", "protocol_oss", "protocol_oss_2")):
                source = db.create_job(email_source="outlook", data={"config_snapshot": {
                    "registration_driver": driver, "twofa_enabled": False, "codex_enabled": False,
                }})
                db.update_job(source["id"], status="failed", email=f"registration-{index}@example.test")
                rejected = registration.retry_job(source["id"], registration_driver="roxy")
                self.assertEqual("browser_unavailable_on_deployment", rejected.get("error_code"), rejected)
                result = registration.retry_job(source["id"])
                if driver == "roxy":
                    self.assertEqual("browser_unavailable_on_deployment", result.get("error_code"), result)
                else:
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(driver, registration.registration_options_for_job(result["job"])["registration_driver"])

    def test_registration_browser_postprocessing_is_rejected_before_task_creation(self):
        for settings in (
            {"twofa_enabled": True, "twofa_driver": "browser", "codex_enabled": False},
            {"twofa_enabled": False, "codex_enabled": True, "codex_driver": "roxy"},
        ):
            with self.subTest(settings=settings), patch.object(registration, "registration_config_snapshot", return_value={
                "registration_driver": "protocol", **settings,
            }), patch.object(registration, "get_executor", return_value=Mock()):
                with self.assertRaisesRegex(ValueError, "browser_unavailable_on_deployment"):
                    registration.submit_registration(1, email_source="outlook")

    def test_cli_rejects_browser_before_proxy_or_email_acquisition(self):
        import main

        with patch("config.roxybrowser.REGISTRATION_DRIVER", "roxy"), patch(
            "core.proxy.provider.acquire_registration_proxy", side_effect=AssertionError("不应领取代理"),
        ), patch.object(main, "prepare_registration_inputs", side_effect=AssertionError("不应领取邮箱")):
            result = main.run_one_batch_item(0, 1)
        self.assertFalse(result["success"])
        self.assertEqual("browser_unavailable_on_deployment", result.get("error_code"), result)

    def test_registration_http_rejects_browser_with_classified_error(self):
        client = create_app(auth_code="test-auth").test_client()
        result = client.post("/api/jobs", json={"registration_driver": "roxy", "count": 2}, headers={"X-Auth-Code": "test-auth"})
        self.assertEqual(503, result.status_code)
        self.assertEqual("browser_unavailable_on_deployment", result.get_json()["error_code"])

    def test_deployment_failure_has_specific_task_error_classification(self):
        from core.operations.errors import classify_task_error

        result = classify_task_error(
            "browser_unavailable_on_deployment：当前部署未提供浏览器，仅支持纯协议功能",
            task_type="codex_retry", stage="preflight",
        )
        self.assertEqual("browser_unavailable_on_deployment", result["code"])

    def test_existing_browser_setup_queue_stops_before_remote_worker(self):
        created = operation.create_runtime_task(
            task_type="twofa_setup", account_id=self.account_id, email="deployment@example.test",
            source_system="webui_runtime", source_id="browser-setup-before-deployment-change",
            data={"steps": ["twofa"], "config_snapshot": {"twofa_driver": "browser"}},
        )
        runtime._register_runtime_handlers()
        with patch.object(runtime.codex_retry_service, "run_twofa_worker", side_effect=AssertionError("不应执行浏览器操作")):
            result = task_gateway._execute_operation_handler("twofa_setup", created["run"]["id"])
        self.assertEqual("failed", result["status"])
        stored = operation.get_run(created["run"]["id"])
        self.assertEqual("browser_unavailable_on_deployment", stored["result_summary"].get("error_code"))

    def test_existing_browser_live_queue_stops_before_remote_worker(self):
        created = operation.create_runtime_task(
            task_type="live_check", account_id=self.account_id, email="deployment@example.test",
            data={"driver": "browser_roxy", "config_snapshot": {"live_check_driver": "browser_roxy"}},
        )
        live.register_operation_handlers()
        with patch.object(live, "_run_live_check", side_effect=AssertionError("不应执行浏览器操作")):
            result = task_gateway._execute_operation_handler("live_check", created["run"]["id"])
        self.assertEqual("failed", result["status"])
        stored = operation.get_run(created["run"]["id"])
        self.assertEqual("browser_unavailable_on_deployment", stored["result_summary"].get("error_code"))
