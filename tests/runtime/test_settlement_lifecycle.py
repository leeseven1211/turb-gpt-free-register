"""Offline lifecycle barriers: owned work, actual joins and one stop deadline."""
from __future__ import annotations

import threading
import time
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from core.runtime import assembly, bindings, readiness
from core.runtime.composition import ComponentHooks, RuntimeController, RuntimeStartError
from core.runtime.context import AdmissionGate
from core.runtime.context import RuntimeContext
from core.runtime.managed import ManagedRuntime
from core.runtime.manifest import COMPONENTS
from core.runtime.worker_heartbeat import WorkerHeartbeat


class ThreadSettlement:
    """Synthetic local cleanup carrier; never opens storage or business I/O."""
    def __init__(self, events):
        self.events = events
        self.pending = threading.Event()
        self.cleanup_done = threading.Event()
        self.release_cleanup = threading.Event()
        self.stop_event = threading.Event()
        self.entered = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.deadlines = []
        self.active_deadline = None

    def run(self):
        self.entered.set()
        while not self.stop_event.wait(.001):
            if self.pending.is_set() and self.release_cleanup.is_set():
                self.pending.clear()
                self.cleanup_done.set()
                self.events.append('cleanup')

    def _settlement_domain(self):
        return 'synthetic-domain'

    def start_runtime(self, *, domain=None, admission=None):
        self.thread.start()
        assert self.entered.wait(.5)
        return True

    def active_counts(self):
        return {'settlement_pending': int(self.pending.is_set())}

    def begin_shutdown(self, deadline):
        self.active_deadline = deadline
        return True

    def begin_finalization(self, deadline):
        self.events.append('settlement-finalization')
        self.active_deadline = deadline
        return True

    def end_shutdown(self, deadline):
        if self.active_deadline == deadline and self.thread.is_alive() and not self.stop_event.is_set():
            self.active_deadline = None
            self.events.append('settlement-background')
            return True
        return False

    def stop_release_runtime(self, deadline):
        return True

    def drain_runtime(self, deadline):
        self.deadlines.append(deadline)
        self.events.append('settlement-drain')
        while self.pending.is_set() and time.monotonic() < deadline:
            self.cleanup_done.wait(min(.005, max(0., deadline - time.monotonic())))
        return not self.pending.is_set()

    def stop_runtime(self, deadline):
        self.events.append('settlement-stop')
        self.stop_event.set()
        self.thread.join(max(0., deadline - time.monotonic()))
        return not self.thread.is_alive()


class SettlementLifecycleTests(unittest.TestCase):
    def manager(self, *, counts=None, on_components_stop=None, clock=time.monotonic):
        events = []
        gate = AdmissionGate()
        controller = SimpleNamespace(
            context=SimpleNamespace(executes=True, admission=gate),
            start=lambda: None,
            stop_selected=lambda names, budget: events.append(('selected', tuple(names), budget)) or True,
            stop=lambda **kwargs: (on_components_stop() if on_components_stop else None) or
                events.append('components-stop') or True,
            close_owner=lambda **kwargs: events.append('owner-close') or True,
        )
        heartbeat = SimpleNamespace(start=lambda: None,
            stop=lambda **kwargs: events.append('heartbeat-stop') or True)
        manager = ManagedRuntime(controller=controller, heartbeat=heartbeat,
            producer_names=(), claim_names=(), active_counts=counts or (lambda: {'accepted': 0}),
            settle=lambda budget: events.append('projections') or True,
            flush=lambda budget: events.append('flush') or True,
            close_executors=lambda budget: events.append('executors-joined') or True,
            close_connections=lambda budget: events.append('pools-close') or True,
            clock=clock)
        return manager, events

    def attach_carrier(self, manager, events):
        carrier = ThreadSettlement(events)
        carrier.start_runtime()
        self.addCleanup(carrier.thread.join, .5)
        self.addCleanup(carrier.stop_event.set)
        manager._settlement = carrier
        return carrier

    def test_second_drain_consumes_stop_hook_cleanup_before_join_and_pool_close(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        def stop_components(**kwargs):
            events.append('components-stop')
            self.assertTrue(carrier.thread.is_alive())
            carrier.pending.set()
            carrier.release_cleanup.set()
            return True
        manager.controller.stop = stop_components
        manager._active_counts = lambda: {'accepted': 0, **carrier.active_counts()}
        manager.start()
        self.assertTrue(manager.stop(timeout=.5))
        self.assertTrue(carrier.cleanup_done.is_set(), 'stop hook cleanup was skipped')
        self.assertFalse(carrier.thread.is_alive(), 'callback exit is not a thread join')
        self.assertEqual(len(carrier.deadlines), 2)
        self.assertLess(events.index('cleanup'), events.index('settlement-stop'))
        self.assertLess(events.index('settlement-stop'), events.index('pools-close'))
        self.assertLess(events.index('pools-close'), events.index('owner-close'))

    def test_first_drain_runs_while_pending_work_blocks_idle(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        carrier.pending.set()
        manager._active_counts = lambda: {'accepted': 0, **carrier.active_counts()}
        # Drain announces the shared deadline and allows an already-running
        # local cleanup to finish; a late-only settlement callback cannot do it.
        original_drain = carrier.drain_runtime
        def drain(deadline):
            carrier.release_cleanup.set()
            return original_drain(deadline)
        carrier.drain_runtime = drain
        manager.start()
        self.assertTrue(manager.stop(timeout=.2))
        self.assertTrue(carrier.cleanup_done.is_set())
        self.assertLess(events.index('settlement-drain'), events.index('executors-joined'))

    def test_repeated_stop_cannot_renew_the_first_deadline(self):
        now = [10.]
        manager, events = self.manager(counts=lambda: {'accepted': 1}, clock=lambda: now[0])
        manager.start()
        self.assertFalse(manager.stop(timeout=0))
        now[0] = 11.
        manager._active_counts = lambda: {'accepted': 0}
        self.assertFalse(manager.stop(timeout=100))
        selected_budgets = [item[2] for item in events if isinstance(item, tuple)]
        self.assertEqual(selected_budgets, [])
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)

    def test_live_settlement_thread_prevents_pool_and_owner_close(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        carrier.stop_runtime = lambda deadline: False
        manager.start()
        self.assertFalse(manager.stop(timeout=.05))
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)
        self.assertEqual(manager.status()['state'], 'stop_incomplete')

    def test_pending_barrier_consumes_one_short_deadline_and_keeps_threads_owned(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        carrier.pending.set()
        manager._active_counts = lambda: {'accepted': 0, **carrier.active_counts()}
        manager.start()
        started = time.monotonic()
        self.assertFalse(manager.stop(timeout=.02))
        self.assertLess(time.monotonic() - started, .3)
        self.assertTrue(carrier.thread.is_alive())
        self.assertFalse(carrier.cleanup_done.is_set())
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)
        carrier.release_cleanup.set()
        self.assertTrue(carrier.cleanup_done.wait(.3))
        self.assertFalse(manager.stop(timeout=5))
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)

    def test_incomplete_stop_lifts_only_carrier_attempt_budget_and_explicit_finalize_closes(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        carrier.pending.set()
        manager._active_counts = lambda: {'accepted': 0, **carrier.active_counts()}
        manager.start()
        self.assertFalse(manager.stop(.02))
        original_deadline = manager._shutdown_deadline
        self.assertIsNone(carrier.active_deadline)
        self.assertTrue(carrier.thread.is_alive())
        self.assertIn('draining', manager.controller.context.admission.reasons())
        self.assertNotIn('owner-close', events)
        carrier.release_cleanup.set()
        self.assertTrue(carrier.cleanup_done.wait(.3))
        self.assertFalse(manager.stop(10))
        self.assertEqual(manager._shutdown_deadline, original_deadline)
        self.assertNotIn('owner-close', events)
        self.assertTrue(carrier.thread.is_alive(), 'expired stop must not stop the compensation carrier')
        self.assertFalse(carrier.stop_event.is_set())
        finalizer = getattr(manager, 'finalize_incomplete', None)
        self.assertTrue(callable(finalizer), 'explicit incomplete finalization API missing')
        self.assertTrue(finalizer(.5))
        self.assertEqual(manager._shutdown_deadline, original_deadline)
        self.assertFalse(carrier.thread.is_alive())
        self.assertIn('settlement-finalization', events)
        self.assertLess(events.index('pools-close'), events.index('owner-close'))

    def test_finalize_is_rejected_before_incomplete_stop_and_cannot_renew_its_budget(self):
        now = [10.]
        manager, events = self.manager(counts=lambda: {'accepted': 1}, clock=lambda: now[0])
        finalizer = getattr(manager, 'finalize_incomplete', None)
        self.assertTrue(callable(finalizer), 'explicit incomplete finalization API missing')
        self.assertFalse(finalizer(20))
        manager.start()
        self.assertFalse(finalizer(20))
        self.assertFalse(manager.stop(0))
        original_deadline = manager._shutdown_deadline
        self.assertFalse(finalizer(0))
        final_deadline = manager._finalize_deadline
        now[0] = 11.
        manager._active_counts = lambda: {'accepted': 0}
        self.assertFalse(finalizer(100))
        self.assertEqual(manager._shutdown_deadline, original_deadline)
        self.assertEqual(manager._finalize_deadline, final_deadline)
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)

    def test_installed_runtime_exposes_explicit_incomplete_finalization(self):
        manager, events = self.manager()
        installed = assembly.InstalledRuntime(bootstrap=None, controller=manager.controller,
            observer=None, owner=None, manager=manager, heartbeat=None)
        manager.start()
        self.assertFalse(installed.stop(0))
        finalizer = getattr(installed, 'finalize_incomplete', None)
        self.assertTrue(callable(finalizer), 'installed runtime finalization API missing')
        self.assertTrue(finalizer(.5))
        self.assertIn('owner-close', events)

    def test_concurrent_finalization_calls_share_one_deadline_and_no_business_restart(self):
        manager, events = self.manager(counts=lambda: {'accepted': 1})
        manager.start()
        self.assertFalse(manager.stop(0))
        original_deadline = manager._shutdown_deadline
        manager._active_counts = lambda: {'accepted': 0}
        entered, release = threading.Event(), threading.Event()
        calls = []
        def close_executors(budget):
            calls.append(budget)
            entered.set()
            release.wait(min(.3, budget))
            return release.is_set()
        manager._close_executors = close_executors
        results = []
        finalizer = getattr(manager, 'finalize_incomplete', None)
        self.assertTrue(callable(finalizer), 'explicit incomplete finalization API missing')
        first = threading.Thread(target=lambda: results.append(finalizer(.3)), daemon=True)
        second = threading.Thread(target=lambda: results.append(finalizer(10)), daemon=True)
        self.addCleanup(first.join, .5)
        self.addCleanup(second.join, .5)
        self.addCleanup(release.set)
        first.start()
        self.assertTrue(entered.wait(.2))
        final_deadline = manager._finalize_deadline
        second.start()
        release.set()
        first.join(.5)
        second.join(.5)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(results, [True, True])
        self.assertEqual(manager._finalize_deadline, final_deadline)
        self.assertEqual(manager._shutdown_deadline, original_deadline)
        self.assertEqual(len(calls), 1)
        self.assertEqual(events.count('pools-close'), 1)
        self.assertEqual(events.count('owner-close'), 1)
        self.assertIn('draining', manager.controller.context.admission.reasons())

    def test_teardown_exception_is_incomplete_and_allows_explicit_retained_cleanup(self):
        for boundary in ('executors', 'heartbeat', 'connections'):
            with self.subTest(boundary=boundary):
                manager, events = self.manager()
                carrier = self.attach_carrier(manager, events)
                fail = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('private details'))
                if boundary == 'executors':
                    manager._close_executors = fail
                elif boundary == 'heartbeat':
                    manager._heartbeat.stop = fail
                else:
                    manager._close_connections = fail
                manager.start()
                self.assertFalse(manager.stop(.2))
                self.assertEqual(manager.status(), {
                    'state': 'stop_incomplete', 'error_code': 'runtime_stop_failed'})
                self.assertNotIn('private', repr(manager.status()))
                self.assertNotIn('owner-close', events)
                if carrier.thread.is_alive():
                    self.assertIsNone(carrier.active_deadline)
                manager._close_executors = lambda budget: True
                manager._heartbeat.stop = lambda **kwargs: True
                manager._close_connections = lambda budget: events.append('pools-close') or True
                self.assertTrue(manager.finalize_incomplete(.3))
                self.assertFalse(carrier.thread.is_alive())
                self.assertIn('owner-close', events)

    def test_legacy_release_thread_must_join_before_pool_and_owner_close(self):
        manager, events = self.manager()
        manager._close_releases = lambda deadline: False
        manager.start()
        self.assertFalse(manager.stop(timeout=.05))
        self.assertNotIn('pools-close', events)
        self.assertNotIn('owner-close', events)

    def test_coordinator_receives_original_deadline_before_producers_stop(self):
        manager, events = self.manager()
        carrier = self.attach_carrier(manager, events)
        carrier.begin_shutdown = lambda deadline: events.append(('deadline', deadline))
        manager.start()
        self.assertTrue(manager.stop(timeout=.5))
        deadline_index = next((index for index, event in enumerate(events)
                               if isinstance(event, tuple) and event[0] == 'deadline'), None)
        self.assertIsNotNone(deadline_index)
        first_stop = next(index for index, event in enumerate(events)
                          if isinstance(event, tuple) and event[0] == 'selected')
        self.assertLess(deadline_index, first_stop)

    def test_startup_rollback_joins_legacy_releases_before_owner(self):
        events = []
        carrier = ThreadSettlement(events)
        self.addCleanup(carrier.thread.join, .5)
        self.addCleanup(carrier.stop_event.set)
        modules = {
            'core.operations.settlement': carrier,
            'core.operations.concurrency': SimpleNamespace(
                stop_release_runtime=lambda deadline: events.append('legacy-join') or False),
        }
        hooks = bindings.build_components(resolve=modules.__getitem__)
        carrier.start_runtime()
        self.assertFalse(hooks['settlement'].stop(RuntimeContext('worker'), .2))
        self.assertIn('legacy-join', events)

    def test_missing_settlement_health_blocks_local_and_remote_readiness(self):
        components = {name: {'started': True, 'alive': True}
                      for name in readiness.REQUIRED_COMPONENTS}
        components['settlement']['healthy'] = True
        components['config_observer']['state'] = 'applied'
        components.pop('settlement', None)
        self.assertFalse(readiness.execution_ready(state='running', admission_open=True,
            owner_valid=True, components=components))
        record = dict(state='running', ready=True, owner_nonce='nonce', generation=1,
            release='release', applied_db_revision=1, components=components)
        self.assertFalse(readiness.remote_status(record, expected_release='release',
            required_db_revision=1)['ready'])

    def test_remote_counts_are_numeric_and_sanitized(self):
        components = {name: {'started': True, 'alive': True}
                      for name in readiness.REQUIRED_COMPONENTS}
        components['settlement']['healthy'] = True
        components['config_observer']['state'] = 'applied'
        record = dict(state='running', ready=True, owner_nonce='nonce', generation=1,
            release='release', applied_db_revision=1, components=components,
            counts={'accepted': 0, 'settlement_pending': 2, 'credential': 'private'})
        value = readiness.remote_status(record, expected_release='release', required_db_revision=1)
        self.assertEqual(value.get('counts'), {'accepted': 0, 'settlement_pending': 2})
        self.assertNotIn('private', repr(value))

    def test_executor_join_ignores_coordinator_owned_counts(self):
        pools = [SimpleNamespace(close_runtime=lambda timeout: True) for _ in range(2)]
        modules = {
            'core.operations.executor': SimpleNamespace(executor=pools[0], extract_executor=pools[1]),
            'core.registration.service': SimpleNamespace(close_runtime_executor=lambda timeout: True),
        }
        import core.operations
        import core.registration
        with ExitStack() as stack:
            stack.enter_context(patch.dict('sys.modules', modules))
            stack.enter_context(patch.object(core.operations, 'executor',
                modules['core.operations.executor'], create=True))
            stack.enter_context(patch.object(core.registration, 'service',
                modules['core.registration.service'], create=True))
            stack.enter_context(patch.object(assembly, '_business_counts',
                return_value={'accepted': 0, 'active': 0}))
            stack.enter_context(patch.object(assembly, '_active_counts',
                return_value={'accepted': 0, 'active': 0, 'settlement_pending': 1}))
            self.assertTrue(assembly._close_executors(.1))

    def test_startup_carrier_precedes_claimers_and_failed_start_joins_before_owner(self):
        events = []
        carrier = ThreadSettlement(events)
        self.addCleanup(carrier.thread.join, .5)
        self.addCleanup(carrier.stop_event.set)
        owner = SimpleNamespace(start=lambda: events.append('owner-start'),
            require_owner=lambda: None,
            close=lambda timeout: events.append('owner-close') or
                (not carrier.thread.is_alive()))
        hooks = {spec.name: ComponentHooks(lambda ctx: None, lambda ctx, timeout: True)
                 for spec in COMPONENTS}
        hooks['settlement'] = bindings.build_components(
            resolve=lambda name: carrier)['settlement']
        def claim(ctx):
            self.assertTrue(carrier.thread.is_alive())
            events.append('claimer')
            raise RuntimeError('synthetic startup failure')
        hooks['operation_dispatcher'] = ComponentHooks(claim, lambda ctx, timeout: True)
        controller = RuntimeController(RuntimeContext('worker'), hooks, owner=owner)
        with self.assertRaises(RuntimeStartError):
            controller.start()
        self.assertIn('claimer', events)
        self.assertFalse(carrier.thread.is_alive())
        self.assertLess(events.index('settlement-stop'), events.index('owner-close'))

    def test_heartbeat_success_clears_only_heartbeat_reason(self):
        gate = AdmissionGate()
        gate.unblock('startup')
        for reason in ('heartbeat', 'settlement', 'owner_lost', 'draining'):
            gate.block(reason)
        heartbeat = WorkerHeartbeat(admission=gate, write_heartbeat=lambda status: True,
            collect_status=lambda: {'ready': False})
        heartbeat._pulse()
        self.assertEqual(gate.reasons(), ('draining', 'owner_lost', 'settlement'))

    def test_actual_controller_keeps_carrier_through_all_other_stop_hooks(self):
        events = []
        carrier = ThreadSettlement(events)
        self.addCleanup(carrier.thread.join, .5)
        self.addCleanup(carrier.stop_event.set)
        owner = SimpleNamespace(start=lambda: None, require_owner=lambda: None,
            close=lambda timeout: events.append('owner-close') or
                not carrier.thread.is_alive())
        hooks = {spec.name: ComponentHooks(lambda ctx: None, lambda ctx, timeout: True)
                 for spec in COMPONENTS}
        hooks['settlement'] = bindings.build_components(
            resolve=lambda name: carrier)['settlement']
        def cleanup_stop(ctx, budget):
            self.assertTrue(carrier.thread.is_alive())
            events.append('stop-hook')
            carrier.pending.set()
            carrier.release_cleanup.set()
            return True
        hooks['proxy_pool'] = ComponentHooks(lambda ctx: None, cleanup_stop)
        controller = RuntimeController(RuntimeContext('worker'), hooks, owner=owner)
        manager = ManagedRuntime(controller=controller,
            heartbeat=SimpleNamespace(start=lambda: None, stop=lambda **kw: True),
            producer_names=(), claim_names=(), active_counts=carrier.active_counts,
            flush=lambda budget: True, close_executors=lambda budget: True,
            close_connections=lambda budget: events.append('pools-close') or True,
            settlement=carrier, settlement_component='settlement')
        manager.start()
        self.assertTrue(manager.stop(.5))
        self.assertFalse(carrier.thread.is_alive())
        self.assertTrue(carrier.cleanup_done.is_set())
        self.assertEqual(controller.status()['remaining_components'], [])
        self.assertLess(events.index('stop-hook'), events.index('cleanup'))
        self.assertLess(events.index('settlement-stop'), events.index('pools-close'))

    def test_startup_rollback_preserves_carrier_until_cleanup_producer_joins(self):
        events = []
        carrier = ThreadSettlement(events)
        self.addCleanup(carrier.thread.join, .5)
        self.addCleanup(carrier.stop_event.set)
        late_cleanup, enqueued = threading.Event(), threading.Event()
        def produce_cleanup():
            late_cleanup.wait(.5)
            carrier.pending.set()
            carrier.release_cleanup.set()
            enqueued.set()
        producer = threading.Thread(target=produce_cleanup, daemon=True)
        self.addCleanup(producer.join, .5)
        self.addCleanup(late_cleanup.set)
        modules = {'core.operations.settlement': carrier,
            'core.operations.concurrency': SimpleNamespace(stop_release_runtime=lambda deadline: True),
            'core.storage.operations.permits': SimpleNamespace(_settlement_domain=lambda: 'domain')}
        hooks = {spec.name: ComponentHooks(lambda ctx: None, lambda ctx, timeout: True)
                 for spec in COMPONENTS}
        hooks['settlement'] = bindings.build_components(resolve=modules.__getitem__)['settlement']
        hooks['proxy_pool'] = ComponentHooks(lambda ctx: producer.start(), lambda ctx, timeout: False)
        def fail(ctx):
            raise RuntimeError('synthetic startup failure')
        hooks['operation_dispatcher'] = ComponentHooks(fail, lambda ctx, timeout: True)
        owner = SimpleNamespace(start=lambda: None, require_owner=lambda: None,
            close=lambda timeout: events.append('owner-close') or True)
        controller = RuntimeController(RuntimeContext('worker'), hooks, owner=owner)
        with self.assertRaises(RuntimeStartError):
            controller.start()
        self.assertTrue(carrier.thread.is_alive())
        self.assertNotIn('owner-close', events)
        late_cleanup.set()
        self.assertTrue(enqueued.wait(.3))
        self.assertTrue(carrier.cleanup_done.wait(.3))
        producer.join(.3)
        controller.components['proxy_pool'] = ComponentHooks(lambda ctx: None,
            lambda ctx, timeout: not producer.is_alive())
        self.assertTrue(controller.stop(.5))
        self.assertFalse(carrier.thread.is_alive())
        self.assertIn('owner-close', events)

    def test_registration_pending_is_counted_and_missing_is_unknown(self):
        for value in (1, None, True, 'invalid'):
            modules = {
                'core.operations.concurrency': SimpleNamespace(release_runtime_status=lambda: {
                    'pending': 0, 'inflight': 0, 'alive': False, 'renewal_pending': 0,
                    **({} if value is None else {'registration_pending': value})}),
                'core.operations.settlement': SimpleNamespace(active_counts=lambda: {
                    name: 0 for name in assembly.SETTLEMENT_COUNT_KEYS}),
            }
            import core.operations
            with self.subTest(value=value), patch.dict('sys.modules', modules), patch.object(
                    core.operations, 'concurrency', modules['core.operations.concurrency'],
                    create=True), patch.object(core.operations, 'settlement',
                    modules['core.operations.settlement'], create=True), patch.object(
                    assembly, '_business_counts', return_value={'accepted': 0, 'active': 0}):
                counts = assembly._active_counts()
                self.assertIn('registration_pending', counts)
                self.assertEqual(counts['registration_pending'], value)
                manager, _events = self.manager(counts=lambda: counts)
                self.assertFalse(manager._idle())

    def test_legacy_renewal_pending_is_counted_and_missing_is_unknown(self):
        import core.operations
        for value in (1, None, True, 'invalid'):
            concurrency = SimpleNamespace(release_runtime_status=lambda: {
                'pending': 0, 'inflight': 0, 'alive': False, 'registration_pending': 0,
                **({} if value is None else {'renewal_pending': value})})
            settlement = SimpleNamespace(active_counts=lambda: {
                name: 0 for name in assembly.SETTLEMENT_COUNT_KEYS})
            modules = {'core.operations.concurrency': concurrency,
                       'core.operations.settlement': settlement}
            with self.subTest(value=value), patch.dict('sys.modules', modules), patch.object(
                    core.operations, 'concurrency', concurrency, create=True), patch.object(
                    core.operations, 'settlement', settlement, create=True), patch.object(
                    assembly, '_business_counts', return_value={'accepted': 0, 'active': 0}):
                counts = assembly._active_counts()
                self.assertIn('legacy_renewal_pending', counts)
                self.assertEqual(counts['legacy_renewal_pending'], value)
                manager, _events = self.manager(counts=lambda: counts)
                self.assertFalse(manager._idle())

    def test_unverified_scan_pending_is_counted_and_missing_is_unknown(self):
        import core.operations
        for value in (1, None, True, 'invalid'):
            counts = {name: 0 for name in assembly.SETTLEMENT_COUNT_KEYS
                      if name != 'unverified_scan_pending'}
            if value is not None:
                counts['unverified_scan_pending'] = value
            concurrency = SimpleNamespace(release_runtime_status=lambda: {
                'pending': 0, 'inflight': 0, 'alive': False,
                'registration_pending': 0, 'renewal_pending': 0})
            settlement = SimpleNamespace(active_counts=lambda: counts)
            modules = {'core.operations.concurrency': concurrency,
                       'core.operations.settlement': settlement}
            with self.subTest(value=value), patch.dict('sys.modules', modules), patch.object(
                    core.operations, 'concurrency', concurrency, create=True), patch.object(
                    core.operations, 'settlement', settlement, create=True), patch.object(
                    assembly, '_business_counts', return_value={'accepted': 0, 'active': 0}):
                actual = assembly._active_counts()
                self.assertIn('unverified_scan_pending', actual)
                self.assertEqual(actual['unverified_scan_pending'], value)
                manager, _events = self.manager(counts=lambda: actual)
                self.assertFalse(manager._idle())

    def test_start_binding_passes_original_domain_without_querying_status(self):
        context = RuntimeContext('worker')
        domain = object()
        received = []
        modules = {
            'core.operations.settlement': SimpleNamespace(
                start_runtime=lambda **kwargs: received.append(kwargs) or True),
            'core.storage.operations.permits': SimpleNamespace(_settlement_domain=lambda: domain),
        }
        hooks = bindings.build_components(resolve=modules.__getitem__)
        hooks['settlement'].start(context)
        self.assertIs(received[0].get('domain'), domain)
        self.assertIs(received[0].get('admission'), context.admission)

    def test_unconfirmed_settlement_start_blocks_claimers(self):
        events = []
        modules = {
            'core.operations.settlement': SimpleNamespace(
                start_runtime=lambda **kwargs: False, drain_runtime=lambda deadline: True,
                stop_runtime=lambda deadline: True),
            'core.operations.concurrency': SimpleNamespace(stop_release_runtime=lambda deadline: True),
            'core.storage.operations.permits': SimpleNamespace(_settlement_domain=lambda: 'domain'),
        }
        hooks = {spec.name: ComponentHooks(
            lambda ctx, name=spec.name: events.append(name), lambda ctx, timeout: True)
                 for spec in COMPONENTS}
        hooks['settlement'] = bindings.build_components(resolve=modules.__getitem__)['settlement']
        owner = SimpleNamespace(start=lambda: None, require_owner=lambda: None,
            close=lambda timeout: True)
        controller = RuntimeController(RuntimeContext('worker'), hooks, owner=owner)
        with self.assertRaises(RuntimeStartError):
            controller.start()
        self.assertNotIn('operation_dispatcher', events)
        self.assertFalse(controller.context.admission.is_open())


if __name__ == '__main__':
    unittest.main()
