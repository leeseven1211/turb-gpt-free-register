"""Real PostgreSQL transaction scope for the opt-in plan-check JIT setting.

The observer reads the executing connection and then runs the original SQL.
No assertion relies on the presence or spelling of a SET statement.
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import psycopg
from psycopg.pq import TransactionStatus

from core.storage.operations import bulk, bulk_common as common, bulk_selections
from tests.bulk import test_plan_check_preflight_policy as policy_tests
from tests.support_pg import PostgresTestCase


class FreezeAborted(RuntimeError):
    pass


class PlanCheckPreflightJitTests(PostgresTestCase):
    account = policy_tests.PlanCheckPreflightPolicyTests.account
    selection = policy_tests.PlanCheckPreflightPolicyTests.selection
    rows = policy_tests.PlanCheckPreflightPolicyTests.rows

    def setUp(self):
        bulk.reset_ready()
        bulk.init()

    @staticmethod
    def state(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('jit') AS jit, pg_backend_pid() AS pid")
            return dict(cur.fetchone())

    @contextmanager
    def session(self, initial, *, plan_mode="auto"):
        # Keep this exact physical connection until after commit/rollback has
        # been checked; a fresh pool checkout could hide leaked settings.
        with common.connect() as conn:
            original = self.state(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT current_setting('plan_cache_mode') AS mode")
                original_mode = cur.fetchone()["mode"]
                cur.execute("SELECT set_config('jit', %s, false), "
                            "set_config('plan_cache_mode', %s, false)", (initial, plan_mode))
            conn.commit()
            threshold = conn.prepare_threshold
            conn.prepare_threshold = 0

            @contextmanager
            def transaction():
                self.assertEqual(TransactionStatus.IDLE, conn.info.transaction_status)
                with conn.transaction():
                    yield conn

            try:
                with patch.object(bulk_selections, "connect", transaction):
                    yield conn, original["pid"]
            finally:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('jit', %s, false), "
                                "set_config('plan_cache_mode', %s, false)",
                                (original["jit"], original_mode))
                conn.commit()
                conn.prepare_threshold = threshold

    @contextmanager
    def observe_target_writes(self, conn, *, abort_after_write=False):
        original_execute = psycopg.Cursor.execute
        observations = []
        target_table = common.table("operation_selection_targets")

        def execute(cur, query, *args, **kwargs):
            # Only locate the real write under test; never fake its result or
            # infer the setting from SQL text. The probe uses a separate cursor
            # on the same connection so RETURNING remains available to callers.
            target_write = (cur.connection is conn and isinstance(query, str)
                            and "INSERT INTO " + target_table in query)
            if target_write:
                with conn.cursor() as probe:
                    original_execute(probe, "SELECT current_setting('jit') AS jit, pg_backend_pid() AS pid")
                    before = dict(probe.fetchone())
            result = original_execute(cur, query, *args, **kwargs)
            if target_write:
                with conn.cursor() as probe:
                    original_execute(probe, "SELECT current_setting('jit') AS jit, pg_backend_pid() AS pid")
                    after = dict(probe.fetchone())
                observations.append((before, after))
                if abort_after_write:
                    # Make PostgreSQL abort the real transaction, rather than
                    # merely raising a Python exception around a healthy one.
                    with conn.cursor() as probe:
                        original_execute(probe, "SELECT 1 / 0")
            return result

        with patch.object(psycopg.Cursor, "execute", execute):
            yield observations

    def assert_writes(self, observations, *, jit, pid):
        self.assertTrue(observations, "no actual target-writing statement was observed")
        self.assertTrue(all(before == after == {"jit": jit, "pid": pid}
                            for before, after in observations), observations)

    def assert_ready_targets(self, selected, ids, *, receipts):
        parent, targets = self.rows(selected)
        self.assertEqual("ready", parent["status"])
        self.assertEqual(ids, [target["target_id"] for target in targets])
        self.assertEqual(len(ids), parent["total_count"])
        if receipts:
            self.assertEqual({"ready": len(ids), "waiting_account": 0, "not_executable": 0},
                             parent["preflight_summary"])
            for target in targets:
                self.assertEqual("ready", target["match_evidence"]["preflight"]["status"])
                self.assertEqual(target["id"], target["match_evidence"]["preflight"]["target_id"])

    @staticmethod
    def prepared_counts(conn):
        with conn.cursor() as cur:
            cur.execute("""SELECT COALESCE(sum(generic_plans),0)::bigint AS generic,
                COALESCE(sum(custom_plans),0)::bigint AS custom
                FROM pg_prepared_statements WHERE statement LIKE %s AND statement LIKE %s""",
                        ("%policy_input AS MATERIALIZED%",
                         "%INSERT INTO " + common.table("operation_selection_targets") + "%"))
            return dict(cur.fetchone())

    def test_opt_in_freeze_disables_jit_and_commit_restores_same_session(self):
        for initial in ("on", "off"):
            for plan_mode in ("auto", "force_generic_plan", "force_custom_plan"):
                with self.subTest(initial=initial, plan_mode=plan_mode):
                    ids = [self.account(f"jit-{initial}-{plan_mode}")]
                    selected = self.selection(ids)
                    with self.session(initial, plan_mode=plan_mode) as (conn, pid):
                        prepared_before = self.prepared_counts(conn)
                        conn.commit()
                        with self.observe_target_writes(conn) as observed:
                            result = bulk.freeze_selection(selected["id"], preflight_policy="plan_check_db_v1")
                        self.assertEqual("ready", result["state"])
                        self.assertEqual(TransactionStatus.IDLE, conn.info.transaction_status)
                        self.assert_writes(observed, jit="off", pid=pid)
                        self.assertEqual({"jit": initial, "pid": pid}, self.state(conn))
                        conn.commit()
                        # Reuse the same backend for a later unrelated query.
                        self.assertEqual({"jit": initial, "pid": pid}, self.state(conn))
                        prepared_after = self.prepared_counts(conn)
                        if plan_mode != "auto":
                            counter = "generic" if plan_mode == "force_generic_plan" else "custom"
                            self.assertGreater(prepared_after[counter], prepared_before[counter],
                                               (plan_mode, prepared_before, prepared_after))
                    self.assert_ready_targets(selected, ids, receipts=True)

    def test_sql_error_after_real_insert_rolls_back_data_and_local_setting(self):
        for initial in ("on", "off"):
            with self.subTest(initial=initial):
                selected = self.selection([self.account(f"rollback-{initial}")])
                before = self.rows(selected)
                with self.session(initial) as (conn, pid):
                    with self.observe_target_writes(conn, abort_after_write=True) as observed:
                        with self.assertRaises(psycopg.errors.DivisionByZero):
                            bulk.freeze_selection(selected["id"], preflight_policy="plan_check_db_v1")
                    self.assertEqual(TransactionStatus.IDLE, conn.info.transaction_status)
                    self.assert_writes(observed, jit="off", pid=pid)
                    self.assertEqual({"jit": initial, "pid": pid}, self.state(conn))
                self.assertEqual(before, self.rows(selected))

    def test_generic_other_operation_and_custom_callback_keep_session_setting(self):
        for initial in ("on", "off"):
            for operation, custom in (("plan_check", False), ("token_refresh", False), ("plan_check", True)):
                with self.subTest(initial=initial, operation=operation, custom=custom):
                    ids = [self.account(f"unchanged-{initial}-{operation}-{custom}")]
                    selected = self.selection(ids, operation=operation)
                    callback_states = []

                    def callback(targets, active_conn):
                        callback_states.append(self.state(active_conn))
                        return [{"target_id": target["id"], "status": "ready", "reason_code": None,
                                 "blocker_run_id": None, "checked_at": "2026-11-14T00:00:00"}
                                for target in targets]

                    with self.session(initial) as (conn, pid):
                        with self.observe_target_writes(conn) as observed:
                            bulk.freeze_selection(selected["id"], **({"preflight": callback} if custom else {}))
                        self.assert_writes(observed, jit=initial, pid=pid)
                        self.assertEqual({"jit": initial, "pid": pid}, self.state(conn))
                        self.assertEqual([{"jit": initial, "pid": pid}] if custom else [], callback_states)
                    self.assert_ready_targets(selected, ids, receipts=custom)

    def test_unicode_policy_fallback_stays_local_to_opt_in_transaction(self):
        ids = [self.account("unicode-jit", email="\u212aelvin-jit@example.test")]
        selected = self.selection(ids)
        with self.session("on") as (conn, pid):
            with self.observe_target_writes(conn) as observed:
                bulk.freeze_selection(selected["id"], preflight_policy="plan_check_db_v1")
            # The unsupported fast path writes nothing, then the generic INSERT
            # and real Python receipts finish in this same opted-in transaction.
            self.assertEqual(2, len(observed))
            self.assert_writes(observed, jit="off", pid=pid)
            self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
        self.assert_ready_targets(selected, ids, receipts=True)

    def test_policy_operation_guard_rejects_without_persisted_changes(self):
        selected = self.selection([self.account("wrong-operation")], operation="token_refresh")
        before = self.rows(selected)
        with self.session("on") as (conn, pid):
            with self.assertRaises(common.BulkError) as error:
                bulk.freeze_selection(selected["id"], preflight_policy="plan_check_db_v1")
            self.assertEqual("preflight_policy_operation_mismatch", error.exception.code)
            self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
        self.assertEqual(before, self.rows(selected))

    def test_savepoint_restore_and_separate_backend_keep_settings_scoped(self):
        selected = self.selection([self.account("savepoint")])
        before = self.rows(selected)
        with self.session("on") as (conn, pid), common.connect() as other:
            with other.cursor() as cur:
                cur.execute("SET LOCAL jit=on")
            other_state = self.state(other)
            self.assertNotEqual(pid, other_state["pid"])
            self.assertEqual("on", other_state["jit"])

            @contextmanager
            def savepoint_connection():
                # Only the test adapter nests the transaction. The public
                # production entry point continues to own its connection.
                with conn.transaction():
                    yield conn

            with conn.transaction():
                self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
                with self.assertRaisesRegex(FreezeAborted, "before freeze"):
                    # This savepoint predates the production SET LOCAL.
                    with conn.transaction():
                        with patch.object(bulk_selections, "connect", savepoint_connection):
                            with self.observe_target_writes(conn) as observed:
                                bulk.freeze_selection(selected["id"], preflight_policy="plan_check_db_v1")
                        self.assert_writes(observed, jit="off", pid=pid)
                        self.assertEqual({"jit": "off", "pid": pid}, self.state(conn))
                        self.assertEqual(other_state, self.state(other))
                        with conn.cursor() as cur:
                            cur.execute(f"SELECT count(*) AS total FROM {common.table('operation_selection_targets')} "
                                        "WHERE selection_id=%s", (selected["id"],))
                            self.assertEqual(1, cur.fetchone()["total"])

                        with self.assertRaisesRegex(FreezeAborted, "after freeze"):
                            # A newer savepoint must restore the established
                            # off setting, not the session's original on value.
                            with conn.transaction():
                                with conn.cursor() as cur:
                                    cur.execute("SET LOCAL jit=on")
                                self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
                                raise FreezeAborted("after freeze")
                        self.assertEqual({"jit": "off", "pid": pid}, self.state(conn))
                        raise FreezeAborted("before freeze")
                self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
                self.assertEqual(other_state, self.state(other))
                with conn.cursor() as cur:
                    cur.execute(f"SELECT count(*) AS total FROM {common.table('operation_selection_targets')} "
                                "WHERE selection_id=%s", (selected["id"],))
                    self.assertEqual(0, cur.fetchone()["total"])
            self.assertEqual(TransactionStatus.IDLE, conn.info.transaction_status)
            self.assertEqual({"jit": "on", "pid": pid}, self.state(conn))
        self.assertEqual(before, self.rows(selected))
