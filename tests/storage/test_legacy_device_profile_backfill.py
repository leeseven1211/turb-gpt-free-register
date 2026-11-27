# -*- coding: utf-8 -*-
"""历史同源设备资料补缺，只使用独立 PostgreSQL 测试 schema。"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.types.json import Jsonb

from core.storage import postgres as pg, records
from core.storage.accounts import device_profiles
from tests.support_pg import PostgresTestCase

try:
    from tools.migrations import backfill_legacy_device_profiles as tool
except ImportError:
    tool = None


class LegacyDeviceProfileBackfillTests(PostgresTestCase):
    def setUp(self):
        self.key = Fernet.generate_key().decode()
        env = patch.dict(os.environ, {"TURB_CONFIG_ENCRYPTION_KEY": self.key})
        env.start()
        self.addCleanup(env.stop)
        cache = patch.object(device_profiles, "_READY_KEY", "")
        cache.start()
        self.addCleanup(cache.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.email = "legacy-device@example.test"
        self.when = "2026-11-20T10:00:00+00:00"
        self.profile = {
            "screen_width": 1440, "screen_height": 900, "device_pixel_ratio": 2,
            "hardware_concurrency": 8, "device_memory": 8, "js_heap_size_limit": 4294967296,
            "impersonate": "chrome149", "screen": "1440x900", "lang": "en-US",
            "sec_ch_ua_arch": "", "ua_arch": "x86", "tls_fp": "fixture-tls",
            "akamai_fp": "fixture-akamai", "viewport": {"width": 1440, "height": 900},
            "timezone_iana": "America/Los_Angeles", "timezone_offset_minutes": 480,
            "inner_width": 1400, "inner_height": 800, "has_touch": False, "max_touch_points": 0,
            "react_listening_key": "private-react", "geo": {"country": "US"},
            "cookies": [{"name": "private-cookie", "value": "private-cookie-value"}],
            "access_token": "private-token", "proxy_url": "private-proxy",
            "build_id": "request-build", "script_src_samples": ["https://private.test/secret"],
        }
        self.account_id = records.insert_row(records.ACCOUNTS, {
            "email": self.email, "created_at": self.when, "updated_at": self.when,
            "extra_json": json.dumps({
                "device_id": "legacy-device", "browser_profile": self.profile,
                "registration_driver": "protocol_oss_2",
            }),
        })
        device_profiles.init()
        self.manifest = self.root / "manifest.json"
        self.receipt = self.root / "dry-run.json"

    def config(self, instance="fixture-local"):
        self.assertIsNotNone(tool, "历史画像迁移工具尚未实现")
        return tool.Config(pg.database_url(), self.schema, self.key, instance)

    def plan(self):
        config = self.config()
        return tool.run(config, self.manifest, self.receipt)

    def apply(self, name="apply"):
        config = self.config()
        return tool.run(config, self.manifest, self.root / f"{name}.json", apply=True)

    def raw_account(self, account_id=None):
        with pg.connect() as conn:
            return conn.execute(sql.SQL("SELECT email,updated_at,data FROM {} WHERE id=%s").format(
                sql.Identifier(self.schema, "registered_accounts")),
                (account_id or self.account_id,),
            ).fetchone()

    def change_data(self, **changes):
        row = self.raw_account()
        data = dict(row[2])
        data.update(changes)
        with pg.connect() as conn:
            conn.execute(sql.SQL("UPDATE {} SET data=%s WHERE id=%s").format(
                sql.Identifier(self.schema, "registered_accounts")), (Jsonb(data), self.account_id))

    def device_rows(self):
        with pg.connect() as conn:
            return conn.execute(sql.SQL("SELECT * FROM {} ORDER BY account_id").format(
                sql.Identifier(self.schema, "account_device_profiles"))).fetchall()

    def saved(self):
        rows = self.device_rows()
        if not rows:
            return None
        return json.loads(Fernet(self.key.encode()).decrypt(rows[0][2].encode()).decode())

    def test_dry_run_leaves_sources_and_devices_unchanged_with_private_manifest(self):
        before = self.raw_account()
        result = self.plan()
        self.assertEqual(1, result["candidate_count"])
        self.assertEqual([], self.device_rows())
        self.assertEqual(before, self.raw_account())
        for path in (self.manifest, self.receipt):
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            for private in (self.email, "legacy-device", "fixture-tls", "private-token", "private-react"):
                self.assertNotIn(private, path.read_text())

    def test_apply_keeps_stable_and_upstream_values_but_removes_session_material(self):
        before = self.raw_account()
        self.plan()
        self.assertEqual({"inserted": 1}, self.apply()["results"])
        saved = self.saved()
        self.assertEqual(self.account_id, saved["account_id"])
        self.assertEqual(self.email, saved["email"])
        self.assertEqual("legacy-device", saved["payload"]["device_id"])
        expected = {key: value for key, value in self.profile.items() if key not in {
            "react_listening_key", "geo", "cookies", "access_token", "proxy_url", "build_id",
            "script_src_samples",
        }}
        self.assertEqual(expected, saved["payload"]["browser_profile"])
        self.assertEqual("", saved["payload"]["browser_profile"]["sec_ch_ua_arch"])
        self.assertEqual("x86", saved["payload"]["browser_profile"]["ua_arch"])
        self.assertEqual("legacy_extra_json", self.device_rows()[0][3])
        self.assertEqual(before, self.raw_account())

    def test_top_level_pair_is_available_when_extra_has_no_pair(self):
        self.change_data(extra_json="{}", device_id="top-device", browser_profile=self.profile)
        self.plan()
        self.apply()
        self.assertEqual("top-device", self.saved()["payload"]["device_id"])
        self.assertEqual("legacy_account_data", self.device_rows()[0][3])

    def test_equal_pairs_prefer_extra_without_duplicate_candidates(self):
        self.change_data(device_id="legacy-device", browser_profile=self.profile)
        self.assertEqual(1, self.plan()["candidate_count"])
        self.apply()
        self.assertEqual("legacy_extra_json", self.device_rows()[0][3])

    def test_conflicting_devices_or_profiles_are_skipped_without_choosing_one(self):
        for changes in (
            {"device_id": "other-device", "browser_profile": self.profile},
            {"device_id": "legacy-device", "browser_profile": {**self.profile, "screen_width": 1920}},
        ):
            self.change_data(**changes)
            path = self.root / f"manifest-{len(list(self.root.iterdir()))}.json"
            result = tool.run(self.config(), path, path.with_suffix(".receipt"))
            self.assertEqual(0, result["candidate_count"])
            self.assertEqual({"source_conflict": 1}, result["skipped"])
        self.assertEqual([], self.device_rows())

    def test_incomplete_sources_are_never_cross_combined(self):
        self.change_data(extra_json=json.dumps({"device_id": "legacy-device"}),
                         browser_profile=self.profile, device_id=None)
        result = self.plan()
        self.assertEqual(0, result["candidate_count"])
        self.assertEqual({"incomplete_source_pair": 1}, result["skipped"])

    def test_unpaired_secondary_device_hint_does_not_block_complete_extra_source(self):
        self.change_data(device_id="later-device-without-profile")
        self.assertEqual(1, self.plan()["candidate_count"])
        self.apply()
        self.assertEqual("legacy-device", self.saved()["payload"]["device_id"])

    def test_unpaired_extra_profile_does_not_block_complete_top_source(self):
        self.change_data(extra_json={"browser_profile": {"screen_width": 1920}},
                         device_id="top-device", browser_profile=self.profile)
        self.assertEqual(1, self.plan()["candidate_count"])
        self.apply()
        self.assertEqual("top-device", self.saved()["payload"]["device_id"])

    def test_nested_tls_order_empty_headers_and_false_values_are_preserved(self):
        profile = {**self.profile, "tls_fp": {
            "tls_permute_extensions": False, "tls_grease": None,
            "tls_signature_algorithms": ["rsa_pss_rsae_sha256", "ecdsa_secp256r1_sha256"],
            "http2_stream_weight": 0, "cookie": "private-nested-cookie",
        }, "viewport": {"width": 1440, "height": 900, "token": "private-nested-token"}}
        self.change_data(extra_json={"device_id": "legacy-device", "browser_profile": profile})
        self.plan()
        self.apply()
        actual = self.saved()["payload"]["browser_profile"]
        self.assertEqual({
            "tls_permute_extensions": False, "tls_grease": None,
            "tls_signature_algorithms": ["rsa_pss_rsae_sha256", "ecdsa_secp256r1_sha256"],
            "http2_stream_weight": 0,
        }, actual["tls_fp"])
        self.assertEqual({"width": 1440, "height": 900}, actual["viewport"])
        self.assertIs(actual["has_touch"], False)
        self.assertEqual(0, actual["max_touch_points"])
        self.assertEqual("", actual["sec_ch_ua_arch"])
        self.assertEqual("x86", actual["ua_arch"])

    def test_device_id_must_be_a_nonempty_string(self):
        for index, bad in enumerate((None, "", "  ", 123, False, {"value": "device"})):
            self.change_data(extra_json={"device_id": bad, "browser_profile": self.profile})
            result = tool.run(self.config(), self.root / f"device-{index}.json", self.root / f"device-{index}-receipt.json")
            self.assertEqual(0, result["candidate_count"])
            self.assertEqual({"incomplete_source_pair": 1}, result["skipped"])

    def test_unknown_driver_is_kept_but_any_explicit_rust_evidence_is_excluded(self):
        self.change_data(extra_json={"device_id": "legacy-device", "browser_profile": self.profile})
        self.assertEqual(1, self.plan()["candidate_count"])
        self.change_data(registration_driver="sentinel_rs")
        result = tool.run(self.config(), self.root / "rust.json", self.root / "rust-receipt.json")
        self.assertEqual(0, result["candidate_count"])
        self.assertEqual({"rust_registration_placeholder": 1}, result["skipped"])

    def test_nonpositive_nonfinite_and_boolean_required_values_are_classified(self):
        for index, bad in enumerate((0, -1, True, None, "1440", float("inf"), float("nan"), 10**400)):
            profile = {**self.profile, "screen_width": bad}
            self.change_data(extra_json=json.dumps({"device_id": "legacy-device", "browser_profile": profile}))
            result = tool.run(self.config(), self.root / f"bad-{index}.json", self.root / f"bad-{index}-receipt.json")
            self.assertEqual(0, result["candidate_count"])
            self.assertEqual({"profile_numeric_invalid": 1}, result["skipped"])

    def test_existing_partial_row_and_concurrent_insert_are_preserved(self):
        self.plan()
        device_profiles.save_profile(self.account_id, self.email, {"device_id": "newer-device"})
        before = self.device_rows()
        self.assertEqual({"existing_device": 1}, self.apply()["results"])
        self.assertEqual(before, self.device_rows())
        result = tool.run(self.config(), self.root / "fresh.json", self.root / "fresh-receipt.json")
        self.assertEqual({"existing_device": 1}, result["skipped"])

    def test_email_source_and_both_updated_markers_are_guarded(self):
        mutations = (
            ("email", "changed@example.test"),
            ("column_updated", "2026-11-21T10:00:00+00:00"),
            ("data_updated", "2026-11-22T10:00:00+00:00"),
            ("source", "different-device"),
        )
        for index, (kind, value) in enumerate(mutations):
            original = self.raw_account()
            manifest = self.root / f"guard-{index}.json"
            tool.run(self.config(), manifest, self.root / f"guard-{index}-dry.json")
            if kind == "email":
                with pg.connect() as conn:
                    conn.execute(sql.SQL("UPDATE {} SET email=%s WHERE id=%s").format(
                        sql.Identifier(self.schema, "registered_accounts")), (value, self.account_id))
            elif kind == "column_updated":
                with pg.connect() as conn:
                    conn.execute(sql.SQL("UPDATE {} SET updated_at=%s WHERE id=%s").format(
                        sql.Identifier(self.schema, "registered_accounts")), (value, self.account_id))
            elif kind == "data_updated":
                self.change_data(updated_at=value)
            else:
                self.change_data(extra_json={"device_id": value, "browser_profile": self.profile})
            result = tool.run(self.config(), manifest, self.root / f"guard-{index}-apply.json", apply=True)
            self.assertEqual({"account_changed" if kind == "email" else "source_changed": 1}, result["results"])
            self.assertEqual([], self.device_rows())
            with pg.connect() as conn:
                conn.execute(sql.SQL("UPDATE {} SET email=%s,updated_at=%s,data=%s WHERE id=%s").format(
                    sql.Identifier(self.schema, "registered_accounts")),
                    (original[0], original[1], Jsonb(original[2]), self.account_id))

    def test_fixed_manifest_reapply_is_idempotent_and_rejects_session_manifest(self):
        self.plan()
        self.apply()
        before = self.device_rows()
        self.assertEqual({"existing_device": 1}, self.apply("again")["results"])
        self.assertEqual(before, self.device_rows())
        manifest = json.loads(self.manifest.read_text())
        manifest["source"] = "account_protocol_sessions"
        body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        manifest["manifest_sha256"] = tool.shared._digest(body)
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(tool.shared.BackfillError, "manifest_invalid"):
            self.apply("wrong")

    def test_cross_instance_and_tampered_manifest_fail_without_writing(self):
        self.plan()
        with self.assertRaisesRegex(tool.BackfillError, "manifest_scope_mismatch"):
            tool.run(self.config("fixture-oracle"), self.manifest, self.root / "cross-instance.json", apply=True)
        manifest = json.loads(self.manifest.read_text())
        manifest["candidates"][0]["account_id"] += 1
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(tool.BackfillError, "manifest_digest_mismatch"):
            self.apply("tampered")
        self.assertEqual([], self.device_rows())

    def test_source_only_migration_has_no_session_table_dependency(self):
        with pg.connect() as conn:
            exists = conn.execute("SELECT to_regclass(%s)", (
                f"{self.schema}.account_protocol_sessions",)).fetchone()[0]
        self.assertIsNone(exists)
        self.plan()
        self.apply()
        with pg.connect() as conn:
            exists = conn.execute("SELECT to_regclass(%s)", (
                f"{self.schema}.account_protocol_sessions",)).fetchone()[0]
        self.assertIsNone(exists)
        self.assertEqual(1, len(self.device_rows()))

    def test_failure_rolls_back_the_batch_without_changing_legacy_sources(self):
        second_id = records.insert_row(records.ACCOUNTS, {
            "email": "second@example.test", "updated_at": self.when,
            "extra_json": json.dumps({"device_id": "second-device", "browser_profile": self.profile}),
        })
        original = self.raw_account()
        self.plan()
        with pg.connect() as conn:
            conn.execute(sql.SQL("""
                CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $body$
                BEGIN
                    IF NEW.account_id = {} THEN RAISE EXCEPTION 'fixture_write_failure'; END IF;
                    RETURN NEW;
                END $body$
            """).format(sql.Identifier(self.schema, "reject_second_legacy"), sql.Literal(second_id)))
            conn.execute(sql.SQL("""
                CREATE TRIGGER reject_second_legacy BEFORE INSERT ON {}
                FOR EACH ROW EXECUTE FUNCTION {}()
            """).format(sql.Identifier(self.schema, "account_device_profiles"),
                        sql.Identifier(self.schema, "reject_second_legacy")))
        with self.assertRaisesRegex(tool.BackfillError, "database_apply_failed"):
            self.apply()
        self.assertEqual([], self.device_rows())
        self.assertEqual(original, self.raw_account())
        receipt = json.loads((self.root / "apply.json").read_text())
        self.assertFalse(receipt["completed"])
        self.assertEqual({}, receipt["results"])

    def test_naive_source_time_uses_manifest_observation_without_guessing_timezone(self):
        naive = "2026-11-20T10:00:00"
        with pg.connect() as conn:
            conn.execute(sql.SQL("UPDATE {} SET updated_at=%s WHERE id=%s").format(
                sql.Identifier(self.schema, "registered_accounts")), (naive, self.account_id))
        self.plan()
        manifest = json.loads(self.manifest.read_text())
        self.apply()
        envelope = self.saved()
        self.assertEqual(manifest["created_at"], envelope["updated_at"])
        self.assertEqual({
            "source_kind": "legacy_extra_json", "time_basis": "migration_observed",
            "source_row_updated_raw": naive, "observed_at": manifest["created_at"],
        }, envelope["provenance"])

    def test_offset_source_time_is_recorded_as_row_update_without_claiming_usage_time(self):
        self.plan()
        self.apply()
        envelope = self.saved()
        self.assertEqual(self.when, envelope["updated_at"])
        self.assertEqual("source_row_updated", envelope["provenance"]["time_basis"])

    def test_migrated_profile_is_selected_and_consumed_by_real_session_without_network(self):
        from core.accounts.password_setup.reset import _select_reset_identity
        from core.auth.protocol.session import BrowserSession

        self.change_data(extra_json={"device_id": "legacy-device", "browser_profile": {
            **self.profile, "device_os": "Windows", "browser_os": "Windows",
            "webgl_vendor": "fixture-vendor", "webgl_renderer": "fixture-renderer",
        }})
        self.plan()
        self.apply()
        saved = device_profiles.load_profile(self.account_id, self.email)
        identity = _select_reset_identity(saved, {})
        self.assertEqual("legacy-device", identity["device_id"])
        original_saved = json.loads(json.dumps(saved))
        original_identity = json.loads(json.dumps(identity))
        with patch("curl_cffi.requests.Session.request",
                   side_effect=AssertionError("隔离构造不得发起网络请求")):
            session = BrowserSession(proxy="", detect_exit_geo=False, identity=identity)
            try:
                self.assertEqual("legacy-device", session.device_id)
                for field, expected in (
                    ("screen_width", 1440), ("screen_height", 900),
                    ("device_pixel_ratio", 2), ("hardware_concurrency", 8),
                    ("device_memory", 8), ("js_heap_size_limit", 4294967296),
                    ("webgl_vendor", "fixture-vendor"), ("webgl_renderer", "fixture-renderer"),
                ):
                    self.assertEqual(expected, session.browser_profile[field])
                self.assertEqual(original_saved, saved)
                self.assertEqual(original_identity, identity)
            finally:
                session.close()
