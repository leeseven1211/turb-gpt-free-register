"""连接为只读时，任务中心 GET 直接用已有查询读取已迁移的表。"""

from contextlib import contextmanager
from contextvars import ContextVar

from psycopg.errors import InvalidSchemaName, UndefinedColumn, UndefinedTable


class TaskSchemaUnavailable(Exception):
    """当前只读连接缺少查询实际使用的表或列。"""


# None 表示普通调用；仅查询服务进入这个作用域，首次访问存储才借连接。
_mode: ContextVar[str | None] = ContextVar("task_query_mode", default=None)


@contextmanager
def task_query():
    token = _mode.set("pending")
    try:
        yield
    except (UndefinedTable, UndefinedColumn, InvalidSchemaName) as error:
        if _mode.get() == "readonly":
            raise TaskSchemaUnavailable from error
        raise
    finally:
        _mode.reset(token)


def readonly_task_query() -> bool:
    return _mode.get() == "readonly"


def _readonly_connection(conn) -> bool:
    if conn.read_only is True or conn.info.parameter_status("in_hot_standby") == "on":
        return True
    mode = conn.info.parameter_status("default_transaction_read_only")
    if mode is None:
        from psycopg.rows import tuple_row

        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute("SHOW transaction_read_only")
            mode = cur.fetchone()[0]
    return mode == "on"


@contextmanager
def task_read_connection(connect, initialize, initialized):
    """为任务查询借用连接，可写库沿用各存储原有的初始化流程。"""
    if _mode.get() == "pending":
        # 热读就地复用查询连接；冷的可写初始流程要另借连接，先归还这条。
        with connect() as conn:
            readonly = _readonly_connection(conn)
            _mode.set("readonly" if readonly else "writable")
            if readonly or initialized():
                yield conn
                return
    if not readonly_task_query():
        initialize()
    with connect() as conn:
        yield conn
