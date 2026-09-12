// Isolated rendering fixtures: these never enter the application or runtime DB.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',textContent:'',value:'',hidden:false,
    querySelectorAll:()=>[],scrollHeight:0,scrollTop:0,clientHeight:0});
  return nodes.get(id);
};
const source = fs.readFileSync(path.join(__dirname,'../mission_control/static/app.js'),'utf8');
const context = vm.createContext({document:{getElementById:node},navigator:{},
  AbortSignal,Date,console,setInterval:()=>{},fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../mission_control/static/passive.js'),'utf8'),context);
vm.runInContext(source,context);
const run = code => vm.runInContext(code,context);
async function main() {
  run(`latestObservations={generic:{source_reason:'K3S_NOT_RUNNING'}};latestRunFleets={generic:{currentness:'OBSERVED',organizations:{LION:{total:2,active:1,idle:1}}}};renderRunObservations({run_id:'generic',adapter_type:'LPCL_EVENT_STREAM'},[{event_type:'CHANNEL_MESSAGE',payload:{from_pod_uid:'pod-a',to_pod_uid:'pod-b'}}])`);
  assert.equal(node('vktDetail').hidden,false);
  assert.match(node('channelFeed').innerHTML,/pod-a/);
  assert.match(node('channelFeed').innerHTML,/pod-b/);
  assert.match(node('channelContext').textContent,/K3S_NOT_RUNNING/);
  assert.match(node('fleetOrganizations').innerHTML,/2/);
  run('latestObservations={};latestRunFleets={};');

  run(`renderFleet({}, {metrics:{fleet_organizations:{LION:18,SPECTRA:24,TIGER:41}}})`);
  assert.match(node('fleetOrganizations').innerHTML,/18 recorded pods/);
  assert.match(node('fleetOrganizations').innerHTML,/active UNKNOWN/);
  assert.doesNotMatch(node('fleetOrganizations').innerHTML,/active 0/);
  run(`renderFleet({currentness:'OBSERVED',organizations:{LION:{total:2,active:null,idle:null}}})`);
  assert.match(node('fleetOrganizations').innerHTML,/active UNKNOWN/);
  assert.match(run(`badge('RECORDED · PASS','PASS')`),/tone-good/);
  run(`renderChannels('r',[])`);
  assert.match(node('channelFeed').innerHTML,/No recorded CHANNEL_MESSAGE/);
  run(`renderChannels('r',[{event_type:'CHANNEL_MESSAGE',payload:{from_fleet:'LION',to_fleet:'TIGER',message_id:'m1'}}])`);
  assert.match(node('channelContext').textContent,/1 recorded messages/);
  assert.match(node('channelFeed').innerHTML,/m1/);
  run(`selectedChannel='SPECTRA → TIGER';renderChannels('r',[{event_type:'CHANNEL_MESSAGE',payload:{from_fleet:'LION',to_fleet:'TIGER'}}])`);
  assert.equal(run('selectedChannel'),'ALL');

  run('renderSummary({recorded_active_runs:1,observed_active_runs:0})');
  assert.match(node('summary').innerHTML,/Recorded active runs.*>1</);
  assert.match(node('summary').innerHTML,/Observed active runs.*>0</);
  run('renderSummary({active_runs:2})');
  assert.match(node('summary').innerHTML,/Recorded active runs.*>2</);
  assert.match(node('summary').innerHTML,/Observed active runs.*>UNKNOWN</);
  assert.match(node('summary').innerHTML,/Deferred runs/);
  assert.match(node('summary').innerHTML,/Workloads/);
  assert.match(node('summary').innerHTML,/Artifacts/);
  assert.match(node('summary').innerHTML,/UNKNOWN/);
  assert.doesNotMatch(node('summary').innerHTML,/Working drones|Fleet total|Organizations/);
  run(`receipts([{receipt_id:'r',status:'PASS'}],'run')`);
  assert.match(node('receipts').innerHTML,/RECEIPT_PRESENT/);
  assert.match(node('receipts').innerHTML,/<td>UNKNOWN<\/td>/);
  assert.doesNotMatch(node('receipts').innerHTML,/VERIFIED|COMPLETE/);
  run(`participants({a:{state:'RUNNING',logical_id:'a'}},{host:'h'})`);
  assert.match(node('participants').innerHTML,/NONE OBSERVED/);
  assert.match(node('participants').innerHTML,/LOGICAL ONLY/);
  // Verify exact text encoding, not a partial blacklist of HTML tag spellings.
  const artifactTextCases = [
    ['<img src=x>', '&lt;img src=x&gt;'],
    ['<IMG src=x>', '&lt;IMG src=x&gt;'],
    ['<ImG src=x>', '&lt;ImG src=x&gt;'],
    ['<script>sample</script>', '&lt;script&gt;sample&lt;/script&gt;'],
    ['<SCRIPT>sample</SCRIPT>', '&lt;SCRIPT&gt;sample&lt;/SCRIPT&gt;'],
    ['<ScRiPt>sample</ScRiPt>', '&lt;ScRiPt&gt;sample&lt;/ScRiPt&gt;'],
    ['&<>\'"', '&amp;&lt;&gt;&#39;&quot;'],
  ];
  for (const [input, encoded] of artifactTextCases) {
    context.artifactFixture = [{artifact_id:input,path:input}];
    run("artifacts(artifactFixture,'r')");
    const html = node('artifacts').innerHTML;
    assert.equal(html.split(`<td>${encoded}</td>`).length - 1, 2,
      'artifact ID and path must both preserve the fully escaped text');
    assert.equal(html.includes(input), false, 'raw fixture must not enter HTML');
  }
  delete context.artifactFixture;
  run(`allRuns=[{run_id:'r',adapter_type:'VKT_R3',process_class:'A',status:'PASS'}];$('processClass').value='B';renderRuns()`);
  assert.match(node('runs').innerHTML,/No runs match/);
  run(`$('processClass').value='A';renderRuns()`);
  assert.match(node('runs').innerHTML,/data-id="r"/);
  assert.notEqual(run("tone('UNKNOWN')"),run("tone('PASS')"));
  assert.notEqual(run("tone('CLEANED')"),run("tone('VERIFIED')"));
  assert.equal(run('stamp(null)'),'UNKNOWN');
  assert.equal(run('stamp(0)'),'1970-01-01T00:00:00.000Z');
  run(`allRuns=[{run_id:'history',adapter_type:'VKT_R3',status:'PASS',workload:{pods:384},evidence:{class:'HISTORICAL_IMPORTED_EVIDENCE'},participants:{PHASE_A:128}}];latestFleet={};renderCluster(true)`);
  assert.match(node('clusterState').textContent,/HISTORICAL/);
  assert.equal((node('clusterMap').innerHTML.match(/class="drone-cell cell-unknown"/g)||[]).length,385); // 384 + legend
  assert.match(node('clusterMap').innerHTML,/128 participants \(aggregate\)/);
  assert.doesNotMatch(node('clusterMap').innerHTML,/pod_uid|drone_id/);
  run(`allRuns=[{run_id:'live',adapter_type:'VKT_R3',status:'RUNNING',host:'<img src=x>',namespace:'vkt-r3',participants:{}}];latestFleet={currentness:'OBSERVED',run_ids:['live'],fleet_total:3,organizations:{A:{total:3,active:2}}};renderCluster(true)`);
  assert.match(node('clusterState').textContent,/OBSERVED/);
  assert.match(node('clusterMap').innerHTML,/2 fresh heartbeats/);
  assert.equal((node('clusterMap').innerHTML.match(/class="drone-cell cell-fresh"/g)||[]).length,3); // 2 + legend
  assert.doesNotMatch(node('clusterMap').innerHTML,/<img/);
  run(`latestFleet.pod_observations=[{run_id:'live',pods:[{uid:'uid-1',name:'<script>bad</script>',fleet:'A',ready:true,phase:'Running'}]}];renderCluster(true)`);
  assert.match(node('clusterMap').innerHTML,/pod-ready/);
  assert.match(node('clusterMap').innerHTML,/data-pod="uid-1"/);
  assert.ok(node('clusterMap').innerHTML.includes('&lt;script&gt;bad&lt;/script&gt;'));
  const podButton={dataset:{pod:'uid-1'}};
  node('clusterMap').querySelectorAll=()=>[podButton];
  run('renderCluster(true)');
  podButton.onclick();
  assert.equal(node('clusterPodDetail').hidden,false);
  assert.match(node('clusterPodDetail').textContent,/uid-1/);
  run('renderCluster(true)');
  assert.equal(node('clusterPodDetail').hidden,false);
  node('clusterMap').querySelectorAll=()=>[];
  run('renderCluster(false)');
  assert.match(node('clusterState').textContent,/OFFLINE/);
  assert.doesNotMatch(node('clusterMap').innerHTML,/pod-ready/);
  assert.equal((node('clusterMap').innerHTML.match(/class="drone-cell cell-fresh"/g)||[]).length,1); // legend only
  run(`latestFleet.run_ids=['other'];renderCluster(true)`);
  assert.match(node('clusterState').textContent,/UNKNOWN/);
  run(`allRuns[0].workload={pods:10000000};renderCluster(true)`);
  assert.equal((node('clusterMap').innerHTML.match(/class="drone-cell cell-unknown"/g)||[]).length,513);
  run(`allRuns[0].workload={pods:-1};renderCluster(true)`);
  assert.match(node('clusterMap').innerHTML,/No valid count/);
  run(`allRuns=[];renderCluster(true)`);
  assert.match(node('clusterState').textContent,/No fleet evidence/);
  assert.equal(node('clusterDetails').hidden,true);
  // An old request cannot replace a newer selection, even when it finishes last.
  const pending=[];
  context.fetch=url=>new Promise(resolve=>pending.push({url,resolve}));
  const old=run("detail('old')"),fresh=run("detail('new')");
  function answer(item){const id=item.url.split('/')[3];return {ok:true,run:{run_id:id,adapter_type:'OSS_REPOSITORY_TEST',status:'PASS',verification_status:'OBSERVED'},events:[],metrics:{},participants:{},artifacts:[],receipts:[]};}
  pending.slice(6).forEach(p=>p.resolve({ok:true,json:async()=>answer(p)}));
  await fresh;
  pending.slice(0,6).forEach(p=>p.resolve({ok:true,json:async()=>answer(p)}));
  await old;
  assert.match(node('identity').innerHTML,/>new</);
  assert.doesNotMatch(node('identity').innerHTML,/>old</);
  run("latestObservations={new:{observation_status:'POLL_STALE',heartbeat_status:'UNKNOWN'}}");
  context.fetch=async()=>({ok:true,json:async()=>({run:{run_id:'new',status:'RUNNING',metrics:{drone_pods:[{uid:'large-pod-array'}],ready:1}},metrics:{},events:[],participants:{},artifacts:[],receipts:[]})});
  await run("detail('new')");
  assert.match(node('identity').innerHTML,/recorded_status/);
  assert.match(node('identity').innerHTML,/POLL_STALE/);
  assert.doesNotMatch(node('metrics').innerHTML,/large-pod-array|drone_pods/);
  assert.match(node('metrics').innerHTML,/ready/);
  context.fetch=async()=>({ok:false,status:404});
  await run("detail('gone')");
  assert.equal(node('detail').hidden,true);
  assert.match(node('detailState').textContent,/UNKNOWN/);
  run('refreshInFlight=false');
  await run('refresh()');
  assert.equal(node('health').textContent,'OFFLINE');
  assert.equal(run('Object.keys(latestObservations).length'),0);
  assert.equal(node('detail').hidden,true);
  console.log('PASS: global cards, unknowns, evidence separation, logical identities, escaping, filters, selection race, failure state');
}
main().catch(e=>{console.error(e);process.exitCode=1});
