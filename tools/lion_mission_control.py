#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from cyber_lion.mission_control.storage import Store
from cyber_lion.mission_control.registry import AdapterRegistry
from cyber_lion.mission_control.adapters import VKTR3Adapter,OSSRepositoryTestAdapter,LPCLEventStreamAdapter
from cyber_lion.mission_control.server import MissionControl,serve
from cyber_lion.mission_control.events import EventSocket
from cyber_lion.mission_control.historical import import_known
def ids(a):
 h=a.source_head;t=a.source_tree
 if not h or not t:
  x=json.loads(Path(a.source_identity).read_text());h=h or x.get('source_head');t=t or x.get('source_tree')
 if not isinstance(h,str) or len(h)!=40 or not isinstance(t,str) or len(t)!=40:raise SystemExit('invalid source identity')
 return h,t
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-head');p.add_argument('--source-tree');p.add_argument('--source-identity',default='/opt/lion/k3s-vkt-r3/source-identity.json');p.add_argument('--client',default='/usr/local/libexec/lion-vkt-effect-admission-client.py');p.add_argument('--db',default='/var/lib/sentinelx/uploads/lion-mission-control/mission-control.db');p.add_argument('--interval',type=float,default=2.0);p.add_argument('--event-socket',default='/run/lion-mission-control/events.sock');p.add_argument('command',choices=['serve','status','export']);a=p.parse_args();h,t=ids(a);s=Store(a.db);import_known(s);r=AdapterRegistry([VKTR3Adapter(h,t,a.client),OSSRepositoryTestAdapter(h,t,a.client),LPCLEventStreamAdapter()]);mc=MissionControl(r,s,a.interval)
 if a.command=='serve':
  es=EventSocket(a.event_socket,s);es.start()
  try:serve(mc)
  finally:es.close()
  return 0
 mc.poll_once();print(json.dumps(mc.summary() if a.command=='status' else {'runs':s.runs()},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
