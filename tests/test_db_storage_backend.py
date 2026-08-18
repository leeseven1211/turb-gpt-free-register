# -*- coding: utf-8 -*-
"""db.py 换到行级存储之后的行为回归。

覆盖三件改造前做不到、且直接对应过真实故障的事：
  1. insert_account 把账号与邮箱池写在同一个事务里
  2. 三个 claim_* 跨连接互斥，且超时能回收
  3. 单字段更新只写变化的那一行，不再重写整个集合
"""
import threading
import unittest
from datetime import datetime, timedelta

from core import db, record_store as rs
from core.record_store import ACCOUNTS, JOBS, OUTLOOK_POOL
from tests.support_pg import PostgresTestCase


class InsertAccountTransactionTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_account_and_mailbox_are_committed_together(self):
        rs.insert_row(OUTLOOK_POOL, {"email": "pair@example.test", "status": "available"})

        acc_id = db.insert_account(email="pair@example.test", access_token="tok-1")

        self.assertIsNotNone(db.get_account(acc_id))
        pool = rs.get_row_by(OUTLOOK_POOL, "email", "pair@example.test")
        self.assertEqual(pool["status"], "used")
        self.assertEqual(pool["registered_account_id"], acc_id)

    def test_mailbox_is_not_left_available_after_account_exists(self):
        """邮箱被标记 used 与账号存在，必须同真同假。

        分两次落盘时，中间失败会留下账号已建、邮箱仍 available 的状态，
        这个邮箱之后会被再领一次，导致同一地址重复注册。
        """
        rs.insert_row(OUTLOOK_POOL, {"email": "atomic@example.test", "status": "available"})
        db.insert_account(email="atomic@example.test", access_token="tok-2")

        account = db.get_account_by_email("atomic@example.test")
        pool = rs.get_row_by(OUTLOOK_POOL, "email", "atomic@example.test")
        self.assertEqual(bool(account), pool["status"] == "used")


class ClaimConcurrencyTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.acc_id = rs.insert_row(ACCOUNTS, {"email": "claim@example.test"})

    def test_plan_check_claim_is_exclusive_across_threads(self):
        results, lock = [], threading.Lock()

        def attempt():
            ok = db.claim_account_plan_check(acc_id=self.acc_id)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=attempt) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(1 for r in results if r), 1, f"应恰好一个成功: {results}")

    def test_live_check_claim_is_exclusive_across_threads(self):
        results, lock = [], threading.Lock()

        def attempt():
            ok = db.claim_account_live_check(self.acc_id)
            with lock:
                results.append(ok)

        threads = [threading.Thread(target=attempt) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sum(1 for r in results if r), 1, f"应恰好一个成功: {results}")

    def test_extract_claim_is_exclusive(self):
        self.assertTrue(db.claim_account_extract(self.acc_id))
        self.assertFalse(db.claim_account_extract(self.acc_id))

    def test_stale_queue_entry_is_reclaimable(self):
        self.assertTrue(db.claim_account_plan_check(acc_id=self.acc_id))
        self.assertFalse(db.claim_account_plan_check(acc_id=self.acc_id))

        stale = (datetime.now() - timedelta(seconds=3600)).isoformat(timespec="seconds")
        rs.patch_row(ACCOUNTS, self.acc_id, {"plan_check_queued_at": stale})
        self.assertTrue(db.claim_account_plan_check(acc_id=self.acc_id),
                        "排队已超时的记录必须能被重新领取，否则会永久卡住")

    def test_unparseable_timestamp_does_not_wedge_the_account(self):
        """时间戳损坏时必须放行——否则一行脏数据会让账号永远无法再被领取。"""
        rs.patch_row(ACCOUNTS, self.acc_id, {
            "plan_check_status": "queued", "plan_check_queued_at": "不是时间",
        })
        self.assertTrue(db.claim_account_plan_check(acc_id=self.acc_id))

    def test_deactivated_account_is_not_claimable_for_live_check(self):
        rs.patch_row(ACCOUNTS, self.acc_id, {"account_status": "deactivated"})
        self.assertFalse(db.claim_account_live_check(self.acc_id))

    def test_mark_running_requires_an_active_claim(self):
        self.assertFalse(db.mark_account_plan_check_running(self.acc_id))
        self.assertTrue(db.claim_account_plan_check(acc_id=self.acc_id))
        self.assertTrue(db.mark_account_plan_check_running(self.acc_id))


class WriteScopeTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.ids = [rs.insert_row(ACCOUNTS, {"email": f"scope{i}@example.test"})
                    for i in range(6)]

    def _row_versions(self) -> dict[int, str]:
        """读每行的 xmin —— 最后写入该行的事务号。

        不用 updated_at 判断"哪些行被写过"：它是秒级精度，同一秒内的写入看不出
        差别。xmin 由 PostgreSQL 维护，行被物理重写才会变，是精确的度量。
        """
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id, xmin::text AS v FROM {rs._qualified(ACCOUNTS)}")
            return {int(r["id"]): r["v"] for r in cur.fetchall()}

    def test_single_field_update_touches_exactly_one_row(self):
        """改造前这里会重写整个集合；现在只应有一行被物理写入。"""
        before = self._row_versions()
        db.update_account_note(self.ids[2], "只改这一条")
        after = self._row_versions()

        changed = sorted(i for i in after if before.get(i) != after[i])
        self.assertEqual(changed, [self.ids[2]])

    def test_note_survives_an_unrelated_concurrent_update(self):
        db.update_account_note(self.ids[0], "备注保留")
        db.update_account_note(self.ids[1], "另一条备注")
        self.assertEqual(db.get_account(self.ids[0])["note"], "备注保留")
        self.assertEqual(db.get_account(self.ids[1])["note"], "另一条备注")


class JobStorageTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()

    def test_job_round_trip_through_table(self):
        job = db.create_job(email_source="outlook")
        fetched = db.get_job(job["id"])
        self.assertEqual(fetched["id"], job["id"])
        self.assertEqual(fetched["status"], job["status"])

    def test_job_progress_updates_persist(self):
        job = db.create_job(email_source="outlook")
        db.update_job(job["id"], status="running")
        self.assertEqual(db.get_job(job["id"])["status"], "running")


class StartupRecoveryTests(PostgresTestCase):
    """启动恢复不得清空数据。

    这条对应一次真实事故：未完成的存储层代码被线上服务加载后，启动恢复读到一张
    空表，又把空快照当成全量写了回去，361 条注册任务只剩 5 条。恢复逻辑只允许
    改状态，绝不允许改变行数。
    """

    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.job_ids = [
            rs.insert_row(JOBS, {"job_uuid": f"u-{i}", "status": s, "email": f"j{i}@example.test"})
            for i, s in enumerate(["success", "failed", "running", "queued", "success"])
        ]
        self.acc_ids = [
            rs.insert_row(ACCOUNTS, {"email": f"keep{i}@example.test"}) for i in range(4)
        ]

    def test_recovery_preserves_every_row(self):
        before_jobs = rs.count_rows(JOBS)
        before_accounts = rs.count_rows(ACCOUNTS)

        db.recover_interrupted_registration_jobs()
        db.recover_interrupted_plan_checks()
        db.recover_interrupted_live_checks()
        db.recover_interrupted_extract_links()

        self.assertEqual(rs.count_rows(JOBS), before_jobs)
        self.assertEqual(rs.count_rows(ACCOUNTS), before_accounts)

    def test_repeated_recovery_is_stable(self):
        """模拟连续重启：行数必须始终不变。"""
        for _ in range(3):
            db.recover_interrupted_registration_jobs()
            self.assertEqual(rs.count_rows(JOBS), len(self.job_ids))
            self.assertEqual(rs.count_rows(ACCOUNTS), len(self.acc_ids))

    def test_recovery_only_rewrites_interrupted_rows(self):
        """已完成的任务不该被恢复流程重写。"""
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id, xmin::text AS v FROM {rs._qualified(JOBS)}")
            before = {int(r["id"]): r["v"] for r in cur.fetchall()}

        db.recover_interrupted_registration_jobs()

        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id, xmin::text AS v FROM {rs._qualified(JOBS)}")
            after = {int(r["id"]): r["v"] for r in cur.fetchall()}

        rewritten = {i for i in after if before.get(i) != after[i]}
        finished = {self.job_ids[0], self.job_ids[1], self.job_ids[4]}
        self.assertFalse(rewritten & finished,
                         f"已完成的任务被重写了: {sorted(rewritten & finished)}")


if __name__ == "__main__":
    unittest.main()
