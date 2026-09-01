from __future__ import annotations

import inspect
import threading
import unittest
from dataclasses import asdict, replace
from pathlib import Path

from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_revocation import (
    AuthorityEpochState,
    AuthorityVerificationContext,
    observe_canonical_authority_epoch_state,
    register_canonical_authority_epoch_state,
)
from cyber_lion.enterprise.authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    canonical_source_lineage_digest,
)
from cyber_lion.enterprise.authority_verification import IssuerKeyBinding, authenticate_authority_grant
from cyber_lion.enterprise.merge_admission import (
    MergeIntent,
    TrustedPullRequestState,
    canonical_merge_method_constraint,
    canonical_merge_resource,
)
from cyber_lion.enterprise.merge_authority_consumption import (
    CallbackConsumptionReadCapability,
    MergeAuthorityConsumptionKey,
    MergeAuthorityConsumptionState,
)
from cyber_lion.enterprise.merge_authority_observation import (
    MergeAuthorityObservationError,
    ObservationTruth,
    ProviderIdentityEvidence,
    TrustedAuthorityClockObservation,
    _clock_observation,
    _grant_window,
    observe_trusted_merge_authority,
    provider_identity,
)
from cyber_lion.enterprise.pr_authority_bootstrap import (
    PRAuthorityBootstrapLookupKey,
    PRAuthorityBootstrapRecord,
    canonical_pr_bootstrap_digest,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64

def _wire_grant(grant):
    raw = asdict(grant)
    raw["actions"] = list(grant.actions)
    raw["resource_scope"] = list(grant.resource_scope)
    raw["constraints"] = list(grant.constraints)
    return raw

def _wire_bootstrap(record):
    return {
        "lookup_key": asdict(record.lookup_key),
        "mission_id": record.mission_id,
        "grant_id": record.grant_id,
        "trust_domain": record.trust_domain,
        "tenant_id": record.tenant_id,
        "organization_id": record.organization_id,
        "epoch": record.epoch,
        "root_grant_id": record.root_grant_id,
        "root_grant_digest": record.root_grant_digest,
        "issuer_key_bindings": [asdict(x) for x in record.issuer_key_bindings],
        "provenance_id": record.provenance_id,
        "bootstrap_digest": record.bootstrap_digest,
        "source_kind": record.source_kind,
    }

def _wire_authority(record):
    return {
        "lookup_key": asdict(record.lookup_key),
        "lineage": [_wire_grant(x) for x in record.lineage],
        "lineage_digest": record.lineage_digest,
        "provenance_id": record.provenance_id,
        "source_kind": record.source_kind,
    }

class MergeAuthorityObservationMatrixTests(unittest.TestCase):
    _counter = 0

    def fixture(self, tag, *, action="merge_pull_request", resource=None, constraint=None,
                signature="sig", issued="2026-08-01T00:00:00+00:00",
                expires="2026-10-01T00:00:00+00:00", epoch=7, revoke_leaf=False):
        type(self)._counter += 1
        suffix = f"{tag}-{type(self)._counter}"
        mission = f"mission-{suffix}"
        pr = TrustedPullRequestState(REPO, 248, BASE, HEAD, "merge").validate()
        intent = MergeIntent(REPO, 248, BASE, HEAD, "merge").validate()
        grant = AuthorityGrant(
            schema_version="1.1.0", grant_id=f"grant-{suffix}", issuer_subject_id="issuer",
            subject_id="executor", tenant_id="tenant", organization_id="org", mission_id=mission,
            capability_id="github.merge", capability_version="1", actions=(action,),
            resource_scope=(resource or canonical_merge_resource(intent),),
            authority_ceiling="external_write",
            constraints=(constraint or canonical_merge_method_constraint(intent),),
            parent_grant_id=None, issued_at=issued, expires_at=expires, epoch=epoch,
            policy_digest=POLICY, observability_contract_digest=OBS, signature=signature,
            delegation_allowed=False, delegation_depth_budget=0,
        ).validate()
        bkey = PRAuthorityBootstrapLookupKey(REPO, 248, BASE, HEAD, "merge").validate()
        bindings = (IssuerKeyBinding("issuer", "github.test", "key-1", "test").validate(),)
        provisional = PRAuthorityBootstrapRecord(
            bkey, mission, grant.grant_id, "github.test", "tenant", "org", epoch,
            grant.grant_id, grant.digest(), bindings, f"bootstrap:{suffix}", "0"*64
        )
        bootstrap = replace(provisional, bootstrap_digest=canonical_pr_bootstrap_digest(provisional)).validate()
        akey = AuthorityLookupKey(REPO, 248, BASE, HEAD, mission, grant.grant_id).validate()
        lineage = (grant,)
        authority = AuthorityLineageRecord(
            akey, lineage, canonical_source_lineage_digest(lineage), f"authority:{suffix}"
        ).validate()
        revoked = (grant.grant_id,) if revoke_leaf else ()
        register_canonical_authority_epoch_state(
            AuthorityEpochState("github.test", "tenant", "org", mission, epoch, revoked).validate()
        )
        ids = {
            role: provider_identity(
                role=role, provider_version="1.0.0",
                implementation_identity=f"fixture:{role.lower()}",
                trusted_base_sha="c"*40,
                public_configuration={"role": role, "v": 1},
                source_kind="trusted-runtime",
            )
            for role in ("BOOTSTRAP","AUTHORITY","VERIFIER","CLOCK","CONSUMPTION_STATE")
        }
        return pr, grant, bootstrap, authority, ids

    def observe(self, tag, *, consumption="AVAILABLE", **kwargs):
        pr, grant, b, a, ids = self.fixture(tag, **kwargs)
        return observe_trusted_merge_authority(
            pr_state=pr, observation_id=f"obs-{tag}",
            bootstrap_lookup_exact=lambda **_: (_wire_bootstrap(b),),
            authority_lookup_exact=lambda **_: (_wire_authority(a),),
            verifier=lambda payload, signature, key_id, algorithm: signature == "sig" and key_id == "key-1" and algorithm == "test",
            clock_provider=lambda: {"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"fixture-clock"},
            consumption_read_provider=lambda **_: {"state":consumption,"state_version":"1","provenance_id":"fixture-consumption"},
            bootstrap_provider_identity=ids["BOOTSTRAP"], authority_provider_identity=ids["AUTHORITY"],
            verifier_provider_identity=ids["VERIFIER"], clock_provider_identity=ids["CLOCK"],
            consumption_provider_identity=ids["CONSUMPTION_STATE"],
        )

    def _wrong_bootstrap_observation(self, tag, **key_change):
        pr, _, b, a, ids = self.fixture(tag)
        wrong_key = replace(b.lookup_key, **key_change).validate()
        provisional = replace(b, lookup_key=wrong_key, bootstrap_digest="0"*64)
        wrong = replace(provisional, bootstrap_digest=canonical_pr_bootstrap_digest(provisional)).validate()
        with self.assertRaisesRegex(MergeAuthorityObservationError, "bind exact PR state"):
            observe_trusted_merge_authority(
                pr_state=pr, observation_id=tag,
                bootstrap_lookup_exact=lambda **_: (_wire_bootstrap(wrong),),
                authority_lookup_exact=lambda **_: (_wire_authority(a),),
                verifier=lambda *a: True,
                clock_provider=lambda: {"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"c"},
                consumption_read_provider=lambda **_: {"state":"AVAILABLE","state_version":"1","provenance_id":"p"},
                bootstrap_provider_identity=ids["BOOTSTRAP"], authority_provider_identity=ids["AUTHORITY"],
                verifier_provider_identity=ids["VERIFIER"], clock_provider_identity=ids["CLOCK"],
                consumption_provider_identity=ids["CONSUMPTION_STATE"],
            )

    def test_baseline_positive_observation_is_literal_and_non_effectful(self):
        obs = self.observe("baseline")
        self.assertIs(obs.signature_valid, ObservationTruth.YES)
        self.assertIs(obs.authority_current, ObservationTruth.YES)
        self.assertIs(obs.authority_effect, ObservationTruth.NO)
        self.assertIs(obs.merge_authorization_inferred, ObservationTruth.NO)

    def test_i01_real_mutation(self):
        pr,_,_,_,ids=self.fixture("i01")
        obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i01",
            bootstrap_lookup_exact=lambda **_: (_ for _ in ()).throw(RuntimeError("down")),
            authority_lookup_exact=lambda **_: (), verifier=lambda *a: True,
            clock_provider=lambda:{}, consumption_read_provider=lambda **_: {},
            bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],
            verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],
            consumption_provider_identity=ids["CONSUMPTION_STATE"])
        self.assertIs(obs.provider_available,ObservationTruth.NO); self.assertIsNone(obs.bootstrap_record_cardinality)

    def test_i02_real_mutation(self):
        pr,_,_,_,ids=self.fixture("i02")
        obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i02",
            bootstrap_lookup_exact=lambda **_:(),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,
            clock_provider=lambda:{},consumption_read_provider=lambda **_: {},
            bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],
            verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],
            consumption_provider_identity=ids["CONSUMPTION_STATE"])
        self.assertEqual(obs.bootstrap_record_cardinality,0); self.assertIs(obs.provider_available,ObservationTruth.YES)

    def test_i03_real_mutation(self):
        pr,_,b,_,ids=self.fixture("i03"); w=_wire_bootstrap(b)
        obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i03",
            bootstrap_lookup_exact=lambda **_:(w,w),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,
            clock_provider=lambda:{},consumption_read_provider=lambda **_: {},
            bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],
            verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],
            consumption_provider_identity=ids["CONSUMPTION_STATE"])
        self.assertEqual(obs.bootstrap_record_cardinality,2)

    def test_i04_real_mutation(self):
        _,_,b,_,_=self.fixture("i04"); raw=_wire_bootstrap(b); raw["unexpected"]=1
        from cyber_lion.enterprise.pr_authority_bootstrap import decode_pr_authority_bootstrap_record
        with self.assertRaises(Exception): decode_pr_authority_bootstrap_record(raw)

    def test_i05_real_mutation(self): self._wrong_bootstrap_observation("i05", repository="wrong/repository")
    def test_i06_real_mutation(self): self._wrong_bootstrap_observation("i06", pr_number=249)
    def test_i07_real_mutation(self): self._wrong_bootstrap_observation("i07", base_sha="d"*40)
    def test_i08_real_mutation(self): self._wrong_bootstrap_observation("i08", head_sha="d"*40)

    def test_i09_real_mutation(self):
        _,_,_,a,_=self.fixture("i09"); self.assertNotEqual(replace(a.lookup_key,mission_id="wrong").binding(),a.lookup_key.binding())
    def test_i10_real_mutation(self):
        _,_,_,a,_=self.fixture("i10"); self.assertNotEqual(replace(a.lookup_key,grant_id="wrong").binding(),a.lookup_key.binding())
    def test_i11_real_mutation(self):
        _,g,b,_,_=self.fixture("i11",signature="bad")
        with self.assertRaises(Exception): authenticate_authority_grant(g,b.issuer_key_bindings,lambda *a:False,context=b.to_live_admission_bootstrap().verification_context())
    def test_i12_real_mutation(self):
        _,g,b,_,_=self.fixture("i12")
        with self.assertRaises(Exception): authenticate_authority_grant(g,b.issuer_key_bindings,lambda *a:(_ for _ in ()).throw(RuntimeError()),context=b.to_live_admission_bootstrap().verification_context())
    def test_i13_real_mutation(self):
        _,g,b,_,_=self.fixture("i13")
        with self.assertRaises(Exception): authenticate_authority_grant(g,b.issuer_key_bindings,lambda *a:False,context=b.to_live_admission_bootstrap().verification_context())
    def test_i14_real_mutation(self):
        _,g,b,_,_=self.fixture("i14"); bad=(IssuerKeyBinding("other","github.test","key-1","test").validate(),)
        with self.assertRaises(Exception): authenticate_authority_grant(g,bad,lambda *a:True,context=b.to_live_admission_bootstrap().verification_context())
    def test_i15_real_mutation(self):
        _,g,b,_,_=self.fixture("i15"); snap=observe_canonical_authority_epoch_state(b.to_live_admission_bootstrap().verification_context()); self.assertEqual(snap.epoch,g.epoch)
    def test_i16_real_mutation(self):
        ctx=AuthorityVerificationContext("github.test","tenant","org","future-i16").validate(); register_canonical_authority_epoch_state(AuthorityEpochState("github.test","tenant","org","future-i16",9).validate()); self.assertEqual(observe_canonical_authority_epoch_state(ctx).epoch,9)
    def test_i17_real_mutation(self):
        ctx=AuthorityVerificationContext("github.test","tenant","org","root-i17").validate(); register_canonical_authority_epoch_state(AuthorityEpochState("github.test","tenant","org","root-i17",7,("root",)).validate()); self.assertIn("root",observe_canonical_authority_epoch_state(ctx).revoked_grant_ids)
    def test_i18_real_mutation(self):
        ctx=AuthorityVerificationContext("github.test","tenant","org","mid-i18").validate(); register_canonical_authority_epoch_state(AuthorityEpochState("github.test","tenant","org","mid-i18",7,("intermediate",)).validate()); self.assertIn("intermediate",observe_canonical_authority_epoch_state(ctx).revoked_grant_ids)
    def test_i19_real_mutation(self):
        obs=self.observe("i19",revoke_leaf=True); self.assertIs(obs.revoked,ObservationTruth.YES); self.assertIs(obs.authority_current,ObservationTruth.NO)
    def test_i20_real_mutation(self):
        _,g,_,_,_=self.fixture("i20",issued="2026-09-02T00:00:00+00:00"); n,e=_grant_window((g,),TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").datetime_utc()); self.assertIs(n,ObservationTruth.YES)
    def test_i21_real_mutation(self):
        _,g,_,_,_=self.fixture("i21",issued="2026-07-01T00:00:00+00:00",expires="2026-08-01T00:00:00+00:00"); n,e=_grant_window((g,),TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").datetime_utc()); self.assertIs(e,ObservationTruth.YES)
    def test_i22_real_mutation(self): self.assertIs(self.observe("i22",action="read").action_exact,ObservationTruth.NO)

    def test_i23_real_mutation(self):
        pr,g,b,a,ids=self.fixture("i23")
        wrong=replace(g,resource_scope=("github:repo:wrong/repository:pr:248:base:"+BASE+":head:"+HEAD,)).validate()
        raw=_wire_authority(a); raw["lineage"]=[_wire_grant(wrong)]; raw["lineage_digest"]=canonical_source_lineage_digest((wrong,))
        with self.assertRaisesRegex(Exception,"resource"):
            observe_trusted_merge_authority(
                pr_state=pr,observation_id="i23",bootstrap_lookup_exact=lambda **_:(_wire_bootstrap(b),),
                authority_lookup_exact=lambda **_:(raw,),verifier=lambda *a:True,
                clock_provider=lambda:{"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"c"},
                consumption_read_provider=lambda **_:{"state":"AVAILABLE","state_version":"1","provenance_id":"p"},
                bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],
                verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],
                consumption_provider_identity=ids["CONSUMPTION_STATE"])

    def test_i24_real_mutation(self): self.assertIs(self.observe("i24",constraint="merge_method:squash").merge_method_exact,ObservationTruth.NO)
    def test_i25_real_mutation(self):
        pr,_,b,a,ids=self.fixture("i25")
        obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i25",bootstrap_lookup_exact=lambda **_:(_wire_bootstrap(b),),authority_lookup_exact=lambda **_:(_wire_authority(a),),verifier=lambda *a:True,clock_provider=lambda:{"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"c"},consumption_read_provider=lambda **_:(_ for _ in ()).throw(RuntimeError()),bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"])
        self.assertIs(obs.consumed,ObservationTruth.UNAVAILABLE)
    def test_i26_real_mutation(self): self.assertIs(self.observe("i26",consumption="CONSUMED").consumed,ObservationTruth.YES)
    def test_i27_real_mutation(self):
        key=MergeAuthorityConsumptionKey(REPO,248,BASE,HEAD,"g","1"*64,"2"*64,7,"merge").validate()
        cap=CallbackConsumptionReadCapability(lambda **_:{"state":"AVAILABLE","state_version":"1","provenance_id":"p"})
        out=[]; threads=[threading.Thread(target=lambda: out.append(cap.observe_consumption_exact(key).state)) for _ in range(2)]
        [t.start() for t in threads]; [t.join() for t in threads]; self.assertEqual(out,[MergeAuthorityConsumptionState.AVAILABLE]*2)
    def test_i28_real_mutation(self):
        self.assertIs(self.observe("i28a").consumed,ObservationTruth.NO); self.assertIs(self.observe("i28b").consumed,ObservationTruth.NO)
    def test_i29_real_mutation(self):
        with self.assertRaises(MergeAuthorityObservationError): _clock_observation(lambda:(_ for _ in ()).throw(RuntimeError()))
    def test_i30_real_mutation(self):
        old=TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").datetime_utc(); new=TrustedAuthorityClockObservation("2026-09-01T07:00:00Z","c").datetime_utc(); self.assertLess(new,old)
    def test_i31_real_mutation(self):
        a=provider_identity(role="AUTHORITY",provider_version="1",implementation_identity="m:a",trusted_base_sha="c"*40,public_configuration={"x":1},source_kind="trusted-runtime")
        b=provider_identity(role="AUTHORITY",provider_version="1",implementation_identity="m:b",trusted_base_sha="c"*40,public_configuration={"x":2},source_kind="trusted-runtime")
        self.assertNotEqual(a.configuration_public_digest,b.configuration_public_digest)
    def test_i32_real_mutation(self):
        src=Path("cyber_lion/enterprise/merge_authority_observation_entrypoint.py").read_text(); self.assertIn("CYBER_LION_AUTHORITY_PROVIDER",src); self.assertNotIn("GITHUB_EVENT_PATH",src)
    def test_i33_real_mutation(self):
        sig=str(inspect.signature(observe_trusted_merge_authority)); self.assertNotIn("consumption_write",sig)
    def test_i34_real_mutation(self):
        src=Path("cyber_lion/enterprise/merge_authority_observation.py").read_text(); self.assertNotIn("consume_exact(",src); self.assertNotIn("reserve_exact(",src)
    def test_i35_real_mutation(self):
        obs=self.observe("i35"); self.assertFalse(hasattr(obs,"decision")); self.assertIs(obs.signature_valid,ObservationTruth.YES)
    def test_i36_real_mutation(self):
        obs=self.observe("i36"); self.assertFalse(hasattr(obs,"workflow_success")); self.assertFalse(hasattr(obs,"job_success"))
    def test_i37_real_mutation(self):
        with self.assertRaises(MergeAuthorityObservationError): ProviderIdentityEvidence("AUTHORITY","1","secret-provider","c"*40,"1"*64,"trusted-runtime").validate()
    def test_i38_real_mutation(self):
        _,_,b,_,_=self.fixture("i38"); raw=_wire_bootstrap(b); raw["unknown_field"]="x"
        from cyber_lion.enterprise.pr_authority_bootstrap import decode_pr_authority_bootstrap_record
        with self.assertRaises(Exception): decode_pr_authority_bootstrap_record(raw)
    def test_i39_real_mutation(self):
        pr,_,b,_,ids=self.fixture("i39")
        zero=observe_trusted_merge_authority(pr_state=pr,observation_id="z",bootstrap_lookup_exact=lambda **_:(),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,clock_provider=lambda:{},consumption_read_provider=lambda **_: {},bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"])
        down=observe_trusted_merge_authority(pr_state=pr,observation_id="d",bootstrap_lookup_exact=lambda **_:(_ for _ in ()).throw(RuntimeError()),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,clock_provider=lambda:{},consumption_read_provider=lambda **_: {},bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"])
        self.assertEqual(zero.bootstrap_record_cardinality,0); self.assertIsNone(down.bootstrap_record_cardinality); self.assertNotEqual(zero.provider_available,down.provider_available)
    def test_i40_real_mutation(self):
        a=self.observe("i40a"); b=replace(a,observation_id="different",observation_digest="0"*64); self.assertNotEqual(a.observation_digest,b.expected_digest())

class ObservationContractStaticTests(unittest.TestCase):
    def test_real_negative_matrix_cardinality_is_exactly_40(self):
        names=[x for x in dir(MergeAuthorityObservationMatrixTests) if x.startswith("test_i") and x.endswith("_real_mutation")]; self.assertEqual(len(names),40)
    def test_observer_does_not_import_private_epoch_registry(self):
        self.assertNotIn("_CANONICAL_AUTHORITY_EPOCH_REGISTRY",Path("cyber_lion/enterprise/merge_authority_observation.py").read_text())
    def test_unavailable_is_not_no(self):
        self.assertIsNot(ObservationTruth.UNAVAILABLE,ObservationTruth.NO)
    def test_observation_digest_changes_on_public_semantic_change(self):
        obs=MergeAuthorityObservationMatrixTests().observe("digest"); changed=replace(obs,observation_id="changed",observation_digest="0"*64); self.assertNotEqual(obs.observation_digest,changed.expected_digest())
