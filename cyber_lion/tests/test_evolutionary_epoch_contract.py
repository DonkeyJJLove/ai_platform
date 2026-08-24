from dataclasses import replace
import unittest

from cyber_lion.contracts.evolutionary_epoch import (
    EpochTransition,
    EvolutionaryEpochContractError,
    RnDEventProjection,
    RnDGraphProjection,
)

H = "a" * 64
H2 = "b" * 64
H3 = "c" * 64


class EvolutionaryEpochContractTests(unittest.TestCase):
    def test_event_projection_is_domain_bound_and_authority_free(self):
        item = RnDEventProjection(
            projection_id="proj:1",
            record_type="Hypothesis",
            record_id="hyp:1",
            record_digest=H,
            event_id="evt:1",
            event_type="HypothesisGenerated",
            correlation_id="corr:1",
            causation_id=None,
            epistemic_state="UNDERSTOOD",
            provenance_refs=("evidence:1",),
        ).sealed()
        self.assertEqual(len(item.projection_digest), 64)
        item.validate()
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, authority_effective="write", projection_digest="").validate()
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, event_type="ActionExecuted", projection_digest="").validate()

    def test_graph_projection_forbids_authority_node_and_edge(self):
        item = RnDGraphProjection(
            projection_id="graph:1",
            record_type="Hypothesis",
            record_id="hyp:1",
            record_digest=H,
            event_id="evt:1",
            node_id="hyp:1",
            node_type="ARTIFACT",
            edge_ids=("edge:1",),
            edge_types=("DERIVED_FROM",),
            provenance_refs=("evidence:1",),
        ).sealed()
        item.validate()
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, node_type="AUTHORITY_RECORD", projection_digest="").validate()
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, edge_types=("AUTHORITY_PARENT_OF",), projection_digest="").validate()

    def test_epoch_transition_is_non_effectful_and_digest_bound(self):
        item = EpochTransition(
            epoch_id="E004",
            previous_epoch_id="E003",
            rnd_engine_state_digest=H,
            memory_head=H2,
            promotion_digest=H3,
            evolution_delta_digest=H,
            event_projection_digest=H2,
            graph_projection_digest=H3,
            state="MEMORY_COMMITTED",
        ).sealed()
        item.validate()
        self.assertEqual(item.authority_effect, "NONE")
        self.assertEqual(item.execution_effect, "NONE")
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, execution_effect="RUNTIME", transition_digest="").validate()
        with self.assertRaises(EvolutionaryEpochContractError):
            replace(item, transition_digest="0" * 64).validate()

    def test_same_inputs_same_projection_digest(self):
        kwargs = dict(
            projection_id="proj:deterministic",
            record_type="EvolutionDelta",
            record_id="delta:1",
            record_digest=H,
            event_id="evt:delta",
            event_type="DeltaDetected",
            correlation_id="corr:1",
            causation_id="evt:promotion",
            epistemic_state="FORMALISED",
            provenance_refs=("promotion:1",),
        )
        self.assertEqual(RnDEventProjection(**kwargs).sealed().projection_digest,
                         RnDEventProjection(**kwargs).sealed().projection_digest)


if __name__ == "__main__":
    unittest.main()
