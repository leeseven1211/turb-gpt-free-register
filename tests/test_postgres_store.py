# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import db, postgres_store


class PostgresPrimaryStoreTests(unittest.TestCase):
    def test_read_prefers_postgres_payload_over_compatibility_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "accounts.json"
            path.write_text(json.dumps([{"id": 1, "email": "file@example.test"}]), encoding="utf-8")
            expected = [{"id": 2, "email": "postgres@example.test"}]
            with patch.object(postgres_store, "enabled", return_value=True), patch.object(
                postgres_store, "load_collection", return_value=(True, expected)
            ) as load:
                self.assertEqual(db._read_json(path, []), expected)
            load.assert_called_once_with("accounts.json")

    def test_write_commits_postgres_and_refreshes_compatibility_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "jobs.json"
            payload = [{"id": 7, "status": "success"}]
            with patch.object(postgres_store, "enabled", return_value=True), patch.object(
                postgres_store, "save_collection"
            ) as save:
                db._write_json(path, payload)
            save.assert_called_once_with("jobs.json", payload)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)


if __name__ == "__main__":
    unittest.main()
