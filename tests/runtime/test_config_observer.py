from __future__ import annotations
import threading
import time
import unittest
from core.runtime import context
from core.runtime import config_observer as observer_module

class ObserverLifecycleTests(unittest.TestCase):
    def wait(self, predicate, timeout=1):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.002)
        self.fail('condition did not become true')

    def make(self, *, revision=None, read=None, apply=None, max_age=.2):
        gate=context.AdmissionGate()
        gate.block('owner_lost')
        publications=[]
        def publish(values, db_revision, *, before_publish):
            before_publish()
            publications.append((dict(values),db_revision))
            return db_revision, len(publications)+7
        observer=observer_module.ConfigObserver(
            admission=gate,
            read_revision=revision or (lambda: 12),
            read_snapshot=read or (lambda: ({'A':'fresh'},12)),
            apply_snapshot=apply or publish,
            poll_interval=.01, freshness_budget=max_age,
        )
        self.addCleanup(lambda: observer.stop(timeout=1))
        return observer, gate, publications

    def test_legacy_inactive_bootstrap_is_only_allowed_with_explicit_adapter(self):
        gate=context.AdmissionGate()
        observer=observer_module.ConfigObserver(admission=gate,read_revision=lambda:0,
            read_snapshot=lambda:(None,0),apply_snapshot=lambda *a,**k:self.fail('must not publish'),
            inactive_snapshot=lambda:7,poll_interval=.01,freshness_budget=.2)
        self.addCleanup(lambda:observer.stop(timeout=1))
        observer.start()
        self.wait(lambda:observer.status()['state']=='applied')
        self.assertEqual(observer.status()['applied_db_revision'],0)
        self.assertEqual(observer.status()['local_snapshot_revision'],7)
        self.assertNotIn('config',gate.reasons())

    def test_starts_background_poll_and_preserves_other_gate_reasons(self):
        observer,gate,published=self.make()
        observer.start()
        self.wait(lambda: observer.status()['applied_db_revision']==12)
        self.assertEqual(observer.status()['local_snapshot_revision'],8)
        self.assertEqual(gate.reasons(),('owner_lost','startup'))
        time.sleep(.04)
        self.assertEqual(len(published),1)
        self.assertTrue(observer.stop(timeout=1))
        self.assertEqual(observer.status()['state'],'stopped')
        self.assertFalse(observer.status()['alive'])
        self.assertIn('config',gate.reasons())

    def test_read_exception_keeps_applied_revision_and_retry_restores_only_config(self):
        current=[12]
        def revision():
            if current[0] is None: raise RuntimeError('SECRET=hidden')
            return current[0]
        observer,gate,published=self.make(revision=revision,read=lambda: ({'A':'new'},current[0]))
        observer.start()
        self.wait(lambda: observer.status()['applied_db_revision']==12)
        current[0]=None
        self.wait(lambda: observer.status()['error_code']=='config_read_failed')
        self.assertEqual(observer.status()['applied_db_revision'],12)
        self.assertNotIn('SECRET',repr(observer.status()))
        self.assertIn('config',gate.reasons())
        current[0]=13
        self.wait(lambda: observer.status()['applied_db_revision']==13)
        self.assertNotIn('config',gate.reasons())
        self.assertIn('owner_lost',gate.reasons())

    def test_regressed_database_revision_never_unblocks_or_overwrites(self):
        current=[12]
        observer,gate,published=self.make(revision=lambda:current[0])
        observer.start()
        self.wait(lambda: observer.status()['applied_db_revision']==12)
        current[0]=11
        self.wait(lambda: observer.status()['error_code']=='config_revision_regressed')
        self.assertIn('config',gate.reasons())
        self.assertEqual(len(published),1)

    def test_blackholed_read_is_blocked_by_independent_watchdog(self):
        entered,release=threading.Event(),threading.Event()
        self.addCleanup(release.set)
        def revision():
            entered.set()
            release.wait(1)
            return 12
        observer,gate,published=self.make(revision=revision,max_age=.06)
        observer.start()
        self.assertTrue(entered.wait(1))
        self.wait(lambda: observer.status()['error_code']=='config_timeout')
        self.assertIn('config',gate.reasons())
        self.assertFalse(observer.stop(timeout=.001))
        self.assertEqual(observer.status()['state'],'stop_incomplete')
        release.set()
        self.assertTrue(observer.stop(timeout=1))
        self.assertEqual(published,[])

    def test_apply_hang_and_stop_refuses_late_publication(self):
        entered,release=threading.Event(),threading.Event()
        self.addCleanup(release.set)
        published=[]
        def apply(values,revision,*,before_publish):
            entered.set()
            release.wait(1)
            before_publish()
            published.append(revision)
            return revision,1
        observer,gate,_=self.make(apply=apply,max_age=.06)
        observer.start()
        self.assertTrue(entered.wait(1))
        self.wait(lambda: observer.status()['error_code']=='config_timeout')
        self.assertFalse(observer.stop(timeout=.001))
        release.set()
        self.assertTrue(observer.stop(timeout=1))
        self.assertEqual(published,[])
        self.assertIsNone(observer.status()['applied_db_revision'])

    def test_concurrent_save_between_probe_and_snapshot_applies_newer_pair(self):
        observer,gate,published=self.make(read=lambda: ({'A':'newer'},13))
        observer.start()
        self.wait(lambda: observer.status()['applied_db_revision']==13)
        self.assertEqual(published[0],({'A':'newer'},13))

    def test_apply_failure_does_not_advance_revision(self):
        def fail(*args,**kwargs): raise RuntimeError('secret=do-not-copy')
        observer,gate,_=self.make(apply=fail)
        observer.start()
        self.wait(lambda: observer.status()['error_code']=='config_apply_failed')
        self.assertIsNone(observer.status()['applied_db_revision'])
        self.assertIn('config',gate.reasons())
        self.assertNotIn('secret',repr(observer.status()))

    def test_inactive_snapshot_keeps_admission_blocked(self):
        observer,gate,published=self.make(read=lambda:(None,12))
        observer.start()
        self.wait(lambda: observer.status()['error_code']=='config_inactive')
        self.assertEqual(published,[])
        self.assertIn('config',gate.reasons())

    def test_stop_idempotent_and_restart_requires_new_observer(self):
        observer,_,_=self.make()
        observer.start()
        observer.start()
        self.assertTrue(observer.stop(timeout=1))
        self.assertTrue(observer.stop(timeout=1))
        with self.assertRaisesRegex(RuntimeError,'restart'):
            observer.start()

if __name__=='__main__': unittest.main()
