"""资料提交按本动作回执收口，HTTP 成功不能代替完整身份会话。"""
from contextlib import ExitStack, contextmanager
import json
import shutil
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.auth.browser import password_auth
from core.auth.browser.browser_submission import BrowserSubmissionReceipt, record_browser_submission_fact
from core.registration.roxy import _make_submission_observer
from core.auth.browser import selenium_dom
from core.storage import registration
from tests.support_pg import PostgresTestCase


class _Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = time

    def sleep(self, seconds):
        self.now += seconds


class _ProfileHarness:
    @contextmanager
    def profile(self, *, status=None, auth_error=None, session=False, context=None, before=None, click=None, prepared_misses=0):
        clock = _Clock()
        driver = SimpleNamespace(current_url="https://auth.openai.com/about-you", execute_script=Mock())
        driver.execute_script.side_effect = lambda script, *args: (
            {"valid": True, "fields": []} if "form.checkValidity()" in script else []
        )
        if context is not None:
            driver._registration_fact_context = context
        observer = _make_submission_observer(driver)
        if before is not None:
            before(driver, observer)

        selection_attempts = [0]

        def submit(current, *, before_dispatch=None):
            selection_attempts[0] += 1
            if selection_attempts[0] <= prepared_misses:
                return False
            if before_dispatch is not None:
                before_dispatch()
            if click is not None:
                return click(current, observer)
            if status is not None:
                meta = {"target_id": "current-target", "request_id": "current-request",
                        "endpoint_kind": "profile_submit", "http_method": "POST"}
                observer(meta)
                observer({**meta, "response": True, "http_status": status, "duration_ms": 1200,
                          "auth_error": auth_error})
            if session:
                current.current_url = "https://chatgpt.com/"
            return True

        with ExitStack() as stack:
            stack.enter_context(patch.object(password_auth, "time", clock))
            stack.enter_context(patch.object(password_auth, "_page_snapshot", side_effect=lambda current: {
                "url": current.current_url, "inputs": [{"name": "name"}, {"name": "age"}]
                if "/about-you" in current.current_url else [],
            }))
            for name in ("human_delay", "_accept_profile_consents", "_check_manual_stop"):
                stack.enter_context(patch.object(password_auth, name))
            stack.enter_context(patch.object(password_auth, "_fill_birthday_or_age", return_value="age"))
            stack.enter_context(patch.object(password_auth, "_select_or_type", return_value=True))
            stack.enter_context(patch.object(password_auth, "_profile_account_rejection_marker", return_value=None))
            stack.enter_context(patch.object(password_auth, "log_submission_diagnostics"))
            recover = stack.enter_context(patch.object(password_auth, "recover_submission_page", return_value=None))
            read = stack.enter_context(patch.object(password_auth, "_read_profile_session_once", return_value={
                "accessToken": "synthetic-session", "user": {"email": "parent+child@example.test"},
            }))
            button = stack.enter_context(patch.object(password_auth, "_click_if_enabled_submit", side_effect=submit))
            yield driver, clock, button, recover, read

    def complete(self, driver):
        return password_auth._complete_profile_page(
            driver, "Unit User", "2000-01-02", timeout=10, transition_timeout=90,
            expected_email="parent+child@example.test",
        )


class ProfileSubmissionReceiptTests(_ProfileHarness, unittest.TestCase):
    def test_exact_current_400_existing_account_has_durable_safe_marker(self):
        with self.profile(status=400, auth_error={"code": "user_already_exists", "type": "invalid_request_error",
                                                 "message": "synthetic-private"}) as (driver, _, click, recover, read):
            with self.assertRaises(RuntimeError) as caught:
                self.complete(driver)
            self.assertEqual(driver._browser_submission_receipt.safe_fact()["error_type"],
                             "account_create_user_already_exists")
            self.assertEqual(type(caught.exception).__name__, "ProfileAccountAlreadyExistsError")
            self.assertEqual(caught.exception.http_status, 400)
            self.assertEqual(caught.exception.auth_error, {
                "code": "user_already_exists", "type": "invalid_request_error", "category": "email_conflict",
            })
            self.assertNotIn("synthetic-private", str(caught.exception))
            self.assertEqual(driver._browser_submission_receipt.phase, "rejected")
            click.assert_called_once()
            recover.assert_not_called()
            read.assert_not_called()

    def test_other_profile_rejections_never_acquire_existing_account_marker(self):
        cases = [(400, "invalid_auth_step"), (400, "email_taken"), (401, "user_already_exists"),
                 (409, "user_already_exists"), (400, None)]
        for status, code in cases:
            with self.subTest(status=status, code=code), self.profile(
                status=status, auth_error={"code": code, "type": "invalid_request_error"},
            ) as (driver, *_):
                with self.assertRaises(RuntimeError) as caught:
                    self.complete(driver)
                self.assertEqual(driver._browser_submission_receipt.error_type, f"account_create_http_{status}")
                self.assertEqual(type(caught.exception), RuntimeError)

    def test_existing_profile_exception_retains_only_actual_safe_error_fields(self):
        with self.profile(status=400, auth_error={"code": "user_already_exists", "type": "authentication_error",
                                                 "message": "synthetic-private"}) as (driver, *_):
            with self.assertRaises(RuntimeError) as caught:
                self.complete(driver)
        self.assertEqual(caught.exception.auth_error, {
            "code": "user_already_exists", "type": "authentication_error", "category": "email_conflict",
        })
        self.assertNotIn("synthetic-private", str(caught.exception))

    def test_current_profile_4xx_rejects_early_without_reposting(self):
        for status in (400, 401, 403, 409, 422, 429):
            with self.subTest(status=status), self.profile(status=status) as (driver, clock, click, recover, read):
                with self.assertRaisesRegex(RuntimeError, f"request_unknown: account_create_http_{status}"):
                    self.complete(driver)
                self.assertLess(clock.now, 5)
                click.assert_called_once()
                recover.assert_not_called()
                read.assert_not_called()
                receipt = driver._browser_submission_receipt
                self.assertEqual((receipt.kind, receipt.endpoint_kind, receipt.phase),
                                 ("profile", "profile_submit", "rejected"))
                self.assertEqual(receipt.http_status, status)

    def test_profile_200_still_requires_identity_session(self):
        with self.profile(status=200) as (driver, clock, click, recover, read):
            with self.assertRaisesRegex(RuntimeError, "request_unknown"):
                self.complete(driver)
            self.assertGreaterEqual(clock.now, 90)
            self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
            click.assert_called_once()
            read.assert_not_called()

    def test_profile_200_confirms_only_after_expected_email_session(self):
        with self.profile(status=200, session=True) as (driver, clock, click, recover, read):
            self.assertTrue(self.complete(driver))
            self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
            self.assertEqual(read.call_args.kwargs["expected_email"], "parent+child@example.test")

    def test_missing_target_remains_prepared_and_can_wait_before_single_dispatch(self):
        with self.profile(status=400, prepared_misses=2) as (driver, clock, click, recover, read):
            with self.assertRaisesRegex(RuntimeError, "account_create_http_400"):
                self.complete(driver)
            self.assertEqual(click.call_count, 3)
            self.assertLess(clock.now, 5)
            self.assertEqual(len(driver._browser_submission_receipts), 1)
            self.assertEqual(driver._browser_submission_receipt.phase, "rejected")

    def test_bridge_failure_after_dispatch_preserves_unknown_without_second_click(self):
        def click(driver, observer):
            raise RuntimeError("synthetic-private-bridge-message")

        with self.profile(click=click) as (driver, clock, button, recover, read):
            with self.assertRaisesRegex(RuntimeError, "request_unknown: profile_dispatch_unknown") as caught:
                self.complete(driver)
            self.assertNotIn("synthetic-private", str(caught.exception))
            self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
            button.assert_called_once()

    def test_auth_error_is_filtered_on_bound_receipt_and_never_in_durable_fact(self):
        def click(driver, observer):
            meta = {"target_id": "current-target", "request_id": "current-request",
                    "endpoint_kind": "profile_submit", "http_method": "POST"}
            observer(meta)
            observer({**meta, "response": True, "http_status": 400,
                      "auth_error": {"code": "invalid_auth_step", "type": "invalid_request_error",
                                     "category": "synthetic-private", "message": "synthetic-private"}})
            return True

        with self.profile(click=click) as (driver, *rest):
            with self.assertRaisesRegex(RuntimeError, "invalid_auth_step") as caught:
                self.complete(driver)
            self.assertNotIn("synthetic-private", str(caught.exception))
            receipt = driver._browser_submission_receipt
            self.assertEqual(receipt.auth_error["category"], "auth_state")
            self.assertNotIn("auth_error", receipt.safe_fact())
            self.assertNotIn("request_binding", receipt.safe_fact())

    def test_successful_http_cannot_bypass_identity_mismatch(self):
        with self.profile(status=200, session=True) as (driver, clock, click, recover, read):
            read.side_effect = RuntimeError("request_unknown: session_identity_mismatch")
            with self.assertRaisesRegex(RuntimeError, "session_identity_mismatch"):
                self.complete(driver)
            self.assertEqual(driver._browser_submission_receipt.phase, "unknown")
            recover.assert_not_called()

    def test_late_old_response_does_not_reject_new_profile(self):
        old = BrowserSubmissionReceipt(kind="profile", stage="profile", phase="ui_dispatched",
                                       endpoint_kind="profile_submit")
        meta = {"target_id": "old-target", "request_id": "old-request",
                "endpoint_kind": "profile_submit", "http_method": "POST"}

        def before(driver, observer):
            driver._browser_submission_receipts = [old]
            driver._browser_submission_receipt = old
            observer(meta)

        def click(driver, observer):
            observer({**meta, "response": True, "http_status": 400})
            driver.current_url = "https://chatgpt.com/"
            return True

        with self.profile(before=before, click=click) as (driver, *rest):
            self.assertTrue(self.complete(driver))
            self.assertEqual(old.phase, "rejected")
            self.assertIsNot(driver._browser_submission_receipt, old)
            self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
            self.assertIsNone(driver._browser_submission_receipt.http_status)

    def test_ambiguous_late_old_request_cannot_bind_to_current_profile(self):
        old = BrowserSubmissionReceipt(kind="profile", stage="profile", phase="confirmed",
                                       endpoint_kind="profile_submit")

        def before(driver, observer):
            driver._browser_submission_receipts = [old]

        with self.profile(status=400, session=True, before=before) as (driver, *rest):
            self.assertTrue(self.complete(driver))
            self.assertEqual(driver._browser_submission_receipt.phase, "confirmed")
            self.assertIsNone(driver._browser_submission_receipt.http_status)

    def test_dispatch_persistence_failure_prevents_click(self):
        context = {"attempt_id": 11, "run_id": 12, "job_id": 13, "execution_id": "unit-execution"}
        dispatched = []

        def click(driver, observer):
            dispatched.append(True)
            return True

        def persist(_attempt, **fact):
            if fact["phase"] == "dispatch_intent":
                raise RuntimeError("synthetic-persist-failure")
            return fact

        with self.profile(context=context, click=click) as (driver, *rest), \
                patch.object(registration, "record_submission_fact", side_effect=persist):
            with self.assertRaisesRegex(RuntimeError, "synthetic-persist-failure"):
                self.complete(driver)
        self.assertEqual(dispatched, [])


class ProfileDispatchBoundaryTests(unittest.TestCase):
    def test_disabled_submit_does_not_fall_through_to_request_submit(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("需要 Node 验证只读目标选择脚本")
        driver = SimpleNamespace(execute_script=Mock(return_value=None))
        selenium_dom._click_if_enabled_submit(driver)
        script = driver.execute_script.call_args.args[0]
        fixture = """
        const submit={disabled:true,offsetWidth:1};
        const form={offsetWidth:1,querySelector:()=>submit,requestSubmit(){throw new Error('不能提前提交');}};
        const document={querySelectorAll:selector=>selector==='form'?[form]:selector.includes(':not')?[]:[submit]};
        """
        result = subprocess.run([node, "-e", fixture + "const select=function(){" + script +
                                 "};console.log(JSON.stringify({selected:!!select()}));"],
                                check=True, capture_output=True, text=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), {"selected": False})

    def test_request_submit_waits_for_durable_callback_before_submitting_form(self):
        form = object()
        order = []
        driver = SimpleNamespace(execute_script=Mock(side_effect=lambda script, *args: (
            order.append("request_submit") if args else {"request_submit_form": form}
        )))
        self.assertTrue(selenium_dom._click_if_enabled_submit(
            driver, before_dispatch=lambda: order.append("durable"),
        ))
        self.assertEqual(order, ["durable", "request_submit"])

    def test_no_target_does_not_enter_dispatch(self):
        driver = SimpleNamespace(execute_script=Mock(return_value=None))
        before = Mock()
        self.assertFalse(selenium_dom._click_if_enabled_submit(driver, before_dispatch=before))
        before.assert_not_called()

    def test_persistence_failure_is_not_swallowed_before_click(self):
        driver = SimpleNamespace(execute_script=Mock(return_value=object()))
        with patch.object(selenium_dom, "_human_click") as click:
            with self.assertRaisesRegex(RuntimeError, "synthetic-persist-failure"):
                selenium_dom._click_if_enabled_submit(
                    driver, before_dispatch=Mock(side_effect=RuntimeError("synthetic-persist-failure")),
                )
            click.assert_not_called()

    def test_dispatch_bridge_failure_is_not_retried_as_missing_button(self):
        driver = SimpleNamespace(execute_script=Mock(return_value=object()))
        before = Mock()
        with patch.object(selenium_dom, "_human_click", side_effect=RuntimeError("bridge-failure")):
            with self.assertRaisesRegex(RuntimeError, "bridge-failure"):
                selenium_dom._click_if_enabled_submit(driver, before_dispatch=before)
        before.assert_called_once()


class ProfileReceiptStorageTests(_ProfileHarness, PostgresTestCase):
    def setUp(self):
        registration.reset_ready()
        registration.init()

    def test_exact_profile_conflict_marker_survives_deduplicated_rejection(self):
        address = "parent+child@example.test"
        attempt = registration.create_attempt(address)
        run = registration.start_run(attempt["id"], execution_id="profile-conflict", initial_status="running")
        context = {"attempt_id": attempt["id"], "run_id": run["id"], "execution_id": "profile-conflict"}
        with self.profile(status=400, auth_error={"code": "user_already_exists", "type": "invalid_request_error"},
                          context=context) as (driver, *_):
            with self.assertRaises(RuntimeError):
                self.complete(driver)
        private = registration.get_private_resume_context(attempt["id"], email=address)
        rejected = [item for item in private["submission_facts"] if item["phase"] == "rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["error_type"], "account_create_user_already_exists")
        self.assertEqual(rejected[0]["http_status"], 400)

    def test_rejected_profile_preserves_original_password_account_and_resume(self):
        address = "parent+child@example.test"
        attempt = registration.create_attempt(address)
        run = registration.start_run(attempt["id"], execution_id="profile-execution", initial_status="running")
        saved = registration.save_password_checkpoint(
            attempt["id"], email=address, password="SyntheticOriginalPassword123!", state="confirmed",
            account={"email": address}, run_id=run["id"], execution_id="profile-execution",
        )
        context = {"attempt_id": attempt["id"], "run_id": run["id"], "execution_id": "profile-execution"}
        with self.profile(status=400, context=context) as (driver, *rest):
            with self.assertRaisesRegex(RuntimeError, "account_create_http_400"):
                self.complete(driver)
        private = registration.get_private_resume_context(attempt["id"], email=address)
        current = registration.get_attempt(attempt["id"])
        self.assertEqual(private["password"], "SyntheticOriginalPassword123!")
        self.assertEqual(current["account_id"], saved["account_id"])
        facts = [f for f in private["submission_facts"] if f["kind"] == "profile"]
        self.assertEqual(len({f["submission_id"] for f in facts}), 1)
        self.assertIn("dispatch_intent", [f["phase"] for f in facts])
        self.assertIn("rejected", [f["phase"] for f in facts])
        self.assertTrue(any(f["phase"] == "rejected" and f["http_status"] == 400 for f in facts))
        registration.finish_run(run["id"], status="failed")
        resumed = registration.retry_run(attempt["id"], action_type="registration_resume")
        self.assertEqual(resumed["attempt_id"], attempt["id"])


if __name__ == "__main__":
    unittest.main()
