from datetime import datetime,timezone,timedelta
import json,pytest
from cyber_lion.contracts.swarm_status import StatusReport
from cyber_lion.enterprise.swarm_governor import SwarmGovernorLeaseStore
from cyber_lion.enterprise.swarm_status import SwarmStatusStore,SwarmStatusStateError
from cyber_lion.enterprise.swarm_status_projection import validate_status_projection,classify_live_master

class Clock:
    def __init__(self):self.v=datetime(2026,1,1,tzinfo=timezone.utc)
    def __call__(self):return self.v
    def add(self,s):self.v+=timedelta(seconds=s)

def ctx():return {"observed_master":{"commit":"a"*40,"tree":"b"*40,"observed_at":"2026-01-01T00:00:00+00:00"},"governor":{"logical_role":"SWARM_GOVERNOR","instance_id":"g","state":"ACTIVE","epoch":1,"fencing_token":1,"is_authority_source":False},"architecture":{},"critical_path":[],"formations":[],"missions":[],"drones":[],"role_assignments":[],"dependencies":[],"blockers":[],"channels":[],"pending_messages":[],"epistemic_state":"CURRENT","source_refs":["e"]}

def report(snapshot,op,event,payload):return StatusReport(op,snapshot["revision"],snapshot["status_digest"],"d1","m1",event,payload,("e",),"2026-01-01T00:00:00+00:00")

def test_action_lifecycle_moves_terminal_to_history(tmp_path):
    c=Clock();g=SwarmGovernorLeaseStore(tmp_path/"g.db",clock=c);lease=g.acquire("g",lease_seconds=60);s=SwarmStatusStore(tmp_path/"s.db",tmp_path/"status.json",system_id="LION",clock=c,governor_store=g,known_drones=("d1",),initial_context=ctx())
    x=s.snapshot();x=s.apply_report(report(x,"1","ACTION_PLANNED",{"action_id":"a","role":"BUILDER"}),lease=lease);x=s.apply_report(report(x,"2","ACTION_ACCEPTED",{"action_id":"a"}),lease=lease);x=s.apply_report(report(x,"3","ACTION_STARTED",{"action_id":"a"}),lease=lease);x=s.apply_report(report(x,"4","ACTION_COMPLETED",{"action_id":"a","result_refs":["pr:1"]}),lease=lease)
    assert x["current_actions"]==[] and x["history"][0]["state"]=="COMPLETED";validate_status_projection(x)

def test_stale_cas_and_unknown_drone_fail_closed(tmp_path):
    c=Clock();g=SwarmGovernorLeaseStore(tmp_path/"g.db",clock=c);lease=g.acquire("g",lease_seconds=60);s=SwarmStatusStore(tmp_path/"s.db",tmp_path/"status.json",system_id="LION",clock=c,governor_store=g,known_drones=("d1",),initial_context=ctx());x=s.snapshot();r=report(x,"1","ACTION_PLANNED",{"action_id":"a"});s.apply_report(r,lease=lease)
    with pytest.raises(SwarmStatusStateError):s.apply_report(r,lease=lease)
    bad=StatusReport("2",s.snapshot()["revision"],s.snapshot()["status_digest"],"unknown","m1","STATUS_REPORT",{},("e",),"2026-01-01T00:00:00+00:00")
    with pytest.raises(SwarmStatusStateError):s.apply_report(bad,lease=lease)

def test_external_status_modification_detected(tmp_path):
    c=Clock();g=SwarmGovernorLeaseStore(tmp_path/"g.db",clock=c);g.acquire("g",lease_seconds=60);p=tmp_path/"status.json";s=SwarmStatusStore(tmp_path/"s.db",p,system_id="LION",clock=c,governor_store=g,known_drones=("d1",),initial_context=ctx());s.close();raw=json.loads(p.read_text());raw["revision"]=999;p.write_text(json.dumps(raw))
    with pytest.raises(SwarmStatusStateError):SwarmStatusStore(tmp_path/"s.db",p,system_id="LION",clock=c,governor_store=g,known_drones=("d1",),initial_context=ctx())

def test_live_master_staleness():
    status={"schema_version":"1.0.0","system_id":"LION","revision":0,"status_digest":"0"*64,"previous_status_digest":"0"*64,"revision_digest":"0"*64,"previous_revision_digest":"0"*64,**ctx(),"current_actions":[],"history":[],"generated_at":"2026-01-01T00:00:00+00:00"}
    from cyber_lion.contracts.swarm_status import compute_status_digest,compute_revision_digest
    status["status_digest"]=compute_status_digest(status);status["revision_digest"]=compute_revision_digest(revision=0,status_digest=status["status_digest"],previous_revision_digest="0"*64)
    assert classify_live_master(status,live_commit="c"*40,live_tree="b"*40)=="STALE"
