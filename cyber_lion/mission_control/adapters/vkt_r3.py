from __future__ import annotations
import json,subprocess,uuid
from .base import Adapter
class VKTR3Adapter(Adapter):
 adapter_id='VKT_R3'; supported_process_classes=('LOCAL_SUPERVISED_RUNTIME_TEST','VKT_R3_384_DRONE_TEST')
 def __init__(self,head,tree,client='/usr/local/libexec/lion-vkt-effect-admission-client.py'): self.head=head;self.tree=tree;self.client=client
 def _read(self):
  p=subprocess.run([self.client,'evidence','--source-head',self.head,'--source-tree',self.tree,'--run-id','mc-'+uuid.uuid4().hex[:12]],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45,check=False)
  if p.returncode: raise RuntimeError('vkt evidence failed')
  x=json.loads(p.stdout); return x['result']
 def discover_runs(self):
  x=self._read(); r=x.get('router_state') or {}; m=r.get('mission') or {}
  rid=m.get('run_id') or 'vkt-r3-current'; status='PASS' if m.get('completed') else ('RUNNING' if x.get('materialized') else 'DISCOVERED')
  return [{'run_id':rid,'process_language':'LPCL-1_0','process_class':'VKT_R3_384_DRONE_TEST','adapter_type':self.adapter_id,'status':status,'verification_status':'CORROBORATED' if status=='PASS' else 'OBSERVED','phase':m.get('phase'),'host':'LION-AUTH-LAB','runtime':'K3S','namespace':'vkt-r3','source':self.head,'target':'VKT-R3','workload':'384 drones','authority':'OBSERVATION_ONLY','metrics':{'pods':x.get('materialized',0),'uids':x.get('unique_uid_count',0),'restarts':x.get('restart_count_total',0),'fresh_drones':r.get('fresh_count',0),'cases':r.get('cases_seen',0),'proven':r.get('cases_proven',0),'messages':r.get('messages_total',0),'ack_rate':r.get('ack_rate',0),'orphans':r.get('orphans',0),'duplicates':r.get('duplicates',0),'vendor_requests':x.get('vendor_requests',0)},'participants':r.get('participants') or {},'evidence_classes':['KUBERNETES_RUNTIME','PROVIDER_RECEIPT'],'cleanup_status':'UNKNOWN'}]
