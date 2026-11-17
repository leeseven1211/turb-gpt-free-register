"""同 Run 换线只授权原身份登录，保留原始未决写入事实。"""
from unittest.mock import patch

from core.storage import registration
from core.auth.browser.browser_submission import unresolved_submission_ids
from tests.support_pg import PostgresTestCase


class RegistrationRouteResumeStorageTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.email = "route-recovery@example.test"
        self.attempt = registration.create_attempt(self.email)
        self.run = registration.start_run(
            self.attempt["id"], execution_id="route-execution",
            initial_status="running", action_type="registration",
        )
        self.facts = {"run_id": self.run["id"], "execution_id": "route-execution"}
        registration.save_password_checkpoint(
            self.attempt["id"], email=self.email, password="SyntheticCandidate123!",
            state="started", **self.facts,
        )
        registration.record_submission_fact(
            self.attempt["id"], submission_id="unknown-create", kind="profile",
            stage="profile", phase="unknown", endpoint_kind="profile_submit",
            http_method="POST", **self.facts,
        )

    def dispatch(self, *, kind="resume_login", stage="submit_email", endpoint="email_submit"):
        return registration.record_submission_fact(
            self.attempt["id"], submission_id="new-login", kind=kind,
            stage=stage, phase="dispatch_intent", endpoint_kind=endpoint,
            http_method="POST", **self.facts,
        )

    def authorize(self, **overrides):
        kwargs = {
            "email": self.email, **self.facts,
            "previous_route_no": 1, "route_attempt_no": 2,
        }
        return registration.authorize_route_resume(self.attempt["id"], **{**kwargs, **overrides})

    def test_same_run_original_login_requires_narrow_route_authorization(self):
        with self.assertRaisesRegex(ValueError, "registration_resume"):
            self.dispatch()
        self.authorize()
        self.dispatch()
        private = registration.get_private_resume_context(self.attempt["id"], email=self.email)
        self.assertIn("unknown-create", unresolved_submission_ids(private["submission_facts"]))
        self.assertEqual(registration.get_run(self.run["id"])["action_type"], "registration")

    def test_authorization_does_not_allow_password_or_profile_creation(self):
        self.authorize()
        for kind, stage, endpoint in (
            ("password", "password_create", "password_submit"),
            ("profile", "profile", "profile_submit"),
            ("resume_login", "password_create", "password_submit"),
        ):
            with self.subTest(kind=kind, stage=stage):
                with self.assertRaises(ValueError):
                    self.dispatch(kind=kind, stage=stage, endpoint=endpoint)

    def test_foreign_execution_email_or_nonadvancing_route_is_rejected(self):
        for values in (
            {"execution_id": "old-execution"},
            {"email": "other@example.test"},
            {"route_attempt_no": 1},
            {"route_attempt_no": True},
        ):
            with self.subTest(values=values):
                with self.assertRaises((ValueError, RuntimeError)):
                    self.authorize(**values)

    def test_new_run_does_not_inherit_old_route_authorization(self):
        self.authorize()
        registration.finish_run(self.run["id"], status="failed")
        new = registration.start_run(
            self.attempt["id"], execution_id="new-execution",
            initial_status="running", action_type="registration",
        )
        self.facts = {"run_id": new["id"], "execution_id": "new-execution"}
        with self.assertRaisesRegex(ValueError, "registration_resume"):
            self.dispatch()

    def test_preauth_without_candidate_only_allows_a_new_email_action(self):
        other = registration.create_attempt("preauth-route@example.test")
        run = registration.start_run(
            other["id"], execution_id="preauth-route", initial_status="running",
        )
        facts = {"run_id": run["id"], "execution_id": "preauth-route"}
        registration.record_submission_fact(
            other["id"], submission_id="old-signin", kind="email", stage="nextauth",
            phase="unknown", endpoint_kind="nextauth_signin", http_method="POST", **facts,
        )
        self.assertTrue(registration.authorize_route_resume(
            other["id"], email="preauth-route@example.test", previous_route_no=1,
            route_attempt_no=2, **facts,
        ))
        registration.record_submission_fact(
            other["id"], submission_id="new-email", kind="email", stage="submit_email",
            phase="dispatch_intent", endpoint_kind="email_submit", http_method="POST", **facts,
        )
        with self.assertRaises(ValueError):
            registration.record_submission_fact(
                other["id"], submission_id="new-password", kind="password", stage="password_create",
                phase="dispatch_intent", endpoint_kind="password_submit", http_method="POST", **facts,
            )
        registration.record_submission_fact(
            other["id"], submission_id="new-email", kind="email", stage="submit_email",
            phase="confirmed", endpoint_kind="email_submit", http_method="POST", result="success", **facts,
        )
        registration.save_password_checkpoint(
            other["id"], email="preauth-route@example.test", password="SyntheticFirstCandidate123!",
            state="prepared", **facts,
        )
        registration.record_submission_fact(
            other["id"], submission_id="new-password", kind="password", stage="password_create",
            phase="prepared", endpoint_kind="password_submit", http_method="POST", **facts,
        )
        registration.record_submission_fact(
            other["id"], submission_id="new-password", kind="password", stage="password_create",
            phase="dispatch_intent", endpoint_kind="password_submit", http_method="POST", **facts,
        )
        private = registration.get_private_resume_context(other["id"], email="preauth-route@example.test")
        self.assertIn("old-signin", unresolved_submission_ids(private["submission_facts"]))
        self.assertTrue(private["route_resume_authorization"]["candidate_digest"])
        registration.record_submission_fact(
            other["id"], submission_id="new-password", kind="password", stage="password_create",
            phase="confirmed", endpoint_kind="password_submit", http_method="POST", result="success", **facts,
        )
        decode = registration._decode

        def changed_candidate(value):
            result = decode(value)
            if isinstance(result, dict) and result.get("password") == "SyntheticFirstCandidate123!":
                return {**result, "password": "DifferentSyntheticCandidate123!"}
            return result

        with patch.object(registration, "_decode", side_effect=changed_candidate):
            with self.assertRaisesRegex(ValueError, "未决"):
                registration.record_submission_fact(
                    other["id"], submission_id="new-otp", kind="otp", stage="email_otp",
                    phase="dispatch_intent", endpoint_kind="otp_submit", http_method="POST", **facts,
                )
        registration.record_submission_fact(
            other["id"], submission_id="new-otp", kind="otp", stage="email_otp",
            phase="dispatch_intent", endpoint_kind="otp_submit", http_method="POST", **facts,
        )

    def test_one_route_authorization_cannot_bypass_new_unknown_login(self):
        self.authorize()
        self.dispatch()
        registration.record_submission_fact(
            self.attempt["id"], submission_id="new-login", kind="resume_login", stage="submit_email",
            phase="unknown", endpoint_kind="email_submit", http_method="POST", **self.facts,
        )
        with self.assertRaisesRegex(ValueError, "未决"):
            registration.record_submission_fact(
                self.attempt["id"], submission_id="another-login", kind="resume_login", stage="submit_email",
                phase="dispatch_intent", endpoint_kind="email_submit", http_method="POST", **self.facts,
            )

    def test_verified_original_login_can_complete_profile_never_previously_dispatched(self):
        other = registration.create_attempt("password-route@example.test")
        run = registration.start_run(
            other["id"], execution_id="password-route", initial_status="running",
        )
        facts = {"run_id": run["id"], "execution_id": "password-route"}
        registration.save_password_checkpoint(
            other["id"], email="password-route@example.test", password="SyntheticCandidate123!",
            state="started", **facts,
        )
        registration.record_submission_fact(
            other["id"], submission_id="old-password", kind="password", stage="password_create",
            phase="unknown", endpoint_kind="password_submit", http_method="POST", **facts,
        )
        registration.authorize_route_resume(
            other["id"], email="password-route@example.test",
            previous_route_no=1, route_attempt_no=2, **facts,
        )
        for phase in ("dispatch_intent", "request_observed", "response_observed", "confirmed"):
            registration.record_submission_fact(
                other["id"], submission_id="verified-login", kind="resume_login", stage="login_password",
                phase=phase, endpoint_kind="password_submit", http_method="POST",
                http_status=200 if phase in {"response_observed", "confirmed"} else None,
                result="success" if phase == "confirmed" else "", **facts,
            )
        registration.record_submission_fact(
            other["id"], submission_id="first-profile", kind="profile", stage="profile",
            phase="dispatch_intent", endpoint_kind="profile_submit", http_method="POST", **facts,
        )
        private = registration.get_private_resume_context(other["id"], email="password-route@example.test")
        self.assertIn("old-password", unresolved_submission_ids(private["submission_facts"]))


class RegistrationPreparedRouteResumeTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()
        self.email = "prepared-route@example.test"
        self.password = "SyntheticPreparedCandidate123!"
        self.attempt = registration.create_attempt(self.email)
        original = registration.start_run(
            self.attempt["id"], execution_id="prepared-original", initial_status="running",
        )
        original_facts = {"run_id": original["id"], "execution_id": "prepared-original"}
        registration.save_password_checkpoint(
            self.attempt["id"], email=self.email, password=self.password,
            state="prepared", **original_facts,
        )
        registration.record_submission_fact(
            self.attempt["id"], submission_id="original-password", kind="password",
            stage="password_create", phase="prepared", endpoint_kind="password_submit",
            http_method="POST", **original_facts,
        )
        registration.finish_run(original["id"], status="failed")
        self.run = registration.start_run(
            self.attempt["id"], execution_id="prepared-current", initial_status="running",
        )
        self.facts = {"run_id": self.run["id"], "execution_id": "prepared-current"}
        registration.record_submission_fact(
            self.attempt["id"], submission_id="current-signin", kind="email", stage="nextauth",
            phase="unknown", endpoint_kind="nextauth_signin", http_method="POST", **self.facts,
        )

    def authorize(self):
        return registration.authorize_route_resume(
            self.attempt["id"], email=self.email, previous_route_no=1, route_attempt_no=2, **self.facts,
        )

    def write(self, identifier, *, kind="email", stage="submit_email", endpoint="email_submit",
              phase="dispatch_intent", result=""):
        return registration.record_submission_fact(
            self.attempt["id"], submission_id=identifier, kind=kind, stage=stage, phase=phase,
            endpoint_kind=endpoint, http_method="POST", result=result, **self.facts,
        )

    def test_only_prepared_candidate_keeps_preauth_and_can_continue_after_new_email_confirmation(self):
        self.assertTrue(self.authorize())
        self.write("new-email")
        with self.assertRaisesRegex(ValueError, "未决"):
            self.write("new-password", kind="password", stage="password_create", endpoint="password_submit")
        self.write("new-email", phase="confirmed", result="success")
        self.write("new-password", kind="password", stage="password_create", endpoint="password_submit")
        private = registration.get_private_resume_context(self.attempt["id"], email=self.email)
        self.assertEqual(private["route_resume_authorization"]["mode"], "preauth")
        self.assertEqual(private["password"], self.password)
        self.assertEqual(private["password_state"], "prepared")
        self.assertIn("current-signin", unresolved_submission_ids(private["submission_facts"]))
        self.assertEqual(registration.get_run(self.run["id"])["action_type"], "registration")

    def test_prepared_preauth_does_not_grant_original_identity_login(self):
        self.authorize()
        with self.assertRaisesRegex(ValueError, "registration_resume"):
            self.write("new-login", kind="resume_login")

    def test_one_prepared_preauth_authorization_cannot_bypass_new_unknown_email(self):
        self.authorize()
        self.write("new-email")
        self.write("new-email", phase="unknown")
        with self.assertRaisesRegex(ValueError, "未决"):
            self.write("another-email")

    def test_prepared_candidate_digest_is_rechecked_before_preauth_dispatch(self):
        self.authorize()
        decode = registration._decode

        def changed_candidate(value):
            result = decode(value)
            if isinstance(result, dict) and result.get("password") == self.password:
                return {**result, "password": "DifferentSyntheticCandidate123!"}
            return result

        with patch.object(registration, "_decode", side_effect=changed_candidate):
            with self.assertRaisesRegex(ValueError, "未决"):
                self.write("new-email")
        private = registration.get_private_resume_context(self.attempt["id"], email=self.email)
        self.assertEqual(private["password"], self.password)

    def test_prepared_mode_does_not_override_an_actually_dispatched_password(self):
        self.write("actual-password", kind="password", stage="password_create",
                   endpoint="password_submit", phase="unknown")
        self.assertTrue(self.authorize())
        private = registration.get_private_resume_context(self.attempt["id"], email=self.email)
        self.assertEqual(private["route_resume_authorization"]["mode"], "identity_login")
        with self.assertRaisesRegex(ValueError, "未决"):
            self.write("new-email")

    def test_prepared_preauth_authorization_is_not_inherited_by_a_new_run(self):
        self.authorize()
        registration.finish_run(self.run["id"], status="failed")
        newer = registration.start_run(
            self.attempt["id"], execution_id="prepared-next-run", initial_status="running",
        )
        self.facts = {"run_id": newer["id"], "execution_id": "prepared-next-run"}
        with self.assertRaisesRegex(ValueError, "registration_resume"):
            self.write("new-login", kind="resume_login")
