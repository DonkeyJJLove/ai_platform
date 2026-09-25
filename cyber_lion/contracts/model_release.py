"""Immutable ModelRelease identity; lifecycle/promotion is separate and non-effectful."""
from dataclasses import asdict,dataclass,replace
from hashlib import sha256
import json,re
HEX=re.compile(r"^[0-9a-f]{64}$");AUTHORITY_EFFECT="NONE";SCHEMA_ID="lion.model-release/v1"
class ModelReleaseError(ValueError):pass
def _j(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _h(v,n):
    if not isinstance(v,str) or not HEX.fullmatch(v):raise ModelReleaseError(n)
    return v
def _t(v,n):
    if not isinstance(v,str) or not v.strip():raise ModelReleaseError(n)
    return v
@dataclass(frozen=True)
class ModelRelease:
    release_id:str;base_weights_digest:str;adapter_digest:str|None;tokenizer_digest:str;chat_template_digest:str;prompt_profile_digest:str;tool_schema_digest:str;runtime_digest:str;knowledge_release_digest:str;release_digest:str="";schema_id:str=SCHEMA_ID;authority_effect:str="NONE"
    def payload(self):d=asdict(self);d.pop("release_digest",None);return d
    def compute_digest(self):return sha256(b"LION/MODEL-RELEASE/1\0"+_j(self.payload())).hexdigest()
    def validate(self,require_digest=True):
        _t(self.release_id,"release_id")
        for n in ("base_weights_digest","tokenizer_digest","chat_template_digest","prompt_profile_digest","tool_schema_digest","runtime_digest","knowledge_release_digest"):_h(getattr(self,n),n)
        if self.adapter_digest is not None:_h(self.adapter_digest,"adapter_digest")
        if self.schema_id!=SCHEMA_ID or self.authority_effect!="NONE":raise ModelReleaseError("schema/authority")
        if require_digest:
            _h(self.release_digest,"release_digest")
            if self.release_digest!=self.compute_digest():raise ModelReleaseError("release identity changed")
        return self
    def sealed(self):return replace(self,release_digest=self.compute_digest()).validate()
LIFECYCLE_STATES=frozenset({"TRAINING_CANDIDATE","EVALUATED_CANDIDATE","SHADOW_CANDIDATE","APPROVED_RELEASE"})
@dataclass(frozen=True)
class ModelReleaseLifecycle:
    release_ref:str;state:str;evidence_refs:tuple[str,...];authority_effect:str="NONE"
    def validate(self):
        _t(self.release_ref,"release_ref")
        if self.state not in LIFECYCLE_STATES or type(self.evidence_refs) is not tuple or self.authority_effect!="NONE":raise ModelReleaseError("lifecycle")
        return self
