from __future__ import annotations

from dataclasses import FrozenInstanceError
from hashlib import sha256
import unittest

from cyber_lion.contracts.fleet_status_sources import (
    FleetStatusSourceContractError,
    MissingStatusSource,
    ReconciledStatusFact,
    SourceConflict,
    StatusSourceBatch,
    StatusSourceIdentity,
    StatusSourceObservation,
    StatusSourcePin,
    StatusSourceRead,
    canonical_json,
)


class FleetStatusSourcesContractTests(unittest.TestCase):
    def identity(self, **overrides):
        values = dict(
            source_id="source-1", source_kind="FLEET_CONTROL", source_instance_id="instance-1",
            source_implementation_digest="1" * 64, trust_anchor_id="anchor-1",
        )
        values.update(overrides)
        return StatusSourceIdentity(**values)

    def observation(self, **overrides):
        values = dict(
            observation_id="obs-1", mission_id="mission-1", drone_id="drone-1", executor_id=None,
            runtime_id=None, repository="DonkeyJJLove/ai_platform", baseline_sha="a" * 40,
            dimension="MISSION", state="RUNNING", value_items=(("phase", "IMPLEMENT"),),
            provenance_ref="prov-1", evidence_digest="2" * 64, epistemic_class="OBSERVED",
        )
        values.update(overrides)
        return StatusSourceObservation(**values)

    def test_source_identity_is_immutable_and_digest_pinned(self):
        identity = self.identity().validate()
        with self.assertRaises(FrozenInstanceError):
            identity.source_id = "other"
        pin = StatusSourcePin(
            identity.source_id, identity.source_kind, identity.source_instance_id,
            identity.source_implementation_digest, identity.trust_anchor_id, identity.digest(),
        ).validate()
        self.assertEqual(pin.validate_identity(identity), identity)
        with self.assertRaises(FleetStatusSourceContractError):
            pin.validate_identity(self.identity(source_instance_id="substitute"))

    def test_observation_requires_sorted_unique_values_and_real_epistemic_class(self):
        candidate = self.observation()
        self.assertIs(candidate.validate(), candidate)
        with self.assertRaises(FleetStatusSourceContractError):
            self.observation(value_items=(("z", "1"), ("a", "2"))).validate()
        with self.assertRaises(FleetStatusSourceContractError):
            self.observation(epistemic_class="INFERRED").validate()

    def test_mission_bound_dimension_requires_mission_id(self):
        with self.assertRaises(FleetStatusSourceContractError):
            self.observation(mission_id=None, dimension="AUTHORITY").validate()
        self.observation(mission_id=None, dimension="CI").validate()

    def test_read_digest_binds_source_identity_time_and_observations(self):
        identity = self.identity().validate()
        read = StatusSourceRead(identity, "2026-08-21T10:00:00+00:00", (self.observation(),)).validate()
        changed = StatusSourceRead(identity, "2026-08-21T10:00:01+00:00", (self.observation(),)).validate()
        self.assertNotEqual(read.digest(), changed.digest())

    def test_batch_chain_is_exact_and_tamper_fails(self):
        identity = self.identity().validate()
        read = StatusSourceRead(identity, "2026-08-21T10:00:00+00:00", (self.observation(),)).validate()
        read_digest = read.digest()
        batch_digest = sha256(canonical_json({
            "source_identity_digest": identity.digest(), "source_sequence": 1,
            "source_observed_at": read.source_observed_at, "read_digest": read_digest,
        })).hexdigest()
        previous = "0" * 64
        chain = sha256((previous + batch_digest).encode("ascii")).hexdigest()
        batch = StatusSourceBatch(identity, 1, read.source_observed_at, read_digest, batch_digest, chain, previous, read.observations)
        self.assertIs(batch.validate(), batch)
        with self.assertRaises(FleetStatusSourceContractError):
            StatusSourceBatch(identity, 1, read.source_observed_at, read_digest, "f" * 64, chain, previous, read.observations).validate()

    def test_reconciled_fact_and_conflict_are_descriptive(self):
        fact = ReconciledStatusFact(
            "mission-1", "AUTHORITY", "ACTIVE", (("grant_id", "g1"),),
            ("authority-source",), ("authority-prov",), "ANCHORED",
        ).validate()
        self.assertEqual(len(fact.digest()), 64)
        conflict = SourceConflict(
            "conflict-1", "SOURCE_PROVENANCE_CONFLICT", "mission-1", "drone-1", "AUTHORITY",
            ("a", "b"), ("oa", "ob"), ("pa", "pb"), "2026-08-21T10:00:00+00:00",
        ).validate()
        self.assertEqual(len(conflict.digest()), 64)

    def test_missing_source_is_explicit_not_synthetic_state(self):
        missing = MissingStatusSource(
            "mission-1", "drone-1", "HEARTBEAT", ("HEARTBEAT",), "2026-08-21T10:00:00+00:00",
        ).validate()
        self.assertEqual(len(missing.digest()), 64)
        with self.assertRaises(FleetStatusSourceContractError):
            MissingStatusSource("mission-1", "drone-1", "HEARTBEAT", (), "2026-08-21T10:00:00+00:00").validate()


if __name__ == "__main__":
    unittest.main()
