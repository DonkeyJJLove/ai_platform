#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,re,subprocess,sys,threading,time,urllib.parse,urllib.request,urllib.error,uuid
from contextvars import ContextVar
from datetime import datetime,timezone
from pathlib import Path
from cyber_lion.app_coordination.local_intelligence_gateway import Gateway,serve_gateway
from cyber_lion.app_coordination.thread_store import ThreadStore
from cyber_lion.app_coordination.web_research_broker import WebEvidence
from cyber_lion.contracts.phase_execution_contract import compile_panel_phase_contracts, preflight_execution_contracts, PhaseExecutionContractError
from cyber_lion.mission_control import global_scheduler as mission_scheduler

DRONE_ROLES={
'MAT01':'Repository/Git read','MAT02':'Local source read','MAT03':'Local clone federation',
'MAT04':'GitHub/currentness','MAT05':'Public web search','MAT06':'Public web fetch',
'MAT07':'Web evidence validation','MAT08':'Receipt validator A','MAT09':'Local model health',
'MAT10':'Receipt validator B','MAT11':'Receipt coordinator','MAT12':'Reconciler'}

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def digest(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp-'+uuid.uuid4().hex[:8]);tmp.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True),encoding='utf-8');os.replace(tmp,path)
def _json_request(url,body=None,timeout=20):
    data=None;headers={'Accept':'application/json','User-Agent':'LION-Local-Intelligence/1'};method='GET'
    if body is not None:data=json.dumps(body,ensure_ascii=False).encode();headers['Content-Type']='application/json';method='POST'
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

class LpclControlBridge:
    """Loopback-only LPCL intake/control bridge. It never grants model authority."""
    KEY_RE=re.compile(r'^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$')
    MID_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
    ALLOWED_PROTOCOLS=('LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL','LIFECYCLE','HISTORY','LINEAGE','TRANSPORT','BROKER','MEDIATOR','THREAD')
    def __init__(self,broker,base='http://127.0.0.1:8766'):
        self.broker=broker;self.base=base.rstrip('/')
    def _get(self,path,timeout=8):
        req=urllib.request.Request(self.base+path,headers={'User-Agent':'LION-LPCL-PANEL/1'},method='GET')
        with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
    def _post(self,path,body,timeout=10):
        data=json.dumps(body,ensure_ascii=False).encode('utf-8');req=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json','User-Agent':'LION-LPCL-PANEL/1'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read(4096)).get('error','backend request rejected')
            except (ValueError,AttributeError):detail='backend request rejected'
            raise ValueError('Mission Control '+str(error.code)+': '+str(detail)[:600]) from error
    @classmethod
    def _parse_pairs(cls,text):
        lines=text.replace('\r\n','\n').replace('\r','\n').split('\n');out={};i=0
        while i<len(lines):
            m=cls.KEY_RE.match(lines[i].strip())
            if not m:i+=1;continue
            key,val=m.group(1),m.group(2).strip();i+=1
            if not val:
                buf=[]
                while i<len(lines):
                    s=lines[i].strip()
                    if cls.KEY_RE.match(s):break
                    if s and not s.startswith('#'):buf.append(s)
                    i+=1
                val=' '.join(buf).strip()
            out[key]=val
        return out
    def validate(self,text):
        if not isinstance(text,str) or not 20<=len(text)<=200000:raise ValueError('lpcl text')
        kv=self._parse_pairs(text)
        if not kv.get('MISSION_DESCRIPTION') and kv.get('MISSION_OBJECTIVE'):kv['MISSION_DESCRIPTION']=kv['MISSION_OBJECTIVE']
        if not kv.get('LOGICAL_DRONE_COUNT') and kv.get('LOGICAL_DRONES'):kv['LOGICAL_DRONE_COUNT']=kv['LOGICAL_DRONES']
        if not kv.get('MATERIAL_DRONE_COUNT') and kv.get('MATERIAL_FLEET_TARGET'):kv['MATERIAL_DRONE_COUNT']=kv['MATERIAL_FLEET_TARGET']
        required=('PROJECT','MODE','CONTROL_LANGUAGE','MISSION_ID','MISSION_TITLE','MISSION_OBJECTIVE','MISSION_DESCRIPTION','LOGICAL_DRONE_COUNT','MATERIAL_DRONE_COUNT','PROTOCOLS')
        missing=[k for k in required if not kv.get(k)]
        if missing:raise ValueError('LPCL_MISSING_REQUIRED:'+','.join(missing))
        if kv['PROJECT']!='LION_EVOLUSION' or kv['MODE']!='AUTONOMOUS_EXECUTE' or kv['CONTROL_LANGUAGE'] not in {'LPCL/1.1','LPCL/1.2'}:raise ValueError('lpcl envelope')
        mid=kv['MISSION_ID']
        if not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
        logical=int(kv['LOGICAL_DRONE_COUNT']);material=int(kv['MATERIAL_DRONE_COUNT'])
        if not 1<=logical<=512 or not 0<=material<=4096:raise ValueError('fleet cardinality')
        prot=[x for x in re.split(r'[,;\s]+',kv['PROTOCOLS'].strip()) if x]
        if not prot or any(x not in self.ALLOWED_PROTOCOLS for x in prot):raise ValueError('protocols')
        phases=[]
        for key in sorted(k for k in kv if re.fullmatch(r'PHASE_[0-9]{2}',k)):
            val=kv[key]
            if '|' in val:pid,title=[x.strip() for x in val.split('|',1)]
            else:
                pid=val.strip();title=' '.join(w.capitalize() for w in pid.split('_'))
            if not self.MID_RE.fullmatch(pid) or not title:raise ValueError('LPCL_PHASE_INVALID:'+key)
            phases.append({'id':pid,'title':title[:180]})
        if not phases:raise ValueError('no phases')
        try:
            contracts=compile_panel_phase_contracts(kv,mid,phases,kv['CONTROL_LANGUAGE'])
            try:
                registry_snapshot=self._get('/api/v3/capabilities/process-contracts')
                runtime_registry=registry_snapshot.get('capabilities') if isinstance(registry_snapshot,dict) else None
                if not isinstance(runtime_registry,dict):raise ValueError('runtime capability registry malformed')
                registry_state='LIVE_RUNTIME_REGISTRY'
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
                registry_snapshot={'schema':'UNAVAILABLE_LEGACY_MISSION_CONTROL','capabilities':{},'authority_effect':'NONE'}
                runtime_registry={};registry_state='UNAVAILABLE_FALLBACK_EMPTY'
            preflight=preflight_execution_contracts(contracts,runtime_registry)
        except PhaseExecutionContractError as exc:
            raise ValueError('LPCL_PHASE_EXECUTION_CONTRACT:'+str(exc)) from exc
        cur=self.broker.call('MAT04','github_branch',{'repository':'DonkeyJJLove/ai_platform','branch':'master'})['result']
        dg=hashlib.sha256(text.encode('utf-8')).hexdigest()
        spec={'mission_id':mid,'title':kv['MISSION_TITLE'][:180],'objective':kv['MISSION_OBJECTIVE'][:4000],'description':kv['MISSION_DESCRIPTION'][:8000],'lpcl_digest':dg,'lpcl_text':text,'source_head':cur['head'],'source_tree':cur['tree'],'logical_count':logical,'material_target':material,'phases':phases,'protocols':prot}
        return {'valid':True,'lpcl_digest':dg,'source_currentness':cur,'spec':spec,'execution_preflight':preflight.as_dict(),'capability_registry_state':registry_state,'capability_registry_digest':registry_snapshot.get('registry_digest') if isinstance(registry_snapshot,dict) else None,'phase_execution_contracts':[x.as_dict() for x in contracts],'parsed':{'run':kv.get('RUN'),'project':kv['PROJECT'],'mode':kv['MODE'],'control_language':kv['CONTROL_LANGUAGE'],'phase_count':len(phases)}}
    def __call__(self,op,args):
        args=args or {}
        if op=='recent':
            view=str(args.get('view') or 'operational').lower()
            if view not in {'operational','history','all'}:raise ValueError('mission view')
            return self._get('/api/v3/missions/recent?view='+view)
        if op=='capability_registry':return self._get('/api/v3/capabilities/process-contracts')
        if op in {'mission_delete_preview','mission_delete'}:
            mid=args.get('mission_id')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if op=='mission_delete_preview':return self._get('/api/v3/missions/'+mid+'/delete-preview')
            dg=args.get('spec_digest')
            if not isinstance(dg,str) or not re.fullmatch('[0-9a-f]{64}',dg):raise ValueError('spec_digest')
            return self._post('/api/v3/missions/'+mid+'/delete',{'spec_digest':dg})
        if op=='phase_action':
            if type(args) is not dict or set(args)!={'mission_id','phase_id','action','control_token'}:raise ValueError('phase action schema')
            mid=args['mission_id'];pid=args['phase_id'];action=args['action'];token=args['control_token']
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(pid,str) or not self.MID_RE.fullmatch(pid):raise ValueError('phase identity')
            if action not in {'PAUSE','STOP'} or not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):raise ValueError('phase containment action/token')
            return self._post('/api/v3/missions/'+mid+'/phase-actions',{'phase_id':pid,'action':action,'control_token':token})
        if op=='saas_request':
            if args.get('scope_type'):return self._post('/api/v3/saas-broker/requests',args)
            mid=args.get('mission_id');question=args.get('question')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(question,str) or not question.strip() or len(question)>8000:raise ValueError('saas request')
            return self._post('/api/v3/saas/request',{'mission_id':mid,'question':question})
        if op=='saas_status':return self._get('/api/v3/saas-broker/status')
        if op=='saas_request_status':
            rid=args.get('request_id')
            if not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('saas request id')
            return self._get('/api/v3/saas-broker/requests/'+rid)
        if op=='saas_request_cancel':
            rid=args.get('request_id')
            if set(args)!={'request_id'} or not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('saas request id')
            return self._post('/api/v3/saas/cancel',{'request_id':rid})
        if op=='mission_action':
            mid=args.get('mission_id');action=args.get('action');payload=args.get('payload') or {}
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if not isinstance(action,str):raise ValueError('action')
            return self._post('/api/v3/missions/'+mid+'/actions',{'action':action,**payload},timeout=240)
        if op=='dual_create':
            mid=args.get('mission_id');req=args.get('original_request');cur=args.get('currentness')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(req,str) or not isinstance(cur,dict):raise ValueError('dual create')
            return self._post('/api/v3/dual/create',{'mission_id':mid,'original_request':req,'currentness':cur})
        if op=='dual_link_saas':return self._post('/api/v3/dual/link-saas',{'request_id':args.get('request_id'),'saas_request_id':args.get('saas_request_id')})
        if op=='dual_response':return self._post('/api/v3/dual/response',{'request_id':args.get('request_id'),'provider':args.get('provider'),'response_text':args.get('response_text'),'transport':args.get('transport')})
        if op=='dual_result':
            rid=args.get('request_id')
            if not isinstance(rid,str) or not self.MID_RE.fullmatch(rid):raise ValueError('dual request id')
            return self._get('/api/v3/dual/'+rid)
        if op=='local_assignments':
            mid=args.get('mission_id');limit=int(args.get('limit',16));q=('?mission_id='+mid if isinstance(mid,str) and mid else '')+('&' if isinstance(mid,str) and mid else '?')+'limit='+str(limit);return self._get('/api/v3/local/assignments'+q)
        if op=='local_assignment_claim':return self._post('/api/v3/local/assignments/claim',{'assignment_id':args.get('assignment_id'),'material_drone_id':args.get('material_drone_id')})
        if op=='local_assignment_receipt':return self._post('/api/v3/local/assignments/receipt',{'assignment_id':args.get('assignment_id'),'material_drone_id':args.get('material_drone_id'),'lease_generation':args.get('lease_generation'),'status':args.get('status'),'result':args.get('result'),'effect_receipt_digest':args.get('effect_receipt_digest'),'authority_effect':'NONE'})
        if op=='process':
            mid=args.get('mission_id')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            return self._get('/api/v3/missions/'+mid+'/process')
        if op=='post_message':
            mid=args.get('mission_id');protocol=args.get('protocol');phase=args.get('phase');payload=args.get('payload');from_id=args.get('from_id') or 'LPCL_PANEL';to_id=args.get('to_id') or 'MISSION_CONTROL'
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid):raise ValueError('mission_id')
            if protocol not in self.ALLOWED_PROTOCOLS or not isinstance(payload,dict):raise ValueError('protocol message')
            return self._post('/api/v3/missions/'+mid+'/messages',{'protocol':protocol,'from_id':from_id,'to_id':to_id,'phase':phase,'payload':payload})
        if op=='validate_lpcl':return self.validate(args.get('lpcl_text'))
        if op=='register_lpcl':
            source=args.get('lpcl_text');v=self.validate(source);out=self._post('/api/v3/missions/register-lpcl',v['spec']);mission=out.get('mission') if isinstance(out,dict) else None
            if not isinstance(mission,dict):raise ValueError('REGISTERED_SOURCE_DRIFT:missing mission readback')
            backend_mid=mission.get('mission_id') or (mission.get('process') or {}).get('mission_id');backend_digest=mission.get('spec_digest') or (mission.get('process') or {}).get('lpcl_digest')
            if backend_mid!=v['spec']['mission_id'] or backend_digest!=v['lpcl_digest']:raise ValueError('REGISTERED_SOURCE_DRIFT')
            return {**out,'registration_confirmation':{'mission_id':backend_mid,'lpcl_digest':backend_digest,'source_length':len(source),'authority_effect':'NONE'}}
        if op=='activate_lpcl':
            mid=args.get('mission_id');dg=args.get('lpcl_digest')
            if not isinstance(mid,str) or not self.MID_RE.fullmatch(mid) or not isinstance(dg,str) or not re.fullmatch('[0-9a-f]{64}',dg):raise ValueError('activation')
            out=self._post('/api/v3/missions/'+mid+'/activate',{'lpcl_digest':dg,'activation_event':'EXPLICIT_UI_ACTIVATION'})
            if not isinstance(out,dict) or out.get('mission_id')!=mid:raise ValueError('ACTIVATION_SOURCE_DRIFT')
            return {**out,'activation_confirmation':{'mission_id':mid,'lpcl_digest':dg,'authority_effect':'EXPLICIT_USER_ACTIVATION'}}
        if op=='current_action':
            action=args.get('action');pod=args.get('pod_name')
            if action not in {'START','PAUSE','RESUME','VALIDATE','STOP','RESTART_ONE'}:raise ValueError('action')
            body={'action':action}
            if action=='RESTART_ONE':
                if not isinstance(pod,str) or len(pod)>180:raise ValueError('pod')
                body['pod_name']=pod
            return self._post('/api/v3/missions/current/actions',body,timeout=240)
        raise ValueError('control operation denied')

class OperatorControlBridge:
    """Bounded server-side proxy to the independent operator-control gateway."""
    def __init__(self,base,key_file,pairing_file=None):
        self.base=str(base).rstrip('/');self.key=Path(key_file).resolve().read_text(encoding='utf-8').strip();self.pairing_file=Path(pairing_file).resolve() if pairing_file else None
        if len(self.key)<64:raise ValueError('operator proxy key unavailable')
    @staticmethod
    def _read_operator_local_secret(path):
        if path is None or not Path(path).is_file():return None
        p=Path(path);raw=p.read_bytes()
        if p.suffix.lower()=='.dpapi':
            if os.name!='nt':raise ValueError('DPAPI pairing secret requires Windows')
            import ctypes
            from ctypes import wintypes
            class DATA_BLOB(ctypes.Structure):_fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_byte))]
            CryptUnprotectData=ctypes.windll.crypt32.CryptUnprotectData;LocalFree=ctypes.windll.kernel32.LocalFree
            src=(ctypes.c_byte*len(raw)).from_buffer_copy(raw);in_blob=DATA_BLOB(len(raw),src);out_blob=DATA_BLOB();desc=wintypes.LPWSTR()
            if not CryptUnprotectData(ctypes.byref(in_blob),ctypes.byref(desc),None,None,None,0,ctypes.byref(out_blob)):raise ValueError('DPAPI operator pairing decrypt failed')
            try:value=ctypes.string_at(out_blob.pbData,out_blob.cbData).decode('utf-8').strip()
            finally:LocalFree(out_blob.pbData)
            return value
        return raw.decode('utf-8').strip()
    def _request(self,path,body=None,timeout=8,session_token=None):
        data=None;headers={'Accept':'application/json','User-Agent':'LION-8780-Operator-Proxy/1','X-LION-Panel-Proxy-Key':self.key};method='GET'
        if session_token:headers['X-LION-Operator-Session']=session_token
        if body is not None:data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();headers['Content-Type']='application/json';method='POST'
        req=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:return json.load(res)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read(4096)).get('error','operator gateway rejected')
            except Exception:detail='operator gateway rejected'
            raise ValueError('Operator Control '+str(error.code)+': '+str(detail)[:600]) from error
    def __call__(self,op,args):
        args=args or {}
        if op=='pair':
            code=args.get('pairing_code') or self._read_operator_local_secret(self.pairing_file)
            if not code:raise ValueError('operator pairing code required')
            return self._request('/v1/session/pair',{'pairing_code':code},10)
        if op=='session':return self._request('/v1/session',session_token=args.get('session_token'))
        if op=='unpair':return self._request('/v1/session/revoke',{},10,session_token=args.get('session_token'))
        if op=='state':return self._request('/v1/state?'+urllib.parse.urlencode({'mission_id':args.get('mission_id')}),session_token=args.get('session_token'))
        if op=='participants':return self._request('/v1/participants',session_token=args.get('session_token'))
        if op=='events':return self._request('/v1/events?'+urllib.parse.urlencode({'mission_id':args.get('mission_id'),'after':int(args.get('after',0)),'limit':int(args.get('limit',200))}),session_token=args.get('session_token'))
        if op=='command':return self._request('/v1/commands', {k:v for k,v in args.items() if k!='session_token'},15,session_token=args.get('session_token'))
        if op=='command_status':return self._request('/v1/commands/'+urllib.parse.quote(str(args.get('command_id')),safe=''),session_token=args.get('session_token'))
        if op=='ack':return self._request('/v1/events/ack',{k:v for k,v in args.items() if k!='session_token'},session_token=args.get('session_token'))
        raise ValueError('operator operation denied')

class MaterialDroneBroker:
    def __init__(self,runtime_dir):self.root=Path(runtime_dir).resolve();self.local=threading.local()
    def begin(self):self.local.receipts=[]
    def _remember(self,r):
        if not hasattr(self.local,'receipts'):self.local.receipts=[]
        self.local.receipts.append({k:r.get(k) for k in ('task_id','drone_id','runtime_identity','role','status','receipt_digest','authority_effect')})
    def receipts(self):return list(getattr(self.local,'receipts',[]))
    def fleet_state(self):
        rows=[];now=datetime.now(timezone.utc)
        for drone,role in DRONE_ROLES.items():
            p=self.root/'health'/f'{drone}.json'
            try:h=json.loads(p.read_text(encoding='utf-8'));stamp=h.get('observed_at') or h.get('started_at');age=(now-datetime.fromisoformat(stamp)).total_seconds();h['heartbeat_age_seconds']=round(age,3);h['live']=h.get('status')=='READY' and age<3;rows.append(h)
            except Exception:rows.append({'drone_id':drone,'role':role,'status':'UNKNOWN','live':False,'authority_effect':'NONE'})
        return {'requested':12,'healthy':sum(1 for x in rows if x.get('live')),'rows':rows,'authority_effect':'NONE'}
    def _intrinsic(self,r):
        if type(r) is not dict or r.get('authority_effect')!='NONE':raise ValueError('material receipt authority')
        rd=r.get('receipt_digest');payload={k:r[k] for k in r if k!='receipt_digest'}
        if not isinstance(rd,str) or digest(payload)!=rd or digest(r.get('result'))!=r.get('result_digest'):raise ValueError('material receipt digest')
        return r
    @staticmethod
    def _read_json_transient(path,deadline):
        path=Path(path);last=None
        while time.time()<deadline:
            try:return json.loads(path.read_text(encoding='utf-8'))
            except (PermissionError,OSError,json.JSONDecodeError) as e:last=e;time.sleep(.02)
        if last:raise last
        raise TimeoutError(f'material json read timeout:{path.name}')
    def _call_raw(self,drone,operation,args,timeout=30):
        if drone not in DRONE_ROLES:raise ValueError('unknown material drone')
        task_id=uuid.uuid4().hex;task={'task_id':task_id,'drone_id':drone,'operation':operation,'args':args,'created_at':time.time_ns()};out=self.root/'outbox'/drone/f'{task_id}.json';atomic_json(self.root/'inbox'/drone/f'{task_id}.json',task);end=time.time()+timeout
        while time.time()<end:
            if out.exists():
                try:r=self._intrinsic(self._read_json_transient(out,min(end,time.time()+1.0)));hp=self.root/'health'/f'{drone}.json';h=self._read_json_transient(hp,min(end,time.time()+1.0))
                except (PermissionError,OSError,json.JSONDecodeError):time.sleep(.04);continue
                if r.get('runtime_identity')!=h.get('runtime_identity'):raise ValueError('material runtime identity drift')
                try:out.unlink()
                except OSError:pass
                self._remember(r);return r
            time.sleep(.04)
        raise TimeoutError(f'material drone timeout:{drone}')
    def call(self,drone,operation,args,timeout=30,validate=True):
        r=self._call_raw(drone,operation,args,timeout)
        if r.get('status')!='PASS':raise ValueError(f"material drone denied:{r.get('result')}")
        if validate and drone not in {'MAT08','MAT10'}:
            for v in ('MAT08','MAT10'):
                vr=self._call_raw(v,'validate_receipt',{'receipt':r},10)
                if vr.get('status')!='PASS' or not vr.get('result',{}).get('valid'):raise ValueError('material receipt validation failed')
        return r
    def aggregate(self):
        ds=[x.get('receipt_digest') for x in self.receipts() if isinstance(x.get('receipt_digest'),str)]
        if not ds:return None
        c=self.call('MAT11','coordinate',{'receipt_digests':ds},validate=True);all_ds=[x.get('receipt_digest') for x in self.receipts() if isinstance(x.get('receipt_digest'),str)];f=self.call('MAT12','reconcile',{'receipt_digests':all_ds},validate=True);return {'coordinator':c['result'],'reconciler':f['result']}

def providers(broker,model):
    def cur(kind,args):
        if kind=='github_branch':r=broker.call('MAT04','github_branch',{'repository':args['repository'],'branch':args['branch']});x=r['result'];return {'head':x['head'],'tree':x['tree']}
        if kind=='local_model':return broker.call('MAT09','model_health',{})['result']
        raise ValueError('provider kind denied')
    def gitprov(op,args):
        if op not in {'head_tree','status'}:raise ValueError('git op denied')
        return broker.call('MAT01',op,{})['result']
    def content(op,args):
        if op not in {'read_file','search'}:raise ValueError('content op denied')
        return broker.call('MAT02',op,args)['result']
    def source(op,args):
        if op=='local_clones':return broker.call('MAT03','local_clones',{})['result']
        if op=='federation':return broker.call('MAT04','federation',{})['result']
        if op=='branch_state':return broker.call('MAT04','github_branch',{'repository':args['repository'],'branch':args['branch']})['result']
        raise ValueError('source op denied')
    def mission(op,args):
        if op=='recent':return broker.call('MAT04','mission_recent',{})['result']
        if op=='process':return broker.call('MAT04','mission_process',{'mission_id':args['mission_id']})['result']
        raise ValueError('mission op denied')
    class MaterialWeb:
        def search(self,query,limit=5):
            r=broker.call('MAT05','web_search',{'query':query,'limit':limit});rows=r['result']
            for row in rows:broker.call('MAT07','validate_web',{'url':row['url']})
            return tuple(rows)
        def fetch(self,url):broker.call('MAT07','validate_web',{'url':url});d=broker.call('MAT06','web_fetch',{'url':url})['result'];return WebEvidence(**d)
    def modelprov(messages,max_tokens=384):broker.call('MAT09','model_health',{});d=_json_request(model.rstrip('/')+'/v1/chat/completions',body={'messages':messages,'max_tokens':max_tokens,'temperature':0.1,'stream':False},timeout=90);return d['choices'][0]['message']['content']
    return cur,gitprov,content,source,mission,MaterialWeb(),modelprov


def local_assignment_worker_once(control,modelprov,*,material_drone_id='MD025'):
    pending=control('local_assignments',{'limit':16}).get('assignments') or []
    for row in pending:
        if row.get('material_drone_id')!=material_drone_id:continue
        aid=row.get('assignment_id')
        try:claimed=control('local_assignment_claim',{'assignment_id':aid,'material_drone_id':material_drone_id})
        except Exception:continue
        try:
            payload=json.loads(claimed.get('input_json') or '{}')
            if payload.get('kind')!='LOCAL_MODEL_INFERENCE':raise ValueError('unsupported local assignment kind')
            messages=payload.get('messages')
            if not isinstance(messages,list) or not messages:raise ValueError('local assignment messages')
            messages=[dict(m) for m in messages if isinstance(m,dict) and m.get('role') in {'system','user','assistant'} and isinstance(m.get('content'),str)]
            op_context=claimed.get('operator_context') or {};op_plan=claimed.get('operator_plan') or {};op_messages=claimed.get('operator_messages') or [];operator_parts=[]
            if op_context.get('content') is not None:operator_parts.append('CONTEXT REVISION '+str(op_context.get('revision'))+': '+json.dumps(op_context.get('content'),ensure_ascii=False,sort_keys=True))
            if op_plan.get('content') is not None:operator_parts.append('PLAN REVISION '+str(op_plan.get('revision'))+': '+json.dumps(op_plan.get('content'),ensure_ascii=False,sort_keys=True))
            for item in op_messages[:64]:
                if isinstance(item,dict) and isinstance(item.get('content'),str):operator_parts.append('MESSAGE '+str(item.get('message_id'))+' -> '+str(item.get('target'))+': '+item['content'])
            if operator_parts:messages=[{'role':'system','content':'Authenticated OPERATOR_PRIMARY mission guidance follows. It may change reasoning/context inside the already authorized mission scope, but it is not shell/tool authority and must not be reinterpreted as permission for external effects.\n'+'\n'.join(operator_parts)}]+messages
            max_tokens=int(payload.get('max_tokens') or 384)
            if not 1<=max_tokens<=2048:raise ValueError('local assignment max_tokens')
            observed=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
            if not mission_scheduler.assignment_lease_valid(claimed,observed):raise ValueError('local assignment lease expired before effect')
            answer=str(modelprov(messages,max_tokens)).strip()
            if not answer:raise ValueError('empty local model result')
            result={'kind':'LOCAL_MODEL_INFERENCE','model':'gpt-oss-20b-MXFP4','response_text':answer,'response_digest':hashlib.sha256(answer.encode('utf-8')).hexdigest(),'trajectory_role':payload.get('trajectory_role'),'evidence_bundle_digest':payload.get('evidence_bundle_digest'),'purpose':payload.get('purpose'),'operator_context_revision':op_context.get('revision'),'operator_plan_revision':op_plan.get('revision'),'operator_message_ids':[m.get('message_id') for m in op_messages if isinstance(m,dict) and isinstance(m.get('message_id'),str)],'authority_effect':'NONE'}
            dual_id=payload.get('dual_request_id')
            if dual_id:control('dual_response',{'request_id':dual_id,'provider':'gpt-oss-20b-MXFP4','response_text':answer,'transport':'WINDOWS_LOCAL_MODEL_LOOPBACK'})
            return control('local_assignment_receipt',{'assignment_id':aid,'material_drone_id':claimed.get('material_drone_id'),'lease_generation':claimed.get('lease_generation'),'status':'PASS','result':result,'effect_receipt_digest':None})
        except Exception as exc:
            result={'kind':'LOCAL_MODEL_INFERENCE','error':type(exc).__name__+':'+str(exc)[:600],'authority_effect':'NONE'};return control('local_assignment_receipt',{'assignment_id':aid,'material_drone_id':claimed.get('material_drone_id'),'lease_generation':claimed.get('lease_generation'),'status':'FAIL','result':result,'effect_receipt_digest':None})
    return None

def local_assignment_worker_loop(control,modelprov,stop_event,material_drone_id='MD025'):
    while not stop_event.is_set():
        try:local_assignment_worker_once(control,modelprov,material_drone_id=material_drone_id)
        except Exception:pass
        stop_event.wait(1)

RUNTIME_STARTED_AT=datetime.now(timezone.utc).isoformat();RECON_CAPABILITY_CLASS='CONTROL_PLANE_RECONNAISSANCE';RECON_WINDOWS_SCHEMA='lion.control-plane-windows-observation/v1'
def _recon_sha(path):
    try:
        h=hashlib.sha256()
        with Path(path).open('rb') as f:
            while True:
                b=f.read(1024*1024)
                if not b:break
                h.update(b)
        return h.hexdigest()
    except OSError:return None
RUNTIME_LOADED_SOURCE_SHA=_recon_sha(Path(__file__).resolve());GATEWAY_LOADED_SOURCE_SHA=_recon_sha(Path(sys.modules[Gateway.__module__].__file__).resolve())
def _recon_observation_fingerprint(*,phase,runtime_loaded_sha,gateway_loaded_sha,features,local,github,thread_identity):
    feature_digest=hashlib.sha256(json.dumps(features,sort_keys=True,separators=(',',':')).encode()).hexdigest();value={'phase':phase,'runtime_loaded':runtime_loaded_sha,'gateway_loaded':gateway_loaded_sha,'feature_digest':feature_digest,'local':local,'github':github,'thread':thread_identity};return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest(),feature_digest

def control_plane_recon_observer_once(control,broker,gitprov,thread_db,repo,model_url):
    recent=control('recent',{});mid=recent.get('focus_mission_id')
    if not mid:return None
    snap=control('process',{'mission_id':mid});phase=(snap.get('process') or {}).get('current_phase')
    if not phase:return None
    bindings=snap.get('phase_capability_bindings') or [];bound=next((x for x in bindings if x.get('phase_id')==phase and x.get('capability_class')==RECON_CAPABILITY_CLASS and x.get('state')=='BOUND'),None)
    if not bound:return None
    try:
        local=gitprov('head_tree',{});local_state={'head':local.get('head'),'tree':local.get('tree'),'status':'OK'}
    except Exception as exc:local_state={'status':'UNKNOWN','error':type(exc).__name__}
    try:
        remote=broker.call('MAT04','github_branch',{'repository':'DonkeyJJLove/ai_platform','branch':'master'})['result'];github={'head':remote.get('head'),'tree':remote.get('tree'),'status':'OK'}
    except Exception as exc:github={'status':'UNKNOWN','error':type(exc).__name__}
    try:thread_identity={'path':str(Path(thread_db).resolve()),'sha256':_recon_sha(Path(thread_db).resolve()),'exists':Path(thread_db).resolve().is_file()}
    except Exception:thread_identity={'exists':False,'sha256':None}
    features={'runtime_started_at':RUNTIME_STARTED_AT,'runtime_loaded_source_sha256':RUNTIME_LOADED_SOURCE_SHA,'gateway_loaded_source_sha256':GATEWAY_LOADED_SOURCE_SHA,'repo_path':str(Path(repo).resolve()),'model_url':model_url,'operator_control_bridge':True};fp,feature_digest=_recon_observation_fingerprint(phase=phase,runtime_loaded_sha=RUNTIME_LOADED_SOURCE_SHA,gateway_loaded_sha=GATEWAY_LOADED_SOURCE_SHA,features=features,local=local_state,github=github,thread_identity=thread_identity)
    payload={'schema':RECON_WINDOWS_SCHEMA,'event':'WINDOWS_CONTROL_PLANE_OBSERVATION','observation_fingerprint':fp,'feature_digest':feature_digest,'runtime':{'started_at':RUNTIME_STARTED_AT,'runtime_loaded_source_sha256':RUNTIME_LOADED_SOURCE_SHA,'gateway_loaded_source_sha256':GATEWAY_LOADED_SOURCE_SHA},'local_repository':local_state,'github_master':github,'thread_store':thread_identity,'authority_effect':'NONE'}
    return control('post_message',{'mission_id':mid,'protocol':'CURRENTNESS','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':payload})

def control_plane_recon_observer_loop(control,broker,gitprov,thread_db,repo,model_url,stop_event):
    while not stop_event.is_set():
        try:control_plane_recon_observer_once(control,broker,gitprov,thread_db,repo,model_url)
        except Exception:pass
        stop_event.wait(2)

def local_canary_loop(control,modelprov,stop_event,panel_port,model_url):
    while not stop_event.is_set():
        try:
            recent=control('recent',{});mid=recent.get('focus_mission_id')
            if mid:
                snap=control('process',{'mission_id':mid});phase=(snap.get('process') or {}).get('current_phase')
                if phase=='LIVE_AUTONOMY_CANARY':
                    exists=any(msg.get('protocol')=='EVIDENCE' and msg.get('from_id')=='LPCL_PANEL' and msg.get('phase')==phase and (msg.get('payload') or {}).get('event')=='LOCAL_MODEL_CANARY_PASS' for msg in snap.get('protocol_messages') or [])
                    if not exists:
                        prompt='LOCAL self-hosting inference canary: return any concise non-empty response.';answer=str(modelprov([{'role':'system','content':'You are the proposal-only local LION cognitive executor. Return a concise response.'},{'role':'user','content':prompt}],64)).strip();rd=hashlib.sha256(answer.encode()).hexdigest();pd=hashlib.sha256(prompt.encode()).hexdigest();event='LOCAL_MODEL_CANARY_PASS' if answer else 'LOCAL_MODEL_CANARY_EMPTY';control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':{'event':event,'model':'gpt-oss-20b-MXFP4','prompt_digest':pd,'response_digest':rd,'response_bytes':len(answer.encode()),'transport':'WINDOWS_LOCAL_MODEL_LOOPBACK','authority_effect':'NONE'}})
                elif phase=='READY_FOR_SYSTEM_ACCEPTANCE_TESTS':
                    exists=any(msg.get('protocol')=='EVIDENCE' and msg.get('from_id')=='LPCL_PANEL' and msg.get('phase')==phase and (msg.get('payload') or {}).get('event')=='WINDOWS_CONTROL_SURFACE_READBACK' for msg in snap.get('protocol_messages') or [])
                    if not exists:
                        panel=_json_request(f'http://127.0.0.1:{panel_port}/health',timeout=3);models=_json_request(model_url.rstrip('/')+'/v1/models',timeout=5);model_count=len(models.get('data') or []) if isinstance(models,dict) else 0;control('post_message',{'mission_id':mid,'protocol':'EVIDENCE','from_id':'LPCL_PANEL','to_id':'MISSION_EXECUTION_DRIVER','phase':phase,'payload':{'event':'WINDOWS_CONTROL_SURFACE_READBACK','panel_http':200 if panel.get('status')=='ok' else 0,'panel_authority_effect':panel.get('authority_effect'),'model_http':200,'model_count':model_count,'model_id':'gpt-oss-20b-MXFP4','authority_effect':'NONE'}})
        except Exception:pass
        stop_event.wait(5)

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--material-runtime-dir',required=True);p.add_argument('--rag');p.add_argument('--rag-sha');p.add_argument('--release');p.add_argument('--model',default='http://127.0.0.1:8772');p.add_argument('--model-sha',required=True);p.add_argument('--mission-control-url',default='http://127.0.0.1:8766');p.add_argument('--operator-control-url',default='http://127.0.0.1:8767');p.add_argument('--operator-panel-key-file');p.add_argument('--operator-pairing-file');p.add_argument('--port',type=int,default=8780);p.add_argument('--thread-db');a=p.parse_args()
    if bool(a.rag)!=bool(a.rag_sha) or bool(a.rag)!=bool(a.release):raise SystemExit('rag, rag-sha and release must be supplied together')
    b=MaterialDroneBroker(a.material_runtime_dir);cur,gp,cp,sp,mission,web,mp=providers(b,a.model);thread_db=Path(a.thread_db).resolve() if a.thread_db else Path(a.material_runtime_dir).resolve().parent/'threads'/'lion-local-model.db';threads=ThreadStore(thread_db);control=LpclControlBridge(b,a.mission_control_url);operator=None
    if a.operator_panel_key_file:operator=OperatorControlBridge(a.operator_control_url,a.operator_panel_key_file,a.operator_pairing_file)
    g=Gateway(a.repo,a.rag,a.rag_sha,a.release,a.model,a.model_sha,mp,cur,gp,web=web,content_provider=cp,source_provider=sp,mission_provider=mission,control_provider=control,material_begin=b.begin,material_receipts=b.receipts,material_state=b.fleet_state,material_reconcile=b.aggregate,thread_provider=threads,operator_provider=operator)
    canary_stop=threading.Event();threading.Thread(target=local_canary_loop,args=(control,mp,canary_stop,a.port,a.model),daemon=True).start()
    for material_id in ('MD025','MD026','MD027'):threading.Thread(target=local_assignment_worker_loop,args=(control,mp,canary_stop,material_id),daemon=True,name='local-model-'+material_id).start()
    threading.Thread(target=control_plane_recon_observer_loop,args=(control,b,gp,thread_db,a.repo,a.model,canary_stop),daemon=True,name='control-plane-recon-observer').start()
    from cyber_lion.app_coordination.saas_thread_delivery import delivery_loop
    threading.Thread(target=delivery_loop,args=(threads,control,canary_stop),daemon=True,name='saas-thread-delivery').start()
    try:serve_gateway(g,a.port)
    finally:canary_stop.set()
if __name__=='__main__':main()
