from threading import Event
from unittest.mock import patch

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
