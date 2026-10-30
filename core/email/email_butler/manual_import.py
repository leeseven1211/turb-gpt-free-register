"""Explicit HME supply imports. Registration never invokes this service.

Preview reads remote stock only. Creation commits the exact candidate identities,
original read profile and permanent ownership before starting any handoff HTTP.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from core.email.email_butler import client as client
from core.storage import postgres as postgres_store, records as record_store
from core.email.email_butler import inventory_handoff as handoff
from core.storage.email import butler_manual_imports as store
from core.storage.email import local_imports as imports

logger = logging.getLogger('core.butler_manual_import')
_ITEM_STATES = ('pending', 'submitting', 'unknown', 'imported', 'skipped', 'failed')


class RemoteError(RuntimeError):
    """Safe remote failure for the HTTP boundary; never retains upstream text."""


def _uuid(value, label):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError('invalid_' + label) from None
    return value


def _config():
    from config import email as config
    base = str(getattr(config, 'EMAIL_BUTLER_API_BASE', '') or '').strip().rstrip('/')
    key = str(getattr(config, 'EMAIL_BUTLER_API_KEY', '') or '').strip()
    mailbox = str(getattr(config, 'ICLOUD_HME_FORWARD_IMAP_EMAIL', '') or '').strip().lower()
    try:
        parsed = urlsplit(base)
        valid = (parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and parsed.path.rstrip('/').endswith('/v1'))
    except ValueError:
        valid = False
    if not valid or not key or not imports._ADDRESS.fullmatch(mailbox):
        raise ValueError('butler_configuration_required')
    fingerprint = hashlib.sha256(json.dumps([base, key, mailbox]).encode()).hexdigest()
    return {'api_base': base, 'api_key': key, 'mailbox_email': mailbox, 'fingerprint': fingerprint}


def _request(method, path, connection, **kwargs):
    try:
        return client._request(method, path, api_base=connection['api_base'], api_key=connection['api_key'], **kwargs)
    except Exception:
        raise RemoteError('butler_remote_unavailable') from None


def _filters(data):
    if not isinstance(data, dict):
        raise ValueError('invalid_import_filters')
    provider = data.get('provider', 'icloud_hme')
    identity_type = data.get('identity_type', 'all')
    count = data.get('count')
    if provider != 'icloud_hme' or identity_type not in {'all', 'primary', 'plus_alias'}:
        raise ValueError('unsupported_import_type')
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 200:
        raise ValueError('invalid_import_count')
    result = {'provider': provider, 'identity_type': identity_type, 'count': count}
    for field in ('domain', 'group'):
        value = data.get(field)
        if value is not None and value != '':
            if not isinstance(value, str) or len(value) > 200 or any(ord(char) < 32 for char in value):
                raise ValueError('invalid_import_' + field)
            result[field] = value.strip().lower().lstrip('@') if field == 'domain' else value.strip()
    return result


def options():
    return {'ok': True, 'providers': [{'value': 'icloud_hme', 'label': 'iCloud 隐藏邮箱'}],
            'identity_types': [{'value': 'all', 'label': '全部'}, {'value': 'primary', 'label': '母邮箱'},
                               {'value': 'plus_alias', 'label': '子邮箱'}], 'max_count': 200,
            'domains': [], 'groups': []}


def preview(data):
    filters = _filters(data)
    connection = _config()
    who = _request('GET', '/me', connection)
    client_id = handoff.verify_client(who)
    parameters = {key: value for key, value in filters.items() if key != 'count'}
    result = _request('GET', '/mailboxes/import-candidates', connection, params={**parameters, 'limit': 5000})
    if result.get('supported') is not True or result.get('policy_applied') is not True or not isinstance(result.get('candidates'), list):
        raise RemoteError('butler_candidates_contract_unsupported')
    candidates, seen = [], set()
    try:
        for raw in result['candidates'][:5000]:
            item = handoff.validate_candidate(raw, mailbox=connection['mailbox_email'])
            if item['email'] in seen:
                continue
            seen.add(item['email'])
            if filters['identity_type'] == 'primary' and item['identity_type'] != 'primary':
                continue
            if filters['identity_type'] == 'plus_alias' and item['identity_type'] == 'primary':
                continue
            if filters.get('domain') and item['email'].partition('@')[2] != filters['domain'].lower():
                continue
            candidates.append(item)
    except (ValueError, KeyError, TypeError):
        raise RemoteError('butler_candidate_identity_mismatch') from None
    with record_store.transaction() as conn:
        occupied = store.conflicts([item['email'] for item in candidates], conn=conn)
        eligible = [item for item in candidates if item['email'] not in occupied]
        chosen = eligible[:filters['count']]
        token = str(uuid.uuid4())
        record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, {
            'preview_token': token, 'expires_at': datetime.now(timezone.utc) + timedelta(minutes=15),
            'filters': filters, 'candidates': chosen, 'config_fingerprint': connection['fingerprint'],
            'client_id': client_id,
        }, conn=conn)
    return {'ok': True, 'preview_token': token, 'available': len(eligible), 'selected': len(chosen),
            'count': filters['count'], 'items': [{'email': item['email'], 'identity_type': item['identity_type']}
                                              for item in chosen[:10]], 'filters': filters}


def create(data):
    if not isinstance(data, dict):
        raise ValueError('invalid_import_request')
    request_id = _uuid(data.get('request_id'), 'request_id')
    token = _uuid(data.get('preview_token'), 'preview_token')
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-import-request:' + request_id)
        previous = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_BATCHES, 'request_id', request_id, conn=conn)
        if previous:
            if previous['preview_token'] != token:
                raise ValueError('import_request_conflict: 原请求已用于其他预览')
            return _public(previous, conn=conn)
        snapshot = record_store.get_row_by(record_store.EMAIL_BUTLER_IMPORT_PREVIEWS, 'preview_token', token, conn=conn)
        if not snapshot:
            raise ValueError('import_preview_not_found: 预览不存在，请重新预览')
        expires = snapshot['expires_at']
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if expires <= datetime.now(timezone.utc):
            raise ValueError('import_preview_expired: 预览已过期，请重新预览')
        connection = _config()
        if snapshot['config_fingerprint'] != connection['fingerprint']:
            raise ValueError('import_snapshot_conflict: 连接已变化，请重新预览')
        candidates = snapshot['candidates']
        if not candidates:
            raise ValueError('import_preview_empty: 无可导入候选')
        for address in sorted(item['email'] for item in candidates):
            record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        occupied = store.conflicts([item['email'] for item in candidates], conn=conn)
        profile = imports._fixed_butler_profile(conn, _connection=connection)
        consumer_id = handoff._consumer_instance()
        batch_id = str(uuid.uuid4())
        row_id = record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, {
            'batch_id': batch_id, 'request_id': request_id, 'preview_token': token, 'status': 'running',
            'filters': snapshot['filters'], 'profile_id': profile['id'], 'client_id': snapshot['client_id'],
            'consumer_id': consumer_id, 'error_code': None,
        }, conn=conn)
        for position, item in enumerate(candidates):
            ownership = handoff.ownership_for_import(item['email'], connection['api_base'], snapshot['client_id'], consumer_id)
            record_store.insert_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, {
                'batch_id': batch_id, 'position': position, 'address_norm': item['email'],
                'acquisition_id': ownership['acquisition_id'], 'ownership': ownership, 'candidate': item,
                'status': 'skipped' if item['email'] in occupied else 'pending',
                'error_code': 'local_email_conflict' if item['email'] in occupied else None,
            }, conn=conn)
        row = record_store.get_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row_id, conn=conn)
        public = _public(row, conn=conn)
    _launch(batch_id)
    return public


def _public(row, *, conn=None):
    counts = {state: 0 for state in _ITEM_STATES}
    error_counts = {}
    for item in store.items(row['batch_id'], conn=conn):
        counts[item['status']] += 1
        code = item.get('error_code')
        if code:
            error_counts[code] = error_counts.get(code, 0) + 1
    return {'batch_id': row['batch_id'], 'request_id': row['request_id'], 'status': row['status'],
            'total': sum(counts.values()), 'requested': row['filters']['count'],
            **counts, 'counts': counts,
            'completed': counts['imported'] + counts['skipped'] + counts['failed'] + counts['unknown'],
            'can_retry': bool(counts['pending'] or counts['submitting'] or counts['unknown']),
            'error_counts': error_counts, 'error_code': row.get('error_code'),
            'created_at': row.get('created_at'), 'updated_at': row.get('updated_at')}


def get(batch_id):
    return _public(store.batch(_uuid(batch_id, 'batch_id')))


def retry(batch_id):
    row = store.batch(_uuid(batch_id, 'batch_id'))
    # The worker owns status changes under a database session lock. Merely
    # requesting a retry cannot race a live worker or replace its execution.
    public = _public(row)
    if public['can_retry']:
        _launch(batch_id)
    return public


def _launch(batch_id):
    threading.Thread(target=_run_batch, args=(batch_id,), name='butler-import-' + batch_id[:8], daemon=True).start()


def reconcile_interrupted():
    """启动时标记已中断批次，保留原地址供显式续跑，不发起远端交接。"""
    recovered = 0
    rows = record_store.list_rows(record_store.EMAIL_BUTLER_IMPORT_BATCHES, where='status = %s', params=('running',))
    for row in rows:
        lock_key = 'butler-manual-import:' + row['batch_id']
        with postgres_store.connect() as lock_conn:
            with lock_conn.cursor() as cur:
                cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0))', (lock_key,))
                acquired = cur.fetchone()[0]
            lock_conn.commit()
            if not acquired:
                continue
            try:
                current = store.batch(row['batch_id'])
                if current['status'] == 'running':
                    states = [item['status'] for item in store.items(row['batch_id'])]
                    complete = all(state in {'imported', 'skipped'} for state in states)
                    record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, current['id'],
                                           {'status': 'completed' if complete else 'partial',
                                            'error_code': None if complete else 'import_interrupted'})
                    recovered += 1
            finally:
                lock_conn.rollback()
                with lock_conn.cursor() as cur:
                    cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (lock_key,))
                lock_conn.commit()
    return recovered


def _patch_item(item_id, changes, *, conn=None):
    record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item_id, changes, conn=conn)


def _batch_error_code(error):
    """区分数据库、本地任务和固定远端连接异常，不把任意异常误报为配置失效。"""
    from psycopg import Error as PostgresError

    if isinstance(error, PostgresError):
        return 'import_storage_unavailable'
    if isinstance(error, RemoteError):
        return 'butler_remote_unavailable'
    code = str(getattr(error, 'code', '') or str(error).partition(':')[0])
    if code in {'fixed_route_unavailable', 'email_derivation_profile_unavailable'}:
        return 'fixed_route_unavailable'
    if code == 'handoff_contract_unsupported':
        return code
    return 'import_internal_error'


def _process_item(batch, item, profile):
    address = item['address_norm']
    # Commit submitting before any network. A crash from this point is an
    # uncertain original handoff, recovered only by explicit retry.
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        existing = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
        if existing and (existing.get('butler_handoff') or {}).get('acquisition_id') == item['acquisition_id']:
            _patch_item(item['id'], {'status': 'imported', 'pool_id': existing['id'], 'error_code': None}, conn=conn)
            return
        if store.conflicts([address], conn=conn, exclude_item_id=item['id']):
            _patch_item(item['id'], {'status': 'skipped' if item['status'] == 'pending' else 'unknown',
                                    'error_code': 'local_email_conflict'}, conn=conn)
            return
        _patch_item(item['id'], {'status': 'submitting', 'error_code': None}, conn=conn)
    try:
        with record_store.transaction() as conn:
            record_store.advisory_xact_lock(conn, 'registered-account:' + address)
            receipt = handoff.handoff_selected(item['candidate'], profile,
                ownership=item['ownership'], client_id=batch['client_id'])
            inserted, _ = imports.import_resources([item['candidate']], source='email_butler',
                _fixed_profile=profile, _handoffs={address: receipt}, _manual_item_id=item['id'], _conn=conn)
            if not inserted:
                raise ValueError('local_import_unconfirmed')
            row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
            _patch_item(item['id'], {'status': 'imported', 'pool_id': row['id'], 'error_code': None}, conn=conn)
    except Exception as exc:
        code = getattr(exc, 'status_code', None)
        definite = (item['status'] == 'pending' and isinstance(code, int)
                    and 400 <= code < 500 and code not in {408, 425, 429})
        _patch_item(item['id'], {'status': 'failed' if definite else 'unknown',
                                'error_code': 'handoff_rejected' if definite else 'handoff_unconfirmed'})


def _run_batch(batch_id):
    # Session ownership spans HTTP and each per-address transaction. Unlock
    # explicitly before returning the pooled connection to another caller.
    lock_key = 'butler-manual-import:' + batch_id
    with postgres_store.connect() as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0))', (lock_key,))
            acquired = cur.fetchone()[0]
        lock_conn.commit()
        if not acquired:
            return
        batch = None
        try:
            batch = store.batch(batch_id)
            remaining = [item for item in store.items(batch_id) if item['status'] in {'pending', 'submitting', 'unknown'}]
            if remaining:
                profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(batch['profile_id']))
                if not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
                    raise ValueError('fixed_route_unavailable')
                from core.email.derivation import _profile_credentials
                connection = _profile_credentials(profile)
                who = _request('GET', '/me', connection)
                handoff.verify_client(who, client_id=batch['client_id'])
                record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                                       {'status': 'running', 'error_code': None})
                # 批次锁与行级业务连接按 row_factory 分池；小业务池同步降低并发。
                workers = min(4, max(1, int(os.getenv('TURB_DB_POOL_MAX') or 12)))
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='butler-handoff') as executor:
                    futures = [executor.submit(_process_item, batch, item, profile) for item in remaining]
                    for future in futures:
                        future.result()
            states = [item['status'] for item in store.items(batch_id)]
            complete = all(state in {'imported', 'skipped'} for state in states)
            record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                                   {'status': 'completed' if complete else 'partial', 'error_code': None})
        except Exception as exc:
            error_code = _batch_error_code(exc)
            if batch:
                record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                                       {'status': 'partial', 'error_code': error_code})
            logger.warning('Butler 手动导入已暂停，原批次已保留：%s（%s）', error_code, type(exc).__name__)
        finally:
            lock_conn.rollback()
            with lock_conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (lock_key,))
            lock_conn.commit()
