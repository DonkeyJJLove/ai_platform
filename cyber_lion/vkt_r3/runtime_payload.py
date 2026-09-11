from __future__ import annotations

DRONE_SOURCE = r'''import hashlib,json,os,time,urllib.parse,urllib.request
fleet=os.environ['FLEET']
pod=os.environ.get('POD_NAME','?')
pod_uid=os.environ.get('POD_UID','')
drone=pod.rsplit('-',1)[-1] if '-' in pod else pod
router=os.environ.get('VKT_ROUTER','http://vkt-fleet-router:8080')
seq=0
messages_sent=0
messages_received=0
current_case=None
current_phase='WAIT_FOR_FLEET'

def post(path,obj,timeout=2):
    body=json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
    req=urllib.request.Request(router+path,data=body,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        raw=r.read()
        return json.loads(raw) if raw else {}

def get(path,timeout=2):
    with urllib.request.urlopen(router+path,timeout=timeout) as r:
        return json.loads(r.read())

while True:
    seq+=1
    hb={'fleet':fleet,'drone_id':drone,'pod_name':pod,'pod_uid':pod_uid,'heartbeat_seq':seq,'messages_sent':messages_sent,'messages_received':messages_received,'current_case':current_case,'current_phase':current_phase,'vendor_requests':0,'t':time.time()}
    try:
        post('/heartbeat',hb)
        task=get('/task?pod_uid='+urllib.parse.quote(pod_uid,safe=''))
        messages_received+=1
        current_case=task.get('case_id')
        current_phase=task.get('phase','IDLE')
        if task.get('action')=='SEND_MESSAGE':
            payload={'case_id':current_case,'fleet':fleet,'drone_id':drone,'phase':current_phase,'synthetic_local_execution':True,'vendor_requests':0}
            payload_digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            message_id=hashlib.sha256((pod_uid+'|'+current_phase+'|'+str(current_case)+'|1').encode()).hexdigest()
            msg={'message_id':message_id,'correlation_id':task['correlation_id'],'parent_message_id':task.get('parent_message_id'),'timestamp':time.time(),'from_fleet':fleet,'from_drone_id':drone,'from_pod_uid':pod_uid,'to_fleet':task.get('to_fleet','ROUTER'),'case_id':current_case,'phase':current_phase,'type':task['message_type'],'payload_digest':payload_digest,'evidence_class':'LOCAL_SYNTHETIC','vendor_requests':0}
            ack=post('/message',msg)
            messages_received+=1
            if ack.get('ack') is True:
                messages_sent+=1
    except Exception:
        pass
    time.sleep(1)
'''

ROUTER_SOURCE = r'''from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib,json,threading,time,urllib.parse

EXPECTED={'TIGER':128,'SPECTRA':128,'LION':128}
CASES=[f'VKT-R3-CASE-{i:02d}' for i in range(1,37)]
PHASES=[
 ('TIGER_RELATION_ANALYSIS','TIGER','TIGER_RELATION_SCAN','SPECTRA'),
 ('SPECTRA_FALSIFIER','SPECTRA','SPECTRA_FALSIFIER_RESULT','LION'),
 ('LION_LOCAL_EXECUTION','LION','LION_EXECUTION_RESULT','LION'),
 ('LION_RECEIPT','LION','LION_RECEIPT_WRITTEN','SPECTRA'),
 ('SPECTRA_PROOF_UPDATE','SPECTRA','SPECTRA_PROOF_UPDATE','TIGER'),
 ('TIGER_ADJACENCY','TIGER','TIGER_ADJACENCY_UPDATE','ROUTER'),
]
lock=threading.RLock()
drones={}
messages={}
message_order=[]
events=[]
assignments={}
participants={p[0]:set() for p in PHASES}
case_state={c:{'case_id':c,'status':'WAITING','last_message_id':None,'messages':0} for c in CASES}
mission={'started':False,'completed':False,'phase':'WAIT_FOR_FLEET','phase_index':-1,'started_at':None,'completed_at':None,'duplicates':0,'orphans':0,'acks':0,'vendor_requests':0}

def event(t,**kw):
    row={'event_id':hashlib.sha256((t+'|'+str(time.time_ns())+'|'+str(len(events))).encode()).hexdigest(),'timestamp':time.time(),'event_type':t,**kw}
    events.append(row)
    if len(events)>10000: del events[:1000]

def fresh(now=None):
    now=time.time() if now is None else now
    return {u:d for u,d in drones.items() if now-float(d.get('_seen',0))<=10 and d.get('vendor_requests',0)==0}

def fleet_counts(rows):
    out={f:0 for f in EXPECTED}
    for d in rows.values():
        f=d.get('fleet')
        if f in out: out[f]+=1
    return out

def maybe_start():
    if mission['started']: return
    rows=fresh(); counts=fleet_counts(rows)
    if counts!=EXPECTED: return
    for fleet in EXPECTED:
        members=sorted((d for d in rows.values() if d.get('fleet')==fleet),key=lambda d:(int(d.get('drone_id')) if str(d.get('drone_id','')).isdigit() else 10**9,str(d.get('pod_uid'))))
        if len(members)!=128: return
        for i,d in enumerate(members): assignments[d['pod_uid']]={'fleet':fleet,'case_id':CASES[i%len(CASES)]}
    mission.update({'started':True,'phase_index':0,'phase':PHASES[0][0],'started_at':time.time()})
    for c in CASES: case_state[c]['status']='ACTIVE'
    event('TEST_STARTED',phase=mission['phase'],summary='384 fresh drones registered; semantic run started')

def advance_if_ready():
    if not mission['started'] or mission['completed']: return
    phase=mission['phase']
    if len(participants[phase])<128: return
    event('PHASE_COMPLETED',phase=phase,participants=len(participants[phase]))
    idx=mission['phase_index']+1
    if idx>=len(PHASES):
        mission.update({'completed':True,'phase':'COMPLETE','phase_index':idx,'completed_at':time.time()})
        for c in CASES: case_state[c]['status']='PROVEN'
        event('TEST_COMPLETED',phase='COMPLETE',summary='All six distributed semantic phases completed')
        return
    mission['phase_index']=idx; mission['phase']=PHASES[idx][0]
    event('PHASE_CHANGED',phase=mission['phase'])

def task_for(uid):
    maybe_start()
    a=assignments.get(uid)
    if not a or not mission['started'] or mission['completed']:
        return {'action':'IDLE','phase':mission['phase'],'case_id':a.get('case_id') if a else None}
    phase,role,mtype,to_fleet=PHASES[mission['phase_index']]
    if a['fleet']!=role or uid in participants[phase]:
        return {'action':'IDLE','phase':phase,'case_id':a['case_id']}
    c=a['case_id']
    return {'action':'SEND_MESSAGE','phase':phase,'case_id':c,'message_type':mtype,'to_fleet':to_fleet,'correlation_id':hashlib.sha256(c.encode()).hexdigest(),'parent_message_id':case_state[c]['last_message_id']}

def accept_message(x):
    required={'message_id','correlation_id','parent_message_id','timestamp','from_fleet','from_drone_id','from_pod_uid','to_fleet','case_id','phase','type','payload_digest','evidence_class','vendor_requests'}
    if set(x)!=required: return False,'FIELD_SET'
    if x.get('vendor_requests')!=0: return False,'VENDOR_REQUEST'
    uid=x.get('from_pod_uid'); d=drones.get(uid); a=assignments.get(uid)
    if not d or not a: return False,'UNKNOWN_DRONE'
    if d.get('fleet')!=x.get('from_fleet') or a.get('case_id')!=x.get('case_id'): return False,'IDENTITY_OR_CASE'
    if not mission['started'] or mission['completed']: return False,'MISSION_STATE'
    phase,role,mtype,to_fleet=PHASES[mission['phase_index']]
    if x.get('phase')!=phase or x.get('from_fleet')!=role or x.get('type')!=mtype: return False,'PHASE_ROLE_TYPE'
    mid=x['message_id']
    if mid in messages:
        if messages[mid]==x: return True,'REPLAY_ACK'
        mission['duplicates']+=1; return False,'DUPLICATE_ID_COLLISION'
    parent=x.get('parent_message_id')
    if parent is not None and parent not in messages:
        mission['orphans']+=1; return False,'ORPHAN_PARENT'
    messages[mid]=x; message_order.append(mid); participants[phase].add(uid); mission['acks']+=1
    cs=case_state[x['case_id']]; cs['last_message_id']=mid; cs['messages']+=1
    event(x['type'],fleet=x['from_fleet'],pod_uid=uid,case_id=x['case_id'],phase=phase,message_id=mid,correlation_id=x['correlation_id'],evidence_digest=x['payload_digest'])
    advance_if_ready(); return True,'ACK'

def snapshot():
    rows=fresh(); counts=fleet_counts(rows)
    seen={c for c,s in case_state.items() if s['messages']>0}
    total=len(messages); acks=mission['acks']
    return {'sample_utc':time.time(),'heartbeat_count':len(drones),'fresh_count':len(rows),'fresh_by_fleet':counts,'mission':dict(mission),'messages_total':total,'ack_count':acks,'ack_rate':1.0 if total==0 else acks/total,'duplicates':mission['duplicates'],'orphans':mission['orphans'],'cases_total':36,'cases_seen':len(seen),'cases_proven':sum(1 for s in case_state.values() if s['status']=='PROVEN'),'case_state':list(case_state.values()),'participants':{k:len(v) for k,v in participants.items()},'vendor_requests':0,'events':events[-500:],'messages':[messages[m] for m in message_order[-1000:]]}

class H(BaseHTTPRequestHandler):
    def sendj(self,code,obj):
        b=json.dumps(obj,sort_keys=True,separators=(',',':')).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n=int(self.headers.get('Content-Length','0'))
        if n<0 or n>65536: self.sendj(413,{'ok':False}); return
        try: x=json.loads(self.rfile.read(n))
        except Exception: self.sendj(400,{'ok':False,'error':'JSON'}); return
        with lock:
            if self.path=='/heartbeat':
                if x.get('vendor_requests')!=0 or x.get('fleet') not in EXPECTED or not x.get('pod_uid'): self.sendj(400,{'ok':False}); return
                y=dict(x); y['_seen']=time.time(); drones[x['pod_uid']]=y; maybe_start(); self.sendj(200,{'ok':True,'registered':True,'mission_phase':mission['phase']}); return
            if self.path=='/message':
                ok,reason=accept_message(x); self.sendj(200 if ok else 409,{'ack':ok,'reason':reason,'mission_phase':mission['phase']}); return
        self.sendj(404,{'ok':False})
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); qs=urllib.parse.parse_qs(u.query)
        with lock:
            if u.path=='/state': self.sendj(200,snapshot()); return
            if u.path=='/mission': self.sendj(200,snapshot()); return
            if u.path=='/task': self.sendj(200,task_for((qs.get('pod_uid') or [''])[0])); return
        self.sendj(404,{'ok':False})
    def log_message(self,*a): pass
ThreadingHTTPServer(('0.0.0.0',8080),H).serve_forever()
'''

def runtime_sources() -> dict[str, str]:
    return {"drone.py": DRONE_SOURCE, "router.py": ROUTER_SOURCE}
