"""补密码预检换线、故障隔离及提交后不重放的回归。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.accounts.password_setup.proxy import is_proxy_transport_failure
from core.accounts.password_setup.route_recovery import AccountActionRouteFailure
from core.network.protocol_traffic import current_correlation
from tests.accounts import test_password_setup_integration as integration


def route(number):
    return SimpleNamespace(
        proxy_url=f"http://route-{number}.example:8080", provider=f"provider-{number}",
        region="JP", mode="pool", release=Mock(),
        lease=SimpleNamespace(lease_id=f"lease-{number}", exit_ip=f"192.0.2.{number}"),
        public_dict=lambda: {"network_route": "proxy", "proxy_mode": "pool", "proxy_provider": f"provider-{number}"},
    )


class PasswordProxyRotationTests(unittest.TestCase):
    def run_worker(self, behavior, routes, **kwargs):
        return integration.PasswordSetupIntegrationTests().run_setup(
            password_behavior=behavior, routes=routes, **kwargs,
        )[0]

    def test_step_403_and_preflight_share_four_routes_and_exclude_all_failed_exits(self):
        routes = [route(n) for n in range(1, 5)]
        requests = []
        failure = AccountActionRouteFailure("authorize", "GET", http_status=403)
        seen = []

        def behavior(supplier, failed, recover):
            self.assertEqual(routes[0].proxy_url, supplier(1))
            self.assertEqual(routes[1].proxy_url, recover(failure, routes[0].proxy_url))
            seen.append(current_correlation())
            failed(TimeoutError("request timed out"))
            self.assertEqual(routes[2].proxy_url, supplier(2))
            self.assertEqual(routes[3].proxy_url, recover(failure, routes[2].proxy_url))
            seen.append(current_correlation())
            self.assertIsNone(recover(failure, routes[3].proxy_url))
            return {"ok": False, "status": "failed", "error_code": "account_action_route_exhausted"}

        result = integration.PasswordSetupIntegrationTests().run_setup(
            routes=routes, route_behavior=behavior, proxy_country="JP", route_requests=requests,
        )[0]
        self.assertFalse(result["ok"])
        self.assertEqual(4, len(requests))
        self.assertEqual([{"192.0.2.1"}, {"192.0.2.1", "192.0.2.2"},
                          {"192.0.2.1", "192.0.2.2", "192.0.2.3"}],
                         [set(request["excluded_exit_ips"]) for request in requests[1:]])
        self.assertTrue(all(request["region"] == "JP" for request in requests))
        self.assertEqual([2, 4], [correlation["route_attempt_no"] for correlation in seen])
        for current in routes:
            current.release.assert_called_once()

    def test_step_recovery_cancellation_releases_current_lease_without_reacquiring(self):
        from core.operations.runtime import OperationCancelled

        current = route(1)

        def behavior(supplier, _failed, _recover):
            supplier(1)
            raise OperationCancelled("已取消")

        result = integration.PasswordSetupIntegrationTests().run_setup(
            routes=[current], route_behavior=behavior,
        )[0]
        self.assertEqual("stopped", result["status"])
        current.release.assert_called_once()

    def test_local_transport_init_failure_after_rotation_does_not_quarantine_new_lease(self):
        from core.accounts.password_setup import route_recovery
        from tests.accounts.test_account_action_route_session import session

        first, second = route(1), route(2)

        def behavior(supplier, failed, recover):
            supplier(1)
            current = session(RuntimeError("curl: (56) Proxy CONNECT aborted"))
            current.proxy = first.proxy_url
            client = route_recovery.AccountActionSession(
                current, recover=recover, check=lambda: None, observe=failed,
            )
            with patch.object(route_recovery, "Session", side_effect=RuntimeError("local transport init failed")):
                try:
                    client.get("https://auth.openai.com/oauth/authorize")
                except route_recovery.AccountActionRouteHalt as halted:
                    error = halted.error
                    return {
                        "ok": False, "status": "failed", "error_code": error.code,
                        "proxy_transport_failed": error.proxy_transport_failed,
                    }
            self.fail("本地 transport 初始化失败必须停止原请求")

        result = integration.PasswordSetupIntegrationTests().run_setup(
            routes=[first, second], route_behavior=behavior,
        )[0]
        self.assertEqual("account_action_route_unavailable", result["error_code"])
        first.release.assert_called_once_with(reason="account-action-route-rotate", fault=True)
        second.release.assert_called_once()
        self.assertFalse(second.release.call_args.kwargs.get("fault", False))

    def test_native_cancellation_during_replacement_pool_wait_stops_without_delivering_a_lease(self):
        from core.operations.runtime import CancellationToken, operation_context

        current = route(1)
        token = CancellationToken(51, "fixture-token", lambda *_: False)
        acquired = []

        def acquire(**kwargs):
            acquired.append(kwargs)
            if len(acquired) == 1:
                return current
            token.request_local()
            kwargs["cancel"]()
            raise AssertionError("原生取消必须在代理池等待检查点传播")

        def behavior(supplier, _failed, recover):
            supplier(1)
            recover(AccountActionRouteFailure("authorize", "GET", http_status=403), current.proxy_url)
            self.fail("取消后不得继续返回线路")

        with operation_context(token):
            result = integration.PasswordSetupIntegrationTests().run_setup(
                routes=acquire, route_behavior=behavior,
            )[0]
        self.assertEqual("stopped", result["status"])
        self.assertEqual(2, len(acquired))
        current.release.assert_called_once()

    def test_rotates_and_quarantines_only_failed_proxy_and_updates_traffic_owner(self):
        first, second = route(1), route(2)
        correlations = []

        def login(supplier, failed):
            self.assertEqual(first.proxy_url, supplier(1))
            correlations.append(current_correlation())
            failed(RuntimeError("curl: (56) Proxy CONNECT aborted; private credential"))
            self.assertEqual(second.proxy_url, supplier(2))
            correlations.append(current_correlation())
            return {"ok": True, "status": "success", "message": "原密码有效"}

        before = current_correlation()
        result = self.run_worker(login, [first, second], proxy_country="JP")

        self.assertTrue(result["ok"])
        first.release.assert_called_once_with(reason="password-preflight-rotate", fault=True)
        second.release.assert_called_once()
        self.assertNotIn("fault", second.release.call_args.kwargs)
        self.assertEqual("provider-2", result["proxy_provider"])
        self.assertEqual(["lease-1", "lease-2"], [r["proxy_lease_id"] for r in correlations])
        self.assertEqual([1, 2], [r["route_attempt_no"] for r in correlations])
        self.assertEqual(before, current_correlation())

    def test_http_rejection_and_plain_timeout_rotate_without_quarantining(self):
        for failure in (RuntimeError("Auth authorize 路由被拒绝: HTTP 403"), TimeoutError("request timed out")):
            with self.subTest(failure=type(failure).__name__):
                first, second = route(1), route(2)

                def login(supplier, failed):
                    supplier(1)
                    failed(failure)
                    supplier(2)
                    return {"ok": True, "status": "success"}

                self.assertTrue(self.run_worker(login, [first, second])["ok"])
                first.release.assert_called_once_with(reason="password-preflight-rotate", fault=False)
                self.assertNotIn("fault", second.release.call_args.kwargs)

    def test_exhausted_proxy_failure_quarantines_final_route(self):
        current = route(1)

        def login(supplier, failed):
            supplier(1)
            failed(RuntimeError("curl: (7) CONNECT tunnel failed, response 502"))
            return {"ok": False, "status": "failed"}

        self.assertFalse(self.run_worker(login, [current])["ok"])
        self.assertIs(current.release.call_args.kwargs["fault"], True)

    def test_otp_timeout_does_not_rotate_or_quarantine(self):
        current = route(1)

        def login(supplier, failed):
            supplier(1)
            failed(TimeoutError("等待邮箱验证码超时"))
            return {"ok": False, "status": "failed", "error_code": "password_setup_email_otp_failed"}

        self.assertFalse(self.run_worker(login, [current])["ok"])
        current.release.assert_called_once()
        self.assertNotIn("fault", current.release.call_args.kwargs)

    def test_unknown_password_submission_is_preserved_and_fault_isolated_without_retry(self):
        current = route(1)

        def login(supplier, _failed):
            supplier(1)
            return {"ok": False, "status": "attention_required", "mutation_submitted": True,
                    "remote_receipt_state": "unknown", "proxy_transport_failed": True}

        result = self.run_worker(login, [current])
        self.assertFalse(result["ok"])
        self.assertTrue(result["mutation_submitted"])
        self.assertEqual("unknown", result["remote_receipt_state"])
        current.release.assert_called_once()
        self.assertIs(current.release.call_args.kwargs["fault"], True)

    def test_replacement_acquisition_failure_releases_original_once(self):
        current = route(1)

        def login(supplier, failed):
            supplier(1)
            failed(RuntimeError("Proxy CONNECT aborted"))
            try:
                supplier(2)
            except RuntimeError:
                return {"ok": False, "status": "failed", "message": "新线路暂不可用"}
            self.fail("新线路申请应失败")

        result = self.run_worker(login, [current, RuntimeError("新线路暂不可用")])
        self.assertFalse(result["ok"])
        self.assertEqual("新线路暂不可用", result["message"])
        current.release.assert_called_once_with(reason="password-preflight-rotate", fault=True)

    def test_preflight_uses_four_distinct_routes_and_reports_each_failure(self):
        from core.accounts.liveness.protocol import legacy

        supplier, failed = Mock(side_effect=[f"proxy-{n}" for n in range(4)]), Mock()
        sessions = [SimpleNamespace(session=Mock(), proxy=f"proxy-{n}") for n in range(4)]
        with patch.object(legacy, "BrowserSession", side_effect=sessions), \
                patch.object(legacy, "_warm_protocol_login_context", side_effect=RuntimeError("Proxy CONNECT aborted")), \
                patch.object(legacy.time, "sleep"):
            with self.assertRaises(RuntimeError):
                legacy._network_preflight_with_retry("fixture@example.test", None,
                    proxy_supplier=supplier, on_preflight_failure=failed)
        self.assertEqual([1, 2, 3, 4], [c.args[0] for c in supplier.call_args_list])
        self.assertEqual(4, failed.call_count)
        self.assertEqual(4, len({s.proxy for s in sessions}))
        for session in sessions:
            session.session.close.assert_called_once()

    def test_v2_auth_passes_supplier_and_failure_callback_to_preflight(self):
        from core.accounts.liveness.protocol import v2

        supplier, failed = Mock(), Mock()
        terminal = RuntimeError("Proxy CONNECT aborted")
        with patch.object(v2, "get_account_login_credentials", return_value=("fixture-password", "")), \
                patch.object(v2, "_network_preflight_with_retry", side_effect=terminal) as preflight:
            result = v2.refresh_access_token("fixture@example.test", proxy=None,
                proxy_supplier=supplier, on_network_failure=failed)
        self.assertFalse(result["ok"])
        self.assertIs(supplier, preflight.call_args.kwargs["proxy_supplier"])
        self.assertIs(failed, preflight.call_args.kwargs["on_preflight_failure"])
        failed.assert_called_once_with(terminal)

    def test_cancelled_failure_observer_closes_session_and_does_not_acquire_another_route(self):
        from core.accounts.liveness.protocol import legacy
        from core.operations.runtime import OperationCancelled

        session = SimpleNamespace(session=Mock(), proxy="fixture-route")
        supplier = Mock(return_value="fixture-route")
        with patch.object(legacy, "BrowserSession", return_value=session), \
                patch.object(legacy, "_warm_protocol_login_context", side_effect=RuntimeError("Proxy CONNECT aborted")):
            with self.assertRaises(OperationCancelled):
                legacy._network_preflight_with_retry("fixture@example.test", None,
                    proxy_supplier=supplier, on_preflight_failure=Mock(side_effect=OperationCancelled("已取消")))
        session.session.close.assert_called_once()
        supplier.assert_called_once_with(1)

    def test_only_explicit_proxy_transport_evidence_is_quarantined(self):
        for message, expected in (
            ("Proxy CONNECT aborted", True), ("CONNECT tunnel failed, response 502", True),
            ("Could not resolve proxy", True), ("curl: (56) connection reset", False),
            ("curl: (28) request timed out", False), ("HTTP 403", False),
            ("password_reset_required", False), ("等待邮箱验证码超时", False),
        ):
            with self.subTest(message=message):
                self.assertIs(is_proxy_transport_failure(RuntimeError(message)), expected)
