"""邮箱本地事实共用的集合 SQL；不接触网络或运行控制。"""
from collections import defaultdict
import json

from core.storage import postgres as pg, records as store


def lock_keys(conn, keys):
    keys = sorted(set(keys))
    if keys:
        with conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(key,0)) FROM '
                '(SELECT unnest(%s::text[]) AS key ORDER BY key) ordered', (keys,))
            cur.fetchall()


def insert_many(conn, spec, payloads, *, conflict_key=None):
    """保留 records 的字段拆分/派生规则；每组同构行一条 INSERT RETURNING。"""
    groups = defaultdict(list)
    for raw in payloads:
        body = dict(raw)
        body.setdefault('created_at', store._now())
        body.setdefault('updated_at', body['created_at'])
        promoted, rest = store._split(spec, body, partial=False)
        value = {**promoted, 'data': rest}
        groups[tuple(sorted(value))].append(value)
    result = []
    for fields, values in groups.items():
        columns = ','.join(pg.quote_identifier(field) for field in fields)
        projection = ','.join('x.' + pg.quote_identifier(field) for field in fields)
        conflict = (f' ON CONFLICT ({pg.quote_identifier(conflict_key)}) WHERE '
            f'{pg.quote_identifier(conflict_key)} IS NOT NULL DO NOTHING' if conflict_key else '')
        # 500行一块只限制 SQL 体积，调用方拥有整体事务边界。
        for offset in range(0, len(values), 500):
            with conn.cursor() as cur:
                cur.execute(f'INSERT INTO {pg.qualified(spec.name)} ({columns}) SELECT {projection} '
                    f'FROM jsonb_populate_recordset(NULL::{pg.qualified(spec.name)},%s::jsonb) x'
                    + conflict + ' RETURNING *',
                    (json.dumps(values[offset:offset + 500], ensure_ascii=False, default=str),))
                result.extend(store.merge_row(spec, row) for row in cur.fetchall())
    return result


def patch_many(conn, spec, changes):
    from core.storage.email.bulk_mutations import _patch_many
    _patch_many(conn, spec, changes)
