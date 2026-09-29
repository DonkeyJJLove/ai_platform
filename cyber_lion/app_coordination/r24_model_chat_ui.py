"""Candidate R24 canonical Model Chat + separate Protocol verification surface.

This UI is wired only to canonical conversation APIs for Model Chat. Legacy
threads are rendered nowhere on this surface. Protocol is a separate read-only
mission projection with separate transcript semantics.
"""
R24_MODEL_CHAT_UI = r'''<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LION R24 · Canonical Conversations</title>
<style>
:root{color-scheme:dark;--bg:#071019;--panel:#0c1822;--panel2:#0a141d;--line:#284153;--text:#e9f1f6;--muted:#8ea8b8;--accent:#2d8fa5;--ok:#78d9aa;--warn:#e1bd66;--bad:#e48c8c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Segoe UI,system-ui,sans-serif}
.shell{display:grid;grid-template-columns:310px minmax(0,1fr);min-height:100vh}.side{border-right:1px solid var(--line);padding:16px;background:#061018}
main{padding:20px;max-width:1280px;width:100%;margin:auto}.muted{color:var(--muted)}.tiny{font-size:11px}.hidden{display:none!important}
button,select,textarea,input{background:#102937;color:var(--text);border:1px solid #35576b;border-radius:8px;padding:8px}
button{cursor:pointer}.primary{background:var(--accent)}button:disabled{opacity:.5;cursor:not-allowed}.wide{width:100%}
.list{display:flex;flex-direction:column;gap:6px;margin-top:10px}.conv{width:100%;text-align:left;background:#0b1822}.conv.active{border-color:#78cae5;background:#123043}
.tabs{display:flex;gap:6px;margin-bottom:12px}.tab.active{background:var(--accent)}.header{display:flex;gap:12px;align-items:flex-start;justify-content:space-between}
.identity{font:12px/1.5 Consolas,monospace;color:#a9c4d2;overflow-wrap:anywhere}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:9px;padding:9px;background:#0b1720}.k{font-size:10px;color:var(--muted)}.v{font:12px Consolas,monospace;overflow-wrap:anywhere}
.chat{border:1px solid var(--line);border-radius:12px;background:var(--panel);min-height:460px;margin-top:14px;display:flex;flex-direction:column}
.messages{padding:18px;display:flex;flex-direction:column;gap:12px;flex:1}.msg{border:1px solid var(--line);border-radius:10px;padding:10px 12px;max-width:92%;white-space:pre-wrap}
.msg.USER{align-self:flex-end;background:#183345;max-width:80%}.msg.ASSISTANT{align-self:flex-start;background:#0b151d}.msg.imported{border-style:dashed;border-color:#997d37;background:#1a1710}
.role{font-size:10px;color:var(--muted);margin-bottom:4px}.composer{border-top:1px solid var(--line);padding:12px}.composer textarea{width:100%;min-height:90px;resize:vertical;background:#061019}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}.state{font-size:12px;color:var(--muted)}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.pending{border:1px dashed #886f36;border-radius:8px;padding:8px 10px;color:var(--warn);font:12px Consolas,monospace;margin:8px 0}
.box{border:1px solid var(--line);border-radius:10px;background:var(--panel2);padding:12px;margin:10px 0}.protocol-row{border-bottom:1px solid #203544;padding:8px 0;white-space:pre-wrap}.protocol-row:last-child{border-bottom:0}
.bridge{font:11px Consolas,monospace;white-space:pre-wrap}.external{border-color:#705ea7}.danger-note{border:1px solid #734c4c;background:#1a1111;padding:8px;border-radius:8px;color:#e9a5a5}
@media(max-width:850px){.shell{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--line)}}
</style>
</head>
<body>
<div class="shell">
<aside class="side">
  <h1 style="margin:0">LION R24 · Conversations</h1>
  <div class="muted">Canonical Model Chat</div>
  <div class="tabs" style="margin-top:14px">
    <button id="tabChat" class="tab active">Model Chat</button>
    <button id="tabProtocol" class="tab">Protocol</button>
  </div>
  <button id="newConversation" class="primary wide">+ Nowa rozmowa</button>
  <select id="missionSelect" class="wide" style="margin-top:8px"><option value="">— wybierz misję —</option></select>
  <button id="newMissionConversation" class="wide" style="margin-top:6px">+ Nowa rozmowa dla misji</button>
  <button id="filterMission" class="wide" style="margin-top:6px">Pokaż rozmowy tej misji</button>
  <button id="showAll" class="wide" style="margin-top:6px">Pokaż wszystkie</button>
  <div id="conversationList" class="list"></div>
  <div class="danger-note tiny" style="margin-top:16px">Legacy threads są archiwalne/read-only. Ten widok ich nie mutuje.</div>
</aside>
<main>
<section id="chatPanel">
  <div class="header">
    <div>
      <h2 id="title" style="margin:0">Brak rozmowy</h2>
      <div id="identity" class="identity">conversation_id=NONE</div>
    </div>
    <div id="health" class="state">BOOT</div>
  </div>
  <div class="cards">
    <div class="card"><div class="k">STATE</div><div id="convState" class="v">—</div></div>
    <div class="card"><div class="k">BINDING EPOCH</div><div id="epoch" class="v">—</div></div>
    <div class="card"><div class="k">MISSION</div><div id="missionCard" class="v">NULL</div></div>
    <div class="card"><div class="k">ROUTE</div><div id="routeCard" class="v">LOCAL</div></div>
    <div class="card"><div class="k">DELIVERY CURSOR</div><div id="cursorCard" class="v">0</div></div>
  </div>
  <div class="row">
    <button id="bindMission">Bind mission → successor</button>
    <button id="detachMission">Detach → successor UNBOUND</button>
  </div>
  <div class="box external">
    <div class="k">NATIVE SaaS PROJECT THREAD — EXTERNAL ONLY</div>
    <div id="bridges" class="bridge">No explicit bridges.</div>
    <div class="row">
      <input id="externalThreadRef" placeholder="external_thread_ref">
      <input id="externalSystem" value="CHATGPT_SAAS" placeholder="external_system">
      <button id="addBridge">Create explicit bridge</button>
    </div>
  </div>
  <div id="pending"></div>
  <section class="chat">
    <div id="messages" class="messages"></div>
    <div class="composer">
      <textarea id="input" placeholder="Wiadomość Model Chat"></textarea>
      <div class="row">
        <select id="route"><option>LOCAL</option><option>SAAS</option><option>DUAL</option></select>
        <button id="send" class="primary">Wyślij</button>
        <span id="sendState" class="state">READY</span>
      </div>
    </div>
  </section>
</section>

<section id="protocolPanel" class="hidden">
  <div class="header">
    <div>
      <h2 style="margin:0">Protocol plane</h2>
      <div class="identity">Separate semantics · separate transcript · not Model Chat</div>
    </div>
    <div id="protocolHealth" class="state">READY</div>
  </div>
  <div class="box">
    <div class="row">
      <select id="protocolMissionSelect"></select>
      <button id="refreshProtocol">Refresh protocol projection</button>
    </div>
    <div id="protocolIdentity" class="identity" style="margin-top:8px">mission_id=NONE</div>
  </div>
  <div class="box">
    <div class="k">PROTOCOL TRANSCRIPT</div>
    <div id="protocolTranscript" class="tiny muted">Select mission.</div>
  </div>
</section>
</main>
</div>
<script>
const $=id=>document.getElementById(id);
const consumerKey='lion-r24-canonical-consumer';
let consumerId=localStorage.getItem(consumerKey);
if(!consumerId){consumerId='browser-'+crypto.randomUUID().replaceAll('-','');localStorage.setItem(consumerKey,consumerId)}
let conversations=[],missions=[],activeId=null,activeGeneration=0,activeConversation=null,cursorByConversation={},pollBusy=false,pendingByConversation={},missionFilter=null;

async function api(path,opts={}){
 const r=await fetch(path,{cache:'no-store',...opts});let x={};try{x=await r.json()}catch(_){}
 if(!r.ok)throw new Error(x.error||('HTTP '+r.status));return x;
}
const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const opId=p=>p+'-'+crypto.randomUUID().replaceAll('-','');

function tab(which){
 $('chatPanel').classList.toggle('hidden',which!=='chat');$('protocolPanel').classList.toggle('hidden',which!=='protocol');
 $('tabChat').classList.toggle('active',which==='chat');$('tabProtocol').classList.toggle('active',which==='protocol');
}
function renderMissionOptions(){
 const html='<option value="">— wybierz misję —</option>'+missions.map(m=>'<option value="'+esc(m.mission_id)+'">'+esc(m.state+' · '+m.mission_id)+'</option>').join('');
 $('missionSelect').innerHTML=html;$('protocolMissionSelect').innerHTML=html;
}
async function refreshMissions(){
 const x=await api('/api/missions/recent?view=operational');missions=x.missions||[];renderMissionOptions();
}
function renderList(){
 $('conversationList').innerHTML=conversations.map(c=>{
   const mid=c.current_binding?.mission_id||'UNBOUND';
   return '<button class="conv '+(c.conversation_id===activeId?'active':'')+'" data-id="'+esc(c.conversation_id)+'">'+esc(c.title)+'<br><span class="muted">'+esc(c.state)+' · epoch '+esc(c.current_binding?.binding_epoch)+' · '+esc(mid)+'</span></button>';
 }).join('');
 document.querySelectorAll('.conv[data-id]').forEach(b=>b.onclick=()=>openConversation(b.dataset.id));
}
async function refreshList(){
 const qs=new URLSearchParams({limit:'500'});if(missionFilter)qs.set('mission_id',missionFilter);
 const x=await api('/api/conversations?'+qs.toString());conversations=x.conversations||[];renderList();
 if(activeId){const c=conversations.find(x=>x.conversation_id===activeId);if(c)renderConversation(c)}
}
function renderConversation(c){
 activeConversation=c;$('title').textContent=c.title||'Rozmowa';
 $('identity').textContent='conversation_id='+c.conversation_id+' · mission_id='+(c.current_binding?.mission_id??'NULL');
 $('convState').textContent=c.state;$('epoch').textContent=c.current_binding?.binding_epoch??'—';
 $('missionCard').textContent=c.current_binding?.mission_id??'NULL';$('routeCard').textContent=$('route').value;
 $('cursorCard').textContent=String(cursorByConversation[c.conversation_id]??0);
 $('send').disabled=c.state==='FROZEN';$('bindMission').disabled=c.state==='FROZEN';$('detachMission').disabled=c.state==='FROZEN'||!c.current_binding?.mission_id;
 const bridges=c.external_bridges||[];
 $('bridges').textContent=bridges.length?bridges.map(b=>'EXTERNAL · '+b.external_system+' · '+b.external_thread_ref+'\nbridge_id='+b.bridge_id+' · authority_effect='+b.authority_effect).join('\n\n'):'No explicit bridges. Native SaaS threads are not inherited or reused.';
}
function renderMessages(rows){
 $('messages').innerHTML=(rows||[]).map(m=>{
   const imported=!!m.metadata?.imported_legacy;
   const marker=imported?'[IMPORTED LEGACY · READ-ONLY] ':'';
   return '<div class="msg '+esc(m.role)+(imported?' imported':'')+'"><div class="role">'+esc(marker+m.role+' · '+m.lane_id+' · '+m.correlation_id)+'</div>'+esc(m.content)+'</div>';
 }).join('');$('messages').scrollTop=$('messages').scrollHeight;
}
function renderPending(){const rows=pendingByConversation[activeId]||[];$('pending').innerHTML=rows.map(x=>'<div class="pending">'+esc(x)+'</div>').join('')}
async function refreshTranscript(id,generation){
 const x=await api('/api/conversations/'+encodeURIComponent(id)+'/messages');if(id!==activeId||generation!==activeGeneration)return;renderMessages(x.messages||[]);
}
async function openConversation(id){
 const generation=++activeGeneration;activeId=id;renderList();const c=await api('/api/conversations/'+encodeURIComponent(id));
 if(id!==activeId||generation!==activeGeneration)return;renderConversation(c);renderPending();await refreshTranscript(id,generation);await pollEvents(true);
}
async function createConversation(missionId=null){
 const key='ui-'+crypto.randomUUID().replaceAll('-','');const body={title:missionId?'Mission · '+missionId:'Nowa rozmowa',idempotency_key:key};
 if(missionId)body.mission_id=missionId;const c=await post('/api/conversations',body);missionFilter=null;await refreshList();await openConversation(c.conversation_id);
}
async function bindMission(){
 if(!activeId)return;const mid=$('missionSelect').value;if(!mid)throw new Error('Wybierz misję');
 const next=await post('/api/conversations/'+encodeURIComponent(activeId)+'/bind',{mission_id:mid,operation_id:opId('bind')});
 missionFilter=null;await refreshList();await openConversation(next.conversation_id);
}
async function detachMission(){
 if(!activeId)return;const next=await post('/api/conversations/'+encodeURIComponent(activeId)+'/detach',{operation_id:opId('detach')});
 missionFilter=null;await refreshList();await openConversation(next.conversation_id);
}
async function addBridge(){
 if(!activeId||!activeConversation)return;const ref=$('externalThreadRef').value.trim();const system=$('externalSystem').value.trim()||'CHATGPT_SAAS';if(!ref)return;
 const digest=activeConversation.current_binding?.context_digest;if(!digest)throw new Error('context digest unavailable');
 await post('/api/conversations/'+encodeURIComponent(activeId)+'/bridges',{external_thread_ref:ref,external_system:system,context_snapshot_digest:digest,provenance:{surface:'R24_CANONICAL_UI',explicit:true}});
 await openConversation(activeId);
}
async function send(){
 if(!activeId)return;const text=$('input').value.trim();if(!text)return;
 const id=activeId,generation=activeGeneration,route=$('route').value;$('send').disabled=true;$('sendState').textContent='SUBMITTING';
 try{
  const x=await post('/api/conversations/'+encodeURIComponent(id)+'/chat',{message:text,route,client_request_id:opId('ui'),output_language:'auto'});
  if(id!==activeId||generation!==activeGeneration)return;$('input').value='';$('sendState').textContent=x.state||'ACCEPTED';
  const rows=pendingByConversation[id]||(pendingByConversation[id]=[]);if(x.state==='SAAS_QUEUED'||x.state==='DUAL_WAITING')rows.push(route+' · '+x.correlation_id+' · waiting durable response');
  await refreshTranscript(id,generation);await pollEvents(true);
 }catch(e){$('sendState').textContent='ERROR · '+e.message}
 finally{if(id===activeId&&activeConversation?.state!=='FROZEN')$('send').disabled=false}
}
async function pollEvents(force=false){
 if(!activeId||pollBusy)return;pollBusy=true;const id=activeId,generation=activeGeneration;
 try{
   const known=cursorByConversation[id];const qs=new URLSearchParams({consumer_id:consumerId,limit:'100'});if(known!==undefined)qs.set('after',String(known));
   const x=await api('/api/conversations/'+encodeURIComponent(id)+'/events?'+qs.toString());if(id!==activeId||generation!==activeGeneration)return;
   const events=x.events||[];if(events.length){
     await refreshTranscript(id,generation);if(events.some(e=>e.state==='DELIVERED')){pendingByConversation[id]=[];renderPending();$('sendState').textContent='DELIVERED'}
     cursorByConversation[id]=x.next_cursor;await post('/api/conversations/'+encodeURIComponent(id)+'/cursor',{consumer_id:consumerId,last_sequence:x.next_cursor});$('cursorCard').textContent=String(x.next_cursor);
   }else if(known===undefined){cursorByConversation[id]=x.next_cursor||0;$('cursorCard').textContent=String(cursorByConversation[id])}
   $('health').textContent='REACTIVE · '+new Date().toLocaleTimeString();
 }catch(e){if(force)$('health').textContent='DEGRADED · '+e.message}finally{pollBusy=false}
}
async function refreshProtocol(){
 const mid=$('protocolMissionSelect').value;if(!mid){$('protocolTranscript').textContent='Select mission.';return}
 $('protocolHealth').textContent='LOADING';const x=await api('/api/missions/'+encodeURIComponent(mid)+'/process');$('protocolIdentity').textContent='mission_id='+mid+' · Model Chat identity is not used here';
 const rows=x.protocol_messages||[];$('protocolTranscript').innerHTML=rows.length?rows.map(m=>'<div class="protocol-row">'+esc((m.protocol||m.kind||'PROTOCOL')+' · '+(m.from_id||m.from_participant||'?')+' → '+(m.to_id||m.target||'?')+'\n'+JSON.stringify(m.payload||m.content||{},null,2))+'</div>').join(''):'<div class="muted">No protocol messages in current projection.</div>';
 $('protocolHealth').textContent='PROTOCOL CURRENT · '+new Date().toLocaleTimeString();
}

$('tabChat').onclick=()=>tab('chat');$('tabProtocol').onclick=()=>tab('protocol');
$('newConversation').onclick=()=>createConversation(null);
$('newMissionConversation').onclick=()=>{const m=$('missionSelect').value;if(m)createConversation(m)};
$('filterMission').onclick=async()=>{missionFilter=$('missionSelect').value||null;await refreshList()};
$('showAll').onclick=async()=>{missionFilter=null;await refreshList()};
$('bindMission').onclick=()=>bindMission().catch(e=>$('health').textContent='BIND ERROR · '+e.message);
$('detachMission').onclick=()=>detachMission().catch(e=>$('health').textContent='DETACH ERROR · '+e.message);
$('addBridge').onclick=()=>addBridge().catch(e=>$('health').textContent='BRIDGE ERROR · '+e.message);
$('send').onclick=send;$('route').onchange=()=>{$('routeCard').textContent=$('route').value};
$('refreshProtocol').onclick=()=>refreshProtocol().catch(e=>$('protocolHealth').textContent='ERROR · '+e.message);
$('input').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();send()}});
async function boot(){await Promise.all([refreshMissions(),refreshList()]);if(conversations.length)await openConversation(conversations[0].conversation_id);setInterval(()=>void pollEvents(false),800)}
boot().catch(e=>$('health').textContent='BOOT ERROR · '+e.message);
</script>
</body>
</html>'''
