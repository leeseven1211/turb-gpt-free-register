"""F05 actual parser/spool resource limits over bounded loopback requests."""
from __future__ import annotations
import http.client
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
from core.runtime.http_server import HttpServer


def fd_count():
    directory=Path('/proc/self/fd')
    if not directory.exists():directory=Path('/dev/fd')
    return len(list(directory.iterdir()))


class HttpLimitTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='http-limits-fault-')
        self.calls=[];self.server=None
        self.baseline_fd=fd_count()
        self.original_tempdir=tempfile.tempdir
        def application(environ,start):
            self.calls.append(environ['PATH_INFO'])
            body=environ['wsgi.input'].read() if environ['REQUEST_METHOD']=='POST' else b'OK'
            start('200 OK',[('Content-Length',str(len(body)))])
            return [body]
        self.application=application

    def tearDown(self):
        if self.server is not None:self.server.stop(timeout=2)
        self.directory.cleanup()

    def start(self,max_body=1024*1024):
        self.server=HttpServer(self.application,host='127.0.0.1',port=0,
                               threads=1,spool_dir=Path(self.directory.name),
                               max_request_body_size=max_body)
        self.port=self.server.start()[1]

    def response(self,sock):
        response=http.client.HTTPResponse(sock);response.begin()
        status=response.status;response.read()
        return status

    def await_condition(self,condition,reason):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if condition():return
            time.sleep(.005)
        self.fail(reason)

    def assert_clean(self):
        self.assertTrue(self.server.stop(timeout=2))
        status=self.server.status()
        self.evidence={'http_status':status,'fd_baseline':self.baseline_fd,
                       'fd_after_stop':fd_count(),'named_files_after_stop':len(list(Path(self.directory.name).iterdir())),
                       'application_calls':list(self.calls),'tempdir_restored':tempfile.tempdir==self.original_tempdir}
        if hasattr(self,'upload_evidence'):self.evidence['upload']=self.upload_evidence
        self.assertEqual((status['workers_alive'],status['loop_alive'],status['channels'],
                          status['active_calls'],status['responses_open'],status['resource_errors']),
                         (0,False,0,0,0,0))
        self.assertEqual(list(Path(self.directory.name).iterdir()),[])
        self.assertEqual(tempfile.tempdir,self.original_tempdir)
        self.assertLessEqual(fd_count(),self.baseline_fd)

    def test_oversized_header_returns_431_without_entering_application(self):
        self.start()
        with socket.create_connection(('127.0.0.1',self.port),timeout=2) as sock:
            sock.sendall(b'GET /never-header HTTP/1.1\r\nHost: fixture\r\nX-Oversized: '+
                         b'h'*(self.server._server.adj.max_request_header_size+1024)+b'\r\n\r\n')
            self.assertEqual(self.response(sock),431)
        self.assertEqual(self.calls,[])
        self.assert_clean()

    def test_fixed_length_and_chunked_oversized_bodies_return_413_without_handler(self):
        self.start(max_body=4096)
        requests=(
            b'POST /never-fixed HTTP/1.1\r\nHost: fixture\r\nContent-Length: 4097\r\n\r\n',
            b'POST /never-chunked HTTP/1.1\r\nHost: fixture\r\nTransfer-Encoding: chunked\r\n\r\n1001\r\n'+b'x'*4097+b'\r\n0\r\n\r\n',
        )
        for request in requests:
            with socket.create_connection(('127.0.0.1',self.port),timeout=2) as sock:
                sock.sendall(request)
                self.assertEqual(self.response(sock),413)
        self.assertEqual(self.calls,[])
        self.assert_clean()

    def test_slow_partial_upload_spills_only_received_bytes_then_closes_spool_and_fds(self):
        # Cross real Waitress 512 KiB overflow; do not complete the declared body.
        opened=[];snapshots=[];original=tempfile.TemporaryFile
        def record_file(*args,**kwargs):
            stream=original(*args,**kwargs);opened.append(stream)
            return stream
        with patch.object(tempfile,'TemporaryFile',record_file):
            self.start(max_body=2*1024*1024)
            threshold=self.server._server.adj.inbuf_overflow
            received=threshold+65536
            with socket.create_connection(('127.0.0.1',self.port),timeout=2) as sock:
                sock.sendall(b'POST /never-partial HTTP/1.1\r\nHost: fixture\r\nContent-Length: 1572864\r\n\r\n')
                remaining=received
                while remaining:
                    size=min(32768,remaining);sock.sendall(b'u'*size);remaining-=size
                    snapshots.append({'sent':received-remaining,'fd_count':fd_count(),'named_files':len(list(Path(self.directory.name).iterdir()))})
                def received_all():
                    for channel in tuple(self.server._server.active_channels.values()):
                        parser=channel.request
                        if parser and parser.body_rcv and len(parser.body_rcv)==received:return True
                    return False
                self.await_condition(received_all,'partial body did not reach real parser')
                self.assertTrue(opened)
                self.assertTrue(all(not stream.closed for stream in opened))
                self.assertEqual(sum(os.fstat(stream.fileno()).st_size for stream in opened),received)
                self.assertEqual(self.calls,[])
                self.assertLessEqual(max(row['fd_count'] for row in snapshots)-self.baseline_fd,16)
                self.upload_evidence={'inbuf_overflow_bytes':threshold,'received_bytes':received,
                                      'declared_body_bytes':1572864,'actual_spool_files':len(opened),
                                      'actual_spool_bytes':sum(os.fstat(stream.fileno()).st_size for stream in opened),
                                      'samples':snapshots}
                self.assertTrue(self.server.stop(timeout=2))
                self.assertTrue(all(stream.closed for stream in opened))
                self.upload_evidence['all_spool_files_closed']=all(stream.closed for stream in opened)
            self.assertEqual(self.calls,[])
            self.assertGreaterEqual(self.server.status()['discarded_requests'],1)
            self.assert_clean()


if __name__=='__main__':unittest.main()
