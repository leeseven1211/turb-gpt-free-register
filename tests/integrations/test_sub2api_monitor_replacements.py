"""巡检内存决策在补传前使用已确认的替代目标。"""
from __future__ import annotations

from unittest.mock import patch

from core.integrations.sub2api import monitor, monitor_collections
from core.storage import postgres, records, sub2api, sub2api_monitor
from core.storage.operations import store as operations
from tests.support_pg import PostgresTestCase


class Sub2ApiMonitorReplacementTests(PostgresTestCase):
    def setUp(self):
        records.init()
        operations.reset_ready()
        operations.init()
        sub2api.init()
        self.backend = "monitor-replacement-backend"
        self.email = "replacement@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {"email": self.email})
        self.filename = "replacement.json"
        content = {"email": self.email, "account_id": "provider-identity",
                   "access_token": "isolated-access", "refresh_token": "isolated-refresh"}
        self.credential_id = records.insert_row(records.CODEX_CREDENTIALS, {
            "filename": self.filename, "email": self.email, "content": content})
        self.generation = sub2api.credential_generation(content)

    def mapping_only_state(self, *, targets=(41,), mapping=None):
        sub2api.save_repair(
            self.backend, self.account_id, stage="sync_wait",
            remote_account_ids=list(targets), source_generation=self.generation)
        sub2api.save_repair(
            self.backend, self.account_id, superseded_targets=mapping or {"41": 42})
        # mapping-only 更新仍可保留旧 raw IDs，后续决策必须在内存先归一化。
        state = sub2api.get_repair(self.backend, self.account_id)
        self.assertEqual(state["remote_account_ids"], list(targets))
        return state

    def job(self, target, status, *, generation=None):
        row = sub2api.queue(
            self.filename, backend=self.backend, generation=generation or self.generation,
            account_id=self.account_id, email=self.email, credential_id=self.credential_id,
            remote_account_ids=[target], trigger="sub2api_monitor")[0]
        with postgres.connect() as conn:
            conn.execute(f"""UPDATE {sub2api._table()} SET status=%s,stage=%s,
                dispatch_requested=FALSE WHERE id=%s""", (status, status, row["id"]))

    def scan(self):
        accounts = {self.account_id: records.get_row(records.ACCOUNTS, self.account_id)}
        facts = sub2api_monitor.snapshot(self.backend, [self.account_id])
        return monitor_collections.Scan(self.backend, accounts, facts)

    def process(self, scan):
        summary = {"group_ids": [], "sync_queued": 0, "reauth_queued": 0, "reasons": {}}
        token = monitor._SCAN.set(scan)
        try:
            with patch.object(monitor._cfg, "SUB2API_MONITOR_ENABLED", True):
                monitor._process(
                    self.backend, scan.accounts[self.account_id], scan.credentials, [], summary)
        finally:
            monitor._SCAN.reset(token)
        return scan.states[self.account_id]

    def test_successful_replacement_closes_continuation_instead_of_waiting_on_superseded_job(self):
        self.mapping_only_state()
        self.job(41, "superseded")
        self.job(42, "success")
        scan = self.scan()
        state = self.process(scan)
        self.assertEqual(state["stage"], "idle")
        self.assertEqual(state["remote_account_ids"], [42])
        self.assertEqual(state["superseded_targets"], {"41": 42})
        self.assertEqual(state["last_sync_generation"], self.generation)
        self.assertEqual(scan.sync, [])
        self.assertEqual(scan.oauth, [])

    def test_superseded_job_does_not_make_pending_replacement_complete(self):
        self.mapping_only_state()
        self.job(41, "superseded")
        self.job(42, "pending")
        scan = self.scan()
        state = self.process(scan)
        self.assertEqual(state["remote_account_ids"], [42])
        self.assertEqual(state["stage"], "sync_wait")
        self.assertNotIn("last_sync_generation", state)
        self.assertEqual(scan.sync, [])

    def test_new_credential_generation_queues_only_the_replacement_target(self):
        self.mapping_only_state()
        self.job(41, "superseded", generation="previous-generation")
        self.job(42, "success", generation="previous-generation")
        scan = self.scan()
        state = self.process(scan)
        self.assertEqual(state["remote_account_ids"], [42])
        self.assertEqual(state["stage"], "sync_wait")
        self.assertEqual(len(scan.sync), 1)
        self.assertEqual(scan.sync[0]["remote_account_ids"], [42])
        self.assertEqual(scan.sync[0]["generation"], self.generation)
        self.assertEqual(scan.sync[0]["credential_id"], self.credential_id)

    def test_save_merges_transitive_replacement_mapping_before_next_decision(self):
        self.mapping_only_state(targets=(41, 42, 50))
        scan = self.scan()
        state = scan.save(
            self.account_id, scan.states[self.account_id],
            superseded_targets={"42": 43}, remote_account_ids=[41, 42, 50])
        self.assertEqual(state["remote_account_ids"], [43, 50])
        self.assertEqual(state["superseded_targets"], {"41": 43, "42": 43})
        self.assertIs(scan.states[self.account_id], state)
        self.assertIs(scan.changed[self.account_id], state)
