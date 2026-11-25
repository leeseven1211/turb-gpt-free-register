"""注册批量重试的后处理受理必须共享集合事务和原父任务身份。"""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import replace
from unittest.mock import patch

from psycopg import Cursor

from core import db
from core.storage import records, registration
from core.storage.operations import store
from tests.support_pg import PostgresTestCase


class RegistrationRetryFollowupsStoreTests(PostgresTestCase):
    def setUp(self):
        store.reset_ready()
        store.init()
        self.seed(records.ACCOUNTS, [
            {"id": index, "email": f"followup-{index}@example.test", "access_token": "private-at",
             "status": "success", "plan_check_status": "failed"}
            for index in range(1, 64)
        ])

    def api(self):
        name = "core.storage.registration.retry_followups"
        self.assertIsNotNone(importlib.util.find_spec(name), "缺少注册后处理集合受理边界")
        return importlib.import_module(name)

    def source(self, account_id):
        address = f"followup-{account_id}@example.test"
        source_id = records.insert_row(records.JOBS, {
            "email": address, "email_source": "outlook", "account_id": account_id,
            "status": "partial_success", "job_type": "registration",
        })
        parent = store.create_runtime_task(
            task_type="registration", account_id=None, email=address,
            source_system="registration_jobs", source_id=str(source_id),
            resource_family="registration_chain",
        )
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='partial_success' WHERE id=%s",
                        (parent["id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='partial_success' WHERE id=%s",
                        (parent["run"]["id"],))
        return db.get_job(source_id), parent

    def spec(self, account_id, action, *, source=None, data=None, snapshot=None):
        api = self.api()
        source = source or self.source(account_id)[0]
        return api.RetryFollowup(
            source=source, account=db.get_account(account_id), action=action,
            data=data or ({"steps": ["twofa"], "source_job_id": source["id"],
                          "task_trigger": "registration_job_retry"} if action == "twofa" else {}),
            config_snapshot=snapshot or {
                "password_driver": "protocol", "twofa_driver": "protocol",
                "private_connection_secret": "must-not-persist",
            },
            config_allowlist=("password_driver", "twofa_driver"),
        )

    def rows(self, name):
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {store._table(name)} ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def test_mixed_followups_keep_parent_identity_and_atomic_business_projections(self):
        api = self.api()
        records.patch_row(records.ACCOUNTS, 2, {"codex_credential_state": "valid",
            "codex_status": "success", "updated_at": "2026-01-01T00:00:00"})
        specs = [self.spec(1, "plan_check"), self.spec(2, "codex"), self.spec(3, "twofa")]
        replies = api.admit(specs)
        self.assertTrue(all(reply["accepted"] for reply in replies.values()), replies)
        tasks = {task["id"]: task for task in self.rows("operation_tasks")}
        for spec in specs:
            reply = replies[spec.source["id"]]
            task = tasks[reply["task_id"]]
            run = store.get_run(reply["run_id"])
            self.assertEqual(task["account_id"], spec.account["id"])
            self.assertEqual(run["status"], "queued")
            self.assertNotIn("private_connection_secret", run["data"]["config_snapshot"])
            self.assertNotIn("private-at", str(task["data"]) + str(run["data"]))
            if spec.action == "plan_check":
                self.assertIsNone(task["parent_task_id"])
            else:
                parent = store.find_task_by_source("registration_jobs", str(spec.source["id"]))
                self.assertEqual(task["parent_task_id"], parent["id"])
                self.assertEqual(task["root_task_id"], parent["root_task_id"])
        plan = db.get_account(1)
        self.assertEqual(plan["plan_check_status"], "queued")
        self.assertEqual(plan["plan_check_trigger"], "registration_retry_plan_check")
        codex = db.get_account(2)
        self.assertEqual((codex["codex_status"], codex["codex_execution_status"]), ("success", "queued"))
        self.assertEqual(codex["codex_active_run_id"], replies[specs[1].source["id"]]["run_id"])
        self.assertNotEqual(codex["updated_at"], "2026-01-01T00:00:00")
        setup_reply = replies[specs[2].source["id"]]
        self.assertEqual(db.get_job(specs[2].source["id"])["registration_account_task_id"], setup_reply["task_id"])

    def test_setup_reuses_compatible_active_run_then_appends_to_the_same_terminal_task(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        fresh = self.spec(1, "twofa", source=db.get_job(spec.source["id"]))
        reused = api.admit([fresh])[spec.source["id"]]
        self.assertTrue(reused["reused"])
        self.assertEqual((reused["task_id"], reused["run_id"]), (first["task_id"], first["run_id"]))
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {store._table('operation_runs')} SET status='failed',
                data=data || '{{"prior_only":"kept","remote_intent":{{"kind":"remote_write"}},
                                  "remote_receipt":{{"outcome":"unknown"}}}}'::jsonb WHERE id=%s""",
                        (first["run_id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first["task_id"],))
        next_spec = self.spec(1, "twofa", source=db.get_job(spec.source["id"]),
            data={"steps": ["password"], "source_job_id": spec.source["id"]})
        appended = api.admit([next_spec])[spec.source["id"]]
        self.assertTrue(appended["accepted"])
        self.assertFalse(appended["reused"])
        self.assertEqual(appended["task_id"], first["task_id"])
        run = store.get_run(appended["run_id"])
        self.assertEqual(run["run_no"], 2)
        self.assertEqual(run["data"]["prior_only"], "kept")
        self.assertEqual(run["data"]["steps"], ["password"])
        self.assertNotIn("remote_intent", run["data"])
        self.assertNotIn("remote_receipt", run["data"])

    def test_initial_parent_link_does_not_rewrite_the_original_registration_run(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        parent = store.find_task_by_source("registration_jobs", str(spec.source["id"]))
        before = {row["id"]: row for row in self.rows("operation_tasks")}[parent["id"]]
        reply = api.admit([spec])[spec.source["id"]]
        self.assertTrue(reply["accepted"])
        after = {row["id"]: row for row in self.rows("operation_tasks")}[parent["id"]]
        self.assertEqual((after["status"], after["last_run_id"]), (before["status"], before["last_run_id"]))

    def test_reused_setup_without_parent_repairs_its_link_and_waiting_parent(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=NULL,root_task_id=id WHERE id=%s",
                        (first["task_id"],))
        fresh = self.spec(1, "twofa", source=db.get_job(spec.source["id"]))
        reused = api.admit([fresh])[spec.source["id"]]
        self.assertTrue(reused["reused"])
        parent = store.find_task_by_source("registration_jobs", str(spec.source["id"]))
        task = {row["id"]: row for row in self.rows("operation_tasks")}[reused["task_id"]]
        self.assertEqual(task["parent_task_id"], parent["id"])
        self.assertEqual(task["root_task_id"], parent["root_task_id"])
        self.assertEqual({row["id"]: row for row in self.rows("operation_tasks")}[parent["id"]]["status"], "waiting")

    def test_setup_does_not_switch_an_active_driver_or_country(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        incompatible = self.spec(1, "twofa", source=db.get_job(spec.source["id"]),
            snapshot={"password_driver": "roxy", "twofa_driver": "browser"})
        reply = api.admit([incompatible])[spec.source["id"]]
        self.assertFalse(reply["accepted"])
        self.assertIn("驱动", reply["error"])
        runs = [row for row in self.rows("operation_runs") if row["task_id"] == first["task_id"]]
        self.assertEqual(len(runs), 1)

    def test_terminal_setup_task_deactivation_still_blocks_appending_a_new_run(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed',target_status='account_deactivated' WHERE id=%s",
                        (first["task_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                        (first["run_id"],))
        reply = api.admit([self.spec(1, "twofa", source=db.get_job(spec.source["id"]))])[spec.source["id"]]
        self.assertFalse(reply["accepted"])
        self.assertIn("废号", reply["error"])
        self.assertEqual(len([row for row in self.rows("operation_runs") if row["task_id"] == first["task_id"]]), 1)

    def test_fresh_followup_keeps_the_existing_waiting_coordinator_admission_policy(self):
        api = self.api()
        spec = self.spec(1, "codex")
        coordinator = store.create_runtime_task(task_type="fixture_coordinator", account_id=1,
            email="followup-1@example.test", resource_family="openai_interactive")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='waiting' WHERE id=%s",
                        (coordinator["run"]["id"],))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='waiting' WHERE id=%s",
                        (coordinator["id"],))
        reply = api.admit([spec])[spec.source["id"]]
        self.assertTrue(reply["accepted"], reply)
        self.assertNotEqual(reply["task_id"], coordinator["id"])

    def test_stopping_setup_is_busy_and_cannot_be_reported_as_a_reused_run(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='stopping' WHERE id=%s",
                        (first["task_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='stopping' WHERE id=%s",
                        (first["run_id"],))
        reply = api.admit([self.spec(1, "twofa", source=db.get_job(spec.source["id"]))])[spec.source["id"]]
        self.assertFalse(reply["accepted"])
        self.assertFalse(reply["reused"])
        self.assertTrue(reply["busy"])

    def test_active_setup_run_is_reused_when_its_task_projection_has_not_caught_up(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first["task_id"],))
        reply = api.admit([self.spec(1, "twofa", source=db.get_job(spec.source["id"]))])[spec.source["id"]]
        self.assertTrue(reply["accepted"], reply)
        self.assertTrue(reply["reused"])
        self.assertEqual(reply["run_id"], first["run_id"])

    def test_older_waiting_run_remains_current_when_a_later_historical_run_failed(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='waiting' WHERE id=%s",
                        (first["run_id"],))
            cur.execute(f"""INSERT INTO {store._table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,status,account_id,resource_family,data)
                SELECT 'synthetic-later-failed',task_id,2,source_system,'synthetic-later-failed',
                    'failed',account_id,resource_family,data
                FROM {store._table('operation_runs')} WHERE id=%s RETURNING id""", (first["run_id"],))
            later = cur.fetchone()["id"]
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed',last_run_id=%s WHERE id=%s",
                        (later, first["task_id"]))
        reply = api.admit([self.spec(1, "twofa", source=db.get_job(spec.source["id"]))])[spec.source["id"]]
        self.assertTrue(reply["accepted"], reply)
        self.assertTrue(reply["reused"])
        self.assertEqual(reply["run_id"], first["run_id"])
        self.assertEqual(len([row for row in self.rows("operation_runs") if row["task_id"] == first["task_id"]]), 2)

    def test_changed_identity_missing_token_and_busy_only_reject_the_affected_source(self):
        api = self.api()
        changed = self.spec(1, "twofa")
        tokenless = self.spec(2, "plan_check")
        busy = self.spec(3, "codex")
        eligible = self.spec(4, "plan_check")
        records.patch_row(records.ACCOUNTS, 1, {"email": "changed@example.test"})
        records.patch_row(records.ACCOUNTS, 2, {"access_token": ""})
        store.create_runtime_task(task_type="fixture", account_id=3,
            email="followup-3@example.test", resource_family="openai_interactive")
        replies = api.admit([changed, tokenless, busy, eligible])
        self.assertFalse(replies[changed.source["id"]]["accepted"])
        self.assertFalse(replies[tokenless.source["id"]]["accepted"])
        self.assertTrue(replies[busy.source["id"]]["busy"])
        active = [row for row in self.rows("operation_runs") if row["account_id"] == 3][0]
        self.assertEqual(replies[busy.source["id"]]["task_id"], active["task_id"])
        self.assertEqual(replies[busy.source["id"]]["run_id"], active["id"])
        self.assertTrue(replies[eligible.source["id"]]["accepted"])
        self.assertEqual(db.get_account(2)["plan_check_status"], "failed")

    def test_plan_stage_claim_failure_does_not_create_a_task_or_change_the_account(self):
        api = self.api()
        records.patch_row(records.ACCOUNTS, 1, {"plan_check_status": "queued",
            "plan_check_queued_at": "2099-01-01T00:00:00"})
        spec = self.spec(1, "plan_check")
        before = db.get_account(1)
        task_count = len(self.rows("operation_tasks"))
        reply = api.admit([spec])[spec.source["id"]]
        self.assertTrue(reply["busy"])
        self.assertFalse(reply["accepted"])
        self.assertEqual(db.get_account(1), before)
        self.assertEqual(len(self.rows("operation_tasks")), task_count)

    def test_stage_busy_source_does_not_prevent_a_later_different_followup_for_the_account(self):
        api = self.api()
        records.patch_row(records.ACCOUNTS, 1, {"plan_check_status": "queued",
            "plan_check_queued_at": "2099-01-01T00:00:00"})
        first = self.spec(1, "plan_check")
        second = self.spec(1, "codex")
        replies = api.admit([first, second])
        self.assertTrue(replies[first.source["id"]]["busy"])
        self.assertTrue(replies[second.source["id"]]["accepted"], replies)

    def test_linked_attempt_deactivated_after_planning_never_creates_postprocessing(self):
        api = self.api()
        spec = self.spec(1, "codex")
        attempt = registration.create_attempt(
            "followup-1@example.test", root_job_id=spec.source["id"],
            email_source="outlook", driver="protocol_oss_2",
        )
        records.patch_row(records.JOBS, spec.source["id"], {"attempt_id": attempt["id"]})
        spec = replace(spec, source=db.get_job(spec.source["id"]))
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {registration._table('registration_attempts')} SET target_status='deactivated',account_id=1 WHERE id=%s",
                        (attempt["id"],))
        task_count = len(self.rows("operation_tasks"))
        reply = api.admit([spec])[spec.source["id"]]
        self.assertFalse(reply["accepted"])
        self.assertIn("废号", reply["error"])
        self.assertEqual(len(self.rows("operation_tasks")), task_count)

    def test_linked_attempt_and_root_snapshots_are_rechecked_under_the_collection_lock(self):
        api = self.api()
        root = records.insert_row(records.JOBS, {
            "email": "followup-1@example.test", "email_source": "outlook",
            "account_id": 1, "status": "partial_success", "job_type": "registration",
        })
        attempt = registration.create_attempt(
            "followup-1@example.test", root_job_id=root, email_source="outlook", driver="protocol_oss_2",
        )
        records.patch_row(records.JOBS, root, {"attempt_id": attempt["id"]})
        source = records.insert_row(records.JOBS, {
            "root_job_id": root, "parent_job_id": root, "attempt_id": attempt["id"],
            "email": "followup-1@example.test", "email_source": "outlook",
            "account_id": 1, "status": "failed", "job_type": "registration",
        })
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {registration._table('registration_attempts')} SET account_id=1 WHERE id=%s",
                        (attempt["id"],))
        spec = replace(self.spec(1, "codex", source=db.get_job(source)),
                       root=db.get_job(root), attempt=registration.get_attempt(attempt["id"]))
        records.patch_row(records.JOBS, root, {"email_source": "email_butler"})
        reply = api.admit([spec])[source]
        self.assertFalse(reply["accepted"])
        self.assertIn("变化", reply["error"])
        self.assertFalse(any(row["task_type"] == "codex_retry" for row in self.rows("operation_tasks")))

    def test_legacy_child_without_attempt_retains_the_linked_root_dispatch_policy(self):
        api = self.api()
        root = records.insert_row(records.JOBS, {
            "email": "followup-1@example.test", "email_source": "outlook",
            "account_id": 1, "status": "partial_success", "job_type": "registration",
        })
        attempt = registration.create_attempt(
            "followup-1@example.test", root_job_id=root, email_source="outlook", driver="protocol_oss_2",
        )
        records.patch_row(records.JOBS, root, {"attempt_id": attempt["id"]})
        child = records.insert_row(records.JOBS, {
            "root_job_id": root, "parent_job_id": root, "email": "followup-1@example.test",
            "email_source": "outlook", "account_id": 1, "status": "failed", "job_type": "registration",
        })
        spec = replace(self.spec(1, "codex", source=db.get_job(child)),
                       root=db.get_job(root), attempt=registration.get_attempt(attempt["id"]))
        reply = api.admit([spec])[child]
        self.assertTrue(reply["accepted"], reply)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (reply["task_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                        (reply["run_id"],))
            cur.execute(f"UPDATE {registration._table('registration_attempts')} SET target_status='deactivated' WHERE id=%s",
                        (attempt["id"],))
        denied = api.admit([spec])[child]
        self.assertFalse(denied["accepted"])
        self.assertIn("废号", denied["error"])

    def test_optional_connection_keeps_followups_and_parent_receipts_in_caller_transaction(self):
        api = self.api()
        spec = self.spec(1, "twofa")
        before_tasks = self.rows("operation_tasks")
        with self.assertRaisesRegex(RuntimeError, "caller rollback"):
            with store._connect() as conn:
                reply = api.admit([spec], conn=conn)[spec.source["id"]]
                self.assertTrue(reply["accepted"])
                raise RuntimeError("caller rollback")
        self.assertEqual(self.rows("operation_tasks"), before_tasks)
        self.assertIsNone(db.get_job(spec.source["id"]).get("registration_account_task_id"))

    def test_caller_catching_a_python_error_cannot_commit_half_a_followup_collection(self):
        api = self.api()
        spec = self.spec(1, "plan_check")
        before_tasks, before_runs = self.rows("operation_tasks"), self.rows("operation_runs")
        execute = Cursor.execute
        def fail_event(cursor, query, *args, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("caught collection error")
            return execute(cursor, query, *args, **kwargs)
        with store._connect() as conn:
            records.patch_row(records.ACCOUNTS, 2, {"note": "caller transaction survives"}, conn=conn)
            with patch.object(Cursor, "execute", fail_event):
                try:
                    api.admit([spec], conn=conn)
                except RuntimeError:
                    pass
        self.assertEqual(self.rows("operation_tasks"), before_tasks)
        self.assertEqual(self.rows("operation_runs"), before_runs)
        self.assertEqual(db.get_account(1)["plan_check_status"], "failed")
        self.assertEqual(db.get_account(2)["note"], "caller transaction survives")

    def test_concurrent_setup_requests_never_append_two_active_runs(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        api = self.api()
        spec = self.spec(1, "twofa")
        gate = Barrier(2)
        def submit():
            gate.wait(timeout=10)
            return api.admit([spec])[spec.source["id"]]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit), pool.submit(submit)]
            replies = [future.result(timeout=20) for future in futures]
        self.assertEqual(sum(reply["accepted"] and not reply["reused"] for reply in replies), 1)
        tasks = [row for row in self.rows("operation_tasks") if row["task_type"] == "account_setup_retry"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(len([row for row in self.rows("operation_runs") if row["task_id"] == tasks[0]["id"]]), 1)

    def test_existing_task_locked_by_single_retry_returns_busy_without_lock_inversion(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first["task_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                        (first["run_id"],))
        fresh = self.spec(1, "twofa", source=db.get_job(spec.source["id"]))
        task_locked, release_task = Event(), Event()
        def single_retry_lock():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {store._table('operation_tasks')} WHERE id=%s FOR UPDATE",
                            (first["task_id"],))
                task_locked.set()
                if not release_task.wait(10):
                    raise RuntimeError("single retry lock wait expired")
        with ThreadPoolExecutor(max_workers=1) as pool:
            held = pool.submit(single_retry_lock)
            try:
                self.assertTrue(task_locked.wait(5))
                with store._connect() as conn, conn.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='200ms'")
                    reply = api.admit([fresh], conn=conn)[spec.source["id"]]
                self.assertFalse(reply["accepted"])
                self.assertTrue(reply["busy"])
            finally:
                release_task.set()
            held.result(timeout=10)

    def test_busy_parent_run_cannot_wait_back_on_the_locked_account(self):
        self._parent_transition_avoids_lock_inversion(different_existing_parent=False)

    def test_existing_parent_is_prelocked_even_when_source_projection_resolves_another_parent(self):
        self._parent_transition_avoids_lock_inversion(different_existing_parent=True)

    def _parent_transition_avoids_lock_inversion(self, *, different_existing_parent):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        parent = store.find_task_by_source("registration_jobs", str(spec.source["id"]))
        if different_existing_parent:
            parent = store.create_runtime_task(task_type="account_completion", account_id=None,
                email="followup-1@example.test", resource_family="completion_coordinator")
            parent["last_run_id"] = parent["run"]["id"]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status='failed' WHERE id=%s",
                        (first["task_id"],))
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status='failed' WHERE id=%s",
                        (first["run_id"],))
            if different_existing_parent:
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=%s,root_task_id=%s WHERE id=%s",
                            (parent["id"], parent["id"], first["task_id"]))
        fresh = self.spec(1, "twofa", source=db.get_job(spec.source["id"]))
        parent_locked, request_account = Event(), Event()
        def parent_transition():
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='2s'")
                cur.execute(f"SELECT id FROM {store._table('operation_runs')} WHERE id=%s FOR UPDATE",
                            (parent["last_run_id"],))
                parent_locked.set()
                if not request_account.wait(5):
                    raise RuntimeError("followup did not reach parent locks")
                cur.execute(f"SELECT id FROM {records._qualified(records.ACCOUNTS)} WHERE id=1 FOR UPDATE")
        execute = Cursor.execute
        def observed(cursor, query, *args, **kwargs):
            text = str(query)
            query_parameters = args[0] if args else ()
            selected_runs = query_parameters[0] if query_parameters else ()
            if ("operation_runs" in text and "FOR UPDATE" in text
                    and isinstance(selected_runs, (list, tuple)) and parent["last_run_id"] in selected_runs):
                request_account.set()
            return execute(cursor, query, *args, **kwargs)
        with ThreadPoolExecutor(max_workers=1) as pool:
            transition = pool.submit(parent_transition)
            try:
                self.assertTrue(parent_locked.wait(5))
                with patch.object(Cursor, "execute", observed), store._connect() as conn, conn.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='2s'")
                    replies = api.admit([fresh], conn=conn)
                self.assertIn(fresh.source["id"], replies)
            finally:
                request_account.set()
            transition.result(timeout=10)

    def test_event_failure_rolls_back_task_run_stage_and_registration_reference(self):
        api = self.api()
        specs = [self.spec(1, "plan_check"), self.spec(2, "twofa")]
        before_tasks = self.rows("operation_tasks")
        before_runs = self.rows("operation_runs")
        execute = Cursor.execute
        def fail_event(cursor, query, *args, **kwargs):
            if str(query).lstrip().startswith(f"INSERT INTO {store._table('operation_events')}"):
                raise RuntimeError("synthetic enqueue failure")
            return execute(cursor, query, *args, **kwargs)
        with patch.object(Cursor, "execute", fail_event), self.assertRaisesRegex(RuntimeError, "synthetic"):
            api.admit(specs)
        self.assertEqual(self.rows("operation_tasks"), before_tasks)
        self.assertEqual(self.rows("operation_runs"), before_runs)
        self.assertEqual(db.get_account(1)["plan_check_status"], "failed")
        self.assertIsNone(db.get_job(specs[1].source["id"]).get("registration_account_task_id"))

    def test_same_account_different_sources_preserves_request_order_and_returns_busy(self):
        api = self.api()
        first = self.spec(1, "codex")
        second = self.spec(1, "twofa")
        replies = api.admit([first, second])
        self.assertTrue(replies[first.source["id"]]["accepted"])
        self.assertFalse(replies[second.source["id"]]["accepted"])
        self.assertTrue(replies[second.source["id"]]["busy"])

    def test_prepare_qualifies_all_sources_without_reserving_or_writing_a_followup(self):
        api = self.api()
        specs = [self.spec(1, "plan_check"), self.spec(1, "codex"), self.spec(2, "twofa")]
        before = {name: self.rows(name) for name in ("operation_tasks", "operation_runs", "operation_events")}
        account = db.get_account(1)
        with store._connect() as conn:
            contexts = api.resolve_followup_context_task_ids(conn, specs)
            from core.storage.operations.bulk_retry_tasks import lock_retry_parents_many

            parents = lock_retry_parents_many(conn, [], additional_parent_task_ids=contexts)
            prepared = api.prepare_followups(conn, specs, locked_parent_contexts=parents)
            self.assertEqual([spec.source["id"] for spec in specs],
                             [row["source_job_id"] for row in prepared.rows])
            self.assertTrue(all(row["resource_family"] == "openai_interactive" for row in prepared.rows))
            self.assertEqual({}, prepared.replies)
        self.assertEqual(account, db.get_account(1))
        self.assertEqual(before, {name: self.rows(name) for name in before})
        self.assertIsNone(db.get_job(specs[2].source["id"]).get("registration_account_task_id"))

    def test_commit_only_selected_prepared_sources_and_keeps_stage_claims_for_winners(self):
        api = self.api()
        first, second = self.spec(1, "plan_check"), self.spec(1, "codex")
        with store._connect() as conn:
            prepared = api.prepare_followups(conn, [first, second])
            replies = api.commit_followups(conn, prepared, winner_source_ids=[second.source["id"]])
        self.assertNotIn(first.source["id"], replies)
        self.assertTrue(replies[second.source["id"]]["accepted"])
        self.assertEqual("failed", db.get_account(1)["plan_check_status"])
        self.assertFalse(any(task["task_type"] == "plan_check" for task in self.rows("operation_tasks")))
        self.assertEqual(1, len([task for task in self.rows("operation_tasks") if task["task_type"] == "codex_retry"]))

    def test_prepare_reuse_defers_missing_parent_and_registration_reference_repairs_to_commit(self):
        api = self.api()
        original = self.spec(1, "twofa")
        first = api.admit([original])[original.source["id"]]
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=NULL,root_task_id=id WHERE id=%s",
                        (first["task_id"],))
        records.patch_row(records.JOBS, original.source["id"], {"registration_account_task_id": None})
        fresh = self.spec(1, "twofa", source=db.get_job(original.source["id"]))
        with store._connect() as conn:
            prepared = api.prepare_followups(conn, [fresh])
            self.assertTrue(prepared.replies[fresh.source["id"]]["reused"])
            with conn.cursor() as cur:
                cur.execute(f"SELECT parent_task_id FROM {store._table('operation_tasks')} WHERE id=%s",
                            (first["task_id"],))
                self.assertIsNone(cur.fetchone()["parent_task_id"])
                cur.execute(f"SELECT data FROM {records._qualified(records.JOBS)} WHERE id=%s",
                            (fresh.source["id"],))
                self.assertIsNone(cur.fetchone()["data"].get("registration_account_task_id"))
            replies = api.commit_followups(conn, prepared, winner_source_ids=[])
        self.assertTrue(replies[fresh.source["id"]]["reused"])
        self.assertEqual(first["task_id"], db.get_job(fresh.source["id"])["registration_account_task_id"])
        repaired = {task["id"]: task for task in self.rows("operation_tasks")}[first["task_id"]]
        self.assertIsNotNone(repaired["parent_task_id"])

    def test_prepare_with_frozen_parent_context_rejects_a_new_unlocked_parent(self):
        from psycopg.errors import SerializationFailure

        api = self.api()
        spec = self.spec(1, "twofa")
        with store._connect() as conn:
            with self.assertRaises(SerializationFailure):
                api.prepare_followups(conn, [spec], locked_parent_contexts={})
        self.assertFalse(any(task["task_type"] == "account_setup_retry" for task in self.rows("operation_tasks")))

    def test_resolver_preserves_both_source_and_existing_setup_parent_contexts(self):
        from core.storage.operations.bulk_retry_tasks import lock_retry_parents_many

        api = self.api()
        spec = self.spec(1, "twofa")
        first = api.admit([spec])[spec.source["id"]]
        source_parent = store.find_task_by_source("registration_jobs", str(spec.source["id"]))
        actual_parent = store.create_runtime_task(task_type="account_completion", account_id=None,
            email="followup-1@example.test", resource_family="completion_coordinator")
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET parent_task_id=%s,root_task_id=%s WHERE id=%s",
                        (actual_parent["id"], actual_parent["id"], first["task_id"]))
        fresh = self.spec(1, "twofa", source=db.get_job(spec.source["id"]))
        with store._connect() as conn:
            contexts = api.resolve_followup_context_task_ids(conn, [fresh])
            self.assertEqual(sorted([source_parent["id"], actual_parent["id"]]), contexts)
            parents = lock_retry_parents_many(conn, [], additional_parent_task_ids=contexts)
            api.prelock_followup_sources(conn, [fresh])
            prepared = api.prepare_followups(conn, [fresh], locked_parent_contexts=parents)
        self.assertTrue(prepared.replies[spec.source["id"]]["reused"])
        self.assertEqual([], prepared.rows)

    def test_prepare_rejects_parent_generation_changed_since_global_prelock(self):
        from psycopg.errors import SerializationFailure
        from core.storage.operations.bulk_retry_tasks import lock_retry_parents_many

        api = self.api()
        spec = self.spec(1, "codex")
        with store._connect() as conn:
            contexts = api.resolve_followup_context_task_ids(conn, [spec])
            parents = lock_retry_parents_many(conn, [], additional_parent_task_ids=contexts)
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {store._table('operation_tasks')} SET last_run_id=NULL WHERE id=ANY(%s)",
                            (contexts,))
            with self.assertRaises(SerializationFailure):
                api.prepare_followups(conn, [spec], locked_parent_contexts=parents)
            conn.rollback()
        self.assertFalse(any(task["task_type"] == "codex_retry" for task in self.rows("operation_tasks")))

    def test_followup_collection_sql_is_constant_for_one_and_twenty_targets(self):
        api = self.api()
        execute = Cursor.execute
        for offset, action in ((0, "plan_check"), (21, "codex"), (42, "twofa")):
            with self.subTest(action=action):
                small = [self.spec(offset + 1, action)]
                large = [self.spec(index, action) for index in range(offset + 2, offset + 22)]
                counts = []
                for specs in (small, large):
                    queries = []
                    def measured(cursor, query, *args, **kwargs):
                        queries.append(str(query))
                        return execute(cursor, query, *args, **kwargs)
                    with patch.object(Cursor, "execute", measured):
                        replies = api.admit(specs)
                    self.assertTrue(all(row["accepted"] for row in replies.values()), replies)
                    counts.append(len(queries))
                print(f"注册后处理{action}: 1目标SQL={counts[0]}, 20目标SQL={counts[1]}")
                self.assertEqual(counts[0], counts[1], counts)
                self.assertLessEqual(counts[1], 30, counts)
