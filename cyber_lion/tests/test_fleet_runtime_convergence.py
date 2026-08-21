from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from cyber_lion.contracts.fleet_runtime_convergence import RuntimeFleetConvergenceSnapshot
from cyber_lion.enterprise.fleet_runtime_convergence import (
    RuntimeFleetConvergenceError,
    load_snapshot,
    verify_snapshot,
)

MASTER = "d" * 40
TREE = "e" * 40
NOW = datetime(2026, 8, 21, 15, 20, tzinfo=timezone.utc)


def snapshot(**changes):
    base = RuntimeFleetConvergenceSnapshot(
        schema_version="1.0.0",
        snapshot_id="1" * 64,
        repository="DonkeyJJLove/ai_platform",
        current_master=MASTER,
        current_master_tree=TREE,
        observed_at=(NOW - timedelta(seconds=10)).isoformat(),
        source_kind="AUTHORITATIVE_RUNTIME_STORE",
        source_instance="lion-runtime-control-plane-01",
        source_digest="2" * 64,
        active_missions=0,
        unknown_missions=0,
        unresolved_write_leases=0,
        unknown_results=0,
        late_unreconciled_results=0,
        missing_heartbeats=0,
        stale_heartbeats=0,
        unknown_branch_ownership=0,
        unowned_active_branches=0,
        unreconciled_effects=0,
        reconciliation_disagreements=0,
        active_authority=0,
        residual_authority=0,
        durable_state_consistency=True,
        event_chain_consistency=True,
        generation_fencing_consistency=True,
        inventory_complete=True,
    )
    return replace(base, **changes)


class RuntimeFleetConvergenceTests(unittest.TestCase):
    def verify(self, item):
        return verify_snapshot(
            item,
            repository="DonkeyJJLove/ai_platform",
            expected_master=MASTER,
            expected_master_tree=TREE,
            now=NOW,
            max_age_seconds=300,
        )

    def test_exact_zero_snapshot_is_closable(self):
        receipt = self.verify(snapshot())
        self.assertEqual(receipt["status"], "FLEET_CLOSABLE")
        self.assertEqual(receipt["blockers"], [])

    def test_each_nonzero_counter_fails_closed(self):
        names = (
            "active_missions", "unknown_missions", "unresolved_write_leases",
            "unknown_results", "late_unreconciled_results", "missing_heartbeats",
            "stale_heartbeats", "unknown_branch_ownership", "unowned_active_branches",
            "unreconciled_effects", "reconciliation_disagreements", "active_authority",
            "residual_authority",
        )
        for name in names:
            with self.subTest(name=name), self.assertRaises(RuntimeFleetConvergenceError):
                self.verify(snapshot(**{name: 1}))

    def test_partial_inventory_and_consistency_fail_closed(self):
        for name in (
            "inventory_complete", "durable_state_consistency",
            "event_chain_consistency", "generation_fencing_consistency",
        ):
            with self.subTest(name=name), self.assertRaises(RuntimeFleetConvergenceError):
                self.verify(snapshot(**{name: False}))

    def test_master_and_tree_substitution_denied(self):
        with self.assertRaises(RuntimeFleetConvergenceError):
            self.verify(snapshot(current_master="a" * 40))
        with self.assertRaises(RuntimeFleetConvergenceError):
            self.verify(snapshot(current_master_tree="b" * 40))

    def test_non_authoritative_source_denied(self):
        with self.assertRaises(Exception):
            self.verify(snapshot(source_kind="SELF_REPORTED"))

    def test_stale_and_future_snapshot_denied(self):
        with self.assertRaises(RuntimeFleetConvergenceError):
            self.verify(snapshot(observed_at=(NOW - timedelta(seconds=301)).isoformat()))
        with self.assertRaises(RuntimeFleetConvergenceError):
            self.verify(snapshot(observed_at=(NOW + timedelta(seconds=1)).isoformat()))

    def test_loader_rejects_extra_or_missing_fields(self):
        value = snapshot().canonical_dict()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "snapshot.json"
            value["unexpected"] = True
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(RuntimeFleetConvergenceError):
                load_snapshot(path)
            value.pop("unexpected")
            value.pop("residual_authority")
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(RuntimeFleetConvergenceError):
                load_snapshot(path)


if __name__ == "__main__":
    unittest.main()
