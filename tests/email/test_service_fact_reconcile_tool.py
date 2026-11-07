"""补标必须保留完整地址、稳定证据和逐项远端确认。"""
import unittest

from tools.maintenance.reconcile_butler_service_facts import (
    ReconcileError, build_items, validate_results,
)


class ReconcileServiceFactsTests(unittest.TestCase):
    def row(self, email='mother+child@icloud.com', kind='imported', record='pool:1'):
        return {'email': email, 'fact_type': kind, 'source_record': record,
            'observed_at': '2026-11-07T08:00:00'}

    def build(self, rows):
        return build_items(rows, source_instance='turb-local', source_timezone='Asia/Shanghai')

    def test_full_addresses_and_facts_are_independent_and_replay_stable(self):
        rows = [self.row(), self.row('mother@icloud.com'), self.row(kind='registered')]
        items, issues = self.build(rows)
        self.assertEqual(issues, [])
        self.assertEqual(len(items), 3)
        self.assertEqual(self.build(list(reversed(rows)))[0], items)
        self.assertEqual(len({item['evidence_id'] for item in items}), 3)
        self.assertEqual({item['observed_at'] for item in items}, {'2026-11-07T00:00:00+00:00'})

    def test_imported_never_invents_success_fact(self):
        items, _ = self.build([self.row(), self.row(record='claims:7')])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['fact_type'], 'imported')
        self.assertNotIn('success_count', items[0])

    def test_bad_evidence_is_classified_and_not_sent(self):
        items, issues = self.build([self.row('bad'), {**self.row(), 'observed_at': 'invalid'}])
        self.assertEqual(items, [])
        self.assertEqual({item['error_code'] for item in issues}, {'service_address_invalid', 'service_evidence_time_invalid'})

    def test_response_must_match_exact_address_and_identity(self):
        items, _ = self.build([self.row()])
        result = {**items[0], 'code': 200, 'ever_imported': True, 'permanent': True}
        self.assertEqual(validate_results(items, {'results': [result]})[0]['code'], 200)
        for altered in [dict(result, address='mother@icloud.com'), dict(result, permanent=False), dict(result, evidence_id='other')]:
            with self.assertRaises(ReconcileError):
                validate_results(items, {'results': [altered]})

    def test_registered_receipt_needs_evidence_but_not_imported_flag(self):
        items, _ = self.build([self.row(kind='registered')])
        result = {**items[0], 'code': 200, 'permanent': True, 'ever_imported': False}
        with self.assertRaises(ReconcileError):
            validate_results(items, {'results': [result]})
        result['registration_observed_at'] = items[0]['observed_at']
        self.assertEqual(validate_results(items, {'results': [result]})[0]['code'], 200)

    def test_partial_failure_is_preserved_for_exact_item(self):
        items, _ = self.build([self.row()])
        result = {**items[0], 'code': 409, 'error_code': 'service_evidence_conflict'}
        receipt = validate_results(items, {'results': [result]})[0]
        self.assertEqual(receipt['error_code'], 'service_evidence_conflict')
        self.assertNotIn('address', receipt)
