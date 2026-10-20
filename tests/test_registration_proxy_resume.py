"""原身份续跑换线：只动本轮线路，不清除旧提交或回收邮箱。"""
from contextlib import ExitStack, nullcontext
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core import db, operation_task_store, record_store, registration_service as service
from core.registration.browser_submission import unresolved_submission_ids
from core.registration import roxy
from core.storage import registration
from tests.support_pg import PostgresTestCase


class RegistrationProxyResumeTests(PostgresTestCase):
    def setUp(self):
        operation_task_store.reset_ready()
        operation_task_store.init()
        registration.reset_ready()
        registration.init()

    def seed_resume(self):
        address = "held+abc123@example.test"
        password = "OriginalSavedPassword123!"
        root_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "route-resume-root", "email": address,
            "email_source": "icloud_hide", "status": "running", "job_type": "registration",
            "data": {"config_snapshot": {"registration_driver": "roxy", "proxy_country": "US"}},
        })
        attempt = registration.ensure_attempt_for_job(root_id)
        original = registration.start_run(
            attempt["id"], job_id=root_id, execution_id="original-route-run", initial_status="running",
        )
        registration.save_password_checkpoint(
            attempt["id"], email=address, password=password, state="started",
            run_id=original["id"], execution_id="original-route-run", job_id=root_id,
        )
        registration.record_submission_fact(
            attempt["id"], submission_id="original-unknown-profile", kind="profile",
            stage="profile", phase="unknown", endpoint_kind="account_create", http_method="POST",
            run_id=original["id"], execution_id="original-route-run",
        )
        registration.advance_checkpoint(attempt["id"], "account_request_started", target_status="request_unknown")
        registration.finish_run(original["id"], status="failed")
        db.update_job(root_id, status="failed", error="request_unknown")
        child_id = record_store.insert_row(record_store.JOBS, {
            "job_uuid": "route-resume-child", "email": address,
            "email_source": "icloud_hide", "status": "pending", "job_type": "registration_resume",
            "parent_job_id": root_id, "root_job_id": root_id, "attempt_id": attempt["id"],
            "data": {"config_snapshot": {"registration_driver": "roxy", "proxy_country": "US"}},
        })
        return address, password, attempt["id"], root_id, child_id

    @staticmethod
    def lease(index):
        return SimpleNamespace(
            lease_id=f"offline-lease-{index}", provider="711proxy",
            endpoint=f"192.0.2.{index}:8080", exit_ip=f"198.51.100.{index}", region="US",
            acquired_at=datetime.now(timezone.utc), expires_at=None,
            proxy_url=f"http://192.0.2.{index}:8080", metadata={},
        )

    def run_resume(self, results):
        address, password, attempt_id, root_id, child_id = self.seed_resume()
        contexts, calls = [], []
        leases = [self.lease(index + 1) for index in range(len(results))]
        remaining = iter(results)

        def register(**kwargs):
            calls.append(kwargs)
            context = service.registration_fact_context()
            contexts.append(context)
            rotation = kwargs["registration_options"]["_resume_proxy_rotation"]
            self.assertEqual(roxy._validated_resume_proxy_rotation(
                kwargs["registration_options"], context, kwargs.get("profile_id"),
            ), rotation)
            self.assertEqual(rotation["retry_available"], len(calls) == 1)
            if len(calls) > 1:
                self.assertEqual(rotation["reopen_profile_id"], "held-profile")
                self.assertEqual(kwargs["profile_id"], "held-profile")
            return {"success": False, "email": address, **next(remaining)}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=1))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_delay", return_value=0))
            acquire = stack.enter_context(patch("core.proxy_provider.acquire_registration_proxy", side_effect=leases))
            release = stack.enter_context(patch("core.proxy_provider.release_proxy"))
            stack.enter_context(patch("core.registration.dispatcher.run_registration", side_effect=register))
            stack.enter_context(patch("core.registration_debug.capture_current_failure"))
            release_email = stack.enter_context(patch("core.email_provider.release_email"))
            stack.enter_context(patch("core.email_provider.retain_email"))
            unconsumed = stack.enter_context(patch.object(service, "_release_unconsumed_job_email"))
            prepare = stack.enter_context(patch.object(service, "_prepare_registration_args"))
            service._run_one_job(child_id, "/tmp/offline-resume-route.log")
        self.assertEqual(len(calls), len(results))
        for call, context in zip(calls, contexts):
            self.assertEqual(call["email"], address)
            self.assertEqual(call["existing_password"], password)
            self.assertEqual(context["attempt_id"], attempt_id)
            self.assertEqual(context["job_id"], child_id)
        self.assertEqual(len({x["run_id"] for x in contexts}), 1)
        self.assertEqual(db.get_job(child_id)["attempt_id"], attempt_id)
        self.assertEqual(db.get_job(child_id)["root_job_id"], root_id)
        self.assertNotIn("_resume_proxy_rotation", str(db.get_job(child_id).get("data")))
        private = registration.get_private_resume_context(attempt_id, email=address)
        self.assertEqual(private["password"], password)
        self.assertIn("original-unknown-profile", unresolved_submission_ids(private["submission_facts"]))
        self.assertEqual(registration.get_attempt(attempt_id)["target_status"], "request_unknown")
        prepare.assert_not_called()
        release_email.assert_not_called()
        unconsumed.assert_not_called()
        return acquire, release, leases, db.get_job(child_id)

    def test_resume_initial_get_failure_rotates_current_lease_and_retains_identity(self):
        acquire, release, leases, job = self.run_resume([
            {"proxy_transport_failure": True, "current_lease_route_verified": True,
             "resume_login_get_transport_failure": True, "request_unknown": False,
             "resume_proxy_rotation_ready": True, "resume_proxy_rotation_profile_id": "held-profile",
             "error": "net::ERR_TUNNEL_CONNECTION_FAILED"},
            {"request_unknown": True, "error": "profile_confirmation_unknown"},
        ])
        self.assertEqual(acquire.call_count, 2)
        self.assertEqual([x.kwargs["country"] for x in acquire.call_args_list], ["US", "US"])
        release.assert_any_call(leases[0], reason="registration_proxy_retry_1", fault=True)
        release.assert_any_call(leases[1], reason="failed")
        self.assertEqual(job["route_attempt_no"], 2)
        self.assertEqual(job["status"], "failed")

    def test_post_submit_transport_failure_faults_route_without_replaying_unknown_post(self):
        acquire, release, leases, _job = self.run_resume([
            {"proxy_transport_failure": True, "current_lease_route_verified": True,
             "resume_login_get_transport_failure": False, "request_unknown": True,
             "error": "net::ERR_CONNECTION_RESET"},
        ])
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="transport_failure", fault=True)

    def test_resume_rotation_is_bounded_and_last_bad_route_is_faulted(self):
        failure = {"proxy_transport_failure": True, "current_lease_route_verified": True,
                   "resume_login_get_transport_failure": True, "request_unknown": False,
                   "resume_proxy_rotation_ready": True, "resume_proxy_rotation_profile_id": "held-profile",
                   "error": "net::ERR_PROXY_CONNECTION_FAILED"}
        acquire, release, leases, job = self.run_resume([failure, failure])
        self.assertEqual(acquire.call_count, 2)
        self.assertEqual(release.call_count, 2)
        release.assert_any_call(leases[0], reason="registration_proxy_retry_1", fault=True)
        release.assert_any_call(leases[1], reason="transport_failure", fault=True)
        self.assertEqual(job["status"], "failed")

    def test_retained_route_failure_does_not_fault_the_unused_current_lease(self):
        acquire, release, leases, _job = self.run_resume([
            {"proxy_transport_failure": True, "current_lease_route_verified": False,
             "resume_login_get_transport_failure": False, "request_unknown": True,
             "error": "net::ERR_PROXY_CONNECTION_FAILED"},
        ])
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="failed")

    def test_unconfirmed_window_close_never_allocates_another_lease(self):
        acquire, release, leases, _job = self.run_resume([
            {"proxy_transport_failure": True, "current_lease_route_verified": True,
             "resume_login_get_transport_failure": True, "resume_proxy_rotation_ready": False,
             "request_unknown": False, "error": "net::ERR_TUNNEL_CONNECTION_FAILED"},
        ])
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="transport_failure", fault=True)

    def assert_terminal_without_proxy_fault(self, error):
        acquire, release, leases, _job = self.run_resume([{"request_unknown": True, "error": error}])
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="failed")

    def test_http_400_does_not_fault_or_rotate(self):
        self.assert_terminal_without_proxy_fault("HTTP 400")

    def test_http_403_does_not_fault_or_rotate(self):
        self.assert_terminal_without_proxy_fault("HTTP 403")

    def test_budget_timeout_does_not_fault_or_rotate(self):
        self.assert_terminal_without_proxy_fault("StageTimeout: budget exhausted")

    def test_empty_auth_shell_does_not_fault_or_rotate(self):
        self.assert_terminal_without_proxy_fault("empty auth shell")
