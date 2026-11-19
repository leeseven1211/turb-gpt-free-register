"""F03 actual loopback allocations; no app/config/storage/DB import."""
from __future__ import annotations
import errno
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from core.runtime.http_server import HttpServer


class HttpStartupTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='http-startup-fault-')
        self.previous_tempdir=tempfile.tempdir
        self.application_calls=[]
        def application(environ,start):
            self.application_calls.append(environ['PATH_INFO'])
            start('200 OK',[('Content-Length','2')])
            return [b'OK']
        self.server=HttpServer(application,host='127.0.0.1',port=0,
                               threads=2,spool_dir=Path(self.directory.name))

    def tearDown(self):
        # Fixture fallback only: observations/assertions precede this cleanup.
        # Failed start must not leave a loop/socket/thread in the test runner.
        dispatcher=self.server._dispatcher
        if dispatcher is not None:
            dispatcher.begin_drain()
            for thread in dispatcher.actual_threads:
                if thread.ident is not None:thread.join(1)
        self.server._loop_stop.set()
        for channel in list(self.server._map.values()):channel.close()
        if self.server._loop is not None and self.server._loop.ident is not None:self.server._loop.join(1)
        tempfile.tempdir=self.previous_tempdir
        self.directory.cleanup()

    def facts(self):
        return {'map_entries':len(self.server._map),
                'actual_worker_alive':sum(thread.is_alive() for thread in self.server._dispatcher.actual_threads),
                'loop_alive':bool(self.server._loop and self.server._loop.is_alive()),
                'tempdir_restored':tempfile.tempdir==self.previous_tempdir,
                'application_calls':list(self.application_calls)}

    def assert_allocations_released(self):
        self.evidence=self.facts()
        self.assertEqual(self.evidence,{'map_entries':0,'actual_worker_alive':0,
                         'loop_alive':False,'tempdir_restored':True,'application_calls':[]})

    def test_real_bind_conflict_releases_own_allocations_and_preserves_foreign_listener(self):
        with socket.socket() as foreign:
            foreign.bind(('127.0.0.1',0));foreign.listen(1)
            self.server.port=foreign.getsockname()[1]
            with self.assertRaises(OSError) as caught:self.server.start()
            self.assertEqual(caught.exception.errno,errno.EADDRINUSE)
            self.assert_allocations_released()
            with socket.create_connection(foreign.getsockname(),timeout=1) as connected:
                accepted,_address=foreign.accept();accepted.close()
            self.assertTrue(self.server.stop(timeout=.1))

    def test_accept_failure_after_real_worker_allocation_cleans_and_can_be_stopped(self):
        from waitress.server import BaseWSGIServer
        original=BaseWSGIServer.accept_connections
        expected=RuntimeError('synthetic-accept-after-listen-failure')
        def fail_after_listen(value):
            original(value)
            raise expected
        with patch.object(BaseWSGIServer,'accept_connections',fail_after_listen):
            with self.assertRaises(RuntimeError) as caught:self.server.start()
        self.assertIs(caught.exception,expected)
        self.assert_allocations_released()
        self.assertTrue(self.server.stop(timeout=.1))

    def test_create_failure_after_real_socket_and_trigger_allocation_releases_both(self):
        from waitress import server as waitress_server
        original=waitress_server.create_server
        expected=RuntimeError('synthetic-create-after-allocation-failure');allocated=[]
        def fail_after_create(*args,**kwargs):
            value=original(*args,**kwargs);allocated.append(value)
            raise expected
        with patch.object(waitress_server,'create_server',fail_after_create):
            with self.assertRaises(RuntimeError) as caught:self.server.start()
        self.assertIs(caught.exception,expected)
        self.assert_allocations_released()
        self.assertTrue(self.server.stop(timeout=.1))
        with socket.socket() as replacement:
            replacement.bind(('127.0.0.1',int(allocated[0].effective_port)))

    def test_second_worker_start_failure_preserves_original_error_and_releases_allocations(self):
        original=threading.Thread.start
        expected=RuntimeError('synthetic-second-worker-start-failure')
        def fail_second(thread,*args,**kwargs):
            if thread.name=='turb-http-1':raise expected
            return original(thread,*args,**kwargs)
        caught=None
        with patch.object(threading.Thread,'start',fail_second):
            try:self.server.start()
            except BaseException as error:caught=error
        self.assertIs(caught,expected,json.dumps(self.facts(),sort_keys=True))
        self.assert_allocations_released()
        self.assertTrue(self.server.stop(timeout=.1))

    def test_loop_start_failure_cleans_real_workers_without_joining_unstarted_loop(self):
        original=threading.Thread.start
        expected=RuntimeError('synthetic-loop-start-failure')
        def fail_loop(thread,*args,**kwargs):
            if thread.name=='turb-http-loop':raise expected
            return original(thread,*args,**kwargs)
        with patch.object(threading.Thread,'start',fail_loop):
            with self.assertRaises(RuntimeError) as caught:self.server.start()
        self.assertIs(caught.exception,expected)
        self.assert_allocations_released()
        self.assertTrue(self.server.stop(timeout=.1))
        self.assertTrue(self.server.stop(timeout=0))


if __name__=='__main__':unittest.main()
