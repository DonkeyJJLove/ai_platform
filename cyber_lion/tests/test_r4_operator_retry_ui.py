from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = ROOT / "cyber_lion/app_coordination/local_intelligence_gateway.py"
CLUSTER = ROOT / "deploy/mission-control/v3/app.js"


class R4OperatorRetryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATEWAY.read_text(encoding="utf-8")
        cls.cluster = CLUSTER.read_text(encoding="utf-8")

    def test_delete_button_visible_near_mission_title_and_bound_to_safe_preview(self):
        s = self.source
        self.assertIn('id="missionDeleteQuick" type="button"', s)
        title = s.index('id="missionTitle"')
        button = s.index('id="missionDeleteQuick"')
        self.assertLess(button - title, 500, "Delete must not be hidden below huge phase output")
        self.assertIn("fetch('/api/missions/'+encodeURIComponent(mid)+'/delete-preview'", s)
        self.assertIn("JSON.stringify({spec_digest:p.spec_digest})", s)
        self.assertIn("if($('missionDeleteQuick'))$('missionDeleteQuick').disabled=readOnly", s)
        self.assertIn("if($('missionDeleteQuick'))$('missionDeleteQuick').disabled=true", s)

    def test_saas_status_projection_forwards_actual_broker_hop(self):
        # Live broker advertises automatic_hop=AVAILABLE. The old local
        # gateway discarded it while the panel demanded that exact field.
        self.assertIn(
            "('session_attestation_state','pending_count','channel_state',"
            "'transport','automatic_hop')",
            self.source,
        )
        self.assertIn("broker.automatic_hop!=='AVAILABLE'", self.source)

    def test_cognitive_prepare_requires_available_saas_transport_and_never_auto_activates(self):
        s = self.source
        snippet = s[s.index('let lpclBoundSyncBusy=false;'):
                    s.index('async function prepareCognitiveContext(){')]
        self.assertIn("/api/saas/broker/status", snippet)
        self.assertIn("['BOUND','EXPIRED','NOT_ATTESTED']", snippet)
        self.assertIn("idempotency_key:'lpcl-sync-'", snippet)
        self.assertIn("mission_id:mid", snippet)
        self.assertIn("await prepareCognitiveContext()", snippet)
        self.assertNotIn("activateLpcl(", snippet)
        self.assertNotIn("docker compose", snippet)
        self.assertIn("mission.cognitive_requirements?.providers", snippet)
        self.assertIn("COGNITIVE_PROVIDER_REQUIREMENTS_DRIFT", snippet)
        self.assertIn("await refreshCognitiveReadiness()", self.source)
        self.assertIn("if(cmcActive?.current_binding?.mission_id===lpclRegistered?.mission_id)", self.source)

    def test_cluster_follow_mode_refuses_historical_fallback(self):
        s = self.cluster
        self.assertIn("const run=selected?candidates.find(r=>r.run_id===selected):observedRun", s)
        self.assertIn("NO CURRENT FLEET OBSERVATION", s)
        self.assertIn("Historical 12/64", s)

    def test_lpcl_validation_without_mat04_does_not_enable_registration(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not installed")
        body = self.source
        fragment = body[
            body.index("function renderLpclIntake("):
            body.index("function invalidateLpclSource(")
        ]
        test = r"""
const vm=require('vm'),assert=require('node:assert/strict');
const buttons={};
const c={
 lpclValidated:{validated_digest:'a'.repeat(64),
  response:{source_currentness:{verification:'UNVERIFIED'}}},
 lpclRegistered:null,
 lpclBoundSyncBusy:false,
 lpclCognitiveState:null,
 lpclSourceState:null,
 $:id=>buttons[id]||(buttons[id]={disabled:false,textContent:''}),
 lpclRequiredCognitiveProviders:()=>[],
 lpclSourceDiagnostics:()=>({input_length:100,detected_key_count:10}),
 patchCards:()=>{},
 renderLpclCognitive:()=>{},
};
vm.runInNewContext(source,c);
c.renderLpclIntake('VALIDATED',{input_length:100,detected_key_count:10});
assert.equal(buttons.lpclRegisterButton.disabled,true,'Unverified source cannot register');
assert.equal(buttons.lpclActivateButton.disabled,true,'Unregistered source cannot activate');
c.lpclValidated.response.source_currentness.verification='VERIFIED';
c.renderLpclIntake('VALIDATED',{input_length:100,detected_key_count:10});
assert.equal(buttons.lpclRegisterButton.disabled,false,'Verified current source can register');
console.log('PASS_NO_MAT04_SOURCE_CURRENTNESS_IS_NOT_AUTHORITY');
"""
        result = subprocess.run(
            [node, "-e", "const source="+json.dumps(fragment)+";\n"+test],
            text=True,capture_output=True,timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:1800])
        self.assertIn("PASS_NO_MAT04", result.stdout)

    def test_source_embedded_js_parses(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not installed; dedicated Node workflow still required")
        start = self.source.index("<script>") + len("<script>")
        end = self.source.index("</script>", start)
        program = self.source[start:end]
        result = subprocess.run([node, "--check", "-"], input=program, text=True,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr[:1800])

    def test_operator_expired_saas_first_send_allowed_but_unavailable_or_backlog_fail_closed(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node not installed")
        source = self.source
        code = source[source.index('let lpclBoundSyncBusy=false;'):
                      source.index('async function prepareCognitiveContext(){')]
        probe = r'''
const vm = require("vm");
const assert = require("node:assert/strict");

function fixture({expired=false, alreadyRequested=false, ready=false, transportReady=true, backlog=0}={}) {
 let events=[], active=null, buttons={}, lastNote='';
 const mission='LION-R4-E2E-8L32M-TEST';
 const digest='a'.repeat(64);
 const ctx={
  lpclRegistered:{mission_id:mission,lpcl_digest:digest,validated_source:'LOCAL_MODEL_INFERENCE,SAAS_DELEGATION'},
  cmcActive:null,
  cmcGeneration:1,cmcActiveId:null,
  lpclSourceState:'REGISTERED',
  $:id=>buttons[id]||(buttons[id]={disabled:false,set textContent(v){lastNote=v},get textContent(){return lastNote}}),
  lpclRequiredCognitiveProviders:()=>['LOCAL','SAAS'],
  renderLpclIntake:state=>events.push('RENDER:'+state),
  cmcApi:async path=>{
   events.push('GET:'+path);
   if(path.endsWith('/process'))return {mission_id:mission,spec_digest:digest,state:'REGISTERED',cognitive_requirements:{providers:['LOCAL','SAAS']}};
   if(path.endsWith('/api/saas/broker/status'))return {session_attestation_state:expired?'EXPIRED':'BOUND',pending_count:backlog,automatic_hop:transportReady?'AVAILABLE':'UNAVAILABLE',channel_state:transportReady?'SENTINELX_MCP_READY':'WAITING_MEDIATOR'};
   if(path.endsWith('/messages'))return {messages:alreadyRequested?[{role:'USER',content:'LION cognitive synchronization bootstrap.'}]:[]};
   throw Error('UNEXPECTED_GET '+path);
  },
  cmcPost:async (path,body)=>{
   events.push('POST:'+path);
   assert.equal(path,'/api/conversations');
   assert.equal(body.mission_id,mission);
   assert.equal(body.idempotency_key,'lpcl-sync-'+digest.slice(0,40));
   return {state:'BOUND',conversation_id:'conv-canonical-r4',
    current_binding:{mission_id:mission,binding_epoch:1}};
  },
  cmcRefreshList:async()=>events.push('LIST'),
  cmcOpen:async id=>{
   events.push('OPEN:'+id);
   ctx.cmcActive={state:'BOUND',conversation_id:id,current_binding:{mission_id:mission,binding_epoch:1}};
   ctx.cmcActiveId=id;
  },
  refreshCognitiveReadiness:async()=>({readiness:{readiness:ready?'READY':'WAITING'}}),
  prepareCognitiveContext:async()=>events.push('DISPATCH_DUAL_SYNC'),
  cmcPoll:async()=>events.push('POLL'),
  encodeURIComponent,
  Error,
 };
 vm.runInNewContext(source,ctx);
 return {ctx,events,note:()=>lastNote};
}

(async()=>{
 const ok=fixture();await ok.ctx.prepareBoundCognition();
 assert.equal(ok.events.filter(x=>x==='DISPATCH_DUAL_SYNC').length,1);
 assert.equal(ok.events.filter(x=>x==='POST:/api/conversations').length,1);
 assert.match(ok.note(),/DUAL zgłoszono/);
 const expired=fixture({expired:true});
 await expired.ctx.prepareBoundCognition();
 assert.equal(expired.events.filter(x=>x==='DISPATCH_DUAL_SYNC').length,1);
 assert.match(expired.note(),/READY obu providerów przed autoryzacją/);
 const unavailable=fixture({expired:true,transportReady:false});
 await assert.rejects(()=>unavailable.ctx.prepareBoundCognition(),/SAAS_TRANSPORT_NOT_READY/);
 assert.equal(unavailable.events.filter(x=>x.startsWith('POST:')).length,0);
 const backlog=fixture({expired:true,backlog:1});
 await assert.rejects(()=>backlog.ctx.prepareBoundCognition(),/SAAS_BACKLOG_PRESENT/);
 assert.equal(backlog.events.filter(x=>x.startsWith('POST:')).length,0);
 const requested=fixture({alreadyRequested:true,expired:true});
 await requested.ctx.prepareBoundCognition();
 assert.equal(requested.events.filter(x=>x==='DISPATCH_DUAL_SYNC').length,0);
 assert.match(requested.note(),/bez ponowienia/);
 const done=fixture({ready:true});
 await done.ctx.prepareBoundCognition();
 assert.equal(done.events.filter(x=>x==='DISPATCH_DUAL_SYNC').length,0);
 console.log('PASS JS OPERATOR PANEL: 6 scenarios incl expired and no replay; no auto activation');
})().catch(e=>{console.error(e);process.exit(1)});
'''
        completed = subprocess.run([node, "-e", "const source=" + json.dumps(code) + ";\n" + probe],
                                   text=True, capture_output=True, timeout=25)
        self.assertEqual(completed.returncode, 0,
                         completed.stderr[-2600:] + completed.stdout[-1200:])
        self.assertIn("PASS JS OPERATOR PANEL", completed.stdout)


if __name__ == "__main__":
    unittest.main()
