#!/usr/bin/env python3
"""Last-resort, inventory-bound containment for LION-owned canary resources.

No database, network, shell or fuzzy process matching is used. A process is
signalled only when PID, executable, /proc starttime and cmdline digest all
match a pre-recorded inventory entry. Receipts are independent files for
later Mission Control reconciliation.
"""
from __future__ import annotations
import argparse,hashlib,json,os,signal,tempfile,time,uuid
from pathlib import Path

SCHEMA='lion.operator-containment-inventory/v1'
RECEIPT_SCHEMA='lion.operator-containment-receipt/v1'

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()

def proc_identity(pid:int):
    root=Path('/proc')/str(pid)
    exe=os.readlink(root/'exe')
    cmd=(root/'cmdline').read_bytes();cmd_sha=hashlib.sha256(cmd).hexdigest()
    stat=(root/'stat').read_text(encoding='utf-8',errors='strict')
    tail=stat.rsplit(')',1)[1].strip().split();starttime=tail[19]
    return {'pid':pid,'exe':exe,'cmdline_sha256':cmd_sha,'proc_starttime':starttime}

def atomic_json(path:Path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as h:
            json.dump(value,h,ensure_ascii=False,sort_keys=True,separators=(',',':'));h.write('\n');h.flush();os.fsync(h.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        try:
            if os.path.exists(name):os.unlink(name)
        except OSError:pass

def load_inventory(path:Path):
    value=json.loads(path.read_text(encoding='utf-8'))
    if type(value) is not dict or value.get('schema')!=SCHEMA:raise ValueError('inventory schema')
    if not isinstance(value.get('mission_id'),str) or not value['mission_id']:raise ValueError('inventory mission')
    targets=value.get('targets')
    if type(targets) is not list or not 1<=len(targets)<=128:raise ValueError('inventory targets')
    ids=set()
    for t in targets:
        if type(t) is not dict or set(t)!={'target_id','kind','pid','exe','proc_starttime','cmdline_sha256'}:raise ValueError('inventory target schema')
        if t['kind']!='process' or type(t['pid']) is not int or t['pid']<=1:raise ValueError('inventory target kind')
        if not isinstance(t['target_id'],str) or not t['target_id'] or t['target_id'] in ids:raise ValueError('inventory target id')
        ids.add(t['target_id'])
        if not isinstance(t['exe'],str) or not t['exe'].startswith('/'):raise ValueError('inventory exe')
        if not isinstance(t['proc_starttime'],str) or not t['proc_starttime'].isdigit():raise ValueError('inventory starttime')
        if not isinstance(t['cmdline_sha256'],str) or len(t['cmdline_sha256'])!=64:raise ValueError('inventory cmdline digest')
    return value

def verify_target(target):
    observed=proc_identity(int(target['pid']))
    expected={k:target[k] for k in ('pid','exe','cmdline_sha256','proc_starttime')}
    if observed!=expected:raise ValueError('target identity drift:'+target['target_id'])
    return observed

def alive(pid):
    try:
        os.kill(pid,0)
        stat=(Path('/proc')/str(pid)/'stat').read_text(encoding='utf-8',errors='strict')
        state=stat.rsplit(')',1)[1].strip().split()[0]
        return state!='Z'
    except (ProcessLookupError,FileNotFoundError):return False

def contain(inventory_path:Path,receipt_dir:Path,mission_id:str,request_id:str,timeout:float=3.0):
    inv=load_inventory(inventory_path)
    if mission_id!=inv['mission_id']:raise ValueError('mission inventory mismatch')
    if not request_id or len(request_id)>128:raise ValueError('request id')
    inv_digest=digest(inv);receipt_path=receipt_dir/(request_id+'.json')
    if receipt_path.exists():
        prior=json.loads(receipt_path.read_text(encoding='utf-8'))
        if prior.get('inventory_digest')!=inv_digest or prior.get('mission_id')!=mission_id:raise ValueError('request id conflict')
        return prior
    verified=[]
    for target in inv['targets']:verified.append((target,verify_target(target)))
    results=[]
    for target,identity in verified:
        pid=int(target['pid']);os.kill(pid,signal.SIGTERM);deadline=time.monotonic()+max(.1,float(timeout))
        while alive(pid) and time.monotonic()<deadline:time.sleep(.02)
        results.append({'target_id':target['target_id'],'identity':identity,'signal':'SIGTERM','stopped':not alive(pid)})
    body={'schema':RECEIPT_SCHEMA,'request_id':request_id,'mission_id':mission_id,'inventory_digest':inv_digest,
          'results':results,'status':'PASS' if all(x['stopped'] for x in results) else 'PARTIAL','observed_at':time.time_ns(),
          'authority_effect':'BOUNDED_LOCAL_CONTAINMENT'}
    body['receipt_digest']=digest(body);atomic_json(receipt_path,body);return body

def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--receipt-dir',required=True);p.add_argument('--mission-id',required=True);p.add_argument('--request-id',default='contain-'+uuid.uuid4().hex);p.add_argument('--timeout',type=float,default=3.0);a=p.parse_args()
    out=contain(Path(a.inventory),Path(a.receipt_dir),a.mission_id,a.request_id,a.timeout);print(json.dumps(out,ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
