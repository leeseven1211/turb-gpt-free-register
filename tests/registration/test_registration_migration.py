"""Exercise registration migration at cold startup and from the maintenance CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import psycopg
from psycopg.conninfo import make_conninfo

from core import account_task_store, db, operation_task_store
from core.storage import postgres, records, registration
from core.storage.operations import schema as operation_schema
from tests.support_pg import PostgresTestCase, drop_schema, temporary_schema_name


class RegistrationMigrationTests(PostgresTestCase):
    def setUp(self):
        registration.reset_ready()

    def _new_schema(self, label):
        name = temporary_schema_name(label)
        self.addCleanup(drop_schema, name)
        return name

    def _version(self):
        with postgres.connect() as conn:
            table = postgres.qualified("registration_schema_migrations")
            if conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None:
                return []
            return conn.execute(f"SELECT version FROM {table} ORDER BY version").fetchall()

    def test_cold_process_reads_durable_version_while_registration_tables_are_locked(self):
        registration.init()
        self.assertEqual([(1,)], self._version())
        reader = make_conninfo(postgres.database_url(), options="-c default_transaction_read_only=on -c lock_timeout=200ms")
        with postgres.connect() as holder:
            holder.execute(f"LOCK TABLE {postgres.qualified('registration_jobs')}, "
                           f"{postgres.qualified('registration_attempts')} IN ACCESS EXCLUSIVE MODE")
            with patch.dict(os.environ, DATABASE_URL=reader):
                registration.reset_ready()
                registration.init()

    def test_contested_migration_rolls_back_and_can_be_retried(self):
        business = self._new_schema("reg_collision")
        with patch.dict(os.environ, TURB_DB_SCHEMA=business):
            records.init()
            jobs = postgres.qualified("registration_jobs")
            with postgres.connect() as holder:
                holder.execute(f"SELECT id FROM {jobs} LIMIT 1")
                started = time.monotonic()
                # PGOPTIONS bounds the old implementation as well so this test cannot hang.
                bounded = make_conninfo(postgres.database_url(), options="-c statement_timeout=5s")
                with patch.dict(os.environ, DATABASE_URL=bounded):
                    with self.assertRaises(psycopg.errors.LockNotAvailable):
                        registration.init()
                self.assertLess(time.monotonic() - started, 4.5)
                self.assertEqual([], self._version())
                self.assertIsNone(holder.execute("SELECT to_regclass(%s)",
                                  (postgres.qualified("registration_attempts"),)).fetchone()[0])
            registration.init()
            self.assertEqual([(1,)], self._version())

    def test_first_install_failure_rolls_back_shared_tables_and_retries(self):
        schema = self._new_schema("reg_first_rollback")
        with patch.dict(os.environ, TURB_DB_SCHEMA=schema):
            with patch.object(registration, "_migrate_legacy_checkpoints", side_effect=ValueError("bad checkpoint")):
                with self.assertRaisesRegex(ValueError, "bad checkpoint"):
                    registration.init()
            with postgres.connect() as conn:
                self.assertIsNone(conn.execute("SELECT to_regnamespace(%s)", (schema,)).fetchone()[0])
            registration.init()
            self.assertEqual([(1,)], self._version())
            postgres.save_collection("registration_test", {"ok": True})
            self.assertEqual((True, {"ok": True}), postgres.load_collection("registration_test"))

    def test_independent_initializers_run_the_checkpoint_migration_once(self):
        schema = self._new_schema("reg_concurrency")
        env = {**os.environ, "TURB_DB_SCHEMA": schema, "PYTHON_DOTENV_DISABLED": "1"}
        script = """
import sys
from core.storage import registration as r
original = r._migrate_legacy_checkpoints
def instrument(cur):
    print('migrating', flush=True)
    return original(cur)
r._migrate_legacy_checkpoints = instrument
print('ready', flush=True)
sys.stdin.readline()
r.init()
"""
        with subprocess.Popen([sys.executable, "-c", script], env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as first, \
             subprocess.Popen([sys.executable, "-c", script], env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as second:
            for child in (first, second):
                self.assertEqual("ready\n", child.stdout.readline())
            for child in (first, second):
                child.stdin.write("\n")
                child.stdin.flush()
            outputs = [child.communicate(timeout=12) for child in (first, second)]
        self.assertEqual([0, 0], [first.returncode, second.returncode], outputs)
        self.assertEqual(1, sum(stdout.count("migrating") for stdout, _ in outputs))

    def test_first_write_initializes_an_empty_business_schema(self):
        business = self._new_schema("first_job")
        with patch.dict(os.environ, TURB_DB_SCHEMA=business, OPERATION_TASK_DB_SCHEMA=business), \
             patch.object(account_task_store, "_SCHEMA", business):
            job = db.create_job("outlook")
            with postgres.connect() as conn:
                rows = conn.execute(
                    f"SELECT j.id,a.id,r.job_id FROM {postgres.qualified('registration_jobs')} j "
                    f"JOIN {postgres.qualified('registration_attempts')} a ON a.id=j.attempt_id "
                    f"JOIN {postgres.qualified('registration_runs')} r ON r.attempt_id=a.id",
                ).fetchall()
            self.assertEqual([(job["id"], job["attempt_id"], job["id"])], rows)
            self.assertEqual([(1,)], self._version())

    def test_operation_upgrade_and_registration_initializer_share_the_attempt_table(self):
        schema = self._new_schema("reg_operation_race")
        with patch.dict(os.environ, TURB_DB_SCHEMA=schema, OPERATION_TASK_DB_SCHEMA=schema), \
             patch.object(account_task_store, "_SCHEMA", schema), ThreadPoolExecutor(max_workers=1) as pool:
            apply_operation = operation_schema._apply_operation_schema
            registration_upgrade = None

            def overlap(cur):
                nonlocal registration_upgrade
                apply_operation(cur)
                registration_upgrade = pool.submit(registration.init)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    cur.execute(
                        "SELECT 1 FROM pg_locks WHERE NOT granted "
                        "AND pg_backend_pid() = ANY(pg_blocking_pids(pid)) LIMIT 1"
                    )
                    if cur.fetchone():
                        return
                    time.sleep(.01)
                self.fail("registration did not reach the uncommitted operation schema")

            with patch.object(operation_schema, "_apply_operation_schema", overlap):
                operation_task_store.init()
            registration_upgrade.result(timeout=5)
            self.assertEqual([(1,)], self._version())

    def test_business_migration_is_independent_of_operation_schema(self):
        operation = self._new_schema("op_reg_scope")
        with patch.dict(os.environ, OPERATION_TASK_DB_SCHEMA=operation), \
             patch.object(account_task_store, "_SCHEMA", self.schema):
            registration.init()
            operation_task_store.init()
            self.assertEqual([(1,)], self._version())
            with postgres.connect() as conn:
                self.assertIsNone(conn.execute("SELECT to_regclass(%s)",
                    (f"{operation}.registration_schema_migrations",)).fetchone()[0])
                self.assertIsNotNone(conn.execute("SELECT to_regclass(%s)",
                    (f"{operation}.operation_tasks",)).fetchone()[0])

    def test_actual_cli_inspects_empty_and_legacy_schemas_without_writes(self):
        script = Path(__file__).resolve().parents[2] / "tools" / "migrations" / "migrate_registration_attempts.py"
        schema = self._new_schema("reg_cli")
        with patch.dict(os.environ, TURB_DB_SCHEMA=schema):
            def cli(*flags, writer=False, expected=0):
                dsn = postgres.database_url()
                if not writer:
                    dsn = make_conninfo(dsn, options="-c default_transaction_read_only=on")
                result = subprocess.run([sys.executable, str(script), "--json", *flags],
                    env={**os.environ, "DATABASE_URL": dsn, "PYTHON_DOTENV_DISABLED": "1"},
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(expected, result.returncode, result.stderr)
                return json.loads(result.stdout)

            self.assertEqual(0, cli()["backfill"]["jobs"])
            self.assertFalse(cli("--verify", expected=2)["verification"]["ok"])
            with postgres.connect() as conn:
                self.assertIsNone(conn.execute("SELECT to_regnamespace(%s)", (schema,)).fetchone()[0])
            records.init()
            records.insert_row(records.JOBS, {"status": "failed", "job_type": "registration"})
            self.assertEqual(1, cli()["backfill"]["jobs"])
            self.assertFalse(cli("--verify", expected=2)["verification"]["ok"])
            self.assertEqual([], self._version())
            self.assertTrue(cli("--apply", writer=True)["verification"]["ok"])
            self.assertTrue(cli("--verify")["verification"]["ok"])
