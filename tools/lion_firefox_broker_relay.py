#!/usr/bin/env python3
"""Secret-holding WSL relay between Mission Control SaaS broker and Firefox mediator IPC.

The broker mediator key and response_token never leave LION-AUTH-LAB. Windows
receives only request_id/question/claim_generation and returns answer text.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time, urllib.request, urllib.error
from pathlib import Path

FIREFOX_TRANSPORT="CHATGPT_FIREFOX_PROJECT_MEDIATED"
FIREFOX_ATTESTATION="FIREFOX_UI_PROJECT_BOUND_OBSERVATION"
WAITING={"WAITING_SUPERVISOR","WAITING_OPERATOR_OVERDUE","QUEUED"}

def atomic_json(path:Path,value,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True),encoding='utf-8');os.chmod(tmp,mode);os.replace(tmp,path)

def load_json(path:Path,default=None):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except Exception:return default

def http_json(base,path,method='GET',body=None,key=None,timeout=15):
    data=None;headers={'Accept':'application/json','User-Agent':'LION-Firefox-Broker-Relay/1'}
    if body is not None:
        data=json.dumps(body,separators=(',',':'),ensure_ascii=False).encode();headers['Content-Type']='application/json'
    if key:headers['X-LION-Mediator-Key']=key
    req=urllib.request.Request(base.rstrip('/')+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raw=e.read().decode('utf-8','replace')
        raise RuntimeError(f'HTTP {e.code} {raw[:800]}') from e

def safe_unlink(path):
    try:Path(path).unlink()
    except FileNotFoundError:pass

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--broker',default='http://127.0.0.1:8766');ap.add_argument('--key-file',default='/var/lib/sentinelx/uploads/lion-mission-control-v3/saas-mediator.key');ap.add_argument('--state-dir',default='/var/lib/sentinelx/uploads/firefox-mediator-relay');ap.add_argument('--ipc-dir',required=True);ap.add_argument('--interval',type=float,default=0.5);ap.add_argument('--once',action='store_true');a=ap.parse_args()
    state=Path(a.state_dir);claims=state/'claims';ipc=Path(a.ipc_dir);inbox=ipc/'inbox';outbox=ipc/'outbox';receipts=ipc/'receipts';archive=ipc/'archive'
    for p in (state,claims,ipc,inbox,outbox,receipts,archive):p.mkdir(parents=True,exist_ok=True)
    key=Path(a.key_file).read_text(encoding='utf-8').strip()
    if len(key)<64:raise SystemExit('mediator key unavailable')
    def heartbeat():
        st=load_json(ipc/'mediator-status.json') or {'mediator_id':'LION_FIREFOX_MEDIATOR_R1','transport':FIREFOX_TRANSPORT,'state':'STARTING','project_title':None,'chat_title':None,'browser':'Firefox Developer Edition','authority_effect':'NONE'}
        payload={k:st.get(k) for k in ('mediator_id','transport','state','project_title','chat_title','browser','authority_effect')}
        payload['mediator_id']=payload.get('mediator_id') or 'LION_FIREFOX_MEDIATOR_R1';payload['transport']=FIREFOX_TRANSPORT;payload['browser']=payload.get('browser') or 'Firefox Developer Edition';payload['authority_effect']='NONE'
        return http_json(a.broker,'/api/v3/saas-broker/mediator/heartbeat','POST',payload,key)
    def finish_answers():
        for answer_file in sorted(outbox.glob('*.json')):
            ans=load_json(answer_file);rid=ans.get('request_id') if isinstance(ans,dict) else None
            secret=load_json(claims/(str(rid)+'.json')) if rid else None
            if not rid or not secret:continue
            if ans.get('claim_generation')!=secret.get('claim_generation'):
                atomic_json(receipts/(rid+'.json'),{'request_id':rid,'status':'REJECTED_STALE_LOCAL_ANSWER','authority_effect':'NONE'},0o644);safe_unlink(answer_file);continue
            payload={'response_token':secret['response_token'],'claim_generation':secret['claim_generation'],'answer':str(ans.get('answer') or ''),'model_identity':str(ans.get('model_identity') or 'ChatGPT UI / LION_EVOLUSION'),'transport':FIREFOX_TRANSPORT,'attestation_class':FIREFOX_ATTESTATION}
            try:res=http_json(a.broker,f'/api/v3/saas-broker/requests/{rid}/respond','POST',payload,key,30)
            except Exception as exc:
                status=http_json(a.broker,f'/api/v3/saas-broker/requests/{rid}')
                if status.get('status')=='RESPONDED':res={'status':'RESPONDED','recovered':True,'receipt_digest':status.get('receipt_digest')}
                elif status.get('status')!='CLAIMED':
                    atomic_json(receipts/(rid+'.json'),{'request_id':rid,'status':'BROKER_REJECTED','reason':type(exc).__name__+':'+str(exc)[:300],'broker_status':status.get('status'),'authority_effect':'NONE'},0o644);safe_unlink(answer_file);safe_unlink(claims/(rid+'.json'));safe_unlink(inbox/(rid+'.json'));continue
                else:continue
            public={'request_id':rid,'status':res.get('status'),'receipt_digest':((res.get('receipt') or {}).get('receipt_digest') if isinstance(res,dict) else None),'authority_effect':'NONE'}
            atomic_json(receipts/(rid+'.json'),public,0o644)
            work=inbox/(rid+'.json')
            if work.exists():os.replace(work,archive/(rid+'.work.json'))
            if answer_file.exists():os.replace(answer_file,archive/(rid+'.answer.json'))
            safe_unlink(claims/(rid+'.json'))
    def recover_claims():
        for secret_file in list(claims.glob('*.json')):
            secret=load_json(secret_file);rid=secret.get('request_id') if isinstance(secret,dict) else None
            if not rid:continue
            try:status=http_json(a.broker,f'/api/v3/saas-broker/requests/{rid}')
            except Exception:continue
            if status.get('status')=='RESPONDED':
                atomic_json(receipts/(rid+'.json'),{'request_id':rid,'status':'RESPONDED','receipt_digest':status.get('receipt_digest'),'authority_effect':'NONE'},0o644);safe_unlink(secret_file);safe_unlink(inbox/(rid+'.json'));continue
            if status.get('status')!='CLAIMED' or status.get('claim_generation')!=secret.get('claim_generation'):
                safe_unlink(secret_file);safe_unlink(inbox/(rid+'.json'))
    def claim_new():
        if any(claims.glob('*.json')):return
        pending=http_json(a.broker,'/api/v3/saas-broker/pending').get('requests') or []
        row=next((r for r in pending if r.get('transport')==FIREFOX_TRANSPORT and r.get('status') in WAITING),None)
        if not row:return
        rid=row['request_id'];claim=http_json(a.broker,f'/api/v3/saas-broker/requests/{rid}/claim','POST',{},key)
        secret={'request_id':rid,'response_token':claim['response_token'],'claim_generation':claim['claim_generation'],'claim_expires_at':claim.get('claim_expires_at'),'question':claim['question'],'question_digest':claim['question_digest']}
        atomic_json(claims/(rid+'.json'),secret)
        work={'schema':'lion.firefox-mediator-work/v2','request_id':rid,'question':claim['question'],'question_digest':claim['question_digest'],'claim_generation':claim['claim_generation'],'mission_id':row.get('mission_id'),'thread_id':row.get('thread_id'),'scope_type':row.get('scope_type'),'scope_id':row.get('scope_id'),'transport':FIREFOX_TRANSPORT,'thread_policy':'ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER','authority_effect':'NONE'}
        atomic_json(inbox/(rid+'.json'),work,0o644)
    last_hb=0.0
    while True:
        try:
            if time.time()-last_hb>=10:heartbeat();last_hb=time.time()
            finish_answers();recover_claims();claim_new()
            atomic_json(state/'relay-status.json',{'status':'READY','observed_at':time.time(),'broker':a.broker,'authority_effect':'NONE'},0o644)
        except Exception as exc:
            atomic_json(state/'relay-status.json',{'status':'DEGRADED','observed_at':time.time(),'error':type(exc).__name__+':'+str(exc)[:500],'authority_effect':'NONE'},0o644)
        if a.once:break
        time.sleep(max(0.1,a.interval))
if __name__=='__main__':main()
