#!/usr/bin/env python3
"""Read-only Worker status probe; no DDL, component start or business recovery."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

def evaluate_worker(record,expected,required_revision,*,components_ready=None):
    if components_ready is None:
        from core.runtime.readiness import REQUIRED_COMPONENTS,component_ready
        components_ready=lambda values:all(component_ready(name,values.get(name)) for name in REQUIRED_COMPONENTS)
    checks={
        'identity':all(record.get(key)==value for key,value in expected.items()),
        'generation':type(record.get('generation')) is int and record['generation']>0 and bool(record.get('owner_nonce')),
        'fresh':record.get('fresh') is True,
        'runtime':record.get('ready') is True and record.get('state')=='running' and record.get('mode') in {'worker','combined'},
        'config':type(record.get('applied_db_revision')) is int and record['applied_db_revision']>=required_revision and type(record.get('local_snapshot_revision')) is int and record['local_snapshot_revision']>=0,
        'components':components_ready(record.get('components') if isinstance(record.get('components'),dict) else {}),
    }
    return{'ok':all(checks.values()),'status':'ready' if all(checks.values()) else 'not_ready','checks':checks,'instance_id':expected.get('instance_id'),'pid':record.get('pid'),'generation':record.get('generation')}

def main(argv=None):
    parser=argparse.ArgumentParser(description='只读核对独立 Worker 的持久身份、代际、配置及组件')
    parser.add_argument('--instance-id',required=True);parser.add_argument('--release',required=True);parser.add_argument('--pid',type=int);parser.add_argument('--process-start');parser.add_argument('--runtime-dir',required=True)
    args=parser.parse_args(argv)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from config.env_loader import ensure_loaded
    ensure_loaded()
    from core.storage import postgres,runtime_workers,runtime_config
    expected={'instance_id':args.instance_id,'release':args.release}
    if args.pid:expected['pid']=args.pid
    if args.process_start:expected['process_start']=args.process_start
    try:
        # No ensure_tables / require_ready: a fresh empty schema remains absent.
        with postgres.connect() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            revision=runtime_config.current_revision(conn=conn)
            record=runtime_workers.read_worker(args.instance_id,conn=conn)
        result=evaluate_worker(record,expected,revision)
    except Exception:
        result={'ok':False,'status':'not_ready','error_code':'runtime_probe_unavailable'}
    finally:postgres.close_pools()
    print(json.dumps(result,ensure_ascii=False));return 0 if result['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
