"""Mission Control source-rebind plans; pure candidate, never service activation."""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json,re

REPOSITORY="DonkeyJJLove/ai_platform"
DOMAIN=b"LION/MISSION-CONTROL/SOURCE-REBIND-CANDIDATE/1\0"
HEX40=re.compile(r"^[0-9a-f]{40}$"); HEX64=re.compile(r"^[0-9a-f]{64}$")

class SourceRebindError(ValueError): pass

def text(v,label):
    if type(v) is not str or not v.strip() or "\0" in v: raise SourceRebindError(label)
def sha40(v,label):
    if type(v) is not str or HEX40.fullmatch(v) is None: raise SourceRebindError(label)
def digest(v,label):
    if type(v) is not str or HEX64.fullmatch(v) is None: raise SourceRebindError(label)
def canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)

@dataclass(frozen=True)
class RuntimeSourceIdentity:
    repository:str; branch:str; source_head:str; source_tree:str; release_id:str; trust_class:str
    def validate(self):
        if self.repository!=REPOSITORY or self.branch!="master": raise SourceRebindError("canonical repository/branch required")
        sha40(self.source_head,"source head"); sha40(self.source_tree,"source tree"); text(self.release_id,"release id")
        if self.trust_class not in {"TEST_ONLY","CANDIDATE","PRODUCTION"}: raise SourceRebindError("trust class")
        return self

@dataclass(frozen=True)
class TargetSourceCandidate:
    repository:str; branch:str; source_head:str; source_tree:str; release_digest:str; configuration_digest:str; adapter_set_digest:str; database_schema_digest:str
    def validate(self):
        if self.repository!=REPOSITORY or self.branch!="master": raise SourceRebindError("target repository/branch")
        sha40(self.source_head,"target head"); sha40(self.source_tree,"target tree")
        for v,n in ((self.release_digest,"release digest"),(self.configuration_digest,"configuration digest"),(self.adapter_set_digest,"adapter set digest"),(self.database_schema_digest,"database schema digest")): digest(v,n)
        return self

@dataclass(frozen=True)
class SourceRebindPlan:
    current_head:str; current_tree:str; target_head:str; target_tree:str; release_digest:str; configuration_digest:str; adapter_set_digest:str; database_schema_digest:str; currentness:str; plan_digest:str
    authority_effect:str="NONE"; runtime_effect:str="NONE"; service_restart:bool=False; k3s_effect:str="NONE"; state:str="OFFLINE_CANDIDATE_NOT_ACTIVATED"
    def validate(self):
        for v,n in ((self.current_head,"current head"),(self.current_tree,"current tree"),(self.target_head,"target head"),(self.target_tree,"target tree")): sha40(v,n)
        for v,n in ((self.release_digest,"release digest"),(self.configuration_digest,"configuration digest"),(self.adapter_set_digest,"adapter set digest"),(self.database_schema_digest,"database schema digest"),(self.plan_digest,"plan digest")): digest(v,n)
        if self.currentness not in {"SOURCE_CHANGE_REQUIRED","ALREADY_CURRENT"}: raise SourceRebindError("currentness")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE" or self.service_restart is not False or self.k3s_effect!="NONE": raise SourceRebindError("rebind plan cannot activate runtime")
        if self.state!="OFFLINE_CANDIDATE_NOT_ACTIVATED": raise SourceRebindError("state promotion")
        body={k:v for k,v in asdict(self).items() if k!="plan_digest"}
        expected=sha256(DOMAIN+canonical(body).encode()).hexdigest()
        if expected!=self.plan_digest: raise SourceRebindError("plan digest mismatch")
        return self

def propose_source_rebind(current,target,*,observed_master_head,observed_master_tree):
    if type(current) is not RuntimeSourceIdentity or type(target) is not TargetSourceCandidate: raise SourceRebindError("exact identities required")
    current.validate(); target.validate(); sha40(observed_master_head,"observed master head"); sha40(observed_master_tree,"observed master tree")
    if (target.source_head,target.source_tree)!=(observed_master_head,observed_master_tree): raise SourceRebindError("target is not exact observed master")
    if current.repository!=target.repository or current.branch!=target.branch: raise SourceRebindError("repository substitution")
    currentness="ALREADY_CURRENT" if (current.source_head,current.source_tree)==(target.source_head,target.source_tree) else "SOURCE_CHANGE_REQUIRED"
    fields=dict(current_head=current.source_head,current_tree=current.source_tree,target_head=target.source_head,target_tree=target.source_tree,
        release_digest=target.release_digest,configuration_digest=target.configuration_digest,adapter_set_digest=target.adapter_set_digest,database_schema_digest=target.database_schema_digest,
        currentness=currentness,authority_effect="NONE",runtime_effect="NONE",service_restart=False,k3s_effect="NONE",state="OFFLINE_CANDIDATE_NOT_ACTIVATED")
    fields["plan_digest"]=sha256(DOMAIN+canonical(fields).encode()).hexdigest()
    return SourceRebindPlan(**fields).validate()

def apply_source_rebind(*args,**kwargs):
    raise SourceRebindError("runtime source rebind requires separate deployment authority")
