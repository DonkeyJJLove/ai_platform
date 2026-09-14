const MC=id=>document.getElementById(id);
const mcesc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let MC_SELECTED=null,MC_DATA=null,MC_PROTOCOL='ALL',MC_FOCUS=null,MC_PINNED=false,MC_REFRESHING=false,MC_REFRESH_PENDING=false,MC_LAST_RENDER_KEY=null;

async function mcget(path){
  const r=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!r.ok)throw new Error('HTTP '+r.status);
  return r.json();
}
function mccard(k,v){return `<div class="card"><div class="k">${mcesc(k)}</div><div class="v">${mcesc(v)}</div></div>`}
function mcbtn(a,label,cls=''){return `<button type="button" class="${cls}" data-mc-action="${mcesc(a)}">${mcesc(label)}</button>`}
function capState(name){return MC_DATA?.capabilities?.[name]?.state||'UNAVAILABLE'}
function missionPath(mid,suffix=''){return '/api/v3/missions/'+encodeURIComponent(mid)+suffix}
function mcRenderKey(s,registry,sources){const p=s.process||{},d=s.execution_driver||{};return JSON.stringify({projection:s,focus:MC_FOCUS,selected:MC_SELECTED,pinned:MC_PINNED,state:s.state,runtime:s.runtime_state,ready:s.ready,materialized:s.materialized,progress:p.progress,phase:p.current_phase,driver:[d.state,d.generation,d.heartbeat_at,d.current_phase,d.waiting_reason,d.blocking_gate,d.next_action,d.last_effect,d.last_effect_receipt],phases:(s.phases||[]).map(x=>[x.phase_id,x.status,x.progress,x.detail]),logical:(s.logical||[]).map(x=>[x.logical_id,x.ready,x.materialized]),workers:(s.workers||[]).map(x=>[x.pod_uid,x.ready,x.restarts]),messages:(s.protocol_messages||[]).slice(0,30).map(x=>x.id||x.payload_digest),receipts:(s.action_receipts||[]).slice(0,20).map(x=>x.receipt_digest||x.receipt_id),registry:(registry||[]).map(x=>[x.mission_id,x.state,x.progress,x.current_phase]),sources:(sources||[]).map(x=>[x.source_id||x.name,x.available,x.currentness])})}
function mcRenderHeader(s){const mode=MC_PINNED?'PINNED':'FOLLOW_FOCUS',focus=MC_FOCUS||'UNKNOWN',last=s.updated_at||'UNKNOWN';MC('mcV3Meta').textContent=s.title+' · '+s.mission_id+' · state '+s.state+' · runtime '+s.runtime_state+' · VIEW '+mode+(MC_PINNED?' · focus '+focus:'')+' · mission update '+last+' · schema '+(s.normalized_schema_version||missingRecord(s))+' · revision '+(s.projection_revision||missingRecord(s))+' · age '+(s.updated_at?Math.max(0,Math.floor((Date.now()-Date.parse(s.updated_at))/1000))+'s':missingRecord(s))+' · collector poll '+new Date().toISOString()}
function mcCaptureViewport(){const feed=MC('mcProtocolFeed'),active=document.activeElement;return {x:window.scrollX,y:window.scrollY,feed,feedY:feed?.scrollTop||0,active,selection:(active&&typeof active.selectionStart==='number')?[active.selectionStart,active.selectionEnd]:null}}
function mcRestoreViewport(v){if(!v)return;const restore=()=>{if(v.feed&&document.contains(v.feed))v.feed.scrollTop=v.feedY;window.scrollTo(v.x,v.y);if(v.active&&document.contains(v.active)&&document.activeElement!==v.active){try{v.active.focus({preventScroll:true});if(v.selection&&typeof v.active.setSelectionRange==='function')v.active.setSelectionRange(v.selection[0],v.selection[1])}catch(e){}}};restore();requestAnimationFrame(restore)}

// Render only the canonical backend projection; binding is never an auto-hop signal.
function mcRenderSupervisor(projection){
  let host=MC('mcSupervisorCards');
  if(!host){
    const anchor=MC('mcV3Cards');if(!anchor)return;
    host=document.createElement('section');host.id='mcSupervisorCards';
    host.className=anchor.className;host.setAttribute('aria-label','SaaS supervisor');
    anchor.insertAdjacentElement('afterend',host);
  }
  const p=projection||{},lease=p.lease||{},freshness=p.freshness||{};
  const fields=[
    ['channel','SAAS CHANNEL',p.channel],['session','SESSION',p.session],
    ['model','MODEL',p.model],['transport','TRANSPORT',p.transport],
    ['pending','PENDING',p.pending?.request_id??p.pending_state],
    ['last_receipt','LAST RECEIPT',p.last_receipt?.receipt_digest??p.last_receipt_state],
    ['lease','LEASE',lease.state],['expires_at','LEASE EXPIRES',lease.expires_at],
    ['authority','SUPERVISOR AUTHORITY',p.authority],
    ['automatic_hop','AUTOMATIC HOP',typeof p.automatic_hop==='boolean'?String(p.automatic_hop):'UNKNOWN'],
    ['freshness','FRESHNESS',freshness.state],['observed_at','OBSERVED AT',freshness.observed_at],
    ['unknown_reasons','UNKNOWN REASONS',Array.isArray(p.unknown_reasons)?(p.unknown_reasons.join(' · ')||'NONE'):'PROJECTION_UNAVAILABLE'],
  ];
  const existing=new Map(Array.from(host.children).map(node=>[node.dataset.supervisorKey,node]));
  for(const [key,label,value] of fields){
    let card=existing.get(key);
    if(!card){
      card=document.createElement('div');card.className='card';card.dataset.supervisorKey=key;
      const name=document.createElement('div');name.className='k';name.textContent=label;
      const output=document.createElement('div');output.className='v';
      card.append(name,output);host.appendChild(card);
    }
    const output=card.lastElementChild,text=String(value??'UNKNOWN');
    if(output.textContent!==text)output.textContent=text;
  }
}

async function mcPhaseAction(button){
  const missionId=MC_SELECTED,payload={phase_id:button.dataset.phaseId,action:button.dataset.phaseAction,control_token:button.dataset.controlToken};button.disabled=true;
  try{const r=await fetch(missionPath(missionId,'/phase-actions'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),result=await r.json();if(!r.ok)throw new Error(result.error||('HTTP '+r.status));patchHtml(MC('mcPhaseControlResult'),semanticDetail('phase-receipt','Phase control receipt',[['Mission',missionId],['Action',payload.action],['Receipt',result.readback?.receipt_id??result.receipt?.receipt_id],['Driver readback',result.readback?.driver_state],['Phase readback',result.readback?.phase_status]],result,mcesc));await mcRefresh()}
  catch(error){MC('mcPhaseControlResult').textContent='CONTROL DENIED / UNAVAILABLE · '+error.message}
  finally{button.disabled=false}
}

async function mcCurrentMaterialAct(action,pod){
  if(MC_DATA?.mission_id!=='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3')return alert('Low-level material action is not bound to this mission.');
  if(!confirm(action+(pod?' '+pod:'')))return;
  const r=await fetch('/api/v3/missions/current/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...(pod?{pod_name:pod}:{})})});
  const x=await r.json();if(!r.ok){alert(x.error||'control failed');return}await mcRefresh();
}

async function mcLifecycleAct(action,payload={}){
  if(!MC_SELECTED)return;
  const label=action.replaceAll('_',' ');
  if(action==='RESTART'&&!confirm('Restart material runtime for '+MC_SELECTED+'?\nThis does not clear PASS/FAIL/BLOCKED phase verdicts.'))return;
  if(action==='ROLLBACK'&&!confirm(label+' mission '+MC_SELECTED+'?'))return;
  const r=await fetch(missionPath(MC_SELECTED,'/actions'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})});
  const x=await r.json();
  if(!r.ok){alert(x.error||'mission lifecycle action failed');return}
  if(x?.result?.state&&String(x.result.state).includes('REQUIRED'))alert(label+': '+x.result.state+'\nNo material effect was executed.');
  await mcRefresh();
}

async function mcActionPrompt(action){
  if(action==='REDESIGN'){
    const reason=prompt('Redesign intent / reason');if(!reason)return;return mcLifecycleAct(action,{reason});
  }
  if(action==='ADD_COMPONENT'){
    const component_id=prompt('Component ID (stable identifier)');if(!component_id)return;
    const component_class=prompt('Component class / role','LOGICAL_COMPONENT')||'LOGICAL_COMPONENT';
    return mcLifecycleAct(action,{component:{component_id,component_class},reason:'operator requested component addition'});
  }
  if(action==='ACTIVATE_REVISION'){
    const comp=(MC_DATA?.revision_compilations||[]).find(x=>String(x.state||'').includes('AWAITING_EXPLICIT_ACTIVATION'));
    if(!comp)return alert('No compiled successor revision is awaiting explicit activation.');
    const typed=prompt('Exact successor LPCL digest to activate\n'+comp.successor_mission_id,comp.lpcl_digest);if(!typed)return;
    if(typed.trim()!==comp.lpcl_digest)return alert('Exact digest mismatch; activation denied.');
    return mcLifecycleAct(action,{revision_id:comp.revision_id,lpcl_digest:typed.trim()});
  }
  if(action==='ROLLBACK'){
    const point=(MC_DATA?.rollback_points||[])[0];
    if(!point)return alert('No rollback evidence point exists yet. Run Audit first.');
    return mcLifecycleAct(action,{rollback_id:point.rollback_id});
  }
  return mcLifecycleAct(action);
}

function mcRenderProtocols(s){
  const rows=s.protocol_messages||[],counts={};for(const x of rows)counts[x.protocol]=(counts[x.protocol]||0)+1;
  const keys=Object.keys(counts).sort();if(MC_PROTOCOL!=='ALL'&&!counts[MC_PROTOCOL])MC_PROTOCOL='ALL';
  patchHtml(MC('mcProtocolFilters'),(rows.length?`<button class="mc-proto ${MC_PROTOCOL==='ALL'?'active':''}" data-proto="ALL">ALL <b>${rows.length}</b></button>`:'')+keys.map(k=>`<button class="mc-proto ${MC_PROTOCOL===k?'active':''}" data-proto="${mcesc(k)}">${mcesc(k)} <b>${counts[k]}</b></button>`).join(''));
  MC('mcProtocolFilters').querySelectorAll('[data-proto]').forEach(b=>b.onclick=()=>{MC_PROTOCOL=b.dataset.proto;mcRenderProtocols(s)});
  const shown=rows.filter(x=>MC_PROTOCOL==='ALL'||x.protocol===MC_PROTOCOL).slice(0,120);
  patchHtml(MC('mcProtocolFeed'),shown.length?shown.map(x=>{const q=x.payload||{},summary=[q.event,q.status,q.action,q.gate,q.state].filter(Boolean).join(' · ')||'RECORDED';return `<article class="mc-message" data-key="${mcesc(x.id||x.payload_digest||[x.observed_at,x.protocol,x.from_id,x.to_id].join(':'))}"><div><b>${mcesc(x.protocol)}</b> · ${mcesc(x.from_id)} → ${mcesc(x.to_id)}</div><div class="mc-message-meta">${mcesc(x.observed_at)} · phase ${mcesc(x.phase||'—')} · ${mcesc(x.direction)}</div><div class="mc-labels"><span>${mcesc(summary)}</span>${q.authority_effect?`<span>AUTH ${mcesc(q.authority_effect)}</span>`:''}</div><details class="mc-raw"><summary>RAW</summary><pre>${mcesc(JSON.stringify(q,null,2))}</pre></details></article>`}).join(''):'<div class="mc-line mc-history">No protocol messages recorded for this mission/stage.</div>');
}

function renderSchemaContext(s){
  const sc=s.schema_context||{},gaps=sc.missing_fields||[];
  const hist=String(sc.record_class||'').startsWith('HISTORICAL');
  MC('mcSchemaNotice').className='mc-schema-notice '+(hist?'historical':'current');
  patchHtml(MC('mcSchemaNotice'),`<b>${mcesc(sc.record_class||'SCHEMA UNKNOWN')}</b> · ${mcesc(sc.source_stage||'UNKNOWN STAGE')}<br>${mcesc(sc.compatibility_note||'')}`+
    (gaps.length?`<div class="mc-gap-list"><b>Fields not recorded at source stage:</b> ${gaps.map(x=>mcesc(x.field_name)).join(' · ')}</div>`:''));
  patchHtml(MC('mcLifecycleInfo'),`<b>DB schema:</b> ${mcesc(s.normalized_schema_version||sc.current_schema||missingRecord(s))} · <b>lineage:</b> ${(s.lineage||[]).length} · <b>design revisions:</b> ${(s.design_revisions||[]).length} · <b>audits:</b> ${(s.audits||[]).length} · <b>rollback points:</b> ${(s.rollback_points||[]).length}`);
}

function renderLifecycleActions(s){
  let a=mcbtn('REFRESH','Refresh')+mcbtn('AUDIT','Audit')+mcbtn('RESTART','Restart material runtime')+mcbtn('VALIDATE','Validate')+mcbtn('REDESIGN','Redesign')+mcbtn('ADD_COMPONENT','Add component')+mcbtn('ROLLBACK','Rollback plan');
  if((s.revision_compilations||[]).some(x=>String(x.state||'').includes('AWAITING_EXPLICIT_ACTIVATION')))a+=mcbtn('ACTIVATE_REVISION','Activate revision');
  const ds=s.execution_driver?.state;
  if(['ACTIVE','WAITING','BLOCKED'].includes(ds))a+=mcbtn('PAUSE','Pause driver');
  if(['BOOTSTRAP_PAUSED','PAUSED','STOPPED','FAILED'].includes(ds))a+=mcbtn('RESUME','Resume driver');
  if(ds&&!['COMPLETE','STOPPED'].includes(ds))a+=mcbtn('STOP','Stop driver','danger');
  if(s.mission_id==='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3'){
    if(s.state==='RUNNING')a+=`<button type="button" data-low-action="PAUSE">Pause</button><button type="button" data-low-action="VALIDATE">Validate fleet</button>`;
    if(s.state==='PAUSED')a+=`<button type="button" data-low-action="RESUME">Resume</button>`;
    if(['RUNNING','PAUSED','FAILED','CONVERGING'].includes(s.state))a+=`<button type="button" class="danger" data-low-action="STOP">Stop</button>`;
    if(['AUTHORIZED','STOPPED','FAILED'].includes(s.state))a+=`<button type="button" data-low-action="START">Start</button>`;
  }
  patchHtml(MC('mcV3Actions'),a);
  MC('mcV3Actions').querySelectorAll('[data-mc-action]').forEach(b=>b.onclick=()=>mcActionPrompt(b.dataset.mcAction));
  MC('mcV3Actions').querySelectorAll('[data-low-action]').forEach(b=>b.onclick=()=>mcCurrentMaterialAct(b.dataset.lowAction));
  patchHtml(MC('mcCapabilityMatrix'),Object.entries(s.capabilities||{}).map(([k,v])=>`<span class="mc-cap"><b>${mcesc(k)}</b> ${mcesc(v.state)}${v.reason?' · '+mcesc(v.reason):''}</span>`).join(''));
}

function mcRender(s,registry,sources){
  MC_DATA=s;const n=s.normalized_runtime||{},p={...(s.process||{}),current_phase:n.runtime?.current_phase??s.process?.current_phase},sc=s.schema_context||{};
  patchHtml(MC('mcV3Authority'),'CONTROL: <b>'+mcesc(s.control_authority||'NONE')+'</b>');
  mcRenderHeader(s);
  const historical=String(sc.record_class||'').startsWith('HISTORICAL');
  MC('mcObjective').textContent=p.objective||(historical?'Not recorded: mission predates the mission-process schema.':'Objective not recorded');
  MC('mcDescription').textContent=p.description||'';
  const hasProgress=p.progress!==null&&p.progress!==undefined;
  const progress=hasProgress?Number(p.progress):null;
  MC('mcProgressLabel').textContent=hasProgress?'Progress '+progress.toFixed(1)+'%':'Progress: NOT RECORDED AT SOURCE STAGE';
  MC('mcCurrentPhase').textContent=p.current_phase?('Current phase: '+p.current_phase):(historical?'Phase model did not exist for this record':'No active phase');
  MC('mcProgressBar').style.width=hasProgress?Math.max(0,Math.min(100,progress))+'%':'0%';
  patchHtml(MC('mcV3Cards'),[['STATE',s.state],['RUNTIME',s.runtime_state],['LOGICAL',s.logical_count],['MATERIAL',`${s.materialized}/${s.material_target}`],['READY',`${s.ready}/${s.material_target}`],['PROGRESS',hasProgress?progress.toFixed(1)+'%':'N/A'],['SCHEMA',sc.record_class||'UNKNOWN'],['AUTH',p.authority_state||'N/A']].map(x=>mccard(...x)).join(''));
  renderSchemaContext(s);renderLifecycleActions(s);
  const d=s.execution_driver||{};
  patchHtml(MC('mcDriverState'),d.driver_id?`<div class="mc-driver-grid"><span><b>DRIVER</b> ${mcesc(d.state||'UNKNOWN')}</span><span><b>GEN</b> ${mcesc(d.generation)}</span><span><b>HEARTBEAT</b> ${mcesc(d.heartbeat_at||'NONE')}</span><span><b>PHASE</b> ${mcesc(d.current_phase||'—')}</span><span><b>ATTEMPT</b> ${mcesc((d.latest_attempt||{}).attempt_id||'—')}</span><span><b>WAIT</b> ${mcesc(d.waiting_reason||'—')}</span><span><b>GATE</b> ${mcesc(d.blocking_gate||'—')}</span><span><b>NEXT</b> ${mcesc(d.next_action||'—')}</span><span><b>LAST EFFECT</b> ${mcesc(d.last_effect||'—')}</span><span><b>RECEIPT</b> ${mcesc(d.last_effect_receipt||'—')}</span></div>`:'<div class="mc-line mc-history"><b>DRIVER:</b> not materialized for this mission/stage.</div>');
  patchHtml(MC('mcPhases'),boundedRows(s.normalized_runtime?.phases??s.phases).map(x=>phaseCard(x,s,mcesc)).join('')||'<p>'+missingRecord(s)+'</p>');
  MC('mcPhases').querySelectorAll('[data-phase-action]').forEach(b=>b.onclick=()=>mcPhaseAction(b));
  mcRenderProtocols(s);
  const startComponentAllowed=capState('START_COMPONENT')!=='UNAVAILABLE';
  patchHtml(MC('mcV3Logical'),(s.logical||[]).map(x=>`<article class="mc-ld"><b>${mcesc(x.logical_id)} · ${mcesc(x.role)}</b><div>${x.ready}/${x.material_target} ready · ${x.materialized}/${x.material_target} materialized</div><div class="bar"><i style="width:${Math.min(100,100*x.ready/Math.max(1,x.material_target))}%"></i></div>${startComponentAllowed?`<button type="button" data-start-component="${mcesc(x.logical_id)}">start component</button>`:''}</article>`).join('')||'<div class="mc-line mc-history">No logical component model was recorded for this mission/stage.</div>');
  MC('mcV3Logical').querySelectorAll('[data-start-component]').forEach(b=>b.onclick=()=>mcLifecycleAct('START_COMPONENT',{component_id:b.dataset.startComponent}));
  const role=Object.fromEntries((s.logical||[]).map(x=>[x.logical_id,x.role]));
  // Retain only the pre-existing exact legacy mission RESTART_ONE control.
  const workerRestart=s.mission_id==='LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3'&&s.state==='RUNNING'?(worker=>typeof worker.pod_name==='string'&&worker.pod_name?`<button type="button" data-key="restart" data-restart="${mcesc(worker.pod_name)}">restart pod</button>`:''):null;
  patchHtml(MC('mcV3Workers'),workerCards(s,mcesc,workerRestart));
  MC('mcV3Workers').querySelectorAll('[data-restart]').forEach(b=>b.onclick=()=>mcCurrentMaterialAct('RESTART_ONE',b.dataset.restart));

  patchHtml(MC('mcV3Registry'),(registry||[]).map(x=>{const has=x.progress!==null&&x.progress!==undefined;const progressText=has?Number(x.progress).toFixed(1)+'%':'historical · no process progress';return `<button type="button" class="mc-reg ${x.mission_id===s.mission_id?'active':''}" data-mid="${mcesc(x.mission_id)}"><b>${x.controllable?'●':'○'} ${mcesc(x.title||x.mission_id)}</b><span>${mcesc(x.state)} · ${mcesc(progressText)}${x.current_phase?' · '+mcesc(x.current_phase):''}</span><small>${mcesc(x.objective||'Process metadata not recorded at source stage')}</small></button>`}).join(''));
  MC('mcV3Registry').querySelectorAll('[data-mid]').forEach(b=>b.onclick=()=>{MC_SELECTED=b.dataset.mid;MC_PINNED=MC_SELECTED!==MC_FOCUS;MC_LAST_RENDER_KEY=null;mcRefresh()});
  const actionReceipts=(s.action_receipts||[]).map(x=>`<div class="mc-line">${mcesc(x.created_at)} · ${mcesc(x.action)} · <b class="${x.status==='PASS'?'mc-live':'mc-bad'}">${mcesc(x.status)}</b> · ${mcesc(x.effect_class)}</div>`).join('');
  const commands=(s.commands||[]).map(x=>`<div class="mc-line">${mcesc(x.requested_at)} · ${mcesc(x.action)} · <b class="${x.status==='PASS'?'mc-live':x.status==='FAIL'?'mc-bad':'mc-warn'}">${mcesc(x.status)}</b>${x.pod_name?' · '+mcesc(x.pod_name):''}</div>`).join('');
  patchHtml(MC('mcV3Commands'),actionReceipts+commands||'<div class="mc-line">No control receipts.</div>');
  patchHtml(MC('mcV3Sources'),(sources||[]).map(x=>`<article class="source-card"><b>${mcesc(x.source_id||x.name)}</b> · <span class="${x.available?'mc-live':'mc-bad'}">${x.available?'AVAILABLE':'MISSING'}</span><div>${mcesc(x.path)}</div><div class="tables">${mcesc(Object.entries(x.tables||{}).map(([k,v])=>k+'='+v).join(' · '))}</div><div class="tables">mode=${mcesc(x.mode)} · currentness=${mcesc(x.currentness)}</div></article>`).join(''));
}

async function mcRefresh(){
  if(MC_REFRESHING){MC_REFRESH_PENDING=true;return}MC_REFRESHING=true;
  try{
    const [reg,src]=await Promise.all([mcget('/api/v3/missions/recent'),mcget('/api/v3/evidence-sources')]);
    const registry=reg.missions||[];MC_FOCUS=reg.focus_mission_id||registry[0]?.mission_id||'LION-R4-PREFLIGHT-L12-M64-MISSION-CONTROL-V3';
    if(!MC_PINNED||!MC_SELECTED||!registry.some(x=>x.mission_id===MC_SELECTED))MC_SELECTED=MC_FOCUS;
    const requestedMissionId=MC_SELECTED;
    const [s,supervisor]=await Promise.all([mcget(missionPath(requestedMissionId,'/process')),mcget('/api/v3/saas/status?mission_id='+encodeURIComponent(requestedMissionId)).catch(()=>null)]);
    if(requestedMissionId!==MC_SELECTED){MC_REFRESH_PENDING=true;return}
    mcRenderSupervisor(supervisor?.supervisor_projection);
    const vp=mcCaptureViewport();
    const select=MC('mcMissionSelect');patchHtml(select,registry.map(x=>`<option value="${mcesc(x.mission_id)}">${mcesc(x.title||x.mission_id)} · ${mcesc(x.state)}${x.mission_id===MC_FOCUS?' · FOCUS':''}</option>`).join(''));
    select.value=MC_SELECTED;select.onchange=()=>{MC_SELECTED=select.value;MC_PINNED=MC_SELECTED!==MC_FOCUS;MC_LAST_RENDER_KEY=null;mcRefresh()};const rf=MC('mcReturnFocus');if(rf){rf.hidden=!MC_PINNED;rf.onclick=()=>{MC_PINNED=false;MC_SELECTED=MC_FOCUS;MC_LAST_RENDER_KEY=null;mcRefresh()}};
    const key=mcRenderKey(s,registry,src.sources||[]);if(key!==MC_LAST_RENDER_KEY){mcRender(s,registry,src.sources||[]);MC_LAST_RENDER_KEY=key}else mcRenderHeader(s);mcRestoreViewport(vp);
  }catch(e){mcRenderSupervisor(null);MC('mcV3Authority').textContent='CONTROL UNKNOWN';MC('mcV3Meta').textContent='Mission control refresh failed: '+e.message}
  finally{MC_REFRESHING=false;if(MC_REFRESH_PENDING){MC_REFRESH_PENDING=false;queueMicrotask(mcRefresh)}}
}
mcRefresh();setInterval(mcRefresh,3000);
