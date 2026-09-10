#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, socket, sys
SOCKET='/run/lion-runner-exec.sock'; HEX40=re.compile(r'^[0-9a-f]{40}$'); HEX64=re.compile(r'^[0-9a-f]{64}$'); MAX=10*1024*1024

def rid(): return hashlib.sha256(os.urandom(32)).hexdigest()
def call(req):
    if os.geteuid()!=0: raise SystemExit('runner-exec client requires root caller')
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect(SOCKET); s.sendall(json.dumps(req,sort_keys=True,separators=(',',':')).encode()+b'\n'); s.shutdown(socket.SHUT_WR)
    data=bytearray()
    while True:
        p=s.recv(65536)
        if not p: break
        data.extend(p)
        if len(data)>MAX: raise SystemExit('runner-exec response too large')
    s.close(); v=json.loads(bytes(data).decode()); print(json.dumps(v,sort_keys=True,separators=(',',':'))); return 0 if v.get('ok') is True else 2
p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True); sub.add_parser('identity')
for n in ('static-unittest','static-pycompile'):
    q=sub.add_parser(n); q.add_argument('--repo-path',required=True); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True)
q=sub.add_parser('provider-call'); q.add_argument('--provider-operation',choices=['PING','LIST_FLEET_RESOURCES'],required=True); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True)
q=sub.add_parser('pod-provider-call'); q.add_argument('--provider-operation',choices=['PRECHECK_POD_RUNTIME','PREPARE_LOCAL_K8S','MATERIALIZE_VKT_PODS','READ_POD_EVIDENCE','STOP_VKT_PODS'],required=True); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True); q.add_argument('--run-id',required=True)
q=sub.add_parser('scale64-run'); q.add_argument('--source-head',required=True); q.add_argument('--source-tree',required=True); q.add_argument('--run-request-id',required=True)
a=p.parse_args(); req={'schema_version':'1.0.0','request_id':rid()}
if a.cmd=='identity': req['operation']='IDENTITY'
elif a.cmd in ('static-unittest','static-pycompile'):
    if not HEX40.fullmatch(a.source_head) or not HEX40.fullmatch(a.source_tree): raise SystemExit('invalid source identity')
    req.update(operation='STATIC_UNITTEST' if a.cmd=='static-unittest' else 'STATIC_PYCOMPILE',repo_path=a.repo_path,source_head=a.source_head,source_tree=a.source_tree)
elif a.cmd=='provider-call':
    if not HEX40.fullmatch(a.source_head) or not HEX40.fullmatch(a.source_tree): raise SystemExit('invalid source identity')
    req.update(operation='PROVIDER_CALL',provider_operation=a.provider_operation,source_head=a.source_head,source_tree=a.source_tree)
elif a.cmd=='pod-provider-call':
    if not HEX40.fullmatch(a.source_head) or not HEX40.fullmatch(a.source_tree): raise SystemExit('invalid source identity')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',a.run_id): raise SystemExit('invalid run id')
    req.update(operation='POD_PROVIDER_CALL',provider_operation=a.provider_operation,source_head=a.source_head,source_tree=a.source_tree,run_id=a.run_id)
else:
    if not HEX40.fullmatch(a.source_head) or not HEX40.fullmatch(a.source_tree) or not HEX64.fullmatch(a.run_request_id): raise SystemExit('invalid scale64 identity')
    req.update(operation='SCALE64_RUN',source_head=a.source_head,source_tree=a.source_tree,run_request_id=a.run_request_id)
raise SystemExit(call(req))
