"""Phase 6 T7 readiness rules against the actual required-component catalog."""
import unittest

from core.runtime import readiness as m


class ReadinessTests(unittest.TestCase):
 def statuses(self):
  c={k:{'started':True,'alive':True} for k in m.REQUIRED_COMPONENTS};c['config_observer'].update(state='applied');c['settlement'].update(healthy=True);return c
 def test_requires_every_critical_thread(self):
  c=self.statuses();self.assertTrue(m.execution_ready(state='running',admission_open=True,owner_valid=True,components=c))
  for name in m.REQUIRED_COMPONENTS:
   bad=dict(c);bad.pop(name);self.assertFalse(m.execution_ready(state='running',admission_open=True,owner_valid=True,components=bad),name)
 def test_missing_c2a_scheduler_is_not_ready_to_resume_repairs(self):
  c=self.statuses();c['c2a_monitor']={'started':True,'alive':False,'disabled':True}
  self.assertFalse(m.execution_ready(state='running',admission_open=True,owner_valid=True,components=c))
 def test_disabled_periodic_is_healthy_only_if_thread_alive(self):
  self.assertTrue(m.component_ready('at_refresher',{'started':True,'alive':True,'disabled':True}))
  self.assertFalse(m.component_ready('at_refresher',{'started':True,'alive':False,'disabled':True}))
 def test_local_compatibility_uses_worker_pid(self):
  value=m.compatibility_status(mode='web',source='postgres_worker',ready=True,state='running',identity={'pid':123},components={},config={})
  self.assertEqual(value['pid'],123);self.assertEqual(value['source'],'postgres_worker')
 def test_drain_and_lost_owner_are_never_ready(self):
  for state,gate,owner in [('draining',False,True),('running',True,False),('running',False,True)]:self.assertFalse(m.execution_ready(state=state,admission_open=gate,owner_valid=owner,components=self.statuses()))
if __name__=='__main__':unittest.main()
