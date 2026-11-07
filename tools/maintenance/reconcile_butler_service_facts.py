#!/usr/bin/env python3
"""只读提取 Turb 证据，通过 Butler API 幂等补充永久服务事实。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from dotenv import dotenv_values
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import requests


class ReconcileError(RuntimeError):
    """只暴露分类，不携带数据库连接或服务凭据。"""


POOL_TABLES = (
    'email_pool_butler', 'email_pool_icloud_hide', 'email_pool_outlook',
    'email_pool_generic_api', 'email_pool_domain',
)


def address(value):
    value = str(value or '').strip().lower()
    if not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+', value):
        raise ReconcileError('service_address_invalid')
    return value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def observed_at(value, source_timezone):
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(source_timezone))
        return dt.astimezone(timezone.utc).isoformat(timespec='seconds')
    except (TypeError, ValueError, KeyError):
        raise ReconcileError('service_evidence_time_invalid') from None


def extra_json(value):
    if isinstance(value, dict):
        return value
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def build_items(rows, *, source_instance, source_timezone):
    """每个原始证据使用稳定标识；绝不以标签或领取状态推断成功。"""
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', source_instance):
        raise ReconcileError('source_instance_invalid')
    candidates = defaultdict(list)
    issues = []
    for row in rows:
        try:
            target = address(row['email'])
            timestamp = observed_at(row['observed_at'], source_timezone)
        except ReconcileError as exc:
            issues.append({'record': row['source_record'], 'error_code': str(exc)})
            continue
        kind = row['fact_type']
        if kind not in {'imported', 'registered'}:
            raise ReconcileError('service_fact_type_invalid')
        candidates[(target, kind)].append((timestamp, str(row['source_record'])))
    items = []
    for (target, kind), facts in sorted(candidates.items()):
        # 原始创建时间不随重跑变化；选最早事实，证据 ID 包含原记录和完整地址。
        timestamp, record = min(facts)
        evidence_id = 'turb:' + digest(f'{source_instance}:{record}:{target}:{kind}')
        items.append({'address': target, 'service': 'openai', 'fact_type': kind,
            'evidence_id': evidence_id, 'source_instance': source_instance,
            'source_record': record, 'observed_at': timestamp})
    return items, issues


def collect(conn, schema):
    """仅 SELECT，所有来源均为权威表；不加载应用生产写入保护开关。"""
    rows = []
    qname = lambda name: sql.Identifier(schema, name)
    with conn.cursor() as cur:
        cur.execute('SELECT current_setting(\'transaction_read_only\') AS mode')
        if cur.fetchone()['mode'] != 'on':
            raise ReconcileError('readonly_transaction_required')
        cur.execute(sql.SQL('SELECT id,email,created_at,account_has_access_token,data->>\'extra_json\' AS extra_json, '
            'split_part(COALESCE(data->>\'original_email_line\',\'\'),\'----\',1) AS original_email FROM {}').format(qname('registered_accounts')))
        accounts = list(cur.fetchall())
        for account in accounts:
            base = {'source_record': f"registered_accounts:{account['id']}", 'email': account['email'], 'observed_at': account['created_at']}
            rows.append({**base, 'fact_type': 'imported'})
            extra = extra_json(account['extra_json'])
            if account['account_has_access_token'] or extra.get('registration_checkpoint') in {'registered', 'core_persisted'}:
                rows.append({**base, 'fact_type': 'registered'})
            if account['original_email'] and account['original_email'].strip().lower() != account['email'].strip().lower():
                rows.append({**base, 'source_record': base['source_record'] + ':original', 'email': account['original_email'], 'fact_type': 'imported'})
        for table in POOL_TABLES:
            cur.execute(sql.SQL('SELECT id,email,created_at FROM {}').format(qname(table)))
            rows.extend({'source_record': f"{table}:{r['id']}", 'email': r['email'], 'observed_at': r['created_at'], 'fact_type': 'imported'} for r in cur.fetchall())
        for table in ('local_email_claims', 'email_address_allocations', 'email_butler_import_items'):
            where = sql.SQL(" WHERE status='imported'") if table == 'email_butler_import_items' else sql.SQL('')
            cur.execute(sql.SQL('SELECT id,address_norm AS email,created_at FROM {}{}').format(qname(table), where))
            rows.extend({'source_record': f"{table}:{r['id']}", 'email': r['email'], 'observed_at': r['created_at'], 'fact_type': 'imported'} for r in cur.fetchall())
        cur.execute(sql.SQL("SELECT id,COALESCE(NULLIF(email_snapshot,''),email) AS email,created_at "
            "FROM {} WHERE local_account_state='persisted' AND remote_account_state='confirmed'").format(qname('registration_attempts')))
        for row in cur.fetchall():
            base = {'source_record': f"registration_attempts:{row['id']}", 'email': row['email'], 'observed_at': row['created_at']}
            rows.extend({**base, 'fact_type': kind} for kind in ('imported', 'registered'))
    return rows


def connection_values(conn, cfg, schema):
    """只解密指定 Butler 连接，明文仅留在进程内。"""
    values = {key: cfg.get(key, '') for key in ('EMAIL_BUTLER_API_BASE', 'EMAIL_BUTLER_API_KEY')}
    with conn.cursor() as cur:
        cur.execute(sql.SQL('SELECT key,value_encrypted FROM {} WHERE key=ANY(%s)').format(sql.Identifier(schema, 'runtime_config_values')), (list(values),))
        encrypted = cur.fetchall()
    if encrypted:
        try:
            cipher = Fernet(cfg['TURB_CONFIG_ENCRYPTION_KEY'].encode())
            values.update({r['key']: cipher.decrypt(r['value_encrypted'].encode()).decode() for r in encrypted})
        except Exception:
            raise ReconcileError('service_credentials_unavailable') from None
    base = str(values['EMAIL_BUTLER_API_BASE'] or '').rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password:
        raise ReconcileError('service_endpoint_invalid')
    if not values['EMAIL_BUTLER_API_KEY']:
        raise ReconcileError('service_credentials_unavailable')
    return base, values['EMAIL_BUTLER_API_KEY']


def transport_base(original, override=None):
    """仅允许以显式本机回环维护端口代替原传输地址。"""
    base = str(override or original).rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReconcileError('service_endpoint_invalid')
    if override and (parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.path != '/v1'):
        raise ReconcileError('maintenance_transport_must_be_loopback')
    return base


def request_json(session, method, url, *, payload=None):
    try:
        response = session.request(method, url, json=payload, timeout=(10, 45))
        result = response.json()
    except requests.RequestException:
        raise ReconcileError('service_fact_transport_unconfirmed') from None
    except ValueError:
        raise ReconcileError('service_fact_response_invalid') from None
    if response.status_code >= 400:
        code = str(result.get('error_code') or f'http_{response.status_code}') if isinstance(result, dict) else f'http_{response.status_code}'
        raise ReconcileError(code if re.fullmatch(r'[a-z0-9_]+', code) else 'service_fact_rejected')
    if not isinstance(result, dict) or result.get('code') != 200:
        raise ReconcileError('service_fact_response_invalid')
    return result


def validate_results(items, response):
    expected = {row['evidence_id']: row for row in items}
    results = response.get('results')
    if not isinstance(results, list) or len(results) != len(items):
        raise ReconcileError('service_fact_response_mismatch')
    seen = set()
    output = []
    for result in results:
        if not isinstance(result, dict) or result.get('evidence_id') not in expected or result['evidence_id'] in seen:
            raise ReconcileError('service_fact_response_mismatch')
        wanted = expected[result['evidence_id']]
        seen.add(result['evidence_id'])
        if result.get('address') != wanted['address'] or result.get('service') != 'openai':
            raise ReconcileError('service_fact_response_mismatch')
        ok = result.get('code') == 200
        if ok and (result.get('permanent') is not True or wanted['fact_type'] == 'imported' and result.get('ever_imported') is not True):
            raise ReconcileError('service_fact_unconfirmed')
        if ok and wanted['fact_type'] == 'registered' and not result.get('registration_observed_at'):
            raise ReconcileError('service_registration_fact_unconfirmed')
        output.append({'address_hash': digest(wanted['address']), 'evidence_id': wanted['evidence_id'],
            'fact_type': wanted['fact_type'], 'code': result.get('code'),
            'error_code': str(result.get('error_code') or '') if not ok else ''})
    return output


def write_receipt(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('w', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    temporary.replace(path)


def run(args):
    cfg = dotenv_values(args.source_root / '.env', interpolate=False)
    if not cfg.get('DATABASE_URL'):
        raise ReconcileError('source_database_missing')
    schema = cfg.get('TURB_DB_SCHEMA') or 'public'
    with psycopg.connect(cfg['DATABASE_URL'], options='-c default_transaction_read_only=on', row_factory=dict_row) as conn:
        rows = collect(conn, schema)
        items, issues = build_items(rows, source_instance=args.source_instance, source_timezone=args.source_timezone)
        connection = connection_values(conn, cfg, schema) if args.apply else None
    summary = {'source_instance': args.source_instance, 'mode': 'apply' if args.apply else 'dry_run',
        'captured_at': datetime.now(timezone.utc).isoformat(), 'addresses': len({r['address'] for r in items}),
        'facts': len(items), 'fact_types': dict(Counter(r['fact_type'] for r in items)), 'issue_count': len(issues), 'issues': issues,
        'manifest_sha256': digest(json.dumps(items, sort_keys=True, ensure_ascii=False)), 'results': []}
    write_receipt(args.receipt, summary)
    if not args.apply:
        return summary
    if issues:
        raise ReconcileError('service_evidence_preflight_failed')
    if (args.expected_facts is None or args.expected_facts != len(items)
            or args.expected_manifest != summary['manifest_sha256']):
        raise ReconcileError('service_fact_count_changed')
    base, key = connection
    base = transport_base(base, args.transport_base)
    session = requests.Session()
    session.headers.update({'Authorization': 'Bearer ' + key, 'User-Agent': 'Turb-Service-Facts-Reconcile/1.0', 'Accept': 'application/json'})
    who = request_json(session, 'GET', base + '/me')
    capabilities = set(who.get('capabilities') or [])
    required = {'service_facts.permanent.v1', 'service_facts.reconcile.v1'}
    if not required.issubset(capabilities) or str((who.get('policy') or {}).get('service') or '').lower() != 'openai':
        raise ReconcileError('service_fact_capability_required')
    for start in range(0, len(items), args.batch_size):
        batch = items[start:start + args.batch_size]
        result = request_json(session, 'POST', base + '/service-facts/batch', payload={'items': batch})
        summary['results'].extend(validate_results(batch, result))
        write_receipt(args.receipt, summary)
    if any(row['code'] != 200 for row in summary['results']):
        raise ReconcileError('service_fact_partial_failure')
    summary['completed'] = True
    write_receipt(args.receipt, summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--source-instance', required=True)
    parser.add_argument('--source-timezone', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-facts', type=int)
    parser.add_argument('--expected-manifest', help='此前 dry-run 的 manifest_sha256，apply 必须一致')
    parser.add_argument('--transport-base', help='仅供维护窗口使用的本机回环 /v1 地址')
    parser.add_argument('--batch-size', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 200:
        parser.error('每批数量必须为 1 至 200')
    try:
        result = run(args)
    except ReconcileError as exc:
        print(json.dumps({'ok': False, 'error_code': str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_code': 'reconcile_' + type(exc).__name__.lower()}, ensure_ascii=False))
        return 1
    print(json.dumps({key: value for key, value in result.items() if key not in {'results', 'issues'}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
