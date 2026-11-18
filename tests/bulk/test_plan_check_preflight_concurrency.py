"""Real PostgreSQL concurrency contracts for the opt-in plan-check freeze.

The INSERT gate only schedules two real database sessions. It never changes
the production eligibility query, receipts, or transaction isolation level.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import threading
import time
import uuid
from unittest.mock import patch

from core.storage import records
from core.storage.operations import bulk, bulk_common as common, bulk_selections
from tests.bulk import test_plan_check_preflight_policy as policy_tests
from tests.support_pg import PostgresTestCase


class PlanCheckPreflightConcurrencyTests(PostgresTestCase):
    # Import the module, not its TestCase class: unittest must not discover and
    # rerun the separate policy suite when it loads this module.
    account = policy_tests.PlanCheckPreflightPolicyTests.account
    selection = policy_tests.PlanCheckPreflightPolicyTests.selection
    freeze = policy_tests.PlanCheckPreflightPolicyTests.freeze
    rows = policy_tests.PlanCheckPreflightPolicyTests.rows

    def setUp(self):
        bulk.reset_ready()
        bulk.init()

    @contextmanager
    def bounded_connection(self):
        with common.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='20s'")
                cur.execute("SET LOCAL statement_timeout='30s'")
            yield conn

    @contextmanager
    def insert_gate(self, selection_id):
        suffix = uuid.uuid4().hex[:12]
        function_name = f"policy_insert_gate_{suffix}"
        trigger_name = f"policy_insert_gate_{suffix}"
        key = (uuid.uuid4().int % 2147483647, uuid.uuid4().int % 2147483647)
        with self.bounded_connection() as conn, conn.cursor() as cur:
            cur.execute(f"""CREATE FUNCTION {common.table(function_name)}()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.selection_id={int(selection_id)} THEN
                    PERFORM pg_advisory_xact_lock({key[0]},{key[1]});
                END IF;
                RETURN NEW; END $$""")
            cur.execute(f"""CREATE TRIGGER {trigger_name} BEFORE INSERT
                ON {common.table('operation_selection_targets')} FOR EACH ROW
                EXECUTE FUNCTION {common.table(function_name)}()""")
        try:
            with self.bounded_connection() as controller:
                with controller.cursor() as cur:
                    cur.execute("SELECT pg_advisory_lock(%s,%s)", key)
                held = True

                def release():
                    nonlocal held
                    if held:
                        with controller.cursor() as cur:
                            cur.execute("SELECT pg_advisory_unlock(%s,%s) AS released", key)
                            self.assertTrue(cur.fetchone()["released"])
                        held = False

                try:
                    yield controller, key, release
                finally:
                    # A failed probe can abort the transaction; the session
                    # lock still belongs to us and must be released explicitly.
                    if held:
                        controller.rollback()
                        with controller.cursor() as cur:
                            cur.execute("SET LOCAL statement_timeout='30s'")
                        release()
        finally:
            with self.bounded_connection() as conn, conn.cursor() as cur:
                cur.execute(f"DROP TRIGGER {trigger_name} ON {common.table('operation_selection_targets')}")
                cur.execute(f"DROP FUNCTION {common.table(function_name)}()")

    @contextmanager
    def freeze_workers(self, selected):
        states = []
        local = threading.local()
        connection_lock = threading.Lock()

        @contextmanager
        def connection():
            state = local.state
            with self.bounded_connection() as conn:
                with connection_lock:
                    state["connection"] = conn
                    state["pid"] = conn.info.backend_pid
                state["started"].set()
                try:
                    yield conn
                finally:
                    with connection_lock:
                        state["connection"] = None

        def start():
            state = {"started": threading.Event(), "done": threading.Event(),
                     "connection": None, "pid": None, "result": None, "error": None}

            def run():
                local.state = state
                try:
                    state["result"] = self.freeze(selected)
                except BaseException as exc:
                    state["error"] = exc
                finally:
                    state["done"].set()

            state["thread"] = threading.Thread(target=run, name=f"policy-freeze-{uuid.uuid4().hex[:8]}")
            states.append(state)
            state["thread"].start()
            self.assertTrue(state["started"].wait(8), "freeze did not open its database session")
            return state

        with patch.object(bulk_selections, "connect", connection):
            try:
                yield start
            finally:
                # Cancellation is only cleanup after a failed assertion or
                # unexpected timeout. The normal path releases the gate and
                # awaits both real database results before reaching here.
                with connection_lock:
                    for state in states:
                        if not state["done"].is_set() and state["connection"] is not None:
                            state["connection"].cancel()
                for state in states:
                    state["thread"].join(timeout=35)
                self.assertFalse(any(state["thread"].is_alive() for state in states),
                                 "freeze worker survived statement timeout and cleanup")

    def wait_for_lock(self, controller, worker, *, key=None, blocker_pid=None):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if worker["done"].is_set():
                if worker["error"] is not None:
                    raise worker["error"]
                self.fail("freeze completed before the required concurrent lock was observed")
            with controller.cursor() as cur:
                if key is not None:
                    cur.execute("""SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s
                        AND locktype='advisory' AND NOT granted AND classid=%s::oid
                        AND objid=%s::oid AND objsubid=2) AS waiting""", (worker["pid"], *key))
                else:
                    cur.execute("SELECT %s=ANY(pg_blocking_pids(%s)) AS waiting", (blocker_pid, worker["pid"]))
                if cur.fetchone()["waiting"]:
                    return
            worker["done"].wait(.02)
        self.fail("did not observe the required PostgreSQL lock before timeout")

    def completed_result(self, worker):
        self.assertTrue(worker["done"].wait(35), "freeze worker exceeded its statement timeout")
        if worker["error"] is not None:
            raise worker["error"]
        return worker["result"]

    def test_statement_snapshot_survives_concurrent_token_run_and_registration_changes(self):
        ids = [self.account(f"concurrent-{name}") for name in ("token", "run", "registration", "ready")]
        selected = self.selection(ids)
        identity = uuid.uuid4().hex
        with self.insert_gate(selected["id"]) as (controller, key, release):
            with self.freeze_workers(selected) as start:
                worker = start()
                self.wait_for_lock(controller, worker, key=key)
                # The INSERT statement is executing and its MVCC snapshot is
                # already fixed. Commit new business facts on another session.
                with self.bounded_connection() as writer, writer.cursor() as cur:
                    self.assertNotEqual(worker["pid"], writer.info.backend_pid)
                    self.assertNotEqual(controller.info.backend_pid, writer.info.backend_pid)
                    cur.execute(f"""UPDATE {records._qualified(records.ACCOUNTS)}
                        SET data=jsonb_set(data,'{{access_token}}','\"\"'::jsonb) WHERE id=%s""", (ids[0],))
                    self.assertEqual(1, cur.rowcount)
                    cur.execute(f"""INSERT INTO {common.table('operation_tasks')}
                        (task_uuid,source_system,source_id,task_type,target_type,account_id,requested_action)
                        VALUES (%s,'policy-test',%s,'plan_check','account',%s,'plan_check') RETURNING id""",
                                (identity, identity, ids[1]))
                    task_id = cur.fetchone()["id"]
                    cur.execute(f"""INSERT INTO {common.table('operation_runs')}
                        (run_uuid,task_id,run_no,source_system,source_id,status,account_id,next_attempt_at)
                        VALUES (%s,%s,1,'policy-test',%s,'waiting',%s,'2099-01-01T00:00:00Z') RETURNING id""",
                                (identity, task_id, identity, ids[1]))
                    blocker = cur.fetchone()["id"]
                    records.insert_row(records.JOBS, {
                        "job_uuid": uuid.uuid4().hex, "account_id": ids[2], "email": "",
                        "status": "pending", "job_type": "registration",
                        "created_at": "2026-10-15T10:00:00", "updated_at": "2026-10-15T10:00:00",
                    }, conn=writer)
                self.assertFalse(worker["done"].is_set())
                release()
                self.assertEqual("ready", self.completed_result(worker)["state"])
        original = self.rows(selected)
        parent, targets = original
        self.assertEqual({"ready": 4, "waiting_account": 0, "not_executable": 0}, parent["preflight_summary"])
        self.assertEqual(ids, [target["target_id"] for target in targets])
        for target in targets:
            check = target["match_evidence"]["preflight"]
            self.assertEqual((target["id"], "ready", None, None),
                             (check["target_id"], check["status"], check["reason_code"], check["blocker_run_id"]))
            self.assertTrue(target["baseline"]["has_access_token"])
            self.assertEqual(parent["selected_at"], datetime.fromisoformat(check["checked_at"]))
            self.assertEqual(parent["selected_at"], datetime.fromisoformat(target["baseline"]["plan_check"]["frozen_at"]))

        # A later selection must observe all three committed changes. The old
        # selection remains an immutable statement snapshot, including replay.
        latest = self.selection(ids)
        with patch.object(bulk_selections, "connect", self.bounded_connection):
            self.freeze(latest)
            self.freeze(selected)
        latest_parent, latest_targets = self.rows(latest)
        self.assertEqual({"ready": 1, "waiting_account": 2, "not_executable": 1}, latest_parent["preflight_summary"])
        expected = [("not_executable", "access_token_missing", None), ("waiting_account", "account_busy", blocker),
                    ("waiting_account", "registration_in_progress", None), ("ready", None, None)]
        for target, wanted in zip(latest_targets, expected, strict=True):
            check = target["match_evidence"]["preflight"]
            self.assertEqual(wanted, (check["status"], check["reason_code"], check["blocker_run_id"]))
        self.assertFalse(latest_targets[0]["baseline"]["has_access_token"])
        self.assertEqual(original, self.rows(selected))

    def test_concurrent_freeze_replay_returns_identical_selection_without_duplicate_targets(self):
        ids = [self.account(f"replay-{number}") for number in range(3)]
        selected = self.selection(ids)
        with self.insert_gate(selected["id"]) as (controller, key, release):
            with self.freeze_workers(selected) as start:
                first = start()
                self.wait_for_lock(controller, first, key=key)
                second = start()
                self.assertNotEqual(first["pid"], second["pid"])
                self.wait_for_lock(controller, second, blocker_pid=first["pid"])
                release()
                first_result = self.completed_result(first)
                second_result = self.completed_result(second)
        self.assertEqual(first_result, second_result)
        self.assertEqual("ready", first_result["state"])
        self.assertEqual(3, first_result["target_count"])
        parent, targets = self.rows(selected)
        self.assertEqual({"ready": 3, "waiting_account": 0, "not_executable": 0}, parent["preflight_summary"])
        self.assertEqual(ids, [target["target_id"] for target in targets])
        self.assertEqual([1, 2, 3], [target["ordinal"] for target in targets])
        self.assertEqual(3, len({target["id"] for target in targets}))
        self.assertEqual([target["id"] for target in targets],
                         [target["match_evidence"]["preflight"]["target_id"] for target in targets])
        with self.bounded_connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS total FROM {common.table('operation_selection_targets')}")
            self.assertEqual(3, cur.fetchone()["total"])
            cur.execute(f"SELECT last_value FROM {common.table('operation_selection_targets_id_seq')}")
            self.assertEqual(max(target["id"] for target in targets), cur.fetchone()["last_value"])
        before = self.rows(selected)
        with patch.object(bulk_selections, "connect", self.bounded_connection):
            self.freeze(selected)
        self.assertEqual(before, self.rows(selected))
