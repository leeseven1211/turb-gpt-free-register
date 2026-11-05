"""AT 换线恢复沿用逻辑请求，保留历史未知回执并确认最终写回。"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import db
from core.accounts.liveness import service
from core.operations import task_gateway
from core.storage import records
from core.storage.operations import store as operation
from tests.support_pg import PostgresTestCase


class AtNetworkRecoveryStorageTests(PostgresTestCase):
    def setUp(self):
        task_gateway.init()
        operation.reset_ready()
        operation.init()
        service.register_operation_handlers()

    def scenario(self, final_result):
        email = "network-recovery@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email, "access_token": "fixture-old-at", "email_source": "cloudflare",
            "account_status": "active", "registration_proxy_region": "IN",
            "created_at": "2026-11-05T10:00:00", "updated_at": "2026-11-05T10:00:00",
        })
        calls, routes = [], []

        def acquire(**kwargs):
            route = SimpleNamespace(proxy_url=f"http://192.0.2.{len(routes)+1}:8080", release=Mock())
            route.public_dict = lambda: {"network_route": "proxy", "proxy_mode": "pool",
                                        "proxy_provider": "test", "proxy_region": kwargs.get("region")}
            routes.append(route)
            return route

        def refresh(_email, **kwargs):
            kwargs["proxy_supplier"](1)
            calls.append(1)
            if len(calls) == 1:
                kwargs["on_remote_request_started"]()
                return {"ok": False, "status": "failed", "error": "email_otp_failed",
                        "error_category": "email", "live_check_driver": "protocol_v2",
                        "roxy_fallback_allowed": False,
                        "auth_diagnostics": {"operation": "email_otp_send", "failure_kind": "transport_error",
                                             "exception_type": "SSLError", "curl_error_code": 35}}
            if not (final_result.get("mutation_submitted") is False):
                kwargs["on_remote_request_started"]()
            return dict(final_result)

        values = {"ACCOUNT_AT_REFRESH_DRIVER": "protocol", "OPENAI_PROTOCOL_VERSION": "v2",
                  "ACCOUNT_AT_REFRESH_COUNTRY": "JP", "ACCOUNT_AT_REFRESH_NETWORK_RETRIES": 1,
                  "ACCOUNT_AT_REFRESH_NETWORK_TIMEOUT_SECONDS": 900, "LIVE_CHECK_ROXY_FALLBACK_ENABLED": False,
                  "ACCOUNT_ACTION_PROXY_RETRY_DELAY": 0}
        snapshot = SimpleNamespace(revision=905, as_dict=lambda: values)
        with (
            patch.object(service, "get_config_snapshot", return_value=snapshot),
            patch.object(service, "_resolve_refresh_driver", return_value="protocol_v2"),
            patch.object(service, "_append_log"),
            patch.object(task_gateway, "notify_dispatch"),
            patch("core.proxy.account_routes.acquire_account_proxy", side_effect=acquire),
            patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=refresh),
            patch("core.accounts.liveness.protocol.legacy.check_account_liveness", side_effect=AssertionError("测试不得调用未替换的驱动")),
        ):
            submitted = service.enqueue_account_live_check(account_id=account_id, email=email, force_refresh=True,
                                                          trigger="fixture_network_recovery")
            self.assertTrue(submitted["accepted"])
            task_gateway._execute_operation_handler("token_refresh", submitted["run_id"])
        run = operation.get_run(submitted["run_id"])
        events = operation.list_task_events(submitted["task_id"], run_id=submitted["run_id"], limit=200)["items"]
        return account_id, run, events, routes, calls

    def test_unknown_attempt_then_new_route_success_keeps_history_and_confirms_same_intent(self):
        account_id, run, events, routes, calls = self.scenario({
            "ok": True, "status": "live", "access_token": "fixture-new-at",
            "session": {"account": {"planType": "free"}}, "auth_method": "email_otp",
            "live_check_driver": "protocol_v2", "roxy_fallback_allowed": False,
        })
        self.assertEqual(2, len(calls))
        self.assertEqual("success", run["status"])
        self.assertEqual("confirmed", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual("confirmed", run["data"]["remote_receipt"]["outcome"])
        self.assertEqual(1, sum(event["event_type"] == "remote.request_started" for event in events))
        self.assertTrue(any(event["event_type"] == "remote.receipt_unknown" for event in events))
        self.assertEqual("fixture-new-at", db.get_account(account_id)["access_token"])
        self.assertTrue(any(call.kwargs.get("fault") is True for call in routes[0].release.call_args_list))
        self.assertEqual(1, run["result_summary"]["network_recovery"]["route_retries"])

    def test_later_preflight_failure_cannot_downgrade_previous_unknown_intent(self):
        _, run, events, _, calls = self.scenario({
            "ok": False, "status": "failed", "error": "password_missing", "error_category": "configuration",
            "mutation_submitted": False, "action_dispatched": False, "remote_request_started": False,
            "roxy_fallback_allowed": False,
        })
        self.assertEqual(2, len(calls))
        self.assertEqual("attention_required", run["status"])
        self.assertEqual("unknown", run["data"]["remote_intent"]["receipt_state"])
        self.assertEqual(1, sum(event["event_type"] == "remote.request_started" for event in events))
        self.assertTrue(any(event["event_type"] == "remote.receipt_unknown" for event in events))
