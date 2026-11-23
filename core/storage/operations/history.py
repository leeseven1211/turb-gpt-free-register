"""有界读取归档，在文件校验完成后用独立短事务复核并清理历史。"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic

from psycopg.errors import DeadlockDetected, LockNotAvailable, QueryCanceled, SerializationFailure
from psycopg.rows import dict_row
from psycopg_pool import PoolTimeout

from core.storage import postgres
from core.storage.operations import common, schema
from core.storage.operations.common import _table as table

# File I/O has its own cancellation checkpoints. These deadlines apply only to SQL.
_TX_SECONDS = 2.0
_CANDIDATES = 32
_EVENT_ROWS = 1000
_PAGE_BYTES = 4 * 1024 * 1024
_READ_ROWS = 128
_SECTIONS = ("tasks", "runs", "events", "resources", "leases", "batch_items", "batches",
             "projection_queue", "dependencies", "extract_link_payment_orders")


class SnapshotChanged(Exception):
    """This file was not used to delete any rows."""


@contextmanager
def _database():
    # A timeout during COMMIT can mean its reply was lost. Only classify checkout
    # or statement deadlines inside the transaction as known, retryable rollbacks.
    with ExitStack() as stack:
        try:
            conn = stack.enter_context(postgres.connect(row_factory=dict_row, deadline=monotonic() + _TX_SECONDS))
        except (PoolTimeout, TimeoutError) as exc:
            raise SnapshotChanged from exc
        try:
            yield conn
        except (LockNotAvailable, QueryCanceled, DeadlockDetected, SerializationFailure, TimeoutError) as exc:
            raise SnapshotChanged from exc


def _eligible_tasks():
    return f"""
    SELECT task.id, task.batch_id, task.source_system, task.completed_at, task.xmin::text AS version
    FROM {table('operation_tasks')} task
    WHERE task.status IN ({common._TERMINAL_STATUS_SQL})
      AND NOT (task.data ? 'bulk_target_round_id')
      AND task.completed_at IS NOT NULL
      AND task.completed_at < %s
      AND NOT EXISTS (
          SELECT 1 FROM {table('extract_link_payment_orders')} payment
          WHERE payment.task_id=task.id
            AND (payment.payment_state IN ('pending','unknown')
              OR (payment.payment_state='succeeded'
                AND COALESCE(payment.summary->>'plus_verification_status', '')
                    NOT IN ('confirmed','not_applicable')))
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('extract_link_payment_orders')} original
          JOIN {table('extract_link_payment_orders')} linked
            ON linked.summary->>'related_payment_order_id'=original.id::text
          WHERE original.task_id=task.id AND linked.task_id<>task.id
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('operation_runs')} uncertain_run
          WHERE uncertain_run.task_id=task.id
            AND task.task_type IN ('token_refresh', 'live_check')
            AND uncertain_run.status='failed'
            AND uncertain_run.result_summary->>'cause_code' IN ('password_change_required', 'password_page_error')
            AND uncertain_run.result_summary->>'outcome'='request_unknown'
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('operation_runs')} run
          WHERE run.task_id=task.id
            AND run.status IN ({common._ACTIVE_RUN_STATUS_SQL})
      )
      AND NOT (
          task.source_system='registration_jobs'
          AND EXISTS (
              SELECT 1 FROM {table('registration_jobs')} source_task
              WHERE source_task.id::text=task.source_id
                AND source_task.status IN ({common._ACTIVE_RUN_STATUS_SQL})
          )
      )
      AND NOT (
          task.source_system='account_action_tasks'
          AND EXISTS (
              SELECT 1 FROM {table('account_action_tasks')} source_task
              WHERE source_task.id::text=task.source_id
                AND source_task.status IN ({common._ACTIVE_RUN_STATUS_SQL})
          )
      )
      AND NOT EXISTS (
          SELECT 1
          FROM {table('account_operation_leases')} lease
          JOIN {table('operation_runs')} run ON run.id=lease.run_id
          WHERE run.task_id=task.id AND lease.expires_at >= now()
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('operation_tasks')} child
          WHERE child.id<>task.id
            AND (child.parent_task_id=task.id OR child.root_task_id=task.id)
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('operation_task_dependencies')} dependency
          WHERE dependency.status<>'completed'
            AND (
              (
                dependency.parent_source_system=task.source_system
                AND dependency.parent_source_id IN (task.source_id, task.id::text)
              ) OR (
                dependency.child_source_system=task.source_system
                AND dependency.child_source_id IN (task.source_id, task.id::text)
              )
            )
      )
      AND NOT EXISTS (
          SELECT 1 FROM {table('operation_runs')} r JOIN {common._permit_table()} p ON p.run_id=r.id
          WHERE r.task_id=task.id AND p.released_at IS NULL
      )
    """


def _eligible_batches():
    return f"""SELECT b.id, b.completed_at FROM {table('operation_batches')} b
        WHERE b.status IN ({common._TERMINAL_STATUS_SQL}) AND b.completed_at < %s
          AND b.source_system <> 'bulk_manager'
          AND NOT EXISTS (SELECT FROM {table('operation_tasks')} t WHERE t.batch_id=b.id)
          AND NOT EXISTS (SELECT FROM {table('operation_runs')} r WHERE r.batch_id=b.id)
          AND NOT EXISTS (SELECT FROM {table('operation_batch_items')} i WHERE i.batch_id=b.id)
          AND NOT EXISTS (SELECT FROM {table('operation_projection_queue')} q
                          WHERE q.batch_id=b.id AND q.status IN ('queued','running'))"""


def _ids(rows):
    return [row['id'] for row in rows]


@dataclass(frozen=True)
class ScanPosition:
    tasks: tuple[datetime, int] | None = None
    batches: tuple[datetime, int] | None = None


def _candidate_page(cur, relation, eligibility, alias, cutoff, limit, after):
    # Evaluate the joins only for this page. A LIMIT after the joins can scan the
    # entire protected history without returning a cursor before the SQL deadline.
    sql = f"""SELECT id, completed_at FROM {table(relation)}
        WHERE status IN ({common._TERMINAL_STATUS_SQL}) AND completed_at < %s"""
    params = [cutoff]
    if after:
        sql += ' AND (completed_at, id) > (%s, %s)'
        params.extend(after)
    cur.execute(sql + ' ORDER BY completed_at,id LIMIT %s', (*params, limit))
    page = cur.fetchall()
    if not page:
        return [], None
    next_key = (page[-1]['completed_at'], page[-1]['id']) if len(page) == limit else None
    cur.execute(eligibility + f' AND {alias}.id=ANY(%s) ORDER BY {alias}.completed_at,{alias}.id',
                (cutoff, _ids(page)))
    return cur.fetchall(), next_key


def _candidates(cutoff, limit, after):
    # These are only availability probes. Release every lock before reading payloads or writing files.
    with _database() as conn, conn.cursor() as cur:
        candidates, task_key = ([], None) if after and not after.tasks else _candidate_page(
            cur, 'operation_tasks', _eligible_tasks(), 'task', cutoff, limit, after.tasks if after else None,
        )
        proposed = _ids(candidates)
        if proposed:
            runs = f"SELECT task_id,id FROM {table('operation_runs')} WHERE task_id=ANY(%s) ORDER BY id"
            cur.execute(runs, (proposed,))
            seen = {(r['task_id'], r['id']) for r in cur.fetchall()}
            cur.execute(runs + ' FOR UPDATE SKIP LOCKED', (proposed,))
            held = {(r['task_id'], r['id']) for r in cur.fetchall()}
            busy = {task for task, _ in seen ^ held}
            cur.execute(f"SELECT id FROM {table('operation_tasks')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED",
                        ([i for i in proposed if i not in busy],))
            held_tasks = set(_ids(cur.fetchall()))
            # A Run may have committed between probing Runs and locking their parents.
            cur.execute(runs, (proposed,))
            busy.update(task for task, _ in held ^ {(r['task_id'], r['id']) for r in cur.fetchall()})
            busy.update(set(proposed) - held_tasks)
        else:
            busy = set()
        batches, batch_key = ([], None) if after and not after.batches else _candidate_page(
            cur, 'operation_batches', _eligible_batches(), 'b', cutoff, limit, after.batches if after else None,
        )
        proposed_batches = _ids(batches)
        cur.execute(f"SELECT id FROM {table('operation_batches')} WHERE id=ANY(%s) ORDER BY id FOR UPDATE SKIP LOCKED",
                    (proposed_batches,))
        empty_batches = _ids(cur.fetchall())
    cursor = ScanPosition(task_key, batch_key) if task_key or batch_key else None
    available = [r for r in candidates if r['id'] not in busy]
    return available, empty_batches, len(busy) + len(proposed_batches) - len(empty_batches), cursor


def _event_piece(task_ids):
    """Use the (task_id,id) index and stop after the first unselected event, even for a huge task."""
    versions = []
    size = 0
    with _database() as conn, conn.cursor() as cur:
        for task_id in task_ids:
            cur.execute(f"""SELECT id, xmin::text AS version, octet_length(row_to_json(e)::text) AS size
                FROM {table('operation_events')} e WHERE task_id=%s ORDER BY id LIMIT %s""",
                        (task_id, _EVENT_ROWS + 1 - len(versions)))
            for row in cur.fetchall():
                if len(versions) == _EVENT_ROWS or (versions and size + row['size'] > _PAGE_BYTES):
                    return versions, True
                versions.append((row['id'], row['version']))
                size += row['size']
    return versions, False


def _crossed_task_ids(cur, task_ids, event_ids, partial):
    """Two independent FKs can disagree in legacy data. Preserve both owners of such a row."""
    if not task_ids:
        return set()
    runs = table('operation_runs')
    run_scope = f"SELECT id FROM {runs} WHERE task_id=ANY(%s)"
    event_scope = 'child.id=ANY(%s)'
    params = [event_ids]
    if not partial:
        event_scope += f' OR child.run_id IN ({run_scope})'
        params.append(task_ids)
    relations = [('operation_events', 'run_id', event_scope)]
    if not partial:
        for relation, column in (('operation_batch_items', 'run_id'), ('extract_link_payment_orders', 'origin_run_id')):
            relations.append((relation, column, f'child.task_id=ANY(%s) OR child.{column} IN ({run_scope})'))
            params.extend((task_ids, task_ids))
    selects = [
        f"""SELECT unnest(ARRAY[child.task_id,r.task_id]) AS id FROM {table(relation)} child
            JOIN {runs} r ON r.id=child.{column}
            WHERE ({scope}) AND child.task_id<>r.task_id""" for relation, column, scope in relations
    ]
    cur.execute(' UNION '.join(selects), params)
    return set(_ids(cur.fetchall())).intersection(task_ids)


@dataclass(frozen=True)
class Section:
    relation: str
    where: str
    params: tuple
    keys: tuple = ('id',)

    def versions(self, cur, *, lock=False, limit=None):
        keys = ','.join(self.keys)
        sql = f"SELECT {keys},r.xmin::text AS _version FROM {table(self.relation)} r WHERE {self.where} ORDER BY {keys}"
        params = self.params
        if limit is not None:
            sql += ' LIMIT %s'
            params = (*params, limit)
        cur.execute(sql + (' FOR UPDATE OF r NOWAIT' if lock else ''), params)
        return {self.key(row): row['_version'] for row in cur.fetchall()}

    def key(self, row):
        return tuple(row[k] for k in self.keys)

    def pages(self):
        # The database returns at most one page. Its connection is returned before the first yield.
        end = None
        keys = ','.join(self.keys)
        while True:
            where = self.where
            params = self.params
            if end is not None:
                where += f" AND ({keys}) > ({','.join(['%s'] * len(end))})"
                params = (*params, *end)
            with _database() as conn, conn.cursor() as cur:
                cur.execute(f"""WITH page AS MATERIALIZED (
                    SELECT r.*,r.xmin::text AS _version,octet_length(row_to_json(r)::text) AS _bytes
                    FROM {table(self.relation)} r WHERE {where} ORDER BY {keys} LIMIT %s
                ), sized AS (SELECT page.*,sum(_bytes) OVER (ORDER BY {keys}) AS _total FROM page)
                SELECT * FROM sized WHERE _total <= %s OR _total=_bytes ORDER BY {keys}""",
                            (*params, _READ_ROWS, _PAGE_BYTES))
                rows = cur.fetchall()
            if not rows:
                return
            end = self.key(rows[-1])
            yield rows


def _sections(task_ids, batch_ids, event_ids):
    run_scope = f"SELECT id FROM {table('operation_runs')} WHERE task_id=ANY(%s)"
    related_run = f'run_id IN ({run_scope})'
    dependency = f"""EXISTS (SELECT FROM {table('operation_tasks')} t WHERE t.id=ANY(%s)
        AND ((r.parent_source_system=t.source_system AND r.parent_source_id IN (t.source_id,t.id::text))
          OR (r.child_source_system=t.source_system AND r.child_source_id IN (t.source_id,t.id::text))))"""
    return {
        'tasks': Section('operation_tasks', 'id=ANY(%s)', (task_ids,)),
        'runs': Section('operation_runs', 'task_id=ANY(%s)', (task_ids,)),
        'events': Section('operation_events', 'id=ANY(%s) AND task_id=ANY(%s)', (event_ids, task_ids)),
        'resources': Section('operation_resources', related_run, (task_ids,)),
        'leases': Section('account_operation_leases', related_run, (task_ids,), ('run_id','account_id','resource_family')),
        'batch_items': Section('operation_batch_items', 'task_id=ANY(%s)', (task_ids,)),
        'batches': Section('operation_batches', 'id=ANY(%s)', (batch_ids,)),
        'projection_queue': Section('operation_projection_queue', 'batch_id=ANY(%s)', (batch_ids,)),
        'dependencies': Section('operation_task_dependencies', dependency, (task_ids,)),
        'extract_link_payment_orders': Section('extract_link_payment_orders', 'task_id=ANY(%s)', (task_ids,)),
        # This relation is a version guard only. Its payload never enters the archive.
        'provider_jobs': Section('extract_link_provider_jobs', related_run, (task_ids,), ('run_id',)),
    }


class Piece:
    def __init__(self, candidates, empty_batches, cutoff, event_versions, partial):
        self.task_ids = _ids(candidates)
        self.empty_batches = set(empty_batches)
        self.batch_ids = sorted({r['batch_id'] for r in candidates if r['batch_id']} | set(empty_batches))
        self.sources = {r['source_system'] for r in candidates}
        self.native_ids = {r['id'] for r in candidates if r['source_system'] == 'native_operations'}
        self.cutoff = cutoff
        self.event_ids = [key for key, _ in event_versions]
        self.partial = partial
        self.sections = _sections(self.task_ids, self.batch_ids, self.event_ids)
        self.expected = {'events': {(key,): version for key, version in event_versions}}
        self.native_logs = set()
        self.raw_bytes = 0
        # Preserve the task and Run identity from BEFORE entering user/file code, even for an event-only file.
        with _database() as conn, conn.cursor() as cur:
            for name in ('runs', 'tasks', 'batches'):
                self.expected[name] = self.sections[name].versions(cur)
            if not partial:
                self.expected['provider_jobs'] = self.sections['provider_jobs'].versions(cur)
            if self.expected['tasks'] != {(row['id'],): row['version'] for row in candidates}:
                raise SnapshotChanged
            if set(self.expected['batches']) != {(i,) for i in self.batch_ids}:
                raise SnapshotChanged

    def archive(self, days, archive, archive_stream, checkpoint, check_cancel):
        done = set()

        def rows(name):
            checkpoint()
            if not self.partial or name == 'events':
                section = self.sections[name]
                versions = {}
                expected = self.expected.get(name)
                for page in section.pages():
                    for row in page:
                        checkpoint()
                        key = section.key(row)
                        version = row.pop('_version')
                        if expected is not None and expected.get(key) != version:
                            raise SnapshotChanged
                        versions[key] = version
                        self.raw_bytes += row.pop('_bytes')
                        row.pop('_total')
                        if name == 'runs' and row['task_id'] in self.native_ids and row.get('log_file'):
                            self.native_logs.add(row['log_file'])
                        yield common._row(row)
                if expected is not None and expected != versions:
                    raise SnapshotChanged
                self.expected[name] = versions
            done.add(name)

        metadata = dict(version=1, created_at=common._now().isoformat(), cutoff=self.cutoff.isoformat(), retention_days=days)
        streams = {name: rows(name) for name in _SECTIONS}
        try:
            if archive_stream is None:
                receipt = archive({**metadata, **{k: list(v) for k, v in streams.items()}})
            else:
                receipt = archive_stream(metadata, streams, check_cancel=check_cancel)
            if done != set(_SECTIONS):
                raise RuntimeError('归档分段未完整读取')
            return receipt
        finally:
            for stream in streams.values():
                stream.close()

    def _check(self, cur, name, *, lock=True):
        expected = self.expected[name]
        if self.sections[name].versions(cur, lock=lock, limit=len(expected)+1) != expected:
            raise SnapshotChanged

    def _lock_sources(self, cur):
        # The legacy identities are text, with no FK. Lock matching rows; fence absent identities too.
        for source in ('registration_jobs', 'account_action_tasks'):
            if source not in self.sources:
                continue
            cur.execute(f"SELECT DISTINCT source_id FROM {table('operation_tasks')} WHERE id=ANY(%s) AND source_system=%s",
                        (self.task_ids, source))
            wanted = [r['source_id'] for r in cur.fetchall()]
            cur.execute(f"SELECT id FROM {table(source)} WHERE id::text=ANY(%s) ORDER BY id FOR SHARE NOWAIT", (wanted,))
            if len(cur.fetchall()) != len(wanted):
                cur.execute(f"LOCK TABLE {table(source)} IN SHARE MODE NOWAIT")

    def commit(self, checkpoint):
        with _database() as conn, conn.cursor() as cur:
            # Keep simultaneous maintenance and non-FK writers out only for the short delete transaction.
            if self.task_ids:
                cur.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS ok',
                            (f'{common._schema_name()}:independent-payment:xxsyun',))
                if not cur.fetchone()['ok']:
                    raise SnapshotChanged
                cur.execute(f"LOCK TABLE {table('operation_task_dependencies')} IN SHARE MODE NOWAIT")
                if self.expected['runs']:
                    cur.execute(f'LOCK TABLE {common._permit_table()} IN SHARE MODE NOWAIT')
            self._check(cur, 'runs')
            self._check(cur, 'tasks')
            # The Task FK prevents later inserts. Do not acquire a newly discovered Run after its Task.
            self._check(cur, 'runs', lock=False)
            self._lock_sources(cur)
            self._check(cur, 'events')
            if not self.partial:
                self._check(cur, 'batches')
                for name in ('projection_queue', 'resources', 'leases', 'batch_items', 'dependencies',
                             'extract_link_payment_orders', 'provider_jobs'):
                    self._check(cur, name)
            else:
                # Lease renewal can turn an expired lease into an active one without changing its Run.
                self.sections['leases'].versions(cur, lock=True)
                self.sections['extract_link_payment_orders'].versions(cur, lock=True)
            cur.execute(_eligible_tasks() + ' AND task.id=ANY(%s)', (self.cutoff, self.task_ids))
            if set(_ids(cur.fetchall())) != set(self.task_ids):
                raise SnapshotChanged
            if _crossed_task_ids(cur, self.task_ids, self.event_ids, self.partial):
                raise SnapshotChanged
            checkpoint()
            if self.event_ids:
                cur.execute(f"DELETE FROM {table('operation_events')} WHERE id=ANY(%s)", (self.event_ids,))
                if cur.rowcount != len(self.event_ids):
                    raise SnapshotChanged
            deleted_tasks = deleted_batches = 0
            if not self.partial:
                # An insert between event selection and locking the parent must never be cascade-deleted.
                # Legacy cross-linked rows may also be reached through the independent Run foreign key.
                run_ids = [k[0] for k in self.expected['runs']]
                cur.execute(f"SELECT FROM {table('operation_events')} WHERE task_id=ANY(%s) OR run_id=ANY(%s) LIMIT 1",
                            (self.task_ids, run_ids))
                if cur.fetchone() is not None:
                    raise SnapshotChanged
                dependency_ids = [key[0] for key in self.expected['dependencies']]
                cur.execute(f"DELETE FROM {table('operation_task_dependencies')} WHERE id=ANY(%s) AND status='completed'", (dependency_ids,))
                cur.execute(f"DELETE FROM {table('operation_tasks')} WHERE id=ANY(%s)", (self.task_ids,))
                deleted_tasks = cur.rowcount
                cur.execute(f"""WITH eligible AS ({_eligible_batches()} AND b.id=ANY(%s))
                    DELETE FROM {table('operation_batches')} target USING eligible
                    WHERE target.id=eligible.id RETURNING target.id""", (self.cutoff, self.batch_ids))
                removed = set(_ids(cur.fetchall()))
                if deleted_tasks != len(self.task_ids) or not self.empty_batches.issubset(removed):
                    raise SnapshotChanged
                deleted_batches = len(removed)
            checkpoint()
        return deleted_tasks, deleted_batches


def cleanup_terminal_history(*, retention_days: int, limit: int = 500, archive=None, archive_stream=None,
                             check_cancel: Callable | None = None, after: ScanPosition | None = None) -> dict:
    if check_cancel is not None and not callable(check_cancel):
        raise ValueError('归档取消检查必须可调用')
    checkpoint = check_cancel or (lambda: None)
    checkpoint()
    days = int(retention_days or 0)
    if days <= 0:
        return dict(deleted_tasks=0, deleted_batches=0, disabled=True)
    if (archive is None) == (archive_stream is None) or not callable(archive or archive_stream):
        raise ValueError('任务中心清理必须提供一个归档回调')
    schema.init_operation_schema()
    cutoff = common._now() - timedelta(days=days)
    result = dict(deleted_tasks=0, deleted_batches=0, deleted_events=0, cutoff=cutoff.isoformat())
    try:
        candidates, batches, busy, cursor = _candidates(
            cutoff, max(1, min(_CANDIDATES, int(limit or 500))), after,
        )
        result.update(busy_tasks=busy, next_cursor=cursor)
        event_versions, partial = [], False
        while candidates:
            task_ids = _ids(candidates)
            event_versions, partial = _event_piece(task_ids)
            with _database() as conn, conn.cursor() as cur:
                crossed = _crossed_task_ids(cur, task_ids, [key for key, _ in event_versions], partial)
            if not crossed:
                break
            result['inconsistent_tasks'] = result.get('inconsistent_tasks', 0) + len(crossed)
            candidates = [r for r in candidates if r['id'] not in crossed]
            event_versions, partial = [], False
        if not candidates and not batches:
            return result
        piece = Piece(candidates, batches, cutoff, event_versions, partial)
        checkpoint()
        receipt = piece.archive(days, archive, archive_stream, checkpoint, check_cancel)
        checkpoint()
        deleted_tasks, deleted_batches = piece.commit(checkpoint)
    except SnapshotChanged:
        result['retry'] = True
        return result
    return dict(result, deleted_tasks=deleted_tasks, deleted_batches=deleted_batches, deleted_events=len(piece.event_ids),
                archive=receipt, native_log_files=sorted(piece.native_logs), has_more=True, raw_bytes=piece.raw_bytes)
