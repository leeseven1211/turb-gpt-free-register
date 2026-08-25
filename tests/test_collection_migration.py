# -*- coding: utf-8 -*-
from core import postgres_store, record_store
from tests.support_pg import PostgresTestCase
from tools import migrate_collections_to_tables as migration


class CollectionMigrationTests(PostgresTestCase):
    def test_all_admin_sources_migrate_idempotently_and_verify(self):
        for index, (collection, spec, filename) in enumerate(migration.MIGRATIONS, start=1):
            row = {"id": index, "email": f"row{index}@example.test", "status": "available"}
            if spec is record_store.JOBS:
                row = {"id": index, "job_uuid": f"job-{index}", "status": "failed"}
            postgres_store.save_collection(collection, [row])
            rows, origin = migration.load_source(collection, filename)
            inserted, errors = migration.do_apply(collection, spec, rows, origin)
            self.assertEqual(inserted, 1)
            self.assertEqual(errors, [])
            inserted_again, errors = migration.do_apply(collection, spec, rows, origin)
            self.assertEqual(inserted_again, 0)
            self.assertEqual(errors, [])
            self.assertEqual(migration.do_verify(collection, spec, rows, origin), [])

        filename = "codex-migrated@example.test-free.json"
        postgres_store.save_collection("codex_credentials", {
            filename: {
                "content": {
                    "email": "migrated@example.test",
                    "account_id": "acct-migrated",
                    "access_token": "secret",
                    "refresh_token": "refresh",
                },
                "mtime": "2026-08-20T12:00:00",
            }
        })
        postgres_store.save_collection("codex_导出状态.json", {
            filename: {"exported_count": 3, "exported_at": "2026-08-21T12:00:00"}
        })
        rows, origin = migration.load_codex_source()
        inserted, errors = migration.do_apply(
            "codex_credentials", record_store.CODEX_CREDENTIALS, rows, origin
        )
        self.assertEqual((inserted, errors), (1, []))
        self.assertEqual(
            migration.do_verify(
                "codex_credentials", record_store.CODEX_CREDENTIALS, rows, origin
            ),
            [],
        )
        stored = record_store.get_row_by(
            record_store.CODEX_CREDENTIALS, "filename", filename
        )
        self.assertEqual(stored["exported_count"], 3)
        self.assertEqual(stored["content"]["access_token"], "secret")


if __name__ == "__main__":
    import unittest
    unittest.main()
