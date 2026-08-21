from __future__ import annotations

from datetime import datetime,timedelta,timezone
import sqlite3,tempfile,unittest
from pathlib import Path

from cyber_lion.contracts.fleet_coordination import FleetCoordinationSpec,FleetPlanRequest
from cyber_lion.enterprise.fleet_coordination_state import FleetCoordinationStateError,FleetCoordinationStore

BASE="a"*40; TREE="b"*40; REPO="DonkeyJJLove/ai_platform"

class Clock:
    def __init__(self): self.value=datetime(2026,8,21,14,0,tzinfo=timezone.utc)
    def __call__(self): return self.value
    def tick(self,s=1): self.value+=timedelta(seconds=s)

def mission(suffix,*,branch=None,path=None,baseline=BASE,tree=TREE,dependencies=()):
    return FleetCoordinationSpec(f"mission-{suffix}",f"drone-{suffix}",REPO,baseline,tree,branch or f"mission/f005-{suffix}",(path or f"cyber_lion/{suffix}.py",),dependencies,(f"authority:{suffix}",))
def plan(request_id,*,head=BASE,max_parallel=2): return FleetPlanRequest(request_id,"coord-1",((REPO,head),),max_parallel)

class FleetCoordinationStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Path(self.tmp.name)/"coord.sqlite3"; self.clock=Clock(); self.store=FleetCoordinationStore(self.db,coordinator_id="coord-1",clock=self.clock)
    def tearDown(self):
        if self.store is not None:
            try:self.store.close()
            except sqlite3.ProgrammingError:pass
        self.tmp.cleanup()
    def restart(self):
        self.store.close(); self.store=FleetCoordinationStore(self.db,coordinator_id="coord-1",clock=self.clock)
    def raw_update(self,sql,args=()):
        self.store.close(); c=sqlite3.connect(self.db); c.execute(sql,args); c.commit(); c.close(); self.store=None
    def corrupt_plan_request(self,raw):
        self.store.close(); c=sqlite3.connect(self.db); c.execute("DROP TRIGGER fleet_coordination_plan_no_update"); c.execute("UPDATE fleet_coordination_plan SET request_json=? WHERE request_id='p1'",(raw,)); c.commit(); c.close(); self.store=None
    def assert_restart_fails(self):
        with self.assertRaises(FleetCoordinationStateError): FleetCoordinationStore(self.db,coordinator_id="coord-1",clock=self.clock)

    def test_restart_preserves_running_dispatch_and_leases(self):
        self.store.register_mission(mission("a")); d=self.store.plan(plan("p1",max_parallel=1))[0]; before=self.store.snapshot(); self.restart(); self.assertEqual(self.store.snapshot(),before); self.assertEqual(self.store.mission_state("mission-a").dispatch_id,d.dispatch_id)
    def test_coordinator_substitution_denied(self):
        self.store.register_mission(mission("a")); self.store.close()
        with self.assertRaises(FleetCoordinationStateError): FleetCoordinationStore(self.db,coordinator_id="coord-2",clock=self.clock)
        self.store=FleetCoordinationStore(self.db,coordinator_id="coord-1",clock=self.clock)
    def test_registration_and_plan_replay_idempotent(self):
        s=mission("a"); self.store.register_mission(s); rev=self.store.snapshot().revision; self.store.register_mission(s); self.assertEqual(self.store.snapshot().revision,rev); r=plan("p1",max_parallel=1); first=self.store.plan(r); snap=self.store.snapshot(); self.assertEqual(self.store.plan(r),first); self.assertEqual(self.store.snapshot(),snap)
    def test_request_substitution_denied(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1))
        with self.assertRaises(FleetCoordinationStateError): self.store.plan(plan("p1",max_parallel=2))
    def test_dependency_cycle_and_waiting(self):
        self.store.register_mission(mission("a",dependencies=("mission-b",)))
        with self.assertRaises(FleetCoordinationStateError): self.store.register_mission(mission("b",dependencies=("mission-a",)))
    def test_path_and_branch_conflicts(self):
        self.store.register_mission(mission("a",branch="mission/shared",path="cyber_lion/shared")); self.store.register_mission(mission("b",path="cyber_lion/shared/x.py")); self.store.register_mission(mission("c",branch="mission/shared",path="other/c.py")); ds=self.store.plan(plan("p1",max_parallel=3)); self.assertEqual(tuple(x.mission_id for x in ds),("mission-a",))
    def test_stale_baseline_rolls_back_plan(self):
        self.store.register_mission(mission("a")); self.store.register_mission(mission("b",baseline="c"*40))
        with self.assertRaises(FleetCoordinationStateError): self.store.plan(plan("p1",max_parallel=2))
        self.assertEqual(self.store.mission_state("mission-a").state,"STARTING"); self.assertEqual(self.store.active_leases(),())
    def test_dependency_dispatches_only_after_done(self):
        self.store.register_mission(mission("a")); self.store.register_mission(mission("b",dependencies=("mission-a",))); first=self.store.plan(plan("p1")); self.assertEqual(tuple(x.mission_id for x in first),("mission-a",)); self.clock.tick(); d=first[0]; self.store.record_terminal("mission-a",dispatch_id=d.dispatch_id,fencing_token=d.fencing_token,terminal_state="DONE",evidence_ref="verified:a"); self.clock.tick(); self.assertEqual(tuple(x.mission_id for x in self.store.plan(plan("p2"))),("mission-b",))
    def test_requeue_fences_stale_generation(self):
        self.store.register_mission(mission("a")); first=self.store.plan(plan("p1",max_parallel=1))[0]; self.clock.tick(); self.store.requeue("mission-a",dispatch_id=first.dispatch_id,fencing_token=first.fencing_token,evidence_ref="lost"); self.clock.tick(); second=self.store.plan(plan("p2",max_parallel=1))[0]; self.assertEqual(second.generation,2)
        with self.assertRaises(FleetCoordinationStateError): self.store.record_terminal("mission-a",dispatch_id=first.dispatch_id,fencing_token=first.fencing_token,terminal_state="DONE",evidence_ref="stale")
    def test_clock_rollback_denied(self):
        self.store.register_mission(mission("a")); self.clock.value-=timedelta(seconds=1)
        with self.assertRaises(FleetCoordinationStateError): self.store.plan(plan("p1",max_parallel=1))
    def test_restart_detects_missing_lease(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1)); self.raw_update("DELETE FROM fleet_coordination_active_lease WHERE lease_kind='PATH'"); self.assert_restart_fails()
    def test_restart_detects_spec_digest_tamper(self):
        self.store.register_mission(mission("a")); self.raw_update("UPDATE fleet_coordination_mission SET baseline_sha=? WHERE mission_id='mission-a'",("c"*40,)); self.assert_restart_fails()
    def test_restart_detects_write_scope_materialization_tamper(self):
        self.store.register_mission(mission("a")); self.raw_update("UPDATE fleet_coordination_mission SET write_scope_json='[\"other.py\"]' WHERE mission_id='mission-a'"); self.assert_restart_fails()
    def test_restart_detects_dependency_materialization_tamper(self):
        self.store.register_mission(mission("a",dependencies=("external",))); self.raw_update("DELETE FROM fleet_coordination_dependency WHERE mission_id='mission-a'"); self.assert_restart_fails()
    def test_restart_detects_request_digest_tamper_after_storage_bypass(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1)); self.corrupt_plan_request('{"coordinator_id":"coord-1","current_heads":[["DonkeyJJLove/ai_platform","'+BASE+'"]],"max_parallel":2,"request_id":"p1"}'); self.assert_restart_fails()
    def test_restart_detects_dispatch_to_spec_tamper(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1)); self.raw_update("UPDATE fleet_coordination_mission SET branch='mission/other' WHERE mission_id='mission-a'"); self.assert_restart_fails()
    def test_restart_detects_materialized_state_tamper(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1)); self.raw_update("UPDATE fleet_coordination_mission SET state='WAITING' WHERE mission_id='mission-a'"); self.assert_restart_fails()
    def test_event_and_plan_append_only(self):
        self.store.register_mission(mission("a")); self.store.plan(plan("p1",max_parallel=1)); c=sqlite3.connect(self.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError): c.execute("UPDATE fleet_coordination_event SET event_type='x' WHERE seq=1")
            with self.assertRaises(sqlite3.DatabaseError): c.execute("DELETE FROM fleet_coordination_plan WHERE request_id='p1'")
        finally:c.close()
        self.assertEqual(self.store.verify_event_chain(),self.store.snapshot().event_head)

if __name__=="__main__": unittest.main()
