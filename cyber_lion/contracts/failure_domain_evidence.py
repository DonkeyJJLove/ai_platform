"""Immutable failure-domain evidence contracts; no executor or authority promotion."""
from dataclasses import asdict,dataclass
from datetime import datetime
from hashlib import sha256
import json,re

SHA=re.compile(r"^[0-9a-f]{64}$"); BOOT=re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
class FailureDomainContractError(ValueError):pass

def _text(v,n):
 if type(v) is not str or not v.strip() or "\0" in v:raise FailureDomainContractError(n)
def _digest(v,n):
 if type(v) is not str or SHA.fullmatch(v) is None:raise FailureDomainContractError(n)
def _time(v,n):
 _text(v,n)
 try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
 except ValueError as e:raise FailureDomainContractError(n) from e
 if d.utcoffset() is None:raise FailureDomainContractError(n)
 return d
def _seal(domain,v):return sha256(domain+json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

@dataclass(frozen=True)
class HostBootObservation:
 host_id:str; hostname:str; boot_id:str; virtualization_class:str; evidence_digest:str; observed_at:str
 def validate(self):
  for x,n in ((self.host_id,"host_id"),(self.hostname,"hostname"),(self.virtualization_class,"virtualization_class")):_text(x,n)
  if BOOT.fullmatch(self.boot_id) is None:raise FailureDomainContractError("boot_id")
  _digest(self.evidence_digest,"evidence_digest"); _time(self.observed_at,"observed_at"); return self
 def digest(self):self.validate();return _seal(b"LION/HOST-BOOT-OBSERVATION/1\0",asdict(self))

@dataclass(frozen=True)
class FailureDomainAssessment:
 observation_digests:tuple[str,...]; shared_boot_groups:tuple[tuple[str,...],...]; kernel_boot_domain_independence:str; physical_independence:str; material_executor_independence:str; currentness:str; assessment_digest:str; authority_effect:str="NONE"; runtime_effect:str="NONE"
 def validate(self):
  if type(self.observation_digests) is not tuple or len(self.observation_digests)<2 or len(set(self.observation_digests))!=len(self.observation_digests):raise FailureDomainContractError("observation digests")
  for x in self.observation_digests:_digest(x,"observation digest")
  if type(self.shared_boot_groups) is not tuple:raise FailureDomainContractError("shared groups")
  seen=set()
  for g in self.shared_boot_groups:
   if type(g) is not tuple or len(g)<2 or tuple(sorted(g))!=g:raise FailureDomainContractError("shared group")
   for h in g:
    _text(h,"host id")
    if h in seen:raise FailureDomainContractError("host in multiple shared groups")
    seen.add(h)
  if self.kernel_boot_domain_independence not in {"FALSIFIED_SHARED_BOOT_ID","NOT_FALSIFIED_BY_BOOT_ID","UNKNOWN_STALE_EVIDENCE"}:raise FailureDomainContractError("kernel state")
  if self.physical_independence!="NOT_PROVEN" or self.material_executor_independence!="NOT_PROVEN":raise FailureDomainContractError("independence promotion")
  if self.currentness not in {"CURRENT","STALE"}:raise FailureDomainContractError("currentness")
  if self.authority_effect!="NONE" or self.runtime_effect!="NONE":raise FailureDomainContractError("effect promotion")
  _digest(self.assessment_digest,"assessment digest")
  body=asdict(self);body.pop("assessment_digest")
  if self.assessment_digest!=_seal(b"LION/FAILURE-DOMAIN-ASSESSMENT/1\0",body):raise FailureDomainContractError("assessment digest mismatch")
  return self
