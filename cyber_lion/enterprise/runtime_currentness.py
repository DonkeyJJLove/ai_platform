"""F009 effect-time authority/policy/observability guard."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from typing import Protocol
from cyber_lion.contracts.executor_sandbox import SandboxOperation
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding,EffectTimeCurrentnessEvidence
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from .executor_sandbox import SandboxExecutionResult
from .live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from .policy_gate import authority_contains

class RuntimeCurrentnessError(RuntimeError):pass
class EffectTimeCurrentnessSource(Protocol):
    source_id:str;source_instance_id:str;implementation_digest:str;trust_anchor_id:str;trust_anchor_digest:str
    def resolve_authority(self,admission_digest:str)->LiveAdmittedAuthority:...
    def current_policy_binding(self,policy_binding:str)->str:...
    def current_observability_state(self,runtime_identity_digest:str,requested_effect_digest:str)->str:...
class SandboxExecutor(Protocol):
    @property
    def policy_digest(self)->str:...
    def execute(self,op:SandboxOperation,*,payload:bytes=b"")->SandboxExecutionResult:...
_OBS_CEILING={"HEALTHY":"privileged","DEGRADED":"read","LOST":"none"}

class EffectTimeCurrentnessGuardedSandbox:
    """Wrap the final sandbox boundary and revalidate immediately before the effect."""
    def __init__(self,*,inner:SandboxExecutor,admission:RuntimeAdmission,effect:RequestedRuntimeEffect,runtime_identity:RuntimeIdentityBinding,authority_admission:LiveAuthorityAdmission,currentness_source:EffectTimeCurrentnessSource,currentness_trust:CurrentnessSourceTrustBinding,clock):
        admission.validate();effect.validate();runtime_identity.validate();currentness_trust.validate()
        actual=(getattr(currentness_source,"source_id",None),getattr(currentness_source,"source_instance_id",None),getattr(currentness_source,"implementation_digest",None),getattr(currentness_source,"trust_anchor_id",None),getattr(currentness_source,"trust_anchor_digest",None))
        if actual!=currentness_trust.binding():raise RuntimeCurrentnessError("effect-time currentness source substitution denied")
        if not all(callable(getattr(currentness_source,n,None)) for n in ("resolve_authority","current_policy_binding","current_observability_state")):raise RuntimeCurrentnessError("effect-time currentness source unavailable")
        if not isinstance(authority_admission,LiveAuthorityAdmission):raise RuntimeCurrentnessError("LiveAuthorityAdmission required")
        if not callable(getattr(inner,"execute",None)) or not isinstance(getattr(inner,"policy_digest",None),str):raise RuntimeCurrentnessError("inner sandbox unavailable")
        if admission.requested_effect_digest!=effect.digest() or admission.runtime_identity_digest!=runtime_identity.digest():raise RuntimeCurrentnessError("currentness context binding mismatch")
        self._inner=inner;self._a=admission;self._e=effect;self._i=runtime_identity;self._authority=authority_admission;self._src=currentness_source;self._trust=currentness_trust;self._clock=clock;self.last_currentness_evidence=None
    @property
    def policy_digest(self):return self._inner.policy_digest
    def _now(self):
        now=self._clock()
        if not isinstance(now,datetime) or now.tzinfo is None:raise RuntimeCurrentnessError("trusted currentness clock unavailable")
        return now.astimezone(timezone.utc)
    def _check(self,op:SandboxOperation):
        if op.mission_id!=self._e.mission_id or op.executor_id!=self._i.execution_subject or op.sandbox_id!=self._i.sandbox_id or op.workspace_id!=self._i.workspace_id:raise RuntimeCurrentnessError("effect-time operation identity substitution denied")
        if (op.action,op.path)!=(self._e.action_class,self._e.resource):raise RuntimeCurrentnessError("effect-time action/resource substitution denied")
        try:admitted=self._src.resolve_authority(self._a.admission_digest)
        except Exception as exc:raise RuntimeCurrentnessError("effect-time authority evidence unavailable") from exc
        if type(admitted) is not LiveAdmittedAuthority:raise RuntimeCurrentnessError("effect-time authority type invalid")
        admitted.validate()
        if admitted.digest()!=self._a.live_authority_digest or admitted.lineage_digest!=self._a.authority_lineage_digest:raise RuntimeCurrentnessError("effect-time authority substitution denied")
        try:current=self._authority.revalidate(admitted,now=self._now())
        except Exception as exc:raise RuntimeCurrentnessError("authority revoked or stale at effect boundary") from exc
        if current.digest()!=self._a.live_authority_digest:raise RuntimeCurrentnessError("authority changed at effect boundary")
        try:policy=self._src.current_policy_binding(self._a.policy_binding)
        except Exception as exc:raise RuntimeCurrentnessError("effect-time policy currentness unavailable") from exc
        if policy!=self._a.policy_binding:raise RuntimeCurrentnessError("policy changed before effect")
        try:obs=self._src.current_observability_state(self._a.runtime_identity_digest,self._a.requested_effect_digest)
        except Exception as exc:raise RuntimeCurrentnessError("effect-time observability unavailable") from exc
        if obs!=self._a.observability_state:raise RuntimeCurrentnessError("observability changed before effect")
        if obs=="LOST" or not authority_contains(_OBS_CEILING[obs],self._a.effective_authority):raise RuntimeCurrentnessError("effect-time observability ceiling exceeded")
        now=self._now().isoformat();eid=sha256((self._a.admission_digest+"\0"+op.digest()+"\0"+now).encode()).hexdigest()
        return EffectTimeCurrentnessEvidence(eid,self._a.admission_digest,self._a.requested_effect_digest,self._a.runtime_identity_digest,self._a.live_authority_digest,self._a.authority_lineage_digest,self._a.policy_binding,obs,self._trust.source_id,self._trust.source_instance_id,self._trust.source_implementation_digest,self._trust.trust_anchor_id,self._trust.trust_anchor_digest,now).sealed()
    def execute(self,op:SandboxOperation,*,payload:bytes=b"")->SandboxExecutionResult:
        self.last_currentness_evidence=self._check(op)
        return self._inner.execute(op,payload=payload)
