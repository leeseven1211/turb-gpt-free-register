"""注册业务换线只消费当前动作事实，与代理供应商无关。"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from core.registration import service


class RegistrationRoutePolicyRegressionTests(TestCase):
    def test_structured_preauth_transport_rotates_for_every_supplier(self):
        result = {
            "error": "ProxyConnectionError",
            "registration_diagnostics": {
                "operation": "preauth", "failure_kind": "transport_error",
                "exception_type": "ProxyConnectionError",
                "exception_chain": ["ProxyConnectionError"],
            },
        }
        with patch.object(service, "_registration_proxy_retry_limit", return_value=2):
            for provider in ("1024proxy", "711proxy", "proxy_pool", "future_supplier"):
                with self.subTest(provider=provider):
                    self.assertTrue(service._should_retry_registration_with_new_proxy(
                        result, SimpleNamespace(provider=provider), 0,
                    ))

    def test_current_preauth_403_rotates_without_cloudflare_marker(self):
        result = {
            "error": "认证入口被拒绝",
            "registration_diagnostics": {
                "operation": "preauth", "failure_kind": "http_error",
                "http_status": 403, "exception_type": "RuntimeError",
            },
        }
        with patch.object(service, "_registration_proxy_retry_limit", return_value=2):
            self.assertTrue(service._should_retry_registration_with_new_proxy(
                result, SimpleNamespace(provider="711proxy"), 0,
            ))

    def test_unknown_password_submission_is_not_restarted_as_registration(self):
        result = {
            "error": "TimeoutError", "request_unknown": True,
            "registration_diagnostics": {
                "operation": "password_submit", "failure_kind": "transport_error",
                "exception_type": "TimeoutError",
            },
        }
        with patch.object(service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(service._should_retry_registration_with_new_proxy(
                result, SimpleNamespace(provider="711proxy"), 0,
            ))

    def test_historical_403_text_cannot_override_current_business_failure(self):
        result = {
            "error": "历史 HTTP 403；本次验证码错误",
            "registration_diagnostics": {
                "operation": "otp_validate", "failure_kind": "http_error",
                "http_status": 401, "exception_type": "RuntimeError",
            },
        }
        with patch.object(service, "_registration_proxy_retry_limit", return_value=2):
            self.assertFalse(service._should_retry_registration_with_new_proxy(
                result, SimpleNamespace(provider="711proxy"), 0,
            ))


class RegistrationRouteFailureContractTests(TestCase):
    def failure(self, method, url, **kwargs):
        from core.registration.route_recovery import registration_route_failure
        return registration_route_failure(method, url, **kwargs)

    def test_403_on_password_creation_is_a_rejected_current_request(self):
        failure = self.failure(
            "POST", "https://auth.openai.com/api/accounts/user/register",
            response=SimpleNamespace(status_code=403),
        )
        self.assertEqual(failure.operation, "password_create")
        self.assertEqual(failure.http_status, 403)
        self.assertTrue(failure.response_received)
        self.assertTrue(failure.replay_safe)

    def test_password_timeout_preserves_unknown_write_semantics(self):
        failure = self.failure(
            "POST", "https://auth.openai.com/api/accounts/user/register",
            error=TimeoutError(),
        )
        self.assertEqual(failure.transport_kind, "timeout")
        self.assertFalse(failure.response_received)
        self.assertFalse(failure.replay_safe)

    def test_signin_timeout_does_not_imply_password_creation(self):
        failure = self.failure(
            "POST", "https://chatgpt.com/api/auth/signin/openai", error=TimeoutError(),
        )
        self.assertEqual(failure.operation, "preauth")
        self.assertTrue(failure.replay_safe)

    def test_callback_get_is_not_replayed_like_a_session_read(self):
        callback = self.failure(
            "GET", "https://chatgpt.com/api/auth/callback/openai?code=synthetic",
            error=TimeoutError(),
        )
        session = self.failure(
            "GET", "https://chatgpt.com/api/auth/session", error=TimeoutError(),
        )
        self.assertFalse(callback.replay_safe)
        self.assertTrue(session.replay_safe)

    def test_mailbox_and_static_asset_403_do_not_rotate_registration(self):
        for url in (
            "https://mailbox.example.test/api/otp",
            "https://chatgpt.com/assets/app.js",
            "https://auth.openai.com/api/telemetry",
            "https://auth.openai.com.evil.test/authorize",
        ):
            with self.subTest(url=url):
                self.assertIsNone(self.failure("GET", url, response=SimpleNamespace(status_code=403)))

    def test_429_and_ordinary_business_errors_keep_their_existing_policy(self):
        for status in (200, 400, 401, 409, 429):
            with self.subTest(status=status):
                self.assertIsNone(self.failure(
                    "POST", "https://auth.openai.com/api/accounts/password/verify",
                    response=SimpleNamespace(status_code=status),
                ))

    def test_stage_deadline_and_cancellation_are_not_transport_failures(self):
        from core.auth.state_machine import StageTimeout
        for error in (StageTimeout("步骤预算已用尽"), service.StopRequested("用户停止")):
            with self.subTest(error=type(error).__name__):
                self.assertIsNone(self.failure("GET", "https://chatgpt.com/api/auth/session", error=error))

    def test_browser_network_codes_have_specific_transport_causes(self):
        for code, kind in (
            ("ERR_CONNECTION_TIMED_OUT", "timeout"), ("ERR_NAME_NOT_RESOLVED", "dns"),
            ("ERR_HTTP2_PING_FAILED", "connection"), ("Failed to fetch", "connection"),
            ("ERR_CERT_AUTHORITY_INVALID", "tls"),
        ):
            with self.subTest(code=code):
                failure = self.failure(
                    "GET", "https://chatgpt.com/api/auth/session", error=RuntimeError(code),
                )
                self.assertIsNotNone(failure)
                self.assertEqual(failure.transport_kind, kind)

    def test_recovery_scope_is_removed_after_failure_and_does_not_leak(self):
        from core.registration.route_recovery import (
            current_route_recovery, registration_route_recovery,
        )
        callback = lambda failure, proxy: None
        self.assertIsNone(current_route_recovery())
        with self.assertRaisesRegex(RuntimeError, "测试退出"):
            with registration_route_recovery(callback):
                self.assertIs(current_route_recovery(), callback)
                raise RuntimeError("测试退出")
        self.assertIsNone(current_route_recovery())


class RegistrationRouteCoordinatorTests(TestCase):
    def lease(self, index, **overrides):
        return SimpleNamespace(
            proxy_url=f"http://192.0.2.{index}:8080", exit_ip=f"198.51.100.{index}",
            region="JP", lease_id=f"route-{index}", **overrides,
        )

    def coordinator(self, leases, *, limit=2):
        from core.registration.route_recovery import RegistrationRouteCoordinator
        self.acquired, self.released, self.routes = [], [], []
        iterator = iter(leases[1:])

        def acquire(**kwargs):
            self.acquired.append(kwargs)
            return next(iterator)

        def begin(reason):
            self.routes.append(reason)
            return len(self.routes) + 1

        return RegistrationRouteCoordinator(
            leases[0], limit=limit, delay=0, acquire=acquire,
            release=lambda lease, **kwargs: self.released.append((lease, kwargs)),
            check_stop=lambda: None, begin_route=begin,
        )

    def test_403_uses_new_exit_and_one_budget_across_different_steps(self):
        from core.registration.route_recovery import RegistrationRouteFailure
        leases = [self.lease(i) for i in (1, 2, 3)]
        coordinator = self.coordinator(leases)
        for step, old, new in zip(("preauth", "password_create"), leases, leases[1:]):
            failure = RegistrationRouteFailure(step, http_status=403, response_received=True, replay_safe=True)
            self.assertIs(coordinator(failure, old.proxy_url), new)
        self.assertIsNone(coordinator(failure, leases[-1].proxy_url))
        self.assertEqual(coordinator.used, 2)
        self.assertEqual([r["excluded_exit_ip"] for r in self.acquired], ["198.51.100.1", "198.51.100.2"])
        self.assertTrue(all(not options["fault"] for _, options in self.released))

    def test_stale_request_does_not_spend_current_route_or_budget(self):
        from core.registration.route_recovery import RegistrationRouteFailure
        first, second = self.lease(1), self.lease(2)
        coordinator = self.coordinator([first, second])
        failure = RegistrationRouteFailure("session", transport_kind="timeout", replay_safe=True)
        self.assertIsNone(coordinator(failure, "http://192.0.2.99:8080"))
        self.assertEqual(coordinator.used, 0)
        self.assertEqual(self.acquired, [])
        self.assertEqual(self.released, [])

    def test_same_or_unknown_new_exit_is_released_without_driver_use(self):
        from core.registration.route_recovery import RegistrationRouteFailure
        for ip in ("198.51.100.1", None):
            with self.subTest(exit_ip=ip):
                first, second = self.lease(1), self.lease(2)
                second.exit_ip = ip
                coordinator = self.coordinator([first, second])
                with self.assertRaisesRegex(RuntimeError, "新出口"):
                    coordinator(RegistrationRouteFailure("preauth", transport_kind="proxy", replay_safe=True),
                                first.proxy_url)
                self.assertIsNone(coordinator.lease)
                self.assertEqual(len(self.released), 2)

    def test_cancellation_after_release_stops_before_new_acquisition(self):
        from core.registration.route_recovery import RegistrationRouteFailure
        first, second = self.lease(1), self.lease(2)
        coordinator = self.coordinator([first, second])
        checks = iter((None, RuntimeError("已取消")))

        def check():
            error = next(checks)
            if error:
                raise error

        coordinator.check_stop = check
        with self.assertRaisesRegex(RuntimeError, "已取消"):
            coordinator(RegistrationRouteFailure("session", transport_kind="timeout", replay_safe=True),
                        first.proxy_url)
        self.assertEqual(self.acquired, [])
        self.assertIsNone(coordinator.lease)


class RegistrationRoutePresentationTests(TestCase):
    def test_current_403_is_a_network_problem_while_preserving_original_cause(self):
        from core.operations.errors import classify_task_error
        info = classify_task_error(
            "认证 HTTP 403", task_type="registration", result_summary={
                "cause_code": "protocol_auth_http_failed",
                "route_failure": {
                    "operation": "password_create", "http_status": 403, "transport_kind": "",
                    "response_received": True, "replay_safe": True,
                },
            },
        )
        self.assertEqual(info["source_label"], "网络 / 上游服务")
        self.assertEqual(info["code"], "protocol_auth_http_failed")
        self.assertEqual(info["display_code"], "NET-REG-403")
        self.assertIn("密码创建", info["summary"])

    def test_failed_old_connection_close_has_a_specific_local_cause(self):
        from core.operations.errors import classify_task_error
        from core.registration.errors import _safe_protocol_registration_error
        code = "registration_route_close_failed"
        message = _safe_protocol_registration_error(RuntimeError("private transport detail"), code)
        self.assertIn("旧连接关闭失败", message)
        self.assertNotIn("private transport detail", message)
        info = classify_task_error(message, task_type="registration", result_summary={"cause_code": code})
        self.assertEqual(info["code"], code)
        self.assertEqual(info["display_code"], "FLOW-REG-ROUTE-CLOSE")
