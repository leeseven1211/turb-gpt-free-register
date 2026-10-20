"""换绑目标地址与旧地址重认证的执行租约边界。"""
from contextlib import ExitStack, nullcontext
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import email_auth_guard as guard, email_change_service as service, record_store
from core.storage import email_address_allocations as store
from tests.support_pg import PostgresTestCase


class EmailChangeFrozenCompatibilityTests(unittest.TestCase):
    def test_disabled_new_derivation_still_restores_original_acquisition(self):
        context = SimpleNamespace(
            checkpoint=lambda: None, task_id=37,
            run={"data": {"remail_acquisition_id": "change:37"}},
            config_snapshot={"email_derivation_enabled": False, "email_derivation_sources": ""},
        )
        with patch.object(store, "find_allocation", return_value={"id": 9}) as lookup, patch.object(
            service.email_provider, "acquire_email", return_value="mother+abc123@example.test"
        ) as acquire, patch.object(service.db, "get_account_by_email", return_value=None):
            target, result = service._acquire_email_change_target(
                context, account_id=1, source="icloud_hide", current_email="old@example.test",
            )
        self.assertEqual(target, "mother+abc123@example.test")
        self.assertIsNone(result)
        lookup.assert_called_once_with(acquisition_id="change:37")
        acquire.assert_called_once_with("icloud_hide", owner_kind="email_change", owner_id=37, acquisition_id="change:37")


class EmailChangeAuthGuardTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        parent_id = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "mother@example.test", "status": "used",
            "client_id": "fixture-client", "refresh_token": "fixture-refresh",
        })
        profile = store.create_inbox_profile(inbox_key="change-fixture", connector="outlook", credential_ref="fixture-reference", inbox_locator={"parent_id": parent_id})
        store.configure_parent("outlook", parent_id, max_children=3, inbox_profile_id=profile["id"])
        self.old = store.allocate_address(source="outlook", parent_id=parent_id, acquisition_id="old", owner_kind="fixture", owner_id="old")["address"]
        self.target = store.allocate_address(source="outlook", parent_id=parent_id, acquisition_id="target", owner_kind="fixture", owner_id="target")["address"]

    def _context(self, current_email):
        return SimpleNamespace(
            account_id=7, run_id=8, task_id=9, email=current_email,
            run={"data": {"email_source": "outlook"}, "trigger": "fixture"},
            config_snapshot={"email_change_enabled": True}, lease=lambda **_kwargs: nullcontext(),
            report=Mock(), checkpoint=Mock(), remote_request_started=Mock(), remote_request_receipt=Mock(),
        )

    def _run(self, *, current_email=None, fail_wait=False):
        old_email = current_email or self.old
        context = self._context(old_email)
        route = SimpleNamespace(proxy_url="", public_dict=lambda: {}, release=Mock())
        session = Mock()
        observed = []

        def begin(*_args, **_kwargs):
            self.assertEqual(guard.current_session().email, self.target)
            self.assertIsNotNone(store.find_active_otp_request(self.target))
            observed.append("begin")
            return service.BeginChangeResult(session, "fixture-at", 123.0, False)

        def wait(email, **_kwargs):
            self.assertEqual(email, self.target)
            self.assertEqual(guard.current_session().email, self.target)
            guard.begin_generation(123.0)
            guard.observe_candidate("target-message", {"recipient": email})
            if fail_wait:
                raise RuntimeError("fixture-mailbox-disconnect")
            return "123456"

        def writeback(_account_id, **kwargs):
            if kwargs.get("ok"):
                self.assertEqual(guard.current_session().email, self.target)
                self.assertIsNotNone(store.find_active_otp_request(self.target))
                observed.append("writeback")
            return True

        def child(*_args, **_kwargs):
            self.assertIsNone(store.find_active_otp_request(self.target))
            return {"accepted": True, "task_id": 21, "run_id": 22}

        with ExitStack() as stack:
            mocks = [
                patch.object(service.db, "get_account", return_value={"email": old_email, "email_source": "outlook", "access_token": "fixture-old-at"}),
                patch("core.browser_traffic.record_unavailable"),
                patch.object(service.email_provider, "validate_email_source", return_value="outlook"),
                patch.object(service.db, "claim_account_email_change", return_value=True),
                patch.object(service, "_acquire_email_change_target", return_value=(self.target, None)),
                patch.object(service.db, "mark_account_email_change_running"),
                patch.object(service, "acquire_account_proxy", return_value=route),
                patch.object(service, "_account_stable_identity", return_value=SimpleNamespace(session_payload=lambda: {})),
                patch("core.session.BrowserSession", return_value=session),
                patch.object(service, "begin_change_with_optional_reauth", side_effect=begin),
                patch.object(service.email_provider, "wait_for_otp", side_effect=wait),
                patch.object(service, "EmailChangeProtocol", return_value=Mock()),
                patch.object(service.email_provider, "email_material_line", return_value="fixture-material"),
                patch.object(service.db, "finish_account_email_change", side_effect=writeback),
                patch.object(service, "_safe_readback", return_value=True),
                patch.object(service, "_finalize_consumed_email", return_value={"status": "success"}),
                patch.object(service, "_enqueue_live_check_child", side_effect=child),
            ]
            for mocked in mocks:
                stack.enter_context(mocked)
            result = service._handle_email_change(context)
        return result, observed

    def test_derived_target_is_locked_through_verify_and_writeback_then_released_before_child(self):
        with guard.email_auth_session(self.old) as old_session:
            result, observed = self._run()
            self.assertIs(guard.current_session(), old_session)
            self.assertIsNone(store.get_otp_request(old_session.row["id"]).get("candidate_message_key"))
        self.assertEqual(result.status, "success")
        self.assertEqual(observed, ["begin", "writeback"])
        target = store.list_otp_requests(self.target)[0]
        self.assertEqual(target["candidate_message_key"], "target-message")
        self.assertEqual(target["submission_state"], "offered")
        self.assertEqual(target["state"], "confirmed")
        self.assertIsNone(store.find_active_otp_request(self.target))

    def test_ordinary_old_mailbox_also_holds_target_and_failure_preserves_unknown_without_leak(self):
        result, observed = self._run(current_email="ordinary@example.test", fail_wait=True)
        self.assertEqual(result.status, "request_unknown")
        self.assertEqual(observed, ["begin"])
        latest = store.list_otp_requests(self.target)[0]
        self.assertEqual(latest["state"], "cancelled")
        self.assertEqual(latest["submission_state"], "result_unknown")
        self.assertIsNone(guard.current_session())
        self.assertIsNone(store.find_active_otp_request(self.target))

    def test_recent_login_with_second_positional_email_uses_old_scope_and_restores_target(self):
        from core import account_liveness

        old_transport = Mock()
        fresh_transport = Mock()
        seen = []

        def complete(*_args, **_kwargs):
            self.assertEqual(guard.current_session().email, self.old)
            guard.begin_generation(122.0)
            guard.observe_candidate("old-reauth-message", {"recipient": self.old})
            seen.append("old")
            return {"accessToken": "fixture-fresh-at"}, "email_otp"

        with guard.email_auth_session(self.target) as target_session, patch.object(
            account_liveness, "_network_preflight_with_retry", return_value=(fresh_transport, "https://auth.example.test/authorize")
        ), patch.object(account_liveness, "follow_authorize", return_value="https://auth.example.test/email-verification"), patch.object(
            account_liveness, "_complete_recent_login_on_session", side_effect=complete
        ), patch.object(account_liveness, "_warm_authenticated_session"):
            result = account_liveness.perform_recent_login(old_transport, self.old, email_source="outlook")
            self.assertEqual(result["access_token"], "fixture-fresh-at")
            self.assertIs(guard.current_session(), target_session)
            self.assertIsNone(store.get_otp_request(target_session.row["id"]).get("candidate_message_key"))
        self.assertEqual(seen, ["old"])
        self.assertEqual(store.list_otp_requests(self.old)[0]["candidate_message_key"], "old-reauth-message")

    def test_busy_target_propagates_for_gateway_deferral_before_any_remote_begin(self):
        entered, release = threading.Event(), threading.Event()

        def hold_target():
            with guard.email_auth_session(self.target):
                entered.set()
                self.assertTrue(release.wait(10))

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(hold_target)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(store.OtpLeaseBusy):
                    self._run()
            finally:
                release.set()
            future.result(timeout=5)
