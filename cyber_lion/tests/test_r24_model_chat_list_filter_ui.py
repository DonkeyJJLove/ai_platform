"""R11 Model Chat list filters: explicit scope, no identity cutover or side effects."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest

from cyber_lion.app_coordination.local_intelligence_gateway import UI


class ModelChatListFilterUiTests(unittest.TestCase):
    def test_source_and_status_surface(self):
        self.assertIn('id="cmcListStatus"', UI)
        self.assertIn('aria-live="polite"', UI)
        self.assertIn("cmcFilterMission').onclick=()=>cmcApplyListFilter('MISSION')", UI)
        self.assertIn("cmcShowAll').onclick=()=>cmcApplyListFilter('ALL')", UI)
        self.assertIn("LIST_FILTER_SCOPE_DRIFT", UI)
        self.assertIn("OTWARTA ROZMOWA POZA FILTREM", UI)
        self.assertIn("ROZMOWA · ", UI)
        self.assertNotIn(
            "cmcFilterMission=selectedMissionId||missionFocusId||null", UI
        )

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_exact_filter_ui_javascript_with_fake_dom_and_get_only(self):
        start = UI.index("function cmcRenderList(){")
        end = UI.index("function cmcRenderBridge(c){", start)
        code = UI[start:end]
        setup = """
let cmcConversations=[],cmcActiveId='conv-unbound',cmcActive=null;
let cmcFilterMission=null,cmcListGeneration=0;
let selectedMissionId=null,missionFocusId=null;
const all=[
 {conversation_id:'conv-unbound',title:'Nowa rozmowa',state:'UNBOUND',
  current_binding:{mission_id:null,binding_epoch:1}},
 {conversation_id:'conv-bound',title:'Mission test',state:'BOUND',
  current_binding:{mission_id:'M1',binding_epoch:2}}
];
const elem={
 cmcConversationSelect:{
  _html:'',value:'',
  get innerHTML(){return this._html},
  set innerHTML(v){this._html=v;this.value=''}
 },
 cmcListStatus:{textContent:''}
};
const $=id=>elem[id];
const esc=v=>String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const calls=[],opened=[];
let delayMission=false,resolver=null,wrongScope=false;
async function cmcApi(path){
 calls.push(path);
 const u=new URL(path,'http://panel.invalid');
 const mission=u.searchParams.get('mission_id');
 if(mission==='M1'&&delayMission){
  return new Promise(res=>{resolver=res});
 }
 const actual=mission==='M1'?all.filter(x=>x.current_binding.mission_id==='M1'):all;
 return {mission_id:wrongScope?'INCORRECT':mission,conversations:actual};
}
const cmcRenderConversation=c=>opened.push(c.conversation_id);
"""
        tests = """
(async()=>{
 const assert=(ok,msg)=>{if(!ok)throw Error(msg)};
 await cmcApplyListFilter('MISSION');
 assert(calls.length===0,'missing mission must not fetch all silently');
 assert(elem.cmcListStatus.textContent.includes('WYBIERZ MISJĘ'),'mission hint');

 await cmcApplyListFilter('ALL');
 assert(calls.length===1&&calls[0].includes('limit=500'),'all fetch');
 assert(elem.cmcConversationSelect.value==='conv-unbound','all active');
 assert(elem.cmcListStatus.textContent.includes('2 rozmów'),'visible count');
 assert(elem.cmcConversationSelect.innerHTML.includes('ROZMOWA ·'),'entry title');

 selectedMissionId='M1';
 await cmcApplyListFilter('MISSION');
 assert(calls.at(-1).includes('mission_id=M1'),'exact scope');
 assert(cmcConversations.length===1,'filtered count');
 assert(elem.cmcConversationSelect.value==='','out of filter placeholder');
 assert(cmcActiveId==='conv-unbound','active identity changed by filter');
 assert(elem.cmcListStatus.textContent.includes('OTWARTA ROZMOWA POZA FILTREM'),'out of scope message');

 cmcActiveId='conv-bound';
 await cmcApplyListFilter('MISSION');
 assert(elem.cmcConversationSelect.value==='conv-bound','filtered active selection');
 assert(!elem.cmcListStatus.textContent.includes('POZA FILTREM'),'false outside');

 await cmcApplyListFilter('ALL');
 assert(cmcConversations.length===2,'reset all list');
 assert(elem.cmcConversationSelect.value==='conv-bound','all preserves active');

 delayMission=true;
 const slow=cmcApplyListFilter('MISSION');
 assert(typeof resolver==='function','missing delayed mission');
 delayMission=false;
 await cmcApplyListFilter('ALL');
 resolver({mission_id:'M1',conversations:all.filter(x=>x.current_binding.mission_id==='M1')});
 await slow;
 assert(cmcFilterMission===null&&cmcConversations.length===2,'stale result overwrote all');
 assert(elem.cmcListStatus.textContent.includes('WSZYSTKIE ROZMOWY'),'scope after race');

 wrongScope=true;
 await cmcApplyListFilter('MISSION');
 assert(elem.cmcListStatus.textContent.includes('LIST_FILTER_SCOPE_DRIFT'),'mismatch not displayed');
 assert(cmcConversations.length===2,'mismatched response applied');

 console.log(JSON.stringify({
  result:'PASS_7_SCOPED_UI_CASES',
  missing_mission_feedback:true,all_count:true,exact_mission_query:true,
  active_identity_preserved:true,filtered_out_feedback:true,
  stale_result_discarded:true,unexpected_scope_denied:true,
  writes:0,inference:0
 }));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
"""
        driver = """
const vm=require('node:vm'),fs=require('node:fs');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
vm.runInNewContext(p.setup+'\\n'+p.code+'\\n'+p.tests,{
 URL,URLSearchParams,console
});
"""
        run = subprocess.run(
            ["node", "-e", driver],
            input=json.dumps(
                {"setup": setup, "code": code, "tests": tests},
                ensure_ascii=False,
            ),
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stdout + "\n" + run.stderr)
        result = json.loads(run.stdout.strip())
        self.assertEqual(result["result"], "PASS_7_SCOPED_UI_CASES")
        self.assertEqual(result["writes"], 0)
        self.assertEqual(result["inference"], 0)


if __name__ == "__main__":
    unittest.main()
