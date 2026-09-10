from __future__ import annotations
import json,subprocess,uuid
from .base import Adapter
class OSSRepositoryTestAdapter(Adapter):
 adapter_id='OSS_REPOSITORY_TEST'; supported_process_classes=('AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST',)
 def __init__(self,head,tree,client='/usr/local/libexec/lion-vkt-effect-admission-client.py'): self.head=head;self.tree=tree;self.client=client
 def _read(self):
  p=subprocess.run([self.client,'oss-evidence','--source-head',self.head,'--source-tree',self.tree,'--run-id','mc-'+uuid.uuid4().hex[:12]],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45,check=False)
  if p.returncode: return None
  x=json.loads(p.stdout); return x.get('result') if x.get('ok') else None
 def discover_runs(self):
  x=self._read()
  if not isinstance(x,dict): return []
  status='PASS' if x.get('job_succeeded')==1 and x.get('job_failed',0)==0 and x.get('pytest_exit_code')==0 else ('RUNNING' if x.get('pod_uid') else 'UNKNOWN')
  return [{'run_id':x.get('run_id') or 'oss-itsdangerous-current','process_language':'LPCL-1_0','process_class':'AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST','adapter_type':self.adapter_id,'status':status,'verification_status':'VERIFIED' if status=='PASS' else 'OBSERVED','phase':'PYTEST','host':'LION-AUTH-LAB','runtime':'K3S','namespace':'oss-test-itsdangerous','source':self.head,'target':'pallets/itsdangerous','workload':'itsdangerous-pytest','authority':'OBSERVATION_ONLY','metrics':{'tests_passed':x.get('tests_passed'),'tests_failed':x.get('tests_failed'),'tests_skipped':x.get('tests_skipped'),'pytest_exit_code':x.get('pytest_exit_code'),'clone_exit_code':x.get('clone_exit_code'),'pod_restarts':x.get('pod_restarts',0)},'participants':[],'artifact_count':len(x.get('artifacts') or []),'receipt_count':len(x.get('receipts') or []),'evidence_classes':['KUBERNETES_RUNTIME','TEST_LOG','PROVIDER_RECEIPT'],'cleanup_status':x.get('cleanup_status','UNKNOWN'),'adapter_detail':x}]
