#!/usr/bin/env python3
"""从原固定 profile 只读提取精确收件绑定，经原凭据补齐 Butler 读取授权。"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from dotenv import dotenv_values
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import requests

try:
    from tools.maintenance.reconcile_butler_service_facts import ReconcileError, address, digest, request_json, write_receipt, transport_base
except ModuleNotFoundError:
    from reconcile_butler_service_facts import ReconcileError, address, digest, request_json, write_receipt, transport_base


def build_bindings(profiles, references, tombstones, instance):
    candidates, issues = {}, []
    skipped = Counter()
    for row in references:
        try:
            email = address(row['email'])
        except ReconcileError:
            issues.append({'record': row['record'], 'error_code': 'service_address_invalid'})
            continue
        if email in tombstones:
            skipped['tombstone'] += 1
            continue
        profile = profiles.get(int(row['profile_id'] or 0))
        if not profile:
            issues.append({'record': row['record'], 'error_code': 'fixed_route_unavailable'})
            continue
        if profile.get('connector') != 'forward_butler':
            skipped['not_fixed_butler'] += 1
            continue
        if profile.get('state') != 'active':
            issues.append({'record': row['record'], 'error_code': 'fixed_route_unavailable'})
            continue
        locator = profile.get('inbox_locator') or {}
        try:
            mailbox = address(locator.get('mailbox_email'))
            base = transport_base(locator.get('api_base'), None)
        except ReconcileError:
            issues.append({'record': row['record'], 'error_code': 'fixed_route_invalid'})
            continue
        reference = str(profile.get('credential_ref') or '')
        if not reference:
            issues.append({'record': row['record'], 'error_code': 'fixed_route_credentials_missing'})
            continue
        item = {'address': email, 'service': 'openai',
                'binding_id': 'turb-read:' + digest(f'{instance}:{profile["id"]}:{email}'),
                'mailbox_email': mailbox,
                'evidence_ref': f'{instance}:email_inbox_profiles:{profile["id"]}:address:{digest(email)}'}
        token = str(row.get('legacy_lease_id') or '')
        if token:
            item['legacy_lease_id'] = token
        candidate = {'item': item, 'api_base': base, 'credential_ref': reference, 'profile_id': profile['id']}
        old = candidates.get(email)
        if old and old != candidate:
            issues.append({'address_hash': digest(email), 'error_code': 'fixed_route_conflict'})
        else:
            candidates[email] = candidate
    return [candidates[k] for k in sorted(candidates)], issues, dict(skipped)


def collect_bindings(conn, schema, instance):
    q = lambda name: sql.Identifier(schema, name)
    profiles, references, tombstones = {}, [], set()
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('transaction_read_only') mode")
        if cur.fetchone()['mode'] != 'on':
            raise ReconcileError('readonly_transaction_required')
        cur.execute(sql.SQL('SELECT * FROM {}').format(q('email_inbox_profiles')))
        for row in cur.fetchall():
            profiles[row['id']] = {**(row.get('data') or {}), **{k:v for k,v in row.items() if k != 'data'}}
        current = set()
        cur.execute(sql.SQL('SELECT lower(trim(email)) email FROM {}').format(q('registered_accounts')))
        current.update(r['email'] for r in cur.fetchall())
        for table in ('email_pool_butler', 'email_pool_icloud_hide'):
            cur.execute(sql.SQL('SELECT id,email,status,data FROM {}').format(q(table)))
            for row in cur.fetchall():
                data = row.get('data') or {}
                if row['status'] == 'tombstone':
                    tombstones.add(address(row['email']))
                    continue
                current.add(address(row['email']))
                profile_id = data.get('local_inbox_profile_id') or data.get('inbox_profile_id') or (data.get('derivation_policy') or {}).get('inbox_profile_id')
                references.append({'email': row['email'], 'profile_id': profile_id, 'record': f'{table}:{row["id"]}',
                                   'legacy_lease_id': (data.get('mailbox') or {}).get('lease_id')})
        cur.execute(sql.SQL('SELECT id,address_norm,parent_address,inbox_profile_id,state FROM {} ORDER BY id').format(q('email_address_allocations')))
        for row in cur.fetchall():
            if row['state'] in {'released', 'returned', 'deleted', 'cancelled'}:
                continue
            references.append({'email': row['address_norm'], 'profile_id': row['inbox_profile_id'], 'record': f'email_address_allocations:{row["id"]}'})
            if row['parent_address'].strip().lower() in current:
                references.append({'email': row['parent_address'], 'profile_id': row['inbox_profile_id'], 'record': f'email_address_allocations:{row["id"]}:parent'})
        for profile in profiles.values():
            identity = profile.get('butler_identity') or {}
            if identity.get('email') and identity['email'].strip().lower() in current:
                references.append({'email': identity['email'], 'profile_id': profile['id'], 'record': f'email_inbox_profiles:{profile["id"]}',
                                   'legacy_lease_id': identity.get('lease_id')})
    return build_bindings(profiles, references, tombstones, instance)


def decrypt_routes(conn, cfg, schema, candidates):
    refs = sorted({r['credential_ref'] for r in candidates})
    with conn.cursor() as cur:
        cur.execute(sql.SQL('SELECT key,value_encrypted FROM {} WHERE key=ANY(%s)').format(sql.Identifier(schema, 'runtime_config_values')), (refs,))
        rows = cur.fetchall()
    try:
        cipher = Fernet(cfg['TURB_CONFIG_ENCRYPTION_KEY'].encode())
        keys = {r['key']: cipher.decrypt(r['value_encrypted'].encode()).decode() for r in rows}
        for ref in refs:
            if not keys.get(ref):
                raise ValueError()
        return keys
    except Exception:
        raise ReconcileError('fixed_route_credentials_unavailable') from None


def run(args):
    cfg = dotenv_values(args.source_root / '.env', interpolate=False)
    schema = cfg.get('TURB_DB_SCHEMA') or 'public'
    with psycopg.connect(cfg['DATABASE_URL'], options='-c default_transaction_read_only=on', row_factory=dict_row) as conn:
        candidates, issues, skipped = collect_bindings(conn, schema, args.source_instance)
        keys = decrypt_routes(conn, cfg, schema, candidates) if args.apply else {}
    summary = {'source_instance': args.source_instance, 'mode': 'apply' if args.apply else 'dry_run',
               'captured_at': datetime.now(timezone.utc).isoformat(), 'bindings': len(candidates), 'issues': issues,
               'issue_count': len(issues), 'skipped': skipped,
               'manifest': [{'address_hash': digest(r['item']['address']), 'profile_id': r['profile_id'],
                             'route_hash': digest(r['api_base']), 'credential_ref': r['credential_ref'],
                             'evidence_ref': r['item']['evidence_ref']} for r in candidates],
               'manifest_sha256': digest(json.dumps(candidates, sort_keys=True)), 'results': []}
    write_receipt(args.receipt, summary)
    if not args.apply:
        return summary
    if issues or args.expected_bindings != len(candidates) or args.expected_manifest != summary['manifest_sha256']:
        raise ReconcileError('read_binding_preflight_failed')
    groups = {}
    for row in candidates:
        groups.setdefault((row['api_base'], row['credential_ref']), []).append(row['item'])
    for (original, ref), items in groups.items():
        base = transport_base(original, args.transport_base)
        with requests.Session() as session:
            session.headers.update({'Authorization': 'Bearer ' + keys[ref], 'Accept': 'application/json'})
            who = request_json(session, 'GET', base + '/me')
            if 'service_read_bindings.reconcile.v1' not in (who.get('capabilities') or []) or (who.get('policy') or {}).get('service') != 'openai':
                raise ReconcileError('read_binding_capability_required')
            for start in range(0, len(items), 100):
                batch = items[start:start+100]
                with psycopg.connect(cfg['DATABASE_URL'], options='-c default_transaction_read_only=on', row_factory=dict_row) as conn:
                    fresh, fresh_issues, _ = collect_bindings(conn, schema, args.source_instance)
                if fresh_issues or digest(json.dumps(fresh, sort_keys=True)) != summary['manifest_sha256']:
                    raise ReconcileError('read_binding_source_changed')
                response = request_json(session, 'POST', base + '/service-read-bindings/batch', payload={'items': batch})
                results = response.get('results')
                expected = {r['address']: r for r in batch}
                if not isinstance(results, list) or len(results) != len(batch) or {r.get('address') for r in results} != set(expected):
                    raise ReconcileError('read_binding_response_mismatch')
                for result in results:
                    wanted = expected[result['address']]
                    if result.get('code') == 200 and result.get('binding_id') != wanted['binding_id']:
                        raise ReconcileError('read_binding_response_mismatch')
                    summary['results'].append({'address_hash': digest(result['address']), 'code': result.get('code'), 'error_code': result.get('error_code', '')})
                write_receipt(args.receipt, summary)
    if any(r['code'] != 200 for r in summary['results']):
        raise ReconcileError('read_binding_partial_failure')
    summary['completed'] = True
    write_receipt(args.receipt, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--source-instance', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-bindings', type=int)
    parser.add_argument('--expected-manifest', help='此前 dry-run 的 manifest_sha256，apply 必须一致')
    parser.add_argument('--transport-base', help='仅供维护窗口使用的本机回环 /v1 地址')
    args = parser.parse_args()
    try:
        result = run(args)
    except ReconcileError as exc:
        print(json.dumps({'ok': False, 'error_code': str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_code': 'read_binding_' + type(exc).__name__.lower()}, ensure_ascii=False))
        return 1
    print(json.dumps({k:v for k,v in result.items() if k not in {'results','issues','manifest'}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
