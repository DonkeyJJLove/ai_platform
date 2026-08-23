"""F009 fail-closed bridge from canonical PDP evidence to inert runtime admission.

No effect is executed here. Runtime admission is a capability-reducing, single-use binding
that downstream execution must consume explicitly.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from threading import Lock
from typing import Protocol

from cyber_lion.contracts.policy_gate import GateApplied,PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding,canonical_json
from .control_plane import ActionProposal
from .live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from .policy_gate import authority_contains

class RuntimeEnforcementError(RuntimeError): pass

class RuntimeAdmissionReplayGuard(Protocol):
    def consume(self,replay_key:str)->bool: ...

class InMemoryRuntimeAdmissionReplayGuard:
    def __init__(self): self._lock=Lock();self._seen:set[str]=set()
    def consume(self,replay_key:str)->bool:
        with self._lock:
            if replay_key in self._seen:return False
            self._seen.add(replay_key);return True

_OBS_CEILING={"HEALTHY":"privileged","DEGRADED":"read","LOST":"none"}

def _pdp_receipt_digest(receipt:PDPDecisionReceipt)->str:
    return sha256(b"LION/F009-PDP-RECEIPT/1\0"+canonical_json(asdict(receipt))).hexdigest()

class RuntimeAdmissionEngine:
    def __init__(self,*,authority_admission:LiveAuthorityAdmission,replay_guard:RuntimeAdmissionReplayGuard):
        if not isinstance(authority_admission,LiveAuthorityAdmission): raise RuntimeEnforcementError("LiveAuthorityAdmission is required")
        if not callable(getattr(replay_guard,"consume",None)): raise RuntimeEnforcementError("runtime replay guard unavailable")
        self._authority=authority_admission;self._replay=replay_guard

    def admit(self,*,gate:GateApplied,pdp_receipt:PDPDecisionReceipt,admitted_authority:LiveAdmittedAuthority,proposal:ActionProposal,effect:RequestedRuntimeEffect,runtime_identity:RuntimeIdentityBinding,trusted_now:datetime)->RuntimeAdmission:
        if type(gate) is not GateApplied or type(pdp_receipt) is not PDPDecisionReceipt: raise RuntimeEnforcementError("exact canonical PDP evidence required")
        if type(admitted_authority) is not LiveAdmittedAuthority: raise RuntimeEnforcementError("exact live authority receipt required")
        if type(proposal) is not ActionProposal or type(effect) is not RequestedRuntimeEffect or type(runtime_identity) is not RuntimeIdentityBinding: raise RuntimeEnforcementError("exact runtime admission input types required")
        try:
            gate.validate();pdp_receipt.validate();admitted_authority.validate();proposal.validate();effect.validate();runtime_identity.validate()
        except Exception as exc: raise RuntimeEnforcementError("runtime admission input invalid") from exc
        if trusted_now.tzinfo is None: raise RuntimeEnforcementError("trusted_now must be timezone-aware")
        if gate.decision!="ALLOW" or gate.effective_authority=="none": raise RuntimeEnforcementError("runtime admission requires canonical ALLOW")
        if (pdp_receipt.request_id,pdp_receipt.gate_event_id,pdp_receipt.decision_digest)!=(gate.request_id,gate.gate_event_id,gate.decision_digest): raise RuntimeEnforcementError("PDP receipt does not bind exact GateApplied")
        if gate.proposal_id!=proposal.proposal_id or effect.proposal_id!=proposal.proposal_id: raise RuntimeEnforcementError("proposal substitution denied")
        if effect.mission_id!=proposal.mission_id or admitted_authority.mission_id!=proposal.mission_id: raise RuntimeEnforcementError("mission substitution denied")
        if effect.policy_binding!=gate.policy_binding: raise RuntimeEnforcementError("policy binding mismatch")
        if effect.authority_lineage_digest!=gate.authority_lineage_digest or admitted_authority.lineage_digest!=gate.authority_lineage_digest: raise RuntimeEnforcementError("authority lineage mismatch")
        if effect.observability_state!=gate.observability_state: raise RuntimeEnforcementError("observability state mismatch")
        if effect.runtime_identity_digest!=runtime_identity.digest(): raise RuntimeEnforcementError("runtime identity substitution denied")
        if effect.requested_authority!=proposal.requested_authority or gate.effective_authority!=proposal.requested_authority: raise RuntimeEnforcementError("authority class substitution denied")
        if not authority_contains(admitted_authority.authority_ceiling,gate.effective_authority): raise RuntimeEnforcementError("live authority ceiling exceeded")
        if not authority_contains(_OBS_CEILING[gate.observability_state],gate.effective_authority): raise RuntimeEnforcementError("observability-conditioned authority ceiling exceeded")
        if (effect.action_class,effect.resource)!=(proposal.action_class,proposal.target): raise RuntimeEnforcementError("resource or action substitution denied")
        if proposal.payload_digest is None or effect.payload_digest!=proposal.payload_digest: raise RuntimeEnforcementError("exact proposal payload binding required")
        try: current=self._authority.revalidate(admitted_authority,now=trusted_now)
        except Exception as exc: raise RuntimeEnforcementError("live authority revalidation failed") from exc
        if type(current) is not LiveAdmittedAuthority: raise RuntimeEnforcementError("live revalidation returned invalid receipt")
        current.validate()
        if current.digest()!=admitted_authority.digest(): raise RuntimeEnforcementError("live authority changed before runtime admission")
        effect_digest=effect.digest();identity_digest=runtime_identity.digest();live_digest=current.digest();pdp_digest=_pdp_receipt_digest(pdp_receipt)
        replay_key=sha256((gate.decision_digest+"\0"+effect_digest+"\0"+identity_digest+"\0"+live_digest).encode("ascii")).hexdigest()
        try: consumed=self._replay.consume(replay_key)
        except Exception as exc: raise RuntimeEnforcementError("runtime replay state unavailable") from exc
        if consumed is not True: raise RuntimeEnforcementError("runtime admission replay denied")
        return RuntimeAdmission(admission_id="runtime-admission:"+replay_key,request_id=gate.request_id,gate_event_id=gate.gate_event_id,proposal_id=gate.proposal_id,gate_decision_digest=gate.decision_digest,pdp_receipt_digest=pdp_digest,live_authority_digest=live_digest,authority_lineage_digest=gate.authority_lineage_digest,policy_binding=gate.policy_binding,effective_authority=gate.effective_authority,requested_effect_digest=effect_digest,runtime_identity_digest=identity_digest,observability_state=gate.observability_state,replay_key=replay_key).sealed()
