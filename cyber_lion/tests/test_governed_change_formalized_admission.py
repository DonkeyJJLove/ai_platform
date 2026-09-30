from dataclasses import replace
import unittest

from cyber_lion.contracts.architecture_formalization_manifest import FormalizationProposalBinding
from cyber_lion.contracts.federated_formalization_binding import (
    FederatedFormalizationBinding,
    RepositoryFormalizationDisposition,
    fleet_dependency_graph_digest,
)
from cyber_lion.contracts.formalization_closure import ArtifactResult, CandidateBinding, FormalizationClosureRecord, GateResult
from cyber_lion.contracts.governed_change_proposal import GovernedChangeProposal, SCHEMA_VERSION
from cyber_lion.contracts.repository_expansion import FleetBaseline, RegisteredRepository, RepositoryBaseline, RepositoryDependencyEdge
from cyber_lion.enterprise.governed_change_admission import GovernedChangeAdmissionEngine, GovernedChangeAdmissionError
from cyber_lion.tests.formalization_test_support import registry, manifest
from cyber_lion.architecture_projection.formalization import derive_required_formalization_set

A="a"*40
B="b"*40
C="c"*40


def proposal():
    return GovernedChangeProposal(
        schema_version=SCHEMA_VERSION,
        proposal_id="gcp:formalized",
        epoch_id="E005",
        source_delta_id="delta:architecture",
        source_delta_digest="1"*64,
        source_epoch_transition_digest="2"*64,
        source_memory_head="3"*64,
        source_promotion_digest="4"*64,
        source_pdp_decision_digest="5"*64,
        target_component="architecture knowledge",
        candidate_scope=("cyber_lion/architecture_projection/architecture_knowledge.py",),
        dependency_ids=("formalization",),
        falsification_conditions=("formalization must close",),
        evidence_refs=("obs:architecture",),
        risk_class="AMBER",
    ).sealed()


def fleet():
    edge=RepositoryDependencyEdge(
        "DonkeyJJLove/swarm","DonkeyJJLove/ai_platform","CONSUMES",
        "global architecture owner",None,
        "stale global architecture","semantic drift",
        "federated-formalization-test","swarm:cyber-lion.repository.json",
    )
    return FleetBaseline(
        "1.0.0","fleet:formalized",
        (
            RegisteredRepository("DonkeyJJLove/ai_platform","master",A,B),
            RegisteredRepository("DonkeyJJLove/swarm","master",C,B),
        ),
        (
            RepositoryBaseline("1.0.0","DonkeyJJLove/ai_platform","master",A,B,None,"UNKNOWN","UNKNOWN","NONE",(),(),("DonkeyJJLove/swarm",),("architecture",),("proposal != authority",),True,()),
            RepositoryBaseline("1.0.0","DonkeyJJLove/swarm","master",C,B,None,"UNKNOWN","UNKNOWN","NONE",(),("DonkeyJJLove/ai_platform",),(),("runtime",),("workload != authority",),True,()),
        ),
        (edge,),
    ).validate()


def closed_formalization():
    reg=registry()
    man=manifest(reg)
    required=derive_required_formalization_set(man,reg)
    results=tuple(
        ArtifactResult(
            item.artifact_id,item.classification,
            "NOT_APPLICABLE" if item.classification=="NOT_APPLICABLE" else "PASS",
            ("evidence:"+item.artifact_id,),
        )
        for item in required.items
    )
    closure=FormalizationClosureRecord(
        "fcr:formalized",
        CandidateBinding("6"*64,"7"*40,"8"*40,"9"*64),
        man.manifest_digest,
        results,
        "PASS","PASS","PASS","PASS",
        (GateResult("t1","PASS",("test",)),),
        (GateResult("e1","PASS",("eval",)),),
        "CURRENT_CANDIDATE",(),"PASS",
    ).sealed(man,reg)
    return reg,man,closure


def federation_binding(man):
    f=fleet()
    value=FederatedFormalizationBinding(
        "ffb:formalized",man.manifest_digest,f.baseline_digest(),fleet_dependency_graph_digest(f),
        (
            RepositoryFormalizationDisposition("DonkeyJJLove/ai_platform",A,B,"UPDATE",("architecture-projection",)),
            RepositoryFormalizationDisposition("DonkeyJJLove/swarm",C,B,"VALIDATE_ONLY",()),
        ),
    ).sealed(f)
    return f,value


class GovernedChangeFormalizedAdmissionTests(unittest.TestCase):
    def test_formalized_path_derives_normal_admission_after_all_bindings_pass(self):
        p=proposal();reg,man,closure=closed_formalization();f,fb=federation_binding(man)
        pb=FormalizationProposalBinding("fpb:test",p.proposal_digest,man.manifest_digest).sealed()
        req=GovernedChangeAdmissionEngine().derive_formalized_request(
            proposal=p,action_class="BUILD_CANDIDATE",trusted_repository="DonkeyJJLove/ai_platform",
            formalization_manifest=man,formalization_registry=reg,proposal_binding=pb,
            formalization_closure=closure,federated_binding=fb,fleet_baseline=f,
        )
        self.assertEqual(req.proposal_digest,p.proposal_digest)
        self.assertEqual(req.authority_effect,"NONE")

    def test_proposal_substitution_is_denied(self):
        p=proposal();reg,man,closure=closed_formalization();f,fb=federation_binding(man)
        pb=FormalizationProposalBinding("fpb:test","f"*64,man.manifest_digest).sealed()
        with self.assertRaisesRegex(GovernedChangeAdmissionError,"proposal substitution"):
            GovernedChangeAdmissionEngine().derive_formalized_request(
                proposal=p,action_class="BUILD_CANDIDATE",trusted_repository="DonkeyJJLove/ai_platform",
                formalization_manifest=man,formalization_registry=reg,proposal_binding=pb,
                formalization_closure=closure,federated_binding=fb,fleet_baseline=f,
            )

    def test_federation_manifest_substitution_is_denied(self):
        p=proposal();reg,man,closure=closed_formalization();f,fb=federation_binding(man)
        pb=FormalizationProposalBinding("fpb:test",p.proposal_digest,man.manifest_digest).sealed()
        bad=replace(fb,formalization_manifest_digest="e"*64,binding_digest="")
        with self.assertRaises(Exception):
            GovernedChangeAdmissionEngine().derive_formalized_request(
                proposal=p,action_class="BUILD_CANDIDATE",trusted_repository="DonkeyJJLove/ai_platform",
                formalization_manifest=man,formalization_registry=reg,proposal_binding=pb,
                formalization_closure=closure,federated_binding=bad,fleet_baseline=f,
            )

    def test_not_applicable_repository_cannot_request_admission(self):
        p=proposal();reg,man,closure=closed_formalization();f,_=federation_binding(man)
        fb=FederatedFormalizationBinding(
            "ffb:na",man.manifest_digest,f.baseline_digest(),fleet_dependency_graph_digest(f),
            (
                RepositoryFormalizationDisposition("DonkeyJJLove/ai_platform",A,B,"UPDATE",("architecture-projection",)),
                RepositoryFormalizationDisposition("DonkeyJJLove/swarm",C,B,"NOT_APPLICABLE",()),
            ),
        ).sealed(f)
        pb=FormalizationProposalBinding("fpb:test",p.proposal_digest,man.manifest_digest).sealed()
        with self.assertRaisesRegex(GovernedChangeAdmissionError,"NOT_APPLICABLE"):
            GovernedChangeAdmissionEngine().derive_formalized_request(
                proposal=p,action_class="RUN_TEST",trusted_repository="DonkeyJJLove/swarm",
                formalization_manifest=man,formalization_registry=reg,proposal_binding=pb,
                formalization_closure=closure,federated_binding=fb,fleet_baseline=f,
            )


if __name__=="__main__":
    unittest.main()
