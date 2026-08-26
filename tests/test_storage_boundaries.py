"""存储模块边界和兼容别名契约。"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase

from core import db, operation_task_store
from core.storage import (
    accounts,
    codex,
    db_legacy,
    email_pool,
    jobs,
    operation,
    operation_projection,
    operation_runtime_store,
)
from core.operations import legacy_task_store, task_gateway


class StorageBoundaryTests(TestCase):
    def test_legacy_storage_modules_are_same_objects_as_new_implementations(self):
        self.assertIs(db, db_legacy)
        self.assertIs(operation_task_store, operation)
        from core import account_task_store

        self.assertIs(account_task_store, legacy_task_store)

    def test_domain_repositories_expose_declared_entrypoints(self):
        self.assertIn("get_account", accounts.__all__)
        self.assertIn("create_job", jobs.__all__)
        self.assertIn("claim_next_outlook", email_pool.__all__)
        self.assertIn("read_codex_credential", codex.__all__)
        self.assertTrue(callable(accounts.get_account))
        self.assertTrue(callable(operation_projection.sync_account_task))
        self.assertTrue(callable(operation_runtime_store.create_runtime_task))
        self.assertTrue(callable(task_gateway.create_task))

    def test_core_does_not_define_storage_implementation_functions(self):
        root = Path(__file__).resolve().parents[1] / "core"
        for name in ("db.py", "operation_task_store.py"):
            tree = ast.parse((root / name).read_text(encoding="utf-8"))
            definitions = [
                node.name
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            ]
            self.assertEqual([], definitions, name)

    def test_application_services_use_task_gateway_boundary(self):
        root = Path(__file__).resolve().parents[1] / "core"
        service_names = (
            "codex_retry_service.py", "codex_token_refresh_service.py", "deactivation_mail_service.py",
            "live_check_service.py", "plan_check_service.py", "registration_service.py",
        )
        for name in service_names:
            source = (root / name).read_text(encoding="utf-8")
            self.assertNotIn("from core import account_task_store", source, name)


if __name__ == "__main__":
    import unittest

    unittest.main()
