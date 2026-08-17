# -*- coding: utf-8 -*-
"""PostgreSQL 测试支撑：每个测试类一个临时 schema，结束即销毁。

为什么需要这个：`core.postgres_store` 不再有"纯文件模式"回退，测试进程一旦碰
数据库就是真库。`_guard_production_schema()` 会拦住 public schema，所以任何用到
存储层的测试都必须先把 `TURB_DB_SCHEMA` 指到一次性 schema。

用法：

    from tests.support_pg import PostgresTestCase

    class MyStoreTests(PostgresTestCase):
        def test_something(self):
            ...   # 此时 TURB_DB_SCHEMA 已指向 test_mystoretests_<uuid>

没有可用 DATABASE_URL 时整个类会 skip，本地无库也能跑其余测试。
"""
from __future__ import annotations

import os
import unittest
import uuid

from core import postgres_store


def database_available() -> bool:
    """检测是否有可用的 DATABASE_URL。

    显式加载 .env：不是每个测试模块都会 import config，不加载就会把"有库"误判成"无库"
    而整类跳过。
    """
    try:
        from config.env_loader import load_env
        load_env(override=False)
    except Exception:
        pass
    return bool(str(os.getenv("DATABASE_URL") or "").strip())


def temporary_schema_name(prefix: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in prefix).strip("_").lower()
    return f"test_{safe[:24]}_{uuid.uuid4().hex[:8]}"


def drop_schema(name: str) -> None:
    """删除临时 schema。只接受本模块生成的 test_ 前缀名，避免误删。"""
    if not name.startswith("test_"):
        raise ValueError(f"拒绝删除非测试 schema: {name!r}")
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {postgres_store.quote_identifier(name)} CASCADE")


def truncate_schema(name: str) -> None:
    """清空临时 schema 里的所有表，恢复到空库状态。

    对应改造前"每个用例一个 tempfile.TemporaryDirectory"的隔离粒度：schema 建在
    类级别，但用例之间必须互相看不到对方写的行，否则计数类断言会累加。
    `RESTART IDENTITY` 一并复位 id 序列，让断言 id 的用例保持稳定。
    """
    if not name.startswith("test_"):
        raise ValueError(f"拒绝清空非测试 schema: {name!r}")
    with postgres_store.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (name,))
        tables = [row[0] for row in cur.fetchall()]
        if not tables:
            return
        joined = ", ".join(
            f"{postgres_store.quote_identifier(name)}.{postgres_store.quote_identifier(t)}"
            for t in tables
        )
        cur.execute(f"TRUNCATE {joined} RESTART IDENTITY CASCADE")


class PostgresTestCase(unittest.TestCase):
    """给每个测试类分配独立 schema；没有 DATABASE_URL 时跳过。"""

    schema: str = ""
    _previous_schema: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not database_available():
            raise unittest.SkipTest("需要本机 PostgreSQL DATABASE_URL")
        cls.schema = temporary_schema_name(cls.__name__)
        cls._previous_schema = os.environ.get("TURB_DB_SCHEMA")
        os.environ["TURB_DB_SCHEMA"] = cls.schema
        postgres_store.reset_cache()
        postgres_store.ensure_schema()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls.schema:
                drop_schema(cls.schema)
        finally:
            if cls._previous_schema is None:
                os.environ.pop("TURB_DB_SCHEMA", None)
            else:
                os.environ["TURB_DB_SCHEMA"] = cls._previous_schema
            postgres_store.reset_cache()
            super().tearDownClass()

    def run(self, result=None):
        # 用 run() 而不是 setUp()：子类几乎都自带 setUp，不能指望每个都记得调
        # super().setUp()。集合读缓存有 1 秒 TTL，同类内相邻用例会互相看到脏数据。
        if self.schema:
            truncate_schema(self.schema)
        postgres_store.reset_cache()
        return super().run(result)
