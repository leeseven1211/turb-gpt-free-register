from threading import Event
import threading
import json
from unittest.mock import patch

from psycopg import Cursor

from core import db
from core.registration import service
from core.storage.registration import bulk_submission
from tests.support_pg import PostgresTestCase


class RegistrationBatchStopTests(PostgresTestCase):
    def _batch(self, batch_id, count=1):
        return bulk_submission.create_jobs(
            count=count, email_source="outlook", batch_id=batch_id, workers=2,
            config_snapshot={"registration_driver": "protocol_oss_2"}, debug_enabled=False,
        )

    def test_older_batch_is_found_beyond_latest_thousand_jobs(self):
        running, pending = self._batch("old-selected", 2)
        db.update_job(running["id"], status="running")
        newer = self._batch("new-unselected", 1001)
        with patch.object(service, "_ACTIVE_JOBS", set()), patch.object(
            service, "_STOP_EVENTS", {}
        ), patch.object(service, "_append_job_log"):
            result = service.request_stop_batch("old-selected")
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["stopped"])
        self.assertEqual(0, result["cancelled"])
        self.assertEqual("stopped", db.get_job(running["id"])["status"])
        self.assertEqual("pending", db.get_job(pending["id"])["status"])
        self.assertTrue(all(db.get_job(job["id"])["status"] == "pending" for job in (newer[0], newer[-1])))

    def test_active_worker_gets_signal_and_keeps_cooperative_stopping_state(self):
        [selected] = self._batch("active-selected")
        [unselected] = self._batch("active-unselected")
        db.update_job(selected["id"], status="running")
        db.update_job(unselected["id"], status="running")
        selected_signal, unselected_signal = Event(), Event()
        with patch.object(service, "_ACTIVE_JOBS", {selected["id"], unselected["id"]}), patch.object(
            service, "_STOP_EVENTS", {selected["id"]: selected_signal, unselected["id"]: unselected_signal}
        ), patch.object(service, "_append_job_log"):
            result = service.request_stop_batch("active-selected")
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["stopping"])
        self.assertEqual(0, result["stopped"])
        self.assertTrue(selected_signal.is_set())
        self.assertFalse(unselected_signal.is_set())
        selected_job = db.get_job(selected["id"])
        self.assertEqual("stopping", selected_job["status"])
        self.assertIsNone(selected_job.get("completed_at"))
        self.assertEqual("running", db.get_job(unselected["id"])["status"])

    def test_cancel_pending_only_cancels_selected_batch(self):
        selected = self._batch("cancel-selected", 2)
        unselected = self._batch("cancel-unselected", 2)
        result = service.request_stop_batch("cancel-selected", cancel_pending=True)
        self.assertTrue(result["ok"])
        self.assertEqual(2, result["cancelled"])
        self.assertEqual(0, result["stopping"])
        self.assertTrue(all(db.get_job(job["id"])["status"] == "cancelled" for job in selected))
        self.assertTrue(all(db.get_job(job["id"])["status"] == "pending" for job in unselected))

    def test_running_batch_uses_a_constant_number_of_queries(self):
        counts = []
        original = Cursor.execute
        owner_thread = threading.get_ident()
        for index, count in enumerate((1, 5)):
            batch_id = f"query-budget-{index}"
            jobs = self._batch(batch_id, count)
            for job in jobs:
                db.update_job(job["id"], status="running")
            ids = {job["id"] for job in jobs}
            statements = []

            def execute(cursor, query, *args, **kwargs):
                if threading.get_ident() == owner_thread:
                    statements.append(str(query))
                return original(cursor, query, *args, **kwargs)

            with (
                patch.object(service, "_ACTIVE_JOBS", ids),
                patch.object(service, "_STOP_EVENTS", {ident: Event() for ident in ids}),
                patch.object(db, "get_job", side_effect=AssertionError("unexpected per-job read")),
                patch.object(db, "transition_job_status", side_effect=AssertionError("unexpected per-job CAS")),
                patch.object(Cursor, "execute", execute),
            ):
                result = service.request_stop_batch(batch_id)
            self.assertEqual(count, result["stopping"])
            counts.append(len(statements))
        self.assertTrue(0 < counts[0] == counts[1], counts)

    def test_finished_job_is_not_overwritten_after_batch_snapshot(self):
        from core.storage.registration import batch_stop

        [job] = self._batch("finish-between-read-and-write")
        db.update_job(job["id"], status="running")
        original = batch_stop.request_stops

        def finish_first(*args, **kwargs):
            db.update_job(job["id"], status="success")
            return original(*args, **kwargs)

        with (
            patch.object(service, "_ACTIVE_JOBS", {job["id"]}),
            patch.object(service, "_STOP_EVENTS", {job["id"]: Event()}),
            patch.object(batch_stop, "request_stops", side_effect=finish_first),
        ):
            result = service.request_stop_batch("finish-between-read-and-write")
        self.assertEqual(1, result["completed"])
        self.assertEqual(0, result["stopping"])
        self.assertEqual(0, result["stopped"])
        self.assertEqual("success", db.get_job(job["id"])["status"])

    def test_orphan_stop_keeps_immediate_actions_and_error_projection(self):
        from core.storage.operations import store

        [job] = self._batch("orphan-projection")
        db.update_job(job["id"], status="running")
        with patch.object(service, "_ACTIVE_JOBS", set()), patch.object(service, "_STOP_EVENTS", {}):
            result = service.request_stop_batch("orphan-projection")
        self.assertEqual(1, result["stopped"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT task.next_actions,task.error_category,task.error_code,
                run.error_category AS run_category,run.error_code AS run_code
                FROM {store._table('operation_tasks')} task
                JOIN {store._table('operation_runs')} run ON task.last_run_id=run.id
                WHERE run.source_system='registration_jobs' AND run.source_id=%s""", (str(job["id"]),))
            row = cur.fetchone()
        self.assertEqual([{"action": "registration_retry", "label": "重新执行注册", "source_job_id": job["id"]}],
                         row["next_actions"])
        self.assertEqual(("user", "user.interrupted", "user", "user.interrupted"),
                         (row["error_category"], row["error_code"], row["run_category"], row["run_code"]))

    def test_missing_sources_are_resolved_once_for_the_selected_orphans(self):
        from core.email import provider
        from core.storage import records
        from core.storage.email import provider_orders

        provider_orders.init()
        counts = []
        owner_thread, original = threading.get_ident(), Cursor.execute
        for index, count in enumerate((1, 5)):
            batch_id = f"missing-source-budget-{index}"
            jobs = self._batch(batch_id, count)
            for ordinal, job in enumerate(jobs):
                email = f"missing-source-{index}-{ordinal}@example.test"
                records.patch_row(records.JOBS, job["id"], {"status": "running", "email": email, "email_source": None})
                records.insert_row(records.ACCOUNTS, {"email": email, "email_source": "outlook"})
                records.insert_row(records.GENERIC_API_POOL, {"email": email, "status": "available"})
            statements = []

            def execute(cursor, query, *args, **kwargs):
                if threading.get_ident() == owner_thread:
                    statements.append(str(query))
                return original(cursor, query, *args, **kwargs)

            with (
                patch.object(service, "_ACTIVE_JOBS", set()),
                patch.object(service, "_STOP_EVENTS", {}),
                patch.object(provider, "resolve_email_source", side_effect=AssertionError("per-email source lookup")),
                patch.object(provider, "remember_email_source", wraps=provider.remember_email_source) as remember,
                patch.object(Cursor, "execute", execute),
            ):
                result = service.request_stop_batch(batch_id)
            self.assertEqual(count, result["stopped"])
            self.assertTrue(all(call.args[1] == "outlook" for call in remember.call_args_list))
            self.assertEqual(count, remember.call_count)
            counts.append(len(statements))
        self.assertTrue(0 < counts[0] == counts[1], counts)

    def test_stopping_legacy_unprojected_jobs_creates_the_original_task_run_mapping(self):
        from core.storage import records, registration
        from core.storage.operations import store

        records.init()
        sources = []
        for index in range(2):
            row = db._new_job_row(email_source="outlook", email=f"unprojected-stop-{index}@example.test",
                                  batch_id="unprojected-stop", batch_workers=3, batch_index=index + 1, batch_size=2)
            row["status"] = "running"
            row["progress_steps"] = {"network": {"state": "success", "detail": "fixture-network",
                                                "occurred_at": "2026-11-24T12:00:00+00:00"}}
            sources.append(records.insert_row(records.JOBS, row))
        with patch.object(service, "_ACTIVE_JOBS", set()), patch.object(service, "_STOP_EVENTS", {}):
            result = service.request_stop_batch("unprojected-stop")
        self.assertEqual(2, result["stopped"])
        for source_id in sources:
            source = db.get_job(source_id)
            task = store.find_task_by_source("registration_jobs", str(source_id), include_runs=True)
            self.assertIsNotNone(task)
            self.assertEqual("stopped", task["status"])
            self.assertEqual(source_id, task["next_actions"][0]["source_job_id"])
            self.assertEqual("user.interrupted", task["error_code"])
            self.assertEqual(source["attempt_id"], task["attempt_id"])
            self.assertEqual([], registration.list_runs(source["attempt_id"]))
            with store._connect() as conn, conn.cursor() as cur:
                cur.execute(f"""SELECT message,detail FROM {store._table('operation_events')}
                    WHERE source_system='registration_progress' AND source_id=%s""", (f"{source_id}:stage:network",))
                event = cur.fetchone()
            self.assertEqual("fixture-network", event["message"])
            self.assertTrue(event["detail"]["event_time_known"])

    def test_missing_stop_projection_rolls_back_with_the_status_update(self):
        from core.storage import records
        from core.storage.operations import common
        from core.storage.registration import batch_stop_projection

        records.init()
        row = db._new_job_row(email_source="outlook", email="unprojected-rollback@example.test",
                              batch_id="unprojected-stop-rollback")
        row["status"] = "running"
        source_id = records.insert_row(records.JOBS, row)
        original = batch_stop_projection.ensure_missing

        def create_then_fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("injected projection failure")

        with (
            patch.object(service, "_ACTIVE_JOBS", set()),
            patch.object(service, "_STOP_EVENTS", {}),
            patch.object(batch_stop_projection, "ensure_missing", side_effect=create_then_fail),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected projection failure"):
                service.request_stop_batch("unprojected-stop-rollback")
        self.assertEqual("running", db.get_job(source_id)["status"])
        self.assertIsNone(db.get_job(source_id)["attempt_id"])
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM {common._table('operation_tasks')}")
            self.assertEqual(0, cur.fetchone()["n"])

    def test_missing_stop_projection_advances_the_existing_attempt_account_facts(self):
        from core.storage import records, registration
        from core.storage.operations import store

        records.init()
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": "unprojected-account@example.test", "access_token": "fixture-at", "codex_status": "failed",
        })
        row = db._new_job_row(email_source="outlook", email="unprojected-account@example.test",
                              account_id=account_id, batch_id="unprojected-account")
        row["status"] = "running"
        source_id = records.insert_row(records.JOBS, row)
        attempt = registration.create_attempt(row["email"], root_job_id=source_id, email_source="outlook")
        with patch.object(service, "_ACTIVE_JOBS", set()), patch.object(service, "_STOP_EVENTS", {}):
            service.request_stop_batch("unprojected-account")
        latest = registration.get_attempt(attempt["id"])
        self.assertEqual("account_available", latest["target_status"])
        self.assertEqual("core_persisted", latest["checkpoint"])
        self.assertEqual(account_id, latest["account_id"])
        task = store.find_task_by_source("registration_jobs", str(source_id), include_runs=True)
        self.assertEqual("codex_retry", task["next_actions"][0]["action"])

    def test_501_unprojected_same_root_jobs_use_bounded_payloads_and_monotonic_runs(self):
        from core.storage import records
        from core.storage.operations import store

        records.init()
        root = db._new_job_row(email_source="outlook", email="large-unprojected@example.test",
                               batch_id="large-unprojected")
        root.update(status="stopped")
        root_id = records.insert_row(records.JOBS, root)
        jobs = []
        with records.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {records._qualified(records.JOBS)} (email,job_uuid,status,batch_id,
                    root_job_id,parent_job_id,data,created_at,updated_at)
                SELECT %s,'large-stop-' || n,'running','large-unprojected',%s,%s,
                    jsonb_build_object('email_source','outlook','retry_attempt',n,'job_type','registration'),
                    '2026-11-24T00:00:00+00:00','2026-11-24T00:00:00+00:00'
                FROM generate_series(1,501) n RETURNING id""", (root["email"], root_id, root_id))
            jobs = [row["id"] for row in cur.fetchall()]
        sizes = []
        execute = Cursor.execute
        owner_thread = threading.get_ident()

        def bounded(cursor, query, params=None, **kwargs):
            if threading.get_ident() == owner_thread and "jsonb_to_recordset" in str(query):
                for value in params or ():
                    if isinstance(value, str) and value.startswith("["):
                        payload = json.loads(value)
                        if isinstance(payload, list):
                            sizes.append(len(payload))
                            self.assertLessEqual(len(payload), 500)
            return execute(cursor, query, params, **kwargs)

        with (
            patch.object(service, "_ACTIVE_JOBS", set()),
            patch.object(service, "_STOP_EVENTS", {}),
            patch.object(Cursor, "execute", bounded),
        ):
            result = service.request_stop_batch("large-unprojected")
        self.assertEqual(501, result["stopped"])
        self.assertIn(500, sizes)
        self.assertIn(1, sizes)
        task = store.find_task_by_source("registration_jobs", str(jobs[-1]), include_runs=True)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n,max(run_no) AS highest FROM {store._table('operation_runs')} WHERE task_id=%s",
                        (task["id"],))
            count = cur.fetchone()
            cur.execute(f"SELECT source_id FROM {store._table('operation_runs')} WHERE id=%s", (task["last_run_id"],))
            self.assertEqual(str(jobs[-1]), cur.fetchone()["source_id"])
        self.assertEqual((501, 502), (count["n"], count["highest"]))

    def test_unprojected_job_prelocks_its_existing_batch_and_missing_queue_anchor(self):
        from core.storage import postgres, records
        from core.storage.operations import common

        self._batch("existing-batch-before-unprojected")
        row = db._new_job_row(email_source="outlook", email="prelock-unprojected@example.test",
                              batch_id="existing-batch-before-unprojected")
        row["status"] = "running"
        source_id = records.insert_row(records.JOBS, row)
        with common._connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {common._table('operation_projection_queue')}")
            cur.execute(f"""SELECT id FROM {common._table('operation_batches')}
                WHERE source_system='registration_batches' AND source_id=%s""", ("existing-batch-before-unprojected",))
            batch_id = cur.fetchone()["id"]
        execute, observed = Cursor.execute, []

        def check_lock(cursor, query, params=None, **kwargs):
            text = str(query)
            if "FOR UPDATE" in text and records.JOBS.name in text:
                with postgres.connect() as other, other.cursor() as current:
                    current.execute("SET LOCAL lock_timeout='100ms'")
                    with self.assertRaises(Exception) as blocked:
                        current.execute(f"SELECT id FROM {common._table('operation_batches')} WHERE id=%s FOR UPDATE",
                                        (batch_id,))
                    self.assertEqual("55P03", getattr(blocked.exception, "sqlstate", None))
                observed.append(True)
            return execute(cursor, query, params, **kwargs)

        with (
            patch.object(service, "_ACTIVE_JOBS", set()),
            patch.object(service, "_STOP_EVENTS", {}),
            patch.object(Cursor, "execute", check_lock),
        ):
            result = service.request_stop_batch("existing-batch-before-unprojected")
        self.assertTrue(observed)
        self.assertEqual(1, result["stopped"])
        self.assertEqual("stopped", db.get_job(source_id)["status"])
