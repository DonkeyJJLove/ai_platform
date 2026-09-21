'use strict';
const { canonicalJson, sha256 } = require('./canonical');
const { latentProxy } = require('./latent-proxy');
function semanticEntropyMetrics({allMessages=[],selectedMessages=[],allSources=[],selectedSources=[],semanticAnchors=[],crossThreadReferenceCount=0,relevance}){
  const values=[...selectedMessages,...selectedSources].map(x=>String(x.digest||x.content||x.text||'')),unique=new Set(values);
  const stale=selectedSources.filter(x=>x.currentness==='STALE').length,selectedBytes=Buffer.byteLength(canonicalJson({selectedMessages,selectedSources}));
  const allCount=allMessages.length+allSources.length,selectedCount=selectedMessages.length+selectedSources.length,scores=(relevance.feature_scores||[]).map(x=>x.total_score);
  const mean=scores.length?scores.reduce((a,b)=>a+b,0)/scores.length:0,dispersion=scores.length?scores.reduce((s,x)=>s+(x-mean)**2,0)/scores.length:0;
  return {duplicate_context_ratio:values.length?(values.length-unique.size)/values.length:0,stale_context_ratio:selectedSources.length?stale/selectedSources.length:0,contradiction_count:(relevance.contradiction_ids||[]).length,cross_thread_reference_count:crossThreadReferenceCount,semantic_anchor_retention:semanticAnchors.length?1:1,relevance_dispersion:Number(dispersion.toFixed(6)),context_pruning_ratio:allCount?Math.max(0,(allCount-selectedCount)/allCount):0,context_byte_size:selectedBytes};
}
function buildContextEnvelope({thread,requestId,intent,relevance,messages=[],sources=[],observations=[],currentness={},providerRequirements={},selectedProvider}){
  const selectedMessages=messages.filter(m=>(relevance.selected_message_ids||[]).includes(m.message_id));
  const selectedSources=sources.filter(s=>(relevance.selected_source_ids||[]).includes(s.source_id));
  const contradictions=(relevance.contradiction_ids||[]).map(id=>({id}));
  const entropy=semanticEntropyMetrics({allMessages:messages,selectedMessages,allSources:sources,selectedSources,semanticAnchors:relevance.semantic_anchors||[],relevance});
  const proxy=latentProxy({query:intent,relevance,selectedSources,thread,contradictions,selectedProvider});
  const envelope={schema:'lion.context-envelope/v1',thread_id:thread.thread_id,request_id:requestId,intent,semantic_anchors:relevance.semantic_anchors||[],selected_messages:selectedMessages.map(({message_id,role,content,created_at,meta})=>({message_id,role,content,created_at,meta})),selected_sources:selectedSources,currentness,contradictions,excluded_noise_summary:{count:(relevance.excluded_noise||[]).length,ids:relevance.excluded_noise||[]},relevance_features:relevance.feature_scores||[],semantic_context_entropy_metrics:entropy,latent_proxy:proxy,provider_requirements:providerRequirements,authority_effect:'NONE'};
  return {...envelope,context_digest:sha256(canonicalJson(envelope))};
}
module.exports={buildContextEnvelope,semanticEntropyMetrics};
