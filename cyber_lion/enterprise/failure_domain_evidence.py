"""Pure derivation of failure-domain evidence from bounded host boot observations."""
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import json
from cyber_lion.contracts.failure_domain_evidence import HostBootObservation,FailureDomainAssessment,FailureDomainContractError

def _seal(v):return sha256(b"LION/FAILURE-DOMAIN-ASSESSMENT/1\0"+json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def assess_failure_domains(observations,*,trusted_now,max_age_seconds=30):
 if type(observations) is not tuple or len(observations)<2:raise FailureDomainContractError("at least two observations required")
 if type(trusted_now) is not datetime or trusted_now.utcoffset() is None:raise FailureDomainContractError("aware trusted_now required")
 if type(max_age_seconds) is not int or not 1<=max_age_seconds<=300:raise FailureDomainContractError("bounded max age")
 ids=[];stale=False;groups=defaultdict(list);digests=[]
 for o in observations:
  if type(o) is not HostBootObservation:raise FailureDomainContractError("exact observation type required")
  o.validate();ids.append(o.host_id);digests.append(o.digest());groups[o.boot_id].append(o.host_id)
  observed=datetime.fromisoformat(o.observed_at.replace("Z","+00:00"));age=(trusted_now-observed).total_seconds()
  if age<0 or age>max_age_seconds:stale=True
 if len(ids)!=len(set(ids)):raise FailureDomainContractError("duplicate host_id")
 shared=tuple(sorted((tuple(sorted(v)) for v in groups.values() if len(v)>1),key=lambda x:x))
 kernel="UNKNOWN_STALE_EVIDENCE" if stale else ("FALSIFIED_SHARED_BOOT_ID" if shared else "NOT_FALSIFIED_BY_BOOT_ID")
 fields=dict(observation_digests=tuple(sorted(digests)),shared_boot_groups=shared,kernel_boot_domain_independence=kernel,physical_independence="NOT_PROVEN",material_executor_independence="NOT_PROVEN",currentness="STALE" if stale else "CURRENT",authority_effect="NONE",runtime_effect="NONE")
 fields["assessment_digest"]=_seal(fields)
 return FailureDomainAssessment(**fields).validate()
