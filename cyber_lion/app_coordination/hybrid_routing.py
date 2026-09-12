"""Effect-free hybrid routing policy for LION R8 candidates.

Routing decides where proposal-only reasoning may occur. It never grants authority,
starts a model runtime, dispatches an effect, mutates a repository or consumes a lease.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json,re

D=re.compile(r"^[0-9a-f]{64}$")
ROUTES=frozenset({"LOCAL","SAAS","DETERMINISTIC","QUEUE","DEFER"})
SENSITIVE=frozenset({"AUTHORITY_BOUND","SECURITY_DECISION","CURRENTNESS_BIND","CROSS_MODULE_DIAGNOSIS"})

def _text(v,n):
    if type(v) is not str or not v.strip() or "\x00" in v: raise ValueError(n)
def _digest(v,n):
    if type(v) is not str or D.fullmatch(v) is None: raise ValueError(n)
def _canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

@dataclass(frozen=True)
class HybridRoutingPolicy:
    policy_id:str; revision:str; local_model_digest:str; local_runtime_digest:str
    local_context_limit:int=4096; local_parallel_slots:int=1
    local_classes:tuple[str,...]=("RAG_RETRIEVAL_WITH_SOURCE_IDENTITY","TEST_CASE_PROPOSAL")
    authority_effect:str="NONE"; runtime_effect:str="NONE"
    def validate(self):
        _text(self.policy_id,"policy_id");_text(self.revision,"revision")
        _digest(self.local_model_digest,"local_model_digest");_digest(self.local_runtime_digest,"local_runtime_digest")
        if type(self.local_context_limit) is not int or self.local_context_limit<256: raise ValueError("local_context_limit")
        if type(self.local_parallel_slots) is not int or self.local_parallel_slots!=1: raise ValueError("local_parallel_slots must remain one until remeasured")
        if type(self.local_classes) is not tuple or not self.local_classes or len(set(self.local_classes))!=len(self.local_classes): raise ValueError("local_classes")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE": raise ValueError("routing policy cannot carry authority/effect")
        return self
    def digest(self): self.validate(); return sha256(b"LION/R8/HYBRID-ROUTING-POLICY/1\0"+_canon(asdict(self))).hexdigest()

@dataclass(frozen=True)
class ModelProfile:
    model_digest:str; runtime_digest:str; runtime_state:str; qualified_classes:tuple[str,...]; context_limit:int; parallel_slots:int
    def validate(self):
        _digest(self.model_digest,"model_digest");_digest(self.runtime_digest,"runtime_digest")
        if self.runtime_state not in {"ACTIVE","INACTIVE","UNKNOWN"}: raise ValueError("runtime_state")
        if type(self.qualified_classes) is not tuple or len(set(self.qualified_classes))!=len(self.qualified_classes): raise ValueError("qualified_classes")
        if type(self.context_limit) is not int or self.context_limit<1: raise ValueError("context_limit")
        if type(self.parallel_slots) is not int or self.parallel_slots<0: raise ValueError("parallel_slots")
        return self

@dataclass(frozen=True)
class TaskEnvelope:
    task_id:str; task_class:str; operation_class:str; input_digest:str; input_tokens:int; data_may_leave_host:bool=True; authority_bound:bool=False
    def validate(self):
        _text(self.task_id,"task_id");_text(self.task_class,"task_class");_text(self.operation_class,"operation_class");_digest(self.input_digest,"input_digest")
        if type(self.input_tokens) is not int or self.input_tokens<0: raise ValueError("input_tokens")
        if type(self.data_may_leave_host) is not bool or type(self.authority_bound) is not bool: raise ValueError("booleans")
        return self

@dataclass(frozen=True)
class RouteDecision:
    route:str; reason:str; policy_digest:str; task_id:str; authority_effect:str="NONE"; runtime_effect:str="NONE"
    def validate(self):
        if self.route not in ROUTES: raise ValueError("route")
        _text(self.reason,"reason");_digest(self.policy_digest,"policy_digest");_text(self.task_id,"task_id")
        if self.authority_effect!="NONE" or self.runtime_effect!="NONE": raise ValueError("route cannot grant authority/effect")
        return self

def route_task(task,policy,profile,*,active_local_inferences=0):
    if type(task) is not TaskEnvelope or type(policy) is not HybridRoutingPolicy or type(profile) is not ModelProfile: raise ValueError("exact types required")
    task.validate();policy.validate();profile.validate(); pd=policy.digest()
    if (profile.model_digest,profile.runtime_digest)!=(policy.local_model_digest,policy.local_runtime_digest): raise ValueError("model profile substitution")
    if type(active_local_inferences) is not int or active_local_inferences<0: raise ValueError("active_local_inferences")
    if task.operation_class=="DETERMINISTIC_TEST": return RouteDecision("DETERMINISTIC","test/hash/schema work is deterministic",pd,task.task_id).validate()
    if task.authority_bound or task.task_class in SENSITIVE: return RouteDecision("SAAS","sensitive reasoning requires SaaS review and downstream authority gates",pd,task.task_id).validate()
    if task.input_tokens>min(policy.local_context_limit,profile.context_limit): return RouteDecision("SAAS","context overflow escalates; no truncation",pd,task.task_id).validate()
    local_ok=(profile.runtime_state=="ACTIVE" and task.task_class in policy.local_classes and task.task_class in profile.qualified_classes)
    if local_ok:
        if active_local_inferences>=min(policy.local_parallel_slots,profile.parallel_slots): return RouteDecision("QUEUE","single local slot busy",pd,task.task_id).validate()
        return RouteDecision("LOCAL","qualified bounded local proposal class",pd,task.task_id).validate()
    if task.data_may_leave_host: return RouteDecision("SAAS","local route unavailable or unqualified",pd,task.task_id).validate()
    return RouteDecision("DEFER","no qualified on-host route and data egress denied",pd,task.task_id).validate()
