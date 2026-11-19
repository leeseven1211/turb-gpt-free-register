"""Exact proxy-child reconciliation through native PostgreSQL entry points.

Only the root's exclusive test slot may enable SETTLEMENT_DB_TESTS.  This module
does not import the PostgreSQL fixture otherwise.

These are storage-directed cases: no callback, browser, provider actor or
carrier is started.  Scoped owner_liveness answers model an already exited
fixture owner; they are not evidence of a real process kill or 900-second
orphan detection.  Pool children, operation rows, receipts, claims and SQL
failures remain real.  Recovery must never call a proxy/provider release.
"""
from __future__ import annotations

import copy
import os
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
import time
import uuid
from unittest.mock import patch


if os.getenv("SETTLEMENT_DB_TESTS") == "1":
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row

    from core.accounts import operation_results
    from core.operations import settlement
    from core.operations.settlement_contracts import OperationSettlementFenced, seal_intent
    from core.proxy.provider import ProxyLease
    from core.storage import postgres, records
    from core.storage.operations import common, legacy_task_store, permits, settlements, store
    from core.storage.proxy import leases as proxy_leases
    from core.storage.proxy import pool
    from tests.operations.test_settlement_resource_faults import TransactionFault
    from tests.support_pg import PostgresTestCase

    class ProxyExpirySettlementPostgresTests(PostgresTestCase):
        """Synthetic ownership, real pool/settlement SQL, no live actor."""

        def setUp(self):
            super().setUp()
            self.assertTrue(all(value == 0 for value in settlement.active_counts().values()))
            self.assertFalse(settlement._THREAD is not None and settlement._THREAD.is_alive())
            self.stack = ExitStack()
            self.addCleanup(self.stack.close)
            self.stack.enter_context(patch.object(legacy_task_store, "_SCHEMA", self.schema))
            self.stack.enter_context(patch.object(legacy_task_store, "_READY_KEY", ""))
            self.stack.enter_context(patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("proxy expiry SQL cases cannot call a remote service"),
            ))
            legacy_task_store.init()
            store.reset_ready()
            store.init()
            permits.ensure_tables()
            records.init()
            self.domain = permits._settlement_domain()
            self.owner = {
                **permits.current_owner(),
                "pid": 1073741823,
                "process_start": "proxy-expiry-sql-fixture",
            }
            self.cases = []
            self.addCleanup(self._close_originals)

        @contextmanager
        def _owner_state(self, state):
            original = permits.owner_liveness
            identity = tuple(self.owner[key] for key in ("host_id", "pid", "process_start"))

            def classify(owner):
                actual = tuple(owner.get(key) for key in ("host_id", "pid", "process_start"))
                return state if actual == identity else original(owner)

            with patch.object(permits, "owner_liveness", side_effect=classify):
                yield

        @contextmanager
        def _passive_only(self):
            with (
                patch("core.proxy.provider.release_proxy",
                      side_effect=AssertionError("recovery must not release a provider")),
                patch("core.proxy.pool.release",
                      side_effect=AssertionError("recovery must not return a pool child")),
                patch.object(pool, "release",
                             side_effect=AssertionError("recovery must not mutate the pool")),
                patch.object(proxy_leases, "release",
                             side_effect=AssertionError("recovery must not release a proxy child")),
            ):
                yield

        def _row(self, table, field, value):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table} WHERE {field}=%s", (value,))
                row = cur.fetchone()
                return dict(row) if row else None

        def _operation_resource(self, case):
            return self._row(common._table("operation_resources"), "id", case.resource["id"])

        def _permit(self, case):
            return self._row(permits._permit_table(self.schema), "permit_id", case.origin["permit_id"])

        def _proxy_snapshot(self):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                result = {}
                for name in ("proxy_leases", "proxy_pool_resources"):
                    cur.execute(f"SELECT * FROM {postgres.qualified(name)} ORDER BY id")
                    result[name] = [dict(row) for row in cur.fetchall()]
                return result

        def _business_snapshot(self, case):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                result = {}
                for name, field, value in (
                    ("operation_tasks", "id", case.task["id"]),
                    ("operation_runs", "id", case.run["id"]),
                    ("operation_events", "run_id", case.run["id"]),
                    ("operation_settlement_receipts", "run_id", case.run["id"]),
                    ("operation_settlement_dispositions", "run_id", case.run["id"]),
                ):
                    cur.execute(
                        f"SELECT * FROM {common._table(name)} WHERE {field}=%s ORDER BY id",
                        (value,),
                    )
                    result[name] = [dict(row) for row in cur.fetchall()]
                return result

        def _seed_ready_pool(self, *, ttl_seconds=1800):
            profile = "proxy-expiry-" + uuid.uuid4().hex
            slot = pool.reserve_slot(profile, "1024proxy", max_size=30, timeout=60)
            self.assertIsNotNone(slot)
            acquired = datetime.now()
            endpoint = f"192.0.2.{len(self.cases) + 1}:8080"
            anchor = ProxyLease(
                uuid.uuid4().hex, "1024proxy", f"http://{endpoint}", endpoint, acquired,
                expires_at=acquired + timedelta(seconds=ttl_seconds),
                exit_ip=f"198.51.100.{len(self.cases) + 1}", region="US",
                metadata={"persistent_lease": True},
            )
            proxy_leases.reserve_pending(
                lease_id=anchor.lease_id, provider=anchor.provider, endpoint=anchor.endpoint,
                proxy_url=anchor.proxy_url, acquired_at=acquired.isoformat(),
                expires_at=anchor.expires_at.isoformat(), purpose="pool-reserve",
            )
            proxy_leases.activate(
                lease_id=anchor.lease_id, exit_ip=anchor.exit_ip, region="US",
                expires_at=anchor.expires_at.isoformat(),
            )
            self.assertTrue(pool.publish(slot, anchor))
            return slot, anchor

        def _case(self, *, shared_pool=None, ttl_seconds=1800, min_ttl=300):
            task = store.create_runtime_task(
                task_type="plan_check", account_id=None, email="proxy-expiry@example.test",
                resource_family="proxy-expiry-sql", trigger="synthetic_proxy_expiry",
            )
            run = task["run"]
            execution_id = uuid.uuid4().hex
            self.assertTrue(store.claim_run(
                run["id"], execution_id=execution_id, worker_pid=self.owner["pid"],
            ))
            origin = {
                "version": 1, "domain_id": self.domain.domain_id,
                "operation_schema": self.domain.operation_schema,
                "permit_schema": self.domain.permit_schema,
                "task_id": task["id"], "run_id": run["id"], "run_uuid": run["run_uuid"],
                "execution_id": execution_id, "permit_id": uuid.uuid4().hex,
                "ticket_id": uuid.uuid4().hex, "owner": dict(self.owner),
                "lease_requirement": "accountless",
            }
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""INSERT INTO {permits._permit_table(self.schema)}
                    (permit_id,execution_key,execution_id,run_id,task_type,owner,metadata)
                    VALUES (%s,%s,%s,%s,'plan_check',%s::jsonb,%s::jsonb)""",
                    (origin["permit_id"], f"operation_run:{run['id']}", execution_id, run["id"],
                     settlements._json(self.owner), settlements._json({"settlement_ticket": origin})),
                )
            slot, anchor = shared_pool or self._seed_ready_pool(ttl_seconds=ttl_seconds)
            child = pool.claim(
                slot["profile_key"], min_ttl=min_ttl, max_age=60, allow_reuse=True, reuse_limit=100,
                correlation={"purpose": "plan-check", "operation_task_id": task["id"],
                             "operation_run_id": run["id"]},
            )
            self.assertIsNotNone(child)
            self.assertEqual(slot["resource_id"], child.metadata["pool_resource_id"])
            self.assertEqual(anchor.lease_id, child.metadata["pool_anchor_id"])
            self.assertTrue(pool.mark_delivered(child))
            child_row = records.get_row_by(records.PROXY_LEASES, "lease_id", child.lease_id)
            binding = {
                "version": 1, "domain_id": self.domain.domain_id,
                "task_id": task["id"], "run_id": run["id"], "run_uuid": run["run_uuid"],
                "execution_id": execution_id, "provider": child.provider,
                "lease_id": child.lease_id, "pool_resource_id": slot["resource_id"],
                "pool_anchor_id": anchor.lease_id,
                "acquired_at": child_row["acquired_at"], "expires_at": child_row["expires_at"],
                "actor_scope": "owner_process",
            }
            resource = store.register_resource(
                run["id"], resource_type="proxy_lease", provider=child.provider,
                external_id=f"proxy-expiry:{execution_id}",
                detail={"execution_id": execution_id, "proxy_pool_child": binding},
            )
            case = SimpleNamespace(
                task=task, run=run, origin=origin, slot=slot, anchor=anchor, child=child,
                binding=binding, resource=resource, receipt=None, disposition=None, intent=None,
            )
            self.cases.append(case)
            return case

        def _payload(self, case):
            return {
                "resource_id": case.resource["id"], "resource_uuid": case.resource["resource_uuid"],
                "run_id": case.run["id"], "execution_id": case.origin["execution_id"],
                "external_id": case.resource["external_id"],
                "proxy_pool_child": copy.deepcopy(case.binding),
            }

        def _terminal(self, case, *, payload=None, kind="terminal"):
            case.intent = seal_intent(
                kind=kind, origin=case.origin,
                payload=({"status": "success", "message": "original confirmed synthetic result",
                          "result_summary": {"fixture_business_count": 1}}
                         if kind == "terminal" else
                         {"reason": "synthetic continuation", "delay_seconds": 60, "stage": "waiting"}),
                obligations=({
                    "action_kind": "resource_release",
                    "resource_identity": case.resource["resource_uuid"],
                    "payload": payload if payload is not None else self._payload(case),
                    "blocks_permit": True,
                },),
            )
            case.receipt = settlements.submit_intent(case.intent, domain=self.domain)
            return case.receipt

        def _orphan_disposition(self, case):
            """Start after legal independent recovery, without timing claims."""
            store.finish_run(
                case.run["id"], status="interrupted", execution_id=case.origin["execution_id"],
                message="synthetic already recovered original",
                result_summary={"outcome": "interrupted", "fixture_business_count": 1},
            )
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(
                    f"""SELECT event_uuid FROM {common._table('operation_events')}
                    WHERE run_id=%s AND event_type='run.interrupted' ORDER BY id DESC LIMIT 1""",
                    (case.run["id"],),
                )
                event = cur.fetchone()
                self.assertIsNotNone(event)
                case.disposition = settlements.write_disposition(
                    cur, ticket=case.origin,
                    result={"status": "interrupted", "event_uuid": event["event_uuid"],
                            "result_summary": {"outcome": "interrupted", "fixture_business_count": 1},
                            "original_intent_committed": False,
                            "recovery_reason": "worker_exit_confirmed",
                            "resource_disposition": "cleanup_pending"},
                )
            return case.disposition

        def _resource_job(self, case):
            with postgres.connect(row_factory=dict_row) as conn, conn.cursor() as cur:
                cur.execute(
                    f"""SELECT * FROM {common._table('operation_settlement_cleanup')}
                    WHERE permit_id=%s AND execution_id=%s AND action_kind='resource_release'
                    ORDER BY id""",
                    (case.origin["permit_id"], case.origin["execution_id"]),
                )
                jobs = [dict(row) for row in cur.fetchall()]
            self.assertEqual(1, len(jobs))
            return jobs[0]

        def _make_due(self, case):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {common._table('operation_settlement_cleanup')}
                    SET next_attempt_at=now() WHERE permit_id=%s AND execution_id=%s
                    AND state='pending'""",
                    (case.origin["permit_id"], case.origin["execution_id"]),
                )

        def _run_resource(self, case):
            self._make_due(case)
            expected_id = self._resource_job(case)["id"]
            result = settlements.run_cleanup_once(
                domain=self.domain, permit_id=case.origin["permit_id"],
                execution_id=case.origin["execution_id"],
            )
            if result is not None:
                self.assertEqual(expected_id, result["cleanup_id"])
            return result

        def _assert_blocked(self, case):
            self.assertNotEqual("released", self._operation_resource(case)["state"])
            self.assertIsNone(self._permit(case)["released_at"])
            self.assertTrue(settlements.cleanup_blocks_permit(
                case.origin["permit_id"], case.origin["execution_id"], domain=self.domain,
            ))
            self.assertFalse(permits.release(
                case.origin["permit_id"], case.origin["execution_id"],
                schema=self.schema, database_url=self.domain.database_url,
            ))

        def _close_receipt(self, case):
            with self._owner_state("exited"):
                for _ in range(8):
                    self._make_due(case)
                    outcome = settlements.run_cleanup_once(
                        domain=self.domain, permit_id=case.origin["permit_id"],
                        execution_id=case.origin["execution_id"],
                    )
                    if outcome is None:
                        break
                    if outcome.get("blocked"):
                        settlements.retry_cleanup(domain=self.domain, identity=outcome["identity"])
                        continue
                    self.assertIn(outcome["state"], {"done", "superseded"})
                self.assertFalse(settlements.cleanup_blocks_permit(
                    case.origin["permit_id"], case.origin["execution_id"], domain=self.domain,
                ))
                self.assertTrue(permits.release(
                    case.origin["permit_id"], case.origin["execution_id"],
                    schema=self.schema, database_url=self.domain.database_url,
                ))

        def _close_originals(self):
            """Normal owner cleanup remains available even while RED is expected.

            Restore intentionally corrupted input, then use the existing live
            cleanup handle to return its own child and confirm the real ledger.
            Never write a cleanup job's done flag or invent a callback handoff.
            """
            for case in reversed(self.cases):
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {common._table('operation_resources')}
                        SET detail=detail || %s::jsonb WHERE id=%s""",
                        (settlements._json({"execution_id": case.origin["execution_id"],
                                            "proxy_pool_child": case.binding}), case.resource["id"]),
                    )
                    cur.execute(
                        f"""UPDATE {common._table('operation_settlement_cleanup')}
                        SET payload=%s::jsonb WHERE permit_id=%s AND execution_id=%s
                        AND action_kind='resource_release'""",
                        (settlements._json(self._payload(case)),
                         case.origin["permit_id"], case.origin["execution_id"]),
                    )
                route = SimpleNamespace(
                    lease=case.child, provider=case.child.provider,
                    release=lambda reason=None, fault=False, child=case.child:
                        pool.release(child, reason=reason or "fixture_owner_close", fault=fault),
                )
                cleanup = operation_results.AccountRouteCleanup(
                    route, run_id=case.run["id"], domain=self.domain,
                )
                cleanup.resource_id = case.resource["id"]
                self.assertTrue(cleanup.release())
                if case.disposition is not None:
                    with self._owner_state("exited"):
                        self.assertIsNotNone(settlements.confirm_disposition_resources(
                            case.origin, domain=self.domain,
                        ))
                        self.assertTrue(permits.release(
                            case.origin["permit_id"], case.origin["execution_id"],
                            schema=self.schema, database_url=self.domain.database_url,
                        ))
                else:
                    if case.receipt is None:
                        self._terminal(case)
                    self._close_receipt(case)

        def test_terminal_released_or_recent_child_confirms_without_changing_proxy_rows(self):
            for child_state in ("released", "recent"):
                with self.subTest(child_state=child_state):
                    case = self._case()
                    pool.release(case.child, reason="original_business_finished")
                    if child_state == "recent":
                        row = records.get_row_by(records.PROXY_LEASES, "lease_id", case.child.lease_id)
                        records.patch_row(records.PROXY_LEASES, row["id"], {
                            "state": "recent", "exit_ip": None, "endpoint_owner": False,
                            "recent_until": (datetime.now() + timedelta(minutes=2)).isoformat(),
                        })
                    self._terminal(case)
                    proxy_before = self._proxy_snapshot()
                    business_before = self._business_snapshot(case)
                    with self._owner_state("exited"), self._passive_only():
                        result = self._run_resource(case)
                        self.assertEqual("done", result["state"])
                        self.assertEqual("released", self._operation_resource(case)["state"])
                        self.assertEqual(proxy_before, self._proxy_snapshot())
                        self.assertEqual(business_before, self._business_snapshot(case))
                        self._close_receipt(case)
                    self.assertIsNotNone(self._permit(case)["released_at"])

        def test_short_natural_child_expiry_preserves_live_g2_on_a_new_anchor(self):
            # Every child inherits its anchor's expiry.  A still-live G2 after
            # G1's natural expiry therefore requires its own real new anchor.
            case = self._case(ttl_seconds=3.5, min_ttl=0)
            successor = self._case()
            expires = datetime.fromisoformat(case.binding["expires_at"])
            self.assertNotEqual(case.anchor.lease_id, successor.anchor.lease_id)
            self.assertGreater(datetime.fromisoformat(successor.binding["expires_at"]), expires)
            self.assertLess(datetime.now(), expires, "short fixture expired before its negative assertion")
            self._terminal(case)
            proxy_before = self._proxy_snapshot()
            successor_before = (self._business_snapshot(successor), self._operation_resource(successor),
                                self._permit(successor))
            business_before = self._business_snapshot(case)
            with self._owner_state("exited"), self._passive_only():
                self.assertEqual("pending", self._run_resource(case)["state"])
                self._assert_blocked(case)
                deadline = time.monotonic() + 8
                while datetime.now() < expires and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertGreaterEqual(datetime.now(), expires)
                self.assertEqual("done", self._run_resource(case)["state"])
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self.assertEqual(successor_before, (
                    self._business_snapshot(successor), self._operation_resource(successor),
                    self._permit(successor),
                ))
                self.assertEqual(business_before, self._business_snapshot(case))
                self._close_receipt(case)
            self.assertIsNotNone(self._permit(case)["released_at"])

        def test_released_g1_preserves_live_g2_sharing_the_same_anchor(self):
            case = self._case()
            successor = self._case(shared_pool=(case.slot, case.anchor))
            self.assertNotEqual(case.child.lease_id, successor.child.lease_id)
            self.assertEqual(case.anchor.lease_id, successor.anchor.lease_id)
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case)
            proxy_before = self._proxy_snapshot()
            successor_before = (
                self._business_snapshot(successor), self._operation_resource(successor),
                self._permit(successor),
            )
            business_before = self._business_snapshot(case)
            with self._owner_state("exited"), self._passive_only():
                self.assertEqual("done", self._run_resource(case)["state"])
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self.assertEqual(successor_before, (
                    self._business_snapshot(successor), self._operation_resource(successor),
                    self._permit(successor),
                ))
                self.assertEqual(business_before, self._business_snapshot(case))
                self._close_receipt(case)

        def test_payload_identity_mismatches_never_confirm_original_resource(self):
            mutations = (
                ("payload", "resource_id", 2147483647),
                ("payload", "resource_uuid", "replacement-resource"),
                ("payload", "external_id", "replacement-external"),
                ("payload", "execution_id", "replacement-execution"),
                ("binding", "version", 2),
                ("binding", "domain_id", "replacement-domain"),
                ("binding", "task_id", 2147483647),
                ("binding", "run_id", 2147483647),
                ("binding", "run_uuid", "replacement-run"),
                ("binding", "execution_id", "replacement-execution"),
                ("binding", "lease_id", "replacement-child"),
                ("binding", "provider", "replacement-provider"),
                ("binding", "pool_resource_id", "replacement-pool-resource"),
                ("binding", "pool_anchor_id", "replacement-anchor"),
                ("binding", "acquired_at", "2001-01-01T00:00:00"),
                ("binding", "expires_at", "2001-01-01T00:00:00"),
            )
            for scope, field, replacement in mutations:
                with self.subTest(scope=scope, field=field):
                    case = self._case()
                    pool.release(case.child, reason="original_business_finished")
                    payload = self._payload(case)
                    target = payload if scope == "payload" else payload["proxy_pool_child"]
                    target[field] = replacement
                    self._terminal(case, payload=payload)
                    proxy_before = self._proxy_snapshot()
                    business_before = self._business_snapshot(case)
                    with self._owner_state("exited"), self._passive_only():
                        result = self._run_resource(case)
                        expected = ("pending" if scope == "payload" and field in {"resource_id", "resource_uuid"}
                                    else "reconciliation_required")
                        self.assertEqual(expected, result["state"])
                        self._assert_blocked(case)
                    self.assertEqual(proxy_before, self._proxy_snapshot())
                    self.assertEqual(business_before, self._business_snapshot(case))

        def test_defer_receipt_keeps_proxy_reconciliation_pending(self):
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case, kind="defer")
            proxy_before = self._proxy_snapshot()
            business_before = self._business_snapshot(case)
            with self._owner_state("exited"), self._passive_only():
                self.assertEqual("reconciliation_required", self._run_resource(case)["state"])
                self._assert_blocked(case)
            self.assertEqual(proxy_before, self._proxy_snapshot())
            self.assertEqual(business_before, self._business_snapshot(case))

        def test_real_child_missing_or_changed_identity_cannot_authorize_resource_cas(self):
            from core.storage.operations import proxy_resources

            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            original_resource = self._operation_resource(case)
            original_proxy = self._proxy_snapshot()
            # SAVEPOINT rollback restores each injected bad input exactly.
            # No changed timestamp is used as a successful expiry fixture.
            changes = (
                ("missing", None, None),
                ("expires_missing", "expires_at", None),
                ("expires_invalid", "expires_at", "invalid-fixture-timestamp"),
                ("expires_changed", "expires_at", "2001-01-01T00:00:00"),
                ("acquired_changed", "acquired_at", "2001-01-01T00:00:00"),
                ("provider_changed", "provider", "different-provider"),
                ("task_changed", "operation_task_id", 2147483647),
                ("run_changed", "operation_run_id", 2147483647),
                ("resource_changed", "data.pool_resource_id", "different-pool-resource"),
                ("anchor_changed", "data.pool_anchor_id", "different-anchor"),
            )
            with self._owner_state("exited"), self._passive_only():
                with common.settlement_scope(self.domain), common._connect() as conn, conn.cursor() as cur:
                    for label, field, replacement in changes:
                        with self.subTest(change=label):
                            cur.execute("SAVEPOINT proxy_child_bad_input")
                            try:
                                if field is None:
                                    cur.execute(
                                        f"DELETE FROM {postgres.qualified('proxy_leases')} WHERE lease_id=%s",
                                        (case.child.lease_id,),
                                    )
                                elif field.startswith("data."):
                                    key = field.split(".", 1)[1]
                                    cur.execute(
                                        f"""UPDATE {postgres.qualified('proxy_leases')}
                                        SET data=data || %s::jsonb WHERE lease_id=%s""",
                                        (settlements._json({key: replacement}), case.child.lease_id),
                                    )
                                else:
                                    cur.execute(
                                        sql.SQL("UPDATE {} SET {}=%s WHERE lease_id=%s").format(
                                            sql.SQL(postgres.qualified("proxy_leases")), sql.Identifier(field),
                                        ),
                                        (replacement, case.child.lease_id),
                                    )
                                self.assertFalse(proxy_resources.reconcile_proxy_resource(
                                    cur, resource=original_resource, binding=case.binding,
                                    origin=case.origin, domain=self.domain,
                                ))
                                cur.execute(
                                    f"SELECT * FROM {common._table('operation_resources')} WHERE id=%s",
                                    (case.resource["id"],),
                                )
                                self.assertEqual(original_resource, dict(cur.fetchone()))
                            finally:
                                cur.execute("ROLLBACK TO SAVEPOINT proxy_child_bad_input")
                                cur.execute("RELEASE SAVEPOINT proxy_child_bad_input")
            self.assertEqual(original_proxy, self._proxy_snapshot())
            self.assertIsNone(self._permit(case)["released_at"])

        def test_lost_cleanup_claim_cannot_write_resource_or_complete_another_claim(self):
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case)
            resource_before = self._operation_resource(case)
            proxy_before = self._proxy_snapshot()
            business_before = self._business_snapshot(case)
            original_execute = settlements._execute_cleanup
            stolen_token = uuid.uuid4().hex
            captured = {}

            def invalidate_claim(job, **kwargs):
                if job["action_kind"] != "resource_release":
                    return original_execute(job, **kwargs)
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {common._table('operation_settlement_cleanup')}
                        SET claim_token=%s WHERE id=%s AND claim_token=%s AND state='claimed'""",
                        (stolen_token, job["id"], job["claim_token"]),
                    )
                    self.assertEqual(1, cur.rowcount)
                captured["job"] = dict(job)
                return original_execute(job, **kwargs)

            try:
                with self._owner_state("exited"), self._passive_only():
                    with patch.object(settlements, "_execute_cleanup", side_effect=invalidate_claim):
                        outcome = self._run_resource(case)
                    self.assertIn(outcome["state"], {"pending", "claim_lost"})
                    self.assertIn("job", captured)
                    job_after = self._resource_job(case)
                    self.assertEqual("claimed", job_after["state"])
                    self.assertEqual(stolen_token, job_after["claim_token"])
                    self.assertIsNone(job_after["completed_at"])
                    self.assertEqual(resource_before, self._operation_resource(case))
                    self._assert_blocked(case)
                    self.assertEqual(proxy_before, self._proxy_snapshot())
                    self.assertEqual(business_before, self._business_snapshot(case))
            finally:
                # Undo only the deliberate claim corruption.  This is not an
                # elapsed 30-second timeout test and never forges job completion.
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {common._table('operation_settlement_cleanup')}
                        SET state='pending',claim_token=NULL,claim_until=NULL,next_attempt_at=now()
                        WHERE permit_id=%s AND execution_id=%s AND state='claimed' AND claim_token=%s""",
                        (case.origin["permit_id"], case.origin["execution_id"], stolen_token),
                    )
            with self._owner_state("exited"), self._passive_only():
                self.assertEqual("done", self._run_resource(case)["state"])
                self._close_receipt(case)

        def test_alive_unverified_external_and_legacy_owners_cannot_confirm_resource(self):
            for gate in ("alive", "unverified", "external", "legacy"):
                with self.subTest(gate=gate):
                    case = self._case()
                    pool.release(case.child, reason="original_business_finished")
                    payload = self._payload(case)
                    if gate == "external":
                        case.binding["actor_scope"] = "external"
                        payload["proxy_pool_child"]["actor_scope"] = "external"
                        detail = {"execution_id": case.origin["execution_id"],
                                  "proxy_pool_child": case.binding}
                    elif gate == "legacy":
                        payload.pop("proxy_pool_child")
                        detail = {"execution_id": case.origin["execution_id"]}
                    else:
                        detail = {"execution_id": case.origin["execution_id"],
                                  "proxy_pool_child": case.binding}
                    with postgres.connect() as conn, conn.cursor() as cur:
                        cur.execute(
                            f"UPDATE {common._table('operation_resources')} SET detail=%s::jsonb WHERE id=%s",
                            (settlements._json(detail), case.resource["id"]),
                        )
                    self._terminal(case, payload=payload)
                    proxy_before = self._proxy_snapshot()
                    business_before = self._business_snapshot(case)
                    with self._owner_state(gate if gate in {"alive", "unverified"} else "exited"), self._passive_only():
                        result = self._run_resource(case)
                        if gate in {"alive", "unverified"}:
                            self.assertIsNone(result)
                        else:
                            self.assertEqual("pending", result["state"])
                        self._assert_blocked(case)
                    self.assertEqual(proxy_before, self._proxy_snapshot())
                    self.assertEqual(business_before, self._business_snapshot(case))

        def test_orphan_disposition_appends_resource_proof_without_rewriting_result(self):
            case = self._case()
            # Begin after an independently recorded interrupted result.  This
            # does not shorten or claim to exercise the 900-second detector.
            self._orphan_disposition(case)
            business_before = self._business_snapshot(case)
            with self._owner_state("exited"), self._passive_only():
                self.assertIsNone(settlements.confirm_disposition_resources(case.origin, domain=self.domain))
                self._assert_blocked(case)
            pool.release(case.child, reason="original_business_finished")
            proxy_before = self._proxy_snapshot()
            with self._owner_state("exited"), self._passive_only():
                confirmation = settlements.confirm_disposition_resources(case.origin, domain=self.domain)
                self.assertIsNotNone(confirmation)
                self.assertEqual(
                    confirmation,
                    settlements.confirm_disposition_resources(case.origin, domain=self.domain),
                )
                self.assertEqual("released", self._operation_resource(case)["state"])
                self.assertEqual(business_before, self._business_snapshot(case))
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self.assertTrue(permits.release(
                    case.origin["permit_id"], case.origin["execution_id"],
                    schema=self.schema, database_url=self.domain.database_url,
                ))

        @contextmanager
        def _mismatched_permit_owner(self, case, field):
            changed = dict(self.owner)
            changed[field] = {
                "host_id": "different-fixture-host",
                "pid": 1073741822,
                "process_start": "different-fixture-start",
            }[field]
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {permits._permit_table(self.schema)} SET owner=%s::jsonb WHERE permit_id=%s",
                    (settlements._json(changed), case.origin["permit_id"]),
                )
            try:
                yield
            finally:
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE {permits._permit_table(self.schema)} SET owner=%s::jsonb WHERE permit_id=%s",
                        (settlements._json(self.owner), case.origin["permit_id"]),
                    )

        def test_terminal_permit_owner_must_match_persisted_ticket_before_resource_cas(self):
            for field in ("host_id", "pid", "process_start"):
                with self.subTest(field=field):
                    case = self._case()
                    pool.release(case.child, reason="original_business_finished")
                    self._terminal(case)
                    resource_before = self._operation_resource(case)
                    proxy_before = self._proxy_snapshot()
                    business_before = self._business_snapshot(case)
                    with (
                        self._mismatched_permit_owner(case, field),
                        self._owner_state("exited"), self._passive_only(),
                    ):
                        self.assertEqual("reconciliation_required", self._run_resource(case)["state"])
                        self.assertEqual(resource_before, self._operation_resource(case))
                        self._assert_blocked(case)
                        self.assertEqual(proxy_before, self._proxy_snapshot())
                        self.assertEqual(business_before, self._business_snapshot(case))

        def test_orphan_permit_owner_must_match_persisted_ticket_before_resource_cas(self):
            for field in ("host_id", "pid", "process_start"):
                with self.subTest(field=field):
                    case = self._case()
                    pool.release(case.child, reason="original_business_finished")
                    self._orphan_disposition(case)
                    resource_before = self._operation_resource(case)
                    proxy_before = self._proxy_snapshot()
                    business_before = self._business_snapshot(case)
                    with (
                        self._mismatched_permit_owner(case, field),
                        self._owner_state("exited"), self._passive_only(),
                    ):
                        try:
                            confirmation = settlements.confirm_disposition_resources(
                                case.origin, domain=self.domain,
                            )
                        except OperationSettlementFenced:
                            confirmation = None
                        self.assertIsNone(confirmation)
                        self.assertIsNone(settlements.read_receipt(
                            seal_intent(kind="terminal", origin=case.origin, payload={"status": "success"}),
                            domain=self.domain,
                        ))
                        self.assertEqual(resource_before, self._operation_resource(case))
                        self._assert_blocked(case)
                        self.assertEqual(proxy_before, self._proxy_snapshot())
                        self.assertEqual(business_before, self._business_snapshot(case))

        def test_live_superseded_kind_cannot_authorize_new_proxy_resource_cas(self):
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            original = self._orphan_disposition(case)
            resource_before = self._operation_resource(case)
            proxy_before = self._proxy_snapshot()
            # Change only the independent disposition kind.  The complete
            # legally produced result and its integrity digest remain intact;
            # no callback handoff or actor-stop proof is invented here.
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(
                    f"""UPDATE {common._table('operation_settlement_dispositions')}
                    SET disposition_kind='live_superseded' WHERE id=%s""",
                    (original["id"],),
                )
            try:
                injected = settlements.read_disposition(case.origin, domain=self.domain)
                self.assertEqual("live_superseded", injected["disposition_kind"])
                self.assertEqual(original["result"], injected["result"])
                self.assertEqual(original["result_digest"], injected["result_digest"])
                business_before = self._business_snapshot(case)
                with self._owner_state("exited"), self._passive_only():
                    try:
                        confirmation = settlements.confirm_disposition_resources(
                            case.origin, domain=self.domain,
                        )
                    except OperationSettlementFenced:
                        confirmation = None
                    self.assertIsNone(confirmation)
                    self.assertEqual(resource_before, self._operation_resource(case))
                    self._assert_blocked(case)
                    self.assertEqual(proxy_before, self._proxy_snapshot())
                    self.assertEqual(business_before, self._business_snapshot(case))
            finally:
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"""UPDATE {common._table('operation_settlement_dispositions')}
                        SET disposition_kind='orphan_recovery' WHERE id=%s""",
                        (original["id"],),
                    )

        def test_resource_commit_ack_loss_retries_readback_without_rewriting_result_or_release(self):
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case)
            proxy_before = self._proxy_snapshot()
            business_before = self._business_snapshot(case)
            fault = TransactionFault(
                common._connect,
                lambda query, params: query.startswith("UPDATE") and '"operation_resources"' in query,
                ack_losses=1,
            )
            with self._owner_state("exited"), self._passive_only():
                with patch.object(common, "_connect", side_effect=fault.connect):
                    first = self._run_resource(case)
                self.assertEqual("pending", first["state"])
                self.assertEqual(1, fault.events.count("committed_ack_lost"))
                committed = self._operation_resource(case)
                self.assertEqual("released", committed["state"])
                self.assertIsNone(self._permit(case)["released_at"])
                self.assertEqual("done", self._run_resource(case)["state"])
                self.assertEqual(committed, self._operation_resource(case))
                self.assertEqual(business_before, self._business_snapshot(case))
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self._close_receipt(case)

        def test_resource_sql_rollback_keeps_original_pending_until_public_retry(self):
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case)
            resource_before = self._operation_resource(case)
            proxy_before = self._proxy_snapshot()
            business_before = self._business_snapshot(case)
            fault = TransactionFault(
                common._connect,
                lambda query, params: query.startswith("UPDATE") and '"operation_resources"' in query,
                rollbacks=1,
            )
            with self._owner_state("exited"), self._passive_only():
                with patch.object(common, "_connect", side_effect=fault.connect):
                    first = self._run_resource(case)
                self.assertEqual("pending", first["state"])
                self.assertEqual("settlement_storage_unavailable", first["error_code"])
                self.assertFalse(first["blocked"])
                failed_job = self._resource_job(case)
                with postgres.connect() as conn, conn.cursor() as cur:
                    cur.execute(
                        f"SELECT EXTRACT(EPOCH FROM (next_attempt_at-now())) "
                        f"FROM {common._table('operation_settlement_cleanup')} WHERE id=%s",
                        (failed_job["id"],),
                    )
                    self.assertLessEqual(float(cur.fetchone()[0]), 5.0)
                self.assertGreater(first["retry_after_seconds"], 0)
                self.assertEqual(["40001"], fault.sqlstates)
                self.assertEqual(1, fault.events.count("sql_rollback"))
                self.assertNotIn("committed_ack_lost", fault.events)
                self.assertEqual(resource_before, self._operation_resource(case))
                job = self._resource_job(case)
                self.assertEqual("pending", job["state"])
                self.assertIsNone(job["completed_at"])
                self._assert_blocked(case)
                self.assertEqual(business_before, self._business_snapshot(case))
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self.assertEqual("done", self._run_resource(case)["state"])
                self.assertEqual("released", self._operation_resource(case)["state"])
                self.assertEqual(business_before, self._business_snapshot(case))
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self._close_receipt(case)

        def test_real_role_denied_resource_update_preserves_original_then_recovers(self):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user")
                if not cur.fetchone()[0]:
                    self.skipTest("exclusive disposable PostgreSQL CREATEROLE required")
            role = "proxy_expiry_denied_" + uuid.uuid4().hex[:12]
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT UPDATE ON {}.operation_settlement_cleanup TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                for table_name in (
                    "operation_execution_permits", "operation_runs", "operation_tasks",
                ):
                    cur.execute(sql.SQL("GRANT UPDATE ON {}.{} TO {}").format(
                        sql.Identifier(self.schema), sql.Identifier(table_name), sql.Identifier(role)))
                # A row lock requires UPDATE privilege on at least one column.
                # Grant an unrelated column so the genuine state/detail CAS,
                # rather than an earlier ownership lock, raises SQLSTATE 42501.
                cur.execute(sql.SQL("GRANT UPDATE(provider) ON {}.operation_resources TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                cur.execute(sql.SQL("GRANT UPDATE(provider) ON {}.proxy_leases TO {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
            self.addCleanup(self._drop_role, role)
            case = self._case()
            pool.release(case.child, reason="original_business_finished")
            self._terminal(case)
            resource_before = self._operation_resource(case)
            proxy_before = self._proxy_snapshot()
            business_before = self._business_snapshot(case)
            original = common._connect
            sqlstates = []

            @contextmanager
            def denied():
                try:
                    with original() as conn:
                        with conn.cursor() as cur:
                            cur.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                        yield conn
                except psycopg.Error as exc:
                    sqlstates.append(exc.sqlstate)
                    raise

            with self._owner_state("exited"), self._passive_only():
                with patch.object(common, "_connect", side_effect=denied):
                    result = self._run_resource(case)
                self.assertEqual("reconciliation_required", result["state"])
                self.assertIn("42501", sqlstates)
                self.assertEqual("settlement_storage_permission_denied", result["error_code"])
                self.assertTrue(result["blocked"])
                self.assertEqual(resource_before, self._operation_resource(case))
                self._assert_blocked(case)
                blocked_job = self._resource_job(case)
                self.assertEqual("reconciliation_required", blocked_job["state"])
                self.assertIsNone(blocked_job["completed_at"])
                for field in ("receipt_id", "run_uuid", "execution_id", "permit_id",
                              "action_kind", "resource_identity"):
                    with self.subTest(field=field), self.assertRaises(OperationSettlementFenced):
                        settlements.retry_cleanup(
                            domain=self.domain, identity={**result["identity"], field: "foreign"})
                for _ in range(3):
                    outcome = settlements.run_cleanup_once(
                        domain=self.domain, permit_id=case.origin["permit_id"],
                        execution_id=case.origin["execution_id"],
                    )
                    # A different due tail may progress in the top-level
                    # result. The original blocked resource remains diagnosed
                    # under its exact ID, without starving that other action.
                    candidates = [outcome, *(outcome.get("diagnostics") or [])]
                    matching = [row for row in candidates
                                if row.get("cleanup_id") == blocked_job["id"]]
                    self.assertEqual(1, len(matching))
                    blocked = matching[0]
                    self.assertTrue(blocked["blocked"])
                    self.assertEqual("reconciliation_required", blocked["state"])
                    self.assertEqual(result["identity"], blocked["identity"])
                    self.assertEqual("settlement_storage_permission_denied", blocked["error_code"])
                    self.assertEqual(resource_before, self._operation_resource(case))
                    self._assert_blocked(case)
                self.assertEqual(blocked_job["attempts"], self._resource_job(case)["attempts"])
                # A fresh consumer has no process-local registry evidence, but
                # reads the original persisted blocker without executing it.
                with ExitStack() as state:
                    for name, value in (
                        ("_REGISTRY", {}), ("_EXPECTED", set()), ("_REGISTRY_ERROR", ""),
                        ("_CARRIER_ERROR", ""), ("_DOMAINS", {self.domain.domain_id: self.domain}),
                        ("_SCAN_BLOCKED", {}), ("_SCAN_DIAGNOSTICS", {}),
                        ("_SCAN_NEXT", {}), ("_SCAN_FAILURES", {}), ("_SCAN_ERROR", ""),
                        ("_SCAN_INFLIGHT", 0), ("_STOP", False), ("_STOP_WITH_PENDING", False),
                        ("_DEADLINE", None), ("_STARTED", True), ("_ADMISSION", None),
                        ("_THREAD", SimpleNamespace(is_alive=lambda: True)),
                    ):
                        state.enter_context(patch.object(settlement, name, value))
                    settlement._scan_domains()
                    self.assertFalse(settlement.runtime_status()["healthy"])
                    self.assertEqual(1, settlement.active_counts()["unverified_scan_pending"])
                self.assertEqual(blocked_job["attempts"], self._resource_job(case)["attempts"])
                settlements.retry_cleanup(domain=self.domain, identity=result["identity"])
                self.assertEqual("done", settlements.run_cleanup_once(
                    domain=self.domain, permit_id=case.origin["permit_id"],
                    execution_id=case.origin["execution_id"],
                )["state"])
                self.assertEqual(business_before, self._business_snapshot(case))
                self.assertEqual(proxy_before, self._proxy_snapshot())
                self._close_receipt(case)

        def _drop_role(self, role):
            with postgres.connect() as conn, conn.cursor() as cur:
                cur.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                cur.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                    sql.Identifier(self.schema), sql.Identifier(role)))
                cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
