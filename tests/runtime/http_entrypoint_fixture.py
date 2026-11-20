"""Actual web.main/Waitress signals; injected no-DB runtime and synthetic WSGI."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import signal
import socket
import sys
import threading
import time
from types import ModuleType,SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core.runtime.http_server import HttpServer

def emit(value):print(json.dumps(value,sort_keys=True),flush=True)
def module(name,**values):
    result=ModuleType(name);result.__dict__.update(values);return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--timeout',type=float,required=True)
    args=parser.parse_args()
    resources={'pool_open':True,'runtime_stop_calls':0,'lock_released':False,
               'response_closed':False,'http_stop_calls':0,'signal_count':0}
    events=[];stop_started=None;entry=None
    def app(environ,start):
        path=environ['PATH_INFO'];emit({'event':'entered','path':path,'pool_open':resources['pool_open']})
        if path=='/short':
            deadline=time.monotonic()+2
            while resources['signal_count']<2 and time.monotonic()<deadline:time.sleep(.002)
        elif path=='/long':threading.Event().wait(30)
        if not resources['pool_open']:raise AssertionError('pool_closed_under_live_application')
        body=b'synthetic-entrypoint-ok';start('200 OK',[('Content-Length',str(len(body)))])
        class Response:
            def __iter__(self):yield body
            def close(self):resources['response_closed']=True
        return Response()
    class Observed(HttpServer):
        def start(self):
            address=super().start();emit({'event':'started','port':address[1]});return address
        def stop(self,timeout=20):
            nonlocal stop_started
            stop_started=time.monotonic()
            resources['http_stop_calls']+=1
            emit({'event':'draining','timeout':timeout})
            clean=super().stop(timeout)
            events.append('http-stop')
            emit({'event':'http-stopped','clean':clean,'elapsed':time.monotonic()-stop_started,
                  **self.status()})
            return clean
    def stop_runtime(**_kwargs):
        events.append('runtime-stop');resources['runtime_stop_calls']+=1
        resources['pool_open']=False
        return True
    bootstrap=SimpleNamespace(mode='web',runtime_dir=args.directory,
                              prepare_log_environment=lambda:None)
    modules={
        'config':module('config'),
        'config.env_loader':module('config.env_loader',ensure_loaded=lambda:None),
        'config.deployment':module('config.deployment',browser_enabled=lambda:False),
        'core.runtime.bootstrap':module('core.runtime.bootstrap',RuntimeBootstrap=SimpleNamespace(from_environment=lambda **_kwargs:bootstrap)),
        'core.runtime.assembly':module('core.runtime.assembly',install=lambda *_args,**_kwargs:None),
        'core.runtime.process':module('core.runtime.process',start_runtime=lambda *_args:None,stop_runtime=stop_runtime),
        'core.storage':module('core.storage',postgres=SimpleNamespace(require_ready=lambda:None)),
        'core.operation_task_store':module('core.operation_task_store',init=lambda:None),
        'webui.app':module('webui.app',create_app=lambda **_kwargs:app),
        'webui.auth':module('webui.auth',is_generated_code=lambda:False),
        'core.runtime.http_server':module('core.runtime.http_server',HttpServer=Observed),
    }
    spec=importlib.util.spec_from_file_location('signal_actual_web_entry',ROOT/'web.py')
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    original_register=signal.signal
    def register(signum,handler):
        def recorded(received,frame):
            resources['signal_count']+=1
            emit({'event':'signal','number':received,'sequence':resources['signal_count']})
            return handler(received,frame)
        return original_register(signum,recorded)
    original_release=entry._release_single_instance
    def release(handle):
        original_release(handle);resources['lock_released']=True;events.append('unlock')
    code=0
    try:
        with patch.dict(sys.modules,modules),patch.object(signal,'signal',register),patch.object(entry,'_release_single_instance',release),patch.object(sys,'argv',['web.py','--mode','web','--server','waitress','--port',str(args.port),'--http-drain-timeout',str(args.timeout)]):
            try:entry.main()
            except SystemExit as exc:code=exc.code or 0
    finally:
        try:probe=socket.create_connection(('127.0.0.1',args.port),timeout=.1)
        except OSError:listener_released=True
        else:probe.close();listener_released=False
        emit({'event':'final','exit_code':code,'resources':resources,'events':events,
              'listener_released':listener_released,
              'elapsed_since_stop':None if stop_started is None else time.monotonic()-stop_started})
    return code

if __name__=='__main__':raise SystemExit(main())
