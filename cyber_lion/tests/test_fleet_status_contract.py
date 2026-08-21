from __future__ import annotations

import json
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_status import (
    FleetStatusContractError,
    FleetStatusIdentity,
    TrustedVerificationEvidence,
    VerificationTrustPins,
)


H40 = "a" * 40
H64 = "b" * 64


class FleetStatusContractTests(unittest.TestCase):
    def identity(self) -> FleetStatusIdentity:
        return FleetStatusIdentity(
            "drone-1", "executor-1", "mission-1", "parent-1", "DonkeyJJLove/ai_platform",
            H40, "c" * 40, "mission/fcsr", ("**",), ("cyber_lion/**",), "sandbox-1",
        )

    def evidence(self, **overrides) -> TrustedVerificationEvidence:
        values = dict(
            verification_id="verify-1", mission_id="mission-1", drone_id="drone-1", executor_id="executor-1",
            verifier_id="verifier-1", verifier_identity_digest="1"*64, verifier_implementation_digest="2"*64,
            trust_anchor_id="anchor-1", trust_anchor_digest="3"*64, verification_state="PASS",
            evidence_digest="4"*64, source_provenance_ref="prov-1", epistemic_class="ANCHORED",
            observed_at="2026-08-21T08:00:00+00:00",
        )
        values.update(overrides)
        return TrustedVerificationEvidence(**values)

    def test_identity_is_immutable_and_validates(self):
        obj = self.identity().validate()
        with self.assertRaises(Exception):
            obj.drone_id = "other"
        self.assertEqual(len(obj.digest()), 64)

    def test_verifier_cannot_equal_drone(self):
        with self.assertRaises(FleetStatusContractError):
            self.evidence(verifier_id="drone-1").validate()

    def test_verifier_cannot_equal_executor(self):
        with self.assertRaises(FleetStatusContractError):
            self.evidence(verifier_id="executor-1").validate()

    def test_pass_cannot_be_inferred(self):
        with self.assertRaises(FleetStatusContractError):
            self.evidence(epistemic_class="INFERRED").validate()

    def test_trust_pins_are_exact(self):
        pins = VerificationTrustPins("verifier-1", "1"*64, "2"*64, "anchor-1", "3"*64)
        self.assertIs(pins.validate(), pins)

    def test_wire_schema_is_closed_and_typed(self):
        p = Path(__file__).parents[1] / "contracts" / "v1" / "fleet_status_snapshot.schema.json"
        schema = json.loads(p.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        item = schema["properties"]["drone_records"]["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(set(item["required"]), set(item["properties"]))
        self.assertFalse(schema["properties"]["aggregate"]["additionalProperties"])
        self.assertFalse(schema["properties"]["anomalies"]["items"]["additionalProperties"])

    def test_schema_rejects_extra_field_by_contract_shape(self):
        p = Path(__file__).parents[1] / "contracts" / "v1" / "fleet_status_snapshot.schema.json"
        schema = json.loads(p.read_text(encoding="utf-8"))
        self.assertIs(schema["properties"]["drone_records"]["items"]["additionalProperties"], False)
        self.assertIn("mission_status", schema["properties"]["drone_records"]["items"]["properties"])


if __name__ == "__main__":
    unittest.main()
