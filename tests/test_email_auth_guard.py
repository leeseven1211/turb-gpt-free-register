"""派生地址认证租约、重入、候选代次与过期执行隔离。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from contextvars import copy_context
from datetime import datetime, timedelta, timezone
import inspect
import os
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core import email_auth_guard as guard, record_store
from core.storage import email_address_allocations as store
from tests.support_pg import PostgresTestCase


class OrdinaryEmailAuthGuardTests(unittest.TestCase):
    def test_ordinary_address_never_queries_new_tables_and_preserves_signature(self):
        def remote(email: str, *, value: int = 3) -> dict:
            self.assertIsNone(guard.current_session())
            guard.checkpoint()
            self.assertIsNone(guard.begin_generation(100))
            self.assertIsNone(guard.observe_candidate("unused", {"recipient": email}))
            return {"ok": True, "value": value}

        wrapped = guard.serialize_email_auth(remote)
        with patch.object(store, "find_allocation", side_effect=AssertionError("普通地址不能查询新表")), patch.object(store, "acquire_otp_request") as acquire:
            self.assertEqual(wrapped("ordinary@example.test", value=4), {"ok": True, "value": 4})
        acquire.assert_not_called()
        self.assertEqual(inspect.signature(wrapped), inspect.signature(remote))
        self.assertIs(wrapped.__wrapped__, remote)

    def test_unknown_plus_address_retains_legacy_auth_path(self):
        wrapped = guard.serialize_email_auth(lambda email: {"ok": True})
        with patch("core.email_derivation.find_binding", return_value=None), patch.object(store, "acquire_otp_request") as acquire:
            self.assertEqual(wrapped("ordinary+tag@example.test"), {"ok": True})
        acquire.assert_not_called()

    def test_all_remote_entrypoints_acquire_before_entering_original_body(self):
        from core.account_liveness import check_account_liveness, perform_recent_login
        from core.codex_oauth import run_codex_oauth
        from core.registration.dispatcher import run_registration
        from core.roxy_codex_oauth import run_roxy_chatgpt_account_action, run_roxy_codex_oauth
        from core.protocol_v2_liveness import refresh_access_token as protocol_refresh
        from core.roxy_liveness import refresh_access_token as roxy_refresh

        @contextmanager
        def denied(email):
            self.assertEqual(email, "derived+abc123@example.test")
            raise store.OtpLeaseBusy("认证执行正在占用")
            yield

        calls = (
            (run_registration, {"email": "derived+abc123@example.test", "name": "Fixture"}),
            (check_account_liveness, {"email": "derived+abc123@example.test"}),
            (run_codex_oauth, {"email": "derived+abc123@example.test", "force": True}),
            (run_roxy_chatgpt_account_action, {"email": "derived+abc123@example.test", "action": lambda _driver: None}),
            (run_roxy_codex_oauth, {"email": "derived+abc123@example.test", "force": True}),
            (perform_recent_login, {"session": Mock(), "email": "derived+abc123@example.test"}),
            (protocol_refresh, {"email": "derived+abc123@example.test"}),
            (roxy_refresh, {"email": "derived+abc123@example.test"}),
        )
        with patch.object(guard, "email_auth_session", side_effect=denied):
            for entry, kwargs in calls:
                with self.subTest(entry=entry.__name__), self.assertRaises(store.OtpLeaseBusy):
                    entry(**kwargs)


    def test_operation_gateway_guards_only_interactive_handlers_with_email(self):
        from core.operations import task_gateway

        for family, email, expected in (("openai_interactive", "derived+abc123@example.test", True), ("completion_coordinator", "derived+abc123@example.test", False), ("maintenance", "derived+abc123@example.test", False), ("openai_interactive", "", False)):
            with self.subTest(family=family, email=bool(email)):
                result = task_gateway.OperationResult.success()
                context = SimpleNamespace(
                    email=email, resource_family=family, cancellation=None, report=Mock(), checkpoint=Mock(),
                    finished=True, last_result=result, release_lease=Mock(),
                )
                session = SimpleNamespace(set_result=Mock())
                handler = Mock(return_value=result)
                with (
                    patch.dict(task_gateway._OPERATION_HANDLERS, {"guard_test": handler}),
                    patch.object(task_gateway, "_operation", return_value=SimpleNamespace(claim_run=Mock(return_value={"id": 1}))),
                    patch.object(task_gateway, "OperationHandlerContext", return_value=context),
                    patch("core.account_operation_executor.operation_log_context", return_value=nullcontext()),
                    patch.object(task_gateway, "operation_context", return_value=nullcontext()),
                    patch.object(task_gateway, "_operation_handler_result_payload", return_value={"ok": True}),
                    patch.object(guard, "email_auth_session", return_value=nullcontext(session)) as scope,
                ):
                    self.assertEqual(task_gateway._execute_operation_handler("guard_test", 1), {"ok": True})
                if expected:
                    scope.assert_called_once_with(email)
                    session.set_result.assert_called_once_with(result)
                else:
                    scope.assert_not_called()
                    session.set_result.assert_not_called()
                handler.assert_called_once_with(context)
                context.release_lease.assert_called_once()


    def test_gateway_defers_busy_email_without_failing_or_starting_remote_handler(self):
        from core.operations import task_gateway

        @contextmanager
        def busy(_email):
            raise store.OtpLeaseBusy("该完整邮箱已有活跃认证执行")
            yield

        context = SimpleNamespace(
            email="derived+abc123@example.test", resource_family="openai_interactive", cancellation=None,
            report=Mock(), checkpoint=Mock(), finished=False, last_result=None, release_lease=Mock(),
            is_cancel_requested=Mock(return_value=False), run_id=11, task_id=12,
        )
        repository = SimpleNamespace(claim_run=Mock(return_value={"id": 11}), requeue_claimed_run=Mock(return_value=True))
        handler = Mock()
        with (
            patch.dict(task_gateway._OPERATION_HANDLERS, {"guard_busy_test": handler}),
            patch.object(task_gateway, "_operation", return_value=repository),
            patch.object(task_gateway, "OperationHandlerContext", return_value=context),
            patch("core.account_operation_executor.operation_log_context", return_value=nullcontext()),
            patch.object(task_gateway, "operation_context", return_value=nullcontext()),
            patch.object(guard, "email_auth_session", side_effect=busy),
            patch.object(task_gateway, "notify_dispatch") as notify,
        ):
            result = task_gateway._execute_operation_handler("guard_busy_test", 11)
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(result["task_id"], 12)
        self.assertEqual(repository.requeue_claimed_run.call_args.kwargs["delay_seconds"], 1.0)
        handler.assert_not_called()
        context.release_lease.assert_called_once()
        notify.assert_called_once()


class DerivedEmailAuthGuardTests(PostgresTestCase):
    def setUp(self):
        record_store.init()
        parent_id = record_store.insert_row(record_store.OUTLOOK_POOL, {
            "email": "mother@example.test", "status": "used",
            "client_id": "fixture-client", "refresh_token": "fixture-refresh",
        })
        profile = store.create_inbox_profile(
            inbox_key="fixture-mother", connector="outlook", credential_ref="parent:outlook:fixture",
            inbox_locator={"parent_id": parent_id},
        )
        store.configure_parent("outlook", parent_id, max_children=3, inbox_profile_id=profile["id"])
        self.binding = store.allocate_address(source="outlook", parent_id=parent_id, acquisition_id="fixture:first", owner_kind="fixture", owner_id="first")
        self.sibling = store.allocate_address(source="outlook", parent_id=parent_id, acquisition_id="fixture:second", owner_kind="fixture", owner_id="second")
        self.email = self.binding["address"]
        self.sibling_email = self.sibling["address"]

    def test_same_thread_reenters_and_candidate_is_only_offered(self):
        sessions = []

        @guard.serialize_email_auth
        def nested(email):
            sessions.append(guard.current_session())
            current = guard.begin_generation(100)
            self.assertEqual(current["id"], guard.begin_generation("100")["id"])
            offered = guard.observe_candidate("mailbox:uidvalidity:uid", {"recipient": email, "header": "Received"}, {"uid": "2"})
            self.assertEqual(offered["state"], "active")
            self.assertEqual(offered["submission_state"], "offered")
            return {"ok": True}

        @guard.serialize_email_auth
        def outer(email):
            sessions.append(guard.current_session())
            self.assertEqual(len(store.list_otp_requests(email)), 1)
            return nested(email)

        self.assertEqual(outer(self.email), {"ok": True})
        self.assertIs(sessions[0], sessions[1])
        self.assertFalse(sessions[0].heartbeat_thread.is_alive())
        self.assertIsNone(guard.current_session())
        latest, prepared = store.list_otp_requests(self.email)
        self.assertEqual(prepared["state"], "superseded")
        self.assertEqual(latest["state"], "confirmed")
        self.assertEqual(latest["submission_state"], "offered")
        self.assertNotIn("code", latest)
        self.assertIsNone(store.find_active_otp_request(self.email))

    def test_failure_keeps_unknown_fact_and_same_attempt_can_rerun(self):
        sessions = []

        @guard.serialize_email_auth
        def failing(email):
            sessions.append(guard.current_session())
            guard.begin_generation(100)
            guard.observe_candidate("message-1", {"recipient": email})
            raise RuntimeError("远端回执中断")

        @guard.serialize_email_auth
        def resumed(email):
            sessions.append(guard.current_session())
            guard.begin_generation(101)
            return {"ok": True}

        with patch("core.registration_service.registration_fact_context", return_value={"attempt_id": 77, "job_id": 91}):
            with self.assertRaisesRegex(RuntimeError, "远端回执中断"):
                failing(self.email)
            unknown = store.list_otp_requests(self.email)[0]
            self.assertEqual((unknown["state"], unknown["submission_state"]), ("cancelled", "result_unknown"))
            self.assertIsNone(store.find_active_otp_request(self.email))
            resumed(self.email)
        self.assertEqual(sessions[0].owner_id, "77")
        self.assertEqual(sessions[1].owner_id, "77")
        self.assertNotEqual(sessions[0].execution_token, sessions[1].execution_token)
        self.assertTrue(all(not session.heartbeat_thread.is_alive() for session in sessions))
        self.assertEqual(store.get_otp_request(unknown["id"])["submission_state"], "result_unknown")

    def test_pg_concurrency_rejects_same_owner_other_execution_and_allows_sibling(self):
        entered, release = threading.Event(), threading.Event()
        remote_calls = []

        @guard.serialize_email_auth
        def holding(email):
            remote_calls.append(email)
            entered.set()
            self.assertTrue(release.wait(10), "等待释放测试执行超时")
            return {"ok": True}

        @guard.serialize_email_auth
        def other(email):
            remote_calls.append(email)
            return {"ok": True}

        with patch("core.registration_service.registration_fact_context", return_value={"attempt_id": 99}), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(holding, self.email)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(store.OtpLeaseBusy):
                    other(self.email)
                self.assertEqual(pool.submit(other, self.sibling_email).result(timeout=5), {"ok": True})
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5), {"ok": True})
        self.assertEqual(remote_calls.count(self.email), 1)
        self.assertEqual(remote_calls.count(self.sibling_email), 1)

    def test_copied_context_in_other_thread_cannot_reenter_original_execution(self):
        with guard.email_auth_session(self.email):
            context = copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(context.run, lambda: guard.serialize_email_auth(lambda email: {"ok": True})(self.email))
                with self.assertRaises(store.OtpLeaseBusy):
                    future.result(timeout=5)

    def test_another_process_observes_existing_auth_lease(self):
        script = """
import sys
from core.email_auth_guard import email_auth_session
from core.storage.email_address_allocations import OtpLeaseBusy
try:
    with email_auth_session(sys.argv[1]):
        raise AssertionError('不得进入远端动作')
except OtpLeaseBusy:
    print('busy')
"""
        with guard.email_auth_session(self.email):
            result = subprocess.run([sys.executable, "-c", script, self.email], env=dict(os.environ), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "busy")

    def test_expired_execution_fence_cannot_offer_late_candidate_or_modify_new_owner(self):
        replacement = None
        try:
            with self.assertRaises(store.StaleOtpFence):
                with guard.email_auth_session(self.email) as session:
                    previous = guard.begin_generation(100)
                    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                    record_store.patch_row(record_store.EMAIL_OTP_REQUESTS, previous["id"], {"lease_expires_at": past})
                    replacement = store.acquire_otp_request(address=self.email, owner_kind=session.owner_kind, owner_id=session.owner_id, execution_token="new-execution", lease_seconds=180)
                    guard.observe_candidate("late-message", {"recipient": self.email})
            self.assertIsNone(store.get_otp_request(replacement["id"]).get("candidate_message_key"))
            self.assertEqual(store.get_otp_request(replacement["id"])["state"], "active")
        finally:
            if replacement:
                store.finish_otp_request(replacement["id"], execution_token=replacement["execution_token"], fence=replacement["fence"], state="cancelled")

    def test_generation_changes_do_not_reuse_old_candidate_or_challenge(self):
        with guard.email_auth_session(self.email):
            first = guard.begin_generation(100)
            guard.observe_candidate("first-message", {"recipient": self.email})
            second = guard.begin_generation(101)
            self.assertNotEqual(first["challenge_id"], second["challenge_id"])
            self.assertGreater(second["send_generation"], first["send_generation"])
            self.assertIsNone(second.get("candidate_message_key"))
            self.assertEqual(second["submission_state"], "not_started")
            self.assertEqual(store.get_otp_request(first["id"])["submission_state"], "offered")

    def test_heartbeat_renews_and_stops_on_exit(self):
        renewed = threading.Event()
        original = store.renew_otp_lease
        sessions = []

        def heartbeat(*args, **kwargs):
            result = original(*args, **kwargs)
            renewed.set()
            return result

        with patch.object(guard, "HEARTBEAT_SECONDS", 0.02), patch.object(store, "renew_otp_lease", side_effect=heartbeat):
            with guard.email_auth_session(self.email) as session:
                sessions.append(session)
                self.assertTrue(renewed.wait(3))
                guard.checkpoint()
        self.assertFalse(sessions[0].heartbeat_thread.is_alive())
        self.assertIsNone(store.find_active_otp_request(self.email))

    def test_heartbeat_loss_prevents_accepting_remote_result_and_cleans_context(self):
        sessions = []
        with patch.object(guard, "HEARTBEAT_SECONDS", 0.01), patch.object(store, "renew_otp_lease", side_effect=store.StaleOtpFence("资格失效")):
            with self.assertRaises(store.StaleOtpFence):
                with guard.email_auth_session(self.email) as session:
                    sessions.append(session)
                    session.heartbeat_thread.join(timeout=3)
                    self.assertFalse(session.heartbeat_thread.is_alive())
                    guard.checkpoint()
        self.assertIsNone(guard.current_session())
        self.assertEqual(store.list_otp_requests(self.email)[0]["submission_state"], "result_unknown")
        self.assertIsNone(store.find_active_otp_request(self.email))

    def test_normal_nested_address_does_not_record_candidate_in_other_mailbox(self):
        @guard.serialize_email_auth
        def ordinary(email):
            self.assertIsNone(guard.current_session())
            self.assertIsNone(guard.observe_candidate("ordinary-message"))
            return {"ok": True}

        with guard.email_auth_session(self.email) as session:
            ordinary("ordinary@example.test")
            self.assertIs(guard.current_session(), session)
            self.assertIsNone(store.get_otp_request(session.row["id"]).get("candidate_message_key"))

    def test_ordinary_target_masks_observer_but_preserves_old_derived_auth_reentry(self):
        with guard.email_auth_session(self.email) as original:
            with guard.email_auth_session("ordinary-target@example.test"):
                self.assertIsNone(guard.current_session())
                with guard.email_auth_session(self.email) as reentered:
                    self.assertIs(reentered, original)
                    self.assertIs(guard.current_session(), original)
                    guard.begin_generation(100)
                    guard.observe_candidate("old-address-reauth", {"recipient": self.email})
                self.assertIsNone(guard.current_session())
            self.assertIs(guard.current_session(), original)
            self.assertEqual(len(store.list_otp_requests(self.email)), 2)

    def test_explicit_observer_handoff_records_worker_candidate_without_cross_thread_reentry(self):
        def fetch(email):
            self.assertIsNotNone(guard.current_session())
            guard.begin_generation(100)
            guard.observe_candidate("worker-message", {"recipient": email})
            return "fixture-result"

        with guard.email_auth_session(self.email) as session, ThreadPoolExecutor(max_workers=1) as pool:
            observed = guard.bind_auth_observer(fetch)
            self.assertEqual(pool.submit(observed, self.email).result(timeout=5), "fixture-result")
            self.assertEqual(session.row["candidate_message_key"], "worker-message")
            self.assertEqual(session.row["submission_state"], "offered")
        self.assertIsNone(guard.current_session())
        self.assertIsNone(guard._OBSERVER_REQUEST.get())

    def test_late_worker_from_superseded_generation_cannot_offer_into_new_challenge(self):
        entered, release = threading.Event(), threading.Event()

        def fetch(email):
            guard.begin_generation(100)
            entered.set()
            self.assertTrue(release.wait(5))
            guard.observe_candidate("old-worker-message", {"recipient": email})

        with guard.email_auth_session(self.email), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(guard.bind_auth_observer(fetch), self.email)
            try:
                self.assertTrue(entered.wait(5))
                current = guard.begin_generation(101)
            finally:
                release.set()
            with self.assertRaises(store.StaleOtpFence):
                future.result(timeout=5)
            guard.checkpoint()
            self.assertIsNone(store.get_otp_request(current["id"]).get("candidate_message_key"))

    def test_candidate_without_provider_message_identity_remains_explicitly_unknown(self):
        with guard.email_auth_session(self.email) as session:
            guard.begin_generation(100)
            observed = guard.observe_candidate("", {"recipient": self.email}, {"message_mapping": "unknown"})
            self.assertEqual(observed["submission_state"], "offered")
            self.assertEqual(observed["candidate_evidence"]["message_mapping"], "unknown")
            self.assertTrue(observed["candidate_message_key"].startswith("unknown:"))
            session.set_result({"ok": True})
        latest = store.list_otp_requests(self.email)[0]
        self.assertEqual(latest["state"], "cancelled")
        self.assertEqual(latest["submission_state"], "result_unknown")

    def test_outer_registration_success_cannot_confirm_failed_nested_codex_generation(self):
        @guard.serialize_email_auth
        def codex(email):
            guard.begin_generation(101)
            guard.observe_candidate("codex-message", {"recipient": email})
            return {"ok": False, "status": "failed"}

        @guard.serialize_email_auth
        def registration(email):
            guard.begin_generation(100)
            guard.observe_candidate("registration-message", {"recipient": email})
            codex(email)
            return {"success": True, "registration_success": True, "postprocess_success": False}

        registration(self.email)
        current = store.list_otp_requests(self.email)[0]
        self.assertEqual(current["candidate_message_key"], "codex-message")
        self.assertEqual(current["state"], "cancelled")
        self.assertEqual(current["submission_state"], "result_unknown")

    def test_observer_callback_cannot_start_after_auth_session_has_closed(self):
        called = Mock()
        with guard.email_auth_session(self.email):
            observed = guard.bind_auth_observer(called)
        with self.assertRaises(store.StaleOtpFence):
            observed()
        called.assert_not_called()
