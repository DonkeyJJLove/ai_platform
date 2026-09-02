from __future__ import annotations

from dataclasses import replace
import unittest

from cyber_lion.contracts.fleet_effect_budget import (
    FleetEffectBudgetContractError,
    FleetEffectBudgetSnapshot,
    FleetEffectEnvelope,
    FleetEffectReservation,
    FleetEffectReservationRequest,
)


T0 = "2026-09-02T08:00:00+00:00"
T1 = "2026-09-02T09:00:00+00:00"
POLICY = "a" * 64
AUTH = "b" * 64
ENV_DIGEST = "c" * 64


def envelope() -> FleetEffectEnvelope:
    return FleetEffectEnvelope("env-1", "fleet-1", 1, POLICY, 2, 2, 2, 1, T0, T1).validate()


def request() -> FleetEffectReservationRequest:
    return FleetEffectReservationRequest(
        "res-1", "eff-1", "mission-1", "executor-1", "runtime-1",
        "DonkeyJJLove/ai_platform", "mission/budget-r1", ("cyber_lion/a.py",),
        AUTH, 4, 1, T0, T1,
    ).validate()


class FleetEffectBudgetContractTests(unittest.TestCase):
    def test_envelope_digest_deterministic(self):
        value = envelope()
        self.assertEqual(value.digest(), envelope().digest())

    def test_envelope_requires_positive_limits(self):
        with self.assertRaises(FleetEffectBudgetContractError):
            replace(envelope(), max_concurrent_writers=0).validate()

    def test_request_binds_scope_generation_and_authority_effect_key(self):
        value = request()
        self.assertEqual(value.repository, "DonkeyJJLove/ai_platform")
        self.assertEqual(value.branch, "mission/budget-r1")
        self.assertEqual(value.envelope_generation, 1)
        self.assertEqual(value.authority_effect_key, AUTH)
        self.assertEqual(value.changed_paths, ("cyber_lion/a.py",))

    def test_request_rejects_unsafe_path(self):
        with self.assertRaises(FleetEffectBudgetContractError):
            replace(request(), changed_paths=("../escape",)).validate()

    def test_request_rejects_bad_authority_key(self):
        with self.assertRaises(FleetEffectBudgetContractError):
            replace(request(), authority_effect_key="not-a-digest").validate()

    def test_terminal_reservation_requires_finalized_at(self):
        r = FleetEffectReservation(
            "res-1", request().digest(), "eff-1", "mission-1", "executor-1", "runtime-1",
            "DonkeyJJLove/ai_platform", "mission/budget-r1", ("cyber_lion/a.py",), AUTH, 4,
            "env-1", 1, ENV_DIGEST, "FINALIZED", T0, T1, None,
        )
        with self.assertRaises(FleetEffectBudgetContractError):
            r.validate()

    def test_snapshot_rejects_duplicate_active_ids(self):
        s = FleetEffectBudgetSnapshot("env-1", 1, ENV_DIGEST, 2, (), (), (), ("r", "r"), T0)
        with self.assertRaises(FleetEffectBudgetContractError):
            s.validate()


if __name__ == "__main__":
    unittest.main()
