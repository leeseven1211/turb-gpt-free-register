"""Synthetic subprocess HTTP server; never imports application/config/storage."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from core.runtime.http_server import HttpServer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spool',required=True);parser.add_argument('--timeout',type=float,default=1)
    args=parser.parse_args();stopped=threading.Event()
    for name in ('SIGTERM','SIGINT'):signal.signal(getattr(signal,name),lambda *_:stopped.set())
    def app(environ,start):
        path=environ['PATH_INFO']
        print(json.dumps({'entered':path}),flush=True)
        if path=='/delay':time.sleep(.25)
        if path=='/blocked':time.sleep(30)
        body=b'x'*(8*1024*1024) if path=='/large' else b'synthetic-http-ok'
        start('200 OK',[('Content-Type','application/octet-stream'),('Content-Length',str(len(body))),('Cache-Control','no-store')])
        return [body]
    server=HttpServer(app,host='127.0.0.1',port=0,spool_dir=Path(args.spool));address=server.start()
    print(json.dumps({'port':address[1]}),flush=True)
    stopped.wait(10);clean=server.stop(args.timeout)
    print(json.dumps({'clean':clean,**server.status()}),flush=True)
    return 0 if clean else 3
if __name__=='__main__':raise SystemExit(main())
