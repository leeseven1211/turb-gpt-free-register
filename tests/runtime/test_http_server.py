"""Real loopback HTTP lifecycle; synthetic WSGI only, no application or DB import."""
from __future__ import annotations
import http.client
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
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
    def get(self, path='/', *, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        try:
            conn.request('GET', path, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()
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

    def test_slow_requests_report_queue_and_handler_time_separately(self):
        with patch('core.runtime.http_server._SLOW_REQUEST_SECONDS', .08, create=True):
            with self.assertLogs('core.runtime.http_server', level='WARNING') as observed:
                self.assertEqual(self.get(), (200, b'fixture-body'))
                readers = [threading.Thread(target=self.get, args=('/block',)) for _ in range(2)]
                for reader in readers:
                    reader.start()
                deadline = time.monotonic() + 2
                while self.server.status()['active_calls'] < 2 and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertEqual(self.server.status()['active_calls'], 2)
                queued = threading.Thread(target=self.get, args=('/',))
                queued.start()
                deadline = time.monotonic() + 2
                while self.server.status()['buffered_requests'] < 3 and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertEqual(self.server.status()['buffered_requests'], 3)
                time.sleep(.12)
                self.release.set()
                for reader in [*readers, queued]:
                    reader.join(2)
                    self.assertFalse(reader.is_alive())
        records = [record.getMessage() for record in observed.records if 'http_slow_request' in record.getMessage()]
        document = [message for message in records if 'route=文档 ' in message]
        self.assertEqual(len(document), 1)
        self.assertRegex(document[0], r'queue_ms=\d+\.\d handler_ms=\d+\.\d')
        queue_ms, handler_ms = (float(document[0].split(f'{field}=')[1].split()[0])
                                for field in ('queue_ms', 'handler_ms'))
        self.assertGreater(queue_ms, 100)
        self.assertGreater(queue_ms, handler_ms)
        blocked = [message for message in records if 'route=其他 ' in message]
        self.assertEqual(len(blocked), 2)
        for message in blocked:
            queue_ms, handler_ms = (float(message.split(f'{field}=')[1].split()[0])
                                    for field in ('queue_ms', 'handler_ms'))
            self.assertGreater(handler_ms, 100)
            self.assertGreater(handler_ms, queue_ms)

    def test_slow_request_logs_only_fixed_route_labels(self):
        self.assertTrue(self.server.stop(timeout=2))

        def app(_environ, start_response):
            time.sleep(.04)
            start_response('200 OK', [('Content-Length', '0')])
            return [b'']

        self.server = HttpServer(app, host='127.0.0.1', port=0, spool_dir=Path(self.directory.name))
        self.port = self.server.start()[1]
        cases = {
            '/api/extract-workbench/tasks?search=fixture-query': '/api/extract-workbench/tasks',
            '/api/accounts/fixture-account-id?search=fixture-query': '/api/accounts/*',
            '/api/unknown/fixture-account-id?search=fixture-query': '其他 API',
            '/static/fixture-file-name?search=fixture-query': '静态资源',
        }
        with patch('core.runtime.http_server._SLOW_REQUEST_SECONDS', .02, create=True):
            with self.assertLogs('core.runtime.http_server', level='WARNING') as observed:
                for path in cases:
                    with self.subTest(path=path):
                        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
                        try:
                            conn.request('GET', path, headers={'Authorization': 'Bearer fixture-auth'})
                            response = conn.getresponse()
                            self.assertEqual((response.status, response.read()), (200, b''))
                        finally:
                            conn.close()
        messages = [record.getMessage() for record in observed.records]
        self.assertEqual(len(messages), len(cases))
        for message, label in zip(messages, cases.values()):
            self.assertIn(f'route={label} ', message)
            self.assertNotIn('fixture-', message)

    def test_slow_json_and_streamed_body_report_separate_durations(self):
        from flask import jsonify
        from webui.app import create_app

        app = create_app(auth_code="test-auth")
        app.json.default = lambda _value: time.sleep(.04) or "fixture"

        @app.get('/api/timing-test')
        def timing_fixture():
            return jsonify({"value": object()})

        self.assertTrue(self.server.stop(timeout=2))
        self.server = HttpServer(app, host='127.0.0.1', port=0, spool_dir=Path(self.directory.name))
        self.port = self.server.start()[1]
        with patch('core.runtime.http_server._SLOW_REQUEST_SECONDS', .02):
            with self.assertLogs('core.runtime.http_server', level='WARNING') as traced:
                self.assertEqual(self.get('/api/timing-test', headers={"X-Auth-Code": "test-auth"})[0], 200)
                self.assertTrue(self.server.stop(timeout=2))
        values = dict(field.split('=') for field in traced.records[0].getMessage().split() if '=' in field)
        self.assertGreater(float(values['json_ms']), 35)
        self.assertGreaterEqual(float(values['handler_ms']), float(values['json_ms']))

        def streaming(_environ, start_response):
            start_response('200 OK', [])
            def body():
                time.sleep(.04)
                yield b'fixture-stream'
            return body()

        self.server = HttpServer(streaming, host='127.0.0.1', port=0, spool_dir=Path(self.directory.name))
        self.port = self.server.start()[1]
        with patch('core.runtime.http_server._SLOW_REQUEST_SECONDS', .02):
            with self.assertLogs('core.runtime.http_server', level='WARNING') as traced:
                self.assertEqual(self.get('/timing-test'), (200, b'fixture-stream'))
                self.assertTrue(self.server.stop(timeout=2))
        values = dict(field.split('=') for field in traced.records[0].getMessage().split() if '=' in field)
        self.assertGreater(float(values['response_ms']), 35)
        self.assertGreater(float(values['response_ms']), float(values['handler_ms']))

    def test_slow_log_failure_cannot_replace_application_response(self):
        with patch('core.runtime.http_server._SLOW_REQUEST_SECONDS', 0), \
                patch.object(self.server.logger, 'warning', side_effect=OSError('日志写入失败')):
            self.assertEqual(self.get(), (200, b'fixture-body'))

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
