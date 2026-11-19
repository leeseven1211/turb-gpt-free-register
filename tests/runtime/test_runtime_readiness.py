"""Readiness consumes the real flattened Worker repository contract."""
import unittest
from core.runtime import readiness
from core.runtime.context import AdmissionGate, RuntimeContext
from core.runtime import execution_access
from unittest.mock import patch

class RuntimeReadinessTests(unittest.TestCase):
    def components(self):
        values={key:{'started':True,'alive':True} for key in readiness.REQUIRED_COMPONENTS}
        values['config_observer'].update(state='applied')
        values['settlement'].update(healthy=True)
        return values

    def record(self):
        return dict(state='running',ready=True,owner_nonce='nonce',generation=3,
                    pid=41,host='fixture',process_start='start',mode='worker',release='sha',
                    applied_db_revision=9,local_snapshot_revision=4,age_seconds=1,
                    components=self.components())

    def test_real_flattened_record_projects_worker_identity_and_config(self):
        value=readiness.remote_status(self.record(),expected_release='sha',required_db_revision=9)
        self.assertTrue(value['ready']);self.assertEqual(value['pid'],41)
        self.assertEqual(value['config_observer']['applied_db_revision'],9)
        self.assertTrue(value['registration_dispatcher']['alive'])

    def test_stale_revision_release_missing_and_dead_component_are_not_ready(self):
        for change in ({'ready':False},{'applied_db_revision':8},{'release':'old'},
                       {'owner_nonce':''},{'generation':None},{'components':{}}):
            record=self.record();record.update(change)
            self.assertFalse(readiness.remote_status(record,expected_release='sha',required_db_revision=9)['ready'])

    def test_disabled_scheduler_needs_a_live_thread(self):
        self.assertTrue(readiness.component_ready('at_refresher',dict(started=True,alive=True,disabled=True)))
        self.assertFalse(readiness.component_ready('at_refresher',dict(started=True,alive=False,disabled=True)))

    def test_resource_support_survives_draining_but_not_owner_loss(self):
        context=RuntimeContext('worker')
        context.admission.unblock('startup');context.admission.block('draining')
        with patch.object(execution_access,'_context',return_value=context),patch.object(execution_access,'execution_allowed',return_value=False),patch.object(execution_access,'execution_owner_valid',return_value=True):
            self.assertTrue(execution_access.execution_support_allowed())
            context.admission.block('owner_lost')
            self.assertFalse(execution_access.execution_support_allowed())

if __name__=='__main__':unittest.main()
