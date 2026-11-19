"""Phase 6 T3 dependency rollback regression with fake transactions only."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import types
import unittest
from unittest.mock import patch

from core.storage import postgres
from core.storage.operations import dependency_handoffs


class DependencyHandoffFenceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.has_permit = True
        self.attempts_match = True
        self.current = None
        self.conn = types.SimpleNamespace(cursor=self.cursor)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(
            postgres, "connect", side_effect=AssertionError("real DB forbidden")))
        self.stack.enter_context(patch.object(dependency_handoffs.common, "_connect", self.connect))
        self.stack.enter_context(patch.object(dependency_handoffs.common, "_table",
            lambda name: '"fixture"."' + name + '"'))
        self.stack.enter_context(patch.object(
            dependency_handoffs.bulk_execution, "dependency_update", self.bulk_update))

    @contextmanager
    def connect(self):
        self.current = self.conn
        self.calls.append("begin")
        yield self.conn
        self.calls.append("commit")
        self.current = None

    @contextmanager
    def cursor(self):
        cursor = types.SimpleNamespace(
            execute=self.execute,
            fetchone=lambda: {"permit_id": "p"} if self.has_permit else None,
            rowcount=int(self.attempts_match),
        )
        yield cursor

    @contextmanager
    def bulk_update(self, conn, *, dependency_id):
        self.assertIs(self.current, conn)
        self.calls.append(("bulk", dependency_id))
        yield

    def execute(self, sql, args):
        self.assertIs(self.current, self.conn)
        self.calls.append(("sql", " ".join(sql.split()), args))

    def rollback(self):
        return dependency_handoffs.requeue_dependency(
            9, permit_id="p", execution_id="e", attempts=3, reason="runtime_execution_paused")

    def test_exact_live_permit_locked_before_attempt_fenced_requeue(self):
        self.assertTrue(self.rollback())
        queries = [call for call in self.calls if isinstance(call, tuple) and call[0] == "sql"]
        self.assertIn("FOR UPDATE", queries[0][1])
        self.assertIn("released_at IS NULL", queries[0][1])
        self.assertEqual(("p", "e", "operation_dependency:9"), queries[0][2])
        self.assertIn("status='running' AND attempts=%s", queries[1][1])
        self.assertIn("attempts=GREATEST(attempts - 1, 0)", queries[1][1])
        self.assertEqual(("runtime_execution_paused", 9, 3), queries[1][2])
        self.assertEqual("commit", self.calls[-1])

    def test_missing_or_released_permit_never_changes_dependency(self):
        self.has_permit = False
        self.assertFalse(self.rollback())
        self.assertEqual(1, len([
            call for call in self.calls if isinstance(call, tuple) and call[0] == "sql"]))

    def test_new_claim_attempt_or_terminal_dependency_cannot_be_requeued(self):
        self.attempts_match = False
        self.assertFalse(self.rollback())


if __name__ == "__main__":
    unittest.main()
