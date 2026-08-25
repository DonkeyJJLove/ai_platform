"""Non-effectful E004 builder-entry contracts."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json, re
from pathlib import PurePosixPath

SCHEMA_VERSION="1.0.0"
BUILDER_CAPABILITY_CLASS="DETACHED_CANDIDATE_BUILD_ONLY"
_PERMIT_DOMAIN=b"LION/E004-BUILDER-ENTRY-PERMIT/1\0"
_REPLAY_DOMAIN=b"LION/E004-BUILDER-ENTRY-CONSUMPTION/1\0"
_SUBJECT_DOMAIN=b"LION/E004-TRUSTED-BUILDER-SUBJECT/1\0"
_SHA40=re.compile(r"^[0-9a-f]{40}$")
_SHA64=re.compile(r"^[0-9a-f]{64}$")
_ID=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,511}$")
_REPO=re.compile(r"^[^/\s]+/[^/\s]+$")

class BuilderEntryPermitContractError(ValueError): pass

def _json(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def _text(v,n):
    if not isinstance(v,str) or not v.strip() or "\x00" in v: raise BuilderEntryPermitContractError(f"{n} invalid")
    return v
def _id(v,n):
    if not _ID.fullmatch(_text(v,n)): raise BuilderEntryPermitContractError(f"{n} invalid")
    return v
def _dig(v,n):
    if not _SHA64.fullmatch(_text(v,n)): raise BuilderEntryPermitContractError(f"{n} invalid")
    return v
def _sha(v,n):
    if not _SHA40.fullmatch(_text(v,n)): raise BuilderEntryPermitContractError(f"{n} invalid")
    return v
def _repo(v):
    if not _REPO.fullmatch(_text(v,"repository")): raise BuilderEntryPermitContractError("repository invalid")
    return v
def _paths(v,n):
    if type(v) is not tuple or not v or len(set(v))!=len(v): raise BuilderEntryPermitContractError(f"{n} invalid")
    for x in v:
        _text(x,n); p=PurePosixPath(x)
        if "\\" in x or any(c in x for c in "*?[]") or p.is_absolute() or ".." in p.parts or str(p)!=x: raise BuilderEntryPermitContractError(f"{n} unsafe")
    return v
def _resources(repo,scope): return tuple(f"repo-path:{repo}:{p}" for p in scope)

@dataclass(frozen=True)
class TrustedBuilderSubject:
    builder_subject_id:str; builder_instance_id:str; capability_class:str; repository:str
    candidate_scope:tuple[str,...]; resource_scope:tuple[str,...]
    identity_digest:str; implementation_digest:str; attestation_digest:str
    valid_from:str; expires_at:str; state:str="ADMITTED"; source_kind:str="trusted-control-plane"; subject_digest:str=""
    def payload(self):
        d=asdict(self); d.pop("subject_digest"); d["candidate_scope"]=list(self.candidate_scope); d["resource_scope"]=list(self.resource_scope); return d
    def compute_digest(self): return sha256(_SUBJECT_DOMAIN+_json(self.payload())).hexdigest()
    def validate(self):
        _id(self.builder_subject_id,"builder_subject_id"); _id(self.builder_instance_id,"builder_instance_id"); _repo(self.repository); _paths(self.candidate_scope,"candidate_scope")
        if self.resource_scope!=_resources(self.repository,self.candidate_scope): raise BuilderEntryPermitContractError("builder scope projection mismatch")
        for n in ("identity_digest","implementation_digest","attestation_digest"): _dig(getattr(self,n),n)
        _text(self.valid_from,"valid_from"); _text(self.expires_at,"expires_at")
        if self.capability_class!=BUILDER_CAPABILITY_CLASS or self.state!="ADMITTED" or self.source_kind!="trusted-control-plane": raise BuilderEntryPermitContractError("builder subject trust/capability invalid")
        if self.subject_digest:
            _dig(self.subject_digest,"subject_digest")
            if self.subject_digest!=self.compute_digest(): raise BuilderEntryPermitContractError("builder subject digest mismatch")
        return self
    def sealed(self):
        self.validate(); return TrustedBuilderSubject(**{**asdict(self),"subject_digest":self.compute_digest()}).validate()

def builder_entry_replay_payload(**k):
    for n in ("source_consumption_permit_id","root_grant_id","builder_subject_id","builder_instance_id"): _id(k[n],n)
    for n in ("source_consumption_permit_digest","source_consumption_replay_digest","current_baseline_digest","root_grant_digest","current_authority_digest","builder_identity_digest","builder_implementation_digest","builder_attestation_digest"): _dig(k[n],n)
    _repo(k["repository"]); _sha(k["baseline_master_sha"],"baseline_master_sha"); _sha(k["baseline_master_tree_sha"],"baseline_master_tree_sha")
    scope=_paths(k["candidate_scope"],"candidate_scope")
    if k["resource_scope"]!=_resources(k["repository"],scope): raise BuilderEntryPermitContractError("resource scope projection mismatch")
    if k["action"]!="BUILD_CANDIDATE" or k["builder_capability_class"]!=BUILDER_CAPABILITY_CLASS: raise BuilderEntryPermitContractError("action/capability invalid")
    for n in ("authority_epoch","authority_state_version"):
        if isinstance(k[n],bool) or not isinstance(k[n],int) or k[n]<(0 if n=="authority_epoch" else 1): raise BuilderEntryPermitContractError(f"{n} invalid")
    d=dict(k); d["candidate_scope"]=list(scope); d["resource_scope"]=list(k["resource_scope"]); return d

def compute_builder_entry_replay_digest(**k): return sha256(_REPLAY_DOMAIN+_json(builder_entry_replay_payload(**k))).hexdigest()

@dataclass(frozen=True)
class BuilderEntryPermit:
    schema_version:str; builder_entry_permit_id:str; source_consumption_permit_id:str; source_consumption_permit_digest:str; source_consumption_replay_digest:str
    repository:str; baseline_master_sha:str; baseline_master_tree_sha:str; current_baseline_digest:str; action:str; candidate_scope:tuple[str,...]; resource_scope:tuple[str,...]
    authority_epoch:int; authority_state_version:int; root_grant_id:str; root_grant_digest:str; current_authority_digest:str
    builder_subject_id:str; builder_instance_id:str; builder_capability_class:str; builder_identity_digest:str; builder_implementation_digest:str; builder_attestation_digest:str
    checked_at:str; builder_entry_replay_digest:str; state:str="BUILDER_ENTRY_PERMIT_ISSUED"; authority_effect:str="NONE"; execution_effect:str="NONE"; repository_ref_effect:str="NONE"; external_effect:str="NONE"; builder_entry_permit_digest:str=""
    def replay_kwargs(self):
        names=("source_consumption_permit_id","source_consumption_permit_digest","source_consumption_replay_digest","repository","baseline_master_sha","baseline_master_tree_sha","current_baseline_digest","action","candidate_scope","resource_scope","authority_epoch","authority_state_version","root_grant_id","root_grant_digest","current_authority_digest","builder_subject_id","builder_instance_id","builder_capability_class","builder_identity_digest","builder_implementation_digest","builder_attestation_digest")
        return {n:getattr(self,n) for n in names}
    def payload(self):
        d=asdict(self); d.pop("builder_entry_permit_digest"); d["candidate_scope"]=list(self.candidate_scope); d["resource_scope"]=list(self.resource_scope); return d
    def compute_builder_entry_replay_digest(self): return compute_builder_entry_replay_digest(**self.replay_kwargs())
    def compute_digest(self): return sha256(_PERMIT_DOMAIN+_json(self.payload())).hexdigest()
    def validate(self):
        if self.schema_version!=SCHEMA_VERSION: raise BuilderEntryPermitContractError("unsupported schema")
        builder_entry_replay_payload(**self.replay_kwargs()); _text(self.checked_at,"checked_at")
        expected=self.compute_builder_entry_replay_digest()
        if self.builder_entry_replay_digest!=expected: raise BuilderEntryPermitContractError("builder entry replay source binding mismatch")
        if self.builder_entry_permit_id!=f"bep:{expected}": raise BuilderEntryPermitContractError("builder entry permit id mismatch")
        if self.state!="BUILDER_ENTRY_PERMIT_ISSUED" or (self.authority_effect,self.execution_effect,self.repository_ref_effect,self.external_effect)!=("NONE","NONE","NONE","NONE"): raise BuilderEntryPermitContractError("builder entry permit carries state/effect")
        if self.builder_entry_permit_digest:
            _dig(self.builder_entry_permit_digest,"builder_entry_permit_digest")
            if self.builder_entry_permit_digest!=self.compute_digest(): raise BuilderEntryPermitContractError("builder entry permit digest mismatch")
        return self
    def sealed(self):
        self.validate(); return BuilderEntryPermit(**{**asdict(self),"builder_entry_permit_digest":self.compute_digest()}).validate()
