import unittest
from unittest.mock import patch

from cyber_lion.contracts.builder_entry_permit import BUILDER_CAPABILITY_CLASS, TrustedBuilderSubject
from cyber_lion.contracts.build_authorization_consumption import BuildAuthorizationConsumptionPermit, SCHEMA_VERSION as CVER, compute_consumption_replay_digest
from cyber_lion.contracts.candidate_build_authorization import TrustedRepositoryBaseline
from cyber_lion.enterprise.builder_entry_permit import BuilderEntryPermitEngine, BuilderEntryPermitError, TrustedBuilderSubjectSource
from cyber_lion.enterprise.candidate_build_authorization import LiveAdmittedResourceAuthority, LiveResourceAuthorityAdmission

D=lambda c:c*64
S=lambda c:c*40
REPO="DonkeyJJLove/ai_platform"
MASTER="f51bd8aa90a6040ca77f3b1f28b2f7c5a7499639"
TREE="efde6fce25cf92fe0193faf3a4a24039f30a0c2b"
SCOPE=("cyber_lion/example.py",)
RES=(f"repo-path:{REPO}:cyber_lion/example.py",)
NOW="2026-08-25T01:30:00+00:00"


def live_receipt():
    return LiveAdmittedResourceAuthority(repository=REPO,mission_id="E004",grant_id="grant-R17",action="BUILD_CANDIDATE",resource_scope=RES,lineage_digest=D("3"),provenance_id="prov-R17",epoch=4,epoch_state_version=9,authority_ceiling="local_write",root_grant_id="root-R17",root_grant_digest=D("4"),authenticated_grant_digests=(D("1"),D("2")),leaf_key_id="key-R17",leaf_algorithm="ed25519",replay_digest=D("9"),admitted_at="2026-08-25T01:00:00+00:00")

def baseline(sha=MASTER,tree=TREE,observed="2026-08-25T01:20:00+00:00"):
    return TrustedRepositoryBaseline(REPO,sha,tree,observed)

def source_permit(live=None):
    live=live or live_receipt(); base=baseline()
    kw=dict(authorization_id="cba:"+D("a"),authorization_digest=D("b"),issuance_replay_digest=D("a"),repository=REPO,baseline_master_sha=MASTER,baseline_master_tree_sha=TREE,baseline_observation_digest=D("c"),current_baseline_digest=base.digest(),candidate_scope=SCOPE,resource_scope=RES,action="BUILD_CANDIDATE",grant_id="grant-R17",leaf_grant_digest=D("2"),authority_lineage_digest=D("3"),authority_provenance_id="prov-R17",authority_epoch=4,authority_state_version=9,root_grant_id="root-R17",root_grant_digest=D("4"),live_admission_digest=D("d"),current_authority_digest=live.digest(),authorization_valid_from="2026-08-25T00:00:00+00:00",authorization_expires_at="2026-08-26T00:00:00+00:00")
    replay=compute_consumption_replay_digest(**kw)
    return BuildAuthorizationConsumptionPermit(schema_version=CVER,consumption_permit_id="cbcp:"+replay,checked_at="2026-08-25T01:20:00+00:00",consumption_replay_digest=replay,**kw).sealed()

def builder_subject(instance="instance-01"):
    return TrustedBuilderSubject(builder_subject_id="builder-R17",builder_instance_id=instance,capability_class=BUILDER_CAPABILITY_CLASS,repository=REPO,candidate_scope=SCOPE,resource_scope=RES,identity_digest=D("5"),implementation_digest=D("6"),attestation_digest=D("7"),valid_from="2026-08-25T00:00:00+00:00",expires_at="2026-08-26T00:00:00+00:00").sealed()

class BaselineSource:
    def __init__(self,value): self.value=value
    def current(self,repository): return self.value
class F005:
    def __init__(self,state="QUARANTINED",effect="DENY"): self.value={"state":state,"effect_authority":effect}
    def current(self): return self.value
class Replay:
    def __init__(self): self.seen=set(); self.calls=0
    def consume(self,digest,*,consumed_at):
        self.calls+=1
        if digest in self.seen: return False
        self.seen.add(digest); return True
class Builders(TrustedBuilderSubjectSource):
    def __init__(self,records,kind="trusted-control-plane"): self.records=records; self.source_kind=kind
    def _lookup_exact(self,**kwargs): return self.records

def engine(*,base=None,f005=None,builders=None,replay=None):
    live=object.__new__(LiveResourceAuthorityAdmission)
    return BuilderEntryPermitEngine(live_authority=live,baseline_source=BaselineSource(base or baseline()),f005_state_source=f005 or F005(),builder_source=builders or Builders((builder_subject(),)),replay_guard=replay or Replay()),live

class BuilderEntryPermitEngineTests(unittest.TestCase):
    def test_issues_non_effectful_exact_builder_bound_permit(self):
        lr=live_receipt(); e,live=engine()
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            p=e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(p.builder_subject_id,"builder-R17"); self.assertEqual(p.builder_instance_id,"instance-01"); self.assertEqual(p.builder_capability_class,BUILDER_CAPABILITY_CLASS)
        self.assertEqual((p.authority_effect,p.execution_effect,p.repository_ref_effect,p.external_effect),("NONE","NONE","NONE","NONE")); p.validate()

    def test_duplicate_entry_is_denied(self):
        lr=live_receipt(); replay=Replay(); e,_=engine(replay=replay); src=source_permit(lr); now=__import__("datetime").datetime.fromisoformat(NOW)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            e.issue_permit(source_permit=src,admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=now)
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=src,admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=now)

    def test_baseline_drift_fails_before_replay(self):
        lr=live_receipt(); replay=Replay(); e,_=engine(base=baseline(S("e"),TREE),replay=replay)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls,0)

    def test_builder_authentication_failures_do_not_burn_replay(self):
        lr=live_receipt(); now=__import__("datetime").datetime.fromisoformat(NOW)
        for builders in (Builders(()),Builders((builder_subject(),builder_subject())),Builders((builder_subject(),),kind="caller-self-asserted")):
            replay=Replay(); e,_=engine(builders=builders,replay=replay)
            with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
                with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=now)
            self.assertEqual(replay.calls,0)

    def test_builder_instance_substitution_is_denied_before_replay(self):
        lr=live_receipt(); replay=Replay(); e,_=engine(builders=Builders((builder_subject("instance-01"),)),replay=replay)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-02",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls,0)

    def test_f005_injection_fails_before_replay(self):
        lr=live_receipt(); replay=Replay(); e,_=engine(f005=F005("ACTIVE","ALLOW"),replay=replay)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls,0)

    def test_authority_drift_and_expired_builder_fail(self):
        lr=live_receipt(); drift=LiveAdmittedResourceAuthority(**{**lr.__dict__,"epoch_state_version":10}); replay=Replay(); e,_=engine(replay=replay)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=drift):
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls,0)
        expired=TrustedBuilderSubject(**{**builder_subject().__dict__,"expires_at":"2026-08-25T01:00:00+00:00","subject_digest":""}).sealed(); replay=Replay(); e,_=engine(builders=Builders((expired,)),replay=replay)
        with patch.object(LiveResourceAuthorityAdmission,"revalidate",return_value=lr):
            with self.assertRaises(BuilderEntryPermitError): e.issue_permit(source_permit=source_permit(lr),admitted_authority=lr,builder_subject_id="builder-R17",builder_instance_id="instance-01",trusted_now=__import__("datetime").datetime.fromisoformat(NOW))
        self.assertEqual(replay.calls,0)

    def test_no_effect_surface(self): BuilderEntryPermitEngine.assert_no_effect_surface()

if __name__=="__main__": unittest.main()
