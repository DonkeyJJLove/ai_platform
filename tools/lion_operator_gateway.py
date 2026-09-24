#!/usr/bin/env python3
"""Loopback-only ingress for durable human operator intervention.

The gateway performs no model inference and offers no shell/URL/SQL surface.
It shares the Mission Control SQLite authority ledger but remains a separate
process so containment can survive loss of the main 8766 HTTP service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from cyber_lion.mission_control import global_scheduler, operator_control, operator_swarm_session

DEFAULT_DB = "/var/lib/sentinelx/uploads/lion-mission-control-v3/mission-control-v3.db"
DEFAULT_KEY = "/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-gateway.key"
DEFAULT_PROXY_KEY = "/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-sentinelx-proxy.key"
DEFAULT_PANEL_PROXY_KEY = "/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-panel-proxy.key"
DEFAULT_PAIRING_KEY = "/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-pairing.key"
DEFAULT_FLOOR = "/var/lib/sentinelx/uploads/lion-operator-control/operator-epoch-floors.json"


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_key(path: Path) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if len(key) < 64:
        raise RuntimeError("operator gateway key unavailable")
    return key


def atomic_json(path: Path, value: dict, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n");handle.flush();os.fsync(handle.fileno())
        os.chmod(name, mode);os.replace(name, path)
    finally:
        try:
            if os.path.exists(name):os.unlink(name)
        except OSError:pass


def read_json(path: Path, default):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value,dict) else default
    except (OSError,ValueError):return default


class Runtime:
    def __init__(self, db: Path, key_file: Path, proxy_key_file: Path, panel_proxy_key_file: Path, pairing_key_file: Path, floor_file: Path, mission_control_url: str, *, bootstrap_primary=False):
        self.db=db.resolve();self.key_file=key_file.resolve();self.proxy_key_file=proxy_key_file.resolve();self.panel_proxy_key_file=panel_proxy_key_file.resolve();self.pairing_key_file=pairing_key_file.resolve();self.floor_file=floor_file.resolve()
        self.key=load_key(self.key_file);self.proxy_key=load_key(self.proxy_key_file);self.panel_proxy_key=load_key(self.panel_proxy_key_file);self.pairing_key=load_key(self.pairing_key_file);self.mission_control_url=mission_control_url.rstrip('/');self.lock=threading.Lock();self.session_lock=threading.Lock();self.sessions={};self.pairing_challenges={}
        c=self.connect();operator_control.migrate(c,now);operator_swarm_session.migrate(c,now)
        participant=operator_control.participant_snapshot(c).get('participant')
        if participant is None:
            if not bootstrap_primary:
                c.close();raise RuntimeError('primary operator not provisioned; explicit bootstrap required')
            operator_control.ensure_primary_operator(c,now)
        if operator_control.participant_snapshot(c,operator_control.SENTINELX_PROXY_PRINCIPAL).get('participant') is None:
            if not bootstrap_primary:
                c.close();raise RuntimeError('SentinelX proxy not provisioned; explicit bootstrap required')
            operator_control.ensure_operator_proxy(c,now)
        if operator_control.participant_snapshot(c,operator_control.PANEL_PROXY_PRINCIPAL).get('participant') is None:
            if not bootstrap_primary:
                c.close();raise RuntimeError('panel proxy not provisioned; explicit bootstrap required')
            operator_control.ensure_panel_proxy(c,now)
        self.reconcile_epoch_floors(c);c.close()

    def connect(self):
        c=sqlite3.connect(self.db,timeout=2);c.row_factory=sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=1500')
        return c

    def _key_identity(self, supplied):
        if not isinstance(supplied,str):return None
        if len(supplied)==len(self.key) and secrets.compare_digest(supplied,self.key):return operator_control.PRIMARY_OPERATOR
        if len(supplied)==len(self.proxy_key) and secrets.compare_digest(supplied,self.proxy_key):return operator_control.SENTINELX_PROXY_PRINCIPAL
        if len(supplied)==len(self.panel_proxy_key) and secrets.compare_digest(supplied,self.panel_proxy_key):return operator_control.PANEL_PROXY_PRINCIPAL
        return None

    def issue_panel_pairing_challenge(self, supplied_key):
        if self._key_identity(supplied_key)!=operator_control.PANEL_PROXY_PRINCIPAL:raise PermissionError('panel transport authentication required')
        stamp=time.time();challenge_id=secrets.token_hex(16);code=secrets.token_hex(16);expires=stamp+60.0
        with self.session_lock:
            self.pairing_challenges={k:v for k,v in self.pairing_challenges.items() if v.get('expires',0)>stamp and v.get('attempts',0)>0}
            self.pairing_challenges[challenge_id]={'code_digest':hashlib.sha256(code.encode()).hexdigest(),'expires':expires,'attempts':3,'transport_principal':operator_control.PANEL_PROXY_PRINCIPAL}
        return {'challenge_id':challenge_id,'pairing_code':code,'expires_at_epoch':expires,'attempts_remaining':3,'authority_effect':'NONE'}

    def pair_panel(self, supplied_key, pairing_code, challenge_id=None):
        if self._key_identity(supplied_key)!=operator_control.PANEL_PROXY_PRINCIPAL:raise PermissionError('panel transport authentication required')
        if challenge_id is None:
            if not isinstance(pairing_code,str) or len(pairing_code)!=len(self.pairing_key) or not secrets.compare_digest(pairing_code,self.pairing_key):raise PermissionError('operator pairing code denied')
        else:
            if not isinstance(challenge_id,str) or len(challenge_id)!=32 or not isinstance(pairing_code,str):raise PermissionError('operator pairing challenge denied')
            stamp=time.time()
            with self.session_lock:
                challenge=self.pairing_challenges.get(challenge_id)
                if not challenge or challenge.get('expires',0)<=stamp or challenge.get('transport_principal')!=operator_control.PANEL_PROXY_PRINCIPAL:
                    self.pairing_challenges.pop(challenge_id,None);raise PermissionError('operator pairing challenge expired or invalid')
                if not secrets.compare_digest(hashlib.sha256(pairing_code.encode()).hexdigest(),challenge['code_digest']):
                    challenge['attempts']=int(challenge.get('attempts',0))-1
                    if challenge['attempts']<=0:self.pairing_challenges.pop(challenge_id,None)
                    raise PermissionError('operator pairing challenge denied')
                self.pairing_challenges.pop(challenge_id,None)
        token=secrets.token_urlsafe(48);expires=time.time()+8*3600
        with self.session_lock:self.sessions[token]={'principal_id':operator_control.PRIMARY_OPERATOR,'expires':expires,'transport_principal':operator_control.PANEL_PROXY_PRINCIPAL}
        return {'paired':True,'principal_id':operator_control.PRIMARY_OPERATOR,'transport_principal':operator_control.PANEL_PROXY_PRINCIPAL,'session_token':token,'expires_at_epoch':expires}

    def revoke_panel_session(self, token):
        if not isinstance(token,str) or not token:raise PermissionError('operator session required')
        with self.session_lock:
            session=self.sessions.pop(token,None)
        if not session:raise PermissionError('operator session invalid')
        return {'revoked':True,'principal_id':session['principal_id'],'authority_effect':'NONE'}

    def principal_for_key(self, supplied, session_token=None, *, allow_panel_transport=False):
        identity=self._key_identity(supplied)
        if identity!=operator_control.PANEL_PROXY_PRINCIPAL:return identity
        if isinstance(session_token,str):
            with self.session_lock:
                session=self.sessions.get(session_token)
                if session and session['expires']<=__import__('time').time():self.sessions.pop(session_token,None);session=None
            if session:return session['principal_id']
        return operator_control.PANEL_PROXY_PRINCIPAL if allow_panel_transport else None

    def floors(self):return read_json(self.floor_file,{"schema":"lion.operator-epoch-floor/v1","missions":{}})

    def reconcile_epoch_floors(self,c):
        floors=self.floors();missions=floors.get('missions') if isinstance(floors.get('missions'),dict) else {}
        for mid,row in missions.items():
            if not isinstance(row,dict) or type(row.get('control_epoch')) is not int:continue
            if c.execute('SELECT 1 FROM missions WHERE mission_id=?',(mid,)).fetchone() is None:continue
            operator_control.force_epoch_at_least(c,mid,row['control_epoch'],now,incarnation_id=row.get('incarnation_id'))

    def persist_floor(self,mission_id):
        c=self.connect()
        try:state=operator_control.control_state(c,mission_id,now)
        finally:c.close()
        with self.lock:
            value=self.floors();value.setdefault('schema','lion.operator-epoch-floor/v1');missions=value.setdefault('missions',{})
            prior=missions.get(mission_id) if isinstance(missions.get(mission_id),dict) else {}
            epoch=max(int(prior.get('control_epoch') or 0),int(state['control_epoch']))
            missions[mission_id]={"control_epoch":epoch,"incarnation_id":state['incarnation_id'],"control_owner":state['control_owner'],
                                  "pause_latch":int(state['pause_latch']),"stop_latch":int(state['stop_latch']),"updated_at":now()}
            atomic_json(self.floor_file,value)

    def update_command_state(self,command_id,mission_id,execution,observation,detail):
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT 1 FROM operator_commands WHERE command_id=? AND mission_id=?',(command_id,mission_id)).fetchone()
            if not row:raise ValueError('command not found')
            result=c.execute('SELECT result_json FROM operator_commands WHERE command_id=?',(command_id,)).fetchone()
            try:payload=json.loads(result['result_json'] or '{}')
            except Exception:payload={}
            payload['driver_resume']={"execution_state":execution,"observation_state":observation,"detail":detail,"observed_at":now()}
            c.execute('UPDATE operator_commands SET execution_state=?,observation_state=?,result_json=? WHERE command_id=?',
                      (execution,observation,json.dumps(payload,sort_keys=True,separators=(',',':')),command_id))
            raw={"command_id":command_id,"execution_state":execution,"observation_state":observation,"detail":detail}
            c.execute('INSERT INTO operator_events(mission_id,command_id,event_type,payload_json,payload_digest,observed_at) VALUES(?,?,?,?,?,?)',
                      (mission_id,command_id,'OPERATOR_COMMAND_EXECUTION_UPDATE',json.dumps(raw,sort_keys=True,separators=(',',':')),operator_control.digest(raw),now()))
            c.commit()
        except Exception:c.rollback();raise
        finally:c.close()

    def try_resume_driver(self,command):
        result=command.get('result') or {}
        if not result.get('driver_resume_required'):return command
        mid=command['mission_id'];cid=command['command_id']
        body=json.dumps({'action':'RESUME'}).encode();req=urllib.request.Request(
            self.mission_control_url+'/api/v3/missions/'+mid+'/actions',data=body,
            headers={'Content-Type':'application/json','User-Agent':'LION-Operator-Gateway/1'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=5) as response:
                value=json.loads(response.read().decode('utf-8'))
            self.update_command_state(cid,mid,'DRIVER_RESUME_REQUESTED','READBACK_PRESENT',str((value.get('result') or {}).get('state') or value.get('status') or 'OK'))
        except Exception as exc:
            self.update_command_state(cid,mid,'WAITING_DRIVER_SERVICE','PARTIAL',type(exc).__name__)
        c=self.connect()
        try:return operator_control.command_status(c,cid)
        finally:c.close()

    def apply(self,value,*,principal_id):
        c=self.connect()
        try:out=operator_control.apply_command(c,value,now,principal_id=principal_id)
        finally:c.close()
        if value.get('action') in operator_control.CONTROL_ACTIONS or value.get('action')=='REASSIGN':
            self.persist_floor(value['mission_id'])
        return self.try_resume_driver(out) if value.get('action')=='RESUME_SCOPE' else out

    def _conversation_bindings(self,c,mission_id):
        rows=c.execute("""SELECT logical_drone_id,material_drone_id
                          FROM mission_execution_assignments
                          WHERE mission_id=? AND phase_id='__TOPOLOGY__' AND state='BOUND'
                            AND logical_drone_id IS NOT NULL AND material_drone_id IS NOT NULL
                          ORDER BY logical_drone_id,material_drone_id""",(mission_id,)).fetchall()
        out=[];seen=set()
        for row in rows:
            pair=(str(row['logical_drone_id']),str(row['material_drone_id']))
            if pair in seen:continue
            seen.add(pair);out.append(pair)
        return out

    def _conversation_binding(self,c,mission_id,target,correlation_id):
        bindings=self._conversation_bindings(c,mission_id)
        if not bindings:raise ValueError('conversation topology unavailable')
        candidates=list(bindings)
        if isinstance(target,str) and target.startswith('drone:'):
            ident=target.split(':',1)[1];candidates=[x for x in bindings if x[0]==ident]
        elif isinstance(target,str) and target.startswith('worker:'):
            ident=target.split(':',1)[1];candidates=[x for x in bindings if x[1]==ident]
        elif isinstance(target,str) and target.startswith('group:'):
            recipients=set(operator_control.resolve_target(c,mission_id,target))
            candidates=[x for x in bindings if ('drone:'+x[0]) in recipients or ('worker:'+x[1]) in recipients]
        elif isinstance(target,str) and target not in {'mission:'+mission_id,'swarm:'+mission_id}:
            operator_control.resolve_target(c,mission_id,target)
        if not candidates:raise ValueError('conversation target has no current executor')
        seed=str(correlation_id or target or mission_id)
        index=int(hashlib.sha256(seed.encode('utf-8')).hexdigest(),16)%len(candidates)
        return candidates[index]

    def route_conversation_command(self,value):
        mission_id=str(value.get('mission_id') or '');target=str(value.get('target') or ('mission:'+mission_id));correlation_id=value.get('correlation_id')
        c=self.connect()
        try:logical_id,material_id=self._conversation_binding(c,mission_id,target,correlation_id)
        finally:c.close()
        routed=dict(value);routed['target']='worker:'+material_id
        payload=dict(value.get('payload') or {});payload['conversation_scope_target']=target;payload['conversation_logical_context']='drone:'+logical_id;routed['payload']=payload
        return routed,{'scope_target':target,'logical_drone_id':logical_id,'material_drone_id':material_id,'authority_effect':'NONE'}

    def _conversation_history(self,c,mission_id,correlation_id,current_message_id,limit=6):
        if not isinstance(correlation_id,str) or not correlation_id:return []
        current=c.execute("SELECT created_at,message_id FROM operator_messages WHERE mission_id=? AND message_id=?",(mission_id,current_message_id)).fetchone()
        if not current:return []
        prior=c.execute("""SELECT message_id,content,created_at
                           FROM operator_messages
                           WHERE mission_id=? AND correlation_id=? AND from_participant=? AND kind='MESSAGE'
                             AND (created_at<? OR (created_at=? AND message_id<?))
                           ORDER BY created_at DESC,message_id DESC LIMIT ?""",
                        (mission_id,correlation_id,operator_control.PRIMARY_PARTICIPANT,current['created_at'],current['created_at'],current['message_id'],int(limit))).fetchall()
        messages=[]
        for row in reversed(prior):
            messages.append({'role':'user','content':str(row['content'])[:12000]})
            reply=c.execute("""SELECT r.content
                               FROM operator_messages r
                               JOIN mission_execution_assignments a ON a.assignment_id=r.applied_assignment_id
                               WHERE r.mission_id=? AND r.correlation_id=? AND r.kind='RESPONSE'
                                 AND r.causation_id=? AND a.input_json LIKE '%"conversation_protocol_version":2%'
                               ORDER BY r.created_at DESC,r.message_id DESC LIMIT 1""",
                            (mission_id,correlation_id,row['message_id'])).fetchone()
            if reply:messages.append({'role':'assistant','content':str(reply['content'])[:12000]})
        return messages[-12:]

    def dispatch_conversation_message(self,value,applied):
        mission_id=str(value.get('mission_id') or '')
        target=str(value.get('target') or ('mission:'+mission_id))
        correlation_id=value.get('correlation_id')
        result=applied.get('result') if isinstance(applied,dict) else None
        message_id=result.get('message_id') if isinstance(result,dict) else None
        payload=value.get('payload') if isinstance(value.get('payload'),dict) else {}
        content=payload.get('content')
        if not mission_id or not isinstance(message_id,str) or not isinstance(content,str) or not content.strip():
            raise ValueError('conversation dispatch input')
        c=self.connect()
        try:
            turn=c.execute("SELECT created_at FROM operator_messages WHERE mission_id=? AND message_id=?",(mission_id,message_id)).fetchone()
            if not turn:raise ValueError('conversation message missing')
            driver=c.execute("SELECT generation,state,current_phase FROM mission_execution_drivers WHERE mission_id=?",(mission_id,)).fetchone()
            if not driver or int(driver['generation'] or 0)<1:raise ValueError('conversation driver generation unavailable')
            generation=int(driver['generation'])
            completed=c.execute("""SELECT assignment_id,state,lease_generation FROM mission_execution_assignments
                                   WHERE mission_id=? AND input_json LIKE ?
                                     AND input_json LIKE '%"conversation_protocol_version":2%'
                                     AND state='PASS'
                                   ORDER BY created_at LIMIT 1""",
                                (mission_id,'%"operator_message_ids":["'+message_id+'"]%')).fetchone()
            if completed:return {'assignment_id':completed['assignment_id'],'state':'PASS','lease_generation':completed['lease_generation'],'idempotent':True,'authority_effect':'NONE'}
            prior=c.execute("""SELECT assignment_id,state,lease_generation FROM mission_execution_assignments
                               WHERE mission_id=? AND input_json LIKE ?
                                 AND input_json LIKE '%"conversation_protocol_version":2%'
                                 AND state IN ('READY','CLAIMED')
                                 AND lease_generation=?
                               ORDER BY created_at DESC LIMIT 1""",
                            (mission_id,'%"operator_message_ids":["'+message_id+'"]%',generation)).fetchone()
            if prior:return {'assignment_id':prior['assignment_id'],'state':prior['state'],'lease_generation':prior['lease_generation'],'idempotent':True,'authority_effect':'NONE'}
            mission_phase_context=str(driver['current_phase'] or 'UNKNOWN')
            assignment_phase='OPERATOR_BUS_'+hashlib.sha256(message_id.encode('utf-8')).hexdigest()[:16]
            logical_id,material_id=self._conversation_binding(c,mission_id,target,correlation_id)
            control=operator_control.control_state(c,mission_id,now) or {}
            dispatch_authority=operator_control.PRIMARY_OPERATOR if control.get('control_owner')==operator_control.PRIMARY_OPERATOR else operator_control.AUTONOMOUS_OWNER
            history=self._conversation_history(c,mission_id,correlation_id,message_id)
            messages=history+[{'role':'user','content':content.strip()[:16000]}]
            assignment_input={
                'kind':'LOCAL_MODEL_INFERENCE',
                'capability':'OPERATOR_BUS_CONVERSATION_R1',
                'model_capability':'OPERATOR_BUS_CONVERSATION_R1',
                'purpose':'OPERATOR_BUS_CONVERSATION_R1',
                'trajectory_role':'CONVERSATION',
                'task_id':'operator-message:'+message_id,
                'correlation_id':correlation_id,
                'conversation_protocol_version':2,
                'conversation_turn_created_at':turn['created_at'],
                'mission_phase_context':mission_phase_context,
                'operator_message_ids':[message_id],
                'messages':messages[-13:],
                'max_tokens':768,
                'communication_source':'operator:primary',
                'logical_context':'drone:'+logical_id,
                'communication_phase':'OPERATOR_BUS',
                'evidence_classes':['TRUSTED_TOPOLOGY_CONTEXT','OPERATOR_MESSAGE'],
                'authority_effect':'NONE',
            }
            aid=global_scheduler.create_assignment(c,mission_id,assignment_phase,logical_id,material_id,assignment_input,now,lease_generation=int(driver['generation']),dispatch_authority=dispatch_authority)
            return {'assignment_id':aid,'state':'READY','phase_id':assignment_phase,'logical_drone_id':logical_id,'material_drone_id':material_id,'dispatch_authority':dispatch_authority,'idempotent':False,'authority_effect':'NONE'}
        finally:c.close()


def reconcile_pending_conversations_once(runtime: Runtime, limit: int = 64) -> dict:
    c=runtime.connect()
    try:
        rows=[dict(r) for r in c.execute("""SELECT mission_id,message_id,command_id,target,content,correlation_id,created_at
                                           FROM operator_messages
                                           WHERE from_participant=?
                                             AND command_id LIKE 'panel-%'
                                             AND correlation_id IS NOT NULL
                                             AND state IN ('PENDING','PARTIAL')
                                           ORDER BY created_at,message_id LIMIT ?""",
                                        (operator_control.PRIMARY_PARTICIPANT,int(limit))).fetchall()]
    finally:c.close()
    groups={}
    for row in rows:groups.setdefault((row['mission_id'],row['correlation_id']),[]).append(row)
    dispatched=existing=completed=repaired=failed=0;errors=[]
    for (_mission_id,_correlation_id),turns in groups.items():
        for row in turns:
            c=runtime.connect()
            try:
                driver=c.execute("SELECT generation FROM mission_execution_drivers WHERE mission_id=?",(row['mission_id'],)).fetchone()
                generation=int(driver['generation']) if driver and driver['generation'] is not None else None
                completed_row=c.execute("""SELECT assignment_id,state,lease_generation FROM mission_execution_assignments
                                           WHERE mission_id=? AND input_json LIKE ?
                                             AND input_json LIKE '%"conversation_protocol_version":2%'
                                             AND state='PASS'
                                           ORDER BY created_at LIMIT 1""",
                                        (row['mission_id'],'%"operator_message_ids":["'+row['message_id']+'"]%')).fetchone()
                prior=c.execute("""SELECT assignment_id,state,lease_generation FROM mission_execution_assignments
                                   WHERE mission_id=? AND input_json LIKE ?
                                     AND input_json LIKE '%"conversation_protocol_version":2%'
                                     AND state IN ('READY','CLAIMED')
                                     AND lease_generation=?
                                   ORDER BY created_at DESC LIMIT 1""",
                                (row['mission_id'],'%"operator_message_ids":["'+row['message_id']+'"]%',generation)).fetchone() if generation is not None else None
            finally:c.close()
            if completed_row:
                c=runtime.connect()
                try:
                    reply=c.execute("SELECT 1 FROM operator_messages WHERE mission_id=? AND correlation_id=? AND kind='RESPONSE' AND causation_id=? AND applied_assignment_id=? LIMIT 1",(row['mission_id'],row['correlation_id'],row['message_id'],completed_row['assignment_id'])).fetchone()
                    if reply:
                        completed+=1
                        continue
                    retained=c.execute("SELECT result_json FROM mission_assignment_payloads WHERE assignment_id=?",(completed_row['assignment_id'],)).fetchone()
                    if not retained:raise ValueError('conversation PASS missing retained payload')
                    try:result=json.loads(retained['result_json'])
                    except Exception as exc:raise ValueError('conversation retained payload invalid') from exc
                    applied=operator_control.note_assignment_application(c,completed_row['assignment_id'],result,now)
                    c.commit()
                    if not applied.get('response_message_ids'):raise ValueError('conversation PASS retained payload has no response')
                    repaired+=1;completed+=1
                    continue
                except Exception as exc:
                    failed+=1;errors.append({'message_id':row['message_id'],'error':type(exc).__name__+':'+str(exc)[:200]})
                    break
                finally:c.close()
            if prior:
                existing+=1
                break
            value={
                'command_id':row['command_id'],
                'mission_id':row['mission_id'],
                'action':'MESSAGE',
                'target':row['target'],
                'payload':{'content':row['content']},
                'correlation_id':row['correlation_id'],
            }
            try:
                routed,_=runtime.route_conversation_command(value)
                out=runtime.dispatch_conversation_message(routed,{'result':{'message_id':row['message_id']}})
                if out.get('idempotent'):existing+=1
                else:dispatched+=1
            except Exception as exc:
                failed+=1;errors.append({'message_id':row['message_id'],'error':type(exc).__name__+':'+str(exc)[:200]})
            break
    return {'pending':len(rows),'threads':len(groups),'dispatched':dispatched,'existing':existing,'completed':completed,'repaired':repaired,'failed':failed,'errors':errors,'authority_effect':'NONE'}


def conversation_reconcile_loop(runtime: Runtime):
    while True:
        try:reconcile_pending_conversations_once(runtime)
        except Exception:pass
        time.sleep(1.0)


def reconcile_active_swarm_sessions_once(runtime: Runtime) -> dict:
    c=runtime.connect()
    try:
        session_ids=[r[0] for r in c.execute("SELECT session_id FROM operator_swarm_sessions WHERE state='ACTIVE' ORDER BY created_at").fetchall()]
        processed=handoffs=responses=0
        for sid in session_ids:
            result=operator_swarm_session.reconcile_session(c,sid,now)
            processed+=int(result.get('processed') or 0);handoffs+=int(result.get('handoffs') or 0);responses+=int(result.get('responses') or 0)
        return {'sessions':len(session_ids),'processed':processed,'handoffs':handoffs,'responses':responses}
    finally:c.close()


def swarm_reconcile_loop(runtime: Runtime):
    while True:
        try:reconcile_active_swarm_sessions_once(runtime)
        except Exception:pass
        time.sleep(0.5)


def make_handler(runtime: Runtime):
    class H(BaseHTTPRequestHandler):
        server_version='LIONOperatorControl/1'
        def log_message(self,*a):return
        def reply(self,value,status=200):
            raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def auth(self,*,allow_panel_transport=False):
            host=(self.headers.get('Host') or '').split(':',1)[0].strip('[]').lower()
            if host not in {'127.0.0.1','localhost','::1'}:raise PermissionError('host denied')
            if self.headers.get('Origin'):raise PermissionError('browser origin denied')
            supplied=self.headers.get('X-LION-Operator-Key') or self.headers.get('X-LION-Operator-Proxy-Key') or self.headers.get('X-LION-Panel-Proxy-Key')
            principal=runtime.principal_for_key(supplied,self.headers.get('X-LION-Operator-Session'),allow_panel_transport=allow_panel_transport)
            if principal is None:raise PermissionError('operator authentication required')
            return principal
        def body(self,maximum=65536):
            n=int(self.headers.get('Content-Length','0'))
            if not 2<=n<=maximum or 'application/json' not in (self.headers.get('Content-Type') or ''):raise ValueError('json body')
            value=json.loads(self.rfile.read(n));
            if type(value) is not dict:raise ValueError('json object')
            return value
        def do_GET(self):
            try:
                principal=self.auth(allow_panel_transport=True);u=urlsplit(self.path);path=unquote(u.path);q=parse_qs(u.query)
                if path=='/health':return self.reply({'status':'ok','schema':operator_control.SCHEMA_ID,'authority_effect':'NONE','authenticated_principal':principal})
                if path=='/v1/session':return self.reply({'paired':principal==operator_control.PRIMARY_OPERATOR,'principal_id':principal,'authority_effect':'NONE'})
                if path=='/v1/channel/general':
                    channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    after=int((q.get('after') or ['0'])[0]);limit=int((q.get('limit') or ['200'])[0])
                    c=runtime.connect()
                    try:return self.reply(operator_control.general_channel_snapshot(c,channel_principal,now,after=after,limit=limit))
                    finally:c.close()
                if path=='/v1/swarm/session/active':
                    channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    c=runtime.connect()
                    try:return self.reply({'session':operator_swarm_session.active_session(c,channel_principal,now),'authority_effect':'NONE'})
                    finally:c.close()
                if path.startswith('/v1/swarm/sessions/'):
                    channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    tail=path[len('/v1/swarm/sessions/'):];parts=[x for x in tail.split('/') if x]
                    if not parts:raise ValueError('swarm session id')
                    sid=parts[0];c=runtime.connect()
                    try:
                        if len(parts)==2 and parts[1]=='snapshot':return self.reply(operator_swarm_session.session_snapshot(c,sid,channel_principal,now))
                        if len(parts)==2 and parts[1]=='assistant':
                            row=c.execute("SELECT * FROM operator_swarm_members WHERE session_id=? AND participant_id=?",(sid,operator_swarm_session.ASSISTANT_PARTICIPANT)).fetchone();return self.reply({'assistant':dict(row) if row else None,'authority_effect':'NONE'})
                        if len(parts)==2 and parts[1]=='assistant-stream':
                            if principal!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise PermissionError('SentinelX proxy required')
                            after=int((q.get('after') or ['0'])[0]);limit=int((q.get('limit') or ['25'])[0]);return self.reply(operator_swarm_session.assistant_stream(c,sid,channel_principal,now,after=after,limit=limit))
                        if len(parts)==1:
                            after=int((q.get('after') or ['0'])[0]);limit=int((q.get('limit') or ['25'])[0]);return self.reply(operator_swarm_session.session_stream(c,sid,channel_principal,now,after=after,limit=limit))
                        return self.reply({'error':'not found'},404)
                    finally:c.close()
                if principal==operator_control.PANEL_PROXY_PRINCIPAL:raise PermissionError('operator pairing required')
                if path=='/v1/participants':
                    c=runtime.connect()
                    try:return self.reply(operator_control.participant_snapshot(c,principal))
                    finally:c.close()
                if path=='/v1/thread':
                    correlation_id=(q.get('correlation_id') or [None])[0];limit=int((q.get('limit') or ['500'])[0])
                    if not correlation_id:raise ValueError('correlation_id')
                    c=runtime.connect()
                    try:return self.reply(operator_control.thread_snapshot(c,correlation_id,now,limit=limit))
                    finally:c.close()
                if path=='/v1/state':
                    mid=(q.get('mission_id') or [None])[0]
                    if not mid:raise ValueError('mission_id')
                    c=runtime.connect()
                    try:return self.reply(operator_control.mission_snapshot(c,mid,now))
                    finally:c.close()
                if path=='/v1/events':
                    mid=(q.get('mission_id') or [None])[0];after=int((q.get('after') or ['0'])[0]);limit=int((q.get('limit') or ['200'])[0])
                    if not mid:raise ValueError('mission_id')
                    c=runtime.connect()
                    try:return self.reply(operator_control.events_after(c,mid,after,limit=limit))
                    finally:c.close()
                if path.startswith('/v1/commands/'):
                    cid=path[len('/v1/commands/'):]
                    c=runtime.connect()
                    try:return self.reply(operator_control.command_status(c,cid))
                    finally:c.close()
                if principal==operator_control.PANEL_PROXY_PRINCIPAL:raise PermissionError('operator pairing required')
                return self.reply({'error':'not found'},404)
            except PermissionError as exc:return self.reply({'error':str(exc)},403)
            except Exception as exc:return self.reply({'error':type(exc).__name__+':'+str(exc)},400)
        def do_POST(self):
            try:
                path=unquote(urlsplit(self.path).path);value=self.body()
                if path=='/v1/session/pair/challenge':
                    if value:raise ValueError('pair challenge schema')
                    supplied=self.headers.get('X-LION-Panel-Proxy-Key') or self.headers.get('X-LION-Operator-Proxy-Key')
                    return self.reply(runtime.issue_panel_pairing_challenge(supplied),201)
                if path=='/v1/session/pair':
                    if set(value)=={'pairing_code'}:
                        challenge_id=None
                    elif set(value)=={'pairing_code','challenge_id'}:
                        challenge_id=value['challenge_id']
                    else:raise ValueError('pair schema')
                    supplied=self.headers.get('X-LION-Panel-Proxy-Key') or self.headers.get('X-LION-Operator-Proxy-Key')
                    return self.reply(runtime.pair_panel(supplied,value['pairing_code'],challenge_id),201)
                if path=='/v1/session/revoke':
                    if value:raise ValueError('revoke schema')
                    principal=self.auth()
                    if principal!=operator_control.PRIMARY_OPERATOR:raise PermissionError('primary operator session required')
                    return self.reply(runtime.revoke_panel_session(self.headers.get('X-LION-Operator-Session')))
                if path=='/v1/channel/general/messages':
                    principal=self.auth(allow_panel_transport=True)
                    channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    if set(value)!={'command_id','content'}:raise ValueError('general channel message schema')
                    c=runtime.connect()
                    try:return self.reply(operator_control.post_general_message(c,channel_principal,value['command_id'],value['content'],now),201)
                    finally:c.close()
                if path=='/v1/swarm/sessions':
                    principal=self.auth(allow_panel_transport=True);channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    allowed={'mission_id','duration_seconds','workers','mode'}
                    if set(value)-allowed or 'mission_id' not in value:raise ValueError('swarm session open schema')
                    c=runtime.connect()
                    try:return self.reply(operator_swarm_session.open_session(c,channel_principal,value['mission_id'],now,duration_seconds=int(value.get('duration_seconds') or operator_swarm_session.MAX_SESSION_SECONDS),workers=value.get('workers'),mode=value.get('mode') or 'TWO_DRONE_VERIFY'),201)
                    finally:c.close()
                if path.startswith('/v1/swarm/sessions/'):
                    principal=self.auth(allow_panel_transport=True);channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    tail=path[len('/v1/swarm/sessions/'):];parts=[x for x in tail.split('/') if x]
                    if len(parts)!=2:raise ValueError('swarm session operation')
                    sid,op=parts;c=runtime.connect()
                    try:
                        if op=='messages':
                            allowed={'command_id','target','content','kind','correlation_id','causation_id','thread_id','verifier_worker'}
                            if set(value)-allowed or not {'command_id','target','content'}.issubset(value):raise ValueError('swarm message schema')
                            return self.reply(operator_swarm_session.send_message(c,channel_principal,sid,value['command_id'],value['target'],value['content'],now,kind=value.get('kind') or 'REQUEST',correlation_id=value.get('correlation_id'),causation_id=value.get('causation_id'),thread_id=value.get('thread_id'),verifier_worker=value.get('verifier_worker')),201)
                        if op=='assistant-attach':
                            if principal!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise PermissionError('SentinelX proxy required')
                            if set(value)-{'model_identity'}:raise ValueError('assistant attach schema')
                            return self.reply(operator_swarm_session.attach_assistant(c,channel_principal,sid,now,model_identity=value.get('model_identity') or 'UNKNOWN'),201)
                        if op=='assistant-messages':
                            if principal!=operator_control.SENTINELX_PROXY_PRINCIPAL:raise PermissionError('SentinelX proxy required')
                            allowed={'command_id','target','content','kind','correlation_id','causation_id','thread_id'}
                            if set(value)-allowed or not {'command_id','target','content'}.issubset(value):raise ValueError('assistant message schema')
                            return self.reply(operator_swarm_session.assistant_send(c,channel_principal,sid,value['command_id'],value['target'],value['content'],now,kind=value.get('kind') or 'MESSAGE',correlation_id=value.get('correlation_id'),causation_id=value.get('causation_id'),thread_id=value.get('thread_id')),201)
                        if op=='close':
                            if value:raise ValueError('swarm close schema')
                            return self.reply(operator_swarm_session.close_session(c,sid,channel_principal,now))
                        return self.reply({'error':'not found'},404)
                    finally:c.close()
                principal=self.auth()
                if path=='/v1/commands':
                    if principal==operator_control.PRIMARY_OPERATOR and isinstance(value,dict) and value.get('action')=='MESSAGE':
                        mission_id=value.get('mission_id');payload=value.get('payload') if isinstance(value.get('payload'),dict) else {};content=payload.get('content');command_id=value.get('command_id');target=value.get('target') or ('mission:'+str(mission_id or ''))
                        c=runtime.connect()
                        try:
                            active=operator_swarm_session.active_session(c,principal,now)
                            if active and active.get('session',{}).get('mission_id')==mission_id:
                                sid=active['session']['session_id'];members=active.get('members') or []
                                if target in {'mission:'+mission_id,'swarm:'+mission_id}:
                                    primary=next((m.get('participant_id') for m in members if m.get('member_kind')=='MATERIAL_WORKER' and m.get('role')=='PRIMARY' and m.get('state')=='ACTIVE'),None)
                                    if not primary:raise ValueError('swarm primary worker unavailable')
                                    target=primary
                                sent=operator_swarm_session.send_message(c,principal,sid,command_id,target,content,now,kind='REQUEST',correlation_id=value.get('correlation_id'))
                                return self.reply({'schema':'lion.operator-command-swarm-route/v1','mission_id':mission_id,'session_id':sid,'round_id':sent.get('round_id'),'message':sent.get('message'),'assignments':sent.get('assignments') or [],'admission_state':'ACCEPTED','execution_state':'DISPATCHED','observation_state':'PERSISTED','authority_effect':'NONE','idempotent':bool(sent.get('idempotent'))},201)
                        finally:c.close()
                        try:
                            routed,route_meta=runtime.route_conversation_command(value)
                        except Exception as route_exc:
                            applied=runtime.apply(value,principal_id=principal)
                            response=dict(applied);response.update({'schema':'lion.operator-conversation-dispatch/v1','execution_state':'WAITING_DISPATCH','observation_state':'PERSISTED','conversation_route':None,'dispatch_error':type(route_exc).__name__+':'+str(route_exc)[:400],'authority_effect':'NONE'})
                            return self.reply(response,201)
                        applied=runtime.apply(routed,principal_id=principal)
                        try:
                            dispatch=runtime.dispatch_conversation_message(routed,applied)
                            response=dict(applied);response.update({'schema':'lion.operator-conversation-dispatch/v1','execution_state':'DISPATCHED','observation_state':'PERSISTED','conversation_route':route_meta,'conversation_assignment':dispatch,'authority_effect':'NONE'})
                            return self.reply(response,201)
                        except Exception as exc:
                            response=dict(applied);response.update({'schema':'lion.operator-conversation-dispatch/v1','execution_state':'WAITING_DISPATCH','observation_state':'PERSISTED','conversation_route':route_meta,'dispatch_error':type(exc).__name__+':'+str(exc)[:400],'authority_effect':'NONE'})
                            return self.reply(response,201)
                    return self.reply(runtime.apply(value,principal_id=principal),201)
                if path=='/v1/events/ack':
                    if set(value)!={'consumer_id','mission_id','event_id'}:raise ValueError('ack schema')
                    c=runtime.connect()
                    try:return self.reply(operator_control.acknowledge_events(c,value['consumer_id'],value['mission_id'],value['event_id'],now))
                    finally:c.close()
                return self.reply({'error':'not found'},404)
            except PermissionError as exc:return self.reply({'error':str(exc)},403)
            except Exception as exc:return self.reply({'error':type(exc).__name__+':'+str(exc)},409)
    return H


class FleetThreadingHTTPServer(ThreadingHTTPServer):
    request_queue_size=128
    daemon_threads=True
    allow_reuse_address=True


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default=DEFAULT_DB);p.add_argument('--key-file',default=DEFAULT_KEY);p.add_argument('--proxy-key-file',default=DEFAULT_PROXY_KEY);p.add_argument('--panel-proxy-key-file',default=DEFAULT_PANEL_PROXY_KEY);p.add_argument('--pairing-key-file',default=DEFAULT_PAIRING_KEY)
    p.add_argument('--epoch-floor',default=DEFAULT_FLOOR);p.add_argument('--mission-control-url',default='http://127.0.0.1:8766')
    p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8767);p.add_argument('--bootstrap-primary',action='store_true')
    a=p.parse_args()
    if a.host not in {'127.0.0.1','::1'}:raise SystemExit('operator gateway must remain loopback-only')
    runtime=Runtime(Path(a.db),Path(a.key_file),Path(a.proxy_key_file),Path(a.panel_proxy_key_file),Path(a.pairing_key_file),Path(a.epoch_floor),a.mission_control_url,bootstrap_primary=a.bootstrap_primary)
    threading.Thread(target=swarm_reconcile_loop,args=(runtime,),daemon=True,name='operator-swarm-reconciler').start()
    threading.Thread(target=conversation_reconcile_loop,args=(runtime,),daemon=True,name='operator-conversation-reconciler').start()
    FleetThreadingHTTPServer((a.host,a.port),make_handler(runtime)).serve_forever()


if __name__=='__main__':main()
