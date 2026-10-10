"""R9: Active Ecosystem displays bounded 0/1/32 phase needs, never authority."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[2]
JS=ROOT/"deploy/mission-control/v3/control-v3.js"


class PhaseFleetProjectionViewTests(unittest.TestCase):
    def test_selected_mission_schema_and_cluster_proof_paths_are_explicit(self):
        src=JS.read_text(encoding="utf-8")
        for expected in (
            "material_fleet_lifecycle",
            "phase_demand:",
            "phase_demand_state:",
            "phase_effect_admitted:false",
            "PHASE MATERIAL NEED",
            "Phase need (0/1/32)",
            "Phase contract / status",
            "Phase runtime observation",
            "Phase blockers",
        ):
            self.assertIn(expected,src)
        self.assertNotIn("material.effect_admitted===true",src)

    @unittest.skipUnless(shutil.which("node"),"Node runtime unavailable")
    def test_read_model_renders_0_1_32_and_rejects_authority_spoof(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(process.argv[1],'utf8');
const a=src.indexOf('function projectActiveEcosystem('),b=src.indexOf('function renderActiveEcosystem(',a);
assert(a>=0&&b>a);
const ctx={};vm.runInNewContext(src.slice(a,b),ctx);
const base={
  mission_id:'LION-APPLICATION-FACTORY-CROSS-MODEL-R1',
  source_head:'a'.repeat(40),source_tree:'b'.repeat(40),
  spec_digest:'c'.repeat(64),state:'WAITING',
  adapter:'LPCL_MISSION',material_target:32,logical_count:4,
  process:{authority_state:'EXPLICIT_USER_ACTIVATION',current_phase:'P1'},
  execution_driver:{state:'WAITING',generation:2,blocking_gate:'DOCKER_FLEET_CURRENTNESS_REQUIRED'},
  workers:[],
};
for(const demand of [0,1,32]){
  const entry={
    schema:'lion.mission-scoped-material-fleet-lifecycle/v1',
    desired_workers:demand,phase_id:'P1',
    phase_contract_digest:'d'.repeat(64),
    authority_effect:'NONE',execution_effect:'NONE',effect_admitted:false,
    state:'BLOCKED',blockers:['CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT'],
    observed_fleet:{state:'UNAVAILABLE'}
  };
  const obj={...base,material_fleet_lifecycle:entry};
  const got=ctx.projectActiveEcosystem(obj,{automatic_hop:'AVAILABLE',session_attestation_state:'EXPIRED'});
  assert.strictEqual(got.phase_demand,demand);
  assert.strictEqual(got.phase_demand_state,'BLOCKED');
  assert.strictEqual(got.phase_effect_admitted,false);
  assert.strictEqual(got.phase_observation,'UNAVAILABLE');
  assert.strictEqual(got.source_currentness,'UNVERIFIED');
  assert.strictEqual(got.phase_blockers[0],'CURRENT_RUNTIME_SOURCE_UNVERIFIED_OR_DRIFT');
  assert.strictEqual(got.fleet,'NO_CURRENT_MATERIAL_FLEET');
  for(const spoof of [
    {...entry,effect_admitted:true},
    {...entry,authority_effect:'ALLOW'},
    {...entry,execution_effect:'DOCKER_UP'},
    {...entry,desired_workers:64},
    {...entry,schema:'attacker-claim'}
  ]){
    const denied=ctx.projectActiveEcosystem({...base,material_fleet_lifecycle:spoof},{});
    assert.strictEqual(denied.phase_demand,null);
    assert.strictEqual(denied.phase_effect_admitted,false);
    assert.strictEqual(denied.phase_demand_state,'UNKNOWN');
  }
}
console.log('R9_READ_MODEL_0_1_32_FAIL_CLOSED_PASS');
'''
        r=subprocess.run(
            ["node","-e",script,str(JS)],
            text=True,capture_output=True,timeout=15
        )
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("R9_READ_MODEL_0_1_32_FAIL_CLOSED_PASS",r.stdout)


if __name__=="__main__":
    unittest.main()
