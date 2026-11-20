"""Audited Waitress 3.0.2 lifecycle adapter; no Flask/config/storage imports.

Private seams are deliberately version fenced: server._map/trigger, channel parser,
requests/outbuf locks and dispatcher queue. shutdown()'s bool is never stop evidence.
"""
from __future__ import annotations
from importlib.metadata import version
import logging
import math
from pathlib import Path
import tempfile
import threading
import time

from .request_timing import RequestTiming, current_request_timing

AUDITED_WAITRESS_VERSION = '3.0.2'
_SLOW_REQUEST_SECONDS = 1.0
_OBSERVED_API_PATHS = frozenset({
    '/api/accounts', '/api/accounts/inspections', '/api/accounts/plan-check-status',
    '/api/bulk/batches', '/api/bulk/catalog', '/api/bulk/query-facets',
    '/api/capabilities', '/api/codex', '/api/config', '/api/dashboard',
    '/api/email-derivation/allocations', '/api/email-derivation/summary',
    '/api/extract-workbench/analytics', '/api/extract-workbench/batches',
    '/api/extract-workbench/config', '/api/extract-workbench/summary', '/api/extract-workbench/tasks',
    '/api/jobs', '/api/operations', '/api/outlook', '/api/proxy-pool',
    '/api/proxy-traffic/current', '/api/proxy-traffic/history', '/api/proxy-traffic/summary',
    '/api/proxy-traffic/traffic', '/api/summary', '/api/ui-settings',
})
_OBSERVED_API_GROUPS = {
    '/api/accounts/': '/api/accounts/*',
    '/api/bulk/': '/api/bulk/*',
    '/api/extract-workbench/': '/api/extract-workbench/*',
    '/api/jobs/': '/api/jobs/*',
    '/api/operations/': '/api/operations/*',
}


def _request_route_label(path: str) -> str:
    """用固定值关联浏览器观察，路径参数和静态文件名不进入日志。"""
    if path in {'/', '/login'}:
        return '文档'
    if path in {'/healthz', '/readyz'}:
        return path
    if path.startswith('/static/') or path == '/favicon.ico':
        return '静态资源'
    if path in _OBSERVED_API_PATHS:
        return path
    if path.startswith('/api/'):
        for prefix, label in _OBSERVED_API_GROUPS.items():
            if path.startswith(prefix):
                return label
        return '其他 API'
    return '其他'


class HttpServer:
    def __init__(self, application, *, host: str, port: int, spool_dir: Path,
                 threads: int = 4, logger=None, max_request_body_size: int = 1073741824):
        if not isinstance(host,str) or not host or any(char.isspace() for char in host):
            raise ValueError('http_host_invalid')
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('http_port_invalid')
        if type(threads) is not int or not 1 <= threads <= 128:
            raise ValueError('http_threads_invalid')
        self.application=application;self.host=host;self.port=port;self.threads=threads
        self.spool_dir=Path(spool_dir);self.logger=logger or logging.getLogger(__name__)
        self.max_request_body_size=max_request_body_size
        self._lock=threading.RLock();self._stop_lock=threading.Lock()
        self._draining=threading.Event();self._loop_stop=threading.Event();self._drain_applied=threading.Event()
        self._server=None;self._dispatcher=None;self._loop=None;self._map={}
        self._state='new';self._active_calls=0;self._responses=set();self._discarded=0
        self._resource_errors=0;self._listener_closed=False;self._previous_tempdir=tempfile.tempdir

    def _tracked_app(self,environ,start_response):
        with self._lock:self._active_calls+=1
        timing = current_request_timing.get()
        if timing is not None:
            timing.route = _request_route_label(environ.get('PATH_INFO', ''))
        started_at = time.monotonic()
        try:response=self.application(environ,start_response)
        finally:
            if timing is not None:
                timing.handler_finished = time.monotonic()
                timing.handler_seconds = timing.handler_finished - started_at
            with self._lock:self._active_calls-=1
        token=object()
        with self._lock:self._responses.add(token)
        owner=self
        def closed():
            with owner._lock:owner._responses.discard(token)
        # Preserve Waitress file-wrapper zero-copy/output-buffer ownership.
        from waitress.buffers import ReadOnlyFileBasedBuffer
        if isinstance(response,ReadOnlyFileBasedBuffer):
            original=response.close
            def close_file():
                try:original()
                except BaseException:
                    with owner._lock:owner._resource_errors+=1
                    raise
                finally:closed()
            response.close=close_file
            return response
        class TrackedResponse:
            def __iter__(self):return iter(response)
            def close(self):
                try:
                    close=getattr(response,'close',None)
                    if close:close()
                except BaseException:
                    with owner._lock:owner._resource_errors+=1
                    raise
                finally:closed()
        if hasattr(response,'__len__'):
            class SizedTrackedResponse(TrackedResponse):
                def __len__(self):return len(response)
            return SizedTrackedResponse()
        return TrackedResponse()

    def _log_slow_request(self, timing: RequestTiming) -> None:
        if timing.handler_finished is None:
            return
        response_seconds = time.monotonic() - timing.handler_finished
        if timing.queue_seconds + timing.handler_seconds + response_seconds < _SLOW_REQUEST_SECONDS:
            return
        try:
            self.logger.warning(
                'HTTP 慢请求 code=http_slow_request route=%s queue_ms=%.1f handler_ms=%.1f '
                'json_ms=%.1f pool_ms=%.1f response_ms=%.1f',
                timing.route, timing.queue_seconds * 1000, timing.handler_seconds * 1000,
                timing.json_seconds * 1000, timing.pool_seconds * 1000, response_seconds * 1000,
            )
        except Exception:
            # 日志失败时保持原有响应和连接清理。
            pass

    def start(self):
        if self._state!='new':raise RuntimeError('http_server_not_restartable')
        if version('waitress')!=AUDITED_WAITRESS_VERSION:raise RuntimeError('http_waitress_version_mismatch')
        if not self.spool_dir.is_absolute():raise ValueError('http_spool_absolute_required')
        self.spool_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.spool_dir.is_symlink():raise ValueError('http_spool_symlink_rejected')
        self.spool_dir.chmod(0o700)
        # Must precede Waitress/buffer imports. Dedicated Web process owns this path.
        tempfile.tempdir=str(self.spool_dir)
        from waitress import wasyncore
        from waitress.channel import HTTPChannel
        from waitress.server import create_server
        from waitress.task import ThreadedTaskDispatcher
        owner=self
        class Dispatcher(ThreadedTaskDispatcher):
            def __init__(self):
                super().__init__();self.actual_threads=[];self.active=set();self.halt=False
            def start_new_thread(self,target,thread_no):
                thread=threading.Thread(target=target,args=(thread_no,),name=f'turb-http-{thread_no}',daemon=True)
                self.actual_threads.append(thread);thread.start()
            def handler_thread(self,thread_no):
                try:
                    while True:
                        with self.lock:
                            while not self.queue and not self.halt:self.queue_cv.wait()
                            if self.halt:return
                            task=self.queue.popleft()
                            if owner._draining.is_set():
                                self.queue.appendleft(task);self.queue_cv.wait(.01);continue
                            queue_seconds = time.monotonic() - task._turb_enqueued_at
                            self.active.add(task)
                        timing = RequestTiming(queue_seconds)
                        timing_token = current_request_timing.set(timing)
                        try:task.service()
                        except BaseException:owner.logger.exception('http_task_failed')
                        finally:
                            current_request_timing.reset(timing_token)
                            with self.lock:self.active.discard(task)
                            if owner._draining.is_set():task.close_when_flushed=True
                            try:owner._server.pull_trigger()
                            except OSError:pass
                            owner._log_slow_request(timing)
                finally:
                    with self.lock:self.threads.discard(thread_no);self.thread_exit_cv.notify_all()
            def add_task(self,task):
                with self.lock:
                    task._turb_enqueued_at = time.monotonic()
                    self.queue.append(task);self.queue_cv.notify()
            def begin_drain(self):
                with self.lock:
                    self.halt=True;pending=list(self.queue);self.queue.clear();active=set(self.active);self.queue_cv.notify_all()
                return pending,active
        class Channel(HTTPChannel):
            def readable(self):return not owner._draining.is_set() and super().readable()
            def received(self,data):
                if owner._draining.is_set():return False
                return super().received(data)
        dispatcher=Dispatcher();self._dispatcher=dispatcher
        try:
            # One numeric/listen target avoids MultiSocketServer.close's implicit shutdown.
            self._server=create_server(self._tracked_app,host=self.host,port=self.port,
                map=self._map,_dispatcher=dispatcher,_start=False,threads=self.threads,
                max_request_body_size=self.max_request_body_size,channel_request_lookahead=0,
                ipv4=':' not in self.host,ipv6=':' in self.host,
                asyncore_loop_timeout=.05,clear_untrusted_proxy_headers=True)
            if not hasattr(self._server,'active_channels'):raise RuntimeError('http_multi_listener_unsupported')
            self._server.channel_class=Channel
            dispatcher.set_thread_count(self.threads)
            self._server.accept_connections();self._state='running'
            def loop():
                try:
                    while not self._loop_stop.is_set():
                        if self._draining.is_set() and not self._drain_applied.is_set():self._apply_drain()
                        wasyncore.loop(timeout=.02,count=1,map=self._map)
                except BaseException:
                    with self._lock:self._resource_errors+=1
                    self.logger.exception('http_loop_failed')
                finally:
                    self._loop_stop.set()
                    self._server.trigger.close()
            self._loop=threading.Thread(target=loop,name='turb-http-loop',daemon=True);self._loop.start()
            return self._server.effective_host,int(self._server.effective_port)
        except BaseException:
            self._state='start_failed';self._draining.set()
            try:
                if self._server is not None and hasattr(self._server,'active_channels'):self._apply_drain()
                else:dispatcher.begin_drain()
                for channel in list(self._map.values()):
                    try:channel.close()
                    except Exception:self._resource_errors+=1
                for thread in dispatcher.actual_threads:
                    if thread.ident is not None and thread is not threading.current_thread():thread.join(1)
            except BaseException:
                # Teardown must retain the original startup exception. Any
                # unclosed allocation remains visible to the later stop call.
                self._resource_errors+=1
                self.logger.exception('http_start_cleanup_incomplete')
            finally:
                tempfile.tempdir=self._previous_tempdir
            raise

    def _apply_drain(self):
        server=self._server;dispatcher=self._dispatcher
        # Listener only: BaseWSGIServer.close would also close trigger prematurely.
        from waitress import wasyncore
        server.accepting=False;wasyncore.dispatcher.close(server);self._listener_closed=True
        pending,active=dispatcher.begin_drain()
        for channel in list(server.active_channels.values()):
            with channel.requests_lock:
                keep=1 if channel in active else 0
                discarded=channel.requests[keep:];channel.requests=channel.requests[:keep]
                if channel.request is not None:discarded.append(channel.request);channel.request=None
                for request in discarded:
                    try:request.close()
                    except Exception:self._resource_errors+=1
                self._discarded+=len(discarded)
                if channel not in active:channel.close_when_flushed=True
            if channel not in active and not channel.total_outbufs_len:channel.handle_close()
        self._drain_applied.set()

    def status(self):
        dispatcher=self._dispatcher
        with self._lock:
            return {'state':self._state,'draining':self._draining.is_set(),
                'listener_closed':self._listener_closed,'loop_alive':bool(self._loop and self._loop.is_alive()),
                'workers_alive':sum(thread.is_alive() for thread in dispatcher.actual_threads) if dispatcher else 0,
                'channels':len(self._server.active_channels) if self._server is not None else 0,
                'buffered_requests':sum(len(channel.requests)+(channel.request is not None) for channel in tuple(self._server.active_channels.values())) if self._server is not None else 0,
                'active_calls':self._active_calls,'responses_open':len(self._responses),
                'discarded_requests':self._discarded,'resource_errors':self._resource_errors}

    def serve(self):
        if not self._loop:raise RuntimeError('http_server_not_started')
        while self._loop.is_alive() and not self._draining.wait(.1):pass
        if self._loop_stop.is_set() and not self._draining.is_set():raise RuntimeError('http_loop_exited')

    def stop(self,timeout=20.0):
        if not math.isfinite(timeout) or timeout<0:raise ValueError('http_stop_budget_invalid')
        deadline=time.monotonic()+timeout
        if not self._stop_lock.acquire(timeout=max(0,deadline-time.monotonic())):
            return False
        try:
            if self._state=='stopped':return True
            if self._server is None:
                clean=not self._map and self._resource_errors==0 and not (
                    self._dispatcher and any(thread.is_alive() for thread in self._dispatcher.actual_threads))
                self._state='stopped' if clean else 'stop_incomplete'
                return clean
            self._draining.set();self._state='draining'
            try:self._server.pull_trigger()
            except OSError:pass
            while time.monotonic()<deadline:
                status=self.status()
                if self._drain_applied.is_set() and status['workers_alive']==0 and status['channels']==0 and status['active_calls']==0 and status['responses_open']==0:break
                time.sleep(min(.01,max(0,deadline-time.monotonic())))
            status=self.status()
            clean=self._drain_applied.is_set() and not any(status[key] for key in ('workers_alive','channels','active_calls','responses_open','resource_errors'))
            if clean:
                self._loop_stop.set()
                try:self._server.pull_trigger()
                except OSError:pass
                if self._loop is not None and self._loop.ident is not None and self._loop is not threading.current_thread():self._loop.join(max(0,deadline-time.monotonic()))
                clean=not (self._loop and self._loop.is_alive()) and not self._map and self._resource_errors==0
            if clean and tempfile.tempdir==str(self.spool_dir):tempfile.tempdir=self._previous_tempdir
            self._state='stopped' if clean else 'stop_incomplete'
            if not clean:self.logger.error('http_stop_incomplete %s',self.status())
            return clean
        finally:
            self._stop_lock.release()
