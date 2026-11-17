"""真实注册 worker 的同 Run 换线、预算和流量归属集成。"""
from contextlib import ExitStack, nullcontext
from dataclasses import asdict
from unittest.mock import patch

from core import db, operation_task_store
from core.network.protocol_traffic import current_correlation
from core.registration import admission, service
from core.registration.route_recovery import (
    RegistrationRouteFailure, current_route_recovery,
)
from core.storage import registration
from tests.registration import test_registration_proxy_resume as resume_fixture
from tests.support_pg import PostgresTestCase


class RegistrationRouteWorkerTests(PostgresTestCase):
    def setUp(self):
        operation_task_store.reset_ready()
        operation_task_store.init()
        registration.reset_ready()
        registration.init()

    def run_worker(self, *, terminal_blocked=False, terminal_request_unknown=True):
        email, password, attempt_id, _, job_id = resume_fixture.RegistrationProxyResumeTests.seed_resume(self)
        leases = [resume_fixture.RegistrationProxyResumeTests.lease(i) for i in (1, 2, 3)]
        observations = []
        current_diagnostics = {
            "operation": "other", "failure_kind": "transport_error",
            "exception_type": "TimeoutError", "exception_chain": ["TimeoutError"],
            "request_method": "GET", "request_host_class": "auth", "request_path_class": "unmapped",
        }
        old_audit = [{
            "route_failure": {
                "operation": "preauth", "http_status": None, "transport_kind": "proxy",
                "response_received": False, "replay_safe": True,
            },
        }]

        def driver(**kwargs):
            callback = current_route_recovery()
            before = service.registration_fact_context()
            current = current_correlation()
            observations.append((before, current))
            first_failure = (
                RegistrationRouteFailure("preauth", transport_kind="proxy", replay_safe=True)
                if terminal_blocked else
                RegistrationRouteFailure("preauth", http_status=403, response_received=True, replay_safe=True)
            )
            new = callback(first_failure, kwargs["proxy"])
            self.assertIs(new, leases[1])
            observations.append((service.registration_fact_context(), current_correlation()))
            if terminal_blocked:
                return {
                    "success": False, "email": email, "request_unknown": terminal_request_unknown,
                    "route_recovery_blocked": True, "route_failure": asdict(first_failure),
                    "cause_code": ("registration_profile_submission_unresolved" if terminal_request_unknown
                                   else "protocol_unmapped_request_transport_failed"),
                    "error": ("原资料提交结果未知，保留原提交且不重复创建" if terminal_request_unknown
                              else "当前可信认证请求尚未分类，连接超时"),
                    **({} if terminal_request_unknown else {
                        "registration_diagnostics": current_diagnostics,
                        "registration_recovery_audit": old_audit,
                    }),
                }
            last_failure = RegistrationRouteFailure("session", transport_kind="timeout", replay_safe=True)
            self.assertIsNone(callback(last_failure, new.proxy_url))
            return {
                "success": False, "email": email, "request_unknown": True,
                "error": "已用完本次线路额度", "route_failure": asdict(last_failure),
            }

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(
                service, "_registration_proxy_retry_limit", return_value=3 if terminal_blocked else 1,
            ))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_delay", return_value=0))
            stack.enter_context(patch("core.browser.roxy.profile_binding.account_profile_id", return_value=None))
            acquire = stack.enter_context(patch("core.proxy.provider.acquire_registration_proxy", side_effect=leases))
            release = stack.enter_context(patch("core.proxy.provider.release_proxy"))
            stack.enter_context(patch("core.registration.dispatcher.run_registration", side_effect=driver))
            stack.enter_context(patch("core.registration.debug.capture_current_failure"))
            stack.enter_context(patch("core.email.provider.retain_email"))
            admission.run_job(job_id, lambda: service._run_one_job(job_id, "/tmp/offline-route-worker.log"))
        self.assertEqual(len(observations), 2)
        self.assertEqual(observations[0][0]["run_id"], observations[1][0]["run_id"])
        self.assertEqual(observations[0][1]["route_attempt_no"], 1)
        self.assertEqual(observations[1][1]["route_attempt_no"], 2)
        self.assertEqual(observations[1][1]["proxy_lease_id"], leases[1].lease_id)
        self.assertEqual(acquire.call_count, 2)
        self.assertEqual(acquire.call_args.kwargs["excluded_exit_ip"], leases[0].exit_ip)
        self.assertEqual(acquire.call_args.kwargs["country"], "US")
        self.assertEqual(db.get_job(job_id)["route_attempt_no"], 2)
        private = registration.get_private_resume_context(attempt_id, email=email)
        self.assertEqual(private["password"], password)
        self.assertEqual(current_correlation(), {})
        self.assertIsNone(current_route_recovery())
        self.assertEqual(len(release.call_args_list), 2)
        self.assertIs(release.call_args_list[0].args[0], leases[0])
        self.assertIs(release.call_args_list[1].args[0], leases[1])
        self.assertEqual(release.call_args_list[0].kwargs["fault"], terminal_blocked)
        self.assertEqual(release.call_args_list[1].kwargs.get("fault", False), not terminal_blocked)
        if terminal_blocked:
            summary = registration.get_run(observations[0][0]["run_id"])["result_summary"]
            self.assertNotIn("route_failure", summary)
            if terminal_request_unknown:
                self.assertEqual(summary["cause_code"], "registration_profile_submission_unresolved")
                self.assertEqual(summary["outcome"], "request_unknown")
            else:
                self.assertEqual(summary["cause_code"], "protocol_unmapped_request_transport_failed")
                self.assertEqual(summary.get("registration_diagnostics"), current_diagnostics)
                self.assertIs(summary.get("route_recovery_blocked"), True)
                self.assertEqual(summary.get("registration_recovery_audit"), old_audit)
                self.assertNotIn("outcome", summary)

    def test_protocol_callback_rotates_once_and_preserves_the_same_run(self):
        self.run_worker()

    def test_terminal_after_rotation_does_not_quarantine_new_lease_or_persist_old_failure(self):
        self.run_worker(terminal_blocked=True)

    def test_nonunknown_failure_persists_current_diagnostics_and_old_audit_separately(self):
        self.run_worker(terminal_blocked=True, terminal_request_unknown=False)
