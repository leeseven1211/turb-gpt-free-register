"""Real loopback HTTP lifecycle; synthetic WSGI only, no application or DB import."""
from __future__ import annotations
import http.client
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from core.runtime.http_server import HttpServer

class HttpServerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='turb-http-fixture-')
        self.release=threading.Event();self.entered=threading.Event();self.closed=threading.Event();self.paths=[]
        def app(environ,start_response):
            path=environ['PATH_INFO'];self.paths.append(path)
            if path=='/block':self.entered.set();self.release.wait(5)
            if path=='/upload':body=environ['wsgi.input'].read()
            else:body=b'fixture-body'
            start_response('200 OK',[('Content-Type','application/octet-stream'),('Content-Length',str(len(body)))])
            outer=self
            class Response:
                def __iter__(self):yield body
                def close(self):outer.closed.set()
            return Response()
        self.server=HttpServer(app,host='127.0.0.1',port=0,threads=2,spool_dir=Path(self.directory.name))
        self.address=self.server.start();self.port=int(self.address[1])
    def tearDown(self):
        self.release.set();self.server.stop(timeout=2);self.directory.cleanup()
    def get(self,path='/'):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);conn.request('GET',path);response=conn.getresponse();value=(response.status,response.read());conn.close();return value
    def test_idle_stop_closes_real_listener_channels_loop_and_worker_threads(self):
        self.assertEqual(self.get(),(200,b'fixture-body'));self.assertTrue(self.closed.wait(1))
        self.assertTrue(self.server.stop(timeout=2));status=self.server.status()
        self.assertEqual((status['workers_alive'],status['loop_alive'],status['channels'],status['active_calls'],status['responses_open']),(0,False,0,0,0))
        with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',self.port),timeout=.1)
        self.assertTrue(self.server.stop(timeout=0))
    def test_short_inflight_response_finishes_before_worker_exit_and_new_requests_are_refused(self):
        result=[];reader=threading.Thread(target=lambda:result.append(self.get('/block')));reader.start();self.assertTrue(self.entered.wait(1))
        outcome=[];stopper=threading.Thread(target=lambda:outcome.append(self.server.stop(timeout=2)));stopper.start()
        deadline=time.monotonic()+1
        while not self.server.status()['draining'] and time.monotonic()<deadline:time.sleep(.01)
        self.release.set();reader.join(2);stopper.join(2)
        self.assertEqual(result,[(200,b'fixture-body')]);self.assertEqual(outcome,[True]);self.assertTrue(self.closed.is_set())
    def test_blocked_application_timeout_is_false_with_actual_thread_evidence_then_can_finish(self):
        reader=threading.Thread(target=lambda:self.get('/block'));reader.start();self.assertTrue(self.entered.wait(1));started=time.monotonic()
        self.assertFalse(self.server.stop(timeout=.05));self.assertLess(time.monotonic()-started,.5)
        status=self.server.status();self.assertGreater(status['workers_alive'],0);self.assertEqual(status['active_calls'],1)
        self.release.set();reader.join(2);self.assertTrue(self.server.stop(timeout=2))
    def test_partial_upload_is_discarded_without_entering_wsgi_and_keepalive_cannot_add_work(self):
        sock=socket.create_connection(('127.0.0.1',self.port),timeout=1);sock.sendall(b'POST /upload HTTP/1.1\r\nHost: fixture\r\nContent-Length: 999999\r\n\r\npartial')
        deadline=time.monotonic()+1
        while self.server.status()['buffered_requests']==0 and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.server.stop(timeout=2));self.assertNotIn('/upload',self.paths);self.assertGreaterEqual(self.server.status()['discarded_requests'],1);sock.close()
    def test_queued_wsgi_requests_are_discarded_while_active_requests_finish(self):
        readers=[];results=[]
        for _ in range(2):
            reader=threading.Thread(target=lambda:results.append(self.get('/block')));reader.start();readers.append(reader)
        deadline=time.monotonic()+1
        while self.server.status()['active_calls']<2 and time.monotonic()<deadline:time.sleep(.01)
        queued=socket.create_connection(('127.0.0.1',self.port),timeout=1);queued.sendall(b'GET /never-start HTTP/1.1\r\nHost: fixture\r\n\r\n')
        deadline=time.monotonic()+1
        while self.server.status()['buffered_requests']<3 and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.server.stop(timeout=.03));self.assertNotIn('/never-start',self.paths);self.assertGreaterEqual(self.server.status()['discarded_requests'],1)
        self.release.set()
        for reader in readers:reader.join(2)
        queued.close();self.assertTrue(self.server.stop(timeout=2));self.assertEqual(len(results),2)
    def test_upload_limit_and_iterable_error_close_resources(self):
        self.server.stop(timeout=1)
        closed=threading.Event()
        def broken(_environ,start):
            start('200 OK',[('Content-Type','text/plain')])
            class Broken:
                def __iter__(self):raise RuntimeError('synthetic iterator failure');yield b''
                def close(self):closed.set()
            return Broken()
        self.server=HttpServer(broken,host='127.0.0.1',port=0,threads=1,spool_dir=Path(self.directory.name),max_request_body_size=8)
        self.port=self.server.start()[1]
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=1);conn.request('POST','/',body=b'123456789');response=conn.getresponse();self.assertEqual(response.status,413);response.read();conn.close()
        self.assertEqual(self.get()[0],500);self.assertTrue(closed.wait(1));self.assertTrue(self.server.stop(timeout=2));self.assertEqual(self.server.status()['responses_open'],0)
    def test_file_wrapper_response_preserves_content_and_closes_the_file(self):
        self.server.stop(timeout=1);opened=[]
        def download(environ,start):
            stream=tempfile.TemporaryFile('w+b');stream.write(b'file-body');stream.seek(0);opened.append(stream)
            start('200 OK',[('Content-Type','application/octet-stream'),('Content-Disposition','attachment; filename=fixture.bin'),('Cache-Control','no-store')])
            return environ['wsgi.file_wrapper'](stream)
        self.server=HttpServer(download,host='127.0.0.1',port=0,spool_dir=Path(self.directory.name));self.port=self.server.start()[1]
        self.assertEqual(self.get(),(200,b'file-body'));self.assertTrue(self.server.stop(timeout=2));self.assertTrue(opened[0].closed)
    def test_concurrent_stop_obeys_each_call_deadline(self):
        reader=threading.Thread(target=lambda:self.get('/block'));reader.start();self.assertTrue(self.entered.wait(1))
        first=threading.Thread(target=lambda:self.server.stop(.5));first.start();time.sleep(.02);started=time.monotonic()
        self.assertFalse(self.server.stop(.03));self.assertLess(time.monotonic()-started,.15)
        self.release.set();reader.join(2);first.join(2)
    def test_keepalive_connection_is_closed_at_drain(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=1);conn.request('GET','/');response=conn.getresponse();self.assertEqual(response.read(),b'fixture-body')
        self.assertTrue(self.server.stop(timeout=2));conn.close();self.assertEqual(self.paths,['/'])

if __name__=='__main__':unittest.main()
