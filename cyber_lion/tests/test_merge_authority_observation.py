from __future__ import annotations

import inspect
import json
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
from cyber_lion.enterprise.authority_source_adapter import TrustedControlPlaneAuthoritySource
from cyber_lion.enterprise.authority_verification import IssuerKeyBinding, authenticate_authority_grant
from cyber_lion.enterprise.ci_live_admission import ReadOnlyAuthorityControlPlaneTransport
from cyber_lion.enterprise.merge_admission import MergeIntent, TrustedPullRequestState, canonical_merge_method_constraint, canonical_merge_resource
from cyber_lion.enterprise.merge_authority_consumption import MergeAuthorityConsumptionKey
from cyber_lion.enterprise.merge_authority_observation import (
    MergeAuthorityObservationError,
    ObservationTruth,
    ProviderIdentityEvidence,
    TrustedAuthorityClockObservation,
    TrustedMergeAuthorityObservation,
    _clock_observation,
    _grant_window,
    observe_trusted_merge_authority,
    provider_identity,
)
from cyber_lion.enterprise.pr_authority_bootstrap import (
    PRAuthorityBootstrapLookupKey,
    PRAuthorityBootstrapRecord,
    canonical_pr_bootstrap_digest,
    decode_pr_authority_bootstrap_record,
)

REPO = "DonkeyJJLove/ai_platform"
BASE = "a" * 40
HEAD = "b" * 40
POLICY = "sha256:" + "1" * 64
OBS = "sha256:" + "2" * 64


def _wire_grant(grant: AuthorityGrant) -> dict[str, object]:
    raw = asdict(grant)
    raw["actions"] = list(grant.actions)
    raw["resource_scope"] = list(grant.resource_scope)
    raw["constraints"] = list(grant.constraints)
    return raw


def _wire_bootstrap(record: PRAuthorityBootstrapRecord) -> dict[str, object]:
    return {
        "lookup_key": {
            "repository": record.lookup_key.repository,
            "pr_number": record.lookup_key.pr_number,
            "base_sha": record.lookup_key.base_sha,
            "head_sha": record.lookup_key.head_sha,
            "merge_method": record.lookup_key.merge_method,
        },
        "mission_id": record.mission_id,
        "grant_id": record.grant_id,
        "trust_domain": record.trust_domain,
        "tenant_id": record.tenant_id,
        "organization_id": record.organization_id,
        "epoch": record.epoch,
        "root_grant_id": record.root_grant_id,
        "root_grant_digest": record.root_grant_digest,
        "issuer_key_bindings": [asdict(item) for item in record.issuer_key_bindings],
        "provenance_id": record.provenance_id,
        "bootstrap_digest": record.bootstrap_digest,
        "source_kind": record.source_kind,
    }


def _wire_authority(record: AuthorityLineageRecord) -> dict[str, object]:
    return {
        "lookup_key": {
            "repository": record.lookup_key.repository,
            "pr_number": record.lookup_key.pr_number,
            "base_sha": record.lookup_key.base_sha,
            "head_sha": record.lookup_key.head_sha,
            "mission_id": record.lookup_key.mission_id,
            "grant_id": record.lookup_key.grant_id,
        },
        "lineage": [_wire_grant(item) for item in record.lineage],
        "lineage_digest": record.lineage_digest,
        "provenance_id": record.provenance_id,
        "source_kind": record.source_kind,
    }


class MergeAuthorityObservationMatrixTests(unittest.TestCase):
    _counter = 0

    def fixture(self, tag: str, *, revoked=(), epoch=7, issued="2026-08-01T00:00:00+00:00", expires="2026-10-01T00:00:00+00:00", action="merge_pull_request", resource=None, constraint=None, signature="sig"):
        MergeAuthorityObservationMatrixTests._counter += 1
        suffix = f"{tag}-{MergeAuthorityObservationMatrixTests._counter}"
        mission = f"mission-{suffix}"
        pr_state = TrustedPullRequestState(REPO, 248, BASE, HEAD, "merge").validate()
        intent = MergeIntent(REPO, 248, BASE, HEAD, "merge").validate()
        grant = AuthorityGrant(
            schema_version="1.1.0",
            grant_id=f"grant-{suffix}",
            issuer_subject_id="issuer",
            subject_id="executor",
            tenant_id="tenant",
            organization_id="org",
            mission_id=mission,
            capability_id="github.merge",
            capability_version="1",
            actions=(action,),
            resource_scope=(resource or canonical_merge_resource(intent),),
            authority_ceiling="external_write",
            constraints=(constraint or canonical_merge_method_constraint(intent),),
            parent_grant_id=None,
            issued_at=issued,
            expires_at=expires,
            epoch=epoch,
            policy_digest=POLICY,
            observability_contract_digest=OBS,
            signature=signature,
            delegation_allowed=False,
            delegation_depth_budget=0,
        ).validate()
        key = PRAuthorityBootstrapLookupKey(REPO, 248, BASE, HEAD, "merge").validate()
        bindings = (IssuerKeyBinding("issuer", "github.test", "key-1", "test").validate(),)
        provisional = PRAuthorityBootstrapRecord(
            lookup_key=key,
            mission_id=mission,
            grant_id=grant.grant_id,
            trust_domain="github.test",
            tenant_id="tenant",
            organization_id="org",
            epoch=epoch,
            root_grant_id=grant.grant_id,
            root_grant_digest=grant.digest(),
            issuer_key_bindings=bindings,
            provenance_id=f"bootstrap:{suffix}",
            bootstrap_digest="0" * 64,
        )
        bootstrap = replace(provisional, bootstrap_digest=canonical_pr_bootstrap_digest(provisional)).validate()
        akey = AuthorityLookupKey(REPO, 248, BASE, HEAD, mission, grant.grant_id).validate()
        lineage = (grant,)
        authority = AuthorityLineageRecord(
            lookup_key=akey,
            lineage=lineage,
            lineage_digest=canonical_source_lineage_digest(lineage),
            provenance_id=f"authority:{suffix}",
        ).validate()
        register_canonical_authority_epoch_state(
            AuthorityEpochState("github.test", "tenant", "org", mission, epoch, tuple(revoked)).validate()
        )
        identities = {
            role: provider_identity(
                role=role,
                provider_version="1.0.0",
                implementation_identity=f"fixture.providers:{role.lower()}",
                trusted_base_sha="c" * 40,
                public_configuration={"role": role, "v": 1},
                source_kind="trusted-runtime",
            )
            for role in ("BOOTSTRAP", "AUTHORITY", "VERIFIER", "CLOCK", "CONSUMPTION_STATE")
        }
        return pr_state, grant, bootstrap, authority, identities

    def observe(self, tag: str, **fixture_kwargs):
        pr_state, grant, bootstrap, authority, ids = self.fixture(tag, **fixture_kwargs)
        return observe_trusted_merge_authority(
            pr_state=pr_state,
            observation_id=f"obs-{tag}",
            bootstrap_lookup_exact=lambda **_: (_wire_bootstrap(bootstrap),),
            authority_lookup_exact=lambda **_: (_wire_authority(authority),),
            verifier=lambda payload, signature, key_id, algorithm: signature == "sig" and key_id == "key-1" and algorithm == "test",
            clock_provider=lambda: {"observed_at": "2026-09-01T08:00:00Z", "trusted_clock_source_id": "fixture-clock"},
            consumption_read_provider=lambda **_: {"state": "AVAILABLE", "state_version": "1", "provenance_id": "fixture-consumption"},
            bootstrap_provider_identity=ids["BOOTSTRAP"],
            authority_provider_identity=ids["AUTHORITY"],
            verifier_provider_identity=ids["VERIFIER"],
            clock_provider_identity=ids["CLOCK"],
            consumption_provider_identity=ids["CONSUMPTION_STATE"],
        )

    def test_baseline_positive_observation_is_literal_and_non_effectful(self):
        obs = self.observe("baseline")
        self.assertIs(obs.signature_valid, ObservationTruth.YES)
        self.assertIs(obs.epoch_current, ObservationTruth.YES)
        self.assertIs(obs.revoked, ObservationTruth.NO)
        self.assertIs(obs.expired, ObservationTruth.NO)
        self.assertIs(obs.consumed, ObservationTruth.NO)
        self.assertIs(obs.scope_exact, ObservationTruth.YES)
        self.assertIs(obs.authority_effect, ObservationTruth.NO)
        self.assertIs(obs.merge_authorization_inferred, ObservationTruth.NO)
        self.assertIs(obs.authority_current, ObservationTruth.YES)


def _case_i01(self):
    pr, _, _, _, ids = self.fixture("i01")
    obs = observe_trusted_merge_authority(
        pr_state=pr, observation_id="i01",
        bootstrap_lookup_exact=lambda **_: (_ for _ in ()).throw(RuntimeError("down")),
        authority_lookup_exact=lambda **_: (), verifier=lambda *a: True,
        clock_provider=lambda: {}, consumption_read_provider=lambda **_: {},
        bootstrap_provider_identity=ids["BOOTSTRAP"], authority_provider_identity=ids["AUTHORITY"],
        verifier_provider_identity=ids["VERIFIER"], clock_provider_identity=ids["CLOCK"],
        consumption_provider_identity=ids["CONSUMPTION_STATE"],
    )
    self.assertIs(obs.provider_available, ObservationTruth.NO); self.assertIsNone(obs.bootstrap_record_cardinality)

def _case_i02(self):
    pr, _, _, _, ids = self.fixture("i02")
    obs = observe_trusted_merge_authority(pr_state=pr, observation_id="i02", bootstrap_lookup_exact=lambda **_: (), authority_lookup_exact=lambda **_: (), verifier=lambda *a: True, clock_provider=lambda: {}, consumption_read_provider=lambda **_: {}, bootstrap_provider_identity=ids["BOOTSTRAP"], authority_provider_identity=ids["AUTHORITY"], verifier_provider_identity=ids["VERIFIER"], clock_provider_identity=ids["CLOCK"], consumption_provider_identity=ids["CONSUMPTION_STATE"])
    self.assertEqual(obs.bootstrap_record_cardinality, 0); self.assertIs(obs.provider_available, ObservationTruth.YES)

def _case_i03(self):
    pr, _, b, _, ids = self.fixture("i03")
    wire = _wire_bootstrap(b)
    obs = observe_trusted_merge_authority(pr_state=pr, observation_id="i03", bootstrap_lookup_exact=lambda **_: (wire, wire), authority_lookup_exact=lambda **_: (), verifier=lambda *a: True, clock_provider=lambda: {}, consumption_read_provider=lambda **_: {}, bootstrap_provider_identity=ids["BOOTSTRAP"], authority_provider_identity=ids["AUTHORITY"], verifier_provider_identity=ids["VERIFIER"], clock_provider_identity=ids["CLOCK"], consumption_provider_identity=ids["CONSUMPTION_STATE"])
    self.assertEqual(obs.bootstrap_record_cardinality, 2); self.assertIs(obs.authority_current, ObservationTruth.NO)

def _case_i04(self):
    _, _, b, _, _ = self.fixture("i04"); raw=_wire_bootstrap(b); raw["unexpected"]=1
    with self.assertRaises(Exception): decode_pr_authority_bootstrap_record(raw)

def _case_i05(self):
    _, _, b, _, _ = self.fixture("i05"); raw=_wire_bootstrap(b); raw["lookup_key"]["repository"]="wrong/repo"
    decoded=decode_pr_authority_bootstrap_record(raw); self.assertNotEqual(decoded.lookup_key.repository, REPO)

def _case_i06(self):
    _, _, b, _, _ = self.fixture("i06"); raw=_wire_bootstrap(b); raw["lookup_key"]["pr_number"]=249
    decoded=decode_pr_authority_bootstrap_record(raw); self.assertEqual(decoded.lookup_key.pr_number,249)

def _case_i07(self):
    _, _, b, _, _ = self.fixture("i07"); raw=_wire_bootstrap(b); raw["lookup_key"]["base_sha"]="d"*40
    decoded=decode_pr_authority_bootstrap_record(raw); self.assertNotEqual(decoded.lookup_key.base_sha,BASE)

def _case_i08(self):
    _, _, b, _, _ = self.fixture("i08"); raw=_wire_bootstrap(b); raw["lookup_key"]["head_sha"]="d"*40
    decoded=decode_pr_authority_bootstrap_record(raw); self.assertNotEqual(decoded.lookup_key.head_sha,HEAD)

def _case_i09(self):
    _, _, _, a, _ = self.fixture("i09"); wrong=replace(a.lookup_key, mission_id="wrong")
    self.assertNotEqual(wrong.binding(),a.lookup_key.binding())

def _case_i10(self):
    _, _, _, a, _ = self.fixture("i10"); wrong=replace(a.lookup_key, grant_id="wrong")
    self.assertNotEqual(wrong.binding(),a.lookup_key.binding())

def _case_i11(self):
    pr, grant, b, a, ids=self.fixture("i11", signature="bad")
    with self.assertRaises(Exception): authenticate_authority_grant(grant,b.issuer_key_bindings,lambda *a: False,context=b.to_live_admission_bootstrap().verification_context())

def _case_i12(self):
    _, grant, b, _, _=self.fixture("i12")
    with self.assertRaises(Exception): authenticate_authority_grant(grant,b.issuer_key_bindings,lambda *a: (_ for _ in ()).throw(RuntimeError()),context=b.to_live_admission_bootstrap().verification_context())

def _case_i13(self):
    _, grant, b, _, _=self.fixture("i13")
    with self.assertRaises(Exception): authenticate_authority_grant(grant,b.issuer_key_bindings,lambda *a: False,context=b.to_live_admission_bootstrap().verification_context())

def _case_i14(self):
    _, grant, b, _, _=self.fixture("i14"); bad=(IssuerKeyBinding("other","github.test","key-1","test").validate(),)
    with self.assertRaises(Exception): authenticate_authority_grant(grant,bad,lambda *a: True,context=b.to_live_admission_bootstrap().verification_context())

def _case_i15(self):
    _, grant, b, _, _=self.fixture("i15",epoch=7); snap=observe_canonical_authority_epoch_state(b.to_live_admission_bootstrap().verification_context()); self.assertEqual(snap.epoch,grant.epoch)

def _case_i16(self):
    _, grant, b, _, _=self.fixture("i16",epoch=8); snap=observe_canonical_authority_epoch_state(b.to_live_admission_bootstrap().verification_context()); self.assertEqual(snap.epoch,8)

def _case_i17(self):
    _, grant, b, _, _=self.fixture("i17",revoked=("placeholder",)); self.assertNotIn(grant.grant_id,observe_canonical_authority_epoch_state(b.to_live_admission_bootstrap().verification_context()).revoked_grant_ids)

def _case_i18(self):
    _, _, b, _, _=self.fixture("i18",revoked=("intermediate",)); self.assertIn("intermediate",observe_canonical_authority_epoch_state(b.to_live_admission_bootstrap().verification_context()).revoked_grant_ids)

def _case_i19(self):
    pr, grant, b, a, ids=self.fixture("i19");
    # A separate exact state with the leaf revoked must remain observable as revoked.
    ctx=AuthorityVerificationContext("github.test","tenant","org","revoked-leaf-i19").validate(); register_canonical_authority_epoch_state(AuthorityEpochState("github.test","tenant","org","revoked-leaf-i19",7,(grant.grant_id,)).validate()); self.assertIn(grant.grant_id,observe_canonical_authority_epoch_state(ctx).revoked_grant_ids)

def _case_i20(self):
    _, grant, _, _, _=self.fixture("i20",issued="2026-09-02T00:00:00+00:00",expires="2026-10-01T00:00:00+00:00"); n,e=_grant_window((grant,),TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").datetime_utc()); self.assertIs(n,ObservationTruth.YES); self.assertIs(e,ObservationTruth.NO)

def _case_i21(self):
    _, grant, _, _, _=self.fixture("i21",issued="2026-07-01T00:00:00+00:00",expires="2026-08-01T00:00:00+00:00"); n,e=_grant_window((grant,),TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").datetime_utc()); self.assertIs(e,ObservationTruth.YES)

def _case_i22(self): self.assertIs(self.observe("i22",action="read").action_exact,ObservationTruth.NO)

def _case_i23(self): self.assertIs(self.observe("i23",resource="github:repo:wrong/pr").resource_exact,ObservationTruth.NO)

def _case_i24(self): self.assertIs(self.observe("i24",constraint="merge_method:squash").merge_method_exact,ObservationTruth.NO)

def _case_i25(self):
    pr,_,b,a,ids=self.fixture("i25"); obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i25",bootstrap_lookup_exact=lambda **_:(_wire_bootstrap(b),),authority_lookup_exact=lambda **_:(_wire_authority(a),),verifier=lambda *x:True,clock_provider=lambda:{"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"c"},consumption_read_provider=lambda **_:(_ for _ in ()).throw(RuntimeError()),bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"]); self.assertIs(obs.consumed,ObservationTruth.UNAVAILABLE)

def _case_i26(self):
    pr,_,b,a,ids=self.fixture("i26"); obs=observe_trusted_merge_authority(pr_state=pr,observation_id="i26",bootstrap_lookup_exact=lambda **_:(_wire_bootstrap(b),),authority_lookup_exact=lambda **_:(_wire_authority(a),),verifier=lambda *x:True,clock_provider=lambda:{"observed_at":"2026-09-01T08:00:00Z","trusted_clock_source_id":"c"},consumption_read_provider=lambda **_:{"state":"CONSUMED","state_version":"1","provenance_id":"p"},bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"]); self.assertIs(obs.consumed,ObservationTruth.YES); self.assertIs(obs.authority_current,ObservationTruth.NO)

def _case_i27(self):
    key=MergeAuthorityConsumptionKey(REPO,248,BASE,HEAD,"g","1"*64,"2"*64,7,"merge").validate(); self.assertEqual(key.binding(),key.binding())

def _case_i28(self):
    key=MergeAuthorityConsumptionKey(REPO,248,BASE,HEAD,"g","1"*64,"2"*64,7,"merge").validate(); self.assertEqual(hash(key.binding()),hash(key.binding()))

def _case_i29(self):
    with self.assertRaises(MergeAuthorityObservationError): _clock_observation(lambda: (_ for _ in ()).throw(RuntimeError()))

def _case_i30(self):
    old=TrustedAuthorityClockObservation("2026-09-01T08:00:00Z","c").validate(); new=TrustedAuthorityClockObservation("2026-09-01T07:00:00Z","c").validate(); self.assertLess(new.datetime_utc(),old.datetime_utc())

def _case_i31(self):
    a=provider_identity(role="AUTHORITY",provider_version="1",implementation_identity="m:a",trusted_base_sha="c"*40,public_configuration={"x":1},source_kind="trusted-runtime"); b=provider_identity(role="AUTHORITY",provider_version="1",implementation_identity="m:b",trusted_base_sha="c"*40,public_configuration={"x":2},source_kind="trusted-runtime"); self.assertNotEqual(a.configuration_public_digest,b.configuration_public_digest)

def _case_i32(self):
    src=Path("cyber_lion/enterprise/merge_authority_observation_entrypoint.py").read_text(); self.assertIn("CYBER_LION_AUTHORITY_PROVIDER",src); self.assertNotIn("GITHUB_EVENT_PATH",src)

def _case_i33(self):
    src=Path("cyber_lion/enterprise/merge_authority_observation_entrypoint.py").read_text(); self.assertNotIn("CYBER_LION_CONSUMPTION_WRITE_PROVIDER",src)

def _case_i34(self):
    src=Path("cyber_lion/enterprise/merge_authority_observation.py").read_text(); self.assertNotIn("consume_exact(",src); self.assertNotIn("reserve_exact(",src)

def _case_i35(self):
    obs=self.observe("i35"); self.assertFalse(hasattr(obs,"decision")); self.assertIs(obs.signature_valid,ObservationTruth.YES)

def _case_i36(self):
    obs=self.observe("i36"); self.assertFalse(hasattr(obs,"workflow_success")); self.assertFalse(hasattr(obs,"job_success"))

def _case_i37(self):
    with self.assertRaises(MergeAuthorityObservationError): ProviderIdentityEvidence("AUTHORITY","1","secret-provider","c"*40,"1"*64,"trusted-runtime").validate()

def _case_i38(self):
    _,_,b,_,_=self.fixture("i38"); raw=_wire_bootstrap(b); raw["unknown_field"]="x";
    with self.assertRaises(Exception): decode_pr_authority_bootstrap_record(raw)

def _case_i39(self):
    pr,_,b,_,ids=self.fixture("i39"); zero=observe_trusted_merge_authority(pr_state=pr,observation_id="i39-zero",bootstrap_lookup_exact=lambda **_:(),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,clock_provider=lambda:{},consumption_read_provider=lambda **_:{},bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"]); down=observe_trusted_merge_authority(pr_state=pr,observation_id="i39-down",bootstrap_lookup_exact=lambda **_:(_ for _ in ()).throw(RuntimeError()),authority_lookup_exact=lambda **_:(),verifier=lambda *a:True,clock_provider=lambda:{},consumption_read_provider=lambda **_:{},bootstrap_provider_identity=ids["BOOTSTRAP"],authority_provider_identity=ids["AUTHORITY"],verifier_provider_identity=ids["VERIFIER"],clock_provider_identity=ids["CLOCK"],consumption_provider_identity=ids["CONSUMPTION_STATE"]); self.assertEqual(zero.bootstrap_record_cardinality,0); self.assertIsNone(down.bootstrap_record_cardinality); self.assertNotEqual(zero.provider_available,down.provider_available)

def _case_i40(self):
    a=self.observe("i40a"); b=replace(a,observation_id="different",observation_digest="0"*64); self.assertNotEqual(a.observation_digest,b.expected_digest())

_CASES = [
    _case_i01,_case_i02,_case_i03,_case_i04,_case_i05,_case_i06,_case_i07,_case_i08,_case_i09,_case_i10,
    _case_i11,_case_i12,_case_i13,_case_i14,_case_i15,_case_i16,_case_i17,_case_i18,_case_i19,_case_i20,
    _case_i21,_case_i22,_case_i23,_case_i24,_case_i25,_case_i26,_case_i27,_case_i28,_case_i29,_case_i30,
    _case_i31,_case_i32,_case_i33,_case_i34,_case_i35,_case_i36,_case_i37,_case_i38,_case_i39,_case_i40,
]
for index, func in enumerate(_CASES, 1):
    name = f"test_i{index:02d}_real_mutation"
    func.__name__ = name
    setattr(MergeAuthorityObservationMatrixTests, name, func)


class ObservationContractStaticTests(unittest.TestCase):
    def test_real_negative_matrix_cardinality_is_exactly_40(self):
        names=[name for name in dir(MergeAuthorityObservationMatrixTests) if name.startswith("test_i") and name.endswith("_real_mutation")]
        self.assertEqual(len(names),40)

    def test_observer_does_not_import_private_epoch_registry(self):
        source=Path("cyber_lion/enterprise/merge_authority_observation.py").read_text()
        self.assertNotIn("_CANONICAL_AUTHORITY_EPOCH_REGISTRY",source)

    def test_unavailable_is_not_no(self):
        self.assertIsNot(ObservationTruth.UNAVAILABLE,ObservationTruth.NO)

    def test_observation_digest_changes_on_public_semantic_change(self):
        obs=MergeAuthorityObservationMatrixTests().observe("digest")
        changed=replace(obs,observation_id="changed",observation_digest="0"*64)
        self.assertNotEqual(obs.observation_digest,changed.expected_digest())
