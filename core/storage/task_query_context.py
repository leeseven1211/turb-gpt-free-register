"""任务和账号查询只读取已部署的表，独立存储调用仍可初始化。"""

from contextlib import contextmanager
from contextvars import ContextVar

from psycopg.errors import InvalidSchemaName, UndefinedColumn, UndefinedTable


class TaskSchemaUnavailable(Exception):
    """当前查询需要的表或列尚未部署。"""


MISSING_SCHEMA_ERRORS = (UndefinedTable, UndefinedColumn, InvalidSchemaName)
_readonly = ContextVar("readonly_task_query", default=False)


@contextmanager
def task_query():
    token = _readonly.set(True)
    try:
        yield
    except MISSING_SCHEMA_ERRORS as error:
        raise TaskSchemaUnavailable from error
    finally:
        _readonly.reset(token)


def readonly_task_query() -> bool:
    return _readonly.get()


def task_read_connection(connect, initialize):
    if not readonly_task_query():
        initialize()
    return connect()
