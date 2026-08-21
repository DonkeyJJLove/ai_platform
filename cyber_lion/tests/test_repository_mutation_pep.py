from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import inspect,tempfile,unittest
from unittest.mock import patch
from cyber_lion.contracts.repository_mutation import *
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.live_authority_admission import LiveAdmittedAuthority,LiveAuthorityAdmission,LiveAuthorityAdmissionError
from cyber_lion.enterprise.repository_mutation_pep import RepositoryMutationPEP,RepositoryMutationPEPError
import cyber_lion.enterprise.repository_mutation_state as state_module

HEAD="a"*40; COMMIT="b"*40; TREE="c"*40; REPO="DonkeyJJLove/ai_platform"; BRANCH="mission/lion-fleet-control-plane-v0"; MISSION="R2"
VER=TrustedVerifierPin("verifier-1","1"*64,"2"*64,"source","3"*64,"4"*64).validate()
EFFECT=TrustedDependencyPin("cas","5"*64,"6"*64,"7"*64).validate()
OBS=TrustedDependencyPin("observer","8"*64,"9"*64,"a"*64).validate()
CLOCK=TrustedDependencyPin("clock","b"*64,"c"*64,"d"*64).validate()
RUNTIME=TrustedDependencyPin("runtime-1","e"*64,"f"*64,"1"*64).validate()

class Source(CandidateVerificationSource):
    source_id="source"; source_identity_digest="3"*64; source_implementation_digest="4"*64
    def __init__(self,recs): self.recs=recs
    def _lookup_exact(self,d): return self.recs
class Backend:
    def __init__(self): self.head=HEAD
class Effect:
    dependency_id="cas"; identity_digest="5"*64; implementation_digest="6"*64
    def __init__(self,b,events=None,status="APPLIED",apply=True): self.b=b; self.events=events; self.status=status; self.apply=apply; self.calls=0
    def compare_and_swap_fast_forward(self,**kw):
        self.calls+=1
        if self.events is not None:self.events.append("cas")
        if self.b.head!=kw["expected_old_sha"]: return AttachProviderResult("FAILED_NO_EFFECT",self.dependency_id)
        if self.apply:self.b.head=kw["candidate_commit_sha"]
        return AttachProviderResult(self.status,self.dependency_id)
class Observer:
    dependency_id="observer"; identity_digest="8"*64; implementation_digest="9"*64
    def __init__(self,b,events=None,fail_on=()): self.b=b; self.events=events; self.calls=0; self.fail_on=set(fail_on)
    def observe_ref(self,*,repository,branch):
        self.calls+=1
        if self.events is not None:self.events.append("observe")
        if self.calls in self.fail_on: raise RuntimeError("obs")
        return TrustedRefState(repository,branch,self.b.head,f"t{self.calls}").validate()
class Clock:
    dependency_id="clock"; identity_digest="b"*64; implementation_digest="c"*64
    def __init__(self,times,events=None): self.times=list(times); self.events=events; self.calls=0
    def now(self):
        self.calls+=1
        if self.events is not None:self.events.append("clock")
        if len(self.times)>1:return self.times.pop(0)
        return self.times[0]
class FakeCAS:
    supports_exact_old_sha_cas=True
    dependency_id="attacker"; identity_digest="0"*64; implementation_digest="0"*64
    def compare_and_swap_fast_forward(self,**kw): raise AssertionError

def candidate():
    return DetachedRepositoryCandidate(REPO,BRANCH,HEAD,HEAD,COMMIT,TREE,("a","b"),"builder","p").validate()
def verified(c):
    return VerifiedDetachedCandidate(c.digest(),REPO,BRANCH,HEAD,HEAD,COMMIT,TREE,changed_paths_digest(c.changed_paths),"verifier-1","1"*64,"2"*64,("e",),"v")
def intent(c,v): return ExactRefAttachIntent(REPO,BRANCH,MISSION,HEAD,HEAD,COMMIT,TREE,v.digest()).validate()
def make_grant(i,runtime=RUNTIME):
    return AuthorityGrant("1.1.0","g","iss","sub","t","o",MISSION,"github.ref.attach","1",("fast_forward_ref",),(canonical_attach_resource(i),),"external_write",("force:false","single_effect:true",canonical_verification_constraint(i),f"runtime_scope:{runtime.digest()}"),None,"2026-08-20T00:00:00+00:00","2026-08-22T00:00:00+00:00",1,"sha256:"+"3"*64,"sha256:"+"4"*64,"sig").validate()
def admitted(g):
    return LiveAdmittedAuthority(REPO,41,"1"*40,HEAD,MISSION,g.grant_id,"5"*64,"p",1,1,"external_write",g.grant_id,"6"*64,(g.digest(),),"k","alg","7"*64,"2026-08-21T00:00:00+00:00").validate()

VALID=datetime(2026,8,21,0,10,tzinfo=timezone.utc)
EXPIRED=datetime(2026,8,23,0,10,tzinfo=timezone.utc)
EARLY=datetime(2026,8,19,0,10,tzinfo=timezone.utc)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.pp=patch.object(state_module,"CANONICAL_REPOSITORY_ATTACH_JOURNAL_PATH",self.tmp.name+"/j.db"); self.pp.start()
        self.c=candidate(); self.v=verified(self.c); self.i=intent(self.c,self.v); self.g=make_grant(self.i); self.a=admitted(self.g)
        self.live=object.__new__(LiveAuthorityAdmission); self.b=Backend(); self.e=Effect(self.b); self.o=Observer(self.b); self.clock=Clock([VALID,VALID,VALID])
    def tearDown(self): self.pp.stop(); self.tmp.cleanup()
    def pep(self,*,clock=None,effect=None,observer=None,runtime=RUNTIME,source=None):
        return RepositoryMutationPEP(live_admission=self.live,verification_source=source or Source((self.v,)),verifier_pin=VER,
          effect_port=effect or self.e,effect_pin=EFFECT,observer=observer or self.o,observer_pin=OBS,
          clock=clock or self.clock,clock_pin=CLOCK,runtime_scope_pin=runtime)
    def admit_ok(self,p):
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            return p.admit(intent=self.i,candidate=self.c,admitted=self.a,authority_leaf=self.g,admission_id="adm",effect_id="eff")
    def test_operation_caller_cannot_supply_time_or_dependencies(self):
        for method in (RepositoryMutationPEP.admit,RepositoryMutationPEP.execute):
            ps=inspect.signature(method).parameters
            for forbidden in ("now","prepared_at","attempted_at","finalized_at","clock","verification_source","provider","journal"):
                self.assertNotIn(forbidden,ps)
    def test_self_declared_cas_denied(self):
        with self.assertRaises(RepositoryMutationPEPError): self.pep(effect=FakeCAS())
    def test_journal_classified_single_runtime(self):
        p=self.pep(); self.assertEqual(p.journal_scope_class,"SINGLE_RUNTIME_ATTACH_ONLY")
        self.assertEqual(p.runtime_scope_constraint,f"runtime_scope:{RUNTIME.digest()}")
    def test_runtime_scope_constraint_required(self):
        bad=replace(self.g,constraints=tuple(x for x in self.g.constraints if not x.startswith("runtime_scope:")))
        bad_a=admitted(bad); p=self.pep()
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=bad_a):
            d=p.admit(intent=self.i,candidate=self.c,admitted=bad_a,authority_leaf=bad,admission_id="adm",effect_id="eff")
        self.assertEqual(d.decision,"DENY")
    def test_trusted_clock_used_at_admit_not_yet_valid_denied(self):
        p=self.pep(clock=Clock([EARLY]))
        def rv(_self,a,*,now):
            if now < VALID: raise LiveAuthorityAdmissionError("not yet valid")
            return a
        with patch.object(LiveAuthorityAdmission,"revalidate",new=rv):
            d=p.admit(intent=self.i,candidate=self.c,admitted=self.a,authority_leaf=self.g,admission_id="adm",effect_id="eff")
        self.assertEqual(d.decision,"DENY")
    def test_expired_grant_cannot_be_reanimated(self):
        clock=Clock([VALID,EXPIRED]); p=self.pep(clock=clock); d=self.admit_ok(p)
        def rv(_self,a,*,now):
            if now>=EXPIRED: raise LiveAuthorityAdmissionError("expired")
            return a
        with patch.object(LiveAuthorityAdmission,"revalidate",new=rv):
            with self.assertRaises(LiveAuthorityAdmissionError):
                p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertEqual(self.e.calls,0)
    def test_fresh_clock_read_immediately_before_effect(self):
        events=[]; b=Backend(); e=Effect(b,events); o=Observer(b,events); c=Clock([VALID,VALID,VALID],events); p=self.pep(clock=c,effect=e,observer=o); d=self.admit_ok(p); events.clear()
        def rv(_self,a,*,now): events.append("revalidate"); return a
        with patch.object(LiveAuthorityAdmission,"revalidate",new=rv):
            p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertEqual(events[:6],["observe","clock","revalidate","clock","revalidate","cas"])
    def test_runtime_binding_restart_safe(self):
        p1=self.pep(); d=self.admit_ok(p1)
        alt=TrustedDependencyPin("runtime-2","e"*64,"f"*64,"2"*64).validate()
        p2=self.pep(runtime=alt)
        with self.assertRaises(RepositoryMutationPEPError):
            p2.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertEqual(self.e.calls,0)
    def test_success_requires_post_effect_observation(self):
        p=self.pep(); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            r=p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertIsNotNone(r); self.assertEqual(p._journal.get("eff").status,"APPLIED")
    def test_failed_no_effect_requires_observation(self):
        b=Backend(); e=Effect(b,status="FAILED_NO_EFFECT",apply=False); o=Observer(b,fail_on={3}); p=self.pep(effect=e,observer=o); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            r=p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertIsNone(r); self.assertEqual(p._journal.get("eff").status,"RECONCILE_REQUIRED")
    def test_observed_failed_no_effect_terminal(self):
        b=Backend(); e=Effect(b,status="FAILED_NO_EFFECT",apply=False); o=Observer(b); p=self.pep(effect=e,observer=o); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertEqual(p._journal.get("eff").status,"FAILED_NO_EFFECT")
    def test_crash_reconcile_first_no_second_cas(self):
        p=self.pep(); d=self.admit_ok(p); p._journal.mark_attempted("eff",attempted_at="x")
        r=p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertIsNone(r); self.assertEqual(self.e.calls,0); self.assertEqual(p._journal.get("eff").status,"RECONCILE_REQUIRED")
    def test_final_revocation_blocks_before_effect(self):
        p=self.pep(); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",side_effect=[self.a,LiveAuthorityAdmissionError("revoked")]):
            with self.assertRaises(LiveAuthorityAdmissionError):
                p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertEqual(self.e.calls,0); self.assertEqual(p._journal.get("eff").status,"RECONCILE_REQUIRED")
    def test_forged_admission_denied(self):
        p=self.pep(); d=self.admit_ok(p); f=replace(d,verification_digest="f"*64)
        with self.assertRaises(RepositoryMutationPEPError):
            p.execute(admission=f,intent=self.i,admitted=self.a,authority_leaf=self.g)
    def test_unknown_old_head_reconcile(self):
        b=Backend(); e=Effect(b,status="UNKNOWN",apply=False); o=Observer(b); p=self.pep(effect=e,observer=o); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            r=p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertIsNone(r); self.assertEqual(p._journal.get("eff").status,"RECONCILE_REQUIRED")
    def test_wrong_post_effect_head_reconcile(self):
        class Wrong(Effect):
            def compare_and_swap_fast_forward(self,**kw):
                self.calls+=1; self.b.head="d"*40; return AttachProviderResult("APPLIED",self.dependency_id)
        b=Backend(); e=Wrong(b); o=Observer(b); p=self.pep(effect=e,observer=o); d=self.admit_ok(p)
        with patch.object(LiveAuthorityAdmission,"revalidate",return_value=self.a):
            r=p.execute(admission=d,intent=self.i,admitted=self.a,authority_leaf=self.g)
        self.assertIsNone(r); self.assertEqual(p._journal.get("eff").status,"RECONCILE_REQUIRED")
if __name__=="__main__": unittest.main()
