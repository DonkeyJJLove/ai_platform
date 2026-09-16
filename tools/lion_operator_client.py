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
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8767');p.add_argument('--key-file',required=True)
    sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('status');s.add_argument('mission_id')
    e=sub.add_parser('events');e.add_argument('mission_id');e.add_argument('--after',type=int,default=0);e.add_argument('--limit',type=int,default=200)
    r=sub.add_parser('receipt');r.add_argument('command_id')
    x=sub.add_parser('intervene');x.add_argument('mission_id');x.add_argument('action',choices=sorted(PROXY_ACTIONS));x.add_argument('--target');x.add_argument('--content');x.add_argument('--command-id')
    a=p.parse_args();k=key(a.key_file)
    if a.cmd=='status':out=request(a.base,k,'/v1/state?'+urllib.parse.urlencode({'mission_id':a.mission_id}))
    elif a.cmd=='events':out=request(a.base,k,'/v1/events?'+urllib.parse.urlencode({'mission_id':a.mission_id,'after':a.after,'limit':a.limit}))
    elif a.cmd=='receipt':out=request(a.base,k,'/v1/commands/'+urllib.parse.quote(a.command_id,safe=''))
    else:
        if a.action in {'MESSAGE','ANNOTATE'} and not a.content:raise SystemExit('--content required')
        command={'command_id':a.command_id or ('sentinelx-'+uuid.uuid4().hex),'mission_id':a.mission_id,'action':a.action,'target':a.target or ('mission:'+a.mission_id),'payload':payload(a.action,a.content)}
        out=request(a.base,k,'/v1/commands',command)
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
