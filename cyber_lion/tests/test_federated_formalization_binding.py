from dataclasses import replace
import unittest

from cyber_lion.contracts.federated_formalization_binding import (
    FederatedFormalizationBinding,
    FederatedFormalizationBindingError,
    RepositoryFormalizationDisposition,
    fleet_dependency_graph_digest,
)
from cyber_lion.contracts.repository_expansion import (
    FleetBaseline,
    RegisteredRepository,
    RepositoryBaseline,
    RepositoryDependencyEdge,
)

A="a"*40
B="b"*40
C="c"*40


def fleet():
    edge=RepositoryDependencyEdge(
        source="DonkeyJJLove/ai_platform",
        target="DonkeyJJLove/swarm",
        relation="CONSUMES",
        contract="execution mesh",
        version_assumption=None,
        failure_mode="runtime contract drift",
        security_impact="runtime admission mismatch",
        test_coverage="cross-repo contract",
        evidence="cyber_lion/registry/repositories.json",
    )
    return FleetBaseline(
        schema_version="1.0.0",
        baseline_id="v15-federation-test",
        registered=(
            RegisteredRepository("DonkeyJJLove/ai_platform","master",A,B),
            RegisteredRepository("DonkeyJJLove/swarm","master",C,B),
        ),
        observations=(
            RepositoryBaseline(
                "1.0.0","DonkeyJJLove/ai_platform","master",A,B,None,
                "UNKNOWN","UNKNOWN","NONE",(),
                ("DonkeyJJLove/swarm",),(),("formalization",),("proposal != authority",),True,(),
            ),
            RepositoryBaseline(
                "1.0.0","DonkeyJJLove/swarm","master",C,B,None,
                "UNKNOWN","UNKNOWN","NONE",(),
                (),("DonkeyJJLove/ai_platform",),("runtime",),("workload != authority",),True,(),
            ),
        ),
        edges=(edge,),
    ).validate()


def binding():
    f=fleet()
    return FederatedFormalizationBinding(
        binding_id="ffb:test",
        formalization_manifest_digest="1"*64,
        fleet_baseline_digest=f.baseline_digest(),
        dependency_graph_digest=fleet_dependency_graph_digest(f),
        repositories=(
            RepositoryFormalizationDisposition("DonkeyJJLove/ai_platform",A,B,"UPDATE",("architecture-projection",)),
            RepositoryFormalizationDisposition("DonkeyJJLove/swarm",C,B,"VALIDATE_ONLY",()),
        ),
    ).sealed(f)


class FederatedFormalizationBindingTests(unittest.TestCase):
    def test_exact_federation_binding_passes(self):
        f=fleet(); b=binding()
        self.assertEqual(b.validate(f),b)
        self.assertEqual(len(b.binding_digest),64)
        self.assertEqual(b.authority_effect,"NONE")

    def test_missing_repository_is_denied(self):
        f=fleet(); b=binding()
        with self.assertRaisesRegex(FederatedFormalizationBindingError,"exactly cover"):
            replace(b,repositories=b.repositories[:1],binding_digest="").sealed(f)

    def test_repository_head_substitution_is_denied(self):
        f=fleet(); b=binding()
        bad=replace(b.repositories[1],baseline_head=A)
        with self.assertRaisesRegex(FederatedFormalizationBindingError,"baseline substitution"):
            replace(b,repositories=(b.repositories[0],bad),binding_digest="").sealed(f)

    def test_dependency_graph_substitution_is_denied(self):
        f=fleet(); b=binding()
        with self.assertRaisesRegex(FederatedFormalizationBindingError,"dependency graph digest"):
            replace(b,dependency_graph_digest="2"*64,binding_digest="").sealed(f)

    def test_binding_cannot_carry_authority(self):
        f=fleet(); b=binding()
        with self.assertRaisesRegex(FederatedFormalizationBindingError,"authority/effect"):
            replace(b,authority_effect="WRITE",binding_digest="").sealed(f)

    def test_not_applicable_cannot_require_artifacts(self):
        with self.assertRaisesRegex(FederatedFormalizationBindingError,"NOT_APPLICABLE"):
            RepositoryFormalizationDisposition(
                "DonkeyJJLove/swarm",C,B,"NOT_APPLICABLE",("x",)
            ).validate()


if __name__=="__main__":
    unittest.main()
