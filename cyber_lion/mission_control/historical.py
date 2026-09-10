from __future__ import annotations
import hashlib,json,re
from pathlib import Path
VKT_SUMMARY=Path('/var/lib/sentinelx/uploads/vkt-r3-lpcl-v2-final/final-summary.json')
VKT_VALIDATION=Path('/var/lib/sentinelx/uploads/vkt-r3-validation/lpcl-v2-supervised-600s.json')
OSS_SUMMARY=Path('/var/lib/sentinelx/uploads/oss-repository-tests/itsdangerous/final-summary.json')
OSS_EVIDENCE=Path('/var/lib/sentinelx/uploads/oss-repository-tests/itsdangerous/final-evidence.json')
def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def _artifact(p):return {'path':str(p),'sha256':_sha(p),'evidence_class':'HISTORICAL_IMPORTED_EVIDENCE'}
def import_known(store):
 if VKT_SUMMARY.is_file():
  s=json.loads(VKT_SUMMARY.read_text());checks=s.get('pre_cleanup_checks') or {};arts=[_artifact(VKT_SUMMARY)]
  if VKT_VALIDATION.is_file():arts.append(_artifact(VKT_VALIDATION))
  run={'run_id':s.get('run','historical-vkt-r3'),'process_language':'LPCL-1_0','process_class':'VKT_R3_384_DRONE_TEST','adapter_type':'VKT_R3','status':'PASS' if s.get('final_status')=='PASS' else 'UNKNOWN','verification_status':'VERIFIED' if s.get('validation_600s_pass') and s.get('validator_status')=='PASS' and not s.get('validator_errors') else 'DEGRADED','phase':'CLEANUP_COMPLETED','host':'LION-AUTH-LAB','runtime':'K3S','namespace':'vkt-r3','source':s.get('source_head'),'target':'VKT-R3','workload':'384 drones','authority':'OBSERVATION_ONLY','metrics':{'pods':384 if checks.get('ready_384') else None,'uids':384 if checks.get('unique_uid_384') else None,'restarts':0 if checks.get('restarts_0') else None,'fresh_drones':384 if checks.get('fresh_384') else None,'cases':36 if checks.get('cases_proven_36') else None,'proven':36 if checks.get('cases_proven_36') else None,'messages':768 if checks.get('messages_768') else None,'ack_rate':1.0 if checks.get('ack_rate_1') else None,'orphans':0 if checks.get('orphans_0') else None,'duplicates':0 if checks.get('duplicates_0') else None,'vendor_requests':s.get('vendor_requests')},'participants':[],'artifacts':arts,'receipts':[],'artifact_count':len(arts),'receipt_count':0,'cleanup_status':s.get('cleanup_status','UNKNOWN'),'evidence_classes':['HISTORICAL_IMPORTED_EVIDENCE','ARTIFACT_HASH','TEST_LOG'],'historical':True}
  store.index_run(run)
 if OSS_SUMMARY.is_file():
  s=json.loads(OSS_SUMMARY.read_text());ev={};arts=[_artifact(OSS_SUMMARY)]
  if OSS_EVIDENCE.is_file():
   arts.append(_artifact(OSS_EVIDENCE));ev=(json.loads(OSS_EVIDENCE.read_text()).get('result') or {})
  m=re.match(r'\s*(\d+)\s+passed',str(s.get('pytest_summary','')));passed=int(m.group(1)) if m else None
  checks=s.get('classification_checks') or {};verified=bool(checks) and all(checks.values()) and s.get('final_status')=='PASS'
  receipts=[]
  if ev.get('receipt_path') and ev.get('receipt_sha256'):receipts.append({'path':ev['receipt_path'],'sha256':ev['receipt_sha256'],'evidence_class':'PROVIDER_RECEIPT'})
  run={'run_id':s.get('run','historical-oss-itsdangerous'),'process_language':'LPCL-1_0','process_class':'AUTONOMOUS_LOCAL_K3S_OSS_REPOSITORY_TEST','adapter_type':'OSS_REPOSITORY_TEST','status':'PASS' if s.get('final_status')=='PASS' else 'UNKNOWN','verification_status':'VERIFIED' if verified else 'DEGRADED','phase':'CLEANUP_COMPLETED','host':'LION-AUTH-LAB','runtime':'K3S','namespace':s.get('k8s_namespace'),'source':s.get('platform_source_head'),'target':s.get('target_repository'),'workload':s.get('k8s_job'),'authority':'OBSERVATION_ONLY','metrics':{'tests_passed':passed,'tests_failed':0 if verified else None,'tests_skipped':0 if verified else None,'pytest_exit_code':s.get('pytest_exit_code'),'clone_exit_code':s.get('clone_exit_code'),'pod_restarts':s.get('pod_restarts')},'participants':[{'pod_uid':s.get('pod_uid'),'role':'test-pod'}] if s.get('pod_uid') else [],'artifacts':arts,'receipts':receipts,'artifact_count':len(arts),'receipt_count':len(receipts),'cleanup_status':s.get('cleanup_status','UNKNOWN'),'evidence_classes':['HISTORICAL_IMPORTED_EVIDENCE','ARTIFACT_HASH','TEST_LOG']+(['PROVIDER_RECEIPT'] if receipts else []),'historical':True,'adapter_detail':{'cloned_head':s.get('cloned_head'),'target_commit':s.get('target_commit'),'pytest_summary':s.get('pytest_summary'),'post_cleanup_status':s.get('post_cleanup_status'),'init_image_id':s.get('init_image_id'),'test_image_id':s.get('test_image_id')}}
  store.index_run(run)
