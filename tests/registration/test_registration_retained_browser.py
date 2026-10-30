"""失败任务保留的浏览器只交给同一身份、已结束旧 worker 的重跑。"""
import importlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


EMAIL = "original@example.test"
SOURCE_ID = 31
CURRENT_ID = 32
ATTEMPT_ID = 41


class RetainedBrowserTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module("core.registration.retained_browser")
        except ModuleNotFoundError as exc:
            if exc.name != "core.registration.retained_browser":
                raise
            self.fail("尚未实现失败浏览器的同 Attempt 恢复模块")
        self.module = importlib.reload(self.module)
        self.source = {
            "id": SOURCE_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "job_type": "registration", "status": "running",
            "started_at": "1970-01-01T00:02:03+00:00",
        }
        self.current = {
            "id": CURRENT_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "root_job_id": SOURCE_ID, "job_type": "registration_resume", "status": "running",
        }
        self.rows = {SOURCE_ID: self.source, CURRENT_ID: self.current}
        self.driver = SimpleNamespace(
            _registration_otp_after_ts=125.5,
            _browser_submission_receipt=object(),
            close=Mock(), quit=Mock(), execute_script=Mock(),
        )
        self.opened = SimpleNamespace(profile_id="original-profile", created_by_run=True)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.get_job = self.stack.enter_context(patch("core.db.get_job", side_effect=lambda job_id: self.rows.get(job_id)))
        self.active = self.stack.enter_context(patch("core.registration.service.is_job_worker_active", return_value=False, create=True))

    def source_facts(self, **changes):
        return {"job_id": SOURCE_ID, "attempt_id": ATTEMPT_ID, **changes}

    def current_facts(self, **changes):
        return {"job_id": CURRENT_ID, "attempt_id": ATTEMPT_ID, **changes}

    def retain(self, **kwargs):
        values = {"email": EMAIL, "facts": self.source_facts(), **kwargs}
        return self.module.retain_failed_browser(self.driver, self.opened, **values)

    def take(self, **kwargs):
        values = {"email": EMAIL, "profile_id": "original-profile", "facts": self.current_facts(), **kwargs}
        return self.module.take_failed_browser(**values)

    def prepare(self):
        self.assertTrue(self.retain())
        self.source["status"] = "failed"

    def assert_blocked(self, callback):
        with self.assertRaisesRegex(RuntimeError, "^request_unknown:") as error:
            callback()
        message = str(error.exception)
        for private_value in (EMAIL, "original-profile", "127.0.0.1", "9222"):
            self.assertNotIn(private_value, message)

    def test_same_attempt_pre_account_retry_consumes_original_driver_once(self):
        receipt = self.driver._browser_submission_receipt
        self.prepare()
        candidate = self.take()
        self.assertIsInstance(candidate, self.module.RetainedRoxyBrowser)
        self.assertIs(candidate.driver, self.driver)
        self.assertIs(candidate.opened, self.opened)
        self.assertEqual((candidate.email, candidate.job_id, candidate.attempt_id, candidate.root_job_id),
                         (EMAIL, SOURCE_ID, ATTEMPT_ID, SOURCE_ID))
        self.assertEqual(candidate.otp_after_ts, 125.5)
        self.assertIs(self.driver._browser_submission_receipt, receipt)
        self.assertIsNone(self.take())
        self.driver.close.assert_not_called()
        self.driver.quit.assert_not_called()
        self.driver.execute_script.assert_not_called()

    def test_matching_email_is_normalized_without_changing_identity(self):
        self.prepare()
        self.assertIs(self.take(email=" Original@Example.Test ").driver, self.driver)

    def test_registration_retry_can_reuse_without_any_account_binding(self):
        self.prepare()
        self.current["job_type"] = "registration"
        self.assertNotIn("account_id", self.source)
        self.assertIs(self.take(profile_id=None).opened, self.opened)

    def test_child_source_preserves_original_root_chain(self):
        self.source["root_job_id"] = 19
        self.current["root_job_id"] = 19
        self.prepare()
        self.assertEqual(self.take().root_job_id, 19)

    def test_attempt_alias_is_accepted_in_context_and_job_projection(self):
        self.source["registration_attempt_id"] = self.source.pop("attempt_id")
        self.current["registration_attempt_id"] = self.current.pop("attempt_id")
        self.assertTrue(self.retain(facts={"job_id": SOURCE_ID, "registration_attempt_id": ATTEMPT_ID}))
        self.source["status"] = "failed"
        candidate = self.take(facts={"job_id": CURRENT_ID, "registration_attempt_id": ATTEMPT_ID})
        self.assertIs(candidate.driver, self.driver)

    def test_no_candidate_is_the_only_normal_missing_result(self):
        self.get_job.side_effect = RuntimeError("数据库读取失败")
        self.assertIsNone(self.take())

    def test_source_email_changed_after_failure_blocks_claim_without_consuming(self):
        self.prepare()
        self.source["email"] = "different@example.test"
        self.assert_blocked(self.take)
        self.source["email"] = EMAIL
        self.assertIs(self.take().driver, self.driver)

    def test_current_email_changed_blocks_claim(self):
        self.prepare()
        self.current["email"] = "different@example.test"
        self.assert_blocked(self.take)

    def test_requested_email_must_match_retained_identity(self):
        self.prepare()
        self.assert_blocked(lambda: self.take(email="different@example.test"))

    def test_source_attempt_changed_blocks_claim(self):
        self.prepare()
        self.source["attempt_id"] = 42
        self.assert_blocked(self.take)

    def test_current_attempt_changed_blocks_claim(self):
        self.prepare()
        self.current["attempt_id"] = 42
        self.assert_blocked(self.take)

    def test_conflicting_attempt_aliases_cannot_override_original_attempt(self):
        self.prepare()
        self.assert_blocked(lambda: self.take(facts=self.current_facts(registration_attempt_id=42)))

    def test_conflicting_attempt_aliases_cannot_hide_an_existing_candidate(self):
        self.prepare()
        self.assert_blocked(lambda: self.take(facts=self.current_facts(attempt_id=42, registration_attempt_id=ATTEMPT_ID)))

    def test_source_account_binding_and_current_binding_must_agree(self):
        self.source["account_id"] = 51
        self.current["account_id"] = 52
        self.prepare()
        self.assert_blocked(self.take)

    def test_current_root_chain_changed_blocks_claim(self):
        self.prepare()
        self.current["root_job_id"] = 33
        self.assert_blocked(self.take)

    def test_source_root_chain_changed_blocks_claim(self):
        self.prepare()
        self.source["root_job_id"] = 33
        self.assert_blocked(self.take)

    def test_other_profile_binding_blocks_claim(self):
        self.prepare()
        self.assert_blocked(lambda: self.take(profile_id="different-profile"))

    def test_nonregistration_current_job_blocks_claim(self):
        self.prepare()
        self.current["job_type"] = "codex_retry"
        self.assert_blocked(self.take)

    def test_old_worker_blocks_claim_even_after_database_says_failed(self):
        self.prepare()
        self.active.return_value = True
        self.assert_blocked(self.take)
        self.active.return_value = False
        self.assertIs(self.take().driver, self.driver)

    def test_worker_state_read_failure_blocks_claim(self):
        self.prepare()
        self.active.side_effect = RuntimeError("worker状态读取失败")
        self.assert_blocked(self.take)

    def test_running_or_paused_source_cannot_be_claimed(self):
        for status in ("running", "paused", "queued", "success"):
            with self.subTest(status=status):
                self.prepare()
                self.source["status"] = status
                self.assert_blocked(self.take)

    def test_debug_paused_source_cannot_be_claimed(self):
        self.prepare()
        self.source["debug_state"] = "paused"
        self.assert_blocked(self.take)

    def test_failed_terminal_states_are_claimable(self):
        for status in ("failed", "partial_success", "request_unknown", "cancelled", "stopped"):
            with self.subTest(status=status):
                self.prepare()
                self.source["status"] = status
                self.assertIs(self.take().driver, self.driver)

    def test_missing_source_or_current_row_blocks_claim(self):
        for job_id in (SOURCE_ID, CURRENT_ID):
            with self.subTest(job_id=job_id):
                self.prepare()
                missing = self.rows.pop(job_id)
                self.assert_blocked(self.take)
                self.rows[job_id] = missing

    def test_database_read_failure_is_not_treated_as_missing(self):
        self.prepare()
        self.get_job.side_effect = RuntimeError("私有连接信息不能出现在错误输出")
        self.assert_blocked(self.take)

    def test_simultaneous_claims_cannot_share_the_same_original_driver(self):
        self.prepare()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.take(), range(2)))
        self.assertEqual(sum(candidate is not None for candidate in results), 1)
        self.assertIs(next(candidate for candidate in results if candidate is not None).driver, self.driver)

    def test_source_metadata_fallback_preserves_original_mail_time(self):
        del self.driver._registration_otp_after_ts
        self.prepare()
        self.assertEqual(self.take().otp_after_ts, 123.0)

    def test_datetime_start_metadata_preserves_original_mail_time(self):
        del self.driver._registration_otp_after_ts
        self.source["started_at"] = datetime(1970, 1, 1, 0, 2, 3, tzinfo=timezone.utc)
        self.prepare()
        self.assertEqual(self.take().otp_after_ts, 123.0)

    def test_invalid_original_mail_time_does_not_invent_a_new_timestamp(self):
        del self.driver._registration_otp_after_ts
        self.source["started_at"] = "不可解析"
        self.prepare()
        self.assertIsNone(self.take().otp_after_ts)

    def test_explicit_unknown_original_mail_time_never_uses_job_start_time(self):
        self.driver._registration_otp_after_ts = None
        self.prepare()
        self.assertIsNone(self.take().otp_after_ts)

    def test_retain_without_original_identity_context_does_not_create_candidate(self):
        for facts in ({}, {"job_id": SOURCE_ID}, {"attempt_id": ATTEMPT_ID}):
            with self.subTest(facts=facts):
                self.assertFalse(self.retain(facts=facts))
        self.assertIsNone(self.take())

    def test_retain_rejects_source_identity_mismatch(self):
        for field, value in (("email", "different@example.test"), ("attempt_id", 42)):
            with self.subTest(field=field):
                original = self.source[field]
                self.source[field] = value
                self.assertFalse(self.retain())
                self.source[field] = original
        self.assertIsNone(self.take())

    def test_cache_overflow_forgets_oldest_handle_without_closing_browser(self):
        for offset in range(129):
            job_id = 1000 + offset
            attempt_id = 2000 + offset
            self.rows[job_id] = {
                "id": job_id, "email": EMAIL, "attempt_id": attempt_id,
                "job_type": "registration", "status": "failed",
            }
            self.assertTrue(self.retain(facts={"job_id": job_id, "attempt_id": attempt_id}))
        self.current.update(attempt_id=2000, root_job_id=1000)
        self.assertIsNone(self.take(facts=self.current_facts(attempt_id=2000)))
        self.current.update(attempt_id=2128, root_job_id=1128)
        self.assertIs(self.take(facts=self.current_facts(attempt_id=2128)).driver, self.driver)
        self.driver.close.assert_not_called()
        self.driver.quit.assert_not_called()


class BoundRetainedBrowserTests(unittest.TestCase):
    """进程缓存丢失后，只从已核验的账号绑定恢复原窗口连接。"""

    def setUp(self):
        self.module = importlib.reload(importlib.import_module("core.registration.retained_browser"))
        self.source = {
            "id": SOURCE_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "job_type": "registration", "status": "failed", "account_id": 51,
            "started_at": "1970-01-01T00:02:03+00:00",
        }
        self.current = {
            "id": CURRENT_ID, "email": EMAIL, "attempt_id": ATTEMPT_ID,
            "root_job_id": SOURCE_ID, "parent_job_id": SOURCE_ID,
            "job_type": "registration_resume", "status": "running", "account_id": 51,
        }
        self.binding = {
            "profile_id": "original-profile", "retained": True,
            "open_result": {"code": 0, "data": {
                "http": "http://127.0.0.1:9222", "driver": "/original/chromedriver",
            }},
        }
        self.account = {"id": 51, "email": EMAIL, "extra_json": {"roxybrowser": self.binding}}
        self.rows = {SOURCE_ID: self.source, CURRENT_ID: self.current}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.get_job = self.stack.enter_context(patch("core.db.get_job", side_effect=lambda job_id: self.rows.get(job_id)))
        self.get_account = self.stack.enter_context(patch("core.db.get_account", return_value=self.account))
        self.active = self.stack.enter_context(patch("core.registration.service.is_job_worker_active", return_value=False, create=True))
        self.stack.enter_context(patch("core.browser.roxy.client.RoxyBrowserClient.request", side_effect=AssertionError("恢复连接元数据不应请求 Roxy")))

    def recover(self, **kwargs):
        method = getattr(self.module, "recover_bound_failed_browser", None)
        self.assertIsNotNone(method, "尚未实现保留账号窗口的持久连接恢复")
        values = {"email": EMAIL, "profile_id": "original-profile",
                  "facts": {"job_id": CURRENT_ID, "attempt_id": ATTEMPT_ID}, **kwargs}
        return method(**values)

    def assert_blocked(self, callback):
        with self.assertRaisesRegex(RuntimeError, "^request_unknown:") as error:
            callback()
        message = str(error.exception)
        for private_value in (EMAIL, "original-profile", "127.0.0.1", "9222", "/original/chromedriver"):
            self.assertNotIn(private_value, message)

    def test_durable_binding_recovers_original_debugger_without_driver_or_new_profile(self):
        candidate = self.recover(email=" Original@Example.Test ")
        self.assertIsInstance(candidate, self.module.RetainedRoxyBrowser)
        self.assertIsNone(candidate.driver)
        self.assertEqual((candidate.email, candidate.job_id, candidate.attempt_id, candidate.root_job_id),
                         (EMAIL, SOURCE_ID, ATTEMPT_ID, SOURCE_ID))
        self.assertEqual(candidate.otp_after_ts, 123.0)
        self.assertEqual(candidate.opened.profile_id, "original-profile")
        self.assertEqual(candidate.opened.debugger_address, "127.0.0.1:9222")
        self.assertEqual(candidate.opened.raw["data"]["driver"], "/original/chromedriver")
        self.assertFalse(candidate.opened.created_by_run)
        self.assertTrue(candidate.opened.account_bound)
        self.assertIsNone(candidate.opened.traffic_capture)

    def test_retry_source_start_time_cannot_replace_original_mail_time(self):
        self.source.update(parent_job_id=19, root_job_id=19)
        self.current["root_job_id"] = 19
        self.assertIsNone(self.recover().otp_after_ts)

    def test_source_current_and_account_identity_conflicts_stop_recovery(self):
        for row, field, value in (
            (self.source, "email", "different@example.test"),
            (self.current, "email", "different@example.test"),
            (self.account, "email", "different@example.test"),
            (self.source, "attempt_id", 42),
            (self.current, "attempt_id", 42),
            (self.source, "root_job_id", 39),
            (self.current, "root_job_id", 39),
            (self.source, "account_id", 52),
            (self.current, "account_id", 52),
            (self.account, "id", 52),
        ):
            with self.subTest(field=field, value=value):
                original = row.get(field)
                row[field] = value
                self.assert_blocked(self.recover)
                if original is None:
                    row.pop(field)
                else:
                    row[field] = original

    def test_original_worker_or_nonterminal_source_cannot_be_reconnected(self):
        self.active.return_value = True
        self.assert_blocked(self.recover)
        self.active.return_value = False
        self.source["debug_state"] = "paused"
        self.assert_blocked(self.recover)
        self.source.pop("debug_state")
        for status in ("running", "queued", "success", "paused"):
            with self.subTest(status=status):
                self.source["status"] = status
                self.assert_blocked(self.recover)

    def test_direct_run_or_missing_profile_never_uses_durable_connection_fallback(self):
        self.current.pop("parent_job_id")
        self.assertIsNone(self.recover())
        self.current["parent_job_id"] = SOURCE_ID
        self.assertIsNone(self.recover(profile_id=None))
        self.assertIsNone(self.recover(profile_id=""))

    def test_missing_or_unretained_connection_metadata_preserves_normal_open_path(self):
        self.binding.pop("open_result")
        self.assertIsNone(self.recover())
        self.binding["open_result"] = {"data": {"driver": "/original/chromedriver"}}
        self.assertIsNone(self.recover())
        self.binding["open_result"] = {"data": {"http": "127.0.0.1:9222"}}
        for retained in (False, 0, "false", "off"):
            with self.subTest(retained=retained):
                self.binding["retained"] = retained
                self.assertIsNone(self.recover())

    def test_requested_profile_must_equal_durable_binding(self):
        self.assert_blocked(lambda: self.recover(profile_id="another-profile"))
        self.binding["profile_id"] = "another-profile"
        self.assert_blocked(self.recover)

    def test_unreadable_or_missing_source_and_account_facts_stop_recovery(self):
        for dependency in (self.get_job, self.get_account, self.active):
            with self.subTest(dependency=dependency):
                original = dependency.side_effect
                dependency.side_effect = RuntimeError("连接信息 127.0.0.1:9222 不应出现在用户报错")
                self.assert_blocked(self.recover)
                dependency.side_effect = original
        self.rows.pop(SOURCE_ID)
        self.assert_blocked(self.recover)
        self.rows[SOURCE_ID] = self.source
        self.get_account.return_value = None
        self.assert_blocked(self.recover)

    def test_conflicting_attempt_aliases_or_account_presence_stop_recovery(self):
        self.assert_blocked(lambda: self.recover(facts={
            "job_id": CURRENT_ID, "attempt_id": ATTEMPT_ID, "registration_attempt_id": 42,
        }))
        self.source.pop("account_id")
        self.assert_blocked(self.recover)
