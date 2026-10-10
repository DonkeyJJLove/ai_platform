"""R5 Mission Control Active Ecosystem: a recorded fleet is not a live fleet."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
STATIC=ROOT/"deploy/mission-control/v3"
JS=STATIC/"control-v3.js"

class ActiveEcosystemViewTests(unittest.TestCase):
    def test_html_and_cluster_navigation_are_present(self):
        html=(STATIC/"index.html").read_text(encoding="utf-8")
        for selector in ("mcActiveEcosystem","mcEcosystemStatus","mcEcosystemMap",
                         "mcEcosystemClusterLink","mcClusterScope","mcClusterEvidenceRows"):
            self.assertIn('id="'+selector+'"',html)
        self.assertIn('href="#cluster"',html)
        self.assertIn('id="cluster"',html)

    def test_source_ui_distinguishes_history_from_live_state(self):
        source=JS.read_text(encoding="utf-8")
        self.assertIn("function projectActiveEcosystem",source)
        self.assertIn("NO_CURRENT_MATERIAL_FLEET",source)
        self.assertIn("RECORDED_NOT_ACTIVE",source)
        self.assertIn("RECORDED_",source)
        self.assertIn("source_currentness:'UNVERIFIED'",source)
        self.assertIn("renderActiveEcosystem(s,supervisor)",source)
        self.assertIn("renderActiveEcosystem(null,broker)",source)
        self.assertIn("renderActiveEcosystem(null,null)",source)

    @unittest.skipUnless(shutil.which("node"),"Node runtime not available")
    def test_projections_do_not_promote_history_or_transport_to_executed_mission(self):
        node=r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const src=fs.readFileSync(process.argv[1],'utf8');
const from=src.indexOf('function projectActiveEcosystem(');
const to=src.indexOf('async function mcRefresh(){',from);
assert(from>=0&&to>from);
const context={};
vm.runInNewContext(src.slice(from,to),context);
const empty=context.projectActiveEcosystem(null,{automatic_hop:'AVAILABLE',channel_state:'SENTINELX_MCP_READY',pending_count:0,session_attestation_state:'EXPIRED'});
assert.equal(empty.status,'NO_CURRENT_MISSION');
assert.equal(empty.fleet,'NO_CURRENT_MATERIAL_FLEET');
const mission={
  mission_id:'M-1',source_head:'a'.repeat(40),source_tree:'b'.repeat(40),
  state:'STOPPED',material_target:32,logical_count:8,adapter:'LPCL_MISSION',
  process:{authority_state:'NONE',current_phase:'PH-1'},
  execution_driver:{state:'WAITING',generation:1},
  workers:[{pod_uid:'pod-1',logical_id:'MD001',ready:1}]
};
const broker={automatic_hop:'AVAILABLE',channel_state:'SENTINELX_MCP_READY',pending_count:0,session_attestation_state:'EXPIRED'};
const historical=context.projectActiveEcosystem(mission,broker);
assert.equal(historical.status,'RECORDED_NOT_ACTIVE');
assert.equal(historical.source_currentness,'UNVERIFIED');
assert.match(historical.fleet,/RECORDED_1_WORKERS_CURRENTNESS_UNVERIFIED/);
assert.equal(historical.saas,'TRANSPORT_READY_NO_MISSION_RECEIPT');
mission.process.authority_state='EXPLICIT_USER_ACTIVATION';mission.state='WAITING';
const active=context.projectActiveEcosystem(mission,broker);
assert.equal(active.status,'ACTIVATED_RUNTIME_UNVERIFIED');
assert.equal(active.source_currentness,'UNVERIFIED');
assert.equal(active.completion,'NOT_OBSERVED');
console.log('ACTIVE_ECOSYSTEM_PROJECTION_PASS');
'''
        check=subprocess.run(["node","-e",node,str(JS)],text=True,capture_output=True,timeout=12)
        self.assertEqual(check.returncode,0,check.stderr)
        self.assertIn("ACTIVE_ECOSYSTEM_PROJECTION_PASS",check.stdout)

if __name__=="__main__":
    unittest.main()
