"""Foreground subprocess signals and slow consumers over actual loopback sockets."""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[2]
class HttpProcessTests(unittest.TestCase):
    def start(self,timeout=1):
        directory=tempfile.TemporaryDirectory(prefix='http-process-')
        child=subprocess.Popen([sys.executable,str(ROOT/'tests/runtime/http_server_fixture.py'),'--spool',directory.name,'--timeout',str(timeout)],cwd=ROOT,env={'PATH':os.defpath,'PYTHON_DOTENV_DISABLED':'1'},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(directory.cleanup)
        def cleanup():
            if child.poll() is None:child.kill();child.wait(2)
            child.stdout.close();child.stderr.close()
        self.addCleanup(cleanup)
        self.assertTrue(select.select([child.stdout],[],[],3)[0]);port=json.loads(child.stdout.readline())['port']
        return child,port
    def test_sigterm_drains_short_request_and_exits_zero_with_no_remaining_http_threads(self):
        child,port=self.start();response=[]
        def get():
            conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3);conn.request('GET','/delay');r=conn.getresponse();response.append((r.status,r.read()));conn.close()
        reader=threading.Thread(target=get);reader.start();self.assertTrue(select.select([child.stdout],[],[],2)[0]);self.assertEqual(json.loads(child.stdout.readline())['entered'],'/delay');child.send_signal(signal.SIGTERM);reader.join(3);out,err=child.communicate(timeout=3)
        self.assertEqual(child.returncode,0,err);self.assertEqual(response,[(200,b'synthetic-http-ok')]);status=json.loads(out.strip().splitlines()[-1]);self.assertTrue(status['clean']);self.assertEqual(status['workers_alive'],0);self.assertFalse(status['loop_alive'])
    def test_blocked_app_exits_three_without_claiming_drain_success(self):
        child,port=self.start(.05);sock=socket.create_connection(('127.0.0.1',port),timeout=1);self.addCleanup(sock.close);sock.sendall(b'GET /blocked HTTP/1.1\r\nHost: fixture\r\n\r\n');self.assertTrue(select.select([child.stdout],[],[],2)[0]);self.assertEqual(json.loads(child.stdout.readline())['entered'],'/blocked');child.send_signal(signal.SIGTERM);out,err=child.communicate(timeout=2)
        self.assertEqual(child.returncode,3);status=json.loads(out.strip().splitlines()[-1]);self.assertFalse(status['clean']);self.assertGreater(status['active_calls'],0);self.assertGreater(status['workers_alive'],0)
    def test_slow_download_consumer_times_out_truthfully_then_process_closes_resources(self):
        child,port=self.start(.05);sock=socket.create_connection(('127.0.0.1',port),timeout=1);self.addCleanup(sock.close);sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024);sock.sendall(b'GET /large HTTP/1.1\r\nHost: fixture\r\n\r\n');self.assertIn(b'200 OK',sock.recv(512));child.send_signal(signal.SIGTERM);out,err=child.communicate(timeout=2)
        self.assertEqual(child.returncode,3);status=json.loads(out.strip().splitlines()[-1]);self.assertFalse(status['clean']);self.assertTrue(status['channels']>0 or status['responses_open']>0)
if __name__=='__main__':unittest.main()
