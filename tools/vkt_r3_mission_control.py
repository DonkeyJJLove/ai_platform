#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from cyber_lion.mission_control.storage import Store
from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.adapters import VKTR3Adapter,OSSRepositoryTestAdapter,LPCLEventStreamAdapter
from cyber_lion.mission_control.server import MissionControl,serve

def resolve_source(args):
    head=args.source_head; tree=args.source_tree
    if not head or not tree:
        identity=json.loads(Path(args.source_identity).read_text())
        head=head or identity.get('source_head'); tree=tree or identity.get('source_tree')
    if not isinstance(head,str) or len(head)!=40 or not isinstance(tree,str) or len(tree)!=40: raise SystemExit('invalid source identity')
    return head,tree

def build(args):
    head,tree=resolve_source(args); store=Store(args.db)
    reg=AdapterRegistry([VKTR3Adapter(head,tree,args.client),OSSRepositoryTestAdapter(head,tree,args.client),LPCLEventStreamAdapter()])
    return MissionControl(reg,store,args.interval)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--source-head'); p.add_argument('--source-tree'); p.add_argument('--source-identity',default='/opt/lion/k3s-vkt-r3/source-identity.json'); p.add_argument('--client',default='/usr/local/libexec/lion-vkt-effect-admission-client.py'); p.add_argument('--db',default='/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db'); p.add_argument('--interval',type=float,default=2.0)
    sp=p.add_subparsers(dest='command',required=True); s=sp.add_parser('serve'); s.add_argument('--host',default='127.0.0.1'); s.add_argument('--port',type=int,default=8765); s.add_argument('--fallback-port',type=int,action='append',default=[]); s.add_argument('--listen-state',default='/run/lion-mission-control/listen.json'); sp.add_parser('status'); sp.add_parser('export'); sp.add_parser('verify')
    a=p.parse_args(); mc=build(a)
    if a.command=='serve':
        ports=[a.port]+a.fallback_port if a.fallback_port else range(a.port,8776); serve(mc,a.host,ports,a.listen_state); return 0
    runs=mc.poll_once()
    if a.command=='status': print(json.dumps({'ok':mc.error is None,'summary':mc.summary()},sort_keys=True)); return 0
    if a.command=='export': print(json.dumps({'runs':mc.store.runs()},sort_keys=True)); return 0
    if a.command=='verify': print(json.dumps({'ok':mc.error is None,'runs':runs},sort_keys=True)); return 0 if mc.error is None else 2
    return 2
if __name__=='__main__': raise SystemExit(main())
