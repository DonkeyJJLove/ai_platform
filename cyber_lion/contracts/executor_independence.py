"""Evidence taxonomy for material executor independence.

Connector identity, hostnames, logical drones and distinct runtime process labels are
separate evidence planes. Only externally attested physical/control/runtime domains
can support a material-executor independence candidate.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json,re

SHA=re.compile(r"^[0-9a-f]{64}$");BOOT=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
class ExecutorIndependenceError(ValueError):pass
def text(v,n):
 if type(v) is not str or not v.strip() or "\0" in v:raise ExecutorIndependenceError(n)
def dig(v,n):
 if type(v) is not str or SHA.fullmatch(v) is None:raise ExecutorIndependenceError(n)
def timev(v,n):
 text(v,n)
 try:d=datetime.fromisoformat(v.replace('Z','+00:00'))
 except ValueError as e:raise ExecutorIndependenceError(n) from e
 if d.utcoffset() is None:raise ExecutorIndependenceError(n)
 return d
def seal(domain,v):return sha256(domain+json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class ConnectorExecutorObservation:
 connector_id:str;host_id:str;hostname:str;boot_id:str;virtualization_class:str;evidence_digest:str;observed_at:str
 def validate(self):
  for v,n in ((self.connector_id,'connector_id'),(self.host_id,'host_id'),(self.hostname,'hostname'),(self.virtualization_class,'virtualization_class')):text(v,n)
  if BOOT.fullmatch(self.boot_id) is None:raise ExecutorIndependenceError('boot_id')
  dig(self.evidence_digest,'evidence_digest');timev(self.observed_at,'observed_at');return self
 def digest(self):self.validate();return seal(b'LION/CONNECTOR-EXECUTOR-OBSERVATION/1\0',asdict(self))

@dataclass(frozen=True)
class IndependentExecutorAttestation:
 executor_id:str;runtime_instance_id:str;physical_domain_id:str;control_domain_id:str;virtualization_class:str;runtime_attestation_digest:str;physical_attestation_digest:str;control_attestation_digest:str;trust_anchor_digest:str;issuer_id:str;observed_at:str;expires_at:str;attestation_class:str='EXTERNAL_HARDWARE_BOUND_CANDIDATE'
 def validate(self):
  for v,n in ((self.executor_id,'executor_id'),(self.runtime_instance_id,'runtime_instance_id'),(self.physical_domain_id,'physical_domain_id'),(self.control_domain_id,'control_domain_id'),(self.virtualization_class,'virtualization_class'),(self.issuer_id,'issuer_id')):text(v,n)
  for v,n in ((self.runtime_attestation_digest,'runtime_attestation_digest'),(self.physical_attestation_digest,'physical_attestation_digest'),(self.control_attestation_digest,'control_attestation_digest'),(self.trust_anchor_digest,'trust_anchor_digest')):dig(v,n)
  observed=timev(self.observed_at,'observed_at');expires=timev(self.expires_at,'expires_at')
  if not observed<expires or (expires-observed).total_seconds()>300:raise ExecutorIndependenceError('bounded attestation window required')
  if self.attestation_class!='EXTERNAL_HARDWARE_BOUND_CANDIDATE':raise ExecutorIndependenceError('attestation class promotion')
  if self.virtualization_class.upper() in {'WSL','WSL2','CONTAINER','LOGICAL','SAME-HOST-VM'}:raise ExecutorIndependenceError('virtualization class cannot prove physical independence')
  return self
 def digest(self):self.validate();return seal(b'LION/INDEPENDENT-EXECUTOR-ATTESTATION/1\0',asdict(self))

@dataclass(frozen=True)
class ExecutorIndependenceAssessment:
 connector_count:int;host_identity_count:int;shared_boot_groups:tuple[tuple[str,...],...];routing_identity:str;boot_domain_independence:str;runtime_instance_independence:str;physical_machine_independence:str;control_domain_independence:str;material_executor_independence:str;attested_executor_count:int;currentness:str;evidence_digests:tuple[str,...];assessment_digest:str;authority_effect:str='NONE';runtime_effect:str='NONE'
 def validate(self):
  if type(self.connector_count) is not int or self.connector_count<1 or type(self.host_identity_count) is not int or self.host_identity_count<1:raise ExecutorIndependenceError('counts')
  if self.routing_identity not in {'DISTINCT_CONNECTOR_IDENTITIES_OBSERVED','DUPLICATE_CONNECTOR_OR_HOST_IDENTITY','UNKNOWN_STALE_EVIDENCE'}:raise ExecutorIndependenceError('routing state')
  if self.boot_domain_independence not in {'FALSIFIED_SHARED_BOOT_ID','NOT_FALSIFIED_BY_BOOT_ID','UNKNOWN_STALE_EVIDENCE'}:raise ExecutorIndependenceError('boot state')
  for attr in ('runtime_instance_independence','physical_machine_independence','control_domain_independence'):
   if getattr(self,attr) not in {'NOT_PROVEN','ATTESTED_DISTINCT','UNKNOWN_STALE_EVIDENCE'}:raise ExecutorIndependenceError(attr)
  if self.material_executor_independence not in {'NOT_PROVEN','ATTESTED_DISTINCT_CANDIDATE','UNKNOWN_STALE_EVIDENCE'}:raise ExecutorIndependenceError('material state')
  if self.currentness not in {'CURRENT','STALE'}:raise ExecutorIndependenceError('currentness')
  if type(self.attested_executor_count) is not int or self.attested_executor_count<0:raise ExecutorIndependenceError('attested count')
  if type(self.evidence_digests) is not tuple or tuple(sorted(self.evidence_digests))!=self.evidence_digests or len(set(self.evidence_digests))!=len(self.evidence_digests):raise ExecutorIndependenceError('evidence vector')
  for d in self.evidence_digests:dig(d,'evidence digest')
  if self.material_executor_independence=='ATTESTED_DISTINCT_CANDIDATE':
   if self.attested_executor_count<2 or any(getattr(self,x)!='ATTESTED_DISTINCT' for x in ('runtime_instance_independence','physical_machine_independence','control_domain_independence')):raise ExecutorIndependenceError('material independence promotion')
  if self.boot_domain_independence=='FALSIFIED_SHARED_BOOT_ID' and self.material_executor_independence!='NOT_PROVEN':raise ExecutorIndependenceError('shared boot cannot promote material independence')
  if self.authority_effect!='NONE' or self.runtime_effect!='NONE':raise ExecutorIndependenceError('effect promotion')
  dig(self.assessment_digest,'assessment_digest');body=asdict(self);body.pop('assessment_digest')
  if self.assessment_digest!=seal(b'LION/EXECUTOR-INDEPENDENCE-ASSESSMENT/1\0',body):raise ExecutorIndependenceError('assessment digest mismatch')
  return self
