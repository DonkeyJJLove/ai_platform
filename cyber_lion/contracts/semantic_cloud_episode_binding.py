"""Read-only binding of semantic-cloud artifacts to an existing EBLE episode."""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from hashlib import sha256
import json,re
from typing import Tuple
from .evidence_bound_learning_episode import EvidenceBoundLearningEpisode

SCHEMA_ID="lion.semantic-cloud-episode-binding/v1";AUTHORITY_EFFECT="NONE";EFFECT="NONE"
_SAFE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$");_HEX=re.compile(r"^[0-9a-f]{64}$")
class SemanticCloudEpisodeBindingError(ValueError):pass
def _id(v,n):
    if not isinstance(v,str) or _SAFE.fullmatch(v) is None:raise SemanticCloudEpisodeBindingError(f"{n} invalid")
    return v
def _hex(v,n):
    if not isinstance(v,str) or _HEX.fullmatch(v) is None:raise SemanticCloudEpisodeBindingError(f"{n} invalid")
    return v
def _refs(v,n):
    if type(v) is not tuple:raise SemanticCloudEpisodeBindingError(f"{n} invalid")
    for x in v:_id(x,n)
    if len(v)!=len(set(v)):raise SemanticCloudEpisodeBindingError(f"{n} unique")
    return v

@dataclass(frozen=True)
class SemanticCloudEpisodeBinding:
    binding_id:str
    eble_episode_ref:str
    eble_episode_digest:str
    mission_intent_ref:str
    query_plan_ref:str
    rag_context_ref:str
    semantic_scaffold_ref:str
    semantic_delta_refs:Tuple[str,...]
    relevance_graph_ref:str
    relevance_projection_refs:Tuple[str,...]
    capability_need_refs:Tuple[str,...]
    composition_refs:Tuple[str,...]
    mosaic_refs:Tuple[str,...]
    decision_candidate_refs:Tuple[str,...]
    action_ir_candidate_ref:str|None
    binding_digest:str=""
    schema_id:str=SCHEMA_ID
    authority_effect:str="NONE"
    effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("binding_digest",None);return d
    def compute_digest(self):
        return sha256(b"LION/SEMANTIC-CLOUD-EPISODE/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,episode:EvidenceBoundLearningEpisode|None=None,require_digest=True):
        for v,n in ((self.binding_id,"binding_id"),(self.eble_episode_ref,"eble_episode_ref"),(self.mission_intent_ref,"mission_intent_ref"),(self.query_plan_ref,"query_plan_ref"),(self.rag_context_ref,"rag_context_ref"),(self.semantic_scaffold_ref,"semantic_scaffold_ref"),(self.relevance_graph_ref,"relevance_graph_ref")):_id(v,n)
        _hex(self.eble_episode_digest,"eble_episode_digest")
        for n in ("semantic_delta_refs","relevance_projection_refs","capability_need_refs","composition_refs","mosaic_refs","decision_candidate_refs"):_refs(getattr(self,n),n)
        if self.action_ir_candidate_ref is not None:_id(self.action_ir_candidate_ref,"action_ir_candidate_ref")
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE" or self.effect!="NONE":raise SemanticCloudEpisodeBindingError("binding cannot carry authority/effect")
        if episode is not None:
            episode.validate()
            if self.eble_episode_ref!=episode.episode_id or self.eble_episode_digest!=episode.episode_digest:raise SemanticCloudEpisodeBindingError("EBLE substitution denied")
        if require_digest:
            _hex(self.binding_digest,"binding_digest")
            if self.binding_digest!=self.compute_digest():raise SemanticCloudEpisodeBindingError("binding_digest mismatch")
        return self
    def sealed(self):return replace(self,binding_digest=self.compute_digest()).validate()
