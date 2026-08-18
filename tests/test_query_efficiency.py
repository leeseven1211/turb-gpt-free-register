# -*- coding: utf-8 -*-
"""查询效率回归。

拆表后读路径的成本结构变了：以前整个集合是一行 blob（还带 1 秒缓存），
现在是多行多次查询。于是两类问题会悄悄冒出来——
  1. 为了取一条记录而加载整张表，在逐条调用的地方退化成 N+1
  2. 每次查询新建数据库连接（实测建连接 38ms、真正查询 2.4ms）

这两点都不会让测试变红，只会让页面变慢，所以用查询计数把它们钉住。
"""
import unittest

from core import db, postgres_store, record_store as rs
from core import registration_service as svc
from core.record_store import ACCOUNTS, JOBS
from tests.support_pg import PostgresTestCase


class _QueryCounter:
    """统计期间执行的 SQL 条数。"""

    def __init__(self):
        self.count = 0

    def __enter__(self):
        import psycopg
        self._orig = psycopg.Cursor.execute
        counter = self

        def counting_execute(cursor, query, params=None, **kw):
            counter.count += 1
            return counter._orig(cursor, query, params, **kw)

        psycopg.Cursor.execute = counting_execute
        return self

    def __exit__(self, *exc):
        import psycopg
        psycopg.Cursor.execute = self._orig
        return False


class SingleRowLookupTests(PostgresTestCase):
    def setUp(self):
        rs.reset_ready()
        rs.init()
        self.ids = [rs.insert_row(ACCOUNTS, {"email": f"q{i}@example.test"}) for i in range(40)]

    def test_get_account_does_not_scan_the_table(self):
        with _QueryCounter() as c:
            db.get_account(self.ids[7])
        self.assertLessEqual(c.count, 2, "取一条账号不该扫全表")

    def test_get_account_by_email_does_not_scan_the_table(self):
        with _QueryCounter() as c:
            db.get_account_by_email("q7@example.test")
        self.assertLessEqual(c.count, 2)

    def test_count_accounts_is_a_single_aggregate(self):
        with _QueryCounter() as c:
            self.assertEqual(db.count_accounts(), 40)
        self.assertLessEqual(c.count, 2)


class RetryInfoFanoutTests(PostgresTestCase):
    """get_retry_info 会被列表页对每一条任务调用一次。

    它内部的两次查找（同链成功任务、关联账号）一旦退化成全表扫描，
    100 条任务的列表就会慢到以秒计——这正是切换后真实遇到的问题。
    """

    def setUp(self):
        rs.reset_ready()
        rs.init()
        for i in range(60):
            rs.insert_row(JOBS, {
                "job_uuid": f"u{i}", "status": "failed",
                "email": f"j{i}@example.test", "root_job_id": i,
            })
        for i in range(60):
            rs.insert_row(ACCOUNTS, {"email": f"j{i}@example.test"})

    def test_per_job_cost_does_not_grow_with_table_size(self):
        job = db.list_jobs(limit=1)[0]
        with _QueryCounter() as c:
            svc.get_retry_info(job)
        self.assertLessEqual(c.count, 6, f"单条任务用了 {c.count} 次查询，疑似退化成全表扫描")

    def test_successful_retry_lookup_is_pushed_into_sql(self):
        job = db.list_jobs(limit=1)[0]
        with _QueryCounter() as c:
            db.get_successful_retry_for_job(int(job["id"]))
        self.assertLessEqual(c.count, 3)


class ConnectionPoolTests(PostgresTestCase):
    def test_connections_are_pooled_not_reopened(self):
        """连接是借出来的，不是每次新建的。

        建连接约 38ms、查询约 2.4ms；不池化的话，列表页每渲染一行都要重新握手。
        """
        seen = set()
        for _ in range(8):
            with postgres_store.connect() as conn:
                seen.add(id(conn))
        self.assertLess(len(seen), 8, "每次都拿到新连接对象，说明没有复用")


if __name__ == "__main__":
    unittest.main()
