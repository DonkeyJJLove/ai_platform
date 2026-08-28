from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import unittest
from unittest.mock import patch

from cyber_lion.contracts.independent_evidence_origin import (
    EXTERNAL_PRODUCER_CONTROL_DOMAIN_CLASS,
    EXTERNAL_PRODUCER_KEY_STORAGE_CLASS,
    EXTERNAL_PRODUCER_PROVENANCE_CLASS,
    ExternalEvidenceProducerObservation,
    IndependentEvidenceOriginContractError,
    IndependentEvidenceOriginReceipt,
    origin_receipt_digest,
)
import cyber_lion.enterprise.independent_evidence_origin as origin


T0 = "2026-08-28T00:00:00Z"
T1 = "2026-08-28T00:01:00Z"
T2 = "2026-08-28T00:02:00Z"
SHA = "2df1c99ff523c7a98262b7fc8dc1c8f7d457a5ab"
TREE = "e218efcda4b208c990b27b33e63ec294242c34fb"
H1 = "a" * 64
H2 = "b" * 64


def observation(**changes) -> ExternalEvidenceProducerObservation:
    profile = origin.canonical_external_evidence_producer_profile()
    values = dict(
        producer_id=profile.producer_id,
        producer_instance_id="external-origin-instance-01",
        producer_subject_id="external-origin-producer-01",
        trust_anchor_id=profile.trust_anchor_id,
        algorithm=profile.algorithm,
        public_key_sha256=profile.public_key_sha256,
        control_domain_class=profile.control_domain_class,
        key_storage_class=profile.key_storage_class,
        provenance_class=profile.provenance_class,
        provider_bindings=profile.provider_bindings,
        key_material_exportable=False,
        key_material_on_lion_host=False,
        key_material_in_repository=False,
        consumer_can_sign=False,
        producer_ready=True,
        observation_channel_ready=True,
        observed_at=T1,
    )
    values.update(changes)
    return ExternalEvidenceProducerObservation(**values)


def request(*, requester="provisioning-requester", consumer="lion-origin-consumer", requested_at=T0):
    return origin.derive_external_evidence_producer_provisioning_request(
        request_id="external-origin-provisioning-01",
        candidate_sha=SHA,
        candidate_tree=TREE,
        requester_subject_id=requester,
        consumer_subject_id=consumer,
        requested_at=requested_at,
    )


def admitted(obs: ExternalEvidenceProducerObservation | None = None):
    obs = (obs or observation()).validate()
    req = request()
    receipt = origin.ExternalEvidenceProducerProvisioningBoundary.admit(
        req,
        obs,
        expected_candidate_sha=SHA,
        expected_candidate_tree=TREE,
        issued_at=T2,
    )
    return req, obs, receipt


def origin_receipt(instance="external-origin-instance-01") -> IndependentEvidenceOriginReceipt:
    provider = dict(origin.CANONICAL_PROVIDER_BINDINGS)[origin.ORIGIN_CANDIDATE_TREE]
    nonce = sha256(b"external-origin-test-nonce").hexdigest()
    digest = origin_receipt_digest(
        provider_id=provider,
        provider_instance_id=instance,
        trust_anchor_id=origin.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        algorithm=origin.CANONICAL_ORIGIN_ALGORITHM,
        observation_id="external-tree-observation-01",
        observation_kind=origin.ORIGIN_CANDIDATE_TREE,
        observed_object_identity="0" * 40,
        observed_object_digest=H1,
        payload_digest=H2,
        issued_at=T2,
        nonce=nonce,
    )
    return IndependentEvidenceOriginReceipt(
        provider_id=provider,
        provider_instance_id=instance,
        trust_anchor_id=origin.CANONICAL_ORIGIN_TRUST_ANCHOR_ID,
        algorithm=origin.CANONICAL_ORIGIN_ALGORITHM,
        observation_id="external-tree-observation-01",
        observation_kind=origin.ORIGIN_CANDIDATE_TREE,
        observed_object_identity="0" * 40,
        observed_object_digest=H1,
        payload_digest=H2,
        issued_at=T2,
        nonce=nonce,
        receipt_digest=digest,
        signature_hex="0" * 512,
    ).validate()


class ExternalEvidenceProducerProvisioningTests(unittest.TestCase):
    def test_profile_is_exactly_bound_to_pinned_verifier(self):
        profile = origin.canonical_external_evidence_producer_profile()
        self.assertEqual(profile.trust_anchor_id, origin.CANONICAL_ORIGIN_TRUST_ANCHOR_ID)
        self.assertEqual(profile.algorithm, origin.CANONICAL_ORIGIN_ALGORITHM)
        self.assertEqual(profile.public_key_sha256, origin.origin_public_key_fingerprint())
        self.assertEqual(profile.provider_bindings, origin.CANONICAL_PROVIDER_BINDINGS)
        self.assertEqual(
            profile.public_key_sha256,
            "f822bed0c7ea1d9ff7e591bc930ce5b56a118c73663196bc1a21a31c4b00b779",
        )

    def test_valid_handoff_is_evidence_only_and_carries_no_effect_authority(self):
        req, obs, receipt = admitted()
        self.assertEqual(receipt.request_digest, req.digest())
        self.assertEqual(receipt.observation_digest, obs.digest())
        self.assertEqual(receipt.producer_instance_id, obs.producer_instance_id)
        self.assertIs(receipt.evidence_only, True)
        self.assertIs(receipt.effect_authority, False)
        self.assertIs(receipt.secret_material_present, False)
        public = {name for name in dir(receipt) if not name.startswith("_")}
        self.assertFalse(public & {"execute", "apply", "sign", "mint"})

    def test_externality_key_storage_and_provider_substitution_fail_closed(self):
        invalid = (
            {"control_domain_class": "LION_HOST"},
            {"key_storage_class": "EXPORTABLE_FILE"},
            {"provenance_class": "TEST_ONLY"},
            {"key_material_exportable": True},
            {"key_material_on_lion_host": True},
            {"key_material_in_repository": True},
            {"consumer_can_sign": True},
            {"public_key_sha256": "c" * 64},
            {"trust_anchor_id": "caller-anchor"},
            {"algorithm": "caller-algorithm"},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                obs = observation(**changes)
                if changes.keys() & {
                    "control_domain_class", "key_storage_class", "provenance_class",
                    "key_material_exportable", "key_material_on_lion_host",
                    "key_material_in_repository", "consumer_can_sign",
                }:
                    with self.assertRaises(IndependentEvidenceOriginContractError):
                        obs.validate()
                else:
                    obs.validate()
                    with self.assertRaises(origin.IndependentEvidenceOriginError):
                        origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                            request(), obs,
                            expected_candidate_sha=SHA,
                            expected_candidate_tree=TREE,
                            issued_at=T2,
                        )

        reversed_bindings = tuple(reversed(origin.CANONICAL_PROVIDER_BINDINGS))
        obs = observation(provider_bindings=reversed_bindings).validate()
        with self.assertRaises(origin.IndependentEvidenceOriginError):
            origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                request(), obs,
                expected_candidate_sha=SHA,
                expected_candidate_tree=TREE,
                issued_at=T2,
            )

    def test_role_readiness_currentness_and_chronology_are_fail_closed(self):
        with self.assertRaises(origin.IndependentEvidenceOriginError):
            origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                request(), observation(producer_subject_id="lion-origin-consumer").validate(),
                expected_candidate_sha=SHA, expected_candidate_tree=TREE, issued_at=T2,
            )
        for changes in ({"producer_ready": False}, {"observation_channel_ready": False}):
            with self.subTest(changes=changes), self.assertRaises(origin.IndependentEvidenceOriginError):
                origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                    request(), observation(**changes).validate(),
                    expected_candidate_sha=SHA, expected_candidate_tree=TREE, issued_at=T2,
                )
        with self.assertRaises(origin.IndependentEvidenceOriginError):
            origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                request(), observation().validate(),
                expected_candidate_sha="f" * 40, expected_candidate_tree=TREE, issued_at=T2,
            )
        with self.assertRaises(origin.IndependentEvidenceOriginError):
            origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                request(), observation().validate(),
                expected_candidate_sha=SHA, expected_candidate_tree="f" * 40, issued_at=T2,
            )
        with self.assertRaises(origin.IndependentEvidenceOriginError):
            origin.ExternalEvidenceProducerProvisioningBoundary.admit(
                request(requested_at=T2), observation(observed_at=T0).validate(),
                expected_candidate_sha=SHA, expected_candidate_tree=TREE, issued_at=T1,
            )

    def test_requester_consumer_collision_is_unrepresentable(self):
        with self.assertRaises(IndependentEvidenceOriginContractError):
            request(requester="same-subject", consumer="same-subject")

    def test_verified_origin_must_bind_exact_provisioned_instance(self):
        _, obs, provisioned = admitted()
        good = origin_receipt()
        with patch.object(origin, "verify_independent_evidence_origin", return_value=good) as verify:
            result = origin.ExternalEvidenceProducerProvisioningBoundary.verify_provisioned_origin(
                good,
                provisioned,
                obs,
                observation_kind=origin.ORIGIN_CANDIDATE_TREE,
                observed_object_identity=good.observed_object_identity,
                observed_object_digest=good.observed_object_digest,
                payload_digest=good.payload_digest,
            )
            self.assertIs(result, good)
            verify.assert_called_once()

        forged = origin_receipt(instance="attacker-instance")
        with patch.object(origin, "verify_independent_evidence_origin", return_value=forged) as verify:
            with self.assertRaises(origin.IndependentEvidenceOriginError):
                origin.ExternalEvidenceProducerProvisioningBoundary.verify_provisioned_origin(
                    forged,
                    provisioned,
                    obs,
                    observation_kind=origin.ORIGIN_CANDIDATE_TREE,
                    observed_object_identity=forged.observed_object_identity,
                    observed_object_digest=forged.observed_object_digest,
                    payload_digest=forged.payload_digest,
                )
            verify.assert_not_called()

    def test_public_provisioning_api_exposes_no_secret_or_effect_selector(self):
        forbidden = {
            "key_material", "credential", "endpoint", "command", "destination",
            "signer", "provider_selector", "verifier", "authority",
        }
        for fn in (
            origin.derive_external_evidence_producer_provisioning_request,
            origin.ExternalEvidenceProducerProvisioningBoundary.admit,
            origin.ExternalEvidenceProducerProvisioningBoundary.verify_provisioned_origin,
        ):
            with self.subTest(fn=fn.__name__):
                self.assertFalse(set(inspect.signature(fn).parameters) & forbidden)
        public = {
            name for name in dir(origin.ExternalEvidenceProducerProvisioningBoundary)
            if not name.startswith("_")
        }
        self.assertFalse(public & {"mint", "sign", "execute", "apply", "provision_key"})


if __name__ == "__main__":
    unittest.main()
