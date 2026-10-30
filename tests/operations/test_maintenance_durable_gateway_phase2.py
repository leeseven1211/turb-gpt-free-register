from __future__ import annotations

from copy import deepcopy
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core.operations import executor as account_operation_executor
from core import db
from core.storage import postgres as postgres_store, records as record_store
from core.accounts.deactivation import mail_scan as deactivation_mail_service
from core.extract_link import service as extract_link_service
from core.accounts.liveness import service as live_check_service
from core.accounts.plans import service as plan_check_service
from core.operations import task_gateway
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class _Route:
    proxy_url = None

    def public_dict(self):
        return {
            "network_route": "direct",
            "proxy_mode": "direct",
            "proxy_provider": "test",
            "proxy_region": "US",
            "proxy_used": None,
        }

    def release(self, **_kwargs):
        return None


class _ConfigSnapshot:
    def __init__(self, values: dict, revision: int):
        self.values = dict(values)
        self.revision = int(revision)

    def as_dict(self):
        return dict(self.values)


class MaintenanceDurableGatewayTests(PostgresTestCase):
    def setUp(self):
        task_gateway.init()
        operation.reset_ready()
        operation.init()
        self.assertTrue(live_check_service.register_maintenance_operation_handlers())

    def _account(self, email: str, **extra) -> int:
        values = {
            "email": email,
            "access_token": "synthetic-access-token",
            "email_source": "cloudflare",
            "account_status": "active",
            "created_at": "2026-09-14T10:00:00",
            "updated_at": "2026-09-14T10:00:00",
        }
        values.update(extra)
        return record_store.insert_row(record_store.ACCOUNTS, values)

    def _run_native(self, task_type: str, run_id: int) -> dict:
        result = task_gateway._execute_operation_handler(task_type, int(run_id))
        self.assertNotEqual("not_claimed", result.get("status"), result)
        return result

    def test_native_submissions_capture_canonical_revision_without_secrets(self):
        live_id = self._account("snapshot-live@example.test")
        plan_id = self._account("snapshot-plan@example.test")
        mail_id = self._account("snapshot-mail@example.test", email_source="cloudflare")
        extract_id = self._account("snapshot-extract@example.test")

        with (
            patch.object(live_check_service, "_captured_proxy_source", return_value="direct"),
            patch.object(live_check_service, "resolve_driver", return_value="protocol_current"),
        ):
            live = live_check_service.enqueue_account_live_check(
                account_id=live_id,
                email="snapshot-live@example.test",
            )
        with patch.object(plan_check_service, "_captured_proxy_source", return_value="direct"):
            plan = plan_check_service.enqueue_account_plan_check(
                account_id=plan_id,
                email="snapshot-plan@example.test",
                access_token="synthetic-access-token",
                trigger="manual",
            )
        with patch.object(deactivation_mail_service, "_LOOKBACK_DAYS", 123):
            mail = deactivation_mail_service.enqueue(mail_id, trigger="manual")
        with patch.object(extract_link_service, "_cdk", return_value="submission-secret"):
            extract = extract_link_service.enqueue_account_extract(
                account_id=extract_id,
                email="snapshot-extract@example.test",
                access_token="enqueue-token-must-not-be-stored",
                trigger="manual",
                link_type="pix",
                cdk="submission-secret",
            )

        self.assertTrue(all(item.get("accepted") for item in (live, plan, mail, extract)))
        for item in (live, plan, mail, extract):
            run = operation.get_run(item["run_id"])
            snapshot = run["data"].get("config_snapshot")
            self.assertIsInstance(snapshot, dict)
            self.assertIn("config_snapshot_revision", snapshot)
            self.assertNotIn("access_token", run["data"])
            self.assertNotIn("cdk", run["data"])
            self.assertNotIn("EXTRACT_LINK_CDK", snapshot)
            self.assertNotIn("EMAIL_BUTLER_API_KEY", snapshot)
            self.assertNotIn("ICLOUD_HME_API_TOKEN", snapshot)
            self.assertNotIn("PLAN_CHECK_PROXY", snapshot)

    def test_plan_handler_consumes_captured_config_after_global_mutation(self):
        account_id = self._account("snapshot-plan-execute@example.test")
        snapshot = _ConfigSnapshot({
            "PLAN_CHECK_TIMEOUT": 7.0,
            "PLAN_CHECK_MAX_ATTEMPTS": 1,
            "PLAN_CHECK_RETRY_DELAY": 0.0,
            "PLAN_CHECK_REGISTRATION_RECHECK_DELAY": 0.0,
            "PLAN_CHECK_MIN_INTERVAL": 0.0,
            "PLAN_CHECK_JITTER": 0.0,
            "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
            "ACCOUNT_PLAN_CHECK_DRIVER": "protocol",
        }, revision=701)
        with (
            patch.object(plan_check_service, "get_config_snapshot", return_value=snapshot),
            patch.object(plan_check_service, "_captured_proxy_source", return_value="direct"),
        ):
            submitted = plan_check_service.enqueue_account_plan_check(
                account_id=account_id,
                email="snapshot-plan-execute@example.test",
                access_token="enqueue-token-must-not-be-used",
                trigger="manual",
            )

        seen: dict[str, object] = {}

        def check_plan(_token, **kwargs):
            seen.update(kwargs)
            return {
                "ok": True,
                "http_status": 200,
                "current_plan_type": "free",
                "plus_trial_eligible": False,
            }

        with (
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_TIMEOUT", 99.0),
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_MAX_ATTEMPTS", 4),
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_RETRY_DELAY", 22.0),
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_MIN_INTERVAL", 22.0),
            patch.object(plan_check_service.proxy_cfg, "PLAN_CHECK_JITTER", 22.0),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()) as acquire,
            patch.object(plan_check_service, "check_account_plan", side_effect=check_plan),
        ):
            result = self._run_native("plan_check", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual(7.0, seen["timeout"])
        self.assertEqual(1, seen["max_attempts"])
        self.assertEqual(0.0, seen["retry_delay"])
        self.assertEqual("pool", acquire.call_args.kwargs["source"])
        self.assertEqual(701, operation.get_run(submitted["run_id"])["data"]["config_snapshot"]["config_snapshot_revision"])

    def test_extract_handler_consumes_captured_transport_config_and_reads_cdk_on_demand(self):
        account_id = self._account("snapshot-extract-execute@example.test")
        snapshot = _ConfigSnapshot({
            "EXTRACT_LINK_API_BASE": "https://snapshot.extract.invalid",
            "EXTRACT_LINK_TYPE": "pix",
            "EXTRACT_LINK_REQUEST_TIMEOUT": 11,
            "EXTRACT_LINK_EVENT_TIMEOUT": 33,
        }, revision=702)
        with (
            patch.object(extract_link_service, "get_config_snapshot", return_value=snapshot),
            patch.object(extract_link_service, "_cdk", return_value="runtime-secret"),
        ):
            submitted = extract_link_service.enqueue_account_extract(
                account_id=account_id,
                email="snapshot-extract-execute@example.test",
                access_token="enqueue-token-must-not-be-stored",
                trigger="manual",
                link_type="pix",
                cdk="submission-secret",
            )

        create_seen: dict[str, object] = {}
        events_seen: dict[str, object] = {}

        def create_job(**kwargs):
            create_seen.update(kwargs)
            kwargs["on_request_started"]()
            return {"job_id": "snapshot-job", "cdk_remaining": 1}

        def iter_events(*, job_id, cdk, **kwargs):
            events_seen.update({"job_id": job_id, "cdk": cdk, **kwargs})
            return iter([("result", {"result": {"payment_method": "pix"}})])

        with (
            patch.object(extract_link_service, "_cdk", return_value="runtime-secret"),
            patch.object(extract_link_service, "_append_log", create=True),
            patch.object(live_check_service, "run_account_live_check_inline", return_value={
                "accepted": True,
                "result": {"ok": True, "status": "live"},
            }) as preflight,
            patch.object(extract_link_service, "_create_extract_job", side_effect=create_job),
            patch.object(extract_link_service, "_iter_sse_events", side_effect=iter_events),
        ):
            result = self._run_native("extract_link", submitted["run_id"])

        self.assertEqual("success", result["status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual(702, run["data"]["config_snapshot"]["config_snapshot_revision"])
        self.assertNotIn("cdk", run["data"])
        self.assertEqual("https://snapshot.extract.invalid", create_seen["api_base"])
        self.assertEqual(11, create_seen["request_timeout"])
        self.assertEqual("https://snapshot.extract.invalid", events_seen["api_base"])
        self.assertEqual(33, events_seen["event_timeout"])
        self.assertEqual("runtime-secret", events_seen["cdk"])
        self.assertEqual(702, preflight.call_args.kwargs["config_snapshot"]["config_snapshot_revision"])

    def test_deactivation_handler_uses_submission_lookback_after_global_mutation(self):
        account_id = self._account("snapshot-mail-execute@example.test", email_source="cloudflare")
        snapshot = _ConfigSnapshot({}, revision=703)
        with (
            patch.object(deactivation_mail_service, "get_config_snapshot", return_value=snapshot),
            patch.object(deactivation_mail_service, "_LOOKBACK_DAYS", 123),
        ):
            submitted = deactivation_mail_service.enqueue(account_id, trigger="manual")

        with (
            patch.object(deactivation_mail_service, "_LOOKBACK_DAYS", 1),
            patch.object(deactivation_mail_service, "scan_cloudflare_deactivation", return_value={
                "ok": True,
                "detected": False,
                "checked_at": "2026-09-14T12:00:00Z",
                "confidence": "none",
            }) as scan,
        ):
            result = self._run_native("deactivation_mail", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual(123, scan.call_args.kwargs["lookback_days"])
        self.assertEqual(703, operation.get_run(submitted["run_id"])["data"]["config_snapshot"]["config_snapshot_revision"])

    def test_live_enqueue_claims_native_run_and_writes_account_without_legacy_reporter(self):
        account_id = self._account("live-maintenance@example.test")
        route = _Route()
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "resolve_driver", return_value="api"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(live_check_service, "run_probe", return_value={
                "ok": True,
                "http_status": 200,
                "current_plan_type": "free",
                "live_check_driver": "api",
            }),
            patch.object(live_check_service.account_task_store, "create_task", side_effect=AssertionError("legacy task")),
            patch.object(live_check_service, "TaskReporter", side_effect=AssertionError("legacy reporter")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="live-maintenance@example.test",
                trigger="manual",
            )

            self.assertTrue(submitted["accepted"])
            self.assertFalse(submitted["busy"])
            run = operation.get_run(submitted["run_id"])
            self.assertEqual("queued", run["status"])
            self.assertEqual("native_operations", run["source_system"])
            self.assertNotIn("access_token", run["data"])

            result = self._run_native("live_check", submitted["run_id"])

        self.assertEqual("success", result["status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("success", run["status"])
        account = db.get_account(account_id)
        self.assertEqual("live", account["live_check_status"])
        self.assertTrue(account["live_check_ok"])

    def test_maintenance_registration_entrypoint_covers_all_native_types(self):
        self.assertTrue(
            {
                "live_check",
                "token_refresh",
                "plan_check",
                "deactivation_mail",
                "extract_link",
            }.issubset(set(task_gateway.registered_operation_types()))
        )

    def test_native_services_keep_compatibility_seams_without_legacy_consumers(self):
        common = account_operation_executor.executor
        self.assertIs(live_check_service._EXECUTOR, common)
        self.assertIs(plan_check_service._ACCOUNT_EXECUTOR, common)
        self.assertIsNot(plan_check_service._EXECUTOR, common)
        self.assertTrue(callable(plan_check_service._EXECUTOR.submit))
        for service in (deactivation_mail_service, extract_link_service):
            self.assertFalse(hasattr(service, "_EXECUTOR"), service.__name__)
            self.assertFalse(hasattr(service, "_ACCOUNT_EXECUTOR"), service.__name__)
        self.assertFalse(hasattr(deactivation_mail_service, "_HME_QUEUE"))
        self.assertFalse(hasattr(deactivation_mail_service, "_ensure_hme_coordinator"))

    def test_sentinel_failure_closes_protocol_receipt_then_browser_uses_new_intent(self):
        account_id = self._account("sentinel-browser@example.test")

        def sentinel_failure(_email, **kwargs):
            kwargs["on_remote_request_started"]()
            return {
                "ok": False, "status": "failed", "error": "password_sentinel_failed",
                "mutation_submitted": False, "action_dispatched": False,
                "remote_request_started": True, "roxy_fallback_allowed": True,
                "auth_diagnostics": {"operation": "password_sentinel", "curl_error_code": 35},
            }

        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=sentinel_failure),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", return_value=True),
            patch("core.accounts.liveness.roxy.flow.refresh_access_token", return_value={
                "ok": True, "status": "live", "access_token": "synthetic-refreshed-token",
            }) as browser,
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id, email="sentinel-browser@example.test",
                trigger="token_refresh_manual", force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertTrue(result["ok"])
        browser.assert_called_once()
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("success", run["status"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["outcome"])
        events = operation.list_task_events(submitted["task_id"], run_id=submitted["run_id"], limit=100)["items"]
        starts = [event for event in events if event.get("event_type") == "remote.request_started"]
        self.assertEqual(2, len(starts))
        self.assertTrue(any(
            event.get("event_type") == "remote.receipt_received"
            and event.get("detail", {}).get("outcome") == "not_submitted" for event in events
        ))

    def test_refresh_unknown_is_terminal_reconcile_state_and_does_not_fallback_or_retry(self):
        account_id = self._account("refresh-unknown@example.test")
        route = _Route()
        self.assertTrue(db.claim_account_live_check(account_id, trigger="token_refresh_manual"))
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "protocol_v2_unknown_error",
            }) as refresh,
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("unknown refresh must not fallback")),
        ):
            result = live_check_service._run_live_check(
                account_id=account_id,
                email="refresh-unknown@example.test",
                proxy=None,
                trigger="token_refresh_manual",
                force_refresh=True,
                refresh_driver="v2",
                release_queue_slot=False,
            )

        refresh.assert_called_once()
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        self.assertTrue(result["manual_reconcile"])
        self.assertEqual("failed", db.get_account(account_id)["live_check_status"])

    def test_sentinel_failure_without_browser_keeps_specific_failed_result(self):
        account_id = self._account("sentinel-no-browser@example.test")

        def fail_before_password(_email, **kwargs):
            kwargs["on_remote_request_started"]()
            return {
                "ok": False, "status": "failed", "error": "password_sentinel_failed",
                "mutation_submitted": False, "action_dispatched": False,
                "remote_request_started": True, "roxy_fallback_allowed": True,
                "auth_diagnostics": {
                    "operation": "password_sentinel", "curl_error_code": 56,
                    "exception_type": "ConnectionError", "private_value": "synthetic-secret",
                },
            }

        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=fail_before_password),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=False),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id, email="sentinel-no-browser@example.test",
                trigger="token_refresh_manual", force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertFalse(result.get("reconcile_required"))
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertEqual("not_submitted", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual("password_sentinel_failed", run["result_summary"]["cause_code"])
        self.assertEqual("password_sentinel", run["result_summary"]["auth_diagnostics"]["operation"])
        self.assertEqual(56, run["result_summary"]["auth_diagnostics"]["curl_error_code"])
        self.assertNotIn("synthetic-secret", str(run["result_summary"]))

    def test_password_connection_loss_keeps_concrete_cause_and_prevents_browser_retry(self):
        account_id = self._account("password-disconnected@example.test")

        def lost_password_receipt(_email, **kwargs):
            kwargs["on_remote_request_started"]()
            return {
                "ok": False, "status": "failed", "error": "password_result_unknown",
                "mutation_submitted": True, "action_dispatched": True,
                "remote_response_received": False, "reconcile_required": True,
                "auth_diagnostics": {"operation": "password_verify", "curl_error_code": 56},
            }

        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=lost_password_receipt),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("已派发密码时禁止自动重提")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id, email="password-disconnected@example.test",
                trigger="token_refresh_manual", force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("password_result_unknown", run["result_summary"]["cause_code"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["outcome"])

    def test_refresh_cause_is_preserved_without_changing_unknown_fence(self):
        account_id = self._account("refresh-cause@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "email_otp_failed",
                "error_category": "email",
                "auth_method": "email_otp",
                "remote_request_started": True,
                "roxy_fallback_allowed": False,
                "auth_diagnostics": {
                    "operation": "email_otp",
                    "failure_kind": "no_mail",
                    "exception_type": "ForwardIMAPNoMailTimeout",
                    "private_value": "private-token",
                },
            }),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("unknown refresh must not fallback")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="refresh-cause@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        run = operation.get_run(submitted["run_id"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("request_unknown", run["result_summary"]["outcome"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        self.assertEqual("email_otp_failed", run["result_summary"]["cause_code"])
        self.assertEqual("no_mail", run["result_summary"]["auth_diagnostics"]["failure_kind"])
        self.assertNotIn("private-token", str(run["result_summary"]))

    def test_refresh_boundary_and_rejection_require_exact_evidence(self):
        self.assertEqual("email_otp_failed", live_check_service._safe_refresh_cause_code({
            "error_code": "request_unknown",
            "error": "email_otp_failed",
        }))
        self.assertFalse(live_check_service._refresh_result_before_remote_boundary({
            "remote_request_started": True,
            "error": "auth_route_rejected",
        }))
        self.assertTrue(live_check_service._refresh_result_before_remote_boundary({
            "remote_request_started": False,
            "error": "auth_route_rejected",
        }))
        self.assertFalse(live_check_service._refresh_result_is_rejected({
            "error": "password_rejected_email_fallback_failed",
        }))
        self.assertTrue(live_check_service._refresh_result_is_rejected({
            "error": "password_rejected",
        }))
        self.assertTrue(live_check_service._refresh_result_is_rejected({
            "status": "deactivated",
            "error": "password_rejected_email_fallback_failed",
            "password_auth_status": "rejected",
        }))

    def test_password_rejected_email_fallback_failure_keeps_unknown_receipt(self):
        account_id = self._account("refresh-password-fallback@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "password_rejected_email_fallback_failed",
                "error_category": "email",
                "password_auth_status": "rejected",
                "auth_method": "protocol_v2",
                "remote_request_started": True,
                "roxy_fallback_allowed": False,
                "auth": {
                    "status": "password_rejected_email_fallback_failed",
                    "code": "password_rejected_email_fallback_failed",
                    "next_action": "stop",
                },
                "auth_diagnostics": {
                    "operation": "password_email_fallback",
                    "failure_kind": "fallback_failed",
                    "cause_code": "email_otp_failed",
                    "cause_failure_kind": "no_mail",
                },
            }),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("unknown refresh must not fallback")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="refresh-password-fallback@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        run = operation.get_run(submitted["run_id"])
        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual("password_rejected_email_fallback_failed", run["result_summary"]["cause_code"])
        self.assertEqual("email_otp_failed", run["result_summary"]["auth_diagnostics"]["cause_code"])

    def test_native_refresh_unknown_finishes_attention_required_after_business_writeback(self):
        account_id = self._account("native-refresh-unknown@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "protocol_v2_unknown_error",
            }),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("unknown refresh must not fallback")),
            patch.object(live_check_service, "TaskReporter", side_effect=AssertionError("native reporter")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-unknown@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        self.assertEqual("attention_required", result["database_status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("request_unknown", run["result_summary"]["outcome"])
        self.assertTrue(run["result_summary"]["reconcile_required"])
        self.assertEqual("failed", db.get_account(account_id)["live_check_status"])

    def test_native_refresh_route_rejection_does_not_open_remote_boundary(self):
        account_id = self._account("native-refresh-route-rejected@example.test")

        def reject_before_remote_write(_email, **kwargs):
            self.assertTrue(callable(kwargs.get("on_remote_request_started")))
            return {
                "ok": False,
                "status": "failed",
                "error": "auth_route_rejected",
                "error_category": "network",
                "http_status": 403,
                "auth_method": "protocol_v2",
                "roxy_fallback_allowed": True,
            }

        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=reject_before_remote_write),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=False),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-route-rejected@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertEqual("failed", db.get_account(account_id)["live_check_status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("failed", run["status"])
        self.assertNotIn("remote_intent", run["data"])
        events = operation.list_task_events(
            submitted["task_id"], run_id=submitted["run_id"], limit=100,
        )["items"]
        self.assertFalse(any(event.get("event_type") == "remote.request_started" for event in events))
        self.assertFalse(any(event.get("event_type") == "remote.receipt_unknown" for event in events))

    def test_token_refresh_retry_reclaims_account_projection_before_dispatch(self):
        account_id = self._account("token-refresh-retry-claim@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "protocol_v2_unknown_error",
            }),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=False),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="token-refresh-retry-claim@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", db.get_account(account_id)["live_check_status"])
        task = {
            "id": submitted["task_id"],
            "account_id": account_id,
            "email_snapshot": "token-refresh-retry-claim@example.test",
            "status": "attention_required",
            "source_system": "native_operations",
        }
        retry = task_gateway.operation_action(
            "token_refresh", "retry", source_system="native_operations",
        )
        self.assertIsNotNone(retry)
        with patch.object(task_gateway, "notify_dispatch"):
            result = retry(task)

        self.assertTrue(result["accepted"])
        self.assertEqual("queued", db.get_account(account_id)["live_check_status"])

    def test_token_refresh_retry_captures_current_driver_and_debug_without_changing_old_runs(self):
        account_id = self._account("token-refresh-retry-config@example.test")
        old_snapshot = task_gateway.normalize_config_snapshot(_ConfigSnapshot({
            "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
            "OPENAI_PROTOCOL_VERSION": "v2",
            "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED": False,
            "ACCOUNT_REFRESH_AT_PROXY_MODE": "direct",
        }, revision=801), allowlist=live_check_service.LIVE_CONFIG_ALLOWLIST)
        task = operation.create_runtime_task(
            task_type="token_refresh", account_id=account_id,
            email="token-refresh-retry-config@example.test", source_system="native_operations",
            source_id="token-refresh-retry-config", data={
                "force_refresh": True, "driver": None, "refresh_driver": "v2",
                "proxy_source": "direct", "config_snapshot": old_snapshot,
            },
        )
        operation.finish_run(int(task["run"]["id"]), status="failed", error="fixture failure")
        previous_data = {int(task["run"]["id"]): deepcopy(operation.get_run(task["run"]["id"])["data"])}
        retry_task = {
            "id": task["id"], "task_type": "token_refresh", "account_id": account_id,
            "email_snapshot": "token-refresh-retry-config@example.test",
            "status": "failed", "source_system": "native_operations",
        }
        retry = task_gateway.operation_action("token_refresh", "retry", source_system="native_operations")
        self.assertIsNotNone(retry)

        for revision, driver, version, debug in (
            (802, "browser_roxy", "v2", True),
            (803, "protocol", "v1", False),
            (804, "protocol", "v2", False),
        ):
            with (
                patch.object(live_check_service, "get_config_snapshot", return_value=_ConfigSnapshot({
                    "ACCOUNT_AT_REFRESH_DRIVER": driver,
                    "OPENAI_PROTOCOL_VERSION": version,
                    "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED": debug,
                    "ACCOUNT_REFRESH_AT_PROXY_MODE": "direct",
                }, revision=revision)),
                patch.object(task_gateway, "notify_dispatch"),
            ):
                result = retry(retry_task)

            self.assertTrue(result["accepted"])
            run = operation.get_run(result["run_id"])
            self.assertEqual(int(task["id"]), run["task_id"])
            snapshot = run["data"]["config_snapshot"]
            self.assertEqual(driver if driver == "browser_roxy" else version, run["data"]["refresh_driver"])
            self.assertEqual(driver, snapshot["refresh_driver"])
            self.assertIs(debug, snapshot["refresh_roxy_debug_enabled"])
            self.assertEqual(version, snapshot["refresh_protocol_version"])
            self.assertEqual(revision, snapshot["config_snapshot_revision"])
            for old_run_id, data in previous_data.items():
                self.assertEqual(data, operation.get_run(old_run_id)["data"])
            operation.finish_run(int(run["id"]), status="failed", error="fixture failure")
            previous_data[int(run["id"])] = deepcopy(operation.get_run(run["id"])["data"])

    def test_plain_live_check_retry_keeps_original_driver_snapshot(self):
        account_id = self._account("live-check-retry-config@example.test")
        old_snapshot = task_gateway.normalize_config_snapshot(_ConfigSnapshot({
            "ACCOUNT_LIVE_CHECK_DRIVER": "protocol_current",
            "ACCOUNT_AT_REFRESH_DRIVER": "protocol",
            "OPENAI_PROTOCOL_VERSION": "v2",
            "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED": False,
        }, revision=811), allowlist=live_check_service.LIVE_CONFIG_ALLOWLIST)
        task = operation.create_runtime_task(
            task_type="live_check", account_id=account_id,
            email="live-check-retry-config@example.test", source_system="native_operations",
            source_id="live-check-retry-config", data={
                "force_refresh": False, "driver": "protocol_current", "refresh_driver": None,
                "proxy_source": "direct", "config_snapshot": old_snapshot,
            },
        )
        old_run_id = int(task["run"]["id"])
        operation.finish_run(old_run_id, status="failed", error="fixture failure")
        old_data = deepcopy(operation.get_run(old_run_id)["data"])
        retry_task = {
            "id": task["id"], "task_type": "live_check", "account_id": account_id,
            "email_snapshot": "live-check-retry-config@example.test",
            "status": "failed", "source_system": "native_operations",
        }
        retry = task_gateway.operation_action("live_check", "retry", source_system="native_operations")
        self.assertIsNotNone(retry)
        with (
            patch.object(live_check_service, "get_config_snapshot", return_value=_ConfigSnapshot({
                "ACCOUNT_LIVE_CHECK_DRIVER": "browser_roxy",
                "ACCOUNT_AT_REFRESH_DRIVER": "browser_roxy",
                "ACCOUNT_AT_REFRESH_ROXY_DEBUG_ENABLED": True,
            }, revision=812)),
            patch.object(task_gateway, "notify_dispatch"),
        ):
            result = retry(retry_task)

        self.assertTrue(result["accepted"])
        run = operation.get_run(result["run_id"])
        self.assertEqual(int(task["id"]), run["task_id"])
        self.assertEqual("protocol_current", run["data"]["driver"])
        self.assertIsNone(run["data"]["refresh_driver"])
        self.assertEqual(old_snapshot, run["data"]["config_snapshot"])
        self.assertEqual(old_data, operation.get_run(old_run_id)["data"])

    def test_force_refresh_uses_token_refresh_native_task_type_for_any_trigger(self):
        account_id = self._account("refresh-at-trigger@example.test")
        with (
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch.object(live_check_service, "_captured_proxy_source", return_value="direct"),
            patch.object(live_check_service, "_append_log"),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="refresh-at-trigger@example.test",
                trigger="manual_refresh_at",
                force_refresh=True,
            )

        self.assertTrue(submitted["accepted"])
        run = operation.get_run(submitted["run_id"])
        self.assertIsNotNone(run)
        self.assertEqual("token_refresh", run["task_type"])

    def test_native_refresh_confirms_only_after_response_writeback_and_readback(self):
        account_id = self._account("native-refresh-confirmed@example.test")
        refresh_result = {
            "ok": True,
            "status": "live",
            "access_token": "fresh-token",
            "session": {"account": {"planType": "free"}},
            "auth_method": "protocol_v2",
            "password_auth_status": "verified",
            "live_check_driver": "protocol_v2",
            "validation_method": "authenticated_session",
            "roxy_fallback_allowed": False,
        }
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", return_value=refresh_result) as refresh,
            patch.object(live_check_service, "TaskReporter", side_effect=AssertionError("native reporter")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-confirmed@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        refresh.assert_called_once()
        self.assertEqual("success", result["status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("success", run["status"])
        self.assertEqual("token_refresh", run["data"]["remote_intent"]["action"])
        self.assertEqual("confirmed", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["outcome"])
        receipt_events = [
            event for event in operation.list_task_events(
                submitted["task_id"], run_id=submitted["run_id"], limit=100,
            )["items"]
            if event.get("event_type") == "remote.receipt_received"
        ]
        self.assertEqual(2, len(receipt_events))
        account = db.get_account(account_id)
        self.assertEqual("fresh-token", account["access_token"])
        self.assertEqual("live", account["live_check_status"])

    def test_native_refresh_exception_after_remote_boundary_is_request_unknown(self):
        account_id = self._account("native-refresh-exception@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=_Route()),
            patch(
                "core.accounts.liveness.protocol.v2.refresh_access_token",
                side_effect=RuntimeError("transport disconnected"),
            ),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.accounts.liveness.roxy.flow.available", side_effect=AssertionError("must not retry unknown refresh")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-exception@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("refresh_driver_exception", run["result_summary"]["cause_code"])
        self.assertEqual("RuntimeError", run["result_summary"]["auth_diagnostics"]["exception_type"])
        self.assertEqual("unknown", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual("failed", db.get_account(account_id)["live_check_status"])

    def test_native_queued_run_survives_startup_recovery_until_dispatch(self):
        account_id = self._account("restart-maintenance@example.test")
        with patch.object(plan_check_service, "_query_account_plan", side_effect=AssertionError("not dispatched")):
            submitted = plan_check_service.enqueue_account_plan_check(
                account_id=account_id,
                email="restart-maintenance@example.test",
                access_token="synthetic-access-token",
                trigger="manual",
            )
            self.assertTrue(submitted["accepted"])
            self.assertEqual("queued", operation.get_run(submitted["run_id"])["status"])
            self.assertEqual(0, operation.recover_interrupted_runtime_runs())
            self.assertEqual("queued", operation.get_run(submitted["run_id"])["status"])
            operation.request_run_cancel(int(submitted["run_id"]), reason="test cleanup")

    def test_live_concurrent_enqueue_has_one_native_run_and_idempotent_retry_reuses_it(self):
        account_id = self._account("live-dedupe@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "resolve_driver", return_value="api"),
        ):
            barrier = threading.Barrier(2)

            def submit_once():
                barrier.wait(timeout=3)
                return live_check_service.enqueue_account_live_check(
                    account_id=account_id,
                    email="live-dedupe@example.test",
                    trigger="manual",
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(submit_once) for _ in range(2)]
                results = [future.result(timeout=5) for future in futures]

            self.assertEqual(1, sum(bool(item.get("accepted")) for item in results))
            self.assertEqual(1, sum(bool(item.get("busy")) for item in results))
            active = operation.active_run_for_account(account_id, "openai_interactive")
            self.assertIsNotNone(active)

        keyed_account_id = self._account("live-keyed@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "resolve_driver", return_value="api"),
        ):
            keyed = live_check_service.enqueue_account_live_check(
                account_id=keyed_account_id,
                email="live-keyed@example.test",
                trigger="manual",
                idempotency_key="retry-request-1",
            )
            retry = live_check_service.enqueue_account_live_check(
                account_id=keyed_account_id,
                email="live-keyed@example.test",
                trigger="manual",
                idempotency_key="retry-request-1",
            )
        self.assertTrue(keyed["accepted"])
        self.assertFalse(keyed["busy"])
        self.assertTrue(retry["accepted"])
        self.assertFalse(retry["busy"])
        self.assertTrue(retry["reused"])
        self.assertEqual(keyed["task_id"], retry["task_id"])
        self.assertEqual(keyed["run_id"], retry["run_id"])

    def test_plan_native_handler_reads_latest_token_and_persists_terminal_business_state(self):
        account_id = self._account("plan-maintenance@example.test")
        route = _Route()
        with (
            patch.object(plan_check_service, "get_config_snapshot", return_value=_ConfigSnapshot({
                "PLAN_CHECK_COUNTRIES": [], "ACCOUNT_PLAN_CHECK_PROXY_MODE": "direct",
            }, revision=702)),
            patch.object(plan_check_service, "_query_account_plan", return_value={
                "ok": True,
                "http_status": 200,
                "current_plan_type": "free",
                "plus_trial_eligible": False,
            }),
            patch("core.proxy.account_routes.acquire_account_proxy", return_value=route),
            patch.object(plan_check_service.account_task_store, "create_task", side_effect=AssertionError("legacy task")),
            patch.object(plan_check_service, "TaskReporter", side_effect=AssertionError("legacy reporter")),
        ):
            submitted = plan_check_service.enqueue_account_plan_check(
                account_id=account_id,
                email="plan-maintenance@example.test",
                access_token="enqueue-snapshot-must-not-be-used",
                trigger="manual",
            )
            self.assertTrue(submitted["accepted"])
            self.assertFalse(submitted["busy"])
            result = self._run_native("plan_check", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(submitted["run_id"])["status"])
        account = db.get_account(account_id)
        self.assertEqual("success", account["plan_check_status"])
        self.assertTrue(account["plan_check_ok"])

    def test_hme_bulk_native_run_scans_two_aliases_once_and_fans_out_writeback(self):
        first_id = self._account("first@icloud.example", email_source="icloud_hide")
        second_id = self._account("second@icloud.example", email_source="icloud_hide")
        results = {
            "first@icloud.example": {
                "ok": True,
                "detected": False,
                "checked_at": "2026-09-14T12:00:00Z",
                "confidence": "none",
            },
            "second@icloud.example": {
                "ok": True,
                "detected": True,
                "checked_at": "2026-09-14T12:00:01Z",
                "received_at": "2026-09-14T11:59:00Z",
                "subject": "Account deactivated",
                "sender": "noreply@openai.com",
                "confidence": "high",
            },
        }
        with (
            patch.object(
                deactivation_mail_service,
                "scan_hme_deactivation",
                side_effect=AssertionError("HME aliases must use the bulk scanner"),
            ) as per_alias,
            patch.object(
                deactivation_mail_service,
                "scan_hme_deactivation_bulk",
                return_value=results,
            ) as bulk_scan,
            patch.object(
                deactivation_mail_service.account_task_store,
                "create_task",
                side_effect=AssertionError("native HME must not create legacy tasks"),
            ),
            patch.object(
                deactivation_mail_service,
                "TaskReporter",
                side_effect=AssertionError("native HME must use structured events"),
            ),
        ):
            submitted = deactivation_mail_service.enqueue_bulk(
                [first_id, second_id],
                trigger="manual_hme_bulk",
            )
            self.assertEqual(2, len(submitted["started"]))
            self.assertEqual(
                1,
                len({item["task_id"] for item in submitted["started"]}),
            )
            self.assertEqual(
                1,
                len({item["run_id"] for item in submitted["started"]}),
            )
            self.assertTrue(all(item["shared_scan"] for item in submitted["started"]))
            run_id = submitted["started"][0]["run_id"]
            self.assertEqual("queued", operation.get_run(run_id)["status"])
            result = self._run_native("deactivation_mail", run_id)

        bulk_scan.assert_called_once_with(
            ["first@icloud.example", "second@icloud.example"],
            lookback_days=deactivation_mail_service._LOOKBACK_DAYS,
        )
        per_alias.assert_not_called()
        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(run_id)["status"])
        first = db.get_account(first_id)
        second = db.get_account(second_id)
        self.assertEqual("success", first["deactivation_mail_scan_status"])
        self.assertEqual("success", second["deactivation_mail_scan_status"])
        self.assertFalse(first.get("deactivation_mail_detected", False))
        self.assertTrue(second.get("deactivation_mail_detected", False))
        self.assertEqual("high", second["deactivation_mail_confidence"])

    def test_hme_bulk_persists_and_scans_more_than_operation_list_limit(self):
        account_ids = [
            self._account(
                f"bulk-{index:03d}@icloud.example",
                email_source="icloud_hide",
            )
            for index in range(121)
        ]
        expected_emails = [f"bulk-{index:03d}@icloud.example" for index in range(121)]
        results = {
            email: {
                "ok": True,
                "detected": False,
                "checked_at": "2026-09-14T12:00:00Z",
                "confidence": "none",
            }
            for email in expected_emails
        }

        with patch.object(
            deactivation_mail_service,
            "scan_hme_deactivation_bulk",
            return_value=results,
        ) as bulk_scan:
            submitted = deactivation_mail_service.enqueue_bulk(
                account_ids,
                trigger="manual_hme_large_bulk",
            )
            self.assertEqual(121, len(submitted["started"]))
            self.assertEqual(1, len({item["run_id"] for item in submitted["started"]}))
            run_id = int(submitted["started"][0]["run_id"])
            run = operation.get_run(run_id)
            self.assertEqual(121, run["data"]["account_count"])
            self.assertEqual(
                [100, 21],
                [len(batch) for batch in run["data"]["account_batches"]],
            )

            result = self._run_native("deactivation_mail", run_id)

        bulk_scan.assert_called_once_with(
            expected_emails,
            lookback_days=deactivation_mail_service._LOOKBACK_DAYS,
        )
        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(run_id)["status"])
        self.assertTrue(all(
            db.get_account(account_id)["deactivation_mail_scan_status"] == "success"
            for account_id in account_ids
        ))

    def test_hme_bulk_partial_failure_writes_each_alias_and_fails_coordinator(self):
        first_id = self._account("partial-first@icloud.example", email_source="icloud_hide")
        second_id = self._account("partial-second@icloud.example", email_source="icloud_hide")
        with patch.object(
            deactivation_mail_service,
            "scan_hme_deactivation_bulk",
            return_value={
                "partial-first@icloud.example": {
                    "ok": True,
                    "detected": False,
                    "checked_at": "2026-09-14T12:01:00Z",
                },
                "partial-second@icloud.example": {
                    "ok": False,
                    "error": "alias index unavailable",
                },
            },
        ) as bulk_scan:
            submitted = deactivation_mail_service.enqueue_bulk(
                [first_id, second_id],
                trigger="manual_hme_partial",
            )
            result = self._run_native("deactivation_mail", submitted["started"][0]["run_id"])

        bulk_scan.assert_called_once()
        run = operation.get_run(submitted["started"][0]["run_id"])
        self.assertEqual("failed", result["status"])
        self.assertEqual("failed", run["status"])
        self.assertTrue(run["result_summary"]["partial_failure"])
        self.assertEqual(1, run["result_summary"]["failed_count"])
        self.assertEqual("success", db.get_account(first_id)["deactivation_mail_scan_status"])
        self.assertEqual("failed", db.get_account(second_id)["deactivation_mail_scan_status"])
        self.assertIn("alias index unavailable", db.get_account(second_id)["deactivation_mail_error"])

    def test_hme_bulk_cancel_after_shared_scan_marks_unfanned_aliases_cancelled(self):
        first_id = self._account("cancel-first@icloud.example", email_source="icloud_hide")
        second_id = self._account("cancel-second@icloud.example", email_source="icloud_hide")
        submitted: dict | None = None

        def scan_then_cancel(emails, *, lookback_days):
            self.assertEqual(
                ["cancel-first@icloud.example", "cancel-second@icloud.example"],
                emails,
            )
            self.assertEqual(deactivation_mail_service._LOOKBACK_DAYS, lookback_days)
            self.assertIsNotNone(submitted)
            operation.request_run_cancel(int(submitted["started"][0]["run_id"]), reason="operator cancelled")
            return {
                "cancel-first@icloud.example": {"ok": True, "detected": False},
                "cancel-second@icloud.example": {"ok": True, "detected": True},
            }

        with patch.object(
            deactivation_mail_service,
            "scan_hme_deactivation_bulk",
            side_effect=scan_then_cancel,
        ) as bulk_scan:
            submitted = deactivation_mail_service.enqueue_bulk(
                [first_id, second_id],
                trigger="manual_hme_cancel",
            )
            result = self._run_native("deactivation_mail", submitted["started"][0]["run_id"])

        bulk_scan.assert_called_once()
        run = operation.get_run(submitted["started"][0]["run_id"])
        self.assertEqual("cancelled", result["status"])
        self.assertEqual("cancelled", run["status"])
        self.assertEqual(2, run["result_summary"]["cancelled_count"])
        self.assertEqual("cancelled", db.get_account(first_id)["deactivation_mail_scan_status"])
        self.assertEqual("cancelled", db.get_account(second_id)["deactivation_mail_scan_status"])
        self.assertFalse(db.get_account(first_id).get("deactivation_mail_detected", False))
        self.assertFalse(db.get_account(second_id).get("deactivation_mail_detected", False))

    def test_recovered_hme_run_closes_only_incomplete_account_projections(self):
        first_id = self._account("restart-first@icloud.example", email_source="icloud_hide")
        second_id = self._account("restart-second@icloud.example", email_source="icloud_hide")
        submitted = deactivation_mail_service.enqueue_bulk(
            [first_id, second_id],
            trigger="scheduled",
        )
        run_id = int(submitted["started"][0]["run_id"])
        db.update_account_deactivation_mail(first_id, {
            "status": "running",
            "trigger": "scheduled",
        })
        db.update_account_deactivation_mail(second_id, {
            "status": "success",
            "trigger": "scheduled",
            "detected": False,
            "checked_at": "2026-09-22T14:30:00+00:00",
        })
        operation.claim_run(run_id, execution_id="crashed-worker", worker_pid=987)
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE {postgres_store.qualified('operation_runs')} "
                "SET heartbeat_at=now() - interval '1 hour' WHERE id=%s",
                (run_id,),
            )

        self.assertEqual(1, operation.recover_interrupted_runtime_runs())
        self.assertEqual(1, deactivation_mail_service.reconcile_interrupted_scans())

        first = db.get_account(first_id)
        second = db.get_account(second_id)
        self.assertEqual("failed", first["deactivation_mail_scan_status"])
        self.assertIn("WebUI 重启", first["deactivation_mail_error"])
        self.assertFalse(first.get("deactivation_mail_checked_at"))
        self.assertEqual("success", second["deactivation_mail_scan_status"])
        self.assertTrue(operation.get_run(run_id)["result_summary"]["projection_reconciled"])

    def test_deactivation_native_handler_scans_mailbox_and_never_uses_hme_consumer(self):
        account_id = self._account(
            "mail-maintenance@example.test",
            email_source="cloudflare",
        )
        with (
            patch.object(deactivation_mail_service, "scan_cloudflare_deactivation", return_value={
                "detected": False,
                "checked_at": "2026-09-14T12:00:00+00:00",
                "confidence": "none",
            }),
            patch.object(deactivation_mail_service.account_task_store, "create_task", side_effect=AssertionError("legacy task")),
            patch.object(deactivation_mail_service, "TaskReporter", side_effect=AssertionError("legacy reporter")),
        ):
            submitted = deactivation_mail_service.enqueue(account_id, trigger="manual")
            self.assertTrue(submitted["accepted"])
            self.assertFalse(submitted.get("busy", False))
            result = self._run_native("deactivation_mail", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(submitted["run_id"])["status"])
        self.assertEqual("success", db.get_account(account_id)["deactivation_mail_scan_status"])

    def test_extract_native_handler_rechecks_token_and_writes_link_without_token_payload(self):
        account_id = self._account("extract-maintenance@example.test")
        with (
            patch.object(extract_link_service, "_cdk", return_value="test-cdk"),
            patch.object(extract_link_service, "_append_log", create=True),
            patch.object(live_check_service, "run_account_live_check_inline", return_value={
                "accepted": True,
                "result": {"ok": True, "status": "live"},
            }),
            patch.object(extract_link_service, "_create_extract_job", side_effect=lambda **kwargs: (
                kwargs["on_request_started"](),
                {"job_id": "job-1", "cdk_remaining": 2},
            )[1]),
            patch.object(extract_link_service, "_iter_sse_events", return_value=iter([
                ("result", {"result": {"long_url": "https://links.invalid/one", "payment_method": "pix"}}),
            ])),
            patch.object(extract_link_service.account_task_store, "create_task", side_effect=AssertionError("legacy task")),
            patch.object(extract_link_service, "TaskReporter", side_effect=AssertionError("legacy reporter")),
        ):
            submitted = extract_link_service.enqueue_account_extract(
                account_id=account_id,
                email="extract-maintenance@example.test",
                access_token="enqueue-token-must-not-be-stored",
                trigger="manual",
                link_type="pix",
                cdk="test-cdk",
            )
            self.assertTrue(submitted["accepted"])
            run = operation.get_run(submitted["run_id"])
            self.assertNotIn("access_token", run["data"])
            result = self._run_native("extract_link", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual("success", operation.get_run(submitted["run_id"])["status"])
        account = db.get_account(account_id)
        self.assertEqual("success", account["extract_link_status"])
        self.assertTrue(account["extract_link_ok"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("extract_job_create", run["data"]["remote_intent"]["action"])
        self.assertEqual("confirmed", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["outcome"])
        receipt_events = [
            event for event in operation.list_task_events(
                submitted["task_id"], run_id=submitted["run_id"], limit=100,
            )["items"]
            if event.get("event_type") == "remote.receipt_received"
        ]
        self.assertEqual(2, len(receipt_events))

    def test_native_extract_job_create_exception_is_request_unknown_without_retry(self):
        account_id = self._account("extract-job-unknown@example.test")

        def fail_create(**kwargs):
            kwargs["on_request_started"]()
            raise RuntimeError("extract service disconnected")

        with (
            patch.object(extract_link_service, "_cdk", return_value="test-cdk"),
            patch.object(extract_link_service, "_append_log", create=True),
            patch.object(live_check_service, "run_account_live_check_inline", return_value={
                "accepted": True,
                "result": {"ok": True, "status": "live"},
            }),
            patch.object(
                extract_link_service,
                "_create_extract_job",
                side_effect=fail_create,
            ),
            patch.object(extract_link_service, "_iter_sse_events", side_effect=AssertionError("no SSE after unknown create")),
            patch.object(extract_link_service, "TaskReporter", side_effect=AssertionError("native reporter")),
        ):
            submitted = extract_link_service.enqueue_account_extract(
                account_id=account_id,
                email="extract-job-unknown@example.test",
                access_token="enqueue-token-must-not-be-stored",
                trigger="manual",
                link_type="pix",
                cdk="test-cdk",
            )
            result = self._run_native("extract_link", submitted["run_id"])

        self.assertEqual("failed", result["status"])
        self.assertTrue(result["reconcile_required"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("unknown", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual("request_unknown", db.get_account(account_id)["extract_link_status"])

    def test_cancelled_queued_maintenance_run_is_not_claimed_or_executed(self):
        account_id = self._account("cancel-maintenance@example.test")
        with patch.object(plan_check_service, "_query_account_plan", side_effect=AssertionError("network must not run")):
            submitted = plan_check_service.enqueue_account_plan_check(
                account_id=account_id,
                email="cancel-maintenance@example.test",
                access_token="synthetic-access-token",
                trigger="manual",
            )
            cancelled = operation.request_run_cancel(int(submitted["run_id"]), reason="operator cancelled")
            self.assertEqual("cancelled", cancelled["status"])
            self.assertEqual(0, task_gateway.dispatch_registered_once(limit=20))

        self.assertEqual("cancelled", operation.get_run(submitted["run_id"])["status"])
        self.assertFalse(db.get_account(account_id).get("plan_check_ok"))


if __name__ == "__main__":
    import unittest

    unittest.main()
