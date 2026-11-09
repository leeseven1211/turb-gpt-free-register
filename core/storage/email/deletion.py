"""邮箱删除只保护已确认的注册事实，领取和密码占位不是成功证据。"""
from __future__ import annotations

import json

from core.storage import postgres as pg, records as store


def _exists(cur, name):
    cur.execute('SELECT to_regclass(%s) AS relation', (pg.qualified(name),))
    return bool(cur.fetchone()['relation'])


def registration_confirmed(address, *, conn, account_id=None):
    address = str(address or '').strip().lower()
    if not address:
        return False
    with conn.cursor() as cur:
        cur.execute(f'''SELECT data,account_has_access_token FROM {pg.qualified(store.ACCOUNTS.name)}
            WHERE lower(email)=%s OR id=%s
            OR lower(split_part(COALESCE(data->>'original_email_line',''),'----',1))=%s''',
            (address, account_id, address))
        for row in cur.fetchall():
            if row['account_has_access_token']:
                return True
            extra = row['data'].get('extra_json') or {}
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except (TypeError, ValueError):
                    extra = {}
            if isinstance(extra, dict) and extra.get('imported_registered') is True:
                return True
            if (isinstance(extra, dict) and extra.get('registration_checkpoint') in {
                    'registered', 'token_obtained', 'core_persisted', 'postprocessing', 'completed'}
                    or row['data'].get('email_change_status') == 'success'):
                return True
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_USAGE_REPORTS.name)}
            WHERE address_norm=%s AND result='ok' LIMIT 1''', (address,))
        if cur.fetchone():
            return True
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_SERVICE_SYNC.name)}
            WHERE address_norm=%s AND kind='import' AND data->>'as_registered'='true'
            AND state IN ('local_only','delivered') LIMIT 1''', (address,))
        if cur.fetchone():
            return True
        if _exists(cur, 'registration_attempts'):
            attempts = pg.qualified('registration_attempts')
            identity = "(lower(email)=%s OR lower(email_snapshot)=%s)"
            cur.execute(f'''SELECT 1 FROM {attempts} WHERE {identity} AND (
                remote_account_state='confirmed' OR local_account_state IN ('token_obtained','persisted')
                OR checkpoint IN ('account_confirmed','token_obtained','core_persisted','postprocessing','completed','registered')) LIMIT 1''',
                (address, address))
            if cur.fetchone():
                return True
            if _exists(cur, 'registration_events'):
                cur.execute(f'''SELECT 1 FROM {pg.qualified('registration_events')} e
                    JOIN {attempts} a ON a.id=e.attempt_id
                    WHERE (lower(a.email)=%s OR lower(a.email_snapshot)=%s)
                    AND e.event_type='core_persisted' LIMIT 1''', (address, address))
                if cur.fetchone():
                    return True
    return False


def registration_active(address, *, conn):
    """本地可先移除；活跃执行结束前不提前退还它仍在读取的租约。"""
    address = str(address or '').strip().lower()
    with conn.cursor() as cur:
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.JOBS.name)} WHERE lower(email)=%s
            AND status IN ('pending','queued','running','stopping','cancelling') LIMIT 1''', (address,))
        if cur.fetchone():
            return True
        cur.execute(f'''SELECT 1 FROM {pg.qualified(store.EMAIL_OTP_REQUESTS.name)} WHERE lower(address_key)=%s
            AND state='active' AND lease_expires_at>%s LIMIT 1''', (address, store._now()))
        if cur.fetchone():
            return True
        if _exists(cur, 'registration_attempts') and _exists(cur, 'registration_runs'):
            cur.execute(f'''SELECT 1 FROM {pg.qualified('registration_runs')} r
                JOIN {pg.qualified('registration_attempts')} a ON a.id=r.attempt_id
                WHERE (lower(a.email)=%s OR lower(a.email_snapshot)=%s)
                AND r.status IN ('queued','running') LIMIT 1''', (address, address))
            return bool(cur.fetchone())
    return False


def pool_deleted(address, *, conn):
    from core.email.inventory import TABLES

    with conn.cursor() as cur:
        for spec in TABLES.values():
            cur.execute(f'''SELECT 1 FROM {pg.qualified(spec.name)} WHERE lower(email)=%s
                AND (status='tombstone' OR COALESCE(data->>'pool_deleted_at','')<>'') LIMIT 1''',
                (str(address or '').strip().lower(),))
            if cur.fetchone():
                return True
    return False
