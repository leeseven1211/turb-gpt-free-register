"""Managed lifecycle regressions migrated from the Phase 6 T7 candidate."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from core.runtime.composition import ComponentHooks, RuntimeController
from core.runtime.context import AdmissionGate, RuntimeContext
from core.runtime.managed import ManagedRuntime
from core.runtime.manifest import COMPONENTS


class ManagedRuntimeTests(unittest.TestCase):
    def setup_runtime(self):
        self.calls = []
        self.gate = AdmissionGate()
        controller = Mock()
        controller.context.admission = self.gate
        controller.context.executes = True
        controller.start.side_effect = lambda: self.calls.append("start") or True
        controller.stop_selected.side_effect = lambda names, budget: self.calls.append(
            ("stop", tuple(names))) or True
        controller.stop.side_effect = lambda **kwargs: self.calls.append("remaining") or True
        controller.close_owner.side_effect = lambda **kwargs: self.calls.append("owner") or True
        heartbeat = Mock()
        heartbeat.start.side_effect = lambda: self.calls.append("heartbeat")
        heartbeat.stop.side_effect = lambda **kwargs: self.calls.append("heartbeat_stop") or True
        runtime = ManagedRuntime(
            controller=controller, heartbeat=heartbeat,
            producer_names=("producer",), claim_names=("claim",),
            active_counts=lambda: {"accepted": 0},
            flush=lambda budget: self.calls.append("flush") or True,
            close_executors=lambda budget: self.calls.append("executors") or True,
        )
        return runtime, controller, heartbeat

    def test_gate_closed_until_heartbeat(self):
        runtime, _controller, _heartbeat = self.setup_runtime()
        runtime.start()
        self.assertIn("heartbeat", self.gate.reasons())
        self.assertEqual(self.calls, ["start", "heartbeat"])

    def test_drain_order_and_owner_last(self):
        # The candidate checked this with a mocked controller. Keep the same
        # order assertion against the product controller and its real gate.
        calls = []
        alive = {"owner": False}

        def start_owner():
            alive["owner"] = True

        def require_owner():
            self.assertTrue(alive["owner"])

        def close_owner(timeout):
            calls.append("owner")
            alive["owner"] = False
            return True

        owner = SimpleNamespace(start=start_owner, require_owner=require_owner, close=close_owner)
        context = RuntimeContext("worker")
        hooks = {}
        for spec in COMPONENTS:
            def stop(_context, budget, name=spec.name):
                self.assertGreaterEqual(budget, 0)
                self.assertTrue(alive["owner"])
                self.assertIn("draining", context.admission.reasons())
                calls.append(("stop", name))
                return True
            hooks[spec.name] = ComponentHooks(lambda _context: None, stop)
        controller = RuntimeController(context, hooks, owner=owner)
        heartbeat = SimpleNamespace(
            start=lambda: None,
            stop=lambda **kwargs: calls.append("heartbeat_stop") or True,
        )
        producers = ("at_refresher",)
        claims = ("registration_dispatcher",)
        runtime = ManagedRuntime(
            controller=controller, heartbeat=heartbeat,
            producer_names=producers, claim_names=claims,
            active_counts=lambda: {"accepted": 0},
            flush=lambda budget: calls.append("flush") or True,
            close_executors=lambda budget: calls.append("executors") or True,
        )
        runtime.start()
        remaining = [
            name for name in reversed(controller.status()["remaining_components"])
            if name not in producers + claims
        ]
        self.assertTrue(runtime.stop(timeout=1))
        self.assertEqual(calls, [
            ("stop", "at_refresher"), ("stop", "registration_dispatcher"), "executors",
            *(("stop", name) for name in remaining),
            "flush", "heartbeat_stop", "owner",
        ])
        self.assertFalse(alive["owner"])
        self.assertEqual(controller.status()["remaining_components"], [])

    def test_busy_drain_retains_owner_and_heartbeat(self):
        runtime, controller, heartbeat = self.setup_runtime()
        runtime.start()
        runtime._active_counts = lambda: {"accepted": 1}
        self.assertFalse(runtime.stop(timeout=0))
        controller.close_owner.assert_not_called()
        heartbeat.stop.assert_not_called()

    def test_unknown_counts_do_not_release(self):
        runtime, controller, _heartbeat = self.setup_runtime()
        runtime.start()
        runtime._active_counts = lambda: {"accepted": None}
        self.assertFalse(runtime.stop(timeout=0))
        controller.close_owner.assert_not_called()

    def test_producer_timeout_retains_owner(self):
        runtime, controller, heartbeat = self.setup_runtime()
        runtime.start()
        controller.stop_selected.side_effect = None
        controller.stop_selected.return_value = False
        self.assertFalse(runtime.stop(timeout=0))
        controller.close_owner.assert_not_called()
        heartbeat.stop.assert_not_called()

    def test_heartbeat_timeout_retains_owner(self):
        runtime, controller, heartbeat = self.setup_runtime()
        runtime.start()
        heartbeat.stop.side_effect = None
        heartbeat.stop.return_value = False
        self.assertFalse(runtime.stop(timeout=1))
        controller.close_owner.assert_not_called()

    def test_flush_failure_retains_owner(self):
        runtime, controller, _heartbeat = self.setup_runtime()
        runtime.start()
        runtime._flush = Mock(side_effect=OSError("private"))
        self.assertFalse(runtime.stop(timeout=1))
        controller.close_owner.assert_not_called()
        self.assertEqual(runtime.status()["error_code"], "runtime_flush_failed")

    def test_start_failure_cleans_heartbeat_before_owner(self):
        runtime, _controller, heartbeat = self.setup_runtime()
        heartbeat.start.side_effect = RuntimeError("private")
        with self.assertRaises(RuntimeError):
            runtime.start()
        self.assertEqual(self.calls[-3:], ["remaining", "heartbeat_stop", "owner"])

    def test_web_does_not_start_heartbeat(self):
        runtime, controller, heartbeat = self.setup_runtime()
        controller.context.executes = False
        runtime.start()
        heartbeat.start.assert_not_called()
        self.assertNotIn("heartbeat", self.gate.reasons())

    def test_retry_stop_after_expired_deadline_retains_owner(self):
        runtime, _controller, _heartbeat = self.setup_runtime()
        runtime.start()
        runtime._active_counts = lambda: {"accepted": 1}
        self.assertFalse(runtime.stop(timeout=0))
        runtime._active_counts = lambda: {"accepted": 0}
        self.assertFalse(runtime.stop(timeout=1))
        self.assertIn("draining", self.gate.reasons())
        self.assertNotIn("owner", self.calls)


if __name__ == "__main__":
    unittest.main()
