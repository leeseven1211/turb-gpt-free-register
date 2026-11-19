"""Real child process identity/control with a synthetic sleeper, no product entrypoint."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from core.runtime.role_launcher import RoleManager,RoleError,inspect_process
class RealRoleTests(unittest.TestCase):
    def test_inspected_identity_and_term_stop_are_role_scoped(self):
        with tempfile.TemporaryDirectory(prefix='role-real-') as directory:
            root=Path(directory).resolve();children=[]
            def spawn(argv,**kwargs):
                script="import signal,time;signal.signal(signal.SIGTERM,lambda *_:exit(0));print('ready',flush=True);time.sleep(30)"
                child=subprocess.Popen([sys.executable,'-c',script],cwd=root,env={'PATH':os.defpath},stdout=subprocess.PIPE,text=True);children.append(child);child.stdout.readline();return child.pid
            manager=RoleManager(root=root,runtime_dir=root/'run',instance_id='fixture',release='a'*40,python=sys.executable,spawn=spawn,probe=lambda _:(True,True),owns_listener=lambda _pid,_port:True)
            try:
                worker=manager.start('worker');web=manager.start('web');self.assertEqual(inspect_process(worker['pid']).cwd,str(root));stopped=manager.stop('web',timeout=2)
                self.assertEqual(stopped['state'],'stopped');self.assertFalse(stopped['clean']);self.assertIsNotNone(inspect_process(worker['pid']))
            finally:
                for child in children:
                    if child.poll() is None:child.terminate()
                    child.wait(2);child.stdout.close()
    def test_listener_ownership_is_bound_to_real_pid_and_port(self):
        import socket
        from core.runtime.role_launcher import owns_listener
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen();port=listener.getsockname()[1]
            self.assertTrue(owns_listener(os.getpid(),port));self.assertFalse(owns_listener(os.getppid(),port));self.assertFalse(owns_listener(os.getpid(),port+1 if port<65535 else port-1))
    def test_owner_heartbeat_start_remains_raw_ps_not_pid_reuse_token(self):
        actual=inspect_process(os.getpid())
        expected=subprocess.run(['ps','-p',str(os.getpid()),'-o','lstart='],capture_output=True,text=True,check=True).stdout.strip()
        self.assertEqual(actual.owner_process_start,expected)
    def test_reused_pid_never_receives_signal_even_when_process_exists(self):
        with tempfile.TemporaryDirectory(prefix='role-reuse-') as directory:
            root=Path(directory).resolve();manager=RoleManager(root=root,runtime_dir=root/'run',instance_id='fixture',release='a'*40,python=sys.executable,probe=lambda _:(True,True),owns_listener=lambda _pid,_port:True)
            current=inspect_process(os.getpid());manager.write('worker',{'pid':current.pid,'process_start':'different','cwd':current.cwd,'command':current.command,'role':'worker','instance_id':'fixture','release':'a'*40,'source':'manual'})
            with self.assertRaisesRegex(RoleError,'identity_mismatch'):manager.stop('worker',timeout=.01)
if __name__=='__main__':unittest.main()
