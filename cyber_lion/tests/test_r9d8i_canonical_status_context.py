from __future__ import annotations

import unittest
from dataclasses import replace

from cyber_lion.contracts.fleet_status import FleetAggregate, FleetStatusSnapshot, SCOPE_CLASS
from cyber_lion.enterprise.canonical_lion_status_adapter import adapt_fleet_status, derive_observability
from cyber_lion.enterprise.repository_maintenance_pdp_context import RepositoryMaintenancePDPContext
from cyber_lion.enterprise.swarm_status_projection import validate_status_projection


class R9D8ICanonicalStatusContextTests(unittest.TestCase):
    def _empty_snapshot(self) -> FleetStatusSnapshot:
        aggregate = FleetAggregate(
            total_known_drones=0,
            reachable_drones=0,
            unreachable_drones=0,
            active_missions=0,
            idle_drones=0,
            running_drones=0,
            waiting_drones=0,
            blocked_drones=0,
            degraded_drones=0,
            failed_drones=0,
            done_not_closed=0,
            missions_in_verification=0,
            missions_in_reconciliation=0,
            active_authority_count=0,
            active_write_lease_count=0,
            unresolved_effect_count=0,
            stale_heartbeat_count=0,
            unknown_state_count=0,
        )
        raw = FleetStatusSnapshot(
            schema_version="1.0.0",
            snapshot_id="snapshot:r9d8i",
            snapshot_revision=1,
            snapshot_digest="0" * 64,
            observed_at="2026-08-26T07:00:00+00:00",
            registry_instance_id="registry:r9d8i",
            scope_class=SCOPE_CLASS,
            aggregate=aggregate,
            drone_records=(),
            anomalies=(),
        )
        return replace(raw, snapshot_digest=raw.recompute_digest()).validate()

    def test_empty_fleet_never_becomes_current_or_healthy(self) -> None:
        snapshot = self._empty_snapshot()
        self.assertEqual(derive_observability(snapshot), "LOST")
        status, observability = adapt_fleet_status(
            snapshot,
            observed_master="1" * 40,
            observed_tree="2" * 40,
            exact_master_relation_proven=True,
        )
        self.assertEqual(observability, "LOST")
        self.assertEqual(status["epistemic_state"], "UNKNOWN")
        validate_status_projection(status)

    def test_unproven_master_relation_cannot_be_current(self) -> None:
        snapshot = self._empty_snapshot()
        status, _ = adapt_fleet_status(
            snapshot,
            observed_master="1" * 40,
            observed_tree="2" * 40,
            exact_master_relation_proven=False,
        )
        self.assertNotEqual(status["epistemic_state"], "CURRENT")

    def test_context_digest_detects_substitution(self) -> None:
        c = RepositoryMaintenancePDPContext(
            policy_binding="p@1:sha256:" + "a" * 64,
            policy_digest="sha256:" + "a" * 64,
            mission_id="maintenance",
            mission_revision=1,
            mission_digest="b" * 64,
            agent_registry_id="agents",
            registry_revision=1,
            registry_event_head="c" * 64,
            registry_projection_digest="d" * 64,
            planner_implementation_digest="e" * 64,
            swarm_digest="f" * 64,
            agents_digest="1" * 64,
            enterprise_graph_id="graph",
            graph_revision=1,
            graph_event_head="2" * 64,
            graph_projection_digest="3" * 64,
            status_digest="4" * 64,
            fleet_snapshot_digest="5" * 64,
            observability_state="HEALTHY",
            master="6" * 40,
            tree="7" * 40,
        ).sealed()
        self.assertEqual(c.context_digest, c.compute_digest())
        with self.assertRaises(Exception):
            replace(c, master="8" * 40).validate()


if __name__ == "__main__":
    unittest.main()
