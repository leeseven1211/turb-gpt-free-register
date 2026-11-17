"""受管 CLI 线路恢复和调用方自带代理的资源边界。"""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.network.protocol_traffic import current_correlation
from core.registration import service
from core.registration.route_recovery import (
    RegistrationRouteFailure, current_route_recovery, managed_registration_proxy,
)
from core.registration.standalone import _run_managed_registration_driver
from core.storage import registration
from tests.support_pg import PostgresTestCase


class ManagedRouteCliTests(PostgresTestCase):
    @staticmethod
    def lease(index):
        return SimpleNamespace(
            proxy_url=f"http://192.0.2.{index}:8080", exit_ip=f"198.51.100.{index}",
            region="JP", lease_id=f"cli-{index}",
        )

    def context(self):
        attempt = registration.create_attempt("managed-cli@example.test")
        run = registration.start_run(
            attempt["id"], execution_id="managed-cli", initial_status="running",
        )
        return {"attempt_id": attempt["id"], "run_id": run["id"], "execution_id": "managed-cli", "job_id": None}

    def test_managed_cli_rotates_and_returns_the_final_lease_to_its_owner(self):
        facts = self.context()
        old, new = self.lease(1), self.lease(2)
        seen = []

        def driver(**kwargs):
            seen.append(current_correlation())
            lease = current_route_recovery()(
                RegistrationRouteFailure("session", http_status=403, response_received=True, replay_safe=True),
                kwargs["proxy"],
            )
            self.assertIs(lease, new)
            seen.append(current_correlation())
            return {"success": False, "error": "合成终态"}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "registration_fact_context", return_value=facts))
            stack.enter_context(patch.object(service, "check_stop_requested"))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=1))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_delay", return_value=0))
            stack.enter_context(patch.object(service, "_bind_progress_route_context"))
            acquire = stack.enter_context(patch("core.proxy.provider.acquire_registration_proxy", return_value=new))
            release = stack.enter_context(patch("core.proxy.provider.release_proxy"))
            with managed_registration_proxy(old) as owner:
                _run_managed_registration_driver(
                    driver, {"email": "managed-cli@example.test", "proxy": old.proxy_url},
                    driver_name="protocol_oss_2",
                )
                self.assertIs(owner.lease, new)
        self.assertEqual([item["route_attempt_no"] for item in seen], [1, 2])
        self.assertEqual([item["proxy_lease_id"] for item in seen], ["cli-1", "cli-2"])
        self.assertEqual(acquire.call_args.kwargs["excluded_exit_ip"], "198.51.100.1")
        release.assert_called_once()
        self.assertEqual(current_correlation(), {})
        self.assertIsNone(current_route_recovery())

    def test_default_roxy_with_no_budget_has_no_active_recovery_callback(self):
        facts = self.context()
        lease = self.lease(1)
        observed = []
        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "registration_fact_context", return_value=facts))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=0))
            with managed_registration_proxy(lease) as owner:
                _run_managed_registration_driver(
                    lambda **kwargs: observed.append(current_route_recovery()) or {
                        "success": False, "current_lease_route_verified": True,
                        "route_failure": RegistrationRouteFailure("preauth", transport_kind="timeout", replay_safe=True),
                    },
                    {"email": "managed-cli@example.test", "proxy": lease.proxy_url}, driver_name="roxy",
                )
                self.assertTrue(owner.fault)
        self.assertEqual(observed, [None])

    def test_caller_supplied_proxy_does_not_acquire_a_pool_route(self):
        seen = []
        with patch("core.proxy.provider.acquire_registration_proxy") as acquire:
            result = _run_managed_registration_driver(
                lambda **kwargs: seen.append(current_route_recovery()) or {"success": False},
                {"email": "managed-cli@example.test", "proxy": self.lease(1).proxy_url},
                driver_name="protocol_oss_2",
            )
        self.assertEqual(seen, [None])
        self.assertFalse(result["success"])
        acquire.assert_not_called()

    def test_cli_final_run_preserves_structured_current_route_failure(self):
        from core.registration.standalone import run_registration_in_context
        seen = []
        failure = RegistrationRouteFailure("preauth", http_status=403, response_received=True, replay_safe=True)

        def driver(**kwargs):
            seen.append(service.registration_fact_context())
            return {
                "success": False, "error": "当前认证请求 HTTP 403",
                "route_failure": failure, "cause_code": "protocol_auth_http_failed",
            }

        with (
            managed_registration_proxy(self.lease(1)),
            patch.object(service, "_registration_proxy_retry_limit", return_value=0),
        ):
            run_registration_in_context(
                driver, {"email": "run-failure@example.test", "name": "测试", "proxy": self.lease(1).proxy_url},
                driver_name="roxy",
            )
        summary = registration.get_run(seen[0]["run_id"])["result_summary"]
        self.assertEqual(summary["route_failure"]["http_status"], 403)
        self.assertEqual(summary["route_failure"]["operation"], "preauth")
        self.assertEqual(summary["cause_code"], "protocol_auth_http_failed")
