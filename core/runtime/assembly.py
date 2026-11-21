"""Explicit Web/Worker composition root. Domain imports happen on installation."""
from __future__ import annotations

from dataclasses import asdict, replace
from importlib import import_module
import logging
from pathlib import Path
from threading import Lock
import time

from .bindings import build_components
from .bootstrap import RuntimeBootstrap
from .composition import ComponentHooks, RuntimeController
from .config_observer import create_config_observer
from .context import RuntimeContext
from .instance_owner import ExecutionOwner, OwnerError
from .managed import ManagedRuntime
from .finalizer import BoundedFinalizer
from .manifest import COMPONENTS
from .readiness import (compatibility_status, execution_ready, remote_status,
                        SETTLEMENT_COUNT_KEYS)

_PRODUCERS = ('deactivation_scanner', 'at_refresher', 'codex_refresher', 'sub2api_sync',
              'sub2api_monitor', 'c2a_monitor', 'auth_context_cleanup', 'task_retention',
              'registration_proxy_backfill')
_CLAIMERS = ('registration_dispatcher', 'operation_dispatcher', 'dependency_dispatcher',
             'butler_import_dispatcher')
_STOPS = {
 'proxy_pool': 'core.proxy.pool:stop',
 'projection_worker': 'core.operation_task_store:stop_projection_worker',
 'bulk_workers': 'core.bulk_operations.service:stop_workers',
 'sms_cancel_worker': 'core.sms.provider:stop_cancel_worker',
 'deactivation_scanner': 'core.accounts.deactivation.mail_scan:stop_periodic_scanner',
 'at_refresher': 'core.accounts.token_refresh:stop_periodic_refresher',
 'codex_refresher': 'core.codex.token_refresh_service:stop_periodic_refresher',
 'sub2api_sync': 'core.integrations.sub2api.jobs:stop_periodic_sync',
 'sub2api_monitor': 'core.integrations.sub2api.monitor:stop_periodic_monitor',
 'c2a_monitor': 'core.integrations.c2a.monitor:stop_periodic_monitor',
 'auth_context_cleanup': 'core.accounts.auth_context_cleanup:stop_periodic_cleanup',
 'task_retention': 'core.operations.retention:stop_periodic_cleanup',
 'registration_proxy_backfill': 'core.operations.reconciliation:stop_periodic_account_proxy_backfill',
 'email_usage_reports': 'core.email.email_butler.usage_reports:stop_worker',
 'email_service_sync': 'core.email.email_butler.service_facts:stop_worker',
}
_STATUS = {
 'settlement': 'core.operations.settlement:runtime_status',
 'proxy_pool': 'core.proxy.pool:worker_status',
 'projection_worker': 'core.operation_task_store:projection_worker_status',
 'registration_dispatcher': 'core.registration.service:dispatcher_status',
 'operation_dispatcher': 'core.operations.task_gateway:dispatcher_status',
 'dependency_dispatcher': 'core.operations.task_gateway:dependency_dispatcher_status',
 'bulk_workers': 'core.bulk_operations.service:worker_status',
 'butler_import_dispatcher': 'core.email.email_butler.manual_import:dispatcher_status',
 'sms_cancel_worker': 'core.sms.provider:cancel_worker_status',
 'deactivation_scanner': 'core.accounts.deactivation.mail_scan:scheduler_status',
 'at_refresher': 'core.accounts.token_refresh:scheduler_status',
 'codex_refresher': 'core.codex.token_refresh_service:scheduler_status',
 'sub2api_sync': 'core.integrations.sub2api.jobs:scheduler_status',
 'sub2api_monitor': 'core.integrations.sub2api.monitor:scheduler_status',
 'c2a_monitor': 'core.integrations.c2a.monitor:scheduler_status',
 'auth_context_cleanup': 'core.accounts.auth_context_cleanup:scheduler_status',
 'task_retention': 'core.operations.retention:scheduler_status',
 'registration_proxy_backfill': 'core.operations.reconciliation:account_proxy_backfill_status',
 'email_usage_reports': 'core.email.email_butler.usage_reports:worker_runtime_status',
 'email_service_sync': 'core.email.email_butler.service_facts:worker_runtime_status',
}


def _lookup(target):
    module, attr = target.split(':', 1)
    return getattr(import_module(module), attr)


class _HeartbeatBinding:
    """Allocate a durable generation only after the controller acquired owner."""
    def __init__(self, context, owner, bootstrap, collector):
        self.context, self.owner, self.bootstrap = context, owner, bootstrap
        self.collector = collector
        self.reporter = None
        self.generation = None
        self._pause_epoch = 0
        self._epoch_lock = Lock()

    def owner_pause_changed(self):
        with self._epoch_lock:
            self._pause_epoch += 1
        if self.reporter is not None:
            self.reporter.request_refresh()

    def start(self):
        from core.storage import postgres, runtime_workers
        from .worker_heartbeat import WorkerHeartbeat
        self.owner.require_owner()
        identity = asdict(self.owner.status().identity)
        identity.update(mode=self.context.mode.value, release=self.bootstrap.release)
        with postgres.connect() as conn:
            runtime_workers.ensure_tables(conn)
            self.owner.require_owner()
            self.generation = runtime_workers.begin_generation(self.bootstrap.instance_id,
                identity['nonce'], identity, conn=conn)
        def collect():
            with self._epoch_lock:
                epoch = self._pause_epoch
            return {**self.collector(), '_owner_pause_epoch': epoch}

        def write(status):
            with postgres.connect() as conn:
                # Pool checkout can outlive an ownership pause. Recheck here,
                # then use the same single writer and generation CAS as usual.
                try:
                    self.owner.require_owner()
                except OwnerError as exc:
                    if exc.code != 'owner_probe_paused':
                        raise
                    status = {**status, 'ready': False}
                with self._epoch_lock:
                    if status.get('_owner_pause_epoch') != self._pause_epoch:
                        status = {**status, 'ready': False}
                return runtime_workers.heartbeat(self.generation, status, conn=conn)
        self.reporter = WorkerHeartbeat(admission=self.context.admission,
            write_heartbeat=write, collect_status=collect)
        self.reporter.start()

    def stop(self, timeout=3.0):
        return True if self.reporter is None else self.reporter.stop(timeout=timeout)

    def status(self):
        return {'healthy': False, 'state': 'new'} if self.reporter is None else self.reporter.status()


class InstalledRuntime:
    def __init__(self, *, bootstrap, controller, observer, owner, manager, heartbeat):
        self.bootstrap, self.controller, self.observer = bootstrap, controller, observer
        self.owner, self.manager, self.heartbeat = owner, manager, heartbeat

    def start(self):
        if not self.controller.context.executes:
            self.observer.start()
        try:
            return self.manager.start()
        except BaseException:
            if not self.controller.context.executes:
                self.observer.stop(timeout=3.0)
            raise

    def stop(self, timeout=60.0):
        deadline = self.manager.stop_deadline(timeout)
        if not self.controller.context.executes and not self.observer.stop(
                timeout=max(0., deadline - time.monotonic())):
            return False
        return self.manager.stop(timeout=max(0.0, deadline - time.monotonic()))

    def finalize_incomplete(self, timeout=60.0):
        deadline = self.manager.finalization_deadline(timeout)
        if deadline is None:
            return self.manager.finalize_incomplete(timeout=0)
        if not self.controller.context.executes and not self.observer.stop(
                timeout=max(0., deadline - time.monotonic())):
            return False
        return self.manager.finalize_incomplete(
            timeout=max(0., deadline - time.monotonic()))

    def component_status(self):
        result = {}
        for name, target in _STATUS.items():
            try:
                result[name] = _lookup(target)()
            except Exception:
                result[name] = {'error_code': 'component_error'}
        result['config_observer'] = self.observer.status()
        from core.operations import executor
        from core.registration import service
        result['account_executor'] = executor.executor.runtime_status()
        result['extract_executor'] = executor.extract_executor.runtime_status()
        result['registration_executor'] = service.registration_executor_status()
        return result

    def collect_worker_status(self):
        components = self.component_status()
        context = self.controller.context
        # The reporter must be able to repair its own admission reason. Its
        # current failure is represented by the durable heartbeat's freshness.
        other_reasons = set(context.admission.reasons()) - {'heartbeat'}
        state = self.manager.status()['state']
        ready = execution_ready(state=state, admission_open=not other_reasons,
            owner_valid=self.controller.execution_owner_valid(), components=components)
        config = components['config_observer']
        return {'state': state, 'ready': ready, 'components': components,
                'applied_db_revision': config.get('applied_db_revision'),
                'local_snapshot_revision': config.get('local_snapshot_revision'),
                'counts': _active_counts()}

    def status(self):
        if not self.controller.context.executes:
            from core.storage import runtime_config, runtime_workers
            record = runtime_workers.read_worker(self.bootstrap.instance_id)
            result = remote_status(record, expected_release=self.bootstrap.release,
                                   required_db_revision=runtime_config.current_revision())
            web_config = self.observer.status()
            result['web_config_observer'] = web_config
            if web_config.get('alive') is not True or web_config.get('state') != 'applied':
                result.update(ready=False, error='web_config_not_ready')
            return result
        values = self.collect_worker_status()
        ready = values['ready'] and self.heartbeat.status().get('healthy') is True
        identity = asdict(self.owner.status().identity) if self.owner.status().identity else {}
        result = compatibility_status(mode=self.bootstrap.mode, source='local_worker',
            ready=ready, state=values['state'], identity=identity,
            components=values['components'], config=values['components']['config_observer'],
            counts=values['counts'],
            error_code=None if ready else 'runtime_not_ready')
        result['heartbeat'] = self.heartbeat.status()
        return result


def _active_counts(*, draining=False):
    from core.operations import concurrency, settlement
    result = _business_counts()
    counts = settlement.drain_counts() if draining else settlement.active_counts()
    # Missing, bool or malformed facts remain unknown and prevent clean drain.
    result.update({name: counts.get(name) for name in SETTLEMENT_COUNT_KEYS})
    release_status = concurrency.release_runtime_status()
    result.update(legacy_release_pending=release_status.get('pending'),
                  legacy_release_inflight=release_status.get('inflight'),
                  legacy_renewal_pending=release_status.get('renewal_pending'),
                  registration_pending=release_status.get('registration_pending'))
    if draining:
        result['active_admissions'] = concurrency.active_admissions()
    return result


def _idle_for_owner_retry(context):
    from core.bulk_operations import service as bulk
    from core.operations import concurrency, settlement
    from core.registration import service

    # Keep unrelated admission reasons in force. A setup or shutdown in progress
    # cannot enter the retry path. The dedicated probe and watchdog stay separate.
    if {'startup', 'startup_failed', 'draining', 'owner_lost'}.intersection(
            context.admission.reasons()):
        return False
    business_counts = _business_counts()
    pending_dispatch = service.dispatcher_status().get('in_flight')
    return (all(type(value) is int and value == 0 for value in business_counts.values())
            and type(pending_dispatch) is int and pending_dispatch == 0
            and bulk.idle_for_owner_retry()
            and concurrency.idle_for_owner_retry()
            and settlement.idle_for_owner_retry())


def _business_counts():
    from core.operations import executor
    from core.registration import service
    from core.email.email_butler import manual_import
    statuses = (executor.executor.runtime_status(), executor.extract_executor.runtime_status(),
                service.registration_executor_status())
    butler = manual_import.dispatcher_status()
    return {'accepted': sum(item['accepted'] for item in statuses),
            'active': sum(item['active'] for item in statuses),
            'active_batches': butler['active_batches'],
            'pending_owner_releases': butler['pending_owner_releases']}


def _close_executors(timeout):
    from core.operations import executor
    from core.registration import service
    deadline = time.monotonic() + max(0., timeout)
    counts = _business_counts()
    if not counts or any(not isinstance(value, int) or isinstance(value, bool) or value != 0
                         for value in counts.values()):
        return False
    # shutdown(False) revokes queueing without an unbounded join. The executor
    # still owns its thread handles; the following join checks the real threads.
    return all(pool.close_runtime(max(0., deadline - time.monotonic()))
               for pool in (executor.executor, executor.extract_executor)
               ) and service.close_runtime_executor(max(0., deadline - time.monotonic()))


def install(bootstrap: RuntimeBootstrap, *, logger=None):
    """Install once before Flask routes or Worker execution can be entered."""
    from .process import install_runtime, install_lifecycle
    from core.storage import postgres
    from core.sms import provider
    from core.maintenance import sentinel
    context = RuntimeContext(bootstrap.mode, logger or logging.getLogger('core.runtime'))
    provider.configure_cancel_queue_path(bootstrap.runtime_dir / 'sms_cancel_queue.json')
    sentinel.configure_cache_directory(
        Path(__file__).resolve().parents[2] / 'run' / 'sentinel-candidates'
        if bootstrap.legacy_paths else bootstrap.runtime_dir / 'sentinel-candidates')
    observer = create_config_observer(context)

    def pause():
        context.admission.block('owner_probe_paused')
        heartbeat.owner_pause_changed()

    def resume():
        context.admission.unblock('owner_probe_paused')
        heartbeat.owner_pause_changed()

    pause_hooks = dict(
        probe_timeout=30.0,
        on_pause=pause,
        can_resume=lambda: _idle_for_owner_retry(context),
        on_resume=resume,
    ) if bootstrap.mode == 'worker' else {}
    owner = ExecutionOwner(mode=bootstrap.mode, instance_id=bootstrap.instance_id,
        schema=postgres.schema_name(), stable_dir=bootstrap.runtime_dir,
        connect_dedicated=postgres.connect_dedicated,
        on_lost=lambda: context.admission.block('owner_lost'), **pause_hooks) if context.executes else None
    components = build_components()
    for name, target in _STOPS.items():
        original = components[name]
        components[name] = replace(original, stop=lambda _ctx, budget, t=target: _lookup(t)(timeout=budget))
    components['config_observer'] = ComponentHooks(lambda _ctx: observer.start(),
                                                   lambda _ctx, budget: observer.stop(timeout=budget))
    components['butler_import_dispatcher'] = ComponentHooks(
        lambda _ctx: _lookup('core.email.email_butler.manual_import:start_dispatcher')(),
        lambda _ctx, budget: _lookup('core.email.email_butler.manual_import:stop_dispatcher')(timeout=budget))
    controller = RuntimeController(context, components, owner=owner)
    installed = None
    heartbeat = _HeartbeatBinding(context, owner, bootstrap,
                                   lambda: installed.collect_worker_status()) if context.executes else None
    from core.storage import compat_export
    def settle():
        if context.executes:
            from core.storage.operations import projection
            from core.bulk_operations import service as bulk
            while projection.run_projection_once() is not None:
                pass
            while bulk.run_once('project'):
                pass
        return True
    def finalize():
        return compat_export.finish_runtime(timeout=60.0)
    def close_connections():
        postgres.close_pools()
        return True
    manager = ManagedRuntime(controller=controller, heartbeat=heartbeat,
        producer_names=_PRODUCERS if context.executes else (),
        claim_names=_CLAIMERS if context.executes else (),
        active_counts=(lambda: _active_counts(draining=True)) if context.executes else lambda: {'accepted': 0},
        settle=BoundedFinalizer(settle),
        flush=BoundedFinalizer(finalize),
        close_connections=BoundedFinalizer(close_connections),
        settlement=import_module('core.operations.settlement') if context.executes else None,
        settlement_component='settlement' if context.executes else None,
        close_releases=(lambda deadline: import_module(
            'core.operations.concurrency').stop_release_runtime(deadline))
            if context.executes else None,
        close_executors=_close_executors if context.executes else lambda _budget: True)
    installed = InstalledRuntime(bootstrap=bootstrap, controller=controller, observer=observer,
                                  owner=owner, manager=manager, heartbeat=heartbeat)
    install_runtime(controller)
    install_lifecycle(installed)
    # Actions must exist even after a Web-only restart, before that process has
    # submitted any task. Domain execution registration remains Worker-owned.
    from .actions import register_actions
    register_actions()
    return installed
