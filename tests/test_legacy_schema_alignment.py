from __future__ import annotations

import importlib
import os
import unittest


class LegacySchemaAlignmentTests(unittest.TestCase):
    def test_legacy_tasks_follow_turb_schema_when_account_schema_is_unset(self):
        from core.operations import legacy_task_store

        previous_turb_schema = os.environ.get("TURB_DB_SCHEMA")
        previous_account_schema = os.environ.get("ACCOUNT_TASK_DB_SCHEMA")
        try:
            os.environ["TURB_DB_SCHEMA"] = "test_webui_runtime"
            os.environ.pop("ACCOUNT_TASK_DB_SCHEMA", None)
            reloaded = importlib.reload(legacy_task_store)

            self.assertEqual("test_webui_runtime", reloaded._SCHEMA)
        finally:
            if previous_turb_schema is None:
                os.environ.pop("TURB_DB_SCHEMA", None)
            else:
                os.environ["TURB_DB_SCHEMA"] = previous_turb_schema
            if previous_account_schema is None:
                os.environ.pop("ACCOUNT_TASK_DB_SCHEMA", None)
            else:
                os.environ["ACCOUNT_TASK_DB_SCHEMA"] = previous_account_schema
            importlib.reload(legacy_task_store)


if __name__ == "__main__":
    unittest.main()
