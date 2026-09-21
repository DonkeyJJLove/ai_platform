'use strict';
const { sha256, canonicalJson } = require('./canonical');
function norm(s='') { return String(s).normalize('NFKC').toLowerCase(); }
function tokens(s='') { return new Set(norm(s).match(/[\p{L}\p{N}_:./#@+-]+/gu) || []); }
function techIds(s='') { return new Set(String(s).normalize('NFKC').match(/(?:\b\d{4}\b|\b[A-Z][A-Z0-9_.:-]{2,}\b|\b[a-zA-Z_][\w.-]*\.(?:js|py|json|md|ps1|cjs|mjs)\b|\b[a-f0-9]{7,64}\b)/g) || []); }
function quotes(s='') { return new Set(Array.from(String(s).matchAll(/["“”']([^"“”']{3,160})["“”']/g), m => norm(m[1]))); }
function overlap(a,b) { if (!a.size || !b.size) return 0; let n=0; for (const x of a) if (b.has(x)) n++; return n / Math.max(a.size,b.size); }
function exactEntityScore(query, entities=[]) { const q=norm(query); const matches=entities.filter(e => e && q.includes(norm(e.name || e.id || e))); return matches.length ? Math.min(1, matches.length / Math.max(1, entities.length)) : 0; }
function ageWeight(createdAt, now) { const ref=Number.isFinite(now)?now:0; const parsed=Date.parse(createdAt || ''); const t=Number.isFinite(parsed)?parsed:ref; const hours=Math.max(0,(ref-t)/3600000); return 1/(1+hours/48); }
class RelevanceEngine {
  scoreItem(query, item, ctx={}) {
    const qt=tokens(query), it=tokens(item.content || item.text || '');
    const qid=techIds(query), iid=techIds(item.content || item.text || '');
    const quoted=quotes(query); const body=norm(item.content || item.text || '');
    let quoteHit=0; for(const q of quoted) if(body.includes(q)) quoteHit=1;
    const explicitRef = (item.message_id && norm(query).includes(norm(item.message_id))) || (item.source_id && norm(query).includes(norm(item.source_id))) ? 1 : 0;
    const lineage = item.causation_id && ctx.requestLineage?.includes(item.causation_id) ? 1 : (item.request_id && ctx.requestLineage?.includes(item.request_id) ? 1 : 0);
    const threadAffinity = item.thread_id && item.thread_id === ctx.threadId ? 1 : 0;
    const currentness = item.currentness === 'STALE' ? 0 : (item.currentness === 'CURRENT' || item.currentness === 'FRESH' ? 1 : 0.5);
    const contradiction = item.contradiction === true || item.kind === 'CONTRADICTION' ? 1 : 0;
    const stale = item.currentness === 'STALE' ? 1 : 0;
    const noise = item.noise === true ? 1 : 0;
    const feature_scores={semantic_affinity:overlap(qt,it),technical_identifier_overlap:overlap(qid,iid),exact_entity_match:exactEntityScore(query,item.entities||[]),quoted_reference_match:quoteHit,explicit_reference_weight:explicitRef,thread_affinity:threadAffinity,lineage_strength:lineage,source_currentness:currentness,recency_weight:ageWeight(item.created_at,ctx.evaluationTime),contradiction_penalty:contradiction,staleness_penalty:stale,noise_penalty:noise};
    const total=2.2*feature_scores.semantic_affinity+1.8*feature_scores.technical_identifier_overlap+2.5*feature_scores.quoted_reference_match+2.5*explicitRef+1.4*threadAffinity+1.7*lineage+0.8*currentness+0.5*feature_scores.recency_weight+0.5*feature_scores.exact_entity_match-0.7*contradiction-1.2*stale-1.5*noise;
    return {...item,feature_scores,total_score:Number(total.toFixed(6))};
  }
  evaluate({query,thread,messages=[],sources=[],observations=[],currentness={},entities=[],requestLineage=[],evaluation_time=null}) {
    const threadId=thread?.thread_id;
    const all=[...messages.map(x=>({...x,_class:'message'})),...sources.map(x=>({...x,_class:'source'})),...observations.map(x=>({...x,_class:'observation'}))];
    const explicitEvaluation=Date.parse(evaluation_time||'');
    const itemTimes=all.map(x=>Date.parse(x.created_at||'')).filter(Number.isFinite);
    const evaluationTime=Number.isFinite(explicitEvaluation)?explicitEvaluation:(itemTimes.length?Math.max(...itemTimes):0);
    const scored=all.map(x=>this.scoreItem(query,x,{threadId,requestLineage,evaluationTime})).sort((a,b)=>b.total_score-a.total_score||String(a.message_id||a.source_id||'').localeCompare(String(b.message_id||b.source_id||'')));
    const selected=scored.filter(x=>x.total_score>0).slice(0,24),excluded=scored.filter(x=>!selected.includes(x));
    const anchors=[...new Set([...tokens(query)].filter(t=>t.length>=4).slice(0,32))].sort();
    const contradictionIds=selected.filter(x=>x.feature_scores.contradiction_penalty>0).map(x=>x.contradiction_id||x.source_id||x.message_id).filter(Boolean);
    const result={selected_message_ids:selected.filter(x=>x._class==='message').map(x=>x.message_id).filter(Boolean),selected_source_ids:selected.filter(x=>x._class==='source').map(x=>x.source_id).filter(Boolean),semantic_anchors:anchors,contradiction_ids:contradictionIds,excluded_noise:excluded.filter(x=>x.feature_scores.noise_penalty>0).map(x=>x.message_id||x.source_id||x.id).filter(Boolean),feature_scores:selected.map(x=>({id:x.message_id||x.source_id||x.id,class:x._class,total_score:x.total_score,components:x.feature_scores})),total_score:Number(selected.reduce((s,x)=>s+x.total_score,0).toFixed(6)),currentness,entity_ids:entities.map(e=>e.id||e.name||e).filter(Boolean),evaluation_time:new Date(evaluationTime).toISOString()};
    result.evidence_digest=sha256(canonicalJson(result)); return result;
  }
}
module.exports={RelevanceEngine,tokens,techIds,norm};
