"""独立 AT 刷新在登录前固定国家，查活和同链显式线路保持原行为。"""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from config import account as account_config
from core.accounts.liveness import service


EMAIL = "at-country@example.test"
ACCOUNT = {"id": 7, "email": EMAIL, "access_token": "fixture-at"}


class AtRefreshCountryPolicyTests(unittest.TestCase):
    def test_snapshot_country_wins_over_current_configuration(self):
        with (
            patch.object(account_config, "ACCOUNT_AT_REFRESH_COUNTRY", "IN"),
            patch("core.proxy.account_routes.resolve_account_region") as registration,
        ):
            country = service._resolve_at_refresh_country(
                account_id=7, email=EMAIL, config_snapshot={"refresh_at_country": " us "},
            )
        self.assertEqual("US", country)
        registration.assert_not_called()

    def test_empty_and_historical_snapshots_follow_the_registration_country(self):
        for snapshot in ({"refresh_at_country": ""}, {"refresh_at_country": None}, {}):
            with (
                self.subTest(snapshot=snapshot),
                patch.object(account_config, "ACCOUNT_AT_REFRESH_COUNTRY", "US"),
                patch("core.proxy.account_routes.resolve_account_region", return_value="JP") as registration,
            ):
                country = service._resolve_at_refresh_country(account_id=7, email=EMAIL, config_snapshot=snapshot)
            self.assertEqual("JP", country)
            registration.assert_called_once_with(account_id=7, email=EMAIL)

    def test_compatibility_call_without_snapshot_reads_current_policy(self):
        for configured, expected in (("US", "US"), ("", "JP")):
            with (
                self.subTest(configured=configured),
                patch.object(account_config, "ACCOUNT_AT_REFRESH_COUNTRY", configured),
                patch("core.proxy.account_routes.resolve_account_region", return_value="JP") as registration,
            ):
                country = service._resolve_at_refresh_country(account_id=7, email=EMAIL, config_snapshot=None)
            self.assertEqual(expected, country)
            self.assertEqual(not configured, registration.called)

    def test_invalid_saved_country_is_rejected_before_route_acquisition(self):
        for value in ("Rand", "USA", "ZZ", "JP,US"):
            with self.subTest(value=value), patch("core.proxy.account_routes.resolve_account_region") as registration:
                with self.assertRaisesRegex(ValueError, "ISO"):
                    service._resolve_at_refresh_country(
                        account_id=7, email=EMAIL, config_snapshot={"refresh_at_country": value},
                    )
                registration.assert_not_called()

    def test_enqueue_projects_the_country_into_the_frozen_run_snapshot(self):
        with (
            patch.object(service, "get_config_snapshot", return_value={"ACCOUNT_AT_REFRESH_COUNTRY": "US"}),
            patch.object(service, "_resolve_refresh_driver", return_value="legacy"),
            patch.object(service, "deployment_unavailable", return_value=None),
            patch.object(service, "register_operation_handlers"),
            patch.object(service, "_captured_proxy_source", return_value="pool"),
            patch.object(service, "_append_log"),
            patch.object(service.db, "get_account", return_value=dict(ACCOUNT)),
            patch.object(service.db, "account_is_deactivated", return_value=False),
            patch.object(service.db, "claim_account_live_check", return_value=True),
            patch.object(service.account_task_store, "submit_durable_operation", return_value={
                "accepted": True, "task_id": 17, "run_id": 27,
            }) as submit,
        ):
            result = service.enqueue_account_live_check(account_id=7, email=EMAIL, force_refresh=True)
        self.assertTrue(result["accepted"])
        self.assertEqual("ACCOUNT_AT_REFRESH_COUNTRY", service.LIVE_CONFIG_ALLOWLIST["refresh_at_country"])
        self.assertEqual("US", submit.call_args.kwargs["config_snapshot"]["refresh_at_country"])


class AtRefreshCountryRoutingTests(unittest.TestCase):
    def run_worker(self, *, driver="v2", policy="US", force_refresh=True, proxy=None,
                   attempts=1, registration_countries=None, protocol_result=None, completion_auth=False,
                   acquisition_errors=()):
        routes = []
        calls = []
        errors = iter(acquisition_errors)

        def acquire(**kwargs):
            calls.append(dict(kwargs))
            error = next(errors, None)
            if error is not None:
                raise error
            route = SimpleNamespace(
                proxy_url=kwargs.get("explicit_proxy") or f"http://fixture-route-{len(routes)}.invalid:8080",
                release=Mock(),
            )
            region = kwargs.get("region")
            route.public_dict = lambda: {"network_route": "proxy", "proxy_region": region}
            routes.append(route)
            return route

        def success():
            return {"ok": True, "status": "live", "access_token": "fixture-fresh", "session": {}}

        def protocol(_email, **kwargs):
            supplier = kwargs.get("proxy_supplier")
            if supplier:
                for attempt in range(1, attempts + 1):
                    supplier(attempt)
            return dict(protocol_result) if protocol_result is not None else success()

        snapshot = {"refresh_at_country": policy, "roxy_fallback_enabled": protocol_result is not None,
                    "auth_raw_context_enabled": False, "proxy_retry_limit": 1, "proxy_retry_delay": 0}
        with ExitStack() as stack:
            for item in (
                patch.object(service.db, "mark_account_live_check_running", return_value=True),
                patch.object(service.db, "get_account", return_value=dict(ACCOUNT)),
                patch.object(service.db, "update_account_liveness", return_value=True),
                patch.object(service, "_reporter", return_value=MagicMock()),
                patch.object(service, "_append_log"),
                patch.object(service, "_checkpoint"),
                patch.object(service, "token_claims", return_value={}),
                patch.object(service, "_resolve_protocol_identity", return_value=None),
                patch("core.proxy.account_routes.acquire_account_proxy", side_effect=acquire),
                patch("core.accounts.liveness.roxy.flow.available", return_value=True),
                patch("core.accounts.liveness.protocol.v2.refresh_access_token", side_effect=protocol),
                patch("core.accounts.liveness.protocol.v3.refresh_access_token", side_effect=protocol),
                patch.object(service, "check_account_liveness", side_effect=protocol),
                patch("core.accounts.liveness.roxy.flow.refresh_access_token", side_effect=lambda *_args, **_kwargs: success()),
                patch.object(service, "run_probe", return_value={"ok": True, "http_status": 200}),
            ):
                stack.enter_context(item)
            registration = stack.enter_context(patch(
                "core.proxy.account_routes.resolve_account_region",
                side_effect=registration_countries or ["JP", "IN"],
            ))
            result = service._run_live_check(
                account_id=7, email=EMAIL, trigger="fixture", proxy=proxy,
                force_refresh=force_refresh, refresh_driver=driver if force_refresh else None,
                driver=None if force_refresh else "protocol_current", config_snapshot=snapshot,
                completion_auth=completion_auth,
            )
        return result, calls, routes, registration

    def test_all_refresh_drivers_apply_the_same_fixed_country_before_login(self):
        for driver in ("v1", "v2", "v3", "browser_roxy"):
            with self.subTest(driver=driver):
                result, calls, _, registration = self.run_worker(driver=driver)
                self.assertTrue(result["ok"])
                self.assertEqual(["US"], [call["region"] for call in calls])
                self.assertEqual("token-refresh", calls[0]["purpose"])
                registration.assert_not_called()

    def test_preflight_rotations_resolve_follow_country_once_for_the_whole_run(self):
        result, calls, routes, registration = self.run_worker(policy="", attempts=3)
        self.assertTrue(result["ok"])
        registration.assert_called_once_with(account_id=7, email=EMAIL)
        self.assertEqual(["JP", "JP", "JP"], [call["region"] for call in calls])
        self.assertEqual([0, 1, 2], [call["rotation_index"] for call in calls])
        self.assertTrue(all(route.release.call_count == 1 for route in routes))

    def test_route_acquisition_retries_preserve_the_selected_country(self):
        result, calls, _, registration = self.run_worker(
            policy="", acquisition_errors=(RuntimeError("1024Proxy 获取失败：临时连接失败"),),
        )
        self.assertTrue(result["ok"])
        registration.assert_called_once()
        self.assertEqual(["JP", "JP"], [call["region"] for call in calls])
        self.assertEqual([0, 1], [call["rotation_index"] for call in calls])

    def test_roxy_fallback_keeps_the_same_follow_country(self):
        result, calls, _, registration = self.run_worker(policy="", protocol_result={
            "ok": False, "status": "failed", "error": "network_preflight_failed",
            "remote_request_started": False, "roxy_fallback_allowed": True,
        })
        self.assertTrue(result["ok"])
        registration.assert_called_once()
        self.assertEqual(["JP", "JP"], [call["region"] for call in calls])
        self.assertEqual([0, 4], [call["rotation_index"] for call in calls])

    def test_explicit_same_chain_route_is_reused_without_a_country_override(self):
        proxy = "http://same-chain.invalid:8080"
        result, calls, _, registration = self.run_worker(proxy=proxy)
        self.assertTrue(result["ok"])
        registration.assert_not_called()
        self.assertEqual(1, len(calls))
        self.assertEqual(proxy, calls[0]["explicit_proxy"])
        self.assertNotIn("region", calls[0])

    def test_empty_explicit_route_still_acquires_with_the_fixed_country(self):
        result, calls, _, _ = self.run_worker(proxy="")
        self.assertTrue(result["ok"])
        self.assertEqual("US", calls[0]["region"])
        self.assertNotIn("explicit_proxy", calls[0])

    def test_ordinary_liveness_does_not_read_or_apply_refresh_country(self):
        result, calls, _, registration = self.run_worker(force_refresh=False)
        self.assertTrue(result["ok"])
        registration.assert_not_called()
        self.assertEqual("live-check", calls[0]["purpose"])
        self.assertNotIn("region", calls[0])

    def test_completion_explicit_refresh_also_uses_the_independent_country(self):
        result, calls, _, registration = self.run_worker(completion_auth=True)
        self.assertTrue(result["ok"])
        self.assertEqual("US", calls[0]["region"])
        registration.assert_not_called()


if __name__ == "__main__":
    unittest.main()
