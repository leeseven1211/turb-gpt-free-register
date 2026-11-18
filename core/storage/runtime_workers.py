"""Nonsecret durable Worker status; reads never bootstrap or reclaim resources.

The composition root must hold and verify ExecutionOwner before begin_generation.
A generation receipt is a fencing token for status writes, never a business lease.
"""
from __future__ import annotations

import json
import math
import re
from contextlib import contextmanager
from dataclasses import dataclass
from collections.abc import Mapping

from psycopg.rows import dict_row
from core.storage import postgres as postgres_store

_INSTANCE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
_NONCE = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
COMPONENT_NAMES = frozenset({
    'settlement',
    'operation_storage', 'bulk_storage', 'recover_before_handlers', 'proxy_pool',
    'maintenance_handlers', 'account_handlers', 'codex_retry_handler', 'codex_refresh_handler',
    'sentinel_handler', 'sub2api_monitor_handler', 'sub2api_upload_handler', 'c2a_sync_handler',
    'verify_handlers', 'recover_before_dispatchers', 'projection_worker',
    'registration_dispatcher', 'operation_dispatcher', 'dependency_handler',
    'dependency_dispatcher', 'bulk_workers', 'recover_ready_dependencies',
    'recover_local_artifacts', 'sms_cancel_worker', 'recover_account_background_state',
    'deactivation_scanner', 'at_refresher', 'codex_refresher', 'sub2api_sync',
    'sub2api_monitor', 'auth_context_cleanup', 'task_retention', 'email_usage_reports',
    'email_service_sync', 'config_observer', 'account_executor', 'extract_executor',
    'registration_executor', 'butler_import_dispatcher',
})
SETTLEMENT_COUNT_NAMES = frozenset({'settlement_pending', 'resource_pending', 'permit_pending',
    'compensation_inflight', 'unpersisted', 'callback_active', 'registered',
    'unverified_scan_pending'})
COUNT_NAMES = frozenset({'accepted', 'active', 'active_batches', 'pending_owner_releases',
                        'legacy_release_pending', 'legacy_release_inflight',
                        'legacy_renewal_pending',
                        'registration_pending',
                        *SETTLEMENT_COUNT_NAMES})
_BOOL_FIELDS = frozenset({'started', 'alive', 'healthy', 'running', 'idle', 'disabled', 'stopping',
                          'thread_alive'})
_STATES = frozenset({'unknown', 'new', 'starting', 'running', 'ready', 'applied', 'pending',
                     'idle', 'disabled', 'degraded', 'error', 'failed', 'start_failed',
                     'draining', 'stopping', 'stopped', 'stop_incomplete', 'fenced', 'held', 'lost'})
_ERROR_CODES = frozenset({'component_error', 'config_read_failed', 'config_apply_failed',
    'config_timeout', 'config_inactive', 'config_revision_regressed', 'config_invalid_revision',
    'config_observer_interrupted', 'config_thread_dead', 'config_start_failed',
    'heartbeat_write_failed', 'heartbeat_collect_failed', 'heartbeat_timeout',
    'heartbeat_fenced', 'heartbeat_thread_dead', 'heartbeat_interrupted',
    'heartbeat_start_failed', 'runtime_not_ready', 'owner_lost',
    'operation_settlement_pending', 'operation_settlement_conflict', 'operation_settlement_fenced',
    'settlement_storage_unavailable', 'settlement_storage_permission_denied',
    'settlement_storage_authentication_failed', 'settlement_storage_sqlstate_unknown',
    'settlement_carrier_unavailable', 'settlement_permit_unconfirmed'})


class RuntimeWorkerStoreError(RuntimeError):
    """Stable public failure without DSN, exception text or original payload."""


@dataclass(frozen=True)
class WorkerGeneration:
    instance_id: str
    owner_nonce: str
    generation: int

    def __post_init__(self):
        _identifiers(self.instance_id, self.owner_nonce)
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError('runtime_worker_invalid_generation')


def _identifiers(instance_id, owner_nonce=None):
    if not isinstance(instance_id, str) or not _INSTANCE.fullmatch(instance_id):
        raise ValueError('runtime_worker_invalid_identity')
    if owner_nonce is not None and (not isinstance(owner_nonce, str) or not _NONCE.fullmatch(owner_nonce)):
        raise ValueError('runtime_worker_invalid_identity')


def _nonnegative(value):
    if type(value) is not int or value < 0 or value > 2**63 - 1:
        raise ValueError('runtime_worker_invalid_status')
    return value


def _error_code(value):
    if value in (None, ''):
        return None
    return value if isinstance(value, str) and value in _ERROR_CODES else 'component_error'


def normalize_status(value: Mapping) -> dict:
    """Project a bounded status schema; arbitrary nested data never reaches SQL."""
    if not isinstance(value, Mapping):
        raise ValueError('runtime_worker_invalid_status')
    state = value.get('state', 'unknown')
    result = {'state': state if isinstance(state, str) and state in _STATES else 'unknown',
              'ready': value.get('ready') is True,
              'applied_db_revision': None, 'local_snapshot_revision': None,
              'components': {}, 'counts': {}}
    for name in ('applied_db_revision', 'local_snapshot_revision'):
        if value.get(name) is not None:
            result[name] = _nonnegative(value[name])
    if 'error_code' in value:
        result['error_code'] = _error_code(value['error_code'])
    components = value.get('components', {})
    counts = value.get('counts', {})
    if not isinstance(components, Mapping) or not isinstance(counts, Mapping):
        raise ValueError('runtime_worker_invalid_status')
    for name in COMPONENT_NAMES:
        if name not in components:
            continue
        source = components[name]
        if not isinstance(source, Mapping):
            raise ValueError('runtime_worker_invalid_status')
        component = {}
        for key in _BOOL_FIELDS:
            if key in source:
                if type(source[key]) is not bool:
                    raise ValueError('runtime_worker_invalid_status')
                component[key] = source[key]
        for key in COUNT_NAMES:
            if key in source:
                component[key] = _nonnegative(source[key])
        if 'state' in source:
            state = source['state']
            component['state'] = state if isinstance(state, str) and state in _STATES else 'unknown'
        if 'error_code' in source:
            component['error_code'] = _error_code(source['error_code'])
        if name == 'settlement':
            if 'cleanup_scan_error_code' in source:
                component['cleanup_scan_error_code'] = _error_code(source['cleanup_scan_error_code'])
            if 'oldest_age_seconds' in source:
                age = source['oldest_age_seconds']
                if (type(age) not in (int, float) or not math.isfinite(age)
                        or not 0 <= age <= 2**63 - 1):
                    raise ValueError('runtime_worker_invalid_status')
                component['oldest_age_seconds'] = age
            for field, names in (('counts', SETTLEMENT_COUNT_NAMES),
                                 ('stages', ('callback', 'resources', 'settlement', 'permit'))):
                if field in source:
                    values = source[field]
                    if not isinstance(values, Mapping):
                        raise ValueError('runtime_worker_invalid_status')
                    component[field] = {key: _nonnegative(values[key]) for key in names
                                        if key in values}
        result['components'][name] = component
    for name in COUNT_NAMES:
        if name in counts:
            result['counts'][name] = _nonnegative(counts[name])
    return result


def _identity(identity, owner_nonce):
    if not isinstance(identity, Mapping):
        raise ValueError('runtime_worker_invalid_identity')
    result = {}
    for key, limit in (('host', 255), ('process_start', 128), ('release', 128)):
        value = identity.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
            raise ValueError('runtime_worker_invalid_identity')
        result[key] = value
    pid = identity.get('pid')
    if type(pid) is not int or not 0 < pid < 2**63:
        raise ValueError('runtime_worker_invalid_identity')
    mode = identity.get('mode')
    if mode not in {'worker', 'combined'} or identity.get('nonce', owner_nonce) != owner_nonce:
        raise ValueError('runtime_worker_invalid_identity')
    result.update(pid=pid, mode=mode)
    return result


@contextmanager
def _connection(conn=None):
    try:
        if conn is not None:
            yield conn
        else:
            with postgres_store.connect() as current:
                yield current
    except Exception:
        raise RuntimeWorkerStoreError('runtime_worker_database_unavailable') from None


def ensure_tables(conn) -> None:
    """Call only from explicit Worker bootstrap while owner is held."""
    if conn.autocommit:
        raise ValueError('runtime_worker_transaction_required')
    postgres_store._guard_production_schema()
    with _connection(conn) as current, current.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS {postgres_store.quote_identifier(postgres_store.schema_name())}')
        cur.execute(f'''CREATE TABLE IF NOT EXISTS {postgres_store.qualified('runtime_workers')} (
            instance_id TEXT PRIMARY KEY,
            owner_nonce TEXT NOT NULL,
            generation BIGINT NOT NULL CHECK (generation > 0),
            host TEXT NOT NULL, pid BIGINT NOT NULL, process_start TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('worker', 'combined')), release TEXT NOT NULL,
            heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            status JSONB NOT NULL
        )''')


def begin_generation(instance_id: str, owner_nonce: str, identity: Mapping, *, conn=None) -> WorkerGeneration:
    """Owner-verified bootstrap only; same-nonce retries retain their generation."""
    _identifiers(instance_id, owner_nonce)
    safe = _identity(identity, owner_nonce)
    initial = json.dumps(normalize_status({'state': 'starting'}))
    with _connection(conn) as current, current.cursor(row_factory=dict_row) as cur:
        cur.execute(f'''INSERT INTO {postgres_store.qualified('runtime_workers')} AS worker
            (instance_id, owner_nonce, generation, host, pid, process_start, mode, release, heartbeat_at, status)
            VALUES (%s, %s, 1, %s, %s, %s, %s, %s, clock_timestamp(), %s::jsonb)
            ON CONFLICT (instance_id) DO UPDATE SET
                generation = CASE WHEN worker.owner_nonce = EXCLUDED.owner_nonce
                                  THEN worker.generation ELSE worker.generation + 1 END,
                owner_nonce = EXCLUDED.owner_nonce, host = EXCLUDED.host, pid = EXCLUDED.pid,
                process_start = EXCLUDED.process_start, mode = EXCLUDED.mode, release = EXCLUDED.release,
                heartbeat_at = clock_timestamp(), status = EXCLUDED.status
            RETURNING generation''',
            (instance_id, owner_nonce, safe['host'], safe['pid'], safe['process_start'],
             safe['mode'], safe['release'], initial))
        generation = int(cur.fetchone()['generation'])
    return WorkerGeneration(instance_id, owner_nonce, generation)


def heartbeat(generation: WorkerGeneration, status: Mapping, *, conn=None) -> bool:
    """CAS update only. False means fenced/absent; callers must not begin again."""
    if not isinstance(generation, WorkerGeneration):
        raise ValueError('runtime_worker_invalid_generation')
    payload = json.dumps(normalize_status(status), separators=(',', ':'))
    with _connection(conn) as current, current.cursor(row_factory=dict_row) as cur:
        cur.execute(f'''UPDATE {postgres_store.qualified('runtime_workers')}
            SET heartbeat_at = clock_timestamp(), status = %s::jsonb
            WHERE instance_id = %s AND owner_nonce = %s AND generation = %s
            RETURNING generation''',
            (payload, generation.instance_id, generation.owner_nonce, generation.generation))
        return cur.fetchone() is not None


def _absent(instance_id, server_epoch):
    return {'instance_id': instance_id, 'state': 'absent', 'present': False,
            'fresh': False, 'ready': False, 'server_epoch': float(server_epoch),
            'heartbeat_epoch': None, 'age_seconds': None}


def read_worker(instance_id: str, *, conn=None, max_age: float = 20.0) -> dict:
    """Readiness is freshness plus assembly truth; no local wall clock is used."""
    _identifiers(instance_id)
    if not math.isfinite(max_age) or max_age <= 0:
        raise ValueError('runtime_worker_invalid_budget')
    table = postgres_store.qualified('runtime_workers')
    with _connection(conn) as current, current.cursor(row_factory=dict_row) as cur:
        cur.execute('SELECT to_regclass(%s) AS relation, EXTRACT(EPOCH FROM clock_timestamp()) AS server_epoch', (table,))
        probe = cur.fetchone()
        if probe['relation'] is None:
            return _absent(instance_id, probe['server_epoch'])
        cur.execute(f'''SELECT instance_id, owner_nonce, generation, host, pid, process_start, mode, release,
            status, EXTRACT(EPOCH FROM heartbeat_at) AS heartbeat_epoch,
            EXTRACT(EPOCH FROM clock_timestamp()) AS server_epoch
            FROM {table} WHERE instance_id = %s''', (instance_id,))
        row = cur.fetchone()
    if row is None:
        return _absent(instance_id, probe['server_epoch'])
    safe = normalize_status(row['status'])
    observed, heartbeat_at = float(row['server_epoch']), float(row['heartbeat_epoch'])
    age = observed - heartbeat_at
    fresh = math.isfinite(age) and 0 <= age < max_age
    result = {key: row[key] for key in ('instance_id', 'owner_nonce', 'generation', 'host', 'pid',
                                       'process_start', 'mode', 'release')}
    result.update(safe)
    result.update(present=True, fresh=fresh, reported_ready=safe['ready'],
                  ready=fresh and safe['ready'] and safe['state'] == 'running',
                  heartbeat_epoch=heartbeat_at, server_epoch=observed, age_seconds=age)
    return result
