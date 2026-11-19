"""Offline runtime finalization tests: real lifecycle plus injected services."""
from __future__ import annotations

import atexit
import importlib.util
import os
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.runtime.context import AdmissionGate
from core.runtime.managed import ManagedRuntime


class ManagedDrainFinalizationTests(unittest.TestCase):
    def test_remaining_components_stop_before_final_export_and_owner_release(self):
        events = []
        class Controller:
            context = SimpleNamespace(executes=True, admission=AdmissionGate())
            def start(self):
                events.append('start')
            def stop_selected(self, names, budget):
                events.extend(names)
                return True
            def stop(self, **kwargs):
                self.release_owner = kwargs['release_owner']
                events.append('remaining-stop')
                return True
            def close_owner(self, **kwargs):
                events.append('owner-close')
                return True
        heartbeat = SimpleNamespace(start=lambda: events.append('heartbeat-start'),
                                    stop=lambda **kwargs: events.append('heartbeat-stop') or True)
        manager = ManagedRuntime(controller=Controller(), heartbeat=heartbeat,
            producer_names=['producers-stop'], claim_names=['claimers-stop'],
            active_counts=lambda: {'accepted': 0, 'active': 0},
            settle=lambda _budget: events.append('settle-projections') or True,
            flush=lambda _budget: events.append('export-finalize') or True,
            close_executors=lambda _budget: events.append('executor-close') or True)
        manager.start()
        self.assertTrue(manager.stop(timeout=.5))
        self.assertEqual(events[2:], ['producers-stop', 'claimers-stop', 'executor-close',
            'settle-projections', 'remaining-stop', 'export-finalize', 'heartbeat-stop', 'owner-close'])
        self.assertFalse(manager.controller.release_owner)

    def test_export_timeout_retains_owner_and_heartbeat_for_retry(self):
        events = []
        ready = threading.Event()
        controller = SimpleNamespace(context=SimpleNamespace(executes=True, admission=AdmissionGate()),
            start=lambda: None, stop_selected=lambda names, budget: True,
            stop=lambda **kwargs: True, close_owner=lambda **kwargs: events.append('owner') or True)
        heartbeat = SimpleNamespace(start=lambda: None, stop=lambda **kwargs: events.append('heartbeat') or True)
        manager = ManagedRuntime(controller=controller, heartbeat=heartbeat,
            producer_names=[], claim_names=[], active_counts=lambda: {'accepted': 0},
            settle=lambda budget: True, flush=lambda budget: ready.is_set(), close_executors=lambda budget: True)
        manager.start()
        self.assertFalse(manager.stop(timeout=.01))
        self.assertEqual(events, [])
        ready.set()
        self.assertTrue(manager.stop(timeout=.1))
        self.assertEqual(events, ['heartbeat', 'owner'])


class CompatExportFinalizationTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[2] / 'core/storage/compat_export.py'
        spec = importlib.util.spec_from_file_location('isolated_compat_export', path)
        self.exports = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.exports)
        atexit.unregister(self.exports.shutdown)
        self.addCleanup(lambda: self.exports.finish_runtime(timeout=1.))
        self.environment = patch.dict(os.environ, {'COMPAT_EXPORT_MODE': 'debounced', 'COMPAT_EXPORT_DEBOUNCE_SECONDS': '0'})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_schedule_after_finish_keeps_pending_without_reviving_worker(self):
        called = threading.Event()
        self.exports.register('example', called.set)
        self.assertTrue(self.exports.finish_runtime(timeout=.2))
        self.exports.schedule('example')
        self.assertFalse(called.wait(.03))
        self.assertEqual(self.exports.pending(), ['example'])
        self.assertFalse(self.exports.finish_runtime(timeout=.1))
        self.assertIsNone(self.exports._WORKER)

    def test_sync_schedule_after_finish_keeps_pending_without_running_exporter(self):
        called = threading.Event()
        self.exports.register('example', called.set)
        self.assertTrue(self.exports.finish_runtime(timeout=.2))
        with patch.dict(os.environ, {'COMPAT_EXPORT_MODE': 'sync'}):
            self.exports.schedule('example')
        self.assertFalse(called.is_set())
        self.assertEqual(self.exports.pending(), ['example'])

    def test_inflight_export_is_drained_then_late_schedule_cannot_start_another(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def export():
            entered.set()
            release.wait(.5)
        self.exports.register('example', export)
        self.exports.schedule('example')
        self.assertTrue(entered.wait(.2))
        self.assertFalse(self.exports.finish_runtime(timeout=.01))
        release.set()
        self.assertTrue(self.exports.finish_runtime(timeout=.2))
        self.exports.schedule('example')
        self.assertEqual(self.exports.pending(), ['example'])
        self.assertFalse(self.exports.finish_runtime(timeout=.01))


if __name__ == '__main__':
    unittest.main()
