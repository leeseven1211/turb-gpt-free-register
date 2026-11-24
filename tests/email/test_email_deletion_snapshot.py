"""集合删除快照须保持逐邮箱判定，读取次数不随选择数量增长。"""
from datetime import datetime, timedelta
import importlib
import importlib.util
import json
from unittest.mock import patch
import uuid

from core.storage import postgres as pg, records as store, registration
from core.storage.email import deletion, local_imports
from tests.support_pg import PostgresTestCase


class EmailDeletionSnapshotTests(PostgresTestCase):
    def setUp(self):
        store.init()
        registration.reset_ready()
        registration.init()

    def load(self, targets, *, conn):
        name = 'core.storage.email.deletion_snapshot'
        self.assertIsNotNone(importlib.util.find_spec(name), '集合删除安全快照尚未实现')
        return importlib.import_module(name).load_snapshot(targets, conn=conn)

    def pool(self, address, **fields):
        row_id = store.insert_row(store.EMAIL_BUTLER_POOL, {
            'email': address, 'status': 'available', 'used_at': None, **fields})
        return store.get_row(store.EMAIL_BUTLER_POOL, row_id)

    def attempt(self, address, **fields):
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"""INSERT INTO {pg.qualified('registration_attempts')}
                (attempt_uuid,email,email_snapshot,checkpoint,remote_account_state,local_account_state)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                (uuid.uuid4().hex, fields.get('email', address), fields.get('email_snapshot', address),
                 fields.get('checkpoint', 'failed'), fields.get('remote_account_state', 'request_unknown'),
                 fields.get('local_account_state', 'none')))
            return int(cur.fetchone()['id'])

    def assert_equivalent(self, rows, *, expected, unused_inventory=True):
        with store.transaction() as conn:
            snapshot = self.load(rows, conn=conn)
            for row, (confirmed, active, reason) in zip(rows, expected, strict=True):
                with self.subTest(address=row['email']):
                    self.assertEqual(snapshot.confirmed(row), confirmed)
                    self.assertEqual(snapshot.active(row), active)
                    self.assertEqual(snapshot.return_block_reason(row, unused_inventory=unused_inventory), reason)
                    self.assertEqual(snapshot.confirmed(row), local_imports.pool_mutation_protected(row, conn=conn))
                    self.assertEqual(snapshot.active(row), deletion.registration_active(row['email'], conn=conn))
                    self.assertEqual(snapshot.return_block_reason(row, unused_inventory=unused_inventory),
                        deletion.lease_return_block_reason(row['email'], conn=conn, pool=row,
                            account_id=row.get('registered_account_id'), unused_inventory=unused_inventory))

    def test_confirmed_registration_evidence_matches_existing_single_address_checks(self):
        rows = []
        cases = ('pool_token', 'account_token', 'linked_account', 'imported_json', 'imported_object',
                 'checkpoint', 'rebound', 'service_import', 'attempt_local', 'attempt_checkpoint', 'event')
        for kind in cases:
            address = kind + '@example.test'
            row = self.pool(address)
            if kind == 'pool_token':
                row['access_token'] = 'fixture-pool-token'
            elif kind in {'account_token', 'linked_account', 'imported_json', 'imported_object', 'checkpoint', 'rebound'}:
                fields = {'email': 'other@example.test' if kind == 'linked_account' else address}
                if kind in {'account_token', 'linked_account'}:
                    fields['access_token'] = 'fixture-account-token'
                elif kind.startswith('imported'):
                    extra = {'imported_registered': True}
                    fields['extra_json'] = json.dumps(extra) if kind.endswith('json') else extra
                elif kind == 'checkpoint':
                    fields['extra_json'] = {'registration_checkpoint': 'registered'}
                else:
                    fields.update(email='rebound@example.test',
                        original_email_line=address.upper() + '----fixture', email_change_status='success')
                account_id = store.insert_row(store.ACCOUNTS, fields)
                if kind == 'linked_account':
                    row['registered_account_id'] = account_id
            elif kind == 'service_import':
                store.insert_row(store.EMAIL_SERVICE_SYNC, {'event_key': address, 'kind': 'import',
                    'source': 'email_butler', 'address_norm': address, 'state': 'local_only', 'as_registered': True})
            elif kind.startswith('attempt'):
                self.attempt(address, **({'local_account_state': 'persisted'} if kind == 'attempt_local'
                    else {'checkpoint': 'token_obtained'}))
            else:
                attempt_id = self.attempt(address, email='current@example.test', email_snapshot=address.upper())
                with store.transaction() as conn, conn.cursor() as cur:
                    cur.execute(f"""INSERT INTO {pg.qualified('registration_events')}
                        (event_uuid,attempt_id,checkpoint,event_type) VALUES (%s,%s,'failed','core_persisted')""",
                        (uuid.uuid4().hex, attempt_id))
            rows.append(row)
        self.assert_equivalent(rows, expected=[(True, False, 'registration_confirmed')] * len(rows))

    def test_historical_usage_blocks_return_without_becoming_registration_success(self):
        rows = []
        cases = ('placeholder', 'job', 'usage', 'otp', 'local_claim', 'batch_claim',
                 'allocation', 'claim_intent', 'empty_claim_intent', 'attempt', 'duplicate', 'duplicate_used')
        for kind in cases:
            address = kind + '@example.test'
            row = self.pool(address)
            if kind == 'placeholder':
                store.insert_row(store.ACCOUNTS, {'email': address, 'password': 'fixture',
                    'extra_json': 'invalid-json', 'refresh_token': 'mailbox-only'})
            elif kind == 'job':
                store.insert_row(store.JOBS, {'email': address.upper(), 'status': 'failed'})
            elif kind == 'usage':
                store.insert_row(store.EMAIL_USAGE_REPORTS, {'event_key': address, 'operation_id': address,
                    'address_norm': address, 'source': 'email_butler', 'result': 'ok', 'state': 'delivered'})
            elif kind == 'otp':
                self.otp(address, active=False)
            elif kind == 'local_claim':
                store.insert_row(store.LOCAL_EMAIL_CLAIMS, {'acquisition_id': address, 'owner_kind': 'test',
                    'owner_id': address, 'source': 'email_butler', 'pool_id': row['id'],
                    'address_norm': address, 'status': 'failed'})
            elif kind == 'batch_claim':
                store.insert_row(store.REGISTRATION_BATCH_EMAIL_CLAIMS, {'claim_key': address,
                    'batch_id': 'fixture', 'email': address, 'email_source': 'email_butler',
                    'claimed_at': '2026-11-01T00:00:00'})
            elif kind == 'allocation':
                store.insert_row(store.EMAIL_ADDRESS_ALLOCATIONS, {'address': address, 'address_norm': address,
                    'source': 'email_butler', 'parent_kind': 'pool', 'parent_id': row['id'],
                    'parent_address': 'parent@example.test', 'inbox_profile_id': 1, 'strategy': 'plus_tag',
                    'tag': 'fixture', 'state': 'failed'})
            elif kind.endswith('claim_intent'):
                store.insert_row(store.EMAIL_BUTLER_CLAIM_INTENTS, {'acquisition_id': address,
                    'owner_kind': 'test', 'owner_id': address, 'status': 'claimed',
                    'address_norm': '' if kind.startswith('empty') else address,
                    'api_base': 'https://fixture.test', 'credential_ref': 'FIXTURE_KEY',
                    'mailbox': {'email': address}})
            elif kind == 'attempt':
                self.attempt(address, checkpoint='account_confirmed', remote_account_state='confirmed')
            else:
                store.insert_row(store.GENERIC_API_POOL, {'email': address,
                    'status': 'used' if kind == 'duplicate_used' else 'available', 'used_at': None})
            rows.append(row)
        self.assert_equivalent(rows, expected=[(False, False, 'registration_result_unverified')] * len(rows))

    def otp(self, address, *, active):
        store.insert_row(store.EMAIL_OTP_REQUESTS, {'address_key': address, 'owner_kind': 'test',
            'owner_id': address, 'challenge_id': 'fixture', 'send_generation': 1,
            'requested_at': '2026-11-01T00:00:00', 'send_state': 'sent',
            'state': 'active' if active else 'expired', 'submission_state': 'result_unknown',
            'execution_token': 'fixture', 'fence': 1,
            'lease_expires_at': (datetime.now() + timedelta(hours=1 if active else -1)).isoformat()})

    def test_active_execution_and_unused_inventory_keep_original_precedence(self):
        rows = []
        for kind in ('job_active', 'otp_active', 'run_active', 'unused', 'used_at', 'linked_missing'):
            address = kind + '@example.test'
            row = self.pool(address)
            if kind == 'job_active':
                store.insert_row(store.JOBS, {'email': address, 'status': 'pending'})
            elif kind == 'otp_active':
                self.otp(address.upper(), active=True)
            elif kind == 'run_active':
                attempt_id = self.attempt(address)
                with store.transaction() as conn, conn.cursor() as cur:
                    cur.execute(f"""INSERT INTO {pg.qualified('registration_runs')}
                        (run_uuid,attempt_id,run_no,status) VALUES (%s,%s,1,'running')""",
                        (uuid.uuid4().hex, attempt_id))
            elif kind == 'used_at':
                row['used_at'] = '2026-11-01T00:00:00'
            elif kind == 'linked_missing':
                row['registered_account_id'] = 999999
            rows.append(row)
        self.assert_equivalent(rows, expected=[
            (False, True, 'registration_active'), (False, True, 'registration_active'),
            (False, True, 'registration_active'), (False, False, ''),
            (False, False, 'registration_result_unverified'), (False, False, 'registration_result_unverified')])
        self.assert_equivalent([rows[3]], expected=[(False, False, 'registration_result_unverified')],
            unused_inventory=False)

    def test_full_address_identity_does_not_block_sibling_and_empty_address_remains_unverified(self):
        used = self.pool('same+used@example.test')
        sibling = self.pool('same+untouched@example.test')
        store.insert_row(store.EMAIL_USAGE_REPORTS, {'event_key': 'sibling-fixture', 'operation_id': 'fixture',
            'address_norm': used['email'], 'source': 'email_butler', 'result': 'ok', 'state': 'delivered'})
        self.assert_equivalent([used, sibling, {'email': ''}], expected=[
            (False, False, 'registration_result_unverified'), (False, False, ''),
            (False, False, 'registration_result_unverified')])

    def test_optional_event_run_and_attempt_tables_can_be_absent(self):
        row = self.pool('optional@example.test')
        self.attempt(row['email'], checkpoint='completed')
        with store.transaction() as conn, conn.cursor() as cur:
            for table in ('registration_events', 'registration_runs'):
                cur.execute(f'DROP TABLE {pg.qualified(table)} CASCADE')
        self.assert_equivalent([row], expected=[(True, False, 'registration_confirmed')])
        with store.transaction() as conn, conn.cursor() as cur:
            cur.execute(f"DROP TABLE {pg.qualified('registration_attempts')} CASCADE")
        self.assert_equivalent([row], expected=[(False, False, '')])

    def test_pool_token_precedes_active_but_empty_address_precedes_token_for_return(self):
        row = self.pool('active-with-token@example.test', access_token='fixture-pool-token')
        store.insert_row(store.JOBS, {'email': row['email'], 'status': 'running'})
        self.assert_equivalent([row, {'email': '', 'access_token': 'fixture-pool-token'}],
            expected=[(True, True, 'registration_confirmed'), (True, False, 'registration_result_unverified')])

    def test_twenty_targets_use_same_sql_budget_as_one_without_per_item_reads(self):
        from psycopg import Cursor
        rows = [self.pool(f'budget-{number}@example.test') for number in range(20)]
        counts = []
        original = Cursor.execute
        for subset in (rows[:1], rows):
            queries = []
            def measured(cursor, query, params=None, **kwargs):
                queries.append(str(query))
                return original(cursor, query, params, **kwargs)
            with store.transaction() as conn, patch.object(Cursor, 'execute', measured):
                snapshot = self.load(subset, conn=conn)
                for row in subset:
                    self.assertFalse(snapshot.confirmed(row))
                    self.assertFalse(snapshot.active(row))
                    self.assertEqual(snapshot.return_block_reason(row, unused_inventory=True), '')
            counts.append(len(queries))
            self.assertFalse(any('FOR UPDATE' in query.upper() for query in queries))
            self.assertLessEqual(len(queries), 8)
        self.assertEqual(counts[0], counts[1])
