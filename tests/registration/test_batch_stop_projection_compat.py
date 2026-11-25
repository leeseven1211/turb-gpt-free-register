"""历史停止补投影与原单项投影器的事实对照。"""
from __future__ import annotations

from core import db
from core.registration import service
from core.storage import records
from core.storage.operations import common, projection, store
from core.storage.registration import batch_stop
from tests.support_pg import PostgresTestCase


class BatchStopProjectionCompatibilityTests(PostgresTestCase):
    def setUp(self):
        records.init()
        store.reset_ready()
        store.init()

    def _source(self, *, email, batch_id, **changes):
        row = db._new_job_row(email_source="outlook", email=email, batch_id=batch_id)
        row.update(status="running", **changes)
        ident = records.insert_row(records.JOBS, row)
        return records.get_row(records.JOBS, ident)

    def _snapshot(self, task_id):
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""SELECT batch_id,parent_task_id,root_task_id,attempt_id,account_id,
                    email_snapshot,status,target_status,current_stage,last_run_id,next_actions,
                    error_category,error_code,error_message,completed_at,data
                FROM {store._table('operation_tasks')} WHERE id=%s""", (task_id,))
            return dict(cur.fetchone())

    def test_existing_task_without_source_run_gets_original_binding_updates(self):
        email = "stop-stale-task@example.test"
        account_id = records.insert_row(records.ACCOUNTS, {
            "email": email, "access_token": "isolated-test-at", "codex_status": "failed",
        })
        source = self._source(email=email, batch_id="stale-binding", account_id=account_id,
                              config_snapshot={"registration_driver": "protocol_oss_2"})
        identity = f"{source['id']}:registration"
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {store._table('operation_tasks')}
                    (task_uuid,source_system,source_id,task_type,target_type,requested_action,
                     status,target_status,email_snapshot,data)
                VALUES (%s,'registration_chains',%s,'registration','registration_attempt',
                        'registration','running','request_unknown','stale@example.test',
                        '{{"retained_fact":"keep"}}'::jsonb)
                RETURNING id""",
                (common._uuid("task", f"registration_chains:{identity}"), identity))
            task_id = cur.fetchone()["id"]
        batch_stop.request_stops([source["id"]], active_job_ids=set(), now_iso=service._now_iso())
        actual = self._snapshot(task_id)
        self.assertIsNotNone(actual["attempt_id"])
        self.assertIsNotNone(actual["batch_id"])
        self.assertEqual(account_id, actual["account_id"])
        self.assertEqual(email, actual["email_snapshot"])
        self.assertEqual("account_available", actual["target_status"])
        self.assertEqual("keep", actual["data"]["retained_fact"])
        projection.sync_registration_job(source["id"])
        self.assertEqual(self._snapshot(task_id), actual)

    def _same_root_last_run(self, old_state):
        root = self._source(email=f"stop-prior-{old_state}@example.test", batch_id=f"prior-{old_state}")
        projection.sync_registration_job(root["id"])
        task = store.find_task_by_source("registration_jobs", str(root["id"]), include_runs=True)
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {store._table('operation_runs')} SET status=%s WHERE id=%s",
                        (old_state, task["last_run_id"]))
            cur.execute(f"UPDATE {store._table('operation_tasks')} SET status=%s WHERE id=%s",
                        (old_state, task["id"]))
        records.patch_row(records.JOBS, root["id"], changes={"status": old_state})
        selected = self._source(
            email=root["email"], batch_id=f"prior-{old_state}", root_job_id=root["id"],
            parent_job_id=root["id"], retry_attempt=1,
        )
        batch_stop.request_stops([selected["id"]], active_job_ids=set(), now_iso=service._now_iso())
        actual = self._snapshot(task["id"])
        self.assertEqual("stopped", actual["status"])
        with store._connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT source_id FROM {store._table('operation_runs')} WHERE id=%s",
                        (actual["last_run_id"],))
            self.assertEqual(str(selected["id"]), cur.fetchone()["source_id"])
        projection.sync_registration_job(selected["id"])
        self.assertEqual(self._snapshot(task["id"]), actual)

    def test_old_waiting_run_does_not_replace_new_stopped_run(self):
        self._same_root_last_run("waiting")

    def test_old_stopping_run_does_not_replace_new_stopped_run(self):
        self._same_root_last_run("stopping")

    def test_other_batch_active_run_keeps_its_actions_and_errors(self):
        root = self._source(email="stop-active-root@example.test", batch_id="original-active-batch")
        projection.sync_registration_job(root["id"])
        task = store.find_task_by_source("registration_jobs", str(root["id"]), include_runs=True)
        prior = self._snapshot(task["id"])
        selected = self._source(
            email=root["email"], batch_id="selected-retry-batch", root_job_id=root["id"],
            parent_job_id=root["id"], retry_attempt=1,
        )
        batch_stop.request_stops([selected["id"]], active_job_ids=set(), now_iso=service._now_iso())
        actual = self._snapshot(task["id"])
        self.assertEqual(prior["last_run_id"], actual["last_run_id"])
        self.assertEqual("running", actual["status"])
        for field in ("next_actions", "error_category", "error_code", "error_message"):
            self.assertEqual(prior[field], actual[field], field)
        projection.sync_registration_job(selected["id"])
        self.assertEqual(self._snapshot(task["id"]), actual)
