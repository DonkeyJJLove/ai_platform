import pytest
from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import AuthorityLineageRecord,AuthorityLookupKey,AuthoritySource,canonical_pr_authority_resource,canonical_source_lineage_digest
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.models import AgentSpec,MissionSpec,SwarmSpec
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint,PolicyGateError,authority_contains

Z="0"*64
class Source(AuthoritySource):
    def __init__(self,record): self.record=record
    def _lookup_exact(self,key): return (self.record,)
class Graph:
    projection_digest="1"*64

def grant_for(key,authority="external_write"):
    g=AuthorityGrant(schema_version="1.1.0",grant_id=key.grant_id,issuer_subject_id="root",subject_id="agent",
        tenant_id="t",organization_id="o",mission_id=key.mission_id,capability_id="cap",capability_version="1",
        actions=("act",),resource_scope=(canonical_pr_authority_resource(key),),authority_ceiling=authority,constraints=(),parent_grant_id=None,
        issued_at="2026-01-01T00:00:00+00:00",expires_at="2027-01-01T00:00:00+00:00",epoch=1,
        policy_digest="sha256:"+Z,observability_contract_digest="sha256:"+Z,signature="sig").validate()
    return AuthorityLineageRecord(key,(g,),canonical_source_lineage_digest((g,)),"prov").validate()

def fixture(authority="external_write",risk="GREEN",requested="read",verifier=None):
    key=AuthorityLookupKey("DonkeyJJLove/ai_platform",123,"a"*40,"b"*40,"m","g").validate()
    src=Source(grant_for(key,authority));pdp=CanonicalPolicyDecisionPoint(authority_source=src)
    agents={"a":AgentSpec("a","1","builder","m",("cap",),authority_ceiling="external_write",observability_events=("trace",)).validate()}
    verifiers=()
    if verifier:
        agents[verifier]=AgentSpec(verifier,"1","verifier","m",("cap",),authority_ceiling="read",is_verifier=True).validate();verifiers=(verifier,)
    mission=MissionSpec("m","purpose",("cap",),authority_ceiling="external_write",risk_class=risk,require_independent_verifier=risk=="RED").validate()
    swarm=SwarmSpec("s","m",tuple(agents),("cap",),"mesh","external_write",risk,1.0,verifier_agent_ids=verifiers).validate()
    prop=ActionProposal("p","m","s","a","cap",requested,"act","target",evidence_refs=("ev",),required_observability=("trace",),verifier_agent_id=verifier).validate()
    policy=PolicyRevision("policy","1","sha256:"+Z,risk).validate()
    return pdp,key,agents,mission,swarm,prop,policy

def evaluate(parts,**overrides):
    pdp,key,agents,mission,swarm,prop,policy=parts
    args=dict(request_id="r",gate_event_id="g",proposal=prop,mission=mission,swarm=swarm,agents=agents,policy=policy,
        authority_key=key,graph_projection=Graph(),status={"epistemic_state":"CURRENT","status_digest":"2"*64},
        observability_state="HEALTHY",observed_event_types=("trace",),evidence_refs=("graph:1","status:1","authority:1"))
    args.update(overrides);return pdp.evaluate(**args)

def test_green_allow_exact_evidence_and_authority():
    out=evaluate(fixture());assert out.applied.decision=="ALLOW";assert out.receipt.request_digest==out.requested.request_digest

def test_semantic_partial_order_keeps_financial_and_deploy_incomparable():
    assert not authority_contains("financial","deploy");assert not authority_contains("deploy","financial")
    with pytest.raises(PolicyGateError): evaluate(fixture(authority="financial",requested="deploy"))

def test_stale_status_fails_closed():
    with pytest.raises(PolicyGateError): evaluate(fixture(),status={"epistemic_state":"STALE","status_digest":"2"*64})

def test_degraded_observability_monotonically_denies_write():
    out=evaluate(fixture(requested="external_write"),observability_state="DEGRADED");assert out.applied.decision=="DENY";assert out.applied.effective_authority=="none"

def test_replay_substitution_is_denied():
    parts=fixture();evaluate(parts)
    with pytest.raises(PolicyGateError): evaluate(parts,evidence_refs=("different",))
