const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require('C:/Users/d2j3/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'../..'),out=path.resolve(root,'../../outputs');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const gateway=read('cyber_lion/app_coordination/local_intelligence_gateway.py').match(/UI=r'''([\s\S]*?)'''/)[1];
const report={schema:'lion.r2-ui-browser/v1',scope:'MOCKED_HEADLESS_EDGE; NO_LIVE_EFFECT',checks:{},errors:[],events:[],unexpected:[],source_hashes:{}};
for(const p of ['cyber_lion/app_coordination/local_intelligence_gateway.py','deploy/mission-control/v3/app.js','deploy/mission-control/v3/control-v3.js','deploy/mission-control/v3/index.html'])report.source_hashes[p]=crypto.createHash('sha256').update(read(p)).digest('hex');
const supervisor={schema:'lion.supervisor-projection/v1',channel:'READY_FOR_HANDOFF',session:'BOUND',model:'fixture supervisor',transport:'SESSION_MEDIATED',automatic_hop:false,authority:'NONE',pending_state:'NONE',pending_count:0,last_receipt_state:'NONE',freshness:{state:'FRESH'},lease:{state:'ACTIVE'},unknown_reasons:[]};
let focus='M1',revision=1,holdMission=null,releaseHeld=null,heldReady=null,phasePosts=0;
const missions=['M1','M2','H1'].map(mission_id=>({mission_id,title:mission_id,state:mission_id==='H1'?'SUPERSEDED':'RUNNING',runtime_state:'RUNNING',progress:25,current_phase:'P1',objective:'fixture objective'}));
function snapshot(id){
 const historical=id==='H1',phase={phase_id:'P1',title:'Very long phase title '.repeat(12),status:'RUNNING',progress:revision,handler_id:'fixture.handler',handler_version:'1',blocker:'fixture blocker',evidence_count:1,capabilities:{INSPECT:{supported:true},PAUSE:{supported:!historical,control_token:'fixture-token',reason:historical?'HISTORICAL_PHASE':'AVAILABLE'},STOP:{supported:false,reason:'NOT_AVAILABLE'}}};
 const events=[{id:'event1',protocol:'EVIDENCE',from_id:'worker1',to_id:'control',observed_at:'2026-09-14T12:00:00Z',phase:'P1',payload:{status:'OBSERVED',revision}}];
 const worker={pod_uid:'pod1',pod_name:'fixture-pod',logical_id:'logical1',material_drone_id:'drone1',phase:'Running',ready:true,restarts:0};
 return {mission_id:id,title:id,state:historical?'SUPERSEDED':'RUNNING',runtime_state:'RUNNING',updated_at:'2026-09-14T12:00:00Z',normalized_schema_version:'lion.mission-runtime/v1',projection_version:'lion.mission-projection/v1',projection_revision:'revision-'+revision,logical_count:1,material_target:1,materialized:1,ready:1,schema_context:{record_class:historical?'HISTORICAL_PARTIAL_SCHEMA':'CURRENT_SCHEMA',missing_fields:[]},process:{objective:'fixture objective',description:'fixture description',current_phase:null,progress:25,authority_state:'NONE'},phases:[phase],workers:[worker],logical:[],capabilities:{},protocol_messages:events,normalized_runtime:{record_class:historical?'HISTORICAL_PARTIAL_SCHEMA':'CURRENT_SCHEMA',runtime:{current_phase:'P1',current_phase_reason:'DERIVED_SINGLE_ACTIVE_PHASE'},phases:[phase],fleet:{material_workers:[worker]},environment:{namespace:'fixture-ns',hosts:null,node:null,image:null},observability:{events,source_updated_at:'2026-09-14T12:00:00Z'},gaps:[{field:'environment.hosts',reason:historical?'HISTORICAL_NOT_RECORDED':'NOT_RECORDED'}]},execution_assignments:[{assignment_id:'assign1',material_drone_id:'drone1'}],execution_receipts:[{receipt_id:'receipt1',material_drone_id:'drone1'}]};
}
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({channel:'msedge',headless:true});
  for(const mode of ['gateway','control']){
   focus='M1';revision=1;
   const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage();
   page.on('pageerror',e=>report.errors.push({mode,message:e.message}));
   await page.addInitScript(()=>{window.setInterval=()=>0;});
   await page.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url()),p=url.pathname;
    if(url.origin!=='http://candidate.test'){report.unexpected.push(req.url());return route.abort();}
    if(p==='/')return route.fulfill({contentType:'text/html',body:mode==='gateway'?gateway:read('deploy/mission-control/v3/index.html')});
    if(['/app.js','/control-v3.js','/passive.js','/app.css'].includes(p))return route.fulfill({contentType:p.endsWith('.css')?'text/css':'text/javascript',body:read('deploy/mission-control/v3'+p)});
    let value;
    if(['/api/missions/recent','/api/v3/missions/recent'].includes(p))value={missions,focus_mission_id:focus};
    else if(/^\/api\/(?:v3\/)?missions\/[^/]+\/process$/.test(p)){
     const id=p.split('/').at(-2);value=snapshot(id);
     if(holdMission===id){holdMission=null;heldReady?.();await new Promise(resolve=>{releaseHeld=resolve;});}
    }
    else if(p.endsWith('/phase-actions')){const body=req.postDataJSON();assert.deepEqual(Object.keys(body).sort(),['action','control_token','phase_id']);assert.equal(body.action,'PAUSE');phasePosts++;value={receipt:{receipt_id:'control-receipt'},readback:{driver_state:'PAUSED',phase_status:'RUNNING',receipt_id:'control-receipt'}};}
    else if(p==='/api/state')value={model:'fixture',material:{},mission_control:{},supervisor_projection:supervisor};
    else if(p==='/api/v3/saas/status')value={supervisor_projection:supervisor};
    else if(p==='/api/v3/evidence-sources')value={sources:[]};
    else if(p==='/api/threads')value={threads:[{thread_id:'t1',title:'test'}]};
    else if(p==='/api/threads/t1')value={thread_id:'t1',title:'test',messages:[]};
    else if(p==='/api/ui-runtime-events'){report.events.push(req.postDataJSON());value={status:'RECORDED'};}
    else if(p==='/api/summary')value={ok:true,summary:{},fleet:{},observation:{}};
    else if(p==='/api/adapters')value={adapters:[{adapter_id:'fixture',supported_process_classes:['TEST'],control_authority:'OBSERVATION_ONLY'}]};
    else if(p==='/api/runs')value={runs:[{run_id:'run1',status:'COMPLETE',host:'fixture-host',runtime:'fixture-runtime',adapter_type:'TEST',process_class:'TEST'}]};
    else if(p==='/api/runs/run1/events')value={events:[{event_id:'run-event',event_type:'RECORDED',run_id:'run1',timestamp:1,payload:{observed:true}}]};
    else {report.unexpected.push(req.method()+' '+p);return route.fulfill({status:404,json:{error:'unmocked'}});}
    await route.fulfill({json:value});
   });
   await page.goto('http://candidate.test/');
   const phaseRoot=mode==='gateway'?'#missionPhases':'#mcPhases';
   await page.locator(phaseRoot+' .semantic-card').waitFor();
   const poll=mode==='gateway'?()=>Promise.all([state(),refreshMissions()]):()=>Promise.all([refresh(),mcRefresh()]);
   await page.evaluate(poll);
   const initial=await page.locator(phaseRoot).innerText();assert.match(initial,/fixture.handler/);assert.match(initial,/fixture blocker/);assert.match(initial,/Evidence count/);
   assert.equal(await page.locator(phaseRoot+' [data-phase-action="STOP"]').count(),0);
   await page.locator(phaseRoot+' [data-phase-action="PAUSE"]').click();
   const result=mode==='gateway'?'#phaseControlResult':'#mcPhaseControlResult';
   await page.waitForFunction(id=>document.querySelector(id)?.textContent.includes('control-receipt'),result);
   const phaseRaw=page.locator(phaseRoot+' details').first();await phaseRaw.evaluate(n=>n.open=true);
   if(mode==='gateway')await page.locator('#q').fill('Preserve this draft');
   await page.evaluate(({mode,phaseRoot})=>{
    const input=mode==='gateway'?document.querySelector('#q'):document.querySelector('#mcMissionSelect');input.focus();
    if(mode==='gateway')input.setSelectionRange(2,8);
    window.__input=input;window.__phase=document.querySelector(phaseRoot+' .semantic-card');window.__raw=window.__phase.querySelector('details');
    const scroll=mode==='gateway'?document.querySelector('.app'):document.scrollingElement;scroll.scrollTop=180;window.__scroll=scroll;window.__scrollTop=scroll.scrollTop;
   },{mode,phaseRoot});
   for(let i=0;i<5;i++){revision++;await page.evaluate(poll);}
   const invariant=await page.evaluate(({mode,phaseRoot})=>({node:window.__phase===document.querySelector(phaseRoot+' .semantic-card'),raw:window.__raw.open,input:document.activeElement===window.__input,scroll:window.__scroll.scrollTop===window.__scrollTop,draft:mode==='gateway'?window.__input.value:null}),{mode,phaseRoot});
   assert.deepEqual(invariant,{node:true,raw:true,input:true,scroll:true,draft:mode==='gateway'?'Preserve this draft':null});
   report.checks[mode+'_refresh_invariants']={pass:true,...invariant};
   if(mode==='gateway')await page.locator('.mission-item[data-mid="H1"]').click();else await page.locator('#mcMissionSelect').selectOption('H1');
   await page.waitForFunction(mode=>mode==='gateway'?missionData?.mission_id==='H1':MC_DATA?.mission_id==='H1',mode);
   focus='M2';await page.evaluate(poll);
   assert.equal(await page.evaluate(mode=>mode==='gateway'?missionData.mission_id:MC_DATA.mission_id,mode),'H1');
   assert.equal(await page.locator(phaseRoot+' [data-phase-action]').count(),0);
   if(mode==='gateway')await page.getByRole('button',{name:'Return to focus',exact:true}).click();else await page.locator('#mcReturnFocus').click();
   await page.waitForFunction(mode=>mode==='gateway'?missionData?.mission_id==='M2':MC_DATA?.mission_id==='M2',mode);
   report.checks[mode+'_pin_and_return']={pass:true,historical_pinned:'H1',focus_after_return:'M2',global_supervisor:'BOUND'};
   if(mode==='gateway'){
    const waiting=new Promise(resolve=>{heldReady=resolve;});holdMission='M2';
    await page.evaluate(()=>{void refreshMissionProcess();});await waiting;
    revision=99;await page.evaluate(()=>refreshMissionProcess());releaseHeld();releaseHeld=null;
    await page.waitForTimeout(80);
    assert.equal(await page.evaluate(()=>missionData.projection_revision),'revision-99');
    report.checks.gateway_stale_same_mission_response={pass:true};
   }else{
    const waiting=new Promise(resolve=>{heldReady=resolve;});holdMission='M2';
    await page.evaluate(()=>{void mcRefresh();});await waiting;
    await page.locator('#mcMissionSelect').selectOption('H1');releaseHeld();releaseHeld=null;
    await page.waitForFunction(()=>MC_DATA?.mission_id==='H1'&&!MC_REFRESHING);
    report.checks.control_slow_poll_selection={pass:true};
   }
   const worker=mode==='gateway'?'#missionWorkers':'#mcV3Workers';assert.match(await page.locator(worker).innerText(),/assign1/);assert.match(await page.locator(worker).innerText(),/receipt1/);
   await page.setViewportSize({width:390,height:844});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
   assert.equal(overflow,false);report.checks[mode+'_narrow_layout']={pass:true,width:390,no_page_horizontal_overflow:true};
   await page.screenshot({path:path.join(out,'r2-'+mode+'-candidate.png')});await context.close();
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.events,[]);assert.deepEqual(report.unexpected,[]);assert.equal(phasePosts,2);
  report.checks.phase_containment_ui={pass:true,mocked_posts:phasePosts,no_live_effect:true};report.result='PASS';
 }catch(e){report.result='FAIL';report.failure={name:e.name,message:e.message,stack:e.stack};process.exitCode=1;}
 finally{if(browser)await browser.close();fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'r2-ui-browser.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));}
})();
