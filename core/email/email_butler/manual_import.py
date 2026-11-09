"""人工导入与后台协调；注册仅领取已导入库存，不调用远端分配。"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone

from core.storage import records as record_store
from core.storage.email import butler_manual_imports as store
from core.operations import concurrency
from core.storage.operations.permits import current_owner

logger = logging.getLogger('core.butler_manual_import')
_ITEM_STATES = ('pending', 'submitting', 'unknown', 'imported', 'skipped', 'failed')
_FINISHED_BATCH_EXECUTIONS: set[str] = set()


class RemoteError(RuntimeError):
    """HTTP 边界兼容异常，不保留上游私有正文。"""


def _uuid(value, label):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError('invalid_' + label) from None
    return value


def _config():
    from core.email.email_butler.manual_import_v2 import configuration
    return configuration()


def _filters(data):
    from core.email.email_butler.manual_import_v2 import filters
    return filters(data)


def options():
    from core.email.email_butler.manual_import_v2 import options as v2_options
    return v2_options()


def preview(data):
    from core.email.email_butler.manual_import_v2 import preview as v2_preview
    return v2_preview(data)


def create(data):
    from core.email.email_butler.manual_import_v2 import create as v2_create
    return v2_create(data)


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
            'can_retry': row['status'] != 'cancelled' and bool(counts['pending'] or counts['submitting'] or counts['unknown']),
            'can_cancel': row['status'] not in {'completed', 'cancelled'},
            'cancelled_at': row.get('cancelled_at'),
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


def cancel(batch_id):
    """终止后续导入；原请求、在途回执和已导入邮箱继续保留，不自动退租。"""
    batch_id = _uuid(batch_id, 'batch_id')
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-manual-import:' + batch_id)
        row = store.batch(batch_id, conn=conn)
        if row['status'] not in {'completed', 'cancelled'}:
            changes = {'status': 'cancelled', 'cancelled_at': datetime.now(timezone.utc).isoformat(),
                       'concurrency_blocked_by': []}
            record_store.patch_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, row['id'], changes, conn=conn)
            row.update(changes)
        return _public(row, conn=conn)


def _patch_active_batch(batch, changes, *, conn=None):
    """晚到的协调者和等待状态不能覆盖用户已终止的批次。"""
    return record_store.claim_row(record_store.EMAIL_BUTLER_IMPORT_BATCHES, batch['id'],
                                  changes=changes, guard="status <> 'cancelled'", conn=conn)


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
    if previous['status'] == 'cancelled' or _batch_owner_active(previous):
        return None
    owner = {**current_owner(), 'thread_id': threading.get_ident()}
    with record_store.transaction() as conn:
        record_store.advisory_xact_lock(conn, 'butler-manual-import:' + batch_id)
        batch = store.batch(batch_id, conn=conn)
        if (batch['status'] == 'cancelled'
                or batch.get('worker_execution_id') != previous.get('worker_execution_id')):
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
    if code == 'handoff_contract_unsupported' or getattr(error, 'error_code', ''):
        return code
    return 'import_internal_error'


def _record_item_error(item, error_code, *, rejected=False):
    # 旧交接结果尚未确认时，后续拒绝不能抹掉先前可能已成功的事实。
    definite = rejected and item['status'] == 'pending'
    _patch_item(item['id'], {'status': 'failed' if definite else 'unknown', 'error_code': error_code})


def _wait_import_execution(batch, suffix, claim):
    """容量不足仅等待，不提交远端、不改变重试计数或交接意图。"""
    from psycopg import Error as PostgresError
    from psycopg_pool import PoolTimeout

    key = f"butler-import:{batch['batch_id']}:{suffix}"
    last_reasons = None

    def claim_active(conn, execution_id):
        # 并发准入已持有并发锁，再取批次锁；终止仅取批次锁，保持锁顺序一致。
        record_store.advisory_xact_lock(conn, 'butler-manual-import:' + batch['batch_id'])
        if store.batch(batch['batch_id'], conn=conn)['status'] == 'cancelled':
            return None
        return claim(conn, execution_id)

    while True:
        try:
            # 容量不足时不会进入 claim，也需要让显式终止及时结束等待。
            if store.batch(batch['batch_id'])['status'] == 'cancelled':
                return None
            admitted = concurrency.try_admit_and_claim(
                execution_key=key, task_type='email_import', claim=claim_active,
                batch_key=f"butler-import:{batch['batch_id']}", batch_limit=4,
                metadata={'source_system': 'email_butler_import_batches', 'source_id': batch['batch_id']},
            )
        except (concurrency.ConcurrencyStoreUnavailable, concurrency.ConcurrencyPolicyError) as error:
            admitted = concurrency.AdmissionResult(blocked_by=(error.code,))
        except (PostgresError, PoolTimeout):
            admitted = concurrency.AdmissionResult(blocked_by=('scheduler_store_unavailable',))
        if admitted.context is not None:
            if last_reasons:
                try:
                    _patch_active_batch(batch, {'concurrency_blocked_by': []})
                except Exception:
                    logger.warning('Butler 已获准执行，等待原因暂未清除')
            return admitted.context
        if 'not_claimable' in admitted.blocked_by:
            return None
        reasons = list(admitted.blocked_by)
        if reasons != last_reasons:
            try:
                _patch_active_batch(batch, {'concurrency_blocked_by': reasons})
                last_reasons = reasons
            except Exception:
                # 数据库失联时保持原执行意图，恢复连接后继续等待同一许可。
                pass
        threading.Event().wait(0.25)


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
        from core.email.email_butler.manual_import_v2 import run_batch
        run_batch(batch)
        states = [item['status'] for item in store.items(batch_id)]
        complete = all(state in {'imported', 'skipped'} for state in states)
        _patch_active_batch(batch, {'status': 'completed' if complete else 'partial', 'error_code': None})
    except Exception as exc:
        error_code = _batch_error_code(exc)
        if _patch_active_batch(batch, {'status': 'partial', 'error_code': error_code}):
            logger.warning('Butler 手动导入已暂停，原批次已保留：%s（%s）', error_code, type(exc).__name__)
    finally:
        _release_batch_owner(batch)
