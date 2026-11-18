"""F08 repeat real signals during one actual web.main/Waitress HTTP drain."""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]

class HttpSignalTests(unittest.TestCase):
    def start_child(self,timeout):
        directory=tempfile.TemporaryDirectory(prefix='http-entry-signals-')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        child=subprocess.Popen([sys.executable,str(ROOT/'tests/runtime/http_entrypoint_fixture.py'),
                                '--directory',directory.name,'--port',str(port),'--timeout',str(timeout)],
                               cwd=ROOT,env={'PATH':os.defpath,'PYTHON_DOTENV_DISABLED':'1'},
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        messages=queue.Queue();all_messages=[]
        def read():
            for line in child.stdout:
                value=json.loads(line);all_messages.append(value);messages.put(value)
        reader=threading.Thread(target=read,daemon=True);reader.start()
        def cleanup():
            if child.poll() is None:child.kill();child.wait(2)
            reader.join(1);child.stdout.close();child.stderr.close();directory.cleanup()
        self.addCleanup(cleanup)
        self.assertEqual(messages.get(timeout=3)['event'],'started')
        return child,port,messages,all_messages,reader

    def test_repeat_sigterm_and_sigint_finish_short_request_with_one_drain_and_exit_zero(self):
        child,port,messages,all_messages,reader=self.start_child(1)
        result=[];errors=[]
        def request():
            try:
                connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
                connection.request('GET','/short');response=connection.getresponse()
                result.append((response.status,response.read()));connection.close()
            except BaseException as exc:errors.append(type(exc).__name__)
        request_thread=threading.Thread(target=request);request_thread.start()
        self.assertEqual(messages.get(timeout=2)['event'],'entered')
        child.send_signal(signal.SIGTERM)
        while messages.get(timeout=2)['event']!='draining':pass
        child.send_signal(signal.SIGINT)
        request_thread.join(3);child.wait(3);reader.join(1)
        self.assertEqual(child.returncode,0,child.stderr.read())
        self.assertEqual(errors,[]);self.assertEqual(result,[(200,b'synthetic-entrypoint-ok')])
        final=next(value for value in all_messages if value['event']=='final')
        stopped=next(value for value in all_messages if value['event']=='http-stopped')
        self.assertTrue(stopped['clean']);self.assertEqual(stopped['workers_alive'],0)
        self.assertEqual(stopped['channels'],0);self.assertFalse(stopped['loop_alive'])
        self.assertEqual(final['resources']['signal_count'],2)
        self.assertEqual(final['resources']['http_stop_calls'],1)
        self.assertEqual(final['resources']['runtime_stop_calls'],1)
        self.assertTrue(final['resources']['response_closed'])
        self.assertTrue(final['resources']['lock_released']);self.assertTrue(final['listener_released'])
        self.assertEqual(final['events'],['http-stop','runtime-stop','unlock'])
        self.evidence={'pid':child.pid,'port':port,'returncode':child.returncode,
                       'reaped':child.poll() is not None,'messages':list(all_messages)}

    def test_repeated_signals_do_not_reset_long_request_deadline_or_close_live_pool(self):
        timeout=.12
        child,port,messages,all_messages,reader=self.start_child(timeout)
        sock=socket.create_connection(('127.0.0.1',port),timeout=1);self.addCleanup(sock.close)
        sock.sendall(b'GET /long HTTP/1.1\r\nHost: fixture\r\n\r\n')
        self.assertEqual(messages.get(timeout=2)['event'],'entered')
        child.send_signal(signal.SIGTERM)
        while messages.get(timeout=2)['event']!='draining':pass
        child.send_signal(signal.SIGTERM)
        while messages.get(timeout=2).get('sequence')!=2:pass
        child.send_signal(signal.SIGINT)
        child.wait(3);reader.join(1)
        self.assertEqual(child.returncode,3,child.stderr.read())
        final=next(value for value in all_messages if value['event']=='final')
        stopped=next(value for value in all_messages if value['event']=='http-stopped')
        self.assertFalse(stopped['clean']);self.assertEqual(stopped['active_calls'],1)
        self.assertGreater(stopped['workers_alive'],0)
        self.assertLess(stopped['elapsed'],timeout+.15)
        self.assertLess(final['elapsed_since_stop'],timeout+.2)
        self.assertEqual(final['resources']['signal_count'],3)
        self.assertEqual(final['resources']['http_stop_calls'],1)
        self.assertEqual(final['resources']['runtime_stop_calls'],0)
        self.assertTrue(final['resources']['pool_open'])
        self.assertFalse(final['resources']['lock_released'])
        self.assertEqual(final['events'],['http-stop'])
        self.evidence={'pid':child.pid,'port':port,'returncode':child.returncode,
                       'reaped':child.poll() is not None,'messages':list(all_messages)}

if __name__=='__main__':unittest.main()
