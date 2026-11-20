"""Product worker heartbeat lifecycle with injected I/O; no database or network."""
from __future__ import annotations

import threading
import time
import unittest
import logging

from core.runtime import context as context_module
from core.runtime import worker_heartbeat as heartbeat_module


def wait_until(predicate, timeout=1.):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.002)
    return bool(predicate())


class HeartbeatTests(unittest.TestCase):
    def make(self, writer=lambda _status: True, collector=lambda: {'state': 'running', 'ready': True}, **kwargs):
        gate = context_module.AdmissionGate()
        controller = heartbeat_module.WorkerHeartbeat(admission=gate, write_heartbeat=writer,
            collect_status=collector, interval=.01, freshness_budget=.06, **kwargs)
        self.addCleanup(lambda: controller.stop(timeout=1.))
        return controller, gate

    def make_clocked(self, writer=lambda _status: True, collector=lambda: {'state': 'running', 'ready': True}):
        now = [0.]
        worker, gate = self.make(writer, collector, clock=lambda: now[0])
        # Model start's reference without scheduling the two lifecycle threads.
        worker._started_at = 0.
        worker._state = 'starting'
        gate.block('heartbeat')
        return worker, gate, now

    def test_failure_logs_once_until_recovery_without_private_exception_text(self):
        def failed_writer(_payload):
            raise RuntimeError('postgres://private-password@private-host/private-db')

        worker, gate, _now = self.make_clocked(failed_writer)
        with self.assertLogs('core.runtime.worker_heartbeat', level='WARNING') as captured:
            worker._pulse()
            worker._pulse()
            worker._pulse()
            worker._write = lambda _: True
            worker._pulse()
            worker._write = failed_writer
            worker._pulse()
        self.assertEqual(len(captured.records), 2)
        for record in captured.records:
            self.assertIn('heartbeat_write_failed', record.getMessage())
            self.assertIn('RuntimeError', record.getMessage())
            self.assertNotIn('private', record.getMessage())
            self.assertIsNone(record.exc_info)
        self.assertEqual(worker.status()['error_code'], 'heartbeat_write_failed')
        self.assertIn('heartbeat', gate.reasons())

    def test_collector_failure_log_names_exception_class_without_payload(self):
        def failed_collector():
            raise ValueError('private-status-and-account')

        worker, _gate, _now = self.make_clocked(collector=failed_collector)
        with self.assertLogs('core.runtime.worker_heartbeat', level='WARNING') as captured:
            worker._pulse()
            worker._pulse()
        self.assertEqual(len(captured.records), 1)
        message = captured.records[0].getMessage()
        self.assertIn('heartbeat_collect_failed', message)
        self.assertIn('ValueError', message)
        self.assertNotIn('private', message)
        self.assertIsNone(captured.records[0].exc_info)

    def test_watchdog_and_pulse_timeout_diagnostics_run_outside_state_lock(self):
        for source in ('watchdog', 'collector', 'writer'):
            with self.subTest(source=source):
                worker, _gate, now = self.make_clocked()
                probes = []

                class LockProbe(logging.Handler):
                    def emit(self, _record):
                        acquired = threading.Event()

                        def probe():
                            with worker._lock:
                                acquired.set()

                        thread = threading.Thread(target=probe, daemon=True)
                        thread.start()
                        probes.append((thread, acquired.wait(.2)))

                logger = logging.getLogger('core.runtime.worker_heartbeat')
                handler = LockProbe()
                logger.addHandler(handler)
                try:
                    if source == 'watchdog':
                        now[0] = .061
                        worker._check_health()
                    elif source == 'collector':
                        def slow_collector():
                            now[0] = .061
                            return {'state': 'running', 'ready': True}

                        worker._collect = slow_collector
                        worker._pulse()
                    else:
                        def slow_writer(_payload):
                            now[0] = .061
                            return True

                        worker._write = slow_writer
                        worker._pulse()
                finally:
                    logger.removeHandler(handler)
                    handler.close()
                    for thread, _acquired in probes:
                        thread.join(1.)
                self.assertEqual(len(probes), 1)
                self.assertTrue(probes[0][1], 'diagnostic held the heartbeat state lock')
                self.assertEqual(worker.status()['error_code'], 'heartbeat_timeout')

    def start_pulse(self, worker, entered, release):
        pulse = threading.Thread(target=worker._pulse, daemon=True)
        def cleanup():
            release.set()
            pulse.join(1.)
            self.assertFalse(pulse.is_alive(), 'injected heartbeat pulse did not stop')
        self.addCleanup(cleanup)
        pulse.start()
        self.assertTrue(entered.wait(1.))
        return pulse

    def test_inflight_startup_write_cannot_clear_watchdog_timeout(self):
        entered, release = threading.Event(), threading.Event()
        def writer(_):
            entered.set()
            release.wait()
            return True
        worker, gate, now = self.make_clocked(writer)
        now[0] = .010
        pulse = self.start_pulse(worker, entered, release)
        now[0] = .061
        with self.assertLogs('core.runtime.worker_heartbeat', level='WARNING') as captured:
            worker._check_health()
        message = captured.records[0].getMessage()
        self.assertIn('phase=write', message)
        self.assertIn('collect_ms=0.0', message)
        self.assertIn('write_ms=51.0', message)
        self.assertEqual(worker._error, 'heartbeat_timeout')
        now[0] = .062
        release.set()
        pulse.join(1.)
        self.assertFalse(pulse.is_alive())
        self.assertEqual(worker._error, 'heartbeat_timeout')
        self.assertIn('heartbeat', gate.reasons())
        self.assertIsNone(worker._last_success)

        # A pulse begun after timeout remains eligible despite repeated checks.
        entered.clear()
        release.clear()
        now[0] = .070
        pulse = self.start_pulse(worker, entered, release)
        now[0] = .071
        worker._check_health()
        worker._check_health()
        now[0] = .072
        release.set()
        pulse.join(1.)
        self.assertFalse(pulse.is_alive())
        self.assertEqual(worker._state, 'running')
        self.assertIsNone(worker._error)
        self.assertNotIn('heartbeat', gate.reasons())
        self.assertEqual(worker._last_success, .072)

    def test_inflight_collection_cannot_clear_watchdog_timeout(self):
        entered, release = threading.Event(), threading.Event()
        writes = []
        def collect():
            entered.set()
            release.wait()
            return {'state': 'running', 'ready': True}
        worker, gate, now = self.make_clocked(lambda payload: writes.append(payload) or True, collect)
        now[0] = .010
        pulse = self.start_pulse(worker, entered, release)
        now[0] = .061
        worker._check_health()
        now[0] = .062
        release.set()
        pulse.join(1.)
        self.assertFalse(pulse.is_alive())
        self.assertEqual(len(writes), 1)
        self.assertEqual(worker._error, 'heartbeat_timeout')
        self.assertIn('heartbeat', gate.reasons())
        self.assertIsNone(worker._last_success)
        now[0] = .070
        worker._pulse()
        self.assertEqual(worker._last_success, .070)
        self.assertNotIn('heartbeat', gate.reasons())

    def test_each_new_timeout_after_prior_success_invalidates_its_inflight_write(self):
        worker, gate, now = self.make_clocked()
        worker._pulse()
        self.assertEqual(worker._last_success, 0.)
        for started, expired, finished, recovered in ((.010, .061, .062, .070), (.080, .131, .132, .140)):
            with self.subTest(started=started):
                previous_success = worker._last_success
                entered, release = threading.Event(), threading.Event()
                def writer(_):
                    entered.set()
                    release.wait()
                    return True
                worker._write = writer
                now[0] = started
                pulse = self.start_pulse(worker, entered, release)
                now[0] = expired
                worker._check_health()
                now[0] = finished
                release.set()
                pulse.join(1.)
                self.assertFalse(pulse.is_alive())
                self.assertEqual(worker._error, 'heartbeat_timeout')
                self.assertEqual(worker._last_success, previous_success)
                self.assertIn('heartbeat', gate.reasons())
                now[0] = recovered
                worker._pulse()
                self.assertEqual(worker._last_success, recovered)
                self.assertNotIn('heartbeat', gate.reasons())

    def test_timeout_then_write_failure_does_not_starve_fresh_recovery(self):
        entered, release = threading.Event(), threading.Event()
        def failed_writer(_):
            entered.set()
            release.wait()
            raise RuntimeError('synthetic database failure')
        worker, gate, now = self.make_clocked(failed_writer)
        now[0] = .010
        pulse = self.start_pulse(worker, entered, release)
        now[0] = .061
        worker._check_health()
        now[0] = .062
        release.set()
        pulse.join(1.)
        self.assertFalse(pulse.is_alive())
        self.assertEqual(worker._error, 'heartbeat_write_failed')
        self.assertIn('heartbeat', gate.reasons())
        self.assertIsNone(worker._last_success)

        entered, release = threading.Event(), threading.Event()
        def fresh_writer(_):
            entered.set()
            release.wait()
            return True
        worker._write = fresh_writer
        now[0] = .070
        pulse = self.start_pulse(worker, entered, release)
        now[0] = .071
        worker._check_health()
        worker._check_health()
        now[0] = .072
        release.set()
        pulse.join(1.)
        self.assertFalse(pulse.is_alive())
        self.assertEqual(worker._state, 'running')
        self.assertIsNone(worker._error)
        self.assertEqual(worker._last_success, .072)
        self.assertNotIn('heartbeat', gate.reasons())

    def test_fresh_write_own_budget_still_applies_after_timeout(self):
        worker, gate, now = self.make_clocked()
        now[0] = .061
        worker._check_health()
        def slow_writer(_):
            now[0] = .140
            return True
        worker._write = slow_writer
        now[0] = .070
        worker._pulse()
        self.assertEqual(worker._error, 'heartbeat_timeout')
        self.assertIn('heartbeat', gate.reasons())
        self.assertIsNone(worker._last_success)
        worker._write = lambda _: True
        now[0] = .150
        worker._pulse()
        self.assertEqual(worker._last_success, .150)
        self.assertNotIn('heartbeat', gate.reasons())

    def test_final_nonready_after_timeout_never_recovers_admission(self):
        writes = []
        worker, gate, now = self.make_clocked(lambda payload: writes.append(payload) or True)
        now[0] = .061
        worker._check_health()
        self.assertTrue(worker.stop(timeout=0.))
        worker._pulse(final=True)
        self.assertEqual(writes, [{'state': 'stopping', 'ready': False}])
        self.assertTrue(worker.status()['final_write_succeeded'])
        self.assertFalse(worker.status()['healthy'])
        self.assertIsNone(worker._last_success)
        self.assertIn('heartbeat', gate.reasons())

    def test_cas_miss_after_timeout_still_permanently_fences(self):
        writes = []
        worker, gate, now = self.make_clocked(lambda payload: writes.append(payload) or False)
        now[0] = .061
        worker._check_health()
        now[0] = .070
        worker._pulse()
        self.assertEqual(worker._error, 'heartbeat_fenced')
        self.assertEqual(worker._state, 'fenced')
        worker._pulse()
        self.assertEqual(len(writes), 1)
        self.assertIsNone(worker._last_success)
        self.assertIn('heartbeat', gate.reasons())

    def test_initial_gate_and_recovery_only_clear_own_reason(self):
        release = threading.Event()
        entered = threading.Event()
        def writer(_):
            entered.set()
            release.wait(.8)
            return True
        worker, gate = self.make(writer)
        self.addCleanup(release.set)
        gate.block('config')
        gate.block('owner_lost')
        worker.start()
        self.assertTrue(entered.wait(.3))
        self.assertIn('heartbeat', gate.reasons())
        release.set()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))
        self.assertEqual(gate.reasons(), ('config', 'owner_lost', 'startup'))

    def test_write_failure_is_sanitized_and_recovers(self):
        fail = threading.Event()
        fail.set()
        def writer(_):
            if fail.is_set():
                raise RuntimeError('postgres://password@private-host')
            return True
        worker, gate = self.make(writer)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['error_code'] == 'heartbeat_write_failed'))
        self.assertIn('heartbeat', gate.reasons())
        self.assertNotIn('password', str(worker.status()))
        fail.clear()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))
        self.assertNotIn('heartbeat', gate.reasons())

    def test_collector_failure_blocks_before_writing(self):
        writes = []
        def collect():
            raise ValueError('secret status')
        worker, gate = self.make(lambda payload: writes.append(payload) or True, collect)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['error_code'] == 'heartbeat_collect_failed'))
        self.assertEqual(writes, [])
        self.assertIn('heartbeat', gate.reasons())

    def test_cas_miss_permanently_fences_and_does_not_retry_new_generation(self):
        writes = []
        def write(payload):
            writes.append(payload)
            return False
        worker, gate = self.make(write)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['state'] == 'fenced'))
        time.sleep(.035)
        self.assertEqual(len(writes), 1)
        self.assertIn('heartbeat', gate.reasons())
        self.assertFalse(worker.status()['healthy'])

    def test_stuck_write_watchdog_and_stop_budget_remain_truthful(self):
        release = threading.Event()
        entered = threading.Event()
        def writer(_):
            entered.set()
            release.wait(.8)
            return True
        worker, gate = self.make(writer)
        self.addCleanup(release.set)
        worker.start()
        self.assertTrue(entered.wait(.3))
        self.assertTrue(wait_until(lambda: worker.status()['error_code'] == 'heartbeat_timeout'))
        started = time.monotonic()
        self.assertFalse(worker.stop(timeout=.01))
        self.assertLess(time.monotonic() - started, .1)
        self.assertTrue(worker.status()['inflight'])
        self.assertTrue(worker.status()['alive'])
        self.assertIn('heartbeat', gate.reasons())
        release.set()
        self.assertTrue(wait_until(lambda: worker.stop(timeout=.01)))
        self.assertFalse(worker.status()['healthy'])
        self.assertFalse(worker.status()['alive'])
        self.assertIn('heartbeat', gate.reasons())

    def test_late_write_does_not_clear_timeout_before_a_new_fresh_write(self):
        release_first = threading.Event()
        second_entered = threading.Event()
        release_second = threading.Event()
        writes = []
        def writer(payload):
            writes.append(payload)
            if len(writes) == 1:
                release_first.wait()
            elif len(writes) == 2:
                second_entered.set()
                release_second.wait()
            return True
        worker, gate = self.make(writer)
        self.addCleanup(release_first.set)
        self.addCleanup(release_second.set)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['error_code'] == 'heartbeat_timeout'))
        release_first.set()
        self.assertTrue(second_entered.wait(.3))
        self.assertIn('heartbeat', gate.reasons())
        self.assertFalse(worker.status()['healthy'])
        release_second.set()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))

    def test_writer_interruption_is_visible_and_fail_closed(self):
        def writer(_):
            raise SystemExit('secret interruption')
        worker, gate = self.make(writer)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['error_code'] == 'heartbeat_interrupted'))
        self.assertFalse(worker.status()['healthy'])
        self.assertIn('heartbeat', gate.reasons())
        self.assertNotIn('secret', str(worker.status()))

    def test_stop_persists_nonready_and_same_instance_cannot_restart(self):
        writes = []
        worker, gate = self.make(lambda payload: writes.append(payload) or True)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))
        worker.start()
        self.assertTrue(worker.stop(.3))
        self.assertEqual(writes[-1]['state'], 'stopping')
        self.assertFalse(writes[-1]['ready'])
        self.assertTrue(worker.status()['final_write_succeeded'])
        self.assertTrue(worker.stop(.3))
        with self.assertRaisesRegex(RuntimeError, 'restart_requires_new_instance'):
            worker.start()
        self.assertIn('heartbeat', gate.reasons())

    def test_stop_still_persists_nonready_when_collector_breaks(self):
        broken = threading.Event()
        writes = []
        def collect():
            if broken.is_set():
                raise RuntimeError('secret collector error')
            return {'state': 'running', 'ready': True}
        worker, _gate = self.make(lambda payload: writes.append(payload) or True, collect)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))
        broken.set()
        self.assertTrue(worker.stop(.3))
        self.assertEqual(writes[-1], {'state': 'stopping', 'ready': False})
        self.assertTrue(worker.status()['final_write_succeeded'])

    def test_final_write_failure_does_not_claim_durable_shutdown(self):
        def writer(payload):
            if payload['state'] == 'stopping':
                raise RuntimeError('secret')
            return True
        worker, _gate = self.make(writer)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.status()['healthy']))
        self.assertTrue(worker.stop(.3))
        self.assertFalse(worker.status()['final_write_succeeded'])
        self.assertEqual(worker.status()['error_code'], 'heartbeat_write_failed')


if __name__ == '__main__':
    unittest.main()
