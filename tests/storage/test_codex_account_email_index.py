"""Real PostgreSQL coverage for the Codex lookup's account email expression index."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import psycopg

from core.storage import postgres as pg
from core.storage import records as rs
from tests.support_pg import PostgresTestCase


INDEX_NAME = "idx_registered_accounts_normalized_email"
EXPRESSION = "LOWER(BTRIM(COALESCE(email, '')))"


@contextmanager
def executed_sql():
    """Observe SQL while still executing every statement against PostgreSQL."""
    statements = []
    original = psycopg.Cursor.execute

    def execute(cursor, query, *args, **kwargs):
        statements.append(query if isinstance(query, str) else query.as_string(cursor.connection))
        return original(cursor, query, *args, **kwargs)

    with patch.object(psycopg.Cursor, "execute", execute):
        yield statements


def account_analyzes(statements):
    return [statement for statement in statements
            if statement.lstrip().upper().startswith("ANALYZE ")
            and '"registered_accounts"' in statement]


class AccountEmailIndexAssertions:
    def index_facts(self):
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT c.oid, c.relkind, t.relname AS table_name, am.amname, "
                "i.indisunique, i.indisvalid, i.indisready, i.indnkeyatts, i.indnatts, "
                "i.indkey::text, i.indoption::text, "
                "pg_get_expr(i.indexprs, i.indrelid) AS expression, "
                "pg_get_expr(i.indpred, i.indrelid) AS predicate, "
                "pg_get_indexdef(c.oid) AS definition "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "LEFT JOIN pg_index i ON i.indexrelid = c.oid "
                "LEFT JOIN pg_class t ON t.oid = i.indrelid "
                "LEFT JOIN pg_am am ON am.oid = c.relam "
                "WHERE n.nspname = %s AND c.relname = %s",
                (self.schema, INDEX_NAME),
            )
            return cur.fetchone()

    def assert_expected_index(self):
        facts = self.index_facts()
        self.assertIsNotNone(facts, "account normalized-email index was not created")
        self.assertEqual(facts["relkind"], "i")
        self.assertEqual(facts["table_name"], "registered_accounts")
        self.assertEqual(facts["amname"], "btree")
        self.assertFalse(facts["indisunique"], "normalization must not introduce uniqueness")
        self.assertTrue(facts["indisvalid"])
        self.assertTrue(facts["indisready"])
        self.assertEqual(facts["indnkeyatts"], 1)
        self.assertEqual(facts["indnatts"], 1)
        self.assertEqual(facts["indkey"], "0")
        self.assertEqual(facts["indoption"], "0")
        self.assertEqual(facts["expression"], "lower(btrim(COALESCE(email, ''::text)))")
        self.assertIsNone(facts["predicate"])
        return facts

    def drop_test_index(self):
        # This name belongs only to the temporary schema created by PostgresTestCase.
        self.assertTrue(self.schema.startswith("test_"))
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP INDEX IF EXISTS {pg.qualified(INDEX_NAME)}")

    def expression_stats(self):
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT attname, null_frac, n_distinct FROM pg_stats "
                "WHERE schemaname = %s AND tablename = %s",
                (self.schema, INDEX_NAME),
            )
            return cur.fetchall()


class NewAccountEmailIndexTests(AccountEmailIndexAssertions, PostgresTestCase):
    def test_new_schema_creates_nonunique_expression_index_and_analyzes_once(self):
        # Missing expression DDL or its initial ANALYZE must fail this test.
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s) AS relation", (rs._qualified(rs.ACCOUNTS),))
            self.assertIsNone(cur.fetchone()["relation"])
        rs.reset_ready()
        with executed_sql() as statements:
            rs.init()
        self.assert_expected_index()
        self.assertEqual(len(account_analyzes(statements)), 1)


class LegacyAccountEmailIndexTests(AccountEmailIndexAssertions, PostgresTestCase):
    def setUp(self):
        self.drop_test_index()
        rs.reset_ready()
        rs.init()
        # Reproduce an existing table from before this index, preserving all data/schema.
        self.drop_test_index()
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {rs._qualified(rs.ACCOUNTS)} ALTER COLUMN email SET NOT NULL")
        self.addCleanup(self.drop_test_index)
        self.addCleanup(rs.reset_ready)

    def test_legacy_rows_are_preserved_and_expression_statistics_are_created(self):
        ids = [rs.insert_row(rs.ACCOUNTS, {"email": email}) for email in (
            " Alice@example.test ", "alice@example.test", "ALICE@EXAMPLE.TEST",
            "", "   ", "bob@example.test",
        )]
        rs.reset_ready()
        with executed_sql() as statements:
            rs.init()
        self.assert_expected_index()
        self.assertEqual(len(account_analyzes(statements)), 1)
        stats = self.expression_stats()
        self.assertEqual(len(stats), 1, "ANALYZE must populate expression-index statistics")
        self.assertEqual(stats[0]["null_frac"], 0)
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {rs._qualified(rs.ACCOUNTS)} ORDER BY id")
            self.assertEqual([row["id"] for row in cur.fetchall()], ids)
            cur.execute(
                f"SELECT {EXPRESSION} AS normalized, COUNT(*) AS count "
                f"FROM {rs._qualified(rs.ACCOUNTS)} GROUP BY 1 ORDER BY 1"
            )
            self.assertEqual(cur.fetchall(), [
                {"normalized": "", "count": 2},
                {"normalized": "alice@example.test", "count": 3},
                {"normalized": "bob@example.test", "count": 1},
            ])

    def test_reinitialization_keeps_oid_and_does_not_reanalyze(self):
        rs.insert_row(rs.ACCOUNTS, {"email": "one@example.test"})
        rs.reset_ready()
        rs.init()
        before = self.assert_expected_index()
        before_stats = self.expression_stats()
        self.assertEqual(len(before_stats), 1)
        with executed_sql() as statements:
            for _ in range(3):
                rs.reset_ready()
                rs.init()
        self.assertEqual(self.assert_expected_index()["oid"], before["oid"])
        self.assertEqual(self.expression_stats(), before_stats)
        self.assertEqual(account_analyzes(statements), [])
        self.assertFalse(any(statement.lstrip().upper().startswith(("CREATE INDEX", "DROP INDEX"))
                             and INDEX_NAME in statement for statement in statements))

    def test_correct_precreated_index_is_reused_without_analyze(self):
        rs.insert_row(rs.ACCOUNTS, {"email": "precreated@example.test"})
        with pg.connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(f"CREATE INDEX CONCURRENTLY {pg.quote_identifier(INDEX_NAME)} ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION})")
            cur.execute(f"ANALYZE {rs._qualified(rs.ACCOUNTS)}")
        before = self.assert_expected_index()
        rs.reset_ready()
        with executed_sql() as statements:
            rs.init()
        self.assertEqual(self.assert_expected_index()["oid"], before["oid"])
        self.assertEqual(account_analyzes(statements), [])
        self.assertEqual(len(self.expression_stats()), 1)

    def test_normalized_duplicates_and_nullable_legacy_emails_remain_insertable(self):
        # The raw-email unique index remains; normalized uniqueness must not be added.
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {rs._qualified(rs.ACCOUNTS)} ALTER COLUMN email DROP NOT NULL")
        rs.reset_ready()
        rs.init()
        self.assert_expected_index()
        values = [" Alice@example.test ", "alice@example.test", "ALICE@EXAMPLE.TEST", "", "   ", None, None]
        with rs._connect() as conn, conn.cursor() as cur:
            for email in values:
                cur.execute(
                    f"INSERT INTO {rs._qualified(rs.ACCOUNTS)} (email, created_at, updated_at) VALUES (%s, '', '')",
                    (email,),
                )
            cur.execute(
                f"SELECT {EXPRESSION} AS normalized, COUNT(*) AS count "
                f"FROM {rs._qualified(rs.ACCOUNTS)} GROUP BY 1 ORDER BY 1"
            )
            self.assertEqual(cur.fetchall(), [
                {"normalized": "", "count": 4},
                {"normalized": "alice@example.test", "count": 3},
            ])

    def test_same_named_wrong_index_is_rejected_without_replacement(self):
        # IF NOT EXISTS alone silently accepts each incompatible lookup index.
        definitions = [
            f"ON {rs._qualified(rs.ACCOUNTS)} (LOWER(email))",
            f"ON {rs._qualified(rs.ACCOUNTS)} (email)",
            f"ON {rs._qualified(rs.ACCOUNTS)} USING hash ({EXPRESSION})",
            f"ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION}) WHERE email <> ''",
            f"ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION}) INCLUDE (id)",
            f"ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION} DESC)",
            f"ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION} text_pattern_ops)",
            f'ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION} COLLATE "C")',
            f"ON {rs._qualified(rs.CODEX_CREDENTIALS)} ({EXPRESSION})",
        ]
        for definition in definitions:
            with self.subTest(definition=definition):
                self.drop_test_index()
                with rs._connect() as conn, conn.cursor() as cur:
                    cur.execute(f"CREATE INDEX {pg.quote_identifier(INDEX_NAME)} {definition}")
                before = self.index_facts()
                rs.reset_ready()
                with executed_sql() as statements:
                    with self.assertRaisesRegex(RuntimeError, INDEX_NAME):
                        rs.init()
                after = self.index_facts()
                self.assertEqual(after["oid"], before["oid"])
                self.assertEqual(after["definition"], before["definition"])
                self.assertEqual(account_analyzes(statements), [])

    def test_same_named_unique_index_is_rejected_without_replacement(self):
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE UNIQUE INDEX {pg.quote_identifier(INDEX_NAME)} ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION})")
        before = self.index_facts()
        self.assertTrue(before["indisunique"])
        rs.reset_ready()
        with self.assertRaisesRegex(RuntimeError, INDEX_NAME):
            rs.init()
        after = self.index_facts()
        self.assertEqual(after["oid"], before["oid"])
        self.assertTrue(after["indisunique"])

    def test_same_named_invalid_nonunique_index_is_rejected_without_replacement(self):
        account_id = rs.insert_row(rs.ACCOUNTS, {"email": "blocked-build@example.test"})
        # Concurrent build registers its index, then waits for this pre-existing writer.
        # Cancel the build through a local timeout, producing a real invalid index
        # without changing pg_index or requiring superuser permissions.
        with rs._connect() as writer, writer.cursor() as cur:
            cur.execute(f"UPDATE {rs._qualified(rs.ACCOUNTS)} SET updated_at = 'held' WHERE id = %s", (account_id,))
            with pg.connect(autocommit=True, options="-c statement_timeout=1000") as builder:
                with self.assertRaises(psycopg.errors.QueryCanceled):
                    builder.execute(f"CREATE INDEX CONCURRENTLY {pg.quote_identifier(INDEX_NAME)} ON {rs._qualified(rs.ACCOUNTS)} ({EXPRESSION})")
            writer.rollback()
        before = self.index_facts()
        self.assertIsNotNone(before, "concurrent cancellation must leave a catalog index")
        self.assertFalse(before["indisunique"])
        self.assertFalse(before["indisvalid"])
        rs.reset_ready()
        with self.assertRaisesRegex(RuntimeError, INDEX_NAME):
            rs.init()
        after = self.index_facts()
        self.assertEqual(after["oid"], before["oid"])
        self.assertFalse(after["indisvalid"])
