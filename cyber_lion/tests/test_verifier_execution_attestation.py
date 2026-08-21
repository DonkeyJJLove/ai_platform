from __future__ import annotations

from datetime import datetime, timezone
import inspect
import unittest

from cyber_lion.contracts.verifier_execution_attestation import (
    ExactVerificationTarget, ExecutorParticipationRecord, FixedSourcePin,
    TrustedCIEvidence, TrustedParticipationHistory, TrustedSemanticVerificationResult,
    VerifierExecutionAttestation, evidence_bundle_digest,
)
from cyber_lion.contracts.workload_identity import VerifiedWorkloadIdentity
from cyber_lion.enterprise.runtime_attestation import VerifiedRuntimeAttestation
from cyber_lion.enterprise.verifier_execution_attestation import (
    InMemoryVerifierExecutionReplayGuard, VerifierExecutionAdmission,
    VerifierExecutionAdmissionError,
)

BASE="1"*40; HEAD="a"*40; TREE="b"*40; PROOF="c"*64
RUNTIME_ATTEST="d"*64; IMPL="e"*64; ARTIFACT="f"*64
MISSION="LION-FLEET-CANONICAL-STATUS-REGISTRY-P0"
NOW=datetime(2026,8,21,12,20,tzinfo=timezone.utc)

def target():
    return ExactVerificationTarget("DonkeyJJLove/ai_platform",44,BASE,HEAD,TREE,"32477275518",MISSION,"STATUS-SOURCE-ADAPTERS-R2").validate()

def pin(name):
    return FixedSourcePin(name,f"{name}-instance","0"*64,f"{name}-root").validate()

def participation(role,subject,runtime):
    return ExecutorParticipationRecord(subject,runtime,role,"DonkeyJJLove/ai_platform",MISSION,HEAD,TREE,f"history:{role}:{subject}","3"*64,"history-root","2026-08-21T11:30:00+00:00").validate()

def history(records=None):
    p=pin("history")
    records=records or (participation("BUILDER","builder","builder-runtime"),participation("VERIFICATION_ATTACH","attach","attach-runtime"))
    return TrustedParticipationHistory.build(source_id=p.source_id,source_instance_id=p.source_instance_id,trust_anchor_id=p.trust_anchor_id,source_implementation_digest=p.source_implementation_digest,observed_at="2026-08-21T11:40:00+00:00",records=tuple(records))

def workload(expires="2026-08-21T13:00:00+00:00"):
    return VerifiedWorkloadIdentity("verifier","lion","tenant","org","aud",PROOF,"key","2026-08-21T11:00:00+00:00",expires)

def runtime():
    return VerifiedRuntimeAttestation("verifier","verifier-runtime","DonkeyJJLove/ai_platform",HEAD,"4"*40,"run",1,MISSION,ARTIFACT,IMPL,RUNTIME_ATTEST,"runtime:ref","runtime-root")

def ci(conclusion="SUCCESS"):
    p=pin("ci")
    return TrustedCIEvidence(p.source_id,p.source_instance_id,p.source_implementation_digest,p.trust_anchor_id,"DonkeyJJLove/ai_platform",44,BASE,HEAD,TREE,"32477275518","Cyber-Lion Core",conclusion,"2026-08-21T12:00:00+00:00","ci:ref","5"*64).validate()

def semantic(result="PASS"):
    p=pin("semantic")
    return TrustedSemanticVerificationResult(p.source_id,p.source_instance_id,p.source_implementation_digest,p.trust_anchor_id,"sem","verifier","verifier-runtime",IMPL,target().digest(),"2"*64,result,"2026-08-21T12:05:00+00:00","sem:ref","6"*64).validate()

class Source:
    def __init__(self,name,value):
        p=pin(name); self.source_id=p.source_id; self.source_instance_id=p.source_instance_id
        self.source_implementation_digest=p.source_implementation_digest; self.trust_anchor_id=p.trust_anchor_id
        self.value=value
    def resolve(self, exact_target): return self.value

def gate(w=None,h=None,c=None,s=None,replay=None):
    return VerifierExecutionAdmission(
        expected_target=target(),
        workload_source=Source("workload",w or workload()),workload_source_pin=pin("workload"),
        runtime_source=Source("runtime",runtime()),runtime_source_pin=pin("runtime"),
        participation_source=Source("history",h or history()),participation_source_pin=pin("history"),
        ci_source=Source("ci",c or ci()),ci_source_pin=pin("ci"),
        semantic_source=Source("semantic",s or semantic()),semantic_source_pin=pin("semantic"),
        replay_guard=replay or InMemoryVerifierExecutionReplayGuard())

def request(h=None,c=None,s=None,**changes):
    h=h or history(); c=c or ci(); s=s or semantic()
    bundle=evidence_bundle_digest(target=target(),workload_identity_proof_digest=PROOF,runtime_attestation_digest=RUNTIME_ATTEST,verifier_implementation_digest=IMPL,participation_history_digest=h.history_digest,ci_evidence_digest=c.digest(),semantic_verification_result_digest=s.digest())
    values=dict(attestation_id="vea",verifier_subject_id="verifier",verifier_runtime_instance_id="verifier-runtime",verifier_implementation_digest=IMPL,workload_identity_proof_digest=PROOF,runtime_attestation_digest=RUNTIME_ATTEST,target=target(),participation_history_digest=h.history_digest,ci_evidence_digest=c.digest(),semantic_verification_result_digest=s.digest(),evidence_bundle_digest=bundle,issued_at="2026-08-21T12:10:00+00:00",expires_at="2026-08-21T12:50:00+00:00")
    values.update(changes); return VerifierExecutionAttestation(**values)

class Tests(unittest.TestCase):
    def test_public_input_surface(self):
        self.assertEqual(tuple(inspect.signature(VerifierExecutionAdmission.admit).parameters),("self","attestation","now"))

    def test_good_evidence_passes(self):
        self.assertEqual(gate().admit(request(),now=NOW).verification_result,"PASS")

    def test_expired_workload_denied(self):
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(w=workload("2026-08-21T12:00:00+00:00")).admit(request(),now=NOW)

    def test_builder_and_attach_collisions_denied(self):
        cases=(
            history((participation("BUILDER","verifier","old"),participation("VERIFICATION_ATTACH","attach","ar"))),
            history((participation("BUILDER","builder","br"),participation("VERIFICATION_ATTACH","attach","verifier-runtime"))),
        )
        for h in cases:
            with self.assertRaises(VerifierExecutionAdmissionError):
                gate(h=h).admit(request(h=h),now=NOW)

    def test_incomplete_history_denied(self):
        h=history((participation("BUILDER","builder","br"),))
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(h=h).admit(request(h=h),now=NOW)

    def test_failed_ci_denied(self):
        c=ci("FAILURE")
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(c=c).admit(request(c=c),now=NOW)

    def test_failed_semantic_denied(self):
        s=semantic("FAIL")
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate(s=s).admit(request(s=s),now=NOW)

    def test_bundle_substitution_and_replay_denied(self):
        with self.assertRaises(VerifierExecutionAdmissionError):
            gate().admit(request(evidence_bundle_digest="9"*64),now=NOW)
        guard=InMemoryVerifierExecutionReplayGuard(); g=gate(replay=guard); a=request()
        g.admit(a,now=NOW)
        with self.assertRaises(VerifierExecutionAdmissionError): g.admit(a,now=NOW)

if __name__=="__main__": unittest.main()
