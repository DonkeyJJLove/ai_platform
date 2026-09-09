#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, pwd, re, shutil, socket, struct, subprocess, sys
from pathlib import Path
from typing import Any

SCHEMA='1.0.0'
RUNNER_USER='lion-maintenance-runner'
EXPECTED_ROOT_UID=0
PROVIDER_SOCKET='/run/lion-docker-p0/provider.sock'
POD_PROVIDER_SOCKET='/run/lion-k3s-vkt-r3/provider.sock'
FIXED_REPO=Path('/opt/lion/effect-admission/scale64-repo')
FIXED_IDENTITY=Path('/opt/lion/effect-admission/scale64-source-identity.json')
STATE_ROOT=Path('/var/lib/lion-runner-exec')
WORKSPACE_ROOT=Path('/opt/lion/effect-admission/workspaces')
HEX40=re.compile(r'^[0-9a-f]{40}$')
HEX64=re.compile(r'^[0-9a-f]{64}$')
SAFE_RUN_ID=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
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
 'cyber_lion.tests.test_lion_k3s_pod_materializer',
 'cyber_lion.tests.test_lion_k3s_pod_provider',
)
PYCOMPILE_FILES=(
 'tools/p0_docker_scale64_soak.py','tools/p0_docker_drone_runtime.py','tools/p0_rootless_docker_provider.py',
 'tools/lion_effect_admission_broker.py','tools/lion_runner_exec_provider.py','tools/lion_runner_exec_client.py',
 'tools/lion_k3s_pod_provider.py','tools/lion_k3s_pod_provider_client.py','tools/lion_k3s_pod_materializer.py','tools/lion_lpcl_autonomous_vulnerability_research.py',
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
    if p.stat().st_uid != os.geteuid(): raise Deny('repo-owner-mismatch')
    if p.parent.stat().st_uid != os.geteuid(): raise Deny('workspace-owner-mismatch')
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
def pod_provider_call(op:str,head:str,tree:str,run_id:str)->dict[str,Any]:
    allowed={"PRECHECK_POD_RUNTIME","PREPARE_LOCAL_K8S","MATERIALIZE_VKT_PODS","READ_POD_EVIDENCE","STOP_VKT_PODS"}
    if op not in allowed: raise Deny('pod-provider-operation-denied')
    if not isinstance(run_id,str) or not SAFE_RUN_ID.fullmatch(run_id): raise Deny('pod-provider-run-id-invalid')
    req={
        'schema_version':'1.0.0',
        'request_id':sha256(os.urandom(32)),
        'operation':op,
        'mission_id':'VKT-R3-384-REAL-POD-MISSION-CONTROL-R2',
        'run_id':run_id,
        'source_head':head,
        'source_tree':tree,
    }
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    sock.connect(POD_PROVIDER_SOCKET)
    sock.sendall(canonical(req)+b'\n'); sock.shutdown(socket.SHUT_WR)
    data=bytearray()
    while True:
        part=sock.recv(65536)
        if not part: break
        data.extend(part)
        if len(data)>MAX_RESPONSE: raise Deny('pod-provider-response-too-large')
    sock.close()
    value=json.loads(bytes(data).decode())
    if not isinstance(value,dict) or value.get('ok') is not True or not isinstance(value.get('result'),dict):
        raise Deny('pod-provider-call-failed:'+str(value.get('error') if isinstance(value,dict) else 'malformed'))
    return value['result']

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
        if len(log_raw)>MAX_LOG: log_raw=log_raw$Ô…ôÄôs¥Ð¢Wf–FVæ6SÔæöæS²6÷W&6Uö†6ƒÔæöæP¢–bWf–FVæ6U÷F‚æ—5öf–ÆR‚“ ¢&sÖWf–FVæ6U÷F‚ç&VEö'—FW2‚¢–bÆVâ‡&r“äÔ…ôUd”DTä4S¢&—6RFVç’‚vWf–FVæ6R×FöòÖÆ&vRr¢6÷W&6Uö†6ƒ×6†#Sb‡&r“²Wf–FVæ6SÖ§6öâæÆöG2‡&ræFV6öFR‚’¢–bæ÷B—6–ç7Fæ6R†Wf–FVæ6RÆF–7B“¢&—6RFVç’‚vWf–FVæ6RÖæ÷BÖö&¦V7Br¢&WGW&â²w&WGW&æ6öFRs§&ö2ç&WGW&æ6öFRÂvÆörs¦Æöu÷&ræFV6öFR‚wWFbÓ‚rÂw&WÆ6Rr’ÂvWf–FVæ6Rs¦Wf–FVæ6RÂw6÷W&6UöWf–FVæ6U÷6†#Sbs§6÷W&6Uö†6‡Ð¢f–æÆÇ“ ¢6‡WF–Âç&×G&VR‡'VåöF—"Æ–væ÷&UöW'&÷'3ÕG'VR¦FVb†æFÆR‡&W¦F–7E·7G"Äç•Ò’ÓæF–7E·7G"Äç•Ó ¢–bVW%÷V–B‚’ÔU…T5DTEõ$ôõEõT”C¢&—6RFVç’‚v6ÆÆW"Öæ÷B×&ö÷Br¢–bvBævWGwV–B†÷2ævWFWV–B‚’’çuöæÖRÕ%TääU%õU4U#¢&—6RFVç’‚w&÷f–FW"×w&öær×W6W"r¢–b&WævWB‚w66†VÖ÷fW'6–öâr’Õ44„TÔ¢&—6RFVç’‚w66†VÖÖÖ—6ÖF6‚r¢&WV—&Uö†WƒcB‡&WævWB‚w&WVW7Eö–Br’Âw&WVW7Eö–Br“²÷×&WævWB‚v÷W&F–öâr¢–b÷ÓÒt”DTåD•E’s ¢–b6WB‡&W’×²w66†VÖ÷fW'6–öârÂw&WVW7Eö–BrÂv÷W&F–öâwÓ¢&—6RFVç’‚v–FVçF—G’Öf–VÆB×6WBr¢&WGW&â²wW6W&æÖRs¥%TääU%õU4U"ÂwV–Bs¦÷2ævWFWV–B‚’Âvv–Bs¦÷2ævWFVv–B‚’Âw7WÆVÖVçF'•öw&÷W2s¦÷2ævWFw&÷W2‚’ÂvæõöæWu÷&—g2s¦æõöæWu÷&—g2‚—Ð¢–b÷–â²u5DD”5õTä•EDU5BrÂu5DD”5õ”4ôÕ”ÄRwÓ ¢–b6WB‡&W’×²w66†VÖ÷fW'6–öârÂw&WVW7Eö–BrÂv÷W&F–öârÂw&Wõ÷F‚rÂw6÷W&6Uö†VBrÂw6÷W&6U÷G&VRwÓ¢&—6RFVç’‚w7FF–2Öf–VÆB×6WBr¢†VC×&WV—&Uö†WƒC‡&W²w6÷W&6Uö†VBuÒÂw6÷W&6Uö†VBr“²G&VS×&WV—&Uö†WƒC‡&W²w6÷W&6U÷G&VRuÒÂw6÷W&6U÷G&VRr“²×&Wõ÷F‚‡&W²w&Wõ÷F‚uÒ“²fW&–g•÷&Wò‡Æ†VBÇG&VR¢&wcÕ²r÷W7"ö&–â÷—F†öã2rÂrÖÒrÂwVæ—GFW7BrÂ¥5DD”5ôÔôETÄU5Ò–b÷ÓÒu5DD”5õTä•EDU5BrVÇ6R²r÷W7"ö&–â÷—F†öã2rÂrÖÒrÂw•ö6ö×–ÆRrÂ¥”4ôÕ”ÄUôd”ÄU5Ð¢&ö3×'Vâ†&wbÆ7vC×ÆVçcÖ&÷VæFVEöVçb‡’ÇF–ÖV÷WCÓ3–b÷ÓÒu5DD”5õTä•EDU5BrVÇ6R“¢–b&ö2ç&WGW&æ6öFRÓ¢&—6RFVç’†÷æÆ÷vW"‚’²rÖf–ÆVC¢r·&ö2ç7FF÷WBæFV6öFR‚wWFbÓ‚rÂw&WÆ6Rr•²ÓC¥Ò¢&WGW&â²w7FGW2s¢u52rÂv÷W&F–öâs¦÷Ð¢–b÷ÓÒu$õd”DU%ô4ÄÂs ¢–b6WB‡&W’×²w66†VÖ÷fW'6–öârÂw&WVW7Eö–BrÂv÷W&F–öârÂw&÷f–FW%ö÷W&F–öârÂw6÷W&6Uö†VBrÂw6÷W&6U÷G&VRwÓ¢&—6RFVç’‚w&÷f–FW"Öf–VÆB×6WBr¢†VC×&WV—&Uö†WƒC‡&W²w6÷W&6Uö†VBuÒÂw6÷W&6Uö†VBr“²G&VS×&WV—&Uö†WƒC‡&W²w6÷W&6U÷G&VRuÒÂw6÷W&6U÷G&VRr¢&WGW&â&÷f–FW%ö6ÆÂ‡&W²w&÷f–FW%ö÷W&F–öâuÒÆ†VBÇG&VR¢–b÷ÓÒuôEõ$õd”DU%ô4ÄÂs ¢–b6WB‡&W’×²w66†VÖ÷fW'6–öârÂw&WVW7Eö–BrÂv÷W&F–öârÂw&÷f–FW%ö÷W&F–öârÂw6÷W&6Uö†VBrÂw6÷W&6U÷G&VRrÂw'Våö–BwÓ¢&—6RFVç’‚wöB×&÷f–FW"Öf–VÆB×6WBr¢†VC×&WV—&Uö†WƒC‡&W²w6÷W&6Uö†VBuÒÂw6÷W&6Uö†VBr“²G&VS×&WV—&Uö†WƒC‡&W²w6÷W&6U÷G&VRuÒÂw6÷W&6U÷G&VRr¢&WGW&âöE÷&÷f–FW%ö6ÆÂ‡&W²w&÷f–FW%ö÷W&F–öâuÒÆ†VBÇG&VRÇ&W²w'Våö–BuÒ¢–b÷ÓÒu44ÄScEõ%Tâs ¢–b6WB‡&W’×²w66†VÖ÷fW'6–öârÂw&WVW7Eö–BrÂv÷W&F–öârÂw6÷W&6Uö†VBrÂw6÷W&6U÷G&VRrÂw'Vå÷&WVW7Eö–BwÓ¢&—6RFVç’‚w66ÆScBÖf–VÆB×6WBr¢&WGW&â66ÆScE÷'Vâ‡&WV—&Uö†WƒC‡&W²w6÷W&6Uö†VBuÒÂw6÷W&6Uö†VBr’Ç&WV—&Uö†WƒC‡&W²w6÷W&6U÷G&VRuÒÂw6÷W&6U÷G&VRr’Ç&WV—&Uö†WƒcB‡&W²w'Vå÷&WVW7Eö–BuÒÂw'Vå÷&WVW7Eö–Br’¢&—6RFVç’‚v÷W&F–öâÖæ÷BÖÆÆ÷vÆ—7FVBr¦FVbÖ–â‚’Óæ–çC ¢&–CÔæöæP¢G'“ ¢&W×&V6V—fR‚“²&–C×&WævWB‚w&WVW7Eö–Br’–b—6–ç7Fæ6R‡&WævWB‚w&WVW7Eö–Br’Ç7G"’VÇ6RæöæP¢&WÇ’‡²vö²s¥G'VRÂw&WVW7Eö–Bs§&–BÂw&W7VÇBs¦†æFÆR‡&W—Ò“²&WGW&â ¢W†6WBW†6WF–öâ2W†3 ¢&WÇ’‡²vö²s¤fÇ6RÂw&WVW7Eö–Bs§&–BÂvW'&÷"s§G—R†W†2’åõöæÖUõò²s¢r·7G"†W†2•³£C×Ò“²&WGW&â ¦–bõöæÖUõóÓÒuõöÖ–åõòs¢&—6R7—7FVÔW†—B†Ö–â‚’ 