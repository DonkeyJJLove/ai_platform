import unittest
from cyber_lion.contracts.panel_projection import ProjectionError
from cyber_lion.mission_control.control_read_model import (
 build_artifact_projection,build_evolution_projection,build_federation_projection,
 build_mission_projection,build_model_projection,build_repository_projection,
 build_swarm_projection,build_timeline_projection,
)

class ControlReadModelTests(unittest.TestCase):
 def h(self,**changes):
  v={"observed_at":"2026-10-05T20:15:00Z","source_refs":("source:a",),"source_revision":"91dd9db46aa6fa9f7c2284a40bc924723a052cb2","projection_version":"1.0.0","currentness":"CURRENT","gaps":()}
  v.update(changes);return v
 def test_mission_whitelist(self):
  p=build_mission_projection({"mission_id":"M1","state":"RUNNING","private_field":"omit","process":{"current_phase":"P1","progress":25,"objective":"bounded","authority_state":"AUTHORIZED","raw_field":"omit"},"execution_driver":{"driver_id":"D1","generation":3,"state":"ACTIVE","private_field":"omit"}},**self.h()).payload()
  self.assertNotIn("private_field",p);self.assertNotIn("raw_field",p["process"]);self.assertNotIn("private_field",p["execution_driver"])
 def test_swarm_whitelist_and_sort(self):
  p=build_swarm_projection([
   {"material_worker_id":"MD002","state":"READY","architecture":{"runtime_instance_id":"r2","source_head":"b"*40,"private_field":"omit"},"transport_metrics":{"open_connections":2,"reconnects":1,"private_metric":9},"unlisted":{"x":1}},
   {"material_worker_id":"MD001","state":"READY","architecture":{"runtime_instance_id":"r1","source_head":"a"*40}},
  ],**self.h()).payload()
  self.assertEqual([x["material_worker_id"] for x in p["workers"]],["MD001","MD002"]);self.assertEqual(p["ready_count"],2)
  self.assertNotIn("unlisted",p["workers"][1]);self.assertNotIn("private_field",p["workers"][1]["architecture"]);self.assertNotIn("private_metric",p["workers"][1]["transport_metrics"])
 def test_model_excludes_raw_prompt_and_response(self):
  p=build_model_projection([{"model_call_id":"mc1","provider":"LION_LOCAL_MODEL","transport":"LOCAL","state":"RESPONSE_RECONCILED","input_digest":"a"*64,"result_digest":"b"*64,"raw_input":"omit","raw_output":"omit"}],**self.h()).payload()["calls"][0]
  self.assertNotIn("raw_input",p);self.assertNotIn("raw_output",p)
 def test_artifact_excludes_content(self):
  p=build_artifact_projection([{"artifact_id":"A1","mission_id":"M1","artifact_type":"TEST","content_digest":"c"*64,"content_json":"omit","content":{"x":1},"authority_effect":"NONE"}],**self.h()).payload()["artifacts"][0]
  self.assertNotIn("content",p);self.assertNotIn("content_json",p)
 def test_federation_repository_evolution_deterministic(self):
  f=build_federation_projection([{"repository":"z/repo","head":"2"*40},{"repository":"a/repo","head":"0"*40}],**self.h()).payload()
  self.assertEqual([x["repository"] for x in f["repositories"]],["a/repo","z/repo"])
  r=build_repository_projection({"repository":"a/repo","head":"0"*40,"private_field":"omit"},**self.h()).payload();self.assertNotIn("private_field",r)
  e=build_evolution_projection([{"repository":"a/repo","task_id":"T2"},{"repository":"a/repo","task_id":"T1"}],**self.h()).payload();self.assertEqual([x["task_id"] for x in e["changes"]],["T1","T2"])
 def test_timeline_unknown_and_raw_omitted(self):
  rows=build_timeline_projection([{"event_id":"e2","timestamp":"2026-10-05T20:00:02Z","event_class":"INVENTED","raw_field":"omit"},{"event_id":"e1","timestamp":"2026-10-05T20:00:01Z","event_class":"COGNITION"}],**self.h()).payload()["events"]
  self.assertEqual([x["event_id"] for x in rows],["e1","e2"]);self.assertEqual(rows[1]["event_class"],"UNKNOWN");self.assertNotIn("raw_field",rows[1])
 def test_bounds_and_types(self):
  with self.assertRaisesRegex(ProjectionError,"exceeds bound"):build_model_projection([{"model_call_id":str(i)} for i in range(513)],**self.h())
  with self.assertRaises(ProjectionError):build_mission_projection("bad",**self.h())

if __name__=="__main__":unittest.main()
