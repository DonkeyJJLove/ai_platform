#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, pwd, re, shutil, socket, struct, subprocess, sys
from pathlib import Path
from typing import Any

SCHEMA='1.0.0'
RUNNER_USER='lion-maintenance-runner'
EXPECTED_ROOT_UID=0
PROVIDER_SOCKET='/run/lion-docker-p0/provider.sock'
FIXED_REPO=Path('/opt/lion/effect-admission/scale64-repo')
FIXED_IDENTITY=Path('/opt/lion/effect-admission/scale64-source-identity.json')
STATE_ROOT=Path('/var/lib/lion-runner-exec')
WORKSPACE_ROOT=Path('/opt/lion/effect-admission/workspaces')
HEX40=re.compile(r'^[0-9a-f]{40}$')
HEX64=re.compile(r'^[0-9a-f]{64}$')
MAX_REQUEST=64*1024
MAX_RESPONSE=10*1024*1024
MAX_LOG=1024*1024
MAX_EVIDENCE=8*1024*1024
STATIC_MODULES=(
 'cyber_lion.tests.test_p0_docker_scale64',
 'cyber_lion.tests.test_p0_rootless_docker_provider',
 'cyber_lion.tests.test_docker_fleet_polygon',
 'cyber_lion.tests.test_scale64_control_plane',
 'cyber_lion.tests.test_scale64_runner_exec',
)
PYCOMPILE_FILES=(
 'tools/p0_docker_scale64_soak.py','tools/p0_docker_drone_runtime.py','tools/p0_rootless_docker_provider.py',
 'tools/lion_effect_admission_broker.py','tools/lion_runner_exec_provider.py','tools/lion_runner_exec_client.py',
)

class Deny(RuntimeError): pass

def canonical(v:Any)->bytes: return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def require_hex40(v:Any,label:str)->str:
    if not isinstance(v,str) or not HEX40.fullmatch(v): raise Deny(label+':invalid')
    return v
def require_hex64(v:Any,label:str)->str:
    if not isinstance(v,str) or not HEX64.fullmatch(v): raise Deny(label+':invalid')
    return v
def peer_uid()->int:
    s=socket.fromfd(0,socket.AF_UNIX,socket.SOCK_STREAM)
    raw=s.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize('3i')); s.close()
    return struct.unpack('3i',raw)[1]
def receive()->dict[str,Any]:
    raw=sys.stdin.buffer.readline(MAX_REQUEST+1)
    if len(raw)>MAX_REQUEST: raise Deny('request-too-large')
    v=json.loads(raw.decode())
    if not isinstance(v,dict): raise Deny('request-not-object')
    return v
def reply(v:dict[str,Any])->None:
    raw=canonical(v)+b'\n'
    if len(raw)>MAX_RESPONSE: raw=canonical({'ok':False,'error':'response-too-large'})+b'\n'
    sys.stdout.buffer.write(raw); sys.stdout.buffer.flush()
def bounded_env(repo:Path|None=None)->dict[str,str]:
    e={'PATH':'/usr/bin:/bin','HOME':'/tmp','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'}
    if repo is not None: e['PYTHONPATH']=str(repo)
    return e
def run(argv:list[str],*,cwd:Path|None=None,env:dict[str,str]|None=None,timeout:int=600)->subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv,cwd=str(cwd) if cwd else None,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,shell=False,check=False,timeout=timeout)
def repo_path(v:Any)->Path:
    if not isinstance(v,str): raise Deny('repo-path-invalid')
    p=Path(v).resolve()
    try: p.relative_to(WORKSPACE_ROOT)
    except ValueError as exc: raise Deny('repo-path-outside-workspace') from exc
    if p.name!='repo' or not p.is_dir(): raise Deny('repo-path-shape')
    return p
def verify_repo(p:Path,head:str,tree:str)->None:
    a=subprocess.check_output(['/usr/bin/git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
    b=subprocess.check_output(['/usr/bin/git','-C',str(p),'rev-parse','HEAD^{tree}'],text=True).strip()
    if a!=head or b!=tree: raise Deny('repo-identity-mismatch')
def provider_call(op:str,head:str,tree:str)->dict[str,Any]:
    if op not in {'PING','LIST_FLEET_RESOURCES'}: raise Deny('provider-operation-denied')
    req={'schema_version':'1.0.0','request_id':sha256(os.urandom(32)),'operation':op,'mission_id':'lion-local-swarm-scale64','fleet_id':'lion-local-swarm-scale64','run_id':'scale64-precheck','source_head':head,'source_tree':tree,'plan_digest':sha256(b'lion-scale64-precheck'),'payload':{}}
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect(PROVIDER_SOCKET); s.sendall(canonical(req)+b'\n'); s.shutdown(socket.SHUT_WR)
    data=bytearray()
    while True:
        part=s.recv(65536)
        if not part: break
        data.extend(part)
        if len(data)>1024*1024: raise Deny('provider-response-too-large')
    s.close(); v=json.loads(bytes(data).decode())
    if not isinstance(v,dict) or v.get('ok') is not True or not isinstance(v.get('result'),dict): raise Deny('provider-call-failed')
    return v['result']
def no_new_privs()->int:
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('NoNewPrivs:'): return int(line.split()[1])
    raise Deny('nnp-unavailable')
def scale64_run(head:str,tree:str,request_id:str)->dict[str,Any]:
    require_hex40(head,'source_head'); require_hex40(tree,'source_tree'); require_hex64(request_id,'run_request_id')
    if not FIXED_REPO.is_dir() or not FIXED_IDENTITY.is_file(): raise Deny('fixed-source-missing')
    ident=json.loads(FIXED_IDENTITY.read_text())
    if ident.get('source_head')!=head or ident.get('source_tree')!=tree: raise Deny('fixed-source-mismatch')
    STATE_ROOT.mkdir(parents=True,exist_ok=True)
    run_dir=STATE_ROOT/request_id
    if run_dir.exists(): raise Deny('runner-request-replay')
    run_dir.mkdir(mode=0o700)
    log_path=run_dir/'run.log'; evidence_path=run_dir/'evidence.json'
    try:
        with log_path.open('wb',buffering=0) as log:
            proc=subprocess.run(['/usr/bin/python3','tools/p0_docker_scale64_soak.py','--source-head',head,'--source-tree',tree,'--duration-seconds','180','--poll-seconds','15','--evidence-out',str(evidence_path)],cwd=str(FIXED_REPO),env=bounded_env(FIXED_REPO),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,shell=False,check=False,timeout=900)
        log_raw=log_path.read_bytes()
        if len(log_raw)>MAX_LOG: log_raw=log_raw[-MAX_LOG:]
        evidence=None; source_hash=None
        if evidence_path.is_file():
            raw=evidence_path.read_bytes()
            if len(raw)>MAX_EVIDENCE: raise Deny('evidence-too-large')
            source_hash=sha256(raw); evidence=json.loads(raw.decode())
            if not isinstance(evidence,dict): raise Deny('evidence-not-object')
        return {'returncode':proc.returncode,'log':log_raw.decode('utf-8','replace'),'evidence':evidence,'source_evidence_sha256':source_hash}
    finally:
        shutil.rmtree(run_dir,ignore_errors=True)
def handle(req:dict[str,Any])->dict[str,Any]:
    if peer_uid()!=EXPECTED_ROOT_UID: raise Deny('caller-not-root')
    if pwd.getpwuid(os.geteuid()).pw_name!=RUNNER_USER: raise Deny('provider-wrong-user')
    if req.get('schema_version')!=SCHEMA: raise Deny('schema-mismatch')
    require_hex64(req.get('request_id'),'request_id'); op=req.get('operation')
    if op=='IDENTITY':
        if set(req)!={'schema_version','request_id','operation'}: raise Deny('identity-field-set')
        return {'username':RUNNER_USER,'uid':os.geteuid(),'gid':os.getegid(),'supplementary_groups':os.getgroups(),'no_new_privs':no_new_privs()}
    if op in {'STATIC_UNITTEST','STATIC_PYCOMPILE'}:
        if set(req)!={'schema_version','request_id','operation','repo_path','source_head','source_tree'}: raise Deny('static-field-set')
        head=require_hex40(req['source_head'],'source_head'); tree=require_hex40(req['source_tree'],'source_tree'); p=repo_path(req['repo_path']); verify_repo(p,head,tree)
        argv=['/usr/bin/python3','-m','unittest',*STATIC_MODULES] if op=='STATIC_UNITTEST' else ['/usr/bin/python3','-m','py_compile',*PYCOMPILE_FILES]
        proc=run(argv,cwd=p,env=bounded_env(p),timeout=300 if op=='STATIC_UNITTEST' else 90)
        if proc.returncode!=0: raise Deny(op.lower()+'-failed:'+proc.stdout.decode('utf-8','replace')[-4000:])
        return {'status':'PASS','operation':op}
    if op=='PROVIDER_CALL':
        if set(req)!={'schema_version','request_id','operation','provider_operation','source_head','source_tree'}: raise Deny('provider-field-set')
        head=require_hex40(req['source_head'],'source_head'); tree=require_hex40(req['source_tree'],'source_tree')
        return provider_call(req['provider_operation'],head,tree)
    if op=='SCALE64_RUN':
        if set(req)!={'schema_version','request_id','operation','source_head','source_tree','run_request_id'}: raise Deny('scale64-field-set')
        return scale64_run(require_hex40(req['source_head'],'source_head'),require_hex40(req['source_tree'],'source_tree'),require_hex64(req['run_request_id'],'run_request_id'))
    raise Deny('operation-not-allowlisted')
def main()->int:
    rid=None
    try:
        req=receive(); rid=req.get('request_id') if isinstance(req.get('request_id'),str) else None
        reply({'ok':True,'request_id':rid,'result':handle(req)}); return 0
    except Exception as exc:
        reply({'ok':False,'request_id':rid,'error':type(exc).__name__+':'+str(exc)[:4000]}); return 2
if __name__=='__main__': raise SystemExit(main())
