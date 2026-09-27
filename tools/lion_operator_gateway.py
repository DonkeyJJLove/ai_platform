#!/usr/bin/env python3
"""Loopback-only ingress for durable human operator intervention.

The gateway performs no model inference and offers no shell/URL/SQL surface.
It shares the Mission Control SQLite authority ledger but remains a separate
process so containment can survive loss of the main 8766 HTTP service.
"""
from __future__ import annotations

import argparse
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

from cyber_lion.mission_control import operator_control, operator_swarm_session, global_scheduler, execution_driver, dual_result_join

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
        self.key=load_key(self.key_file);self.proxy_key=load_key(self.proxy_key_file);self.panel_proxy_key=load_key(self.panel_proxy_key_file);self.pairing_key=load_key(self.pairing_key_file);self.mission_control_url=mission_control_url.rstrip('/');self.lock=threading.Lock();self.session_lock=threading.Lock();self.sessions={}
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

    def pair_panel(self, supplied_key, pairing_code):
        if self._key_identity(supplied_key)!=operator_control.PANEL_PROXY_PRINCIPAL:raise PermissionError('panel transport authentication required')
        if not isinstance(pairing_code,str) or len(pairing_code)!=len(self.pairing_key) or not secrets.compare_digest(pairing_code,self.pairing_key):raise PermissionError('operator pairing code denied')
        token=secrets.token_urlsafe(48);expires=__import__('time').time()+8*3600
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

    def mc_get(self,path,timeout=8):
        req=urllib.request.Request(self.mission_control_url+path,headers={'User-Agent':'LION-Protocol-Cognition/1'},method='GET')
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    def mc_post(self,path,value,timeout=10):
        body=json.dumps(value,ensure_ascii=False).encode('utf-8')
        req=urllib.request.Request(self.mission_control_url+path,data=body,headers={'Content-Type':'application/json','User-Agent':'LION-Protocol-Cognition/1'},method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as response:
            return json.loads(response.read().decode('utf-8'))

    def apply(self,value,*,principal_id):
        c=self.connect()
        try:out=operator_control.apply_command(c,value,now,principal_id=principal_id)
        finally:c.close()
        if value.get('action') in operator_control.CONTROL_ACTIONS or value.get('action')=='REASSIGN':
            self.persist_floor(value['mission_id'])
        if value.get('action')=='MESSAGE':
            result=out.get('result') if isinstance(out,dict) else None
            message_id=result.get('message_id') if isinstance(result,dict) else None
            if message_id:
                try:out['protocol_fanout']=dispatch_protocol_message(self,message_id)
                except Exception as exc:out['protocol_fanout']={'state':'PARTIAL','error':type(exc).__name__+':'+str(exc),'authority_effect':'NONE'}
        return self.try_resume_driver(out) if value.get('action')=='RESUME_SCOPE' else out


def _protocol_route(conn,message_id,participant_id):
    row=conn.execute("SELECT cognition_route FROM operator_protocol_recipient_routes WHERE message_id=? AND recipient=?",(message_id,participant_id)).fetchone()
    if row is None:raise ValueError('protocol cognition route missing')
    return str(row['cognition_route'])

def _protocol_trajectory(conn,message_id,participant_id):
    row=conn.execute("SELECT * FROM protocol_cognitive_trajectories WHERE message_id=? AND participant_id=?",(message_id,participant_id)).fetchone()
    return dict(row) if row else None


def _execution_binding(conn,mission_id,participant_id):
    if participant_id.startswith('worker:'):
        material=participant_id.split(':',1)[1]
        row=conn.execute("SELECT logical_drone_id FROM mission_execution_assignments WHERE mission_id=? AND material_drone_id=? AND phase_id='__TOPOLOGY__' ORDER BY created_at LIMIT 1",(mission_id,material)).fetchone()
        logical=(row['logical_drone_id'] if row else None) or ('MATERIAL_'+material)
        return logical,material
    if participant_id.startswith('drone:'):
        logical=participant_id.split(':',1)[1]
        row=conn.execute("SELECT material_drone_id FROM mission_execution_assignments WHERE mission_id=? AND logical_drone_id=? AND material_drone_id IS NOT NULL ORDER BY CASE WHEN phase_id='__TOPOLOGY__' THEN 0 ELSE 1 END,created_at LIMIT 1",(mission_id,logical)).fetchone()
        if row and row['material_drone_id']:return logical,row['material_drone_id']
        # Compatibility for small in-memory/operator tests where material_workers
        # carries the logical mapping directly.
        cols={r['name'] for r in conn.execute('PRAGMA table_info(material_workers)')}
        if {'mission_id','pod_name','logical_id'}.issubset(cols):
            row=conn.execute("SELECT pod_name FROM material_workers WHERE mission_id=? AND logical_id=? ORDER BY pod_name LIMIT 1",(mission_id,logical)).fetchone()
            if row and row['pod_name']:return logical,row['pod_name']
        raise ValueError('logical participant has no material execution substrate: '+participant_id)
    raise ValueError('unsupported protocol participant: '+str(participant_id))


def _participant_prompt(participant_id,mission_id,content,route):
    return ("LION PROTOCOL PARTICIPANT\nparticipant_id="+participant_id+"\nmission_id="+mission_id+
            "\ncognition_route="+route+"\nauthority_effect=NONE\n"
            "Respond only as this participant. Do not impersonate or aggregate other participants.\n\n"+content)

def _create_local_protocol_assignment(conn,msg,participant,route,logical,material,driver,dispatch_authority,prompt,dual_request_id=None):
    participant_phase='PROTO_'+operator_control.digest({'message_id':msg['message_id'],'participant_id':participant,'route':route})[:24]
    payload={
        'kind':'LOCAL_MODEL_INFERENCE',
        'purpose':'PROTOCOL_FANOUT_R1',
        'conversation_protocol_version':5,
        'protocol_message_id':msg['message_id'],
        'fanout_id':msg['fanout_id'],
        'recipient_set_digest':msg['recipient_set_digest'],
        'responding_participant_id':participant,
        'cognition_route':route,
        'model_capability':'LOCAL_MODEL_INFERENCE',
        'operator_message_ids':[msg['message_id']],
        'messages':[{'role':'user','content':prompt}],
        'max_tokens':384,
        'dual_request_id':dual_request_id,
        'authority_effect':'NONE',
    }
    aid=global_scheduler.create_assignment(conn,msg['mission_id'],participant_phase,logical,material,payload,now,lease_generation=int(driver['generation']),dispatch_authority=dispatch_authority)
    operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,local_assignment_id=aid,state='LOCAL_ASSIGNMENT_READY' if route=='LOCAL' else 'DUAL_WAITING_RESPONSES')
    conn.commit()
    return aid

def _dispatch_protocol_participant(runtime,conn,msg,delivery,driver,dispatch_authority):
    participant=delivery['recipient'];route=_protocol_route(conn,msg['message_id'],participant)
    trajectory=_protocol_trajectory(conn,msg['message_id'],participant)
    if trajectory is None:
        trajectory=operator_control.ensure_protocol_trajectory(conn,msg['message_id'],msg['mission_id'],participant,route,now)
        conn.commit()
    if trajectory['state'] in {'RESPONSE_RECONCILED','FAILED','CANCELLED','SAAS_SEND_UNKNOWN','DUAL_SAAS_SEND_UNKNOWN'}:
        return {'participant_id':participant,'cognition_route':route,'state':trajectory['state'],'idempotent':True}
    logical,material=_execution_binding(conn,msg['mission_id'],participant)
    prompt=_participant_prompt(participant,msg['mission_id'],msg['content'],route)
    if route=='DETERMINISTIC_ONLY':
        operator_control.record_protocol_model_response(conn,msg['message_id'],participant,'DETERMINISTIC_OK',now,result_digest=operator_control.digest('DETERMINISTIC_OK'),model_call_id='deterministic:'+trajectory['trajectory_id'])
        conn.commit()
        return {'participant_id':participant,'cognition_route':route,'state':'RESPONSE_RECONCILED','idempotent':False}
    if route=='LOCAL':
        if trajectory.get('local_assignment_id'):
            return {'participant_id':participant,'cognition_route':route,'state':trajectory['state'],'assignment_id':trajectory['local_assignment_id'],'idempotent':True}
        aid=_create_local_protocol_assignment(conn,msg,participant,route,logical,material,driver,dispatch_authority,prompt)
        return {'participant_id':participant,'cognition_route':route,'state':'LOCAL_ASSIGNMENT_READY','assignment_id':aid,'logical_drone_id':logical,'material_worker_id':material,'idempotent':False}
    if route=='SAAS':
        if not participant.startswith('drone:'):raise ValueError('SAAS protocol cognition requires logical drone participant')
        request_id=trajectory.get('saas_request_id')
        if not request_id:
            operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,state='SAAS_SEND_ATTEMPT')
            conn.commit()
            try:
                handoff=runtime.mc_post('/api/v3/saas-broker/requests',{'scope_type':'MISSION','mission_id':msg['mission_id'],'question':prompt,'authority_effect':'NONE'})
            except Exception:
                operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,state='SAAS_SEND_UNKNOWN')
                conn.commit()
                raise
            request_id=handoff['request_id']
            trajectory=operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,saas_request_id=request_id,state='SAAS_WAITING_RESPONSE')
            conn.commit()
        return {'participant_id':participant,'cognition_route':route,'state':trajectory['state'],'saas_request_id':request_id,'idempotent':True}
    if route=='DUAL':
        if not participant.startswith('drone:'):raise ValueError('DUAL protocol cognition requires logical drone participant')
        dual_id=trajectory.get('dual_request_id')
        if not dual_id:
            currentness={'mission_id':msg['mission_id'],'fanout_id':msg['fanout_id'],'participant_id':participant,'recipient_set_digest':msg['recipient_set_digest']}
            dual=dual_result_join.create_dual(conn,msg['mission_id'],'PROTO_'+operator_control.digest({'message_id':msg['message_id'],'participant_id':participant})[:24],prompt,currentness,now)
            dual_id=dual['request_id']
            trajectory=operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,dual_request_id=dual_id,state='DUAL_INTENT_DURABLE')
            conn.commit()
        dualrow=conn.execute("SELECT local_prompt,saas_prompt,saas_request_id FROM mission_dual_evaluations WHERE request_id=?",(dual_id,)).fetchone()
        if dualrow is None:raise ValueError('dual protocol evaluation missing')
        aid=trajectory.get('local_assignment_id')
        if not aid:
            aid=_create_local_protocol_assignment(conn,msg,participant,route,logical,material,driver,dispatch_authority,dualrow['local_prompt'],dual_request_id=dual_id)
            trajectory=operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,local_assignment_id=aid,state='DUAL_WAITING_RESPONSES')
            conn.commit()
        saas_id=trajectory.get('saas_request_id') or dualrow['saas_request_id']
        if not saas_id:
            operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,state='DUAL_SAAS_SEND_ATTEMPT')
            conn.commit()
            try:
                handoff=runtime.mc_post('/api/v3/saas-broker/requests',{'scope_type':'MISSION','mission_id':msg['mission_id'],'question':dualrow['saas_prompt'],'authority_effect':'NONE'})
            except Exception:
                operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,state='DUAL_SAAS_SEND_UNKNOWN')
                conn.commit()
                raise
            saas_id=handoff['request_id']
            dual_result_join.link_saas_request(conn,dual_id,saas_id,now)
            trajectory=operator_control.protocol_trajectory_update(conn,msg['message_id'],participant,now,saas_request_id=saas_id,state='DUAL_WAITING_RESPONSES')
            conn.commit()
        return {'participant_id':participant,'cognition_route':route,'state':'DUAL_WAITING_RESPONSES','assignment_id':aid,'dual_request_id':dual_id,'saas_request_id':saas_id,'logical_drone_id':logical,'material_worker_id':material,'idempotent':False}
    raise ValueError('unsupported protocol cognition route')

def dispatch_protocol_message(runtime: Runtime,message_id: str) -> dict:
    c=runtime.connect()
    try:
        msg=c.execute("SELECT message_id,mission_id,content,fanout_id,recipient_set_digest,state FROM operator_messages WHERE message_id=?",(message_id,)).fetchone()
        if msg is None:raise ValueError('protocol message not found')
        control=operator_control.control_state(c,msg['mission_id'],now)
        if control and (bool(control['pause_latch']) or bool(control['stop_latch'])):
            return {'state':'FENCED','message_id':message_id,'created':[],'existing':[],'failed':[],'expected':0,'authority_effect':'NONE'}
        driver=c.execute("SELECT generation,current_phase,state FROM mission_execution_drivers WHERE mission_id=?",(msg['mission_id'],)).fetchone()
        if driver is None:raise ValueError('mission execution driver unavailable')
        if driver['state'] not in {'ACTIVE','WAITING','BLOCKED'}:raise ValueError('mission driver not dispatchable')
        dispatch_authority=operator_control.PRIMARY_OPERATOR if control and control['control_owner']==operator_control.PRIMARY_OPERATOR else operator_control.AUTONOMOUS_OWNER
        rows=c.execute("SELECT recipient,delivery_state FROM operator_message_deliveries WHERE message_id=? ORDER BY recipient",(message_id,)).fetchall()
        created=[];existing=[];failed=[]
        for delivery in rows:
            participant=delivery['recipient']
            if delivery['delivery_state'] in {'APPLIED','FAILED','CANCELLED'}:continue
            try:
                before=_protocol_trajectory(c,message_id,participant)
                out=_dispatch_protocol_participant(runtime,c,msg,delivery,driver,dispatch_authority)
                (existing if before else created).append(out)
            except Exception as exc:
                failed.append({'participant_id':participant,'error':type(exc).__name__+':'+str(exc)})
        state='COMPLETE_DISPATCH' if not failed else 'PARTIAL'
        return {'state':state,'message_id':message_id,'fanout_id':msg['fanout_id'],'expected':len(rows),'created':created,'existing':existing,'failed':failed,'authority_effect':'NONE'}
    finally:c.close()


def reconcile_protocol_external_once(runtime: Runtime) -> dict:
    c=runtime.connect()
    try:
        rows=[dict(r) for r in c.execute("SELECT * FROM protocol_cognitive_trajectories WHERE state IN ('SAAS_WAITING_RESPONSE','DUAL_WAITING_RESPONSES','DUAL_LOCAL_RESPONSE_READY','DUAL_INTENT_DURABLE') ORDER BY created_at LIMIT 64").fetchall()]
    finally:c.close()
    reconciled=failed=waiting=0
    for row in rows:
        try:
            if row['cognition_route']=='SAAS':
                if not row.get('saas_request_id'):waiting+=1;continue
                status=runtime.mc_get('/api/v3/saas/requests/'+row['saas_request_id']);state=status.get('status') or status.get('state')
                if state=='RESPONDED' and isinstance(status.get('response_text'),str) and status['response_text'].strip():
                    c=runtime.connect()
                    try:
                        operator_control.record_protocol_model_response(c,row['message_id'],row['participant_id'],status['response_text'],now,result_digest=status.get('response_digest'),model_call_id='saas:'+row['saas_request_id'])
                        c.commit();reconciled+=1
                    finally:c.close()
                elif state in {'FAILED','CANCELLED','EXPIRED','REJECTED','SUPERSEDED'}:
                    c=runtime.connect()
                    try:
                        operator_control.fail_protocol_trajectory(c,row['message_id'],row['participant_id'],'SAAS_'+str(state),now)
                        c.commit();failed+=1
                    finally:c.close()
                else:waiting+=1
            elif row['cognition_route']=='DUAL':
                if row.get('state')!='DUAL_LOCAL_RESPONSE_READY':waiting+=1;continue
                if not row.get('dual_request_id'):waiting+=1;continue
                status=runtime.mc_get('/api/v3/dual/'+row['dual_request_id'])
                if status.get('state')=='JOINED' and isinstance(status.get('answer'),str) and status['answer'].strip():
                    c=runtime.connect()
                    try:
                        operator_control.record_protocol_model_response(c,row['message_id'],row['participant_id'],status['answer'],now,result_digest=operator_control.digest(status['answer']),model_call_id='dual:'+row['dual_request_id'])
                        c.commit();reconciled+=1
                    finally:c.close()
                else:waiting+=1
        except Exception:
            failed+=1
    return {'checked':len(rows),'reconciled':reconciled,'failed':failed,'waiting':waiting,'authority_effect':'NONE'}

def reconcile_protocol_fanout_once(runtime: Runtime) -> dict:
    external=reconcile_protocol_external_once(runtime)
    c=runtime.connect()
    try:
        rows=c.execute("""SELECT DISTINCT m.message_id
                         FROM operator_messages m
                         JOIN operator_message_deliveries d ON d.message_id=m.message_id
                         WHERE m.kind='MESSAGE' AND m.state IN ('PENDING','PARTIAL')
                           AND d.delivery_state NOT IN ('APPLIED','FAILED','CANCELLED')
                         ORDER BY m.created_at,m.message_id LIMIT 64""").fetchall()
        ids=[r['message_id'] for r in rows]
    finally:c.close()
    created=existing=failed=0
    for mid in ids:
        try:
            out=dispatch_protocol_message(runtime,mid)
            created+=len(out.get('created') or []);existing+=len(out.get('existing') or []);failed+=len(out.get('failed') or [])
        except Exception:failed+=1
    return {'messages':len(ids),'created':created,'existing':existing,'failed':failed,'external':external,'authority_effect':'NONE'}


def protocol_fanout_loop(runtime: Runtime):
    while True:
        try:reconcile_protocol_fanout_once(runtime)
        except Exception:pass
        time.sleep(0.75)


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
                if path=='/v1/session/pair':
                    if set(value)!={'pairing_code'}:raise ValueError('pair schema')
                    supplied=self.headers.get('X-LION-Panel-Proxy-Key') or self.headers.get('X-LION-Operator-Proxy-Key')
                    return self.reply(runtime.pair_panel(supplied,value['pairing_code']),201)
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
                    try:return self.reply(operator_swarm_session.open_session(c,channel_principal,value['mission_id'],now,duration_seconds=int(value.get('duration_seconds') or operator_swarm_session.MAX_SESSION_SECONDS),workers=value.get('workers') or operator_swarm_session.DEFAULT_WORKERS,mode=value.get('mode') or 'TWO_DRONE_VERIFY'),201)
                    finally:c.close()
                if path.startswith('/v1/swarm/sessions/'):
                    principal=self.auth(allow_panel_transport=True);channel_principal=operator_control.PRIMARY_OPERATOR if principal==operator_control.PANEL_PROXY_PRINCIPAL else principal
                    tail=path[len('/v1/swarm/sessions/'):];parts=[x for x in tail.split('/') if x]
                    if len(parts)!=2:raise ValueError('swarm session operation')
                    sid,op=parts;c=runtime.connect()
                    try:
                        if op=='messages':
                            allowed={'command_id','target','content','kind','correlation_id','causation_id','thread_id'}
                            if set(value)-allowed or not {'command_id','target','content'}.issubset(value):raise ValueError('swarm message schema')
                            return self.reply(operator_swarm_session.send_message(c,channel_principal,sid,value['command_id'],value['target'],value['content'],now,kind=value.get('kind') or 'REQUEST',correlation_id=value.get('correlation_id'),causation_id=value.get('causation_id'),thread_id=value.get('thread_id')),201)
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
    threading.Thread(target=protocol_fanout_loop,args=(runtime,),daemon=True,name='operator-protocol-fanout-reconciler').start()
    FleetThreadingHTTPServer((a.host,a.port),make_handler(runtime)).serve_forever()


if __name__=='__main__':main()
