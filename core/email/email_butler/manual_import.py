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
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from core.email.email_butler import client as client
from core.storage import postgres as postgres_store, records as record_store
from core.email.email_butler import inventory_handoff as handoff
from core.storage.email import butler_manual_imports as store
from core.storage.email import local_imports as imports
from core.operations import concurrency
from core.storage.operations.permits import current_owner

logger = logging.getLogger('core.butler_manual_import')
_ITEM_STATES = ('pending', 'submitting', 'unknown', 'imported', 'skipped', 'failed')
_FINISHED_BATCH_EXECUTIONS: set[str] = set()
_HANDOFF_BATCH_SIZE = 25


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
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
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
                               {'value': 'plus_alias', 'label': '子邮箱'}], 'max_count': None,
            'domains': [], 'groups': []}


def preview(data):
    filters = _filters(data)
    connection = _config()
    who = _request('GET', '/me', connection)
    client_id = handoff.verify_client(who)
    parameters = {key: value for key, value in filters.items() if key != 'count'}
    result = _request('GET', '/mailboxes/import-candidates', connection, params={**parameters, 'limit': 0})
    if result.get('supported') is not True or result.get('policy_applied') is not True or not isinstance(result.get('candidates'), list):
        raise RemoteError('butler_candidates_contract_unsupported')
    candidates, seen = [], set()
    try:
        for raw in result['candidates']:
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
            'blocked_by': list(row.get('concurrency_blocked_by') or []),
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
        if _batch_owner_active(row):
            continue
        with concurrency.admission_transaction() as conn:
            record_store.advisory_xact_lock(conn, 'butler-manual-import:' + row['batch_id'])
            current = store.batch(row['batch_id'], conn=conn)
            active = concurrency.active_execution_keys(prefix=f"butler-import:{row['batch_id']}:", conn=conn)
            if (active or current.get('worker_execution_id') != row.get('worker_execution_id')
                    or current['status'] != 'running'):
                continue
            states = [item['status'] for item in store.items(row['batch_id'], conn=conn)]
            complete = all(state in {'imported', 'skipped'} for state in states)
            record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, current['id'],
                                   {'status': 'completed' if complete else 'partial',
                                    'worker_owner': None, 'worker_execution_id': None,
                                    'error_code': None if complete else 'import_interrupted'}, conn=conn)
            recovered += 1
    return recovered


def _batch_owner_active(batch):
    execution_id = str(batch.get('worker_execution_id') or '')
    if execution_id in _FINISHED_BATCH_EXECUTIONS:
        return False
    owner = batch.get('worker_owner')
    return bool(owner and concurrency.owner_liveness(owner) != 'exited')


def _claim_batch_owner(batch_id):
    """短事务固定协调者身份，等待业务许可时不借用数据库连接。"""
    previous = store.batch(batch_id)
    if _batch_owner_active(previous):
        return None
    owner = {**current_owner(), 'thread_id': threading.get_ident()}
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-manual-import:' + batch_id)
        batch = store.batch(batch_id, conn=conn)
        if batch.get('worker_execution_id') != previous.get('worker_execution_id'):
            return None
        execution_id = uuid.uuid4().hex
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                               {'worker_owner': owner, 'worker_execution_id': execution_id}, conn=conn)
        batch.update(worker_owner=owner, worker_execution_id=execution_id)
        return batch


def _release_batch_owner(batch):
    execution_id = str(batch['worker_execution_id'])
    _FINISHED_BATCH_EXECUTIONS.add(execution_id)

    def release():
        with record_store.transaction() as conn:
            record_store.advisory_xact_lock(conn, 'butler-manual-import:' + batch['batch_id'])
            record_store.claim_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                changes={'worker_owner': None, 'worker_execution_id': None},
                guard="data->>'worker_execution_id' = %s", guard_params=(execution_id,), conn=conn)

    try:
        release()
        _FINISHED_BATCH_EXECUTIONS.discard(execution_id)
    except Exception:
        def retry_release():
            while True:
                try:
                    release()
                    _FINISHED_BATCH_EXECUTIONS.discard(execution_id)
                    return
                except Exception:
                    threading.Event().wait(1)

        threading.Thread(target=retry_release, name='butler-owner-release', daemon=True).start()


def _patch_item(item_id, changes, *, conn=None):
    record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_ITEMS, item_id, changes, conn=conn)


def _batch_error_code(error):
    """区分数据库、本地任务和固定远端连接异常，不把任意异常误报为配置失效。"""
    from psycopg import Error as PostgresError

    if isinstance(error, PostgresError):
        return 'import_storage_unavailable'
    if isinstance(error, concurrency.ConcurrencyStoreUnavailable):
        return 'scheduler_store_unavailable'
    if isinstance(error, concurrency.ConcurrencyPolicyError):
        return error.code
    if isinstance(error, RemoteError):
        return 'butler_remote_unavailable'
    code = str(getattr(error, 'code', '') or str(error).partition(':')[0])
    if code in {'fixed_route_unavailable', 'email_derivation_profile_unavailable'}:
        return 'fixed_route_unavailable'
    if code == 'handoff_contract_unsupported':
        return code
    return 'import_internal_error'


def _prepare_item(item, *, conn=None):
    """先持久化原交接意图，远端等待期间不占用业务连接。"""
    address = item['address_norm']
    with (nullcontext(conn) if conn is not None else record_store.transaction()) as conn:
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        existing = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
        if existing and (existing.get('butler_handoff') or {}).get('acquisition_id') == item['acquisition_id']:
            _patch_item(item['id'], {'status': 'imported', 'pool_id': existing['id'], 'error_code': None}, conn=conn)
            return False
        if store.conflicts([address], conn=conn, exclude_item_id=item['id']):
            _patch_item(item['id'], {'status': 'skipped' if item['status'] == 'pending' else 'unknown',
                                    'error_code': 'local_email_conflict'}, conn=conn)
            return False
        _patch_item(item['id'], {'status': 'submitting', 'error_code': None}, conn=conn)
    return True


def _finish_item(item, profile, receipt):
    """远端已确认后重新锁定地址，原子保存本地库存与进度。"""
    address = item['address_norm']
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'registered-account:' + address)
        existing = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
        if existing and (existing.get('butler_handoff') or {}).get('acquisition_id') == item['acquisition_id']:
            _patch_item(item['id'], {'status': 'imported', 'pool_id': existing['id'], 'error_code': None}, conn=conn)
            return
        if store.conflicts([address], conn=conn, exclude_item_id=item['id']):
            _patch_item(item['id'], {'status': 'unknown', 'error_code': 'local_email_conflict'}, conn=conn)
            return
        inserted, _ = imports.import_resources([item['candidate']], source='email_butler',
            _fixed_profile=profile, _handoffs={address: receipt}, _manual_item_id=item['id'], _conn=conn)
        if not inserted:
            raise ValueError('local_import_unconfirmed')
        row = record_store.get_row_by(record_store.EMAIL_BUTLER_POOL, 'email', address, conn=conn)
        _patch_item(item['id'], {'status': 'imported', 'pool_id': row['id'], 'error_code': None}, conn=conn)


def _record_item_error(item, error_code, *, rejected=False):
    # 旧交接结果尚未确认时，后续拒绝不能抹掉先前可能已成功的事实。
    definite = rejected and item['status'] == 'pending'
    _patch_item(item['id'], {'status': 'failed' if definite else 'unknown', 'error_code': error_code})


def _wait_import_execution(batch, suffix, claim):
    """容量不足仅等待，不提交远端、不改变重试计数或交接意图。"""
    key = f"butler-import:{batch['batch_id']}:{suffix}"
    last_reasons = None
    while True:
        try:
            admitted = concurrency.try_admit_and_claim(
                execution_key=key, task_type='email_import', claim=claim,
                batch_key=f"butler-import:{batch['batch_id']}", batch_limit=4,
                metadata={'source_system': 'email_butler_import_batches', 'source_id': batch['batch_id']},
            )
        except (concurrency.ConcurrencyStoreUnavailable, concurrency.ConcurrencyPolicyError) as error:
            admitted = concurrency.AdmissionResult(blocked_by=(error.code,))
        if admitted.context is not None:
            if last_reasons:
                try:
                    record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'], {'concurrency_blocked_by': []})
                except Exception:
                    logger.warning('Butler 已获准执行，等待原因暂未清除')
            return admitted.context
        if 'not_claimable' in admitted.blocked_by:
            return None
        reasons = list(admitted.blocked_by)
        if reasons != last_reasons:
            try:
                record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'], {'concurrency_blocked_by': reasons})
                last_reasons = reasons
            except Exception:
                # 数据库失联时保持原执行意图，恢复连接后继续等待同一许可。
                pass
        # 导入没有取消入口；存储状态仍是 pending，进程停止后按原批次显式继续。
        threading.Event().wait(0.25)


def _import_preflight(batch, connection):
    context = _wait_import_execution(batch, 'preflight', lambda _conn, execution_id: {'execution_id': execution_id})
    try:
        with concurrency.execution_scope(context):
            return _request('GET', '/me', connection)
    finally:
        concurrency.release_execution(context, reason='worker_exit')


def _process_item(batch, item, profile, connection=None):
    context = _wait_import_execution(
        batch, f"item:{item['id']}",
        lambda conn, execution_id: {'execution_id': execution_id, 'item_id': item['id'],
                                     'prepared': _prepare_item(item, conn=conn)},
    )
    if context is None:
        return
    try:
        with concurrency.execution_scope(context):
            if not context.claimed_run['prepared']:
                return
            try:
                receipt = handoff.handoff_selected(item['candidate'], profile,
                    ownership=item['ownership'], client_id=batch['client_id'], connection=connection)
                _finish_item(item, profile, receipt)
            except Exception as exc:
                code = getattr(exc, 'status_code', None)
                definite = (item['status'] == 'pending' and isinstance(code, int)
                            and 400 <= code < 500 and code not in {408, 425, 429})
                _record_item_error(item, 'handoff_rejected' if definite else 'handoff_unconfirmed', rejected=definite)
    finally:
        concurrency.release_execution(context, reason='worker_exit')


def _process_chunk(batch, items, profile, connection):
    started = time.monotonic()
    prepared = []

    def claim(conn, execution_id):
        prepared[:] = [item for item in items if _prepare_item(item, conn=conn)]
        return {'execution_id': execution_id, 'items': [item['id'] for item in prepared]}

    suffix = 'chunk:' + hashlib.sha256(','.join(str(item['id']) for item in items).encode()).hexdigest()
    context = _wait_import_execution(batch, suffix, claim)
    if context is None:
        return
    try:
        with concurrency.execution_scope(context):
            if not prepared:
                return
            prepared_at = time.monotonic()
            results = handoff.handoff_selected_batch(prepared, profile, client_id=batch['client_id'], connection=connection)
            received_at = time.monotonic()
            for item in prepared:
                outcome = results[item['acquisition_id']]
                if 'receipt' in outcome:
                    try:
                        _finish_item(item, profile, outcome['receipt'])
                    except Exception as exc:
                        _record_item_error(item, _batch_error_code(exc))
                else:
                    _record_item_error(item, outcome['error_code'], rejected=outcome['outcome'] == 'failed')
            logger.info('Butler 批量交接：数量=%s，准备=%.3fs，远端=%.3fs，写入=%.3fs',
                        len(prepared), prepared_at - started, received_at - prepared_at, time.monotonic() - received_at)
    finally:
        concurrency.release_execution(context, reason='worker_exit')


def _run_batch(batch_id):
    from psycopg import Error as PostgresError
    from psycopg_pool import PoolTimeout

    while True:
        try:
            batch = _claim_batch_owner(batch_id)
            break
        except (PostgresError, PoolTimeout, concurrency.ConcurrencyStoreUnavailable):
            # 刚创建的持久批次不能因领取 owner 时短暂失联留下无人执行的 running。
            logger.warning('Butler 等待数据库恢复后领取原批次协调权')
            threading.Event().wait(1)
    if batch is None:
        return
    try:
        remaining = [item for item in store.items(batch_id) if item['status'] in {'pending', 'submitting', 'unknown'}]
        if remaining:
            profile = record_store.get_row(record_store.EMAIL_INBOX_PROFILES, int(batch['profile_id']))
            if not profile or profile.get('state') != 'active' or profile.get('connector') != 'forward_butler':
                raise ValueError('fixed_route_unavailable')
            from core.email.derivation import _profile_credentials
            connection = _profile_credentials(profile)
            who = _import_preflight(batch, connection)
            handoff.verify_client(who, client_id=batch['client_id'])
            record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                                   {'status': 'running', 'error_code': None})
            if 'mailboxes.import_batch.v1' in (who.get('capabilities') or []):
                for offset in range(0, len(remaining), _HANDOFF_BATCH_SIZE):
                    _process_chunk(batch, remaining[offset:offset + _HANDOFF_BATCH_SIZE], profile, connection)
            else:
                workers = min(4, max(1, int(os.getenv('TURB_DB_POOL_MAX') or 12)))
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='butler-handoff') as executor:
                    candidates = iter(remaining)
                    futures = set()
                    exhausted = False
                    while futures or not exhausted:
                        while len(futures) < workers and not exhausted:
                            item = next(candidates, None)
                            if item is None:
                                exhausted = True
                                break
                            futures.add(executor.submit(_process_item, batch, item, profile, connection))
                        if futures:
                            completed, futures = wait(futures, return_when=FIRST_COMPLETED)
                            for future in completed:
                                future.result()
        states = [item['status'] for item in store.items(batch_id)]
        complete = all(state in {'imported', 'skipped'} for state in states)
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                               {'status': 'completed' if complete else 'partial', 'error_code': None})
    except Exception as exc:
        error_code = _batch_error_code(exc)
        record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                               {'status': 'partial', 'error_code': error_code})
        logger.warning('Butler 手动导入已暂停，原批次已保留：%s（%s）', error_code, type(exc).__name__)
    finally:
        _release_batch_owner(batch)
