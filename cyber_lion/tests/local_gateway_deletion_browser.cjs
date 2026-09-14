const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch({channel:'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1280,height:800}}),errors=[],polls=[];
let threads=[{thread_id:'owned',title:'Owned conversation'}];
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.route('http://fixture.test/**',async route=>{
 const request=route.request(),path=new URL(request.url()).pathname;let body={};
 if(path==='/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.argv[2],'utf8')});
 if(path==='/api/threads')body=request.method()==='POST'?{thread_id:'new',title:'New'}:{threads};
 else if(path==='/api/threads/owned'&&request.method()==='DELETE'){threads=[];body={deleted:true};}
 else if(path==='/api/threads/owned')body={...threads[0],messages:[]};
 else if(path==='/api/missions/recent')body={missions:[]};
 else if(path==='/api/state')body={supervisor_projection:{session:'EXPIRED',pending:{request_id:'unowned'},automatic_hop:false}};
 else if(path.startsWith('/api/saas/requests/')){polls.push(path);body={status:'PENDING'};}
 return route.fulfill({json:body});
});
const report={scope:'REAL_EDGE_CANDIDATE_UI_WITH_ISOLATED_HTTP_FIXTURES',production_changes:false};
try{
 await page.goto('http://fixture.test/');await page.waitForFunction(()=>activeThreadId==='owned');
 await page.waitForTimeout(1700);assert.equal(polls.length,0,'global request must not attach to conversation');
 await page.evaluate(()=>{resetMessages();addMsg('user','DELETED QUESTION');addMsg('assistant','DELETED ANSWER');patchHtml(evidenceEl,'DELETED EVIDENCE');debugEl.textContent='DELETED DEBUG';lastPayload={answer:'DELETED ANSWER'};});
 await page.evaluate(()=>{void pollSaas({request_id:'owned-request',thread_id:'owned'});});
 await page.waitForTimeout(1700);assert.equal(polls.length,1);
 await page.locator('[data-delete="owned"]').click();await page.waitForFunction(()=>pendingSaasPolls.size===0&&activeThreadId===null);
 const count=polls.length;await page.waitForTimeout(1800);assert.equal(polls.length,count);
 assert.equal(await page.evaluate(()=>busyEl.textContent),'');
 assert.equal(await page.evaluate(()=>messagesEl.querySelectorAll('.msg').length),1);
 assert.ok(!(await page.evaluate(()=>messagesEl.textContent)).includes('DELETED'));
 assert.equal(await page.evaluate(()=>evidenceEl.textContent+debugEl.textContent),'');
 assert.equal(await page.evaluate(()=>lastPayload),null);
 await page.reload();await page.waitForTimeout(1700);assert.equal(polls.length,count,'deleted request must not return after reload');
 report.cancellation={visible_messages_removed:true,evidence_removed:true,last_payload_cleared:true,global_not_adopted:true,delete_stops_poll:true,busy_cleared:true,reload_no_resurrection:true};
 // An already fetched thread response must not resurrect a deleted conversation.
 let releaseRead;const readGate=new Promise(resolve=>releaseRead=resolve);let readStarted;
 const readStartedGate=new Promise(resolve=>readStarted=resolve);
 await page.route('http://fixture.test/api/threads/late',async route=>{
  if(route.request().method()==='DELETE')return route.fulfill({json:{deleted:true}});
  readStarted();await readGate;return route.fulfill({json:{thread_id:'late',title:'Late',messages:[{role:'user',content:'LATE DELETED MESSAGE'}]}});
 });
 await page.evaluate(()=>{void openThread('late')});await readStartedGate;
 await page.evaluate(()=>deleteThread('late'));releaseRead();await page.waitForTimeout(200);
 assert.equal(await page.evaluate(()=>activeThreadId),'new');
 assert.ok(!(await page.evaluate(()=>messagesEl.textContent)).includes('LATE DELETED'));
 report.cancellation.late_read_cannot_resurrect=true;
 report.layout=[];
 for(const width of [1280,390]){
  await page.setViewportSize({width,height:800});
  const dimensions=await page.evaluate(()=>{
   const host=document.getElementById('missionPhases');
   host.innerHTML=phaseCard({phase_id:'fixture',title:'Change request deadline from terminal expiry to advisory overdue state',status:'PASS',progress:100,detail:'Long detail '.repeat(150),control_unavailable_reason:'NOT_EXACT_CURRENT_PHASE'}, {}, esc);
   const box=host.firstElementChild.getBoundingClientRect();return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,phaseHeight:box.height,tooltip:host.querySelector('[title]').title};
  });
  assert.ok(dimensions.documentWidth<=width,JSON.stringify(dimensions));assert.ok(dimensions.phaseHeight<150,JSON.stringify(dimensions));
  report.layout.push(dimensions);
 }
 assert.deepEqual(errors,[]);report.result='PASS';
}catch(e){report.result='FAIL';report.error=e.stack;process.exitCode=1;}
finally{report.page_errors=errors;fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
})();
