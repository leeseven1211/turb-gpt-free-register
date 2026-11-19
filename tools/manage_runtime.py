#!/usr/bin/env python3
"""Local role launcher delegated by webui.sh; managers run Python foreground."""
from __future__ import annotations
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.runtime.role_launcher import RoleError,RoleManager

@contextlib.contextmanager
def control_lock(directory):
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    import fcntl
    with (directory/'launcher.lock').open('a+') as lock:
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise RoleError('launcher_busy') from None
        try:yield
        finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def main(argv=None):
    parser=argparse.ArgumentParser(description='按精确身份管理 combined/web/worker；服务由 systemd/launchd 直接运行 Python')
    parser.add_argument('command',choices=['start','stop','restart','status','check','ready','logs','log'])
    parser.add_argument('role',choices=['combined','web','worker','all'],default='combined',nargs='?')
    args=parser.parse_args(argv)
    try:
        port=int(os.getenv('PORT','5000'));timeout=float(os.getenv('STARTUP_CHECK_TIMEOUT','30'));stop_timeout=float(os.getenv('STOP_TIMEOUT','90'))
        if timeout<=0 or stop_timeout<0:raise ValueError()
    except ValueError:parser.error('PORT/STARTUP_CHECK_TIMEOUT/STOP_TIMEOUT 无效')
    # The control tool itself reads no .env. Child entrypoints retain that bootstrap.
    from core.runtime.bootstrap import RuntimeBootstrap
    mode='worker' if args.role=='worker' else 'web' if args.role in {'web','all'} else 'combined'
    raw=os.getenv('TURB_RUNTIME_DIR')
    environment={**os.environ,'TURB_RUNTIME_MODE':mode}
    if mode!='combined' and not raw:parser.error('split 角色要求显式 TURB_RUNTIME_DIR 和稳定 TURB_INSTANCE_ID')
    bootstrap=RuntimeBootstrap.from_environment(project_root=ROOT,environment=environment)
    runtime_dir=bootstrap.runtime_dir
    python=str(ROOT/'.venv/bin/python') if (ROOT/'.venv/bin/python').exists() else sys.executable
    host=os.getenv('HOST','127.0.0.1');probe_host='127.0.0.1' if host in {'0.0.0.0','::'} else host
    from tools.check_startup import check_startup
    def probe(role):
        if role!='worker':
            results=check_startup(f'http://{probe_host}:{port}',timeout=1)
            return results[0].ok,all(result.ok for result in results)
        identity=manager.read('worker') or {}
        command=[python,str(ROOT/'tools/check_runtime.py'),'--instance-id',bootstrap.instance_id,'--release',bootstrap.release,'--runtime-dir',str(runtime_dir)]
        if identity.get('pid'):command+=['--pid',str(identity['pid'])]
        if identity.get('owner_process_start'):command+=['--process-start',identity['owner_process_start']]
        try:
            result=subprocess.run(command,cwd=ROOT,env={**os.environ,'TURB_RUNTIME_MODE':'worker','TURB_RUNTIME_DIR':str(runtime_dir),'TURB_INSTANCE_ID':bootstrap.instance_id},capture_output=True,text=True,timeout=5)
            return result.returncode==0,result.returncode==0
        except (OSError,subprocess.SubprocessError):return False,False
    manager=RoleManager(root=ROOT,runtime_dir=runtime_dir,instance_id=bootstrap.instance_id,release=bootstrap.release,python=python,host=host,port=port,probe=probe)
    roles=['web','worker'] if args.role=='all' else [args.role]
    try:
        if args.command in {'logs','log'}:
            if len(roles)!=1:raise RoleError('logs_requires_one_role')
            value=manager.read(roles[0]) or {};log=Path(value.get('log',runtime_dir/'logs'/f'{roles[0]}.log'))
            if not log.exists():raise RoleError('log_absent')
            return subprocess.call(['tail','-n','120','-f',str(log)])
        with control_lock(runtime_dir):
            if args.command=='start' and args.role=='all':results=manager.start_all(timeout)
            elif args.command=='start':results=[manager.start(roles[0],timeout)]
            elif args.command=='restart':
                if args.role=='all':
                    for role in roles:
                        receipt=manager.stop(role,stop_timeout)
                        if receipt.get('state')=='stopped' and receipt.get('clean') is not True:raise RoleError('stop_incomplete_no_restart')
                    results=manager.start_all(timeout)
                else:results=[manager.restart(roles[0],stop_timeout,timeout)]
            elif args.command=='stop':
                results=[]
                for role in roles:
                    try:results.append(manager.stop(role,stop_timeout))
                    except RoleError as exc:results.append({'role':role,'state':'stop_incomplete','clean':False,'error_code':str(exc)})
            else:results=[manager.status(role) for role in roles]
        for result in results:
            safe={key:value for key,value in result.items() if key not in {'command','nonce','exit_path'}}
            print(json.dumps(safe,ensure_ascii=False))
        if args.command in {'check','ready'}:return 0 if all(result.get('ready') for result in results) else 1
        if args.command=='stop':return 0 if all(result.get('state')=='absent' or result.get('clean') is True for result in results) else 3
        if args.command=='status':return 0 if all(result.get('alive') for result in results) else 1
        return 0
    except RoleError as exc:
        print(json.dumps({'ok':False,'error_code':str(exc),'roles':roles,'runtime_dir':str(runtime_dir)}),file=sys.stderr)
        return 3
if __name__=='__main__':raise SystemExit(main())
