#!/usr/bin/env python3
from __future__ import annotations
import fcntl,json,os,time,urllib.request,urllib.parse,socket
from datetime import datetime,timezone
from pathlib import Path
from tools.lion_local_intelligence_runtime import LpclControlBridge,local_assignment_worker_once

WORKER_ID=os.environ["LION_MATERIAL_WORKER_ID"]
MC=os.environ.get("LION_MISSION_CONTROL_URL","http://host.docker.internal:8766")
MODEL=os.environ.get("LION_LOCAL_MODEL_URL","http://host.docker.internal:8772")
STATUS=Path("/status")/(WORKER_ID+".json")
LOCK=Path("/gate/model.lock")
MODEL_NAME="gpt-oss-20b-MXFP4"

def stamp(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def write_status(**x):
    value={"schema":"lion.docker-local-worker.status/v1","observed_at":stamp(),"material_worker_id":WORKER_ID,"mission_control":MC,"model_endpoint":MODEL,"model":MODEL_NAME,**x}
    tmp=STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,sort_keys=True)+chr(10),encoding="utf-8")
    os.replace(tmp,STATUS)

def force_ipv4_url(url):
    p=urllib.parse.urlsplit(url)
    if p.hostname!='host.docker.internal':return url
    ip=socket.gethostbyname(p.hostname)
    port=p.port
    netloc=ip+((':'+str(port)) if port else '')
    return urllib.parse.urlunsplit((p.scheme,netloc,p.path,p.query,p.fragment))

def request(url,body=None,timeout=10):
    data=None;headers={"User-Agent":"LION-Docker-Worker/1"}
    if body is not None:
        data=json.dumps(body).encode()
        headers["Content-Type"]="application/json"
    url=force_ipv4_url(url)
    req=urllib.request.Request(url,data=data,headers=headers,method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

bridge=LpclControlBridge(None,MC)

def modelprov(messages,max_tokens=384):
    LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try:
            models=request(MODEL.rstrip("/")+"/v1/models",timeout=5)
            ids=[str(x.get("id") or x.get("name") or x.get("model") or "") for x in (models.get("data") or models.get("models") or []) if isinstance(x,dict)]
            if not any(MODEL_NAME in x for x in ids): raise RuntimeError("local model identity mismatch")
            out=request(MODEL.rstrip("/")+"/v1/chat/completions",{"messages":messages,"max_tokens":int(max_tokens),"temperature":0.1,"stream":False},timeout=120)
            return out["choices"][0]["message"]["content"]
        finally:
            fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def _assignment_input(row):
    value=row.get("input")
    if isinstance(value,dict):return value
    raw=row.get("input_json")
    if isinstance(raw,str):
        try:
            parsed=json.loads(raw)
            if isinstance(parsed,dict):return parsed
        except Exception:pass
    return {}

def material_sandbox_canary_once():
    listing=request(MC.rstrip("/")+"/api/v3/local/assignments?limit=64",timeout=5)
    for row in listing.get("assignments") or []:
        if row.get("material_drone_id")!=WORKER_ID:continue
        value=_assignment_input(row)
        if value.get("kind")!="MATERIAL_SANDBOX_CANARY":continue
        aid=str(row.get("assignment_id") or "")
        if not aid:continue
        claimed=request(MC.rstrip("/")+"/api/v3/local/assignments/claim",{"assignment_id":aid,"material_drone_id":WORKER_ID},timeout=10)
        value=_assignment_input(claimed) or value
        token=str(value.get("token") or "")
        target_name=str(value.get("target_name") or "")
        content=str(value.get("content") or "")
        expected=str(value.get("expected_sha256") or "")
        if not token or not target_name or target_name!=Path(target_name).name or len(content.encode("utf-8"))>4096:
            raise RuntimeError("invalid material sandbox canary contract")
        data=content.encode("utf-8")
        if __import__("hashlib").sha256(data).hexdigest()!=expected:
            raise RuntimeError("material sandbox canary expected digest mismatch")
        root=Path("/tmp/lion-r23-material-canary");root.mkdir(parents=True,exist_ok=True)
        target=root/target_name;tmp=target.with_suffix(".tmp")
        with tmp.open("wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,target)
        observed=target.read_bytes();observed_sha=__import__("hashlib").sha256(observed).hexdigest()
        if observed_sha!=expected or observed!=data:
            raise RuntimeError("material sandbox canary readback mismatch")
        result={"kind":"MATERIAL_SANDBOX_CANARY","token":token,"material_worker_id":WORKER_ID,"target":str(target),"bytes_written":len(data),"expected_sha256":expected,"observed_sha256":observed_sha,"readback_match":True,"sandbox_scope":"CONTAINER_TMPFS","authority_effect":"NONE"}
        return request(MC.rstrip("/")+"/api/v3/local/assignments/receipt",{"assignment_id":aid,"material_drone_id":WORKER_ID,"lease_generation":claimed.get("lease_generation"),"status":"PASS","result":result,"effect_receipt_digest":None,"authority_effect":"NONE"},timeout=10)
    return None

write_status(state="STARTING",last_receipt=None,last_error=None)
while True:
    try:
        request(MC.rstrip("/")+"/api/v3/local/assignments?limit=1",timeout=5)
        request(MODEL.rstrip("/")+"/v1/models",timeout=5)
        write_status(state="READY",last_receipt=None,last_error=None)
        receipt=material_sandbox_canary_once()
        if receipt is None:
            receipt=local_assignment_worker_once(bridge,modelprov,material_drone_id=WORKER_ID)
        if receipt is not None:
            print(json.dumps({"event":"LION_WORKER_RECEIPT","worker":WORKER_ID,"receipt":receipt},ensure_ascii=False),flush=True)
            write_status(state="READY",last_receipt=receipt,last_error=None)
        time.sleep(0.75)
    except KeyboardInterrupt:
        write_status(state="STOPPED",last_receipt=None,last_error=None)
        raise
    except Exception as exc:
        err=type(exc).__name__+":"+str(exc)[:800]
        print(json.dumps({"event":"LION_WORKER_ERROR","worker":WORKER_ID,"error":err}),flush=True)
        write_status(state="DEGRADED",last_receipt=None,last_error=err)
        time.sleep(2)
