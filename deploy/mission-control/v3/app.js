/* Reconcile observed markup in place. User-owned disclosure/input state is retained. */
const lionMarkupCache=new WeakMap();
function lionNodeKey(node){
  if(node.nodeType!==1)return null;
  for(const key of ['id','data-key','data-mid','data-run','data-pod','data-mc-action','data-low-action','data-proto','data-p','data-channel','data-open','data-start-component','data-restart'])if(node.hasAttribute(key))return node.tagName+':'+key+':'+node.getAttribute(key);
  return null;
}
function patchHtml(root,markup){
  if(!root)return;markup=String(markup??'');if(lionMarkupCache.get(root)===markup)return;
  const fragment=document.createElement('template');fragment.innerHTML=markup;
  function reconcile(parent,desired){
    const old=Array.from(parent.childNodes),keyed=new Map(old.map(n=>[lionNodeKey(n),n]).filter(([k])=>k));const used=new Set();
    for(let i=0;i<desired.length;i++){
      const next=desired[i],key=lionNodeKey(next);let node=key?keyed.get(key):old[i];
      if(node&&(used.has(node)||node.nodeType!==next.nodeType||node.nodeName!==next.nodeName||(!key&&lionNodeKey(node))))node=null;
      if(!node){node=next.cloneNode(true);parent.insertBefore(node,parent.childNodes[i]||null)}
      else{
        if(node!==parent.childNodes[i])parent.insertBefore(node,parent.childNodes[i]||null);
        if(node.nodeType===3){if(node.data!==next.data)node.data=next.data}
        else if(node.nodeType===1){
          for(const attr of Array.from(node.attributes))if(!(node.tagName==='DETAILS'&&attr.name==='open')&&!next.hasAttribute(attr.name))node.removeAttribute(attr.name);
          for(const attr of Array.from(next.attributes))if(!(node.tagName==='DETAILS'&&attr.name==='open')&&node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
          if(!['INPUT','TEXTAREA','SELECT'].includes(node.tagName)||document.activeElement!==node)reconcile(node,Array.from(next.childNodes));
        }
      }
      used.add(node);
    }
    for(const node of old)if(!used.has(node)&&node.parentNode===parent)node.remove();
  }
  const positions=[root,...root.querySelectorAll('*')].filter(n=>n.scrollTop||n.scrollLeft).map(n=>[n,n.scrollTop,n.scrollLeft]);
  reconcile(root,Array.from(fragment.content.childNodes));
  for(const [node,top,left] of positions)if(node.isConnected){node.scrollTop=top;node.scrollLeft=left}
  lionMarkupCache.set(root,markup);
}
function boundedRows(value){return Array.isArray(value)?value.slice(0,300):[]}
function missingRecord(raw){return String(raw?.normalized_runtime?.record_class||raw?.schema_context?.record_class||'').startsWith('HISTORICAL')?'HISTORICAL_NOT_RECORDED':'NOT_RECORDED'}
function viewValue(value,raw){return value===null||value===undefined||value===''?missingRecord(raw):typeof value==='object'?JSON.stringify(value):String(value)}
function semanticDetail(key,title,fields,raw,escape){
  return `<article class="semantic-card" data-key="${escape(key)}"><h3>${escape(title)}</h3><dl>${fields.map(([name,value])=>`<dt>${escape(name)}</dt><dd>${escape(viewValue(value,raw))}</dd>`).join('')}</dl><details class="semantic-raw" data-key="raw"><summary>RAW · source record</summary><pre>${escape(JSON.stringify(raw??{},null,2).slice(0,40000))}</pre></details></article>`;
}
function phaseCard(phase,mission,escape){
  const fields=[['State',phase.status??phase.state],['Progress',phase.progress===null||phase.progress===undefined?null:phase.progress+'%'],['Handler',phase.handler_id],['Handler version',phase.handler_version],['Blocker',phase.blocker],['Evidence count',phase.evidence_count],['Detail',phase.detail],['Control',Object.entries(phase.capabilities||{}).filter(([a,c])=>['PAUSE','STOP'].includes(a)&&c.supported===true).map(([a])=>a).join(' / ')||phase.control_unavailable_reason||phase.capabilities?.PAUSE?.reason||'INSPECTION_ONLY · no phase mutation capability supplied']];
  const controls=['PAUSE','STOP'].filter(action=>phase.capabilities?.[action]?.supported===true&&typeof phase.capabilities[action].control_token==='string').map(action=>`<button type="button" data-key="${action}" data-phase-action="${action}" data-phase-id="${escape(phase.phase_id)}" data-control-token="${escape(phase.capabilities[action].control_token)}">${action} current phase driver</button>`).join('');
  return semanticDetail(phase.phase_id||phase.id,phase.title||phase.phase_id,fields,{...phase,schema_context:mission.schema_context},escape).replace('</article>',`<div class="phase-actions">${controls}</div></article>`);
}
function workerCards(mission,escape){
  const workers=boundedRows(mission.normalized_runtime?.fleet?.material_workers??mission.workers).map(worker=>{
    const match=row=>(worker.material_drone_id&&row.material_drone_id===worker.material_drone_id)||(worker.pod_uid&&row.pod_uid===worker.pod_uid);
    return {...worker,assignment_history:worker.assignment_history??(Array.isArray(mission.execution_assignments)?mission.execution_assignments.filter(match):null),receipt_history:worker.receipt_history??(Array.isArray(mission.execution_receipts)?mission.execution_receipts.filter(match):null)};
  });
  return workers.map((w,i)=>semanticDetail(w.pod_uid||w.uid||w.worker_id||w.pod_name||i,w.pod_name||w.name||w.worker_id||'Material worker',[
    ['Identity',w.pod_uid??w.uid??w.worker_id],['Logical assignment',w.logical_id??w.assignment],['Runtime',w.runtime??w.process_id??w.pid],['State',w.phase??w.state],['Ready',w.ready],['Restarts',w.restarts],['Host / node',w.node_name??w.node??w.host],['Image',w.image],['Assignment history',w.assignment_history],['Receipt history',w.receipt_history],['History window','Latest 100 mission assignments / receipts; exact material_drone_id or pod_uid match'],['Control',w.capabilities?.RESTART?.reason||'INSPECTION_ONLY · no worker restart capability supplied']
  ],{...w,schema_context:mission.schema_context},escape)).join('')||'<p class="status">No material worker records supplied.</p>';
}

const $=id=>document.getElementById(id);
let allRuns=[];
let selectedRunId=null;
let selectedChannel='ALL';
let channelEvents=[];
let refreshInFlight=false;
let detailGeneration=0;
const pretty=v=>JSON.stringify(v??{},null,2);
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const targetText=r=>r?.target?.repository||r?.target?.kind||'';
async function get(path){const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(8000)});if(!r.ok)throw new Error('HTTP '+r.status);return await r.json()}
function card(k,v,sub=''){return `<div class="card" data-key="${esc(k)}"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div>${sub?`<div class="mini">${esc(sub)}</div>`:''}</div>`}
function tone(v){const x=String(v??'').toUpperCase();if(['PASS','VERIFIED','COMPLETE','READY'].includes(x))return 'tone-good';if(['RUNNING','STARTING','CLEANING','OBSERVED','PARTIAL','CORROBORATED','AUTHORIZED','WAITING','BLOCKED'].includes(x))return 'tone-live';if(['FAIL','FAILED','ERROR','CONTRADICTED'].includes(x))return 'tone-bad';if(['DEFER','UNKNOWN','DEGRADED','SUPERSEDED'].includes(x))return 'tone-warn';return ''}
function flatten(value,prefix='',depth=0){if(value===null||value===undefined)return [[prefix||'value','UNKNOWN']];if(Array.isArray(value))return [[prefix||'value',value.length?JSON.stringify(value):'[]']];if(typeof value!=='object')return [[prefix||'value',value]];const entries=Object.entries(value);if(!entries.length)return [[prefix||'value','{}']];let out=[];for(const [k,v] of entries){const key=prefix?`${prefix}.${k}`:k;if(v&&typeof v==='object'&&!Array.isArray(v)&&depth<1)out=out.concat(flatten(v,key,depth+1));else out.push([key,v===null?'UNKNOWN':typeof v==='object'?JSON.stringify(v):v])}return out}
function renderChips(id,obj){const root=$(id);const pairs=flatten(obj);patchHtml(root,pairs.map(([k,v])=>`<button type="button" class="data-chip ${tone(v)}" data-key="${esc(k)}" data-copy="${esc(v)}" title="Click to copy"><span>${esc(k)}</span><b>${esc(v)}</b></button>`).join(''));root.querySelectorAll('.data-chip').forEach(b=>b.onclick=()=>navigator.clipboard?.writeText(b.dataset.copy||''))}
function renderFleet(fleet,recordedRun=null){
  const current=fleet.currentness==='OBSERVED';
  let orgs=fleet.organizations||{};
  if(!current && recordedRun){
    const counts=recordedRun.metrics?.fleet_organizations||{};
    orgs=Object.fromEntries(Object.entries(counts).map(([name,total])=>[name,{total,active:null,idle:null}]));
    if(!Object.keys(orgs).length){for(const pod of recordedRun.metrics?.drone_pods||[]){if(!pod.fleet)continue;orgs[pod.fleet]??={total:0,active:null,idle:null};orgs[pod.fleet].total++}}
  }
  $('workingDrones').textContent=current?(fleet.working_drones??'UNKNOWN'):'UNKNOWN';
  $('fleetCurrentness').textContent=current?'Latest observed fleet organization; activity requires heartbeat evidence.':'Recorded fleet membership only. Current activity and topology are UNKNOWN.';
  const rows=Object.entries(orgs);
  patchHtml($('fleetOrganizations'),rows.length?rows.map(([name,v])=>{
    const total=countValue(v.total),active=current?countValue(v.active):null,idle=current?countValue(v.idle):null;
    const pct=total>0&&active!==null?Math.min(100,Math.round(active*100/total)):null;
    return `<article class="org-card"><div class="org-title"><b>${esc(name)}</b><span>${total??'UNKNOWN'} ${current?'observed':'recorded'} pods</span></div>${pct===null?'':`<div class="org-bar"><i style="width:${pct}%"></i></div>`}<div class="org-meta"><span>active ${active??'UNKNOWN'}</span><span>idle ${idle??'UNKNOWN'}</span></div></article>`;
  }).join(''):'<div class="empty-state">No organization evidence for this run. No groups have been invented.</div>');
}
function channelKey(p){return `${p?.from_fleet||'UNKNOWN'} → ${p?.to_fleet||'UNKNOWN'}`}
function renderChannels(runId,events){channelEvents=(events||[]).filter(e=>e.event_type==='CHANNEL_MESSAGE');const counts={};for(const e of channelEvents){const key=channelKey(e.payload||{});counts[key]=(counts[key]||0)+1}const keys=Object.keys(counts).sort();if(selectedChannel!=='ALL'&&!counts[selectedChannel])selectedChannel='ALL';$('channelContext').textContent=runId?`${runId} · ${channelEvents.length} recorded messages · ${keys.length} recorded channels`:'No active channel source.';patchHtml($('channelFilters'),(keys.length?`<button class="channel-btn ${selectedChannel==='ALL'?'active':''}" data-channel="ALL">ALL <b>${channelEvents.length}</b></button>`:'')+keys.map(k=>`<button class="channel-btn ${selectedChannel===k?'active':''}" data-channel="${esc(k)}">${esc(k)} <b>${counts[k]}</b></button>`).join(''));$('channelFilters').querySelectorAll('.channel-btn').forEach(b=>b.onclick=()=>{selectedChannel=b.dataset.channel;renderChannels(runId,channelEvents)});const feed=$('channelFeed');const stick=feed.scrollHeight-feed.scrollTop-feed.clientHeight<80||feed.scrollHeight===0;const shown=channelEvents.filter(e=>selectedChannel==='ALL'||channelKey(e.payload||{})===selectedChannel).slice(-300);patchHtml(feed,shown.length?shown.map(e=>{const p=e.payload||{};const ts=e.timestamp?new Date(e.timestamp*1000).toLocaleTimeString():'';return `<article class="message"><div class="message-top"><span class="message-route">${esc(p.from_fleet||'?')} / ${esc(p.from_drone_id||'?')} → ${esc(p.to_fleet||'?')}</span><time>${esc(ts)}</time></div><div class="message-tags"><span>${esc(p.phase||e.phase||'')}</span><span>${esc(p.type||'MESSAGE')}</span><span>${esc(p.case_id||'')}</span></div><div class="message-id">${esc(p.message_id||e.event_id||'')}</div></article>`}).join(''):'<div class="empty-state">No recorded CHANNEL_MESSAGE events for this run. Live drone communication is not established.</div>');if(stick)feed.scrollTop=feed.scrollHeight}

let latestFleet={};
let latestObservations={};
const known=v=>v===null||v===undefined||v===''?'UNKNOWN':typeof v==='object'?JSON.stringify(v):String(v);
const stamp=v=>v===null||v===undefined?'UNKNOWN':Number.isFinite(Number(v))?new Date(Number(v)*1000).toISOString():String(v);
const badge=(v,status=v)=>`<span class="state ${tone(status)}">${esc(known(v))}</span>`;
function renderSummary(x){x={...x,recorded_active_runs:x.recorded_active_runs??x.active_runs};patchHtml($('summary'),[['Recorded active runs','recorded_active_runs'],['Observed active runs','observed_active_runs'],['Completed runs','completed_runs'],['Superseded runs','superseded_runs'],['Failed runs','failed_runs'],['Deferred runs','deferred_runs'],['Hosts','hosts'],['Workloads','workloads'],['Events','events'],['Artifacts','artifacts']].map(([label,key])=>card(label,x[key]??'UNKNOWN')).join(''))}
function table(id,columns,rows){
  if(['events','phases','recentEvents'].includes(id)){
    patchHtml($(id),rows.map((row,i)=>semanticDetail(row.key||row[2]+'-'+row[0]+'-'+i,row[1]||'Recorded event',columns.map((column,j)=>[column,row[j]]),row.record||row,esc)).join('')||'<p class="empty-state">No recorded events.</p>');return;
  }
  patchHtml($(id),rows.length?`<div class="table-wrap"><table><thead><tr>${columns.map(c=>`<th scope="col">${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map((row,i)=>`<tr data-key="${esc(row[0]??i)}">${row.map(v=>`<td>${esc(known(v))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:'<p class="empty-state">No recorded evidence.</p>');
}

function rebuildFilters(){for(const [id,key,label] of [['adapter','adapter_type','adapters'],['status','status','statuses'],['processClass','process_class','process classes']]){const root=$(id),cur=root.value;const values=[...new Set(allRuns.map(r=>r[key]).filter(Boolean))].sort();if(cur&&!values.includes(cur))values.push(cur);const html=`<option value="">All ${label}</option>`+values.map(x=>`<option>${esc(x)}</option>`).join('');if(root.innerHTML!==html){patchHtml(root,html);root.value=cur}}}
function renderRuns(){const a=$('adapter').value,s=$('status').value,c=$('processClass').value;const rows=allRuns.filter(r=>(!a||r.adapter_type===a)&&(!s||r.status===s)&&(!c||r.process_class===c));patchHtml($('runs'),rows.length?rows.map(r=>`<tr data-run="${encodeURIComponent(r.run_id)}" class="${r.run_id===selectedRunId?'selected':''}"><td data-label="Recorded status">${badge('RECORDED · '+r.status,r.status)}</td><td data-label="Run ID"><button class="run-select" data-id="${encodeURIComponent(r.run_id)}">${esc(r.run_id)}</button></td><td data-label="Process class">${esc(known(r.process_class))}</td><td data-label="Adapter">${esc(known(r.adapter_type))}</td><td data-label="Host">${esc(known(r.host))}</td><td data-label="Runtime">${esc(known(r.runtime))}</td><td data-label="Target">${esc(targetText(r))}</td><td data-label="Phase">${esc(known(r.phase))}</td><td data-label="Started">${esc(stamp(r.started_at))}</td><td data-label="Duration">${esc(r.duration==null?'UNKNOWN':Number(r.duration).toFixed(1)+' s')}</td></tr>`).join(''):'<tr><td colspan="10" class="empty-state">No runs match these filters. Recorded history is retained.</td></tr>');$('runs').querySelectorAll('.run-select').forEach(b=>b.onclick=()=>detail(decodeURIComponent(b.dataset.id)))}
function eventRows(events){return [...events].sort((a,b)=>(a.timestamp??Infinity)-(b.timestamp??Infinity)||String(a.event_id).localeCompare(String(b.event_id))).map(e=>Object.assign([stamp(e.timestamp),e.event_type,e.run_id,e.phase,e.source||e.adapter_type||e.host,e.payload],{key:e.event_id,record:e}))}
function participants(value,run){table('participants',['Participant ID','Role','Fleet','Logical identity','Material identity','Host','Runtime','State','Observation state'],Object.entries(value||{}).map(([id,p])=>{p=p&&typeof p==='object'?p:{state:p};return [p.participant_id??id,p.role,p.fleet,p.logical_identity??p.logical_id??p.drone_id??id,p.material_identity??p.pod_uid??p.uid??'NONE OBSERVED',p.host??run.host,p.runtime??run.runtime,(p.material_identity??p.pod_uid??p.uid)?(p.state??p.status):'LOGICAL ONLY · '+known(p.state??p.status),p.observation_state??p.verification_status]}))}
function artifacts(value,id){table('artifacts',['Artifact ID','Type','Run ID','Origin','Path / reference','Digest','Created at','Verification state'],(value||[]).map(a=>[a.artifact_id,a.type??a.artifact_type,a.run_id??id,a.origin??a.evidence_class,a.path??a.reference,a.sha256??a.digest,stamp(a.created_at??a.timestamp),a.verification_state??a.verification_status]))}
function receipts(value,id){table('receipts',['Receipt ID','Run ID','Presence','Operation','Reported status','Effect observed','Reconciliation complete','Path / reference','Digest','Created at'],(value||[]).map(r=>[r.receipt_id,r.run_id??id,'RECEIPT_PRESENT',r.operation,r.status,r.effect_observed,r.reconciliation_complete,r.path??r.reference,r.sha256??r.digest,stamp(r.created_at??r.timestamp)]))}
async function detail(id,silent=false){const generation=++detailGeneration;if(selectedRunId!==id)selectedChannel='ALL';selectedRunId=id;if(!silent){$('detail').hidden=true;$('empty').hidden=true;$('detailState').textContent='Loading selected run…';renderRuns();$('runDetail').scrollIntoView?.({behavior:'smooth',block:'start'})}try{const [r,e,m,p,a,rc]=await Promise.all(['','/events','/metrics','/participants','/artifacts','/receipts'].map(s=>get('/api/runs/'+encodeURIComponent(id)+s)));if(generation!==detailGeneration||selectedRunId!==id)return;const run=r.run;if(!run)throw new Error('Run unavailable');patchHtml($('runSchema'),semanticDetail('run-schema','Run schema',[['Schema version',run.normalized_schema_version??run.schema_version],['Projection revision',run.projection_revision],['Record class',run.normalized_runtime?.record_class??run.schema_context?.record_class],['Legacy gaps',run.normalized_runtime?.gaps??run.schema_context?.missing_fields]],run,esc));$('empty').hidden=true;$('detail').hidden=false;$('detailState').textContent='Recorded run evidence · '+id;renderChips('identity',{run_id:run.run_id,process_language:run.process_language,process_class:run.process_class,adapter_type:run.adapter_type,recorded_status:run.status,observation_status:latestObservations[run.run_id]?.observation_status,heartbeat_status:latestObservations[run.run_id]?.heartbeat_status,phase:run.phase,host:run.host,runtime:run.runtime,namespace:run.namespace});renderChips('source',run.source);renderChips('target',run.target);renderChips('authority',run.authority);renderChips('timeline',{started_at:stamp(run.started_at),finished_at:stamp(run.finished_at),duration_seconds:run.duration??'UNKNOWN'});table('events',['Timestamp','Type','Run ID','Phase','Source','Payload'],eventRows(e.events||[]));table('phases',['Timestamp','Type','Run ID','Phase','Source','Payload'],eventRows((e.events||[]).filter(x=>['PHASE_STARTED','PHASE_COMPLETED'].includes(x.event_type))));$('adapterTitle').textContent=run.adapter_type==='VKT_R3'?'Vulnerability Knowledge Test':run.adapter_type==='OSS_REPOSITORY_TEST'?'OSS repository test':known(run.adapter_type);const metricValues={...(run.metrics||{}),...(m.metrics||{})};delete metricValues.drone_pods;renderChips('metrics',metricValues);participants({...run.participants,...p.participants},run);artifacts(a.artifacts,id);receipts(rc.receipts,id);renderChips('cleanup',run.cleanup);renderChips('verification',{verification_status:run.verification_status,evidence:run.evidence});renderPassiveEvidence(run,e.events||[]);$('vktDetail').hidden=run.adapter_type!=='VKT_R3';if(run.adapter_type==='VKT_R3'){renderChannels(id,e.events||[]);renderFleet((latestFleet.run_ids||[]).length===1&&latestFleet.run_ids[0]===id?latestFleet:{},run)}}catch(error){if(generation!==detailGeneration)return;$('detail').hidden=true;$('detailState').textContent='UNKNOWN — selected run could not be refreshed. '+error.message}}
function environment(summary,adapters){patchHtml($('adapters'),boundedRows(adapters.adapters).map(a=>semanticDetail(a.adapter_id,a.adapter_id,[['Supported process classes',a.supported_process_classes],['Control authority',a.control_authority],['State',a.status??a.state]],a,esc)).join('')||'<p>No registered adapters reported.</p>');
  const hosts=[...new Set(allRuns.map(r=>r.host).filter(Boolean))];
  patchHtml($('hosts'),hosts.map(host=>{const runs=allRuns.filter(r=>r.host===host);return semanticDetail(host,host,[['Evidence','RECORDED_RUN_MEMBERSHIP'],['Runtimes',[...new Set(runs.map(r=>r.runtime).filter(Boolean))]],['Recorded runs',runs.length]],{host,runs:runs.map(r=>({run_id:r.run_id,runtime:r.runtime,status:r.status,started_at:r.started_at}))},esc)}).join('')||'<p>NOT_RECORDED · no host observation supplied.</p>');
  $('currentness').textContent='API read at '+new Date().toISOString()+'. Runtime currentness: '+(summary.fleet?.currentness??'UNKNOWN')+'. '+(summary.observation?('Reason: '+summary.observation.reason+'; poll age: '+known(summary.observation.age_seconds)+' s; last success: '+stamp(summary.observation.success_at)):(summary.error||'API availability does not establish readiness.'));const rd=summary.readiness||{};$('readiness').textContent='Readiness: '+(rd.status||'UNKNOWN')+(rd.focus_mission_id?' · focus '+rd.focus_mission_id:'')+(Number.isFinite(Number(rd.ready))&&Number.isFinite(Number(rd.target))?' · '+rd.ready+'/'+rd.target+' ready':'');if(summary.observation?.adapters){const reasons=Object.entries(summary.observation.adapters).filter(([,v])=>v.empty_reason).map(([k,v])=>k+': '+v.empty_reason);if(reasons.length)$('currentness').textContent+='; '+reasons.join(' | ')}$('health').textContent=summary.ok?'API AVAILABLE':'DEGRADED';$('health').className='pill '+(summary.ok?'':'tone-warn')}

// Count visualization only: aggregate phase participants are not drone identities.
let clusterOnline=false;
let clusterSelectedPod=null;
let clusterSelectedPodRun=null;
const countValue=v=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0?v:null;
const fleetRun=r=>r.adapter_type==='VKT_R3'||r.workload?.kind==='KubernetesFleet'||r.metrics?.fleet_organizations;
function renderCluster(online=clusterOnline){
  clusterOnline=online;
  const candidates=allRuns.filter(fleetRun).sort((a,b)=>
    Number((latestFleet.run_ids||[]).includes(b.run_id))-Number((latestFleet.run_ids||[]).includes(a.run_id))||
    Number(['RUNNING','STARTING'].includes(b.status))-Number(['RUNNING','STARTING'].includes(a.status))||
    (b.started_at??b.finished_at??0)-(a.started_at??a.finished_at??0)||String(a.run_id).localeCompare(String(b.run_id)));
  const picker=$('clusterRun'),selected=picker.value;
  patchHtml(picker,'<option value="">Follow latest fleet</option>'+candidates.map(r=>`<option value="${esc(r.run_id)}">${esc(r.run_id)}</option>`).join(''));
  picker.value=selected;
  const run=selected?candidates.find(r=>r.run_id===selected):candidates[0];
  $('clusterPodDetail').hidden=true;
  $('clusterDetails').hidden=!run;
  if(!run){$('clusterState').textContent=online?'No fleet evidence recorded. Cluster state: UNKNOWN.':'OFFLINE · Cluster state: UNKNOWN.';patchHtml($('clusterMap'),'<div class="empty-state">Waiting for a fleet observation. No drones have been inferred.</div>');return}
  const historical=run.evidence?.class==='HISTORICAL_IMPORTED_EVIDENCE'||['CLEANED','CLEANING'].includes(run.status)||['STOPPED','CLEANED'].includes(run.cleanup?.status);
  // Use the fresh summary itself; never color persisted participant records as live.
  const current=online&&!historical&&latestFleet.currentness==='OBSERVED'&&latestFleet.run_ids?.length===1&&latestFleet.run_ids[0]===run.run_id;
  const metrics=run.metrics||{};
  const records=current?(latestFleet.pod_observations||[]).find(x=>x.run_id===run.run_id)?.pods:metrics.drone_pods;
  const pods=Array.isArray(records)?records.filter(p=>p&&typeof p.uid==='string'&&p.uid):[];
  const identitiesValid=new Set(pods.map(p=>p.uid)).size===pods.length;
  $('clusterPodDetail').hidden=true;
  const raw=current?latestFleet.organizations:(metrics.fleet_organizations||{});
  let groups=Object.entries(raw||{}).map(([name,v])=>({name,total:countValue(current?v.total:v),active:current?countValue(v.active):null}));
  const reportedTotal=countValue(current?latestFleet.fleet_total:(metrics.pods??run.workload?.pods));
  if(!groups.length)groups=[{name:'Fleet · organization breakdown unavailable',total:reportedTotal,active:null}];
  const mode=!online?'OFFLINE · cached evidence':current?'OBSERVED · latest fleet counts':historical?'HISTORICAL · completed or cleaned run':'RECORDED · runtime currentness UNKNOWN';
  $('clusterState').textContent=mode+' · '+run.run_id;
  $('clusterDetails').onclick=()=>{detail(run.run_id);$('runDetail').scrollIntoView?.({behavior:'smooth'})};
  let budget=512;
  const groupsHtml=groups.slice(0,64).map(g=>{
    const total=g.total,active=g.active!==null&&total!==null&&g.active<=total?g.active:null;
    const shown=total===null?0:Math.min(total,budget);budget-=shown;
    const members=identitiesValid?pods.filter(p=>p.fleet===g.name||(groups.length===1&&g.name.startsWith('Fleet ·'))):[];
    const identityMode=members.length>0;
    const dots=identityMode?members.slice(0,shown).map(p=>`<button type="button" class="pod-cell ${current?(p.phase==='Failed'?'pod-failed':p.ready===true?'pod-ready':p.ready===false?'pod-not-ready':'cell-unknown'):'cell-unknown'}" data-pod="${esc(p.uid)}" title="${esc(p.name||p.uid)} · ${current?'observed':'recorded'} · ${esc(known(p.phase))}" aria-label="${esc(p.name||p.uid)} · ${esc(p.uid)}"></button>`).join(''):Array.from({length:shown},(_,i)=>`<i class="drone-cell ${current&&active!==null?(i<active?'cell-fresh':'cell-no-heartbeat'):'cell-unknown'}"></i>`).join('');
    return `<article class="cluster-group"><div class="org-title"><h3>${esc(g.name)}</h3><strong>${total??'UNKNOWN'}</strong></div><p class="hint">${current&&active!==null?active+' fresh heartbeats · '+(total-active)+' without fresh heartbeat':'Current activity: UNKNOWN'}</p><div class="drone-matrix" ${identityMode?'':'aria-hidden="true"'}>${dots}</div>${identityMode?`<p class="hint">${Math.min(members.length,shown)} identified pods shown · ${current?'Kubernetes readiness':'historical observation'}. Heartbeats above are aggregate counts.</p>`:total===null?'<p class="hint">No valid count supplied.</p>':shown<total?`<p class="hint">${shown} of ${total} count cells shown.</p>`:''}</article>`;
  }).join('');
  const phaseCounts=Object.entries(run.participants||{}).filter(([,v])=>countValue(v)!==null);
  patchHtml($('clusterMap'),`<div class="cluster-host"><div><span class="cluster-kicker">HOST / RUNTIME</span><h3>${esc(known(run.host))}</h3><span>${esc(known(run.runtime))} · namespace ${esc(known(run.namespace))}</span></div><div class="cluster-total"><strong>${reportedTotal??'UNKNOWN'}</strong><span>${current?'observed pods':'recorded pods'}</span></div></div><div class="cluster-branch" aria-hidden="true"></div><div class="cluster-groups">${groupsHtml}</div>${groups.length>64?'<p class="hint">First 64 groups shown.</p>':''}<div class="cluster-legend"><span><i class="drone-cell cell-fresh"></i> Fresh heartbeat count</span><span><i class="drone-cell cell-no-heartbeat"></i> No fresh heartbeat count</span><span><i class="drone-cell cell-unknown"></i> Historical / unknown activity</span></div><div class="cluster-phases"><b>Recorded phase: ${esc(known(run.phase))}</b>${phaseCounts.map(([k,v])=>`<span>${esc(k)} · ${v} participants (aggregate)</span>`).join('')}</div>`);
  if(pods.length&&identitiesValid)patchHtml($('clusterMap'),$('clusterMap').innerHTML+('<p class="hint">Identified pod colors: cyan = Ready, amber = Not Ready, red = Failed, outline = historical / unknown. Kubernetes readiness is separate from application heartbeat freshness.</p>'));
  const showPod=uid=>{
    const pod=identitiesValid?pods.find(p=>p.uid===uid):null;
    if(!pod)return;
    clusterSelectedPod=uid;clusterSelectedPodRun=run.run_id;
    $('clusterPodDetail').hidden=false;
    $('clusterPodDetail').textContent=pretty({observation:current?'LATEST PROVIDER OBSERVATION':'RECORDED · CURRENT STATE UNKNOWN',run_id:run.run_id,host:run.host,namespace:run.namespace,...pod});
  };
  $('clusterMap').querySelectorAll('[data-pod]').forEach(button=>button.onclick=()=>showPod(button.dataset.pod));
  if(clusterSelectedPodRun===run.run_id)showPod(clusterSelectedPod);
}

async function refresh(){if(refreshInFlight)return;refreshInFlight=true;try{const [s,data,adapters]=await Promise.all([get('/api/summary'),get('/api/runs'),get('/api/adapters')]);latestFleet=s.ok===true?(s.fleet||{}):{};latestObservations=s.run_observations||{};allRuns=data.runs||[];renderSummary(s.summary||{});environment(s,adapters);rebuildFilters();renderRuns();renderCluster(true);const events=await Promise.all(allRuns.map(r=>get('/api/runs/'+encodeURIComponent(r.run_id)+'/events')));table('recentEvents',['Timestamp','Type','Run ID','Phase','Source','Payload'],eventRows(events.flatMap(x=>x.events||[])).slice(-30));if(selectedRunId)await detail(selectedRunId,true)}catch(e){$('health').textContent='OFFLINE';$('health').className='pill tone-bad';$('currentness').textContent='Runtime currentness: UNKNOWN — refresh failed. Visible records may be stale.';$('detailState').textContent='UNKNOWN — connection lost; previous details are hidden.';$('detail').hidden=true;latestFleet={};latestObservations={};renderSummary({});renderCluster(false)}finally{refreshInFlight=false}}
$('clusterRun').onchange=()=>renderCluster();
$('adapter').onchange=renderRuns;$('status').onchange=renderRuns;$('processClass').onchange=renderRuns;refresh();setInterval(refresh,5000);
