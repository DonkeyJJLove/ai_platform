from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from cyber_lion.contracts.candidate_build_authorization import (
    ResourceAuthorityLookupKey,
    TrustedRepositoryBaseline,
    canonical_repo_path_resource,
)
from cyber_lion.contracts.governed_change_admission import GovernedChangeAdmissionRequest
from cyber_lion.contracts.policy_gate import GateApplied, GateRequested, PDPDecisionReceipt
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.candidate_build_authorization import (
    CandidateBuildAuthorizationEngine,
    CandidateBuildAuthorizationError,
    LiveResourceAuthorityAdmission,
    ResourceAuthorityLineageRecord,
    ResourceAuthoritySource,
)

REPO = "DonkeyJJLove/ai_platform"
MISSION = "E004-R11"
GRANT = "grant-e004-r11-build"
PATHS = (
    "cyber_lion/contracts/candidate_build_authorization.py",
    "cyber_lion/enterprise/candidate_build_authorization.py",
)
RESOURCES = tuple(canonical_repo_path_resource(REPO, p) for p in PATHS)
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
BASE = "a" * 40
TREE = "b" * 40
NOW = datetime(2026, 8, 25, 0, 30, tzinfo=timezone.utc)
POLICY_DIGEST = "sha256:" + "6" * 64
POLICY_BINDING = "candidate-build@1:" + POLICY_DIGEST


def signature_verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    return signature == "sig" and key_id == "key-1" and algorithm == "test"


class MemoryReplay:
    def __init__(self):
        self.seen = set()

    def consume(self, digest, *, consumed_at):
        if digest in self.seen:
            return False
        self.seen.add(digest)
        return True


class EpochProvider:
    def __init__(self, epoch=4, version=1, revoked=()):
        self.state = type("Epoch", (), {})()
        self.state.epoch = epoch
        self.state.version = version
        self.state.revoked_grant_ids = tuple(revoked)

    def current(self, context):
        return self.state


class RootProvider:
    def __init__(self, grant):
        self.root = type("Root", (), {})()
        self.root.root_grant_id = grant.grant_id
        self.root.root_grant_digest = grant.digest()

    def resolve(self, context, epoch):
        return self.root


class BaselineSource:
    def __init__(self, sha=BASE, tree=TREE, repository=REPO):
        self.sha = sha
        self.tree = tree
        self.repository = repository

    def current(self, repository):
        return TrustedRepositoryBaseline(
            repository=self.repository,
            master_sha=self.sha,
            master_tree_sha=self.tree,
            observed_at=NOW.isoformat(),
        ).validate()


class StaticResourceSource(ResourceAuthoritySource):
    def __init__(self, records):
        self.records = records

    def _lookup_resource_exact(self, key):
        return self.records


def make_grant(*, authority="local_write", resources=RESOURCES, actions=("BUILD_CANDIDATE",), expires="2026-08-25T02:00:00+00:00"):
    return AuthorityGrant(
        schema_version="1.1.0",
        grant_id=GRANT,
        issuer_subject_id="issuer",
        subject_id="candidate-builder",
        tenant_id="tenant",
        organization_id="org",
        mission_id=MISSION,
        capability_id="repository.candidate-build",
        capability_version="1.0.0",
        actions=actions,
        resource_scope=resources,
        authority_ceiling=authority,
        constraints=("candidate_build_only:true",),
        parent_grant_id=None,
        issued_at="2026-08-25T00:00:00+00:00",
        expires_at=expires,
        epoch=4,
        policy_digest=POLICY_DIGEST,
        observability_contract_digest="sha256:" + "7" * 64,
        signature="sig",
        delegation_allowed=False,
        delegation_depth_budget=0,
    ).validate()


def make_key(resources=RESOURCES):
    return ResourceAuthorityLookupKey(REPO, MISSION, GRANT, "BUILD_CANDIDATE", resources).validate()


def make_record(grant=None, key=None):
    grant = grant or make_grant()
    key = key or make_key()
    return ResourceAuthorityLineageRecord(
        lookup_key=key,
        lineage=(grant,),
        lineage_digest=canonical_source_lineage_digest((grant,)),
        provenance_id="control-plane:e004:r11",
    ).validate()


def make_admission(**changes):
    values = dict(
        schema_version="1.0.0",
        request_id="gca:e004-r11",
        proposal_id="gcp:e004-r11",
        proposal_digest=H1,
        epoch_id="E004",
        source_delta_digest=H2,
        source_epoch_transition_digest=H3,
        source_memory_head="4" * 64,
        source_promotion_digest="5" * 64,
        repository=REPO,
        target_component="candidate-build-authorization",
        candidate_scope=PATHS,
        requested_action="BUILD_CANDIDATE",
        requested_resource_scope=RESOURCES,
        risk_class="AMBER",
        lane="AMBER",
        requested_authority="local_write",
        evidence_refs=("evidence:e004:r11",),
    )
    values.update(changes)
    return GovernedChangeAdmissionRequest(**values).sealed()


def make_policy(admission=None, lineage_digest=None, *, observability="HEALTHY"):
    admission = admission or make_admission()
    lineage_digest = lineage_digest or make_record().lineage_digest
    request = GateRequested(
        request_id="gate:e004-r11",
        proposal_id=admission.request_id,
        policy_binding=POLICY_BINDING,
        authority_lineage_digest=lineage_digest,
        enterprise_graph_digest="8" * 64,
        status_digest="9" * 64,
        observability_state=observability,
        lane=admission.lane,
        requested_authority=admission.requested_authority,
        evidence_refs=(admission.proposal_digest, admission.admission_request_digest),
    ).sealed()
    applied = GateApplied(
        gate_event_id="gate-event:e004-r11",
        request_id=request.request_id,
        proposal_id=request.proposal_id,
        decision="ALLOW",
        effective_authority="local_write",
        policy_binding=request.policy_binding,
        authority_lineage_digest=request.authority_lineage_digest,
        enterprise_graph_digest=request.enterprise_graph_digest,
        status_digest=request.status_digest,
        observability_state=request.observability_state,
        lane=request.lane,
        rationale="exact candidate build admission allowed",
    ).sealed()
    receipt = PDPDecisionReceipt(
        receipt_id="pdp-receipt:e004-r11",
        request_id=request.request_id,
        gate_event_id=applied.gate_event_id,
        request_digest=request.request_digest,
        decision_digest=applied.decision_digest,
        replay_key="c" * 64,
    ).validate()
    return request, applied, receipt


def make_live(*, grant=None, record=None, epoch_provider=None, live_replay=None):
    grant = grant or make_grant()
    record = record or make_record(grant=grant)
    return LiveResourceAuthorityAdmission(
        authority_source=StaticResourceSource((record,)),
        context=AuthorityVerificationContext(
            trust_domain="github.test", tenant_id="tenant", organization_id="org", mission_id=MISSION
        ).validate(),
        issuer_keys=(IssuerKeyBinding(
            issuer_subject_id="issuer", trust_domain="github.test", key_id="key-1", algorithm="test"
        ).validate(),),
        signature_verifier=signature_verifier,
        epoch_provider=epoch_provider or EpochProvider(),
        root_provider=RootProvider(grant),
        replay_guard=live_replay or MemoryReplay(),
    )


def make_engine(*, grant=None, record=None, epoch_provider=None, live_replay=None, issuance_replay=None, baseline=None):
    return CandidateBuildAuthorizationEngine(
        live_authority=make_live(
            grant=grant, record=record, epoch_provider=epoch_provider, live_replay=live_replay
        ),
        baseline_source=baseline or BaselineSource(),
        issuance_replay_guard=issuance_replay or MemoryReplay(),
    )


class CandidateBuildAuthorizationEngineTests(unittest.TestCase):
    def test_happy_path_issues_non_effectful_authorization(self):
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        auth = make_engine(record=record).issue(
            admission_request=admission, gate_request=request, gate_applied=applied,
            pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
        )
        self.assertEqual(auth.action, "BUILD_CANDIDATE")
        self.assertEqual(auth.resource_scope, RESOURCES)
        self.assertEqual(auth.baseline_master_sha, BASE)
        self.assertEqual(auth.baseline_master_tree_sha, TREE)
        self.assertEqual(auth.effective_authority_ceiling, "local_write")
        self.assertEqual(
            (auth.authority_effect, auth.execution_effect, auth.repository_ref_effect, auth.external_effect),
            ("NONE", "NONE", "NONE", "NONE"),
        )
        self.assertEqual(auth.authorization_id, f"cba:{auth.issuance_replay_digest}")
        self.assertEqual(len(auth.authorization_digest), 64)

    def test_gate_request_substitution_denied(self):
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        other = replace(request, status_digest="d" * 64, request_digest="").sealed()
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "binding mismatch"):
            make_engine(record=record).issue(
                admission_request=admission, gate_request=other, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_gate_decision_or_receipt_substitution_denied(self):
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        bad_receipt = replace(receipt, decision_digest="d" * 64)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "binding mismatch"):
            make_engine(record=record).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=bad_receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_cross_action_transfer_denied(self):
        admission = make_admission(requested_action="RUN_TEST", requested_authority="local_write")
        record = make_record()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "BUILD_CANDIDATE"):
            make_engine(record=record).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_scope_widening_and_path_addition_denied_by_authority_record(self):
        narrow_grant = make_grant(resources=(RESOURCES[0],))
        key = make_key()
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "resource scope"):
            make_record(grant=narrow_grant, key=key)

    def test_authority_widening_is_attenuated_to_local_write(self):
        grant = make_grant(authority="external_write")
        record = make_record(grant=grant)
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        auth = make_engine(grant=grant, record=record).issue(
            admission_request=admission, gate_request=request, gate_applied=applied,
            pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
        )
        self.assertEqual(auth.effective_authority_ceiling, "local_write")

    def test_insufficient_authority_denied(self):
        grant = make_grant(authority="read")
        record = make_record(grant=grant)
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "cannot contain local_write"):
            make_engine(grant=grant, record=record).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_revoked_or_expired_grant_denied(self):
        grant = make_grant()
        record = make_record(grant=grant)
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "revoked"):
            make_engine(grant=grant, record=record, epoch_provider=EpochProvider(revoked=(GRANT,))).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )
        expired = make_grant(expires="2026-08-25T00:10:00+00:00")
        expired_record = make_record(grant=expired)
        request2, applied2, receipt2 = make_policy(admission, expired_record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "expired"):
            make_engine(grant=expired, record=expired_record).issue(
                admission_request=admission, gate_request=request2, gate_applied=applied2,
                pdp_receipt=receipt2, grant_id=GRANT, trusted_now=NOW,
            )

    def test_authority_state_version_drift_denied_during_revalidation(self):
        grant = make_grant()
        record = make_record(grant=grant)
        provider = EpochProvider(version=1)
        live = make_live(grant=grant, record=record, epoch_provider=provider)
        key = make_key()
        admitted = live.admit(key=key, now=NOW, replay_nonce="first")
        provider.state.version = 2
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "stale or forged"):
            live.revalidate(admitted, now=NOW)

    def test_repository_baseline_substitution_denied(self):
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "repository substitution"):
            make_engine(record=record, baseline=BaselineSource(repository="Other/repo")).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_duplicate_source_issuance_is_denied_persistently_by_separate_domain(self):
        shared_issuance = MemoryReplay()
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        first = make_engine(record=record, issuance_replay=shared_issuance)
        first.issue(
            admission_request=admission, gate_request=request, gate_applied=applied,
            pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
        )
        # Fresh live admission/replay simulates a restarted authority admission process;
        # the independent issuance replay domain must still reject the same source tuple.
        second = make_engine(record=record, issuance_replay=shared_issuance)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "issuance replay denied"):
            second.issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_f005_dependency_injection_denied(self):
        record = make_record()
        admission = make_admission(target_component="F005-executor-sandbox")
        request, applied, receipt = make_policy(admission, record.lineage_digest)
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "F005 remains quarantined"):
            make_engine(record=record).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_degraded_observability_cannot_authorize_local_write(self):
        record = make_record()
        admission = make_admission()
        request, applied, receipt = make_policy(admission, record.lineage_digest, observability="DEGRADED")
        with self.assertRaisesRegex(CandidateBuildAuthorizationError, "HEALTHY"):
            make_engine(record=record).issue(
                admission_request=admission, gate_request=request, gate_applied=applied,
                pdp_receipt=receipt, grant_id=GRANT, trusted_now=NOW,
            )

    def test_engine_exposes_no_effect_method(self):
        CandidateBuildAuthorizationEngine.assert_no_effect_surface()
        forbidden = {
            "execute", "write", "push", "merge", "deploy", "release", "create_branch",
            "create_pr", "run_test", "build_candidate", "issue_grant", "revoke_grant",
        }
        self.assertTrue(forbidden.isdisjoint(set(CandidateBuildAuthorizationEngine.__dict__)))


if __name__ == "__main__":
    unittest.main()
