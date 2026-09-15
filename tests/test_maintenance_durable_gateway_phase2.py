from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core import db, record_store
from core import deactivation_mail_service, extract_link_service, live_check_service, plan_check_service
from core.operations import task_gateway
from core.storage import operation
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
            patch("core.account_proxy.acquire_account_proxy", return_value=_Route()) as acquire,
            patch.object(plan_check_service, "check_account_plan", side_effect=check_plan),
        ):
            result = self._run_native("plan_check", submitted["run_id"])

        self.assertEqual("success", result["status"])
        self.assertEqual(7.0, seen["timeout"])
        self.assertEqual(1, seen["max_attempts"])
        self.assertEqual(0.0, seen["retry_delay"])
        self.assertEqual("direct", acquire.call_args.kwargs["source"])
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
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
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

    def test_native_services_have_no_legacy_consumer_handles(self):
        for service in (
            live_check_service,
            plan_check_service,
            deactivation_mail_service,
            extract_link_service,
        ):
            self.assertFalse(hasattr(service, "_EXECUTOR"), service.__name__)
            self.assertFalse(hasattr(service, "_ACCOUNT_EXECUTOR"), service.__name__)
        self.assertFalse(hasattr(deactivation_mail_service, "_HME_QUEUE"))
        self.assertFalse(hasattr(deactivation_mail_service, "_ensure_hme_coordinator"))

    def test_refresh_unknown_is_terminal_reconcile_state_and_does_not_fallback_or_retry(self):
        account_id = self._account("refresh-unknown@example.test")
        route = _Route()
        self.assertTrue(db.claim_account_live_check(account_id, trigger="token_refresh_manual"))
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
            patch("core.protocol_v2_liveness.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "protocol_v2_unknown_error",
            }) as refresh,
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.roxy_liveness.available", side_effect=AssertionError("unknown refresh must not fallback")),
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
        self.assertEqual("request_unknown", result["status"])
        self.assertTrue(result["manual_reconcile"])
        self.assertEqual("request_unknown", db.get_account(account_id)["live_check_status"])

    def test_native_refresh_unknown_finishes_attention_required_after_business_writeback(self):
        account_id = self._account("native-refresh-unknown@example.test")
        with (
            patch.object(live_check_service, "_append_log"),
            patch.object(live_check_service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch("core.account_proxy.acquire_account_proxy", return_value=_Route()),
            patch("core.protocol_v2_liveness.refresh_access_token", return_value={
                "ok": False,
                "status": "failed",
                "error": "protocol_v2_unknown_error",
            }),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.roxy_liveness.available", side_effect=AssertionError("unknown refresh must not fallback")),
            patch.object(live_check_service, "TaskReporter", side_effect=AssertionError("native reporter")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-unknown@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("request_unknown", result["status"])
        self.assertEqual("attention_required", result["database_status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("request_unknown", run["result_summary"]["outcome"])
        self.assertEqual("request_unknown", db.get_account(account_id)["live_check_status"])

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
            patch("core.account_proxy.acquire_account_proxy", return_value=_Route()),
            patch("core.protocol_v2_liveness.refresh_access_token", return_value=refresh_result) as refresh,
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
            patch("core.account_proxy.acquire_account_proxy", return_value=_Route()),
            patch(
                "core.protocol_v2_liveness.refresh_access_token",
                side_effect=RuntimeError("transport disconnected"),
            ),
            patch.object(live_check_service, "_roxy_fallback_enabled", return_value=True),
            patch("core.roxy_liveness.available", side_effect=AssertionError("must not retry unknown refresh")),
        ):
            submitted = live_check_service.enqueue_account_live_check(
                account_id=account_id,
                email="native-refresh-exception@example.test",
                trigger="token_refresh_manual",
                force_refresh=True,
            )
            result = self._run_native("token_refresh", submitted["run_id"])

        self.assertEqual("request_unknown", result["status"])
        run = operation.get_run(submitted["run_id"])
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("unknown", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("unknown", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual("request_unknown", db.get_account(account_id)["live_check_status"])

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
            patch.object(plan_check_service, "_query_account_plan", return_value={
                "ok": True,
                "http_status": 200,
                "current_plan_type": "free",
                "plus_trial_eligible": False,
            }),
            patch("core.account_proxy.acquire_account_proxy", return_value=route),
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
            patch.object(extract_link_service, "_create_extract_job", return_value={"job_id": "job-1", "cdk_remaining": 2}),
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
                side_effect=RuntimeError("extract service disconnected"),
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

        self.assertEqual("request_unknown", result["status"])
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
