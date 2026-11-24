from threading import Event
import threading
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
