#!/usr/bin/env python3
"""R10 R2 bounded material drone worker.

Each process has one immutable role and communicates only through bounded JSON
mailboxes.  It never receives credentials and cannot execute arbitrary commands.
"""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,time,urllib.request,uuid,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from cyber_lion.app_coordination.lion_context_provider import FED
from cyber_lion.app_coordination.web_research_broker import PublicWebReadBroker,validate_public_https_url

ROLES={
'MAT01':'LOCAL_REPOSITORY_CURRENTNESS','MAT02':'LOCAL_REPOSITORY_CONTENT','MAT03':'LOCAL_CLONE_INVENTORY','MAT04':'FEDERATION_CURRENTNESS',
'MAT05':'PUBLIC_WEB_SEARCH','MAT06':'PUBLIC_WEB_FETCH','MAT07':'WEB_SECURITY_FALSIFIER','MAT08':'SOURCE_PROVENANCE_VALIDATOR',
'MAT09':'MODEL_GPU_OBSERVER','MAT10':'RESULT_VALIDATOR','MAT11':'MATERIAL_COORDINATOR','MAT12':'FINAL_RECONCILER'}
FEDMAP={repo:branch for repo,branch in FED}
DENIED_PARTS={'.git','.venv','node_modules','.secret','.credentials'}

def now():return datetime.now(timezone.utc).isoformat()
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode('utf-8')
def digest(v):return hashlib.sha256(canon(v)).hexdigest()
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,sort_keys=True,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)
def safe_path(root,rel):
    if not isinstance(rel,str) or not rel or '\x00' in rel:raise ValueError('path denied')
    root=Path(root).resolve(strict=True);p=(root/rel).resolve(strict=False)
    if root not in p.parents:raise ValueError('path denied')
    parts=p.relative_to(root).parts
    if any(x in DENIED_PARTS for x in parts) or p.name=='.env':raise ValueError('path denied')
    return p.resolve(strict=True)
def git(root,*args):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,timeout=15)
    if p.returncode:raise ValueError('git read failed')
    return p.stdout.strip()
def public_json(url,timeout=8):
    req=urllib.request.Request(url,headers={'User-Agent':'LION-R10-MAT04/1','Accept':'application/vnd.github+json'},method='GET')
    with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)

def remote_git_branch(repo_name,branch):
    if FEDMAP.get(repo_name)!=branch:raise ValueError('repository/branch denied')
    url=f'https://github.com/{repo_name}.git';ref=f'refs/heads/{branch}'
    p=subprocess.run(['git','ls-remote','--heads',url,ref],capture_output=True,text=True,timeout=25)
    if p.returncode or not p.stdout.strip():raise ValueError('remote ref unavailable')
    head=p.stdout.split()[0]
    with tempfile.TemporaryDirectory(prefix='lion-r10-mat04-') as td:
        subprocess.run(['git','init','--bare','-q',td],check=True,capture_output=True,timeout=10)
        f=subprocess.run(['git','-C',td,'fetch','-q','--depth=1','--filter=blob:none',url,head],capture_output=True,text=True,timeout=45)
        if f.returncode:raise ValueError('remote tree fetch failed')
        tree=git(td,'rev-parse','FETCH_HEAD^{tree}')
    return {'repository':repo_name,'branch':branch,'head':head,'tree':tree}

def model_json(base,path,timeout=4):
    req=urllib.request.Request(base.rstrip('/')+path,headers={'User-Agent':'LION-R10-MAT09/1'},method='GET')
    with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
def mission_control_json(path,timeout=5):
    if not isinstance(path,str) or not path.startswith('/api/v3/missions/') or '..' in path or len(path)>512:raise ValueError('mission control path denied')
    req=urllib.request.Request('http://127.0.0.1:8766'+path,headers={'User-Agent':'LION-R10-MAT04-MISSION/1'},method='GET')
    with urllib.request.urlopen(req,timeout=timeout) as res:
        if res.status!=200:raise ValueError('mission control status')
        return json.load(res)

def scan_clones():
    home=Path.home();roots=(home/'PycharmProjects',home/'Documents'/'Codex');out=[];seen=set()
    for base in roots:
        if not base.exists():continue
        for gitdir in base.glob('**/.git'):
            if len(gitdir.relative_to(base).parts)>7:continue
            repo=gitdir.parent
            key=str(repo)
            if key in seen:continue
            seen.add(key)
            try:
                origin=git(repo,'config','--get','remote.origin.url')
                head=git(repo,'rev-parse','HEAD');branch=git(repo,'branch','--show-current');dirty=len(git(repo,'status','--porcelain').splitlines())
                out.append({'path':key,'origin':origin,'head':head,'branch':branch,'dirty':dirty})
            except Exception:continue
    return out[:128]
def validate_receipt_object(rec):
    if type(rec) is not dict:return False
    needed={'task_id','drone_id','runtime_identity','role','input_digest','result_digest','started_at','completed_at','status','authority_effect','result','receipt_digest'}
    if set(rec)!=needed or rec.get('authority_effect')!='NONE':return False
    payload={k:rec[k] for k in rec if k!='receipt_digest'}
    return digest(payload)==rec['receipt_digest'] and digest(rec['result'])==rec['result_digest']

def execute(role,op,args,repo,model):
    if type(args) is not dict:raise ValueError('args')
    if role=='LOCAL_REPOSITORY_CURRENTNESS':
        if op=='head_tree':return {'head':git(repo,'rev-parse','HEAD'),'tree':git(repo,'rev-parse','HEAD^{tree}')}
        if op=='status':return git(repo,'status','--porcelain').splitlines()
    elif role=='LOCAL_REPOSITORY_CONTENT':
        if op=='read_file':
            p=safe_path(repo,args.get('path'));b=p.read_bytes()
            if len(b)>262144:raise ValueError('file too large')
            return {'path':str(p.relative_to(Path(repo).resolve())).replace('\\','/'),'sha256':hashlib.sha256(b).hexdigest(),'text':b.decode('utf-8')}
        if op=='search':
            q=args.get('query');limit=args.get('limit',20)
            if not isinstance(q,str) or not q or type(limit) is not int or not 1<=limit<=50:raise ValueError('query')
            root=Path(repo).resolve();out=[]
            for base,dirs,files in os.walk(root):
                dirs[:]=[d for d in dirs if d not in {'.git','.venv','node_modules','__pycache__'}]
                for name in files:
                    p=Path(base)/name
                    if p.suffix.lower() not in {'.py','.md','.json','.yaml','.yml','.txt','.toml'}:continue
                    try:t=p.read_text(encoding='utf-8')
                    except (OSError,UnicodeError):continue
                    i=t.lower().find(q.lower())
                    if i>=0:
                        out.append({'path':str(p.relative_to(root)).replace('\\','/'),'snippet':t[max(0,i-120):i+700]})
                        if len(out)>=limit:return out
            return out
    elif role=='LOCAL_CLONE_INVENTORY' and op=='local_clones':return scan_clones()
    elif role=='FEDERATION_CURRENTNESS':
        if op=='github_branch':return remote_git_branch(args.get('repository'),args.get('branch'))
        if op=='federation':return [remote_git_branch(x,b) for x,b in FED]
        if op=='mission_recent':return mission_control_json('/api/v3/missions/recent')
        if op=='mission_process':
            mid=args.get('mission_id')
            import re
            if not isinstance(mid,str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',mid) is None:raise ValueError('mission_id')
            return mission_control_json('/api/v3/missions/'+mid+'/process')
    elif role=='PUBLIC_WEB_SEARCH' and op=='web_search':return list(PublicWebReadBroker().search(args.get('query'),args.get('limit',5)))
    elif role=='PUBLIC_WEB_FETCH' and op=='web_fetch':return PublicWebReadBroker().fetch(args.get('url')).as_dict()
    elif role=='WEB_SECURITY_FALSIFIER' and op=='validate_web':
        url=args.get('url');validate_public_https_url(url);return {'url':url,'public_https':True,'authority_effect':'NONE'}
    elif role in {'SOURCE_PROVENANCE_VALIDATOR','RESULT_VALIDATOR'} and op=='validate_receipt':
        rec=args.get('receipt');return {'valid':validate_receipt_object(rec),'receipt_digest':rec.get('receipt_digest') if isinstance(rec,dict) else None}
    elif role=='MODEL_GPU_OBSERVER':
        if op=='model_health':return {'health':model_json(model,'/health'),'models':model_json(model,'/v1/models').get('data',[])}
        if op=='gpu_state':
            exe='nvidia-smi.exe' if os.name=='nt' else 'nvidia-smi'
            p=subprocess.run([exe,'--query-gpu=name,uuid,driver_version,memory.total,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True,timeout=10)
            if p.returncode:raise ValueError('gpu observer failed')
            return {'raw':p.stdout.strip()}
    elif role in {'MATERIAL_COORDINATOR','FINAL_RECONCILER'} and op in {'coordinate','reconcile'}:
        rows=args.get('receipt_digests')
        if type(rows) is not list or not all(isinstance(x,str) and len(x)==64 for x in rows):raise ValueError('receipt digests')
        return {'receipt_digests':rows,'aggregate_digest':digest(sorted(rows)),'authority_effect':'NONE'}
    raise ValueError('operation denied')

def main():
    p=argparse.ArgumentParser();p.add_argument('--drone-id',required=True,choices=tuple(ROLES));p.add_argument('--runtime-dir',required=True);p.add_argument('--repo',required=True);p.add_argument('--model',default='http://127.0.0.1:8772');a=p.parse_args()
    role=ROLES[a.drone_id];runtime=Path(a.runtime_dir).resolve();inbox=runtime/'inbox'/a.drone_id;outbox=runtime/'outbox'/a.drone_id;health=runtime/'health'/f'{a.drone_id}.json';seenfile=runtime/'seen'/f'{a.drone_id}.txt'
    inbox.mkdir(parents=True,exist_ok=True);outbox.mkdir(parents=True,exist_ok=True);seenfile.parent.mkdir(parents=True,exist_ok=True)
    runtime_identity=str(uuid.uuid4());seen=set(seenfile.read_text(encoding='utf-8').splitlines()) if seenfile.exists() else set()
    atomic_json(health,{'drone_id':a.drone_id,'role':role,'runtime_identity':runtime_identity,'pid':os.getpid(),'started_at':now(),'status':'READY','authority_effect':'NONE'})
    while True:
        for taskfile in sorted(inbox.glob('*.json')):
            started=now();status='DENY';result={'reason':'invalid task'};task_id=taskfile.stem;input_digest=''
            try:
                task=json.loads(taskfile.read_text(encoding='utf-8'));expected={'task_id','drone_id','operation','args','created_at'}
                if type(task) is not dict or set(task)!=expected:raise ValueError('task schema')
                task_id=task['task_id'];input_digest=digest(task)
                if task['drone_id']!=a.drone_id:raise ValueError('forged drone identity')
                if task_id in seen:raise ValueError('duplicate task id')
                seen.add(task_id);seenfile.open('a',encoding='utf-8').write(task_id+'\n')
                result=execute(role,task['operation'],task['args'],a.repo,a.model);status='PASS'
            except Exception as e:result={'reason':type(e).__name__+':'+str(e)}
            payload={'task_id':task_id,'drone_id':a.drone_id,'runtime_identity':runtime_identity,'role':role,'input_digest':input_digest,'result_digest':digest(result),'started_at':started,'completed_at':now(),'status':status,'authority_effect':'NONE','result':result}
            payload['receipt_digest']=digest(payload);atomic_json(outbox/f'{task_id}.json',payload)
            try:taskfile.unlink()
            except OSError:pass
        # refresh liveness without changing immutable identity
        try:
            h=json.loads(health.read_text(encoding='utf-8'));h['observed_at']=now();atomic_json(health,h)
        except Exception:pass
        time.sleep(0.08)
if __name__=='__main__':main()
