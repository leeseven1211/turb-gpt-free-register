# -*- coding: utf-8 -*-
import importlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from core.storage import postgres as postgres_store
from tests.support_pg import PostgresTestCase


class RuntimeConfigMigrationTests(PostgresTestCase):
    @contextmanager
    def source(self, *, runtime_value="original-value"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_url = os.environ["DATABASE_URL"]
            text = (
                f'# 原始部署配置\nDATABASE_URL="{database_url}"\nTURB_DB_SCHEMA="{self.schema}"\n'
                'WEBUI_AUTH_CODE="stable-auth"\nWEBUI_SESSION_SECRET="stable-session"\n'
                'TURB_MAIL_CONSUMER_ID="stable-consumer"\nNODE_EXECUTABLE="/custom/node"\n'
                f'RUNTIME_TEST_SETTING="{runtime_value}"\nPROXY_POOL=""\n'
                'EMAIL_DERIVATION_BUTLER_SECRET_OLD="historical-secret"\n'
                'UNKNOWN_OLD_SETTING="unknown-old-value"\n'
            )
            (root / ".env").write_text(text, encoding="utf-8")
            yield root, text

    def tool(self):
        path = Path(__file__).resolve().parents[2] / 'tools/migrations/migrate_runtime_config.py'
        self.assertTrue(path.is_file(), "缺少显式运行配置迁移工具")
        return importlib.import_module("tools.migrations.migrate_runtime_config")

    def relations(self):
        with postgres_store.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (self.schema,))
            return {row[0] for row in cur.fetchall()}

    def test_dry_run_does_not_create_tables_backup_key_or_change_source(self):
        tool = self.tool()
        with self.source() as (root, original):
            before = self.relations()
            report = tool.run_migration(root)
            self.assertEqual(report["mode"], "dry-run")
            self.assertIn("UNKNOWN_OLD_SETTING", report["runtime_keys"])
            self.assertIn("EMAIL_DERIVATION_BUTLER_SECRET_OLD", report["runtime_keys"])
            self.assertEqual((root / ".env").read_text(encoding="utf-8"), original)
            self.assertEqual({path.name for path in root.iterdir()}, {".env"})
            self.assertEqual(self.relations(), before)
            self.assertNotIn("TURB_CONFIG_ENCRYPTION_KEY", report["runtime_keys"])

    def test_apply_preserves_identity_unknown_values_history_and_private_backup(self):
        tool = self.tool()
        with self.source() as (root, original), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TURB_CONFIG_ENCRYPTION_KEY", None)
            report = tool.run_migration(root, apply=True)
            values = tool.read_source_values(root)
            self.assertEqual(values["WEBUI_AUTH_CODE"], "stable-auth")
            self.assertEqual(values["WEBUI_SESSION_SECRET"], "stable-session")
            self.assertEqual(values["TURB_MAIL_CONSUMER_ID"], "stable-consumer")
            self.assertEqual(values["NODE_EXECUTABLE"], "/custom/node")
            self.assertTrue(values["DATABASE_URL"] == os.environ["DATABASE_URL"])
            self.assertEqual(set(values), {
                "WEBUI_AUTH_CODE", "WEBUI_SESSION_SECRET", "TURB_MAIL_CONSUMER_ID",
                "NODE_EXECUTABLE", "DATABASE_URL", "TURB_DB_SCHEMA", "TURB_CONFIG_ENCRYPTION_KEY",
            })
            self.assertEqual(stat.S_IMODE((root / ".env").stat().st_mode), 0o600)
            Fernet(values["TURB_CONFIG_ENCRYPTION_KEY"].encode())
            backups = list((root / "logs" / "run" / "runtime-config-backups").glob("*.env"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), original)
            self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
            from core.storage import runtime_config as store
            with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": values["TURB_CONFIG_ENCRYPTION_KEY"]}):
                self.assertEqual(store.read_values(), {
                    "RUNTIME_TEST_SETTING": "original-value", "PROXY_POOL": "",
                    "EMAIL_DERIVATION_BUTLER_SECRET_OLD": "historical-secret",
                    "UNKNOWN_OLD_SETTING": "unknown-old-value",
                })
            self.assertEqual(report["migrated_count"], 4)
            self.assertNotIn("original-value", repr(report))
            self.assertNotIn(os.environ["DATABASE_URL"], repr(report))

    def test_repeated_migration_does_not_change_database_revision_or_master_key(self):
        tool = self.tool()
        with self.source() as (root, _):
            tool.run_migration(root, apply=True)
            key = tool.read_source_values(root)["TURB_CONFIG_ENCRYPTION_KEY"]
            from core.storage import runtime_config as store
            revision = store.current_revision()
            report = tool.run_migration(root, apply=True)
            self.assertEqual(store.current_revision(), revision)
            self.assertEqual(tool.read_source_values(root)["TURB_CONFIG_ENCRYPTION_KEY"], key)
            self.assertEqual(report["migrated_count"], 0)

    def test_existing_different_database_value_is_not_overwritten(self):
        tool = self.tool()
        from core.storage import runtime_config as store
        key = Fernet.generate_key().decode()
        with self.source() as (root, _), patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": key}):
            store.write_values({"RUNTIME_TEST_SETTING": "newer-database-value"}, activate=True)
            with self.assertRaisesRegex(tool.MigrationError, "database_conflict"):
                tool.run_migration(root, apply=True)
            self.assertEqual(store.read_values()["RUNTIME_TEST_SETTING"], "newer-database-value")
            retained = tool.read_source_values(root)
            self.assertEqual(retained["RUNTIME_TEST_SETTING"], "original-value")
            self.assertTrue(list((root / "logs" / "run" / "runtime-config-backups").glob("*.env")))

    def test_database_failure_keeps_original_runtime_values_and_persisted_key(self):
        tool = self.tool()
        from core.storage import runtime_config as store
        with self.source() as (root, _), patch.object(store, "write_values", side_effect=RuntimeError("fixture-private-value")):
            with self.assertRaises(tool.MigrationError) as raised:
                tool.run_migration(root, apply=True)
            self.assertNotIn("fixture-private-value", str(raised.exception))
            retained = tool.read_source_values(root)
            self.assertEqual(retained["RUNTIME_TEST_SETTING"], "original-value")
            self.assertIn("TURB_CONFIG_ENCRYPTION_KEY", retained)
            self.assertFalse(store.is_active())

    def test_commit_before_prune_failure_can_be_replayed(self):
        tool = self.tool()
        with self.source() as (root, _):
            with patch.object(tool, "_prune_env", side_effect=OSError("fixture-private-error")):
                with self.assertRaisesRegex(tool.MigrationError, "env_prune_failed"):
                    tool.run_migration(root, apply=True)
            retained = tool.read_source_values(root)
            self.assertIn("RUNTIME_TEST_SETTING", retained)
            key = retained["TURB_CONFIG_ENCRYPTION_KEY"]
            from core.storage import runtime_config as store
            revision = store.current_revision()
            tool.run_migration(root, apply=True)
            self.assertEqual(store.current_revision(), revision)
            self.assertNotIn("RUNTIME_TEST_SETTING", tool.read_source_values(root))
            self.assertEqual(tool.read_source_values(root)["TURB_CONFIG_ENCRYPTION_KEY"], key)

    def test_active_database_without_master_key_refuses_to_generate_a_new_key(self):
        tool = self.tool()
        from core.storage import runtime_config as store
        with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            store.write_values({"RUNTIME_TEST_SETTING": "database-value"}, activate=True)
        with self.source() as (root, _), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TURB_CONFIG_ENCRYPTION_KEY", None)
            with self.assertRaisesRegex(tool.MigrationError, "missing_encryption_key"):
                tool.run_migration(root, apply=True)
            self.assertNotIn("TURB_CONFIG_ENCRYPTION_KEY", tool.read_source_values(root))

    def test_inactive_existing_values_cannot_be_overwritten_or_activated_by_conflict(self):
        tool = self.tool()
        from core.storage import runtime_config as store
        key = Fernet.generate_key().decode()
        with self.source() as (root, _), patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": key}):
            store.write_values({"RUNTIME_TEST_SETTING": "inactive-existing-value"})
            revision = store.current_revision()
            with self.assertRaisesRegex(tool.MigrationError, "database_conflict"):
                tool.run_migration(root, apply=True)
            self.assertFalse(store.is_active())
            self.assertEqual(store.current_revision(), revision)

    def test_cli_reports_only_categories_counts_and_key_names(self):
        tool = self.tool()
        with self.source() as (root, _), io.StringIO() as output:
            with redirect_stdout(output):
                self.assertEqual(tool.main(["--source-root", str(root), "--dry-run"]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["runtime_count"], 4)
            self.assertNotIn("original-value", output.getvalue())
            self.assertNotIn(os.environ["DATABASE_URL"], output.getvalue())
        with io.StringIO() as output, redirect_stderr(output):
            self.assertEqual(tool.main(["--source-root", "/missing-fixture-directory", "--apply"]), 1)
            self.assertEqual(json.loads(output.getvalue())["error_category"], "source_env_unreadable")

    def test_import_does_not_load_config_or_read_any_source_file(self):
        tool_path = Path(__file__).resolve().parents[2] / 'tools/migrations/migrate_runtime_config.py'
        self.assertTrue(tool_path.is_file())
        script = (
            "import importlib.util,sys; "
            "spec=importlib.util.spec_from_file_location('migration_fixture',sys.argv[1]); "
            "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
            "assert 'config' not in sys.modules"
        )
        result = subprocess.run([sys.executable, "-c", script, str(tool_path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_apply_shares_env_writer_lock_and_keeps_update_written_before_release(self):
        tool = self.tool()
        parser_path = Path(__file__).resolve().parents[2] / "config" / "env_loader.py"
        script = """
import importlib.util
import sys
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('physical_env_fixture', sys.argv[2])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._ENV_PATH = root / '.env'
with module.env_file_lock():
    print('locked', flush=True)
    sys.stdin.readline()
    with (root / '.env').open('a', encoding='utf-8') as stream:
        stream.write('CONCURRENT_SOURCE_SETTING="concurrent-value"\\n')
"""
        with self.source() as (root, _):
            writer = subprocess.Popen(
                [sys.executable, "-c", script, str(root), str(parser_path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(writer.stdout.readline().strip(), "locked")
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(tool.run_migration, root, apply=True)
                    try:
                        with self.assertRaises(TimeoutError):
                            future.result(timeout=0.1)
                    finally:
                        writer.stdin.write("release\n")
                        writer.stdin.flush()
                    report = future.result(timeout=15)
                _, stderr = writer.communicate(timeout=5)
                self.assertEqual(writer.returncode, 0, stderr)
                self.assertIn("CONCURRENT_SOURCE_SETTING", report["runtime_keys"])
                key = tool.read_source_values(root)["TURB_CONFIG_ENCRYPTION_KEY"]
                from core.storage import runtime_config as store
                with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": key}):
                    self.assertEqual(store.read_values()["CONCURRENT_SOURCE_SETTING"], "concurrent-value")
            finally:
                if writer.poll() is None:
                    writer.kill()
                    writer.communicate(timeout=5)

    def test_backup_preserves_original_env_bytes(self):
        tool = self.tool()
        with self.source() as (root, text):
            original = text.replace("\n", "\r\n").encode("utf-8")
            (root / ".env").write_bytes(original)
            tool.run_migration(root, apply=True)
            backups = list((root / "logs/run/runtime-config-backups").glob("*.env"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)

    def test_dotenv_comments_escapes_interpolation_and_multiline_match_old_loader(self):
        tool = self.tool()
        text = (
            "MIGRATION_BASE=base-value\n"
            "MIGRATION_UNQUOTED=value # comment\n"
            'MIGRATION_QUOTED="value" # comment\n'
            "MIGRATION_LITERAL='literal\\nsequence'\n"
            "MIGRATION_INTERPOLATED=${MIGRATION_BASE}/suffix\n"
            'MIGRATION_TAB="left\\tright"\n'
            "MIGRATION_MULTILINE='first\nsecond'\n"
            "NODE_EXECUTABLE='node\\npath'\n"
            "WEBUI_SESSION_SECRET='first\nsecond'\n"
        )
        expected = {
            "MIGRATION_BASE": "base-value", "MIGRATION_UNQUOTED": "value",
            "MIGRATION_QUOTED": "value", "MIGRATION_LITERAL": "literal\\nsequence",
            "MIGRATION_INTERPOLATED": "base-value/suffix", "MIGRATION_TAB": "left\tright",
            "MIGRATION_MULTILINE": "first\nsecond", "NODE_EXECUTABLE": "node\\npath",
            "WEBUI_SESSION_SECRET": "first\nsecond",
        }
        with self.source() as (root, _):
            with (root / ".env").open("a", encoding="utf-8") as stream:
                stream.write(text)
            parsed = tool.read_source_values(root)
            self.assertEqual({key: parsed[key] for key in expected}, expected)
            from dotenv import load_dotenv
            from core.storage import runtime_config as store
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PYTHON_DOTENV_DISABLED", None)
                for key in expected:
                    os.environ.pop(key, None)
                load_dotenv(root / ".env", override=False)
                before = {key: os.environ[key] for key in expected}
                tool.run_migration(root, apply=True)
                physical = tool.read_source_values(root)
                with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": physical["TURB_CONFIG_ENCRYPTION_KEY"]}):
                    after = {**store.read_values(), **physical}
                self.assertEqual({key: after[key] for key in expected}, before)
                for key in expected:
                    os.environ.pop(key, None)
                load_dotenv(root / ".env", override=False)
                self.assertEqual(os.environ["NODE_EXECUTABLE"], before["NODE_EXECUTABLE"])
                self.assertEqual(os.environ["WEBUI_SESSION_SECRET"], before["WEBUI_SESSION_SECRET"])

    def test_invalid_dotenv_binding_is_rejected_without_pruning(self):
        tool = self.tool()
        with self.source() as (root, original):
            malformed = original + 'MIGRATION_BROKEN="unterminated\n'
            (root / ".env").write_text(malformed, encoding="utf-8")
            with self.assertRaisesRegex(tool.MigrationError, "invalid_env_assignment"):
                tool.run_migration(root, apply=True)
            self.assertEqual((root / ".env").read_text(encoding="utf-8"), malformed)
            self.assertFalse((root / "logs/run/runtime-config-backups").exists())

    def test_ambient_different_database_or_schema_refuses_to_migrate_or_prune(self):
        tool = self.tool()
        for updates in ({"DATABASE_URL": "postgresql://fixture.invalid/other"}, {"TURB_DB_SCHEMA": "test_wrong_target"}):
            with self.subTest(keys=sorted(updates)), self.source() as (root, original), patch.dict(os.environ, updates):
                with self.assertRaisesRegex(tool.MigrationError, "target_mismatch"):
                    tool.run_migration(root, apply=True)
                self.assertEqual((root / ".env").read_text(encoding="utf-8"), original)
                self.assertFalse((root / "logs/run/runtime-config-backups").exists())

    def test_runtime_explicit_environment_override_matches_old_startup(self):
        tool = self.tool()
        with self.source() as (root, _), patch.dict(os.environ, {"RUNTIME_TEST_SETTING": "effective-environment-value"}):
            tool.run_migration(root, apply=True)
            from core.storage import runtime_config as store
            key = tool.read_source_values(root)["TURB_CONFIG_ENCRYPTION_KEY"]
            with patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": key}):
                self.assertEqual(store.read_values()["RUNTIME_TEST_SETTING"], "effective-environment-value")

    def test_crlf_multiline_matches_standard_file_loading(self):
        tool = self.tool()
        from dotenv.main import DotEnv
        with self.source() as (root, original):
            text = original + "MIGRATION_MULTILINE='first\r\nsecond'\r\n"
            (root / ".env").write_bytes(text.replace("\n", "\r\n").replace("\r\r\n", "\r\n").encode())
            standard = DotEnv(root / ".env", override=False).dict()
            self.assertEqual(tool.read_source_values(root)["MIGRATION_MULTILINE"], standard["MIGRATION_MULTILINE"])

    def test_source_target_context_does_not_inherit_production_permission(self):
        tool = self.tool()
        with self.source() as (root, _), patch.dict(os.environ, {"TURB_ALLOW_PRODUCTION_DB": "1"}):
            from core.storage import runtime_config as store
            observed = []
            original_transaction = store.transaction

            @contextmanager
            def transaction():
                observed.append(os.getenv("TURB_ALLOW_PRODUCTION_DB"))
                with original_transaction() as conn:
                    yield conn

            with patch.object(store, "transaction", transaction):
                tool.run_migration(root, apply=True)
            self.assertTrue(observed)
            self.assertTrue(all(value is None for value in observed))
            self.assertEqual(os.environ["TURB_ALLOW_PRODUCTION_DB"], "1")
