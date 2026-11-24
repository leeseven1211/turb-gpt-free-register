from unittest.mock import patch

from core import db
from core.registration import service
from core.storage import postgres, registration
from core.storage.operations import store as operation_store
from core.storage.registration import bulk_retry
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class RegistrationRetryBulkTests(PostgresTestCase):
    def _root(self, address, batch, workers=3):
        job = db.create_job("outlook", batch_id=batch, batch_index=2, batch_size=5,
                            batch_workers=workers, data={"config_snapshot": {
                                "registration_driver": "protocol_oss_2", "proxy_country": "JP",
                            }})
        db.update_job(job["id"], email=address, status="failed")
        self._finish(job)
        return job

    def _finish(self, job):
        registration.finish_run(registration.list_runs(job["attempt_id"])[0]["id"], status="failed")

    def _request(self, ids):
        client = create_app(auth_code="test-auth").test_client()
        with (patch.object(service, "start_dispatcher"),
              patch.object(service, "notify_dispatch"),
              patch.object(service, "configure_submission_workers"),
              patch.object(service, "registration_deployment_unavailable", return_value=None)):
            response = client.post("/api/jobs/retry-bulk",
                                   json={"job_ids": ids, "workers": 8, "debug_enabled": True},
                                   headers={"X-Auth-Code": "test-auth"})
        assert response.status_code == 200
        return response.get_json()

    def test_one_insert_admits_distinct_roots_and_reuses_their_active_child(self):
        first = self._root("first@example.test", "origin-a")
        second = self._root("second@example.test", "origin-b", workers=4)
        previous, created = db.create_retry_job(first["id"], job_type="registration", email_source="outlook",
                                                email="first@example.test", data={"config_snapshot": {
                                                    "registration_driver": "protocol_oss_2", "proxy_country": "SG",
                                                }})
        assert created
        db.update_job(previous["id"], status="failed")
        self._finish(previous)
        with postgres.connect() as conn, conn.cursor() as cur:
            captures = postgres.qualified("retry_insert_capture")
            fn = postgres.qualified("record_retry_insert")
            cur.execute(f"CREATE TABLE {captures} (n int)")
            cur.execute(f"""CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN INSERT INTO {captures} SELECT count(*) FROM inserted; RETURN NULL; END $$""")
            cur.execute(f"""CREATE TRIGGER capture_retry_insert AFTER INSERT ON
                {postgres.qualified("registration_jobs")} REFERENCING NEW TABLE AS inserted
                FOR EACH STATEMENT EXECUTE FUNCTION {fn}()""")
        try:
            body = self._request([previous["id"], first["id"], second["id"]])
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"SELECT n FROM {captures}")
                assert [row[0] for row in cur.fetchall()] == [2]
        finally:
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DROP TRIGGER capture_retry_insert ON {postgres.qualified('registration_jobs')}")
                cur.execute(f"DROP FUNCTION {fn}()")
                cur.execute(f"DROP TABLE {captures}")

        assert body["skipped"] == []
        first_retry, second_retry = [item["job"] for item in body["started"]]
        assert body["reused"][0]["source_job_id"] == first["id"]
        assert body["reused"][0]["job"]["id"] == first_retry["id"]
        assert body["affected_batch_ids"] == ["origin-a", "origin-b"]
        for root, selected, retry, country, workers in (
            (first, previous, first_retry, "SG", 3), (second, second, second_retry, "JP", 4),
        ):
            job = db.get_job(retry["id"])
            assert job["root_job_id"] == root["id"]
            assert job["parent_job_id"] == selected["id"]
            assert job["attempt_id"] == root["attempt_id"]
            assert job["email"] == ("first@example.test" if root is first else "second@example.test")
            assert job["config_snapshot"]["proxy_country"] == country
            assert job["batch_workers"] == workers
            assert (job["batch_index"], job["batch_size"]) == (2, 5)
            assert job["debug_enabled"] is True
            assert job["registration_dispatch_ready"] is True
            run = registration.list_runs(root["attempt_id"])[0]
            assert (run["job_id"], run["status"]) == (job["id"], "queued")
            assert run["data"]["config_snapshot"] == {
                "registration_driver": "protocol_oss_2", "proxy_country": country,
            }
            task = operation_store.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
            assert task["status"] == "queued"
            assert task["data"]["latest_legacy_job_id"] == job["id"]
        again = self._request([first["id"], second["id"]])
        assert again["started"] == []
        assert [item["job"]["id"] for item in again["reused"]] == [first_retry["id"], second_retry["id"]]

    def test_source_and_email_changes_after_validation_only_skip_affected_items(self):
        changed = self._root("changed@example.test", "changed")
        deleted = self._root("deleted@example.test", "deleted")
        eligible = self._root("eligible@example.test", "eligible")
        admit = bulk_retry.admit

        def change_before_write(plans):
            db.update_job(changed["id"], status="running")
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(f"""INSERT INTO {postgres.qualified('email_pool_outlook')}
                                (email,status,created_at,updated_at) VALUES (%s,'tombstone',%s,%s)""",
                            ("deleted@example.test", deleted["created_at"], deleted["created_at"]))
            return admit(plans)

        with patch.object(bulk_retry, "admit", side_effect=change_before_write):
            body = self._request([changed["id"], deleted["id"], eligible["id"]])
        assert [item["source_job_id"] for item in body["started"]] == [eligible["id"]]
        assert [(item["id"], item["reason"]) for item in body["skipped"]] == [
            (changed["id"], "当前状态不支持重试：running"),
            (deleted["id"], "原邮箱已删除，不能继续注册"),
        ]
        assert len(registration.list_runs(changed["attempt_id"])) == 1
        assert len(registration.list_runs(deleted["attempt_id"])) == 1

    def test_resume_uses_original_attempt_and_appends_to_resume_projection(self):
        root = self._root("resume@example.test", "resume")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {postgres.qualified('registration_attempts')}
                            SET checkpoint='password_confirmed',private_context=%s
                            WHERE id=%s""",
                        ('{"password":"fixture-password"}', root["attempt_id"]))
        body = self._request([root["id"]])
        assert body["skipped"] == []
        [item] = body["started"]
        job = item["job"]
        assert item["retry_action"] == "registration_resume"
        assert job["attempt_id"] == root["attempt_id"]
        assert job["email"] == "resume@example.test"
        assert job["config_snapshot"]["registration_driver"] == "protocol_oss_2"
        task = operation_store.find_task_by_source("registration_jobs", str(job["id"]), include_runs=True)
        original = operation_store.find_task_by_source("registration_jobs", str(root["id"]), include_runs=True)
        assert task["task_type"] == "registration_resume"
        assert task["root_task_id"] == original["id"]
        assert task["parent_task_id"] == original["id"]
        assert registration.list_runs(root["attempt_id"])[0]["action_type"] == "registration_resume"
