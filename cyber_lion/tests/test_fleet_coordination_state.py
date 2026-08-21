from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
import tempfile
from pathlib import Path
import unittest

from cyber_lion.contracts.fleet_coordination import FleetCoordinationSpec, FleetPlanRequest
from cyber_lion.enterprise.fleet_coordination_state import (
    FleetCoordinationStateError,
    FleetCoordinationStore,
)


BASE = "a" * 40
TREE = "b" * 40
REPO = "DonkeyJJLove/ai_platform"


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 8, 21, 14, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def tick(self, seconds: int = 1) -> None:
        self.value += timedelta(seconds=seconds)


def mission(
    suffix: str,
    *,
    branch: str | None = None,
    path: str | None = None,
    baseline: str = BASE,
    tree: str = TREE,
    dependencies: tuple[str, ...] = (),
) -> FleetCoordinationSpec:
    return FleetCoordinationSpec(
        mission_id=f"mission-{suffix}",
        drone_id=f"drone-{suffix}",
        repository=REPO,
        baseline_sha=baseline,
        baseline_tree_sha=tree,
        branch=branch or f"mission/f005-{suffix}",
        write_scope=(path or f"cyber_lion/{suffix}.py",),
        dependencies=dependencies,
        evidence_refs=(f"authority:{suffix}",),
    )


def plan(request_id: str, *, head: str = BASE, max_parallel: int = 2) -> FleetPlanRequest:
    return FleetPlanRequest(
        request_id=request_id,
        coordinator_id="coord-1",
        current_heads=((REPO, head),),
        max_parallel=max_parallel,
    )


class FleetCoordinationStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "coordination.sqlite3"
        self.clock = Clock()
        self.store = FleetCoordinationStore(
            self.db,
            coordinator_id="coord-1",
            clock=self.clock,
        )

    def tearDown(self) -> None:
        if self.store is not None:
            try:
                self.store.close()
            except sqlite3.ProgrammingError:
                pass
        self.tmp.cleanup()

    def test_restart_preserves_running_dispatch_and_leases(self) -> None:
        self.store.register_mission(mission("a"))
        dispatch = self.store.plan(plan("p1", max_parallel=1))[0]
        before = self.store.snapshot()
        self.assertEqual(before.missions[0].state, "RUNNING")
        self.assertEqual(len(before.active_leases), 2)

        self.store.close()
        self.store = FleetCoordinationStore(self.db, coordinator_id="coord-1", clock=self.clock)
        after = self.store.snapshot()
        self.assertEqual(after, before)
        self.assertEqual(after.missions[0].dispatch_id, dispatch.dispatch_id)

    def test_coordinator_substitution_is_denied_on_restart(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.close()
        with self.assertRaises(FleetCoordinationStateError):
            FleetCoordinationStore(self.db, coordinator_id="coord-2", clock=self.clock)
        self.store = FleetCoordinationStore(self.db, coordinator_id="coord-1", clock=self.clock)

    def test_exact_registration_and_plan_replay_are_idempotent(self) -> None:
        spec = mission("a")
        self.store.register_mission(spec)
        revision_after_register = self.store.snapshot().revision
        self.store.register_mission(spec)
        self.assertEqual(self.store.snapshot().revision, revision_after_register)

        request = plan("p1", max_parallel=1)
        first = self.store.plan(request)
        after_first = self.store.snapshot()
        second = self.store.plan(request)
        after_second = self.store.snapshot()
        self.assertEqual(second, first)
        self.assertEqual(after_second, after_first)
        self.assertEqual(after_second.missions[0].generation, 1)

    def test_same_request_id_with_different_payload_is_denied(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.plan(plan("p1", max_parallel=1))
        with self.assertRaises(FleetCoordinationStateError):
            self.store.plan(plan("p1", max_parallel=2))

    def test_registration_substitution_and_dependency_cycle_are_denied(self) -> None:
        first = mission("a", dependencies=("mission-b",))
        self.store.register_mission(first)
        with self.assertRaises(FleetCoordinationStateError):
            self.store.register_mission(mission("a", tree="c" * 40, dependencies=("mission-b",)))
        with self.assertRaises(FleetCoordinationStateError):
            self.store.register_mission(mission("b", dependencies=("mission-a",)))
        with self.assertRaises(FleetCoordinationStateError):
            self.store.mission_state("mission-b")

    def test_path_and_branch_leases_prevent_parallel_conflicts(self) -> None:
        self.store.register_mission(mission("a", branch="mission/shared", path="cyber_lion/shared"))
        self.store.register_mission(mission("b", branch="mission/other", path="cyber_lion/shared/x.py"))
        self.store.register_mission(mission("c", branch="mission/shared", path="other/c.py"))
        dispatched = self.store.plan(plan("p1", max_parallel=3))
        self.assertEqual(tuple(item.mission_id for item in dispatched), ("mission-a",))
        self.assertEqual(self.store.mission_state("mission-b").state, "STARTING")
        self.assertEqual(self.store.mission_state("mission-c").state, "STARTING")

    def test_stale_baseline_rolls_back_whole_plan_without_partial_dispatch(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.register_mission(mission("b", baseline="c" * 40))
        with self.assertRaises(FleetCoordinationStateError):
            self.store.plan(plan("p1", head=BASE, max_parallel=2))
        self.assertEqual(self.store.mission_state("mission-a").state, "STARTING")
        self.assertEqual(self.store.mission_state("mission-a").generation, 0)
        self.assertEqual(self.store.active_leases(), ())
        reader = self.store.open_query_reader()
        try:
            self.assertEqual(reader.execute("SELECT count(*) FROM fleet_coordination_plan").fetchone()[0], 0)
        finally:
            reader.close()

    def test_dependency_waits_for_done_then_dispatches(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.register_mission(mission("b", dependencies=("mission-a",)))
        first = self.store.plan(plan("p1", max_parallel=2))
        self.assertEqual(tuple(item.mission_id for item in first), ("mission-a",))
        self.clock.tick()
        self.store.record_terminal(
            "mission-a",
            dispatch_id=first[0].dispatch_id,
            fencing_token=first[0].fencing_token,
            terminal_state="DONE",
            evidence_ref="verified:a",
        )
        self.assertEqual(self.store.active_leases(), ())
        self.clock.tick()
        second = self.store.plan(plan("p2", max_parallel=2))
        self.assertEqual(tuple(item.mission_id for item in second), ("mission-b",))

    def test_requeue_creates_new_generation_and_old_fence_cannot_complete(self) -> None:
        self.store.register_mission(mission("a"))
        first = self.store.plan(plan("p1", max_parallel=1))[0]
        self.clock.tick()
        self.store.requeue(
            "mission-a",
            dispatch_id=first.dispatch_id,
            fencing_token=first.fencing_token,
            evidence_ref="executor-lost:a",
        )
        self.assertEqual(self.store.mission_state("mission-a").state, "WAITING")
        self.assertEqual(self.store.active_leases(), ())
        revision = self.store.snapshot().revision
        self.store.requeue(
            "mission-a",
            dispatch_id=first.dispatch_id,
            fencing_token=first.fencing_token,
            evidence_ref="executor-lost:a",
        )
        self.assertEqual(self.store.snapshot().revision, revision)

        self.clock.tick()
        second = self.store.plan(plan("p2", max_parallel=1))[0]
        self.assertEqual(second.generation, 2)
        self.assertNotEqual(second.dispatch_id, first.dispatch_id)
        self.assertNotEqual(second.fencing_token, first.fencing_token)
        with self.assertRaises(FleetCoordinationStateError):
            self.store.record_terminal(
                "mission-a",
                dispatch_id=first.dispatch_id,
                fencing_token=first.fencing_token,
                terminal_state="DONE",
                evidence_ref="stale-result",
            )

    def test_terminal_transition_is_fenced_idempotent_and_releases_leases(self) -> None:
        self.store.register_mission(mission("a"))
        dispatch = self.store.plan(plan("p1", max_parallel=1))[0]
        self.clock.tick()
        self.store.record_terminal(
            "mission-a",
            dispatch_id=dispatch.dispatch_id,
            fencing_token=dispatch.fencing_token,
            terminal_state="FAILED",
            evidence_ref="failure:a",
        )
        after = self.store.snapshot()
        self.assertEqual(after.missions[0].state, "FAILED")
        self.assertEqual(after.active_leases, ())
        self.store.record_terminal(
            "mission-a",
            dispatch_id=dispatch.dispatch_id,
            fencing_token=dispatch.fencing_token,
            terminal_state="FAILED",
            evidence_ref="failure:a",
        )
        self.assertEqual(self.store.snapshot(), after)
        with self.assertRaises(FleetCoordinationStateError):
            self.store.record_terminal(
                "mission-a",
                dispatch_id=dispatch.dispatch_id,
                fencing_token=dispatch.fencing_token,
                terminal_state="DONE",
                evidence_ref="failure:a",
            )

    def test_missing_current_head_fails_closed(self) -> None:
        self.store.register_mission(mission("a"))
        request = FleetPlanRequest(
            request_id="p1",
            coordinator_id="coord-1",
            current_heads=(("DonkeyJJLove/other", BASE),),
            max_parallel=1,
        )
        with self.assertRaises(FleetCoordinationStateError):
            self.store.plan(request)
        self.assertEqual(self.store.mission_state("mission-a").state, "STARTING")

    def test_trusted_clock_rollback_is_denied(self) -> None:
        self.store.register_mission(mission("a"))
        self.clock.value -= timedelta(seconds=1)
        with self.assertRaises(FleetCoordinationStateError):
            self.store.plan(plan("p1", max_parallel=1))
        self.assertEqual(self.store.mission_state("mission-a").state, "STARTING")

    def test_event_and_plan_records_are_database_append_only_and_reader_is_query_only(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.plan(plan("p1", max_parallel=1))
        conn = sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE fleet_coordination_event SET event_type='tamper' WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM fleet_coordination_event WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE fleet_coordination_plan SET result_json='[]' WHERE request_id='p1'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM fleet_coordination_plan WHERE request_id='p1'")
        finally:
            conn.close()
        reader = self.store.open_query_reader()
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                reader.execute("DELETE FROM fleet_coordination_mission")
        finally:
            reader.close()
        self.assertEqual(self.store.verify_event_chain(), self.store.snapshot().event_head)

    def test_restart_detects_corrupt_running_lease_set(self) -> None:
        self.store.register_mission(mission("a"))
        self.store.plan(plan("p1", max_parallel=1))
        self.store.close()
        conn = sqlite3.connect(self.db)
        try:
            conn.execute("DELETE FROM fleet_coordination_active_lease WHERE lease_kind='PATH'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(FleetCoordinationStateError):
            FleetCoordinationStore(self.db, coordinator_id="coord-1", clock=self.clock)
        # Keep tearDown from operating on the closed original connection.
        self.store = None


if __name__ == "__main__":
    unittest.main()
