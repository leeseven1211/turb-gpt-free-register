"""在隔离 schema 内验证真实 PostgreSQL 锁超时的诊断。"""
from psycopg.errors import LockNotAvailable

from core.storage import postgres
from tests.support_pg import PostgresTestCase


class PostgresWaitDiagnosticsTests(PostgresTestCase):
    def test_lock_timeout_preserves_driver_error_and_hides_statement(self):
        table = postgres.qualified("test_private_wait_relation")
        with postgres.connect() as conn, conn.cursor() as cursor:
            cursor.execute(f"CREATE TABLE {table} (id integer PRIMARY KEY)")
            cursor.execute(f"INSERT INTO {table} VALUES (1)")

        with postgres.connect() as blocker, blocker.cursor() as cursor:
            cursor.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
            with self.assertLogs("core.postgres_store", level="WARNING") as captured:
                with self.assertRaises(LockNotAvailable):
                    with postgres.connect() as waiting, waiting.cursor() as other:
                        other.execute("SET LOCAL lock_timeout = '80ms'")
                        other.execute(f"SELECT id FROM {table}")

        message = next(row.getMessage() for row in captured.records
                       if "code=db_lock_unavailable" in row.getMessage())
        self.assertIn("sqlstate=55P03", message)
        self.assertRegex(message, r"\btransaction_ms=\d+\.\d")
        self.assertNotIn("test_private_wait_relation", message)
        self.assertNotIn("SELECT", message)
        with postgres.connect() as conn, conn.cursor() as cursor:
            cursor.execute(f"SELECT id FROM {table}")
            self.assertEqual(cursor.fetchone(), (1,))
