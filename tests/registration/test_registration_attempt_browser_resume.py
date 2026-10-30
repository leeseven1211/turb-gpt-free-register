"""服务重启后，无账号记录的原 Attempt 仍可找回失败窗口。"""
from contextlib import ExitStack
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


EMAIL = "original@example.test"
ROOT_ID = 31
SOURCE_ID = 32
PARENT_ID = 33
CURRENT_ID = 34
ATTEMPT_ID = 41


class AttemptBrowserResumeTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.reload(importlib.import_module("core.registration.retained_browser"))
        self.source = {
            "id": SOURCE_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "root_job_id": ROOT_ID, "parent_job_id": ROOT_ID,
            "job_type": "registration_resume", "status": "failed", "account_id": None,
            "started_at": "1970-01-01T00:40:00+00:00",
        }
        self.current = {
            "id": CURRENT_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "root_job_id": ROOT_ID, "parent_job_id": PARENT_ID,
            "job_type": "registration_resume", "status": "running", "account_id": None,
        }
        self.binding = {
            "job_id": SOURCE_ID, "root_job_id": ROOT_ID,
            "profile_id": "original-profile", "debugger_address": "127.0.0.1:9222",
            "driver_path": "/unit/original/chromedriver", "otp_after_ts": 125.5,
        }
        self.private = {"password": "unit-original-password", "retained_browser": self.binding}
        self.rows = {SOURCE_ID: self.source, CURRENT_ID: self.current}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.get_job = self.stack.enter_context(patch("core.db.get_job", side_effect=self.rows.get))
        self.get_account = self.stack.enter_context(patch("core.db.get_account", side_effect=AssertionError("无账号恢复不应读取账号")))
        self.get_private = self.stack.enter_context(patch("core.storage.registration.get_private_resume_context", return_value=self.private))
        self.active = self.stack.enter_context(patch("core.registration.service.is_job_worker_active", return_value=False))
        self.roxy_request = self.stack.enter_context(patch("core.browser.roxy.client.RoxyBrowserClient.request", side_effect=AssertionError("恢复关联不应请求 Roxy")))

    def recover(self, **changes):
        values = {"email": EMAIL, "profile_id": None,
                  "facts": {"job_id": CURRENT_ID, "attempt_id": ATTEMPT_ID, "root_job_id": ROOT_ID},
                  **changes}
        return self.module.recover_attempt_failed_browser(**values)

    def assert_blocked(self, callback):
        with self.assertRaisesRegex(RuntimeError, "^request_unknown:") as raised:
            callback()
        for private_value in (EMAIL, "original-profile", "127.0.0.1", "9222", "/unit/original/chromedriver", "unit-original-password"):
            self.assertNotIn(private_value, str(raised.exception))

    def test_empty_process_cache_recovers_pre_account_window_from_private_context(self):
        self.assertFalse(self.module._RETAINED)
        candidate = self.recover(email=" Original@Example.Test ")
        self.assertIsInstance(candidate, self.module.RetainedRoxyBrowser)
        self.assertIsNone(candidate.driver)
        self.assertEqual((candidate.email, candidate.job_id, candidate.attempt_id, candidate.root_job_id),
                         (EMAIL, SOURCE_ID, ATTEMPT_ID, ROOT_ID))
        self.assertEqual(candidate.otp_after_ts, 125.5)
        self.assertEqual(candidate.opened.profile_id, "original-profile")
        self.assertEqual(candidate.opened.debugger_address, "127.0.0.1:9222")
        self.assertEqual(candidate.opened.raw, {"data": {
            "http": "127.0.0.1:9222", "driver": "/unit/original/chromedriver"}})
        self.assertFalse(candidate.opened.created_by_run)
        self.assertFalse(candidate.opened.account_bound)
        self.assertIsNone(candidate.opened.traffic_capture)
        self.get_private.assert_called_once_with(ATTEMPT_ID, email=EMAIL)
        self.get_account.assert_not_called()
        self.roxy_request.assert_not_called()

    def test_saved_source_can_precede_immediate_parent_in_same_attempt_chain(self):
        self.assertNotEqual(self.binding["job_id"], self.current["parent_job_id"])
        self.assertEqual(self.recover().job_id, SOURCE_ID)
        self.assertEqual([call.args[0] for call in self.get_job.call_args_list], [CURRENT_ID, SOURCE_ID])
        self.active.assert_called_once_with(SOURCE_ID)

    def test_source_and_current_email_attempt_root_and_job_type_conflicts_block(self):
        for row, field, value in (
            (self.source, "email", "different@example.test"),
            (self.current, "email", "different@example.test"),
            (self.source, "attempt_id", 42), (self.current, "attempt_id", 42),
            (self.source, "root_job_id", 39), (self.current, "root_job_id", 39),
            (self.source, "job_type", "twofa_retry"), (self.current, "job_type", "twofa_retry"),
            (self.binding, "job_id", 99), (self.binding, "root_job_id", 39),
        ):
            with self.subTest(field=field, value=value):
                original = row[field]
                row[field] = value
                self.assert_blocked(self.recover)
                row[field] = original
        self.assert_blocked(lambda: self.recover(email="different@example.test"))
        self.assert_blocked(lambda: self.recover(facts={
            "job_id": CURRENT_ID, "attempt_id": ATTEMPT_ID, "root_job_id": 39}))

    def test_conflicting_account_or_requested_profile_blocks_saved_window(self):
        self.source["account_id"] = 51
        self.current["account_id"] = 52
        self.assert_blocked(self.recover)
        self.source["account_id"] = 52
        self.assertTrue(self.recover(profile_id="original-profile").opened.account_bound)
        self.assert_blocked(lambda: self.recover(profile_id="different-profile"))

    def test_active_paused_or_nonterminal_source_cannot_be_taken(self):
        self.active.return_value = True
        self.assert_blocked(self.recover)
        self.active.return_value = False
        self.source["debug_state"] = "paused"
        self.assert_blocked(self.recover)
        self.source.pop("debug_state")
        for state in ("running", "queued", "success", "paused"):
            with self.subTest(state=state):
                self.source["status"] = state
                self.assert_blocked(self.recover)

    def test_no_durable_binding_or_direct_root_preserves_normal_open_path(self):
        for binding in (None, {}, "invalid", []):
            with self.subTest(binding=binding):
                self.get_private.return_value = {} if binding == {} else {"retained_browser": binding}
                self.assertIsNone(self.recover())
        self.get_private.reset_mock()
        self.current.pop("parent_job_id")
        self.assertIsNone(self.recover())
        self.get_private.assert_not_called()

    def test_missing_saved_connection_fields_block_instead_of_opening_new_window(self):
        for field in ("profile_id", "debugger_address", "job_id", "root_job_id"):
            with self.subTest(field=field):
                value = self.binding.pop(field)
                self.assert_blocked(self.recover)
                self.binding[field] = value

    def test_unknown_original_mail_time_never_uses_retry_start_time(self):
        for value in (None, "invalid", float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                self.binding["otp_after_ts"] = value
                self.assertIsNone(self.recover().otp_after_ts)

    def test_unreadable_private_or_task_facts_do_not_expose_connection_data(self):
        for dependency in (self.get_job, self.get_private, self.active):
            with self.subTest(dependency=dependency):
                original = dependency.side_effect
                dependency.side_effect = RuntimeError("127.0.0.1:9222 unit-original-password")
                self.assert_blocked(self.recover)
                dependency.side_effect = original
        self.get_private.return_value = None
        self.assert_blocked(self.recover)


class PersistAttemptBrowserResumeTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("core.registration.retained_browser")
        self.driver = SimpleNamespace(_registration_otp_after_ts=125.5)
        self.opened = SimpleNamespace(
            profile_id="original-profile", debugger_address="127.0.0.1:9222",
            raw={"token": "unit-private-token", "data": {
                "driver": "/unit/original/chromedriver", "cookies": "unit-private-cookie",
                "proxy": "unit-private-proxy"}},
        )
        self.facts = {"attempt_id": ATTEMPT_ID, "job_id": SOURCE_ID,
                      "run_id": 71, "execution_id": "unit-execution"}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.save = self.stack.enter_context(patch("core.storage.registration.save_browser_resume_context", create=True))
        self.get_job = self.stack.enter_context(patch("core.db.get_job", side_effect=AssertionError("连接白名单保存不应另读任务")))
        self.request = self.stack.enter_context(patch("core.browser.roxy.client.RoxyBrowserClient.request", side_effect=AssertionError("保存连接不应请求 Roxy")))

    def persist(self, **changes):
        return self.module.persist_browser_resume_context(
            self.driver, self.opened, email=EMAIL, facts={**self.facts, **changes})

    def test_save_only_connection_whitelist_and_original_mail_boundary(self):
        self.assertTrue(self.persist())
        self.save.assert_called_once_with(
            ATTEMPT_ID, email=EMAIL, job_id=SOURCE_ID, run_id=71,
            execution_id="unit-execution", profile_id="original-profile",
            debugger_address="127.0.0.1:9222", driver_path="/unit/original/chromedriver",
            otp_after_ts=125.5,
        )
        self.get_job.assert_not_called()
        self.request.assert_not_called()
        serialized = repr(self.save.call_args)
        for private_value in ("unit-private-token", "unit-private-cookie", "unit-private-proxy"):
            self.assertNotIn(private_value, serialized)

    def test_alias_driver_paths_are_normalized_without_copying_raw_payload(self):
        for field in ("driver", "driverPath", "driver_path"):
            with self.subTest(field=field):
                self.opened.raw["data"] = {field: "/unit/alias-driver", "cookie": "unit-private-cookie"}
                self.assertTrue(self.persist())
                self.assertEqual(self.save.call_args.kwargs["driver_path"], "/unit/alias-driver")
                self.assertNotIn("unit-private-cookie", repr(self.save.call_args))

    def test_missing_driver_and_unknown_mail_boundary_remain_explicitly_unknown(self):
        self.opened.raw = {}
        self.driver = None
        self.assertTrue(self.persist())
        self.assertEqual(self.save.call_args.kwargs["driver_path"], "")
        self.assertIsNone(self.save.call_args.kwargs["otp_after_ts"])

    def test_incomplete_execution_or_browser_identity_does_not_save(self):
        for field in ("attempt_id", "job_id", "run_id", "execution_id"):
            with self.subTest(field=field):
                self.assertFalse(self.persist(**{field: None}))
        for field in ("profile_id", "debugger_address"):
            with self.subTest(field=field):
                original = getattr(self.opened, field)
                setattr(self.opened, field, "")
                self.assertFalse(self.persist())
                setattr(self.opened, field, original)
        self.save.assert_not_called()

    def test_save_failure_preserves_sanitized_original_window_error(self):
        self.save.side_effect = RuntimeError("unit-private-token 127.0.0.1:9222")
        with self.assertRaisesRegex(RuntimeError, "^request_unknown:") as raised:
            self.persist()
        self.assertNotIn("unit-private-token", str(raised.exception))
        self.assertNotIn("127.0.0.1", str(raised.exception))
