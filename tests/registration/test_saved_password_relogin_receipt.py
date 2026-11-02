"""受控已保存密码重登录只收口明确关联的原登录回执。"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, complete_saved_password_relogin, record_browser_submission_fact, unresolved_submission_ids
from core.storage import registration, postgres as postgres_store
from tests.support_pg import PostgresTestCase
from tests.registration.test_registration_password_flow import _saved_password_refresh_flow


class SavedPasswordReloginReceiptTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()

    def context(self):
        attempt = registration.create_attempt("saved@example.test")
        run = registration.start_run(int(attempt["id"]), action_type="registration_resume",
                                     execution_id="saved-relogin", initial_status="running")
        context = {"attempt_id": int(attempt["id"]), "run_id": int(run["id"]),
                   "execution_id": "saved-relogin", "job_id": None}
        registration.save_password_checkpoint(**context, email="saved@example.test",
                                              password="SavedPass123!", state="started")
        return context

    def facts(self, context):
        return registration.get_private_resume_context(context["attempt_id"], email="saved@example.test")["submission_facts"]

    def profile(self, driver):
        profile = BrowserSubmissionReceipt(kind="profile", stage="profile", endpoint_kind="profile_submit", http_method="POST")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=profile)
        return profile

    def pair(self, context, *, confirmed=True):
        driver = SimpleNamespace(_registration_fact_context=context)
        old, new = [BrowserSubmissionReceipt(kind="resume_login", stage="login_password",
                    endpoint_kind="password_submit", http_method="POST") for _ in range(2)]
        record_browser_submission_fact(driver, "dispatch_intent", receipt=old)
        record_browser_submission_fact(driver, "unknown", receipt=old, result="unknown")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=new)
        if confirmed:
            record_browser_submission_fact(driver, "confirmed", receipt=new, result="success")
        return driver, old, new

    def resolve(self, context, old, new, **changes):
        args = {**context, "email": "saved@example.test", "password": "SavedPass123!",
                "submission_id": old.submission_id, "replacement_submission_id": new.submission_id, **changes}
        return registration.supersede_saved_password_login_submission(**args)

    def test_controlled_refresh_then_confirmed_login_and_otp_allows_profile(self):
        context = self.context()
        with _saved_password_refresh_flow() as flow:
            flow.driver._registration_fact_context = context
            password_auth._fill_password_page_if_present(flow.driver, "saved@example.test", existing_password="SavedPass123!")
            old, new = flow.driver._browser_submission_receipts
            otp = BrowserSubmissionReceipt(kind="resume_login", stage="email_otp", endpoint_kind="otp_submit", http_method="POST")
            record_browser_submission_fact(flow.driver, "dispatch_intent", receipt=otp)
            record_browser_submission_fact(flow.driver, "confirmed", receipt=otp, result="success")
            profile = self.profile(flow.driver)
        facts = self.facts(context)
        self.assertEqual(old.phase, "superseded")
        self.assertTrue(any(f["submission_id"] == old.submission_id and f["phase"] == "unknown" for f in facts))
        replacement = next(f for f in facts if f["phase"] == "superseded")
        self.assertEqual((replacement["result"], replacement["error_type"], replacement["replacement_submission_id"]),
                         ("unknown", "saved_password_relogin", new.submission_id))
        self.assertEqual(unresolved_submission_ids(facts), {profile.submission_id})

    def test_resolution_rejects_unconfirmed_login_identity_password_and_stale_fence(self):
        context = self.context()
        driver, old, new = self.pair(context, confirmed=False)
        with self.assertRaisesRegex(ValueError, "尚未确认"):
            self.resolve(context, old, new)
        record_browser_submission_fact(driver, "confirmed", receipt=new, result="success")
        for changes in ({"email": "other@example.test"}, {"password": "different"},
                        {"execution_id": "stale"}, {"job_id": 999},
                        {"replacement_submission_id": old.submission_id}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.resolve(context, old, new, **changes)
        with self.assertRaisesRegex(ValueError, "未决浏览器"):
            self.profile(driver)

    def test_non_login_or_cross_run_fact_cannot_be_superseded(self):
        context = self.context()
        driver, old, new = self.pair(context)
        original_facts = self.facts(context)
        for identifier in (old.submission_id, new.submission_id):
            for change in ({"kind": "password"}, {"stage": "password_create"},
                           {"endpoint_kind": "otp_submit"}, {"http_method": "GET"},
                           {"run_id": context["run_id"] + 1}):
                with self.subTest(identifier=identifier, change=change):
                    with postgres_store.connect() as conn, conn.cursor() as cur:
                        cur.execute(f"UPDATE {postgres_store.qualified('registration_attempts')} SET private_context=jsonb_set(private_context, '{{submission_facts}}', %s::jsonb) WHERE id=%s",
                                    (json.dumps([{**fact, **change} if fact['submission_id'] == identifier else fact for fact in original_facts]), context['attempt_id']))
                    with self.assertRaises(ValueError):
                        self.resolve(context, old, new)
                    if "run_id" not in change or identifier == new.submission_id:
                        with self.assertRaisesRegex(ValueError, "未决浏览器"):
                            self.profile(driver)

    def test_non_resume_and_finished_run_cannot_resolve_login(self):
        context = self.context()
        _, old, new = self.pair(context)
        for action, status in (("registration", "running"), ("registration_resume", "failed")):
            with self.subTest(action=action, status=status):
                with postgres_store.connect() as conn, conn.cursor() as cur:
                    cur.execute(f"UPDATE {postgres_store.qualified('registration_runs')} SET action_type=%s, status=%s WHERE id=%s",
                                (action, status, context['run_id']))
                with self.assertRaises(ValueError):
                    self.resolve(context, old, new)
        self.assertIn(old.submission_id, unresolved_submission_ids(self.facts(context)))

    def test_dedicated_resolution_is_idempotent_and_does_not_close_other_unknown(self):
        context = self.context()
        driver, old, new = self.pair(context)
        otp = BrowserSubmissionReceipt(kind="resume_login", stage="email_otp", endpoint_kind="otp_submit")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=otp)
        record_browser_submission_fact(driver, "unknown", receipt=otp, result="unknown")
        self.resolve(context, old, new)
        self.resolve(context, old, new)
        another = BrowserSubmissionReceipt(kind="resume_login", stage="login_password", endpoint_kind="password_submit", http_method="POST")
        record_browser_submission_fact(driver, "dispatch_intent", receipt=another)
        record_browser_submission_fact(driver, "confirmed", receipt=another, result="success")
        with self.assertRaisesRegex(ValueError, "其他提交替代"):
            self.resolve(context, old, another)
        facts = self.facts(context)
        self.assertEqual(sum(f['phase'] == 'superseded' for f in facts), 1)
        self.assertEqual(unresolved_submission_ids(facts), {otp.submission_id})
        with self.assertRaisesRegex(ValueError, "未决浏览器"):
            self.profile(driver)

    def test_generic_fact_api_cannot_forge_saved_password_relogin_resolution(self):
        context = self.context()
        driver, old, new = self.pair(context)
        for phase, error_type in (("superseded", "saved_password_relogin"),
                                  (" superseded ", "saved_password_relogin"),
                                  ("superseded", " saved_password_relogin ")):
            with self.subTest(phase=phase, error_type=error_type), self.assertRaises(ValueError):
                registration.record_submission_fact(**context, submission_id=old.submission_id,
                    kind="resume_login", stage="login_password", endpoint_kind="password_submit", http_method="POST",
                    phase=phase, result="unknown", error_type=error_type, replacement_submission_id=new.submission_id)
        with self.assertRaisesRegex(ValueError, "专用校验入口"):
            record_browser_submission_fact(driver, "superseded", receipt=old, result="unknown",
                error_type="saved_password_relogin", replacement_submission_id=new.submission_id)
        self.assertEqual(old.phase, "unknown")
        self.assertIn(old.submission_id, unresolved_submission_ids(self.facts(context)))

    def test_late_original_rejection_before_new_confirmation_keeps_real_terminal(self):
        context = self.context()
        with _saved_password_refresh_flow() as flow:
            flow.driver._registration_fact_context = context

            def observe(driver, phase, *, receipt=None, **changes):
                if phase == "confirmed" and len(driver._browser_submission_receipts) == 2:
                    record_browser_submission_fact(driver, "rejected", receipt=driver._browser_submission_receipts[0], result="failure")
                return record_browser_submission_fact(driver, phase, receipt=receipt, **changes)

            flow.facts.side_effect = observe
            password_auth._fill_password_page_if_present(flow.driver, "saved@example.test", existing_password="SavedPass123!")
            old, _ = flow.driver._browser_submission_receipts
            self.profile(flow.driver)
        self.assertEqual(old.phase, "rejected")
        self.assertFalse(any(f["phase"] == "superseded" for f in self.facts(context)))

    def test_late_terminal_during_resolution_never_reverts_to_superseded(self):
        context = self.context()
        driver, old, new = self.pair(context)
        driver._registration_resume_login = True
        resolve = registration.supersede_saved_password_login_submission

        def late_rejection(*args, **kwargs):
            record_browser_submission_fact(driver, "rejected", receipt=old, result="failure")
            return resolve(*args, **kwargs)

        with patch.object(registration, "supersede_saved_password_login_submission", side_effect=late_rejection):
            complete_saved_password_relogin(driver, original=old, replacement=new, email="saved@example.test", password="SavedPass123!")
        self.assertEqual(old.phase, "rejected")
        self.profile(driver)

    def test_late_terminal_after_durable_superseded_never_downgrades_memory(self):
        context = self.context()
        driver, old, new = self.pair(context)
        driver._registration_resume_login = True
        resolve = registration.supersede_saved_password_login_submission

        def late_rejection(*args, **kwargs):
            result = resolve(*args, **kwargs)
            record_browser_submission_fact(driver, "rejected", receipt=old, result="failure")
            return result

        with patch.object(registration, "supersede_saved_password_login_submission", side_effect=late_rejection):
            complete_saved_password_relogin(driver, original=old, replacement=new, email="saved@example.test", password="SavedPass123!")
        self.assertEqual(old.phase, "rejected")
