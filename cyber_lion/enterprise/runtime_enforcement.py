"""F009 R2 fail-closed bridge from canonical PDP evidence to inert runtime admission.

No effect is executed here. Caller-provided semantic objects are accepted only when an
independently configured canonical PDP source and an exact provisioned executor bind them.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime,timezone
from hashlib import sha256
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.executor_provisioning import ExecutorProvisioningRequest,ProviderTrustBinding,ProvisionedExecutor
from cyber_lion.contracts.policy_gate import GateApplied,PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import CanonicalPDPDecisionEvidence,PDPSourceTrustBinding,RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding,canonical_json
from .control_plane import ActionProposal
from .live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from .policy_gate import authority_contains

class RuntimeEnforcementError(RuntimeError):pass

class RuntimeAdmissionReplayGuard(Protocol):
    def consume(self,replay_key:str)->bool:...

class CanonicalPDPDecisionSource(Protocol):
    source_id:str
    source_instance_id:str
    implementation_digest:str
    trust_anchor_id:str
    trust_anchor_digest:str
    def resolve(self,request_id:str,gate_event_id:str)->CanonicalPDPDecisionEvidence:...
    def current_policy_binding(self,policy_binding:str)->str:...

class InMemoryRuntimeAdmissionReplayGuard:
    def __init__(self):self._lock=Lock();self._seen:set[str]=set()
    def consume(self,replay_key:str)->bool:
        with self._lock:
            if replay_key in self._seen:return False
            self._seen.add(replay_key);return True

_OBS_CEILING={"HEALTHY":"privileged","DEGRADED":"read","LOST":"none"}

def _pdp_receipt_digest(receipt:PDPDecisionReceipt)->str:
    receipt.validate();return sha256(b"LION/F009-PDP-RECEIPT/2\0"+canonical_json(asdict(receipt))).hexdigest()

def _utc(value:str)->datetime:
    try:d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise RuntimeEnforcementError("canonical PDP evidence timestamp invalid") from exc
    if d.tzinfo is None:raise RuntimeEnforcementError("canonical PDP evidence timestamp must be timezone-aware")
    return d.astimezone(timezone.utc)

class RuntimeAdmissionEngine:
    def __init__(self,*,authority_admission:LiveAuthorityAdmission,pdp_source:CanonicalPDPDecisionSource,pdp_source_trust:PDPSourceTrustBinding,replay_guard:RuntimeAdmissionReplayGuard):
        if not isinstance(authority_admission,LiveAuthorityAdmission):raise RuntimeEnforcementError("LiveAuthorityAdmission is required")
        if type(pdp_source_trust) is not PDPSourceTrustBinding:raise RuntimeEnforcementError("exact PDP source trust binding required")
        pdp_source_trust.validate()
        actual=(getattr(pdp_source,"source_id",None),getattr(pdp_source,"source_instance_id",None),getattr(pdp_source,"implementation_digest",None),getattr(pdp_source,"trust_anchor_id",None),getattr(pdp_source,"trust_anchor_digest",None))
        if actual!=pdp_source_trust.binding():raise RuntimeEnforcementError("canonical PDP source substitution denied")
        if not callable(getattr(pdp_source,"resolve",None)) or not callable(getattr(pdp_source,"current_policy_binding",None)):raise RuntimeEnforcementError("canonical PDP source unavailable")
        if not callable(getattr(replay_guard,"consume",None)):raise RuntimeEnforcementError("runtime replay guard unavailable")
        self._authority=authority_admission;self._source=pdp_source;self._source_trust=pdp_source_trust;self._replay=replay_guard

    def _canonical_pdp(self,gate:GateApplied,receipt:PDPDecisionReceipt,trusted_now:datetime)->CanonicalPDPDecisionEvidence:
        try:evidence=self._source.resolve(gate.request_id,gate.gate_event_id)
        except Exception as exc:raise RuntimeEnforcementError("canonical PDP evidence unavailable") from exc
        if type(evidence) is not CanonicalPDPDecisionEvidence:raise RuntimeEnforcementError("canonical PDP source returned invalid evidence")
        try:evidence.validate()
        except Exception as exc:raise RuntimeEnforcementError("canonical PDP evidence invalid") from exc
        source_binding=(evidence.source_id,evidence.source_instance_id,evidence.source_implementation_digest,evidence.trust_anchor_id,evidence.trust_anchor_digest)
        if source_binding!=self._source_trust.binding():raise RuntimeEnforcementError("canonical PDP evidence source binding mismatch")
        now=trusted_now.astimezone(timezone.utc)
        if now<_utc(evidence.issued_at) or now>=_utc(evidence.expires_at):raise RuntimeEnforcementError("canonical GateApplied is stale or not yet current")
        pdp_digest=_pdp_receipt_digest(receipt)
        expected=(gate.request_id,gate.gate_event_id,gate.proposal_id,gate.decision_digest,pdp_digest,receipt.request_digest,receipt.replay_key,gate.policy_binding,gate.authority_lineage_digest,gate.observability_state)
        actual=(evidence.request_id,evidence.gate_event_id,evidence.proposal_id,evidence.gate_decision_digest,evidence.pdp_receipt_digest,evidence.request_digest,evidence.replay_key,evidence.policy_binding,evidence.authority_lineage_digest,evidence.observability_state)
        if actual!=expected:raise RuntimeEnforcementError("caller PDP evidence does not match canonical source")
        try:current_policy=self._source.current_policy_binding(gate.policy_binding)
        except Exception as exc:raise RuntimeEnforcementError("current policy binding unavailable") from exc
        if current_policy!=gate.policy_binding:raise RuntimeEnforcementError("GateApplied policy binding is stale")
        return evidence

    @staticmethod
    def _runtime_identity(runtime_identity:RuntimeIdentityBinding,provisioned:ProvisionedExecutor,request:ExecutorProvisioningRequest,trust:ProviderTrustBinding)->str:
        if type(provisioned) is not ProvisionedExecutor or type(request) is not ExecutorProvisioningRequest or type(trust) is not ProviderTrustBinding:raise RuntimeEnforcementError("exact provisioning evidence required")
        try:provisioned.validate_for(request,trust);runtime_identity.validate()
        except Exception as exc:raise RuntimeEnforcementError("authoritative provisioned runtime evidence invalid") from exc
        pd=provisioned.digest()
        expected=(provisioned.drone_id,provisioned.executor_id,provisioned.runtime_instance_id,provisioned.sandbox_id,provisioned.workspace_id,provisioned.runtime_attestation_digest,pd)
        actual=(runtime_identity.workload_identity,runtime_identity.execution_subject,runtime_identity.runtime_instance_id,runtime_identity.sandbox_id,runtime_identity.workspace_id,runtime_identity.runtime_attestation_digest,runtime_identity.provisioned_executor_digest)
        if actual!=expected:raise RuntimeEnforcementError("runtime/workload/execution-subject substitution denied")
        return pd

    def admit(self,*,gate:GateApplied,pdp_receipt:PDPDecisionReceipt,admitted_authority:LiveAdmittedAuthority,proposal:ActionProposal,effect:RequestedRuntimeEffect,runtime_identity:RuntimeIdentityBinding,provisioned_executor:ProvisionedExecutor,provisioning_request:ExecutorProvisioningRequest,provider_trust:ProviderTrustBinding,trusted_now:datetime)->RuntimeAdmission:
        if type(gate) is not GateApplied or type(pdp_receipt) is not PDPDecisionReceipt:raise RuntimeEnforcementError("exact canonical PDP evidence required")
        if type(admitted_authority) is not LiveAdmittedAuthority:raise RuntimeEnforcementError("exact live authority receipt required")
        if type(proposal) is not ActionProposal or type(effect) is not RequestedRuntimeEffect or type(runtime_identity) is not RuntimeIdentityBinding:raise RuntimeEnforcementError("exact runtime admission input types required")
        try:gate.validate();pdp_receipt.validate();admitted_authority.validate();proposal.validate();effect.validate();runtime_identity.validate()
        except Exception as exc:raise RuntimeEnforcementError("runtime admission input invalid") from exc
        if trusted_now.tzinfo is None:raise RuntimeEnforcementError("trusted_now must be timezone-aware")
        if gate.decision!="ALLOW" or gate.effective_authority=="none":raise RuntimeEnforcementError("runtime admission requires canonical ALLOW")
        if (pdp_receipt.request_id,pdp_receipt.gate_event_id,pdp_receipt.decision_digest)!=(gate.request_id,gate.gate_event_id,gate.decision_digest):raise RuntimeEnforcementError("PDP receipt does not bind exact GateApplied")
        canonical=self._canonical_pdp(gate,pdp_receipt,trusted_now)
        provisioned_digest=self._runtime_identity(runtime_identity,provisioned_executor,provisioning_request,provider_trust)
        if provisioned_executor.mission_id!=proposal.mission_id:raise RuntimeEnforcementError("provisioned executor mission substitution denied")
        if gate.proposal_id!=proposal.proposal_id or effect.proposal_id!=proposal.proposal_id:raise RuntimeEnforcementError("proposal substitution denied")
        if effect.mission_id!=proposal.mission_id or admitted_authority.mission_id!=proposal.mission_id:raise RuntimeEnforcementError("mission substitution denied")
        if effect.policy_binding!=gate.policy_binding:raise RuntimeEnforcementError("policy binding mismatch")
        if effect.authority_lineage_digest!=gate.authority_lineage_digest or admitted_authority.lineage_digest!=gate.authority_lineage_digest:raise RuntimeEnforcementError("authority lineage mismatch")
        if effect.observability_state!=gate.observability_state:raise RuntimeEnforcementError("observability state mismatch")
        if effect.runtime_identity_digest!=runtime_identity.digest():raise RuntimeEnforcementError("runtime identity substitution denied")
        if effect.requested_authority!=proposal.requested_authority or gate.effective_authority!=proposal.requested_authority:raise RuntimeEnforcementError("authority class substitution denied")
        if not authority_contains(admitted_authority.authority_ceiling,gate.effective_authority):raise RuntimeEnforcementError("live authority ceiling exceeded")
        if gate.observability_state=="LOST" or not authority_contains(_OBS_CEILING[gate.observability_state],gate.effective_authority):raise RuntimeEnforcementError("observability-conditioned authority ceiling exceeded")
        if (effect.action_class,effect.resource)!=(proposal.action_class,proposal.target):raise RuntimeEnforcementError("resource or action substitution denied")
        if proposal.payload_digest is None or effect.payload_digest!=proposal.payload_digest:raise RuntimeEnforcementError("exact proposal payload binding required")
        try:current=self._authority.revalidate(admitted_authority,now=trusted_now)
        except Exception as exc:raise RuntimeEnforcementError("live authority revalidation failed") from exc
        if type(current) is not LiveAdmittedAuthority:raise RuntimeEnforcementError("live revalidation returned invalid receipt")
        current.validate()
        if current.digest()!=admitted_authority.digest():raise RuntimeEnforcementError("live authority changed before runtime admission")
        effect_digest=effect.digest();identity_digest=runtime_identity.digest();live_digest=current.digest();pdp_digest=_pdp_receipt_digest(pdp_receipt)
        replay_key=sha256((canonical.evidence_digest+"\0"+gate.decision_digest+"\0"+effect_digest+"\0"+identity_digest+"\0"+live_digest+"\0"+provisioned_digest).encode("ascii")).hexdigest()
        try:consumed=self._replay.consume(replay_key)
        except Exception as exc:raise RuntimeEnforcementError("runtime replay state unavailable") from exc
        if consumed is not True:raise RuntimeEnforcementError("runtime admission replay denied")
        return RuntimeAdmission(admission_id="runtime-admission:"+replay_key,request_id=gate.request_id,gate_event_id=gate.gate_event_id,proposal_id=gate.proposal_id,gate_decision_digest=gate.decision_digest,pdp_receipt_digest=pdp_digest,pdp_evidence_digest=canonical.evidence_digest,live_authority_digest=live_digest,authority_lineage_digest=gate.authority_lineage_digest,policy_binding=gate.policy_binding,effective_authority=gate.effective_authority,requested_effect_digest=effect_digest,runtime_identity_digest=identity_digest,provisioned_executor_digest=provisioned_digest,observability_state=gate.observability_state,replay_key=replay_key).sealed()
