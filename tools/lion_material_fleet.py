#!/usr/bin/env python3
"""Start/status/stop the R10 MAT12 user-level material fleet."""
from __future__ import annotations
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.lion_material_drone_worker import ROLES

def atomic(path,v):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(v,sort_keys=True),encoding='utf-8');os.replace(tmp,path)
def alive(pid):
    pid=int(pid)
    if os.name=='nt':
        import ctypes
        h=ctypes.windll.kernel32.OpenProcess(0x1000,False,pid)
        if not h:return False
        ctypes.windll.kernel32.CloseHandle(h);return True
    try:os.kill(pid,0);return True
    except OSError:return False
def start(runtime,repo,worker):
    runtime=Path(runtime);(runtime/'pids').mkdir(parents=True,exist_ok=True);rows=[]
    for drone,role in ROLES.items():
        hp=runtime/'health'/f'{drone}.json'
        if hp.exists():
            try:
                h=json.loads(hp.read_text());
                if alive(h.get('pid')):rows.append(h);continue
            except Exception:pass
        log=(runtime/'logs'/f'{drone}.log');log.parent.mkdir(parents=True,exist_ok=True);fh=log.open('ab')
        kw={'stdin':subprocess.DEVNULL,'stdout':fh,'stderr':subprocess.STDOUT,'cwd':str(Path(worker).resolve().parents[1])}
        if os.name=='nt':kw['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS
        else:kw['start_new_session']=True
        p=subprocess.Popen([sys.executable,str(worker),'--drone-id',drone,'--runtime-dir',str(runtime),'--repo',str(repo)],**kw);(runtime/'pids'/f'{drone}.pid').write_text(str(p.pid))
    deadline=time.time()+15
    while time.time()<deadline:
        rows=[]
        for drone in ROLES:
            hp=runtime/'health'/f'{drone}.json'
            if hp.exists():
                try:
                    h=json.loads(hp.read_text());
                    if alive(h.get('pid')) and h.get('status')=='READY':rows.append(h)
                except Exception:pass
        if len(rows)==len(ROLES):break
        time.sleep(.1)
    return rows
def status(runtime):
    runtime=Path(runtime);rows=[]
    for drone,role in ROLES.items():
        hp=runtime/'health'/f'{drone}.json'
        if hp.exists():
            try:
                h=json.loads(hp.read_text());h['alive']=alive(h.get('pid'));rows.append(h)
            except Exception:pass
    return rows
def stop(runtime):
    rows=status(runtime)
    for h in rows:
        if h.get('alive'):
            try:os.kill(int(h['pid']),signal.SIGTERM)
            except OSError:pass
    return rows
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status','stop']);p.add_argument('--runtime-dir',required=True);p.add_argument('--repo');p.add_argument('--worker');a=p.parse_args()
    if a.action=='start':
        if not a.repo or not a.worker:raise SystemExit('start requires repo and worker')
        rows=start(a.runtime_dir,a.repo,a.worker)
    elif a.action=='status':rows=status(a.runtime_dir)
    else:rows=stop(a.runtime_dir)
    print(json.dumps({'count':len(rows),'healthy':sum(1 for x in rows if x.get('alive',True) and x.get('status')=='READY'),'rows':rows},sort_keys=True))
if __name__=='__main__':main()
