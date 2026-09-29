"""Evidence-bound learning episode as a read-only projection into existing EvolutionaryRnD."""
from __future__ import annotations
from dataclasses import asdict,dataclass,replace
from datetime import datetime,timezone
from hashlib import sha256
import json,re
from typing import Tuple
from cyber_lion.contracts.evolutionary_rnd import EvidenceObservation
SCHEMA_ID="lion.evidence-bound-learning-episode/v1";AUTHORITY_EFFECT="NONE"
EPISODE_CLASSES=frozenset({"POSITIVE_CANDIDATE","NEGATIVE_CANDIDATE","CONTRASTIVE_CANDIDATE","QUARANTINED","SUPERSEDED"})
OUTCOMES=frozenset({"CONFIRMED_SUCCESS","CONFIRMED_FAILURE","PARTIAL","UNKNOWN","SUPERSEDED"})
EVIDENCE_CLASSES=frozenset({"DETERMINISTIC_TEST","INDEPENDENT_OBSERVATION","RECONCILIATION","HUMAN_ADJUDICATION","RECEIPT","TEACHER_OUTPUT","MODEL_OUTPUT","BROKER_RECEIPT","THREAD_DELIVERY","MODEL_CALL","ASSIGNMENT","INVOCATION"})
STRONG_LABEL_EVIDENCE=frozenset({"DETERMINISTIC_TEST","INDEPENDENT_OBSERVATION","RECONCILIATION","HUMAN_ADJUDICATION"})
HEX=re.compile(r"^[0-9a-f]{64}$")
class EvidenceBoundLearningEpisodeError(ValueError):pass
def _dt(v,n):
    if not isinstance(v,str) or not v:raise EvidenceBoundLearningEpisodeError(n)
    try:d=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError as e:raise EvidenceBoundLearningEpisodeError(n) from e
    if d.tzinfo is None:raise EvidenceBoundLearningEpisodeError(n)
    return d.astimezone(timezone.utc)
def _txt(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v:raise EvidenceBoundLearningEpisodeError(n)
    return v
def _hex(v,n):
    if not isinstance(v,str) or not HEX.fullmatch(v):raise EvidenceBoundLearningEpisodeError(n)
    return v
@dataclass(frozen=True)
class EpisodeEvidenceRef:
    ref:str;content_digest:str;evidence_class:str;event_time:str;observation_time:str;ingestion_time:str;available_to_model_at:str;included_in_input:bool
    def validate(self,input_cutoff:str):
        _txt(self.ref,"ref");_hex(self.content_digest,"content_digest")
        if self.evidence_class not in EVIDENCE_CLASSES or type(self.included_in_input) is not bool:raise EvidenceBoundLearningEpisodeError("evidence")
        e,o,i,a,c=map(lambda p:_dt(*p),[(self.event_time,"event_time"),(self.observation_time,"observation_time"),(self.ingestion_time,"ingestion_time"),(self.available_to_model_at,"available_to_model_at"),(input_cutoff,"input_cutoff")])
        if o<e or i<o:raise EvidenceBoundLearningEpisodeError("time order")
        if self.included_in_input and (a>c or i>c):raise EvidenceBoundLearningEpisodeError("future-information leakage")
        return self
@dataclass(frozen=True)
class EvidenceBoundLearningEpisode:
    episode_id:str;model_release_ref:str;causal_group_ref:str;task_family:str;episode_class:str;outcome:str;input_cutoff:str;decision_time:str;
    message_refs:Tuple[str,...];invocation_refs:Tuple[str,...];attempt_refs:Tuple[str,...];assignment_refs:Tuple[str,...];model_call_refs:Tuple[str,...];broker_receipt_refs:Tuple[str,...];result_refs:Tuple[str,...];observation_refs:Tuple[str,...];reconciliation_refs:Tuple[str,...];
    evidence:Tuple[EpisodeEvidenceRef,...];teacher_output_refs:Tuple[str,...];rights_basis_ref:str;classification:str;allowed_uses:Tuple[str,...];teacher_consultation_scope:str;episode_digest:str="";schema_id:str=SCHEMA_ID;authority_effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("episode_digest",None);return d
    def compute_digest(self):return sha256(b"LION/EBLE/1\0"+json.dumps(self.payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    def validate(self,require_digest=True):
        for v,n in [(self.episode_id,"episode_id"),(self.model_release_ref,"model_release_ref"),(self.causal_group_ref,"causal_group_ref"),(self.task_family,"task_family"),(self.rights_basis_ref,"rights_basis_ref"),(self.classification,"classification"),(self.teacher_consultation_scope,"teacher_consultation_scope")]:_txt(v,n)
        cutoff=_dt(self.input_cutoff,"input_cutoff");decision=_dt(self.decision_time,"decision_time")
        if decision<cutoff:raise EvidenceBoundLearningEpisodeError("decision precedes cutoff")
        if self.episode_class not in EPISODE_CLASSES or self.outcome not in OUTCOMES or self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE":raise EvidenceBoundLearningEpisodeError("episode semantics")
        for name in ("message_refs","invocation_refs","attempt_refs","assignment_refs","model_call_refs","broker_receipt_refs","result_refs","observation_refs","reconciliation_refs","teacher_output_refs","allowed_uses"):
            value=getattr(self,name)
            if type(value) is not tuple or len(set(value))!=len(value):raise EvidenceBoundLearningEpisodeError(name)
            for x in value:_txt(x,name)
        if type(self.evidence) is not tuple:raise EvidenceBoundLearningEpisodeError("evidence")
        for ev in self.evidence:ev.validate(self.input_cutoff)
        if self.outcome=="UNKNOWN" and self.episode_class in {"POSITIVE_CANDIDATE","NEGATIVE_CANDIDATE"}:raise EvidenceBoundLearningEpisodeError("UNKNOWN cannot become positive/negative")
        if self.outcome in {"CONFIRMED_SUCCESS","CONFIRMED_FAILURE"}:
            classes={x.evidence_class for x in self.evidence}
            if not classes.intersection(STRONG_LABEL_EVIDENCE):raise EvidenceBoundLearningEpisodeError("teacher/receipt is not ground truth")
            if not self.reconciliation_refs:raise EvidenceBoundLearningEpisodeError("confirmed outcome requires reconciliation")
        if require_digest:
            _hex(self.episode_digest,"episode_digest")
            if self.episode_digest!=self.compute_digest():raise EvidenceBoundLearningEpisodeError("episode digest")
        return self
    def sealed(self):return replace(self,episode_digest=self.compute_digest()).validate()
def to_evidence_observation(episode:EvidenceBoundLearningEpisode,*,source_digest:str,observed_at:str)->EvidenceObservation:
    episode.validate();_hex(source_digest,"source_digest")
    content=episode.episode_digest
    return EvidenceObservation(
        observation_id=f"eble:{episode.episode_id}",observation_kind="EVIDENCE_BOUND_LEARNING_EPISODE",
        source_ref=episode.episode_id,source_digest=source_digest,observed_at=observed_at,
        epistemic_class="OBSERVED",provenance_refs=(episode.episode_id,)+episode.reconciliation_refs,
        content_digest=content,
    ).sealed()
