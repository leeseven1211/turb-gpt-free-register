"""Role management uses exact process facts and injected launch/probe boundaries."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from core.runtime.role_launcher import RoleManager,ProcessInfo,RoleError
class RoleLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='roles-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.runtime=self.root/'run';self.calls=[];self.processes={};self.now=0.
        self.manager=RoleManager(root=self.root,runtime_dir=self.runtime,instance_id='fixture',release='a'*40,python='/python',inspect=self.processes.get,spawn=self.spawn,signal_process=self.signal,probe=lambda role:(True,role!='web'),clock=lambda:self.now,sleep=self.sleep,owns_listener=lambda _pid,_port:True)
    def spawn(self,argv,**kwargs):
        self.calls.append(('spawn',argv,kwargs));pid=100+len(self.processes);self.processes[pid]=ProcessInfo(pid,'start-'+str(pid),str(self.root),' '.join(argv));return pid
    def signal(self,pid,signum):
        self.calls.append(('signal',pid,signum));self.processes.pop(pid,None)
        for role in ('combined','web','worker'):
            value=self.manager.read(role)
            if value and value.get('pid')==pid:
                from core.runtime.role_launcher import atomic_json
                atomic_json(Path(value['exit_path']),{'pid':pid,'nonce':value['nonce'],'clean':True,'exit_code':0})
    def sleep(self,seconds):self.now+=seconds
    def test_legacy_combined_preserves_absent_runtime_directory_bootstrap(self):
        from core.runtime.bootstrap import RuntimeBootstrap
        from unittest.mock import patch
        self.manager.environment={}
        self.manager.start('combined');child_env=self.calls[0][2]['env']
        with patch('core.runtime.bootstrap.subprocess.run') as run:
            def git_result(command, **_kwargs):
                run.return_value.stdout = str(self.root) if '--show-toplevel' in command else 'a' * 40
                return run.return_value
            run.side_effect = git_result
            bootstrap=RuntimeBootstrap.from_environment(project_root=self.root,environment=child_env)
        self.assertTrue(bootstrap.legacy_paths)
        self.assertNotIn('TURB_RUNTIME_DIR',child_env)
    def test_default_combined_and_split_web_argv_never_include_auth_secret(self):
        self.assertEqual(self.manager.start('combined')['state'],'ready');self.assertIn('--mode',self.calls[0][1]);self.assertIn('combined',self.calls[0][1]);self.manager.stop('combined')
        self.assertEqual(self.manager.start('web')['state'],'alive_not_ready');argv=self.calls[-1][1];self.assertIn('waitress',argv);self.assertIn('web',argv);self.assertNotIn('--auth-code',argv)
    def test_restart_web_does_not_signal_or_replace_worker(self):
        worker=self.manager.start('worker');web=self.manager.start('web');self.manager.restart('web');self.assertIn(worker['pid'],self.processes);self.assertEqual([call[1] for call in self.calls if call[0]=='signal'],[web['pid']])
    def test_pid_reuse_or_cwd_command_mismatch_sends_no_signal(self):
        receipt=self.manager.start('worker');pid=receipt['pid'];self.processes[pid]=ProcessInfo(pid,'different-start',str(self.root),'other-command')
        with self.assertRaisesRegex(RoleError,'identity_mismatch'):self.manager.stop('worker')
        self.assertFalse(any(call[0]=='signal' for call in self.calls));self.assertTrue(self.manager.path('worker').exists())
    def test_stop_timeout_is_nonzero_keeps_identity_and_restart_does_not_spawn(self):
        self.manager.start('worker');self.manager.signal_process=lambda *_:None
        with self.assertRaisesRegex(RoleError,'stop_timeout'):self.manager.restart('worker',stop_timeout=.1)
        self.assertTrue(self.manager.path('worker').exists());self.assertEqual(sum(call[0]=='spawn' for call in self.calls),1)
    def test_managed_identity_blocks_manual_start_stop_and_restart(self):
        self.manager.start('web');value=self.manager.read('web');value['source']='systemd';self.manager.write('web',value)
        self.assertTrue(self.manager.status('web')['alive']);self.assertFalse(self.manager.status('web')['ready'])
        for method in (self.manager.start,self.manager.stop,self.manager.restart):
            with self.assertRaisesRegex(RoleError,'managed_use_manager'):method('web')
    def test_existing_unready_worker_must_become_ready_before_start_all_spawns_web(self):
        worker=self.manager.start('worker');self.manager.probe=lambda role:(True,role!='worker')
        with self.assertRaisesRegex(RoleError,'startup_timeout'):self.manager.start_all(timeout=.1)
        self.assertEqual(sum(call[0]=='spawn' for call in self.calls),1);self.assertIn(worker['pid'],self.processes)
    def test_existing_worker_start_waits_for_bounded_readiness(self):
        self.manager.start('worker');attempts=[]
        def probe(_role):attempts.append(1);return True,len(attempts)>=3
        self.manager.probe=probe;self.assertEqual(self.manager.start('worker',timeout=1)['state'],'ready');self.assertEqual(len(attempts),3)
    def test_start_all_does_not_accept_ready_from_a_port_after_expected_web_exits(self):
        web_probes=[]
        def probe(role):
            if role=='worker':return True,True
            web_probes.append(1)
            if len(web_probes)==1:return True,False
            web=self.manager.read('web');self.processes.pop(web['pid'],None)
            return True,True
        self.manager.probe=probe
        with self.assertRaisesRegex(RoleError,'startup_process_exited'):self.manager.start_all(timeout=1)
        self.assertIsNotNone(self.manager.read('worker'))
    def test_foreign_ready_listener_cannot_make_start_or_status_ready(self):
        self.manager.owns_listener=lambda _pid,_port:False
        self.manager.probe=lambda _role:(True,True)
        with self.assertRaisesRegex(RoleError,'startup_timeout'):self.manager.start('web',timeout=.1)
        value=self.manager.status('web');self.assertFalse(value['ready']);self.assertFalse(value['http_alive']);self.assertTrue(value['alive'])
    def test_start_all_keeps_worker_if_web_fails(self):
        self.manager.probe=lambda role:(role!='web',role!='web')
        with self.assertRaisesRegex(RoleError,'startup_timeout'):self.manager.start_all(timeout=.1)
        self.assertTrue(self.manager.path('worker').exists());self.assertIn(self.manager.read('worker')['pid'],self.processes)
if __name__=='__main__':unittest.main()
