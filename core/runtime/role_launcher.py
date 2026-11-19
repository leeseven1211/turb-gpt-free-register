"""Local role control with exact identity; no app/config/database imports.

This module never discovers/adopts processes by name or port and never SIGKILLs.
Manager-owned identities must be controlled by their manager to avoid respawn races.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

class RoleError(RuntimeError):pass
@dataclass(frozen=True)
class ProcessInfo:
    pid:int
    process_start:str
    cwd:str
    command:str
    owner_process_start:str=''

def inspect_process(pid:int):
    if type(pid) is not int or pid<1:return None
    try:
        result=subprocess.run(['ps','-p',str(pid),'-o','lstart=','-o','stat=','-o','command='],capture_output=True,text=True,timeout=2)
        if result.returncode or not result.stdout.strip():return None
        fields=result.stdout.strip().split(None,6)
        if len(fields)<7 or fields[5].startswith('Z'):return None
        start=' '.join(fields[:5]);command=fields[6]
        proc=Path('/proc')/str(pid)
        if proc.exists():
            cwd=str((proc/'cwd').resolve(strict=True))
            command=' '.join((proc/'cmdline').read_bytes().decode().strip('\0').split('\0'))
            stat=(proc/'stat').read_text();start+=':'+stat[stat.rfind(')')+2:].split()[19]
        else:
            current=subprocess.run(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True,timeout=2)
            cwd=next((line[1:] for line in current.stdout.splitlines() if line.startswith('n')),'')
        if not cwd:return None
        owner_start=subprocess.run(['ps','-p',str(pid),'-o','lstart='],capture_output=True,text=True,timeout=2).stdout.strip()
        if not owner_start:return None
        return ProcessInfo(pid,start,cwd,command,owner_start)
    except (OSError,ValueError,subprocess.SubprocessError):return None

def owns_listener(pid:int,port:int) -> bool:
    """Read-only socket ownership proof; a healthy unrelated port is insufficient."""
    if type(pid) is not int or pid<1 or type(port) is not int or not 1<=port<=65535:return False
    try:
        proc=Path('/proc')/str(pid)
        if proc.exists():
            inodes=set()
            for descriptor in (proc/'fd').iterdir():
                try:target=os.readlink(descriptor)
                except OSError:continue
                match=re.fullmatch(r'socket:\[(\d+)\]',target)
                if match:inodes.add(match.group(1))
            for filename in ('tcp','tcp6'):
                table=proc/'net'/filename
                if not table.exists():continue
                for line in table.read_text().splitlines()[1:]:
                    fields=line.split()
                    if len(fields)>9 and fields[3]=='0A' and int(fields[1].rsplit(':',1)[1],16)==port and fields[9] in inodes:return True
            return False
        result=subprocess.run(['lsof','-nP','-a','-p',str(pid),'-iTCP:'+str(port),'-sTCP:LISTEN','-FpnT'],capture_output=True,text=True,timeout=2)
        # lsof has already applied PID+TCP+port+LISTEN AND predicates.
        lines=result.stdout.splitlines()
        return result.returncode==0 and 'p'+str(pid) in lines and any(line=='TST=LISTEN' for line in lines)
    except (OSError,ValueError,subprocess.SubprocessError):return False

def atomic_json(path:Path,value:dict):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as stream:
            os.chmod(temporary,0o600);json.dump(value,stream,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()

def write_exit_receipt(*,role:str,clean:bool,code:int):
    """Entrypoint-only receipt; no secret or operation payload is accepted."""
    raw=os.environ.get('TURB_ROLE_EXIT_PATH');nonce=os.environ.get('TURB_ROLE_LAUNCH_NONCE')
    if raw and nonce:
        atomic_json(Path(raw),{'role':role,'nonce':nonce,'pid':os.getpid(),'clean':clean is True,'exit_code':int(code),'finished_at':time.time()})

def publish_managed_identity(bootstrap):
    source=os.environ.get('TURB_RUNTIME_MANAGER','')
    if source not in {'systemd','launchd'}:return
    current=inspect_process(os.getpid())
    if current is None:raise RoleError('process_identity_unavailable')
    role=bootstrap.mode
    atomic_json(bootstrap.runtime_dir/f'{role}.json',{**asdict(current),'role':role,'instance_id':bootstrap.instance_id,'release':bootstrap.release,'source':source,'nonce':uuid.uuid4().hex})

class RoleManager:
    def __init__(self,*,root:Path,runtime_dir:Path,instance_id:str,release:str,python:str,
                 host='127.0.0.1',port=5000,inspect=inspect_process,spawn=None,
                 signal_process=os.kill,probe=None,clock=time.monotonic,sleep=time.sleep,environment=None,owns_listener=owns_listener):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',instance_id):raise RoleError('instance_invalid')
        if not re.fullmatch(r'[a-fA-F0-9]{40,64}',release):raise RoleError('release_invalid')
        if not Path(runtime_dir).is_absolute():raise RoleError('runtime_directory_absolute_required')
        if type(port) is not int or not 1<=port<=65535:raise RoleError('port_invalid')
        self.root=Path(root).resolve();self.runtime_dir=Path(runtime_dir);self.instance_id=instance_id;self.release=release;self.python=python;self.host=host;self.port=port
        self.inspect=inspect;self.spawn=spawn or self._spawn;self.signal_process=signal_process;self.probe=probe or (lambda _: (False,False));self.clock=clock;self.sleep=sleep
        self.owns_listener=owns_listener
        self.environment=dict(os.environ if environment is None else environment);self._children={}
    def path(self,role):
        if role not in {'combined','web','worker'}:raise RoleError('role_invalid')
        return self.runtime_dir/f'{role}.json'
    def read(self,role):
        try:
            value=json.loads(self.path(role).read_text())
            if not isinstance(value,dict):raise ValueError()
            return value
        except FileNotFoundError:return None
        except (OSError,ValueError):raise RoleError('identity_invalid') from None
    def write(self,role,value):atomic_json(self.path(role),value)
    def _spawn(self,argv,*,env,log):
        log.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with log.open('ab') as output:
            os.chmod(log,0o600)
            child=subprocess.Popen(argv,cwd=self.root,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        self._children[child.pid]=child;return child.pid
    def _verified(self,role,value,allow_managed=False):
        if value.get('source')!='manual' and not (allow_managed and value.get('source') in {'systemd','launchd'}):raise RoleError('managed_use_manager')
        if value.get('role')!=role or value.get('instance_id')!=self.instance_id or value.get('release')!=self.release:raise RoleError('identity_mismatch')
        pid=value.get('pid');observed=self.inspect(pid)
        if observed is None:return None
        if any(value.get(key)!=getattr(observed,key) for key in ('pid','process_start','cwd','command')) or observed.cwd!=str(self.root):raise RoleError('identity_mismatch')
        return observed
    def _args(self,role):
        if role=='worker':return[self.python,str(self.root/'worker.py')]
        return[self.python,str(self.root/'web.py'),'--host',self.host,'--port',str(self.port),'--mode',role,*(['--server','waitress'] if role=='web' else [])]
    def start(self,role,timeout=30.):
        if not math.isfinite(timeout) or timeout<=0:raise RoleError('startup_budget_invalid')
        existing=self.read(role)
        if existing:
            if self._verified(role,existing):return self._wait_ready(role,existing,timeout)
            self.path(role).unlink()
        if os.environ.get('TURB_RUNTIME_MANAGER'):raise RoleError('managed_use_manager')
        if self.environment.get('EXTRA_ARGS'):raise RoleError('extra_args_unsupported_use_explicit_cli')
        conflicts=('web','worker') if role=='combined' else ('combined',)
        for conflict in conflicts:
            other=self.read(conflict)
            if other and self.inspect(other.get('pid')) is not None:
                raise RoleError('conflicting_role_running')
        nonce=uuid.uuid4().hex;exit_path=self.runtime_dir/f'{role}.exit.json'
        env={**self.environment,'TURB_RUNTIME_MODE':role,'TURB_INSTANCE_ID':self.instance_id,'TURB_RUNTIME_DIR':str(self.runtime_dir),'TURB_ROLE_LAUNCH_NONCE':nonce,'TURB_ROLE_EXIT_PATH':str(exit_path)}
        if role=='combined' and not self.environment.get('TURB_RUNTIME_DIR'):
            env.pop('TURB_RUNTIME_DIR',None)
        if env.get('AUTH_CODE'):env['WEBUI_AUTH_CODE']=env['AUTH_CODE']
        argv=self._args(role)
        if role!='worker' and env.get('OPEN_BROWSER') in {'1','true'}:argv.append('--open-browser')
        if env.get('VERBOSE') in {'1','true'}:argv.append('--verbose')
        log=self.runtime_dir/'logs'/f'{role}.log';pid=self.spawn(argv,env=env,log=log)
        observed=self.inspect(pid)
        if observed is None:raise RoleError('process_identity_unavailable')
        value={**asdict(observed),'role':role,'instance_id':self.instance_id,'release':self.release,'source':'manual','nonce':nonce,'exit_path':str(exit_path),'log':str(log)};self.write(role,value)
        return self._wait_ready(role,value,timeout)
    def _wait_ready(self,role,value,timeout,require_ready=False):
        deadline=self.clock()+timeout
        while True:
            if self._verified(role,value) is None:raise RoleError('startup_process_exited')
            listener_ok=role=='worker' or self.owns_listener(value['pid'],self.port)
            alive,ready=self.probe(role) if listener_ok else (False,False)
            if role!='worker' and not self.owns_listener(value['pid'],self.port):alive=ready=False
            if self._verified(role,value) is None:raise RoleError('startup_process_exited')
            if ready or role=='web' and alive and not require_ready:return{**value,'state':'ready' if ready else 'alive_not_ready','alive':alive,'ready':ready}
            if self.clock()>=deadline:raise RoleError('startup_timeout')
            self.sleep(min(.2,max(0,deadline-self.clock())))
    def stop(self,role,timeout=90.):
        if not math.isfinite(timeout) or timeout<0:raise RoleError('stop_budget_invalid')
        value=self.read(role)
        if value is None:return{'role':role,'state':'absent','clean':None}
        observed=self._verified(role,value)
        if observed is not None:
            self.signal_process(observed.pid,signal.SIGTERM);deadline=self.clock()+timeout
            while self._verified(role,value) is not None:
                if self.clock()>=deadline:raise RoleError('stop_timeout_identity_retained')
                self.sleep(min(.1,max(0,deadline-self.clock())))
        receipt=None
        try:receipt=json.loads(Path(value.get('exit_path','')).read_text())
        except (OSError,ValueError):pass
        clean=bool(receipt and receipt.get('nonce')==value.get('nonce') and receipt.get('pid')==value.get('pid') and receipt.get('clean') is True and receipt.get('exit_code')==0)
        self.path(role).unlink()
        return{'role':role,'pid':value['pid'],'state':'stopped','clean':clean,'exit_code':receipt.get('exit_code') if receipt else None}
    def restart(self,role,stop_timeout=90.,timeout=30.):
        stopped=self.stop(role,stop_timeout)
        if stopped.get('state')=='stopped' and stopped.get('clean') is not True:raise RoleError('stop_incomplete_no_restart')
        return self.start(role,timeout)
    def status(self,role):
        value=self.read(role)
        if value is None:return{'role':role,'state':'absent','alive':False,'ready':False}
        alive=self._verified(role,value,allow_managed=True) is not None
        listener_ok=role=='worker' or self.owns_listener(value['pid'],self.port)
        probe_alive,ready=self.probe(role) if alive and listener_ok else (False,False)
        if role!='worker' and not self.owns_listener(value['pid'],self.port):probe_alive=ready=False
        if self._verified(role,value,allow_managed=True) is None:alive=probe_alive=ready=False
        return{**value,'state':'ready' if ready else 'alive_not_ready' if alive else 'exited','alive':alive,'ready':ready,'http_alive':probe_alive}
    def start_all(self,timeout=30.):
        worker=self.start('worker',timeout);web=self.start('web',timeout)
        if not web['ready']:web=self._wait_ready('web',self.read('web'),timeout,require_ready=True)
        return[worker,web]
