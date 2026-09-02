from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone, timedelta
import tempfile
import threading
import unittest

from cyber_lion.contracts.fleet_effect_budget import FleetEffectEnvelope, FleetEffectReservationRequest
from cyber_lion.enterprise.fleet_effect_budget import FleetEffectBudgetError, FleetEffectBudgetStore


NOW = datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc)
POLICY = "a" * 64
IDENTITY = "b" * 64
IMPLEMENTATION = "c" * 64
CANDIDATE = "d" * 64


class Clock:
    def __init__(self, value=NOW):
        self.value = value
    def __call__(self):
        return self.value


def env(**kw):
    values = dict(
        envelope_id="env-1", fleet_id="fleet-1", generation=1, policy_digest=POLICY,
        max_concurrent_writers=2, max_active_repository_effects=2,
        max_active_branch_effects=2, max_active_path_effects=1,
        valid_from=(NOW - timedelta(minutes=1)).isoformat(),
        expires_at=(NOW + timedelta(hours=1)).isoformat(),
    )
    values.update(kw)
    return FleetEffectEnvelope(**values).validate()


def req(i: int, *, repository="DonkeyJJLove/ai_platform", branch="mission/budget-r1", path=None, generation=1):
    path = path or f"cyber_lion/{i}.py"
    return FleetEffectReservationRequest(
        reservation_id=f"res-{i}", effect_id=f"eff-{i}", candidate_digest=f"{i + 100:064x}",
        mission_id=f"mission-{i}", executor_id=f"executor-{i}", runtime_id=f"runtime-{i}",
        repository=repository, branch=branch, changed_paths=(path,), authority_effect_key=f"{i + 1:064x}",
        authority_epoch=4, envelope_generation=generation, requested_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(minutes=10)).isoformat(),
    ).validate()


class FleetEffectBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.store = FleetEffectBudgetStore(
            self.tmp.name + "/budget.db", envelope=env(), clock=self.clock,
            identity_digest=IDENTITY, implementation_digest=IMPLEMENTATION,
        )
    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_limit(self):
        self.store.reserve_exact(req(1))
        self.store.reserve_exact(req(2))
        snap = self.store.snapshot()
        self.assertEqual(snap.active_writers, 2)
        with self.assertRaises(FleetEffectBudgetError):
            self.store.reserve_exact(req(3))

    def test_replay_denied(self):
        r = req(1)
        self.store.reserve_exact(r)
        with self.assertRaises(FleetEffectBudgetError):
            self.store.reserve_exact(r)

    def test_stale_generation_denied(self):
        with self.assertRaises(FleetEffectBudgetError):
            self.store.reserve_exact(req(1, generation=2))

    def test_repository_limit(self):
        store = FleetEffectBudgetStore(
            self.tmp.name + "/repo.db", envelope=env(max_concurrent_writers=10, max_active_repository_effects=1),
            clock=self.clock, identity_digest=IDENTITY, implementation_digest=IMPLEMENTATION,
        )
        store.reserve_exact(req(1))
        with self.assertRaises(FleetEffectBudgetError):
            store.reserve_exact(req(2, branch="mission/other"))

    def test_branch_limit(self):
        store = FleetEffectBudgetStore(
            self.tmp.name + "/branch.db", envelope=env(max_concurrent_writers=10, max_active_repository_effects=10, max_active_branch_effects=1),
            clock=self.clock, identity_digest=IDENTITY, implementation_digest=IMPLEMENTATION,
        )
        store.reserve_exact(req(1))
        with self.assertRaises(FleetEffectBudgetError):
            store.reserve_exact(req(2))

    def test_path_limit(self):
        store = FleetEffectBudgetStore(
            self.tmp.name + "/path.db", envelope=env(max_concurrent_writers=10, max_active_repository_effects=10, max_active_branch_effects=10, max_active_path_effects=1),
            clock=self.clock, identity_digest=IDENTITY, implementation_digest=IMPLEMENTATION,
        )
        store.reserve_exact(req(1, path="cyber_lion/shared.py"))
        with self.assertRaises(FleetEffectBudgetError):
            store.reserve_exact(req(2, path="cyber_lion/shared.py"))

    def test_release_frees_budget_but_replay_remains_denied(self):
        reserved = self.store.reserve_exact(req(1))
        released = self.store.release(reserved.reservation_id)
        self.assertEqual(released.state, "RELEASED")
        self.store.reserve_exact(req(2))
        with self.assertRaises(FleetEffectBudgetError):
            self.store.reserve_exact(req(1))

    def test_expiry_frees_budget(self):
        short = replace(req(1), expires_at=(NOW + timedelta(seconds=1)).isoformat())
        self.store.reserve_exact(short)
        self.clock.value = NOW + timedelta(seconds=2)
        r2 = replace(
            req(2), requested_at=self.clock.value.isoformat(),
            expires_at=(self.clock.value + timedelta(minutes=1)).isoformat(),
        )
        self.store.reserve_exact(r2)
        self.assertEqual(self.store.get("res-1").state, "EXPIRED")

    def test_validate_for_effect_rejects_wrong_runtime_and_scope(self):
        request = req(1)
        reserved = self.store.reserve_exact(request)
        with self.assertRaises(FleetEffectBudgetError):
            self.store.validate_for_effect(
                reserved, effect_id=request.effect_id, candidate_digest=request.candidate_digest,
                mission_id=request.mission_id, executor_id=request.executor_id,
                runtime_id="runtime-attacker", repository=request.repository, branch=request.branch,
                authority_effect_key=request.authority_effect_key, authority_epoch=request.authority_epoch,
            )

    def test_validate_for_effect_rejects_wrong_candidate(self):
        request = req(1)
        reserved = self.store.reserve_exact(request)
        with self.assertRaises(FleetEffectBudgetError):
            self.store.validate_for_effect(
                reserved, effect_id=request.effect_id, candidate_digest="f" * 64,
                mission_id=request.mission_id, executor_id=request.executor_id,
                runtime_id=request.runtime_id, repository=request.repository, branch=request.branch,
                authority_effect_key=request.authority_effect_key, authority_epoch=request.authority_epoch,
            )

    def test_concurrency_never_overcommits_and_hits_exact_limit(self):
        barrier = threading.Barrier(8)
        ok = []
        denied = []
        lock = threading.Lock()
        def worker(i):
            barrier.wait()
            try:
                self.store.reserve_exact(req(i + 10))
                with lock:
                    ok.append(i)
            except FleetEffectBudgetError:
                with lock:
                    denied.append(i)
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(ok), 2)
        self.assertEqual(len(denied), 6)
        self.assertEqual(self.store.snapshot().active_writers, 2)

    def test_envelope_substitution_denied(self):
        with self.assertRaises(FleetEffectBudgetError):
            FleetEffectBudgetStore(
                self.tmp.name + "/budget.db", envelope=env(generation=2), clock=self.clock,
                identity_digest=IDENTITY, implementation_digest=IMPLEMENTATION,
            )


if __name__ == "__main__":
    unittest.main()
