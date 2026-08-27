from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.branch_ownership_registry import BranchOwnershipRecord
from cyber_lion.contracts.enterprise_graph import EnterpriseGraphProjection, canonical_json as graph_json
from cyber_lion.contracts.policy_gate import PolicyRevision
from cyber_lion.contracts.swarm_status import compute_revision_digest, compute_status_digest
from cyber_lion.enterprise.authority_grant import AuthorityGrant
from cyber_lion.enterprise.authority_source import AuthorityLineageRecord, AuthorityLookupKey, AuthoritySource, canonical_pr_authority_resource, canonical_source_lineage_digest
from cyber_lion.enterprise.authority_verification import AuthorityVerificationContext, IssuerKeyBinding
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.maintenance_bundle import CAPABILITY_REPOSITORY_REF_DELETE, MaintenanceBinding, SQLiteMaintenanceBundleRepository
from cyber_lion.enterprise.models import AgentSpec, MissionSpec, SwarmSpec
from cyber_lion.enterprise.persistent_authority_state import DurableReplayGuard, PersistentBindingFinalizer, PersistentEpochStateProvider, PersistentRootAnchorProvider, SQLiteAuthorityStateStore
from cyber_lion.enterprise.repository_delete_fence import RepositoryDeleteFence
from cyber_lion.enterprise.repository_maintenance_mediated_cleanup import (
    CanonicalSlashSafeGitHubRepositoryMaintenanceBackend,
    MediatedRepositoryMaintenanceError,
    RepositoryMaintenanceAdmissionRuntime,
    RepositoryMaintenanceRequestEvidence,
    RepositoryMaintenanceTrustedDependencies,
)
from cyber_lion.enterprise.repository_maintenance_pdp_context import RepositoryMaintenancePDPContext, ResolvedRepositoryMaintenancePDPContext
from cyber_lion.enterprise.repository_maintenance_sandbox import RepositoryMaintenanceSandbox, _build_operation
from cyber_lion.contracts.repository_maintenance_sandbox import REPOSITORY, RepositoryMaintenancePolicy
from cyber_lion.enterprise.trusted_control_plane_providers import SQLiteTrustedControlPlaneStore

Z = "0" * 64
MASTER = "1" * 40
TREE = "2" * 40
HEAD = "3" * 40
MISSION = "LION-E006-R9D8-CANARY"
POLICY_ID = "LION-E006-R9D8-POLICY"
BRANCH = "mission/e006-r9d8-mediation-canary"
NOW = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)


def status():
    s = {
        "schema_version": "1.0.0",
        "system_id": "LION",
        "revision": 3,
        "previous_status_digest": Z,
        "previous_revision_digest": Z,
        "observed_master": {},
        "governor": {},
        "architecture": {},
        "critical_path": [],
        "formations": [],
        "missions": [],
        "drones": [],
        "role_assignments": [],
        "dependencies": [],
        "blockers": [],
        "channels": [],
        "pending_messages": [],
        "current_actions": [],
        "history": [],
        "epistemic_state": "CURRENT",
        "source_refs": [],
        "generated_at": NOW.isoformat(),
    }
    s["status_digest"] = compute_status_digest(s)
    s["revision_digest"] = compute_revision_digest(
        revision=s["revision"],
        status_digest=s["status_digest"],
        previous_revision_digest=s["previous_revision_digest"],
    )
    return s


def graph():
    payload = {"graph_id": "g", "nodes": [], "edges": []}
    dg = sha256(graph_json(payload)).hexdigest()
    return EnterpriseGraphProjection("g", 1, Z, (), (), dg).verify_digest()


class Source(AuthoritySource):
    def __init__(self, record):
        self.record = record

    def _lookup_exact(self, key):
        return (self.record,) if key.binding() == self.record.lookup_key.binding() else ()


class Resolver:
    def __init__(self, resolved, *, drift_on_second=False):
        self.resolved = resolved
        self.calls = 0
        self.drift_on_second = drift_on_second

    def resolve(self, **kwargs):
        self.calls += 1
        if self.drift_on_second and self.calls >= 2:
            changed = replace(self.resolved.context, graph_projection_digest="f" * 64, context_digest="").sealed()
            return replace(self.resolved, context=changed)
        return self.resolved


class StaticBundleSource:
    def __init__(self, bundle):
        self.bundle = bundle

    def resolve_exact(self, *, repository, capability):
        if (repository, capability) != (self.bundle.binding.repository, self.bundle.binding.capability):
            raise RuntimeError("lookup mismatch")
        return self.bundle


class MemoryCanonicalBackend(CanonicalSlashSafeGitHubRepositoryMaintenanceBackend):
    def __init__(self):
        super().__init__(REPOSITORY, "token")
        self._master = MASTER
        self._tree = TREE
        self._head = HEAD
        self.delete_calls = 0
        self.fake_204_without_delete = False

    def master_sha(self):
        return self._master

    def master_tree(self, master_sha):
        if master_sha != self._master:
            raise RuntimeError("stale master")
        return self._tree

    def branch_sha(self, branch):
        self._assert_branch(branch)
        return self._head

    def _assert_branch(self, branch):
        if branch != BRANCH:
            raise RuntimeError("wrong branch")

    def compare_branch_to_master(self, branch):
        self._assert_branch(branch)
        return {"status": "ahead", "ahead_by": 1, "behind_by": 0}

    def open_prs_for_branch(self, branch):
        self._assert_branch(branch)
        return []

    def ownership_observation(self, branch, master_sha):
        self._assert_branch(branch)
        return BranchOwnershipRecord(
            repository=REPOSITORY,
            branch=branch,
            branch_head_sha=self._head,
            ownership_state="UNOWNED",
            mission_id=None,
            baseline_sha=None,
            superseded_by_branch=None,
            supersession_provenance_ref=None,
            source_provenance_ref=f"memory:{master_sha}",
            epistemic_class="OBSERVED",
            record_revision=1,
        ).validate()

    def _delete_exact_branch_ref_http(self, path):
        expected = f"/repos/{REPOSITORY}/git/refs/heads/{BRANCH}"
        if path != expected:
            raise RuntimeError(f"unexpected delete path {path}")
        self.delete_calls += 1
        if not self.fake_204_without_delete:
            self._head = None
        return 204


class R9D8UMediatedCleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.cp_store = SQLiteTrustedControlPlaneStore(str(root / "control-plane.sqlite"))
        self.bundle_repo = SQLiteMaintenanceBundleRepository(self.cp_store, initialize_schema=True)
        self.policy = PolicyRevision(POLICY_ID, "1", "sha256:" + Z, "RED", True).validate()
        self.mission = MissionSpec(
            MISSION,
            "governed repository maintenance branch-ref deletion",
            (CAPABILITY_REPOSITORY_REF_DELETE,),
            authority_ceiling="external_write",
            risk_class="RED",
            max_agents=2,
            observability_quorum=1.0,
            require_independent_verifier=True,
            max_total_cost_units=2.0,
        ).validate()
        policy_record = {
            "record_kind": "maintenance-policy",
            "lookup_key": {"repository": REPOSITORY, "mission_id": MISSION, "policy_id": POLICY_ID},
            "revision": self.policy.revision,
            "content_digest": self.policy.content_digest,
            "lane": self.policy.lane,
            "active": True,
            "provenance_ref": "external-admin:r9d8u:policy",
            "policy_payload": asdict(self.policy),
        }
        mission_payload = asdict(self.mission)
        mission_payload["required_capabilities"] = list(self.mission.required_capabilities)
        mission_record = {
            "record_kind": "maintenance-mission",
            "lookup_key": {"repository": REPOSITORY, "mission_id": MISSION},
            "provenance_ref": "external-admin:r9d8u:mission",
            "mission_payload": mission_payload,
        }
        self.bundle = self.bundle_repo.provision(
            binding=MaintenanceBinding(REPOSITORY, CAPABILITY_REPOSITORY_REF_DELETE, MISSION, POLICY_ID),
            maintenance_policy_record=policy_record,
            maintenance_mission_record=mission_record,
            administrator_id="external-admin:r9d8u",
            operation_id="provision:r9d8u:1",
            source_system_id="lion-control-plane-prod",
            provisioned_at=NOW.isoformat(),
        )
        self.proposer = AgentSpec(
            "proposer",
            "1",
            "repository-maintainer",
            MISSION,
            (CAPABILITY_REPOSITORY_REF_DELETE,),
            authority_ceiling="external_write",
            observability_events=("github:ref-current",),
            risk_class="RED",
        ).validate()
        self.verifier = AgentSpec(
            "verifier",
            "1",
            "independent-verifier",
            MISSION,
            (CAPABILITY_REPOSITORY_REF_DELETE,),
            authority_ceiling="read",
            observability_events=("github:ref-current",),
            risk_class="RED",
            is_verifier=True,
        ).validate()
        self.swarm = SwarmSpec(
            "swarm:r9d8u",
            MISSION,
            (self.proposer.agent_id, self.verifier.agent_id),
            (CAPABILITY_REPOSITORY_REF_DELETE,),
            "mesh",
            "external_write",
            "RED",
            1.0,
            verifier_agent_ids=(self.verifier.agent_id,),
            estimated_cost_units=1.0,
        ).validate()
        self.graph = graph()
        self.lion_status = status()
        context = RepositoryMaintenancePDPContext(
            policy_binding=self.policy.binding,
            policy_digest=self.policy.content_digest,
            mission_id=MISSION,
            mission_revision=1,
            mission_digest="4" * 64,
            agent_registry_id="agents:r9d8u",
            registry_revision=1,
            registry_event_head="5" * 64,
            registry_projection_digest="6" * 64,
            planner_implementation_digest="7" * 64,
            swarm_digest="8" * 64,
            agents_digest="9" * 64,
            enterprise_graph_id=self.graph.graph_id,
            graph_revision=self.graph.revision,
            graph_event_head=self.graph.event_head,
            graph_projection_digest=self.graph.projection_digest,
            status_digest=self.lion_status["status_digest"],
            fleet_snapshot_digest="a" * 64,
            observability_state="HEALTHY",
            master=MASTER,
            tree=TREE,
        ).sealed()
        self.resolved = ResolvedRepositoryMaintenancePDPContext(
            context=context,
            policy=self.policy,
            mission=self.mission,
            swarm=self.swarm,
            agents={self.proposer.agent_id: self.proposer, self.verifier.agent_id: self.verifier},
            graph_projection=self.graph,
            lion_status=self.lion_status,
        )
        self.key = AuthorityLookupKey(REPOSITORY, 216, "a" * 40, "b" * 40, MISSION, "grant:r9d8u").validate()
        grant = AuthorityGrant(
            schema_version="1.1.0",
            grant_id=self.key.grant_id,
            issuer_subject_id="root",
            subject_id="maintenance-agent",
            tenant_id="t",
            organization_id="o",
            mission_id=MISSION,
            capability_id=CAPABILITY_REPOSITORY_REF_DELETE,
            capability_version="1",
            actions=("delete_exact_branch_ref",),
            resource_scope=(canonical_pr_authority_resource(self.key),),
            authority_ceiling="external_write",
            constraints=(),
            parent_grant_id=None,
            issued_at="2026-01-01T00:00:00+00:00",
            expires_at="2027-01-01T00:00:00+00:00",
            epoch=1,
            policy_digest=self.policy.content_digest,
            observability_contract_digest="sha256:" + Z,
            signature="sig",
        ).validate()
        record = AuthorityLineageRecord(
            self.key,
            (grant,),
            canonical_source_lineage_digest((grant,)),
            "external-control-plane:r9d8u",
        ).validate()
        authority_store = SQLiteAuthorityStateStore(str(root / "authority.sqlite"))
        authority_context = ("lion.test", "t", "o", MISSION)
        authority_store.bootstrap_context(authority_context, epoch=1)
        authority_store.register_root(authority_context, epoch=1, root_grant_id=grant.grant_id, root_grant_digest=grant.digest())
        self.live = LiveAuthorityAdmission(
            authority_source=Source(record),
            context=AuthorityVerificationContext("lion.test", "t", "o", MISSION),
            issuer_keys=(IssuerKeyBinding("root", "lion.test", "key", "ed25519"),),
            signature_verifier=lambda *_: True,
            epoch_provider=PersistentEpochStateProvider(authority_store),
            root_provider=PersistentRootAnchorProvider(authority_store),
            replay_guard=DurableReplayGuard(authority_store, domain="r9d8u-test"),
            binding_finalizer=PersistentBindingFinalizer(authority_store),
        )
        self.fence = RepositoryDeleteFence(str(root / "fence.sqlite"))
        self.request = RepositoryMaintenanceRequestEvidence(
            repository=REPOSITORY,
            control_comment_id=123456,
            actor_login="DonkeyJJLove",
            owner_login="DonkeyJJLove",
            branch=BRANCH,
            expected_branch_head=HEAD,
            event_digest="b" * 64,
        ).validate()

    def tearDown(self):
        self.tmp.cleanup()

    def setup_runtime(self, *, drift_on_second=False, fake_204=False):
        backend = MemoryCanonicalBackend()
        backend.fake_204_without_delete = fake_204
        repo_policy = RepositoryMaintenancePolicy(
            "1.0.0", REPOSITORY, MISSION, "master", ("docs/", "mission/"), 1
        ).validate()
        sandbox = RepositoryMaintenanceSandbox(policy=repo_policy, backend=backend)
        operation, _ = _build_operation(sandbox=sandbox, branch=BRANCH, index=1, master_sha=MASTER)
        deps = RepositoryMaintenanceTrustedDependencies(
            context_resolver=Resolver(self.resolved, drift_on_second=drift_on_second),
            authority_admission=self.live,
            authority_key=self.key,
            provider_id="c" * 64,
        ).validate(bundle=self.bundle)
        runtime = RepositoryMaintenanceAdmissionRuntime(
            bundle_source=StaticBundleSource(self.bundle),
            dependencies=deps,
            fence=self.fence,
        )
        return runtime, backend, sandbox, operation, repo_policy

    def test_full_canonical_chain_reconciles_one_fake_effect(self):
        runtime, backend, sandbox, operation, repo_policy = self.setup_runtime()
        result = runtime.execute_one(
            request=self.request,
            bundle=self.bundle,
            operation=operation,
            policy=repo_policy,
            sandbox=sandbox,
            backend=backend,
            expected_master_tree=TREE,
            execution_id="test:1",
        )
        self.assertEqual(result["fence_state"], "RECONCILED")
        self.assertIsNone(backend.branch_sha(BRANCH))
        self.assertEqual(backend.delete_calls, 1)
        self.assertEqual(result["effect"], CAPABILITY_REPOSITORY_REF_DELETE)

    def test_legacy_issue_comment_authority_path_is_disabled(self):
        _, backend, _, _, _ = self.setup_runtime()
        with self.assertRaises(MediatedRepositoryMaintenanceError):
            backend.authorize_delete(authority=self.request, operation=None, policy=None)
        self.assertEqual(backend.delete_calls, 0)

    def test_direct_delete_without_pdp_and_fence_is_denied(self):
        _, backend, _, _, _ = self.setup_runtime()
        with self.assertRaises(Exception):
            backend.delete_exact_branch_ref(BRANCH, HEAD)
        self.assertEqual(backend.delete_calls, 0)

    def test_context_drift_after_prepared_denies_before_delete(self):
        runtime, backend, sandbox, operation, repo_policy = self.setup_runtime(drift_on_second=True)
        with self.assertRaises(MediatedRepositoryMaintenanceError):
            runtime.execute_one(
                request=self.request,
                bundle=self.bundle,
                operation=operation,
                policy=repo_policy,
                sandbox=sandbox,
                backend=backend,
                expected_master_tree=TREE,
                execution_id="test:drift",
            )
        self.assertEqual(backend.delete_calls, 0)

    def test_fake_204_is_not_terminal_success(self):
        runtime, backend, sandbox, operation, repo_policy = self.setup_runtime(fake_204=True)
        with self.assertRaises(Exception):
            runtime.execute_one(
                request=self.request,
                bundle=self.bundle,
                operation=operation,
                policy=repo_policy,
                sandbox=sandbox,
                backend=backend,
                expected_master_tree=TREE,
                execution_id="test:fake204",
            )
        self.assertEqual(backend.delete_calls, 1)
        self.assertEqual(backend.branch_sha(BRANCH), HEAD)


if __name__ == "__main__":
    unittest.main()