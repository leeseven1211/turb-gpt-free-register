"""Literal PostgreSQL contracts for the opt-in plan_check database policy.

Expected eligibility/receipts are hand-written domain facts, never generated
by the SQL policy or generic preflight implementation under test.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import uuid
from unittest.mock import Mock, patch

from core.storage import records
from core.storage.operations import bulk, bulk_common as common
from tests.support_pg import PostgresTestCase


class PlanCheckPreflightPolicyTests(PostgresTestCase):
    def setUp(self):
        bulk.reset_ready()
        bulk.init()

    def account(self, label, **changes):
        return self.seed(records.ACCOUNTS, [{
            "email": f"policy-{label}@example.test", "created_at": "2026-10-15T10:00:00",
            "updated_at": "2026-10-15T10:00:00", "plan_type": "free", "current_plan_type": "free",
            "plan_check_status": "success", "plan_check_ok": True, "plus_promo_kind": "none",
            "access_token": "synthetic-token", **changes,
        }])[0]

    def selection(self, ids, *, snapshot=None, operation="plan_check"):
        return bulk.create_selection(
            request_key=uuid.uuid4().hex, source={"kind": "ids", "ids": ids},
            operation_key=operation, config_revision="saved-policy-v1",
            config_snapshot={"auto_refresh_at_enabled": False} if snapshot is None else snapshot,
        )

    def freeze(self, selection, **kwargs):
        return bulk.freeze_selection(selection["id"], preflight_policy="plan_check_db_v1", **kwargs)

    def rows(self, selection):
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {common.table('operation_selections')} WHERE id=%s", (selection["id"],))
            parent = dict(cur.fetchone())
            cur.execute(f"SELECT * FROM {common.table('operation_selection_targets')} WHERE selection_id=%s ORDER BY ordinal",
                        (selection["id"],))
            return parent, [dict(row) for row in cur.fetchall()]

    def active_run(self, account_id, status="waiting"):
        identity = uuid.uuid4().hex
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {common.table('operation_tasks')}
                (task_uuid,source_system,source_id,task_type,target_type,account_id,requested_action)
                VALUES (%s,'policy-test',%s,'plan_check','account',%s,'plan_check') RETURNING id""",
                        (identity, identity, account_id))
            task_id = cur.fetchone()["id"]
            cur.execute(f"""INSERT INTO {common.table('operation_runs')}
                (run_uuid,task_id,run_no,source_system,source_id,status,account_id,next_attempt_at)
                VALUES (%s,%s,1,'policy-test',%s,%s,%s,'2099-01-01T00:00:00Z') RETURNING id""",
                        (identity, task_id, identity, status, account_id))
            return int(cur.fetchone()["id"])

    def job(self, *, account_id=None, email="", status="pending", job_type="registration"):
        return self.seed(records.JOBS, [{
            "job_uuid": uuid.uuid4().hex, "account_id": account_id, "email": email,
            "status": status, "job_type": job_type,
            "created_at": "2026-10-15T10:00:00", "updated_at": "2026-10-15T10:00:00",
        }])[0]

    def freeze_generic(self, selection, *, chunk_sizes=None):
        from core.bulk_operations import adapters

        saved = self.rows(selection)[0]["config_snapshot"]

        def preflight(targets, conn):
            if chunk_sizes is not None:
                chunk_sizes.append(len(targets))
            return adapters.preflight_many(targets, operation_key="plan_check", settings=saved, conn=conn)

        return bulk.freeze_selection(selection["id"], preflight=preflight, preflight_identity_only=True)

    def assert_complete_facts_equal(self, generic, selected):
        """Compare every persisted field, allowing only identity and clock changes."""
        facts = []
        for selection in (generic, selected):
            parent, targets = deepcopy(self.rows(selection))
            for target in targets:
                check = target["match_evidence"]["preflight"]
                self.assertEqual(target["id"], check["target_id"])
                self.assertEqual(parent["id"], target["selection_id"])
                self.assertEqual({"target_id", "status", "reason_code", "checked_at", "blocker_run_id"}, set(check))
                self.assertIsInstance(datetime.fromisoformat(check["checked_at"]), datetime)
                self.assertEqual(parent["selected_at"],
                                 datetime.fromisoformat(target["baseline"]["plan_check"]["frozen_at"]))
                # Separate selections must allocate separate true target IDs.
                # Business account IDs, ordinals, reasons and blockers stay exact.
                target["id"] = check["target_id"] = target["ordinal"]
                target["selection_id"] = 0
                check["checked_at"] = "<checked_at>"
                target["baseline"]["plan_check"]["frozen_at"] = "<selected_at>"
            parent["id"] = 0
            parent["request_key"] = "<request_key>"
            for field in ("selected_at", "preflight_at", "created_at", "updated_at", "expires_at", "next_attempt_at"):
                self.assertIsInstance(parent[field], datetime)
                parent[field] = f"<{field}>"
            facts.append((parent, targets))
        self.assertEqual(*facts)

    def test_priority_minimum_blocker_and_real_target_receipts(self):
        ready = self.account("ready")
        disabled = self.account("disabled", account_status="deactivated", email="", access_token="")
        no_email = self.account("no-email", email=" \t\n", access_token="")
        busy = self.account("busy", access_token="")
        registering = self.account("registering", access_token="")
        missing_token = self.account("missing-token", access_token="")
        missing = 900001
        self.active_run(disabled)
        self.active_run(no_email)
        first_blocker = self.active_run(busy, "waiting")
        self.active_run(busy, "running")
        self.active_run(missing)
        for account_id in (disabled, no_email, busy, registering, missing):
            self.job(account_id=account_id)
        selected = self.selection([missing, disabled, no_email, busy, registering, missing_token, ready, ready])
        # Shift target identities away from account IDs: receipt.target_id is
        # the target row ID, never the business account ID or ordinal.
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),7000,true)",
                        (common.table('operation_selection_targets'),))
        frozen = self.freeze(selected)
        parent, targets = self.rows(selected)
        expected = [
            (missing, "not_executable", "account_missing", None),
            (disabled, "not_executable", "account_deactivated", None),
            (no_email, "not_executable", "account_email_missing", None),
            (busy, "waiting_account", "account_busy", first_blocker),
            (registering, "waiting_account", "registration_in_progress", None),
            (missing_token, "not_executable", "access_token_missing", None),
            (ready, "ready", None, None),
        ]
        self.assertEqual(7, frozen["target_count"])
        self.assertEqual({"ready": 1, "waiting_account": 2, "not_executable": 4}, frozen["preflight_summary"])
        self.assertEqual("ready", frozen["state"])
        self.assertEqual(parent["selected_at"], parent["preflight_at"])
        for ordinal, (target, (account_id, status, reason, blocker)) in enumerate(zip(targets, expected, strict=True), 1):
            self.assertEqual(account_id, target["target_id"])
            self.assertEqual(ordinal, target["ordinal"])
            self.assertGreater(target["id"], 7000)
            check = target["match_evidence"]["preflight"]
            self.assertEqual({"target_id", "status", "reason_code", "checked_at", "blocker_run_id"}, set(check))
            self.assertEqual((target["id"], status, reason, blocker),
                             (check["target_id"], check["status"], check["reason_code"], check["blocker_run_id"]))
            self.assertEqual(parent["selected_at"], datetime.fromisoformat(check["checked_at"]))
            self.assertEqual(parent["selected_at"], datetime.fromisoformat(target["baseline"]["plan_check"]["frozen_at"]))

    def test_complete_snapshot_and_saved_configuration_are_preserved(self):
        account_id = self.account("evidence", access_token="", password="synthetic-password", totp_secret="synthetic-totp",
            plan_last_success_at="saved-success", plan_check_countries=["JP"], plan_check_partial=False,
            plan_check_stale=False, plan_check_country_results=[{
                "country": "JP", "status": "success", "checked_at": "country-time",
                "result": {"ok": True, "private": "must-not-copy"}, "stale": False,
            }], account_promotions=[{
                "plan": "plus", "kind": "trial", "stale": False, "expired": False,
                "expires_at": "future", "private": "must-not-copy",
            }])
        selected = self.selection([account_id], snapshot={"auto_refresh_at_enabled": True, "marker": "saved"})
        with patch("core.bulk_operations.catalog.capture_settings", side_effect=AssertionError("must use saved settings")):
            self.freeze(selected)
        parent, targets = self.rows(selected)
        target = targets[0]
        self.assertEqual({"auto_refresh_at_enabled": True, "marker": "saved"}, parent["config_snapshot"])
        self.assertEqual({"email": "policy-evidence@example.test", "created_at": "2026-10-15T10:00:00"}, target["display_snapshot"])
        check = target["match_evidence"]["preflight"]
        self.assertEqual({"created_at": "2026-10-15T10:00:00", "promotion": "none", "reason_code": None,
                          "preflight": check}, target["match_evidence"])
        self.assertEqual("ready", check["status"])
        baseline = target["baseline"]
        stamp = baseline["plan_check"].pop("frozen_at")
        self.assertEqual(parent["selected_at"], datetime.fromisoformat(stamp))
        self.assertEqual({
            "plan_type": "free", "current_plan_type": "free", "promotion": "none",
            "has_password": True, "totp_enabled": True, "has_access_token": False,
            "codex_credential_state": None, "plan_check": {
                "product": "plus", "status": "success", "ok": True, "countries": ["JP"],
                "partial": False, "checked_at": "saved-success", "plus_offer_kind": "none", "stale": False,
                "country_results": [{"country": "JP", "status": "success", "checked_at": "country-time", "ok": True, "stale": False}],
                "promotions": [{"plan": "plus", "kind": "trial", "stale": False, "expired": False, "expires_at": "future"}],
            },
        }, baseline)

    def test_invalid_policy_callback_and_operation_are_rejected_without_writes(self):
        account_id = self.account("rejected")
        callback = Mock(side_effect=AssertionError("conflicting callback must not run"))
        for operation, kwargs in (
            ("plan_check", {"preflight_policy": "unknown_policy"}),
            ("plan_check", {"preflight_policy": "plan_check_db_v1", "preflight": callback}),
            ("token_refresh", {"preflight_policy": "plan_check_db_v1"}),
        ):
            with self.subTest(operation=operation, policy=kwargs["preflight_policy"]):
                selected = self.selection([account_id], operation=operation)
                before = self.rows(selected)
                with self.assertRaises(common.BulkError):
                    bulk.freeze_selection(selected["id"], **kwargs)
                self.assertEqual(before, self.rows(selected))
        callback.assert_not_called()

    def test_all_active_run_states_block_and_terminal_runs_do_not(self):
        ids, expected = [], []
        for status in ("queued", "running", "cancelling", "settling", "stopping", "waiting"):
            account_id = self.account(f"active-{status}")
            blocker = self.active_run(account_id, status)
            ids.append(account_id)
            expected.append(("waiting_account", "account_busy", blocker))
        for status in ("success", "failed", "cancelled", "attention_required"):
            account_id = self.account(f"terminal-{status}")
            self.active_run(account_id, status)
            ids.append(account_id)
            expected.append(("ready", None, None))
        selected = self.selection(ids)
        frozen = self.freeze(selected)
        self.assertEqual({"ready": 4, "waiting_account": 6, "not_executable": 0}, frozen["preflight_summary"])
        for target, wanted in zip(self.rows(selected)[1], expected, strict=True):
            receipt = target["match_evidence"]["preflight"]
            self.assertEqual(wanted, (receipt["status"], receipt["reason_code"], receipt["blocker_run_id"]))

    def test_registration_state_type_and_normalized_email_ownership(self):
        ids, expected = [], []
        active_states = ("pending", "queued", "running", "stopping", "cancelling", "settling", "waiting", "debug_paused")
        for number, status in enumerate(active_states):
            account_id = self.account(f"job-{status}")
            # Alternate account ownership and normalized email-only ownership.
            self.job(account_id=account_id if number % 2 == 0 else None,
                     email="unrelated@example.test" if number % 2 == 0 else f" POLICY-JOB-{status.upper()}@EXAMPLE.TEST ",
                     status=status, job_type="registration" if number % 2 == 0 else "registration_resume")
            ids.append(account_id)
            expected.append(("waiting_account", "registration_in_progress", None))
        for label, status, job_type, disposition in (
            ("empty-type", "pending", "", "waiting_account"),
            ("null-type", "pending", None, "waiting_account"),
            ("terminal", "success", "registration", "ready"),
            ("unrelated-type", "running", "plan_check", "ready"),
        ):
            account_id = self.account(label)
            self.job(account_id=account_id, status=status, job_type=job_type)
            ids.append(account_id)
            expected.append((disposition, "registration_in_progress" if disposition == "waiting_account" else None, None))
        normalized = self.account("unicode-email", email="\u2003 POLICY-NORMALIZED@EXAMPLE.TEST\u00a0")
        self.job(email="policy-normalized@example.test", status="running")
        ids.append(normalized)
        expected.append(("waiting_account", "registration_in_progress", None))
        selected = self.selection(ids)
        self.freeze(selected)
        for target, wanted in zip(self.rows(selected)[1], expected, strict=True):
            receipt = target["match_evidence"]["preflight"]
            self.assertEqual(wanted, (receipt["status"], receipt["reason_code"], receipt["blocker_run_id"]))

    def test_deactivation_uses_all_original_fields_and_python_whitespace_rules(self):
        ids = [self.account(f"state-{key}", **{key: "\u2003\tDeAcTiVaTeD\u00a0\n"})
               for key in ("account_status", "codex_status", "codex_credential_state")]
        ids.append(self.account("whitespace-email", email="\u2003\t\n\u00a0"))
        # The derived boolean alone is not the domain predicate.
        projected_only = self.account("projection-only")
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {records._qualified(records.ACCOUNTS)} SET deactivated=true WHERE id=%s", (projected_only,))
        ids.append(projected_only)
        selected = self.selection(ids)
        self.freeze(selected)
        checks = [row["match_evidence"]["preflight"] for row in self.rows(selected)[1]]
        self.assertEqual(["account_deactivated"] * 3 + ["account_email_missing", None],
                         [check["reason_code"] for check in checks])
        self.assertEqual(["not_executable"] * 4 + ["ready"], [check["status"] for check in checks])

    def test_saved_auto_refresh_false_and_default_true_do_not_read_live_config(self):
        account_id = self.account("saved-no-token", access_token="")
        with patch("core.bulk_operations.catalog.capture_settings", side_effect=AssertionError("live config read")):
            for snapshot, expected in (({"auto_refresh_at_enabled": False}, "not_executable"), ({}, "ready")):
                with self.subTest(snapshot=snapshot):
                    selected = self.selection([account_id], snapshot=snapshot)
                    self.freeze(selected)
                    parent, targets = self.rows(selected)
                    self.assertEqual(snapshot, parent["config_snapshot"])
                    self.assertEqual(expected, targets[0]["match_evidence"]["preflight"]["status"])

    def test_insert_or_selection_update_failure_rolls_back_all_freeze_facts(self):
        import psycopg

        ids = [self.account("rollback-one"), self.account("rollback-two")]
        for phase, table_name, event in (
            ("insert", "operation_selection_targets", "BEFORE INSERT"),
            ("summary", "operation_selections", "BEFORE UPDATE"),
        ):
            with self.subTest(phase=phase):
                selected = self.selection(ids)
                before = self.rows(selected)
                account_before = [records.get_row(records.ACCOUNTS, account_id) for account_id in ids]
                with common.connect() as conn, conn.cursor() as cur:
                    cur.execute(f"""CREATE OR REPLACE FUNCTION {common.table('policy_freeze_reject')}()
                        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                        RAISE EXCEPTION 'synthetic freeze failure' USING ERRCODE='23514'; END $$""")
                    cur.execute(f"""CREATE TRIGGER policy_freeze_reject {event}
                        ON {common.table(table_name)} FOR EACH ROW
                        EXECUTE FUNCTION {common.table('policy_freeze_reject')}()""")
                try:
                    with self.assertRaises(psycopg.errors.CheckViolation):
                        self.freeze(selected)
                    self.assertEqual(before, self.rows(selected))
                    self.assertEqual(account_before, [records.get_row(records.ACCOUNTS, account_id) for account_id in ids])
                finally:
                    with common.connect() as conn, conn.cursor() as cur:
                        cur.execute(f"DROP TRIGGER policy_freeze_reject ON {common.table(table_name)}")
                self.assertEqual("ready", self.freeze(selected)["state"])

    def test_stale_fence_cannot_freeze_and_successful_replay_preserves_evidence(self):
        selected = self.selection([self.account("fenced")])
        first = bulk.claim_work("selection", "policy-worker-one")[0]
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {common.table('operation_selections')} SET lease_until=now()-interval '1 second' WHERE id=%s",
                        (selected["id"],))
        second = bulk.claim_work("selection", "policy-worker-two")[0]
        before = self.rows(selected)
        with self.assertRaises(common.BulkError) as caught:
            self.freeze(selected, owner_id="policy-worker-one", fence=first["fence"])
        self.assertEqual("lease_lost", caught.exception.code)
        self.assertEqual(before, self.rows(selected))
        self.freeze(selected, owner_id="policy-worker-two", fence=second["fence"])
        frozen = self.rows(selected)
        self.freeze(selected)
        self.assertEqual(frozen, self.rows(selected))

    def test_frozen_policy_evidence_and_parent_foreign_key_remain_protected(self):
        import psycopg

        selected = self.selection([self.account("immutable")])
        self.freeze(selected)
        before = self.rows(selected)
        for mutation in ("baseline='{}'::jsonb", "match_evidence='{}'::jsonb", "target_id=999999"):
            with self.subTest(mutation=mutation):
                with self.assertRaises(psycopg.errors.CheckViolation):
                    with common.connect() as conn, conn.cursor() as cur:
                        cur.execute(f"UPDATE {common.table('operation_selection_targets')} SET {mutation} WHERE selection_id=%s",
                                    (selected["id"],))
                self.assertEqual(before, self.rows(selected))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DELETE FROM {common.table('operation_selections')} WHERE id=%s", (selected["id"],))
        self.assertEqual(before, self.rows(selected))

    def test_empty_query_is_ready_with_zero_summary_and_query_limit_keeps_order(self):
        ids = [self.account(f"query-{number}") for number in range(3)]
        for predicate, limit, expected in (("FALSE", 2, []), ("TRUE", 2, ids[::-1][:2])):
            with self.subTest(predicate=predicate):
                selected = bulk.create_selection(
                    request_key=uuid.uuid4().hex, source={"kind": "query", "query": {"limit": limit}},
                    operation_key="plan_check", config_revision="saved-policy-v1",
                    config_snapshot={"auto_refresh_at_enabled": False},
                )
                frozen = self.freeze(selected, where_sql=predicate)
                parent, targets = self.rows(selected)
                self.assertEqual("ready", frozen["state"])
                self.assertEqual(len(expected), frozen["target_count"])
                self.assertEqual({"ready": len(expected), "waiting_account": 0, "not_executable": 0}, frozen["preflight_summary"])
                self.assertEqual(expected, [target["target_id"] for target in targets])
                self.assertEqual(list(range(1, len(expected) + 1)), [target["ordinal"] for target in targets])
                self.assertEqual(parent["selected_at"], parent["preflight_at"])

    def test_over_capacity_rolls_back_targets_and_selection(self):
        # Missing IDs are valid frozen identities. No 100001 real accounts or
        # business operations are needed to exercise the write/rollback limit.
        selected = self.selection(list(range(1000000, 1100001)))
        before = self.rows(selected)
        with self.assertRaises(common.BulkError) as caught:
            self.freeze(selected)
        self.assertEqual("selection_capacity_exceeded", caught.exception.code)
        self.assertEqual(before, self.rows(selected))

    def test_eligibility_and_baseline_share_the_insert_statement_snapshot(self):
        account_id = self.account("statement-snapshot")
        selected = self.selection([account_id])
        # The INSERT trigger deliberately changes the source row after the
        # statement starts. A subsequent generic callback read would see it;
        # the opt-in policy receipt and baseline must use the earlier snapshot.
        # This is an in-transaction observation test, not concurrent-load proof.
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""CREATE OR REPLACE FUNCTION {common.table('policy_source_change')}()
                RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                UPDATE {records._qualified(records.ACCOUNTS)}
                SET data=jsonb_set(data,'{{access_token}}','\"\"'::jsonb)
                WHERE id=NEW.target_id;
                RETURN NEW; END $$""")
            cur.execute(f"""CREATE TRIGGER policy_source_change BEFORE INSERT
                ON {common.table('operation_selection_targets')} FOR EACH ROW
                EXECUTE FUNCTION {common.table('policy_source_change')}()""")
        try:
            self.freeze(selected)
            target = self.rows(selected)[1][0]
            self.assertEqual("ready", target["match_evidence"]["preflight"]["status"])
            self.assertTrue(target["baseline"]["has_access_token"])
            self.assertEqual("", records.get_row(records.ACCOUNTS, account_id)["access_token"])
        finally:
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"DROP TRIGGER policy_source_change ON {common.table('operation_selection_targets')}")

    def test_current_and_historical_batch_sources_keep_scope_and_consumed_evidence(self):
        import psycopg

        ids = [self.account(f"source-{number}") for number in range(3)]
        original = self.selection(ids)
        self.freeze(original)
        with patch("core.bulk_operations.catalog.capture_settings", return_value={
            "config_revision": "saved-policy-v1", "effective_settings": {"auto_refresh_at_enabled": False},
        }):
            batch = bulk.create_batch(
                request_key=uuid.uuid4().hex, selection_id=original["id"], selection_revision=1,
                operation_key="plan_check", parameters={}, config_revision="saved-policy-v1", start_paused=True,
            )
        original_rows = self.rows(original)
        self.assertEqual("consumed", original_rows[0]["status"])
        middle_target = original_rows[1][1]["id"]
        retry = bulk.create_round(
            batch["id"], request_key=uuid.uuid4().hex, source={"view": "current"},
            selection={"kind": "targets", "target_ids": [middle_target]},
        )
        bulk.freeze_round(retry["id"])
        records.patch_row(records.ACCOUNTS, ids[1], {"access_token": ""})
        for view, expected in (("current", ids), ("round", [ids[1]])):
            with self.subTest(view=view):
                source = {"kind": "batch_targets", "batch_id": batch["id"], "view": view,
                          "selection": {"kind": "all"}}
                if view == "round":
                    source["round_id"] = retry["id"]
                copied = bulk.create_selection(
                    request_key=uuid.uuid4().hex, source=source, operation_key="plan_check",
                    config_revision="saved-policy-v1", config_snapshot={"auto_refresh_at_enabled": False},
                )
                self.freeze(copied)
                parent, targets = self.rows(copied)
                self.assertIsNotNone(parent["basis_summary_revision"])
                self.assertEqual(expected, [target["target_id"] for target in targets])
                self.assertEqual(list(range(1, len(expected) + 1)), [target["ordinal"] for target in targets])
                for target in targets:
                    check = target["match_evidence"]["preflight"]
                    self.assertEqual(target["id"], check["target_id"])
                    self.assertEqual("not_executable" if target["target_id"] == ids[1] else "ready", check["status"])
        protected = self.rows(original)
        self.freeze(original)
        self.assertEqual(protected, self.rows(original))
        with self.assertRaises(psycopg.errors.CheckViolation):
            with common.connect() as conn, conn.cursor() as cur:
                cur.execute(f"UPDATE {common.table('operation_selection_targets')} SET match_evidence='{{}}'::jsonb WHERE id=%s",
                            (middle_target,))
        self.assertEqual(protected, self.rows(original))

    def test_registration_email_propagation_stays_inside_each_5000_target_chunk(self):
        records.init()
        with common.connect() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {records._qualified(records.ACCOUNTS)}
                (email,created_at,updated_at,plan_type,current_plan_type,plan_check_status,plan_check_ok,plus_promo_kind,data)
                SELECT CASE WHEN number=2 THEN 'shared@example.test'
                            WHEN number=5001 THEN ' SHARED@EXAMPLE.TEST '
                            ELSE 'policy-chunk-' || number::text || '@example.test' END,
                    '2026-10-15T10:00:00','2026-10-15T10:00:00','free','free','success',true,'none',
                    '{{"access_token":"synthetic-token"}}'::jsonb
                FROM generate_series(1,5001) number ORDER BY number RETURNING id""")
            ids = [int(row["id"]) for row in cur.fetchall()]
        # SQL BTRIM does not strip tabs: this job is fetched only through the
        # first account ID. Python normalization then occupies account 2 in
        # that same callback page, but must not leak into ordinal 5001.
        self.job(account_id=ids[0], email="\tshared@example.test\t")
        generic = self.selection(ids)
        chunk_sizes = []
        self.freeze_generic(generic, chunk_sizes=chunk_sizes)
        self.assertEqual([5000, 1], chunk_sizes)
        selected = self.selection(ids)
        self.freeze(selected)
        for selection in (generic, selected):
            parent, targets = self.rows(selection)
            self.assertEqual({"ready": 4999, "waiting_account": 2, "not_executable": 0}, parent["preflight_summary"])
            self.assertEqual(5001, parent["total_count"])
            self.assertEqual(ids, [target["target_id"] for target in targets])
            self.assertEqual(list(range(1, 5002)), [target["ordinal"] for target in targets])
            for index, target in enumerate(targets):
                check = target["match_evidence"]["preflight"]
                expected = ("waiting_account", "registration_in_progress", None) if index < 2 else ("ready", None, None)
                self.assertEqual(expected, (check["status"], check["reason_code"], check["blocker_run_id"]),
                                 f"ordinal={target['ordinal']}")
        self.assert_complete_facts_equal(generic, selected)

    def test_non_ascii_kelvin_fallback_matches_generic_complete_facts(self):
        from core.storage.operations import plan_preflight

        kelvin = self.account("kelvin", email="\u212aelvin@example.test")
        ready = self.account("kelvin-ready")
        busy = self.account("kelvin-run")
        no_token = self.account("kelvin-no-token", access_token="")
        blocker = self.active_run(busy)
        self.job(email="kelvin@example.test")
        ids = [kelvin, ready, busy, no_token]
        generic = self.selection(ids)
        self.freeze_generic(generic)
        generic_targets = self.rows(generic)[1]
        last_generic_id = max(target["id"] for target in generic_targets)
        selected = self.selection(ids)
        before_parent, before_targets = self.rows(selected)
        self.assertEqual([], before_targets)
        original_freeze = plan_preflight.freeze

        def observe_unsupported_attempt(cur, **kwargs):
            result = original_freeze(cur, **kwargs)
            self.assertIsNone(result)
            cur.execute(f"SELECT * FROM {common.table('operation_selections')} WHERE id=%s", (selected["id"],))
            self.assertEqual(before_parent, dict(cur.fetchone()))
            cur.execute(f"SELECT * FROM {common.table('operation_selection_targets')} WHERE selection_id=%s", (selected["id"],))
            self.assertEqual([], cur.fetchall())
            cur.execute(f"SELECT last_value FROM {common.table('operation_selection_targets_id_seq')}")
            self.assertEqual(last_generic_id, cur.fetchone()["last_value"])
            return result

        with patch.object(plan_preflight, "freeze", side_effect=observe_unsupported_attempt) as attempted, \
                patch.object(plan_preflight, "fallback_receipts", wraps=plan_preflight.fallback_receipts) as fallback:
            self.freeze(selected)
        attempted.assert_called_once()
        fallback.assert_called_once()
        target_ids = sorted(target["id"] for target in self.rows(selected)[1])
        self.assertEqual(list(range(last_generic_id + 1, last_generic_id + 5)), target_ids)
        expected = [("waiting_account", "registration_in_progress", None), ("ready", None, None),
                    ("waiting_account", "account_busy", blocker), ("not_executable", "access_token_missing", None)]
        for selection in (generic, selected):
            parent, targets = self.rows(selection)
            self.assertEqual({"ready": 1, "waiting_account": 2, "not_executable": 1}, parent["preflight_summary"])
            self.assertEqual(4, parent["total_count"])
            self.assertEqual(ids, [target["target_id"] for target in targets])
            for target, wanted in zip(targets, expected, strict=True):
                check = target["match_evidence"]["preflight"]
                self.assertEqual(wanted, (check["status"], check["reason_code"], check["blocker_run_id"]))
        self.assert_complete_facts_equal(generic, selected)

    def test_nested_null_and_non_mapping_config_match_generic_eligibility(self):
        # preflight_many selects config_snapshot when the key is present;
        # null/non-mapping nested values become {}, whose refresh default is true.
        cases = [
            ({"auto_refresh_at_enabled": True, "config_snapshot": {"auto_refresh_at_enabled": False}}, "not_executable"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": {"auto_refresh_at_enabled": True}}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": None}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": []}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": ["invalid"]}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": "invalid"}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": False}, "ready"),
            ({"auto_refresh_at_enabled": False, "config_snapshot": 7}, "ready"),
        ]
        accounts = [self.account("nested-ascii", access_token=""),
                    self.account("nested-unicode", email="\u212aelvin-nested@example.test", access_token="")]
        for account_id in accounts:
            for snapshot, expected in cases:
                with self.subTest(account_id=account_id, snapshot=snapshot):
                    generic = self.selection([account_id], snapshot=snapshot)
                    self.freeze_generic(generic)
                    selected = self.selection([account_id], snapshot=snapshot)
                    self.freeze(selected)
                    for selection in (generic, selected):
                        parent, targets = self.rows(selection)
                        self.assertEqual(snapshot, parent["config_snapshot"])
                        self.assertEqual({"ready": int(expected == "ready"), "waiting_account": 0,
                                          "not_executable": int(expected == "not_executable")}, parent["preflight_summary"])
                        check = targets[0]["match_evidence"]["preflight"]
                        self.assertEqual((expected, "access_token_missing" if expected == "not_executable" else None, None),
                                         (check["status"], check["reason_code"], check["blocker_run_id"]))
                    self.assert_complete_facts_equal(generic, selected)
