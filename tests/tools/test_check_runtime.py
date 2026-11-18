from __future__ import annotations
import unittest
from tools.check_runtime import evaluate_worker
class WorkerCheckTests(unittest.TestCase):
    def test_requires_same_identity_release_fresh_generation_config_and_component_truth(self):
        record={'instance_id':'fixture','release':'a'*40,'mode':'worker','pid':42,'process_start':'start','owner_nonce':'nonce','generation':1,'fresh':True,'ready':True,'state':'running','applied_db_revision':3,'local_snapshot_revision':3,'components':{}}
        expected={'instance_id':'fixture','release':'a'*40,'pid':42,'process_start':'start'}
        self.assertTrue(evaluate_worker(record,expected,3,components_ready=lambda _:True)['ok'])
        for key,value in [('release','b'*40),('process_start','other'),('fresh',False),('generation',0),('applied_db_revision',2),('local_snapshot_revision',None),('owner_nonce','')]:
            with self.subTest(key=key):self.assertFalse(evaluate_worker({**record,key:value},expected,3,components_ready=lambda _:True)['ok'])
        self.assertFalse(evaluate_worker(record,expected,3,components_ready=lambda _:False)['ok'])
    def test_local_snapshot_revision_is_not_in_database_revision_domain(self):
        record={'instance_id':'fixture','release':'a'*40,'mode':'worker','pid':42,'process_start':'Mon Nov  2 12:00:00 2026','owner_nonce':'nonce','generation':1,'fresh':True,'ready':True,'state':'running','applied_db_revision':100,'local_snapshot_revision':1,'components':{}}
        self.assertTrue(evaluate_worker(record,{'instance_id':'fixture','release':'a'*40,'pid':42,'process_start':'Mon Nov  2 12:00:00 2026'},100,components_ready=lambda _:True)['ok'])
    def test_absent_or_malformed_status_stays_not_ready_without_private_payload(self):
        result=evaluate_worker({'private':'sentinel'},{'instance_id':'fixture','release':'a'*40},0)
        self.assertFalse(result['ok']);self.assertNotIn('sentinel',str(result))
if __name__=='__main__':unittest.main()
