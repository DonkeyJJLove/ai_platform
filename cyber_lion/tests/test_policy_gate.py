import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import AuthorityLineageRecord,AuthorityLookupKey,AuthoritySource,canonical_pr_authority_resource,canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext,IssuerKeyBinding
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.models import AgentSpec,MissionSpec,SwarmSpec
from cyber_lion.enterprise.persistent_authority_state import DurableReplayGuard,PersistentBindingFinalizer,PersistentEpochStateProvider,PersistentRootAnchorProvider,SQLiteAuthorityStateStore
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint,PolicyGateError,authority_contains
Z="0"*64
NOW=datetime(2026,8,23,10,0,tzinfo=timezone.utc)
class Source(AuthoritySource):
    def __init__(self,record):self.record=record
    def _lookup_exact(self,key):return (self.record,)
class Graph:projection_digest="1"*64

def grant_for(key,authority="external_write",policy_digest="sha256:"+Z):
    g=AuthorityGrant(schema_version="1.1.0",grant_id=key.grant_id,issuer_subject_id="root",subject_id="agent",tenant_id="t",organization_id="o",mission_id=key.mission_id,capability_id="cap",capability_version="1",actions=("act",),resource_scope=(canonical_pr_authority_resource(key),),authority_ceiling=authority,constraints=(),parent_grant_id=None,issued_at="2026-01-01T00:00:00+00:00",expires_at="2027-01-01T00:00:00+00:00",epoch=1,policy_digest=policy_digest,observability_contract_digest="sha256:"+Z,signature="sig").validate()
    return AuthorityLineageRecord(key,(g,),canonical_source_lineage_digest((g,)),"prov").validate()

def fixture(authority="external_write",risk="GREEN",requested="read",verifier=None,grant_policy="sha256:"+Z):
    td=tempfile.TemporaryDirectory();key=AuthorityLookupKey("DonkeyJJLove/ai_platform",123,"a"*40,"b"*40,"m","g").validate();record=grant_for(key,authority,grant_policy);src=Source(record)
    store=SQLiteAuthorityStateStore(str(Path(td.name)/"authority.db"));context=("lion.test","t","o","m");store.bootstrap_context(context,epoch=1);root=record.lineage[0];store.register_root(context,epoch=1,root_grant_id=root.grant_id,root_grant_digest=root.digest())
    admission=LiveAuthorityAdmission(authority_source=src,context=AuthorityVerificationContext("lion.test","t","o","m"),issuer_keys=(IssuerKeyBinding("root","lion.test","key","ed25519"),),signature_verifier=lambda *_:True,epoch_provider=PersistentEpochStateProvider(store),root_provider=PersistentRootAnchorProvider(store),replay_guard=DurableReplayGuard(store,domain="pdp-test"),binding_finalizer=PersistentBindingFinalizer(store))
    pdp=CanonicalPolicyDecisionPoint(authority_admission=admission)
    agents={"a":AgentSpec("a","1","builder","m",("cap",),authority_ceiling="external_write",observability_events=("trace",)).validate()};verifiers=()
    if verifier:
        agents[verifier]=AgentSpec(verifier,"1","verifier","m",("cap",),authority_ceiling="read",is_verifier=True).validate();verifiers=(verifier,)
    mission=MissionSpec("m","purpose",("cap",),authority_ceiling="external_write",risk_class=risk,require_independent_verifier=risk=="RED").validate();swarm=SwarmSpec("s","m",tuple(agents),("cap",),"mesh","external_write",risk,1.0,verifier_agent_ids=verifiers).validate();prop=ActionProposal("p","m","s","a","cap",requested,"act","target",evidence_refs=("ev",),required_observability=("trace",),verifier_agent_id=verifier).validate();policy=PolicyRevision("policy","1","sha256:"+Z,risk).validate()
    return td,pdp,key,agents,mission,swarm,prop,policy

def evaluate(parts,**overrides):
    td,pdp,key,agents,mission,swarm,prop,policy=parts
    args=dict(request_id="r",gate_event_id="g",proposal=prop,mission=mission,swarm=swarm,agents=agents,policy=policy,authority_key=key,graph_projection=Graph(),status={"epistemic_state":"CURRENT","status_digest":"2"*64},observability_state="HEALTHY",observed_event_types=("trace",),evidence_refs=("graph:1","status:1","authority:1"),trusted_now=NOW);args.update(overrides);return pdp.evaluate(**args)

class CanonicalPDPTests(unittest.TestCase):
    def test_green_allow_requires_live_admitted_authority(self):
        parts=fixture();out=evaluate(parts);self.assertEqual(out.applied.decision,"ALLOW");self.assertEqual(out.receipt.request_digest,out.requested.request_digest);parts[0].cleanup()
    def test_semantic_partial_order_keeps_financial_and_deploy_incomparable(self):
        self.assertFalse(authority_contains("financial","deploy"));self.assertFalse(authority_contains("deploy","financial"));parts=fixture(authority="financial",requested="deploy")
        with self.assertRaises(PolicyGateError):evaluate(parts)
        parts[0].cleanup()
    def test_stale_status_fails_closed_before_authority_admission(self):
        parts=fixture()
        with self.assertRaises(PolicyGateError):evaluate(parts,status={"epistemic_state":"STALE","status_digest":"2"*64})
        parts[0].cleanup()
    def test_degraded_observability_monotonically_denies_write(self):
        parts=fixture(requested="external_write");out=evaluate(parts,observability_state="DEGRADED");self.assertEqual(out.applied.decision,"DENY");self.assertEqual(out.applied.effective_authority,"none");parts[0].cleanup()
    def test_replay_substitution_is_denied_without_second_authority_consumption(self):
        parts=fixture();first=evaluate(parts);self.assertIs(evaluate(parts),first)
        with self.assertRaises(PolicyGateError):evaluate(parts,evidence_refs=("different",))
        parts[0].cleanup()
    def test_policy_revision_must_match_authenticated_grant_digest(self):
        parts=fixture(grant_policy="sha256:"+"f"*64)
        with self.assertRaises(PolicyGateError):evaluate(parts)
        parts[0].cleanup()
