"""付费邮箱模拟 API 与隔离 PostgreSQL 恢复验收，不调用真实供应商。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests

from config import email as cfg
from core import email_provider
from core import mailcode_client as mailcode
from core import xigua_client as xigua
from core.auth_challenge import AuthCancelledError
from core.mailbox_wait import use_budget
from core.registration.state_machine import CancellationRequested, StageBudget, StageTimeout
from core.storage import mail_provider_orders as orders
from tests.support_pg import PostgresTestCase


def response(data, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = data
    return result


def mailcode_order():
    return {"order_id": "order-1", "status": "COMPLETED", "items": [
        {"mailbox_id": "mailbox-1", "email": "paid@example.test", "status": "ACTIVE"}]}


def codes(records=None, cursor="7", channel="READY", has_more=False):
    return {"records": records or [], "next_sequence": cursor, "channel_status": channel, "has_more": has_more}


class OrderLockQueueTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(orders, "init"))
        self.enterContext(patch.object(orders.postgres_store, "database_url", return_value="fixture-pool"))
        self.enterContext(patch.dict(orders._LOCK_SLOTS, {}, clear=True))

    def test_sixteen_tasks_queue_outside_limited_pool(self):
        guard, seen_all, release = threading.Lock(), threading.Event(), threading.Event()
        seen, active, maximum, checkouts = set(), 0, 0, 0

        class Slots(threading.BoundedSemaphore):
            def acquire(self, *args, **kwargs):
                with guard:
                    seen.add(threading.get_ident())
                    if len(seen) == 16:
                        seen_all.set()
                return super().acquire(*args, **kwargs)

        orders._LOCK_SLOTS["fixture-pool"] = Slots(2)

        @contextmanager
        def limited_pool(**_kwargs):
            nonlocal active, maximum, checkouts
            with guard:
                active += 1
                maximum, checkouts = max(maximum, active), checkouts + 1
                if active > 2:
                    raise AssertionError("不应进入连接池等待或触发 PoolTimeout")
            cursor = SimpleNamespace(execute=lambda *_args: None, fetchone=lambda: {"acquired": True})
            try:
                yield SimpleNamespace(cursor=lambda: nullcontext(cursor))
            finally:
                with guard:
                    active -= 1

        def worker(number):
            with orders.order_lock("mailcode", str(number)):
                if not release.wait(3):
                    raise AssertionError("测试未释放模拟供应商慢请求")
                return number

        with patch.object(orders.postgres_store, "connect", side_effect=limited_pool):
            with ThreadPoolExecutor(max_workers=16) as pool:
                futures = [pool.submit(worker, number) for number in range(16)]
                try:
                    self.assertTrue(seen_all.wait(2))
                    with guard:
                        self.assertEqual(checkouts, 2)
                finally:
                    release.set()
                self.assertEqual([future.result(timeout=3) for future in futures], list(range(16)))
        self.assertEqual(maximum, 2)
        self.assertEqual(checkouts, 16)

    def test_pool_queue_cancellation_never_borrows_connection_or_leaks_slot(self):
        slots, cancelled = threading.BoundedSemaphore(1), [False]
        orders._LOCK_SLOTS["fixture-pool"] = slots
        slots.acquire()
        with patch.object(orders.postgres_store, "connect") as connect, use_budget(StageBudget.start(5, cancel=lambda: cancelled[0])), patch("core.mailbox_wait.bounded_sleep", side_effect=lambda _seconds: cancelled.__setitem__(0, True)):
            with self.assertRaises(CancellationRequested):
                with orders.order_lock("mailcode", "cancelled"):
                    self.fail("取消后不能开始供应商请求")
        connect.assert_not_called()
        slots.release()
        self.assertTrue(slots.acquire(blocking=False))
        slots.release()

    def test_pool_queue_respects_shared_deadline(self):
        slots, clock = threading.BoundedSemaphore(1), [0.0]
        orders._LOCK_SLOTS["fixture-pool"] = slots
        slots.acquire()
        with patch.object(orders.postgres_store, "connect") as connect, use_budget(StageBudget.start(1, clock=lambda: clock[0])), patch("core.mailbox_wait.bounded_sleep", side_effect=lambda _seconds: clock.__setitem__(0, 2.0)):
            with self.assertRaises(StageTimeout):
                with orders.order_lock("mailcode", "expired"):
                    self.fail("预算结束后不能开始供应商请求")
        connect.assert_not_called()
        slots.release()

    def test_slot_released_when_database_checkout_fails(self):
        slots = threading.BoundedSemaphore(1)
        orders._LOCK_SLOTS["fixture-pool"] = slots
        with patch.object(orders.postgres_store, "connect", side_effect=RuntimeError("模拟数据库不可用")):
            with self.assertRaisesRegex(RuntimeError, "模拟数据库不可用"):
                with orders.order_lock("mailcode", "failure"):
                    self.fail("连接失败不能执行订单")
        self.assertTrue(slots.acquire(blocking=False))
        slots.release()


class PaidMailProviderTests(PostgresTestCase):
    def setUp(self):
        mailcode._CONTEXT_CACHE.clear()
        xigua._CACHE.clear()
        email_provider._EMAIL_SOURCE_HINTS.clear()
        self.addCleanup(email_provider._EMAIL_SOURCE_HINTS.clear)
        settings = {"MAILCODE_API_KEY": "private-test-key", "MAILCODE_PRODUCT_ID": "product-test",
                    "MAILCODE_REQUEST_TIMEOUT": 20, "MAILCODE_CHANNEL_WAIT_SECONDS": 2,
                    "XIGUA_API_BASE": "https://xigua.example.test", "XIGUA_API_KEY": "private-test-key",
                    "XIGUA_OFFER_ID": "offer-test", "XIGUA_REQUEST_TIMEOUT": 20,
                    "XIGUA_POLL_ATTEMPTS": 4, "XIGUA_POLL_INTERVAL": 1,
                    "OTP_MAX_WAIT": 3, "OTP_SETTLE_SECONDS": 0, "USE_EMAIL_SERVICE": True}
        for key, value in settings.items():
            self.enterContext(patch.object(cfg, key, value))
        self.http = self.enterContext(patch.object(requests, "request", side_effect=AssertionError("禁止真实供应商请求")))
        self.enterContext(patch.object(mailcode, "bounded_sleep"))
        self.enterContext(patch.object(xigua, "bounded_sleep"))

    def buy_mailcode(self, owner="root-1"):
        self.http.side_effect = [response({"data": mailcode_order()}), response({"data": codes()})]
        return mailcode.pick_account(owner_kind="registration_root", owner_id=owner, acquisition_id=owner)

    def buy_xigua(self, owner="root-2"):
        self.http.side_effect = lambda method, *_args, **_kwargs: response({"data": []}) if method == "GET" else response({"data": {"email": "xigua@example.test", "id": "xigua-order"}})
        return xigua.pick_account(owner_kind="registration_root", owner_id=owner, acquisition_id=owner)

    def test_mailcode_purchase_and_restart_reuse_exact_original_order(self):
        account = self.buy_mailcode()
        mailcode._CONTEXT_CACHE.clear()
        self.http.reset_mock(side_effect=True)
        self.http.side_effect = AssertionError("恢复禁止重购")
        with patch.object(cfg, "MAILCODE_PRODUCT_ID", "another-product"):
            recovered = mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1")
        self.assertEqual((recovered.email, recovered.order_id, recovered.next_sequence), (account.email, "order-1", "7"))
        self.http.assert_not_called()
        row = orders.get_by_owner("mailcode", "registration_root", "root-1")
        self.assertEqual(row["request_json"], {"product_id": "product-test", "count": 1})
        self.assertNotIn("private-test-key", str(row))

    def test_mailcode_unknown_purchase_restart_keeps_original_idempotency(self):
        self.http.side_effect = requests.Timeout("private-test-key")
        with self.assertRaises(mailcode.MailCodeError) as caught:
            mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1")
        self.assertNotIn("private-test-key", str(caught.exception))
        first = self.http.call_args_list[0].kwargs
        row = orders.get_by_owner("mailcode", "registration_root", "root-1")
        self.assertEqual(row["status"], "request_unknown")
        self.buy_mailcode()
        resumed = self.http.call_args_list[-2].kwargs
        self.assertEqual(first["headers"]["Idempotency-Key"], resumed["headers"]["Idempotency-Key"])
        self.assertEqual(first["json"], resumed["json"])

    def test_channel_failure_preserves_purchased_mailbox_without_repurchase(self):
        self.http.side_effect = [response({"data": mailcode_order()}), response({"error": {"code": "UNAUTHORIZED"}}, 401)]
        with self.assertRaises(mailcode.MailCodeError):
            mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1")
        self.http.reset_mock()
        self.http.side_effect = [response({"data": codes(cursor="9")})]
        account = mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1")
        self.assertEqual(account.next_sequence, "9")
        self.assertEqual(self.http.call_args.args[0], "GET")
        self.assertEqual(self.http.call_count, 1)

    def test_mailcode_concurrent_same_owner_only_buys_once(self):
        self.http.side_effect = [response({"data": mailcode_order()}), response({"data": codes()})]
        def acquire(_):
            return mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1").email
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(acquire, range(2)))
        self.assertEqual(values, ["paid@example.test"] * 2)
        self.assertEqual(sum(call.args[0] == "POST" for call in self.http.call_args_list), 1)

    def test_mailcode_cursor_and_leading_zero_survive_restart(self):
        account = self.buy_mailcode()
        now = time.time()
        self.http.side_effect = [response({"data": codes([
            {"code": "012345", "received_at": now * 1000, "expires_at": (now + 120) * 1000, "sequence": "8"}], cursor="8")})]
        self.assertEqual(mailcode.fetch_latest_otp(account.email, after_ts=now - 1, settle_seconds=0), "012345")
        mailcode._CONTEXT_CACHE.clear()
        self.assertEqual(mailcode.restore_account_context(account.email).next_sequence, "8")
        self.assertEqual(self.http.call_args.kwargs["params"]["after_sequence"], "7")

    def test_mailcode_old_and_expired_codes_are_not_returned(self):
        account = self.buy_mailcode()
        now = time.time()
        self.http.side_effect = [response({"data": codes([
            {"code": "123456", "received_at": (now - 30) * 1000, "sequence": "8"},
            {"code": "234567", "received_at": now * 1000, "expires_at": (now - 1) * 1000, "sequence": "9"}], cursor="9")})]
        with self.assertRaises(mailcode.MailCodeError):
            mailcode.fetch_latest_otp(account.email, after_ts=now - 1, max_wait=0)

    def interrupt_mailcode_candidate(self, account, received, *, expires=None):
        self.http.side_effect = [response({"data": codes([
            {"code": "012345", "received_at": received * 1000,
             "expires_at": (received + 120 if expires is None else expires) * 1000,
             "sequence": "8"}], cursor="8")})]
        with patch.object(mailcode, "bounded_sleep", side_effect=AuthCancelledError("模拟进程中断")):
            with self.assertRaises(AuthCancelledError):
                mailcode.fetch_latest_otp(account.email, after_ts=received - 1, settle_seconds=5)

    def test_mailcode_pending_candidate_and_cursor_restore_after_interruption(self):
        account = self.buy_mailcode()
        clock = [time.time()]
        with patch.object(mailcode, "time", SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)):
            self.interrupt_mailcode_candidate(account, clock[0])
            private = orders.get_by_owner("mailcode", "registration_root", "root-1")["private_json"]
            self.assertEqual((private["next_sequence"], private["otp_candidate"]["delivery_status"]), ("8", "pending"))
            mailcode._CONTEXT_CACHE.clear()
            clock[0] += 6
            self.http.side_effect = [response({"data": codes(cursor="8")})]
            self.assertEqual(mailcode.fetch_latest_otp(account.email, after_ts=clock[0] - 7), "012345")
        private = orders.get_by_owner("mailcode", "registration_root", "root-1")["private_json"]
        self.assertEqual(private["otp_candidate"]["delivery_status"], "returned")
        self.assertNotIn("012345", repr(mailcode.restore_account_context(account.email)))
        self.assertEqual(self.http.call_args.kwargs["params"]["after_sequence"], "8")

    def test_mailcode_returned_candidate_is_reentrant_only_for_same_challenge(self):
        account = self.buy_mailcode()
        now = time.time()
        self.http.side_effect = [response({"data": codes([
            {"code": "012345", "received_at": now * 1000, "expires_at": (now + 120) * 1000, "sequence": "8"}], cursor="8")})]
        self.assertEqual(mailcode.fetch_latest_otp(account.email, after_ts=now - 1, settle_seconds=0), "012345")
        mailcode._CONTEXT_CACHE.clear()
        self.http.side_effect = [response({"data": codes(cursor="8")}), response({"data": codes(cursor="8")})]
        self.assertEqual(mailcode.fetch_latest_otp(account.email, after_ts=now - 1, max_wait=0), "012345")
        with self.assertRaises(mailcode.MailCodeError):
            mailcode.fetch_latest_otp(account.email, after_ts=now - 2, max_wait=0)

    def test_mailcode_restart_discards_expired_pending_candidate(self):
        account = self.buy_mailcode()
        clock = [time.time()]
        with patch.object(mailcode, "time", SimpleNamespace(time=lambda: clock[0], monotonic=time.monotonic)):
            self.interrupt_mailcode_candidate(account, clock[0], expires=clock[0] + 3)
            clock[0] += 6
            self.http.side_effect = [response({"data": codes(cursor="8")})]
            with self.assertRaises(mailcode.MailCodeError):
                mailcode.fetch_latest_otp(account.email, after_ts=clock[0] - 7, max_wait=0)
        private = orders.get_by_owner("mailcode", "registration_root", "root-1")["private_json"]
        self.assertIsNone(private["otp_candidate"])

    def test_mailcode_restored_candidate_does_not_hide_newer_record(self):
        account = self.buy_mailcode()
        now = time.time()
        self.interrupt_mailcode_candidate(account, now)
        self.http.side_effect = [response({"data": codes([
            {"code": "654321", "received_at": (now + 1) * 1000, "expires_at": (now + 120) * 1000, "sequence": "9"}], cursor="9")})]
        self.assertEqual(mailcode.fetch_latest_otp(account.email, after_ts=now - 1, settle_seconds=0), "654321")
        private = orders.get_by_owner("mailcode", "registration_root", "root-1")["private_json"]
        self.assertEqual(private["next_sequence"], "9")
        self.assertEqual(private["otp_candidate"]["sequence"], 9)

    def test_xigua_unknown_purchase_restart_reuses_key_and_original_offer(self):
        self.http.side_effect = requests.Timeout("private-test-key")
        with self.assertRaises(xigua.XiguaError) as caught:
            xigua.pick_account(owner_kind="registration_root", owner_id="root-2", acquisition_id="root-2")
        self.assertNotIn("private-test-key", str(caught.exception))
        first = self.http.call_args.kwargs
        with patch.object(cfg, "XIGUA_OFFER_ID", "different-offer"):
            self.buy_xigua()
        self.assertEqual(first["headers"]["Idempotency-Key"], self.http.call_args.kwargs["headers"]["Idempotency-Key"])
        self.assertEqual(self.http.call_args.kwargs["json"], {"offer_id": "offer-test"})

    def test_xigua_unknown_purchase_reconciles_only_matching_idempotency_key(self):
        self.http.side_effect = requests.Timeout()
        with self.assertRaises(xigua.XiguaError):
            xigua.pick_account(owner_kind="registration_root", owner_id="root-2", acquisition_id="root-2")
        row = orders.get_by_owner("xigua", "registration_root", "root-2")
        self.http.reset_mock()
        self.http.side_effect = [response({"items": [
            {"email": "wrong@example.test", "id": "wrong-order", "idempotency_key": "other-key"},
            {"email": "xigua@example.test", "id": "xigua-order", "idempotency_key": row["idempotency_key"]}]})]
        account = xigua.pick_account(owner_kind="registration_root", owner_id="root-2", acquisition_id="root-2")
        self.assertEqual((account.email, account.order_id), ("xigua@example.test", "xigua-order"))
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(self.http.call_args.args[0], "GET")

    def test_xigua_release_and_restart_keep_original_order(self):
        account = self.buy_xigua()
        self.http.reset_mock(side_effect=True)
        self.http.side_effect = AssertionError("失败禁止取消或重购")
        xigua.release_account(account.email, status="failed")
        xigua._CACHE.clear()
        self.assertEqual(xigua.restore_account_context(account.email).order_id, "xigua-order")
        self.assertEqual(xigua.pick_account(owner_kind="registration_root", owner_id="root-2", acquisition_id="root-2").email, account.email)
        self.http.assert_not_called()

    def test_xigua_confirmed_code_and_duplicate_receipt_survive_restart(self):
        account = self.buy_xigua()
        self.http.side_effect = None
        self.http.return_value = response({"data": {"verification_code": "012345", "received_at": time.time()}})
        self.assertEqual(xigua.fetch_latest_otp(account.email, after_ts=1, settle_seconds=0), "012345")
        xigua._CACHE.clear()
        with self.assertRaises(xigua.XiguaError):
            xigua.fetch_latest_otp(account.email, after_ts=1, settle_seconds=0)

    def test_provider_source_and_retry_restore_survive_cache_loss(self):
        account = self.buy_mailcode()
        email_provider._EMAIL_SOURCE_HINTS.clear()
        mailcode._CONTEXT_CACHE.clear()
        self.assertEqual(email_provider.resolve_email_source(account.email, fallback=False), "mailcode")
        self.assertEqual(email_provider.restore_email_context(account.email, source="mailcode"), "mailcode")

    def test_unknown_email_restore_never_lists_supplier_or_purchases(self):
        self.http.reset_mock(side_effect=True)
        with self.assertRaises(xigua.XiguaError):
            xigua.restore_account_context("missing@example.test")
        with self.assertRaises(mailcode.MailCodeError):
            mailcode.restore_account_context("missing@example.test")
        self.http.assert_not_called()

    def test_supplier_identity_change_does_not_repurchase(self):
        self.buy_mailcode()
        self.http.reset_mock(side_effect=True)
        with patch.object(cfg, "MAILCODE_API_KEY", "other-key"):
            with self.assertRaisesRegex(RuntimeError, "身份"):
                mailcode.pick_account(owner_kind="registration_root", owner_id="root-1", acquisition_id="root-1")
        self.http.assert_not_called()

    def test_same_acquisition_cannot_be_rebound_to_other_owner(self):
        self.buy_mailcode()
        self.http.reset_mock(side_effect=True)
        with self.assertRaises(Exception):
            mailcode.pick_account(owner_kind="registration_root", owner_id="other", acquisition_id="root-1")
        self.http.assert_not_called()

    def test_provider_paid_failure_never_falls_back_to_other_provider(self):
        with patch.object(cfg, "EMAIL_SOURCE", "mailcode,outlook"), patch.object(mailcode, "pick_account", side_effect=mailcode.MailCodeError("暂时故障")), patch("core.outlook_client.pick_account") as outlook:
            with self.assertRaises(mailcode.MailCodeError):
                email_provider.acquire_email(owner_kind="cli", owner_id="one", acquisition_id="one")
        outlook.assert_not_called()
