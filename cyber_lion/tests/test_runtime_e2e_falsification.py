import inspect
import unittest
from datetime import datetime,timezone
from hashlib import sha256

from cyber_lion.contracts.executor_sandbox import SandboxExecutionReceipt
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission,RuntimeIdentityBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding,RuntimeExecutionRequest
from cyber_lion.contracts.runtime_reconciliation import RuntimeEffectObservation,RuntimeObserverTrustBinding
from cyber_lion.enterprise.executor_sandbox import SandboxExecutionResult
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_currentness import EffectTimeCurrentnessGuardedSandbox,RuntimeCurrentnessError
from cyber_lion.enterprise.runtime_execution import InMemoryAdmissionConsumptionGuard,RuntimeExecutionEngine,RuntimeExecutionError
from cyber_lion.enterprise.runtime_reconciliation import RuntimeReconciler,RuntimeReconciliationError

Z="0"*64
F="f"*64
PAYLOAD=b"x"
PD=sha256(PAYLOAD).hexdigest()
NOW=datetime(2026,8,23,14,10,tzinfo=timezone.utc)
POLICY="policy@1:sha256:"+Z


def authority():
    return LiveAdmittedAuthority(
        repository="DonkeyJJLove/ai_platform",pr_number=1,base_sha="a"*40,head_sha="b"*40,
        mission_id="mission:1",grant_id="grant:1",lineage_digest=Z,provenance_id="prov",
        epoch=1,epoch_state_version=1,authority_ceiling="local_write",root_grant_id="grant:1",
        root_grant_digest=Z,authenticated_grant_digests=(Z,),leaf_key_id="key",leaf_algorithm="ed25519",
        replay_digest=Z,admitted_at="2026-08-23T14:00:00+00:00",
    ).validate()


def identity():
    return RuntimeIdentityBinding("drone:1","executor:1","runtime:1","sandbox:1","workspace:1",Z,Z).validate()


def effect(i=None):
    i=i or identity()
    return RequestedRuntimeEffect(
        "effect:1","proposal:1","mission:1",POLICY,Z,"local_write","WRITE_FILE","workspace/out.txt",PD,"HEALTHY",i.digest()
    ).validate()


def admission(a=None,e=None,i=None):
    a=a or authority();i=i or identity();e=e or effect(i)
    return RuntimeAdmission(
        "admission:1","request:1","gate:1",e.proposal_id,Z,Z,Z,a.digest(),a.lineage_digest,
        e.policy_binding,e.requested_authority,e.digest(),i.digest(),i.provisioned_executor_digest,"HEALTHY",Z
    ).sealed()


def request(a=None,e=None,i=None):
    i=i or identity();e=e or effect(i);a=a or admission(e=e,i=i)
    return RuntimeExecutionRequest(
        execution_id="exec:1",admission_digest=a.admission_digest,requested_effect_digest=e.digest(),
        runtime_identity_digest=i.digest(),provisioned_executor_digest=i.provisioned_executor_digest,
        mission_id=e.mission_id,executor_id=i.execution_subject,runtime_instance_id=i.runtime_instance_id,
        sandbox_id=i.sandbox_id,workspace_id=i.workspace_id,dispatch_id=Z,fencing_token=F,generation=1,
        action=e.action_class,resource=e.resource,payload_digest=e.payload_digest,payload_size=len(PAYLOAD),command=(),
    ).validate()


class LiveAdmission(LiveAuthorityAdmission):
    def __init__(self,*,revoked=False,changed=False):self.revoked=revoked;self.changed=changed
    def revalidate(self,a,*,now):
        if self.revoked:raise RuntimeError("revoked")
        if self.changed:return LiveAdmittedAuthority(**{**a.__dict__,"epoch_state_version":a.epoch_state_version+1})
        return a


class CurrentnessSource:
    source_id="current";source_instance_id="current:1";implementation_digest=Z;trust_anchor_id="current-anchor";trust_anchor_digest=Z
    def __init__(self,a,*,policy=POLICY,obs="HEALTHY",fail=False):self.a=a;self.policy=policy;self.obs=obs;self.fail=fail
    def resolve_authority(self,_):
        if self.fail:raise RuntimeError("source lost")
        return self.a
    def current_policy_binding(self,_):
        if self.fail:raise RuntimeError("source lost")
        return self.policy
    def current_observability_state(self,*_):
        if self.fail:raise RuntimeError("source lost")
        return self.obs


def currentness_trust():
    return CurrentnessSourceTrustBinding("current","current:1",Z,"current-anchor",Z).validate()


class InnerSandbox:
    policy_digest=Z
    def __init__(self,*,outcome="SUCCEEDED",lie_identity=False,missing_observation=False):
        self.outcome=outcome;self.lie_identity=lie_identity;self.missing_observation=missing_observation;self.calls=0
    def execute(self,op,*,payload=b""):
        self.calls+=1
        executor="executor:lie" if self.lie_identity else op.executor_id
        events=() if self.missing_observation else (("effect-observed",) if self.outcome=="SUCCEEDED" else ("aborted",))
        refs=("side:write",) if self.outcome=="SUCCEEDED" else ()
        effect_digest=op.payload_digest if self.outcome=="SUCCEEDED" else Z
        receipt=SandboxExecutionReceipt(
            "sandbox:"+op.operation_id,op.operation_id,op.digest(),self.policy_digest,Z,Z,Z,Z,
            op.mission_id,op.drone_id,executor,op.sandbox_id,op.workspace_id,op.dispatch_id,op.fencing_token,
            op.generation,"runtime:1",Z,op.action,self.outcome,effect_digest,Z,0,
            len(payload) if op.action=="WRITE_FILE" else 0,None,events,refs,
        )
        return SandboxExecutionResult(receipt,b"")


class AdmissionSource:
    source_id="admission";source_instance_id="admission:1";implementation_digest=Z;trust_anchor_id="admission-anchor";trust_anchor_digest=Z
    def __init__(self,a,*,current=True):self.a=a;self.current=current
    def resolve(self,_):return self.a
    def is_current(self,_):return self.current


def admission_trust():
    return RuntimeAdmissionSourceTrustBinding("admission","admission:1",Z,"admission-anchor",Z).validate()


class Observer:
    source_id="observer";source_instance_id="observer:1";implementation_digest=Z;trust_anchor_id="observer-anchor";trust_anchor_digest=Z
    def __init__(self,o=None,*,fail=False):self.o=o;self.fail=fail
    def observe(self,_):
        if self.fail:raise RuntimeError("observation unavailable")
        return self.o


def observer_trust():
    return RuntimeObserverTrustBinding("observer","observer:1",Z,"observer-anchor",Z).validate()


def observation_from_receipt(r,*,effect_digest=None,effect_state=None,events=None,refs=None):
    return RuntimeEffectObservation(
        "obs:"+r.execution_id,r.execution_id,r.admission_digest,r.request_digest,r.operation_digest,r.action,r.resource,
        effect_state or r.effect_state,effect_digest or r.effect_digest,events if events is not None else r.observed_events,
        refs if refs is not None else r.side_effect_refs,"observer","observer:1",Z,"observer-anchor",Z,
        "2026-08-23T14:11:00+00:00",
    ).sealed()


class RuntimeE2EFalsificationTests(unittest.TestCase):
    def chain(self,*,revoked=False,changed=False,policy=POLICY,obs="HEALTHY",admission_current=True,inner=None,currentness_fail=False):
        a=authority();i=identity();e=effect(i);adm=admission(a,e,i);req=request(adm,e,i);inner=inner or InnerSandbox()
        guard=EffectTimeCurrentnessGuardedSandbox(
            inner=inner,admission=adm,effect=e,runtime_identity=i,
            authority_admission=LiveAdmission(revoked=revoked,changed=changed),
            currentness_source=CurrentnessSource(a,policy=policy,obs=obs,fail=currentness_fail),
            currentness_trust=currentness_trust(),clock=lambda:NOW,
        )
        engine=RuntimeExecutionEngine(
            admission_source=AdmissionSource(adm,current=admission_current),admission_source_trust=admission_trust(),
            consumption_guard=InMemoryAdmissionConsumptionGuard(),sandbox=guard,
        )
        return a,i,e,adm,req,inner,guard,engine

    def execute(self,c,payload=PAYLOAD):
        _,i,e,adm,req,_,_,eng=c
        return eng.execute(admission=adm,request=req,effect=e,runtime_identity=i,payload=payload)

    def test_exact_chain_effect_currentness_observation_reconciliation_matches(self):
        c=self.chain();r=self.execute(c);self.assertEqual(c[5].calls,1);c[6].last_currentness_evidence.validate()
        obs=observation_from_receipt(r);rec=RuntimeReconciler(observer=Observer(obs),observer_trust=observer_trust(),clock=lambda:NOW)
        out=rec.reconcile(receipt=r,currentness=c[6].last_currentness_evidence)
        self.assertEqual(out.disposition,"MATCHED");self.assertEqual(out.anomaly_codes,())

    def test_authority_revoked_after_admission_before_effect_never_reaches_backend(self):
        c=self.chain(revoked=True);self.assertRaises(RuntimeCurrentnessError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_authority_changed_after_admission_before_effect_never_reaches_backend(self):
        c=self.chain(changed=True);self.assertRaises(RuntimeCurrentnessError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_policy_changed_after_admission_before_effect_never_reaches_backend(self):
        c=self.chain(policy="policy@2:sha256:"+F);self.assertRaises(RuntimeCurrentnessError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_observability_lost_after_admission_before_effect_never_reaches_backend(self):
        c=self.chain(obs="LOST");self.assertRaises(RuntimeCurrentnessError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_currentness_evidence_loss_before_effect_fails_closed(self):
        c=self.chain(currentness_fail=True);self.assertRaises(RuntimeCurrentnessError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_stale_runtime_admission_never_reaches_effect_boundary(self):
        c=self.chain(admission_current=False);self.assertRaises(RuntimeExecutionError,self.execute,c);self.assertEqual(c[5].calls,0)

    def test_replay_cannot_execute_second_effect(self):
        c=self.chain();self.execute(c);self.assertRaises(RuntimeExecutionError,self.execute,c);self.assertEqual(c[5].calls,1)

    def test_payload_substitution_is_denied_before_backend(self):
        c=self.chain();self.assertRaises(RuntimeExecutionError,self.execute,c,b"y");self.assertEqual(c[5].calls,0)

    def test_runtime_backend_identity_lie_is_rejected(self):
        c=self.chain(inner=InnerSandbox(lie_identity=True));self.assertRaises(RuntimeExecutionError,self.execute,c);self.assertEqual(c[5].calls,1)

    def test_effect_without_trustworthy_observation_is_rejected(self):
        c=self.chain(inner=InnerSandbox(missing_observation=True));self.assertRaises(RuntimeExecutionError,self.execute,c);self.assertEqual(c[5].calls,1)

    def test_independent_observer_effect_lie_is_mismatch_not_success(self):
        c=self.chain();r=self.execute(c);obs=observation_from_receipt(r,effect_digest=Z)
        rec=RuntimeReconciler(observer=Observer(obs),observer_trust=observer_trust(),clock=lambda:NOW)
        out=rec.reconcile(receipt=r,currentness=c[6].last_currentness_evidence)
        self.assertEqual(out.disposition,"MISMATCH");self.assertIn("EFFECT_DIGEST_MISMATCH",out.anomaly_codes)

    def test_missing_independent_observer_fails_closed(self):
        c=self.chain();r=self.execute(c);rec=RuntimeReconciler(observer=Observer(fail=True),observer_trust=observer_trust(),clock=lambda:NOW)
        self.assertRaises(RuntimeReconciliationError,rec.reconcile,receipt=r,currentness=c[6].last_currentness_evidence)

    def test_aborted_unknown_cannot_become_success(self):
        c=self.chain(inner=InnerSandbox(outcome="ABORTED"));r=self.execute(c);self.assertEqual(r.outcome,"ABORTED");self.assertEqual(r.effect_state,"UNKNOWN")
        obs=observation_from_receipt(r,effect_state="UNKNOWN",effect_digest=Z,events=r.observed_events,refs=())
        rec=RuntimeReconciler(observer=Observer(obs),observer_trust=observer_trust(),clock=lambda:NOW)
        out=rec.reconcile(receipt=r,currentness=c[6].last_currentness_evidence)
        self.assertEqual(out.disposition,"UNKNOWN");self.assertNotEqual(out.disposition,"MATCHED")

    def test_governor_status_graph_role_and_mosaic_are_not_runtime_permission_inputs(self):
        execute_params=set(inspect.signature(RuntimeExecutionEngine.execute).parameters)
        guard_params=set(inspect.signature(EffectTimeCurrentnessGuardedSandbox.__init__).parameters)
        forbidden={"governor","status","enterprise_graph","graph","role","formation","mosaic"}
        self.assertFalse(execute_params&forbidden);self.assertFalse(guard_params&forbidden)

if __name__=="__main__":unittest.main()
