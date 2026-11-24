"""调用方持有邮箱行及地址锁后，集合读取删除与退租判定所需事实。"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json

from core.storage import postgres as pg, records as store


def _address(row: Mapping) -> str:
    return str(row.get('email') or '').strip().lower()


@dataclass
class DeletionSnapshot:
    """与 deletion 单邮箱判据一致；方法不再读取数据库。"""

    confirmed_addresses: set[str] = field(default_factory=set)
    confirmed_account_ids: set[int] = field(default_factory=set)
    account_addresses: set[str] = field(default_factory=set)
    account_ids: set[int] = field(default_factory=set)
    active_addresses: set[str] = field(default_factory=set)
    used_addresses: set[str] = field(default_factory=set)
    pools: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))

    def confirmed(self, row: Mapping) -> bool:
        # 本地删除沿用 pool_mutation_protected 的池内 Token 保护。
        if str(row.get('access_token') or '').strip():
            return True
        address = _address(row)
        if not address:
            return False
        account_id = row.get('registered_account_id')
        return (address in self.confirmed_addresses
                or account_id is not None and int(account_id) in self.confirmed_account_ids)

    def active(self, row: Mapping) -> bool:
        return _address(row) in self.active_addresses

    def return_block_reason(self, row: Mapping, *, unused_inventory: bool = False) -> str:
        address = _address(row)
        if not address:
            return 'registration_result_unverified'
        if self.confirmed(row):
            return 'registration_confirmed'
        if self.active(row):
            return 'registration_active'
        if not unused_inventory or row.get('used_at') or row.get('registered_account_id'):
            return 'registration_result_unverified'
        account_id = row.get('registered_account_id')
        if (address in self.account_addresses
                or account_id is not None and int(account_id) in self.account_ids
                or address in self.used_addresses):
            return 'registration_result_unverified'
        matches = self.pools.get(address, ())
        if len(matches) != 1 or any(
                pool['status'] not in {'available', 'tombstone'}
                or pool['used_at'] or pool['registered_account_id'] for pool in matches):
            return 'registration_result_unverified'
        return ''


def _account_confirmed(row: Mapping) -> bool:
    if row['account_has_access_token']:
        return True
    data = row['data']
    extra = data.get('extra_json') or {}
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (TypeError, ValueError):
            extra = {}
    return (isinstance(extra, dict) and (extra.get('imported_registered') is True
            or extra.get('registration_checkpoint') in {
                'registered', 'token_obtained', 'core_persisted', 'postprocessing', 'completed'})
            or data.get('email_change_status') == 'success')


def load_snapshot(targets: Sequence[Mapping], *, conn) -> DeletionSnapshot:
    """只使用传入连接集合读取；不初始化表、不加锁、不提交事务。"""
    snapshot = DeletionSnapshot()
    if not targets:
        return snapshot
    addresses = sorted({_address(row) for row in targets})
    account_ids = sorted({int(row['registered_account_id']) for row in targets
                          if row.get('registered_account_id') is not None})
    with conn.cursor() as cur:
        cur.execute(f"""SELECT id,lower(email) AS address,
            lower(split_part(COALESCE(data->>'original_email_line',''),'----',1)) AS original_address,
            data,account_has_access_token
            FROM {pg.qualified(store.ACCOUNTS.name)}
            WHERE lower(email)=ANY(%s) OR id=ANY(%s)
               OR lower(split_part(COALESCE(data->>'original_email_line',''),'----',1))=ANY(%s)""",
            (addresses, account_ids, addresses))
        for row in cur.fetchall():
            identities = {row['address'], row['original_address']}
            snapshot.account_addresses.update(identities)
            snapshot.account_ids.add(int(row['id']))
            if _account_confirmed(row):
                snapshot.confirmed_addresses.update(identities)
                snapshot.confirmed_account_ids.add(int(row['id']))
        cur.execute(f"""SELECT address_norm FROM {pg.qualified(store.EMAIL_SERVICE_SYNC.name)}
            WHERE address_norm=ANY(%s) AND kind='import' AND data->>'as_registered'='true'
              AND state IN ('local_only','delivered')""", (addresses,))
        snapshot.confirmed_addresses.update(row['address_norm'] for row in cur.fetchall())

        histories = (
            (store.LOCAL_EMAIL_CLAIMS, 'lower(address_norm)', 'FALSE', ()),
            (store.REGISTRATION_BATCH_EMAIL_CLAIMS, 'lower(email)', 'FALSE', ()),
            (store.JOBS, 'lower(email)',
             "status IN ('pending','queued','running','stopping','cancelling')", ()),
            (store.EMAIL_USAGE_REPORTS, 'lower(address_norm)', 'FALSE', ()),
            (store.EMAIL_OTP_REQUESTS, 'lower(address_key)',
             "state='active' AND lease_expires_at>%s", (store._now(),)),
            (store.EMAIL_ADDRESS_ALLOCATIONS, 'lower(address_norm)', 'FALSE', ()),
            (store.EMAIL_BUTLER_CLAIM_INTENTS,
             "lower(COALESCE(NULLIF(address_norm,''),data->'mailbox'->>'email',''))", 'FALSE', ()),
        )
        statements, parameters = [], []
        for table, address, active, active_params in histories:
            statements.append(f"""SELECT {address} AS address,{active} AS active
                FROM {pg.qualified(table.name)} WHERE {address}=ANY(%s)""")
            parameters.extend((*active_params, addresses))
        cur.execute(' UNION ALL '.join(statements), parameters)
        for row in cur.fetchall():
            snapshot.used_addresses.add(row['address'])
            if row['active']:
                snapshot.active_addresses.add(row['address'])

        optional = {name: pg.qualified(name) for name in (
            'registration_attempts', 'registration_events', 'registration_runs')}
        cur.execute("""SELECT name,to_regclass(name) IS NOT NULL AS present
            FROM unnest(%s::text[]) AS names(name)""", (list(optional.values()),))
        present = {row['name'] for row in cur.fetchall() if row['present']}
        if optional['registration_attempts'] in present:
            events = (f"""EXISTS (SELECT 1 FROM {optional['registration_events']} e
                WHERE e.attempt_id=a.id AND e.event_type='core_persisted')"""
                if optional['registration_events'] in present else 'FALSE')
            active = (f"""EXISTS (SELECT 1 FROM {optional['registration_runs']} r
                WHERE r.attempt_id=a.id AND r.status IN ('queued','running'))"""
                if optional['registration_runs'] in present else 'FALSE')
            cur.execute(f"""SELECT lower(a.email) AS address,lower(a.email_snapshot) AS snapshot_address,
                (a.local_account_state IN ('token_obtained','persisted')
                 OR a.checkpoint IN ('token_obtained','core_persisted','postprocessing','completed','registered')
                 OR {events}) AS confirmed,{active} AS active
                FROM {optional['registration_attempts']} a
                WHERE lower(a.email)=ANY(%s) OR lower(a.email_snapshot)=ANY(%s)""",
                (addresses, addresses))
            for row in cur.fetchall():
                identities = {row['address'], row['snapshot_address']}
                snapshot.used_addresses.update(identities)
                if row['confirmed']:
                    snapshot.confirmed_addresses.update(identities)
                if row['active']:
                    snapshot.active_addresses.update(identities)

        from core.email.inventory import TABLES
        statements = [f"""SELECT lower(email) AS address,status,used_at,registered_account_id
            FROM {pg.qualified(table.name)} WHERE lower(email)=ANY(%s)"""
            for table in TABLES.values()]
        cur.execute(' UNION ALL '.join(statements), tuple(addresses for _ in statements))
        for row in cur.fetchall():
            snapshot.pools[row['address']].append(dict(row))
    return snapshot
