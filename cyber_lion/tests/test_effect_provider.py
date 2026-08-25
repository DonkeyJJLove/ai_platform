import unittest
from dataclasses import replace

from cyber_lion.contracts.effect import EffectContractError,EffectObservation,EffectReconciliation
from cyber_lion.contracts.repository_mutation import ExactRefAttachIntent
from cyber_lion.contracts.runtime_enforcement import RequestedRuntimeEffect,RuntimeAdmission
from cyber_lion.enterprise.effect_provider import EffectProviderAdapterError,F009RuntimeEffectAdapter,RepositoryMutationEffectAdapter


class EffectProviderTests(unittest.TestCase):
    def attach(self):
        return ExactRefAttachIntent(
            repository="DonkeyJJLove/ai_platform",
            branch="master",
            mission_id="E006",
            expected_head_sha="a"*40,
            expected_parent_sha="a"*40,
            candidate_commit_sha="b"*40,
            candidate_tree_sha="c"*40,
            candidate_verification_digest="1"*64,
        ).validate()

    def runtime_effect(self):
        return RequestedRuntimeEffect(
            effect_id="runtime-effect-1",
            proposal_id="proposal-1",
            mission_id="E006",
            policy_binding="policy:v1",
            authority_lineage_digest="1"*64,
            requested_authority="local_write",
            action_class="write_file",
            resource="workspace:/result.txt",
            payload_digest="2"*64,
            observability_state="HEALTHY",
            runtime_identity_digest="3"*64,
        ).validate()

    def admission(self,effect=None):
        effect=effect or self.runtime_effect()
        return RuntimeAdmission(
            admission_id="admission-1",
            request_id="request-1",
            gate_event_id="gate-1",
            proposal_id=effect.proposal_id,
            gate_decision_digest="4"*64,
            pdp_receipt_digest="5"*64,
            pdp_evidence_digest="6"*64,
            live_authority_digest="7"*64,
            authority_lineage_digest=effect.authority_lineage_digest,
            policy_binding=effect.policy_binding,
            effective_authority=effect.requested_authority,
            requested_effect_digest=effect.digest(),
            runtime_identity_digest=effect.runtime_identity_digest,
            provisioned_executor_digest="8"*64,
            observability_state=effect.observability_state,
            replay_key="9"*64,
        ).sealed()

    def test_repository_effect_normalizes_exact_intent(self):
        intent=self.attach()
        contract=RepositoryMutationEffectAdapter().normalize(
            intent=intent,requested_authority="local_write",
            authority_evidence_digest="2"*64,currentness_evidence_digest="3"*64,
            pep_identity_digest="4"*64,execution_identity_digest="5"*64,
            required_observer_ids=("repo-observer",),required_observation_channels=("ref-state",),
        )
        self.assertEqual(contract.exact_effect_digest,intent.digest())
        self.assertTrue(contract.reconciliation_required)
        self.assertEqual(contract.effect_class,"repository.fast_forward_ref")

    def test_f009_effect_normalizes_exact_runtime_admission(self):
        effect=self.runtime_effect();admission=self.admission(effect)
        contract=F009RuntimeEffectAdapter().normalize(
            effect=effect,admission=admission,currentness_evidence_digest="a"*64,
            pep_identity_digest="b"*64,required_observer_ids=("runtime-observer",),
            required_observation_channels=("effect-target-state",),
        )
        self.assertEqual(contract.exact_effect_digest,effect.digest())
        self.assertEqual(contract.authority_evidence_digest,admission.live_authority_digest)
        self.assertEqual(contract.execution_identity_digest,effect.runtime_identity_digest)

    def test_runtime_effect_substitution_denied(self):
        effect=self.runtime_effect();admission=self.admission(effect)
        changed=replace(effect,payload_digest="f"*64)
        with self.assertRaises(EffectProviderAdapterError):
            F009RuntimeEffectAdapter().normalize(
                effect=changed,admission=admission,currentness_evidence_digest="a"*64,
                pep_identity_digest="b"*64,required_observer_ids=("runtime-observer",),
                required_observation_channels=("effect-target-state",),
            )

    def test_observer_requirement_is_fail_closed(self):
        with self.assertRaises(EffectProviderAdapterError):
            RepositoryMutationEffectAdapter().normalize(
                intent=self.attach(),requested_authority="local_write",
                authority_evidence_digest="2"*64,currentness_evidence_digest="3"*64,
                pep_identity_digest="4"*64,execution_identity_digest="5"*64,
                required_observer_ids=(),required_observation_channels=("ref-state",),
            )

    def test_observation_cannot_be_inferred_or_simulated(self):
        with self.assertRaises(EffectContractError):
            EffectObservation(
                observation_id="o",effect_contract_digest="1"*64,observer_id="obs",
                observer_identity_digest="2"*64,observed_effect_digest="3"*64,
                channel="state",observed_state_digest="4"*64,observed_at="t",
                epistemic_state="SIMULATED",
            ).validate()

    def test_match_reconciliation_requires_exact_effect_identity(self):
        with self.assertRaises(EffectContractError):
            EffectReconciliation(
                reconciliation_id="r",effect_contract_digest="1"*64,
                expected_effect_digest="2"*64,observed_effect_digest="3"*64,
                observation_digests=("4"*64,),status="MATCH",reconciler_id="rec",
                reconciler_identity_digest="5"*64,reconciled_at="t",
            ).validate()

    def test_unknown_cannot_hide_exact_match(self):
        with self.assertRaises(EffectContractError):
            EffectReconciliation(
                reconciliation_id="r",effect_contract_digest="1"*64,
                expected_effect_digest="2"*64,observed_effect_digest="2"*64,
                observation_digests=("4"*64,),status="UNKNOWN",reconciler_id="rec",
                reconciler_identity_digest="5"*64,reconciled_at="t",
            ).validate()

    def test_adapters_are_normalizers_not_effectors(self):
        for adapter in (RepositoryMutationEffectAdapter(),F009RuntimeEffectAdapter()):
            self.assertFalse(hasattr(adapter,"execute"))
            self.assertFalse(hasattr(adapter,"attach"))
            self.assertFalse(hasattr(adapter,"authorize"))
            self.assertFalse(hasattr(adapter,"observe"))


if __name__=="__main__":unittest.main()
