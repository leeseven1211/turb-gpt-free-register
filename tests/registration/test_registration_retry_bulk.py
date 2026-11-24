import threading
from unittest.mock import patch

from psycopg import Cursor

from core import db
from core.registration import service
from core.storage import postgres, records, registration
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

    def test_bulk_prefetch_preserves_existing_attempt_email_identity(self):
        root = self._root("unlinked-address@example.test", "prefetch")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {postgres.qualified('registration_attempts')}
                            SET email=NULL WHERE id=%s""", (root["attempt_id"],))
        body = self._request([root["id"]])
        assert body["started_count"] == 1
        attempt = registration.get_attempt(root["attempt_id"])
        assert (attempt["email"], attempt["email_snapshot"]) == (None, "unlinked-address@example.test")

    def test_bulk_reads_selected_jobs_and_attempts_as_collections(self):
        first = self._root("first-prefetch@example.test", "first-prefetch")
        second = self._root("second-prefetch@example.test", "second-prefetch")
        with (patch.object(db, "get_job", wraps=db.get_job) as read_job,
              patch.object(registration, "get_attempt", wraps=registration.get_attempt) as read_attempt,
              patch.object(db, "get_successful_retry_for_job", wraps=db.get_successful_retry_for_job) as read_retry):
            body = self._request([first["id"], second["id"]])
        assert body["started_count"] == 2
        assert (read_job.call_count, read_attempt.call_count, read_retry.call_count) == (0, 0, 0)

    def test_retry_prefetch_query_count_is_constant_for_multiple_roots(self):
        roots = [self._root(f"query-budget-{index}@example.test", f"query-budget-{index}")
                 for index in range(5)]
        execute = Cursor.execute
        owner_thread = threading.get_ident()
        counts = []
        for selected in (roots[:1], roots):
            statements = []

            def capture(cursor, query, *args, **kwargs):
                if threading.get_ident() == owner_thread:
                    statements.append(str(query))
                return execute(cursor, query, *args, **kwargs)

            with patch.object(Cursor, "execute", capture):
                facts = service._prefetch_retry_facts([root["id"] for root in selected])
            assert set(facts) == {root["id"] for root in selected}
            assert all(facts[root["id"]].source_attempt["id"] == root["attempt_id"] for root in selected)
            counts.append(len(statements))
        assert 0 < counts[0] == counts[1] <= 8, counts

    def test_task_center_selected_roots_enter_one_registration_admission(self):
        from core.storage.operations import legacy_task_store

        self.enterContext(patch.object(legacy_task_store, "_SCHEMA", self.schema))
        self.enterContext(patch.object(legacy_task_store, "_READY_KEY", ""))
        legacy_task_store.init()
        roots = [self._root(f"task-center-{index}@example.test", f"task-center-{index}")
                 for index in range(2)]
        for root in roots:
            operation_store.sync_registration_job(root["id"])
        task_ids = [operation_store.find_task_by_source("registration_jobs", str(root["id"]), include_runs=True)["id"]
                    for root in roots]
        client = create_app(auth_code="test-auth").test_client()
        with (
            patch.object(service, "start_dispatcher"),
            patch.object(service, "notify_dispatch"),
            patch.object(service, "configure_submission_workers"),
            patch.object(service, "registration_deployment_unavailable", return_value=None),
            patch.object(bulk_retry, "admit", wraps=bulk_retry.admit) as admit,
            patch.object(service, "_prefetch_retry_facts", wraps=service._prefetch_retry_facts) as prefetch,
        ):
            response = client.post("/api/operations/bulk", json={"action": "retry", "task_ids": task_ids},
                                   headers={"X-Auth-Code": "test-auth"})
        assert response.status_code == 200
        body = response.get_json()
        assert body["accepted_count"] == 2, body
        prefetch.assert_called_once_with([root["id"] for root in roots])
        admit.assert_called_once()
        assert [plan.source_id for plan in admit.call_args.args[0]] == [root["id"] for root in roots]

    def test_legacy_roots_without_attempts_are_backfilled_in_the_collection_transaction(self):
        records.init()
        roots = []
        for index in range(2):
            row = db._new_job_row(
                email_source="outlook", email=f"legacy-{index}@example.test",
                batch_id="legacy-selected", batch_index=index + 1, batch_size=2, batch_workers=3,
                data={"config_snapshot": {"registration_driver": "protocol_oss_2", "proxy_country": "JP"}},
            )
            row["status"] = "failed"
            row["id"] = records.insert_row(records.JOBS, row)
            roots.append(db.get_job(row["id"]))
        plans = [bulk_retry.RetryAdmission(
            source=root, root=root, attempt=None, action="registration", email=root["email"],
            email_source="outlook", account=None, batch_id=root["batch_id"], batch_index=root["batch_index"],
            batch_size=root["batch_size"], workers=3, config_snapshot=root["config_snapshot"], debug_enabled=False,
        ) for root in roots]
        with patch.object(db, "create_retry_job", side_effect=AssertionError("unexpected single-item fallback")):
            result = bulk_retry.admit(plans)
        for root in roots:
            child, created = result[root["id"]]
            assert created
            child = db.get_job(child["id"])
            assert child["root_job_id"] == root["id"]
            assert child["parent_job_id"] == root["id"]
            assert child["email"] == root["email"]
            assert child["batch_workers"] == 3
            attempt = registration.get_attempt(child["attempt_id"])
            assert attempt["root_job_id"] == root["id"]
            assert attempt["email"] == root["email"]
            assert len(registration.list_runs(attempt["id"])) == 1
            task = operation_store.find_task_by_source("registration_jobs", str(child["id"]), include_runs=True)
            assert task["status"] == "queued"
            assert db.get_job(root["id"])["attempt_id"] is None

    def test_missing_projection_is_backfilled_without_single_item_fallback(self):
        root = self._root("projection-gap@example.test", "projection-gap")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM {postgres.qualified('operation_tasks')}")
            cur.execute(f"DELETE FROM {postgres.qualified('operation_batches')}")
        with patch.object(db, "create_retry_job", side_effect=AssertionError("unexpected single-item fallback")):
            body = self._request([root["id"]])
        assert body["started_count"] == 1, body
        [result] = body["started"]
        assert result["job"]["attempt_id"] == root["attempt_id"]
        assert len(registration.list_runs(root["attempt_id"])) == 2

    def test_legacy_backfill_and_retry_roll_back_together(self):
        records.init()
        row = db._new_job_row(email_source="outlook", email="legacy-rollback@example.test",
                              batch_id="legacy-rollback", data={"config_snapshot": {"registration_driver": "protocol_oss_2"}})
        row["status"] = "failed"
        source_id = records.insert_row(records.JOBS, row)
        source = db.get_job(source_id)
        plan = bulk_retry.RetryAdmission(
            source=source, root=source, attempt=None, action="registration", email=source["email"],
            email_source="outlook", account=None, batch_id=source["batch_id"], batch_index=1,
            batch_size=1, workers=3, config_snapshot=source["config_snapshot"], debug_enabled=False,
        )
        with patch.object(bulk_retry, "_insert_facts", side_effect=RuntimeError("injected retry write failure")):
            with self.assertRaisesRegex(RuntimeError, "injected retry write failure"):
                bulk_retry.admit([plan])
        with postgres.connect() as conn, conn.cursor() as cur:
            for table in ("registration_attempts", "registration_runs", "operation_tasks", "operation_batches"):
                cur.execute(f"SELECT count(*) FROM {postgres.qualified(table)}")
                assert cur.fetchone()[0] == 0, table
        assert db.get_job(source_id)["attempt_id"] is None

    def test_historical_attempt_with_only_root_job_id_keeps_run_sequence(self):
        root = self._root("root-id-only@example.test", "root-id-only")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {postgres.qualified('registration_attempts')}
                SET source_root_job_id=NULL WHERE id=%s""", (root["attempt_id"],))
        body = self._request([root["id"]])
        assert body["started_count"] == 1, body
        [item] = body["started"]
        assert item["job"]["attempt_id"] == root["attempt_id"]
        runs = registration.list_runs(root["attempt_id"])
        assert [row["run_no"] for row in runs] == [2, 1]
        assert registration.get_attempt(root["attempt_id"])["source_root_job_id"] is None

    def test_historical_root_id_only_attempt_with_active_run_is_not_retried(self):
        root = self._root("root-id-active@example.test", "root-id-active")
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""UPDATE {postgres.qualified('registration_attempts')}
                SET source_root_job_id=NULL WHERE id=%s""", (root["attempt_id"],))
            cur.execute(f"""UPDATE {postgres.qualified('registration_runs')}
                SET status='running',completed_at=NULL WHERE attempt_id=%s""", (root["attempt_id"],))
        body = self._request([root["id"]])
        assert body["started_count"] == 0, body
        assert "Attempt" in body["skipped"][0]["reason"]
        assert len(registration.list_runs(root["attempt_id"])) == 1
