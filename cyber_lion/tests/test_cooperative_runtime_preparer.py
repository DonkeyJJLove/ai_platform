from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cyber_lion.contracts.action_proposal_context import (
    ExplicitActionProposalContext,
    REQUIRED_CONTEXT_FIELDS,
)
from cyber_lion.contracts.action_runtime_binding import (
    RuntimeBindingCurrentness,
    bind_allowed_action_to_runtime_inputs,
)
from cyber_lion.contracts.executor_provisioning import (
    ExecutorProvisioningRequest,
    ProviderTrustBinding,
    ProvisionedExecutor,
)
from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy,
    FleetDispatchBinding,
    ProvisioningBinding,
    SandboxResourceLimits,
    SandboxRuntimeBinding,
)
from cyber_lion.contracts.policy_gate import GateApplied, GateRequested, PDPDecisionReceipt
from cyber_lion.contracts.runtime_enforcement import PDPSourceTrustBinding
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import (
    LiveAdmittedAuthority,
    LiveAuthorityAdmission,
)
from cyber_lion.enterprise.policy_gate import PDPResult
from cyber_lion.enterprise.runtime_enforcement import (
    InMemoryRuntimeAdmissionReplayGuard,
    RuntimeAdmissionEngine,
)
from cyber_lion.enterprise.cooperative_runtime_composition import CooperativeRuntimeContext
from cyber_lion.enterprise.cooperative_control_plane_materializer import CooperativeControlPlaneMaterializer
from cyber_lion.enterprise.cooperative_runtime_evidence_exporter import CooperativeRuntimeEvidenceExporter
from cyber_lion.enterprise.cooperative_runtime_evidence_sources import SQLiteCooperativeRuntimeEvidencePublisher
from cyber_lion.enterprise.cooperative_runtime_preparer import (
    CooperativeRuntimePreparationError,
    CooperativeRuntimePreparationEvidence,
    PreparedCooperativeContextSource,
    assert_no_effect_surface,
    prepare_cooperative_runtime_context,
)
from cyber_lion.mission_control.cooperative_artifacts import WRITE_KIND
from cyber_lion.mission_control import (
    cooperative_production as cp,
    execution_driver,
    global_scheduler,
    operator_control,
)
from cyber_lion.mission_control.cooperative_production import CAPABILITY_PRODUCTION
from cyber_lion.tests import test_executor_sandbox as sb
from cyber_lion.tests import test_runtime_currentness as rc
from cyber_lion.tests import test_runtime_execution as rt


NOW = datetime(2026, 10, 7, 21, 30, tzinfo=timezone.utc)
Z = "0" * 64
REPO = "DonkeyJJLove/ai_platform"
HEAD = "a" * 40
TREE = "b" * 40
POLICY = "policy@1:sha256:" + Z


def D(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class FakeAdmission(LiveAuthorityAdmission):
    def __init__(self):
        pass

    def revalidate(self, admitted, *, now):
        return admitted


class FakePDPSource:
    source_id = "pdp"
    source_instance_id = "pdp:1"
    implementation_digest = Z
    trust_anchor_id = "pdp-anchor"
    trust_anchor_digest = Z

    def __init__(self, evidence):
        self.evidence = evidence

    def resolve(self, request_id, gate_event_id):
        return self.evidence

    def current_policy_binding(self, policy_binding):
        return policy_binding


class CooperativeRuntimePreparerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "artifacts"
        self.root.mkdir()
        self.data = "runtime preparer: żółw\n".encode("utf-8")
        self.artifact_sha = sha256(self.data).hexdigest()
        self.resource = "M1/g00000001/product.txt"
        original = {
            "kind": WRITE_KIND,
            "mission_id": "M1",
            "generation": 1,
            "artifact_name": "product.txt",
            "content": self.data.decode("utf-8"),
            "expected_sha256": self.artifact_sha,
            "producer_model_call_id": "modelcall-r620",
            "parent_response_digest": D("parent-response"),
            "capability": CAPABILITY_PRODUCTION,
            "authority_effect": "NONE",
        }
        raw = json.dumps(
            original, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        self.assignment = {
            "assignment_id": "assignment-r620",
            "mission_id": "M1",
            "phase_id": "BUILD__COOP_WRITE",
            "material_drone_id": "MD001",
            "logical_drone_id": "LD001",
            "lease_generation": 1,
            "control_epoch": 1,
            "context_revision": 0,
            "plan_revision": 0,
            "dispatch_authority": "AUTONOMOUS",
            "state": "HELD",
            "input_json": raw,
            "input_digest": sha256(raw.encode("utf-8")).hexdigest(),
        }
        self.proposal = ActionProposal(
            "proposal:r620",
            "M1",
            "swarm:r620",
            "agent:r620",
            CAPABILITY_PRODUCTION,
            "local_write",
            "WRITE_FILE",
            self.resource,
            True,
            ("evidence:r620",),
            ("trace",),
            verifier_agent_id="agent:verifier",
            payload_digest=self.artifact_sha,
        ).validate()
        self.context = ExplicitActionProposalContext(
            proposal_id=self.proposal.proposal_id,
            mission_id=self.proposal.mission_id,
            swarm_id=self.proposal.swarm_id,
            proposer_agent_id=self.proposal.proposer_agent_id,
            capability=self.proposal.capability,
            requested_authority=self.proposal.requested_authority,
            action_class=self.proposal.action_class,
            target=self.proposal.target,
            consequential=self.proposal.consequential,
            evidence_refs=self.proposal.evidence_refs,
            required_observability=self.proposal.required_observability,
            verifier_agent_id=self.proposal.verifier_agent_id,
            expected_lair_payload_digest=self.artifact_sha,
            field_provenance=tuple(
                (name, "evidence:" + name)
                for name in sorted((*REQUIRED_CONTEXT_FIELDS, "verifier_agent_id"))
            ),
        ).validate()
        self.pdp = self._pdp("ALLOW")
        self.trust = ProviderTrustBinding(
            "provider:r620", "provider:r620:1", D("provider-impl"),
            "provider-anchor:r620", D("provider-anchor"),
        ).validate()
        self.provision_request = ExecutorProvisioningRequest(
            "1.0.0",
            "provision:r620",
            "idem:r620",
            "drone:r620",
            "executor:r620",
            "M1",
            "mission:parent",
            REPO,
            HEAD,
            TREE,
            "mission/r620",
            ("M1",),
            (self.resource,),
            "python",
            D("image"),
            D("sandbox-profile"),
            D("resource-profile"),
            (),
            NOW.isoformat(),
        ).validate()
        self.provisioned = ProvisionedExecutor(
            "1.0.0",
            "provisioned:r620",
            self.provision_request.request_id,
            self.provision_request.digest(),
            self.provision_request.idempotency_key,
            self.provision_request.drone_id,
            self.provision_request.executor_id,
            "runtime:r620",
            "sandbox:r620",
            "workspace:r620",
            self.provision_request.mission_id,
            self.provision_request.parent_mission_id,
            self.provision_request.repository,
            self.provision_request.baseline_sha,
            self.provision_request.baseline_tree_sha,
            self.provision_request.branch,
            self.provision_request.read_scope,
            self.provision_request.write_scope,
            self.provision_request.runtime_class,
            self.provision_request.image_digest,
            self.provision_request.sandbox_profile_digest,
            self.provision_request.resource_profile_digest,
            (),
            self.trust.provider_id,
            self.trust.provider_instance_id,
            self.trust.implementation_digest,
            self.trust.trust_anchor_id,
            self.trust.trust_anchor_digest,
            D("runtime-attestation"),
            "provider:evidence:r620",
            NOW.isoformat(),
        ).validate_for(self.provision_request, self.trust)
        self.pdp_trust = PDPSourceTrustBinding(
            "pdp", "pdp:1", Z, "pdp-anchor", Z
        ).validate()
        self.currentness = RuntimeBindingCurrentness(
            self.pdp_trust,
            self.provisioned.digest(),
            NOW,
            NOW - timedelta(minutes=1),
            NOW + timedelta(minutes=10),
        ).validate()
        self.authority = LiveAdmittedAuthority(
            repository=REPO,
            pr_number=1,
            base_sha=HEAD,
            head_sha=TREE,
            mission_id="M1",
            grant_id="grant:r620",
            lineage_digest=Z,
            provenance_id="provenance:r620",
            epoch=1,
            epoch_state_version=1,
            authority_ceiling="local_write",
            root_grant_id="grant:r620",
            root_grant_digest=Z,
            authenticated_grant_digests=(Z,),
            leaf_key_id="key:r620",
            leaf_algorithm="ed25519",
            replay_digest=Z,
            admitted_at=(NOW - timedelta(minutes=2)).isoformat(),
        ).validate()
        self.runtime = SandboxRuntimeBinding(
            "backend:r620",
            D("backend-id"),
            D("backend-impl"),
            D("isolation"),
            self.provisioned.sandbox_id,
            self.provisioned.workspace_id,
        ).validate()
        self.dispatch = FleetDispatchBinding(
            "M1",
            self.provisioned.drone_id,
            D("dispatch"),
            D("fence"),
            1,
            REPO,
            HEAD,
            TREE,
            self.provisioned.branch,
            (self.resource,),
        ).validate()
        self.provisioning = ProvisioningBinding(
            self.provision_request.digest(),
            D("provisioning-materialization"),
            self.provisioned.digest(),
            "M1",
            self.provisioned.drone_id,
            self.provisioned.executor_id,
            REPO,
            HEAD,
            TREE,
            self.provisioned.branch,
            self.provisioned.read_scope,
            self.provisioned.write_scope,
            self.provisioned.runtime_instance_id,
            self.provisioned.sandbox_id,
            self.provisioned.workspace_id,
            self.provisioned.runtime_attestation_digest,
        ).validate()
        self.policy = ExecutionSandboxPolicy(
            REPO,
            HEAD,
            TREE,
            self.provisioned.branch,
            "M1",
            self.provisioned.drone_id,
            self.provisioned.executor_id,
            self.provisioned.sandbox_id,
            self.provisioned.workspace_id,
            self.provisioned.runtime_instance_id,
            self.authority.digest(),
            self.runtime.digest(),
            self.dispatch.digest(),
            self.provisioning.digest(),
            self.dispatch.dispatch_id,
            self.dispatch.fencing_token,
            1,
            self.provisioned.runtime_attestation_digest,
            self.provisioned.read_scope,
            (self.resource,),
            ("M1",),
            (("python", "-m", "unittest"),),
            SandboxResourceLimits(2, 131072, 131072, 1),
        ).validate()
        self.evidence = self._evidence()
        self.engine = self._engine(self.evidence)

    def _pdp(self, decision):
        requested = GateRequested(
            "request:r620",
            self.proposal.proposal_id,
            POLICY,
            Z,
            Z,
            Z,
            "HEALTHY",
            "GREEN",
            self.proposal.requested_authority,
            ("evidence:r620",),
        ).sealed()
        applied = GateApplied(
            "gate:r620",
            requested.request_id,
            self.proposal.proposal_id,
            decision,
            self.proposal.requested_authority if decision == "ALLOW" else "none",
            POLICY,
            Z,
            Z,
            Z,
            "HEALTHY",
            "GREEN",
            "canonical",
        ).sealed()
        receipt = PDPDecisionReceipt(
            "receipt:r620:" + decision.lower(),
            requested.request_id,
            applied.gate_event_id,
            requested.request_digest,
            applied.decision_digest,
            D("replay:" + decision),
        ).validate()
        return PDPResult(requested, applied, receipt)

    def _evidence(self, **changes):
        values = dict(
            proposal=self.proposal,
            proposal_context=self.context,
            pdp_result=self.pdp,
            currentness=self.currentness,
            admitted_authority=self.authority,
            provisioning_request=self.provision_request,
            provider_trust=self.trust,
            provisioned_executor=self.provisioned,
            sandbox_runtime=self.runtime,
            dispatch=self.dispatch,
            provisioning=self.provisioning,
            sandbox_policy=self.policy,
        )
        values.update(changes)
        return CooperativeRuntimePreparationEvidence(**values)

    def _engine(self, evidence):
        effect, identity, canonical = bind_allowed_action_to_runtime_inputs(
            evidence.proposal,
            evidence.proposal_context,
            evidence.pdp_result,
            evidence.currentness,
            evidence.provisioned_executor,
        )
        return RuntimeAdmissionEngine(
            authority_admission=FakeAdmission(),
            pdp_source=FakePDPSource(canonical),
            pdp_source_trust=self.pdp_trust,
            replay_guard=InMemoryRuntimeAdmissionReplayGuard(),
        )

    def prepare(self, *, evidence=None, assignment=None, engine=None):
        evidence = evidence or self.evidence
        return prepare_cooperative_runtime_context(
            assignment=assignment or self.assignment,
            artifact_root=self.root,
            evidence=evidence,
            admission_engine=engine or self.engine,
            trusted_now=NOW,
        )

    def test_exact_evidence_prepares_context_without_artifact_effect(self):
        context = self.prepare()
        self.assertIsInstance(context, CooperativeRuntimeContext)
        self.assertEqual(context.execution.assignment_id, self.assignment["assignment_id"])
        self.assertEqual(context.execution.worker_id, "MD001")
        self.assertEqual(context.execution.request.resource, self.resource)
        self.assertEqual(context.execution.request.payload_digest, self.artifact_sha)
        self.assertEqual(context.execution.request.action, "WRITE_FILE")
        self.assertEqual(context.execution.admission.requested_effect_digest, context.execution.effect.digest())
        self.assertEqual(context.execution.admission.runtime_identity_digest, context.execution.identity.digest())
        self.assertEqual(list(self.root.rglob("*")), [])

    def test_ready_or_claimed_assignment_is_not_preparation_input(self):
        for state in ("READY", "CLAIMED", "PASS"):
            with self.subTest(state=state):
                with self.assertRaisesRegex(
                    CooperativeRuntimePreparationError, "HELD assignment"
                ):
                    self.prepare(assignment={**self.assignment, "state": state})

    def test_proposal_target_or_payload_substitution_is_denied(self):
        for proposal in (
            replace(self.proposal, target="M1/g00000001/other.txt"),
            replace(self.proposal, payload_digest=D("other-payload")),
        ):
            evidence = self._evidence(proposal=proposal)
            with self.assertRaises(CooperativeRuntimePreparationError):
                self.prepare(evidence=evidence, engine=self.engine)

    def test_deny_never_prepares_runtime_context(self):
        denied = self._pdp("DENY")
        evidence = self._evidence(pdp_result=denied)
        # Build an engine from canonical ALLOW evidence so the denial cannot be
        # converted by caller-controlled source substitution.
        with self.assertRaises(Exception):
            self._engine(evidence)
        evidence = self._evidence(pdp_result=denied)
        with self.assertRaises(CooperativeRuntimePreparationError):
            prepare_cooperative_runtime_context(
                assignment=self.assignment,
                artifact_root=self.root,
                evidence=evidence,
                admission_engine=self.engine,
                trusted_now=NOW,
            )

    def test_provisioning_binding_substitution_is_denied(self):
        bad = replace(self.provisioning, workspace_id="workspace:other")
        evidence = self._evidence(provisioning=bad)
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationError, "provisioning"
        ):
            self.prepare(evidence=evidence)

    def test_dispatch_generation_substitution_is_denied(self):
        bad = replace(self.dispatch, generation=2)
        bad_policy = replace(
            self.policy,
            fleet_dispatch_binding_digest=bad.digest(),
            generation=2,
        )
        evidence = self._evidence(dispatch=bad, sandbox_policy=bad_policy)
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationError, "dispatch generation"
        ):
            self.prepare(evidence=evidence)

    def test_sandbox_runtime_substitution_is_denied(self):
        bad = replace(self.runtime, workspace_id="workspace:other")
        bad_policy = replace(self.policy, runtime_binding_digest=bad.digest())
        evidence = self._evidence(sandbox_runtime=bad, sandbox_policy=bad_policy)
        with self.assertRaises(CooperativeRuntimePreparationError):
            self.prepare(evidence=evidence)

    def test_replay_cannot_prepare_second_runtime_admission(self):
        self.prepare()
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationError, "canonical runtime admission denied"
        ):
            self.prepare()

    def test_prepared_context_source_is_repeatable_without_second_admission(self):
        context = self.prepare()
        source = PreparedCooperativeContextSource(context)
        first = source(self.assignment["assignment_id"])
        second = source(self.assignment["assignment_id"])
        self.assertIs(first, second)
        self.assertEqual(first, context)
        self.assertEqual(source.authority_effect, "NONE")
        with self.assertRaisesRegex(
            CooperativeRuntimePreparationError, "assignment substitution"
        ):
            source("assignment:other")

    def test_prepared_context_flows_through_r616_to_ready_without_artifact_effect(self):
        db_path = Path(self.temp.name).resolve() / "mission-control-current.sqlite"
        provider_root = Path(self.temp.name).resolve() / "provider-contexts"
        provider_root.mkdir()
        provider_db = Path(self.temp.name).resolve() / "provider-evidence.sqlite"
        stamp = NOW.isoformat()
        lpcl = "MISSION=M1\nPHASE=BUILD\n"
        lpcl_digest = sha256(lpcl.encode("utf-8")).hexdigest()

        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            db.executescript(
                """
                CREATE TABLE schema_migrations(
                  version INTEGER PRIMARY KEY,
                  schema_id TEXT NOT NULL,
                  applied_at TEXT NOT NULL,
                  source_head TEXT,
                  source_tree TEXT,
                  migration_digest TEXT,
                  note TEXT
                );
                CREATE TABLE missions(
                  mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,adapter TEXT NOT NULL,
                  spec_digest TEXT NOT NULL,source_head TEXT,source_tree TEXT,namespace TEXT,
                  state TEXT NOT NULL,runtime_state TEXT,logical_count INTEGER NOT NULL,
                  material_target INTEGER NOT NULL,materialized INTEGER NOT NULL DEFAULT 0,
                  ready INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,authorized_at TEXT,
                  updated_at TEXT NOT NULL,last_error TEXT,spec_json TEXT NOT NULL
                );
                CREATE TABLE mission_process_specs(
                  mission_id TEXT PRIMARY KEY,title TEXT NOT NULL,objective TEXT NOT NULL,
                  description TEXT NOT NULL,lpcl_digest TEXT,lpcl_text TEXT,
                  protocols_json TEXT NOT NULL,authority_state TEXT NOT NULL,
                  current_phase TEXT,progress REAL NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                """
            )
            db.execute(
                "INSERT INTO missions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "M1","R620 fixture","LPCL_MISSION",lpcl_digest,HEAD,TREE,None,
                    "RUNNING","DRIVER_ACTIVE",1,1,1,1,stamp,stamp,stamp,None,"{}",
                ),
            )
            db.execute(
                "INSERT INTO mission_process_specs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "M1","R620 fixture","prepare cooperative runtime","integration fixture",
                    lpcl_digest,lpcl,"[]","EXPLICIT_USER_ACTIVATION","BUILD",0.0,stamp,stamp,
                ),
            )
            db.commit()
            operator_control.migrate(db, lambda: stamp)
            execution_driver.migrate(
                db, lambda: stamp, source_head=HEAD, source_tree=TREE
            )
            global_scheduler.migrate(db, lambda: stamp)
            operator_control.ensure_control_state(db, "M1", lambda: stamp)
            execution_driver.ensure_driver(
                db, "M1", lambda: stamp, initial_state="ACTIVE"
            )
            db.execute(
                "UPDATE mission_execution_drivers SET current_phase='BUILD',"
                " lease_expires_at=?, heartbeat_at=?, updated_at=? WHERE mission_id='M1'",
                (
                    (NOW + timedelta(minutes=10)).isoformat(),
                    stamp,
                    stamp,
                ),
            )
            original = json.loads(self.assignment["input_json"])
            assignment_id = global_scheduler.create_held_assignment(
                db,
                "M1",
                "BUILD__COOP_WRITE",
                "LD001",
                "MD001",
                original,
                lambda: stamp,
                lease_generation=1,
            )
            db.row_factory = sqlite3.Row
            row = dict(
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchone()
            )

        context = self.prepare(assignment=row)
        prepared_source = PreparedCooperativeContextSource(context)
        reads = {"count": 0}

        def context_source(aid):
            reads["count"] += 1
            return prepared_source(aid)

        publisher = SQLiteCooperativeRuntimeEvidencePublisher(provider_db)
        admission_source = rt.AdmissionSource(context.execution.admission)
        currentness_source = rc.Source(
            self.authority,
            policy=context.execution.effect.policy_binding,
            obs=context.execution.effect.observability_state,
        )
        dispatch_source = sb.DispatchSource(context.dispatch)

        def transfer_binding(aid, purpose):
            self.assertEqual(purpose, "CONTEXT")
            self.assertEqual(aid, assignment_id)
            return {
                "repository": REPO,
                "source_head": HEAD,
                "mission_id": "M1",
                "assignment_id": aid,
                "conversation_id": "conversation-r620",
                "binding_epoch": 1,
                "generation": 1,
                "lease_generation": 1,
                "context_digest": D("r620-context"),
                "projection_digest": D("r620-projection"),
                "request_id": "request-r620-context",
                "producer_ref": "MISSION_CONTROL",
            }

        exporter = CooperativeRuntimeEvidenceExporter(
            publisher=publisher,
            context_source=context_source,
            admission_source=admission_source,
            admission_trust=rt.trust(),
            authority_admission=FakeAdmission(),
            currentness_source=currentness_source,
            currentness_trust=rc.trust(),
            dispatch_source=dispatch_source,
            runtime_identity_source=lambda runtime: context.execution.identity,
            provisioning_binding_source=lambda aid: context.provisioning,
            context_pin_source=lambda aid: (_ for _ in ()).throw(
                AssertionError("R6.16 must replace template context pin source")
            ),
            transfer_binding_source=transfer_binding,
            now_fn=lambda: NOW,
        )
        materializer = CooperativeControlPlaneMaterializer(
            mission_db=db_path,
            provider_context_root=provider_root,
            exporter_template=exporter,
            ttl_seconds=10,
        )

        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            result = cp._materialize_and_release(
                db,
                assignment_id,
                materializer=materializer,
                expected_kind=cp.WRITE_MATERIALIZATION_KIND,
                expected_provider=cp.WRITE_PROVIDER_ID,
                now_fn=lambda: stamp,
            )

        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["materialization_kind"], cp.WRITE_MATERIALIZATION_KIND)
        self.assertEqual(result["provider_id"], cp.WRITE_PROVIDER_ID)
        self.assertGreaterEqual(reads["count"], 2)
        self.assertEqual(list(self.root.rglob("*")), [])

        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            final = dict(
                db.execute(
                    "SELECT * FROM mission_execution_assignments WHERE assignment_id=?",
                    (assignment_id,),
                ).fetchone()
            )
            release = global_scheduler.held_assignment_release_evidence(
                db, assignment_id
            )
        self.assertEqual(final["state"], "READY")
        self.assertIsNotNone(release)
        self.assertEqual(release["evidence"]["provider_id"], cp.WRITE_PROVIDER_ID)
        self.assertEqual(release["evidence"]["authority_effect"], "NONE")

        with sqlite3.connect(provider_db) as db:
            counts = {
                name: db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                for name in (
                    "runtime_admission_evidence",
                    "context_pin_evidence",
                    "dispatch_evidence",
                    "provisioning_evidence",
                    "runtime_identity_evidence",
                    "currentness_evidence",
                    "transfer_binding_evidence",
                )
            }
        self.assertTrue(all(value == 1 for value in counts.values()))

    def test_preparer_has_no_direct_effect_surface(self):
        assert_no_effect_surface()


if __name__ == "__main__":
    unittest.main()
