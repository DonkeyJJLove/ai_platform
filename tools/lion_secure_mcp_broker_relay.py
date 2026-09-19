#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

SECURE="CHATGPT_OPENAI_SECURE_MCP_TUNNEL"
ATTEST="OPENAI_SECURE_MCP_TUNNEL_TOOL_ROUNDTRIP"
WAITING={"WAITING_SUPERVISOR","WAITING_OPERATOR_OVERDUE","QUEUED"}
FINAL={"RECONCILED","SUPERSEDED","FAILED"}

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def ts(v): return datetime.fromisoformat(str(v).replace("Z","+00:00"))
def sha(s): return hashlib.sha256(s.encode()).hexdigest()

def load(p,default=None):
    try:return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:return default

def atomic(p,v,mode=0o600):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2),encoding="utf-8")
    os.chmod(t,mode);os.replace(t,p)

def http(base,path,method="GET",body=None,headers=None,timeout=15):
    h={"Accept":"application/json","User-Agent":"LION-Secure-MCP-Broker-Relay/1"}
    if headers:h.update(headers)
    data=None
    if body is not None:
        data=json.dumps(body,separators=(",",":"),ensure_ascii=False).encode()
        h["Content-Type"]="application/json"
    req=urllib.request.Request(base.rstrip("/")+path,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode("utf-8");return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw=e.read().decode("utf-8","replace");raise RuntimeError(f"HTTP {e.code} {raw[:500]}") from e

def driver_ready(ipc,ttl=20):
    s=load(Path(ipc)/"node-manager-status.json") or {}
    try: age=(datetime.now(timezone.utc)-ts(s["observed_at"])).total_seconds()
    except Exception:return False,s
    return bool(s.get("worker_alive") and 0<=age<=ttl),s

def ingress_ready(base,token):
    try:return bool(http(base,"/health",headers={"X-LION-Token":token},timeout=3).get("ok"))
    except Exception:return False

def hb(a,key,state):
    return http(a.broker,"/api/v3/saas-broker/mediator/heartbeat","POST",{
      "mediator_id":"LION_OPENAI_SECURE_MCP_BRIDGE_R1","transport":SECURE,"state":state,
      "project_title":"LION_EVOLUSION","chat_title":"MISSION_SCOPED_THREAD",
      "browser":"OpenAI Secure MCP Tunnel + existing ChatGPT project wakeup","authority_effect":"NONE"
    },{"X-LION-Mediator-Key":key})

def make_turn(row):
    rid=row["request_id"]
    payload={
      "command_id":"MC-"+rid,"mission_id":row.get("mission_id"),"session_id":"CHATGPT-SAAS",
      "thread_id":row.get("thread_id"),"cursor":0,
      "input":"LION Mission Control SaaS request.\nAuthority effect: NONE. "
              "This is a cognitive request, not permission for external effects.\n"
              f"Broker request id: {rid}\nQuestion: {row['question']}\n\n"
              "Answer the question. Then complete this exact LION turn with lion_complete_turn, "
              'using response={"text":"<your answer>"} and actor="chatgpt-saas-mcp". '
              "Do not call any other write tool.",
      "metadata":{"source":"LION_MISSION_CONTROL","broker_request_id":rid,
        "request_code":row.get("request_code"),"scope_type":row.get("scope_type"),
        "scope_id":row.get("scope_id"),"thread_id":row.get("thread_id"),
        "transport":SECURE,"authority_effect":"NONE"}
    }
    return payload

def get_turn(a,token,turn_id):
    return http(a.ingress,f"/v1/turns/{turn_id}",headers={"X-LION-Token":token},timeout=10)["turn"]

def wake_prompt(turn_id,rid):
    return ("Use LION-MCP-R2.\n\n"
      f"Call lion_get_turn with:\nturn_id = {turn_id}\n\n"
      "Follow the input of that turn exactly.\n\n"
      "Then call lion_complete_turn for the same turn_id.\n"
      'Use your answer as response.text.\nactor = "chatgpt-saas-mcp"\n'
      "Do not call any other write tool.\n"
      f"Broker request id: {rid}")

def queue_wakeup(ipc,row,turn_id):
    q=wake_prompt(turn_id,row["request_id"])
    work={"schema":"lion.firefox-mediator-work/v2","request_id":row["request_id"],
      "question":q,"question_digest":sha(q),"claim_generation":row["claim_generation"],
      "mission_id":row.get("mission_id"),"thread_id":row.get("thread_id"),
      "scope_type":row.get("scope_type"),"scope_id":row.get("scope_id"),
      "transport":SECURE,"thread_policy":"ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER",
      "authority_effect":"NONE"}
    atomic(Path(ipc)/"inbox"/(row["request_id"]+".json"),work,0o644)

def claim_new(a,key,token,state_dir):
    pending=http(a.broker,"/api/v3/saas-broker/pending").get("requests") or []
    row=next((x for x in pending if x.get("transport")==SECURE and x.get("status") in WAITING),None)
    if not row:return
    rid=row["request_id"];sf=state_dir/(rid+".json")
    if sf.exists():return
    claim=http(a.broker,f"/api/v3/saas-broker/requests/{rid}/claim","POST",{},{"X-LION-Mediator-Key":key})
    turn=http(a.ingress,"/v1/turns","POST",make_turn(row),{"X-LION-Token":token})["turn"]
    rec={"schema":"lion.secure-mcp-broker-relay.state/v1","request_id":rid,
      "request_code":row.get("request_code"),"question_digest":row.get("question_digest"),
      "scope_type":row.get("scope_type"),"scope_id":row.get("scope_id"),
      "thread_id":row.get("thread_id"),"broker_transport":SECURE,
      "claim_generation":claim["claim_generation"],"claim_expires_at":claim.get("claim_expires_at"),
      "turn_id":turn["turn_id"],"turn_command_id":"MC-"+rid,"turn_request_hash":turn.get("request_hash"),
      "created_at":now(),"last_observed_at":now(),"state":"SAAS_DISPATCH_PENDING",
      "claim":claim,"response_digest":None,"broker_receipt_digest":None,
      "delivery_identity":"saas:"+rid,"reconciliation_state":"OPEN"}
    atomic(sf,rec);queue_wakeup(a,{**row,"claim_generation":claim["claim_generation"]},turn["turn_id"])
    rec["state"]="SAAS_ACTIVE";rec["last_observed_at"]=now();atomic(sf,rec)

def reconcile(a,key,token,sf,rec):
    rid=rec["request_id"];bs=http(a.broker,f"/api/v3/saas-broker/requests/{rid}")
    if bs.get("status")=="RESPONDED":
        rec.update(state="BROKER_RESPONDED",broker_receipt_digest=bs.get("receipt_digest"),last_observed_at=now())
    elif rec.get("turn_id"):
        turn=get_turn(a,token,rec["turn_id"]);rec["last_observed_at"]=now()
        if turn.get("status")=="COMPLETED":
            response=turn.get("response");answer=response.get("text") if isinstance(response,dict) else response
            if not isinstance(answer,str) or not answer.strip():
                rec.update(state="FAILED",error="completed turn missing response text")
            else:
                rec.update(state="TURN_COMPLETED",response_digest=sha(answer))
                c=rec["claim"]
                result=http(a.broker,f"/api/v3/saas-broker/requests/{rid}/respond","POST",{
                  "response_token":c["response_token"],"claim_generation":c["claim_generation"],
                  "answer":answer,"model_identity":"ChatGPT SaaS / LION-MCP-R2 + project wakeup",
                  "transport":SECURE,"attestation_class":ATTEST
                },{"X-LION-Mediator-Key":key},timeout=30)
                receipt=result.get("receipt") or {};binding=result.get("binding") or {}
                rec.update(state="BROKER_RESPONDED",broker_receipt_digest=receipt.get("receipt_digest"),
                           binding_id=binding.get("binding_id"),last_observed_at=now())
                if rec.get("broker_receipt_digest"):
                    try:http(a.broker,"/api/v3/saas-broker/session/attest","POST",
                      {"request_id":rid,"receipt_digest":rec["broker_receipt_digest"]},
                      {"X-LION-Mediator-Key":key},timeout=10)
                    except Exception:pass
    if rec.get("state")=="BROKER_RESPONDED":
        check=http(a.broker,f"/api/v3/saas-broker/requests/{rid}")
        if check.get("status")=="RESPONDED" and check.get("receipt_digest"):
            rec.update(state="RECONCILED",reconciliation_state="BROKER_RECEIPT_BOUND")
    atomic(sf,rec)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--broker",default="http://127.0.0.1:8766")
    ap.add_argument("--mediator-key-file",required=True)
    ap.add_argument("--ingress",default="http://127.0.0.1:8791")
    ap.add_argument("--ingress-token-file",required=True)
    ap.add_argument("--state-dir",required=True)
    ap.add_argument("--ipc-dir",required=True)
    ap.add_argument("--interval",type=float,default=1.0);ap.add_argument("--once",action="store_true")
    a=ap.parse_args();key=Path(a.mediator_key_file).read_text().strip();token=Path(a.ingress_token_file).read_text().strip()
    if len(key)<64 or len(token)<32:raise SystemExit("relay credentials unavailable")
    state_dir=Path(a.state_dir);state_dir.mkdir(parents=True,exist_ok=True);last_hb=0.0
    while True:
        ok_driver,_=driver_ready(a.ipc);state="READY" if ingress_ready(a.ingress,token) and ok_driver else "DEGRADED"
        try:
            if time.time()-last_hb>=10:hb(a,key,state);last_hb=time.time()
            for sf in sorted(state_dir.glob("saas-*.json")):
                rec=load(sf)
                if isinstance(rec,dict) and rec.get("state") not in FINAL:reconcile(a,key,token,sf,rec)
            if state=="READY":claim_new(a,key,token,state_dir)
            atomic(state_dir/"relay-status.json",{"schema":"lion.secure-mcp-broker-relay.status/v1",
              "status":state,"observed_at":now(),"broker":a.broker,"ingress":a.ingress,
              "wakeup_driver":"FIREFOX_NODE_PROJECT_MANAGER","authority_effect":"NONE"},0o644)
        except Exception as exc:
            atomic(state_dir/"relay-status.json",{"schema":"lion.secure-mcp-broker-relay.status/v1",
              "status":"DEGRADED","observed_at":now(),"error":type(exc).__name__+":"+str(exc)[:400],
              "authority_effect":"NONE"},0o644)
        if a.once:break
        time.sleep(max(0.2,a.interval))

if __name__=="__main__":main()
