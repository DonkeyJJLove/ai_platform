// Display claims only. This renderer never changes runtime or trust classifications.
function renderPassiveEvidence(run, events) {
  const root=document.getElementById('passiveDetail');
  root.replaceChildren();
  root.hidden=run.adapter_type!=='PASSIVE_UNVERIFIED';
  if(root.hidden)return;
  const add=(tag,text,parent=root)=>{const n=document.createElement(tag);n.textContent=text;parent.append(n);return n};
  const value=v=>v===null||v===undefined?'UNKNOWN':typeof v==='object'?JSON.stringify(v):String(v);
  add('h2','Passive evidence · UNVERIFIED');
  add('p','Reported identities, pods and messages. These claims do not establish a current fleet, authenticated sender or runtime authority.').className='hint';
  const evidence=run.evidence?.passive_observation;
  if(!evidence||typeof evidence!=='object'||Array.isArray(evidence)){add('p','No passive observation record.');return}
  const identity=evidence.identity||{};
  const summary=add('dl','');summary.className='passive-summary';
  for(const [label,v] of [
    ['Recorded run',run.run_id],['Declared producer',identity.producer_id],
    ['Declared instance',identity.instance_id],['Declared source run',identity.run_id],
    ['Declared host',identity.host_id],['Declared clock',identity.clock_id],
    ['Source time (Unix ms)',evidence.source_observed_ms],['First receipt (Unix ms)',evidence.first_received_ms],
    ['Evaluated at (Unix ms)',evidence.evaluated_ms],['Recorded time assessment',evidence.freshness],
    ['Declared stage',evidence.lifecycle?.stage],['Declared result',evidence.lifecycle?.result],
    ['Recorded sequence gap',evidence.sequence_gap]]){add('dt',label,summary);add('dd',value(v),summary)}
  add('p','The time assessment belongs to the recorded evaluation; refreshing this page does not renew it.').className='hint';
  add('h3','Declared pod membership');
  const pods=Array.isArray(evidence.pods)?evidence.pods.slice(0,128):[];
  const choices=add('div','');choices.className='passive-pods';
  const detail=add('pre','');detail.id='passivePodDetail';detail.hidden=true;
  for(const pod of pods){
    if(!pod||typeof pod!=='object')continue;
    const button=add('button',`${value(pod.group)} · ${value(pod.name)} · ${value(pod.uid)}`,choices);
    button.type='button';button.dataset.passivePod=value(pod.uid);
    button.onclick=()=>{detail.hidden=false;detail.textContent=JSON.stringify({trust:'UNVERIFIED',recorded_run:run.run_id,...Object.fromEntries(['uid','name','namespace','group','phase','ready','restarts'].map(k=>['declared_'+k,pod[k]??null]))},null,2)};
  }
  if(!pods.length)add('p','No declared pods in this record.',choices);
  add('h3','Unverified recorded messages');
  const list=add('div','');list.id='passiveMessages';
  const messages=(Array.isArray(events)?events:[]).filter(e=>e?.run_id===run.run_id&&e.event_type==='CHANNEL_MESSAGE'&&e.adapter_type==='PASSIVE_UNVERIFIED').slice(-128);
  for(const event of messages){const p=event.payload||{};const item=add('article','',list);item.className='passive-message';
    add('strong','UNVERIFIED · '+value(p.message_id),item);
    add('p',`${value(p.from_fleet)} / ${value(p.from_drone_id)} → ${value(p.to_fleet)}`,item);
    add('p',`Reported type: ${value(p.type)} · source Unix seconds: ${value(event.timestamp)}`,item);
  }
  if(!messages.length)add('p','No unverified messages recorded for this run.',list);
}
