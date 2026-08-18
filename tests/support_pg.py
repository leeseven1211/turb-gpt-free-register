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
import pathlib
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from unittest.mock import patch

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
    """给每个测试类分配独立 schema；没有 DATABASE_URL 时跳过。

    另外把 db 的兼容导出路径重定向到临时目录：这些导出仍会在每次写入时触发，
    不重定向的话测试会覆盖仓库根目录下的真实账号文件。
    """

    schema: str = ""
    _previous_schema: str | None = None

    # db 里那些指向仓库根目录真实文件的常量
    _REDIRECTED_PATHS = (
        "_ACCOUNTS_JSON", "_ACCOUNTS_TXT", "_TOKENS_TXT", "_VIEWER_HTML",
        "_JOBS_JSON", "_OUTLOOK_JSON", "_OUTLOOK_TXT",
        "_GENERIC_API_EMAIL_JSON", "_GENERIC_API_EMAIL_TXT",
        "_DOMAIN_EMAIL_JSON", "_ICLOUD_HIDE_EMAIL_JSON",
        "_LEGACY_ACCOUNTS_JSON", "_LEGACY_JOBS_JSON", "_LEGACY_OUTLOOK_JSON",
    )

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

    def seed(self, spec, records: list[dict]) -> list[int]:
        """往行级表里写测试数据。

        取代改造前"往临时 JSON 文件里塞一段 payload"的做法——那时 db 从文件读，
        现在 db 从表读。
        """
        from core import record_store
        record_store.reset_ready()
        record_store.init()
        return [record_store.insert_row(spec, dict(r)) for r in records]

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

        from core import db, record_store
        record_store.reset_ready()
        with tempfile.TemporaryDirectory() as td, ExitStack() as stack:
            root = pathlib.Path(td)
            for name in self._REDIRECTED_PATHS:
                if hasattr(db, name):
                    stack.enter_context(
                        patch.object(db, name, root / f"{name.strip('_').lower()}.json"))
            return super().run(result)

