#!/usr/bin/env python3
"""Bounded SentinelX proxy CLI for the LION operator-control gateway.

This client never authenticates as OPERATOR_PRIMARY. Its key maps only to the
server-side OPERATOR_SENTINELX_PROXY grant and its local action vocabulary is
an additional fail-closed restriction, not the authority source.
"""
from __future__ import annotations
import argparse,json,urllib.parse,urllib.request,urllib.error,uuid
from pathlib import Path

PROXY_ACTIONS={'MESSAGE','REQUEST_STATUS','ANNOTATE','PAUSE_SCOPE','STOP_SCOPE','TAKE_CONTROL'}
DEFAULT_PROXY_KEY='/var/lib/sentinelx/uploads/lion-mission-control-v3/operator-sentinelx-proxy.key'

def key(path):
    value=Path(path).read_text(encoding='utf-8').strip()
    if len(value)<64:raise SystemExit('operator proxy key unavailable')
    return value

def request(base,key_value,path,body=None):
    data=None;headers={'Accept':'application/json','User-Agent':'LION-SentinelX-Operator-Proxy/1','X-LION-Operator-Proxy-Key':key_value};method='GET'
    if body is not None:data=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode();headers['Content-Type']='application/json';method='POST'
    req=urllib.request.Request(base.rstrip('/')+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:raise SystemExit(e.read().decode('utf-8','replace')[:2000])

def payload(action,content):
    if action in {'MESSAGE','ANNOTATE'}:return {'content':content}
    return {}

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8767');p.add_argument('--key-file',default=DEFAULT_PROXY_KEY)
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('status');s.add_argument('mission_id')
    t=sub.add_parser('thread');t.add_argument('mission_id');t.add_argument('correlation_id')
    e=sub.add_parser('events');e.add_argument('mission_id');e.add_argument('--after',type=int,default=0);e.add_argument('--limit',type=int,default=200)
    r=sub.add_parser('receipt');r.add_argument('command_id')
    cr=sub.add_parser('channel-read');cr.add_argument('--after',type=int,default=0);cr.add_argument('--limit',type=int,default=200)
    cs=sub.add_parser('channel-send');cs.add_argument('--content',required=True);cs.add_argument('--command-id')
    sa=sub.add_parser('swarm-active')
    sr=sub.add_parser('swarm-read');sr.add_argument('session_id');sr.add_argument('--after',type=int,default=0);sr.add_argument('--limit',type=int,default=25)
    ss=sub.add_parser('swarm-send');ss.add_argument('session_id');ss.add_argument('--target',required=True);ss.add_argument('--content',required=True);ss.add_argument('--kind',default='REQUEST');ss.add_argument('--command-id')
    aa=sub.add_parser('assistant-attach');aa.add_argument('session_id');aa.add_argument('--model-identity',default='UNKNOWN')
    ar=sub.add_parser('assistant-read');ar.add_argument('session_id');ar.add_argument('--after',type=int,default=0);ar.add_argument('--limit',type=int,default=25)
    asm=sub.add_parser('assistant-send');asm.add_argument('session_id');asm.add_argument('--target',required=True);asm.add_argument('--content',required=True);asm.add_argument('--kind',default='MESSAGE');asm.add_argument('--command-id');asm.add_argument('--correlation-id');asm.add_argument('--causation-id');asm.add_argument('--thread-id')
    x=sub.add_parser('intervene');x.add_argument('mission_id');x.add_argument('action',choices=sorted(PROXY_ACTIONS));x.add_argument('--target');x.add_argument('--content');x.add_argument('--command-id');x.add_argument('--correlation-id');x.add_argument('--causation-id')
    a=p.parse_args();k=key(a.key_file)
    if a.cmd=='status':out=request(a.base,k,'/v1/state?'+urllib.parse.urlencode({'mission_id':a.mission_id}))
    elif a.cmd=='thread':
        state=request(a.base,k,'/v1/state?'+urllib.parse.urlencode({'mission_id':a.mission_id}));messages=[m for m in (state.get('messages') or []) if m.get('correlation_id')==a.correlation_id];ids={m.get('message_id') for m in messages};out={'mission_id':a.mission_id,'correlation_id':a.correlation_id,'messages':list(reversed(messages)),'message_deliveries':[d for d in (state.get('message_deliveries') or []) if d.get('message_id') in ids],'control':state.get('control'),'authority_effect':'NONE'}
    elif a.cmd=='events':out=request(a.base,k,'/v1/events?'+urllib.parse.urlencode({'mission_id':a.mission_id,'after':a.after,'limit':a.limit}))
    elif a.cmd=='receipt':out=request(a.base,k,'/v1/commands/'+urllib.parse.quote(a.command_id,safe=''))
    elif a.cmd=='channel-read':out=request(a.base,k,'/v1/channel/general?'+urllib.parse.urlencode({'after':a.after,'limit':a.limit}))
    elif a.cmd=='channel-send':out=request(a.base,k,'/v1/channel/general/messages',{'command_id':a.command_id or ('sentinelx-channel-'+uuid.uuid4().hex),'content':a.content})
    elif a.cmd=='swarm-active':out=request(a.base,k,'/v1/swarm/session/active')
    elif a.cmd=='swarm-read':out=request(a.base,k,'/v1/swarm/sessions/'+urllib.parse.quote(a.session_id,safe='')+'?'+urllib.parse.urlencode({'after':a.after,'limit':a.limit}))
    elif a.cmd=='swarm-send':out=request(a.base,k,'/v1/swarm/sessions/'+urllib.parse.quote(a.session_id,safe='')+'/messages',{'command_id':a.command_id or ('sentinelx-swarm-'+uuid.uuid4().hex),'target':a.target,'content':a.content,'kind':a.kind})
    elif a.cmd=='assistant-attach':out=request(a.base,k,'/v1/swarm/sessions/'+urllib.parse.quote(a.session_id,safe='')+'/assistant-attach',{'model_identity':a.model_identity})
    elif a.cmd=='assistant-read':out=request(a.base,k,'/v1/swarm/sessions/'+urllib.parse.quote(a.session_id,safe='')+'/assistant-stream?'+urllib.parse.urlencode({'after':a.after,'limit':a.limit}))
    elif a.cmd=='assistant-send':out=request(a.base,k,'/v1/swarm/sessions/'+urllib.parse.quote(a.session_id,safe='')+'/assistant-messages',{'command_id':a.command_id or ('chatgpt-swarm-'+uuid.uuid4().hex),'target':a.target,'content':a.content,'kind':a.kind,'correlation_id':a.correlation_id,'causation_id':a.causation_id,'thread_id':a.thread_id})
    else:
        if a.action in {'MESSAGE','ANNOTATE'} and not a.content:raise SystemExit('--content required')
        command={'command_id':a.command_id or ('sentinelx-'+uuid.uuid4().hex),'mission_id':a.mission_id,'action':a.action,'target':a.target or ('mission:'+a.mission_id),'payload':payload(a.action,a.content)}
        if a.correlation_id:command['correlation_id']=a.correlation_id
        if a.causation_id:command['causation_id']=a.causation_id
        out=request(a.base,k,'/v1/commands',command)
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
