import dataclasses
import pytest
from cyber_lion.contracts.policy_gate import GateApplied,GateRequested,PDPDecisionReceipt,PolicyGateContractError,PolicyRevision

H="0"*64

def test_policy_revision_and_gate_records_are_digest_bound():
    p=PolicyRevision("p","7","sha256:"+H,"GREEN").validate();assert "p@7" in p.binding
    r=GateRequested("r","proposal",p.binding,H,H,H,"HEALTHY","GREEN","read",("e",)).sealed()
    assert len(r.request_digest)==64;r.validate()
    with pytest.raises(PolicyGateContractError): dataclasses.replace(r,proposal_id="other").validate()
    a=GateApplied("g","r","proposal","ALLOW","read",p.binding,H,H,H,"HEALTHY","GREEN","ok").sealed()
    assert len(a.decision_digest)==64;a.validate()
    PDPDecisionReceipt("x","r","g",r.request_digest,a.decision_digest,H).validate()

def test_deny_cannot_carry_effective_authority():
    with pytest.raises(PolicyGateContractError):
        GateApplied("g","r","p","DENY","read","p@1:x",H,H,H,"HEALTHY","GREEN","no").validate()
