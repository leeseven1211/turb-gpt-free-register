# -*- coding: utf-8 -*-
"""邮箱库存表达式索引 v2 的隔离迁移测试。"""
import tempfile
from pathlib import Path
import json
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from unittest.mock import patch

from core.storage import records as rs
from core.storage.email import inventory_indexes
from tests.support_pg import PostgresTestCase


class EmailInventoryIndexMigrationTests(PostgresTestCase):
    def _source_root(self, directory: str, *, database_url: str | None = None, schema: str | None = None) -> Path:
        source_root = Path(directory)
        source_root.joinpath(".env").write_text(
            "\n".join((
                f"DATABASE_URL={database_url or rs.postgres_store.database_url()}",
                f"TURB_DB_SCHEMA={schema or self.schema}",
            )) + "\n",
            encoding="utf-8",
        )
        return source_root

    def test_v2_creates_nine_non_unique_expression_indexes(self):
        rs.init()

        with rs._connect() as conn:
            observed = inventory_indexes.inspect_indexes(conn)

        self.assertEqual(len(observed), 9)
        self.assertTrue(all(item["exists"] for item in observed))
        self.assertTrue(all(item["relkind"] == "i" for item in observed))
        self.assertTrue(all(item["amname"] == "btree" for item in observed))
        self.assertTrue(all(not item["indisunique"] for item in observed))
        self.assertTrue(all(item["indisvalid"] and item["indisready"] and item["indislive"] for item in observed))
        self.assertTrue(all(item["indnkeyatts"] == 1 and item["indnatts"] == 1 for item in observed))
        self.assertTrue(all(item["predicate"] == spec.predicate for item, spec in zip(
            observed, inventory_indexes.INDEX_SPECS
        )))
        self.assertTrue(all(item["expression"] == spec.expression for item, spec in zip(
            observed, inventory_indexes.INDEX_SPECS
        )))

    def test_existing_v1_marker_is_upgraded_without_reapplying_v1_schema(self):
        rs.init()
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = %s",
                (rs._SCHEMA_VERSION,),
            )
            for spec in inventory_indexes.INDEX_SPECS:
                cur.execute(
                    f"DROP INDEX {rs.postgres_store.qualified(spec.name)}"
                )

        rs.reset_ready()
        with patch.object(rs, "_apply_record_schema", wraps=rs._apply_record_schema) as apply_v1:
            rs.init()
        apply_v1.assert_not_called()

        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = %s",
                (rs._SCHEMA_VERSION,),
            )
            self.assertIsNotNone(cur.fetchone())

    def test_wrong_existing_index_definition_is_rejected(self):
        rs.init()
        spec = inventory_indexes.INDEX_SPECS[0]
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP INDEX {rs.postgres_store.qualified(spec.name)}")
            cur.execute(
                f"CREATE INDEX {rs.postgres_store.quote_identifier(spec.name)} "
                f"ON {rs.postgres_store.qualified(spec.table)} (LOWER(BTRIM(email)))"
            )

        with self.assertRaisesRegex(RuntimeError, "定义或状态不符合预期"):
            with rs._connect() as conn:
                inventory_indexes.ensure_indexes(conn, concurrent=False)

    def test_repeated_v2_initialization_does_not_rebuild_indexes(self):
        rs.init()
        with patch.object(inventory_indexes, "_create_index", wraps=inventory_indexes._create_index) as create:
            rs.reset_ready()
            rs.init()
        create.assert_not_called()

    def test_maintenance_apply_uses_real_autocommit_online_path(self):
        rs.init()
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = %s",
                (rs._SCHEMA_VERSION,),
            )
            for spec in inventory_indexes.INDEX_SPECS:
                cur.execute(f"DROP INDEX {rs.postgres_store.qualified(spec.name)}")

        from tools.maintenance import prepare_email_inventory_indexes as tool

        with tempfile.TemporaryDirectory() as directory:
            source_root = self._source_root(directory)
            result = tool.run(source_root, apply=True)

        self.assertTrue(result["ok"])
        self.assertEqual(set(result["created"]), {spec.name for spec in inventory_indexes.INDEX_SPECS})
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = 2"
            )
            self.assertIsNotNone(cur.fetchone())

    def test_maintenance_check_is_read_only_and_direct_cli_loads_repo(self):
        rs.init()
        from tools.maintenance import prepare_email_inventory_indexes as tool

        with tempfile.TemporaryDirectory() as directory:
            source_root = self._source_root(directory)
            result = tool.run(source_root, apply=False)
            self.assertTrue(result["ok"])
            values = {
                "DATABASE_URL": rs.postgres_store.database_url(),
                "TURB_DB_SCHEMA": self.schema,
            }
            with tool._target_environment(values) as effective:
                with tool._connect(effective, readonly=True) as conn, conn.cursor() as cur:
                    cur.execute("SELECT current_setting('transaction_read_only')")
                    self.assertEqual(cur.fetchone()[0], "on")

            command = [
                sys.executable,
                str(Path(__file__).resolve().parents[2] / "tools/maintenance/prepare_email_inventory_indexes.py"),
                "--source-root",
                str(source_root),
            ]
            completed = subprocess.run(
                command,
                cwd=source_root,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["ok"])

    def test_online_gate_makes_startup_and_second_tool_fail_fast(self):
        rs.init()
        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = %s",
                (rs._SCHEMA_VERSION,),
            )

        from tools.maintenance import prepare_email_inventory_indexes as tool

        with tempfile.TemporaryDirectory() as directory:
            source_root = self._source_root(directory)
            values = {
                "DATABASE_URL": rs.postgres_store.database_url(),
                "TURB_DB_SCHEMA": self.schema,
            }
            with tool._target_environment(values) as effective:
                holder = tool._connect(effective)
                self.assertTrue(tool._try_online_gate(holder))
                try:
                    with self.assertRaisesRegex(RuntimeError, "在线迁移进行中"):
                        with rs._connect() as conn:
                            rs.ensure_record_schema(conn)
                    with self.assertRaisesRegex(tool.IndexPreparationError, "schema_migration_busy"):
                        tool.run(source_root, apply=True)
                finally:
                    tool._unlock_online_gate(holder)
                    holder.close()

        with rs._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {rs.postgres_store.qualified(rs._SCHEMA_MIGRATIONS)} WHERE version = 2"
            )
            self.assertIsNone(cur.fetchone())

    def test_process_connection_values_override_bootstrap_file(self):
        rs.init()
        current_url = rs.postgres_store.database_url()
        parsed = urlsplit(current_url)
        file_url = urlunsplit((parsed.scheme, parsed.netloc, "/turb_dev", parsed.query, parsed.fragment))
        from tools.maintenance import prepare_email_inventory_indexes as tool

        with tempfile.TemporaryDirectory() as directory:
            source_root = self._source_root(directory, database_url=file_url, schema="missing_file_schema")
            with patch.dict(
                "os.environ",
                {
                    "DATABASE_URL": current_url,
                    "TURB_DB_SCHEMA": self.schema,
                    "TURB_ALLOW_PRODUCTION_DB": "0",
                },
                clear=False,
            ):
                result = tool.run(source_root, apply=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["schema"], self.schema)

    def test_bootstrap_interpolation_keeps_process_environment_values(self):
        from tools.maintenance import prepare_email_inventory_indexes as tool

        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory)
            source_root.joinpath(".env").write_text(
                "REVIEW_SCHEMA_TARGET=test_file\n"
                "TURB_DB_SCHEMA=${REVIEW_SCHEMA_TARGET}\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"REVIEW_SCHEMA_TARGET": "test_process"}, clear=False):
                values = tool._bootstrap_values(source_root)
        self.assertEqual(values["TURB_DB_SCHEMA"], "test_process")
