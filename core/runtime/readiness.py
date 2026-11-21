"""Strict component readiness and a sanitized compatibility projection."""
from __future__ import annotations

REQUIRED_COMPONENTS = (
    'settlement',
    'registration_dispatcher', 'operation_dispatcher', 'dependency_dispatcher',
    'projection_worker', 'bulk_workers', 'butler_import_dispatcher',
    'config_observer', 'deactivation_scanner', 'at_refresher', 'codex_refresher',
    'sub2api_sync', 'sub2api_monitor', 'c2a_monitor', 'auth_context_cleanup', 'task_retention',
)

SETTLEMENT_COUNT_KEYS = (
    'settlement_pending', 'resource_pending', 'permit_pending',
    'compensation_inflight', 'unpersisted', 'callback_active', 'registered',
    'unverified_scan_pending',
)
COUNT_KEYS = ('accepted', 'active', 'active_batches', 'pending_owner_releases',
              'legacy_release_pending', 'legacy_release_inflight',
              'legacy_renewal_pending',
              'registration_pending',
              *SETTLEMENT_COUNT_KEYS)


def sanitized_counts(values: object) -> dict:
    """A status projection never exports arbitrary labels or private values."""
    if not isinstance(values, dict):
        return {}
    return {name: values[name] for name in COUNT_KEYS if name in values
            and isinstance(values[name], int) and not isinstance(values[name], bool)
            and values[name] >= 0}


def component_ready(name: str, status: object) -> bool:
    if not isinstance(status, dict):
        return False
    if status.get('error_code') or status.get('error'):
        return False
    if name == 'config_observer':
        return status.get('alive') is True and status.get('state') == 'applied'
    if name == 'settlement':
        return (status.get('started') is True and status.get('alive') is True
                and status.get('healthy') is True and status.get('stopping') is not True)
    if status.get('stopping') is True:
        return False
    return status.get('started') is True and (
        status.get('alive') is True or status.get('healthy') is True)


def execution_ready(*, state: str, admission_open: bool, owner_valid: bool,
                    components: dict) -> bool:
    return bool(state == 'running' and admission_open and owner_valid and all(
        component_ready(name, components.get(name)) for name in REQUIRED_COMPONENTS))


def compatibility_status(*, mode: str, source: str, ready: bool, state: str,
                         identity: dict, components: dict, config: dict,
                         counts: dict | None = None,
                         error_code: str | None = None) -> dict:
    """Keep the current health-route component keys while exposing their source."""
    result = {
        'mode': mode, 'source': source, 'ready': bool(ready),
        'started': state in {'running', 'draining', 'stopping', 'stop_incomplete'},
        'state': state, 'pid': identity.get('pid'), 'worker_identity': identity,
        'executor': components.get('account_executor'),
        'codex_dispatcher': components.get('operation_dispatcher'),
        'registration_dispatcher': components.get('registration_dispatcher'),
        'dependency_dispatcher': components.get('dependency_dispatcher'),
        'projection_worker': components.get('projection_worker'),
        'bulk_operations': components.get('bulk_workers'),
        'settlement': components.get('settlement'),
        'counts': sanitized_counts(counts),
        'components': components, 'config_observer': config,
    }
    if error_code:
        result['error'] = error_code
    return result


def remote_status(record: dict, *, expected_release: str, required_db_revision: int) -> dict:
    """Heartbeat age is measured by PostgreSQL; staleness never frees a lease."""
    payload = record
    identity = {key: record.get(key) for key in ('host', 'pid', 'process_start', 'mode')}
    identity.update(nonce=record.get('owner_nonce'))
    components = payload.get('components') if isinstance(payload.get('components'), dict) else {}
    config = {key: record.get(key) for key in ('applied_db_revision', 'local_snapshot_revision')}
    applied = config.get('applied_db_revision')
    revisions_match = isinstance(applied, int) and not isinstance(applied, bool) and applied >= required_db_revision
    release_matches = record.get('release') == expected_release
    ready = bool(record.get('ready') is True and release_matches and revisions_match
                 and record.get('owner_nonce') and record.get('generation')
                 and all(component_ready(name, components.get(name)) for name in REQUIRED_COMPONENTS))
    result = compatibility_status(mode='web', source='postgres_worker', ready=ready,
        state=str(payload.get('state') or 'absent'), identity=identity,
        components=components, config=config,
        counts=payload.get('counts'),
        error_code=None if ready else ('worker_release_mismatch' if not release_matches else
                                      'worker_config_pending' if not revisions_match else 'worker_not_ready'))
    result.update(worker_generation=record.get('generation'),
                  worker_age_seconds=record.get('age_seconds'))
    return result
