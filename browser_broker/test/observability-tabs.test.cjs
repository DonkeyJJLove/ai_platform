'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const main=fs.readFileSync(path.join(__dirname,'..','src','main.cjs'),'utf8');
const overview=fs.readFileSync(path.join(__dirname,'..','observability-preview','LION_Cluster_System_Tabs_Preview.html'),'utf8');
const local=fs.readFileSync(path.join(__dirname,'..','local-gpt.html'),'utf8');
const digest=x=>createHash('sha256').update(x).digest('hex');
test('Mission Control Cluster System are peers on the LEFT and not nested',()=>{
 assert(main.includes("left_tabs:['mission','cluster','system']"));
 assert(main.includes("right_tabs:['panel','saas','local']"));
 assert(main.includes('views=[saas,panel,local,cluster,system,mission,leftTabs,rightTabs]'));
 assert(main.includes("mission.setBounds(activeLeftTab==='mission'?L:HL)"));
 assert(main.includes("cluster.setBounds(activeLeftTab==='cluster'?L:HL)"));
 assert(main.includes("system.setBounds(activeLeftTab==='system'?L:HL)"));
});
test('LPCL SaaS and Local GPT are sibling right surfaces',()=>{
 for(const key of ['panel','saas','local'])
  assert(main.includes(key+".setBounds(activeRightTab==='"+key+"'?R:HR)"));
 for(const tab of ['panel','saas','local'])assert(main.includes('lion-right://'+tab));
 for(const tab of ['mission','cluster','system'])assert(main.includes('lion-left://'+tab));
});
test('tab changes update bounds only, without reloading SaaS',()=>{
 const m=main.match(/selectRightTab=name=>\{([\s\S]*?)\};/);
 const n=main.match(/selectLeftTab=name=>\{([\s\S]*?)\};/);
 assert(m&&n);
 for(const text of [m[1],n[1]])assert(!/reload\(|loadURL\(|close\(/.test(text));
 assert(main.includes('activeLeftTab=name;layout();updateTitle()'));
 assert(main.includes('activeRightTab=name;layout();updateTitle()'));
});
test('strict local URLs and preload IPC sender binding exist',()=>{
 assert(main.includes("event.sender!==local.webContents"));
 assert(main.includes("event.sender===cluster.webContents"));
 assert(main.includes("event.sender===system.webContents"));
 assert(main.includes("throw Error('LOCAL_SENDER_NOT_ADMITTED')"));
 assert(main.includes("throw Error('OBSERVATION_SENDER_NOT_ADMITTED')"));
 assert(main.includes('preload:path.join(__dirname,\'local-preload.cjs\')'));
 assert(main.includes('preload:path.join(__dirname,\'observer-preload.cjs\')'));
 assert(main.includes('u.href.split(\'#\')[0]===localURL'));
});
test('renderer source pins enforce identical LF bytes on Git Windows and Linux',()=>{
 const attrs=fs.readFileSync(path.join(__dirname,'..','.gitattributes'),'utf8');
 assert.match(attrs,/^\*\.cjs text eol=lf$/m);
 assert.match(attrs,/^\*\.html text eol=lf$/m);
 assert(!attrs.includes('Start-LION-Browser-ISE.ps1'));
});
test('both local file pages are SHA pinned and script-syntax valid',()=>{
 assert(main.includes("overviewSha256='"+digest(overview)+"'"));
 assert(main.includes("localSha256='"+digest(local)+"'"));
 for(const page of [overview,local]){
  const js=page.match(/<script>\s*([\s\S]*?)<\/script>\s*<\/body>/);
  assert(js,'inline local renderer script');
  new vm.Script(js[1]);
  assert(!page.includes('innerHTML'));
  assert(page.includes("default-src 'none'"));
 }
});
test('cluster refreshes read-only owner data, repo HEADs remain labelled snapshot',()=>{
 assert(overview.includes('window.lionObserver.snapshot()'));
 assert(overview.includes('STORED_GITHUB_HEADS_NOT_LIVE')||overview.includes('Repozytoria wymagają ponownego GitHub-currentness'));
 assert(!overview.includes('fetch('));
 assert(overview.includes('lion-refresh'));
});
test('cluster renders carrier digest, freshness and individual material workers without authority',()=>{
 const html=fs.readFileSync(path.join(__dirname,'..','observability-preview','LION_Cluster_System_Tabs_Preview.html'),'utf8');
 for(const phrase of ['observedFleet.carrier_digest_verified','observedFleet.currentness','observedFleet.observed_runtime_state',
  'w=>w.worker_id||w.name','w=>w.container_state||w.state','NIEPOTWIERDZONE'])
  assert(html.includes(phrase),phrase);
 assert(!html.includes('docker stop')&&!html.includes('innerHTML'));
});
test('Local GPT has operator-initiated send and provenance, never tools or autostart',()=>{
 assert(local.includes("window.lionLocal.send(prompt,past)"));
 assert(local.includes('mission_binding'));
 assert(local.includes('NOT_BOUND'));
 assert(main.includes("canonicalConsumer.stop('RECOVERY_OPERATOR_RESUME_REQUIRED')"));
 assert(!main.includes("canonicalConsumer.resume('R24_COMPLEMENTARY_CANONICAL_SAAS')"));
 assert(local.includes('maks. 8000'));
});
test('expanded menu implements actual navigation and guarded SaaS relay',()=>{
 for(const group of ['Control Plane','Intelligence','Diagnostyka','Federacja','Pomoc'])
  assert(main.includes("label:'"+group+"'"));
 assert(main.includes("snapshot.unresolved_count||snapshot.upstream_pending!==0"));
 assert(main.includes("canonicalConsumer?.resume('LOCAL_OPERATOR_MENU_EXACT_BOUNDED')"));
 assert(main.includes('selectLeftTab(\'cluster\')'));
 assert(main.includes('selectRightTab(\'local\')'));
});
