# -*- coding: utf-8 -*-
"""设备画像运维补缺：只测试隔离 PostgreSQL schema，不连接生产库。"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from psycopg import sql

from core.storage import postgres as pg, records
from core.storage.accounts import device_profiles, protocol_sessions
from tests.support_pg import PostgresTestCase
from tools.migrations import backfill_account_device_profiles as tool


class DeviceProfileBackfillTests(PostgresTestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode()
        env = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": self.key})
        env.start()
        self.addCleanup(env.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = self.root / "manifest.json"
        self.receipt = self.root / "receipt.json"
        self.email = "device-backfill@example.test"
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "created_at": "2026-11-20T10:00:00",
            "updated_at": "2026-11-20T10:00:00",
        })
        self.profile = {
            "screen_width": 1440, "screen_height": 900, "device_pixel_ratio": 2,
            "hardware_concurrency": 8, "device_memory": 8,
            "js_heap_size_limit": 4294967296, "impersonate": "chrome149",
        }
        self.when = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
        for module in (protocol_sessions, device_profiles):
            cache = patch.object(module, "_READY_KEY", "")
            cache.start()
            self.addCleanup(cache.stop)
        protocol_sessions.init()
        device_profiles.init()
        self.config = tool.Config(pg.database_url(), self.schema, self.key, "fixture-local")

    def save_session(self, payload=None, **kwargs):
        protocol_sessions.save_session(
            self.account_id, self.email,
            payload or {"device_id": "original-device", "browser_profile": self.profile,
                        "cookies": [{"name": "private-cookie", "value": "private-value"}]},
            now=self.when, **kwargs,
        )
        with pg.connect() as conn:
            conn.execute(
                sql.SQL("UPDATE {} SET updated_at=%s WHERE account_id=%s").format(
                    sql.Identifier(self.schema, "account_protocol_sessions")),
                (self.when, self.account_id),
            )

    def plan(self):
        return tool.run(self.config, self.manifest, self.receipt, apply=False)

    def apply(self, suffix="apply"):
        return tool.run(self.config, self.manifest, self.root / f"{suffix}.json", apply=True)

    def device_rows(self):
        with pg.connect() as conn:
            return conn.execute(sql.SQL("SELECT * FROM {} ORDER BY account_id").format(
                sql.Identifier(self.schema, "account_device_profiles"))).fetchall()

    def test_dry_run_is_private_and_never_initializes_or_writes_business_tables(self):
        self.save_session()
        with patch.object(device_profiles, "init", side_effect=AssertionError("禁止业务初始化")), \
                patch.object(protocol_sessions, "init", side_effect=AssertionError("禁止业务初始化")):
            result = self.plan()
        self.assertEqual(1, result["candidate_count"])
        self.assertEqual([], self.device_rows())
        content = self.manifest.read_text() + self.receipt.read_text()
        for private in (self.email, "original-device", "private-cookie", "private-value", "chrome149"):
            self.assertNotIn(private, content)
        self.assertEqual(0o600, stat.S_IMODE(self.manifest.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(self.receipt.stat().st_mode))

    def test_expired_session_fills_only_device_fields_and_preserves_source_time(self):
        self.save_session()
        with pg.connect() as conn:
            original = conn.execute(sql.SQL("SELECT encrypted_payload,expires_at,updated_at FROM {}").format(
                sql.Identifier(self.schema, "account_protocol_sessions"))).fetchone()
        self.plan()
        result = self.apply()
        self.assertEqual({"inserted": 1}, result["results"])
        saved = device_profiles.load_profile(self.account_id, self.email)
        self.assertEqual("original-device", saved["device_id"])
        self.assertEqual(self.profile, saved["browser_profile"])
        self.assertEqual("chrome149", saved["impersonate"])
        self.assertNotIn("cookies", saved)
        self.assertNotIn("expires_at", saved)
        with pg.connect() as conn:
            now = conn.execute(sql.SQL("SELECT encrypted_payload,expires_at,updated_at FROM {}").format(
                sql.Identifier(self.schema, "account_protocol_sessions"))).fetchone()
            last_used = conn.execute(sql.SQL("SELECT last_used_at FROM {}").format(
                sql.Identifier(self.schema, "account_device_profiles"))).fetchone()[0]
        self.assertEqual(original, now)
        self.assertEqual(self.when, last_used)
        self.assertIsNone(protocol_sessions.load_session(self.account_id, self.email))

    def test_reapplying_same_manifest_and_new_scan_are_idempotent(self):
        self.save_session()
        self.plan()
        self.apply()
        before = self.device_rows()
        second = self.apply("second")
        self.assertEqual({"existing_device": 1}, second["results"])
        self.assertEqual(before, self.device_rows())
        fresh = tool.run(self.config, self.root / "fresh.json", self.root / "fresh-receipt.json", apply=False)
        self.assertEqual(0, fresh["candidate_count"])

    def test_existing_even_partial_device_row_is_never_replaced(self):
        self.save_session()
        device_profiles.save_profile(self.account_id, self.email, {"device_id": "newer-device"})
        before = self.device_rows()
        self.assertEqual(0, self.plan()["candidate_count"])
        self.assertEqual(before, self.device_rows())

    def test_device_inserted_after_plan_is_preserved(self):
        self.save_session()
        self.plan()
        device_profiles.save_profile(self.account_id, self.email, {"device_id": "concurrent-device"})
        before = self.device_rows()
        self.assertEqual({"existing_device": 1}, self.apply()["results"])
        self.assertEqual(before, self.device_rows())

    def test_email_change_after_plan_skips_without_writing(self):
        self.save_session()
        self.plan()
        records.patch_row(records.ACCOUNTS, self.account_id, {"email": "changed@example.test"})
        self.assertEqual({"account_changed": 1}, self.apply()["results"])
        self.assertEqual([], self.device_rows())

    def test_session_updated_after_plan_skips_even_when_payload_is_unchanged(self):
        self.save_session()
        self.plan()
        with pg.connect() as conn:
            conn.execute(sql.SQL("UPDATE {} SET updated_at=updated_at+interval '1 second'").format(
                sql.Identifier(self.schema, "account_protocol_sessions")))
        self.assertEqual({"source_changed": 1}, self.apply()["results"])
        self.assertEqual([], self.device_rows())

    def test_ciphertext_changed_after_plan_skips_even_when_timestamp_is_unchanged(self):
        self.save_session()
        self.plan()
        self.save_session({"device_id": "replaced-device", "browser_profile": self.profile})
        self.assertEqual({"source_changed": 1}, self.apply()["results"])
        self.assertEqual([], self.device_rows())

    def test_incomplete_profile_or_invalid_envelope_is_classified(self):
        self.save_session({"device_id": "original-device", "browser_profile": {"screen_width": 1440}})
        self.assertEqual({"incomplete_profile": 1}, self.plan()["skipped"])
        self.manifest.unlink()
        self.receipt.unlink()
        cipher = Fernet(self.key.encode())
        invalid = cipher.encrypt(json.dumps({
            "version": 1, "account_id": self.account_id, "email": "wrong@example.test",
            "payload": {"device_id": "original-device", "browser_profile": self.profile},
        }).encode()).decode()
        with pg.connect() as conn:
            conn.execute(sql.SQL("UPDATE {} SET encrypted_payload=%s").format(
                sql.Identifier(self.schema, "account_protocol_sessions")), (invalid,))
        result = self.plan()
        self.assertEqual(0, result["candidate_count"])
        self.assertEqual({"envelope_binding_invalid": 1}, result["skipped"])

    def test_cross_instance_and_tampered_manifest_fail_before_writing(self):
        self.save_session()
        self.plan()
        other = tool.Config(pg.database_url(), self.schema, self.key, "fixture-oracle")
        with self.assertRaisesRegex(tool.BackfillError, "manifest_scope_mismatch"):
            tool.run(other, self.manifest, self.root / "other.json", apply=True)
        manifest = json.loads(self.manifest.read_text())
        manifest["candidates"][0]["account_id"] += 1
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(tool.BackfillError, "manifest_digest_mismatch"):
            self.apply()
        self.assertEqual([], self.device_rows())

    def test_missing_table_is_not_created(self):
        with pg.connect() as conn:
            conn.execute(sql.SQL("DROP TABLE {}").format(
                sql.Identifier(self.schema, "account_device_profiles")))
        with self.assertRaisesRegex(tool.BackfillError, "required_table_missing"):
            self.plan()
        with pg.connect() as conn:
            exists = conn.execute("SELECT to_regclass(%s)", (
                f"{self.schema}.account_device_profiles",)).fetchone()[0]
        self.assertIsNone(exists)

    def test_apply_failure_rolls_back_all_insertions_and_keeps_failure_receipt(self):
        self.save_session()
        second_id = records.insert_row(records.ACCOUNTS, {"email": "second@example.test"})
        protocol_sessions.save_session(
            second_id, "second@example.test",
            {"device_id": "second-device", "browser_profile": self.profile}, now=self.when,
        )
        self.plan()
        with pg.connect() as conn:
            conn.execute(sql.SQL("""
                CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $body$
                BEGIN
                    IF NEW.account_id = {} THEN RAISE EXCEPTION 'fixture_write_failure'; END IF;
                    RETURN NEW;
                END $body$
            """).format(sql.Identifier(self.schema, "reject_second_device"), sql.Literal(second_id)))
            conn.execute(sql.SQL("""
                CREATE TRIGGER reject_second BEFORE INSERT ON {}
                FOR EACH ROW EXECUTE FUNCTION {}()
            """).format(
                sql.Identifier(self.schema, "account_device_profiles"),
                sql.Identifier(self.schema, "reject_second_device"),
            ))
        with self.assertRaisesRegex(tool.BackfillError, "database_apply_failed"):
            self.apply()
        self.assertEqual([], self.device_rows())
        receipt = json.loads((self.root / "apply.json").read_text())
        self.assertFalse(receipt["completed"])
        self.assertEqual("database_apply_failed", receipt["error_code"])

    def test_private_manifest_cannot_be_overwritten_or_follow_a_symlink(self):
        self.save_session()
        self.manifest.write_text("existing private document")
        with self.assertRaisesRegex(tool.BackfillError, "private_output_exists"):
            self.plan()
        self.assertEqual("existing private document", self.manifest.read_text())
        self.manifest.unlink()
        target = self.root / "target.json"
        target.write_text("do not replace")
        self.manifest.symlink_to(target)
        with self.assertRaisesRegex(tool.BackfillError, "private_output_exists"):
            self.plan()
        self.assertEqual("do not replace", target.read_text())

    def test_direct_run_requires_explicit_production_instance_authorization(self):
        config = tool.Config("dbname=turb_console", self.schema, self.key, "fixture-production")
        with self.assertRaisesRegex(tool.BackfillError, "production_instance_not_authorized"):
            tool.run(config, self.manifest, self.receipt)
        self.assertFalse(self.manifest.exists())

    def test_service_resolved_production_database_is_guarded_after_readonly_connection(self):
        class ResolvedConnection:
            info = SimpleNamespace(dbname="turb_console")
            closed = False

            def close(self):
                self.closed = True

        for allowed, expected in (
            (False, "production_instance_not_authorized"),
            (True, "isolated_test_database_required"),
        ):
            connection = ResolvedConnection()
            config = tool.Config("service=fixture", self.schema, self.key, "fixture-production", allowed)
            with patch.object(tool.psycopg, "connect", return_value=connection):
                with self.assertRaisesRegex(tool.BackfillError, expected):
                    tool._connect(config, read_only=False)
            self.assertTrue(connection.closed)
