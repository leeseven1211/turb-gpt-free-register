"""Phase 6 T3 role and settlement gates use actual runtime access functions."""
from __future__ import annotations

from contextlib import ExitStack
import threading
import unittest
from unittest.mock import patch

from core.runtime import execution_access, process, standalone
from core.runtime.context import RuntimeContext


class RuntimeExecutionGateTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.current = None
        self.admitted = False
        self.owner = True
        self.calls = []

        def admitted():
            self.calls.append("admitted")
            return self.admitted

        for guard in (
            patch.object(process, "get_runtime_context", lambda: self.current),
            patch.object(process, "execution_admitted", admitted),
            patch.object(process, "execution_owner_valid", lambda: self.owner),
            patch.object(standalone, "_OWNER", None),
            patch.object(standalone, "_LOST", threading.Event()),
        ):
            self.stack.enter_context(guard)

    def test_unmanaged_legacy_explicitly_remains_compatible(self):
        self.assertTrue(execution_access.component_start_allowed())
        self.assertTrue(execution_access.execution_allowed())
        self.assertEqual(self.calls, [])

    def test_web_cannot_start_or_execute_even_if_gate_reports_open(self):
        self.current = RuntimeContext("web")
        self.admitted = True
        self.assertFalse(execution_access.component_start_allowed())
        self.assertFalse(execution_access.execution_allowed())
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(RuntimeError, "web_execution_forbidden"):
            execution_access.require_execution_component()

    def test_worker_can_initialize_before_recovery_but_cannot_admit(self):
        self.current = RuntimeContext("worker")
        self.assertTrue(execution_access.component_start_allowed())
        self.assertFalse(execution_access.execution_allowed())
        self.assertEqual(self.calls, ["admitted"])

    def test_worker_requires_owner_and_gate_not_just_role(self):
        self.current = RuntimeContext("worker")
        self.admitted = True
        self.assertTrue(execution_access.execution_allowed())
        self.admitted = False
        self.assertFalse(execution_access.execution_allowed())

    def test_settlement_keeps_owner_check_when_admission_closed(self):
        self.current = RuntimeContext("worker")
        self.admitted = False
        self.assertTrue(execution_access.execution_owner_valid())
        self.assertFalse(execution_access.execution_allowed())
        self.owner = False
        self.assertFalse(execution_access.execution_owner_valid())

    def test_settlement_never_grants_web_but_preserves_explicit_standalone(self):
        self.assertTrue(execution_access.execution_owner_valid())
        self.current = RuntimeContext("web")
        self.assertFalse(execution_access.execution_owner_valid())


if __name__ == "__main__":
    unittest.main()
