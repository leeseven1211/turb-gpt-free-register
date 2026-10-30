"""本地Roxy仅凭当前Run的强证据许可，有限换线并保留原身份。"""
from contextlib import ExitStack, nullcontext
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from core import db, operation_task_store
from core.storage import records as record_store
from core.registration import service as service
from core.auth.browser.browser_submission import unresolved_submission_ids
from core.registration import roxy
from core.storage import registration
from tests.support_pg import PostgresTestCase
from tests.registration import test_registration_proxy_resume as resume_fixture


ADDRESS = "held+abc123@example.test"
FACTS = {"job_id": 11, "attempt_id": 12, "run_id": 13, "execution_id": "current-run"}


def cf_result(*, profile_id="", context=None, **extra):
    return {
        "success": False, "email": ADDRESS, "request_unknown": True,
        "registration_checkpoint": "account_request_started",
        "cf_proxy_rotation_ready": True, "cf_proxy_rotation_profile_id": profile_id,
        "current_lease_route_verified": True, "cause_code": "auth_cloudflare_challenge",
        "cause_diagnostics": {"http_status": 403, "auth_endpoint": "nextauth_signin",
                              "response_kind": "cloudflare_challenge"},
        "cf_proxy_rotation_context": dict(FACTS if context is None else context),
        **extra,
    }


class CloudflareRotationPermissionTests(TestCase):
    def job(self, driver="roxy", job_type="registration_resume"):
        return {"id": 11, "job_type": job_type, "email": ADDRESS,
                "config_snapshot": {"registration_driver": driver}}

    def accepted(self, result, job=None, context=None):
        return service._confirmed_registration_cf_proxy_rotation(
            result, self.job() if job is None else job, email=ADDRESS,
            fact_context=FACTS if context is None else context,
        )

    def test_current_signin_and_csrf_permission_accepts_historical_unknown_checkpoint(self):
        for endpoint in ("nextauth_signin", "nextauth_csrf"):
            with self.subTest(endpoint=endpoint):
                result = cf_result(profile_id="bound-profile", account_id=40)
                result["cause_diagnostics"]["auth_endpoint"] = endpoint
                before = deepcopy(result)
                self.assertTrue(self.accepted(result))
                self.assertEqual(result, before)

    def test_registration_with_closed_disposable_profile_allows_empty_reopen_id(self):
        self.assertTrue(self.accepted(cf_result(), self.job(job_type="registration")))

    def test_current_challenge_without_reopen_permission_still_marks_route_fault(self):
        result = cf_result(cf_proxy_rotation_ready=False)
        result.pop("cf_proxy_rotation_profile_id")
        self.assertTrue(service._confirmed_registration_cf_proxy_failure(
            result, self.job(), email=ADDRESS, fact_context=FACTS,
        ))
        self.assertFalse(self.accepted(result))
        result["cf_proxy_rotation_context"]["run_id"] = 999
        self.assertFalse(service._confirmed_registration_cf_proxy_failure(
            result, self.job(), email=ADDRESS, fact_context=FACTS,
        ))

    def test_rejects_weak_stale_foreign_and_persisted_results(self):
        cases = []
        for key, value in (("cf_proxy_rotation_ready", 1), ("current_lease_route_verified", False),
                           ("cf_proxy_rotation_profile_id", None), ("cause_code", "HTTP 403"),
                           ("success", True), ("access_token", "saved-test-token"), ("core_persisted", True),
                           ("registration_checkpoint", "core_persisted"), ("email", "other@example.test")):
            cases.append((key, cf_result(**{key: value}), self.job(), FACTS))
        for field, value in (("http_status", "403"), ("http_status", 400),
                             ("auth_endpoint", "telemetry"), ("auth_endpoint", "password"),
                             ("response_kind", "http_error")):
            result = cf_result()
            result["cause_diagnostics"][field] = value
            cases.append((field, result, self.job(), FACTS))
        for key in FACTS:
            result = cf_result()
            result["cf_proxy_rotation_context"][key] = "stale"
            cases.append(("stale_" + key, result, self.job(), FACTS))
        cases += [("other_driver", cf_result(), self.job("roxy_oss"), FACTS),
                  ("job_email_mismatch", cf_result(), {**self.job(), "email": "other@example.test"}, FACTS),
                  ("no_snapshot", cf_result(), {"id": 11, "job_type": "registration"}, FACTS),
                  ("other_job", cf_result(), self.job(job_type="codex_retry"), FACTS),
                  ("context_absent", cf_result(), self.job(), {**FACTS, "attempt_id": None}),
                  ("only_error_text", {"email": ADDRESS, "error": "HTTP 403 cf-mitigated=challenge"}, self.job(), FACTS)]
        for name, result, job, context in cases:
            with self.subTest(name=name):
                self.assertFalse(self.accepted(result, job, context))

    def test_only_full_original_email_matches_and_hash_cannot_replace_it(self):
        result = cf_result(email_sha256="irrelevant-hash")
        result.pop("email")
        self.assertFalse(self.accepted(result))
        result["email"] = "other@example.test"
        self.assertFalse(self.accepted(result))
        self.assertTrue(self.accepted(cf_result(email=" HELD+ABC123@EXAMPLE.TEST ")))


class CloudflareWorkerRotationTests(PostgresTestCase):
    def setUp(self):
        operation_task_store.reset_ready()
        operation_task_store.init()
        registration.reset_ready()
        registration.init()

    def run_worker(self, *, profile_id="", repeated_ip=False, missing_ip=False, initial_missing_ip=False,
                   limit=1, with_account=False):
        address, password, attempt_id, root_id, child_id = resume_fixture.RegistrationProxyResumeTests.seed_resume(self)
        account_id = None
        if with_account:
            account_id = record_store.insert_row(record_store.ACCOUNTS, {
                "email": address, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
                "email_source": "icloud_hide", "registration_proxy_provider": "original-provider",
                "registration_proxy_region": "CA",
                "extra_json": {"registration_checkpoint": "email_verification_pending", "account_password": password},
            })
            db.update_job(child_id, account_id=account_id)
        calls, contexts = [], []
        leases = [resume_fixture.RegistrationProxyResumeTests.lease(1), resume_fixture.RegistrationProxyResumeTests.lease(2)]
        if repeated_ip:
            leases[1].exit_ip = leases[0].exit_ip
        if missing_ip:
            leases[1].exit_ip = None
        if initial_missing_ip:
            leases[0].exit_ip = None

        def driver(**kwargs):
            calls.append(kwargs)
            contexts.append(service.registration_fact_context())
            options = kwargs["registration_options"].get("_roxy_cf_proxy_rotation")
            self.assertIsInstance(options, dict)
            self.assertEqual({key: options[key] for key in FACTS}, contexts[-1])
            self.assertIs(options["retry_available"], len(calls) <= limit)
            self.assertEqual(options["reopen_profile_id"], profile_id if len(calls) > 1 else "")
            self.assertIs(options["previous_cf_temporary_profile_deleted"], len(calls) > 1 and not profile_id)
            self.assertEqual(kwargs["profile_id"], profile_id or None)
            return cf_result(profile_id=profile_id, context=contexts[-1],
                             cf_proxy_rotation_ready=len(calls) <= limit,
                             **({"account_id": account_id} if account_id is not None else {}))

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=limit))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_delay", return_value=0))
            stack.enter_context(patch("core.browser.roxy.profile_binding.account_profile_id", return_value=profile_id or None))
            acquire = stack.enter_context(patch("core.proxy.provider.acquire_registration_proxy", side_effect=leases))
            release = stack.enter_context(patch("core.proxy.provider.release_proxy"))
            stack.enter_context(patch("core.registration.dispatcher.run_registration", side_effect=driver))
            stack.enter_context(patch("core.registration.debug.capture_current_failure"))
            release_email = stack.enter_context(patch("core.email.provider.release_email"))
            stack.enter_context(patch("core.email.provider.retain_email"))
            prepare = stack.enter_context(patch.object(service, "_prepare_registration_args"))
            service._run_one_job(child_id, "/tmp/offline-cf-service.log")
        self.assertEqual(len(calls), 1 if repeated_ip or missing_ip or initial_missing_ip or limit == 0 else 2)
        for call, context in zip(calls, contexts):
            self.assertEqual(call["email"], address)
            self.assertEqual(call["existing_password"], password)
            self.assertEqual(context["job_id"], child_id)
            self.assertEqual(context["attempt_id"], attempt_id)
        self.assertEqual(len({context["run_id"] for context in contexts}), 1)
        self.assertEqual(len({context["execution_id"] for context in contexts}), 1)
        private = registration.get_private_resume_context(attempt_id, email=address)
        self.assertEqual(private["password"], password)
        self.assertIn("original-unknown-profile", unresolved_submission_ids(private["submission_facts"]))
        self.assertEqual(registration.get_attempt(attempt_id)["target_status"], "request_unknown")
        self.assertNotIn("_roxy_cf_proxy_rotation", str(db.get_job(child_id).get("data")))
        release_email.assert_not_called()
        prepare.assert_not_called()
        if account_id is not None and (repeated_ip or missing_ip or initial_missing_ip):
            self.assertEqual(db.get_account(account_id)["registration_proxy_provider"], "original-provider")
            self.assertEqual(db.get_account(account_id)["registration_proxy_region"], "CA")
        return acquire, release, leases, db.get_job(child_id)

    def test_resume_challenge_quarantines_both_routes_and_keeps_bound_profile(self):
        acquire, release, leases, job = self.run_worker(profile_id="bound-profile")
        self.assertEqual(acquire.call_count, 2)
        release.assert_any_call(leases[0], reason="auth_cloudflare_challenge", fault=True)
        release.assert_any_call(leases[1], reason="auth_cloudflare_challenge", fault=True)
        self.assertEqual(job["route_attempt_no"], 2)

    def test_closed_disposable_profile_rotates_without_reusing_profile(self):
        acquire, _release, _leases, _job = self.run_worker()
        self.assertEqual(acquire.call_count, 2)

    def test_exhausted_limit_quarantines_without_acquiring_extra_proxy(self):
        acquire, release, leases, _job = self.run_worker(limit=0)
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="auth_cloudflare_challenge", fault=True)

    def test_repeated_exit_ip_is_not_replayed_or_reacquired(self):
        acquire, release, leases, job = self.run_worker(repeated_ip=True, with_account=True)
        self.assertEqual(acquire.call_count, 2)
        release.assert_any_call(leases[1], reason="auth_cloudflare_challenge", fault=True)
        self.assertIn("cf_proxy_new_ip_unverified", job["error_message"])
        self.assertEqual(job["proxy_status"], "released")

    def test_missing_exit_ip_is_not_replayed_or_reacquired(self):
        acquire, release, leases, job = self.run_worker(missing_ip=True, with_account=True)
        self.assertEqual(acquire.call_count, 2)
        release.assert_any_call(leases[1], reason="auth_cloudflare_challenge", fault=True)
        self.assertIn("cf_proxy_new_ip_unverified", job["error_message"])
        self.assertEqual(job["proxy_status"], "released")

    def test_unknown_initial_exit_ip_stops_before_acquiring_an_unverifiable_replacement(self):
        acquire, release, leases, job = self.run_worker(initial_missing_ip=True)
        self.assertEqual(acquire.call_count, 1)
        release.assert_called_once_with(leases[0], reason="auth_cloudflare_challenge", fault=True)
        self.assertIn("cf_proxy_new_ip_unverified", job["error_message"])
        self.assertEqual(job["proxy_status"], "released")

    def run_mixed_rotations(self, sequence, *, repeated_after_transport=False, missing_after_transport=False):
        address, password, attempt_id, _root_id, child_id = resume_fixture.RegistrationProxyResumeTests.seed_resume(self)
        calls, contexts = [], []
        leases = [resume_fixture.RegistrationProxyResumeTests.lease(index + 1) for index in range(3)]
        if repeated_after_transport:
            leases[2].exit_ip = leases[0].exit_ip
        if missing_after_transport:
            leases[2].exit_ip = None
        unverified_after_transport = repeated_after_transport or missing_after_transport

        def driver(**kwargs):
            calls.append(kwargs)
            context = service.registration_fact_context()
            contexts.append(context)
            options = kwargs["registration_options"]
            cf = options["_roxy_cf_proxy_rotation"]
            transport = options["_resume_proxy_rotation"]
            self.assertEqual(roxy._validated_roxy_cf_proxy_rotation(options, context, kwargs["profile_id"]), cf)
            self.assertEqual(roxy._validated_resume_proxy_rotation(options, context, kwargs["profile_id"]), transport)
            if len(calls) == 1:
                self.assertEqual(kwargs["profile_id"], None)
            elif sequence[len(calls) - 2] == "cf":
                self.assertEqual(transport["reopen_profile_id"], "")
                expected_profile = "transport-profile" if len(calls) == 3 else ""
                self.assertEqual(cf["reopen_profile_id"], expected_profile)
                self.assertIs(cf["previous_cf_temporary_profile_deleted"], not bool(expected_profile))
                self.assertEqual(kwargs["profile_id"], expected_profile or None)
            else:
                self.assertEqual(transport["reopen_profile_id"], "transport-profile")
                self.assertEqual(cf["reopen_profile_id"], "")
                self.assertIs(cf["previous_cf_temporary_profile_deleted"], False)
                self.assertEqual(kwargs["profile_id"], "transport-profile")
            if len(calls) == 3:
                return {"success": False, "email": address, "request_unknown": True, "error": "profile_confirmation_unknown"}
            if sequence[len(calls) - 1] == "cf":
                # 无账号绑定时，只有首轮临时环境可删除；transport重开环境保留原ID。
                return cf_result(profile_id=kwargs["profile_id"] or "", context=context)
            return {"success": False, "email": address, "proxy_transport_failure": True,
                    "current_lease_route_verified": True, "resume_login_get_transport_failure": True,
                    "resume_proxy_rotation_ready": True, "resume_proxy_rotation_profile_id": "transport-profile",
                    "error": "net::ERR_TUNNEL_CONNECTION_FAILED"}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "_JobLogContext", return_value=nullcontext()))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_limit", return_value=2))
            stack.enter_context(patch.object(service, "_registration_proxy_retry_delay", return_value=0))
            stack.enter_context(patch("core.browser.roxy.profile_binding.account_profile_id", return_value=None))
            acquire = stack.enter_context(patch("core.proxy.provider.acquire_registration_proxy", side_effect=leases))
            release = stack.enter_context(patch("core.proxy.provider.release_proxy"))
            stack.enter_context(patch("core.registration.dispatcher.run_registration", side_effect=driver))
            stack.enter_context(patch("core.registration.debug.capture_current_failure"))
            stack.enter_context(patch("core.email.provider.retain_email"))
            release_email = stack.enter_context(patch("core.email.provider.release_email"))
            service._run_one_job(child_id, "/tmp/offline-mixed-cf-service.log")
        self.assertEqual(acquire.call_count, 3)
        self.assertEqual(len(calls), 2 if unverified_after_transport else 3)
        self.assertEqual({context["attempt_id"] for context in contexts}, {attempt_id})
        self.assertEqual(len({context["run_id"] for context in contexts}), 1)
        for call in calls:
            self.assertEqual(call["email"], address)
            self.assertEqual(call["existing_password"], password)
        expected_error = "cf_proxy_new_ip_unverified" if unverified_after_transport else "profile_confirmation_unknown"
        self.assertIn(expected_error, db.get_job(child_id)["error_message"])
        if unverified_after_transport:
            release.assert_any_call(leases[2], reason="auth_cloudflare_challenge", fault=True)
        private = registration.get_private_resume_context(attempt_id, email=address)
        self.assertIn("original-unknown-profile", unresolved_submission_ids(private["submission_facts"]))
        self.assertEqual(registration.get_attempt(attempt_id)["target_status"], "request_unknown")
        release_email.assert_not_called()

    def test_cf_then_transport_clears_deleted_temporary_profile_marker(self):
        self.run_mixed_rotations(("cf", "transport"))

    def test_transport_then_cf_clears_previous_transport_reopen_marker(self):
        self.run_mixed_rotations(("transport", "cf"))

    def test_later_transport_rotation_cannot_return_to_previously_challenged_exit_ip(self):
        self.run_mixed_rotations(("cf", "transport"), repeated_after_transport=True)

    def test_later_transport_rotation_still_requires_a_verifiable_exit_ip(self):
        self.run_mixed_rotations(("cf", "transport"), missing_after_transport=True)
