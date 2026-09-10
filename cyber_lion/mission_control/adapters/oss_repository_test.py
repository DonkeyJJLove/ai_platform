from __future__ import annotations
import copy,json,re,subprocess,uuid
from .base import Adapter
RUN_ID='LION-LPCL-1_0-BOUNDED-OSS-REPOSITORY-K3S-AUTONOMOUS-TEST-v2'
class OSSRepositoryTestAdapter(Adapter):
 adapter_id='OSS_REPOSITORY_TEST';supported_process_classes=('AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST',)
 def __init__(self,head,tree,client='/usr/local/libexec/lion-vkt-effect-admission-client.py'):self.head=head;self.tree=tree;self.client=client;self.last=None
 def _read(self):
  p=subprocess.run([self.client,'oss-evidence','--source-head',self.head,'--source-tree',self.tree,'--run-id','mc-'+uuid.uuid4().hex[:12]],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=45,check=False)
  if p.returncode:return None
  x=json.loads(p.stdout);return x.get('result') if x.get('ok') else None
 def discover_runs(self):
  x=self._read()
  if not isinstance(x,dict):return []
  if x.get('status')=='ABSENT':
   if self.last is None:return []
   run=copy.deepcopy(self.last);run['phase']='CLEANUP_COMPLETED';run['cleanup_status']='CLEANED';run['adapter_detail']['post_cleanup_status']='ABSENT'
   if x.get('receipt_path') and x.get('receipt_sha256'):run['receipts'].append({'path':x['receipt_path'],'sha256':x['receipt_sha256'],'evidence_class':'PROVIDER_RECEIPT'});run['receipt_count']=len(run['receipts'])
   self.last=run;return [run]
  js=x.get('job_status') or {};pods=x.get('pods') or [];states=[s for p in pods for s in (p.get('states') or [])];git_state=next((s for s in states if s.get('name')=='git-clone'),{});pytest_state=next((s for s in states if s.get('name')=='pytest'),{})
  success=x.get('status')=='PASS' and js.get('succeeded')==1 and js.get('failed',0)==0 and git_state.get('exit_code')==0 and pytest_state.get('exit_code')==0
  status='PASS' if success else ('RUNNING' if js.get('active',0) or pods else 'UNKNOWN');summary=x.get('pytest_summary') or '';m=re.match(r'\s*(\d+)\s+passed',summary);passed=int(m.group(1)) if m else None;restarts=sum(int(s.get('restart_count') or 0) for s in states)
  receipts=[]
  if x.get('receipt_path') and x.get('receipt_sha256'):receipts.append({'path':x['receipt_path'],'sha256':x['receipt_sha256'],'evidence_class':'PROVIDER_RECEIPT'})
  run={'run_id':RUN_ID,'process_language':'LPCL-1_0','process_class':'AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST','adapter_type':self.adapter_id,'status':status,'verification_status':'VERIFIED' if success and x.get('vendor_requests')==0 else 'OBSERVED','phase':'PYTEST','host':'LION-AUTH-LAB','runtime':'K3S','namespace':x.get('namespace'),'source':self.head,'target':'pallets/itsdangerous','workload':x.get('job'),'authority':'OBSERVATION_ONLY','metrics':{'tests_passed':passed,'tests_failed':0 if success else None,'tests_skipped':0 if success else None,'pytest_exit_code':pytest_state.get('exit_code'),'clone_exit_code':git_state.get('exit_code'),'pod_restarts':restarts},'participants':[{'pod_uid':p.get('uid'),'name':p.get('name'),'phase':p.get('phase')} for p in pods],'artifacts':[],'receipts':receipts,'artifact_count':0,'receipt_count':len(receipts),'evidence_classes':['KUBERNETES_RUNTIME','TEST_LOG']+(['PROVIDER_RECEIPT'] if receipts else []),'cleanup_status':'PENDING','adapter_detail':x}
  self.last=run;return [run]
