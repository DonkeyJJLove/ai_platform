/* Candidate-only acceptance. All HTTP is mocked; no live services are contacted.
 * Run with bundled Node. Duration is 360 accelerated polls / 30 simulated minutes,
 * never evidence of a 30-minute wall-clock deployment observation.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {chromium}=require('C:/Users/d2j3/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sourcePath=path.resolve(__dirname,'../app_coordination/local_intelligence_gateway.py');
const outputPath=process.argv[2]||path.resolve(__dirname,'../../../../outputs/browser-candidate.json');
const source=fs.readFileSync(sourcePath,'utf8');
const match=source.match(/UI=r'''([\s\S]*?)'''/);
assert.ok(match,'Python source contains raw UI literal');
const html=match[1];
const projection={schema:'lion.supervisor-projection/v1',channel:'READY_FOR_HANDOFF',session:'BOUND',model:'GPT-5.6 Sol',transport:'CHATGPT_SENTINELX_SESSION_MEDIATED',pending:null,pending_count:0,pending_state:'NONE',last_receipt:null,last_receipt_state:'NONE',lease:{state:'ACTIVE',expires_at:'2026-09-14T13:00:00Z'},authority:'NONE',automatic_hop:false,freshness:{state:'FRESH',observed_at:'2026-09-14T12:00:00Z'},unknown_reasons:[]};
const statePayload={model:'local-test-model',gpu:'fixture',rag_status:'fixture',web_capability:'fixture',repository_capability:'fixture',authority_effect:'NONE',material:{healthy:0},mission_control:{},saas_session_bridge:{pending:null},supervisor_projection:projection};
const report={schema:'lion.epoch3-browser-candidate/v1',scope:'CANDIDATE_MOCKED_BROWSER_ONLY',live_service_mutations:false,source_path:sourcePath,source_sha256:crypto.createHash('sha256').update(source).digest('hex'),ui_sha256:crypto.createHash('sha256').update(html).digest('hex'),browser:'headless Microsoft Edge via Playwright',checks:{},polling:{iterations:360,cadence_seconds:5,simulated_duration_minutes:30,wall_clock_30_minute_claim:false},runtime_events:[],page_errors:[],unexpected_requests:[],started_at:new Date().toISOString()};
let browser,chatPayload,stateReads=0,missionReads=0;
const baseChat={answer:'Candidate supervisor answer.',route:'LION_CAPABILITY_CURRENTNESS',tool_calls:['fixture.read'],currentness:[{subject:'fixture',status:'OBSERVED'}],material_receipts:[{receipt_digest:'fixture-receipt'}],supervisor_projection:projection,web_fetches:[{title:'HTTPS evidence',url:'https://example.test/evidence'},{title:'HTTP evidence',url:'http://example.test/read-only'},{title:'invalid javascript source',url:'javascript:alert(1)'},{title:'invalid data source',url:'data:text/html,hello'}],web_sources:[]};
const started=Date.now();
(async()=>{
  try{
    browser=await chromium.launch({channel:'msedge',headless:true});
    const context=await browser.newContext({viewport:{width:1440,height:1100}});
    const page=await context.newPage();
    page.on('pageerror',error=>report.page_errors.push({name:error.name,message:error.message}));
    await page.addInitScript(()=>{window.__scheduledIntervals=[];window.setInterval=(callback,delay)=>{window.__scheduledIntervals.push({callback,delay});return window.__scheduledIntervals.length;};});
    await page.route('**/*',async route=>{
      const request=route.request(),url=new URL(request.url());
      const pathname=url.pathname;
      if(url.origin!=='http://lion-candidate.test'){
        report.unexpected_requests.push(request.url());return route.abort();
      }
      if(pathname==='/')return route.fulfill({status:200,contentType:'text/html; charset=utf-8',body:html});
      let body;
      if(pathname==='/api/state'){stateReads++;body=statePayload;}
      else if(pathname==='/api/missions/recent'){missionReads++;body={missions:[],focus_mission_id:null};}
      else if(pathname==='/api/threads'&&request.method()==='GET')body={threads:[{thread_id:'fixture-thread',title:'Candidate test'}]};
      else if(pathname==='/api/threads/fixture-thread'&&request.method()==='GET')body={thread_id:'fixture-thread',title:'Candidate test',messages:[]};
      else if(pathname==='/api/threads/fixture-thread/chat'&&request.method()==='POST')body=chatPayload;
      else if(pathname==='/api/ui-runtime-events'&&request.method()==='POST'){report.runtime_events.push(request.postDataJSON());body={status:'RECORDED'};}
      else {report.unexpected_requests.push(request.method()+' '+request.url());return route.fulfill({status:404,json:{error:'unmocked endpoint'}});}
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
    });
    chatPayload=baseChat;
    await page.goto('http://lion-candidate.test/');
    await page.waitForFunction(()=>activeThreadId==='fixture-thread'&&!stateRefreshing&&!missionsRefreshing&&document.querySelector('#saasCards [data-key="SESSION"] .v')?.textContent==='BOUND');
    assert.equal(await page.evaluate(()=>window.__scheduledIntervals.some(x=>x.delay===5000)),true);
    const initialAssistants=await page.locator('.msg.assistant').count();
    await page.locator('#q').fill('mamy łączność z SaaS?');
    await page.evaluate(()=>go());
    await page.waitForFunction(()=>!stateRefreshing);
    assert.equal(await page.locator('.msg.assistant').count(),initialAssistants+1);
    assert.equal(await page.locator('.msg.assistant .md').last().innerText(),baseChat.answer);
    assert.equal(await page.locator('#evidence').isVisible(),true);
    const evidenceText=await page.locator('#evidence').innerText();
    assert.match(evidenceText,/fixture\.read/);assert.match(evidenceText,/Currentness/);assert.match(evidenceText,/Material receipts.*1/s);
    const hrefs=await page.locator('#evidence a').evaluateAll(nodes=>nodes.map(node=>node.href));
    assert.deepEqual(hrefs,['https://example.test/evidence','http://example.test/read-only']);
    assert.equal(await page.locator('#evidence a').evaluateAll(nodes=>nodes.every(node=>node.rel.includes('noopener')&&node.rel.includes('noreferrer'))),true);
    assert.match(evidenceText,/invalid javascript source/);
    assert.equal(report.runtime_events.length,0);assert.equal(report.page_errors.length,0);
    report.checks.actual_go_success={pass:true,new_assistant_messages:1,evidence_visible:true,no_reference_error:true};
    report.checks.source_protocols={pass:true,allowed:['https','http'],non_links:['javascript','data'],hrefs};
    chatPayload={...baseChat,answer:'Malformed optional arrays handled.',tool_calls:{wrong:'type'},currentness:'wrong',material_receipts:42,web_fetches:{url:'wrong'},web_sources:null};
    const beforeMalformed=await page.locator('.msg.assistant').count();
    await page.evaluate(()=>go('Test malformed optional evidence arrays'));
    await page.waitForFunction(()=>!stateRefreshing);
    assert.equal(await page.locator('.msg.assistant').count(),beforeMalformed+1);
    assert.equal(await page.locator('.msg.assistant .md').last().innerText(),chatPayload.answer);
    assert.equal(report.runtime_events.length,0);
    report.checks.malformed_optional_arrays={pass:true};
    await page.locator('#q').fill('Preserve focused draft');
    await page.locator('#q').focus();
    await page.evaluate(()=>{qEl.setSelectionRange(3,9);window.__candidateNodes=Array.from(document.querySelectorAll('#saasCards .card'));window.__candidateInput=qEl;});
    const readStart=stateReads,missionStart=missionReads;
    const identity=await page.evaluate(async()=>{
      for(let i=0;i<360;i++)await Promise.allSettled([state(),refreshMissions()]);
      return {nodesStable:window.__candidateNodes.every((node,i)=>node===document.querySelectorAll('#saasCards .card')[i]),inputStable:window.__candidateInput===qEl,focused:document.activeElement===qEl,value:qEl.value,selection:[qEl.selectionStart,qEl.selectionEnd]};
    });
    assert.equal(stateReads-readStart,360);assert.equal(missionReads-missionStart,360);
    assert.deepEqual(identity,{nodesStable:true,inputStable:true,focused:true,value:'Preserve focused draft',selection:[3,9]});
    report.polling={...report.polling,state_reads:stateReads-readStart,mission_reads:missionReads-missionStart,execution:'Accelerated awaited calls to the same state()/refreshMissions() functions used by the 5000ms interval; time is simulated, not elapsed.'};
    report.checks.keyed_identity_and_input={pass:true,...identity};
    const assistantCount=await page.locator('.msg.assistant').count();
    await page.evaluate(()=>{window.__originalEvidenceHtml=evidenceHtml;evidenceHtml=()=>{throw new ReferenceError('candidate injected evidence render failure');};});
    await page.evaluate(()=>go('Trigger injected rendering failure'));
    await page.waitForFunction(()=>!stateRefreshing);
    assert.equal(await page.locator('.msg.assistant').count(),assistantCount);
    assert.equal(report.runtime_events.length,1);
    assert.equal(report.runtime_events[0].event_class,'UI_RUNTIME_ERROR');
    assert.equal(report.runtime_events[0].operation,'chat.submit');
    assert.equal(report.runtime_events[0].error_name,'ReferenceError');
    assert.match(report.runtime_events[0].message,/candidate injected/);
    assert.match(await page.locator('#route').innerText(),/UI_RUNTIME_ERROR/);
    await page.evaluate(()=>{evidenceHtml=window.__originalEvidenceHtml;});
    report.checks.injected_render_failure={pass:true,expected_injected_error:true,assistant_message_added:false,event_posted:true};
    assert.deepEqual(report.page_errors,[]);assert.deepEqual(report.unexpected_requests,[]);
    report.result='PASS';
  }catch(error){report.result='FAIL';report.failure={name:error.name,message:error.message,stack:error.stack};process.exitCode=1;}
  finally{
    if(browser)await browser.close();
    report.finished_at=new Date().toISOString();report.wall_clock_seconds=(Date.now()-started)/1000;
    fs.mkdirSync(path.dirname(outputPath),{recursive:true});fs.writeFileSync(outputPath,JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({result:report.result,evidence:outputPath,wall_clock_seconds:report.wall_clock_seconds,checks:report.checks,failure:report.failure},null,2));
  }
})();
