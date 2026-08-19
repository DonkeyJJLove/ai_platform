from __future__ import annotations
import copy
import dataclasses
import unittest
from cyber_lion.enterprise.conformance import (
    ControlledChangeDryRunReceipt, ConformanceResult, current_partial_conformance,
    evaluate_read_only_provider,
)
from cyber_lion.enterprise.control_plane import ActionProposal, ExecutionControlPlane
from cyber_lion.enterprise.models import AgentSpec, EnterpriseModelError, MissionSpec
from cyber_lion.enterprise.planner import SwarmPlanner

PROVIDER = "DonkeyJJLove/glitchlab"
COMMIT = "7a06d479f5e0c6d68174eecb585eed22c7e40792"
MANIFEST_DIGEST = "6c2ddafd793f0d2b8d1164fcbe91ba775eecc4e147f87e4104c3ee2447aee1b2"
MANIFEST = {
    "schema_version": "1.0.0",
    "repository": {"id": PROVIDER, "url": "https://github.com/DonkeyJJLove/glitchlab",
                   "owner": "DonkeyJJLove", "default_branch": "master", "vcs_ref": None},
    "cyber_lion": {"tile_id": "evolution-compiler.glitchlab",
                   "roles": ["EvolutionCompiler", "DeltaNormalizer", "InvariantEvaluator",
                             "StructuralChangeAnalyzer"], "layers": ["SEM", "MAND"],
                   "disposition": ["KEEP", "REFINE", "GENERALIZE", "INTEGRATE"]},
    "capabilities": ["delta.normalize", "delta.structural_projection", "invariant.evaluate",
                     "sast.bridge", "change.observability", "change.explain"],
    "authority": {"maximum_level": "local_write",
                  "required_gates": ["glitchlab.invariants", "cyber-lion.mand"]},
    "observability": {"logs": ["delta.analysis", "invariant.verdict", "compiler.decision"],
                      "metrics": ["delta.size", "invariant.failures", "authority.delta",
                                  "observability.delta"],
                      "traces": ["source→delta→projection→invariants→decision"]},
    "security": {"trust_boundaries": ["generated proposal != accepted mutation",
                                      "semantic analysis != runtime authority",
                                      "local invariant pass != path safety",
                                      "self-healing proposal requires external gate before consequential mutation"]},
    "epistemic": {"status": "ENGINEERING_CANDIDATE", "confidence": 0.86},
}

class RCCM1DConformanceTests(unittest.TestCase):
    def snapshot(self, manifest=MANIFEST, commit=COMMIT, capability="invariant.evaluate"):
        return evaluate_read_only_provider(
            manifest, provider_id=PROVIDER, provider_commit=commit,
            expected_commit=COMMIT, capability=capability,
            expected_manifest_digest=MANIFEST_DIGEST,
        )

    def test_real_glitchlab_snapshot_is_pinned_and_read_only(self):
        snapshot, manifest = self.snapshot()
        self.assertEqual(snapshot.provider_commit, COMMIT)
        self.assertEqual(snapshot.runtime_authority, "read")
        self.assertEqual(manifest.maximum_authority, "local_write")
        self.assertEqual(snapshot.manifest_digest, MANIFEST_DIGEST)

    def test_snapshot_rejects_drift_identity_and_capability_spoof(self):
        with self.assertRaises(EnterpriseModelError):
            self.snapshot(commit="0" * 40)
        wrong = copy.deepcopy(MANIFEST)
        wrong["repository"]["id"] = "DonkeyJJLove/not-glitchlab"
        with self.assertRaises(EnterpriseModelError):
            self.snapshot(wrong)
        with self.assertRaises(EnterpriseModelError):
            self.snapshot(capability="deploy.production")

    def test_manifest_digest_change_fails_closed(self):
        changed = copy.deepcopy(MANIFEST)
        changed["capabilities"].append("unexpected.capability")
        with self.assertRaises(EnterpriseModelError):
            self.snapshot(changed)

    def test_partial_conformance_cannot_be_promoted(self):
        result = current_partial_conformance()
        self.assertEqual((result.overall, result.promotion_decision), ("PARTIAL", "HOLD"))
        with self.assertRaises(EnterpriseModelError):
            ConformanceResult("PASS", "PASS", "PASS", "PASS", "UNKNOWN", "UNKNOWN",
                              "UNKNOWN", "UNKNOWN", "PASS", "PROMOTE").validate()
        failed = ConformanceResult("FAIL", "PASS", "PASS", "PASS", "UNKNOWN", "UNKNOWN",
                                   "UNKNOWN", "UNKNOWN", "FAIL", "HOLD").validate()
        self.assertEqual(failed.overall, "FAIL")

    def test_controlled_change_gate_can_run_without_executing_effect(self):
        builder = AgentSpec("builder", "1.0.0", "builder", "dry-run", ("code.write",),
                            "external_write", "test",
                            ("DecisionProposed", "OutcomeObserved"), max_cost_units=1.0)
        verifier = AgentSpec("verifier", "1.0.0", "verifier", "dry-run",
                             ("security.verify",), is_verifier=True)
        mission = MissionSpec("rccm-1d", "controlled change dry-run", ("code.write",),
                              "external_write", "AMBER", 2, 1.0, True, 3.0)
        agents = {"builder": builder, "verifier": verifier}
        swarm = SwarmPlanner().plan(mission, list(agents.values()))
        proposal = ActionProposal("proposal:rccm-1d", mission.mission_id, swarm.swarm_id,
                                  "builder", "code.write", "external_write", "git.change",
                                  "glitchlab:dry-run", True, ("evidence:glitchlab",),
                                  ("DecisionProposed", "OutcomeObserved"), "verifier",
                                  "sha256:requested-effect")
        decision = ExecutionControlPlane().evaluate(
            proposal=proposal, mission=mission, swarm=swarm, agents=agents,
            policy_ids=("policy:rccm-1d-read-only",),
            observed_event_types=("DecisionProposed", "OutcomeObserved"),
            gate_event_id="gate:rccm-1d",
        )
        self.assertEqual(decision.decision, "ALLOW")
        snapshot, _ = self.snapshot()
        result = current_partial_conformance()
        receipt = ControlledChangeDryRunReceipt(
            snapshot.provider_id, snapshot.provider_commit, snapshot.manifest_digest,
            proposal.proposal_id, decision.gate_event_id, decision.decision,
            proposal.payload_digest or "sha256:none", result.digest(),
        ).validate(proposal, decision)
        self.assertFalse(receipt.executed)
        self.assertIsNone(receipt.actual_effect_digest)
        with self.assertRaises(EnterpriseModelError):
            dataclasses.replace(receipt, proposal_id="proposal:other").validate(proposal, decision)

    def test_dry_run_receipt_cannot_claim_actual_effect(self):
        with self.assertRaises(EnterpriseModelError):
            ControlledChangeDryRunReceipt(
                PROVIDER, COMMIT, MANIFEST_DIGEST, "p", "g", "ALLOW", "sha256:req",
                current_partial_conformance().digest(), True, "sha256:effect",
            ).validate()
