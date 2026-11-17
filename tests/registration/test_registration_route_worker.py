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

    def run_worker(self, *, mixed=False):
        email, password, attempt_id, _, job_id = resume_fixture.RegistrationProxyResumeTests.seed_resume(self)
        leases = [resume_fixture.RegistrationProxyResumeTests.lease(i) for i in (1, 2, 3)]
        observations = []

        def driver(**kwargs):
            callback = current_route_recovery()
            before = service.registration_fact_context()
            current = current_correlation()
            observations.append((before, current))
            new = callback(
                RegistrationRouteFailure("preauth", http_status=403, response_received=True, replay_safe=True),
                kwargs["proxy"],
            )
            self.assertIs(new, leases[1])
            observations.append((service.registration_fact_context(), current_correlation()))
            last_failure = RegistrationRouteFailure("session", transport_kind="timeout", replay_safe=True)
            self.assertIsNone(callback(last_failure, new.proxy_url))
            return {
                "success": False, "email": email, "request_unknown": True,
                "error": "已用完本次线路额度", "route_failure": asdict(last_failure),
            }

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=1))
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
        self.assertFalse(release.call_args_list[0].kwargs["fault"])
        self.assertTrue(release.call_args_list[1].kwargs["fault"])

    def test_protocol_callback_rotates_once_and_preserves_the_same_run(self):
        self.run_worker()
