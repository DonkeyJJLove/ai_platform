'use strict';
const { tokens, techIds } = require('./relevance-engine');
function latentProxy({query,relevance,selectedSources=[],thread,contradictions=[],selectedProvider}) {
  const sourceAffinities=(relevance.feature_scores||[]).filter(x=>x.class==='source').map(x=>({source_id:x.id,score:x.total_score}));
  const stale=selectedSources.filter(x=>x.currentness==='STALE').length;
  const duplicates=new Set(); let duplicateCount=0;
  for(const s of selectedSources){const k=String(s.digest||s.content||s.text||'');if(duplicates.has(k))duplicateCount++;else duplicates.add(k);}
  return {model_internal_latent_state:'UNOBSERVABLE',latent_proxy_state:'OBSERVABLE_DERIVED_STATE',query_terms:[...tokens(query)].sort(),semantic_anchors:[...(relevance.semantic_anchors||[])],entity_ids:[...(relevance.entity_ids||[])],technical_identifiers:[...techIds(query)].sort(),source_affinities:sourceAffinities,thread_affinity:thread?.thread_id?1:0,contradiction_density:contradictions.length/Math.max(1,(relevance.selected_source_ids||[]).length+(relevance.selected_message_ids||[]).length),stale_evidence_ratio:stale/Math.max(1,selectedSources.length),duplicate_context_ratio:duplicateCount/Math.max(1,selectedSources.length),lineage_depth:0,selected_provider:selectedProvider,authority_effect:'NONE'};
}
module.exports={latentProxy};
