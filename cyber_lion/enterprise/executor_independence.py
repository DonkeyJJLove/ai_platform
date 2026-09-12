"""Pure executor-independence assessment; never materializes executors."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from cyber_lion.contracts.executor_independence import *

def assess_executor_independence(observations,*,attestations=(),trusted_now,max_age_seconds=30):
 if type(observations) is not tuple or len(observations)<1:raise ExecutorIndependenceError('observations tuple required')
 if type(attestations) is not tuple:raise ExecutorIndependenceError('attestations tuple required')
 if type(trusted_now) is not datetime or trusted_now.utcoffset() is None:raise ExecutorIndependenceError('aware trusted_now required')
 if type(max_age_seconds) is not int or not 1<=max_age_seconds<=300:raise ExecutorIndependenceError('bounded max age')
 connectors=[];hosts=[];groups=defaultdict(list);evidence=[];stale=False
 for o in observations:
  if type(o) is not ConnectorExecutorObservation:raise ExecutorIndependenceError('exact connector observation required')
  o.validate();connectors.append(o.connector_id);hosts.append(o.host_id);groups[o.boot_id].append(o.host_id);evidence.append(o.digest());age=(trusted_now-timev(o.observed_at,'observed_at')).total_seconds();stale|=age<0 or age>max_age_seconds
 duplicate=len(connectors)!=len(set(connectors)) or len(hosts)!=len(set(hosts));shared=tuple(sorted((tuple(sorted(v)) for v in groups.values() if len(v)>1)))
 routing='UNKNOWN_STALE_EVIDENCE' if stale else ('DUPLICATE_CONNECTOR_OR_HOST_IDENTITY' if duplicate else 'DISTINCT_CONNECTOR_IDENTITIES_OBSERVED')
 boot='UNKNOWN_STALE_EVIDENCE' if stale else ('FALSIFIED_SHARED_BOOT_ID' if shared else 'NOT_FALSIFIED_BY_BOOT_ID')
 valid=[]
 for a in attestations:
  if type(a) is not IndependentExecutorAttestation:raise ExecutorIndependenceError('exact executor attestation required')
  a.validate();age=(trusted_now-timev(a.observed_at,'observed_at')).total_seconds();expires=timev(a.expires_at,'expires_at')
  if age<0 or age>max_age_seconds or trusted_now>=expires:stale=True
  valid.append(a);evidence.append(a.digest())
 if stale:
  runtime=physical=control=material='UNKNOWN_STALE_EVIDENCE'
 else:
  runtime=physical=control='NOT_PROVEN';material='NOT_PROVEN'
  if len(valid)>=2:
   exec_ids={a.executor_id for a in valid};runtime_ids={a.runtime_instance_id for a in valid};physical_ids={a.physical_domain_id for a in valid};control_ids={a.control_domain_id for a in valid};anchors={a.trust_anchor_digest for a in valid}
   if len(exec_ids)!=len(valid):raise ExecutorIndependenceError('duplicate executor attestation')
   # Different attested runtime/physical/control domains are independently necessary.
   if len(runtime_ids)==len(valid):runtime='ATTESTED_DISTINCT'
   if len(physical_ids)==len(valid):physical='ATTESTED_DISTINCT'
   if len(control_ids)==len(valid) and len(anchors)>=2:control='ATTESTED_DISTINCT'
   if (runtime,physical,control)==('ATTESTED_DISTINCT','ATTESTED_DISTINCT','ATTESTED_DISTINCT') and not shared:material='ATTESTED_DISTINCT_CANDIDATE'
 fields=dict(connector_count=len(connectors),host_identity_count=len(set(hosts)),shared_boot_groups=shared,routing_identity=routing,boot_domain_independence=boot,runtime_instance_independence=runtime,physical_machine_independence=physical,control_domain_independence=control,material_executor_independence=material,attested_executor_count=len(valid),currentness='STALE' if stale else 'CURRENT',evidence_digests=tuple(sorted(evidence)),authority_effect='NONE',runtime_effect='NONE')
 fields['assessment_digest']=seal(b'LION/EXECUTOR-INDEPENDENCE-ASSESSMENT/1\0',fields);return ExecutorIndependenceAssessment(**fields).validate()
