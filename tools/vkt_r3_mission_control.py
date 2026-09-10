#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from cyber_lion.vkt_r3.mission_control.source import EvidenceSource
from cyber_lion.vkt_r3.mission_control.server import MissionControl, serve

def resolve_source(args):
    head=args.source_head; tree=args.source_tree
    if not head or not tree:
        identity=json.loads(Path(args.source_identity).read_text())
        head=head or identity.get('source_head'); tree=tree or identity.get('source_tree')
    if not isinstance(head,str) or len(head)!=40 or not isinstance(tree,str) or len(tree)!=40: raise SystemExit('invalid source identity')
    return head,tree
def build(args):
    head,tree=resolve_source(args); return MissionControl(EvidenceSource(head,tree,args.client),args.db,args.interval)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--source-head'); p.add_argument('--source-tree'); p.add_argument('--source-identity',default='/opt/lion/k3s-vkt-r3/source-identity.json'); p.add_argument('--client',default='/usr/local/libexec/lion-vkt-effect-admission-client.py'); p.add_argument('--db',default='/var/lib/sentinelx/uploads/vkt-r3-mission-control/mission-control.db'); p.add_argument('--interval',type=float,default=2.0)
    sp=p.add_subparsers(dest='command',required=True); s=sp.add_parser('serve'); s.add_argument('--host',default='127.0.0.1'); s.add_argument('--port',type=int,default=8765); sp.add_parser('status'); sp.add_parser('export'); sp.add_parser('verify')
    a=p.parse_args(); mc=build(a)
    if a.command=='serve': serve(mc,a.host,a.port); return 0
    if a.command=='status': print(json.dumps(mc.poll_once(),sort_keys=True)); return 0
    if a.command=='export': print(json.dumps(mc.store.export(),sort_keys=True)); return 0
    if a.command=='verify':
        x=mc.poll_once(); ok=not x.get('errors'); print(json.dumps({'ok':ok,'errors':x.get('errors',[]),'state':x},sort_keys=True)); return 0 if ok else 2
    return 2
if __name__=='__main__': raise SystemExit(main())
